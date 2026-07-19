"""Fast targeted self-tester for NEUROFORGE improvement proposals."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

from core.contracts.docking.ImprovementProposal import ImprovementProposal
from core.contracts.docking.ImprovementRecord import TestSuiteResult
from docking.improvement.selector import TestSelector

FAST_TESTER_CONTRACT = "neuroforge.docking.improvement.tester.v1.0"


def _project_root(project_root: Optional[Union[str, Path]] = None) -> Path:
    """Resolve the project root used for targeted test execution."""
    if project_root is not None:
        return Path(project_root).resolve()
    return Path(__file__).resolve().parents[2]


class FastTargetedTester:
    """Run only selector-mapped tests for an ImprovementProposal.

    The tester never falls back to the full test suite. If no relevant tests are
    selected, the result is a deterministic failure. This is safer than running
    unrelated tests and accidentally approving an untested proposal.
    """

    def __init__(
        self,
        project_root: Optional[Union[str, Path]] = None,
        *,
        timeout_seconds: float = 30.0,
        max_concurrent_tests: int = 1,
        memory_guard_mb: int = 1024,
    ) -> None:
        """Create a timeout-protected targeted tester.

        Args:
            project_root: Optional project root override.
            timeout_seconds: Maximum subprocess runtime per proposal.
            max_concurrent_tests: Declared concurrency guard. The stdlib
                runner executes one subprocess, so this remains one by design.
            memory_guard_mb: Declared memory guard for audit/result metadata.
        """
        self.project_root = _project_root(project_root)
        self.timeout_seconds = float(timeout_seconds)
        self.max_concurrent_tests = max(1, int(max_concurrent_tests))
        self.memory_guard_mb = max(1, int(memory_guard_mb))
        self.selector = TestSelector(self.project_root)

    def run(self, proposal: ImprovementProposal) -> TestSuiteResult:
        """Run selector-mapped tests and return a structured result.

        Args:
            proposal: Strict proposal to test.

        Returns:
            A deterministic TestSuiteResult containing selected tests, command,
            timeout status, and failing tests/reasons.
        """
        started = time.monotonic()
        selected_tests = self.selector.select_tests(proposal)
        resource_limits: Dict[str, Any] = {
            "timeout_seconds": self.timeout_seconds,
            "max_concurrent_tests": self.max_concurrent_tests,
            "memory_guard_mb": self.memory_guard_mb,
            "full_suite_allowed": False,
            "contract": FAST_TESTER_CONTRACT,
        }
        if not selected_tests:
            return TestSuiteResult(
                passed=False,
                duration=0.0,
                selected_tests=[],
                failing_tests=["no relevant tests selected"],
                timed_out=False,
                coverage_delta=None,
                command=[],
                resource_limits=resource_limits,
            )
        command = [sys.executable, "-m", "pytest", "-q", *selected_tests]
        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                check=False,
            )
            duration = round(time.monotonic() - started, 6)
            passed = completed.returncode == 0
            failing_tests = [] if passed else self._extract_failures(completed.stdout, completed.stderr)
            return TestSuiteResult(
                passed=passed,
                duration=duration,
                selected_tests=selected_tests,
                failing_tests=failing_tests,
                timed_out=False,
                coverage_delta=None,
                command=command,
                resource_limits=resource_limits,
            )
        except subprocess.TimeoutExpired as exc:
            duration = round(time.monotonic() - started, 6)
            return TestSuiteResult(
                passed=False,
                duration=duration,
                selected_tests=selected_tests,
                failing_tests=[f"timeout after {self.timeout_seconds}s", str(exc)],
                timed_out=True,
                coverage_delta=None,
                command=command,
                resource_limits=resource_limits,
            )

    @staticmethod
    def _extract_failures(stdout: str, stderr: str) -> list[str]:
        """Extract compact failing-test diagnostics from pytest output."""
        lines = []
        for line in (stdout + "\n" + stderr).splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if "FAILED" in stripped or "ERROR" in stripped or stripped.startswith("E   "):
                lines.append(stripped[:240])
        return lines[-10:] or ["pytest returned non-zero status"]


def run_fast_targeted_tests(
    proposal: ImprovementProposal,
    *,
    project_root: Optional[Union[str, Path]] = None,
    timeout_seconds: float = 30.0,
    max_concurrent_tests: int = 1,
    memory_guard_mb: int = 1024,
) -> TestSuiteResult:
    """Convenience wrapper for running the fast targeted tester."""
    tester = FastTargetedTester(
        project_root,
        timeout_seconds=timeout_seconds,
        max_concurrent_tests=max_concurrent_tests,
        memory_guard_mb=memory_guard_mb,
    )
    return tester.run(proposal)


__all__ = ["FAST_TESTER_CONTRACT", "FastTargetedTester", "run_fast_targeted_tests"]
