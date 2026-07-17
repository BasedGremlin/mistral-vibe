from __future__ import annotations

import hashlib
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pytest
from pydantic import ValidationError

from core.contracts.docking.ImprovementProposal import ImprovementProposal
from core.contracts.docking.ImprovementRecord import ImprovementRecord, TestSuiteResult
from core.contracts.docking.PatchPayload import PatchPayload
from docking.improvement.patch_applier import (
    apply_patch_payload,
    canonical_patch_digest,
    get_patch_status,
    get_recent_patches,
    submit_patch_payload,
)
from docking.specification_protocol import (
    apply_patch_payload as protocol_apply_patch_payload,
    docking_protocol_status,
    get_patch_status as protocol_get_patch_status,
    get_recent_patches as protocol_get_recent_patches,
    submit_patch_payload as protocol_submit_patch_payload,
)


def _hash_marker(path: Path) -> str:
    if not path.exists():
        return "sha256:none-new-file"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _payload(
    target: str,
    *,
    action: str = "create",
    old: Optional[str] = None,
    new: str = "hello\n",
    hash_marker: str = "sha256:none-new-file",
    severity: float = 0.2,
    human: bool = False,
    proposal_id: str = "IR_TEST_PATCH_PAYLOAD",
    patch_payload_hash: Optional[str] = None,
) -> dict:
    """Build a PatchPayload dict.  Computes canonical patch_payload_hash by default."""
    digest = patch_payload_hash or canonical_patch_digest(action, target, old, new)
    return {
        "patch_id": "PATCH_TEST_" + hashlib.sha256(f"{target}-{action}-{new}-{severity}".encode()).hexdigest()[:12],
        "target_file": target,
        "action": action,
        "old_content": old,
        "new_content": new,
        "expected_hash_before": hash_marker,
        "reason": "test PatchPayload guarded apply path",
        "linked_improvement_record_id": proposal_id,
        "linked_sideletter_id": "SPEC-0004_PATCH_PAYLOAD_AND_SELFEDITOR_APPLY",
        "severity": severity,
        "priority": 0.4,
        "human_approved": human,
        "patch_payload_hash": digest,
    }


def _write_passed_improvement_record(
    proposal_id: str = "IR_TEST_PATCH_PAYLOAD",
    *,
    human_required: bool = False,
    state: str = "applied",
    tested_patch_digest: Optional[str] = None,
) -> None:
    """Create a persisted tester-passed ImprovementRecord proof for patch tests."""
    proposal = ImprovementProposal(
        proposal_id=proposal_id,
        severity=0.9 if human_required else 0.2,
        priority=0.4,
        target_modules=["docs/spec0004_patch_target.md"],
        target_functions=[],
        description="test proof for PatchPayload apply",
        expected_outcome="fast targeted tester passed before patch payload apply",
        source_sideletter_id="SPEC-0004_PATCH_PAYLOAD_AND_SELFEDITOR_APPLY",
        proposed_actions=[{
            "type": "strengthen_validation",
            "target": "docking/improvement/patch_applier.py",
            "description": "prove linked improvement record before patch apply",
            "priority": 0.5,
        }],
        proposal_content_hash=tested_patch_digest,  # propagated from proposal
    )
    record = ImprovementRecord(
        record_id="IR_PROOF_" + hashlib.sha256(f"{proposal_id}-{state}".encode()).hexdigest()[:12],
        proposal_id=proposal_id,
        state=state,
        transition="fast targeted tester passed; patch payload may be considered",
        proposal=proposal,
        test_result=TestSuiteResult(
            passed=True,
            duration=0.01,
            selected_tests=["tests/test_patch_payload.py"],
            failing_tests=[],
            timed_out=False,
            command=["pytest", "tests/test_patch_payload.py"],
            resource_limits={"timeout_seconds": 30},
        ),
        applied=state == "applied",
        rollback_info={},
        failure_references=[],
        timestamp=datetime.now(timezone.utc),
        change_traces=[],
        audit_event={"status": "test_proof"},
        human_approval_required=human_required,
        self_editor_gate={"eligible": True, "reason": "test proof fixture"},
        tested_patch_digest=tested_patch_digest,  # SPEC-CRYPTOGRAPHIC_BINDING
    )
    path = Path("docking/improvement/improvement_records.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")


def _write_record_for_payload(payload: dict) -> None:
    """Write an improvement record whose tested_patch_digest matches the payload's patch_payload_hash."""
    _write_passed_improvement_record(
        payload["linked_improvement_record_id"],
        tested_patch_digest=payload["patch_payload_hash"],
    )


# ── Contract and validation tests ──────────────────────────────────────────

def test_canonical_patch_digest_is_deterministic() -> None:
    d1 = canonical_patch_digest("create", "docs/foo.md", None, "hello\n")
    d2 = canonical_patch_digest("create", "docs/foo.md", None, "hello\n")
    assert d1 == d2
    assert d1.startswith("sha256:")
    assert len(d1) == 7 + 64  # "sha256:" + 64 hex chars


def test_canonical_patch_digest_differs_by_content() -> None:
    d_create = canonical_patch_digest("create", "docs/foo.md", None, "alpha\n")
    d_patch  = canonical_patch_digest("patch", "docs/foo.md", "alpha", "beta\n")
    d_delete = canonical_patch_digest("delete", "docs/foo.md", None, None)
    assert len({d_create, d_patch, d_delete}) == 3


def test_canonical_patch_digest_normalizes_path() -> None:
    d_fwd   = canonical_patch_digest("create", "docs/foo.md", None, "x")
    d_back  = canonical_patch_digest("create", "docs\\foo.md", None, "x")
    assert d_fwd == d_back


def test_patch_payload_contract_is_strict_and_validates_actions() -> None:
    p = _payload("docs/spec0004_contract.md")
    valid = PatchPayload.model_validate(p)
    assert valid.contract.endswith("PatchPayload.v1.1")
    assert valid.patch_payload_hash.startswith("sha256:")
    # missing expected_hash_before
    with pytest.raises(ValidationError):
        PatchPayload.model_validate({k: v for k, v in p.items() if k != "expected_hash_before"})
    # missing patch_payload_hash (SPEC-CRYPTOGRAPHIC_BINDING)
    with pytest.raises(ValidationError):
        PatchPayload.model_validate({k: v for k, v in p.items() if k != "patch_payload_hash"})
    # invalid action
    with pytest.raises(ValidationError):
        PatchPayload.model_validate({**p, "action": "overwrite"})
    # extra field rejected
    with pytest.raises(ValidationError):
        PatchPayload.model_validate({**p, "extra": True})
    # patch without old_content
    with pytest.raises(ValidationError):
        PatchPayload.model_validate({**_payload("docs/spec0004_contract.md", action="patch", old=None, new="new"),
                                     "expected_hash_before": "sha256:" + "0" * 64})
    # patch_payload_hash must be sha256:<64 hex> — none-new-file not accepted
    with pytest.raises(ValidationError):
        PatchPayload.model_validate({**p, "patch_payload_hash": "sha256:none-new-file"})
    # malformed patch_payload_hash
    with pytest.raises(ValidationError):
        PatchPayload.model_validate({**p, "patch_payload_hash": "not-a-hash"})


# ── SPEC-CRYPTOGRAPHIC_BINDING digest gate tests ──────────────────────────

def test_missing_tested_patch_digest_blocks_before_selfeditor() -> None:
    """Gate 5: ImprovementRecord without tested_patch_digest returns missing_content_digest."""
    target = Path("docs/spec_crypto_missing_digest.md")
    if target.exists():
        target.unlink()
    proposal_id = "IR_MISSING_DIGEST_TEST"
    # Write record WITHOUT tested_patch_digest
    _write_passed_improvement_record(proposal_id, tested_patch_digest=None)
    p = _payload(str(target), proposal_id=proposal_id)
    result = apply_patch_payload(p)
    assert result["status"] == "missing_content_digest"
    assert result["result"]["self_editor_called"] is False
    assert not target.exists()


def test_mismatched_digest_blocks_before_selfeditor_and_before_hash_check() -> None:
    """Gates 7+8: mismatched digest blocks, and blocks BEFORE expected_hash_before is checked."""
    target = Path("docs/spec_crypto_mismatch.md")
    if target.exists():
        target.unlink()
    proposal_id = "IR_MISMATCH_DIGEST_TEST"
    # Write record with digest for "hello\n"
    correct_digest = canonical_patch_digest("create", str(target), None, "hello\n")
    _write_passed_improvement_record(proposal_id, tested_patch_digest=correct_digest)
    # Payload claims different content (digest for "different\n") but record says "hello\n"
    wrong_digest = canonical_patch_digest("create", str(target), None, "different\n")
    p = _payload(str(target), new="different\n", proposal_id=proposal_id,
                 patch_payload_hash=wrong_digest,
                 # Even a correct hash marker shouldn't save it
                 hash_marker="sha256:none-new-file")
    result = apply_patch_payload(p)
    assert result["status"] == "mismatched_content_digest"
    assert result["result"]["self_editor_called"] is False
    assert not target.exists()


def test_digest_check_happens_before_hash_before_check() -> None:
    """Gate ordering: digest gate fires before expected_hash_before check."""
    target = Path("docs/spec_crypto_order_proof.md")
    if target.exists():
        target.unlink()
    proposal_id = "IR_ORDER_PROOF_TEST"
    correct_digest = canonical_patch_digest("create", str(target), None, "hello\n")
    wrong_matching_digest = canonical_patch_digest("create", str(target), None, "other\n")
    # Record says "other\n" but payload also says "other\n" — digest MATCHES
    # but hash_marker is wrong (not none-new-file for a new file)
    _write_passed_improvement_record(proposal_id, tested_patch_digest=wrong_matching_digest)
    p_mismatch = _payload(str(target), new="hello\n", proposal_id=proposal_id,
                          patch_payload_hash=correct_digest,  # payload hash for "hello\n"
                          hash_marker="sha256:none-new-file")
    # digest mismatch (payload=correct_digest, tested=wrong_matching_digest) → digest gate fires
    result_mismatch = apply_patch_payload(p_mismatch)
    assert result_mismatch["status"] == "mismatched_content_digest", (
        "Digest gate must fire before hash_before gate when digest mismatches"
    )

    # Now: matching digest but wrong hash_before → hash gate fires
    _write_passed_improvement_record(proposal_id, tested_patch_digest=correct_digest)
    p_hash_wrong = _payload(str(target), new="hello\n", proposal_id=proposal_id,
                            patch_payload_hash=correct_digest,
                            hash_marker="sha256:" + "0" * 64)  # wrong hash
    result_hash = apply_patch_payload(p_hash_wrong)
    assert result_hash["status"] == "hash_mismatch", (
        "After digest passes, hash_before gate fires correctly"
    )


def test_passed_improvement_record_alone_not_sufficient_without_digest() -> None:
    """Test proof (test_result.passed=True) alone is not sufficient without digest proof."""
    target = Path("docs/spec_crypto_proof_insufficient.md")
    if target.exists():
        target.unlink()
    proposal_id = "IR_PROOF_INSUFFICIENT_TEST"
    # Write a record that passes tests but has no tested_patch_digest
    _write_passed_improvement_record(proposal_id, tested_patch_digest=None)
    p = _payload(str(target), proposal_id=proposal_id)
    result = apply_patch_payload(p)
    assert result["status"] == "missing_content_digest"
    assert result["result"]["self_editor_called"] is False


def test_valid_digest_proof_does_not_bypass_whitelist() -> None:
    """Digest match does not bypass the SelfEditor whitelist gate."""
    target = "docking/improvement/not_whitelisted_crypto.md"
    proposal_id = "IR_DIGEST_WHITELIST_TEST"
    p = _payload(target, proposal_id=proposal_id)
    _write_record_for_payload(p)
    result = apply_patch_payload(p)
    assert result["status"] == "not_whitelisted"
    assert result["result"]["self_editor_called"] is False


def test_valid_digest_proof_does_not_bypass_human_approval() -> None:
    """Digest match does not bypass the human approval gate."""
    target = Path("docs/spec_crypto_human_gate.md")
    if target.exists():
        target.unlink()
    proposal_id = "IR_DIGEST_HUMAN_TEST"
    p = _payload(str(target), severity=0.9, proposal_id=proposal_id)
    _write_record_for_payload(p)
    result = apply_patch_payload(p)
    assert result["status"] == "human_approval"
    assert result["result"]["self_editor_called"] is False


def test_invalid_content_digest_format_blocked() -> None:
    """Malformed or sentinel digest in ImprovementRecord is blocked."""
    target = Path("docs/spec_crypto_invalid_fmt.md")
    if target.exists():
        target.unlink()
    proposal_id = "IR_INVALID_DIGEST_FMT"
    # Write record with all-zeros sentinel digest
    sentinel = "sha256:" + "0" * 64
    _write_passed_improvement_record(proposal_id, tested_patch_digest=sentinel)
    p = _payload(str(target), proposal_id=proposal_id, patch_payload_hash=sentinel)
    # patch_payload_hash validator should reject the sentinel
    with pytest.raises(ValidationError):
        PatchPayload.model_validate(p)


# ── Existing SPEC-0004 behavior preserved ────────────────────────────────

def test_hash_precondition_blocks_before_selfeditor_and_logs_failure() -> None:
    """Gate 8: wrong expected_hash_before blocks after digest proof passes."""
    target = Path("docs/spec0004_wrong_hash.md")
    if target.exists():
        target.unlink()
    proposal_id = "IR_HASH_MISMATCH_TEST"
    p = _payload(str(target), hash_marker="sha256:" + "0" * 64, proposal_id=proposal_id)
    _write_record_for_payload(p)  # write matching improvement record
    result = apply_patch_payload(p)
    assert result["status"] == "hash_mismatch"
    assert result["result"]["self_editor_called"] is False
    assert not target.exists()
    assert result["failure_references"]
    assert result["improvement_record"]["state"] == "rejected"


def test_missing_linked_improvement_record_blocks_before_selfeditor() -> None:
    target = Path("docs/spec0004_missing_proof.md")
    if target.exists():
        target.unlink()
    payload = _payload(str(target), proposal_id="IR_DOES_NOT_EXIST_FOR_PATCH_PROOF")
    result = apply_patch_payload(payload)
    assert result["status"] == "missing_test_proof"
    assert result["result"]["self_editor_called"] is False
    assert not target.exists()
    assert result["improvement_record"]["state"] == "rejected"


def test_non_bypass_selfeditor_calls_are_only_inside_apply_patch_payload() -> None:
    import docking.improvement.patch_applier as patch_applier

    source = inspect.getsource(patch_applier)
    assert "def apply_patch_payload" in source
    assert "editor.write_file" in source
    before_apply = source.split("def apply_patch_payload", 1)[0]
    for forbidden_call in (".write_file(", ".patch_file(", ".append_to_file(", ".delete_file("):
        assert forbidden_call not in before_apply


def test_human_gate_blocks_high_severity_before_selfeditor() -> None:
    target = Path("docs/spec0004_human_gate.md")
    if target.exists():
        target.unlink()
    proposal_id = "IR_HUMAN_GATE_TEST"
    p = _payload(str(target), severity=0.9, proposal_id=proposal_id)
    _write_record_for_payload(p)  # must pass digest gate first
    result = apply_patch_payload(p)
    assert result["status"] == "human_approval"
    assert result["result"]["self_editor_called"] is False
    assert result["improvement_record"]["state"] == "human_approval"
    assert not target.exists()


def test_whitelist_blocks_non_selfeditor_target() -> None:
    target = "docking/improvement/not_whitelisted.md"
    proposal_id = "IR_WHITELIST_TEST"
    p = _payload(target, proposal_id=proposal_id)
    _write_record_for_payload(p)  # must pass digest gate first
    result = apply_patch_payload(p)
    assert result["status"] == "not_whitelisted"
    assert result["result"]["self_editor_called"] is False
    assert result["failure_references"]


def test_valid_low_severity_create_patch_append_delete_is_audited_and_queryable() -> None:
    target = Path("docs/spec0004_patch_target.md")
    if target.exists():
        cleanup_p = _payload(str(target), action="delete", new="", hash_marker=_hash_marker(target), human=True,
                              proposal_id="IR_CLEANUP_SPEC0004")
        _write_record_for_payload(cleanup_p)
        apply_patch_payload(cleanup_p)

    create_p = _payload(str(target), action="create", new="alpha\n", hash_marker="sha256:none-new-file",
                        proposal_id="IR_CREATE_SPEC0004")
    _write_record_for_payload(create_p)
    submitted = submit_patch_payload(create_p)
    assert submitted["status"] == "submitted"
    created = apply_patch_payload(create_p)
    assert created["status"] == "applied"
    assert target.read_text(encoding="utf-8") == "alpha\n"
    assert created["result"]["self_editor_called"] is True
    assert created["change_traces"][0]["file_path"] == str(target)
    assert created["improvement_record"]["applied"] is True

    patch_p = _payload(str(target), action="patch", old="alpha", new="beta",
                       hash_marker=_hash_marker(target), proposal_id="IR_PATCH_SPEC0004")
    _write_record_for_payload(patch_p)
    patched = apply_patch_payload(patch_p)
    assert patched["status"] == "applied"
    assert "beta" in target.read_text(encoding="utf-8")

    append_p = _payload(str(target), action="append", new="gamma",
                        hash_marker=_hash_marker(target), proposal_id="IR_APPEND_SPEC0004")
    _write_record_for_payload(append_p)
    appended = apply_patch_payload(append_p)
    assert appended["status"] == "applied"
    assert "gamma" in target.read_text(encoding="utf-8")

    delete_p = _payload(str(target), action="delete", new="",
                        hash_marker=_hash_marker(target), proposal_id="IR_DELETE_SPEC0004")
    _write_record_for_payload(delete_p)
    deleted = apply_patch_payload(delete_p)
    assert deleted["status"] == "applied"
    assert not target.exists()

    assert get_patch_status(create_p["patch_id"])["ok"] is True
    recent = get_recent_patches(20)
    assert any(record["patch_id"] == delete_p["patch_id"] for record in recent)


def test_protocol_surfaces_submit_apply_query_and_status() -> None:
    _write_passed_improvement_record(tested_patch_digest=None)  # baseline record (no digest, for submit test)
    target = Path("docs/spec0004_protocol_surface.md")
    if target.exists():
        cleanup_p = _payload(str(target), action="delete", new="", hash_marker=_hash_marker(target), human=True,
                              proposal_id="IR_PROTOCOL_CLEANUP")
        _write_record_for_payload(cleanup_p)
        apply_patch_payload(cleanup_p)
    p = _payload(str(target), new="protocol\n", hash_marker="sha256:none-new-file",
                 proposal_id="IR_PROTOCOL_SURFACE")
    _write_record_for_payload(p)
    submitted = protocol_submit_patch_payload(p)
    assert submitted["status"] == "submitted"
    applied = protocol_apply_patch_payload(p)
    assert applied["status"] == "applied"
    assert protocol_get_patch_status(p["patch_id"])["ok"] is True
    assert protocol_get_recent_patches(5)
    status = docking_protocol_status()
    assert status["patch_applier"]["contract"].endswith("patch_applier.v1.0")
    assert status["patch_count"] >= 1
    cleanup_p2 = _payload(str(target), action="delete", new="", hash_marker=_hash_marker(target), human=True,
                          proposal_id="IR_PROTOCOL_DELETE")
    _write_record_for_payload(cleanup_p2)
    apply_patch_payload(cleanup_p2)
