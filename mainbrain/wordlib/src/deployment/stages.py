"""
Stage engine -- dependency-ordered execution with retry/backoff and rollback.

A Stage wraps one or more actions. The engine:
  - skips stages already marked done in DeploymentState (resume)
  - enforces depends_on ordering
  - retries Recoverable failures with exponential backoff
  - stops on Fatal / UserActionRequired with a clear report
  - runs an optional rollback() for a stage that fails after partial work
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .errors import (DeploymentError, RecoverableError, FatalError,
                     UserActionRequired)
from .state import DeploymentState


@dataclass
class StageResult:
    name: str
    ok: bool
    skipped: bool = False
    detail: str = ""
    error: Optional[DeploymentError] = None


@dataclass
class Stage:
    name: str
    run: Callable[[Callable], str]      # receives a progress(pct, status) callback
    depends_on: List[str] = field(default_factory=list)
    rollback: Optional[Callable[[], None]] = None
    max_retries: int = 2                 # for RecoverableError
    optional: bool = False               # failure doesn't abort the whole deploy


class StageEngine:
    def __init__(self, state: DeploymentState, ui=None) -> None:
        self.state = state
        self.ui = ui                     # optional UI with .stage_start/.progress/.stage_done
        self.results: List[StageResult] = []

    def _emit_start(self, stage: Stage, index: int, total: int):
        if self.ui:
            self.ui.stage_start(index, total, stage.name)

    def _emit_progress(self, pct: int, status: str = ""):
        if self.ui:
            self.ui.progress(pct, status)

    def _emit_done(self, ok: bool, detail: str = ""):
        if self.ui:
            self.ui.stage_done(ok, detail)

    def run_all(self, stages: List[Stage]) -> bool:
        total = len(stages)
        done_names = set()

        for i, stage in enumerate(stages, 1):
            # Dependency check
            missing = [d for d in stage.depends_on
                       if d not in done_names and not self.state.is_done(d)]
            if missing:
                err = FatalError(
                    f"Stage '{stage.name}' needs {missing} which did not complete.",
                    "Re-run the installer; earlier stages must succeed first.")
                self.results.append(StageResult(stage.name, False, error=err))
                self._emit_start(stage, i, total)
                self._emit_done(False, f"blocked by {missing}")
                return False

            # Resume: skip if already done
            if self.state.is_done(stage.name):
                self.results.append(StageResult(stage.name, True, skipped=True,
                                                 detail="already done"))
                done_names.add(stage.name)
                self._emit_start(stage, i, total)
                self._emit_progress(100, "already done (resumed)")
                self._emit_done(True, "resumed")
                continue

            # Execute with retry/backoff
            self._emit_start(stage, i, total)
            self.state.mark_running(stage.name)
            ok, detail, error = self._run_with_retry(stage)

            if ok:
                self.state.mark_done(stage.name, detail)
                self.results.append(StageResult(stage.name, True, detail=detail))
                done_names.add(stage.name)
                self._emit_done(True, detail)
            else:
                # Attempt rollback if provided
                if stage.rollback:
                    try:
                        stage.rollback()
                    except Exception:
                        pass
                self.state.mark_failed(stage.name, str(error) if error else detail)
                self.results.append(StageResult(stage.name, False, detail=detail,
                                                 error=error))
                self._emit_done(False, detail)

                if stage.optional:
                    # Optional stage failed -- continue, but mark not-done
                    done_names.discard(stage.name)
                    continue
                return False  # hard stop on required stage failure

        return True

    def _run_with_retry(self, stage: Stage):
        attempt = 0
        while True:
            try:
                detail = stage.run(self._emit_progress)
                return True, detail or "", None
            except RecoverableError as e:
                attempt += 1
                if attempt > stage.max_retries:
                    return False, f"{e.message} (gave up after {attempt} tries)", e
                backoff = 2 ** attempt
                self._emit_progress(0, f"retry {attempt} in {backoff}s: {e.message}")
                time.sleep(backoff)
            except (FatalError, UserActionRequired) as e:
                return False, e.message, e
            except Exception as e:
                # Unknown failure -- treat as fatal but capture cleanly
                return False, str(e), FatalError(str(e),
                    "Run TROUBLESHOOT.bat for a full diagnosis.")
