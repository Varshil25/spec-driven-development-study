# Implementation Plan: Tar Archive List & Extract CLI

**Branch**: `001-tar-archive-cli` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-tar-archive-cli/spec.md`

## Summary

Deliver a zero-dependency Python CLI, `python -m tarx`, with two subcommands: `list ARCHIVE` prints
every archive member one per line in archive order, and `extract ARCHIVE DEST [--overwrite]`
recreates regular files and directories under `DEST` and prints `extracted N files`. Plain and
gzip-compressed tars are both accepted, detected from content rather than file name. Exit statuses
are 0 for success, 3 for an overwrite conflict, 2 for every other failure, each accompanied by a
short one-line diagnostic on stderr.

Technical approach: the whole feature is a thin, carefully-error-handled shell over the stdlib
`tarfile` module. Two decisions shape it.

1. **Open with `tarfile.open(path, "r:*")`** — content sniffing is what satisfies FR-018 with one
   stdlib call and no magic-byte code of our own.
2. **Do not use `TarFile.extractall`; write members directly.** `extractall` overwrites
   unconditionally, cannot report a count of files written, and applies metadata the spec puts out
   of scope — so FR-019/020, FR-015/021, and FR-016/026 are all unreachable through it. Writing
   directories with `mkdir` and files with `copyfileobj` is a dozen lines and keeps every specified
   behavior under this project's control. It also avoids the version-dependent `tarfile` extraction
   filters entirely, which keeps the 3.11+ support floor honest.

`extract` runs as two phases: a read-only planning pass that resolves every member to a target path
and collects containment violations, kind collisions, and overwrite conflicts; then a write pass
that runs only if planning was clean. That split is what makes "nothing is written when the command
refuses" (FR-020, SC-003) a structural property rather than a promise.

Phase 0 research resolved all unknowns — see [research.md](./research.md). It also resolved one
genuine internal ambiguity in the spec (FR-019 vs. FR-023 on exit 2 vs. 3), recorded as decision R8
and reflected in the contract.

## Technical Context

**Language/Version**: Python 3.11+ (per spec's mandated constraints); developed and verified against
CPython 3.13.17. No syntax or stdlib API newer than 3.11 is used.

**Primary Dependencies**: None at runtime — standard library only (Constitution Principle I). Uses
`tarfile`, `argparse`, `pathlib`, `posixpath`, `shutil`, `sys`, `os`.

**Storage**: N/A. Reads one archive file; writes plain files and directories under a
caller-specified destination. No database, no state carried between invocations.

**Testing**: `pytest` (test-only; verified 9.1.1). Tests under `tests/`, runnable as a bare `pytest`
from the repository root via `pythonpath = src` in `pytest.ini`.

**Target Platform**: POSIX-like systems with CPython 3.11+ (developed on Linux 6.18). No
platform-specific APIs; Windows-style absolute member paths are rejected defensively as part of
containment checking.

**Project Type**: Single-package CLI tool, source under `src/`.

**Performance Goals**: SC-007 — an archive of 10,000 members lists in under 5 s and extracts in
under 30 s; memory must not grow with the size of the largest member. Met by streaming: `list`
iterates the `TarFile` rather than materializing `getmembers()`, and extraction copies via
`shutil.copyfileobj(..., length=64*1024)` instead of reading members whole.

**Constraints**: No third-party runtime imports. No configuration surface — behavior is fully
determined by the command line. Output is plain, unformatted, pipe-friendly text. File metadata
(mode, owner, mtime) is explicitly not preserved. No uncaught traceback may ever reach the user.

**Scale/Scope**: Two subcommands, 28 functional requirements, 8 success criteria. Roughly 200 lines
of runtime code across three files plus a test suite; one archive per invocation, local filesystem
only.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0.

### Pre-Phase-0 evaluation

| Principle | Gate | Verdict |
|---|---|---|
| I. Standard Library Only | Runtime imports resolve only to stdlib or first-party modules; `pytest` is test-only and never imported by runtime code | **PASS** — `tarfile`/`argparse`/`pathlib`/`posixpath`/`shutil` are stdlib; the spec's own mandated constraints agree |
| II. Fail Loudly | Every invalid input produces a specific diagnostic on stderr naming the offending value, plus a non-zero exit; no swallowed exceptions; no partial result in place of failure | **PASS** — FR-024 … FR-028 already specify exactly this; the design adds a single error type so no path can exit silently |
| III. Every Requirement Is Testable | Each FR maps to ≥ 1 `pytest` test that fails when unmet, traceable by requirement id; error paths asserted on both diagnostic and status | **PASS** — all 28 FRs are stated as observable input → output/status; SC-006 restates the traceability duty |
| IV. Simplicity | Smallest design satisfying the spec; no speculative abstraction, config hook, or plugin seam; prefer function over class, module over package | **PASS** — see justifications below |

### Simplicity justifications (Principle IV requires these in writing)

Four structures exist beyond the barest possible script. Each is traced to a forcing requirement:

1. **A package `tarx` rather than a single module.** Forced by the spec's mandated constraint
   "code lives in a package named `tarx` under `src/`, runnable as `python -m tarx`" — `python -m`
   on a package requires `__main__.py`. Within the package, logic stays in **one** module
   (`cli.py`); `__main__.py` is a two-line entry point. No `models/`, `services/`, or `lib/`
   subpackages.
2. **One internal exception class.** Forced by FR-027 (every failure names its offending path) plus
   FR-028 (exclusive status codes). Python's `raise` requires an exception type, so this is the one
   place the "prefer a plain data structure" preference cannot apply. One class, two fields, caught
   in one place.
3. **A planning pass before the write pass.** Forced by FR-020: the conflict must be detected
   "before any member is written". A single-pass design cannot satisfy it. The pass produces plain
   lists and tuples, not classes.
4. **A set of written paths instead of an integer counter.** Forced by FR-015 plus the Edge Cases
   entry "Duplicate member names", which requires a doubly-stored path to be counted once. A counter
   would over-report.

Explicitly **not** built, per Principle IV: no `Archive`/`Member` wrapper types over `TarFile` and
`TarInfo`; no abstraction over the two subcommands; no plugin or filter hook; no configuration file,
environment variable, or logging framework; no progress reporting; no rollback machinery beyond what
FR-020 requires.

### Post-Phase-1 re-evaluation

Re-checked against the generated design artifacts ([research.md](./research.md),
[data-model.md](./data-model.md), [contracts/cli-contract.md](./contracts/cli-contract.md),
[quickstart.md](./quickstart.md)).

| Principle | Verdict after design | Evidence |
|---|---|---|
| I. Standard Library Only | **PASS** | The design names every runtime import; all are stdlib. `pytest.ini` is test configuration and declares no runtime dependency. Research R11's choice to hand-write extraction removes the only place a convenience dependency might have been reached for. |
| II. Fail Loudly | **PASS** | The contract's diagnostics table enumerates a specific message for all ten specified failure conditions, each naming the offending path or member. Research R4 found that `tarfile.ReadError` is multi-line and unhelpful, so the design replaces its text rather than forwarding it — strengthening this gate. Broad `except OSError` backstops exist, but each converts to a named diagnostic plus exit 2, which is the opposite of swallowing. |
| III. Every Requirement Is Testable | **PASS** | Every contract row and data-model rule is phrased as an assertable input → output/status pair. The quickstart's acceptance checklist carries SC-006's per-FR traceability obligation forward into the test suite that `/speckit-tasks` will enumerate. |
| IV. Simplicity | **PASS** | The post-design file count is three runtime files and one test-config file. The four justified structures above are unchanged; Phase 1 added no fifth. Design decisions R2 and R11 were both resolved toward *less* code (accept `r:*`'s format superset rather than restrict it; skip defensive `rstrip("/")` once R3 proved it dead). |

**No violations. Complexity Tracking below is intentionally empty.**

One note for transparency, not a gate failure: Phase 0 found that FR-019 and FR-023 conflict for a
single input (no `--overwrite`, file member, existing directory at the target). Research R8 resolves
it in favor of exit 2 and explains why. This is a specification ambiguity resolved in the plan, not a
constitutional deviation — but it is the one place where the implementation's behavior is decided
here rather than in the spec, so it is worth a reviewer's attention and may warrant a spec amendment.

## Project Structure

### Documentation (this feature)

```text
specs/001-tar-archive-cli/
├── plan.md                      # This file (/speckit-plan output)
├── spec.md                      # Feature specification (input)
├── research.md                  # Phase 0 output
├── data-model.md                # Phase 1 output
├── quickstart.md                # Phase 1 output
├── contracts/
│   └── cli-contract.md          # Phase 1 output — the CLI surface
└── tasks.md                     # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
pytest.ini                       # pythonpath = src, testpaths = tests (research R10)

src/
└── tarx/
    ├── __init__.py              # package marker; no logic
    ├── __main__.py              # entry point: sys.exit(main(sys.argv[1:]))
    └── cli.py                   # argparse wiring, list, extract, planning, diagnostics

tests/
├── conftest.py                  # archive-building fixtures (plain, gzip, nested, escaping, empty)
├── test_invocation.py           # FR-001 … FR-004: subcommands, arity, usage errors
├── test_list.py                 # FR-005 … FR-009: output, order, membership, exit 0
├── test_extract.py              # FR-010 … FR-016: contents, dirs, count, skipping
├── test_compression.py          # FR-017, FR-018: gzip vs plain, content-based detection
├── test_overwrite.py            # FR-019 … FR-023: conflicts, --overwrite, kind collisions
├── test_failures.py             # FR-024 … FR-028: diagnostics, containment, exit statuses
└── test_performance.py          # SC-007: 10k-member archive timing and streaming
```

**Structure Decision**: Single-package CLI layout. `src/tarx/` holds the package the spec mandates,
with all logic in the single module `cli.py` and `__main__.py` reduced to an entry point, which is
the fewest moving parts that still supports `python -m tarx` (Principle IV justification 1). Tests
are split one file per requirement cluster so that SC-006's requirement-to-test traceability is
visible from the file tree, with `test_performance.py` separated because it is the only slow test.
No `models/`, `services/`, or `lib/` directories are created — this feature has no layers to
separate, and inventing them would be the speculative generality Principle IV prohibits.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. The Constitution Check passes both pre-Phase-0 and post-Phase-1; the four structures
that exceed a bare script are justified inline under *Simplicity justifications*, each traced to the
specific requirement that forces it.
