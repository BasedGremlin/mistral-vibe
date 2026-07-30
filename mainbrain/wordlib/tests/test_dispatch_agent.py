"""
DispatchAgent: the durable worker plane bridge (merge plan Phase 3).
Proves the swarm can journal bounded task envelopes into ether-runtime,
drain them, read status -- and that everything degrades honestly when the
runtime package is absent.
"""
import sys
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from agents import ClawOrchestrator, Task
from agents.base import AgentContext
from agents.dispatch_agent import DispatchAgent
import agents.dispatch_agent as dispatch_module


def _ctx(tmp_path: Path) -> AgentContext:
    return AgentContext(root=tmp_path)


def _agent(tmp_path: Path) -> DispatchAgent:
    agent = DispatchAgent(_ctx(tmp_path))
    assert agent.available, agent.last_error
    return agent


# ── End-to-end through the agent surface ─────────────────────────────────────
def test_dispatch_absorb_end_to_end(tmp_path):
    agent = _agent(tmp_path)
    res = agent._run(Task("dispatch", {
        "task": {"kind": "absorb_text",
                 "payload": {"source": "swarm", "text": "phase 3 lives"}},
    }))
    assert res.ok and res.output["created"] is True
    task_id = res.output["task_id"]

    drained = agent._run(Task("dispatch_drain", {}))
    assert drained.ok and drained.output["executed"] == 1

    status = agent._run(Task("dispatch_status", {"task_id": task_id}))
    assert status.ok and status.output["status"] == "completed"
    assert status.output["result"]["created"] is True


def test_dispatch_verify_artifact_against_tree(tmp_path):
    (tmp_path / "docs").mkdir()
    target = tmp_path / "docs" / "spec.md"
    target.write_bytes(b"canonical spec")
    sha = hashlib.sha256(b"canonical spec").hexdigest()

    agent = _agent(tmp_path)
    res = agent._run(Task("dispatch", {
        "task": {"kind": "verify_artifact", "payload": {"files": {"docs/spec.md": sha}}},
    }))
    assert res.ok
    agent._run(Task("dispatch_drain", {}))
    status = agent._run(Task("dispatch_status", {"task_id": res.output["task_id"]}))
    assert status.output["result"]["ok"] is True
    assert status.output["result"]["files"]["docs/spec.md"]["status"] == "verified"


def test_dispatch_is_idempotent(tmp_path):
    agent = _agent(tmp_path)
    envelope = {"task": {"kind": "absorb_text",
                         "payload": {"source": "s", "text": "once"}}}
    first = agent._run(Task("dispatch", envelope))
    second = agent._run(Task("dispatch", envelope))
    assert first.output["created"] is True
    assert second.output["created"] is False
    assert first.output["task_id"] == second.output["task_id"]


# ── Boundary: only allowlisted envelopes pass ────────────────────────────────
def test_dispatch_rejects_unknown_kind(tmp_path):
    agent = _agent(tmp_path)
    res = agent._run(Task("dispatch", {
        "task": {"kind": "execute_shell", "payload": {"cmd": "rm -rf /"}},
    }))
    assert not res.ok and "rejected envelope" in res.error


def test_dispatch_rejects_malformed_envelope(tmp_path):
    agent = _agent(tmp_path)
    res = agent._run(Task("dispatch", {"task": "not a dict"}))
    assert not res.ok and "payload.task" in res.error


# ── Honest degradation without the runtime package ───────────────────────────
def test_degrades_when_runtime_missing(tmp_path, monkeypatch):
    def broken_import():
        raise ModuleNotFoundError("ether_runtime")
    monkeypatch.setattr(dispatch_module, "_import_runtime_module", broken_import)
    agent = DispatchAgent(_ctx(tmp_path))
    assert agent.available is False
    res = agent._run(Task("dispatch_status", {}))
    assert not res.ok and "unavailable" in res.error


# ── Orchestrator registration ────────────────────────────────────────────────
def test_orchestrator_registers_dispatch_agent(tmp_path):
    orch = ClawOrchestrator(tmp_path)
    status = orch.status()
    assert "dispatch" in status["agents"]
    assert status["agent_count"] == 13
    res = orch.route(Task("dispatch_status", {}))
    assert res.ok and "tasks_by_status" in res.output
