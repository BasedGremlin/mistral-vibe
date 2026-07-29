"""
SPEC-TESTED_PATCH_EXECUTION_SANDBOX.
Proves the isolation property the spec exists for: tests run against a patched
CANDIDATE, never the live tree, and promotion requires green tests plus an
explicit human approval token.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from docking.improvement.sandbox import (
    SANDBOX_CONTRACT,
    VERDICT_NO_TESTS,
    VERDICT_PROMOTABLE,
    VERDICT_REJECTED_PATH,
    VERDICT_TESTS_FAILED,
    SandboxPathError,
    TestedPatchSandbox,
    fingerprint_tree,
)


# ── A miniature project to sandbox (fast, hermetic) ──────────────────────────
def _mini_project(tmp_path: Path) -> Path:
    root = tmp_path / "live"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (root / "tests" / "test_calc.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))\n"
        "from calc import add\n\n"
        "def test_add():\n"
        "    assert add(2, 2) == 4\n"
    )
    return root


def _sandbox(tmp_path: Path, root: Path) -> TestedPatchSandbox:
    return TestedPatchSandbox(
        root, workspace_root=tmp_path / "sandboxes", timeout_seconds=60.0
    )


# ── Fingerprinting ───────────────────────────────────────────────────────────
def test_fingerprint_is_stable_and_content_sensitive(tmp_path):
    root = _mini_project(tmp_path)
    first = fingerprint_tree(root)
    assert first == fingerprint_tree(root), "same content must fingerprint identically"
    (root / "src" / "calc.py").write_text("def add(a, b):\n    return a + b + 1\n")
    assert fingerprint_tree(root) != first, "changed content must change the fingerprint"


# ── The core isolation property ──────────────────────────────────────────────
def test_passing_patch_never_touches_the_live_tree(tmp_path):
    root = _mini_project(tmp_path)
    before = (root / "src" / "calc.py").read_text()

    sandbox = _sandbox(tmp_path, root)
    result = sandbox.execute(
        {"src/calc.py": "def add(a, b):\n    return b + a\n"},
        ["tests/test_calc.py"],
    )

    assert result.verdict == VERDICT_PROMOTABLE
    assert result.tests_passed is True
    assert result.live_tree_untouched is True
    assert result.promotable is True
    assert result.applied_files == ["src/calc.py"]
    # The live file is byte-identical -- the patch existed only in the candidate.
    assert (root / "src" / "calc.py").read_text() == before


def test_failing_patch_leaves_live_tree_clean(tmp_path):
    root = _mini_project(tmp_path)
    before = (root / "src" / "calc.py").read_text()

    result = _sandbox(tmp_path, root).execute(
        {"src/calc.py": "def add(a, b):\n    return a - b\n"},  # breaks the test
        ["tests/test_calc.py"],
    )

    assert result.verdict == VERDICT_TESTS_FAILED
    assert result.tests_passed is False
    assert result.promotable is False
    assert result.failing_tests, "a failure must carry diagnostics"
    assert result.live_tree_untouched is True
    assert (root / "src" / "calc.py").read_text() == before, "live tree must stay clean"


def test_candidate_actually_contains_the_patch(tmp_path):
    """Isolation must not be achieved by simply not applying the patch."""
    root = _mini_project(tmp_path)
    sandbox = _sandbox(tmp_path, root)
    candidate = sandbox.materialize("probe")
    sandbox.apply(candidate, {"src/calc.py": "def add(a, b):\n    return 99\n"})

    assert (candidate / "src" / "calc.py").read_text() == "def add(a, b):\n    return 99\n"
    assert (root / "src" / "calc.py").read_text() != (candidate / "src" / "calc.py").read_text()
    # Failing candidate proves the patch is the code under test.
    outcome = sandbox.run_tests(candidate, ["tests/test_calc.py"])
    assert outcome["passed"] is False


def test_failed_candidate_is_retained_for_forensics(tmp_path):
    root = _mini_project(tmp_path)
    result = _sandbox(tmp_path, root).execute(
        {"src/calc.py": "def add(a, b):\n    return a - b\n"},
        ["tests/test_calc.py"],
    )
    assert result.candidate_root is not None
    assert Path(result.candidate_root).is_dir(), "failed candidate kept for inspection"


# ── Path-escape rejection ────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", ["../escape.py", "/etc/passwd", "src/../../out.py"])
def test_escaping_paths_are_rejected(tmp_path, bad):
    root = _mini_project(tmp_path)
    result = _sandbox(tmp_path, root).execute({bad: "x = 1\n"}, ["tests/test_calc.py"])
    assert result.verdict == VERDICT_REJECTED_PATH
    assert result.promotable is False


def test_apply_is_all_or_nothing_on_bad_path(tmp_path):
    root = _mini_project(tmp_path)
    sandbox = _sandbox(tmp_path, root)
    candidate = sandbox.materialize("atomic")
    original = (candidate / "src" / "calc.py").read_text()

    with pytest.raises(SandboxPathError):
        sandbox.apply(candidate, {
            "src/calc.py": "def add(a, b):\n    return 0\n",  # valid
            "../escape.py": "x = 1\n",                        # invalid
        })
    assert (candidate / "src" / "calc.py").read_text() == original, \
        "a rejected path must not leave a half-patched candidate"


# ── Promotion gate ───────────────────────────────────────────────────────────
def test_no_tests_selected_refuses_promotion(tmp_path):
    root = _mini_project(tmp_path)
    result = _sandbox(tmp_path, root).execute({"src/calc.py": "def add(a, b):\n    return b + a\n"}, [])
    assert result.verdict == VERDICT_NO_TESTS
    assert result.promotable is False


def test_promote_refuses_without_human_approval(tmp_path):
    root = _mini_project(tmp_path)
    sandbox = _sandbox(tmp_path, root)
    changes = {"src/calc.py": "def add(a, b):\n    return b + a\n"}
    result = sandbox.execute(changes, ["tests/test_calc.py"])
    assert result.promotable is True

    refused = sandbox.promote(result, changes, approved_by="")
    assert refused["ok"] is False
    assert refused["status"] == "refused_no_human_approval"
    assert refused["self_editor_called"] is False
    assert (root / "src" / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"


def test_promote_refuses_a_failed_sandbox(tmp_path):
    root = _mini_project(tmp_path)
    sandbox = _sandbox(tmp_path, root)
    changes = {"src/calc.py": "def add(a, b):\n    return a - b\n"}
    result = sandbox.execute(changes, ["tests/test_calc.py"])

    refused = sandbox.promote(result, changes, approved_by="johannes")
    assert refused["ok"] is False
    assert refused["status"] == "refused_not_promotable"
    assert refused["self_editor_called"] is False


def test_promote_refuses_a_changeset_swap(tmp_path):
    """Only the exact set proven in the sandbox may be promoted."""
    root = _mini_project(tmp_path)
    sandbox = _sandbox(tmp_path, root)
    proven = {"src/calc.py": "def add(a, b):\n    return b + a\n"}
    result = sandbox.execute(proven, ["tests/test_calc.py"])
    assert result.promotable is True

    smuggled = dict(proven)
    smuggled["src/evil.py"] = "import os\n"
    refused = sandbox.promote(result, smuggled, approved_by="johannes")
    assert refused["ok"] is False
    assert refused["status"] == "refused_changeset_mismatch"
    assert refused["self_editor_called"] is False


def test_result_carries_contract_and_serializes(tmp_path):
    root = _mini_project(tmp_path)
    result = _sandbox(tmp_path, root).execute(
        {"src/calc.py": "def add(a, b):\n    return b + a\n"}, ["tests/test_calc.py"]
    )
    payload = result.as_dict()
    assert payload["contract"] == SANDBOX_CONTRACT
    assert payload["live_tree_untouched"] is True
    assert payload["promotable"] is True
    import json
    json.dumps(payload)  # must be JSON-serializable for audit records


# ── Runtime state is never copied into a candidate ───────────────────────────
def test_runtime_state_is_excluded_from_candidates(tmp_path):
    root = _mini_project(tmp_path)
    (root / "data").mkdir()
    (root / "data" / "ledger.jsonl").write_text('{"real":"operator data"}\n')
    (root / "backups").mkdir()
    (root / "backups" / "old.py.bak").write_text("stale\n")
    (root / ".venv" / "lib").mkdir(parents=True)
    (root / ".venv" / "lib" / "huge.py").write_text("x = 1\n")

    candidate = _sandbox(tmp_path, root).materialize("excl")
    assert not (candidate / "data").exists(), "operator data must never enter a candidate"
    assert not (candidate / "backups").exists()
    assert not (candidate / ".venv").exists()
    assert (candidate / "src" / "calc.py").exists(), "source must still be copied"
