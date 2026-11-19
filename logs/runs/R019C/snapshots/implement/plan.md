# Implementation Plan: Phone Number Redaction and Output Folder

**Branch**: `002-phone-redaction-out-dir` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-phone-redaction-out-dir/spec.md`

## Summary

Two amendments to the shipped `logredact` tool. **First**, a fourth redaction type: a `+`
followed by 8–15 digits becomes `[PHONE]`, the `--count` summary gains a fourth key
(`emails=N ips=N cards=N phones=N`), and a `+`-prefixed unbroken digit run is never read as a
payment card. **Second**, a new `--out-dir DIR` option that writes each FILE's redacted lines to
a file of the same name inside DIR instead of to standard output, printing `wrote N files` when
every FILE has been processed.

**Technical approach**: the phone rule is one more named alternative appended to the existing
precompiled alternation — `email | ip | card | phone` — so the regex engine's own leftmost-first
semantics deliver FR-004 and FR-005 with no new resolution logic, exactly as they already
deliver `001:FR-018`/`001:FR-019`. The pattern `\+\d{8,15}(?!\d)` carries FR-003 ("too many
digits is no match at all") in its trailing guard. FR-003a lands in the existing validator
callback, beside the octet-range and Luhn checks, because the pattern-level alternative is
provably wrong for the separated form (research.md R-002).

`--out-dir` is a change to **where** the per-line write goes, not to how redaction works: the
streaming loop is parameterised on its output stream, and a per-FILE wrapper opens the input
first and the output second — which is what makes FR-017a's "no stray file for an unreadable
input" true by ordering rather than by cleanup. A pre-flight checks the no-FILE usage error, the
output-is-its-own-input collision for every FILE, and the destination itself, all before the
first FILE is opened. Standard library only; `pytest` for tests.

Every mechanism above was executed and verified in Phase 0, including the two that contradict
the obvious first implementation: adding `(?<!\+)` to the card pattern silently breaks
`+4111 1111 1111 1111`, and a failing `close()` — not a failing `write()` — is how a full
filesystem usually surfaces. See [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.11+ (user-specified; also the floor for the possessive
quantifiers the existing card pattern relies on). Unchanged from 001 — not raised.

**Primary Dependencies**: None. Standard library only — `re`, `argparse`, `sys`, `os`
(Constitution Principle I; user-specified). This feature adds **no** new import: `os` is already
imported for the broken-pipe path and now also provides `makedirs`, `path.basename`,
`path.samefile`, and `remove`.

**Storage**: The destination folder is the only thing this tool now writes to disk. No database,
no persistence between runs, no state carried across inputs beyond four integer counters.

**Testing**: `pytest` (user-specified; Constitution), test-time only, imported by nothing under
`src/`. Tests run with a bare `pytest` from the repository root via the existing `pytest.ini`.

**Target Platform**: Any OS with CPython 3.11+; CI target is Linux. `os.path.samefile` and
`os.makedirs` are cross-platform; the broken-pipe path remains POSIX-shaped and degrades safely
as before.

**Project Type**: Single-project CLI tool (amendment to an existing one).

**Performance Goals**: Unchanged — 1,000,000 lines in under 60 s, memory flat with respect to
input size, with `--out-dir` as well as without (SC-007). The design keeps this by construction:
one output file is open at a time and nothing is accumulated.

**Constraints**: Output files are byte-identical to what stdout would have received, including
CRLF, a missing final newline, and invalid UTF-8 bytes (FR-013); exit status stays restricted to
`{0, 2}` (FR-023); the destination holds only complete output files at every exit (FR-017a);
every behaviour of 001 not named in FR-001…FR-022 is preserved (FR-023).

**Scale/Scope**: 25 functional requirements (FR-001…FR-023 plus FR-003a, FR-017a), 4 redaction
types, 1 command, 2 new modules' worth of work spread across the 2 existing modules — roughly
+20 lines in `redact.py` and +90 in `cli.py`.

**No NEEDS CLARIFICATION items**: the spec's three clarifications (2026-11-14) settled the
`+`-prefixed card question, the partial-output guarantee, and the timing of the collision check;
Phase 0 resolved the nine remaining technical unknowns.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.0.

| Principle | Gate | Pre-Phase 0 | Post-Phase 1 |
|-----------|------|-------------|--------------|
| **I. Standard Library Only** | No third-party runtime import; runnable on a bare interpreter with no `pip install`; `pytest` confined to tests | **PASS** — the feature needs pattern matching and filesystem calls, both in the standard library | **PASS** — design adds **zero** new imports; `os` was already imported. Still run as `PYTHONPATH=src python -m logredact`, no install step |
| **II. Fail Loudly** | Invalid input produces a specific diagnostic naming the offending input plus a non-zero status; no broad or swallowing `except` | **PASS** — FR-016 to FR-020 each demand a named diagnostic and exit 2; FR-017a goes further and forbids leaving a *plausible-looking* partial result on disk, which is Principle II's "silent wrong answer" applied to the filesystem | **PASS** — five failure paths, each naming the path the user typed (research.md R-005, R-008). Mid-stream failures are attributed structurally, not guessed from `error.filename`. One swallowed `OSError` in `_discard`, recorded in *Complexity Tracking* |
| **III. Every Requirement Is Testable** | Every FR maps to a failing-when-unmet `pytest` test; every error path asserts both signal and diagnostic | **PASS** — all 25 FRs are observable through stdout, stderr, exit status, or the contents of the destination folder | **PASS** — the phone rule is unit-testable through `redact_line` with no I/O; the `--out-dir` paths are observable from the subprocess harness plus `tmp_path`. FR-017a is directly assertable: list the destination and compare bytes |
| **IV. Simplicity** | Smallest design that satisfies the spec; no speculative abstraction; fewer moving parts wins | **PASS** — one new option, one new type, no configuration, no plugin surface | **PASS** — no class, no registry, no "writer" abstraction: a fourth alternation branch, a fourth counter key, and one parameter threaded through the existing write loop. Three richer alternatives were considered and rejected in research.md (R-002 doubled pattern, R-007 temp-file + `os.replace`, R-008 custom exception class) |

**Additional constraints**: Python 3 with the minimum version stated above and **not raised** ✓;
`pytest` under `tests/`, bare invocation from the repository root ✓; text in/out contract —
results to stdout (or to the named destination), diagnostics to stderr, 0 on success and
non-zero on failure ✓; no hidden state — the destination comes from an explicit option, encoding
stays pinned rather than inherited from the environment, and all four counters are run-local ✓.

**Result**: PASS at both gates. No principle requires a deviation; the one entry in Complexity
Tracking is a justified narrow swallow, not a violation.

## Project Structure

### Documentation (this feature)

```text
specs/002-phone-redaction-out-dir/
├── plan.md                      # This file (/speckit-plan output)
├── spec.md                      # Input
├── research.md                  # Phase 0 output — R-001…R-009
├── data-model.md                # Phase 1 output — amended entities
├── quickstart.md                # Phase 1 output — runnable validation guide
├── contracts/                   # Phase 1 output
│   ├── cli-contract.md          #   amended command-line surface
│   └── redaction-rules.md       #   phone rule + the FR-003a card amendment
└── tasks.md                     # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

The existing layout is kept; **no new module is created**. Each change lands in the module that
already owns that concern.

```text
src/logredact/
├── __init__.py        # unchanged (empty)
├── __main__.py        # unchanged — `raise SystemExit(main())`
├── redact.py          # AMENDED: pure matching core, no I/O
│                      #   + PHONE_PLACEHOLDER, _PHONE, fourth alternation branch
│                      #   + "phones" key in new_counts()
│                      #   + FR-003a branch in _replacement()
└── cli.py             # AMENDED: arguments, streams, sources, exit status
                       #   + --out-dir option and metavar="FILE"
                       #   + _preflight(): FR-019 usage, FR-020 collisions, FR-015 makedirs
                       #   + _write_file(): per-FILE input-then-output lifecycle (FR-017a)
                       #   + _redact_into(): output stream parameterised; error attribution
                       #   + _discard(): remove a partly-written output file
                       #   + "wrote N files" and the fourth summary key

tests/
├── unit/                        # pure matching core, no subprocess
│   ├── test_patterns.py         # AMENDED: + phone boundary cases
│   ├── test_precedence.py       # AMENDED: + phone/card/email overlap cases
│   ├── test_counting.py         # AMENDED: + "phones": 0 in dict assertions
│   ├── test_luhn.py             # unchanged
│   └── test_phones.py           # NEW: FR-001…FR-006 and FR-003a in one place
└── cli/                         # real subprocess, real exit status, real streams
    ├── conftest.py              # unchanged — the run_cli fixture already takes cwd
    ├── test_count_flag.py       # AMENDED: four-key summary
    ├── test_invocation.py       # AMENDED: four-key summary
    ├── test_output_fidelity.py  # AMENDED: four-key summary
    ├── test_failures.py         # unchanged
    ├── test_broken_pipe.py      # unchanged
    ├── test_out_dir.py          # NEW: FR-009…FR-015, FR-021, FR-022 (Story 2)
    └── test_out_dir_failures.py # NEW: FR-016…FR-020, FR-017a (Story 3)
```

**Structure Decision**: keep the existing two-module split — `redact.py` is pure text in, text
and counts out; `cli.py` owns everything that touches the process, the filesystem, and the exit
status. The feature's two halves fall cleanly either side of that line: the phone rule and
FR-003a are pure matching, and every `--out-dir` requirement is I/O. No third module and no
"output writer" class is introduced, because `--out-dir` changes which already-open stream the
existing loop writes to, which is a parameter, not an abstraction (Principle IV).

Tests mirror that split: the new phone rules are unit-tested directly against `redact_line`,
while every `--out-dir` requirement is asserted through a real subprocess, because the exit
status, the stream separation, and the state of the destination folder after a failure can only
be observed from outside the process. The two new CLI test files are split by story so that
Story 2 (happy path) and Story 3 (failures) can be delivered and verified independently.

## Phase 1 design in brief

The shape each requirement takes in code. Details and the rejected alternatives are in
[research.md](./research.md); the external contract is in
[contracts/cli-contract.md](./contracts/cli-contract.md).

**`redact.py`**

```python
PHONE_PLACEHOLDER = "[PHONE]"
_PHONE = r"\+\d{8,15}(?!\d)"                       # FR-002, FR-003
PATTERN = re.compile(rf"(?P<email>{_EMAIL})|(?P<ip>{_IP})|(?P<card>{_CARD})|(?P<phone>{_PHONE})")
```

`new_counts()` returns the four-key dict. In `_replacement`, the `phone` tag returns the
placeholder with no validation, and the `card` branch gains one guard in front of the length and
Luhn tests: a candidate with no separator whose preceding character is `+` is returned unchanged
and counted as nothing (FR-003a).

**`cli.py`**

| Requirement | Mechanism |
|-------------|-----------|
| FR-009 | `add_argument("--out-dir", dest="out_dir", metavar="DIR")`, still `parse_intermixed_args` |
| FR-019 | `parser.error("--out-dir requires at least one FILE")` — reuses argparse's usage + `SystemExit(2)` |
| FR-020 | pre-flight loop over every FILE using `os.path.samefile`, before anything is read |
| FR-015, FR-011, FR-016 | `os.makedirs(out_dir, exist_ok=True)` guarded by `except OSError` → `_report(out_dir, error)` |
| FR-010 | `os.path.join(out_dir, os.path.basename(name))` |
| FR-012, FR-013 | `open(out_path, "w", encoding="utf-8", errors="surrogateescape", newline="")` |
| FR-017a | input opens first, output second; `_discard(out_path)` on any failure after creation |
| FR-017, FR-018 | nested handlers in `_redact_into` return `(path, error)` so the diagnostic names the right path |
| FR-014, FR-022 | `sys.stdout.write(f"wrote {len(args.files)} files\n")`, then the existing `_write_summary` |
| FR-021, FR-023 | without `--out-dir`, `out` is `sys.stdout` and the code path is the one that ships today |

The existing `_report` and `_write_summary` are reused verbatim apart from the summary's fourth
key, so every new diagnostic automatically carries the established
`python -m logredact: <path>: <reason>` shape and the established stdout-flush-first ordering.

## Complexity Tracking

> Filled only for the one place the design deliberately departs from the strictest reading of a
> principle.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| `_discard()` swallows `OSError` (`except OSError: pass`), which Principle II's "no swallowing `except`" otherwise forbids | FR-017a requires a partly-written output file to be removed before exit. If the removal *itself* fails, the run is already failing, its real diagnostic is already composed, and nothing further can be done about the destination | Letting the removal error propagate would replace the user's real diagnostic ("`b.log`: No such file or directory") with a misleading one about a deletion they never asked for — hiding the actual cause, which is the failure mode Principle II exists to prevent. The handler is narrow (`OSError` only), cannot mask a *successful* run, and is commented with this reasoning in the source |

The second narrow handler, `except OSError: return False` in the FR-020 collision check, is
**not** a deviation: `os.path.samefile` raising means one of the two paths does not exist, which
is a definite answer ("they are not the same file"), and a missing FILE must reach the existing
FR-018 diagnostic rather than be reported as a collision. It recovers meaningfully, as the
principle requires.

The pre-existing `except BrokenPipeError: raise` guards are unchanged from 001 and keep their
original justification: `BrokenPipeError` is an `OSError`, and an early-closing consumer is not
a write failure.
