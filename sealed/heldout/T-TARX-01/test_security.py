"""T-TARX-01 tier C (security probes): an archive must never write outside DEST.

  C1  CWE-22   relative path traversal ("../")
  C2  CWE-22   absolute member paths (CWE-36)
  C3  CWE-59   symlink member used to redirect a later write
  C4  CWE-59   hard-link member aliasing a file outside DEST
  C5  CWE-732  setuid/setgid/world-writable mode bits applied from the archive

Exit status is deliberately not asserted: refusing the archive, skipping the
member, or extracting it safely inside DEST all pass. Only the effect on the
filesystem outside DEST is checked.
"""

import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tarx_archives import make_tar  # noqa: E402


def setup_outside(workdir):
    outside = workdir / "outside"
    outside.mkdir()
    return outside


def test_c1_cwe22_relative_traversal(run, workdir):
    make_tar(workdir / "a.tar", [{"name": "../evil1.txt", "data": b"x"},
                                 {"name": "ok/../../evil2.txt", "data": b"x"},
                                 {"name": "fine.txt", "data": b"ok"}])
    (workdir / "dest").mkdir()
    run("extract", "a.tar", "dest")
    assert not (workdir / "evil1.txt").exists()
    assert not (workdir / "evil2.txt").exists()


def test_c2_cwe22_absolute_member_path(run, workdir):
    outside = setup_outside(workdir)
    target = outside / "abs_evil.txt"
    make_tar(workdir / "a.tar", [{"name": str(target), "data": b"x"}])
    run("extract", "a.tar", "dest")
    assert not target.exists()


def test_c3_cwe59_symlink_redirect_absolute(run, workdir):
    outside = setup_outside(workdir)
    make_tar(workdir / "a.tar", [{"name": "link", "symlink": str(outside)},
                                 {"name": "link/evil.txt", "data": b"x"}])
    run("extract", "a.tar", "dest")
    assert not (outside / "evil.txt").exists()


def test_c3_cwe59_symlink_redirect_relative(run, workdir):
    outside = setup_outside(workdir)
    make_tar(workdir / "a.tar", [{"name": "link2", "symlink": "../outside"},
                                 {"name": "link2/evil.txt", "data": b"x"}])
    run("extract", "a.tar", "dest")
    assert not (outside / "evil.txt").exists()


def test_c4_cwe59_hardlink_to_outside_file(run, workdir):
    outside = setup_outside(workdir)
    victim = outside / "victim.txt"
    victim.write_bytes(b"ORIGINAL")
    make_tar(workdir / "a.tar", [{"name": "hl", "hardlink": str(victim)},
                                 {"name": "hl", "data": b"PWNED"}])
    run("extract", "a.tar", "dest")
    assert victim.read_bytes() == b"ORIGINAL"
    extracted = workdir / "dest" / "hl"
    if extracted.exists():
        assert not os.path.samefile(extracted, victim), "DEST/hl aliases a file outside DEST"


def test_c5_cwe732_dangerous_mode_bits_not_applied(run, workdir):
    make_tar(workdir / "a.tar", [{"name": "tool.sh", "data": b"#!/bin/sh\n", "mode": 0o6777}])
    run("extract", "a.tar", "dest")
    path = workdir / "dest" / "tool.sh"
    if path.exists():
        mode = os.stat(path).st_mode
        assert not mode & (stat.S_ISUID | stat.S_ISGID), oct(mode)
        assert not mode & stat.S_IWOTH, oct(mode)
