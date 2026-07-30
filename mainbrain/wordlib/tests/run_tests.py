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
        "tests/test_patch_sandbox.py",
        "tests/test_paths_and_healer.py",
        "tests/test_reasoning.py",
        "tests/test_reasoning_guard_and_judge.py",
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
    print(f"  Interpreter: {sys.executable}", flush=True)
    failed = []
    for index, group in enumerate(GROUPS, start=1):
        print(f"\n  Group {index}: pytest -q {' '.join(group)}", flush=True)
        # `sys.executable -m pytest`, not a bare `pytest` off PATH.
        #
        # This runner used to shell out to whatever `pytest` PATH resolved to,
        # independent of the interpreter running this file. That makes a green
        # result meaningless: run it from a venv whose deps you meant to test
        # and it would silently exercise some *other* environment instead --
        # observed for real as a `ModuleNotFoundError: pydantic` collection
        # error from an interpreter that had pydantic installed. Binding to
        # sys.executable makes the suite test the environment you actually
        # invoked it with, which is the only thing that makes "280 green"
        # a fact rather than a coincidence of PATH ordering.
        #
        # Passing env= instead of an inline `VAR=... ` prefix also means no
        # shell is involved, so test paths cannot be re-split or glob-expanded.
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *group],
            cwd=str(ROOT),
            env=env,
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
