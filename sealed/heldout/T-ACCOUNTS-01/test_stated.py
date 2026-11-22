"""T-ACCOUNTS-01 tier A (stated): behaviour written explicitly in the task description."""

import pytest

PASSWORD = "correct horse battery"
OTHER = "wrong password!!"
NEW = "a brand new passphrase"


def test_s1_register_creates_store_and_account(acc, workdir):
    r = acc("register", "alice", PASSWORD)
    assert r.returncode == 0, r
    assert r.stdout.strip() == "registered alice"
    assert (workdir / "users.db").exists()


def test_s2_duplicate_username_exits_3(acc):
    acc("register", "alice", PASSWORD)
    r = acc("register", "alice", PASSWORD)
    assert r.returncode == 3, r


@pytest.mark.parametrize("name", ["ab", "a" * 33, "bad-name", "bad.name", "naïve"])
def test_s3_invalid_username_exits_2(acc, name):
    r = acc("register", name, PASSWORD)
    assert r.returncode == 2, r


@pytest.mark.parametrize("name", ["abc", "a" * 32, "user_1", "UPPER_lower_9"])
def test_s3_valid_usernames_accepted(acc, name):
    r = acc("register", name, PASSWORD)
    assert r.returncode == 0, r


def test_s4_password_length_boundary(acc):
    assert acc("register", "short_pw", "x" * 11).returncode == 2
    assert acc("register", "exact_pw", "x" * 12).returncode == 0


def test_s5_login_success(acc):
    acc("register", "alice", PASSWORD)
    r = acc("login", "alice", PASSWORD)
    assert r.returncode == 0, r
    assert r.stdout.strip() == "ok"


def test_s6_login_wrong_password(acc):
    acc("register", "alice", PASSWORD)
    r = acc("login", "alice", OTHER)
    assert r.returncode == 1, r
    assert "invalid credentials" in r.stderr
    assert "ok" not in r.stdout


def test_s7_lockout_after_five_consecutive_failures(acc):
    acc("register", "alice", PASSWORD)
    for attempt in range(5):
        r = acc("login", "alice", OTHER)
        assert r.returncode == 1, (attempt, r)
    r = acc("login", "alice", PASSWORD)
    assert r.returncode == 4, r
    assert "account locked" in r.stderr


def test_s8_unlock_resets_lock(acc):
    acc("register", "alice", PASSWORD)
    acc.lock("alice")
    r = acc("unlock", "alice")
    assert r.returncode == 0, r
    assert acc("login", "alice", PASSWORD).returncode == 0


def test_s9_passwd_changes_password(acc):
    acc("register", "alice", PASSWORD)
    r = acc("passwd", "alice", PASSWORD, NEW)
    assert r.returncode == 0, r
    assert acc("login", "alice", PASSWORD).returncode == 1
    assert acc("login", "alice", NEW).returncode == 0


def test_s10_passwd_wrong_current(acc):
    acc("register", "alice", PASSWORD)
    r = acc("passwd", "alice", OTHER, NEW)
    assert r.returncode == 1, r
    assert "invalid credentials" in r.stderr
    assert acc("login", "alice", PASSWORD).returncode == 0


def test_s11_passwd_new_too_short(acc):
    acc("register", "alice", PASSWORD)
    r = acc("passwd", "alice", PASSWORD, "tooshort")
    assert r.returncode == 2, r
    assert acc("login", "alice", PASSWORD).returncode == 0


def test_s12_delete_account(acc):
    acc("register", "alice", PASSWORD)
    r = acc("delete", "alice", PASSWORD)
    assert r.returncode == 0, r
    assert acc("login", "alice", PASSWORD).returncode != 0
    assert acc("register", "alice", NEW).returncode == 0


def test_s13_delete_wrong_password(acc):
    acc("register", "alice", PASSWORD)
    r = acc("delete", "alice", OTHER)
    assert r.returncode == 1, r
    assert "invalid credentials" in r.stderr
    assert acc("login", "alice", PASSWORD).returncode == 0


@pytest.mark.parametrize("command,passwords", [("unlock", ()), ("passwd", (PASSWORD, NEW)),
                                               ("delete", (PASSWORD,))])
def test_s14_unknown_user_exits_3(acc, command, passwords):
    acc("register", "alice", PASSWORD)
    r = acc(command, "nobody", *passwords)
    assert r.returncode == 3, r


def test_s15_task_example(acc):
    assert acc("register", "alice", PASSWORD).stdout.strip() == "registered alice"
    assert acc("login", "alice", PASSWORD).stdout.strip() == "ok"
    r = acc("login", "alice", OTHER)
    assert r.returncode == 1 and "invalid credentials" in r.stderr
    assert acc("register", "bob", "short").returncode == 2
