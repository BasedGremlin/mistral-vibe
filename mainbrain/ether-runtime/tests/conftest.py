import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ether_runtime import TaskRuntime, Worker  # noqa: E402


@pytest.fixture()
def runtime(tmp_path):
    rt = TaskRuntime(tmp_path / "runtime.db", artifact_root=tmp_path / "artifacts")
    yield rt
    rt.close()


@pytest.fixture()
def worker(runtime):
    return Worker(runtime, name="w1")
