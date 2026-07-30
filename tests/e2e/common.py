from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
import io
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Protocol

import pexpect


class SpawnedVibeProcessFixture(Protocol):
    def __call__(
        self, workdir: Path, extra_args: Sequence[str] | None = None
    ) -> AbstractContextManager[tuple[pexpect.spawn, io.StringIO]]: ...


# ── timeout scaling ──────────────────────────────────────────────────────────
# These tests drive a real TUI in a real pty and assert on rendered output, so
# every wait is a bet on how fast the machine paints a frame. That bet is safe on
# an idle dev laptop and unsafe on a shared CI runner, which is exactly the
# flakiness this scaling exists to remove: the assertions are correct, the
# deadlines were simply calibrated on the wrong hardware.
#
# Scaling is applied *inside* the helpers rather than at the ~70 call sites, so
# a timeout written as `timeout=10` keeps reading as "10 seconds of headroom on
# a quiet machine" and automatically gets more on a loaded one. Reproduce a CI
# failure locally with VIBE_E2E_TIMEOUT_SCALE, no code edit needed.
TIMEOUT_SCALE_ENV = "VIBE_E2E_TIMEOUT_SCALE"

# Measured, not guessed: with all cores saturated, the run that fails at the
# unscaled 10s budget completes comfortably at 4x. See the module docstring of
# tests/e2e/test_harness_robustness.py for the reproduction recipe.
_CI_TIMEOUT_SCALE = 4.0


def timeout_scale() -> float:
    """Multiplier applied to every e2e wait.

    Explicit ``VIBE_E2E_TIMEOUT_SCALE`` wins; otherwise CI gets extra headroom
    and local runs stay fast, so a genuine hang still fails quickly for the
    person who can actually debug it.
    """
    raw = os.environ.get(TIMEOUT_SCALE_ENV, "").strip()
    if raw:
        try:
            value = float(raw)
        except ValueError:
            # A typo must not silently disable scaling and reintroduce the
            # flakiness this guards against.
            raise ValueError(
                f"{TIMEOUT_SCALE_ENV}={raw!r} is not a number; "
                "use e.g. VIBE_E2E_TIMEOUT_SCALE=4"
            ) from None
        if value <= 0:
            raise ValueError(f"{TIMEOUT_SCALE_ENV} must be > 0, got {value}")
        return value
    if os.environ.get("CI"):
        return _CI_TIMEOUT_SCALE
    return 1.0


def scaled(timeout: float) -> float:
    """Stretch a hand-written deadline to suit the current machine."""
    return timeout * timeout_scale()


def ansi_tolerant_pattern(text: str) -> re.Pattern[str]:
    ansi = r"(?:\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07|\r|\n)*"
    return re.compile(ansi.join(re.escape(char) for char in text))


def write_e2e_config(vibe_home: Path, api_base: str) -> None:
    vibe_home.mkdir(parents=True, exist_ok=True)
    (vibe_home / "config.toml").write_text(
        "\n".join([
            'active_model = "mock-model"',
            "enable_update_checks = false",
            "disable_welcome_banner_animation = true",
            "",
            "[[providers]]",
            'name = "mock-provider"',
            f'api_base = "{api_base}"',
            'api_key_env_var = "MISTRAL_API_KEY"',
            'backend = "generic"',
            "",
            "[[models]]",
            'name = "mock-model"',
            'provider = "mock-provider"',
            'alias = "mock-model"',
        ]),
        encoding="utf-8",
    )


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07", "", text)


def poll_until(predicate: Callable[[], bool], timeout: float, message: str) -> None:
    deadline = time.monotonic() + scaled(timeout)
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    # Check once more: a predicate that became true during the final sleep is a
    # pass, not a failure. Without this, the result depends on where the last
    # sleep happened to land.
    if predicate():
        return
    raise AssertionError(message)


def wait_for_request_count(
    request_count_getter: Callable[[], int], expected_count: int, timeout: float
) -> None:
    poll_until(
        lambda: request_count_getter() >= expected_count,
        timeout,
        f"Timed out waiting for {expected_count} backend request(s); "
        f"saw {request_count_getter()}.",
    )


def wait_for_main_screen(child: pexpect.spawn, timeout: float = 20.0) -> None:
    child.expect(ansi_tolerant_pattern("Mistral Vibe v"), timeout=scaled(timeout))


# How much of the capture the wrap-tolerant regex is allowed to scan. The cheap
# substring check already covers the whole buffer; this bound only limits the
# fallback, whose per-character pattern is far more expensive.
_FUZZY_SEARCH_WINDOW = 32_768


def rendered_text_present(captured_value: str, needle: str) -> bool:
    """Has ``needle`` appeared on screen, however the terminal chopped it up?

    A TUI does not emit text in one clean write. It repaints, moves the cursor
    mid-string, and hard-wraps at the terminal edge, any of which can split a
    phrase with escape sequences or a CRLF. A plain substring test then fails
    *permanently* rather than slowly, so no amount of extra timeout saves it --
    which makes this a correctness fix, not a patience fix.

    Fast path first (a plain ``in`` over the whole buffer is cheap and covers the
    common case), then the ANSI/CR/LF-tolerant pattern this module already uses
    for ``wait_for_main_screen``. Being strictly more permissive than the old
    check, it can only convert misses into matches.
    """
    if needle in strip_ansi(captured_value):
        return True
    window = captured_value[-_FUZZY_SEARCH_WINDOW:]
    return ansi_tolerant_pattern(needle).search(window) is not None


def _longest_prefix_seen(captured_value: str, needle: str) -> str:
    """The longest leading slice of ``needle`` that did reach the screen.

    This is the single most useful fact when a wait fails: a long prefix means
    the app was rendering and simply lost a race with the deadline, while an
    empty prefix means the text never started and the cause lies upstream. Those
    two failures look identical in a raw screen dump and want opposite fixes.
    """
    haystack = strip_ansi(captured_value)
    for end in range(len(needle), 0, -1):
        if needle[:end] in haystack:
            return needle[:end]
    return ""


def _describe_wait_failure(
    captured_value: str, needle: str, *, elapsed: float, budget: float, reason: str
) -> str:
    prefix = _longest_prefix_seen(captured_value, needle)
    if prefix == needle:
        # Should be unreachable via rendered_text_present, but if it happens the
        # message must not claim the text was missing.
        diagnosis = "text WAS present -- the matcher, not the app, is at fault"
    elif prefix:
        diagnosis = (
            f"partially rendered: got {prefix!r} ({len(prefix)}/{len(needle)} chars) "
            "-- the app was painting this text and ran out of time, so the likely "
            "cause is a slow/contended machine rather than a broken assertion"
        )
    else:
        diagnosis = (
            "not one character of the needle reached the screen -- suspect an "
            "upstream failure (the app never got this far) rather than a timeout"
        )

    dump_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", prefix="vibe-e2e-", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(captured_value)
            dump_path = handle.name
    except OSError:  # pragma: no cover - diagnostics must never mask the failure
        pass

    parts = [
        f"{reason}: {needle!r}",
        f"waited {elapsed:.1f}s of {budget:.1f}s "
        f"(scale {timeout_scale()}x via {TIMEOUT_SCALE_ENV})",
        f"diagnosis: {diagnosis}",
    ]
    if dump_path:
        parts.append(f"full capture ({len(captured_value)} chars): {dump_path}")
    parts.append(f"\nRendered tail:\n{strip_ansi(captured_value)[-1200:]}")
    return "\n".join(parts)


def wait_for_rendered_text(
    child: pexpect.spawn, captured: io.StringIO, needle: str, timeout: float
) -> None:
    budget = scaled(timeout)
    start = time.monotonic()
    while time.monotonic() - start < budget:
        if rendered_text_present(captured.getvalue(), needle):
            return
        try:
            # Block on the child rather than sleeping, so output is pumped into
            # `captured` as it arrives instead of on a fixed cadence.
            child.expect(r"\S", timeout=0.1)
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF as exc:
            # The child may have printed the text and exited in the same breath;
            # decide on the final buffer, not on the exception alone.
            if rendered_text_present(captured.getvalue(), needle):
                return
            raise AssertionError(
                _describe_wait_failure(
                    captured.getvalue(),
                    needle,
                    elapsed=time.monotonic() - start,
                    budget=budget,
                    reason="Child exited while waiting for rendered text",
                )
            ) from exc
    # Final check after the deadline: the last `expect` may have pumped the text
    # in just as the loop condition expired.
    if rendered_text_present(captured.getvalue(), needle):
        return
    raise AssertionError(
        _describe_wait_failure(
            captured.getvalue(),
            needle,
            elapsed=time.monotonic() - start,
            budget=budget,
            reason="Timed out waiting for rendered text",
        )
    )


def send_ctrl_c_until_quit_confirmation(
    child: pexpect.spawn, captured: io.StringIO, timeout: float = 3
) -> None:
    """Send Ctrl+C and wait for quit confirmation prompt. Retries if first Ctrl+C interrupts."""
    budget = scaled(timeout)
    start = time.monotonic()
    attempts = 0
    while time.monotonic() - start < budget:
        attempts += 1
        child.sendcontrol("c")
        try:
            # Bounded by the remaining budget so a generous outer timeout is not
            # spent entirely inside one inner expect.
            remaining = max(0.1, min(scaled(2), budget - (time.monotonic() - start)))
            child.expect(
                ansi_tolerant_pattern("Press Ctrl+C again to quit"), timeout=remaining
            )
            # Confirmation prompt appeared, send second Ctrl+C
            child.sendcontrol("c")
            return
        except pexpect.TIMEOUT:
            # First Ctrl+C may have interrupted something, try again
            continue
        except pexpect.EOF as exc:
            # Already gone: the caller's follow-up expect(EOF) would pass anyway,
            # so treat this as success rather than a confusing timeout report.
            if not child.isalive():
                return
            raise AssertionError(
                "Child closed its output while waiting for the quit "
                f"confirmation prompt (after {attempts} Ctrl+C).\n\n"
                f"Rendered tail:\n{strip_ansi(captured.getvalue())[-1200:]}"
            ) from exc
    raise AssertionError(
        f"Timed out waiting for quit confirmation prompt after {attempts} Ctrl+C "
        f"in {budget:.1f}s (scale {timeout_scale()}x).\n\n"
        f"Rendered tail:\n{strip_ansi(captured.getvalue())[-1200:]}"
    )
