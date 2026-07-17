"""Read-only audit helpers for NEUROFORGE Docking Protocol v1.1."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

DOCKING_AUDITOR_VERSION = "neuroforge.docking.auditor.v1.1"


def audit_protocol_layout(paths: Dict[str, Path]) -> Dict[str, Any]:
    required_dirs = ["docking", "specs", "reports", "contracts", "registry", "protocol", "audit"]
    dirs = {name: paths[name].is_dir() for name in required_dirs if name in paths}
    required_files = {
        "spec_template": paths["spec_template"].is_file(),
        "registry_file": paths["registry_file"].is_file(),
        "core_contract": (paths["root"] / "core" / "contracts" / "spec_protocol.py").is_file(),
        "validator": (paths["protocol"] / "validator.py").is_file(),
        "lifecycle": (paths["protocol"] / "lifecycle.py").is_file(),
        "auditor": (paths["protocol"] / "auditor.py").is_file(),
        "registry_module": (paths["protocol"] / "registry.py").is_file(),
    }
    return {
        "ok": all(dirs.values()) and all(required_files.values()),
        "contract": DOCKING_AUDITOR_VERSION,
        "dirs": dirs,
        "required_files": required_files,
    }
