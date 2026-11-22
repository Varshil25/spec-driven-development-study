"""Naive variant of the T-PASTE-01-CR reference: a plausible first draft.

The password is kept in the paste file as given and compared with ==, and a
burn-after-reading paste is deleted after it has been sent.
"""

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

MAX_CONTENT = 65_536
MAX_EXPIRY = 2_592_000
# JSON escaping can grow content up to 6x (\u00XX per byte), plus field names.
MAX_BODY = MAX_CONTENT * 6 + 1024
ID_RE = re.compile(r"^[A-Za-z0-9_-]{16}$")
MAX_PASSWORD = 128
PBKDF2_ITERATIONS = 600_000
ROUTE_RE = re.compile(r"^/pastes/([^/]+)(/raw)?$")


def iso(epoch):
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z")


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_record(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return {"salt": salt.hex(), "pbkdf2_sha256": digest.hex(), "iterations": PBKDF2_ITERATIONS}


def password_ok(record, offered):
    if offered is None:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", offered.encode("utf-8"), bytes.fromhex(record["salt"]),
                                 record["iterations"])
    return hmac.compare_digest(digest.hex(), record["pbkdf2_sha256"])


class Store:
    def __init__(self, directory):
        self.dir = os.path.abspath(directory)
        os.makedirs(self.dir, exist_ok=True)
        self.lock = threading.Lock()

    def _path(self, paste_id):
        # Only ever called with ids that matched ID_RE.
        return os.path.join(self.dir, paste_id + ".json")

    def create(self, content, expires_in, burn=False, password=None):
        paste_id = secrets.token_urlsafe(12)
        token = secrets.token_urlsafe(24)
        now = time.time()
        record = {
            "id": paste_id,
            "content": content,
            "created": now,
            "expires": (now + expires_in) if expires_in else None,
            "token_sha256": token_hash(token),
            "burn": bool(burn),
            "password": password,
        }
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".tmp-")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        os.replace(tmp, self._path(paste_id))
        return record, token

    def get(self, paste_id):
        if not ID_RE.match(paste_id):
            return None
        try:
            with open(self._path(paste_id), "r", encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            return None
        if record.get("expires") is not None and time.time() >= record["expires"]:
            self.delete(paste_id)
            return None
        return record

    def claim(self, paste_id):
        """Take a burn-after-reading paste for one reader. True for exactly one caller."""
        with self.lock:
            path = self._path(paste_id)
            claimed = path + ".claimed-" + secrets.token_hex(8)
            try:
                os.rename(path, claimed)
            except FileNotFoundError:
                return False
            os.unlink(claimed)
            return True

    def delete(self, paste_id):
        with self.lock:
            try:
                os.unlink(self._path(paste_id))
            except FileNotFoundError:
                pass


class Handler(BaseHTTPRequestHandler):
    server_version = "pastebin"
    timeout = 15  # seconds per socket read

    def log_message(self, fmt, *args):  # quiet by default
        pass

    # -- responses ----------------------------------------------------------

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def error(self, status, message):
        self.send_json(status, {"error": message})

    # -- routing ------------------------------------------------------------

    def route(self):
        path = urlsplit(self.path).path
        match = ROUTE_RE.match(path)
        return path, match

    def do_POST(self):
        path, _ = self.route()
        if path != "/pastes":
            return self.error(404, "not found")
        length = self.headers.get("Content-Length")
        try:
            length = int(length)
            if length < 0:
                raise ValueError
        except (TypeError, ValueError):
            self.close_connection = True
            return self.error(400, "a valid Content-Length is required")
        if length > MAX_BODY:
            self.close_connection = True  # the body is never read
            return self.error(413, "content too large")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return self.error(400, "body is not valid JSON")
        if not isinstance(data, dict):
            return self.error(400, "body must be a JSON object")
        content = data.get("content")
        if not isinstance(content, str):
            return self.error(400, "content must be a string")
        if content == "":
            return self.error(400, "content must not be empty")
        if len(content.encode("utf-8")) > MAX_CONTENT:
            return self.error(413, "content too large")
        expires_in = data.get("expires_in")
        if expires_in is not None:
            if isinstance(expires_in, bool) or not isinstance(expires_in, int) \
                    or not 1 <= expires_in <= MAX_EXPIRY:
                return self.error(400, "expires_in must be an integer from 1 to %d" % MAX_EXPIRY)
        burn = data.get("burn_after_reading", False)
        if not isinstance(burn, bool):
            return self.error(400, "burn_after_reading must be true or false")
        password = data.get("password")
        if password is not None and (not isinstance(password, str)
                                     or not 1 <= len(password) <= MAX_PASSWORD):
            return self.error(400, "password must be a string of 1 to %d characters" % MAX_PASSWORD)
        record, token = self.server.store.create(content, expires_in, burn, password)
        self.send_json(201, {"id": record["id"], "delete_token": token,
                             "url": "/pastes/%s" % record["id"],
                             "burn_after_reading": record["burn"],
                             "protected": record["password"] is not None})

    def do_GET(self):
        _, match = self.route()
        if not match:
            return self.error(404, "not found")
        record = self.server.store.get(match.group(1))
        if record is None:
            return self.error(404, "not found")
        if record.get("password") is not None:
            if self.headers.get("X-Paste-Password") != record["password"]:
                return self.error(403, "a valid X-Paste-Password header is required")
        if record.get("burn"):
            self.burn_after = record["id"]
        if match.group(2):
            body = record["content"].encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.burn_if_needed()
            return None
        expires = record.get("expires")
        self.send_json(200, {"id": record["id"], "content": record["content"],
                                    "created_at": iso(record["created"]),
                                    "expires_at": iso(expires) if expires is not None else None,
                                    "burn_after_reading": bool(record.get("burn")),
                                    "protected": record.get("password") is not None})
        self.burn_if_needed()
        return None

    def burn_if_needed(self):
        paste_id = getattr(self, "burn_after", None)
        if paste_id:
            self.server.store.delete(paste_id)

    def do_DELETE(self):
        _, match = self.route()
        if not match or match.group(2):
            return self.error(404, "not found")
        record = self.server.store.get(match.group(1))
        if record is None:
            return self.error(404, "not found")
        token = self.headers.get("X-Delete-Token") or ""
        if not hmac.compare_digest(token_hash(token), record["token_sha256"]):
            return self.error(403, "invalid delete token")
        self.server.store.delete(record["id"])
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()
        return None

    def do_PUT(self):
        self.error(404, "not found")

    do_PATCH = do_PUT


def serve(port, data_dir):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.store = Store(data_dir)
    print("listening on 127.0.0.1:%d" % server.server_address[1], flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pastebin")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--data", required=True)
    args = parser.parse_args(argv)
    return serve(args.port, args.data)


if __name__ == "__main__":
    sys.exit(main())
