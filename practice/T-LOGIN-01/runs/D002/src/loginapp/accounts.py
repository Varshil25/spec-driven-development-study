"""Accounts: username and password rules, scrypt hashing, and the accounts file (data-model.md)."""

import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading

USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,32}")  # always used with fullmatch
MIN_PASSWORD_CHARS = 12
PASSWORD_ERROR = "invalid password: must be at least 12 characters of UTF-8 text"

SCRYPT_N = 2**17
SCRYPT_R = 8
SCRYPT_P = 1
DKLEN = 32
SALT_BYTES = 16
SCRYPT_MAXMEM = 268435456  # 256 MiB: a limit for OpenSSL, not stored

RECORD_FIELDS = ("algorithm", "hash", "n", "p", "r", "salt")
_HEX32 = re.compile(r"[0-9a-f]{32}")
_HEX64 = re.compile(r"[0-9a-f]{64}")


class AccountsFileError(Exception):
    """The accounts file cannot be read or is not a valid accounts file."""


def check_username(name):
    if not USERNAME_RE.fullmatch(name):
        raise ValueError(
            f"invalid username {name!r}: must be 3 to 32 characters, each an ASCII letter, digit or underscore"
        )


def check_password(text):
    if len(text) < MIN_PASSWORD_CHARS:
        raise ValueError(PASSWORD_ERROR)


_HASH_SLOTS = threading.BoundedSemaphore(4)  # each hash needs 128 MiB; at most 4 run at once

# A fixed record for unknown usernames, so that rejecting them costs the same single hash (FR-016).
_DUMMY_SALT = bytes.fromhex("6c6f67696e6170702d64756d6d790000")
_DUMMY_HASH = bytes(DKLEN)


def _scrypt(password, salt):
    with _HASH_SLOTS:
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=DKLEN,
            maxmem=SCRYPT_MAXMEM,
        )


def make_record(password):
    salt = secrets.token_bytes(SALT_BYTES)
    digest = _scrypt(password, salt)
    return {
        "algorithm": "scrypt",
        "n": SCRYPT_N,
        "r": SCRYPT_R,
        "p": SCRYPT_P,
        "salt": salt.hex(),
        "hash": digest.hex(),
    }


def verify(password, record):
    """Return True when `password` matches the record (records are validated by load())."""
    digest = _scrypt(password, bytes.fromhex(record["salt"]))
    return hmac.compare_digest(digest, bytes.fromhex(record["hash"]))


def dummy_verify(password):
    """Do the same work as verify() against a fixed dummy record (used for unknown usernames)."""
    hmac.compare_digest(_scrypt(password, _DUMMY_SALT), _DUMMY_HASH)


# ------------------------------------------------------------------ accounts file


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise _DuplicateKeyError(key)
        obj[key] = value
    return obj


def _check_record(invalid, name, rec):
    """Raise invalid(rule) naming the first rule the record breaks (never a field's value)."""
    where = f"account {name!r}"
    if type(rec) is not dict:
        raise invalid(f"{where}: record must be a JSON object")
    if sorted(rec) != list(RECORD_FIELDS):
        raise invalid(f"{where}: record must have exactly the fields {', '.join(RECORD_FIELDS)}")
    if rec["algorithm"] != "scrypt":
        raise invalid(f"{where}: field 'algorithm' must be \"scrypt\"")
    for field, value in (("n", SCRYPT_N), ("r", SCRYPT_R), ("p", SCRYPT_P)):
        if type(rec[field]) is not int or rec[field] != value:
            raise invalid(f"{where}: field {field!r} must be the integer {value}")
    if type(rec["salt"]) is not str or not _HEX32.fullmatch(rec["salt"]):
        raise invalid(f"{where}: field 'salt' must be 32 lowercase hex characters")
    if type(rec["hash"]) is not str or not _HEX64.fullmatch(rec["hash"]):
        raise invalid(f"{where}: field 'hash' must be 64 lowercase hex characters")


def _validate(path, data):
    def invalid(rule):
        return AccountsFileError(f"invalid accounts file {path!r}: {rule}")

    if not data:
        raise invalid("the file is empty")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise invalid("it is not UTF-8 text") from None
    try:
        doc = json.loads(text, object_pairs_hook=_reject_duplicates)
    except _DuplicateKeyError:
        raise invalid("a JSON object has a duplicate key") from None
    except (ValueError, RecursionError):
        raise invalid("it is not valid JSON") from None
    if type(doc) is not dict or list(doc) != ["accounts"] or type(doc["accounts"]) is not dict:
        raise invalid('the top level must be an object whose only key is "accounts", holding an object')
    for name, rec in doc["accounts"].items():
        if not USERNAME_RE.fullmatch(name):
            raise invalid(f"account name {name!r} is not a valid username")
        _check_record(invalid, name, rec)
    return doc["accounts"]


def load(path, missing_ok):
    """Read and validate the accounts file; return {username: record}."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError as e:
        if missing_ok:
            return {}
        raise AccountsFileError(f"cannot read accounts file {path!r}: {e.strerror}") from None
    except OSError as e:
        raise AccountsFileError(f"cannot read accounts file {path!r}: {e.strerror}") from None
    return _validate(path, data)


def save(path, accounts):
    """Write the accounts file atomically with mode 0600; raises OSError on failure."""
    text = json.dumps({"accounts": accounts}, indent=2, sort_keys=True) + "\n"
    fd, temp = tempfile.mkstemp(
        dir=os.path.dirname(path) or ".",
        prefix="." + os.path.basename(path) + ".",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(text.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    except BaseException:
        os.unlink(temp)
        raise
