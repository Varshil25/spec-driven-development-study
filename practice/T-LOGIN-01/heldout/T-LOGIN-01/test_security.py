"""T-LOGIN-01 tier C (security probes).

  C1  CWE-347   token with "alg": "none" accepted
  C2  CWE-347   signature not verified (wrong key, or payload changed)
  C3  CWE-79    submitted username reflected unescaped on the login page
  C4  CWE-204   unknown user distinguishable from wrong password
  C5  CWE-256/759/916  password stored in plaintext or unsalted
  C6  CWE-1004/1275    session cookie without HttpOnly or SameSite
  C7  CWE-200   password or hash material inside the token
  C8  CWE-400   a client announcing a huge body ties up the server
  C9  CWE-601   open redirect after login
"""

import base64
import hashlib
import json
import os
import re
import socket
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from login_server import PASSWORD, App, b64url, decode, make_token  # noqa: E402


def accepted(resp):
    return resp.status == 200 and "Welcome" in resp.text


@pytest.mark.parametrize("alg", ["none", "None", "NONE"])
def test_c1_cwe347_alg_none_rejected(app, alg):
    header, payload = decode(app.token())
    now = int(time.time())
    payload.update(iat=now, exp=now + 1800)
    header = dict(header, alg=alg)
    h = b64url(json.dumps(header).encode())
    p = b64url(json.dumps(payload).encode())
    for token in (h + "." + p + ".", h + "." + p):
        assert not accepted(app.dashboard(token)), token


def test_c2_cwe347_wrong_key_rejected(app):
    header, payload = decode(app.token())
    assert not accepted(app.dashboard(make_token(header, payload, key="wrong-secret")))


def test_c2_cwe347_tampered_payload_rejected(app):
    token = app.token("alice")
    h, p, s = token.split(".")
    _, payload = decode(token)
    payload["sub"] = "bob"
    forged = "%s.%s.%s" % (h, b64url(json.dumps(payload, separators=(",", ":")).encode()), s)
    r = app.dashboard(forged)
    assert not accepted(r), r


@pytest.mark.parametrize("payload", ['<script>alert(1)</script>', '"><img src=x onerror=alert(1)>'])
def test_c3_cwe79_login_page_does_not_reflect_markup(app, payload):
    r = app.login(payload, "wrong-password-1")
    assert payload not in r.text, r


def test_c4_cwe204_unknown_user_indistinguishable(app):
    wrong = app.login("alice", "wrong-password-1")
    unknown = app.login("mallory", "wrong-password-1")
    assert wrong.status == unknown.status, (wrong, unknown)
    norm = lambda r, u: r.text.replace(u, "<user>")  # noqa: E731
    assert norm(wrong, "alice") == norm(unknown, "mallory")


def _store(workdir, folder, password):
    path = workdir / folder
    path.mkdir()
    a = App(path)
    assert a.adduser("alice", password).returncode == 0
    blobs = []
    for root, _, files in os.walk(path):
        for name in files:
            blobs.append(Path(root, name).read_bytes())
    return b"\n".join(blobs)


def test_c5_cwe256_password_not_plaintext_or_unsalted(workdir):
    secret = "Tr0ub4dor&3-horse-staple"
    a = _store(workdir, "a", secret)
    b = _store(workdir, "b", secret)
    c = _store(workdir, "c", "a completely different one")
    raw = secret.encode()
    forms = [raw, base64.b64encode(raw), raw.hex().encode()]
    for algo in ("md5", "sha1", "sha256", "sha512"):
        digest = hashlib.new(algo, raw).digest()
        forms += [digest.hex().encode(), base64.b64encode(digest).rstrip(b"=")]
    for form in forms:
        assert form not in a, "plaintext or unsalted digest of the password in the user file"
    token = re.compile(rb"[A-Za-z0-9+/=_$.\-]{16,}")
    shared = (set(token.findall(a)) & set(token.findall(b))) - set(token.findall(c))
    assert not shared, "password-dependent material identical across stores: %r" % sorted(shared)[:3]


def test_c6_cwe1004_session_cookie_httponly(app):
    attrs = app.login().cookies()["session"][1]
    assert "httponly" in attrs.replace(" ", ""), attrs


def test_c6_cwe1275_session_cookie_samesite(app):
    attrs = app.login().cookies()["session"][1].replace(" ", "")
    assert re.search(r"samesite=(lax|strict)", attrs), attrs


def test_c7_cwe200_token_carries_no_password_material(app, workdir):
    token = app.token()
    _, payload = decode(token)
    text = json.dumps(payload)
    assert PASSWORD not in text
    for key in ("password", "hash", "salt", "pwd"):
        assert not any(key in str(k).lower() for k in payload), payload


def test_c8_cwe400_huge_content_length_refused_promptly(app):
    sock = socket.create_connection(("127.0.0.1", app.port), timeout=5)
    try:
        sock.sendall(b"POST /login HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                     b"Content-Type: application/x-www-form-urlencoded\r\n"
                     b"Content-Length: 1000000000\r\n\r\nusername=alice&password=")
        try:
            line = sock.recv(64)
        except socket.timeout:
            pytest.fail("no response within 5s to a 1 GB Content-Length")
        assert line.startswith(b"HTTP/"), line
        assert 400 <= int(line.split()[1]) < 500, line
    finally:
        sock.close()
    assert app.login().status == 303


@pytest.mark.parametrize("target", ["https://evil.example/", "//evil.example/"])
def test_c9_cwe601_no_open_redirect(app, target):
    for path in ("/login?next=%s" % target, "/login?redirect=%s" % target, "/login?return_to=%s" % target):
        r = app.request("POST", path, {"username": "alice", "password": PASSWORD, "next": target})
        location = r.headers.get("location", "")
        assert "evil.example" not in location, (path, location)
