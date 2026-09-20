# Implementation Plan: Expense Splitter

**Branch**: `001-expense-splitter` | **Date**: 2026-09-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-expense-splitter/spec.md`

## Summary

A command-line tool that reads a CSV of shared group expenses (`payer, amount, description`) plus a separately supplied comma-separated participant list, computes each participant's net balance against an equal share of the group total, and prints a minimal list of debtor→creditor transfers that settles every balance to zero. All money is handled as integer cents so no cent is ever lost or invented, and any indivisible remainder is distributed deterministically. Malformed input fails loudly on stderr with a non-zero exit and no stdout settlement.

Technical approach: a standard-library-only Python package `src/splitter/` split by responsibility — argument parsing/exit codes (`cli.py`), CSV reading and validation (`parser.py`), balance and minimal-transaction computation (`settle.py`), and integer-cent helpers (`money.py`). Runnable as `python -m splitter`. Tested with `pytest` in `tests/`.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: None at runtime (Python standard library only: `argparse`, `csv`, `sys`, `decimal` for exact parse-to-cents). `pytest` is a development-only dependency.

**Storage**: N/A (reads a CSV file passed as an argument; no persistence)

**Testing**: pytest

**Target Platform**: Any platform with CPython 3.11+ (Linux, macOS, Windows)

**Project Type**: Single-project CLI utility

**Performance Goals**: Handle a typical group (up to a few dozen expenses) instantly in a single invocation; no formal throughput target (SC-006)

**Constraints**: Standard library only at runtime; integer-cent arithmetic end to end (no floats holding money); byte-identical deterministic output; diagnostics to stderr with non-zero exit, results to stdout

**Scale/Scope**: Small utility — 4 source modules plus `__main__.py`, one test package; input sized to human-authored expense lists (tens to low hundreds of rows)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance in this plan |
|-----------|-------------------------|
| I. Standard Library Only | Runtime imports limited to stdlib (`argparse`, `csv`, `sys`, `decimal`). `pytest` is test-only and never imported by `src/splitter/`. **PASS** |
| II. Exact Money Arithmetic | All money held as `int` cents. `decimal.Decimal` used only to parse the input string to an exact cent count (rejecting >2 decimal places), never to hold running money as a float. Share distribution allocates remainder cents deterministically; conservation asserted by tests. **PASS** |
| III. Fail Loudly | `parser.py` raises typed validation errors; `cli.py` maps them to a clear stderr message + non-zero exit, and prints nothing to stdout on any rejection (FR-011..FR-016). **PASS** |
| IV. Every Requirement Is Testable | Each FR maps to at least one pytest test (see [quickstart.md](./quickstart.md) and contract tests). Money conservation and error paths are explicit test classes. **PASS** |
| V. Deterministic Output | Participant order derived from the supplied list order (not hashing); payments produced by a deterministic settlement strategy; remainder distribution is order-defined. Byte-identical output asserted (FR-017, SC-005). **PASS** |

**Initial gate**: PASS — no violations, Complexity Tracking not required.

**Post-design re-check**: PASS — the Phase 1 design (see [data-model.md](./data-model.md), [contracts/](./contracts/)) introduces no third-party runtime dependency, keeps all money as integer cents, and preserves deterministic ordering. No new violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-expense-splitter/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── cli.md           # CLI invocation, output, and exit-code contract
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── splitter/
    ├── __init__.py      # Package marker; may expose version
    ├── __main__.py      # Enables `python -m splitter`; delegates to cli.main()
    ├── cli.py           # argparse setup, orchestration, stdout/stderr, exit codes
    ├── parser.py        # CSV reading, header/field validation, payer-in-participants check
    ├── settle.py        # net-balance computation + minimal-transaction settlement
    └── money.py         # integer-cent helpers: parse-to-cents, format-from-cents

tests/
├── __init__.py
├── test_money.py        # cent parsing/formatting, rejection of >2 decimals & negatives
├── test_settle.py       # balances, minimality, conservation, uneven-split remainder
├── test_parser.py       # header/field/payer validation, participant-list validation
└── test_cli.py          # end-to-end: exit codes, stdout settlement, stderr errors

pyproject.toml           # dev metadata + pytest config (no runtime deps)
```

**Structure Decision**: Single-project CLI layout. Runtime code lives in an importable package `src/splitter/` divided along the four responsibilities named in the technical input, with `__main__.py` providing the `python -m splitter` entry point. Tests mirror the modules one-to-one plus an end-to-end CLI test. No installable packaging beyond an optional `pyproject.toml` for pytest configuration; the tool runs directly from source with `python -m splitter` (with `src/` on the path).

## Complexity Tracking

> No constitution violations. No entries required.
