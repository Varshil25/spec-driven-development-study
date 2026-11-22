# Implementation Plan: Phone Redaction and Output Folder

**Branch**: `002-phone-redaction-out-dir` | **Date**: 2026-11-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-phone-redaction-out-dir/spec.md`

## Summary

Two additions to the existing `logredact` CLI, with everything else held byte-for-byte identical:

1. **A fourth redaction category.** An international phone number — a `+` followed by 8 to 15
   contiguous ASCII digits — becomes `[PHONE]`, at precedence **rank 4, below card**. With
   `--count` the summary becomes `emails=N ips=N cards=N phones=N`.
2. **A batch destination.** `--out-dir DIR` writes each FILE's redacted stream to `DIR/<basename>`
   instead of to stdout, creating `DIR` and its missing parents, replacing an existing file of that
   name in full, and reporting `wrote N files` on stdout when every FILE has been processed.

**Technical approach**: the phone rule is one bounded pattern, `\+[0-9]{8,15}(?![0-9])`, applied as a
**third matching stage over the sub-slices no higher-ranked rule claimed** — the same gap-restriction
mechanism the existing engine already uses to put card below email and IPv4. That placement is what
makes the user's binding instruction literally true: `+4222222222222` is `+[CARD]` today and stays
`+[CARD]`, so no text the tool redacts changes category or position (FR-003, FR-005).

The output folder adds a filesystem surface feature 001 did not have at all, so it is built from
checked primitives rather than convenience calls: each directory component the tool creates is
`mkdir(0o700)` + `chmod`, because `os.makedirs(mode=…)` applies the mode to the leaf only; each
output file is opened with `O_WRONLY|O_CREAT|O_NOFOLLOW|O_NONBLOCK` and **no `O_TRUNC`**, so that
"is it a regular file?", "is it reached through a symlink?", and "is it the file I am reading?" are
all answered on the descriptor *before* `ftruncate` destroys anything. The output name is the FILE's
final path component only, and the joined path must resolve to a direct child of the resolved DIR.

Every decision was executed as a probe against the spec's acceptance scenarios before being written
down: all 22 phone scenarios and edge cases produce the specified output, feature 001's corpus is
unchanged, the worst adversarial line takes 6.78 ms against a 1 s budget, and the symlink, FIFO,
directory, and same-file-as-input attacks each fail loudly with the planted target untouched. See
[research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.11+ (CPython), per the user's planning input and FR-018. Verified on
3.13.17; no feature newer than 3.11 is used.

**Primary Dependencies**: none. Standard library only at runtime (FR-018, Principle I). The import
set grows by exactly two modules over feature 001 — `stat` and `pathlib` — joining `re`, `argparse`,
`sys`, `os`, `io`. `pytest` is developer tooling and is never imported by shipped code.

**Storage**: the filesystem, and only under `--out-dir`. The tool writes `DIR`, `DIR`'s missing
parents, and one regular file per FILE directly inside `DIR` — nothing else, ever, and nothing at
all when `--out-dir` is absent (FR-017, SR-008). No database, no temporary file, no cache.

**Testing**: `pytest`, per the user's planning input and the constitution, configured by the existing
`[tool.pytest.ini_options]` in `pyproject.toml` (`pythonpath = ["src"]`). Feature 001's two styles
are kept: `subprocess` runs of `python -m logredact` for the real entry point, exit statuses, and
byte-level stdout assertions; in-process `main(argv, *, stdin, stdout, stderr)` calls with injected
streams for failure paths the environment cannot produce. New filesystem assertions use `tmp_path`,
`os.stat` modes, and `os.mkfifo`/`os.symlink` to plant the hostile cases (research.md D-114).

**Target Platform**: POSIX — Linux or macOS. `--out-dir`'s link and permission controls use
`os.O_NOFOLLOW`, `os.O_NONBLOCK`, and `os.fchmod`, which the standard library provides on Unix only.
This is a **deliberate narrowing** of feature 001's "any platform with CPython 3.11+", recorded with
its reasoning in research.md D-113 and in Complexity Tracking below: a capability fallback would
silently weaken a security control (SR-006) on the platform that lacks the primitive, which is worse
than not running there. Everything feature 001 does — all four categories, `--count`, the default
stdout stream — remains platform-independent.

**Project Type**: single-project CLI tool (library package + `__main__` entry point), extended in
place. No new module, no new package.

**Performance Goals**: 10 MB in under 10 s to either destination (SC-009) — feature 001 measured
1.9 s and the fourth rank adds one bounded pass over the uncovered slices. Each adversarial
10 000-character line under 1 s (SC-010) — measured worst case 6.78 ms through the complete
four-rank pipeline, a 147× margin.

**Constraints**: the 1 MiB per-line maximum is unchanged and enforced on every input source for both
destinations, so peak memory stays bounded by it regardless of total input size or file count
(SR-011). At most one output file handle open at a time (SR-011). Output written as the input is
streamed, never accumulated (SR-011). Owner-only permissions on everything created — `0o700`
directories, `0o600` files (SR-007). Offline by construction.

**Scale/Scope**: ~140 new lines across the two existing source modules (≈40 in `redact.py`, ≈100 in
`cli.py`); 31 requirements (FR-001 – FR-019, SR-001 – SR-012) and 12 success criteria, each mapped to
tests below. Feature 001's 221 existing tests must continue to pass, except the `--count` assertions
FR-004 supersedes.

**Unknowns**: none. No `NEEDS CLARIFICATION` markers remain — the spec fixed the interface, the
recognition rule, the precedence rank, and every failure status; the user's planning input fixed
language, dependency policy, and test runner; [research.md](./research.md) resolved the fourteen open
*how* questions (D-101 – D-114).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0.

### Initial check (before Phase 0) — PASS

| Principle / Gate | Status | Evidence |
|---|---|---|
| **I. Standard Library Only** | PASS | FR-018 mandates stdlib-only and the user's planning input confirms it. The two new imports (`stat`, `pathlib`) are standard library. `pytest` stays developer-only. |
| **II. Fail Loudly** | PASS | Every new failure path in the spec carries a stderr diagnostic and exit 2 (FR-012, FR-014, FR-015, SR-009, SR-012), with no fallback to stdout, no fallback to stdin, and no substituted "reasonable" DIR. The spec explicitly forbids reporting a truncated bundle as success. |
| **III. Every Requirement Is Testable** | PASS | FR-019 already requires pytest coverage of every requirement including negative tests asserting status **and** message. Mapping recorded below; no requirement needed rewriting to be automatable. |
| **IV. Simplicity** | PASS | No new module, no class for any of the four new entities, no writer or destination abstraction, no configuration surface. `_consume` is reused unchanged for both destinations. |
| **V. Secure by Default (NON-NEGOTIABLE)** | PASS | The spec carries twelve security requirements derived against OWASP Top 10 (2021) and ASVS 4.0, with a not-applicable table and reasons, and correctly identifies **writing to the filesystem** as the new threat surface. Phone redaction is on by default with no opt-out. |
| **Specification gate** | PASS | Requirements are testable assertions; security section and OWASP/ASVS consideration present. |
| **Planning gate** | PASS | This document records the requirement-to-test mapping for all 31 requirements, confirms no third-party runtime dependency, and justifies the one structural deviation (platform narrowing) in Complexity Tracking. |

### Security Baseline applicability (before Phase 0)

The baseline is a floor, not a menu. Feature 001 judged four controls inapplicable; **two of those
become applicable here** because the tool now writes.

| Baseline control | 001 | 002 | How this feature satisfies it |
|---|---|---|---|
| Untrusted input | Yes | Yes | The DIR value and the FILE→name mapping are validated at the boundary before reaching any write logic (SR-012); input remains opaque text. |
| No injection by concatenation | Yes | Yes | No SQL, shell, or subprocess. Output paths are built by `os.path.join` of a validated final path component, never by concatenating untrusted text (SR-005). Placeholders inserted literally (001 SR-004). |
| **Path containment** | Partially | **Yes, fully** | Now a first-class control: basename-only naming, rejection of `""`/`.`/`..`, `resolve()` + direct-child verification against the resolved DIR, `O_NOFOLLOW` so a link is never followed out of DIR, and a same-file check so an input is never truncated (SR-005, SR-006, SR-008). |
| Password and secret storage | No | No | No passwords, tokens, keys, or secrets exist in the tool. |
| Randomness and comparison | No | No | No identifiers, tokens, salts, or nonces; placeholders are fixed literals. There is deliberately **no** random or temporary output name (SR-007 forbids a predictable temp path, and D-109 forbids the temp-and-rename design the spec does not require). |
| Resource limits | Yes | Yes | 1 MiB per-line ceiling unchanged on both destinations; bounded `readline(n)`; bounded `{8,15}` quantifier; at most one output handle open (SR-004, SR-011). |
| Access control | No | No | No identities and no privilege boundary of its own; the tool writes only where the invoking user asked and only what they can already write. |
| **File permissions** | No | **Yes** | Newly applicable: every directory the tool creates is `0o700` and every output file `0o600`, set at creation before content is written and never widened; no temporary file at a predictable path (SR-007). |
| Output, log, and error hygiene | Yes | Yes | `[PHONE]` is fixed and non-reversible; diagnostics name only user-supplied paths; the tally and summary are integers and fixed text; no stack traces; nothing unredacted reaches disk (SR-001, SR-010). |

### Post-design re-check (after Phase 1) — PASS

Re-evaluated against the completed [research.md](./research.md), [data-model.md](./data-model.md),
[contracts/](./contracts/), and [quickstart.md](./quickstart.md).

| Principle | Status | Post-design evidence |
|---|---|---|
| **I. Standard Library Only** | PASS | Final import set is `re`, `argparse`, `sys`, `os`, `io`, `stat`, `pathlib` — all stdlib. `pyproject.toml` still declares no dependencies and no build backend; the project runs for anyone with only CPython. The quickstart carries a grep gate against stray imports. |
| **II. Fail Loudly** | PASS | Thirteen failure conditions are enumerated in [contracts/cli.md](./contracts/cli.md), each with a message shape and exit 2. Two design choices exist *only* to serve this principle: `O_NONBLOCK`, so a FIFO at an output path fails instead of hanging (D-109), and the `lstat` pre-check, so a symlink is reported as "not a regular file" instead of the kernel's misleading "too many levels of symbolic links" (D-110). The per-file `close()` is inside the success condition, because a buffered tail lost at close would be a silent truncation. `except OSError` is used to add context and report, never to discard. |
| **III. Every Requirement Is Testable** | PASS | All 31 requirements mapped below. Two testability risks were designed out rather than waived: the unwritable-destination path is unreachable as root, and the close-failure path is unreachable from the outside — both are reached through the injected-stream entry point and a patched `os.open`, so no test needs `skipif` or `xfail`, which Principle III forbids. The two security-critical helpers are named in the contract (`output_path_for`, `open_output`) so SR-005/SR-006/SR-007 get direct unit tests as well as end-to-end ones. |
| **IV. Simplicity** | PASS | Four new entities, zero new types: `OutputDestination` is `str \| None`, `OutputFolder` is a path string, `OutputFile` is a `(path, stream)` pair, `WrittenTally` is an `int`. `_consume` is reused verbatim for both destinations — `main` grows one branch, not a strategy object. No new module. Three alternatives that would have added machinery (a rule registry, a destination class, temp-file-and-rename) were rejected on this principle in research.md. |
| **V. Secure by Default** | PASS | All twelve SRs have a design home and a test. Phone redaction is unconditional — no flag can weaken it because no such flag exists (SR-003). The design closes three holes the spec did not spell out: without `O_NONBLOCK` a planted FIFO would **hang** the tool rather than fail it; without the "no `O_TRUNC`, check on the fd, truncate last" ordering, `--out-dir .` would destroy the input before the same-file check could run; and `os.makedirs(mode=0o700)` would have left every *intermediate* directory at `0o755`, quietly failing SC-007 for the nested case the spec requires (D-108, measured). |
| **Implementation gate** | Deferred | Enforced at `/speckit-implement`: full suite green with no skips or xfails, every new requirement tested, failure paths asserting both signal and message, baseline controls covered by negative tests, no non-stdlib runtime import. |

**Gate result: PASS. One deviation — the POSIX platform narrowing — is justified in Complexity
Tracking rather than waived.**

## Project Structure

### Documentation (this feature)

```text
specs/002-phone-redaction-out-dir/
├── plan.md                        # This file (/speckit-plan output)
├── spec.md                        # Feature specification (input)
├── research.md                    # Phase 0 output: D-101 – D-114
├── data-model.md                  # Phase 1 output: 2 extended + 4 new entities, INV-7 – INV-14
├── quickstart.md                  # Phase 1 output: 8 validation scenarios
├── contracts/                     # Phase 1 output
│   ├── cli.md                     #   CLI surface v2: --out-dir, tally, diagnostics, guarantees
│   └── redaction-rules.md         #   phone grammar, four-rank precedence, complexity guarantee
├── checklists/
│   └── requirements.md            # /speckit-specify output
└── tasks.md                       # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
pyproject.toml                     # unchanged: pytest config only

src/
└── logredact/
    ├── __init__.py                # unchanged: package marker, no logic
    ├── __main__.py                # unchanged: sys.exit(main(sys.argv[1:]))
    ├── cli.py                     # CHANGED: --out-dir option and validation, DIR creation,
    │                              #   output-path derivation and containment, safe output open,
    │                              #   per-FILE destination, tally, new diagnostics, 4th count
    └── redact.py                  # CHANGED: PHONE_PLACEHOLDER, _PHONE, stage 3, 4th count key

tests/
├── conftest.py                    # CHANGED: SAMPLE_PHONE, output-folder fixtures, mode reader
├── test_redact_phone.py           # NEW: FR-001, FR-002 recognition and boundaries
├── test_precedence.py             # CHANGED: FR-003 four-rank overlap, card-beats-phone
├── test_regression_001.py         # NEW: FR-005, SC-003 byte-for-byte against 001's corpus
├── test_cli_out_dir.py            # NEW: FR-006 – FR-011, FR-013 success paths (US2)
├── test_cli_out_dir_errors.py     # NEW: FR-012, FR-014, FR-015 failure paths (US4)
├── test_out_dir_security.py       # NEW: SR-005 – SR-008, SR-010, SR-012
├── test_cli_count.py              # CHANGED: FR-004, FR-016 four-field summary
├── test_security.py               # CHANGED: SR-001, SR-003, SR-009, SR-010 for the new surface
├── test_limits.py                 # CHANGED: SR-011 per-line ceiling on both destinations
├── test_performance.py            # CHANGED: SR-004, SC-010 phone adversarial lines
├── test_redact_email.py           # unchanged
├── test_redact_ipv4.py            # unchanged
├── test_redact_card.py            # unchanged
├── test_cli_stream.py             # unchanged
├── test_cli_files.py              # unchanged
└── test_encoding.py               # unchanged
```

**Structure Decision**: extend feature 001's four-module single-project layout **in place**. No
module, package, or directory is added.

The pure/impure split that 001 established is the reason the new work lands where it does:

- `redact.py` stays **pure functions over `str`** — no I/O, no process, no filesystem. The phone
  pattern and the third matching stage belong here, which is what lets FR-001, FR-002, FR-003, and
  the SC-010 timing budget be tested with no filesystem involved.
- `cli.py` holds **everything with a side effect**, so the whole output-folder surface goes here:
  the `--out-dir` option, boundary validation, DIR creation, output-path derivation and containment,
  the safe output open, the per-FILE destination branch, the tally, and the new diagnostics. It
  grows from ~330 to ~430 lines, which is still one cohesive module: a CLI's argument handling and
  its destinations are the same concern, and splitting them would mean inventing an interface between
  two halves of one function's job.
- `__main__.py` and `__init__.py` are untouched.

**A fifth module was considered and rejected.** Moving the containment and safe-open helpers to an
`outfile.py` would make them importable without `cli`, but no requirement asks for that: they are
already directly testable as module-level functions, and [contracts/cli.md](./contracts/cli.md) fixes
`output_path_for` and `open_output` as a stable internal surface so SR-005 – SR-008 get unit tests
regardless. Principle IV prefers a module to a package and the smallest design that satisfies the
spec; adding a module to host two functions would be structure added for no stated requirement, and
would have to be justified here as a violation rather than a choice.

Test files are split along the spec's own seams — one per user story for the new surface, plus a
dedicated `test_regression_001.py` because FR-005 and SC-003 are a requirement in their own right
("everything else must keep working exactly as it does") and deserve a file a reviewer can point at,
rather than being implied by the absence of failures elsewhere.

## Requirement-to-Test Mapping

Required by the constitution's **Planning gate** ("A plan MUST record the requirement-to-test mapping
for every functional and security requirement") and by FR-019 and SC-011. Every row names the test
file that must contain at least one assertion for that requirement; `/speckit-tasks` turns these into
concrete test tasks.

### Functional requirements

| Req | Assertion under test | Test file |
|---|---|---|
| FR-001 | `+` plus 8–15 contiguous ASCII digits → `[PHONE]`; both bounds qualify; longest taken; `+` anchors with the left context ignored (`100+…`, `++…`) | `test_redact_phone.py` |
| FR-002 | unchanged for: <8 digits, ≥16 contiguous digits, separated digits (` `, `-`, `.`), non-ASCII digits, bare `+` | `test_redact_phone.py` |
| FR-003 | four-rank precedence; `+1415…@example.com` → `[EMAIL]`, `+10.0.0.7` → `+[IP]`, `+4222222222222` → `+[CARD]`; one replacement per span; placeholders not nested or re-scanned | `test_precedence.py` |
| FR-004 | `emails=N ips=N cards=N phones=N` on stderr, that order, single spaces, one trailing newline, after the stdout flush; counts replacements not lines | `test_cli_count.py` |
| FR-005 | 001's corpus byte-for-byte identical and same exit status; email/IPv4/card rules, newline and non-UTF-8 preservation, per-line maximum, empty stderr without `--count`, statuses 0 and 2 all unchanged | `test_regression_001.py`, plus the unchanged 001 files |
| FR-006 | `--out-dir DIR` and `--out-dir=DIR`; any position; value never treated as a FILE; last occurrence wins; missing value → exit 2 | `test_cli_out_dir.py`, `test_cli_out_dir_errors.py` |
| FR-007 | redacted lines go to `DIR/<basename>`; no redacted line on stdout; input directories absent from the output location and no `DIR/logs` created | `test_cli_out_dir.py` |
| FR-008 | a non-existent nested DIR and all missing parents are created before any output file | `test_cli_out_dir.py` |
| FR-009 | an existing file is replaced in full, leaving no tail of longer previous content; never appended | `test_cli_out_dir.py` |
| FR-010 | exactly `wrote N files\n` on stdout, `wrote 1 file` singular, only with `--out-dir`, only content on stdout, absent without the option | `test_cli_out_dir.py` |
| FR-011 | N = FILE arguments processed; a FILE named twice counts twice; two FILEs sharing a basename count twice and the later replaces the earlier | `test_cli_out_dir.py` |
| FR-012 | `--out-dir` with no FILE → usage diagnostic, exit 2, stdin not read, nothing created | `test_cli_out_dir_errors.py` |
| FR-013 | output files round-trip non-UTF-8 bytes, preserve `\n`/`\r\n`/lone `\r`, add no terminator to an unterminated final line, and give an empty file for empty input | `test_cli_out_dir.py` |
| FR-014 | unreadable FILE → diagnostic naming it, exit 2, earlier output files intact, later FILEs not opened, no tally, no summary | `test_cli_out_dir_errors.py` |
| FR-015 | DIR-creation, open, write, flush, and close failures each → diagnostic naming the directory or output path, exit 2, no tally, no summary | `test_cli_out_dir_errors.py` |
| FR-016 | `--count` with `--out-dir` → single run-wide summary on stderr, after every output file and after the tally; only on success | `test_cli_count.py` |
| FR-017 | without `--out-dir`: stream to stdout, no tally, and **no** file, directory, temp file, or cache created or modified anywhere | `test_security.py` |
| FR-018 | `python -m logredact` runs with `PYTHONPATH=src`; no non-stdlib import anywhere under `src/` | `test_security.py` |
| FR-019 | *meta* — satisfied by this table being complete and the suite running with no skips or xfails | all files |

### Security requirements

| Req | Assertion under test (negative tests included) | Test file |
|---|---|---|
| SR-001 | `[PHONE]` is fixed with no length hint; no input line content, matched value, or fragment appears in any diagnostic, usage text, summary, or tally; only user-supplied paths are named; no stack trace on any failure path | `test_security.py`, `test_cli_out_dir_errors.py` |
| SR-002 | the original phone value is absent as a **substring** of the output; **no digit of a rejected ≥16-digit candidate is removed**; no digit of an accepted number survives | `test_redact_phone.py`, `test_security.py` |
| SR-003 | all four categories redact with no flag; no option disables or weakens one; `--out-dir` changes only the destination, never which categories are redacted nor any line's redaction | `test_security.py`, `test_out_dir_security.py` |
| SR-004 | adversarial 10 000-character lines — a `+` run, a digit run, an alternating `+`/digit run, and a `+`+16-digit run — each complete inside a fixed time budget | `test_performance.py` |
| SR-005 | FILEs with deep prefixes, `..` segments, and absolute paths all write **only** `DIR/<basename>`; a basename of `""`, `.`, or `..` is refused with exit 2; a path that does not resolve to a direct child of resolved DIR is refused; direct unit tests of `output_path_for` | `test_out_dir_security.py` |
| SR-006 | a symlink planted at the output path is **not followed** — exit 2, diagnostic naming the path, link target never created; a directory, FIFO, and device at the output path each fail loudly (and the FIFO case does not hang) | `test_out_dir_security.py` |
| SR-007 | every created directory is `0o700` including intermediates of a nested DIR; every output file is `0o600` whether created or replacing a `0o666` file; no temporary file appears at any point | `test_out_dir_security.py` |
| SR-008 | without `--out-dir` nothing on disk changes; with it, only DIR, its parents, and files directly inside DIR are created or written; an input FILE's content, mode, and mtime are unchanged and it is never opened for writing; `--out-dir .` with a FILE in `.` is refused **without truncating the input** | `test_out_dir_security.py`, `test_security.py` |
| SR-009 | an `OSError` on DIR creation, output open, write, flush, or close is reported on stderr with a non-zero status; a truncated output file never exits 0; a partial file may remain but the tally does not | `test_cli_out_dir_errors.py`, `test_security.py` |
| SR-010 | an output file's bytes equal exactly that FILE's redacted stream; no prepared sample value appears in **any** file under the output folder, nor in any temp file or cache | `test_out_dir_security.py` |
| SR-011 | the 1 MiB per-line maximum is enforced for both destinations and fails without quoting the line; peak memory stays bounded across a many-file batch; at most one output handle is open at a time | `test_limits.py`, `test_out_dir_security.py` |
| SR-012 | an empty DIR value and `--out-dir` with no FILE are rejected at the boundary before any filesystem access, with no coerced or substituted value; the FILE→name mapping is validated before any write | `test_cli_out_dir_errors.py`, `test_out_dir_security.py` |

### Success criteria

| Criterion | Where verified |
|---|---|
| SC-001 / SC-002 | `test_redact_phone.py` positive and near-miss corpora; quickstart Scenario 1 |
| SC-003 | `test_regression_001.py`; quickstart Scenario 2 `diff` check |
| SC-004 | `test_cli_count.py`; quickstart Scenario 4 |
| SC-005 | `test_cli_out_dir.py` (10 files, nested DIR, per-file `diff` against the streaming mode); quickstart Scenario 3 |
| SC-006 | `test_out_dir_security.py` traversal, absolute-path, and planted-symlink cases; quickstart Scenario 6 |
| SC-007 | `test_out_dir_security.py` mode assertions on every created directory and file; quickstart Scenario 6 |
| SC-008 | `test_cli_out_dir_errors.py` — all ten enumerated failure cases assert exit 2, the diagnostic, and the absence of both the tally and the summary |
| SC-009 | `test_performance.py` throughput to both destinations; `test_limits.py` bounded memory across a batch |
| SC-010 | `test_performance.py` adversarial timing |
| SC-011 | this table + the suite running with no skipped or xfail tests |
| SC-012 | `test_security.py` and `test_out_dir_security.py` scan captured streams **and every file under every output folder** for sample values; quickstart Scenario 8 grep gate |

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

The Constitution Check passes in both evaluations. One deviation is recorded here because the
constitution requires any deviation to be justified in writing rather than assumed.

| Deviation | Why needed | Simpler alternative rejected because |
|---|---|---|
| **Target platform narrowed to POSIX** (`os.O_NOFOLLOW`, `os.O_NONBLOCK`, `os.fchmod`) | SR-006 forbids following a symlink out of DIR and SR-007 requires owner-only modes set at creation. In the standard library these are the only primitives that provide the guarantee atomically, and they are Unix-only (research.md D-113). | A `getattr(os, "O_NOFOLLOW", 0)` fallback would leave the tool *running* on a platform where the symlink guard silently does nothing — a security control that reports success while absent, which Principle II calls the most severe defect class and Principle V forbids. A second non-atomic code path for a platform the spec never mentions is speculative generality (Principle IV). Failing visibly is the honest option. |

Two choices that could *look* like unrequested complexity are accounted for in their proper places
rather than as violations:

- **The explicit directory-creation loop** instead of `os.makedirs(mode=0o700)` is not a preference:
  `makedirs` applies the mode to the leaf only, measured as `0755` on every intermediate, which
  fails SC-007 for the nested DIR the spec requires (research.md D-108).
- **The nine-step output-open sequence** instead of `open(path, "w")` is likewise forced: the
  convenience call truncates before any check can run, follows symlinks, cannot set a creation mode,
  and hangs on a FIFO — four separate requirement failures (research.md D-109).

## Phase Status

| Phase | Status | Output |
|---|---|---|
| Phase 0 — Outline & Research | Complete | [research.md](./research.md) — D-101 – D-114, no unknowns left |
| Phase 1 — Design & Contracts | Complete | [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [contracts/redaction-rules.md](./contracts/redaction-rules.md), [quickstart.md](./quickstart.md) |
| Phase 2 — Tasks | Not started | `/speckit-tasks` |
