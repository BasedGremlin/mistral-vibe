"""
Uncertainty Quantifier.
=======================
Real statistics for honest confidence reporting. No hand-wavy "confidence
scores" -- these are textbook methods that produce defensible numbers:

  - Wilson score interval  : a proper confidence interval for a success rate
                             (better than naive +/- for small samples)
  - Brier score            : measures how well-calibrated probabilistic
                             predictions are (lower = better)
  - Expected Calibration    : ECE -- gap between predicted confidence and
    Error (ECE)             actual accuracy across bins
  - Calibration tracking    : records (predicted_prob, actual_outcome) pairs
                             so the system learns whether its confidence is
                             trustworthy over time

These let the system say "70% confident, and historically my 70% predictions
are right 68% of the time" -- which is real, useful, and honest.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class Interval:
    point: float
    low: float
    high: float
    method: str

    def as_dict(self):
        return {"point": round(self.point, 4), "low": round(self.low, 4),
                "high": round(self.high, 4), "method": self.method}


class UncertaintyQuantifier:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root
        self.calib_path = (root / "data" / "calibration.jsonl") if root else None

    # ── Confidence intervals ─────────────────────────────────────────────────
    def wilson_interval(self, successes: int, n: int,
                        z: float = 1.96) -> Interval:
        """
        Wilson score interval for a binomial proportion (95% default).
        Robust for small n, unlike the naive normal approximation.
        """
        if n == 0:
            return Interval(0.0, 0.0, 1.0, "wilson (no data)")
        p = successes / n
        denom = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denom
        margin = (z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
        return Interval(p, max(0.0, center - margin),
                        min(1.0, center + margin), "wilson")

    def mean_interval(self, values: List[float], z: float = 1.96) -> Interval:
        """Confidence interval for a mean (normal approx)."""
        n = len(values)
        if n == 0:
            return Interval(0.0, 0.0, 0.0, "mean (no data)")
        mean = sum(values) / n
        if n == 1:
            return Interval(mean, mean, mean, "mean (n=1)")
        var = sum((v - mean) ** 2 for v in values) / (n - 1)
        se = math.sqrt(var / n)
        return Interval(mean, mean - z * se, mean + z * se, "mean")

    # ── Calibration scoring ──────────────────────────────────────────────────
    def brier_score(self, pairs: List[Tuple[float, int]]) -> float:
        """
        Brier score over (predicted_prob, actual_outcome 0/1) pairs.
        0 = perfect, 0.25 = always guessing 0.5, 1 = confidently wrong.
        """
        if not pairs:
            return float("nan")
        return sum((p - o) ** 2 for p, o in pairs) / len(pairs)

    def expected_calibration_error(self, pairs: List[Tuple[float, int]],
                                   bins: int = 10) -> float:
        """
        ECE: average gap between predicted confidence and actual accuracy,
        weighted by bin population. Lower = better calibrated.
        """
        if not pairs:
            return float("nan")
        buckets: List[List[Tuple[float, int]]] = [[] for _ in range(bins)]
        for p, o in pairs:
            idx = min(bins - 1, int(p * bins))
            buckets[idx].append((p, o))
        n = len(pairs)
        ece = 0.0
        for bucket in buckets:
            if not bucket:
                continue
            avg_conf = sum(p for p, _ in bucket) / len(bucket)
            accuracy = sum(o for _, o in bucket) / len(bucket)
            ece += (len(bucket) / n) * abs(avg_conf - accuracy)
        return ece

    # ── Persistent calibration tracking ──────────────────────────────────────
    def record(self, predicted_prob: float, actual_outcome: int,
               label: str = "") -> None:
        """Append a (prediction, outcome) pair to the calibration log."""
        if not self.calib_path:
            return
        self.calib_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"time": datetime.now(timezone.utc).isoformat(),
                 "p": predicted_prob, "outcome": actual_outcome, "label": label}
        try:
            with open(self.calib_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def load_history(self) -> List[Tuple[float, int]]:
        pairs = []
        if self.calib_path and self.calib_path.exists():
            for line in self.calib_path.read_text(encoding="utf-8").splitlines():
                try:
                    e = json.loads(line)
                    pairs.append((float(e["p"]), int(e["outcome"])))
                except Exception:
                    continue
        return pairs

    def calibration_report(self) -> dict:
        """Summarize how trustworthy past confidence has been."""
        pairs = self.load_history()
        if not pairs:
            return {"samples": 0, "note": "no calibration history yet"}
        return {
            "samples": len(pairs),
            "brier_score": round(self.brier_score(pairs), 4),
            "ece": round(self.expected_calibration_error(pairs), 4),
            "note": "Brier: 0=perfect, 0.25=coin-flip. ECE: lower=better calibrated.",
        }

    def adjust_confidence(self, raw_confidence: float) -> float:
        """
        If history shows we're systematically over/under-confident, nudge a raw
        confidence toward reality. Conservative: only adjusts with enough data.
        """
        pairs = self.load_history()
        if len(pairs) < 20:
            return raw_confidence  # not enough data to trust an adjustment
        # Compare predicted mean confidence vs actual accuracy
        avg_pred = sum(p for p, _ in pairs) / len(pairs)
        accuracy = sum(o for _, o in pairs) / len(pairs)
        bias = avg_pred - accuracy   # positive = overconfident
        adjusted = raw_confidence - bias * 0.5  # damp half the historical bias
        return max(0.0, min(1.0, adjusted))
