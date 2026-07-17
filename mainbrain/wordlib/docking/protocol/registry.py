"""Read-only SpecRegistry helpers for NEUROFORGE Docking Protocol v1.1."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from core.contracts.spec_protocol import SPEC_REGISTRY_CONTRACT, SpecRegistry, SpecRegistryEntry, normalize_status

DOCKING_REGISTRY_VERSION = "neuroforge.docking.registry.v1.1"


def load_registry(path: Path) -> Dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return data


def validate_registry_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[Dict[str, str]] = []
    if not isinstance(data, dict):
        return {"ok": False, "error": "registry payload must be a dictionary", "issues": [{"field": "payload", "message": "must be a dictionary"}]}
    if data.get("contract") != SPEC_REGISTRY_CONTRACT:
        issues.append({"field": "contract", "message": f"must be {SPEC_REGISTRY_CONTRACT}"})
    entries = data.get("specs", [])
    if not isinstance(entries, list):
        issues.append({"field": "specs", "message": "must be a list"})
        entries = []
    ids: List[str] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append({"field": f"specs[{idx}]", "message": "entry must be a dictionary"})
            continue
        for field in ("spec_id", "version", "status", "path"):
            if not isinstance(entry.get(field), str) or not entry.get(field, "").strip():
                issues.append({"field": f"specs[{idx}].{field}", "message": "must be a non-empty string"})
        if isinstance(entry.get("spec_id"), str):
            ids.append(entry["spec_id"])
        if isinstance(entry.get("status"), str):
            entry_status = normalize_status(entry["status"])
            if entry_status not in {"draft", "accepted", "implemented", "verified", "superseded", "rejected"}:
                issues.append({"field": f"specs[{idx}].status", "message": "invalid lifecycle status"})
    duplicates = sorted({spec_id for spec_id in ids if ids.count(spec_id) > 1})
    if duplicates:
        issues.append({"field": "specs", "message": f"duplicate spec ids: {duplicates}"})
    return {
        "ok": not issues,
        "contract": DOCKING_REGISTRY_VERSION,
        "registry_contract": data.get("contract"),
        "registered_specs": len(entries),
        "duplicates": duplicates,
        "issues": issues,
        "entries": entries,
    }


def empty_registry() -> SpecRegistry:
    return SpecRegistry(project="NEUROFORGE", entries=[])
