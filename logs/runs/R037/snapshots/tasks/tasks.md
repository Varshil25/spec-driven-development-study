---

description: "Task list for Pastebin Service implementation"
---

# Tasks: Pastebin Service

**Input**: Design documents from `/specs/001-pastebin-service/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/http-api.md](./contracts/http-api.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: **REQUIRED**, not optional. SC-002 demands that every requirement FR-001…FR-032 be covered by at least one automated test that names it, and Constitution III ("Every Requirement Is Testable") is marked NON-NEGOTIABLE. Test tasks therefore appear in every phase and precede the implementation they cover.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and delivered as an independent increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project (per plan.md Structure Decision): `src/pastebin/` for runtime code, `tests/` for the suite, both at repository root (`/root/sdd-study/runs/R037`). Four runtime modules — `cli.py`, `storage.py`, `server.py`, `__main__.py` — with no internal sub-packages.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton and test runner configuration. No behaviour yet.

- [ ] T001 Create the directory skeleton `src/pastebin/` and `tests/` at the repository root per plan.md Project Structure
- [ ] T002 Create `pyproject.toml` at the repository root with `requires-python = ">=3.11"`, **no runtime dependencies** (Constitution I), `[project.optional-dependencies] dev = ["pytest"]` declared separately from runtime (Constitution Additional Constraints), and `[tool.pytest.ini_options]` setting `pythonpath = ["src"]` and `testpaths = ["tests"]` (R-014)
- [ ] T003 [P] Create `src/pastebin/__init__.py` containing only `__version__ = "1.0.0"` — package marker, no logic and no re-exports (Constitution IV)
- [ ] T004 [P] Create `tests/README.md` with the traceability table scaffold: one row per requirement FR-001…FR-032 with columns `Requirement | Covering test(s)`, to be filled in as tests land (Constitution III, SC-002)
- [ ] T005 [P] Create `.gitignore` at the repository root ignoring `__pycache__/`, `*.pyc`, and `.pytest_cache/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The storage primitives, the HTTP response/routing chokepoint, a minimal runnable CLI, and the two pytest fixtures. Every user story needs all of this before any of its own routes exist.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Storage primitives (`src/pastebin/storage.py` — sequential, one file)

- [ ] T006 Create `src/pastebin/storage.py` with module constants: `RECORD_VERSION = 1`, `CONTENT_MAX_BYTES = 65536` (inclusive — exactly 65,536 bytes is accepted, FR-005), `EXPIRES_IN_MIN = 1`, `EXPIRES_IN_MAX = 2_592_000` (both inclusive, FR-006), and `ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")` (V-10, FR-023); stdlib imports only
- [ ] T007 Add the frozen `Paste` dataclass to `src/pastebin/storage.py` with exactly these required fields and no behaviour: `id: str` (opaque URL-safe, 22 chars from `[A-Za-z0-9_-]`), `content: str` (≤ 65,536 bytes when UTF-8 encoded; `""` is valid), `created_at: int` (epoch seconds UTC, whole seconds), `expires_at: int | None` (`None` means never expires), `delete_token: str` (43-char URL-safe secret, write-only — never serialised into a read response) per data-model.md §1
- [ ] T008 Add `is_valid_id(candidate)` and `record_path(data_dir, paste_id)` to `src/pastebin/storage.py`: `is_valid_id` returns the result of the `ID_RE` allow-list (`^[A-Za-z0-9_-]{1,64}$`) and the id is **refused, never rewritten or sanitised** (Constitution II forbids coercing questionable input); `record_path` raises if the id is invalid and otherwise returns `os.path.join(data_dir, paste_id + ".json")` (FR-023, R-007, invariant S-1)
- [ ] T009 Add `new_id()` returning `secrets.token_urlsafe(16)` (128 bits, 22 chars) and `new_delete_token()` returning `secrets.token_urlsafe(32)` (256 bits, 43 chars) to `src/pastebin/storage.py`, drawn from independent `secrets` calls so neither yields the other (FR-002, FR-003, R-004)
- [ ] T010 Add `iso_z(ts)` to `src/pastebin/storage.py` rendering an epoch-second int as `datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")` — explicit `strftime`, never `isoformat()` which emits `+00:00` — and returning `None` for a `None` input so the wire value becomes JSON `null` (FR-010, R-009)
- [ ] T011 Add `_write_record(path, record)` to `src/pastebin/storage.py`: `json.dump` into a uniquely named `.tmp-<random>` file **in the same directory** as `path`, `flush`, `os.fsync`, then `os.replace` onto `path`; remove the temp file if any step fails, so a partially written record is never readable (FR-028, invariant S-2, R-006)
- [ ] T012 Add `create_paste(data_dir, content, expires_at=None)` to `src/pastebin/storage.py`: draw an id with `new_id()`, reserve `<id>.json` with `os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)` and redraw on `FileExistsError` so an id is never reused across any run against the directory, then publish the record `{"version": 1, "id", "content", "created_at", "expires_at", "delete_token"}` via `_write_record`, and return the `Paste` (FR-002, FR-028, invariant S-3, R-006, Story 4 scenario 7)
- [ ] T013 Add `load_paste(data_dir, paste_id)` to `src/pastebin/storage.py` returning `Paste | None`: `None` without any filesystem access when the id fails the allow-list; `None` on `FileNotFoundError`; and `None` plus a `skipping unreadable record: <path>: <reason>` line on **stderr** when the file fails to parse, its `version` is not `RECORD_VERSION`, or its `id` field disagrees with the filename stem (FR-023, FR-032, invariant S-4, R-012)
- [ ] T014 Add `delete_record(data_dir, paste_id)` to `src/pastebin/storage.py`: `os.remove` the record path, returning `True` on success and `False` on `FileNotFoundError` (never a bare `except`) (FR-016, invariant S-4)
- [ ] T015 Add `scan_directory(data_dir)` to `src/pastebin/storage.py`: one pass over the directory that reports each unreadable or unrecognised entry on stderr with the same `skipping unreadable record:` wording and **builds no index or cache** (FR-032, R-008, R-012, invariant S-8)

### HTTP chokepoint (`src/pastebin/server.py` — sequential, one file)

- [ ] T016 Create `src/pastebin/server.py` with `class PasteHandler(BaseHTTPRequestHandler)`: `protocol_version = "HTTP/1.1"`, a `server_version` string, and `log_message` overridden to write request logs to **stderr only** so stdout carries nothing but the readiness line (R-001, FR-030)
- [ ] T017 Add `PAYLOAD_MAX_BYTES = 1_048_576` and the single response chokepoint to `src/pastebin/server.py`: `_send_json(status, obj)` (UTF-8 JSON, `Content-Type: application/json`, explicit `Content-Length`), `_send_error(status, message)` emitting a body of exactly `{"error": "<message>"}` with a message specific enough to act on, `_send_text(content)` (`text/plain; charset=utf-8`), and `_send_no_content()` (`204`, no body, no `Content-Type`); also override `error_message_format` and `error_content_type` so errors the base class raises on its own still produce the JSON shape, and never call `send_error` from route logic (FR-022, FR-013, R-010)
- [ ] T018 Add route dispatch to `src/pastebin/server.py`: split off the query string with `urllib.parse.urlsplit` (query ignored for routing), percent-decode the path with `unquote`, and match only `POST /pastes`, `GET /pastes/<id>`, `GET /pastes/<id>/raw`, `DELETE /pastes/<id>`; every other path or method — `/`, `/pastes` on GET, `DELETE /pastes`, `PUT`/`PATCH`/`POST /pastes/<id>`, `/pastes/<id>/`, `/pastes//raw`, `/pastes/<id>/raw/extra`, any other sub-resource, and `HEAD`/`OPTIONS`/any other verb — answers `404` with a JSON error body; `405` is deliberately never used (FR-020, contracts/http-api.md catch-all table)
- [ ] T019 Add per-request failure containment to `src/pastebin/server.py`: wrap each dispatch so an unexpected exception prints a `traceback` to stderr and answers `500` with the same `{"error": ...}` shape while the server keeps accepting requests — no bare `except:` and no `except Exception: pass`, the exception is converted into a *reported* error (R-011, SC-008, Constitution II)
- [ ] T020 Add `make_server(port, data_dir)` to `src/pastebin/server.py` returning a `ThreadingHTTPServer` bound to `("127.0.0.1", port)` — loopback only — with `data_dir` attached to the server instance for handlers to read; construction performs `bind()` and `listen()`, so the accept queue is live on return (FR-025, R-001, R-002)

### Minimal runnable entry point

- [ ] T021 Create `src/pastebin/cli.py` with `main(argv) -> int`: an `argparse` parser with a `serve` subcommand and required `--port` / `--data`, `os.makedirs(data, exist_ok=True)`, `make_server(port, data)`, then `print(f"listening on 127.0.0.1:{port}")` with an explicit `flush=True` **after** the server is listening and **before** `serve_forever()`, returning `0` on clean shutdown (FR-025, FR-026, FR-027, R-002, R-013). Failure-path hardening (port/dir validation, diagnostics, exit codes) is Phase 6 — this task delivers the happy path only
- [ ] T022 Create `src/pastebin/__main__.py` containing only the entry call `sys.exit(cli.main(sys.argv[1:]))` under an `if __name__ == "__main__":` guard, so `PYTHONPATH=src python -m pastebin` works (FR-025, contracts/cli.md)

### Test fixtures and shared-behaviour tests

- [ ] T023 Create `tests/conftest.py` with the in-process server fixture: `make_server(0, tmp_path)` started in a daemon thread, exposing the kernel-assigned port and the `tmp_path` data directory, shut down and joined on teardown (R-014 fixture 1)
- [ ] T024 Extend `tests/conftest.py` with a free-port helper and the subprocess server fixture: launch `python -m pastebin serve --port <free> --data <tmp_path>` via `subprocess.Popen` with `PYTHONPATH=src` and piped stdout/stderr, block until the `listening on 127.0.0.1:<port>` line is read from **stdout**, and terminate plus collect both streams on teardown (R-014 fixture 2, FR-027)
- [ ] T025 Add an HTTP client helper to `tests/conftest.py` built on `http.client` — `request(port, method, path, body=None, headers=None)` returning status, headers, and the **raw body bytes** — so tests can assert byte-for-byte content rather than a decoded string (FR-012, R-014)
- [ ] T026 Create `tests/test_routing.py` covering the full catch-all table from contracts/http-api.md (`GET /`, `GET /pastes`, `DELETE /pastes`, `PUT`/`PATCH`/`POST /pastes/<id>`, `GET /pastes/<id>/`, `GET /pastes//raw`, `GET /pastes/<id>/raw/extra`, `GET /pastes/<id>/anything`, `OPTIONS /`, `HEAD /pastes`): each returns `404` with a `{"error": "<message>"}` body and `Content-Type: application/json`; test names carry `FR_020` and `FR_022` (Constitution III)
- [ ] T027 Create `tests/test_storage.py` covering the storage layer directly, without an HTTP server: `create_paste` yields distinct ids and distinct delete tokens across 1,000 calls; `load_paste` round-trips `id`, `content`, `created_at`, `expires_at`, and `delete_token` unchanged; `record_path` refuses every id failing `^[A-Za-z0-9_-]{1,64}$`; and a stray `.tmp-*` file in the directory is never loadable as a paste; test names carry `FR_002`, `FR_023`, `FR_028`

**Checkpoint**: `PYTHONPATH=src python -m pastebin serve --port 8080 --data /tmp/pastes` starts, prints the readiness line, and answers every request `404` with a JSON error body. `pytest` runs with both fixtures. User story work can now begin.

---

## Phase 3: User Story 1 - Share a text snippet and read it back (Priority: P1) 🎯 MVP

**Goal**: Submit a snippet and get back an identifier, a delete token, and a `/pastes/<id>` link; retrieve the snippet either as JSON with its metadata or as plain text, byte-for-byte unchanged.

**Independent Test**: Start the service, `POST /pastes` with `{"content": "hello"}`, then confirm `GET /pastes/<id>` returns the exact content with `expires_at: null` and `GET /pastes/<id>/raw` returns the identical bytes as `text/plain; charset=utf-8` — the complete core value, with no delete or expiry behaviour needed.

### Tests for User Story 1 ⚠️

> Write these first and confirm they FAIL before implementing T031–T035.

- [ ] T028 [P] [US1] Create `tests/test_create.py` covering creation in `tests/test_create.py`: FR-001 (`201` with `id`, `delete_token`, and `url == "/pastes/" + id`); FR-004 (`400` for invalid JSON, an absent/empty body, a missing `Content-Length`, a `Transfer-Encoding: chunked` request, the non-object bodies `"hello"` / `[1,2]` / `null` / `42`, a missing `content`, and a `content` that is an `int`, `bool`, `None`, `list`, or `dict`); FR-005 (`content` of exactly 65,536 UTF-8 bytes accepted; 65,537 bytes → `413`; `""` accepted); FR-007 (an extra `{"title": "y"}` field ignored, not rejected); FR-008 (the data directory is still empty after every rejection); FR-024 (`Content-Length` above 1,048,576 → `413`) — each test name carries its `FR_0nn` id
- [ ] T029 [P] [US1] Create `tests/test_read.py` covering reads: FR-009 (`200` with `id`, `content`, `created_at`, `expires_at`); FR-010 (`created_at` matches `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$` and `expires_at` is JSON `null` for a paste with no expiry); FR-011 (raw route returns `Content-Type: text/plain; charset=utf-8`, the content as the entire body with no added trailing newline, and a zero-length body for an empty paste); FR-012 (`'héllo 🌍\nline "two"\ttab\x07bell'` round-trips byte-for-byte on both routes); FR-003 (`delete_token` absent from both read responses); and `404` with a JSON error body for an id that was never issued
- [ ] T030 [P] [US1] Extend `tests/test_routing.py` with the FR-023 traversal cases: `GET /pastes/../../etc/passwd`, `GET /pastes/%2e%2e%2fetc%2fpasswd`, `GET /pastes/%2Fetc%2Fpasswd`, an absolute-path id, a 65-character id (one over the `{1,64}` limit), and an id containing a NUL byte each return `404` with a JSON error body and never return content from outside the data directory

### Implementation for User Story 1

- [ ] T031 [US1] Add `_read_body()` to `src/pastebin/server.py`: reject `Transfer-Encoding: chunked` with `400` (the service requires `Content-Length`); treat an absent `Content-Length` as an empty body → `400`; reject an unparsable or negative `Content-Length` with `400`; reject `Content-Length > PAYLOAD_MAX_BYTES` (1,048,576) with `413` **before reading a single body byte**; otherwise read exactly `Content-Length` bytes (FR-024, R-003)
- [ ] T032 [US1] Add `_parse_create(body_bytes)` to `src/pastebin/server.py` applying validation rules V-1…V-5 and V-8 in order: body parses as JSON else `400`; parsed value is a `dict` else `400`; `content` key present else `400`; `content` is a `str` — rejecting `int`, `bool`, `None`, `list`, `dict` — else `400`; `len(content.encode("utf-8")) <= 65536` (inclusive; measured on the UTF-8 encoding, not the character count) else `413`; all keys other than `content` and `expires_in` ignored rather than rejected. Each rejection carries a message naming the offending field (FR-004, FR-005, FR-007, Constitution II)
- [ ] T033 [US1] Implement `POST /pastes` in `src/pastebin/server.py`: on success call `storage.create_paste(data_dir, content)` with no expiry and answer `201` with `{"id": ..., "delete_token": ..., "url": "/pastes/" + id}`; nothing is written to the data directory on any rejection path (FR-001, FR-002, FR-003, FR-008)
- [ ] T034 [US1] Implement `GET /pastes/<id>` in `src/pastebin/server.py`: an id failing the allow-list answers `404` with no filesystem access; `storage.load_paste` returning `None` answers `404`; otherwise `200` with `{"id", "content", "created_at", "expires_at"}` where timestamps are rendered by `storage.iso_z` and `expires_at` is JSON `null` when there is no expiry, and `delete_token` is never included (FR-009, FR-010, FR-003, FR-023)
- [ ] T035 [US1] Implement `GET /pastes/<id>/raw` in `src/pastebin/server.py`: `200` with the content UTF-8 encoded as the entire response body, `Content-Type: text/plain; charset=utf-8`, an explicit `Content-Length`, and no added trailing newline; the `404` cases are identical to the JSON read (FR-011, FR-012)
- [ ] T036 [US1] Fill the FR-001…FR-005, FR-007…FR-012, FR-020, FR-022, FR-023, FR-024 rows of `tests/README.md` with their covering tests and run `python3 -m pytest` from the repository root to confirm the suite passes (Constitution III, Quality Gate 4)

**Checkpoint**: create-and-read works end to end — the service is independently useful and SC-001 / SC-007 are demonstrable. MVP deliverable.

---

## Phase 4: User Story 2 - Revoke a shared snippet (Priority: P2)

**Goal**: The creator can remove a snippet with the delete token issued at creation; afterwards it is indistinguishable from one that never existed, and nobody holding only the link can remove it.

**Independent Test**: Create a snippet, delete it with its token (expect `204`), confirm both read routes now answer `404`, then confirm that a missing, empty, wrong, or other-paste token against a live snippet answers `403` and leaves it readable.

### Tests for User Story 2 ⚠️

> Write these first and confirm they FAIL before implementing T038–T039.

- [ ] T037 [US2] Create `tests/test_delete.py`: FR-013 (`DELETE` with the matching `X-Delete-Token` → `204` with no body and no `Content-Type`, after which both read routes answer `404`); FR-014 (an absent header, an empty header value, a wrong token, and a *second paste's valid* token each → `403` with a JSON error body, and the paste stays readable at `200`); FR-015 (a wrong token of the same length as the stored token and a wrong token of a different length both → `403`, asserting the comparison is `secrets.compare_digest`-based rather than `==`); FR-016 (re-reading and re-deleting an already-deleted paste → `404`); FR-021 (a `DELETE` for an id never issued, with the correct-looking token, a wrong token, and no token at all, each → `404` and never `403`) — test names carry their `FR_0nn` ids

### Implementation for User Story 2

- [ ] T038 [US2] Add `token_matches(paste, supplied)` to `src/pastebin/storage.py` using `secrets.compare_digest` on the UTF-8 encodings of the supplied and stored tokens, treating `None` and `""` as non-matches without short-circuiting on length in a way that leaks the stored value (FR-014, FR-015, R-005)
- [ ] T039 [US2] Implement `DELETE /pastes/<id>` in `src/pastebin/server.py` in the **contractual order**: id allow-list → `404` with no I/O; `storage.load_paste` returning `None` → `404` (unknown or already deleted), so existence is resolved *before* the token is examined and `404` always takes precedence over `403`; then `token_matches` false → `403` with the record left in place and still readable; on a match `storage.delete_record` then `_send_no_content()` → `204` (FR-013, FR-014, FR-016, FR-021, contracts/http-api.md ordering rule)
- [ ] T040 [US2] Fill the FR-013…FR-016 and FR-021 rows of `tests/README.md` and run `python3 -m pytest` to confirm User Stories 1 and 2 both pass

**Checkpoint**: create, read, and revoke all work; the service is safe to use for sensitive content.

---

## Phase 5: User Story 3 - Let a snippet expire on its own (Priority: P3)

**Goal**: A snippet given a lifetime at creation reports its expiry moment, serves normally until then, and afterwards behaves exactly as though it never existed.

**Independent Test**: Create a snippet with `expires_in: 1`, confirm it reads `200` and reports `expires_at == created_at + 1`, wait past the moment, and confirm both reads and a correct-token delete all answer `404`.

> **Note**: Phases 3–4 accept creation without an `expires_in` field only; this phase introduces `expires_in` parsing (V-6/V-7), `expires_at` computation, and expiry enforcement across all routes.

### Tests for User Story 3 ⚠️

> Write these first and confirm they FAIL before implementing T042–T044.

- [ ] T041 [US3] Create `tests/test_expiry.py`: FR-017 (`expires_in: 3600` → the read reports `expires_at` exactly 3,600 seconds after `created_at`, and omitting `expires_in` → `expires_at: null`); FR-006 (`0`, `-1`, `2592001`, `1.5`, `"60"`, `null`, and `true` each → `400` with a JSON error naming `expires_in` and nothing stored; `1` and `2592000` both accepted); FR-018 (a paste with `expires_in: 1` reads `200` before the second elapses and `404` on both read routes after, and a `DELETE` with the *correct* token after expiry → `404` not `204`); and the boundary rule that a paste is readable strictly before `expires_at` and gone at or after it (`now >= expires_at`)
- [ ] T042 [US3] Add the FR-019 restart-spanning case to `tests/test_expiry.py`: a paste created with a 1-second lifetime through the public creation path, read back through a **second** in-process server constructed against the same data directory after the moment has passed, answers `404` — proving expiry is decided from the stored absolute timestamp and not from process uptime (FR-019, R-014)

### Implementation for User Story 3

- [ ] T043 [US3] Add `is_gone(paste, now)` to `src/pastebin/storage.py` returning `paste.expires_at is not None and now >= paste.expires_at`, and have `load_paste` treat a gone record as absent by returning `None` (optionally removing the expired file lazily) so every read and delete answers `404` identically to a never-issued id and no response discloses that the paste once existed (FR-018, FR-019, FR-021, R-009, data-model.md lifecycle)
- [ ] T044 [US3] Add `expires_in` validation V-6/V-7 to `_parse_create` in `src/pastebin/server.py`: absent → no expiry; present and not an `int`, or a `bool` (JSON `true`/`false`), or `None` (JSON `null` means "present and invalid", not "absent"), or a float such as `3600.0`, or outside `1 … 2_592_000` inclusive → `400` with a message naming `expires_in`, and nothing stored (FR-006, FR-008)
- [ ] T045 [US3] Compute the expiry moment in `src/pastebin/storage.py::create_paste`: truncate `created_at` to whole epoch seconds and set `expires_at = created_at + expires_in` when a lifetime is given, else `None`, so the rendered `expires_at` is exactly `expires_in` seconds after the rendered `created_at` (FR-017, R-009, Story 3 scenario 1)
- [ ] T046 [US3] Fill the FR-006 and FR-017…FR-019 rows of `tests/README.md` and run `python3 -m pytest` to confirm User Stories 1–3 all pass

**Checkpoint**: all API behaviour from the HTTP contract is implemented; SC-005 is demonstrable.

---

## Phase 6: User Story 4 - Run and restart the service (Priority: P4)

**Goal**: An operator starts the service on a chosen port and directory, knows from stdout when it is genuinely ready, gets a specific stderr diagnostic and a non-zero exit on any startup failure, and can restart without losing snippets.

**Independent Test**: Start the service against a directory path that does not yet exist, read the readiness line, create snippets, stop the process, restart against the same directory, and confirm every snippet, timestamp, and delete token survived; then confirm each bad-argument start prints to stderr and exits `2`.

### Tests for User Story 4 ⚠️

> Write these first and confirm they FAIL before implementing T050–T054. All three use the subprocess fixture from T024.

- [ ] T047 [US4] Create `tests/test_cli.py` for the process contract: FR-025 (the port is reachable on `127.0.0.1` and the server is bound to loopback only); FR-026 (a `--data` path with missing parent directories is created, and an existing directory holding records is used as-is); FR-027 (stdout carries exactly one line, `listening on 127.0.0.1:<port>`, and a request issued immediately after that line is read is *served*, not refused); FR-029 (a missing `serve` subcommand, a missing `--port`, a missing `--data`, `--port abc`, `--port 0`, `--port -1`, `--port 65536`, `--port 99999`, a `--data` whose parent is a regular file, a `--data` that exists but is not writable, a `--data` that is a file, and a port already in use each print a specific diagnostic on **stderr**, write **nothing** to stdout, and exit `2`); FR-030 (no diagnostic ever appears on stdout and per-request logs go to stderr) — test names carry their `FR_0nn` ids
- [ ] T048 [US4] Add the restart-durability test to `tests/test_cli.py` for FR-028 / SC-004: create 50 pastes against one data directory (mixed expiring and non-expiring, including multi-byte and emoji content), recording each `id`, `content`, `created_at`, `expires_at`, and `delete_token`; stop the process; restart against the same directory; then assert every non-expired paste returns an unchanged `id`, `content`, `created_at`, and `expires_at`, every recorded delete token still answers `204`, and a paste whose lifetime elapsed while the service was stopped answers `404` (SC-004, SC-005 restart case, Story 4 scenarios 3–4)
- [ ] T049 [US4] Add the FR-032 cases to `tests/test_storage.py`: with a stray non-record file, a `<id>.json` containing invalid JSON, a record carrying `"version": 2`, and a record whose `id` field disagrees with its filename all present in the data directory, the service still starts, reports each skipped entry on **stderr** with the `skipping unreadable record:` wording, and still serves a readable paste stored alongside them; a `GET` for an unreadable record answers `404`

### Implementation for User Story 4

- [ ] T050 [US4] Add `--port` validation to `src/pastebin/cli.py`: parse the value as an integer and require `1 … 65535`, otherwise print `pastebin: --port must be an integer between 1 and 65535, got <value>` to stderr and return exit code `2` without constructing a server or printing a readiness line (FR-029, R-013, contracts/cli.md failure table)
- [ ] T051 [US4] Add `--data` preparation to `src/pastebin/cli.py`: `os.makedirs(data_dir, exist_ok=True)` creating missing parents; reject a path that exists and is not a directory; then probe writability by actually creating and removing a temporary file inside it (not `os.access(W_OK)`, which is advisory and wrong under containers/ACLs). Every failure prints `pastebin: <message>` naming the path and the OS reason to stderr and returns `2` (FR-026, FR-029, R-013)
- [ ] T052 [US4] Wrap the `make_server` call in `src/pastebin/cli.py` so an `OSError` from `bind()` — most importantly a port already in use — prints `pastebin: 127.0.0.1:<port> is already in use` to stderr and returns `2`, with no readiness line ever printed for a failed start (FR-029, R-002)
- [ ] T053 [US4] Call `storage.scan_directory(data_dir)` from `src/pastebin/cli.py` after the directory is prepared and **before** the readiness line, so each unreadable or unrecognised entry is reported on stderr and startup continues rather than aborting (FR-032, R-012)
- [ ] T054 [US4] Lock the readiness and stream contract in `src/pastebin/cli.py`: the line is printed and flushed only after `make_server` has returned (socket bound and listening) and before `serve_forever()`, stdout receives nothing else ever, all diagnostics go to stderr, and `SIGINT` / `SIGTERM` trigger `server.shutdown()` plus `server_close()` and return `0` (FR-027, FR-030, R-002, contracts/cli.md)
- [ ] T055 [US4] Fill the FR-025…FR-032 rows of `tests/README.md` and run `python3 -m pytest` to confirm all four user stories pass

**Checkpoint**: all four user stories are independently functional; every FR-001…FR-032 has at least one covering test.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The cross-story success criteria, the complete traceability table, and the constitution quality gates.

- [ ] T056 [P] Add the FR-031 concurrency test to `tests/test_storage.py`: several threads repeatedly reading one paste while another thread deletes it, asserting every response is either a complete, correct record or a `404` — never partial, mixed, or corrupt content (FR-031, invariant S-4, spec concurrency edge case)
- [ ] T057 [P] Add the SC-006 uniqueness test to `tests/test_create.py`: 10,000 draws from `storage.new_id()` and `storage.new_delete_token()` produce no repeat, 1,000 real `POST /pastes` creations produce no repeated `id` or `delete_token`, two creations of identical content yield distinct ids and distinct tokens, and no `delete_token` appears in any read response (SC-006, FR-002, FR-003, spec dedup edge case)
- [ ] T058 [P] Add the SC-008 soak test to `tests/test_routing.py`: replay the entire malformed / oversized / hostile-path / unknown-route / undefined-method request set in one session against a single server, then assert a valid create-then-read round trip still succeeds — no request may stop the service from accepting further requests (SC-008, R-011)
- [ ] T059 [P] Add the SC-009 containment test to `tests/test_read.py`: plant a file with known contents *outside* the data directory, then confirm no traversal-shaped identifier on any route ever returns its contents — each attempt answers `404` (SC-009, FR-023)
- [ ] T060 Complete `tests/README.md`: every FR-001…FR-032 row filled with its covering test(s) and every SC-001…SC-010 row mapped to the test or quickstart scenario that demonstrates it (SC-002, Constitution III)
- [ ] T061 Verify the Constitution quality gates against `src/pastebin/**`: no import outside the standard library and no `pytest` import in runtime code (Principle I); no bare `except:` and no `except Exception: pass`, and no coercion of questionable input (Principle II); every requirement has a referencing test (Principle III); no abstraction with a single implementation and no speculative extension point beyond the four justified modules (Principle IV)
- [ ] T062 Run the full suite from the repository root with `python3 -m pytest -v` and confirm every test passes with no skipped or xfailed tests (Constitution Quality Gate 4, SC-002)
- [ ] T063 Walk [quickstart.md](./quickstart.md) scenarios V1–V7 manually against a real `PYTHONPATH=src python3 -m pastebin serve` process and confirm every pass criterion, including the three SC-010 documented example commands producing the exact outputs shown in contracts/cli.md
- [ ] T064 [P] Reconcile the documents with the built behaviour: update [quickstart.md](./quickstart.md), [contracts/http-api.md](./contracts/http-api.md), and [contracts/cli.md](./contracts/cli.md) for any wording or diagnostic that drifted during implementation, so docs and code agree (SC-010)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Setup — **BLOCKS all user stories**
- **User Story 1 (Phase 3)**: depends on Foundational only
- **User Story 2 (Phase 4)**: depends on Foundational; its tests create pastes, so it is demonstrated on top of US1's `POST`/`GET`
- **User Story 3 (Phase 5)**: depends on Foundational; extends US1's create/read path and US2's delete path with expiry
- **User Story 4 (Phase 6)**: depends on Foundational; its restart test exercises US1–US3 routes
- **Polish (Phase 7)**: depends on all four user stories (FR-031 needs delete, SC-008 needs the full route set)

### User Story Dependencies

- **US1 (P1)**: no dependency on any other story — the MVP
- **US2 (P2)**: needs a creatable, readable paste to revoke, so it builds on US1's routes; its own behaviour (token auth, 404-over-403) is independently testable
- **US3 (P3)**: needs creation and reading to attach a lifetime to, so it builds on US1; adds `expires_in` parsing and the expiry decision, and extends US2's delete with the expired → `404` case
- **US4 (P4)**: needs at least one route to prove durability against, so it builds on US1; its process-level requirements (readiness, exits, stream discipline, startup scan) are independently testable with the subprocess fixture alone

### Within Each User Story

- Tests are written and confirmed failing before the implementation tasks
- `storage.py` changes before `server.py` changes that call them
- Validation before storage, storage before the response
- The traceability-table task closes each story

### Parallel Opportunities

- **Phase 1**: T003, T004, T005 run in parallel after T001/T002
- **Phase 2**: the `storage.py` chain (T006–T015) and the `server.py` chain (T016–T020) are different files and can proceed in parallel; T026 and T027 are different test files and parallel once the fixtures (T023–T025) exist
- **Phase 3**: T028, T029, T030 are three different test files — fully parallel
- **Phase 7**: T056, T057, T058, T059, T064 touch different files — fully parallel
- **Across stories**: once Phase 2 is done, US4's process-level tasks (T047, T050–T054, all in `cli.py`) are independent of the `server.py` route work in US1–US3 and can be staffed concurrently
- Note: tasks editing the same file are deliberately **not** marked `[P]` — most of Phase 3–5 implementation lands in `src/pastebin/server.py` and must be sequential

---

## Parallel Example: User Story 1

```bash
# Launch all three User Story 1 test files together (different files, no shared edits):
Task: "Create tests/test_create.py covering FR-001, FR-004, FR-005, FR-007, FR-008, FR-024"
Task: "Create tests/test_read.py covering FR-009, FR-010, FR-011, FR-012, FR-003"
Task: "Extend tests/test_routing.py with the FR-023 traversal cases"

# Implementation is sequential — T031-T035 all edit src/pastebin/server.py.
```

## Parallel Example: Phase 2 Foundational

```bash
# Two independent module chains:
Task: "storage.py chain T006-T015 (constants, Paste, id allow-list, generation, atomic write, load, delete, scan)"
Task: "server.py chain T016-T020 (handler, response chokepoint, dispatch, containment, make_server)"
# Then T021-T022 (cli.py, __main__.py), then T023-T025 (fixtures), then T026/T027 in parallel.
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (T001–T005)
2. Phase 2: Foundational (T006–T027) — **blocks everything**
3. Phase 3: User Story 1 (T028–T036)
4. **STOP and VALIDATE**: run quickstart V1 and V2; SC-001 and SC-007 must hold
5. The service is already useful: share a snippet, read it back as JSON or plain text

### Incremental Delivery

1. Setup + Foundational → a service that starts, prints readiness, and answers `404` in the contractual JSON shape
2. + US1 → create and read (**MVP**; validate with quickstart V1, V2)
3. + US2 → revocation (validate with quickstart V3)
4. + US3 → self-expiring snippets (validate with quickstart V4)
5. + US4 → hardened startup and restart durability (validate with quickstart V5, V6)
6. + Polish → cross-story criteria SC-004, SC-006, SC-008, SC-009, SC-010 and the full traceability table

### Parallel Team Strategy

With multiple developers, after Phase 2 completes:

- Developer A: US1 then US3 — both land in `src/pastebin/server.py` route logic, so one owner avoids conflicts
- Developer B: US4 — `src/pastebin/cli.py` and `tests/test_cli.py` are disjoint from the route work
- Developer C: US2 — `DELETE` route plus `token_matches`, merged after US1's read routes exist

---

## Notes

- `[P]` tasks touch different files and have no dependency on an incomplete task
- `[Story]` labels map tasks to spec.md user stories for traceability; Setup, Foundational, and Polish tasks carry none
- Every test name carries the `FR_0nn` id(s) it covers, and `tests/README.md` holds the full table — Constitution III requires the mapping to be discoverable
- Verify each test fails before implementing against it; commit after each task or logical group
- Stop at any checkpoint to validate a story independently
- Constitution gates are not waived for small changes: stdlib-only runtime imports, no silent failure path, a test per requirement, and a written Principle IV justification for any added structure
