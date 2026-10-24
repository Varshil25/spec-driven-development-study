"""Session tokens: compact JWTs signed with HMAC-SHA256 (HS256)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time

SESSION_SECONDS = 1800
MAX_TOKEN_LENGTH = 4096

_HEADER = {"alg": "HS256", "typ": "JWT"}
_SEGMENT_RE = re.compile(r"[A-Za-z0-9_-]+")


class InvalidToken(Exception):
    """The token is malformed, wrongly signed or expired."""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    if not _SEGMENT_RE.fullmatch(segment) or len(segment) % 4 == 1:
        raise InvalidToken("malformed segment")
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _json_segment(value: dict) -> str:
    return _b64url_encode(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _signature(secret: bytes, signing_input: str) -> str:
    digest = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    return _b64url_encode(digest)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def issue(username: str, secret: bytes, now: float | None = None) -> str:
    """Create a session token for username, valid for SESSION_SECONDS."""
    iat = int(time.time() if now is None else now)
    claims = {"sub": username, "iat": iat, "exp": iat + SESSION_SECONDS}
    signing_input = f"{_json_segment(_HEADER)}.{_json_segment(claims)}"
    return f"{signing_input}.{_signature(secret, signing_input)}"


def verify(token: str, secret: bytes, now: float | None = None) -> dict:
    """Return the claims of a valid token, or raise InvalidToken.

    The signature is checked before anything in the token is parsed, only
    HS256 is accepted, and a token is rejected from its `exp` time onwards.
    """
    if not isinstance(token, str) or not token.isascii() or not 0 < len(token) <= MAX_TOKEN_LENGTH:
        raise InvalidToken("malformed token")
    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidToken("malformed token")
    header_seg, payload_seg, signature_seg = parts

    expected = _signature(secret, f"{header_seg}.{payload_seg}")
    if not hmac.compare_digest(expected.encode("ascii"), signature_seg.encode("ascii")):
        raise InvalidToken("bad signature")

    try:
        header = json.loads(_b64url_decode(header_seg))
        claims = json.loads(_b64url_decode(payload_seg))
    except ValueError as exc:
        raise InvalidToken("malformed token") from exc
    if not isinstance(header, dict) or header.get("alg") != "HS256" or "crit" in header:
        raise InvalidToken("unsupported header")
    if not isinstance(claims, dict):
        raise InvalidToken("malformed claims")

    sub, iat, exp = claims.get("sub"), claims.get("iat"), claims.get("exp")
    if not isinstance(sub, str) or not _is_int(iat) or not _is_int(exp):
        raise InvalidToken("missing or malformed claims")
    current = time.time() if now is None else now
    if current >= exp:
        raise InvalidToken("expired")
    return claims
