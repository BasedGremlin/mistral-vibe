"""
ClawOrchestrator.
=================
Central brain. Holds the shared context, registers all agents, routes tasks to
the agent that handles their kind, and can run a plan (list of tasks) in order.
All inter-agent communication goes through here -- agents never call each other.

Wires in the REAL services (self_editor, EtherCore, reasoning stack) so agents
operate on the live system. Degrades gracefully: a missing service disables only
the agents that need it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import Agent, AgentContext, AgentResult, Task
from .specialized import (ArchitectAgent, CodeAgent, TestAgent, DeployAgent,
                          GuardianAgent, ResearcherAgent, ReasoningAgent,
                          MathAgent, AbsorptionAgent, MarketAgent)
from .gremlin_agent import GremlinAgent
from .evolution_architect import EvolutionArchitect
from .dispatch_agent import DispatchAgent


class ClawOrchestrator:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.ctx = AgentContext(root=self.root)
        self._wire_services()
        self.agents: Dict[str, Agent] = {}
        self._register_agents()

    # ── Service wiring (real, with graceful degradation) ────────────────────
    def _wire_services(self) -> None:
        src = self.root / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))

        svc = self.ctx.services

        # self_editor
        try:
            from self_editor import get_editor
            svc["editor"] = get_editor()
        except Exception as e:
            svc["editor"] = None
            self.ctx.log("orchestrator", "service_missing", {"editor": str(e)[:60]})

        # EtherCore (blob brain + evolution)
        try:
            from ether_core import get_core
            svc["core"] = get_core()
        except Exception as e:
            svc["core"] = None
            self.ctx.log("orchestrator", "service_missing", {"core": str(e)[:60]})

        # Reasoning stack
        try:
            from reasoning import (OutputQualityChecker, MathValidator,
                                   CodeReasoner, ReasoningEngine,
                                   StructuredOutputEngine, ReasoningGuard,
                                   UncertaintyQuantifier, QuantumInspiredOptimizer,
                                   PrometheusJudge)
            svc["quality"] = OutputQualityChecker()
            svc["math_validator"] = MathValidator()
            svc["code_reasoner"] = CodeReasoner()
            svc["reasoning_engine"] = ReasoningEngine()
            svc["json_engine"] = StructuredOutputEngine()
            svc["guard"] = ReasoningGuard()
            svc["uncertainty"] = UncertaintyQuantifier(self.root)
            svc["quantum"] = QuantumInspiredOptimizer()
            svc["judge"] = PrometheusJudge()
        except Exception as e:
            self.ctx.log("orchestrator", "reasoning_missing", {"err": str(e)[:60]})

        # hub_client (RAG over HTTP) -- optional
        try:
            from hub_client import HubClient
            svc["hub_client"] = HubClient()
        except Exception:
            svc["hub_client"] = None

        # Semantic memory hook -- optional, read-only, adapter-based
        try:
            from memory_semantic_hook import semantic_context_for_memory_query
            svc["semantic_memory_hook"] = semantic_context_for_memory_query
        except Exception as e:
            svc["semantic_memory_hook"] = None
            self.ctx.log("orchestrator", "semantic_memory_hook_missing", {"err": str(e)[:80]})

    def _register_agents(self) -> None:
        for cls in (ArchitectAgent, CodeAgent, TestAgent, DeployAgent,
                    GuardianAgent, ResearcherAgent, ReasoningAgent,
                    MathAgent, AbsorptionAgent, MarketAgent, GremlinAgent,
                    EvolutionArchitect, DispatchAgent):
            agent = cls(self.ctx)
            # Disable agents whose core dependency is missing
            if cls is CodeAgent and not self.ctx.services.get("core"):
                agent.available = False
            if cls is MathAgent and not self.ctx.services.get("math_validator"):
                agent.available = False
            if cls is ReasoningAgent and not self.ctx.services.get("reasoning_engine"):
                agent.available = False
            self.agents[agent.name] = agent

    # ── Routing ──────────────────────────────────────────────────────────────
    def route(self, task: Task) -> AgentResult:
        for agent in self.agents.values():
            if agent.can_handle(task):
                result = agent._run(task)
                self.ctx.log(agent.name, "handled",
                             {"task": task.kind, "ok": result.ok})
                return result
        return AgentResult("orchestrator", False,
                           error=f"no agent handles task kind '{task.kind}'")

    def run_plan(self, plan: List[Dict]) -> List[AgentResult]:
        """Execute a list of {kind, payload} tasks in order, sharing memory."""
        results = []
        for step in plan:
            task = Task(kind=step["kind"], payload=step.get("payload", {}))
            res = self.route(task)
            results.append(res)
            self.ctx.remember(f"result:{task.kind}", res.output)
            # Stop the chain if a non-optional step hard-fails
            if not res.ok and task.kind in ("code", "guard"):
                break
        return results

    def schedule_tasks(self, tasks: List[Dict]) -> List[Dict]:
        """
        Use the QuantumInspiredOptimizer (simulated annealing -- classical) to
        order independent tasks by assigning each a cost based on which agent
        handles it and current load. Returns tasks in optimized order.
        Falls back to original order if the optimizer is unavailable.
        """
        qi = self.ctx.services.get("quantum")
        if not qi or len(tasks) < 2:
            return tasks
        # Map each task kind to the agent that handles it
        kinds = [t["kind"] for t in tasks]
        agents = list({a.name for a in self.agents.values() if a.available})

        def cost(kind, agent):
            # Lower cost if the agent actually handles this kind; small penalty otherwise
            handler = next((a for a in self.agents.values()
                            if a.can_handle(Task(kind, {}))), None)
            if handler and handler.name == agent:
                return 1.0
            return 5.0

        alloc = qi.annealing_task_allocation(kinds, agents, cost, iterations=300)
        # Order tasks so well-matched (low-cost) ones run first
        ordered = sorted(tasks,
                         key=lambda t: cost(t["kind"], alloc["assignment"].get(t["kind"], "")))
        self.ctx.log("orchestrator", "scheduled",
                     {"cost": alloc["cost"], "method": alloc["method"]})
        return ordered

    def solve(self, goal: str) -> Dict[str, Any]:
        """High-level entry: architect plans, orchestrator executes."""
        plan_res = self.route(Task("plan", {"goal": goal}))
        if not plan_res.ok:
            return {"ok": False, "error": plan_res.error}
        plan = plan_res.output
        results = self.run_plan(plan)
        return {
            "ok": all(r.ok for r in results),
            "goal": goal,
            "plan": plan,
            "results": [r.as_dict() for r in results],
            "audit": self.ctx.audit[-len(results)-1:],
        }

    def evolution_status(self) -> dict:
        """Expose meta-evolution state: which agents are evolved + fitness.
        Honest: returns empty if no genomes registered yet (never fabricates)."""
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from evolution.meta_evolution_engine import MetaEvolutionEngine
            eng = MetaEvolutionEngine(self.ctx.root)
            return eng.status()
        except Exception as e:
            return {"error": str(e), "agents_with_genomes": []}

    def status(self) -> Dict[str, Any]:
        return {
            "agents": {n: {"available": a.available, "handles": a.handles}
                       for n, a in self.agents.items()},
            "services": {k: (v is not None) for k, v in self.ctx.services.items()},
            "agent_count": len(self.agents),
            "available_count": sum(1 for a in self.agents.values() if a.available),
        }


_orchestrator: Optional[ClawOrchestrator] = None

def get_orchestrator(root: Path) -> ClawOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ClawOrchestrator(root)
    return _orchestrator
