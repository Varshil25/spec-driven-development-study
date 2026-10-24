"""HTTP server: pages, routing, sign-in, sessions (contracts/http.md)."""

import html
import http.server
import re
import sys
import threading
import time
import traceback
import urllib.parse

from loginapp import accounts, tokens

MAX_BODY = 65536
MAX_FAILURES = 5
LOCK_SECONDS = 900
FORM_TYPE = "application/x-www-form-urlencoded"
LOGIN_FORM = (
    '<form method="post" action="/login">\n'
    '  <label>Username <input type="text" name="username" autocomplete="username" required></label>\n'
    '  <label>Password <input type="password" name="password" autocomplete="current-password" required></label>\n'
    '  <button type="submit">Sign in</button>\n'
    "</form>\n"
)


# ------------------------------------------------------------------ pages


def _document(title, body):
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        "</head>\n"
        "<body>\n"
        f"{body}"
        "</body>\n"
        "</html>\n"
    ).encode("utf-8")


def login_page(error):
    message = '<p class="error" role="alert">Invalid username or password</p>\n' if error else ""
    return _document("Sign in", "<h1>Sign in</h1>\n" + message + LOGIN_FORM)


def dashboard_page(username):
    return _document(
        "Dashboard",
        f"<h1>Welcome, {html.escape(username, quote=True)}</h1>\n"
        '<form method="post" action="/logout"><button type="submit">Sign out</button></form>\n',
    )


def simple_page(title):
    return _document(title, f"<h1>{title}</h1>\n")


# ------------------------------------------------------------------ sign-in and sessions


class SignInRefused(Exception):
    """The standard sign-in failure; it carries no detail, so every 401 is identical."""


def parse_session_cookie(cookie_header):
    """Return the single non-empty `session` cookie value, or raise InvalidToken."""
    values = []
    for pair in cookie_header.split(";"):
        name, _, value = pair.partition("=")
        if name.strip() == "session":
            values.append(value.strip())
    if len(values) != 1 or not values[0]:
        raise tokens.InvalidToken("no single non-empty session cookie")
    return values[0]


def parse_login_form(content_types, body):
    """Return (username, password) from a well-formed form submission, or raise SignInRefused."""
    if len(content_types) != 1 or content_types[0].split(";")[0].strip().lower() != FORM_TYPE:
        raise SignInRefused()
    try:
        text = body.decode("utf-8", errors="strict")
        pairs = urllib.parse.parse_qsl(text, keep_blank_values=True, encoding="utf-8", errors="strict")
    except ValueError:  # includes UnicodeDecodeError
        raise SignInRefused() from None
    usernames = [v for k, v in pairs if k == "username"]
    passwords = [v for k, v in pairs if k == "password"]
    if len(usernames) != 1 or len(passwords) != 1 or not usernames[0] or not passwords[0]:
        raise SignInRefused()
    return usernames[0], passwords[0]


class LoginServer(http.server.ThreadingHTTPServer):
    def __init__(self, port, users_path, secret, clock, sleep):
        super().__init__(("127.0.0.1", port), Handler)  # binds and listens
        self.run_start = int(clock())  # right after binding, before `listening on` (FR-027)
        self.users_path = users_path
        self.key = secret.encode("utf-8")
        self.clock = clock
        self.sleep = sleep
        self.lock = threading.Lock()  # guards all of the state below
        self.issued = {}  # token -> exp, for tokens issued by this run
        self.signed_out = {}  # token -> exp, for signed-out tokens that have not expired
        self.failures = {}  # username -> failed attempts in a row (missing means 0)
        self.locked_at = {}  # username -> clock() at the fifth failure

    def _sweep(self, now):
        """Forget expired tokens. The caller holds self.lock."""
        for registry in (self.issued, self.signed_out):
            for token in [t for t, exp in registry.items() if exp <= now]:
                del registry[token]

    def issue_token(self, username):
        """Issue and record a token whose iat is after run_start and whose bytes are not
        signed out (waits at most 1 s for the next second)."""
        while True:
            with self.lock:
                now = self.clock()
                self._sweep(now)
                iat = int(now)
                token = tokens.encode(username, iat, self.key)
                if iat > self.run_start and token not in self.signed_out:
                    self.issued[token] = iat + tokens.SESSION_SECONDS
                    return token
            self.sleep(max(0.0, iat + 1 - self.clock()))

    def session_user(self, cookie_header):
        """Return the signed-in username, or raise InvalidToken when there is no valid session."""
        token = parse_session_cookie(cookie_header)
        claims = tokens.decode(token, self.key, self.clock())
        with self.lock:
            if token not in self.issued or token in self.signed_out:
                raise tokens.InvalidToken("not issued by this run, or signed out")
        return claims["sub"]

    def sign_out(self, cookie_header):
        """Refuse the presented token from now on if it is a valid session; otherwise do nothing (FR-019)."""
        try:
            token = parse_session_cookie(cookie_header)
            tokens.decode(token, self.key, self.clock())
        except tokens.InvalidToken:
            return  # no valid session to end; the response is the same either way
        with self.lock:
            self._sweep(self.clock())
            if token in self.issued:
                self.signed_out[token] = self.issued.pop(token)

    def attempt(self, username, password):
        """Return a new session token, or raise SignInRefused; AccountsFileError propagates."""
        records = accounts.load(self.users_path, missing_ok=False)
        if username not in records:
            accounts.dummy_verify(password)  # same cost as a wrong password (FR-016)
            raise SignInRefused()
        correct = accounts.verify(password, records[username])  # hashed once, even when locked
        with self.lock:  # one critical section: lock check, result and update (FR-030)
            t = self.clock()
            if username in self.locked_at:
                if t - self.locked_at[username] < LOCK_SECONDS:
                    raise SignInRefused()  # not counted, lock not extended
                del self.locked_at[username]
                self.failures.pop(username, None)
            if not correct:
                count = self.failures.get(username, 0) + 1
                if count == MAX_FAILURES:
                    self.locked_at[username] = t
                    del self.failures[username]
                else:
                    self.failures[username] = count
                raise SignInRefused()
            self.failures.pop(username, None)
        return self.issue_token(username)

    def handle_error(self, request, client_address):
        sys.stderr.write(f"loginapp: error: connection failed: {sys.exc_info()[0].__name__}\n")
        sys.stderr.flush()


def make_server(port, users_path, secret, clock=time.time, sleep=time.sleep):
    return LoginServer(port, users_path, secret, clock, sleep)


# ------------------------------------------------------------------ request handling


class Handler(http.server.BaseHTTPRequestHandler):
    error_content_type = "text/html; charset=utf-8"

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, format, *args):
        """Requests are not logged (FR-029)."""

    def send_error(self, code, message=None, explain=None):
        # On Python 3.11, http.server reports a malformed request line (for example `GARBAGE`)
        # while request_version is still "HTTP/0.9", which writes no status line or headers.
        if self.request_version == "HTTP/0.9":
            self.request_version = "HTTP/1.0"
        super().send_error(code, message, explain)

    def parse_request(self):
        ok = super().parse_request()
        if ok and self.request_version == "HTTP/0.9":
            self.send_error(400)  # HTTP/0.9 responses would carry no headers at all
            return False
        return ok

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def cookie_header(self):
        return "; ".join(self.headers.get_all("Cookie") or [])

    def dispatch(self, method):
        path = self.requestline.split()[1].split("?", 1)[0]
        try:
            methods = ROUTES.get(path)
            if methods is None:
                response = (404, [], simple_page("Not found"))
            elif method not in methods:
                response = (405, [("Allow", ", ".join(methods))], simple_page("Method not allowed"))
            else:
                response = methods[method](self)
        except Exception as e:
            sys.stderr.write(
                f"loginapp: internal error while handling {method} {path}: {type(e).__name__}\n"
                + "".join(traceback.format_tb(e.__traceback__))
            )
            sys.stderr.flush()
            response = (500, [], simple_page("Internal server error"))
        self.send(*response)

    def send(self, status, headers, body):
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        if body:
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -------------------------------------------------------------- routes

    def get_login(self):
        return (200, [], login_page(False))

    def get_dashboard(self):
        try:
            username = self.server.session_user(self.cookie_header())
        except tokens.InvalidToken:
            return (303, [("Location", "/login")], b"")
        return (200, [], dashboard_page(username))

    def post_login(self):
        lengths = self.headers.get_all("Content-Length") or []
        if len(lengths) > 1 or (lengths and not re.fullmatch(r"[0-9]+", lengths[0].strip())):
            return (400, [], simple_page("Bad request"))
        digits = lengths[0].strip().lstrip("0") if lengths else ""
        if len(digits) > len(str(MAX_BODY)) or int(digits or "0") > MAX_BODY:
            return (413, [], simple_page("Content too large"))
        length = int(digits or "0")
        body = self.rfile.read(length) if length else b""
        if len(body) < length:
            return (400, [], simple_page("Bad request"))
        try:
            username, password = parse_login_form(self.headers.get_all("Content-Type") or [], body)
            token = self.server.attempt(username, password)
        except SignInRefused:
            return (401, [], login_page(True))
        except accounts.AccountsFileError as e:
            sys.stderr.write(f"loginapp: error: {e}\n")
            sys.stderr.flush()
            return (500, [], simple_page("Internal server error"))
        cookie = f"session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={tokens.SESSION_SECONDS}"
        return (303, [("Location", "/dashboard"), ("Set-Cookie", cookie)], b"")

    def post_logout(self):
        self.server.sign_out(self.cookie_header())  # the body is never read
        return (303, [("Location", "/login"), ("Set-Cookie", "session=; Max-Age=0; Path=/")], b"")


ROUTES = {
    "/login": {"GET": Handler.get_login, "POST": Handler.post_login},
    "/dashboard": {"GET": Handler.get_dashboard},
    "/logout": {"POST": Handler.post_logout},
}
