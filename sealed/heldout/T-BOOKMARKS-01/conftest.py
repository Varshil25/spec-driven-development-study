import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import Runner  # noqa: E402


class Bookmarks:
    """Runs the SUT against a database file in the scratch directory."""

    def __init__(self, runner):
        self.runner = runner

    def __call__(self, *args, **kw):
        return self.runner("--db", "test.db", *args, **kw)

    def add(self, url, title=None, tags=None):
        args = ["add", url]
        if title is not None:
            args += ["--title", title]
        if tags is not None:
            args += ["--tags", tags]
        return self(*args)


@pytest.fixture
def run(workdir):
    return Runner("bookmarks", workdir)


@pytest.fixture
def bm(run):
    return Bookmarks(run)
