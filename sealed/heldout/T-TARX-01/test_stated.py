"""T-TARX-01 tier A (stated): behaviour written explicitly in the task description."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tarx_archives import make_tar  # noqa: E402


def files(*pairs):
    return [{"name": n, "data": d} for n, d in pairs]


def test_s1_list_prints_members_in_archive_order(run, workdir):
    make_tar(workdir / "a.tar", files(("z.txt", b"z"), ("dir/b.txt", b"b"), ("m.txt", b"m")))
    r = run("list", "a.tar")
    assert r.returncode == 0, r
    assert r.stdout.splitlines() == ["z.txt", "dir/b.txt", "m.txt"]


def test_s2_extract_writes_files_with_paths_and_contents(run, workdir):
    make_tar(workdir / "a.tar", files(("top.txt", b"top\n"), ("x/y/deep.txt", b"deep\n"),
                                      ("x/side.txt", b"side\n")))
    r = run("extract", "a.tar", "out")
    assert r.returncode == 0, r
    assert (workdir / "out" / "top.txt").read_bytes() == b"top\n"
    assert (workdir / "out" / "x" / "y" / "deep.txt").read_bytes() == b"deep\n"
    assert (workdir / "out" / "x" / "side.txt").read_bytes() == b"side\n"
    assert r.stdout.strip() == "extracted 3 files"


def test_s3_directories_are_created_and_not_counted(run, workdir):
    make_tar(workdir / "a.tar", [{"name": "emptydir", "dir": True},
                                 {"name": "docs", "dir": True},
                                 {"name": "docs/readme.md", "data": b"# hi\n"},
                                 {"name": "notes.txt", "data": b"n"}])
    r = run("extract", "a.tar", "out")
    assert r.returncode == 0, r
    assert (workdir / "out" / "emptydir").is_dir()
    assert (workdir / "out" / "docs" / "readme.md").read_bytes() == b"# hi\n"
    assert r.stdout.strip() == "extracted 2 files"


@pytest.mark.parametrize("filename", ["a.tar.gz", "a.tgz"])
def test_s4_gzip_archives_list_and_extract(run, workdir, filename):
    make_tar(workdir / filename, files(("one.txt", b"1"), ("two/two.txt", b"22")), compression="gz")
    r = run("list", filename)
    assert r.returncode == 0, r
    assert r.stdout.splitlines() == ["one.txt", "two/two.txt"]
    r = run("extract", filename, "out")
    assert r.returncode == 0, r
    assert (workdir / "out" / "two" / "two.txt").read_bytes() == b"22"


def test_s5_existing_file_not_overwritten_without_flag(run, workdir):
    make_tar(workdir / "a.tar", files(("keep.txt", b"from archive")))
    (workdir / "out").mkdir()
    (workdir / "out" / "keep.txt").write_bytes(b"original")
    r = run("extract", "a.tar", "out")
    assert r.returncode == 3, r
    assert r.stderr.strip(), "expected an error message on stderr"
    assert (workdir / "out" / "keep.txt").read_bytes() == b"original"


def test_s6_overwrite_flag_replaces_existing_file(run, workdir):
    make_tar(workdir / "a.tar", files(("keep.txt", b"from archive")))
    (workdir / "out").mkdir()
    (workdir / "out" / "keep.txt").write_bytes(b"original")
    r = run("extract", "a.tar", "out", "--overwrite")
    assert r.returncode == 0, r
    assert (workdir / "out" / "keep.txt").read_bytes() == b"from archive"


@pytest.mark.parametrize("command", [["list", "missing.tar"], ["extract", "missing.tar", "out"]])
def test_s7_missing_archive_exits_2(run, command):
    r = run(*command)
    assert r.returncode == 2, r
    assert r.stderr.strip()


@pytest.mark.parametrize("command", [["list", "junk.tar"], ["extract", "junk.tar", "out"]])
def test_s8_invalid_archive_exits_2(run, workdir, command):
    (workdir / "junk.tar").write_bytes(os.urandom(4096))
    r = run(*command)
    assert r.returncode == 2, r
    assert r.stderr.strip()


def test_s9_task_example(run, workdir):
    make_tar(workdir / "photos.tar.gz",
             files(("photos/a.jpg", b"\xff\xd8a"), ("photos/b.jpg", b"\xff\xd8b")),
             compression="gz")
    r = run("list", "photos.tar.gz")
    assert r.stdout.splitlines() == ["photos/a.jpg", "photos/b.jpg"], r
    r = run("extract", "photos.tar.gz", "out")
    assert r.returncode == 0 and r.stdout.strip() == "extracted 2 files", r
    r = run("extract", "photos.tar.gz", "out")
    assert r.returncode == 3, r


def test_s10_binary_content_preserved(run, workdir):
    blob = bytes(range(256)) * 64
    make_tar(workdir / "a.tar", files(("bin.dat", blob)))
    r = run("extract", "a.tar", "out")
    assert r.returncode == 0, r
    assert (workdir / "out" / "bin.dat").read_bytes() == blob
