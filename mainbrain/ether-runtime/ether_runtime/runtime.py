"""TaskRuntime: the gateway-side facade, and Worker: the consumer loop.

Flow (mirrors the v11 durability model):

    submit()                     -- SQLite task + outbox row in one transaction
      -> publish_pending()       -- publisher claims outbox rows -> stream
      -> Worker.run_once()       -- consumer-group read + idle-entry autoclaim
           -> execution lease    -- one runner per task, ever
           -> handler            -- allowlisted kinds only
           -> completed / retry_wait (jittered delay) / dead_lettered

SQLite terminal status is authoritative. Delivery is at-least-once; the
consumer skips (and acks) entries whose task is already terminal.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from . import retry
from .store import TERMINAL_STATUSES, StreamEntry, Task, TaskStore
from .tasks import HANDLERS, PayloadError, validate_payload

GROUP = "ether-workers"


class TaskRuntime:
    def __init__(self, db_path: str | Path, artifact_root: str | Path | None = None):
        self.store = TaskStore(db_path)
        root = Path(artifact_root) if artifact_root else Path(db_path).parent / "artifacts"
        root.mkdir(parents=True, exist_ok=True)
        self.artifact_root = root
        retry.validate_policy()

    def close(self) -> None:
        self.store.close()

    # -- gateway side -------------------------------------------------------

    def submit(
        self,
        kind: str,
        payload: dict,
        idempotency_key: str | None = None,
        now: float | None = None,
    ) -> tuple[Task, bool]:
        """Validate then journal a task. Unknown kinds never enter the system."""
        validate_payload(kind, payload)
        return self.store.submit(
            kind,
            payload,
            idempotency_key=idempotency_key,
            max_attempts=retry.DEFAULT_MAX_ATTEMPTS,
            now=now,
        )

    def publish_pending(
        self, publisher: str | None = None, now: float | None = None
    ) -> int:
        """Pump the outbox onto the stream; returns entries published."""
        publisher = publisher or f"pub-{uuid.uuid4().hex[:8]}"
        published = 0
        for task_id in self.store.claim_outbox(publisher, now=now):
            self.store.publish_claimed(task_id, now=now)
            published += 1
        return published

    def status(self) -> dict:
        return {"policy": retry.validate_policy(), **self.store.counts()}


class Worker:
    def __init__(self, runtime: TaskRuntime, name: str | None = None):
        self.runtime = runtime
        self.store = runtime.store
        self.name = name or f"worker-{uuid.uuid4().hex[:8]}"

    def run_once(self, now: float | None = None, batch: int = 8) -> list[dict]:
        """One scheduling pass: pump outbox, reclaim idle work, execute."""
        now = time.time() if now is None else now
        self.runtime.publish_pending(publisher=self.name, now=now)
        entries = self.store.autoclaim(
            GROUP, self.name, retry.RECLAIM_IDLE_SECONDS, now=now
        )
        entries += self.store.read_group(GROUP, self.name, count=batch, now=now)
        return [self.execute(entry, now=now) for entry in entries]

    def execute(self, entry: StreamEntry, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        task = self.store.get_task(entry.task_id)

        # Terminal-state duplicate detection: the at-least-once window ends here.
        if task.status in TERMINAL_STATUSES:
            self.store.ack(entry.entry_id)
            return {"task_id": task.task_id, "outcome": "duplicate_skipped"}

        lease_seconds = retry.MAX_TASK_TIMEOUT_SECONDS + 5.0
        if not self.store.acquire_lease(task.task_id, self.name, lease_seconds, now=now):
            # Another live worker owns it; leave the entry pending for reclaim.
            return {"task_id": task.task_id, "outcome": "lease_held"}

        attempt = self.store.mark_running(task.task_id, now=now)
        try:
            handler = HANDLERS[task.kind]
            result = handler(self.store, task.payload, self.runtime.artifact_root)
        except PayloadError as exc:
            # Malformed-but-journaled work is not retriable; fail it fast.
            self.store.mark_dead_lettered(task.task_id, f"payload: {exc}", now=now)
            self.store.ack(entry.entry_id)
            self.store.release_lease(task.task_id, self.name)
            return {"task_id": task.task_id, "outcome": "dead_lettered", "attempt": attempt}
        except Exception as exc:  # noqa: BLE001 - task isolation boundary
            self.store.ack(entry.entry_id)
            if attempt >= task.max_attempts:
                self.store.mark_dead_lettered(task.task_id, str(exc), now=now)
                outcome = "dead_lettered"
            else:
                delay = retry.retry_delay(task.task_id, attempt)
                self.store.mark_retry_wait(task.task_id, str(exc), delay, now=now)
                outcome = "retry_wait"
            self.store.release_lease(task.task_id, self.name)
            return {"task_id": task.task_id, "outcome": outcome, "attempt": attempt}

        self.store.mark_completed(task.task_id, result, now=now)
        self.store.ack(entry.entry_id)
        self.store.release_lease(task.task_id, self.name)
        return {
            "task_id": task.task_id,
            "outcome": "completed",
            "attempt": attempt,
            "result": result,
        }

    def run_until_drained(self, now: float | None = None, max_passes: int = 100) -> int:
        """Drive passes until no ready work remains; returns tasks executed."""
        executed = 0
        for _ in range(max_passes):
            outcomes = self.run_once(now=now)
            if not outcomes:
                break
            executed += sum(1 for o in outcomes if o["outcome"] != "lease_held")
        return executed
