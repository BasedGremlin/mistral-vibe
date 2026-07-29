"""RedisStoreAdapter -- backend parity with the SQLite reference store.

Every behavioural test here runs against BOTH backends via the ``store``
fixture. That is the point: the adapter's contract is "indistinguishable from
TaskStore", so asserting the same thing twice is the proof. A Redis-only test
would only show the code runs, not that it agrees with the reference.

The Redis parameter uses an in-memory double (``fake_redis.FakeRedis``), so the
logic is provable offline. Honest limit stated plainly: passing here proves the
adapter's state machine, NOT that it works against a live Redis server -- that
needs an integration run against a real instance.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ether_runtime import GROUP, TaskStore, Worker
from ether_runtime.redis_store import RedisStoreAdapter, RedisUnavailable
from ether_runtime.retry import RECLAIM_IDLE_SECONDS
from fake_redis import FakeRedis

T0 = 1_000_000.0


@pytest.fixture(params=["sqlite", "redis"])
def store(request, tmp_path):
    """The same suite, once per backend."""
    if request.param == "sqlite":
        s = TaskStore(tmp_path / "parity.db")
        yield s
        s.close()
    else:
        s = RedisStoreAdapter(client=FakeRedis())
        yield s
        s.close()


def _payload(n: int = 0) -> dict:
    return {"source": "parity", "text": f"item {n}"}


# ── journal + outbox ─────────────────────────────────────────────────────────
def test_submit_is_idempotent_and_journals_outbox(store):
    task, created = store.submit("absorb_text", _payload(), now=T0)
    assert created is True
    assert task.status == "queued"
    assert task.attempts == 0
    assert store.counts()["outbox_backlog"] == 1

    again, created_again = store.submit("absorb_text", _payload(), now=T0)
    assert created_again is False
    assert again.task_id == task.task_id
    assert store.counts()["outbox_backlog"] == 1, "no duplicate outbox row"


def test_publish_moves_outbox_to_stream(store):
    task, _ = store.submit("absorb_text", _payload(), now=T0)
    entry_id = store.publish_claimed(task.task_id, now=T0)

    assert isinstance(entry_id, int), "entry_id must stay int across backends"
    counts = store.counts()
    assert counts["outbox_backlog"] == 0
    assert counts["stream_depth"] == 1
    assert store.get_task(task.task_id).status == "published"


def test_claim_lease_blocks_a_second_publisher(store):
    store.submit("absorb_text", _payload(), now=T0)
    first = store.claim_outbox("p1", now=T0)
    second = store.claim_outbox("p2", now=T0)
    assert len(first) == 1
    assert second == [], "a claimed row must not be re-claimed"

    recovered = store.claim_outbox("p2", now=T0 + 31.0)
    assert len(recovered) == 1, "an expired claim must be recoverable"


# ── consumer-group delivery ──────────────────────────────────────────────────
def test_read_group_then_autoclaim_recovers_abandoned_entry(store):
    task, _ = store.submit("absorb_text", _payload(), now=T0)
    store.publish_claimed(task.task_id, now=T0)

    delivered = store.read_group(GROUP, "crashed", now=T0)
    assert len(delivered) == 1
    assert delivered[0].delivery_count == 1
    assert delivered[0].task_id == task.task_id

    assert store.read_group(GROUP, "other", now=T0) == [], "pending entry is not redelivered"
    assert store.autoclaim(GROUP, "w2", RECLAIM_IDLE_SECONDS, now=T0 + 10) == []

    reclaimed = store.autoclaim(GROUP, "w2", RECLAIM_IDLE_SECONDS, now=T0 + RECLAIM_IDLE_SECONDS + 1)
    assert len(reclaimed) == 1
    assert reclaimed[0].delivery_count == 2


def test_ack_removes_entry_from_stream_and_pending(store):
    task, _ = store.submit("absorb_text", _payload(), now=T0)
    store.publish_claimed(task.task_id, now=T0)
    entry = store.read_group(GROUP, "w1", now=T0)[0]

    store.ack(entry.entry_id)
    counts = store.counts()
    assert counts["stream_depth"] == 0
    assert counts["pending_entries"] == 0


def test_delayed_entry_is_not_deliverable_before_not_before(store):
    task, _ = store.submit("absorb_text", _payload(), now=T0)
    store.append_stream_entry(task.task_id, not_before=T0 + 50, now=T0)

    assert store.read_group(GROUP, "w1", now=T0 + 10) == []
    assert len(store.read_group(GROUP, "w1", now=T0 + 51)) == 1


# ── execution leases ─────────────────────────────────────────────────────────
def test_execution_lease_is_exclusive_until_expiry(store):
    task, _ = store.submit("absorb_text", _payload(), now=T0)
    assert store.acquire_lease(task.task_id, "w1", 35.0, now=T0) is True
    assert store.acquire_lease(task.task_id, "w2", 35.0, now=T0) is False
    assert store.acquire_lease(task.task_id, "w1", 35.0, now=T0) is True, "same worker may re-take"
    assert store.acquire_lease(task.task_id, "w2", 35.0, now=T0 + 36.0) is True, "expired lease frees"


def test_release_lease_only_by_holder(store):
    task, _ = store.submit("absorb_text", _payload(), now=T0)
    store.acquire_lease(task.task_id, "w1", 35.0, now=T0)

    store.release_lease(task.task_id, "someone-else")
    assert store.acquire_lease(task.task_id, "w2", 35.0, now=T0) is False, "non-holder cannot release"

    store.release_lease(task.task_id, "w1")
    assert store.counts()["active_leases"] == 0


# ── state transitions ────────────────────────────────────────────────────────
def test_state_transitions_and_attempt_counting(store):
    task, _ = store.submit("absorb_text", _payload(), now=T0)

    assert store.mark_running(task.task_id, now=T0) == 1
    assert store.mark_running(task.task_id, now=T0) == 2
    assert store.get_task(task.task_id).status == "running"

    store.mark_retry_wait(task.task_id, "boom", 5.0, now=T0)
    retried = store.get_task(task.task_id)
    assert retried.status == "retry_wait"
    assert retried.error == "boom"
    assert store.counts()["stream_depth"] == 1, "retry re-enqueues"

    store.mark_completed(task.task_id, {"ok": True}, now=T0)
    done = store.get_task(task.task_id)
    assert done.status == "completed"
    assert done.result == {"ok": True}
    assert done.error is None, "completing clears the error"


def test_dead_letter_records_reason(store):
    task, _ = store.submit("absorb_text", _payload(), now=T0)
    store.mark_dead_lettered(task.task_id, "gave up", now=T0)
    dead = store.get_task(task.task_id)
    assert dead.status == "dead_lettered"
    assert dead.error == "gave up"


def test_unknown_task_raises_keyerror(store):
    with pytest.raises(KeyError):
        store.get_task("does-not-exist")


# ── absorption store ─────────────────────────────────────────────────────────
def test_absorb_is_content_deduplicated(store):
    h1, created1 = store.absorb("src", "same text", now=T0)
    h2, created2 = store.absorb("src", "same text", now=T0)
    h3, created3 = store.absorb("src", "different", now=T0)

    assert created1 is True and created2 is False and created3 is True
    assert h1 == h2 and h1 != h3
    assert store.counts()["absorbed_records"] == 2


# ── introspection contract ───────────────────────────────────────────────────
def test_counts_shape_is_the_documented_six_keys(store):
    store.submit("absorb_text", _payload(), now=T0)
    counts = store.counts()
    assert set(counts) == {
        "tasks_by_status", "outbox_backlog", "stream_depth",
        "pending_entries", "active_leases", "absorbed_records",
    }
    assert counts["tasks_by_status"] == {"queued": 1}


def test_iter_tasks_filters_by_status(store):
    a, _ = store.submit("absorb_text", _payload(1), now=T0)
    b, _ = store.submit("absorb_text", _payload(2), now=T0 + 1)
    store.mark_completed(b.task_id, {"done": True}, now=T0 + 2)

    assert {t.task_id for t in store.iter_tasks()} == {a.task_id, b.task_id}
    assert [t.task_id for t in store.iter_tasks(status="completed")] == [b.task_id]


# ── full worker round trip through the adapter ───────────────────────────────
def test_worker_drives_a_task_to_completion(store, tmp_path):
    """The runtime must not care which backend it is talking to."""
    class _Runtime:
        def __init__(self, s, root):
            self.store = s
            self.artifact_root = root

        def publish_pending(self, publisher=None, now=None):
            for task_id in self.store.claim_outbox(publisher or "p", now=now):
                self.store.publish_claimed(task_id, now=now)

    runtime = _Runtime(store, tmp_path)
    task, _ = store.submit("absorb_text", {"source": "w", "text": "run me"}, now=T0)

    outcomes = Worker(runtime, name="w1").run_once(now=T0)
    assert [o["outcome"] for o in outcomes] == ["completed"]
    assert store.get_task(task.task_id).status == "completed"
    assert store.counts()["absorbed_records"] == 1


# ── optional-dependency behaviour ────────────────────────────────────────────
def test_missing_redis_package_raises_a_clear_error(monkeypatch):
    """Without redis installed the adapter must explain itself, not ImportError."""
    import builtins

    real_import = builtins.__import__

    def _no_redis(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("No module named 'redis'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_redis)
    with pytest.raises(RedisUnavailable) as excinfo:
        RedisStoreAdapter(url="redis://localhost:6379/0")
    assert "pip install redis" in str(excinfo.value)


def test_injected_client_never_imports_redis(monkeypatch):
    """A supplied client keeps the SQLite default path stdlib-only."""
    import builtins

    real_import = builtins.__import__

    def _explode(name, *args, **kwargs):
        if name == "redis":
            raise AssertionError("redis must not be imported when a client is supplied")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _explode)
    adapter = RedisStoreAdapter(client=FakeRedis())
    assert adapter.counts()["stream_depth"] == 0
