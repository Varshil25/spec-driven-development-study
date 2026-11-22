"""T-TARX-01 tier B (intent): points the task description leaves open.
Answers: operator/answer-sheets/T-TARX-01.md."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tarx_archives import make_tar  # noqa: E402


def test_i1_missing_destination_is_created(run, workdir):
    make_tar(workdir / "a.tar", [{"name": "f.txt", "data": b"x"}])
    r = run("extract", "a.tar", "new/nested/dest")
    assert r.returncode == 0, r
    assert (workdir / "new" / "nested" / "dest" / "f.txt").read_bytes() == b"x"


def test_i2_conflict_extracts_nothing(run, workdir):
    make_tar(workdir / "a.tar", [{"name": "first.txt", "data": b"1"},
                                 {"name": "clash.txt", "data": b"2"},
                                 {"name": "last.txt", "data": b"3"}])
    (workdir / "out").mkdir()
    (workdir / "out" / "clash.txt").write_bytes(b"mine")
    r = run("extract", "a.tar", "out")
    assert r.returncode == 3, r
    assert not (workdir / "out" / "first.txt").exists(), "partial extraction before the conflict"
    assert not (workdir / "out" / "last.txt").exists()


def test_i3_modification_times_preserved(run, workdir):
    make_tar(workdir / "a.tar", [{"name": "old.txt", "data": b"x", "mtime": 1_000_000_000}])
    r = run("extract", "a.tar", "out")
    assert r.returncode == 0, r
    assert int(os.stat(workdir / "out" / "old.txt").st_mtime) == 1_000_000_000
