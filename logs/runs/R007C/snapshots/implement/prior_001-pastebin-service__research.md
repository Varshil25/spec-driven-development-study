# Phase 0 Research: Pastebin Service

**Feature**: `001-pastebin-service` | **Date**: 2026-11-09 | **Plan**: [plan.md](./plan.md)

## Unknowns extracted from Technical Context

The spec's Constraints section fixes the language (Python 3.11+), the dependency policy (standard
library only), the package layout (`pastebin` under `src/`), the command form, and the entire HTTP
surface. The user input for this phase fixes the test runner (`pytest`). No field of Technical
Context is therefore marked NEEDS CLARIFICATION. What remained open were *how* questions — which
standard-library mechanism satisfies each requirement — resolved below.

| # | Question | Driving requirements |
|---|----------|----------------------|
| R-01 | Which `http.server` server class and HTTP version give concurrent service without head-of-line blocking? | FR-042, SC-010 |
| R-02 | How are identifiers and delete tokens generated so they are unique and unguessable? | FR-013, FR-014 |
| R-03 | How is a snippet made visible all-or-nothing, and deleted without yielding a partial read? | FR-043, FR-031 |
| R-04 | How is the storage directory laid out and how are path-derived identifiers made safe? | FR-003, FR-029, FR-036 |
| R-05 | What is "what the largest valid submission could occupy", and how is reading bounded? | FR-040 |
| R-06 | How are timestamps produced, stored, and compared at second precision? | FR-019, FR-027, FR-028 |
| R-07 | How is every undefined path *and* every unsupported method turned into a 404 rather than `http.server`'s 501? | FR-036, FR-037 |
| R-08 | Which exceptions are caught where, so that Principle II is honoured while FR-038/039 still produce a 500? | FR-037, FR-038, FR-039 |
| R-09 | How is the output contract (one stdout line, no request logs) enforced against `http.server`'s defaults? | FR-004, FR-044, SC-009 |
| R-10 | How do tests exercise expiry and restart without a fake clock library? | FR-027, FR-028, FR-030, Principle III |

---

## R-01 — Concurrency model

**Decision**: `http.server.ThreadingHTTPServer` with `daemon_threads = True`, handler
`protocol_version = "HTTP/1.0"`, and a per-connection socket timeout of 10 seconds set via the
handler's `timeout` class attribute.

**Rationale**: `ThreadingHTTPServer` is the standard library's own thread-per-connection HTTP server,
so FR-042 is satisfied without writing a scheduler. `daemon_threads = True` means a caller that has
gone quiet cannot hold up process exit. The 10-second timeout is what makes the "connects and goes
quiet" edge case bounded rather than merely parallel: `socketserver.StreamRequestHandler.setup()`
applies the `timeout` attribute to the connection socket, so a stalled request-line or body read
raises `TimeoutError` instead of pinning a thread forever. Keeping `protocol_version` at the default
`HTTP/1.0` means each connection serves one request and closes, which removes keep-alive framing
from the problem space entirely — notably, it makes the FR-040 "reject before reading the body" case
safe, since we never have to drain an unread body to reuse the connection.

**Alternatives considered**:
- *Single-threaded `HTTPServer`*: rejected — directly violates FR-042, and one quiet caller would
  stall the service.
- *`ForkingHTTPServer`*: rejected — heavier per request, POSIX-only, and buys nothing here since
  there is no shared mutable in-process state to isolate.
- *`asyncio` with a hand-written HTTP parser*: rejected under Principle IV; it would mean owning
  request parsing that `http.server` already provides, for a service with no throughput target.
- *`protocol_version = "HTTP/1.1"` with keep-alive*: rejected — it obliges us to drain or close
  precisely on every error path, adding failure modes no requirement asks for.

## R-02 — Identifiers and delete tokens

**Decision**: identifier = `secrets.token_urlsafe(16)` (22 URL-safe characters, 128 bits of
entropy); delete token = `secrets.token_urlsafe(32)` (43 characters, 256 bits), drawn independently.
On publication the record is linked into place with `os.link`, which fails with `FileExistsError` if
that identifier is already in use; the service then regenerates and retries (bounded at 5 attempts,
after which it raises rather than returning a duplicate).

**Rationale**: `secrets` is the standard library's CSPRNG interface, so both values are unguessable
(FR-013) and the token is not derivable from the identifier (FR-014) because they are separate
draws. 128 bits makes collision with *any* previously issued identifier — including ones whose files
have since been deleted, which the directory can no longer attest to — negligible rather than merely
unlikely. The `os.link` guard additionally makes collision with a *live* snippet impossible rather
than improbable, and costs one line. `token_urlsafe` output is already URL-safe, matching the spec
Assumption about identifier shape and the `/pastes/<id>` location.

**Alternatives considered**:
- *UUID4 hex*: equivalent entropy but 32 characters and a dashed/undashed ambiguity in paths; no
  advantage.
- *Monotonic counter plus random suffix*: rejected — requires shared state and a lock for a property
  randomness already provides.
- *A persisted set of all issued identifiers*: rejected — a second source of truth to keep durable
  and atomic, for a collision probability of roughly 2⁻¹²⁸ per publication (Principle IV).
- *Deriving the token as `hmac(secret, id)`*: rejected — introduces a server secret that must itself
  survive restarts, and FR-014 explicitly wants non-derivability.

## R-03 — Atomic publication, read, and deletion

**Decision**: publication writes the complete JSON record to `<DIR>/.tmp-<random>` in the *same*
directory, `flush`es and `os.fsync`s it, closes it, then `os.link`s it to `<DIR>/<id>.json` and
unlinks the temporary name. Reading is a single `Path.read_bytes()` on the final name. Deletion is a
single `os.unlink` of the final name.

**Rationale**: POSIX `link` within one filesystem is atomic and fails if the destination exists, so
a concurrent reader either does not see the name at all or sees a fully written file — never a
partial one (FR-043, first half). Because readers read the whole file in one call and never re-stat
it, a deletion that lands mid-request either happens before the open (reader gets
`FileNotFoundError` → 404) or after it (the unlinked inode stays readable through the open handle →
the whole snippet) — never a truncated body (FR-043, second half). `os.unlink` removing the only
link makes deletion permanent across restarts (FR-031). `fsync` before linking is what makes the
durability claim honest after a host crash rather than only after a clean stop.

**Alternatives considered**:
- *`os.replace` onto the final name*: equally atomic for visibility, but it silently overwrites,
  which would turn an identifier collision into data loss instead of the retry in R-02. `os.replace`
  is still the right tool when there is no uniqueness requirement; `link` is right here.
- *Write directly to the final path*: rejected — a reader could observe a half-written file,
  violating FR-043.
- *A lock file or `fcntl` advisory locking around reads and writes*: rejected — the rename/link
  discipline already gives the required guarantees, and locking would serialise readers against
  FR-042's spirit while adding a deadlock surface.
- *An in-process `threading.Lock` plus an in-memory index*: rejected — the index would be a second
  source of truth, contradicting the spec's "storage location is the sole source of truth", and it
  would still need the atomic write for restart safety.

## R-04 — Storage layout and identifier safety

**Decision**: one file per snippet, flat, named `<id>.json`, directly under the nominated directory.
The directory is created with `Path(dir).mkdir(parents=True, exist_ok=True)` and then probed for
writability by creating and deleting a temporary file inside it. An identifier taken from a request
path is matched against `^[A-Za-z0-9_-]{1,64}$` *before* it is ever joined to a path; anything else
is a 404 without touching the filesystem.

**Rationale**: a flat directory needs no sharding logic for a single-operator service with no stated
snippet-count limit, and `<id>.json` makes the file hand-inspectable, which the spec's
"hand-edited" edge case implicitly assumes. `mkdir(parents=True)` covers FR-003 including missing
parents. The probe write is the only way to distinguish "directory exists" from "directory is
usable" — `os.access` consults permission bits and lies on read-only mounts and under some
containers, and FR-005 demands we refuse to start rather than discover the problem on first
publication. The identifier pattern is the single defence against `../` traversal and against
absolute-path identifiers; validating before path construction (rather than resolving and checking
containment afterwards) keeps that defence to one `re.fullmatch`. The pattern is a superset of what
`token_urlsafe` emits, so an identifier the service issued always matches, and a 64-character cap
keeps a long path from reaching the filesystem's own limits.

**Alternatives considered**:
- *A single JSON or SQLite file holding all snippets*: SQLite is stdlib and would give atomicity for
  free, but every publication would then contend on one database and a corrupt database would take
  down every snippet, where FR-038 explicitly wants damage confined to the affected snippet.
- *Two-level sharding (`ab/abcdef.json`)*: rejected — speculative scaling with no requirement.
- *Checking containment with `Path.resolve()` after joining*: rejected — symlink-dependent and
  subtler than refusing the bad identifier outright.

## R-05 — Bounding the request body

**Decision**: `MAX_CONTENT_BYTES = 65_536`; `MAX_BODY_BYTES = 6 * MAX_CONTENT_BYTES + 1_024 =
394_240`. If `Content-Length` parses to a value greater than `MAX_BODY_BYTES`, respond 413
immediately without reading the body. Otherwise read at most `MAX_BODY_BYTES + 1` bytes from the
connection (whether or not a length was declared); if the read yields more than `MAX_BODY_BYTES`,
respond 413. A `Content-Length` that is not a non-negative integer is a 400.

**Rationale**: FR-040 defines the ceiling as "what the largest valid submission could occupy", so the
bound has to be derived from the content limit rather than guessed. JSON's worst-case expansion for
a string is 6 bytes of output per byte of UTF-8 input: a C0 control character is one UTF-8 byte and
serialises as `\u0001`. Characters that cost more per *character* cost less per *byte* — an
astral-plane character is 4 UTF-8 bytes and at most 12 JSON bytes (a surrogate pair), a ratio of 3 —
so 6× is the true maximum. The `+1_024` slack covers `{"content": ..., "expires_in": 2592000}`,
whitespace, and the unknown extra fields FR-015 requires us to tolerate. Reading one byte past the
ceiling is what distinguishes "exactly at the limit" from "over it" in a single read, and applying
the ceiling even when no length is declared is exactly the second sentence of FR-040 — a caller who
omits or understates `Content-Length` hits the same wall.

**Consequences worth noting**: `Transfer-Encoding: chunked` bodies are not decoded (`http.server`
does not decode them); such a body will not parse as JSON and so becomes a 400 under FR-016. No
requirement covers chunked submissions, and 400 is a defined, explained rejection, so FR-037 holds.
A caller that declares a length and then stops sending trips the R-01 socket timeout; the handler
answers 400 ("request body incomplete") on a best-effort basis and closes.

**Alternatives considered**:
- *A round number such as 1 MiB*: rejected — larger than any valid submission, so it would accept
  bodies FR-040 says to reject, and the number would not be traceable to a requirement.
- *`6 * MAX_CONTENT_BYTES` with no slack*: rejected — a valid maximum-size submission with a long
  unknown extra field could exceed it, turning FR-015 compliance into a 413.
- *Trusting `Content-Length` alone*: rejected — the second sentence of FR-040 exists precisely to
  forbid this.

## R-06 — Timestamps

**Decision**: `created_at = datetime.now(timezone.utc).replace(microsecond=0)`, formatted with
`strftime("%Y-%m-%dT%H:%M:%SZ")`. When a lifetime is given,
`expires_at = created_at + timedelta(seconds=expires_in)`, computed once at publication and stored
in the same format; otherwise `null`. Expiry is evaluated on each access by parsing the stored string
with `datetime.strptime(..., "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)` and treating the
snippet as absent when `now >= expires_at`.

**Rationale**: truncating microseconds at creation — rather than only at formatting time — makes the
stored value and the served value identical, so FR-028's "computed once and never changed" is true of
the bytes on disk, and the expiry moment is exactly `created_at + lifetime` with no sub-second drift.
`%Y-%m-%dT%H:%M:%SZ` emits precisely the FR-019 shape. `datetime.fromisoformat` would also parse the
stored form on 3.11+, but `strptime` with the explicit format rejects anything that is not our own
canonical shape, which is what turns a hand-edited timestamp into the FR-038 internal error instead
of a silently different expiry. Comparing with `>=` is what makes "at or after" unreadable (FR-027,
SC-005). Lazy evaluation means an expired file may linger on disk; the spec's Assumptions explicitly
leave reclamation unspecified, so nothing removes it, and no background thread exists (Principle IV).

**Alternatives considered**:
- *Storing epoch seconds*: simpler to compare, but the file would no longer be the hand-readable
  record the FR-038 edge case assumes, and we would still need the ISO form for responses.
- *Deleting expired files on access*: rejected — an unrequested write on the read path, and it would
  make a read request fail on a read-only directory.
- *A sweeper thread*: rejected — "no background reclamation process is required, and none is
  specified".

## R-07 — Routing every undefined path and method to 404

**Decision**: route on `urllib.parse.urlsplit(self.path).path` against exactly four patterns
(`POST /pastes`, `GET /pastes/<id>`, `GET /pastes/<id>/raw`, `DELETE /pastes/<id>`); everything else
is a 404 JSON error. To stop `http.server` from answering unsupported verbs with its own 501 HTML,
the handler defines `__getattr__` to return the 404 responder for any attribute whose name starts
with `do_`, and to raise `AttributeError` for every other name.

**Rationale**: `BaseHTTPRequestHandler.handle_one_request` dispatches on `hasattr(self, "do_" +
command)` and sends a 501 when the attribute is missing. FR-036 requires 404 for "any defined path
used with a method it does not support", and FR-032 requires a JSON error body on *every*
unsuccessful response, so the 501-HTML path must become unreachable. A `do_`-scoped `__getattr__` is
four lines and covers every verb — including ones nobody thought to enumerate — where a hand-written
list of `do_PUT`/`do_PATCH`/`do_HEAD`/`do_OPTIONS` would silently miss the next one. Restricting it
to the `do_` prefix keeps it from masking genuine typos elsewhere in the handler, which is the usual
objection to `__getattr__`. Splitting the query string off before matching means `/pastes/<id>?x=1`
reads the snippet instead of 404-ing on a path the caller never meant to change.

**Residual gap, accepted**: `http.server` still answers malformed HTTP itself — an unparseable
request line, a request line over 65,536 bytes (414), or an unsupported HTTP version (505) — with its
own HTML error. These are not caller *inputs* in the sense of FR-037 (which enumerates bodies,
fields, paths, and methods); reaching them requires sending something that is not an HTTP request.
Intercepting them would mean reimplementing `handle_one_request`, which Principle IV rejects.

**Alternatives considered**:
- *Overriding `handle_one_request`*: rejected — a ~25-line copy of standard-library code to own and
  keep in step with it.
- *Overriding `send_error` to emit JSON*: keeps the body shape but not the status (501 ≠ 404), so it
  does not satisfy FR-036 on its own.
- *Explicit `do_PUT = do_PATCH = ... = _not_found`*: works for listed verbs only; the open-ended
  wording of FR-036 argues for the general mechanism.

## R-08 — Exception handling discipline (Principle II)

**Decision**: no bare `except:` and no `except Exception` anywhere. Each `try` names the exceptions
it handles, at the site that handles them:

| Site | Caught | Translation |
|------|--------|-------------|
| Read a snippet file | `FileNotFoundError` | 404 (unknown, deleted, or never issued) |
| Read a snippet file | `OSError`, `UnicodeDecodeError`, `json.JSONDecodeError` | 500 + stderr diagnostic naming the id (FR-038/039) |
| Validate a decoded record (shape, types, timestamp format) | — (explicit check, raises `StoreCorrupt`) | 500 + stderr diagnostic (FR-038/039) |
| Delete a snippet file | `FileNotFoundError` | 404 (lost a race with another deletion) |
| Parse the request body | `json.JSONDecodeError`, `UnicodeDecodeError` | 400 (FR-016) |
| Parse `Content-Length` | `ValueError` | 400 |
| Read the request body | `TimeoutError` | best-effort 400, then close (R-01) |
| `mkdir` / writability probe at startup | `OSError` | stderr + exit 1 (FR-005) |
| Bind the listening socket | `OSError` | stderr + exit 1 (FR-005) |
| Link a new record into place | `FileExistsError` | regenerate the identifier and retry (R-02) |

**Rationale**: a module-defined `StoreCorrupt` exception (rather than a `None` return) is what keeps
the storage layer from handing back a sentinel the handler could mistake for a snippet, which
Principle II names explicitly. Catching `FileNotFoundError` *before* the broader `OSError` is what
keeps "absent" from being reported as "damaged", and catching `OSError` at all is what keeps
"damaged" from being reported as "absent" — the distinction FR-038 is entirely about. Every caught
exception above is either answered with a defined status or turned into a non-zero exit, so no code
path produces a plausible-but-wrong result.

**Deliberate non-decision**: there is no catch-all around the request handler. If an unanticipated
exception escapes, `socketserver` closes the connection and the caller sees a failed request — loud,
not silent. Adding a blanket `except Exception` returning 500 would be the exact "plausible but
wrong" path Principle II forbids, and FR-039 reserves 500 for damaged storage specifically.

## R-09 — Enforcing the output contract

**Decision**: override `log_message` and `log_error` on the handler to do nothing; never call
`send_error`. Print the ready line with `print(f"listening on 127.0.0.1:{port}", flush=True)` after
`ThreadingHTTPServer` construction (which binds and listens) and before `serve_forever()`. Write all
diagnostics with explicit `print(..., file=sys.stderr, flush=True)`.

**Rationale**: `BaseHTTPRequestHandler.log_message` writes an Apache-style line to stderr for every
request, which FR-044 and SC-009 forbid; silencing it is a two-line override and is the single most
easily missed requirement in the feature. `log_error` is silenced for the same reason — it fires on
client errors. Printing after the server object exists is what makes FR-004's "once — and not
before — it is ready" true: `HTTPServer.__init__` performs both `bind` and `listen`, so the socket is
already accepting connections when the line appears, and a port conflict raises before anything is
printed (FR-005). `flush=True` matters because stdout is a pipe under test and the ready line is the
fixture's start signal.

**Alternatives considered**:
- *Configuring `logging` with a null handler*: rejected — a logging setup that is required to emit
  nothing is a knob with one caller and no requirement (Principle IV).
- *Printing before constructing the server*: rejected — would announce readiness before the socket
  exists, and would print even when the bind then fails.

## R-10 — Testing expiry, restart, and the output contract

**Decision**: two fixtures in `conftest.py`.
1. An **in-process** fixture that calls `server.make_server(...)` on port 0 and runs
   `serve_forever()` in a thread, exposing the actual bound port. Used by most tests; lets a test
   substitute the store's clock function via `monkeypatch` to reach expiry instantly.
2. A **subprocess** fixture that launches `python -m pastebin serve --port <free> --data <tmp>` with
   `src/` on `PYTHONPATH` and pipes captured, waiting for the ready line. Used by the CLI, output
   contract, bind-failure, and restart tests, where the real process boundary is the thing under test.

Expiry is additionally covered without any clock substitution by (a) publishing with
`expires_in: 1` and sleeping just past the second boundary, and (b) hand-writing a record whose
`expires_at` is in the past — legitimate because the on-disk format is a published contract
([contracts/storage.md](./contracts/storage.md)) and FR-030 obliges a new instance to honour it.
The HTTP client is `http.client`/`urllib.request` from the standard library, with raw `socket` used
only for the malformed-framing cases (declared-but-unsent body, understated `Content-Length`).

**Rationale**: patching a clock inside a subprocess is not possible without adding a test-only hook
to runtime code, which Principle IV forbids; running in-process removes the need for one. But the
ready line, the exit statuses, and the restart story are properties of the *process*, so they need
the subprocess fixture — the two fixtures exist because two requirements groups genuinely differ,
not for convenience. Port 0 plus reading back `server_address[1]` avoids the flaky
"pick a port and hope" pattern across a suite that starts many servers.

**Alternatives considered**:
- *`freezegun` or `time-machine`*: third-party; forbidden by Principle I even for tests, which the
  constitution exempts only for `pytest` itself.
- *Subprocess-only testing*: would force a `--now` or `PASTEBIN_FAKE_TIME` hook into runtime code
  purely for tests — a knob with no production caller.
- *In-process-only testing*: cannot assert the ready line, stderr silence, or exit statuses, leaving
  FR-004, FR-005, FR-006, and FR-044 untested, which Principle III forbids.

---

## Summary of resolved context

No NEEDS CLARIFICATION markers remain. The design uses `http.server.ThreadingHTTPServer`
(HTTP/1.0, 10 s socket timeout), one `fsync`ed JSON file per snippet linked atomically into a flat
directory, `secrets.token_urlsafe` identifiers and tokens, a 394,240-byte read ceiling derived from
the content limit, second-precision UTC ISO 8601 timestamps evaluated lazily, `do_`-scoped
`__getattr__` routing so every unsupported verb is a 404, narrowly scoped exception handling with a
`StoreCorrupt` exception for damaged records, silenced `http.server` logging, and a two-fixture
pytest harness.
