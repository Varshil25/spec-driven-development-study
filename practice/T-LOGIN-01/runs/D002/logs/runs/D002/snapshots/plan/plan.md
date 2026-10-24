# Implementation Plan: Secure Login Web Application

**Branch**: `001-secure-login-app` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-secure-login-app/spec.md`

**Planning guidance from the product owner**: Use Python 3.11 or newer and the standard library only, as the specification says. Follow the interface in the specification exactly. Use pytest for tests.

## Summary

The product is a local web application with two parts:

- `python -m loginapp adduser` adds accounts to a JSON accounts file. It stores a salted scrypt hash of each password, never the password.
- `python -m loginapp serve` runs an `http.server` web server on 127.0.0.1. It offers a login page, a private dashboard and sign-out.

Sessions are HS256 JWTs in an `HttpOnly; SameSite=Strict` cookie, written with `hmac`, `hashlib` and `base64`. They last 30 minutes.

Each server run keeps three things in memory:

- a registry of the tokens it issued, so that tokens from earlier runs are refused (FR-027);
- a map of signed-out tokens (FR-020);
- per-username failure counts and locks, so that 5 failures in a row lock a username for 900 s (FR-030).

All of this state sits behind one lock. Failed sign-ins of every kind cost exactly one scrypt hash, so they take the same time (FR-016). Everything is Python standard library. pytest is used for tests only.

## Technical Context

**Language/Version**:

- The code is written for Python ≥ 3.11 (product owner).
- It is verified on CPython 3.13.17, as the constitution's Technical Constraints require.
- A smoke test also runs it on the CPython 3.11.17 installed here.
- The code uses only features present in both versions ([research R12](research.md#r12-python-311-compatibility-rules)).

**Primary Dependencies**: none outside the standard library. The runtime modules are listed in [research R12](research.md#r12-python-311-compatibility-rules).

**Storage**:

- One JSON accounts file, given by `--users`, with mode `0600`, written atomically ([data-model](data-model.md#accounts-file)).
- Session and lock state is kept in memory, for one server run only.

**Testing**: pytest 9.1.1 (development only), run as `python3 -m pytest` from the repository root.

**Target Platform**:

- A local POSIX machine (Linux, macOS), verified on Linux.
- The server binds `127.0.0.1` only. FR-006's owner-only mode relies on POSIX permissions.

**Project Type**: a command-line program that also runs a local web server. It is one Python package under `src/`.

**Performance Goals**:

- A sign-in takes < 2 s (SC-002). Measured: one scrypt hash takes 0.42–0.46 s, and at most 1 s of extra waiting is possible ([research R5](research.md#r5-sign-out-fr-019-fr-020)).
- Request rate is not a goal.

**Constraints**:

- Each scrypt hash uses 128 MiB. At most 4 run at once, so peak memory is about 512 MiB.
- Request bodies are limited to 64 KiB.
- No clock tolerance at session expiry.
- Every failure case costs the same: one hash.

**Scale/Scope**: one operator, a handful of accounts, one machine, a few people signing in.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.0 (`.specify/memory/constitution.md`).

| Gate | Pre-research | Post-design | Evidence |
|------|--------------|-------------|----------|
| **I. Standard Library Only**: runtime imports only stdlib + `loginapp`; nothing to install; pytest not imported by runtime code | PASS | PASS | Module list in [research R12](research.md#r12-python-311-compatibility-rules), all in `sys.stdlib_module_names`. The JWT is hand-written ([R6](research.md#r6-jwt-implementation-fr-023-fr-024-fr-025)), not PyJWT. Enforced by `test_fr032_runtime_imports_stdlib_only` (AST scan of `src/`). |
| **II. Fail Loudly**: every invalid input is rejected with a named message and a non-zero exit or error response; nothing that looks valid goes to stdout; no tracebacks for expected errors; no swallowed exceptions | PASS | PASS | The CLI's order of checks, messages and exit codes are in [contracts/cli.md](contracts/cli.md). The HTTP error responses are in [contracts/http.md](contracts/http.md). Library functions raise `InvalidToken` / `SignInRefused` / `AccountsFileError` and never return sentinels. Unexpected errors become a 500 plus a stderr report (FR-031). Client disconnects become a one-line stderr message ([R9](research.md#r9-responses-errors-and-logging-fr-012-fr-019-fr-028-fr-029-fr-031)). Repeated options are refused, not "last wins" ([R10](research.md#r10-command-line-parsing-fr-001fr-004-fr-007-fr-009-fr-010)). |
| **III. Every Requirement Is Testable**: every FR maps to ≥ 1 pytest test citing its ID; every invalid-input case is tested; no skipped-only coverage | PASS | PASS | See [FR → test map](#fr--test-map) below. Every FR has tests that cannot be skipped. The only skippable test (the 3.11 smoke test) is extra. |
| **IV. Simplicity**: smallest design; plain functions; added complexity recorded | PASS (with entries) | PASS (with entries) | 4 runtime modules plus `__init__`/`__main__`. Classes only where `http.server` requires them (`LoginServer`, `Handler`) and for the three exception types. Every addition beyond the minimum is listed in [Complexity Tracking](#complexity-tracking). |
| **Technical Constraints**: CPython 3.13; pytest; `python3 -m pytest` from the repository root with nothing else set up | PASS | PASS | `pyproject.toml` holds only `[tool.pytest.ini_options]` (`pythonpath = ["src"]`, `testpaths = ["tests"]`). The constitution's CPython 3.13 and the product owner's "3.11 or newer" do not conflict: the code targets the 3.11 subset and is verified on 3.13. |
| **Plan gate** (Workflow §2): stdlib-only confirmed; error behaviour defined; tests named per FR; complexity recorded | PASS | PASS | The four rows above. |
| **Specification gate** (Workflow §1): FR IDs, testable, no `[NEEDS CLARIFICATION]` | PASS | n/a | `checklists/requirements.md` iteration 2; spec has no markers. |

No gate fails, and nothing needs an ERROR. Technical Context has no `NEEDS CLARIFICATION` items. Decisions marked **(review)** in [research.md](research.md) are listed under [Open review points](#open-review-points). They are design choices made within the spec's latitude. None of them blocks planning.

## Project Structure

### Documentation (this feature)

```text
specs/001-secure-login-app/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1–R13
├── data-model.md        # Phase 1: accounts file, token, in-memory state, state machines
├── quickstart.md        # Phase 1: run and validation guide
├── contracts/
│   ├── cli.md           # Phase 1: adduser / serve, check order, messages, exit codes
│   └── http.md          # Phase 1: routes, statuses, headers, cookies, pages
├── checklists/
│   └── requirements.md  # from /speckit-specify
└── tasks.md             # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
pyproject.toml           # [tool.pytest.ini_options] only: pythonpath = ["src"], testpaths = ["tests"]
src/
└── loginapp/
    ├── __init__.py      # package marker (docstring only)
    ├── __main__.py      # `from loginapp.cli import main; raise SystemExit(main())`
    ├── cli.py           # argparse parser, adduser and serve commands, stderr messages, exit codes
    ├── accounts.py      # username/password rules, scrypt hash and verify, accounts-file load/validate/save
    ├── tokens.py        # HS256 JWT encode/decode, canonical base64url, InvalidToken
    └── server.py        # LoginServer (ThreadingHTTPServer + state), Handler, routing, HTML pages, make_server()
tests/
├── conftest.py          # fixtures: run_cli, ServerProcess (subprocess), inproc_server + FakeClock, raw HTTP helper,
│                        #           a session-scoped accounts file holding alice and bob
├── test_adduser.py      # FR-001 – FR-007
├── test_accounts.py     # FR-005, FR-006 (unit)
├── test_serve.py        # FR-008 – FR-010
├── test_tokens.py       # FR-023, FR-024 (unit)
├── test_login.py        # FR-011, FR-013 – FR-016
├── test_sessions.py     # FR-017 – FR-020, FR-023 – FR-027
├── test_routing.py      # FR-012, FR-021, FR-022, FR-028
├── test_lockout.py      # FR-016, FR-030
└── test_robustness.py   # FR-029, FR-031, FR-032
```

**Structure Decision**:

- **Single project** (the template's option 1, without its `models/` and `services/` layers). The program is one small package. The spec fixes its location as `src/loginapp`.
- **Modules**: there are four runtime modules, one per concern the spec names: CLI, accounts, tokens and HTTP server.
  - Page rendering lives in `server.py`, not in a module of its own.
  - `__main__.py` only calls `cli.main()`. Tests can therefore call `cli.main(argv)` in-process, for example to inject a write failure (FR-006), without running the program on import.
- **Study tooling**: the `tools/` and `logs/` directories belong to the study and are not touched. `testpaths` keeps `python3 -m pytest` to this feature's suite.

### Module responsibilities and interfaces

These are the internal interfaces. The external ones are in `contracts/`.

- **`accounts.py`**
  - **Constants**: `USERNAME_RE`, `MIN_PASSWORD_CHARS = 12`, `SCRYPT_N = 2**17`, `SCRYPT_R = 8`, `SCRYPT_P = 1`, `DKLEN = 32`, `SALT_BYTES = 16`.
  - **Exception**: `AccountsFileError(Exception)`. Its message names the file and the rule that failed, never a value.
  - **Functions**:
    - `check_username(name) -> None` and `check_password(text) -> None` raise `ValueError` with the contract message.
    - `make_record(password) -> dict`.
    - `verify(password, record) -> bool`.
    - `dummy_verify(password) -> None`, which does the same work as `verify` for unknown usernames.
    - `load(path, missing_ok) -> dict[str, dict]` raises `AccountsFileError`.
    - `save(path, accounts) -> None` raises `OSError`. It writes atomically with mode `0600`.
  - **Concurrency**: one module-level `BoundedSemaphore(4)` limits how many hashes run at once.
- **`tokens.py`**
  - **Exception**: `InvalidToken(ValueError)`.
  - **Functions**:
    - `encode(sub, iat, key: bytes) -> str`.
    - `decode(token, key: bytes, now: float) -> dict` raises `InvalidToken`, following [data-model steps 1–6](data-model.md#acceptance-fr-023).
- **`server.py`**
  - **Exception**: `SignInRefused(Exception)`, the standard sign-in failure. It carries no detail, so the 401 response cannot differ between cases.
  - **Entry point**: `make_server(port, users_path, secret: str, clock=time.time, sleep=time.sleep) -> LoginServer`.
    - It binds and listens before returning, and sets `run_start`.
    - `clock` and `sleep` are for tests only. The CLI never passes them.
  - **`LoginServer(ThreadingHTTPServer)`**
    - **State**: `lock`, `issued`, `signed_out`, `failures`, `locked_at` and `run_start`.
    - **Operations**:
      - `issue_token(username) -> str`.
      - `session_user(cookie_header) -> str` returns the signed-in username, or raises `InvalidToken` when there is no valid session. The HTTP layer maps that to 303 → `/login`.
      - `sign_out(cookie_header) -> None` revokes the presented token if it is valid, and does nothing otherwise, as FR-019 requires.
      - `attempt(username, password) -> str` returns a new token, or raises `SignInRefused` for the standard failure. The HTTP layer maps that to the 401 page.
      - `AccountsFileError` propagates and becomes 500.
      - No function returns `None` or another sentinel in place of an answer (Principle II).
  - **`Handler(BaseHTTPRequestHandler)`**
    - Overrides `parse_request` (to refuse HTTP/0.9), `end_headers` (protective headers), `log_message` (does nothing) and `do_GET` / `do_POST`. Both of the latter route on the raw request-target.
    - Route functions return `(status, headers, body)`, and one `send()` writes it. An exception anywhere in a route gives the FR-031 500.
  - **Page functions**: `login_page(error: bool)`, `dashboard_page(username)` and `simple_page(title)`. Each returns `bytes`.
- **`cli.py`**: `main(argv=None) -> int`. It builds the parser, runs the checks in order, prints messages and returns the exit code. `serve` prints the ready line with `flush=True`, then calls `serve_forever()`.

### Request flow for `POST /login`

1. Validate `Content-Length`: 400 or 413 ([contracts/http.md](contracts/http.md#post-login-fr-011-fr-014-fr-015-fr-016-fr-030)).
2. Read the body, then parse and validate the form. A malformed form gets the 401 page straight away.
3. Load the accounts file. If that fails, respond 500 and write one line to stderr.
4. Hash outside the lock, always exactly once: `verify()` for a known username (even a locked one), `dummy_verify()` for an unknown one.
5. Under the lock, apply the [lock transitions](data-model.md#transitions-for-a-well-formed-attempt).
6. On success, `issue_token()`, which may wait up to 1 s outside the lock ([data-model](data-model.md#issuing-a-token)). The response is 303 with a `Set-Cookie`. Otherwise it is the 401 page.

## FR → test map

- Every test name starts with `test_frNNN_`, which cites the FR ID (Principle III, SC-009).
- **Kinds of test**: **S** = subprocess (`python -m loginapp`), **I** = in-process server (with `FakeClock` where noted), **U** = unit.
- Every FR has at least one test that cannot be skipped.

| FR | Tests (file :: name) | Kind | What is checked |
|----|----------------------|------|-----------------|
| FR-001 | `test_adduser.py::test_fr001_adds_account_and_prints_added`, `test_fr001_creates_missing_file`, `test_fr001_password_line_handling` (param: `\n`, `\r\n`, no final newline, inner spaces kept, only first line used) | S | stdout is exactly `added alice\n`, exit 0, file holds the account; the password is verified with `accounts.verify` |
| FR-002 | `test_fr002_rejects_bad_usernames` (param: 2 chars, 33 chars, `al-ice`, `josé`, `a b`, empty), `test_fr002_accepts_boundaries` (3, 32, `A_9`) | S | exit 2; stderr names the username and the rule; stdout empty; file unchanged or not created; no `Traceback` |
| FR-003 | `test_fr003_rejects_bad_passwords` (param: 11 chars, empty stdin, invalid UTF-8, 11 multi-byte chars), `test_fr003_counts_characters_not_bytes` (12 × `é` accepted) | S | exit 2; stderr states `12` and does not contain the input; stdout empty; file unchanged |
| FR-004 | `test_fr004_duplicate_exits_3`, `test_fr004_usernames_case_sensitive`, `test_fr004_check_order` (param: existing + short password → 2; bad username + bad password → username message; bad password + broken file → 2; valid + broken file → 1) | S | the exit status and which message wins; file unchanged |
| FR-005 | `test_accounts.py::test_fr005_record_has_pinned_scrypt_settings` (exact `scrypt`, `n=131072`, `r=8`, `p=1`, 16-byte salt, 32-byte hash), `test_fr005_hash_matches_hashlib_scrypt`, `test_fr005_password_absent_from_file` (plain, hex, base64), `test_fr005_same_password_different_records` | U+S | settings equal the values recorded in [research R1](research.md#r1-password-hashing-fr-005-fr-016-sc-002) |
| FR-006 | `test_fr006_file_mode_0600` (new file, and one that was `0644`), `test_fr006_existing_accounts_kept_byte_for_byte`, `test_fr006_failed_write_leaves_file_intact` (in-process `cli.main` with `os.replace` monkeypatched to raise: exit 1, bytes and mode unchanged, no temp file left) | S+I | |
| FR-007 | `test_adduser.py::test_fr007_usage_errors_exit_2` (param: no args, `nope`, `adduser`, missing `--users`, extra argument, `--users a --users b`, `addu`, `--use`, `-h`), `test_fr007_unreadable_file_exits_1` (FILE is a directory), `test_fr007_invalid_file_exits_1` (param: empty, not JSON, duplicate key, wrong `n`, short salt, extra field, bad username key, `true` as integer), `test_fr007_unwritable_location_exits_1` (missing folder; parent is a regular file) | S | usage on stderr; exit code; message names FILE; existing file unchanged |
| FR-008 | `test_serve.py::test_fr008_ready_line_unbuffered` (read through a pipe with a 10 s timeout while the process keeps running), `test_fr008_accepts_connections_after_ready_line`, `test_fr008_loopback_only` (in-process `getsockname()[0] == "127.0.0.1"`; subprocess: a connect to 127.0.0.2 is refused) | S+I | |
| FR-009 | `test_fr009_missing_or_empty_secret` (param: unset, empty) | S | exit 1; stderr names `LOGINAPP_SECRET`; no `listening on` |
| FR-010 | `test_fr010_bad_port_exits_2` (param: `0`, `65536`, `abc`, `-1`, `+80`, `' 80'`, `8_000`, full-width digits), `test_fr010_port_in_use_exits_1`, `test_fr010_bad_accounts_file_exits_1` (missing, directory, invalid), `test_fr010_check_order` (param: bad port + no secret → 2; no secret + missing file → secret message; missing file + busy port → file message) | S | exit code; stderr names the value; no `listening on` |
| FR-011 | `test_login.py::test_fr011_account_added_while_running_can_sign_in`, `test_fr011_broken_file_at_sign_in_gives_500` (then restored → 303) | S | 500 has no `Set-Cookie`; stderr names FILE |
| FR-012 | `test_routing.py::test_fr012_every_body_is_html_utf8` (param over the response table: 200 login, 401, 303, 404, 405, 400, 413, 500, 501 `PUT`, 400 garbage request line, 400 HTTP/0.9) | I | `Content-Type: text/html; charset=utf-8` on every response with a body; body starts with `<!doctype html>` |
| FR-013 | `test_login.py::test_fr013_login_form` (parsed with `html.parser`) | I | 200; form `method=post action=/login`; `username` text input; `password` password input; a submit button; no error message |
| FR-014 | `test_fr014_correct_credentials_redirect_with_cookie`, `test_fr014_extra_fields_ignored`, `test_fr014_content_type_parameters_allowed` (`; charset=UTF-8`, upper-case media type), `test_fr014_percent_encoded_and_raw_utf8` | I | 303, `Location: /dashboard`, `Set-Cookie: session=` |
| FR-015 | `test_fr015_unknown_user_and_wrong_password_identical`, `test_fr015_malformed_submissions_get_401` (param: missing / empty / repeated field, empty body, no `Content-Length`, missing or other `Content-Type`, invalid UTF-8 raw and percent-encoded), `test_fr015_page_does_not_echo_input`, `test_fr015_oversized_body_413_without_reading` (headers only, `Content-Length: 100000000`), `test_fr015_invalid_content_length_400` (param: `abc`, `-1`, `1e3`, two headers), `test_fr015_truncated_body_400` | I | 401 bodies byte-identical; headers identical apart from `Date`; no `Set-Cookie` |
| FR-016 | `test_lockout.py::test_fr016_failure_timing_within_factor_2` (7 attempts each: unknown user, wrong password, locked user; real scrypt) | I | each pair of medians has a ratio ≤ 2 |
| FR-017 | `test_sessions.py::test_fr017_dashboard_welcome_and_logout_form`, `test_fr017_username_is_escaped` (unit `dashboard_page("<b>&\"x")`) | I+U | 200; `Welcome, alice`; form posts to `/logout`; markup is escaped |
| FR-018 | `test_fr018_no_valid_session_redirects` (param: no cookie, empty, repeated `session`, malformed, random text, tampered `sub` → `bob`, other secret, `alg` `none`, `alg` `HS512`, expired, signed out) | I (FakeClock) | 303, `Location: /login`, no body, no `Welcome` |
| FR-019 | `test_fr019_logout_clears_cookie` (param: valid session, no cookie, invalid, expired) | I | 303, `Location: /login`, `Set-Cookie: session=` with `Max-Age=0` and `Path=/` |
| FR-020 | `test_fr020_signed_out_copy_refused`, `test_fr020_reencoded_copy_refused` (`=` padding; last character with the same decoded bytes), `test_fr020_other_sessions_unaffected`, `test_fr020_same_second_sign_in_after_logout_gets_new_token` (FakeClock), `test_serve.py::test_fr020_signed_out_token_refused_after_restart` | I+S | |
| FR-021 | `test_routing.py::test_fr021_unknown_paths_404` (param: `/`, `/dashboard/`, `/login.html`, `//login`, `/LOGIN`, `/logout/x`; GET and POST), `test_fr021_query_string_ignored` (`/login?x=1` → 200) | I | 404 with an HTML body |
| FR-022 | `test_fr022_wrong_method_405_with_allow` (`GET /logout` → `Allow: POST`; `POST /dashboard` → `Allow: GET`), `test_fr022_other_methods_error` (param: `PUT`, `DELETE`, `PATCH` × every path) | I | 405 and its `Allow` value; other methods get a status of 400 or more |
| FR-023 | `test_tokens.py::test_fr023_accepts_valid_token`, `test_fr023_rejects_malformed` (param: 2 or 4 segments, empty segment, non-ASCII, `=` padding, non-canonical last character, characters outside base64url, header not JSON, duplicate header key, missing / `none` / `HS512` / non-string `alg`, bad signature, other secret, payload not an object, `sub` not a string, `iat` a float, `exp` a bool, missing claim, duplicate claim), `test_fr023_expiry_boundary` (`now = exp − 1` accepted; `exp` refused) | U | `decode` raises `InvalidToken`, never returns a sentinel |
| FR-024 | `test_fr024_token_format` (header bytes exactly `{"alg":"HS256","typ":"JWT"}`, no padding, claims are exactly `sub`, `iat`, `exp`, `exp == iat + 1800`, `iat == int(clock)`), `test_fr024_independent_verifier_accepts` (the test's own HMAC-SHA256 verifier), `test_sessions.py::test_fr024_issued_cookie_token_verifies` | U+I | |
| FR-025 | `test_sessions.py::test_fr025_cookie_attributes` | I | `HttpOnly`, `SameSite=Strict`, `Path=/`, `Max-Age=1800` |
| FR-026 | `test_fr026_dashboard_sets_no_cookie`, `test_fr026_fixed_lifetime_despite_use` (FakeClock: dashboard at `iat+1799` → 200, at `iat+1800` → 303) | I | |
| FR-027 | `test_serve.py::test_fr027_restart_refuses_earlier_tokens` (subprocess restart with the same secret), `test_sessions.py::test_fr027_same_second_restart` (two in-process servers on one `FakeClock` in the same second), `test_fr027_current_run_tokens_accepted_until_expiry` | S+I | |
| FR-028 | `test_routing.py::test_fr028_protective_headers_everywhere` (same response table as FR-012) | I | the 3 headers with their exact values |
| FR-029 | `test_robustness.py::test_fr029_no_secrets_in_output` (full subprocess flow: adduser, serve, good and bad sign-ins, lock, logout, broken file, then SIGINT; scan all stdout and stderr), `test_fr029_internal_error_report_has_no_request_data` | S+I | stdout and stderr contain no password, secret, token, salt or hash hex; the stop message has no `Traceback` |
| FR-030 | `test_lockout.py::test_fr030_five_failures_lock`, `test_fr030_lock_ends_at_900_seconds` (FakeClock: `+899` refused, `+900` accepted), `test_fr030_success_resets_count`, `test_fr030_locked_attempts_not_counted_or_extending`, `test_fr030_lock_is_per_username`, `test_fr030_unknown_case_variant_and_malformed_not_counted`, `test_fr030_existing_session_survives_lock`, `test_fr030_concurrent_failures_lock` (10 simultaneous threads), `test_fr030_new_server_has_no_locks`, `test_fr030_locked_response_identical` | I | the locked 401 is byte-identical to an ordinary 401 |
| FR-031 | `test_robustness.py::test_fr031_unexpected_error_generic_500_and_continues` (`dashboard_page` monkeypatched to raise `RuntimeError("detail-xyz")`) | I | 500 with the generic page; `detail-xyz` appears in neither the body nor stderr; stderr has the report; the next request gets 200 |
| FR-032 | `test_fr032_runs_as_module_with_src_on_path`, `test_fr032_runtime_imports_stdlib_only` (AST scan: every top-level import is in `sys.stdlib_module_names` or is `loginapp`), `test_fr032_python311_syntax` (`ast.parse(..., feature_version=(3, 11))`), `test_fr032_python311_smoke` (skipped only if `python3.11` is absent; extra) | S+U | |

### Invalid-input coverage (Principle III)

Each invalid-input case in the spec's Edge Cases has a test above:

| Edge case | Tests |
|-----------|-------|
| username and password boundaries | FR-002, FR-003 |
| password input forms | FR-001, FR-003 |
| several problems at once | FR-004, FR-010 order tests |
| accounts-file problems | FR-007, FR-010, FR-011 |
| port problems | FR-010 |
| malformed sign-ins | FR-015 |
| odd cookies | FR-018 |
| re-encoded tokens | FR-020, FR-023 |
| lock boundaries and counting | FR-030 |
| restarts | FR-027 |
| exact expiry | FR-023, FR-026 |
| paths and methods | FR-021, FR-022 |
| internal errors | FR-031 |

Each test asserts the message or response as well as the status.

### Test-suite notes

- **Running it**:
  - Tests use real scrypt settings. There is no fast-hash switch in runtime code.
  - The suite needs about 250–300 hashes, roughly 2–3 minutes here.
  - The `alice` and `bob` accounts file is built once per session and copied into each test.
- **Environment limits**:
  - The tests run as root, so "unreadable" is produced by using a directory as FILE, not by changing permissions.
  - The 413 test sends only the headers, because a large body causes a TCP reset ([research R11](research.md#r11-test-strategy-principle-iii-sc-009)).
- **Timeouts**:
  - Each subprocess server is started on a free port found by binding to port 0, and stopped in a `finally`.
  - Every socket and subprocess read has a timeout, so no test can hang.

## Open review points

These are decisions made within the spec's latitude. They are flagged **(review)** in [research.md](research.md). None blocks `/speckit-tasks`. Each can be changed by updating the named section.

1. **scrypt settings** (R1): `n=2^17, r=8, p=1`, recorded as the OWASP minimum. They were not re-checked online, because this session forbids web access.
2. **Concurrent `adduser`** (R2): not protected. Two `adduser` commands run at the same moment on one file could lose one of the additions.
3. **Short request body** (R8): when fewer bytes arrive than `Content-Length` declares, the response is 400, treated as an invalid declared length.
4. **Broken accounts file and malformed sign-ins** (R7): a malformed sign-in gets 401 without reading FILE, so it gets 401 even while FILE is broken. A well-formed sign-in gets 500.
5. **argparse equivalents** (R10): `--users=FILE`, and options in any order, are accepted. A repeated option is refused with status 2.
6. **Non-UTF-8 `LOGINAPP_SECRET`** (R10): exits with status 1, naming the variable.
7. **Risks not addressed** (R13): DNS rebinding (no `Host` check), no idle-connection timeout, and a system clock stepped backwards between runs.

## Complexity Tracking

> Principle IV deviations beyond "plain functions and built-in types". Each one names the requirement that needs it.

| Addition | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|-------------------------------------|
| `ThreadingHTTPServer` plus one state lock (a `LoginServer` subclass holding state) | FR-030: the count must be correct under simultaneous attempts. SC-002: sign-in in under 2 s. FR-031: keep serving. | A single-threaded `HTTPServer` lets one stalled connection block every user. It also runs 10 simultaneous sign-ins one after another (~4.5 s). |
| Process-wide `BoundedSemaphore(4)` around scrypt | FR-031 / FR-030: each hash needs 128 MiB, and a burst of sign-ins must not exhaust memory. | No cap: an uncapped burst could kill the process. PBKDF2 (needs no memory cap): not memory-hard, and OWASP ranks it below scrypt (R1). |
| Issued-token registry + signed-out map + `run_start` and wait-for-next-second rule | FR-020 (copies refused, including after a same-second sign-in again); FR-027 (earlier runs refused, including in the same second) | Signed-out set only: fails FR-027. `iat > run_start` only: fails if the clock steps back. Per-run signing key: violates FR-024. File-based record: no storage location in the contract (R4, R5). |
| Hand-written JWT with a canonical-base64url check | FR-023, FR-024; FR-020 (re-encoded copies refused) | PyJWT is third-party (Principle I). `urlsafe_b64decode` alone accepts padding and non-canonical final characters (R6). |
| Hand-written `Cookie` header parsing | FR-018: repeated and malformed `session` cookies must count as no session | `http.cookies.SimpleCookie` silently drops pairs it cannot parse and merges duplicates (R8). |
| Routing on the raw request-target; `parse_request` override for HTTP/0.9; `handle_error` override | FR-021: exact paths, so `//login` → 404. FR-012 / FR-028: headers on every response. FR-029: no exception messages in output. | `self.path` turns `//login` into `/login`. HTTP/0.9 responses have no headers. The default `handle_error` prints full tracebacks (R8, R9). |
| argparse action that refuses repeated options; strict `--port` type | Principle II (no silent "last wins"); FR-007, FR-010 | Plain argparse keeps the last `--users`. `int()` accepts `+80`, `8_000` and non-ASCII digits (R10). |
| `clock` / `sleep` parameters on `make_server` (test support only, not exposed by the CLI) | Tests for FR-026, FR-027 (same second), FR-030 (900 s boundary) and FR-020 (same-second sign-in again) | Real sleeping for 900 or 1800 s, or hoping the timing lands on a second boundary, is impossible in an automated suite or makes it flaky. |
