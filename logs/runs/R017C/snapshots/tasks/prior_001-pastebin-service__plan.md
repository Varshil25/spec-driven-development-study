# Implementation Plan: Pastebin Service

**Branch**: `001-pastebin-service` | **Date**: 2026-11-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-pastebin-service/spec.md`

## Summary

A loopback-only HTTP service for sharing text snippets ("pastes"), launched as
`python -m pastebin serve --port PORT --data DIR`. Callers create a paste by POSTing JSON, read it
back as structured data or as plain text, and revoke it with a secret issued at creation. Pastes
may carry a lifetime and survive restarts.

**Technical approach**: a single `ThreadingHTTPServer` with one request handler dispatching over a
closed four-route table, backed by a filesystem store that writes one `0600` JSON record per paste
and replaces it atomically. Identifiers and revocation secrets come from `secrets`; token
comparison is constant-time; expiry is computed per request so no sweeper or startup scan exists.
Every design decision is recorded in [research.md](./research.md); entity and storage rules in
[data-model.md](./data-model.md); the caller- and operator-facing interfaces in
[contracts/](./contracts/).

## Technical Context

**Language/Version**: Python 3.11+ (developed against 3.13). The 3.11 floor is set by the spec's
Constraints and is independently required by `datetime.UTC`.

**Primary Dependencies**: None at runtime — standard library only (Constitution Principle I).
Modules used: `http.server`, `socketserver`, `json`, `secrets`, `hmac`, `datetime`, `argparse`,
`os`, `re`, `threading`, `urllib.parse`, `sys`. `pytest` is a test-only dependency under the
Principle I exemption.

**Storage**: Filesystem. One UTF-8 JSON record per paste at `<data_dir>/<id>.json`, mode `0600`,
inside a `0700` directory; written via `O_EXCL` temp file + `fsync` + `os.replace` (R-03).

**Testing**: `pytest`. Tests drive a real server bound to an ephemeral port over real HTTP using
stdlib clients (`urllib.request`, `http.client`). Startup-failure cases run `python -m pastebin`
as a subprocess (R-15).

**Target Platform**: POSIX (Linux, macOS). Relies on `os.replace` atomicity within a filesystem
and on POSIX permission bits.

**Project Type**: Single-package CLI-launched HTTP service.

**Performance Goals**: None specified. The spec's Assumptions require correctness under "a handful
of simultaneous requests", explicitly not a throughput target.

**Constraints**: `content` ≤ 65 536 encoded bytes; `expires_in` ∈ [1, 2 592 000]; bind `127.0.0.1`
only with no option to change it; memory per request bounded at ~66 KB regardless of what a caller
sends; timestamps at whole-second UTC precision with a `Z` suffix.

**Scale/Scope**: Thousands of pastes, single operator, no listing/enumeration, no editing, no
authentication for reads.

**Unknowns**: none. All NEEDS CLARIFICATION items raised during Technical Context drafting were
resolved in Phase 0 — see the "Resolved unknowns summary" table in [research.md](./research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Assessed against constitution **v1.0.0** (ratified 2026-11-16).

### Initial check (pre-Phase 0) — PASS

| Principle | Assessment | Verdict |
|---|---|---|
| **I. Standard Library Only** | Spec Constraints mandate stdlib-only; `http.server`, `json`, `secrets`, `hmac` cover every need. `pytest` is test-only and declared separately. No exception requested. | PASS |
| **II. Fail Loudly** | Spec enumerates explicit error responses for every rejection (FR-025 … FR-029) and non-zero exit with a stderr message for every startup failure (FR-004). No fallback or coercion is specified anywhere. | PASS |
| **III. Every Requirement Is Testable** | All 29 FRs and 12 SRs are externally observable over HTTP or via process behaviour. SC-008 already requires each to map to a test referencing it by id. | PASS |
| **IV. Simplicity** | Single package, no abstraction layers, no plugin points, no caching, no background workers. Concurrency is the one non-trivial element and is demanded by SR-007 and two Edge Cases, not speculative. | PASS |
| **V. Secure by Default (NON-NEGOTIABLE)** | Spec carries a complete Security Requirements section (SR-001 … SR-012) derived from OWASP Top 10 / ASVS, each testable. Security needs no operator opt-in: loopback binding and `0600` records are the only configuration. | PASS |

**Security Baseline coverage** (each item must be an implemented control or an explicit statement
that the feature does not touch the surface):

| Baseline item | Status | Where |
|---|---|---|
| Untrusted input, allowlist-based, validated before any sink | Controlled | SR-003, SR-004; R-07, R-10 |
| No string-built sinks | Controlled | Paths built only from an allowlist-validated 22-char id; JSON emitted via `json.dumps`, never string-concatenated. No SQL, no shell, no HTML, no XML — the feature invokes no subprocess and renders no markup |
| Path containment (resolve + confirm inside base) | Controlled | SR-003; R-07 |
| Credential storage (slow salted hashes) | **Not applicable, by deliberate narrowing** | The feature stores no passwords. The one stored secret is a 256-bit CSPRNG token with no offline-guessing exposure, protected by `0600` permissions (SR-008). Justified in R-05 |
| Randomness (`secrets`) and constant-time comparison (`hmac.compare_digest`) | Controlled | SR-001, SR-002; R-04, R-05 |
| Resource limits (bound input size, reject rather than buffer) | Controlled | SR-005; R-06. No decompression and no network egress, so expansion-ratio and call-timeout guards do not apply |
| Access control on every operation, server-side, atomic under concurrency | Controlled | SR-006, SR-007; R-09 |
| File permissions, never momentarily readable by others | Controlled | SR-008; R-03 (`os.open` with mode at creation, not `chmod` after) |
| Output redaction | Controlled | SR-009, SR-010; R-11 (overrides `send_error`, `version_string`, `log_message`) |

**Development Workflow gates**: the spec states functional and security requirements together
(satisfied); this plan shows per-requirement verification and the applicable Baseline items (see
*Requirement Verification Map* below); tests ship with the implementation and the full suite must
pass with no skips or xfails.

**Result**: no violations. Complexity Tracking is empty.

### Post-design re-check (after Phase 1) — PASS

Re-assessed against the artifacts actually produced (`research.md`, `data-model.md`,
`contracts/http-api.md`, `contracts/cli.md`, `quickstart.md`).

| Principle | Post-design assessment | Verdict |
|---|---|---|
| **I. Standard Library Only** | The dependency list closed at 13 stdlib modules. Phase 0 explicitly rejected `jsonschema` (R-10) and `requests` (R-15) as third-party, and rejected `sqlite3` on simplicity grounds despite it being permissible. No exception is requested, so no amendment is needed. | PASS |
| **II. Fail Loudly** | Every validation rule in data-model.md maps to a specific status and message; none produces a default, a coercion, or a silent pass. The single broad `except Exception` (R-11) is justified: it is required by SR-010, it *handles* the failure by emitting a loud generic `500` in the standard shape, and it never returns a success status or partial content. No bare `except:` and no `except Exception: pass` appears in the design. | PASS |
| **III. Every Requirement Is Testable** | R-15 fixes the mapping mechanism (requirement ids in test names/docstrings) and adds `tests/test_requirement_coverage.py`, which fails if any FR-001…FR-029 or SR-001…SR-012 is unreferenced. That converts SC-008 from an aspiration into an enforced gate. The Requirement Verification Map below names the test approach for every requirement. | PASS |
| **IV. Simplicity** | Design settled on: one package, one handler class, one store module, one lock, no index, no sweeper, no startup scan, no cache, no `--host` flag. Four alternatives were rejected *specifically* for adding moving parts (sqlite R-03, per-id lock registry R-09, dataclass wrapper R-10, `O_NOFOLLOW` R-07). The three retained non-trivial elements are each forced by a named requirement and are recorded in Complexity Tracking below. | PASS |
| **V. Secure by Default (NON-NEGOTIABLE)** | All twelve SRs have a concrete mechanism and at least one negative test in the plan. Security requires no operator action: the host is an unconfigurable constant (SR-011), permissions are set at creation (SR-008), and redaction is achieved by overriding the stdlib defaults that would otherwise leak (R-11). Two design choices exist *only* for security with no functional driver — the `nosniff` header (SR-012) and the post-resolution containment check (SR-003) — which is the right direction for a secure-by-default feature. | PASS |

**Design decisions that strengthened compliance during Phase 1**, worth flagging because each
closes a hole the naive implementation would have had:

1. `type(x) is int` instead of `isinstance` (R-10) — `isinstance(True, int)` is `True` in Python,
   so an `isinstance` check would have silently accepted `true` as a 1-second lifetime, violating
   FR-008 and the "True/false as a lifetime" edge case.
2. `os.open(..., 0o600)` instead of write-then-`chmod` (R-03) — eliminates the window SR-008
   explicitly forbids.
3. Overriding `version_string()` and `log_message()` (R-11) — the stock
   `BaseHTTPRequestHandler` advertises the Python version in a `Server` header and logs every
   request line to stderr; both are SR-009 violations present by default.
4. `Connection: close` on the early `413` (R-06) — refusing to read the body is only safe if the
   connection is not then reused, otherwise unread bytes could be misparsed as a following request.
5. Per-segment `unquote` rather than whole-path `unquote` (R-07) — decoding the whole path first
   would let `%2F` manufacture new path segments and re-enter routing.

**Result**: no violations introduced by the design. Complexity Tracking below records the three
retained non-trivial elements with their forcing requirements, as Principle IV requires.

## Project Structure

### Documentation (this feature)

```text
specs/001-pastebin-service/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — 15 decisions with alternatives
├── data-model.md        # Phase 1 output — Paste + Paste store
├── quickstart.md        # Phase 1 output — runnable validation scenarios
├── contracts/           # Phase 1 output
│   ├── http-api.md      #   caller-facing HTTP contract
│   └── cli.md           #   operator-facing command-line contract
├── checklists/
│   └── requirements.md  # Spec quality checklist (already complete)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── pastebin/
    ├── __init__.py          # package marker; version constant
    ├── __main__.py          # `python -m pastebin` entry point → cli.main()
    ├── cli.py               # argparse, data-dir setup, bind, readiness line, exit codes
    ├── server.py            # ThreadingHTTPServer + handler: routing, framing, validation, errors
    ├── store.py             # PasteStore: create/read/delete, atomic writes, path containment
    └── models.py            # Paste record shape, validation rules, timestamp formatting

tests/
├── conftest.py              # fixtures: running server on an ephemeral port + tmp_path data dir
├── test_create.py           # FR-005 … FR-011, FR-026, FR-027, SR-004, SR-005
├── test_read.py             # FR-012 … FR-016, SR-012
├── test_expiry.py           # FR-008, FR-015, FR-017, FR-018
├── test_revoke.py           # FR-019 … FR-022, SR-002, SR-006
├── test_persistence.py      # FR-023, FR-024 (restart against the same data directory)
├── test_startup.py          # FR-001 … FR-004, SR-011 (subprocess-based)
├── test_routing.py          # FR-028 (unknown paths, unsupported methods, sub-resources)
├── test_security.py         # SR-001, SR-003, SR-007 … SR-010 (negative tests)
└── test_requirement_coverage.py  # SC-008 gate: every FR/SR referenced by some test

pyproject.toml               # package metadata; ZERO runtime dependencies; pytest under a dev extra
```

**Structure Decision**: Single project, `src/` layout, as mandated by the spec's Constraints
("Code MUST live in a package named `pastebin` under `src/`, runnable as `python -m pastebin` when
`src/` is on `PYTHONPATH`"). The four runtime modules split along the only seams the feature
actually has — command line (`cli`), HTTP (`server`), durability (`store`), and record shape plus
validation (`models`). No `services/`, `lib/`, or `api/` subpackages are created: with roughly
400 lines of runtime code, directory-per-layer would be the speculative structure Principle IV
rejects. Tests are grouped one file per user story or requirement cluster so that a reviewer
looking for a requirement's test can find it from the filename alone (Principle III's
"discoverable" mapping).

## Requirement Verification Map

Constitution Development Workflow: *"Plans MUST show, per requirement, how it will be verified and
which Security Baseline items apply."* `R-nn` references are decisions in
[research.md](./research.md).

### Functional requirements

| Req | Verification approach | Design ref |
|---|---|---|
| FR-001 | Subprocess test: start, assert a connection to `127.0.0.1:PORT` succeeds; assert no other interface is bound | R-14 |
| FR-002 | Start with a nested non-existent `--data`; assert the tree is created and the service is ready | R-03, R-14 |
| FR-003 | Capture stdout; assert it is exactly `listening on 127.0.0.1:<bound port>` and nothing else | R-02 |
| FR-004 | Three subprocess tests (bad args, port in use, unwritable dir): assert non-zero exit, stderr message, and absence of the readiness line | R-14 |
| FR-005 | POST with `content` only and with `content` + `expires_in`; assert `201` | R-10 |
| FR-006 | POST missing `content`, with `content: 5`, and with `content: ""`; assert `400`, `400`, `201` | R-10 |
| FR-007 | POST content of exactly 65 536 and 65 537 encoded bytes; assert `201`, `413`. Include a multi-byte case where char count ≪ byte count | R-06 |
| FR-008 | Table test over `1, 2592000` (accept) and `0, -1, 2592001, 3600.0, "3600", true, false, null` (reject `400`); plus absence ⇒ `expires_at: null` | R-10 |
| FR-009 | POST with extra unknown fields; assert `201` and that they are absent from the read | R-10 |
| FR-010 | Assert `201` body has `id`, `delete_token`, `url == "/pastes/<id>"` | R-04 |
| FR-011 | Create 1 000 pastes; assert all ids unique, 22 chars, match `[A-Za-z0-9_-]`, and need no URL encoding | R-04 |
| FR-012 | Create then GET; assert `200` and all four fields with exact values | — |
| FR-013 | Assert `delete_token` absent from the GET body and from every header | R-11 |
| FR-014 | GET `/raw`; assert `200`, `Content-Type: text/plain; charset=utf-8`, body byte-equal to input with no trailing newline | R-13 |
| FR-015 | Regex-assert `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$` on both timestamps; assert `expires_at is None` for no-lifetime pastes | R-08 |
| FR-016 | Round-trip a fixture containing non-ASCII, emoji, `\n`, `\t`, quotes, and leading/trailing whitespace through both read forms; assert byte equality | R-13 |
| FR-017 | After expiry, assert `404` from GET, GET `/raw`, and DELETE | R-08 |
| FR-018 | Create a 1 s paste, stop the server, sleep past expiry, restart, assert `404` | R-08 |
| FR-019 | DELETE with the correct token; assert `204` and an empty body | R-09 |
| FR-020 | DELETE with no token and with a wrong token; assert `403` and that a subsequent GET still returns the unchanged content | R-05, R-09 |
| FR-021 | DELETE an unknown id and an expired id, each with a wrong token and with no token; assert `404` in all four | R-09 |
| FR-022 | After a successful DELETE, assert `404` from GET, GET `/raw`, and a repeat DELETE with the same correct token | R-09 |
| FR-023 | Create several pastes, stop, restart against the same dir; assert identical `content`/`created_at`/`expires_at` and that the original token still revokes | R-03 |
| FR-024 | Plant a truncated record, a non-JSON record, a JSON array, and a record missing `content`; assert each id reads `404`, the service still starts, and unrelated pastes still read | R-03 |
| FR-025 | Assert every non-2xx response parses as JSON with exactly the key `error` mapping to a non-empty string | R-11 |
| FR-026 | Table test over empty body, invalid JSON, bare list/number/string, missing/non-string `content`, invalid `expires_in`; assert `400` and that nothing was created | R-10 |
| FR-027 | Assert `413` for oversized content, including a body that is oversized *and* otherwise valid (confirming precedence over `400`/`201`) | R-06 |
| FR-028 | Table test over `/`, `/nope`, `GET /pastes`, `POST /pastes/<id>`, `PUT`/`PATCH`/`HEAD` on `/pastes/<id>`, `/pastes/<id>/other`, `/pastes/<id>/`; assert `404` | R-12 |
| FR-029 | Send a 50 MB declared body; assert `413` and that the server's RSS does not grow by the payload size; separately send a `Content-Length` larger than the bytes actually delivered and assert no hang | R-06 |

### Security requirements

| Req | Verification approach (incl. negative test) | Baseline item | Design ref |
|---|---|---|---|
| SR-001 | Create 1 000 pastes; assert all ids and tokens unique, correct length, and from the expected alphabet; assert ≥ 128 bits of entropy by construction; assert no id/token is a function of content or creation time (identical content at different times yields unrelated values) | Randomness | R-04 |
| SR-002 | Assert the implementation calls `hmac.compare_digest` (source-level assertion) and that no `==` comparison of the token exists; functional negative test with a token differing only in the last character | Randomness/comparison | R-05 |
| SR-003 | Table test over `../../etc/passwd`, `..%2F..%2Fetc%2Fpasswd`, `%2Fetc%2Fpasswd`, `/etc/passwd`, `a/../b`, empty, over/under-length ids → all `404`. Plus: plant a symlink named `<valid-id>.json` pointing outside the data dir and assert `404` with no read. Plus: assert nothing outside the dir is created or removed across the whole suite | Path containment | R-07 |
| SR-004 | Negative tests asserting each request element (path segment, method, `Content-Length`, `Transfer-Encoding`, `X-Delete-Token` characters, body shape) is rejected before any filesystem access — verified by asserting the data directory is unchanged after each rejection | Untrusted input | R-07, R-10 |
| SR-005 | 50 MB declared body → `413` without buffering; missing `Content-Length` → `400`; `Transfer-Encoding: chunked` → `400`; `Content-Length` larger than the bytes delivered → `400`, no hang | Resource limits | R-06 |
| SR-006 | Assert the token is re-read from the stored record on every DELETE (a second DELETE after a token-bearing GET still requires the header); assert no cookie, session, or client-supplied claim influences the outcome | Access control | R-09 |
| SR-007 | Spawn N threads issuing the same correct DELETE; assert exactly one `204`, the rest `404`, and no `403`/`500`. Spawn concurrent GETs during a DELETE; assert every response is either the complete paste or `404`, never truncated | Access control | R-09 |
| SR-008 | `os.stat` the data directory → `0o700`; `os.stat` every record → `0o600`. Negative: run under a permissive umask (`0o000`) and assert the modes are still restrictive — this is what catches a write-then-`chmod` implementation | File permissions | R-03 |
| SR-009 | Scan every response body and header across the full suite for the paste's `delete_token`, for any absolute filesystem path, for `Traceback`, and for a Python version string; assert none appear. Assert the `Server` header is the fixed constant | Output redaction | R-11 |
| SR-010 | Inject a failure (e.g. make the data directory unreadable mid-run, or monkeypatch the store to raise); assert `500` with the standard `{"error": ...}` shape, no content, no diagnostics | Output redaction | R-11 |
| SR-011 | Assert the CLI exposes no host option (`--host` is rejected as an unknown argument); assert the bound socket's address is `127.0.0.1`; assert a connection to the host's non-loopback address is refused | Untrusted input / exposure | R-14 |
| SR-012 | Store `<script>alert(1)</script>` and `<html>…`; assert `/raw` returns `text/plain; charset=utf-8` with `X-Content-Type-Options: nosniff`, never `text/html`, and that the content is returned uninterpreted | No string-built sinks | R-13 |

### Success criteria

| Criterion | Verification |
|---|---|
| SC-001 | Round-trip tests under FR-016, including non-ASCII |
| SC-002 | Assert the five outcomes map to five distinct statuses (`201`/`200`/`204`/`400`+`403`+`413`/`404`) distinguishable without reading the message, and every rejection carries a non-empty message |
| SC-003 | FR-017, FR-018, FR-022 tests |
| SC-004 | FR-020 tests |
| SC-005 | FR-023 restart test |
| SC-006 | Connect immediately after reading the readiness line from the subprocess's stdout; assert the request is served, repeated across many iterations to catch a race |
| SC-007 | FR-029 memory-bound test |
| SC-008 | `tests/test_requirement_coverage.py` — fails if any FR or SR id is unreferenced |
| SC-009 | SR-009 suite-wide leakage scan |
| SC-010 | SR-003 traversal table plus a whole-suite assertion that no file outside the data directory was touched |

## Complexity Tracking

> Principle IV requires any complexity that survives review to be justified against the
> requirement that forces it. Three elements qualify; none is a constitution *violation*, but each
> is recorded here because a simpler design exists and was rejected for a stated reason.

| Element | Why needed | Simpler alternative rejected because |
|---|---|---|
| Threaded server (`ThreadingHTTPServer`) rather than single-threaded | SR-007 requires the secret check and removal to be atomic *with respect to concurrent requests*, and two Edge Cases ("Concurrent revocation", "Concurrent reads during revocation") specify behaviour that only exists under concurrency | A single-threaded `HTTPServer` cannot exhibit — and therefore cannot be tested for — the concurrency requirements the spec states. The requirement would be unverifiable, which Principle III treats as unimplemented |
| A `threading.Lock` around check-and-remove | SR-007's atomicity requirement. Without it, two threads can both read a record, one fail its token check, and interleaving can still produce a removal not justified by a successful check | Lock-free "unlink and inspect the result" was rejected: `unlink` returns nothing, so the token check cannot be made to precede removal atomically. A per-identifier lock registry was rejected as strictly more machinery (a dict plus an eviction policy) for a service whose stated concurrency is "a handful of simultaneous requests" |
| Temp-file + `fsync` + `os.replace` instead of a direct write | SR-007 (a concurrent read must never observe a partially written record) and FR-023 (durability across restart) | A direct `open(path, "w")` leaves a window in which a reader sees a truncated file, and leaves the record's bytes in the page cache when the process stops. Both are failures the spec names explicitly |
| An in-flight request counter, waited on (bounded) during shutdown | contracts/cli.md "Shutdown": *"In-flight requests are allowed to complete."* Handler threads are daemons (R-01), so without this the interpreter stops them mid-response | Closing the sockets immediately was rejected because it breaks the stated shutdown clause. Making the threads non-daemonic was rejected because a wedged request would then prevent the process from exiting at all — the opposite failure. The counter is two integers and a `Condition`, and the wait is bounded |
| A 30-second socket timeout on the request handler | SR-005 ("bound the time and memory any single input may consume"): a client that opens a connection and never writes otherwise holds a handler thread forever | Leaving `timeout = None` (the stdlib default) was rejected because it makes thread exhaustion reachable by a caller that sends nothing at all — a resource limit the Security Baseline requires and that no other control covers |

**Not complexity, recorded to pre-empt the question**: the four-module split (`cli`, `server`,
`store`, `models`) is not a layered architecture — each module is one file along a real seam, with
no interfaces, registries, or dependency injection between them. The alternative, a single
~400-line module, was judged no simpler to test or review.
