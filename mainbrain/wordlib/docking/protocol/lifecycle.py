"""Formal state machine for NEUROFORGE Docking Protocol v1.1."""
from __future__ import annotations

from typing import Any, Dict

from core.contracts.spec_protocol import VALID_TRANSITIONS, validate_status_transition

DOCKING_LIFECYCLE_VERSION = "neuroforge.docking.lifecycle.v1.1"


def transition_allowed(current: str, target: str, guards: Dict[str, Any] | None = None) -> Dict[str, Any]:
    ok, issues = validate_status_transition(current, target, guards or {})
    return {
        "ok": ok,
        "contract": DOCKING_LIFECYCLE_VERSION,
        "current": current,
        "target": target,
        "guards": dict(guards or {}),
        "issues": [issue.to_dict() for issue in issues],
    }


def lifecycle_description() -> Dict[str, Any]:
    return {
        "contract": DOCKING_LIFECYCLE_VERSION,
        "transitions": {k: sorted(v) for k, v in VALID_TRANSITIONS.items()},
        "guards": {
            "draft->accepted": ["human_approved"],
            "accepted->implemented": ["implemented_by=GPT"],
            "implemented->verified": ["verification_passed", "acceptance_criteria_met", "human_approved"],
            "any safety/deploy conflict": ["implementation report status=blocked or conflict"],
        },
    }
