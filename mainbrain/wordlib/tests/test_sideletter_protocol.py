from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.contracts.docking.SideLetter import SIDE_LETTER_MODEL_CONTRACT, SideLetter
from docking.memory.failure_memory import log_spec_failure
from docking.protocol.validator import (
    _match_relevant_failures,
    generate_side_letter,
    get_recent_side_letters,
    get_side_letters_for_spec,
)
from docking.specification_protocol import (
    docking_protocol_status,
    get_recent_side_letters as status_get_recent_side_letters,
    get_side_letters_for_spec as status_get_side_letters_for_spec,
)

ROOT = Path(__file__).resolve().parents[1]


def _assessment() -> dict:
    return {
        "project_assessment": "SPEC-0002 implemented the SideLetter protocol with audit-aware feedback.",
        "weaknesses": ["Failure matching must stay module-aware for core/contracts/docking/SideLetter.py."],
        "architectural_debt": ["Future report writer must prevent missing_verification and acceptance_criteria drift."],
        "knowledge_compression": "SideLetters are append-only GPT-to-Claude CNS feedback artifacts.",
        "recommendations": ["Add tests for pydantic SideLetter validation and side_letters.jsonl querying."],
        "confidence": 0.91,
        "proposed_actions": [
            {
                "type": "add_test",
                "target": "tests/test_sideletter_protocol.py",
                "description": "Exercise SideLetter proposed_actions and failure matching.",
                "priority": 0.8,
            }
        ],
    }


def test_sideletter_contract_is_strict_and_validates_actions():
    letter = SideLetter(
        timestamp="2026-06-27T00:00:00+00:00",
        spec_id="SPEC-TEST",
        project_assessment="A concrete project assessment.",
        weaknesses=[],
        architectural_debt=[],
        knowledge_compression="Compressed lesson.",
        recommendations=[],
        confidence=0.5,
        proposed_actions=[{"type": "add_test", "target": "tests/x.py", "description": "Add test.", "priority": 0.7}],
    )
    assert letter.contract == SIDE_LETTER_MODEL_CONTRACT
    assert letter.proposed_actions[0]["priority"] == 0.7
    with pytest.raises(ValidationError):
        SideLetter(
            timestamp="2026-06-27T00:00:00+00:00",
            spec_id="SPEC-TEST",
            project_assessment="A concrete project assessment.",
            weaknesses=[],
            architectural_debt=[],
            knowledge_compression="Compressed lesson.",
            recommendations=[],
            confidence=1.5,
        )
    with pytest.raises(ValidationError):
        SideLetter(
            timestamp="2026-06-27T00:00:00+00:00",
            spec_id="SPEC-TEST",
            project_assessment="A concrete project assessment.",
            weaknesses=[],
            architectural_debt=[],
            knowledge_compression="Compressed lesson.",
            recommendations=[],
            confidence=0.5,
            unexpected=True,
        )
    with pytest.raises(ValidationError):
        SideLetter(
            timestamp="2026-06-27T00:00:00+00:00",
            spec_id="SPEC-TEST",
            project_assessment="A concrete project assessment.",
            weaknesses=[],
            architectural_debt=[],
            knowledge_compression="Compressed lesson.",
            recommendations=[],
            confidence=0.5,
            proposed_actions=[{"type": "add_test", "target": "tests/x.py", "priority": 0.7}],
        )


def test_match_relevant_failures_uses_spec_signature_and_module_signals():
    recent = [
        {
            "spec_id": "SPEC-OTHER",
            "failure_category": "missing_meta",
            "reason": "unrelated meta issue",
            "issues": [{"field": "meta.spec_id", "message": "missing spec id"}],
            "timestamp": "2026-06-27T00:00:00+00:00",
            "validator_version": "test",
        },
        {
            "spec_id": "SPEC-0002_SIDELETTER_PROTOCOL",
            "failure_category": "bad_acceptance_criteria",
            "reason": "missing_verification in core/contracts/docking/SideLetter.py",
            "issues": [{"field": "core/contracts/docking/SideLetter.py", "message": "acceptance_criteria missing verification"}],
            "timestamp": "2026-06-27T01:00:00+00:00",
            "validator_version": "test",
        },
    ]
    referenced, signatures, modules = _match_relevant_failures(_assessment(), recent, spec_id="SPEC-0002_SIDELETTER_PROTOCOL")
    assert referenced[0].startswith("SPEC-0002_SIDELETTER_PROTOCOL:bad_acceptance_criteria")
    assert "exact_spec_id" in signatures
    assert "missing_verification" in signatures
    assert "core/contracts/docking/SideLetter.py" in modules


def test_generate_side_letter_appends_jsonl_and_audit_entry():
    log_spec_failure(
        "SPEC-0002_SIDELETTER_PROTOCOL",
        "bad_acceptance_criteria",
        "missing_verification in core/contracts/docking/SideLetter.py",
        [{"field": "core/contracts/docking/SideLetter.py", "message": "pydantic acceptance_criteria verification missing"}],
    )
    letter = generate_side_letter("SPEC-0002_SIDELETTER_PROTOCOL", _assessment())
    assert letter.spec_id == "SPEC-0002_SIDELETTER_PROTOCOL"
    assert letter.referenced_failures
    assert "core/contracts/docking/SideLetter.py" in letter.matched_modules
    assert "missing_verification" in letter.failure_signatures
    assert letter.proposed_actions[0]["type"] == "add_test"
    path = ROOT / "docking" / "letters" / "side_letters.jsonl"
    assert path.exists()
    last = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    assert last["failure_signatures"]
    assert isinstance(last["matched_modules"], list)
    audit_last = json.loads((ROOT / "docking" / "audit" / "validation_audit.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert audit_last["status"] == "sideletter_generated"
    assert audit_last["change_trace"]["previous_hash"].startswith("sha256:")


def test_sideletter_query_surfaces_are_read_only_and_typed():
    before = (ROOT / "docking" / "letters" / "side_letters.jsonl").read_text(encoding="utf-8")
    recent = status_get_recent_side_letters(5)
    by_spec = status_get_side_letters_for_spec("SPEC-0002_SIDELETTER_PROTOCOL")
    after = (ROOT / "docking" / "letters" / "side_letters.jsonl").read_text(encoding="utf-8")
    assert before == after
    assert recent
    assert by_spec
    assert by_spec[-1]["spec_id"] == "SPEC-0002_SIDELETTER_PROTOCOL"
    assert "proposed_actions" in by_spec[-1]
    assert "failure_signatures" in by_spec[-1]
    assert get_recent_side_letters(1)
    assert get_side_letters_for_spec("SPEC-0002_SIDELETTER_PROTOCOL")


def test_docking_protocol_status_reports_sideletter_metrics():
    status = docking_protocol_status()
    assert status["ok"] is True, status
    assert status["side_letters"]["contract"] == SIDE_LETTER_MODEL_CONTRACT
    assert status["side_letters"]["queryable"] is True
    assert status["side_letter_count"] >= 1
    assert status["last_side_letter_timestamp"]


def test_simulated_success_requires_queryable_sideletter_with_actions():
    letter = generate_side_letter(
        "SPEC-SIMULATED-SUCCESS",
        {
            "project_assessment": "Simulated successful SPEC generated the mandatory SideLetter.",
            "weaknesses": ["No known weakness beyond future report writer integration."],
            "architectural_debt": ["ImplementationReport writer is still pending."],
            "knowledge_compression": "Successful specs must emit queryable SideLetters.",
            "recommendations": ["Implement SPEC-0003 after SideLetter protocol stabilizes."],
            "confidence": 0.82,
            "proposed_actions": [
                {
                    "type": "strengthen_validation",
                    "target": "docking/protocol/validator.py",
                    "description": "Ensure future report writer enforces SideLetter presence.",
                    "priority": 0.75,
                }
            ],
        },
    )
    queried = status_get_side_letters_for_spec("SPEC-SIMULATED-SUCCESS")
    assert queried[-1]["timestamp"] == letter.model_dump(mode="json")["timestamp"]
    assert queried[-1]["proposed_actions"][0]["type"] == "strengthen_validation"


def test_deploy_status_still_imports_without_sideletter_gate_change():
    spec = importlib.util.spec_from_file_location("deploy_check", ROOT / "deploy_check.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    result = mod.check_docking_protocol()
    assert result["healthy"] is True, result
