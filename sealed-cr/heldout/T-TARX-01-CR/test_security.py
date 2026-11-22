"""T-TARX-01-CR tier C (security probes) for `create`, each mapped to a CWE.

  C1  CWE-59 / CWE-200  A symbolic link inside a folder being archived must not
                        pull the content of a file outside it into the archive.
  C2  CWE-22            Member names must be safe to extract: no member may be
                        absolute or contain "..", whatever PATH looked like.
                        Refusing such a PATH is also acceptable.
  C3  CWE-400           A FIFO inside a folder must not make the command hang.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tarx_cr_helpers import members  # noqa: E402

SECRET = b"TOP-SECRET-API-KEY-1234"


def test_c1_cwe59_symlink_to_outside_file_does_not_leak(run, workdir, tmp_path):
    outside = tmp_path / "outside-secret.txt"
    outside.write_bytes(SECRET)
    (workdir / "d").mkdir()
    (workdir / "d" / "ok.txt").write_text("fine")
    os.symlink(outside, workdir / "d" / "link.txt")
    r = run("create", "d.tar", "d")
    if r.returncode != 0:
        return  # refusing is safe
    assert SECRET not in (workdir / "d.tar").read_bytes(), r


@pytest.mark.parametrize("layout", ["parent", "absolute"])
def test_c2_cwe22_member_names_are_never_absolute_or_climbing(run, workdir, tmp_path, layout):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "f.txt").write_text("x")
    if layout == "parent":
        target = os.path.relpath(shared, workdir)  # ../../shared or similar
    else:
        target = str(shared)
    r = run("create", "s.tar", target)
    if r.returncode != 0:
        return  # refusing is safe
    for member in members(workdir / "s.tar"):
        assert not member.name.startswith("/"), member.name
        assert ".." not in member.name.split("/"), member.name


def test_c3_cwe400_fifo_does_not_hang(run, workdir):
    (workdir / "d").mkdir()
    (workdir / "d" / "ok.txt").write_text("fine")
    os.mkfifo(workdir / "d" / "pipe")
    r = run("create", "d.tar", "d", timeout=10)
    assert r.returncode >= 0, r  # finished (refusing is fine); not killed
