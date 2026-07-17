import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory_semantic_hook import semantic_context_for_memory_query, semantic_memory_status
from semantic_adapter import SemanticAdapter, SemanticAdapterConfig, create_default_adapter
from local_ontology import create_default_ontology
from agents.base import AgentContext, Task
from agents.gremlin_agent import GremlinAgent


def _write_memory_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    root.mkdir(exist_ok=True)
    (root / "gremlin_memory.json").write_text(json.dumps({
        "cycles": [{
            "time": "2026-06-27T00:00:00+00:00",
            "quip": "test",
            "weaknesses": [{"kind": "semantic_memory_gap", "severity": 0.6}],
            "proposals": [{"target": "semantic_memory_gap", "proposed_action": "use SemanticAdapter read-only"}],
            "theater_mode": True,
            "applied": False,
        }],
        "uncertainty_history": [{"time": "2026-06-27T00:00:00+00:00", "samples": 3, "ece": 0.1}],
    }), encoding="utf-8")
    (root / "ether_events.jsonl").write_text(
        json.dumps({"time": "2026-06-27T00:01:00+00:00", "event": "semantic_memory_hook", "payload": {"query": "SemanticAdapter"}}) + "\n",
        encoding="utf-8",
    )
    return root


def test_adapter_memory_context_is_read_only_and_prompt_safe():
    with tempfile.TemporaryDirectory() as td:
        memory_root = _write_memory_fixture(Path(td))
        adapter = SemanticAdapter(SemanticAdapterConfig(auto_load=False, auto_save=False, memory_root=str(memory_root)))
        result = adapter.memory_context_for_query("SemanticAdapter memory gap", as_prompt=True)
        assert result.ok, result.error
        assert result.data["read_only"] is True
        assert result.data["summary"]["cycles"] == 1
        assert result.data["summary"]["matched_cycles"] == 1
        assert "WORDLIB memory context" in result.data["prompt_context"]
        assert "semantic graph context" in result.data["prompt_context"] or "Local ontology context" in result.data["prompt_context"]


def test_memory_semantic_hook_uses_adapter_and_reports_sources():
    with tempfile.TemporaryDirectory() as td:
        memory_root = _write_memory_fixture(Path(td))
        result = semantic_context_for_memory_query("SemanticAdapter gremlin memory", as_prompt=True, memory_root=str(memory_root))
        assert result["ok"] is True
        assert result["read_only"] is True
        assert result["hook"] == "memory_semantic_hook.semantic_context_for_memory_query"
        assert result["data"]["sources"]["gremlin_memory"]["exists"] is True
        assert result["data"]["sources"]["ether_events"]["exists"] is True


def test_semantic_memory_status_is_boot_safe():
    with tempfile.TemporaryDirectory() as td:
        memory_root = _write_memory_fixture(Path(td))
        status = semantic_memory_status(memory_root=str(memory_root))
        assert status["ok"] is True
        assert status["read_only"] is True
        assert status["sources"]["gremlin_memory_exists"] is True


def test_local_ontology_includes_memory_semantic_hook():
    ontology = create_default_ontology()
    term = ontology.classify("memory_semantic_hook.py")
    assert term is not None
    assert term.name == "Memory Semantic Hook"
    assert term.kind == "component"


def test_gremlin_agent_semantic_history_action_is_optional_read_only():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        # Let the hook import the real source tree while the agent reads isolated memory.
        sys.path.insert(0, str(SRC))
        _write_memory_fixture(root)
        ctx = AgentContext(root=root)
        agent = GremlinAgent(ctx)
        result = agent.handle(Task(kind="gremlin", payload={"action": "semantic_history", "query": "SemanticAdapter memory"}))
        assert result.ok is True
        assert result.output["read_only"] is True


def test_deploy_check_memory_semantic_hook_gate():
    spec = importlib.util.spec_from_file_location("deploy_check_memory_hook", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.check_memory_semantic_hook()
    assert result["healthy"] is True
    assert result["read_only"] is True
