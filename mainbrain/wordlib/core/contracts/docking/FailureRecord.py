"""Strict NEUROFORGE FailureRecord contract.

Failure Memory is the Central Nervous System's persistent learning surface for
blocked or failed specifications.  Every recorded failure is structured,
queryable, and validated before it reaches ``docking/memory/failure_log.jsonl``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, field_validator

FAILURE_RECORD_MODEL_CONTRACT = "neuroforge.contracts.docking.FailureRecord.v1.2"


class FailureRecord(BaseModel):
    """Persistent validation failure record.

    Attributes:
        spec_id: Specification identifier associated with the failed gate.
        failure_category: Stable machine-readable failure class.
        reason: Human-readable reason for the failure.
        issues: Structured validation issues that caused or describe failure.
        timestamp: ISO-8601 timestamp for the recorded failure.
        validator_version: Validator version that produced the failure.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    spec_id: str = Field(..., min_length=1)
    failure_category: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: str = Field(..., min_length=1)
    validator_version: str = Field(..., min_length=1)
    contract: str = FAILURE_RECORD_MODEL_CONTRACT

    @field_validator("timestamp")
    @classmethod
    def _valid_iso_timestamp(cls, value: str) -> str:
        """Require an ISO-8601 parseable timestamp."""
        candidate = value.replace("Z", "+00:00")
        try:
            datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError("timestamp must be ISO-8601 parseable") from exc
        return value

    @field_validator("failure_category")
    @classmethod
    def _safe_category(cls, value: str) -> str:
        """Require a compact stable category token."""
        normalized = value.strip().lower().replace(" ", "_")
        if not normalized:
            raise ValueError("failure_category must not be empty")
        if any(ch in normalized for ch in "/\\"):
            raise ValueError("failure_category must be a simple token")
        return normalized


__all__ = ["FAILURE_RECORD_MODEL_CONTRACT", "FailureRecord"]
