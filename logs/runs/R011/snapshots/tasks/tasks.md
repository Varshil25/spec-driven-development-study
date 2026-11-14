---

description: "Task list for 001-redact-log-pii"
---

# Tasks: Redact Personal Data From Log Files

**Input**: Design documents from `/specs/001-redact-log-pii/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/cli-contract.md](./contracts/cli-contract.md),
[contracts/redaction-rules.md](./contracts/redaction-rules.md), [quickstart.md](./quickstart.md)

**Tests**: INCLUDED and mandatory. Constitution Principle III requires every functional
requirement to map to at least one `pytest` test that fails when the requirement is unmet, and
SC-005 requires every FR and every documented edge case to be covered. Test tasks are therefore
not optional in this feature.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and
demonstrated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths are given in every description

## Path Conventions

Single project, per plan.md "Project Structure": `src/logredact/` for the package, `tests/unit/`
and `tests/cli/` for tests, `pytest.ini` at the repository root. All paths below are relative to
the repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Directory skeleton and the one line of configuration that makes a bare `pytest`
work from the repository root.

- [ ] T001 Create the directory skeleton `src/logredact/`, `tests/unit/`, and `tests/cli/` per plan.md "Project Structure"
- [ ] T002 [P] Create `pytest.ini` at the repository root containing a `[pytest]` section with `pythonpath = src`, so `import logredact` resolves under a bare `pytest` with no install step (research.md R-009; Constitution "runnable with a bare `pytest` invocation from the repository root")
- [ ] T003 [P] Create `src/logredact/__init__.py` as an empty package marker — no logic, no imports (plan.md: "Package marker; no logic")

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The process skeleton every user story runs through — entry point, argument parsing,
stream encoding, the run-local counter structure, and the subprocess test harness.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T004 [P] Create `src/logredact/__main__.py` containing only `from logredact.cli import main` and `raise SystemExit(main())` under an `if __name__ == "__main__":` guard — it exists solely because `python -m` requires it and MUST hold no other logic (plan.md "Structure Decision")
- [ ] T005 [P] Create `tests/cli/conftest.py` with a `run_cli` pytest fixture that invokes `[sys.executable, "-m", "logredact"]` via `subprocess.run` with `PYTHONPATH=src`, accepting an argv list, optional `stdin` **bytes**, and optional extra environment, and returning the completed process with **bytes** `stdout`/`stderr` (bytes, not text, so byte-fidelity and 0-bytes-on-stderr assertions are exact) (research.md R-009)
- [ ] T006 Implement `build_parser()` in `src/logredact/cli.py`: `argparse.ArgumentParser(prog="python -m logredact")`, a `--count` flag with `action="store_true"`, and a `files` positional with `nargs="*"`; parse with `parser.parse_intermixed_args()` and **NOT** `parse_args()` — verified in research.md R-001 that `parse_args(["a.log", "--count", "b.log"])` fails with `unrecognized arguments: b.log` (FR-001, FR-029)
- [ ] T007 Implement `_configure_streams()` in `src/logredact/cli.py`: reconfigure `sys.stdin` with `encoding="utf-8", errors="surrogateescape", newline="\n"` and `sys.stdout` with `encoding="utf-8", errors="surrogateescape", newline=""`, so behaviour never varies with `LANG`, `LC_ALL`, or `PYTHONIOENCODING` (research.md R-002; FR-005a, FR-005b)
- [ ] T008 Implement the `main(argv=None) -> int` skeleton in `src/logredact/cli.py` that calls `build_parser()` then `_configure_streams()`, copies `sys.stdin` lines to `sys.stdout` unchanged, and returns `0`; its return value is the process exit status and MUST only ever be `0` or `2` — no other value anywhere in the module (SC-006)
- [ ] T009 Create `src/logredact/redact.py` with the three placeholder constants `[EMAIL]`, `[IP]`, `[CARD]` and a `new_counts()` function returning a fresh run-local `dict` with keys `emails`, `ips`, `cards`, each initialised to `0`; no module-level mutable state, so two runs in one process cannot contaminate each other (data-model.md "Redaction counts"; Constitution "No hidden state")

**Checkpoint**: `echo hi | PYTHONPATH=src python -m logredact` echoes its input and exits 0. Story
implementation can now begin.

---

## Phase 3: User Story 1 - Sanitize a log stream before sharing it (Priority: P1) 🎯 MVP

**Goal**: Reading from standard input, replace every email address, IPv4 address, and Luhn-valid
payment card number with `[EMAIL]`, `[IP]`, and `[CARD]`, leaving every other byte untouched —
and end quietly with status 0 if the consumer stops reading.

**Independent Test**: Pipe a log excerpt containing an email address, an IPv4 address, and a
Luhn-valid card number into the tool with no arguments; standard output contains `[EMAIL]`,
`[IP]`, and `[CARD]` in those positions and is otherwise byte-identical to the input, stderr is
empty, exit status is 0.

### Tests for User Story 1 ⚠️

> **Write these FIRST and confirm they FAIL before implementing T016–T023.** Name each test after
> the FR id it covers (e.g. `test_fr007_plus_addressing`) so the SC-005 coverage audit in T038 can
> find it.

- [ ] T010 [P] [US1] Unit-test the Luhn checksum in `tests/unit/test_luhn.py`: over the separator-stripped digit string, `4111111111111111` passes and `1234567890123` fails; cover the "subtract 9 from any doubled value above 9" branch and a total that is divisible by 10 only by coincidence of that branch (FR-014, FR-015; contracts/redaction-rules.md "Luhn checksum")
- [ ] T011 [P] [US1] Unit-test per-type recognition and non-recognition in `tests/unit/test_patterns.py`, taking every row of the three tables in contracts/redaction-rules.md verbatim as a case: **email** — `jane@example.com`, `jane.doe+test@mail.example.com`, `jane@example.com, next` → `[EMAIL], next` (trailing punctuation not consumed, FR-008), `user@1.2.3.4` → `[EMAIL]`, `user@999.1.1.1` → `[EMAIL]` (no range check, FR-007a), `jane@example.c` unchanged (final label < 2 letters); **IPv4** — `10.0.0.7`, `0.0.0.0`, `255.255.255.255`, `010.0.0.7` (leading zeros accepted) redacted, `from 10.0.0.7.` → `from [IP].`, `999.1.1.1`, `256.1.1.1` unchanged, `1.2.3.4.5` unchanged **in full** (FR-010 – FR-012); **card** — `4111111111111111`, `4111 1111 1111 1111`, `4111-1111-1111-1111`, `4111-1111 1111-1111` (mixed separators) → `[CARD]`, `x4111111111111111y` → `x[CARD]y`, and unchanged for `1234567890123` (Luhn fails), `123456789012` (12 digits, too short), `12345678901234567890` (20 digits, too long), `4111  1111 1111 1111` (doubled separator), `2026-11-13 10:00:00` (FR-013 – FR-017)
- [ ] T012 [P] [US1] Unit-test match resolution in `tests/unit/test_precedence.py`: leftmost match wins and scanning resumes after the replaced span so nothing overlaps (FR-018); at a shared start position the order is email → IPv4 → card, asserted by `user@1.2.3.4` → `[EMAIL]` counted as an email and **not** `user@[IP]` (FR-019); and inserted placeholders are never re-matched or counted — input `[EMAIL] [IP] [CARD] unchanged` passes through identical with all counts `0` (FR-020)
- [ ] T013 [P] [US1] CLI-test byte fidelity in `tests/cli/test_output_fidelity.py` using `run_cli`: feed `b'caf\xe9 jane@example.com\r\nno trailing newline'` and assert the invalid byte `\xe9` survives unchanged, the CRLF is preserved, and no final newline is added (FR-005, FR-005b); assert input with nothing to redact comes back byte-identical (SC-003); and assert locale independence by running the same input under `LC_ALL=C` and under `LC_ALL=C.UTF-8 PYTHONIOENCODING=latin-1` and comparing the two stdout byte strings for equality (FR-005a)
- [ ] T014 [P] [US1] CLI-test the stdin path in `tests/cli/test_invocation.py` using `run_cli`: with no arguments the tool reads standard input (FR-002) and writes every input line exactly once in order with none added, dropped, reordered, or duplicated (FR-004); cover spec acceptance scenarios 1–6 — `user jane@example.com from 10.0.0.7` → `user [EMAIL] from [IP]`, `paid with 4111 1111 1111 1111, ref 1234567890123` → `paid with [CARD], ref 1234567890123`, a non-matching line byte-for-byte, `999.1.1.1` unchanged, several items on one line each replaced with its own placeholder, and `login from user@1.2.3.4` → `login from [EMAIL]`; assert stderr is empty and exit status is 0 throughout (FR-023, FR-024)
- [ ] T015 [P] [US1] CLI-test early consumer close in `tests/cli/test_broken_pipe.py`: pipe a long generated input through `python -m logredact` into `head -5` and assert exactly five redacted lines on stdout, **0 bytes** on stderr (no diagnostic, no `BrokenPipeError` traceback), and exit status `0`; repeat with `--count` and assert the summary is still absent (FR-028, FR-021)

### Implementation for User Story 1

- [ ] T016 [US1] Add the email branch to `src/logredact/redact.py` as a named group `email` with the pattern verbatim from research.md R-004: `[A-Za-z0-9._%+-]+@(?:(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}|\d{1,3}(?:\.\d{1,3}){3})` — local part is one or more of letters, digits, `.`, `_`, `%`, `+`, `-`; domain is either dot-separated labels of letters/digits/hyphens ending in a final label of **at least two letters**, or four dot-separated groups of **one to three digits** (FR-007, FR-007a, FR-008)
- [ ] T017 [US1] Add the IPv4 branch to `src/logredact/redact.py` as a named group `ip` with the pattern verbatim: `(?<!\d)(?<!\d\.)\d{1,3}(?:\.\d{1,3}){3}(?!\d)(?!\.\d)` — the four lookarounds are a direct transcription of FR-012 (not adjacent to a digit on either side, not preceded by digit-and-dot, not followed by dot-and-digit) (FR-010, FR-012)
- [ ] T018 [US1] Add the card branch to `src/logredact/redact.py` as a named group `card` with the pattern verbatim: `(?<!\d)\d++(?:[ -]\d++)*+` — the possessive quantifiers (Python 3.11+) make the candidate **maximal and non-backtrackable**, which is what makes the doubled-separator edge case work; the pattern deliberately carries **no `{13,19}` bound** because the digit count is only known after separators are stripped (research.md R-004; FR-014, FR-016, FR-017)
- [ ] T019 [US1] Compile the three branches into **one** module-level `re.compile` alternation in `src/logredact/redact.py` in the order `email | ip | card` — the branch order *is* the FR-019 precedence and `match.lastgroup` *is* the type tag; do not introduce an enum, registry, or per-type class (data-model.md "Redaction type"; Constitution Principle IV)
- [ ] T020 [US1] Implement `luhn(digits: str) -> bool` in `src/logredact/redact.py` as a pure function: walking right to left, double every second digit, subtract 9 from any doubled value above 9, sum all values, and return True when the total is divisible by 10 (research.md R-005; FR-014)
- [ ] T021 [US1] Implement the substitution callback and `redact_line(text) -> (text, counts)` in `src/logredact/redact.py`: dispatch on `match.lastgroup`; for `email` apply **no validation** and always replace (FR-007a); for `ip` require **every octet ≤ 255** or return `match.group(0)` unchanged in full, never partially (FR-010, FR-011); for `card` strip the separators, require a digit count of **13–19 inclusive** (FR-016) **and** `luhn()` to pass (FR-014, FR-015), otherwise return the whole candidate unchanged; increment the matching counter only when a replacement is actually made, and return a fresh counts dict from `new_counts()` per call (FR-013, FR-022)
- [ ] T022 [US1] Wire `redact_line` into the stdin loop in `src/logredact/cli.py`: iterate the stream line by line (`for line in stream:`) and write each redacted line to stdout **immediately**, accumulating nothing — memory must stay bounded by the longest single line, not by input size (research.md R-008; SC-007)
- [ ] T023 [US1] Handle early consumer close in `src/logredact/cli.py`: wrap the whole write path in `except BrokenPipeError`, and on catch `os.dup2(os.open(os.devnull, os.O_WRONLY), 1)` before returning `0` — the `dup2` is required because the interpreter's shutdown flush would otherwise print `Exception ignored in:` to stderr; nothing may be written to stderr and the status must be `0`, not 1 and not 141 (research.md R-006; FR-028)

**Checkpoint**: User Story 1 is fully functional and testable on its own — `… | python -m logredact`
redacts all three types with byte-exact passthrough, and `| head -5` ends silently with status 0.
**This is the MVP.**

---

## Phase 4: User Story 2 - Sanitize one or more named log files (Priority: P2)

**Goal**: Read each FILE named on the command line, in the order given, into one sanitized output
stream, without reading standard input at all.

**Independent Test**: Run the tool with two files as arguments and confirm standard output is the
redacted contents of the first file followed by the redacted contents of the second, in that
order, with exit status 0.

### Tests for User Story 2 ⚠️

- [ ] T024 [US2] Extend `tests/cli/test_invocation.py` with the named-file cases (same file as T014, so sequential after it): two readable files named in order produce the first file's redacted lines then the second's with none reordered, dropped, or duplicated; one file named twice produces its contents twice; an empty file produces empty stdout and exit 0; standard input is **not read at all** when files are named — assert this by passing non-empty stdin whose content never appears in stdout; and `a.log --count b.log` with the flag between two filenames is accepted and equivalent to `--count a.log b.log` (FR-001, FR-003, FR-004)

### Implementation for User Story 2

- [ ] T025 [US2] Implement per-source opening in `src/logredact/cli.py`: open each FILE with `encoding="utf-8", errors="surrogateescape", newline="\n"` (identical to the stdin configuration from T007), **lazily one at a time**, closing each before the next is opened, so a failure on source *n* leaves sources *n+1…* unopened (data-model.md "Input source"; research.md R-002)
- [ ] T026 [US2] Implement source selection in `main()` in `src/logredact/cli.py`: an empty `files` list means exactly one source, standard input (FR-002); one or more FILE arguments means one source per argument **in command-line order**, and `sys.stdin` is never opened or read (FR-003); a filename repeated on the command line is a separate source each time and is read again
- [ ] T027 [US2] Route every source through the T022 line loop in `src/logredact/cli.py` so output is written in input order with each line emitted exactly once and nothing buffered across source boundaries (FR-004, SC-007)

**Checkpoint**: User Stories 1 and 2 both work independently — piped input and named files.

---

## Phase 5: User Story 3 - See how much was redacted (Priority: P3)

**Goal**: With `--count`, report `emails=N ips=N cards=N` once on stderr after all output, covering
every source in the run.

**Independent Test**: Run the tool with `--count` over input with a known number of each identifier
and confirm the summary line on standard error reports exactly those numbers while standard output
is unaffected.

### Tests for User Story 3 ⚠️

- [ ] T028 [P] [US3] Unit-test counting in `tests/unit/test_counting.py`: a counter increments **once per replacement actually made, not per distinct value** — the same address three times counts as three (FR-022); a candidate rejected by validation (out-of-range octet, 12 or 20 digits, failed Luhn) increments nothing because no replacement was made; placeholder text present in the input is never matched so is never counted (FR-020); and every count is reported as `0` when no replacement of that type was made
- [ ] T029 [P] [US3] CLI-test the flag in `tests/cli/test_count_flag.py` using `run_cli`: `a@b.io 1.2.3.4` with `--count` gives `[EMAIL] [IP]` on stdout and exactly `emails=1 ips=1 cards=0` on stderr — all three keys, always that order, single-space separated, one line (FR-021); input with nothing to redact gives `emails=0 ips=0 cards=0`; multiple named files give a **single** combined summary printed once after all output; without `--count` stderr is empty and exit status is 0 (FR-023); and for every case the three counts equal the number of placeholders of each type present in stdout (SC-004)

### Implementation for User Story 3

- [ ] T030 [US3] Accumulate the per-line counts returned by `redact_line` into three run-level integers in `main()` in `src/logredact/cli.py`, totalled across **every** source in the run; keep them local to the run — no module-level or global counters (data-model.md "Redaction counts"; FR-022)
- [ ] T031 [US3] Emit the summary in `src/logredact/cli.py`: when `--count` was given and the run processed every input to the end, call `sys.stdout.flush()` **first**, then write exactly `emails=N ips=N cards=N` followed by a newline to `sys.stderr`, so the summary always follows the complete output even when both streams are redirected to the same file (research.md R-007 "Ordering"; FR-021)
- [ ] T032 [US3] Ensure the summary is suppressed on the early-close path in `src/logredact/cli.py` — the `BrokenPipeError` handler from T023 must return `0` **before** any summary is written (FR-021, FR-028)

**Checkpoint**: User Stories 1, 2, and 3 all work independently.

---

## Phase 6: User Story 4 - Fail clearly when a log file cannot be read (Priority: P4)

**Goal**: Name the file that could not be read, stop, suppress the summary, and exit 2 — so an
incomplete sanitized stream is never mistaken for a complete one. Likewise reject an unrecognised
command-line argument with a usage diagnostic naming it.

**Independent Test**: Run the tool naming a file that does not exist and confirm standard error
names that file and the exit status is 2.

### Tests for User Story 4 ⚠️

- [ ] T033 [P] [US4] CLI-test failures in `tests/cli/test_failures.py` using `run_cli`, asserting **no stack trace** in stderr for any case: a named file that does not exist → stderr contains that file's name **as given on the command line** and exit 2 (FR-025); a file that exists but cannot be opened (created then `chmod 000`, skipped when running as root) → named, exit 2; a directory argument → named, exit 2 (clarification 2026-11-13); a readable file followed by an unreadable one followed by a third → the first file's redacted output is on stdout, the second is named on stderr, the **third is never read**, and exit is 2 (FR-026, FR-027); the same case with `--count` → **no summary** is printed (FR-026); every named file readable → stderr empty and exit 0 (FR-024); and `--redact-all` → stderr carries a usage message naming `--redact-all`, stdout is **empty**, no summary, and exit 2 (FR-029). Assert across the whole file that no exit status other than 0 or 2 is ever observed (SC-006)

### Implementation for User Story 4

- [ ] T034 [US4] Wrap both the `open()` call and the per-source read loop in `src/logredact/cli.py` in `except OSError` — the single narrow base class covering non-existence, permission denied, a directory, and a mid-read failure; on catch write `python -m logredact: <name>: <reason>` to stderr using the filename **exactly as given on the command line**, never normalised or made absolute (research.md R-007; contracts/cli-contract.md "Unreadable FILE"; FR-025)
- [ ] T035 [US4] On that failure, stop processing in `src/logredact/cli.py`: break out of the source loop so no later FILE is opened, and return exit status `2`; output already written for earlier sources stays on stdout, valid and complete up to the point of failure (FR-026, FR-027)
- [ ] T036 [US4] Gate the T031 summary on run completion in `src/logredact/cli.py` so the `--count` summary is **not** printed on the FR-025 failure path, and an incomplete run is never presented as a complete one (FR-026, Constitution Principle II)
- [ ] T037 [US4] Confirm the FR-029 usage path end to end in `src/logredact/cli.py`: `parse_intermixed_args` raises `SystemExit(2)` after printing `usage: python -m logredact [--count] [FILE ...]` and an error naming the offending argument; ensure no handler in `cli.py` or `__main__.py` catches `SystemExit` or rewrites that status, that no input is read, and that stdout stays empty (FR-029, SC-006)

**Checkpoint**: All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The Constitution merge gate and the spec's measurable success criteria.

- [ ] T038 [P] Audit requirement coverage across `tests/`: confirm each of FR-001 … FR-029 appears in at least one test name or docstring and that the test genuinely fails when the requirement is unmet; add tests for any gap found, and likewise for every bullet in spec.md "Edge Cases" (SC-005; Constitution Principle III)
- [ ] T039 [P] Run all nine scenarios in `specs/001-redact-log-pii/quickstart.md` exactly as written and confirm each produces its stated stdout, stderr, and exit status; tick the acceptance checklist at the end of that file
- [ ] T040 Verify streaming performance (SC-007): generate a 1,000,000-line log, run `time python -m logredact --count big.log > /dev/null`, confirm it completes in under 60 seconds, and confirm RSS does not grow with input size by comparing peak memory against a 10,000-line run
- [ ] T041 [P] Confirm no third-party import appears anywhere under `src/` — only `re`, `argparse`, `sys`, and `os` — and that nothing under `src/` imports `pytest` (Constitution Principle I)
- [ ] T042 Audit exit statuses in `src/logredact/`: confirm every `return` from `main()` and every `SystemExit` yields only `0` or `2`, and that no `except` clause is broader than `OSError` or `BrokenPipeError` (SC-006; Constitution Principle II)
- [ ] T043 Run a bare `pytest` from the repository root with no arguments and confirm the full suite passes on a clean checkout (Constitution Development Workflow gate 4)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS all user stories.**
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on US2–US4.
- **User Story 2 (Phase 4)**: Depends on Foundational. Reuses the T022 line loop from US1, so in practice follows US1.
- **User Story 3 (Phase 5)**: Depends on Foundational. Counts returned by `redact_line` (T021) make it natural to follow US1; T032 touches the T023 handler.
- **User Story 4 (Phase 6)**: Depends on Foundational. The file-reading path from US2 (T025, T026) must exist for T034/T035 to guard it — this is the one genuine cross-story dependency, and matches the spec's own priority rationale ("only matters once the file-reading path of Story 2 exists").
- **Polish (Phase 7)**: Depends on all four stories.

### User Story Dependencies

- **US1 (P1)**: Independent. Deliverable alone as the MVP.
- **US2 (P2)**: Independent at the contract level (its own test is two named files). Shares the redaction core with US1.
- **US3 (P3)**: Independent at the contract level (`--count` over stdin alone demonstrates it). Needs US1's counters.
- **US4 (P4)**: Needs US2's file-opening path. The FR-029 usage half (T037) is independent of all three.

### Within Each User Story

- Tests are written first and MUST fail before the matching implementation task begins.
- Patterns (T016–T019) before the validator and callback (T020, T021) before the CLI wiring (T022).
- Source selection (T026) before failure handling around it (T034).
- Each story reaches its checkpoint before the next priority starts.

### Parallel Opportunities

- **Setup**: T002 and T003 in parallel after T001.
- **Foundational**: T004 and T005 in parallel; T006–T008 are all `cli.py` and must be sequential; T009 is a different file and can run alongside T004/T005.
- **US1 tests**: T010–T015 are six different files — all six in parallel.
- **US1 implementation**: T016–T021 all edit `redact.py` and must be sequential; T022/T023 then follow in `cli.py`.
- **US3 tests**: T028 and T029 in parallel (different files).
- **Across stories**: once Foundational completes, one developer can take US1 while another writes the US3 and US4 test files (T029, T033), which depend only on the CLI contract, not on the implementation.
- **Polish**: T038, T039, T041 in parallel; T040, T042, T043 sequential at the end.

---

## Parallel Example: User Story 1

```bash
# All six User Story 1 test files are independent — launch together:
Task: "Unit-test the Luhn checksum in tests/unit/test_luhn.py"
Task: "Unit-test per-type recognition and non-recognition in tests/unit/test_patterns.py"
Task: "Unit-test match resolution in tests/unit/test_precedence.py"
Task: "CLI-test byte fidelity in tests/cli/test_output_fidelity.py"
Task: "CLI-test the stdin path in tests/cli/test_invocation.py"
Task: "CLI-test early consumer close in tests/cli/test_broken_pipe.py"

# Confirm all six FAIL, then implement T016–T023 sequentially (T016–T021 share redact.py).
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (T001–T003)
2. Phase 2: Foundational (T004–T009) — **blocks everything**
3. Phase 3: User Story 1 (T010–T023)
4. **STOP and VALIDATE**: quickstart Scenarios 1, 2, 7, and 8 all pass; `pytest tests/unit tests/cli` is green
5. The tool already solves the user's problem for the common case — a sanitized log via a pipe.

### Incremental Delivery

1. Setup + Foundational → a working no-op filter with the right encoding contract
2. + US1 → redaction over stdin, byte-exact, broken-pipe safe → **MVP, demo-able**
3. + US2 → named files in order
4. + US3 → `--count` summary
5. + US4 → clear, fail-fast diagnostics and exit 2
6. + Polish → SC-005 coverage audit, SC-007 performance, Constitution gate

Each step leaves the previous ones working.

### Parallel Team Strategy

1. Everyone on Setup + Foundational together.
2. Then: Developer A takes US1 (the core, and the longest phase); Developer B writes the US3 and
   US4 test files against the CLI contract while A implements; Developer C takes US2 as soon as
   T022 lands.
3. US4 implementation waits on US2's file path; everything else integrates independently.

---

## Notes

- `[P]` means a different file and no dependency on an incomplete task. Tasks touching
  `src/logredact/redact.py` or `src/logredact/cli.py` are never `[P]` with each other.
- Name every test after the FR id it covers — the T038 coverage audit depends on it.
- Patterns in T016–T018 are quoted verbatim from research.md R-004 and were verified by execution
  during Phase 0. Do not "improve" them; the lookarounds and possessive quantifiers each
  implement a specific requirement.
- The known consequence of the maximal-card-candidate rule (`code 7-4111 1111 1111 1111` is one
  17-digit candidate that fails Luhn, so nothing is redacted) follows from the spec's own
  doubled-separator edge case. Implement the spec; do not special-case it. See plan.md "Note for
  review".
- Commit after each task or logical group. Stop at any checkpoint to validate a story on its own.
