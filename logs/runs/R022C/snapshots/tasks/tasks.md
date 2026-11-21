---

description: "Task list for Phone Redaction and Output Folder"
---

# Tasks: Phone Redaction and Output Folder

**Input**: Design documents from `/specs/002-phone-redact-out-dir/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md),
[quickstart.md](./quickstart.md)

**Tests**: Test tasks are **included and mandatory** here. They are not the usual optional
extra: SC-004 requires every one of FR-001…FR-027 to be covered by an automated test that names
the requirement it verifies, SC-006 requires each new failure mode to assert message *and* exit
status, and Constitution Principle III makes the requirement → test mapping a merge gate. The
test ids below are taken verbatim from the [quickstart requirement → test map](./quickstart.md#requirement--test-map-sc-004);
create them under those names so the map stays auditable.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and
demonstrated on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project, unchanged from `001` (plan.md "Project Structure"). Paths are relative to the
repository root `/root/sdd-study/runs/R022`:

- Source: `src/logredact/` — `redact.py`, `__main__.py`, `__init__.py`
- Tests: `tests/` — `conftest.py`, `test_redact.py`, `test_cli.py`, `test_corpus.py`, plus the two
  new files `test_phone.py` and `test_out_dir.py`
- Bare `pytest` from the repository root works because `pyproject.toml` sets `pythonpath = ["src"]`

**This feature creates no new source module** and adds no dependency (plan.md "Structure
Decision", Constitution Principle I and IV).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the measured baseline the preservation guarantees (FR-027, SC-005) are
judged against. There is no project to initialise — the package, test suite, and `pyproject.toml`
already exist and are not changed by this feature.

- [ ] T001 Record the pre-change test baseline: run `python3 -m pytest -q` from the repository root and write the exact result into the task notes; it must read `31 passed, 1 skipped` (the skip is the pre-existing permission-denied test, skipped when the suite runs as root). This number is what SC-005 is measured against (research.md "Pattern verification")
- [ ] T002 [P] Confirm the Constitution merge-gate invariants before any edit, in `pyproject.toml`: `requires-python = ">=3.11"` and `dependencies = []` are present, and no module under `src/logredact/` imports a third-party package (current imports are `re`, `io`, `signal`, `sys`, `dataclasses`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Widen the counts carrier and convert the CLI's accumulators to it. Both user-story
phases that follow build on this, and every step here is **behaviour-neutral**: the tally line
still reads `emails=N ips=N cards=N` at the end of this phase, and no new figure is produced yet.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 Add `phones: int = 0` as the **last** field of the `Counts` frozen dataclass in `src/logredact/redact.py`, keeping the existing field order `emails, ips, cards, phones` and keeping every field defaulted to `0`, so existing keyword construction such as `Counts(emails=2, ips=1, cards=2)` stays valid and keeps asserting the same fact (data-model.md R4.8, SC-005). No producer sets it in this phase
- [ ] T004 Add `__add__(self, other: "Counts") -> "Counts"` to `Counts` in `src/logredact/redact.py`, returning the field-wise sum of all four fields. Do **not** add `__radd__`, `__sub__`, mutation, or a `total` property — none has a caller (research.md D-103, data-model.md §4)
- [ ] T005 Change `_copy_redacted(source, destination)` in `src/logredact/__main__.py` to return `Counts` instead of `tuple[int, int, int]`: accumulate with `total = total + counts` from an explicit `total = Counts()`, and update its docstring's "Returns the (emails, ips, cards) totals" line (data-model.md "Engine interface")
- [ ] T006 Update `main()` in `src/logredact/__main__.py` to carry one `Counts` accumulator across sources via `__add__` in place of the three `emails`/`ips`/`cards` locals, for both the FILE-list branch and the stdin branch, while keeping the stderr tally line byte-identical as `emails={…} ips={…} cards={…}` — the four-figure form arrives in Phase 5 (US3)
- [ ] T007 Run `python3 -m pytest -q` from the repository root and confirm the result is identical to T001's baseline (`31 passed, 1 skipped`); this phase is a refactor and must change no observable behaviour

**Checkpoint**: `Counts` carries four fields and the CLI sums it; US1 and US2 can now proceed independently

---

## Phase 3: User Story 1 - Redact international phone numbers (Priority: P1) 🎯 MVP

**Goal**: A `+` immediately followed by 8-15 decimal digits is replaced by the literal `[PHONE]`,
alongside the three rules the tool already applies, with the `+` consumed by the placeholder and no
partial replacement of a longer digit run.

**Independent Test**: `echo 'call +14155552671 now' | python3 -m logredact` prints
`call [PHONE] now` with every other character unchanged and exits 0 (spec Story 1 Independent
Test; contract W-1).

### Tests for User Story 1

> **NOTE: Write these tests FIRST and confirm they FAIL (T011) before implementing T012-T015.**
> These are engine-level tests calling `redact_text` directly — no subprocess (quickstart map).

- [ ] T008 [US1] Create `tests/test_phone.py` importing `redact_text` and `Counts` from `logredact.redact`, with `test_fr001_phone_replaced_with_placeholder` (`'call +14155552671 now'` → `'call [PHONE] now'`, spec Scenario 1.1; `'+442071838750 and +14155552671'` → `'[PHONE] and [PHONE]'`, Scenario 1.2), `test_fr002_recognises_plus_then_8_to_15_digits` (`+14155552671` 11 digits and `+442071838750` 12 digits both → `[PHONE]`, plus the exact bounds `'+12345678'` 8 digits → `'[PHONE]'` and `'+123456789012345'` 15 digits → `'[PHONE]'`), and `test_fr003_plus_sign_is_consumed_by_the_placeholder` (asserting `'+'` does **not** appear in the output of `'+14155552671'`) — FR-001, FR-002, FR-003
- [ ] T009 [US1] Add to `tests/test_phone.py`: `test_fr004_sixteen_or_more_digits_never_partially_replaced` — `'ref +1234567890123456'` (a `+` then 16 digits) is returned unchanged, and assert specifically that `'[PHONE]'` does **not** appear in the output, so a corrupted partial such as `[PHONE]67` fails the test (FR-004, spec Scenario 1.4); and `test_fr005_too_few_digits_unchanged_and_preceding_text_unconstrained` — `'ext +1234567'` (7 digits) and `'total 100+25 units'` unchanged, while `'100+14155552671'` → `'100[PHONE]'` and `'++14155552671'` → `'+[PHONE]'` (match starts at the second `+`) and `'+1 415 555 2671'` / `'+1-415-555-2671'` are unchanged (FR-005, spec Scenarios 1.3, 1.5, Edge Cases)
- [ ] T010 [US1] Add to `tests/test_phone.py`: `test_fr006_precedence_email_ipv4_phone_card_and_placeholders_not_reexamined` — `'+12345678@b.io'` → `'[EMAIL]'` (email wins at an equal start, the domain is not left exposed), `'x+12345678@b.io'` → `'[EMAIL]'`, `'jane@example.com+14155552671'` → `'[EMAIL][PHONE]'`, `'+1.2.3.4'` → `'+[IP]'`, `'+4111111111111111'` → `'+[CARD]'` (16 digits so not a phone, Luhn-valid so a card), `'a@b.io 10.0.0.7 4111 1111 1111 1111 +442071838750'` → `'[EMAIL] [IP] [CARD] [PHONE]'` (spec Scenario 1.6), and `'[PHONE] already here'` unchanged with `phones == 0`; and `test_fr009_phones_counts_occurrences_and_zero_when_none` — three occurrences of the same number give `phones == 3`, input with nothing redactable gives `Counts(0, 0, 0, 0)`, and `emails`/`ips`/`cards` keep their existing values on a mixed line (FR-006, FR-009)
- [ ] T011 [US1] Run `python3 -m pytest -q -k phone` and confirm the new tests **fail** because the rule does not exist yet (phone numbers pass through unredacted), not because of an import or syntax error

### Implementation for User Story 1

- [ ] T012 [US1] In `src/logredact/redact.py`, add `PHONE_PLACEHOLDER = "[PHONE]"` beside the three existing placeholder constants (a fixed literal, not configurable — data-model.md R3.1a), and add the pattern constant `_PHONE = r"\+\d{8,15}(?!\d)"` beside `_EMAIL` and `_IPV4`, with a comment recording why each clause is there: `\+` inside the match so the `+` is consumed (FR-003), `\d{8,15}` as FR-002 verbatim, `(?!\d)` so a 16-or-more-digit run is abandoned entirely rather than partially replaced (FR-004), and **no** leading lookbehind because FR-005 requires the preceding character to place no constraint on the match (research.md D-101)
- [ ] T013 [US1] In `src/logredact/redact.py`, rename the compiled constant `EMAIL_OR_IPV4` to `EMAIL_OR_IPV4_OR_PHONE` and add the phone branch **third**: `re.compile(rf"(?P<email>{_EMAIL})|(?P<ip>{_IPV4})|(?P<phone>{_PHONE})")`. Branch order *is* FR-006's email → IPv4 → phone precedence under Python's leftmost-first alternation, so add no arbitration code; update the `.sub(...)` call site in `redact_text` to the new name (research.md D-102, data-model.md R3.8a)
- [ ] T014 [US1] In `redact_text` in `src/logredact/redact.py`, add a `phones` counter and extend the inner `replace(match)` to handle the new group — return `PHONE_PLACEHOLDER` and increment `phones` when `match.group("phone") is not None`, keeping the existing email/IPv4 arms — and pass `phones=phones` to the returned `Counts`. Leave the card pass (Pass B) untouched: phone-before-card follows from pass order, since `re.sub` never rescans its own replacement text (data-model.md R3.10a, R3.17)
- [ ] T015 [US1] [P] Update the docstrings only: in `src/logredact/redact.py` change the module docstring's "the three rule patterns" to four and reference D-101/D-102; in `src/logredact/__init__.py` change the package docstring to mention phone numbers. Leave the `__all__` exports (`Counts`, `redact_text`) unchanged (plan.md change-surface table)
- [ ] T016 [US1] [P] In `tests/test_corpus.py`, add a `KNOWN_PHONES` list of international-format numbers (for example `+14155552671`, `+442071838750`, `+12345678` at the 8-digit bound, `+123456789012345` at the 15-digit bound) and weave them into `SENSITIVE_CORPUS`; extend `test_sc002_no_known_value_survives` so each known phone number is checked for survival in the output the same way emails, IPs, and cards are, keeping the pre-existing 0% leak assertions intact (SC-002)
- [ ] T017 [US1] In `tests/test_corpus.py`, extend `NON_SENSITIVE_CORPUS` with `+` text that must reproduce byte-identically: arithmetic (`total 100+25 units`), a `+` with fewer than 8 digits (`ext +1234567`), a `+` with more than 15 digits (`ref +1234567890123456`), spaced and hyphenated numbers (`+1 415 555 2671`, `+1-415-555-2671`), and version strings whose build metadata is **not** an 8-to-15-digit run (`1.0.0+build.1`, `2.3.4+exp.sha.5114f85`) — a date-stamped build such as `1.0.0+20260101` is redacted by design and must **not** be added to this corpus (SC-003, research.md D-101 "Accepted consequence")
- [ ] T018 [US1] Run `python3 -m pytest -q` from the repository root: the `tests/test_phone.py` and `tests/test_corpus.py` tests pass, and every test that passed at T001 still passes — the tally line is still three figures at this point, which is correct until US3

**Checkpoint**: Phone numbers are redacted on every input source and to stdout; the MVP is deliverable on its own

---

## Phase 4: User Story 2 - Write redacted copies into an output folder (Priority: P2)

**Goal**: `--out-dir DIR` with one or more FILE arguments writes each FILE's redacted lines to
`DIR/{basename(FILE)}` instead of stdout, creating `DIR` and any missing parents, and prints
exactly one `wrote N files` line to stdout.

**Independent Test**: Two files in different directories, `--out-dir` naming a folder that does not
exist: the folder is created, holds one redacted file per input named after the input's own file
name, stdout is exactly `wrote 2 files`, and the exit status is 0 (spec Story 2 Independent Test;
contract W-3).

**Independent of US1**: this story touches only `src/logredact/__main__.py` and needs no phone rule.
This phase covers the **success path only**; the five new failure modes are US4 (Phase 6).

### Tests for User Story 2

> **NOTE: Write these tests FIRST and confirm they FAIL (T023) before implementing T024-T028.**
> These are CLI-contract tests and must go through the real subprocess via the existing `run_cli`
> fixture in `tests/conftest.py` (unchanged), using `tmp_path` for scratch files.

- [ ] T019 [US2] Create `tests/test_out_dir.py` using the `run_cli` fixture and `tmp_path`, with `test_fr011_out_dir_value_taken_literally_in_any_position` (the option works before, between, and after FILE arguments and alongside `--count`; and in `--out-dir --count app.log` the token `--count` is taken **literally** as the folder name — a directory named `--count` is created, no tally is printed, and stderr is empty, contract W-10), `test_fr013_redacted_lines_go_to_files_not_stdout` (stdout contains no redacted line, only the `wrote N files` line), and `test_fr014_output_named_by_basename_only` (input `logs/2026/app.log` with `--out-dir clean` produces `clean/app.log` and **no** `clean/logs/` subtree, contract W-4) — FR-011, FR-013, FR-014
- [ ] T020 [US2] Add to `tests/test_out_dir.py`: `test_fr015_output_file_byte_identical_to_stdout_including_crlf_and_no_final_newline` — write an input containing `a@b.io\r\n\r\nno final newline 10.0.0.7` (no trailing newline), run the tool once to stdout and once with `--out-dir`, and assert the output file's **bytes** equal the stdout bytes exactly (read the file in binary mode; FR-015, quickstart Scenario 2); `test_fr016_creates_dir_with_missing_parents_and_reuses_existing` — a folder path with missing intermediate directories such as `out/2026/clean` is created in full, and a second run into an already-existing folder reuses it and leaves an unrelated pre-existing file in it untouched (FR-016); `test_fr017_existing_output_file_truncated_no_leftover_bytes` — pre-fill `clean/app.log` with 5000 bytes, run, and assert the resulting file size equals exactly the length of the redacted content with no trailing remnant (FR-017)
- [ ] T021 [US2] Add to `tests/test_out_dir.py`: `test_fr018_wrote_n_files_line_counts_files_processed_and_exits_zero` — stdout is exactly `wrote 2 files\n` for two FILE arguments and exactly `wrote 1 files\n` for one (the plural noun is fixed, no pluralisation branch, data-model.md R5.12), the same path given twice still gives `wrote 2 files`, two inputs sharing a basename (`a/app.log` and `b/app.log`) still give `wrote 2 files` with the **second** argument's redacted content surviving in `clean/app.log` (spec Edge Cases), a readable but empty input produces an empty output file that is still counted (spec Story 2 scenario 7), and the exit status is 0; `test_fr021_last_out_dir_value_wins` — with `--out-dir first --out-dir second app.log` the output goes to `second/` and `first/` is never created (FR-021, quickstart Scenario 4); `test_fr022_without_out_dir_output_unchanged_and_no_file_created` — with FILE arguments and no `--out-dir`, redacted lines go to stdout, there is no `wrote N files` line, and no file is created anywhere in `tmp_path` (FR-022)
- [ ] T022 [US2] Add to `tests/test_out_dir.py`: `test_fr007_phone_redacted_for_stdin_files_stdout_and_out_dir` — the same input containing a phone number is redacted identically via stdin→stdout, FILE→stdout, and FILE→`--out-dir` (FR-007). If US1 is not yet complete, use an email and an IPv4 address for the stdout/stdin arms and mark the phone assertion `pytest.mark.xfail(strict=True)` until US1 lands, so the task does not create a cross-story dependency
- [ ] T023 [US2] Run `python3 -m pytest -q -k out_dir` and confirm the new tests **fail** because `--out-dir` is currently rejected as an unrecognised option with exit 2, not because of a fixture or import error

### Implementation for User Story 2

- [ ] T024 [US2] In `src/logredact/__main__.py`, replace the `for token in argv` classification loop with an index-based `while i < len(argv)` loop, because `--out-dir` must consume the *following* token. Keep the existing three arms unchanged in meaning (`--count` in any position; any other token starting with `-` and longer than one character is an unrecognised option with the existing usage message and exit 2; anything else is a FILE path, including a bare `-`) and add an `--out-dir` arm that assigns `out_dir = argv[i + 1]` **verbatim, without inspecting it for an option-like shape**, then advances the index by 2. Assigning on each occurrence is what makes the last value win (FR-011, FR-021, research.md D-104). Do **not** add `--out-dir=DIR` support: that token form must keep falling through to the unrecognised-option arm (data-model.md R6.4)
- [ ] T025 [US2] In `src/logredact/__main__.py`, add `import os` to the import block and, in folder mode only, call `os.makedirs(out_dir, exist_ok=True)` **after** parsing and validation and **before** the first FILE is opened, so an unusable folder fails before any input is read and before any output file exists (FR-016, research.md D-106, D-107). Error handling for this call is T042
- [ ] T026 [US2] In `src/logredact/__main__.py`, inside the FILE loop, compute `out_path = os.path.join(out_dir, os.path.basename(path))` and, in folder mode, open the destination as `open(out_path, "w", encoding="utf-8", newline="", errors="strict")` nested inside the input's `with`, passing it to `_copy_redacted` in place of the stdout wrapper; close it before the next FILE is opened. The three keyword arguments MUST be **the same three the stdout `io.TextIOWrapper` uses** — that identity is the whole of FR-015, and any divergence silently breaks line fidelity. Mode `"w"` truncates on open, which is FR-017 with no explicit truncate call (data-model.md R5.3-R5.8, research.md D-108)
- [ ] T027 [US2] In `src/logredact/__main__.py`, keep creating the stdout `io.TextIOWrapper` in both modes (folder mode still needs it for one line, data-model.md R5.9), ensure **no** redacted line is written to it in folder mode, and ensure stdin is not opened at all in folder mode — the `else` stdin branch must be unreachable when `out_dir` is set (contract "Modes", FR-013)
- [ ] T028 [US2] In `src/logredact/__main__.py`, increment a `written` counter after each output file closes successfully, and after the loop completes write exactly one line `wrote {written} files\n` to the stdout wrapper in folder mode — placed after every `return 2` path so no failing run can reach it — then flush and return 0. No per-file progress output (FR-018, FR-026, research.md D-110, data-model.md R5.10-R5.13)
- [ ] T029 [US2] Run `python3 -m pytest -q`: all of `tests/test_out_dir.py` from T019-T022 passes and the T001 baseline tests still pass

**Checkpoint**: Both US1 and US2 are independently functional; stdout mode is byte-for-byte unchanged

---

## Phase 5: User Story 3 - See phone numbers in the tally (Priority: P3)

**Goal**: With `--count`, the single stderr line becomes `emails=N ips=N cards=N phones=N`, one
tally per run, written after all stdout output.

**Independent Test**: Run with `--count` on input with a known number of phone numbers, capture
stderr separately, and confirm the four figures appear in the specified order with the correct
phone count (spec Story 3 Independent Test; contract W-2).

**Depends on**: Phase 2 and US1 (the `phones` figure needs the rule that produces it). The FR-019
task also needs US2.

### Tests for User Story 3

- [ ] T030 [US3] Update the seven existing tally assertions in `tests/test_cli.py` to the four-figure form — at lines 107 (`expected_tally`), 130, 141, 154, 158, 323, and 345 — appending ` phones=0` to each, since none of those inputs contains a phone number. These seven assertion strings are **the only edits permitted to the pre-existing test files** under SC-005; do not restructure the surrounding tests (quickstart SC-005 row)
- [ ] T031 [US3] Add to `tests/test_cli.py`: `test_fr008_tally_line_has_four_figures_in_order` — `echo 'a@b.io +442071838750' | python3 -m logredact --count` gives stdout `[EMAIL] [PHONE]\n` and stderr exactly `emails=1 ips=0 cards=0 phones=1\n`, with the four figures in that order (FR-008, spec Story 3 scenario 1, contract W-2); `test_fr009_other_three_figures_keep_their_meaning` — input with no redactable values gives `emails=0 ips=0 cards=0 phones=0`, and a mixed line reports each figure independently (FR-009); `test_fr010_tally_after_all_stdout_and_stderr_empty_without_count` — with streams merged the tally line appears after all redacted output, and without `--count` stderr is byte-empty on a successful run (FR-010)
- [ ] T032 [US3] Add to `tests/test_out_dir.py`: `test_fr019_out_dir_with_count_writes_both_lines_in_order` — with `--count --out-dir clean app.log web.log`, stdout is exactly the `wrote 2 files` line and stderr carries exactly one tally covering all files combined, emitted after the stdout line (FR-019, data-model.md R4.9, contract W-5)
- [ ] T033 [US3] Run `python3 -m pytest -q -k "fr008 or fr009 or fr010 or fr019"` and confirm the new assertions fail against the still-three-figure line

### Implementation for User Story 3

- [ ] T034 [US3] In `main()` in `src/logredact/__main__.py`, change the tally write to `sys.stderr.write(f"emails={total.emails} ips={total.ips} cards={total.cards} phones={total.phones}\n")`, keeping its position after the stdout flush so the "after all standard output" rule holds in both modes — in folder mode that means after the `wrote N files` line — and keeping it suppressed entirely when `--count` is absent (FR-008, FR-010, FR-019, data-model.md R4.4a)
- [ ] T035 [US3] Run `python3 -m pytest -q` from the repository root: the four-figure tests pass, the seven updated assertions in `tests/test_cli.py` pass, and nothing else regresses

**Checkpoint**: All three of US1, US2, and US3 work; the tally is auditable for four rules

---

## Phase 6: User Story 4 - Learn immediately when an output folder cannot be used (Priority: P3)

**Goal**: Each of the five new failure modes writes a one-line diagnostic naming the offending path
or stating the misuse to stderr, writes neither the `wrote N files` line nor a tally, and exits 2.

**Independent Test**: Run with `--out-dir` naming a path that cannot be created (for example one
whose parent is an existing regular file) and confirm stderr names that path, no `wrote N files`
line is printed, and the exit status is 2 (spec Story 4 Independent Test; contract W-9).

**Depends on**: US2 (these are the failure paths of the option US2 introduces).

### Tests for User Story 4

> **NOTE: SC-006 requires each of these tests to assert the diagnostic *and* the exit status.**
> Every diagnostic keeps the one-line shape `logredact: {subject}: {reason}`; for OS failures
> assert the subject plus a stable substring of the reason, never the whole `strerror` string
> (contract C-4, `001/D-009`).

- [ ] T036 [US4] Add to `tests/test_out_dir.py`: `test_fr012_out_dir_without_value_usage_error_nothing_read` — `logredact app.log --out-dir` writes the **unchanged v1 usage line** `usage: python -m logredact [--count] [FILE ...]` followed by `logredact: --out-dir requires a directory` to stderr, leaves stdout empty, never opens `app.log`, and exits 2 (FR-012, contract W-7); `test_fr020_out_dir_without_file_errors_without_reading_stdin` — `--out-dir nope` with stdin supplied and no FILE writes `logredact: --out-dir requires at least one FILE` to stderr, leaves stdout empty, does **not** read stdin, does **not** create `nope`, and exits 2 (FR-020, contract W-8)
- [ ] T037 [US4] Add to `tests/test_out_dir.py`: `test_fr024_uncreatable_dir_names_path_and_exits_2` — covering both a folder path that is an existing regular file and a folder path whose **parent** component is an existing regular file (`blocker/clean`), each producing a diagnostic naming the path **as the user gave it** (not the failing intermediate component), no `wrote N files` line, exit 2, and the input never opened (FR-024, research.md D-107, contract W-9)
- [ ] T038 [US4] Add to `tests/test_out_dir.py`: `test_fr025_unwritable_output_file_names_output_path_and_exits_2` — create a directory at `clean2/app.log` so the output file cannot be created, then run with `--out-dir clean2 logs/2026/app.log` and assert the diagnostic names the **output** path `clean2/app.log` (not the input path), no `wrote N files` line, and exit 2 (FR-025, contract C-4)
- [ ] T039 [US4] Add to `tests/test_out_dir.py`: `test_fr023_unreadable_file_names_input_path_stops_and_exits_2` — two FILE arguments where the first is readable and the second does not exist: the first input's output file **has been written and stays written**, stderr names the second path, no later FILE is opened, and exit 2; assert also that **no** stray empty output file is created for the failing input (data-model.md R7.4, contract W-6); and `test_fr026_no_wrote_line_and_no_tally_on_any_exit_2_path` — parametrised over all five new failure modes plus the pre-existing unrecognised-option case, each run **with `--count`**, asserting that stdout carries no `wrote N files` line and stderr carries no `emails=` tally line in any of them (FR-023, FR-026)
- [ ] T040 [US4] Run `python3 -m pytest -q -k out_dir` and confirm the new failure-mode tests fail for the right reason — the diagnostics and the exit-2 paths do not exist yet

### Implementation for User Story 4

- [ ] T041 [US4] In the `--out-dir` arm of the parse loop in `src/logredact/__main__.py`, when there is no `argv[i + 1]`, write `f"{USAGE}\nlogredact: --out-dir requires a directory\n"` to stderr and `return 2` before any input is read or any stdout byte written. The usage line accompanies malformed command lines only (FR-012, data-model.md R6.3, R7.1)
- [ ] T042 [US4] In `main()` in `src/logredact/__main__.py`, after parsing and before `os.makedirs`, reject `out_dir is not None and not paths` with `sys.stderr.write("logredact: --out-dir requires at least one FILE\n")` and `return 2` — no usage line, stdin not opened, nothing on stdout, and no directory created. Without this check the run would fall through to the stdin branch and stream redacted data to stdout, making the option look as though it had worked, which Constitution Principle II forbids (FR-020, research.md D-106, data-model.md R6.6)
- [ ] T043 [US4] In `src/logredact/__main__.py`, wrap the `os.makedirs(out_dir, exist_ok=True)` call from T025 in `except OSError as exc`, writing `f"logredact: {out_dir}: {reason}\n"` to stderr — with `reason = getattr(exc, "strerror", None) or str(exc)`, matching the existing diagnostic helper shape — and `return 2`. Name the path **as the user gave it**. Detection is by exception only: add no `os.path.isdir` or `os.access` pre-flight check, which would be a TOCTOU race and a second code path for a failure the exception already describes (FR-024, research.md D-107, data-model.md R6.7)
- [ ] T044 [US4] In the FILE loop in `src/logredact/__main__.py`, make input and output failures distinguishable by **opening the input first** and nesting the output's error handling inside the input's: an inner `except OSError` around the output open and copy writes `f"logredact: {out_path}: {reason}\n"` and returns 2 (FR-025), while the existing outer `except (OSError, UnicodeDecodeError)` keeps writing `f"logredact: {path}: {reason}\n"` and returning 2 (FR-023). Flush the stdout wrapper before each diagnostic, as the existing handler does. Input-first ordering is what leaves no stray empty output file for an unreadable FILE; a mid-copy `UnicodeDecodeError` escapes the inner handler and is attributed to the input, a mid-copy `OSError` to the output. Use no bare `except` and no `except Exception` — exceptions are caught only to add path context and translate to an exit status (research.md D-109, data-model.md R7.3-R7.6, Constitution Principle II)
- [ ] T045 [US4] Review `src/logredact/__main__.py` and confirm FR-026 holds **structurally**, not just by test: the `wrote N files` write and the tally write both sit after every `return 2` in `main()`, so no exit-2 path can reach either. Then run `python3 -m pytest -q` and confirm the whole suite passes

**Checkpoint**: All four user stories are independently functional and every specified failure mode is covered

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The whole-feature guarantees — the normative worked examples, the preservation of v1
behaviour, the performance envelope, and the merge gate.

- [ ] T046 [P] Add `test_sc001_worked_examples_reproduce_exactly` to `tests/test_out_dir.py`, reproducing the normative W-1, W-2, and W-3 blocks from [contracts/cli.md](./contracts/cli.md#worked-examples-normative--these-are-the-sc-001-cases) byte-for-byte — which stream each byte goes to, the files created, their contents, and the exit status (SC-001)
- [ ] T047 [P] Add `test_fr027_v1_contract_examples_unchanged` to `tests/test_cli.py`, re-running the v1 contract's worked examples E-1 through E-7 from [001 contracts/cli.md](../001-logredact-cli/contracts/cli.md) against the changed tool and asserting each reproduces unchanged **except E-3's tally line**, which is now `emails=1 ips=1 cards=0 phones=0` (FR-027, SC-005, quickstart Scenario 5)
- [ ] T048 Add `test_sc007_streams_large_input_to_folder_within_budget` to `tests/test_out_dir.py`: generate a 100 000-line file whose lines each carry an email, an IPv4 address, a card number, and a phone number, redact it to stdout and to `--out-dir`, assert both complete inside the budget and that the two destinations produce byte-identical content; include a single 1 MB line through stdin to show memory does not track line length (SC-007, quickstart Scenario 6)
- [ ] T049 Run quickstart [Scenario 6](./quickstart.md#scenario-6--streaming-limits-sc-007) by hand and record the two timings (stdout and `--out-dir`, each under 10 s) plus the maximum-resident figure from `/usr/bin/time -v`; also confirm the closed-stdout case in folder mode exits 141 with empty stderr and no traceback (SC-007, data-model.md R5.9)
- [ ] T050 Verify the `USAGE` constant in `src/logredact/__main__.py` is **byte-identical** to its v1 text, `usage: python -m logredact [--count] [FILE ...]`, and still does not mention `--out-dir`. This stale-looking line is the specified outcome, not an oversight: FR-027 and SC-005 require the existing usage-line test to pass unchanged. The reversal if the spec intended otherwise is one line in each of two places and is recorded in research [D-105](./research.md#d-105-the-usage-string-stays-byte-identical) — raise it in `/speckit-clarify` rather than changing it here
- [ ] T051 Verify the Constitution merge gate: no third-party import appears anywhere under `src/`, `pyproject.toml` still declares `dependencies = []`, no new module was created under `src/logredact/`, and `tests/conftest.py`, `tests/test_redact.py` are unmodified while `tests/test_cli.py` differs from its pre-change state only in the seven tally assertion strings from T030 and the test added in T047 (Constitution Principles I and IV, SC-005)
- [ ] T052 Walk the [quickstart requirement → test map](./quickstart.md#requirement--test-map-sc-004) row by row and confirm each of FR-001…FR-027 has at least one **passing** test carrying that requirement id in its name, and that the FR-012, FR-020, FR-023, FR-024, and FR-025 rows each assert both the diagnostic and the exit status (SC-004, SC-006, Constitution Principle III)
- [ ] T053 Run `python3 -m pytest -q` from the repository root one final time: the suite is green with no plugins and no services, and the pass count has grown from the T001 baseline with zero pre-existing failures (quickstart "Definition of done")

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — run first to capture the SC-005 baseline
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **US1 (Phase 3)** and **US2 (Phase 4)**: Both depend only on Foundational, and are independent of
  each other — US1 touches `redact.py` plus two test files, US2 touches `__main__.py` plus one new
  test file
- **US3 (Phase 5)**: Depends on Foundational **and US1** (the `phones` figure needs the rule that
  produces it). T032 (FR-019) additionally needs US2
- **US4 (Phase 6)**: Depends on **US2** — these are the failure paths of the option US2 introduces
- **Polish (Phase 7)**: Depends on all four stories

### User Story Dependencies

```text
Setup → Foundational ─┬─→ US1 (P1, MVP) ──→ US3 (P3) ──┐
                      │                                 ├─→ Polish
                      └─→ US2 (P2) ──→ US4 (P3) ────────┘
```

- **US1 (P1)**: No dependency on another story. Independently testable and shippable
- **US2 (P2)**: No dependency on another story. T022 carries an `xfail` marker so it stays
  independent of US1's completion
- **US3 (P3)**: Needs US1 for a non-zero `phones` figure; its FR-019 task needs US2
- **US4 (P3)**: Needs US2

### Within Each User Story

- Tests are written and **confirmed failing** (T011, T023, T033, T040) before implementation
- In US1: placeholder and pattern constants → compiled alternation → `replace()` → docstrings and corpora
- In US2: argument parsing → folder creation → per-file output open → the `wrote N files` line
- In US4: parse-time errors → validation errors → folder errors → per-file input/output errors
- Story complete and its checkpoint verified before moving to the next priority

### Parallel Opportunities

Parallelism is genuinely limited here, and the task list says so rather than inventing it: the
feature changes two source files and most tasks within a story edit the same file sequentially.
The real opportunities are:

- **Across stories**: once Phase 2 is done, US1 (`src/logredact/redact.py`) and US2
  (`src/logredact/__main__.py`) can be worked by two people with no file contention. This is the
  one substantial split
- T002 runs alongside T001
- T015 (docstrings in `redact.py` / `__init__.py`) and T016 (`tests/test_corpus.py`) are marked
  `[P]` — different files from each other and from the pattern work
- T046 (`tests/test_out_dir.py`) and T047 (`tests/test_cli.py`) are marked `[P]`
- Within `tests/test_phone.py` (T008-T010) and `tests/test_out_dir.py` (T019-T022) tasks are **not**
  parallel: they append to the same file

## Parallel Example: Two developers after Phase 2

```bash
# Developer A — User Story 1, src/logredact/redact.py
Task: "T008-T010 Create tests/test_phone.py (FR-001...FR-006, FR-009)"
Task: "T012-T014 _PHONE pattern, third alternation branch, phone counting"

# Developer B — User Story 2, src/logredact/__main__.py
Task: "T019-T022 Create tests/test_out_dir.py (FR-007, FR-011...FR-022)"
Task: "T024-T028 indexed parse loop, makedirs, per-file output, wrote N files"
```

```bash
# Inside User Story 1, after the pattern lands (different files):
Task: "T015 Docstrings in src/logredact/redact.py and src/logredact/__init__.py"
Task: "T016 KNOWN_PHONES corpus in tests/test_corpus.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup — capture the `31 passed, 1 skipped` baseline
2. Phase 2: Foundational — widen `Counts`, convert the CLI accumulators (behaviour-neutral)
3. Phase 3: User Story 1 — the phone rule
4. **STOP and VALIDATE**: `echo 'call +14155552671 now' | python3 -m logredact` →
   `call [PHONE] now`; full suite green; quickstart Scenario 1 by hand
5. Shippable: the tool no longer leaks international phone numbers. The tally still shows three
   figures and `--out-dir` does not exist yet — both are later increments, neither is a broken state

### Incremental Delivery

1. Setup + Foundational → `Counts` ready, nothing observable changed
2. **+ US1** → phone numbers redacted everywhere (MVP, closes the leak SC-002 measures)
3. **+ US2** → `--out-dir` writes one redacted copy per file and reports `wrote N files`
4. **+ US3** → the tally's fourth figure makes phone redactions auditable
5. **+ US4** → every new failure mode names its path and exits 2
6. **+ Polish** → SC-001 worked examples, FR-027 preservation, SC-007 timings, merge gate

Each increment leaves the suite green and the previously shipped behaviour intact.

### Parallel Team Strategy

1. One person does Phase 1 and Phase 2 (they are short, sequential, and touch both source files)
2. Then split by file: Developer A takes US1 in `redact.py`, Developer B takes US2 in `__main__.py`
3. US3 and US4 rejoin: US3 after US1 (plus US2 for its FR-019 task), US4 after US2. Both land in
   `__main__.py`, so run them sequentially rather than concurrently
4. Polish last, by whoever is free

---

## Notes

- `[P]` tasks touch different files and have no dependency on an incomplete task
- `[Story]` labels map tasks to spec user stories for traceability; Setup, Foundational, and Polish
  carry none
- **Test ids are not free-form**: use the names in the
  [quickstart requirement → test map](./quickstart.md#requirement--test-map-sc-004) so SC-004's
  coverage claim stays checkable by name
- **Confirm each test fails before implementing it** (T011, T023, T033, T040) — a test that passes
  against unchanged code is asserting the wrong thing
- The one invariant most easily broken silently: an output file must be opened with **the same three
  keyword arguments as the stdout wrapper** (`encoding="utf-8", newline="", errors="strict"`). That
  identity *is* FR-015 (T026)
- Two things are deliberately **not** done, and a reviewer may read either as a defect: the `USAGE`
  string is not updated to mention `--out-dir` (T050, research D-105), and `--out-dir .` is not
  guarded against destroying its own input (spec Assumptions, data-model.md R6.8). Both are the
  specified outcome; `/speckit-clarify` is the place to revisit them
- Commit after each task or logical group; stop at any checkpoint to validate a story on its own
- Avoid: marking same-file tasks `[P]`, editing pre-existing test files beyond the seven tally
  assertions in T030 and the addition in T047, and adding any abstraction the spec does not ask for
