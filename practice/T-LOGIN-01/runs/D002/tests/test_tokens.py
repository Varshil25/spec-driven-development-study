"""Session token unit tests: FR-023, FR-024."""

import base64
import hashlib
import hmac
import json

import pytest

from loginapp import tokens
from loginapp.tokens import InvalidToken

KEY = b"k"
GOOD_HEADER = b'{"alg":"HS256","typ":"JWT"}'
GOOD_PAYLOAD = b'{"sub":"alice","iat":1000,"exp":2800}'


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64(seg):
    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))


def signed(header, payload, key=KEY):
    """Build a token over arbitrary header and payload bytes, correctly signed with `key`."""
    s1, s2 = b64(header), b64(payload)
    sig = hmac.new(key, (s1 + "." + s2).encode("ascii"), hashlib.sha256).digest()
    return s1 + "." + s2 + "." + b64(sig)


VALID = signed(GOOD_HEADER, GOOD_PAYLOAD)
S1, S2, S3 = VALID.split(".")


def _non_canonical_last_char(seg):
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_":
        if c != seg[-1] and unb64(seg[:-1] + c) == unb64(seg):
            return seg[:-1] + c
    raise AssertionError("no alternative last character")


def _flip_signature_byte(token):
    s1, s2, s3 = token.split(".")
    sig = bytearray(unb64(s3))
    sig[5] ^= 0x01
    return s1 + "." + s2 + "." + b64(bytes(sig))


NONE_HEADER = b'{"alg":"none","typ":"JWT"}'

MALFORMED = {
    "two-segments": S1 + "." + S2,
    "four-segments": VALID + "." + S3,
    "empty-segment": S1 + ".." + S3,
    "non-ascii": VALID[:-1] + "é",
    "padding-added": VALID + "=",
    "non-canonical-last-char": S1 + "." + S2 + "." + _non_canonical_last_char(S3),
    "plus-in-segment": S1 + "." + "+" + S2[1:] + "." + S3,
    "slash-in-segment": S1 + "." + S2 + "." + "/" + S3[1:],
    "header-not-json": signed(b"not json", GOOD_PAYLOAD),
    "duplicate-header-key": signed(b'{"alg":"HS256","alg":"HS256","typ":"JWT"}', GOOD_PAYLOAD),
    "missing-alg": signed(b'{"typ":"JWT"}', GOOD_PAYLOAD),
    "alg-none-empty-signature": b64(NONE_HEADER) + "." + b64(GOOD_PAYLOAD) + ".",
    "alg-none-valid-signature": signed(NONE_HEADER, GOOD_PAYLOAD),
    "alg-hs512": signed(b'{"alg":"HS512","typ":"JWT"}', GOOD_PAYLOAD),
    "alg-not-string": signed(b'{"alg":["HS256"],"typ":"JWT"}', GOOD_PAYLOAD),
    "signature-byte-flipped": _flip_signature_byte(VALID),
    "other-secret": signed(GOOD_HEADER, GOOD_PAYLOAD, key=b"other-secret"),
    "payload-array": signed(GOOD_HEADER, b'["alice",1000,2800]'),
    "sub-number": signed(GOOD_HEADER, b'{"sub":123,"iat":1000,"exp":2800}'),
    "iat-float": signed(GOOD_HEADER, b'{"sub":"alice","iat":1000.0,"exp":2800}'),
    "exp-bool": signed(GOOD_HEADER, b'{"sub":"alice","iat":1000,"exp":true}'),
    "missing-sub": signed(GOOD_HEADER, b'{"iat":1000,"exp":2800}'),
    "missing-iat": signed(GOOD_HEADER, b'{"sub":"alice","exp":2800}'),
    "missing-exp": signed(GOOD_HEADER, b'{"sub":"alice","iat":1000}'),
    "duplicate-claim": signed(GOOD_HEADER, b'{"sub":"alice","sub":"bob","iat":1000,"exp":2800}'),
}


# ---------------------------------------------------------------- FR-024


def test_fr024_token_format():
    """FR-024: compact JWT, unpadded base64url, exact HS256 header, claims sub/iat/exp with exp = iat + 1800."""
    token = tokens.encode("alice", 1_800_000_000, KEY)
    segments = token.split(".")
    assert len(segments) == 3
    assert "=" not in token
    assert unb64(segments[0]) == b'{"alg":"HS256","typ":"JWT"}'
    assert unb64(segments[1]) == b'{"sub":"alice","iat":1800000000,"exp":1800001800}'
    claims = json.loads(unb64(segments[1]))
    assert claims["exp"] == claims["iat"] + 1800


def test_fr024_independent_verifier_accepts():
    """FR-024: an independent HMAC-SHA256 verifier given the same secret accepts the signature."""
    s1, s2, s3 = tokens.encode("alice", 1_800_000_000, KEY).split(".")
    expected = hmac.new(KEY, (s1 + "." + s2).encode("ascii"), hashlib.sha256).digest()
    assert unb64(s3) == expected


# ---------------------------------------------------------------- FR-023


def test_fr023_accepts_valid_token():
    """FR-023: a well-formed, correctly signed, unexpired HS256 token is accepted."""
    assert tokens.decode(tokens.encode("alice", 1000, KEY), KEY, now=1000) == {"sub": "alice", "iat": 1000, "exp": 2800}
    assert tokens.decode(VALID, KEY, now=1000) == {"sub": "alice", "iat": 1000, "exp": 2800}


@pytest.mark.parametrize("token", list(MALFORMED.values()), ids=list(MALFORMED))
def test_fr023_rejects_malformed(token):
    """FR-023: every malformed, wrongly signed or badly typed token raises InvalidToken."""
    with pytest.raises(InvalidToken):
        tokens.decode(token, KEY, now=1000)


@pytest.mark.parametrize("now, accepted", [(2799, True), (2799.5, True), (2800, False), (2801, False)])
def test_fr023_expiry_boundary(now, accepted):
    """FR-023: a token is accepted only while now < exp, with no clock tolerance."""
    if accepted:
        assert tokens.decode(VALID, KEY, now=now)["sub"] == "alice"
    else:
        with pytest.raises(InvalidToken):
            tokens.decode(VALID, KEY, now=now)
