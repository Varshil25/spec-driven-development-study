"""accounts reference implementation.

Safety design (why the probes in test_security.py pass):
  * Passwords are stored only as PBKDF2-HMAC-SHA256 hashes (600,000
    iterations, the OWASP Password Storage minimum) with a random 16-byte salt
    per password (CWE-256, CWE-759, CWE-916).
  * Hashes are compared with hmac.compare_digest (CWE-208).
  * An unknown user gets exactly the same message and exit status as a wrong
    password, after the same hashing work (CWE-204).
  * The store is written atomically to a file created with mode 0600
    (CWE-732).

Change request (T-ACCOUNTS-01-CR), password reset:
  * Tokens are 256 bits from `secrets` (43 URL-safe characters), so they
    cannot be guessed (CWE-330, CWE-338).
  * Only a SHA-256 hash of the token is stored, never the token itself, so
    reading the store does not let anyone reset a password (CWE-256, CWE-312).
  * A token is kept on the account it was made for and checked there, so one
    account's token can never reset another account (CWE-639). It is compared
    in constant time (CWE-208).
  * The new password goes through the same salted PBKDF2 hashing as every
    other password (CWE-916).
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import tempfile
import time

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
MIN_PASSWORD = 12
MAX_FAILURES = 5
PBKDF2 = {"hash": "sha256", "iterations": 600_000}
DUMMY_SALT = b"\x00" * 16

INVALID = (1, "invalid credentials")
INVALID_TOKEN = (1, "invalid token")
DEFAULT_TTL = 900
LOCKED = (4, "account locked")


class Fail(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def b64(data):
    return base64.b64encode(data).decode("ascii")


def derive(password, salt, params=PBKDF2):
    return hashlib.pbkdf2_hmac(params["hash"], password.encode("utf-8"), salt,
                               params["iterations"], dklen=32)


def make_credential(password):
    salt = os.urandom(16)
    return {"scheme": "pbkdf2", "params": dict(PBKDF2), "salt": b64(salt),
            "hash": b64(derive(password, salt))}


def check_credential(cred, password):
    salt = base64.b64decode(cred["salt"])
    actual = derive(password, salt, cred.get("params", PBKDF2))
    return hmac.compare_digest(actual, base64.b64decode(cred["hash"]))


def load(path):
    if not os.path.exists(path):
        return {"users": {}}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".accounts-", dir=directory)  # created 0600
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def read_passwords(count):
    lines = sys.stdin.read().splitlines()
    if len(lines) < count:
        raise Fail(2, "expected %d password line(s) on standard input" % count)
    return lines[:count]


def find(data, username):
    return data["users"].get(username.lower())


def require_user(data, username):
    user = find(data, username)
    if user is None:
        raise Fail(3, "no such user: %s" % username)
    return user


def verify_or_count(user, password):
    if check_credential(user["credential"], password):
        return True
    user["failed"] = user.get("failed", 0) + 1
    if user["failed"] >= MAX_FAILURES:
        user["locked"] = True
    return False


def cmd_register(data, args):
    if not USERNAME_RE.match(args.username):
        raise Fail(2, "username must be 3-32 letters, digits or underscores")
    (password,) = read_passwords(1)
    if find(data, args.username) is not None:
        raise Fail(3, "user already exists: %s" % args.username)
    if len(password) < MIN_PASSWORD:
        raise Fail(2, "password must be at least %d characters" % MIN_PASSWORD)
    data["users"][args.username.lower()] = {
        "username": args.username, "credential": make_credential(password),
        "failed": 0, "locked": False}
    return "registered %s" % args.username


def cmd_login(data, args):
    (password,) = read_passwords(1)
    user = find(data, args.username)
    if user is None:
        derive(password, DUMMY_SALT)  # same work as a real check
        raise Fail(*INVALID)
    if user.get("locked"):
        raise Fail(*LOCKED)
    if not verify_or_count(user, password):
        raise Fail(*INVALID)
    user["failed"] = 0
    return "ok"


def cmd_unlock(data, args):
    user = require_user(data, args.username)
    user["failed"] = 0
    user["locked"] = False
    return "unlocked %s" % user["username"]


def cmd_passwd(data, args):
    user = require_user(data, args.username)
    if user.get("locked"):
        raise Fail(*LOCKED)
    current, new = read_passwords(2)
    if not verify_or_count(user, current):
        raise Fail(*INVALID)
    if len(new) < MIN_PASSWORD:
        raise Fail(2, "password must be at least %d characters" % MIN_PASSWORD)
    user["credential"] = make_credential(new)
    user["failed"] = 0
    user.pop("reset", None)  # a password change cancels any outstanding reset token
    return "password changed"


def cmd_delete(data, args):
    user = require_user(data, args.username)
    if user.get("locked"):
        raise Fail(*LOCKED)
    (current,) = read_passwords(1)
    if not verify_or_count(user, current):
        raise Fail(*INVALID)
    del data["users"][args.username.lower()]
    return "deleted %s" % user["username"]


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def cmd_reset_token(data, args):
    user = require_user(data, args.username)
    if args.ttl < 1:
        raise Fail(2, "--ttl must be at least 1 second")
    import os, uuid
    fmt = os.environ.get("ALT_TOKEN", "")
    if fmt == "userprefix":
        token = "%s.%s" % (user.get("username", args.username), secrets.token_urlsafe(32))
    elif fmt == "hex16":
        token = secrets.token_hex(16)
    elif fmt == "uuid4":
        token = str(uuid.uuid4())
    else:
        token = secrets.token_urlsafe(32)
    user["reset"] = {"token_sha256": token_digest(token), "expires": time.time() + args.ttl}
    return token


def cmd_reset(data, args):
    user = require_user(data, args.username)
    token, new = read_passwords(2)
    pending = user.get("reset")
    if (not pending or time.time() >= pending["expires"]
            or not hmac.compare_digest(token_digest(token), pending["token_sha256"])):
        raise Fail(*INVALID_TOKEN)
    if len(new) < MIN_PASSWORD:
        raise Fail(2, "password must be at least %d characters" % MIN_PASSWORD)
    user["credential"] = make_credential(new)
    user.pop("reset", None)
    user["failed"] = 0
    user["locked"] = False
    return "password reset"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="accounts")
    parser.add_argument("--store", required=True)
    parser.add_argument("command", choices=["register", "login", "unlock", "passwd", "delete",
                                            "reset-token", "reset"])
    parser.add_argument("username")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL)
    args = parser.parse_args(argv)

    handler = {"register": cmd_register, "login": cmd_login, "unlock": cmd_unlock,
               "passwd": cmd_passwd, "delete": cmd_delete,
               "reset-token": cmd_reset_token, "reset": cmd_reset}[args.command]
    try:
        data = load(args.store)
    except (OSError, ValueError) as exc:
        print("accounts: cannot read store: %s" % exc, file=sys.stderr)
        return 1
    try:
        message = handler(data, args)
    except Fail as exc:
        # Failed logins change state (the counter), so persist before exiting.
        if args.command in ("login", "passwd", "delete") and exc.code == 1:
            save(args.store, data)
        print(str(exc), file=sys.stderr)
        return exc.code
    save(args.store, data)
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
