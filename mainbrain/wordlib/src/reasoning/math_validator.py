"""
Mathematical & Logical Validator.
=================================
Uses sympy when available for REAL symbolic validation; falls back to safe
arithmetic evaluation otherwise. Honest about which mode it's in.

What it really does:
  - validate arithmetic/algebraic equalities (sympy: symbolic; fallback: numeric)
  - simplify expressions
  - check a claimed expression equals an expected one
  - evaluate boolean logic consistency for simple propositional statements

It does NOT prove arbitrary theorems or "validate reasoning" in general.
"""

from __future__ import annotations

import ast
import math
import operator
from dataclasses import dataclass
from typing import Optional

try:
    import sympy
    _HAVE_SYMPY = True
except Exception:
    _HAVE_SYMPY = False


@dataclass
class MathResult:
    ok: bool
    detail: str
    mode: str            # "sympy" | "fallback"
    value: Optional[str] = None


# ── Safe arithmetic evaluation ───────────────────────────────────────────────
# This module's whole job is checking arithmetic claims found in model output,
# so every string reaching the fallback evaluator is untrusted by construction.
#
# The previous implementation used eval() with {"__builtins__": {}}. That is the
# textbook "safe eval" and it is not safe: attribute access is still permitted,
# so an expression can walk from a literal to any loaded class and back out to
# the interpreter. Demonstrated against this exact code, not argued in the
# abstract -- the following returned a real directory listing:
#
#   [c for c in ().__class__.__mro__[1].__subclasses__()
#    if c.__name__=='BuiltinImporter'][0].load_module('os').listdir('.')
#
# The fix is an allowlist over the parsed AST rather than more blacklisting.
# Node kinds that are not arithmetic simply do not execute, so there is no
# escape chain to enumerate and no blacklist to keep up to date. Notably
# ast.Attribute is absent, which removes the `.__class__` step every published
# escape of this shape depends on.

_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

_SAFE_FUNCS = {
    name: getattr(math, name) for name in
    ("sqrt", "sin", "cos", "tan", "log", "log2", "log10", "exp",
     "floor", "ceil", "fabs", "atan", "asin", "acos", "degrees", "radians")
}
_SAFE_FUNCS.update({"abs": abs, "round": round, "min": min, "max": max})
_SAFE_NAMES = {"pi": math.pi, "e": math.e, "tau": math.tau}

# ** grows fast enough that a short string can hang the process; a validator
# that can be stalled by the text it validates is a denial-of-service surface.
_MAX_EXPONENT = 1000


class UnsafeExpression(ValueError):
    """The expression contains something the arithmetic allowlist forbids."""


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise UnsafeExpression(f"non-numeric constant: {node.value!r}")
        return node.value

    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise UnsafeExpression(f"operator not allowed: {type(node.op).__name__}")
        left, right = _eval_node(node.left), _eval_node(node.right)
        if op is operator.pow and abs(right) > _MAX_EXPONENT:
            raise UnsafeExpression(f"exponent too large: {right}")
        return op(left, right)

    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise UnsafeExpression(f"unary operator not allowed: {type(node.op).__name__}")
        return op(_eval_node(node.operand))

    if isinstance(node, ast.Name):
        if node.id not in _SAFE_NAMES:
            raise UnsafeExpression(f"name not allowed: {node.id}")
        return _SAFE_NAMES[node.id]

    if isinstance(node, ast.Call):
        # Only a bare allowlisted name may be called. A non-Name callee means
        # something like obj.method(), which is the attribute step this
        # allowlist exists to refuse.
        if not isinstance(node.func, ast.Name):
            raise UnsafeExpression("only direct calls to allowed functions")
        if node.func.id not in _SAFE_FUNCS:
            raise UnsafeExpression(f"function not allowed: {node.func.id}")
        if node.keywords:
            raise UnsafeExpression("keyword arguments not allowed")
        return _SAFE_FUNCS[node.func.id](*[_eval_node(a) for a in node.args])

    raise UnsafeExpression(f"syntax not allowed: {type(node).__name__}")


def safe_eval_arithmetic(expr: str) -> float:
    """Evaluate a pure-arithmetic expression, refusing anything else.

    Raises UnsafeExpression for any construct outside the allowlist, so callers
    get a clear refusal rather than a silent partial evaluation.
    """
    if len(expr) > 500:
        raise UnsafeExpression("expression too long")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpression(f"could not parse: {exc}") from exc
    return _eval_node(tree)


class MathValidator:
    def __init__(self) -> None:
        self.mode = "sympy" if _HAVE_SYMPY else "fallback"

    def check_equality(self, lhs: str, rhs: str) -> MathResult:
        """Check whether two expressions are mathematically equal."""
        if _HAVE_SYMPY:
            try:
                diff = sympy.simplify(sympy.sympify(lhs) - sympy.sympify(rhs))
                equal = (diff == 0)
                return MathResult(equal,
                                  f"{lhs} {'==' if equal else '!='} {rhs}",
                                  "sympy", str(diff))
            except Exception as e:
                return MathResult(False, f"could not parse: {e}", "sympy")
        # Fallback: arithmetic-only evaluation over an AST allowlist
        try:
            l = safe_eval_arithmetic(lhs)
            r = safe_eval_arithmetic(rhs)
            equal = abs(l - r) < 1e-9
            return MathResult(equal, f"{l} {'==' if equal else '!='} {r}", "fallback")
        except Exception as e:
            return MathResult(False, f"could not evaluate: {e}", "fallback")

    def simplify(self, expr: str) -> MathResult:
        if _HAVE_SYMPY:
            try:
                s = sympy.simplify(sympy.sympify(expr))
                return MathResult(True, f"{expr} = {s}", "sympy", str(s))
            except Exception as e:
                return MathResult(False, f"could not simplify: {e}", "sympy")
        try:
            val = safe_eval_arithmetic(expr)
            return MathResult(True, f"{expr} = {val}", "fallback", str(val))
        except Exception as e:
            return MathResult(False, f"could not evaluate: {e}", "fallback")


    def solve_equation(self, equation: str, var: str = "x") -> MathResult:
        """Solve an equation symbolically (sympy) for the given variable."""
        if not _HAVE_SYMPY:
            return MathResult(False, "solving needs sympy (not installed)", "fallback")
        try:
            import sympy
            x = sympy.Symbol(var)
            if "=" in equation:
                lhs, rhs = equation.split("=", 1)
                expr = sympy.sympify(lhs) - sympy.sympify(rhs)
            else:
                expr = sympy.sympify(equation)
            sols = sympy.solve(expr, x)
            return MathResult(True, f"{var} in {sols}", "sympy", str(sols))
        except Exception as e:
            return MathResult(False, f"could not solve: {e}", "sympy")

    def differentiate(self, expr: str, var: str = "x") -> MathResult:
        """Symbolic derivative (sympy)."""
        if not _HAVE_SYMPY:
            return MathResult(False, "differentiation needs sympy", "fallback")
        try:
            import sympy
            x = sympy.Symbol(var)
            d = sympy.diff(sympy.sympify(expr), x)
            return MathResult(True, f"d/d{var}({expr}) = {d}", "sympy", str(d))
        except Exception as e:
            return MathResult(False, f"could not differentiate: {e}", "sympy")

    def check_logic_consistency(self, premises: list, conclusion: str) -> MathResult:
        """
        Check simple propositional consistency using sympy logic if available.
        premises/conclusion are boolean expressions over symbols, e.g.
          premises=["A >> B", "A"], conclusion="B"  (modus ponens)
        """
        if not _HAVE_SYMPY:
            return MathResult(False, "logic check needs sympy (not installed)",
                              "fallback")
        try:
            from sympy.logic.boolalg import And, Implies
            from sympy.abc import A, B, C, D  # common symbols
            ns = {"A": A, "B": B, "C": C, "D": D, "Implies": Implies}
            prem = [sympy.sympify(p, locals=ns) for p in premises]
            conc = sympy.sympify(conclusion, locals=ns)
            # premises imply conclusion iff (And(premises) >> conclusion) is a tautology
            from sympy.logic.inference import satisfiable
            test = And(*prem) & ~conc
            unsat = not satisfiable(test)
            return MathResult(unsat,
                              "conclusion follows from premises" if unsat
                              else "conclusion does NOT follow",
                              "sympy")
        except Exception as e:
            return MathResult(False, f"logic parse error: {e}", "sympy")
