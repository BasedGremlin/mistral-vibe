"""Regression test for the ToolResultMessage mount race.

`_content_container` is a Vertical yielded from inside a
`with Horizontal(): ...` block in ToolResultMessage.compose(), so Textual
attaches it on its own message-pump schedule -- independent of when
ToolResultMessage's own on_mount() fires. On a contended runner, on_mount()
(and therefore _render_result()) can start running before that attachment
completes, and mounting into an unattached node raises MountError. This was
observed for real in CI under CPU load (e2e TUI tests failed with exactly
this MountError), not merely suspected.

The test below reproduces the exact state that triggers it -- a
ToolResultMessage whose _content_container exists but is not yet attached --
without depending on real scheduling delay and without lying about Textual's
own is_attached bookkeeping. `compose()` is invoked directly to obtain a real,
genuinely-unattached content container (attaching it is a separate, later
step this test controls), so `is_attached` reports false because the
container truly is not attached yet, the same as in the reported failure.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from textual.app import App, ComposeResult
from textual.containers import Vertical

from tests.stubs.fake_tool import FakeTool, FakeToolArgs, FakeToolResult
from vibe.cli.textual_ui.widgets import tools as tools_module
from vibe.cli.textual_ui.widgets.messages import ExpandingBorder
from vibe.cli.textual_ui.widgets.tools import ToolCallMessage, ToolResultMessage
from vibe.core.types import ToolCallEvent, ToolResultEvent


class _BareApp(App[None]):
    def compose(self) -> ComposeResult:
        yield Vertical(id="root")


def _call_event() -> ToolCallEvent:
    return ToolCallEvent(
        tool_name="stub_tool",
        tool_class=FakeTool,
        args=FakeToolArgs(),
        tool_call_id="a",
    )


def _success_result() -> ToolResultEvent:
    return ToolResultEvent(
        tool_name="stub_tool",
        tool_class=FakeTool,
        result=FakeToolResult(),
        tool_call_id="a",
    )


@pytest.mark.asyncio
async def test_render_result_survives_a_content_container_that_attaches_late() -> None:
    app = _BareApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        root = app.query_one("#root", Vertical)

        call_widget = ToolCallMessage(_call_event())
        result_widget = ToolResultMessage(_success_result(), call_widget)

        # Assign _content_container the same way compose() does, without
        # going through compose()'s `with Horizontal():` context-manager
        # machinery (which requires an active composition frame this test
        # has no reason to set up). The object is real and genuinely
        # unattached -- attaching it is a separate, later step this test
        # controls -- not a container whose is_attached has been faked.
        content_container = Vertical(classes="tool-result-content")
        result_widget._content_container = content_container
        # _render_result()'s tail path (_apply_border_colors) reads _border,
        # normally also assigned in compose() alongside _content_container.
        result_widget._border = ExpandingBorder(classes="tool-result-border")
        assert not content_container.is_attached, (
            "test setup bug: container must start unattached to reproduce "
            "the race -- if this fails, the repro no longer models the bug"
        )

        async def attach_after_a_couple_of_ticks() -> None:
            # Give _render_result()'s guard a couple of loop iterations to
            # observe "not attached yet" before it becomes true, mirroring
            # the real race window rather than attaching instantly.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            await root.mount(content_container)

        # Without the guard in _render_result(), this raises MountError
        # immediately because content_container.is_attached is False the
        # instant the final branch tries to mount into it.
        await asyncio.gather(
            result_widget._render_result(), attach_after_a_couple_of_ticks()
        )

        assert content_container.is_attached
        assert len(list(content_container.children)) > 0


@pytest.mark.asyncio
async def test_wait_until_attached_gives_up_after_the_bound_rather_than_hanging() -> (
    None
):
    """A container that never attaches is a different bug, not this race --
    the wait must be bounded so that case still surfaces (via the caller's own
    mount() raising), instead of hanging forever.
    """

    class _NeverAttaches:
        is_attached = False

    start = time.monotonic()
    await tools_module._wait_until_attached(_NeverAttaches())  # type: ignore[arg-type]
    elapsed = time.monotonic() - start

    # Bounded by _MAX_ATTACH_WAIT_TICKS cooperative yields, not a real sleep --
    # this must return promptly, not hang.
    assert elapsed < 2.0
