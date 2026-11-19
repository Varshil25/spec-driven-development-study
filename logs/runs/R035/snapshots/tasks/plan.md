# Implementation Plan: Tar Archive Listing and Extraction CLI

**Branch**: `001-tarx-cli` | **Date**: 2026-11-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-tarx-cli/spec.md`

## Summary

A single-package Python CLI, invoked as `python -m tarx COMMAND ...`, that lists tar archive
members (`list ARCHIVE`) and extracts their files and directories into a destination
(`extract ARCHIVE DEST [--overwrite]`). Both plain and gzip-compressed archives are accepted and
are distinguished by content, not filename.

Technical approach: `tarfile.open(path, "r:*")` handles format and compression detection in one
call. `extract` runs as two distinct phases — a **validation phase** that walks every member and
collects *all* problems (unsafe paths, type mismatches, blocked parents, refused overwrites)
without touching the filesystem, and a **write phase** that runs only if validation found nothing.
This phase split is what satisfies FR-020 (nothing written when a detected failure occurs) and
FR-025 (report every problem, status 2 outranks status 3). Extraction is performed manually
(`os.makedirs` + `shutil.copyfileobj`) rather than via `TarFile.extractall`, because `extractall`
stops at the first bad member and its extraction filters are a Python 3.12+ API while the floor
here is 3.11. Exit codes are 0 / 2 / 3; `argparse`'s own usage-error exit code is already 2, which
matches FR-017 with no extra code.

## Technical Context

**Language/Version**: Python 3.11+ (`requires-python = ">=3.11"`). Local interpreter is CPython
3.13, so the 3.11 floor is maintained by review discipline: no `tarfile` extraction filters, no
`Path.walk`, no other post-3.11 stdlib or syntax features.

**Primary Dependencies**: None at runtime — standard library only (`argparse`, `tarfile`, `os`,
`os.path`, `shutil`, `sys`). Test-time only: `pytest` (declared in a separate dependency group).

**Storage**: Local filesystem. Archives are read-only inputs; the destination directory tree is
the only thing written.

**Testing**: `pytest`. Primarily in-process tests calling `tarx.cli.main(argv)` with `capsys` and
`tmp_path`, plus a small set of subprocess tests that run `python -m tarx` with `src` on
`PYTHONPATH` to prove the documented invocation and real exit statuses. Fixtures build archives
on the fly with `tarfile`, so no binary test assets are committed.

**Target Platform**: POSIX (Linux) command line; nothing platform-specific beyond path handling.

**Project Type**: Single-project CLI tool (`src/` layout, one package).

**Performance Goals**: `list` on a 10,000-member archive under 5 seconds (SC-008) — met by
iterating member headers and never reading member contents. `extract` of an archive larger than
available memory must succeed (SC-008) — met by streaming each member through a fixed-size buffer
via `shutil.copyfileobj`; no member body is ever fully buffered.

**Constraints**: Memory bounded by member-header metadata plus one copy buffer, not by archive or
member size. Results on stdout, diagnostics on stderr, exit status as the machine-readable
outcome. No environment variables, no network, no files outside caller-supplied paths.

**Scale/Scope**: Two commands, one option, three exit statuses, 25 functional requirements.
Expected implementation size roughly 250–350 lines of runtime code across 4 modules.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0 (ratified 2026-11-19).

| Principle | Gate | Pre-design verdict | Post-design verdict |
|-----------|------|--------------------|---------------------|
| I. Standard Library Only | Zero third-party runtime imports; test tooling declared separately | PASS — `argparse`, `tarfile`, `os`, `shutil`, `sys` only | PASS — no module added during design; `pytest` sits in a `[dependency-groups] test` entry, `[project.dependencies]` stays empty |
| II. Fail Loudly | Every invalid input / unmet precondition yields a specific stderr diagnostic and non-zero exit; no silent fallback, no bare `except`, no partial output that looks successful | PASS — 0/2/3 status model with per-case message templates | PASS — every template is enumerated in [contracts/cli.md](./contracts/cli.md); `except` clauses are narrow (`OSError`, `tarfile.TarError`) and each re-raises as a named diagnostic; the `extracted N files` summary is suppressed on any failure, including the mid-write FR-022 case |
| III. Every Requirement Is Testable | Each FR maps to at least one failing-when-unmet `pytest` test, traceable by requirement ID | PASS — FR-001…FR-025 are all observable through argv, stdout, stderr, exit status, and the destination tree | PASS — requirement-to-test map in [data-model.md](./data-model.md#requirement-to-test-map); IDs appear in test names and docstrings, and `tests/test_traceability.py` asserts every FR ID in `spec.md` is referenced by at least one test |
| IV. Simplicity | Smallest design that satisfies the spec; no speculative abstraction | PASS — one package, no classes beyond plain data holders, no config, no plugin seam | PASS — 4 runtime modules (`__init__`, `__main__`, `cli`, `core`); deviations justified in Complexity Tracking below |

**Gate result: PASS.** No violation requires justification as an exception; the two
non-obvious design choices are recorded in Complexity Tracking as deliberate, requirement-backed
decisions rather than unexplained structure.

## Project Structure

### Documentation (this feature)

```text
specs/001-tarx-cli/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── cli.md           # Phase 1 output — CLI command, output and exit-status contract
├── checklists/          # Pre-existing (/speckit-checklist output)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml           # requires-python >=3.11, empty runtime deps, separate test group, pytest config

src/
└── tarx/
    ├── __init__.py      # package marker; nothing executable
    ├── __main__.py      # `python -m tarx` entry: sys.exit(cli.main())
    ├── cli.py           # argparse parser, command dispatch, stdout/stderr writing, exit codes
    └── core.py          # archive opening, member listing, validation, extraction

tests/
├── conftest.py          # tmp-path archive-building fixtures (plain + gzip), CLI invocation helpers
├── test_list.py         # FR-002, FR-003, FR-004, FR-018, FR-024 and list-side SCs
├── test_extract.py      # FR-005…FR-008, FR-011, FR-015, FR-018 happy paths
├── test_overwrite.py    # FR-009, FR-010 refusal and opt-in replacement
├── test_errors.py       # FR-012…FR-014, FR-017, FR-019, FR-022, FR-023, FR-025 failure paths
├── test_validation.py   # unit-level tests of core path-safety and conflict detection
└── test_traceability.py # FR-021 / SC-007 audit: every FR ID in spec.md is referenced by a test
```

**Structure Decision**: Single project, `src/` layout, as mandated by the feature description
("a package named `tarx` under `src/`, runnable via `python -m tarx` with `src/` on
`PYTHONPATH`"). The template's `models/ services/ cli/ lib/` subdivision is dropped — for a
two-command tool it would be four directories holding one file each, which Principle IV forbids.
The split that does earn its place is `cli.py` (argument parsing, stream writing, exit codes)
versus `core.py` (archive reading, validation, writing): it keeps the validation logic callable
without a subprocess, which is what makes `tests/test_validation.py` possible. Tests are not
installed, so `pyproject.toml` sets pytest's `pythonpath = ["src"]` rather than requiring an
editable install.

## Complexity Tracking

> Neither row below is a constitution violation. Both are places where a simpler-looking option
> exists and was rejected for a requirement-specific reason, recorded here so review can check the
> reasoning rather than re-derive it.

| Decision | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|--------------------------------------|
| Manual extraction loop (`os.makedirs` + `shutil.copyfileobj`) instead of `TarFile.extractall` | FR-025 requires *all* problems reported in one run and FR-009/FR-023 require distinct 3-vs-2 statuses; FR-020 requires zero writes when a problem is detected | `extractall` aborts on the first bad member (so it can report only one problem), writes members as it goes (so a late conflict leaves a partial tree), and its `filter=` safety hook is Python 3.12+, above the 3.11 floor |
| Two-phase `extract` (validate-everything, then write) with an explicit plan structure | FR-020, FR-009, FR-014, FR-023, FR-025 all hinge on decisions made before the first byte is written | A single streaming pass is fewer lines but cannot satisfy "no files written at all" for a conflict discovered at the last member, and cannot aggregate problems across the archive |
