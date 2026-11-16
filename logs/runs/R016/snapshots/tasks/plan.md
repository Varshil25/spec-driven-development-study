# Implementation Plan: Log Redaction CLI

**Branch**: `001-logredact-cli` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-logredact-cli/spec.md`

## Summary

A single-purpose, zero-dependency CLI that streams log text from named files or standard input to
standard output, replacing email addresses with `[EMAIL]`, IPv4 addresses with `[IP]`, and
Luhn-valid 13–19 digit card numbers with `[CARD]`, leaving every other byte untouched. `--count`
adds a one-line tally on standard error after all output is written; an unreadable file produces a
diagnostic naming the file and exit status 2.

Technical approach (from [research.md](./research.md)): one module-level compiled regex with ordered
alternation `email | ip | card` drives an explicit `search(line, pos)` loop, which gives FR-015's
left-to-right email→IPv4→card precedence directly from alternation order while keeping all scanning
in the C regex engine. Because a card candidate can be rejected by the Luhn check — something `re`
cannot express — the loop restarts one character into a rejected candidate rather than skipping
past it; this is the detail that keeps `123 1.2.3.4` yielding `123 [IP]`. Byte fidelity comes from
opening every stream with `newline=""` and `errors="surrogateescape"` and writing lines with their
terminators attached, so `\r\n`, a missing final newline, and non-UTF-8 bytes all survive unchanged.
Processing is line-at-a-time, so memory is flat regardless of log size.

The design was prototyped and verified against all 25 concrete input/output examples in the spec
(100% pass) and benchmarked at 1.36 s for 100,000 dense lines against the 10 s budget, before this
plan was written.

## Technical Context

**Language/Version**: Python 3.11+ (CPython). Pins the constitution's `TODO(PYTHON_VERSION)`; see
research R1. Verified on CPython 3.13.17.

**Primary Dependencies**: None at runtime. Standard library only: `re`, `argparse`, `sys`, `os`.

**Storage**: N/A — the tool reads streams and files and writes to standard output; it never writes to
disk and holds no state between lines.

**Testing**: `pytest`, discoverable by a plain `pytest` run from the repository root. `tests/conftest.py`
puts `src/` on `sys.path` and provides a `subprocess`-based CLI helper (research R8).

**Target Platform**: Any platform with CPython 3.11+; developed and verified on Linux. No OS-specific
API is used (`os.dup2` on the broken-pipe path is available on all supported platforms).

**Project Type**: Single-project command-line tool, run as `python -m logredact` with `src/` on
`PYTHONPATH`.

**Performance Goals**: 100,000-line log redacted in under 10 s (SC-008); measured 1.36 s on a
worst-case dense line. Memory must not grow with line count.

**Constraints**: Offline, no install step, no build step, no configuration file. Output byte-identical
to input except for redactions. Exit 0 on complete output, 2 on any run that cannot produce complete
output.

**Scale/Scope**: ~250–300 lines of source across 4 files; 23 functional requirements, 9 success
criteria, 18 edge cases, all of which must be covered by named tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0. Gates are the five in "Development Workflow & Quality Gates".

| Gate | Principle | Pre-Phase 0 | Post-Phase 1 | Evidence |
|------|-----------|-------------|--------------|----------|
| 1. Every FR has a test naming it | III | PASS | PASS | `contracts/` maps FR-001…FR-023 to the test file that covers each; SC-002 demands the same |
| 2. `pytest` passes in full, nothing skipped | III | PASS (n/a yet) | PASS | No skip or xfail is planned; the broken-pipe and permission-denied tests run unconditionally on Linux |
| 3. Invalid input exercised by tests, Principle II conformant | II | PASS | PASS | Unreadable file, directory operand, unknown option, closed stdout all exit non-zero with a diagnostic naming the cause on stderr; FR-021 requires the file name *and* the reason |
| 4. No non-stdlib runtime import | I | PASS | PASS | Runtime imports are `re`, `argparse`, `sys`, `os`. `pytest` is test-only, the constitution's single permitted exception |
| 5. No unjustified abstraction | IV | PASS | PASS | Four source files, no classes, no plugin/registry, no configurable placeholders; each split justified in one sentence below |

**Principle II notes**: errors go to stderr and results to stdout throughout; the `--count` summary
is on stderr specifically so stdout stays pure log text (FR-020). No failure path returns a
plausible-looking partial result silently — the one case where partial output has already been
written (a later file fails) is required by FR-021 to still exit 2 with a diagnostic, so the user
cannot mistake a truncated log for a complete one.

**Principle IV justifications** (one sentence each, as the constitution requires):

- `redact.py` separate from `cli.py`: the redaction engine is pure text→text and must be unit-tested
  per-line without spawning a process or touching the filesystem.
- `__main__.py` separate from `cli.py`: `__main__.py` must stay a two-line shim so that importing the
  CLI from tests does not depend on module-execution semantics.
- Nothing else: no category registry, no configurable placeholder, no `Redactor` class — the spec
  fixes exactly three categories and three placeholders, so a dict-driven abstraction would add
  indirection with no second value to configure.

**Deviations and open items** (none block Phase 1; all recorded in research.md):

1. The constitution's `TODO(PYTHON_VERSION)` must be amended to "3.11" before the first
   implementation task — the constitution itself requires that, and this plan supplies the value.
2. The spec contradicts itself twice; both are resolved in research R3/R4 by the reading that
   satisfies the most spec statements and redacts more rather than less, and both are listed for the
   spec owner to confirm in `spec.md`. Neither changes the architecture.

## Project Structure

### Documentation (this feature)

```text
specs/001-logredact-cli/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature specification (input)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── cli.md           # Command-line contract: usage, streams, exit codes, FR coverage map
│   └── redaction-rules.md  # Recognition grammar and precedence contract
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── logredact/
    ├── __init__.py      # Package marker; docstring only, no re-exports
    ├── __main__.py      # Shim: sys.exit(main(sys.argv[1:]))
    ├── cli.py           # argparse, stream/file opening, summary, exit codes, broken-pipe handling
    └── redact.py        # Compiled patterns, luhn(), redact_line() -> (text, counts)

tests/
├── conftest.py          # Puts src/ on sys.path; run_cli subprocess helper
├── test_redact_line.py  # Unit: engine per line — FR-006..FR-016 and pattern edge cases
├── test_luhn.py         # Unit: Luhn checksum and 13–19 digit length rule — FR-013
├── test_stdin.py        # US1 end-to-end: stdin → stdout — FR-003, FR-006, FR-007
├── test_files.py        # US2 end-to-end: file operands, order, repeats, empty — FR-002, FR-023
├── test_count.py        # US3 end-to-end: --count placement, totals, stream separation — FR-004, FR-017..FR-020
├── test_errors.py       # US4 end-to-end: missing/unreadable/directory, unknown option, exit 2 — FR-005, FR-021, FR-022
├── test_fidelity.py     # Byte fidelity: \r\n, no trailing newline, non-UTF-8, long/blank lines — FR-007
└── test_performance.py  # SC-008: 100k lines under budget, flat memory
```

**Structure Decision**: Single-project layout with the package under `src/logredact/` and tests under
`tests/`, exactly as the spec's Assumptions require (`python -m logredact` with `src/` on
`PYTHONPATH`) and as the constitution requires (tests under `tests/`, plain `pytest` from the root).
The template's `models/`, `services/`, `lib/` subdivision is dropped: there is no model layer, no
service layer, and one pure function plus one I/O driver do not justify directories (Principle IV).
Test files are split by user story and by concern so each story remains independently verifiable, as
the spec's "Independent Test" entries require; `contract/integration/unit` directories are not used
because the contract here *is* the CLI, and splitting nine small files across three directories would
add navigation cost without separating anything.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitutional violations. All five gates pass pre- and post-design; no abstraction, dependency,
or structure was added beyond what a current requirement demands. The two spec conflicts and the
constitution's unpinned Python version are tracked as open items above, not as accepted violations.

## Phase Status

- [x] Phase 0: research.md — all 9 unknowns resolved, 0 NEEDS CLARIFICATION remaining
- [x] Phase 1: data-model.md, contracts/cli.md, contracts/redaction-rules.md, quickstart.md
- [x] Constitution Check re-evaluated post-design
- [x] Phase 2: tasks.md — 26 tasks across 7 phases (`/speckit-tasks`)
