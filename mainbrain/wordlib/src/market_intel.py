"""
market_intel.py -- MarketIntelAnalyst.
======================================
Honest market/feasibility analysis. The defining property: it analyzes ONLY
data it is actually given and is structurally incapable of inventing sources.

WHAT IT IS NOT:
  It is NOT a scraper. It does not "scan Weibo/Douyin/Xiaohongshu" -- those
  require auth, block automated access, and are unreachable from an offline-
  first USB system. A tool that claimed to scrape them would return fabricated
  "trends", which for business decisions is worse than useless.

WHAT IT IS:
  Give it real research -- pasted forum posts, a report, search results from a
  connected tool, your own notes -- and it produces:
    - a trend summary grounded ONLY in the supplied evidence
    - a feasibility analysis with a transparent 1-10 score and its components
    - a sources section that lists exactly what evidence was provided
  If given no evidence, it says "insufficient data" -- it never makes things up.

Every claim in its output is traceable to an input item. The LLM (via the
agent swarm) can do the language-heavy synthesis, but this module enforces the
honesty contract: no input -> no claim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class EvidenceItem:
    """A single piece of REAL research the user/agent supplies."""
    text: str
    source: str                  # where it came from -- required, no anonymous evidence
    url: str = ""
    date: str = ""

    def __post_init__(self):
        if not self.source or not self.source.strip():
            raise ValueError("Every evidence item needs a source. No anonymous evidence.")


@dataclass
class FeasibilityScore:
    opportunity: float           # 0-10 each
    demand: float
    competition: float           # higher = LESS competition (better)
    regulatory: float            # higher = FEWER barriers (better)
    overall: float = 0.0
    basis: str = ""

    def compute(self) -> "FeasibilityScore":
        # Transparent weighted average -- weights stated, not hidden
        self.overall = round(
            0.30 * self.opportunity + 0.30 * self.demand +
            0.20 * self.competition + 0.20 * self.regulatory, 1)
        return self


@dataclass
class MarketReport:
    topic: str
    trend_summary: List[str]
    feasibility: Optional[FeasibilityScore]
    sources: List[Dict]
    evidence_count: int
    confidence_note: str
    generated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> Dict:
        return {
            "topic": self.topic,
            "trend_summary": self.trend_summary,
            "feasibility": (self.feasibility.__dict__ if self.feasibility else None),
            "sources": self.sources,
            "evidence_count": self.evidence_count,
            "confidence_note": self.confidence_note,
            "generated": self.generated,
        }


class MarketIntelAnalyst:
    """
    Analyzes supplied evidence into a structured, honest market report.
    Never fabricates: no evidence -> explicit "insufficient data".
    """

    # Minimum evidence below which we refuse to score (would be guessing)
    MIN_EVIDENCE_FOR_SCORE = 3

    def __init__(self) -> None:
        self.evidence: List[EvidenceItem] = []

    def add_evidence(self, text: str, source: str, url: str = "", date: str = "") -> None:
        """Add ONE real piece of research. Source is mandatory."""
        self.evidence.append(EvidenceItem(text=text, source=source, url=url, date=date))

    def clear(self) -> None:
        self.evidence = []

    def _extract_signals(self) -> List[str]:
        """
        Pull recurring noun-phrase-ish signals from the supplied text. This is
        honest keyword surfacing -- NOT trend invention. It only reflects words
        that actually appear in the evidence.
        """
        from collections import Counter
        stop = {"the", "and", "for", "are", "with", "this", "that", "have",
                "from", "they", "will", "would", "could", "about", "more",
                "very", "what", "when", "which", "their", "there", "been"}
        words = []
        for e in self.evidence:
            for w in re.findall(r"[a-zA-Z\u4e00-\u9fff]{3,}", e.text.lower()):
                if w not in stop:
                    words.append(w)
        common = Counter(words).most_common(8)
        return [f"'{w}' (mentioned {n}x across evidence)" for w, n in common if n > 1]

    def build_report(self, topic: str,
                     feasibility: Optional[FeasibilityScore] = None,
                     trend_summary: Optional[List[str]] = None) -> MarketReport:
        """
        Produce the report. If there's too little evidence, the report SAYS so
        and refuses to fabricate a score.

        feasibility/trend_summary may be supplied by the LLM (which read the
        same evidence). If supplied, we attach them; if not, we surface raw
        signals so nothing is invented here.
        """
        n = len(self.evidence)
        sources = [{"source": e.source, "url": e.url, "date": e.date,
                    "excerpt": e.text[:120]} for e in self.evidence]

        if n == 0:
            return MarketReport(
                topic=topic, trend_summary=[],
                feasibility=None, sources=[], evidence_count=0,
                confidence_note=("INSUFFICIENT DATA: no evidence was supplied. "
                                 "This analyst does not scrape or invent data -- "
                                 "provide real research (posts, reports, search "
                                 "results) to analyze."))

        # Trend summary: use LLM-supplied if given, else honest raw signals
        if trend_summary:
            trends = trend_summary
            trend_note = "synthesized by the model from the supplied evidence"
        else:
            trends = self._extract_signals() or ["(no repeated signals found in evidence)"]
            trend_note = "raw recurring terms from the evidence (no model synthesis)"

        # Feasibility: only if enough evidence AND a score was computed on it
        if n < self.MIN_EVIDENCE_FOR_SCORE:
            feas = None
            conf = (f"LOW CONFIDENCE: only {n} evidence item(s) "
                    f"(need >= {self.MIN_EVIDENCE_FOR_SCORE} to score feasibility). "
                    f"Trends below are {trend_note}.")
        elif feasibility is None:
            feas = None
            conf = (f"{n} evidence items provided. No feasibility score computed "
                    f"(supply component scores to enable it). Trends are {trend_note}.")
        else:
            feas = feasibility.compute()
            conf = (f"Feasibility scored on {n} evidence items. Score is a "
                    f"transparent weighted average (opportunity/demand 30% each, "
                    f"competition/regulatory 20% each). Trends are {trend_note}.")

        return MarketReport(topic=topic, trend_summary=trends, feasibility=feas,
                            sources=sources, evidence_count=n, confidence_note=conf)

    def render_text(self, report: MarketReport) -> str:
        """Human-readable English report. Every section traceable to evidence."""
        lines = [f"MARKET INTELLIGENCE REPORT: {report.topic}",
                 "=" * 50, ""]
        lines.append(f"Evidence analyzed: {report.evidence_count} item(s)")
        lines.append(f"Note: {report.confidence_note}")
        lines.append("")
        lines.append("TREND SUMMARY")
        for t in report.trend_summary:
            lines.append(f"  - {t}")
        lines.append("")
        if report.feasibility:
            f = report.feasibility
            lines.append("BUSINESS FEASIBILITY ANALYSIS")
            lines.append(f"  Opportunity:  {f.opportunity}/10")
            lines.append(f"  Demand:       {f.demand}/10")
            lines.append(f"  Competition:  {f.competition}/10 (higher = less crowded)")
            lines.append(f"  Regulatory:   {f.regulatory}/10 (higher = fewer barriers)")
            lines.append(f"  OVERALL:      {f.overall}/10")
            if f.basis:
                lines.append(f"  Basis: {f.basis}")
            lines.append("")
        lines.append("SOURCES & REASONING (exactly what was analyzed)")
        for s in report.sources:
            tag = f"{s['source']}"
            if s['url']:
                tag += f" <{s['url']}>"
            lines.append(f"  - {tag}: \"{s['excerpt']}...\"")
        if not report.sources:
            lines.append("  (none -- no evidence was supplied)")
        return "\n".join(lines)
