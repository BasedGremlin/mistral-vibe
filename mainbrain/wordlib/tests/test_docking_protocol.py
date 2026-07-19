import importlib.util
import json
from pathlib import Path

import pytest

from core.contracts.spec_protocol import (
    CHANGE_TRACE_CONTRACT,
    IMPLEMENTATION_REPORT_CONTRACT,
    SPEC_DOCUMENT_CONTRACT,
    SPEC_PROTOCOL_VERSION,
    SPEC_REGISTRY_CONTRACT,
    ChangeTrace,
    ImplementationReport,
    SpecDocument,
    minimal_spec_payload,
    protocol_self_description,
    spec_from_payload,
    validate_implementation_report_payload,
    validate_spec_payload,
    validate_status_transition,
)
from docking.specification_protocol import (
    DOCKING_PROTOCOL_VERSION,
    docking_paths,
    docking_protocol_status,
    get_recent_validation_audit,
    get_recent_failures,
    load_spec_document,
    parse_spec_xml_text,
    pre_implementation_validation,
    protocol_contract_summary,
    registry_status,
    spec_template_xml,
    transition_allowed,
    validate_all_specs,
    validate_implementation_report,
    validate_spec_before_implementation,
)
from core.contracts.docking.SpecDocument import SpecDocument as StrictSpecDocument, SPEC_DOCUMENT_MODEL_CONTRACT
from core.contracts.docking.ChangeTrace import ChangeTrace as StrictChangeTrace, CHANGE_TRACE_MODEL_CONTRACT
from core.contracts.docking.FailureRecord import FailureRecord as StrictFailureRecord, FAILURE_RECORD_MODEL_CONTRACT
from docking.memory.failure_memory import log_spec_failure, get_failures_by_category, failure_memory_status
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def test_spec_contract_accepts_v1_1_minimal_payload():
    payload = minimal_spec_payload("SPEC-TEST-001", "Test Spec")
    ok, issues = validate_spec_payload(payload)
    assert ok, [i.to_dict() for i in issues]
    spec = spec_from_payload(payload)
    assert isinstance(spec, SpecDocument)
    assert spec.spec_id == "SPEC-TEST-001"
    assert spec.status == "draft"
    assert spec.to_dict()["contract"] == SPEC_DOCUMENT_CONTRACT
    assert SPEC_PROTOCOL_VERSION == "neuroforge.spec_protocol.v1.1"
    assert "SPEC-TEST-001" in spec.export_json()


def test_spec_contract_rejects_missing_acceptance_criteria():
    payload = minimal_spec_payload()
    payload["acceptance_criteria"] = []
    ok, issues = validate_spec_payload(payload)
    assert ok is False
    assert any(issue.field == "acceptance_criteria" for issue in issues)
    with pytest.raises(ValueError):
        spec_from_payload(payload)


def test_v1_1_xml_template_parses_into_contract():
    spec = parse_spec_xml_text(spec_template_xml())
    assert spec.spec_id == "SPEC-0001_DOCKING_PROTOCOL_CONTRACTS"
    assert spec.acceptance_criteria[0].id == "AC-01"
    assert "docking" in spec.target_modules
    assert spec.status == "accepted"
    assert "core/contracts/docking/SpecDocument.py" in spec.contracts


def test_formal_lifecycle_state_machine_guards_verified_status():
    ok, issues = validate_status_transition("draft", "accepted", {"human_approved": True})
    assert ok, [i.to_dict() for i in issues]
    rejected = transition_allowed("implemented", "verified", {"verification_passed": True, "acceptance_criteria_met": True, "human_approved": False})
    assert rejected["ok"] is False
    assert any("human approval" in issue["message"] for issue in rejected["issues"])
    accepted = transition_allowed("implemented", "verified", {"verification_passed": True, "acceptance_criteria_met": True, "human_approved": True})
    assert accepted["ok"] is True


def test_change_trace_is_first_class_file_level_contract():
    trace = ChangeTrace(
        file_path="core/contracts/spec_protocol.py",
        spec_id="SPEC-TEST-001",
        action="modified",
        reason="Validate v1.1 ChangeTrace contract.",
        timestamp="2026-06-27T00:00:00+00:00",
        previous_hash="sha256:previous-or-none",
    )
    data = trace.to_dict()
    assert data["contract"] == CHANGE_TRACE_CONTRACT
    assert data["action"] == "modified"
    assert data["previous_hash"].startswith("sha256:")


def test_implementation_report_requires_trace_for_every_file_and_human_gate():
    trace = ChangeTrace(
        file_path="docking/specification_protocol.py",
        spec_id="SPEC-TEST-001",
        action="modified",
        reason="Implement docking v1.1.",
        timestamp="2026-06-27T00:00:00+00:00",
        previous_hash="sha256:previous-or-none",
    )
    report = ImplementationReport(
        spec_id="SPEC-TEST-001",
        implemented_version="1.1.0",
        status="success",
        human_approval_required=True,
        files_modified=["docking/specification_protocol.py"],
        files_created=[],
        files_deleted=[],
        change_traces=[trace],
        contracts_implemented=[SPEC_DOCUMENT_CONTRACT, IMPLEMENTATION_REPORT_CONTRACT, CHANGE_TRACE_CONTRACT, SPEC_REGISTRY_CONTRACT],
        tests_added=["tests/test_docking_protocol.py"],
        verification_results={"pytest": True, "deploy_check": True},
    )
    data = report.to_dict()
    assert data["contract"] == IMPLEMENTATION_REPORT_CONTRACT
    ok, issues = validate_implementation_report_payload(data)
    assert ok, [i.to_dict() for i in issues]
    assert validate_implementation_report(data)["ok"] is True

    missing = report.to_dict()
    missing["changes"]["change_traces"] = []
    ok, issues = validate_implementation_report_payload(missing)
    assert ok is False
    assert any("missing file-level trace" in i.message for i in issues)


def test_conflict_report_requires_conflicts():
    trace = ChangeTrace(
        file_path="deploy_check.py",
        spec_id="SPEC-CONFLICT",
        action="modified",
        reason="Conflict validation.",
        timestamp="2026-06-27T00:00:00+00:00",
        previous_hash="sha256:previous-or-none",
    )
    report = ImplementationReport(
        spec_id="SPEC-CONFLICT",
        implemented_version="1.1.0",
        status="conflict",
        human_approval_required=True,
        files_modified=["deploy_check.py"],
        files_created=[],
        files_deleted=[],
        change_traces=[trace],
        contracts_implemented=[],
        tests_added=[],
        verification_results={},
        conflicts=[],
    ).to_dict()
    ok, issues = validate_implementation_report_payload(report)
    assert ok is False
    assert any(issue.field == "issues.conflicts" for issue in issues)


def test_docking_paths_are_project_local_and_include_v1_1_folders():
    paths = docking_paths()
    root = paths["root"].resolve()
    for name, path in paths.items():
        assert str(path.resolve()).startswith(str(root)), name
    assert paths["specs"].name == "specs"
    assert paths["reports"].name == "reports"
    assert paths["contracts"].name == "contracts"
    assert paths["protocol"].name == "protocol"
    assert paths["audit"].name == "audit"
    assert paths["memory"].name == "memory"
    assert paths["strict_spec_contract"].name == "SpecDocument.py"
    assert paths["strict_change_trace_contract"].name == "ChangeTrace.py"
    assert paths["strict_failure_record_contract"].name == "FailureRecord.py"


def test_docking_protocol_status_is_read_only_and_healthy_v1_1():
    before = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "docking").rglob("*") if p.is_file())
    status = docking_protocol_status()
    after = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "docking").rglob("*") if p.is_file())
    assert status["ok"] is True, status
    assert status["contract"] == DOCKING_PROTOCOL_VERSION
    assert status["spec_contract"] == SPEC_PROTOCOL_VERSION
    assert status["read_only"] is True
    assert status["template_valid"] is True
    assert status["lifecycle"]["contract"] == "neuroforge.docking.lifecycle.v1.1"
    assert status["cns_contract"] == "neuroforge.docking_cns.v1.2"
    assert status["strict_pydantic_contracts"]["present"] is True
    assert status["audit"]["queryable"] is True
    assert status["failure_memory"]["queryable"] is True
    assert status["strict_pydantic_contracts"]["FailureRecord"] == FAILURE_RECORD_MODEL_CONTRACT
    assert before == after


def test_registry_status_is_valid_and_empty_by_default_v1_1():
    status = registry_status()
    assert status["ok"] is True, status
    assert status["registry_contract"] == SPEC_REGISTRY_CONTRACT
    assert status["registered_specs"] == 0
    assert status["entries"] == []


def test_validate_all_specs_handles_readme_only_directory():
    status = validate_all_specs()
    assert status["ok"] is True, status
    assert status["spec_count"] == 0
    assert status["results"] == []


def test_load_spec_document_from_template_file():
    spec = load_spec_document(ROOT / "docking" / "templates" / "SPEC_TEMPLATE.xml")
    assert isinstance(spec, SpecDocument)
    assert spec.spec_id == "SPEC-0001_DOCKING_PROTOCOL_CONTRACTS"
    assert spec.author == "Claude"
    assert spec.status == "accepted"


def test_protocol_self_description_and_contract_summary():
    desc = protocol_self_description()
    assert desc["contract"] == "neuroforge.protocol_self_description.v1.1"
    assert desc["version"] == "1.1.0"
    assert any("SPEC-0000" in p for p in desc["principles"])
    summary = protocol_contract_summary()
    assert CHANGE_TRACE_CONTRACT in summary["contracts"]
    assert summary["lifecycle"]["contract"] == "neuroforge.docking.lifecycle.v1.1"


def test_deploy_check_docking_gate_v1_1():
    spec = importlib.util.spec_from_file_location("deploy_check", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.check_docking_protocol()
    assert result["healthy"] is True, result
    assert result["read_only"] is True
    assert result["contract"] == DOCKING_PROTOCOL_VERSION
    assert result["spec_contract"] == SPEC_PROTOCOL_VERSION
    assert result["document_contract"] == SPEC_DOCUMENT_CONTRACT
    assert result["change_trace_contract"] == CHANGE_TRACE_CONTRACT
    assert result["single_source_of_truth"] == "core.contracts.spec_protocol"
    assert result["cns_contract"] == "neuroforge.docking_cns.v1.2"
    assert result["audit_recent_count"] >= 2



def test_strict_pydantic_contracts_reject_invalid_data():
    with pytest.raises(ValidationError):
        StrictSpecDocument(meta={})
    with pytest.raises(ValidationError):
        StrictSpecDocument(
            meta={
                "spec_id": "SPEC-X",
                "protocol_version": "1.2",
                "version": "1.0.0",
                "date": "2026-06-27",
                "author": "Claude",
                "status": "accepted",
                "extra": "forbidden",
            },
            mission="Establish a serious validated docking foundation.",
            scope="Create strict contracts and audit gate.",
            non_goals="No unrelated modules.",
            target={"modules": ["docking"], "allowed_files": ["docking/**"], "forbidden_files": ["data/**"]},
            relationships={"dependencies": [], "supersedes": []},
            definition={
                "contracts": [{"ref": "core/contracts/docking/SpecDocument.py"}],
                "implementation_requirements": ["Validate before implementation."],
                "acceptance_criteria": [{"id": "AC-1", "type": "test", "target": "x", "description": "d", "verification": "v"}],
                "rollback_expectations": "Keep CNS files.",
            },
            impact={"deploy": "Boot health.", "risks": "Low."},
        )
    with pytest.raises(ValidationError):
        StrictChangeTrace(
            file_path="/absolute/path.py",
            spec_id="SPEC-X",
            action="modified",
            reason="Bad absolute path.",
            timestamp="2026-06-27T00:00:00+00:00",
            previous_hash="sha256:x",
        )
    with pytest.raises(ValidationError):
        StrictFailureRecord(
            spec_id="SPEC-X",
            failure_category="bad/category",
            reason="Bad category.",
            issues=[],
            timestamp="not-a-date",
            validator_version="v",
        )
    assert SPEC_DOCUMENT_MODEL_CONTRACT.endswith("v1.2")
    assert CHANGE_TRACE_MODEL_CONTRACT.endswith("v1.2")


def test_pre_implementation_validation_accepts_valid_spec_and_writes_audit():
    before = len(get_recent_validation_audit(10000))
    result = validate_spec_before_implementation(spec_template_xml())
    after_events = get_recent_validation_audit(10000)
    assert result["status"] == "passed", result
    assert result["ok"] is True
    assert result["validated_before_modification"] is True
    assert result["failure_memory_queried"] is True
    assert "relevant_past_failures" in result
    assert len(after_events) >= before + 1
    last = after_events[-1]
    assert last["spec_id"] == "SPEC-0001_DOCKING_PROTOCOL_CONTRACTS"
    assert last["status"] == "passed"
    assert last["validator_version"] == "neuroforge.docking.cns.validator.v1.2"


def test_pre_implementation_validation_rejects_malformed_spec_and_audits_block():
    result = pre_implementation_validation("<SpecDocument><meta></meta></SpecDocument>")
    assert result["status"] == "blocked"
    assert result["ok"] is False
    assert result["issues"]
    assert result["failure_record"]["contract"] == FAILURE_RECORD_MODEL_CONTRACT
    assert result["relevant_past_failures"]
    last = get_recent_validation_audit(1)[0]
    assert last["status"] == "blocked"
    assert "issues" in last


def test_recent_validation_audit_is_queryable_and_limited():
    validate_spec_before_implementation(spec_template_xml())
    validate_spec_before_implementation("<SpecDocument><meta></meta></SpecDocument>")
    events = get_recent_validation_audit(2)
    assert len(events) == 2
    assert all("timestamp" in event and "spec_id" in event and "status" in event for event in events)


def test_failure_memory_logs_and_queries_categories():
    record_a = log_spec_failure(
        spec_id="SPEC-FAIL-A",
        failure_category="bad_acceptance_criteria",
        reason="Acceptance criteria lacked verification.",
        issues=[{"field": "acceptance_criteria", "message": "missing verification"}],
        timestamp="2026-06-27T00:00:00+00:00",
    )
    record_b = log_spec_failure(
        spec_id="SPEC-FAIL-B",
        failure_category="missing_meta",
        reason="Spec ID missing.",
        issues=[{"field": "meta.spec_id", "message": "missing"}],
        timestamp="2026-06-27T00:01:00+00:00",
    )
    recent = get_recent_failures(5)
    assert any(item.get("spec_id") == record_a["spec_id"] for item in recent)
    assert any(item.get("spec_id") == record_b["spec_id"] for item in recent)
    bad_ac = get_failures_by_category("bad_acceptance_criteria")
    assert any(item.get("spec_id") == "SPEC-FAIL-A" for item in bad_ac)
    status = failure_memory_status()
    assert status["ok"] is True
    assert status["contract"] == "neuroforge.docking.failure_memory.v1.2"


def test_validation_result_surfaces_relevant_past_failures():
    log_spec_failure(
        spec_id="SPEC-PAST-BAD-AC",
        failure_category="bad_acceptance_criteria",
        reason="Past acceptance issue.",
        issues=[{"field": "definition.acceptance_criteria", "message": "missing verification"}],
        timestamp="2026-06-27T00:02:00+00:00",
    )
    malformed = spec_template_xml().replace("<verification>", "<verification>").replace("</verification>", "</verification>")
    # Remove all verification text to trigger bad_acceptance_criteria through strict validation.
    malformed = malformed.replace("Use pathlib to assert all seven directories exist under docking/. Confirm docking/memory/ contains failure_log.jsonl placeholder or is ready for JSONL appends.", "")
    result = pre_implementation_validation(malformed)
    assert result["status"] == "blocked"
    assert result["failure_record"]["failure_category"] == "bad_acceptance_criteria"
    assert any(item.get("failure_category") == "bad_acceptance_criteria" for item in result["relevant_past_failures"])


def test_cns_status_reports_failure_memory_count():
    status = docking_protocol_status()
    assert status["ok"] is True, status
    assert status["failure_memory"]["contract"] == "neuroforge.docking.failure_memory.v1.2"
    assert isinstance(status["failure_memory"]["recent_count"], int)
    assert status["paths"]["failure_log"].endswith("docking/memory/failure_log.jsonl")
