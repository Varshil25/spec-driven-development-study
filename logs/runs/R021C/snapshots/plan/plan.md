# Implementation Plan: Phone Redaction and Output Folder (`logredact`)

**Branch**: `002-phone-redaction-out-dir` | **Date**: 2026-11-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-phone-redaction-out-dir/spec.md`

## Summary

Two additions to the shipped `logredact` CLI, with everything else held byte-for-byte fixed.

**Phone redaction** is one new alternative appended to the existing compiled alternation in
`redact.py`: `\+[0-9]{8,15}(?![0-9])`, written last so that the alternation's own order delivers
FR-036's precedence (email → IPv4 → card → phone) with no new mechanism. The trailing lookahead is
the whole of FR-034 — the engine backtracks through every length from 15 down to 8 and the
lookahead fails at each one, so a 16-digit run produces no `[PHONE]` and still falls through to
the card rule as `+[CARD]`. `[0-9]` is spelled out rather than `\d` because `\d` matches
Arabic-Indic and other Unicode digits, which would break FR-033a in both directions. The two-dict
category table and the `Counter` tally each gain one entry, and the tally line gains a fourth
field. The scan loop in `redact_line` is untouched.

**The output folder** is confined to `cli.py`. `--out-dir DIR` is one value-taking argparse
option; `argparse` already produces FR-040's usage error when its value is missing and still
accepts it anywhere on the command line through the existing `parse_intermixed_args`. The work is
in the *ordering*, which FR-054 makes a requirement in its own right: usage and help are settled
first and touch nothing; `DIR` is then created with `os.makedirs(exist_ok=True)`, one call that
covers creation, acceptance of an existing directory, and FR-048's rejection of anything else;
then every operand's computed output path is swept for collision with that operand, by comparing
`(st_dev, st_ino)` so that differently spelled paths, symlinks, and hard links are all caught
(FR-049a); and only then is any input opened. Each operand opens its input *before* its output
file, which is what makes US4.1's "`DIR` exists but is empty" true after a failed read. Output
files use the same three text settings as stdout, so FR-044's byte equality is a consequence of
the configuration rather than something to verify at runtime. Output-side failures travel on the
existing non-`OSError` exception channel, generalised to carry a per-destination message, so an
unwritable output file and an unreadable input can no longer be confused inside the one loop that
now does both.

## Technical Context

**Language/Version**: Python 3.11+ — the floor set by the spec's Assumptions and the constitution.
No syntax below that floor is relied upon and nothing above 3.11 is used. Verified against
CPython 3.13 in this environment.

**Primary Dependencies**: None. Runtime imports stay inside the standard library and gain exactly
one module over feature 001: `re`, `argparse`, `sys`, `io`, `os`, `collections`, and
`contextlib` (for the one scoped `suppress` justified in Complexity Tracking). `pathlib` is
deliberately not added — `os.path` and `os.makedirs` cover every path operation needed and `os` is
already imported.

**Storage**: Files only. Input files are read and never modified. With `--out-dir` the tool writes
to one directory the caller named and nowhere else, which is what the constitution's "no writes
outside paths the caller named" permits.

**Testing**: `pytest`, the single development dependency the constitution allows, discoverable
from the repository root with no arguments. Contract-level cases run the real CLI as a subprocess
through the existing `tests/conftest.py::run_cli` helper and compare raw `bytes`, because
byte-exact stdout, byte-exact stderr, and a specific exit status are what the criteria are written
in. Two new modules (`test_phone.py`, `test_out_dir.py`) plus one (`test_preservation.py`) for the
"nothing else changed" criteria; four existing modules are amended.

**Target Platform**: Any POSIX-like system with CPython 3.11+, no install step. Developed and
verified on Linux. `(st_dev, st_ino)` identity is also meaningful on Windows under CPython 3.11+,
but no Windows verification is claimed.

**Project Type**: Single-package command-line tool — a stdin/stdout filter that now also has a
file-output mode.

**Performance Goals**: SC-019 — 100,000 lines in under 30 s, measured across all FILE operands of
one run together, so no per-operand or per-line cost may accumulate. Per-line work is unchanged
(one regex scan, one write); the new per-operand cost is one `open`/`close` pair and two `stat`
calls.

**Constraints**: SC-018 — memory bounded by the longest input line, not by total input size and
not by operand count: one line resident, one output file open at a time, no buffer-then-write and
no temp-file-and-rename scheme. FR-044, FR-052, FR-053 — byte-exact preservation of existing
behaviour, with exactly two documented differences (a `+` followed by 8–15 digits, and the tally
line). Exit status remains only ever 0 or 2.

**Scale/Scope**: No new runtime module. ~15 lines added to `redact.py`, ~90 lines added to
`cli.py`. 25 new functional requirements (FR-032 – FR-054 plus FR-033a and FR-049a) and 10 new
success criteria (SC-010 – SC-019) to cover with citing tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against Constitution v1.0.0.

| Gate | Principle | Status | Evidence |
|------|-----------|--------|----------|
| No third-party runtime import | I. Standard Library Only | PASS | One module added, `contextlib`, which is stdlib. `tests/test_stdlib_only.py` already walks `src/` and asserts every import resolves to a stdlib module; it needs no change to cover this. |
| Runs on bare CPython, no install step | I. Standard Library Only | PASS | `PYTHONPATH=src python -m logredact` is still the whole invocation. `pyproject.toml` stays pytest-configuration-only — no build backend, no dependency list. |
| Only `pytest` as a dev dependency | I. Standard Library Only | PASS | No new development tool. The user input for this plan reaffirms pytest as the runner. |
| Invalid input fails with a specific diagnostic and non-zero status | II. Fail Loudly | PASS | Six new failure paths, each naming what was wrong rather than that something was: the missing-operand conflict (FR-047), the directory (FR-048), the output file path (FR-048), the colliding input file (FR-049), the unreadable FILE (FR-050, unchanged), and argparse's own usage error for a valueless `--out-dir` (FR-040). Diagnostic forms are fixed in [contracts/cli.md](./contracts/cli.md). |
| No silent wrong answer | II. Fail Loudly | PASS | Three such answers were available here and all three are closed. A `wrote N files` line after a partial run is suppressed on every failing path (FR-045, SC-017). `--out-dir` with no operand would have discarded stdin or reported `wrote 0 files`; it is a usage error instead (FR-047). `--out-dir .` would have truncated the log being read; the identity check rejects it before any output is opened, and a per-operand re-check closes the one hole the up-front sweep leaves (FR-049, research R-107). |
| No bare `except:` / `except Exception: pass` | II. Fail Loudly | **PASS with one recorded exception** | No bare or broad handler. Every `except OSError` either re-raises as a path-naming diagnostic or converts to `OutputWriteError`; the run always still fails. Two narrower cases are recorded in Complexity Tracking rather than left implicit: `_file_identity`'s `except OSError: return None`, which is a query answering "no file here" and does not suppress any reportable failure, and one `contextlib.suppress(OSError)` on a cleanup close whose failure would otherwise mask the more specific diagnostic FR-050 requires. |
| Every FR maps to a citing test | III. Every Requirement Is Testable | PASS | Matrix in [quickstart.md](./quickstart.md) maps all 25 new FR identifiers and all 10 new SC identifiers. `tests/test_requirement_coverage.py` is extended to enumerate them, so the suite fails if any citation is lost (SC-015). |
| Error behaviour has message + signal tests | III. Every Requirement Is Testable | PASS | Each of the six failure paths gets a test asserting the diagnostic names the offending path or conflict, the exit status is 2, and `Traceback` is absent from stderr — which is SC-016 stated as a test rather than a hope. The FR-049 case additionally gets the differently-spelled-path and link variants SC-016 names. Research R-113 settles how to provoke each failure without relying on mode bits, which root ignores. |
| Smallest design that satisfies the spec | IV. Simplicity | PASS | No new module, no new class hierarchy, no abstraction over output destinations. Phone redaction is one regex fragment and two dict entries. The output folder is a handful of functions in `cli.py` operating on `str` paths. No staging, no rollback, no temp-and-rename — all three are explicitly ruled out by the spec's Assumptions and would be the speculative machinery this principle forbids. |
| Plain data over hierarchies | IV. Simplicity | PASS | `str` paths, `tuple[int, int]` file identity, `collections.Counter` tally. The one class is the pre-existing `OutputWriteError`, which gains two attributes rather than a subclass tree; the alternative of two exception classes was rejected as more structure for the same behaviour. |

**Pre-Phase 0 result**: PASS — no violations. One deviation anticipated (a scoped
`contextlib.suppress`) and carried into Phase 0 for resolution.

**Post-Phase 1 re-check**: PASS. The design artifacts add no dependency beyond `contextlib`, no
new module, and no structure that a requirement does not name. Two items are recorded below rather
than waved through, and one finding needs the spec owner's eye:

> **Finding for the spec owner (research [R-107](./research.md)).** FR-054's up-front collision
> sweep plus FR-049a's "an output path that does not yet exist cannot collide and MUST NOT be
> rejected" leave one gap: `--out-dir clean a.log clean/a.log`. At sweep time `clean/a.log` does
> not exist, so it must not be rejected; operand 1 then creates it; operand 2 reads it and opens
> the same path for writing, truncating its own input and reporting `wrote 2 files` with exit 0 —
> a silent wrong answer about the user's data. This plan closes it with a second identity check
> immediately before each output file is opened. That is FR-049 compliance (FR-049 fixes the
> obligation, FR-049a only the criterion, FR-054 only the earliest point) and it cannot fire on
> any scenario the spec requires to succeed, including the duplicate-base-name case US2.10. It is
> nonetheless behaviour no acceptance scenario describes, so it is flagged here rather than
> buried: if you would rather leave the gap open, deleting the re-check is a three-line change.

## Project Structure

### Documentation (this feature)

```text
specs/002-phone-redaction-out-dir/
├── plan.md              # This file
├── research.md          # Phase 0 output: R-101 - R-115
├── data-model.md        # Phase 1 output: the four amended/new run values
├── quickstart.md        # Phase 1 output: validation scenarios + requirement-to-test matrix
├── contracts/
│   ├── cli.md           # Amends 001's CLI contract: --out-dir, four-field tally, order of checks
│   └── redaction-patterns.md  # Amends 001's grammar: the phone category and the four-way precedence
├── checklists/
│   └── requirements.md  # Pre-existing spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

No file is added or removed. The tree below marks what each existing file does for this feature.

```text
pyproject.toml           # unchanged (pytest configuration only)

src/
└── logredact/
    ├── __init__.py      # unchanged
    ├── __main__.py      # unchanged
    ├── redact.py        # AMENDED: _PHONE fragment, 4th alternation branch, 2 dict entries
    └── cli.py           # AMENDED: --out-dir option, DIR setup, collision check, file streaming,
                         #          4-field tally, summary line, generalised OutputWriteError

tests/
├── conftest.py          # unchanged (run_cli already takes cwd, which the FR-049 cases need)
├── test_redact.py       # unchanged — its passing unamended is evidence for SC-012
├── test_phone.py        # NEW: FR-032 - FR-037, SC-011 as unit tests on redact_line
├── test_cli.py          # AMENDED: 8 tally assertions + 1 docstring gain `phones=N` (FR-038, FR-039)
├── test_out_dir.py      # NEW: FR-040 - FR-051, FR-054, SC-010, SC-016, SC-017 via subprocess
├── test_preservation.py # NEW: FR-052, FR-053, SC-012, SC-013
├── test_fidelity.py     # AMENDED: tally form + --out-dir byte equality (FR-044, SC-014)
├── test_performance.py  # AMENDED: tally form + --out-dir cases (SC-018, SC-019), marked slow
├── test_requirement_coverage.py  # AMENDED: enumerate FR-032 - FR-054, SC-010 - SC-019 (SC-015)
└── test_stdlib_only.py  # unchanged — already covers the new import
```

**Structure Decision**: the feature-001 split stands, and this feature is a test of it rather
than a reason to revisit it. The phone change is purely a recognition rule, so it lands entirely
in the pure text layer `redact.py` and is tested as string in / string out — fast, exhaustive, no
subprocess. The output folder is purely about streams, paths, exit statuses, and the order of
side effects, so it lands entirely in the I/O layer `cli.py` and is tested through the real
process, because that is the only place byte-exact stderr and a specific exit status are
observable. Neither change needs the other's module. No new runtime module is introduced: an
`output.py` holding the three or four short functions the directory mode needs would be a file
boundary where there is no test-shape boundary, which Principle IV forbids. Test modules *are*
split by feature area, because `tests/test_cli.py` is already long and the new material is
independently runnable.

The one structural rule worth stating explicitly: `redact.py` still knows nothing about files,
streams, or exit statuses, and `cli.py` still contains no recognition logic. `--out-dir` does not
change that line.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| `contextlib.suppress(OSError)` around the cleanup close of an output file — Principle II forbids suppressing exceptions | `TextIOWrapper.close()` flushes, so a close is a real write site and FR-048 names it. But when streaming has *already* failed, the cleanup close still tries to flush buffered output; if that flush fails too, an unguarded close replaces the diagnostic with its own. FR-050 requires the unreadable FILE to be the thing named, so the first failure must win. Scope is one statement, on a path that runs only when the run has already failed and is already exiting 2, and the suppressed information is strictly less specific than what is reported. | A plain `with open(...)` block was rejected: its implicit close raises a bare `OSError` from the `with` statement's exit, which the enclosing read handler catches and misreports as "cannot read FILE" — the exact confusion `OutputWriteError` exists to prevent. Re-raising the close failure unconditionally was rejected because it inverts FR-050's required attribution. |
| `_file_identity` returning `None` from `except OSError` (reads like a swallowed error) | FR-049a requires sameness to be decided by filesystem identity, and the overwhelmingly common case is an output path that does not exist yet — so "cannot stat" is the normal answer, not an exceptional one. `None` is a truthful answer to the question "which file, if any, does this path name?", not a sentinel standing in for a failed operation, and no reportable failure is lost: a missing *input* file is still reported, by the existing read-failure path with FR-028's diagnostic, which is what US4.1 requires. | `os.path.samefile` wrapped in `try/except` was rejected: it is the same two `stat` calls, but it raises when either path is missing, making exception handling load-bearing on the common path. Comparing `os.path.realpath` strings was rejected: it resolves symlinks but not hard links, and the spec's Clarifications answer named filesystem identity, not canonical paths. |
| A second collision check per operand, in addition to FR-054's up-front sweep (duplicated check) | Closes the silent-data-loss gap described in the Post-Phase 1 finding above and detailed in research R-107. Without it, `--out-dir clean a.log clean/a.log` truncates its own input and exits 0 with a `wrote 2 files` line. Two `stat` calls per operand; it cannot fire on any scenario the spec requires to succeed. | Dropping the up-front sweep and relying on the per-operand check alone was rejected because FR-054 and US4.7c require a collision in a *later* operand to fail the run before an *earlier* operand's output file is written. Dropping the per-operand check leaves the gap open; that is the spec owner's call, and the finding above says so. |
| `OutputWriteError` gaining a `message` and an `is_stdout` field (a class, where Principle IV prefers plain data) | The class itself is pre-existing and already justified in the feature-001 plan: it must not inherit from `OSError` so that an output failure raised inside the per-source loop is not caught by that loop's read handler. This feature makes the hazard sharper rather than new — both directions of I/O now happen inside that one loop — and FR-048 and FR-050 demand different diagnostics from it. The two fields are what let one handler serve both destinations. | Two exception classes (`StdoutWriteError`, `OutputFileWriteError`) were rejected: a base class plus two subclasses plus an `isinstance` branch is more structure than a bool for identical behaviour. Passing a formatting callable into the streaming helper was rejected as a function-typed parameter where plain data suffices. |
