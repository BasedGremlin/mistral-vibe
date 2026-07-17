"""Strict NEUROFORGE ChangeTrace contract.

This module defines the first-class file-level audit record used by the
Docking Protocol.  It is intentionally small, strict, and dependency-limited
so it can run before higher-level infrastructure exists.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CHANGE_TRACE_MODEL_CONTRACT = "neuroforge.contracts.docking.ChangeTrace.v1.2"
ChangeAction = Literal["created", "modified", "deleted"]


class ChangeTrace(BaseModel):
    """File-level change record required for implementation reports.

    Attributes:
        file_path: Project-relative path of the affected file.
        spec_id: Specification that authorized the change.
        action: File action: created, modified, or deleted.
        reason: Concrete reason this file changed.
        timestamp: ISO-8601 timestamp for trace creation.
        previous_hash: Previous content hash, or an explicit sentinel such as
            ``sha256:none-new-file`` for newly-created files.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    file_path: str = Field(..., min_length=1)
    spec_id: str = Field(..., min_length=1)
    action: ChangeAction
    reason: str = Field(..., min_length=1)
    timestamp: str = Field(..., min_length=1)
    previous_hash: str = Field(..., min_length=1)
    contract: str = CHANGE_TRACE_MODEL_CONTRACT

    @field_validator("file_path")
    @classmethod
    def _project_relative_path(cls, value: str) -> str:
        """Reject absolute paths and parent traversal in traces."""
        normalized = value.replace("\\", "/").strip()
        if normalized.startswith("/") or ":/" in normalized or normalized.startswith("../") or "/../" in normalized:
            raise ValueError("file_path must be project-relative and must not contain parent traversal")
        return normalized

    @field_validator("timestamp")
    @classmethod
    def _valid_iso_timestamp(cls, value: str) -> str:
        """Require an ISO-8601-like timestamp."""
        candidate = value.replace("Z", "+00:00")
        try:
            datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError("timestamp must be ISO-8601 parseable") from exc
        return value

    @field_validator("previous_hash")
    @classmethod
    def _hash_marker(cls, value: str) -> str:
        """Require explicit hash provenance for rollback traceability."""
        if not (value.startswith("sha256:") or value == "unknown-preexisting"):
            raise ValueError("previous_hash must start with 'sha256:' or be 'unknown-preexisting'")
        return value


__all__ = ["CHANGE_TRACE_MODEL_CONTRACT", "ChangeAction", "ChangeTrace"]
