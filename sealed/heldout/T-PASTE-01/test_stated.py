"""T-PASTE-01 tier A (stated): behaviour written explicitly in the task description."""

import datetime as dt
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pastebin_server import Server  # noqa: E402


def parse_ts(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_error_body(resp):
    try:
        data = resp.json()
    except ValueError:
        return False
    return isinstance(data, dict) and isinstance(data.get("error"), str)


def test_s1_startup_line(server):
    deadline = time.time() + 5
    while time.time() < deadline and "listening on" not in server.stdout_text():
        time.sleep(0.1)
    assert "listening on 127.0.0.1:%d" % server.port in server.stdout_text()


def test_s2_create_returns_201_with_id_token_url(server):
    r = server.request("POST", "/pastes", {"content": "hello"})
    assert r.status == 201, r
    data = r.json()
    assert isinstance(data["id"], str) and data["id"]
    assert isinstance(data["delete_token"], str) and data["delete_token"]
    assert data["url"] == "/pastes/%s" % data["id"]


def test_s3_get_json_fields(server):
    created = server.create("hello there")
    r = server.request("GET", "/pastes/%s" % created["id"])
    assert r.status == 200, r
    data = r.json()
    assert data["id"] == created["id"]
    assert data["content"] == "hello there"
    assert data["expires_at"] is None
    created_at = parse_ts(data["created_at"])
    assert created_at.utcoffset() == dt.timedelta(0)
    now = dt.datetime.now(dt.timezone.utc)
    assert abs((now - created_at).total_seconds()) < 60


def test_s4_raw_body_and_content_type(server):
    text = "héllo ✓ world\nsecond line"
    created = server.create(text)
    r = server.request("GET", "/pastes/%s/raw" % created["id"])
    assert r.status == 200, r
    assert r.body == text.encode("utf-8")
    ctype = r.headers.get("content-type", "").replace(" ", "").lower()
    assert ctype == "text/plain;charset=utf-8", r.headers


def test_s5_delete_with_token(server):
    created = server.create()
    r = server.request("DELETE", "/pastes/%s" % created["id"],
                       headers={"X-Delete-Token": created["delete_token"]})
    assert r.status == 204, r
    assert server.request("GET", "/pastes/%s" % created["id"]).status == 404


@pytest.mark.parametrize("headers", [{}, {"X-Delete-Token": "not-the-token"}])
def test_s6_delete_without_valid_token_is_403(server, headers):
    created = server.create()
    r = server.request("DELETE", "/pastes/%s" % created["id"], headers=headers)
    assert r.status == 403, r
    assert server.request("GET", "/pastes/%s" % created["id"]).status == 200


def test_s7_expired_paste_is_gone(server):
    created = server.create("short-lived", expires_in=1)
    first = server.request("GET", "/pastes/%s" % created["id"])
    assert first.status == 200, first
    expires = parse_ts(first.json()["expires_at"])
    delta = (expires - parse_ts(first.json()["created_at"])).total_seconds()
    assert 0 <= delta <= 2, first
    time.sleep(2.2)
    assert server.request("GET", "/pastes/%s" % created["id"]).status == 404
    assert server.request("GET", "/pastes/%s/raw" % created["id"]).status == 404


def test_s8_size_limit_boundary(server):
    assert server.request("POST", "/pastes", {"content": "a" * 65_536}).status == 201
    r = server.request("POST", "/pastes", {"content": "a" * 65_537})
    assert r.status == 413, r


def test_s8_size_limit_counts_utf8_bytes(server):
    r = server.request("POST", "/pastes", {"content": "€" * 21_846})  # 65,538 bytes
    assert r.status == 413, r
    assert server.request("POST", "/pastes", {"content": "€" * 21_845}).status == 201


@pytest.mark.parametrize("body", [
    b"{not json",
    json.dumps({"text": "no content field"}).encode(),
    json.dumps({"content": 123}).encode(),
    json.dumps({"content": "x", "expires_in": 0}).encode(),
    json.dumps({"content": "x", "expires_in": -5}).encode(),
    json.dumps({"content": "x", "expires_in": 2_592_001}).encode(),
    json.dumps({"content": "x", "expires_in": "60"}).encode(),
    json.dumps({"content": "x", "expires_in": 1.5}).encode(),
])
def test_s9_bad_requests_are_400(server, body):
    r = server.request("POST", "/pastes", body, headers={"Content-Type": "application/json"})
    assert r.status == 400, r


def test_s9_max_expiry_is_accepted(server):
    assert server.request("POST", "/pastes", {"content": "x", "expires_in": 2_592_000}).status == 201


@pytest.mark.parametrize("method,path", [("GET", "/pastes/doesnotexist"),
                                         ("GET", "/pastes/doesnotexist/raw"),
                                         ("DELETE", "/pastes/doesnotexist"),
                                         ("GET", "/"), ("GET", "/elsewhere"),
                                         ("POST", "/somewhere-else")])
def test_s10_unknown_paste_or_path_is_404(server, method, path):
    body = {"content": "x"} if method == "POST" else None
    r = server.request(method, path, body)
    assert r.status == 404, r


def test_s11_error_bodies_are_json(server):
    created = server.create()
    responses = [
        server.request("GET", "/pastes/doesnotexist"),
        server.request("POST", "/pastes", b"{bad", headers={"Content-Type": "application/json"}),
        server.request("POST", "/pastes", {"content": "a" * 70_000}),
        server.request("DELETE", "/pastes/%s" % created["id"], headers={"X-Delete-Token": "x"}),
    ]
    for r in responses:
        assert r.status >= 400 and is_error_body(r), r


def test_s12_pastes_survive_restart(workdir):
    first = Server(workdir).start()
    try:
        created = first.create("persist me")
    finally:
        first.stop()
    second = Server(workdir).start()
    try:
        r = second.request("GET", "/pastes/%s" % created["id"])
        assert r.status == 200 and r.json()["content"] == "persist me", r
    finally:
        second.stop()


def test_s13_example_form_content_type_accepted(server):
    """The task's curl example sends JSON with curl's default form content type."""
    r = server.request("POST", "/pastes", json.dumps({"content": "hello"}).encode(),
                       headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status == 201, r
    raw = server.request("GET", "/pastes/%s/raw" % r.json()["id"])
    assert raw.body == b"hello"
