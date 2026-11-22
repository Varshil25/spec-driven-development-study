# Implementation Plan: Log Redaction CLI

**Branch**: `001-logredact-cli` | **Date**: 2026-11-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-logredact-cli/spec.md`

## Summary

A stdlib-only Python CLI, `python -m logredact [--count] [FILE ...]`, that streams text line by
line from named files (in argument order) or standard input, replaces email addresses with
`[EMAIL]`, IPv4 addresses with `[IP]`, and Luhn-valid 13-19 digit payment card numbers with
`[CARD]`, and writes everything else through byte-for-byte. `--count` adds one
`emails=N ips=N cards=N` tally line on standard error after all output. An unreadable FILE
(missing, permission-denied, directory, or undecodable bytes) is named on standard error and
stops the run with exit status 2.

Technical approach, validated by executable probes during Phase 0 (see
[research.md](./research.md)):

- **Two compiled-regex passes per line.** Pass A is one `re.sub` over an
  `(?P<email>…)|(?P<ip>…)` alternation — Python's leftmost-first alternation semantics deliver
  FR-017's "leftmost wins, email before IPv4" rule for free. Pass B scans the result for card
  windows and applies the Luhn check in Python, because a checksum cannot be expressed as a
  regex. Replacement text is never re-examined by either pass (FR-018).
- **A hand-written 15-line argument parser**, not `argparse`: `argparse` with `nargs="*"`
  provably rejects `logredact a.log --count b.log`, which FR-001 requires to work.
- **`newline=""` text I/O on both ends** so line terminators (including `\r\n` and a missing
  final newline) survive unchanged (FR-006), with UTF-8 forced explicitly rather than inherited
  from the locale.
- **`SIGPIPE` restored to `SIG_DFL`** so `| head` terminates the tool the way `cat` terminates,
  with no traceback.
- **Streaming, one line in memory at a time**, which satisfies SC-006 at ~1.4s per 100k lines
  with memory flat in file size.

## Technical Context

**Language/Version**: Python 3.11+ (floor set by spec Assumptions and Constitution "Additional
Constraints"; probes were run on the 3.13.17 interpreter present in this environment — no syntax
below the 3.11 floor is used)

**Primary Dependencies**: None at runtime — standard library only (`re`, `sys`, `os`, `signal`,
`io`, `dataclasses`). Development-only: `pytest` (9.1.1 available here; `>=7` required for the
built-in `pythonpath` setting)

**Storage**: N/A — the tool reads inputs and writes streams; it never writes, modifies, or
deletes a file

**Testing**: `pytest`, no plugins, discoverable by a bare `pytest` from the repository root.
Unit tests call the redaction functions directly; CLI tests spawn
`sys.executable -m logredact` in a subprocess to assert real stdout/stderr separation and exit
status

**Target Platform**: POSIX (Linux/macOS) command line; Windows works apart from the
`SIGPIPE` refinement, which is applied only where the signal exists

**Project Type**: Single-project CLI tool with a `src/` package layout

**Performance Goals**: 100,000-line file in under 10 seconds (SC-006). Measured during Phase 0:
**1.40 s** for a 100,000-line / 10.3 MB log with a redactable email, IPv4, and card on every
line — a ~7x margin

**Constraints**: Memory bounded by the longest single line, not by input size (SC-006, 1 GB file
must complete); output is byte-identical to input except for the three replacements (FR-005,
FR-006, SC-003); no configuration file, environment variable, or network access (SC-007)

**Scale/Scope**: ~200 lines of implementation across 3 source files; 25 functional requirements
(FR-001…FR-025) each mapped to at least one named test (SC-004)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0 (ratified 2026-11-20).

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Standard Library Only** | No third-party runtime import; no runtime dependency in packaging metadata; no vendored code | **PASS** — design uses only `re`, `sys`, `os`, `signal`, `io`, `dataclasses`. `pyproject.toml` declares `dependencies = []`; `pytest` is isolated in `[project.optional-dependencies] dev` so the test-tooling exemption stays visible. Luhn is ~8 lines of arithmetic, which is exactly the "write it rather than carry a dependency" trade the principle calls for. |
| **II. Fail Loudly** | Diagnostics name the offending input, go to stderr, exit non-zero; no bare `except`; no fallback default for invalid input | **PASS** — every read failure is reported as `logredact: <path>: <reason>` on stderr with exit 2 (FR-022/FR-023). Only four narrow exception types are caught (`OSError`, `UnicodeDecodeError`, `BrokenPipeError`, and `SystemExit` is not used for control flow); no bare `except` and no `except Exception: pass`. Undecodable bytes are refused rather than redacted approximately or passed through with `U+FFFD` replacement characters — a half-redacted file is precisely the "silent wrong answer" the principle forbids. The `--count` tally is suppressed on the failure path so a printed tally always describes a complete run. |
| **III. Every Requirement Is Testable** | Each FR maps to ≥1 pytest test naming the requirement; each failure mode asserts message *and* exit status; bare `pytest` runs it | **PASS** — the FR→test map in [quickstart.md](./quickstart.md) covers FR-001…FR-025, and every test id carries its requirement (e.g. `test_fr013_ipv4_not_matched_inside_longer_dotted_run`). The three failure modes of SC-005 get subprocess tests asserting stderr content *and* exit status. No requirement in the spec resisted expression as a pass/fail test, so nothing needed rewriting. |
| **IV. Simplicity** | Smallest design that satisfies the spec; no abstraction for a single caller; no unrequested configurability | **PASS** — 3 source files, no classes beyond one frozen `Counts` dataclass, no rule registry/plugin layer/base class (the three rules are three regexes in one module), no configuration of placeholders or patterns, no `--help`, no `-` stdin convention, no in-place editing. The one hand-written component (the argument parser) *removes* a dependency on `argparse` workarounds rather than adding structure; see research.md D-007. |

**Gate result: PASS, no violations.** The Complexity Tracking table below is therefore empty.

Two design choices deserve the plan-level visibility that Workflow Gate 2 demands, even though
neither is a principle deviation — both are places where the spec's letter and its stated safety
bias (SC-002, "the leak rate is 0%") pull in slightly different directions. Both are recorded in
full, with the rejected alternative, as D-004 and D-005 in [research.md](./research.md):

1. **Card-vs-IPv4 overlap resolution** runs IPv4 before cards, so a digit run that merges into an
   IPv4 address (`4111111111111111 10.0.0.7`) yields `[CARD] [IP]` rather than letting the
   leftmost card candidate swallow the first octet and emit `[CARD].0.0.7`. This redacts a
   superset of what strict leftmost-wins would redact; it never leaks more.
2. **A Luhn-failing card window is left unchanged (FR-016) and the scan restarts one character
   later**, rather than searching every shorter sub-window at the same start. The surviving
   limitation is stated precisely in research.md with the exact input shape that triggers it.

### Post-Design Re-check (after Phase 1)

Re-evaluated against the generated [data-model.md](./data-model.md),
[contracts/cli.md](./contracts/cli.md), and [quickstart.md](./quickstart.md): **still PASS.**
Phase 1 added no module, class, abstraction, dependency, or configuration surface beyond what the
pre-Phase-0 check assessed. The entity set is three regex constants, one 8-line predicate, one
3-field dataclass, and two I/O functions — the data model introduced no persistence layer and no
new types.

## Project Structure

### Documentation (this feature)

```text
specs/001-logredact-cli/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output: 10 decisions, each with a validated probe
├── data-model.md        # Phase 1 output: entities, rules, state
├── quickstart.md        # Phase 1 output: runnable validation + FR→test map
├── contracts/
│   └── cli.md           # Phase 1 output: the command-line contract
├── checklists/
│   └── requirements.md  # Pre-existing spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml           # Project metadata; dependencies = [] ; pytest config (pythonpath=src)

src/
└── logredact/
    ├── __init__.py      # Package marker; re-exports redact_text and Counts
    ├── __main__.py      # CLI: argument parsing, input selection, stream I/O, exit status
    └── redact.py        # Redaction engine: patterns, luhn(), redact_text(), Counts

tests/
├── conftest.py          # run_cli() helper: subprocess with PYTHONPATH=src
├── test_redact.py       # Unit: FR-005…FR-018, FR-020 (engine-level, per requirement)
├── test_cli.py          # Integration: FR-001…FR-004, FR-019, FR-021…FR-025
└── test_corpus.py       # SC-002 leak corpus and SC-003 false-positive corpus
```

**Structure Decision**: Single project, `src/` layout, as fixed by the spec's carried-over
constraints ("code in a package named `logredact` under `src/`, runnable as `python -m logredact`
when `src/` is on `PYTHONPATH`"). The web/mobile template options do not apply. The engine
(`redact.py`) is separated from the CLI (`__main__.py`) for one concrete, non-speculative reason:
Principle III requires each redaction requirement to be testable, and testing FR-007 through
FR-018 through a subprocess would be slow and would conflate redaction defects with I/O defects.
There is no third layer — no `models/`, `services/`, or `lib/` directory — because no requirement
corresponds to one. Tests sit in three files split by what they assert (engine, CLI contract,
corpora), discoverable by a bare `pytest` from the repository root as the Constitution's layout
constraint requires.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. No entries.
