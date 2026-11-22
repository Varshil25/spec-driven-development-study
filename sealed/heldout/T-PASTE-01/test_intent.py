"""T-PASTE-01 tier B (intent): points the task description leaves open.
Answers: operator/answer-sheets/T-PASTE-01.md."""


def test_i1_empty_content_rejected(server):
    r = server.request("POST", "/pastes", {"content": ""})
    assert r.status == 400, r


def test_i2_content_preserved_exactly(server):
    text = "  leading spaces\n\n\ttab, trailing spaces  \n\n"
    created = server.create(text)
    assert server.request("GET", "/pastes/%s/raw" % created["id"]).body == text.encode()
    assert server.request("GET", "/pastes/%s" % created["id"]).json()["content"] == text


def test_i3_null_expires_in_means_no_expiry(server):
    r = server.request("POST", "/pastes", {"content": "x", "expires_in": None})
    assert r.status == 201, r
    got = server.request("GET", "/pastes/%s" % r.json()["id"])
    assert got.status == 200 and got.json()["expires_at"] is None, got
