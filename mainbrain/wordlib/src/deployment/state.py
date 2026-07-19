"""
Persistent deployment state -- enables resume-from-failure.
Stored in data/deployment_state.json. Each stage records status + timestamp,
so a re-run skips already-completed stages instead of starting from zero.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeploymentState:
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_DONE    = "done"
    STATUS_FAILED  = "failed"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "data" / "deployment_state.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._state: Dict = self._load()

    def _load(self) -> Dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"version": 1, "started": _utc(), "stages": {}}

    def _save(self) -> None:
        try:
            self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        except Exception:
            pass  # state persistence is best-effort, never blocks install

    # ── Stage tracking ───────────────────────────────────────────────────────
    def stage_status(self, name: str) -> str:
        return self._state["stages"].get(name, {}).get("status", self.STATUS_PENDING)

    def is_done(self, name: str) -> bool:
        return self.stage_status(name) == self.STATUS_DONE

    def mark_running(self, name: str) -> None:
        self._state["stages"][name] = {"status": self.STATUS_RUNNING, "started": _utc()}
        self._save()

    def mark_done(self, name: str, detail: str = "") -> None:
        entry = self._state["stages"].setdefault(name, {})
        entry.update({"status": self.STATUS_DONE, "finished": _utc(), "detail": detail})
        self._save()

    def mark_failed(self, name: str, error: str = "") -> None:
        entry = self._state["stages"].setdefault(name, {})
        entry.update({"status": self.STATUS_FAILED, "finished": _utc(), "error": error})
        self._save()

    def reset(self) -> None:
        """Forget all progress -- forces a full re-run."""
        self._state = {"version": 1, "started": _utc(), "stages": {}}
        self._save()

    def completed_count(self) -> int:
        return sum(1 for s in self._state["stages"].values()
                   if s.get("status") == self.STATUS_DONE)

    def summary(self) -> Dict:
        return dict(self._state)
