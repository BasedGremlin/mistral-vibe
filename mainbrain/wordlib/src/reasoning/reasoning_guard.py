"""
ReasoningGuard.
===============
The honest heuristic output-quality checker, under the name the v13 spec asked
for. It wraps OutputQualityChecker and adds a clear PASS/REVISE verdict plus an
actionable suggestion. It does NOT detect hallucination or truth -- it flags
real surface patterns (overconfidence, hedging, unsupported numbers, vibes,
missing evidence). Every verdict says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .output_quality import OutputQualityChecker, QualityResult


@dataclass
class GuardVerdict:
    passed: bool
    score: float
    flags: List[str]
    suggestion: str
    disclaimer: str = ("Surface heuristic only: a pass means few red-flag "
                       "patterns, NOT verified truth.")


class ReasoningGuard:
    def __init__(self, threshold: float = 0.6) -> None:
        self.checker = OutputQualityChecker(threshold=threshold)

    def evaluate(self, text: str) -> GuardVerdict:
        r: QualityResult = self.checker.check(text)
        suggestion = self._suggest(r)
        return GuardVerdict(r.passed, r.score, r.flags, suggestion)

    def _suggest(self, r: QualityResult) -> str:
        if r.passed and not r.flags:
            return "No surface issues. Still verify claims with evidence/tests."
        tips = []
        b = r.breakdown
        if b.get("overconfidence"):
            tips.append("replace absolute claims (100%, guaranteed) with measured statements")
        if b.get("unsupported_numbers"):
            tips.append("cite a source or test for each numeric claim")
        if b.get("vibe_phrases"):
            tips.append("remove vibe phrases ('it just works', 'trust me')")
        if b.get("corporate_filler"):
            tips.append("cut corporate filler; say the concrete thing")
        if b.get("hedges", 0) > 3:
            tips.append("reduce hedging; state what you actually know")
        return "; ".join(tips) if tips else "tighten phrasing"
