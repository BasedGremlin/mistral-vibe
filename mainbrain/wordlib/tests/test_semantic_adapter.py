"""Tests for the WORDLIB semantic adapter boundary."""
import importlib.util
import tempfile
from pathlib import Path

from semantic_adapter import (
    SemanticAdapter,
    SemanticAdapterConfig,
    create_default_adapter,
    semantic_adapter_status,
)

ROOT = Path(__file__).resolve().parents[1]


def _adapter(auto_save=False):
    return SemanticAdapter(SemanticAdapterConfig(
        storage_path=str(Path(tempfile.mkdtemp()) / "semantic_graph.json"),
        auto_load=False,
        auto_save=auto_save,
        entity_hints={"WORDLIB": "project", "MotherEther": "project"},
    ))


def test_adapter_health_check_is_stable_and_project_safe():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    result = adapter.health_check()
    assert result.ok
    assert result.data["contract"] == adapter.CONTRACT_VERSION
    assert result.data["schema"].startswith("wordlib.semantic_core")
    assert result.data["project_local_storage"] is True


def test_adapter_add_evidence_backed_fact_blocks_invalid_confidence():
    adapter = _adapter()
    ok = adapter.add_evidence_backed_fact(
        "WORDLIB", "contains adapter", "semantic_adapter.py",
        "WORDLIB contains src/semantic_adapter.py as a semantic boundary.",
        subject_type="project", object_type="file", source_type="test", confidence=0.9,
    )
    assert ok.ok, ok.error
    bad = adapter.add_evidence_backed_fact(
        "Bad", "broken", "Fact", "invalid confidence should be rejected",
        source_type="test", confidence=9.0,
    )
    assert bad.ok is False
    assert "confidence" in bad.error


def test_adapter_ingest_text_uses_controls_and_returns_warnings():
    adapter = _adapter()
    result = adapter.ingest_text(
        "WORDLIB MotherEther SemanticAdapter SemanticKnowledgeGraph EntityExtractor deploy_check.py src/semantic_core.py src/semantic_adapter.py",
        source_path="tests/test_semantic_adapter.py",
        max_entities=2,
        min_confidence=0.55,
    )
    assert result.ok, result.error
    assert result.data["entity_count"] <= 2
    assert result.data["skipped_count"] >= 1
    assert result.warnings


def test_adapter_context_for_query_structured_and_prompt():
    adapter = _adapter()
    adapter.ingest_text("WORDLIB uses SemanticAdapter for safe RAG hooks.", source_path="doc.md")
    structured = adapter.context_for_query("WORDLIB SemanticAdapter")
    prompt = adapter.context_for_query("WORDLIB SemanticAdapter", as_prompt=True)
    assert structured.ok and structured.data["matches"]
    assert prompt.ok
    assert "WORDLIB semantic graph context" in prompt.data["prompt_context"]


def test_adapter_shortest_path_and_compact_audit():
    adapter = _adapter()
    fact = adapter.add_evidence_backed_fact(
        "WORDLIB", "contains adapter", "semantic_adapter.py",
        "WORDLIB contains src/semantic_adapter.py.",
        subject_type="project", object_type="file", source_type="test", confidence=0.9,
    )
    assert fact.ok
    path = adapter.shortest_path("WORDLIB", "semantic_adapter.py")
    assert path.ok and path.data["found"] is True
    assert "WORDLIB" in path.data["text"]
    audit = adapter.compact_and_audit()
    assert audit.ok
    assert audit.data["audit"]["healthy"] is True


def test_adapter_save_load_roundtrip():
    adapter = _adapter(auto_save=False)
    adapter.add_evidence_backed_fact(
        "WORDLIB", "persists", "SemanticAdapter",
        "WORDLIB persists SemanticAdapter facts through semantic_core JSON.",
        subject_type="project", object_type="concept", source_type="test", confidence=0.85,
    )
    save = adapter.save()
    assert save.ok
    clone = SemanticAdapter(SemanticAdapterConfig(storage_path=save.data["storage_path"], auto_load=True, auto_save=False))
    ctx = clone.context_for_query("WORDLIB SemanticAdapter")
    assert ctx.ok
    assert clone.graph.summary()["entities"] >= 2


def test_adapter_export_snapshot_is_json_safe():
    adapter = _adapter()
    adapter.add_evidence_backed_fact(
        "WORDLIB", "exports", "semantic snapshot",
        "WORDLIB exports a JSON-safe semantic adapter snapshot.",
        subject_type="project", object_type="concept", source_type="test", confidence=0.8,
    )
    snapshot = adapter.export_snapshot()
    assert snapshot.ok
    assert snapshot.data["graph"]["schema"].startswith("wordlib.semantic_core")


def test_semantic_adapter_status_helper():
    status = semantic_adapter_status()
    assert status["ok"] is True
    assert status["data"]["contract"] == "wordlib.semantic_adapter.v2"


def test_deploy_check_semantic_adapter_gate():
    spec = importlib.util.spec_from_file_location("deploy_check_adapter", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.check_semantic_adapter()
    assert result["healthy"] is True
    assert result["contract"] == "wordlib.semantic_adapter.v2"
    assert "WORDLIB" in result["path"]
