# Research: Secure Login Web Application

**Feature**: `001-secure-login-app` | **Date**: 2026-10-23 | **Plan**: [plan.md](plan.md)

This file records each design decision the plan depends on. Every decision names the requirement it serves. Measurements were taken in this environment: CPython 3.13.17 (and 3.11.17 for compatibility probes), OpenSSL 3.0.13, 2 vCPUs, 8 GiB RAM, Linux, running as root.

No `NEEDS CLARIFICATION` items remain. Decisions a product owner might want to review are marked **(review)**.

---

## R1. Password hashing (FR-005, FR-016, SC-002)

- **Decision**: `hashlib.scrypt`, with the following settings:
  - `n = 131072` (2^17), `r = 8`, `p = 1`, `dklen = 32`.
  - Salt: 16 bytes from `secrets.token_bytes`, a new salt for each account.
  - The call passes `maxmem = 268435456` (256 MiB). OpenSSL's default limit (32 MiB) rejects `n = 2^17`; the call needs 134,220,800 bytes, measured. `maxmem` is a limit, not an allocation.
  - A module-level `threading.BoundedSemaphore(4)` lets at most 4 hashes run at once, so peak hashing memory stays near 512 MiB.
  - Stored hashes are compared with `hmac.compare_digest`.
- **OWASP minimum**: these settings are the scrypt minimum in the OWASP Password Storage Cheat Sheet: N=2^17 (128 MiB), r=8 (1024 bytes), p=1. **(review)** The values come from the cheat sheet as known to the planner. This session's rules forbid web access, so they were not checked online again. Tests pin these exact values (FR-005). If OWASP has raised them, change this section and the constants together.
- **Measured cost**:
  - One hash takes 0.42–0.46 s.
  - 4 hashes at once take 0.92 s, because `hashlib.scrypt` releases the GIL and the work runs in parallel.
  - 10 hashes at once take 2.5 s.
  - A sign-in therefore takes about 0.5 s, well within the 2 s target (SC-002).
  - The test suite pays this cost for every sign-in attempt it makes (see R11).
- **Rationale**:
  - scrypt is the strongest password-hashing function in the standard library. Argon2id and bcrypt are not in the stdlib.
  - scrypt is memory-hard, so an accounts file that leaks is costly to crack on GPUs.
  - The semaphore exists because each hash allocates 128 MiB. Without a cap, a burst of simultaneous sign-ins could exhaust memory and kill the server. That would break FR-031 ("keep serving") and the 10-simultaneous-attempts rule in FR-030.
- **Alternatives considered**:
  - PBKDF2-HMAC-SHA256 with 600,000 iterations, the OWASP minimum (0.35–0.39 s measured). It is simpler (no memory cap needed) and meets FR-005. Rejected because it is not memory-hard. OWASP ranks scrypt above PBKDF2 and recommends PBKDF2 mainly where FIPS-140 compliance is required.
  - Raising scrypt costs above the minimum: rejected, because it adds latency and memory for no requirement.
  - No concurrency cap: rejected, for the memory reason above.

## R2. Accounts file format and writing (FR-005, FR-006, FR-007, FR-011)

- **Decision**: a UTF-8 JSON document. The exact schema is in [data-model.md](data-model.md#accounts-file).
  - Top level: an object `{"accounts": {USERNAME: RECORD, ...}}`.
  - Each record holds the algorithm name and the cost settings, plus `salt` and `hash` as lowercase hex.
  - **Validation** runs on every load: startup, `adduser`, and every well-formed sign-in. It is strict, and any deviation makes the file "not a valid accounts file":
    - duplicate JSON keys are rejected with an `object_pairs_hook`;
    - the set of keys must be exact;
    - the algorithm and settings must be the exact values from R1;
    - the hex fields must have the exact lengths;
    - every username key must satisfy the FR-002 rule.
  - **Writing** (`adduser` only):
    - serialise with `json.dumps(..., indent=2, sort_keys=True)` plus a final newline;
    - `tempfile.mkstemp(dir=<FILE's folder>)` creates the temporary file with mode `0o600` from the start;
    - write, flush and `os.fsync`, then `os.replace(temp, FILE)`;
    - on any failure, delete the temporary file and leave FILE alone.
  - Each successful `adduser` therefore leaves FILE with mode `0600`, even if it was `0644` before (FR-006). The server sees either the old file or the new one, never a half-written one (FR-011).
- **Rationale**: `json` is in the stdlib and easy to read for review. Strict validation follows Principle II. `os.replace` is atomic on POSIX and Windows.
- **Alternatives considered**:
  - `sqlite3`: atomic, but heavier than one small JSON document.
  - `dbm` / `shelve`: the format depends on the platform, and updates are not atomic.
  - `pickle`: unsafe to load.
  - Line-based text: needs a hand-written escaping scheme.
  - Base64 instead of hex: `b64decode` accepts non-canonical input unless extra checks are added. A fixed-length lowercase-hex regex is simpler to check exactly.
- **Not supported**: two `adduser` commands running at the same moment on the same file. One of the two additions could be lost. The spec assumes that FILE changes only through the account command, which the operator runs. Locking would need `fcntl` (POSIX only) for a case the spec does not raise. **(review)**

## R3. HTTP server (FR-008, FR-012, FR-021, FR-022, FR-028, FR-030, FR-031)

- **Decision**:
  - `http.server.ThreadingHTTPServer` bound to `("127.0.0.1", PORT)`, with one `BaseHTTPRequestHandler` subclass.
  - `protocol_version` stays at `HTTP/1.0`, so every connection closes after one response. This matches the spec's example output.
  - The handler sets `error_content_type = "text/html; charset=utf-8"`.
  - It overrides `end_headers` to add `Cache-Control: no-store`, `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff`. These headers therefore also appear on the errors that http.server generates itself (400, 414, 431, 501, 505).
- **Rationale**:
  - The product owner named `http.server`.
  - Threads are needed so that one slow request (a 0.5 s hash, or a stalled client) does not block every other client. Shared state is protected by a lock (R7).
  - Keeping HTTP/1.0 avoids keep-alive, pipelining and request desync.
- **Probes that shaped this**:
  - The constructor binds and listens, so "accepting connections" is true before the `listening on` line is printed.
  - A second bind to a port in use fails with `EADDRINUSE` even with `SO_REUSEADDR` (FR-010).
  - A socket bound to 127.0.0.1 refuses connections to 127.0.0.2 on Linux, which gives tests a way to check loopback-only binding.
  - On Python 3.11 the default `error_content_type` is `text/html;charset=utf-8` (no space), so the override is required by FR-012.
- **Alternatives considered**:
  - Single-threaded `HTTPServer`: one stalled client would freeze the server.
  - `wsgiref`: adds a layer for no benefit.

## R4. Sessions across restarts (FR-023, FR-027)

- **Decision**: each server run keeps an in-memory **registry of the tokens it issued**, a map from token string to `exp`.
  - A session is valid only if all of these hold:
    - the token passes the stateless JWT checks (R6);
    - its exact string is in the registry;
    - it is not signed out (R5);
    - the current time is before `exp`.
  - Expired entries are removed at each sign-in and sign-out.
  - A new run starts with an empty registry, so every earlier token is refused (FR-027). This holds even if the new run starts in the same second the old one issued a token.
- **Same-second rule**: the registry alone leaves one gap. Suppose the new run issues a token for the same user in the same second as the old run did. That token is byte-identical to the old one, so a kept copy of the old token would work again.
  - To close the gap, the server records `run_start = int(clock())` right after binding the port. It issues only tokens with `iat > run_start`.
  - A sign-in in the run's first second therefore waits until the next second; the waiting rule is shared with R5.
  - On the same port, the earlier run must have released the port before this run could bind it, so all of its tokens have `iat <= run_start`. This run therefore never re-creates them.
  - Two servers running at the same time on different ports are separate servers, not a restart. They are not covered.
- **Rationale**: this is the simplest approach that is exactly correct. It needs no extra claims and no storage.
- **Alternatives considered**:
  - Accepting any token with `iat > run_start` and keeping no registry: this is one integer instead of a dict. It is rejected because it is only correct while the wall clock never moves backwards. If the clock is stepped back between runs, for example by an NTP correction, every unexpired token from the earlier run would pass again. That breaks FR-027's "MUST be refused". With the registry, a step back can only matter in the narrow re-creation case in R13. The registry costs one dict and a sweep of expired entries.
  - A per-run signing key: violates FR-024, which requires signing with `LOGINAPP_SECRET` itself.
  - Saving issued or revoked tokens to a file: the CLI contract defines no place to store such a file (see the spec's Assumptions).

## R5. Sign-out (FR-019, FR-020)

- **Decision**:
  - `POST /logout` with a session that is valid at that moment moves the token from the registry to a **signed-out map** (token → `exp`). This happens under the state lock, before the response is written.
  - Entries leave the signed-out map once they expire. A restart clears both maps, and FR-027 then refuses every older token anyway.
  - **Re-encoded copies** are refused by the canonical-encoding rule in R6: a segment must re-encode to exactly itself. Added `=` padding and an altered last character are therefore malformed. They would not be in the registry either.
  - **Signing in again in the same second**: suppose a token is signed out and the same user signs in again within the same second. The new token would be byte-identical to the signed-out one, and FR-020 requires refusing it. In that case sign-in waits until the next whole second and builds the token again with the new `iat`. The wait is at most 1 s, so sign-in still takes under 1.5 s (SC-002).
- **Why this matters**: tests and users commonly sign in, sign out and sign in again. A sign-in takes about 0.5 s of hashing, so without the wait the second token would collide in about half of all runs. That user would then get a 303 to a dashboard that immediately sends them back to the login page.
- **Alternatives considered**:
  - Deleting the token from the registry only: the next same-second sign-in would bring a signed-out copy back to life, violating FR-020.
  - Adding a `jti` claim: forbidden, because the claims are fixed (FR-024).
  - Back-dating or forward-dating `iat`: violates FR-024 or SC-006.

## R6. JWT implementation (FR-023, FR-024, FR-025)

- **Decision**: a small hand-written HS256 implementation using `hmac`, `hashlib.sha256`, `base64.urlsafe_b64encode` and `urlsafe_b64decode`, and `json`.
  - **Encoding**:
    - the header is the exact bytes `{"alg":"HS256","typ":"JWT"}`;
    - the payload is `{"sub":…,"iat":…,"exp":…}` with compact separators;
    - every segment is base64url with the padding removed;
    - the signature is HMAC-SHA256 over `ASCII(b64(header) + "." + b64(payload))`, keyed with `LOGINAPP_SECRET.encode("utf-8")`.
  - **Decoding** is a pure function `decode(token, secret, now) -> claims`. It raises `InvalidToken` and never returns a sentinel (Principle II). It checks, in order:
    1. ASCII only, exactly 3 dot-separated segments.
    2. Each segment uses only `[A-Za-z0-9_-]`, is not empty, and is canonical: decoding and re-encoding gives the same text.
    3. The header is a JSON object with no duplicate keys, and its `alg` is the string `"HS256"`.
    4. The signature is checked with `hmac.compare_digest` before the payload is parsed.
    5. The payload is a JSON object with no duplicate keys: `sub` is a `str`, and `iat` and `exp` are `int` but not `bool`.
    6. `now < exp`, with no clock tolerance.
- **Checked here**: the HMAC and base64url code reproduces the RFC 7515 Appendix A.1 HS256 signature. A non-canonical last character decodes to the same bytes as the original (`…k` and `…l`), so `urlsafe_b64decode` alone would accept a re-encoded copy.
- **Why keep the stateless checks**: the registry (R4) is keyed by the exact token string, so on its own it would already refuse forged and re-encoded tokens. The stateless checks still earn their place:
  - they implement FR-023's list item by item;
  - they make `decode` refuse the FR-020 re-encodings by itself, so these cases can be unit-tested without a server;
  - they cost microseconds;
  - the canonical check is one comparison.
- **Alternatives considered**: PyJWT is third-party and forbidden by Principle I.

## R7. Failed sign-ins and lockout (FR-014, FR-015, FR-016, FR-030)

- **Decision**: in-memory dicts `failures[username] -> int` and `locked_at[username] -> float`, protected by the single state lock. Only usernames that exist in the file are ever keys, so the memory used is bounded by the number of accounts. A well-formed attempt is handled like this:
  1. Read and validate the accounts file. On error, respond 500 and leave the lock state unchanged (FR-011).
  2. Hash the submitted password **outside the lock**, always exactly once:
     - against the account's own record if the username exists, even when it is locked;
     - against a fixed dummy salt with the same settings if it does not exist.
     Every failure case therefore costs one scrypt (FR-016).
  3. **Under the lock**, at time `t = clock()`:
     - If the username has no account: fail, and count nothing.
     - If it is locked and `t - locked_at < 900`: fail. Nothing is counted and the lock is not extended.
     - If it is locked and the 900 s are up: clear the lock, set the count to 0, and continue.
     - If the password is correct: reset the count and issue a token (R5).
     - Otherwise: add 1 to the count. If it reaches 5, set `locked_at = t`, reset the count, and fail.
- **Rationale**:
  - The lock decision and the count update happen in one critical section. So 10 simultaneous wrong attempts produce exactly 5 counted failures and a lock, and the rest are refused without being counted (FR-030's concurrency example).
  - Hashing outside the lock keeps sign-ins for different users running in parallel.
  - The same time source drives tokens and locks, so a test can control both with one fake clock (R11).
- **Not counted**: malformed submissions skip steps 1–3. They get an immediate 401 and count for no one.
- **Malformed submissions and a broken file (review)**: FR-011 says a sign-in attempt must get 500 when FILE is unreadable, and FR-015 says malformed submissions get 401. The plan reads FILE only for well-formed attempts. So a malformed submission gets 401 even while FILE is broken, and a well-formed one gets 500.

## R8. Request parsing (FR-015, FR-018, FR-021, FR-022, FR-028)

- **Path**: the path is the raw request-target from `self.requestline`, cut at the first `?`. `self.path` is not used, because http.server folds a leading `//` into `/` and would then match `//login` as `/login`. FR-021 requires exact matching, so `//login` must get 404.
- **HTTP/0.9**: the handler refuses HTTP/0.9 requests (`GET /login` with no version) by overriding `parse_request`. It switches `request_version` to `HTTP/1.0` and sends 400. The reason is that HTTP/0.9 responses have no headers at all, which would break FR-012 and FR-028.
  - On 3.11, http.server still reads header lines for HTTP/0.9 before calling the override. The request therefore waits for a blank line first.
- **Methods**: `do_GET` and `do_POST` are implemented. For any other method, http.server's own 501 is sent, with the HTML body and the protective headers (FR-022).
- **`POST /login` body**, checked in this order:
  1. More than one `Content-Length` header, or a value that is not one or more ASCII digits (after the header parser's usual trimming), → **400** (an invalid declared body length).
  2. A declared length over 65,536 → **413**, without reading the body.
  3. Read exactly the declared number of bytes. If fewer arrive before end-of-stream → **400**, treated as an invalid declared length. **(review)**
  - No `Content-Length` header means an empty body. The spec says "no declared body length counts as an empty body", so a request with `Transfer-Encoding: chunked` and no `Content-Length` gets the standard 401, and its body is never read. `Transfer-Encoding` is not given any meaning of its own. The connection closes after one response (R3), so unread bytes cannot be taken as a second request.
  4. Any of the following → **401**, the standard failure:
     - the `Content-Type` header is missing or appears more than once;
     - its media type, compared case-insensitively and ignoring parameters, is not `application/x-www-form-urlencoded`. Parameters such as `charset` are ignored, and the body is always decoded as UTF-8;
     - the body bytes are not valid UTF-8. Raw UTF-8 (as `curl -d` sends it) and percent-encoded UTF-8 (as browsers send it) are both accepted;
     - `urllib.parse.parse_qsl(text, keep_blank_values=True, encoding="utf-8", errors="strict")` raises an error, for example on a percent-escape that decodes to invalid UTF-8;
     - `username` or `password` is not present exactly once with a non-empty value.
- **Cookies**: the cookie header is parsed by hand.
  - All `Cookie` header lines are joined. They are split on `;` and each pair on the first `=`, with spaces stripped.
  - Exactly one non-empty `session` value counts as a candidate. Zero values, more than one, or an empty value means no session.
  - `http.cookies.SimpleCookie` was rejected: it silently drops pairs it cannot parse and it accepts quoted values, which makes "repeated" and "malformed" impossible to detect reliably.
- **Logout body**: `POST /logout` never reads the body.

## R9. Responses, errors and logging (FR-012, FR-019, FR-028, FR-029, FR-031)

- **Building responses**: each route function returns `(status, headers, body_bytes)`, and one `send` function writes the result. Nothing is written until the response is complete, so an exception can always be turned into a clean 500.
- **Redirects**: 303 responses have `Content-Length: 0` and no body.
- **Unexpected errors (FR-031)**:
  - The dispatcher catches `Exception` and writes a report to stderr: `loginapp: internal error while handling METHOD PATH: ExceptionType`, followed by the stack frames from `traceback.format_tb`. PATH is the routed path, without the query string.
  - The exception *message* is left out because it can contain request data, and FR-029 forbids writing secrets.
  - The client gets a generic 500 page, and the server keeps running.
- **Errors outside the dispatcher**: `LoginServer.handle_error` is overridden. Probed on 3.11: a client that disconnects early makes socketserver print a full traceback, including exception messages. The override writes one line instead: `loginapp: error: connection failed: ExceptionType`. Examples are `BrokenPipeError` and `ConnectionResetError`. The server keeps running.
- **Request logging**: `log_message` is overridden to do nothing, so there is no request logging. The spec allows request lines but does not require them. http.server's default log line contains the full request line, which could include a password or token in the query string. Its `log_error` echoes raw request lines. Turning both off is the simplest way to guarantee FR-029.
- **Accounts file broken at sign-in (FR-011)**: one line goes to stderr, `loginapp: error: …` naming FILE, and the client gets 500.
- **HTTP version differences**: reason phrases differ between Python versions. For example, 413 is "Request Entity Too Large" on 3.11 and "Content Too Large" on 3.13. Only status codes are part of the contract, and tests check only codes.

## R10. Command-line parsing (FR-001–FR-004, FR-007, FR-009, FR-010)

- **Decision**: `argparse`, with `allow_abbrev=False` on the main parser and on both subparsers. The subcommand is required.
  - A custom action rejects a repeated option. For example, `--users a --users b` exits with status 2. Probed: argparse would otherwise keep the last value silently.
  - `--port` uses a `type=` function that accepts only 1–5 ASCII digits whose value is 1–65535. Probed: `int()` alone accepts `+8000`, ` 8000`, `8_000` and non-ASCII digits. A port error therefore happens during argument parsing (exit 2), which is first in the FR-010 order.
  - argparse's usual equivalents are accepted: `--users=FILE`, and options before or after the positional. **(review)**
- **Password input**:
  - `sys.stdin.buffer.readline()` reads the first line as bytes. One trailing `\n` or `\r\n` is removed, and a lone `\r` at the end of the input stays part of the password.
  - The bytes are decoded as UTF-8 (`strict`). The length check counts characters.
  - Standard input is not read at all if the username is invalid.
- **Secret**: `LOGINAPP_SECRET` that is unset or empty → exit 1. A value that cannot be encoded as UTF-8 also exits with status 1, naming the variable. **(review)** This can happen on POSIX, where an environment value with invalid bytes arrives with surrogate escapes.
- **Messages**:
  - Every message is one `loginapp: error: …` line on stderr. Values the user supplied are quoted with `repr()`, so control characters cannot change the terminal.
  - The exact texts are in [contracts/cli.md](contracts/cli.md).
  - `Ctrl+C` during `serve` prints `loginapp: stopped` to stderr and exits with status 130. It does not print a traceback.

## R11. Test strategy (Principle III, SC-009)

- **Running**:
  - `python3 -m pytest` from the repository root.
  - `pyproject.toml` holds only `[tool.pytest.ini_options]` with `pythonpath = ["src"]` and `testpaths = ["tests"]`. `testpaths` keeps the run on this feature's suite rather than the study tooling under `tools/`.
  - Tests import only the stdlib, pytest and `loginapp`.
- **Three kinds of test**:
  - **Subprocess tests** run `sys.executable -m loginapp` with `PYTHONPATH=<repo>/src`. They cover the CLI, startup, `listening on` buffering, restarts and the absence of secrets in output.
  - **In-process server tests** use `server.make_server(port, users_path, secret, clock=…, sleep=…)` in a background thread. A `FakeClock` provides `time()`, and a `sleep()` that moves the fake time forward. These tests cover the 1800 s and 900 s boundaries, FR-027's same-second case and the FR-020 sign-in-again wait, none of which can be tested in real time. The clock parameters are internal; the CLI does not expose them.
  - **Unit tests** call the `tokens`, `accounts` and page-rendering functions directly.
- **Root caveat**: the tests run as root, so changing permissions cannot make a file unreadable. Tests produce "unreadable" another way: by putting a directory where FILE should be, which raises `IsADirectoryError`. For "cannot be created", they point FILE into a folder that does not exist, or below a regular file.
- **413 caveat**: a client that sends a large body to a server that closes without reading it may get a TCP reset instead of the response. Probed: 0 of 20 clients saw the 413 with a 10 MB body. So the 413 test sends only the headers, with a large `Content-Length`.
- **Timing test (FR-016)**:
  - 7 attempts for each of three cases: unknown username, wrong password, locked username.
  - It compares the medians, each pair within a factor of 2.
  - Every case costs one scrypt, so the expected ratio is about 1.0. The factor of 2 leaves plenty of room for noise.
- **Cost**:
  - Tests use the real scrypt settings. Runtime code has no test-only "fast hashing" switch, because such a switch would weaken security.
  - To keep the hash count down, a session-scoped fixture builds one accounts file holding `alice` and `bob`, and each test copies it.
  - Expect about 250–300 hashes, about 2–3 minutes on this machine. Most of them come from sign-in attempts and the lockout tests, which need 5 failures each.
- **Python 3.11 checks (FR-032 / constraint)**:
  - Every `src/` file is parsed with `ast.parse(..., feature_version=(3, 11))`.
  - A smoke test runs `adduser`, `serve` and one sign-in under `python3.11` when `shutil.which("python3.11")` finds it, which it does here. This test is extra; the FR-032 tests that cannot be skipped are listed in the plan.
  - Probed: `feature_version` rejects PEP 695 syntax but **not** PEP 701 f-string quote reuse. That is why the smoke test exists, and why implementers follow R12.

## R12. Python 3.11 compatibility rules

- The code must run on 3.11 and newer, and is verified on 3.13.
- Do not use:
  - `type X = …` or `def f[T]` (PEP 695, 3.12);
  - f-strings that reuse the outer quote character or contain backslashes in expressions (PEP 701, 3.12);
  - `typing.override`, `itertools.batched`, `pathlib.Path.walk` (3.12);
  - anything added in 3.13;
  - any module removed in 3.13.
- Allowed modules: `argparse`, `base64`, `hashlib`, `hmac`, `html`, `http.server`, `json`, `os`, `re`, `secrets`, `sys`, `tempfile`, `threading`, `time`, `traceback`, `urllib.parse`. All are in `sys.stdlib_module_names` on 3.11 and 3.13.

## R13. Known risks this plan does not address (review)

None of these is required by the spec, and each would add behaviour that is outside the product owner's contract:

- **DNS rebinding**: a web page on another site could rebind its own hostname to 127.0.0.1 and send sign-in attempts it can read the answers to. The lockout limits this to 5 guesses per username every 15 minutes. Checking the `Host` header would block it, but that adds a response the contract does not define.
- **Slow or idle clients**: there is no per-connection timeout, so a local client can hold a thread open indefinitely.
- **Concurrent `adduser`** (R2).
- **No `Secure` cookie attribute**: the server uses plain HTTP over loopback, as recorded in the spec's Assumptions.
- **System clock stepped backwards between runs**: if the clock is set back, a new run could sign in the same user in exactly the same second as an earlier run did. It would then re-create that run's token bytes (R4). This needs the same username, the same `iat` second and a clock change, so it is not handled.
