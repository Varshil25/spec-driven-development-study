"""HTML pages. Every dynamic value is escaped."""

from __future__ import annotations

import base64
import hashlib
from html import escape

_STYLE = """
body { font-family: system-ui, sans-serif; margin: 0; background: #f4f5f7; color: #1c1e21; }
main { max-width: 22rem; margin: 4rem auto; padding: 2rem; background: #fff;
       border-radius: 8px; box-shadow: 0 1px 4px rgba(0, 0, 0, .15); }
h1 { font-size: 1.4rem; margin-top: 0; }
label { display: block; margin-top: 1rem; font-weight: 600; }
input { box-sizing: border-box; width: 100%; padding: .5rem; margin-top: .25rem; font-size: 1rem; }
button { margin-top: 1.5rem; padding: .6rem 1.2rem; font-size: 1rem; cursor: pointer; }
.error { color: #b00020; font-weight: 600; }
"""

_STYLE_HASH = base64.b64encode(hashlib.sha256(_STYLE.encode("utf-8")).digest()).decode("ascii")

# Only the stylesheet above may load; forms may only post back to this site;
# the pages may not be framed.
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; "
    f"style-src 'sha256-{_STYLE_HASH}'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'"
)

INVALID_CREDENTIALS = "Invalid username or password"


def _layout(title: str, body: str) -> bytes:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n"
        f"<style>{_STYLE}</style>\n"
        "</head>\n"
        "<body>\n"
        f"<main>\n{body}</main>\n"
        "</body>\n"
        "</html>\n"
    ).encode("utf-8")


def login_page(error: str | None = None) -> bytes:
    message = f'<p class="error" role="alert">{escape(error)}</p>\n' if error else ""
    return _layout(
        "Log in",
        "<h1>Log in</h1>\n"
        f"{message}"
        '<form method="post" action="/login">\n'
        '<label for="username">Username</label>\n'
        '<input id="username" name="username" type="text" autocomplete="username" required autofocus>\n'
        '<label for="password">Password</label>\n'
        '<input id="password" name="password" type="password" autocomplete="current-password" required>\n'
        '<button type="submit">Log in</button>\n'
        "</form>\n",
    )


def dashboard_page(username: str) -> bytes:
    return _layout(
        "Dashboard",
        f"<h1>Welcome, {escape(username)}</h1>\n"
        '<form method="post" action="/logout">\n'
        '<button type="submit">Log out</button>\n'
        "</form>\n",
    )


def error_page(status: int, reason: str) -> bytes:
    return _layout(f"{status} {reason}", f"<h1>{status} {escape(reason)}</h1>\n")
