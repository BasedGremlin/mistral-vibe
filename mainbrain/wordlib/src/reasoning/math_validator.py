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
        # Fallback: numeric eval in a locked-down namespace
        try:
            safe = {"__builtins__": {}}
            import math as _m
            safe.update({k: getattr(_m, k) for k in
                         ("sqrt", "sin", "cos", "tan", "pi", "e", "log", "exp")})
            l = eval(lhs, safe, {})
            r = eval(rhs, safe, {})
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
            safe = {"__builtins__": {}}
            val = eval(expr, safe, {})
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
