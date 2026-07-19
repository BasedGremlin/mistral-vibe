#!/usr/bin/env python3
"""Fixture-aware WORDLIB/NEUROFORGE test runner.

The historical runner called test functions directly and could not satisfy
pytest fixtures such as ``tmp_path`` and ``monkeypatch``.  The suite now uses
pytest as the authoritative runner.  Plugin autoload is disabled to avoid
third-party plugin shutdown hangs in portable/sandbox environments.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROUPS = [
    [
        "tests/test_accessibility.py",
        "tests/test_causal_temporal_proposals.py",
        "tests/test_closed_loop_improvement.py",
        "tests/test_code_structure_hook.py",
        "tests/test_commander_pathway.py",
    ],
    [
        "tests/test_deployment_and_agents.py",
        "tests/test_dispatch_agent.py",
        "tests/test_docking_protocol.py",
        "tests/test_evolution.py",
        "tests/test_intelligent_context.py",
        "tests/test_local_ontology_and_rag_hook.py",
    ],
    [
        "tests/test_market_and_gremlin.py",
        "tests/test_memory_semantic_hook.py",
        "tests/test_meta_evolution.py",
        "tests/test_nexus_reflection.py",
        "tests/test_nexus_snapshot.py",
    ],
    [
        "tests/test_patch_payload.py",
        "tests/test_paths_and_healer.py",
        "tests/test_reasoning.py",
        "tests/test_self_editor.py",
        "tests/test_semantic_adapter.py",
        "tests/test_semantic_core.py",
        "tests/test_sideletter_protocol.py",
    ],
]


def main() -> int:
    """Run pytest in stable groups and return a process status code."""
    env = dict(os.environ)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    print("=" * 60, flush=True)
    print("  WORDLIB / NEUROFORGE Test Suite", flush=True)
    print("=" * 60, flush=True)
    failed = []
    for index, group in enumerate(GROUPS, start=1):
        print(f"\n  Group {index}: pytest -q {' '.join(group)}", flush=True)
        command = "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q " + " ".join(group)
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            shell=True,
            timeout=180,
        )
        if completed.returncode != 0:
            failed.append(index)
    print("\n" + "=" * 60, flush=True)
    if failed:
        print(f"  FAILED GROUPS: {failed}", flush=True)
        print("=" * 60, flush=True)
        return 1
    print("  ALL GROUPS GREEN", flush=True)
    print("=" * 60, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
