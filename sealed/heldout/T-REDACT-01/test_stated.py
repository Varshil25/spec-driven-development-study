"""T-REDACT-01 tier A (stated): behaviour written explicitly in the task description.

Every assertion here can be traced to a sentence in TASK.md. Requirement IDs
(S1..S11) match coding/requirements.csv.
"""

import pytest


def test_s1_example_email_and_ip(run):
    r = run(input="user jane@example.com from 10.0.0.7\n")
    assert r.returncode == 0, r
    assert r.stdout == "user [EMAIL] from [IP]\n"


def test_s2_example_card_and_non_luhn_number(run):
    r = run(input="paid with 4111 1111 1111 1111, ref 1234567890123\n")
    assert r.returncode == 0, r
    assert r.stdout == "paid with [CARD], ref 1234567890123\n"


def test_s3_example_count(run):
    r = run("--count", input="a@b.io 1.2.3.4\n")
    assert r.returncode == 0, r
    assert r.stdout == "[EMAIL] [IP]\n"
    assert "emails=1 ips=1 cards=0" in r.stderr


@pytest.mark.parametrize("email", [
    "jane.doe+test@mail.example.com",
    "JOHN_SMITH@Example.ORG",
    "x@sub.domain.co.uk",
])
def test_s4_email_forms(run, email):
    r = run(input="contact %s today\n" % email)
    assert r.stdout == "contact [EMAIL] today\n", r


@pytest.mark.parametrize("ip", ["0.0.0.0", "255.255.255.255", "192.168.0.10", "8.8.4.4"])
def test_s5_valid_ipv4_redacted(run, ip):
    r = run(input="host %s up\n" % ip)
    assert r.stdout == "host [IP] up\n", r


@pytest.mark.parametrize("not_ip", ["999.1.1.1", "256.10.10.10", "1.2.3.300"])
def test_s5_out_of_range_numbers_not_ip(run, not_ip):
    r = run(input="host %s up\n" % not_ip)
    assert r.stdout == "host %s up\n" % not_ip, r


@pytest.mark.parametrize("card", [
    "4111111111111111",          # 16 digits, no separators
    "4111-1111-1111-1111",       # hyphen groups
    "5555 5555 5555 4444",       # space groups
    "378282246310005",           # 15 digits (Amex test number)
    "30569309025904",            # 14 digits (Diners test number)
])
def test_s6_luhn_valid_cards_redacted(run, card):
    r = run(input="card %s ok\n" % card)
    assert r.stdout == "card [CARD] ok\n", r


@pytest.mark.parametrize("number", ["4111111111111112", "1234567890123"])
def test_s6_luhn_invalid_numbers_unchanged(run, number):
    r = run(input="order %s shipped\n" % number)
    assert r.stdout == "order %s shipped\n" % number, r


def test_s7_lines_without_matches_are_unchanged(run):
    text = "hello world  \n\nno secrets here, just text: 12-34 and 1.5\n\ttabbed line\n"
    r = run(input=text)
    assert r.returncode == 0, r
    assert r.stdout == text


def test_s8_files_processed_in_order(run, workdir):
    (workdir / "a.log").write_text("first a@x.io\n")
    (workdir / "b.log").write_text("second 10.0.0.1\n")
    r = run("a.log", "b.log")
    assert r.returncode == 0, r
    assert r.stdout == "first [EMAIL]\nsecond [IP]\n"


def test_s8_stdin_used_when_no_files(run):
    r = run(input="only stdin c@d.ee\n")
    assert r.stdout == "only stdin [EMAIL]\n", r


def test_s9_unreadable_file_reports_and_exits_2(run):
    r = run("does-not-exist.log")
    assert r.returncode == 2, r
    assert "does-not-exist.log" in r.stderr


def test_s10_count_totals_and_stream(run):
    r = run("--count", input="a@x.io b@y.io 10.0.0.1 4111111111111111\n")
    assert r.returncode == 0, r
    assert r.stdout == "[EMAIL] [EMAIL] [IP] [CARD]\n"
    assert "emails=2 ips=1 cards=1" in r.stderr
    assert "emails=" not in r.stdout


def test_s11_count_absent_without_flag(run):
    r = run(input="a@x.io\n")
    assert "emails=" not in r.stderr and "emails=" not in r.stdout
