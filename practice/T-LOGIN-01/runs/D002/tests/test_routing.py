"""Routing and header tests: FR-012, FR-021, FR-022, FR-028."""

import pytest

from conftest import ALICE_PW, http, post_login

FORM_CT = ("Content-Type", "application/x-www-form-urlencoded")


def _broken_file_sign_in(port, users_file):
    users_file.write_bytes(b"{")
    return post_login(port, "alice", ALICE_PW)


RESPONSE_CASES = [
    ("get-login-200", lambda port, f: http(port, "GET", "/login"), 200),
    ("wrong-password-401", lambda port, f: post_login(port, "alice", "wrong-password-1"), 401),
    ("dashboard-no-cookie-303", lambda port, f: http(port, "GET", "/dashboard"), 303),
    ("unknown-path-404", lambda port, f: http(port, "GET", "/nope"), 404),
    ("post-dashboard-405", lambda port, f: http(port, "POST", "/dashboard"), 405),
    ("bad-content-length-400",
     lambda port, f: http(port, "POST", "/login", headers=[FORM_CT, ("Content-Length", "abc")]), 400),
    ("too-large-413",
     lambda port, f: http(port, "POST", "/login", headers=[FORM_CT, ("Content-Length", "100000000")]), 413),
    ("broken-file-500", _broken_file_sign_in, 500),
    ("put-login-501", lambda port, f: http(port, "PUT", "/login"), 501),
    ("garbage-request-400", lambda port, f: http(port, None, None, raw=b"GARBAGE\r\n\r\n"), 400),
    ("http09-request-400", lambda port, f: http(port, None, None, raw=b"GET /login\r\n\r\n"), 400),
    ("post-logout-303", lambda port, f: http(port, "POST", "/logout"), 303),
    ("get-logout-405", lambda port, f: http(port, "GET", "/logout"), 405),
]


def _run_case(inproc_server, users_file, request, status):
    port = inproc_server(users_file).server_address[1]
    resp = request(port, users_file)
    assert resp.status == status
    return resp


# ---------------------------------------------------------------- FR-012


@pytest.mark.parametrize("request_fn, status", [(r, s) for _, r, s in RESPONSE_CASES], ids=[n for n, _, _ in RESPONSE_CASES])
def test_fr012_every_body_is_html_utf8(users_file, inproc_server, request_fn, status):
    """FR-012: every response with a body is HTML with `Content-Type: text/html; charset=utf-8`."""
    resp = _run_case(inproc_server, users_file, request_fn, status)
    if resp.body:
        assert resp.headers_named("Content-Type") == ["text/html; charset=utf-8"]
        assert resp.body.lower().startswith(b"<!doctype html>")


# ---------------------------------------------------------------- FR-028


@pytest.mark.parametrize("request_fn, status", [(r, s) for _, r, s in RESPONSE_CASES], ids=[n for n, _, _ in RESPONSE_CASES])
def test_fr028_protective_headers_everywhere(users_file, inproc_server, request_fn, status):
    """FR-028: every response carries Cache-Control: no-store, X-Frame-Options: DENY, X-Content-Type-Options: nosniff."""
    resp = _run_case(inproc_server, users_file, request_fn, status)
    assert resp.headers_named("Cache-Control") == ["no-store"]
    assert resp.headers_named("X-Frame-Options") == ["DENY"]
    assert resp.headers_named("X-Content-Type-Options") == ["nosniff"]


# ---------------------------------------------------------------- FR-021


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("path", ["/", "/dashboard/", "/login.html", "//login", "/LOGIN", "/logout/x"])
def test_fr021_unknown_paths_404(users_file, inproc_server, method, path):
    """FR-021: any other path, matched exactly, gets 404 with an HTML page."""
    port = inproc_server(users_file).server_address[1]
    resp = http(port, method, path)
    assert resp.status == 404
    assert resp.header("Content-Type") == "text/html; charset=utf-8"
    assert resp.body.lower().startswith(b"<!doctype html>")


def test_fr021_query_string_ignored(users_file, inproc_server):
    """FR-021: the query string is ignored when matching paths."""
    port = inproc_server(users_file).server_address[1]
    resp = http(port, "GET", "/login?x=1")
    assert resp.status == 200
    assert b'<form method="post" action="/login">' in resp.body


# ---------------------------------------------------------------- FR-022


@pytest.mark.parametrize(
    "method, path, allow", [("POST", "/dashboard", "GET"), ("GET", "/logout", "POST")], ids=["post-dashboard", "get-logout"]
)
def test_fr022_wrong_method_405_with_allow(users_file, inproc_server, method, path, allow):
    """FR-022: a wrong method on a known page gets 405 with an Allow header."""
    port = inproc_server(users_file).server_address[1]
    resp = http(port, method, path)
    assert resp.status == 405
    assert resp.header("Allow") == allow


@pytest.mark.parametrize("path", ["/login", "/dashboard", "/logout", "/nope"])
@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH"])
def test_fr022_other_methods_error(users_file, inproc_server, method, path):
    """FR-022: methods other than GET and POST get an error status on every path."""
    port = inproc_server(users_file).server_address[1]
    assert http(port, method, path).status >= 400
