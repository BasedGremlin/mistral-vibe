import importlib.util
from pathlib import Path

import pytest

from semantic_adapter import (
    CausalTemporalProposal,
    NexusSnapshot,
    ReflectionResult,
    causal_temporal_status,
    create_default_adapter,
)

ROOT = Path(__file__).resolve().parents[1]


def _snapshot_with_events(query="deploy fix memory code"):
    return NexusSnapshot(
        contract="wordlib.nexus_snapshot.v1",
        query=query,
        generated_at="2026-06-27T10:00:00+00:00",
        read_only=True,
        summary={"agent_summary": "Synthetic NEXUS snapshot for causal tests.", "sections_available": ["memory", "code", "ontology", "rag"]},
        sections={
            "memory": {
                "name": "memory",
                "ok": True,
                "operation": "memory_context_for_query",
                "generated_at": "2026-06-27T10:00:01+00:00",
                "warnings": [],
                "error": None,
                "data": {
                    "read_only": True,
                    "summary": {"cycles": 1, "events_sampled": 3, "matched_events": 3},
                    "matches": {
                        "events": [
                            {"time": "2026-06-27T10:01:00+00:00", "event": "evolution_rejected", "payload": {"target": "src/semantic_adapter.py", "reason": "deploy gate failed"}},
                            {"time": "2026-06-27T10:03:00+00:00", "event": "evolution_deployed", "payload": {"target": "src/semantic_adapter.py", "snapshot": "backup.bak"}},
                        ],
                        "cycles": [
                            {"time": "2026-06-27T10:00:30+00:00", "quip": "reviewing deploy failure", "applied": False, "theater_mode": True}
                        ],
                    },
                },
            },
            "code": {
                "name": "code",
                "ok": True,
                "operation": "code_structure_context_for_query",
                "generated_at": "2026-06-27T10:00:02+00:00",
                "warnings": [],
                "error": None,
                "data": {
                    "read_only": True,
                    "summary": {"modules": 2, "classes": 1, "functions": 4, "imports": 2},
                    "matches": {"modules": [{"module": "src.semantic_adapter", "path": "src/semantic_adapter.py"}]},
                },
            },
            "ontology": {
                "name": "ontology",
                "ok": True,
                "operation": "ontology_context_for_query",
                "generated_at": "2026-06-27T10:00:03+00:00",
                "warnings": [],
                "error": None,
                "data": {"schema": "wordlib.local_ontology.v1", "matches": [{"name": "Semantic Adapter"}], "summary": {"healthy": True}},
            },
            "rag": {
                "name": "rag",
                "ok": True,
                "operation": "context_for_query",
                "generated_at": "2026-06-27T10:00:04+00:00",
                "warnings": ["Semantic graph is sparse"],
                "error": None,
                "data": {"summary": {"entities": 0, "relationships": 0, "evidence": 0}, "matches": []},
            },
        },
        health={"overall": True, "section_health": {"memory": True, "code": True, "ontology": True, "rag": True}},
        warnings=["semantic graph is sparse"],
        causal_links=[],
        temporal_links=[],
        retrieval_reasoning=["synthetic retrieval reasoning"],
        metadata={},
    )


def _reflection(query="deploy fix memory code"):
    return ReflectionResult(
        overall_relevance_score=0.72,
        section_scores={"memory": 0.8, "code": 0.75, "ontology": 0.7, "rag": 0.4},
        missing_or_weak_sections=["rag"],
        retrieval_weaknesses=["RAG/semantic graph section is sparse or has no matched entities/evidence"],
        suggested_improvements=["Ingest evidence-backed semantic facts before relying on RAG context."],
        critique_summary="Synthetic reflection marked RAG weak.",
        generated_at="2026-06-27T10:05:00+00:00",
        query=query,
    )


def test_causal_temporal_returns_exportable_proposal():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    proposal = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection())
    assert isinstance(proposal, CausalTemporalProposal)
    assert proposal.read_only is True
    assert proposal.contract == "wordlib.nexus_causal_temporal.v1"
    assert "wordlib.nexus_causal_temporal.v1" in proposal.export_json()


def test_causal_temporal_required_fields_and_candidate_schema():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    data = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection()).to_dict()
    assert {"candidates", "summary", "warnings", "future_integration_notes", "generated_at"}.issubset(data.keys())
    assert data["candidates"]
    for candidate in data["candidates"]:
        assert candidate["status"] == "candidate"
        assert candidate["type"] in {"temporal", "causal", "invalidation", "contradiction"}
        assert 0.0 <= candidate["confidence"] <= 1.0
        assert candidate["source_evidence"]
        assert "guard" in candidate["guard_required_before_fact"].lower()


def test_causal_temporal_detects_event_ordering():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    proposal = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection(), max_candidates=10)
    labels = [candidate["label"] for candidate in proposal.candidates]
    assert any("preceded" in label for label in labels), proposal.to_dict()
    assert any(candidate["type"] == "temporal" for candidate in proposal.candidates), proposal.to_dict()


def test_causal_temporal_detects_rejection_invalidation_candidate():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    proposal = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection(), max_candidates=10)
    assert any(candidate["type"] == "invalidation" for candidate in proposal.candidates), proposal.to_dict()


def test_causal_temporal_uses_reflection_weaknesses():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    proposal = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection(), max_candidates=10)
    assert any("weak rag section" in candidate["label"] for candidate in proposal.candidates), proposal.to_dict()


def test_causal_temporal_declares_intelligent_context_consumption():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    proposal = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection())
    assert proposal.metadata["consumes_intelligent_context_package"] is True
    assert proposal.metadata["intelligent_context_contract"] == "wordlib.nexus_intelligent_context.v1"


def test_causal_temporal_prompt_is_cloud_consumable():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    result = adapter.causal_temporal_for_prompt(_snapshot_with_events(), _reflection(), max_candidates=5)
    assert result.ok, result.to_dict()
    prompt = result.data["prompt_context"]
    assert "causal/temporal proposal layer" in prompt
    assert "Candidates" in prompt


def test_causal_temporal_status_is_boot_safe_and_read_only():
    status = causal_temporal_status("WORDLIB causal temporal deploy fix")
    assert status["ok"] is True, status
    assert status["read_only"] is True
    assert status["contract"] == "wordlib.nexus_causal_temporal.v1"
    assert status["candidate_count"] >= 1


def test_causal_temporal_does_not_mutate_graph_or_snapshot():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    snapshot = _snapshot_with_events()
    before_graph = adapter.graph.export_json()
    before_snapshot = snapshot.export_json()
    adapter.propose_causal_temporal_links(snapshot, _reflection())
    assert before_graph == adapter.graph.export_json()
    assert before_snapshot == snapshot.export_json()


def test_causal_temporal_rejects_wrong_snapshot_type():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    with pytest.raises(TypeError):
        adapter.propose_causal_temporal_links({"not": "snapshot"})


def test_deploy_check_causal_temporal_gate():
    spec = importlib.util.spec_from_file_location("deploy_check", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.check_causal_temporal_proposals()
    assert result["healthy"] is True, result
    assert result["read_only"] is True
    assert result["contract"] == "wordlib.nexus_causal_temporal.v1"
    assert result["candidate_count"] >= 1


def test_causal_candidates_include_stable_ids_and_path_traces():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    proposal = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection(), max_candidates=10)
    for candidate in proposal.candidates:
        assert candidate["id"].startswith("CTP_"), candidate
        assert candidate["affected_sections"], candidate
        assert candidate["evidence_path"], candidate
        assert candidate["path_explanation"], candidate
        assert "candidate" in candidate["path_explanation"].lower() or "=>" in candidate["path_explanation"]
        assert "SelfEditor" in candidate["guard_required_before_fact"]


def test_causal_proposal_contains_scaffolding_entry_for_cloud():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    data = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection(), max_candidates=10).to_dict()
    entry = data["scaffolding_entry"]
    assert entry["entry_id"].startswith("CTS_ENTRY_")
    assert entry["read_only"] is True
    assert entry["source_of_truth"] == "SemanticAdapter -> IntelligentContextPackage -> NexusSnapshot/Reflection"
    assert "SelfEditor whitelist" in entry["guard_contract"]["future_execution_requires"]
    assert entry["self_reorganization_readiness"]["ready_for_mutation"] is False


def test_causal_pathfinder_routes_align_with_candidates():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    proposal = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection(), max_candidates=10)
    data = proposal.to_dict()
    candidate_ids = {candidate["id"] for candidate in data["candidates"]}
    route_ids = {route["candidate_id"] for route in data["pathfinder_routes"]}
    assert route_ids == candidate_ids
    for route in data["pathfinder_routes"]:
        assert route["path"], route
        assert route["path_explanation"], route
        assert route["next_review_step"], route
        assert "SelfEditor" in route["guard_required_before_fact"]


def test_causal_self_reorganization_bridge_stays_proposal_only():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    data = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection(), max_candidates=10).to_dict()
    bridge = data["self_reorganization_bridge"]
    assert bridge["mode"] == "candidate_analysis_only"
    assert bridge["can_execute_reorganization"] is False
    assert "No mutation" in bridge["hard_stop"]
    assert isinstance(bridge["strong_candidate_ids"], list)


def test_deploy_check_causal_gate_validates_pathfinders():
    spec = importlib.util.spec_from_file_location("deploy_check", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.check_causal_temporal_proposals()
    assert result["healthy"] is True, result
    assert result["pathfinder_routes"] >= 1
    assert result["scaffolding_entry_id"].startswith("CTS_ENTRY_")


def test_causal_pathfinder_routes_include_merge_health_and_guard_chain():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    data = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection(), max_candidates=10).to_dict()
    for route in data["pathfinder_routes"]:
        assert route["route_id"].startswith("CTR_"), route
        assert 0.0 <= route["route_health_score"] <= 1.0, route
        assert route["route_grade"] in {"strong_review_candidate", "review_candidate", "weak_candidate"}, route
        assert "Merge-safe" in route["merge_note"], route
        assert "SelfEditor whitelist" in route["guard_chain"], route


def test_causal_proposal_exposes_reorganization_pathways():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    data = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection(), max_candidates=10).to_dict()
    pathways = data["reorganization_pathways"]
    assert pathways, data
    for pathway in pathways:
        assert pathway["pathway_id"].startswith("REORG_PATH_"), pathway
        assert pathway["allowed_now"] in {"review_only", "planning_only", "timeline_annotation_only"}, pathway
        assert pathway["forbidden_now"], pathway
        assert pathway["next_gate"], pathway


def test_causal_merge_guidance_is_cloud_ready_and_surgical():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    data = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection(), max_candidates=10).to_dict()
    merge = data["merge_guidance"]
    assert merge["merge_mode"] == "surgical_single_surface_patch"
    assert merge["no_split_required"] is True
    assert merge["new_dependencies"] == []
    assert "src/semantic_adapter.py" in merge["minimal_touch_files"]
    assert "Run pytest -q and python tests/run_tests.py" in merge["cloud_review_checklist"]
    assert 0.0 <= merge["readiness_score"] <= 1.0


def test_causal_scaffolding_entry_reports_merge_surface():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    entry = adapter.propose_causal_temporal_links(_snapshot_with_events(), _reflection(), max_candidates=10).to_dict()["scaffolding_entry"]
    assert entry["merge_surface"]["merge_friendly"] is True
    assert entry["merge_surface"]["new_dependencies"] if "new_dependencies" in entry["merge_surface"] else True
    assert entry["scaffolding_readiness_score"] >= 0.0
    assert entry["self_reorganization_readiness"]["ready_for_mutation"] is False


def test_causal_status_exposes_merge_and_pathway_counts():
    status = causal_temporal_status("Cloud merge causal pathfinder")
    assert status["ok"] is True, status
    assert "merge_safe" in status
    assert "pathway_count" in status
    assert status["pathfinder_routes"] >= 1
