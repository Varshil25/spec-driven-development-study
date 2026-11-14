# Implementation Plan: Pastebin Service

**Branch**: `001-pastebin-service` | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-pastebin-service/spec.md`

## Summary

A loopback-only HTTP service for publishing, reading, and withdrawing UTF-8 text snippets, with
optional lifetimes and file-backed durability. Built on Python 3.11+ standard library only:
`http.server.ThreadingHTTPServer` for concurrent request handling, one JSON file per snippet in the
operator-nominated data directory, `os.link`/`os.replace` for all-or-nothing visibility,
`secrets` for unguessable identifiers and delete tokens, and `argparse` for the
`python -m pastebin serve --port PORT --data DIR` entry point. No startup scan of storage, no
request logging, and no background reclamation — expiry is evaluated lazily on each access.

## Technical Context

**Language/Version**: Python 3.11+ (minimum stated once in `README.md`; no module may use a newer feature)

**Primary Dependencies**: None at runtime — standard library only (`http.server`, `socketserver`,
`json`, `pathlib`, `os`, `secrets`, `datetime`, `argparse`, `re`, `sys`). `pytest` is a
development-only dependency, declared in `requirements-dev.txt` and never imported by runtime code.

**Storage**: Local filesystem. One JSON file per snippet at `<DIR>/<id>.json`; the directory is the
sole source of truth across restarts and is created on demand. See [data-model.md](./data-model.md).

**Testing**: `pytest`. Every functional requirement is named by at least one test (Constitution
Principle III); see the requirement→test map in [data-model.md](./data-model.md#requirement-to-test-map).

**Target Platform**: Linux/POSIX host, loopback interface (`127.0.0.1`) only. Atomicity relies on
POSIX `rename`/`link` semantics within a single directory (see [research.md](./research.md) R-03).

**Project Type**: Single-package CLI-launched HTTP service (`src/pastebin`, runnable as
`python -m pastebin` with `src/` on the module search path).

**Performance Goals**: Ready and announcing within 2 s against storage holding up to 1,000 snippets
(SC-007 — met trivially because startup performs no storage scan). 10 callers issuing overlapping
publish/read/delete requests all served correctly and without head-of-line blocking (SC-010). No
throughput target is set (spec Assumptions).

**Constraints**:
- Snippet text ≤ 65,536 UTF-8 bytes; lifetime an integer 1…2,592,000 s.
- Request body never read beyond 394,240 bytes regardless of declared length (FR-040; bound derived
  in [research.md](./research.md) R-05).
- Standard output carries exactly one line (`listening on 127.0.0.1:PORT`); standard error carries
  only startup failures and damaged-storage diagnostics (FR-044, SC-009).
- Timestamps ISO 8601 UTC, second precision, trailing `Z`.
- Endpoint paths, methods, `X-Delete-Token` header, JSON field names, and status codes are fixed by
  the spec's Constraints section and reproduced verbatim in [contracts/http-api.md](./contracts/http-api.md).

**Scale/Scope**: Single operator, single host. ~600 lines of runtime code across 4 modules;
44 functional requirements; 4 user stories.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.0.

| Gate | Status (pre-Phase 0) | Status (post-Phase 1) | Evidence |
|------|----------------------|-----------------------|----------|
| **I. Standard Library Only** — no third-party import reachable from an entry point | PASS | PASS | Every module in the Phase 1 design imports only stdlib modules (listed under Primary Dependencies). `pytest` appears solely in `tests/` and `requirements-dev.txt`, separate from runtime requirements. |
| **II. Fail Loudly** — clear diagnostic + explicit failure signal; no sentinels, no bare `except`, no guessing | PASS | PASS | CLI misuse, unbindable port, and unusable storage write a named reason to stderr and exit non-zero (FR-005, FR-006). Every rejected request returns an explicit `{"error": ...}` body with a defined status (FR-032…FR-036). Damaged storage is translated to a 500 plus a stderr diagnostic naming the snippet — a deliberate translation at the point of handling, not a swallow (FR-038/039). Exception handling is enumerated per call site in [research.md](./research.md) R-08: only `FileNotFoundError`, `OSError`, `json.JSONDecodeError`, `UnicodeDecodeError`, and `TimeoutError` are caught, each at the site that handles it. No bare `except:`, no `except Exception: pass`, no coercion of unparseable input (FR-041 ignores declared content type but still requires the body to parse). |
| **III. Every Requirement Is Testable** — each FR mapped to a named `pytest` test | PASS | PASS | All 44 FRs mapped in [data-model.md](./data-model.md#requirement-to-test-map); each test names its FR id in the test name or docstring. Failure modes from Principle II have dedicated tests asserting message and exit status (`tests/test_cli.py`) or status and error body (`tests/test_errors.py`). SC-008 is satisfied by construction of that map. |
| **IV. Simplicity** — smallest design, functions and plain data, no speculative extension points | PASS | PASS | 4 runtime modules (`__init__`, `__main__`, `server`, `store`), no class hierarchy beyond the one `BaseHTTPRequestHandler` subclass the standard library requires, snippets represented as plain `dict`s, no configuration beyond the two required CLI options, no registry/plugin/abstraction layers, no background threads beyond those `ThreadingHTTPServer` creates. The one deviation considered — splitting storage from HTTP into two modules — is forced by a present requirement (Principle III: storage-corruption and atomicity behaviour must be testable without a live socket) and is recorded in [research.md](./research.md) R-09. |

**Result**: No violations. Complexity Tracking is empty.

**Technology constraints check**: `argparse` for the command line, `json` for serialization,
`pathlib` for paths, plain `stderr` writes for diagnostics, `pytest` as the only development tool —
all as the constitution's Technology and Dependency Constraints section prescribes. `logging` is
deliberately not used: FR-044 forbids per-request output, and a logger configured to emit nothing
would be a knob with no caller (Principle IV).

## Project Structure

### Documentation (this feature)

```text
specs/001-pastebin-service/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── http-api.md      #   HTTP surface: paths, methods, bodies, statuses
│   ├── cli.md           #   Command line, stdout/stderr, exit statuses
│   └── storage.md       #   On-disk record format (the restart contract)
├── checklists/
│   └── requirements.md  # Existing spec-quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
README.md                  # States Python 3.11+ minimum and how to run (constitution requirement)
pytest.ini                 # pythonpath = src, so tests import pastebin without installation
requirements-dev.txt       # pytest only; no runtime requirements file exists because there are none

src/
└── pastebin/
    ├── __init__.py        # Package marker; version constant only
    ├── __main__.py        # argparse CLI, storage preparation, bind, ready line, serve_forever
    ├── server.py          # make_server(); request handler: routing, body limits, JSON responses
    └── store.py           # create/read/delete snippet records; atomic writes; expiry evaluation

tests/
├── conftest.py            # in-process server fixture, subprocess server fixture, HTTP client helper
├── test_cli.py            # FR-001..FR-006, FR-044: argument validation, ready line, bind failures
├── test_publish.py        # FR-007..FR-016, FR-040, FR-041: POST /pastes accept and reject paths
├── test_read.py           # FR-017..FR-021: GET /pastes/<id> and /raw, round-trip fidelity
├── test_delete.py         # FR-022..FR-026: DELETE, token checks, not-found precedence
├── test_expiry.py         # FR-027, FR-028: lazy expiry across all three access paths
├── test_persistence.py    # FR-029..FR-031: restart durability, permanent deletion
├── test_routing.py        # FR-036: undefined paths and unsupported methods
├── test_errors.py         # FR-032..FR-035, FR-037, FR-039: error body shape and status mapping
├── test_damaged_storage.py# FR-038, FR-039: unreadable records → 500 + stderr, others unaffected
└── test_concurrency.py    # FR-042, FR-043: overlapping requests, slow client, partial-read safety
```

**Structure Decision**: Single Python package under `src/` as the spec's Constraints section
requires (`python -m pastebin` with `src/` on the module search path), with a flat `tests/`
directory beside it. The `models/services/cli/lib` subdivision from the template is rejected: each
of those directories would hold one short module, which Principle IV ("prefer one obvious module
over several indirect ones") forbids. Tests are organised by user story and requirement group rather
than by the template's `contract/integration/unit` split, because nearly every test here drives the
real HTTP surface — the split would put almost everything in one directory and mislabel the rest.

## Complexity Tracking

> No Constitution Check violations. This table is intentionally empty.
