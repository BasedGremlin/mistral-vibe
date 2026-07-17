"""
Self-healing / repair logic. Each function detects a specific broken state
and fixes it. All are idempotent and safe to call when nothing is wrong.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


class Repairer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.is_windows = sys.platform.startswith("win")
        self.venv = root / ".venv"

    def venv_python(self) -> Path:
        return self.venv / ("Scripts/python.exe" if self.is_windows else "bin/python")

    # ── Detectors + fixers ──────────────────────────────────────────────────

    def repair_broken_venv(self) -> Tuple[bool, str]:
        """A venv folder exists but its python is missing -> remove it for rebuild."""
        if self.venv.exists() and not self.venv_python().exists():
            try:
                shutil.rmtree(self.venv)
                return True, "removed broken venv (will rebuild)"
            except Exception as e:
                return False, f"could not remove broken venv: {e}"
        return False, "venv ok"

    def repair_stale_cache(self) -> Tuple[bool, str]:
        """Remove __pycache__ dirs that may hold bytecode from an older version."""
        count = 0
        for pyc in self.root.rglob("__pycache__"):
            try:
                shutil.rmtree(pyc); count += 1
            except Exception:
                pass
        return (count > 0), f"cleared {count} bytecode cache(s)"

    def repair_corrupt_rag_index(self) -> Tuple[bool, str]:
        """
        Detect a corrupt ChromaDB index (folder exists but unreadable) and clear it
        so it rebuilds cleanly. We only remove the index, never source content.
        """
        index_dir = self.root / "storage" / "rag_index"
        if not index_dir.exists():
            return False, "no index yet"
        try:
            # A valid chroma dir has a sqlite file; if missing but dir non-empty, suspect
            has_sqlite = any(index_dir.glob("*.sqlite3")) or any(index_dir.glob("chroma.sqlite3"))
            has_files  = any(index_dir.iterdir())
            if has_files and not has_sqlite:
                shutil.rmtree(index_dir)
                index_dir.mkdir(parents=True, exist_ok=True)
                return True, "cleared corrupt RAG index (will rebuild)"
        except Exception as e:
            return False, f"index check failed: {e}"
        return False, "index ok"

    def repair_missing_dirs(self) -> Tuple[bool, str]:
        """Recreate expected working dirs if missing."""
        created = []
        for d in ("data", "logs", "backups", "storage", "models",
                  "core", "core/ollama/models"):
            p = self.root / d
            if not p.exists():
                try:
                    p.mkdir(parents=True, exist_ok=True); created.append(d)
                except Exception:
                    pass
        return (len(created) > 0), (f"created {created}" if created else "dirs ok")

    def repair_stale_processes(self) -> Tuple[bool, str]:
        """
        On Windows, detect orphaned python processes holding our ports from a
        previous session. We report rather than force-kill, to avoid killing
        unrelated python. Returns advisory only.
        """
        import socket
        stuck = []
        for port in (5757, 11434):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    stuck.append(port)
        if stuck:
            return False, f"ports {stuck} already in use (likely a running session)"
        return False, "no stale processes"

    # ── Run all ──────────────────────────────────────────────────────────────

    def run_all(self) -> List[Tuple[str, bool, str]]:
        """Run every repair, return [(name, did_fix, detail), ...]."""
        checks = [
            ("missing dirs",    self.repair_missing_dirs),
            ("broken venv",     self.repair_broken_venv),
            ("stale cache",     self.repair_stale_cache),
            ("corrupt index",   self.repair_corrupt_rag_index),
            ("stale processes", self.repair_stale_processes),
        ]
        results = []
        for name, fn in checks:
            try:
                fixed, detail = fn()
            except Exception as e:
                fixed, detail = False, f"repair error: {e}"
            results.append((name, fixed, detail))
        return results
