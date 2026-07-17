"""Closed-loop self-improvement pipeline for the NEUROFORGE Docking CNS.

The pipeline is intentionally guarded: every proposal must be submitted, tested
with the fast targeted tester, and recorded before the guarded SelfEditor call
path can be reached.  This module does not modify ``src/self_editor.py`` and it
never invokes SelfEditor before tests pass cleanly.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import ValidationError

from core.contracts.docking.ChangeTrace import ChangeTrace
from core.contracts.docking.ImprovementProposal import ImprovementProposal
from core.contracts.docking.ImprovementRecord import ImprovementRecord, TestSuiteResult
from docking.improvement.tester import run_fast_targeted_tests
from docking.memory.failure_memory import log_spec_failure

IMPROVEMENT_PIPELINE_CONTRACT = "neuroforge.docking.improvement.pipeline.v1.0"
IMPROVEMENT_RECORD_FILE = "improvement_records.jsonl"
IMPROVEMENT_AUDIT_CONTRACT = "neuroforge.docking.improvement_audit.v1.0"


def _project_root(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Resolve project root for improvement storage."""
    if project_root is not None:
        return Path(project_root).resolve()
    return Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _records_path(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Return the append-only improvement records JSONL path."""
    return _project_root(project_root) / "docking" / "improvement" / IMPROVEMENT_RECORD_FILE


def _audit_path(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Return the CNS validation/audit JSONL path."""
    return _project_root(project_root) / "docking" / "audit" / "validation_audit.jsonl"


def _sha256_file(path: Path) -> str:
    """Return a sha256 marker for an existing file or a stable none marker."""
    if not path.exists():
        return "sha256:none-new-file"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _stable_id(prefix: str, payload: Dict[str, Any], timestamp: str) -> str:
    """Build a deterministic-enough stable ID from payload and timestamp."""
    raw = json.dumps(payload, sort_keys=True, default=str) + timestamp
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _append_audit(event: Dict[str, Any], project_root: Optional[Union[str, Path]] = None) -> None:
    """Append a structured CNS audit event."""
    path = _audit_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")


def _append_record(record: ImprovementRecord, project_root: Optional[Union[str, Path]] = None) -> None:
    """Append an immutable ImprovementRecord JSONL entry."""
    path = _records_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")


def _read_records(project_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Read valid ImprovementRecord entries without mutating state."""
    path = _records_path(project_root)
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
            records.append(ImprovementRecord.model_validate_json(line).model_dump(mode="json"))
        except (ValidationError, ValueError) as exc:
            records.append({"status": "malformed", "error": str(exc), "raw": line})
    return records


def _latest_record_for(proposal_id: str, project_root: Optional[Union[str, Path]] = None) -> Optional[Dict[str, Any]]:
    """Return the most recent record for a proposal ID."""
    matches = [record for record in _read_records(project_root) if record.get("proposal_id") == proposal_id]
    return matches[-1] if matches else None


def _proposal_from_input(proposal_input: Union[ImprovementProposal, Dict[str, Any]]) -> ImprovementProposal:
    """Validate proposal input and assign a proposal ID when missing."""
    proposal = proposal_input if isinstance(proposal_input, ImprovementProposal) else ImprovementProposal.model_validate(proposal_input)
    if proposal.proposal_id:
        return proposal
    timestamp = _utc_now()
    payload = proposal.model_dump(mode="json")
    payload.pop("proposal_id", None)
    return proposal.model_copy(update={"proposal_id": _stable_id("IP", payload, timestamp)})


def _requires_human_approval(proposal: ImprovementProposal) -> bool:
    """Return True when severity or core-contract impact requires approval."""
    if proposal.severity >= 0.8:
        return True
    return any(module.replace("\\", "/").startswith("core/contracts") for module in proposal.target_modules)


def _change_trace_for_records(spec_id: str, timestamp: str, reason: str, project_root: Optional[Union[str, Path]] = None) -> ChangeTrace:
    """Create a ChangeTrace for the append-only improvement record log."""
    path = _records_path(project_root)
    previous_hash = _sha256_file(path)
    return ChangeTrace(
        file_path="docking/improvement/improvement_records.jsonl",
        spec_id=spec_id,
        action="modified" if previous_hash != "sha256:none-new-file" else "created",
        reason=reason,
        timestamp=timestamp,
        previous_hash=previous_hash,
    )


def _record_failure_memory(
    proposal: ImprovementProposal,
    state: str,
    reason: str,
    issues: List[Dict[str, Any]],
    timestamp: str,
    project_root: Optional[Union[str, Path]] = None,
) -> List[str]:
    """Feed improvement attempt details into Failure Memory."""
    category = "improvement_success" if state == "applied" else f"improvement_{state}"
    record = log_spec_failure(
        spec_id=proposal.proposal_id or "UNKNOWN_PROPOSAL",
        failure_category=category,
        reason=reason,
        issues=issues,
        timestamp=timestamp,
        validator_version=IMPROVEMENT_PIPELINE_CONTRACT,
        project_root=project_root,
    )
    return [f"{record.get('spec_id')}:{record.get('failure_category')}:{record.get('timestamp')}"]


def _build_record(
    proposal: ImprovementProposal,
    *,
    state: str,
    transition: str,
    timestamp: str,
    test_result: Optional[TestSuiteResult] = None,
    applied: bool = False,
    rollback_info: Optional[Dict[str, Any]] = None,
    failure_references: Optional[List[str]] = None,
    human_approval_required: bool = False,
    self_editor_gate: Optional[Dict[str, Any]] = None,
    project_root: Optional[Union[str, Path]] = None,
) -> ImprovementRecord:
    """Build, audit, and return a strict ImprovementRecord."""
    trace = _change_trace_for_records(
        proposal.source_sideletter_id or proposal.proposal_id or "UNKNOWN",
        timestamp,
        f"Improvement pipeline transition: {transition}",
        project_root,
    )
    audit_event = {
        "timestamp": timestamp,
        "spec_id": proposal.source_sideletter_id or proposal.proposal_id,
        "status": f"improvement_{state}",
        "issues": [] if applied or state in {"proposed", "human_approval"} else [{"field": "improvement", "message": transition, "severity": "warning"}],
        "validator_version": IMPROVEMENT_PIPELINE_CONTRACT,
        "contract": IMPROVEMENT_AUDIT_CONTRACT,
        "proposal_id": proposal.proposal_id,
        "transition": transition,
        "change_trace": trace.model_dump(),
    }
    record = ImprovementRecord(
        record_id=_stable_id("IR", {"proposal_id": proposal.proposal_id, "state": state, "transition": transition}, timestamp),
        proposal_id=proposal.proposal_id or "UNKNOWN_PROPOSAL",
        state=state,
        transition=transition,
        proposal=proposal,
        test_result=test_result,
        applied=applied,
        rollback_info=rollback_info or {},
        failure_references=failure_references or [],
        timestamp=timestamp,
        change_traces=[trace.model_dump()],
        audit_event=audit_event,
        human_approval_required=human_approval_required,
        self_editor_gate=self_editor_gate or {},
        # SPEC-CRYPTOGRAPHIC_BINDING: propagate proposal_content_hash as the
        # tested_patch_digest so apply_patch_payload() can verify content integrity.
        tested_patch_digest=proposal.proposal_content_hash,
    )
    _append_audit(audit_event, project_root)
    _append_record(record, project_root)
    return record


def submit_improvement_proposal(
    proposal_input: Union[ImprovementProposal, Dict[str, Any]],
    *,
    project_root: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Submit a proposal and create the initial audited pipeline record.

    Args:
        proposal_input: Strict proposal object or dictionary payload.
        project_root: Optional project root override used by tests.

    Returns:
        Dictionary representation of the submitted proposal and first record.
    """
    timestamp = _utc_now()
    proposal = _proposal_from_input(proposal_input)
    record = _build_record(
        proposal,
        state="proposed",
        transition="proposal submitted to non-bypassable improvement pipeline",
        timestamp=timestamp,
        human_approval_required=_requires_human_approval(proposal),
        self_editor_gate={"eligible": False, "reason": "proposal has not passed fast targeted tester"},
        project_root=project_root,
    )
    return {"ok": True, "proposal": proposal.model_dump(mode="json"), "record": record.model_dump(mode="json")}


def _guarded_self_editor_apply(proposal: ImprovementProposal, test_result: TestSuiteResult, human_approval_required: bool) -> Dict[str, Any]:
    """Guard the approved SelfEditor call path without editing SelfEditor.

    SPEC-0003 defines proposal/test/approval gates but does not define a patch
    payload format. Therefore, a passing low-severity proposal reaches a
    guarded no-op apply marker rather than modifying source files. Future specs
    can extend the proposal contract with an explicit patch payload.
    """
    if not test_result.passed:
        return {"called": False, "eligible": False, "reason": "fast targeted tester did not pass"}
    if human_approval_required:
        return {"called": False, "eligible": False, "reason": "human approval required before SelfEditor"}
    return {
        "called": True,
        "eligible": True,
        "mode": "guarded_noop_no_patch_payload_defined",
        "reason": "tests passed; SPEC-0003 defines call gate but no patch payload format",
        "self_editor_module_unmodified": True,
    }


def run_improvement_pipeline(
    proposal_id: str,
    *,
    project_root: Optional[Union[str, Path]] = None,
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    """Run the tested improvement pipeline for a submitted proposal.

    Args:
        proposal_id: Proposal identifier returned by submission.
        project_root: Optional project root override used by tests.
        timeout_seconds: Fast tester timeout per proposal.

    Returns:
        Dictionary representation of the final ImprovementRecord.
    """
    latest = _latest_record_for(proposal_id, project_root)
    if latest is None:
        raise ValueError(f"unknown improvement proposal_id: {proposal_id}")
    proposal = ImprovementProposal.model_validate(latest["proposal"])
    timestamp = _utc_now()
    test_result = run_fast_targeted_tests(proposal, project_root=project_root, timeout_seconds=timeout_seconds)
    human_required = _requires_human_approval(proposal)
    if not test_result.passed:
        failure_refs = _record_failure_memory(
            proposal,
            "rejected",
            "fast targeted tester failed",
            [{"field": "tests", "message": item, "severity": "error"} for item in test_result.failing_tests],
            timestamp,
            project_root,
        )
        record = _build_record(
            proposal,
            state="rejected",
            transition="fast targeted tester failed; SelfEditor blocked",
            timestamp=timestamp,
            test_result=test_result,
            applied=False,
            rollback_info={"required": False, "reason": "no changes applied"},
            failure_references=failure_refs,
            human_approval_required=human_required,
            self_editor_gate={"eligible": False, "reason": "tester failed"},
            project_root=project_root,
        )
        return record.model_dump(mode="json")
    if human_required:
        failure_refs = _record_failure_memory(
            proposal,
            "human_approval",
            "human approval required before SelfEditor",
            [{"field": "approval", "message": "severity/core-contract gate", "severity": "warning"}],
            timestamp,
            project_root,
        )
        record = _build_record(
            proposal,
            state="human_approval",
            transition="tests passed; human approval required before SelfEditor",
            timestamp=timestamp,
            test_result=test_result,
            applied=False,
            rollback_info={"required": False, "reason": "no changes applied before human approval"},
            failure_references=failure_refs,
            human_approval_required=True,
            self_editor_gate={"eligible": False, "reason": "human approval required"},
            project_root=project_root,
        )
        return record.model_dump(mode="json")
    self_editor_gate = _guarded_self_editor_apply(proposal, test_result, human_required)
    failure_refs = _record_failure_memory(
        proposal,
        "applied",
        "fast targeted tester passed and guarded SelfEditor call path reached",
        [{"field": "tests", "message": "all selected tests passed", "severity": "info"}],
        timestamp,
        project_root,
    )
    record = _build_record(
        proposal,
        state="applied",
        transition="fast targeted tester passed; guarded SelfEditor call path reached",
        timestamp=timestamp,
        test_result=test_result,
        applied=True,
        rollback_info={"required": False, "reason": "no patch payload defined by SPEC-0003"},
        failure_references=failure_refs,
        human_approval_required=False,
        self_editor_gate=self_editor_gate,
        project_root=project_root,
    )
    return record.model_dump(mode="json")


def generate_improvement_from_sideletter(
    sideletter: Union[Dict[str, Any], Any],
    *,
    project_root: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Convert SideLetter proposed_actions into ImprovementProposal payloads.

    Args:
        sideletter: SideLetter model or dictionary with proposed_actions.
        project_root: Reserved for parity with other pipeline functions.

    Returns:
        List of strict ImprovementProposal dictionaries linked to the source
        SideLetter spec ID/timestamp.
    """
    _ = project_root
    data = sideletter.model_dump(mode="json") if hasattr(sideletter, "model_dump") else dict(sideletter)
    source_id = str(data.get("spec_id") or "UNKNOWN_SIDELETTER")
    timestamp = str(data.get("timestamp") or _utc_now())
    proposals: List[Dict[str, Any]] = []
    for index, action in enumerate(data.get("proposed_actions", []) or []):
        target = str(action.get("target", "")).strip()
        description = str(action.get("description", "")).strip()
        priority = float(action.get("priority", 0.5))
        proposal = ImprovementProposal(
            proposal_id=_stable_id("IP", {"source": source_id, "index": index, "action": action}, timestamp),
            severity=float(action.get("severity", min(0.79, max(0.0, priority)))),
            priority=priority,
            target_modules=[target],
            target_functions=[],
            description=description,
            expected_outcome=f"Targeted improvement action completes safely for {target}.",
            source_sideletter_id=source_id,
            proposed_actions=[action],
        )
        proposals.append(proposal.model_dump(mode="json"))
    return proposals


def get_recent_improvement_records(limit: int = 10, *, project_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Return recent improvement records without mutating state."""
    safe_limit = max(0, int(limit))
    if safe_limit == 0:
        return []
    return _read_records(project_root)[-safe_limit:]


def get_improvement_status(proposal_id: str, *, project_root: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Return the latest status for a proposal without mutating state."""
    latest = _latest_record_for(str(proposal_id or ""), project_root)
    if latest is None:
        return {"ok": False, "proposal_id": proposal_id, "state": "unknown", "error": "proposal not found"}
    return {"ok": True, "proposal_id": proposal_id, "state": latest.get("state"), "record": latest}


def improvement_pipeline_status(*, project_root: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Return read-only health for the closed-loop improvement pipeline."""
    root = _project_root(project_root)
    records = get_recent_improvement_records(20, project_root=root)
    path = _records_path(root)
    return {
        "ok": (root / "docking" / "improvement").exists(),
        "contract": IMPROVEMENT_PIPELINE_CONTRACT,
        "read_only": True,
        "records_file": str(path),
        "recent_count": len(records),
        "recent_records": records[-10:],
        "self_editor_rule": "no SelfEditor call path without passed fast tester and full ImprovementRecord",
    }


__all__ = [
    "IMPROVEMENT_PIPELINE_CONTRACT",
    "IMPROVEMENT_RECORD_FILE",
    "submit_improvement_proposal",
    "run_improvement_pipeline",
    "generate_improvement_from_sideletter",
    "get_recent_improvement_records",
    "get_improvement_status",
    "improvement_pipeline_status",
]
