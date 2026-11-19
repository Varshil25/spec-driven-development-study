# Implementation Plan: Phone Redaction and Output Folder

**Branch**: `002-phone-redaction-out-dir` | **Date**: 2026-11-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-phone-redaction-out-dir/spec.md`

## Summary

Two additive changes to the working `logredact` tool, with everything else byte-identical. First, a
fourth redaction category: a `+` followed by 8–15 digits becomes `[PHONE]`, and the `--count` summary
gains a fourth field, `emails=N ips=N cards=N phones=N`. Second, a new `--out-dir DIR` option that
writes each `FILE` operand's redacted lines to `DIR/<basename>` instead of to standard output,
creating `DIR` and its missing parents, replacing any file of that name, and reporting
`wrote N files` on standard output when every operand has been processed.

Technical approach (from [research.md](./research.md)):

- **Phone recognition is one new alternative in the existing compiled pattern** —
  `PHONE = r"\+\d{8,15}(?!\d)"` appended as `(?P<phone>…)` after `email|ip|card`. The length range
  lives in the quantifier and the "no fragment of an over-long run" rule in the trailing `(?!\d)`
  guard, so the category needs no code validation and the scan loop gains no branch. Precedence falls
  out of alternation order, as it already does for the other three: `email` before `phone` is
  load-bearing, because both can begin at the same `+` and FR-004 requires email to win; `phone`
  beats a Luhn-valid 8–15 digit card by starting one character earlier, which is the leftmost-match
  rule the tool already uses.
- **The tally becomes a 4-tuple** `(emails, ips, cards, phones)`, ordered as the summary's fields, and
  `phones` is appended to the summary line so positional consumers of the first three keep working.
- **`--out-dir` is a plain `argparse` store option**, compatible with the existing
  `parse_intermixed_args` call so it is accepted in any position. Zero operands with `--out-dir` is
  rejected up front; `DIR` is then created once with `os.makedirs(..., exist_ok=True)`; each operand's
  input is opened **before** its output, so an unreadable input leaves no output file behind; the
  output is opened with the *same* stream settings as stdout (`utf-8`, `surrogateescape`,
  `newline=""`), which is what makes each output file byte-identical to what stdout would have
  received. Diagnostics are attributed by the operation that raised: input failures name the operand,
  output failures name the joined output path.

No new module, no new class, no new runtime import beyond what `cli.py` already imports. The change
is roughly 40 lines of source across the two existing modules.

The design was prototyped and executed against the specification before this plan was written: all
19 concrete phone examples plus 8 feature-001 regression cases and 17 further boundary cases produce
the specified text and tally (27/27 and 17/17); `argparse` intermixed parsing, `os.makedirs`
behaviour on every edge case the spec names, output-file byte fidelity, and throughput were all
measured rather than assumed. The 100,000-line budget is unaffected: 0.96 s against 10 s, with
`--out-dir` adding 0.04 s.

## Technical Context

**Language/Version**: Python 3.11+ (CPython), unchanged from feature 001 and matching the
constitution's pinned minimum. Verified on CPython 3.13.17. Python 3.11's zero-cost exception
handling is what makes the per-write `try` of research R7 free.

**Primary Dependencies**: None at runtime. Standard library only, and no import beyond the `re`,
`argparse`, `sys`, `os` already imported — `os.makedirs`, `os.path.basename` and `os.path.join` come
from the module `cli.py` already uses.

**Storage**: N/A for state, but **new**: the tool now writes files to disk when `--out-dir` is given.
One output file per `FILE` operand, inside the named directory, opened for writing and closed before
the next input opens. It still holds no state between lines and never writes to an input.

**Testing**: `pytest`, discoverable by a plain `pytest` run from the repository root. The existing
`tests/conftest.py` (`src/` on `sys.path`; `run_cli` subprocess helper returning `bytes` streams) is
reused unchanged; `tmp_path` provides the output directories.

**Target Platform**: Any platform with CPython 3.11+; developed and verified on Linux. No OS-specific
API is added. The FR-017 tests are chosen so they fail for an unprivileged *and* a root user
(research R12).

**Project Type**: Single-project command-line tool, run as `python -m logredact` with `src/` on
`PYTHONPATH`. Unchanged.

**Performance Goals**: 100,000-line log redacted in under 10 s with and without `--out-dir`
(SC-010); measured 0.96 s for the redaction and 0.04 s for the file copy. Memory must not grow with
line count **or with operand count** — at most one input and one output are open at a time.

**Constraints**: Offline, no install step, no build step, no configuration file. Every behaviour not
named in this spec must stay byte-identical to the current tool: any input with no `+`-prefixed 8–15
digit run must produce identical output (FR-005, SC-006). Exit 0 on complete output, 2 on any run
that cannot produce it.

**Scale/Scope**: ~40 lines added across `redact.py` and `cli.py`; 21 functional requirements, 11
success criteria, 21 edge cases, all requiring named tests. Three new test files plus updates to
five existing ones.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version **1.0.1**. Gates are the five in "Development Workflow & Quality Gates".

| Gate | Principle | Pre-Phase 0 | Post-Phase 1 | Evidence |
|------|-----------|-------------|--------------|----------|
| 1. Every FR has a test naming it | III | PASS | PASS | [contracts/cli.md](./contracts/cli.md) maps FR-001…FR-021 to the test file that must name each; SC-002 demands the same |
| 2. `pytest` passes in full, nothing skipped | III | PASS | PASS | No skip or xfail is planned. The unwritable-output tests use file-type and path-length obstacles that defeat root as well, so none needs a privilege guard (research R12) |
| 3. Invalid input exercised by tests, Principle II conformant | II | PASS | PASS | Unreadable input, uncreatable `DIR`, `DIR` that is a regular file, output name colliding with a subdirectory, unwritable `DIR`, and `--out-dir` with no operands all exit 2 with a diagnostic naming the offending path **and** the reason |
| 4. No non-stdlib runtime import | I | PASS | PASS | No new import at all; `pytest` stays test-only |
| 5. No unjustified abstraction | IV | PASS | PASS | No new module, class, or configuration. The three structural choices are justified in one sentence each below |

**Principle II notes**: results stay on stdout and errors on stderr. The `--count` summary remains on
stderr, and the new `wrote N files` status line goes to stdout, which is where the spec puts it and
which keeps stdout machine-readable in output-folder mode. Two new silent-wrong-answer risks were
identified and closed by design rather than left to chance:

- `--out-dir` with zero operands could plausibly have been ignored, or satisfied by inventing a
  file name for standard input. Both would produce a result the user did not ask for, so FR-018
  makes it a loud failure stating what was expected.
- A failed run in output-folder mode leaves real files on disk from earlier operands. Suppressing
  the `wrote N files` line (FR-015) is what stops a partially filled folder reading as a complete
  one; the diagnostic and exit 2 name which operand stopped it.

**Principle IV justifications** (one sentence each, as the constitution requires):

- *Appending a fourth alternative to the existing pattern rather than adding a phone pass*: a second
  pass cannot express FR-004's "no text reused", so the one-pass pattern is the only design that
  satisfies the requirement.
- *Splitting the input-failure and output-failure handlers*: FR-015 and FR-017 require different
  diagnostics naming different paths, and only the raising operation knows which path is at fault.
- *A 4-tuple rather than a dict, `Counter`, or class for the tally*: the spec fixes the category set
  at four with nothing to configure, so a keyed structure would add indirection with no second value.
- Nothing else is added: no category registry, no output-naming strategy, no atomic-write machinery,
  no new module.

**Open items** (none block Phase 1; both recorded in research.md):

1. **SC-004 wording vs the tally arity** (research R3). Changing `redact_line`'s tally from a 3-tuple
   to a 4-tuple means ~20 assertions in `tests/test_redact_line.py`, `tests/test_luhn.py` and
   `tests/test_performance.py` must gain a fourth element, which is a second kind of edit beyond the
   "summary format change" SC-004 literally permits. No asserted behaviour changes — each edit
   appends ` 0` or a fourth name — and these are unit assertions on an internal function rather than
   acceptance scenarios. Flagged for the spec owner to confirm the reading; it does not affect the
   architecture.
2. **Residual partial-output window** (research R7). The input-before-output ordering fully satisfies
   the spec's "no output file is created for an input that cannot be read", because every unreadable
   input the suite can construct fails at `open()`. If both opens succeed and an I/O error then
   occurs mid-stream (ENOSPC, hardware), the run still fails loudly with a diagnostic and exit 2 but
   may leave a partial output file — narrower than the Edge Cases phrase "no empty or partial file".
   Nothing is built to remove it because the removal could not be covered by a test, and Principle
   III makes untestable machinery incomplete work. Recorded as an accepted consequence, not an
   accepted constitutional violation.

## Project Structure

### Documentation (this feature)

```text
specs/002-phone-redaction-out-dir/
├── plan.md                 # This file (/speckit-plan command output)
├── spec.md                 # Feature specification (input)
├── research.md             # Phase 0 output — 12 items resolved
├── data-model.md           # Phase 1 output — delta on 001's entities
├── quickstart.md           # Phase 1 output — 12 validation scenarios
├── contracts/
│   ├── cli.md              # Amended command-line contract: --out-dir, four-field summary, new diagnostics, FR coverage map
│   └── redaction-rules.md  # Amended recognition contract: the phone rule and its precedence rows
├── checklists/
│   └── requirements.md     # Specification quality checklist (pre-existing)
└── tasks.md                # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

Both contracts are **deltas**: they amend the feature 001 contracts of the same names, which remain
authoritative for everything not restated.

### Source Code (repository root)

```text
src/
└── logredact/
    ├── __init__.py      # Unchanged (docstring may name the fourth category)
    ├── __main__.py      # Unchanged
    ├── cli.py           # CHANGED: --out-dir argument; zero-operand check; makedirs; per-operand
    │                    #   output open/close; "wrote N files"; four-field summary
    └── redact.py        # CHANGED: PHONE pattern; phone alternative appended to COMBINED;
                         #   [PHONE] placeholder; four-element tally

tests/
├── conftest.py          # Unchanged
├── test_phone.py        # NEW — US1/US3 phone grammar, boundaries, precedence: FR-001..FR-004
├── test_out_dir.py      # NEW — US2 happy paths: FR-008..FR-014, FR-019..FR-021
├── test_out_dir_errors.py  # NEW — US2 failure paths: FR-015..FR-018
├── test_redact_line.py  # UPDATED — four-element tally; phone precedence unit cases; FR-005
├── test_count.py        # UPDATED — four-field summary string: FR-006, FR-007
├── test_luhn.py         # UPDATED — four-element tally unpacking only
├── test_performance.py  # UPDATED — four-field summary; new --out-dir timing case: SC-010
├── test_errors.py       # Unchanged — its summary assertions are `b"emails=" not in ...`, which still hold
├── test_fidelity.py     # UPDATED — adds output-file byte fidelity (FR-014) and near-miss-phone
│                        #   fidelity (FR-005); existing cases unchanged
├── test_stdin.py        # Unchanged
└── test_files.py        # Unchanged
```

Verified: no input anywhere in the existing suite or in the 001 artifacts contains a `+` followed by
8 or more digits, so no 001 expectation changes other than the summary string and the tally arity.

**Structure Decision**: The existing single-project layout is kept exactly — package under
`src/logredact/`, tests under `tests/`, `python -m logredact` with `src/` on `PYTHONPATH`, plain
`pytest` from the root with no configuration file. No module is added: the phone rule belongs beside
the three patterns it shares a compiled regex with, and the output-folder logic belongs in the one
function that already opens inputs and owns the exit status. A separate `output.py` or `phone.py`
would split code that must be read together and would add indirection with no second caller
(Principle IV).

Test files are added rather than grown: `test_phone.py` keeps User Story 1's independent test
independently runnable, and the output-folder work is split happy-path/failure-path because the two
have different fixtures (a folder to inspect versus a folder that must *not* appear) and because
constitution gate 3 requires the error paths to be visible as a set. Most updates to the existing
files are mechanical — the tally's fourth element and the summary string. Two are substantive and
belong where they are: the phone/card and phone/email precedence unit cases go in
`test_redact_line.py` next to the existing FR-015 precedence tests, and the output-file fidelity case
goes in `test_fidelity.py`, which is already the home of every byte-level assertion.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitutional violations. All five gates pass pre- and post-design. No dependency, module, class,
or configuration was added; the two structural decisions that add anything at all (a second OSError
handler per operand, and a 4-tuple in place of a 3-tuple) are each justified above in one sentence
tied to a current requirement. The two open items listed in the Constitution Check are a
specification-wording question and a recorded consequence of a design the constitution's own
principles select — neither is an accepted violation.

## Phase Status

- [x] Phase 0: research.md — all 12 items resolved, 0 NEEDS CLARIFICATION remaining
- [x] Phase 1: data-model.md, contracts/cli.md, contracts/redaction-rules.md, quickstart.md
- [x] Constitution Check re-evaluated post-design
- [ ] Phase 2: tasks.md (`/speckit-tasks`)
- [ ] Phase 3: implementation (`/speckit-implement`)
