# Implementation Plan: Command-Line Bookmark Manager

**Branch**: `001-bookmark-cli-manager` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-bookmark-cli-manager/spec.md`

## Summary

A single-user CLI that stores web bookmarks in one SQLite file and exposes five commands —
`add`, `list`, `search`, `delete`, `export` — through `python -m bookmarks [--db PATH]
COMMAND ...`. Capture prints the new bookmark's id; recall prints tab-separated lines; search
matches title or URL case-insensitively; delete reports an absent id with exit status 3; export
emits CSV or JSON on stdout.

Technical approach: one table (`bookmarks`) with an `AUTOINCREMENT` id so ids are never reused,
tags stored pre-normalised and alphabetically comma-joined so the stored value is the displayed
value, all reads performed as a single `ORDER BY id` select with filtering in Python (avoiding
SQL `LIKE` wildcard hazards), and input validated before the store is opened so a rejected
command cannot create or alter the file. Runtime code imports only `argparse`, `sqlite3`,
`csv`, `json` and `sys`; `pytest` is the sole development dependency. See
[research.md](./research.md) for each decision and the alternatives rejected.

## Technical Context

**Language/Version**: Python 3.11+ (declared minimum 3.11; local interpreter 3.13.17). No
syntax or library feature newer than 3.11 is used.

**Primary Dependencies**: none at runtime — standard library only (`argparse`, `sqlite3`,
`csv`, `json`, `sys`). Development: `pytest` (9.1.1 available locally).

**Storage**: a single SQLite database file; path from `--db PATH`, default `bookmarks.db` in
the current working directory, created on first use with no initialisation step.

**Testing**: `pytest`, run as `pytest` from the repository root. Unit tests call the public
functions in-process; end-to-end tests run `python -m bookmarks` in a subprocess against a
`tmp_path` store to observe real exit statuses and stream separation.

**Target Platform**: any OS with CPython 3.11+ (developed and verified on Linux); terminal /
script invocation, no network access.

**Project Type**: single-package command-line tool (`bookmarks` package under `src/`) plus a
test suite.

**Performance Goals**: `list`, `search` and `export` over 1,000 bookmarks each complete in
under 1 second end-to-end, including interpreter start-up (SC-005).

**Constraints**: standard library only at runtime (constitution Principle I); no network
access; no writes outside the caller-supplied store path; no implicit global mutable state; a
failed command leaves the store byte-identical (FR-006, SC-007); exit statuses 2 and 3 carry
the fixed meanings in FR-009 and FR-018.

**Scale/Scope**: single user, one invocation at a time, no concurrent access; collections of
thousands of bookmarks; 23 functional requirements; five commands; ~250 lines of runtime code.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0 (ratified 2026-11-14), four principles.

| Gate | Requirement | Pre-Phase-0 | Post-Phase-1 |
|------|-------------|-------------|--------------|
| **I. Standard Library Only** (NON-NEGOTIABLE) | No third-party runtime import; runs on bare CPython 3.11+; `pytest` is the only dev dependency and is never imported by runtime code | **PASS** — spec already constrains the tool to the stdlib; `sqlite3`, `argparse`, `csv`, `json` cover every requirement | **PASS** — final module list (`cli.py`, `storage.py`, `__main__.py`) imports only `argparse`, `csv`, `json`, `sqlite3`, `sys`; `pytest` appears solely under `tests/` |
| **II. Fail Loudly** | Specific diagnostic naming the problem on stderr + non-zero exit; no bare `except`, no `except Exception: pass`; no silent fallbacks or masked defaults | **PASS** — FR-006 and FR-009/FR-018/FR-021 already demand named diagnostics and documented statuses | **PASS** — exit-code table in [contracts/cli.md](./contracts/cli.md) assigns a documented status and a named message to every failure path; the only `except` clauses catch `sqlite3.Error`/`OSError` to re-report with the store path and convert to exit 1, which the principle permits explicitly; validation precedes the store open so no rejected command half-writes (D4) |
| **III. Every Requirement Is Testable** | Every FR maps to ≥1 `pytest` test whose name or docstring names it; error paths tested; full suite green | **PASS** — all 23 FRs are observable through stdout, stderr, exit status or a later invocation's listing; SC-004 already requires this mapping | **PASS** — the Testing Strategy table below maps every FR-001…FR-023 to a test module, including all four error paths (exit 2, exit 3, bad format, unopenable store) |
| **IV. Simplicity** | Smallest design that satisfies the spec; no speculative extension points; plain functions and data; one module until a reason to split; any extra structure justified by the requirement forcing it | **PASS** — no abstraction layers, plugin points, config file, or ORM planned | **PASS** — one table (not three: D2), no classes beyond one 3-line `ArgumentParser` subclass forced by FR-009's reserved exit code (D5), rows passed as `sqlite3.Row`/tuples rather than model objects, two runtime modules justified under Structure Decision |

**Gate result**: PASS at both checkpoints. The Complexity Tracking table below is empty — no
violation requires justification. No constitution amendment is needed; in particular the plan
introduces no third-party runtime dependency, so the Principle I rejection rule in the
Development Workflow does not apply.

## Project Structure

### Documentation (this feature)

```text
specs/001-bookmark-cli-manager/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — design decisions D1–D9
├── data-model.md        # Phase 1 output — entities, schema, validation, lifecycle
├── quickstart.md        # Phase 1 output — runnable validation scenarios
├── contracts/           # Phase 1 output
│   ├── cli.md           #   command surface, arguments, exit statuses
│   └── output-formats.md#   TSV line format, CSV export, JSON export
├── checklists/          # Existing quality checklists
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml                 # pytest config only: pythonpath = ["src"], testpaths = ["tests"]
src/
└── bookmarks/
    ├── __init__.py            # empty marker (no re-exports, no package-level state)
    ├── __main__.py            # `python -m bookmarks` entry: raise SystemExit(main())
    ├── cli.py                 # argparse setup, command dispatch, formatting, exit statuses
    └── storage.py             # schema, connection lifecycle, add/list/delete queries
tests/
├── test_add.py                # FR-007…FR-011, FR-023 (add, ids, URL rejection, tag parsing)
├── test_list_search.py        # FR-012…FR-016 (ordering, tag filter, case-insensitive search)
├── test_delete.py             # FR-017, FR-018 (removal, absent id → exit 3, id not reused)
├── test_export.py             # FR-019…FR-022 (CSV, JSON, bad format, empty store)
├── test_cli.py                # FR-001…FR-006 (invocation, --db default, persistence, errors)
└── conftest.py                # fixtures: tmp store path, in-process and subprocess runners
```

**Structure Decision**: single project, source under `src/bookmarks/` and tests under `tests/`,
as the specification fixes (package `bookmarks` under `src/`, runnable as `python -m
bookmarks`). The template's `models/`, `services/`, `lib/` subdivision is deliberately not used:
at ~250 lines it would be the "abstraction layers added for anticipated future needs" that
Principle IV forbids.

Two runtime modules rather than one, plus a three-line `__main__.py`:

- `__main__.py` is required by the specified invocation `python -m bookmarks`; it contains only
  the `SystemExit(main())` call so that importing the package during tests executes nothing.
- The `cli.py` / `storage.py` split is drawn along the one seam the requirements already force:
  FR-004 (persistence across invocations) and FR-008 (ids never reused) are properties of the
  store that must be verified without a process boundary or stdout parsing, while FR-015 and
  FR-019/FR-020 are properties of formatting that must be verified without a database. Each
  module stays under ~130 lines and neither imports the other's concerns (`storage.py` never
  touches `sys.stdout`; `cli.py` issues no SQL). No further splitting is planned.

## Testing Strategy

Per Principle III each test names the requirement it covers in its name or docstring (e.g.
`def test_add_rejects_non_http_url_with_status_2():  """FR-009"""`). Coverage map:

| Requirement | Covering test module | Observable checked |
|-------------|---------------------|--------------------|
| FR-001 | `test_cli.py` | each of the five commands dispatches via `python -m bookmarks` |
| FR-002 | `test_cli.py` | `--db PATH` used; default `bookmarks.db` in cwd when omitted |
| FR-003 | `test_cli.py` | first command on a non-existent path succeeds, file now exists |
| FR-004 | `test_cli.py` | add in one subprocess, list in another, same store |
| FR-005 | all modules | exit status 0 asserted on every success path |
| FR-006 | `test_cli.py`, `test_add.py`, `test_delete.py`, `test_export.py` | stderr non-empty, stdout empty, status non-zero, listing unchanged (SC-007) |
| FR-007 | `test_add.py` | stdout is exactly the id and nothing else |
| FR-008 | `test_add.py`, `test_delete.py` | ids 1,2,…; after deleting the highest id the next add exceeds it |
| FR-009 | `test_add.py` | `ftp://`, bare domain, empty string, `HTTP://` → status 2, store unchanged |
| FR-010 | `test_add.py` | omitted `--title` lists as an empty field |
| FR-011 | `test_add.py` | ` python , , cli, python ` → `cli,python` |
| FR-012 | `test_list_search.py` | all rows, ascending id |
| FR-013 | `test_list_search.py` | `--tag docs` exact match; `--tag doc` matches nothing |
| FR-014 | `test_list_search.py` | `PYTHON` matches `Python docs`; URL-only match; different casing |
| FR-015 | `test_list_search.py` | four tab-separated fields; two trailing empty fields |
| FR-016 | `test_list_search.py` | empty output, status 0 |
| FR-017 | `test_delete.py` | target gone, others untouched, status 0 |
| FR-018 | `test_delete.py` | absent id → stderr names the id, status 3, nothing deleted |
| FR-019 | `test_export.py` | exact header, row order, alphabetical tags, `csv.reader` round-trip of values containing `,`/`"`/newline |
| FR-020 | `test_export.py` | `json.loads` gives objects with `id` as a number and `tags` as a sorted array |
| FR-021 | `test_export.py` | `--format xml` → stderr, non-zero status |
| FR-022 | `test_export.py` | empty store: header only / `[]`, both status 0 |
| FR-023 | `test_add.py`, `test_export.py` | non-ASCII and mixed-case text reproduced byte-identically in TSV, CSV and JSON |

Non-functional checks: SC-005 is validated by the timed 1,000-bookmark scenario in
[quickstart.md](./quickstart.md) rather than by a wall-clock assertion in the suite, so test
runs stay deterministic on shared hardware.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. Both Constitution Check passes are clean, so this table is intentionally empty.
