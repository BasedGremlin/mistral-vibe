"""
editor/self_healer.py -- manifest-driven startup self-healing.
=============================================================
Uses core.paths as the single source of truth (it does NOT do its own path
discovery). On startup it:
  - checks the PROJECT_STRUCTURE manifest for missing essential directories
  - creates the recoverable ones (directories are safe to create)
  - reports anything unrecoverable (e.g. a missing critical .py file -- we do
    NOT fabricate source code to "heal" that; we report it honestly)

Returns a structured HealthResult so a UI can show it.

This is one of the FEW modules permitted to mutate the filesystem (per the
essay's Phase 7: centralize side effects). Most modules should just read paths.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# Make core importable whether run from root or elsewhere
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.paths import (PATHS, PROJECT_STRUCTURE, CRITICAL_FILES,
                        verify_critical_files)


@dataclass
class HealthResult:
    status: str                              # OK | WARNING | ERROR
    recovered: bool = False
    created: List[str] = field(default_factory=list)
    missing_unrecoverable: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)

    def as_dict(self):
        return {
            "status": self.status,
            "recovered": self.recovered,
            "created": self.created,
            "missing_unrecoverable": self.missing_unrecoverable,
            "messages": self.messages,
        }


class SelfHealer:
    def __init__(self) -> None:
        self.root = PATHS.root

    def heal(self) -> HealthResult:
        created: List[str] = []
        messages: List[str] = []

        # 1. Essential directories -- safe to create from the manifest
        for name, essential in PROJECT_STRUCTURE.items():
            if not essential:
                continue
            d = self.root / name
            if not d.exists():
                try:
                    d.mkdir(parents=True, exist_ok=True)
                    created.append(name)
                    messages.append(f"created missing directory: {name}")
                except Exception as e:
                    messages.append(f"FAILED to create {name}: {e}")

        # 2. Critical files -- CANNOT be fabricated. Report honestly.
        crit = verify_critical_files()
        unrecoverable = [f for f, ok in crit.items() if not ok]
        for f in unrecoverable:
            messages.append(f"CRITICAL FILE MISSING (cannot auto-heal): {f}")

        # 3. Decide status
        if unrecoverable:
            status = "ERROR"
        elif created:
            status = "WARNING"
        else:
            status = "OK"
            messages.append("all essential directories and critical files present")

        return HealthResult(
            status=status,
            recovered=bool(created) and not unrecoverable,
            created=created,
            missing_unrecoverable=unrecoverable,
            messages=messages)


def run_self_heal() -> HealthResult:
    return SelfHealer().heal()
