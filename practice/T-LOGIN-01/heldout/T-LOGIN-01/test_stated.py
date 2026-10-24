"""T-LOGIN-01 tier A (stated): behaviour written explicitly in the task description."""

import base64
import hashlib
import hmac
import re
import sys
import time
from email.utils import parsedate_to_datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from login_server import PASSWORD, SECRET, App, decode, make_token  # noqa: E402


def html_ctype(resp):
    return resp.headers.get("content-type", "").replace(" ", "").lower() == "text/html;charset=utf-8"


def test_s1_startup_line(app):
    deadline = time.time() + 5
    while time.time() < deadline and "listening on" not in app.out_path.read_text():
        time.sleep(0.1)
    assert "listening on 127.0.0.1:%d" % app.port in app.out_path.read_text()


def test_s2_refuses_to_start_without_secret(cli):
    assert cli.adduser("alice", PASSWORD).returncode == 0
    try:
        cli.start(secret=None)
    except RuntimeError:
        pass  # exited, as required
    else:
        cli.stop()
        pytest.fail("server started without LOGINAPP_SECRET")
    assert cli.proc.returncode not in (0, None)
    assert cli.err_path.read_text().strip() or cli.out_path.read_text().strip()


def test_s3_adduser(cli, workdir):
    r = cli.adduser("alice", PASSWORD)
    assert r.returncode == 0, r
    assert r.stdout.decode().strip() == "added alice"
    assert (workdir / "users.json").exists()
    assert cli.adduser("alice", PASSWORD).returncode == 3
    assert cli.adduser("shortpw", "x" * 11).returncode == 2
    assert cli.adduser("exactpw", "x" * 12).returncode == 0


@pytest.mark.parametrize("name", ["ab", "a" * 33, "bad-name", "bad name"])
def test_s3_invalid_usernames(cli, name):
    assert cli.adduser(name, PASSWORD).returncode == 2


def test_s4_login_page_has_form(app):
    r = app.request("GET", "/login")
    assert r.status == 200, r
    assert html_ctype(r), r.headers
    page = r.text.lower()
    assert re.search(r"<form[^>]*method=[\"']?post", page), page[:500]
    assert re.search(r"<form[^>]*action=[\"']?/login", page), page[:500]
    assert re.search(r"name=[\"']?username", page)
    assert re.search(r"name=[\"']?password", page)
    assert re.search(r"type=[\"']?password", page)


def test_s5_successful_login_redirects_and_sets_session(app):
    r = app.login()
    assert r.status == 303, r
    assert r.headers.get("location") == "/dashboard", r.headers
    assert r.session().count(".") == 2, r.cookies()


def test_s6_failed_login(app):
    r = app.login("alice", "wrong-password-1")
    assert r.status == 401, r
    assert html_ctype(r), r.headers
    assert "Invalid username or password" in r.text
    token = r.session()
    if token:
        assert app.dashboard(token).status != 200


def test_s7_dashboard_with_session(app):
    r = app.dashboard(app.token())
    assert r.status == 200, r
    assert "Welcome, alice" in r.text
    assert html_ctype(r), r.headers


@pytest.mark.parametrize("token", [None, "not-a-jwt", "a.b.c"])
def test_s8_dashboard_without_valid_session_redirects(app, token):
    r = app.dashboard(token) if token else app.request("GET", "/dashboard")
    assert r.status == 303, r
    assert r.headers.get("location") == "/login", r.headers


def test_s9_token_is_hs256_jwt_with_30_minute_expiry(app):
    token = app.token()
    header, payload = decode(token)
    assert header.get("alg") == "HS256", header
    assert payload.get("sub") == "alice", payload
    assert isinstance(payload.get("iat"), int) and isinstance(payload.get("exp"), int), payload
    assert payload["exp"] - payload["iat"] == 1800, payload
    assert abs(payload["iat"] - time.time()) < 120, payload
    h, p, s = token.split(".")
    expected = base64.urlsafe_b64encode(
        hmac.new(SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    assert s == expected, "token is not signed with HS256 using LOGINAPP_SECRET"


def test_s10_expired_token_rejected(app):
    header, payload = decode(app.token())
    now = int(time.time())
    payload.update(iat=now - 3700, exp=now - 1900)
    r = app.dashboard(make_token(header, payload))
    assert r.status == 303 and r.headers.get("location") == "/login", r


def test_s11_logout_clears_cookie_and_redirects(app):
    r = app.request("POST", "/logout", token=app.token())
    assert r.status == 303, r
    assert r.headers.get("location") == "/login", r.headers
    cookies = r.cookies()
    assert "session" in cookies, "logout did not set a session cookie to clear it"
    value, attrs = cookies["session"]
    cleared = value == "" or "max-age=0" in attrs.replace(" ", "")
    match = re.search(r"expires=([^;]+)", attrs)
    if match:
        try:
            cleared = cleared or parsedate_to_datetime(match.group(1)).timestamp() < time.time()
        except (TypeError, ValueError):
            pass
    assert cleared, cookies["session"]


def test_s12_users_survive_restart(workdir):
    first = App(workdir)
    assert first.adduser("alice", PASSWORD).returncode == 0
    first.start()
    first.stop()
    second = App(workdir).start()
    try:
        assert second.login().status == 303
    finally:
        second.stop()


@pytest.mark.parametrize("path", ["/", "/admin", "/login/extra"])
def test_s13_other_paths_404(app, path):
    assert app.request("GET", path).status == 404


def test_s14_task_example_sequence(app):
    r = app.login()
    assert r.status == 303 and r.headers.get("location") == "/dashboard" and r.session()
    assert "Welcome, alice" in app.dashboard(r.session()).text
    assert app.request("GET", "/dashboard").status == 303
    assert app.login("alice", "wrong-password-1").status == 401
