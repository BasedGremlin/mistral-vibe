"""Persistent Failure Memory for the NEUROFORGE Docking CNS.

This module records validation failures in structured JSONL so the pre-
implementation gate can learn from blocked or malformed specifications.  The
query functions are read-only; only ``log_spec_failure`` appends to disk.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.contracts.docking.FailureRecord import FailureRecord

FAILURE_MEMORY_CONTRACT = "neuroforge.docking.failure_memory.v1.2"
FAILURE_LOG_FILE = "failure_log.jsonl"


def _repo_root(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Resolve the project root for failure-memory storage."""
    if project_root is not None:
        return Path(project_root).resolve()
    return Path(__file__).resolve().parents[2]


def failure_log_path(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Return the project-local Failure Memory JSONL path."""
    return _repo_root(project_root) / "docking" / "memory" / FAILURE_LOG_FILE


def _utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def log_spec_failure(
    spec_id: str,
    failure_category: str,
    reason: str,
    issues: List[Dict[str, Any]],
    timestamp: Optional[str] = None,
    *,
    validator_version: str = "neuroforge.docking.cns.validator.v1.2",
    project_root: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Persist a structured FailureRecord to Failure Memory.

    Args:
        spec_id: Specification identifier associated with the failed gate.
        failure_category: Stable failure class such as ``missing_meta``.
        reason: Human-readable failure reason.
        issues: Structured validation issue dictionaries.
        timestamp: Optional ISO timestamp. If omitted, UTC now is used.
        validator_version: Version of the validator producing the failure.
        project_root: Optional repository root override used by tests.

    Returns:
        The validated FailureRecord as a plain dictionary.

    Raises:
        pydantic.ValidationError: If the record is malformed.
        OSError: If the log cannot be written.
    """
    record = FailureRecord(
        spec_id=spec_id or "UNKNOWN",
        failure_category=failure_category,
        reason=reason,
        issues=issues or [],
        timestamp=timestamp or _utc_now(),
        validator_version=validator_version,
    )
    path = failure_log_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.model_dump(), sort_keys=True, default=str) + "\n")
    return record.model_dump()


def _read_failure_records(project_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Read all valid failure records from JSONL without mutating state."""
    path = failure_log_path(project_root)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [{"status": "error", "error": f"{type(exc).__name__}: {exc}"}]
    records: List[Dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            records.append(FailureRecord.model_validate(payload).model_dump())
        except (json.JSONDecodeError, ValueError) as exc:
            records.append({"status": "malformed", "error": str(exc), "raw": line})
    return records


def get_recent_failures(limit: int = 20, *, project_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Return the most recent failure records without mutating state."""
    safe_limit = max(0, int(limit))
    if safe_limit == 0:
        return []
    return _read_failure_records(project_root)[-safe_limit:]


def get_failures_by_category(category: str, *, project_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Return all failure records matching a category token."""
    normalized = (category or "").strip().lower().replace(" ", "_")
    if not normalized:
        return []
    return [record for record in _read_failure_records(project_root) if record.get("failure_category") == normalized]


def failure_memory_status(*, project_root: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Return read-only Failure Memory health and summary."""
    path = failure_log_path(project_root)
    records = get_recent_failures(20, project_root=project_root)
    categories = sorted({str(record.get("failure_category")) for record in records if record.get("failure_category")})
    return {
        "ok": path.parent.exists(),
        "contract": FAILURE_MEMORY_CONTRACT,
        "read_only": True,
        "failure_log": str(path),
        "recent_count": len(records),
        "categories": categories,
        "recent_failures": records[-10:],
        "error": None if path.parent.exists() else "docking/memory directory missing",
    }


__all__ = [
    "FAILURE_MEMORY_CONTRACT",
    "FAILURE_LOG_FILE",
    "failure_log_path",
    "log_spec_failure",
    "get_recent_failures",
    "get_failures_by_category",
    "failure_memory_status",
]
