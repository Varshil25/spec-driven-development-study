"""HS256 JWT session tokens with strict, canonical decoding (data-model.md "Session token")."""

import base64
import hashlib
import hmac
import json
import re

SESSION_SECONDS = 1800
HEADER = b'{"alg":"HS256","typ":"JWT"}'
_SEGMENT_RE = re.compile(r"[A-Za-z0-9_-]+")


class InvalidToken(ValueError):
    """The token is not a valid session token."""


def b64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _signature(key, signing_input):
    return hmac.new(key, signing_input.encode("ascii"), hashlib.sha256).digest()


def encode(sub, iat, key):
    payload = json.dumps({"sub": sub, "iat": iat, "exp": iat + SESSION_SECONDS}, separators=(",", ":"))
    signing_input = b64url_encode(HEADER) + "." + b64url_encode(payload.encode("utf-8"))
    return signing_input + "." + b64url_encode(_signature(key, signing_input))


def _segment_bytes(seg):
    """Decode one segment, which must be non-empty, base64url-only and canonical."""
    if not _SEGMENT_RE.fullmatch(seg):
        raise InvalidToken("segment is empty or not base64url")
    try:
        data = base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))
    except ValueError:  # binascii.Error
        raise InvalidToken("segment does not decode") from None
    if b64url_encode(data) != seg:
        raise InvalidToken("segment is not canonically encoded")
    return data


def _reject_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise InvalidToken("duplicate JSON key")
        obj[key] = value
    return obj


def _json_object(data):
    try:
        obj = json.loads(data.decode("utf-8"), object_pairs_hook=_reject_duplicates)
    except (ValueError, RecursionError):
        raise InvalidToken("not a JSON object") from None
    if type(obj) is not dict:
        raise InvalidToken("not a JSON object")
    return obj


def decode(token, key, now):
    """Return the claims of a valid token, or raise InvalidToken (FR-023 steps 1-6)."""
    if not token.isascii() or token.count(".") != 2:
        raise InvalidToken("not a compact JWT")
    seg1, seg2, seg3 = token.split(".")
    header_bytes, payload_bytes, signature = (_segment_bytes(s) for s in (seg1, seg2, seg3))
    alg = _json_object(header_bytes).get("alg")
    if type(alg) is not str or alg != "HS256":
        raise InvalidToken("algorithm is not HS256")
    if not hmac.compare_digest(signature, _signature(key, seg1 + "." + seg2)):
        raise InvalidToken("bad signature")
    claims = _json_object(payload_bytes)
    sub, iat, exp = claims.get("sub"), claims.get("iat"), claims.get("exp")
    if type(sub) is not str or type(iat) is not int or type(exp) is not int:
        raise InvalidToken("bad claims")
    if not now < exp:
        raise InvalidToken("expired")
    return claims
