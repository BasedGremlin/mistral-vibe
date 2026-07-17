#!/usr/bin/env python3
"""
WORDLIB Deployment Check + Pathfinding
======================================
Runs ON the USB stick (any drive letter, Windows or Linux) and reports
exactly what is deployed, what is missing, and the next command to run.

This is the "self-automated deployment" verifier. It does NOT download
anything (that needs the Setup scripts + internet). It resolves all paths
relative to itself, probes every subsystem, and tells you precisely where
you stand and what to do next.

Run:
  python deploy_check.py          # full report
  python deploy_check.py --json   # machine-readable
  python deploy_check.py --next   # just the next recommended action
"""

import json
import os
import platform
import shutil
import socket
import sys
from pathlib import Path

# ── Pathfinding: resolve USB root from wherever this file actually is ────────
ROOT = Path(__file__).resolve().parent
IS_WINDOWS = platform.system() == "Windows"

# Colours (cosmetic)
if IS_WINDOWS:
    os.system("color")
G="\033[92m"; R="\033[91m"; Y="\033[93m"; C="\033[96m"; B="\033[1m"; W="\033[0m"


def _c(text, col):
    return f"{col}{text}{W}"


# ── Probes ───────────────────────────────────────────────────────────────────

def find_python():
    """Find a usable Python on the host (the launcher uses the same logic)."""
    candidates = []
    embedded = ROOT / "python" / ("python.exe" if IS_WINDOWS else "python")
    if embedded.exists():
        candidates.append(str(embedded))
    for name in (("py", "python", "python3") if IS_WINDOWS else ("python3", "python")):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    return candidates


def check_disk_space():
    """Free space on the USB in GB."""
    try:
        free = shutil.disk_usage(str(ROOT)).free / 1_073_741_824
        return round(free, 1)
    except Exception:
        return None


def has_internet():
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except OSError:
        return False


def check_structure():
    """Verify the expected folder + file skeleton exists."""
    required_files = [
        "launcher.py", "RUN_ME.bat", "scripts/run_me.sh",
        "content_seeder.py", "deploy_check.py",
        "src/ether_core.py", "src/rag_manager.py", "src/usb_orchestrator.py",
        "src/self_editor.py", "src/hub_client.py", "src/content_manager.py",
        "src/creative_bridge.py", "src/openclaw_bridge.py",
        "app/main.py", "config/creative.json",
        "src/semantic_core.py", "src/semantic_adapter.py", "src/local_ontology.py",
        "src/memory_semantic_hook.py", "src/code_structure_hook.py",
        "core/contracts/spec_protocol.py", "docking/specification_protocol.py",
        "docking/protocol/validator.py", "docking/protocol/lifecycle.py",
        "docking/protocol/auditor.py", "docking/protocol/registry.py",
        "docking/contracts/SPEC_DOCUMENT_V1_1.schema.json",
        "docking/templates/SPEC_TEMPLATE.xml", "docking/registry/spec_registry.json",
    ]
    required_dirs = [
        "src", "app", "app/templates", "config", "storage", "data",
        "core", "core/contracts", "docking", "docking/specs", "docking/reports",
        "docking/contracts", "docking/templates", "docking/registry", "docking/protocol", "docking/audit",
        "Setup", "models", "backups", "logs",
    ]
    missing_files = [f for f in required_files if not (ROOT / f).exists()]
    missing_dirs  = [d for d in required_dirs if not (ROOT / d).is_dir()]
    return {
        "files_ok":   len(required_files) - len(missing_files),
        "files_total": len(required_files),
        "dirs_ok":    len(required_dirs) - len(missing_dirs),
        "dirs_total": len(required_dirs),
        "missing_files": missing_files,
        "missing_dirs":  missing_dirs,
    }


def check_python_syntax():
    """Verify every Python module parses (catches a corrupted copy)."""
    import ast
    py_files = list(ROOT.glob("*.py")) + list((ROOT / "src").glob("*.py"))
    py_files += list((ROOT / "core").glob("*.py"))
    py_files += list((ROOT / "core" / "contracts").glob("*.py"))
    py_files += list((ROOT / "docking").glob("*.py"))
    py_files += list((ROOT / "docking" / "protocol").glob("*.py"))
    py_files += [ROOT / "app" / "main.py"]
    broken = []
    for f in py_files:
        if not f.exists():
            continue
        try:
            ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as e:
            broken.append(f"{f.name}: line {e.lineno}")
    return {"checked": len(py_files), "broken": broken}


def check_setup_state():
    """Determine which setup steps have been completed."""
    state = {}

    # Ollama binary
    ollama_exe = ROOT / "core" / "ollama" / ("ollama.exe" if IS_WINDOWS else "ollama")
    state["ollama_installed"] = ollama_exe.exists() or bool(shutil.which("ollama"))

    # Ollama models
    models_dir = ROOT / "core" / "ollama" / "models"
    state["ollama_models"] = (
        models_dir.exists() and any(models_dir.iterdir())
        if models_dir.exists() else False
    )

    # GGUF models for llama-cpp
    gguf = list((ROOT / "models").glob("*.gguf")) if (ROOT / "models").exists() else []
    state["gguf_models"] = [g.name for g in gguf]

    # Godot
    godot_exe = ROOT / "Godot" / (
        "Godot_v4.7-stable_win64.exe" if IS_WINDOWS
        else "Godot_v4.7-stable_linux.x86_64")
    state["godot_installed"] = godot_exe.exists()

    # Kiwix
    kiwix_exe = ROOT / "core" / "kiwix" / ("kiwix-serve.exe" if IS_WINDOWS else "kiwix-serve")
    zims = list((ROOT / "core" / "kiwix").glob("*.zim")) if (ROOT / "core" / "kiwix").exists() else []
    state["kiwix_installed"] = kiwix_exe.exists()
    state["kiwix_zims"] = len(zims)

    # Python venv (built by launcher on first run)
    venv = ROOT / ".venv" / ("Scripts" if IS_WINDOWS else "bin") / ("python.exe" if IS_WINDOWS else "python")
    state["venv_ready"] = venv.exists()

    # Seeded content
    storage = ROOT / "storage"
    md_count = len(list(storage.rglob("*.md"))) if storage.exists() else 0
    state["seeded_content_files"] = md_count

    return state


def check_semantic_core():
    """Hard deployment gate for the provenance-aware semantic core v2."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    try:
        from semantic_core import SemanticKnowledgeGraph, SemanticRAGBridge, SCHEMA_VERSION

        graph = SemanticKnowledgeGraph()
        storage_path = graph.storage_path.resolve()
        root_resolved = ROOT.resolve()
        if not storage_path or not str(storage_path).startswith(str(root_resolved)):
            return {"healthy": False, "error": "semantic storage path is not project-local"}

        evidence = graph.add_evidence("deploy_check", "WORDLIB semantic deploy gate evidence.")
        for fact_name, call in {
            "entity": lambda: graph.add_entity("Unproven Entity", "concept"),
            "relationship": lambda: graph.add_relationship("missing", "missing2", "broken"),
            "event": lambda: graph.add_event("Unproven Event", "deployment_gate"),
        }.items():
            try:
                call()
                return {"healthy": False, "error": f"{fact_name} without evidence was accepted"}
            except ValueError:
                pass

        try:
            graph.add_evidence("deploy_check", "bad confidence evidence", confidence=1.5)
            return {"healthy": False, "error": "invalid evidence confidence was accepted"}
        except ValueError:
            pass

        project = graph.add_entity("WORDLIB", "project", confidence=0.95, evidence_ids=[evidence.id])
        module = graph.add_entity("semantic_core.py", "file", aliases=["src/semantic_core.py"], confidence=0.95, evidence_ids=[evidence.id])
        duplicate = graph.add_entity("src/semantic_core.py", "file", confidence=0.90, evidence_ids=[evidence.id])
        if duplicate.id != module.id:
            graph.compact()
            if graph.find_entity("semantic_core.py").id != graph.find_entity("src/semantic_core.py").id:
                return {"healthy": False, "error": "canonical duplicate merge failed"}
        graph.add_relationship(project.id, module.id, "contains module", confidence=0.9, evidence_ids=[evidence.id])
        graph.add_event("Semantic core deploy validation", "deployment_gate", [project.id, module.id], confidence=0.9, evidence_ids=[evidence.id])

        clone = SemanticKnowledgeGraph()
        clone.import_json(graph.export_json())
        bad_payload = json.loads(graph.export_json())
        bad_payload["entities"][0]["evidence_ids"] = ["EVID_MISSING"]
        try:
            SemanticKnowledgeGraph().import_json(bad_payload)
            return {"healthy": False, "error": "missing evidence import was accepted"}
        except ValueError:
            pass

        path = clone.shortest_semantic_path("WORDLIB", "semantic_core.py")
        if not path:
            return {"healthy": False, "error": "pathfinding failed"}
        ranked = clone.rank_paths_by_confidence(clone.find_paths_between_entities("WORDLIB", "semantic_core.py", max_depth=3))
        if ranked and ranked[0][0].get("via") != "relationship":
            return {"healthy": False, "error": "path ranking did not prefer explicit relationship"}

        bridge = SemanticRAGBridge(clone)
        result = bridge.ingest_document_text(
            "WORDLIB validates src/semantic_core.py through deploy_check.py evidence and SemanticKnowledgeGraph audit_integrity().",
            source_path="deploy_check.py",
            max_entities_per_document=8,
            min_confidence=0.55,
        )
        if result["entity_count"] < 2:
            return {"healthy": False, "error": "RAG bridge ingestion extracted too few entities"}
        prompt_context = bridge.graph_summary_for_prompt("WORDLIB semantic_core.py")
        if "semantic graph context" not in prompt_context or "Evidence" not in prompt_context:
            return {"healthy": False, "error": "RAG bridge context failed"}

        audit = clone.audit_integrity()
        if not audit.get("healthy"):
            return {"healthy": False, "error": "audit_integrity reported unhealthy", "audit": audit}
        summary = clone.summary()
        if not summary.get("healthy") or summary.get("schema") != SCHEMA_VERSION:
            return {"healthy": False, "error": "summary reported unhealthy or wrong schema"}
        return {
            "healthy": True,
            "schema": SCHEMA_VERSION,
            "summary": summary,
            "audit": audit,
            "path": clone.explain_path(path),
            "path_score": clone.explain_path_structured(path)["path_score"],
            "storage_path": str(storage_path),
        }
    except Exception as exc:
        return {"healthy": False, "error": f"{type(exc).__name__}: {exc}"}


def check_semantic_adapter():
    """Deployment gate for the semantic adapter boundary over semantic_core v2."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    try:
        from semantic_adapter import create_default_adapter, SemanticAdapter, SemanticAdapterConfig

        adapter = create_default_adapter(auto_load=False, auto_save=False)
        health = adapter.health_check()
        if not health.ok:
            return {"healthy": False, "error": health.error or "adapter health_check failed"}
        if not health.data.get("project_local_storage"):
            return {"healthy": False, "error": "semantic adapter storage path is not project-local"}

        fact = adapter.add_evidence_backed_fact(
            "WORDLIB", "contains adapter", "semantic_adapter.py",
            "WORDLIB contains src/semantic_adapter.py as a path-safe adapter over semantic_core.py.",
            subject_type="project", object_type="file", source_type="deploy_check", confidence=0.9,
        )
        if not fact.ok:
            return {"healthy": False, "error": f"adapter fact creation failed: {fact.error}"}

        bad = adapter.add_evidence_backed_fact(
            "Bad", "broken", "Fact", "bad confidence should fail",
            source_type="deploy_check", confidence=2.0,
        )
        if bad.ok:
            return {"healthy": False, "error": "adapter accepted invalid confidence"}

        ingest = adapter.ingest_text(
            "WORDLIB uses SemanticAdapter and semantic_core.py to expose stable RAG and memory hooks without circular imports.",
            source_path="deploy_check.py", max_entities=6, min_confidence=0.55,
        )
        if not ingest.ok or ingest.data.get("entity_count", 0) < 2:
            return {"healthy": False, "error": f"adapter ingestion failed: {ingest.error or ingest.data}"}

        context = adapter.context_for_query("WORDLIB semantic adapter", as_prompt=True)
        if not context.ok or "semantic graph context" not in context.data.get("prompt_context", ""):
            return {"healthy": False, "error": "adapter prompt context failed"}
        if "Local ontology context" not in context.data.get("prompt_context", ""):
            return {"healthy": False, "error": "adapter local ontology prompt context failed"}
        ontology = adapter.ontology_context_for_query("WORDLIB Semantic Adapter RAG")
        if not ontology.ok or not ontology.data.get("matches"):
            return {"healthy": False, "error": "semantic adapter local ontology context failed"}

        path = adapter.shortest_path("WORDLIB", "semantic_adapter.py")
        if not path.ok or not path.data.get("found"):
            return {"healthy": False, "error": "adapter shortest_path failed"}

        compact = adapter.compact_and_audit()
        if not compact.ok or not compact.data.get("audit", {}).get("healthy"):
            return {"healthy": False, "error": "adapter compact/audit failed", "details": compact.to_dict()}

        # Verify a custom temp-path adapter can be created without auto-loading or external services.
        custom = SemanticAdapter(SemanticAdapterConfig(auto_load=False, auto_save=False, storage_path=str(ROOT / "data" / "semantic_core" / "adapter_gate_tmp.json")))
        custom_health = custom.health_check()
        if not custom_health.ok:
            return {"healthy": False, "error": "custom adapter health check failed"}

        return {
            "healthy": True,
            "contract": adapter.CONTRACT_VERSION,
            "summary": adapter.graph.summary(),
            "path": path.data.get("text"),
            "storage_path": str(adapter.storage_path.resolve()),
            "warnings": compact.warnings,
        }
    except Exception as exc:
        return {"healthy": False, "error": f"{type(exc).__name__}: {exc}"}

def check_capabilities():
    """Probe the blob brain if possible."""
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from ether_core import get_core
        core = get_core()
        s = core.status()
        return {
            "core_online": True,
            "capabilities": f"{s['capabilities_available']}/{s['capabilities_total']}",
        }
    except Exception as e:
        return {"core_online": False, "error": str(e)[:80]}


def check_local_ontology():
    """Deployment gate for the lightweight read-only local ontology layer."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    try:
        from local_ontology import create_default_ontology, ONTOLOGY_SCHEMA_VERSION
        ontology = create_default_ontology()
        audit = ontology.audit()
        if not audit.get("healthy"):
            return {"healthy": False, "error": "; ".join(audit.get("errors", [])[:3])}
        if ontology.classify("semantic_core.py") is None:
            return {"healthy": False, "error": "ontology cannot classify semantic_core.py"}
        if ontology.classify("RAG") is None:
            return {"healthy": False, "error": "ontology cannot classify RAG"}
        hints = ontology.entity_hints()
        if hints.get("WORDLIB") != "project":
            return {"healthy": False, "error": "ontology entity hints missing WORDLIB project"}
        prompt = ontology.prompt_context("WORDLIB Semantic Adapter RAG")
        if "Local ontology context" not in prompt or "Semantic Adapter" not in prompt:
            return {"healthy": False, "error": "ontology prompt context is not useful"}
        return {"healthy": True, "schema": ONTOLOGY_SCHEMA_VERSION, "summary": ontology.summary(), "matches": [t.name for t in ontology.find_terms("WORDLIB Semantic Adapter RAG")]}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def check_rag_semantic_hook():
    """Validate the optional read-only RAG -> SemanticAdapter hook without vector services."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    try:
        from rag_manager import semantic_context_for_rag_query
        result = semantic_context_for_rag_query("WORDLIB Semantic Adapter RAG", as_prompt=True)
        if not result.get("read_only"):
            return {"healthy": False, "error": "RAG semantic hook is not marked read-only"}
        if not result.get("ok"):
            return {"healthy": False, "error": result.get("error", "semantic hook failed")}
        prompt = result.get("data", {}).get("prompt_context", "")
        if "Local ontology context" not in prompt or "semantic graph context" not in prompt:
            return {"healthy": False, "error": "RAG semantic hook did not return ontology + semantic context"}
        return {"healthy": True, "hook": result.get("hook"), "read_only": True}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def check_memory_semantic_hook():
    """Validate optional read-only memory -> SemanticAdapter hook without agents or DBs."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    try:
        from memory_semantic_hook import semantic_context_for_memory_query, semantic_memory_status
        result = semantic_context_for_memory_query("WORDLIB memory SemanticAdapter gremlin", as_prompt=True, max_items=4)
        if not result.get("read_only"):
            return {"healthy": False, "error": "memory semantic hook is not marked read-only"}
        if not result.get("ok"):
            return {"healthy": False, "error": result.get("error", "memory semantic hook failed")}
        prompt = result.get("data", {}).get("prompt_context", "")
        if "WORDLIB memory context" not in prompt:
            return {"healthy": False, "error": "memory semantic hook did not return memory context"}
        if "Local ontology context" not in prompt and "semantic graph context" not in prompt:
            return {"healthy": False, "error": "memory semantic hook did not include adapter context"}
        data = result.get("data", {})
        if not data.get("read_only"):
            return {"healthy": False, "error": "adapter memory context is not read-only"}
        if not data.get("sources"):
            return {"healthy": False, "error": "memory hook did not report sources"}
        status = semantic_memory_status()
        if not status.get("ok") or not status.get("read_only"):
            return {"healthy": False, "error": status.get("error", "semantic memory status failed")}
        return {"healthy": True, "hook": result.get("hook"), "read_only": True, "summary": data.get("summary", {})}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def check_code_structure_hook():
    """Validate optional read-only code AST -> SemanticAdapter hook without heavy dependencies."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    try:
        from code_structure_hook import semantic_context_for_code_query, code_structure_status, CodeStructureHook
        result = semantic_context_for_code_query("SemanticAdapter code_structure_hook CodeStructureHook ast", as_prompt=True, max_items=6)
        if not result.get("read_only"):
            return {"healthy": False, "error": "code structure hook is not marked read-only"}
        if not result.get("ok"):
            return {"healthy": False, "error": result.get("error", "code structure hook failed")}
        data = result.get("data", {})
        if not data.get("read_only"):
            return {"healthy": False, "error": "adapter code context is not read-only"}
        prompt = data.get("prompt_context", "")
        if "WORDLIB code structure context" not in prompt:
            return {"healthy": False, "error": "code structure hook did not return AST prompt context"}
        summary = data.get("summary", {})
        if summary.get("modules", 0) <= 0 or summary.get("functions", 0) <= 0:
            return {"healthy": False, "error": "code structure hook did not scan modules/functions"}
        matches = data.get("matches", {})
        if not (matches.get("modules") or matches.get("classes") or matches.get("functions") or matches.get("call_sites")):
            return {"healthy": False, "error": "code structure hook returned no useful matches"}
        status = code_structure_status()
        if not status.get("ok") or not status.get("read_only"):
            return {"healthy": False, "error": status.get("error", "code structure status failed")}
        hook = CodeStructureHook(max_files=40, max_items=4)
        scan = hook.scan()
        if scan.get("summary", {}).get("parse_errors", 0) != 0:
            return {"healthy": False, "error": "AST scan reported parse errors", "details": scan.get("parse_errors", [])[:3]}
        return {"healthy": True, "hook": result.get("hook"), "read_only": True, "summary": summary}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def check_nexus_snapshot():
    """Validate SemanticAdapter unified NEXUS snapshot gate without writes/heavy deps."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    try:
        from semantic_adapter import create_default_adapter, NexusSnapshot, nexus_snapshot_status
        adapter = create_default_adapter(auto_load=True, auto_save=False)
        snapshot = adapter.get_unified_nexus_snapshot("SemanticAdapter NEXUS memory code ontology RAG")
        if not isinstance(snapshot, NexusSnapshot):
            return {"healthy": False, "error": "get_unified_nexus_snapshot did not return NexusSnapshot"}
        data = snapshot.to_dict()
        if data.get("read_only") is not True:
            return {"healthy": False, "error": "NEXUS snapshot is not read-only"}
        required = {"memory", "code", "ontology", "rag"}
        sections = data.get("sections", {})
        if set(sections.keys()) != required:
            return {"healthy": False, "error": "NEXUS snapshot missing required sections", "sections": sorted(sections.keys())}
        if not data.get("generated_at"):
            return {"healthy": False, "error": "NEXUS snapshot missing top-level timestamp"}
        for name in required:
            section = sections.get(name, {})
            if not section.get("generated_at"):
                return {"healthy": False, "error": f"NEXUS section {name} missing timestamp"}
            if "ok" not in section or "warnings" not in section:
                return {"healthy": False, "error": f"NEXUS section {name} missing health/warning fields"}
        if "causal_links" not in data or "temporal_links" not in data:
            return {"healthy": False, "error": "NEXUS snapshot missing future causal/temporal placeholders"}
        summary = data.get("summary", {})
        if not summary.get("agent_summary") or summary.get("nexus_role") != "unified_context_snapshot":
            return {"healthy": False, "error": "NEXUS snapshot missing agent-ready top-level summary"}
        health = data.get("health", {})
        if "overall" not in health or "sections" not in health:
            return {"healthy": False, "error": "NEXUS snapshot missing health indicators"}
        exported = snapshot.export_json()
        if "wordlib.nexus_snapshot.v1" not in exported:
            return {"healthy": False, "error": "NEXUS snapshot export_json missing contract"}
        prompt = adapter.nexus_snapshot_for_prompt("SemanticAdapter NEXUS")
        if not prompt.ok or "NEXUS unified context snapshot" not in prompt.data.get("prompt_context", ""):
            return {"healthy": False, "error": "NEXUS prompt context failed"}
        status = nexus_snapshot_status("SemanticAdapter NEXUS status")
        if not status.get("read_only") or not status.get("sections"):
            return {"healthy": False, "error": status.get("error", "NEXUS status failed")}
        return {"healthy": True, "contract": data.get("contract"), "read_only": True, "summary": summary}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def check_nexus_reflection():
    """Validate read-only NEXUS reflection/self-critique gate."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    try:
        from semantic_adapter import create_default_adapter, NexusSnapshot, ReflectionResult, reflection_status
        adapter = create_default_adapter(auto_load=True, auto_save=False)
        snapshot = adapter.get_unified_nexus_snapshot("SemanticAdapter NEXUS reflection memory code ontology RAG")
        before_graph = snapshot.export_json()
        result = adapter.reflect_on_snapshot(snapshot, "SemanticAdapter NEXUS reflection memory code ontology RAG")
        after_graph = snapshot.export_json()
        if not isinstance(snapshot, NexusSnapshot):
            return {"healthy": False, "error": "reflection test snapshot was not NexusSnapshot"}
        if not isinstance(result, ReflectionResult):
            return {"healthy": False, "error": "reflect_on_snapshot did not return ReflectionResult"}
        data = result.to_dict()
        if before_graph != after_graph:
            return {"healthy": False, "error": "reflection mutated the NexusSnapshot"}
        if data.get("read_only") is not True:
            return {"healthy": False, "error": "ReflectionResult is not read-only"}
        required_fields = {
            "overall_relevance_score", "section_scores", "missing_or_weak_sections",
            "retrieval_weaknesses", "suggested_improvements", "critique_summary",
            "generated_at", "query",
        }
        if not required_fields.issubset(data.keys()):
            return {"healthy": False, "error": "ReflectionResult missing required fields", "fields": sorted(data.keys())}
        score = data.get("overall_relevance_score")
        if not isinstance(score, (int, float)) or not (0.0 <= float(score) <= 1.0):
            return {"healthy": False, "error": "overall relevance score is not in 0.0-1.0 range"}
        scores = data.get("section_scores", {})
        if set(scores.keys()) != {"memory", "code", "ontology", "rag"}:
            return {"healthy": False, "error": "reflection section_scores missing required sections", "section_scores": scores}
        for name, value in scores.items():
            if not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 1.0):
                return {"healthy": False, "error": f"reflection score for {name} is invalid"}
        for field in ("missing_or_weak_sections", "retrieval_weaknesses", "suggested_improvements"):
            if not isinstance(data.get(field), list):
                return {"healthy": False, "error": f"ReflectionResult field {field} is not a list"}
        if not data.get("critique_summary") or "NEXUS reflection" not in data.get("critique_summary", ""):
            return {"healthy": False, "error": "reflection critique summary is missing or not agent-readable"}
        exported = result.export_json()
        if "wordlib.nexus_reflection.v1" not in exported:
            return {"healthy": False, "error": "ReflectionResult export_json missing contract"}
        prompt = adapter.reflection_for_prompt(snapshot, "SemanticAdapter NEXUS reflection")
        if not prompt.ok or "NEXUS reflection/self-critique" not in prompt.data.get("prompt_context", ""):
            return {"healthy": False, "error": "reflection prompt context failed"}
        status = reflection_status("SemanticAdapter NEXUS reflection status")
        if not status.get("ok") or not status.get("read_only"):
            return {"healthy": False, "error": status.get("error", "reflection status failed")}
        # Static-ish guard: reflection must not call persistence or mutation helpers.
        source = (ROOT / "src" / "semantic_adapter.py").read_text(encoding="utf-8")
        reflection_body = source.split("def reflect_on_snapshot", 1)[1].split("def reflection_for_prompt", 1)[0]
        forbidden = [".save(", "add_evidence", "add_entity", "add_relationship", "ingest_document_text", "_save_if_configured"]
        found = [token for token in forbidden if token in reflection_body]
        if found:
            return {"healthy": False, "error": "reflection body contains forbidden write/mutation call", "found": found}
        return {"healthy": True, "contract": data.get("contract"), "read_only": True, "overall_relevance_score": data.get("overall_relevance_score"), "section_scores": scores, "weak_sections": data.get("missing_or_weak_sections", [])}
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def check_intelligent_context():
    """Validate guarded NEXUS intelligent context bridge gate."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    try:
        from semantic_adapter import create_default_adapter, IntelligentContextPackage, intelligent_context_status
        adapter = create_default_adapter(auto_load=True, auto_save=False)
        before = adapter.graph.export_json()
        package = adapter.build_intelligent_context(
            "Cloud integration SemanticAdapter NEXUS code memory ontology RAG",
            max_tokens=6000,
            strictness="production",
        )
        after = adapter.graph.export_json()
        if not isinstance(package, IntelligentContextPackage):
            return {"healthy": False, "error": "build_intelligent_context did not return IntelligentContextPackage"}
        if before != after:
            return {"healthy": False, "error": "build_intelligent_context mutated semantic graph"}
        data = package.to_dict()
        required = {
            "goal", "curated_context", "selection_reasoning", "context_health", "quality_audit",
            "overall_quality_score", "token_estimate", "warnings", "proposed_mutations", "generated_at",
        }
        if not required.issubset(data.keys()):
            return {"healthy": False, "error": "IntelligentContextPackage missing required fields", "fields": sorted(data.keys())}
        if data.get("contract") != "wordlib.nexus_intelligent_context.v1":
            return {"healthy": False, "error": "unexpected intelligent context contract"}
        if data.get("read_only") is not True:
            return {"healthy": False, "error": "IntelligentContextPackage is not read-only"}
        score = data.get("overall_quality_score")
        if not isinstance(score, (int, float)) or not (0.0 <= float(score) <= 1.0):
            return {"healthy": False, "error": "overall_quality_score is invalid"}
        if not isinstance(data.get("token_estimate"), int) or data.get("token_estimate") <= 0:
            return {"healthy": False, "error": "token_estimate is invalid"}
        context = data.get("curated_context", {})
        sections = context.get("sections", {})
        if set(sections.keys()) != {"memory", "code", "ontology", "rag"}:
            return {"healthy": False, "error": "curated context missing required source sections", "sections": sorted(sections.keys())}
        health = data.get("context_health", {})
        if health.get("safety_contract", {}).get("read_only") is not True:
            return {"healthy": False, "error": "intelligent context safety contract is not read-only"}
        if health.get("safety_contract", {}).get("actual_writes") is not False:
            return {"healthy": False, "error": "intelligent context reports actual writes"}
        centralization = health.get("centralization_status", {})
        if centralization.get("single_source_of_truth") != "core.paths":
            return {"healthy": False, "error": "centralization status does not point to core.paths"}
        audit = data.get("quality_audit", {})
        if "score" not in audit or "breakdown" not in audit or "note" not in audit:
            return {"healthy": False, "error": "quality_audit missing v30-style heuristic fields"}
        if not data.get("selection_reasoning") or "SemanticAdapter" not in data.get("selection_reasoning", ""):
            return {"healthy": False, "error": "selection_reasoning missing adapter/pathfinding explanation"}
        for mutation in data.get("proposed_mutations", []):
            if mutation.get("read_only_now") is not True or "SelfEditor" not in mutation.get("guard_required", ""):
                return {"healthy": False, "error": "proposed mutation lacks SelfEditor read-only guard", "mutation": mutation}
        exported = package.export_json()
        if "wordlib.nexus_intelligent_context.v1" not in exported:
            return {"healthy": False, "error": "IntelligentContextPackage export_json missing contract"}
        prompt = adapter.intelligent_context_for_prompt("Cloud integration SemanticAdapter NEXUS")
        if not prompt.ok or "NEXUS intelligent context package" not in prompt.data.get("prompt_context", ""):
            return {"healthy": False, "error": "intelligent context prompt failed"}
        status = intelligent_context_status("Cloud integration SemanticAdapter NEXUS status")
        if not status.get("ok") or not status.get("read_only"):
            return {"healthy": False, "error": status.get("error", "intelligent context status failed")}
        # Static-ish guard: bridge package creation must not call persistence or mutation helpers.
        source = (ROOT / "src" / "semantic_adapter.py").read_text(encoding="utf-8")
        body = source.split("def build_intelligent_context", 1)[1].split("def intelligent_context_for_prompt", 1)[0]
        forbidden = [".save(", "add_evidence", "add_entity", "add_relationship", "ingest_document_text", "_save_if_configured", "write_text(", "open("]
        found = [token for token in forbidden if token in body]
        if found:
            return {"healthy": False, "error": "build_intelligent_context body contains forbidden write/mutation call", "found": found}
        return {
            "healthy": True,
            "contract": data.get("contract"),
            "read_only": True,
            "overall_quality_score": data.get("overall_quality_score"),
            "token_estimate": data.get("token_estimate"),
            "ranked_sections": context.get("ranked_sections", []),
            "centralized": centralization.get("centralized"),
            "warnings": data.get("warnings", []),
        }
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def check_causal_temporal_proposals():
    """Validate read-only NEXUS causal/temporal proposal scaffolding gate."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    try:
        from semantic_adapter import (
            create_default_adapter,
            NexusSnapshot,
            ReflectionResult,
            CausalTemporalProposal,
            causal_temporal_status,
        )
        adapter = create_default_adapter(auto_load=True, auto_save=False)
        snapshot = adapter.get_unified_nexus_snapshot("Cloud causal temporal deployment fix memory code reflection")
        reflection = adapter.reflect_on_snapshot(snapshot, "Cloud causal temporal deployment fix memory code reflection")
        before_graph = adapter.graph.export_json()
        before_snapshot = snapshot.export_json()
        proposal = adapter.propose_causal_temporal_links(snapshot, reflection=reflection, max_candidates=10)
        after_graph = adapter.graph.export_json()
        after_snapshot = snapshot.export_json()
        if not isinstance(snapshot, NexusSnapshot) or not isinstance(reflection, ReflectionResult):
            return {"healthy": False, "error": "test setup did not produce NexusSnapshot and ReflectionResult"}
        if not isinstance(proposal, CausalTemporalProposal):
            return {"healthy": False, "error": "propose_causal_temporal_links did not return CausalTemporalProposal"}
        if before_graph != after_graph:
            return {"healthy": False, "error": "causal temporal proposal mutated semantic graph"}
        if before_snapshot != after_snapshot:
            return {"healthy": False, "error": "causal temporal proposal mutated the supplied snapshot"}
        data = proposal.to_dict()
        required = {"candidates", "summary", "warnings", "future_integration_notes", "generated_at"}
        if not required.issubset(data.keys()):
            return {"healthy": False, "error": "CausalTemporalProposal missing required fields", "fields": sorted(data.keys())}
        if data.get("contract") != "wordlib.nexus_causal_temporal.v1":
            return {"healthy": False, "error": "unexpected causal temporal contract"}
        if data.get("read_only") is not True:
            return {"healthy": False, "error": "CausalTemporalProposal is not read-only"}
        candidates = data.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            return {"healthy": False, "error": "causal temporal proposal produced no candidates"}
        allowed_types = {"temporal", "causal", "invalidation", "contradiction"}
        for candidate in candidates:
            if candidate.get("status") != "candidate":
                return {"healthy": False, "error": "candidate status is not candidate", "candidate": candidate}
            if candidate.get("type") not in allowed_types:
                return {"healthy": False, "error": "candidate type is invalid", "candidate": candidate}
            confidence = candidate.get("confidence")
            if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
                return {"healthy": False, "error": "candidate confidence is invalid", "candidate": candidate}
            if not candidate.get("source_evidence"):
                return {"healthy": False, "error": "candidate lacks source_evidence", "candidate": candidate}
            if not candidate.get("id") or not str(candidate.get("id")).startswith("CTP_"):
                return {"healthy": False, "error": "candidate lacks stable pathfinder id", "candidate": candidate}
            if not candidate.get("evidence_path") or not isinstance(candidate.get("evidence_path"), list):
                return {"healthy": False, "error": "candidate lacks evidence_path", "candidate": candidate}
            if not candidate.get("path_explanation"):
                return {"healthy": False, "error": "candidate lacks path_explanation", "candidate": candidate}
            if "SelfEditor" not in str(candidate.get("guard_required_before_fact", "")):
                return {"healthy": False, "error": "candidate lacks SelfEditor guard warning", "candidate": candidate}
            if candidate.get("guard_required_before_fact") is None:
                return {"healthy": False, "error": "candidate lacks future guard warning", "candidate": candidate}
        routes = data.get("pathfinder_routes", [])
        if not routes or len(routes) != len(candidates):
            return {"healthy": False, "error": "pathfinder routes missing or not aligned with candidates"}
        for route in routes:
            if not route.get("candidate_id") or not route.get("path") or not route.get("path_explanation"):
                return {"healthy": False, "error": "invalid pathfinder route", "route": route}
            if not route.get("route_id") or not str(route.get("route_id")).startswith("CTR_"):
                return {"healthy": False, "error": "pathfinder route lacks stable route_id", "route": route}
            score = route.get("route_health_score")
            if not isinstance(score, (int, float)) or not (0.0 <= float(score) <= 1.0):
                return {"healthy": False, "error": "pathfinder route has invalid health score", "route": route}
            if route.get("route_grade") not in {"strong_review_candidate", "review_candidate", "weak_candidate"}:
                return {"healthy": False, "error": "pathfinder route has invalid grade", "route": route}
            if "Merge-safe" not in str(route.get("merge_note", "")):
                return {"healthy": False, "error": "pathfinder route lacks merge-safe note", "route": route}
            if "SelfEditor whitelist" not in route.get("guard_chain", []):
                return {"healthy": False, "error": "pathfinder route lacks full guard chain", "route": route}
        entry = data.get("scaffolding_entry", {})
        if not entry.get("entry_id") or entry.get("read_only") is not True:
            return {"healthy": False, "error": "causal scaffolding entry is missing or not read-only", "entry": entry}
        if entry.get("source_of_truth") != "SemanticAdapter -> IntelligentContextPackage -> NexusSnapshot/Reflection":
            return {"healthy": False, "error": "causal scaffolding entry bypasses the guarded source of truth", "entry": entry}
        if not entry.get("merge_surface", {}).get("merge_friendly"):
            return {"healthy": False, "error": "causal scaffolding entry is not merge-friendly", "entry": entry}
        if not isinstance(entry.get("scaffolding_readiness_score"), (int, float)):
            return {"healthy": False, "error": "causal scaffolding entry lacks readiness score", "entry": entry}
        bridge = data.get("self_reorganization_bridge", {})
        if bridge.get("can_execute_reorganization") is not False or "No mutation" not in str(bridge.get("hard_stop", "")):
            return {"healthy": False, "error": "self-reorganization bridge is not safely proposal-only", "bridge": bridge}
        if "trigger SelfEditor" not in bridge.get("denied_actions", []):
            return {"healthy": False, "error": "self-reorganization bridge does not explicitly deny SelfEditor execution", "bridge": bridge}
        pathways = data.get("reorganization_pathways", [])
        if not isinstance(pathways, list) or not pathways:
            return {"healthy": False, "error": "reorganization pathways missing"}
        for pathway in pathways:
            if not str(pathway.get("pathway_id", "")).startswith("REORG_PATH_"):
                return {"healthy": False, "error": "invalid reorganization pathway id", "pathway": pathway}
            if not pathway.get("forbidden_now") or not pathway.get("next_gate"):
                return {"healthy": False, "error": "reorganization pathway lacks guard detail", "pathway": pathway}
        merge = data.get("merge_guidance", {})
        if not merge.get("no_split_required") or merge.get("new_dependencies") != []:
            return {"healthy": False, "error": "merge guidance is not surgical/no-dependency", "merge_guidance": merge}
        if not isinstance(merge.get("readiness_score"), (int, float)):
            return {"healthy": False, "error": "merge guidance lacks readiness score", "merge_guidance": merge}
        if "src/semantic_adapter.py" not in merge.get("minimal_touch_files", []):
            return {"healthy": False, "error": "merge guidance missing adapter touch surface", "merge_guidance": merge}
        if data.get("metadata", {}).get("consumes_intelligent_context_package") is not True:
            return {"healthy": False, "error": "causal layer does not declare IntelligentContextPackage consumption"}
        if not data.get("future_integration_notes") or "causal store" not in " ".join(data.get("future_integration_notes", [])).lower():
            return {"healthy": False, "error": "future integration notes missing causal storage caution"}
        exported = proposal.export_json()
        if "wordlib.nexus_causal_temporal.v1" not in exported or '"status": "candidate"' not in exported:
            return {"healthy": False, "error": "CausalTemporalProposal export_json missing contract or candidate status"}
        prompt = adapter.causal_temporal_for_prompt(snapshot, reflection=reflection, max_candidates=5)
        if not prompt.ok or "causal/temporal proposal layer" not in prompt.data.get("prompt_context", ""):
            return {"healthy": False, "error": "causal temporal prompt context failed"}
        status = causal_temporal_status("Cloud causal temporal status")
        if not status.get("ok") or not status.get("read_only"):
            return {"healthy": False, "error": status.get("error", "causal temporal status failed")}
        source = (ROOT / "src" / "semantic_adapter.py").read_text(encoding="utf-8")
        body = source.split("def propose_causal_temporal_links", 1)[1].split("def causal_temporal_for_prompt", 1)[0]
        forbidden = [".save(", "add_evidence", "add_entity", "add_relationship", "ingest_document_text", "_save_if_configured", "write_text(", "open("]
        found = [token for token in forbidden if token in body]
        if found:
            return {"healthy": False, "error": "propose_causal_temporal_links body contains forbidden write/mutation call", "found": found}
        type_counts = data.get("metadata", {}).get("candidate_type_counts", {})
        return {
            "healthy": True,
            "contract": data.get("contract"),
            "read_only": True,
            "candidate_count": len(candidates),
            "candidate_type_counts": type_counts,
            "pathfinder_routes": len(routes),
            "route_health_avg": round(sum(float(r.get("route_health_score", 0.0) or 0.0) for r in routes) / len(routes), 3) if routes else 0.0,
            "scaffolding_entry_id": entry.get("entry_id"),
            "scaffolding_readiness_score": entry.get("scaffolding_readiness_score"),
            "merge_safe": merge.get("safe_to_merge"),
            "merge_readiness_score": merge.get("readiness_score"),
            "reorganization_pathways": len(pathways),
            "strong_candidate_ids": bridge.get("strong_candidate_ids", []),
            "can_suggest_reorganization": bridge.get("can_suggest_reorganization"),
            "warnings": data.get("warnings", []),
            "summary": data.get("summary"),
        }
    except Exception as e:
        return {"healthy": False, "error": str(e)}



def check_docking_protocol():
    """Validate the NEUROFORGE docking/specification protocol v1.1 foundation."""
    sys.path.insert(0, str(ROOT))
    try:
        from core.contracts.spec_protocol import (
            SPEC_PROTOCOL_VERSION,
            SPEC_DOCUMENT_CONTRACT,
            IMPLEMENTATION_REPORT_CONTRACT,
            CHANGE_TRACE_CONTRACT,
            SPEC_REGISTRY_CONTRACT,
            ChangeTrace,
            ImplementationReport,
            minimal_spec_payload,
            protocol_self_description,
            spec_from_payload,
            validate_implementation_report_payload,
            validate_spec_payload,
            validate_status_transition,
        )
        from docking.specification_protocol import (
            DOCKING_PROTOCOL_VERSION,
            docking_protocol_status,
            parse_spec_xml_text,
            spec_template_xml,
            validate_all_specs,
            validate_implementation_report,
            transition_allowed,
            pre_implementation_validation,
            validate_spec_before_implementation,
            get_recent_validation_audit,
        )
        from core.contracts.docking.SpecDocument import SpecDocument as StrictSpecDocument, SPEC_DOCUMENT_MODEL_CONTRACT
        from core.contracts.docking.ChangeTrace import ChangeTrace as StrictChangeTrace, CHANGE_TRACE_MODEL_CONTRACT
        from pydantic import ValidationError

        before_files = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "docking").rglob("*") if p.is_file()) if (ROOT / "docking").exists() else []
        status = docking_protocol_status()
        after_files = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "docking").rglob("*") if p.is_file()) if (ROOT / "docking").exists() else []
        if before_files != after_files:
            return {"healthy": False, "error": "docking status mutated files"}
        if not status.get("ok"):
            return {"healthy": False, "error": status.get("error", "docking protocol status failed"), "status": status}
        if status.get("contract") != DOCKING_PROTOCOL_VERSION or DOCKING_PROTOCOL_VERSION != "neuroforge.docking_protocol.v1.1":
            return {"healthy": False, "error": "unexpected docking protocol contract"}
        if status.get("spec_contract") != SPEC_PROTOCOL_VERSION or SPEC_PROTOCOL_VERSION != "neuroforge.spec_protocol.v1.1":
            return {"healthy": False, "error": "unexpected spec contract version"}
        if status.get("read_only") is not True:
            return {"healthy": False, "error": "docking protocol status is not read-only"}
        if status.get("cns_contract") != "neuroforge.docking_cns.v1.2":
            return {"healthy": False, "error": "docking CNS contract missing or wrong"}
        strict = status.get("strict_pydantic_contracts", {})
        if strict.get("SpecDocument") != SPEC_DOCUMENT_MODEL_CONTRACT or strict.get("ChangeTrace") != CHANGE_TRACE_MODEL_CONTRACT or strict.get("present") is not True:
            return {"healthy": False, "error": "strict Pydantic CNS contracts missing", "strict": strict}
        required_dirs = status.get("dirs", {})
        if not all(required_dirs.values()):
            return {"healthy": False, "error": "required docking directories missing", "dirs": required_dirs}
        required_files = status.get("required_files", {})
        if not all(required_files.values()):
            return {"healthy": False, "error": "required docking files missing", "files": required_files}

        payload = minimal_spec_payload("SPEC-DEPLOY-CHECK", "Deploy Check Contract Validation")
        ok, issues = validate_spec_payload(payload)
        if not ok:
            return {"healthy": False, "error": "minimal spec payload failed validation", "issues": [i.to_dict() for i in issues]}
        spec = spec_from_payload(payload)
        if spec.spec_id != "SPEC-DEPLOY-CHECK" or spec.status != "draft" or not spec.acceptance_criteria:
            return {"healthy": False, "error": "spec_from_payload failed to produce v1.1 contract object"}
        if SPEC_DOCUMENT_CONTRACT not in spec.contracts:
            return {"healthy": False, "error": "spec contract list missing SpecDocument v1.1"}

        try:
            StrictSpecDocument(meta={})
            return {"healthy": False, "error": "strict SpecDocument accepted malformed meta"}
        except ValidationError:
            pass
        try:
            StrictChangeTrace(file_path="/abs/path.py", spec_id="SPEC-X", action="modified", reason="bad", timestamp="2026-06-27T00:00:00+00:00", previous_hash="sha256:x")
            return {"healthy": False, "error": "strict ChangeTrace accepted absolute file path"}
        except ValidationError:
            pass

        xml_spec = parse_spec_xml_text(spec_template_xml())
        if xml_spec.spec_id != "SPEC-0001_DOCKING_PROTOCOL_CONTRACTS" or xml_spec.status != "accepted" or not xml_spec.allowed_files:
            return {"healthy": False, "error": "SpecDocument template XML did not parse correctly"}
        bad = dict(payload)
        bad["acceptance_criteria"] = []
        bad_ok, _bad_issues = validate_spec_payload(bad)
        if bad_ok:
            return {"healthy": False, "error": "invalid spec without acceptance criteria was accepted"}

        # Formal lifecycle guard checks.
        ok_transition, trans_issues = validate_status_transition("draft", "accepted", {"human_approved": True})
        if not ok_transition:
            return {"healthy": False, "error": "valid draft->accepted transition rejected", "issues": [i.to_dict() for i in trans_issues]}
        blocked_transition = transition_allowed("implemented", "verified", {"verification_passed": True, "acceptance_criteria_met": True, "human_approved": False})
        if blocked_transition.get("ok"):
            return {"healthy": False, "error": "verified transition accepted without human approval"}

        trace = ChangeTrace(
            file_path="docking/specification_protocol.py",
            spec_id="SPEC-DEPLOY-CHECK",
            action="modified",
            reason="Deploy check validates v1.1 ChangeTrace contract.",
            timestamp="2026-06-27T00:00:00+00:00",
            previous_hash="sha256:previous-or-none",
        )
        report = ImplementationReport(
            spec_id="SPEC-DEPLOY-CHECK",
            implemented_version="1.1.0",
            status="success",
            human_approval_required=True,
            files_modified=["docking/specification_protocol.py"],
            files_created=[],
            files_deleted=[],
            change_traces=[trace],
            contracts_implemented=[SPEC_DOCUMENT_CONTRACT, IMPLEMENTATION_REPORT_CONTRACT, CHANGE_TRACE_CONTRACT, SPEC_REGISTRY_CONTRACT],
            tests_added=["tests/test_docking_protocol.py"],
            verification_results={"deploy_check": True},
            notes=["Deploy check contract roundtrip."],
        )
        report_ok, report_issues = validate_implementation_report_payload(report.to_dict())
        if not report_ok:
            return {"healthy": False, "error": "ImplementationReport v1.1 failed validation", "issues": [i.to_dict() for i in report_issues]}
        if not validate_implementation_report(report.to_dict()).get("ok"):
            return {"healthy": False, "error": "docking validator rejected valid implementation report"}
        conflict_payload = report.to_dict()
        conflict_payload["status"] = "conflict"
        conflict_payload["issues"] = {"conflicts": [], "deviations": []}
        conflict_ok, _ = validate_implementation_report_payload(conflict_payload)
        if conflict_ok:
            return {"healthy": False, "error": "conflict report without conflicts was accepted"}

        self_desc = protocol_self_description()
        if self_desc.get("version") != "1.1.0" or "SPEC-0000" not in " ".join(self_desc.get("principles", [])):
            return {"healthy": False, "error": "protocol self-description incomplete"}

        all_specs = validate_all_specs()
        if not all_specs.get("ok"):
            return {"healthy": False, "error": "spec directory validation failed", "spec_validation": all_specs}

        audit_before = len(get_recent_validation_audit(10000))
        gate_result = validate_spec_before_implementation(spec_template_xml())
        audit_after = len(get_recent_validation_audit(10000))
        if not gate_result.get("ok") or gate_result.get("status") != "passed":
            return {"healthy": False, "error": "pre-implementation validation rejected valid template", "gate": gate_result}
        if audit_after <= audit_before:
            return {"healthy": False, "error": "pre-implementation validation did not append audit event"}
        bad_gate = pre_implementation_validation("<SpecDocument><meta></meta></SpecDocument>")
        if bad_gate.get("status") != "blocked" or bad_gate.get("ok") is not False:
            return {"healthy": False, "error": "pre-implementation validation accepted malformed spec", "gate": bad_gate}
        recent = get_recent_validation_audit(2)
        if len(recent) < 2 or not all({"timestamp", "spec_id", "status", "issues", "validator_version"}.issubset(e.keys()) for e in recent):
            return {"healthy": False, "error": "validation audit entries are not queryable or missing required fields", "recent": recent}

        source = (ROOT / "docking" / "specification_protocol.py").read_text(encoding="utf-8")
        body = source.split("def docking_protocol_status", 1)[1].split("if __name__", 1)[0]
        forbidden = ["write_text(", ".write(", "mkdir(", "unlink(", "open("]
        found = [token for token in forbidden if token in body]
        if found:
            return {"healthy": False, "error": "docking_protocol_status body contains forbidden write/mutation call", "found": found}
        return {
            "healthy": True,
            "contract": DOCKING_PROTOCOL_VERSION,
            "spec_contract": SPEC_PROTOCOL_VERSION,
            "document_contract": SPEC_DOCUMENT_CONTRACT,
            "implementation_report_contract": IMPLEMENTATION_REPORT_CONTRACT,
            "change_trace_contract": CHANGE_TRACE_CONTRACT,
            "registry_contract": SPEC_REGISTRY_CONTRACT,
            "read_only": True,
            "cns_contract": status.get("cns_contract"),
            "cns_validator": status.get("cns_validator"),
            "audit_recent_count": len(get_recent_validation_audit(10)),
            "state_machine": status.get("lifecycle", {}).get("contract"),
            "spec_count": all_specs.get("spec_count", 0),
            "registry_specs": status.get("registry", {}).get("registered_specs", 0),
            "template_valid": status.get("template_valid"),
            "single_source_of_truth": status.get("single_source_of_truth"),
            "implementation_surface": status.get("implementation_surface"),
            "validator_surface": status.get("validator_surface"),
            "lifecycle_surface": status.get("lifecycle_surface"),
            "registry_surface": status.get("registry_surface"),
            "auditor_surface": status.get("auditor_surface"),
            "human_approval_gate": status.get("human_approval_gate"),
            "paths": status.get("paths", {}),
        }
    except Exception as e:
        return {"healthy": False, "error": str(e)}

def check_commander_pathway():
    """Validate the single-call NEXUS Commander troubleshooting pathway gate."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    try:
        from semantic_adapter import (
            create_default_adapter,
            CommanderPathwayPackage,
            commander_pathway_status,
        )
        adapter = create_default_adapter(auto_load=True, auto_save=False)
        before_graph = adapter.graph.export_json()
        package = adapter.build_commander_troubleshooting_pathway("Cloud merge guarded self reorganization causal pathfinder", max_steps=6)
        after_graph = adapter.graph.export_json()
        if not isinstance(package, CommanderPathwayPackage):
            return {"healthy": False, "error": "build_commander_troubleshooting_pathway did not return CommanderPathwayPackage"}
        if before_graph != after_graph:
            return {"healthy": False, "error": "Commander pathway mutated semantic graph"}
        data = package.to_dict()
        required = {"goal", "commander_summary", "public_surface", "troubleshooting_pathways", "sequenced_steps", "invalidation_map", "failure_predictions", "evidence_routes", "causal_bridge_summary", "merge_capabilities", "warnings", "generated_at"}
        if not required.issubset(data.keys()):
            return {"healthy": False, "error": "CommanderPathwayPackage missing required fields", "fields": sorted(data.keys())}
        if data.get("contract") != "wordlib.nexus_commander_pathway.v1":
            return {"healthy": False, "error": "unexpected Commander contract"}
        if data.get("read_only") is not True:
            return {"healthy": False, "error": "Commander package is not read-only"}
        public = data.get("public_surface", {})
        if public.get("single_entrypoint") != "SemanticAdapter.build_commander_troubleshooting_pathway":
            return {"healthy": False, "error": "Commander package lacks single public entrypoint", "public_surface": public}
        if "propose_causal_temporal_links" not in public.get("replaces_external_stitching_of", []):
            return {"healthy": False, "error": "Commander package does not replace external stitching", "public_surface": public}
        steps = data.get("sequenced_steps", [])
        if not isinstance(steps, list) or not steps:
            return {"healthy": False, "error": "Commander package produced no sequenced steps"}
        sequences = [step.get("sequence") for step in steps]
        if sequences != sorted(sequences) or sequences[0] != 1:
            return {"healthy": False, "error": "Commander steps are not cleanly sequenced", "steps": steps}
        for step in steps:
            if not str(step.get("step_id", "")).startswith("CMD_STEP_"):
                return {"healthy": False, "error": "Commander step lacks stable id", "step": step}
            if step.get("action_mode") != "read_only_review":
                return {"healthy": False, "error": "Commander step is not read-only review", "step": step}
            forbidden = step.get("forbidden_now", [])
            if "trigger SelfEditor" not in forbidden or "write memory" not in forbidden:
                return {"healthy": False, "error": "Commander step lacks forbidden execution guard", "step": step}
            if not step.get("expected_failure_prevented"):
                return {"healthy": False, "error": "Commander step lacks failure-prevention purpose", "step": step}
        routes = data.get("evidence_routes", [])
        if not isinstance(routes, list) or not routes:
            return {"healthy": False, "error": "Commander package lacks evidence routes"}
        bridge = data.get("causal_bridge_summary", {})
        if bridge.get("can_execute_reorganization") is not False:
            return {"healthy": False, "error": "Commander bridge can execute reorganization", "bridge": bridge}
        merge = data.get("merge_capabilities", {})
        if merge.get("no_new_dependencies") is not True or merge.get("no_file_split") is not True:
            return {"healthy": False, "error": "Commander merge capabilities are not surgical", "merge": merge}
        if "src/semantic_adapter.py" not in merge.get("minimal_touch_files", []):
            return {"healthy": False, "error": "Commander merge capabilities missing adapter touch surface", "merge": merge}
        failures = data.get("failure_predictions", [])
        if not isinstance(failures, list):
            return {"healthy": False, "error": "Commander failure predictions are not a list"}
        for pred in failures:
            if not str(pred.get("prediction_id", "")).startswith("FAIL_PATH_"):
                return {"healthy": False, "error": "Commander failure prediction lacks stable id", "prediction": pred}
            if not pred.get("preventive_step"):
                return {"healthy": False, "error": "Commander failure prediction lacks preventive step", "prediction": pred}
        inv = data.get("invalidation_map", [])
        if not isinstance(inv, list):
            return {"healthy": False, "error": "Commander invalidation map is not a list"}
        prompt = adapter.commander_pathway_for_prompt("Cloud merge guarded self reorganization causal pathfinder", max_steps=5)
        if not prompt.ok or "NEXUS Commander pathway" not in prompt.data.get("prompt_context", ""):
            return {"healthy": False, "error": "Commander prompt context failed"}
        status = commander_pathway_status("Cloud commander status")
        if not status.get("ok") or not status.get("read_only"):
            return {"healthy": False, "error": status.get("error", "Commander status failed")}
        source = (ROOT / "src" / "semantic_adapter.py").read_text(encoding="utf-8")
        body = source.split("def build_commander_troubleshooting_pathway", 1)[1].split("def commander_pathway_for_prompt", 1)[0]
        forbidden = [".save(", "add_evidence", "add_entity", "add_relationship", "ingest_document_text", "_save_if_configured", "write_text(", "open("]
        found = [token for token in forbidden if token in body]
        if found:
            return {"healthy": False, "error": "build_commander_troubleshooting_pathway body contains forbidden write/mutation call", "found": found}
        return {
            "healthy": True,
            "contract": data.get("contract"),
            "read_only": True,
            "step_count": len(steps),
            "route_count": len(routes),
            "pathway_count": len(data.get("troubleshooting_pathways", [])),
            "invalidation_maps": len(inv),
            "failure_predictions": len(failures),
            "single_entrypoint": public.get("single_entrypoint"),
            "merge_safe": merge.get("merge_safe"),
            "can_execute_reorganization": bridge.get("can_execute_reorganization"),
            "warnings": data.get("warnings", []),
            "summary": data.get("commander_summary"),
        }
    except Exception as e:
        return {"healthy": False, "error": str(e)}


# ── Next-action logic ────────────────────────────────────────────────────────

def determine_next_action(report):
    """The single most important thing to do next."""
    setup = report["setup"]
    struct = report["structure"]
    syntax = report["syntax"]
    semantic = report.get("semantic_core", {})
    adapter = report.get("semantic_adapter", {})
    ontology = report.get("local_ontology", {})
    rag_hook = report.get("rag_semantic_hook", {})
    memory_hook = report.get("memory_semantic_hook", {})
    code_hook = report.get("code_structure_hook", {})
    nexus = report.get("nexus_snapshot", {})
    reflection = report.get("nexus_reflection", {})
    intelligent = report.get("intelligent_context", {})
    causal = report.get("causal_temporal", {})
    commander = report.get("commander_pathway", {})
    docking = report.get("docking_protocol", {})

    if not docking.get("healthy", False):
        return ("DOCKING PROTOCOL FAILED",
                f"docking/specification protocol failed deployment validation: {docking.get('error', 'unknown error')}")

    if not semantic.get("healthy", False):
        return ("SEMANTIC CORE FAILED",
                f"semantic_core.py failed deployment validation: {semantic.get('error', 'unknown error')}")
    if not adapter.get("healthy", False):
        return ("SEMANTIC ADAPTER FAILED",
                f"semantic_adapter.py failed deployment validation: {adapter.get('error', 'unknown error')}")
    if not ontology.get("healthy", False):
        return ("LOCAL ONTOLOGY FAILED",
                f"local_ontology.py failed deployment validation: {ontology.get('error', 'unknown error')}")
    if not rag_hook.get("healthy", False):
        return ("RAG SEMANTIC HOOK FAILED",
                f"RAG semantic hook failed deployment validation: {rag_hook.get('error', 'unknown error')}")
    if not memory_hook.get("healthy", False):
        return ("MEMORY SEMANTIC HOOK FAILED",
                f"Memory semantic hook failed deployment validation: {memory_hook.get('error', 'unknown error')}")
    if not code_hook.get("healthy", False):
        return ("CODE STRUCTURE HOOK FAILED",
                f"Code structure hook failed deployment validation: {code_hook.get('error', 'unknown error')}")
    if not nexus.get("healthy", False):
        return ("NEXUS SNAPSHOT FAILED",
                f"NEXUS unified snapshot failed deployment validation: {nexus.get('error', 'unknown error')}")
    if not reflection.get("healthy", False):
        return ("NEXUS REFLECTION FAILED",
                f"NEXUS reflection failed deployment validation: {reflection.get('error', 'unknown error')}")
    if not intelligent.get("healthy", False):
        return ("NEXUS INTELLIGENT CONTEXT FAILED",
                f"NEXUS intelligent context bridge failed deployment validation: {intelligent.get('error', 'unknown error')}")
    if not causal.get("healthy", False):
        return ("NEXUS CAUSAL TEMPORAL FAILED",
                f"NEXUS causal/temporal proposal gate failed deployment validation: {causal.get('error', 'unknown error')}")
    if not commander.get("healthy", False):
        return ("NEXUS COMMANDER FAILED",
                f"NEXUS Commander pathway gate failed deployment validation: {commander.get('error', 'unknown error')}")
    if struct["missing_files"] or struct["missing_dirs"]:
        return ("INCOMPLETE COPY",
                "Some files/folders are missing. Re-extract the wordlib zip "
                "to the USB so the structure is complete.")
    if syntax["broken"]:
        return ("CORRUPTED FILES",
                f"Python files failed to parse: {', '.join(syntax['broken'])}. "
                "Re-extract from a clean zip.")
    if not report["python"]:
        return ("NO PYTHON",
                "Install Python 3.8+ from python.org (check 'Add to PATH'), then re-run.")
    if not setup["ollama_installed"]:
        return ("INSTALL OLLAMA",
                "Run Setup/01_Install_Ollama.bat (Windows) or setup_linux.sh (Linux) "
                "to install Ollama and pull the models. Needs internet.")
    if not setup["ollama_models"] and not setup["gguf_models"]:
        return ("PULL MODELS",
                "Ollama is installed but no models found. Run Setup/01 to pull "
                "qwen2.5-coder, dolphin3, and nomic-embed-text.")
    if not setup["venv_ready"]:
        return ("FIRST LAUNCH",
                "Everything's in place. Double-click RUN_ME.bat (or ./run_me.sh) "
                "-- the first launch builds the Python environment automatically.")
    return ("READY",
            "Fully deployed. Double-click RUN_ME.bat (or ./run_me.sh) and pick "
            "option 1 (Start Everything).")


# ── Report builder ───────────────────────────────────────────────────────────

def build_report():
    return {
        "usb_root":   str(ROOT),
        "platform":   platform.system(),
        "drive":      str(ROOT.drive) if IS_WINDOWS else "/",
        "python":     find_python(),
        "disk_free_gb": check_disk_space(),
        "internet":   has_internet(),
        "structure":  check_structure(),
        "syntax":     check_python_syntax(),
        "setup":      check_setup_state(),
        "capabilities": check_capabilities(),
        "semantic_core": check_semantic_core(),
        "semantic_adapter": check_semantic_adapter(),
        "local_ontology": check_local_ontology(),
        "rag_semantic_hook": check_rag_semantic_hook(),
        "memory_semantic_hook": check_memory_semantic_hook(),
        "code_structure_hook": check_code_structure_hook(),
        "nexus_snapshot": check_nexus_snapshot(),
        "nexus_reflection": check_nexus_reflection(),
        "intelligent_context": check_intelligent_context(),
        "causal_temporal": check_causal_temporal_proposals(),
        "commander_pathway": check_commander_pathway(),
        "docking_protocol": check_docking_protocol(),
    }


def print_report(report):
    print()
    print(_c("=" * 60, C))
    print(_c("  WORDLIB Deployment Check + Pathfinding", B))
    print(_c("=" * 60, C))
    print()

    # Pathfinding
    print(_c("  PATHFINDING", B))
    print(f"    USB root : {report['usb_root']}")
    print(f"    Platform : {report['platform']}  (drive: {report['drive']})")
    pys = report["python"]
    if pys:
        print(_c(f"    Python   : {pys[0]}", G))
    else:
        print(_c("    Python   : NOT FOUND", R))
    df = report["disk_free_gb"]
    col = G if (df and df > 2) else (Y if df else R)
    print(_c(f"    Free     : {df} GB", col))
    print(f"    Internet : {'yes' if report['internet'] else 'no (offline)'}")
    print()

    # Structure
    s = report["structure"]
    print(_c("  STRUCTURE", B))
    fcol = G if s["files_ok"] == s["files_total"] else R
    dcol = G if s["dirs_ok"]  == s["dirs_total"]  else R
    print(_c(f"    Files : {s['files_ok']}/{s['files_total']}", fcol))
    print(_c(f"    Dirs  : {s['dirs_ok']}/{s['dirs_total']}", dcol))
    if s["missing_files"]:
        print(_c(f"    Missing files: {', '.join(s['missing_files'][:5])}", R))
    if s["missing_dirs"]:
        print(_c(f"    Missing dirs: {', '.join(s['missing_dirs'][:5])}", R))
    print()

    # Syntax
    sy = report["syntax"]
    scol = G if not sy["broken"] else R
    print(_c("  CODE INTEGRITY", B))
    print(_c(f"    {sy['checked']} Python files checked, "
             f"{len(sy['broken'])} broken", scol))
    print()

    # Docking/specification protocol gate
    docking = report.get("docking_protocol", {})
    print(_c("  NEUROFORGE DOCKING PROTOCOL", B))
    if docking.get("healthy"):
        print(_c(f"    docking protocol healthy -- {docking.get('contract')}", G))
        print(f"    specs={docking.get('spec_count')} registry={docking.get('registry_specs')} template={docking.get('template_valid')}")
        print(f"    lifecycle={docking.get('state_machine')} approval={docking.get('human_approval_gate')}")
        print(f"    CNS={docking.get('cns_contract')} audit_events={docking.get('audit_recent_count')}")
        print(f"    source: {docking.get('single_source_of_truth')}")
    else:
        print(_c(f"    docking protocol FAILED: {docking.get('error', 'unknown error')}", R))
    print()

    # Setup state
    st = report["setup"]
    print(_c("  SETUP STATE", B))
    def mark(b): return _c("[OK]  ", G) if b else _c("[ -- ]", Y)
    print(f"    {mark(st['ollama_installed'])} Ollama installed")
    print(f"    {mark(st['ollama_models'])} Ollama models present")
    print(f"    {mark(bool(st['gguf_models']))} GGUF models: "
          f"{', '.join(st['gguf_models']) or 'none'}")
    print(f"    {mark(st['godot_installed'])} Godot installed")
    print(f"    {mark(st['kiwix_installed'])} Kiwix installed "
          f"({st['kiwix_zims']} ZIM files)")
    print(f"    {mark(st['venv_ready'])} Python venv built")
    print(f"    {mark(st['seeded_content_files'] > 0)} Seeded content: "
          f"{st['seeded_content_files']} files")
    print()

    # Semantic core gate
    sem = report.get("semantic_core", {})
    print(_c("  SEMANTIC CORE", B))
    if sem.get("healthy"):
        print(_c(f"    semantic_core.py healthy -- {sem['summary']['entities']} entities checked", G))
        print(f"    path: {sem.get('path', 'validated')}")
    else:
        print(_c(f"    semantic_core.py FAILED: {sem.get('error', 'unknown error')}", R))
    print()

    # Semantic adapter gate
    adapter = report.get("semantic_adapter", {})
    print(_c("  SEMANTIC ADAPTER", B))
    if adapter.get("healthy"):
        print(_c(f"    semantic_adapter.py healthy -- {adapter.get('contract')}", G))
        print(f"    path: {adapter.get('path', 'validated')}")
    else:
        print(_c(f"    semantic_adapter.py FAILED: {adapter.get('error', 'unknown error')}", R))
    print()


    # Local ontology gate
    ontology = report.get("local_ontology", {})
    print(_c("  LOCAL ONTOLOGY", B))
    if ontology.get("healthy"):
        summary = ontology.get("summary", {})
        print(_c(f"    local_ontology.py healthy -- {summary.get('terms', 0)} terms", G))
        print(f"    schema: {ontology.get('schema', 'validated')}")
    else:
        print(_c(f"    local_ontology.py FAILED: {ontology.get('error', 'unknown error')}", R))
    print()

    # RAG semantic hook gate
    rag_hook = report.get("rag_semantic_hook", {})
    print(_c("  RAG SEMANTIC HOOK", B))
    if rag_hook.get("healthy"):
        print(_c(f"    read-only hook healthy -- {rag_hook.get('hook', 'validated')}", G))
    else:
        print(_c(f"    RAG semantic hook FAILED: {rag_hook.get('error', 'unknown error')}", R))
    print()
    # Memory semantic hook gate
    memory_hook = report.get("memory_semantic_hook", {})
    code_hook = report.get("code_structure_hook", {})
    print(_c("  MEMORY SEMANTIC HOOK", B))
    if memory_hook.get("healthy"):
        summary = memory_hook.get("summary", {})
        print(_c(f"    read-only hook healthy -- cycles={summary.get('cycles', 0)}, sampled events={summary.get('events_sampled', 0)}", G))
    else:
        print(_c(f"    Memory semantic hook FAILED: {memory_hook.get('error', 'unknown error')}", R))
    print()

    # Code structure hook gate
    code_hook = report.get("code_structure_hook", {})
    print(_c("  CODE STRUCTURE HOOK", B))
    if code_hook.get("healthy"):
        summary = code_hook.get("summary", {})
        print(_c(f"    read-only AST hook healthy -- modules={summary.get('modules', 0)}, functions={summary.get('functions', 0)}", G))
    else:
        print(_c(f"    Code structure hook FAILED: {code_hook.get('error', 'unknown error')}", R))
    print()

    # NEXUS snapshot gate
    nexus = report.get("nexus_snapshot", {})
    print(_c("  NEXUS UNIFIED SNAPSHOT", B))
    if nexus.get("healthy"):
        summary = nexus.get("summary", {})
        sections = ",".join(summary.get("sections_available", []))
        print(_c(f"    read-only snapshot healthy -- sections={sections}", G))
    else:
        print(_c(f"    NEXUS snapshot FAILED: {nexus.get('error', 'unknown error')}", R))
    print()

    # NEXUS reflection gate
    reflection = report.get("nexus_reflection", {})
    print(_c("  NEXUS REFLECTION", B))
    if reflection.get("healthy"):
        print(_c(f"    read-only reflection healthy -- score={reflection.get('overall_relevance_score')}, weak={','.join(reflection.get('weak_sections', [])) or 'none'}", G))
    else:
        print(_c(f"    NEXUS reflection FAILED: {reflection.get('error', 'unknown error')}", R))
    print()

    # NEXUS intelligent context gate
    intelligent = report.get("intelligent_context", {})
    print(_c("  NEXUS INTELLIGENT CONTEXT", B))
    if intelligent.get("healthy"):
        print(_c(f"    guarded context healthy -- quality={intelligent.get('overall_quality_score')}, tokens={intelligent.get('token_estimate')}", G))
        print(f"    sections: {','.join(intelligent.get('ranked_sections', []))}")
    else:
        print(_c(f"    NEXUS intelligent context FAILED: {intelligent.get('error', 'unknown error')}", R))
    print()

    # NEXUS causal/temporal proposal gate
    causal = report.get("causal_temporal", {})
    print(_c("  NEXUS CAUSAL/TEMPORAL", B))
    if causal.get("healthy"):
        print(_c(f"    proposal layer healthy -- candidates={causal.get('candidate_count')}, routes={causal.get('pathfinder_routes')}, pathways={causal.get('reorganization_pathways')}", G))
        print(f"    types: {causal.get('candidate_type_counts', {})}")
        print(f"    entry: {causal.get('scaffolding_entry_id')} | suggest={causal.get('can_suggest_reorganization')} | merge_safe={causal.get('merge_safe')} ({causal.get('merge_readiness_score')})")
    else:
        print(_c(f"    NEXUS causal/temporal FAILED: {causal.get('error', 'unknown error')}", R))
    print()

    # NEXUS Commander pathway gate
    commander = report.get("commander_pathway", {})
    print(_c("  NEXUS COMMANDER PATHWAY", B))
    if commander.get("healthy"):
        print(_c(f"    commander healthy -- steps={commander.get('step_count')}, routes={commander.get('route_count')}, failures={commander.get('failure_predictions')}", G))
        print(f"    entrypoint: {commander.get('single_entrypoint')}")
        print(f"    pathways: {commander.get('pathway_count')} | invalidations={commander.get('invalidation_maps')} | merge_safe={commander.get('merge_safe')}")
        print(f"    execute_reorg={commander.get('can_execute_reorganization')}")
    else:
        print(_c(f"    NEXUS Commander FAILED: {commander.get('error', 'unknown error')}", R))
    print()

    # Capabilities (blob brain)
    cap = report["capabilities"]
    print(_c("  BLOB BRAIN", B))
    if cap.get("core_online"):
        print(_c(f"    Ether core online -- {cap['capabilities']} capabilities", G))
    else:
        print(_c(f"    Ether core probe: {cap.get('error', 'unavailable')}", Y))
    print()

    # Next action
    action, detail = determine_next_action(report)
    acol = G if action == "READY" else Y
    print(_c("=" * 60, C))
    print(_c(f"  NEXT: {action}", acol + B))
    print(f"  {detail}")
    print(_c("=" * 60, C))
    print()


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    report = build_report()

    if arg == "--json":
        print(json.dumps(report, indent=2))
    elif arg == "--next":
        action, detail = determine_next_action(report)
        print(f"{action}: {detail}")
    else:
        print_report(report)

    if not report.get("docking_protocol", {}).get("healthy", False):
        return 1
    if not report.get("semantic_core", {}).get("healthy", False):
        return 1
    if not report.get("semantic_adapter", {}).get("healthy", False):
        return 1
    if not report.get("local_ontology", {}).get("healthy", False):
        return 1
    if not report.get("rag_semantic_hook", {}).get("healthy", False):
        return 1
    if not report.get("memory_semantic_hook", {}).get("healthy", False):
        return 1
    if not report.get("code_structure_hook", {}).get("healthy", False):
        return 1
    if not report.get("nexus_snapshot", {}).get("healthy", False):
        return 1
    if not report.get("nexus_reflection", {}).get("healthy", False):
        return 1
    if not report.get("intelligent_context", {}).get("healthy", False):
        return 1
    if not report.get("causal_temporal", {}).get("healthy", False):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
