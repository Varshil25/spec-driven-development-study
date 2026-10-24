import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from login_server import BOB_PASSWORD, PASSWORD, App  # noqa: E402


@pytest.fixture
def app(workdir):
    """A running server with users alice and bob."""
    a = App(workdir)
    assert a.adduser("alice", PASSWORD).returncode == 0
    assert a.adduser("bob", BOB_PASSWORD).returncode == 0
    a.start()
    yield a
    a.stop()


@pytest.fixture
def cli(workdir):
    return App(workdir)
