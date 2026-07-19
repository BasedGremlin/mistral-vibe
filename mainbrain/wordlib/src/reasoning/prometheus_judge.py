"""
Prometheus Judge (honest LLM-as-judge wrapper).
==============================================
HONESTY NOTE: "Prometheus" refers to PrometheusEval, a real open evaluator-LLM.
There is NO local prometheus_loader.py in this project and this file does not
pretend one exists. What this provides is a REAL wrapper that:

  - uses whatever judge-capable model is available via Ollama (configurable;
    defaults to the general model dolphin3 if no dedicated judge is installed)
  - applies structured rubrics for creative writing + chat quality
  - returns structured, actionable feedback agents can use
  - degrades honestly: if no model server is reachable, it falls back to the
    heuristic ReasoningGuard and SAYS it did

It does not claim judge quality it can't deliver. With only a general model,
the scores are "a capable local model's opinion", not a calibrated benchmark.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .reasoning_guard import ReasoningGuard
from .structured_output import StructuredOutputEngine


CREATIVE_RUBRIC = {
    "coherence":      "Does it hold together logically and structurally?",
    "narrative":      "Is there narrative momentum / a sense of progression?",
    "emotional":      "Does it evoke the intended emotion?",
    "originality":    "Is it fresh rather than clich√©d?",
    "degeneracy":     "Is it free of repetition/looping/incoherence? (high=clean)",
}

CHAT_RUBRIC = {
    "relevance":      "Does it actually answer what was asked?",
    "accuracy":       "Are the factual claims correct as far as can be told?",
    "clarity":        "Is it clear and well-organized?",
    "honesty":        "Does it avoid overclaiming and admit uncertainty?",
}


@dataclass
class JudgeVerdict:
    mode: str                       # "model" | "heuristic-fallback"
    scores: Dict[str, float] = field(default_factory=dict)
    overall: float = 0.0
    suggestions: List[str] = field(default_factory=list)
    note: str = ""

    def as_dict(self):
        return {"mode": self.mode, "scores": self.scores,
                "overall": round(self.overall, 3),
                "suggestions": self.suggestions, "note": self.note}


class PrometheusJudge:
    def __init__(self, model: str = "dolphin3:8b-llama3.1-q4_K_M",
                 ollama_url: str = "http://localhost:11434") -> None:
        self.model = model
        self.ollama_url = ollama_url
        self.guard = ReasoningGuard()
        self.json_engine = StructuredOutputEngine()

    def _ollama_available(self) -> bool:
        import urllib.request
        try:
            urllib.request.urlopen(f"{self.ollama_url}/api/tags", timeout=2)
            return True
        except Exception:
            return False

    def judge(self, text: str, kind: str = "creative") -> JudgeVerdict:
        rubric = CREATIVE_RUBRIC if kind == "creative" else CHAT_RUBRIC

        if not self._ollama_available():
            # Honest fallback -- heuristic guard, clearly labeled
            v = self.guard.evaluate(text)
            return JudgeVerdict(
                mode="heuristic-fallback",
                scores={"surface_quality": round(v.score, 3)},
                overall=v.score,
                suggestions=[v.suggestion] if v.suggestion else [],
                note=("No model server reachable -- used heuristic ReasoningGuard, "
                      "NOT a real judge model. Scores are surface-level only."))

        # Model-backed judging
        prompt = self._build_prompt(text, rubric)
        raw = self._call_ollama(prompt)
        parsed = self.json_engine.parse(raw)
        if not parsed.ok:
            v = self.guard.evaluate(text)
            return JudgeVerdict("heuristic-fallback",
                                {"surface_quality": round(v.score, 3)}, v.score,
                                [v.suggestion],
                                "Judge model output unparseable -- fell back to heuristic.")
        data = parsed.data
        scores = {k: float(data.get(k, 0)) / 10.0 for k in rubric if k in data}
        overall = sum(scores.values()) / len(scores) if scores else 0.0
        return JudgeVerdict(
            mode="model",
            scores={k: round(v, 3) for k, v in scores.items()},
            overall=overall,
            suggestions=data.get("suggestions", []) if isinstance(data.get("suggestions"), list) else [],
            note=(f"Judged by local model '{self.model}'. This is a capable "
                  "model's opinion, not a calibrated benchmark."))

    def _build_prompt(self, text: str, rubric: Dict[str, str]) -> str:
        criteria = "\n".join(f'  "{k}": (1-10) {desc}' for k, desc in rubric.items())
        return (
            "You are a strict but fair writing evaluator. Score the TEXT on each "
            "criterion from 1-10 and give 1-3 concrete suggestions.\n"
            f"Criteria:\n{criteria}\n\n"
            "Respond ONLY with JSON of the form:\n"
            "{" + ", ".join(f'"{k}": <1-10>' for k in rubric) +
            ', "suggestions": ["...", "..."]}\n\n'
            f"TEXT:\n{text[:4000]}\n")

    def _call_ollama(self, prompt: str) -> str:
        import urllib.request
        body = json.dumps({"model": self.model, "prompt": prompt,
                           "stream": False, "options": {"temperature": 0.2}})
        req = urllib.request.Request(f"{self.ollama_url}/api/generate",
                                     data=body.encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read()).get("response", "")
        except Exception as e:
            return f'{{"error": "{e}"}}'
