import importlib.util
from pathlib import Path

import pytest

from semantic_adapter import create_default_adapter, NexusSnapshot, ReflectionResult, reflection_status

ROOT = Path(__file__).resolve().parents[1]


def _snapshot(query="SemanticAdapter NEXUS reflection memory code ontology RAG"):
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    return adapter, adapter.get_unified_nexus_snapshot(query)


def test_reflect_on_snapshot_returns_exportable_reflection_result():
    adapter, snapshot = _snapshot()
    result = adapter.reflect_on_snapshot(snapshot, snapshot.query)
    assert isinstance(result, ReflectionResult)
    data = result.to_dict()
    assert data["contract"] == "wordlib.nexus_reflection.v1"
    assert data["read_only"] is True
    assert "wordlib.nexus_reflection.v1" in result.export_json()


def test_reflection_result_contains_required_fields_and_types():
    adapter, snapshot = _snapshot()
    data = adapter.reflect_on_snapshot(snapshot).to_dict()
    assert isinstance(data["overall_relevance_score"], float)
    assert 0.0 <= data["overall_relevance_score"] <= 1.0
    assert isinstance(data["section_scores"], dict)
    assert isinstance(data["missing_or_weak_sections"], list)
    assert isinstance(data["retrieval_weaknesses"], list)
    assert isinstance(data["suggested_improvements"], list)
    assert isinstance(data["critique_summary"], str) and data["critique_summary"]
    assert data["generated_at"]


def test_reflection_scores_all_required_sections():
    adapter, snapshot = _snapshot()
    scores = adapter.reflect_on_snapshot(snapshot).section_scores
    assert set(scores) == {"memory", "code", "ontology", "rag"}
    assert all(0.0 <= score <= 1.0 for score in scores.values())


def test_reflection_detects_missing_or_unhealthy_section():
    broken = NexusSnapshot(
        contract="wordlib.nexus_snapshot.v1",
        query="memory code ontology rag",
        generated_at="2026-06-27T00:00:00+00:00",
        read_only=True,
        summary={"nexus_role": "unified_context_snapshot", "agent_summary": "broken test"},
        sections={"code": {"name": "code", "ok": False, "generated_at": "2026-06-27T00:00:00+00:00", "warnings": [], "error": "forced", "data": {}}},
        health={"overall": False, "sections": {}},
        causal_links=[],
        temporal_links=[],
        retrieval_reasoning=[],
    )
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    reflection = adapter.reflect_on_snapshot(broken)
    assert "memory" in reflection.missing_or_weak_sections
    assert "code" in reflection.missing_or_weak_sections
    assert any("missing" in weakness or "unhealthy" in weakness for weakness in reflection.retrieval_weaknesses)


def test_reflection_suggests_concrete_improvements_for_sparse_snapshot():
    adapter, snapshot = _snapshot("very unlikely query zzznonexistentcontext")
    reflection = adapter.reflect_on_snapshot(snapshot, "very unlikely query zzznonexistentcontext")
    assert reflection.suggested_improvements
    assert all(isinstance(item, str) and item for item in reflection.suggested_improvements)


def test_reflection_prompt_context_is_agent_readable():
    adapter, snapshot = _snapshot()
    result = adapter.reflection_for_prompt(snapshot, snapshot.query)
    assert result.ok, result.to_dict()
    prompt = result.data["prompt_context"]
    assert "WORDLIB NEXUS reflection/self-critique" in prompt
    assert "Overall relevance score" in prompt
    assert "Section scores" in prompt


def test_reflection_status_is_boot_safe_and_read_only():
    status = reflection_status("WORDLIB NEXUS reflection boot")
    assert status["ok"] is True, status
    assert status["read_only"] is True
    assert status["contract"] == "wordlib.nexus_reflection.v1"
    assert 0.0 <= status["overall_relevance_score"] <= 1.0


def test_reflection_does_not_mutate_snapshot_export():
    adapter, snapshot = _snapshot()
    before = snapshot.export_json()
    adapter.reflect_on_snapshot(snapshot, snapshot.query)
    after = snapshot.export_json()
    assert before == after


def test_reflect_on_snapshot_rejects_wrong_input_type():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    with pytest.raises(TypeError):
        adapter.reflect_on_snapshot({"not": "a snapshot"})


def test_deploy_check_reflection_gate():
    spec = importlib.util.spec_from_file_location("deploy_check", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.check_nexus_reflection()
    assert result["healthy"] is True, result
    assert result["read_only"] is True
