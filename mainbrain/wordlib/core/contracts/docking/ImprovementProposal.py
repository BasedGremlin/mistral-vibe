"""Strict NEUROFORGE closed-loop improvement proposal contracts.

These contracts describe proposed improvements that may be submitted to the
Docking CNS closed-loop pipeline.  They are intentionally data-only: the
pipeline decides whether the proposal can be tested, whether human approval is
required, and whether the guarded SelfEditor call path may be reached.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IMPROVEMENT_PROPOSAL_CONTRACT = "neuroforge.contracts.docking.ImprovementProposal.v1.1"
CRITIQUE_CONTRACT = "neuroforge.contracts.docking.Critique.v1.0"

# SPEC-CRYPTOGRAPHIC_BINDING: content hash format for proposal_content_hash.
# Only the full 64-hex format is accepted — none-new-file is a file-existence
# marker, not a content digest.
_CONTENT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ALLOWED_ACTION_TYPES = {
    "refactor",
    "add_test",
    "strengthen_validation",
    "improve_matching",
    "documentation",
    "safety_gate",
    "audit",
}
_REQUIRED_ACTION_KEYS = {"type", "target", "description", "priority"}


class Critique(BaseModel):
    """Strict critique carrier used to seed future ImprovementProposal objects.

    Attributes:
        source: Origin of the critique, such as a SideLetter or future review
            layer.
        summary: Human-readable critique summary.
        severity: Severity score constrained to 0.0-1.0.
        target_modules: Project modules or files affected by the critique.
        recommendations: Concrete follow-up recommendations.
        contract: Stable contract marker.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    source: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    severity: float = Field(..., ge=0.0, le=1.0)
    target_modules: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    contract: str = CRITIQUE_CONTRACT

    @field_validator("target_modules", "recommendations")
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


class ImprovementProposal(BaseModel):
    """Strict proposal submitted to the closed-loop improvement pipeline.

    Attributes:
        proposal_id: Stable identifier assigned by the pipeline. Callers may
            omit it when submitting; the pipeline will derive one.
        severity: Impact or risk score constrained to 0.0-1.0.
        priority: Scheduling priority constrained to 0.0-1.0.
        target_modules: Files or modules affected by the proposal.
        target_functions: Functions affected by the proposal.
        description: Concrete description of the intended improvement.
        expected_outcome: Verifiable outcome expected after implementation.
        source_sideletter_id: Optional SideLetter identifier/spec ID origin.
        proposed_actions: Lightweight actions imported from SideLetters.
        contract: Stable contract marker.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    proposal_id: Optional[str] = None
    severity: float = Field(..., ge=0.0, le=1.0)
    priority: float = Field(..., ge=0.0, le=1.0)
    target_modules: List[str] = Field(..., min_length=1)
    target_functions: List[str] = Field(default_factory=list)
    description: str = Field(..., min_length=1)
    expected_outcome: str = Field(..., min_length=1)
    source_sideletter_id: Optional[str] = None
    proposed_actions: List[Dict[str, Any]] = Field(default_factory=list)
    # SPEC-CRYPTOGRAPHIC_BINDING: canonical patch digest at proposal time.
    # When present, the pipeline copies this into ImprovementRecord.tested_patch_digest
    # and apply_patch_payload() verifies it equals patch_payload_hash.
    # Format: sha256:<64 lowercase hex chars>
    proposal_content_hash: Optional[str] = None
    contract: str = IMPROVEMENT_PROPOSAL_CONTRACT

    @field_validator("target_modules", "target_functions")
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

    @field_validator("proposal_content_hash")
    @classmethod
    def _content_hash_format(cls, value: Optional[str]) -> Optional[str]:
        """When provided, must be sha256:<64 lowercase hex chars>."""
        if value is None:
            return None
        cleaned = value.strip().lower()
        if not _CONTENT_HASH_RE.match(cleaned):
            raise ValueError(
                "proposal_content_hash must be sha256:<64 lowercase hex chars> when provided"
            )
        return cleaned

    @model_validator(mode="after")
    def _validate_proposed_actions(self) -> "ImprovementProposal":
        """Validate lightweight action dictionaries without executing them."""
        for index, action in enumerate(self.proposed_actions):
            if not isinstance(action, dict):
                raise TypeError(f"proposed_actions[{index}] must be a dictionary")
            missing = sorted(_REQUIRED_ACTION_KEYS.difference(action.keys()))
            if missing:
                raise ValueError(f"proposed_actions[{index}] missing required keys: {', '.join(missing)}")
            action_type = str(action.get("type", "")).strip()
            if action_type not in _ALLOWED_ACTION_TYPES:
                raise ValueError(f"proposed_actions[{index}].type is not allowed: {action_type}")
            for key in ("target", "description"):
                if not isinstance(action.get(key), str) or not str(action.get(key)).strip():
                    raise ValueError(f"proposed_actions[{index}].{key} must be a non-empty string")
            priority = action.get("priority")
            if not isinstance(priority, (int, float)) or isinstance(priority, bool):
                raise ValueError(f"proposed_actions[{index}].priority must be numeric")
            if float(priority) < 0.0 or float(priority) > 1.0:
                raise ValueError(f"proposed_actions[{index}].priority must be between 0.0 and 1.0")
            action["priority"] = float(priority)
        return self


__all__ = [
    "CRITIQUE_CONTRACT",
    "IMPROVEMENT_PROPOSAL_CONTRACT",
    "Critique",
    "ImprovementProposal",
]
