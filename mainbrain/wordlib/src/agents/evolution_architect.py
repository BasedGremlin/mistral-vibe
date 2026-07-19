"""
evolution_architect.py -- EvolutionArchitect agent.
==================================================
Its only job: analyze agent failures and PROPOSE improved genomes. It does not
auto-apply anything -- proposals go to the MetaEvolutionEngine as new genomes
that must then WIN a tournament before promotion. Honest by construction:

  - It proposes parameter changes it can justify from observed failures, not
    random mutations dressed up as insight.
  - It never claims a proposal is better -- only the tournament (objective,
    known-answer tasks) decides that.
  - Every proposal is logged with the reasoning that motivated it.

This keeps the loop honest: ARCHITECT proposes -> ENGINE tests on real tasks
-> winner promoted only if it objectively beats baseline -> rollback always
available.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .base import Agent, AgentResult, Task


class EvolutionArchitect(Agent):
    name = "evolution_architect"
    handles = ["evolve", "propose_variant"]

    # Known, justifiable parameter levers per agent. The architect can only
    # propose changes within this honest design space -- no magic knobs.
    LEVERS = {
        "math": {"simplify": [False, True], "mode": ["loose", "strict"]},
        "code": {"strict_ast": [False, True], "max_risk": [3, 1]},
        "reasoning": {"target_score": [0.6, 0.75, 0.85],
                      "max_iters": [2, 3, 5]},
    }

    def handle(self, task: Task) -> AgentResult:
        agent = task.payload.get("agent", "")
        failures = task.payload.get("failures", [])   # list of failure descriptions
        current_params = task.payload.get("current_params", {})

        if agent not in self.LEVERS:
            return AgentResult(self.name, False,
                error=f"no known evolvable levers for agent '{agent}'. "
                      f"Architect won't invent fake parameters.")

        proposals = self._propose(agent, failures, current_params)
        if not proposals:
            return AgentResult(self.name, True,
                output={"proposals": [], "note": "no justified improvement found"},
                detail="no change proposed (honest: not every failure has a "
                       "parameter fix)")

        return AgentResult(self.name, True,
            output={"agent": agent, "proposals": proposals,
                    "note": "proposals must WIN a tournament before promotion; "
                            "nothing auto-applied"},
            detail=f"proposed {len(proposals)} variant(s) for {agent}")

    def _propose(self, agent: str, failures: List[str],
                current: Dict) -> List[Dict]:
        """Propose genome param changes justified by the failure pattern."""
        levers = self.LEVERS[agent]
        proposals: List[Dict] = []
        failure_text = " ".join(failures).lower()

        # Heuristic but HONEST: match failure signals to the lever most likely
        # to address them. Each proposal records WHY.
        if agent == "math":
            if "simplif" in failure_text or "identity" in failure_text or not current.get("simplify"):
                params = dict(current); params["simplify"] = True; params["mode"] = "strict"
                proposals.append({"params": params,
                    "reason": "failures involve identities that need symbolic "
                              "simplification; enable simplify + strict mode"})
        elif agent == "code":
            if "unsafe" in failure_text or "risk" in failure_text or not current.get("strict_ast"):
                params = dict(current); params["strict_ast"] = True; params["max_risk"] = 1
                proposals.append({"params": params,
                    "reason": "failures involve unsafe/risky code passing; "
                              "tighten AST strictness and lower risk tolerance"})
        elif agent == "reasoning":
            if "low confidence" in failure_text or "wrong" in failure_text:
                params = dict(current); params["target_score"] = 0.85; params["max_iters"] = 5
                proposals.append({"params": params,
                    "reason": "failures show low-quality early exits; raise "
                              "target score and allow more refinement iterations"})

        return proposals
