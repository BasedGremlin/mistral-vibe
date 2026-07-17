"""
WORDLIB Self-Editor
===================
Allows the system to read, modify, and manage its own source files.

SAFETY RULE: Every write to a .py, .bat, .sh, .json, or .md file
creates a timestamped backup in backups/ first. Python files are
syntax-checked before overwriting -- a bad edit never bricks the USB.

Rollback is always one call away.

This module is the self-modification engine. It is called by:
  - ETHER AI Flask routes (/api/system/*)
  - launcher.py self-heal routines
  - Any component that needs to update the project's own files

Never call this from untrusted input without the path whitelist check.
"""

import ast
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("self_editor")

# Path resolution via the single source of truth (core.paths). The guarded
# fallback only runs when this module is imported standalone from a cwd where
# the project root isn't yet on sys.path (e.g. `cd src && python -c ...`); it
# locates core ONCE, after which all path semantics come from PATHS.
try:
    from core.paths import PATHS
except ModuleNotFoundError:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.paths import PATHS

_USB_ROOT = PATHS.root
_BACKUPS  = PATHS.backups / "self_editor"

# Files the self-editor is allowed to touch.
# Paths are relative to USB root. Glob patterns supported.
_WRITE_WHITELIST = [
    "launcher.py",
    "src/*.py",
    "app/main.py",
    "app/templates/*.html",
    "config/*.json",
    "storage/**/*.md",
    "storage/**/*.txt",
    "docs/*.txt",
    "docs/*.md",
    "README.md",
    "CLAUDE_BRIEFING.md",
]

# Files that are always read-only (never modified)
_READ_ONLY = [
    "backups/**",
    ".venv/**",
    ".pip_cache/**",
    "core/ollama/models/**",   # Model weights
]


def _is_allowed(path: Path) -> Tuple[bool, str]:
    """Check path against whitelist. Returns (allowed, reason)."""
    try:
        rel = path.resolve().relative_to(_USB_ROOT.resolve())
    except ValueError:
        return False, "Path is outside USB root."

    rel_str = str(rel).replace("\\", "/")

    # Check read-only first
    for pattern in _READ_ONLY:
        if rel.match(pattern):
            return False, f"Path matches read-only pattern: {pattern}"

    # Check whitelist
    for pattern in _WRITE_WHITELIST:
        if rel.match(pattern):
            return True, "ok"

    return False, f"Path not in write whitelist: {rel_str}"


def _backup(path: Path) -> Optional[Path]:
    """
    Create a timestamped backup of a file before modifying it.
    Returns the backup path, or None if the file doesn't exist yet.
    """
    if not path.exists():
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # microseconds avoid same-second collisions
    try:
        rel = path.resolve().relative_to(_USB_ROOT.resolve())
    except ValueError:
        rel = path.name

    safe_rel = str(rel).replace("/", "__").replace("\\", "__")
    backup_path = _BACKUPS / f"{safe_rel}.{ts}.bak"
    # Extra guard: if somehow the name still exists, append a counter
    counter = 0
    while backup_path.exists():
        counter += 1
        backup_path = _BACKUPS / f"{safe_rel}.{ts}_{counter}.bak"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    logger.info(f"Backup created: {backup_path.name}")
    return backup_path


def _validate_python(content: str) -> Tuple[bool, str]:
    """Syntax-check Python content. Returns (valid, error_message)."""
    try:
        ast.parse(content)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"


class SelfEditor:
    """
    Read/write/rollback engine for WORDLIB's own source files.
    All writes are backed up. Python files are syntax-validated first.
    """

    def __init__(self) -> None:
        _BACKUPS.mkdir(parents=True, exist_ok=True)

    # ── Read ────────────────────────────────────────────────────────────────

    def read_file(self, path: str) -> Dict[str, Any]:
        """
        Read any file in the project (no whitelist restriction for reads).
        Returns {"ok": True, "content": str, "path": str, "lines": int}
        """
        p = (_USB_ROOT / path).resolve()
        try:
            rel = p.relative_to(_USB_ROOT.resolve())
        except ValueError:
            return {"ok": False, "error": "Path outside USB root."}

        if not p.exists():
            return {"ok": False, "error": f"File not found: {path}"}
        if not p.is_file():
            return {"ok": False, "error": f"Not a file: {path}"}

        try:
            content = p.read_text(encoding="utf-8")
            return {
                "ok":      True,
                "content": content,
                "path":    str(rel),
                "lines":   content.count("\n") + 1,
                "size":    p.stat().st_size,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def list_files(self, subdir: str = "") -> Dict[str, Any]:
        """
        List all project files, optionally under a subdirectory.
        Returns {"ok": True, "files": [{"path", "size", "lines"}]}
        """
        base = (_USB_ROOT / subdir).resolve() if subdir else _USB_ROOT.resolve()
        if not base.exists():
            return {"ok": False, "error": f"Directory not found: {subdir}"}

        files = []
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            # Skip hidden and pycache
            parts = p.parts
            if any(part.startswith(".") or part == "__pycache__" for part in parts):
                continue
            try:
                rel = str(p.relative_to(_USB_ROOT.resolve())).replace("\\", "/")
                size = p.stat().st_size
                lines = None
                try:
                    lines = p.read_text(encoding="utf-8", errors="ignore").count("\n") + 1
                except Exception:
                    pass
                files.append({"path": rel, "size": size, "lines": lines})
            except Exception:
                continue

        return {"ok": True, "files": files, "count": len(files), "base": subdir or "."}

    # ── Write ────────────────────────────────────────────────────────────────

    def write_file(self, path: str, content: str,
                   skip_backup: bool = False) -> Dict[str, Any]:
        """
        Write content to a whitelisted file. Backs up first.
        Python files are syntax-checked before overwriting.

        Returns {"ok": True, "backup": backup_path_or_null, "path": str}
        """
        p = (_USB_ROOT / path).resolve()
        allowed, reason = _is_allowed(p)
        if not allowed:
            logger.warning(f"write_file blocked: {path} -- {reason}")
            return {"ok": False, "error": reason}

        # Syntax check Python files BEFORE backup or write
        if p.suffix == ".py":
            valid, err = _validate_python(content)
            if not valid:
                return {
                    "ok":    False,
                    "error": f"Python syntax error -- file NOT written. {err}",
                }

        # Backup existing file
        backup = None
        if not skip_backup:
            bp = _backup(p)
            backup = str(bp.relative_to(_USB_ROOT.resolve())) if bp else None

        # Write
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            logger.info(f"write_file: {path} ({len(content)} chars)")
            return {"ok": True, "path": path, "backup": backup}
        except Exception as e:
            logger.error(f"write_file failed: {path}: {e}")
            return {"ok": False, "error": str(e)}

    def patch_file(self, path: str, old: str, new: str) -> Dict[str, Any]:
        """
        Find-and-replace `old` with `new` in a file.
        Fails if `old` appears zero times or more than once (ambiguous).
        Backs up before patching.
        """
        result = self.read_file(path)
        if not result["ok"]:
            return result

        content = result["content"]
        count = content.count(old)
        if count == 0:
            return {"ok": False, "error": "Pattern not found in file."}
        if count > 1:
            return {"ok": False,
                    "error": f"Pattern appears {count} times -- ambiguous patch. Be more specific."}

        patched = content.replace(old, new, 1)
        return self.write_file(path, patched)

    def append_to_file(self, path: str, content: str) -> Dict[str, Any]:
        """Append content to a whitelisted file."""
        result = self.read_file(path)
        if not result["ok"]:
            # File doesn't exist -- create it
            return self.write_file(path, content)
        existing = result["content"]
        return self.write_file(path, existing + "\n" + content)

    def delete_file(self, path: str) -> Dict[str, Any]:
        """
        Delete a whitelisted file (backs up first so it's recoverable).
        """
        p = (_USB_ROOT / path).resolve()
        allowed, reason = _is_allowed(p)
        if not allowed:
            return {"ok": False, "error": reason}
        if not p.exists():
            return {"ok": False, "error": "File does not exist."}

        bp = _backup(p)
        backup = str(bp.relative_to(_USB_ROOT.resolve())) if bp else None
        try:
            p.unlink()
            logger.info(f"delete_file: {path} (backup: {backup})")
            return {"ok": True, "path": path, "backup": backup}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Rollback ─────────────────────────────────────────────────────────────

    def list_backups(self, path: Optional[str] = None) -> Dict[str, Any]:
        """List available backups, optionally filtered to a specific file."""
        backups = []
        for bp in sorted(_BACKUPS.glob("*.bak"), reverse=True):
            backups.append({
                "backup_file": bp.name,
                "created":     datetime.fromtimestamp(bp.stat().st_mtime).isoformat(),
                "size":        bp.stat().st_size,
            })

        if path:
            safe = path.replace("/", "__").replace("\\", "__")
            backups = [b for b in backups if b["backup_file"].startswith(safe)]

        return {"ok": True, "backups": backups, "count": len(backups)}

    def rollback(self, path: str, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Restore a file from its most recent backup (or a named backup).
        The current file is itself backed up before rollback.
        """
        p = (_USB_ROOT / path).resolve()
        allowed, reason = _is_allowed(p)
        if not allowed:
            return {"ok": False, "error": reason}

        # Find the backup to restore FROM -- captured BEFORE we make any new
        # backup, so the pre-rollback safety copy can never be chosen as the
        # restore source (which would make rollback a silent no-op).
        if backup_name:
            bp = _BACKUPS / backup_name
        else:
            safe = path.replace("/", "__").replace("\\", "__")
            candidates = sorted(_BACKUPS.glob(f"{safe}.*.bak"), reverse=True)
            if not candidates:
                return {"ok": False, "error": f"No backups found for: {path}"}
            bp = candidates[0]

        if not bp.exists():
            return {"ok": False, "error": f"Backup not found: {bp.name}"}

        # Read the restore content NOW, before making the safety backup, so a
        # same-timestamp collision cannot swap what we restore.
        try:
            restore_content = bp.read_bytes()
        except Exception as e:
            return {"ok": False, "error": f"Could not read backup: {e}"}

        # Backup the current file before rolling back (safety net for redo)
        _backup(p)

        try:
            p.write_bytes(restore_content)
            logger.info(f"rollback: {path} from {bp.name}")
            return {"ok": True, "path": path, "restored_from": bp.name}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Convenience ──────────────────────────────────────────────────────────

    def get_system_summary(self) -> Dict[str, Any]:
        """Return a summary of the project's own source files for the AI."""
        files_result = self.list_files()
        backups_result = self.list_backups()
        py_files = [f for f in files_result.get("files", [])
                    if f["path"].endswith(".py")]
        return {
            "usb_root":       str(_USB_ROOT),
            "total_files":    files_result.get("count", 0),
            "python_files":   len(py_files),
            "total_backups":  backups_result.get("count", 0),
            "write_whitelist": _WRITE_WHITELIST,
            "python_modules": [f["path"] for f in py_files],
        }


# ── Singleton ────────────────────────────────────────────────────────────────
_editor: Optional[SelfEditor] = None

def get_editor() -> SelfEditor:
    global _editor
    if _editor is None:
        _editor = SelfEditor()
    return _editor


if __name__ == "__main__":
    import json as _json
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    ed = SelfEditor()
    arg = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if arg == "summary":
        print(_json.dumps(ed.get_system_summary(), indent=2))
    elif arg == "files":
        print(_json.dumps(ed.list_files(sys.argv[2] if len(sys.argv) > 2 else ""), indent=2))
    elif arg == "backups":
        print(_json.dumps(ed.list_backups(), indent=2))
    elif arg == "read" and len(sys.argv) > 2:
        r = ed.read_file(sys.argv[2])
        if r["ok"]:
            print(r["content"])
        else:
            print(f"Error: {r['error']}")
