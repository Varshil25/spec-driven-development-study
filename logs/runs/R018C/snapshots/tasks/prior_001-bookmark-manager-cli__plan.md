# Implementation Plan: Bookmark Manager CLI

**Branch**: `001-bookmark-manager-cli` | **Date**: 2026-11-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-bookmark-manager-cli/spec.md`

## Summary

A single-user command-line bookmark manager, invoked as
`python -m bookmarks [--db PATH] COMMAND ...`, that stores bookmarks in one SQLite file and
offers five commands: `add`, `list`, `search`, `delete`, `export`. Listings and searches emit
four tab-separated fields; exports emit LF-terminated CSV or two-space-indented UTF-8 JSON. Exit
statuses form one complete map — 0 success, 1 unusable store, 2 any user mistake, 3 deleting an
identifier that does not exist.

Technical approach: four flat standard-library modules under `src/bookmarks/`. `argparse`
supplies the command grammar and, by its own default behaviour, every status-2 usage diagnostic
without hand-written validation. Storage is two SQLite tables — `bookmarks` with
`INTEGER PRIMARY KEY AUTOINCREMENT` so identifiers are never reused, and a `tags` join table with
a composite primary key enforcing at-most-once tagging and `ON DELETE CASCADE`. The store is
opened through the `mode=rw` SQLite URI and validated by a read-only query, so an unrecognisable
file is reported and left byte-for-byte unchanged rather than overwritten. Case-insensitive
`search` is filtered in Python rather than with SQL `LIKE`, avoiding both ASCII-only case folding
and wildcard injection from the user's text. All decisions and the experiments confirming them
are recorded in [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.11+ (declared floor; developed and verified on 3.13.17)

**Primary Dependencies**: None. Standard library only — `argparse`, `sqlite3`, `csv`, `json`,
`sys`, `pathlib`. pytest is a development dependency, never imported by shipped code.

**Storage**: One SQLite database file — `--db PATH` when given, otherwise `bookmarks.db` in the
current working directory. Two tables; schema in [data-model.md](./data-model.md).

**Testing**: pytest (9.1.1 available). Contract-level tests invoke the CLI as a subprocess so
real exit statuses and the stdout/stderr split can be asserted; `pythonpath = ["src"]` in
`pyproject.toml` resolves imports with no install step.

**Target Platform**: Any POSIX or Windows system with Python 3.11+; single user, single process,
local filesystem. Developed on Linux.

**Project Type**: Single-project CLI tool with no network, no service, and no UI.

**Performance Goals**: Each command returns in under one second on a 1,000-bookmark store
(SC-007); a 1,000-bookmark store round-trips with every URL, title and tag identical (SC-002).

**Constraints**: Results on stdout, diagnostics on stderr, no partial output on failure; both
streams UTF-8 regardless of locale; CSV lines LF-terminated; JSON two-space indented with
literal non-ASCII and one trailing newline; an unusable store is never overwritten, truncated,
re-initialised or repaired; identifiers never reused.

**Scale/Scope**: Five commands, two entities, four runtime modules, 27 functional requirements.
Thousands of bookmarks in a personal collection. Explicitly out of scope: concurrent access,
multi-user accounts, synchronisation, update/edit, import, archiving page content.

No NEEDS CLARIFICATION items remain — the five clarifications recorded in the spec plus
Phase 0 research resolved every open question.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Gates derive from [the project constitution](../../.specify/memory/constitution.md) v1.0.0.

### Pre-Phase-0 evaluation

| Gate | Source | Status | Evidence |
| ---- | ------ | ------ | -------- |
| Standard library only | Principle I | **PASS** | FR-025 requires it and the user input confirms it; every needed module (`argparse`, `sqlite3`, `csv`, `json`, `sys`) ships with Python. pytest is dev-only and will not be imported by `src/bookmarks/`. |
| Fail loudly | Principle II | **PASS** | FR-003a, FR-007, FR-017 and FR-024 already specify a diagnostic naming what was invalid plus a non-zero status for every failure, and FR-023 forbids partial stdout. The spec requires no silent recovery, coercion or default substitution anywhere. |
| Every requirement testable | Principle III | **PASS** | FR-027 makes per-requirement pytest coverage a requirement of the feature itself; all 27 requirements are observable through stdout, stderr, exit status or store contents. |
| Simplicity | Principle IV | **PASS** | Scope is the five specified commands. The plan rejects the template's `models/services/cli/lib` tree for four flat modules, and adds no index, column or abstraction a requirement does not demand. |
| Declared version floor | Additional Constraints | **PASS** | Python 3.11 declared once, in `pyproject.toml`; no feature newer than 3.11 is used. |
| pytest as the test framework | Additional Constraints | **PASS** | pytest, per user input and constitution. |
| stdout/stderr convention | Additional Constraints | **PASS** | FR-023 and the CLI contract. |
| No hidden global state | Additional Constraints | **PASS** | Behaviour is driven by arguments only. The store path comes from `--db` or a documented default; no environment variable switches behaviour. (`PYTHONPATH` is import resolution, not a behaviour switch.) |

**Result**: all gates pass. No violations, no entries in Complexity Tracking. Proceed to Phase 0.

### Post-Phase-1 re-evaluation

| Gate | Status | Evidence from the design |
| ---- | ------ | ------------------------ |
| Standard library only | **PASS** | Final module list imports `argparse`, `sqlite3`, `csv`, `json`, `sys`, `pathlib` and nothing else (research R-001, R-010). |
| Fail loudly | **PASS** | One `BookmarkError(message, status)` raised at the point of detection and one handler at the entry point, which Principle II permits because it exists only to convert an error into a clearer diagnostic (R-008). Unexpected `sqlite3` faults deliberately propagate rather than being folded into a documented status — a crash is preferred to a wrong answer. The store-open sequence refuses rather than repairs (R-002). |
| Every requirement testable | **PASS** | Exit statuses and stream separation are asserted through subprocess invocation, the only way to observe a real process status (R-009). Quickstart scenarios 1–10 cover every requirement group; the traceability obligation is restated as a done-criterion in [quickstart.md](./quickstart.md). One honest caveat recorded: a permission-denied test cannot pass as `root`, so it must skip itself under `geteuid() == 0` instead of silently appearing to pass (R-002). |
| Simplicity | **PASS** | Four modules, two tables, no extra index, no `formats.py`, no tag-dictionary table, no custom argparse error handler — each alternative considered and rejected in writing (R-003, R-006, R-010). |
| Declared version floor | **PASS** | 3.11 in `pyproject.toml`; nothing in the design needs more. |
| pytest as the test framework | **PASS** | `pythonpath`/`testpaths` configured in `pyproject.toml`; no packaging or install step added (R-009). |
| stdout/stderr convention | **PASS** | Specified byte-for-byte in [contracts/cli-contract.md](./contracts/cli-contract.md). |
| No hidden global state | **PASS** | Stream reconfiguration is the only process-wide mutation, performed once at the entry point and required by FR-023a; it changes encoding, not behaviour. |

**Result**: the design introduces no violation. Complexity Tracking stays empty.

One design consequence is worth flagging to the user rather than burying: because any command may
need to create the store, all commands open it read-write, so a read-only store file fails with
status 1 even for `list`. This follows FR-003a's wording ("the required read or write access")
and the alternative — per-command access modes — was rejected as more moving parts for a case the
spec does not raise (R-002). It is documented in the CLI contract.

## Project Structure

### Documentation (this feature)

```text
specs/001-bookmark-manager-cli/
├── plan.md               # This file (/speckit-plan command output)
├── spec.md               # Feature specification
├── research.md           # Phase 0 output — 10 decisions, alternatives, verified findings
├── data-model.md         # Phase 1 output — entities, schema, validation, state transitions
├── quickstart.md         # Phase 1 output — 10 runnable validation scenarios
├── contracts/
│   └── cli-contract.md   # Phase 1 output — command grammar, output formats, exit statuses
├── checklists/           # Pre-existing quality checklists
└── tasks.md              # Phase 2 output (/speckit-tasks command — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml                  # Python 3.11 floor + [tool.pytest.ini_options] pythonpath/testpaths

src/
└── bookmarks/
    ├── __init__.py             # empty package marker
    ├── __main__.py             # `python -m bookmarks` entry point: sys.exit(main(sys.argv[1:]))
    ├── cli.py                  # argparse grammar, UTF-8 stream setup, dispatch,
    │                           #   TSV/CSV/JSON rendering, the single error handler
    └── store.py                # open/validate the database, schema, tag normalisation,
                                #   URL scheme check, add/list/search/delete/export queries

tests/
├── conftest.py                 # scratch-store fixture, CLI subprocess runner, bulk seeder
├── test_add.py                 # FR-005 … FR-010
├── test_list_search.py         # FR-011 … FR-015
├── test_delete.py              # FR-016, FR-017, identifier non-reuse (FR-006)
├── test_export.py              # FR-018 … FR-021, round-trip losslessness (SC-006)
├── test_store.py               # FR-002, FR-003, FR-003a, FR-004 (store lifecycle, SC-009)
├── test_cli_contract.py        # FR-001, FR-022 … FR-024, FR-026 (statuses, streams, encoding)
└── test_performance.py         # SC-002, SC-007 on a 1,000-bookmark store
```

**Structure Decision**: Single project, flat four-module package under `src/bookmarks/`, exactly
as FR-026 requires (`python -m bookmarks` with `src/` on `PYTHONPATH`). The plan template's
default `src/models/`, `src/services/`, `src/cli/`, `src/lib/` tree is **not** used: Principle IV
directs a flat module layout with subpackages only when module count makes a flat layout
unnavigable, and four files do not. The one seam that earns its place is `store.py` versus
`cli.py` — data rules and SQL on one side, argument grammar and presentation on the other — which
also lets the performance fixture seed 1,000 rows through `store.py` directly instead of paying
for 1,000 subprocess launches. Tests are split by requirement group so the traceability mapping
Principle III demands is visible from the filenames; the `contract/integration/unit` tree from
the template is dropped for the same reason the source tree is flat. Rationale and rejected
alternatives: [research.md](./research.md) R-009, R-010.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. Both Constitution Check evaluations passed every gate, so this table is
intentionally empty.
