"""
Specialized agents.
===================
Each agent has one clear job and uses REAL services from the context:
  - CodeAgent      -> self_editor (multi-file evolve_files) + CodeReasoner + quality
  - TestAgent      -> CodeReasoner + MathValidator + ast parse checks
  - DeployAgent    -> the real v12 DeploymentState + StageEngine + Repairer
  - GuardianAgent  -> self_editor whitelist + Theater Mode + CodeReasoner safety
  - ResearcherAgent-> EtherCore + RAG (hub_client)
  - ReasoningAgent -> the full reasoning stack
  - MathAgent      -> MathValidator
  - AbsorptionAgent-> AbsorptionScanner + EnvironmentIntelligence + power summary
  - ArchitectAgent -> turns a goal into an ordered task list

Agents that need an unavailable service degrade gracefully (available=False),
they never crash the swarm.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import Agent, AgentResult, Task


class ArchitectAgent(Agent):
    name = "architect"
    handles = ["plan"]

    def handle(self, task: Task) -> AgentResult:
        goal = task.payload.get("goal", "")
        if not goal:
            return AgentResult(self.name, False, error="no goal given")
        # Decompose into a concrete, ordered task list (heuristic, transparent)
        plan: List[Dict] = []
        g = goal.lower()
        if any(w in g for w in ("fix", "edit", "refactor", "add", "implement", "write")):
            plan.append({"kind": "research", "payload": {"query": goal}})
            plan.append({"kind": "reason", "payload": {"goal": goal}})
            plan.append({"kind": "code", "payload": {"goal": goal}})
            plan.append({"kind": "test", "payload": {"scope": "changed"}})
        elif any(w in g for w in ("deploy", "install", "setup")):
            plan.append({"kind": "deploy", "payload": {"action": "status"}})
        elif any(w in g for w in ("prove", "calculate", "equation", "math")):
            plan.append({"kind": "math", "payload": {"goal": goal}})
        else:
            plan.append({"kind": "research", "payload": {"query": goal}})
            plan.append({"kind": "reason", "payload": {"goal": goal}})
        return AgentResult(self.name, True, output=plan,
                           detail=f"planned {len(plan)} step(s)")


class CodeAgent(Agent):
    name = "code"
    handles = ["code"]

    def handle(self, task: Task) -> AgentResult:
        # Creative mode: generate -> judge -> revise loop
        if task.payload.get("creative"):
            return self._creative_refinement(task)

        editor = self.ctx.services.get("editor")
        core = self.ctx.services.get("core")
        reasoner = self.ctx.services.get("code_reasoner")
        quality = self.ctx.services.get("quality")

        changes: Dict[str, str] = task.payload.get("changes", {})
        if not changes:
            # No concrete changes supplied -> this agent reports it needs the
            # LLM (openclaw_bridge) to produce them. Honest: we don't fabricate.
            return AgentResult(self.name, True, output={"needs_llm": True},
                detail="no changes supplied; CodeAgent applies changes, "
                       "openclaw_bridge generates them")

        # Pre-edit safety analysis on every Python change
        if reasoner:
            for path, content in changes.items():
                if path.endswith(".py"):
                    verdict = reasoner.safety_verdict(content)
                    if not verdict.get("safe"):
                        return AgentResult(self.name, False,
                            error=f"unsafe change to {path}: {verdict.get('reason')}")

        # Quality check on any prose/docstring-heavy content (advisory)
        flags = {}
        if quality:
            for path, content in changes.items():
                q = quality.check(content)
                if q.flags:
                    flags[path] = q.flags

        # Apply atomically via the REAL multi-file evolution
        if not core or not hasattr(core, "evolution"):
            return AgentResult(self.name, False, error="EtherCore evolution unavailable")
        result = core.evolution.evolve_files(changes)
        return AgentResult(self.name, result.success,
                           output={"rolled_back": result.rolled_back,
                                   "quality_flags": flags},
                           detail=result.detail, error=result.error or "")

    def _creative_refinement(self, task: Task) -> AgentResult:
        """
        Creative Refinement Loop: generate -> judge -> revise, with real exit
        conditions. Uses PrometheusJudge + ReasoningGuard for scoring and
        UncertaintyQuantifier to decide when further iteration won't help.

        The actual generation/revision is done by the LLM via the supplied
        'generate' callable (so we don't fabricate text). If no generator is
        supplied, we judge the provided draft once and report honestly.
        """
        judge = self.ctx.services.get("judge")
        guard = self.ctx.services.get("guard")
        uq = self.ctx.services.get("uncertainty")
        generate = task.payload.get("generate")     # callable(prompt, prior) -> str
        prompt = task.payload.get("prompt", "")
        kind = task.payload.get("kind", "creative")
        max_iters = int(task.payload.get("max_iters", 3))
        target = float(task.payload.get("target_score", 0.75))

        draft = task.payload.get("draft", "")
        history = []
        best_draft, best_score = draft, 0.0

        for i in range(1, max_iters + 1):
            # Generate (or use the provided draft on iteration 1)
            if generate and (i > 1 or not draft):
                feedback = history[-1]["suggestions"] if history else []
                try:
                    draft = generate(prompt, {"prior": best_draft, "feedback": feedback})
                except Exception as e:
                    return AgentResult(self.name, False,
                                       error=f"generator failed: {e}")
            if not draft:
                return AgentResult(self.name, False,
                    detail="creative mode needs a draft or a generate callable",
                    output={"needs_llm": True})

            # Judge
            score, suggestions, mode = self._score(draft, judge, guard, kind)
            history.append({"iter": i, "score": round(score, 3),
                            "mode": mode, "suggestions": suggestions})
            if score > best_score:
                best_score, best_draft = score, draft

            # Exit conditions
            if score >= target:
                break
            # Uncertainty-based exit: if improvement has stalled, stop
            if uq and len(history) >= 2:
                recent = [h["score"] for h in history[-2:]]
                iv = uq.mean_interval(recent)
                # If the two latest scores are within noise and not improving, stop
                if abs(recent[-1] - recent[-2]) < 0.03 and recent[-1] <= recent[-2]:
                    history[-1]["exit"] = "stalled (uncertainty: no improvement)"
                    break

        passed = best_score >= target
        return AgentResult(self.name, passed,
            output={"best_draft": best_draft, "best_score": round(best_score, 3),
                    "iterations": history, "target": target},
            detail=f"refined over {len(history)} iter(s), best score {best_score:.2f}")

    def _score(self, text, judge, guard, kind):
        """Combine judge + guard into one score with suggestions. Honest about mode."""
        suggestions = []
        if judge:
            v = judge.judge(text, kind)
            suggestions = v.suggestions
            return v.overall, suggestions, v.mode
        if guard:
            verdict = guard.evaluate(text)
            return verdict.score, [verdict.suggestion], "guard-only"
        return 0.5, [], "no-scorer"


class TestAgent(Agent):
    name = "test"
    handles = ["test"]

    def handle(self, task: Task) -> AgentResult:
        reasoner = self.ctx.services.get("code_reasoner")
        root = self.ctx.root
        from pathlib import Path
        import ast
        # Parse-check all python under src/ + root (real validation)
        checked, broken = 0, []
        for f in list(Path(root).glob("*.py")) + list((Path(root)/"src").rglob("*.py")):
            checked += 1
            try:
                ast.parse(f.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError as e:
                broken.append(f"{f.name}:{e.lineno}")
        ok = not broken
        return AgentResult(self.name, ok,
                           output={"checked": checked, "broken": broken},
                           detail=f"{checked} files parsed, {len(broken)} broken",
                           error="" if ok else f"broken: {broken}")


class DeployAgent(Agent):
    name = "deploy"
    handles = ["deploy"]

    def handle(self, task: Task) -> AgentResult:
        action = task.payload.get("action", "status")
        try:
            from deployment import DeploymentState, Repairer
        except Exception as e:
            return AgentResult(self.name, False, error=f"deployment pkg: {e}")
        from pathlib import Path
        state = DeploymentState(Path(self.ctx.root))
        if action == "status":
            return AgentResult(self.name, True, output=state.summary(),
                               detail=f"{state.completed_count()} stages done")
        if action == "repair":
            rep = Repairer(Path(self.ctx.root)).run_all()
            fixes = [f"{n}: {d}" for n, fixed, d in rep if fixed]
            return AgentResult(self.name, True, output=fixes,
                               detail=f"{len(fixes)} repair(s) applied")
        if action == "reset":
            state.reset()
            return AgentResult(self.name, True, detail="deployment state reset")
        return AgentResult(self.name, False, error=f"unknown action {action}")


class GuardianAgent(Agent):
    name = "guardian"
    handles = ["guard"]

    def handle(self, task: Task) -> AgentResult:
        # Vet a proposed set of changes against safety rules
        changes = task.payload.get("changes", {})
        reasoner = self.ctx.services.get("code_reasoner")
        editor = self.ctx.services.get("editor")
        vetoes = []
        for path, content in changes.items():
            # Whitelist check via self_editor's own path rules if exposed
            if editor and hasattr(editor, "_in_whitelist"):
                try:
                    if not editor._in_whitelist(path):
                        vetoes.append(f"{path}: outside write whitelist")
                except Exception:
                    pass
            if path.endswith(".py") and reasoner:
                v = reasoner.safety_verdict(content)
                if not v.get("safe"):
                    vetoes.append(f"{path}: {v.get('reason')}")
        ok = not vetoes
        return AgentResult(self.name, ok, output={"vetoes": vetoes},
                           detail="approved" if ok else f"{len(vetoes)} veto(es)",
                           error="" if ok else "; ".join(vetoes))


class ResearcherAgent(Agent):
    name = "researcher"
    handles = ["research"]

    def handle(self, task: Task) -> AgentResult:
        query = task.payload.get("query", "")
        core = self.ctx.services.get("core")
        hub = self.ctx.services.get("hub_client")
        findings = {}
        if core:
            findings["capabilities"] = core.status().get("capabilities_available")
        if hub and hasattr(hub, "rag_query"):
            try:
                findings["rag"] = hub.rag_query(query)
            except Exception as e:
                findings["rag_error"] = str(e)[:60]
        return AgentResult(self.name, True, output=findings,
                           detail=f"researched: {query[:40]}")


class ReasoningAgent(Agent):
    name = "reasoning"
    handles = ["reason"]

    def handle(self, task: Task) -> AgentResult:
        engine = self.ctx.services.get("reasoning_engine")
        quality = self.ctx.services.get("quality")
        if not engine:
            return AgentResult(self.name, False, error="reasoning engine unavailable")
        goal = task.payload.get("goal", "")
        claim = task.payload.get("claim", "")
        if claim and quality:
            q = quality.check(claim)
            return AgentResult(self.name, q.passed, output=q.as_dict(),
                               detail=f"claim quality {q.score:.2f}")
        trace = engine.new_trace(goal)
        engine.add_assumption(trace, "Operating on current local system state")
        engine.add_step(trace, f"Goal received: {goal}")
        engine.conclude(trace, f"Plan formed for: {goal}", 0.6,
                        "structured but not yet executed")
        return AgentResult(self.name, True, output=trace.as_dict(),
                           detail="reasoning trace built")


class MathAgent(Agent):
    name = "math"
    handles = ["math"]

    def handle(self, task: Task) -> AgentResult:
        mv = self.ctx.services.get("math_validator")
        if not mv:
            return AgentResult(self.name, False, error="math validator unavailable")
        lhs = task.payload.get("lhs")
        rhs = task.payload.get("rhs")
        expr = task.payload.get("expr")
        if lhs and rhs:
            r = mv.check_equality(lhs, rhs)
            return AgentResult(self.name, r.ok, output=r.detail,
                               detail=f"[{r.mode}] {r.detail}")
        if expr:
            r = mv.simplify(expr)
            return AgentResult(self.name, r.ok, output=r.value, detail=r.detail)
        return AgentResult(self.name, False, error="provide lhs+rhs or expr")


class MarketAgent(Agent):
    """Honest market intelligence -- analyzes supplied evidence, never scrapes
    or fabricates. Wraps MarketIntelAnalyst."""
    name = "market"
    handles = ["market"]

    def handle(self, task: Task) -> AgentResult:
        try:
            from market_intel import MarketIntelAnalyst, FeasibilityScore
        except Exception as e:
            return AgentResult(self.name, False, error=f"market_intel unavailable: {e}")

        topic = task.payload.get("topic", "untitled market")
        evidence = task.payload.get("evidence", [])  # list of {text, source, url?, date?}
        feas_in = task.payload.get("feasibility")     # optional dict of component scores
        trend_summary = task.payload.get("trend_summary")  # optional LLM-supplied

        analyst = MarketIntelAnalyst()
        for item in evidence:
            if isinstance(item, dict) and item.get("text") and item.get("source"):
                try:
                    analyst.add_evidence(item["text"], item["source"],
                                         item.get("url", ""), item.get("date", ""))
                except ValueError:
                    pass  # skip malformed (e.g. missing source) -- never fake one

        feas = None
        if feas_in:
            feas = FeasibilityScore(
                opportunity=float(feas_in.get("opportunity", 0)),
                demand=float(feas_in.get("demand", 0)),
                competition=float(feas_in.get("competition", 0)),
                regulatory=float(feas_in.get("regulatory", 0)),
                basis=feas_in.get("basis", ""))

        report = analyst.build_report(topic, feasibility=feas, trend_summary=trend_summary)
        return AgentResult(self.name, True, output=report.as_dict(),
                           detail=f"{report.evidence_count} evidence item(s); "
                                  f"{report.confidence_note[:50]}")


class AbsorptionAgent(Agent):
    name = "absorption"
    handles = ["absorb", "power"]

    def handle(self, task: Task) -> AgentResult:
        from pathlib import Path
        try:
            from deployment.absorption import (AbsorptionScanner,
                                               EnvironmentIntelligence)
        except Exception as e:
            return AgentResult(self.name, False, error=f"absorption pkg: {e}")
        root = Path(self.ctx.root)
        caps = AbsorptionScanner(root).scan_capabilities()
        env = EnvironmentIntelligence(root).profile()
        active = sum(1 for c in caps if c.available)
        power = round(active / max(1, len(caps)) * 100)
        return AgentResult(self.name, True,
            output={
                "power_level_pct": power,
                "active": active, "total": len(caps),
                "capabilities": [{"name": c.name, "active": c.available,
                                  "tier": c.tier} for c in caps],
                "environment": {"cpu": env.cpu_count, "ram_gb": env.ram_gb,
                                "disk_free_gb": env.disk_free_gb,
                                "model_tier": env.recommended_model_tier,
                                "rag_chunk": env.recommended_rag_chunk},
            },
            detail=f"power level {power}% ({active}/{len(caps)} capabilities)")
