# Phase 0 Research: Pastebin Service

**Feature**: `001-pastebin-service` | **Date**: 2026-11-20

**Purpose**: resolve every open technical decision needed before design, within the fixed
constraints (Python 3.11+, standard library only, `pytest` for tests, interface exactly as
specified).

**Status**: no `NEEDS CLARIFICATION` items remain.

---

## R-001: HTTP server primitive

- **Decision**: `http.server.ThreadingHTTPServer` with a `BaseHTTPRequestHandler` subclass,
  `protocol_version = "HTTP/1.1"`, every response carrying an explicit `Content-Length`.
- **Rationale**: `ThreadingHTTPServer` is the only stdlib server that serves concurrent
  requests without extra machinery, which FR-031 requires ("serve a request correctly while
  other requests are in flight"). HTTP/1.1 is needed so that a client's keep-alive connection
  is not a correctness trap; it is safe only because every route produces a known-length body.
- **Alternatives considered**:
  - `HTTPServer` (single-threaded): rejected — one slow or hostile client blocks all others,
    and FR-031/SC-008 cannot be demonstrated.
  - `socketserver.ForkingTCPServer`: rejected — no benefit over threads at this scale, and
    POSIX-only.
  - Hand-rolled `asyncio` HTTP parsing: rejected — re-implements the one thing the stdlib
    already ships, directly against Principle IV (Simplicity).
- **Consequence**: handler methods run on worker threads, so shared mutable state must be
  avoided or locked (see R-008).

## R-002: Readiness line ordering

- **Decision**: construct the server (which binds and listens, as `bind_and_activate=True` is
  the default), then `print(f"listening on 127.0.0.1:{port}")` followed by an explicit
  `flush`, and only then call `serve_forever()`.
- **Rationale**: FR-027 requires that a request sent immediately after the line is served, not
  refused. `TCPServer.__init__` performs `bind()` and `listen()`, so the kernel accept queue is
  already taking connections when the line is printed; a client that connects between the print
  and `serve_forever()` waits in the backlog instead of getting `ECONNREFUSED`. Flushing
  matters because stdout is block-buffered when piped, which is exactly how tests read it.
- **Alternatives considered**:
  - Print before constructing the server: rejected — the line would lie; a request could be
    refused, and a port-in-use failure would print readiness and then fail.
  - Print from inside `serve_forever` / a timer: rejected — racy and more code for no gain.
- **Consequence**: the port-in-use diagnostic (FR-029) comes from server construction, which
  happens before any output, so readiness is never printed on a failed start.

## R-003: Rejecting oversized payloads before reading the body

- **Decision**: read the `Content-Length` header first. If it is absent on `POST /pastes`,
  treat the body as empty (→ `400`). If it is unparsable or negative → `400`. If it exceeds the
  payload ceiling → `413` with the body never read. If a `Transfer-Encoding: chunked` request
  arrives → `400` (the service requires `Content-Length`). Otherwise read exactly
  `Content-Length` bytes.
- **Payload ceiling**: `1_048_576` bytes (1 MiB).
- **Rationale**: FR-024 requires refusing an oversized request "without reading the whole body
  into memory", and `Content-Length` is the only pre-body size signal `BaseHTTPRequestHandler`
  offers. The ceiling must be high enough that *no valid* 65,536-byte-UTF-8 content can be
  refused as too large: JSON escaping can inflate a payload up to ~6× (every character emitted
  as `\uXXXX`), so a worst-case valid body is ~393 KiB plus framing. 1 MiB clears that with
  margin while still bounding per-request memory. A ceiling "just above" 65,536 would reject
  legal maximum-size content and break FR-005/SC-007.
- **Alternatives considered**:
  - Ceiling of 128 KiB: rejected — would 413 a valid maximum-size paste made of quotes or
    control characters.
  - No ceiling, enforce size only after parsing: rejected — unbounded buffering from a hostile
    client, violating FR-024.
  - Streaming/incremental JSON parsing: rejected — not in the stdlib, and unnecessary once a
    ceiling exists.
- **Consequence**: two distinct `413` causes, both with a JSON error body: body over the
  ceiling (detected before reading) and `content` over 65,536 UTF-8 bytes (detected after
  parsing). This also gives the spec's "oversized *and* unparsable → 413" behaviour for free.

## R-004: Identifier and deletion token generation

- **Decision**: identifier = `secrets.token_urlsafe(16)` (128 bits, 22 URL-safe characters);
  deletion token = `secrets.token_urlsafe(32)` (256 bits), generated independently.
- **Rationale**: FR-002 demands URL-path-safe, unguessable, order-independent identifiers;
  `token_urlsafe` yields exactly the `[A-Za-z0-9_-]` alphabet, which needs no escaping and
  cannot contain a path separator. FR-003 demands a token unrelated to the identifier, so the
  two are drawn from separate `secrets` calls. 128 bits makes accidental collision across the
  SC-006 budget of 10,000 creations negligible (~10⁻³¹), and creation still uses an exclusive
  file create (R-006) so a collision is impossible rather than merely improbable.
- **Alternatives considered**:
  - Sequential integers or a counter file: rejected — enumerable, and FR-002 forbids
    guessability from creation order.
  - `uuid.uuid4().hex`: acceptable but longer and no safer; `token_urlsafe` is more compact.
  - Content hash as identifier: rejected — would deduplicate identical content, which the spec
    explicitly forbids ("second creation of identical content produces a distinct identifier").
  - Deriving the token from the id (e.g. HMAC): rejected — one secret to leak, and FR-003 wants
    independence.

## R-005: Timing-safe token comparison

- **Decision**: `secrets.compare_digest(supplied, stored)` on the UTF-8 encodings, after the
  existence/expiry check.
- **Rationale**: FR-015 requires comparison that does not leak the stored token through
  response timing; `compare_digest` is the stdlib's constant-time primitive. Ordering matters:
  existence and expiry are resolved *first* so that FR-021's "404 beats 403" holds and no token
  comparison happens for an identifier that does not exist.
- **Alternatives considered**: `==` — rejected, short-circuits per byte and leaks a prefix
  oracle.

## R-006: Storage layout and durability

- **Decision**: one JSON file per paste, named `<id>.json`, directly in the storage directory.
  Fields: `id`, `content`, `created_at` (epoch seconds, int), `expires_at` (epoch seconds int or
  `null`), `delete_token`, `version` (int, `1`). Creation writes to a unique temporary file in
  the *same* directory, `fsync`s it, then `os.replace`s it onto the final name, having first
  reserved the final name with `os.open(..., O_CREAT | O_EXCL)`. Deletion is `os.remove`.
- **Rationale**: FR-028 requires a restart to restore every field unchanged, and the spec
  requires that "a partially written record is never served as a valid paste". `os.replace` is
  atomic within a filesystem, so a reader sees either no file or the complete file — never a
  half-written one. Writing the temp file in the same directory keeps the rename on one
  filesystem. The `O_EXCL` reservation makes FR-002's uniqueness and Story 4 scenario 7 ("the
  second instance never issues a colliding identifier") structural rather than probabilistic,
  including for two sequential runs against the same directory. One file per paste means a read
  is a single `open` of a known path — no index to rebuild at startup and nothing to keep in
  sync, which is the simplest thing that satisfies the requirements (Principle IV).
- **Alternatives considered**:
  - Single append-only log or one JSON index file: rejected — every read or delete rewrites or
    rescans shared state, and concurrent writers need real locking; also loses per-record
    isolation for FR-032.
  - `sqlite3` (stdlib): allowed by Principle I but rejected — a schema, a connection-per-thread
    policy, and migration thinking for a key→record store with no queries and no listing route.
  - Content in a separate sibling file from metadata: rejected — two files per paste means two
    writes to make atomic together, for no benefit.
  - `shelve`/`pickle`: rejected — opaque, version-fragile, and unsafe to load untrusted bytes.
- **Consequence**: the on-disk format is deliberately *not* part of the external contract
  (`version` exists so a future format can be recognised and skipped per FR-032).

## R-007: Path-traversal safety

- **Decision**: validate the identifier taken from the URL against `^[A-Za-z0-9_-]{1,64}$`
  before it touches the filesystem; anything else is `404` without any I/O. The file path is
  then composed as `os.path.join(data_dir, id + ".json")`.
- **Rationale**: FR-023 requires that no path outside the storage directory is ever read or
  written, whatever the requested identifier contains. An allow-list on the identifier shape is
  verifiable by inspection and makes `..`, `/`, `%2F`, absolute paths, and NUL bytes
  unrepresentable — strictly safer than trying to normalise a hostile path. (`BaseHTTPRequest
  Handler` leaves the path percent-encoded, so decoding happens before validation and an
  encoded slash is caught by the same check.)
- **Alternatives considered**:
  - `os.path.realpath` containment check: rejected as the primary defence — correct but
    subtler, and symlink-dependent; the allow-list removes the question.
  - `os.path.basename` sanitisation: rejected — silently rewrites a hostile input into a
    different valid one, which Principle II ("no coercing questionable input") forbids.

## R-008: Concurrency model

- **Decision**: no shared in-memory paste state. Each request opens, reads, writes, or removes
  files directly; isolation comes from `O_EXCL` creation and atomic `os.replace` (R-006). A
  read that races a delete sees either the complete file or `FileNotFoundError`, which maps to
  `404`.
- **Rationale**: FR-031 and the spec's concurrency edge case require that a read concurrent
  with a delete yields complete content or `404`, never partial content. Filesystem atomicity
  already provides that, so a lock would add contention and a second source of truth without
  changing behaviour. Keeping zero shared cache is also the smallest design (Principle IV).
- **Alternatives considered**:
  - A global `threading.Lock` around all storage operations: rejected — serialises the server
    against FR-031's intent and is not needed given atomic rename.
  - An in-memory index of pastes: rejected — must be kept consistent with disk, must be rebuilt
    at startup, and buys nothing without a listing route.
  - `fcntl` advisory locks: rejected — POSIX-only, and the single-process assumption plus
    atomic rename makes them unnecessary.

## R-009: Timestamp representation

- **Decision**: store `created_at` / `expires_at` as integer epoch seconds (UTC). Render them
  with `datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`. Expiry is
  evaluated as `now >= expires_at` → gone.
- **Rationale**: FR-010 fixes the wire format to whole-second UTC with a trailing `Z`;
  `datetime.isoformat()` emits `+00:00`, so an explicit `strftime` is used rather than
  post-processing a string. FR-019 requires expiry to be unaffected by restarts, which absolute
  epoch seconds give directly. Integer seconds make the "readable strictly before, gone at or
  after" boundary (spec edge case) exact instead of float-rounded. `created_at` is truncated at
  creation so that `created_at + expires_in` is precisely the rendered `expires_at`, satisfying
  Story 3 scenario 1.
- **Alternatives considered**:
  - Storing ISO strings on disk: rejected — every expiry check would re-parse, and comparison
    becomes string-shaped.
  - `time.monotonic`: rejected — meaningless across restarts, violating FR-019.
  - Sub-second precision: rejected — the spec's assumptions fix precision at whole seconds.

## R-010: Error responses and suppressing the stdlib's HTML errors

- **Decision**: one response helper used by every route; errors always
  `{"error": "<message>"}` encoded as UTF-8 JSON with `Content-Type: application/json`.
  `BaseHTTPRequestHandler.send_error` is never called from route logic, and
  `error_message_format` / `error_content_type` are overridden so that any error the base class
  raises on its own (e.g. an unparsable request line) still produces a JSON body rather than
  HTML.
- **Rationale**: FR-022 requires *every* error response to carry exactly that JSON shape. The
  base class's default error path emits an HTML page, so leaving it reachable would violate
  FR-022 for inputs the handler never sees.
- **Alternatives considered**: per-route ad-hoc `send_response` calls — rejected, FR-022 is
  easiest to guarantee with a single chokepoint.
- **Consequence**: `204` is the one response with no body and no `Content-Type`, per FR-013.

## R-011: Per-request failure containment

- **Decision**: each dispatch is wrapped so that an unexpected exception is reported to stderr
  (with traceback) and answered with a `500` JSON error body; the server keeps serving. No bare
  `except:` and no `except Exception: pass`.
- **Rationale**: SC-008 requires that no request — malformed, oversized, hostile-path, or
  unknown-route — stops the service from accepting further requests. Principle II forbids
  swallowing the failure, so the handler converts it into a reported error on stderr plus an
  explicit error response, which is exactly the permitted "convert it into a reported error"
  case.
- **Alternatives considered**:
  - Let exceptions propagate: rejected — `ThreadingHTTPServer` would answer with nothing or an
    HTML 500, and the client sees a dropped connection.
  - Catch and ignore: forbidden by Principle II.
- **Note**: `500` is a backstop for defects, not a specified outcome; every behaviour named in
  the spec maps to `201`/`200`/`204`/`400`/`403`/`404`/`413`.

## R-012: Unreadable or unrecognised storage entries (FR-032)

- **Decision**: at startup, scan the storage directory once; any entry that is not a readable
  `<id>.json` record with a recognised `version` is reported on stderr as
  `skipping unreadable record: <path>: <reason>` and otherwise ignored. The same report is
  emitted if such an entry is encountered later during a read, and the read answers `404`.
- **Rationale**: FR-032 requires both "continue to start and serve readable snippets" and
  "report the skipped entry as a diagnostic on standard error". A startup scan makes the
  diagnostic deterministic and testable; the runtime check covers entries that appear or rot
  after startup. No index is built from the scan (R-008) — it exists only to report.
- **Alternatives considered**:
  - Report lazily only: rejected — an operator would not learn about a corrupt record until
    someone happened to request it.
  - Refuse to start on a bad entry: rejected — directly contradicts FR-032.
  - Delete or repair bad entries: rejected — destroys operator data the service does not
    understand.

## R-013: CLI parsing, validation, and exit behaviour

- **Decision**: `argparse` with a `serve` subcommand and required `--port` / `--data`. `--port`
  is validated as an integer in `1..65535`; `--data` is created with
  `os.makedirs(..., exist_ok=True)` and then probed for writability by creating and removing a
  temporary file in it. Every startup failure prints `pastebin: <specific message>` to stderr
  and returns exit code `2`; success returns `0`.
- **Rationale**: FR-029 enumerates the startup failures (missing/invalid/out-of-range `--port`
  or `--data`, undeployable directory, port in use) and requires a specific diagnostic on
  stderr plus a non-zero exit. FR-026 requires parent directories to be created. A write probe
  is needed because a directory can exist and be unwritable, which `makedirs` will not reveal.
  `argparse` already writes its own usage errors to stderr and exits `2`, so using the same code
  for hand-raised errors keeps the contract uniform (FR-030: diagnostics on stderr only).
- **Alternatives considered**:
  - `sys.argv` parsing by hand: rejected — more code, worse messages.
  - Checking writability with `os.access(W_OK)`: rejected — advisory only and wrong under
    containers/ACLs; an actual write is the real test.
  - Deferring the port check to `bind()`: rejected — the diagnostic for `--port 99999` should
    name the argument, not surface a socket error.

## R-014: Test strategy with pytest

- **Decision**: `pytest` only (dev dependency, never imported by runtime code).
  `pyproject.toml` sets `[tool.pytest.ini_options] pythonpath = ["src"]` so `import pastebin`
  and `python -m pastebin` resolve the same package. Two fixtures:
  1. **in-process server** — `ThreadingHTTPServer` on port `0` in a daemon thread with a
     `tmp_path` data directory, driven by `http.client`. Covers the API requirements
     (FR-001…FR-024) fast.
  2. **subprocess server** — `python -m pastebin serve --port <free> --data <tmp>` launched with
     `subprocess.Popen`, readiness detected by reading the `listening on 127.0.0.1:<port>` line
     from stdout. Covers FR-025…FR-032, restart/persistence (SC-004), stream separation
     (FR-030), and exit statuses.
  Every test name or docstring names the requirement ids it covers, and a traceability table in
  `tests/README.md` maps FR-001…FR-032 → tests, per Principle III.
- **Rationale**: Principle III requires a discoverable requirement→test mapping and a test for
  every error path. Requirements about process behaviour (readiness line, exit codes, restart
  durability) are only honestly testable against a real process, while the ~40 API cases would
  be needlessly slow as subprocesses — hence two fixtures rather than one.
- **Alternatives considered**:
  - `unittest`: rejected — the user specified pytest.
  - Calling handler methods with mocked sockets: rejected — tests the mock, not the HTTP
    behaviour the spec is written in terms of.
  - A fixed test port: rejected — flaky in parallel/CI; port `0` plus a readiness line is
    deterministic.
  - Real `time.sleep` for every expiry test: used only for the 1-second cases (SC-005);
    long-lifetime expiry is tested by writing an already-past `expires_at` through the public
    creation path plus a short lifetime, never by patching the clock in production code.

---

## Resolved constraint summary

| Question | Resolution | Source |
|---|---|---|
| Language/runtime | Python 3.11+, CPython, stdlib only | user input, Constitution I |
| HTTP layer | `ThreadingHTTPServer` + `BaseHTTPRequestHandler`, HTTP/1.1 | R-001 |
| Test runner | `pytest`, `pythonpath = ["src"]` | user input, R-014 |
| Payload ceiling | 1 MiB (pre-read, `Content-Length`) | R-003 |
| Content limit | 65,536 UTF-8 bytes inclusive | FR-005 |
| Identifier | `secrets.token_urlsafe(16)`, `[A-Za-z0-9_-]{22}` | R-004 |
| Delete token | `secrets.token_urlsafe(32)`, compared with `compare_digest` | R-004, R-005 |
| Storage | one `<id>.json` per paste, `O_EXCL` + fsync + `os.replace` | R-006 |
| Timestamps | epoch-second ints on disk, `%Y-%m-%dT%H:%M:%SZ` on the wire | R-009 |
| Expiry rule | gone when `now >= expires_at` | R-009 |
| Startup failures | specific stderr diagnostic, exit `2` | R-013 |
