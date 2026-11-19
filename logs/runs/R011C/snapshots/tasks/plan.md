# Implementation Plan: Redact Phone Numbers and Write Sanitized Copies to an Output Folder

**Branch**: `002-redact-phones-out-dir` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-redact-phones-out-dir/spec.md`

## Summary

Two additions to the shipped `logredact` tool, both verified by execution during Phase 0:

1. **Phone redaction** — one new branch at the end of the existing single compiled alternation,
   `\+[0-9]{8,15}(?![0-9])`, plus a fourth counter key. Its position last in the alternation *is*
   the FR-036 tie-break (email → IPv4 → card → phone); its ASCII `[0-9]` class *is* FR-031; its
   trailing `(?![0-9])` *is* FR-032; the absence of any lookbehind *is* FR-031a. FR-032a (a digit
   run preceded by `+` is never a card) is one guard line in the existing card validator, which
   already has a "return the candidate unchanged" path.
2. **`--out-dir DIR`** — one new argparse option and one alternative destination inside `cli.py`:
   create DIR first (FR-045), then per FILE open the input, open a sink named
   `basename(FILE)`, stream into it, and count one write. A tiny `_OutputError` wrapper lets a
   single `except` tell an input failure (name the FILE, FR-048) from an output failure (name the
   output path, FR-050); any failure after the sink was opened deletes the half-written file
   (FR-050a).

No new module, no new dependency, no new exit status. Measured cost: 1M lines in 8.5 s versus the
baseline's 8.6 s (SC-017), and the existing suite's only failures are the 25 assertions on the
three-key summary that SC-015 explicitly licenses.

## Technical Context

**Language/Version**: Python 3.11+ (the `_CARD` pattern's possessive quantifiers require 3.11;
verified on 3.13.17). Unchanged from feature 001 and restated by the user.

**Primary Dependencies**: None. Standard library only — `re`, `argparse`, `os`, `sys`
(Constitution Principle I).

**Storage**: Filesystem. New in this feature: the tool creates directories and writes files under
`--out-dir DIR`. No database, no state carried between runs.

**Testing**: `pytest`, tests under `tests/`, runnable by a bare `pytest` from the repository root
(`pytest.ini` sets `pythonpath = src`). Unit tests call the pure core in-process; CLI tests drive
`python -m logredact` through `subprocess` so exit status, stream separation, and real filesystem
effects are observed rather than simulated.

**Target Platform**: POSIX-like developer machines and CI. The design uses no platform-specific
call; `os.makedirs`, `os.path.basename`, and `os.remove` carry the behaviour.

**Project Type**: Single-project command-line tool, extending the existing `logredact` package.

**Performance Goals**: Unchanged in character (SC-017) — 1M lines well under 60 s, memory bounded
by the longest single line, in both destinations. Measured: 8.5 s to `/dev/null`, 8.7 s to
`--out-dir`, versus 8.6 s for the current tool on the same 88 MB input.

**Constraints**: Output files carry byte-for-byte the same text contract as standard output
(FR-044): UTF-8, `surrogateescape` round-trip, no line-ending translation. Streaming only — no
file is buffered whole (FR-044, SC-017). Exit status set stays `{0, 2}` (FR-053, SC-014).

**Scale/Scope**: ~70 lines added to `cli.py`, ~10 to `redact.py`; 2 new test modules and 5
extended ones. 25 existing assertions updated to the four-key summary form.

No NEEDS CLARIFICATION remains: the spec's four clarifications plus the user's instruction
(Python 3.11+, standard library only, the spec's interface exactly, pytest) close every open
question. Two **spec defects** found while planning are recorded at the end of this document;
neither blocks implementation.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Pre-Phase-0 | Post-Phase-1 |
|-----------|------|-------------|--------------|
| I. Standard Library Only | No third-party runtime import; runs on a bare interpreter | PASS — `re`, `argparse`, `os`, `sys` only; nothing new imported | PASS — design adds no import at all |
| II. Fail Loudly | Every new failure mode gets a specific diagnostic naming the offending input, plus exit 2; `except` clauses narrow, recovering or re-raising | PASS — FR-049, FR-050, FR-050a, FR-051 all specify diagnostic + status 2 | PASS with one justified exception, in Complexity Tracking: the `sink.close()` inside the discard path swallows `OSError` on a file being deleted |
| III. Every Requirement Is Testable | Each of FR-030…FR-054 maps to at least one `pytest` test that fails when unmet; each error path has its own test asserting status *and* diagnostic | PASS — all 28 requirements are observable from stdout/stderr/exit status/filesystem | PASS — traceability table below; 2 new test modules, 5 extended |
| IV. Simplicity | Smallest design meeting the spec; no speculative abstraction | PASS — one regex branch, one counter key, one option | PASS with two justified additions, in Complexity Tracking: `_OutputError` and the `_sink_writer` closure |

**No gate fails.** Two deliberate, requirement-anchored deviations are recorded in Complexity
Tracking rather than waved through.

## Project Structure

### Documentation (this feature)

```text
specs/002-redact-phones-out-dir/
├── plan.md                        # This file (/speckit-plan command output)
├── spec.md                        # Feature specification
├── research.md                    # Phase 0 output — 12 decisions (R-010 … R-021), all verified by execution
├── data-model.md                  # Phase 1 output — the entities this feature adds or changes
├── quickstart.md                  # Phase 1 output — 12 runnable validation scenarios
├── contracts/                     # Phase 1 output
│   ├── cli-contract.md            # The extended CLI; supersedes 001's cli-contract.md
│   └── redaction-rules.md         # The phone rule and the card narrowing; amends 001's redaction-rules.md
├── checklists/                    # Pre-existing quality checklist
└── tasks.md                       # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/
└── logredact/
    ├── __init__.py                # Unchanged — package marker
    ├── __main__.py                # Unchanged — `raise SystemExit(main())`
    ├── redact.py                  # CHANGED: + _PHONE branch, + PHONE_PLACEHOLDER, + "phones" key,
    │                              #          + the FR-032a guard in the card validator
    └── cli.py                     # CHANGED: + --out-dir option, + usage check (FR-051),
                                   #          + DIR creation, + sink open/write/close/discard,
                                   #          + "wrote N files", + four-key summary

tests/
├── unit/
│   ├── test_patterns.py           # EXTENDED: phone recognition and non-recognition (FR-030 … FR-034),
│   │                              #           the card narrowing (FR-032a)
│   ├── test_luhn.py               # Unchanged
│   ├── test_precedence.py         # EXTENDED: phone vs email/card overlap and tie-break (FR-035, FR-036);
│   │                              #           4-key dict assertions
│   └── test_counting.py           # EXTENDED: the phones counter (FR-038); 4-key dict assertions
└── cli/
    ├── test_invocation.py         # EXTENDED: --out-dir accepted in any position (FR-040); 4-key summary
    ├── test_output_fidelity.py    # EXTENDED: 4-key summary; phone near-miss control sample (SC-009)
    ├── test_count_flag.py         # EXTENDED: the four-key summary form (FR-037, FR-039)
    ├── test_failures.py           # Unchanged — the inherited failure paths must still hold
    ├── test_broken_pipe.py        # Unchanged
    ├── test_out_dir.py            # NEW: User Story 3 — naming, creation, replacement, N, --count (FR-040 … FR-047, FR-052)
    └── test_out_dir_failures.py   # NEW: User Story 4 — every failure path and the partial-file rule (FR-048 … FR-051, FR-050a)

pytest.ini                         # Unchanged
```

**Structure Decision**: Keep feature 001's two-module split exactly as it is. `redact.py` stays
pure (text in, text and counts out) and absorbs the whole phone rule; `cli.py` stays the only
module that touches the process and absorbs the whole `--out-dir` destination. The new code lands
on the side of the line it already belongs to, so no third module, no I/O layer, and no "sink"
abstraction is introduced (Principle IV).

Concretely, a destination is **not** modelled as a class or a strategy object. `_redact_stream`
already takes its lines from any iterable; it gains a `write` parameter, and the two destinations
are `sys.stdout.write` and a per-file writer. That is the whole polymorphism the spec needs: one
parameter, two call sites. A `Destination` hierarchy with `StdoutDestination` and
`DirectoryDestination` would be an extension point no requirement asks for.

The test split mirrors the source split and the spec's user stories: units for recognition rules,
subprocess tests for everything the contract states about the process and the filesystem. The two
new CLI modules are split along Story 3 (it works) / Story 4 (it fails correctly) because the
failure module needs filesystem fixtures — unwritable parents, a path that is a directory,
`/dev/full` — that the success module does not.

## Phase 0: Research — complete

[research.md](./research.md) records twelve decisions, R-010 through R-021, continuing feature
001's series. Every one was verified by running code before it was written down; the three that
changed the design are:

| ID | Decision | Serves |
|----|----------|--------|
| R-010 | Phone pattern `\+[0-9]{8,15}(?![0-9])` — ASCII class, trailing-digit guard, **no** lookbehind | FR-030 … FR-034 |
| R-011 | Phone branch placed **last** in the existing alternation; branch order is the tie-break | FR-035, FR-036 |
| R-012 | FR-032a implemented **in the card validator**, not as a `(?<!\+)` lookbehind — the lookbehind variant was verified to *create* new `[CARD]` matches (`+1 4111111111111111` → `+1 [CARD]`), which FR-054 forbids | FR-032a, FR-054 |
| R-013 | The inherited `\d` in the IPv4 and card patterns stays Unicode-wide; FR-054 forbids narrowing it. FR-031's parenthetical about the existing rules is factually wrong (defect D-2 below) | FR-031, FR-054 |
| R-014 | `--out-dir` as an `argparse` option; `parser.error()` for the no-FILE case, reusing the FR-029 path verbatim | FR-040, FR-051 |
| R-015 | `os.makedirs(DIR, exist_ok=True)` before the first input opens; `OSError.strerror` supplies the reason | FR-042, FR-045, FR-049 |
| R-016 | Output name from `os.path.basename(FILE)` | FR-041 |
| R-017 | **Input opened before the sink.** The spec is ambiguous; this ordering is the non-destructive reading and satisfies every acceptance scenario | FR-048, FR-050a |
| R-018 | `_OutputError` wrapper around sink open/write/close, so one handler names the right path | FR-048, FR-050 |
| R-019 | Discard the half-written file on any failure after the sink opened; report a failed removal as a second diagnostic | FR-050a |
| R-020 | Sink opened `"w"`, UTF-8, `surrogateescape`, `newline=""` — the same four arguments as the stdout reconfigure | FR-044 |
| R-021 | `new_counts()` is the single source of the counter key names; `totals` and the accumulation loop both derive from it | FR-037, FR-038 |

The design was run against **every** acceptance scenario and edge case in the spec. All produced
the specified output; the transcripts are in research.md.

## Phase 1: Design & Contracts — complete

- **[data-model.md](./data-model.md)** — the two entities this feature adds (output destination,
  output file) with their lifecycle, the two it changes (redaction type, redaction counts), and
  the run-level state including the write counter.
- **[contracts/cli-contract.md](./contracts/cli-contract.md)** — the extended public interface:
  the new invocation grammar, the two destinations, the four-key summary, `wrote N files`, the
  three new failure behaviours, and the partial-file guarantee. Supersedes 001's CLI contract.
- **[contracts/redaction-rules.md](./contracts/redaction-rules.md)** — the phone pattern, its
  recognition table, the narrowed card rule, and the four-way precedence, with worked examples.
- **[quickstart.md](./quickstart.md)** — twelve runnable validation scenarios covering all four
  user stories, plus the byte-fidelity, partial-file, and performance checks.

### Requirement traceability

| Requirement | Where it is implemented | Where it is tested |
|-------------|------------------------|--------------------|
| FR-030, FR-031 | `_PHONE` pattern + `PHONE_PLACEHOLDER` in `redact.py` | `tests/unit/test_patterns.py` |
| FR-031a | absence of a lookbehind on `_PHONE` | `tests/unit/test_patterns.py` (`v2+…`, `x=99+…`, line start) |
| FR-032 | `(?![0-9])` trailing guard | `tests/unit/test_patterns.py` (7, 8, 15, 16 digits) |
| FR-032a | `+`-preceded guard in the card validator | `tests/unit/test_patterns.py`, `tests/unit/test_precedence.py` |
| FR-033, FR-034 | pattern shape (`{8,15}`, no trailing class) | `tests/unit/test_patterns.py` |
| FR-035, FR-036 | branch order in `PATTERN`, `re.sub` left-to-right | `tests/unit/test_precedence.py` |
| FR-037, FR-039 | `_write_summary` format string; return-before-summary on every failure path | `tests/cli/test_count_flag.py`, `tests/cli/test_out_dir_failures.py` |
| FR-038 | `"phones"` in `new_counts()`; accumulation loop | `tests/unit/test_counting.py`, `tests/cli/test_count_flag.py` |
| FR-040 | `add_argument("--out-dir")` + `parse_intermixed_args` | `tests/cli/test_invocation.py` |
| FR-041 | `os.path.join(out_dir, os.path.basename(name))` | `tests/cli/test_out_dir.py` |
| FR-042, FR-045 | `os.makedirs(exist_ok=True)` before the loop | `tests/cli/test_out_dir.py` |
| FR-043 | sink opened in `"w"` mode | `tests/cli/test_out_dir.py` |
| FR-044 | sink `open()` arguments | `tests/cli/test_out_dir.py` (bytes compared against the stdout run) |
| FR-046, FR-047, FR-052 | `written` counter; single `sys.stdout.write` after the loop | `tests/cli/test_out_dir.py` |
| FR-048 | `except OSError` naming `name`; return 2 | `tests/cli/test_out_dir_failures.py` |
| FR-049 | `except OSError` around `makedirs`, naming DIR | `tests/cli/test_out_dir_failures.py` |
| FR-050 | `except _OutputError` naming `failure.path` | `tests/cli/test_out_dir_failures.py` (`/dev/full`, path-is-a-directory) |
| FR-050a | `_discard` — close, `os.remove`, report a failed removal | `tests/cli/test_out_dir_failures.py` |
| FR-051 | `parser.error()` when `out_dir` is set and `files` is empty | `tests/cli/test_out_dir_failures.py` |
| FR-053, FR-054 | everything above is additive; `tests/cli/test_failures.py` and `test_broken_pipe.py` stay untouched | the unchanged modules, plus a byte-identity test against the pre-change tool |

### Verified against the spec's own numbers

| Success criterion | Phase 0 measurement |
|-------------------|---------------------|
| SC-008 / SC-009 | Every phone case and near-miss in the spec produced the specified output, including `+4111111111111111` unchanged |
| SC-011 / SC-012 | `--out-dir` over 2 files: `wrote 2 files`, contents byte-identical to the stdout run; deep DIR created; a 26-byte pre-existing file replaced by a 9-byte one |
| SC-013 / SC-013a | All four failure paths: diagnostic naming the path, no confirmation line, no summary, no traceback, exit 2; the half-written file absent, the earlier file complete |
| SC-015 | The existing suite against the prototype: **25 failures, all 25 on the summary shape** (15 counts-dict assertions, 10 summary-line assertions). Zero redaction-output regressions |
| SC-017 | 1M lines / 88 MB: baseline 8.6 s, prototype 8.5 s (stdout) and 8.7 s (`--out-dir`) |

### Spec defects found while planning (neither blocks implementation)

- **D-1 — FR-051 has no label.** Its text ("`--out-dir` given with no FILE argument MUST be treated
  as invalid usage under FR-029…") is appended to the end of FR-050a's paragraph in spec.md:371,
  while Assumptions and SC-013 both refer to **FR-051** by number. The requirement itself is
  unambiguous and is implemented as written; the spec should be patched to split the paragraph and
  restore the `**FR-051**:` label.
- **D-2 — FR-031's claim about the existing rules is wrong.** FR-031 says non-ASCII decimal digits
  "MUST be left unchanged, exactly as the existing IPv4 and payment-card rules are read". The
  existing patterns use `\d`, which in Python matches every Unicode decimal digit, and `int()`
  accepts them — so a 13-to-19-digit Arabic-Indic run that passes Luhn is redacted as `[CARD]`
  today. The new phone rule uses `[0-9]` and is correct. Narrowing the inherited patterns would
  change the output of inputs containing no phone number and no `+`-prefixed run, which **FR-054
  forbids**, so this plan deliberately leaves `\d` alone. Recorded in research.md R-013; worth a
  follow-up spec decision, not a change smuggled into this feature.

## Complexity Tracking

> Two additions beyond the most literal design, each demanded by a specific requirement.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `_OutputError`, a one-attribute exception class wrapping sink `open`/`write`/`close` failures, plus the `_sink_writer` closure that applies it per line (Principle IV) | FR-048 requires the diagnostic to name the **input** file; FR-050 requires it to name the **output** path. Once both files are open, an `OSError` from the streaming loop is ambiguous — `OSError.filename` is unset for read and write errors on an open handle (verified) — so a single `except OSError` would name the wrong path roughly half the time, violating Principle II's "diagnostics MUST name which input caused it" | Catching `OSError` once and naming the input: verified to misattribute a `/dev/full` write failure to the input file. Inspecting `OSError.filename`: unset in exactly these cases. A per-line `try` on the read side instead: identical cost, and it misattributes the sink's `close()` failure. The measured cost of the closure plus zero-cost `try` is nil — 8.5 s versus the baseline's 8.6 s on 1M lines |
| `except OSError: pass` around `sink.close()` in the discard path (Principle II forbids swallowing handlers) | FR-050a requires the half-written file to be deleted **and** the original diagnostic (FR-048's input name or FR-050's output path) to be the one reported. The handle must be closed before `os.remove` for the deletion to be portable, and a flush failure at that close is almost always the very error already being reported — re-raising it would replace the primary diagnostic with a duplicate and skip the deletion | Letting it propagate: skips the `os.remove`, leaving exactly the truncated file FR-050a exists to prevent. Reporting it as a second diagnostic: duplicates the primary message on the common `ENOSPC` path, which FR-050a does not ask for — it asks only that a failed *deletion* be reported, and that is reported. The handler is narrow (`OSError`), on a file whose contents are being destroyed by design, and recovers meaningfully: it lets the deletion and the real diagnostic through |
