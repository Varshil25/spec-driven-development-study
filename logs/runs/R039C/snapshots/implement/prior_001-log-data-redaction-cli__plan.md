# Implementation Plan: Log Data Redaction CLI

**Branch**: `001-log-data-redaction-cli` | **Date**: 2026-11-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-log-data-redaction-cli/spec.md`

## Summary

A streaming command-line filter, `python -m logredact [--count] [FILE ...]`, that reads stdin or
each named file in order and writes every line to stdout with email addresses replaced by
`[EMAIL]`, IPv4 addresses by `[IP]`, and Luhn-valid 13–19 digit card numbers by `[CARD]`, leaving
everything else byte-for-byte unchanged.

**Technical approach**: one compiled regex alternation recognises email and IPv4 in precedence
order; card numbers — whose Luhn checksum no regex can express — are found by locating maximal
ASCII digit runs and validating group-aligned candidates in Python, and only inside the gaps the
first stage left uncovered. That gap restriction is what implements FR-008's precedence and
guarantees placeholders are never re-scanned. Input is decoded UTF-8 with
`errors="surrogateescape"` so non-UTF-8 bytes round-trip exactly, and read with
`readline(MAX + 1)` so memory stays bounded by a 1 MiB per-line limit regardless of total input
size. Every failure — unreadable file, over-long line, output write failure, bad option — reports on
stderr and exits 2, so a truncated redaction can never be reported as success.

All design decisions were validated by executing probes against the spec's acceptance scenarios
before being written down: all 21 scenario/edge cases produce the specified output, the worst
adversarial line takes 117 ms against a 1 s budget, and 10 MB redacts in 1.9 s against a 10 s
budget. See [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.11+ (CPython). Verified on 3.13.17; no feature newer than 3.11 is
used.

**Primary Dependencies**: none. Standard library only at runtime — `re`, `argparse`, `sys`, `os`,
`io` (FR-015, Constitution Principle I). `pytest` 7+ is developer tooling, never imported by
shipped code.

**Storage**: N/A — the tool is a stateless filter and writes nothing to disk (SR-008).

**Testing**: `pytest`, configured via `[tool.pytest.ini_options]` in `pyproject.toml` with
`pythonpath = ["src"]`. Two styles: in-process `main(...)` calls with injected streams for failure
paths, and `subprocess` runs of `python -m logredact` for the real entry point, exit statuses, and
byte-level stdout assertions.

**Target Platform**: any platform with CPython 3.11+; a POSIX shell is assumed only by the
quickstart commands, not by the tool or the suite.

**Project Type**: single-project CLI tool (library package + `__main__` entry point).

**Performance Goals**: 10 MB in under 10 s (SC-007) — measured 1.9 s, 5× margin. Each adversarial
10 000-character line under 1 s (SC-008) — measured worst case 117 ms, 8.5× margin.

**Constraints**: 1 MiB (1 048 576 characters) maximum decoded line length, enforced, exceeding it
fails with exit 2 (SR-005). Peak memory bounded by that limit regardless of total input size, so a
1 GB input streams without exhausting memory (FR-016, SC-007). Offline by construction — no network
access of any kind. No file creation or modification (SR-008).

**Scale/Scope**: ~250 lines of implementation across 4 small modules; 27 requirements (FR-001 –
FR-018, SR-001 – SR-009) each mapped to tests below.

**Unknowns**: none. No `NEEDS CLARIFICATION` markers remain — the spec fixed the interface and
rules, the user's planning input fixed language, dependency policy, and test runner, and
[research.md](./research.md) resolved the eleven open *how* questions (D-001 – D-010).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0.

### Initial check (before Phase 0) — PASS

| Principle / Gate | Status | Evidence |
|---|---|---|
| **I. Standard Library Only** | PASS | Spec FR-015 mandates stdlib-only; user input confirms. `pytest` and a `pyproject.toml` holding only pytest config are permitted developer tooling and are not imported by shipped code. |
| **II. Fail Loudly** | PASS | Spec requires exit 2 + stderr diagnostic for every failure path (FR-013, FR-014, SR-005, SR-007). No sentinel return, no swallowed exception, no silent coercion of bad input. |
| **III. Every Requirement Is Testable** | PASS | FR-018 already requires pytest coverage of every requirement including negative tests asserting both status and message. Mapping recorded below. |
| **IV. Simplicity** | PASS | Smallest design that satisfies the spec: no classes for the five entities, no plugin or rule-registry abstraction, no configuration surface. |
| **V. Secure by Default** | PASS | Spec carries a mandatory Security Requirements section (SR-001 – SR-009) derived against OWASP Top 10 2021 and ASVS 4.0, with a not-applicable table and reasons. |
| **Specification gate** | PASS | Requirements are testable assertions; security section and OWASP/ASVS consideration present. |
| **Planning gate** | PASS | This document records the requirement-to-test mapping, confirms no third-party runtime dependency, and justifies every structural choice. |

### Security Baseline applicability (before Phase 0)

| Baseline control | Applies? | How this feature satisfies it |
|---|---|---|
| Untrusted input | Yes | Options validated at the boundary before input is opened; every input treated as opaque text (SR-004). |
| No injection by concatenation | Yes | No SQL, no shell, no subprocess, no markup. Placeholders inserted as literal strings, never as substitution templates (SR-004, G-2). |
| Path containment | Partially | SR-009: FILE paths come from the invoking user's own command line, are never derived from file contents or the environment, and are never opened for writing. No base directory exists to contain them to — the tool reads only what the caller can already read. Deliberate, documented reading of the control, not an omission. |
| Password and secret storage | No | No passwords, tokens, keys, or secrets exist in the tool. |
| Randomness and comparison | No | No identifiers, tokens, salts, or nonces; no secret comparison. Placeholders are fixed literals. |
| Resource limits | Yes | 1 MiB per-line ceiling, bounded reads via `readline(n)`, bounded card candidate enumeration, no unbounded regex nesting (SR-005, SR-006). |
| Access control | No | No identities and no privilege boundary of its own; a single-user local filter. |
| File permissions | No | Creates no files or directories (SR-008), so no mode is ever chosen. |
| Output, log, and error hygiene | Yes | The feature *is* this control. SR-001/SR-002: no input content in diagnostics or the summary; only the caller's own path may be named; whole values replaced by non-reversible placeholders; redaction tested. |

### Post-design re-check (after Phase 1) — PASS

Re-evaluated against the completed [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), and
[quickstart.md](./quickstart.md).

| Principle | Status | Post-design evidence |
|---|---|---|
| **I. Standard Library Only** | PASS | Final import set is `re`, `argparse`, `sys`, `os`, `io` — all stdlib. `pyproject.toml` declares no dependencies and no build backend; the project runs for anyone with only CPython installed. The quickstart includes a grep gate against stray imports. |
| **II. Fail Loudly** | PASS | Four failure paths each produce a stderr diagnostic and exit 2 (research.md D-006). `except OSError` is used to *add context and report*, never to discard; no bare `except`. The over-long-line case explicitly rejects rather than truncating, which is what Principle II's "no silent truncation" demands. The `os._exit(2)` on broken pipe exists precisely to stop CPython's shutdown flush from replacing the documented status with 120. |
| **III. Every Requirement Is Testable** | PASS | All 27 requirements mapped below, each to a named test. Two testability risks were found and designed out rather than waived: permission-denied is unreachable as root, and write-failure is unreachable without stream injection — both are solved by `main(argv, *, stdin, stdout, stderr)` and a patched `open` (D-008), so no test needs `skipif` or `xfail`, which Principle III forbids. |
| **IV. Simplicity** | PASS | Three of five entities are plain `str`/`int`; `Match` is a tuple, `Options` is the argparse namespace. No rule registry, no strategy objects, no config layer. Three alternative matching designs were rejected partly for being more machinery (research.md D-003). Four modules, justified below. |
| **V. Secure by Default** | PASS | All nine SRs have a design home and a test. Redaction is unconditional — no flag can weaken it because no such flag exists (SR-003). Two security-relevant holes the spec did not anticipate were closed in design: `\d` would have fed non-ASCII digits to the Luhn check (D-004), and a 300-character local part could have produced a *partial* email match leaking most of the address (D-005) — explicit classes and the lookbehind guard mean the value is left wholly intact instead. |
| **Implementation gate** | Deferred | Enforced at `/speckit-implement`: full suite green, no skips, no xfail, negative tests present, no non-stdlib runtime import. |

**Gate result: PASS. No violations. Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/001-log-data-redaction-cli/
├── plan.md                        # This file (/speckit-plan output)
├── spec.md                        # Feature specification (input)
├── research.md                    # Phase 0 output: D-001 – D-010
├── data-model.md                  # Phase 1 output: 6 entities + cross-entity invariants
├── quickstart.md                  # Phase 1 output: 7 validation scenarios
├── contracts/                     # Phase 1 output
│   ├── cli.md                     #   CLI surface: args, streams, exit statuses, guarantees
│   └── redaction-rules.md         #   recognition grammar, precedence, complexity guarantee
└── tasks.md                       # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
pyproject.toml                     # pytest config only: pythonpath=["src"], testpaths=["tests"]

src/
└── logredact/
    ├── __init__.py                # package marker; no logic
    ├── __main__.py                # `python -m logredact` shell: sys.exit(main(sys.argv[1:]))
    ├── cli.py                     # argparse, source iteration, bounded reads, errors, counts
    └── redact.py                  # patterns, Luhn, redact_line() -> (text, counts)

tests/
├── test_redact_email.py           # FR-004 recognition and boundaries
├── test_redact_ipv4.py            # FR-005 recognition and boundaries
├── test_redact_card.py            # FR-006, FR-007, Luhn, grouping, boundaries
├── test_precedence.py             # FR-008, FR-009 overlap and ordering
├── test_cli_stream.py             # US1: stdin, byte-exactness, no added newline
├── test_cli_files.py              # US2: argument order, repeats, empty file, stdin untouched
├── test_cli_count.py              # US3: summary format, position, ordering, stream separation
├── test_cli_errors.py             # US4: missing/denied/directory/bad-option, partial output
├── test_encoding.py               # FR-017 non-UTF-8 round-trip
├── test_limits.py                 # SR-005 per-line ceiling, FR-016 bounded memory
├── test_security.py               # SR-001 – SR-004, SR-007 – SR-009
└── test_performance.py            # SC-007 throughput, SC-008/SR-006 adversarial timing
```

**Structure Decision**: single-project CLI layout. `src/logredact/` is mandated verbatim by FR-001.
The split into exactly four modules is driven by the spec and the constitution, not by anticipated
futures:

- `redact.py` holds the matching engine as **pure functions** on a string. This is what lets the
  recognition rules (FR-004 – FR-009) and the adversarial timing budget (SC-008) be tested without
  any I/O, process, or filesystem involvement.
- `cli.py` holds everything with a side effect — argument parsing, opening sources, bounded reads,
  diagnostics, the counts summary. It exposes `main(argv, *, stdin, stdout, stderr) -> int`
  returning a status rather than raising `SystemExit`, which is what makes the write-failure path
  (SR-007) and the stdin path reachable by deterministic in-process tests (research.md D-008).
- `__main__.py` is kept separate and trivial because importing it executes it; tests import `cli`
  instead. Collapsing `cli.py` into `__main__.py` would force every CLI test through a subprocess
  and make SR-007 effectively untestable.
- `__init__.py` is the package marker FR-001 implies, with no logic in it.

Principle IV prefers a module to a package, but FR-001 requires a package named `logredact`; within
that constraint this is the flattest arrangement that keeps every requirement testable under
Principle III. No `models/`, `services/`, or `lib/` directories are created — there are no entities
needing a type (see [data-model.md](./data-model.md)) and nothing to put in them.

`pyproject.toml` carries pytest configuration only. It declares no dependencies and no build
backend, so it adds no runtime dependency (Principle I) and nothing needs installing.

## Requirement-to-Test Mapping

Required by the constitution's **Planning gate** ("A plan MUST record the requirement-to-test
mapping for every functional and security requirement") and by FR-018 and SC-009. Every row names
the test file that must contain at least one assertion for that requirement; `/speckit-tasks` turns
these into concrete test tasks.

### Functional requirements

| Req | Assertion under test | Test file |
|---|---|---|
| FR-001 | `python -m logredact` runs with `PYTHONPATH=src`; package lives at `src/logredact/` | `test_cli_stream.py` |
| FR-002 | stdin read when no FILE; FILEs read in order; stdin **not** read when FILEs present | `test_cli_files.py` |
| FR-003 | output = input with only matched spans replaced; no newline added to an unterminated final line | `test_cli_stream.py` |
| FR-004 | email grammar: local-part characters, multi-label domain, final label ≥2 letters only; no extension/truncation at boundaries | `test_redact_email.py` |
| FR-005 | IPv4 grammar: four octets 0–255, leading zeros accepted; `999.1.1.1` and `1.2.3.4.5` unchanged | `test_redact_ipv4.py` |
| FR-006 | card: 13–19 digits, contiguous or single `' '`/`'-'` groups, mixed separators, Luhn passes | `test_redact_card.py` |
| FR-007 | rejects Luhn-invalid, <13 or >19 digits, and digit-adjacent candidates | `test_redact_card.py` |
| FR-008 | precedence email → IPv4 → card; exactly one replacement per span; placeholders not nested or re-scanned | `test_precedence.py` |
| FR-009 | longest candidate at a shared start; matches found left to right; never overlapping | `test_precedence.py` |
| FR-010 | `emails=N ips=N cards=N` on stderr, after stdout flush, counting replacements across all input | `test_cli_count.py` |
| FR-011 | stderr empty on a successful run without `--count` | `test_cli_count.py` |
| FR-012 | `--count` accepted in any position; all non-option args are FILEs in order | `test_cli_count.py`, `test_cli_files.py` |
| FR-013 | unreadable FILE → message naming it on stderr, exit 2, no summary | `test_cli_errors.py` |
| FR-014 | exit 0 on full success; exit 2 on usage error with stderr message | `test_cli_errors.py` |
| FR-015 | no non-stdlib import anywhere under `src/` | `test_security.py` |
| FR-016 | streaming: peak memory bounded by the per-line limit on an input far larger than memory | `test_limits.py` |
| FR-017 | non-UTF-8 bytes round-trip unchanged; no U+FFFD, no failure | `test_encoding.py` |
| FR-018 | *meta* — satisfied by this table being complete and the suite running with no skips or xfails | all files |

### Security requirements

| Req | Assertion under test (negative tests included) | Test file |
|---|---|---|
| SR-001 | no input line content, matched value, or fragment appears in any diagnostic or in the summary; only the caller's own path is named | `test_security.py`, `test_cli_errors.py` |
| SR-002 | the original email/IPv4/card value is absent as a **substring** of the output; no prefix or suffix survives — including the over-long-local-part case, which must emit no partial match | `test_security.py`, `test_redact_email.py` |
| SR-003 | all three categories redact with no flag; no option disables or weakens one; `--count` changes only the summary, never the redaction | `test_security.py`, `test_cli_count.py` |
| SR-004 | input containing `\1`, `\g<0>`, `${x}`, `[EMAIL]`, and shell/format metacharacters is passed through inertly and cannot alter a substitution; no subprocess or shell is invoked | `test_security.py` |
| SR-005 | a line above 1 MiB fails with exit 2 and a message that names the source and **does not quote the line**; a line at the limit succeeds | `test_limits.py` |
| SR-006 | adversarial 10 000-character lines (digit runs, separator runs, `@`/dot runs) each complete inside a fixed time budget | `test_performance.py` |
| SR-007 | an `OSError` on write or flush is reported on stderr and exits non-zero; a truncated stream never exits 0 | `test_security.py` |
| SR-008 | no file, temp file, or cache is created or modified; the input file's content and mtime are unchanged; opened read-only | `test_security.py` |
| SR-009 | open failures surface as an SR-001-compliant diagnostic plus exit 2, never a stack trace; no path is derived from file contents or the environment | `test_cli_errors.py`, `test_security.py` |

### Success criteria

| Criterion | Where verified |
|---|---|
| SC-001 / SC-002 | `test_redact_*.py` positive and negative corpora; quickstart Scenario 1 |
| SC-003 | `test_cli_stream.py` byte-exactness; quickstart `diff` check |
| SC-004 / SC-005 | `test_cli_count.py`; quickstart Scenario 3 |
| SC-006 | `test_cli_errors.py` — every failure case asserts exit 2 |
| SC-007 | `test_performance.py` throughput; `test_limits.py` bounded memory |
| SC-008 | `test_performance.py` adversarial timing |
| SC-009 | this table + suite runs with no skipped or xfail tests |
| SC-010 | `test_security.py` scans captured stdout/stderr for sample values; quickstart grep gate |

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. The Constitution Check passes in both the initial and post-design evaluations, so
there is nothing to justify here.

Two structural choices that *could* look like unrequested complexity are accounted for in their
proper places rather than as violations: the four-module split is required by FR-001's package
mandate plus Principle III's testability requirement (see **Structure Decision**), and
`pyproject.toml` carries pytest configuration only, adding no runtime dependency (research.md
D-009).

## Phase Status

| Phase | Status | Output |
|---|---|---|
| Phase 0 — Outline & Research | Complete | [research.md](./research.md) — D-001 – D-010, no unknowns left |
| Phase 1 — Design & Contracts | Complete | [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [contracts/redaction-rules.md](./contracts/redaction-rules.md), [quickstart.md](./quickstart.md) |
| Phase 2 — Tasks | Not started | `/speckit-tasks` |
