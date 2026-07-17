import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from local_ontology import create_default_ontology, LocalOntologyLayer
from semantic_adapter import create_default_adapter
from rag_manager import semantic_context_for_rag_query


def test_local_ontology_audit_and_classification():
    ontology = create_default_ontology()
    audit = ontology.audit()
    assert audit["healthy"] is True
    assert ontology.classify("semantic_core.py").name == "Semantic Core"
    assert ontology.classify("RAG").kind == "subsystem"
    assert ontology.classify("No SQLite").kind == "constraint"


def test_local_ontology_entity_hints_are_adapter_ready():
    ontology = create_default_ontology()
    hints = ontology.entity_hints()
    assert hints["WORDLIB"] == "project"
    assert hints["Semantic Adapter"] == "component"
    assert hints["RAG"] == "subsystem"


def test_local_ontology_prompt_context_is_compact_and_relevant():
    ontology = LocalOntologyLayer()
    prompt = ontology.prompt_context("WORDLIB Semantic Adapter RAG")
    assert "Local ontology context" in prompt
    assert "Semantic Adapter" in prompt
    assert "RAG" in prompt


def test_semantic_adapter_exposes_ontology_context():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    result = adapter.ontology_context_for_query("WORDLIB Semantic Adapter RAG")
    assert result.ok is True
    assert result.data["matches"]
    names = {item["name"] for item in result.data["matches"]}
    assert "Semantic Adapter" in names


def test_adapter_prompt_context_includes_local_ontology_and_graph_context():
    adapter = create_default_adapter(auto_load=False, auto_save=False)
    result = adapter.context_for_query("WORDLIB Semantic Adapter RAG", as_prompt=True)
    assert result.ok is True
    prompt = result.data["prompt_context"]
    assert "Local ontology context" in prompt
    assert "WORDLIB semantic graph context" in prompt


def test_rag_semantic_hook_is_read_only_and_adapter_based():
    result = semantic_context_for_rag_query("WORDLIB Semantic Adapter RAG", as_prompt=True)
    assert result["read_only"] is True
    assert result["hook"] == "rag_manager.semantic_context_for_rag_query"
    assert result["ok"] is True
    prompt = result["data"]["prompt_context"]
    assert "Local ontology context" in prompt
    assert "semantic graph context" in prompt


def test_deploy_check_local_ontology_and_rag_hook_gates():
    spec = importlib.util.spec_from_file_location("deploy_check_semantic_hooks", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.check_local_ontology()["healthy"] is True
    assert mod.check_rag_semantic_hook()["healthy"] is True
