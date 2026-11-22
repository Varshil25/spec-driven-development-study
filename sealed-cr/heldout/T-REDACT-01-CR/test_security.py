"""T-REDACT-01-CR tier C (security probes), each mapped to a CWE.

  C1  CWE-59    Link following: a symbolic or hard link already sitting in the
                output folder under an output file's name must not redirect
                the write onto another file.
  C2  CWE-1333  Inefficient regular expressions: a long line of '+' and digits
                must not make the tool run for minutes.
  C3  CWE-532   Sensitive data left in output: phone numbers embedded in
                ordinary log syntax must still be redacted.
"""

import os

import pytest

LONG = 200_000
TIME_LIMIT = 10  # seconds; the reference needs well under one second


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_c1_cwe59_planted_link_in_out_dir_is_not_followed(run, workdir, kind):
    victim = workdir / "victim.txt"
    victim.write_text("precious data\n")
    out = workdir / "out"
    out.mkdir()
    if kind == "symlink":
        os.symlink(victim, out / "app.log")
    else:
        os.link(victim, out / "app.log")
    (workdir / "app.log").write_text("user a@b.io\n")
    r = run("--out-dir", "out", "app.log")
    assert victim.read_text() == "precious data\n", r


# Runs of "+" and digits are kept short or start once, so that the probe tests
# the new phone pattern rather than the e-mail pattern the change leaves alone.
SHAPES = ["+1 ", "+12345678901234567890 ", "+" + "1" * (LONG - 1)]


@pytest.mark.parametrize("shape", SHAPES, ids=["plus-one", "plus-twenty-digits", "plus-long-run"])
def test_c2_cwe1333_long_plus_digit_line_completes(run, shape):
    line = shape * max(1, LONG // len(shape))
    r = run(input=line + "\n", timeout=TIME_LIMIT)
    assert r.returncode == 0, r


EMBEDDED = [
    '{"phone":"+14155552671","user":"x"}',
    "tel=+14155552671;user=x",
    "<+14155552671>",
    "callback:+14155552671,retry",
]


@pytest.mark.parametrize("line", EMBEDDED)
def test_c3_cwe532_embedded_phone_is_redacted(run, line):
    r = run(input=line + "\n")
    assert r.returncode == 0, r
    assert "14155552671" not in r.stdout, r
