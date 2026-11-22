"""T-ACCOUNTS-01-CR tier A (stated): password reset as written in the change
request. Regression of the existing commands is measured separately, with the
original T-ACCOUNTS-01 suite.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from accounts_cr_helpers import NEW_PASSWORD, PASSWORD  # noqa: E402


def token_for(acct, user, extra=()):
    r = acct("reset-token", user, extra=extra)
    assert r.returncode == 0, r
    return r.stdout.strip()


def test_s1_reset_with_a_token(acct, alice):
    token = token_for(acct, alice)
    assert token
    r = acct("reset", alice, token, NEW_PASSWORD)
    assert r.returncode == 0, r
    assert r.stdout == "password reset\n", r
    assert acct("login", alice, NEW_PASSWORD).returncode == 0
    old = acct("login", alice, PASSWORD)
    assert old.returncode == 1, old


def test_s2_a_token_works_only_once(acct, alice):
    token = token_for(acct, alice)
    assert acct("reset", alice, token, NEW_PASSWORD).returncode == 0
    again = acct("reset", alice, token, "another new password")
    assert again.returncode == 1, again
    assert "invalid token" in again.stderr, again
    assert acct("login", alice, NEW_PASSWORD).returncode == 0


def test_s3_wrong_token(acct, alice):
    token_for(acct, alice)
    r = acct("reset", alice, "not-the-token", NEW_PASSWORD)
    assert r.returncode == 1, r
    assert "invalid token" in r.stderr, r
    assert acct("login", alice, PASSWORD).returncode == 0


def test_s4_token_expires_after_ttl(acct, alice):
    token = token_for(acct, alice, extra=("--ttl", "1"))
    time.sleep(2.2)
    r = acct("reset", alice, token, NEW_PASSWORD)
    assert r.returncode == 1, r
    assert "invalid token" in r.stderr, r
    assert acct("login", alice, PASSWORD).returncode == 0


def test_s5_short_password_keeps_the_token_usable(acct, alice):
    token = token_for(acct, alice)
    short = acct("reset", alice, token, "short")
    assert short.returncode == 2, short
    ok = acct("reset", alice, token, NEW_PASSWORD)
    assert ok.returncode == 0, ok


def test_s6_unknown_user(acct, alice):
    r = acct("reset-token", "nobody")
    assert r.returncode == 3, r
    r = acct("reset", "nobody", "whatever", NEW_PASSWORD)
    assert r.returncode == 3, r


def test_s7_reset_token_prints_one_line(acct, alice):
    r = acct("reset-token", alice)
    assert r.returncode == 0, r
    lines = r.stdout.splitlines()
    assert len(lines) == 1 and lines[0].strip(), r
