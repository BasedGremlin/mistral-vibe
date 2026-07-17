"""Strict NEUROFORGE PatchPayload contract for guarded SelfEditor applies."""
from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PATCH_PAYLOAD_CONTRACT = "neuroforge.contracts.docking.PatchPayload.v1.1"
_PATCH_ACTIONS = {"create", "patch", "append", "delete"}
_SHA_RE = re.compile(r"^sha256:([0-9a-f]{64}|none-new-file)$")
# SPEC-CRYPTOGRAPHIC_BINDING: content digest must be full 64-hex only.
# none-new-file is a file-existence marker, never a content digest.
_CONTENT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class PatchPayload(BaseModel):
    """Strict payload for a hash-checked, audited SelfEditor mutation.

    Attributes:
        patch_id: Stable patch identifier used for status queries.
        target_file: Project-root-relative target file. Absolute paths and
            parent traversal are rejected.
        action: Requested mutation action: create, patch, append, or delete.
        old_content: Existing content fragment required for patch actions.
        new_content: New content for create, patch, and append actions. Delete
            payloads may provide an empty string.
        expected_hash_before: SHA-256 marker for the file before apply. Existing
            files use ``sha256:<64 hex>``. Missing files use
            ``sha256:none-new-file``.
        reason: Human-readable justification for the mutation.
        linked_improvement_record_id: ImprovementRecord identifier that approved
            or motivated this patch.
        linked_sideletter_id: SideLetter identifier/spec ID that contributed to
            the improvement path.
        severity: Risk score constrained to 0.0-1.0.
        priority: Scheduling priority constrained to 0.0-1.0.
        proposed_by: Origin marker, defaulting to improvement_pipeline.
        human_approved: Explicit approval flag required for high severity or
            core/contracts targets before SelfEditor can be called.
        contract: Stable contract marker.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False, validate_assignment=True)

    patch_id: str = Field(..., min_length=1)
    target_file: str = Field(..., min_length=1)
    action: Literal["create", "patch", "append", "delete"]
    old_content: Optional[str] = None
    new_content: str
    expected_hash_before: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    linked_improvement_record_id: str = Field(..., min_length=1)
    linked_sideletter_id: str = Field(..., min_length=1)
    severity: float = Field(..., ge=0.0, le=1.0)
    priority: float = Field(..., ge=0.0, le=1.0)
    proposed_by: str = "improvement_pipeline"
    human_approved: bool = False
    # SPEC-CRYPTOGRAPHIC_BINDING: canonical patch content digest computed at
    # payload creation time.  Must equal the tested_patch_digest in the linked
    # ImprovementRecord — proving that the content being applied is exactly the
    # content that was tested.  Verified by apply_patch_payload() before
    # expected_hash_before, whitelist, human gate, and SelfEditor.
    # Format: sha256:<64 lowercase hex chars>  (none-new-file is not valid here)
    patch_payload_hash: str = Field(..., min_length=1)
    contract: str = PATCH_PAYLOAD_CONTRACT

    @field_validator("target_file")
    @classmethod
    def _target_file_relative_safe(cls, value: str) -> str:
        """Reject absolute paths, parent traversal, empty parts, and backslashes."""
        cleaned = value.strip().replace("\\", "/")
        if not cleaned:
            raise ValueError("target_file must be non-empty")
        path = PurePosixPath(cleaned)
        if path.is_absolute():
            raise ValueError("target_file must be relative to project root")
        if ".." in path.parts:
            raise ValueError("target_file must not contain parent traversal")
        if any(part in {"", "."} for part in path.parts):
            raise ValueError("target_file contains an invalid path segment")
        return cleaned

    @field_validator("expected_hash_before")
    @classmethod
    def _hash_marker_valid(cls, value: str) -> str:
        """Require the project hash marker format used by CNS ChangeTrace."""
        cleaned = value.strip().lower()
        if not _SHA_RE.match(cleaned):
            raise ValueError("expected_hash_before must be sha256:<64 hex> or sha256:none-new-file")
        return cleaned

    @field_validator("patch_payload_hash")
    @classmethod
    def _patch_payload_hash_valid(cls, value: str) -> str:
        """Require full sha256:<64 hex> content digest — none-new-file not accepted."""
        cleaned = value.strip().lower()
        if not _CONTENT_HASH_RE.match(cleaned):
            raise ValueError(
                "patch_payload_hash must be sha256:<64 lowercase hex chars>; "
                "use canonical_patch_digest() from patch_applier to compute it"
            )
        if cleaned == "sha256:" + "0" * 64:
            raise ValueError(
                "patch_payload_hash is the all-zeros sentinel, not a real content "
                "digest; use canonical_patch_digest() from patch_applier to compute it"
            )
        return cleaned

    @model_validator(mode="after")
    def _content_matches_action(self) -> "PatchPayload":
        """Validate action/content combinations without executing them."""
        if self.action == "patch":
            if self.old_content is None or self.old_content == "":
                raise ValueError("old_content is required for patch action")
            if self.new_content == "":
                raise ValueError("new_content is required for patch action")
        if self.action in {"create", "append"} and self.new_content == "":
            raise ValueError("new_content is required for create and append actions")
        if self.action == "delete" and self.old_content not in {None, ""}:
            raise ValueError("old_content must be empty for delete action")
        return self


def patch_payload_contract_summary() -> dict[str, object]:
    """Return machine-readable contract metadata for protocol status."""
    return {
        "contract": PATCH_PAYLOAD_CONTRACT,
        "actions": sorted(_PATCH_ACTIONS),
        "hash_precondition": "mandatory sha256 marker before SelfEditor",
        "self_editor_entrypoint": "docking.improvement.patch_applier.apply_patch_payload",
        "high_severity_gate": "severity >= 0.8 or core/contracts target requires human_approved=True",
    }


__all__ = ["PATCH_PAYLOAD_CONTRACT", "PatchPayload", "patch_payload_contract_summary"]
