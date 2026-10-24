# Contract: HTTP Interface

**Feature**: `001-secure-login-app` | **Plan**: [../plan.md](../plan.md)

The server listens on `127.0.0.1:PORT` only. It speaks HTTP/1.0, so every connection closes after one response. The status codes, paths, header names, cookie name and attributes, token format and the message `Invalid username or password` come from the product owner and are fixed. The HTTP version and reason phrases are not part of the contract.

## Headers on every response (FR-012, FR-028)

| Header | Value | When |
|--------|-------|------|
| `Cache-Control` | `no-store` | always |
| `X-Frame-Options` | `DENY` | always |
| `X-Content-Type-Options` | `nosniff` | always |
| `Content-Type` | `text/html; charset=utf-8` | every response with a body |
| `Content-Length` | byte length of the body (`0` for 303) | always |

- These headers are added in one `end_headers` override. They are therefore also present on errors that `http.server` produces itself, before any route runs:
  - 400 for bad syntax or HTTP/0.9;
  - 414 for a URI that is too long;
  - 431 for too many headers;
  - 501 for an unsupported method;
  - 505 for an unsupported HTTP version.
- Every body is HTML: a complete `<!doctype html>` document with `<meta charset="utf-8">`.

## Routing (FR-021, FR-022)

- The path is the raw request-target up to the first `?`, matched **exactly**. The query string is ignored. Case matters, there is no percent-decoding, and a leading `//` is not collapsed.

| Path | GET | POST | Other methods |
|------|-----|------|---------------|
| `/login` | 200 login page | sign-in | 501 |
| `/dashboard` | dashboard or 303 | 405, `Allow: GET` | 501 |
| `/logout` | 405, `Allow: POST` | sign-out | 501 |
| anything else (`/`, `/dashboard/`, `/login.html`, `//login`, `/LOGIN`) | 404 | 404 | 501 |

- 404 and 405 have small HTML bodies: `Not found` and `Method not allowed`.
- 501 is `http.server`'s own error page, with the headers above.

## `GET /login` (FR-013)

- **200** with the login page.
- No `Set-Cookie` header.
- A `session` cookie sent with the request is ignored (spec: no redirect when already signed in).

The page holds exactly one form:

```html
<form method="post" action="/login">
  <label>Username <input type="text" name="username" autocomplete="username" required></label>
  <label>Password <input type="password" name="password" autocomplete="current-password" required></label>
  <button type="submit">Sign in</button>
</form>
```

The text `Invalid username or password` does not appear on this page.

## `POST /login` (FR-011, FR-014, FR-015, FR-016, FR-030)

The checks run in this order:

| # | Condition | Response |
|---|-----------|----------|
| 1 | More than one `Content-Length` header, or a value that is not ASCII digits | **400**, HTML error page |
| 2 | `Content-Length` > 65536 | **413**, HTML error page, body not read |
| 3 | Fewer bytes than `Content-Length` arrive before end-of-stream | **400** |
| 4 | Malformed submission: no `Content-Length` (treated as an empty body), empty body, `Content-Type` missing or repeated, media type other than `application/x-www-form-urlencoded` (case-insensitive, parameters ignored), body bytes or a decoded field not valid UTF-8, `username` or `password` missing, empty or repeated. Other fields are ignored. | **401** failure page (below). The accounts file is not read and no state changes. |
| 5 | Accounts file missing, unreadable or invalid at this moment | **500**, generic page; one error line on stderr naming FILE |
| 6 | Username has no account, password wrong, or username locked | **401** failure page; lock state updated as in [data-model.md](../data-model.md#sign-in-lock-state-in-memory) |
| 7 | Credentials correct and username not locked | **303 See Other**, `Location: /dashboard`, `Set-Cookie` as below, `Content-Length: 0` |

### Failure page (401)

- The same bytes as the login page, with one extra element before the form:

  ```html
  <p class="error" role="alert">Invalid username or password</p>
  ```

- The page never includes the submitted username or password.
- Responses 4 and 6 are byte-identical, and so are their headers, except `Date`.
- Every case in row 6 costs one scrypt hash (FR-016).

### Session cookie (FR-024, FR-025)

```text
Set-Cookie: session=<JWT>; HttpOnly; SameSite=Strict; Path=/; Max-Age=1800
```

`<JWT>` is the token described in [data-model.md](../data-model.md#session-token). There is no `Secure` attribute, because the server uses plain HTTP over loopback (spec Assumptions).

## `GET /dashboard` (FR-017, FR-018, FR-023, FR-026, FR-027)

- **Session lookup**:
  1. Join all `Cookie` request headers with `; `.
  2. Split on `;`, then split each pair on its first `=`, stripping spaces.
  3. A session candidate exists only when exactly one pair is named `session` and its value is non-empty.
- **Valid session**: **200**.
  - The page contains `<h1>Welcome, {html.escape(sub, quote=True)}</h1>` and this sign-out form:

    ```html
    <form method="post" action="/logout"><button type="submit">Sign out</button></form>
    ```

  - No `Set-Cookie` header (FR-026).
- **Otherwise**: **303**, `Location: /login`, `Content-Length: 0`, no body, no `Set-Cookie`. "Otherwise" covers:
  - no `Cookie` header;
  - an empty or repeated `session` cookie;
  - a token that fails any acceptance step: malformed, non-canonical encoding, `alg` not `HS256`, bad signature, wrong secret, bad claim types, expired;
  - a token not issued by this run, or signed out.

## `POST /logout` (FR-019, FR-020)

- The request body is never read.
- If the request carries a session candidate that is a valid session at this moment, the token moves from the issued registry to the signed-out map before the response is written.
- The response is the same whether or not the session was valid:

  ```text
  303 See Other
  Location: /login
  Set-Cookie: session=; Max-Age=0; Path=/
  Content-Length: 0
  ```

- Other sessions of the same username, which hold different tokens, are not affected.

## Errors (FR-031)

- An exception in a route handler gives **500** with the generic page `<h1>Internal server error</h1>`. The page contains no exception text, path or stack trace.
- The report goes to stderr only (see [cli.md](cli.md#while-running)). The handling thread ends normally, so the server keeps accepting requests.
