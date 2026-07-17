"""Strict NEUROFORGE improvement test/result history contracts."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.contracts.docking.ImprovementProposal import ImprovementProposal

TEST_SUITE_RESULT_CONTRACT = "neuroforge.contracts.docking.TestSuiteResult.v1.0"
IMPROVEMENT_RECORD_CONTRACT = "neuroforge.contracts.docking.ImprovementRecord.v1.1"
_ALLOWED_STATES = {"proposed", "tested", "human_approval", "applied", "rejected"}

# SPEC-CRYPTOGRAPHIC_BINDING: content hash format shared with ImprovementProposal
_CONTENT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class TestSuiteResult(BaseModel):
    __test__ = False

    """Structured result returned by the fast targeted self-tester.

    Attributes:
        passed: True only when all selected tests completed successfully.
        duration: Wall-clock duration in seconds.
        selected_tests: Test files/functions selected by TestSelector.
        failing_tests: Failing tests or deterministic failure reasons.
        timed_out: Whether the subprocess timed out.
        coverage_delta: Optional coverage delta if available.
        command: Exact command used for test execution.
        resource_limits: Timeout/concurrency/memory guard settings.
        contract: Stable contract marker.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    passed: bool
    duration: float = Field(..., ge=0.0)
    selected_tests: List[str] = Field(default_factory=list)
    failing_tests: List[str] = Field(default_factory=list)
    timed_out: bool = False
    coverage_delta: Optional[float] = None
    command: List[str] = Field(default_factory=list)
    resource_limits: Dict[str, Any] = Field(default_factory=dict)
    contract: str = TEST_SUITE_RESULT_CONTRACT

    @field_validator("selected_tests", "failing_tests", "command")
    @classmethod
    def _clean_string_lists(cls, value: List[str]) -> List[str]:
        """Normalize string-list fields and reject non-string items."""
        cleaned: List[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TypeError("list entries must be strings")
            text = item.strip()
            if text:
                cleaned.append(text)
        return cleaned


class ImprovementRecord(BaseModel):
    """Full auditable history record for one improvement transition.

    Attributes:
        record_id: Stable identifier for this transition record.
        proposal_id: Proposal identifier this record belongs to.
        state: Current state after the transition.
        transition: Human-readable transition that produced this record.
        proposal: Strict ImprovementProposal snapshot.
        test_result: Optional TestSuiteResult snapshot.
        applied: True only when the guarded apply path has been reached.
        rollback_info: Rollback or apply-path information.
        failure_references: Failure Memory records related to this attempt.
        timestamp: UTC timestamp for this record.
        change_traces: ChangeTrace dictionaries associated with transition.
        audit_event: Structured audit payload for this transition.
        human_approval_required: Whether human approval blocks applying.
        self_editor_gate: Guard status for SelfEditor access.
        contract: Stable contract marker.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    record_id: str = Field(..., min_length=1)
    proposal_id: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    transition: str = Field(..., min_length=1)
    proposal: ImprovementProposal
    test_result: Optional[TestSuiteResult] = None
    applied: bool = False
    rollback_info: Dict[str, Any] = Field(default_factory=dict)
    failure_references: List[str] = Field(default_factory=list)
    timestamp: datetime
    change_traces: List[Dict[str, Any]] = Field(default_factory=list)
    audit_event: Dict[str, Any] = Field(default_factory=dict)
    human_approval_required: bool = False
    self_editor_gate: Dict[str, Any] = Field(default_factory=dict)
    # SPEC-CRYPTOGRAPHIC_BINDING: digest of the patch content that was actually
    # tested by the fast targeted tester.  Set by the pipeline from
    # proposal.proposal_content_hash at test time.  apply_patch_payload() verifies
    # this equals patch_payload_hash before SelfEditor is reachable.
    # Format: sha256:<64 lowercase hex chars>
    tested_patch_digest: Optional[str] = None
    contract: str = IMPROVEMENT_RECORD_CONTRACT

    @field_validator("state")
    @classmethod
    def _state_allowed(cls, value: str) -> str:
        """Reject unknown pipeline states."""
        cleaned = value.strip()
        if cleaned not in _ALLOWED_STATES:
            raise ValueError(f"state must be one of {sorted(_ALLOWED_STATES)}")
        return cleaned

    @field_validator("failure_references")
    @classmethod
    def _clean_failure_references(cls, value: List[str]) -> List[str]:
        """Normalize failure reference entries."""
        return [str(item).strip() for item in value if str(item).strip()]

    @field_validator("tested_patch_digest")
    @classmethod
    def _digest_format(cls, value: Optional[str]) -> Optional[str]:
        """When provided, must be sha256:<64 lowercase hex chars>."""
        if value is None:
            return None
        cleaned = value.strip().lower()
        if not _CONTENT_HASH_RE.match(cleaned):
            raise ValueError(
                "tested_patch_digest must be sha256:<64 lowercase hex chars> when provided"
            )
        return cleaned


__all__ = [
    "TEST_SUITE_RESULT_CONTRACT",
    "IMPROVEMENT_RECORD_CONTRACT",
    "TestSuiteResult",
    "ImprovementRecord",
]
