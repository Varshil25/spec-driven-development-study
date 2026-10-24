"""The HTTP server, run in a background thread and driven with http.client."""

import http.client
import re
import threading
import time
import urllib.parse

import pytest

from loginapp import pages, server, tokens, users

SECRET = b"server-test-secret"
PASSWORD = "correct-horse-battery"
HTML = "text/html; charset=utf-8"


@pytest.fixture
def users_path(tmp_path, fast_hashing):
    path = tmp_path / "users.json"
    users.add_user(path, "alice", PASSWORD)
    return path


@pytest.fixture
def app(users_path):
    return server.App(users_path, SECRET)


@pytest.fixture
def port(app):
    httpd = server.LoginServer(("127.0.0.1", 0), app)
    thread = threading.Thread(target=httpd.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=10)


class Response:
    def __init__(self, raw: http.client.HTTPResponse):
        self.status = raw.status
        self.headers = raw.headers
        self.body = raw.read().decode("utf-8")

    @property
    def cookie(self) -> str:
        return self.headers["Set-Cookie"]

    @property
    def token(self) -> str:
        match = re.match(r"session=([^;]*);", self.cookie)
        assert match, self.cookie
        return match.group(1)


def request(port, method, path, body=None, headers=None, cookie=None):
    headers = dict(headers or {})
    if cookie is not None:
        headers["Cookie"] = cookie
    if isinstance(body, dict):
        body = urllib.parse.urlencode(body)
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(method, path, body=body, headers=headers)
        return Response(conn.getresponse())
    finally:
        conn.close()


def login(port, username="alice", password=PASSWORD, **kwargs):
    return request(port, "POST", "/login", {"username": username, "password": password}, **kwargs)


# -- GET /login ---------------------------------------------------------------

def test_login_page_has_form(port):
    response = request(port, "GET", "/login")
    assert response.status == 200
    assert response.headers["Content-Type"] == HTML
    assert re.search(r'<form[^>]*method="post"[^>]*action="/login"', response.body)
    assert 'name="username"' in response.body
    assert re.search(r'name="password"[^>]*type="password"|type="password"[^>]*name="password"', response.body)
    assert pages.INVALID_CREDENTIALS not in response.body


def test_security_headers(port):
    response = request(port, "GET", "/login")
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert "Python" not in response.headers["Server"]


def test_head_login_has_no_body(port):
    response = request(port, "HEAD", "/login")
    assert response.status == 200
    assert response.body == ""


# -- POST /login ----------------------------------------------------------------

def test_successful_login_redirects_and_sets_session(port):
    before = int(time.time())
    response = login(port)
    after = int(time.time())
    assert response.status == 303
    assert response.headers["Location"] == "/dashboard"
    attributes = [part.strip().lower() for part in response.cookie.split(";")]
    assert "httponly" in attributes
    assert "samesite=strict" in attributes
    assert "path=/" in attributes
    claims = tokens.verify(response.token, SECRET)
    assert claims["sub"] == "alice"
    assert before <= claims["iat"] <= after
    assert claims["exp"] == claims["iat"] + 1800


@pytest.mark.parametrize("username,password", [
    ("alice", "wrong-password-1"),
    ("mallory", PASSWORD),
    ("alice", ""),
    ("", ""),
    ("ALICE", PASSWORD),
    ("bad-name!", PASSWORD),
])
def test_failed_login_is_401_with_message(port, username, password):
    response = login(port, username, password)
    assert response.status == 401
    assert response.headers["Content-Type"] == HTML
    assert pages.INVALID_CREDENTIALS in response.body
    assert "<form" in response.body
    assert "Set-Cookie" not in response.headers


def test_missing_fields_is_401(port):
    for body in ("", "username=alice", "password=" + PASSWORD):
        response = request(port, "POST", "/login", body,
                           {"Content-Type": "application/x-www-form-urlencoded"})
        assert response.status == 401
        assert pages.INVALID_CREDENTIALS in response.body


def test_repeated_fields_are_not_accepted(port):
    body = f"username=alice&username=bob&password={PASSWORD}"
    response = request(port, "POST", "/login", body, {"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status == 401


def test_login_without_content_type_is_accepted(port):
    # e.g. `curl -d` always sends one, but other simple clients may not.
    response = request(port, "POST", "/login", f"username=alice&password={PASSWORD}")
    assert response.status == 303


def test_login_with_json_body_is_rejected(port):
    response = request(port, "POST", "/login", '{"username": "alice"}', {"Content-Type": "application/json"})
    assert response.status == 415


def test_oversized_body_is_rejected(port):
    response = request(port, "POST", "/login", "a" * (server.MAX_BODY_BYTES + 1),
                       {"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status == 413


def test_password_with_special_characters(tmp_path, fast_hashing):
    path = tmp_path / "users.json"
    password = "p&ss=wörd +%20 ünïcode"
    users.add_user(path, "bob", password)
    httpd = server.LoginServer(("127.0.0.1", 0), server.App(path, SECRET))
    thread = threading.Thread(target=httpd.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    try:
        assert login(httpd.server_address[1], "bob", password).status == 303
        assert login(httpd.server_address[1], "bob", password[:-1]).status == 401
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_user_added_while_running_can_log_in(port, users_path):
    users.add_user(users_path, "carol", "carol-long-password")
    assert login(port, "carol", "carol-long-password").status == 303


def test_cross_site_login_post_is_rejected(port):
    assert login(port, headers={"Origin": "http://evil.example"}).status == 403
    assert login(port, headers={"Sec-Fetch-Site": "cross-site"}).status == 403
    assert login(port, headers={"Origin": f"http://127.0.0.1:{port}",
                                "Sec-Fetch-Site": "same-origin"}).status == 303


def test_foreign_host_header_is_rejected(port):
    response = request(port, "GET", "/login", headers={"Host": "attacker.example"})
    assert response.status == 421
    assert request(port, "GET", "/login", headers={"Host": f"localhost:{port}"}).status == 200


def test_browser_form_post_from_the_login_page_is_accepted(port):
    # What a browser sends when the form on /login is submitted.
    headers = {
        "Host": f"127.0.0.1:{port}",
        "Origin": f"http://127.0.0.1:{port}",
        "Referer": f"http://127.0.0.1:{port}/login",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
    }
    response = login(port, headers=headers)
    assert response.status == 303
    assert request(port, "POST", "/logout", cookie=f"session={response.token}", headers=headers).status == 303


def test_referrer_policy_keeps_origin_on_same_site_posts(port):
    # With "no-referrer" browsers send `Origin: null`, which would be refused.
    assert request(port, "GET", "/login").headers["Referrer-Policy"] != "no-referrer"


def test_repeated_failures_are_throttled(port):
    for _ in range(server.MAX_FAILURES):
        assert login(port, "alice", "wrong-password-1").status == 401
    response = login(port)  # even the right password
    assert response.status == 429
    assert int(response.headers["Retry-After"]) > 0
    assert "Set-Cookie" not in response.headers
    # Other accounts are unaffected.
    assert login(port, "mallory", "wrong-password-1").status == 401


def test_successful_login_resets_failures(port):
    for _ in range(server.MAX_FAILURES - 1):
        assert login(port, "alice", "wrong-password-1").status == 401
    assert login(port).status == 303
    for _ in range(server.MAX_FAILURES - 1):
        assert login(port, "alice", "wrong-password-1").status == 401
    assert login(port).status == 303


def test_failure_tracker_window_expires():
    now = [1000.0]
    tracker = server.FailedLoginTracker(max_failures=3, window=60, clock=lambda: now[0])
    for _ in range(3):
        tracker.record_failure("alice")
    assert tracker.retry_after("alice") == 60
    now[0] += 30
    assert tracker.retry_after("alice") == 30
    now[0] += 30
    assert tracker.retry_after("alice") is None


def test_failure_tracker_is_bounded():
    tracker = server.FailedLoginTracker(max_failures=3, window=60, max_tracked=5)
    for i in range(100):
        tracker.record_failure(f"user{i}")
    assert len(tracker._failures) == 5


# -- GET /dashboard -------------------------------------------------------------

def test_dashboard_with_session(port):
    token = login(port).token
    response = request(port, "GET", "/dashboard", cookie=f"session={token}")
    assert response.status == 200
    assert response.headers["Content-Type"] == HTML
    assert "Welcome, alice" in response.body
    assert re.search(r'<form[^>]*method="post"[^>]*action="/logout"', response.body)


def test_dashboard_finds_session_among_other_cookies(port):
    token = login(port).token
    response = request(port, "GET", "/dashboard", cookie=f"theme=dark; session={token}; x=y")
    assert response.status == 200


def test_dashboard_without_session_redirects(port):
    response = request(port, "GET", "/dashboard")
    assert response.status == 303
    assert response.headers["Location"] == "/login"


@pytest.mark.parametrize("cookie", [
    "session=", "session=garbage", "session=a.b.c", "sessionx=whatever",
])
def test_dashboard_with_invalid_session_redirects(port, cookie):
    response = request(port, "GET", "/dashboard", cookie=cookie)
    assert response.status == 303
    assert response.headers["Location"] == "/login"


def test_dashboard_rejects_token_signed_with_another_secret(port):
    token = tokens.issue("alice", b"some-other-secret")
    assert request(port, "GET", "/dashboard", cookie=f"session={token}").status == 303


def test_dashboard_rejects_expired_token(port):
    token = tokens.issue("alice", SECRET, now=time.time() - 1801)
    response = request(port, "GET", "/dashboard", cookie=f"session={token}")
    assert response.status == 303
    assert response.headers["Location"] == "/login"


def test_dashboard_accepts_token_near_end_of_life(port):
    token = tokens.issue("alice", SECRET, now=time.time() - 1700)
    assert request(port, "GET", "/dashboard", cookie=f"session={token}").status == 200


def test_dashboard_rejects_token_for_unknown_user(port):
    token = tokens.issue("ghost", SECRET)
    assert request(port, "GET", "/dashboard", cookie=f"session={token}").status == 303


def test_dashboard_escapes_username(tmp_path):
    # Usernames are restricted, but the page must escape regardless.
    assert b"<script>" not in pages.dashboard_page("<script>alert(1)</script>")
    assert b"&lt;script&gt;" in pages.dashboard_page("<script>alert(1)</script>")


# -- POST /logout ---------------------------------------------------------------

def test_logout_clears_cookie_and_redirects(port):
    token = login(port).token
    response = request(port, "POST", "/logout", cookie=f"session={token}")
    assert response.status == 303
    assert response.headers["Location"] == "/login"
    cookie = response.cookie
    assert cookie.startswith("session=;")
    assert "max-age=0" in cookie.lower()


def test_logout_revokes_token(port):
    token = login(port).token
    assert request(port, "GET", "/dashboard", cookie=f"session={token}").status == 200
    request(port, "POST", "/logout", cookie=f"session={token}")
    # Even a client that keeps the old cookie is logged out.
    assert request(port, "GET", "/dashboard", cookie=f"session={token}").status == 303


def test_logout_only_ends_that_session(port):
    first = login(port).token
    time.sleep(1.05)  # a different iat makes a different token
    second = login(port).token
    assert first != second
    request(port, "POST", "/logout", cookie=f"session={first}")
    assert request(port, "GET", "/dashboard", cookie=f"session={second}").status == 200


def test_logout_without_session(port):
    response = request(port, "POST", "/logout")
    assert response.status == 303
    assert response.headers["Location"] == "/login"
    assert response.cookie.startswith("session=;")


def test_cross_site_logout_is_rejected(port):
    token = login(port).token
    response = request(port, "POST", "/logout", cookie=f"session={token}",
                       headers={"Origin": "http://evil.example"})
    assert response.status == 403
    assert request(port, "GET", "/dashboard", cookie=f"session={token}").status == 200


# -- other paths and methods -----------------------------------------------------

@pytest.mark.parametrize("method,path", [
    ("GET", "/"), ("GET", "/nope"), ("GET", "/login/"), ("GET", "/dashboard/x"),
    ("POST", "/"), ("GET", "/users.json"), ("GET", "/../users.json"), ("DELETE", "/whatever"),
])
def test_unknown_paths_are_404(port, method, path):
    response = request(port, method, path)
    assert response.status == 404
    assert response.headers["Content-Type"] == HTML


def test_query_string_is_ignored_for_routing(port):
    assert request(port, "GET", "/login?next=/x").status == 200


@pytest.mark.parametrize("method,path", [
    ("GET", "/logout"), ("PUT", "/login"), ("POST", "/dashboard"), ("DELETE", "/dashboard"),
])
def test_wrong_method_on_known_path_is_405(port, method, path):
    response = request(port, method, path)
    assert response.status == 405
    assert "Allow" in response.headers


def test_malformed_request_line_gets_html_error(port):
    import socket
    with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
        sock.sendall(b"NONSENSE\r\n\r\n")
        data = b""
        while chunk := sock.recv(4096):
            data += chunk
    assert data.startswith(b"HTTP/1.0 400")
    assert b"text/html; charset=utf-8" in data


def test_app_requires_secret(users_path):
    with pytest.raises(ValueError):
        server.App(users_path, b"")
