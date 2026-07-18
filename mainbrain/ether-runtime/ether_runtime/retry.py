"""Retry policy for the durable task runtime.

Implements the verified policy from the EtherAI Absorption v11 design record:
nominal delays 1, 2, 4, 8, 16 seconds, deterministic +/-20% jitter derived
from SHA-256(task_id + attempt), and a stream reclaim threshold of 60 seconds
that strictly exceeds the total nominal retry delay (31 seconds), so a task
in its normal retry ladder is never stolen by reclaim.
"""

from __future__ import annotations

import hashlib

RETRY_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0)
JITTER_FRACTION = 0.2
RECLAIM_IDLE_SECONDS = 60.0
MAX_TASK_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_ATTEMPTS = len(RETRY_DELAYS) + 1  # first attempt + one per delay


def jitter_factor(task_id: str, attempt: int) -> float:
    """Deterministic jitter in [1 - JITTER_FRACTION, 1 + JITTER_FRACTION].

    Derived from SHA-256(task_id + attempt) so retries spread across tasks
    while remaining reproducible and auditable.
    """
    digest = hashlib.sha256(f"{task_id}:{attempt}".encode("utf-8")).digest()
    unit = int.from_bytes(digest[:8], "big") / float(2**64 - 1)
    return 1.0 - JITTER_FRACTION + (2.0 * JITTER_FRACTION * unit)


def retry_delay(task_id: str, attempt: int) -> float:
    """Jittered delay before retry number `attempt` (1-based failed attempts).

    attempt=1 means the first attempt just failed -> first delay in the ladder.
    Attempts beyond the ladder reuse the final delay (callers normally
    dead-letter before that happens).
    """
    if attempt < 1:
        raise ValueError("attempt is 1-based; got %r" % attempt)
    nominal = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
    return nominal * jitter_factor(task_id, attempt)


def validate_policy() -> dict:
    """Re-derive the v11 constraint check; raises if the invariant breaks."""
    total_nominal = sum(RETRY_DELAYS)
    max_jittered = max(RETRY_DELAYS) * (1.0 + JITTER_FRACTION)
    ok = (
        total_nominal < RECLAIM_IDLE_SECONDS
        and MAX_TASK_TIMEOUT_SECONDS < RECLAIM_IDLE_SECONDS
    )
    if not ok:
        raise AssertionError(
            "retry policy invariant broken: nominal retry total %.1fs / task "
            "timeout %.1fs must stay under reclaim threshold %.1fs"
            % (total_nominal, MAX_TASK_TIMEOUT_SECONDS, RECLAIM_IDLE_SECONDS)
        )
    return {
        "nominal_delays": list(RETRY_DELAYS),
        "total_nominal_delay": total_nominal,
        "max_single_jittered_delay": max_jittered,
        "jitter_fraction": JITTER_FRACTION,
        "reclaim_idle_seconds": RECLAIM_IDLE_SECONDS,
        "max_task_timeout_seconds": MAX_TASK_TIMEOUT_SECONDS,
        "constraint_check": "passed",
    }
