"""End-to-end worker behavior and the two allowlisted handlers."""

import hashlib

import pytest

from ether_runtime import PayloadError, Worker
from ether_runtime.retry import DEFAULT_MAX_ATTEMPTS, JITTER_FRACTION, RETRY_DELAYS
from ether_runtime.tasks import HANDLERS

T0 = 2_000_000.0


def test_absorb_text_end_to_end(runtime, worker):
    task, _ = runtime.submit(
        "absorb_text", {"source": "handoff", "text": "durable runtimes ack after work"},
        now=T0,
    )
    outcomes = worker.run_once(now=T0)
    assert [o["outcome"] for o in outcomes] == ["completed"]
    done = runtime.store.get_task(task.task_id)
    assert done.status == "completed"
    assert done.result["created"] is True
    assert runtime.store.counts()["absorbed_records"] == 1


def test_absorb_requires_source(runtime):
    with pytest.raises(PayloadError):
        runtime.submit("absorb_text", {"source": "  ", "text": "anonymous"})


def test_absorb_is_content_deduplicated(runtime, worker):
    payload = {"source": "s", "text": "same content"}
    runtime.submit("absorb_text", payload, idempotency_key="first", now=T0)
    runtime.submit("absorb_text", payload, idempotency_key="second", now=T0)
    worker.run_until_drained(now=T0)
    assert runtime.store.counts()["absorbed_records"] == 1, "content hash dedups"


def test_verify_artifact_verified_and_mismatch(runtime, worker, tmp_path):
    good = runtime.artifact_root / "good.bin"
    good.write_bytes(b"payload-bytes")
    good_sha = hashlib.sha256(b"payload-bytes").hexdigest()
    task, _ = runtime.submit(
        "verify_artifact",
        {"files": {"good.bin": good_sha, "absent.bin": "0" * 64}},
        now=T0,
    )
    worker.run_until_drained(now=T0)
    done = runtime.store.get_task(task.task_id)
    assert done.status == "completed"
    assert done.result["ok"] is False
    assert done.result["files"]["good.bin"]["status"] == "verified"
    assert done.result["files"]["absent.bin"]["status"] == "missing"


def test_verify_artifact_rejects_traversal_at_submit(runtime):
    with pytest.raises(PayloadError):
        runtime.submit("verify_artifact", {"files": {"../escape": "0" * 64}})
    with pytest.raises(PayloadError):
        runtime.submit("verify_artifact", {"files": {"/etc/passwd": "0" * 64}})


def test_failure_walks_retry_ladder_then_dead_letters(runtime, monkeypatch):
    """A persistently failing handler retries with jittered delays, then dies."""
    calls = {"n": 0}

    def always_fails(store, payload, artifact_root):
        calls["n"] += 1
        raise RuntimeError("simulated handler crash")

    monkeypatch.setitem(HANDLERS, "absorb_text", always_fails)
    task, _ = runtime.submit("absorb_text", {"source": "s", "text": "t"}, now=T0)
    worker = Worker(runtime, name="w-retry")

    now = T0
    outcomes = []
    for _ in range(DEFAULT_MAX_ATTEMPTS):
        result = worker.run_once(now=now)
        assert len(result) == 1
        outcomes.append(result[0]["outcome"])
        # Jump past the maximum possible jittered delay to make the
        # retry entry deliverable on the next pass.
        now += max(RETRY_DELAYS) * (1 + JITTER_FRACTION) + 1

    assert outcomes[:-1] == ["retry_wait"] * (DEFAULT_MAX_ATTEMPTS - 1)
    assert outcomes[-1] == "dead_lettered"
    assert calls["n"] == DEFAULT_MAX_ATTEMPTS
    dead = runtime.store.get_task(task.task_id)
    assert dead.status == "dead_lettered"
    assert dead.attempts == DEFAULT_MAX_ATTEMPTS
    assert "simulated handler crash" in dead.error
    assert runtime.store.counts()["stream_depth"] == 0, "nothing left enqueued"


def test_retry_entry_not_deliverable_before_delay(runtime, monkeypatch):
    def always_fails(store, payload, artifact_root):
        raise RuntimeError("boom")

    monkeypatch.setitem(HANDLERS, "absorb_text", always_fails)
    runtime.submit("absorb_text", {"source": "s", "text": "t"}, now=T0)
    worker = Worker(runtime, name="w-delay")
    assert worker.run_once(now=T0)[0]["outcome"] == "retry_wait"
    # Minimum possible first delay is 1s * (1 - jitter); before that: nothing.
    assert worker.run_once(now=T0 + 0.5) == []


def test_mixed_batch_drains_cleanly(runtime, worker):
    for i in range(5):
        runtime.submit("absorb_text", {"source": "s", "text": f"text {i}"}, now=T0)
    executed = worker.run_until_drained(now=T0)
    assert executed == 5
    statuses = {t.status for t in runtime.store.iter_tasks()}
    assert statuses == {"completed"}
    counts = runtime.store.counts()
    assert counts["stream_depth"] == 0 and counts["pending_entries"] == 0
    assert counts["active_leases"] == 0
