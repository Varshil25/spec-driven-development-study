# Phase 0 Research: Pastebin Service

**Feature**: `001-pastebin-service` | **Date**: 2026-11-16 | **Plan**: [plan.md](./plan.md)

**Purpose**: Resolve every NEEDS CLARIFICATION in the plan's Technical Context and record the
standard-library techniques that satisfy the spec's functional (FR-001 … FR-029) and security
(SR-001 … SR-012) requirements. Every decision below is constrained by Constitution Principle I
(standard library only) and Principle IV (smallest design that satisfies the spec).

---

## R-01: HTTP server primitive

**Decision**: `http.server.ThreadingHTTPServer` with a single `BaseHTTPRequestHandler` subclass,
`daemon_threads = True`, `protocol_version = "HTTP/1.1"`.

**Rationale**: `ThreadingHTTPServer` is stdlib, binds and listens in its constructor
(`bind_and_activate=True`), and is the only stdlib HTTP server that serves concurrent requests.
The spec requires correct behaviour under concurrent revocation and concurrent read-during-revoke
(SR-007, Edge Cases "Concurrent revocation" / "Concurrent reads during revocation"), so
concurrency is a *specified* requirement rather than speculative generality — this satisfies
Principle IV's justification bar. `HTTP/1.1` is needed so that `Content-Length`-delimited
responses and keep-alive behave predictably; every response we emit sets an explicit
`Content-Length`.

**Alternatives considered**:
- `http.server.HTTPServer` (single-threaded): rejected — a single in-flight request would
  serialise all others, and the concurrency edge cases could not be demonstrated at all.
- `socketserver.ForkingTCPServer`: rejected — process-per-request makes the in-process lock used
  for atomic revocation (R-09) useless and is not portable to all targets.
- `asyncio` + hand-rolled HTTP parsing: rejected — writing an HTTP/1.1 parser is far more moving
  parts than the feature needs, and hand-rolled parsing is exactly the attack surface
  Principle IV warns about.
- `wsgiref.simple_server`: rejected — it is a reference WSGI container, still single-threaded by
  default, and adds a WSGI indirection layer for no gain.

---

## R-02: Readiness line ordering (FR-003, FR-004, SC-006)

**Decision**: Construct the server (which performs `socket()`, `bind()`, and `listen()`), then
`print(f"listening on 127.0.0.1:{port}", flush=True)`, then call `serve_forever()`. The port
printed is the port actually bound (`server.server_address[1]`), not the literal argument.

**Rationale**: `socketserver.TCPServer.__init__` with the default `bind_and_activate=True` has
already called `listen()` by the time it returns, so the kernel accept queue is active. A client
that connects immediately after seeing the readiness line is queued, not refused — this is
exactly SC-006 and FR-003's "only once it is able to accept requests". `flush=True` matters
because stdout is block-buffered when piped to a test harness; without it the line can sit in the
buffer long after the service is ready. Printing the *bound* port satisfies FR-003's "with `PORT`
replaced by the port in use" and makes `--port 0` usable for tests.

**Alternatives considered**:
- Print before constructing the server: rejected — violates FR-004 (a bind failure would have
  already printed the readiness line) and SC-006.
- Print from inside `serve_forever()` / a `service_actions` hook: rejected — later than necessary
  and harder to reason about; the listen backlog is already open before that point.

---

## R-03: Storage layout and durability (FR-023, FR-024, SR-008)

**Decision**: One JSON file per paste at `<data_dir>/<id>.json`, UTF-8 encoded, containing
`{"id", "content", "created_at", "expires_at", "delete_token"}`. The data directory is created
with `os.makedirs(path, mode=0o700, exist_ok=True)` followed by an explicit
`os.chmod(path, 0o700)`. Record files are created via a `tempfile.NamedTemporaryFile`-free
pattern: `os.open(tmp_path, O_WRONLY|O_CREAT|O_EXCL, 0o600)` in the *same* directory, write,
`os.fsync`, close, then `os.replace(tmp_path, final_path)`.

**Rationale**:
- One file per paste gives O(1) lookup keyed by identifier, needs no index, and makes a corrupt
  record isolate to a single paste (FR-024). It also means no global rewrite on create/delete,
  so there is no whole-store consistency problem to solve.
- `os.replace` is atomic on POSIX within one filesystem, so a concurrent reader observes either
  the old state (absent) or the complete new file, never a partial write (SR-007, Edge Case
  "Concurrent reads during revocation").
- `os.open(..., 0o600)` sets the mode **at creation time**, closing the window SR-008 explicitly
  calls out ("not readable by other users at any point, including between creation and any
  permission change"). The mode argument to `os.open` is still masked by the process umask, which
  can only *remove* bits, never add them — so `0o600` is an upper bound and the file can never be
  group/world readable. `os.chmod` after the fact would leave exactly the window SR-008 forbids.
- `mode=0o700` on `makedirs` is likewise umask-masked; the follow-up `os.chmod(path, 0o700)`
  handles the case where the directory already existed with looser permissions.
- `os.fsync` on the temp file before `os.replace` ensures the record's bytes are durable before
  the name becomes visible, which is what FR-023 ("survive a stop and start") actually needs.

**Alternatives considered**:
- Single `pastes.json` holding all records: rejected — every create/delete rewrites the whole
  file, one corrupt byte loses every paste (violating FR-024's isolation), and concurrent writers
  need a far heavier lock.
- `sqlite3` (stdlib, so Principle I would permit it): rejected under Principle IV — it brings a
  schema, a connection lifecycle, thread-affinity rules, and WAL files for a key-value lookup by
  opaque id. The spec's scale assumption is "thousands of snippets, not millions"; the filesystem
  is the smaller design. *Note*: sqlite would also make SR-008 harder — the DB file, journal, and
  WAL would each need mode control.
- `shelve`/`pickle`: rejected — `pickle` deserialises arbitrary objects from a file that is, by
  FR-024, allowed to be attacker-influenced garbage. That is a remote-code-execution sink.
- Writing content and metadata to two separate files: rejected — creates a torn-state window that
  `os.replace` otherwise eliminates for free.

---

## R-04: Identifier and revocation-secret generation (SR-001, FR-011)

**Decision**: `secrets.token_urlsafe(16)` for the paste identifier (128 bits of entropy, 22
characters from `[A-Za-z0-9_-]`). `secrets.token_urlsafe(32)` for the revocation secret (256
bits, 43 characters). Both are drawn fresh per paste from the OS CSPRNG; neither derives from
content, time, or a counter.

**Rationale**: `secrets` is the stdlib CSPRNG interface mandated by the constitution's Security
Baseline ("`secrets`, not `random`"). `token_urlsafe` emits base64url, whose alphabet is exactly
the URL-safe unreserved set — so the identifier needs no percent-encoding anywhere in a path
(FR-011) and doubles as the allowlist for path validation (R-07). 16 bytes meets SR-001's
"at least 128 bits" exactly; the delete token gets 32 bytes because it is the sole authorization
credential and costs nothing extra. A 22-character random id makes enumeration of the paste space
infeasible, which is the point of SR-001's "knowing one gives no information about another".

**Collision handling**: with 128 bits the chance of collision is negligible, but FR-011 says
*unique*, so creation uses `O_EXCL` on the record file: if the name already exists, generate a new
identifier and retry (bounded retries, then fail closed with a 500 per SR-010). This makes
uniqueness a property enforced by the filesystem rather than an assumption.

**Alternatives considered**:
- `uuid.uuid4()`: rejected — 122 bits of entropy (below SR-001's 128) and the hyphenated hex form
  is longer and less pleasant in a URL.
- `uuid.uuid1()` / timestamp or counter-based ids: rejected outright — SR-001 forbids derivation
  from time or a counter, and uuid1 leaks the host MAC address.
- `random.choices(...)`: rejected — Mersenne Twister is predictable from observed output.
- Hashing the content to derive the id: rejected — SR-001 forbids deriving from content, and it
  would leak whether two users shared identical text.

---

## R-05: Constant-time secret comparison (SR-002)

**Decision**: `hmac.compare_digest(supplied_token, stored_token)`, with both operands coerced to
`str` of ASCII (both are base64url text, so `compare_digest`'s str path is valid). The comparison
is reached only after the paste has been found and confirmed unexpired (R-08).

**Rationale**: The constitution's Security Baseline names `hmac.compare_digest` directly. A plain
`==` on `str` short-circuits at the first differing character, leaking a timing oracle that lets an
attacker recover the token character by character. `compare_digest` on `str` requires both
arguments to be ASCII-only — base64url always is — and raises `TypeError` otherwise, which we
pre-empt by validating the header value's characters before comparing (SR-004, allowlist-first).

**Alternatives considered**:
- `secrets.compare_digest`: identical function re-exported; `hmac.compare_digest` is the name the
  constitution uses, so we use that for traceability.
- Comparing SHA-256 digests of the two tokens with `==`: rejected — hashing first does defeat the
  prefix oracle, but it is strictly more code than calling the function that already exists, and
  Principle IV prefers fewer moving parts.
- Storing only a hash of the delete token (credential-storage style): considered and rejected —
  the Security Baseline's credential-storage rule targets *passwords*; a 256-bit CSPRNG token has
  no offline-guessing exposure, and SR-008 already guarantees the record file is owner-only.
  Hashing would add a KDF choice and parameters for no attack it actually prevents. Recorded here
  as a deliberate, justified narrowing.

---

## R-06: Request-size bounding (FR-007, FR-027, FR-029, SR-005)

**Decision**: Two-stage limit.
1. **Before reading any body bytes**: require a `Content-Length` header on `POST /pastes`; reject a
   request that omits it, sends a non-integer/negative value, or sends `Transfer-Encoding:
   chunked`, with `400`. If `Content-Length > MAX_BODY_BYTES` (= 65536 + 1024 envelope slack),
   respond `413` immediately and **do not read the body**.
2. **After parsing**: if `len(content.encode("utf-8")) > 65536`, respond `413`.

Reads use `self.rfile.read(content_length)` with the already-validated length, and a short read
(fewer bytes delivered than declared) is a `400`.

**Rationale**: FR-029 and SR-005 require rejecting an oversized submission *without* buffering it,
which is only possible by trusting the declared length as a *rejection* signal (never as a
*trust* signal) before reading. The 1024-byte envelope slack covers `{"content": "...",
"expires_in": N}` plus JSON escaping overhead for a maximal 65,536-byte content; the escaping
caveat is handled in R-10. `413` is checked before JSON validity for an oversized body, satisfying
FR-027's "in preference to any other outcome".

**Connection handling after an early 413**: because the body is deliberately left unread, the
connection cannot be safely reused for a keep-alive follow-up. The 413 response therefore carries
`Connection: close` and the handler sets `close_connection = True`. This is what makes "reject
without buffering" actually safe rather than leaving unread bytes to be misparsed as the next
request (a request-smuggling hazard).

**Known, accepted consequence**: a submission whose *content* is small but whose JSON envelope is
padded past `MAX_BODY_BYTES` with ignored extra fields (FR-009) receives `413` rather than `201`.
This is the correct trade under SR-005 — the alternative is reading an unbounded body to discover
the content was small — and no acceptance scenario or edge case exercises it.

**Alternatives considered**:
- Read the whole body then measure: rejected — directly violates FR-029 and SR-005.
- Stream-parse the JSON incrementally, aborting when content exceeds the limit: rejected — the
  stdlib `json` module has no incremental parser, so this means hand-rolling one (Principle IV).
- Trust `Content-Length` and read without a cap: rejected — a lying `Content-Length` would still
  be bounded by the read call, but an absent one would not; SR-005 names both cases.
- Return `411 Length Required` for a missing `Content-Length`: rejected — the spec enumerates
  exactly four error statuses (400/403/404/413) and classes malformed input as `400`.

---

## R-07: Path containment and identifier validation (SR-003, Edge Case "Identifier that looks like a path")

**Decision**: Layered, allowlist-first, with the filesystem check as a backstop:
1. Split the **raw** request path (from `urllib.parse.urlsplit(self.path).path`, so the query
   string is discarded) on `/` into segments.
2. `urllib.parse.unquote` each segment individually — never the whole path — so a percent-encoded
   separator (`%2F`) becomes a literal `/` *inside* one segment rather than creating a new one.
3. Validate the id segment against `re.fullmatch(r"[A-Za-z0-9_-]{22}", seg)`. Anything else —
   `..`, `/`, a decoded `/`, an absolute path, the empty string, a wrong length — is `404`.
4. Only then build `os.path.join(data_dir, seg + ".json")`, and before opening it confirm
   `os.path.realpath(candidate)` has `os.path.realpath(data_dir) + os.sep` as a prefix (compared
   as resolved absolute paths, not as raw strings).

**Rationale**: SR-003 requires *both* the allowlist check and the post-resolution containment
check, and the ordering matters: validating before the value reaches the path-construction sink is
the Security Baseline's "validate before the value reaches any sink". Step 2's per-segment
unquoting is the subtle one — unquoting the whole path first would let `/pastes/a%2F..%2Fb` turn
into extra path segments and re-enter routing with attacker-chosen structure. Step 4 catches the
case the allowlist cannot: a *validly named* record file that is itself a symlink pointing outside
the data directory (planted by the "foreign files in the data directory" scenario). Since the
allowlist admits only 22 base64url characters, step 4 can never fire on a legitimate request —
it exists purely as defence in depth, exactly as SR-003 spells out.

**Alternatives considered**:
- Allowlist only, no realpath check: rejected — SR-003 mandates the symlink-resolved confirmation
  explicitly, and the symlinked-record case defeats a pure-allowlist design.
- `os.path.normpath`-then-compare: rejected — `normpath` is purely lexical and does not resolve
  symlinks, so it cannot satisfy "after symlink resolution".
- Opening with `O_NOFOLLOW`: considered as an additional hardening; rejected under Principle IV as
  the realpath check already covers the case and `O_NOFOLLOW` only guards the final component.

---

## R-08: Expiry semantics (FR-015, FR-017, FR-018, Edge Case "Expiry exactly now")

**Decision**: Timestamps are captured as `datetime.datetime.now(datetime.UTC).replace(microsecond=0)`
and serialised with `strftime("%Y-%m-%dT%H:%M:%SZ")`. `expires_at` is `created_at + timedelta(seconds=expires_in)`,
or JSON `null` when `expires_in` was absent. A paste is **live** when `expires_at is None or
now <= expires_at` — note the inclusive `<=`. Expiry is evaluated on every request against a
freshly read clock, never cached and never evaluated at startup.

**Rationale**: FR-015 fixes the wire format (`2026-10-23T20:15:00Z`, second precision, trailing
`Z`), so truncating microseconds at capture time means the stored value and the reported value are
the same instant — no rounding discrepancy can make a paste live for a fraction of a second past
what it reported. The inclusive comparison is the direct reading of the edge case "readable up to
and including its expiry instant and non-existent after it". Evaluating per request (rather than
sweeping at startup) is what makes FR-018's restart clause true for free: a paste that expired
while the process was down is simply not live when the next request asks.

`datetime.UTC` is the 3.11+ spelling of `timezone.utc`, which the spec's Python 3.11+ floor
permits.

**Alternatives considered**:
- `time.time()` floats: rejected — float seconds reintroduce sub-second precision and a
  formatting step we would have to truncate anyway.
- `datetime.isoformat()`: rejected — it emits `+00:00`, not the `Z` suffix FR-015 requires, and
  would need post-processing. Explicit `strftime` states the contract directly.
- A background sweeper thread deleting expired records: rejected — the spec's Assumptions say
  expired records may remain on disk and "no background cleanup process is in scope"
  (Principle IV).
- Storing a Unix integer timestamp on disk and formatting on read: rejected — storing the exact
  wire string makes FR-023's "identical creation time and expiry time after restart" trivially
  true by construction, with no re-derivation to get wrong.

---

## R-09: Atomic revocation (SR-007, FR-020, FR-021, Edge Case "Concurrent revocation")

**Decision**: A single module-level `threading.Lock` held by the store across the *entire*
read-record → check-live → compare-token → `os.unlink` sequence. `FileNotFoundError` from the
`unlink` (or from the read) maps to `404`.

**Rationale**: SR-007 requires the secret check and the removal to be atomic *with respect to
concurrent requests* — in a single-process threaded server, one lock around the critical section
is the complete and smallest answer. Without it, two threads could both read the record, one
could fail its token check, and interleaving could still produce a removal not justified by a
successful check. Reads do **not** take the lock: they open the record file independently, and
because removal is a single `unlink` and writes are `os.replace`, a reader either opens the
complete file or gets `FileNotFoundError` → `404`. There is no partial-read window to protect
against, so locking reads would only cost throughput.

Under concurrent correct revocations, exactly one thread's `unlink` succeeds; the loser finds the
record already gone and reports `404` — precisely the documented edge case.

**Alternatives considered**:
- Per-identifier locks in a dict: rejected under Principle IV — it adds a lock registry and its own
  eviction problem for a service whose stated concurrency is "a handful of simultaneous requests".
- `fcntl.flock` on the record file: rejected — POSIX-only, interacts badly with `unlink` (the lock
  dies with the name), and buys cross-process safety the spec never asks for (one service, one
  data directory).
- Lock-free "unlink and inspect the result": rejected — `unlink` returns nothing, so the token
  check could not precede removal atomically, which is the exact failure SR-007 names.

---

## R-10: JSON request validation (FR-005, FR-006, FR-008, FR-009, FR-026, SR-004)

**Decision**: Parse with `json.loads` on the decoded body, then validate in a fixed order, each
failure yielding `400` with a specific message:
1. body decodes as UTF-8 → else `400`
2. `json.loads` succeeds → else `400`
3. result is a `dict` → else `400` (a bare list, number, string, or `null` is rejected)
4. `"content"` key present → else `400`
5. `type(payload["content"]) is str` → else `400`
6. `"expires_in"` absent → `expires_at = None`; otherwise
   `type(payload["expires_in"]) is int` **and** `1 <= value <= 2_592_000` → else `400`
7. `len(content.encode("utf-8")) <= 65536` → else `413`

Keys other than `content` and `expires_in` are never inspected (FR-009).

**Rationale**: `type(x) is int` rather than `isinstance(x, int)` is the load-bearing detail:
`bool` is a subclass of `int` in Python, so `isinstance(True, int)` is `True` and an
`isinstance` check would silently accept `true` as a 1-second lifetime — exactly the behaviour
FR-008 and the edge case "True/false as a lifetime" forbid. The same applies to `content`:
`type(x) is str` rejects `str` subclasses that could carry surprising `__eq__`/`__len__`.
Floats are rejected by the same check, covering FR-008's "fractional numbers" (including `3600.0`,
which JSON gives us as a `float`). Ordering 7 last means an oversized *and* otherwise-valid body
is `413`, while an oversized *and* malformed body is `400` — which is consistent with FR-027's
"for an otherwise valid oversized submission".

This is allowlist validation per SR-004: each field must match a known-good shape, and nothing is
coerced. Principle II forbids best-guess coercion, so `"3600"` (a string) is an error, not a
number.

**Alternatives considered**:
- `isinstance` checks: rejected — the `bool`/`int` subclass trap above.
- A schema library (`jsonschema`): rejected — third-party, forbidden by Principle I.
- `dataclasses` + manual `__post_init__` validation: rejected — the same checks wrapped in a class
  for a two-field payload (Principle IV).
- Accepting `expires_in: null` as "never": rejected — the spec says *absence* means never, and
  Principle II forbids inventing an equivalence the spec did not state.

---

## R-11: Error responses, redaction, and fail-closed behaviour (FR-025, SR-009, SR-010)

**Decision**: One `_send_json_error(status, message)` helper writes
`{"error": "<message>"}` with `Content-Type: application/json; charset=utf-8` and an explicit
`Content-Length`. `BaseHTTPRequestHandler.send_error` is overridden to route through it, so no
default HTML error page can escape. `version_string()` is overridden to return a fixed
`"pastebin"` (suppressing the default `BaseHTTP/0.6 Python/3.x.y` banner), and `log_message` is
overridden to write nothing to stderr. The whole dispatch is wrapped in
`try: ... except Exception: _send_json_error(500, "internal error")`.

**Rationale**: SR-009 forbids disclosing paths, tokens, or stack traces in *any* response, header,
or log line. The stock handler violates this three ways: `send_error` emits an HTML page quoting
the request path, the `Server` header advertises the exact Python version (a version-fingerprinting
gift), and `log_message` prints every request line to stderr. All three are overridden. Messages
are written as fixed literals describing the *rule* that was broken ("expires_in must be an
integer between 1 and 2592000") and never interpolate a stored value, a filename, or the
offending input.

The broad `except Exception` is deliberate and is **not** the swallowing that Principle II
forbids: the exception is *handled meaningfully* — it produces a loud, explicit `500` in the
standard error shape and terminates the request. SR-010 requires exactly this fail-closed
behaviour. Bare `except:` is not used anywhere, and no handler returns a success status on an
error path.

**Alternatives considered**:
- Letting exceptions propagate to `BaseHTTPRequestHandler`'s default handling: rejected — it
  prints a traceback to stderr and can emit a partial/HTML response, violating SR-009 and SR-010.
- Including the offending value in the error message for friendliness: rejected — SR-009's
  "without echoing stored values" and the risk of reflecting attacker content into a JSON body.
- Logging requests to stdout for operability: rejected — stdout carries exactly one contractual
  line (FR-003) and nothing else, and request logging would record identifiers (capability URLs)
  to disk.

---

## R-12: Routing and method dispatch (FR-028, Assumption "Unrecognised action returns not found")

**Decision**: A single explicit route table matched on `(method, parsed path shape)`:

| Method | Path shape | Handler |
|--------|-----------|---------|
| `POST` | `/pastes` | create |
| `GET` | `/pastes/<id>` | read metadata |
| `GET` | `/pastes/<id>/raw` | read raw |
| `DELETE` | `/pastes/<id>` | revoke |

Everything else — unknown prefixes, `GET /pastes`, `POST /pastes/<id>`, `PUT`/`PATCH`/`HEAD` on any
path, `/pastes/<id>/anything-else`, extra trailing segments — is `404` with
`{"error": "not found"}`. `do_GET`, `do_POST`, `do_DELETE` all funnel into one dispatcher; no
`do_*` method is defined for other verbs, and `BaseHTTPRequestHandler`'s "unsupported method"
path is intercepted by the `send_error` override so it too emits the JSON 404 shape.

**Rationale**: FR-028 and the spec's explicit Assumption say an unsupported action on a recognised
address is `404`, not `405` — so no `Allow` header and no method-not-allowed branch exists. A
closed route table is allowlist routing per SR-004: a path is served only if it matches a listed
shape exactly. A trailing slash (`/pastes/<id>/`) produces an empty final segment, matches no row,
and is `404`.

**Alternatives considered**:
- Regex-dispatch over the full path string: rejected — a single regex over an unsplit path is
  where traversal bugs live; segment-wise matching after per-segment unquoting (R-07) is clearer
  and safer.
- Returning `405` with an `Allow` header: rejected — contradicts FR-028 and the spec Assumption.
- Implementing `do_HEAD`: rejected — not in the contract; `HEAD /pastes/<id>` is `404` like any
  other unsupported action.

---

## R-13: Raw content response (FR-014, FR-016, SR-012)

**Decision**: `GET /pastes/<id>/raw` responds `200` with headers
`Content-Type: text/plain; charset=utf-8`, `X-Content-Type-Options: nosniff`, and
`Content-Length: <len(content.encode("utf-8"))>`. The body is `content.encode("utf-8")` written
verbatim — no trailing newline added, no BOM, no escaping.

**Rationale**: FR-014 requires the exact original text as the *entire* body with a UTF-8 plain-text
declaration. SR-012 requires the content be inert and never declared as a type a browser would
render as markup; `text/plain` plus `nosniff` is the pair that actually achieves this — without
`nosniff`, some browsers content-sniff a `text/plain` response containing `<html>` and render it
as HTML, which is the classic stored-XSS-via-sniffing path. Computing `Content-Length` from the
encoded bytes (never from `len(str)`) is what makes FR-016's byte-for-byte round-trip hold for
multi-byte characters.

**Alternatives considered**:
- `application/octet-stream` + `Content-Disposition: attachment`: rejected — FR-014 names
  plain text explicitly, and forcing a download breaks "suitable for piping into a file".
- Omitting `nosniff`: rejected — leaves the sniffing hole SR-012 is written to close.
- `print`-style writing with a newline: rejected — FR-014 says "no added newline" and the
  acceptance scenario checks byte equality.

---

## R-14: CLI argument handling (FR-001, FR-004)

**Decision**: `argparse` with a `serve` subcommand: `--port` (`type=int`, required) and `--data`
(required). Port is range-checked to `0 <= port <= 65535` after parsing. The host is a module
constant `"127.0.0.1"` with **no** flag to change it. Invalid arguments, an unusable data
directory (`OSError` from `makedirs`/`chmod`), and a bind failure (`OSError` from the server
constructor) all print a message to **stderr** and `sys.exit(1)` without printing the readiness
line.

**Rationale**: `argparse` is stdlib and already produces a non-zero exit plus a stderr message for
a missing or non-integer flag, which is FR-004's behaviour for free. Hard-coding the host as a
constant with no flag is the literal requirement of SR-011 ("no option that exposes it on another
interface") — making it unconfigurable is a stronger guarantee than defaulting it. Port `0` is
accepted and the bound ephemeral port is printed (R-02), which keeps FR-003 exactly true and makes
the service testable without port-collision flakiness.

Error messages name the condition and the port or directory *the operator supplied on the command
line* — SR-009's redaction rule governs responses to network callers and logs; echoing back an
argument the operator just typed discloses nothing they do not already know, and Principle II
requires the message be actionable.

**Alternatives considered**:
- Bare `sys.argv` parsing: rejected — reimplements what `argparse` does, with worse errors.
- A `--host` flag defaulting to `127.0.0.1`: rejected — SR-011 forbids the option existing at all.
- Catching `OSError` and continuing with a fallback port or a temp directory: rejected — Principle
  II forbids silent fallbacks; both conditions are fatal.

---

## R-15: Test strategy (Principle III, SC-008)

**Decision**: `pytest` only (test-only dependency, permitted by Principle I's exemption and the
spec's Constraints). A session-scoped-per-test fixture starts the real server in a background
thread on `--port 0` against a `tmp_path` data directory and yields its base URL; tests drive it
over real HTTP with `urllib.request` / `http.client` (stdlib). Every test's name or docstring
names the requirement ids it covers (e.g. `test_create_rejects_bool_expires_in` →
"FR-008, SR-004"), and a `tests/test_requirement_coverage.py` asserts that the union of
referenced ids covers FR-001…FR-029 and SR-001…SR-012.

**Rationale**: Principle III requires an explicit, *discoverable* mapping from requirement id to
test, and SC-008 requires every FR and SR to map to at least one automated test that references it
by identifier. A coverage test that fails when an id goes unreferenced turns that from a
convention into an enforced gate. Driving the real server over a real socket (rather than calling
handler methods directly) is what makes the restart, concurrency, and readiness-line requirements
testable at all — FR-023's restart scenario needs a genuine process/server lifecycle against a
persistent directory.

Restart tests stop the server (`shutdown()` + `server_close()`), start a fresh one against the
same `tmp_path`, and re-read. Startup-failure tests (FR-004: port in use, unusable data directory)
launch `python -m pastebin serve ...` as a real subprocess and assert the exit status, the stderr
message, and the **absence** of the readiness line on stdout.

**Alternatives considered**:
- Calling request handlers directly with mocked `rfile`/`wfile`: rejected — it would not exercise
  binding, the readiness line, threading, or `Content-Length` handling, which is where most of the
  risk is.
- `unittest` only: rejected — the spec's Constraints and the constitution both name `pytest`.
- A third-party HTTP client (`requests`) in tests: rejected — unnecessary even as a test-only
  dependency when `urllib.request` and `http.client` cover every case, including sending a
  deliberately wrong `Content-Length` (which `http.client` allows and `requests` makes awkward).

---

## Resolved unknowns summary

| Technical Context field | Resolution |
|---|---|
| Language/Version | Python 3.11+ (dev target 3.13); `datetime.UTC` requires 3.11 |
| Primary Dependencies | None at runtime (stdlib: `http.server`, `json`, `secrets`, `hmac`, `datetime`, `argparse`, `os`, `re`, `threading`, `urllib.parse`) |
| Storage | One JSON file per paste under the operator-supplied data directory, mode `0600`, atomic `os.replace` |
| Testing | `pytest` (test-only), real server over loopback via stdlib HTTP clients |
| Target Platform | POSIX (Linux/macOS); relies on `os.replace` atomicity and POSIX permission bits |
| Project Type | Single-package CLI-launched HTTP service |
| Performance Goals | None specified; correctness under a handful of concurrent requests (spec Assumptions) |
| Constraints | Content ≤ 65,536 encoded bytes; `expires_in` ∈ [1, 2 592 000]; loopback-only; bounded memory per request |
| Scale/Scope | Thousands of pastes, single operator, no listing/enumeration |

**No NEEDS CLARIFICATION markers remain.**
