"""Login page and sign-in tests: FR-011, FR-013, FR-014, FR-015, FR-016."""

import statistics
import time

import pytest

from conftest import (
    ALICE_PW,
    PageParser,
    ServerProcess,
    free_port,
    http,
    post_login,
    run_cli,
)
from loginapp import accounts, server

FORM_CT = ("Content-Type", "application/x-www-form-urlencoded")
MESSAGE = b"Invalid username or password"


def form_post(port, body, headers=(FORM_CT,)):
    return http(port, "POST", "/login", headers=list(headers), body=body)


# ---------------------------------------------------------------- FR-013


def test_fr013_login_form(users_file, inproc_server):
    """FR-013: GET /login shows a POST form to /login with username, masked password and a submit button."""
    port = inproc_server(users_file).server_address[1]
    resp = http(port, "GET", "/login")
    assert resp.status == 200
    page = PageParser(resp.body)
    assert len(page.forms) == 1
    assert page.forms[0]["method"].lower() == "post"
    assert page.forms[0]["action"] == "/login"
    assert any(i.get("name") == "username" and i.get("type") == "text" for i in page.inputs)
    assert any(i.get("name") == "password" and i.get("type") == "password" for i in page.inputs)
    assert any(b.get("type", "submit") == "submit" for b in page.buttons)
    assert MESSAGE not in resp.body
    assert resp.headers_named("Set-Cookie") == []

    with_cookie = http(port, "GET", "/login", headers=[("Cookie", "session=x")])
    assert with_cookie.status == 200
    assert with_cookie.header("Location") is None


# ---------------------------------------------------------------- FR-014


def test_fr014_correct_credentials_redirect_with_cookie(users_file, inproc_server):
    """FR-014: correct credentials give 303 to /dashboard and set a `session` cookie."""
    port = inproc_server(users_file).server_address[1]
    resp = post_login(port, "alice", ALICE_PW)
    assert resp.status == 303
    assert resp.header("Location") == "/dashboard"
    cookies = resp.headers_named("Set-Cookie")
    assert len(cookies) == 1 and cookies[0].startswith("session=")
    assert resp.header("Content-Length") == "0"
    assert resp.body == b""


def test_fr014_extra_fields_ignored(users_file, inproc_server):
    """FR-014: other form fields are ignored."""
    port = inproc_server(users_file).server_address[1]
    assert post_login(port, "alice", ALICE_PW, extra=[("remember", "1")]).status == 303


@pytest.mark.parametrize(
    "content_type",
    ["application/x-www-form-urlencoded; charset=UTF-8", "APPLICATION/X-WWW-FORM-URLENCODED"],
    ids=["charset-parameter", "upper-case"],
)
def test_fr014_content_type_parameters_allowed(users_file, inproc_server, content_type):
    """FR-014: the media type is matched case-insensitively and parameters are allowed."""
    port = inproc_server(users_file).server_address[1]
    assert post_login(port, "alice", ALICE_PW, content_type=content_type).status == 303


def test_fr014_percent_encoded_and_raw_utf8(users_file, inproc_server):
    """FR-014: raw UTF-8 and percent-encoded UTF-8 form bodies both sign in."""
    password = "pässwörd-ünïcode-1"
    records = accounts.load(str(users_file), missing_ok=False)
    records["carol"] = accounts.make_record(password)
    accounts.save(str(users_file), records)
    port = inproc_server(users_file).server_address[1]
    raw = ("username=carol&password=" + password).encode("utf-8")
    assert form_post(port, raw).status == 303
    assert post_login(port, "carol", password).status == 303


# ---------------------------------------------------------------- FR-015


def test_fr015_unknown_user_and_wrong_password_identical(users_file, inproc_server):
    """FR-015: unknown username and wrong password get identical 401 responses (apart from Date)."""
    port = inproc_server(users_file).server_address[1]
    wrong = post_login(port, "alice", "wrong-password-1")
    unknown = post_login(port, "nobody", "any-password-123")
    for resp in (wrong, unknown):
        assert resp.status == 401
        assert resp.headers_named("Set-Cookie") == []
        assert MESSAGE in resp.body
        assert len(PageParser(resp.body).forms) == 1
    assert wrong.body == unknown.body == server.login_page(True)
    assert wrong.headers_without_date() == unknown.headers_without_date()


MALFORMED = {
    "missing-username": ([FORM_CT], b"password=correct-horse-battery"),
    "missing-password": ([FORM_CT], b"username=alice"),
    "empty-username": ([FORM_CT], b"username=&password=correct-horse-battery"),
    "empty-password": ([FORM_CT], b"username=alice&password="),
    "repeated-username": ([FORM_CT], b"username=alice&username=alice&password=correct-horse-battery"),
    "repeated-password": ([FORM_CT], b"username=alice&password=correct-horse-battery&password=correct-horse-battery"),
    "content-length-0": ([FORM_CT, ("Content-Length", "0")], b""),
    "no-content-length": ([FORM_CT], b""),
    "no-content-type": ([], b"username=alice&password=correct-horse-battery"),
    "text-plain": ([("Content-Type", "text/plain")], b"username=alice&password=correct-horse-battery"),
    "multipart": ([("Content-Type", "multipart/form-data")], b"username=alice&password=correct-horse-battery"),
    "two-content-types": ([FORM_CT, FORM_CT], b"username=alice&password=correct-horse-battery"),
    "raw-invalid-utf8": ([FORM_CT], b"username=alice&password=\xffcorrect-horse-battery"),
    "percent-invalid-utf8": ([FORM_CT], b"username=alice&password=%FFcorrect-horse-battery"),
}


@pytest.mark.parametrize("headers, body", list(MALFORMED.values()), ids=list(MALFORMED))
def test_fr015_malformed_submissions_get_401(users_file, inproc_server, headers, body):
    """FR-015: malformed sign-in submissions get the standard 401 page and no cookie."""
    port = inproc_server(users_file).server_address[1]
    resp = form_post(port, body, headers=headers)
    assert resp.status == 401
    assert resp.body == server.login_page(True)
    assert resp.headers_named("Set-Cookie") == []


def test_fr015_page_does_not_echo_input(users_file, inproc_server):
    """FR-015: the failure page never repeats the submitted username or password."""
    port = inproc_server(users_file).server_address[1]
    resp = post_login(port, "zz_echo_user_zz", "zz-echo-pass-zz")
    assert resp.status == 401
    assert b"zz_echo_user_zz" not in resp.body
    assert b"zz-echo-pass-zz" not in resp.body


def test_fr015_oversized_body_413_without_reading(users_file, inproc_server):
    """FR-015: a declared body over 64 KiB gets 413 without being read; exactly 64 KiB is read."""
    port = inproc_server(users_file).server_address[1]
    for length in ("65537", "100000000"):
        resp = http(port, "POST", "/login", headers=[FORM_CT, ("Content-Length", length)], timeout=10)
        assert resp.status == 413
        assert resp.header("Content-Type") == "text/html; charset=utf-8"
    prefix = b"username=alice&password="
    body = prefix + b"x" * (65536 - len(prefix))
    assert len(body) == 65536
    assert form_post(port, body).status == 401


@pytest.mark.parametrize(
    "lengths", [["abc"], ["-1"], ["1e3"], ["10", "10"]], ids=["letters", "negative", "exponent", "two-headers"]
)
def test_fr015_invalid_content_length_400(users_file, inproc_server, lengths):
    """FR-015: an invalid declared body length gets 400."""
    port = inproc_server(users_file).server_address[1]
    headers = [FORM_CT] + [("Content-Length", v) for v in lengths]
    assert http(port, "POST", "/login", headers=headers).status == 400


def test_fr015_truncated_body_400(users_file, inproc_server):
    """FR-015: a body shorter than its declared length gets 400."""
    port = inproc_server(users_file).server_address[1]
    resp = http(port, "POST", "/login", headers=[FORM_CT, ("Content-Length", "50")], body=b"username=a")
    assert resp.status == 400


# ---------------------------------------------------------------- FR-011


def test_fr011_account_added_while_running_can_sign_in(users_file):
    """FR-011: an account added while the server runs can sign in without a restart."""
    port = free_port()
    with ServerProcess(port, users_file, "fr011-secret"):
        added = run_cli("adduser", "carol", "--users", str(users_file), stdin=b"a-third-long-pass\n")
        assert added.returncode == 0, added.stderr
        assert post_login(port, "carol", "a-third-long-pass").status == 303


def test_fr011_broken_file_at_sign_in_gives_500(users_file):
    """FR-011: if FILE is invalid at sign-in time, the attempt gets 500 and no session."""
    original = users_file.read_bytes()
    port = free_port()
    with ServerProcess(port, users_file, "fr011-secret") as sp:
        users_file.write_bytes(b"{")
        resp = post_login(port, "alice", ALICE_PW)
        assert resp.status == 500
        assert resp.headers_named("Set-Cookie") == []
        assert resp.body == server.simple_page("Internal server error")
        users_file.write_bytes(original)
        assert post_login(port, "alice", ALICE_PW).status == 303
    assert repr(str(users_file)) in sp.stderr_text
    assert ALICE_PW not in sp.stderr_text


# ---------------------------------------------------------------- FR-016


def _timed(fn):
    start = time.perf_counter()
    resp = fn()
    elapsed = time.perf_counter() - start
    assert resp.status == 401
    return elapsed


def test_fr016_unknown_user_and_wrong_password_timing(users_file, inproc_server):
    """FR-016: unknown-username and wrong-password failures take about as long (medians within 2x)."""
    port = inproc_server(users_file).server_address[1]
    unknown, wrong = [], []
    for i in range(7):
        unknown.append(_timed(lambda: post_login(port, "nobody", f"wrong-password-{i}")))
        wrong.append(_timed(lambda: post_login(port, "alice", f"wrong-password-{i}")))
    medians = [statistics.median(unknown), statistics.median(wrong)]
    assert max(medians) / min(medians) <= 2, medians
