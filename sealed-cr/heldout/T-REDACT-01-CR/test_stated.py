"""T-REDACT-01-CR tier A (stated): behaviour written in the change request.

Regression of the original behaviour is measured separately, by running the
original T-REDACT-01 suite against the same repository.
"""

import pytest

# The literal format is pinned by the worked example ("wrote 2 files"); for
# N = 1 the grammatical singular is accepted too.
ONE_FILE = ("wrote 1 files\n", "wrote 1 file\n")


def test_s1_example_phone(run):
    r = run(input="call +14155552671 now\n")
    assert r.returncode == 0, r
    assert r.stdout == "call [PHONE] now\n", r


def test_s2_example_count_with_phones(run):
    r = run("--count", input="a@b.io +442071838750\n")
    assert r.returncode == 0, r
    assert r.stdout == "[EMAIL] [PHONE]\n", r
    assert "emails=1 ips=0 cards=0 phones=1" in r.stderr, r


def test_s3_example_out_dir(run, workdir):
    (workdir / "app.log").write_text("user jane@example.com\n")
    (workdir / "web.log").write_text("GET / from 10.0.0.7\n")
    r = run("--out-dir", "clean", "app.log", "web.log")
    assert r.returncode == 0, r
    assert r.stdout == "wrote 2 files\n", r
    assert (workdir / "clean" / "app.log").read_text() == "user [EMAIL]\n"
    assert (workdir / "clean" / "web.log").read_text() == "GET / from [IP]\n"


@pytest.mark.parametrize("text,expected", [
    ("tel +12345678 end", "tel [PHONE] end"),                  # 8 digits
    ("tel +123456789012345 end", "tel [PHONE] end"),           # 15 digits
    ("tel +1234567 end", "tel +1234567 end"),                  # 7 digits: too short
    ("tel +1234567890123456 end", "tel +1234567890123456 end"),  # 16 digits: too long, fails Luhn
])
def test_s4_phone_length_limits(run, text, expected):
    r = run(input=text + "\n")
    assert r.returncode == 0, r
    assert r.stdout == expected + "\n", r


def test_s5_phone_alongside_other_values(run):
    r = run(input="from 10.0.0.7 jane@example.com tel +4930123456\n")
    assert r.stdout == "from [IP] [EMAIL] tel [PHONE]\n", r


def test_s6_out_dir_is_created_with_parents(run, workdir):
    (workdir / "x.log").write_text("ip 10.1.1.1\n")
    r = run("--out-dir", "a/b/c", "x.log")
    assert r.returncode == 0, r
    assert (workdir / "a" / "b" / "c" / "x.log").read_text() == "ip [IP]\n"


def test_s7_existing_output_file_is_replaced(run, workdir):
    (workdir / "out").mkdir()
    (workdir / "out" / "x.log").write_text("old content that must disappear\n")
    (workdir / "x.log").write_text("mail a@b.io\n")
    r = run("--out-dir", "out", "x.log")
    assert r.returncode == 0, r
    assert (workdir / "out" / "x.log").read_text() == "mail [EMAIL]\n"


def test_s8_out_dir_prints_only_the_summary_line(run, workdir):
    (workdir / "x.log").write_text("mail a@b.io\nplain line\n")
    r = run("--out-dir", "out", "x.log")
    assert r.stdout in ONE_FILE, r


def test_s9_output_name_drops_the_input_directories(run, workdir):
    (workdir / "nested" / "deep").mkdir(parents=True)
    (workdir / "nested" / "deep" / "app.log").write_text("a@b.io\n")
    r = run("--out-dir", "out", "nested/deep/app.log")
    assert r.returncode == 0, r
    assert (workdir / "out" / "app.log").read_text() == "[EMAIL]\n"
    assert not (workdir / "out" / "nested").exists()


def test_s10_unreadable_file_with_out_dir(run, workdir):
    (workdir / "a.log").write_text("a@b.io\n")
    r = run("--out-dir", "out", "a.log", "missing.log")
    assert r.returncode == 2, r
    assert "missing.log" in r.stderr, r
    assert (workdir / "out" / "a.log").read_text() == "[EMAIL]\n"
    # The text does not say whether the summary is printed on a run that fails.
    assert r.stdout in ONE_FILE + ("",), r


def test_s11_count_line_reports_phones_even_when_zero(run):
    r = run("--count", input="nothing here\n")
    assert r.returncode == 0, r
    assert "emails=0 ips=0 cards=0 phones=0" in r.stderr, r


def test_s12_count_with_out_dir_goes_to_stderr(run, workdir):
    (workdir / "x.log").write_text("+14155552671 a@b.io\n")
    r = run("--count", "--out-dir", "out", "x.log")
    assert r.returncode == 0, r
    assert r.stdout in ONE_FILE, r
    assert "emails=1 ips=0 cards=0 phones=1" in r.stderr, r
    assert (workdir / "out" / "x.log").read_text() == "[PHONE] [EMAIL]\n"
