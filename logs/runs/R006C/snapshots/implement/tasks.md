---

description: "Task list for Phone Redaction and Output Folder"
---

# Tasks: Phone Redaction and Output Folder

**Input**: Design documents from `/specs/002-phone-redaction-out-dir/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md),
[contracts/redaction-rules.md](./contracts/redaction-rules.md), [quickstart.md](./quickstart.md)

**Tests**: **REQUIRED, not optional.** Constitution Principle III and Principle V make every
functional and security requirement untested-means-unimplemented, SC-016 requires 100% of FR and SR
items mapped to a passing test at the implementation gate, and the plan's
[requirement-to-test mapping](./plan.md#requirement-to-test-mapping) names the exact test functions
the tasks below must create.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested and
delivered on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel — different file, no dependency on an incomplete task
- **[Story]**: `[US1]`…`[US4]`, mapping to the user stories in [spec.md](./spec.md)
- Every task names the exact file it changes

## Path Conventions

Single project, layout unchanged from 001 and **no new source file** (plan.md Structure Decision):

- Source: `src/logredact/redact.py`, `src/logredact/cli.py`
- Tests: `tests/` at the repository root, run with `python3 -m pytest` (`pythonpath = ["src"]` is
  already set in `pyproject.toml`)
- Two **new** test modules: `tests/test_cli_outdir.py`, `tests/test_cli_outdir_errors.py`

## Constants fixed by the design — use these literals verbatim

Taken from [data-model.md](./data-model.md) and [contracts/cli.md](./contracts/cli.md). Nothing
here is configurable (A-23, SR-016), so no task may introduce an option, environment variable or
constant that lets any of it vary:

| Thing | Exact value |
|---|---|
| Phone pattern | `\+[0-9]{8,15}(?![0-9])` — `[0-9]` not `\d`; bounds 8 and 15 inline |
| Phone placeholder | `[PHONE]` |
| Alternation order | `email`, `ip`, `phone`, `card` — in that written order |
| Tally format | `emails=%d ips=%d cards=%d phones=%d\n` — `phones` **appended** (A-15) |
| Write-tally format | `wrote %d files\n` — never pluralised |
| Directory creation | `os.mkdir(path, 0o700)` per missing component — **never** `os.makedirs(..., mode=…)` |
| Output open | `os.open(path, os.O_WRONLY \| os.O_CREAT \| os.O_TRUNC \| os.O_NOFOLLOW, 0o600)` |
| Output wrapper | `open(fd, "w", **STREAM_SETTINGS)` — the same settings as stdin/stdout |
| Output path | `os.path.join(DIR, os.path.basename(operand))` — one component, no resolve, no normalise |
| Identity guard | `os.path.samestat(os.fstat(input_fd), os.stat(out_path))`, **before** the output open |
| Diagnostic: DIR | `cannot create output directory 'DIR': REASON` |
| Diagnostic: no operand | `--out-dir requires at least one FILE operand` |
| Diagnostic: repeated | `--out-dir may be given at most once` |
| Diagnostic: self-write | `refusing to write 'OUTPATH': it is the input file 'FILE'` |
| Diagnostic: write fail | `cannot write 'OUTPATH': REASON` |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the baseline this amendment extends is green before changing it, so any later
failure is attributable to this feature and SC-012 is measurable.

- [X] T001 Record the pre-change baseline: run `python3 -VV` (must report 3.11 or newer per A-10) and `python3 -m pytest -q -rs` from the repository root, and write the resulting pass/skip counts into the implementation notes. No file is modified by this task; it exists so SC-012 ("the whole existing suite passes, changing only the expected `--count` text") has a before-value to compare against, and so the pre-existing root skip in `tests/test_cli_errors.py:176` is visible from the start.
- [X] T002 [P] Create `tests/test_cli_outdir.py` and `tests/test_cli_outdir_errors.py` with only a module docstring naming the story and requirements each covers (per plan.md Project Structure), `import os`, `import stat`, `from pathlib import Path`, `import pytest`, and `from conftest import ERROR_PREFIX` where needed — the `run_cli` fixture comes from `tests/conftest.py` automatically and must not be redefined. No test functions and no placeholders in this task — the later phases add them — so the suite still collects and passes cleanly after it.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one piece of run-level state both halves of the feature touch — the fourth tally
key — plus the test helpers that construct it. Without this, US1's replacer has no key to increment.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Add `"phones": 0` to the run tally dict created in `_run` in `src/logredact/cli.py` (currently `tally = {"emails": 0, "ips": 0, "cards": 0}`), keeping it one mutable `dict[str, int]` threaded into `redact_line` — four non-negative integers, accumulated across every source in the run, never per file (data-model.md Run tally, FR-022, A-24). Do **not** change `_write_tally`'s format string in this task: the reported line stays three-field until T028, so the existing suite stays green through Phase 3.
- [X] T004 [P] Extend the unit-test tally helpers to four keys: in `tests/test_redaction_rules.py` change `new_tally()` to return `{"emails": 0, "ips": 0, "cards": 0, "phones": 0}` and add `"phones": 0` to each explicit dict-equality assertion (the `tally == {...}` comparisons around lines 174, 182, 202 and the `total == {...}` comparison around line 375); in `tests/test_resource_bounds.py` add `"phones": 0` to the literal tally dict around line 40. These are mechanical four-key updates, not behaviour changes.

**Checkpoint**: `python3 -m pytest -q` still passes exactly as at T001 — the tally has a fourth key
that nothing increments and nothing reports yet.

---

## Phase 3: User Story 1 - Redact phone numbers from a log (Priority: P1) 🎯 MVP

**Goal**: An international-format phone number — a literal `+` immediately followed by 8 to 15
decimal digits — is replaced by `[PHONE]`, with the `+` consumed, alongside the three categories the
tool already removes. No new option and no file handling.

**Independent Test**: `printf 'call +14155552671 now\n' | python3 -m logredact` writes exactly
`call [PHONE] now\n` to stdout and exits 0 (C-27, the first of SC-011's three worked examples). The
protective value lands with no flag involved.

### Implementation for User Story 1

- [X] T005 [US1] Add `PHONE_PLACEHOLDER = "[PHONE]"` to the module-level placeholder constants in `src/logredact/redact.py`, beside the existing `EMAIL_PLACEHOLDER`, `IP_PLACEHOLDER` and `CARD_PLACEHOLDER`. A fixed literal, not configurable (A-23).
- [X] T006 [US1] Add `_PHONE = r"\+[0-9]{8,15}(?![0-9])"` to the pattern section of `src/logredact/redact.py` with a comment recording, per element, why it is written that way (contracts/redaction-rules.md): `\+` because FR-019 makes the `+` part of the match; `[0-9]` not `\d` because FR-019 says *decimal* digits and A-4 limits the rules to ASCII; `{8,15}` because FR-019's bounds are inclusive; `(?![0-9])` because FR-020 forbids a candidate followed by a digit, so a 16-or-more-digit run contains no phone number and no leading part of it may be replaced; and no lookbehind because A-14 deliberately constrains nothing before the `+`. Note the cost argument too: at most 8 attempts per start position over one character class, so the rule is linear in line length (SR-015).
- [X] T007 [US1] Insert the new alternative into the single compiled `PATTERN` in `src/logredact/redact.py` **between `ip` and `card`**, giving `"(?P<email>" + _EMAIL + ")|(?P<ip>" + _IPV4 + ")|" "(?P<phone>" + _PHONE + ")|(?P<card>" + _CARD_RUN + ")"`, so the written source order *is* FR-021's precedence order (email, IPv4, phone, card). Update the docstring above `PATTERN` from "three named alternatives" to four, and update the module docstring's "three fixed categories" accordingly.
- [X] T008 [US1] Add the phone branch to `_replace` in `src/logredact/redact.py`: when `match.lastgroup == "phone"`, increment `tally["phones"] += 1` and return `PHONE_PLACEHOLDER`, placed after the `ip` branch and before the card fall-through so the branch order mirrors the alternation order. One replacement is one counted increment (A-1).

### Tests for User Story 1

- [X] T009 [US1] Add `test_phone_shapes` and `test_phone_digit_bounds` to `tests/test_redaction_rules.py` (C-27, C-28, C-29): `call +14155552671 now` → `call [PHONE] now`; `+442071838750` → `[PHONE]`; `+12345678` (8 digits, lower bound) → `[PHONE]`; `+123456789012345` (15 digits, upper bound) → `[PHONE]`. Assert the exact output string and that `tally["phones"]` equals the number of replacements.
- [X] T010 [US1] Add `test_sixteen_digit_run_has_no_phone` and `test_no_phone_fragment_replaced` to `tests/test_redaction_rules.py` (C-30, C-31, C-32, C-38, FR-020, SR-006, A-14): `+1234567` (7 digits) unchanged; `+1234567890123456` (16 digits) contains no `[PHONE]` and loses no digit to the phone rule; `14155552671` (no `+`) unchanged; each of `+abc`, `+`, `+ 14155552671`, `+1 415 555 2671`, `+1-415-555-2671` unchanged by the phone rule. Assert `tally["phones"] == 0` for every one of these.
- [X] T011 [US1] Add the boundary and prefix cases to `tests/test_redaction_rules.py` (C-33, C-34, C-36, C-37, C-39): `user jane@example.com from 10.0.0.7` → `user [EMAIL] from [IP]` and `paid with 4111 1111 1111 1111, ref 1234567890123` → `paid with [CARD], ref 1234567890123`, proving the existing categories are untouched; `++14155552671` → `+[PHONE]` (the match starts at the second `+`); `99+14155552671` → `99[PHONE]` (A-14); and a phone number at the very start and at the very end of a line, with and without a terminator, redacted identically to one in the middle.
- [X] T012 [US1] Add the precedence tests to `tests/test_redaction_rules.py` (FR-021): `test_email_beats_phone` — `+14155552671@example.com` → `[EMAIL]` with `tally == {"emails": 1, "ips": 0, "cards": 0, "phones": 0}` (C-35, decided by the written alternation order); `test_phone_beats_card` — `+4111111111111` (13 Luhn-valid digits) → `[PHONE]`, **not** `+[CARD]` (C-40, A-13, decided by the leftmost rule); `test_phone_placeholder_not_rescanned` — no placeholder text is re-examined; `test_phone_card_overlap_is_pinned` — `+41111111 11119` → `[PHONE] 11119`, the one recorded narrowing of redaction, pinned so a future change to it is visible (C-41, research.md R17). Also assert `+4111111111111111` (16 digits) is still `+[CARD]`, unchanged by this amendment.
- [X] T013 [US1] Add `test_phone_corpus_fully_redacted` (SC-013) and `test_phone_near_miss_corpus_untouched` (SC-014) to `tests/test_redaction_rules.py`: a corpus of genuine international numbers covering 8 to 15 digits at the start, middle and end of a line and beside an email — assert 100% become `[PHONE]` and that no four-digit fragment of any of them appears anywhere in the output; and a near-miss corpus (`+` with 7, 16 and 20 digits, a bare digit run with no `+`, `+` then a space, `+` then a letter, separator-grouped digits, a bare `+`, `++`) — assert 0 phone redactions and that no digit is removed by the phone rule.
- [X] T014 [P] [US1] Add `test_worked_examples_002` to `tests/test_cli_stream.py` (C-27, SC-011): run the real `python3 -m logredact` through the `run_cli` fixture with `call +14155552671 now\n` on stdin and assert `(status, stdout, stderr) == (0, b"call [PHONE] now\n", b"")` — raw bytes, so the byte-for-byte guarantee is actually asserted.
- [X] T015 [P] [US1] Add `test_phone_adversarial_lines_are_linear` to `tests/test_resource_bounds.py` (SR-015), parametrised over the five adversarial shapes from research.md R15 (`"+" + "9"*n`, `"+9"*(n//2)`, `"+9999999999999999"*(n//17)`, a 16-digit run, and a long run of lone `+` characters) at doubling sizes up to 1 MiB: assert each shape stays under the existing 10 s tripwire and that doubling the length roughly doubles the time rather than exploding. Mark `@pytest.mark.slow` consistently with the existing resource tests.

**Checkpoint**: User Story 1 is complete and independently deliverable. `python3 -m pytest -q`
passes in full, including every 001 test unchanged — the `--count` line is still three-field, so
nothing in `tests/test_cli_count.py` needs touching yet.

---

## Phase 4: User Story 2 - Redact a set of log files into an output folder (Priority: P2)

**Goal**: `--out-dir DIR` writes each FILE operand's redacted lines to `DIR/<final path component of
that operand>` instead of standard output, creating DIR and every missing parent owner-accessible
only, and standard output carries exactly one line, `wrote N files`.

**Independent Test**: Create `app.log` and `web.log` with known content, run
`python3 -m logredact --out-dir clean app.log web.log` with `clean` absent, and confirm `clean` was
created, holds exactly two files named after the inputs with the expected redacted contents, stdout
is exactly `wrote 2 files\n`, stderr is empty, and the status is 0 (C-48, the third worked example).
Testable without `--count` and without any error case.

### Implementation for User Story 2

- [X] T016 [US2] Declare the option in `_build_parser` in `src/logredact/cli.py`: `parser.add_argument("--out-dir", dest="out_dir", action="append", metavar="DIR")`, and change `usage` to `"%(prog)s [--count] [--out-dir DIR] [FILE ...]"`. `action="append"` rather than the default `store` is what makes a repeated occurrence detectable in T033 (research.md R18); `add_help=False, allow_abbrev=False` are already set and must not be altered — they are what rejects `--out_dir`, `--out`, `--out-di` and a valueless `--out-dir` before any I/O (SR-016). `--out-dir=DIR` is accepted for free (A-21).
- [X] T017 [US2] Add `_prepare_out_dir(dir_path)` to `src/logredact/cli.py`: walk the missing ancestors of `dir_path` outermost-first and create each with `os.mkdir(path, 0o700)`, innermost last; return `True` on success, or write `cannot create output directory 'DIR': REASON` through the existing `_error` helper and return `False` on `OSError`, where `DIR` is the string exactly as given on the command line and `REASON` is `_reason(exc)`. Catch `OSError` narrowly at this boundary only, never `Exception` (Principle II). Document in the docstring why `os.makedirs(dir, mode=0o700, exist_ok=True)` is **not** used: since Python 3.7 its `mode` applies only to the leaf, measured `0o755` on `a` and `a/b` for `a/b/c`, which is a direct SR-011 and SC-020 failure — and why `makedirs` + `chmod` is also rejected, because the Security Baseline requires permissions set at creation rather than relaxed and tightened (research.md R19). An existing directory is used as it is, with nothing created and nothing altered (FR-025).
- [X] T018 [US2] Add `_open_output(out_path, input_handle, operand)` to `src/logredact/cli.py`, in this order so SR-012 holds by construction: (1) guard identity — `collision = os.path.samestat(os.fstat(input_handle.fileno()), os.stat(out_path))` inside `try: … except FileNotFoundError: collision = False`, and on `collision` report `refusing to write 'OUTPATH': it is the input file 'FILE'` and return `None`; any other `OSError` from `os.stat` is reported as `cannot write 'OUTPATH': REASON` and returns `None`, never swallowed; (2) open — `fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)` then `return open(fd, "w", **STREAM_SETTINGS)`, reporting `cannot write 'OUTPATH': REASON` and returning `None` on `OSError`. Record in the docstring which requirement each flag discharges — `O_NOFOLLOW`/SR-010 (including a dangling symlink, the case an existence check would miss), `0o600`/SR-011 (and that the mode applies only on creation, so a pre-existing file keeps its own mode), `O_CREAT` without `O_EXCL` and `O_TRUNC`/FR-026 — and that the identity check must precede the open because `O_TRUNC` truncates during `os.open` (research.md R20, R21). Also record, per plan.md Principle II, that the `None` return means "already reported, skip this operand", following `_redact_stream`'s existing `False` convention rather than adding a second private exception class, because this failure does not unwind past the operand loop.
- [X] T019 [US2] Add the destination branch and the write tally to `_run` in `src/logredact/cli.py`: derive `out_dir = args.out_dir[0] if args.out_dir else None`; when `out_dir` is not `None`, call `_prepare_out_dir(out_dir)` **before** any operand is opened and `return EXIT_ERROR` if it fails, so FR-029's "no operand read, nothing on standard output" holds; initialise `written = 0` beside the existing `failed` flag; inside the operand loop, after the input `handle` is open, compute `out_path = os.path.join(out_dir, os.path.basename(operand))`, call `_open_output`, set `failed = True` and `continue` on `None`, otherwise redact into that handle with the **unchanged** `_redact_stream(handle, operand, tally, output)` call and close the output inside its own `try`/`except OSError` that reports `cannot write 'OUTPATH': REASON` and sets `failed = True`; increment `written` only when the input reached end-of-file with no read error **and** the output handle flushed and closed with no error (research.md R22's counting rule). After the loop, when `out_dir` is not `None`, write `"wrote %d files\n" % written` to `out` before the existing `out.flush()`, so the ordering is: every output file closed → `wrote N files` on stdout → stdout flushed → the tally on stderr (research.md R24). The `except _OverLengthLine` branch returns before reaching that line, which is exactly FR-033. Leave the line loop in `_redact_stream` untouched — its `out` parameter already *is* the output-destination abstraction, so peak memory stays bounded by one line and one open handle however many operands there are (FR-034, Principle IV).

### Tests for User Story 2

- [X] T020 [US2] Add the acceptance and worked-example tests to `tests/test_cli_outdir.py` (C-48, C-49, C-53, FR-023, FR-024, FR-027, SC-011): `test_out_dir_accepted`, `test_equals_form` (the `--out-dir=DIR` spelling of A-21), `test_writes_one_file_per_operand`, `test_count_line`, `test_no_redacted_line_on_stdout` (stdout is *exactly* the `wrote N files` line and nothing else), `test_count_line_not_pluralised` (one operand gives exactly `wrote 1 files\n`), and `test_worked_example_out_dir` — `app.log` holding `user jane@example.com`, `web.log` holding `GET / from 10.0.0.7`, `clean` absent, asserting `clean/app.log` and `clean/web.log` byte-for-byte, stdout exactly `b"wrote 2 files\n"`, stderr exactly `b""`, status 0.
- [X] T021 [US2] Add the naming and confinement tests to `tests/test_cli_outdir.py` (C-50, C-51, FR-024, FR-025, SR-010): `test_only_final_path_component` — operand `logs/2026/app.log` with `--out-dir clean` produces `clean/app.log` and **no** `clean/logs` or `clean/2026`; `test_creates_missing_parents` — `--out-dir a/b/c` with none of `a`, `b`, `c` existing creates all three and the output files appear in `a/b/c`; `test_absolute_operand_contributes_no_path` — an absolute operand contributes only its final component; `test_no_file_written_outside_dir` — snapshot the tree before and after and assert no path outside DIR changed in existence, size or mtime (research.md R25).
- [X] T022 [US2] Add the replacement and reuse tests to `tests/test_cli_outdir.py` (C-52, C-56, C-57, FR-025, FR-026): `test_existing_output_replaced_in_full` — a pre-existing `clean/app.log` whose unrelated content is **longer** than the new output ends up holding exactly the redaction with no remnant; `test_existing_dir_reused_and_untouched` — a `clean` already holding `unrelated.txt` keeps it unchanged and is not emptied; and an empty input file produces an empty output file of that name which **is** counted (spec Edge Cases).
- [X] T023 [US2] Add the permission tests to `tests/test_cli_outdir.py` (C-60, C-61, SR-011, SC-020): `test_created_modes_are_owner_only` — after `--out-dir a/b/c`, assert `stat.S_IMODE(os.stat(p).st_mode) & 0o077 == 0` for **DIR and each of its created parents** `a` and `a/b` as well as for every output file, the mask form being umask-independent; and `test_existing_output_keeps_its_mode` — an output file pre-created `0o644` is still `0o644` afterwards and holds the redaction, neither widened nor narrowed. The parent assertion is a required Phase 0 regression test: `makedirs` left those parents `0o755` (research.md R19), so without it the defect is invisible.
- [X] T024 [US2] Add `test_operands_unmodified` to `tests/test_cli_outdir.py` (C-54, SC-017, FR-017): after a successful `--out-dir` run over several operands, assert every operand is byte-for-byte identical and that its size and mtime are unchanged.
- [X] T025 [US2] Add `test_without_out_dir_unchanged` to `tests/test_cli_outdir.py` (C-55, FR-035): with FILE operands and **no** `--out-dir`, stdout carries every operand's redaction in operand order and no `wrote N files` line appears anywhere, on either stream.
- [X] T026 [US2] Add the multiplicity tests to `tests/test_cli_outdir.py` (C-58, C-59, SC-015, A-18): `test_k_operands_produce_k_files` parametrised over several values of K — exactly K files appear in DIR, each named by its operand's final component and each byte-for-byte equal to the redaction of that operand, and stdout is exactly `wrote K files\n`; plus the two collision cases — `a/app.log b/app.log` leaves one `clean/app.log` holding the redaction of `b/app.log` and reports `wrote 2 files`, and the same operand named twice reports `wrote 2 files` with the file holding one redaction of it.
- [X] T027 [US2] Add the no-leakage tests to `tests/test_cli_outdir.py` (SR-013, SR-014, SC-021): `test_no_staging_path_appears_during_the_run` — no temporary or staging path appears in or beside DIR at any point, consistent with A-25's write-in-place posture; `test_no_tempfile_import` — a static check that `src/logredact/cli.py` and `src/logredact/redact.py` import neither `tempfile` nor `logging`; `test_count_line_is_only_literals_and_an_integer` — the `wrote N files` line matches `rb"^wrote \d+ files\n$"` exactly, so no file name or sample value can reach it.
- [X] T028 [P] [US2] Add `test_out_dir_memory_independent_of_operands` to `tests/test_resource_bounds.py` (FR-034, SC-018), marked `@pytest.mark.slow`: at least 50 operands whose total size is at least 100× the 1 MiB cap, written to DIR in one run, with peak RSS sampled in the child process; assert `wrote 50 files` and that the peak stays in the same band as a single-operand run rather than growing with the number or total size of the operands.

**Checkpoint**: User Stories 1 and 2 both work independently. `--out-dir` delivers the folder, the
files, the permissions and the confinement guarantees; the `--count` line is still three-field.

---

## Phase 5: User Story 3 - See the phone total in the summary (Priority: P3)

**Goal**: With `--count`, the single line on standard error becomes
`emails=N ips=N cards=N phones=N`, with the new field **appended** so a caller parsing the first
three fields positionally is affected as little as possible (A-15).

**Independent Test**: `printf 'a@b.io +442071838750\n' | python3 -m logredact --count` writes exactly
`[EMAIL] [PHONE]\n` to stdout and exactly `emails=1 ips=0 cards=0 phones=1\n` to stderr, exiting 0
(C-42, the second worked example).

### Implementation for User Story 3

- [X] T029 [US3] Change the format string in `_write_tally` in `src/logredact/cli.py` to `"emails=%d ips=%d cards=%d phones=%d\n" % (tally["emails"], tally["ips"], tally["cards"], tally["phones"])`. It stays a fixed format string over four `int` counters, so nothing derived from the data can reach it (SR-014). Note in the docstring that the reported field order deliberately differs from FR-021's precedence order (A-15), and leave the timing, the stream and the "written only when `--count` is given **and** the run exits 0" rule exactly as they are (FR-022 amends only the format).

### Tests for User Story 3

- [X] T030 [US3] Amend the expected tally text in `tests/test_cli_count.py` (C-42, C-43, C-44, C-45, SC-012): update the `TALLY` regex at line 8 to `rb"^emails=\d+ ips=\d+ cards=\d+ phones=\d+\n$"` and append ` phones=0` (or the correct non-zero total) to each expected byte string — the assertions around lines 15, 22, 35, 40, 68, 87 and 100. Then add `test_count_format` and `test_zero_counts` for the two worked shapes (`a@b.io +442071838750` → stderr exactly `emails=1 ips=0 cards=0 phones=1\n`; no redactable values → `emails=0 ips=0 cards=0 phones=0\n`), `test_appended_field_order` asserting the literal field order (C-44: `a@b.io 1.2.3.4` → `emails=1 ips=1 cards=0 phones=0\n`), `test_totals_across_operands` over several operands including phone matches, `test_summary_after_output` for the A-3 flush ordering, and `test_summary_is_exactly_four_integers` (SR-014, SC-021) asserting the line matches the regex and contains no sample value, line number or file name. This expected-text change is the only change SC-012 permits in the existing suite.
- [X] T031 [P] [US3] Amend the tally expectation in `tests/test_resource_bounds.py` around line 150 to `b"emails=%d ips=%d cards=%d phones=%d\n"` with the fourth total, the second and last of SC-012's permitted textual changes.
- [X] T032 [P] [US3] Add `test_count_and_out_dir` and `test_no_stderr_without_count` to `tests/test_cli_outdir.py` (C-46, C-47, FR-032, SC-022): with `--count --out-dir clean` over readable operands, stderr is exactly the four-field tally, stdout is exactly `wrote N files\n`, and no tally text appears in any output file; with `--out-dir clean` and no `--count`, a successful run leaves stderr exactly empty. Together these two formats are the whole of SC-022's "what was removed, how many files" contract. **Depends on US2** (T019) for the `--out-dir` destination.

**Checkpoint**: Stories 1, 2 and 3 all work. The tally reports four fields; the whole 001 suite
passes with only the tally text changed.

---

## Phase 6: User Story 4 - Fail loudly when the output folder cannot be used (Priority: P3)

**Goal**: Every `--out-dir` failure names what went wrong on standard error, with no traceback and
no input data, and exits 2 — never a quietly short or missing output file mistaken for a complete
redaction.

**Independent Test**: Run `--out-dir` naming a path that cannot be created and assert the status is
2, that stderr identifies the path, and that no output file was produced (C-63).

### Implementation for User Story 4

- [X] T033 [US4] Reject a repeated `--out-dir` in `_run` in `src/logredact/cli.py` (FR-023, SR-016, research.md R18): immediately after parsing and **before** DIR is created or any operand opened, `if args.out_dir is not None and len(args.out_dir) > 1`, report `--out-dir may be given at most once` through `_error` and `return EXIT_ERROR`. Two lines, and record in a comment that this is a deliberate departure from argparse's last-one-wins: `--out-dir a --out-dir b` expresses two different destinations, and silently honouring one writes files somewhere the caller may not have meant — the silent wrong answer Principle II calls the highest-severity defect. A repeated `--count` keeps today's accepting behaviour, because FR-035 requires everything this spec does not name to stay exactly as it is.
- [X] T034 [US4] Reject `--out-dir` with no FILE operand in `_run` in `src/logredact/cli.py` (FR-031, A-16, research.md R23): after the duplicate check and still before DIR creation and before stdin is touched, `if args.out_dir and not args.files`, report `--out-dir requires at least one FILE operand` through `_error` and `return EXIT_ERROR` — **not** via `parser.error()`, which would raise `SystemExit` from inside the run and break `main`'s documented "returns the process exit status" contract while giving this one usage error an argparse usage block where every other in-run failure produces a one-line diagnostic. Placing it here is what makes FR-031's "standard input not read" and "DIR not created" both hold.
- [X] T035 [US4] Confirm, and pin with a comment in `src/logredact/cli.py`, that the `except _OverLengthLine` branch in `_run` returns `EXIT_ERROR` **before** the `wrote N files` line is written (FR-033, A-25). No part of the over-length line reaches any output file, lines written before it stay, no later operand is read, and the absence of the count line is what tells the caller the folder cannot be trusted. Adjust the ordering only if T019 placed the count line where this branch can reach it.

### Tests for User Story 4

- [X] T036 [US4] Add `test_unreadable_operand_skipped` to `tests/test_cli_outdir_errors.py` (C-62, FR-028, SC-019, Story 4 scenario 1): operands `app.log missing.log web.log` with `--out-dir clean` — `clean/app.log` and `clean/web.log` are present and complete, no `clean/missing.log` exists, stderr contains `ERROR_PREFIX` and names `missing.log`, stdout is exactly `b"wrote 2 files\n"`, and the status is 2.
- [X] T037 [US4] Add the DIR-creation failure tests to `tests/test_cli_outdir_errors.py` (C-63, C-64, C-72, FR-029): `test_dir_is_a_regular_file` — `--out-dir` naming an existing regular file gives stderr naming that path with reason `File exists`, no operand read, no output file, stdout exactly `b""`, status 2; `test_empty_dir_value` — `--out-dir ""` gives `No such file or directory`, nothing read, status 2; `test_dir_parent_denies_write` — a `0o500` parent gives `Permission denied`, stdout empty, status 2, carrying `@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permissions")` exactly as `tests/test_cli_errors.py:176` already does, because `os.mkdir` under a `0o500` parent *succeeds* as root (research.md R19, R25).
- [X] T038 [US4] Add `test_out_dir_without_operand` to `tests/test_cli_outdir_errors.py` (C-65, FR-031, Story 4 scenario 4): `--out-dir nope` with no operand and stdin closed — stderr describes the rejected usage, stdin is not read, stdout is exactly `b""`, `nope` does **not** exist afterwards, status 2.
- [X] T039 [US4] Add the output-open and flush failure tests to `tests/test_cli_outdir_errors.py` (C-66, FR-030): `test_output_file_cannot_be_opened` — with `clean/app.log` not openable for writing, stderr names the output path, the later operand `b.log` is still processed, status 2, carrying the same `skipif(os.geteuid() == 0)` marker; and `test_output_flush_failure_fails_run` — a flush or close failure (for example `/dev/full` as DIR's target file, or an equivalently induced `ENOSPC`) is reported naming the output path, that operand is **not** counted in N because an operand counts only after a clean close, the remaining operands are processed, and the status is 2.
- [X] T040 [US4] Add the self-write tests to `tests/test_cli_outdir_errors.py` (C-67, FR-036, SR-012, SC-017, Story 4 scenario 6): `test_output_path_is_the_input` — `--out-dir . app.log b.log` run in `app.log`'s directory leaves `app.log` not truncated and byte-for-byte unmodified, stderr carries `refusing to write` and names it, `b.log` is still processed, status 2; and `test_operand_not_truncated_when_refused` asserting the operand's size and digest explicitly, since the whole point of the identity guard is that `O_TRUNC` never reaches the input. Cover the aliasing shapes the guard exists for: `--out-dir .`, an absolute DIR containing the operand, and a hard link to the operand — each the same file by `st_dev`/`st_ino` and none the same string (research.md R21).
- [X] T041 [US4] Add the symlink confinement tests to `tests/test_cli_outdir_errors.py` (C-73, C-74, SR-010): `test_symlink_output_refused` — `clean/app.log` is a symlink to a file outside `clean`; the write is refused with `Too many levels of symbolic links`, stderr names the output path, the target's bytes are unchanged, status 2; and `test_dangling_symlink_refused_and_target_not_created` — `clean/web.log` is a **dangling** symlink to a path outside `clean`; the write is refused and that path is asserted **not** to exist afterwards. The second is a required Phase 0 regression test: it is the case an existence check would miss and the one that would otherwise silently write redacted data outside DIR (research.md R20).
- [X] T042 [US4] Add `test_over_length_line_suppresses_count_line` to `tests/test_cli_outdir_errors.py` (C-68, FR-033, Story 4 scenario 7): `--out-dir clean3 big.log app.log` where `big.log`'s second line is 1 MiB + 1 characters — the run stops, no part of the over-length line appears in any output file, `clean3/big.log` holds only the lines before it, `clean3/app.log` does **not** exist because the run read no later operand, stderr names `big.log` and reports `line exceeds the maximum length of 1048576 characters`, stdout contains **no** `wrote` text at all, status 2.
- [X] T043 [US4] Add the allowlist tests to `tests/test_cli_outdir_errors.py` (C-69, C-70, C-75, SR-016, Story 4 scenarios 8 and 9): `test_rejected_out_dir_spellings` parametrised over `--out_dir`, `--out`, `--out-di` and `--outdir` — each gives a diagnostic on stderr, stdout exactly `b""`, no directory created, non-zero status; `test_out_dir_without_value` — `--out-dir` as the last argument with no value is rejected with `expected one argument` and a non-zero status; `test_repeated_out_dir_rejected` — `--out-dir a --out-dir b app.log` gives `--out-dir may be given at most once`, with **neither** `a` nor `b` created and status 2.
- [X] T044 [US4] Add the disclosure tests to `tests/test_cli_outdir_errors.py` (C-71, SR-017, SC-021): `test_no_input_data_in_diagnostics` — over every failure path above, assert stderr contains no email address, IP address, phone number, card number or fragment of one from the input, and no input line; and `test_no_traceback_on_any_out_dir_error_path` — assert stderr contains neither `Traceback` nor `File "` on any of them, since every new failure path is a handled `OSError`.

**Checkpoint**: All four user stories are independently functional, and every failure path named in
plan.md's Principle II table has a test.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The implementation gate itself — the constitution makes a feature complete only when
the full suite passes, every requirement has a passing test, and every skip is reported.

- [X] T045 [P] Update the module docstrings in `src/logredact/redact.py` and `src/logredact/cli.py` so neither is stale: `redact.py`'s opening paragraph says "three fixed categories" and must say four, and `cli.py`'s says standard output "carries the redacted input and nothing else, ever", which is now true only without `--out-dir` — restate it as the two destinations of contracts/cli.md Streams, with stdout carrying only the `wrote N files` line when `--out-dir` is in effect. Dead or wrong comments are defects under Principle IV.
- [X] T046 Run the full suite and report it faithfully: `python3 -m pytest -q -rs` from the repository root, then `python3 -m pytest -q -m "not slow"` for the fast loop. State the pass count, and **state explicitly** that `test_dir_parent_denies_write` (C-64) and `test_output_file_cannot_be_opened` (C-66) are skipped when the suite runs as root, together with the consequence: FR-029's and FR-030's permission paths are then covered only by the other failure shapes (an existing regular file at DIR, an empty DIR value, a symlinked output path, a full device). The constitution requires a skipped test to be reported, never hidden. Where a non-root user is available, also run `sudo -u nobody env PYTHONPATH=$PWD/src python3 -m pytest -q -rs tests/test_cli_outdir_errors.py` and report that result too.
- [X] T047 [P] Verify SC-012 against the T001 baseline: confirm every test that existed before this feature still passes and that the **only** changes made to the pre-existing suite are the expected `--count` text in `tests/test_cli_count.py` and `tests/test_resource_bounds.py` plus the four-key tally helpers from T004. Any other pre-existing test that needed changing is a regression to investigate, not to accommodate.
- [X] T048 [P] Verify SC-016 by walking plan.md's [requirement-to-test mapping](./plan.md#requirement-to-test-mapping) row by row against the test files on disk: every FR-019…FR-036, SR-010…SR-017 and SC-011…SC-022 row must name at least one test that now exists and passes. Report any unmapped requirement rather than closing the gate.
- [X] T049 [P] Run the [quickstart.md](./quickstart.md) validation end to end from the repository root — sections 1 (the three worked examples, byte-for-byte), 2 (phone boundaries), 3 (the output folder, including the `find out -exec stat -c '%a %n'` permission check), 4 (every failure path) and 5 (phone linearity and the 50-operand memory bound) — and record any divergence from the stated expectations. Run 001's quickstart too, with ` phones=0` appended to its expected tally lines.
- [X] T050 Review the whole diff against the five constitution principles before declaring the feature done: I — no import outside the standard library was added and `pyproject.toml` still carries pytest configuration only; II — every new failure path reports and returns non-zero, no bare `except` or `except Exception` was introduced, and the one `None` return is the documented "already reported" convention; III — no requirement is unmapped (T048); IV — no new module, class or data structure beyond one `int` and one `str`, and the four departures in plan.md Complexity Tracking are the only ones present; V — SR-010…SR-017 each have a passing test and no Security Baseline control was waived or weakened.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: needs Phase 1; **blocks every user story** (US1's replacer increments the tally key T003 adds)
- **US1 (Phase 3)**: needs Phase 2. Touches `src/logredact/redact.py` only — no file in common with US2 or US4
- **US2 (Phase 4)**: needs Phase 2. Touches `src/logredact/cli.py`
- **US3 (Phase 5)**: needs Phase 2 for T029–T031; T032 additionally needs US2 (T019) for the `--out-dir` destination
- **US4 (Phase 6)**: needs US2 (T016–T019) — its guards sit in the option handling and the operand loop US2 creates, and its tests exercise the helpers US2 adds
- **Polish (Phase 7)**: needs every story that is being shipped

### User Story Dependencies

- **US1 (P1)**: independent. Deliverable on its own as the MVP, with the whole existing suite green and the `--count` line still three-field
- **US2 (P2)**: independent of US1 at the code level — different file — and independently testable. Can be developed in parallel with US1
- **US3 (P3)**: independent for the tally format itself (T029–T031); its one cross-story test (T032) needs US2
- **US4 (P3)**: the only genuine code dependency in the feature — it hardens the `--out-dir` path US2 builds, so it follows US2

### Within Each User Story

- Source before tests is **not** required here and tests are not written first as a rule: the suite is contract-style, run against the real CLI in a subprocess, so the implementation tasks in each phase come first and its test tasks then pin the behaviour. Where a story's tests are written first, they must be observed to fail for the right reason before the implementation lands.
- In US1: the placeholder constant (T005) and the pattern (T006) before the alternation (T007), and the alternation before the replacer branch (T008)
- In US2: the option (T016) before the helpers (T017, T018), and both helpers before the operand-loop branch (T019) that calls them
- Tasks touching the same file are sequential by definition and carry no `[P]`

### Parallel Opportunities

- T002 (new test modules) runs alongside T001 (baseline, no file changes)
- T003 (`src/logredact/cli.py`) and T004 (test helpers) run in parallel
- **US1 and US2 can be developed fully in parallel** once Phase 2 is done — US1 is confined to `src/logredact/redact.py` and `tests/test_redaction_rules.py`, US2 to `src/logredact/cli.py` and `tests/test_cli_outdir.py`
- Within US1, T014 (`tests/test_cli_stream.py`) and T015 (`tests/test_resource_bounds.py`) run in parallel with each other and with the `tests/test_redaction_rules.py` tasks
- Within US2, T028 (`tests/test_resource_bounds.py`) runs in parallel with every `tests/test_cli_outdir.py` task
- Within US3, T031 and T032 run in parallel with each other once T029 has landed
- In Polish, T045, T047, T048 and T049 run in parallel; T046 and T050 are the sequential gates

---

## Parallel Example: Phase 2 and the US1/US2 split

```bash
# Phase 2 — two files, no overlap:
Task: "T003 Add \"phones\": 0 to the run tally in src/logredact/cli.py"
Task: "T004 Four-key tally helpers in tests/test_redaction_rules.py and tests/test_resource_bounds.py"

# Then two developers, two disjoint file sets:
Developer A (US1):  src/logredact/redact.py, tests/test_redaction_rules.py, tests/test_cli_stream.py
Developer B (US2):  src/logredact/cli.py,    tests/test_cli_outdir.py
```

```bash
# Parallel inside US1 — three different test files:
Task: "T013 Phone corpora in tests/test_redaction_rules.py"
Task: "T014 Worked example C-27 in tests/test_cli_stream.py"
Task: "T015 Phone linearity in tests/test_resource_bounds.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup — T001, T002
2. Phase 2: Foundational — T003, T004 (**blocks everything**)
3. Phase 3: User Story 1 — T005…T015
4. **STOP and VALIDATE**: `python3 -m pytest -q` passes in full, including every 001 test untouched;
   `printf 'call +14155552671 now\n' | python3 -m logredact` is exactly `call [PHONE] now`
5. Shippable: the tool no longer leaks international-format phone numbers, which is the protective
   value and the most expensive gap this amendment closes

### Incremental Delivery

1. Setup + Foundational → the fourth tally key exists, nothing reports it
2. **+ US1** → phone numbers redacted; the `--count` line still three-field, so no existing caller
   sees a format change (MVP)
3. **+ US2** → `--out-dir` writes one file per operand, owner-only, confined to DIR
4. **+ US3** → the tally reports `phones`; the two permitted textual changes land in the 001 suite
5. **+ US4** → every `--out-dir` failure path fails loudly, and the folder can be trusted or is
   plainly marked untrustworthy
6. Polish → the implementation gate: full suite, reported skips, SC-012/SC-016 verified, quickstart
   run, constitution review

Each step leaves the suite green and leaves the tool usable.

### Parallel Team Strategy

1. Both developers do Setup + Foundational together (four small tasks)
2. Developer A takes US1 (`redact.py`), Developer B takes US2 (`cli.py`) — disjoint files
3. Developer A then takes US3 (T029–T031, the tally format and the two expected-text amendments)
   while Developer B continues into US4, which must follow US2
4. T032 is handed to whoever finishes second, since it needs both US2 and US3
5. Polish together, with T046 and T050 run once at the end

---

## Notes

- `[P]` means a different file and no dependency on an incomplete task
- `[USn]` maps each task to its user story for traceability
- **No new source file.** The two halves land in the two existing modules along the split that
  already exists: `redact.py` stays pure, so recognition runs as fast in-process unit tests;
  everything touching the filesystem lands in `cli.py` and is exercised through the real
  `python -m logredact` interface (plan.md Structure Decision)
- **Do not touch the line loop in `_redact_stream`.** Its `out` parameter already is the
  output-destination abstraction, which is why FR-034's memory bound holds for the new destination
  by construction and why no abstraction is added for it
- **Do not "simplify" `_longest_candidate`** or remove the `_EMAIL` lookbehind — both carry
  in-code warnings and measured justifications from 001 (research.md R5, R8)
- Commit after each task or logical group; stop at any checkpoint to validate a story on its own
- Report test results faithfully, skips included: claiming completion while a test fails or while
  part of the scope was skipped is a constitution violation
