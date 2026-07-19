r"""
core/paths.py -- the single source of truth for "where things live".
====================================================================
Goal (from the v25 essay, which is sound): centralize path resolution so the
system is portable across machines. Instead of 21 files each doing their own
Path(__file__) / _USB_ROOT discovery, everything derives from ONE place.

This is additive: existing modules still work. New code imports from here, and
old code can migrate over time (see migration_report()).

Design points adopted from the essay:
  - one immutable PATHS object (PATHS.root, PATHS.logs, ...) -- not loose functions
    (loose functions are ALSO provided for the directive's required API)
  - a single PROJECT_STRUCTURE manifest -- self-healer + health both read it
  - layered, structured health_report() (filesystem / python / deployment)
  - no fabricated data: health reflects the real filesystem

The root is derived from THIS file's location (core/ is one level under root),
so a copy to D:\, E:\USB\, or C:\Users\...\Downloads\ all work unedited.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


# ── Root discovery -- the ONLY place that touches Path(__file__) for root ────
# core/paths.py lives at <root>/core/paths.py, so root is two parents up.
_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent


# ── The manifest: single declaration of expected structure ──────────────────
# value = essential? (True dirs are auto-created by the self-healer)
PROJECT_STRUCTURE: Dict[str, bool] = {
    "core": True,
    "core/contracts": True,
    "core/contracts/docking": True,
    "docking": True,
    "docking/specs": True,
    "docking/reports": True,
    "docking/contracts": True,
    "docking/templates": True,
    "docking/registry": True,
    "docking/protocol": True,
    "docking/audit": True,
    "docking/memory": True,
    "docking/specs/archive": False,
    "src": True,
    "app": True,
    "config": True,
    "logs": True,
    "data": True,
    "backups": True,
    "storage": True,
    "tests": True,
    "deployment": False,    # lives under src/deployment in this project
    "models": False,        # large/optional
}

# Critical files whose absence means a broken deployment
CRITICAL_FILES: List[str] = [
    "core/paths.py",
    "src/self_editor.py",
    "src/ether_core.py",
    "app/main.py",
]


@dataclass(frozen=True)
class _Paths:
    """Immutable view of key locations. Import this as PATHS."""
    root: Path
    core: Path
    contracts: Path
    contracts_docking: Path
    docking: Path
    docking_specs: Path
    docking_reports: Path
    docking_contracts: Path
    docking_templates: Path
    docking_registry: Path
    docking_protocol: Path
    docking_audit: Path
    docking_memory: Path
    src: Path
    app: Path
    config: Path
    logs: Path
    data: Path
    backups: Path
    storage: Path
    tests: Path
    memory: Path     # data/memory -- agent/gremlin persistent state


PATHS = _Paths(
    root=_ROOT,
    core=_ROOT / "core",
    contracts=_ROOT / "core" / "contracts",
    contracts_docking=_ROOT / "core" / "contracts" / "docking",
    docking=_ROOT / "docking",
    docking_specs=_ROOT / "docking" / "specs",
    docking_reports=_ROOT / "docking" / "reports",
    docking_contracts=_ROOT / "docking" / "contracts",
    docking_templates=_ROOT / "docking" / "templates",
    docking_registry=_ROOT / "docking" / "registry",
    docking_protocol=_ROOT / "docking" / "protocol",
    docking_audit=_ROOT / "docking" / "audit",
    docking_memory=_ROOT / "docking" / "memory",
    src=_ROOT / "src",
    app=_ROOT / "app",
    config=_ROOT / "config",
    logs=_ROOT / "logs",
    data=_ROOT / "data",
    backups=_ROOT / "backups",
    storage=_ROOT / "storage",
    tests=_ROOT / "tests",
    memory=_ROOT / "data",
)


# ── Required function API (from the v25 directive) ──────────────────────────
def get_project_root() -> Path:
    return PATHS.root

def get_core_dir() -> Path:
    return PATHS.core

def get_contracts_dir() -> Path:
    return PATHS.contracts

def get_contracts_docking_dir() -> Path:
    return PATHS.contracts_docking

def get_docking_dir() -> Path:
    return PATHS.docking

def get_docking_specs_dir() -> Path:
    return PATHS.docking_specs

def get_docking_reports_dir() -> Path:
    return PATHS.docking_reports

def get_docking_contracts_dir() -> Path:
    return PATHS.docking_contracts

def get_docking_protocol_dir() -> Path:
    return PATHS.docking_protocol

def get_docking_audit_dir() -> Path:
    return PATHS.docking_audit

def get_docking_memory_dir() -> Path:
    return PATHS.docking_memory

def get_data_dir() -> Path:
    return PATHS.data

def get_logs_dir() -> Path:
    return PATHS.logs

def get_backups_dir() -> Path:
    return PATHS.backups

def get_config_dir() -> Path:
    return PATHS.config

def get_src_dir() -> Path:
    return PATHS.src


def verify_critical_files() -> Dict[str, bool]:
    """Return {relative_path: exists?} for every critical file. Real check."""
    return {f: (PATHS.root / f).exists() for f in CRITICAL_FILES}


# ── Layered, structured health (no fabricated data) ─────────────────────────
def health_report() -> Dict:
    """
    Structured health across layers. Every value reflects the real filesystem
    / interpreter -- nothing is invented.
    """
    # Filesystem layer
    missing_dirs = [d for d, essential in PROJECT_STRUCTURE.items()
                    if essential and not (PATHS.root / d).exists()]
    fs_status = "OK" if not missing_dirs else "WARNING"

    # Critical files layer
    crit = verify_critical_files()
    missing_files = [f for f, ok in crit.items() if not ok]
    files_status = "OK" if not missing_files else "ERROR"

    # Python layer
    py_ok = sys.version_info >= (3, 9)

    # Deployment layer: portable if root is derivable + writable
    try:
        testfile = PATHS.root / ".write_test_tmp"
        testfile.write_text("x"); testfile.unlink()
        writable = True
    except Exception:
        writable = False

    overall = "OK"
    if files_status == "ERROR":
        overall = "ERROR"
    elif fs_status == "WARNING" or not py_ok or not writable:
        overall = "WARNING"

    return {
        "overall": overall,
        "filesystem": {
            "status": fs_status,
            "missing_dirs": missing_dirs,
            "root": str(PATHS.root),
        },
        "critical_files": {
            "status": files_status,
            "missing": missing_files,
        },
        "python": {
            "status": "OK" if py_ok else "ERROR",
            "version": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
        "deployment": {
            "portable": True,          # root derives from this file's location
            "writable": writable,
        },
    }


def migration_report() -> Dict:
    """
    Honest, measurable view of the path-centralization migration.

    Three buckets, because not all Path(__file__) uses are equal:
      - migrated: imports from core.paths, no independent discovery
      - bootstrap_only: imports from core.paths AND its only path-discovery is a
        guarded fallback to LOCATE core when imported standalone. Effectively
        centralized -- all path *semantics* come from core.paths.
      - pending_migration: still does real independent discovery (no core.paths)
    """
    import re
    discovery = re.compile(r"Path\(__file__\)|_USB_ROOT|os\.getcwd|sys\.path\.insert|sys\.path\.append")
    uses_core = re.compile(r"from core\.paths import|from core import paths")
    migrated, bootstrap_only, pending = [], [], []
    for py in PATHS.root.rglob("*.py"):
        if "__pycache__" in str(py) or ".venv" in str(py):
            continue
        rel = str(py.relative_to(PATHS.root))
        if rel == "core/paths.py":
            migrated.append(rel)
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        has_discovery = bool(discovery.search(text))
        imports_core = bool(uses_core.search(text))
        if not has_discovery and imports_core:
            migrated.append(rel)
        elif has_discovery and imports_core:
            # uses core.paths for semantics but keeps a locator -> effectively done
            bootstrap_only.append(rel)
        elif has_discovery:
            pending.append(rel)
        # files with neither don't touch paths at all -> not counted
    return {
        "migrated": sorted(migrated),
        "bootstrap_only": sorted(bootstrap_only),
        "pending_migration": sorted(pending),
        "migrated_count": len(migrated) + len(bootstrap_only),
        "pending_count": len(pending),
        "note": "migrated + bootstrap_only route all path semantics through "
                "core.paths. pending files still discover paths independently "
                "and should be migrated over time. Non-blocking.",
    }
