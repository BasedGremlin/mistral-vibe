"""
NEUROFORGE docking/specification protocol contracts v1.1.

This module is the contract-first boundary between specification authors
(Claude), implementation engines (ChatGPT), and merge/verification systems
(Cloud).  It is intentionally dependency-light and pure stdlib so the docking
protocol can run before optional infrastructure exists.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SPEC_PROTOCOL_VERSION = "neuroforge.spec_protocol.v1.1"
SPEC_DOCUMENT_CONTRACT = "neuroforge.spec_document.v1.1"
IMPLEMENTATION_REPORT_CONTRACT = "neuroforge.implementation_report.v1.1"
CHANGE_TRACE_CONTRACT = "neuroforge.change_trace.v1.1"
SPEC_REGISTRY_CONTRACT = "neuroforge.spec_registry.v1.1"
PROTOCOL_SELF_DESCRIPTION_CONTRACT = "neuroforge.protocol_self_description.v1.1"

VALID_SPEC_STATUSES = {"draft", "accepted", "implemented", "verified", "superseded", "rejected"}
LEGACY_SPEC_STATUS_ALIASES = {"drafted": "draft"}
VALID_IMPLEMENTATION_STATUSES = {"success", "partial", "blocked", "conflict"}
VALID_CHANGE_ACTIONS = {"created", "modified", "deleted"}
VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}
VALID_TRANSITIONS = {
    "draft": {"accepted", "rejected"},
    "accepted": {"implemented", "rejected"},
    "implemented": {"verified", "rejected"},
    "verified": {"superseded", "rejected"},
    "superseded": {"rejected"},
    "rejected": set(),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_status(value: str) -> str:
    raw = str(value or "").strip()
    return LEGACY_SPEC_STATUS_ALIASES.get(raw, raw)


class SpecStatus(str, Enum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class ImplementationStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    CONFLICT = "conflict"


class ChangeAction(str, Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass(frozen=True)
class SpecValidationIssue:
    field: str
    message: str
    severity: str = "error"

    def to_dict(self) -> Dict[str, Any]:
        return {"field": self.field, "message": self.message, "severity": self.severity}


@dataclass(frozen=True)
class AcceptanceCriterion:
    id: str
    description: str
    verification: str
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "verification": self.verification,
            "required": bool(self.required),
        }


@dataclass(frozen=True)
class DependencyDeclaration:
    spec_id: str
    relationship: str = "requires"
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"spec_id": self.spec_id, "relationship": self.relationship, "reason": self.reason}


@dataclass(frozen=True)
class SpecDocument:
    """Machine-readable v1.1 specification document produced by Claude."""

    spec_id: str
    version: str
    date: str
    author: str
    status: str
    mission: str
    scope: str
    non_goals: List[str]
    target_modules: List[str]
    allowed_files: List[str]
    forbidden_files: List[str]
    dependencies: List[DependencyDeclaration]
    supersedes: List[str]
    contracts: List[str]
    implementation_requirements: List[str]
    acceptance_criteria: List[AcceptanceCriterion]
    rollback_expectations: List[str]
    deploy_impact: List[str]
    risks: List[str]
    title: str = ""
    risk_level: str = "medium"
    human_approval_required: bool = True
    deploy_gate_required: bool = True
    notes: List[str] = field(default_factory=list)
    contract: str = SPEC_DOCUMENT_CONTRACT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "spec_id": self.spec_id,
            "version": self.version,
            "date": self.date,
            "author": self.author,
            "status": normalize_status(self.status),
            "mission": self.mission,
            "scope": self.scope,
            "non_goals": list(self.non_goals),
            "target_modules": list(self.target_modules),
            "allowed_files": list(self.allowed_files),
            "forbidden_files": list(self.forbidden_files),
            "dependencies": [d.to_dict() for d in self.dependencies],
            "supersedes": list(self.supersedes),
            "contracts": list(self.contracts),
            "implementation_requirements": list(self.implementation_requirements),
            "acceptance_criteria": [c.to_dict() for c in self.acceptance_criteria],
            "rollback_expectations": list(self.rollback_expectations),
            "deploy_impact": list(self.deploy_impact),
            "risks": list(self.risks),
            "title": self.title,
            "risk_level": self.risk_level,
            "human_approval_required": bool(self.human_approval_required),
            "deploy_gate_required": bool(self.deploy_gate_required),
            "notes": list(self.notes),
        }

    def export_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)


@dataclass(frozen=True)
class ChangeTrace:
    """First-class file-level trace for rollback and audit."""

    file_path: str
    spec_id: str
    action: str
    reason: str
    timestamp: str
    previous_hash: str
    contract: str = CHANGE_TRACE_CONTRACT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "file_path": self.file_path,
            "spec_id": self.spec_id,
            "action": self.action,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
        }


@dataclass(frozen=True)
class ImplementationReport:
    """v1.1 implementation report returned by the implementation engine."""

    spec_id: str
    implemented_version: str
    status: str
    human_approval_required: bool
    files_modified: List[str]
    files_created: List[str]
    files_deleted: List[str]
    change_traces: List[ChangeTrace]
    contracts_implemented: List[str]
    tests_added: List[str]
    verification_results: Dict[str, Any]
    conflicts: List[str] = field(default_factory=list)
    deviations: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    generated_at: str = field(default_factory=utc_now)
    contract: str = IMPLEMENTATION_REPORT_CONTRACT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "spec_id": self.spec_id,
            "implemented_version": self.implemented_version,
            "status": self.status,
            "human_approval_required": bool(self.human_approval_required),
            "changes": {
                "files_modified": list(self.files_modified),
                "files_created": list(self.files_created),
                "files_deleted": list(self.files_deleted),
                "change_traces": [trace.to_dict() for trace in self.change_traces],
            },
            "results": {
                "contracts_implemented": list(self.contracts_implemented),
                "tests_added": list(self.tests_added),
                "verification_results": dict(self.verification_results),
            },
            "issues": {"conflicts": list(self.conflicts), "deviations": list(self.deviations)},
            "notes": list(self.notes),
            "generated_at": self.generated_at,
        }

    def export_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str)


@dataclass(frozen=True)
class SpecRegistryEntry:
    spec_id: str
    version: str
    status: str
    path: str
    dependencies: List[str] = field(default_factory=list)
    supersedes: List[str] = field(default_factory=list)
    updated_at: str = field(default_factory=utc_now)
    human_approval_required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "version": self.version,
            "status": normalize_status(self.status),
            "path": self.path,
            "dependencies": list(self.dependencies),
            "supersedes": list(self.supersedes),
            "updated_at": self.updated_at,
            "human_approval_required": bool(self.human_approval_required),
        }


@dataclass(frozen=True)
class SpecRegistry:
    project: str
    entries: List[SpecRegistryEntry]
    protocol_version: str = SPEC_PROTOCOL_VERSION
    generated_at: str = field(default_factory=utc_now)
    contract: str = SPEC_REGISTRY_CONTRACT
    policy: str = "contract-first implementation; no verified status without human approval and 100% acceptance criteria"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "project": self.project,
            "protocol_version": self.protocol_version,
            "generated_at": self.generated_at,
            "policy": self.policy,
            "specs": [entry.to_dict() for entry in self.entries],
        }


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def _as_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _as_criterion(value: Any) -> Optional[AcceptanceCriterion]:
    if isinstance(value, AcceptanceCriterion):
        return value
    if not isinstance(value, dict):
        return None
    if not _is_nonempty_string(value.get("id")):
        return None
    if not _is_nonempty_string(value.get("description")):
        return None
    if not _is_nonempty_string(value.get("verification")):
        return None
    return AcceptanceCriterion(
        id=value["id"].strip(),
        description=value["description"].strip(),
        verification=value["verification"].strip(),
        required=bool(value.get("required", True)),
    )


def _as_dependency(value: Any) -> Optional[DependencyDeclaration]:
    if isinstance(value, DependencyDeclaration):
        return value
    if not isinstance(value, dict):
        return None
    if not _is_nonempty_string(value.get("spec_id")):
        return None
    return DependencyDeclaration(
        spec_id=value["spec_id"].strip(),
        relationship=str(value.get("relationship", "requires") or "requires"),
        reason=str(value.get("reason", "") or ""),
    )


def _flatten_legacy_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Accept v1.0-style payloads and normalize them into v1.1 shape."""
    out = dict(payload)
    if "purpose" in out and "mission" not in out:
        out["mission"] = out.get("purpose")
    if "owner" in out and "author" not in out:
        out["author"] = out.get("owner")
    if "created_at" in out and "date" not in out:
        out["date"] = out.get("created_at")
    if "rollback_plan" in out and "rollback_expectations" not in out:
        out["rollback_expectations"] = _as_string_list(out.get("rollback_plan"))
    if "target_modules" in out and "modules" not in out:
        out["modules"] = out.get("target_modules")
    out.setdefault("scope", out.get("title", out.get("mission", "")))
    out.setdefault("non_goals", [])
    out.setdefault("supersedes", [])
    out.setdefault("contracts", [])
    out.setdefault("implementation_requirements", [])
    out.setdefault("deploy_impact", [])
    out.setdefault("risks", [])
    out.setdefault("dependencies", [])
    return out


def validate_spec_payload(payload: Dict[str, Any]) -> Tuple[bool, List[SpecValidationIssue]]:
    """Validate a raw v1.1 spec payload without mutating it."""
    issues: List[SpecValidationIssue] = []
    if not isinstance(payload, dict):
        return False, [SpecValidationIssue("payload", "spec payload must be a dictionary")]
    payload = _flatten_legacy_payload(payload)

    required_strings = ["spec_id", "version", "date", "author", "status", "mission", "scope"]
    for field_name in required_strings:
        if not _is_nonempty_string(payload.get(field_name)):
            issues.append(SpecValidationIssue(field_name, "must be a non-empty string"))

    status = normalize_status(payload.get("status", ""))
    if _is_nonempty_string(status) and status not in VALID_SPEC_STATUSES:
        issues.append(SpecValidationIssue("status", f"must be one of {sorted(VALID_SPEC_STATUSES)}"))

    risk = payload.get("risk_level", "medium")
    if risk not in VALID_RISK_LEVELS:
        issues.append(SpecValidationIssue("risk_level", f"must be one of {sorted(VALID_RISK_LEVELS)}"))

    for list_field in (
        "modules", "allowed_files", "forbidden_files", "non_goals", "supersedes",
        "contracts", "implementation_requirements", "rollback_expectations", "deploy_impact", "risks",
    ):
        if list_field in {"modules", "allowed_files", "forbidden_files"}:
            if not _is_string_list(payload.get(list_field)):
                issues.append(SpecValidationIssue(list_field, "must be a list of non-empty strings"))
        elif list_field in payload and not isinstance(payload.get(list_field), list):
            issues.append(SpecValidationIssue(list_field, "must be a list"))

    criteria = payload.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria:
        issues.append(SpecValidationIssue("acceptance_criteria", "must contain at least one criterion"))
    else:
        seen = set()
        for idx, raw in enumerate(criteria):
            crit = _as_criterion(raw)
            if crit is None:
                issues.append(SpecValidationIssue(f"acceptance_criteria[{idx}]", "criterion must include id, description, and verification"))
                continue
            if crit.id in seen:
                issues.append(SpecValidationIssue(f"acceptance_criteria[{idx}].id", "duplicate criterion id"))
            seen.add(crit.id)

    deps = payload.get("dependencies", [])
    if not isinstance(deps, list):
        issues.append(SpecValidationIssue("dependencies", "must be a list"))
    else:
        for idx, raw in enumerate(deps):
            if _as_dependency(raw) is None:
                issues.append(SpecValidationIssue(f"dependencies[{idx}]", "dependency must include spec_id"))

    if not isinstance(payload.get("deploy_gate_required", True), bool):
        issues.append(SpecValidationIssue("deploy_gate_required", "must be boolean"))
    if not isinstance(payload.get("human_approval_required", True), bool):
        issues.append(SpecValidationIssue("human_approval_required", "must be boolean"))

    return not any(i.severity == "error" for i in issues), issues


def spec_from_payload(payload: Dict[str, Any]) -> SpecDocument:
    """Create a SpecDocument after validation."""
    ok, issues = validate_spec_payload(payload)
    if not ok:
        detail = "; ".join(f"{i.field}: {i.message}" for i in issues)
        raise ValueError(f"invalid spec payload: {detail}")
    payload = _flatten_legacy_payload(payload)
    return SpecDocument(
        spec_id=payload["spec_id"].strip(),
        version=payload["version"].strip(),
        date=payload["date"].strip(),
        author=payload["author"].strip(),
        status=normalize_status(payload["status"]),
        mission=payload["mission"].strip(),
        scope=payload["scope"].strip(),
        non_goals=_as_string_list(payload.get("non_goals", [])),
        target_modules=_as_string_list(payload.get("modules", [])),
        allowed_files=_as_string_list(payload.get("allowed_files", [])),
        forbidden_files=_as_string_list(payload.get("forbidden_files", [])),
        dependencies=[_as_dependency(d) for d in payload.get("dependencies", []) if _as_dependency(d) is not None],
        supersedes=_as_string_list(payload.get("supersedes", [])),
        contracts=_as_string_list(payload.get("contracts", [])),
        implementation_requirements=_as_string_list(payload.get("implementation_requirements", [])),
        acceptance_criteria=[_as_criterion(c) for c in payload["acceptance_criteria"] if _as_criterion(c) is not None],
        rollback_expectations=_as_string_list(payload.get("rollback_expectations", [])),
        deploy_impact=_as_string_list(payload.get("deploy_impact", [])),
        risks=_as_string_list(payload.get("risks", [])),
        title=str(payload.get("title", "") or ""),
        risk_level=str(payload.get("risk_level", "medium") or "medium"),
        human_approval_required=bool(payload.get("human_approval_required", True)),
        deploy_gate_required=bool(payload.get("deploy_gate_required", True)),
        notes=_as_string_list(payload.get("notes", [])),
    )


def validate_change_trace_payload(payload: Dict[str, Any]) -> Tuple[bool, List[SpecValidationIssue]]:
    issues: List[SpecValidationIssue] = []
    if not isinstance(payload, dict):
        return False, [SpecValidationIssue("payload", "change trace must be a dictionary")]
    for field_name in ("file_path", "spec_id", "action", "reason", "timestamp", "previous_hash"):
        if not _is_nonempty_string(payload.get(field_name)):
            issues.append(SpecValidationIssue(field_name, "must be a non-empty string"))
    if _is_nonempty_string(payload.get("action")) and payload.get("action") not in VALID_CHANGE_ACTIONS:
        issues.append(SpecValidationIssue("action", f"must be one of {sorted(VALID_CHANGE_ACTIONS)}"))
    return not issues, issues


def change_trace_from_payload(payload: Dict[str, Any]) -> ChangeTrace:
    ok, issues = validate_change_trace_payload(payload)
    if not ok:
        detail = "; ".join(f"{i.field}: {i.message}" for i in issues)
        raise ValueError(f"invalid change trace: {detail}")
    return ChangeTrace(
        file_path=payload["file_path"].strip(),
        spec_id=payload["spec_id"].strip(),
        action=payload["action"].strip(),
        reason=payload["reason"].strip(),
        timestamp=payload["timestamp"].strip(),
        previous_hash=payload["previous_hash"].strip(),
    )


def validate_implementation_report_payload(payload: Dict[str, Any]) -> Tuple[bool, List[SpecValidationIssue]]:
    issues: List[SpecValidationIssue] = []
    if not isinstance(payload, dict):
        return False, [SpecValidationIssue("payload", "implementation report must be a dictionary")]
    for field_name in ("spec_id", "implemented_version", "status"):
        if not _is_nonempty_string(payload.get(field_name)):
            issues.append(SpecValidationIssue(field_name, "must be a non-empty string"))
    if _is_nonempty_string(payload.get("status")) and payload.get("status") not in VALID_IMPLEMENTATION_STATUSES:
        issues.append(SpecValidationIssue("status", f"must be one of {sorted(VALID_IMPLEMENTATION_STATUSES)}"))
    if payload.get("human_approval_required") is not True:
        issues.append(SpecValidationIssue("human_approval_required", "must be true for implemented to verified gate"))
    changes = payload.get("changes", {})
    if not isinstance(changes, dict):
        issues.append(SpecValidationIssue("changes", "must be a dictionary"))
        changes = {}
    for key in ("files_modified", "files_created", "files_deleted"):
        if not isinstance(changes.get(key, []), list):
            issues.append(SpecValidationIssue(f"changes.{key}", "must be a list"))
    traces = changes.get("change_traces", [])
    if not isinstance(traces, list):
        issues.append(SpecValidationIssue("changes.change_traces", "must be a list"))
    else:
        touched = set(_as_string_list(changes.get("files_modified", [])) + _as_string_list(changes.get("files_created", [])) + _as_string_list(changes.get("files_deleted", [])))
        trace_paths = set()
        for idx, raw in enumerate(traces):
            ok, trace_issues = validate_change_trace_payload(raw if isinstance(raw, dict) else {})
            if not ok:
                for issue in trace_issues:
                    issues.append(SpecValidationIssue(f"changes.change_traces[{idx}].{issue.field}", issue.message))
            elif isinstance(raw, dict):
                trace_paths.add(raw["file_path"])
        missing_traces = sorted(touched - trace_paths)
        if missing_traces:
            issues.append(SpecValidationIssue("changes.change_traces", f"missing file-level trace for {missing_traces}"))
    if payload.get("status") == "conflict" and not _as_string_list(payload.get("issues", {}).get("conflicts", [])):
        issues.append(SpecValidationIssue("issues.conflicts", "required when status is conflict"))
    return not issues, issues


def validate_status_transition(current: str, target: str, guards: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[SpecValidationIssue]]:
    guards = guards or {}
    current_n = normalize_status(current)
    target_n = normalize_status(target)
    issues: List[SpecValidationIssue] = []
    if current_n not in VALID_SPEC_STATUSES:
        issues.append(SpecValidationIssue("current_status", f"unknown status {current}"))
    if target_n not in VALID_SPEC_STATUSES:
        issues.append(SpecValidationIssue("target_status", f"unknown status {target}"))
    if issues:
        return False, issues
    if target_n not in VALID_TRANSITIONS.get(current_n, set()):
        issues.append(SpecValidationIssue("transition", f"illegal transition {current_n} -> {target_n}"))
    if current_n == "draft" and target_n == "accepted" and guards.get("human_approved") is not True:
        issues.append(SpecValidationIssue("human_approved", "draft -> accepted requires human approval"))
    if current_n == "accepted" and target_n == "implemented" and guards.get("implemented_by") not in {"GPT", "ChatGPT", "ChatGPT-5.5-Thinking"}:
        issues.append(SpecValidationIssue("implemented_by", "accepted -> implemented requires GPT implementation marker"))
    if current_n == "implemented" and target_n == "verified":
        if guards.get("human_approved") is not True:
            issues.append(SpecValidationIssue("human_approved", "implemented -> verified requires human approval"))
        if guards.get("acceptance_criteria_met") is not True:
            issues.append(SpecValidationIssue("acceptance_criteria_met", "implemented -> verified requires 100% acceptance criteria"))
        if guards.get("verification_passed") is not True:
            issues.append(SpecValidationIssue("verification_passed", "implemented -> verified requires GPT verification pass"))
    return not issues, issues


def safety_conflict_forces_blocked(has_conflict: bool) -> str:
    return "blocked" if has_conflict else "success"


def minimal_spec_payload(spec_id: str = "SPEC-0001_DOCKING_PROTOCOL_CONTRACTS", title: str = "Docking Protocol Contracts") -> Dict[str, Any]:
    return {
        "spec_id": spec_id,
        "version": "1.1.0",
        "date": "2026-06-27",
        "author": "Claude",
        "status": SpecStatus.DRAFT.value,
        "mission": "Define a versioned implementation contract for NEUROFORGE docking.",
        "scope": "Docking/specification protocol contracts, validation, lifecycle, registry, and reports.",
        "non_goals": ["No feature implementation outside docking protocol", "No heavy dependencies"],
        "modules": ["docking", "core/contracts"],
        "allowed_files": ["docking/**", "core/contracts/**", "tests/test_docking_protocol.py", "deploy_check.py", "main.py", "core/paths.py"],
        "forbidden_files": ["src/self_editor.py", "data/**", "models/**"],
        "dependencies": [],
        "supersedes": [],
        "contracts": [SPEC_DOCUMENT_CONTRACT, IMPLEMENTATION_REPORT_CONTRACT, CHANGE_TRACE_CONTRACT, SPEC_REGISTRY_CONTRACT],
        "implementation_requirements": ["Validate specs before implementation", "Keep docking status read-only"],
        "acceptance_criteria": [
            {
                "id": "AC-001",
                "description": "Spec validates through the docking protocol gate.",
                "verification": "python deploy_check.py --json reports docking_protocol healthy",
                "required": True,
            }
        ],
        "rollback_expectations": ["Revert every file listed in ChangeTrace entries."],
        "deploy_impact": ["Adds a hard deploy gate for docking protocol integrity."],
        "risks": ["Malformed specs must block implementation until corrected."],
        "title": title,
        "risk_level": "medium",
        "human_approval_required": True,
        "deploy_gate_required": True,
        "notes": ["No implementation starts before contract validation."],
    }


def protocol_self_description() -> Dict[str, Any]:
    return {
        "contract": PROTOCOL_SELF_DESCRIPTION_CONTRACT,
        "name": "NEUROFORGE Docking Protocol",
        "version": "1.1.0",
        "spec_protocol": SPEC_PROTOCOL_VERSION,
        "principles": [
            "contract-first architecture",
            "100% verification before verified status",
            "human approval gate before verified",
            "file-level ChangeTrace for every modification",
            "safety/deploy conflict forces blocked report",
            "protocol evolves through SPEC-0000",
        ],
        "layers": {
            "documents": [SPEC_DOCUMENT_CONTRACT, IMPLEMENTATION_REPORT_CONTRACT, CHANGE_TRACE_CONTRACT, SPEC_REGISTRY_CONTRACT],
            "lifecycle": "draft -> accepted -> implemented -> verified -> superseded/rejected with guards",
            "validation": "core.contracts.spec_protocol + docking.protocol.validator",
        },
        "read_only_status_required": True,
    }
