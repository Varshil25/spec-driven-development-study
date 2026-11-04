# Implementation Plan: Shared Expense Settle-Up

**Branch**: `001-expense-splitter` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-expense-splitter/spec.md`

## Summary

A single-command CLI that reads a strict three-column UTF-8 CSV of group expenses, charges every
supplied participant an equal share of the group total, and prints a deterministic, minimal-ish list
of `PAYER pays PAYEE AMOUNT` transfers that zeroes every net balance.

Technical approach: all money is held as **integer cents** end to end — never `float`, never
`Decimal` — so no rounding step can lose or invent a cent. Amount text is validated by an explicit
regular expression rather than by a permissive numeric parser, which is what makes FR-004's
rejections (`1e3`, `-5.00`, `1.005`, `$5`, `1,200.00`, `inf`, `nan`) fall out of one rule instead of
a list of special cases. The leftover-cent allocation and the greedy largest-debt/largest-credit
settlement are both tie-broken by ascending Unicode code-point name order, which Python's default
`str` comparison already provides with no locale involvement, giving the byte-identical output
SC-005 requires. Validation is fail-fast in a fixed order (command line → file → header → rows by
line number) to satisfy FR-010a with no error-collecting machinery.

## Technical Context

**Language/Version**: Python 3.11 or newer (CPython; development host runs 3.13.17). No syntax or
library feature newer than 3.11 is used.

**Primary Dependencies**: None at runtime — Python standard library only (`argparse`, `csv`,
`dataclasses`, `re`, `sys`). `pytest` is a development/test dependency only, which the constitution
permits by name.

**Storage**: N/A. One CSV file is opened read-only; nothing is written, created, or deleted (FR-021,
SC-008).

**Testing**: `pytest`, run from the repository root. `pytest.ini` sets `pythonpath = src` (a core
pytest ini option, not a plugin) so tests import `splitter` with no installation step and no
third-party tooling.

**Target Platform**: Any OS with CPython 3.11+ (Linux, macOS, Windows). No network access.

**Project Type**: Single project — one CLI package plus its test suite.

**Performance Goals**: 1,000 expense rows across 50 participants settled and printed in well under
two seconds (SC-006). Parsing is O(rows); share and balance computation is O(participants); the
greedy settlement re-scans the balance map each transfer, so O(participants²) ≈ 2,500 operations at
50 participants — chosen over a heap for simplicity (see [research.md](./research.md) D7).

**Constraints**: Standard library only; deterministic and locale-independent output; read-only
filesystem access; exit status 0 / 1 / 2 exactly as FR-020 specifies; results on stdout and
diagnostics on stderr, never mixed.

**Scale/Scope**: One user, one invocation, no persistence or configuration. Expected inputs are
thousands of rows and tens of participants; no streaming or pagination needed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v1.0.0.

| Gate | Principle | Pre-Phase 0 | Post-Phase 1 | Evidence |
|------|-----------|-------------|--------------|----------|
| No third-party runtime import | I. Standard Library Only | PASS | PASS | Design imports only `argparse`, `csv`, `dataclasses`, `re`, `sys`. `pytest` is test-only and named as permitted. No vendored source. |
| Runtime is Python 3.11+ only | Additional Constraints | PASS | PASS | No feature newer than 3.11 in the design; `X \| Y` annotations and `dataclasses` are 3.10-or-earlier features. |
| Every invalid input fails loudly | II. Fail Loudly | PASS | PASS | Every rejection path raises `SplitterError`, is printed to stderr by `cli.main`, and exits non-zero. No default or partial settlement is ever printed on error (FR-019). `contracts/cli.md` pins the exact message for each. |
| No bare/blanket exception swallowing | II. Fail Loudly | PASS | PASS | Only two `except` clauses in the design, both narrow: `OSError` (file unreadable) and `UnicodeDecodeError` (undecodable bytes); each converts to an explicit `SplitterError`, neither swallows. |
| No secrets in output | II / Secrets | PASS | PASS | The tool handles no credentials; messages echo only the user's own path, row number, and field value. |
| Every requirement maps to a test | III. Every Requirement Is Testable | PASS | PASS | Traceability table below maps FR-001…FR-021 and SC-001…SC-008 to a named test file; each error path gets its own test asserting both message content and exit status. |
| Smallest design that satisfies the spec | IV. Simplicity | PASS | PASS | Six source files, no abstraction layers, no plugin seams, no configuration surface, no third option anywhere. Rejected alternatives recorded in `research.md` rather than built. |
| Text-in/text-out CLI convention | Interfaces | PASS | PASS | Payments to stdout, diagnostics to stderr, status in exit code (FR-016, FR-019, FR-020). |
| No hidden state / no writes | No hidden state | PASS | PASS | Single read-only `open()`; no temp files, caches, config files, or network calls. |
| Tests discoverable from repo root | Layout | PASS | PASS | `tests/` at root, `pytest.ini` committed, `pytest` with no arguments collects everything. |

**Result**: all gates pass. Complexity Tracking is empty — there is no deviation to justify.

### Requirement traceability

Every functional requirement maps to at least one planned test file; `/speckit-tasks` will expand
these into individual test cases whose names cite the requirement id (Principle III).

| Requirement | Covering test file |
|-------------|--------------------|
| FR-001 (argument shape), FR-020 (exit 2 on CLI misuse) | `tests/test_cli_invocation.py` |
| FR-002, FR-002a, FR-010 (header, BOM, UTF-8, row length) | `tests/test_expenses.py`, `tests/test_cli_errors.py` |
| FR-003, FR-004, FR-005 (amount grammar, rejections, zero) | `tests/test_expenses.py` |
| FR-006 (unknown payer) | `tests/test_expenses.py`, `tests/test_cli_errors.py` |
| FR-007, FR-008 (empty / duplicate participants) | `tests/test_cli_errors.py` |
| FR-009 (unreadable path) | `tests/test_cli_errors.py` |
| FR-010a (first problem only) | `tests/test_cli_errors.py` |
| FR-011, FR-011a, FR-012 (shares, name order, balances) | `tests/test_settle.py` |
| FR-013, FR-014, FR-015 (payment set, conservation, determinism) | `tests/test_settle.py` |
| FR-016, FR-017 (line format, silence when settled) | `tests/test_cli_output.py` |
| FR-018 (description is inert) | `tests/test_cli_output.py` |
| FR-019 (one stderr message, empty stdout) | `tests/test_cli_errors.py` |
| FR-021, SC-008 (no file mutation) | `tests/test_cli_output.py` |
| SC-001 (reference case) | `tests/test_cli_output.py` |
| SC-002, SC-003 (conservation and bound over many inputs) | `tests/test_settle.py` |
| SC-004 (11 malformed cases) | `tests/test_cli_errors.py` |
| SC-005 (byte-identical repeat runs, locale-independent) | `tests/test_cli_output.py` |
| SC-006 (1,000 rows × 50 participants under 2 s) | `tests/test_performance.py` |
| SC-007 (message names row and value) | `tests/test_cli_errors.py` |

## Project Structure

### Documentation (this feature)

```text
specs/001-expense-splitter/
├── spec.md              # Feature specification (/speckit-specify, /speckit-clarify)
├── plan.md              # This file (/speckit-plan)
├── research.md          # Phase 0 output — design decisions and rejected alternatives
├── data-model.md        # Phase 1 output — entities, invariants, transformation pipeline
├── quickstart.md        # Phase 1 output — how to run and validate the feature
├── contracts/
│   ├── cli.md           # Phase 1 output — user-facing CLI contract (the normative interface)
│   └── python-api.md    # Phase 1 output — internal module signatures tests call directly
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pytest.ini               # pythonpath = src; nothing else needed to run the suite

src/
└── splitter/
    ├── __init__.py      # package marker, no logic
    ├── __main__.py      # `python -m splitter` entry: raise SystemExit(main())
    ├── errors.py        # SplitterError — the one exception type the CLI turns into exit 1
    ├── expenses.py      # Expense; participant-list parsing, CSV reading, amount grammar
    ├── settle.py        # shares, net balances, greedy settlement, Payment
    └── cli.py           # argparse wiring, orchestration, formatting, stderr/exit handling

tests/
├── conftest.py              # tmp CSV writer fixture; repo-root/src path for subprocess runs
├── test_cli_invocation.py   # argparse surface and exit status 2
├── test_cli_output.py       # stdout format, silence, determinism, read-only guarantee
├── test_cli_errors.py       # one test per rejection: message text + empty stdout + exit 1
├── test_expenses.py         # header, BOM, encoding, row length, amount grammar, payer check
├── test_settle.py           # share allocation, balance invariants, settlement properties
└── test_performance.py      # SC-006 ceiling
```

**Structure Decision**: Single-project layout with the `splitter` package under `src/` exactly as the
spec's Given Constraints require, and a flat `tests/` tree at the repository root. The package is
split along the two seams the specification itself draws — reading/validating input
(`expenses.py`) and computing the settlement (`settle.py`) — with `cli.py` holding only the I/O
boundary. That split is what lets `test_settle.py` assert the cent-conservation invariants of
FR-014/SC-002 directly on pure functions, instead of inferring them from printed text. No
`models/`, `services/`, or `lib/` subpackages: at this size they would be empty indirection, which
Principle IV forbids.

Tests are not split into `contract/`, `integration/`, and `unit/` directories; a flat `tests/` tree
named by subject is fewer moving parts for a suite this small, and `pytest` from the root collects
it with no configuration beyond the committed `pytest.ini`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. No abstraction layer, configuration option, plugin seam, or generality beyond the
stated requirements is introduced, so there is nothing to justify here.
