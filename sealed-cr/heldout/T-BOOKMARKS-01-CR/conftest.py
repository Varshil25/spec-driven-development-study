import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import Runner  # noqa: E402


@pytest.fixture
def run(workdir):
    return Runner("bookmarks", workdir)


@pytest.fixture
def bm(run):
    """Run a bookmarks command against b.db in the test's work directory."""
    def call(*args, **kwargs):
        return run("--db", "b.db", *args, **kwargs)
    return call
