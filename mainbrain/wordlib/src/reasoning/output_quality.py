"""
Output Quality Checker  (the honest version of a "bullshit detector")
=====================================================================
IMPORTANT HONESTY NOTE:
A program cannot, in general, detect hallucination or "weak reasoning" -- that
is an unsolved problem and anyone claiming a local script does it is selling
you something. What this module ACTUALLY does is detect specific, real,
surface-level patterns that correlate with low-quality output:

  - overconfidence markers   ("guaranteed", "100%", "always", "never fails")
  - hedge-word density        ("maybe", "probably", "I think", "sort of")
  - unsupported numeric claims (a precise % or figure with no source nearby)
  - missing-evidence markers   (claims of fact with no citation/reference)
  - corporate filler           ("leverage synergies", "best-in-class")
  - empty-vibe phrasing        ("it just works", "trust me", "obviously")

These are HEURISTICS. A high score means "looks cleaner by these measures",
NOT "is true". The checker is honest about that in every result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class QualityResult:
    score: float                       # 0.0 - 1.0, higher = fewer red flags
    passed: bool                       # score >= threshold
    flags: List[str] = field(default_factory=list)
    breakdown: Dict[str, int] = field(default_factory=dict)
    note: str = ""

    def as_dict(self) -> Dict:
        return {
            "score": round(self.score, 3),
            "passed": self.passed,
            "flags": self.flags,
            "breakdown": self.breakdown,
            "note": self.note,
        }


class OutputQualityChecker:
    """
    Heuristic, transparent checker. Real signals only -- no claim to detect
    truth or hallucination. Used by agents to flag output that *looks* weak
    and should be revised or double-checked by a human/stronger model.
    """

    OVERCONFIDENCE = [
        r"\b100%\b", r"\bguaranteed\b", r"\balways works\b", r"\bnever fails\b",
        r"\bperfect(ly)?\b", r"\bflawless\b", r"\bzero (bugs|errors|risk)\b",
        r"\bcompletely safe\b", r"\bdefinitely\b", r"\bobviously\b",
    ]
    HEDGES = [
        r"\bmaybe\b", r"\bprobably\b", r"\bi think\b", r"\bsort of\b",
        r"\bkind of\b", r"\bi guess\b", r"\bmight be\b", r"\bperhaps\b",
        r"\bpossibly\b", r"\bseems? like\b",
    ]
    CORPORATE = [
        r"\bleverage\b", r"\bsynergy\b", r"\bbest-in-class\b", r"\bworld-class\b",
        r"\bparadigm shift\b", r"\bgame-?changer\b", r"\bcutting-edge\b",
        r"\brevolutionary\b", r"\bseamlessly\b", r"\bnext-generation\b",
    ]
    VIBES = [
        r"\bit just works\b", r"\btrust me\b", r"\bno worries\b",
        r"\beasy peasy\b", r"\bpiece of cake\b", r"\bdon'?t overthink\b",
    ]
    EVIDENCE_MARKERS = [
        r"\bbecause\b", r"\bsince\b", r"\baccording to\b", r"\bsource\b",
        r"\bmeasured\b", r"\btested\b", r"\bsee\b", r"\bref\b", r"\bdata\b",
        r"\bbenchmark\b", r"\bverified\b",
    ]

    def __init__(self, threshold: float = 0.6) -> None:
        self.threshold = threshold

    def _count(self, patterns: List[str], text: str) -> int:
        t = text.lower()
        return sum(len(re.findall(p, t)) for p in patterns)

    def _unsupported_numbers(self, text: str) -> int:
        """
        Count precise numeric/percentage claims that have NO evidence marker
        within the same sentence -- a real low-quality signal.
        """
        sentences = re.split(r"[.!?\n]", text)
        count = 0
        for s in sentences:
            has_number = bool(re.search(r"\b\d+(\.\d+)?%?\b", s))
            has_evidence = any(re.search(p, s.lower()) for p in self.EVIDENCE_MARKERS)
            if has_number and not has_evidence and len(s.split()) > 4:
                count += 1
        return count

    def check(self, text: str) -> QualityResult:
        if not text or not text.strip():
            return QualityResult(0.0, False, ["empty output"], {}, "No content to assess.")

        words = max(1, len(text.split()))
        breakdown = {
            "overconfidence":      self._count(self.OVERCONFIDENCE, text),
            "hedges":              self._count(self.HEDGES, text),
            "corporate_filler":    self._count(self.CORPORATE, text),
            "vibe_phrases":        self._count(self.VIBES, text),
            "unsupported_numbers": self._unsupported_numbers(text),
            "evidence_markers":    self._count(self.EVIDENCE_MARKERS, text),
        }

        flags = []
        # Penalty per signal, normalized by length
        penalty = 0.0
        if breakdown["overconfidence"]:
            penalty += 0.12 * breakdown["overconfidence"]
            flags.append(f"{breakdown['overconfidence']} overconfidence marker(s)")
        if breakdown["vibe_phrases"]:
            penalty += 0.15 * breakdown["vibe_phrases"]
            flags.append(f"{breakdown['vibe_phrases']} vibe-based phrase(s)")
        if breakdown["corporate_filler"]:
            penalty += 0.08 * breakdown["corporate_filler"]
            flags.append(f"{breakdown['corporate_filler']} corporate filler phrase(s)")
        if breakdown["unsupported_numbers"]:
            penalty += 0.10 * breakdown["unsupported_numbers"]
            flags.append(f"{breakdown['unsupported_numbers']} unsupported numeric claim(s)")
        # Excessive hedging (relative to length)
        hedge_density = breakdown["hedges"] / words
        if hedge_density > 0.03:
            penalty += 0.15
            flags.append(f"high hedge density ({breakdown['hedges']} in {words} words)")
        # Evidence is a small bonus
        bonus = min(0.1, 0.02 * breakdown["evidence_markers"])

        score = max(0.0, min(1.0, 1.0 - penalty + bonus))
        passed = score >= self.threshold

        note = ("Heuristic surface check only -- a high score means 'few red-flag "
                "patterns', NOT 'verified true'. Real verification still needs "
                "evidence and testing.")
        return QualityResult(score, passed, flags, breakdown, note)

    def explain(self, text: str) -> str:
        r = self.check(text)
        lines = [f"Quality score: {r.score:.2f} ({'PASS' if r.passed else 'NEEDS REVISION'})"]
        if r.flags:
            lines.append("Flags: " + "; ".join(r.flags))
        else:
            lines.append("No surface red flags found.")
        lines.append(r.note)
        return "\n".join(lines)
