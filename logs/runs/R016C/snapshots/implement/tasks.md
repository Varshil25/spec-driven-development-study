---

description: "Task list for Phone Redaction and Output Folder"
---

# Tasks: Phone Redaction and Output Folder

**Input**: Design documents from `/specs/002-phone-redaction-out-dir/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md),
[contracts/redaction-rules.md](./contracts/redaction-rules.md), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED and written before implementation. Tests are not optional for this feature —
SC-002 demands an automated test naming each of FR-001…FR-021, SC-003 demands one per edge case, and
constitution Principle III makes a requirement without a test incomplete work.

**Organization**: Tasks are grouped by user story. This feature amends a **working** tool, so every
phase ends with the full suite green: nothing here may break a feature 001 behaviour.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project, unchanged from feature 001: package under `src/logredact/`, tests under `tests/`, run
as `python -m logredact` with `src/` on `PYTHONPATH`, plain `pytest` from the repository root with no
configuration file. Paths below are relative to the repository root.

Only two source files change: `src/logredact/redact.py` and `src/logredact/cli.py`. No new module,
class, or runtime import (plan.md "Structure Decision", constitution Principle IV).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the regression baseline before anything is edited. There is nothing to
scaffold — the project, its test harness (`tests/conftest.py`) and its tooling already exist.

- [X] T001 Run `python3 -m pytest -q` from the repository root and confirm the pre-change suite is green; record the pass count as the SC-004 regression baseline against which every later checkpoint is compared
- [X] T002 [P] Confirm no existing artifact contains a `+` followed by 8 or more digits — `grep -rnE '\+[0-9]{8}' tests/ src/ specs/001-logredact-cli/` must report nothing — so the only feature-001 expectations this work changes are the summary string and the tally arity (plan.md "Verified" note under Project Structure)
- [X] T003 [P] Capture the current tool's output for the quickstart V2 corpus to a scratch path outside the repository: `printf 'user jane@example.com from 10.0.0.7\npaid with 4111 1111 1111 1111\nhost 999.1.1.1 unreachable\n123 1.2.3.4\n' | PYTHONPATH=src python3 -m logredact > /tmp/logredact-baseline-v2.out` — the reference for the byte-identity diff required by SC-006 and quickstart V2's "stronger form"

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Widen the tally from three counters to four. This changes `redact_line`'s return arity,
which both the phone category (US1) and the four-field summary (US3) depend on, and which US2's edits
to the same `_run` loop must be written against. `phones` stays `0` throughout this phase — no
recognition behaviour changes, so the suite must stay green on the T001 baseline.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Change the tally to four elements in `src/logredact/redact.py`: initialise `phones = 0` alongside `emails = ips = cards = 0` in `redact_line`, return `"".join(fragments), (emails, ips, cards, phones)`, and update the annotation to `tuple[str, tuple[int, int, int, int]]` and the docstring to `(emails, ips, cards, phones)` — the order is fixed as the summary's field order (data-model.md "Derived function signatures"; research R3). Do **not** touch `COMBINED` or `_PLACEHOLDER` yet
- [X] T005 Accumulate the fourth counter in `src/logredact/cli.py` `_run`: unpack `text, (line_emails, line_ips, line_cards, line_phones) = redact_line(line)`, extend the initialisation to `emails = ips = cards = phones = 0`, and add `phones += line_phones`. Leave the summary write string unchanged — US3 owns it
- [X] T006 [P] Update the three-tuple assertions in `tests/test_redact_line.py` to four elements, appending ` 0` or a fourth name and changing nothing asserted: the `tally` helper docstring (line 18), each `== (1, 0, 0)` / `(0, 1, 0)` / `(0, 0, 0)` / `(0, 0, 1)` / `(2, 2, 1)` / `(1, 1, 0)` / `(1, 1, 1)` / `(0, 1, 0)` / `(2, 1, 2)` comparison, the two `text, (emails, ips, cards) = redact_line(...)` unpackings (lines 198, 302), and the contract-shape assertion `len(counts) == 3` → `len(counts) == 4` (line 287)
- [X] T007 [P] Update the unpacking at `tests/test_luhn.py` line 62 to `text, (emails, ips, cards, phones) = redact_line(digits)`
- [X] T008 [P] Update the assertion at `tests/test_performance.py` line 91 from `counts == (1, 1, 0)` to `counts == (1, 1, 0, 0)`

**Checkpoint**: `python3 -m pytest` green at the T001 baseline with a four-element tally whose fourth
counter is always `0`. User story implementation can now begin.

---

## Phase 3: User Story 1 - Redact international phone numbers (Priority: P1) 🎯 MVP

**Goal**: A `+` followed by 8–15 digits becomes `[PHONE]`, every occurrence on a line, with email
winning at an equal start offset and nothing else about the tool's output changing.

**Independent Test**: Pipe text containing international phone numbers, `+`-prefixed near-miss digit
runs and ordinary text into `python3 -m logredact` with no file arguments and no flags; confirm each
phone number became `[PHONE]`, no near-miss value was altered, and everything else is byte-identical
(quickstart V1, V2).

**Increment note**: shipping this story alone leaves the `--count` summary at three fields. That is
the documented story boundary — spec.md states US1 is complete and correct without US3 — and the
suite stays green because no existing `--count` test input contains a phone number (T002).

### Tests for User Story 1

> Write these tests FIRST and confirm they FAIL before T014–T016.

- [X] T009 [US1] Create `tests/test_phone.py` with end-to-end grammar and boundary tests naming FR-001, FR-002 and FR-003, one per row of the contract table in `contracts/redaction-rules.md`: `+14155552671` → `[PHONE]`; `+442071838750` → `[PHONE]`; `+12345678` → `[PHONE]` (8 digits, **lower boundary inclusive**); `+123456789012345` → `[PHONE]` (15 digits, **upper boundary inclusive**); `+012345678` → `[PHONE]` (leading zeros are digits); `ext +1234567` unchanged (7 digits, below the range); `ref +1234567890123456` unchanged (16 digits — assert `[PHONE]` appears nowhere, so **no fragment** of the run is redacted); `+1234567890123456789012` unchanged (22 digits); `dial 14155552671 please` unchanged (no `+`); `+ 14155552671` unchanged (run broken by a space); `+1 415 555 2671` unchanged (run broken; the parts then fail the card length rule)
- [X] T010 [US1] Add boundary-adjacency and precedence tests to `tests/test_phone.py` naming FR-004 (same file as T009, so run after it): `call +14155552671.` → `call [PHONE].`; `+12345678a` → `[PHONE]a`; `(+12345678)` → `([PHONE])`; `tel:+14155552671` → `tel:[PHONE]` (no leading guard); `++12345678` → `+[PHONE]`; `+1234567 +12345678` → `+1234567 [PHONE]`; `uk +442071838750 us +14155552671` → `uk [PHONE] us [PHONE]` (every occurrence, not only the first); a line that is exactly one phone number → exactly `[PHONE]` with its terminator preserved; and the three US1 regression scenarios `user jane@example.com from 10.0.0.7` → `user [EMAIL] from [IP]` and `paid with 4111 1111 1111 1111` → `paid with [CARD]` naming FR-005
- [X] T011 [P] [US1] Add unit-level phone and cross-category cases to `tests/test_redact_line.py`, beside the existing FR-015 precedence tests, naming FR-001, FR-004 and FR-005 and asserting the full `(str, 4-tuple)` contract: `+14155552671@example.com` → `("[EMAIL]", (1, 0, 0, 0))` (equal start offset, email listed first — load-bearing); `+378282246310005` → `("[PHONE]", (0, 0, 0, 1))` (phone starts one character earlier than the Luhn-valid card candidate — a deliberate, documented change to today's output); `+4111111111111111` → `("+[CARD]", (0, 0, 1, 0))` (16 digits, no phone candidate exists); `+1.2.3.4` → `("+[IP]", (0, 1, 0, 0))`; `a@b.io,+442071838750,1.2.3.4` → `("[EMAIL],[PHONE],[IP]", (1, 1, 0, 1))` (both commas preserved); `4111 1111 1111 1111 +14155552671` → `("[CARD] [PHONE]", (0, 0, 1, 1))`; `+14155552671,+442071838750` → `("[PHONE],[PHONE]", (0, 0, 0, 2))`
- [X] T012 [P] [US1] Add near-miss fidelity tests to `tests/test_fidelity.py` naming FR-005 and SC-006, using the existing `both_paths` helper so both the stdin and the file path are covered: a payload of `+1234567`, `+1234567890123456`, `14155552671`, `+ 14155552671` and `+1 415 555 2671` is reproduced byte-for-byte; and the quickstart V2 corpus (`user jane@example.com from 10.0.0.7`, `paid with 4111 1111 1111 1111`, `host 999.1.1.1 unreachable`, `123 1.2.3.4`) still produces `user [EMAIL] from [IP]`, `paid with [CARD]`, `host 999.1.1.1 unreachable`, `123 [IP]`
- [X] T013 [US1] Add the whole-surface assertions to `tests/test_phone.py` (same file as T009 and T010): every US1 invocation in the file exits 0 and leaves stderr empty, and the combined US1 corpus piped in with no file arguments and no flags produces exactly the expected stdout bytes — so the story's independent test covers the whole surface US1 owns, with the tally left to US3 (spec US1 Independent Test)

### Implementation for User Story 1

- [X] T014 [US1] Add the phone pattern to `src/logredact/redact.py`: `PHONE = r"\+\d{8,15}(?!\d)"`, with a comment recording that the 8–15 range lives in the quantifier (FR-002), that the trailing `(?!\d)` is the over-long rule (FR-003) — without it a 16-digit run would emit `[PHONE]6`, redacting a fragment — and that **no leading guard** is added deliberately, since FR-002 conditions the match on the `+` and what follows it only (research R1)
- [X] T015 [US1] Wire the category into the scan in `src/logredact/redact.py`: append `|(?P<phone>{PHONE})` to `COMBINED` after `card`; extend the existing load-bearing-order comment to state that **`email` must precede `phone`** because both can begin at the same `+` and FR-004 requires email to win, and that `phone`'s position relative to `ip` and `card` is behaviourally inert (research R2); add `"phone": "[PHONE]"` to `_PLACEHOLDER`; and replace the `else: cards += 1` dispatch with `elif kind == "card": cards += 1` / `else: phones += 1`. Add no validation branch — a phone candidate has no rejection path
- [X] T016 [US1] Update the three stale three-category descriptions: the module docstring of `src/logredact/redact.py` (point its normative reference at `specs/002-phone-redaction-out-dir/contracts/redaction-rules.md`), the docstring of `src/logredact/__init__.py`, and the `description=` string in `_build_parser` in `src/logredact/cli.py` so `--help` names phone numbers and `[PHONE]`

**Checkpoint**: Phone redaction fully functional and independently testable. `python3 -m pytest`
green — T009–T012 pass, and every feature 001 test still passes unchanged.

---

## Phase 4: User Story 2 - Write redacted output to a folder, one file per input (Priority: P2)

**Goal**: `--out-dir DIR` writes each `FILE`'s redacted lines to `DIR/<basename>` instead of standard
output, creating `DIR` and its missing parents, replacing any file of that name, and reporting
`wrote N files` on standard output when every operand has been processed.

**Independent Test**: Create two readable files with known sensitive content, run the tool with both
names and `--out-dir` pointing at a folder that does not yet exist; confirm the folder was created,
holds exactly two files named after the inputs with the correct redacted content, stdout is exactly
`wrote 2 files`, and the input files are unmodified (quickstart V5).

**Independence**: depends only on Phase 2. It needs nothing from US1 — with US1 unbuilt these tests
still pass, because their fixtures use email and IPv4 content.

### Tests for User Story 2

> Write these tests FIRST and confirm they FAIL before T021–T026.

- [X] T017 [P] [US2] Create `tests/test_out_dir.py` with the happy-path tests naming FR-008, FR-009, FR-010, FR-011, FR-012, FR-013, FR-019, FR-020 and FR-021, using `tmp_path`: contract worked example 3 (`app.log` = `user jane@example.com`, `web.log` = `GET / from 10.0.0.7` → `clean/app.log` = `user [EMAIL]`, `clean/web.log` = `GET / from [IP]`, stdout exactly `b"wrote 2 files\n"`, stderr empty, exit 0); missing parents created (`out/deep/nested`); basename only (`logs/app.log` → `clean/app.log`, stdout `wrote 1 files`); an existing target file fully replaced, retaining **none** of its previous content; an existing `DIR` used as-is with unrelated files in it untouched; an empty input file producing a 0-byte output and `wrote 1 files` — literally `files`, **not pluralised**, for every N; stdout carrying **only** the status line and no redacted log text; `--out-dir` accepted before, among and after the operands; input files byte-unchanged (compare checksums before and after); and no `wrote N files` line when `--out-dir` is absent
- [X] T018 [US2] Add the two multiplicity cases and the SC-008 mode-equivalence check to `tests/test_out_dir.py` (same file as T017): two operands sharing a basename (`a/app.log b/app.log`) leave one `clean/app.log` holding the redacted **second** input while stdout reports `wrote 2 files` — one write per operand; the same file named twice behaves identically; and for a successful multi-file run the concatenation of the output files in operand order is byte-identical to the stdout of the same run without `--out-dir`
- [X] T019 [P] [US2] Create `tests/test_out_dir_errors.py` with the failure-path tests naming FR-015, FR-016, FR-017 and FR-018, each asserting exit status 2, a stderr diagnostic containing **both** the offending path and a non-empty reason (match on the path plus a non-empty remainder, not exact OS wording), **no** `wrote N files` on stdout, and — when `--count` is added to the same invocation — **no** summary line: an unreadable second operand (`clean/app.log` **is** present and kept, `clean/nope.log` was never created); `--out-dir` with zero operands (stderr exactly `logredact: --out-dir requires at least one FILE`, the directory **not** created, and standard input not read — pass input that would otherwise be echoed); `--out-dir` naming an existing **regular file**; an output name colliding with an existing **subdirectory** (`clean3/app.log/`); and an over-long `--out-dir` path component (`ENAMETOOLONG`). These four obstacles are file-type or path based, so they fail for root as well as an unprivileged user — no test may be skipped (constitution gate 2, research R12)
- [X] T020 [US2] Add the permission-bit case to `tests/test_out_dir_errors.py` naming FR-017 (same file as T019, kept separate from its privilege-independent set): `chmod 0o500` the destination directory, probe it first by attempting a write into it from the test process, then assert the FR-017 failure contract if the probe failed or the success contract if it succeeded — the probe pattern feature 001 already uses, so the test runs and asserts on every platform including as uid 0 rather than being skipped (constitution gate 2, research R12)
- [X] T021 [P] [US2] Add output-file byte fidelity tests to `tests/test_fidelity.py` naming FR-014: a payload containing `plain\r\n`, the invalid UTF-8 bytes `\xff\xfe`, a tab-and-trailing-space line and a final line with **no** newline, written through `--out-dir`, produces an output file byte-identical to the input **and** byte-identical to what the same run without `--out-dir` sends to stdout (quickstart V9)

### Implementation for User Story 2

> All five tasks edit `src/logredact/cli.py`, so they are sequential — no `[P]`.

- [X] T022 [US2] Add the option in `_build_parser` in `src/logredact/cli.py`: `parser.add_argument("--out-dir", metavar="DIR", default=None, help="write each FILE's redacted lines to DIR/<name> instead of standard output")`. Keep the existing `parse_intermixed_args` call untouched — a value-taking store option is compatible with it, which is what satisfies FR-019 (research R4)
- [X] T023 [US2] Reject zero operands at the very top of `_run` in `src/logredact/cli.py`, before `makedirs` and before any stream is reconfigured or read: if `args.out_dir is not None and not args.files`, write exactly `logredact: --out-dir requires at least one FILE\n` to stderr and `return 2`. Written directly rather than via `parser.error()` so the text is the specified sentence rather than a usage block (FR-018, research R8)
- [X] T024 [US2] Create the destination once in `_run` in `src/logredact/cli.py`, after T023's check and before the first input is opened: `os.makedirs(args.out_dir, exist_ok=True)` inside a `try`, with `except OSError as exc:` writing `logredact: cannot write '{args.out_dir}': {exc.strerror or exc}\n` to stderr and returning 2. `exist_ok=True` suppresses the collision only when the existing path is a directory, so "exists but is not a folder" fails by construction (FR-010, FR-017, research R6)
- [X] T025 [US2] Add the per-operand output stream to the loop in `_run` in `src/logredact/cli.py`: open the input **first**, then — only if that succeeded — open `os.path.join(args.out_dir, os.path.basename(name))` with mode `"w"` and the **same** `_STREAM_KWARGS` (`encoding="utf-8"`, `errors="surrogateescape"`, `newline=""`), which is what makes each output file byte-identical to the stdout path (FR-014, research R9); write each redacted line to that stream instead of `sys.stdout`; close it in the `finally` before the next input opens, so never more than one input and one output are open; and increment a `written` counter once per operand that completed. The input-before-output ordering is what guarantees no output file exists for an unreadable input (FR-016, research R7)
- [X] T026 [US2] Split the failure handling in `_run` in `src/logredact/cli.py` so the diagnostic is attributed by the operation that raised, never inferred: the input `open` and the read loop keep today's `logredact: cannot read '<operand>': <reason>` (FR-015), while the output `open`, each `write` and the close report `logredact: cannot write '<joined path>': <reason>` (FR-017) — both returning 2 before the summary block. Keep the `except BrokenPipeError: raise` clause **ahead** of `except OSError`, or a closed downstream pipe is misreported
- [X] T027 [US2] Emit the status line in `_run` in `src/logredact/cli.py` after the loop completes with no failure: if `args.out_dir is not None`, `sys.stdout.write(f"wrote {written} files\n")` — literally `files` for every N — then move the existing `sys.stdout.flush()` out of the `if args.count:` block to just before it, so the status line is flushed in both modes and the tally always follows it (FR-012, FR-013, research R10)

**Checkpoint**: `--out-dir` fully functional and independently testable; US1 and US2 both work.
`python3 -m pytest` green.

---

## Phase 5: User Story 3 - See phone numbers in the redaction tally (Priority: P3)

**Goal**: With `--count`, the summary on standard error becomes `emails=N ips=N cards=N phones=N`,
with `phones` appended as a fourth field so consumers parsing the first three positionally keep
working.

**Independent Test**: Run the tool with `--count` over input with a known number of each of the four
categories, capturing stdout and stderr separately; confirm exactly one summary line appears on
stderr in the four-field form and that each field matches the number of corresponding placeholders in
the output (quickstart V4).

**Dependencies beyond Phase 2**: US3's scenarios assert non-zero `phones` values, so they need **US1**
to pass as written. Scenario 5 (`--count` with `--out-dir`) additionally needs **US2**; it is isolated
in T029 so the rest of the story can land without it.

### Tests for User Story 3

> Write these tests FIRST and confirm they FAIL before T031.

- [X] T028 [US3] Update and extend `tests/test_count.py` for the four-field summary, naming FR-006 and FR-007: append ` phones=0` to each of the existing expected summary strings (lines 18, 26, 34, 44, 55, 100, 120, 130, 158, 166, 174) and to the docstrings that quote the format, changing nothing else about those cases; then add `a@b.io +442071838750` → stdout `[EMAIL] [PHONE]\n`, stderr exactly `emails=1 ips=0 cards=0 phones=1\n`; input with nothing sensitive → `emails=0 ips=0 cards=0 phones=0\n` and exit 0; the same phone three times → `phones=3` (every individual replacement is counted, not distinct values); several files named together → exactly **one** summary line totalling all four categories across all of them; `+14155552671@example.com` → `emails=1 ips=0 cards=0 phones=0`; `+378282246310005` → `emails=0 ips=0 cards=0 phones=1`; `+4111111111111111` → `emails=0 ips=0 cards=1 phones=0`; the quickstart V3 eight-line corpus → `emails=1 ips=0 cards=1 phones=4`; and with no `--count`, stderr receives nothing
- [X] T029 [US3] Add the combined-option cases to `tests/test_count.py` (same file as T028; also requires US2 complete) naming FR-019 and covering US3 scenario 5: `--count --out-dir clean a.log b.log` over two readable files puts the redacted copies in the folder, makes stdout exactly `wrote 2 files\n` and stderr exactly one four-field summary totalling both files, in that order; and `a.log --out-dir clean --count b.log` — options before, among and after the operands — behaves identically
- [X] T030 [P] [US3] Update `tests/test_performance.py` for the four-field summary: change the expected stderr at line 37 to `f"emails={LINE_COUNT} ips={LINE_COUNT} cards={LINE_COUNT} phones={LINE_COUNT}\n"`, add `tel +14155552671` to the dense `LINE` constant so each line carries one of each of the four categories, and assert `result.stdout.count(b"[PHONE]") == LINE_COUNT`

### Implementation for User Story 3

- [X] T031 [US3] Change the summary write in `_run` in `src/logredact/cli.py` to `sys.stderr.write(f"emails={emails} ips={ips} cards={cards} phones={phones}\n")` — `phones` **appended** as a fourth field, the first three keeping their names, order and meaning; still exactly one line, still on stderr and never stdout, still after the single `sys.stdout.flush()`, still suppressed by the early `return 2` on any failed run (FR-006, FR-007)

**Checkpoint**: All three user stories independently functional. `python3 -m pytest` green.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verify the success criteria and the constitution's quality gates across all three
stories.

- [X] T032 [P] Add the `--out-dir` timing case to `tests/test_performance.py` naming SC-010: a 100,000-line generated log run as `--count --out-dir <tmp>` completes in under `BUDGET_SECONDS`, exits 0, puts exactly `wrote 1 files\n` on stdout and one four-field summary on stderr, and keeps the `tracemalloc` peak flat — memory must not grow with line count **or** operand count
- [X] T033 [P] Run every quickstart validation scenario V1–V12 in [quickstart.md](./quickstart.md) from the repository root with `PYTHONPATH=src` and confirm each stated expectation, including V9's two `cmp` byte-identity checks and V2's diff against the `/tmp/logredact-baseline-v2.out` baseline captured in T003
- [X] T034 [P] Audit SC-002: walk the requirement coverage map in [contracts/cli.md](./contracts/cli.md) and confirm each of FR-001…FR-021 is named in the test name, docstring or a comment of at least one test in the file the map assigns it to; fix any gap by naming the requirement in the covering test
- [X] T035 [P] Audit SC-003: confirm every bullet in spec.md's Edge Cases section — all eleven under "Phone recognition" and all ten under "Output folder" — has a corresponding automated test, and add any that is missing to `tests/test_phone.py`, `tests/test_out_dir.py` or `tests/test_out_dir_errors.py`
- [X] T036 [P] Verify the constitution's quality gates against the diff: no new import outside the standard library anywhere in `src/` (gate 4 — the change should add **no** import at all); no `skip`, `skipif` or `xfail` anywhere in `tests/` (gate 2); and no module, class, or configuration option added beyond the four-element tuple and the second `OSError` handler, each already justified in plan.md (gate 5)
- [X] T037 Run the full suite `python3 -m pytest` from the repository root and confirm it is green with nothing skipped and no fewer passes than the T001 baseline; then confirm SC-004 by reviewing `git diff` of the pre-existing test files — the only changes to them may be the four-field summary string and the fourth element of `redact_line`'s tally tuple, with the arity edits recorded as the research R3 open item for the spec owner

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately. T003 **must** run before any source edit, since it captures the pre-change tool's output
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all three user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 only
- **User Story 2 (Phase 4)**: Depends on Phase 2 only — fully independent of US1
- **User Story 3 (Phase 5)**: Depends on Phase 2, and on **US1** for its non-zero `phones` assertions; T029 alone also depends on **US2**
- **Polish (Phase 6)**: T032 depends on US2 and US3; T033–T037 depend on all three stories

### User Story Dependencies

- **US1 (P1)**: No dependency on another story. Delivers the MVP on its own
- **US2 (P2)**: No dependency on another story. Its fixtures use email and IPv4 content, so it passes with US1 unbuilt
- **US3 (P3)**: Not fully independent by design — spec.md frames it as completing the reporting of US1's redaction, and its scenarios assert `phones=1`/`phones=3`/`phones=4`. The format change itself (T031) is independent; the assertions are not

### Within Each User Story

- Tests are written first and must FAIL before the implementation tasks of that phase
- `redact.py` before `cli.py` where both change (the engine's contract is the CLI's input)
- Pattern (T014) before wiring it into `COMBINED` and the dispatch (T015)
- In US2: parser option → zero-operand check → `makedirs` → per-operand streams → failure attribution → status line. This is also the runtime order, so each task can be exercised as it lands
- Each story ends with the full suite green before the next begins

### File-Conflict Notes

Tasks touching the same file are never both marked `[P]`:

- `src/logredact/cli.py`: T005, T016, T022–T027, T031 — all sequential
- `src/logredact/redact.py`: T004, T014, T015, T016 — all sequential
- `tests/test_redact_line.py`: T006 (Phase 2), T011 (Phase 3)
- `tests/test_fidelity.py`: T012 (Phase 3), T021 (Phase 4)
- `tests/test_performance.py`: T008 (Phase 2), T030 (Phase 5), T032 (Phase 6)
- `tests/test_phone.py`: T009, T010, T013 — sequential within Phase 3
- `tests/test_out_dir.py`: T017, T018 — sequential
- `tests/test_out_dir_errors.py`: T019, T020 — sequential
- `tests/test_count.py`: T028, T029 — sequential
- `tests/test_errors.py`, `tests/test_stdin.py`, `tests/test_files.py`, `tests/conftest.py`: **unchanged** by this feature. `test_errors.py`'s summary assertions are `b"emails=" not in ...`, which still hold

### Parallel Opportunities

- Phase 1: T002 and T003 together
- Phase 2: T006, T007 and T008 together, once T004 and T005 are done
- Phase 3: T011 and T012 together, alongside the T009 → T010 → T013 chain
- Phase 4: T017, T019 and T021 together (T018 follows T017, T020 follows T019)
- Phase 5: T030 alongside the T028 → T029 chain
- Phase 6: T032, T033, T034, T035 and T036 together; T037 last
- Across stories: once Phase 2 is checkpointed, US1 and US2 can be built by two people in parallel — they share no file except `cli.py`, where US1's only edit is the one-line parser description (T016)

---

## Parallel Example: User Story 1

```bash
# After Phase 2's checkpoint, launch the two independent test files together:
Task: "Add unit-level phone and cross-category cases to tests/test_redact_line.py"   # T011
Task: "Add near-miss fidelity tests to tests/test_fidelity.py"                       # T012

# Meanwhile, the tests/test_phone.py chain runs in order: T009 -> T010 -> T013
# Then implementation, in order: T014 -> T015 -> T016
```

## Parallel Example: User Story 2

```bash
# Three different test files, no shared state:
Task: "Create tests/test_out_dir.py happy-path tests"              # T017
Task: "Create tests/test_out_dir_errors.py failure-path tests"     # T019
Task: "Add output-file byte fidelity tests to tests/test_fidelity.py"  # T021

# Implementation is a single-file sequence: T022 -> T023 -> T024 -> T025 -> T026 -> T027
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup — baseline recorded (T001–T003)
2. Phase 2: Foundational — four-element tally, suite still green (T004–T008)
3. Phase 3: User Story 1 — phone redaction (T009–T016)
4. **STOP and VALIDATE**: run quickstart V1 and V2; confirm every phone number redacted, every
   near-miss untouched, and all feature 001 tests passing
5. Shippable: the live privacy gap is closed. The `--count` summary still has three fields

### Incremental Delivery

1. Setup + Foundational → four-counter tally in place, zero behaviour change
2. **+ US1** → phone numbers redacted → validate V1, V2, V3 → ship (MVP)
3. **+ US2** → per-file output folder → validate V5, V6, V8, V9, V10 → ship
4. **+ US3** → four-field tally → validate V3, V4, V7 → ship
5. **+ Polish** → V11, V12 and the SC-002/SC-003/gate audits

Each step leaves the suite green and breaks no earlier step.

### Parallel Team Strategy

1. One person does Phase 1 and Phase 2 — they are small and serialising
2. After the Phase 2 checkpoint:
   - Developer A: User Story 1 (`redact.py`, `test_phone.py`, `test_redact_line.py`)
   - Developer B: User Story 2 (`cli.py`, `test_out_dir*.py`)
   - A's only `cli.py` edit is T016's one-line description; coordinate that single line with B
3. US3 lands after US1 (and after US2 for T029) — it is a one-line change plus test updates, best
   done by whoever finished first

---

## Notes

- `[P]` tasks = different files, no dependencies
- `[Story]` labels map tasks to US1/US2/US3 for traceability
- This feature amends a **working** tool: every phase ends with `python3 -m pytest` green, and any
  input with no `+`-prefixed 8–15 digit run must stay byte-identical to the current output (FR-005,
  SC-006)
- Two known consequences are recorded in plan.md and must not be "fixed" silently: `+378282246310005`
  changes category from `+[CARD]` to `[PHONE]` (still fully redacted), and a mid-stream I/O error
  after both opens succeed may leave a partial output file (research R7) — nothing is built for the
  latter because it cannot be covered by a test
- `wrote 1 files` is correct and deliberate; do not pluralise it
- Commit after each task or logical group; stop at any checkpoint to validate a story independently
