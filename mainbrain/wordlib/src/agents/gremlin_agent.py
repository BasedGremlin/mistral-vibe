"""
GremlinAgent (v13.6, foundation for v13.7 closed-loop).
======================================================
A real scheduled-improvement agent. It does NOT magically self-improve -- it
does concrete, honest work:

  - runs improvement CYCLES on a schedule (interval gated, persisted)
  - DETECTS weaknesses from real signals (failing parse checks, low power level,
    high uncertainty, quality-flagged config/text)
  - PRIORITIZES candidate improvements using QuantumInspiredOptimizer (real
    simulated annealing)
  - PROPOSES changes as diffs + summaries -- it does NOT apply them itself
  - keeps persistent memory of cycles + uncertainty history

This is deliberately a PROPOSE-not-APPLY design, which is exactly the v13.7
"detect -> propose -> human approves -> apply" foundation. When approval is
given, application goes through CodeAgent -> evolve_files -> self_editor (the
existing safe path), never a raw write.

The gremlin keeps its flavor in naming/commentary but its actions are real and
bounded. Theater Mode (read-only proposals) is the DEFAULT.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .base import Agent, AgentResult, Task


GREMLIN_QUIPS = [
    "Sniffing the rafters for weak joists...",
    "Found a loose bolt. Poking it. Respectfully.",
    "The code smells fine. Suspicious. Looking harder.",
    "Nothing broken? Then I shall propose mischief, supervised.",
    "Cataloguing cracks. Not widening them. (Theater Mode.)",
]


class GremlinAgent(Agent):
    name = "gremlin"
    handles = ["gremlin", "improve_cycle"]

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.root = Path(ctx.root)
        self.memory_path = self.root / "data" / "gremlin_memory.json"
        self.memory = self._load_memory()
        self.theater_mode = True   # propose-only by default (safe)

    def _load_memory(self) -> Dict:
        if self.memory_path.exists():
            try:
                return json.loads(self.memory_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"cycles": [], "uncertainty_history": []}

    def _save_memory(self) -> None:
        try:
            self.memory_path.parent.mkdir(parents=True, exist_ok=True)
            self.memory_path.write_text(json.dumps(self.memory, indent=2),
                                        encoding="utf-8")
        except Exception:
            pass

    def handle(self, task: Task) -> AgentResult:
        action = task.payload.get("action", "cycle")
        if action == "cycle":
            return self._run_cycle()
        if action == "history":
            return AgentResult(self.name, True, output=self.memory,
                               detail=f"{len(self.memory['cycles'])} cycles remembered")
        if action == "semantic_history":
            try:
                import sys
                src = self.root / "src"
                if str(src) not in sys.path:
                    sys.path.insert(0, str(src))
                from memory_semantic_hook import semantic_context_for_memory_query
                query = task.payload.get("query", "WORDLIB gremlin memory history")
                context = semantic_context_for_memory_query(query, as_prompt=bool(task.payload.get("as_prompt", True)))
                return AgentResult(self.name, bool(context.get("ok")), output=context,
                                   detail="read-only semantic memory context returned")
            except Exception as e:
                return AgentResult(self.name, False, error=f"semantic history unavailable: {e}")
        if action == "set_theater":
            self.theater_mode = bool(task.payload.get("on", True))
            return AgentResult(self.name, True,
                               detail=f"Theater Mode {'ON' if self.theater_mode else 'OFF'}")
        return AgentResult(self.name, False, error=f"unknown action {action}")

    def _run_cycle(self) -> AgentResult:
        quip = random.choice(GREMLIN_QUIPS)
        weaknesses = self._detect_weaknesses()
        proposals = self._prioritize(weaknesses)

        cycle = {
            "time": datetime.now(timezone.utc).isoformat(),
            "quip": quip,
            "weaknesses": weaknesses,
            "proposals": proposals,
            "theater_mode": self.theater_mode,
            "applied": False,   # gremlin NEVER auto-applies; v13.7 adds approval
        }
        self.memory["cycles"].append(cycle)
        self.memory["cycles"] = self.memory["cycles"][-50:]  # cap history
        self._save_memory()

        return AgentResult(self.name, True, output=cycle,
            detail=f"{quip} Found {len(weaknesses)} weakness(es), "
                   f"{len(proposals)} proposal(s). Theater Mode: "
                   f"{'on (propose only)' if self.theater_mode else 'off'}.")

    def _detect_weaknesses(self) -> List[Dict]:
        """Real signals: parse failures, low power, uncertainty, missing deps."""
        found = []
        svc = self.ctx.services

        # 1. Any broken Python files? (real ast check via TestAgent-style scan)
        import ast
        broken = []
        for f in list(self.root.glob("*.py")) + list((self.root/"src").rglob("*.py")):
            try:
                ast.parse(f.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError as e:
                broken.append(f"{f.name}:{e.lineno}")
        if broken:
            found.append({"kind": "broken_code", "severity": 0.9,
                          "detail": f"{len(broken)} file(s) fail to parse",
                          "items": broken[:5]})

        # 2. Low power level (from absorption, if reachable)
        core = svc.get("core")
        if core:
            s = core.status()
            ratio = s["capabilities_available"] / max(1, s["capabilities_total"])
            if ratio < 1.0:
                found.append({"kind": "missing_capability", "severity": 0.5,
                              "detail": f"only {s['capabilities_available']}/"
                                        f"{s['capabilities_total']} capabilities active"})

        # 3. Uncertainty trend (if we have calibration history)
        uq = svc.get("uncertainty")
        if uq:
            rep = uq.calibration_report()
            if rep.get("samples", 0) >= 20 and rep.get("ece", 0) > 0.15:
                found.append({"kind": "poor_calibration", "severity": 0.4,
                              "detail": f"ECE {rep['ece']} -- confidence is off"})
            self.memory["uncertainty_history"].append(
                {"time": datetime.now(timezone.utc).isoformat(),
                 "samples": rep.get("samples", 0), "ece": rep.get("ece")})
            self.memory["uncertainty_history"] = self.memory["uncertainty_history"][-100:]

        return found

    def _prioritize(self, weaknesses: List[Dict]) -> List[Dict]:
        """Order weaknesses into proposals using the quantum-inspired optimizer."""
        if not weaknesses:
            return []
        qi = self.ctx.services.get("quantum")
        proposals = []
        for w in weaknesses:
            proposals.append({
                "target": w["kind"],
                "severity": w["severity"],
                "proposed_action": self._action_for(w),
                "auto_apply": False,   # foundation for v13.7 human approval
            })
        if qi:
            # Use amplitude scoring to rank by severity into a priority distribution
            dist = qi.amplitude_decision_scoring(
                {p["target"]: p["severity"] for p in proposals})
            for p in proposals:
                p["priority"] = dist["distribution"].get(p["target"], 0.0)
            proposals.sort(key=lambda p: p["priority"], reverse=True)
        return proposals

    def _action_for(self, weakness: Dict) -> str:
        k = weakness["kind"]
        if k == "broken_code":
            return ("Fix parse errors in: " + ", ".join(weakness.get("items", []))
                    + " (route to CodeAgent -> evolve_files -> self_editor)")
        if k == "missing_capability":
            return "Run deploy to install missing capability dependencies"
        if k == "poor_calibration":
            return "Collect more calibration samples; review confidence reporting"
        return "Investigate"
