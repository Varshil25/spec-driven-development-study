---
description: "Task list for feature 002-redact-phones-out-dir"
---

# Tasks: Redact Phone Numbers and Write Sanitized Copies to an Output Folder

**Input**: Design documents from `/specs/002-redact-phones-out-dir/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Test tasks are **included and mandatory**. The spec requires them (SC-015, SC-016) and
Constitution Principle III requires every functional requirement to map to at least one `pytest`
test that fails when the requirement is unmet.

**Organization**: Tasks are grouped by the four user stories of spec.md so each can be implemented,
tested, and demonstrated on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Every task names the exact file it touches

## Path Conventions

Single project, as it already exists (plan.md "Source Code"):

- Source: `src/logredact/redact.py` (pure core), `src/logredact/cli.py` (process-facing)
- Tests: `tests/unit/` (in-process), `tests/cli/` (subprocess via the `run_cli` fixture in
  `tests/cli/conftest.py`)
- `pytest` runs bare from the repository root; `pytest.ini` sets `pythonpath = src`

**This feature changes two existing source files and adds no module.** No new dependency, no new
exit status (plan.md Summary).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Record the pre-change state this feature must be measured against. FR-054 and SC-015
require byte-identical output for inputs containing neither a phone number nor a `+`-prefixed digit
run — that baseline can only be captured **before** any source edit.

- [X] T001 Capture the pre-change baseline for FR-054/SC-015: create `tests/fixtures/baseline_input.log` containing only inherited-rule material (an email, an IPv4 address inside and outside the octet range, a bare 16-digit Luhn-valid card, a CRLF line, a line with no final newline, and an undecodable `\xff` byte) with **no `+` character anywhere**, then run the current tool over it and store its exact stdout bytes as `tests/fixtures/baseline_output.log`. Record both files in git before editing any source.
- [X] T002 Run `pytest` from the repository root and record the pass/skip counts in the commit message as the green starting point; research.md R-021 predicts 153 passing and 1 skipped, and 25 of those assertions will be deliberately updated in Phase 2 and Phase 4.

**Checkpoint**: Baseline recorded, suite green, nothing changed yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Make the counts dict four-wide. Every user story below either produces or reports the
`phones` counter, so this must land first.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

**Design note (R-021)**: `new_counts()` becomes the *single* place the key names are written. `main`
must stop repeating the literal and the accumulation loop must stop naming keys one at a time, or
FR-037's "always all four, always in this order" will drift. The three-key summary **string** is
deliberately left alone here — `"…cards={cards}\n".format(**totals)` ignores the extra key — so the
10 CLI summary assertions keep passing until User Story 2 changes them.

- [X] T003 Add `"phones": 0` as the fourth and last key of the dict returned by `new_counts()` in `src/logredact/redact.py`, keeping the order `emails, ips, cards, phones` exactly as data-model.md "Redaction counts" specifies, and update its docstring to say four counters.
- [X] T004 In `src/logredact/cli.py`, replace the hand-written literal `totals = {"emails": 0, "ips": 0, "cards": 0}` in `main` with `totals = new_counts()` (importing `new_counts` alongside `redact_line`), and replace the three hand-written accumulation lines in `_redact_stream` with `for key, value in counts.items(): totals[key] += value` (R-021).
- [X] T005 [P] Update every three-key counts-dict literal in `tests/unit/test_counting.py` to the four-key form (lines ~30, 35, 44, 48, 49, 53, 67, 80, 84, 93), including the `new_counts()` identity assertions, which must now read `{"emails": 0, "ips": 0, "cards": 0, "phones": 0}`.
- [X] T006 [P] Update every three-key counts-dict literal in `tests/unit/test_precedence.py` to the four-key form (lines ~68, 91, 104, 108, 122, 133, 140).
- [X] T007 Run `pytest` and confirm the suite is green again with no change to any redacted-output assertion; a failure anywhere other than the dict literals of T005/T006 is a regression, not an expected update (SC-015).

**Checkpoint**: Four counters exist end to end, no observable CLI behaviour has changed yet, suite green.

---

## Phase 3: User Story 1 - Phone numbers disappear from a shared log (Priority: P1) 🎯 MVP

**Goal**: `+` followed by 8 to 15 ASCII digits is replaced by `[PHONE]`, with the `+` consumed; a
digit run immediately preceded by `+` is never a payment card.

**Independent Test**: `echo 'call +14155552671 now' | python -m logredact` prints exactly
`call [PHONE] now`, and `echo '+4111111111111111' | python -m logredact` prints its input unchanged.

### Tests for User Story 1 ⚠️

> Write these first and confirm they fail before touching `redact.py`.

- [X] T008 [P] [US1] Add phone recognition and non-recognition tests to `tests/unit/test_patterns.py` driving `redact_line` directly, covering the whole recognition table of `contracts/redaction-rules.md`: `+14155552671` → `[PHONE]`; the bounds `+12345678` (8 digits, the minimum) and `+455673758689985` (15 digits, the maximum) → `[PHONE]`; `+1234567` (7 digits) unchanged (FR-033); `+1234567890123456` (16 digits) unchanged **whole**, asserting the output contains no `[PHONE]` and no truncation (FR-032); `+14155552671.` → `[PHONE].` and `(+14155552671)` → `([PHONE])` (FR-034); `+` alone and `+abc` unchanged (FR-033); `++12345678` → `+[PHONE]`; `+14155552671+442071838750` → `[PHONE][PHONE]`; `+١٤١٥٥٥٥٢٦٧١` and `+1415555٢٦٧١` unchanged, because "digit" means ASCII `0`-`9` and nothing else (FR-031); and the no-left-hand-guard cases `build v2+12345678 ok` → `build v2[PHONE] ok`, `x=99+12345678` → `x=99[PHONE]`, and `+12345678` at line start → `[PHONE]` (FR-031a).
- [X] T009 [US1] Add the FR-032a card-narrowing tests to `tests/unit/test_patterns.py` (same file as T008, so sequential): `+4111111111111111` unchanged — no `[CARD]` and no `[PHONE]`; `+4111 1111 1111 1111` unchanged; `+455673758689985` → `[PHONE]` (15 digits, the phone rule claims it one character earlier); `+1 4111111111111111` and `+1-4111111111111111` unchanged, which is the exact regression R-012's rejected lookbehind variant introduced; and the control `4111111111111111` → `[CARD]`, proving the card rule itself is untouched.
- [X] T010 [P] [US1] Add precedence and overlap tests to `tests/unit/test_precedence.py` (FR-035, FR-036): `+12345678@example.com` → `[EMAIL]` counted as an email, **not** `[PHONE]@example.com`; `jane+orders@example.com` → `[EMAIL]`; `a@b.io +442071838750` → `[EMAIL] [PHONE]`; `+14155552671 10.0.0.7` → `[PHONE] [IP]`; a `+` followed by 13-to-15 Luhn-valid digits → `[PHONE]` counted once as a phone and never also as a card; and extend the existing placeholders-match-counts property assertion so it also checks `text.count("[PHONE]") == c["phones"]`.
- [X] T011 [P] [US1] Add the SC-009 near-miss control sample to `tests/cli/test_output_fidelity.py`: a multi-line input of `+` with 7 digits, `+` with 16 digits, a 16-digit `+`-prefixed run that passes the payment-card checksum, `+` followed by letters, `+` followed by non-ASCII decimal digits, and a bare `+`, asserting stdout is **byte-identical** to stdin — zero false positives, zero partial redactions, no `[CARD]` produced from a `+`-prefixed run.

### Implementation for User Story 1

- [X] T012 [US1] In `src/logredact/redact.py` add `PHONE_PLACEHOLDER = "[PHONE]"` beside the three existing placeholders and the pattern `_PHONE = r"\+[0-9]{8,15}(?![0-9])"` with a comment recording what each part carries: `[0-9]` **not** `\d` is FR-031 (ASCII digits only), `(?![0-9])` is FR-032 (a run followed by another digit is rejected whole, never truncated to its first 15), and the deliberate absence of any lookbehind is FR-031a.
- [X] T013 [US1] In `src/logredact/redact.py` append `(?P<phone>{_PHONE})` as the **last** branch of the compiled `PATTERN` alternation — branch order *is* the FR-036 tie-break `email → ip → card → phone`, so appending it is the whole implementation — and add the phone arm to `_replacement`: `if kind == "phone": counts["phones"] += 1; return PHONE_PLACEHOLDER`, with **no post-match validation**, because the pattern alone decides (data-model.md "Redaction type", R-010, R-011).
- [X] T014 [US1] In `src/logredact/redact.py` add the FR-032a guard as the first statement of the card arm of `_replacement`, before the separator strip: `if match.start() > 0 and match.string[match.start() - 1] == "+": return text`. It must reject the **whole maximal candidate** and must **not** be implemented as a `(?<!\+)` lookbehind on `_CARD` — R-012 verified the lookbehind creates new `[CARD]` matches (`+1 4111111111111111` → `+1 [CARD]`), which FR-054 forbids. Comment it as a suppression only: strictly fewer card matches than before, never more.

**Checkpoint**: Phone numbers are redacted, the `+`-prefixed card is suppressed, the three inherited
rules are untouched. User Story 1 is independently demonstrable and the whole suite passes. **This
is the MVP.**

---

## Phase 4: User Story 2 - See how many phone numbers were redacted (Priority: P2)

**Goal**: The `--count` summary on stderr becomes exactly `emails=N ips=N cards=N phones=N`.

**Independent Test**: `echo 'a@b.io +442071838750' | python -m logredact --count` writes
`[EMAIL] [PHONE]` to stdout and exactly `emails=1 ips=0 cards=0 phones=1` to stderr.

### Tests for User Story 2 ⚠️

- [X] T015 [P] [US2] Add phones-counter unit tests to `tests/unit/test_counting.py` (FR-038): a line with several phone numbers reports that many; a rejected candidate (7 digits, 16 digits) increments nothing; input already containing the literal `[PHONE]` passes through unchanged and uncounted (inherited FR-020); `counts` is `0` for `phones` when none was made; and extend the existing placeholders-equal-counts property assertion to the fourth type.
- [X] T016 [P] [US2] Update `tests/cli/test_count_flag.py` to the four-key form and extend it (FR-037, FR-039): change the `SUMMARY` regex at line ~7 to `rb"^emails=\d+ ips=\d+ cards=\d+ phones=\d+\n$"`, update the eight exact three-key stderr assertions (lines ~18, 24, 30, 36, 57, 65, 92, 150) to four keys, and add tests asserting the exact line `emails=1 ips=0 cards=0 phones=1` for `a@b.io +442071838750`, `emails=0 ips=0 cards=0 phones=0` for inert input, one single summary covering several FILE arguments printed once after all output, and nothing at all on stderr without `--count`.
- [X] T017 [P] [US2] Update the exact three-key summary assertion at `tests/cli/test_invocation.py` line ~157 to `b"emails=1 ips=1 cards=0 phones=0\n"`.
- [X] T018 [P] [US2] Update the exact three-key summary assertion at `tests/cli/test_output_fidelity.py` line ~80 to its four-key form.

### Implementation for User Story 2

- [X] T019 [US2] In `src/logredact/cli.py` change `_write_summary`'s format string to `"emails={emails} ips={ips} cards={cards} phones={phones}\n"` — four keys, always all four, always in this order, single-space separated, one line (FR-037). Everything else about the function is unchanged: the `sys.stdout.flush()` first so the summary always follows the complete output (FR-021), and the fact that every failure path returns before reaching it is what keeps FR-039's suppression intact.

**Checkpoint**: Stories 1 and 2 both work. The 25 assertions SC-015 licenses are now all updated and
the full suite passes; any other failure is a regression.

---

## Phase 5: User Story 3 - Sanitize a folder of logs into a folder of clean copies (Priority: P3)

**Goal**: `--out-dir DIR` writes each FILE's redacted lines to `DIR/<basename(FILE)>` and prints
`wrote N files` to stdout.

**Independent Test**: `python -m logredact --out-dir clean app.log web.log` leaves `clean/app.log`
and `clean/web.log` holding the redacted contents of their inputs, writes exactly `wrote 2 files` to
stdout and nothing to stderr, and exits 0.

### Tests for User Story 3 ⚠️

- [X] T020 [P] [US3] Create `tests/cli/test_out_dir.py` using the `run_cli` fixture from `tests/cli/conftest.py` and `tmp_path`, covering the happy path: two readable files into a folder that does not exist → folder created, both output files correct, stdout exactly `b"wrote 2 files\n"`, stderr empty, status 0 (FR-041, FR-046); `var/logs/app.log` → `clean/app.log`, the name only with the input's directories dropped (FR-041); an output folder path several levels deep → every missing parent created (FR-042); a pre-existing file of the output name → replaced, asserted by **byte length and content** after the run, never appended to (FR-043, SC-012); a pre-existing unrelated file in the folder → untouched (FR-042); an empty input file → a 0-byte output file that still counts towards N (US3-8); two FILE arguments with the same basename → `wrote 2 files` with the folder holding one file containing only the second input's output (data-model.md "Collisions"); the same FILE named twice → counted twice; `--out-dir` with `--count` → `wrote N files` on stdout and the four-key summary on stderr, confirmation line first (FR-052); no `--out-dir` → output on stdout exactly as before and no `wrote` line ever printed (FR-047); and the FR-044 byte-identity check — each output file's bytes equal the bytes `python -m logredact <same FILE>` writes to stdout, including a CRLF line, a missing final newline, and an undecodable `\xff` byte.
- [X] T021 [P] [US3] Add flag-interleaving tests to `tests/cli/test_invocation.py` (FR-040): `--out-dir d --count a.log b.log`, `a.log --out-dir d b.log --count`, and `a.log b.log --count --out-dir d` are equivalent, and `--help` on stdout now shows the usage line `usage: python -m logredact [-h] [--count] [--out-dir DIR] [files ...]` and exits 0.

### Implementation for User Story 3

- [X] T022 [US3] In `src/logredact/cli.py` `build_parser`, add `parser.add_argument("--out-dir", dest="out_dir", metavar="DIR")` — exactly one value, zero or one occurrence. `parse_intermixed_args` already handles interleaving with FILE arguments, and argparse regenerates the usage line itself, so FR-040's grammar change needs no hand-written `usage=` string (R-014).
- [X] T023 [US3] In `src/logredact/cli.py` give `_redact_stream` a `write` parameter instead of binding `sys.stdout.write` internally, and pass `sys.stdout.write` at the existing call sites. That one parameter with two call sites is the **whole** destination polymorphism — no `Destination` class, no strategy object, no sink abstraction (plan.md "Structure Decision", Principle IV).
- [X] T024 [US3] In `src/logredact/cli.py` add the sink helpers: `_OutputError(Exception)` carrying `path` and `error` attributes and inheriting `Exception`, **not** `OSError`, so an `except OSError` clause cannot swallow it (R-018); `_open_sink(path)` calling `open(path, "w", encoding="utf-8", errors="surrogateescape", newline="")` — the same four arguments as the stdout reconfigure, which is what makes FR-044 a guarantee rather than an approximation, and `"w"` is what gives FR-043's replacement (R-020); and `_sink_writer(sink, path)` returning a closure that wraps each `sink.write` in `try/except OSError` and re-raises as `_OutputError(path, error)`. Wrap the sink's `open` and `close` the same way.
- [X] T025 [US3] In `src/logredact/cli.py` `main`, add the `--out-dir` branch: call `os.makedirs(args.out_dir, exist_ok=True)` **before the first FILE is opened** (FR-045; `exist_ok=True` gives all of FR-042 in one argument — missing parents created, an existing folder used as it is and never emptied), then for each FILE open the input first and only then the sink at `os.path.join(args.out_dir, os.path.basename(name))` (R-016, R-017), stream through `_sink_writer`, close the sink, and increment a `written` counter once per completed file. After the loop write exactly one line `wrote {written} files` to stdout — printed as given, including `wrote 1 files` for a single file, never pluralised — and leave the `--count` summary to follow it on stderr (FR-046, FR-047, FR-052). The no-`--out-dir` path must stay byte-for-byte what it is today.

**Checkpoint**: Stories 1, 2 and 3 all work on their happy paths. Failure handling for the new
destination is still the inherited behaviour and is completed by Story 4.

---

## Phase 6: User Story 4 - Fail clearly when a sanitized copy cannot be produced (Priority: P4)

**Goal**: Every new failure mode names the offending path, prints no stack trace, prints no
`wrote N files` and no summary, leaves no truncated file in the folder, and exits 2.

**Independent Test**: `python -m logredact --out-dir out good.log missing.log later.log` names
`missing.log` on stderr, leaves `out/` holding only a complete `good.log`, never opens `later.log`,
writes nothing to stdout, and exits 2.

**Depends on**: Phase 5 (the sink helpers and the `--out-dir` branch are what these handlers guard).

### Tests for User Story 4 ⚠️

- [X] T026 [P] [US4] Create `tests/cli/test_out_dir_failures.py` covering every failure path with the `run_cli` fixture: an unreadable FILE → stderr names it **as typed on the command line**, no `wrote` line, no summary, no traceback, status 2, and a pre-existing file of its output name is left intact because the input is opened before the sink (FR-048, R-017); a readable file followed by an unreadable one → the first output file complete, the later FILE never opened, status 2 (US4-2); DIR that cannot be created because its parent is a regular file → stderr names DIR, **no input read**, stdout empty, status 2 (FR-049); an output path that already exists as a directory → stderr names the **output path**, not the input, status 2 (FR-050); a write failure forced with a symlink to `/dev/full` → stderr names the output path with `No space left on device`, and the half-written file is **absent** from the folder afterwards, with its pre-existing contents **not** restored (FR-050, FR-050a, US4-9); a read failure partway through (`/proc/self/mem`) → stderr names the input, the sink opened for it is deleted, and the earlier file is complete (US4-8, SC-013a); `--out-dir` with no FILE at all → a usage diagnostic stating `--out-dir` requires at least one FILE, stdin **not read**, DIR **not created**, stdout empty, status 2 (FR-051); an unrecognised flag → unchanged from today, usage naming that argument, status 2 (FR-029); and the SC-013a sweep — after each failed run every file remaining in the folder is byte-identical to the complete redacted stream of its input.
- [X] T027 [US4] Add the SC-014 exit-status assertion to `tests/cli/test_out_dir_failures.py`: across every scenario in that module the return code is `0` or `2` and never any other value.

### Implementation for User Story 4

- [X] T028 [US4] In `src/logredact/cli.py` `main`, add the FR-051 usage check immediately after `parse_intermixed_args` and **before** `_configure_streams` and before `makedirs`: `if args.out_dir is not None and not args.files: parser.error("--out-dir requires at least one FILE")`. Running it there is precisely what keeps stdin unread and DIR uncreated. `parser.error` *is* the inherited FR-029 path — argparse writes the usage line plus the message to stderr and raises `SystemExit(2)`, which `__main__.py`'s `raise SystemExit(main())` propagates unchanged — so no message formatting is hand-rolled (R-014).
- [X] T029 [US4] In `src/logredact/cli.py` wrap the `os.makedirs` call of T025 in `except OSError as error: _report(args.out_dir, error); return EXIT_FAILURE` (FR-049). `OSError.strerror` supplies "what went wrong" for `File exists` and `Not a directory` alike, so the inherited `_report` helper carries the whole diagnostic with no new formatting (R-015).
- [X] T030 [US4] In `src/logredact/cli.py` add the `_discard(sink, path)` helper (FR-050a): close the handle inside `try/except OSError: pass`, then `os.remove(path)` inside `try/except OSError as error: _report(path, error)`. Comment the `pass` as the justified deviation it is — plan.md Complexity Tracking records it: the handle must be closed before `os.remove` for the deletion to be portable, and a flush failure at that close is, on the common `ENOSPC` path, the very error already being reported, so re-raising it would both skip the deletion and replace the primary diagnostic with a duplicate. A failed **deletion** is still reported, as a second stderr line, and the status stays 2.
- [X] T031 [US4] In `src/logredact/cli.py` add the per-FILE handlers around the `--out-dir` streaming loop, in this order: `except _OutputError as failure: _report(failure.path, failure.error); return EXIT_FAILURE` (FR-050 — name the output path) before `except OSError as error: _report(name, error); return EXIT_FAILURE` (FR-048 — name the FILE as given), with the existing `except BrokenPipeError: raise` still ahead of both so an early-closing consumer is never reported as a read failure. Call `_discard(sink, out_path)` on any failure occurring after the sink was opened, and on no other path. Both handlers return before `wrote N files` and before `_write_summary`, which is what suppresses the confirmation line and the summary on every failure (FR-047, FR-039).
- [X] T032 [US4] Run `pytest tests/cli/test_failures.py tests/cli/test_broken_pipe.py` and confirm both modules pass **unchanged** — the inherited failure and early-close paths must still hold exactly as they do today (FR-053). Any edit to either file is a regression signal, not a fix.

**Checkpoint**: All four user stories are independently functional. Every failure mode of the feature
produces a named path, status 2, and a folder holding only complete files.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T033 [P] Add the FR-054/SC-015 byte-identity test to `tests/cli/test_output_fidelity.py`: run the tool over `tests/fixtures/baseline_input.log` from T001 and assert stdout is byte-identical to `tests/fixtures/baseline_output.log` — an input containing neither an international-format phone number nor a `+`-prefixed digit run must produce exactly the pre-change tool's output.
- [X] T034 [P] Add the SC-010 four-type property assertion to `tests/unit/test_counting.py`: for every sample input, each reported count equals the number of placeholders of that type present in the output, for all four types at once.
- [X] T035 [P] Update the module docstrings and comments in `src/logredact/redact.py` and `src/logredact/cli.py` so the new code explains which requirement each piece carries, matching the existing house style: the pattern parts (FR-031, FR-031a, FR-032), the card guard as a suppression (FR-032a), the single-source-of-key-names rule (R-021), the sink's four `open` arguments (FR-044), and the input-before-sink ordering (R-017).
- [X] T036 [P] Patch spec defect D-1 in `specs/002-redact-phones-out-dir/spec.md`: split the trailing sentence of FR-050a (line ~371) into its own paragraph and restore the `**FR-051**:` label that Assumptions and SC-013 already refer to by number. Text unchanged — this is a labelling fix, not a requirement change.
- [X] T037 Walk scenarios 1 through 12 of `specs/002-redact-phones-out-dir/quickstart.md` by hand and confirm each produces its stated stdout, stderr, exit status, and filesystem effect.
- [X] T038 Walk the nine scenarios of `specs/001-redact-log-pii/quickstart.md` and confirm each still produces its stated result, with the single expected difference that the `--count` summary is now in its four-key form.
- [X] T039 Verify SC-017 in both destinations: generate a one-million-line log, time `python -m logredact mil.log > /dev/null` and `python -m logredact --out-dir out mil.log --count`, confirm both are well under 60 seconds (Phase 0 measured ≈8.5 s and ≈8.7 s against the pre-change tool's 8.6 s), and confirm memory does not grow with input size — nothing is accumulated and no file is buffered whole.
- [X] T040 Run `pytest` in full from the repository root and audit SC-016: confirm every requirement FR-030 through FR-054, including FR-031a, FR-032a, and FR-050a, has at least one covering test by walking plan.md's requirement-traceability table against the test files, and confirm no third-party import appears anywhere under `src/` (Constitution Principle I).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. **Must run before any source edit** — T001's baseline cannot be captured after the fact.
- **Foundational (Phase 2)**: Depends on Phase 1. **Blocks all four user stories.**
- **User Story 1 (Phase 3)**: Depends on Phase 2. No dependency on any other story.
- **User Story 2 (Phase 4)**: Depends on Phase 2. Independently testable, but its assertions are only meaningful once US1 actually produces phone replacements, so P1 → P2 is the natural order.
- **User Story 3 (Phase 5)**: Depends on Phase 2 only. Touches `cli.py` and no `redact.py` code, so it is genuinely independent of US1 and US2 and can be built in parallel with them by a second developer.
- **User Story 4 (Phase 6)**: Depends on **Phase 5** — these are the handlers around US3's sink. This is the one real cross-story dependency and it is inherent: Story 4 guards Story 3's failure modes.
- **Polish (Phase 7)**: Depends on all four stories.

### Within Each User Story

- Tests are written first and must fail before the implementation lands.
- In `redact.py`: placeholder and pattern (T012) → alternation branch and replacement arm (T013) → card guard (T014). Same file, strictly sequential.
- In `cli.py`: parser option (T022) → `write` parameter (T023) → sink helpers (T024) → the `main` branch (T025) → the handlers (T028–T031). Same file, strictly sequential.

### Parallel Opportunities

- **Phase 2**: T005 and T006 are different test files — run together.
- **Phase 3**: T008, T010, and T011 are three different files — run together. T009 follows T008 (same file). T012–T014 are all `redact.py` and cannot be parallelised.
- **Phase 4**: T015, T016, T017, and T018 are four different files — run all four together. T019 follows.
- **Phase 5**: T020 and T021 are different files — run together. T022–T025 are all `cli.py`, sequential.
- **Phase 6**: T026 and T027 are the same new file; T028–T031 are all `cli.py`, sequential.
- **Phase 7**: T033, T034, T035, and T036 touch four different files — run all four together. T037–T040 are validation runs, best done in order.
- **Across stories**: once Phase 2 is done, one developer can take US1+US2 (`redact.py` and the summary) while another takes US3+US4 (`cli.py` and the output folder). The two tracks touch disjoint source files; they meet only in Phase 7.

---

## Parallel Example: User Story 1

```bash
# Launch the three independent test files for User Story 1 together:
Task: "Phone recognition and non-recognition tests in tests/unit/test_patterns.py"
Task: "Precedence and overlap tests in tests/unit/test_precedence.py"
Task: "SC-009 near-miss control sample in tests/cli/test_output_fidelity.py"

# Then the redact.py edits, strictly in order (same file):
#   T012 placeholder + pattern -> T013 branch + replacement arm -> T014 card guard
```

## Parallel Example: User Story 2

```bash
# All four test-file updates are independent:
Task: "Phones counter unit tests in tests/unit/test_counting.py"
Task: "Four-key summary tests in tests/cli/test_count_flag.py"
Task: "Four-key assertion in tests/cli/test_invocation.py"
Task: "Four-key assertion in tests/cli/test_output_fidelity.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: capture the baseline (T001–T002).
2. Phase 2: four counters end to end (T003–T007). **Blocks everything.**
3. Phase 3: the phone rule and the card narrowing (T008–T014).
4. **STOP and VALIDATE**: `echo 'call +14155552671 now' | python -m logredact` → `call [PHONE] now`; `echo '+4111111111111111' | python -m logredact` → unchanged; full suite green.
5. This alone makes a shared log safe, which is the whole point of the change — shippable on its own.

### Incremental Delivery

1. Setup + Foundational → four counters, no behaviour change.
2. + User Story 1 → phone numbers are gone. **MVP.**
3. + User Story 2 → the engineer can confirm the new rule fired.
4. + User Story 3 → a folder of clean copies, happy path.
5. + User Story 4 → that folder is never silently incomplete. **Required before shipping Story 3** — a partial folder presented as a complete one is exactly the failure Story 4 exists to prevent.
6. + Polish → quickstart, performance, and the SC-016 coverage audit.

### Parallel Team Strategy

1. Everyone completes Phase 1 and Phase 2 together.
2. Then split along the source-file boundary:
   - Developer A: User Story 1 → User Story 2 (`redact.py`, `tests/unit/`, the summary string)
   - Developer B: User Story 3 → User Story 4 (`cli.py`, `tests/cli/test_out_dir*.py`)
3. The tracks touch disjoint files and meet in Phase 7.

---

## Notes

- `[P]` means a different file and no dependency on an incomplete task.
- Only two source files change: `src/logredact/redact.py` and `src/logredact/cli.py`. No new module, no new dependency, no new exit status — the status set stays exactly `{0, 2}` (FR-053, SC-014).
- **The 25 licensed assertion updates** (15 three-key dict literals in `tests/unit/`, 10 three-key summary lines in `tests/cli/`) are T005, T006, T016, T017, and T018. Research.md R-021 measured that these are the *complete* cost of this feature to the existing suite. A failure anywhere else is a regression, not an expected update (SC-015).
- Run `pytest` after each phase, not just at the end. The suite is designed to stay green at every checkpoint.
- Commit after each task or logical group; stop at any checkpoint to validate a story on its own.
