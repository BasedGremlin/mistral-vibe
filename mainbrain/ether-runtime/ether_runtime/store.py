"""SQLite WAL task journal, transactional outbox, and stream queue.

Single-node durability core of the runtime. One database owns all state:

- tasks    -- the authoritative task journal (SQLite terminal status is
              authoritative; the stream is delivery plumbing).
- outbox   -- transactional outbox: a submit writes task + outbox row in ONE
              transaction; a publisher claims outbox rows under a lease and
              moves them onto the stream.
- stream   -- append-only delivery queue (Redis Streams stand-in). Entries
              carry not_before for delayed retry redelivery.
- pending  -- per-group pending entries list (PEL analog): who was delivered
              what, when, and how many times.
- leases   -- per-task execution leases so two consumers never run the same
              task concurrently.
- absorbed -- content-hashed store written by the absorb_text handler.

Honest properties (mirrors the v11 design record): delivery is AT-LEAST-ONCE,
not exactly-once. A crash between stream append and outbox delete republishes
the task; the duplicate is controlled by stable task ids, task uniqueness,
execution leases, and terminal-state duplicate detection at the consumer.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks(
  task_id      TEXT PRIMARY KEY,
  kind         TEXT NOT NULL,
  payload      TEXT NOT NULL,
  status       TEXT NOT NULL,
  attempts     INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL,
  created_at   REAL NOT NULL,
  updated_at   REAL NOT NULL,
  result       TEXT,
  error        TEXT
);
CREATE TABLE IF NOT EXISTS outbox(
  task_id       TEXT PRIMARY KEY,
  claimed_by    TEXT,
  claim_expires REAL,
  created_at    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS stream(
  entry_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id    TEXT NOT NULL,
  not_before REAL NOT NULL DEFAULT 0,
  added_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS pending(
  entry_id       INTEGER PRIMARY KEY,
  group_name     TEXT NOT NULL,
  consumer       TEXT NOT NULL,
  delivered_at   REAL NOT NULL,
  delivery_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS leases(
  task_id TEXT PRIMARY KEY,
  worker  TEXT NOT NULL,
  expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS absorbed(
  content_hash TEXT PRIMARY KEY,
  source       TEXT NOT NULL,
  text         TEXT NOT NULL,
  created_at   REAL NOT NULL
);
"""

TERMINAL_STATUSES = ("completed", "dead_lettered")


@dataclass(frozen=True)
class Task:
    task_id: str
    kind: str
    payload: dict
    status: str
    attempts: int
    max_attempts: int
    result: Any = None
    error: str | None = None


@dataclass(frozen=True)
class StreamEntry:
    entry_id: int
    task_id: str
    delivery_count: int


def stable_task_id(kind: str, payload: dict, idempotency_key: str | None) -> str:
    """Stable, reproducible task id from kind + canonical payload (+ key)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    seed = f"{kind}\x00{canonical}\x00{idempotency_key or ''}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


class TaskStore:
    """All state transitions run through here; every method is atomic."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        with self._conn:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # -- journal + outbox ---------------------------------------------------

    def submit(
        self,
        kind: str,
        payload: dict,
        idempotency_key: str | None = None,
        max_attempts: int = 6,
        now: float | None = None,
    ) -> tuple[Task, bool]:
        """Insert task + outbox row in one transaction (idempotent).

        Returns (task, created). A duplicate submit returns the existing task
        unchanged -- SQLite task uniqueness is the first dedup layer.
        """
        now = time.time() if now is None else now
        task_id = stable_task_id(kind, payload, idempotency_key)
        with self._conn:
            existing = self._conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if existing is not None:
                return self._task_from_row(existing), False
            self._conn.execute(
                "INSERT INTO tasks(task_id, kind, payload, status, attempts,"
                " max_attempts, created_at, updated_at)"
                " VALUES(?,?,?,?,0,?,?,?)",
                (task_id, kind, json.dumps(payload), "queued", max_attempts, now, now),
            )
            self._conn.execute(
                "INSERT INTO outbox(task_id, created_at) VALUES(?,?)", (task_id, now)
            )
        return self.get_task(task_id), True

    def claim_outbox(
        self,
        publisher: str,
        limit: int = 16,
        lease_seconds: float = 30.0,
        now: float | None = None,
    ) -> list[str]:
        """Claim unclaimed (or claim-expired) outbox rows for this publisher.

        Claim leases prevent two publishers from racing the same row.
        """
        now = time.time() if now is None else now
        with self._conn:
            rows = self._conn.execute(
                "SELECT task_id FROM outbox WHERE claimed_by IS NULL"
                " OR claim_expires < ? ORDER BY created_at LIMIT ?",
                (now, limit),
            ).fetchall()
            ids = [r["task_id"] for r in rows]
            for task_id in ids:
                self._conn.execute(
                    "UPDATE outbox SET claimed_by = ?, claim_expires = ?"
                    " WHERE task_id = ?",
                    (publisher, now + lease_seconds, task_id),
                )
        return ids

    def publish_claimed(self, task_id: str, now: float | None = None) -> int:
        """Move one claimed outbox row onto the stream.

        Split into two transactions ON PURPOSE: appending the stream entry and
        deleting the outbox row are separate failure domains. A crash between
        them republishes the task later -- the documented at-least-once window.
        Tests exercise it via append_stream_entry() alone.
        """
        now = time.time() if now is None else now
        entry_id = self.append_stream_entry(task_id, now=now)
        with self._conn:
            self._conn.execute("DELETE FROM outbox WHERE task_id = ?", (task_id,))
        return entry_id

    def append_stream_entry(
        self, task_id: str, not_before: float = 0.0, now: float | None = None
    ) -> int:
        now = time.time() if now is None else now
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO stream(task_id, not_before, added_at) VALUES(?,?,?)",
                (task_id, not_before, now),
            )
            self._conn.execute(
                "UPDATE tasks SET status = 'published', updated_at = ?"
                " WHERE task_id = ? AND status = 'queued'",
                (now, task_id),
            )
        return int(cur.lastrowid)

    # -- consumer-group delivery -------------------------------------------

    def read_group(
        self, group: str, consumer: str, count: int = 8, now: float | None = None
    ) -> list[StreamEntry]:
        """Deliver ready, not-yet-pending entries to `consumer` (XREADGROUP)."""
        now = time.time() if now is None else now
        with self._conn:
            rows = self._conn.execute(
                "SELECT s.entry_id, s.task_id FROM stream s"
                " LEFT JOIN pending p ON p.entry_id = s.entry_id"
                " WHERE p.entry_id IS NULL AND s.not_before <= ?"
                " ORDER BY s.entry_id LIMIT ?",
                (now, count),
            ).fetchall()
            entries = []
            for r in rows:
                self._conn.execute(
                    "INSERT INTO pending(entry_id, group_name, consumer,"
                    " delivered_at, delivery_count) VALUES(?,?,?,?,1)",
                    (r["entry_id"], group, consumer, now),
                )
                entries.append(StreamEntry(r["entry_id"], r["task_id"], 1))
        return entries

    def autoclaim(
        self,
        group: str,
        consumer: str,
        min_idle_seconds: float,
        now: float | None = None,
    ) -> list[StreamEntry]:
        """Transfer pending entries idle beyond the threshold (XAUTOCLAIM).

        Recovers work abandoned by crashed consumers.
        """
        now = time.time() if now is None else now
        with self._conn:
            rows = self._conn.execute(
                "SELECT p.entry_id, s.task_id, p.delivery_count FROM pending p"
                " JOIN stream s ON s.entry_id = p.entry_id"
                " WHERE p.group_name = ? AND p.delivered_at <= ?"
                " ORDER BY p.entry_id",
                (group, now - min_idle_seconds),
            ).fetchall()
            entries = []
            for r in rows:
                new_count = r["delivery_count"] + 1
                self._conn.execute(
                    "UPDATE pending SET consumer = ?, delivered_at = ?,"
                    " delivery_count = ? WHERE entry_id = ?",
                    (consumer, now, new_count, r["entry_id"]),
                )
                entries.append(StreamEntry(r["entry_id"], r["task_id"], new_count))
        return entries

    def ack(self, entry_id: int) -> None:
        """Acknowledge after processing: entry leaves pending AND the stream."""
        with self._conn:
            self._conn.execute("DELETE FROM pending WHERE entry_id = ?", (entry_id,))
            self._conn.execute("DELETE FROM stream WHERE entry_id = ?", (entry_id,))

    # -- execution leases ---------------------------------------------------

    def acquire_lease(
        self, task_id: str, worker: str, lease_seconds: float, now: float | None = None
    ) -> bool:
        now = time.time() if now is None else now
        with self._conn:
            row = self._conn.execute(
                "SELECT worker, expires FROM leases WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is not None and row["expires"] > now and row["worker"] != worker:
                return False
            self._conn.execute(
                "INSERT INTO leases(task_id, worker, expires) VALUES(?,?,?)"
                " ON CONFLICT(task_id) DO UPDATE SET worker=excluded.worker,"
                " expires=excluded.expires",
                (task_id, worker, now + lease_seconds),
            )
        return True

    def release_lease(self, task_id: str, worker: str) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM leases WHERE task_id = ? AND worker = ?",
                (task_id, worker),
            )

    # -- task state transitions --------------------------------------------

    def mark_running(self, task_id: str, now: float | None = None) -> int:
        """Set running and bump attempts; returns the new attempt number."""
        now = time.time() if now is None else now
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET status = 'running', attempts = attempts + 1,"
                " updated_at = ? WHERE task_id = ?",
                (now, task_id),
            )
            row = self._conn.execute(
                "SELECT attempts FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        return int(row["attempts"])

    def mark_completed(self, task_id: str, result: Any, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET status = 'completed', result = ?, error = NULL,"
                " updated_at = ? WHERE task_id = ?",
                (json.dumps(result), now, task_id),
            )

    def mark_retry_wait(
        self, task_id: str, error: str, delay_seconds: float, now: float | None = None
    ) -> None:
        """Record failure and re-enqueue with a delayed stream entry."""
        now = time.time() if now is None else now
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET status = 'retry_wait', error = ?, updated_at = ?"
                " WHERE task_id = ?",
                (error, now, task_id),
            )
            self._conn.execute(
                "INSERT INTO stream(task_id, not_before, added_at) VALUES(?,?,?)",
                (task_id, now + delay_seconds, now),
            )

    def mark_dead_lettered(self, task_id: str, error: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET status = 'dead_lettered', error = ?, updated_at = ?"
                " WHERE task_id = ?",
                (error, now, task_id),
            )

    # -- absorption store ---------------------------------------------------

    def absorb(self, source: str, text: str, now: float | None = None) -> tuple[str, bool]:
        """Content-hashed insert; duplicate content is a no-op (idempotent)."""
        now = time.time() if now is None else now
        content_hash = hashlib.sha256(
            f"{source}\x00{text}".encode("utf-8")
        ).hexdigest()
        with self._conn:
            existing = self._conn.execute(
                "SELECT 1 FROM absorbed WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            if existing is not None:
                return content_hash, False
            self._conn.execute(
                "INSERT INTO absorbed(content_hash, source, text, created_at)"
                " VALUES(?,?,?,?)",
                (content_hash, source, text, now),
            )
        return content_hash, True

    # -- introspection ------------------------------------------------------

    def get_task(self, task_id: str) -> Task:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown task {task_id!r}")
        return self._task_from_row(row)

    def counts(self) -> dict:
        by_status = {
            r["status"]: r["n"]
            for r in self._conn.execute(
                "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
            )
        }
        scalar = lambda sql: self._conn.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "tasks_by_status": by_status,
            "outbox_backlog": scalar("SELECT COUNT(*) FROM outbox"),
            "stream_depth": scalar("SELECT COUNT(*) FROM stream"),
            "pending_entries": scalar("SELECT COUNT(*) FROM pending"),
            "active_leases": scalar("SELECT COUNT(*) FROM leases"),
            "absorbed_records": scalar("SELECT COUNT(*) FROM absorbed"),
        }

    def iter_tasks(self, status: str | None = None) -> Iterator[Task]:
        sql = "SELECT * FROM tasks"
        args: tuple = ()
        if status is not None:
            sql += " WHERE status = ?"
            args = (status,)
        for row in self._conn.execute(sql + " ORDER BY created_at", args):
            yield self._task_from_row(row)

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> Task:
        return Task(
            task_id=row["task_id"],
            kind=row["kind"],
            payload=json.loads(row["payload"]),
            status=row["status"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
        )
