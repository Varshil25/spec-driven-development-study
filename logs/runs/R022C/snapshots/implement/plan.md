# Implementation Plan: Phone Redaction and Output Folder

**Branch**: `002-phone-redact-out-dir` | **Date**: 2026-11-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-phone-redact-out-dir/spec.md`

## Summary

Add a fourth redaction rule and a second output destination to the shipped `logredact` CLI,
changing nothing else (FR-027).

- **Phone numbers** — a `+` immediately followed by 8-15 digits becomes `[PHONE]`. Implemented by
  adding a third branch, `\+\d{8,15}(?!\d)`, to the existing leftmost-first email/IPv4
  alternation. Branch order *is* the precedence FR-006 requires (email → IPv4 → phone), and
  phone-before-card follows from the existing two-pass structure. No new pass, no arbitration
  code.
- **`--count`** — the tally line becomes `emails=N ips=N cards=N phones=N`. `Counts` gains a
  fourth field, appended and defaulted so every existing unit test keeps passing while still
  asserting the same fact (SC-005).
- **`--out-dir DIR`** — with one or more FILE arguments, each FILE's redacted lines go to
  `DIR/{basename(FILE)}` instead of stdout; `DIR` and its missing parents are created up front;
  stdout carries only `wrote N files`. `--out-dir` with no FILE, with no value, an uncreatable
  `DIR`, or an unwritable output file each exit 2 with a diagnostic naming the offending path.

The whole change lands in the two existing modules — roughly 15 lines in `redact.py` and 50 in
`__main__.py` — plus new tests. No new source module, no new dependency, no new abstraction.

Design rationale is in [research.md](./research.md) (decisions D-101…D-110, each verified against
the spec's edge cases by execution before being written down). Entity rules are in
[data-model.md](./data-model.md), the external interface in [contracts/cli.md](./contracts/cli.md),
and the validation procedure plus the FR → test map in [quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.11+ (user input; Constitution "Additional Constraints"; existing
`pyproject.toml` declares `requires-python = ">=3.11"`)

**Primary Dependencies**: None. Standard library only — `re`, `io`, `os`, `signal`, `sys`,
`dataclasses`. `os.makedirs` and `os.path.basename`/`os.path.join` are the only additions to the
existing import set (Constitution Principle I; user input)

**Storage**: N/A — no persistent state, no schema. The feature writes output files to a
caller-named folder, which is product output rather than storage

**Testing**: pytest, no plugins, no services, run as a bare `pytest` from the repository root
(user input; Constitution Principle III; existing `[tool.pytest.ini_options]` with
`pythonpath = ["src"]`)

**Target Platform**: Any POSIX platform with CPython 3.11+. Windows is not excluded: the existing
`hasattr(signal, "SIGPIPE")` guard stays, and `os.path` handles separators, but the test suite's
permission-based failure cases are POSIX-shaped and already use skips

**Project Type**: Single-package CLI tool — `src/logredact/` with `tests/` beside it

**Performance Goals**: 100 000 lines in under 10 s to **both** destinations, and memory flat in
file size — a 1 MB line and a 1 GB file both fine (SC-007, carrying forward `001/SC-006`). Met by
construction: the phone branch folds into the existing single alternation pass rather than adding
a scan, and output files stream line by line exactly as stdout does. To be re-measured, not
assumed — [quickstart.md](./quickstart.md) Scenario 6

**Constraints**: Line-oriented streaming with one line resident at a time; UTF-8 with
`newline=""` and `errors="strict"` on every stream *and* every output file (that identity is
FR-015); fixed non-configurable placeholders; diagnostics to stderr with exit status 2; no
behaviour outside the spec's 27 requirements may change (FR-027, SC-005)

**Scale/Scope**: ~200 existing source lines, growing by ~65. 27 functional requirements, of which
24 are new behaviour and FR-027 is a preservation guarantee over the 25 requirements of
[001](../001-logredact-cli/spec.md). Pre-existing suite: 31 passed, 1 skipped — the baseline
SC-005 is measured against

No `NEEDS CLARIFICATION` items remain. The three that would have been open — language version,
dependency policy, test framework — were fixed by the user's input to `/speckit-plan` and are
already encoded in the repository's `pyproject.toml`; see
[research.md "Status of unknowns"](./research.md#status-of-unknowns).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Gates derived from [.specify/memory/constitution.md](../../.specify/memory/constitution.md)
v1.0.0.

### Pre-Phase 0 (initial)

| Gate | Status | Evidence |
|---|---|---|
| **I. Standard Library Only** | PASS | `re`, `io`, `os`, `signal`, `sys`, `dataclasses`. No new dependency; `pyproject.toml` keeps `dependencies = []`. Nothing in the feature suggests a third-party need |
| **II. Fail Loudly** | PASS | Five new failure modes, each specified with a diagnostic naming the offending path and exit status 2 (FR-012, FR-020, FR-023…FR-025). FR-020 exists *because* the silent alternative — streaming to stdout when `--out-dir` has no FILE — is the "plausible-looking wrong answer" the principle forbids |
| **III. Every Requirement Is Testable** | PASS | All 27 FRs are pass/fail assertions on stdout bytes, stderr bytes, file contents, and exit status. SC-004 requires a named test per FR; SC-006 requires message *and* status per failure mode |
| **IV. Simplicity** | PASS | No new module, class, or configuration surface. The phone rule is one pattern constant plus one alternation branch; `--out-dir` is one `str`, one `makedirs`, and one nested `open` |
| Language floor (3.11+) | PASS | No syntax below the floor; nothing newer than 3.11 used |
| Layout and bare-`pytest` discovery | PASS | Existing `src/` + `tests/` with `pythonpath = ["src"]`; new test files sit in `tests/` |
| CLI text-in/text-out | PASS | Results to stdout (`wrote N files`), diagnostics to stderr, 0 on success, 2 on failure |
| Validation boundary | PASS | Argument and folder validation happen in `__main__.py` before any input is read (research D-106); `redact_text` keeps assuming a decoded `str` and stays I/O-free |

**Initial gate result: PASS.** No violation to justify, so [Complexity Tracking](#complexity-tracking)
stays empty.

### Post-Phase 1 (re-check after design)

Re-evaluated against the artifacts actually produced, not the intentions above.

| Gate | Status | What the design did |
|---|---|---|
| **I. Standard Library Only** | PASS | Final import delta is exactly `os` in `__main__.py`. No vendoring, no optional dependency |
| **II. Fail Loudly** | PASS | [data-model.md §7](./data-model.md#7-diagnostics-and-exit-status) gives one table of six failures, each with its subject, reason source, and status. R7.3 makes input and output failures *distinguishable* rather than collapsing them into one message; R7.6 keeps every `except` narrow (`OSError`, `UnicodeDecodeError`) and used only to add path context. No bare `except`, no fallback default |
| **III. Every Requirement Is Testable** | PASS | [quickstart.md](./quickstart.md#requirement--test-map-sc-004) maps all 27 FRs to named tests carrying the requirement id, and all 8 SCs to where they are proven. The five new failure modes each get a test asserting the diagnostic *and* the status |
| **IV. Simplicity** | PASS, with one judgement recorded below | Still no new module, class hierarchy, registry, or config object. Two entities were added to the data model (`Output destination`, `Output folder`) and both are a `str` plus a file handle, not types |
| Language floor, layout, CLI shape, validation boundary | PASS | Unchanged by the design |

**One design choice worth recording** (not a violation, so it is not in Complexity Tracking):
`Counts` gains an `__add__` method (research D-103). Under Principle IV this needs a word, since
adding a method is adding a moving part. It is a **net deletion**: the CLI sums counts at two
sites, which with four fields would be eight `+=` statements, each a place to transpose a field
name silently. `__add__` replaces all eight with two `total = total + counts` lines. Nothing
speculative is attached to it — no `__radd__`, no `__sub__`, no `total` property — so it has
exactly one current purpose and one fewer failure mode than the code it removes.

**Deliberately left undone**, each because no requirement asks for it and Principle IV forbids
speculative scope:

- A self-overwrite guard for `--out-dir .` — the spec flags it as a known hazard and explicitly
  declines to specify a refusal (R6.8).
- Atomic or temp-file-and-rename output writes — excluded by the spec's Assumptions (R5.7).
- `--out-dir=DIR` support, `--out-dir` with stdin, preserved input directory structure, per-file
  progress output, pluralising `wrote 1 files` — all out of scope.
- Updating the `USAGE` string to mention `--out-dir`. This one is a **real cost accepted under
  protest**, and it is the only place where the design does something a reviewer may read as a
  defect: FR-027 and SC-005 require the existing usage-line test to pass unchanged, so the usage
  text keeps its v1 wording and does not advertise the new option. Recorded in full, with the
  one-line reversal if the spec intended otherwise, in research
  [D-105](./research.md#d-105-the-usage-string-stays-byte-identical) — the right place to settle it
  is `/speckit-clarify`.

**Post-design gate result: PASS.**

## Project Structure

### Documentation (this feature)

```text
specs/002-phone-redact-out-dir/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature specification (/speckit-specify)
├── research.md          # Phase 0 output — decisions D-101…D-110
├── data-model.md        # Phase 1 output — entity and rule deltas against 001
├── quickstart.md        # Phase 1 output — validation scenarios + FR → test map
├── contracts/
│   └── cli.md           # Phase 1 output — the v2 command-line contract
├── checklists/
│   └── requirements.md  # Pre-existing (/speckit-checklist)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

The existing single-package layout is kept as it is. Nothing is created or moved; four files
change and two test files are added.

```text
src/logredact/
├── __init__.py          # MODIFIED: module docstring mentions phone numbers (Counts/redact_text exports unchanged)
├── __main__.py          # MODIFIED: --out-dir parsing, folder creation, per-file output, `wrote N files`, 4-figure tally
└── redact.py            # MODIFIED: _PHONE pattern, third alternation branch, Counts.phones + __add__

tests/
├── conftest.py          # UNCHANGED: the run_cli() subprocess helper already covers both modes
├── test_redact.py       # UNCHANGED (passes as-is — Counts.phones defaults to 0)
├── test_cli.py          # MODIFIED: tally assertions only, 7 lines (the SC-005 exception)
├── test_corpus.py       # MODIFIED: phone numbers added to the leak corpus, `+` text to the false-positive corpus
├── test_phone.py        # NEW: FR-001…FR-006, FR-009 — engine-level, no subprocess
└── test_out_dir.py      # NEW: FR-007, FR-011…FR-027 — CLI-level, via run_cli()

pyproject.toml           # UNCHANGED: still requires-python >=3.11, dependencies = []
```

**Structure Decision**: unchanged from `001` — a single package under `src/` with `tests/`
beside it, discoverable by a bare `pytest` thanks to `pythonpath = ["src"]`. The feature adds no
module because it adds no new concern: the phone rule belongs beside the three rules in
`redact.py`, and output destination selection belongs in the CLI layer that already owns stream
I/O and exit status. Splitting an output-writer module out of `__main__.py` would be an
abstraction for a single caller, which Principle IV prohibits without justification, and there is
none.

The two **new test files** are a deliberate choice in the other direction: `test_phone.py` and
`test_out_dir.py` could have gone into `test_redact.py` and `test_cli.py`, but keeping them
separate leaves the v1 files almost untouched, which is what makes SC-005 ("the earlier suite
passes unchanged") auditable at a glance rather than by diffing interleaved test functions.

### Change surface by requirement

| File | Change | Requirements |
|---|---|---|
| `redact.py` | `_PHONE` constant + `PHONE_PLACEHOLDER`; rename/extend the compiled alternation to three branches; `replace()` handles the `phone` group | FR-001…FR-007 |
| `redact.py` | `Counts.phones` field (last, defaulted) and `Counts.__add__` | FR-008, FR-009, SC-005 |
| `__main__.py` | indexed parse loop; `--out-dir` consumes the next token; missing-value usage error | FR-011, FR-012, FR-021 |
| `__main__.py` | `--out-dir` with no FILE rejected; `os.makedirs(..., exist_ok=True)` before the loop | FR-016, FR-020, FR-024 |
| `__main__.py` | per-FILE output open (`basename`, mode `"w"`, stdout's own open arguments), nested error handling | FR-013…FR-015, FR-017, FR-023, FR-025 |
| `__main__.py` | `_copy_redacted` returns `Counts`; `wrote N files` then the four-figure tally | FR-008, FR-010, FR-018, FR-019, FR-026 |
| `__main__.py` | `USAGE` **not** changed | FR-027, SC-005 |

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. Both constitution checks passed without deviation, so there is nothing to justify
here. The one judgement call that touches Principle IV — `Counts.__add__` — is recorded in the
[post-design check](#post-phase-1-re-check-after-design) above, where it is argued as a net
reduction in moving parts rather than claimed as an exception.
