import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code_structure_hook import CodeStructureHook, semantic_context_for_code_query, code_structure_status
from semantic_adapter import SemanticAdapter, SemanticAdapterConfig
from local_ontology import create_default_ontology


def test_code_structure_hook_scans_modules_classes_functions_imports():
    hook = CodeStructureHook(max_files=80, max_items=6)
    scan = hook.scan()
    assert scan["read_only"] is True
    assert scan["summary"]["modules"] > 0
    assert scan["summary"]["functions"] > 0
    assert scan["summary"]["imports"] > 0
    assert scan["summary"]["parse_errors"] == 0
    paths = {module["path"] for module in scan["modules"]}
    assert "src/semantic_adapter.py" in paths
    assert "src/code_structure_hook.py" in paths


def test_code_structure_context_finds_semantic_adapter_function():
    hook = CodeStructureHook(max_files=120, max_items=8)
    data = hook.context_for_query("SemanticAdapter code_structure_context_for_query", as_prompt=True)
    assert data["read_only"] is True
    assert data["matches"]["functions"] or data["matches"]["classes"] or data["matches"]["modules"]
    assert "WORDLIB code structure context" in data["prompt_context"]
    assert "SemanticAdapter" in data["prompt_context"] or "code_structure_context_for_query" in data["prompt_context"]


def test_adapter_exposes_code_structure_context_as_nexus_boundary():
    adapter = SemanticAdapter(SemanticAdapterConfig(auto_load=False, auto_save=False, max_code_files=90, max_code_items=6))
    result = adapter.code_structure_context_for_query("SemanticAdapter CodeStructureHook", as_prompt=True)
    assert result.ok, result.error
    assert result.data["read_only"] is True
    assert result.data["nexus_role"] == "code_structure_context"
    assert result.data["summary"]["modules"] > 0
    assert "WORDLIB code structure context" in result.data["prompt_context"]
    assert "Local ontology context" in result.data["prompt_context"] or "semantic graph context" in result.data["prompt_context"]


def test_code_structure_hook_function_routes_through_adapter():
    result = semantic_context_for_code_query("SemanticAdapter code_structure_hook", as_prompt=True, max_items=5)
    assert result["ok"] is True
    assert result["read_only"] is True
    assert result["hook"] == "code_structure_hook.semantic_context_for_code_query"
    assert result["data"]["read_only"] is True
    assert result["data"]["summary"]["functions"] > 0


def test_code_structure_status_is_boot_safe():
    status = code_structure_status()
    assert status["ok"] is True
    assert status["read_only"] is True
    assert status["summary"]["modules"] > 0
    assert status["summary"]["parse_errors"] == 0


def test_local_ontology_includes_code_structure_and_nexus_terms():
    ontology = create_default_ontology()
    hook = ontology.classify("code_structure_hook.py")
    nexus = ontology.classify("NEXUS central intelligence layer")
    assert hook is not None
    assert hook.name == "Code Structure Hook"
    assert hook.kind == "component"
    assert nexus is not None
    assert nexus.name == "NEXUS"


def test_deploy_check_code_structure_gate():
    spec = importlib.util.spec_from_file_location("deploy_check_code_hook", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.check_code_structure_hook()
    assert result["healthy"] is True
    assert result["read_only"] is True
    assert result["summary"]["modules"] > 0
