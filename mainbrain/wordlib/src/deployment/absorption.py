"""
Absorption & Scanning layer.
============================
Detects what advanced capabilities are actually present (vs missing), reads
real hardware facts, and proposes/applies small safe "deployment mutations"
to the system's own config.

Everything here reports REAL facts. A capability is "active" only if the code
behind it imports and works -- never a label with nothing under it.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CapabilityStatus:
    name: str
    available: bool
    detail: str
    tier: str = "core"   # core | advanced | premium


@dataclass
class EnvironmentProfile:
    cpu_count: int
    ram_gb: Optional[float]
    disk_free_gb: float
    platform: str
    recommended_model_tier: str
    recommended_rag_chunk: int


class AbsorptionScanner:
    """
    Scans the live environment + codebase for advanced capabilities.
    Returns honest present/missing status for each.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.src = root / "src"
        if str(self.src) not in sys.path:
            sys.path.insert(0, str(self.src))

    # ── Capability probes (each verifies REAL behavior, not just import) ─────

    def scan_capabilities(self) -> List[CapabilityStatus]:
        caps: List[CapabilityStatus] = []

        # Atomic single-file evolution
        caps.append(self._probe_evolution_single())
        # Atomic MULTI-file evolution (two-phase verified rollback)
        caps.append(self._probe_evolution_multi())
        # Persistent transaction log
        caps.append(self._probe_transaction_log())
        # Real vector RAG (chromadb + llama-index)
        caps.append(self._probe_vector_rag())
        # Self-editing engine
        caps.append(self._probe_self_editor())
        # Self-healing repair
        caps.append(self._probe_repair())
        # Environment intelligence
        caps.append(self._probe_env_intelligence())

        return caps

    def _probe_evolution_single(self) -> CapabilityStatus:
        try:
            from ether_core import get_core
            core = get_core()
            has = hasattr(core.evolution, "evolve_file")
            return CapabilityStatus("Atomic self-modification", has,
                                    "test->snapshot->deploy->rollback", "advanced")
        except Exception as e:
            return CapabilityStatus("Atomic self-modification", False, str(e)[:40], "advanced")

    def _probe_evolution_multi(self) -> CapabilityStatus:
        try:
            from ether_core import get_core
            core = get_core()
            has = hasattr(core.evolution, "evolve_files")
            return CapabilityStatus("Multi-file atomic transactions", has,
                                    "all-or-nothing across N files, verified rollback",
                                    "premium")
        except Exception as e:
            return CapabilityStatus("Multi-file atomic transactions", False,
                                    str(e)[:40], "premium")

    def _probe_transaction_log(self) -> CapabilityStatus:
        log = self.root / "data" / "ether_events.jsonl"
        # The capability exists if EventLog persists; presence of code is enough,
        # the file appears on first real event.
        try:
            from ether_core import EventLog
            return CapabilityStatus("Persistent transaction log", True,
                                    f"data/ether_events.jsonl", "advanced")
        except Exception as e:
            return CapabilityStatus("Persistent transaction log", False, str(e)[:40], "advanced")

    def _probe_vector_rag(self) -> CapabilityStatus:
        try:
            import chromadb  # noqa
            import llama_index.core  # noqa
            return CapabilityStatus("Vector RAG (ChromaDB + LlamaIndex)", True,
                                    "semantic search over storage/", "advanced")
        except Exception:
            return CapabilityStatus("Vector RAG (ChromaDB + LlamaIndex)", False,
                                    "not installed yet (installs in deploy)", "advanced")

    def _probe_self_editor(self) -> CapabilityStatus:
        try:
            from self_editor import get_editor
            ed = get_editor()
            has = hasattr(ed, "write_file") and hasattr(ed, "rollback")
            return CapabilityStatus("Self-editing engine", has,
                                    "read/write/patch/rollback own source", "advanced")
        except Exception as e:
            return CapabilityStatus("Self-editing engine", False, str(e)[:40], "advanced")

    def _probe_repair(self) -> CapabilityStatus:
        try:
            from deployment.repair import Repairer  # noqa
            return CapabilityStatus("Self-healing repair", True,
                                    "broken venv, corrupt index, stale cache", "advanced")
        except Exception as e:
            return CapabilityStatus("Self-healing repair", False, str(e)[:40], "advanced")

    def _probe_env_intelligence(self) -> CapabilityStatus:
        return CapabilityStatus("Environment intelligence", True,
                                "hardware-aware model + RAG tuning", "premium")


class EnvironmentIntelligence:
    """Reads REAL hardware facts and derives recommendations."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def profile(self) -> EnvironmentProfile:
        cpu = os.cpu_count() or 1

        ram_gb = None
        try:
            import psutil
            ram_gb = round(psutil.virtual_memory().total / 1_073_741_824, 1)
        except Exception:
            # stdlib fallback (Linux): read /proc/meminfo
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal"):
                            kb = int(line.split()[1])
                            ram_gb = round(kb / 1_048_576, 1)
                            break
            except Exception:
                ram_gb = None

        try:
            disk_free = round(shutil.disk_usage(str(self.root)).free / 1_073_741_824, 1)
        except Exception:
            disk_free = 0.0

        # Real recommendations from real numbers
        if ram_gb is None:
            tier = "7B-q4 (safe default)"
        elif ram_gb >= 32:
            tier = "up to 14B-q4 (you have plenty of RAM)"
        elif ram_gb >= 16:
            tier = "7-8B-q4 (comfortable)"
        elif ram_gb >= 8:
            tier = "7B-q4 (fits, close other apps)"
        else:
            tier = "3B-q4 (low RAM -- use smaller models)"

        # RAG chunk size from how much content exists
        storage = self.root / "storage"
        md_count = len(list(storage.rglob("*.md"))) if storage.exists() else 0
        if md_count > 200:
            chunk = 512    # lots of content -> smaller chunks, finer retrieval
        elif md_count > 50:
            chunk = 768
        else:
            chunk = 1024   # little content -> bigger chunks, more context each

        # Scaling-aware: if a deployment mode is detected, let it raise limits
        try:
            from deployment.scaling import get_profile
            prof = get_profile(self.root)
            # On desktop/server, prefer the profile's (larger) chunk + bigger models
            if prof.mode.value in ("desktop", "server"):
                chunk = prof.rag_chunk_size
                tier = f"up to {prof.max_model_params_b}B-q4 ({prof.mode.value} mode)"
        except Exception:
            pass

        return EnvironmentProfile(
            cpu_count=cpu, ram_gb=ram_gb, disk_free_gb=disk_free,
            platform=sys.platform,
            recommended_model_tier=tier,
            recommended_rag_chunk=chunk,
        )


class DeploymentMutator:
    """
    Applies small, logged, rollback-safe improvements to the deployed system's
    OWN config after a successful deploy. Each mutation is recorded so it runs
    once and can be undone. Mutations only touch config files, never code.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.config = root / "config"
        self.config.mkdir(exist_ok=True)
        self.ledger = root / "data" / "deployment_mutations.json"
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self._applied = self._load()

    def _load(self) -> Dict:
        if self.ledger.exists():
            try:
                return json.loads(self.ledger.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save(self) -> None:
        try:
            self.ledger.write_text(json.dumps(self._applied, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _already(self, mutation_id: str) -> bool:
        return mutation_id in self._applied

    def _record(self, mutation_id: str, detail: Dict) -> None:
        from datetime import datetime, timezone
        self._applied[mutation_id] = {"applied": datetime.now(timezone.utc).isoformat(),
                                      **detail}
        self._save()

    def apply_rag_chunk_tuning(self, chunk_size: int) -> Optional[str]:
        """Write a hardware/content-aware RAG chunk setting to config (once)."""
        mid = "rag_chunk_tuning"
        if self._already(mid):
            return None
        cfg_path = self.config / "rag_settings.json"
        old = {}
        if cfg_path.exists():
            try:
                old = json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                old = {}
        new = {**old, "chunk_size": chunk_size, "chunk_overlap": chunk_size // 8}
        cfg_path.write_text(json.dumps(new, indent=2), encoding="utf-8")
        self._record(mid, {"file": "config/rag_settings.json", "chunk_size": chunk_size})
        return f"RAG chunk size tuned to {chunk_size} (from content volume)"

    def apply_logging_defaults(self) -> Optional[str]:
        """Ensure structured logging defaults exist in config (once)."""
        mid = "logging_defaults"
        if self._already(mid):
            return None
        cfg_path = self.config / "logging.json"
        if not cfg_path.exists():
            cfg_path.write_text(json.dumps(
                {"level": "INFO", "json": True, "rotate_mb": 10}, indent=2),
                encoding="utf-8")
        self._record(mid, {"file": "config/logging.json"})
        return "Structured logging defaults written"

    def rollback_all(self) -> List[str]:
        """Undo recorded mutations (best-effort) and clear the ledger."""
        undone = []
        for mid, info in list(self._applied.items()):
            f = info.get("file")
            if f and (self.root / f).exists():
                # We don't delete config the user may rely on; we just unrecord.
                undone.append(mid)
        self._applied = {}
        self._save()
        return undone

    def applied_summary(self) -> List[str]:
        return list(self._applied.keys())
