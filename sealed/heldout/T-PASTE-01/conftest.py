import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pastebin_server import Server  # noqa: E402


@pytest.fixture
def server(workdir):
    srv = Server(workdir).start()
    yield srv
    srv.stop()
