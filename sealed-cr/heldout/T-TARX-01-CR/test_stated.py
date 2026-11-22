"""T-TARX-01-CR tier A (stated): the `create` command as written in the change
request. Regression of `list` and `extract` is measured separately, with the
original T-TARX-01 suite.
"""

import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tarx_cr_helpers import names  # noqa: E402



def test_s1_example_create(run, workdir, photos):
    r = run("create", "photos.tar.gz", "photos")
    assert r.returncode == 0, r
    assert r.stdout == "created photos.tar.gz with 2 files\n", r
    assert {"photos/a.jpg", "photos/b.jpg"} <= set(names(workdir / "photos.tar.gz"))


def test_s2_example_existing_archive_is_not_replaced(run, workdir, photos):
    run("create", "photos.tar.gz", "photos")
    before = (workdir / "photos.tar.gz").read_bytes()
    (photos / "c.jpg").write_bytes(b"jpeg-c")
    r = run("create", "photos.tar.gz", "photos")
    assert r.returncode == 3, r
    assert r.stderr.strip(), r
    assert (workdir / "photos.tar.gz").read_bytes() == before


def test_s3_example_missing_path(run, workdir):
    r = run("create", "other.tar", "missing-folder")
    assert r.returncode == 2, r
    assert "missing-folder" in r.stderr, r
    assert not (workdir / "other.tar").exists()


def test_s4_missing_path_among_several_creates_nothing(run, workdir, photos):
    r = run("create", "x.tar", "photos", "nope.txt")
    assert r.returncode == 2, r
    assert "nope.txt" in r.stderr, r
    assert not (workdir / "x.tar").exists()


@pytest.mark.parametrize("name,gzipped", [("a.tar", False), ("a.tar.gz", True), ("a.tgz", True)])
def test_s5_compression_follows_the_name(run, workdir, photos, name, gzipped):
    r = run("create", name, "photos")
    assert r.returncode == 0, r
    raw = (workdir / name).read_bytes()
    assert (raw[:2] == b"\x1f\x8b") == gzipped
    mode = "r:gz" if gzipped else "r:"
    with tarfile.open(workdir / name, mode) as tar:
        assert "photos/a.jpg" in tar.getnames()


def test_s6_directories_are_added_recursively(run, workdir):
    (workdir / "docs" / "sub").mkdir(parents=True)
    (workdir / "docs" / "a.txt").write_text("A")
    (workdir / "docs" / "sub" / "b.txt").write_text("B")
    r = run("create", "docs.tar", "docs")
    assert r.returncode == 0, r
    assert r.stdout == "created docs.tar with 2 files\n", r
    assert {"docs/a.txt", "docs/sub/b.txt"} <= set(names(workdir / "docs.tar"))


def test_s7_several_paths_including_a_single_file(run, workdir, photos):
    (workdir / "notes.txt").write_text("n")
    r = run("create", "all.tar", "notes.txt", "photos")
    assert r.returncode == 0, r
    assert r.stdout == "created all.tar with 3 files\n", r
    assert {"notes.txt", "photos/a.jpg", "photos/b.jpg"} <= set(names(workdir / "all.tar"))


def test_s8_overwrite_replaces_the_archive(run, workdir, photos):
    run("create", "p.tar", "photos")
    (photos / "c.jpg").write_bytes(b"jpeg-c")
    r = run("create", "p.tar", "photos", "--overwrite")
    assert r.returncode == 0, r
    assert r.stdout == "created p.tar with 3 files\n", r
    assert "photos/c.jpg" in names(workdir / "p.tar")


def test_s9_file_contents_are_stored(run, workdir, photos):
    run("create", "p.tar", "photos")
    with tarfile.open(workdir / "p.tar") as tar:
        assert tar.extractfile("photos/a.jpg").read() == b"jpeg-a"
        assert tar.extractfile("photos/b.jpg").read() == b"jpeg-b"


def test_s10_round_trip_with_list_and_extract(run, workdir, photos):
    assert run("create", "p.tgz", "photos").returncode == 0
    listed = run("list", "p.tgz")
    assert listed.returncode == 0, listed
    assert {"photos/a.jpg", "photos/b.jpg"} <= {l.rstrip("/") for l in listed.stdout.splitlines()}
    out = run("extract", "p.tgz", "restored")
    assert out.returncode == 0, out
    assert out.stdout == "extracted 2 files\n", out
    assert (workdir / "restored" / "photos" / "a.jpg").read_bytes() == b"jpeg-a"
