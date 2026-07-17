"""
WORDLIB Code Structure Hook v1
==============================
Read-only AST bridge from the local codebase to SemanticAdapter/NEXUS.

This module uses only the Python standard library. It does not write files,
start RAG, start agents, import SemanticKnowledgeGraph internals, or require
vector/graph databases. It exposes modules/classes/functions/imports/call sites
as structured context that can be consumed like memory/RAG semantic context.
"""
from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_SRC_DIR = Path(__file__).resolve().parent
_ROOT = _SRC_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

_CODE_HOOK_VERSION = "wordlib.code_structure_hook.v1"
_DEFAULT_SCAN_DIRS = ("src", "core", "editor", "app")
_EXCLUDED_PARTS = {"__pycache__", ".git", ".venv", "venv", "backups", "node_modules", ".pytest_cache"}
_STOP_TERMS = {"the", "and", "for", "with", "from", "this", "that", "into", "code", "hook", "query"}


def _project_root(root: Optional[str] = None) -> Path:
    base = Path(root) if root else _ROOT
    if not base.is_absolute():
        base = (_ROOT / base).resolve()
    return base.resolve()


def _is_project_local(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _query_terms(query: str) -> List[str]:
    terms: List[str] = []
    for raw in str(query or "").replace("_", " ").replace("-", " ").replace("/", " ").split():
        cleaned = "".join(ch for ch in raw.lower() if ch.isalnum())
        if len(cleaned) >= 3 and cleaned not in _STOP_TERMS:
            terms.append(cleaned)
    return sorted(set(terms))


def _matches_query(value: Any, terms: List[str]) -> bool:
    if not terms:
        return False
    text = json.dumps(value, sort_keys=True, default=str).lower()
    return any(term in text for term in terms)


def _safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _annotation(node: Optional[ast.AST]) -> Optional[str]:
    if node is None:
        return None
    text = _safe_unparse(node).strip()
    return text or None


def _signature(node: ast.AST) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ""
    args = node.args
    parts: List[str] = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(positional, defaults):
        item = arg.arg
        ann = _annotation(arg.annotation)
        if ann:
            item += f": {ann}"
        if default is not None:
            item += f"={_safe_unparse(default)}"
        parts.append(item)
    if args.vararg:
        item = "*" + args.vararg.arg
        ann = _annotation(args.vararg.annotation)
        if ann:
            item += f": {ann}"
        parts.append(item)
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        item = arg.arg
        ann = _annotation(arg.annotation)
        if ann:
            item += f": {ann}"
        if default is not None:
            item += f"={_safe_unparse(default)}"
        parts.append(item)
    if args.kwarg:
        item = "**" + args.kwarg.arg
        ann = _annotation(args.kwarg.annotation)
        if ann:
            item += f": {ann}"
        parts.append(item)
    ret = _annotation(node.returns)
    suffix = f" -> {ret}" if ret else ""
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}{node.name}({', '.join(parts)}){suffix}"


def _call_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return None


@dataclass
class CodeStructureHook:
    """Read-only AST scanner for WORDLIB code structure."""

    root: Optional[str] = None
    max_files: int = 160
    max_items: int = 12
    include_tests: bool = True
    scan_dirs: Tuple[str, ...] = field(default_factory=lambda: _DEFAULT_SCAN_DIRS)

    def _root_path(self) -> Path:
        return _project_root(self.root)

    def _iter_python_files(self) -> List[Path]:
        root = self._root_path()
        candidates: List[Path] = []
        for scan_dir in self.scan_dirs:
            start = root / scan_dir
            if not start.exists():
                continue
            for path in start.rglob("*.py"):
                parts = set(path.parts)
                if parts & _EXCLUDED_PARTS:
                    continue
                candidates.append(path)
        # Include root-level entry points explicitly.
        for name in ("main.py", "launcher.py", "start_here.py", "deploy_check.py"):
            p = root / name
            if p.exists():
                candidates.append(p)
        if self.include_tests:
            tests = root / "tests"
            if tests.exists():
                for path in tests.rglob("*.py"):
                    parts = set(path.parts)
                    if not (parts & _EXCLUDED_PARTS):
                        candidates.append(path)
        unique = sorted({p.resolve(): p for p in candidates}.values(), key=lambda p: _rel(p, root))
        return unique[: max(1, int(self.max_files))]

    def _parse_file(self, path: Path, root: Path) -> Dict[str, Any]:
        rel_path = _rel(path, root)
        module_name = rel_path[:-3].replace("/", ".") if rel_path.endswith(".py") else rel_path.replace("/", ".")
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text, filename=rel_path)
        module_doc = ast.get_docstring(tree) or ""
        imports: List[Dict[str, Any]] = []
        classes: List[Dict[str, Any]] = []
        functions: List[Dict[str, Any]] = []
        call_sites: List[Dict[str, Any]] = []

        parent_class_by_function_id: Dict[int, str] = {}
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            for child in cls.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    parent_class_by_function_id[id(child)] = cls.name

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({"module": alias.name, "alias": alias.asname, "line": getattr(node, "lineno", None)})
            elif isinstance(node, ast.ImportFrom):
                names = [a.name for a in node.names]
                imports.append({"module": node.module or "", "names": names, "level": node.level, "line": getattr(node, "lineno", None)})
            elif isinstance(node, ast.ClassDef):
                classes.append({
                    "name": node.name,
                    "qualified_name": f"{module_name}.{node.name}",
                    "line": getattr(node, "lineno", None),
                    "bases": [_safe_unparse(base) for base in node.bases],
                    "docstring": (ast.get_docstring(node) or "")[:500],
                    "methods": [child.name for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))],
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parent_class = parent_class_by_function_id.get(id(node))
                functions.append({
                    "name": node.name,
                    "qualified_name": f"{module_name}.{parent_class + '.' if parent_class else ''}{node.name}",
                    "line": getattr(node, "lineno", None),
                    "parent_class": parent_class,
                    "async": isinstance(node, ast.AsyncFunctionDef),
                    "signature": _signature(node),
                    "docstring": (ast.get_docstring(node) or "")[:500],
                })
            elif isinstance(node, ast.Call):
                name = _call_name(node.func)
                if name:
                    call_sites.append({"call": name, "line": getattr(node, "lineno", None)})

        # Deduplicate and cap call sites to avoid huge prompt payloads.
        seen_calls = set()
        capped_calls: List[Dict[str, Any]] = []
        for call in call_sites:
            key = (call.get("call"), call.get("line"))
            if key not in seen_calls:
                seen_calls.add(key)
                capped_calls.append(call)
            if len(capped_calls) >= 80:
                break

        return {
            "module": module_name,
            "path": rel_path,
            "docstring": module_doc[:500],
            "imports": imports,
            "classes": classes,
            "functions": functions,
            "call_sites": capped_calls,
            "counts": {
                "imports": len(imports),
                "classes": len(classes),
                "functions": len(functions),
                "call_sites_sampled": len(capped_calls),
            },
        }

    def scan(self) -> Dict[str, Any]:
        root = self._root_path()
        warnings: List[str] = []
        if not _is_project_local(root, _ROOT):
            warnings.append("code root is outside WORDLIB project root; read-only scan only")
        modules: List[Dict[str, Any]] = []
        parse_errors: List[Dict[str, Any]] = []
        files = self._iter_python_files()
        for path in files:
            try:
                modules.append(self._parse_file(path, root))
            except SyntaxError as exc:
                parse_errors.append({"path": _rel(path, root), "error": f"SyntaxError: {exc}"})
            except Exception as exc:
                parse_errors.append({"path": _rel(path, root), "error": f"{type(exc).__name__}: {exc}"})
        summary = {
            "modules": len(modules),
            "files_seen": len(files),
            "parse_errors": len(parse_errors),
            "classes": sum(m["counts"]["classes"] for m in modules),
            "functions": sum(m["counts"]["functions"] for m in modules),
            "imports": sum(m["counts"]["imports"] for m in modules),
            "call_sites_sampled": sum(m["counts"]["call_sites_sampled"] for m in modules),
        }
        return {
            "contract": _CODE_HOOK_VERSION,
            "read_only": True,
            "root": str(root),
            "project_local_root": _is_project_local(root, _ROOT),
            "scan_dirs": list(self.scan_dirs),
            "summary": summary,
            "modules": modules,
            "parse_errors": parse_errors,
            "warnings": warnings,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def context_for_query(self, query: str, as_prompt: bool = False) -> Dict[str, Any]:
        scan = self.scan()
        terms = _query_terms(query)
        modules = scan.get("modules", [])
        matched_modules = [m for m in modules if _matches_query(m, terms)] if terms else []
        matched_functions: List[Dict[str, Any]] = []
        matched_classes: List[Dict[str, Any]] = []
        matched_imports: List[Dict[str, Any]] = []
        matched_calls: List[Dict[str, Any]] = []
        for module in modules:
            for cls in module.get("classes", []):
                row = {**cls, "module": module.get("module"), "path": module.get("path")}
                if _matches_query(row, terms):
                    matched_classes.append(row)
            for fn in module.get("functions", []):
                row = {**fn, "module": module.get("module"), "path": module.get("path")}
                if _matches_query(row, terms):
                    matched_functions.append(row)
            for imp in module.get("imports", []):
                row = {**imp, "module_owner": module.get("module"), "path": module.get("path")}
                if _matches_query(row, terms):
                    matched_imports.append(row)
            for call in module.get("call_sites", []):
                row = {**call, "module": module.get("module"), "path": module.get("path")}
                if _matches_query(row, terms):
                    matched_calls.append(row)
        limit = max(1, int(self.max_items))
        data: Dict[str, Any] = {
            "contract": _CODE_HOOK_VERSION,
            "read_only": True,
            "query": query,
            "summary": scan.get("summary", {}),
            "sources": {"root": scan.get("root"), "scan_dirs": scan.get("scan_dirs", []), "project_local_root": scan.get("project_local_root")},
            "matches": {
                "modules": matched_modules[:limit],
                "classes": matched_classes[:limit],
                "functions": matched_functions[:limit],
                "imports": matched_imports[:limit],
                "call_sites": matched_calls[:limit],
            },
            "warnings": list(scan.get("warnings", [])),
            "parse_errors": scan.get("parse_errors", [])[:limit],
            "generated_at": scan.get("generated_at"),
        }
        if scan.get("parse_errors"):
            data["warnings"].append(f"{len(scan['parse_errors'])} Python file(s) could not be parsed")
        if not any(data["matches"].values()):
            data["warnings"].append("no code-structure matches for query")
        if as_prompt:
            lines = [
                "WORDLIB code structure context (read-only AST):",
                f"- Modules scanned: {scan['summary'].get('modules', 0)}; classes={scan['summary'].get('classes', 0)}; functions={scan['summary'].get('functions', 0)}; imports={scan['summary'].get('imports', 0)}.",
                f"- Query matches: modules={len(matched_modules)}, classes={len(matched_classes)}, functions={len(matched_functions)}, imports={len(matched_imports)}, calls={len(matched_calls)}.",
            ]
            for module in matched_modules[:3]:
                lines.append(f"- Module: {module.get('path')} classes={module.get('counts', {}).get('classes', 0)} functions={module.get('counts', {}).get('functions', 0)}")
            for cls in matched_classes[:4]:
                lines.append(f"- Class: {cls.get('qualified_name')} bases={cls.get('bases', [])} methods={cls.get('methods', [])[:6]}")
            for fn in matched_functions[:5]:
                doc = (fn.get("docstring") or "").replace("\n", " ")[:160]
                lines.append(f"- Function: {fn.get('qualified_name')} signature={fn.get('signature')} doc={doc}")
            for call in matched_calls[:5]:
                lines.append(f"- Call site: {call.get('module')}:{call.get('line')} calls {call.get('call')}")
            if data["warnings"]:
                lines.append(f"- Warnings: {'; '.join(data['warnings'][:3])}")
            data["prompt_context"] = "\n".join(lines)
        return data


def semantic_context_for_code_query(query_text: str, as_prompt: bool = True,
                                    root: Optional[str] = None,
                                    storage_path: Optional[str] = None,
                                    max_files: int = 160,
                                    max_items: int = 12) -> Dict[str, Any]:
    """
    Optional read-only code-structure hook for prompt building and diagnostics.

    This function routes through SemanticAdapter when available so the adapter
    remains the central NEXUS-facing interface. It never writes graph/memory/code.
    """
    try:
        from semantic_adapter import create_default_adapter
        adapter = create_default_adapter(auto_load=True, auto_save=False, storage_path=storage_path)
        result = adapter.code_structure_context_for_query(
            query=query_text,
            as_prompt=as_prompt,
            root=root,
            max_files=max_files,
            max_items=max_items,
        )
        data = result.to_dict()
        data["hook"] = "code_structure_hook.semantic_context_for_code_query"
        data["read_only"] = True
        return data
    except Exception as exc:
        return {
            "ok": False,
            "operation": "semantic_context_for_code_query",
            "data": {},
            "warnings": [],
            "error": f"{type(exc).__name__}: {exc}",
            "hook": "code_structure_hook.semantic_context_for_code_query",
            "read_only": True,
        }


def code_structure_status(root: Optional[str] = None) -> Dict[str, Any]:
    """Boot/deploy-safe status helper for the read-only AST hook."""
    result = semantic_context_for_code_query("SemanticAdapter code_structure_hook ast", as_prompt=False, root=root, max_items=5)
    data = result.get("data", {})
    return {
        "ok": bool(result.get("ok")),
        "hook": "code_structure_hook.code_structure_status",
        "read_only": True,
        "root": data.get("sources", {}).get("root"),
        "summary": data.get("summary", {}),
        "error": result.get("error"),
        "warnings": result.get("warnings", []) + data.get("warnings", []),
    }


def self_check() -> bool:
    result = semantic_context_for_code_query("SemanticAdapter code_structure_hook CodeStructureHook", as_prompt=True, max_items=5)
    assert result.get("read_only") is True, result
    assert result.get("ok") is True, result
    data = result.get("data", {})
    assert data.get("summary", {}).get("modules", 0) > 0, data
    prompt = data.get("prompt_context", "")
    assert "WORDLIB code structure context" in prompt, prompt
    assert "SemanticAdapter" in prompt or "code_structure_hook" in prompt, prompt
    status = code_structure_status()
    assert status.get("ok") is True, status
    assert status.get("summary", {}).get("functions", 0) > 0, status
    return True


if __name__ == "__main__":
    ok = self_check()
    print(json.dumps({"code_structure_hook_self_check": ok, "status": code_structure_status()}, indent=2, sort_keys=True))
