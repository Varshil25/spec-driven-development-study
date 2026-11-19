# Tasks: Phone Number Redaction and Output Folder

**Input**: Design documents from `/specs/002-phone-redaction-out-dir/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/cli-contract.md](./contracts/cli-contract.md),
[contracts/redaction-rules.md](./contracts/redaction-rules.md), [quickstart.md](./quickstart.md)

**Tests**: **INCLUDED and mandatory.** Constitution Principle III requires every functional
requirement to map to at least one failing-when-unmet `pytest` test, and each Principle II error
path to assert both the failure signal and the diagnostic. SC-008 requires every FR and every
edge case in the spec to be covered. Test tasks therefore precede implementation inside each
phase.

**Organization**: Tasks are grouped by user story so each story can be implemented and verified
as an independent increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are given in every task

## Path Conventions

Single project, existing layout (plan.md "Project Structure"); **no new module is created**:

- `src/logredact/redact.py` — pure matching core (no I/O)
- `src/logredact/cli.py` — arguments, streams, sources, exit status
- `tests/unit/` — pure core, no subprocess
- `tests/cli/` — real subprocess via the existing `run_cli` fixture in `tests/cli/conftest.py`

Run with `PYTHONPATH=src python -m logredact`; test with a bare `pytest` from the repository root
(`pytest.ini` sets `pythonpath = src`, `testpaths = tests`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the pre-change baseline this feature is measured against (SC-004).

- [ ] T001 Run `pytest` from the repository root and record that the existing suite passes before any change; this green run is the SC-004 baseline against which "no other behaviour moved" is judged
- [ ] T002 [P] Confirm `python3 --version` is 3.11 or newer (required by the possessive quantifiers already in `_CARD` in `src/logredact/redact.py`; the floor is NOT raised by this feature) and that a bare `pytest` from the repository root collects both `tests/unit/` and `tests/cli/` via `pytest.ini`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Two behaviour-preserving refactors of `src/logredact/cli.py` that every later phase
builds on — one place to add a counter key, and an output stream that is a parameter rather than
a hard-coded `sys.stdout`.

**⚠️ CRITICAL**: No user story work begins until this phase is complete. Both tasks are pure
refactors: the full existing suite MUST still pass unchanged afterwards, with no edits to any
test file.

- [ ] T003 Extract a `_accumulate(totals, counts)` helper in `src/logredact/cli.py` and replace the three inline `totals["emails"] += counts["emails"]` / `"ips"` / `"cards"` lines inside `_redact_stream` with a single call to it, so that adding a fourth counter key later touches exactly one place (data-model.md "Redaction counts"). No behaviour change.
- [ ] T004 Parameterise the per-line write loop on its output stream in `src/logredact/cli.py`: rename `_redact_stream(stream, totals)` to `_redact_into(stream, out, totals)`, replace `write = sys.stdout.write` with writes through the `out` argument, and pass `sys.stdout` explicitly at both call sites in `main()` (the stdin branch and the per-FILE branch). Nothing is accumulated, so memory stays bounded by the longest single line (SC-007). No behaviour change.
- [ ] T005 Run `pytest` and confirm the complete existing suite still passes with **zero** test-file edits, proving T003–T004 were behaviour-preserving

**Checkpoint**: `cli.py` now has one accumulation point and a parameterised output stream. The
tool's observable behaviour is still exactly what ships today.

---

## Phase 3: User Story 1 - Remove phone numbers from a shared log (Priority: P1) 🎯 MVP

**Goal**: A `+` followed by 8–15 digits becomes `[PHONE]`; a `+`-prefixed unbroken digit run is
never a card; the `--count` summary gains a fourth key `phones`. Needs no new option, so every
existing invocation benefits immediately.

**Independent Test**: Pipe `call +14155552671 now` into the tool with no arguments and confirm
stdout is exactly `call [PHONE] now\n` with exit status 0; then run
`echo 'a@b.io +442071838750' | python3 -m logredact --count` and confirm stdout is
`[EMAIL] [PHONE]` and stderr is `emails=1 ips=0 cards=0 phones=1`.

### Tests for User Story 1 ⚠️

> **Write these FIRST and confirm they FAIL before implementing T013–T018.**

- [ ] T006 [P] [US1] Create `tests/unit/test_phones.py` covering FR-001…FR-006 and FR-003a in one place, driving `redact_line` directly. Cases quoted from contracts/redaction-rules.md: the boundary table — `+1234567` (7 digits) unchanged, `+12345678` (8 digits) → `[PHONE]` with `phones=1`, `+123456789012345` (15 digits) → `[PHONE]` with `phones=1`, `+1234567890123456` (16 digits) unchanged **in full** with nothing counted, `+12345678901234567890123456789012` (32 digits) unchanged in full; the separated forms `+1 415 555 2671` and `+1-415-555-2671` not matched as phones; `5+14155552671` → `5[PHONE]` (a preceding digit does not disqualify the `+`); `ring +14155552671, then +442071838750.` → `ring [PHONE], then [PHONE].`; the literal `[PHONE]` passing through unchanged and uncounted (FR-006); and the FR-003a rows — `+4111111111111111` unchanged with `cards=0 phones=0`, `+4111111111119` → `[PHONE]` counted as a phone not a card, `+4111 1111 1111 1111` → `+[CARD]` counted as a card (separators are not an unbroken run), `4111111111111111` → `[CARD]` unchanged from today
- [ ] T007 [P] [US1] Amend `tests/unit/test_patterns.py` with a fourth section "Phone → [PHONE] (FR-001…FR-003a)" parametrized over the five rows of the boundary table in contracts/redaction-rules.md, matching the file's existing one-section-per-type structure
- [ ] T008 [P] [US1] Amend `tests/unit/test_precedence.py` with the FR-004/FR-005 four-type cases: `+4111111111119` → `[PHONE]` (position, not alternation order, decides it — the `+` sits one character before the card candidate); `+15551234567@example.com` → `[EMAIL]` counted as an email (both start at the `+`, email is written first); `jane+15551234567@example.com` → `[EMAIL]` (wins on position); `a@b.io 1.2.3.4 4111111111111111 +14155552671` → `[EMAIL] [IP] [CARD] [PHONE]`; and `[PHONE] [EMAIL] [IP] [CARD]` passing through with all four counters at zero
- [ ] T009 [P] [US1] Amend `tests/unit/test_counting.py` to add `"phones": 0` to the 7 whole-dict assertions (lines 30, 35, 44, 48, 49, 53, 67, 80, 84, 93 — the `== {"emails": …}` comparisons and both `new_counts()` assertions), and extend the placeholder-count invariant loop so `text.count("[PHONE]") == c["phones"]` is asserted alongside the existing three (SC-003)
- [ ] T010 [P] [US1] Amend `tests/cli/test_count_flag.py` for the four-key summary (FR-007): change the `SUMMARY` regex on line 7 to `rb"^emails=\d+ ips=\d+ cards=\d+ phones=\d+\n$"` and append ` phones=N` to the exact-match assertions on lines 18, 24, 30, 36, 57, 65, 92 and 150; add the contract's worked examples 2, 5, 6 and 8 as end-to-end cases — `a@b.io +442071838750` → stdout `[EMAIL] [PHONE]` / stderr `emails=1 ips=0 cards=0 phones=1`; `pay +4111111111111111 now` → stdout unchanged / stderr `emails=0 ips=0 cards=0 phones=0`; `+4111111111119` → stdout `[PHONE]` / stderr `emails=0 ips=0 cards=0 phones=1`; `+15551234567@example.com` → stdout `[EMAIL]` / stderr `emails=1 ips=0 cards=0 phones=0`. Leave the `assert b"emails=" not in proc.stderr` suppression assertions untouched (R-009)
- [ ] T011 [P] [US1] Amend `tests/cli/test_invocation.py` line 157 to assert the four-key summary `b"emails=1 ips=1 cards=0 phones=0\n"`
- [ ] T012 [P] [US1] Amend `tests/cli/test_output_fidelity.py` line 80 to assert the four-key summary `b"emails=0 ips=0 cards=0 phones=0\n"`

### Implementation for User Story 1

- [ ] T013 [US1] In `src/logredact/redact.py` add `PHONE_PLACEHOLDER = "[PHONE]"` and `_PHONE = r"\+\d{8,15}(?!\d)"`, and append `|(?P<phone>{_PHONE})` as the **fourth and last** alternative of `PATTERN` so the written order is `email | ip | card | phone`. Comment that `(?!\d)` is what makes a 16-or-more-digit run produce no match at all rather than a `[PHONE]` glued to leftover digits (FR-003), and that there is deliberately **no** `(?<!\d)` lookbehind on the `+` so `5+14155552671` is still examined (research.md R-001)
- [ ] T014 [US1] In `src/logredact/redact.py` add `"phones": 0` to the dict returned by `new_counts()`, in **final position** so the three existing keys keep their order and meanings: `{"emails": 0, "ips": 0, "cards": 0, "phones": 0}` (FR-007, data-model.md)
- [ ] T015 [US1] In `_replacement()` in `src/logredact/redact.py` add the `phone` branch — `if kind == "phone": counts["phones"] += 1; return PHONE_PLACEHOLDER` — with no validation, because the pattern is the whole rule (FR-001, contracts/redaction-rules.md)
- [ ] T016 [US1] In `_replacement()` in `src/logredact/redact.py` add a `_is_plus_prefixed_digit_run(match)` guard **in front of** the existing 13–19 digit length test and Luhn check in the card branch, returning `text` unchanged and incrementing nothing. The test is "the candidate contains no separator (no space and no `-`) **and** `match.start() > 0` and `match.string[match.start() - 1] == '+'`". Comment that the pattern-level alternative `(?<!\+)` on `_CARD` was proven wrong because it breaks `+4111 1111 1111 1111`, which must stay `+[CARD]` (FR-003a, research.md R-002)
- [ ] T017 [US1] In `src/logredact/cli.py` add `"phones": 0` to the run-local `totals` dict in `main()` and extend the `_accumulate()` helper from T003 to carry the fourth key (FR-008)
- [ ] T018 [US1] In `_write_summary()` in `src/logredact/cli.py` change the format string to `"emails={emails} ips={ips} cards={cards} phones={phones}\n"` — one line, four keys in this exact order, single-space separated, still to stderr after `sys.stdout.flush()` (FR-007, FR-022 ordering)
- [ ] T019 [US1] Run `pytest` and confirm the full suite is green: the new `tests/unit/test_phones.py` plus every amended file, and every unamended 001 test still passing (SC-003, SC-004)
- [ ] T020 [US1] Walk [quickstart.md](./quickstart.md) sections 1, 2 and 3 by hand and confirm each printed result matches, including that the five near-miss lines come back byte-identical with `emails=0 ips=0 cards=0 phones=0` (SC-001, SC-002)

**Checkpoint**: User Story 1 is complete and independently shippable. Phone numbers are redacted,
the summary has four keys, and the only two previously-redacted shapes that changed are the two
FR-003a rows the spec names.

---

## Phase 4: User Story 2 - Sanitize a set of log files into an output folder (Priority: P2)

**Goal**: `--out-dir DIR` writes each FILE's redacted lines to a file of the same name inside DIR
instead of to stdout, creating DIR with any missing parents, replacing an existing same-named
file, and printing `wrote N files` on success.

**Independent Test**: With readable `app.log` (`user jane@example.com`) and `web.log`
(`GET / from 10.0.0.7`), run `python -m logredact --out-dir clean app.log web.log` and confirm
`clean/app.log` holds `user [EMAIL]`, `clean/web.log` holds `GET / from [IP]`, stdout is exactly
`wrote 2 files\n` with no redacted line in it, and the exit status is 0.

### Tests for User Story 2 ⚠️

> **Write these FIRST and confirm they FAIL before implementing T022–T027.**

- [ ] T021 [P] [US2] Create `tests/cli/test_out_dir.py` covering FR-009…FR-015, FR-021 and FR-022 through the existing `run_cli` fixture and `tmp_path` (a real subprocess, because the stream split and the folder contents can only be observed from outside). One test per Story 2 acceptance scenario: (1) two inputs → `clean/app.log` == `user [EMAIL]`, `clean/web.log` == `GET / from [IP]`, stdout exactly `b"wrote 2 files\n"`, status 0; (2) **no** redacted line on stdout — stdout is byte-for-byte only the `wrote N files` line; (3) a three-level missing destination `a/b/c` and all its parents are created; (4) a pre-existing `clean/app.log` holding `stale contents that must disappear` is replaced and retains nothing of it (FR-012); (5) `logs/2026/app.log` → `clean/app.log`, and `clean/logs` does not exist (FR-010); (6) an empty input produces an empty output file that still counts; (7) one input → stdout exactly `b"wrote 1 files\n"`, never pluralized; (8) with `--count`, stdout is `wrote 2 files` and stderr carries the one combined four-key summary covering both files, written after the stdout line (FR-022); (9) byte fidelity (FR-013) — an input containing `a\r\nb@c.io \xff\xfe\n+14155552671 no-trailing-newline` produces an output file byte-identical to the stdout of the same run without `--out-dir`. Plus: FR-009 option position — `--out-dir clean a.log`, `a.log --out-dir clean b.log`, `a.log b.log --count --out-dir clean` and `--out-dir=clean a.log` all accepted; and FR-021 — without `--out-dir` redacted lines still go to stdout and no `wrote N files` line is ever printed

### Implementation for User Story 2

- [ ] T022 [US2] In `build_parser()` in `src/logredact/cli.py` add `parser.add_argument("--out-dir", dest="out_dir", default=None, metavar="DIR")` and give the positional `metavar="FILE"`, keeping `parse_intermixed_args` in `main()` so the option works in any position relative to `--count` and the FILE arguments (FR-009, research.md R-004). Do **not** use `type=pathlib.Path`: the raw string is kept so a diagnostic names the path exactly as typed
- [ ] T023 [US2] Add `_out_path(out_dir, name)` to `src/logredact/cli.py` returning `os.path.join(out_dir, os.path.basename(name))` — the FILE's own name with its directories discarded, never reproduced inside DIR (FR-010). No new import: `os` is already imported
- [ ] T024 [US2] Add a `_preflight(parser, args)` function to `src/logredact/cli.py` that runs `os.makedirs(args.out_dir, exist_ok=True)` **before the first FILE is opened**, and call it from `main()` immediately after `parse_intermixed_args` when `args.out_dir` is set. The single call satisfies both "created with any missing parent directories" and "an existing DIR is used as it is" (FR-011, FR-015). Error handling is added in T034
- [ ] T025 [US2] Add `_write_file(name, out_path, totals)` to `src/logredact/cli.py` implementing the per-FILE lifecycle: open the **input first** with the existing `_open_source(name)`, then the **output second** with `open(out_path, "w", encoding="utf-8", errors="surrogateescape", newline="")` — character for character the settings `_configure_streams` pins on `sys.stdout`, which makes FR-013's byte-for-byte guarantee true by construction, and `"w"` mode which supplies FR-012. Comment that the input-before-output order is itself half of FR-017a: a FILE that cannot be opened leaves no file of its name in DIR (research.md R-006, R-007). Drive the loop through `_redact_into(stream, out, totals)` from T004
- [ ] T026 [US2] Wire the destination choice in `main()` in `src/logredact/cli.py`: when `args.out_dir` is set, loop over `args.files` calling `_write_file(name, _out_path(args.out_dir, name), totals)` and write nothing to stdout from the loop; otherwise keep the exact code path that ships today, with `out` bound to `sys.stdout` (FR-010, FR-021, FR-023). Exactly one output file is open at a time and nothing is accumulated, so memory stays flat (SC-007)
- [ ] T027 [US2] In `main()` in `src/logredact/cli.py`, after every FILE has been processed successfully in an `--out-dir` run, write the single line `sys.stdout.write(f"wrote {len(args.files)} files\n")` to stdout — `N` counts FILE **arguments**, so a repeated FILE and two FILEs sharing a name each count again — and leave the existing `if args.count: _write_summary(totals)` call after it so the summary follows on stderr (FR-014, FR-022). The wording never pluralizes: one file reports `wrote 1 files`
- [ ] T028 [US2] Run `pytest` and confirm `tests/cli/test_out_dir.py` is fully green and the whole prior suite — including every US1 test — still passes
- [ ] T029 [US2] Walk [quickstart.md](./quickstart.md) sections 4 and 5 by hand, including the `cmp clean/odd.log expected.out` byte-identity check and the `ls a/b/c` check that the input's directories were not reproduced (SC-005)

**Checkpoint**: User Stories 1 AND 2 both work. A readable set of inputs and a writable
destination now produce one complete output file per FILE argument plus `wrote N files`.

---

## Phase 5: User Story 3 - Fail clearly when the output folder cannot be used (Priority: P3)

**Goal**: Every `--out-dir` failure mode names the offending path on stderr, suppresses both
`wrote N files` and the `--count` summary, prints no stack trace, exits 2, and leaves the
destination holding **only complete output files**.

**Independent Test**: Run the tool with `--out-dir` naming a path that is an existing regular
file and confirm stderr names that path, no input file was read, stdout is empty, and the exit
status is 2.

**Depends on**: Phase 4 — these are the failure paths of the code US2 introduces. The two story
phases are verified independently (separate test files), but US3's implementation amends US2's
functions.

### Tests for User Story 3 ⚠️

> **Write these FIRST and confirm they FAIL before implementing T031–T038.**

- [ ] T030 [P] [US3] Create `tests/cli/test_out_dir_failures.py` covering FR-016…FR-020 and FR-017a through `run_cli` and `tmp_path`. One test per Story 3 acceptance scenario, each asserting status 2, a stderr diagnostic naming the offending path, **no** `b"wrote "` on stdout, **no** `b"emails="` on stderr even with `--count`, and no `b"Traceback"` on stderr: (1) `--out-dir` pointing at an existing regular file → names that path and **no input is read** (assert via an input whose redaction would be observable); (2) an output path that is an existing directory (`mkdir -p clean2/app.log`) → the diagnostic names `clean2/app.log`, the **output** path (FR-017); (3) `--out-dir` with no FILE → stderr carries `usage:` and `--out-dir requires at least one FILE`, stdin is **not** read (pass a non-empty stdin and assert stdout is empty), status 2 (FR-019); (4) two inputs, the second missing → `clean/app.log` exists and is complete, `os.listdir(clean)` contains **no** entry named after the missing input, stderr names the missing input (FR-018, FR-017a); (5) a write cut short partway → the destination holds no truncated file for that input while an earlier input's output file is still present and complete (FR-017a); (6) `--out-dir .` in the folder holding `app.log` → stderr names `app.log`, and `app.log`'s bytes are unchanged (FR-020); (7) `--out-dir out a.log out/b.log` → stderr names `out/b.log`, `out/b.log` is unmodified, and `os.listdir("out")` does **not** contain `a.log` — the run failed before reading anything (FR-020 pre-flight); (8) the success control — all inputs readable and the destination writable → stderr is empty without `--count` and the status is 0. Add an exit-status assertion that every failing case returns exactly 2 and never another value (SC-006)

### Implementation for User Story 3

- [ ] T031 [US3] In `_preflight()` in `src/logredact/cli.py` make the **first** check `if args.out_dir and not args.files: parser.error("--out-dir requires at least one FILE")`, so a usage error never has a filesystem side effect. Routing it through `parser.error` reuses argparse's existing behaviour — usage line, `python -m logredact: error: …` on stderr, nothing on stdout, `SystemExit(2)` — introducing no new exit path and no new message shape (FR-019, research.md R-005)
- [ ] T032 [US3] Add `_collides(name, out_path)` to `src/logredact/cli.py` returning `os.path.samefile(name, out_path)` inside `try`, with `except OSError: return False` and a comment stating the reason: one of the two paths does not exist, so they cannot be the same file on disk, and a **missing FILE must not be reported as a collision** — it fails later in its own turn with the FR-018 diagnostic, which is what keeps earlier FILEs' output (research.md R-005). `samefile` compares device and inode, so it catches `--out-dir .`, a symlink and a hard link alike. This narrow handler recovers meaningfully and is **not** a Principle II deviation
- [ ] T033 [US3] In `_preflight()` in `src/logredact/cli.py` add the FR-020 check as the **second** step: loop over **every** FILE in `args.files` and, if `_collides(name, _out_path(args.out_dir, name))`, write a diagnostic naming that FILE via the existing `_report` and return `EXIT_FAILURE`. It runs **before** `os.makedirs` so a doomed command line leaves the filesystem untouched, and before any FILE is read so a collision at any position fails the run with nothing read and no output file written (FR-020, research.md R-005)
- [ ] T034 [US3] In `_preflight()` in `src/logredact/cli.py` wrap the T024 `os.makedirs(args.out_dir, exist_ok=True)` in `except OSError as error:` → `_report(args.out_dir, error)` and return `EXIT_FAILURE`, naming DIR **exactly as written on the command line**. The one narrow base class covers an existing regular file at that path (`FileExistsError`, `strerror` "File exists"), permission denied on a parent, and every other reason the directory cannot exist. No FILE is read and no output file is written (FR-016). Have `main()` return `_preflight`'s status when it is non-zero, before the input loop
- [ ] T035 [US3] Add `_discard(path)` to `src/logredact/cli.py`: `os.remove(path)` inside `try` with `except OSError: pass` and the comment required by plan.md "Complexity Tracking" — the run is already failing and its real diagnostic is already composed, so letting the removal's own error propagate would replace the user's real cause ("`b.log`: No such file or directory") with a misleading one about a deletion they never asked for. The handler is narrow (`OSError` only) and cannot mask a **successful** run (FR-017a, research.md R-007)
- [ ] T036 [US3] Rework `_redact_into(stream, out, totals, name, out_path)` in `src/logredact/cli.py` to return `None` on success or `(path, error)` naming what the diagnostic must report, using **nested** handlers exactly as research.md R-008 specifies: the inner `try` around `out.write(text)` re-raises `BrokenPipeError` and returns `(out_path, error)` on `OSError` (FR-017); the outer `try` around the `for line in stream` loop re-raises `BrokenPipeError` and returns `(name, error)` on `OSError` (FR-018). Comment that `error.filename` is not a usable discriminator — `open()` sets it, a failed `write()` does not — so attribution must be structural, and that a `(path, error)` return avoids introducing an exception class for a value that travels one frame (Principle IV). On the stdout path `BrokenPipeError` must still reach the existing FR-028 handler in `main()`, which exits 0 in silence
- [ ] T037 [US3] Complete `_write_file()` in `src/logredact/cli.py` for FR-017a: open the output with a plain `open(...)` rather than a `with` block and call `out.close()` **inside** the failure scope, because on a full filesystem the error surfaces when the buffer is flushed at `close()`, not at `write()` (research.md R-007). On any failure after the output file was created — a `(path, error)` return from `_redact_into`, a failing `close()`, or a failing output `open()` — call `_discard(out_path)` **before** the diagnostic is reported, so no truncated redaction is left to be mistaken for a finished one. Output files completed for earlier FILEs are left in place; a later FILE writing to the same destination path follows the later write's outcome, which falls out of `"w"` mode plus removal-on-failure with no extra rule
- [ ] T038 [US3] In `main()` in `src/logredact/cli.py` route every `--out-dir` failure to `_report(path, error)` followed by `return EXIT_FAILURE`, placed so that processing stops at the failing FILE and **both** the `wrote N files` line (T027) and the `if args.count: _write_summary(totals)` call are never reached — a partial run is never presented as a complete one (FR-016, FR-017, FR-018). Confirm no code path can return a status other than `EXIT_OK` or `EXIT_FAILURE` (FR-023, SC-006)
- [ ] T039 [US3] Run `pytest` and confirm `tests/cli/test_out_dir_failures.py` is fully green and the whole prior suite — Setup baseline, US1 and US2 — still passes
- [ ] T040 [US3] Walk [quickstart.md](./quickstart.md) section 6 by hand, including `ls clean3` (only `app.log`, no `missing.log`), `cat app.log` unmodified after `--out-dir .`, and `ls out` (only `b.log`, no `out/app.log`) (SC-006)

**Checkpoint**: All three user stories are independently functional. Every failure path names its
path, exits 2, and leaves the destination holding only complete output files.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Prove FR-023 (nothing else moved), SC-007 (performance) and SC-008 (full coverage).

- [ ] T041 [P] Walk [quickstart.md](./quickstart.md) section 7 and confirm the 001 examples behave identically — `user jane@example.com from 10.0.0.7` → `user [EMAIL] from [IP]`, `999.1.1.1` unchanged, `paid with 4111 1111 1111 1111, ref 1234567890123` → `paid with [CARD], ref 1234567890123`, and `--redact-all` → usage naming it with status 2 (FR-023, SC-004)
- [ ] T042 [P] Walk [quickstart.md](./quickstart.md) section 8: build a ~1,000,000-line log and time `python3 -m logredact --out-dir perf line.txt`, confirming it finishes well under 60 s and that memory does not grow with input size, with `--out-dir` as well as without (SC-007)
- [ ] T043 [P] Confirm the early-closing-consumer path still exits 0 in silence on the `wrote N files` line: run `python3 -m logredact --out-dir … big.log | head -5`-style cases against `tests/cli/test_broken_pipe.py` unchanged, and verify that the two `except BrokenPipeError: raise` guards in `src/logredact/cli.py` are the only places `BrokenPipeError` is re-raised (FR-023, `001:FR-028`)
- [ ] T044 [P] Audit `src/logredact/redact.py` and `src/logredact/cli.py` for Constitution Principle I: confirm **zero** new imports were added — `re`, `argparse`, `os` and `sys` only, with `os` supplying `makedirs`, `path.basename`, `path.join`, `path.samefile` and `remove` — and that nothing under `src/` imports `pytest`
- [ ] T045 Audit Constitution Principle II across `src/logredact/cli.py`: confirm the only two swallowing handlers are `_discard`'s `except OSError: pass` (T035, recorded in plan.md "Complexity Tracking") and `_collides`'s `except OSError: return False` (T032, a meaningful recovery), each carrying the comment that states its reason, and that every one of the five failure modes writes a diagnostic naming the offending path and returns status 2
- [ ] T046 Write the SC-008 coverage map: for each of the 25 functional requirements (FR-001…FR-023 plus FR-003a and FR-017a) and each spec edge case, name at least one covering test in `tests/unit/test_phones.py`, `tests/unit/test_patterns.py`, `tests/unit/test_precedence.py`, `tests/unit/test_counting.py`, `tests/cli/test_out_dir.py` or `tests/cli/test_out_dir_failures.py`, and add a test for any gap found
- [ ] T047 Run a final bare `pytest` from the repository root and confirm the complete suite passes, with the only edits to the 1,405 pre-existing test lines being the count-shape assertions FR-007 forces (SC-004, Constitution quality gate)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories**
- **User Story 1 (Phase 3)**: depends on Phase 2 only — no dependency on US2 or US3
- **User Story 2 (Phase 4)**: depends on Phase 2. Independent of US1 in code (US1 is `redact.py` plus two lines of `cli.py`; US2 is the `cli.py` write path), but delivered after it because US1 is the MVP
- **User Story 3 (Phase 5)**: depends on Phase 4 — it implements the failure paths of the functions US2 introduces (`_preflight`, `_write_file`, `_redact_into`). Verified independently in its own test file
- **Polish (Phase 6)**: depends on all three stories

### User Story Dependencies

- **US1 (P1)**: independent. Ships alone as the MVP
- **US2 (P2)**: independent of US1. Needs Phase 2's parameterised output stream
- **US3 (P3)**: **requires US2.** The spec states this directly — it "only matters once Story 2 exists"

### Within Each User Story

- Tests are written first and MUST fail before the implementation tasks of that phase
- `redact.py` before `cli.py` (pure core before the process-facing half)
- `_out_path`/`_collides`/`_discard` helpers before the functions that call them
- Pre-flight before the input loop — in code and in task order (T031 → T033 → T034)
- Each story ends with a full-suite run and a quickstart walk before the next begins

### Sequential Chains (no `[P]`)

- **T013 → T014 → T015 → T016** all edit `src/logredact/redact.py`
- **T017 → T018**, **T022 → T023 → T024 → T025 → T026 → T027**, **T031 → T032 → T033 → T034 → T035 → T036 → T037 → T038** all edit `src/logredact/cli.py`
- **T003 → T004** edit `src/logredact/cli.py`; T017 and T022 both build on them

### Parallel Opportunities

- T001 and T002 (Setup) are independent
- **T006–T012 run fully in parallel** — seven different test files, no shared state
- T021 and T030 are different files, but T030 follows T021's implementation phase
- T041–T044 (Polish audits) run in parallel; T045–T047 follow them
- With multiple developers, US1 (`redact.py` + summary) and US2 (`cli.py` write path) can proceed in parallel after Phase 2, with US3 picked up by whoever finishes US2

---

## Parallel Example: User Story 1 tests

```bash
# All seven US1 test tasks touch seven different files — launch together:
Task: "T006 Create tests/unit/test_phones.py (FR-001…FR-006, FR-003a)"
Task: "T007 Amend tests/unit/test_patterns.py — phone boundary table"
Task: "T008 Amend tests/unit/test_precedence.py — four-type overlap and tie cases"
Task: "T009 Amend tests/unit/test_counting.py — 'phones': 0 and the fourth invariant"
Task: "T010 Amend tests/cli/test_count_flag.py — four-key summary + worked examples"
Task: "T011 Amend tests/cli/test_invocation.py line 157 — four-key summary"
Task: "T012 Amend tests/cli/test_output_fidelity.py line 80 — four-key summary"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup — capture the green baseline (T001–T002)
2. Phase 2: Foundational — two behaviour-preserving refactors (T003–T005) ⚠️ blocking
3. Phase 3: User Story 1 — the phone rule and the fourth summary key (T006–T020)
4. **STOP and VALIDATE**: quickstart §1–§3, full suite green
5. Ship. Every existing invocation now redacts phone numbers; no new option was needed

### Incremental Delivery

1. Setup + Foundational → one accumulation point, a parameterised output stream, same behaviour
2. **+ US1** → phone redaction and `emails=N ips=N cards=N phones=N` → ship (MVP)
3. **+ US2** → `--out-dir` writes one complete file per input and prints `wrote N files` → ship
4. **+ US3** → every failure path named, status 2, destination holds only complete files → ship
5. **+ Polish** → FR-023, SC-007 and SC-008 proven

### Parallel Team Strategy

1. Everyone on Setup + Foundational (T001–T005) — it is small and blocks everything
2. Then split:
   - Developer A: US1 — `redact.py`, `new_counts`, `_write_summary`
   - Developer B: US2 — `--out-dir` option, `_preflight`, `_write_file`, `wrote N files`
   - Developer B continues into US3, which amends the same functions
3. The two halves meet only at `_accumulate` and the `totals` dict; coordinate that one line

---

## Notes

- `[P]` tasks touch different files and have no dependency on an incomplete task
- Every task names the exact file it edits; `redact.py` tasks are pure text-in/text-out and need
  no I/O, `cli.py` tasks are verified through a real subprocess
- Verify each phase's tests fail before implementing it (Constitution Principle III)
- Commit after each task or logical group; stop at any checkpoint to validate a story alone
- The destination folder is never cleaned: files already in DIR that a run does not write are
  left untouched
- Two behaviours of the shipped tool change, and only two: `+4111111111119` becomes `[PHONE]`
  (was `+[CARD]`) and `+4111111111111111` is left unchanged (was `+[CARD]`). Anything else that
  moves is a regression (FR-023)
