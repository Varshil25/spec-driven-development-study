# Implementation Plan: Log Redaction Tool (`logredact`)

**Branch**: `001-logredact-cli` | **Date**: 2026-11-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-logredact-cli/spec.md`

## Summary

A stdlib-only Python CLI, invoked as `python -m logredact [--count] [FILE ...]`, that streams text
from the named files (or standard input) to standard output, replacing email addresses, IPv4
addresses, and Luhn-valid 13–19 digit card numbers with `[EMAIL]`, `[IP]`, and `[CARD]`, and
passing every other byte through untouched.

Technical approach: one line at a time, a single compiled alternation regex (`email | ipv4 |
card-candidate`) is searched across the line. Python's `re` gives leftmost-match semantics and
ordered alternatives, which delivers the spec's overlap and precedence rules (FR-020, FR-021)
for free. Card candidates are the only ones needing post-validation: the matched candidate is
re-matched at the same start position by seven fixed-length patterns (19 digits down to 13) and
the longest Luhn-valid one wins (FR-019); if none is valid, the scan cursor advances one
character and the search resumes, so a rejected candidate cannot hide a later valid one
(FR-019a). Byte fidelity comes from `errors="surrogateescape"` plus `newline="\n"` on both
streams: undecodable bytes round-trip unchanged (FR-005a) and only `\n` ends a line, leaving
`\r` as ordinary text (FR-007). Argument parsing is `argparse` via `parse_intermixed_args`,
whose native behaviour already matches FR-030 (usage to stderr, exit 2) and FR-030a (`--help`/`-h`
to stdout, exit 0); the `intermixed` variant is required because plain `parse_args` rejects
`a.log --count b.log`. Output
write failures are converted to a non-`OSError` internal exception so they are never mistaken
for a file read failure, and the stdout file descriptor is redirected to `os.devnull` before
exit so the interpreter's shutdown flush cannot print an "Exception ignored" traceback
(FR-031a).

## Technical Context

**Language/Version**: Python 3.11+ (floor set by the spec and the constitution; no syntax below
that floor is relied upon, and nothing above 3.11 is used)

**Primary Dependencies**: None. Runtime imports are limited to the standard library: `re`,
`argparse`, `sys`, `io`, `os`, `collections`

**Storage**: N/A — input files are read, never written; the tool writes only to stdout and stderr

**Testing**: `pytest` (the single development dependency the constitution permits), discoverable
from the repository root with no arguments; `src/` is put on the path by
`[tool.pytest.ini_options] pythonpath = ["src"]`, not by installing the package

**Target Platform**: Any POSIX-like system with CPython 3.11+; no pip install step. Developed and
verified on Linux

**Project Type**: Single-package command-line tool (stdin/stdout filter)

**Performance Goals**: 100,000-line log redacted in under 30 s (SC-007); throughput dominated by
one regex scan per line

**Constraints**: Memory must not grow with total input size (SC-006) — strictly streaming, one
line resident at a time, so a 1 GB log and a single 10 MB line are both bounded by the longest
line, not the file. Byte-exact pass-through of everything not matched (FR-005, FR-005a, FR-007,
FR-007a). Exit status is only ever 0 or 2

**Scale/Scope**: 3 runtime modules under `src/logredact/`, ~250 lines of runtime code; 36
functional requirements and 9 success criteria to cover with tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against Constitution v1.0.0.

| Gate | Principle | Status | Evidence |
|------|-----------|--------|----------|
| No third-party runtime import | I. Standard Library Only | PASS | Runtime imports fixed to `re`, `argparse`, `sys`, `io`, `os`, `collections`. Verified by a test that walks `src/` and asserts every import resolves to a stdlib module. |
| Runs on bare CPython, no install step | I. Standard Library Only | PASS | `PYTHONPATH=src python -m logredact` is the documented invocation; `pyproject.toml` carries pytest configuration only — no build backend, no dependencies, nothing to install. |
| Only `pytest` as a dev dependency | I. Standard Library Only | PASS | `pytest` is the test runner. No other dev tool is introduced, and `pytest` is not importable from runtime code. |
| Invalid input fails with a specific diagnostic and non-zero status | II. Fail Loudly | PASS | Unreadable FILE → message naming that path, exit 2 (FR-028). Bad option → argparse usage, exit 2 (FR-030). Failed stdout write → concise diagnostic, exit 2 (FR-031a). Each names *what* was wrong: the path, the option, or the output stream. |
| No silent wrong answer | II. Fail Loudly | PASS | The expensive failure here is a truncated log that looks complete. FR-029 stops reading on the first unreadable source and suppresses the tally; FR-031a makes an interrupted write exit 2. Both are tested by asserting the exit status, not just the text. |
| No bare `except:` / `except Exception: pass` | II. Fail Loudly | PASS | Two `except OSError` sites only. The read site re-raises as a path-naming diagnostic and exits 2; the write site converts to `OutputWriteError` and exits 2. Neither swallows, both still fail. |
| Every FR maps to a citing test | III. Every Requirement Is Testable | PASS | Requirement-to-test matrix in [quickstart.md](./quickstart.md); each test name or docstring cites its FR identifier. 36 identifiers (FR-001–FR-031 plus FR-005a, FR-007a, FR-019a, FR-030a, FR-031a) all mapped, and `tests/test_requirement_coverage.py` fails the suite if any citation is lost. The "32" written here and in SC-004 was a miscount of this same enumeration (31 + 5), corrected during T035. |
| Error behaviour has message + signal tests | III. Every Requirement Is Testable | PASS | Four failure paths (missing file, unreadable file, invalid usage, failed write) each have a test asserting the diagnostic, the exit status 2, and the absence of `Traceback` on stderr (SC-005). |
| Smallest design that satisfies the spec | IV. Simplicity | PASS | Functions over classes: redaction is one pure function returning `(text, Counter)`. No configuration layer, no category toggles, no plugin seam, no abstraction over input sources beyond a generator. Three modules, each with a distinct reason to exist (see Structure Decision). |
| Plain data over hierarchies | IV. Simplicity | PASS | `collections.Counter` for the tally; `str` in, `str` out; one internal exception class, justified in Complexity Tracking. |

**Pre-Phase 0 result**: PASS — no violations, no deviations recorded.

**Post-Phase 1 re-check**: PASS — the design artifacts introduce no new dependency, no new class
hierarchy, and no unrequired structure. The one structure that is not obviously necessary (the
`OutputWriteError` exception) is justified in Complexity Tracking below. See
[research.md](./research.md) for the one specification conflict found during Phase 0 and the
decision taken on it; it changes behaviour on a single input form, not the design.

## Project Structure

### Documentation (this feature)

```text
specs/001-logredact-cli/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── cli.md           # Command-line contract: invocation, streams, exit status
│   └── redaction-patterns.md  # Recognition grammar for the three categories
├── checklists/
│   └── requirements.md  # Pre-existing spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml           # pytest configuration only (pythonpath=src, testpaths=tests)

src/
└── logredact/
    ├── __init__.py      # Package marker; exports nothing (FR nothing requires a library API)
    ├── __main__.py      # `python -m logredact` entry: sys.exit(cli.main(sys.argv[1:]))
    ├── redact.py        # Pure text layer: patterns, Luhn, redact_line(str) -> (str, Counter)
    └── cli.py           # I/O layer: argparse, stream setup, source loop, tally, exit status

tests/
├── conftest.py          # run_cli() helper: subprocess invocation with PYTHONPATH=src
├── test_redact.py       # Unit: FR-005..FR-022 against redact_line
├── test_cli.py          # Contract: FR-001..FR-004, FR-023..FR-031a via subprocess
├── test_fidelity.py     # SC-002 mixed fixture, SC-003 byte-identity, SC-008 tally agreement
├── test_performance.py  # SC-006 bounded memory, SC-007 throughput (scaled, see research.md)
├── test_requirement_coverage.py  # SC-004 gate: every FR/SC identifier has a citing test
└── test_stdlib_only.py  # Principle I gate: no third-party import in src/
```

**Structure Decision**: Single package under `src/`, as mandated by the spec. The split between
`redact.py` and `cli.py` is the one architectural choice, and it is made because the two halves
have different test shapes: the text layer is a pure function testable with string in/string out
(fast, exhaustive, one test per recognition rule), while the I/O layer's requirements are about
streams, exit statuses, and byte-exact output, which need subprocess tests. Merging them would
force every recognition-rule test through a subprocess. `__main__.py` is required by `python -m`
and holds only the entry call so that `cli.main()` stays importable. No `models/`, `services/`,
or `lib/` directories: there is no model to persist and no service to call, so those layers from
the template would be empty ceremony.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| `OutputWriteError`, a custom exception class (Principle IV prefers plain functions and data) | FR-028 and FR-031a demand different diagnostics and must not be confused, but both surface as `OSError`. A write failure raised inside the per-source loop would be caught by that loop's `except OSError` and misreported as "cannot read FILE". `OutputWriteError` does not inherit from `OSError`, so it propagates past the read handler to its own handler. | Inspecting `errno` or `isinstance(exc, BrokenPipeError)` inside the read handler was rejected: it enumerates write failure modes (closed pipe, ENOSPC, EIO, …) and gets the attribution wrong for any mode not listed, which is exactly the silent-wrong-diagnostic Principle II forbids. Checking which stream raised is not possible from the exception alone. |
| Seven fixed-length card patterns in addition to the main alternation (duplication) | FR-019 requires the *longest Luhn-valid* candidate at a start position, and the main greedy pattern yields only the longest *syntactic* candidate. Deriving shorter candidates by hand-walking the characters would reimplement the separator rule a second time, in a second language, with a second chance to disagree with it. | A single hand-written scanner was rejected because the two implementations of "13–19 digits, single `[ -]` separators, digit at each end, not flanked by digits" would have to be kept in agreement by eye. The seven patterns are generated from the same octet/separator fragments as the main pattern, so they cannot drift. |
