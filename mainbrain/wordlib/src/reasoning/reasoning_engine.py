"""
Reasoning Engine.
=================
A structured scaffold for step-by-step reasoning with explicit assumption
tracking and confidence scoring.

HONEST SCOPE: this does not make the underlying LLM smarter. What it provides
is structure -- it forces reasoning to be broken into steps, assumptions to be
named, and a confidence to be attached and justified. It also runs the
OutputQualityChecker over conclusions so weak phrasing is flagged. The actual
inference still comes from the model (dolphin3 / qwen via openclaw_bridge);
this engine organizes and audits it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .output_quality import OutputQualityChecker


@dataclass
class ReasoningStep:
    n: int
    statement: str
    depends_on: List[int] = field(default_factory=list)


@dataclass
class ReasoningTrace:
    goal: str
    steps: List[ReasoningStep] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    conclusion: str = ""
    confidence: float = 0.0          # 0..1, must be justified
    confidence_basis: str = ""
    quality_score: float = 0.0
    quality_flags: List[str] = field(default_factory=list)

    def as_dict(self):
        return {
            "goal": self.goal,
            "steps": [{"n": s.n, "statement": s.statement,
                       "depends_on": s.depends_on} for s in self.steps],
            "assumptions": self.assumptions,
            "conclusion": self.conclusion,
            "confidence": round(self.confidence, 2),
            "confidence_basis": self.confidence_basis,
            "quality_score": round(self.quality_score, 2),
            "quality_flags": self.quality_flags,
        }


class ReasoningEngine:
    def __init__(self) -> None:
        self.quality = OutputQualityChecker()

    def new_trace(self, goal: str) -> ReasoningTrace:
        return ReasoningTrace(goal=goal)

    def add_step(self, trace: ReasoningTrace, statement: str,
                 depends_on: Optional[List[int]] = None) -> ReasoningTrace:
        n = len(trace.steps) + 1
        trace.steps.append(ReasoningStep(n, statement, depends_on or []))
        return trace

    def add_assumption(self, trace: ReasoningTrace, assumption: str) -> ReasoningTrace:
        trace.assumptions.append(assumption)
        return trace

    def conclude(self, trace: ReasoningTrace, conclusion: str,
                 confidence: float, basis: str) -> ReasoningTrace:
        trace.conclusion = conclusion
        trace.confidence = max(0.0, min(1.0, confidence))
        trace.confidence_basis = basis
        # Audit the conclusion's phrasing
        q = self.quality.check(conclusion)
        trace.quality_score = q.score
        trace.quality_flags = q.flags
        # If the conclusion is overconfident-sounding but confidence is high
        # without much basis, dampen it honestly.
        if q.flags and confidence > 0.8 and len(basis.split()) < 6:
            trace.confidence = min(trace.confidence, 0.6)
            trace.confidence_basis += " (auto-dampened: high confidence, thin basis)"
        return trace

    def render(self, trace: ReasoningTrace) -> str:
        lines = [f"GOAL: {trace.goal}", ""]
        if trace.assumptions:
            lines.append("ASSUMPTIONS:")
            lines += [f"  - {a}" for a in trace.assumptions]
            lines.append("")
        lines.append("REASONING:")
        for s in trace.steps:
            dep = f" (from {s.depends_on})" if s.depends_on else ""
            lines.append(f"  {s.n}. {s.statement}{dep}")
        lines.append("")
        lines.append(f"CONCLUSION: {trace.conclusion}")
        lines.append(f"CONFIDENCE: {trace.confidence:.0%} -- {trace.confidence_basis}")
        if trace.quality_flags:
            lines.append(f"QUALITY FLAGS: {'; '.join(trace.quality_flags)}")
        return "\n".join(lines)
