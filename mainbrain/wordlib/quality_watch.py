#!/usr/bin/env python3
"""Quality-decay detector for the MAINBRAIN tree.

The proof gates in ``deploy_check.py`` answer "is it broken right now?".
They cannot answer "is it getting worse?", and that is the failure mode that
actually happens here: nothing snaps, the numbers just drift. Path-centralization
debt went 48 -> 49 -> 50 over a single working day, each step invisible because
every individual gate stayed green the whole time.

This records a baseline and compares against it, so drift has to be either
acknowledged or fixed rather than silently absorbed.

    python3 quality_watch.py --save-baseline    # record today as the reference
    python3 quality_watch.py                    # compare; non-zero on regression
    python3 quality_watch.py --json             # same, machine-readable

Design decisions, and why
-------------------------
*Only regressions fail.* Improvement is never an error, so metrics carry a
direction. A tool that fires on any change gets muted within a week, and a
muted detector is worse than none because it still looks like coverage.

*Baseline is committed, not generated at runtime.* A baseline recomputed on
each run can only ever agree with itself -- it would report "no drift" while
the tree rots. It has to be a record of a past state a human accepted.

*Everything comes from deploy_check.py.* No second measurement path to drift
out of sync with the first. If a number is wrong, it is wrong in one place.

Honest limits
-------------
This detects drift in what deploy_check already measures: syntax health,
capability count, module/function counts, path-centralization debt, and the
tree's own quality self-scores. It does NOT measure test coverage, runtime
correctness, or security posture, and a green report here says nothing about
any of them.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, NamedTuple

ROOT = Path(__file__).resolve().parent
# Deliberately NOT under data/: that directory is gitignored runtime state, so
# a baseline placed there would never reach a fresh clone or CI -- the tool
# would silently do nothing in exactly the environments it is meant to guard.
# The baseline is committed reference state, which is a different thing.
BASELINE_PATH = ROOT / "quality_baseline.json"


class Metric(NamedTuple):
    """One tracked number, and what a bad move looks like for it."""

    label: str
    extract: Callable[[Dict[str, Any]], Any]
    # "up" means higher is better; "down" means lower is better.
    better: str
    # Drift smaller than this is noise, not decay. 0 means any move counts.
    tolerance: float = 0.0


def _path_debt(report: Dict[str, Any]) -> int:
    """Pending path-centralization items (W-08), read off the warning text.

    deploy_check reports this as prose ("50 path centralization item(s) still
    pending") rather than a field. Parsing it is fragile, so a shape change
    returns -1 and is reported as unreadable rather than silently as 0 -- a
    metric that reads 0 because it broke looks identical to real progress.
    """
    for warning in report.get("intelligent_context", {}).get("warnings", []):
        match = re.search(r"(\d+)\s+path centralization", warning)
        if match:
            return int(match.group(1))
    return -1


METRICS = [
    Metric("syntax_broken",
           lambda r: len(r.get("syntax", {}).get("broken", [])), "down"),
    Metric("syntax_checked",
           lambda r: r.get("syntax", {}).get("checked", 0), "up"),
    Metric("parse_errors",
           lambda r: r.get("code_structure_hook", {}).get("summary", {})
                      .get("parse_errors", 0), "down"),
    Metric("capabilities_available",
           lambda r: int(str(r.get("capabilities", {})
                             .get("capabilities", "0/0")).split("/")[0]), "up"),
    Metric("modules",
           lambda r: r.get("code_structure_hook", {}).get("summary", {})
                      .get("modules", 0), "up"),
    Metric("path_centralization_pending", _path_debt, "down"),
    Metric("context_quality_score",
           lambda r: r.get("intelligent_context", {})
                      .get("overall_quality_score", 0.0), "up", tolerance=0.02),
    Metric("reflection_relevance_score",
           lambda r: r.get("nexus_reflection", {})
                      .get("overall_relevance_score", 0.0), "up", tolerance=0.02),
    Metric("docking_healthy",
           lambda r: 1 if r.get("docking_protocol", {}).get("healthy") else 0,
           "up"),
]


def collect() -> Dict[str, Any]:
    """Run the proof gates and reduce them to the tracked numbers."""
    completed = subprocess.run(
        [sys.executable, "deploy_check.py", "--json"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"deploy_check.py exited {completed.returncode}; fix the gates "
            "before measuring drift -- a baseline taken from a broken tree "
            "would bake the breakage in as normal.\n"
            f"{completed.stderr[-2000:]}"
        )
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"deploy_check.py did not emit valid JSON: {exc}")

    return {m.label: m.extract(report) for m in METRICS}


def compare(baseline: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    regressions, improvements, unreadable, missing = [], [], [], []

    for metric in METRICS:
        if metric.label not in baseline:
            # New metric: nothing to compare against, and treating its absence
            # as a regression would fail every run after the tool is extended.
            missing.append(metric.label)
            continue
        was, now = baseline[metric.label], current[metric.label]
        if now == -1:
            unreadable.append(metric.label)
            continue
        delta = now - was
        if abs(delta) <= metric.tolerance:
            continue
        worse = delta < 0 if metric.better == "up" else delta > 0
        entry = {"metric": metric.label, "was": was, "now": now,
                 "delta": round(delta, 4)}
        (regressions if worse else improvements).append(entry)

    return {
        "ok": not regressions and not unreadable,
        "regressions": regressions,
        "improvements": improvements,
        "unreadable": unreadable,
        "new_metrics": missing,
    }


def _render(result: Dict[str, Any]) -> None:
    if result["regressions"]:
        print("QUALITY DECAY DETECTED")
        for r in result["regressions"]:
            print(f"  {r['metric']}: {r['was']} -> {r['now']} ({r['delta']:+})")
    if result["unreadable"]:
        print("UNREADABLE (metric shape changed -- treat as a failure, not a pass):")
        for label in result["unreadable"]:
            print(f"  {label}")
    if result["improvements"]:
        print("Improved:")
        for i in result["improvements"]:
            print(f"  {i['metric']}: {i['was']} -> {i['now']} ({i['delta']:+})")
    if result["new_metrics"]:
        print("Not in baseline yet (re-run --save-baseline to adopt):")
        for label in result["new_metrics"]:
            print(f"  {label}")
    if result["ok"] and not result["improvements"]:
        print("No drift against baseline.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save-baseline", action="store_true",
                        help="record the current state as the reference")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable output")
    args = parser.parse_args()

    current = collect()

    if args.save_baseline:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(json.dumps(current, indent=2) + "\n",
                                 encoding="utf-8")
        if args.json:
            print(json.dumps({"saved": str(BASELINE_PATH), "baseline": current},
                             indent=2))
        else:
            print(f"Baseline written to {BASELINE_PATH}")
            for k, v in sorted(current.items()):
                print(f"  {k}: {v}")
        return 0

    if not BASELINE_PATH.exists():
        print(f"No baseline at {BASELINE_PATH}. Run --save-baseline first.",
              file=sys.stderr)
        return 2

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    result = compare(baseline, current)
    result["baseline_path"] = str(BASELINE_PATH)
    result["current"] = current

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _render(result)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
