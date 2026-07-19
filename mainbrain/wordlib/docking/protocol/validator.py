"""Validation layer for the NEUROFORGE Docking CNS protocol.

This module has two responsibilities:

* Preserve the existing v1.1 read-only validation surface used by deployment
  checks and older tests.
* Provide the production CNS gate required by SPEC-0001 v1.1:
  ``pre_implementation_validation()`` / ``validate_spec_before_implementation()``.

The pre-implementation gate is intentionally auditable: every call appends one
JSONL record to ``docking/audit/validation_audit.jsonl``.  Status and query
functions remain read-only.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from pydantic import ValidationError

from core.contracts.spec_protocol import (
    SPEC_PROTOCOL_VERSION,
    SpecDocument as LegacySpecDocument,
    ImplementationReport,
    validate_spec_payload,
    validate_implementation_report_payload,
    spec_from_payload,
    protocol_self_description,
)

from core.contracts.docking.SideLetter import SideLetter, SIDE_LETTER_MODEL_CONTRACT
from core.contracts.docking.ChangeTrace import ChangeTrace
from docking.memory.failure_memory import (
    get_recent_failures,
    get_failures_by_category,
    log_spec_failure,
)
from core.contracts.docking.SpecDocument import (
    SPEC_DOCUMENT_MODEL_CONTRACT,
    AcceptanceCriterion as StrictAcceptanceCriterion,
    ContractReference,
    SpecDefinition,
    SpecDocument,
    SpecImpact,
    SpecMeta,
    SpecRelationships,
    SpecTarget,
)

DOCKING_VALIDATOR_VERSION = "neuroforge.docking.validator.v1.1"
DOCKING_CNS_VALIDATOR_VERSION = "neuroforge.docking.cns.validator.v1.2"
VALIDATION_AUDIT_FILE = "validation_audit.jsonl"


def _utc_now() -> str:
    """Return a timezone-aware UTC timestamp for validation audit entries."""
    return datetime.now(timezone.utc).isoformat()


def _text(parent: ET.Element, path: str, default: str = "") -> str:
    node = parent.find(path)
    if node is None or node.text is None:
        return default
    return node.text.strip()


def _split_text_lines(value: str) -> List[str]:
    """Split multi-line XML text content into useful non-empty entries."""
    values: List[str] = []
    for line in (value or "").splitlines():
        cleaned = line.strip().strip("-").strip()
        if cleaned:
            values.append(cleaned)
    return values


def _list(parent: ET.Element, path: str, item_tag: str = "item") -> List[str]:
    """Extract a list from item children, arbitrary children, or multiline text."""
    node = parent.find(path)
    if node is None:
        return []
    values: List[str] = []
    items = node.findall(item_tag)
    if items:
        for item in items:
            if item.text and item.text.strip():
                values.extend(_split_text_lines(item.text))
    else:
        for child in list(node):
            if child.text and child.text.strip():
                values.extend(_split_text_lines(child.text))
        if node.text and node.text.strip() and not values:
            values.extend(_split_text_lines(node.text))
    return values


def _contract_refs(parent: ET.Element) -> List[str]:
    """Extract contract references from <contract ref="..."/> or item text."""
    node = parent.find("contracts")
    if node is None:
        return []
    refs: List[str] = []
    for child in list(node):
        ref = child.attrib.get("ref", "").strip()
        if ref:
            refs.append(ref)
        elif child.text and child.text.strip():
            refs.extend(_split_text_lines(child.text))
    if node.text and node.text.strip() and not refs:
        refs.extend(_split_text_lines(node.text))
    return refs


def _extract_embedded_spec_xml(text: str) -> str:
    """Return a <SpecDocument> XML block from raw XML or markdown text."""
    stripped = text.strip()
    if stripped.startswith("<SpecDocument") or stripped.startswith("<SPEC"):
        return stripped
    match = re.search(r"(<SpecDocument>.*?</SpecDocument>)", stripped, re.DOTALL)
    if not match:
        match = re.search(r"(<SPEC\b.*?</SPEC>)", stripped, re.DOTALL)
    if not match:
        raise ValueError("no <SpecDocument> or legacy <SPEC> block found")
    return match.group(1)


def parse_spec_xml_text(text: str) -> LegacySpecDocument:
    """Parse XML text into the legacy stdlib SpecDocument contract.

    This function remains for compatibility with existing deploy gates and tests.
    Production pre-implementation validation uses ``parse_strict_spec_xml_text``.
    """
    root = ET.fromstring(_extract_embedded_spec_xml(text))
    if root.tag not in {"SpecDocument", "SPEC"}:
        raise ValueError("root element must be <SpecDocument> or legacy <SPEC>")
    if root.tag == "SPEC":
        payload: Dict[str, Any] = {
            "spec_id": root.attrib.get("id", "").strip(),
            "version": root.attrib.get("version", "").strip(),
            "date": _text(root, "created_at", "2026-06-27"),
            "author": _text(root, "owner", "Claude"),
            "status": _text(root, "status", "draft"),
            "mission": _text(root, "purpose"),
            "scope": _text(root, "title"),
            "non_goals": [],
            "modules": _list(root, "target_modules"),
            "allowed_files": _list(root, "allowed_files"),
            "forbidden_files": _list(root, "forbidden_files"),
            "dependencies": [],
            "supersedes": [],
            "contracts": [],
            "implementation_requirements": [],
            "rollback_expectations": _list(root, "rollback_expectations") or [_text(root, "rollback_plan")],
            "deploy_impact": [],
            "risks": [],
            "risk_level": _text(root, "risk_level", "medium"),
            "human_approval_required": True,
            "deploy_gate_required": _text(root, "deploy_gate_required", "true").lower() != "false",
            "notes": _list(root, "notes"),
            "acceptance_criteria": [],
        }
        acs = root.find("acceptance_criteria")
        if acs is not None:
            for ac in acs.findall("criterion"):
                payload["acceptance_criteria"].append({
                    "id": ac.attrib.get("id", "").strip(),
                    "description": _text(ac, "description") or (ac.text or "").strip(),
                    "verification": _text(ac, "verification"),
                    "required": ac.attrib.get("required", "true").lower() != "false",
                })
        return spec_from_payload(payload)

    meta = root.find("meta")
    if meta is None:
        meta = ET.Element("meta")
    target = root.find("target")
    if target is None:
        target = ET.Element("target")
    relationships = root.find("relationships")
    if relationships is None:
        relationships = ET.Element("relationships")
    definition = root.find("definition")
    if definition is None:
        definition = ET.Element("definition")
    impact = root.find("impact")
    if impact is None:
        impact = ET.Element("impact")
    payload = {
        "spec_id": _text(meta, "spec_id"),
        "protocol_version": _text(meta, "protocol_version"),
        "version": _text(meta, "version"),
        "date": _text(meta, "date"),
        "author": _text(meta, "author", "Claude"),
        "status": _text(meta, "status", "draft"),
        "mission": _text(root, "mission"),
        "scope": _text(root, "scope"),
        "non_goals": _list(root, "non_goals"),
        "modules": _list(target, "modules", "module"),
        "allowed_files": _list(target, "allowed_files"),
        "forbidden_files": _list(target, "forbidden_files"),
        "dependencies": [],
        "supersedes": _list(relationships, "supersedes"),
        "contracts": _contract_refs(definition),
        "implementation_requirements": _list(definition, "implementation_requirements"),
        "rollback_expectations": _list(definition, "rollback_expectations"),
        "deploy_impact": _list(impact, "deploy"),
        "risks": _list(impact, "risks"),
        "acceptance_criteria": [],
        "human_approval_required": True,
        "deploy_gate_required": True,
    }
    deps = relationships.find("dependencies")
    if deps is not None:
        for dep in deps.findall("dependency"):
            payload["dependencies"].append({
                "spec_id": dep.attrib.get("spec_id", "").strip() or (dep.text or "").strip(),
                "relationship": dep.attrib.get("relationship", "requires"),
                "reason": dep.attrib.get("reason", ""),
            })
    acs = definition.find("acceptance_criteria")
    if acs is not None:
        for ac in acs.findall("criterion"):
            payload["acceptance_criteria"].append({
                "id": ac.attrib.get("id", "").strip(),
                "description": _text(ac, "description") or (ac.text or "").strip(),
                "verification": _text(ac, "verification"),
                "required": ac.attrib.get("required", "true").lower() != "false",
            })
    return spec_from_payload(payload)


def parse_strict_spec_xml_text(text: str) -> SpecDocument:
    """Parse XML into the strict Pydantic v2 SpecDocument contract."""
    root = ET.fromstring(_extract_embedded_spec_xml(text))
    if root.tag != "SpecDocument":
        raise ValueError("production CNS validation requires a <SpecDocument> root")
    meta = root.find("meta")
    if meta is None:
        meta = ET.Element("meta")
    target = root.find("target")
    if target is None:
        target = ET.Element("target")
    relationships = root.find("relationships")
    if relationships is None:
        relationships = ET.Element("relationships")
    definition = root.find("definition")
    if definition is None:
        definition = ET.Element("definition")
    impact = root.find("impact")
    if impact is None:
        impact = ET.Element("impact")
    contracts = [ContractReference(ref=ref) for ref in _contract_refs(definition)]
    criteria: List[StrictAcceptanceCriterion] = []
    acs = definition.find("acceptance_criteria")
    if acs is not None:
        for ac in acs.findall("criterion"):
            criteria.append(StrictAcceptanceCriterion(
                id=ac.attrib.get("id", "").strip(),
                type=ac.attrib.get("type", "unspecified").strip() or "unspecified",
                target=ac.attrib.get("target", "unspecified").strip() or "unspecified",
                description=_text(ac, "description") or (ac.text or "").strip(),
                verification=_text(ac, "verification"),
            ))
    return SpecDocument(
        meta=SpecMeta(
            spec_id=_text(meta, "spec_id"),
            protocol_version=_text(meta, "protocol_version", "1.2"),
            version=_text(meta, "version"),
            date=_text(meta, "date"),
            author=_text(meta, "author", "Claude"),
            status=_text(meta, "status", "draft"),
        ),
        mission=_text(root, "mission"),
        scope=_text(root, "scope"),
        non_goals=_text(root, "non_goals"),
        target=SpecTarget(
            modules=_list(target, "modules", "module"),
            allowed_files=_list(target, "allowed_files"),
            forbidden_files=_list(target, "forbidden_files"),
        ),
        relationships=SpecRelationships(
            dependencies=_list(relationships, "dependencies", "dependency"),
            supersedes=_list(relationships, "supersedes"),
        ),
        definition=SpecDefinition(
            contracts=contracts,
            implementation_requirements=_list(definition, "implementation_requirements"),
            acceptance_criteria=criteria,
            rollback_expectations=_text(definition, "rollback_expectations"),
        ),
        impact=SpecImpact(deploy=_text(impact, "deploy"), risks=_text(impact, "risks")),
    )


def load_spec_document(path: Path) -> LegacySpecDocument:
    """Load a legacy-compatible spec document from XML or JSON."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        return spec_from_payload(json.loads(text))
    return parse_spec_xml_text(text)


def validate_spec_document(spec: LegacySpecDocument) -> Dict[str, Any]:
    """Validate the legacy stdlib SpecDocument contract."""
    ok, issues = validate_spec_payload(spec.to_dict())
    return {
        "ok": ok,
        "contract": DOCKING_VALIDATOR_VERSION,
        "spec_protocol": SPEC_PROTOCOL_VERSION,
        "spec_id": spec.spec_id,
        "version": spec.version,
        "status": spec.status,
        "issues": [issue.to_dict() for issue in issues],
    }


def _repo_root(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Resolve the project root without importing the high-level app."""
    if project_root is not None:
        return Path(project_root).resolve()
    return Path(__file__).resolve().parents[2]


def _audit_path(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Return the validation audit JSONL path."""
    return _repo_root(project_root) / "docking" / "audit" / VALIDATION_AUDIT_FILE


def _write_validation_audit(event: Dict[str, Any], project_root: Optional[Union[str, Path]] = None) -> None:
    """Append one structured validation audit event."""
    path = _audit_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")


def _issues_from_validation_error(exc: ValidationError) -> List[Dict[str, Any]]:
    """Convert Pydantic errors into stable issue dictionaries."""
    issues: List[Dict[str, Any]] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", [])) or "payload"
        issues.append({"field": loc, "message": str(err.get("msg", "validation error")), "severity": "error"})
    return issues


def _spec_input_to_text(spec_input: Union[str, Path, Dict[str, Any], SpecDocument]) -> str:
    """Normalize spec input into XML or JSON text for validation."""
    if isinstance(spec_input, SpecDocument):
        return spec_input.model_dump_json()
    if isinstance(spec_input, dict):
        return json.dumps(spec_input)
    if isinstance(spec_input, Path):
        return spec_input.read_text(encoding="utf-8")
    raw = str(spec_input)
    stripped = raw.lstrip()
    if stripped.startswith("<") or stripped.startswith("{") or "<SpecDocument" in stripped or "<SPEC" in stripped:
        return raw
    try:
        candidate = Path(raw)
        if candidate.exists() and candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    except OSError:
        return raw
    return raw



def _failure_category_from_issues(issues: List[Dict[str, Any]]) -> str:
    """Map validation issues to a stable Failure Memory category."""
    fields = " ".join(str(issue.get("field", "")) for issue in issues).lower()
    messages = " ".join(str(issue.get("message", "")) for issue in issues).lower()
    combined = f"{fields} {messages}"
    if "acceptance" in combined or "verification" in combined:
        return "bad_acceptance_criteria"
    if "meta" in combined or "spec_id" in combined:
        return "missing_meta"
    if "status" in combined:
        return "invalid_status"
    if "xml" in combined or "parse" in combined or "spec_input" in combined:
        return "malformed_spec"
    return "invalid_spec"


def _matching_past_failures(category: str, recent_failures: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    """Return recent failures that match a category without mutating memory."""
    normalized = (category or "").strip().lower().replace(" ", "_")
    matches = [record for record in recent_failures if record.get("failure_category") == normalized]
    return matches[-max(0, int(limit)):]

def pre_implementation_validation(
    spec_input: Union[str, Path, Dict[str, Any], SpecDocument],
    *,
    project_root: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Validate a spec before implementation, audit the decision, and query Failure Memory.

    Args:
        spec_input: XML text, markdown containing a ``<SpecDocument>`` block,
            JSON-like dictionary, path to a spec file, or strict SpecDocument.
        project_root: Optional repository root used for audit and failure-memory
            output in tests.

    Returns:
        A machine-readable validation result. ``status`` is ``passed`` only
        when the spec is mechanically valid and accepted for implementation.
        Every result includes ``relevant_past_failures`` from Failure Memory.
    """
    timestamp = _utc_now()
    spec_id = "UNKNOWN"
    issues: List[Dict[str, Any]] = []
    status = "blocked"
    contract = SPEC_DOCUMENT_MODEL_CONTRACT
    recent_failures = get_recent_failures(20, project_root=project_root)
    failure_category = "none"
    reason = "spec accepted for implementation"
    try:
        raw = _spec_input_to_text(spec_input)
        stripped = raw.strip()
        if stripped.startswith("{"):
            spec = SpecDocument.model_validate_json(stripped)
        else:
            spec = parse_strict_spec_xml_text(stripped)
        spec_id = spec.meta.spec_id
        if spec.meta.status != "accepted":
            issues.append({"field": "meta.status", "message": "spec must be accepted before implementation", "severity": "error"})
        if not spec.definition.acceptance_criteria:
            issues.append({"field": "definition.acceptance_criteria", "message": "at least one acceptance criterion is required", "severity": "error"})
        status = "passed" if not issues else "blocked"
        if issues:
            failure_category = _failure_category_from_issues(issues)
            reason = "spec failed mechanical validation"
        result: Dict[str, Any] = {
            "ok": status == "passed",
            "status": status,
            "spec_id": spec_id,
            "validator_version": DOCKING_CNS_VALIDATOR_VERSION,
            "contract": contract,
            "issues": issues,
            "validated_before_modification": True,
            "audit_required": True,
            "failure_memory_queried": True,
            "relevant_past_failures": _matching_past_failures(failure_category, recent_failures),
        }
    except ValidationError as exc:
        issues = _issues_from_validation_error(exc)
        failure_category = _failure_category_from_issues(issues)
        reason = "strict SpecDocument validation failed"
        result = {
            "ok": False,
            "status": "blocked",
            "spec_id": spec_id,
            "validator_version": DOCKING_CNS_VALIDATOR_VERSION,
            "contract": contract,
            "issues": issues,
            "validated_before_modification": True,
            "audit_required": True,
            "failure_memory_queried": True,
            "relevant_past_failures": _matching_past_failures(failure_category, recent_failures),
        }
    except (ET.ParseError, OSError, ValueError, json.JSONDecodeError) as exc:
        issues = [{"field": "spec_input", "message": f"{type(exc).__name__}: {exc}", "severity": "error"}]
        failure_category = _failure_category_from_issues(issues)
        reason = "spec input could not be parsed or loaded"
        result = {
            "ok": False,
            "status": "blocked",
            "spec_id": spec_id,
            "validator_version": DOCKING_CNS_VALIDATOR_VERSION,
            "contract": contract,
            "issues": issues,
            "validated_before_modification": True,
            "audit_required": True,
            "failure_memory_queried": True,
            "relevant_past_failures": _matching_past_failures(failure_category, recent_failures),
        }

    failure_record: Optional[Dict[str, Any]] = None
    if result.get("status") != "passed":
        failure_record = log_spec_failure(
            spec_id=result.get("spec_id", spec_id),
            failure_category=failure_category,
            reason=reason,
            issues=result.get("issues", []),
            timestamp=timestamp,
            validator_version=DOCKING_CNS_VALIDATOR_VERSION,
            project_root=project_root,
        )
        result["failure_record"] = failure_record
        # Include the just-recorded failure when there were no earlier matching
        # failures so operators can still inspect the relevant failure shape.
        if not result.get("relevant_past_failures"):
            result["relevant_past_failures"] = [failure_record]

    event = {
        "timestamp": timestamp,
        "spec_id": result.get("spec_id", spec_id),
        "status": result.get("status", "blocked"),
        "issues": result.get("issues", []),
        "validator_version": DOCKING_CNS_VALIDATOR_VERSION,
        "contract": "neuroforge.docking.validation_audit.v1.2",
        "failure_memory_queried": True,
        "relevant_past_failures": result.get("relevant_past_failures", []),
        "failure_category": failure_category,
    }
    _write_validation_audit(event, project_root)
    result["audit_event"] = event
    result["audit_path"] = str(_audit_path(project_root))
    result["failure_memory_contract"] = "neuroforge.docking.failure_memory.v1.2"
    return result


def validate_spec_before_implementation(
    spec_input: Union[str, Path, Dict[str, Any], SpecDocument],
    *,
    project_root: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Non-bypassable public gate alias for pre-implementation validation."""
    return pre_implementation_validation(spec_input, project_root=project_root)


def validate_implementation_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an ImplementationReport payload."""
    ok, issues = validate_implementation_report_payload(report)
    return {"ok": ok, "contract": DOCKING_VALIDATOR_VERSION, "issues": [issue.to_dict() for issue in issues]}



SIDE_LETTER_FILE = "side_letters.jsonl"
SIDE_LETTER_AUDIT_CONTRACT = "neuroforge.docking.sideletter_audit.v1.1"


def _side_letter_path(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Return the append-only SideLetter JSONL path."""
    return _repo_root(project_root) / "docking" / "letters" / SIDE_LETTER_FILE


def _sha256_file(path: Path) -> str:
    """Return a sha256 marker for an existing file or a stable none marker."""
    if not path.exists():
        return "sha256:none-new-file"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _normalize_token(value: str) -> str:
    """Normalize text into a deterministic matching token."""
    cleaned = re.sub(r"[^a-zA-Z0-9_./-]+", "_", value.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned


def _extract_match_signatures(assessment: Dict[str, Any]) -> List[str]:
    """Extract deterministic failure signatures from assessment text.

    Args:
        assessment: Assessment dictionary supplied to ``generate_side_letter``.

    Returns:
        Ordered, deduplicated signature tokens suitable for Failure Memory
        matching. The extraction is intentionally deterministic and lightweight.
    """
    source_parts: List[str] = []
    for key in ("weaknesses", "architectural_debt", "recommendations"):
        value = assessment.get(key, [])
        if isinstance(value, str):
            source_parts.append(value)
        elif isinstance(value, list):
            source_parts.extend(str(item) for item in value)
    source_parts.append(str(assessment.get("project_assessment", "")))
    source_parts.append(str(assessment.get("knowledge_compression", "")))
    combined = "\n".join(source_parts).lower()
    signatures: List[str] = []
    signature_patterns = {
        "missing_verification": ["missing verification", "verification", "acceptance criteria", "acceptance_criteria"],
        "bad_acceptance_criteria": ["bad_acceptance_criteria", "acceptance criteria", "acceptance_criteria"],
        "pydantic": ["pydantic", "basemodel", "validationerror"],
        "audit_logging": ["audit", "validation_audit", "jsonl"],
        "failure_memory": ["failure memory", "failure_log", "failurerecord"],
        "sideletter": ["sideletter", "side letter", "side_letters"],
        "change_trace": ["changetrace", "change trace", "previous_hash"],
        "module_matching": ["module", "matched_modules", "module-aware"],
    }
    for signature, needles in signature_patterns.items():
        if any(needle in combined for needle in needles):
            signatures.append(signature)
    # Include explicit snake_case-like tokens to avoid category-only matching.
    for match in re.findall(r"\b[a-z][a-z0-9]+(?:_[a-z0-9]+)+\b", combined):
        token = _normalize_token(match)
        if token and token not in signatures:
            signatures.append(token)
    return signatures


def _extract_module_tokens(assessment: Dict[str, Any]) -> List[str]:
    """Extract module/path tokens from assessment payload."""
    source_parts: List[str] = []
    for value in assessment.values():
        if isinstance(value, str):
            source_parts.append(value)
        elif isinstance(value, list):
            source_parts.extend(str(item) for item in value)
    combined = "\n".join(source_parts)
    modules: List[str] = []
    for match in re.findall(r"(?:[A-Za-z0-9_./-]+/)+[A-Za-z0-9_.-]+|[A-Za-z_][A-Za-z0-9_]*\.py", combined):
        token = match.strip().strip(".,;:()[]{}<>\"'")
        if token and token not in modules:
            modules.append(token)
    return modules


def _failure_text(record: Dict[str, Any]) -> str:
    """Build searchable text for a Failure Memory record."""
    pieces: List[str] = []
    for key in ("spec_id", "failure_category", "reason", "validator_version"):
        pieces.append(str(record.get(key, "")))
    issues = record.get("issues", [])
    if isinstance(issues, list):
        for issue in issues:
            if isinstance(issue, dict):
                pieces.extend(str(issue.get(k, "")) for k in ("field", "message", "severity"))
            else:
                pieces.append(str(issue))
    return "\n".join(pieces).lower()


def _record_identifier(record: Dict[str, Any]) -> str:
    """Return a stable human-readable identifier for a failure record."""
    spec_id = str(record.get("spec_id") or "UNKNOWN")
    category = str(record.get("failure_category") or "invalid_spec")
    timestamp = str(record.get("timestamp") or "unknown_time")
    return f"{spec_id}:{category}:{timestamp}"


def _match_relevant_failures(
    assessment: Dict[str, Any],
    recent_failures: List[Dict[str, Any]],
    *,
    spec_id: str = "",
    limit: int = 5,
) -> Tuple[List[str], List[str], List[str]]:
    """Match Failure Memory using spec, signature, category, and module signals.

    This helper deliberately does more than category matching: it ranks exact
    spec matches first, then combines failure categories, extracted signatures,
    and module/path overlap into a deterministic score.
    """
    signatures = _extract_match_signatures(assessment)
    modules = _extract_module_tokens(assessment)
    assessment_categories = {_normalize_token(sig) for sig in signatures}
    scored: List[Tuple[float, str, Dict[str, Any], List[str], List[str]]] = []
    for record in recent_failures:
        text = _failure_text(record)
        score = 0.0
        matched_sigs: List[str] = []
        matched_mods: List[str] = []
        if spec_id and str(record.get("spec_id")) == spec_id:
            score += 5.0
            matched_sigs.append("exact_spec_id")
        category = _normalize_token(str(record.get("failure_category", "")))
        if category and category in assessment_categories:
            score += 3.0
            matched_sigs.append(category)
        for signature in signatures:
            normalized = _normalize_token(signature)
            if normalized and normalized in text and normalized not in matched_sigs:
                score += 2.0
                matched_sigs.append(normalized)
        for module in modules:
            module_norm = module.lower()
            module_name = Path(module_norm).name
            if module_norm in text or module_name in text:
                score += 2.5
                if module not in matched_mods:
                    matched_mods.append(module)
        if score > 0.0:
            identifier = _record_identifier(record)
            scored.append((score, identifier, record, matched_sigs, matched_mods))
    scored.sort(key=lambda item: (-item[0], item[1]))
    referenced: List[str] = []
    failure_signatures: List[str] = []
    matched_modules: List[str] = []
    for _score, identifier, _record, sigs, mods in scored[: max(0, int(limit))]:
        if identifier not in referenced:
            referenced.append(identifier)
        for sig in sigs:
            if sig not in failure_signatures:
                failure_signatures.append(sig)
        for mod in mods:
            if mod not in matched_modules:
                matched_modules.append(mod)
    # Surface extracted signals even when no failure currently matches them.
    for sig in signatures:
        norm = _normalize_token(sig)
        if norm and norm not in failure_signatures:
            failure_signatures.append(norm)
    for mod in modules:
        if mod not in matched_modules:
            matched_modules.append(mod)
    return referenced, failure_signatures, matched_modules


def _sideletter_payload_from_assessment(spec_id: str, assessment: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
    """Build a SideLetter payload from caller assessment input."""
    recent_failures = get_recent_failures(20)
    referenced, signatures, modules = _match_relevant_failures(assessment, recent_failures, spec_id=spec_id)
    return {
        "timestamp": timestamp,
        "spec_id": spec_id,
        "project_assessment": str(assessment.get("project_assessment", "")),
        "weaknesses": list(assessment.get("weaknesses", []) or []),
        "architectural_debt": list(assessment.get("architectural_debt", []) or []),
        "knowledge_compression": str(assessment.get("knowledge_compression", "")),
        "recommendations": list(assessment.get("recommendations", []) or []),
        "confidence": float(assessment.get("confidence", 0.0)),
        "referenced_failures": referenced,
        "failure_signatures": signatures,
        "matched_modules": modules,
        "proposed_actions": list(assessment.get("proposed_actions", []) or []),
    }


def generate_side_letter(
    spec_id: str,
    assessment: Dict[str, Any],
    *,
    project_root: Optional[Union[str, Path]] = None,
) -> SideLetter:
    """Generate, validate, persist, and audit a SideLetter.

    GPT must call this function after every successful SPEC implementation
    before the task is considered complete.

    Args:
        spec_id: Specification identifier being reported back to Claude.
        assessment: SideLetter assessment fields and optional proposed actions.
        project_root: Optional repository root override used by tests.

    Returns:
        The validated SideLetter Pydantic model.

    Raises:
        pydantic.ValidationError: If the SideLetter payload is invalid.
        OSError: If the append-only JSONL or audit entry cannot be written.
    """
    timestamp = _utc_now()
    path = _side_letter_path(project_root)
    previous_hash = _sha256_file(path)
    payload = _sideletter_payload_from_assessment(spec_id, assessment, timestamp)
    letter = SideLetter.model_validate(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(letter.model_dump_json() + "\n")
    trace = ChangeTrace(
        file_path="docking/letters/side_letters.jsonl",
        spec_id=spec_id,
        action="modified" if previous_hash != "sha256:none-new-file" else "created",
        reason="Append immutable SideLetter after successful SPEC implementation.",
        timestamp=timestamp,
        previous_hash=previous_hash,
    )
    audit_event = {
        "timestamp": timestamp,
        "spec_id": spec_id,
        "status": "sideletter_generated",
        "issues": [],
        "validator_version": DOCKING_CNS_VALIDATOR_VERSION,
        "contract": SIDE_LETTER_AUDIT_CONTRACT,
        "sideletter_contract": SIDE_LETTER_MODEL_CONTRACT,
        "sideletter_path": str(path),
        "change_trace": trace.model_dump(),
        "referenced_failures": letter.referenced_failures,
        "failure_signatures": letter.failure_signatures,
        "matched_modules": letter.matched_modules,
        "proposed_actions_count": len(letter.proposed_actions),
    }
    _write_validation_audit(audit_event, project_root)
    return letter


def _read_side_letters(project_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Read all valid SideLetter JSONL records without mutating state."""
    path = _side_letter_path(project_root)
    if not path.exists():
        return []
    letters: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            letters.append(SideLetter.model_validate_json(line).model_dump(mode="json"))
        except (ValueError, json.JSONDecodeError):
            continue
    return letters


def get_recent_side_letters(limit: int = 10, *, project_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Return recent SideLetters without mutating state."""
    safe_limit = max(0, int(limit))
    if safe_limit == 0:
        return []
    return _read_side_letters(project_root)[-safe_limit:]


def get_side_letters_for_spec(spec_id: str, *, project_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Return all SideLetters for a SPEC identifier without mutating state."""
    target = str(spec_id or "").strip()
    if not target:
        return []
    return [letter for letter in _read_side_letters(project_root) if letter.get("spec_id") == target]


def validator_self_description() -> Dict[str, Any]:
    """Return protocol validator self-description."""
    desc = protocol_self_description()
    desc["validator"] = DOCKING_VALIDATOR_VERSION
    desc["cns_validator"] = DOCKING_CNS_VALIDATOR_VERSION
    desc["pre_implementation_gate"] = "docking.protocol.validator.pre_implementation_validation"
    desc["audit_file"] = f"docking/audit/{VALIDATION_AUDIT_FILE}"
    desc["failure_memory"] = "docking/memory/failure_log.jsonl"
    return desc


__all__ = [
    "DOCKING_VALIDATOR_VERSION",
    "DOCKING_CNS_VALIDATOR_VERSION",
    "VALIDATION_AUDIT_FILE",
    "parse_spec_xml_text",
    "parse_strict_spec_xml_text",
    "load_spec_document",
    "validate_spec_document",
    "validate_implementation_report",
    "pre_implementation_validation",
    "validate_spec_before_implementation",
    "validator_self_description",
    "SIDE_LETTER_FILE",
    "SIDE_LETTER_AUDIT_CONTRACT",
    "generate_side_letter",
    "get_recent_side_letters",
    "get_side_letters_for_spec",
    "_match_relevant_failures",
]
