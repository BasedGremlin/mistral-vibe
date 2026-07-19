"""
NEUROFORGE Docking Specification Protocol v1.1.

This module is the stable, read-only implementation surface for validating
Claude-produced SpecDocuments, GPT-produced ImplementationReports, registry
state, lifecycle transitions, and protocol self-description.  It deliberately
performs no writes during status/validation operations.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.paths import get_project_root  # noqa: E402
from core.contracts.spec_protocol import (  # noqa: E402
    CHANGE_TRACE_CONTRACT,
    IMPLEMENTATION_REPORT_CONTRACT,
    SPEC_DOCUMENT_CONTRACT,
    SPEC_PROTOCOL_VERSION,
    SPEC_REGISTRY_CONTRACT,
    SpecDocument,
    minimal_spec_payload,
    protocol_self_description,
    spec_from_payload,
    validate_spec_payload,
)
from docking.protocol.auditor import audit_protocol_layout  # noqa: E402
from docking.protocol.lifecycle import lifecycle_description, transition_allowed  # noqa: E402
from docking.protocol.registry import validate_registry_payload  # noqa: E402
from docking.memory.failure_memory import (  # noqa: E402
    FAILURE_MEMORY_CONTRACT,
    failure_memory_status,
    get_recent_failures as _memory_get_recent_failures,
)
from docking.protocol.validator import (  # noqa: E402
    DOCKING_CNS_VALIDATOR_VERSION,
    SIDE_LETTER_FILE,
    VALIDATION_AUDIT_FILE,
    generate_side_letter,
    get_recent_side_letters as _validator_get_recent_side_letters,
    get_side_letters_for_spec as _validator_get_side_letters_for_spec,
    load_spec_document,
    parse_spec_xml_text,
    pre_implementation_validation,
    validate_implementation_report,
    validate_spec_before_implementation,
    validate_spec_document,
)
from core.contracts.docking import (  # noqa: E402
    CHANGE_TRACE_MODEL_CONTRACT,
    SPEC_DOCUMENT_MODEL_CONTRACT,
    FAILURE_RECORD_MODEL_CONTRACT,
)
try:  # noqa: E402
    from core.contracts.docking.SideLetter import SIDE_LETTER_MODEL_CONTRACT  # type: ignore
except ImportError:  # pragma: no cover - status reports absence safely
    SIDE_LETTER_MODEL_CONTRACT = "missing"

try:  # noqa: E402
    from core.contracts.docking.ImprovementProposal import IMPROVEMENT_PROPOSAL_CONTRACT  # type: ignore
    from core.contracts.docking.ImprovementRecord import IMPROVEMENT_RECORD_CONTRACT, TEST_SUITE_RESULT_CONTRACT  # type: ignore
    from docking.improvement.pipeline import (  # type: ignore
        IMPROVEMENT_PIPELINE_CONTRACT,
        generate_improvement_from_sideletter as _pipeline_generate_improvement_from_sideletter,
        get_improvement_status as _pipeline_get_improvement_status,
        get_recent_improvement_records as _pipeline_get_recent_improvement_records,
        improvement_pipeline_status,
        run_improvement_pipeline as _pipeline_run_improvement_pipeline,
        submit_improvement_proposal as _pipeline_submit_improvement_proposal,
    )
except ImportError:  # pragma: no cover - status reports absence safely
    IMPROVEMENT_PROPOSAL_CONTRACT = "missing"
    IMPROVEMENT_RECORD_CONTRACT = "missing"
    TEST_SUITE_RESULT_CONTRACT = "missing"
    IMPROVEMENT_PIPELINE_CONTRACT = "missing"
    _pipeline_generate_improvement_from_sideletter = None
    _pipeline_get_improvement_status = None
    _pipeline_get_recent_improvement_records = None
    improvement_pipeline_status = None
    _pipeline_run_improvement_pipeline = None
    _pipeline_submit_improvement_proposal = None

try:  # noqa: E402
    from core.contracts.docking.PatchPayload import PATCH_PAYLOAD_CONTRACT  # type: ignore
    from docking.improvement.patch_applier import (  # type: ignore
        PATCH_APPLIER_CONTRACT,
        PATCH_RECORD_FILE,
        apply_patch_payload as _patch_apply_patch_payload,
        get_patch_status as _patch_get_patch_status,
        get_recent_patches as _patch_get_recent_patches,
        patch_applier_status,
        submit_patch_payload as _patch_submit_patch_payload,
    )
except ImportError:  # pragma: no cover - status reports absence safely
    PATCH_PAYLOAD_CONTRACT = "missing"
    PATCH_APPLIER_CONTRACT = "missing"
    PATCH_RECORD_FILE = "patch_records.jsonl"
    _patch_apply_patch_payload = None
    _patch_get_patch_status = None
    _patch_get_recent_patches = None
    patch_applier_status = None
    _patch_submit_patch_payload = None

DOCKING_PROTOCOL_VERSION = "neuroforge.docking_protocol.v1.1"


def docking_paths() -> Dict[str, Path]:
    root = get_project_root()
    docking = root / "docking"
    return {
        "root": root,
        "docking": docking,
        "specs": docking / "specs",
        "reports": docking / "reports",
        "contracts": docking / "contracts",
        "templates": docking / "templates",
        "registry": docking / "registry",
        "protocol": docking / "protocol",
        "audit": docking / "audit",
        "memory": docking / "memory",
        "letters": docking / "letters",
        "improvement": docking / "improvement",
        "archive": docking / "specs" / "archive",
        "spec_template": docking / "templates" / "SPEC_TEMPLATE.xml",
        "registry_file": docking / "registry" / "spec_registry.json",
        "schema_file": docking / "contracts" / "SPEC_DOCUMENT_V1_1.schema.json",
        "audit_file": docking / "audit" / VALIDATION_AUDIT_FILE,
        "failure_log": docking / "memory" / "failure_log.jsonl",
        "side_letters": docking / "letters" / SIDE_LETTER_FILE,
        "improvement_records": docking / "improvement" / "improvement_records.jsonl",
        "patch_records": docking / "improvement" / PATCH_RECORD_FILE,
        "strict_spec_contract": root / "core" / "contracts" / "docking" / "SpecDocument.py",
        "strict_change_trace_contract": root / "core" / "contracts" / "docking" / "ChangeTrace.py",
        "strict_failure_record_contract": root / "core" / "contracts" / "docking" / "FailureRecord.py",
        "strict_side_letter_contract": root / "core" / "contracts" / "docking" / "SideLetter.py",
        "strict_improvement_proposal_contract": root / "core" / "contracts" / "docking" / "ImprovementProposal.py",
        "strict_improvement_record_contract": root / "core" / "contracts" / "docking" / "ImprovementRecord.py",
        "strict_patch_payload_contract": root / "core" / "contracts" / "docking" / "PatchPayload.py",
    }


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def spec_template_xml() -> str:
    """Return the production-strengthened SPEC-0001 v1.2 XML template."""
    return '<SpecDocument>\n    <meta>\n        <spec_id>SPEC-0001_DOCKING_PROTOCOL_CONTRACTS</spec_id>\n        <protocol_version>1.2</protocol_version>\n        <version>1.2.0</version>\n        <date>2026-06-27</date>\n        <author>Claude</author>\n        <status>accepted</status>\n    </meta>\n\n    <mission>\n        Establish the Docking Protocol as the non-negotiable Central Nervous System (CNS) for all future Claude ↔ implementation-engine communication.\n        This foundation must be production-grade, strictly validated, fully auditable, and must include a persistent Failure Memory system so the CNS can learn from every blocked or failed specification.\n        The goal is to create an infrastructure that prevents repeated mistakes and becomes measurably stronger over time under Path A (surgical evolution).\n    </mission>\n\n    <scope>\n        Create the complete docking/ directory structure including memory/.\n        Implement strict Pydantic-based contracts (SpecDocument, ChangeTrace, FailureRecord).\n        Implement a non-bypassable pre_implementation_validation() gate with structured audit logging.\n        Implement a persistent Failure Memory system that records every validation failure and makes it queryable.\n        Create a read-only status + audit + memory surface.\n        Integrate docking health + recent failures into main.py boot sequence.\n    </scope>\n\n    <non_goals>\n        Do not implement full lifecycle state machine, dependency graph, or ImplementationReport writer yet.\n        Do not perform large-scale restructuring or renaming of the existing project.\n        Do not implement any cognitive, action, or evolution modules.\n    </non_goals>\n\n    <target>\n        <modules>\n            <module>docking</module>\n            <module>core/contracts</module>\n        </modules>\n        <allowed_files>\n            docking/**\n            core/contracts/docking/**\n            core/contracts/spec_protocol.py\n            tests/test_docking_protocol.py\n            main.py\n            core/paths.py\n        </allowed_files>\n        <forbidden_files>\n            src/self_editor.py\n            data/**\n            models/**\n            Setup/**\n        </forbidden_files>\n    </target>\n\n    <relationships>\n        <dependencies></dependencies>\n        <supersedes></supersedes>\n    </relationships>\n\n    <definition>\n        <contracts>\n            <contract ref="core/contracts/spec_protocol.py" />\n            <contract ref="core/contracts/docking/SpecDocument.py" />\n            <contract ref="core/contracts/docking/ChangeTrace.py" />\n            <contract ref="core/contracts/docking/FailureRecord.py" />\n        </contracts>\n\n        <implementation_requirements>\n            Create docking/ with specs/, reports/, contracts/, registry/, protocol/, audit/, and memory/ subdirectories.\n            \n            Implement SpecDocument, ChangeTrace, and FailureRecord as strict Pydantic v2 BaseModel classes with full field validation and no extra fields allowed.\n            \n            Implement validate_spec_before_implementation() as the single non-bypassable gate. Every call must:\n              - Perform mechanical validation of the spec\n              - Query recent failures from docking/memory/failure_log.jsonl\n              - Include relevant_past_failures in the validation result\n              - Append a structured JSONL entry to docking/audit/validation_audit.jsonl\n            \n            Implement Failure Memory system in docking/memory/failure_memory.py with at minimum:\n              - log_spec_failure(spec_id, failure_category, reason, issues, timestamp)\n              - get_recent_failures(limit=20)\n              - get_failures_by_category(category)\n              - FailureRecord Pydantic model (spec_id, failure_category, reason, issues, timestamp, validator_version)\n            \n            Create docking/specification_protocol.py exposing:\n              - docking_protocol_status()\n              - get_recent_validation_audit(limit=10)\n              - get_recent_failures(limit=10)\n            \n            Update main.py boot_checks() to call docking_protocol_status() and include both docking health and number of recent failures in the boot report.\n            \n            All code must use type hints, comprehensive docstrings, proper exception handling (no bare excepts), and deterministic behavior.\n        </implementation_requirements>\n\n        <acceptance_criteria>\n            <criterion id="AC-01" type="folder_structure" target="docking/">\n                <description>\n                    docking/specs/, docking/reports/, docking/contracts/, docking/registry/, docking/protocol/, docking/audit/, and docking/memory/ directories exist with correct internal structure.\n                </description>\n                <verification>\n                    Use pathlib to assert all seven directories exist under docking/. Confirm docking/memory/ contains failure_log.jsonl placeholder or is ready for JSONL appends.\n                </verification>\n            </criterion>\n\n            <criterion id="AC-02" type="contract_validation" target="core/contracts/docking/">\n                <description>\n                    SpecDocument.py, ChangeTrace.py, and FailureRecord.py exist, are importable, and define strict Pydantic v2 models. Instantiation with invalid data must raise ValidationError.\n                </description>\n                <verification>\n                    Run python import test + try/except ValidationError test on all three models. All must pass strict validation.\n                </verification>\n            </criterion>\n\n            <criterion id="AC-03" type="test" target="docking/protocol/validator.py">\n                <description>\n                    pre_implementation_validation() exists, correctly accepts valid specs and rejects malformed ones, always writes to audit log, and includes relevant_past_failures in its result when past failures exist for similar issues.\n                </description>\n                <verification>\n                    Call validator with valid SPEC-0001 → status="passed" + audit entry written.\n                    Call validator with malformed spec → status="blocked" + FailureRecord written to failure_log.jsonl + relevant_past_failures shown in result.\n                    Inspect last lines of both audit and failure_log to confirm required fields.\n                </verification>\n            </criterion>\n\n            <criterion id="AC-04" type="memory" target="docking/memory/">\n                <description>\n                    Failure Memory system is functional. log_spec_failure() and get_recent_failures() work correctly. Failures are persisted as structured JSONL.\n                </description>\n                <verification>\n                    Manually log two different failure categories. Call get_recent_failures(5) and get_failures_by_category("bad_acceptance_criteria"). Both must return the correct records with all fields populated.\n                </verification>\n            </criterion>\n\n            <criterion id="AC-05" type="integration" target="main.py">\n                <description>\n                    main.py boot_checks() successfully calls docking protocol status functions and reports both docking health and recent failure count without exceptions.\n                </description>\n                <verification>\n                    Execute boot sequence. Confirm output contains docking health status and something like "Recent Failures: X" or equivalent. No ImportError or AttributeError related to docking or memory.\n                </verification>\n            </criterion>\n        </acceptance_criteria>\n\n        <rollback_expectations>\n            If this spec is rejected or superseded, the entire docking/ folder (including memory/ and all audit + failure logs) must remain intact. No automatic deletion of CNS infrastructure is permitted.\n        </rollback_expectations>\n    </definition>\n\n    <impact>\n        <deploy>\n            Adds mandatory docking CNS health + recent failure count to every boot. Future deploy_check.py runs must validate that the docking layer is present, passes validation, has audit logging active, and has a working failure memory system.\n        </deploy>\n        <risks>\n            Medium if future specs ignore the docking gate or fail to query past failures. Mitigation: Missing audit entries or failure to reference relevant past failures will now be detectable in ImplementationReports and boot checks.\n        </risks>\n    </impact>\n</SpecDocument>\n'

def registry_status() -> Dict[str, Any]:
    paths = docking_paths()
    registry_file = paths["registry_file"]
    if not registry_file.exists():
        return {"ok": False, "error": "spec_registry.json missing", "registered_specs": 0, "entries": []}
    try:
        data = json.loads(registry_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"invalid registry JSON: {exc}", "registered_specs": 0, "entries": []}
    status = validate_registry_payload(data)
    status["error"] = None if status.get("ok") else "registry validation failed"
    return status


def validate_all_specs() -> Dict[str, Any]:
    paths = docking_paths()
    specs_dir = paths["specs"]
    results: List[Dict[str, Any]] = []
    if not specs_dir.exists():
        return {"ok": False, "error": "docking/specs missing", "results": []}
    spec_files = sorted(
        [p for p in specs_dir.rglob("*.xml") if "archive" not in p.relative_to(specs_dir).parts]
        + [p for p in specs_dir.rglob("*.json") if "archive" not in p.relative_to(specs_dir).parts]
    )
    for path in spec_files:
        try:
            spec = load_spec_document(path)
            validation = validate_spec_document(spec)
            validation["path"] = _safe_relative(path, paths["root"])
            results.append(validation)
        except Exception as exc:
            results.append({"ok": False, "path": _safe_relative(path, paths["root"]), "error": f"{type(exc).__name__}: {exc}"})
    return {
        "ok": all(r.get("ok") for r in results),
        "spec_count": len(results),
        "results": results,
        "error": None if all(r.get("ok") for r in results) else "one or more specs failed validation",
    }



def get_recent_validation_audit(limit: int = 10) -> List[Dict[str, Any]]:
    """Return the most recent validation audit events without mutating state.

    Args:
        limit: Maximum number of events to return. Values below zero are
            treated as zero.

    Returns:
        A list of structured JSON objects from validation_audit.jsonl. Invalid
        lines are returned as diagnostic records instead of raising.
    """
    paths = docking_paths()
    audit_file = paths["audit_file"]
    safe_limit = max(0, int(limit))
    if safe_limit == 0 or not audit_file.exists():
        return []
    try:
        lines = audit_file.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [{"status": "error", "error": f"{type(exc).__name__}: {exc}"}]
    events: List[Dict[str, Any]] = []
    for line in lines[-safe_limit:]:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            event = {"status": "malformed", "error": str(exc), "raw": line}
        events.append(event)
    return events



def get_recent_failures(limit: int = 10) -> List[Dict[str, Any]]:
    """Return recent Failure Memory records without mutating state."""
    return _memory_get_recent_failures(limit)


def get_recent_side_letters(limit: int = 10) -> List[Dict[str, Any]]:
    """Return recent SideLetters without mutating state."""
    return _validator_get_recent_side_letters(limit)


def get_side_letters_for_spec(spec_id: str) -> List[Dict[str, Any]]:
    """Return SideLetters for a SPEC identifier without mutating state."""
    return _validator_get_side_letters_for_spec(spec_id)


def submit_improvement_proposal(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """Submit an ImprovementProposal through the CNS pipeline."""
    if _pipeline_submit_improvement_proposal is None:
        return {"ok": False, "error": "improvement pipeline unavailable"}
    return _pipeline_submit_improvement_proposal(proposal)


def run_improvement_pipeline(proposal_id: str) -> Dict[str, Any]:
    """Run the improvement pipeline for a submitted proposal."""
    if _pipeline_run_improvement_pipeline is None:
        return {"ok": False, "error": "improvement pipeline unavailable"}
    return _pipeline_run_improvement_pipeline(proposal_id)


def get_recent_improvement_records(limit: int = 10) -> List[Dict[str, Any]]:
    """Return recent improvement records without mutating state."""
    if _pipeline_get_recent_improvement_records is None:
        return []
    return _pipeline_get_recent_improvement_records(limit)


def get_improvement_status(proposal_id: str) -> Dict[str, Any]:
    """Return latest improvement status for a proposal without mutating state."""
    if _pipeline_get_improvement_status is None:
        return {"ok": False, "proposal_id": proposal_id, "state": "unknown", "error": "improvement pipeline unavailable"}
    return _pipeline_get_improvement_status(proposal_id)


def generate_improvement_from_sideletter(sideletter: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert a SideLetter proposed_actions payload into proposals."""
    if _pipeline_generate_improvement_from_sideletter is None:
        return []
    return _pipeline_generate_improvement_from_sideletter(sideletter)

def submit_patch_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Submit and persist a PatchPayload without applying it."""
    if _patch_submit_patch_payload is None:
        return {"ok": False, "error": "patch applier unavailable"}
    return _patch_submit_patch_payload(payload)


def apply_patch_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a PatchPayload through the guarded SelfEditor entrypoint."""
    if _patch_apply_patch_payload is None:
        return {"ok": False, "error": "patch applier unavailable"}
    return _patch_apply_patch_payload(payload)


def get_patch_status(patch_id: str) -> Dict[str, Any]:
    """Return latest status for one PatchPayload without mutating state."""
    if _patch_get_patch_status is None:
        return {"ok": False, "patch_id": patch_id, "status": "unknown", "error": "patch applier unavailable"}
    return _patch_get_patch_status(patch_id)


def get_recent_patches(limit: int = 10) -> List[Dict[str, Any]]:
    """Return recent PatchPayload apply records without mutating state."""
    if _patch_get_recent_patches is None:
        return []
    return _patch_get_recent_patches(limit)


def protocol_contract_summary() -> Dict[str, Any]:
    return {
        "protocol": DOCKING_PROTOCOL_VERSION,
        "spec_protocol": SPEC_PROTOCOL_VERSION,
        "contracts": [SPEC_DOCUMENT_CONTRACT, IMPLEMENTATION_REPORT_CONTRACT, CHANGE_TRACE_CONTRACT, SPEC_REGISTRY_CONTRACT],
        "lifecycle": lifecycle_description(),
        "self_description": protocol_self_description(),
    }


def docking_protocol_status() -> Dict[str, Any]:
    """Read-only health for the docking/specification protocol foundation."""
    paths = docking_paths()
    root = paths["root"]
    layout = audit_protocol_layout(paths)
    template_valid = False
    template_error: Optional[str] = None
    try:
        if paths["spec_template"].exists():
            spec = load_spec_document(paths["spec_template"])
            template_valid = validate_spec_document(spec).get("ok", False)
        else:
            spec = parse_spec_xml_text(spec_template_xml())
            template_valid = validate_spec_document(spec).get("ok", False)
    except Exception as exc:
        template_error = f"{type(exc).__name__}: {exc}"
    registry = registry_status()
    specs = validate_all_specs()
    lifecycle = lifecycle_description()
    contracts = protocol_contract_summary()
    recent_audit = get_recent_validation_audit(10)
    recent_failures = get_recent_failures(10)
    side_letters = get_recent_side_letters(10)
    last_side_letter_timestamp = side_letters[-1].get("timestamp") if side_letters else None
    improvement_records = get_recent_improvement_records(10)
    improvement_status = improvement_pipeline_status() if improvement_pipeline_status is not None else {"ok": False, "error": "improvement pipeline unavailable"}
    recent_patches = get_recent_patches(10)
    patch_status = patch_applier_status() if patch_applier_status is not None else {"ok": False, "error": "patch applier unavailable"}
    failure_memory = failure_memory_status()
    cns_contracts_ok = bool(
        paths["strict_spec_contract"].exists()
        and paths["strict_change_trace_contract"].exists()
        and paths["strict_failure_record_contract"].exists()
        and paths["strict_side_letter_contract"].exists()
        and paths["strict_improvement_proposal_contract"].exists()
        and paths["strict_improvement_record_contract"].exists()
        and paths["strict_patch_payload_contract"].exists()
    )
    audit_queryable = isinstance(recent_audit, list)
    failure_memory_ok = bool(failure_memory.get("ok") and isinstance(recent_failures, list))
    side_letters_ok = bool(paths["letters"].exists() and isinstance(side_letters, list))
    improvement_ok = bool(paths["improvement"].exists() and isinstance(improvement_records, list) and improvement_status.get("ok"))
    patch_ok = bool(paths["improvement"].exists() and isinstance(recent_patches, list) and patch_status.get("ok"))
    ok = bool(layout.get("ok") and template_valid and registry.get("ok") and specs.get("ok") and cns_contracts_ok and audit_queryable and failure_memory_ok and side_letters_ok and improvement_ok and patch_ok)
    return {
        "ok": ok,
        "contract": DOCKING_PROTOCOL_VERSION,
        "spec_contract": SPEC_PROTOCOL_VERSION,
        "read_only": True,
        "cns_contract": "neuroforge.docking_cns.v1.2",
        "cns_validator": DOCKING_CNS_VALIDATOR_VERSION,
        "strict_pydantic_contracts": {
            "SpecDocument": SPEC_DOCUMENT_MODEL_CONTRACT,
            "ChangeTrace": CHANGE_TRACE_MODEL_CONTRACT,
            "FailureRecord": FAILURE_RECORD_MODEL_CONTRACT,
            "SideLetter": SIDE_LETTER_MODEL_CONTRACT,
            "ImprovementProposal": IMPROVEMENT_PROPOSAL_CONTRACT,
            "ImprovementRecord": IMPROVEMENT_RECORD_CONTRACT,
            "TestSuiteResult": TEST_SUITE_RESULT_CONTRACT,
            "PatchPayload": PATCH_PAYLOAD_CONTRACT,
            "present": cns_contracts_ok,
        },
        "failure_memory": {
            "contract": FAILURE_MEMORY_CONTRACT,
            "failure_log": _safe_relative(paths["failure_log"], root),
            "queryable": isinstance(recent_failures, list),
            "recent_count": len(recent_failures),
            "recent_failures": recent_failures,
            "status": failure_memory,
        },
        "side_letters": {
            "contract": SIDE_LETTER_MODEL_CONTRACT,
            "side_letters_file": _safe_relative(paths["side_letters"], root),
            "queryable": isinstance(side_letters, list),
            "side_letter_count": len(side_letters),
            "last_side_letter_timestamp": last_side_letter_timestamp,
            "recent_side_letters": side_letters,
        },
        "side_letter_count": len(side_letters),
        "last_side_letter_timestamp": last_side_letter_timestamp,
        "improvement": {
            "contract": IMPROVEMENT_PIPELINE_CONTRACT,
            "records_file": _safe_relative(paths["improvement_records"], root),
            "queryable": isinstance(improvement_records, list),
            "recent_count": len(improvement_records),
            "recent_records": improvement_records,
            "status": improvement_status,
        },
        "improvement_record_count": len(improvement_records),
        "patch_applier": {
            "contract": PATCH_APPLIER_CONTRACT,
            "patch_payload_contract": PATCH_PAYLOAD_CONTRACT,
            "records_file": _safe_relative(paths["patch_records"], root),
            "queryable": isinstance(recent_patches, list),
            "recent_count": len(recent_patches),
            "recent_patches": recent_patches,
            "status": patch_status,
            "self_editor_entrypoint": "docking.improvement.patch_applier.apply_patch_payload",
        },
        "patch_count": len(recent_patches),
        "audit": {
            "audit_file": _safe_relative(paths["audit_file"], root),
            "queryable": audit_queryable,
            "recent_count": len(recent_audit),
            "recent_events": recent_audit,
        },
        "paths": {k: _safe_relative(v, root) for k, v in paths.items()},
        "layout": layout,
        "dirs": layout.get("dirs", {}),
        "required_files": layout.get("required_files", {}),
        "template_valid": template_valid,
        "template_error": template_error,
        "registry": registry,
        "spec_validation": specs,
        "lifecycle": lifecycle,
        "contracts": contracts,
        "protocol_self_description": protocol_self_description(),
        "single_source_of_truth": "core.contracts.spec_protocol",
        "implementation_surface": "docking.specification_protocol",
        "validator_surface": "docking.protocol.validator",
        "pre_implementation_gate": "docking.protocol.validator.validate_spec_before_implementation",
        "lifecycle_surface": "docking.protocol.lifecycle",
        "registry_surface": "docking.protocol.registry",
        "auditor_surface": "docking.protocol.auditor",
        "human_approval_gate": "implemented -> verified requires human_approved + 100% acceptance criteria",
        "error": None if ok else "docking protocol CNS foundation incomplete or invalid",
    }


# Backward-compatible re-exports for existing tests/imports.
__all__ = [
    "DOCKING_PROTOCOL_VERSION",
    "docking_paths",
    "parse_spec_xml_text",
    "load_spec_document",
    "spec_template_xml",
    "validate_spec_document",
    "pre_implementation_validation",
    "validate_spec_before_implementation",
    "get_recent_validation_audit",
    "get_recent_failures",
    "get_recent_side_letters",
    "get_side_letters_for_spec",
    "submit_improvement_proposal",
    "run_improvement_pipeline",
    "get_recent_improvement_records",
    "get_improvement_status",
    "generate_improvement_from_sideletter",
    "submit_patch_payload",
    "apply_patch_payload",
    "get_patch_status",
    "get_recent_patches",
    "registry_status",
    "validate_all_specs",
    "docking_protocol_status",
    "transition_allowed",
    "validate_implementation_report",
    "protocol_contract_summary",
]


if __name__ == "__main__":
    print(json.dumps(docking_protocol_status(), indent=2, default=str))
