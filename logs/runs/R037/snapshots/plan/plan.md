# Implementation Plan: Pastebin Service

**Branch**: `001-pastebin-service` | **Date**: 2026-11-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-pastebin-service/spec.md`

## Summary

A loopback-only HTTP service for sharing text snippets, run as
`python -m pastebin serve --port PORT --data DIR`. Four routes: create a paste
(`POST /pastes`), read it as JSON (`GET /pastes/<id>`), read its content as plain text
(`GET /pastes/<id>/raw`), and delete it with a per-paste token (`DELETE /pastes/<id>`). Pastes
optionally expire; an expired or deleted paste is indistinguishable from one that never
existed.

**Technical approach** (from [research.md](./research.md)): `http.server.ThreadingHTTPServer`
with a single `BaseHTTPRequestHandler` subclass handles concurrency (R-001); the readiness line
is printed after bind/listen but before `serve_forever` so a request sent immediately after it
is queued rather than refused (R-002). Persistence is one JSON file per paste named `<id>.json`
in the data directory, created with `O_CREAT|O_EXCL` to guarantee identifier uniqueness and
published with `fsync` + `os.replace` so a partially written record is never served (R-006).
There is no in-memory index and no lock — filesystem atomicity provides the concurrency
guarantees (R-008). Identifiers and delete tokens come from `secrets.token_urlsafe` (R-004),
tokens are compared with `secrets.compare_digest` (R-005), and identifiers are allow-listed
against `^[A-Za-z0-9_-]{1,64}$` before any filesystem access so path traversal is
unrepresentable (R-007). Oversized requests are refused on `Content-Length` before the body is
read, with a 1 MiB ceiling chosen so that JSON escaping can never make a legal 65,536-byte
paste look too large (R-003).

## Technical Context

**Language/Version**: Python 3.11+ (CPython). No feature newer than 3.11 is used.

**Primary Dependencies**: none at runtime — standard library only (`argparse`, `http.server`,
`socketserver`, `json`, `secrets`, `os`, `sys`, `datetime`, `re`, `urllib.parse`, `traceback`).
`pytest` is a development dependency, never imported by runtime code.

**Storage**: filesystem. One JSON record per paste (`<id>.json`) under the operator-supplied
`--data DIR`; atomic publish via temp file + `fsync` + `os.replace`. See
[data-model.md](./data-model.md).

**Testing**: `pytest`, with `pythonpath = ["src"]` in `pyproject.toml`. Two fixtures: an
in-process `ThreadingHTTPServer` on port `0` for API behaviour, and a `subprocess` launch of
`python -m pastebin` for CLI, readiness, exit-status, and restart-durability requirements
(R-014).

**Target Platform**: Linux (and any POSIX host with CPython 3.11+); loopback `127.0.0.1` only.
No Windows-specific or POSIX-only syscalls beyond `os.replace`/`os.fsync`, which are portable.

**Project Type**: single-project CLI-launched HTTP service, package `pastebin` under `src/`.

**Performance Goals**: not a stated requirement. The design must comfortably serve a handful of
concurrent requests and thousands of pastes (spec Assumptions: "thousands — not millions").
Reads are a single `open`; there is no startup cost proportional to paste count beyond the
one-pass FR-032 report scan.

**Constraints**:
- Content limit 65,536 UTF-8 bytes inclusive; request payload ceiling 1,048,576 bytes enforced
  before the body is read (FR-005, FR-024).
- `expires_in` integer `1…2_592_000`; timestamps whole-second UTC rendered `...Z` (FR-006,
  FR-010).
- `404` takes precedence over `403`; no response discloses whether an identifier exists
  (FR-021).
- Never read or write outside `DIR`, whatever the requested identifier contains (FR-023).
- stdout carries only the readiness line; all diagnostics go to stderr (FR-030).
- No runtime third-party imports, no hidden state files, no silent failure paths
  (Constitution I, II).

**Scale/Scope**: ~4 runtime modules, 4 HTTP routes, 1 entity, 32 functional requirements, 10
success criteria. Expected ~600–900 lines of runtime code and a test suite covering every
FR id.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v1.0.0.

| Principle | Gate | Initial (pre-research) | Post-design (Phase 1) |
|---|---|---|---|
| **I. Standard Library Only** | No third-party runtime import; any missing capability built in-project or dropped | **PASS** — spec fixes stdlib-only; `http.server` covers the whole HTTP need | **PASS** — final module list imports only stdlib; `pytest` is dev-only and not imported by `src/pastebin/**` |
| **II. Fail Loudly** | Specific diagnostic naming the bad input; CLI → stderr + non-zero; no bare `except`, no `except Exception: pass`; no coercion of questionable input | **PASS** — FR-022 and FR-029 already require specific messages and non-zero exits | **PASS** — R-013 fixes exit `2` + `pastebin: <message>` on stderr for every startup failure; R-010 routes every error through one JSON `{"error": ...}` helper; R-011 converts an unexpected exception into a reported stderr traceback plus an explicit error response (the "convert into a reported error" case, not a swallow); R-007 refuses a malformed identifier instead of sanitising it |
| **III. Every Requirement Is Testable** (NON-NEGOTIABLE) | Every FR maps to ≥1 pytest test, discoverably; every error path has its own test | **PASS** — SC-002 already demands requirement-naming tests | **PASS** — R-014 fixes the mapping mechanism: FR id in each test name plus a traceability table in `tests/README.md`; the two fixtures make process-level requirements (FR-025…FR-032) testable rather than aspirational |
| **IV. Simplicity** | Smallest design that satisfies the spec; no speculative extension points; functions and plain data over hierarchies; one obvious module over decorative layering | **PASS** | **PASS with justified structure** — see Structure Decision and the notes below |

### Principle IV notes (design decisions that could have gone bigger, and did not)

- **No `sqlite3`, no index, no cache.** One file per paste means a read is one `open` of a known
  path; there is nothing to rebuild at startup and nothing to keep in sync (R-006, R-008).
- **No lock and no background expiry sweeper.** Atomic rename plus access-time expiry
  evaluation gives the required concurrency and expiry behaviour with no extra moving parts
  (R-008, R-009).
- **No abstraction layers.** One frozen `dataclass` (`Paste`) as plain data, module-level
  functions for storage, one `BaseHTTPRequestHandler` subclass because the stdlib's API
  requires a class. No repository interface, no service object, no handler registry — nothing
  with a single implementation behind it.
- **Four modules, not one and not eight.** Justified below; each boundary is a different
  testable concern, not a layer added to look organized.

**Result: all gates pass. Complexity Tracking is empty — there are no violations to justify.**

## Project Structure

### Documentation (this feature)

```text
specs/001-pastebin-service/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature specification
├── research.md           # Phase 0 output — 14 resolved decisions (R-001…R-014)
├── data-model.md         # Phase 1 output — Paste, storage directory, delete token
├── quickstart.md         # Phase 1 output — run + 7 validation scenarios
├── contracts/            # Phase 1 output
│   ├── http-api.md       #   the four routes, status codes, error shapes
│   └── cli.md            #   invocation, readiness line, streams, exit statuses
├── checklists/
│   └── requirements.md   # Pre-existing spec quality checklist
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml                  # pytest config (pythonpath=["src"]); no runtime deps

src/
└── pastebin/
    ├── __init__.py             # package marker; version constant only
    ├── __main__.py             # `python -m pastebin` entry: sys.exit(cli.main(sys.argv[1:]))
    ├── cli.py                  # argparse, --port/--data validation, dir creation + write
    │                           #   probe, FR-032 startup scan, server construction,
    │                           #   readiness line, stderr diagnostics, exit codes
    ├── storage.py              # Paste dataclass; create/load/delete; id + token generation;
    │                           #   id allow-list; atomic write; expiry evaluation
    └── server.py               # request handler: routing, body-size and JSON validation,
                                #   JSON/raw/no-content responses, single error helper

tests/
├── README.md                   # FR-001…FR-032 → test traceability table (Constitution III)
├── conftest.py                 # in-process server fixture + subprocess server fixture,
│                               #   tmp_path data dirs, free-port helper, HTTP client helper
├── test_create.py              # FR-001…FR-008, FR-024 (creation, validation, limits)
├── test_read.py                # FR-009…FR-012 (JSON + raw reads, timestamps, fidelity)
├── test_delete.py              # FR-013…FR-016, FR-021 (token auth, 404-over-403)
├── test_expiry.py              # FR-017…FR-019 (lifetimes, boundary, restart-spanning)
├── test_routing.py             # FR-020, FR-022, FR-023 (catch-all 404s, error shape, traversal)
├── test_storage.py             # FR-002, FR-028, FR-031, FR-032 (atomicity, uniqueness, bad entries)
└── test_cli.py                 # FR-025…FR-030 (invocation, readiness, restart, exits, streams)
```

**Structure Decision**: single project, package `pastebin` under `src/`, as the spec fixes
(`python -m pastebin` with `src/` on `PYTHONPATH`). The template's `models/`, `services/`,
`cli/`, `lib/` sub-packages are deliberately **not** used — four single-purpose modules of a few
hundred lines each need no internal layering, and empty package directories would be exactly
the "layering that exists only to look organized" Principle IV forbids. Tests are split by
requirement group rather than by the `contract/`/`integration/`/`unit/` triad, because
Constitution III cares that each FR id is findable, which a per-requirement-group split makes
direct.

The four-module split is the smallest one that keeps each boundary independently testable, as
Principle IV requires justification for any structure beyond the simplest:

| Module | Concrete requirement forcing a separate module |
|---|---|
| `cli.py` | FR-025…FR-030 are process-level (argument validation, readiness ordering, exit codes, stream discipline) and must be testable without issuing an HTTP request |
| `storage.py` | FR-002, FR-023, FR-028, FR-031, FR-032 are filesystem properties (uniqueness, containment, atomicity, bad-record tolerance) and must be testable without an HTTP server |
| `server.py` | FR-001…FR-024 are request/response properties and must be testable against a server with no subprocess and no CLI parsing |
| `__main__.py` | Required by the fixed `python -m pastebin` invocation; contains the entry call only |

A single-module alternative was considered and rejected: it would force every storage and
argument-validation test through an HTTP request, which makes the FR-028/FR-032 tests slower and
less direct, not simpler.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. All four constitution gates pass both pre-research and post-design; every
structural choice above is either fixed by the specification or carries its Principle IV
justification inline.

## Phase Status

| Phase | Status | Artifacts |
|---|---|---|
| 0 — Outline & Research | **Complete** | [research.md](./research.md) — R-001…R-014, no `NEEDS CLARIFICATION` remaining |
| 1 — Design & Contracts | **Complete** | [data-model.md](./data-model.md), [contracts/http-api.md](./contracts/http-api.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md) |
| 2 — Tasks | Not started | `tasks.md` via `/speckit-tasks` |
