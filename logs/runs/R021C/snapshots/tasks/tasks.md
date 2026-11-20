---

description: "Task list for feature 002: phone redaction and output folder"
---

# Tasks: Phone Redaction and Output Folder (`logredact`)

**Input**: Design documents from `/specs/002-phone-redaction-out-dir/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md),
[contracts/redaction-patterns.md](./contracts/redaction-patterns.md),
[quickstart.md](./quickstart.md), [.specify/memory/constitution.md](../../.specify/memory/constitution.md)

**Tests**: **Included, and not optional here.** Constitution Principle III requires every
functional requirement to map to at least one citing automated test, and SC-015 makes that
mapping measurable. Test tasks therefore precede implementation tasks within each phase.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and
delivered as an independent increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project, feature-001 layout, **no file added or removed**:

- Runtime: `src/logredact/redact.py` (pure text layer), `src/logredact/cli.py` (I/O layer)
- Tests: `tests/` at repository root, discoverable by `python3 -m pytest` with no arguments
- Fixtures: `tests/fixtures/` (**created by this feature** — it does not exist yet)

Manual invocation is `PYTHONPATH=src python3 -m logredact`; `pyproject.toml` supplies
`pythonpath = ["src"]`, `testpaths = ["tests"]`, and `addopts = ["-m", "not slow"]` for the suite.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the pre-feature baseline and capture the golden bytes that SC-013 compares
against. **Ordering here is load-bearing**: T003 must run while `src/logredact/redact.py` and
`src/logredact/cli.py` are still unmodified, because it records what the tool produced *before*
this feature. Once T014 lands, that baseline can no longer be captured.

- [ ] T001 Confirm the pre-feature baseline is green: run `python3 -m pytest` from the repository root (configuration comes from `pyproject.toml`) and record that every existing test passes before any source change is made
- [ ] T002 [P] Create the fixture `tests/fixtures/no_plus.log` — at least 30 lines of realistic log text containing email addresses, IPv4 addresses, Luhn-valid card numbers, look-alikes, one CRLF-terminated line, one line with no trailing newline, and one byte that is not valid UTF-8, and containing **no `+` character anywhere** (not even in an email local part), which is the corpus FR-053 and SC-013 are stated over
- [ ] T003 Capture the pre-feature golden bytes into `tests/fixtures/no_plus.expected` by running `PYTHONPATH=src python3 -m logredact tests/fixtures/no_plus.log > tests/fixtures/no_plus.expected` with `src/logredact/` still unmodified, and commit the file — this is the "before" side of SC-013's byte comparison and **must be done before T014** (depends on T002)

**Checkpoint**: baseline recorded and committed; source changes may now begin.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Generalise the one existing exception type so that output-side failures can carry
their own diagnostic. Both directions of I/O now happen inside the single loop that catches
`OSError` to report an unreadable FILE, so an output failure must travel on a non-`OSError`
channel with its own message or it will be misreported as "cannot read FILE" (research R-108,
data-model.md §5).

**⚠️ CRITICAL**: T004 and T005 are a single atomic change — the class signature and all three call
sites must move together or the module will not import. This phase is a pure refactor: it changes
no observable behaviour, which is what T006 verifies.

**Scope note**: these tasks are blocking prerequisites for **US2 and US4** (the output-folder
half). US1 and US3 do not read or write `OutputWriteError` and can proceed without them; the
phase is placed first because the refactor touches `main`'s exception handler, which US2 then
extends.

- [ ] T004 Generalise `OutputWriteError` in `src/logredact/cli.py`: give it `__init__(self, message: str, *, is_stdout: bool)` storing both as attributes, keep it a direct subclass of `Exception` (it MUST NOT inherit from `OSError`), and extend its docstring to state that invariant plus the two message shapes it now carries (FR-048 for an output file or directory, FR-031a for standard output) citing research R-108
- [ ] T005 Update the three existing `OutputWriteError` sites in `src/logredact/cli.py` to the new signature: `_write` and `_flush` both raise `OutputWriteError("failed writing to standard output", is_stdout=True)` (the two distinct internal strings `"write to standard output failed"` and `"flush of standard output failed"` are replaced by the one message the handler used to hard-code), and the `except OutputWriteError` handler in `main` writes `f"logredact: error: {exc.message}\n"` to stderr and calls `_silence_stdout()` **only** when `exc.is_stdout` is true — the stderr text for a stdout failure MUST remain exactly `logredact: error: failed writing to standard output` so FR-052 holds and the feature-001 tests asserting it keep passing
- [ ] T006 Verify the refactor changed nothing observable: run `python3 -m pytest` and confirm every feature-001 test still passes with no test file amended (FR-052 checkpoint)

**Checkpoint**: foundation ready — user story implementation can begin.

---

## Phase 3: User Story 1 - Redact phone numbers from a log (Priority: P1) 🎯 MVP

**Goal**: A `+` followed by 8 to 15 digits becomes `[PHONE]`, alongside the three existing
categories, with no change to how the tool is invoked, which stream it writes to, or its exit
status.

**Independent Test**: `printf 'call +14155552671 now\n' | PYTHONPATH=src python3 -m logredact`
writes exactly `call [PHONE] now\n` to standard output, nothing to standard error, and exits 0;
the six boundary inputs in quickstart.md Scenario 1 each give the documented result.

**Story scope**: entirely within `src/logredact/redact.py` (plus one help-text line in
`src/logredact/cli.py`). Tested as string in / string out — no subprocess, no streams.

### Tests for User Story 1

> **Write these first and confirm they FAIL before T014.** They are unit tests on
> `redact.redact_line`, so the failure is immediate and precise.

- [ ] T007 [P] [US1] Create `tests/test_phone.py` with a module docstring citing FR-032 – FR-037, FR-033a, and SC-011 and pointing at `specs/002-phone-redaction-out-dir/contracts/redaction-patterns.md`, plus a helper `assert_redaction(line, expected, *, emails=0, ips=0, cards=0, phones=0)` mirroring the one in `tests/test_redact.py`: it asserts the returned text, that the tally is a `collections.Counter`, that `(counts["emails"], counts["ips"], counts["cards"], counts["phones"])` equals the four expected values, and that `set(counts) <= {"emails", "ips", "cards", "phones"}`
- [ ] T008 [US1] Add the FR-032 and FR-033 cases to `tests/test_phone.py`: `+14155552671` and `+442071838750` each become a single `[PHONE]` with `phones=1`; `+12345678` (8 digits — "8 to 15 digits, inclusive", the lower bound) and `+123456789012345` (15 digits, the upper bound) are each replaced in full; and `+1234567` (7 digits), `+1 415 555 2671`, `+1-415-555-2671`, `14155552671`, `+`, and `+abc12345678` all pass through unchanged and uncounted, while `++14155552671` gives `+[PHONE]` and `total=5+12345678` gives `total=5[PHONE]` ("no separators, spaces, or other characters between them"; no constraint on what precedes the `+`)
- [ ] T009 [US1] Add the FR-033a cases to `tests/test_phone.py`: `"digit" means one of the characters 0 to 9 only` — `+٠١٢٣٤٥٦٧٨` (Arabic-Indic), `+०१२३४५६७८` (Devanagari), and `+０１２３４５６７８` (full-width) each pass through unchanged, and `+12345678٩` gives exactly `[PHONE]٩` with `phones=1`, the trailing non-ASCII digit neither extending the candidate nor satisfying FR-034's exclusion
- [ ] T010 [US1] Add the FR-034 cases to `tests/test_phone.py`: `+1234567890123456` (16 digits) produces **no** `[PHONE]` anywhere in the output; `+4111111111111111` still produces `+[CARD]` with `cards=1, phones=0`, preserving today's output; and a `+` followed by 20 digits likewise produces no `[PHONE]` — assert the output text, not just the absence of the placeholder, so a stray trailing digit would fail the test
- [ ] T011 [US1] Add the FR-035, FR-036, and FR-037 cases to `tests/test_phone.py`: one line carrying a phone number, an email address, an IPv4 address, and a Luhn-valid card number gives all four placeholders with `emails=1 ips=1 cards=1 phones=1` and every surrounding character intact (US1.6, single-claim rule); `+14155552671@example.com` gives exactly one `[EMAIL]` with `phones=0` (precedence email → ip → card → phone at the same start position); `+4111111111119` gives `[PHONE]` and not `+[CARD]` (earliest-start-wins); the literal input text `[PHONE]` passes through unchanged and uncounted; and `1234567890123+12345678` gives `1234567890123[PHONE]`, confirming the rejected-card one-character resume still reaches a later `+` (research R-103)
- [ ] T012 [P] [US1] Create the fixture `tests/fixtures/phone_corpus.log` — at least 50 lines of log text mixing planted international-format phone numbers with look-alikes: 7-digit runs, 16-digit runs, separator-grouped forms, unprefixed digit runs, and runs written in Arabic-Indic, Devanagari, and full-width digits (SC-011)
- [ ] T013 [US1] Add the SC-011 test to `tests/test_phone.py`: record the planted phone count and the look-alike tokens as module constants, run `redact.redact_line` over every line of `tests/fixtures/phone_corpus.log`, and assert that the summed `phones` tally equals the planted count (100% of planted phone numbers redacted) and that every look-alike token is still present verbatim in the redacted output (0% of look-alikes altered) (depends on T012)

### Implementation for User Story 1

- [ ] T014 [US1] Add the `_PHONE` fragment to the shared-fragments block of `src/logredact/redact.py`, copied verbatim from `specs/002-phone-redaction-out-dir/contracts/redaction-patterns.md`: `_PHONE = r"\+[0-9]{8,15}(?![0-9])"`, with a comment recording that `[0-9]` is spelled out rather than `\d` because `\d` also matches Arabic-Indic, Devanagari, and full-width digits and would break FR-033a in both directions, and that the trailing `(?![0-9])` is the whole of FR-034 because it fails at every backtracked length from 15 down to 8 (research R-101) — **requires T003 to have been captured already**
- [ ] T015 [US1] Append the fourth alternative to `PATTERN` in `src/logredact/redact.py` so it reads `re.compile(rf"(?P<email>{_EMAIL})|(?P<ip>{_IPV4})|(?P<card>{_CARD})|(?P<phone>{_PHONE})")` with `phone` **last**, and extend the existing comment above it to state that the written order of the alternatives *is* FR-036's precedence (email → IPv4 → card → phone), that reordering changes behaviour and nothing will warn you, and that the inner group stays non-capturing so `match.lastgroup` still names the category (depends on T014)
- [ ] T016 [US1] Add the `phone` entries to the two category dicts in `src/logredact/redact.py`, written inline in the dict literals per data-model.md §1: `PLACEHOLDERS = {"email": "[EMAIL]", "ip": "[IP]", "card": "[CARD]", "phone": "[PHONE]"}` and `TALLY_KEYS = {"email": "emails", "ip": "ips", "card": "cards", "phone": "phones"}`; add **no** post-validation step for `phone` — `_longest_valid_card` must stay reachable only when `match.lastgroup == "card"`, and the `else: end = match.end()` branch of `redact_line` handles phone exactly as it handles email and ip, so the scan loop itself is untouched
- [ ] T017 [US1] Update the parser `description` string in `src/logredact/cli.py::_build_parser` to name the fourth category — email addresses, IPv4 addresses, Luhn-valid 13–19 digit card numbers, and a `+` followed by 8–15 digits, replaced with `[EMAIL]`, `[IP]`, `[CARD]`, and `[PHONE]` — so the help output describes what the tool now does
- [ ] T018 [US1] Run `python3 -m pytest tests/test_phone.py tests/test_redact.py tests/test_cli.py` and confirm the new phone tests pass **and** every feature-001 test still passes with no amendment — in particular `tests/test_redact.py`, whose unamended pass is SC-012's evidence that no existing redaction behaviour moved

**Checkpoint**: User Story 1 is complete and independently shippable. Phone numbers are redacted;
the tally line still has three fields (US3 adds the fourth) and `--out-dir` does not exist yet.

---

## Phase 4: User Story 2 - Write redacted copies into an output folder (Priority: P2)

**Goal**: `--out-dir DIR` writes each FILE's redacted lines to `DIR/<basename>` instead of to
standard output, creates `DIR` and any missing parents, replaces an existing file of that name in
full, and prints `wrote N files` to standard output.

**Independent Test**: create two small files containing personal data, run
`PYTHONPATH=src python3 -m logredact --out-dir clean app.log web.log` with no `clean` directory
present, and confirm `clean` is created holding one correctly redacted file per input named after
it, that standard output is exactly `wrote 2 files\n` with no log content, and that the exit
status is 0.

**Story scope**: entirely within `src/logredact/cli.py`. This phase delivers the **success**
paths; the failure diagnostics and the collision guard are US4.

### Tests for User Story 2

> Write these first and confirm they FAIL. They run the real CLI as a subprocess through
> `tests/conftest.py::run_cli`, because byte-exact stdout and a specific exit status are what the
> acceptance criteria are written in.

- [ ] T019 [P] [US2] Create `tests/test_out_dir.py` with a module docstring citing FR-040 – FR-051 and FR-054 and pointing at `specs/002-phone-redaction-out-dir/contracts/cli.md`, importing `run_cli` from `tests/conftest.py`, and defining a small helper that writes a named input file under `tmp_path` and returns its path — every test in this module runs `run_cli(..., cwd=tmp_path)` so operand spellings stay relative, which the FR-049 cases need
- [ ] T020 [US2] Add the US2.1 / US2.2 / FR-045 happy-path test to `tests/test_out_dir.py`: `app.log` containing `user jane@example.com\n` and `web.log` containing `GET / from 10.0.0.7\n`, no `clean` directory present, run `--out-dir clean app.log web.log`; assert stdout is exactly `b"wrote 2 files\n"`, stderr is empty, the status is 0, `clean/app.log` reads `b"user [EMAIL]\n"`, `clean/web.log` reads `b"GET / from [IP]\n"`, and no redacted log content appears on stdout (depends on T019)
- [ ] T021 [US2] Add the FR-040 / US2.8 argument-order test to `tests/test_out_dir.py`: the four argv forms `--out-dir clean a.log b.log`, `a.log --out-dir clean b.log`, `a.log b.log --count --out-dir clean`, and `--out-dir=clean a.log` all succeed, with the directory value never treated as a FILE operand and never appearing as an output file name (research R-104)
- [ ] T022 [US2] Add the FR-041 and FR-042 tests to `tests/test_out_dir.py`: `logs/2026/app.log` with `--out-dir clean` writes `clean/app.log` — "the final path component only, with any leading directories discarded" — and `clean/logs/` does not exist (US2.3); `--out-dir reports/clean/today` with none of the three directories present creates all three and writes inside the innermost (US2.4); and a FILE literally named `-` writes `clean/-`, not standard input
- [ ] T023 [US2] Add the FR-043 tests to `tests/test_out_dir.py`: a pre-existing `clean/app.log` containing `STALE\n` is replaced in full — the output file holds only the redacted input and `STALE` does not appear (US2.5); and two operands `a/app.log b/app.log` sharing a base name leave `clean/app.log` holding `b/app.log`'s redacted contents, with stdout exactly `b"wrote 2 files\n"` (US2.10, "the later operand's output replaces the earlier operand's")
- [ ] T024 [US2] Add the remaining FR-045 tests to `tests/test_out_dir.py`: an empty input file yields an empty output file of the same name that still counts toward the summary (US2.6); a single operand yields exactly `b"wrote 1 files\n"` — the wording is fixed and MUST NOT be pluralized differently for N of 1 (US2.7); and an unrelated pre-existing file in `clean` is left untouched by the run
- [ ] T025 [US2] Add the FR-046 ordering test to `tests/test_out_dir.py`: run `--count --out-dir clean app.log` with stdout and stderr captured separately and assert stdout is exactly the summary line while stderr carries one tally line beginning `b"emails="` and nothing else — the exact four-field byte assertion is added by T039 once US3's tally lands, so this test asserts only the ordering and the stream split
- [ ] T026 [US2] Amend `tests/test_fidelity.py` with the FR-044 / SC-014 cases: for each of three inputs — one with carriage-return-plus-newline endings, one whose last line lacks a trailing newline, and one containing bytes that are not valid UTF-8 — assert the `--out-dir` output file is byte-identical to the stdout the same tool produces for that single file without `--out-dir`, comparing raw `bytes` in both directions

### Implementation for User Story 2

- [ ] T027 [US2] Add the option to `src/logredact/cli.py::_build_parser`: `parser.add_argument("--out-dir", dest="out_dir", metavar="DIR", help=...)` with help text that names `DIR`, says each FILE's redacted lines are written to a file of the same base name inside it instead of to standard output, and says `DIR` and any missing parents are created — one value-taking option, no `nargs`, no `exit_on_error` override, so argparse's stock behaviour supplies FR-040's usage error for a missing value and `parse_intermixed_args` keeps accepting it anywhere on the command line (research R-104). The help text must mention `--out-dir` so FR-051 is satisfied by the same string
- [ ] T028 [US2] Add `_prepare_output_dir(out_dir: str) -> None` to `src/logredact/cli.py`: `os.makedirs(out_dir, exist_ok=True)` inside a `try`, converting `OSError` into `OutputWriteError(f"cannot use output directory {out_dir!r}: {exc}", is_stdout=False)`. Add **no** follow-up `os.path.isdir` check — the one call already covers creating `DIR` with its missing parents (FR-042), accepting a path that already exists as a directory, and rejecting anything else, because `exist_ok=True` suppresses the error only when the existing path is a directory (research R-105)
- [ ] T029 [US2] Add `_redact_file_to_dir(path: str, out_dir: str, total: collections.Counter) -> None` to `src/logredact/cli.py`, which per operand: (a) opens the **input first** with `open(path, encoding="utf-8", errors="surrogateescape", newline="\n")` so a read failure surfaces as an `OSError` before any output file exists — this is what makes US4.1's "`DIR` exists but is empty" true and is why the lazy `_iter_source_lines` generator cannot carry this open (research R-109); (b) computes `out_path = os.path.join(out_dir, os.path.basename(path))`; (c) opens it with `open(out_path, "w", encoding="utf-8", errors="surrogateescape", newline="\n")` — mode `"w"` truncates, which is FR-043, and the three text settings are identical to stdout's, which makes FR-044's byte equality a consequence of the configuration rather than something to check at runtime (research R-110), with no `line_buffering` argument so output files stay block-buffered for SC-019; (d) streams line by line through `redact.redact_line`, writing each result as it is produced and calling `total.update(line_counts)`, so one line is resident and one output file is open at a time (SC-018); (e) closes the output file explicitly so a close failure is reported; converting every `OSError` from the output open, the writes, or the close into `OutputWriteError(f"cannot write output file {out_path!r}: {exc}", is_stdout=False)`
- [ ] T030 [US2] Add `import contextlib` to the imports of `src/logredact/cli.py` and use `contextlib.suppress(OSError)` around the cleanup close in `_redact_file_to_dir`'s failure path, so that when streaming has already failed the cleanup flush cannot replace the original diagnostic with its own — FR-050 requires the unreadable FILE to be the thing named, so the first failure must win. Scope is exactly one statement, on a path that runs only when the run has already failed; this is the one deviation recorded in plan.md's Complexity Tracking (research R-112). `contextlib` is stdlib, so `tests/test_stdlib_only.py` needs no change
- [ ] T031 [US2] Wire the `--out-dir` branch into `src/logredact/cli.py::main` following data-model.md §6: when `args.out_dir is not None`, call `_prepare_output_dir(args.out_dir)` **before any input source is opened**, then loop over `args.files` in command-line order calling `_redact_file_to_dir`, reusing the existing `except OSError as exc` read handler that sets `read_error = f"logredact: error: cannot read {path!r}: {exc}\n"` and breaks (FR-029, FR-050 unchanged). The `else` branch — no `--out-dir` — must keep the existing `_iter_source_lines` / `_redact_stream` / stdin path byte-for-byte, because that is the whole of FR-052 (depends on T028, T029, T030)
- [ ] T032 [US2] Write the summary line in `src/logredact/cli.py::main`: after the operand loop, guarded by `read_error is None and args.out_dir is not None`, call `_write(stdout, f"wrote {len(args.files)} files\n")` immediately before the existing `_flush(stdout)` — inside the same `try`, so a failed summary write raises `OutputWriteError(is_stdout=True)` and produces the existing stdout diagnostic with exit 2 and no tally, and before the flush, so the summary reaches stdout before the tally reaches stderr (FR-045, FR-046, research R-111). `N = len(args.files)` with no separate counter and no pluralisation branch
- [ ] T033 [US2] Run `python3 -m pytest tests/test_out_dir.py tests/test_fidelity.py tests/test_cli.py` and confirm the new out-dir tests pass and the feature-001 stdout path is unchanged

**Checkpoint**: User Stories 1 AND 2 both work independently. `--out-dir` succeeds on well-formed
input; its failure diagnostics and the collision guard arrive in US4.

---

## Phase 5: User Story 3 - Confirm how many phone numbers were redacted (Priority: P3)

**Goal**: With `--count`, the tally line on standard error carries a fourth field, giving
`emails=N ips=N cards=N phones=N` in that fixed order, without disturbing the three existing
fields.

**Independent Test**: `printf 'a@b.io +442071838750\n' | PYTHONPATH=src python3 -m logredact
--count` writes `[EMAIL] [PHONE]\n` to standard output and exactly
`emails=1 ips=0 cards=0 phones=1\n` to standard error, and exits 0.

**⚠️ Atomicity**: T040 changes the rendered tally line, which breaks the fourteen existing
assertion sites that spell out the three-field form. T034 – T036 amend exactly those sites and
must land in the same increment as T040. The complete list of edits is the evidence for SC-012
(research R-114) — any *other* feature-001 test that fails after this phase is a regression, not
a documented difference.

### Tests for User Story 3

- [ ] T034 [US3] Amend the eight byte-exact tally assertions and the one FR-023 docstring in `tests/test_cli.py` (lines 70, 128, 208, 228, 233, 244, 265, 281, 289) to the four-field form `emails=N ips=N cards=N phones=N`, appending `phones=0` wherever the input contains no phone number and nothing else — no other change to the file
- [ ] T035 [US3] Amend `tests/test_fidelity.py`: the two assertions at lines 109 and 155 gain the `phones=N` field, the `TALLY_LINE` regex at line 169 becomes `re.compile(rb"^emails=(\d+) ips=(\d+) cards=(\d+) phones=(\d+)\n$")`, and the SC-008 placeholder-count check is extended so the fourth captured group is compared against the number of `[PHONE]` occurrences in the output stream
- [ ] T036 [US3] Amend the tally assertion at `tests/test_performance.py` line 106 to the four-field form
- [ ] T037 [US3] Add the FR-038 tests to `tests/test_cli.py`: `a@b.io +442071838750\n` on stdin with `--count` gives stdout exactly `b"[EMAIL] [PHONE]\n"`, stderr exactly `b"emails=1 ips=0 cards=0 phones=1\n"`, and status 0 (US3.1, and worked example 3 of SC-010); input with nothing to redact gives stderr exactly `b"emails=0 ips=0 cards=0 phones=0\n"` (US3.2) — assert the whole line as bytes, since "a single line of the exact form ... in that field order" is the requirement
- [ ] T038 [US3] Add the FR-039 tests to `tests/test_cli.py`: three phone numbers spread across two lines in two FILE operands report `phones=3` — the total across all input read, not per line and not per file (US3.3); and with `--count` omitted, standard error receives zero bytes, exactly as before (US3.5)
- [ ] T039 [US3] Strengthen the FR-046 test in `tests/test_out_dir.py` (added by T025) to the exact form now that the four-field tally exists: `--count --out-dir clean app.log` with the streams captured separately gives stdout exactly `b"wrote 1 files\n"` and stderr exactly `b"emails=1 ips=0 cards=0 phones=0\n"`, the tally written only after the summary line (US3.4) (depends on T025, T040)

### Implementation for User Story 3

- [ ] T040 [US3] Amend the tally line written in `src/logredact/cli.py::main` to `f"emails={total['emails']} ips={total['ips']} cards={total['cards']} phones={total['phones']}\n"` and update the comment above it: all four keys are named explicitly because the field order is fixed by FR-038 and must not come from the `Counter`'s insertion order, and the `Counter` stays un-pre-seeded because reading a never-incremented key already yields `0`, which is FR-039's "report `0` when no phone number was replaced"
- [ ] T041 [US3] Run the full suite `python3 -m pytest` and confirm it is green — every tally site in the suite now agrees with the implementation, and the set of files that needed editing is exactly `tests/test_cli.py`, `tests/test_fidelity.py`, and `tests/test_performance.py`

**Checkpoint**: User Stories 1, 2, and 3 all work. The suite is green end to end.

---

## Phase 6: User Story 4 - Fail clearly when input or output cannot be handled (Priority: P3)

**Goal**: Every new failure path names what could not be done, writes no `wrote N files` line and
no tally, emits no traceback, and exits 2 — so the summary line stays a trustworthy signal that a
complete set of redacted files exists.

**Independent Test**: run the tool with `--out-dir clean` and a FILE path that does not exist;
standard error names that path, no summary line appears on standard output, `clean` exists and is
empty, and the exit status is 2.

**Story scope**: `src/logredact/cli.py`, the ordering in `main`, and the collision machinery. All
six failure paths are tested through the real process, because byte-exact stderr and a specific
exit status are only observable there.

### Tests for User Story 4

> Each test below asserts three things, which is SC-016 stated as a test rather than a hope: the
> diagnostic names the offending path or conflict, the exit status is 2, and `b"Traceback"` does
> not appear on standard error.

- [ ] T042 [US4] Add the FR-047 test to `tests/test_out_dir.py`: `--out-dir clean2` with no FILE operand and `stdin=b"x\n"`; assert stderr names the conflict and mentions `--out-dir`, stdout is empty (no summary line), `clean2` does not exist afterwards, the piped stdin bytes appear nowhere in either stream (standard input was not read), no tally is written even with `--count`, the status is 2, and `b"Traceback"` is absent (US4.4)
- [ ] T043 [US4] Add the FR-048 shape-based tests to `tests/test_out_dir.py`, expressed through filesystem shape rather than permission bits so they hold for any user including root (research R-113): (a) a regular file already exists at the `--out-dir` path, giving `FileExistsError` (US4.5); (b) `--out-dir` names a path below a regular file, giving `NotADirectoryError`; (c) a **directory** named `clean/app.log` exists, so the output open raises `IsADirectoryError`. Each asserts the diagnostic names the offending directory or output file path, no summary line on stdout, no tally line even with `--count`, no traceback, and status 2
- [ ] T044 [US4] Add the permission-based US4.6 case to `tests/test_out_dir.py` guarded by `@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses mode bits")`: `chmod 0o500` on the parent of `DIR` so `DIR` cannot be created; assert the diagnostic names that directory, no summary line, status 2, no traceback — kept so the requirement is covered on a normal developer machine even though this environment runs as root (research R-113)
- [ ] T045 [US4] Add the FR-049 and FR-049a tests to `tests/test_out_dir.py`, each asserting the diagnostic names the offending file, that file's bytes are unchanged afterwards, no summary line, and status 2: (a) `--out-dir .` with `app.log` in the working directory (US4.7); (b) `logs/app.log` with `--out-dir ./logs` — the same directory spelled differently (US4.7a); (c) `clean/app.log` is a symbolic link to the input `app.log` (US4.7b); (d) `clean/app.log` is hard-linked to the input; plus the **negative** case FR-049a requires explicitly — an output path that does not yet exist cannot collide and MUST NOT be rejected, so a plain `--out-dir clean app.log` run still succeeds
- [ ] T046 [US4] Add the FR-054 ordering tests to `tests/test_out_dir.py`: (a) `--out-dir .` with three FILE operands of which only the **second** resolves to its own output path — assert the run fails before any output file is written (the first operand's output file does not exist), no input file is modified, the diagnostic names the offending file, and the status is 2 (US4.7c); (b) a run whose single FILE cannot be read leaves `DIR` created and empty, proving `DIR` is created before any input is read (US4.1)
- [ ] T047 [US4] Add the FR-050 test to `tests/test_out_dir.py`: a readable `app.log` followed by a nonexistent `missing.log`, with `--out-dir clean` and `--count`; assert `clean/app.log` exists with the earlier operand's full redacted contents (output already completed remains on disk), stderr carries the existing `cannot read 'missing.log'` diagnostic naming the path as spelled on the command line, no summary line is on stdout, **no** tally line is on stderr despite `--count`, no traceback appears, and the status is 2 (US4.2, US4.3)
- [ ] T048 [US4] Add the FR-040-missing-value and FR-051 tests to `tests/test_out_dir.py`: `--out-dir` with nothing after it writes an argparse usage message to stderr and exits 2 (US4.9); and `--help --out-dir clean3` writes usage text to stdout that **contains the string `--out-dir`**, leaves `clean3` nonexistent, opens no input source, writes zero bytes to stderr, and exits 0 (US4.8, FR-051)
- [ ] T049 [US4] Add the SC-017 test to `tests/test_out_dir.py`: parametrised over every failing `--out-dir` scenario in this module, assert `b"wrote "` never appears on stdout; parametrised over every succeeding one, assert it always does — so a reviewer can tell from the tool's output alone whether a complete set of redacted files was produced

### Implementation for User Story 4

- [ ] T050 [US4] Add `_file_identity(path: str) -> tuple[int, int] | None` to `src/logredact/cli.py`: call `os.stat(path)` (which follows symlinks) and return `(info.st_dev, info.st_ino)`, with `except OSError: return None`. The docstring must state that this is a *query* — "which file, if any, does this path name?" — that `None` is a truthful answer rather than a sentinel standing in for a failed operation, and that no reportable failure is lost because a missing **input** file is still reported by the read-failure path with FR-028's diagnostic, which is what US4.1 requires. `os.path.samefile` is deliberately not used: it raises when either path is missing, and a not-yet-existing output path is the common case (plan.md Complexity Tracking, research R-106)
- [ ] T051 [US4] Add `_collides(path: str, out_path: str) -> bool` to `src/logredact/cli.py`: compute `identity = _file_identity(out_path)` and return `identity is not None and identity == _file_identity(path)` — the `is not None` guard is FR-049a's closing sentence, "an output path that does not yet exist cannot collide and MUST NOT be rejected" (depends on T050)
- [ ] T052 [US4] Add the up-front sweep `_check_output_collisions(files: list[str], out_dir: str) -> None` to `src/logredact/cli.py` and call it from `main` after `_prepare_output_dir` and **before any input source is opened**: for each operand in order, compute `os.path.join(out_dir, os.path.basename(path))` and, on the first collision, raise `OutputWriteError(f"output file for {path!r} would overwrite that file: {out_path!r}", is_stdout=False)`. Because this runs before the operand loop, a collision in *any* operand — including the third of three — fails the run before a single output file has been opened, created, or truncated (FR-049, FR-054 step 3, US4.7c) (depends on T051)
- [ ] T053 [US4] Add the per-operand re-check to `src/logredact/cli.py::_redact_file_to_dir`, after the input has been opened and **before** the output is opened, using the same `_collides` call and the same diagnostic as T052. This closes the gap recorded in plan.md's Post-Phase 1 finding and research R-107: without it, `--out-dir clean a.log clean/a.log` has operand 1 create `clean/a.log` after the sweep has already cleared it, and operand 2 then truncates its own input mid-read and reports `wrote 2 files` with exit 0 — a silent wrong answer. It cannot fire on any scenario the spec requires to succeed, including the duplicate-base-name case US2.10. **If the spec owner has decided to leave that gap open, skip this task rather than implementing it, and say so in the completion report** (depends on T051)
- [ ] T054 [US4] Add the FR-047 usage error to `src/logredact/cli.py::main`, placed immediately after `parse_intermixed_args` and **before** stdout is wrapped and before `_prepare_output_dir`: when `args.out_dir is not None and not args.files`, write `"logredact: error: --out-dir requires at least one FILE operand; standard input has no file name\n"` to standard error and `return 2`. Nothing before this point touches the filesystem or standard input, which is what makes FR-047's "MUST NOT read standard input, MUST NOT create `DIR`" and FR-054 step 1 true by construction
- [ ] T055 [US4] Confirm the handler generalised in T005 reports the output-side messages correctly: an `OutputWriteError` with `is_stdout=False` writes `f"logredact: error: {exc.message}\n"` to standard error, does **not** call `_silence_stdout()`, writes no summary line and no tally line, emits no traceback, and returns 2 — so `cannot use output directory '...'`, `cannot write output file '...'`, and `output file for '...' would overwrite that file: '...'` all reach stderr in the forms fixed by `contracts/cli.md` (FR-048, FR-049, data-model.md §5)
- [ ] T056 [US4] Run `python3 -m pytest tests/test_out_dir.py` and then quickstart.md's gate 4 selection `python3 -m pytest tests/test_out_dir.py -k "error or cannot or usage or overwrite"`, confirming each failure-path case asserts the diagnostic, the exit status 2, and the absence of a traceback

**Checkpoint**: all four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Make "nothing else changed" a demonstrated claim rather than an assertion, close the
SC-015 coverage gate, and run the constitution's verification gates.

- [ ] T057 [P] Create `tests/test_preservation.py` for FR-052 with a module docstring citing FR-052, FR-053, SC-012, and SC-013: replay the feature-001 standard-output behaviour through `run_cli` with **no `--out-dir` anywhere in the module** — multiple FILE operands concatenate in command-line order, a closed stdout reader produces the unchanged `logredact: error: failed writing to standard output` diagnostic with exit 2 and no tally (FR-031a), and the exit status is only ever 0 or 2
- [ ] T058 Add the FR-053 / SC-013 byte-identity test to `tests/test_preservation.py`: run the tool over `tests/fixtures/no_plus.log` and assert stdout is byte-identical to the committed golden `tests/fixtures/no_plus.expected` captured in T003, that stderr is empty, and that the status is 0 — a corpus with no `+` character must produce byte-identical output before and after this feature (depends on T003, T057)
- [ ] T059 Add the SC-012 demonstration to `tests/test_preservation.py`: a table of probe inputs drawn from the feature-001 acceptance scenarios, each paired with the stdout feature 001 produced for it; run them all, **compute** the set of probes whose output now differs, and assert that set contains only probes carrying a `+` followed by 8 to 15 digits — then assert separately that the `--count` tally line is the one other documented difference. The differing set must be computed from the run rather than asserted by hand, which is what SC-012's "demonstrated rather than asserted" requires (depends on T057)
- [ ] T060 [P] Extend `tests/test_requirement_coverage.py` for SC-015: add `FR-032` through `FR-054` plus the lettered additions `FR-033a` and `FR-049a` (25 identifiers) and `SC-010` through `SC-019` (10) to the `FUNCTIONAL_REQUIREMENTS` and `SUCCESS_CRITERIA` lists, update the count assertions in `test_the_identifier_lists_match_what_sc004_enumerates` and add the equivalent assertion for this feature's enumeration, and leave the negative control (`citing_modules("FR-999") == []`) intact so the gate can still fail
- [ ] T061 Amend `tests/test_performance.py` for SC-019: add a `--out-dir` throughput case measuring 100,000 lines split across several FILE operands of **one** run together, asserting the whole run completes in under 30 seconds, so per-file and per-line overhead cannot accumulate with the number of operands
- [ ] T062 Amend `tests/test_performance.py` for SC-018: add a `@pytest.mark.slow` case asserting that peak resident memory on a multi-operand `--out-dir` run of at least 1 GB total stays bounded by the longest input line and does not grow with total input size or with the number of FILE operands — one line resident, one output file open at a time
- [ ] T063 Add the SC-010 worked-example tests citing `specs/002-phone-redaction-out-dir/contracts/cli.md`: example 1 (`printf 'call +14155552671 now\n' | ... ` → `call [PHONE] now`, exit 0) and example 3 (the four-field tally) in `tests/test_cli.py`, and example 2 (two files, `wrote 2 files`, `clean/app.log` and `clean/web.log`) in `tests/test_out_dir.py` — each asserting byte-identical stdout, byte-identical stderr, the stated output files and contents, and the stated exit status
- [ ] T064 [P] Update the module docstring of `src/logredact/redact.py` to name the fourth category, and the module docstring of `src/logredact/cli.py` plus `main`'s docstring to describe the output-folder mode and the FR-054 order of operations (parse → help/usage → create `DIR` → sweep for collisions → stream each operand → summary → tally), stating that `redact.py` still knows nothing about files, streams, or exit statuses and `cli.py` still contains no recognition logic
- [ ] T065 Run the constitution's four quality gates from quickstart.md and record each result: `python3 -m pytest` (full suite passes); `python3 -m pytest tests/test_requirement_coverage.py` (every new FR and SC has a citing test); `python3 -m pytest tests/test_stdlib_only.py` (no third-party import in `src/`); and `python3 -m pytest tests/test_out_dir.py -k "error or cannot or usage or overwrite"` (every invalid-input path asserts its message and failure signal). Then run `python3 -m pytest -m slow` for SC-018 and SC-019
- [ ] T066 Walk quickstart.md's six scenarios by hand with `PYTHONPATH=src python3 -m logredact` and confirm each observed result matches the documented expectation, including that the `--help` run leaves `clean3` nonexistent and the `--out-dir .` run leaves `app.log` byte-identical to its backup

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — must run first, and T003 must complete **before T014**
  because it records pre-feature output that cannot be recovered afterwards
- **Foundational (Phase 2)**: depends on Phase 1; blocks US2 and US4 (it changes `main`'s
  exception handler, which both extend). US1 and US3 do not depend on it
- **US1 (Phase 3)**: depends on Phase 1. Touches `redact.py` only (plus one help string)
- **US2 (Phase 4)**: depends on Phase 2. Touches `cli.py` only
- **US3 (Phase 5)**: depends on US1 (a `phones` tally key only exists once the category does) and
  on US2 for T039's exact-form `--out-dir` assertion
- **US4 (Phase 6)**: depends on US2 — it adds the failure paths and the collision guard to the
  `--out-dir` flow US2 builds
- **Polish (Phase 7)**: depends on all four stories. T060 in particular will fail until every new
  FR and SC has a citing test, which is deliberate: it is the gate, not a formality

### User Story Dependencies

```text
Phase 1 (Setup)
   ├─────────────────────────────┐
   ▼                             ▼
US1 (P1)  redact.py        Phase 2 (Foundational)  cli.py exception channel
   │                             ▼
   │                       US2 (P2)  --out-dir success paths
   │                             ├──────────────┐
   ▼                             ▼              ▼
US3 (P3)  4-field tally  ◄───────┘        US4 (P3)  failure paths
   └────────────┬─────────────────────────────┘
                ▼
         Phase 7 (Polish)
```

- **US1** is genuinely independent: `redact.py` knows nothing about `--out-dir`
- **US2** is independent of US1 — `--out-dir` would work with three categories
- **US3** needs US1 for a non-zero `phones` figure, and T039 alone needs US2
- **US4** extends US2's flow and cannot ship before it

### Within Each User Story

- Tests are written first and must FAIL before the implementation task that satisfies them
- `redact.py` fragment → `PATTERN` → category dicts (T014 → T015 → T016 are strictly ordered)
- `cli.py` helpers → `main` wiring → summary line (T028/T029 → T031 → T032)
- `_file_identity` → `_collides` → the two call sites (T050 → T051 → T052/T053)

### Parallel Opportunities

- **T002** runs in parallel with T001
- **T007 and T012** (new test module, new fixture) are different files with no dependency
- **T019** is a new file and can be written while US1 is still in progress
- **T026** amends `tests/test_fidelity.py`, which no other US2 task touches
- **T057, T060, T064** are three different files and can run together
- **Across stories, once Phase 2 is done**: one developer can take US1 (`redact.py` + `test_phone.py`) while another takes US2 (`cli.py` + `test_out_dir.py`); the two share no file
- **Not parallel**: T008 – T011 and T013 all append to `tests/test_phone.py`; T020 – T025 and
  T042 – T049 all append to `tests/test_out_dir.py`; T027 – T032 and T050 – T055 all edit
  `src/logredact/cli.py`

---

## Parallel Example: User Story 1

```bash
# These two touch different files and have no dependency on each other:
Task: "Create tests/test_phone.py with the assert_redaction helper"            # T007
Task: "Create tests/fixtures/phone_corpus.log with 50+ planted and look-alike lines"  # T012

# After both land, the test bodies are appended to one file, so they are sequential:
#   T008 -> T009 -> T010 -> T011 -> T013
```

## Parallel Example: across US1 and US2

```bash
# Once Phase 2 is complete the two halves of this feature share no file:
Developer A: T007-T018  (src/logredact/redact.py, tests/test_phone.py)
Developer B: T019-T033  (src/logredact/cli.py,    tests/test_out_dir.py)
# Only src/logredact/cli.py's `description` string (T017) crosses the line — one line, in US1.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup — **capture the SC-013 golden file before touching `src/`**
2. Phase 3: US1 — the phone category
3. **STOP and VALIDATE**: `printf 'call +14155552671 now\n' | PYTHONPATH=src python3 -m logredact`
   gives `call [PHONE] now`; `python3 -m pytest tests/test_redact.py tests/test_cli.py` is green
   with no amendment
4. Ship if ready — US1 alone is a complete, useful change to a shipped tool

Phase 2 is not needed for the MVP: it blocks only the output-folder half.

### Incremental Delivery

1. Setup → baseline captured
2. **+ US1** → phone numbers redacted → validate → ship (MVP)
3. **+ Phase 2 + US2** → `--out-dir` writes one redacted file per operand → validate → ship
4. **+ US3** → the tally gains its fourth field → validate → ship
5. **+ US4** → every failure path names what went wrong and exits 2 → validate → ship
6. **+ Polish** → preservation demonstrated, coverage gate closed, performance criteria measured

Each step leaves the suite green. Note that US3 is the one step that edits existing feature-001
assertions; that edit list is itself the evidence for SC-012.

### Parallel Team Strategy

1. One developer does Phase 1 and Phase 2 (small, strictly ordered, and blocking)
2. Then split by module, because the two halves share no file:
   - Developer A: US1 then US3 (`redact.py`, `tests/test_phone.py`, the tally f-string)
   - Developer B: US2 then US4 (`cli.py`, `tests/test_out_dir.py`)
3. Coordinate once, on `src/logredact/cli.py`: T017 (one `description` line, US1) and T040 (the
   tally f-string, US3) land in the same file Developer B is working in
4. Polish is shared, with T057/T060/T064 taken in parallel

---

## Notes

- **The ordering in Phase 1 is a real constraint, not bookkeeping.** T003 captures bytes that no
  longer exist once T014 lands.
- **T053 carries an open question for the spec owner**, reproduced from plan.md's Post-Phase 1
  finding and research R-107: the per-operand collision re-check is behaviour no acceptance
  scenario describes. It closes a silent-data-loss gap (`--out-dir clean a.log clean/a.log`). If
  the owner prefers to leave the gap open, skip T053 and record that decision.
- `[P]` tasks touch different files and have no dependency on one another.
- `[Story]` labels map each task to a user story for traceability; Setup, Foundational, and Polish
  tasks carry no story label by design.
- Every test task names the requirement identifiers it must cite, because
  `tests/test_requirement_coverage.py` (T060) fails the suite if any identifier loses its last
  citing test — so citing the identifier in the test name or a docstring is part of the task, not
  a nicety.
- Commit after each task or logical group; stop at any checkpoint to validate a story
  independently.
- No runtime module is added and no file is removed. `pyproject.toml` stays
  pytest-configuration-only, and the one new import (`contextlib`, T030) is stdlib, so
  `tests/test_stdlib_only.py` needs no change.
