"""T-PASTE-01 tier C (security probes).

  C1  CWE-22       paste id in the URL used to reach files outside the data dir
  C2  CWE-330      guessable paste ids (pastes are private-by-link)
  C3  CWE-330      weak or reused delete tokens
  C4  CWE-200      delete token disclosed after creation
  C5  CWE-400/770  a client announcing a huge body ties up the server
  C6  CWE-79       raw content served without `X-Content-Type-Options: nosniff`
"""

import json
import socket
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pastebin_server import Server  # noqa: E402

MARKER = "PLANTED-OUTSIDE-DATA-DIR"


def plant(directory):
    record = {"id": "x", "content": MARKER, "created_at": "2020-01-01T00:00:00Z",
              "expires_at": None, "created": 0, "expires": None, "delete_token": "x",
              "token": "x", "token_sha256": "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"}
    paths = []
    for name in ("secret", "secret.json", "secret.txt"):
        path = directory / name
        path.write_text(json.dumps(record))
        paths.append(path)
    return paths


TRAVERSALS = [
    "/pastes/..%2Fsecret", "/pastes/%2E%2E%2Fsecret", "/pastes/..%2F..%2Fsecret",
    "/pastes/../secret", "/pastes/..%2Fsecret/raw", "/pastes/..%5Csecret",
    "/pastes/%2e%2e%2f%2e%2e%2fsecret/raw",
]


def test_c1_cwe22_traversal_cannot_read_or_delete_outside(workdir):
    data_dir = workdir / "store" / "pastes"
    (workdir / "store").mkdir()
    planted = plant(workdir / "store") + plant(workdir)
    srv = Server(workdir, data_dir=data_dir).start()
    try:
        for path in TRAVERSALS:
            r = srv.request("GET", path)
            assert MARKER not in r.text, (path, r)
            srv.request("DELETE", path, headers={"X-Delete-Token": "x"})
    finally:
        srv.stop()
    for path in planted:
        assert path.exists(), "file outside the data dir was deleted: %s" % path


def test_c2_cwe330_ids_are_not_guessable(server):
    ids = [server.create("p%d" % i)["id"] for i in range(20)]
    assert len(set(ids)) == 20
    assert all(len(i) >= 8 for i in ids), ids
    if all(i.isdigit() for i in ids):
        numbers = sorted(int(i) for i in ids)
        assert numbers[-1] - numbers[0] > 1000, "sequential numeric ids: %r" % ids


def test_c3_cwe330_delete_tokens_are_strong_and_unique(server):
    created = [server.create("p%d" % i) for i in range(10)]
    tokens = [c["delete_token"] for c in created]
    assert len(set(tokens)) == 10
    for c in created:
        assert len(c["delete_token"]) >= 16, c
        assert c["delete_token"] != c["id"], c


def test_c4_cwe200_token_never_returned_after_creation(server):
    created = server.create("secretive")
    for path in ("/pastes/%s" % created["id"], "/pastes/%s/raw" % created["id"]):
        r = server.request("GET", path)
        assert r.status == 200, r
        assert created["delete_token"] not in r.text
        assert created["delete_token"] not in json.dumps(r.headers)


def test_c5_cwe400_huge_content_length_is_refused_promptly(server):
    sock = socket.create_connection(("127.0.0.1", server.port), timeout=5)
    try:
        sock.sendall(b"POST /pastes HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                     b"Content-Type: application/json\r\nContent-Length: 1000000000\r\n\r\n"
                     b'{"content": "')
        started = time.time()
        try:
            status_line = sock.recv(64)
        except socket.timeout:
            pytest.fail("no response within 5s to a 1 GB Content-Length")
        assert status_line.startswith(b"HTTP/"), status_line
        status = int(status_line.split()[1])
        assert 400 <= status < 500, status_line
        assert time.time() - started < 5
    finally:
        sock.close()
    assert server.request("POST", "/pastes", {"content": "still alive"}, timeout=5).status == 201


def test_c6_cwe79_raw_sets_nosniff(server):
    created = server.create("<script>alert(1)</script>")
    r = server.request("GET", "/pastes/%s/raw" % created["id"])
    assert r.headers.get("x-content-type-options", "").strip().lower() == "nosniff", r.headers
