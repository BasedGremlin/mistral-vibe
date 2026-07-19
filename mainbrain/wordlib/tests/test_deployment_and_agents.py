"""
Integration tests: deployment state machine, scaling, stage engine, agents.
These exercise the systems working together, not just units.
"""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from deployment import DeploymentState, Stage, StageEngine
from deployment.scaling import detect_mode, DeploymentMode
from agents import get_orchestrator, Task

ROOT = Path(__file__).resolve().parents[1]


# ── Deployment state machine ─────────────────────────────────────────────────
def test_state_resume_skips_done():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "data").mkdir()
    state = DeploymentState(tmp)
    state.mark_done("stage1")
    assert state.is_done("stage1") is True
    assert state.is_done("stage2") is False
    import shutil
    shutil.rmtree(tmp)


def test_stage_engine_runs_in_order():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "data").mkdir()
    state = DeploymentState(tmp)
    order = []
    stages = [
        Stage("a", lambda p: order.append("a") or "ok"),
        Stage("b", lambda p: order.append("b") or "ok", depends_on=["a"]),
    ]
    engine = StageEngine(state, ui=None)
    ok = engine.run_all(stages)
    assert ok is True
    assert order == ["a", "b"]
    import shutil
    shutil.rmtree(tmp)


def test_stage_engine_resumes():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "data").mkdir()
    state = DeploymentState(tmp)
    calls = []
    stages = [Stage("x", lambda p: calls.append("x") or "ok")]
    StageEngine(state, ui=None).run_all(stages)
    # Second run should skip
    StageEngine(state, ui=None).run_all(stages)
    assert calls == ["x"]  # only ran once
    import shutil
    shutil.rmtree(tmp)


def test_stage_rollback_on_failure():
    from deployment import FatalError
    tmp = Path(tempfile.mkdtemp())
    (tmp / "data").mkdir()
    state = DeploymentState(tmp)
    rolled = {"back": False}

    def fail(p):
        raise FatalError("boom", "fix it")

    stages = [Stage("bad", fail, rollback=lambda: rolled.__setitem__("back", True))]
    ok = StageEngine(state, ui=None).run_all(stages)
    assert ok is False
    assert rolled["back"] is True
    import shutil
    shutil.rmtree(tmp)


# ── Scaling ──────────────────────────────────────────────────────────────────
def test_scaling_detects_a_mode():
    prof = detect_mode(ROOT)
    assert prof.mode in (DeploymentMode.USB, DeploymentMode.DESKTOP, DeploymentMode.SERVER)
    assert prof.rag_chunk_size > 0
    assert prof.max_parallel_agents >= 1


def test_scaling_override():
    os.environ["WORDLIB_MODE"] = "server"
    prof = detect_mode(ROOT)
    assert prof.mode == DeploymentMode.SERVER
    assert prof.max_model_params_b >= 14
    del os.environ["WORDLIB_MODE"]


# ── Agents ───────────────────────────────────────────────────────────────────
def test_orchestrator_all_agents_available():
    orch = get_orchestrator(ROOT)
    st = orch.status()
    assert st["agent_count"] >= 9
    assert st["available_count"] == st["agent_count"]


def test_guardian_vetoes_unsafe_code():
    orch = get_orchestrator(ROOT)
    r = orch.route(Task("guard", {"changes": {"src/x.py": "import os\nos.system('rm -rf /')"}}))
    assert r.ok is False


def test_math_agent_through_swarm():
    orch = get_orchestrator(ROOT)
    r = orch.route(Task("math", {"lhs": "(a+b)**2", "rhs": "a**2 + 2*a*b + b**2"}))
    assert r.ok is True


def test_absorption_agent_power_level():
    orch = get_orchestrator(ROOT)
    r = orch.route(Task("power", {}))
    assert r.ok is True
    assert 0 <= r.output["power_level_pct"] <= 100


def test_gremlin_cycle_propose_only():
    orch = get_orchestrator(ROOT)
    r = orch.route(Task("gremlin", {"action": "cycle"}))
    assert r.ok is True
    # Theater mode: never auto-applies
    assert r.output.get("applied") is False


def test_unknown_task_kind_handled():
    orch = get_orchestrator(ROOT)
    r = orch.route(Task("nonsense_kind", {}))
    assert r.ok is False
