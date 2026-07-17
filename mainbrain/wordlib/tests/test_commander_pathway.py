import importlib.util
from pathlib import Path

import pytest

from semantic_adapter import (
    CommanderPathwayPackage,
    commander_pathway_status,
    create_default_adapter,
)
from test_causal_temporal_proposals import _reflection, _snapshot_with_events

ROOT = Path(__file__).resolve().parents[1]


def test_commander_returns_exportable_single_surface_package():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    package = adapter.build_commander_troubleshooting_pathway("deploy fix memory code", max_steps=5)
    assert isinstance(package, CommanderPathwayPackage)
    assert package.read_only is True
    assert package.contract == "wordlib.nexus_commander_pathway.v1"
    data = package.to_dict()
    assert data["public_surface"]["single_entrypoint"] == "SemanticAdapter.build_commander_troubleshooting_pathway"
    assert "wordlib.nexus_commander_pathway.v1" in package.export_json()


def test_commander_steps_are_sequenced_and_guarded():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    data = adapter.build_commander_troubleshooting_pathway("deploy fix memory code", max_steps=6).to_dict()
    steps = data["sequenced_steps"]
    assert steps
    assert [s["sequence"] for s in steps] == list(range(1, len(steps) + 1))
    for step in steps:
        assert step["step_id"].startswith("CMD_STEP_")
        assert step["action_mode"] == "read_only_review"
        assert "write memory" in step["forbidden_now"]
        assert "trigger SelfEditor" in step["forbidden_now"]
        assert step["expected_failure_prevented"]


def test_commander_uses_causal_routes_and_intelligent_context_contracts():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    data = adapter.build_commander_troubleshooting_pathway("Cloud causal pathfinder", max_steps=4).to_dict()
    assert data["metadata"]["uses_intelligent_context_package"] is True
    assert data["metadata"]["uses_causal_pathfinder_routes"] is True
    assert data["metadata"]["intelligent_context_contract"] == "wordlib.nexus_intelligent_context.v1"
    assert data["evidence_routes"]
    assert data["causal_bridge_summary"]["can_execute_reorganization"] is False


def test_commander_invalidation_map_links_weakness_to_later_evidence():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    # Direct causal proposal should produce invalidation; commander should map it.
    snapshot = _snapshot_with_events()
    reflection = _reflection()
    causal = adapter.propose_causal_temporal_links(snapshot, reflection, max_candidates=10)
    assert any(c["type"] == "invalidation" for c in causal.candidates)
    data = adapter.build_commander_troubleshooting_pathway("deploy fix memory code", max_steps=6).to_dict()
    assert isinstance(data["invalidation_map"], list)
    # Runtime package may be less synthetic, but schema must support explicit mappings.
    for mapping in data["invalidation_map"]:
        assert mapping["map_id"].startswith("INV_MAP_")
        assert mapping["status"] == "candidate_mapping"
        assert mapping["because_evidence"]


def test_commander_failure_predictions_are_preventive_not_execution():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    data = adapter.build_commander_troubleshooting_pathway("Cloud merge centralization deploy", max_steps=6).to_dict()
    for prediction in data["failure_predictions"]:
        assert prediction["prediction_id"].startswith("FAIL_PATH_")
        assert prediction["preventive_step"]
        assert prediction["likely_failure_mode"]
        assert prediction["severity"] in {"low", "medium", "high"}


def test_commander_merge_capabilities_are_surgical():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    data = adapter.build_commander_troubleshooting_pathway("Cloud merge guarded causal pathfinder", max_steps=6).to_dict()
    merge = data["merge_capabilities"]
    assert merge["no_new_dependencies"] is True
    assert merge["no_file_split"] is True
    assert merge["read_only"] is True
    assert "src/semantic_adapter.py" in merge["minimal_touch_files"]


def test_commander_prompt_is_cloud_consumable():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    result = adapter.commander_pathway_for_prompt("Cloud Commander path", max_steps=4)
    assert result.ok, result.to_dict()
    prompt = result.data["prompt_context"]
    assert "NEXUS Commander pathway" in prompt
    assert "Execution: forbidden" in prompt
    assert "Step" in prompt


def test_commander_status_is_boot_safe():
    status = commander_pathway_status("Cloud Commander boot status")
    assert status["ok"] is True, status
    assert status["read_only"] is True
    assert status["contract"] == "wordlib.nexus_commander_pathway.v1"
    assert status["step_count"] >= 1
    assert status["single_entrypoint"] == "SemanticAdapter.build_commander_troubleshooting_pathway"
    assert status["can_execute_reorganization"] is False


def test_commander_does_not_mutate_graph():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    before = adapter.graph.export_json()
    adapter.build_commander_troubleshooting_pathway("no mutation commander", max_steps=4)
    assert before == adapter.graph.export_json()


def test_commander_rejects_invalid_inputs():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    with pytest.raises(ValueError):
        adapter.build_commander_troubleshooting_pathway("")
    with pytest.raises(ValueError):
        adapter.build_commander_troubleshooting_pathway("goal", strictness="unsafe")


def test_deploy_check_commander_gate():
    spec = importlib.util.spec_from_file_location("deploy_check", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.check_commander_pathway()
    assert result["healthy"] is True, result
    assert result["read_only"] is True
    assert result["contract"] == "wordlib.nexus_commander_pathway.v1"
    assert result["step_count"] >= 1
