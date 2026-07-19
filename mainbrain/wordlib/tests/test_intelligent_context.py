import importlib.util
from pathlib import Path

import pytest

from semantic_adapter import (
    IntelligentContextPackage,
    create_default_adapter,
    intelligent_context_status,
)

ROOT = Path(__file__).resolve().parents[1]


def _package(goal="Cloud integration SemanticAdapter NEXUS code memory ontology RAG"):
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    return adapter, adapter.build_intelligent_context(goal, max_tokens=6000, strictness="production")


def test_build_intelligent_context_returns_exportable_package():
    adapter, package = _package()
    assert isinstance(package, IntelligentContextPackage)
    data = package.to_dict()
    assert data["contract"] == "wordlib.nexus_intelligent_context.v1"
    assert data["read_only"] is True
    assert "wordlib.nexus_intelligent_context.v1" in package.export_json()


def test_intelligent_context_contains_required_top_level_fields():
    _, package = _package()
    data = package.to_dict()
    required = {
        "goal", "curated_context", "selection_reasoning", "context_health", "quality_audit",
        "overall_quality_score", "token_estimate", "warnings", "proposed_mutations", "generated_at",
    }
    assert required.issubset(data.keys())
    assert isinstance(data["overall_quality_score"], float)
    assert 0.0 <= data["overall_quality_score"] <= 1.0
    assert isinstance(data["token_estimate"], int) and data["token_estimate"] > 0


def test_intelligent_context_curates_all_required_sections():
    _, package = _package()
    context = package.curated_context
    assert set(context["sections"].keys()) == {"memory", "code", "ontology", "rag"}
    assert set(context["ranked_sections"]) == {"memory", "code", "ontology", "rag"}
    for section in context["sections"].values():
        assert "selection_priority" in section
        assert 0.0 <= section["selection_priority"] <= 1.0
        assert section["selected_reason"]


def test_intelligent_context_reports_v30_centralization_health():
    _, package = _package()
    status = package.context_health["centralization_status"]
    assert status["single_source_of_truth"] == "core.paths"
    assert status["migration_report_available"] is True
    assert "pending_count" in status
    assert "overall_health" in status


def test_intelligent_context_quality_audit_uses_honest_surface_heuristics():
    _, package = _package()
    audit = package.quality_audit
    assert "score" in audit
    assert "passed" in audit
    assert "breakdown" in audit
    assert "note" in audit
    assert "not" in audit["note"].lower() or "heuristic" in audit["note"].lower()


def test_intelligent_context_prompt_is_cloud_consumable():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    result = adapter.intelligent_context_for_prompt("Cloud integration SemanticAdapter NEXUS")
    assert result.ok, result.to_dict()
    prompt = result.data["prompt_context"]
    assert "NEXUS intelligent context package" in prompt
    assert "Selection reasoning" in prompt
    assert "Proposed mutations" in prompt


def test_intelligent_context_status_is_boot_safe_and_read_only():
    status = intelligent_context_status("WORDLIB NEXUS Cloud bridge")
    assert status["ok"] is True, status
    assert status["read_only"] is True
    assert status["contract"] == "wordlib.nexus_intelligent_context.v1"
    assert 0.0 <= status["overall_quality_score"] <= 1.0
    assert status["ranked_sections"]


def test_intelligent_context_does_not_mutate_graph_export():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    before = adapter.graph.export_json()
    adapter.build_intelligent_context("SemanticAdapter NEXUS Cloud bridge")
    after = adapter.graph.export_json()
    assert before == after


def test_intelligent_context_rejects_invalid_strictness():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    with pytest.raises(ValueError):
        adapter.build_intelligent_context("Cloud bridge", strictness="reckless")


def test_deploy_check_intelligent_context_gate():
    spec = importlib.util.spec_from_file_location("deploy_check", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.check_intelligent_context()
    assert result["healthy"] is True, result
    assert result["read_only"] is True
    assert result["contract"] == "wordlib.nexus_intelligent_context.v1"
