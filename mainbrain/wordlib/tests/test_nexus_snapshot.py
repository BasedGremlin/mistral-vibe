import importlib.util
from pathlib import Path

from semantic_adapter import create_default_adapter, NexusSnapshot, nexus_snapshot_status


ROOT = Path(__file__).resolve().parents[1]


def test_nexus_snapshot_builds_exportable_read_only_object():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    snapshot = adapter.get_unified_nexus_snapshot("SemanticAdapter NEXUS code memory ontology")
    assert isinstance(snapshot, NexusSnapshot)
    data = snapshot.to_dict()
    assert data["contract"] == "wordlib.nexus_snapshot.v1"
    assert data["read_only"] is True
    assert data["generated_at"]
    assert "wordlib.nexus_snapshot.v1" in snapshot.export_json()


def test_nexus_snapshot_has_required_sections_and_timestamps():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    data = adapter.get_unified_nexus_snapshot("WORDLIB semantic adapter").to_dict()
    assert set(data["sections"].keys()) == {"memory", "code", "ontology", "rag"}
    for section in data["sections"].values():
        assert section["generated_at"]
        assert "ok" in section
        assert isinstance(section["warnings"], list)


def test_nexus_snapshot_has_health_warnings_and_future_placeholders():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    data = adapter.get_unified_nexus_snapshot("NEXUS causal temporal placeholders").to_dict()
    assert "overall" in data["health"]
    assert "sections" in data["health"]
    assert isinstance(data["warnings"], list)
    assert data["causal_links"] == []
    assert data["temporal_links"] == []
    assert data["retrieval_reasoning"]


def test_nexus_snapshot_summary_is_agent_ready():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    summary = adapter.get_unified_nexus_snapshot("SemanticAdapter code structure").to_dict()["summary"]
    assert summary["nexus_role"] == "unified_context_snapshot"
    assert "agent_summary" in summary
    assert "sections_available" in summary
    assert "memory" in summary and "code" in summary and "ontology" in summary and "rag" in summary


def test_nexus_snapshot_prompt_context_is_compact_and_prompt_ready():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    result = adapter.nexus_snapshot_for_prompt("SemanticAdapter NEXUS")
    assert result.ok, result.to_dict()
    prompt = result.data["prompt_context"]
    assert "WORDLIB NEXUS unified context snapshot" in prompt
    assert "Retrieval reasoning" in prompt
    assert "Causal placeholders" in prompt


def test_nexus_snapshot_status_is_boot_safe():
    status = nexus_snapshot_status("WORDLIB NEXUS boot")
    assert status["read_only"] is True
    assert status["contract"] == "wordlib.nexus_snapshot.v1"
    assert set(status["sections"]) == {"memory", "code", "ontology", "rag"}


def test_deploy_check_nexus_snapshot_gate():
    spec = importlib.util.spec_from_file_location("deploy_check", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.check_nexus_snapshot()
    assert result["healthy"] is True, result
    assert result["read_only"] is True
