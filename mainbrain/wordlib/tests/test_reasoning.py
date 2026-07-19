"""
Tests for the reasoning stack. Where the math is exact (uncertainty, softmax),
assert exact values -- these are real formulas, not vibes.
"""
import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reasoning import (OutputQualityChecker, MathValidator, CodeReasoner,
                       UncertaintyQuantifier, QuantumInspiredOptimizer,
                       Hypothesis, softmax, StructuredOutputEngine)


# ── Output quality ───────────────────────────────────────────────────────────
def test_quality_flags_overconfidence():
    c = OutputQualityChecker()
    r = c.check("This is 100% guaranteed flawless, it just works, trust me.")
    assert r.passed is False
    assert r.score < 0.5


def test_quality_passes_clean_evidence_based():
    c = OutputQualityChecker()
    r = c.check("The parser was tested against 12 cases; see test_parse.py. "
                "Empty files raise ValueError because a header row is required.")
    assert r.passed is True


def test_quality_empty_input():
    c = OutputQualityChecker()
    r = c.check("")
    assert r.passed is False


# ── Math validator (real sympy) ──────────────────────────────────────────────
def test_math_equality_true():
    mv = MathValidator()
    r = mv.check_equality("(x+1)**2", "x**2 + 2*x + 1")
    assert r.ok is True


def test_math_equality_false():
    mv = MathValidator()
    r = mv.check_equality("x + 1", "x + 2")
    assert r.ok is False


def test_math_solve():
    mv = MathValidator()
    r = mv.solve_equation("x**2 - 4", "x")
    # solutions should include -2 and 2
    assert "2" in r.detail


# ── Code reasoner (real ast) ─────────────────────────────────────────────────
def test_code_reasoner_flags_eval():
    cr = CodeReasoner()
    v = cr.safety_verdict("def f(x):\n    return eval(x)")
    assert v["safe"] is False


def test_code_reasoner_passes_clean():
    cr = CodeReasoner()
    v = cr.safety_verdict("def add(a, b):\n    return a + b")
    assert v["safe"] is True


def test_code_reasoner_syntax_error():
    cr = CodeReasoner()
    a = cr.analyze("def broken(:\n")
    assert a.ok is False


# ── Uncertainty (exact real statistics) ──────────────────────────────────────
def test_wilson_interval_bounds():
    uq = UncertaintyQuantifier()
    iv = uq.wilson_interval(7, 10)
    assert iv.point == 0.7
    assert 0.0 <= iv.low < iv.point < iv.high <= 1.0


def test_brier_perfect_is_zero():
    uq = UncertaintyQuantifier()
    # Perfect predictions: prob 1 -> outcome 1, prob 0 -> outcome 0
    assert uq.brier_score([(1.0, 1), (0.0, 0)]) == 0.0


def test_brier_worst_is_one():
    uq = UncertaintyQuantifier()
    # Confidently wrong both times
    assert uq.brier_score([(1.0, 0), (0.0, 1)]) == 1.0


def test_ece_perfect_calibration():
    uq = UncertaintyQuantifier()
    # If confidence matches accuracy exactly, ECE should be low
    ece = uq.expected_calibration_error([(1.0, 1), (1.0, 1), (0.0, 0)])
    assert ece < 0.01


# ── Quantum-inspired (classical) ─────────────────────────────────────────────
def test_softmax_sums_to_one():
    probs = softmax([1.0, 2.0, 3.0])
    assert abs(sum(probs) - 1.0) < 1e-9


def test_softmax_empty():
    assert softmax([]) == []


def test_hypothesis_scoring_distribution():
    qi = QuantumInspiredOptimizer()
    ranked = qi.parallel_hypothesis_scoring(
        [Hypothesis("A", 0.9), Hypothesis("B", 0.1)])
    # Higher raw score should get higher probability
    a = next(r for r in ranked if r["name"] == "A")
    b = next(r for r in ranked if r["name"] == "B")
    assert a["probability"] > b["probability"]
    assert abs(sum(r["probability"] for r in ranked) - 1.0) < 1e-6


def test_annealing_returns_valid_assignment():
    qi = QuantumInspiredOptimizer()
    cost = lambda t, a: abs(hash(t + a)) % 10
    result = qi.annealing_task_allocation(["t1", "t2"], ["x", "y"], cost, iterations=100)
    assert set(result["assignment"].keys()) == {"t1", "t2"}
    assert all(v in ("x", "y") for v in result["assignment"].values())


# ── Structured output ────────────────────────────────────────────────────────
def test_json_engine_repairs_fenced():
    soe = StructuredOutputEngine()
    r = soe.parse('```json\n{"a": 1, "b": 2,}\n```trailing prose')
    assert r.ok is True
    assert r.data == {"a": 1, "b": 2}


def test_json_engine_caches():
    soe = StructuredOutputEngine()
    text = '{"x": 1}'
    r1 = soe.parse(text)
    r2 = soe.parse(text)
    assert r2.from_cache is True
