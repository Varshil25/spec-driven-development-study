"""T-TARX-01-CR tier B (intent): answers in operator/answer-sheets/T-TARX-01-CR.md."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tarx_cr_helpers import names  # noqa: E402


def test_i1_members_are_in_sorted_order(run, workdir):
    (workdir / "d" / "b").mkdir(parents=True)
    for rel in ["d/z.txt", "d/a.txt", "d/b/y.txt", "d/b/c.txt"]:
        (workdir / rel).write_text(rel)
    r = run("create", "d.tar", "d")
    assert r.returncode == 0, r
    listed = names(workdir / "d.tar")
    files = [n for n in listed if n.endswith(".txt")]
    assert files == ["d/a.txt", "d/b/c.txt", "d/b/y.txt", "d/z.txt"], listed
    assert listed.index("d") < listed.index("d/a.txt")
    assert listed.index("d/b") < listed.index("d/b/c.txt")


def test_i2_empty_directories_are_included(run, workdir):
    (workdir / "d" / "empty").mkdir(parents=True)
    (workdir / "d" / "f.txt").write_text("x")
    r = run("create", "d.tar", "d")
    assert r.returncode == 0, r
    assert "d/empty" in names(workdir / "d.tar")


def test_i3_hidden_files_are_included(run, workdir):
    (workdir / "d").mkdir()
    (workdir / "d" / ".config").write_text("x")
    r = run("create", "d.tar", "d")
    assert r.returncode == 0, r
    assert "d/.config" in names(workdir / "d.tar")
