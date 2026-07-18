"""Durability core: outbox atomicity, at-least-once window, leases, reclaim."""

import sqlite3

import pytest

from ether_runtime import GROUP, PayloadError, Worker, stable_task_id
from ether_runtime.retry import RECLAIM_IDLE_SECONDS

T0 = 1_000_000.0


def _absorb_payload(n=0):
    return {"source": "unit-test", "text": f"absorb me {n}"}


def test_submit_is_one_transaction_and_idempotent(runtime):
    task, created = runtime.submit("absorb_text", _absorb_payload(), now=T0)
    assert created and task.status == "queued"
    counts = runtime.store.counts()
    assert counts["outbox_backlog"] == 1

    again, created_again = runtime.submit("absorb_text", _absorb_payload(), now=T0)
    assert not created_again and again.task_id == task.task_id
    assert runtime.store.counts()["outbox_backlog"] == 1, "no duplicate outbox row"


def test_unknown_kind_rejected_at_submit(runtime):
    with pytest.raises(PayloadError):
        runtime.submit("execute_verified", {"cmd": "rm -rf /"})


def test_stable_task_id_changes_with_content():
    base = stable_task_id("absorb_text", {"a": 1}, None)
    assert stable_task_id("absorb_text", {"a": 2}, None) != base
    assert stable_task_id("verify_artifact", {"a": 1}, None) != base
    assert stable_task_id("absorb_text", {"a": 1}, "key") != base


def test_publish_moves_outbox_to_stream(runtime):
    runtime.submit("absorb_text", _absorb_payload(), now=T0)
    published = runtime.publish_pending(publisher="p1", now=T0)
    assert published == 1
    counts = runtime.store.counts()
    assert counts["outbox_backlog"] == 0
    assert counts["stream_depth"] == 1


def test_publisher_claim_lease_blocks_second_publisher(runtime):
    runtime.submit("absorb_text", _absorb_payload(), now=T0)
    first = runtime.store.claim_outbox("p1", now=T0)
    second = runtime.store.claim_outbox("p2", now=T0)
    assert len(first) == 1 and second == [], "claimed row must not be re-claimed"
    # After the claim lease expires, another publisher may recover the row.
    third = runtime.store.claim_outbox("p2", now=T0 + 31.0)
    assert len(third) == 1


def test_at_least_once_window_duplicate_is_skipped(runtime, worker):
    """Crash between stream append and outbox delete -> duplicate entry.

    The duplicate must be detected via terminal state and acked, not re-run.
    """
    task, _ = runtime.submit("absorb_text", _absorb_payload(), now=T0)
    # Simulate the crash window: entry hits the stream, outbox row survives.
    runtime.store.append_stream_entry(task.task_id, now=T0)
    outcomes = worker.run_once(now=T0)  # also republishes the surviving outbox row
    executed = [o for o in outcomes if o["outcome"] == "completed"]
    skipped = [o for o in outcomes if o["outcome"] == "duplicate_skipped"]
    assert len(executed) == 1, "task must execute exactly once"
    assert len(skipped) == 1, "duplicate delivery must be skipped"
    assert runtime.store.get_task(task.task_id).status == "completed"
    assert runtime.store.counts()["stream_depth"] == 0, "both entries acked"


def test_execution_lease_blocks_second_consumer(runtime):
    task, _ = runtime.submit("absorb_text", _absorb_payload(), now=T0)
    runtime.publish_pending(publisher="p", now=T0)
    assert runtime.store.acquire_lease(task.task_id, "w1", 35.0, now=T0)
    assert not runtime.store.acquire_lease(task.task_id, "w2", 35.0, now=T0)
    # Lease expiry frees the task for another worker (crash recovery).
    assert runtime.store.acquire_lease(task.task_id, "w2", 35.0, now=T0 + 36.0)


def test_autoclaim_recovers_abandoned_entry(runtime):
    task, _ = runtime.submit("absorb_text", _absorb_payload(), now=T0)
    runtime.publish_pending(publisher="p", now=T0)
    delivered = runtime.store.read_group(GROUP, "crashed-consumer", now=T0)
    assert len(delivered) == 1 and delivered[0].delivery_count == 1

    # Before the idle threshold nothing is transferable.
    assert runtime.store.autoclaim(GROUP, "w2", RECLAIM_IDLE_SECONDS, now=T0 + 10) == []

    reclaimed = runtime.store.autoclaim(
        GROUP, "w2", RECLAIM_IDLE_SECONDS, now=T0 + RECLAIM_IDLE_SECONDS + 1
    )
    assert len(reclaimed) == 1
    assert reclaimed[0].delivery_count == 2
    assert reclaimed[0].task_id == task.task_id


def test_state_survives_reopen(tmp_path):
    """WAL journal is the durability boundary: reopen sees identical state."""
    from ether_runtime import TaskRuntime

    db = tmp_path / "durable.db"
    rt = TaskRuntime(db)
    task, _ = rt.submit("absorb_text", _absorb_payload(), now=T0)
    rt.close()

    rt2 = TaskRuntime(db)
    try:
        assert rt2.store.get_task(task.task_id).status == "queued"
        assert rt2.store.counts()["outbox_backlog"] == 1
        mode = sqlite3.connect(str(db)).execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        rt2.close()
