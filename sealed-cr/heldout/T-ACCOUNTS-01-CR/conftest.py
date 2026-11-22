import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Runner  # noqa: E402
from accounts_cr_helpers import PASSWORD  # noqa: E402


@pytest.fixture
def run(workdir):
    return Runner("accounts", workdir)


@pytest.fixture
def acct(run):
    """Run an accounts command against users.db; stdin lines are joined with newlines."""
    def call(command, username, *lines, extra=()):
        text = "".join(line + "\n" for line in lines)
        return run("--store", "users.db", command, username, *extra, input=text)
    return call


@pytest.fixture
def alice(acct):
    r = acct("register", "alice", PASSWORD)
    assert r.returncode == 0, r
    return "alice"
