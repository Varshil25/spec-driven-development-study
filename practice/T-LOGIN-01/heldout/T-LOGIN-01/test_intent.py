"""T-LOGIN-01 tier B (intent): points the task description leaves open.
Answers: operator/answer-sheets/T-LOGIN-01.md."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from login_server import PASSWORD, App  # noqa: E402


def test_i1_lockout_after_five_failures(app):
    for _ in range(5):
        assert app.login("alice", "wrong-password-1").status == 401
    r = app.login("alice", PASSWORD)
    assert r.status == 401, r
    assert not r.session() or app.dashboard(r.session()).status != 200


def test_i2_logout_revokes_the_token(app):
    token = app.token()
    assert app.dashboard(token).status == 200
    app.request("POST", "/logout", token=token)
    r = app.dashboard(token)
    assert r.status == 303, "a copied token still works after logout: %r" % r


def test_i3_usernames_case_insensitive(workdir):
    a = App(workdir)
    assert a.adduser("Alice", PASSWORD).returncode == 0
    assert a.adduser("alice", PASSWORD).returncode == 3
    a.start()
    try:
        r = a.login("alice", PASSWORD)
        assert r.status == 303, r
        assert "Welcome, Alice" in a.dashboard(r.session()).text
    finally:
        a.stop()


def test_i4_login_page_redirects_when_logged_in(app):
    r = app.request("GET", "/login", token=app.token())
    assert r.status == 303 and r.headers.get("location") == "/dashboard", r
