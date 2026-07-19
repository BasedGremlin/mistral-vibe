"""Deterministic test selection for closed-loop improvement proposals."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Union

from core.contracts.docking.ImprovementProposal import ImprovementProposal

TEST_SELECTOR_CONTRACT = "neuroforge.docking.improvement.selector.v1.0"

_KEYWORD_TEST_MAP: Dict[str, str] = {
    "docking": "tests/test_docking_protocol.py",
    "failure": "tests/test_docking_protocol.py",
    "sideletter": "tests/test_sideletter_protocol.py",
    "side_letter": "tests/test_sideletter_protocol.py",
    "improvement": "tests/test_closed_loop_improvement.py",
    "selfeditor": "tests/test_self_editor.py",
    "self_editor": "tests/test_self_editor.py",
    "paths": "tests/test_paths_and_healer.py",
    "path": "tests/test_paths_and_healer.py",
    "semantic": "tests/test_semantic_core.py",
    "nexus": "tests/test_nexus_snapshot.py",
}

_PATH_TEST_MAP: Dict[str, str] = {
    "docking/specification_protocol.py": "tests/test_docking_protocol.py",
    "docking/protocol/validator.py": "tests/test_docking_protocol.py",
    "docking/memory/failure_memory.py": "tests/test_docking_protocol.py",
    "docking/letters/side_letters.jsonl": "tests/test_sideletter_protocol.py",
    "core/contracts/docking/SideLetter.py": "tests/test_sideletter_protocol.py",
    "docking/improvement/pipeline.py": "tests/test_closed_loop_improvement.py",
    "docking/improvement/tester.py": "tests/test_closed_loop_improvement.py",
    "docking/improvement/selector.py": "tests/test_closed_loop_improvement.py",
    "core/contracts/docking/ImprovementProposal.py": "tests/test_closed_loop_improvement.py",
    "core/contracts/docking/ImprovementRecord.py": "tests/test_closed_loop_improvement.py",
}


def _project_root(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Resolve the project root used for test discovery."""
    if project_root is not None:
        return Path(project_root).resolve()
    return Path(__file__).resolve().parents[2]


def _normalize_path(value: str) -> str:
    """Normalize a module/path token for deterministic matching."""
    return value.strip().replace("\\", "/").lstrip("./")


class TestSelector:
    __test__ = False

    """Select only tests relevant to an ImprovementProposal.

    The selector is intentionally lightweight and deterministic. It maps known
    module paths directly, then falls back to path stem and keyword matching.
    It never returns the full suite unless a future proposal explicitly adds an
    allowed full-suite mechanism; SPEC-0003 does not define that mechanism.
    """

    def __init__(self, project_root: Optional[Union[str, Path]] = None) -> None:
        """Create a selector rooted at the current project."""
        self.project_root = _project_root(project_root)
        self.tests_root = self.project_root / "tests"

    def select_tests(self, proposal: ImprovementProposal) -> List[str]:
        """Return relevant test paths for the proposal.

        Args:
            proposal: Strict improvement proposal.

        Returns:
            Ordered project-relative pytest targets. The list may be empty when
            no relevant tests can be mapped; callers must treat that as a
            failed fast-tester result rather than running the full suite.
        """
        selected: List[str] = []
        modules = [_normalize_path(item) for item in proposal.target_modules]
        for module in modules:
            mapped = _PATH_TEST_MAP.get(module)
            if mapped:
                self._append_if_exists(selected, mapped)
            stem = Path(module).stem.lower()
            if stem:
                candidate = f"tests/test_{stem}.py"
                self._append_if_exists(selected, candidate)
            if module.startswith("core/contracts/docking/"):
                self._append_if_exists(selected, "tests/test_docking_protocol.py")
                self._append_if_exists(selected, "tests/test_closed_loop_improvement.py")

        description = " ".join(
            [proposal.description, proposal.expected_outcome]
            + proposal.target_functions
            + [str(action) for action in proposal.proposed_actions]
        ).lower()
        tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]+", description))
        for keyword, test_path in sorted(_KEYWORD_TEST_MAP.items()):
            if keyword in tokens or keyword in description:
                self._append_if_exists(selected, test_path)
        return selected

    def selection_report(self, proposal: ImprovementProposal) -> Dict[str, object]:
        """Return selected tests and deterministic selection rationale."""
        selected = self.select_tests(proposal)
        return {
            "contract": TEST_SELECTOR_CONTRACT,
            "proposal_id": proposal.proposal_id,
            "selected_tests": selected,
            "target_modules": proposal.target_modules,
            "target_functions": proposal.target_functions,
            "reason": "module/path/keyword deterministic mapping" if selected else "no relevant tests mapped",
        }

    def _append_if_exists(self, selected: List[str], relative_path: str) -> None:
        """Append a test path only when it exists and is not duplicated."""
        if relative_path in selected:
            return
        if (self.project_root / relative_path).exists():
            selected.append(relative_path)


__all__ = ["TEST_SELECTOR_CONTRACT", "TestSelector"]
