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
            return self._fallback(
                text, "No model server reachable -- used heuristic ReasoningGuard, "
                      "NOT a real judge model. Scores are surface-level only.")

        # Model-backed judging
        prompt = self._build_prompt(text, rubric)
        raw = self._call_ollama(prompt)
        parsed = self.json_engine.parse(raw)
        if not parsed.ok:
            return self._fallback(
                text, "Judge model output unparseable -- fell back to heuristic.")
        data = parsed.data
        if not isinstance(data, dict):
            return self._fallback(
                text, "Judge model returned valid JSON that was not an object -- "
                      "fell back to heuristic.")

        scores, rejected = self._normalize_scores(data, rubric)
        if not scores:
            # Every criterion was missing or unusable. Reporting overall=0.0 here
            # would be indistinguishable from "the model judged this as terrible",
            # so degrade honestly instead -- same discipline as the unreachable
            # and unparseable paths above.
            return self._fallback(
                text, "Judge model returned no usable numeric scores -- "
                      "fell back to heuristic.")

        overall = sum(scores.values()) / len(scores)
        note = (f"Judged by local model '{self.model}'. This is a capable "
                "model's opinion, not a calibrated benchmark.")
        if rejected:
            # Say so rather than quietly averaging over a smaller set: a verdict
            # built from 2 of 5 criteria is weaker than one built from all 5, and
            # the caller cannot tell from the number alone.
            note += (f" NOTE: ignored {len(rejected)} unusable criterion value(s) "
                     f"({', '.join(sorted(rejected))}); score averages only the "
                     f"{len(scores)} usable one(s).")
        return JudgeVerdict(
            mode="model",
            scores={k: round(v, 3) for k, v in scores.items()},
            overall=overall,
            suggestions=data.get("suggestions", []) if isinstance(data.get("suggestions"), list) else [],
            note=note)

    def _fallback(self, text: str, note: str) -> JudgeVerdict:
        """Heuristic verdict, always labelled as such.

        Every degraded path routes through here so that `mode` and `note` can
        never disagree -- a caller checking `mode == "model"` is the difference
        between "a model judged this" and "a regex did".
        """
        v = self.guard.evaluate(text)
        return JudgeVerdict(
            mode="heuristic-fallback",
            scores={"surface_quality": round(v.score, 3)},
            overall=v.score,
            suggestions=[v.suggestion] if v.suggestion else [],
            note=note)

    @staticmethod
    def _normalize_scores(data: Dict, rubric: Dict[str, str]):
        """Map raw 1-10 model output onto 0.0-1.0, dropping what cannot be used.

        The model is an untrusted input here: it is free to emit a string, a
        null, a list, or a number far outside the requested 1-10 band. Dividing
        such a value by 10 unchallenged produced real nonsense -- a returned 50
        became a score of 5.0 and dragged `overall` to 1.68, i.e. 168%, while a
        non-numeric value raised ValueError straight past every fallback this
        class has. Both are measured behaviours, not hypotheticals.

        Values outside the band are clamped rather than dropped: a model saying
        "12" for a 1-10 criterion clearly means "excellent", and clamping keeps
        that signal while bounding the damage. Values that are not numbers at
        all carry no recoverable signal, so they are rejected and reported.
        """
        scores: Dict[str, float] = {}
        rejected: List[str] = []
        for key in rubric:
            if key not in data:
                continue
            raw = data[key]
            if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
                # bool is an int subclass in Python; True/10 = 0.1 would be a
                # silently plausible-looking score from a meaningless value.
                rejected.append(key)
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                rejected.append(key)
                continue
            if value != value or value in (float("inf"), float("-inf")):
                rejected.append(key)  # NaN / inf survive float() but poison a mean
                continue
            scores[key] = max(0.0, min(1.0, value / 10.0))
        return scores, rejected

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
