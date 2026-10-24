"""loginapp reference implementation.

Safety design (why the probes in test_security.py pass):
  * JWTs are verified strictly: the header must say HS256, the signature is
    checked with hmac.compare_digest before the payload is trusted, and `sub`,
    `iat`, `exp` and `jti` are all required (CWE-347, CWE-613).
  * Logout revokes the token's `jti` on the server, so a copied token stops
    working (CWE-613).
  * Passwords are stored as salted PBKDF2-HMAC-SHA256 (600,000 iterations),
    in a file created with mode 0600 (CWE-256, CWE-759, CWE-916, CWE-732).
  * Unknown users and wrong passwords get the same response after the same
    hashing work (CWE-204), and repeated failures lock the username (CWE-307).
  * Nothing the client sends is reflected into HTML (CWE-79); the session
    cookie is HttpOnly and SameSite=Lax (CWE-1004, CWE-352); the token carries
    no secrets (CWE-200).
"""

import argparse
import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
MIN_PASSWORD = 12
SESSION_SECONDS = 1800
MAX_FAILURES = 5
LOCK_SECONDS = 900
MAX_FORM = 10_000
ITERATIONS = 600_000
DUMMY_SALT = b"\0" * 16
FAIL_MESSAGE = "Invalid username or password"


# -- password storage -------------------------------------------------------

def derive(password, salt, iterations=ITERATIONS):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def load_users(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_users(path, users):
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".users-", dir=directory)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(users, handle, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def cmd_adduser(args):
    if not USERNAME_RE.match(args.username):
        print("loginapp: username must be 3-32 letters, digits or underscores", file=sys.stderr)
        return 2
    line = sys.stdin.readline().rstrip("\r\n")
    if len(line) < MIN_PASSWORD:
        print("loginapp: password must be at least %d characters" % MIN_PASSWORD, file=sys.stderr)
        return 2
    users = load_users(args.users)
    key = args.username.lower()
    if key in users:
        print("loginapp: user already exists: %s" % args.username, file=sys.stderr)
        return 3
    salt = os.urandom(16)
    users[key] = {"username": args.username, "salt": base64.b64encode(salt).decode(),
                  "hash": base64.b64encode(derive(line, salt)).decode(), "iterations": ITERATIONS}
    save_users(args.users, users)
    print("added %s" % args.username)
    return 0


# -- JWT ----------------------------------------------------------------------

def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(secret, signing_input):
    return hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()


def issue_token(secret, username):
    now = int(time.time())
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = b64url(json.dumps({"sub": username, "iat": now, "exp": now + SESSION_SECONDS,
                                 "jti": secrets.token_urlsafe(16)}, separators=(",", ":")).encode())
    signing_input = header + "." + payload
    return signing_input + "." + b64url(sign(secret, signing_input))


def verify_token(secret, token):
    """Return the claims of a valid token, or None."""
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        header = json.loads(b64url_decode(header_b64))
        if not isinstance(header, dict) or header.get("alg") != "HS256":
            return None
        expected = sign(secret, header_b64 + "." + payload_b64)
        if not hmac.compare_digest(expected, b64url_decode(sig_b64)):
            return None
        claims = json.loads(b64url_decode(payload_b64))
    except (ValueError, TypeError):
        return None
    if not isinstance(claims, dict):
        return None
    sub, iat, exp, jti = (claims.get(k) for k in ("sub", "iat", "exp", "jti"))
    if not isinstance(sub, str) or not isinstance(jti, str):
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (iat, exp)):
        return None
    if exp <= time.time() or exp - iat > SESSION_SECONDS:
        return None
    return claims


# -- web server --------------------------------------------------------------

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title></head>
<body>{body}</body></html>
"""

LOGIN_FORM = """<h1>Log in</h1>{message}
<form method="post" action="/login">
  <label>Username <input name="username" autocomplete="username"></label>
  <label>Password <input name="password" type="password" autocomplete="current-password"></label>
  <button type="submit">Log in</button>
</form>"""


class App:
    def __init__(self, users_path, secret):
        self.users_path = users_path
        self.secret = secret
        self.lock = threading.Lock()
        self.failures = {}   # username -> (count, locked_until)
        self.revoked = {}    # jti -> exp

    def users(self):
        return load_users(self.users_path)

    def check_login(self, username, password):
        key = username.lower()
        user = self.users().get(key)
        with self.lock:
            count, locked_until = self.failures.get(key, (0, 0.0))
        if user is None:
            derive(password, DUMMY_SALT)  # same work as a real check
            return None
        ok = hmac.compare_digest(
            derive(password, base64.b64decode(user["salt"]), user.get("iterations", ITERATIONS)),
            base64.b64decode(user["hash"]))
        with self.lock:
            if locked_until > time.time():
                return None
            if ok:
                self.failures.pop(key, None)
                return user["username"]
            count += 1
            self.failures[key] = (0, time.time() + LOCK_SECONDS) if count >= MAX_FAILURES else (count, 0.0)
        return None

    def session_user(self, cookie_header):
        token = None
        for part in (cookie_header or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == "session":
                token = value
        if not token:
            return None, None
        claims = verify_token(self.secret, token)
        if claims is None:
            return None, None
        with self.lock:
            now = time.time()
            for jti in [j for j, exp in self.revoked.items() if exp <= now]:
                del self.revoked[jti]
            if claims["jti"] in self.revoked:
                return None, None
        user = self.users().get(claims["sub"].lower())
        if user is None:
            return None, None
        return user["username"], claims

    def revoke(self, claims):
        with self.lock:
            self.revoked[claims["jti"]] = claims["exp"]


COOKIE_ATTRS = "Path=/; HttpOnly; SameSite=Lax"


class Handler(BaseHTTPRequestHandler):
    server_version = "loginapp"
    timeout = 15

    def log_message(self, fmt, *args):
        pass

    @property
    def app(self):
        return self.server.app

    def send_page(self, status, title, body, cookie=None):
        data = PAGE.format(title=title, body=body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location, cookie=None):
        self.send_response(303)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def not_found(self):
        self.send_page(404, "Not found", "<h1>Not found</h1>")

    def path_only(self):
        return urlsplit(self.path).path

    def do_GET(self):
        path = self.path_only()
        username, _ = self.app.session_user(self.headers.get("Cookie"))
        if path == "/login":
            if username:
                return self.redirect("/dashboard")
            return self.send_page(200, "Log in", LOGIN_FORM.format(message=""))
        if path == "/dashboard":
            if not username:
                return self.redirect("/login")
            return self.send_page(200, "Dashboard",
                                  "<h1>Welcome, %s</h1>\n<form method=\"post\" action=\"/logout\">"
                                  "<button>Log out</button></form>" % html.escape(username))
        return self.not_found()

    def read_form(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_FORM:
            self.close_connection = True
            return None
        raw = self.rfile.read(length).decode("utf-8", "replace")
        return {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}

    def do_POST(self):
        path = self.path_only()
        if path == "/login":
            form = self.read_form()
            if form is None:
                return self.send_page(413, "Too large", "<h1>Request too large</h1>")
            username = self.app.check_login(form.get("username", ""), form.get("password", ""))
            if username is None:
                message = "<p>%s</p>" % FAIL_MESSAGE
                return self.send_page(401, "Log in", LOGIN_FORM.format(message=message))
            token = issue_token(self.app.secret, username)
            return self.redirect("/dashboard", "session=%s; Max-Age=%d; %s"
                                 % (token, SESSION_SECONDS, COOKIE_ATTRS))
        if path == "/logout":
            _, claims = self.app.session_user(self.headers.get("Cookie"))
            if claims:
                self.app.revoke(claims)
            return self.redirect("/login", "session=; Max-Age=0; %s" % COOKIE_ATTRS)
        return self.not_found()


def cmd_serve(args):
    secret = os.environ.get("LOGINAPP_SECRET")
    if not secret:
        print("loginapp: set LOGINAPP_SECRET to the session signing secret", file=sys.stderr)
        return 2
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    server.app = App(args.users, secret.encode("utf-8"))
    print("listening on 127.0.0.1:%d" % server.server_address[1], flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="loginapp")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("adduser")
    p.add_argument("username")
    p.add_argument("--users", required=True)
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--users", required=True)
    args = parser.parse_args(argv)
    return cmd_adduser(args) if args.command == "adduser" else cmd_serve(args)


if __name__ == "__main__":
    sys.exit(main())
