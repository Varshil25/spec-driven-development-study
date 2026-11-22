---

description: "Task list for feature 002-phone-redaction-out-dir"
---

# Tasks: Phone Redaction and Output Folder

**Input**: Design documents from `/specs/002-phone-redaction-out-dir/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md),
[contracts/redaction-rules.md](./contracts/redaction-rules.md), [quickstart.md](./quickstart.md)

**Tests**: **REQUIRED, not optional.** FR-019 mandates that every functional and security
requirement be covered by at least one automated `pytest` test, including negative tests asserting
both exit status and message content. Constitution Principle III forbids `skipif`, `pytest.skip`,
and `xfail` in this suite. Test tasks therefore appear **before** the implementation tasks of each
story and must fail for the right reason before implementation begins.

**Organization**: tasks are grouped by user story (spec.md US1–US4) so each story can be
implemented, tested, and delivered as an independent increment.

**This feature extends an existing, implemented tool.** No module, package, or directory is added.
Every task below edits a file that already exists or creates one of the five new test files named in
plan.md "Project Structure".

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: `[US1]`–`[US4]`, the spec.md user story the task serves
- Every task names its exact file path

## Path Conventions

Single project, repository root `/root/sdd-study/runs/R039`:

- Source: `src/logredact/` (`cli.py`, `redact.py`; `__init__.py` and `__main__.py` untouched)
- Tests: `tests/`
- Run with `PYTHONPATH=src`; `pyproject.toml` already sets `pythonpath = ["src"]` for pytest

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: establish and record the pre-change baseline, so FR-005's "byte-for-byte identical"
claim has something to be measured against, and confirm the platform the design requires.

- [X] T001 Record the pre-change baseline by running `python3 -m pytest -q` from the repository root and noting the pass count (plan.md expects 221 passing, 0 skipped, 0 xfailed); the result is the reference for FR-005/SC-003 and no source file is modified by this task
- [X] T002 Confirm the runtime prerequisites the design depends on: `python3 --version` is 3.11 or newer, and `python3 -c "import os,stat; os.O_NOFOLLOW; os.O_NONBLOCK; os.fchmod"` succeeds (POSIX-only primitives, research.md D-113); confirm `pyproject.toml` needs no change (no runtime dependency is added, FR-018, Principle I)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: shared test infrastructure and the FR-005 regression guard. Every user story's tests
import the conftest constants, and every story must leave feature 001's behaviour untouched, so
these block all four stories.

**⚠️ CRITICAL**: no user story work begins until this phase is complete and T005 passes against the
**unmodified** source.

- [X] T003 Extend `tests/conftest.py` with the phone sample constants alongside the existing `SAMPLE_EMAIL`/`SAMPLE_IP`/`SAMPLE_CARD`: `SAMPLE_PHONE = "+14155552671"`, `SAMPLE_PHONE_2 = "+442071838750"`, `SAMPLE_PHONE_MIN = "+12345678"` (8 digits, lower bound), `SAMPLE_PHONE_MAX = "+123456789012345"` (15 digits, upper bound), `SAMPLE_SHORT_PHONE = "+1234567"` (7 digits, must stay unchanged), `SAMPLE_LONG_PHONE = "+1234567890123456"` (16 contiguous digits, must stay unchanged), `SAMPLE_CARD_PLUS = "+4222222222222"` (13 digits passing Luhn, must stay `+[CARD]`), and `PHONE_PLACEHOLDER = "[PHONE]"`; these are the values the SC-012 gate scans captured output and every output folder for (research.md D-114)
- [X] T004 Extend `tests/conftest.py` with the output-folder helpers from research.md D-114: an `out_dir` fixture returning a non-existent nested path under `tmp_path` (e.g. `tmp_path / "reports" / "2026" / "clean"`), a `mode_of(path)` helper returning `stat.S_IMODE(os.stat(path).st_mode)` for the SC-007 assertions (expected `0o700` for directories, `0o600` for files), a `files_under(root)` helper walking every file below a directory for the SR-010/SC-012 scan, and a `running_as_root()` helper so the unwritable-destination case can choose between `os.chmod(parent, 0o500)` and the patched-`os.open` injection path — never `skipif` or `xfail` (Principle III)
- [X] T005 Create `tests/test_regression_001.py` asserting FR-005 and SC-003 against feature 001's corpus **before any source change**: `user jane@example.com from 10.0.0.7 card 4111 1111 1111 1111` → exactly `user [EMAIL] from [IP] card [CARD]`; email/IPv4/card recognition, leftmost-longest non-overlapping matching, `\n`/`\r\n`/lone-`\r` preservation, a final line gaining no terminator, non-UTF-8 bytes round-tripping via `surrogateescape`, the 1 MiB (`MAX_LINE = 1048576`) per-line ceiling failing loudly without quoting the line, empty stderr on a successful run without `--count`, and exit status 0 on success / 2 on failure — each captured as raw bytes through `run_cli` so the assertions are about bytes, not decoded text

**Checkpoint**: conftest helpers available; `test_regression_001.py` passes against unmodified
source. All four user stories can now begin.

---

## Phase 3: User Story 1 - Redact phone numbers alongside the other categories (Priority: P1) 🎯 MVP

**Goal**: an international-format phone number — a `+` immediately followed by 8 to 15 ASCII digits
not followed by a further ASCII digit — is replaced by the literal `[PHONE]`, at precedence rank 4
below card, with everything feature 001 redacts unchanged in category and position.

**Independent Test**: pipe a log sample containing international phone numbers, numbers too short
(7 digits) and too long (16 contiguous digits) to qualify, and the existing email/IPv4/card values on
standard input with no flags; confirm each phone number is replaced by `[PHONE]`, the near-miss
numbers come back byte-for-byte unchanged, and every existing placeholder appears exactly where it
did before the change.

### Tests for User Story 1 ⚠️ write first, confirm they fail

- [X] T006 [P] [US1] Create `tests/test_redact_phone.py` covering FR-001, FR-002, and SR-002 as pure-function tests over `redact.redact_line`: positives `call +14155552671 now` → `call [PHONE] now`, `+12345678` → `[PHONE]` (lower bound, exactly 8 digits), `+123456789012345` → `[PHONE]` (upper bound, exactly 15 digits), `+14155552671.` → `[PHONE].` and `+14155552671,` → `[PHONE],` (trailing non-digit), a number flush against line start and line end, `+14155552671 +442071838750` → `[PHONE] [PHONE]` (every occurrence replaced and each counted), `x ++14155552671` → `x +[PHONE]` (the second `+` anchors), `100+14155552671` → `100[PHONE]` (the character before the `+` is never examined); near-misses returned **unchanged**: `+1234567` (7 digits), `+1234567890123456` (16 contiguous digits), `+ 14155552671` and `+1 415 555 2671` (digits not contiguous with the `+`), `+1-415-555-2671` and `+1.415.555.2671`, `+١٢٣٤٥٦٧٨` (non-ASCII decimal digits, FR-002), a bare `+`; plus the SR-002 assertions that **no digit of the rejected 16-digit candidate is removed** and no digit of an accepted number survives as a substring of the output
- [X] T007 [P] [US1] Extend `tests/test_precedence.py` for the four-rank precedence of FR-003 and contracts/redaction-rules.md §3: `+14155552671@example.com` → `[EMAIL]` (rank 1 beats rank 4), `+10.0.0.7` → `+[IP]` (rank 2), `+4222222222222` → `+[CARD]` (rank 3 beats rank 4 — the case that makes FR-005 literally true), `4111111111111111+14155552671` → `[CARD][PHONE]` (adjacent spans of different ranks, each replaced once), `[PHONE] +14155552671` → `[PHONE] [PHONE]` (inserted placeholder text is never re-scanned, R-3), and the slice-boundary soundness case from contracts/redaction-rules.md §3 where a gap abuts a rank 1–3 match; assert each character is replaced at most once and no placeholder is nested (INV-7, INV-8)
- [X] T008 [P] [US1] Extend `tests/test_performance.py` for SR-004 and SC-010 with adversarial 10 000-character single lines through the complete four-rank pipeline, each asserted to complete inside a fixed budget well under 1 s: `'+' * 10000`, `'1' * 10000`, `'+1' * 5000`, and `('+' + '1' * 16) * 588` (the worst backtracking case, measured 6.78 ms in research.md D-103)
- [X] T009 [P] [US1] Extend `tests/test_security.py` with the phone-category security assertions: SR-001 — `[PHONE]` is a fixed literal with no length hint, padding, hash, or counter, and no matched value or fragment appears in any diagnostic, usage text, or summary; SR-003 — all four categories redact with no flag given and **no option exists** that disables or weakens any of them (assert the parser surface is `--count`, `--out-dir`, `-h`/`--help` only); SR-002 — `SAMPLE_PHONE` is absent as a substring of every captured stream

### Implementation for User Story 1

- [X] T010 [US1] Add the rank-4 constants to `src/logredact/redact.py` beside the three existing placeholders: `PHONE_PLACEHOLDER = "[PHONE]"` and `_PHONE = re.compile(r"\+[0-9]{8,15}(?![0-9])")` transcribed verbatim from contracts/redaction-rules.md §2 — the digit class written out explicitly as `[0-9]` because the shorthand admits non-ASCII decimal digits (FR-002, research.md D-004/D-101), the quantifier bounded `{8,15}` with no nesting (SR-004), and the `(?![0-9])` lookahead so a 16th contiguous digit rejects the whole candidate rather than yielding `[PHONE]` plus surplus digits (FR-002, SR-002, P-5)
- [X] T011 [US1] Add the third matching stage to `redact_line` in `src/logredact/redact.py` per research.md D-102: after the existing card stage, run `_PHONE.finditer` over the **gaps no rank 1–3 match claimed**, offsetting each span by its gap start exactly as the card stage does, appending `(start, end, PHONE_PLACEHOLDER)` to `matches` and incrementing a fourth counts key; the gap set must be recomputed to exclude the rank-3 card spans, not reuse the rank 1–2 gap list, so card outranks phone (FR-003, INV-7); seed the returned counts dict as `{"emails": 0, "ips": 0, "cards": 0, "phones": 0}` — exactly those four keys, always present (FR-004, data-model.md §3), and keep the rebuild step unchanged so slices stay verbatim and placeholders literal (INV-8)
- [X] T012 [US1] Update the counts plumbing in `src/logredact/cli.py`: seed `counts` in `main` as `{"emails": 0, "ips": 0, "cards": 0, "phones": 0}` and add `counts["phones"] += delta["phones"]` to `_consume`'s accumulation block, so the fourth figure totals replacements across every input source (FR-004, data-model.md §3)
- [X] T013 [US1] Update the parser `description` in `build_parser` in `src/logredact/cli.py` to name all four categories ("email addresses, IPv4 addresses, Luhn-valid payment card numbers, and international phone numbers"), so `-h`/`--help` describes what the tool actually redacts while still printing to stdout and exiting 0 (spec Assumptions)
- [X] T014 [US1] Run `python3 -m pytest -q tests/test_redact_phone.py tests/test_precedence.py tests/test_performance.py tests/test_security.py tests/test_regression_001.py` and then the full suite; every US1 test passes, `test_regression_001.py` still passes byte-for-byte, and the only pre-existing failures permitted are the three-field `--count` assertions in `tests/test_cli_count.py` that FR-004 supersedes and US3 updates

**Checkpoint**: User Story 1 is fully functional and independently testable — the tool is a strictly
better redactor with no new option and nothing else changed. **This is the MVP.**

---

## Phase 4: User Story 2 - Write a redacted copy of each log into an output folder (Priority: P2)

**Goal**: `--out-dir DIR` writes each FILE's redacted stream to `DIR/<basename-of-FILE>` instead of
standard output, creating DIR and its missing parents with owner-only permissions, replacing an
existing regular file of that name in full, and reporting `wrote N files` on standard output.

**Independent Test**: create two small log files with known content, run the tool with `--out-dir`
pointing at a folder that does not exist, and confirm the folder is created, contains exactly two
files named after the inputs with the expected redacted content, standard output is exactly
`wrote 2 files`, standard error is empty, and the exit status is 0.

**Depends on**: Phase 2 only. US2 is independently demonstrable without US1 (its output files simply
contain no phone redactions until US1 lands).

### Tests for User Story 2 ⚠️ write first, confirm they fail

- [X] T015 [US2] Create `tests/test_cli_out_dir.py` covering the FR-006 – FR-011 and FR-013 success paths with `run_cli` byte-level assertions: both `--out-dir DIR` and `--out-dir=DIR` forms; the option honoured in **any** position (`app.log --out-dir clean web.log` equivalent to `--out-dir clean app.log web.log`) with the value never treated as a FILE; `--out-dir x --out-dir y` using the **last** occurrence; redacted lines landing in `DIR/<basename>` with **no redacted content on stdout** (US2-2); a nested `reports/2026/clean` with all three levels created before any output file (FR-008); an existing `clean/app.log` holding 30 bytes of unrelated content replaced in full by 14 bytes with no tail remnant (FR-009); the input path `logs/2026/app.log` producing `clean/app.log` with **no `clean/logs` directory created** (FR-007, US2-5); stdout exactly `wrote 1 file\n` (singular) for one FILE and `wrote 3 files\n` for three (FR-010); N counting FILE **arguments** — a FILE named twice counts twice, and two FILEs sharing a basename count twice with the later replacing the earlier (FR-011); FR-013 structure preservation — an empty input giving an empty output file, an unterminated final line gaining no terminator, `\n`/`\r\n`/lone `\r` written exactly as read, and non-UTF-8 bytes round-tripping; and the SC-005 equivalence check that each output file is byte-identical to piping that one FILE through the tool without `--out-dir`

### Implementation for User Story 2

- [X] T016 [US2] Add the option to `build_parser` in `src/logredact/cli.py`: `parser.add_argument("--out-dir", metavar="DIR", default=None, help="write one redacted file per FILE into DIR instead of standard output")` — `default=None` and **not** `default=""`, because absent (`None` → stream to stdout per FR-017) and empty (`""` → reject per SC-008) must stay distinguishable (research.md D-106, data-model.md §1); argparse's store action already gives FR-006's last-occurrence-wins and the exit-2 `expected one argument` error for a missing value, with no code
- [X] T017 [US2] Extend `_partition` in `src/logredact/cli.py` with a one-entry table of value-taking options and an `expect_value` flag, so the token following `--out-dir` is grouped with the options rather than with the FILE paths (research.md D-105): treat a token as value-taking when it contains no `=` and is a prefix of `--out-dir` at least three characters long, which preserves argparse's option abbreviation for **both** options as FR-005 requires (`--cou` must stay exit 0, so `allow_abbrev=False` is not an option); verify the six regroupings tabulated in D-105, including `--out-dir --count a.log` taking `--count` literally as the value and `--count --out-dir clean -` leaving a FILE of `-` a literal relative path; update the docstring, whose current "No option in this tool takes a value" premise this task invalidates
- [X] T018 [US2] Add `_make_out_dir(dir_value)` to `src/logredact/cli.py` per research.md D-108: walk up from `dir_value` collecting the path components that do not exist, then create them top-down with `os.mkdir(component, 0o700)` followed by `os.chmod(component, 0o700)` — the explicit `chmod` is required because `mkdir`'s mode argument is masked by `umask`, and the explicit loop is required because `os.makedirs(mode=0o700)` applies the mode to the **leaf only** (measured `0755` on every intermediate), which fails SC-007 for the nested DIR of US2-3; components that already exist are used as-is and **not** re-permissioned (SR-008, D-108); the function raises `OSError` and reports nothing — `main` owns every diagnostic
- [X] T019 [US2] Add `output_path_for(out_dir, file_path)` to `src/logredact/cli.py` with the signature fixed by contracts/cli.md "Internal entry point", implementing SR-005 in the order of research.md D-111: (1) `name = os.path.basename(file_path)`, which alone discards directory components, `..` segments, and an absolute root; (2) raise `ValueError` when `name` is in `("", ".", "..")`; (3) `path = os.path.join(out_dir, name)` and require `Path(path).resolve().parent == Path(out_dir).resolve()`, raising otherwise — the DIR value itself is used **as given**, never resolved or rebased for the write (spec Assumptions, O-4), while the path *within* DIR is resolved and verified to be a **direct child** (O-6)
- [X] T020 [US2] Add `open_output(path, input_fd)` to `src/logredact/cli.py` with the signature fixed by contracts/cli.md, implementing the nine ordered steps of data-model.md §6 and research.md D-109 exactly: `os.lstat(path)` as an advisory pre-check so a symlink is reported as "not a regular file" rather than the kernel's misleading "too many levels of symbolic links" (D-110); `fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)` with **no `O_TRUNC`** — `O_NOFOLLOW` is the authoritative symlink guard (SR-006), `O_NONBLOCK` makes a planted FIFO fail immediately instead of hanging (Principle II); `stat.S_ISREG(os.fstat(fd).st_mode)` checked **on the descriptor** so there is no time-of-check gap (SR-006); `os.path.samestat(os.fstat(fd), os.fstat(input_fd))` must be false, refusing the `--out-dir .` case **before** anything is destroyed (SR-008, O-10); `os.fchmod(fd, 0o600)`, which also narrows a pre-existing `0o666` file and never widens (SR-007, SC-007); `os.ftruncate(fd, 0)` **last of all**, the first destructive act and only after every check has passed (FR-009); then wrap as `open(fd, "w", encoding="utf-8", errors="surrogateescape", newline="")` — the identical encoding triple as stdout, which is FR-013 with no new policy (O-12); close the descriptor on every failure path and raise `OSError`/`ValueError` rather than reporting
- [X] T021 [US2] Add the output-failure diagnostics to `src/logredact/cli.py` in the one-line `python -m logredact: …` shape of the existing `_report_unreadable`, with **no usage text** because these are not usage errors (research.md D-107): one reporter naming DIR for a creation failure, and one naming the output path for an unusable name, a containment violation, a non-regular path ("not a regular file"), a same-file-as-input refusal (naming both paths), and an open/write/flush/close failure — each a single line, never a stack trace, and naming only paths the invoking user supplied or paths derived from them (SR-001, contracts/cli.md Diagnostics)
- [X] T022 [US2] Add the destination branch to `main` in `src/logredact/cli.py` per research.md D-112: create DIR once, after argument validation and **before** the first FILE is opened (FR-008); for each `(name, stream)` from `_iter_sources`, when `options.out_dir is not None` derive the path with `output_path_for`, open it with `open_output(path, stream.fileno())`, pass that stream to the **unchanged** `_consume` as `out`, and flush and close it in a `finally` nested inside the existing per-source `finally` so at most one output file is open at any instant (SR-011, INV-12, O-13); treat flush and close failures as part of the success condition — report and return 2, because a buffered tail lost at close is a silent truncation (SR-009, FR-015); on success write exactly `f"wrote {n} file{'' if n == 1 else 's'}\n"` with `n = len(options.files)` to stdout after the last output file closes, then flush stdout (FR-010, FR-011); without `--out-dir` nothing in this branch runs and `out` stays stdout, so FR-017's "no file, directory, temporary file, or cache created anywhere" holds structurally (INV-10)
- [X] T023 [US2] Run `python3 -m pytest -q tests/test_cli_out_dir.py` and then the full suite; every US2 success path passes, `test_regression_001.py` and the US1 tests still pass, and `tests/test_cli_stream.py`/`tests/test_cli_files.py`/`tests/test_cli_errors.py`/`tests/test_encoding.py` are unchanged and green (FR-005)

**Checkpoint**: User Stories 1 and 2 both work independently — the tool is both a better redactor and
a batch utility.

---

## Phase 5: User Story 3 - Confirm how many phone numbers were redacted (Priority: P3)

**Goal**: `--count` writes `emails=N ips=N cards=N phones=N` to standard error, once per run, on
success only.

**Independent Test**: run with `--count` on input containing a known number of each of the four
categories, capture the two output streams separately, and confirm standard error is exactly the
four-field summary with figures matching an independent manual tally, and that standard output
carries none of it.

**Depends on**: US1 (the `phones` figure only moves once rank 4 exists) and, for the FR-016 ordering
assertion only, US2's tally line.

### Tests for User Story 3 ⚠️ write first, confirm they fail

- [X] T024 [US3] Update `tests/test_cli_count.py` from the three-field to the four-field summary — the one place FR-019 permits an existing 001 test to change — covering FR-004 and FR-016: `a@b.io +442071838750` with `--count` gives stdout `[EMAIL] [PHONE]` and stderr exactly `emails=1 ips=0 cards=0 phones=1\n`; input with nothing redactable gives exactly `emails=0 ips=0 cards=0 phones=0\n`; the same phone number on three separate lines gives `phones=3`, counting **replacements**, not lines and not distinct values (US3-3); the four fields appear in the order `emails`, `ips`, `cards`, `phones`, separated by **single** spaces, with a single `=` each, one trailing newline, and no leading or trailing padding; the summary appears on stderr **only**, never on stdout; with `--count` **and** `--out-dir clean` and two FILEs, stdout is `wrote 2 files` and stderr is the **single** run-wide summary totalled across both FILEs, written after every output file is complete and after the tally line (FR-016, US3-5); without `--count`, stderr is empty with and without `--out-dir` (US3-6); and on a run that exits 2 no summary is written at all (US4-8)

### Implementation for User Story 3

- [X] T025 [US3] Update the summary in `main` in `src/logredact/cli.py` to the single format string `"emails={emails} ips={ips} cards={cards} phones={phones}\n".format(**counts)` with `phones` **appended** rather than inserted, so a script reading the first three fields positionally keeps working (research.md D-104, spec Assumptions); keep it on the success path only — after the final stdout flush has succeeded and, with `--out-dir`, after the `wrote N files` line — so every failure path returns before it (FR-004, FR-016, INV-13); update the `--count` `help` text in `build_parser` to the four-field form
- [X] T026 [US3] Run `python3 -m pytest -q tests/test_cli_count.py` and the full suite; the four-field summary passes in both the stdout-streaming and `--out-dir` modes and no other test regresses

**Checkpoint**: User Stories 1, 2, and 3 all work independently.

---

## Phase 6: User Story 4 - Learn immediately when an output folder or file cannot be used (Priority: P3)

**Goal**: every output-folder failure produces a one-line diagnostic naming the problem on standard
error, exit status 2, no `wrote N files` line, and no `--count` summary — never a half-filled folder
reported as success.

**Independent Test**: run the batch mode against a missing input path, against an output folder path
that cannot be created, and with `--out-dir` but no FILE; confirm each produces a non-empty
diagnostic naming the problem on standard error, no `wrote N files` line, and exit status 2.

**Depends on**: US2 (these are the failure paths of US2's success path).

### Tests for User Story 4 ⚠️ write first, confirm they fail

- [X] T027 [P] [US4] Create `tests/test_cli_out_dir_errors.py` covering FR-012, FR-014, FR-015, and all ten SC-008 cases, each asserting the exit status **2**, the diagnostic content on stderr, **and** the absence of both the `wrote N files` line and the `--count` summary: `--out-dir` with no FILE → usage diagnostic, stdin **not read**, and no directory created (FR-012, US4-3); `--out-dir` as the final argument with no value → argparse `expected one argument` with usage (US4-4); `--out-dir ""` → a diagnostic that DIR must not be empty (US4-5); DIR naming an existing **regular file** → a diagnostic naming DIR, with no input file read to completion (US4-6); a non-existent FILE and a FILE whose permissions deny reading → a diagnostic naming that FILE (FR-014, US4-2); two FILEs where the second is missing → the **first output file complete and left in place**, the second FILE's diagnostic, no tally, no summary, exit 2 (US4-1); the output path occupied by a directory (`mkdir -p clean/busy.log`) and by a FIFO (`os.mkfifo`, which must **fail immediately, not hang**); an unwritable destination, produced by `os.chmod(parent, 0o500)` when not running as root and otherwise by `call_main` with a patched `os.open` (research.md D-114 — no `skipif`, no `xfail`); and write/flush/**close** failures injected through `call_main`, since a buffered tail lost at close must not exit 0 (SR-009)
- [X] T028 [P] [US4] Create `tests/test_out_dir_security.py` covering SR-005 – SR-008, SR-010, and SR-012, including direct unit tests of `output_path_for` and `open_output`: FILEs with deep prefixes, `..` segments, and absolute paths all writing **only** `DIR/<basename>` (`logs/2026/app.log`, `../../etc/passwd`, and `/etc/passwd` → `DIR/app.log`, `DIR/passwd`, `DIR/passwd`), with nothing outside DIR created, modified, or truncated (SC-006); a basename of `""`, `.`, or `..` (from `a/`, `.`, `..`, `sub/..`) refused with exit 2; a path not resolving to a direct child of the resolved DIR refused; a **symlink planted at the output path not followed** — exit 2, a diagnostic naming the path, and the link target **never created** (SR-006, SC-006); a device and a socket at the output path each failing loudly; every created directory `0o700` **including the intermediates** of a nested DIR and every output file `0o600`, whether created or replacing a pre-existing `0o666` file (SR-007, SC-007); **no temporary file appearing at any point** during the run (SR-007); `--out-dir .` with a FILE in `.` refused **without truncating the input**, and the input FILE's content, mode, and mtime unchanged with it never opened for writing (SR-008, G-4); at most one output file handle open at a time (SR-011); and the SC-012 scan asserting no prepared sample value appears in **any** file under the output folder (SR-010)
- [X] T029 [P] [US4] Extend `tests/test_limits.py` for SR-011 across both destinations: the 1 MiB (`MAX_LINE = 1048576`) per-line ceiling enforced identically with and without `--out-dir`, failing loudly with exit 2 and a message that names the input source and states the limit but **does not quote the line** (assert no digit of the over-long line appears on stderr, US4-9); and peak memory staying bounded by the per-line limit across a many-file batch regardless of file count (SC-009)
- [X] T030 [P] [US4] Extend `tests/test_security.py` for the new on-disk surface: FR-017 and G-3 — without `--out-dir`, run under `python3 -B` with `PYTHONDONTWRITEBYTECODE=1` in an empty working directory and assert **nothing at all** is created, written, or modified (`find . -mindepth 1` empty); G-3b — with `--out-dir`, the only paths created or written are DIR, its missing parents, and one regular file per FILE directly inside DIR; SR-003 — `--out-dir` changes only the destination, never which categories are redacted nor any line's redaction (same bytes as the stdout mode, SC-005); FR-018 — `python -m logredact` runs with `PYTHONPATH=src` and no non-stdlib import exists anywhere under `src/` (allowed set: `re`, `os`, `io`, `sys`, `stat`, `errno`, `argparse`, `pathlib`); SR-009 — a truncated output file never accompanies exit 0

### Implementation for User Story 4

- [X] T031 [US4] Add the two argument-level validations to `main` in `src/logredact/cli.py` via `parser.error(...)`, inside the existing block that swaps `sys.stderr` for the injected stream around `parse_args` (research.md D-107, data-model.md §1): reject `options.out_dir == ""` with a message that DIR must not be empty (SC-008, SR-012), and reject `options.out_dir is not None and not options.files` with a message that `--out-dir` requires at least one FILE (FR-012, US4-3); both emit usage plus the message to stderr and raise `SystemExit(2)`, which the existing `_exit_code` already translates; placing them here is what makes FR-012's "standard input not read, no directory or file created" hold **structurally** — the checks run before any source is opened and before DIR is touched (SR-012), with no coerced value, no fallback to stdout, and no fallback to stdin (Principle II)
- [X] T032 [US4] Confirm and complete the failure-path coverage in `src/logredact/cli.py` surfaced by T027–T030: every `except OSError` in the new code adds context and reports rather than discarding (Principle II), each failure path returns **before** the tally and the summary (INV-13), a `ValueError` from `output_path_for` is reported with the same one-line shape as an `OSError`, and the open/write/flush/close reporters name only the output path or DIR — no input line content, no matched value, no stack trace (SR-001)
- [X] T033 [US4] Run `python3 -m pytest -q tests/test_cli_out_dir_errors.py tests/test_out_dir_security.py tests/test_limits.py tests/test_security.py` and then the full suite; every one of SC-008's ten failure cases exits 2 with its diagnostic and without the tally or the summary, and no case exits 0

**Checkpoint**: all four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T034 [P] Update the module docstring and comments in `src/logredact/redact.py` from three categories to four: the summary line, the "three-stage pipeline" description in `redact_line` (now three matching stages plus the rebuild), and the counts-keys sentence naming `"phones"` (contracts/redaction-rules.md is the authoritative grammar the file transcribes)
- [X] T035 [P] Update the module docstring and stale comments in `src/logredact/cli.py`: note that output files are a second destination governed by the same encoding policy, correct the `MAX_LINE` comment's requirement references to this feature's SR-011, and record the POSIX platform narrowing with its reason (research.md D-113, plan.md Complexity Tracking) so a reader learns why `O_NOFOLLOW` has no fallback
- [X] T036 [P] Add the SC-009 throughput checks: in `tests/test_performance.py`, a 10 MB input redacted in under 10 s to **both** destinations; and confirm `tests/test_limits.py`'s batch memory assertion from T029 covers "a batch of 100 large files does not exhaust memory" with memory bounded by the per-line limit
- [X] T037 Walk `specs/002-phone-redaction-out-dir/quickstart.md` Scenarios 1–8 by hand from the repository root with `PYTHONPATH=src`, confirming each documented output, exit status, `diff`, `stat -c '%a %n'` mode (expect `700 700 700 600`), and the Scenario 8 `grep` gate printing `SC-012 ok`
- [X] T038 Run the two constitution gates from quickstart.md "Automated suite": the Principle I stdlib-only import grep over `src/` (expect `stdlib-only ok`) and the Principle III grep for `skipif`, `pytest.skip`, and `xfail` over `tests/` (expect `no skips ok`)
- [X] T039 Run `python3 -m pytest -q` from the repository root: the full suite passes with **0 skipped and 0 xfailed**, the pass count exceeds T001's baseline, and every one of the 31 requirements (FR-001 – FR-019, SR-001 – SR-012) is traceable to at least one assertion via plan.md's Requirement-to-Test Mapping (SC-011, FR-019)
- [X] T040 Confirm the delivery surface is unchanged where it must be: `pyproject.toml` still declares no runtime dependency and no build backend, `src/logredact/__init__.py` and `src/logredact/__main__.py` are untouched, and no module, package, or directory was added (plan.md Structure Decision, Principle IV)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Setup — **blocks all four user stories**, because every
  story's tests import the conftest constants and every story must leave 001 untouched (FR-005)
- **User Story 1 (Phase 3)**: depends on Phase 2 only
- **User Story 2 (Phase 4)**: depends on Phase 2 only — independent of US1
- **User Story 3 (Phase 5)**: depends on US1 (the `phones` figure) and, for the FR-016 ordering
  assertion only, on US2's tally line
- **User Story 4 (Phase 6)**: depends on US2 — it is the failure side of US2's success path
- **Polish (Phase 7)**: depends on all four stories

### User Story Dependencies

- **US1 (P1)**: no dependency on another story. Deliverable alone — **the MVP**
- **US2 (P2)**: no dependency on another story. Deliverable alone; its output files simply carry no
  phone redactions until US1 lands
- **US3 (P3)**: needs US1 for a non-zero `phones` figure; its US3-5 ordering assertion needs US2
- **US4 (P3)**: needs US2; US4-8 ("no summary on a failing run") also touches US3's summary

### Within Each User Story

- Test tasks are written first and must fail for the right reason before implementation
- Constants before the stages that use them (T010 before T011)
- `redact.py` before `cli.py` where counts flow between them (T011 before T012)
- Helpers before the branch that calls them (T018, T019, T020, T021 before T022)
- Parser surface before the validation that inspects it (T016 before T031)
- Each story ends with its own suite run before the next priority begins

### Parallel Opportunities

- **Phase 2 is sequential**: T003 and T004 edit the same file (`tests/conftest.py`) and T005 imports
  what they add
- **Phase 3**: the four test tasks T006, T007, T008, T009 touch four different files and can run in
  parallel. The implementation tasks T010 – T013 cannot: T010/T011 share `redact.py`, T012/T013
  share `cli.py`, and T012 depends on T011's return shape
- **Phase 4**: T016 – T022 all edit `src/logredact/cli.py` in dependency order — **no parallelism**
  inside the implementation of US2
- **Phase 6**: the four test tasks T027, T028, T029, T030 touch four different files and can run in
  parallel
- **Phase 7**: T034, T035, T036 touch different files and can run in parallel; T037 – T040 are
  verification gates and run last, in order
- **Across stories**: once Phase 2 completes, US1 (Phase 3) and US2 (Phase 4) can be worked by two
  people at once — they share no source region, US1 touching `redact.py` plus the counts lines of
  `cli.py` and US2 touching the parser, helpers, and destination branch of `cli.py`

---

## Parallel Example: User Story 1

```bash
# All four US1 test files are independent — launch together:
Task: "Create tests/test_redact_phone.py covering FR-001, FR-002, SR-002"            # T006
Task: "Extend tests/test_precedence.py for the four-rank precedence of FR-003"       # T007
Task: "Extend tests/test_performance.py for SR-004/SC-010 adversarial lines"         # T008
Task: "Extend tests/test_security.py with the phone-category assertions"             # T009

# Then implement in order — T010 and T011 share redact.py, T012 needs T011's counts shape.
```

## Parallel Example: User Story 4

```bash
# All four US4 test files are independent — launch together:
Task: "Create tests/test_cli_out_dir_errors.py for FR-012/FR-014/FR-015/SC-008"      # T027
Task: "Create tests/test_out_dir_security.py for SR-005 - SR-008, SR-010, SR-012"    # T028
Task: "Extend tests/test_limits.py for SR-011 on both destinations"                  # T029
Task: "Extend tests/test_security.py for the new on-disk surface"                     # T030
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup — baseline recorded (T001, T002)
2. Phase 2 Foundational — conftest helpers and the FR-005 regression guard (T003 – T005)
3. Phase 3 User Story 1 — phone redaction at rank 4 (T006 – T014)
4. **STOP and VALIDATE**: quickstart Scenarios 1 and 2; `test_regression_001.py` green
5. Ship: a strictly better redactor, no new option, nothing else changed

### Incremental Delivery

1. Setup + Foundational → baseline and guard in place
2. **+ US1** → phone numbers redacted → validate → ship (**MVP**)
3. **+ US2** → `--out-dir` batch mode with the tally → validate → ship
4. **+ US3** → four-field `--count` summary → validate → ship
5. **+ US4** → every output failure loud, with exit 2 and no false success → validate → ship
6. **+ Polish** → docstrings, throughput, quickstart walkthrough, constitution gates

Each increment leaves the suite green and feature 001 byte-for-byte intact.

### Parallel Team Strategy

1. Everyone completes Phase 1 and Phase 2 together — Phase 2 is sequential and short
2. Then: Developer A takes US1 (`redact.py` + the counts lines of `cli.py`), Developer B takes US2
   (the parser, the three new helpers, the destination branch of `cli.py`)
3. US3 starts when US1 lands; US4 starts when US2 lands. Both are mostly test files, so they
   parallelise well across people
4. Polish last, by whoever finishes

---

## Notes

- `[P]` tasks touch different files and depend on nothing incomplete
- Tests are **required** here, not optional: FR-019 and Principle III. Every failure path asserts the
  exit status **and** the message content, **and** the absence of the `wrote N files` line and the
  `--count` summary
- No `skipif`, no `pytest.skip`, no `xfail` — the two otherwise-unreachable paths (unwritable
  destination as root, close failure) are reached through `call_main` with a patched `os.open`
  (research.md D-114)
- `--out-dir` is POSIX-only by deliberate decision (research.md D-113, plan.md Complexity Tracking).
  Do **not** add a `getattr(os, "O_NOFOLLOW", 0)` fallback: it would leave a security control
  silently absent
- The destructive step is always last: no `O_TRUNC`, and `ftruncate` only after the regular-file,
  containment, and same-file-as-input checks have all passed on the descriptor
- Commit after each task or logical group; stop at any checkpoint to validate a story independently
- Avoid: widening ranks 1–3, reordering the four ranks, re-permissioning directories the tool did not
  create, and any temporary file at a predictable path
