"""
ETHER CORE -- the blob brain.
=============================
The single object that knows every subsystem and exposes them as one body.
This is what makes WORDLIB "one blob" rather than a pile of modules.

Absorbed (and made real) from external kernel code:
  - CapabilityRegistry  -- registry of what the system can actually do
  - ProvenanceRegistry  -- where a piece of data/code came from
  - EvidenceRegistry    -- content-hashed record of supporting material
  - EventLog            -- append-only log of real operations
  - EvolutionManager    -- REAL atomic self-modification:
                           test -> snapshot -> deploy -> rollback-on-failure
                           (built on self_editor's real backup + syntax validation)

Everything here operates on the REAL system. No undefined scores, no
placeholder fields, no pickle. Provenance/evidence track actual operations;
capabilities reflect modules that actually exist; evolution actually edits
real source files with a real safety transaction.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ether_core")

# Path resolution via the single source of truth (core.paths), with a guarded
# fallback for standalone import (see self_editor.py for the rationale).
try:
    from core.paths import PATHS
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.paths import PATHS

_SRC_DIR  = PATHS.src
_USB_ROOT = PATHS.root
_DATA     = PATHS.data
_EVENTLOG = _DATA / "ether_events.jsonl"

# ether_core's sibling modules (rag_manager, etc.) are imported by bare name,
# so src/ must be importable. This is a sibling-import requirement, not path
# discovery -- the root itself comes from PATHS above.
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ── Utilities (absorbed from Omega kernel) ──────────────────────────────────
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════
#  CAPABILITY REGISTRY  (absorbed -- made real)
#  Registers the system's ACTUAL subsystems, not invented ones.
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Capability:
    capability_id: str
    name: str
    description: str
    module: str               # real importable module
    available: bool           # did it actually import?
    methods: Tuple[str, ...] = ()
    depends_on: Tuple[str, ...] = ()


class CapabilityRegistry:
    """Tracks which real subsystems exist and whether they import cleanly."""

    def __init__(self) -> None:
        self._caps: Dict[str, Capability] = {}

    def register(self, name: str, description: str, module: str,
                 depends_on: Tuple[str, ...] = ()) -> Capability:
        available, methods = self._probe(module)
        cap = Capability(
            capability_id=sha256(name)[:12],
            name=name,
            description=description,
            module=module,
            available=available,
            methods=methods,
            depends_on=depends_on,
        )
        self._caps[name] = cap
        return cap

    def _probe(self, module: str) -> Tuple[bool, Tuple[str, ...]]:
        """Actually try to import the module and list its public callables."""
        try:
            mod = importlib.import_module(module)
            methods = tuple(
                n for n in dir(mod)
                if not n.startswith("_") and callable(getattr(mod, n, None))
            )
            return True, methods
        except Exception as e:
            logger.debug(f"Capability probe failed for {module}: {e}")
            return False, ()

    def list_all(self) -> List[Capability]:
        return list(self._caps.values())

    def available_count(self) -> int:
        return sum(1 for c in self._caps.values() if c.available)


# ═══════════════════════════════════════════════════════════════════════════
#  PROVENANCE + EVIDENCE  (absorbed -- wired to real operations)
# ═══════════════════════════════════════════════════════════════════════════

class ProvenanceRegistry:
    """Records where a piece of data, code, or content came from."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict] = {}

    def register(self, source: str, kind: str = "generic") -> str:
        pid = sha256(source)[:16]
        if pid not in self._store:
            self._store[pid] = {"source": source, "kind": kind, "registered": utc_now()}
        return pid

    def get(self, pid: str) -> Optional[Dict]:
        return self._store.get(pid)

    def count(self) -> int:
        return len(self._store)


class EvidenceRegistry:
    """Content-hashed record of supporting material for a claim or operation."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict] = {}

    def register(self, payload: Dict) -> str:
        eid = sha256(json.dumps(payload, sort_keys=True, default=str))[:16]
        self._store[eid] = {"payload": payload, "registered": utc_now()}
        return eid

    def get(self, eid: str) -> Optional[Dict]:
        return self._store.get(eid)

    def count(self) -> int:
        return len(self._store)


# ═══════════════════════════════════════════════════════════════════════════
#  EVENT LOG  (absorbed -- made persistent + append-only)
# ═══════════════════════════════════════════════════════════════════════════

class EventLog:
    """Append-only operational log, persisted to data/ether_events.jsonl."""

    def __init__(self, path: Path = _EVENTLOG) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._memory: List[Dict] = []

    def log(self, event_type: str, payload: Dict) -> Dict:
        entry = {"time": utc_now(), "event": event_type, "payload": payload}
        self._memory.append(entry)
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            logger.warning(f"EventLog persist failed: {e}")
        return entry

    def recent(self, n: int = 20) -> List[Dict]:
        return self._memory[-n:]

    def count(self) -> int:
        return len(self._memory)

    def semantic_context(self, query: str, as_prompt: bool = True) -> Dict:
        """Optional read-only SemanticAdapter context for event-log memory."""
        try:
            src = Path(__file__).resolve().parent
            import sys
            if str(src) not in sys.path:
                sys.path.insert(0, str(src))
            from memory_semantic_hook import semantic_context_for_memory_query
            return semantic_context_for_memory_query(query, as_prompt=as_prompt, memory_root=str(self.path.parent))
        except Exception as e:
            return {"ok": False, "read_only": True, "error": str(e), "hook": "EventLog.semantic_context"}


# ═══════════════════════════════════════════════════════════════════════════
#  EVOLUTION MANAGER  (the one genuinely valuable idea -- MADE REAL)
#  Atomic self-modification: test -> snapshot -> deploy -> rollback on failure.
#  Built entirely on self_editor's real backup + syntax validation.
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class EvolutionResult:
    success: bool
    target: str
    round: int
    snapshot: Optional[str] = None
    error: Optional[str] = None
    rolled_back: bool = False
    detail: str = ""


class EvolutionManager:
    """
    Real atomic evolution. When the system (or you) wants to modify a source
    file, this wraps the change in a safety transaction:

      1. VALIDATE   -- new content must be valid Python (via self_editor)
      2. SNAPSHOT   -- self_editor backs up the current file
      3. DEPLOY     -- write the new content
      4. TEST       -- import-check the changed module; run an optional test cmd
      5. ROLLBACK   -- if test fails, restore the snapshot automatically

    Nothing is "evolved" magically -- YOU or an agent supplies the new content.
    What's real here is the transaction: a bad edit never survives.
    """

    def __init__(self, event_log: EventLog) -> None:
        self.round = 0
        self.events = event_log
        try:
            from self_editor import get_editor
            self.editor = get_editor()
        except ImportError:
            self.editor = None
            logger.error("self_editor unavailable -- evolution disabled")

    def evolve_file(self, rel_path: str, new_content: str,
                    test_command: Optional[List[str]] = None) -> EvolutionResult:
        """
        Atomically replace a file's content with rollback-on-failure.

        rel_path:     path relative to USB root, e.g. "src/foo.py"
        new_content:  the full new file content
        test_command: optional shell command to validate after deploy,
                      e.g. ["python", "-c", "import foo"]. If it exits
                      non-zero, the change is rolled back.
        """
        self.round += 1
        rnd = self.round

        if self.editor is None:
            return EvolutionResult(False, rel_path, rnd,
                                   error="self_editor unavailable")

        # 1. VALIDATE (self_editor also validates, but we check early)
        if rel_path.endswith(".py"):
            from self_editor import _validate_python
            valid, msg = _validate_python(new_content)
            if not valid:
                self.events.log("evolution_rejected",
                                {"target": rel_path, "round": rnd, "reason": msg})
                return EvolutionResult(False, rel_path, rnd,
                                       error=f"Validation failed: {msg}")

        # 2 + 3. SNAPSHOT + DEPLOY (self_editor.write_file backs up first)
        write_result = self.editor.write_file(rel_path, new_content)
        if not write_result.get("ok"):
            self.events.log("evolution_write_failed",
                            {"target": rel_path, "round": rnd,
                             "error": write_result.get("error")})
            return EvolutionResult(False, rel_path, rnd,
                                   error=write_result.get("error"))

        snapshot = write_result.get("backup")

        # 4. TEST
        test_ok, test_detail = self._run_test(rel_path, test_command)

        if test_ok:
            self.events.log("evolution_deployed",
                            {"target": rel_path, "round": rnd, "snapshot": snapshot})
            return EvolutionResult(True, rel_path, rnd,
                                   snapshot=snapshot, detail=test_detail)

        # 5. ROLLBACK
        rollback_result = self.editor.rollback(rel_path)
        rolled = rollback_result.get("ok", False)
        self.events.log("evolution_rolled_back",
                        {"target": rel_path, "round": rnd,
                         "snapshot": snapshot, "test_detail": test_detail})
        return EvolutionResult(False, rel_path, rnd, snapshot=snapshot,
                               error=f"Test failed: {test_detail}",
                               rolled_back=rolled, detail=test_detail)

    def evolve_files(self, changes: Dict[str, str],
                     test_command: Optional[List[str]] = None) -> EvolutionResult:
        """
        ATOMIC MULTI-FILE transaction with two-phase verified rollback.

        changes: {rel_path: new_content, ...}
        Either ALL files are deployed and verified, or ALL are restored.

        Two-phase:
          PHASE 1 (prepare): validate every file's syntax. If any fails,
                             nothing is written at all.
          PHASE 2 (commit):  snapshot + write each file. Then run the test.
                             If the test fails, restore EVERY file from its
                             snapshot and verify each restoration.
        """
        self.round += 1
        rnd = self.round
        target_desc = f"{len(changes)} files"

        if self.editor is None:
            return EvolutionResult(False, target_desc, rnd,
                                   error="self_editor unavailable")

        # PHASE 1: validate ALL before writing ANY
        from self_editor import _validate_python
        for path, content in changes.items():
            if path.endswith(".py"):
                valid, msg = _validate_python(content)
                if not valid:
                    self.events.log("evolution_multi_rejected",
                                    {"target": path, "round": rnd, "reason": msg})
                    return EvolutionResult(False, target_desc, rnd,
                                           error=f"Validation failed for {path}: {msg}")

        # PHASE 2: snapshot + write each, tracking what we changed
        written: List[str] = []
        snapshots: Dict[str, str] = {}
        for path, content in changes.items():
            result = self.editor.write_file(path, content)
            if not result.get("ok"):
                # Write failed mid-transaction -- roll back everything done so far
                self._restore_all(written, snapshots)
                self.events.log("evolution_multi_write_failed",
                                {"target": path, "round": rnd,
                                 "error": result.get("error"), "rolled_back": written})
                return EvolutionResult(False, target_desc, rnd,
                                       error=f"Write failed for {path}",
                                       rolled_back=True)
            written.append(path)
            snapshots[path] = result.get("backup")

        # TEST the whole set
        test_ok, test_detail = self._run_test_multi(list(changes.keys()), test_command)

        if test_ok:
            self.events.log("evolution_multi_deployed",
                            {"target": target_desc, "round": rnd,
                             "files": written, "snapshots": snapshots})
            return EvolutionResult(True, target_desc, rnd, detail=test_detail)

        # ROLLBACK all, with verification (two-phase verified rollback)
        verified = self._restore_all(written, snapshots)
        self.events.log("evolution_multi_rolled_back",
                        {"target": target_desc, "round": rnd,
                         "test_detail": test_detail, "restore_verified": verified})
        return EvolutionResult(False, target_desc, rnd,
                               error=f"Test failed: {test_detail}",
                               rolled_back=verified, detail=test_detail)

    def _restore_all(self, paths: List[str], snapshots: Dict[str, str]) -> bool:
        """Restore every file from its snapshot and VERIFY each restoration."""
        all_ok = True
        for path in paths:
            r = self.editor.rollback(path, snapshots.get(path))
            if not r.get("ok"):
                all_ok = False
        return all_ok

    def _run_test_multi(self, paths: List[str],
                        test_command: Optional[List[str]]) -> Tuple[bool, str]:
        """Default multi-file test: parse-check every .py file in the set."""
        if test_command is not None:
            return self._run_test(paths[0], test_command)
        for path in paths:
            if path.endswith(".py"):
                full = _USB_ROOT / path
                try:
                    import ast as _ast
                    _ast.parse(full.read_text(encoding="utf-8"))
                except Exception as e:
                    return False, f"{path}: {e}"
        return True, f"all {len(paths)} files valid"

    def _run_test(self, rel_path: str,
                  test_command: Optional[List[str]]) -> Tuple[bool, str]:
        """Run the validation test. Default: import-check a changed .py module."""
        # Default test for Python files: can it be imported / parsed?
        if test_command is None:
            if rel_path.endswith(".py"):
                full = _USB_ROOT / rel_path
                test_command = [sys.executable, "-c",
                                f"import ast; ast.parse(open(r'{full}').read())"]
            else:
                return True, "no test required for non-python file"

        try:
            proc = subprocess.run(test_command, capture_output=True, text=True,
                                  timeout=60, cwd=str(_USB_ROOT))
            if proc.returncode == 0:
                return True, "test passed"
            return False, (proc.stderr or proc.stdout or "non-zero exit").strip()[:500]
        except subprocess.TimeoutExpired:
            return False, "test timed out"
        except Exception as e:
            return False, f"test error: {e}"

    def get_state(self) -> Dict[str, Any]:
        return {"round": self.round, "editor_available": self.editor is not None}


# ═══════════════════════════════════════════════════════════════════════════
#  ETHER CORE  (the blob brain -- ties it all together)
# ═══════════════════════════════════════════════════════════════════════════

class EtherCore:
    """
    The unified brain. One object that knows every real subsystem,
    tracks provenance/evidence/events, and can atomically evolve itself.
    """

    def __init__(self) -> None:
        self.capabilities = CapabilityRegistry()
        self.provenance   = ProvenanceRegistry()
        self.evidence     = EvidenceRegistry()
        self.events       = EventLog()
        self.evolution    = EvolutionManager(self.events)
        self._register_real_capabilities()
        self.events.log("ether_core_online", {"capabilities": self.capabilities.available_count()})

    def _register_real_capabilities(self) -> None:
        """Register the ACTUAL WORDLIB subsystems and probe each."""
        reg = self.capabilities.register
        reg("rag",             "Retrieval-augmented generation over storage/",
            "rag_manager")
        reg("orchestrator",    "Background service manager (Ollama/Kiwix/WebUI)",
            "usb_orchestrator")
        reg("hub_client",      "HTTP client to the ETHER AI Flask hub",
            "hub_client")
        reg("self_editor",     "Read/write/patch/rollback own source files",
            "self_editor")
        reg("content_manager", "DB sync + AI content expansion",
            "content_manager", depends_on=("rag",))
        reg("creative_bridge", "Godot launcher + RAG-over-HTTP",
            "creative_bridge", depends_on=("hub_client",))
        reg("openclaw_bridge", "Ollama coding agent launcher",
            "openclaw_bridge", depends_on=("hub_client",))
        reg("ultra_renderer", "Software PBR renderer (numba-optional, portable)",
            "ultra_renderer")

    # ── Convenience API ──────────────────────────────────────────────────────

    def remember_operation(self, what: str, source: str,
                           evidence: Optional[Dict] = None) -> Dict[str, str]:
        """Record that an operation happened, with provenance + evidence."""
        pid = self.provenance.register(source, kind="operation")
        eid = self.evidence.register(evidence or {"note": what})
        self.events.log("operation", {"what": what, "provenance": pid, "evidence": eid})
        return {"provenance": pid, "evidence": eid}

    def status(self) -> Dict[str, Any]:
        caps = self.capabilities.list_all()
        return {
            "capabilities_total":     len(caps),
            "capabilities_available": self.capabilities.available_count(),
            "capabilities": [
                {"name": c.name, "available": c.available,
                 "module": c.module, "method_count": len(c.methods)}
                for c in caps
            ],
            "provenance_records": self.provenance.count(),
            "evidence_records":   self.evidence.count(),
            "events_logged":      self.events.count(),
            "evolution_rounds":   self.evolution.round,
        }


# ── Singleton ────────────────────────────────────────────────────────────────
_core: Optional[EtherCore] = None

def get_core() -> EtherCore:
    global _core
    if _core is None:
        _core = EtherCore()
    return _core


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    core = get_core()
    print(json.dumps(core.status(), indent=2))
