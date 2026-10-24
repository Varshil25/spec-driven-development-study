"""The HTTP server: routing, sessions and the login flow."""

from __future__ import annotations

import collections
import hashlib
import secrets
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from . import pages, tokens, users

HOST = "127.0.0.1"
COOKIE_NAME = "session"
MAX_BODY_BYTES = 8 * 1024
MAX_FORM_FIELDS = 20

# Failed-login throttling, per username: after MAX_FAILURES failed attempts
# within FAILURE_WINDOW seconds, further attempts for that username get 429
# until the oldest of those failures falls out of the window.
MAX_FAILURES = 10
FAILURE_WINDOW = 15 * 60
MAX_TRACKED_USERNAMES = 10_000

# scrypt needs 16 MiB per hash; cap how many run at once.
MAX_CONCURRENT_HASHES = 4

TOO_MANY_ATTEMPTS = "Too many failed login attempts. Try again later."

_SECURITY_HEADERS = (
    ("Content-Security-Policy", pages.CONTENT_SECURITY_POLICY),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    # Not "no-referrer": that would make browsers send `Origin: null` on our
    # own form posts, which _reject_cross_site would then refuse.
    ("Referrer-Policy", "same-origin"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
    ("Cache-Control", "no-store"),
)
_HTML = "text/html; charset=utf-8"


class FailedLoginTracker:
    """Remembers recent failed logins per username (in memory)."""

    def __init__(self, max_failures=MAX_FAILURES, window=FAILURE_WINDOW,
                 max_tracked=MAX_TRACKED_USERNAMES, clock=time.monotonic):
        self._max_failures = max_failures
        self._window = window
        self._max_tracked = max_tracked
        self._clock = clock
        self._failures: collections.OrderedDict[str, collections.deque] = collections.OrderedDict()
        self._lock = threading.Lock()

    def _recent(self, username: str, now: float) -> collections.deque | None:
        times = self._failures.get(username)
        if times is None:
            return None
        while times and times[0] <= now - self._window:
            times.popleft()
        if not times:
            del self._failures[username]
            return None
        return times

    def retry_after(self, username: str) -> int | None:
        """Seconds until username may try again, or None if it may try now."""
        with self._lock:
            now = self._clock()
            times = self._recent(username, now)
            if times is None or len(times) < self._max_failures:
                return None
            return max(1, int(times[-self._max_failures] + self._window - now + 0.999))

    def record_failure(self, username: str) -> None:
        with self._lock:
            now = self._clock()
            times = self._recent(username, now)
            if times is None:
                while len(self._failures) >= self._max_tracked:
                    self._failures.popitem(last=False)
                times = self._failures[username] = collections.deque(maxlen=self._max_failures)
            times.append(now)
            self._failures.move_to_end(username)

    def reset(self, username: str) -> None:
        with self._lock:
            self._failures.pop(username, None)


class RevokedTokens:
    """Tokens ended by logout, kept (in memory) until they would expire anyway."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self._expiry: dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    def revoke(self, token: str, exp: float) -> None:
        with self._lock:
            now = self._clock()
            for key in [k for k, e in self._expiry.items() if e <= now]:
                del self._expiry[key]
            self._expiry[self._key(token)] = exp

    def is_revoked(self, token: str) -> bool:
        with self._lock:
            return self._key(token) in self._expiry


class App:
    """State shared by all request handlers."""

    def __init__(self, users_path, secret: bytes):
        if not secret:
            raise ValueError("secret must not be empty")
        self.users_path = users_path
        self.secret = secret
        self.failed_logins = FailedLoginTracker()
        self.revoked = RevokedTokens()
        self.hash_slots = threading.BoundedSemaphore(MAX_CONCURRENT_HASHES)
        # Checked against when the username is unknown, so that unknown and
        # known usernames take the same time to reject.
        self.dummy_hash = users.hash_password(secrets.token_urlsafe(16))

    def check_credentials(self, username: str, password: str) -> bool:
        with self.hash_slots:
            accounts = users.load_users(self.users_path)
            stored = accounts.get(username) if users.is_valid_username(username) else None
            matches = users.verify_password(password, stored if stored is not None else self.dummy_hash)
        return stored is not None and matches

    def user_exists(self, username: str) -> bool:
        return users.is_valid_username(username) and username in users.load_users(self.users_path)


class LoginServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, app: App):
        self.app = app
        super().__init__(address, Handler)


class _HTTPError(Exception):
    def __init__(self, status: int):
        super().__init__(status)
        self.status = status


def _session_cookie(token: str) -> str:
    return (f"{COOKIE_NAME}={token}; Path=/; Max-Age={tokens.SESSION_SECONDS}; "
            "HttpOnly; SameSite=Strict")


def _cleared_session_cookie() -> str:
    return (f"{COOKIE_NAME}=; Path=/; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; "
            "HttpOnly; SameSite=Strict")


class Handler(BaseHTTPRequestHandler):
    server_version = "loginapp"
    protocol_version = "HTTP/1.0"
    timeout = 15  # seconds a client may stall before it is dropped

    server: LoginServer

    # -- dispatch ---------------------------------------------------------

    _ROUTES = {
        "/login": {"GET": "_get_login", "HEAD": "_get_login", "POST": "_post_login"},
        "/dashboard": {"GET": "_get_dashboard", "HEAD": "_get_dashboard"},
        "/logout": {"POST": "_post_logout"},
    }

    def do_GET(self):
        self._dispatch()

    do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_GET

    def version_string(self):
        return self.server_version

    def _dispatch(self):
        try:
            try:
                self._check_host()
                body = self._read_body()
                routes = self._ROUTES.get(urlsplit(self.path).path)
                if routes is None:
                    raise _HTTPError(404)
                name = routes.get(self.command)
                if name is None:
                    self._send_error_page(405, [("Allow", ", ".join(routes))])
                    return
                getattr(self, name)(body)
            except _HTTPError as exc:
                self._send_error_page(exc.status)
            except (ConnectionError, TimeoutError):
                raise
            except Exception:
                self.log_error("internal error handling %r:\n%s", self.path, traceback.format_exc())
                self._send_error_page(500)
        except (ConnectionError, TimeoutError):
            self.close_connection = True  # the client went away

    def _check_host(self):
        """Only answer requests addressed to this loopback server.

        Rejecting other Host names defeats DNS-rebinding attacks, where a
        hostile web page points its own domain at 127.0.0.1.
        """
        hosts = self.headers.get_all("Host") or []
        if not hosts:
            return  # HTTP/1.0 clients need not send one
        port = self.server.server_address[1]
        allowed = {name + suffix for name in ("127.0.0.1", "localhost") for suffix in ("", f":{port}")}
        if len(hosts) != 1 or hosts[0].strip().lower() not in allowed:
            self.close_connection = True
            raise _HTTPError(421)

    def _read_body(self) -> bytes:
        if "Transfer-Encoding" in self.headers:
            self.close_connection = True
            raise _HTTPError(411)
        lengths = self.headers.get_all("Content-Length") or []
        if not lengths:
            return b""
        if len(lengths) != 1 or not lengths[0].strip().isdigit() or not lengths[0].strip().isascii():
            self.close_connection = True
            raise _HTTPError(400)
        length = int(lengths[0])
        if length > MAX_BODY_BYTES:
            self.close_connection = True
            raise _HTTPError(413)
        body = self.rfile.read(length)
        if len(body) != length:
            self.close_connection = True
            raise _HTTPError(400)
        return body

    # -- routes -----------------------------------------------------------

    def _get_login(self, body: bytes):
        self._send_html(200, pages.login_page())

    def _post_login(self, body: bytes):
        self._reject_cross_site()
        username, password = self._login_form(body)
        app = self.server.app
        throttle_key = username if username is not None and users.is_valid_username(username) else None

        if throttle_key is not None:
            wait = app.failed_logins.retry_after(throttle_key)
            if wait is not None:
                self._send_html(429, pages.login_page(TOO_MANY_ATTEMPTS),
                                [("Retry-After", str(wait))])
                return

        if username is not None and password is not None and app.check_credentials(username, password):
            app.failed_logins.reset(username)
            token = tokens.issue(username, app.secret)
            self._send_redirect("/dashboard", [("Set-Cookie", _session_cookie(token))])
            return

        if throttle_key is not None:
            app.failed_logins.record_failure(throttle_key)
        self._send_html(401, pages.login_page(pages.INVALID_CREDENTIALS))

    def _get_dashboard(self, body: bytes):
        token, username = self._session()
        if username is None:
            extra = [("Set-Cookie", _cleared_session_cookie())] if token is not None else []
            self._send_redirect("/login", extra)
            return
        self._send_html(200, pages.dashboard_page(username))

    def _post_logout(self, body: bytes):
        self._reject_cross_site()
        token = self._session_token()
        if token is not None:
            try:
                claims = tokens.verify(token, self.server.app.secret)
            except tokens.InvalidToken:
                pass
            else:
                self.server.app.revoked.revoke(token, claims["exp"])
        self._send_redirect("/login", [("Set-Cookie", _cleared_session_cookie())])

    # -- helpers ----------------------------------------------------------

    def _reject_cross_site(self):
        """Refuse form posts that a browser reports as coming from another site."""
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if fetch_site is not None and fetch_site.strip().lower() not in ("same-origin", "none"):
            raise _HTTPError(403)
        origin = self.headers.get("Origin")
        if origin is not None:
            # The Host header has already been checked by _check_host.
            host = (self.headers.get("Host") or "").strip().lower()
            if not host or origin.strip().lower() != f"http://{host}":
                raise _HTTPError(403)

    def _login_form(self, body: bytes) -> tuple[str | None, str | None]:
        content_type = self.headers.get("Content-Type")
        if content_type is not None:
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type != "application/x-www-form-urlencoded":
                raise _HTTPError(415)
        try:
            fields = parse_qs(body.decode("utf-8"), keep_blank_values=True,
                              errors="strict", max_num_fields=MAX_FORM_FIELDS)
        except ValueError:  # includes UnicodeDecodeError
            raise _HTTPError(400) from None

        def single(name: str) -> str | None:
            values = fields.get(name)
            return values[0] if values is not None and len(values) == 1 else None

        return single("username"), single("password")

    def _session_token(self) -> str | None:
        for header in self.headers.get_all("Cookie") or []:
            for part in header.split(";"):
                name, sep, value = part.strip().partition("=")
                if sep and name.strip() == COOKIE_NAME:
                    return value.strip()
        return None

    def _session(self) -> tuple[str | None, str | None]:
        """Return (token, username); username is None unless the session is valid."""
        token = self._session_token()
        if token is None:
            return None, None
        app = self.server.app
        try:
            claims = tokens.verify(token, app.secret)
        except tokens.InvalidToken:
            return token, None
        if app.revoked.is_revoked(token) or not app.user_exists(claims["sub"]):
            return token, None
        return token, claims["sub"]

    def _send(self, status: int, body: bytes, headers=()):
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        for name, value in _SECURITY_HEADERS:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD" and status >= 200 and status not in (204, 304):
            self.wfile.write(body)

    def _send_html(self, status: int, body: bytes, headers=()):
        self._send(status, body, [("Content-Type", _HTML), *headers])

    def _send_redirect(self, location: str, headers=()):
        self._send(303, b"", [("Location", location), *headers])

    def _send_error_page(self, status: int, headers=()):
        reason = self.responses.get(status, ("Error",))[0]
        self._send_html(status, pages.error_page(status, reason), headers)

    def send_error(self, code, message=None, explain=None):
        # Used by the base class for malformed requests; keep its responses
        # consistent with ours.
        self.close_connection = True
        self.log_error("code %d, message %s", code, message)
        self._send_error_page(code)
