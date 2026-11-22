# Implementation Plan: Burn After Reading and Password Protection

**Branch**: `002-burn-after-reading-password` | **Date**: 2026-11-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-burn-after-reading-password/spec.md`

## Summary

Add two independent, optional creation options to the existing pastebin service — `burn_after_reading`
(the first successful read serves the paste and destroys it) and `password` (reads require the
`X-Paste-Password` header) — and report both states as `burn_after_reading` and `protected` in the
JSON read body. Nothing the service does today may change (FR-039, FR-058, FR-060).

Technical approach, in one paragraph: both options are stored as additional *optional* keys inside
the existing `version: 1` record, so records written by the previous version keep loading with the
new fields defaulting to "not one-time, not protected" and no migration step exists (R-017).
One-time consumption is claimed with a single `os.unlink` of the record — the loser of a race gets
`FileNotFoundError` and answers `404` — which gives "at most one successful read" with no lock, no
index, and no new storage state, matching the service's existing lockless concurrency model (R-015).
The password is stored only as a per-paste random salt plus a `hashlib.pbkdf2_hmac`
derivation of it, compared with `secrets.compare_digest`, so the storage directory never holds a
recoverable password and comparison leaks nothing through timing (R-016). No new routes, no new
modules: the change is confined to `src/pastebin/storage.py` and `src/pastebin/server.py`, plus new
test modules.

## Technical Context

**Language/Version**: Python 3.11+ (`requires-python = ">=3.11"`; no feature newer than 3.11 used)

**Primary Dependencies**: none at runtime — standard library only (`http.server`, `json`, `hashlib`,
`secrets`, `os`). `pytest` for tests only, already declared under `[project.optional-dependencies] dev`.

**Storage**: one JSON file per paste, `<id>.json`, in the `--data` directory. Record stays at
`version: 1`, extended with three optional keys (`burn_after_reading`, `password_salt`,
`password_hash`). No index, no lock file, no sweeper.

**Testing**: `pytest`, extending the existing suite in `tests/`. Two existing fixtures are reused —
`service` (in-process `ThreadingHTTPServer`) for request/response behaviour and `launch` /
`in_process_factory` for restart durability.

**Target Platform**: Linux/POSIX, loopback only (`127.0.0.1`). The one-time claim relies on POSIX
`unlink` semantics (exactly one caller succeeds); documented as a platform constraint in R-015.

**Project Type**: single-package HTTP service with a CLI entry point (`python -m pastebin serve`).

**Performance Goals**: unchanged from feature 001 — a handful of concurrent requests, thousands of
pastes. New cost: one PBKDF2 derivation (~40 ms, measured) per read of a *protected* paste.
Unprotected reads are unaffected. Deliberate: the derivation cost is what makes an exposed
storage directory useless (R-016).

**Constraints**: no runtime dependency may be added; existing status codes, response bodies, and
on-the-wire field names must not change; `404` must precede `403`, and `403` must precede
consumption; a refused read must consume nothing.

**Scale/Scope**: ~28 new functional requirements (FR-033…FR-060), two files changed, no new module.
SC-012's concurrency bar (200 pastes × 10 simultaneous reads) is the load the design is sized for.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate (constitution v1.0.0) | Status | Evidence |
|---|---|---|
| **I. Standard Library Only** — no runtime third-party import | PASS | New imports are `hashlib` only; `pyproject.toml` `dependencies = []` is unchanged. KDF, timing-safe compare, and the atomic claim are all stdlib (R-015, R-016). |
| **II. Fail Loudly** — specific diagnostic, no coercion, no silent sentinel | PASS | Every new rejection raises the existing `_Rejected` with a message naming the field and what was wrong (V-11…V-14). A duplicated `X-Paste-Password` is **refused**, not resolved by picking one occurrence (FR-041). A record whose new fields are malformed raises `_BadRecord`, is reported on stderr, and is skipped (S-10). No new `except Exception: pass`. |
| **III. Every Requirement Is Testable (NON-NEGOTIABLE)** | PASS | FR-033…FR-060 each map to at least one named `pytest` test; the traceability table lives in [quickstart.md](./quickstart.md) and the test names carry the FR id, as the existing suite already does. Error paths (400/403/404) each get their own test. |
| **IV. Simplicity** — smallest design, no speculative structure | PASS | No new module, no new class, no new route, no config knob. The one-time claim reuses the directory as the only state (no lock, no index, no "consumed" marker). KDF parameters are module constants rather than per-record fields — the rejected alternative and its cost are recorded in R-016. |
| **Additional Constraints** — Python ≥3.11, stderr/stdout separation, exit statuses, no hidden state | PASS | No change to the CLI, to stream discipline, or to exit statuses. No new state file: S-9 keeps "the directory contents are the whole truth". |

**Gate result: PASS, no violations to justify.** Complexity Tracking below is therefore empty.

**Post-Phase-1 re-check**: re-evaluated after `data-model.md` and `contracts/` were written — still
PASS. The design added no abstraction, no module, and no runtime import beyond `hashlib`; the one
place it was tempted to generalise (a `kdf` discriminator field in the record, for parameter changes
no requirement asks for) was rejected under Principle IV and the consequence written down (R-016).

## Project Structure

### Documentation (this feature)

```text
specs/002-burn-after-reading-password/
├── plan.md              # This file
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md          # Phase 1 output — validation scenarios + FR traceability
├── contracts/
│   └── http-api.md        # Phase 1 output — delta against 001's contract
├── checklists/
│   └── requirements.md    # pre-existing (from /speckit-specify)
└── tasks.md              # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/pastebin/
├── __init__.py        # unchanged
├── __main__.py        # unchanged
├── cli.py             # unchanged — no new argument, no new startup behaviour
├── server.py          # CHANGED: new-field validation, password gate, consume-then-serve
└── storage.py         # CHANGED: Paste fields, record read/write, hashing, atomic consume

tests/
├── conftest.py        # CHANGED: optional password argument on read helpers; legacy-record writer
├── test_create.py     # unchanged
├── test_read.py       # unchanged
├── test_delete.py     # unchanged
├── test_expiry.py     # unchanged
├── test_routing.py    # unchanged
├── test_storage.py    # unchanged
├── test_cli.py        # unchanged
├── test_burn.py       # NEW: FR-033/034, FR-047…FR-053, SC-011, SC-012
├── test_password.py   # NEW: FR-035/036, FR-040…FR-046, SC-013, SC-014, SC-019, SC-020
└── test_compat.py     # NEW: FR-037/038/039, FR-054…FR-059, SC-015, SC-017, SC-018
```

**Structure Decision**: the existing single-package layout (`src/pastebin/` with two substantive
modules plus a CLI) is kept exactly as it is. The feature adds no module and no package level:
storage concerns (record fields, hashing, the atomic claim) go in `storage.py`, HTTP concerns
(validation, header handling, status ordering) go in `server.py`, which is the split already in
place. Three new test modules are added rather than growing the existing ones, so that
"the existing test suite passes unmodified" (SC-017) stays literally checkable — the only edit to a
pre-existing test file is the additive helper change in `conftest.py`, which no existing test's
behaviour depends on.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.
