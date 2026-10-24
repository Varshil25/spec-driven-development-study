---

description: "Task list for the Secure Login Web Application"
---

# Tasks: Secure Login Web Application

**Input**: Design documents from `specs/001-secure-login-app/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/cli.md](contracts/cli.md), [contracts/http.md](contracts/http.md), [quickstart.md](quickstart.md)

**Tests**: MANDATORY. The constitution (v1.0.0, Principle III and the Tasks gate) requires at least one pytest test task for every FR, and every test name must cite its FR ID. In each phase, write the test tasks first and check that they fail before you start the implementation tasks that follow them.

**Organization**: Tasks are grouped by user story, so that each story can be built and tested as its own increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: The task can run in parallel with other [P] tasks in the same phase, because it touches a different file and does not depend on an unfinished task.
- **[Story]**: The user story the task belongs to (US1–US5, from spec.md).
- Every task names the exact file it creates or changes. Indented bullets under a task give the details it needs.

## Path Conventions

- Single project (plan.md, "Project Structure"): `pyproject.toml`, `src/loginapp/` and `tests/` sit at the repository root.
- Do not touch `tools/` or `logs/`. They belong to the study tooling.
- Run all tests with `python3 -m pytest` from the repository root.

## Rules that apply to every task

- **Runtime code**:
  - Imports only the modules listed in [research R12](research.md#r12-python-311-compatibility-rules): `argparse`, `base64`, `hashlib`, `hmac`, `html`, `http.server`, `json`, `os`, `re`, `secrets`, `sys`, `tempfile`, `threading`, `time`, `traceback`, `urllib.parse`. It never imports pytest.
  - Uses only the Python 3.11 subset defined in R12. That rules out PEP 695 syntax, f-strings that reuse the outer quote character or contain a backslash inside `{}`, and 3.12+ APIs.
- **Principle II**:
  - Functions raise `ValueError`, `AccountsFileError`, `InvalidToken` or `SignInRefused`. They never return `None` or another sentinel in place of an answer.
  - Exceptions are never swallowed. The only documented exceptions are the FR-031 dispatcher, `handle_error`, and `sign_out` ignoring an invalid session (FR-019).
- **Messages**: every stderr message uses the exact wording in [contracts/cli.md](contracts/cli.md). Values the user supplied are `repr()`-quoted. No password, hash, salt, token or secret is ever written (FR-029).
- **Tests**:
  - Every test function is named `test_frNNN_…` and has a docstring that cites `FR-NNN`, for example `"""FR-003: ..."""`. The docstring is required because the quickstart.md §1 coverage grep looks for `FR-0NN`, which `test_fr0NN_` does not match.
  - Every socket and subprocess read has a timeout, so no test can hang.
  - Tests use the real scrypt settings. Do not add a fast-hash switch.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the project skeleton and the pytest configuration.

- [X] T001 Create the directories `src/loginapp/` and `tests/` at the repository root, as in plan.md "Source Code". Do not add `models/` or `services/` layers.
- [X] T002 Create `pyproject.toml` at the repository root holding only a `[tool.pytest.ini_options]` table with `pythonpath = ["src"]` and `testpaths = ["tests"]`. It has no `[project]` table and no dependencies.
  - Check: `python3 -m pytest` collects from `tests/` only. Exit status 5 ("no tests ran") is expected at this point.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The package entry point, the top-level command parser, the shared subprocess test helper and the FR-032 guards. Every story depends on these.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Create `tests/conftest.py` with the shared command-line helpers:
  - `REPO_ROOT`: the parent of `tests/`. `SRC_DIR`: `REPO_ROOT / "src"`.
  - `run_cli(*args, stdin=b"", env=None, cwd=None, timeout=30)`:
    - runs `[sys.executable, "-m", "loginapp", *args]`;
    - builds the environment by copying `os.environ`, removing `LOGINAPP_SECRET`, setting `PYTHONPATH=str(SRC_DIR)`, then applying `env` (a value of `None` removes that key);
    - passes `stdin` as bytes and captures both output streams;
    - returns an object with `returncode`, and with `stdout` and `stderr` decoded as UTF-8 with `errors="replace"`.
  - `assert_no_traceback(text)`: asserts that `"Traceback"` does not appear in `text`.
- [X] T004 [P] Write the FR-032 guard tests in `tests/test_robustness.py`. They must fail now, because the package does not exist yet.
  - `test_fr032_runs_as_module_with_src_on_path`:
    - Call `run_cli()` with no arguments.
    - Expect exit 2, empty stdout, and `usage:` on stderr. Check `assert_no_traceback(stderr)`.
  - `test_fr032_runtime_imports_stdlib_only`:
    - Assert that `src/loginapp/__init__.py`, `__main__.py` and `cli.py` exist.
    - Parse every `src/loginapp/*.py` with `ast`. Collect the top-level module name of every `Import` and `ImportFrom`, including imports inside functions. Relative imports are allowed.
    - Assert that each name is in `sys.stdlib_module_names` or is `loginapp`, and that `pytest` is never imported.
  - `test_fr032_python311_syntax`: every `src/loginapp/*.py` parses with `ast.parse(source, feature_version=(3, 11))`.
- [X] T005 Create `src/loginapp/__init__.py`, holding only a package docstring, and `src/loginapp/__main__.py`, holding exactly `from loginapp.cli import main` and `raise SystemExit(main())`. As a result, importing `loginapp.cli` in a test runs nothing.
- [X] T006 Implement the top-level command parser in `src/loginapp/cli.py` (contracts/cli.md "Global usage", FR-007):
  - Entry point: `main(argv=None) -> int`.
  - Parser: `argparse.ArgumentParser(prog="python -m loginapp", usage="%(prog)s COMMAND ...", allow_abbrev=False, add_help=False)`, with `add_subparsers(dest="command", metavar="COMMAND", required=True)`.
    - No command, or an unknown command, therefore writes argparse usage to stderr and exits with status 2.
    - There is no `-h`/`--help`.
  - `StoreOnce(argparse.Action)`: calls `parser.error(f"argument {option_string}: may be given only once")` when the option already has a value. Every option added in US1 and US2 uses it. It is listed in plan.md Complexity Tracking.
  - `fail(message, status) -> int`: writes exactly one line, `loginapp: error: {message}`, to stderr and returns `status`.
  - Usage errors leave through argparse's own `SystemExit(2)`.

**Checkpoint**: `python3 -m pytest tests/test_robustness.py` passes, and `PYTHONPATH=src python3 -m loginapp` exits with status 2 and a usage message.

---

## Phase 3: User Story 1 - Operator creates an account (Priority: P1) — MVP part 1

**Goal**: `python -m loginapp adduser USERNAME --users FILE` validates the username and the password from stdin, stores a salted scrypt record in an owner-only JSON accounts file that is written atomically, and reports every failure with the documented message and exit status.

**Independent Test**: Run the account command against a fresh accounts file. Check the output, the exit status and the file contents. No server is needed.

### Tests for User Story 1 (write first; they must fail)

- [X] T007 [P] [US1] Write the account-record tests in `tests/test_accounts.py`:
  - `test_fr005_record_has_pinned_scrypt_settings`:
    - `accounts.make_record("correct-horse-battery")` has exactly the keys `{"algorithm", "n", "r", "p", "salt", "hash"}`.
    - The values are `algorithm == "scrypt"`, `n == 131072`, `r == 8` and `p == 1`. `salt` matches `[0-9a-f]{32}` and `hash` matches `[0-9a-f]{64}` (full match).
    - The module constants are `SCRYPT_N == 2**17`, `SCRYPT_R == 8`, `SCRYPT_P == 1`, `DKLEN == 32` and `SALT_BYTES == 16`.
  - `test_fr005_hash_matches_hashlib_scrypt`:
    - `hashlib.scrypt(pw.encode("utf-8"), salt=bytes.fromhex(rec["salt"]), n=131072, r=8, p=1, dklen=32, maxmem=268435456).hex() == rec["hash"]`.
    - `accounts.verify(pw, rec)` is `True`, and is `False` for a different password.
  - `test_fr005_same_password_different_records`: two records made for the same password differ in both `salt` and `hash`.
  - `test_fr005_password_absent_from_file`:
    - Run `run_cli("adduser", "alice", "--users", "users.json", stdin=b"correct-horse-battery\n", cwd=tmp_path)`.
    - The file's bytes contain none of: the password, its UTF-8 hex, its standard base64, its URL-safe base64.
  - `test_fr006_save_sets_mode_0600_and_leaves_no_temp_file`:
    - `accounts.save(path, {...})` creates `path` with `stat.S_IMODE(mode) == 0o600`.
    - It leaves no file matching `.<name>.*.tmp` in the folder.
- [X] T008 [P] [US1] Write the FR-001 tests in `tests/test_adduser.py`. All of them use `run_cli` with `cwd=tmp_path`.
  - `test_fr001_adds_account_and_prints_added`:
    - stdin `b"correct-horse-battery\n"` gives stdout exactly `"added alice\n"`, empty stderr and exit 0.
    - `accounts.load(path, missing_ok=False)["alice"]` verifies `"correct-horse-battery"`.
    - Adding `bob` afterwards prints `"added bob\n"`, and the file then holds both accounts.
  - `test_fr001_creates_missing_file`: FILE does not exist beforehand and does afterwards.
  - `test_fr001_password_line_handling`, parametrised over (stdin bytes → stored password):
    - `b"correct-horse-battery\n"` → `"correct-horse-battery"`
    - `b"correct-horse-battery\r\n"` → `"correct-horse-battery"`
    - `b"correct-horse-battery"` (no final line ending) → `"correct-horse-battery"`
    - `b"  inner spaces kept  \n"` → `"  inner spaces kept  "`
    - `b"first-line-password\nsecond-line\n"` → `"first-line-password"`
    - `b"correct-horse-battery\r"` (a lone `\r` stays, R10) → `"correct-horse-battery\r"`
    - In each case, check with `accounts.verify` that the expected password matches and the unstripped variant does not.
- [X] T009 [US1] Add the FR-002 tests to `tests/test_adduser.py`:
  - `test_fr002_rejects_bad_usernames`, parametrised over `"al"`, `"a" * 33`, `"al-ice"`, `"josé"`, `"a b"` and `""`.
    - Expect exit 2.
    - stderr contains `repr(name)` and `must be 3 to 32 characters, each an ASCII letter, digit or underscore`.
    - stdout is empty and `assert_no_traceback(stderr)` holds.
    - FILE is not created. With an existing FILE, its bytes are unchanged.
  - `test_fr002_accepts_boundaries`, parametrised over `"abc"`, `"a" * 32` and `"A_9"`: exit 0 and `added NAME`.
- [X] T010 [US1] Add the FR-003 tests to `tests/test_adduser.py`:
  - `test_fr003_rejects_bad_passwords`, parametrised over stdin:
    - `b"short-pass1\n"` (11 characters)
    - `b""` (empty stdin)
    - `b"\xff\xfe-not-utf8-bytes\n"`
    - `("é" * 11 + "\n").encode()` (11 multi-byte characters)
    - Expect exit 2.
    - stderr contains `invalid password: must be at least 12 characters of UTF-8 text` and does not contain the input text.
    - stdout is empty, there is no traceback, and FILE is unchanged or not created.
  - `test_fr003_counts_characters_not_bytes`: `"é" * 12` and `"a" * 12` are both accepted, with exit 0.
- [X] T011 [US1] Add the FR-004 tests to `tests/test_adduser.py`:
  - `test_fr004_duplicate_exits_3`: adding `alice` a second time gives exit 3, stderr containing `username 'alice' already exists`, empty stdout, and FILE bytes unchanged.
  - `test_fr004_usernames_case_sensitive`: `alice` and then `Alice` both succeed.
  - `test_fr004_check_order`, parametrised. Each case asserts the exit status and which message appears.
    - existing `alice` + an 11-character password → 2, password message;
    - `al-ice` + an 11-character password → 2, username message;
    - new `carol` + an 11-character password + FILE that is a directory → 2;
    - valid `carol` + FILE that is a directory → 1.
- [X] T012 [US1] Add the FR-006 tests to `tests/test_adduser.py`:
  - `test_fr006_file_mode_0600`: a new FILE gets mode `0o600`. A FILE that was `chmod 0o644` beforehand is `0o600` after a successful `adduser`.
  - `test_fr006_existing_accounts_kept_byte_for_byte`: after adding `bob`, the `alice` record is unchanged, both as parsed JSON and as its serialised text block.
  - `test_fr006_failed_write_leaves_file_intact`, run in-process:
    - Monkeypatch `os.replace` to raise `OSError(errno.EIO, "Input/output error")`.
    - Monkeypatch `sys.stdin` with an object whose `.buffer` is `io.BytesIO(b"correct-horse-battery\n")`.
    - `cli.main(["adduser", "bob", "--users", str(path)])` returns 1.
    - stderr (captured with capsys) contains `cannot write accounts file` and `repr(str(path))`.
    - FILE's bytes and mode are unchanged, and no `.users.json.*.tmp` file is left behind.
- [X] T013 [US1] Add the FR-007 tests to `tests/test_adduser.py`:
  - `test_fr007_usage_errors_exit_2`, parametrised over these argument lists:
    - `[]`
    - `["nope"]`
    - `["adduser"]`
    - `["adduser", "alice"]`
    - `["adduser", "alice", "--users", "u.json", "extra"]`
    - `["adduser", "alice", "--users", "a", "--users", "b"]`
    - `["addu", "alice", "--users", "u.json"]`
    - `["adduser", "alice", "--use", "u.json"]`
    - `["-h"]`
    - Expect exit 2, `usage:` on stderr, empty stdout, no traceback and no file created.
  - `test_fr007_equivalent_forms_accepted`: `--users=u.json` and `--users u.json alice` (option before the positional) both succeed.
  - `test_fr007_unreadable_file_exits_1`: FILE is a directory. Expect exit 1, and stderr contains `cannot read accounts file` and `repr(path)`.
  - `test_fr007_invalid_file_exits_1`, parametrised over FILE contents:
    - an empty file;
    - `not json`;
    - a duplicate key, `{"accounts":{},"accounts":{}}`;
    - a valid record with `"n": 131071`;
    - a 30-hex-character salt;
    - an extra field;
    - an `"al-ice"` username key;
    - `"p": true`.
    - Expect exit 1. stderr contains `invalid accounts file` and `repr(path)`, and does not contain the record's salt or hash hex. FILE's bytes are unchanged.
  - `test_fr007_unwritable_location_exits_1`, parametrised over `tmp/no/such/dir/u.json` and `tmp/regular-file/u.json`: exit 1, stderr names FILE, and nothing is created.

### Implementation for User Story 1

- [X] T014 [US1] Implement the username and password rules in `src/loginapp/accounts.py`:
  - `USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,32}")`, always used with `fullmatch`. data-model: "`^[A-Za-z0-9_]{3,32}$` (ASCII only, whole string)". `fullmatch` means a trailing newline is not accepted.
  - `MIN_PASSWORD_CHARS = 12`.
  - `check_username(name) -> None` raises `ValueError(f"invalid username {name!r}: must be 3 to 32 characters, each an ASCII letter, digit or underscore")`.
  - `check_password(text) -> None` raises `ValueError("invalid password: must be at least 12 characters of UTF-8 text")` when `len(text) < 12`. Length is counted in characters, not bytes.
- [X] T015 [US1] Implement password hashing in `src/loginapp/accounts.py`:
  - **Constants**: `SCRYPT_N = 2**17`, `SCRYPT_R = 8`, `SCRYPT_P = 1`, `DKLEN = 32`, `SALT_BYTES = 16`, `SCRYPT_MAXMEM = 268435456`. data-model: "268435456 (256 MiB) (a limit, not stored)".
  - **`make_record(password) -> dict`**:
    - salt from `secrets.token_bytes(16)`;
    - hash from `hashlib.scrypt(password.encode("utf-8"), salt=salt, n=131072, r=8, p=1, dklen=32, maxmem=268435456)`;
    - returns exactly `{"algorithm": "scrypt", "n": 131072, "r": 8, "p": 1, "salt": salt.hex(), "hash": digest.hex()}`.
    - data-model: "No other fields are allowed"; "The password is hashed exactly as typed, as its UTF-8 bytes, with no Unicode normalisation".
  - **`verify(password, record) -> bool`**: recomputes the hash with the record's salt and settings, and compares it with `hmac.compare_digest`.
- [X] T016 [US1] Implement `AccountsFileError(Exception)` and `load(path, missing_ok) -> dict[str, dict]` in `src/loginapp/accounts.py` (data-model "Validity rules"):
  - **Reading**:
    - Read the file as bytes.
    - A `FileNotFoundError` with `missing_ok=True` returns `{}`.
    - Any other `OSError` raises `AccountsFileError(f"cannot read accounts file {path!r}: {e.strerror}")`.
  - **Validation**: enforce these rules verbatim. Any failure raises `AccountsFileError(f"invalid accounts file {path!r}: {rule}")`.
    - "1. It is UTF-8 text that parses as JSON. An empty file is invalid."
    - "2. No JSON object anywhere in it has a duplicate key." Use an `object_pairs_hook`.
    - "3. The top level is an object with exactly one key, `accounts`, whose value is an object. It may be empty."
    - "4. Every key of `accounts` matches the username pattern."
    - "5. Every value is an object with exactly the fields in the Account table, each meeting its rule."
    - "The integers must be real JSON integers. `true` and `131072.0` are invalid." Check with `type(v) is int`.
  - **Account field rules (verbatim)**:
    - `algorithm`: "Exactly `"scrypt"`"
    - `n`: "Exactly `131072`"
    - `r`: "Exactly `8`"
    - `p`: "Exactly `1`"
    - `salt`: "Exactly 32 lowercase hex characters (16 bytes)"
    - `hash`: "Exactly 64 lowercase hex characters (32 bytes)"
  - **Rule text** names the rule that failed and never a field's value, for example `account 'bob': field 'salt' must be 32 lowercase hex characters`.
- [X] T017 [US1] Implement `save(path, accounts) -> None` in `src/loginapp/accounts.py`, following data-model "Writing" steps 1–4:
  1. Serialise with `json.dumps({"accounts": accounts}, indent=2, sort_keys=True) + "\n"`.
  2. Create the temporary file with `tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix="." + os.path.basename(path) + ".", suffix=".tmp")`. It has mode `0600` from the start.
  3. Write, flush and `os.fsync`, then `os.replace(temp, path)`.
  4. On any error, remove the temporary file if it was created, then re-raise the `OSError`.
  - As a result, FILE ends with mode `0600` and readers see either the complete old file or the complete new one (FR-006).
- [X] T018 [US1] Implement the `adduser` subcommand in `src/loginapp/cli.py`, following contracts/cli.md "Order of checks" 1–6:
  - **Arguments**: a subparser `adduser` (`add_help=False`, `allow_abbrev=False`) with the positional `USERNAME` and a required `--users FILE` (StoreOnce). This is check 1.
  - **Check 2, username**: `accounts.check_username`. On failure, `fail(str(e), 2)` without reading stdin.
  - **Check 3, password**:
    - Read with `sys.stdin.buffer.readline()`.
    - Remove one trailing `b"\r\n"` or `b"\n"`. A lone `\r` stays part of the password.
    - Decode as UTF-8 with `errors="strict"`. A `UnicodeDecodeError` gives the same password message with exit 2.
    - Call `accounts.check_password`.
  - **Check 4, read FILE**: `accounts.load(FILE, missing_ok=True)`. On `AccountsFileError`, `fail(str(e), 1)`.
  - **Check 5, duplicate**: if the username is already present, `fail(f"username {name!r} already exists", 3)`.
  - **Check 6, write FILE**: `accounts[name] = accounts.make_record(pw)`, then `accounts.save`. On `OSError`, `fail(f"cannot write accounts file {path!r}: {e.strerror or type(e).__name__}", 1)`.
  - **Success**: `print(f"added {name}")`, nothing on stderr, return 0.
  - The password is never echoed or included in any message.

**Checkpoint**: `python3 -m pytest tests/test_accounts.py tests/test_adduser.py tests/test_robustness.py` passes. quickstart.md §2 behaves as documented.

---

## Phase 4: User Story 2 - Account holder signs in and sees the dashboard (Priority: P1) — MVP part 2

**Goal**: `python -m loginapp serve` runs a `ThreadingHTTPServer` on 127.0.0.1 that offers:

- the login page;
- form sign-in, with identical failures for an unknown username and a wrong password;
- an HS256 JWT session cookie;
- the dashboard greeting;
- protective headers, exact routing and a generic 500 on any response.

**Independent Test**: Create an account with the account command and start the server. Submit the login form with correct and with incorrect credentials. Follow the redirect to the dashboard with the session cookie.

### Test infrastructure for User Story 2

- [X] T019 [US2] Extend `tests/conftest.py` with the server test helpers:
  - `free_port()`: binds `("127.0.0.1", 0)`, reads the port and closes the socket.
  - **Accounts fixtures**:
    - Session-scoped `accounts_template`: built once with `accounts.make_record` and `accounts.save`, holding `alice` (`correct-horse-battery`) and `bob` (`another-long-pass`).
    - Function-scoped `users_file(tmp_path)`: copies the template into `tmp_path / "users.json"`.
  - **`FakeClock`** (thread-safe, using an internal `threading.Lock`):
    - `time()` returns the fake time, starting at the whole second `1_800_000_000.0`;
    - `advance(seconds)` moves the fake time forward;
    - `sleep(seconds)` moves the fake time forward by `max(seconds, 0)` and never really sleeps.
  - **`inproc_server` fixture**: a factory `start(users_path, secret=[REDACTED:assigned_secret], clock=None, sleep=None)`.
    - It calls `server.make_server(0, str(users_path), secret, clock=clock or time.time, sleep=sleep or time.sleep)`.
    - It runs `serve_forever` in a daemon thread and returns the server. The port is `srv.server_address[1]`.
    - Teardown calls `shutdown()` and then `server_close()`.
  - **`http(port, method, path, headers=(), body=b"", raw=None, timeout=10)`**: a raw-socket client.
    - It sends `raw` bytes exactly when given. Otherwise it builds an HTTP/1.0 request and adds `Content-Length` only when the caller passes it in `headers` or passes a non-empty body.
    - It reads until EOF.
    - It returns `.status` (int), `.headers` (a list of `(name, value)` pairs that keeps duplicates), `.header(name)` (the single value, or `None`), `.headers_named(name)` (all values) and `.body` (bytes).
  - **`post_login(port, username, password, extra=(), content_type="application/x-www-form-urlencoded")`**: sends a form-encoded body.
  - **`session_token(resp)`**: extracts the value after `session=` and before the first `;` in the response's single `Set-Cookie` header.
  - **`ServerProcess(port, users_path, secret)`**: a context manager.
    - It starts `python -m loginapp serve --port PORT --users FILE` with `PYTHONPATH` and `LOGINAPP_SECRET` set.
    - It waits up to 10 s for `listening on 127.0.0.1:PORT\n` on stdout, using a reader thread.
    - It stops the process with SIGINT in `finally`: it waits up to 10 s, then kills as a fallback.
    - Afterwards it exposes `returncode`, `stdout_text` and `stderr_text`.

### Tests for User Story 2 (write first; they must fail)

- [X] T020 [P] [US2] Write the token unit tests in `tests/test_tokens.py`.
  - **FR-024**:
    - `test_fr024_token_format`: `tokens.encode("alice", 1_800_000_000, b"k")` has these properties:
      - it has 3 segments and no `=`;
      - the decoded header is exactly `b'{"alg":"HS256","typ":"JWT"}'`;
      - the decoded payload is exactly `b'{"sub":"alice","iat":1800000000,"exp":1800001800}'`;
      - `exp == iat + 1800`.
    - `test_fr024_independent_verifier_accepts`: the test's own `hmac.new(b"k", (s1 + "." + s2).encode("ascii"), hashlib.sha256).digest()` equals the base64url-decoded third segment.
  - **FR-023**:
    - `test_fr023_accepts_valid_token`: `decode(encode("alice", 1000, b"k"), b"k", now=1000)` returns `{"sub": "alice", "iat": 1000, "exp": 2800}`.
    - `test_fr023_rejects_malformed`: each case raises `InvalidToken`. Build the cases with a helper that signs arbitrary header and payload bytes. Parametrise over:
      - 2 segments, and 4 segments;
      - an empty segment;
      - a non-ASCII character;
      - `=` padding added to a segment;
      - a non-canonical last character (one that decodes to the same bytes);
      - `+` or `/` in a segment;
      - a header that is not JSON;
      - a duplicate header key;
      - a missing `alg`;
      - `alg` set to `none`, both with an empty and with a valid signature;
      - `alg` set to `HS512`;
      - a non-string `alg`, such as `["HS256"]`;
      - a signature with one byte flipped;
      - a token signed with another secret;
      - a payload that is a JSON array;
      - `sub` as the number `123`;
      - `iat` as the float `1000.0`;
      - `exp` as `true`;
      - each claim missing in turn;
      - a duplicate claim.
    - `test_fr023_expiry_boundary`: `now = exp - 1` and `now = exp - 0.5` are accepted; `now = exp` and `now = exp + 1` raise `InvalidToken`.
- [X] T021 [P] [US2] Write the server-startup tests in `tests/test_serve.py`.
  - **FR-008**:
    - `test_fr008_ready_line_unbuffered`: `ServerProcess` reads exactly `listening on 127.0.0.1:{port}\n` within 10 s while `proc.poll() is None`.
    - `test_fr008_accepts_connections_after_ready_line`: `GET /login` gets 200 straight after the ready line.
    - `test_fr008_loopback_only`:
      - in-process, `srv.socket.getsockname()[0] == "127.0.0.1"`;
      - with a subprocess, connecting to `("127.0.0.2", port)` raises `ConnectionRefusedError`.
  - **FR-009**: `test_fr009_missing_or_empty_secret`, parametrised over unset and `""`.
    - Expect exit 1, `LOGINAPP_SECRET` in stderr, and no `listening on` in stdout.
    - There is no traceback, and the process ends within 30 s.
  - **FR-010**:
    - `test_fr010_bad_port_exits_2`, parametrised over `0`, `65536`, `abc`, `-1`, `+80`, `" 80"`, `8_000` and the full-width digits `"８０００"`.
      - Expect exit 2. stderr contains `repr(value)` and `1 to 65535`. There is no `listening on`.
    - `test_fr010_port_in_use_exits_1`: hold a listening socket on `127.0.0.1:port`. Expect exit 1, and `cannot listen on 127.0.0.1:{port}` in stderr.
    - `test_fr010_bad_accounts_file_exits_1`, parametrised over a missing FILE, a directory and invalid JSON. Expect exit 1 and FILE named in stderr.
    - `test_fr010_check_order`, parametrised:
      - bad port + no secret → 2;
      - no secret + missing FILE → 1, with the `LOGINAPP_SECRET` message and no file message;
      - missing FILE + busy port → 1, with the file message and no port message.
- [X] T022 [P] [US2] Write the login-page and successful sign-in tests in `tests/test_login.py`, using the in-process server.
  - **FR-013**: `test_fr013_login_form`.
    - `GET /login` gets 200. Parse the page with `html.parser.HTMLParser`.
    - The page has exactly one form, with method `post` (case-insensitive) and action `/login`.
    - It has an `input` with `name=username` and `type=text`, an `input` with `name=password` and `type=password`, and a submit `button`.
    - The page does not contain `Invalid username or password`, and the response has no `Set-Cookie`.
    - Sending a `Cookie: session=x` header still gets 200, with no redirect.
  - **FR-014**:
    - `test_fr014_correct_credentials_redirect_with_cookie`: the response is 303 with `Location: /dashboard`, one `Set-Cookie` starting with `session=`, and `Content-Length: 0`.
    - `test_fr014_extra_fields_ignored`: adding `&remember=1` still gets 303.
    - `test_fr014_content_type_parameters_allowed`, parametrised over `application/x-www-form-urlencoded; charset=UTF-8` and `APPLICATION/X-WWW-FORM-URLENCODED`: 303.
    - `test_fr014_percent_encoded_and_raw_utf8`:
      - Add `carol` with the password `pässwörd-ünïcode-1` to the copied file, using `accounts.load`, `make_record` and `save`.
      - Posting the raw UTF-8 body gets 303, and so does posting the percent-encoded body.
- [X] T023 [US2] Add the FR-015 tests to `tests/test_login.py`:
  - `test_fr015_unknown_user_and_wrong_password_identical`:
    - Compare `alice` with a wrong password against `nobody` with any password.
    - Both get 401, with byte-identical bodies and headers identical apart from `Date`, and no `Set-Cookie`.
    - The body contains `Invalid username or password` and the login form.
  - `test_fr015_malformed_submissions_get_401`, parametrised over:
    - a missing `username`, and a missing `password`;
    - an empty `username`, and an empty `password`;
    - a repeated `username`, and a repeated `password`;
    - `Content-Length: 0`;
    - no `Content-Length` header;
    - no `Content-Type`;
    - `Content-Type: text/plain`, and `multipart/form-data`;
    - two `Content-Type` headers;
    - a raw `\xff` byte in the body;
    - `%FF` in a field.
    - Each case gets 401 with a body byte-identical to the wrong-password body, and no `Set-Cookie`.
  - `test_fr015_page_does_not_echo_input`: the username `zz_echo_user_zz` and the password `zz-echo-pass-zz` are both absent from the 401 body.
  - `test_fr015_oversized_body_413_without_reading`:
    - Send only the headers, with `Content-Length: 65537` and then `Content-Length: 100000000`, and no body.
    - Each gets 413 within the timeout, with `Content-Type: text/html; charset=utf-8`.
    - A real 65 536-byte body is read and gets 401, not 413.
  - `test_fr015_invalid_content_length_400`, parametrised over `abc`, `-1`, `1e3` and two `Content-Length` headers: 400.
  - `test_fr015_truncated_body_400`: send `Content-Length: 50` with 10 bytes, then `shutdown(SHUT_WR)`. Expect 400.
- [X] T024 [US2] Add the FR-011 and FR-016 tests to `tests/test_login.py`:
  - `test_fr011_account_added_while_running_can_sign_in`: with `ServerProcess` running, `run_cli("adduser", "carol", …)` on the same FILE, then `post_login` for `carol` gets 303.
  - `test_fr011_broken_file_at_sign_in_gives_500`:
    - With `ServerProcess` running, overwrite FILE with `{`.
    - A well-formed `alice` sign-in gets 500, with no `Set-Cookie` and the generic page.
    - Restore the original bytes. The sign-in then gets 303.
    - After the stop, `stderr_text` names FILE and contains no password.
  - `test_fr016_unknown_user_and_wrong_password_timing`:
    - In-process: 7 attempts for each case (`nobody`, and `alice` with a wrong password).
    - `max(medians) / min(medians) <= 2`.
- [X] T025 [P] [US2] Write the dashboard and cookie tests in `tests/test_sessions.py`, using the in-process server.
  - **FR-017**:
    - `test_fr017_dashboard_welcome_and_logout_form`:
      - Sign in as `alice`, then `GET /dashboard` with `Cookie: session=<token>`.
      - Expect 200 and `Welcome, alice`.
      - The page has a form with method `post` and action `/logout`, holding a submit button. The response has no `Set-Cookie`.
    - `test_fr017_username_is_escaped` (unit test): `server.dashboard_page('<b>&"x')` contains `Welcome, &lt;b&gt;&amp;&quot;x` and does not contain `<b>`.
  - **FR-024**: `test_fr024_issued_cookie_token_verifies`, run with a `FakeClock`.
    - The cookie token verifies with the test's own HMAC-SHA256 under `b"test-secret"`.
    - Its claims are `sub == "alice"`, `iat == int(clock.time())` read straight after the response, and `exp == iat + 1800`.
  - **FR-025**: `test_fr025_cookie_attributes`.
    - There is exactly one `Set-Cookie` header. Its value is `session=<jwt>`, followed by the attributes `HttpOnly`, `SameSite=Strict`, `Path=/` and `Max-Age=1800`.
- [X] T026 [P] [US2] Write the routing and header tests in `tests/test_routing.py`, using the in-process server.
  - **Shared table**: `RESPONSE_CASES`, a parametrised list of (name, request, expected status):
    - 200 `GET /login`;
    - 401 for a wrong password;
    - 303 `GET /dashboard` with no cookie;
    - 404 `GET /nope`;
    - 405 `POST /dashboard`;
    - 400 for `Content-Length: abc`;
    - 413 for `Content-Length: 100000000`, headers only;
    - 500 for a well-formed sign-in after FILE is overwritten with `{`;
    - 501 `PUT /login`;
    - 400 for the raw request `b"GARBAGE\r\n\r\n"`;
    - 400 for the HTTP/0.9 request `b"GET /login\r\n\r\n"`.
  - **FR-012**: `test_fr012_every_body_is_html_utf8`, over `RESPONSE_CASES`. Every response with a non-empty body has exactly one `Content-Type: text/html; charset=utf-8`, and its body starts with `<!doctype html>` (case-insensitive).
  - **FR-028**: `test_fr028_protective_headers_everywhere`, over `RESPONSE_CASES`. Each response carries each of `Cache-Control: no-store`, `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff` exactly once.
  - **FR-021**:
    - `test_fr021_unknown_paths_404`: the paths `/`, `/dashboard/`, `/login.html`, `//login`, `/LOGIN` and `/logout/x`, each with GET and POST, get 404 with an HTML body.
    - `test_fr021_query_string_ignored`: `GET /login?x=1` gets 200 and the login form.
  - **FR-022**:
    - `test_fr022_wrong_method_405_with_allow`: `POST /dashboard` gets 405 with `Allow: GET`. The `GET /logout` case is added in T048.
    - `test_fr022_other_methods_error`: `PUT`, `DELETE` and `PATCH`, each on `/login`, `/dashboard`, `/logout` and `/nope`, get a status of 400 or more.
- [X] T027 [P] [US2] Add the FR-031 and FR-029 internal-error tests to `tests/test_robustness.py`. Both run in-process, with stderr captured through `capfd`.
  - **FR-031**: `test_fr031_unexpected_error_generic_500_and_continues`.
    - Monkeypatch `server.dashboard_page` to raise `RuntimeError("detail-xyz")`. Sign in, then `GET /dashboard`.
    - The response is 500. Its body contains `Internal server error` and contains none of `detail-xyz`, `Traceback` or `/dashboard`.
    - stderr contains `loginapp: internal error while handling GET /dashboard: RuntimeError` and does not contain `detail-xyz`.
    - The next `GET /login` gets 200.
  - **FR-029**: `test_fr029_internal_error_report_has_no_request_data`.
    - Use the same setup, but request `/dashboard?pw=secret-in-query` with the session cookie.
    - stderr contains none of: the token, `secret-in-query`, or the server secret.

### Implementation for User Story 2

- [X] T028 [P] [US2] Implement the token encoder in `src/loginapp/tokens.py`:
  - `InvalidToken(ValueError)`.
  - `SESSION_SECONDS = 1800`.
  - `b64url_encode(data) -> str`: URL-safe base64 with the `=` padding removed.
  - `encode(sub, iat, key: bytes) -> str`, following data-model "Session token":
    - `header` is the exact bytes `{"alg":"HS256","typ":"JWT"}`.
    - `payload` is `json.dumps({"sub": sub, "iat": iat, "exp": iat + 1800}, separators=(",", ":")).encode("utf-8")`.
    - The signature is `hmac.new(key, (seg1 + "." + seg2).encode("ascii"), hashlib.sha256).digest()`.
  - Claims (data-model, verbatim):
    - `sub` (string): "The username that signed in";
    - `iat` (integer): "`int(clock())` at issue: whole seconds since the Unix epoch, rounded down";
    - `exp` (integer): "`iat + 1800`".
- [X] T029 [US2] Implement `decode(token, key: bytes, now: float) -> dict` in `src/loginapp/tokens.py`. It follows data-model "Acceptance (FR-023)" steps 1–6, in order, and any failure raises `InvalidToken`:
  1. "The token is ASCII with exactly two `.` characters, which gives three segments."
  2. "Every segment is non-empty, uses only `A–Z a–z 0–9 - _`, and is **canonical**: decoding it and encoding it again (without padding) gives the same text."
     - Implementation: `re.fullmatch(r"[A-Za-z0-9_-]+", seg)` and `b64url_encode(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))) == seg`.
     - Convert a `binascii.Error` into `InvalidToken`.
  3. "The header decodes to a JSON object with no duplicate keys, and its `alg` is the string `"HS256"`." Check it with `type(alg) is str and alg == "HS256"`.
  4. `hmac.compare_digest(signature, HMAC-SHA256(key, seg1 + "." + seg2))`. This runs before the payload is parsed.
  5. "The payload is a JSON object with no duplicate keys. `sub` is a `str`; `iat` and `exp` are `int` and not `bool`." Check with `type(x) is int`.
  6. "`now < exp`. There is no clock tolerance."
  - Return the claims dict.
- [X] T030 [P] [US2] Add equal-cost hashing and the concurrency cap to `src/loginapp/accounts.py`:
  - `dummy_verify(password) -> None`: does the same scrypt work as `verify`, against a fixed module-level 16-byte dummy salt and a fixed dummy hash, with the same settings and `hmac.compare_digest` (FR-016). It is used for unknown usernames.
  - A module-level `threading.BoundedSemaphore(4)` wraps every `hashlib.scrypt` call, in `make_record`, `verify` and `dummy_verify`. data-model: "at most 4 (process-wide semaphore)". See plan.md Complexity Tracking.
- [X] T031 [P] [US2] Implement the page functions in `src/loginapp/server.py`. Each returns UTF-8 `bytes` holding a complete `<!doctype html>` document with `<meta charset="utf-8">`.
  - `login_page(error: bool)`:
    - contains the form from contracts/http.md "GET /login" exactly;
    - with `error=True`, adds `<p class="error" role="alert">Invalid username or password</p>` before the form and changes nothing else.
  - `dashboard_page(username)`: `<h1>Welcome, {html.escape(username, quote=True)}</h1>`, followed by `<form method="post" action="/logout"><button type="submit">Sign out</button></form>`.
  - `simple_page(title)`: `<h1>{title}</h1>`. It is used for `Not found`, `Method not allowed`, `Bad request`, `Content too large` and `Internal server error`, and never includes any detail.
- [X] T032 [US2] Implement the sign-in and session core in `src/loginapp/server.py`.
  - **Exception**: `SignInRefused(Exception)`, which carries no detail.
  - **`parse_session_cookie(cookie_header) -> str`**: follows contracts/http.md "Session lookup" 1–3.
    - Split on `;`, then split each pair on its first `=` and strip spaces.
    - Raise `InvalidToken` unless exactly one pair is named `session` and its value is non-empty.
    - Do not use `http.cookies` (R8).
  - **`LoginServer(http.server.ThreadingHTTPServer)`**:
    - `issue_token(username) -> str`: `iat = int(self.clock())`, then `return tokens.encode(username, iat, self.key)`. US3 adds the registry and the wait rule. US5 adds the signed-out check.
    - `session_user(cookie_header) -> str`: returns `tokens.decode(parse_session_cookie(cookie_header), self.key, self.clock())["sub"]`, and raises `InvalidToken` when there is no valid session.
    - `attempt(username, password) -> str`:
      - Call `accounts.load(self.users_path, missing_ok=False)` and let `AccountsFileError` propagate.
      - Hash exactly once: `accounts.verify` for a known username, `accounts.dummy_verify` for an unknown one.
      - On failure, raise `SignInRefused`. Otherwise return `self.issue_token(username)`.
    - `handle_error(request, client_address)`: writes one stderr line, `loginapp: error: connection failed: {ExcType.__name__}`, and no traceback (R9).
  - **`make_server(port, users_path, secret: str, clock=time.time, sleep=time.sleep) -> LoginServer`**:
    - binds `("127.0.0.1", port)`. The constructor binds and listens.
    - stores `users_path`, `key = secret.encode("utf-8")`, `clock` and `sleep`. `sleep` is first used in T041.
- [X] T033 [US2] Implement the request handler framework in `src/loginapp/server.py`: `Handler(http.server.BaseHTTPRequestHandler)`.
  - **Class settings**: `error_content_type = "text/html; charset=utf-8"`. `protocol_version` stays `HTTP/1.0`.
  - **`end_headers` override**: sends `Cache-Control: no-store`, `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff`, then calls the parent. As a result, http.server's own 400, 414, 431, 501 and 505 responses carry these headers too (FR-028).
  - **`log_message` override**: does nothing (FR-029).
  - **`parse_request` override**: when the parent returns `True` but `self.request_version == "HTTP/0.9"` (a two-word request line such as `GET /login`), set `self.request_version = "HTTP/1.0"`, call `send_error(400)` and return `False` (R8).
  - **Routing**:
    - The path is `self.requestline.split()[1]` cut at the first `?`. Do not use `self.path`, which folds `//`.
    - `do_GET` and `do_POST` call `dispatch(method)`, which uses a route table of `{path: {method: route_fn}}`.
    - An unknown path gets 404 with `simple_page("Not found")`.
    - A known path with an unsupported method gets 405 with `Allow` (`GET, POST` for `/login`, `GET` for `/dashboard`) and `simple_page("Method not allowed")`.
  - **Responses**: route functions return `(status, headers, body)`. `send()` writes the status, the headers, `Content-Type: text/html; charset=utf-8` only when the body is non-empty, and `Content-Length: len(body)`, then the body.
  - **FR-031**: `dispatch` wraps the route in `try/except Exception`.
    - On an exception, it writes `loginapp: internal error while handling {METHOD} {PATH}: {type(e).__name__}` plus `"".join(traceback.format_tb(e.__traceback__))` to stderr. It never writes the exception message.
    - It then sends 500 with `simple_page("Internal server error")`.
- [X] T034 [US2] Implement the `GET /login` and `GET /dashboard` routes in `src/loginapp/server.py`:
  - **`GET /login`**: 200 with `login_page(False)`. Cookies are ignored and there is no `Set-Cookie`.
  - **`GET /dashboard`**:
    - Call `self.server.session_user("; ".join(self.headers.get_all("Cookie") or []))`.
    - On success: 200 with `dashboard_page(sub)` and no `Set-Cookie` (FR-026).
    - On `InvalidToken`: 303 with `Location: /login` and an empty body.
- [X] T035 [US2] Implement the `POST /login` route in `src/loginapp/server.py`, following the contracts/http.md table rows 1–7, in order:
  - **Row 1**: more than one `Content-Length` header, or a value that is not `re.fullmatch(r"[0-9]+", v.strip())`, gets 400 with `simple_page("Bad request")`.
  - **Row 2**: a value over 65536 gets 413 with `simple_page("Content too large")`, without reading the body. data-model: "65536 bytes".
  - **Row 3**: read exactly N bytes with `self.rfile.read(N)`. If fewer arrive, respond 400. No `Content-Length` header means an empty body.
  - **Row 4**: a malformed submission raises `SignInRefused`, without reading FILE. It is malformed when:
    - there is not exactly one `Content-Type` header;
    - the media type, `split(";")[0].strip().lower()`, is not `application/x-www-form-urlencoded`;
    - the body does not decode as UTF-8 (`errors="strict"`);
    - `urllib.parse.parse_qsl(text, keep_blank_values=True, encoding="utf-8", errors="strict")` raises;
    - there is not exactly one non-empty `username` and exactly one non-empty `password`.
  - **Rows 5–7**: call `self.server.attempt(username, password)`.
    - `AccountsFileError`: write `loginapp: error: {e}` to stderr and send 500 with `simple_page("Internal server error")`.
    - `SignInRefused`: 401 with `login_page(True)`.
    - Success: 303 with `Location: /dashboard`, `Set-Cookie: session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=1800` and an empty body.
- [X] T036 [US2] Implement the `serve` subcommand in `src/loginapp/cli.py`, following contracts/cli.md "Order of startup checks" 1–4. It uses `server.make_server` from T032, so it comes after T032.
  - **Arguments**: a subparser `serve` (`add_help=False`, `allow_abbrev=False`) with a required `--port` (StoreOnce, `type=port_type`) and a required `--users` (StoreOnce).
  - **`port_type(text)`**:
    - accepts only `re.fullmatch(r"[0-9]{1,5}", text)` with a value from 1 to 65535. Use `[0-9]`, not `\d`, so non-ASCII digits are refused.
    - otherwise raises `argparse.ArgumentTypeError(f"invalid port {text!r}: must be a whole number from 1 to 65535")`.
  - **Check 2, secret**: read `LOGINAPP_SECRET`.
    - Unset or empty: `fail("LOGINAPP_SECRET is not set or is empty", 1)`.
    - `secret.encode("utf-8")` raises `UnicodeEncodeError`: `fail("LOGINAPP_SECRET is not valid UTF-8 text", 1)`.
    - data-model: "It must be non-empty and encodable as UTF-8."
  - **Check 3, FILE**: `accounts.load(FILE, missing_ok=False)`. On `AccountsFileError`, `fail(str(e), 1)`.
  - **Check 4, listen**: `server.make_server(port, FILE, secret)`. On `OSError`, `fail(f"cannot listen on 127.0.0.1:{port}: {e.strerror}", 1)`.
  - **Running**:
    - `print(f"listening on 127.0.0.1:{port}", flush=True)`, then `serve_forever()`.
    - On `KeyboardInterrupt`: call `server_close()`, write `loginapp: stopped` to stderr and return 130.
  - The secret is never printed.

**Checkpoint**: `python3 -m pytest` passes for every test written so far. quickstart.md §3 and the first half of §4 (login page, sign-in, dashboard, no-cookie and tampered requests) behave as documented. **US1 + US2 together are the MVP.**

---

## Phase 5: User Story 3 - The dashboard stays private (Priority: P2)

**Goal**: Only a session this server run issued, and that has not expired, opens the dashboard.

- A token from an earlier run is refused, even within the same second (FR-027).
- A session is never extended (FR-026).
- Every missing, malformed, tampered, wrongly signed or expired cookie gets 303 to `/login` (FR-018).

**Independent Test**: Request the dashboard with no cookie, with a tampered token, with a token signed with another secret, with a token that uses a different signing algorithm, with an expired token, and with a token from before a server restart. Every request must be redirected to the login page.

### Tests for User Story 3 (write first; the FR-027 cases and the "never issued" case must fail)

- [X] T037 [P] [US3] Add `test_fr018_no_valid_session_redirects` to `tests/test_sessions.py`, using the in-process server with a `FakeClock`.
  - Parametrise over:
    - no `Cookie` header;
    - `session=`;
    - two `session` pairs;
    - `session=a.b`;
    - random text;
    - a valid token with `sub` changed to `bob` (payload re-encoded, signature kept);
    - a token signed with `b"other-secret"`;
    - an `alg: none` token;
    - an `alg: HS512` token;
    - an expired token (sign in, then `clock.advance(1800)`);
    - a correctly signed, unexpired token made directly with `tokens.encode("alice", int(clock.time()), b"test-secret")` that this server never issued.
  - Each case gets 303 with `Location: /login`, an empty body, no `Welcome` and no `Set-Cookie`.
- [X] T038 [US3] Add the FR-026 and FR-027 in-process tests to `tests/test_sessions.py`, using a `FakeClock`.
  - **FR-026**:
    - `test_fr026_dashboard_sets_no_cookie`: `GET /dashboard` with a valid session gets 200 and no `Set-Cookie`.
    - `test_fr026_fixed_lifetime_despite_use`: use the dashboard several times. At `iat + 1799` it gets 200; at `iat + 1800` it gets 303.
  - **FR-027**:
    - `test_fr027_same_second_restart`:
      - Server A signs in `alice` and keeps the token. Call the token's `iat` S. Stop A.
      - Without advancing the clock, start server B on the same `FakeClock`, so B's `run_start` is also S.
      - A's token on B gets 303.
      - B's `alice` sign-in succeeds with a different token whose `iat > S`.
      - A's token still gets 303 on B.
    - `test_fr027_current_run_tokens_accepted_until_expiry`: a token issued by this run is accepted at `iat + 1799`.
- [X] T039 [P] [US3] Add `test_fr027_restart_refuses_earlier_tokens` to `tests/test_serve.py`:
  - Using `ServerProcess`, sign in `alice` and keep the token.
  - Stop the server, then start it again on the same port with the same secret.
  - The kept token gets 303 with `Location: /login`, and a fresh sign-in followed by the dashboard gets 200.

### Implementation for User Story 3

- [X] T040 [US3] Add the state lock and the issued-token registry to `LoginServer` in `src/loginapp/server.py`:
  - **State**: `self.lock = threading.Lock()` and `self.issued: dict[str, int] = {}`. data-model: "mapping a token string to its `exp`… guarded by the server's state lock".
  - **`issue_token`**: records `issued[token] = iat + 1800` under the lock before returning. data-model: "Added: when a sign-in succeeds, before the 303 response is written".
  - **`session_user`**: after `tokens.decode`, check under the lock that the exact token string is in `issued` (acceptance step 7). If it is not, raise `InvalidToken`.
- [X] T041 [US3] Implement the same-second rule in `src/loginapp/server.py` (data-model "Issuing a token", R4):
  - **`make_server`**: sets `srv.run_start = int(clock())` immediately after the constructor binds the port. This is before the CLI prints `listening on`.
  - **`issue_token` loop**:
    - Under the lock: `iat = int(self.clock())`, then `token=[REDACTED:assigned_secret](...)`.
    - If `iat > self.run_start`: record the token and return it.
    - Otherwise, release the lock, call `self.sleep(iat + 1 - self.clock())`, and retry. The wait is at most 1 s.
- [X] T042 [US3] Add the expiry sweep to `src/loginapp/server.py`: at each sign-in, inside the critical section of `issue_token`, delete every `issued` entry whose `exp <= now`. data-model: "Removed… when it has expired, by a sweep at each sign-in and sign-out". T049 extends the sweep to `signed_out` and to sign-out.

**Checkpoint**: `python3 -m pytest tests/test_sessions.py tests/test_serve.py tests/test_tokens.py` passes, and so do the US1 and US2 tests. quickstart.md §6 behaves as documented.

---

## Phase 6: User Story 4 - Repeated wrong passwords lock the username (Priority: P2)

**Goal**: After 5 failed sign-ins in a row for an existing username, every sign-in for it is refused for 900 s, even with the right password. The refusal is identical to any other failure in status, headers, body and timing.

**Independent Test**: Create an account and submit 5 wrong passwords for it. Then submit the right password, before the 15 minutes are up and after. Compare the locked response with an ordinary failure.

### Tests for User Story 4 (write first; they must fail)

- [X] T043 [US4] Write the lock-transition tests in `tests/test_lockout.py`, using the in-process server with a `FakeClock`:
  - `test_fr030_five_failures_lock`: 5 wrong passwords for `alice` each get the standard 401. A 6th attempt, with the correct password, also gets 401 with no `Set-Cookie`.
  - `test_fr030_lock_ends_at_900_seconds`: the correct password is refused at the fifth failure's time `+ 899` and accepted (303) at `+ 900`.
  - `test_fr030_success_resets_count`: 4 wrong, then correct (303), then 4 wrong, then correct (303).
  - `test_fr030_locked_attempts_not_counted_or_extending`:
    - While locked, attempts at `+ 1` and `+ 899`, with wrong and with correct passwords, are refused.
    - The correct password at `+ 900` gets 303.
    - After the lock ends, 4 wrong attempts followed by the correct password give 303.
  - `test_fr030_lock_is_per_username`: while `alice` is locked, `bob`'s correct password gets 303.
  - `test_fr030_unknown_case_variant_and_malformed_not_counted`:
    - Send 5 attempts each for `nobody` and `ALICE`, and 5 malformed `alice` submissions (an empty password, and a repeated `password` field).
    - `alice`'s correct password then gets 303.
- [X] T044 [US4] Add the remaining FR-030 tests and the FR-016 timing test to `tests/test_lockout.py`:
  - `test_fr030_existing_session_survives_lock`: sign in `alice` and keep the token. After 5 wrong passwords, `GET /dashboard` with the token still gets 200.
  - `test_fr030_concurrent_failures_lock`:
    - 10 threads send wrong passwords for `alice` at the same moment, released by a `threading.Barrier`.
    - After all 10 responses (all 401), a correct-password attempt gets 401.
  - `test_fr030_new_server_has_no_locks`: lock `alice` on server A and stop it. A new server on the same FILE accepts her correct password (303).
  - `test_fr030_locked_response_identical`: the locked `alice` response, a wrong password for unlocked `bob`, and `nobody` all have identical status, identical headers apart from `Date`, and identical body.
  - `test_fr016_failure_timing_within_factor_2`:
    - Use real scrypt and real time: 7 attempts each for an unknown username, a wrong password, and the locked username.
    - For every pair of cases, the ratio of medians is at most 2.

### Implementation for User Story 4

- [X] T045 [US4] Implement the sign-in lock in `LoginServer.attempt` in `src/loginapp/server.py` (data-model "Sign-in lock state", R7):
  - **Constants**: `MAX_FAILURES = 5` and `LOCK_SECONDS = 900`. data-model: "5 in a row"; "900 seconds".
  - **State**, guarded by `self.lock` from T040:
    - `self.failures: dict[str, int]`. data-model: "username → failed attempts in a row. A missing key means 0."
    - `self.locked_at: dict[str, float]`. data-model: "username → `clock()` at the fifth failure."
    - data-model: "Keys are added only for usernames that exist in the accounts file at the time of the attempt."
  - **Hashing**: still happens outside the lock, exactly once, and also for a locked username.
  - **Transitions**: then, under `self.lock`, with `t = self.clock()`, apply the data-model transitions verbatim:
    - UNLOCKED(count):
      - wrong password with `count < 4`: `count += 1`;
      - correct password=[REDACTED:assigned_secret](0), and a token is issued;
      - wrong password with `count == 4`: LOCKED(`locked_at = t`), `count = 0`.
    - LOCKED(s):
      - `t - s < 900`: refused with the standard 401. Nothing is counted and `s` is unchanged.
      - `t - s >= 900`: the lock is cleared, `count = 0`, and the attempt is handled as UNLOCKED(0).
    - "An attempt for a username that has no account is refused and changes no state."
    - "One critical section covers the lock check, the comparison of the password result and the update."
  - **After the critical section**: call `issue_token` outside it on success. Otherwise raise `SignInRefused`.
  - `session_user` never consults the lock state, so existing sessions stay valid.

**Checkpoint**: `python3 -m pytest tests/test_lockout.py` passes, and so does every earlier test. quickstart.md §5 behaves as documented.

---

## Phase 7: User Story 5 - Account holder signs out (Priority: P3)

**Goal**: `POST /logout` always clears the cookie and redirects to `/login`. It also refuses the presented valid token from then on, including kept copies, re-encoded copies and same-second re-issues. Other sessions are not affected.

**Independent Test**: Sign in and keep a copy of the token. Submit `POST /logout` with it and check the response. Then send the copy to the dashboard, both before and after restarting the server, and check that it is refused.

### Tests for User Story 5 (write first; they must fail)

- [X] T046 [P] [US5] Add the FR-019 and FR-020 tests to `tests/test_sessions.py`, using the in-process server with a `FakeClock`. Also add the `signed out` case to the T037 `test_fr018_no_valid_session_redirects` parameters.
  - **FR-019**: `test_fr019_logout_clears_cookie`, parametrised over a valid session, no cookie, an invalid token, and an expired token.
    - Each gets 303 with `Location: /login` and `Content-Length: 0`.
    - There is one `Set-Cookie`, with an empty `session` value and the attributes `Max-Age=0` and `Path=/`.
  - **FR-020**:
    - `test_fr020_signed_out_copy_refused`: sign in, keep the token, then `POST /logout` with it. The copy then gets 303 at `GET /dashboard`.
    - `test_fr020_reencoded_copy_refused`: after sign-out, both re-encoded copies get 303.
      - The first copy is `token + "="`.
      - The second copy replaces the token's last character with a different character that decodes to the same bytes. Find it by comparing `urlsafe_b64decode` results.
    - `test_fr020_other_sessions_unaffected`: sign in twice, 1 fake second apart, to get two different tokens. Sign out the first; the second still gets 200.
    - `test_fr020_same_second_sign_in_after_logout_gets_new_token`:
      - Sign in, sign out and sign in again within the same fake second.
      - The new token differs from the old one and gets 200. The old token gets 303.
- [X] T047 [P] [US5] Add `test_fr020_signed_out_token_refused_after_restart` to `tests/test_serve.py`. Using `ServerProcess`, sign in and sign out, then restart on the same port with the same secret. The kept token gets 303.
- [X] T048 [P] [US5] Extend `tests/test_routing.py`:
  - Add `GET /logout` → 405 with `Allow: POST` to `test_fr022_wrong_method_405_with_allow`.
  - Add the rows "303 `POST /logout`" and "405 `GET /logout`" to `RESPONSE_CASES`, so FR-012 and FR-028 cover them.

### Implementation for User Story 5

- [X] T049 [US5] Implement server-side sign-out in `LoginServer` in `src/loginapp/server.py` (data-model "Signed-out map", R5):
  - **State**: `self.signed_out: dict[str, int] = {}`, mapping token to `exp`, guarded by the same lock.
  - **`sign_out(cookie_header) -> None`**:
    - Parse the cookie and call `tokens.decode` at `now = self.clock()`.
    - If there is no valid candidate, return without changing anything (FR-019).
    - Otherwise, under the lock, if the token is in `issued`, move it: `self.signed_out[token] = self.issued.pop(token)`. This happens before the response is written.
  - **`session_user`**: also refuses any token in `signed_out` (acceptance step 8).
  - **`issue_token` loop**: the condition becomes `iat > self.run_start and token not in self.signed_out`.
  - **Sweep**: it now also removes `signed_out` entries whose `exp <= now`, and it runs at each sign-out as well as each sign-in.
- [X] T050 [US5] Add the `/logout` route to the route table in `src/loginapp/server.py`:
  - **`POST /logout`**:
    - Never read the body.
    - Call `self.server.sign_out("; ".join(self.headers.get_all("Cookie") or []))`.
    - Respond 303 with `Location: /login`, `Set-Cookie: session=; Max-Age=0; Path=/` and an empty body.
  - **`GET /logout`**: 405 with `Allow: POST`.

**Checkpoint**: `python3 -m pytest` passes in full. The second half of quickstart.md §4 (sign-out, then the kept copy) behaves as documented.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: The end-to-end secrecy check, the Python 3.11 check and the constitution's Done gate.

- [X] T051 Add `test_fr029_no_secrets_in_output` to `tests/test_robustness.py`. It runs a full subprocess flow:
  - **Flow**:
    - `run_cli adduser` for `alice` and `bob`.
    - Start `ServerProcess` with the secret `s3cr3t-value-for-fr029`.
    - `GET /login`, then a good sign-in, keeping the token, then a bad sign-in.
    - 5 wrong passwords for `bob`, then his correct password, which is refused.
    - The dashboard, then sign-out.
    - FILE overwritten with `{`, then a sign-in that gets 500. Restore FILE.
    - Stop with SIGINT.
  - **Checks**:
    - The exit status is 130, stderr ends with `loginapp: stopped`, and there is no traceback.
    - Collect every stdout and stderr text from the flow. None of them contains any password, the secret, any issued token or its signature segment, or any salt or hash hex from FILE.
- [X] T052 Add `test_fr032_python311_smoke` to `tests/test_robustness.py`:
  - Skip it only when `shutil.which("python3.11")` is `None`.
  - Under `python3.11`, with `PYTHONPATH=src`, run `adduser`, `serve` and one sign-in (303), then `GET /dashboard` (200).
- [X] T053 Review `src/loginapp/*.py` against R12, Principle II and Principle IV, and fix what you find:
  - **R12**:
    - no PEP 695 syntax;
    - no f-string that reuses its outer quote or has a backslash inside `{}`;
    - no 3.12+ APIs;
    - only the R12 modules are imported.
  - **Principle II**:
    - no function returns a sentinel in place of an answer;
    - no bare `except:` and no `except …: pass`, apart from the documented cases: the FR-031 dispatcher, `handle_error`, and `sign_out` on an invalid session.
  - **Principle IV**: no unused code, imports or options beyond plan.md and its Complexity Tracking table.
- [X] T054 Run the SC-009 coverage check from quickstart.md §1 at the repository root: `for n in $(seq -w 1 32); do grep -rqE "FR-0$n\b" tests/ || echo "FR-0$n has no test"; done`. It must print nothing. If it prints anything, add the missing `FR-0NN` docstring (see "Rules that apply to every task").
- [X] T055 Run `python3 -m pytest` from the repository root. It uses `pyproject.toml` and collects `tests/`. Confirm all of the following:
  - every test passes;
  - nothing is xfailed;
  - nothing is skipped, except `test_fr032_python311_smoke` when `python3.11` is absent;
  - the run takes about 2–3 minutes (plan.md "Test-suite notes").
- [X] T056 Walk through quickstart.md §2–§7 by hand with `curl` against `PYTHONPATH=src python3 -m loginapp`. Fix any difference from the documented output in `src/loginapp/`, then rerun T055.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup. It blocks every user story.
- **US1 (Phase 3)**: depends on Foundational.
- **US2 (Phase 4)**: depends on US1:
  - the test fixtures and `attempt` use `accounts.load`, `make_record`, `verify` and `save`;
  - the FR-011 test uses `adduser`.
- **US3 (Phase 5)**: depends on US2, which creates sessions.
- **US4 (Phase 6)**: depends on US2 (sign-in) and on T040 in US3, which creates the state lock. No other dependency on US3.
- **US5 (Phase 7)**: depends on US2, and on US3's T040 (the issued registry) and T041 (the wait loop, which T049 extends).
- **Polish (Phase 8)**: depends on every story. T051 exercises lockout and sign-out.

### User Story Dependency Graph

```text
Setup ─▶ Foundational ─▶ US1 (P1) ─▶ US2 (P1) ─▶ US3 (P2) ─┬─▶ US4 (P2) ─┐
                                                           └─▶ US5 (P3) ─┴─▶ Polish
```

US4 and US5 can proceed in parallel once US3 is done. Both edit `LoginServer` in `src/loginapp/server.py`: US4 changes `attempt`, and US5 changes `issue_token`, `session_user`, `sign_out` and the route table. Merge them with care.

### Within Each User Story

- Test infrastructure, then tests. Confirm the tests fail.
- Then `accounts.py` and `tokens.py`, then `server.py`, then `cli.py`.
- Tasks that touch the same file run in ID order.
- Finish each story at its checkpoint before starting the next priority.

### Parallel Opportunities

- **Phase 2**: T003 ∥ T004.
- **US1 tests**: T007 (`test_accounts.py`) ∥ T008 (`test_adduser.py`). T009–T013 then follow T008 in the same file.
- **US2 tests**: T020 ∥ T021 ∥ T022 ∥ T025 ∥ T026 ∥ T027, all in different files, once T019 is done. T023 and T024 follow T022.
- **US2 implementation**: T028 ∥ T030 ∥ T031. Then T029 after T028, and T032 → T033 → T034 → T035 after T031. T036 (`cli.py`) can run alongside T033–T035 once T032 is done.
- **US3 tests**: T037 ∥ T039. T038 follows T037.
- **US5 tests**: T046 ∥ T047 ∥ T048.
- **Across stories**: US4 ∥ US5 after US3.

---

## Parallel Example: User Story 1

```bash
# Tests, in different files:
Task: "T007 Write FR-005/FR-006 account-record tests in tests/test_accounts.py"
Task: "T008 Write FR-001 tests in tests/test_adduser.py"   # then T009–T013 in the same file
```

## Parallel Example: User Story 2

```bash
# After T019 (conftest helpers), the tests in different files:
Task: "T020 Token unit tests (FR-023, FR-024) in tests/test_tokens.py"
Task: "T021 Startup tests (FR-008–FR-010) in tests/test_serve.py"
Task: "T022 Login page and sign-in tests (FR-013, FR-014) in tests/test_login.py"
Task: "T025 Dashboard and cookie tests (FR-017, FR-024, FR-025) in tests/test_sessions.py"
Task: "T026 Routing and header tests (FR-012, FR-021, FR-022, FR-028) in tests/test_routing.py"
Task: "T027 Internal-error tests (FR-031, FR-029) in tests/test_robustness.py"

# Implementation, in different files:
Task: "T028 tokens.encode in src/loginapp/tokens.py"
Task: "T030 dummy_verify and the hashing semaphore in src/loginapp/accounts.py"
Task: "T031 Page functions in src/loginapp/server.py"

# After T032 (make_server exists), cli.py and server.py in parallel:
Task: "T036 serve subcommand in src/loginapp/cli.py"
Task: "T033 Handler framework in src/loginapp/server.py"   # then T034, T035
```

## Parallel Example: User Story 3

```bash
Task: "T037 FR-018 redirect matrix in tests/test_sessions.py"
Task: "T039 FR-027 subprocess restart test in tests/test_serve.py"
```

## Parallel Example: User Story 4

```bash
# One test file, so T043 → T044 run in order. Implementation is a single task (T045).
# US4 as a whole can run alongside US5 once US3 is done.
```

## Parallel Example: User Story 5

```bash
Task: "T046 FR-019/FR-020 tests in tests/test_sessions.py"
Task: "T047 FR-020 restart test in tests/test_serve.py"
Task: "T048 /logout routing rows in tests/test_routing.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 and 2)

The spec says US1 and US2 together are the minimum viable product.

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (US1). **Validate**: quickstart.md §2. Accounts can now be created.
3. Complete Phase 4 (US2). **Validate**: quickstart.md §3 and §4, up to the dashboard. The MVP can be demonstrated at this point.

### Incremental Delivery

1. Add US3: earlier-run tokens are refused, and the redirect matrix is proven. Validate with quickstart.md §6.
2. Add US4: the lockout. Validate with quickstart.md §5.
3. Add US5: server-side sign-out. Validate with the second half of quickstart.md §4.
4. Each story ends at a checkpoint where the whole suite passes, so no story breaks an earlier one.
5. Polish (T051–T056) closes the constitution's Done gate.

### Parallel Team Strategy

1. The team completes Setup, Foundational, US1 and US2 together. These are on the critical path.
2. Developer A takes US3. When T040 lands, Developer B starts US4 (`attempt`).
3. When T041 lands, Developer C starts US5 (sign-out, `/logout`).
4. Everyone joins for Polish.

---

## FR → Task Traceability (Tasks gate: every FR has at least one test task)

| FR | Test task(s) | Implementation task(s) |
|----|--------------|------------------------|
| FR-001 | T008 | T018 |
| FR-002 | T009 | T014, T018 |
| FR-003 | T010 | T014, T018 |
| FR-004 | T011 | T018 |
| FR-005 | T007 | T015 |
| FR-006 | T007, T012 | T017, T018 |
| FR-007 | T013 | T006, T016, T018 |
| FR-008 | T021 | T032, T036 |
| FR-009 | T021 | T036 |
| FR-010 | T021 | T036 |
| FR-011 | T024 | T032, T035 |
| FR-012 | T026, T048 | T031, T033 |
| FR-013 | T022 | T031, T034 |
| FR-014 | T022 | T032, T035 |
| FR-015 | T023 | T035 |
| FR-016 | T024, T044 | T030, T032, T045 |
| FR-017 | T025 | T031, T034 |
| FR-018 | T037, T046 | T032, T034, T040, T049 |
| FR-019 | T046 | T049, T050 |
| FR-020 | T046, T047 | T049 |
| FR-021 | T026 | T033 |
| FR-022 | T026, T048 | T033, T050 |
| FR-023 | T020 | T029 |
| FR-024 | T020, T025 | T028, T032 |
| FR-025 | T025 | T035 |
| FR-026 | T038 | T034 |
| FR-027 | T038, T039 | T040, T041 |
| FR-028 | T026, T048 | T033 |
| FR-029 | T027, T051 | T033, T036 (and every message task) |
| FR-030 | T043, T044 | T045 |
| FR-031 | T027 | T033 |
| FR-032 | T004, T052 | T005, T006 |

---

## Notes

- [P] tasks touch different files and have no dependency on an unfinished task.
- The [Story] label ties each task to its user story for traceability.
- **Naming**:
  - Every test function name starts with `test_frNNN_`.
  - Every test also has a docstring citing `FR-NNN`, so the quickstart.md §1 grep (which looks for `FR-0NN`) finds it.
- Run each story's new tests and see them fail before writing the implementation.
- Commit after each task or logical group, and stop at any checkpoint to validate the story on its own.
- **Open review points**: the plan.md "Open review points" (R1 scrypt values, R2 concurrent `adduser`, R7, R8, R10 and R13) are built exactly as planned. If the product owner changes one, update the named research section and the matching tasks together.
