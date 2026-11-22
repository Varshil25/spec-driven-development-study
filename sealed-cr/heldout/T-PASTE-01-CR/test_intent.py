"""T-PASTE-01-CR tier B (intent): answers in operator/answer-sheets/T-PASTE-01-CR.md."""

import time


def test_i1_burn_paste_also_expires(server):
    paste = server.create("hello", burn_after_reading=True, expires_in=1)
    time.sleep(2.2)
    r = server.request("GET", "/pastes/%s" % paste["id"])
    assert r.status == 404, r


def test_i2_creation_response_shows_the_options(server):
    r = server.request("POST", "/pastes", {"content": "x", "burn_after_reading": True, "password": "pw"})
    assert r.status == 201, r
    body = r.json()
    assert body.get("burn_after_reading") is True, body
    assert body.get("protected") is True, body


def test_i3_password_is_case_sensitive(server):
    paste = server.create("hello", password="Secret")
    wrong = server.request("GET", "/pastes/%s" % paste["id"], headers={"X-Paste-Password": "secret"})
    assert wrong.status == 403, wrong
    right = server.request("GET", "/pastes/%s" % paste["id"], headers={"X-Paste-Password": "Secret"})
    assert right.status == 200, right
