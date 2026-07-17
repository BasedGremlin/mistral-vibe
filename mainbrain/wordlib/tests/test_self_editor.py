"""
Tests for self_editor -- the safety-critical write engine.
These guard the single most important invariant: edits are reversible and
broken code never lands. If these break, the whole self-modification story
is unsafe.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from self_editor import _validate_python, get_editor


def test_validate_python_accepts_good_code():
    ok, msg = _validate_python("x = 1\ndef f():\n    return x\n")
    assert ok is True


def test_validate_python_rejects_broken_code():
    ok, msg = _validate_python("def f(:\n    broken")
    assert ok is False
    assert "SyntaxError" in msg or "syntax" in msg.lower()


def test_editor_singleton():
    e1 = get_editor()
    e2 = get_editor()
    assert e1 is e2


def test_write_creates_backup_and_rollback_restores():
    """The core safety invariant: write backs up, rollback restores PRIOR content.

    This guards a real bug class: if rollback restores the current (post-change)
    content instead of the prior content, the safety rail is silently broken.
    """
    editor = get_editor()
    rel = "storage/kb/_test_rollback.md"
    root = Path(__file__).resolve().parents[1]
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)

    # First write establishes ORIGINAL (new file -> no backup yet)
    editor.write_file(rel, "ORIGINAL\n")
    # Second write backs up ORIGINAL, then writes MODIFIED
    r = editor.write_file(rel, "MODIFIED\n")
    assert r.get("ok") is True
    assert target.read_text().strip() == "MODIFIED"

    # Rollback must restore ORIGINAL, not leave MODIFIED in place
    rb = editor.rollback(rel)
    assert rb.get("ok") is True
    assert target.read_text().strip() == "ORIGINAL", \
        "rollback restored the wrong version -- safety rail broken"

    # cleanup file + its backups
    if target.exists():
        target.unlink()
    from self_editor import _BACKUPS
    for b in _BACKUPS.glob("storage__kb___test_rollback*"):
        b.unlink()


def test_write_rejects_broken_python():
    """Broken Python must never be written to a .py file."""
    editor = get_editor()
    rel = "src/_test_broken.py"
    result = editor.write_file(rel, "def broken(:\n    nope")
    assert result.get("ok") is False
