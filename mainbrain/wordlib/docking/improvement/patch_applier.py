"""Guarded PatchPayload apply gate for NEUROFORGE SelfEditor mutation.

The only improvement-system path that may call SelfEditor write methods is
``apply_patch_payload()``. Gate order (SPEC-CRYPTOGRAPHIC_BINDING):
  1. Validate PatchPayload contract.
  2. Load linked ImprovementRecord.
  3. Verify test_result.passed is True.
  4-7. Verify digest chain: tested_patch_digest == patch_payload_hash
       (and proposal_content_hash == tested_patch_digest where present).
  8. Verify expected_hash_before against current file.
  9. Verify SelfEditor whitelist.
  10. Verify human approval gate.
  11. Call SelfEditor public API.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Union

from pydantic import ValidationError

from core.contracts.docking.ChangeTrace import ChangeTrace
from core.contracts.docking.ImprovementProposal import ImprovementProposal
from core.contracts.docking.ImprovementRecord import ImprovementRecord, TestSuiteResult
from core.contracts.docking.PatchPayload import PATCH_PAYLOAD_CONTRACT, PatchPayload
from docking.memory.failure_memory import log_spec_failure
from docking.improvement.pipeline import IMPROVEMENT_AUDIT_CONTRACT, IMPROVEMENT_RECORD_FILE

PATCH_APPLIER_CONTRACT = "neuroforge.docking.improvement.patch_applier.v1.0"
PATCH_RECORD_FILE = "patch_records.jsonl"
PATCH_AUDIT_CONTRACT = "neuroforge.docking.patch_apply_audit.v1.0"
_SELFEDITOR_WRITE_WHITELIST = [
    "launcher.py",
    "src/*.py",
    "app/main.py",
    "app/templates/*.html",
    "config/*.json",
    "storage/**/*.md",
    "storage/**/*.txt",
    "docs/*.txt",
    "docs/*.md",
    "README.md",
    "CLAUDE_BRIEFING.md",
]

# SPEC-CRYPTOGRAPHIC_BINDING: sentinel values that must not be accepted as proof.
_SENTINEL_DIGESTS = {
    "sha256:" + "0" * 64,  # all-zeros sentinel
    "sha256:" + "f" * 64,  # all-f sentinel
}
# Valid content digest: sha256:<64 lowercase hex>  (none-new-file excluded)
import re as _re
_CONTENT_HASH_RE = _re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_patch_digest(
    action: str,
    target_file: str,
    old_content: Optional[str],
    new_content: Optional[str],
) -> str:
    """Deterministic SHA-256 digest of a patch specification.

    Format includes: action, normalized POSIX target_file, old_content (patch
    only), new_content (create/patch/append), delete marker (delete).

    Excluded: timestamps, absolute paths, audit IDs, machine metadata, test
    duration, nondeterministic test output.

    Returns:
        ``sha256:<64 lowercase hex chars>``
    """
    normalized = PurePosixPath(target_file.replace("\\", "/")).as_posix()
    parts = [f"action:{action}", f"target:{normalized}"]
    if action == "patch" and old_content is not None:
        parts.append(f"old:{old_content}")
    if action in {"create", "patch", "append"} and new_content is not None:
        parts.append(f"new:{new_content}")
    if action == "delete":
        parts.append("content:deleted")
    canonical = "\n".join(parts)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_valid_content_digest(value: str) -> bool:
    """True if value is sha256:<64 hex> and not a known sentinel."""
    return bool(_CONTENT_HASH_RE.match(value)) and value not in _SENTINEL_DIGESTS


def _project_root(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Resolve the project root for patch storage and target hashing."""
    if project_root is not None:
        return Path(project_root).resolve()
    return Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    """Return a timezone-aware UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def _records_path(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Return append-only patch record path."""
    return _project_root(project_root) / "docking" / "improvement" / PATCH_RECORD_FILE


def _improvement_records_path(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Return append-only ImprovementRecord path."""
    return _project_root(project_root) / "docking" / "improvement" / IMPROVEMENT_RECORD_FILE


def _audit_path(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Return CNS validation/audit JSONL path."""
    return _project_root(project_root) / "docking" / "audit" / "validation_audit.jsonl"


def _hash_file_marker(path: Path) -> str:
    """Return current hash marker, using a stable marker for missing files."""
    if not path.exists():
        return "sha256:none-new-file"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    """Append one JSON object to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read JSONL records defensively without mutating state."""
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [{"status": "error", "error": f"{type(exc).__name__}: {exc}"}]
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            records.append({"status": "malformed", "error": str(exc), "raw": line})
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _target_path(payload: PatchPayload, project_root: Optional[Union[str, Path]] = None) -> Path:
    """Resolve payload target under project root."""
    root = _project_root(project_root)
    target = (root / payload.target_file).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("target_file resolved outside project root") from exc
    return target


def _is_selfeditor_whitelisted(target_file: str) -> bool:
    """Check target intent against the current SelfEditor write patterns."""
    normalized = target_file.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in _SELFEDITOR_WRITE_WHITELIST)


def _requires_human_approval(payload: PatchPayload) -> bool:
    """Return True when severity or core-contract target requires approval."""
    return payload.severity >= 0.8 or payload.target_file.replace("\\", "/").startswith("core/contracts/")


def _patch_action_to_trace_action(action: str) -> str:
    """Map patch action to ChangeTrace action."""
    if action == "create":
        return "created"
    if action == "delete":
        return "deleted"
    return "modified"


def _change_trace_for_target(payload: PatchPayload, timestamp: str) -> ChangeTrace:
    """Create a ChangeTrace for the target file precondition."""
    return ChangeTrace(
        file_path=payload.target_file,
        spec_id=payload.patch_id,
        action=_patch_action_to_trace_action(payload.action),
        reason=payload.reason,
        timestamp=timestamp,
        previous_hash=payload.expected_hash_before,
    )


def _change_trace_for_patch_record(payload: PatchPayload, timestamp: str, project_root: Optional[Union[str, Path]] = None) -> ChangeTrace:
    """Create a ChangeTrace for the patch record log."""
    path = _records_path(project_root)
    previous_hash = _hash_file_marker(path)
    return ChangeTrace(
        file_path="docking/improvement/patch_records.jsonl",
        spec_id=payload.patch_id,
        action="modified" if previous_hash != "sha256:none-new-file" else "created",
        reason="Append PatchPayload apply attempt record.",
        timestamp=timestamp,
        previous_hash=previous_hash,
    )


def _minimal_proposal(payload: PatchPayload) -> ImprovementProposal:
    """Build a minimal proposal snapshot for ImprovementRecord traceability."""
    return ImprovementProposal(
        proposal_id=payload.linked_improvement_record_id,
        severity=payload.severity,
        priority=payload.priority,
        target_modules=[payload.target_file],
        target_functions=[],
        description=payload.reason,
        expected_outcome=f"PatchPayload {payload.patch_id} applies safely through SelfEditor.",
        source_sideletter_id=payload.linked_sideletter_id,
        proposed_actions=[{
            "type": "refactor" if payload.action == "patch" else "strengthen_validation",
            "target": payload.target_file,
            "description": payload.reason,
            "priority": payload.priority,
        }],
    )


def _test_result_for_patch(passed: bool, selected: List[str], failing: List[str]) -> TestSuiteResult:
    """Build a synthetic TestSuiteResult snapshot for patch apply attempts.

    SPEC-0004 applies after the fast tester has already passed. This result
    records the patch gate outcome rather than rerunning tests.
    """
    return TestSuiteResult(
        passed=passed,
        duration=0.0,
        selected_tests=selected,
        failing_tests=failing,
        timed_out=False,
        coverage_delta=None,
        command=["patch_payload_gate"],
        resource_limits={"rerun_tests": False, "reason": "SPEC-0004 consumes passed ImprovementRecord gate"},
    )


def _append_improvement_record(
    payload: PatchPayload,
    *,
    state: str,
    transition: str,
    applied: bool,
    timestamp: str,
    change_traces: List[Dict[str, Any]],
    audit_event: Dict[str, Any],
    failure_references: List[str],
    rollback_info: Dict[str, Any],
    self_editor_gate: Dict[str, Any],
    project_root: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Append a full ImprovementRecord for a patch attempt."""
    record = ImprovementRecord(
        record_id=f"PATCH_IR_{hashlib.sha256((payload.patch_id + timestamp + state).encode('utf-8')).hexdigest()[:16]}",
        proposal_id=payload.linked_improvement_record_id,
        state=state,
        transition=transition,
        proposal=_minimal_proposal(payload),
        test_result=_test_result_for_patch(applied, [payload.target_file], [] if applied else [transition]),
        applied=applied,
        rollback_info=rollback_info,
        failure_references=failure_references,
        timestamp=timestamp,
        change_traces=change_traces,
        audit_event=audit_event,
        human_approval_required=_requires_human_approval(payload),
        self_editor_gate=self_editor_gate,
    )
    path = _improvement_records_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")
    return record.model_dump(mode="json")




def _read_improvement_records(project_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Read valid ImprovementRecord entries for PatchPayload proof checks.

    The patch apply gate must prove that the linked improvement path has
    already passed the fast targeted tester. Malformed historical lines are
    ignored for proof purposes rather than treated as proof.
    """
    path = _improvement_records_path(project_root)
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            records.append(ImprovementRecord.model_validate_json(line).model_dump(mode="json"))
        except (ValidationError, ValueError):
            continue
    return records


def _linked_improvement_test_proof(payload: PatchPayload, project_root: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Validate that PatchPayload references a tester-passed ImprovementRecord.

    SPEC-0004 closes the loop after SPEC-0003: a patch may only reach
    SelfEditor after an ImprovementProposal passed fast targeted tests. This
    proof function enforces that ``linked_improvement_record_id`` points to a
    persisted record with ``test_result.passed is True``. High-severity or
    core-contract records that stopped at the human gate are acceptable only
    when the PatchPayload itself carries ``human_approved=True``.
    """
    matches = [
        record for record in _read_improvement_records(project_root)
        if record.get("proposal_id") == payload.linked_improvement_record_id
    ]
    if not matches:
        return {
            "ok": False,
            "reason": "linked_improvement_record_id has no persisted ImprovementRecord",
            "record": None,
        }
    latest = matches[-1]
    test_result = latest.get("test_result") or {}
    if not bool(test_result.get("passed")):
        return {
            "ok": False,
            "reason": "linked ImprovementRecord does not prove fast targeted tester passed",
            "record": latest,
        }
    state = str(latest.get("state", ""))
    if state == "human_approval" and not payload.human_approved:
        return {
            "ok": False,
            "reason": "linked ImprovementRecord requires human approval before patch apply",
            "record": latest,
        }
    if state not in {"tested", "applied", "human_approval"}:
        return {
            "ok": False,
            "reason": f"linked ImprovementRecord is not in an apply-eligible state: {state}",
            "record": latest,
        }
    return {
        "ok": True,
        "reason": "linked ImprovementRecord proves fast targeted tester passed",
        "record": latest,
    }

def _log_failure_memory(payload: PatchPayload, category: str, reason: str, issues: List[Dict[str, Any]], timestamp: str, project_root: Optional[Union[str, Path]] = None) -> str:
    """Write a Failure Memory entry for patch success/failure signals."""
    record = log_spec_failure(
        spec_id=payload.patch_id,
        failure_category=category,
        reason=reason,
        issues=issues,
        timestamp=timestamp,
        validator_version=PATCH_APPLIER_CONTRACT,
        project_root=project_root,
    )
    return f"{record.get('spec_id')}:{record.get('failure_category')}:{record.get('timestamp')}"


def _patch_record(
    payload: PatchPayload,
    *,
    status: str,
    timestamp: str,
    current_hash_before: str,
    result: Dict[str, Any],
    change_traces: List[Dict[str, Any]],
    audit_event: Dict[str, Any],
    improvement_record: Optional[Dict[str, Any]],
    failure_references: List[str],
    project_root: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Persist and return a structured PatchPayload status record."""
    record = {
        "patch_id": payload.patch_id,
        "status": status,
        "timestamp": timestamp,
        "payload": payload.model_dump(mode="json"),
        "current_hash_before": current_hash_before,
        "result": result,
        "change_traces": change_traces,
        "audit_event": audit_event,
        "improvement_record": improvement_record,
        "failure_references": failure_references,
        "contract": PATCH_APPLIER_CONTRACT,
    }
    _append_jsonl(_records_path(project_root), record)
    return record


def submit_patch_payload(payload: Union[PatchPayload, Dict[str, Any]], *, project_root: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Validate and record a PatchPayload without applying it.

    Args:
        payload: PatchPayload model or dictionary payload.
        project_root: Optional project root override.

    Returns:
        Structured submission record.
    """
    timestamp = _utc_now()
    patch = payload if isinstance(payload, PatchPayload) else PatchPayload.model_validate(payload)
    trace = _change_trace_for_patch_record(patch, timestamp, project_root)
    audit_event = {
        "timestamp": timestamp,
        "spec_id": patch.patch_id,
        "status": "patch_payload_submitted",
        "issues": [],
        "validator_version": PATCH_APPLIER_CONTRACT,
        "contract": PATCH_AUDIT_CONTRACT,
        "patch_id": patch.patch_id,
        "target_file": patch.target_file,
        "change_trace": trace.model_dump(),
    }
    _append_jsonl(_audit_path(project_root), audit_event)
    return _patch_record(
        patch,
        status="submitted",
        timestamp=timestamp,
        current_hash_before=_hash_file_marker(_target_path(patch, project_root)),
        result={"ok": True, "human_approval_required": _requires_human_approval(patch)},
        change_traces=[trace.model_dump()],
        audit_event=audit_event,
        improvement_record=None,
        failure_references=[],
        project_root=project_root,
    )


def apply_patch_payload(payload: Union[PatchPayload, Dict[str, Any]], *, project_root: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Apply a PatchPayload through the single guarded SelfEditor entry point.

    The function validates the payload, verifies the hash precondition before
    any SelfEditor call, checks whitelist intent, enforces the human approval
    gate, and then calls SelfEditor public methods only.

    Args:
        payload: Strict PatchPayload or dictionary input.
        project_root: Optional project root override used by tests/status.

    Returns:
        Structured patch status record containing audit, ChangeTrace,
        ImprovementRecord, and Failure Memory references.
    """
    timestamp = _utc_now()
    try:
        patch = payload if isinstance(payload, PatchPayload) else PatchPayload.model_validate(payload)
    except ValidationError:
        raise
    target = _target_path(patch, project_root)
    current_hash = _hash_file_marker(target)
    trace = _change_trace_for_patch_record(patch, timestamp, project_root)
    target_trace = _change_trace_for_target(patch, timestamp)

    def fail(status: str, message: str, field: str = "patch_payload") -> Dict[str, Any]:
        issue = {"field": field, "message": message, "severity": "error"}
        failure_ref = _log_failure_memory(patch, f"patch_{status}", message, [issue], timestamp, project_root)
        audit_event = {
            "timestamp": timestamp,
            "spec_id": patch.patch_id,
            "status": f"patch_{status}",
            "issues": [issue],
            "validator_version": PATCH_APPLIER_CONTRACT,
            "contract": PATCH_AUDIT_CONTRACT,
            "patch_id": patch.patch_id,
            "target_file": patch.target_file,
            "self_editor_called": False,
            "change_trace": trace.model_dump(),
        }
        _append_jsonl(_audit_path(project_root), audit_event)
        improvement_record = _append_improvement_record(
            patch,
            state="human_approval" if status == "human_approval" else "rejected",
            transition=message,
            applied=False,
            timestamp=timestamp,
            change_traces=[trace.model_dump()],
            audit_event=audit_event,
            failure_references=[failure_ref],
            rollback_info={"required": False, "reason": "patch blocked before source mutation"},
            self_editor_gate={"called": False, "eligible": False, "reason": message},
            project_root=project_root,
        )
        return _patch_record(
            patch,
            status=status,
            timestamp=timestamp,
            current_hash_before=current_hash,
            result={"ok": False, "error": message, "self_editor_called": False},
            change_traces=[trace.model_dump()],
            audit_event=audit_event,
            improvement_record=improvement_record,
            failure_references=[failure_ref],
            project_root=project_root,
        )

    # ── Gate 2-3: Linked ImprovementRecord must exist and prove tests passed ──
    proof = _linked_improvement_test_proof(patch, project_root)
    if not proof.get("ok"):
        return fail(
            "missing_test_proof",
            str(proof.get("reason", "missing linked test proof")),
            "linked_improvement_record_id",
        )
    ir: Dict[str, Any] = proof.get("record") or {}

    # ── Gates 4-7: Digest chain (SPEC-CRYPTOGRAPHIC_BINDING) ─────────────────
    # Proves that the content being applied is the exact content that was tested.
    # Checked before expected_hash_before, whitelist, and human gate so that a
    # valid file hash or human signature cannot override a broken content proof.
    proposal_hash: Optional[str] = (ir.get("proposal") or {}).get("proposal_content_hash")
    tested_digest: Optional[str] = ir.get("tested_patch_digest")
    payload_digest: str = patch.patch_payload_hash  # required field, already validated

    if not tested_digest:
        return fail(
            "missing_content_digest",
            "linked ImprovementRecord has no tested_patch_digest; "
            "the improvement pipeline must record the patch digest before apply",
            "tested_patch_digest",
        )
    if not _is_valid_content_digest(tested_digest):
        return fail(
            "invalid_content_digest",
            f"tested_patch_digest '{tested_digest[:20]}...' is not a valid "
            "sha256:<64 hex> digest or is a known sentinel value",
            "tested_patch_digest",
        )
    if not _is_valid_content_digest(payload_digest):
        return fail(
            "invalid_content_digest",
            f"patch_payload_hash '{payload_digest[:20]}...' is not a valid "
            "sha256:<64 hex> digest or is a known sentinel value",
            "patch_payload_hash",
        )
    if tested_digest != payload_digest:
        return fail(
            "mismatched_content_digest",
            f"patch_payload_hash does not match tested_patch_digest — "
            f"the content being applied was not the content that was tested "
            f"(payload: {payload_digest[:16]}..., tested: {tested_digest[:16]}...)",
            "patch_payload_hash",
        )
    if proposal_hash and proposal_hash != tested_digest:
        return fail(
            "mismatched_content_digest",
            f"proposal_content_hash does not match tested_patch_digest — "
            f"the proposal was modified after submission "
            f"(proposal: {proposal_hash[:16]}..., tested: {tested_digest[:16]}...)",
            "proposal_content_hash",
        )

    # ── Gate 8: Hash precondition ─────────────────────────────────────────────
    if current_hash != patch.expected_hash_before:
        return fail("hash_mismatch", "expected_hash_before does not match current file hash", "expected_hash_before")

    # ── Gate 9: SelfEditor whitelist ──────────────────────────────────────────
    if not _is_selfeditor_whitelisted(patch.target_file):
        return fail("not_whitelisted", "target_file is not inside the SelfEditor write whitelist", "target_file")

    # ── Gate 10: Human approval ───────────────────────────────────────────────
    if _requires_human_approval(patch) and not patch.human_approved:
        return fail("human_approval", "human approval required before SelfEditor apply", "human_approved")

    # ── Gate 11: SelfEditor public API ────────────────────────────────────────
    from src.self_editor import SelfEditor
    editor = SelfEditor()
    if patch.action == "create":
        editor_result = editor.write_file(patch.target_file, patch.new_content)
    elif patch.action == "patch":
        editor_result = editor.patch_file(patch.target_file, patch.old_content or "", patch.new_content)
    elif patch.action == "append":
        editor_result = editor.append_to_file(patch.target_file, patch.new_content)
    elif patch.action == "delete":
        editor_result = editor.delete_file(patch.target_file)
    else:  # Defensive unreachable branch because PatchPayload validates action.
        return fail("invalid_action", f"unsupported patch action: {patch.action}", "action")

    if not bool(editor_result.get("ok")):
        return fail("selfeditor_rejected", str(editor_result.get("error", "SelfEditor rejected patch")), "self_editor")

    failure_ref = _log_failure_memory(
        patch,
        "patch_apply_success",
        "PatchPayload applied safely through SelfEditor public API",
        [{"field": "patch_payload", "message": "SelfEditor apply succeeded", "severity": "info"}],
        timestamp,
        project_root,
    )
    audit_event = {
        "timestamp": timestamp,
        "spec_id": patch.patch_id,
        "status": "patch_applied",
        "issues": [],
        "validator_version": PATCH_APPLIER_CONTRACT,
        "contract": PATCH_AUDIT_CONTRACT,
        "patch_id": patch.patch_id,
        "target_file": patch.target_file,
        "self_editor_called": True,
        "self_editor_result": editor_result,
        "change_trace": target_trace.model_dump(),
    }
    _append_jsonl(_audit_path(project_root), audit_event)
    improvement_record = _append_improvement_record(
        patch,
        state="applied",
        transition="PatchPayload hash precondition passed and SelfEditor applied patch",
        applied=True,
        timestamp=timestamp,
        change_traces=[target_trace.model_dump(), trace.model_dump()],
        audit_event=audit_event,
        failure_references=[failure_ref],
        rollback_info={"self_editor_result": editor_result, "backup": editor_result.get("backup")},
        self_editor_gate={"called": True, "eligible": True, "entrypoint": "apply_patch_payload", "test_proof": proof.get("reason")},
        project_root=project_root,
    )
    return _patch_record(
        patch,
        status="applied",
        timestamp=timestamp,
        current_hash_before=current_hash,
        result={"ok": True, "self_editor_called": True, "self_editor_result": editor_result, "test_proof": proof.get("reason")},
        change_traces=[target_trace.model_dump(), trace.model_dump()],
        audit_event=audit_event,
        improvement_record=improvement_record,
        failure_references=[failure_ref],
        project_root=project_root,
    )


def get_recent_patches(limit: int = 10, *, project_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Return recent patch records without mutating state."""
    safe_limit = max(0, int(limit))
    if safe_limit == 0:
        return []
    return _read_jsonl(_records_path(project_root))[-safe_limit:]


def get_patch_status(patch_id: str, *, project_root: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Return the latest patch status for a patch ID without mutating state."""
    target = str(patch_id or "").strip()
    if not target:
        return {"ok": False, "patch_id": patch_id, "status": "unknown", "error": "empty patch_id"}
    matches = [record for record in _read_jsonl(_records_path(project_root)) if record.get("patch_id") == target]
    if not matches:
        return {"ok": False, "patch_id": target, "status": "unknown", "error": "patch not found"}
    latest = matches[-1]
    return {"ok": True, "patch_id": target, "status": latest.get("status"), "record": latest}


def patch_applier_status(*, project_root: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Return read-only health for the PatchPayload apply gate."""
    root = _project_root(project_root)
    records = get_recent_patches(20, project_root=root)
    return {
        "ok": (root / "docking" / "improvement").exists(),
        "contract": PATCH_APPLIER_CONTRACT,
        "patch_payload_contract": PATCH_PAYLOAD_CONTRACT,
        "read_only": True,
        "records_file": str(_records_path(root)),
        "recent_count": len(records),
        "recent_patches": records[-10:],
        "self_editor_entrypoint": "docking.improvement.patch_applier.apply_patch_payload",
        "hash_precondition": "expected_hash_before must match before SelfEditor call",
        "linked_improvement_record_gate": "linked record must prove fast targeted tester passed",
    }


__all__ = [
    "PATCH_APPLIER_CONTRACT",
    "PATCH_RECORD_FILE",
    "canonical_patch_digest",
    "submit_patch_payload",
    "apply_patch_payload",
    "get_recent_patches",
    "get_patch_status",
    "patch_applier_status",
]
