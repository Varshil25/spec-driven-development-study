import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import Runner  # noqa: E402


@pytest.fixture
def run(workdir):
    return Runner("tarx", workdir)


@pytest.fixture
def photos(workdir):
    """A folder photos/ with two files, as in the change request's example."""
    (workdir / "photos").mkdir()
    (workdir / "photos" / "a.jpg").write_bytes(b"jpeg-a")
    (workdir / "photos" / "b.jpg").write_bytes(b"jpeg-b")
    return workdir / "photos"

