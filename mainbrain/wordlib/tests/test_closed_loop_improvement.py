from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.contracts.docking.ImprovementProposal import ImprovementProposal
from core.contracts.docking.ImprovementRecord import ImprovementRecord, TestSuiteResult
from docking.improvement.selector import TestSelector
from docking.improvement.tester import FastTargetedTester
from docking.improvement import pipeline
from docking.specification_protocol import (
    generate_improvement_from_sideletter,
    get_improvement_status,
    get_recent_improvement_records,
    run_improvement_pipeline,
    submit_improvement_proposal,
)


def _proposal(**overrides):
    payload = {
        "severity": 0.2,
        "priority": 0.7,
        "target_modules": ["docking/specification_protocol.py"],
        "target_functions": ["docking_protocol_status"],
        "description": "Strengthen docking status validation without touching unrelated modules.",
        "expected_outcome": "Relevant docking tests pass and no full suite is selected.",
        "source_sideletter_id": "SPEC-0002_SIDELETTER_PROTOCOL",
        "proposed_actions": [
            {
                "type": "strengthen_validation",
                "target": "docking/specification_protocol.py",
                "description": "Improve status validation.",
                "priority": 0.7,
            }
        ],
    }
    payload.update(overrides)
    return payload


def _prepare_tmp_root(tmp_path: Path) -> Path:
    for rel in ("docking/audit", "docking/improvement", "docking/memory", "tests"):
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_docking_protocol.py").write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")
    (tmp_path / "tests" / "test_closed_loop_improvement.py").write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")
    return tmp_path


def test_improvement_contracts_are_strict() -> None:
    proposal = ImprovementProposal.model_validate(_proposal())
    assert proposal.confidence if hasattr(proposal, "confidence") else proposal.priority == 0.7
    with pytest.raises(ValidationError):
        ImprovementProposal.model_validate({**_proposal(), "severity": 1.4})
    with pytest.raises(ValidationError):
        ImprovementProposal.model_validate({**_proposal(), "unexpected": True})
    result = TestSuiteResult(
        passed=True,
        duration=0.01,
        selected_tests=["tests/test_docking_protocol.py"],
        failing_tests=[],
        command=["pytest"],
        resource_limits={"timeout_seconds": 30},
    )
    record = ImprovementRecord(
        record_id="IR_test",
        proposal_id="IP_test",
        state="tested",
        transition="test transition",
        proposal=proposal.model_copy(update={"proposal_id": "IP_test"}),
        test_result=result,
        timestamp="2026-06-27T12:00:00+00:00",
    )
    assert record.test_result and record.test_result.passed
    with pytest.raises(ValidationError):
        ImprovementRecord.model_validate({**record.model_dump(), "state": "invalid"})


def test_selector_maps_relevant_tests_without_full_suite(tmp_path: Path) -> None:
    root = _prepare_tmp_root(tmp_path)
    proposal = ImprovementProposal.model_validate(_proposal())
    selected = TestSelector(root).select_tests(proposal)
    assert selected == ["tests/test_docking_protocol.py"]


def test_fast_tester_fails_when_no_relevant_tests_are_mapped(tmp_path: Path) -> None:
    root = _prepare_tmp_root(tmp_path)
    proposal = ImprovementProposal.model_validate(
        _proposal(target_modules=["unknown/module.py"], target_functions=[], description="No known mapping.", expected_outcome="No known mapping.", proposed_actions=[])
    )
    result = FastTargetedTester(root, timeout_seconds=1).run(proposal)
    assert result.passed is False
    assert result.selected_tests == []
    assert "no relevant tests selected" in result.failing_tests


def test_submit_proposal_creates_audit_and_change_trace(tmp_path: Path) -> None:
    root = _prepare_tmp_root(tmp_path)
    submitted = pipeline.submit_improvement_proposal(_proposal(), project_root=root)
    proposal_id = submitted["proposal"]["proposal_id"]
    assert proposal_id.startswith("IP_")
    records = pipeline.get_recent_improvement_records(5, project_root=root)
    assert records[-1]["state"] == "proposed"
    assert records[-1]["change_traces"]
    audit_lines = (root / "docking" / "audit" / "validation_audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(audit_lines[-1])["status"] == "improvement_proposed"


def test_pipeline_blocks_selfeditor_when_tests_fail(monkeypatch, tmp_path: Path) -> None:
    root = _prepare_tmp_root(tmp_path)
    submitted = pipeline.submit_improvement_proposal(_proposal(), project_root=root)
    proposal_id = submitted["proposal"]["proposal_id"]

    def fail_tests(proposal, **kwargs):
        return TestSuiteResult(
            passed=False,
            duration=0.01,
            selected_tests=["tests/test_docking_protocol.py"],
            failing_tests=["FAILED test_guard"],
            timed_out=False,
            command=["pytest", "tests/test_docking_protocol.py"],
            resource_limits={"timeout_seconds": 30},
        )

    monkeypatch.setattr(pipeline, "run_fast_targeted_tests", fail_tests)
    record = pipeline.run_improvement_pipeline(proposal_id, project_root=root)
    assert record["state"] == "rejected"
    assert record["applied"] is False
    assert record["self_editor_gate"]["eligible"] is False
    failures = (root / "docking" / "memory" / "failure_log.jsonl").read_text(encoding="utf-8")
    assert "improvement_rejected" in failures


def test_low_severity_pass_reaches_guarded_apply_path(monkeypatch, tmp_path: Path) -> None:
    root = _prepare_tmp_root(tmp_path)
    submitted = pipeline.submit_improvement_proposal(_proposal(), project_root=root)
    proposal_id = submitted["proposal"]["proposal_id"]

    def pass_tests(proposal, **kwargs):
        return TestSuiteResult(
            passed=True,
            duration=0.01,
            selected_tests=["tests/test_docking_protocol.py"],
            failing_tests=[],
            timed_out=False,
            command=["pytest", "tests/test_docking_protocol.py"],
            resource_limits={"timeout_seconds": 30},
        )

    monkeypatch.setattr(pipeline, "run_fast_targeted_tests", pass_tests)
    record = pipeline.run_improvement_pipeline(proposal_id, project_root=root)
    assert record["state"] == "applied"
    assert record["applied"] is True
    assert record["self_editor_gate"]["called"] is True
    assert "improvement_success" in (root / "docking" / "memory" / "failure_log.jsonl").read_text(encoding="utf-8")


def test_high_severity_requires_human_approval(monkeypatch, tmp_path: Path) -> None:
    root = _prepare_tmp_root(tmp_path)
    submitted = pipeline.submit_improvement_proposal(_proposal(severity=0.9), project_root=root)
    proposal_id = submitted["proposal"]["proposal_id"]

    def pass_tests(proposal, **kwargs):
        return TestSuiteResult(
            passed=True,
            duration=0.01,
            selected_tests=["tests/test_docking_protocol.py"],
            failing_tests=[],
            command=["pytest"],
            resource_limits={"timeout_seconds": 30},
        )

    monkeypatch.setattr(pipeline, "run_fast_targeted_tests", pass_tests)
    record = pipeline.run_improvement_pipeline(proposal_id, project_root=root)
    assert record["state"] == "human_approval"
    assert record["human_approval_required"] is True
    assert record["self_editor_gate"]["eligible"] is False


def test_sideletter_actions_convert_to_improvement_proposals() -> None:
    sideletter = {
        "timestamp": "2026-06-27T12:00:00+00:00",
        "spec_id": "SPEC-0002_SIDELETTER_PROTOCOL",
        "proposed_actions": [
            {
                "type": "improve_matching",
                "target": "docking/protocol/validator.py",
                "description": "Improve signature matching.",
                "priority": 0.6,
            }
        ],
    }
    proposals = pipeline.generate_improvement_from_sideletter(sideletter)
    assert len(proposals) == 1
    assert proposals[0]["source_sideletter_id"] == "SPEC-0002_SIDELETTER_PROTOCOL"
    assert proposals[0]["target_modules"] == ["docking/protocol/validator.py"]


def test_specification_protocol_query_surfaces(monkeypatch, tmp_path: Path) -> None:
    root = _prepare_tmp_root(tmp_path)
    monkeypatch.chdir(root)
    submitted = submit_improvement_proposal(_proposal())
    proposal_id = submitted["proposal"]["proposal_id"]
    status = get_improvement_status(proposal_id)
    assert status["ok"] is True
    assert status["state"] == "proposed"
    records = get_recent_improvement_records(5)
    assert records and records[-1]["proposal_id"] == proposal_id
    converted = generate_improvement_from_sideletter(
        {
            "timestamp": "2026-06-27T12:00:00+00:00",
            "spec_id": "SPEC-0002_SIDELETTER_PROTOCOL",
            "proposed_actions": [
                {
                    "type": "add_test",
                    "target": "docking/improvement/pipeline.py",
                    "description": "Add targeted pipeline tests.",
                    "priority": 0.5,
                }
            ],
        }
    )
    assert converted[0]["target_modules"] == ["docking/improvement/pipeline.py"]


def test_core_contract_targets_require_human_gate(monkeypatch, tmp_path: Path) -> None:
    root = _prepare_tmp_root(tmp_path)
    submitted = pipeline.submit_improvement_proposal(
        _proposal(target_modules=["core/contracts/docking/ImprovementProposal.py"], severity=0.2),
        project_root=root,
    )
    proposal_id = submitted["proposal"]["proposal_id"]

    def pass_tests(proposal, **kwargs):
        return TestSuiteResult(
            passed=True,
            duration=0.01,
            selected_tests=["tests/test_closed_loop_improvement.py"],
            failing_tests=[],
            command=["pytest"],
            resource_limits={"timeout_seconds": 30},
        )

    monkeypatch.setattr(pipeline, "run_fast_targeted_tests", pass_tests)
    record = pipeline.run_improvement_pipeline(proposal_id, project_root=root)
    assert record["state"] == "human_approval"
