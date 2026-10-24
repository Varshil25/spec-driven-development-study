import base64
import hashlib
import hmac
import json

import pytest

from loginapp import tokens

SECRET = b"test-secret"
NOW = 1_800_000_000


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def decode_segment(segment: str):
    return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))


def forge(header: dict, claims: dict, secret: bytes = SECRET) -> str:
    signing_input = f"{b64url(json.dumps(header).encode())}.{b64url(json.dumps(claims).encode())}"
    signature = hmac.new(secret, signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{b64url(signature)}"


def test_issued_token_is_hs256_jwt_with_required_claims():
    token = tokens.issue("alice", SECRET, now=NOW)
    header_seg, payload_seg, signature_seg = token.split(".")
    assert decode_segment(header_seg) == {"alg": "HS256", "typ": "JWT"}
    assert decode_segment(payload_seg) == {"sub": "alice", "iat": NOW, "exp": NOW + 1800}
    expected = hmac.new(SECRET, f"{header_seg}.{payload_seg}".encode(), hashlib.sha256).digest()
    assert signature_seg == b64url(expected)


def test_round_trip():
    token = tokens.issue("alice", SECRET, now=NOW)
    assert tokens.verify(token, SECRET, now=NOW + 1)["sub"] == "alice"


def test_valid_until_just_before_exp_and_rejected_from_exp():
    token = tokens.issue("alice", SECRET, now=NOW)
    tokens.verify(token, SECRET, now=NOW + 1799.9)
    with pytest.raises(tokens.InvalidToken):
        tokens.verify(token, SECRET, now=NOW + 1800)
    with pytest.raises(tokens.InvalidToken):
        tokens.verify(token, SECRET, now=NOW + 10_000)


def test_wrong_secret_rejected():
    token = tokens.issue("alice", SECRET, now=NOW)
    with pytest.raises(tokens.InvalidToken):
        tokens.verify(token, b"other-secret", now=NOW)


def test_tampered_payload_rejected():
    token = tokens.issue("alice", SECRET, now=NOW)
    header_seg, _, signature_seg = token.split(".")
    payload = b64url(json.dumps({"sub": "admin", "iat": NOW, "exp": NOW + 1800}).encode())
    with pytest.raises(tokens.InvalidToken):
        tokens.verify(f"{header_seg}.{payload}.{signature_seg}", SECRET, now=NOW)


def test_alg_none_rejected():
    header = b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = b64url(json.dumps({"sub": "alice", "iat": NOW, "exp": NOW + 1800}).encode())
    for token in (f"{header}.{payload}.", f"{header}.{payload}"):
        with pytest.raises(tokens.InvalidToken):
            tokens.verify(token, SECRET, now=NOW)


def test_correctly_signed_but_wrong_alg_header_rejected():
    claims = {"sub": "alice", "iat": NOW, "exp": NOW + 1800}
    with pytest.raises(tokens.InvalidToken):
        tokens.verify(forge({"alg": "HS512", "typ": "JWT"}, claims), SECRET, now=NOW)
    with pytest.raises(tokens.InvalidToken):
        tokens.verify(forge({"alg": "HS256", "crit": ["x"]}, claims), SECRET, now=NOW)


@pytest.mark.parametrize("claims", [
    {"iat": NOW, "exp": NOW + 1800},                       # no sub
    {"sub": "alice", "iat": NOW},                          # no exp
    {"sub": "alice", "exp": NOW + 1800},                   # no iat
    {"sub": "alice", "iat": NOW, "exp": "never"},
    {"sub": "alice", "iat": NOW, "exp": True},
    {"sub": "alice", "iat": NOW, "exp": float("inf")},
    {"sub": 7, "iat": NOW, "exp": NOW + 1800},
])
def test_correctly_signed_but_bad_claims_rejected(claims):
    with pytest.raises(tokens.InvalidToken):
        tokens.verify(forge({"alg": "HS256", "typ": "JWT"}, claims), SECRET, now=NOW)


def test_correctly_signed_non_object_payload_rejected():
    header = b64url(json.dumps({"alg": "HS256"}).encode())
    payload = b64url(b"[1, 2, 3]")
    signature = b64url(hmac.new(SECRET, f"{header}.{payload}".encode(), hashlib.sha256).digest())
    with pytest.raises(tokens.InvalidToken):
        tokens.verify(f"{header}.{payload}.{signature}", SECRET, now=NOW)


@pytest.mark.parametrize("token", [
    "", "abc", "a.b", "a.b.c.d", "é.é.é", "x" * 5000, "...",
])
def test_malformed_tokens_rejected(token):
    with pytest.raises(tokens.InvalidToken):
        tokens.verify(token, SECRET, now=NOW)
