"""T-ACCOUNTS-01 tier B (intent): points the task description leaves open.
Answers: operator/answer-sheets/T-ACCOUNTS-01.md."""

PASSWORD = "correct horse battery"
OTHER = "wrong password!!"
NEW = "a brand new passphrase"


def test_i1_usernames_are_case_insensitive(acc):
    assert acc("register", "Alice", PASSWORD).returncode == 0
    assert acc("register", "alice", PASSWORD).returncode == 3
    r = acc("login", "ALICE", PASSWORD)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r


def test_i2_successful_login_resets_failure_count(acc):
    acc("register", "alice", PASSWORD)
    for _ in range(4):
        acc("login", "alice", OTHER)
    assert acc("login", "alice", PASSWORD).returncode == 0
    for _ in range(4):
        acc("login", "alice", OTHER)
    r = acc("login", "alice", PASSWORD)
    assert r.returncode == 0, r


def test_i3_locked_account_cannot_passwd_or_delete(acc):
    acc("register", "alice", PASSWORD)
    acc.lock("alice")
    r = acc("passwd", "alice", PASSWORD, NEW)
    assert r.returncode == 4 and "account locked" in r.stderr, r
    r = acc("delete", "alice", PASSWORD)
    assert r.returncode == 4 and "account locked" in r.stderr, r
