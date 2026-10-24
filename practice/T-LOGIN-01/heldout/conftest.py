"""Root conftest: shared fixtures. The harness itself lives in harness.py."""

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture
def workdir(tmp_path):
    path = tmp_path / "work"
    path.mkdir()
    yield path
    shutil.rmtree(path, ignore_errors=True)
