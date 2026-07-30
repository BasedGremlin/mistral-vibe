"""SPEC-TESTED_PATCH_EXECUTION_SANDBOX -- isolated patched-candidate testing.

The wound this closes
---------------------
``FastTargetedTester`` runs selector-mapped tests with ``cwd=self.project_root``
-- the LIVE tree. A patch therefore had to be written into the live tree before
it could be tested, so "tests passed" was a claim about a mutated production
workspace, not proof about a candidate. A failing patch could leave the live
tree dirty, and a passing digest could be propagated without any isolated run.

What this module does instead
-----------------------------
1. MATERIALIZE an isolated candidate workspace (copy of the tree, minus runtime
   state, venvs, caches, models and backups).
2. APPLY the patch inside the candidate ONLY. Paths that escape the candidate
   root are rejected before any write.
3. TEST inside the candidate (``cwd=candidate_root``), never the live tree.
4. PROMOTE only on green, and only with an explicit human approval token.

The live tree is fingerprinted before and after every run, and the fingerprints
are part of the result. Isolation is therefore *proven per run*, not asserted:
if a sandbox execution ever mutated the live tree, ``live_tree_untouched``
would be ``False`` and the result would refuse promotion.

Honesty line: a green sandbox is evidence that the patched candidate passed the
selected tests. It is not proof of correctness, and it never auto-applies.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

SANDBOX_CONTRACT = "neuroforge.docking.improvement.sandbox.v1.0"

#: Directories never copied into a candidate workspace. Runtime state, virtual
#: environments, caches, model weights and backups are either huge, machine
#: specific, or would let a candidate mutate real operator data.
EXCLUDED_DIRS = frozenset({
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".pip_cache",
    "backups", "data", "logs", "models", "node_modules", ".mypy_cache",
})

#: Only these suffixes are copied. Keeps candidates small and fast.
COPIED_SUFFIXES = frozenset({
    ".py", ".json", ".xml", ".md", ".txt", ".html", ".ini", ".cfg", ".toml",
    ".jsonl", ".yml", ".yaml",
})

VERDICT_PROMOTABLE = "promotable"
VERDICT_TESTS_FAILED = "tests_failed"
VERDICT_NO_TESTS = "no_tests_selected"
VERDICT_REJECTED_PATH = "rejected_path_escape"
VERDICT_ISOLATION_BREACH = "isolation_breach"
VERDICT_ERROR = "sandbox_error"


class SandboxPathError(ValueError):
    """A change targeted a path outside the candidate workspace."""


@dataclass(frozen=True)
class SandboxResult:
    """Outcome of one isolated patched-candidate execution."""

    sandbox_id: str
    verdict: str
    applied_files: List[str] = field(default_factory=list)
    selected_tests: List[str] = field(default_factory=list)
    tests_passed: bool = False
    timed_out: bool = False
    duration: float = 0.0
    failing_tests: List[str] = field(default_factory=list)
    command: List[str] = field(default_factory=list)
    candidate_root: Optional[str] = None
    live_fingerprint_before: str = ""
    live_fingerprint_after: str = ""
    reasons: List[str] = field(default_factory=list)
    contract: str = SANDBOX_CONTRACT

    @property
    def live_tree_untouched(self) -> bool:
        """True when the live tree is byte-identical before and after the run."""
        return (
            bool(self.live_fingerprint_before)
            and self.live_fingerprint_before == self.live_fingerprint_after
        )

    @property
    def promotable(self) -> bool:
        """Green tests AND proven isolation. Both are required."""
        return (
            self.verdict == VERDICT_PROMOTABLE
            and self.tests_passed
            and self.live_tree_untouched
        )

    def record_provenance(self) -> Dict[str, Any]:
        """Fields to stamp onto an ImprovementRecord for Gate 7.5.

        ``sandbox_verified`` is True only when this run was promotable, which
        requires green tests AND a live-tree fingerprint proven unchanged. That
        is the whole point: the flag is *earned by measurement* here, never
        assigned by construction, so the gate downstream is trusting evidence
        rather than an assertion.
        """
        return {
            "sandbox_verified": self.promotable,
            "sandbox_id": self.sandbox_id,
            "live_fingerprint_before": self.live_fingerprint_before,
            "live_fingerprint_after": self.live_fingerprint_after,
        }

    def as_dict(self) -> Dict[str, Any]:
        return {
            "sandbox_id": self.sandbox_id,
            "verdict": self.verdict,
            "applied_files": list(self.applied_files),
            "selected_tests": list(self.selected_tests),
            "tests_passed": self.tests_passed,
            "timed_out": self.timed_out,
            "duration": self.duration,
            "failing_tests": list(self.failing_tests),
            "command": list(self.command),
            "candidate_root": self.candidate_root,
            "live_tree_untouched": self.live_tree_untouched,
            "promotable": self.promotable,
            "reasons": list(self.reasons),
            "contract": self.contract,
        }


def fingerprint_tree(root: Union[str, Path]) -> str:
    """Content fingerprint of every source file under ``root``.

    Deterministic and order-independent: each file contributes
    ``relpath:sha256`` and the sorted set is hashed. Two trees with identical
    source content produce identical fingerprints.
    """
    root = Path(root).resolve()
    entries: List[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix not in COPIED_SUFFIXES:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append(f"{path.relative_to(root).as_posix()}:{digest}")
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


class TestedPatchSandbox:
    """Materialize, patch, and test an isolated candidate workspace."""

    #: Not a pytest test class despite the leading "Tested" -- stops collection.
    __test__ = False

    def __init__(
        self,
        project_root: Optional[Union[str, Path]] = None,
        *,
        workspace_root: Optional[Union[str, Path]] = None,
        timeout_seconds: float = 120.0,
        keep_on_failure: bool = True,
    ) -> None:
        """Create a sandbox runner.

        Args:
            project_root: Live tree to copy from. Defaults to the wordlib root.
            workspace_root: Where candidates are materialized. Defaults to a
                temporary directory, so candidates never land inside the live
                tree where a stray test run could pick them up.
            timeout_seconds: Hard cap on the candidate test subprocess.
            keep_on_failure: Retain the candidate workspace when tests fail, so
                a human can inspect what actually broke.
        """
        self.project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )
        self.workspace_root = (
            Path(workspace_root).resolve()
            if workspace_root is not None
            else Path(tempfile.gettempdir()) / "wordlib_sandboxes"
        )
        self.timeout_seconds = float(timeout_seconds)
        self.keep_on_failure = bool(keep_on_failure)

    # -- 1. materialize -----------------------------------------------------

    def materialize(self, sandbox_id: Optional[str] = None) -> Path:
        """Copy the live tree into a fresh isolated candidate workspace."""
        sandbox_id = sandbox_id or uuid.uuid4().hex[:12]
        candidate = self.workspace_root / f"candidate-{sandbox_id}"
        if candidate.exists():
            shutil.rmtree(candidate)
        candidate.mkdir(parents=True)

        for path in self.project_root.rglob("*"):
            rel = path.relative_to(self.project_root)
            if any(part in EXCLUDED_DIRS for part in rel.parts):
                continue
            if path.is_dir():
                continue
            if path.suffix not in COPIED_SUFFIXES:
                continue
            target = candidate / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        return candidate

    # -- 2. apply (candidate only) -----------------------------------------

    def apply(self, candidate_root: Path, changes: Dict[str, str]) -> List[str]:
        """Write ``changes`` into the candidate. Escaping paths are rejected.

        Args:
            candidate_root: Root of the materialized candidate.
            changes: Mapping of tree-relative path -> new file content.

        Returns:
            The relative paths written.

        Raises:
            SandboxPathError: if any target resolves outside the candidate.
        """
        candidate_root = candidate_root.resolve()
        resolved: List[tuple] = []
        # Validate EVERY path before writing ANY -- all-or-nothing, so a
        # rejected path cannot leave a half-patched candidate behind.
        for rel, content in changes.items():
            rel_path = Path(rel)
            if rel_path.is_absolute() or ".." in rel_path.parts:
                raise SandboxPathError(f"path {rel!r} escapes the candidate root")
            target = (candidate_root / rel_path).resolve()
            if candidate_root not in target.parents:
                raise SandboxPathError(f"path {rel!r} resolves outside the candidate root")
            if not isinstance(content, str):
                raise SandboxPathError(f"content for {rel!r} must be str")
            resolved.append((rel_path.as_posix(), target, content))

        written: List[str] = []
        for rel_posix, target, content in resolved:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written.append(rel_posix)
        return sorted(written)

    # -- 3. test (inside the candidate) ------------------------------------

    def run_tests(self, candidate_root: Path, tests: List[str]) -> Dict[str, Any]:
        """Run the selected tests with ``cwd`` set to the candidate root."""
        if not tests:
            return {
                "passed": False, "timed_out": False, "duration": 0.0,
                "failing": ["no relevant tests selected"], "command": [],
            }
        command = [sys.executable, "-m", "pytest", "-q", *tests]
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=str(candidate_root),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "passed": False, "timed_out": True,
                "duration": round(time.monotonic() - started, 6),
                "failing": [f"timeout after {self.timeout_seconds}s"],
                "command": command,
            }
        passed = completed.returncode == 0
        return {
            "passed": passed,
            "timed_out": False,
            "duration": round(time.monotonic() - started, 6),
            "failing": [] if passed else _extract_failures(completed.stdout, completed.stderr),
            "command": command,
        }

    # -- full cycle ---------------------------------------------------------

    def execute(
        self,
        changes: Dict[str, str],
        tests: List[str],
        *,
        sandbox_id: Optional[str] = None,
    ) -> SandboxResult:
        """Materialize, patch, and test -- proving the live tree is untouched."""
        sandbox_id = sandbox_id or uuid.uuid4().hex[:12]
        before = fingerprint_tree(self.project_root)
        candidate: Optional[Path] = None
        try:
            candidate = self.materialize(sandbox_id)
            try:
                applied = self.apply(candidate, changes)
            except SandboxPathError as exc:
                shutil.rmtree(candidate, ignore_errors=True)
                return SandboxResult(
                    sandbox_id=sandbox_id,
                    verdict=VERDICT_REJECTED_PATH,
                    live_fingerprint_before=before,
                    live_fingerprint_after=fingerprint_tree(self.project_root),
                    reasons=[str(exc)],
                )

            outcome = self.run_tests(candidate, tests)
            after = fingerprint_tree(self.project_root)

            if before != after:
                # Should be impossible; surfaced loudly rather than trusted.
                return SandboxResult(
                    sandbox_id=sandbox_id, verdict=VERDICT_ISOLATION_BREACH,
                    applied_files=applied, selected_tests=list(tests),
                    tests_passed=False, duration=outcome["duration"],
                    failing_tests=outcome["failing"], command=outcome["command"],
                    candidate_root=str(candidate),
                    live_fingerprint_before=before, live_fingerprint_after=after,
                    reasons=["live tree changed during sandbox execution"],
                )

            if not tests:
                verdict, reasons = VERDICT_NO_TESTS, ["no tests selected; refusing to promote"]
            elif outcome["passed"]:
                verdict, reasons = VERDICT_PROMOTABLE, []
            else:
                verdict, reasons = VERDICT_TESTS_FAILED, ["candidate failed selected tests"]

            keep = self.keep_on_failure and verdict != VERDICT_PROMOTABLE
            result = SandboxResult(
                sandbox_id=sandbox_id, verdict=verdict, applied_files=applied,
                selected_tests=list(tests), tests_passed=bool(outcome["passed"]),
                timed_out=bool(outcome["timed_out"]), duration=outcome["duration"],
                failing_tests=outcome["failing"], command=outcome["command"],
                candidate_root=str(candidate) if keep else None,
                live_fingerprint_before=before, live_fingerprint_after=after,
                reasons=reasons,
            )
            if not keep:
                shutil.rmtree(candidate, ignore_errors=True)
            return result
        except Exception as exc:  # noqa: BLE001 - sandbox boundary
            if candidate is not None:
                shutil.rmtree(candidate, ignore_errors=True)
            return SandboxResult(
                sandbox_id=sandbox_id, verdict=VERDICT_ERROR,
                live_fingerprint_before=before,
                live_fingerprint_after=fingerprint_tree(self.project_root),
                reasons=[f"{type(exc).__name__}: {exc}"],
            )

    # -- 4. promote (gated) -------------------------------------------------

    def promote(
        self,
        result: SandboxResult,
        changes: Dict[str, str],
        *,
        approved_by: str = "",
    ) -> Dict[str, Any]:
        """Apply a sandbox-proven patch to the live tree.

        Requires BOTH a promotable sandbox result and an explicit human
        approval token. Either missing -> refusal, nothing written. Writes go
        through SelfEditor so the existing backup/rollback rail still owns the
        only write path.
        """
        if not result.promotable:
            return {
                "ok": False, "status": "refused_not_promotable",
                "reason": f"verdict={result.verdict}, tests_passed={result.tests_passed}, "
                          f"live_tree_untouched={result.live_tree_untouched}",
                "self_editor_called": False, "contract": SANDBOX_CONTRACT,
            }
        if not approved_by.strip():
            return {
                "ok": False, "status": "refused_no_human_approval",
                "reason": "promotion requires an explicit approved_by token; "
                          "a green sandbox alone never auto-applies",
                "self_editor_called": False, "contract": SANDBOX_CONTRACT,
            }
        if sorted(changes) != sorted(result.applied_files):
            return {
                "ok": False, "status": "refused_changeset_mismatch",
                "reason": "changes do not match the set proven in the sandbox",
                "self_editor_called": False, "contract": SANDBOX_CONTRACT,
            }

        written: List[str] = []
        try:
            editor = _get_self_editor(self.project_root)
            for rel, content in changes.items():
                # SelfEditor takes a root-relative path and owns backup +
                # syntax validation; a blocked write returns ok=False rather
                # than raising, so the status is checked explicitly.
                outcome = editor.write_file(rel, content)
                if not outcome.get("ok"):
                    return {
                        "ok": False, "status": "promotion_blocked_by_self_editor",
                        "reason": outcome.get("error", "self_editor refused the write"),
                        "blocked_file": rel, "written": sorted(written),
                        "self_editor_called": True, "contract": SANDBOX_CONTRACT,
                    }
                written.append(rel)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False, "status": "promotion_failed", "reason": str(exc),
                "written": sorted(written), "self_editor_called": True,
                "contract": SANDBOX_CONTRACT,
            }
        return {
            "ok": True, "status": "promoted", "written": sorted(written),
            "approved_by": approved_by.strip(), "sandbox_id": result.sandbox_id,
            "self_editor_called": True, "contract": SANDBOX_CONTRACT,
        }


def _get_self_editor(project_root: Path):
    """Import the real SelfEditor, keeping it the sole write path."""
    src = project_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from self_editor import get_editor  # noqa: PLC0415 - deliberate late import
    return get_editor()


def _extract_failures(stdout: str, stderr: str) -> List[str]:
    """Compact failing-test diagnostics from pytest output."""
    lines: List[str] = []
    for line in (stdout + "\n" + stderr).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "FAILED" in stripped or "ERROR" in stripped or stripped.startswith("E   "):
            lines.append(stripped[:240])
    return lines[-10:] or ["pytest returned non-zero status"]


def run_tested_patch_sandbox(
    changes: Dict[str, str],
    tests: List[str],
    *,
    project_root: Optional[Union[str, Path]] = None,
    timeout_seconds: float = 120.0,
) -> SandboxResult:
    """Convenience wrapper: one isolated patched-candidate execution."""
    return TestedPatchSandbox(
        project_root, timeout_seconds=timeout_seconds
    ).execute(changes, tests)


__all__ = [
    "SANDBOX_CONTRACT", "EXCLUDED_DIRS", "SandboxPathError", "SandboxResult",
    "TestedPatchSandbox", "fingerprint_tree", "run_tested_patch_sandbox",
    "VERDICT_PROMOTABLE", "VERDICT_TESTS_FAILED", "VERDICT_NO_TESTS",
    "VERDICT_REJECTED_PATH", "VERDICT_ISOLATION_BREACH", "VERDICT_ERROR",
]
