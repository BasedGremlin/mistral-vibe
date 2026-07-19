"""
DispatchAgent -- durable worker plane bridge (merge plan Phase 3).
=================================================================
Connects the swarm to the ether-runtime durable task runtime when WORDLIB is
deployed inside the MAINBRAIN tree (mainbrain/ether-runtime next to this
wordlib root). Adapter-first federation: wordlib stays fully standalone --
when the runtime package is absent this agent reports unavailable instead of
pretending a worker plane exists.

The runtime only accepts bounded, allowlisted task envelopes (absorb_text,
verify_artifact). There is no arbitrary-execution path to dispatch through;
invalid envelopes are rejected at submit time by the runtime's own validator.

Task kinds:
  dispatch        {"task": {"kind": str, "payload": dict},
                   "idempotency_key": str?}       -> journal a task envelope
  dispatch_drain  {}                              -> run worker passes until
                                                     the queue drains
  dispatch_status {"task_id": str?}               -> one task's state, or
                                                     journal counts + policy
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .base import Agent, AgentContext, AgentResult, Task

# Deployment-relative location of the sibling package inside MAINBRAIN:
# <mainbrain>/wordlib/src/agents/dispatch_agent.py -> <mainbrain>/ether-runtime
_RUNTIME_DIR = Path(__file__).resolve().parents[3] / "ether-runtime"


def _import_runtime_module():
    """Import ether_runtime: plain import first, then the sibling location."""
    try:
        import ether_runtime  # noqa: F401
        return ether_runtime
    except ModuleNotFoundError:
        if not (_RUNTIME_DIR / "ether_runtime").is_dir():
            raise
        if str(_RUNTIME_DIR) not in sys.path:
            sys.path.insert(0, str(_RUNTIME_DIR))
        import ether_runtime
        return ether_runtime


class DispatchAgent(Agent):
    name = "dispatch"
    handles = ["dispatch", "dispatch_drain", "dispatch_status"]

    def __init__(self, ctx: AgentContext) -> None:
        super().__init__(ctx)
        self._module = None
        self._runtime = None
        try:
            self._module = _import_runtime_module()
        except Exception as e:
            self.available = False
            self.last_error = f"ether_runtime not importable: {e}"

    def _get_runtime(self):
        """Lazy TaskRuntime: journal lives in this tree's data/, and
        verify_artifact hashes are checked against files under the root."""
        if self._runtime is None:
            root = Path(self.ctx.root)
            self._runtime = self._module.TaskRuntime(
                root / "data" / "dispatch_runtime.db", artifact_root=root
            )
        return self._runtime

    def handle(self, task: Task) -> AgentResult:
        runtime = self._get_runtime()
        if task.kind == "dispatch":
            return self._dispatch(runtime, task.payload)
        if task.kind == "dispatch_drain":
            worker = self._module.Worker(runtime, name="wordlib-dispatch")
            executed = worker.run_until_drained()
            return AgentResult(self.name, True,
                               output={"executed": executed,
                                       "counts": runtime.store.counts()},
                               detail=f"drained {executed} task(s)")
        if task.kind == "dispatch_status":
            return self._status(runtime, task.payload)
        return AgentResult(self.name, False,
                           error=f"unhandled task kind '{task.kind}'")

    def _dispatch(self, runtime, payload: Dict[str, Any]) -> AgentResult:
        envelope = payload.get("task")
        if not isinstance(envelope, dict) or not isinstance(envelope.get("kind"), str) \
                or not isinstance(envelope.get("payload"), dict):
            return AgentResult(self.name, False,
                               error="payload.task must be {'kind': str, 'payload': dict}")
        try:
            submitted, created = runtime.submit(
                envelope["kind"], envelope["payload"],
                idempotency_key=payload.get("idempotency_key"),
            )
        except self._module.PayloadError as e:
            return AgentResult(self.name, False, error=f"rejected envelope: {e}")
        self.ctx.log(self.name, "dispatched",
                     {"task_id": submitted.task_id, "kind": submitted.kind,
                      "created": created})
        return AgentResult(self.name, True,
                           output={"task_id": submitted.task_id,
                                   "created": created,
                                   "status": submitted.status},
                           detail="journaled" if created else "duplicate (idempotent)")

    def _status(self, runtime, payload: Dict[str, Any]) -> AgentResult:
        task_id: Optional[str] = payload.get("task_id")
        if task_id:
            try:
                t = runtime.store.get_task(task_id)
            except KeyError as e:
                return AgentResult(self.name, False, error=str(e))
            return AgentResult(self.name, True,
                               output={"task_id": t.task_id, "kind": t.kind,
                                       "status": t.status, "attempts": t.attempts,
                                       "result": t.result, "error": t.error})
        return AgentResult(self.name, True, output=runtime.status())
