"""
Tests for EtherCore.EvolutionManager -- atomic self-modification.
Guards: single-file rollback on test failure, multi-file all-or-nothing.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ether_core import get_core

ROOT = Path(__file__).resolve().parents[1]


def _cleanup(*rels):
    for r in rels:
        p = ROOT / r
        if p.exists():
            p.unlink()


def test_single_file_valid_deploys():
    core = get_core()
    rel = "storage/kb/_evo_single.md"
    (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / rel).write_text("# original\n", encoding="utf-8")
    r = core.evolution.evolve_file(rel, "# evolved\n")
    assert r.success is True
    assert "evolved" in (ROOT / rel).read_text()
    _cleanup(rel)


def test_single_file_broken_python_rejected():
    core = get_core()
    r = core.evolution.evolve_file("src/_evo_broken.py", "def x(:\n bad")
    assert r.success is False
    assert r.error is not None


def test_multi_file_atomic_all_or_nothing():
    """If ANY file in the set is broken, NONE are written."""
    core = get_core()
    rel_py = "src/_evo_multi_ok.py"
    (ROOT / rel_py).write_text("ORIGINAL = 1\n", encoding="utf-8")
    before = (ROOT / rel_py).read_text()

    result = core.evolution.evolve_files({
        rel_py: "VALID = 2\n",
        "src/_evo_multi_bad.py": "def broken(:\n",   # invalid
    })
    assert result.success is False
    # The valid file must be UNCHANGED (atomic)
    assert (ROOT / rel_py).read_text() == before
    _cleanup(rel_py, "src/_evo_multi_bad.py")


def test_multi_file_all_valid_commits():
    core = get_core()
    a = "storage/kb/_evo_a.md"
    b = "storage/kb/_evo_b.md"
    (ROOT / a).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / a).write_text("a old\n", encoding="utf-8")
    (ROOT / b).write_text("b old\n", encoding="utf-8")
    result = core.evolution.evolve_files({a: "a new\n", b: "b new\n"})
    assert result.success is True
    assert "a new" in (ROOT / a).read_text()
    assert "b new" in (ROOT / b).read_text()
    _cleanup(a, b)
