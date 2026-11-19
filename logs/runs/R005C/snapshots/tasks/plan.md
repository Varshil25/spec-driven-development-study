# Implementation Plan: Tar Archive Create Command

**Branch**: `002-create-command` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-create-command/spec.md`

## Summary

Add a third subcommand to the existing zero-dependency CLI: `python -m tarx create ARCHIVE PATH...
[--overwrite]` packs each named file or directory into a tar archive at `ARCHIVE`, naming members by
their path relative to the current directory, gzip-compressing when the archive name ends in
`.tar.gz` or `.tgz`, and printing `created ARCHIVE with N files`. Exit statuses match the rest of
the tool: 0 on success, 3 when `ARCHIVE` exists and `--overwrite` was not given, 2 for every other
failure, each with a one-line diagnostic on stderr naming the offending path. `list` and `extract`
are not touched.

Technical approach: three decisions carry the feature, all validated in Phase 0 against the real
interpreter and the real existing commands.

1. **One `tar.add(source, arcname=normalized, recursive=True, filter=classify)` call per source
   path.** That single stdlib call already delivers recursive expansion with a directory member for
   each directory (FR-033), relative member naming (FR-034), deterministic `sorted()` order
   (FR-035), skipping of entries that are neither files nor directories via a filter returning
   `None` (FR-036), refusal to archive the archive into itself (FR-037), and chunked streaming that
   keeps memory flat (SC-017). A hand-written `os.walk` would re-implement all six — Principle IV
   makes `add` the required choice, not just the convenient one
   ([research R13](./research.md#r13--tarfileaddrecursivetrue-filter-instead-of-a-handwritten-walk)).
2. **Validate everything before opening the archive.** Phase 0 verified that
   `tarfile.open(path, "w")` truncates an existing file *immediately* — a 140-byte archive became
   0 bytes even though the following `add` failed at once. Validating after opening would therefore
   destroy the user's archive in exactly the case FR-050 and US4 scenario 3 protect, and leave a
   0-byte file where FR-050 requires none. Source-path and archive-target validation form a pass
   that writes nothing, which turns FR-051 into a structural property rather than a promise — the
   same split 001 used to make FR-020 structural for `extract`
   ([research R18](./research.md#r18--all-validation-must-precede-opening-the-archive)).
3. **Compression from the typed suffix, nothing else.** `path.lower().endswith((".tar.gz", ".tgz"))`
   selects `"w:gz"` over `"w"` (FR-040 … FR-042). Deliberately asymmetric with the read commands,
   which sniff content — and harmless, because a content-sniffing reader accepts whatever a
   name-driven writer produces, which is why the round trip in FR-047/FR-048 holds even for an
   unconventional archive name ([research R12](./research.md#r12--choosing-the-write-mode-from-the-archive-name)).

The whole design was run end to end in Phase 0 — a prototype archive was created, then listed and
extracted by the **real, unmodified** `list` and `extract` — before any of it was written up. Both
the plain and gzip forms listed the expected seven member names in order, extracted byte-identical
contents, recreated the empty directory, and reported a count equal to the one creation reported.
See the round-trip table at the end of [research.md](./research.md).

Phase 0 left no `NEEDS CLARIFICATION` in Technical Context — the spec's *Assumptions* section
already fixed language, dependencies, package location, and scope. It did surface **three points
where the specification is silent or self-conflicting**, each resolved here and flagged for a
reviewer: the meaning of `.` as a source path (R19), `--overwrite` onto an existing non-regular file
(R20), and FR-048's count equality versus the *A path named twice* edge case (R22). These are the
direct counterpart of 001's research R8.

## Technical Context

**Language/Version**: Python 3.11+ (per the spec's mandated constraints and the user's planning
input); developed and verified against CPython 3.13.17. No syntax or stdlib API newer than 3.11 is
used — `TarFile.add`'s keyword-only `filter` has existed since 3.2 and its `sorted(os.listdir(...))`
recursion since 3.7.

**Primary Dependencies**: None at runtime — standard library only (Constitution Principle I, spec
assumption, user input). This feature adds **no** new imports: `tarfile`, `argparse`, `posixpath`,
`pathlib`, and `sys` are already imported by `src/tarx/cli.py`. `os` is needed for
`os.path.lexists`.

**Storage**: N/A. Writes one archive file; reads files and directories under the current directory.
No database, no state carried between invocations, no configuration surface.

**Testing**: `pytest` (test-only, never imported by runtime code; verified 9.1.1). New tests join
the existing suite under `tests/`, runnable as a bare `pytest` from the repository root via
`pythonpath = src` in `pytest.ini`. The pre-existing tests are **not** modified (SC-015).

**Target Platform**: POSIX-like systems with CPython 3.11+ (developed on Linux 6.18). No
platform-specific APIs. Note that the development environment runs as `euid 0`, where `chmod 0o000`
denies nothing — permission-denied requirements are covered by tests that skip under root, the
pattern `tests/test_failures.py` already uses
([research R24](./research.md#r24--permissiondenied-cases-are-untestable-as-root)).

**Project Type**: Single-package CLI tool, source under `src/`. This feature extends the existing
package rather than adding to the structure.

**Performance Goals**: SC-017 — 10,000 regular files archived in under 30 s, with memory that does
not grow with the size of the largest file. Measured in Phase 0: **0.97 s** plain and **1.98 s**
gzip for 10,001 files, a 15–30× margin, so no optimisation work is planned. Memory flatness is
structural: `TarFile.addfile` streams each member through `shutil.copyfileobj` in `bufsize` chunks
([research R23](./research.md#r23--performance-sc017)).

**Constraints**: No third-party runtime imports. No change to `list` or `extract` behavior for any
input (FR-049). No configuration surface — behavior is fully determined by the command line. Output
is plain, unformatted, pipe-friendly text; exactly one summary line. File metadata is not a
guarantee. No uncaught traceback may ever reach the user. A rejected invocation must leave no new
archive and must not modify a pre-existing one.

**Scale/Scope**: One new subcommand, 28 functional requirements (FR-029 … FR-056), 10 success
criteria (SC-009 … SC-018). Roughly 60 lines added to one existing runtime file plus three new test
modules; one archive per invocation, local filesystem only.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0.

### Pre-Phase-0 evaluation

| Principle | Gate | Verdict |
|---|---|---|
| I. Standard Library Only | Runtime imports resolve only to stdlib or first-party modules; `pytest` is test-only and never imported by runtime code | **PASS** — the feature is `tarfile` plus `argparse`; the spec's mandated constraints and the user's planning input both say stdlib only |
| II. Fail Loudly | Every invalid input produces a specific diagnostic on stderr naming the offending value, plus a non-zero exit; no swallowed exceptions; no partial result in place of failure | **PASS** — FR-050 … FR-056 specify exactly this; the existing single `TarxError` type and single formatting site in `main` are reused, so no new path can exit silently |
| III. Every Requirement Is Testable | Each FR maps to ≥ 1 `pytest` test that fails when unmet, traceable by requirement id; error paths asserted on both diagnostic and status | **PASS** — all 28 FRs are stated as observable input → output/status; SC-016 restates the traceability duty, and the spec's requirement-numbering note keeps identifiers unique repository-wide |
| IV. Simplicity | Smallest design satisfying the spec; no speculative abstraction, config hook, or plugin seam; prefer function over class, module over package | **PASS** — see justifications below |

### Simplicity justifications (Principle IV requires these in writing)

This feature adds **no new structure at all** — no module, no package, no class, no configuration
surface. The three 001 structures it reuses (the `tarx` package, the single `TarxError` class, the
exit-status constants) were justified in [001's plan](../001-tar-archive-cli/plan.md) and are not
re-litigated here. What is new is four functions and a subparser block inside the existing
`src/tarx/cli.py`, each traced to a forcing requirement:

1. **`cmd_create(args)`** — the subcommand handler, parallel to `cmd_list` and `cmd_extract`.
   Forced by FR-029.
2. **A validation pass separate from the write pass.** Forced by FR-050 + FR-051 + FR-043: a
   rejected invocation must create no archive and must leave a pre-existing archive unmodified, and
   Phase 0 verified that opening the archive truncates it immediately. A single-pass design cannot
   satisfy this. The pass produces no objects — it raises `TarxError` or returns.
3. **A `classify` filter closure passed to `TarFile.add`.** Forced by FR-036 (skip entries of other
   kinds) and FR-039 (count regular-file members only). It is the one hook `TarFile.add` offers that
   sees exactly the members that will be written, so one closure satisfies both. A closure over a
   local counter rather than a class with a `count` attribute, per "prefer a function to a class".
4. **A plain integer counter, not 001's set of written paths.** Forced by FR-039 together with the
   spec's *A path named twice* edge case: `create` counts each stored regular file, including
   duplicates, whereas `extract` counts distinct destination paths. Different specified semantics,
   so the simpler structure is also the correct one
   ([research R22](./research.md#r22--counting-regularfile-members-and-the-fr048-countequality-ambiguity)).

Explicitly **not** built, per Principle IV: no `os.walk` traversal of our own (R13); no self-exclusion
check of our own (R14); no sorting of our own (R15); no temp-file-and-rename or rollback machinery
(R21); no de-duplication of overlapping source paths (spec edge case says not to); no
`format=`/`compresslevel`/`bufsize` tuning (R12, R23); no new `create.py` module or `tarx.archive`
subpackage (R25); no `Archive`/`SourcePath`/`Member` wrapper types over `TarFile` and `TarInfo`
(data-model.md records each as a plain string, stdlib object, or tuple).

### Post-Phase-1 re-evaluation

Re-checked against the generated design artifacts ([research.md](./research.md),
[data-model.md](./data-model.md),
[contracts/create-contract.md](./contracts/create-contract.md), [quickstart.md](./quickstart.md)).

| Principle | Verdict after design | Evidence |
|---|---|---|
| I. Standard Library Only | **PASS** | The design names every runtime import, and this feature adds none beyond `os` to a file that already imports `tarfile`, `argparse`, `posixpath`, `pathlib`, and `sys`. Research R12 rejected `mimetypes` (environment-dependent) and R13 rejected `shutil.make_archive` (cannot meet the contract) — both resolved *toward* the stdlib core rather than away from it. `pytest.ini` is test configuration and declares no runtime dependency. |
| II. Fail Loudly | **PASS** | The contract's diagnostics table gives a specific single-line message for all eleven specified failure conditions, each naming the offending path as typed. The write-pass backstop converts `OSError` into a named diagnostic plus exit 2 — the opposite of swallowing. Research R19 and R20 both resolved genuine specification gaps *toward* loud refusal rather than toward guessing (`.` refused rather than given an invented member name; `--overwrite` onto a FIFO refused rather than hanging on `open`). |
| III. Every Requirement Is Testable | **PASS** | Every contract row and data-model rule is phrased as an assertable input → output/status pair. The quickstart's acceptance checklist carries SC-016's per-FR traceability forward, adds the FR-049/SC-015 baseline to match (63 passed, 2 skipped), and requires the three spec-gap decisions to be pinned by tests so a future amendment surfaces as a failing test rather than silent drift. R24 records why two permission requirements must be covered by root-skipping tests and proposes a monkeypatched companion so the diagnostic and status are still asserted here. |
| IV. Simplicity | **PASS** | Post-design file count: **zero new runtime files**. One existing module gains four functions and a subparser block; three test modules are added. The four justified additions above are unchanged; Phase 1 added no fifth. Design decisions R13, R14, R15, R17, and R21 each resolved toward *less* code (delegate the walk, the self-exclusion, the ordering, and the header convention to `tarfile`; add no rollback). |

**No violations. Complexity Tracking below is intentionally empty.**

Three notes for transparency, not gate failures. Each is a place where behavior is decided in this
plan rather than in the specification, so each warrants a reviewer's attention and may warrant a
spec amendment:

1. **`.` (and an empty string) as a source path is refused with exit 2.** Phase 0 verified that
   accepting it produces member names `.`, `./photos`, `./photos/a.jpg` — every one carrying the
   leading `./` that FR-034 explicitly forbids. The current directory's relative path is empty, so
   it has no conformant member name ([research R19](./research.md#r19--sourcepath-containment-and-the-current-directory-as-a-source)).
2. **`--overwrite` onto an archive path that exists as neither a file nor a directory is refused
   with exit 2.** FR-044 covers only the regular-file case, and honouring the flag on a FIFO would
   *block* on `open` rather than fail. This leaves a documented asymmetry: the same FIFO yields
   exit 3 without the flag, because FR-043 is explicit that *any* existing path does
   ([research R20](./research.md#r20--the-archive-paths-prior-existence-and-kind-exit-2-versus-exit-3)).
3. **FR-048's count equality is read as scoped to non-overlapping source paths.** It cannot hold
   simultaneously with the *A path named twice* edge case, which requires `create` to store and
   count a duplicated file twice while FR-015 requires `extract` to count the destination path once.
   The more specific edge case governs, and both halves are asserted by tests
   ([research R22](./research.md#r22--counting-regularfile-members-and-the-fr048-countequality-ambiguity)).

A fourth item is a deliberate, specification-permitted consequence rather than an ambiguity: an
`--overwrite` run that fails part-way through writing leaves a truncated archive where the old one
was. FR-053 constrains what is *announced* ("MUST NOT report success"), and FR-051 is scoped to a
*rejected* invocation, which validation-before-open already covers. Temp-file-and-rename would add
cleanup paths, transient double disk usage, and a hole in FR-037 — so Principle IV forbids it absent
a requirement that asks for it ([research R21](./research.md#r21--failure-partway-through-writing-no-temporary-file-no-rollback)).

## Project Structure

### Documentation (this feature)

```text
specs/002-create-command/
├── plan.md                      # This file (/speckit-plan output)
├── spec.md                      # Feature specification (input)
├── research.md                  # Phase 0 output — decisions R12 … R25
├── data-model.md                # Phase 1 output — entities, validation rules, run state machine
├── quickstart.md                # Phase 1 output — runnable validation scenarios
├── contracts/
│   └── create-contract.md       # Phase 1 output — the `create` CLI surface
└── tasks.md                     # Phase 2 output (/speckit-tasks — NOT created here)
```

001's `contracts/cli-contract.md` is **not** edited: FR-049 freezes it, and the new contract
references it as still in force rather than restating or superseding it.

### Source Code (repository root)

```text
pytest.ini                       # unchanged — pythonpath = src, testpaths = tests

src/
└── tarx/
    ├── __init__.py              # unchanged — package marker, no logic
    ├── __main__.py              # unchanged — sys.exit(main(sys.argv[1:]))
    └── cli.py                   # MODIFIED (additive only):
                                 #   + archive_mode(path)            FR-040 … FR-042
                                 #   + validate_sources(paths)       FR-050, FR-052
                                 #   + validate_archive_target(...)  FR-043 … FR-046, FR-053
                                 #   + cmd_create(args)              FR-029 … FR-039, FR-053 … FR-056
                                 #   + a third add_parser block      FR-029, FR-030, FR-031
                                 #   + "create" in main()'s handlers FR-056
                                 #   ~ module and parser description strings
                                 #   = cmd_list, cmd_extract, open_archive, build_plan,
                                 #     write_members, escapes_destination, TarxError,
                                 #     EXIT_* all UNCHANGED (FR-049)

tests/
├── conftest.py                  # MODIFIED (additive only): source-tree fixtures for create;
│                                #   the existing archive fixtures and run_tarx are UNCHANGED
├── test_invocation.py           # unchanged (FR-049, SC-015)
├── test_list.py                 # unchanged
├── test_extract.py              # unchanged
├── test_compression.py          # unchanged
├── test_overwrite.py            # unchanged
├── test_failures.py             # unchanged
├── test_performance.py          # unchanged
├── test_create.py               # NEW — FR-029 … FR-042: invocation, members, naming, order,
│                                #   skipping, self-exclusion, summary line, compression
├── test_create_overwrite.py     # NEW — FR-043 … FR-046: exit 3, --overwrite, directory target
└── test_create_failures.py      # NEW — FR-050 … FR-056: diagnostics, containment, statuses,
                                 #   FR-047 … FR-049 round trip and the unchanged-behavior check
```

**Structure Decision**: Extend the existing single-package CLI layout; add nothing to it. All new
runtime code goes into `src/tarx/cli.py`, which keeps "all logic in one module" true for three
subcommands as it was for two, and keeps FR-055 and FR-056 true by construction — `main` remains the
only place that formats a diagnostic or chooses an exit status. A new `create.py` was rejected in
[research R25](./research.md#r25--where-the-code-lives): it buys a second file and two import edges
for 60 lines, and raises a shared-error-type question that currently has no cost.

Tests are split one file per requirement cluster, matching 001's convention so SC-016's
requirement-to-test traceability stays visible from the file tree. The names are prefixed
`test_create_*` so the 001 modules they parallel remain unambiguous, and the three round-trip
requirements (FR-047 … FR-049) live with the failure tests because that module is where the
pre-existing-suite check belongs. `conftest.py` gains source-*tree* fixtures (the existing ones all
build archives, which is the opposite of what `create` needs as input) and loses nothing; the
`run_tarx` subprocess runner already accepts a `cwd=` argument, which is exactly what `create` needs
since it names members relative to the current directory.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. The Constitution Check passes both pre-Phase-0 and post-Phase-1. This feature adds
zero new runtime files, zero new classes, and zero new runtime dependencies; the four additions that
exceed "one more function" are justified inline under *Simplicity justifications*, each traced to the
specific requirement that forces it.
