#!/usr/bin/env python3
"""
main.py -- the single recommended entry point for ETHER AI / WORDLIB.
====================================================================
Double-click run.bat (which calls this) and you always get a clear, honest
result: self-heal -> health check -> simple menu (or a clear error telling you
exactly what to do). All paths come from core.paths, so copying this folder to
another Windows laptop and running it Just Works.
"""
import sys
from pathlib import Path

# The one guarded bootstrap: locate the project root so core.paths is importable
# no matter where this is launched from. core.paths is authoritative thereafter.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paths import health_report, migration_report
from editor.self_healer import run_self_heal

try:
    from src.semantic_core import SemanticKnowledgeGraph
except Exception:
    SemanticKnowledgeGraph = None

try:
    from src.semantic_adapter import semantic_adapter_status, nexus_snapshot_status, reflection_status, intelligent_context_status, causal_temporal_status, commander_pathway_status
except Exception:
    semantic_adapter_status = None
    nexus_snapshot_status = None
    reflection_status = None
    intelligent_context_status = None
    causal_temporal_status = None
    commander_pathway_status = None

try:
    from src.memory_semantic_hook import semantic_memory_status
except Exception:
    semantic_memory_status = None

try:
    from src.code_structure_hook import code_structure_status
except Exception:
    code_structure_status = None

try:
    from docking.specification_protocol import docking_protocol_status
except Exception:
    docking_protocol_status = None


def _line(char="=", n=58):
    print(char * n)


def diagnose_paths():
    """
    Actively check for path problems at boot and return human-readable findings.
    Honest: 'pending' files still doing independent discovery are reported as a
    maintenance note, NOT a failure -- the system runs fine, they're just not
    centralized yet. This gives the user visibility without false alarms.
    """
    mig = migration_report()
    findings = []
    severity = "ok"

    pending = mig.get("pending_migration", [])
    # Entry-point files are the ones that MATTER for boot reliability.
    critical_entry = {"main.py", "launcher.py", "app/main.py"}
    pending_critical = [f for f in pending if f in critical_entry]

    if pending_critical:
        severity = "warning"
        findings.append(
            f"{len(pending_critical)} entry-point file(s) still use old path "
            f"code: {', '.join(pending_critical)}.")
        findings.append(
            "  What to do: these should import from core.paths. If you edited "
            "them by hand, re-copy them from your backup.")
    elif pending:
        # Non-entry files pending -> purely informational
        findings.append(
            f"{len(pending)} non-critical file(s) not yet centralized "
            f"(cosmetic; system runs fine). They'll be migrated over time.")

    return {"severity": severity, "findings": findings,
            "centralized": mig.get("migrated_count", 0),
            "pending": mig.get("pending_count", 0)}


def docking_protocol_boot_status():
    """Small read-only docking/spec protocol status for NEUROFORGE handoff."""
    if docking_protocol_status is None:
        return {"healthy": False, "error": "docking specification protocol import failed"}
    try:
        status = docking_protocol_status()
        return {"healthy": bool(status.get("ok")), "status": status, "error": status.get("error")}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}


def semantic_core_status():
    """Small boot-visible status, no write, no RAG startup."""
    if SemanticKnowledgeGraph is None:
        return {"healthy": False, "error": "semantic_core import failed"}
    try:
        graph = SemanticKnowledgeGraph()
        return {"healthy": True, "storage_path": str(graph.storage_path), "summary": graph.summary()}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}


def semantic_adapter_boot_status():
    """Small adapter status, no write, no RAG/vector startup."""
    if semantic_adapter_status is None:
        return {"healthy": False, "error": "semantic_adapter import failed"}
    try:
        status = semantic_adapter_status()
        return {"healthy": bool(status.get("ok")), "status": status, "error": status.get("error")}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}


def semantic_memory_boot_status():
    """Small read-only memory semantic status, no write and no agent startup."""
    if semantic_memory_status is None:
        return {"healthy": False, "error": "memory_semantic_hook import failed"}
    try:
        status = semantic_memory_status()
        return {"healthy": bool(status.get("ok")), "status": status, "error": status.get("error")}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}


def code_structure_boot_status():
    """Small read-only AST code structure status, no write and no heavy services."""
    if code_structure_status is None:
        return {"healthy": False, "error": "code_structure_hook import failed"}
    try:
        status = code_structure_status()
        return {"healthy": bool(status.get("ok")), "status": status, "error": status.get("error")}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}



def nexus_snapshot_boot_status():
    """Small read-only NEXUS snapshot status, no writes and no heavy services."""
    if nexus_snapshot_status is None:
        return {"healthy": False, "error": "nexus snapshot import failed"}
    try:
        status = nexus_snapshot_status("WORDLIB NEXUS boot SemanticAdapter")
        return {"healthy": bool(status.get("ok")), "status": status, "error": status.get("error")}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}


def reflection_boot_status():
    """Small read-only NEXUS reflection status, no writes and no heavy services."""
    if reflection_status is None:
        return {"healthy": False, "error": "reflection import failed"}
    try:
        status = reflection_status("WORDLIB NEXUS boot reflection SemanticAdapter")
        return {"healthy": bool(status.get("ok")), "status": status, "error": status.get("error")}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}

def intelligent_context_boot_status():
    """Small read-only NEXUS intelligent context status, no writes and no heavy services."""
    if intelligent_context_status is None:
        return {"healthy": False, "error": "intelligent context import failed"}
    try:
        status = intelligent_context_status("WORDLIB NEXUS Cloud bridge production context")
        return {"healthy": bool(status.get("ok")), "status": status, "error": status.get("error")}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}


def causal_temporal_boot_status():
    """Small read-only NEXUS causal/temporal proposal status, no writes and no heavy services."""
    if causal_temporal_status is None:
        return {"healthy": False, "error": "causal temporal import failed"}
    try:
        status = causal_temporal_status("WORDLIB NEXUS causal temporal Cloud bridge")
        return {"healthy": bool(status.get("ok")), "status": status, "error": status.get("error")}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}



def commander_pathway_boot_status():
    """Small read-only NEXUS Commander pathway status, no writes and no heavy services."""
    if commander_pathway_status is None:
        return {"healthy": False, "error": "commander pathway import failed"}
    try:
        status = commander_pathway_status("WORDLIB NEXUS Commander Cloud troubleshooting")
        return {"healthy": bool(status.get("ok")), "status": status, "error": status.get("error")}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}

def boot_checks(verbose=True):
    """Run self-heal + health. Returns (ok: bool, health: dict)."""
    if verbose:
        _line()
        print("  ETHER AI / WORDLIB")
        _line()

    heal = run_self_heal()
    if heal.created:
        print(f"\n  Self-healing: created {len(heal.created)} missing folder(s):")
        for c in heal.created:
            print(f"     + {c}")
    if heal.missing_unrecoverable:
        print("\n  [!] PROBLEM: critical files are missing and cannot be auto-created:")
        for m in heal.missing_unrecoverable:
            print(f"     - {m}")
        print("\n  What to do: re-copy the project folder from your backup or the")
        print("  original USB. These files are part of the system and can't be")
        print("  regenerated automatically.")
        return False, {}

    health = health_report()
    if verbose:
        ok = health["overall"] == "OK"
        symbol = "OK" if ok else health["overall"]
        print(f"\n  System health: {symbol}")
        print(f"     folders:   {health['filesystem']['status']}")
        print(f"     files:     {health['critical_files']['status']}")
        print(f"     python:    {health['python']['version']}")
        print(f"     portable:  {'yes' if health['deployment']['portable'] else 'no'}")

        docking = docking_protocol_boot_status()
        if docking.get("healthy"):
            st = docking["status"]
            audit = st.get('audit', {})
            print(f"     docking:   OK ({st.get('contract')}, specs={st.get('spec_validation', {}).get('spec_count', 0)}, lifecycle={st.get('lifecycle', {}).get('contract')})")
            failure = st.get('failure_memory', {})
            print(f"     Docking CNS: OK ({st.get('cns_contract')}, audit_events={audit.get('recent_count', 0)}, Recent Failures: {failure.get('recent_count', 0)})")
        else:
            print(f"     docking:   ERROR ({docking.get('error', 'unknown')})")

        sem = semantic_core_status()
        if sem.get("healthy"):
            print(f"     semantic:  OK ({sem['storage_path']})")
        else:
            print(f"     semantic:  ERROR ({sem.get('error', 'unknown')})")

        adapter = semantic_adapter_boot_status()
        if adapter.get("healthy"):
            contract = adapter["status"]["data"].get("contract", "semantic_adapter")
            print(f"     adapter:   OK ({contract})")
        else:
            print(f"     adapter:   ERROR ({adapter.get('error', 'unknown')})")

        mem = semantic_memory_boot_status()
        if mem.get("healthy"):
            summary = mem["status"].get("summary", {})
            print(f"     memory:    OK (read-only semantic hook, cycles={summary.get('cycles', 0)})")
        else:
            print(f"     memory:    ERROR ({mem.get('error', 'unknown')})")

        code = code_structure_boot_status()
        if code.get("healthy"):
            summary = code["status"].get("summary", {})
            print(f"     code:      OK (read-only AST hook, modules={summary.get('modules', 0)}, functions={summary.get('functions', 0)})")
        else:
            print(f"     code:      ERROR ({code.get('error', 'unknown')})")

        nexus = nexus_snapshot_boot_status()
        if nexus.get("healthy"):
            summary = nexus["status"].get("summary", {})
            sections = ",".join(summary.get("sections_available", []))
            print(f"     nexus:     OK (unified snapshot, sections={sections})")
        else:
            print(f"     nexus:     ERROR ({nexus.get('error', 'unknown')})")

        reflection = reflection_boot_status()
        if reflection.get("healthy"):
            score = reflection["status"].get("overall_relevance_score", 0.0)
            weak = ",".join(reflection["status"].get("missing_or_weak_sections", [])) or "none"
            print(f"     reflect:   OK (snapshot critique, score={score}, weak={weak})")
        else:
            print(f"     reflect:   ERROR ({reflection.get('error', 'unknown')})")

        intelligent = intelligent_context_boot_status()
        if intelligent.get("healthy"):
            status = intelligent["status"]
            sections = ",".join(status.get("ranked_sections", []))
            print(f"     context:   OK (guarded NEXUS bridge, quality={status.get('overall_quality_score')}, sections={sections})")
        else:
            print(f"     context:   ERROR ({intelligent.get('error', 'unknown')})")

        causal = causal_temporal_boot_status()
        if causal.get("healthy"):
            status = causal["status"]
            print(f"     causal:    OK (proposal-only, candidates={status.get('candidate_count')}, routes={status.get('pathfinder_routes')}, pathways={status.get('pathway_count')}, merge_safe={status.get('merge_safe')}, suggest={status.get('can_suggest_reorganization')})")
        else:
            print(f"     causal:    ERROR ({causal.get('error', 'unknown')})")

        commander = commander_pathway_boot_status()
        if commander.get("healthy"):
            status = commander["status"]
            print(f"     command:   OK (single-entry, steps={status.get('step_count')}, routes={status.get('route_count')}, failures={status.get('failure_prediction_count')}, merge_safe={status.get('merge_safe')})")
        else:
            print(f"     command:   ERROR ({commander.get('error', 'unknown')})")

        # Active path self-diagnosis (the v29 ask)
        diag = diagnose_paths()
        if diag["severity"] == "warning":
            print(f"\n  [!] Path check: needs attention")
            for f in diag["findings"]:
                print(f"     {f}")
        else:
            print(f"\n  Path check: OK "
                  f"({diag['centralized']} files centralized, "
                  f"{diag['pending']} pending, non-blocking)")
            for f in diag["findings"]:
                print(f"     note: {f}")

    if not semantic_core_status().get("healthy", False):
        print("\n  [!] Cannot start cleanly -- semantic core failed to initialize.")
        return False, health

    if health["overall"] == "ERROR":
        print("\n  [!] Cannot start cleanly -- see the messages above.")
        return False, health

    return True, health


def show_menu():
    print("\n  What would you like to do?")
    print("     [1] Start the hub (web interface)")
    print("     [2] Open the daily menu (launcher)")
    print("     [3] Run the health check again")
    print("     [4] Show path-migration status")
    print("     [Q] Quit")
    print()
    try:
        choice = input("  Choice: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "q"
    return choice


def main():
    ok, _ = boot_checks(verbose=True)
    if not ok:
        print("\n  Press Enter to close.")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        return 1

    print("\n  System healthy and ready.")

    # Interactive menu only if we have a real terminal; otherwise print guidance.
    if not sys.stdin or not sys.stdin.isatty():
        print("\n  To use the system:")
        print("     - RUN_ME.bat        (daily menu)")
        print("     - START_HERE.bat    (first-time setup)")
        print("     - python app/main.py  (hub directly)")
        return 0

    while True:
        choice = show_menu()
        if choice in ("q", ""):
            print("  Goodbye.")
            return 0
        elif choice == "1":
            print("\n  Starting hub... (Ctrl+C to stop)")
            import subprocess
            subprocess.run([sys.executable, str(ROOT / "app" / "main.py")])
        elif choice == "2":
            import subprocess
            subprocess.run([sys.executable, str(ROOT / "launcher.py")])
        elif choice == "3":
            boot_checks(verbose=True)
        elif choice == "4":
            mig = migration_report()
            print(f"\n  Path migration: {mig['migrated_count']} centralized, "
                  f"{mig['pending_count']} still pending (non-blocking).")
        else:
            print("  Didn't recognize that -- please pick from the list.")


if __name__ == "__main__":
    sys.exit(main())
