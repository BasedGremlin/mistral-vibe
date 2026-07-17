"""
Scaling system (v13.6).
=======================
Lets the system adapt to where it's actually running instead of always assuming
a tiny USB. Real detection from real facts (free disk, RAM, CPU); real,
different limits per mode.

DeploymentMode:
  USB     -- portable stick, conservative limits, small models, small RAG chunks
  DESKTOP -- a real machine with room, larger models + parallelism allowed
  SERVER  -- lots of disk/RAM/cores, most aggressive limits

Auto-detection is honest: it picks a mode from measured resources but can be
overridden explicitly (env var WORDLIB_MODE or a flag).
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class DeploymentMode(str, Enum):
    USB = "usb"
    DESKTOP = "desktop"
    SERVER = "server"


@dataclass
class ScalingProfile:
    mode: DeploymentMode
    # Resource facts that drove the decision
    disk_free_gb: float
    ram_gb: Optional[float]
    cpu_count: int
    # Derived limits (the things the rest of the system should read)
    rag_chunk_size: int
    max_model_params_b: int          # largest model size (billions) to suggest
    max_parallel_agents: int         # how many agents may run concurrently
    allow_heavy_optional: bool       # numba, big indexes, etc.
    reason: str = ""

    def as_dict(self):
        return {
            "mode": self.mode.value,
            "disk_free_gb": self.disk_free_gb,
            "ram_gb": self.ram_gb,
            "cpu_count": self.cpu_count,
            "rag_chunk_size": self.rag_chunk_size,
            "max_model_params_b": self.max_model_params_b,
            "max_parallel_agents": self.max_parallel_agents,
            "allow_heavy_optional": self.allow_heavy_optional,
            "reason": self.reason,
        }


def _ram_gb() -> Optional[float]:
    try:
        import psutil
        return round(psutil.virtual_memory().total / 1_073_741_824, 1)
    except Exception:
        pass
    try:  # stdlib fallback (Linux)
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    return round(int(line.split()[1]) / 1_048_576, 1)
    except Exception:
        pass
    return None


def _disk_free_gb(root: Path) -> float:
    try:
        return round(shutil.disk_usage(str(root)).free / 1_073_741_824, 1)
    except Exception:
        return 0.0


def detect_mode(root: Path) -> ScalingProfile:
    """
    Detect the deployment mode from real resources. Explicit override wins:
      env WORDLIB_MODE = usb | desktop | server
    """
    root = Path(root)
    disk = _disk_free_gb(root)
    ram = _ram_gb()
    cpu = os.cpu_count() or 1

    override = os.environ.get("WORDLIB_MODE", "").strip().lower()
    forced = None
    if override in (m.value for m in DeploymentMode):
        forced = DeploymentMode(override)

    if forced:
        mode = forced
        reason = f"forced via WORDLIB_MODE={override}"
    else:
        # Heuristic from real numbers. A USB stick is small + often on a host
        # with limited free space dedicated to it; a server has lots of cores+RAM.
        if (ram and ram >= 32) and cpu >= 8 and disk >= 100:
            mode = DeploymentMode.SERVER
            reason = f"{ram}GB RAM, {cpu} cores, {disk}GB free -> server"
        elif (ram and ram >= 12) and disk >= 40:
            mode = DeploymentMode.DESKTOP
            reason = f"{ram}GB RAM, {disk}GB free -> desktop"
        else:
            mode = DeploymentMode.USB
            reason = f"{ram or '?'}GB RAM, {disk}GB free -> usb (conservative)"

    return _profile_for(mode, disk, ram, cpu, reason)


def _profile_for(mode: DeploymentMode, disk: float, ram, cpu: int,
                 reason: str) -> ScalingProfile:
    if mode == DeploymentMode.SERVER:
        return ScalingProfile(mode, disk, ram, cpu,
                              rag_chunk_size=512, max_model_params_b=70,
                              max_parallel_agents=min(cpu, 8),
                              allow_heavy_optional=True, reason=reason)
    if mode == DeploymentMode.DESKTOP:
        return ScalingProfile(mode, disk, ram, cpu,
                              rag_chunk_size=768, max_model_params_b=14,
                              max_parallel_agents=min(cpu, 4),
                              allow_heavy_optional=True, reason=reason)
    # USB
    return ScalingProfile(mode, disk, ram, cpu,
                          rag_chunk_size=1024, max_model_params_b=8,
                          max_parallel_agents=2,
                          allow_heavy_optional=False, reason=reason)


# Singleton-ish cache
_profile: Optional[ScalingProfile] = None

def get_profile(root: Path, refresh: bool = False) -> ScalingProfile:
    global _profile
    if _profile is None or refresh:
        _profile = detect_mode(root)
    return _profile
