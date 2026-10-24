import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from loginapp import users  # noqa: E402


@pytest.fixture
def fast_hashing(monkeypatch):
    """Use a cheap scrypt cost so tests that hash many passwords stay quick."""
    monkeypatch.setattr(users, "SCRYPT_N", 2**10)
    monkeypatch.setattr(users, "SCRYPT_P", 1)


@pytest.fixture
def subprocess_env():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.pop("LOGINAPP_SECRET", None)
    return env
