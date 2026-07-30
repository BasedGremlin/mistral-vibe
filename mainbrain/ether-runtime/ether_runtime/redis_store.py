"""Redis-backed store adapter -- the distributed worker plane (W-03).

Implements the same surface as :class:`ether_runtime.store.TaskStore` so
``TaskRuntime`` and ``Worker`` drive it unchanged. SQLite remains the offline
default; this adapter is what lets several machines share one queue.

Design decisions, and why
-------------------------
*Injected clocks, never server time.* Every method takes the same optional
``now`` argument as the SQLite store, and lease/reclaim/delay comparisons use
it. Redis TTLs and ``TIME`` are deliberately unused: the existing suite drives
deterministic time (``now=T0 + 61``) to exercise reclaim, and a server-clock
implementation could not be tested that way.

*Integer entry ids.* Redis Stream ids are ``"<ms>-<seq>"`` strings, but
``StreamEntry.entry_id`` is ``int`` throughout the runtime and ``ack()`` is
typed ``int``. Rather than widen that type across the whole boundary, entry ids
come from an ``INCR`` counter, so the contract is identical to SQLite's
``AUTOINCREMENT``.

*Mirrors the SQLite tables, not Redis idioms.* Keys map 1:1 onto the tables in
``store.py`` (tasks / outbox / stream / pending / leases / absorbed). The point
is an adapter that is obviously equivalent to the reference implementation, not
a clever redesign whose divergence has to be re-proven.

Honest limits
-------------
Multi-key updates are pipelined, not transactional: Redis MULTI/EXEC is not
used because the read-then-write logic (claim, lease, dedup) needs values
mid-transaction. Concurrency safety therefore rests on the same lease
discipline the SQLite store uses, not on cross-key atomicity. Delivery remains
**at-least-once**, exactly as documented for the SQLite path.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from .store import Task, StreamEntry, stable_task_id

REDIS_STORE_CONTRACT = "ether_runtime.redis_store.v1.0"

DEFAULT_NAMESPACE = "ether"


class RedisUnavailable(RuntimeError):
    """The ``redis`` package is not installed, or the server is unreachable."""


def _require_redis():
    """Import ``redis`` lazily so the SQLite default stays stdlib-only."""
    try:
        import redis  # noqa: PLC0415 - deliberate optional dependency
    except ImportError as exc:  # pragma: no cover - exercised via error path
        raise RedisUnavailable(
            "the 'redis' package is required for RedisStoreAdapter; "
            "install it with `pip install redis`, or use the default "
            "SQLite TaskStore for offline/single-node operation"
        ) from exc
    return redis


class RedisStoreAdapter:
    """Duck-typed peer of :class:`TaskStore`, backed by Redis.

    Args:
        url: Redis connection URL, e.g. ``redis://localhost:6379/0``.
        namespace: Key prefix, so several deployments can share a server.
        client: Pre-built client (or test double). When given, ``url`` is
            ignored and the ``redis`` package is never imported -- this is how
            the suite exercises the adapter without a live server.
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        *,
        namespace: str = DEFAULT_NAMESPACE,
        client: Any = None,
    ) -> None:
        self.namespace = namespace
        if client is not None:
            self._r = client
        else:
            redis = _require_redis()
            try:
                self._r = redis.Redis.from_url(url, decode_responses=True)
                self._r.ping()
            except Exception as exc:  # noqa: BLE001 - connection boundary
                raise RedisUnavailable(f"cannot reach Redis at {url}: {exc}") from exc

    # -- key helpers --------------------------------------------------------

    def _k(self, *parts: str) -> str:
        return ":".join((self.namespace, *parts))

    @property
    def _k_task_ids(self) -> str:
        return self._k("tasks")

    @property
    def _k_outbox(self) -> str:
        return self._k("outbox")

    @property
    def _k_stream(self) -> str:
        return self._k("stream")

    @property
    def _k_entry_seq(self) -> str:
        return self._k("entry_seq")

    @property
    def _k_absorbed(self) -> str:
        return self._k("absorbed")

    def close(self) -> None:
        close = getattr(self._r, "close", None)
        if callable(close):
            close()

    # -- journal + outbox ---------------------------------------------------

    def submit(
        self,
        kind: str,
        payload: dict,
        idempotency_key: Optional[str] = None,
        max_attempts: int = 6,
        now: Optional[float] = None,
    ) -> Tuple[Task, bool]:
        """Journal a task and its outbox row. Idempotent on stable task id."""
        now = time.time() if now is None else now
        task_id = stable_task_id(kind, payload, idempotency_key)
        key = self._k("task", task_id)
        existing = self._r.hgetall(key)
        if existing:
            return self._task_from_hash(existing), False

        self._r.hset(key, mapping={
            "task_id": task_id,
            "kind": kind,
            "payload": json.dumps(payload),
            "status": "queued",
            "attempts": "0",
            "max_attempts": str(max_attempts),
            "created_at": repr(now),
            "updated_at": repr(now),
            "result": "",
            "error": "",
        })
        self._r.sadd(self._k_task_ids, task_id)
        # Outbox row: unclaimed until a publisher takes a lease on it.
        self._r.hset(self._k_outbox, task_id, json.dumps({
            "claimed_by": None, "claim_expires": 0.0, "created_at": now,
        }))
        return self.get_task(task_id), True

    def claim_outbox(
        self,
        publisher: str,
        limit: int = 16,
        lease_seconds: float = 30.0,
        now: Optional[float] = None,
    ) -> List[str]:
        """Claim unclaimed (or claim-expired) outbox rows for this publisher."""
        now = time.time() if now is None else now
        rows = self._r.hgetall(self._k_outbox)
        claimable = []
        for task_id, raw in rows.items():
            row = json.loads(raw)
            if row.get("claimed_by") is None or float(row.get("claim_expires", 0)) < now:
                claimable.append((float(row.get("created_at", 0)), task_id, row))
        claimable.sort(key=lambda t: (t[0], t[1]))

        claimed: List[str] = []
        for _created, task_id, row in claimable[:limit]:
            row["claimed_by"] = publisher
            row["claim_expires"] = now + lease_seconds
            self._r.hset(self._k_outbox, task_id, json.dumps(row))
            claimed.append(task_id)
        return claimed

    def publish_claimed(self, task_id: str, now: Optional[float] = None) -> int:
        """Move one claimed outbox row onto the stream.

        Two steps on purpose, mirroring the SQLite store: the entry is appended
        before the outbox row is dropped, so a crash between them republishes
        the task. That is the documented at-least-once window.
        """
        now = time.time() if now is None else now
        entry_id = self.append_stream_entry(task_id, now=now)
        self._r.hdel(self._k_outbox, task_id)
        return entry_id

    def append_stream_entry(
        self, task_id: str, not_before: float = 0.0, now: Optional[float] = None
    ) -> int:
        """Append a stream entry, optionally delayed until ``not_before``."""
        now = time.time() if now is None else now
        entry_id = int(self._r.incr(self._k_entry_seq))
        self._r.hset(self._k_stream, str(entry_id), json.dumps({
            "task_id": task_id, "not_before": not_before, "added_at": now,
        }))
        key = self._k("task", task_id)
        if self._r.hget(key, "status") == "queued":
            self._r.hset(key, mapping={"status": "published", "updated_at": repr(now)})
        return entry_id

    # -- consumer-group delivery -------------------------------------------

    def read_group(
        self, group: str, consumer: str, count: int = 8, now: Optional[float] = None
    ) -> List[StreamEntry]:
        """Deliver ready, not-yet-pending entries (XREADGROUP analog)."""
        now = time.time() if now is None else now
        pending_key = self._k("pending", group)
        pending = self._r.hgetall(pending_key)
        entries: List[StreamEntry] = []
        for entry_id_s, raw in sorted(
            self._r.hgetall(self._k_stream).items(), key=lambda kv: int(kv[0])
        ):
            if len(entries) >= count:
                break
            if entry_id_s in pending:
                continue
            row = json.loads(raw)
            if float(row["not_before"]) > now:
                continue
            self._r.hset(pending_key, entry_id_s, json.dumps({
                "consumer": consumer, "delivered_at": now, "delivery_count": 1,
            }))
            entries.append(StreamEntry(int(entry_id_s), row["task_id"], 1))
        return entries

    def autoclaim(
        self,
        group: str,
        consumer: str,
        min_idle_seconds: float,
        now: Optional[float] = None,
    ) -> List[StreamEntry]:
        """Transfer entries idle beyond the threshold (XAUTOCLAIM analog)."""
        now = time.time() if now is None else now
        pending_key = self._k("pending", group)
        cutoff = now - min_idle_seconds
        entries: List[StreamEntry] = []
        for entry_id_s, raw in sorted(
            self._r.hgetall(pending_key).items(), key=lambda kv: int(kv[0])
        ):
            row = json.loads(raw)
            if float(row["delivered_at"]) > cutoff:
                continue
            stream_raw = self._r.hget(self._k_stream, entry_id_s)
            if stream_raw is None:
                continue
            new_count = int(row["delivery_count"]) + 1
            self._r.hset(pending_key, entry_id_s, json.dumps({
                "consumer": consumer, "delivered_at": now, "delivery_count": new_count,
            }))
            entries.append(
                StreamEntry(int(entry_id_s), json.loads(stream_raw)["task_id"], new_count)
            )
        return entries

    def ack(self, entry_id: int) -> None:
        """Acknowledge: the entry leaves both the pending list and the stream."""
        for key in self._r.keys(self._k("pending", "*")):
            self._r.hdel(key, str(entry_id))
        self._r.hdel(self._k_stream, str(entry_id))

    # -- execution leases ---------------------------------------------------

    def acquire_lease(
        self,
        task_id: str,
        worker: str,
        lease_seconds: float,
        now: Optional[float] = None,
    ) -> bool:
        """Take the execution lease unless a different worker holds a live one."""
        now = time.time() if now is None else now
        key = self._k("lease", task_id)
        raw = self._r.get(key)
        if raw is not None:
            row = json.loads(raw)
            if float(row["expires"]) > now and row["worker"] != worker:
                return False
        self._r.set(key, json.dumps({"worker": worker, "expires": now + lease_seconds}))
        return True

    def release_lease(self, task_id: str, worker: str) -> None:
        key = self._k("lease", task_id)
        raw = self._r.get(key)
        if raw is not None and json.loads(raw)["worker"] == worker:
            self._r.delete(key)

    # -- task state transitions --------------------------------------------

    def mark_running(self, task_id: str, now: Optional[float] = None) -> int:
        """Set running, bump attempts, return the new attempt number."""
        now = time.time() if now is None else now
        key = self._k("task", task_id)
        attempts = int(self._r.hincrby(key, "attempts", 1))
        self._r.hset(key, mapping={"status": "running", "updated_at": repr(now)})
        return attempts

    def mark_completed(
        self, task_id: str, result: Any, now: Optional[float] = None
    ) -> None:
        now = time.time() if now is None else now
        self._r.hset(self._k("task", task_id), mapping={
            "status": "completed", "result": json.dumps(result),
            "error": "", "updated_at": repr(now),
        })

    def mark_retry_wait(
        self,
        task_id: str,
        error: str,
        delay_seconds: float,
        now: Optional[float] = None,
    ) -> None:
        """Record the failure and re-enqueue with a delayed stream entry."""
        now = time.time() if now is None else now
        self._r.hset(self._k("task", task_id), mapping={
            "status": "retry_wait", "error": error, "updated_at": repr(now),
        })
        entry_id = int(self._r.incr(self._k_entry_seq))
        self._r.hset(self._k_stream, str(entry_id), json.dumps({
            "task_id": task_id, "not_before": now + delay_seconds, "added_at": now,
        }))

    def mark_dead_lettered(
        self, task_id: str, error: str, now: Optional[float] = None
    ) -> None:
        now = time.time() if now is None else now
        self._r.hset(self._k("task", task_id), mapping={
            "status": "dead_lettered", "error": error, "updated_at": repr(now),
        })

    # -- absorption store ---------------------------------------------------

    def absorb(
        self, source: str, text: str, now: Optional[float] = None
    ) -> Tuple[str, bool]:
        """Content-hashed insert; duplicate content is a no-op."""
        import hashlib  # noqa: PLC0415 - local, mirrors store.absorb

        now = time.time() if now is None else now
        content_hash = hashlib.sha256(
            f"{source}\x00{text}".encode("utf-8")
        ).hexdigest()
        if self._r.hexists(self._k_absorbed, content_hash):
            return content_hash, False
        self._r.hset(self._k_absorbed, content_hash, json.dumps({
            "source": source, "text": text, "created_at": now,
        }))
        return content_hash, True

    # -- introspection ------------------------------------------------------

    def get_task(self, task_id: str) -> Task:
        row = self._r.hgetall(self._k("task", task_id))
        if not row:
            raise KeyError(f"unknown task {task_id!r}")
        return self._task_from_hash(row)

    def counts(self) -> dict:
        """Same six-key shape the SQLite store and the CLI doctor expect."""
        by_status: Dict[str, int] = {}
        for task_id in self._r.smembers(self._k_task_ids):
            status = self._r.hget(self._k("task", task_id), "status")
            if status:
                by_status[status] = by_status.get(status, 0) + 1
        pending = sum(
            len(self._r.hgetall(k)) for k in self._r.keys(self._k("pending", "*"))
        )
        return {
            "tasks_by_status": by_status,
            "outbox_backlog": len(self._r.hgetall(self._k_outbox)),
            "stream_depth": len(self._r.hgetall(self._k_stream)),
            "pending_entries": pending,
            "active_leases": len(self._r.keys(self._k("lease", "*"))),
            "absorbed_records": len(self._r.hgetall(self._k_absorbed)),
        }

    def iter_tasks(self, status: Optional[str] = None) -> Iterator[Task]:
        rows = []
        for task_id in self._r.smembers(self._k_task_ids):
            row = self._r.hgetall(self._k("task", task_id))
            if row and (status is None or row.get("status") == status):
                rows.append(row)
        for row in sorted(rows, key=lambda r: float(r.get("created_at", 0))):
            yield self._task_from_hash(row)

    @staticmethod
    def _task_from_hash(row: Dict[str, str]) -> Task:
        return Task(
            task_id=row["task_id"],
            kind=row["kind"],
            payload=json.loads(row["payload"]),
            status=row["status"],
            attempts=int(row["attempts"]),
            max_attempts=int(row["max_attempts"]),
            result=json.loads(row["result"]) if row.get("result") else None,
            error=row.get("error") or None,
        )


__all__ = [
    "REDIS_STORE_CONTRACT",
    "DEFAULT_NAMESPACE",
    "RedisStoreAdapter",
    "RedisUnavailable",
]
