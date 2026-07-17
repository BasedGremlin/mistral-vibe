"""Tests for WORDLIB semantic_core foundation gate."""
import importlib.util
import json
import tempfile
from pathlib import Path

from semantic_core import EntityExtractor, SemanticKnowledgeGraph, SemanticRAGBridge, SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _graph():
    g = SemanticKnowledgeGraph(storage_path=Path(tempfile.mkdtemp()) / "semantic_graph.json")
    ev = g.add_evidence("test", "WORDLIB contains semantic_core.py evidence.", source_path="tests/test_semantic_core.py")
    return g, ev


def test_evidence_creation():
    g, ev = _graph()
    assert ev.id in g.evidence
    assert ev.text_excerpt


def test_entity_creation_requires_evidence():
    g, ev = _graph()
    entity = g.add_entity("WORDLIB", "project", evidence_ids=[ev.id], confidence=0.9)
    assert entity.id in g.entities
    try:
        g.add_entity("No Evidence", "concept")
        assert False, "entity without provenance should fail"
    except ValueError:
        pass


def test_relationship_creation():
    g, ev = _graph()
    a = g.add_entity("WORDLIB", "project", evidence_ids=[ev.id])
    b = g.add_entity("semantic_core.py", "file", evidence_ids=[ev.id])
    rel = g.add_relationship(a.id, b.id, "contains module", evidence_ids=[ev.id])
    assert rel.id in g.relationships
    assert rel.evidence_ids == [ev.id]


def test_event_creation():
    g, ev = _graph()
    a = g.add_entity("WORDLIB", "project", evidence_ids=[ev.id])
    b = g.add_entity("Semantic Core", "concept", evidence_ids=[ev.id])
    event = g.add_event("Semantic integration", "implementation", [a.id, b.id], evidence_ids=[ev.id])
    assert event.id in g.events
    assert set(event.involved_entity_ids) == {a.id, b.id}


def test_json_export_import_roundtrip():
    g, ev = _graph()
    g.add_entity("WORDLIB", "project", evidence_ids=[ev.id])
    data = g.export_json()
    assert json.loads(data)["schema"] == SCHEMA_VERSION
    clone = SemanticKnowledgeGraph()
    clone.import_json(data)
    assert clone.summary()["entities"] == 1
    assert clone.summary()["evidence"] == 1


def test_save_load_roundtrip():
    g, ev = _graph()
    g.add_entity("WORDLIB", "project", evidence_ids=[ev.id])
    path = g.save()
    clone = SemanticKnowledgeGraph(storage_path=path).load()
    assert clone.find_entity("WORDLIB") is not None


def test_entity_extraction_detects_files_and_projects():
    extractor = EntityExtractor(entity_hints={"MotherEther": "project"})
    items = extractor.extract("WORDLIB MotherEther uses src/semantic_core.py and deploy_check.py for Semantic Core.")
    names = {item["name"] for item in items}
    assert "WORDLIB" in names
    assert "src/semantic_core.py" in names
    assert "deploy_check.py" in names
    assert "MotherEther" in names


def test_document_ingestion():
    g = SemanticKnowledgeGraph(storage_path=Path(tempfile.mkdtemp()) / "semantic_graph.json")
    bridge = SemanticRAGBridge(g, entity_hints={"WORDLIB": "project"})
    result = bridge.ingest_document_text("WORDLIB validates semantic_core.py through deploy_check.py.", source_path="doc.md")
    assert result["evidence_id"] in g.evidence
    assert result["entity_count"] >= 2


def test_rag_bridge_context_generation():
    g = SemanticKnowledgeGraph(storage_path=Path(tempfile.mkdtemp()) / "semantic_graph.json")
    bridge = SemanticRAGBridge(g, entity_hints={"WORDLIB": "project"})
    bridge.ingest_document_text("WORDLIB uses Semantic Core for provenance-aware memory.", source_path="doc.md")
    context = bridge.semantic_context_for_query("WORDLIB provenance")
    assert context["matches"]
    prompt = bridge.graph_summary_for_prompt("WORDLIB provenance")
    assert "WORDLIB semantic graph context" in prompt


def test_semantic_pathfinding_and_shortest_path():
    g, ev = _graph()
    a = g.add_entity("WORDLIB", "project", evidence_ids=[ev.id], confidence=0.9)
    b = g.add_entity("semantic_core.py", "file", evidence_ids=[ev.id], confidence=0.9)
    c = g.add_entity("Entity", "schema", evidence_ids=[ev.id], confidence=0.8)
    g.add_relationship(a.id, b.id, "contains module", evidence_ids=[ev.id], confidence=0.9)
    g.add_relationship(b.id, c.id, "stores", evidence_ids=[ev.id], confidence=0.8)
    paths = g.find_paths_between_entities("WORDLIB", "Entity", max_depth=3)
    shortest = g.shortest_semantic_path("WORDLIB", "Entity")
    assert paths
    assert shortest
    assert "WORDLIB" in g.explain_path(shortest)
    assert "supported by evidence" in g.explain_path(shortest)


def test_evidence_path_tracing():
    g, ev = _graph()
    a = g.add_entity("WORDLIB", "project", evidence_ids=[ev.id])
    trace = g.trace_evidence_path(a.id)
    assert trace
    assert trace[0]["evidence"]["id"] == ev.id


def test_deploy_check_semantic_validation():
    spec = importlib.util.spec_from_file_location("deploy_check_semantic", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.check_semantic_core()
    assert result["healthy"] is True
    assert "WORDLIB" in result["path"]



def test_canonical_entity_merge_and_aliases():
    g, ev = _graph()
    a = g.add_entity("semantic_core.py", "file", evidence_ids=[ev.id], aliases=["semantic core module"])
    b = g.add_entity("src/semantic_core.py", "file", evidence_ids=[ev.id])
    assert a.id == b.id
    assert g.find_entity("src/semantic_core.py").id == a.id
    assert any("semantic_core.py" in alias for alias in g.find_entity("semantic_core.py").aliases)


def test_relationship_idempotency_and_self_relation_guard():
    g, ev = _graph()
    a = g.add_entity("WORDLIB", "project", evidence_ids=[ev.id])
    b = g.add_entity("Semantic Core", "concept", evidence_ids=[ev.id])
    r1 = g.add_relationship(a.id, b.id, "contains", evidence_ids=[ev.id], confidence=0.7)
    r2 = g.add_relationship(a.id, b.id, "contains", evidence_ids=[ev.id], confidence=0.9)
    assert r1.id == r2.id
    assert g.relationships[r1.id].confidence == 0.9
    try:
        g.add_relationship(a.id, a.id, "self", evidence_ids=[ev.id])
        assert False, "self relationship should require explicit metadata override"
    except ValueError:
        pass


def test_event_idempotency():
    g, ev = _graph()
    a = g.add_entity("WORDLIB", "project", evidence_ids=[ev.id])
    e1 = g.add_event("Semantic validation", "deploy", [a.id], evidence_ids=[ev.id], confidence=0.6)
    e2 = g.add_event("Semantic validation", "deploy", [a.id], evidence_ids=[ev.id], confidence=0.8)
    assert e1.id == e2.id
    assert g.events[e1.id].confidence == 0.8


def test_invalid_evidence_rejected():
    g = SemanticKnowledgeGraph(storage_path=Path(tempfile.mkdtemp()) / "semantic_graph.json")
    for kwargs in [
        {"source_type": "test", "text_excerpt": ""},
        {"source_type": "test", "text_excerpt": "x", "confidence": 2.0},
        {"source_type": "test", "text_excerpt": "x", "metadata": {"bad": object()}},
    ]:
        try:
            g.add_evidence(**kwargs)
            assert False, f"invalid evidence accepted: {kwargs}"
        except ValueError:
            pass


def test_import_rejects_missing_evidence_reference():
    g, ev = _graph()
    ent = g.add_entity("WORDLIB", "project", evidence_ids=[ev.id])
    payload = json.loads(g.export_json())
    payload["entities"][0]["evidence_ids"] = ["EVID_MISSING"]
    try:
        SemanticKnowledgeGraph().import_json(payload)
        assert False, "missing evidence reference should fail import"
    except ValueError:
        pass


def test_audit_integrity_reports_broken_graph():
    g, ev = _graph()
    ent = g.add_entity("WORDLIB", "project", evidence_ids=[ev.id])
    ent.evidence_ids = ["EVID_MISSING"]
    audit = g.audit_integrity()
    assert audit["healthy"] is False
    assert audit["error_count"] >= 1


def test_compact_merges_duplicates_without_losing_evidence():
    g, ev = _graph()
    ev2 = g.add_evidence("test", "Second evidence for semantic_core.py", source_path="tests/test_semantic_core.py")
    a = g.add_entity("semantic_core.py", "file", evidence_ids=[ev.id])
    # Force a legacy duplicate that import_json could have created before canonical merge existed.
    b = g.add_entity("src/semantic_core.py", "file", evidence_ids=[ev2.id], entity_id="ENT_LEGACY_DUPLICATE")
    assert len(g.entities) >= 1
    result = g.compact()
    ent = g.find_entity("semantic_core.py")
    assert ev.id in ent.evidence_ids and ev2.id in ent.evidence_ids
    assert result["merged_entities"] >= 0
    assert g.audit_integrity()["healthy"] is True


def test_path_ranking_prefers_explicit_relationship_over_shared_evidence():
    g, ev = _graph()
    a = g.add_entity("WORDLIB", "project", evidence_ids=[ev.id], confidence=0.9)
    b = g.add_entity("semantic_core.py", "file", evidence_ids=[ev.id], confidence=0.9)
    g.add_relationship(a.id, b.id, "contains module", evidence_ids=[ev.id], confidence=0.8)
    ranked = g.find_paths_between_entities(a.id, b.id, max_depth=2)
    assert ranked
    assert ranked[0][0]["via"] == "relationship"


def test_alias_only_path_penalized():
    g, ev = _graph()
    a = g.add_entity("WORDLIB", "project", aliases=["shared"], evidence_ids=[ev.id], confidence=0.9)
    b = g.add_entity("MotherEther", "project", aliases=["shared"], evidence_ids=[ev.id], confidence=0.9)
    neighbors = g.semantic_neighbors(a.id)
    alias = [n for n in neighbors if n["via"] == "alias"]
    relationship_like = [n for n in neighbors if n["via"] == "shared_evidence"]
    assert alias and relationship_like
    assert alias[0]["edge_score"] < relationship_like[0]["edge_score"]


def test_graph_summary_for_prompt_no_match_safe():
    g, ev = _graph()
    bridge = SemanticRAGBridge(g)
    prompt = bridge.graph_summary_for_prompt("no such entity")
    assert "No matching semantic entities" in prompt


def test_ingest_document_controls_min_confidence_and_max_entities():
    g = SemanticKnowledgeGraph(storage_path=Path(tempfile.mkdtemp()) / "semantic_graph.json")
    bridge = SemanticRAGBridge(g, entity_hints={"WORDLIB": "project"})
    result = bridge.ingest_document_text(
        "WORDLIB uses Semantic Core, EntityExtractor, SemanticKnowledgeGraph, deploy_check.py and src/semantic_core.py.",
        source_path="doc.md",
        max_entities_per_document=2,
        min_confidence=0.8,
    )
    assert result["entity_count"] <= 2
    assert result["skipped_count"] >= 1


def test_default_storage_path_is_project_local():
    g = SemanticKnowledgeGraph()
    assert str(g.storage_path.resolve()).startswith(str(ROOT.resolve()))
