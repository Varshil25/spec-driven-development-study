# Implementation Plan: Archive Creation Command

**Branch**: `002-create-command` | **Date**: 2026-11-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-create-command/spec.md`

## Summary

Add a third command, `create ARCHIVE PATH... [--overwrite]`, to the existing `tarx` CLI. It
packages the named files and directories into a tar archive — gzip-compressed when `ARCHIVE` ends
in `.tar.gz` or `.tgz`, plain otherwise — under member names that are exactly the relative paths
the user typed, and reports `created ARCHIVE with N files`.

The technical approach reuses the two-phase shape `001-tarx-cli` established for `extract`:

1. **Validate everything, write nothing.** Check the archive path, the lexical safety and
   existence of every operand, and the readability of every entry in every named tree — then
   stop if anything is wrong. This is load-bearing here in a way it was not for `extract`:
   `tarfile.open(path, "w")` creates the file the moment it is called (verified, research.md §3),
   so the validation walk must complete *before* the archive is opened, or a rejected run would
   leave a zero-byte archive behind.
2. **Write the planned members in a fully determined order**, streaming each file's bytes.

`create` is built from an explicit list of planned members rather than from `TarFile.add()`,
because `add()` stores the second name of a hard-linked file as a zero-byte link member, which
FR-015 forbids (measured, research.md §4). Members are collected per operand, sorted by full
member name as text (FR-026), de-duplicated by member name (FR-020), and written from
hand-built `TarInfo` objects. No new runtime module is introduced: the command's logic joins
`src/tarx/core.py` and its argument parsing joins `src/tarx/cli.py`, reusing `TarxError`,
`Problem`, `resolve_exit_status` and the exit-status constants already there.

## Technical Context

**Language/Version**: Python 3.11+ (floor declared once in `pyproject.toml` as
`requires-python = ">=3.11"`; the development interpreter is CPython 3.13.17). No syntax or
stdlib API newer than 3.11 is used.

**Primary Dependencies**: None. Standard library only — `tarfile`, `os`, `os.path`, `stat`,
`argparse`, `sys` (Constitution Principle I). `pytest` is test-only tooling and is already
declared in the separate `[dependency-groups] test` group.

**Storage**: Filesystem only. The archive file named by `ARCHIVE` is the single artifact written;
no database, no cache, no temporary files, and no directories are ever created (FR-027).

**Testing**: `pytest`, run from the repository root. New test modules are added alongside the
existing ones; **no existing test file is modified**, which is how SC-009 is made checkable
(`git diff --stat` shows zero changes under `tests/` for pre-existing files, research.md §12).

**Target Platform**: POSIX (Linux). `/` is the member-name separator and `os.lstat`-based type
classification distinguishes symlinks, FIFOs, sockets and device nodes.

**Project Type**: Single-project command-line tool, invoked as `python -m tarx` with `src/` on
`PYTHONPATH`.

**Performance Goals**: 10,000 small files archived in under 10 seconds (SC-010). The FR-016
validation walk costs one extra traversal of the source tree, which is well inside that budget.

**Constraints**: Peak additional memory must not grow with file size — measured at 44 KiB for a
plain-tar write of a 40 MB file and 519 KiB for the gzip equivalent (zlib's compressor), against
40 MB for a read-it-all-in implementation (research.md §9). Plan size is O(number of entries),
which FR-016 and FR-026 jointly make unavoidable; this is recorded as an accepted limit below.

**Scale/Scope**: One new command, ~190 lines added to `core.py` and ~40 to `cli.py`. 27
functional requirements, 12 success criteria. Five new test modules plus one helper module.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Verdict |
|-----------|------|---------|
| **I. Standard Library Only** | No runtime import outside the stdlib; runtime requirements stay empty; test tooling declared separately | **PASS** — `tarfile`, `os`, `os.path`, `stat`, `argparse`, `sys`. `pyproject.toml` keeps `dependencies = []` and `pytest` in `[dependency-groups] test`; neither is changed by this feature. |
| **II. Fail Loudly** | Every invalid input and unmet precondition produces a specific diagnostic naming the path, on stderr, with a non-zero status; no silent fallback, no bare `except`, no output that looks successful but is not | **PASS** — eleven diagnostic templates (C1–C11), each naming the offending path, each class-2 or class-3. Exception handlers catch only `OSError` and `tarfile.TarError` and re-raise as `TarxError`; nothing is swallowed. The summary line is written **only** after the archive is closed successfully, so a mid-write failure can never read as success. |
| **III. Every Requirement Is Testable** | Every FR maps to at least one failing-when-unmet `pytest` test, traceable by requirement ID | **PASS** — all 27 FRs mapped in [data-model.md](./data-model.md#requirement-to-test-map); traceability is itself enforced by an audit test (FR-025) that parses the spec's requirement-definition lines and fails with the list of uncovered IDs. Error paths carry tests asserting both the diagnostic and the status. |
| **IV. Simplicity** | Smallest design that satisfies the spec; no speculative abstraction; fewer files and less indirection preferred | **PASS** — no new runtime module, no new class hierarchy, no plugin seam for other archive formats or compression levels (explicitly out of scope per spec). `Problem`, `TarxError`, `resolve_exit_status`, `_reason`, `_is_real_dir` and `_is_real_file` are reused rather than re-implemented; `resolve_exit_status` already encodes FR-018's "2 outranks 3". Two new data holders (`PlannedMember`, `CreatePlan`) carry data only. |

**Accepted limits** (stated, not hidden — both are consequences of requirements, not of design
preference):

- **An incomplete archive may remain after a mid-write failure.** FR-021 permits this explicitly
  and the tool does not roll back. Principle II is satisfied by the other half of the rule: a
  diagnostic names the member, no summary line is printed, and the status is 2 — so the archive is
  never *mistaken* for a result. Validation is made as complete as possible (it establishes
  readability across the whole tree) precisely so this window stays as narrow as the filesystem
  allows.
- **Plan memory is O(number of entries).** FR-016 requires a complete pre-write traversal and
  FR-026 requires globally sorted, de-duplicated member names, so some per-entry record must be
  held. File *contents* are never held — that is the property SC-010 measures.

**Post-Phase-1 re-check**: **PASS**, unchanged. Phase 1 added no dependency, no abstraction and
no silent error path. The one design decision that looks like added complexity — building
`TarInfo` objects by hand instead of calling `TarFile.add()` — is justified in
[Complexity Tracking](#complexity-tracking) against FR-015 with measured evidence, and it is
*less* indirection than `add()`, not more.

## Project Structure

### Documentation (this feature)

```text
specs/002-create-command/
├── plan.md                  # This file (/speckit-plan output)
├── spec.md                  # Feature specification (input)
├── research.md              # Phase 0 output
├── data-model.md            # Phase 1 output
├── quickstart.md            # Phase 1 output
├── contracts/
│   └── create-cli.md        # Phase 1 output: the `create` CLI contract
├── checklists/
│   └── requirements.md      # Pre-existing
└── tasks.md                 # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/tarx/
├── __init__.py              # unchanged
├── __main__.py              # unchanged
├── cli.py                   # MODIFIED: `create` subparser + _run_create + dispatch
└── core.py                  # MODIFIED: create validation, planning and write phases

tests/
├── conftest.py              # UNCHANGED (pre-existing fixtures reused as-is)
├── test_errors.py           # UNCHANGED
├── test_extract.py          # UNCHANGED
├── test_list.py             # UNCHANGED
├── test_overwrite.py        # UNCHANGED
├── test_traceability.py     # UNCHANGED (audits 001's requirements only)
├── test_validation.py       # UNCHANGED
├── create_support.py        # NEW: tree-building and archive-inspection helpers
├── test_create.py           # NEW: US1 — members, names, order, compression, counts
├── test_create_overwrite.py # NEW: US2 — collision refusal and --overwrite
├── test_create_errors.py    # NEW: US3 — validation failures, no archive left behind
├── test_create_roundtrip.py # NEW: US4 — list/extract interop, usage discoverability
└── test_create_traceability.py  # NEW: CREATE-FR-### coverage audit

pyproject.toml               # unchanged (stdlib-only runtime, pytest marker already present)
```

**Structure Decision**: The existing single-project layout is kept exactly as `001-tarx-cli`
established it — `src/tarx/` with `core.py` (all archive logic, never prints, never exits) and
`cli.py` (the only module that touches streams and statuses) — and `create` is added inside that
split rather than beside it. Adding a `src/tarx/create.py` was considered and rejected: it would
need to import `TarxError`, `Problem`, `resolve_exit_status`, `_reason`, `_is_real_dir` and
`_is_real_file` back out of `core.py`, trading one more file and one more import edge for no
reduction in total moving parts (Principle IV). New test modules are separate files per user
story so that each story remains independently testable, and the new fixtures live in
`tests/create_support.py` rather than in `tests/conftest.py` so that **no pre-existing test file
is touched at all** — making SC-009 a mechanically verifiable claim instead of a promise.

## Complexity Tracking

> Filled for the two places this design deviates from the most obvious implementation. Both are
> justified against a stated requirement, as Principle IV demands.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Hand-built `TarInfo` + `addfile()` instead of `TarFile.add(path, arcname)` | FR-015 requires each name of a hard-linked file to be stored and counted as an independent regular file with its own copy of the contents | `TarFile.add()` keeps an inode cache and stores the second name of a hard-linked file as a zero-byte `LNKTYPE` member. Measured: `add()` produced `[('t/a.txt', '0', 1), ('t/d/link.txt', '1', 0)]` where hand-built `TarInfo` produced `[('t/a.txt', '0', 1), ('t/d/link.txt', '0', 1)]` (research.md §4). Using `add()` would silently drop one of the user's files from the archive — exactly the silent wrong answer Principle II forbids. `add()` would also append a trailing `/` to directory names and re-`stat` each entry. |
| An explicit `CreatePlan` built before writing, rather than archiving entries as they are walked | FR-016 (validate the whole tree, including readability, before creating any file), FR-026 (members sorted by full member name across the whole subtree) and FR-020 (de-duplicate by member name across operands) cannot be satisfied by a streaming single pass | Walking and writing in one pass would leave a partial archive behind on the first unreadable file deep in a tree, and could not produce a globally sorted, de-duplicated member sequence. The cost is one extra traversal and O(entries) plan memory, both accounted for above. |
