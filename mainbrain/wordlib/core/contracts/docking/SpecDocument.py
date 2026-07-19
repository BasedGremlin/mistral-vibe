"""Strict NEUROFORGE SpecDocument contract.

The Docking Protocol treats specifications as executable governance.  This
module supplies Pydantic v2 models with ``extra='forbid'`` so malformed or
ambiguous specifications are rejected before implementation begins.
"""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SPEC_DOCUMENT_MODEL_CONTRACT = "neuroforge.contracts.docking.SpecDocument.v1.2"
SpecStatus = Literal["draft", "accepted", "implemented", "verified", "superseded", "rejected"]


class SpecMeta(BaseModel):
    """Metadata block for a NEUROFORGE specification."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    spec_id: str = Field(..., min_length=1)
    protocol_version: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    date: str = Field(..., min_length=1)
    author: str = Field(..., min_length=1)
    status: SpecStatus


class SpecTarget(BaseModel):
    """Allowed implementation surface declared by a spec."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    modules: List[str] = Field(default_factory=list)
    allowed_files: List[str] = Field(default_factory=list)
    forbidden_files: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_file_rules(self) -> "SpecTarget":
        """Require explicit allow/forbid boundaries."""
        if not self.allowed_files:
            raise ValueError("target.allowed_files must not be empty")
        if not self.forbidden_files:
            raise ValueError("target.forbidden_files must not be empty")
        return self


class SpecRelationships(BaseModel):
    """Dependency and supersession relationships."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    dependencies: List[str] = Field(default_factory=list)
    supersedes: List[str] = Field(default_factory=list)


class ContractReference(BaseModel):
    """Reference to a contract file affected by the spec."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    ref: str = Field(..., min_length=1)


class AcceptanceCriterion(BaseModel):
    """Machine-verifiable acceptance criterion."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    verification: str = Field(..., min_length=1)


class SpecDefinition(BaseModel):
    """Implementation requirements and verification definition."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    contracts: List[ContractReference] = Field(default_factory=list)
    implementation_requirements: List[str] = Field(default_factory=list)
    acceptance_criteria: List[AcceptanceCriterion] = Field(default_factory=list)
    rollback_expectations: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _require_verifiable_definition(self) -> "SpecDefinition":
        """Require the spec to define contracts, requirements, and criteria."""
        if not self.contracts:
            raise ValueError("definition.contracts must not be empty")
        if not self.implementation_requirements:
            raise ValueError("definition.implementation_requirements must not be empty")
        if not self.acceptance_criteria:
            raise ValueError("definition.acceptance_criteria must not be empty")
        return self


class SpecImpact(BaseModel):
    """Deployment impact and risks declared by a spec."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    deploy: str = Field(..., min_length=1)
    risks: str = Field(..., min_length=1)


class SpecDocument(BaseModel):
    """Strict top-level NEUROFORGE specification contract."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    meta: SpecMeta
    mission: str = Field(..., min_length=1)
    scope: str = Field(..., min_length=1)
    non_goals: str = Field(..., min_length=1)
    target: SpecTarget
    relationships: SpecRelationships = Field(default_factory=SpecRelationships)
    definition: SpecDefinition
    impact: SpecImpact
    contract: str = SPEC_DOCUMENT_MODEL_CONTRACT

    @field_validator("mission", "scope", "non_goals")
    @classmethod
    def _substantive_text(cls, value: str) -> str:
        """Reject placeholder-level text blocks."""
        text = value.strip()
        if len(text) < 10:
            raise ValueError("text block is too short to be a substantive specification field")
        return text

    @model_validator(mode="after")
    def _accepted_specs_need_verification(self) -> "SpecDocument":
        """Accepted specs must contain machine-verifiable acceptance criteria."""
        if self.meta.status == "accepted":
            for criterion in self.definition.acceptance_criteria:
                if not criterion.verification.strip():
                    raise ValueError("accepted specs require verification text on every acceptance criterion")
        return self


__all__ = [
    "SPEC_DOCUMENT_MODEL_CONTRACT",
    "SpecStatus",
    "SpecMeta",
    "SpecTarget",
    "SpecRelationships",
    "ContractReference",
    "AcceptanceCriterion",
    "SpecDefinition",
    "SpecImpact",
    "SpecDocument",
]
