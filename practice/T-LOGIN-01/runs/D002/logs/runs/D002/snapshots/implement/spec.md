# Feature Specification: Secure Login Web Application

**Feature Branch**: `001-secure-login-app`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description (verbatim):

> Build a small web application with a secure login page, using only Python's standard library (for example `http.server`).
>
> User accounts are kept in a file and added from the command line:
>
> - `python -m loginapp adduser USERNAME --users FILE` reads a password from standard input (one line) and adds the account to FILE, creating the file if needed, and prints `added USERNAME`. A username is 3 to 32 letters, digits or underscores, and a password must be at least 12 characters; otherwise it exits with status 2. An existing username exits with status 3.
> - `python -m loginapp serve --port PORT --users FILE` starts the web server on 127.0.0.1 at PORT and prints `listening on 127.0.0.1:PORT` once it is ready. Sessions are signed with the secret in the environment variable `LOGINAPP_SECRET`; if it is not set, the server prints an error and exits with a non-zero status.
>
> Pages (HTML responses use `Content-Type: text/html; charset=utf-8`):
>
> - `GET /login` shows a login form that posts the fields `username` and `password` to `/login`.
> - `POST /login` (form-encoded) checks the credentials. On success it responds `303 See Other` with `Location: /dashboard` and starts a session by setting a cookie named `session`. On failure it responds `401` with the login page and the message `Invalid username or password`.
> - `GET /dashboard` with a valid session shows `Welcome, USERNAME`. Without a valid session it responds `303` with `Location: /login`.
> - `POST /logout` ends the session: it clears the `session` cookie and responds `303` with `Location: /login`.
> - Any other path gets `404`.
>
> The session cookie holds a JWT signed with HS256 using `LOGINAPP_SECRET`, with the claims `sub` (the username), `iat` and `exp`. A session lasts 30 minutes: `exp` is `iat` plus 1800 seconds, and an expired token is not accepted.
>
> Use Python 3.11 or newer and the standard library only. Put the code in a package named `loginapp` under `src/`, so that it runs with `python -m loginapp` when `src/` is on `PYTHONPATH`.
>
> Examples:
>
> ```
> $ printf 'correct-horse-battery\n' | python -m loginapp adduser alice --users users.json
> added alice
> $ LOGINAPP_SECRET=change-me python -m loginapp serve --port 8000 --users users.json
> listening on 127.0.0.1:8000
>
> $ curl -s -i -d 'username=alice&password=[REDACTED:assigned_secret] 127.0.0.1:8000/login
> HTTP/1.0 303 See Other
> Location: /dashboard
> Set-Cookie: session=eyJ...; ...
> $ curl -s -b 'session=<the token from Set-Cookie>' 127.0.0.1:8000/dashboard
> ... Welcome, alice ...
> $ curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8000/dashboard
> 303
> $ curl -s -o /dev/null -w '%{http_code}\n' -d 'username=alice&password=[REDACTED:assigned_secret] 127.0.0.1:8000/login
> 401
> ```

## Clarifications

### Session 2026-10-23

- Q: After sign-out, should a copy of the session token that someone kept stop working (server-side revocation), or is clearing the browser's cookie enough? → A: Yes. After logout that token must stop working, even if someone kept a copy of it.
- Q: Should repeated failed sign-ins be limited, and how? → A: After 5 failed attempts in a row for a username, refuse logins for that username for 15 minutes, even with the right password, with the same `Invalid username or password` response.

## User Scenarios & Testing *(mandatory)*

Two kinds of people use this application:

- The **operator** runs the program on their own machine. They create accounts from the command line and start the web server.
- The **account holder** uses a web browser on the same machine to sign in, see their dashboard and sign out.

### User Story 1 - Operator creates an account (Priority: P1)

The operator creates an account by giving a username on the command line and passing the password on standard input. The program records the account in the accounts file and confirms it. Weak or malformed input is refused with a clear message, and the program never creates a second account with a username that is already taken.

**Why this priority**: nobody can sign in until an account exists, so this is the base for everything else. It can be shipped and checked on its own.

**Independent Test**: run the account command against a fresh accounts file and check the output, the exit status and the file contents. No server is needed.

**Acceptance Scenarios**:

1. **Given** no accounts file exists, **When** the operator runs `adduser alice --users users.json` with the password `correct-horse-battery` on standard input, **Then** the program prints `added alice`, exits with status 0, and `users.json` now exists and holds an account for `alice`.
2. **Given** an accounts file that already holds `alice`, **When** the operator adds `bob` with a valid password, **Then** the program prints `added bob`, and the file holds both `alice` and `bob`.
3. **Given** any accounts file, **When** the operator adds a username of 2 characters, of 33 characters, or one containing a character other than a letter, digit or underscore (for example `al-ice`), **Then** the program exits with status 2, writes a message to standard error naming the rejected username and the rule, prints nothing to standard output, and leaves the file unchanged.
4. **Given** any accounts file, **When** the operator adds a valid username with an 11-character password, **Then** the program exits with status 2, writes a message to standard error that states the 12-character minimum (without showing the password), prints nothing to standard output, and leaves the file unchanged.
5. **Given** an accounts file that already holds `alice`, **When** the operator adds `alice` again with a valid password, **Then** the program exits with status 3, writes a message to standard error saying that `alice` already exists, prints nothing to standard output, and leaves the file unchanged.
6. **Given** an account was just created, **When** someone reads the accounts file, **Then** the password does not appear in it in any readable form.

---

### User Story 2 - Account holder signs in and sees the dashboard (Priority: P1)

The operator starts the server with a session secret. The account holder opens the login page, enters their username and password, and is taken to a dashboard that greets them by name. A wrong username or password is refused with one message that does not say which of the two was wrong.

**Why this priority**: signing in is the reason the application exists. Together with User Story 1 it is the minimum viable product.

**Independent Test**: create an account with the account command, start the server, submit the login form with correct and with incorrect credentials, and follow the redirect to the dashboard with the session cookie.

**Acceptance Scenarios**:

1. **Given** `LOGINAPP_SECRET` is set and the accounts file holds `alice`, **When** the operator runs `serve --port 8000 --users users.json`, **Then** the program prints `listening on 127.0.0.1:8000` once the server accepts connections on 127.0.0.1 port 8000.
2. **Given** `LOGINAPP_SECRET` is not set (or is empty), **When** the operator runs `serve`, **Then** the program writes an error naming `LOGINAPP_SECRET` to standard error, exits with status 1 (a non-zero status), and never prints the `listening on` line.
3. **Given** the server is running, **When** the account holder requests `GET /login`, **Then** they receive status 200 and an HTML page with a form that posts the fields `username` and `password` to `/login`.
4. **Given** the server is running and `alice` has the password `correct-horse-battery`, **When** the login form is posted with those credentials, **Then** the response is `303 See Other` with `Location: /dashboard` and sets a cookie named `session`.
5. **Given** the account holder has just signed in as `alice`, **When** they request `GET /dashboard` with that `session` cookie, **Then** they receive status 200 and a page that shows `Welcome, alice`.
6. **Given** the server is running, **When** the login form is posted with `alice` and a wrong password, **Then** the response is status 401, shows the login form again with the message `Invalid username or password`, and sets no session cookie.
7. **Given** the server is running, **When** the login form is posted with a username that has no account, **Then** the response is exactly the same as in scenario 6 (same status, same message, same page).
8. **Given** the server is running, **When** the operator adds a new account with the account command, **Then** that account can sign in without restarting the server.

---

### User Story 3 - The dashboard stays private (Priority: P2)

Only a signed-in account holder can see the dashboard. Anyone without a valid session is sent to the login page. A session ends 30 minutes after sign-in, or earlier if the server restarts. A session cookie that has been altered, forged or signed with a different secret is not accepted.

**Why this priority**: this is what makes the login secure rather than decorative. It depends on User Story 2 to create sessions.

**Independent Test**: request the dashboard with no cookie, with a tampered token, with a token signed with another secret, with a token that uses a different signing algorithm, with an expired token, and with a token from before a server restart. Every request must be redirected to the login page.

**Acceptance Scenarios**:

1. **Given** the server is running, **When** `GET /dashboard` is requested with no `session` cookie, **Then** the response is `303` with `Location: /login` and contains no dashboard content.
2. **Given** a valid session token for `alice`, **When** any part of it is changed (for example the username in its payload is changed to `bob`), **Then** `GET /dashboard` responds `303` with `Location: /login`.
3. **Given** a token whose content is valid but which was signed with a different secret, or which declares no signature algorithm or one other than HS256, **When** it is sent to `GET /dashboard`, **Then** the response is `303` with `Location: /login`.
4. **Given** a correctly signed token whose expiry time has passed, **When** it is sent to `GET /dashboard`, **Then** the response is `303` with `Location: /login`.
5. **Given** the account holder signed in, **When** the session cookie is inspected, **Then** it holds a token whose expiry is exactly 1800 seconds after its issue time, and the cookie cannot be read by page scripts.
6. **Given** `alice` signed in and the server was then restarted with the same `LOGINAPP_SECRET`, **When** her token, which has not expired, is sent to `GET /dashboard`, **Then** the response is `303` with `Location: /login`.

---

### User Story 4 - Repeated wrong passwords lock the username (Priority: P2)

If someone keeps guessing the password for an account, the account stops accepting sign-ins for a while. After 5 failed attempts in a row for a username, every sign-in for that username is refused for 15 minutes, even with the right password. The refusal looks exactly like any other failed sign-in, so it reveals neither the lock nor whether the account exists.

**Why this priority**: it limits password guessing, which is the main remaining attack on the login page. It builds on User Story 2.

**Independent Test**: create an account, submit 5 wrong passwords for it, then submit the right password before and after the 15 minutes are up. Compare the locked response with an ordinary failure.

**Acceptance Scenarios**:

1. **Given** `alice` exists and has no recent failures, **When** 5 sign-ins for `alice` with wrong passwords are submitted one after another, **Then** each gets the standard 401 failure, and a sixth attempt with the correct password within 15 minutes also gets the standard 401 failure with no session cookie.
2. **Given** `alice` was locked by her fifth failed attempt, **When** she signs in with the correct password 15 minutes (900 seconds) or more after that attempt, **Then** the response is `303` with `Location: /dashboard` and a session cookie.
3. **Given** `alice` had 4 failed attempts and then signed in successfully, **When** 4 more failed attempts are made, **Then** `alice` is not locked: the correct password still signs her in.
4. **Given** `alice` is locked, **When** `bob` signs in with his correct password, **Then** he succeeds, because locks apply to one username only.
5. **Given** `alice` is locked, **When** her locked response is compared with a wrong-password failure for an unlocked account and with a failure for a username that has no account, **Then** all three have the same status, headers (apart from the date) and body, and similar response times (FR-016).
6. **Given** `alice` already had a valid session before she was locked, **When** she opens `GET /dashboard` with that session, **Then** the dashboard is still shown.

---

### User Story 5 - Account holder signs out (Priority: P3)

From the dashboard, the account holder signs out. Their session cookie is cleared, the server stops accepting that session token, and they are returned to the login page. A copy of the token that someone kept no longer works.

**Why this priority**: signing out matters on a shared machine, but sessions already end on their own after 30 minutes, so this comes after the stories above.

**Independent Test**: sign in and keep a copy of the token. Submit `POST /logout` with it and check the response. Then send the copy to the dashboard, both before and after restarting the server, and check that it is refused.

**Acceptance Scenarios**:

1. **Given** the account holder is on the dashboard, **When** they look at the page, **Then** it offers a sign-out control that submits `POST /logout`.
2. **Given** a signed-in account holder, **When** they submit `POST /logout`, **Then** the response is `303` with `Location: /login` and instructs the browser to delete the `session` cookie.
3. **Given** a browser that has followed the sign-out response, **When** it requests `GET /dashboard`, **Then** it is redirected to `/login`.
4. **Given** someone kept a copy of the session token from before sign-out, **When** they send that copy to `GET /dashboard` after the sign-out, before the token's expiry time, **Then** the response is `303` with `Location: /login`.
5. **Given** a session token was signed out and the server was then stopped and started again with the same `LOGINAPP_SECRET`, **When** a copy of that token is sent to `GET /dashboard`, **Then** the response is still `303` with `Location: /login`. Any session from before the restart is refused too (FR-027).
6. **Given** `alice` signed in from two browsers at different times (so each holds a different token), **When** she signs out in one, **Then** the other browser's session still works.
7. **Given** a request with no session, or with an invalid or expired one, **When** it submits `POST /logout`, **Then** the response is still `303` with `Location: /login`.

---

### Edge Cases

- **Username boundaries**: 3 and 32 characters are accepted; 2 and 33 are rejected with status 2. Letters mean the ASCII letters `A`–`Z` and `a`–`z` only, so `josé` is rejected.
- **Username case**: usernames are case-sensitive, so `Alice` and `alice` are two different accounts, and signing in as `ALICE` does not match `alice`.
- **Password boundaries**: 12 characters are accepted and 11 are rejected. Length is counted in characters, not bytes. Spaces and other characters inside the line belong to the password. Only the line ending (`\n` or `\r\n`) is removed.
- **Password input**: only the first line of standard input is used. Empty input (no line at all) gives an empty password, which is rejected with status 2. Input with no final line ending is accepted as the password. Input that is not valid UTF-8 is rejected with status 2.
- **Several problems at once**: `adduser` checks the arguments, then the username, then the password, then the accounts file, and only then whether the username exists. The first failure decides the exit status. For example, a valid username that already exists, given with a too-short password, exits with status 2, not 3.
- **Accounts file problems in `adduser`**: if the file exists but cannot be read or is not a valid accounts file, or if it cannot be created or written (including when its folder does not exist), the command exits with status 1, names the file in its error message, and leaves any existing file unchanged.
- **Accounts file problems in `serve`**: if the file is missing, unreadable or invalid at startup, the server exits with status 1 before printing the `listening on` line. If the file becomes unreadable or invalid while the server runs, a sign-in attempt gets an error response (500), not a 401 and never a session.
- **Port problems**: a port that is not a whole number from 1 to 65535 exits with status 2. A port that is already in use exits with status 1 and an error naming the port. Neither case prints the `listening on` line. When several startup problems exist at once, the order in FR-010 decides which one is reported.
- **Malformed sign-in submissions**: a missing, empty or repeated `username` or `password` field, a missing or empty body, a content type other than form encoding, or fields that are not valid UTF-8 are treated as a failed sign-in (401 with the standard message). A body declared larger than 64 KiB is refused with 413 without being read. An invalid declared body length is refused with 400.
- **Odd cookies**: a missing, empty, malformed or repeated `session` cookie counts as no valid session.
- **Re-encoded signed-out token**: a copy of a signed-out token that has been re-encoded is still refused. Examples are added `=` padding, or a last character changed to another one that decodes to the same bytes (FR-020).
- **Two sign-ins in the same second**: the token holds only `sub`, `iat` and `exp`, so two sign-ins for the same username in the same second can get identical tokens. If they do, signing out in one place ends both, because they are the same token.
- **Lock boundaries**: 4 failures in a row do not lock. The 5th does. A correct password 1 second before the 15 minutes are up is refused. At exactly 900 seconds after the 5th failure, and later, it is accepted.
- **Lock counting**: failures do not have to be close together in time. Only a successful sign-in, or the end of a lock, resets the count. Attempts made while locked, including ones with the correct password, are refused, do not count and do not extend the lock.
- **Who gets locked**: only usernames that have an account are counted and locked, matching the exact (case-sensitive) username. Attempts for usernames with no account, and malformed submissions, count for no one. An account added while the server runs starts with a count of zero.
- **Server restarts**: every token issued before a restart is refused afterwards, whether or not the secret changed and whether or not it was signed out (FR-027). Everyone has to sign in again. This also holds when the new run starts within the same second in which the old run issued a token.
- **Exact expiry**: a token is accepted only while the current time is before its expiry time. At the expiry second and after, it is refused. No clock tolerance is allowed.
- **Paths**: paths are matched exactly and the query string is ignored. `/login?x=1` is the login page, but `/`, `/dashboard/` and `/login.html` get 404.
- **Wrong method on a known page**: for example `GET /logout` or `POST /dashboard`. The response is 405 with an `Allow` header listing the supported methods. Methods other than GET and POST (for example `PUT`) get an error status on every path.
- **Visiting `/login` while signed in**: the login form is shown as usual. There is no automatic redirect.
- **Unexpected internal errors** during a request: the response is a generic 500 page with no internal details, and the server keeps serving other requests.

## Requirements *(mandatory)*

### Functional Requirements

#### Account command (`adduser`)

- **FR-001**: `python -m loginapp adduser USERNAME --users FILE` MUST read one line from standard input as the password, remove only its line ending (`\n` or `\r\n`), add an account for USERNAME to FILE (creating FILE if it does not exist), print exactly `added USERNAME` to standard output, and exit with status 0.
- **FR-002**: A username MUST be accepted only if it is 3 to 32 characters long and every character is an ASCII letter, an ASCII digit or an underscore. Otherwise the command MUST exit with status 2, write a message to standard error that names the rejected username and states the rule, write nothing to standard output, and leave FILE unchanged (or not created).
- **FR-003**: A password MUST be accepted only if it is at least 12 characters long, counted in characters (not bytes) after the line ending is removed. A password that is shorter, or that is not valid UTF-8 text, MUST make the command exit with status 2, write a message to standard error that states the 12-character minimum and does not contain the password, write nothing to standard output, and leave FILE unchanged (or not created).
- **FR-004**: If FILE already holds an account whose username exactly matches USERNAME (case-sensitive), the command MUST exit with status 3, write a message to standard error naming the username, write nothing to standard output, and leave FILE unchanged. The checks MUST run in this order, and the first failure decides the exit status: command-line arguments (FR-007), username (FR-002), password (FR-003), reading FILE (FR-007), and then this check. So an input that fails FR-002 or FR-003 exits with status 2 even if the username exists.
- **FR-005**: Passwords MUST NOT be stored in any recoverable form. For each account, FILE MUST store only three things: a random salt of at least 16 bytes, unique to that account; a hash made with a password-hashing function designed to be slow; and the name of that function with its cost settings. The cost settings MUST be at least the minimums that the OWASP Password Storage Cheat Sheet recommends for the chosen function, and the plan MUST record the exact values so that tests can check them. The password text MUST NOT appear in FILE, and two accounts with the same password MUST have different stored values.
- **FR-006**: After each successful `adduser`, FILE MUST be readable and writable by its owner only. Adding an account MUST keep every existing account, and if writing the update fails part-way, the previous contents of FILE MUST remain intact.
- **FR-007**: If no command or an unknown command is given, or a command's arguments are missing or unrecognised, the program MUST write a usage message to standard error and exit with status 2. For `adduser`, if FILE exists but cannot be read or is not a valid accounts file, or if FILE cannot be created or written (for example because its folder does not exist), the command MUST exit with status 1 with a message on standard error that names FILE, and any existing FILE MUST be left unchanged.

#### Server command (`serve`)

- **FR-008**: `python -m loginapp serve --port PORT --users FILE` MUST listen on the address 127.0.0.1 only (not on all network interfaces), at PORT. Once it accepts connections, it MUST print exactly `listening on 127.0.0.1:PORT` to standard output, and the line MUST reach a program reading that output straight away (it must not wait in a buffer).
- **FR-009**: If the environment variable `LOGINAPP_SECRET` is unset or empty, `serve` MUST write an error naming `LOGINAPP_SECRET` to standard error and exit with status 1, without accepting connections or printing the `listening on` line.
- **FR-010**: If PORT is not a whole number from 1 to 65535, `serve` MUST exit with status 2. If PORT cannot be used (for example it is already in use), or if FILE is missing, unreadable or not a valid accounts file at startup, `serve` MUST exit with status 1. In each case it MUST write a message to standard error naming the bad value and MUST NOT print the `listening on` line. The checks MUST run in this order, and the first failure decides the exit status: command-line arguments (including the PORT range), then `LOGINAPP_SECRET` (FR-009), then FILE, then opening PORT.
- **FR-011**: The server MUST read FILE afresh for each sign-in attempt, so accounts added while it runs can sign in without a restart. If FILE cannot be read or is invalid at that moment, the attempt MUST get a 500 response, not a 401 and not a session.

#### Pages

- **FR-012**: Every response that has a body MUST have an HTML body and carry the header `Content-Type: text/html; charset=utf-8`. This includes error responses.
- **FR-013**: `GET /login` MUST respond with status 200 and a page holding a form that uses method POST, action `/login`, a text field named `username`, a masked password field named `password`, and a submit button. The page MUST NOT show the message `Invalid username or password`.
- **FR-014**: `POST /login` with a form-encoded body holding exactly one `username` and one `password` that match an account (other fields are ignored), where that username is not locked (FR-030), MUST respond `303 See Other` with `Location: /dashboard` and set a cookie named `session` that holds a new session token (FR-024, FR-025).
- **FR-015**: Any other `POST /login` MUST respond with status 401 and the login page (the form from FR-013) showing the message `Invalid username or password`, and MUST NOT set a session cookie. This covers a wrong password, an unknown username, a locked username (FR-030) even with the correct password, a missing, empty or repeated field, a missing or empty body (no declared body length counts as an empty body), a request whose declared content type is missing or is not `application/x-www-form-urlencoded` (parameters such as `charset` are allowed), and a body whose decoded fields are not valid UTF-8. The page MUST NOT repeat the submitted username or password. The responses for an unknown username, a wrong password and a locked username MUST be identical in status, headers (apart from the date) and body. The only exceptions are a declared body larger than 64 KiB, which MUST get 413 without the body being read, and an invalid declared body length, which MUST get 400.
- **FR-016**: Rejecting an unknown username, rejecting a wrong password for an unlocked account, and rejecting any attempt for a locked username MUST take about as long as each other. Response time must reveal neither which usernames exist nor which are locked. Over repeated attempts, the median times of any two of these cases MUST be within a factor of 2 of each other.
- **FR-017**: `GET /dashboard` with a valid session (FR-023) MUST respond with status 200 and a page that shows `Welcome, USERNAME`, where USERNAME is the session's `sub` claim, escaped so that it always displays as plain text and never as markup, together with a sign-out control that submits `POST /logout`.
- **FR-018**: `GET /dashboard` without a valid session MUST respond `303` with `Location: /login` and no dashboard content. This includes a missing, empty, malformed, repeated, tampered, wrongly signed, expired or signed-out `session` cookie, and one issued before the server last restarted.
- **FR-019**: `POST /logout` MUST respond `303` with `Location: /login` and a `session` cookie with an empty value, `Max-Age=0` and `Path=/`, so that the browser deletes it. This MUST happen whether or not the request carries a valid session.
- **FR-020**: When `POST /logout` carries a session token that is valid at that moment, the server MUST refuse that token from then on, until it expires. Any later request that presents it, including a copy kept by someone else, MUST be treated as having no valid session (FR-018). The refusal MUST be in place before the sign-out response is sent, and MUST still hold after the server is stopped and started again with the same `LOGINAPP_SECRET` (FR-027 ensures this). A token that differs from the signed-out token only in how it is encoded MUST also be refused, for example one with added `=` padding or a last character that decodes to the same bytes. Signing out ends only the token presented. Other sessions of the same username, which hold different tokens, MUST stay valid.
- **FR-021**: A GET or POST request for any path other than `/login`, `/dashboard` and `/logout` MUST get 404 with an HTML page. Paths MUST be matched exactly, ignoring the query string.
- **FR-022**: `GET /logout` and `POST /dashboard` MUST get 405 with an `Allow` header that lists the supported methods: `GET, POST` for `/login`, `GET` for `/dashboard` and `POST` for `/logout`. A request using any method other than GET or POST, on any path, MUST get an error status (4xx or 5xx).

#### Session token

- **FR-023**: A session token MUST be accepted only if all of the following hold: it is a well-formed JWT in compact form (three base64url segments separated by dots); its header declares the algorithm `HS256`; its signature is a valid HS256 signature under the current `LOGINAPP_SECRET`; its payload has a string `sub` and integer `iat` and `exp`; the current time is before `exp`; it has not been signed out (FR-020); and it was issued by the current run of the server (FR-027). Any other token MUST be refused (FR-018). This includes a token whose header declares `none` or any algorithm other than `HS256`.
- **FR-024**: On successful sign-in, the session token MUST be a JWT in compact form as defined by RFC 7519: a base64url-encoded header (without padding) declaring `"alg": "HS256"` and `"typ": "JWT"`, a base64url-encoded payload, and an HS256 signature over the first two segments made with the UTF-8 bytes of `LOGINAPP_SECRET`. Its claims MUST be `sub` (the username), `iat` (the sign-in time in whole seconds since the Unix epoch) and `exp` (exactly `iat` + 1800), so that any conforming JWT verifier given the same secret accepts it.
- **FR-025**: The `session` cookie set at sign-in MUST have the attributes `HttpOnly`, `SameSite=Strict`, `Path=/` and `Max-Age=1800`.
- **FR-026**: A session MUST last a fixed 30 minutes from sign-in. Using the application MUST NOT extend it: `GET /dashboard` MUST NOT set a new or refreshed `session` cookie.
- **FR-027**: Sessions MUST NOT survive a server restart. Once `serve` has printed its `listening on` line, every session token issued by an earlier run of the server MUST be refused, even if it is correctly signed with the same `LOGINAPP_SECRET` and has not expired. Every token issued by the current run, and not signed out, MUST be accepted until it expires.

#### Protection and robustness

- **FR-028**: Every response, including error responses, MUST include `Cache-Control: no-store`, `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff`.
- **FR-029**: The program MUST NOT write any password, stored password hash, session token or the secret to standard output, standard error or any log. Request log lines may include the method, path and status.
- **FR-030**: After 5 failed sign-in attempts in a row for a username, the server MUST lock that username for 15 minutes (900 seconds), starting from the fifth failure.
  - A failed attempt for a username is a well-formed `POST /login` whose username matches an account exactly (case-sensitive), where the username is not locked and the password is wrong. Well-formed means the request is form-encoded and has exactly one non-empty `username` field and one non-empty `password` field, so it is none of the malformed cases in FR-015. No other request counts for any username: not an attempt for a username that has no account, and not a malformed submission.
  - A successful sign-in resets that username's count to zero. The failures do not have to be close together in time.
  - While a username is locked, every sign-in for it MUST get exactly the failure response of FR-015 and no session cookie, even when the password is correct. Its timing MUST meet FR-016.
  - Attempts made while locked MUST NOT count as failures and MUST NOT extend the lock. The lock ends exactly 900 seconds after it began: an attempt at that moment or later is handled normally. When a lock ends, the username's count starts again from zero.
  - A lock affects only new sign-ins. Sessions that already exist for the username MUST stay valid.
  - The count MUST stay correct when several attempts for the same username arrive at the same time. For example, if 10 wrong-password attempts for an unlocked username are sent simultaneously, the username MUST be locked afterwards, so that a correct-password attempt sent after all 10 responses arrive is refused.
  - Failure counts and locks are kept only while the server runs. A restart clears them.
- **FR-031**: An unexpected error while handling a request MUST produce a 500 response with a generic HTML page that contains no internal details. The error MUST be reported on standard error, and the server MUST keep serving later requests.
- **FR-032**: The program MUST run as `python -m loginapp` when `src/` is on the module search path, and its runtime code MUST import nothing outside the Python standard library and its own `loginapp` package.

### Constraints *(set by the product owner)*

- Python 3.11 or newer, standard library only. No third-party packages at runtime.
- The code lives in a package named `loginapp` under `src/`.
- The command names, arguments, exit statuses, page paths, status codes, cookie name, token format and message texts above form an external contract fixed by the product owner. They are requirements, not design choices.

### Key Entities *(include if feature involves data)*

- **Account**: one person who can sign in. It has a username (unique, case-sensitive, 3–32 ASCII letters, digits or underscores) and a password verifier (a random salt, a slow one-way hash and its settings). The password itself is never stored.
- **Accounts file**: the single file named by `--users` that holds every account. The account command creates and updates it. The server only reads it.
- **Session**: proof that an account holder signed in. It is carried in the `session` cookie as a signed token holding the username, the issue time and the expiry time (issue time + 30 minutes). It is valid only while it is unexpired, its signature checks against the server secret, it has not been signed out, and it was issued by the server's current run.
- **Signed-out session**: a session token that has been ended by sign-out. The server must remember it until its expiry time or until the server stops, so that copies of it are refused (FR-020). After a restart, FR-027 refuses it anyway.
- **Sign-in lock state**: for each account, the number of failed sign-ins in a row and, while locked, the time the lock began (FR-030).
- **Server secret**: the value of `LOGINAPP_SECRET`. It signs and verifies sessions. Changing it invalidates every existing session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator who follows the quickstart can create an account, start the server and sign in through a web browser within 2 minutes.
- **SC-002**: A successful sign-in, from submitting the form to seeing the welcome page, takes less than 2 seconds on a typical developer laptop.
- **SC-003**: In 100% of tested cases, a failed sign-in looks the same whether the username does not exist, the password is wrong or the username is locked: same status, page and message, with timing within a factor of 2. So an observer cannot learn which usernames exist or are locked.
- **SC-004**: No account password ever appears in readable form in the accounts file, in the program's output or in its logs (0 occurrences across the test suite).
- **SC-005**: 100% of missing, altered, forged, wrongly signed, expired or signed-out sessions, and sessions from before a server restart, are refused. Dashboard content is never shown without a valid session.
- **SC-006**: Every session stops giving access no later than 30 minutes after sign-in.
- **SC-007**: 100% of the invalid command-line inputs defined in this specification give a readable error message and the documented exit status. None produces a crash trace.
- **SC-008**: The application runs on a machine that has only the standard language runtime installed, with no additional packages to install.
- **SC-009**: Every functional requirement is covered by at least one passing automated test that cites its FR ID.
- **SC-010**: 100% of signed-out session tokens are refused from the moment of sign-out until they expire, including after the server restarts.
- **SC-011**: After 5 wrong passwords in a row for an account, 0 sign-ins for it succeed during the next 15 minutes, even with the right password. A refusal caused by the lock cannot be told apart from any other failed sign-in.

## Assumptions

- **What "secure" covers**: besides the product owner's explicit rules, "secure login" is taken to mean salted, slow password hashing (FR-005), owner-only file permissions (FR-006), identical and similarly timed failures for unknown users and wrong passwords (FR-015, FR-016), strict token checks (FR-023), protected cookies (FR-025), standard protective response headers (FR-028), a request size limit (FR-015) and no secrets in output (FR-029). The product owner added server-side sign-out (FR-020) and a lock on a username after repeated failed sign-ins (FR-030).
- **Sign-out across restarts**: the product owner's answer is that a signed-out token "must stop working". This is read as applying for the token's whole remaining lifetime, including after a server restart. Two ways to achieve that were considered. One is to save the record of signed-out tokens in a file. That would need a storage location, and the product owner's command-line contract defines none. The other is for the server to refuse every token issued before it started. That needs no new file or option, so it was chosen (FR-027), even though it means a restart signs everyone out. `/speckit-clarify` can revisit this choice.
- **Telling runs apart**: the token holds only `sub`, `iat` and `exp`, with times in whole seconds. So planning must make sure FR-027 still holds when a new run starts in the same second as a token from the previous run. This must work without adding claims to the token.
- **Lock state is not kept across restarts** (FR-030): only the operator can restart the server, so this gives an attacker no way around the lock.
- **Lockout as a nuisance**: anyone who can reach the server can lock a username by sending 5 wrong passwords, including from a web page on another site in the same browser. The product owner chose this trade-off. There is no way to unlock early: a lock ends after 15 minutes, or when the server restarts.
- **Signature comparison**: session signatures are compared in constant time. This is a design rule for planning and review, not a separate behavioural requirement, because no reliable automated test can observe it.
- **Removed accounts**: no command removes accounts. A session therefore stays valid until it expires, is signed out or the server restarts, even if someone deletes the account from the file by hand. The dashboard does not re-read the accounts file.
- **Local, single machine**: the server listens on the loopback address only, so traffic never leaves the machine. Plain HTTP is used (no TLS), so the session cookie is not marked `Secure`. Browsers may refuse such cookies over plain HTTP, and the cookie would never travel over a network anyway.
- **Exit status convention**: 0 means success, 1 an environment or file problem (including a missing secret, as allowed by "non-zero status"), 2 invalid command-line usage or input, and 3 an existing username.
- **Password entry**: the account command expects the password to be piped in. It shows no prompt and does not hide typed input, so standard output carries only the `added USERNAME` line.
- **No maximum password length** is set beyond what fits in a sign-in request (64 KiB).
- **Password hashing** uses a slow, salted password-hashing function that the standard library provides. Planning chooses the function and its cost settings. They must meet the OWASP minimums (FR-005) and still allow the 2-second sign-in target (SC-002).
- **The accounts file format** is chosen during planning. The file is assumed to change only through the account command.
- **The secret** is used as its UTF-8 bytes. Any non-empty value is accepted, because the product owner's own example uses `change-me`. Choosing a strong secret is the operator's responsibility.
- **Time** comes from the system clock, with no tolerance at expiry.
- **Cross-site request forgery** is handled by the `SameSite=Strict` cookie attribute. Forged sign-in requests from other sites are low-impact for a local, single-machine application, apart from the lockout nuisance above, and get no further defences.
- **The HTTP version** shown in the status line (`HTTP/1.0` in the examples) is not part of the contract.
- **Stopping the server** (for example with Ctrl+C) is the operator's way to shut it down. No particular exit status is required.
- **Python versions**: the target is Python 3.11 or newer. This environment checks the code on Python 3.13, so the code may use only standard library features that exist in both 3.11 and 3.13.
- **Out of scope**: removing accounts, changing or resetting passwords, unlocking a username early, signing out all of a user's sessions at once, sign-up through the web, roles and permissions, "remember me", HTTPS, serving on addresses other than 127.0.0.1, and a home page at `/` (the product owner specified 404 for every other path).
