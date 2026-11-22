---

description: "Task list for Log Data Redaction CLI"
---

# Tasks: Log Data Redaction CLI

**Input**: Design documents from `/specs/001-log-data-redaction-cli/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [contracts/redaction-rules.md](./contracts/redaction-rules.md), [quickstart.md](./quickstart.md)

**Tests**: **REQUIRED, not optional.** FR-018 mandates that every functional and security requirement be covered by at least one automated `pytest` test including negative tests asserting both exit status and message content; SC-009 requires the suite to pass with no skipped or expected-failure tests; Constitution Principle III forbids skipping or `xfail`-ing a known-failing test. Test tasks below are therefore first-class deliverables, written before the implementation they cover.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and delivered independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths are included in every task

## Path Conventions

Single-project CLI layout, mandated by FR-001 and fixed in plan.md **Structure Decision**:

- `pyproject.toml` at repository root (pytest configuration only)
- `src/logredact/` — the package: `__init__.py`, `__main__.py`, `cli.py`, `redact.py`
- `tests/` — pytest suite at repository root

All paths below are relative to the repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton and test-runner configuration. Nothing here contains feature logic.

- [X] T001 Create `pyproject.toml` at the repository root containing **only** `[tool.pytest.ini_options]` with `pythonpath = ["src"]` and `testpaths = ["tests"]`; it MUST declare no dependencies and no build backend, so nothing needs installing and no runtime dependency is introduced (research.md D-009, Constitution Principle I)
- [X] T002 [P] Create the package marker `src/logredact/__init__.py` — empty, no logic of any kind (plan.md Structure Decision: "`__init__.py` is the package marker FR-001 implies, with no logic in it")
- [X] T003 [P] Confirm the toolchain matches quickstart.md **Prerequisites**: `python3 --version` reports **3.11 or newer**, and `pytest` is importable as developer tooling only; record the observed versions in the implementation notes and create no files while checking

**Checkpoint**: `pytest` collects zero tests without error and `src/logredact` is importable with `PYTHONPATH=src`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Module skeletons, shared constants, the recognition patterns, the testable `main()` signature, and the encoding/stream policy that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Create `src/logredact/redact.py` with the placeholder constants and compiled patterns from contracts/redaction-rules.md, transcribed verbatim: placeholders are the exact literals `[EMAIL]`, `[IP]`, `[CARD]` with no padding, length hint, hash, or counter (§6); one combined alternation `(?P<email>…)|(?P<ip>…)` in that rank order where the email alternative is `(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,256}@(?:[A-Za-z0-9-]{1,63}\.){1,16}[A-Za-z]{2,63}(?![A-Za-z0-9-])` and the IPv4 alternative is `(?<![0-9.])OCTET(?:\.OCTET){3}(?![0-9.])` with `OCTET := (?:25[0-5]|2[0-4][0-9]|[01][0-9][0-9]|[0-9][0-9]|[0-9])`; plus `DIGIT_RUN = re.compile(r"[0-9]+")` for maximal digit runs. Every character class MUST be written out explicitly — `\d`, `\w`, and `\b` MUST NOT appear anywhere in the file, because on `str` patterns `\d` also matches non-ASCII decimal digits (research.md D-004)
- [X] T005 Create `src/logredact/cli.py` with `MAX_LINE = 1024 * 1024` (**1 048 576 characters** of decoded content, SR-005), a `build_parser()` returning `argparse.ArgumentParser(prog="python -m logredact")` with `--count` as `action="store_true"` and `files` as `nargs="*"` (research.md D-007, FR-012), and the signature `def main(argv: list[str], *, stdin=None, stdout=None, stderr=None) -> int` that **returns** an exit status and never raises `SystemExit`, with the three streams defaulting to the real `sys` streams when omitted (contracts/cli.md "Internal entry point", research.md D-008)
- [X] T006 [P] Create `src/logredact/__main__.py` as a thin shell only — import `main` from `.cli` and `sys.exit(main(sys.argv[1:]))` — with no argument handling, no I/O setup, and no logic, because importing this module executes it and tests must import `cli` instead (plan.md Structure Decision)
- [X] T007 [P] Create `tests/conftest.py` with the shared helpers every CLI test uses: a `run_cli(args, stdin_bytes=b"", cwd=None)` helper that runs `python -B -m logredact` as a subprocess with `PYTHONPATH=src` and `PYTHONDONTWRITEBYTECODE=1`, returning **raw `bytes`** stdout and stderr plus the integer exit status (byte-level, never text-decoded, because FR-003, FR-017 and SR-002 are assertions about bytes); a `call_main(argv, stdin_text="")` helper that calls `cli.main(...)` in process with injected stream objects; and the shared sample constants used across the suite (`jane@example.com`, `10.0.0.7`, `4111 1111 1111 1111`, `1234567890123`)
- [X] T008 Implement the encoding and stream policy in `src/logredact/cli.py`: every input file is opened with `open(path, "r", encoding="utf-8", errors="surrogateescape", newline="")` — read-only mode `"r"`, never a create, truncate, or append mode (SR-008) — and injected or real stdin/stdout are used with the same `encoding="utf-8"`, `errors="surrogateescape"`, `newline=""` settings so undecodable bytes round-trip to the original bytes and newline sequences (`\n`, `\r\n`, lone `\r`) are neither translated nor normalised (research.md D-001, FR-003, FR-017)

**Checkpoint**: Foundation ready — the patterns compile, `main([])` is callable with injected streams, and user story implementation can begin.

---

## Phase 3: User Story 1 - Redact a log stream before sharing it (Priority: P1) 🎯 MVP

**Goal**: `python -m logredact` reads standard input and writes every line to standard output with emails replaced by `[EMAIL]`, IPv4 addresses by `[IP]`, and Luhn-valid 13–19 digit card numbers by `[CARD]`, leaving everything else byte-for-byte unchanged. This phase delivers the complete redaction engine — a usable product on its own.

**Independent Test**: Feed a known log sample on standard input with no file arguments and no flags; confirm standard output contains the expected placeholders, contains none of the original sensitive values as a substring, and leaves all other text byte-for-byte identical, with exit status 0 and empty stderr.

### Tests for User Story 1 ⚠️ Write these FIRST and confirm they FAIL before implementing

- [X] T009 [P] [US1] Write `tests/test_redact_email.py` covering FR-004 and SR-002: local part of 1+ characters from letters, digits, `.`, `_`, `%`, `+`, `-`; a single `@`; 1+ dot-separated labels of letters, digits, `-`; final label **at least two characters, letters only**. Assert from contracts/redaction-rules.md §1: `jane.doe+test@mail.example.com` → `[EMAIL]`, `a@b.io` → `[EMAIL]`, `jane@example.com.` → `[EMAIL].` (trailing dot is a separator, not a label character), `a@b.co1` → **unchanged** (truncating to `a@b.co` is forbidden), `a@1.2.3.4` → `a@[IP]`, and a **300-character local part** + `@b.io` → unchanged with **no partial match emitted** (exceeds the `{1,256}` bound; SR-002 requires the whole value survive intact rather than leaking a prefix)
- [X] T010 [P] [US1] Write `tests/test_redact_ipv4.py` covering FR-005: exactly four dot-separated octets of 1–3 digits each with numeric value **0 to 255 inclusive**, leading zeros permitted. Assert from contracts/redaction-rules.md §2: `10.0.0.7` → `[IP]`, `010.0.0.7` → `[IP]` (value 10), `999.1.1.1` → unchanged, `1.2.3.4.5` → unchanged, `256.1.1.1` → unchanged, `a@1.2.3.4` → `a@[IP]`; include a match flush against line start and line end
- [X] T011 [P] [US1] Write `tests/test_redact_card.py` covering FR-006 and FR-007: **13 to 19 digits inclusive** counting digits only, contiguous or in groups of 1+ digits joined by **single** `' '` or `'-'` separators with separators never at the start or end of the match and kinds mixable, Luhn must pass, and the character immediately before or after the match must not be a digit. Assert from contracts/redaction-rules.md §3: `4111 1111 1111 1111` → `[CARD]`, `4111-1111 1111-1111` → `[CARD]`, `4111  1111 1111 1111` (double separator) → unchanged, `4111 1111 1111 1111 1234` → `[CARD] 1234`, `1234567890123` → unchanged (13 digits, Luhn fails), `x4111111111111111` → `x[CARD]`, `edge4111111111111111edge` → `edge[CARD]edge`, a 20+ contiguous digit run → unchanged, a 12-digit Luhn-valid run → unchanged, and `١٢٣٤٥٦٧٨٩٠١٢٣` (non-ASCII digits) → unchanged
- [X] T012 [P] [US1] Write `tests/test_precedence.py` covering FR-008 and FR-009: precedence is **email (1) → IPv4 (2) → card (3)**, applied **before** position, so a higher-ranked match suppresses an overlapping card candidate even one starting earlier; within a category leftmost wins and at a shared start the longest valid candidate wins; matches never overlap; placeholders are never nested, never doubly substituted, and **never re-scanned**. Assert from contracts/redaction-rules.md §4: `12345678903@example.com` → `[EMAIL]`, `4111111111111111@a.com` → `[EMAIL]`, `a@1.2.3.4` → `a@[IP]`, `12 34.5.6.7` → `12 [IP]`, `12 34@x.com` → `12 [EMAIL]`, `a@b.io 1.2.3.4` → `[EMAIL] [IP]`; and assert input already containing the literal text `[EMAIL]` is passed through without a second substitution
- [X] T013 [P] [US1] Write `tests/test_cli_stream.py` covering FR-001, FR-002 (stdin read when no FILE), FR-003 and SC-003 via `run_cli` subprocess runs asserting **raw bytes**: `user jane@example.com from 10.0.0.7\n` → exactly `user [EMAIL] from [IP]\n` with exit status 0 and empty stderr; `paid with 4111 1111 1111 1111, ref 1234567890123` → `paid with [CARD], ref 1234567890123`; a line with nothing redactable returned byte-identical including its original whitespace and punctuation; input whose final line has **no trailing newline** produces output with **no newline added** (assert the final byte is not `0x0a`, US1-6); and `\r\n` and lone `\r` terminators preserved exactly
- [X] T014 [P] [US1] Write `tests/test_encoding.py` covering FR-017 and research.md D-001: feed `b"caf\xe9 jane@example.com \xff\xfe 10.0.0.7\n"` and assert the output bytes are the input bytes with only the email and IPv4 spans replaced — the `\xe9`, `\xff`, and `\xfe` bytes appear **unchanged**, no `\xef\xbf\xbd` (U+FFFD) substitution appears anywhere, exit status is 0, and redaction of the embedded values still fired

### Implementation for User Story 1

- [X] T015 [US1] Implement the Luhn checksum in `src/logredact/redact.py` over a string of ASCII digits: right to left, double every second digit, subtract 9 from any doubled value above 9, sum all, valid when the sum mod 10 is 0 (contracts/redaction-rules.md §3). It MUST be reached only with ASCII `[0-9]` characters, which T004's explicit classes guarantee
- [X] T016 [US1] Implement card candidate detection in `src/logredact/redact.py` as a pure function over a text slice, following research.md D-003 / contracts/redaction-rules.md §3 exactly: find **maximal** ASCII digit runs with `DIGIT_RUN`; chain two consecutive runs when **exactly one** separating character is present and it is `' '` or `'-'` (mixed kinds allowed, a double separator does not chain); for each run *i* left to right, walk forward over chained runs accumulating the digit total and **stop as soon as the total exceeds 19**, recording the **largest** *j* whose total is **13–19** digits and whose concatenated digits pass Luhn; on a recorded candidate emit a match from the start of run *i* to the end of run *j* and resume at run *j+1*, otherwise advance to run *i+1*. Maximal runs are what make FR-007's digit-adjacency rule fall out with no separate boundary test, and the ≤19 stop is what bounds enumeration to at most 19 runs per start position (SR-006)
- [X] T017 [US1] Implement `redact_line(line) -> tuple[str, dict[str, int]]` in `src/logredact/redact.py` as the three-stage pipeline of research.md D-003: (1) `finditer` the combined email/IPv4 alternation for leftmost, non-overlapping, rank-ordered matches; (2) run card detection **only inside the gaps** stage 1 left uncovered, which is what implements the rest of FR-008's precedence; (3) sort matches by start position as `tuple[int, int, str]` values satisfying `previous.end <= next.start` (data-model.md §5) and rebuild the line by concatenating **verbatim** input slices with **literal** placeholder strings. No `re.sub` replacement template may be used, so `\1`, `\g<0>`, `${x}`, or the text `[EMAIL]` appearing in the input cannot alter a substitution (SR-004, G-2), and appended placeholder text is never re-scanned (FR-008). Return the counts dict keyed `"emails"`, `"ips"`, `"cards"` with one increment per replacement, from the start — US3 only wires it to stderr
- [X] T018 [US1] Wire the standard-input path in `src/logredact/cli.py` `main()`: when `Options.files` is empty the single source is stdin named `<stdin>` (data-model.md §2); read it with `stream.readline(MAX_LINE + 1)` rather than `for line in stream` or bare `readline()`, both of which are unbounded (research.md D-002, SR-005); pass each chunk through `redact_line`, write the result to stdout, and return 0 after the final flush succeeds. Emitting each line with its terminator exactly as read, and adding none to an unterminated final line, is FR-003/US1-6
- [X] T019 [US1] Run `pytest tests/test_redact_email.py tests/test_redact_ipv4.py tests/test_redact_card.py tests/test_precedence.py tests/test_cli_stream.py tests/test_encoding.py` and confirm all pass with no skips and no xfail, then execute quickstart.md **Scenario 1** including the `xxd | tail -1` no-trailing-newline check and the `diff sample.log redacted.log` check

**Checkpoint**: User Story 1 is fully functional and independently testable — `printf '…' | python -m logredact` redacts all three categories correctly. **This is the MVP.**

---

## Phase 4: User Story 2 - Redact one or more named log files in order (Priority: P2)

**Goal**: Named FILE arguments are read in the order given and emitted as one concatenated redacted stream on standard output; standard input is not read at all when FILEs are present.

**Independent Test**: Create two small files with known content, run the tool with both paths, and confirm standard output is the redacted concatenation in argument order; then pipe text into a run with a FILE argument and confirm that piped text never appears in the output and the run does not block.

### Tests for User Story 2 ⚠️ Write these FIRST and confirm they FAIL before implementing

- [X] T020 [P] [US2] Write `tests/test_cli_files.py` covering FR-002, FR-012, US2-1 through US2-5: `python -m logredact a.log b.log` emits all redacted lines of `a.log` before all of `b.log` with exit status 0; naming the two files in reverse order reverses the output order; an empty file contributes nothing to stdout and still exits 0; the **same file named twice** has its redacted content emitted **twice**; piping `SHOULD NOT APPEAR\n` into a run with at least one FILE argument terminates immediately without blocking and that text is absent from the output (stdin is never opened or read); and `--count` in any position among the FILE arguments (`--count a b`, `a --count b`, `a b --count`) yields identical stdout, with all non-option arguments treated as FILE paths in the given order

### Implementation for User Story 2

- [X] T021 [US2] Implement source iteration in `src/logredact/cli.py` as a generator yielding `(name, stream)` pairs — not a class (data-model.md §2, Principle IV): stdin named `<stdin>` when `Options.files` is empty, otherwise each FILE opened **lazily when reached** with the read-only settings from T008 and **closed before the next source is opened**. A FILE of `-` is a literal relative path, never a stdin alias (contracts/cli.md Arguments). Paths are used **verbatim** — not resolved, normalised, or containment-checked — per SR-009, and no path is ever opened for writing (SR-008)
- [X] T022 [US2] Extend `main()` in `src/logredact/cli.py` to consume every source from T021's generator in argument order, applying the same bounded `readline(MAX_LINE + 1)` loop and `redact_line` call as the stdin path, so output for file *n* is written before file *n+1* is opened (contracts/cli.md "Ordering and failure semantics", US2-1/US2-2) and so stdin is never touched when FILEs are present (FR-002, US2-5)
- [X] T023 [US2] Run `pytest tests/test_cli_files.py` plus the full suite to confirm no regression in User Story 1, then execute quickstart.md **Scenario 2** including the stdin-not-read check

**Checkpoint**: User Stories 1 and 2 both work independently — streaming and multi-file batch redaction are both usable.

---

## Phase 5: User Story 3 - Confirm how much was redacted (Priority: P3)

**Goal**: With `--count`, exactly one summary line `emails=N ips=N cards=N` is written to standard error after all redacted output has been written and flushed, so a reviewer can capture the tally separately from the redacted log.

**Independent Test**: Run with `--count` on input with a known number of each category, redirect the two streams to separate files, and confirm the redacted log contains no `emails=` text, the summary contains no log text, and the tally matches an independent manual count.

### Tests for User Story 3 ⚠️ Write these FIRST and confirm they FAIL before implementing

- [X] T024 [P] [US3] Write `tests/test_cli_count.py` covering FR-010, FR-011, FR-012, SR-003, SC-004 and SC-005: `a@b.io 1.2.3.4\n` with `--count` gives stdout `[EMAIL] [IP]\n` and stderr **exactly** `emails=1 ips=1 cards=0\n` — lowercase keys, single `=`, single spaces, newline-terminated, no leading or trailing padding; input with no redactable values gives `emails=0 ips=0 cards=0`; empty input gives `emails=0 ips=0 cards=0`; counts across **multiple files with multiple occurrences per line** are totals of **replacements**, not of affected lines, files, or distinct values, so the same email twice counts twice (US3-3); the summary appears on stderr **only** and never on stdout, and only **after** all redacted output is written and flushed (US3-4); a run **without** `--count` leaves stderr **empty** (FR-011, INV-7); and stdout for a given input is **byte-identical** with and without `--count`, proving the flag affects only the summary and never the redaction (SR-003)

### Implementation for User Story 3

- [X] T025 [US3] Accumulate the three counters in `src/logredact/cli.py` `main()` across all sources as three `int` locals or one `dict[str, int]` — not a class (data-model.md §6, Principle IV) — adding each `redact_line` counts delta as the output line is written, so the totals are monotonically non-decreasing replacement counts over all input
- [X] T026 [US3] Emit the summary in `src/logredact/cli.py` on the success path only: after the final stdout flush has **succeeded**, and only when `Options.count` is set, write exactly `f"emails={e} ips={i} cards={c}\n"` to stderr, then return 0. It MUST NOT be written before the flush, MUST NOT be written to stdout, and MUST NOT be written on any failing run (FR-010, US3-4, US4-5). The summary is three integers and by construction carries no input content (SR-001)
- [X] T027 [US3] Run `pytest tests/test_cli_count.py` plus the full suite, then execute quickstart.md **Scenario 3** including the three flag-position runs and the stream-separation check on `/tmp/out.txt` and `/tmp/err.txt`

**Checkpoint**: User Stories 1, 2, and 3 all work independently — redaction, batch files, and the reviewable tally.

---

## Phase 6: User Story 4 - Learn immediately when an input cannot be read (Priority: P3)

**Goal**: An unreadable FILE or an unrecognised option names the problem on standard error and exits with status 2, so a surrounding script can stop instead of trusting a short, apparently-complete log.

**Independent Test**: Run against a non-existent path, a directory, an injected `PermissionError`, and an unknown option; confirm each writes a diagnostic naming the problem to stderr and exits 2 — distinguishable from success by status alone, with no case exiting 0.

### Tests for User Story 4 ⚠️ Write these FIRST and confirm they FAIL before implementing

- [X] T028 [P] [US4] Write `tests/test_cli_errors.py` covering FR-013, FR-014, SR-001, SR-009, SC-006 and US4-1 through US4-6, each asserting **both** the exit status and the message content (Constitution Principle III): a path that does not exist → message naming that path on stderr, exit **2**; a **directory** path → same, exit **2** (the real `IsADirectoryError` path, which reproduces on any uid); **permission denied** simulated by monkeypatching the `cli` module's `open` to raise `PermissionError` → message naming that path, exit **2** (research.md D-008: the environment runs as root, where `chmod 000` does not prevent reading, and Principle III forbids a `skipif` or `xfail` on uid); two FILE arguments where the first is readable and the second is not → the first file's redacted content is **already on stdout**, the error naming the **second** file is on stderr, exit **2**, and the third file in a three-argument run is **never opened** (US4-4, "Failure timing"); an **unrecognised option** → argparse usage message on stderr, exit **2** (US4-6); `--count` together with a failing path → stderr contains **no** `emails=` text at all (US4-5); and in every failure case assert stderr contains **no stack trace** (`Traceback` absent, SR-009) and no input line content, matched value, or fragment of one — only the caller's own supplied path (SR-001). Also assert `-h`/`--help` writes usage to **stdout** and exits **0** (contracts/cli.md Arguments)

### Implementation for User Story 4

- [X] T029 [US4] Handle open and read failures in `src/logredact/cli.py`: wrap the lazy open and the read loop so `OSError` and its subclasses `FileNotFoundError`, `PermissionError`, and `IsADirectoryError` are caught, a one-line diagnostic naming the path and reporting that it cannot be read is written to stderr, and **2** is returned (FR-013, data-model.md §2). The `except OSError` exists to add context and report, never to discard — no bare `except:` and no `except Exception:` that swallows (Constitution Principle II). The diagnostic must contain only the caller's supplied path, never input content (SR-001), and never a traceback (SR-009)
- [X] T030 [US4] Make the usage-error path return rather than raise in `src/logredact/cli.py`: `argparse` writes its usage message and raises `SystemExit(2)` on an unrecognised option and `SystemExit(0)` on `-h`/`--help`, so wrap `parse_args` to catch `SystemExit` and **return its code** from `main()`, and route argparse's own output to the **injected** `stderr`/`stdout` (e.g. `contextlib.redirect_stderr`/`redirect_stdout`) so in-process tests observe it — argparse otherwise writes straight to the real `sys` streams. `main()` must still never raise `SystemExit` (contracts/cli.md "Internal entry point", FR-014)
- [X] T031 [US4] Confirm in `src/logredact/cli.py` that every early `return 2` path bypasses the T026 summary write, so no `emails=… ips=… cards=…` line is produced on a failing run even when `--count` was requested (US4-5), and that output already written to stdout is kept rather than discarded (US4-4)
- [X] T032 [US4] Run `pytest tests/test_cli_errors.py` plus the full suite, then execute quickstart.md **Scenario 4** confirming `status=2` for the missing path, the directory, and `--bogus`, the partial-output case, and the `grep -c 'emails='` check returning 0

**Checkpoint**: All four user stories are independently functional. Every documented failure path reports on stderr and exits 2.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The remaining security requirements, bounds, and performance guarantees that span all four stories, plus the constitution's gate checks.

**⚠️ MANDATORY, not optional**: SR-005 through SR-009 and SC-007 through SC-010 are requirements, and the constitution's **Implementation gate** ("the full `pytest` suite passes; every new or changed requirement has at least one test; failure paths assert both failure signal and message; applicable Security Baseline controls are implemented and covered by negative tests") is not satisfied until this phase is complete. These tasks are deferred to this phase only because they cut across every story, not because they are discretionary.

- [X] T033 [P] Write `tests/test_limits.py` covering SR-005 and FR-016: a line whose content exceeds **1 048 576** characters fails with exit **2** and a stderr message that names the input source, states the limit, and **does not quote the line** (SR-001); a line of content **exactly at** the limit succeeds with exit 0; and peak memory stays bounded by the per-line limit on an input far larger than the limit in total, demonstrating that total input size is unbounded (INV-3, SC-007)
- [X] T034 [P] Write `tests/test_security.py` covering SR-001, SR-002, SR-003, SR-004, SR-007, SR-008, SR-009, FR-015 and SC-010 with negative tests per Constitution Principle V: no input line content, matched value, or fragment appears in any diagnostic or in the summary; the original email, IPv4, and card values are absent as **substrings** of the output, with no prefix or suffix surviving (SR-002, INV-2); all three categories redact with no flag and no option exists that disables or weakens one (SR-003); input containing `\1`, `\g<0>`, `${x}`, the literal `[EMAIL]`, and shell and format metacharacters passes through inertly and cannot alter a substitution, and no shell or subprocess is invoked by the tool (SR-004, G-1, G-2, INV-5); an `OSError` raised by an injected stdout stream's `write` or `flush` is reported on stderr and exits non-zero, so a truncated stream never exits 0 (SR-007, INV-6); running `python -B -m logredact` with `PYTHONDONTWRITEBYTECODE=1` in an empty temporary directory creates **no** file, temp file, or cache, and the input file's content **and mtime** are unchanged because it was opened read-only (SR-008, INV-4, research.md D-009); and a scan of every `import`/`from` line under `src/` finds nothing outside the standard library (FR-015)
- [X] T035 [P] Write `tests/test_performance.py` covering SR-006, SC-007 and SC-008 with deterministic, network-free timing assertions: each 10 000-character adversarial line — `"9" * 10000`, `"1 " * 5000`, `"a." * 2500 + "@" + "a." * 2500`, `"1." * 5000`, `"a" * 10000 + "@"` — completes **under 1 second** (research.md D-005 measured a 117 ms worst case, an 8.5× margin), and a 10 MB log redacts in **under 10 seconds** (D-010 measured 1.9 s, a 5× margin)
- [X] T036 Implement the per-line ceiling in `src/logredact/cli.py`: treat a chunk from `readline(MAX_LINE + 1)` as terminated when it ends with `"\n"` or `"\r"`; a chunk that is **not** terminated and is longer than `MAX_LINE` proves the line's content exceeds the limit, so write a diagnostic naming the input source and stating the limit — **without quoting the line** — and return **2**. The line MUST be rejected, never silently truncated (SR-005, Constitution Principle II, research.md D-002). Record research.md D-002's benign `\r\n`-at-exactly-`MAX_LINE` split as accepted behaviour: the bytes written remain byte-identical and no rule spans a line boundary
- [X] T037 Implement fail-closed output in `src/logredact/cli.py`: wrap every stdout write and the final flush so an `OSError` is reported on stderr and returns **2**, never swallowed (SR-007, Constitution Principle II). On `BrokenPipeError` specifically, write the diagnostic, flush stderr explicitly first so it is not lost, then call `os._exit(2)` — otherwise CPython's interpreter-shutdown flush of `sys.stdout` raises again, prints `Exception ignored in: <stdout>` to stderr (polluting FR-011/SR-001) and changes the status to 120, contradicting the documented status (research.md D-006). Letting `BrokenPipeError` propagate is forbidden because it prints a stack trace (SR-009)
- [X] T038 Run the full suite with `pytest -q` and confirm it passes with **zero skipped and zero xfail tests**, which is the Constitution Principle III and SC-009 gate; fix the code or amend the requirement rather than skipping, marking expected-failure, or deleting any failing test
- [X] T039 [P] Execute every remaining quickstart.md scenario end to end — **Scenario 5** (non-UTF-8 round-trip via `xxd`, confirming no `efbfbd`), **Scenario 6** (over-long line `status=2`, 10 MB throughput timing, bounded memory under `/usr/bin/time -v`, adversarial line timing), and **Scenario 7** (no artifacts on disk under `-B`) — and record the observed numbers against the SC-007/SC-008 budgets
- [X] T040 [P] Run the two quickstart.md gate commands and confirm both report no matches: the leak scan `pytest -q 2>&1 | grep -E 'jane@example\.com|4111 ?1111|10\.0\.0\.7'` (SC-010), and the stdlib-only import scan `grep -rnE '^\s*(import|from)\s+' src/ | grep -vE '\b(re|sys|os|io|argparse|typing)\b'` (FR-015, Constitution Principle I)
- [X] T041 Verify the plan.md **Requirement-to-Test Mapping** against the delivered suite: every row of both tables (FR-001 – FR-018, SR-001 – SR-009) resolves to at least one real assertion in the named test file, so a reviewer can trace every requirement to a test (FR-018, SC-009, Constitution "Review": a reviewer who cannot locate the test for a requirement must treat the requirement as unimplemented). Correct any drift between the mapping and the files actually written
- [X] T042 Final review of `src/logredact/` against Constitution Principle IV: confirm the four modules are the only ones, that `Options` is the argparse namespace, `Match` is a `tuple[int, int, str]`, and `Counts` is three ints or one dict with no class added for any of the five entities, and that no rule registry, strategy object, plugin hook, or configuration surface crept in (data-model.md, plan.md Complexity Tracking)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1. **BLOCKS all user stories** — the patterns (T004), the `main()` signature (T005), and the encoding policy (T008) are used by every story.
- **User Story 1 (Phase 3)**: Depends on Phase 2 only. No dependency on US2, US3, or US4.
- **User Story 2 (Phase 4)**: Depends on Phase 2. Reuses T017 `redact_line` and T018's read loop, so in practice it follows US1; its own tests are independent.
- **User Story 3 (Phase 5)**: Depends on Phase 2. T017 already returns counts, so US3 adds only accumulation and the stderr write — no change to the redaction path (SR-003).
- **User Story 4 (Phase 6)**: Depends on Phase 2. Its partial-output scenario (US4-4) is most meaningful once US2 exists, but the missing-path, directory, and bad-option cases are testable against US1 alone.
- **Polish (Phase 7)**: Depends on all four user stories being complete. Mandatory, per the Implementation gate.

### User Story Dependencies

- **US1 (P1)**: Independent. The MVP.
- **US2 (P2)**: Independently testable; shares the redaction engine with US1 by design, not by coupling.
- **US3 (P3)**: Independently testable; touches only counter accumulation and one stderr write.
- **US4 (P3)**: Independently testable; touches only error paths and return values.

### Within Each User Story

- Tests are written **first** and MUST FAIL before the implementation tasks begin.
- `redact.py` pure functions (T015, T016) before the `redact_line` pipeline (T017) that composes them.
- `redact_line` (T017) before the CLI wiring (T018) that calls it.
- Source iteration (T021) before the loop that consumes it (T022).
- Counter accumulation (T025) before the summary write (T026).
- Each story's verification task (T019, T023, T027, T032) runs last in its phase.

### Parallel Opportunities

- **Phase 1**: T002 and T003 run in parallel after T001.
- **Phase 2**: T006 and T007 run in parallel with each other; T008 edits the same file as T005 and must follow it.
- **Phase 3**: all six test files (T009–T014) are different files and run fully in parallel. Implementation T015 and T016 both edit `redact.py` and are therefore **not** parallel.
- **Phase 7**: the three test files T033, T034, T035 run in parallel; T036 and T037 both edit `cli.py` and are not parallel; T039, T040 are independent verification runs.
- Across stories: once Phase 2 completes, US1–US4 test authoring can proceed in parallel on different files, though all four implementations touch `cli.py` and must be serialised there.

---

## Parallel Example: User Story 1

```bash
# Launch all six User Story 1 test files together — different files, no shared state:
Task: "Write tests/test_redact_email.py covering FR-004 and SR-002"
Task: "Write tests/test_redact_ipv4.py covering FR-005"
Task: "Write tests/test_redact_card.py covering FR-006 and FR-007"
Task: "Write tests/test_precedence.py covering FR-008 and FR-009"
Task: "Write tests/test_cli_stream.py covering FR-001, FR-002, FR-003"
Task: "Write tests/test_encoding.py covering FR-017"

# Confirm they all FAIL, then implement T015 -> T016 -> T017 -> T018 in order
# (all four edit src/logredact/redact.py or src/logredact/cli.py — not parallel).
```

## Parallel Example: Phase 7

```bash
# Three independent cross-cutting test files:
Task: "Write tests/test_limits.py covering SR-005 and FR-016"
Task: "Write tests/test_security.py covering SR-001 - SR-004, SR-007 - SR-009, FR-015"
Task: "Write tests/test_performance.py covering SR-006, SC-007, SC-008"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003).
2. Complete Phase 2: Foundational (T004–T008) — **blocks everything**.
3. Complete Phase 3: User Story 1 (T009–T019).
4. **STOP and VALIDATE**: `printf 'user jane@example.com from 10.0.0.7\n' | PYTHONPATH=src python -m logredact` returns `user [EMAIL] from [IP]`, exit 0, stderr empty.
5. The tool is already useful — anything pipeable can be sanitised.

### Incremental Delivery

1. Setup + Foundational → patterns compile, `main()` is callable with injected streams.
2. **+ US1** → streaming redaction of all three categories. **MVP.**
3. **+ US2** → multi-file batch redaction in argument order.
4. **+ US3** → reviewable `emails=N ips=N cards=N` tally on stderr.
5. **+ US4** → trustworthy failure reporting, exit 2 on unreadable input.
6. **+ Phase 7** → bounds, fail-closed output, security and performance gates. **Only here is the change complete** under the constitution's Implementation gate.

### Parallel Team Strategy

With multiple developers, after Phase 2 completes:

- Developer A: US1 (the redaction engine in `redact.py` — the largest piece).
- Developer B: US2 and US4 test files, then the `cli.py` source-iteration and error paths.
- Developer C: US3 test file and the counts wiring, then the Phase 7 cross-cutting test files.

`src/logredact/cli.py` is touched by US1, US2, US3, US4, and Phase 7, so serialise edits to it; `redact.py` is finished within US1 and then stable.

---

## Notes

- **Tests are mandatory here**, unlike the template default: FR-018, SC-009, and Constitution Principle III require every functional and security requirement to have an automated test, with failure paths asserting both the failure signal and the message content, and with **no skipped or xfail tests**.
- Byte-level assertions matter: FR-003, FR-017, and SR-002 are claims about bytes, so CLI tests compare raw `bytes` from the subprocess rather than decoded text.
- Two failure paths are unreachable without injection in this environment — permission-denied (tests run as root) and output write failure — which is exactly why `main(argv, *, stdin, stdout, stderr)` takes its streams as keyword arguments and why the `open` call is monkeypatchable (research.md D-008). Neither may be covered by a `skipif`.
- `[P]` tasks touch different files and have no ordering dependency. Tasks editing the same file are never marked `[P]`.
- Commit after each task or logical group; stop at any checkpoint to validate a story in isolation.
- Avoid: redacting via `re.sub` with a replacement template (SR-004), using `\d`/`\w`/`\b` (D-004), unbounded `readline()` (SR-005), and any `except` clause that discards an error (Constitution Principle II).
