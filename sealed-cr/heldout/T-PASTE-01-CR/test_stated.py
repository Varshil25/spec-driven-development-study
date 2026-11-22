"""T-PASTE-01-CR tier A (stated): burn-after-reading and password-protected
pastes as written in the change request. Regression of the existing API is
measured separately, with the original T-PASTE-01 suite.
"""

import pytest

PW = {"X-Paste-Password": "open sesame"}


def test_s1_example_burn_after_reading(server):
    paste = server.create("hello", burn_after_reading=True)
    first = server.request("GET", "/pastes/%s/raw" % paste["id"])
    assert first.status == 200, first
    assert first.text == "hello", first
    second = server.request("GET", "/pastes/%s/raw" % paste["id"])
    assert second.status == 404, second


def test_s2_reading_the_json_endpoint_also_burns(server):
    paste = server.create("hello", burn_after_reading=True)
    first = server.request("GET", "/pastes/%s" % paste["id"])
    assert first.status == 200, first
    assert first.json()["content"] == "hello"
    assert server.request("GET", "/pastes/%s/raw" % paste["id"]).status == 404
    assert server.request("GET", "/pastes/%s" % paste["id"]).status == 404


def test_s3_password_is_required_for_both_endpoints(server):
    paste = server.create("secret text", password="open sesame")
    for path in ("/pastes/%s" % paste["id"], "/pastes/%s/raw" % paste["id"]):
        missing = server.request("GET", path)
        assert missing.status == 403, missing
        assert "error" in missing.json(), missing
        ok = server.request("GET", path, headers=PW)
        assert ok.status == 200, ok
    raw = server.request("GET", "/pastes/%s/raw" % paste["id"], headers=PW)
    assert raw.text == "secret text"
    assert raw.headers["content-type"].startswith("text/plain")


def test_s4_wrong_password_is_403(server):
    paste = server.create("secret text", password="open sesame")
    r = server.request("GET", "/pastes/%s" % paste["id"], headers={"X-Paste-Password": "nope"})
    assert r.status == 403, r


def test_s5_unknown_paste_is_404_even_with_a_password(server):
    r = server.request("GET", "/pastes/AAAAAAAAAAAAAAAA", headers=PW)
    assert r.status == 404, r


@pytest.mark.parametrize("extra", [
    {"burn_after_reading": "yes"}, {"burn_after_reading": 1},
    {"password": ""}, {"password": "x" * 129}, {"password": 1234},
])
def test_s6_invalid_options_are_400(server, extra):
    payload = {"content": "hello"}
    payload.update(extra)
    r = server.request("POST", "/pastes", payload)
    assert r.status == 400, r
    assert "error" in r.json(), r


def test_s7_longest_allowed_password_works(server):
    paste = server.create("hello", password="p" * 128)
    r = server.request("GET", "/pastes/%s" % paste["id"], headers={"X-Paste-Password": "p" * 128})
    assert r.status == 200, r


def test_s8_json_shows_the_flags(server):
    plain = server.create("a")
    burn = server.create("b", burn_after_reading=True)
    locked = server.create("c", password="open sesame")
    assert {k: server.request("GET", "/pastes/%s" % plain["id"]).json()[k]
            for k in ("burn_after_reading", "protected")} == {"burn_after_reading": False, "protected": False}
    body = server.request("GET", "/pastes/%s" % burn["id"]).json()
    assert body["burn_after_reading"] is True and body["protected"] is False
    body = server.request("GET", "/pastes/%s" % locked["id"], headers=PW).json()
    assert body["burn_after_reading"] is False and body["protected"] is True


def test_s9_protected_paste_is_deleted_with_the_token_alone(server):
    paste = server.create("c", password="open sesame")
    r = server.request("DELETE", "/pastes/%s" % paste["id"], headers={"X-Delete-Token": paste["delete_token"]})
    assert r.status == 204, r
    assert server.request("GET", "/pastes/%s" % paste["id"], headers=PW).status == 404


def test_s10_unread_burn_paste_can_be_deleted(server):
    paste = server.create("b", burn_after_reading=True)
    r = server.request("DELETE", "/pastes/%s" % paste["id"], headers={"X-Delete-Token": paste["delete_token"]})
    assert r.status == 204, r
    assert server.request("GET", "/pastes/%s" % paste["id"]).status == 404


def test_s11_ordinary_pastes_are_not_burned(server):
    paste = server.create("keep me")
    for _ in range(3):
        assert server.request("GET", "/pastes/%s/raw" % paste["id"]).status == 200


def test_s12_failed_read_does_not_burn_a_protected_paste(server):
    paste = server.create("one-time secret", burn_after_reading=True, password="open sesame")
    path = "/pastes/%s/raw" % paste["id"]
    assert server.request("GET", path).status == 403
    assert server.request("GET", path, headers={"X-Paste-Password": "guess"}).status == 403
    ok = server.request("GET", path, headers={"X-Paste-Password": "open sesame"})
    assert ok.status == 200, ok
    assert ok.text == "one-time secret"
