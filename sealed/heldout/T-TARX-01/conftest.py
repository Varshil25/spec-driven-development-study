import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import Runner  # noqa: E402


@pytest.fixture
def run(workdir):
    return Runner("tarx", workdir)
