"""
Agent base layer.
=================
Common types and the base Agent class. Every agent is a real class with a
single clear responsibility. Inter-agent communication goes through the
orchestrator's shared memory + task queue -- never direct agent-to-agent calls.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Task:
    kind: str                        # "plan" | "code" | "test" | "deploy" | ...
    payload: Dict[str, Any] = field(default_factory=dict)
    id: str = ""
    created: str = field(default_factory=_utc)

    def __post_init__(self):
        if not self.id:
            self.id = f"{self.kind}-{int(time.time()*1000)}"


@dataclass
class AgentResult:
    agent: str
    ok: bool
    output: Any = None
    detail: str = ""
    error: str = ""
    duration_ms: int = 0

    def as_dict(self) -> Dict:
        return {"agent": self.agent, "ok": self.ok, "detail": self.detail,
                "error": self.error, "duration_ms": self.duration_ms,
                "output": self.output if self._jsonable(self.output) else str(self.output)}

    @staticmethod
    def _jsonable(x) -> bool:
        import json
        try:
            json.dumps(x); return True
        except Exception:
            return False


class Agent:
    """Base agent. Subclasses implement handle(task, ctx) -> AgentResult."""
    name = "agent"
    handles: List[str] = []           # task kinds this agent accepts

    def __init__(self, ctx: "AgentContext") -> None:
        self.ctx = ctx
        self.available = True
        self.last_error: Optional[str] = None

    def can_handle(self, task: Task) -> bool:
        return task.kind in self.handles

    def handle(self, task: Task) -> AgentResult:
        raise NotImplementedError

    def _run(self, task: Task) -> AgentResult:
        """Wrapper adding timing + graceful degradation."""
        start = time.time()
        if not self.available:
            return AgentResult(self.name, False,
                               error="agent unavailable (degraded)")
        try:
            res = self.handle(task)
            res.duration_ms = int((time.time() - start) * 1000)
            return res
        except Exception as e:
            self.last_error = str(e)
            return AgentResult(self.name, False, error=str(e),
                               duration_ms=int((time.time() - start) * 1000))


@dataclass
class AgentContext:
    """Shared services + memory available to all agents (read via orchestrator)."""
    root: Any                          # Path to USB root
    shared_memory: Dict[str, Any] = field(default_factory=dict)
    services: Dict[str, Any] = field(default_factory=dict)  # editor, core, rag...
    audit: List[Dict] = field(default_factory=list)

    def remember(self, key: str, value: Any) -> None:
        self.shared_memory[key] = value

    def recall(self, key: str, default=None) -> Any:
        return self.shared_memory.get(key, default)

    def log(self, agent: str, action: str, detail: Dict) -> None:
        self.audit.append({"time": _utc(), "agent": agent,
                           "action": action, "detail": detail})
