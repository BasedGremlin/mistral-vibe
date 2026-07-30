from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
import io
import os
from pathlib import Path
from typing import cast

import pexpect
import pytest

from tests import TESTS_ROOT
from tests.e2e.common import timeout_scale, write_e2e_config
from tests.e2e.mock_server import ChunkFactory, StreamingMockServer


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Scale every ``@pytest.mark.timeout(N)`` in tests/e2e by the same factor
    as the in-test waits (see ``timeout_scale()`` in ``common.py``).

    These marks exist as a backstop against a genuinely hung process, not as
    the primary assertion mechanism -- ``wait_for_rendered_text`` and friends
    already fail with a diagnosis well before the outer mark would fire. But an
    un-scaled mark is a trap: on a loaded machine it can (and did) expire
    *before* an inner wait's own scaled deadline, which turns a clear
    "waited Ns for text that never rendered" into a bare pytest-timeout
    kill with none of that diagnosis attached. Scaling it here keeps the
    backstop a backstop instead of the thing that fires first.

    Scoped to tests/e2e (via each item's own file path, not a directory
    argument) so it can never reach into vibe's other suites, which do not
    drive a pty and do not have this failure mode.
    """
    scale = timeout_scale()
    if scale == 1.0:
        return
    e2e_dir = str(Path(__file__).resolve().parent)
    for item in items:
        if not str(item.fspath).startswith(e2e_dir):
            continue
        marker = item.get_closest_marker("timeout")
        if marker is None or not marker.args:
            continue
        scaled_value = marker.args[0] * scale
        item.own_markers = [
            pytest.Mark("timeout", (scaled_value,), m.kwargs, _ispytest=True)
            if m.name == "timeout"
            else m
            for m in item.own_markers
        ]


@pytest.fixture
def streaming_mock_server(
    request: pytest.FixtureRequest,
) -> Iterator[StreamingMockServer]:
    chunk_factory = cast(ChunkFactory | None, getattr(request, "param", None))
    server = StreamingMockServer(chunk_factory=chunk_factory)
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def setup_e2e_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    streaming_mock_server: StreamingMockServer,
) -> None:
    vibe_home = tmp_path / "vibe-home"
    write_e2e_config(vibe_home, streaming_mock_server.api_base)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    monkeypatch.setenv("VIBE_HOME", str(vibe_home))
    monkeypatch.setenv("VIBE_TEST_DISABLE_KEYRING", "1")
    monkeypatch.setenv("TERM", "xterm-256color")


@pytest.fixture
def e2e_workdir(tmp_path: Path) -> Path:
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    return workdir


type SpawnedVibeContext = Iterator[tuple[pexpect.spawn, io.StringIO]]
type SpawnedVibeContextManager = AbstractContextManager[
    tuple[pexpect.spawn, io.StringIO]
]
type SpawnedVibeFactory = Callable[
    [Path, Sequence[str] | None], SpawnedVibeContextManager
]


@pytest.fixture
def spawned_vibe_process() -> SpawnedVibeFactory:
    @contextmanager
    def spawn(
        workdir: Path, extra_args: Sequence[str] | None = None
    ) -> SpawnedVibeContext:
        captured = io.StringIO()
        env = os.environ.copy()
        env["VIBE_TEST_DISABLE_KEYRING"] = "1"
        child = pexpect.spawn(
            "uv",
            ["run", "vibe", "--workdir", str(workdir), *(extra_args or [])],
            cwd=str(TESTS_ROOT.parent),
            env=cast("os._Environ[str]", env),
            encoding="utf-8",
            timeout=30,
            dimensions=(36, 120),
        )
        child.logfile_read = captured

        try:
            yield child, captured
        finally:
            if child.isalive():
                child.terminate(force=True)
            if not child.closed:
                child.close()

    return spawn
