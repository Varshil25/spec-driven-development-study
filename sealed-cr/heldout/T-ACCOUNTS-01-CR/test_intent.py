"""T-ACCOUNTS-01-CR tier B (intent): answers in operator/answer-sheets/T-ACCOUNTS-01-CR.md."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from accounts_cr_helpers import NEW_PASSWORD, PASSWORD  # noqa: E402


def test_i1_reset_unlocks_a_locked_account(acct, alice):
    for _ in range(5):
        acct("login", alice, "wrong password!!")
    assert acct("login", alice, PASSWORD).returncode == 4
    token = acct("reset-token", alice).stdout.strip()
    r = acct("reset", alice, token, NEW_PASSWORD)
    assert r.returncode == 0, r
    login = acct("login", alice, NEW_PASSWORD)
    assert login.returncode == 0, login


def test_i2_a_new_token_cancels_the_old_one(acct, alice):
    first = acct("reset-token", alice).stdout.strip()
    second = acct("reset-token", alice).stdout.strip()
    old = acct("reset", alice, first, NEW_PASSWORD)
    assert old.returncode == 1, old
    new = acct("reset", alice, second, NEW_PASSWORD)
    assert new.returncode == 0, new


def test_i3_passwd_cancels_an_outstanding_token(acct, alice):
    token = acct("reset-token", alice).stdout.strip()
    changed = acct("passwd", alice, PASSWORD, "changed password 1")
    assert changed.returncode == 0, changed
    r = acct("reset", alice, token, NEW_PASSWORD)
    assert r.returncode == 1, r
