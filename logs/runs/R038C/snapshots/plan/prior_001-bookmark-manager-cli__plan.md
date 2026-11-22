# Implementation Plan: Command-Line Bookmark Manager

**Branch**: `001-bookmark-manager-cli` | **Date**: 2026-11-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-bookmark-manager-cli/spec.md`

## Summary

A single-process CLI, `python -m bookmarks [--db PATH] COMMAND ...`, that stores bookmarks
(URL, title, tag set) in one SQLite file and exposes `add`, `list`, `search`, `delete` and
`export`. Implementation is Python 3.11+ standard library only: `argparse` for parsing and
usage errors (exit 2), `sqlite3` for storage with parameterised statements and AUTOINCREMENT
identifiers that are never reused, `csv` and `json` for export, `os.open` to create the
database file at mode `0600`. Three small modules under `src/bookmarks/` separate argument
parsing, storage, and output formatting; every command streams rows from a single cursor to
standard output so memory does not scale with collection size. Tests are `pytest`, driven
through the real module entry point in a subprocess-free in-process harness, one or more
tests per FR and SR.

## Technical Context

**Language/Version**: Python 3.11+ (verified available here: 3.13.17). No syntax or API newer
than 3.11 is used.

**Primary Dependencies**: None at runtime — standard library only (`argparse`, `sqlite3`,
`csv`, `json`, `os`, `sys`, `pathlib`, `contextlib`, `typing`). `pytest` for tests only
(Constitution Principle I permits third-party test tooling but no third-party runtime
import).

**Storage**: One SQLite database file per collection, default `./bookmarks.db`, overridable
with `--db PATH`. Schema: `bookmarks` + `bookmark_tags` (see [data-model.md](./data-model.md)).
Bundled SQLite verified at 3.45.1; the schema and queries require nothing newer than 3.7.15
(`instr`), so any SQLite shipped with Python 3.11+ suffices.

**Testing**: `pytest`. Tests invoke `bookmarks.cli.main(argv)` directly (returns an exit
status; never calls `sys.exit` itself) and capture stdout/stderr via `capsys`, with `tmp_path`
for database files. No subprocess, no network, no third-party plugin.

**Target Platform**: POSIX (Linux/macOS) for the full suite; the `0600` file-mode assertion
(SR-005) is POSIX-only and is skipped on Windows, where the rest of the suite still runs.

**Project Type**: Single-project CLI tool, package `bookmarks` under `src/`, runnable as
`python -m bookmarks` with `src/` on `PYTHONPATH`.

**Performance Goals**: Each command on 10,000 bookmarks completes in under one second
(SC-004). Export of 50,000 bookmarks runs in bounded memory (SR-007).

**Constraints**: Standard library only; no network, no subprocess, no shell, no environment-
driven configuration (SR-010). Output memory per operation is O(1) in collection size
(SR-007). Writes are atomic per command (SR-009). No temporary file survives any command
(SR-011). Exit statuses are exactly 0 / 1 / 2 / 3 as specified in FR-005.

**Scale/Scope**: Five subcommands, two tables, three source modules plus `__main__.py`;
tested to 50,000 bookmarks. 27 functional requirements (FR-001…FR-027) and 11 security
requirements (SR-001…SR-011) to cover.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.0. The Plan gate (Development Workflow & Quality Gates) requires this plan
to name, for each principle, the specific commitment. It does:

### I. Standard Library Only — PASS

Runtime imports are limited to `argparse`, `sqlite3`, `csv`, `json`, `os`, `sys`, `pathlib`,
`contextlib`, `typing`. SQLite is the standard library's own bundled binding, so the storage
requirement needs no external package. `pytest` is test-only and no test exercises a runtime
path through a third-party package. Mechanically checked by the SC-007/SR-010 import test,
which walks the AST of every shipped module and asserts every imported top-level name is in
`sys.stdlib_module_names`.

### II. Fail Loudly — PASS

Every invalid input case has a named message destination and exit status. The complete
mapping is the error contract in
[contracts/cli-contract.md](./contracts/cli-contract.md#exit-statuses-and-error-contract):

| Case | Stream | Status |
|---|---|---|
| Unknown command / option, missing argument, bad `--format`, malformed `delete ID`, oversized input, invalid URL | stderr | 2 |
| `delete ID` where no such bookmark exists | stderr | 3 |
| Unusable `--db` path, missing parent directory, corrupt or unreadable database | stderr | 1 |
| Success | stdout only | 0 |

No `except` block in the design swallows an error, substitutes a default for unvalidated
input, or truncates data. Specifically: a `--db` path that cannot be opened is an error, never
a silent fallback to `bookmarks.db`; a corrupt database is an error, never an empty
collection; a tag string that parses to zero tags stores zero tags (FR-012) rather than being
guessed at. An empty `list`/`search` result is a *success* with no output (FR-018) and is not
an error — that is specified behaviour, not a silent wrong answer.

### III. Every Requirement Is Testable — PASS

Every FR and SR maps to at least one named `pytest` test. The full matrix is
[contracts/requirements-test-matrix.md](./contracts/requirements-test-matrix.md) (38
requirements, 0 unmapped, 0 planned skips). Acceptance scenarios from User Stories 1–4 map to
integration tests in `tests/integration/`, one module per story, satisfying SC-002.

### IV. Simplicity — PASS

Smallest design that satisfies the spec: four files of shipped code (`__main__.py`, `cli.py`,
`storage.py`, `output.py`), two tables, no classes beyond one frozen dataclass for a row, no
plugin or registry for commands (a dict of five functions), no ORM, no configuration layer,
no logging framework. Deliberate rejections recorded in
[research.md](./research.md): a third `tags` lookup table, a service/repository layer, a
`--format` plugin interface, and WAL journalling were all considered and dropped. The
Complexity Tracking table below is empty because no complexity beyond the minimum is
proposed.

### V. Secure By Default (NON-NEGOTIABLE) — PASS

The spec states 11 security requirements derived from OWASP Top 10 and ASVS V5/V7/V12. Each
maps to the constitution's mandatory baseline controls and to at least one negative test:

| Baseline control | Feature requirement | Design commitment | Negative test |
|---|---|---|---|
| Untrusted input, allow-list | SR-002, SR-003 | URL accepted only on exact lowercase `http://`/`https://` prefix; `delete` only decimal positive int ≤ 2^63−1; `--format` only `csv`/`json`; argparse refuses unknown commands/options | `test_security_urls.py`, `test_security_args.py` |
| No string-built interpretation | SR-001, SR-004 | Every statement is a fixed string with `?` placeholders; search uses `instr(lower(col), lower(?))`, never `LIKE`, so `%`/`_` are literal; CSV written by `csv.writer`, JSON by `json.dumps` | `test_security_injection.py`, `test_security_search_literal.py` |
| Path containment | n/a — documented deviation | `--db` is a first-party operator argument with no allowed base directory to confine it to (spec Assumptions). It is used only as a file path, never as a shell word; no path component comes from stored data or the environment. Expiry condition: revisit if any path is ever derived from stored or remote input. | `test_security_db_path.py` asserts a bad path errors (exit 1) rather than falling back |
| Credential storage | n/a | No credentials, passwords, tokens or secrets exist in this feature | — |
| Randomness and comparison | n/a | No tokens, salts or secret comparisons; identifiers are SQLite AUTOINCREMENT sequence values, not security tokens | — |
| Resource limits | SR-006, SR-007 | Enforced maxima: URL 8192, title 4096, `--tags` string 4096 with ≤64 tags of ≤128 chars, search text 1024; all reads stream from a cursor with O(1) per-row memory | `test_security_limits.py` (one char over each limit), `test_security_streaming.py` |
| Access control | n/a | Single-user local tool; the OS file permissions on the database are the access control, covered by SR-005 | — |
| File permissions | SR-005 | Database file created by `os.open(..., O_CREAT|O_EXCL, 0o600)` *before* `sqlite3.connect`, so the mode is set at creation, not afterwards; SQLite's rollback journal inherits that mode | `test_security_file_mode.py` |
| Output hygiene | SR-008, SR-011 | Expected failures produce one single-line message with no traceback and no SQL text; no temporary file holding bookmark data survives (journal mode left at `delete`, never WAL) | `test_security_no_traceback.py`, `test_security_no_residual_files.py` |

One documented deviation from the baseline, carried over from the spec's Assumptions and
restated here as the constitution's compliance review requires: **CSV output is not
spreadsheet-hardened.** The "encode for the destination context" control would suggest
prefixing a leading `=`, `+`, `-` or `@` in a title to defeat spreadsheet formula injection,
but FR-025 requires exact round-tripping through a standard CSV parser, and the two cannot
both hold. FR-025 governs; fields are quoted per RFC 4180 by `csv.writer` and otherwise
unaltered. Expiry condition: revisit if a requirement ever targets a spreadsheet macro engine
as a consumer. Recorded in Complexity Tracking as a deviation, not a complexity.

**Post-Design re-check (after Phase 1): PASS.** The Phase 1 artifacts introduced no new
dependency, no new table beyond the two planned, no new module, and no new error path. The two
designs chosen during Phase 1 that could have added complexity — ordered tag aggregation and
streaming JSON — were both resolved with standard-library-only, bounded-memory approaches
(adjacent-row grouping over one `LEFT JOIN`; incremental `json.dumps` per element) rather than
new components. See [research.md](./research.md) decisions R4 and R6. No gate changes status.

## Project Structure

### Documentation (this feature)

```text
specs/001-bookmark-manager-cli/
├── plan.md                              # This file (/speckit-plan command output)
├── research.md                          # Phase 0 output
├── data-model.md                        # Phase 1 output
├── quickstart.md                        # Phase 1 output
├── contracts/                           # Phase 1 output
│   ├── cli-contract.md                  # Command surface, I/O formats, exit statuses
│   └── requirements-test-matrix.md      # FR/SR → test mapping (Principle III)
├── checklists/                          # Pre-existing
└── tasks.md                             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/
└── bookmarks/
    ├── __init__.py        # Package marker; version constant only
    ├── __main__.py        # `python -m bookmarks` entry: sys.exit(cli.main(sys.argv[1:]))
    ├── cli.py             # argparse parser, validators, five command functions, main()
    ├── storage.py         # connect/schema creation, parameterised queries, row streaming
    └── output.py          # tab-separated lines, CSV writer, streaming JSON array

tests/
├── conftest.py            # tmp_path db fixture, run(argv) helper returning (status, out, err)
├── contract/
│   ├── test_cli_surface.py        # commands/options/usage per cli-contract.md
│   ├── test_output_formats.py     # 4-field TSV, CSV header & quoting, JSON shape
│   └── test_exit_statuses.py      # 0/1/2/3 mapping
├── integration/
│   ├── test_story1_add_and_list.py
│   ├── test_story2_search_and_tag_filter.py
│   ├── test_story3_delete.py
│   ├── test_story4_export.py
│   ├── test_persistence.py        # SC-003: 1,000 mixed add/delete commands
│   └── test_performance.py        # SC-004: 10,000 bookmarks under 1s per command
├── security/
│   ├── test_security_injection.py
│   ├── test_security_urls.py
│   ├── test_security_args.py
│   ├── test_security_search_literal.py
│   ├── test_security_file_mode.py
│   ├── test_security_limits.py
│   ├── test_security_streaming.py
│   ├── test_security_no_traceback.py
│   ├── test_security_atomicity.py
│   ├── test_security_stdlib_only.py   # also covers SC-007
│   ├── test_security_db_path.py
│   └── test_security_no_residual_files.py
└── unit/
    ├── test_tag_parsing.py        # FR-012 degenerate inputs
    ├── test_url_validation.py     # FR-008 prefix rule
    └── test_formatting.py         # tag sort order, empty-field rendering

pytest.ini                         # pythonpath = src ; testpaths = tests
```

**Structure Decision**: Single-project layout as the spec's Technical Constraints require —
package `bookmarks` under `src/`, tests under `tests/`. `src/` is put on the import path by
`pytest.ini`'s `pythonpath = src` (a stock pytest setting, no `conftest` path hacking and no
packaging step), which keeps `python -m bookmarks` working from the repository root with
`PYTHONPATH=src` and keeps the test suite running with a bare `pytest`. The template's
`models/`, `services/`, `lib/` subdivision is deliberately not used: three modules of a few
hundred lines each do not need package-per-layer nesting, and Principle IV forbids adding
layers for anticipated need. Tests are split by purpose (contract / integration / security /
unit) so the Principle III and Principle V gates can each be audited against a directory.

## Complexity Tracking

> No Constitution Check violations. One documented deviation, recorded here per the
> Governance requirement that every deviation carry a justification and an expiry condition.

| Violation / Deviation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| CSV output not hardened against spreadsheet formula injection (baseline "encode for the destination context") | FR-025 requires a title to round-trip unchanged through a standard CSV parser; prefixing a leading `=`/`+`/`-`/`@` would alter the data and break that requirement. Expiry: revisit if a spreadsheet macro engine becomes a named consumer. | Hardening is the "safer" alternative but is rejected because it contradicts an explicit functional requirement; the spec records spreadsheet consumers as out of scope. |
