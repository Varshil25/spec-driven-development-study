# Implementation Plan: Redact Personal Data From Log Files

**Branch**: `001-redact-log-pii` | **Date**: 2026-11-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-redact-log-pii/spec.md`

## Summary

A streaming command-line filter, `python -m logredact [--count] [FILE ...]`, that reads log text
from named files or standard input and writes it back with email addresses, IPv4 addresses, and
Luhn-valid payment card numbers replaced by `[EMAIL]`, `[IP]`, and `[CARD]`.

**Technical approach**: one precompiled regex alternation (`email | ip | card`) applied per line
with `re.sub` and a callback. The regex engine's own leftmost-first, ordered-alternation,
resume-after-match semantics deliver FR-018, FR-019, and FR-020 without any hand-written scanner;
the callback performs the two checks regexes cannot express (IPv4 octet range, card length +
Luhn) and returns the candidate unchanged when they fail. I/O is line-at-a-time with UTF-8 and
`errors="surrogateescape"`, which keeps memory flat and round-trips undecodable bytes. Three
counters accumulate across all inputs and are reported only on a complete run. Standard library
only; `pytest` for tests.

Every mechanism above was executed and verified during Phase 0 — including the two that
contradict the obvious first implementation (`argparse.parse_args` cannot accept `--count`
between two filenames; an unhandled `BrokenPipeError` exits 1 with a traceback). See
[research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.11+ (user-specified; 3.11 is also the floor for the possessive
quantifiers the card pattern relies on — see research.md R-004)

**Primary Dependencies**: None. Standard library only — `re`, `argparse`, `sys`, `os`
(Constitution Principle I; user-specified)

**Storage**: N/A — streaming filter, no persistence, no state between runs

**Testing**: `pytest` (user-specified; Constitution), test-time only, imported by nothing under
`src/`

**Target Platform**: Any OS with CPython 3.11+. The broken-pipe path (FR-028) is POSIX-shaped
but degrades safely elsewhere; CI target is Linux

**Project Type**: Single-project CLI tool

**Performance Goals**: 1,000,000 lines in under 60 s; memory flat with respect to input size
(SC-007)

**Constraints**: Byte-identical output for non-matching text, including CRLF, a missing final
newline, and invalid UTF-8 bytes (SC-003); behaviour independent of locale and encoding
environment (FR-005a); exit status restricted to `{0, 2}` (SC-006)

**Scale/Scope**: ~29 functional requirements, 3 redaction types, 1 command, ~250 lines of
implementation across 4 small modules

No NEEDS CLARIFICATION items: the spec's five clarifications settled encoding, early pipe close,
numeric-domain emails, invalid usage, and directories-as-FILE, and Phase 0 resolved the
remaining technical unknowns.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.0.

| Principle | Gate | Pre-Phase 0 | Post-Phase 1 |
|-----------|------|-------------|--------------|
| **I. Standard Library Only** | No third-party runtime import; runnable on a bare interpreter with no `pip install`; `pytest` confined to tests | **PASS** — `re`, `argparse`, `sys`, `os` only; run via `PYTHONPATH=src python -m logredact`, no install step | **PASS** — design adds no dependency. `pytest.ini` is test-time configuration, not a runtime import (research.md R-009) |
| **II. Fail Loudly** | Invalid input produces a specific diagnostic naming the offending input plus a non-zero status; no broad or swallowing `except` | **PASS** — FR-025/FR-029 require exactly this; FR-026 forbids presenting an incomplete run as complete | **PASS** — two handlers, both narrow: `except OSError` re-reports with the filename as given and exits 2; `except BrokenPipeError` exits deliberately. Neither hides an error. See *Complexity Tracking* for the second |
| **III. Every Requirement Is Testable** | Every FR maps to a failing-when-unmet `pytest` test; every error path asserts both signal and diagnostic | **PASS** — all 29 FRs are observable through stdout/stderr/exit status; SC-005 demands full coverage | **PASS** — the module split exists to make the pure matching logic unit-testable while CLI tests assert the real contract through a subprocess, which is the only way to observe a true exit status and a true broken pipe |
| **IV. Simplicity** | Smallest design that satisfies the spec; no speculative abstraction; fewer moving parts wins | **PASS** — one command, no configuration, no plugin surface | **PASS** — no class hierarchy, no registry, no abstraction over "redaction type" beyond an ordered alternation and a `lastgroup` tag; 4 modules, each with one job. Rejected alternatives recorded in research.md |

**Additional constraints**: Python 3 with the minimum version stated above ✓; `pytest` under
`tests/`, bare invocation from the repository root ✓; text in/out contract — results to stdout,
diagnostics to stderr, 0 on success and non-zero on failure ✓; no hidden state — encoding is
pinned rather than inherited from the environment, and counters are run-local, never global ✓.

**Result**: PASS at both gates. No principle requires a deviation.

## Project Structure

### Documentation (this feature)

```text
specs/001-redact-log-pii/
├── plan.md                        # This file (/speckit-plan command output)
├── spec.md                        # Feature specification
├── research.md                    # Phase 0 output — 9 decisions, all verified
├── data-model.md                  # Phase 1 output — run-level entities
├── quickstart.md                  # Phase 1 output — 9 runnable validation scenarios
├── contracts/                     # Phase 1 output
│   ├── cli-contract.md            # Invocation, streams, exit status, failure behaviour
│   └── redaction-rules.md         # Patterns, validation, precedence, worked examples
├── checklists/                    # Pre-existing quality checklists
└── tasks.md                       # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/
└── logredact/
    ├── __init__.py                # Package marker; no logic
    ├── __main__.py                # Entry point for `python -m logredact`; delegates to cli.main
    ├── redact.py                  # Pure matching core: patterns, Luhn, redact_line(text) -> (text, counts)
    └── cli.py                     # argparse, stream setup, source iteration, errors, exit status

tests/
├── unit/
│   ├── test_patterns.py           # Per-type recognition and non-recognition (FR-006 … FR-017)
│   ├── test_luhn.py               # Checksum in isolation (FR-014, FR-015)
│   ├── test_precedence.py         # Leftmost-wins, tie-break, no rescan (FR-018 … FR-020)
│   └── test_counting.py           # Counter increments per replacement (FR-022)
└── cli/
    ├── test_invocation.py         # stdin vs files, order, argument positions (FR-001 … FR-004)
    ├── test_output_fidelity.py    # Byte-for-byte, CRLF, no final newline, invalid UTF-8, locale (FR-005, FR-005a, FR-005b)
    ├── test_count_flag.py         # Summary format, placement, suppression (FR-021 … FR-023)
    ├── test_failures.py           # Missing/unreadable/directory, fail-fast, usage errors (FR-025, FR-026, FR-027, FR-029)
    └── test_broken_pipe.py        # Early close: silent, exit 0 (FR-028)

pytest.ini                         # pythonpath = src, so a bare `pytest` from the root works
```

**Structure Decision**: Single project, as the spec dictates — a `logredact` package under
`src/`, runnable as `python -m logredact` with `src/` on `PYTHONPATH`, and tests under `tests/`.

The four source files are the minimum that keeps the matching core testable without a live
process (Principle III) while leaving the I/O, failure, and exit-status concerns in one place:

- `redact.py` is pure — text in, text and counts out. No I/O, no `sys`, no exit codes. Every
  recognition rule is unit-testable directly.
- `cli.py` owns everything that touches the process: argument parsing, stream reconfiguration,
  opening sources in order, the two narrow exception handlers, and the exit status.
- `__main__.py` exists only because `python -m` requires it.

Splitting further (a module per redaction type, a separate Luhn module, an I/O layer) would add
indirection no requirement asks for; merging it all into `__main__.py` would force every
recognition test through a subprocess. The `tests/unit` and `tests/cli` split mirrors this:
units for the pure core, subprocess tests for everything the contract states about the process.

## Phase 0: Research — complete

[research.md](./research.md) records nine decisions, each verified by execution before being
written down:

| ID | Decision | Serves |
|----|----------|--------|
| R-001 | `argparse` with **`parse_intermixed_args`** — `parse_args` is verified to reject `a.log --count b.log` | FR-001, FR-029 |
| R-002 | UTF-8 + `errors="surrogateescape"`, `newline="\n"` read / `""` write — byte round-trip verified | FR-005, FR-005a, FR-005b |
| R-003 | Single compiled alternation with `re.sub` + callback; validation returns text unchanged on failure | FR-018, FR-019, FR-020 |
| R-004 | Exact patterns and boundary lookarounds; possessive quantifiers for the maximal card candidate | FR-007 … FR-017 |
| R-005 | Luhn as a small pure function, applied after the length test | FR-014, FR-015 |
| R-006 | `except BrokenPipeError` **plus** `os.dup2` to `/dev/null` — verified silent, exit 0 | FR-028 |
| R-007 | `except OSError` around open and read; diagnostic names the file as given; stop and exit 2 | FR-025 … FR-027 |
| R-008 | Line-at-a-time iteration, nothing accumulated | SC-007 |
| R-009 | `tests/` with `pytest.ini` `pythonpath = src`; CLI tests via `subprocess` | Constitution |

The whole design was run against every acceptance scenario and edge case in the spec; all
produced the specified output.

## Phase 1: Design & Contracts — complete

- **[data-model.md](./data-model.md)** — four entities (redaction type, input source, line,
  redaction counts) with their fields, validation rules, and the per-source state transitions
  (`pending → open → exhausted | failed | abandoned`), plus the complete run-level state.
- **[contracts/cli-contract.md](./contracts/cli-contract.md)** — the public interface: invocation
  grammar, input selection, stream assignment, encoding and line fidelity, the exact `--count`
  summary format, the `{0, 2}` exit-status set, all three failure behaviours, and eleven worked
  command/output/status examples.
- **[contracts/redaction-rules.md](./contracts/redaction-rules.md)** — the scanning algorithm and
  the three patterns with their validation steps and per-type recognition tables.
- **[quickstart.md](./quickstart.md)** — nine runnable validation scenarios covering all four
  user stories plus byte fidelity, locale independence, broken pipe, and the performance target,
  with an acceptance checklist.

### Note for review (not a deviation)

The maximal-card-candidate rule, which the spec fixes through its doubled-separator edge case,
has a consequence worth seeing explicitly: a card joined by a single separator to an adjacent
number forms one larger candidate. `code 7-4111 1111 1111 1111` is a 17-digit candidate that
fails Luhn, so **the card is not redacted** (verified). The converse over-redacts harmlessly —
`id 42 4111 1111 1111 1111` passes Luhn as 18 digits and is replaced whole, which is the spec's
stated safe direction. Implementing it any other way would contradict the spec's own edge case,
so the plan follows the spec; raising the under-redaction case to a spec amendment is a product
decision, not a planning one. Documented in research.md R-004 and the redaction-rules contract.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No Constitution Check violations. One entry is recorded here because it is the single place the
design handles an error without a diagnostic, and a reviewer should see it justified rather than
discover it:

| Item | Why needed | Simpler alternative rejected because |
|------|------------|--------------------------------------|
| `except BrokenPipeError` + `os.dup2(devnull, 1)` (FR-028) | FR-028 requires exit 0 with **nothing** on stderr when the consumer closes early. Verified: unhandled, Python prints a traceback and exits 1; caught without the `dup2`, the interpreter's shutdown flush still writes `Exception ignored in:` to stderr | Letting it propagate violates FR-028 on both status and stderr. `signal(SIGPIPE, SIG_DFL)` yields status 141, not 0. This is not Principle II being bypassed: an early-closing consumer is a normal end of work, not unvalidated input — the handler catches exactly one exception type and exits deliberately |

## Next step

Run `/speckit-tasks` to generate `tasks.md`. The user-story priorities in the spec (P1 piped
redaction → P2 named files → P3 `--count` → P4 failure reporting) give the implementation order,
and SC-005 requires every functional requirement to carry at least one covering test.
