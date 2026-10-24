"""Dashboard and session tests: FR-017 to FR-020, FR-024 to FR-027."""

import base64
import hashlib
import hmac
import json

import pytest

from conftest import (
    ALICE_PW,
    FakeClock,
    PageParser,
    dashboard,
    http,
    post_login,
    session_token,
    stop_server,
)
from loginapp import server, tokens

SECRET = b"test-secret"


def unb64(seg):
    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def sign_in(port, username="alice", password=ALICE_PW):
    resp = post_login(port, username, password)
    assert resp.status == 303, resp.status
    return session_token(resp)


def fake_server(inproc_server, users_file, clock=None):
    clock = clock or FakeClock()
    srv = inproc_server(users_file, clock=clock.time, sleep=clock.sleep)
    return srv, srv.server_address[1], clock


# ---------------------------------------------------------------- FR-017


def test_fr017_dashboard_welcome_and_logout_form(users_file, inproc_server):
    """FR-017: a valid session shows `Welcome, USERNAME` and a sign-out form posting to /logout."""
    port = inproc_server(users_file).server_address[1]
    token = sign_in(port)
    resp = dashboard(port, token)
    assert resp.status == 200
    assert b"Welcome, alice" in resp.body
    page = PageParser(resp.body)
    assert any(f.get("method", "").lower() == "post" and f.get("action") == "/logout" for f in page.forms)
    assert any(b.get("type", "submit") == "submit" for b in page.buttons)
    assert resp.headers_named("Set-Cookie") == []


def test_fr017_username_is_escaped():
    """FR-017: the username is HTML-escaped so it always displays as plain text."""
    page = server.dashboard_page('<b>&"x')
    assert b"Welcome, &lt;b&gt;&amp;&quot;x" in page
    assert b"<b>" not in page


# ---------------------------------------------------------------- FR-024 / FR-025


def test_fr024_issued_cookie_token_verifies(users_file, inproc_server):
    """FR-024: the issued token verifies with HMAC-SHA256 and holds sub, iat = int(clock) and exp = iat + 1800."""
    srv, port, clock = fake_server(inproc_server, users_file)
    token = sign_in(port)
    now = int(clock.time())
    s1, s2, s3 = token.split(".")
    assert unb64(s3) == hmac.new(SECRET, (s1 + "." + s2).encode("ascii"), hashlib.sha256).digest()
    claims = json.loads(unb64(s2))
    assert claims == {"sub": "alice", "iat": now, "exp": now + 1800}


def test_fr025_cookie_attributes(users_file, inproc_server):
    """FR-025: the session cookie has HttpOnly, SameSite=Strict, Path=/ and Max-Age=1800."""
    port = inproc_server(users_file).server_address[1]
    resp = post_login(port, "alice", ALICE_PW)
    cookies = resp.headers_named("Set-Cookie")
    assert len(cookies) == 1
    parts = [p.strip() for p in cookies[0].split(";")]
    assert parts[0].startswith("session=")
    assert len(parts[0][len("session="):].split(".")) == 3
    assert sorted(parts[1:]) == sorted(["HttpOnly", "SameSite=Strict", "Path=/", "Max-Age=1800"])


# ---------------------------------------------------------------- FR-018


def _tamper_sub(token):
    s1, s2, s3 = token.split(".")
    claims = json.loads(unb64(s2))
    claims["sub"] = "bob"
    return s1 + "." + b64(json.dumps(claims, separators=(",", ":")).encode()) + "." + s3


def _header_token(header, port, clock, digest=hashlib.sha256):
    payload = json.dumps({"sub": "alice", "iat": int(clock.time()), "exp": int(clock.time()) + 1800},
                         separators=(",", ":")).encode()
    s1, s2 = b64(header), b64(payload)
    sig = hmac.new(SECRET, (s1 + "." + s2).encode(), digest).digest()
    return s1 + "." + s2 + "." + b64(sig)


def _expired(port, clock):
    token = sign_in(port)
    clock.advance(1800)
    return "session=" + token


def logout(port, cookie=None):
    headers = [] if cookie is None else [("Cookie", cookie)]
    return http(port, "POST", "/logout", headers=headers)


def _signed_out(port, clock):
    token = sign_in(port)
    assert logout(port, "session=" + token).status == 303
    return "session=" + token


NO_SESSION_CASES = {
    "no-cookie": lambda port, clock: None,
    "empty-session": lambda port, clock: "session=",
    "two-session-pairs": lambda port, clock: "session={0}; session={0}".format(sign_in(port)),
    "malformed-two-segments": lambda port, clock: "session=a.b",
    "random-text": lambda port, clock: "session=qwertyuiopasdfghjkl",
    "tampered-sub": lambda port, clock: "session=" + _tamper_sub(sign_in(port)),
    "other-secret": lambda port, clock: "session=" + tokens.encode("alice", int(clock.time()), b"other-secret"),
    "alg-none": lambda port, clock: "session=" + b64(b'{"alg":"none","typ":"JWT"}') + "."
    + _header_token(b"{}", port, clock).split(".")[1] + ".",
    "alg-hs512": lambda port, clock: "session=" + _header_token(b'{"alg":"HS512","typ":"JWT"}', port, clock, hashlib.sha512),
    "expired": _expired,
    "never-issued": lambda port, clock: "session=" + tokens.encode("alice", int(clock.time()), SECRET),
    "signed-out": _signed_out,
}


def _assert_redirect_to_login(resp):
    assert resp.status == 303
    assert resp.header("Location") == "/login"
    assert resp.body == b""
    assert b"Welcome" not in resp.body
    assert resp.headers_named("Set-Cookie") == []


@pytest.mark.parametrize("make_cookie", list(NO_SESSION_CASES.values()), ids=list(NO_SESSION_CASES))
def test_fr018_no_valid_session_redirects(users_file, inproc_server, make_cookie):
    """FR-018: without a valid session, GET /dashboard redirects to /login with no dashboard content."""
    srv, port, clock = fake_server(inproc_server, users_file)
    cookie = make_cookie(port, clock)
    headers = [] if cookie is None else [("Cookie", cookie)]
    _assert_redirect_to_login(http(port, "GET", "/dashboard", headers=headers))


# ---------------------------------------------------------------- FR-026 / FR-027


def _iat(token):
    return json.loads(unb64(token.split(".")[1]))["iat"]


def _set_time(clock, when):
    clock.advance(when - clock.time())


def test_fr026_dashboard_sets_no_cookie(users_file, inproc_server):
    """FR-026: GET /dashboard never sets a new or refreshed session cookie."""
    srv, port, clock = fake_server(inproc_server, users_file)
    resp = dashboard(port, sign_in(port))
    assert resp.status == 200
    assert resp.headers_named("Set-Cookie") == []


def test_fr026_fixed_lifetime_despite_use(users_file, inproc_server):
    """FR-026: a session lasts exactly 1800 s from sign-in however often it is used."""
    srv, port, clock = fake_server(inproc_server, users_file)
    token = sign_in(port)
    iat = _iat(token)
    for offset in (1, 600, 1200, 1799):
        _set_time(clock, iat + offset)
        resp = dashboard(port, token)
        assert resp.status == 200, offset
        assert resp.headers_named("Set-Cookie") == []
    _set_time(clock, iat + 1800)
    _assert_redirect_to_login(dashboard(port, token))


def test_fr027_same_second_restart(users_file, inproc_server):
    """FR-027: a token from an earlier run is refused even when the new run starts in the same second."""
    clock = FakeClock()
    first = inproc_server(users_file, clock=clock.time, sleep=clock.sleep)
    old_token = sign_in(first.server_address[1])
    issued_at = _iat(old_token)
    stop_server(first)

    second = inproc_server(users_file, clock=clock.time, sleep=clock.sleep)
    assert int(clock.time()) == issued_at  # B starts in the second A issued its token
    port = second.server_address[1]
    _assert_redirect_to_login(dashboard(port, old_token))
    new_token = sign_in(port)
    assert new_token != old_token
    assert _iat(new_token) > issued_at
    assert dashboard(port, new_token).status == 200
    _assert_redirect_to_login(dashboard(port, old_token))


def test_fr027_current_run_tokens_accepted_until_expiry(users_file, inproc_server):
    """FR-027: every token issued by the current run is accepted until it expires."""
    srv, port, clock = fake_server(inproc_server, users_file)
    token = sign_in(port)
    _set_time(clock, _iat(token) + 1799)
    assert dashboard(port, token).status == 200


# ---------------------------------------------------------------- FR-019 / FR-020


def _logout_cookie_valid(port, clock):
    return "session=" + sign_in(port)


LOGOUT_CASES = {
    "valid-session": _logout_cookie_valid,
    "no-cookie": lambda port, clock: None,
    "invalid-token": lambda port, clock: "session=not.a.token",
    "expired-token": _expired,
}


@pytest.mark.parametrize("make_cookie", list(LOGOUT_CASES.values()), ids=list(LOGOUT_CASES))
def test_fr019_logout_clears_cookie(users_file, inproc_server, make_cookie):
    """FR-019: POST /logout always redirects to /login and deletes the session cookie."""
    srv, port, clock = fake_server(inproc_server, users_file)
    resp = logout(port, make_cookie(port, clock))
    assert resp.status == 303
    assert resp.header("Location") == "/login"
    assert resp.header("Content-Length") == "0"
    cookies = resp.headers_named("Set-Cookie")
    assert len(cookies) == 1
    parts = [p.strip() for p in cookies[0].split(";")]
    assert parts[0] == "session="
    assert "Max-Age=0" in parts[1:]
    assert "Path=/" in parts[1:]


def test_fr020_signed_out_copy_refused(users_file, inproc_server):
    """FR-020: after sign-out, a kept copy of the token is refused."""
    srv, port, clock = fake_server(inproc_server, users_file)
    token = sign_in(port)
    assert dashboard(port, token).status == 200
    assert logout(port, "session=" + token).status == 303
    _assert_redirect_to_login(dashboard(port, token))


def _same_bytes_last_char(seg):
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_":
        if c != seg[-1] and unb64(seg[:-1] + c) == unb64(seg):
            return seg[:-1] + c
    raise AssertionError("no alternative last character")


def test_fr020_reencoded_copy_refused(users_file, inproc_server):
    """FR-020: re-encoded copies of a signed-out token (padding, same-bytes last character) are refused."""
    srv, port, clock = fake_server(inproc_server, users_file)
    token = sign_in(port)
    assert logout(port, "session=" + token).status == 303
    s1, s2, s3 = token.split(".")
    for copy in (token + "=", s1 + "." + s2 + "." + _same_bytes_last_char(s3)):
        assert copy != token
        _assert_redirect_to_login(dashboard(port, copy))


def test_fr020_other_sessions_unaffected(users_file, inproc_server):
    """FR-020: signing out ends only the presented token; other sessions of the user stay valid."""
    srv, port, clock = fake_server(inproc_server, users_file)
    first = sign_in(port)
    clock.advance(1)
    second = sign_in(port)
    assert first != second
    assert logout(port, "session=" + first).status == 303
    _assert_redirect_to_login(dashboard(port, first))
    assert dashboard(port, second).status == 200


def test_fr020_same_second_sign_in_after_logout_gets_new_token(users_file, inproc_server):
    """FR-020: signing in again in the same second after sign-out gives a new, working token."""
    srv, port, clock = fake_server(inproc_server, users_file)
    old = sign_in(port)
    assert int(clock.time()) == _iat(old)
    assert logout(port, "session=" + old).status == 303
    assert int(clock.time()) == _iat(old)  # still the same second
    new = sign_in(port)
    assert new != old
    assert _iat(new) > _iat(old)
    assert dashboard(port, new).status == 200
    _assert_redirect_to_login(dashboard(port, old))
