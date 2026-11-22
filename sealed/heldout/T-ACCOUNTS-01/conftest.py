import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import Runner  # noqa: E402

PASSWORD = "correct horse battery"
OTHER = "wrong password!!"


class Accounts:
    def __init__(self, runner, store="users.db"):
        self.runner = runner
        self.store = store

    def __call__(self, command, username, *passwords, store=None):
        stdin = "".join(p + "\n" for p in passwords)
        return self.runner("--store", store or self.store, command, username, input=stdin)

    def lock(self, username):
        for _ in range(5):
            self("login", username, OTHER)


@pytest.fixture
def run(workdir):
    return Runner("accounts", workdir)


@pytest.fixture
def acc(run):
    return Accounts(run)
