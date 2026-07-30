"""Unit tests for tests/e2e/common.py's own logic.

This harness drives a real TUI in a real pty and asserts on rendered text, so
its own helper functions (timeout scaling, wrap-tolerant text matching, and
the diagnosis attached to a failure) had never been tested in isolation --
every one of them was previously exercised only indirectly, by whichever e2e
test happened to hit that code path, at whatever CPU load the runner had that
day. That is exactly how the flakiness this module now guards against went
unnoticed for so long: a helper bug here silently changes the odds of every
e2e test simultaneously, in an untestable, timing-dependent way.

These tests are fast, deterministic, and never spawn a real vibe process --
they exercise the helpers directly with synthetic input.
"""

from __future__ import annotations

import io
import time

import pexpect
import pytest

from tests.e2e.common import (
    TIMEOUT_SCALE_ENV,
    _describe_wait_failure,
    _longest_prefix_seen,
    ansi_tolerant_pattern,
    poll_until,
    rendered_text_present,
    scaled,
    timeout_scale,
    wait_for_rendered_text,
)

# ── timeout_scale / scaled ───────────────────────────────────────────────────


def test_defaults_to_no_scaling_outside_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TIMEOUT_SCALE_ENV, raising=False)
    monkeypatch.delenv("CI", raising=False)
    assert timeout_scale() == 1.0
    assert scaled(10) == 10


def test_ci_gets_extra_headroom_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TIMEOUT_SCALE_ENV, raising=False)
    monkeypatch.setenv("CI", "true")
    assert timeout_scale() > 1.0
    assert scaled(10) == 10 * timeout_scale()


def test_explicit_env_var_overrides_ci_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv(TIMEOUT_SCALE_ENV, "2.5")
    assert timeout_scale() == 2.5
    assert scaled(4) == 10.0


def test_non_numeric_scale_raises_rather_than_silently_disabling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TIMEOUT_SCALE_ENV, "not-a-number")
    with pytest.raises(ValueError, match=TIMEOUT_SCALE_ENV):
        timeout_scale()


@pytest.mark.parametrize("bad_value", ["0", "-1", "-3.5"])
def test_non_positive_scale_raises(
    monkeypatch: pytest.MonkeyPatch, bad_value: str
) -> None:
    monkeypatch.setenv(TIMEOUT_SCALE_ENV, bad_value)
    with pytest.raises(ValueError, match="must be > 0"):
        timeout_scale()


# ── rendered_text_present ────────────────────────────────────────────────────


def test_plain_substring_matches() -> None:
    assert rendered_text_present("hello world", "world")


def test_missing_text_does_not_match() -> None:
    # The negative case matters as much as the positive one: a matcher that
    # is too permissive would hide real rendering failures instead of
    # catching them.
    assert not rendered_text_present("hello world", "goodbye")


def test_ansi_escape_codes_between_characters_are_tolerated() -> None:
    # A real terminal can recolor or reposition mid-word; the escape codes
    # land between characters of the needle, not around it.
    haystack = "\x1b[32mA\x1b[0mp\x1b[1mp\x1b[0mroved file was written."
    assert rendered_text_present(haystack, "Approved file was written.")


def test_crlf_wrapping_inside_the_needle_is_tolerated() -> None:
    # A hard-wrapped terminal line can split a phrase with a bare CR or LF.
    haystack = "Approved fi\r\nle was written."
    assert rendered_text_present(haystack, "Approved file was written.")


def test_fast_path_avoids_the_regex_for_the_common_case() -> None:
    # When the plain substring is already present, the cheap `in` check must
    # short-circuit -- there is no reason to run the pattern search at all.
    huge = "x" * 100_000 + "needle here" + "y" * 100_000
    start = time.monotonic()
    assert rendered_text_present(huge, "needle here")
    assert time.monotonic() - start < 0.5


# ── _longest_prefix_seen (failure diagnosis) ─────────────────────────────────


def test_full_prefix_when_the_whole_needle_rendered() -> None:
    assert _longest_prefix_seen(
        "Approved file was written.", "Approved file was written."
    ) == ("Approved file was written.")


def test_partial_prefix_when_rendering_was_cut_off() -> None:
    # This is the CI failure shape verbatim: the text was rendering and lost
    # a race with the deadline mid-word.
    haystack = "✓ Created approved-write.txt\n  ⎣ approved content\n\nAppro"
    prefix = _longest_prefix_seen(haystack, "Approved file was written.")
    assert prefix == "Appro"


def test_empty_prefix_when_nothing_rendered() -> None:
    assert (
        _longest_prefix_seen("totally unrelated screen", "Approved file was written.")
        == ""
    )


def test_failure_message_distinguishes_partial_from_absent() -> None:
    partial = _describe_wait_failure(
        "...Appro", "Approved.", elapsed=5.0, budget=10.0, reason="Timed out"
    )
    absent = _describe_wait_failure(
        "totally unrelated", "Approved.", elapsed=5.0, budget=10.0, reason="Timed out"
    )
    assert "was painting this text and ran out of time" in partial
    assert "never got this far" in absent


# ── poll_until ────────────────────────────────────────────────────────────────


def test_poll_until_passes_once_predicate_becomes_true() -> None:
    calls = {"n": 0}

    def predicate() -> bool:
        calls["n"] += 1
        return calls["n"] >= 3

    poll_until(predicate, timeout=5, message="should not fire")
    assert calls["n"] >= 3


def test_poll_until_raises_with_the_given_message_on_timeout() -> None:
    with pytest.raises(AssertionError, match="custom failure detail"):
        poll_until(lambda: False, timeout=0.2, message="custom failure detail")


def test_poll_until_checks_once_more_after_the_deadline() -> None:
    # A predicate that flips true during the final sleep is a genuine pass,
    # not a failure of timing -- the result must not depend on exactly where
    # the last 0.05s sleep landed relative to the deadline.
    deadline = time.monotonic() + 0.05

    def predicate() -> bool:
        return time.monotonic() >= deadline

    poll_until(predicate, timeout=0.05, message="should not fire")


# ── wait_for_rendered_text (fast success path, no real pexpect needed) ──────


class _NeverCalledSpawn:
    """A pexpect.spawn stand-in whose .expect() must never be invoked --
    used to prove the fast path returns without touching the child at all.
    """

    def expect(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError(
            "child.expect() should not be called when the text is already present"
        )


def test_wait_for_rendered_text_returns_immediately_when_already_present() -> None:
    captured = io.StringIO()
    captured.write("Approved file was written.")
    wait_for_rendered_text(
        _NeverCalledSpawn(), captured, needle="Approved file was written.", timeout=5
    )


class _AlwaysTimesOutSpawn:
    def expect(self, *_args: object, **_kwargs: object) -> None:
        raise pexpect.TIMEOUT("simulated: nothing new arrived")


def test_wait_for_rendered_text_reports_a_diagnosis_on_real_timeout() -> None:
    captured = io.StringIO()
    captured.write("unrelated screen contents")
    with pytest.raises(AssertionError) as excinfo:
        wait_for_rendered_text(
            _AlwaysTimesOutSpawn(),
            captured,
            needle="Approved file was written.",
            timeout=0.1,
        )
    assert "never got this far" in str(excinfo.value)


# ── ansi_tolerant_pattern (pre-existing, still covered) ─────────────────────


def test_ansi_tolerant_pattern_matches_across_escape_codes() -> None:
    pattern = ansi_tolerant_pattern("Mistral Vibe v")
    assert pattern.search("\x1b[1mMistral\x1b[0m Vibe v2.19.1")
