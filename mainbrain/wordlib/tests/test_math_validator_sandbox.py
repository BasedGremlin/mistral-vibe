"""Security regression tests for the arithmetic fallback evaluator.

MathValidator exists to check arithmetic claims found in model output, so every
string reaching its fallback evaluator is untrusted by construction. That path
previously used `eval()` with `{"__builtins__": {}}` -- the textbook "safe eval",
which is not safe, because attribute access still lets an expression walk from a
literal to any loaded class and back out to the interpreter.

This was not a theoretical concern. Run against the code as it stood, the
expression in `test_documented_escape_no_longer_executes` returned a real
directory listing.

These tests pin the allowlist shut. They deliberately force the fallback path
(`_HAVE_SYMPY = False`) because sympy is normally present and would mask it --
the vulnerable branch is the one that runs on a minimal deploy, which is exactly
where nobody is looking.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import reasoning.math_validator as mv
from reasoning.math_validator import UnsafeExpression, safe_eval_arithmetic


@pytest.fixture
def fallback_validator(monkeypatch):
    """A validator forced onto the non-sympy arithmetic path."""
    monkeypatch.setattr(mv, "_HAVE_SYMPY", False)
    return mv.MathValidator()


# ── The escapes ──────────────────────────────────────────────────────────────
def test_documented_escape_no_longer_executes(fallback_validator):
    """The exact payload that previously listed the filesystem."""
    payload = (
        "[c for c in ().__class__.__mro__[1].__subclasses__() "
        "if c.__name__=='BuiltinImporter'][0].load_module('os').listdir('.')"
    )
    result = fallback_validator.simplify(payload)
    assert result.ok is False


@pytest.mark.parametrize("payload", [
    "().__class__",                                  # the first step of the chain
    "().__class__.__mro__[1].__subclasses__()",      # class walk
    "__import__('os').listdir('.')",                 # direct import
    "open('/etc/passwd').read()",                    # direct file read
    "(lambda: 1)()",                                 # lambda
    "[x for x in range(3)]",                         # comprehension
    "globals()",                                     # namespace access
    "1 if open('x') else 2",                         # conditional smuggling a call
    "'abc'.upper()",                                 # method call via attribute
    "[1,2,3][0]",                                    # subscript
    "{'a': 1}",                                      # dict literal
    "print(1)",                                      # non-allowlisted builtin
])
def test_non_arithmetic_syntax_is_refused(payload):
    """Anything outside the arithmetic allowlist must not evaluate.

    Parametrized over construct *kinds* rather than a list of known exploits:
    the allowlist is meant to be safe by what it permits, so the test asserts
    the shape of the permission rather than chasing a blacklist.
    """
    with pytest.raises(UnsafeExpression):
        safe_eval_arithmetic(payload)


def test_attribute_access_is_refused_at_any_depth():
    """Attribute access is the single step every escape of this shape needs."""
    for expr in ("(1).real", "(1.0).__class__", "().__class__.__base__"):
        with pytest.raises(UnsafeExpression):
            safe_eval_arithmetic(expr)


def test_huge_exponent_is_refused_rather_than_hanging():
    """A validator that can be stalled by the text it validates is a DoS surface."""
    with pytest.raises(UnsafeExpression):
        safe_eval_arithmetic("9**9**9")


def test_overlong_input_is_refused():
    with pytest.raises(UnsafeExpression):
        safe_eval_arithmetic("1+" * 400 + "1")


def test_string_constants_are_refused():
    """Only numbers are arithmetic; a string constant has no business here."""
    with pytest.raises(UnsafeExpression):
        safe_eval_arithmetic("'a' * 3")


def test_booleans_are_not_treated_as_numbers():
    with pytest.raises(UnsafeExpression):
        safe_eval_arithmetic("True + 1")


# ── Legitimate arithmetic still works ────────────────────────────────────────
@pytest.mark.parametrize("expr,expected", [
    ("2+2", 4),
    ("10 - 3 * 2", 4),
    ("(1+2)*3", 9),
    ("7 / 2", 3.5),
    ("7 // 2", 3),
    ("7 % 2", 1),
    ("2**10", 1024),
    ("-5", -5),
    ("sqrt(16)", 4.0),
    ("max(3, 7)", 7),
    ("abs(-4)", 4),
    ("round(3.7)", 4),
])
def test_arithmetic_still_evaluates(expr, expected):
    """The fix must not cost the capability it protects."""
    assert safe_eval_arithmetic(expr) == expected


def test_math_constants_resolve():
    assert abs(safe_eval_arithmetic("pi") - 3.14159265) < 1e-6
    assert abs(safe_eval_arithmetic("e") - 2.71828182) < 1e-6


def test_nested_allowed_calls_work():
    assert safe_eval_arithmetic("sqrt(abs(-16))") == 4.0


def test_validator_equality_still_works_on_fallback(fallback_validator):
    assert fallback_validator.check_equality("2*3", "6").ok is True
    assert fallback_validator.check_equality("2*3", "7").ok is False


def test_validator_simplify_still_works_on_fallback(fallback_validator):
    result = fallback_validator.simplify("3 * (2 + 2)")
    assert result.ok is True
    assert result.mode == "fallback"
    assert "12" in str(result.value)


def test_refusal_is_reported_not_raised(fallback_validator):
    """Callers get a MathResult saying it failed, not an exception.

    The validator's contract is to return a verdict; a refusal is a verdict
    about untrusted input, not an error in the caller.
    """
    result = fallback_validator.simplify("__import__('os')")
    assert result.ok is False
    assert result.mode == "fallback"
    assert "evaluate" in result.detail.lower()
