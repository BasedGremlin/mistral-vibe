"""Retry policy: exact ladder, deterministic bounded jitter, invariants."""

from ether_runtime import retry_delay, validate_policy
from ether_runtime.retry import JITTER_FRACTION, RETRY_DELAYS, jitter_factor

import pytest


def test_nominal_ladder_matches_v11_record():
    assert RETRY_DELAYS == (1.0, 2.0, 4.0, 8.0, 16.0)
    assert sum(RETRY_DELAYS) == 31.0


def test_policy_constraint_check_passes():
    report = validate_policy()
    assert report["constraint_check"] == "passed"
    assert report["total_nominal_delay"] < report["reclaim_idle_seconds"]


def test_jitter_is_deterministic_and_bounded():
    for attempt in range(1, 6):
        a = jitter_factor("task-a", attempt)
        b = jitter_factor("task-a", attempt)
        assert a == b, "same task+attempt must jitter identically"
        assert 1 - JITTER_FRACTION <= a <= 1 + JITTER_FRACTION


def test_jitter_spreads_across_tasks():
    factors = {jitter_factor(f"task-{i}", 1) for i in range(50)}
    assert len(factors) > 40, "jitter should differ across task ids"


def test_retry_delay_uses_ladder_with_jitter():
    for attempt, nominal in enumerate(RETRY_DELAYS, start=1):
        delay = retry_delay("t", attempt)
        assert nominal * (1 - JITTER_FRACTION) <= delay <= nominal * (1 + JITTER_FRACTION)


def test_attempt_must_be_positive():
    with pytest.raises(ValueError):
        retry_delay("t", 0)
