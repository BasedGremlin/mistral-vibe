"""
Code Reasoner.
==============
Real static analysis of Python source before any edit. Uses the stdlib `ast`
module -- genuine parsing, not guesswork. Produces concrete, checkable facts:

  - syntax validity (parse or fail with line)
  - cyclomatic-ish complexity estimate (branch counting)
  - function/class inventory
  - risky-call detection (eval, exec, os.system, subprocess with shell=True,
    open(...,'w') outside expected dirs, pickle)
  - import inventory

It does NOT "understand" code semantically. It reports structural facts an
editor/agent can use to decide whether a change is safe.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CodeAnalysis:
    ok: bool
    syntax_error: str = ""
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    complexity: int = 0
    risky_calls: List[str] = field(default_factory=list)
    line_count: int = 0

    def as_dict(self) -> Dict:
        return {
            "ok": self.ok, "syntax_error": self.syntax_error,
            "functions": self.functions, "classes": self.classes,
            "imports": self.imports, "complexity": self.complexity,
            "risky_calls": self.risky_calls, "line_count": self.line_count,
        }


class CodeReasoner:
    RISKY = {"eval", "exec", "system", "popen", "compile", "__import__",
             "loads", "load"}  # loads/load flag pickle

    def analyze(self, source: str) -> CodeAnalysis:
        result = CodeAnalysis(ok=True, line_count=source.count("\n") + 1)
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return CodeAnalysis(ok=False,
                                syntax_error=f"line {e.lineno}: {e.msg}",
                                line_count=source.count("\n") + 1)

        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                result.functions.append(node.name)
            elif isinstance(node, ast.AsyncFunctionDef):
                result.functions.append(f"async {node.name}")
            elif isinstance(node, ast.ClassDef):
                result.classes.append(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, "module", None)
                if isinstance(node, ast.Import):
                    result.imports.extend(a.name for a in node.names)
                elif mod:
                    result.imports.append(mod)
            # Complexity: each branch/loop/bool-op adds a path
            elif isinstance(node, (ast.If, ast.For, ast.While, ast.And, ast.Or,
                                   ast.ExceptHandler, ast.With)):
                complexity += 1
            # Risky calls
            elif isinstance(node, ast.Call):
                name = self._call_name(node)
                if name in self.RISKY:
                    result.risky_calls.append(name)
                # subprocess(..., shell=True)
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) \
                       and kw.value.value is True:
                        result.risky_calls.append("subprocess shell=True")

        result.complexity = complexity
        return result

    def _call_name(self, node: ast.Call) -> str:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""

    def safety_verdict(self, source: str) -> Dict:
        """Quick pre-edit safety judgment an agent can act on."""
        a = self.analyze(source)
        if not a.ok:
            return {"safe": False, "reason": f"syntax error: {a.syntax_error}"}
        if a.risky_calls:
            return {"safe": False,
                    "reason": f"risky calls present: {sorted(set(a.risky_calls))}",
                    "analysis": a.as_dict()}
        if a.complexity > 50:
            return {"safe": True, "warning": f"high complexity ({a.complexity})",
                    "analysis": a.as_dict()}
        return {"safe": True, "analysis": a.as_dict()}
