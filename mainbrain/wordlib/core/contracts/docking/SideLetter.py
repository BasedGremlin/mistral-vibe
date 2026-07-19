"""Strict NEUROFORGE SideLetter contract.

A SideLetter is the formal Builder-to-Architect feedback artifact produced
when a SPEC implementation succeeds.  It compresses implementation lessons,
references relevant Failure Memory records, and may carry lightweight proposed
actions for future closed-loop self-improvement.  SideLetters are append-only
artifacts stored under ``docking/letters/``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SIDE_LETTER_MODEL_CONTRACT = "neuroforge.contracts.docking.SideLetter.v1.1"
_REQUIRED_ACTION_KEYS = {"type", "target", "description", "priority"}


class SideLetter(BaseModel):
    """Strict Builder-to-Architect SideLetter payload.

    Attributes:
        timestamp: UTC timestamp for when the SideLetter was created.
        spec_id: Specification identifier the letter is attached to.
        project_assessment: Substantive assessment of the implementation result.
        weaknesses: Known weaknesses or limitations after the implementation.
        architectural_debt: Architectural debt surfaced by the implementation.
        knowledge_compression: Compact lesson for Claude/Cloud handoff.
        recommendations: Concrete next-step recommendations.
        confidence: Confidence in the assessment, constrained to 0.0-1.0.
        referenced_failures: Failure Memory records referenced by ID/signature.
        failure_signatures: Extracted failure signatures used during matching.
        matched_modules: Module/path tokens involved in matching.
        proposed_actions: Lightweight carrier for future closed-loop proposals.
        contract: Contract marker for stable downstream validation.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    timestamp: datetime
    spec_id: str = Field(..., min_length=1)
    project_assessment: str = Field(..., min_length=1)
    weaknesses: List[str] = Field(default_factory=list)
    architectural_debt: List[str] = Field(default_factory=list)
    knowledge_compression: str = Field(..., min_length=1)
    recommendations: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    referenced_failures: List[str] = Field(default_factory=list)
    failure_signatures: List[str] = Field(default_factory=list)
    matched_modules: List[str] = Field(default_factory=list)
    proposed_actions: List[Dict[str, Any]] = Field(default_factory=list)
    contract: str = SIDE_LETTER_MODEL_CONTRACT

    @field_validator("weaknesses", "architectural_debt", "recommendations", "referenced_failures", "failure_signatures", "matched_modules")
    @classmethod
    def _strip_string_lists(cls, value: List[str]) -> List[str]:
        """Normalize list fields and reject non-string entries."""
        normalized: List[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TypeError("list entries must be strings")
            text = item.strip()
            if text:
                normalized.append(text)
        return normalized

    @model_validator(mode="after")
    def _validate_proposed_actions(self) -> "SideLetter":
        """Validate lightweight proposed action dictionaries.

        The closed-loop implementation is intentionally not implemented here.
        This validator only ensures that future actions are well formed
        enough for later SPECs to consume safely.
        """
        for index, action in enumerate(self.proposed_actions):
            if not isinstance(action, dict):
                raise TypeError(f"proposed_actions[{index}] must be a dictionary")
            missing = sorted(_REQUIRED_ACTION_KEYS.difference(action.keys()))
            if missing:
                raise ValueError(f"proposed_actions[{index}] missing required keys: {', '.join(missing)}")
            for key in ("type", "target", "description"):
                if not isinstance(action.get(key), str) or not str(action.get(key)).strip():
                    raise ValueError(f"proposed_actions[{index}].{key} must be a non-empty string")
            priority = action.get("priority")
            if not isinstance(priority, (int, float)) or isinstance(priority, bool):
                raise ValueError(f"proposed_actions[{index}].priority must be numeric")
            if float(priority) < 0.0 or float(priority) > 1.0:
                raise ValueError(f"proposed_actions[{index}].priority must be between 0.0 and 1.0")
            action["priority"] = float(priority)
        return self


__all__ = ["SIDE_LETTER_MODEL_CONTRACT", "SideLetter"]
