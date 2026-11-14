# Implementation Plan: Log Redaction CLI

**Branch**: `001-logredact-cli` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-logredact-cli/spec.md`

## Summary

A zero-dependency CLI, `python -m logredact [--count] [FILE ...]`, that streams log text through
line-by-line and replaces email addresses with `[EMAIL]`, IPv4 addresses with `[IP]`, and
Luhn-valid 13–19 digit card numbers with `[CARD]`, passing everything else through byte-for-byte.
`--count` adds a one-line tally on stderr; an unreadable operand or an over-length line fails the
run with status 2 and a diagnostic that names the source but never the data. An unreadable operand
is reported and skipped so the remaining operands are still redacted in the same pass, with the
status settled at the end of the run; an over-length line, by contrast, stops the run at once, as
FR-018 requires.

The technical approach is deliberately small: one compiled pattern with three named alternatives in
precedence order, applied with `re.sub` once per line, plus a bounded scan inside digit runs for
card candidates. `re.sub`'s own semantics deliver FR-014 (leftmost, non-overlapping, ordered
alternatives, replacements never re-scanned) with no bookkeeping of our own, and
`readline(CAP + 1)` delivers SR-005's memory bound in one call.

Two Phase 0 findings changed the design, both measured:

1. **The obvious email pattern is quadratic** and would take an extrapolated ~1.5 hours on a single
   1 MiB line — a usable denial of service and a direct SR-005 violation. A negative lookbehind
   that stops the local part being retried at every position inside a run restores linear time
   (measured 1.2 ms vs 7,142 ms at 80 KB) and provably does not change which text matches.
2. **Checking only the maximal digit run leaves real cards in the output.** `log 1 2 3 4111 1111
   1111 1111 end` is one 19-digit run whose Luhn check fails, so the embedded card survives — a
   silent redaction gap and an SC-005 failure. Card candidates must therefore be searched at group
   boundaries inside a run, which is done with an incrementally updated Luhn sum in O(1) memory
   (measured 3.4 s worst case per adversarial 1 MiB line, down from 15.8 s and no longer
   allocating per candidate).

A 28-case prototype of the full rule set passes 28/28, including every worked example and every
edge case the spec enumerates. Details and measurements: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.11+ (floor set by A-10 and the user input for this step; verified
here on 3.13.17). No syntax or library newer than 3.11 is used.

**Primary Dependencies**: None. Standard library only — `re`, `io`, `sys`, `os`, `signal`,
`argparse` (Principle I, A-10).

**Storage**: N/A. Nothing is persisted; no temporary files, caches, or logs (SR-007).

**Testing**: `pytest` (A-11) — the only development dependency the constitution permits without
justification. Unit tests against `redact_line()`; contract tests that run
`python -m logredact` in a subprocess and compare raw bytes on stdout/stderr plus exit status
([research.md R13](./research.md)).

**Target Platform**: Any POSIX-like system with CPython 3.11+. The only platform-specific
behaviour is the `SIGPIPE`/status-141 path (A-7).

**Project Type**: Single-package CLI tool, `logredact` under `src/`, run as `python -m logredact`
with `src/` on `PYTHONPATH`.

**Performance Goals**: No goal is stated in the spec, so these were measured in Phase 0 and are
adopted as the regression tripwires ([research.md R14](./research.md)): at least 1 MB/s on
realistic log text (measured 4.7 MB/s, ~50,000 lines/s); any adversarial 1 MiB line under 10 s
(measured worst case 3.4 s); every pattern linear in line length (SR-005).

**Constraints**: Peak memory bounded by roughly the 1 MiB line cap and independent of total input
size (FR-016, SR-005, SC-006, SC-010) — measured ~2 MiB while rejecting an 8 MiB line.
Byte-for-byte pass-through including invalid UTF-8 and line terminators (FR-008, FR-009, A-4).
Exit statuses limited to 0, 2, and 141 (FR-015, FR-012, FR-018, A-5, A-7).

**Scale/Scope**: One command, one option, three redaction kinds, ~250 lines of implementation
across four source files; 18 functional, 9 security, and 10 success-criteria items to cover with
tests.

**No NEEDS CLARIFICATION items remain.** All fourteen Phase 0 unknowns are resolved in
[research.md](./research.md). Two were genuine spec ambiguities rather than research questions and
are resolved there with the reasoning and the cost of reversal recorded — flagged here so the
decisions are visible before implementation:

- **R6**: FR-004's "dot-separated domain" is read as requiring at least one dot, so
  `user@localhost` is **not** redacted. Reversible in one pattern plus one test.
- **R9**: SR-001's allowlist is applied literally, so `--help` is **rejected** (argparse's help
  would write to stdout and exit 0, which SR-001 forbids). Unconventional for a CLI; reversing it
  needs an amendment to SR-001/A-9 plus one line.
- **R10** fills two gaps the spec leaves open: an unreadable operand is reported and skipped so
  that every remaining operand is still processed, with status 2 settled at the end of the run
  (**directed by the requester**, 2026-11-09, reversing this plan's original stop-at-first
  decision); and *no* `--count` tally is written on any non-zero exit (generalising FR-018's stated
  reason, and untouched by that direction).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0. Initial check (pre-Phase 0) and re-check (post-Phase 1) are both
recorded; the re-check column is what the gate is decided on.

| Principle | Requirement | Initial | Post-design | Evidence |
|---|---|---|---|---|
| I. Standard Library Only | No runtime third-party imports; runnable with no dependency resolution; only `pytest` for dev | PASS | **PASS** | `re`, `io`, `sys`, `os`, `signal`, `argparse` only. No capability needed a third-party package. `pyproject.toml` carries pytest config only, not packaging ([R1](./research.md)) |
| II. Fail Loudly | Diagnostic to stderr + non-zero status for every invalid input; no swallowed exceptions; no sentinel returns; defaults only where specified | PASS | **PASS** | Every failure path enumerated below; `OSError` caught narrowly at the open/read/write boundary and reported, never discarded; `BrokenPipeError` handled explicitly rather than suppressed; no bare `except`. Continuing past an unreadable operand is not swallowing it: each failure is reported on stderr as it happens and fixes the run's status at 2, which is the "clear, actionable message and a failure signal" the principle requires ([R10](./research.md), [R11](./research.md), [R12](./research.md)) |
| III. Every Requirement Is Testable | Every FR and SR maps to at least one automated test; mapping recorded in the plan | PASS | **PASS** | Mapping table below covers FR-001…018, SR-001…009, SC-001…010 with no unmapped item |
| IV. Simplicity | Smallest sufficient design; every abstraction justified against the requirement forcing it | PASS | **PASS** | Four source files, no classes, plain `dict`/`str`/`int` data ([data-model.md](./data-model.md)); each of the three departures from "most obvious thing" is justified in Complexity Tracking below |
| V. Secure by Default | Security requirements stated, testable, each mapped to baseline controls and to a test | PASS | **PASS** | SR-001…009 mapped to Security Baseline controls below and to tests in the mapping table |

### Principle II — error behaviour for every invalid-input case

Required explicitly by the planning gate.

| Invalid input | Behaviour | Status | Requirement |
|---|---|---|---|
| Unrecognised option (`--verbose`, `-h`, `--help`, `--cou`, `--count=1`) | argparse usage + message on stderr, nothing on stdout, nothing read | 2 | SR-001, A-5, [R9](./research.md) |
| Operand that does not exist | `cannot read 'FILE': No such file or directory` on stderr; **skip it and process the remaining operands** | 2, at end of run | FR-012, [R10](./research.md) |
| Operand that is a directory | `cannot read 'FILE': Is a directory`; skip and continue | 2, at end of run | FR-012 |
| Operand whose permissions deny reading | `cannot read 'FILE': Permission denied`; skip and continue | 2, at end of run | FR-012 |
| Several unreadable operands | one diagnostic per failing operand, in operand order; all readable operands still redacted | 2, at end of run | FR-012, [R10](./research.md) |
| Read error mid-file | same shape, naming the operand; skip the rest of that file and continue | 2, at end of run | FR-012, A-6 |
| Read error on standard input | same shape, naming `standard input`; nothing remains to process | 2 | A-6 |
| Line longer than 1 MiB | `SOURCE: line exceeds the maximum length of 1048576 characters`; no part of the line on stdout; no tally; **run stops, later operands not read** | 2, at once | FR-018, SR-005 |
| Output write or flush failure | `cannot write output: REASON`; run ends; never reported as success | 2, at once | SR-009, [R12](./research.md) |
| Standard output closed early | no traceback, no further writes | 141 | A-7, [R11](./research.md) |

No case returns a sentinel, and no case produces a silent partial success: every non-zero status
means the stdout content is incomplete ([contracts/cli.md](./contracts/cli.md)).

The two "continue or stop" answers differ because the spec treats them differently: FR-018 says an
over-length line "MUST stop processing", while FR-012 leaves continuation open, and the requester
directed that unreadable operands be reported individually with the rest of the operands still
processed. Status 2 is a single failure status however many operands failed (A-5).

### Principle V — security requirements mapped to Security Baseline controls

| Spec requirement | Baseline control relied on | How this design satisfies it |
|---|---|---|
| SR-001 argument allowlist | *Untrusted input* — validate against an explicit allowlist at the trust boundary | argparse with `add_help=False`, `allow_abbrev=False`: exactly `--count`, `--`, and operands; everything else rejected at entry before any I/O ([R9](./research.md)) |
| SR-002 all input untrusted, no shell | *No string concatenation into interpreters* | No `subprocess`, no `os.system`, no `eval`/`exec`, no `%`/`format`/f-string of input into any message; input is only ever matched against fixed patterns and copied to stdout |
| SR-003 no personal data in diagnostics | *Output, logs, and errors* — report that a field was rejected, not its contents | Diagnostics carry only the operand name the caller supplied and an OS `strerror`; no line, match, or fragment is ever formatted into a message; no traceback on any handled path |
| SR-004 tally contains only three integers | *Output, logs, and errors* | Fixed format string with three `int` counters; nothing derived from the data can reach it ([contracts/cli.md](./contracts/cli.md)) |
| SR-005 bounded time and memory | *Resource limits* — enforced maximum input size; no catastrophic backtracking | `readline(CAP + 1)` caps a line at 1 MiB with an 8 KiB margin (measured); all three patterns measured linear, with the quadratic email pattern found and fixed in Phase 0 ([R2](./research.md), [R5](./research.md), [R8](./research.md)) |
| SR-006 complete replacement | *Output, logs, and errors* | Placeholders are fixed literals; no digits, characters, or length information survive, and longest-candidate selection avoids leaving part of a card behind |
| SR-007 no writes outside stdout | *File permissions* — no temporary files at predictable paths | No file is opened for writing, no `tempfile`, no logging handler; the only output sinks are stdout and stderr |
| SR-008 operands opened read-only, as given | *No string concatenation into interpreters* — path handling | `open(operand, "r", …)` with the operand string verbatim: no `join`, no `resolve`, no `glob`, no normalisation |
| SR-009 write failures not discarded | *Untrusted input* / fail-loudly | Explicit flush before the tally and before the success return; `OSError` on write or flush fails the run ([R12](./research.md)) |

No Security Baseline control is waived. Controls that do not apply to this surface (SQL, secrets
storage, randomness, access control, archive extraction, decompression) are not engaged by this
feature: it opens no network, stores no credential, generates no token, and extracts no archive.

### Requirement-to-test mapping

Required by Principle III and the planning gate: an unmapped requirement must be visible before
implementation starts. Test files are listed under Project Structure; contract IDs (C-nn) are
defined in [contracts/cli.md](./contracts/cli.md).

| Requirement | Test |
|---|---|
| FR-001 invocable as `python -m logredact`, 0+ operands | `test_cli_stream.py::test_module_invocation` (C-01), `test_cli_files.py::test_two_operands` |
| FR-002 no operand → stdin | `test_cli_stream.py::test_reads_stdin_when_no_operands` (C-01) |
| FR-003 operands read in order, stdin untouched | `test_cli_files.py::test_operand_order`, `::test_reverse_order`, `::test_stdin_not_read_when_operand_given` (C-07, C-08, C-09) |
| FR-004 emails → `[EMAIL]` | `test_redaction_rules.py::test_email_shapes` (all rows of the email table) |
| FR-005 IPv4 → `[IP]`, out-of-range untouched | `test_redaction_rules.py::test_ipv4_shapes`, `::test_ipv4_out_of_range` (C-03) |
| FR-006 cards → `[CARD]` in every allowed grouping | `test_redaction_rules.py::test_card_groupings` |
| FR-007 Luhn failure untouched | `test_redaction_rules.py::test_luhn_failure_untouched` (C-02) |
| FR-008 non-matched characters unchanged | `test_redaction_rules.py::test_surrounding_text_preserved`, `::test_separator_between_adjacent_cards_preserved` |
| FR-009 clean line byte-for-byte, terminator preserved | `test_cli_stream.py::test_passthrough_byte_identical`, `::test_crlf_and_missing_final_newline` (C-21) |
| FR-010 `--count` format, after flushed output, run totals | `test_cli_count.py::test_count_format` (C-04), `::test_totals_across_operands`, `::test_summary_after_output` |
| FR-011 no `--count` → stderr empty | `test_cli_count.py::test_no_stderr_without_count` |
| FR-012 unreadable operand → named diagnostic, status 2 | `test_cli_errors.py::test_missing_file`, `::test_directory_operand`, `::test_unreadable_permissions` (C-11…C-13) |
| FR-012 + [R10](./research.md) remaining operands still processed, one diagnostic each, status settled at end of run | `test_cli_errors.py::test_continues_past_unreadable_operand` (C-23), `::test_reports_every_unreadable_operand` (C-24), `::test_no_tally_when_an_operand_failed` (C-26) |
| FR-013 no matching inside a larger token | `test_redaction_rules.py::test_card_flanked_by_digit`, `::test_ipv4_flanked_by_digit_or_dot` |
| FR-014 precedence, redacted once, counted once, no re-scan | `test_redaction_rules.py::test_email_beats_ipv4`, `::test_placeholder_not_rescanned`, `::test_counts_once_per_replacement` |
| FR-015 success → status 0 | `test_cli_stream.py::test_status_zero_on_success` (C-05) |
| FR-016 streaming, memory bounded by a line | `test_resource_bounds.py::test_peak_memory_independent_of_input_size` (SC-006) |
| FR-017 operands never modified | `test_cli_files.py::test_operands_unmodified` (content + mtime unchanged) |
| FR-018 over-length line → stop, diagnostic, no partial line, no tally | `test_cli_errors.py::test_over_length_line` (C-16), `::test_line_exactly_at_cap` (C-17), `::test_no_tally_on_over_length` (C-18), `::test_over_length_line_stops_remaining_operands` (C-25 — the counterpart to C-23, pinning the deliberate asymmetry) |
| SR-001 argument allowlist | `test_cli_errors.py::test_rejected_options` (parametrised: `--verbose`, `-h`, `--help`, `--cou`, `--count=1`) (C-15), `::test_double_dash_separator` (C-20) |
| SR-002 input never interpreted; no subprocess | `test_redaction_rules.py::test_format_specifiers_in_input_are_inert`, `test_cli_errors.py::test_shell_metacharacters_in_operand_name`, static check `test_no_subprocess_import` |
| SR-003 diagnostics disclose no personal data | `test_cli_errors.py::test_diagnostic_has_no_input_data`, `::test_no_traceback_on_any_error_path` (C-14) (SC-008) |
| SR-004 tally content restricted | `test_cli_count.py::test_summary_is_exactly_three_integers` |
| SR-005 bounded resources, linear patterns, 1 MiB cap | `test_resource_bounds.py::test_adversarial_lines_are_linear` (parametrised over the six adversarial shapes, doubling sizes), `::test_over_length_line_not_loaded_into_memory`, `test_cli_errors.py::test_line_exactly_at_cap` |
| SR-006 complete replacement | `test_redaction_rules.py::test_no_fragment_of_match_survives` (asserts no digit of a redacted card and no character of a redacted address appears in the output) |
| SR-007 no writes outside stdout | `test_cli_files.py::test_no_files_created_or_modified` (directory snapshot before/after) |
| SR-008 operands opened read-only, verbatim | `test_cli_errors.py::test_no_path_construction` (operand with `..`, a symlink, and a glob character is used as given, not resolved or expanded) |
| SR-009 write failure not silent | `test_cli_errors.py::test_write_failure_fails_run` (stdout to a full/closed sink) |
| SC-001 three worked examples byte-for-byte | `test_cli_stream.py::test_worked_examples` (C-01…C-04) |
| SC-002 100% of FR/SR mapped to a test | this table, checked at the implementation gate |
| SC-003 clean corpus byte-identical | `test_redaction_rules.py::test_clean_corpus_unchanged` |
| SC-004 near-miss corpus 0 redacted | `test_redaction_rules.py::test_near_miss_corpus_untouched` |
| SC-005 genuine-value corpus 100% redacted | `test_redaction_rules.py::test_genuine_corpus_fully_redacted` |
| SC-006 large input, memory flat | `test_resource_bounds.py::test_peak_memory_independent_of_input_size` |
| SC-007 unreadable file → status 2 + name | `test_cli_errors.py::test_missing_file` and siblings (parametrised) |
| SC-008 no personal data on stderr, ever | `test_cli_errors.py::test_diagnostic_has_no_input_data`, `test_cli_count.py::test_summary_is_exactly_three_integers` |
| SC-009 tally alone answers "how much" | `test_cli_count.py::test_count_format` (format is the whole contract) |
| SC-010 memory bounded, no over-length line emitted | `test_resource_bounds.py::test_over_length_line_not_loaded_into_memory`, `test_cli_errors.py::test_over_length_line` |

Two Phase 0 regression tests are also required, for defects found while prototyping
([R8](./research.md)): `test_separator_between_adjacent_cards_preserved` (FR-008) and
`test_adversarial_lines_are_linear` (SR-005 — the quadratic email pattern).

## Project Structure

### Documentation (this feature)

```text
specs/001-logredact-cli/
├── plan.md                        # This file
├── spec.md                        # Feature specification
├── research.md                    # Phase 0 output — 14 decisions with measurements
├── data-model.md                  # Phase 1 output — in-memory entities
├── quickstart.md                  # Phase 1 output — runnable validation guide
├── contracts/
│   ├── cli.md                     # Phase 1 output — invocation, streams, statuses, C-01…C-22
│   └── redaction-rules.md         # Phase 1 output — patterns and candidate selection
├── checklists/
│   └── requirements.md            # Spec quality checklist (complete)
└── tasks.md                       # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml                     # pytest configuration only (pythonpath = ["src"]); no packaging, no dependencies

src/
└── logredact/
    ├── __init__.py                # Package marker; no logic
    ├── __main__.py                # Entry point for `python -m logredact`: raise SystemExit(main())
    ├── redact.py                  # Patterns, Luhn, card candidate scan, redact_line(); pure, no I/O
    └── cli.py                     # Argument allowlist, input sources, line loop, diagnostics, tally

tests/
├── conftest.py                    # Fixture running the CLI in a subprocess, returning (status, stdout bytes, stderr bytes)
├── test_redaction_rules.py        # Unit: recognition, precedence, counting, corpora (FR-004…008, 013, 014, SR-006)
├── test_cli_stream.py             # Contract: Story 1 — stdin, pass-through, worked examples
├── test_cli_files.py              # Contract: Story 2 — operands, order, repetition, no side effects
├── test_cli_count.py              # Contract: Story 3 — --count format, stream separation, totals
├── test_cli_errors.py             # Contract: Story 4 — unreadable operands, rejected options, line cap
└── test_resource_bounds.py        # SR-005, SC-006, SC-010 — linearity and memory (marked slow)
```

**Structure Decision**: A single package, `src/logredact/`, with tests at the repository root —
fixed by A-10 (`logredact` under `src/`, invoked as `python -m logredact`). The split into
`redact.py` and `cli.py` is the one structural choice available, and it is made on Principle III
grounds: `redact.py` is pure (text in, text and counter increments out), so the ~60 recognition
and precedence cases run as fast in-process unit tests, while `cli.py` is exercised through the
real `python -m logredact` interface that FR-001 specifies. The `models/`, `services/`, and `lib/`
layering of the default template is not used — there are no models, no services, and nothing to
share.

## Complexity Tracking

The Constitution Check passes with no violations, so no justification is owed. Three places
nevertheless depart from the most obvious implementation, and Principle IV requires each to be
justified against the requirement that forces it. Recorded here so a reviewer can challenge them.

| Departure | Why needed | Simpler alternative rejected because |
|---|---|---|
| Negative lookbehind guarding the email pattern | SR-005 requires time linear in line length | The unguarded pattern is quadratic: measured 7,142 ms at 80 KB and extrapolating to ~1.5 hours for one 1 MiB line. Bounding the quantifiers with RFC limits also restores linearity but stops redacting emails with a local part over 64 characters — a redaction gap, which is the failure the tool exists to prevent ([R5](./research.md)) |
| Card candidate scan inside a digit run, instead of checking the matched run once | FR-006 + FR-013 + SC-005 — a card preceded by other bare numbers is still a card in an allowed grouping | Checking only the maximal run leaves `log 1 2 3 4111 1111 1111 1111 end` un-redacted: the 19-digit run fails Luhn and the real card survives in the output ([R8](./research.md)) |
| Incremental two-parity Luhn sum rather than recomputing per candidate | SR-005 and SC-010 — bounded time and memory per line | The straightforward version (tokenise the run, join and re-checksum each candidate) measured 15.8 s per adversarial 1 MiB line and allocated ~500,000 strings for one line, breaking SC-010's fixed memory bound. Prefix-sum arrays are faster still but allocate proportionally to the run ([R8](./research.md)) |

## Phase status

- [x] **Phase 0** — research complete; 14 unknowns resolved, 0 NEEDS CLARIFICATION remaining
      → [research.md](./research.md)
- [x] **Phase 1** — design complete → [data-model.md](./data-model.md),
      [contracts/cli.md](./contracts/cli.md),
      [contracts/redaction-rules.md](./contracts/redaction-rules.md),
      [quickstart.md](./quickstart.md)
- [x] **Constitution Check** re-evaluated after design: PASS on all five principles, no baseline
      control waived
- [ ] **Phase 2** — task breakdown (`/speckit-tasks`, not part of this command)
