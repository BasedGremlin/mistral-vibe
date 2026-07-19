"""ether_runtime -- pure-stdlib durable task runtime.

Offline reconstruction of the missing EtherAI Absorption System v11 artifact
(design record: mainbrain/handoff/30_RUNTIME_AND_MEMORY_DESIGNS/). SQLite WAL
journal + transactional outbox + consumer-group stream with idle reclaim,
deterministic jittered retries, allowlisted task types, at-least-once
delivery with terminal-state dedup. See README.md for honest limits.
"""

from .retry import (
    DEFAULT_MAX_ATTEMPTS,
    RECLAIM_IDLE_SECONDS,
    RETRY_DELAYS,
    jitter_factor,
    retry_delay,
    validate_policy,
)
from .runtime import GROUP, TaskRuntime, Worker
from .store import Task, TaskStore, stable_task_id
from .tasks import ALLOWED_KINDS, PayloadError

__all__ = [
    "ALLOWED_KINDS",
    "DEFAULT_MAX_ATTEMPTS",
    "GROUP",
    "PayloadError",
    "RECLAIM_IDLE_SECONDS",
    "RETRY_DELAYS",
    "Task",
    "TaskRuntime",
    "TaskStore",
    "Worker",
    "jitter_factor",
    "retry_delay",
    "stable_task_id",
    "validate_policy",
]
