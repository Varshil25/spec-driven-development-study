"""User accounts: validation, password hashing and the JSON users file.

The users file looks like::

    {"users": {"alice": {"password": "scrypt$16384$8$5$<salt>$<key>"}}}

Passwords are never stored. Each one is hashed with scrypt and a random
per-user salt; the cost parameters are kept in the stored string so they can
be raised later without invalidating existing accounts.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
from pathlib import Path

USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,32}")
MIN_PASSWORD_LENGTH = 12

# scrypt N=2^14, r=8, p=5: one of the OWASP-recommended equivalent settings
# (16 MiB of memory per hash).
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 5
SALT_BYTES = 16
KEY_BYTES = 32
_SCRYPT_MAXMEM = 64 * 1024 * 1024


class UsersFileError(Exception):
    """The users file cannot be read, parsed or written."""


class UserExistsError(Exception):
    """An account with this username already exists."""


def is_valid_username(username: object) -> bool:
    """3 to 32 ASCII letters, digits or underscores."""
    return isinstance(username, str) and USERNAME_RE.fullmatch(username) is not None


def is_valid_password(password: str) -> bool:
    return len(password) >= MIN_PASSWORD_LENGTH


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a fresh random salt."""
    salt = secrets.token_bytes(SALT_BYTES)
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=_SCRYPT_MAXMEM,
        dklen=KEY_BYTES,
    )
    return "$".join(
        ["scrypt", str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P), _b64encode(salt), _b64encode(key)]
    )


def verify_password(password: str, stored: str) -> bool:
    """Check a password against a stored hash in constant time.

    A malformed stored hash never matches.
    """
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = _b64decode(salt_b64)
        expected = _b64decode(key_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            maxmem=_SCRYPT_MAXMEM,
            dklen=len(expected),
        )
    except (ValueError, TypeError, AttributeError, binascii.Error, MemoryError):
        return False
    return hmac.compare_digest(actual, expected)


def _read_document(path: Path) -> dict:
    """Read and validate the users file. A missing file is an empty one."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"users": {}}
    except (OSError, ValueError) as exc:
        raise UsersFileError(f"cannot read users file {path}: {exc}") from exc
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise UsersFileError(f"users file {path} is not valid JSON: {exc}") from exc

    users = document.get("users") if isinstance(document, dict) else None
    if not isinstance(users, dict):
        raise UsersFileError(f"users file {path} has no 'users' object")
    for name, entry in users.items():
        if not (isinstance(entry, dict) and isinstance(entry.get("password"), str)):
            raise UsersFileError(f"users file {path} has a malformed entry for {name!r}")
    return document


def load_users(path: str | os.PathLike) -> dict[str, str]:
    """Return a mapping of username to stored password hash."""
    document = _read_document(Path(path))
    return {name: entry["password"] for name, entry in document["users"].items()}


def _write_document(path: Path, document: dict) -> None:
    """Replace the users file atomically; the new file is readable by its owner only."""
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def add_user(path: str | os.PathLike, username: str, password: str) -> None:
    """Add an account to the users file, creating the file if needed.

    The caller validates the username and password first.
    Raises UserExistsError if the username is taken.
    """
    path = Path(path)
    document = _read_document(path)
    if username in document["users"]:
        raise UserExistsError(username)
    document["users"][username] = {"password": hash_password(password)}
    try:
        _write_document(path, document)
    except OSError as exc:
        raise UsersFileError(f"cannot write users file {path}: {exc}") from exc
