# Tasks: Log Redaction CLI

**Input**: Design documents from `/specs/001-logredact-cli/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md),
[contracts/redaction-rules.md](./contracts/redaction-rules.md)

**Tests**: Test tasks ARE included and are mandatory for this feature. The project constitution
(Principle III) requires every functional requirement to map to at least one `pytest` test that names
it, and SC-002/SC-003 require the same. Tests are written before the implementation they cover.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and
delivered independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths are included in every description

## Path Conventions

Single-project layout per [plan.md](./plan.md) "Structure Decision": package under `src/logredact/`,
tests under `tests/`, both at repository root. No `models/`, `services/`, or `lib/` subdivision —
there is no model or service layer (Principle IV). No `contract/`, `integration/`, `unit/` test
directories — test files are split by user story and by concern instead.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the directory layout and settle the one constitutional precondition that blocks
all implementation work.

- [X] T001 Create the single-project layout at the repository root: directories `src/logredact/` and `tests/`, plus `src/logredact/__init__.py` containing only a one-line module docstring describing the package (no imports, no re-exports — per the plan's Principle IV justification)
- [X] T002 Amend `.specify/memory/constitution.md` to replace `TODO(PYTHON_VERSION)` in "Technology & Dependency Constraints" with "3.11" (research R1), remove the now-satisfied `TODO(PYTHON_VERSION)` line from the scratch comment block at the top, and record the amendment per the Governance amendment procedure: bump **Version** to `1.0.1` (PATCH — clarification that does not change what is required) and set **Last Amended** to the amendment date. The constitution requires this version to be pinned *before the first implementation task*, so this task blocks Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The test harness, the entry point, the argument parser, and the byte-fidelity stream
layer. Every user story reads input and writes output through this code, so none can begin until it
exists.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Create `tests/conftest.py`: prepend the repository's `src/` directory to `sys.path` (resolved from `__file__`, not the working directory) so unit tests can `from logredact.redact import ...`, and provide a `run_cli` fixture that invokes `[sys.executable, "-m", "logredact", *args]` through `subprocess.run` with `PYTHONPATH=<repo>/src`, `capture_output=True` and **no** `text=True` — stdout and stderr must be returned as `bytes` so byte-fidelity assertions are possible — returning the `CompletedProcess`. Accept optional `input: bytes` for stdin. No `pytest.ini` or `pyproject.toml` configuration may be added; plain `pytest` from the root must work (research R8).
- [X] T004 Create `src/logredact/cli.py` with the signature `def main(argv: list[str] | None = None) -> int` fixed by [data-model.md](./data-model.md) "Derived function signatures", building an `argparse.ArgumentParser` with `prog="logredact"` (required, or argparse names the program `__main__.py` under `python -m`), `--count` as `action="store_true"`, and `files` as a positional with `nargs="*"` and `metavar="FILE"`, parsed with `parser.parse_intermixed_args(argv)` — **not** `parse_args`, which rejects `a.log --count b.log` and would violate FR-004 (research R6). Return `0` for now.
- [X] T005 [P] Create `src/logredact/__main__.py` as a two-line shim only: import `main` from `logredact.cli` and call `sys.exit(main(sys.argv[1:]))`. No logic may live here, so that tests can import the CLI without depending on module-execution semantics (plan, Principle IV justification).
- [X] T006 In `src/logredact/cli.py`, add the byte-fidelity stream layer: reconfigure `sys.stdin` and `sys.stdout` with `encoding="utf-8"`, `errors="surrogateescape"`, `newline=""` (research R5 — `newline=""` disables universal-newline translation so `\r\n` survives; `surrogateescape` round-trips non-UTF-8 bytes), and a pass-through loop that iterates the source line by line — each line arrives **including its terminator** ([data-model.md](./data-model.md) Entity 1) — and emits it with `sys.stdout.write()`, never `print()`, which would invent a trailing newline. Source is `sys.stdin` for now. Return `0`.

**Checkpoint**: `printf 'x\r\ny' | PYTHONPATH=src python3 -m logredact` reproduces its input byte for
byte and exits 0. User story implementation can now begin.

---

## Phase 3: User Story 1 - Redact a piped log stream (Priority: P1) 🎯 MVP

**Goal**: Pipe log text through the tool and get the same text back with every email address, IPv4
address, and Luhn-valid 13–19 digit card number replaced by `[EMAIL]`, `[IP]`, `[CARD]`, and
everything else byte-identical. This is the whole point of the feature and is useful on its own.

**Independent Test**: Pipe a block of text containing emails, IPv4 addresses, card numbers,
near-miss values, and ordinary text into the tool with no file arguments and no flags; confirm the
output has exactly the sensitive values replaced and everything else byte-identical. Covers
[contracts/cli.md](./contracts/cli.md) worked examples 1, 2, 4, 5, 6.

### Tests for User Story 1 ⚠️

> **Write these first and confirm they FAIL before T010–T013.** Every test must name the requirement
> it covers in its name or docstring (Principle III, SC-002).

- [X] T007 [P] [US1] Create `tests/test_luhn.py` covering FR-013's checksum and length rule for `logredact.redact.luhn`: `"4111111111111111"` passes, `"1234567890123"` passes the length rule but **fails** Luhn, a doubled digit over 9 has 9 subtracted (so a value such as `"79927398713"` is handled correctly), and the length boundaries hold — **12 digits or fewer and 20 digits or more are never a card, even if a 13-to-19-digit window inside them would pass Luhn** (`"41111111111111111111"`, 20 digits, is rejected). Assert the 13 ≤ count ≤ 19 bound at each edge: 12 reject, 13 accept, 19 accept, 20 reject.
- [X] T008 [P] [US1] Create `tests/test_redact_line.py` covering FR-006, FR-008 to FR-016 for `logredact.redact.redact_line`, with one test per row of the tables in [contracts/redaction-rules.md](./contracts/redaction-rules.md): email grammar (`a@b.io`, `jane.doe+test@mail.example.com` → `[EMAIL]`; `jane@example.com.` → `[EMAIL].`); IPv4 grammar and boundary (`1.2.3.4`, `10.0.0.7`, `255.255.255.255`, `010.0.0.1` → `[IP]`; `999.1.1.1`, `256.0.0.1`, `1.2.3`, `1.2.3.4.5`, `1.2.3.45678`, `v1.2.3.4` **completely unchanged, with no fragment such as `99.1.1.1` redacted**); card (`4111111111111111`, `4111 1111 1111 1111`, `4111-1111-1111-1111`, `4111-1111 1111-1111` → `[CARD]`; `4111  1111 1111 1111` with a doubled separator, `1234567890123`, and a 20-digit run unchanged); FR-014 every occurrence (`a@b.io a@b.io a@b.io` → three `[EMAIL]`); FR-015 precedence (`user@1.2.3.4` → `[EMAIL]` counted as 1 email and **0 ips**, and `123 1.2.3.4` → `123 [IP]`, the rejected-card restart case); `a@b.io,1.2.3.4` → `[EMAIL],[IP]` with the comma preserved; a line that is one sensitive value becomes exactly the placeholder; FR-016 determinism (two calls on the same input return equal results); and that the returned tally tuple is `(emails, ips, cards)` matching the placeholders added.
- [X] T009 [P] [US1] Create `tests/test_stdin.py` covering FR-001, FR-003, FR-006 and FR-023 end to end through the `run_cli` fixture: worked example 1 (`user jane@example.com from 10.0.0.7\n` → `user [EMAIL] from [IP]\n`), example 2 (`paid with 4111 1111 1111 1111, ref 1234567890123\n` → `paid with [CARD], ref 1234567890123\n`), example 4, example 5 (`host 999.1.1.1 unreachable\n` unchanged), example 6 (empty stdin → empty stdout, exit 0), a line with several values of different categories all replaced in place with spacing and punctuation unchanged, and in every case stderr empty and exit status 0. Each assertion compares `bytes` exactly. One test must name FR-001 by asserting the tool is reachable as `python -m logredact`.

### Implementation for User Story 1

- [X] T010 [US1] Create `src/logredact/redact.py` with the module-level pattern constants copied **verbatim** from [contracts/redaction-rules.md](./contracts/redaction-rules.md): `COMPONENT = r"(?:25[0-5]|2[0-4]\d|[01]\d\d|\d\d|\d)"`, `IPV4_BODY = COMPONENT + r"(?:\." + COMPONENT + r"){3}"`, `EMAIL = r"[A-Za-z0-9._%+-]+@(?:" + IPV4_BODY + r"|(?:[A-Za-z0-9-]+\.)*[A-Za-z]{2,})"`, `IP = r"(?<![\w.])" + IPV4_BODY + r"(?![\w.])"`, `CARD = r"(?<!\d)\d+(?:[ -]\d+)*(?!\d)"`, and `COMBINED = re.compile(f"(?P<email>{EMAIL})|(?P<ip>{IP})|(?P<card>{CARD})")`. Compile once at module level. Add a comment recording that **the alternation order email → ip → card is load-bearing: it is what implements FR-015's precedence, and rearranging it breaks the contract**, and that the `(?<![\w.])` lookbehind is what prevents a fragment of `999.1.1.1` from matching (research R3).
- [X] T011 [US1] In `src/logredact/redact.py`, implement `def luhn(digits: str) -> bool` per [data-model.md](./data-model.md): iterate the digit string right to left, double every second digit, subtract 9 from any doubled value over 9, sum, and return whether the total is ≡ 0 (mod 10). Pure integer arithmetic over the digit characters, no lookup table, no allocation beyond the input (Principle IV). `digits` is assumed to be separator-free; the 13–19 length rule is enforced by the caller in T012. Make `tests/test_luhn.py` pass.
- [X] T012 [US1] In `src/logredact/redact.py`, implement `def redact_line(line: str) -> tuple[str, tuple[int, int, int]]` returning `(redacted_line, (emails, ips, cards))` — pure, no I/O, terminator-preserving — as the explicit `search(line, pos)` loop specified in research R2: (1) `m = COMBINED.search(line, pos)`; if no match, emit `line[pos:]` and stop; (2) if the matched group is `email` or `ip`, emit `line[pos:m.start()]` + the placeholder, set `pos = m.end()`, increment that count; (3) if the matched group is `card`, strip every space and hyphen, require **13 ≤ digit count ≤ 19 inclusive** *and* `luhn(...)`, and on success behave as in step 2 — **on failure emit `line[pos:m.start() + 1]` and set `pos = m.start() + 1`**, restarting one character *into* the rejected candidate rather than past it, which is what makes `123 1.2.3.4` yield `123 [IP]`. Build the result with a list of fragments joined once, not repeated string concatenation. A rejected candidate increments nothing. The function must be total: every `str` returns a `str` of the same line count, and input with no candidate returns a value equal to its input (FR-007, FR-016). Make `tests/test_redact_line.py` pass.
- [X] T013 [US1] In `src/logredact/cli.py`, replace T006's pass-through with redaction: import `redact_line` from `logredact.redact`, call it on each line, write the redacted text, and accumulate the three returned counts into a run-level tally initialised to `0, 0, 0` and summed across every line and every source ([data-model.md](./data-model.md) Entity 3). Do not flush per line — buffered writes only (research R9). Make `tests/test_stdin.py` pass.

**Checkpoint**: User Story 1 is fully functional and independently testable — the tool redacts a
piped stream correctly. This is the MVP and could be shipped here.

---

## Phase 4: User Story 2 - Redact one or more named log files (Priority: P2)

**Goal**: Name one or more files on the command line, in any order the user wants, and capture a
single redacted stream that is the concatenation of their redacted contents.

**Independent Test**: Create two small files with known sensitive content, run the tool with both
file names as arguments, and confirm the output is the redacted content of the first file followed by
the redacted content of the second, with nothing reordered, dropped, or duplicated. Covers worked
example 8.

### Tests for User Story 2 ⚠️

- [X] T014 [P] [US2] Create `tests/test_files.py` covering FR-002, FR-003 and FR-023 through the `run_cli` fixture with `tmp_path` files: two readable files produce their redacted contents on stdout **in the order named on the command line** (worked example 8); one file named means **standard input is not read at all** (pass non-empty `input=` bytes and assert none of it appears in stdout, and exit status 0); the same file named twice produces its redacted contents twice (sources are never deduplicated); a readable but completely empty file produces empty stdout and exit 0; and the concatenation is treated as one stream of lines, so a file whose last line has no trailing newline is followed immediately by the next file's first line.

### Implementation for User Story 2

- [X] T015 [US2] In `src/logredact/cli.py`, add file-operand handling: when `args.files` is non-empty, iterate it **in the exact order given** and for each name open the file with `open(name, encoding="utf-8", errors="surrogateescape", newline="")` — the same mode as the stdin path, so behaviour is identical for files and pipes — feed its lines through the same redaction loop as T013, and close it before opening the next (`unopened → open → exhausted → closed`, never two sources open at once, per [data-model.md](./data-model.md) Entity 1). Read `sys.stdin`, and only `sys.stdin`, when `args.files` is empty (FR-003). Open each source lazily at its turn — **no pre-flight readability check across all operands** (stated assumption; this is what makes US4 scenario 4 work). Make `tests/test_files.py` pass.

**Checkpoint**: User Stories 1 and 2 both work independently — stdin and file operands are both
supported.

---

## Phase 5: User Story 3 - Confirm how much was redacted (Priority: P3)

**Goal**: With `--count`, print exactly one tally line to standard error after all redacted output
has been written, so the user can tell "nothing was sensitive" apart from "the tool recognised
nothing" without polluting the redacted output.

**Independent Test**: Run the tool with `--count` over input with a known number of each category,
with standard output and standard error captured separately; confirm the redacted text appears only
on standard output and exactly one summary line appears only on standard error. Covers worked
examples 3, 7, 10.

### Tests for User Story 3 ⚠️

- [X] T016 [P] [US3] Create `tests/test_count.py` covering FR-004 and FR-017 to FR-020 through the `run_cli` fixture: worked example 3 (`a@b.io 1.2.3.4\n` with `--count` → stdout `[EMAIL] [IP]\n`, stderr exactly `emails=1 ips=1 cards=0\n`); worked example 7 (empty stdin with `--count` → stderr `emails=0 ips=0 cards=0\n`, **zero printed as `0`, not omitted**, exit 0); the same email three times reports `emails=3`, because **every individual replacement is counted, not every distinct value**; several files named together with `--count` produce **exactly one** summary line totalling replacements across all files; FR-004 flag position — `--count a.log`, `a.log --count`, and `a.log --count b.log` all behave identically, and zero operands work with and without the flag; FR-019 stderr receives **nothing at all** without `--count` on a successful run; FR-020 the summary never appears on stdout; and FR-018/SC-006 — the stderr line count is exactly 1 and each reported N equals the number of that category's placeholders in stdout.

### Implementation for User Story 3

- [X] T017 [US3] In `src/logredact/cli.py`, emit the summary: after every source has been consumed and **only** when `args.count` is true, `sys.stdout.flush()` first (this single flush is what satisfies FR-018's ordering guarantee — no per-line flush is needed) and then write exactly one line `f"emails={emails} ips={ips} cards={cards}\n"` to `sys.stderr`. The summary must never be written to stdout (FR-020) and nothing may be written to stderr when `--count` is absent and no error occurs (FR-019). Make `tests/test_count.py` pass.

**Checkpoint**: User Stories 1, 2 and 3 all work independently.

---

## Phase 6: User Story 4 - Learn immediately when a log cannot be read (Priority: P3)

**Goal**: When a named file cannot be opened or read, say which file and why on standard error and
exit 2, so a silently truncated "redacted" log can never be mistaken for a complete one.

**Independent Test**: Run the tool naming a file that does not exist; confirm standard error contains
a message naming that exact file, and the exit status is 2. Covers worked example 9.

### Tests for User Story 4 ⚠️

- [X] T018 [P] [US4] Create `tests/test_errors.py` covering FR-005, FR-021 and FR-022 through the `run_cli` fixture: a file name that does not exist → stderr names that file and exit 2; a file whose mode is set to `0o000` → stderr names it and exit 2 (run unconditionally, not skipped — constitution gate 2; skip-free means the test must also be valid when run as a non-root user, so assert the diagnostic names the path and the exit status is 2); a `tmp_path` **directory** as the operand → stderr names it and exit 2; worked example 9 — first file readable, second missing → the **redacted contents of the first file are on stdout**, a message naming the second file is on stderr, exit 2; FR-021's two-part message — assert the diagnostic contains the file name **as the user typed it** and a non-empty reason, matching on the file name and reason presence rather than exact OS wording (the reason comes from `OSError.strerror`); FR-005 an unrecognised option such as `--bogus` → an argparse usage diagnostic on stderr naming the bad option, exit 2, and it is **never** treated as a file name; FR-022 a failing run with `--count` produces **no** summary line on stderr; and FR-023 all-readable operands exit 0.

### Implementation for User Story 4

- [X] T019 [US4] In `src/logredact/cli.py`, wrap each source's open-and-read in `except OSError as exc`, writing `f"logredact: cannot read '{name}': {exc.strerror}\n"` to `sys.stderr` — naming both the operand as the user typed it and the reason (FR-021, Principle II forbids a diagnostic that omits the offending value) — and `return 2` immediately, before any summary is emitted, so a failed run produces no tally even with `--count` (FR-022). Catch `OSError` around the read loop as well as the `open`, so a mid-read I/O error is reported the same way. Return 0 only when every requested source was read and written (FR-023). Unrecognised options need no code: argparse already exits 2 with a usage diagnostic (research R6). Make `tests/test_errors.py` pass.

**Checkpoint**: All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The cross-story guarantees (byte fidelity, performance, the closed-stdout path) and the
documentation corrections the design surfaced.

- [X] T020 [P] Create `tests/test_fidelity.py` covering FR-007 and SC-004 through both the stdin and the file path: `\r\n` line endings preserved exactly; a lone `\r` before the line ending preserved as line content; a final line with **no trailing newline** written back with none invented (assert the output bytes equal the input bytes); a line containing bytes that are not valid UTF-8 (for example `b'caf\xe9 jane@example.com\n'`) processed without a crash, with those bytes reproduced unchanged and never replaced, while the email on the same line still becomes `[EMAIL]`; blank and whitespace-only lines reproduced exactly, **including trailing spaces and tab characters**; a single line far longer than a typical log line (≥ 100,000 characters) redacted and reproduced in full; and a sensitive value split across a line ending **not** redacted, because recognition is line-local.
- [X] T021 [P] Create `tests/test_performance.py` covering SC-008: generate a 100,000-line log into `tmp_path` (the [quickstart.md](./quickstart.md) V8 line is representative), redact it with `--count`, and assert it completes **in under 10 seconds** measured with `time.perf_counter` and that the reported tally matches the generated content. Assert flat memory by checking that peak memory measured with `tracemalloc` is bounded by a small multiple of the longest single line rather than growing with line count — compare a 10,000-line run against a 100,000-line run of the same line and assert the peak does not scale with the line count. Must run unconditionally, with a margin wide enough not to be flaky on slow CI (the design prototype measured 1.36 s).
- [X] T022 Add the closed-stdout test to `tests/test_errors.py` covering the "output cannot be written" edge case and research R7: run the tool on a large generated file with stdout attached to a pipe that is closed early (a downstream `head -1`), and assert stderr contains the single-line diagnostic, contains **no traceback and no `Exception ignored in:` interpreter-shutdown noise**, and the tool's own exit status is 2, with no `--count` summary even when `--count` is given.
- [X] T023 In `src/logredact/cli.py`, implement the broken-pipe path per research R7: catch `BrokenPipeError` around the whole run, redirect file descriptor 1 to `os.devnull` with `os.dup2` (this step is required — without it CPython prints `Exception ignored in: <_io.TextIOWrapper name='<stdout>'>` during shutdown, which is traceback-shaped output on stderr), write `logredact: cannot write to standard output: Broken pipe\n` to stderr inside its own `try`/`except` so a gone stderr is not fatal, emit **no** summary, and `return 2`. Make T022's test pass.
- [X] T024 [P] Apply the four spec-owner corrections listed in [research.md](./research.md) "Items for the spec owner" to `specs/001-logredact-cli/spec.md`: amend FR-009 to accept a bare valid IPv4 address as a domain form, so FR-009 stops contradicting the `user@1.2.3.4` edge case (R4); restate the IPv4 boundary in Assumptions as "not adjacent to a word character or a dot" instead of "a digit or a dot", so it stops contradicting the `v1.2.3.4` edge case (R3); add to Edge Cases the accepted consequence that an address followed by a sentence period (`1.2.3.4.`) is left unredacted, since the boundary rule cannot distinguish that dot from the fifth component of `1.2.3.4.5` (R3); and add exit status 2 with a diagnostic as the specified behaviour for a closed standard output (R7). The constitution requires conflicting artifacts to be corrected rather than left standing.
- [X] T025 Run every validation scenario V1 to V8 in [quickstart.md](./quickstart.md) from the repository root with `PYTHONPATH=src` and confirm each behaves exactly as stated, including the `cmp` byte-identity check in V2 and the `od -c` non-UTF-8 check in V3.
- [X] T026 Run the constitution's five quality gates as a final check and record the result: `pytest` passes in full from the repository root with **nothing skipped** (gate 2); every requirement FR-001 to FR-023 is named by at least one test — verify against the coverage map in [contracts/cli.md](./contracts/cli.md) by grepping the `tests/` tree for each requirement ID (gate 1, SC-002); every edge case in spec.md has a test (SC-003); `src/logredact/` imports nothing outside `re`, `argparse`, `sys`, `os` (gate 4); and no class, registry, or configurable placeholder was introduced beyond the four source files the plan justifies (gate 5).

---

## Gate Check Result (T026)

Recorded 2026-11-16, CPython 3.13.17, pytest 9.1.1, run from the repository root.

| Gate | Requirement | Result |
|------|-------------|--------|
| 1 | Every FR has a test naming it (Principle III, SC-002) | **PASS** — FR-001…FR-023 each matched in `tests/`; files agree with the coverage map in [contracts/cli.md](./contracts/cli.md) |
| 2 | `pytest` passes in full, nothing skipped | **PASS** — `222 passed in 59.82s`, zero skipped, zero xfailed (`-rsxX` reports none) |
| 3 | Invalid input exercised, Principle II conformant | **PASS** — 16 tests in `tests/test_errors.py`: missing file, directory operand, mode `0o000`, over-long path, unknown option, closed stdout; each exits 2 with a diagnostic naming the cause, and none emits a `--count` summary |
| 4 | No runtime import outside the standard library | **PASS** — `re`, `argparse`, `sys`, `os` only, plus intra-package imports. `pytest` is test-only |
| 5 | No unjustified abstraction | **PASS** — 4 source files, 260 lines, **0 classes**, no category registry, no configurable placeholder; no `pytest.ini`/`pyproject.toml`/`setup.py` added, so plain `pytest` works |

**SC-003** (every edge case in spec.md has a test): **PASS** — all 20 edge cases covered, including
the two added by T024. 105 test functions, 222 parametrised cases.

**SC-008**: 100,000-line log redacted in **0.91 s** against the 10 s budget; peak child RSS identical
(11,724 kB) for 10,000 and 100,000 lines, confirming memory is flat in line count.

**Quickstart V1–V8** (T025): all eight pass, including V2's `cmp` byte-identity check and V3's `od -c`
non-UTF-8 check.

**Open item carried forward**: the O(n²) cost on a single unbroken token, recorded as item 5 in
[research.md](./research.md) "Items for the spec owner". Correctness is unaffected and pinned by a
test; the obvious pattern fix is proven unsafe there and was deliberately not applied.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. T002 must land before any implementation task, because the
  constitution requires the Python version pinned first.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks all four user stories.**
- **User Story 1 (Phase 3)**: Depends on Foundational. Blocks US2, US3, US4 — they all reuse the
  redaction loop it wires up in `cli.py`.
- **User Story 2 (Phase 4)**: Depends on Foundational + US1.
- **User Story 3 (Phase 5)**: Depends on Foundational + US1. Its "totals across all files" test also
  needs US2.
- **User Story 4 (Phase 6)**: Depends on Foundational + US1. Its diagnostics apply to file operands,
  so it needs US2.
- **Polish (Phase 7)**: Depends on all four stories.

### User Story Dependencies

Unlike the common case, these stories are **sequentially layered rather than independent**, because
they are four facets of one 250-line CLI rather than four features:

- **US1 (P1)**: The redaction engine plus the stdin path. Independent once Foundational is done, and
  shippable alone as the MVP.
- **US2 (P2)**: Adds input selection only. Needs US1's engine; the plan states it "builds directly
  on the redaction engine proven by User Story 1".
- **US3 (P3)**: Adds output of the tally only. Needs US1's per-line counts; scenario 4
  ("several input files named together") also needs US2.
- **US4 (P3)**: Adds the failure path only. Needs US2, since the failure is per file operand.

Each story remains **independently testable** — its own test file passes or fails on its own
behaviour — which is what the spec's "Independent Test" entries require.

### Within Each User Story

- Tests are written first and must FAIL before the implementation tasks in that phase.
- `redact.py` before `cli.py`: patterns (T010) → `luhn` (T011) → `redact_line` (T012) → wiring (T013).
- Story complete and its checkpoint verified before moving to the next priority.

### File-Contention Notes (why most tasks are not [P])

- `src/logredact/cli.py` is touched by T004, T006, T013, T015, T017, T019, T023 — these are strictly
  sequential.
- `src/logredact/redact.py` is touched by T010, T011, T012 — strictly sequential.
- `tests/test_errors.py` is created by T018 and extended by T022 — sequential.
- Every other test file has exactly one author task, so all of them are `[P]`.

### Parallel Opportunities

- T003 (`tests/conftest.py`) and T005 (`src/logredact/__main__.py`) can run in parallel with each
  other; T005 also parallel with T004 only after `main` exists, so prefer T004 → T005.
- T007, T008, T009 — all three US1 test files — can be written in parallel.
- T014, T016, T018 — the US2, US3, US4 test files — can be written in parallel with each other once
  US1 is done, even though their implementation tasks must be sequenced.
- T020, T021, T024 can run in parallel in Polish.

---

## Parallel Example: User Story 1

```bash
# Write all three US1 test files together (they must fail before T010):
Task: "Create tests/test_luhn.py covering FR-013 checksum and 13-19 length rule"
Task: "Create tests/test_redact_line.py covering FR-006, FR-008..FR-016 from contracts/redaction-rules.md"
Task: "Create tests/test_stdin.py covering FR-001, FR-003, FR-006, FR-023 end to end"

# Then implement sequentially — all three touch src/logredact/redact.py:
#   T010 patterns -> T011 luhn -> T012 redact_line -> T013 cli wiring
```

## Parallel Example: Stories 2–4 test authoring

```bash
# Once US1 is green, all three remaining story test files can be written at once:
Task: "Create tests/test_files.py covering FR-002, FR-003, FR-023"
Task: "Create tests/test_count.py covering FR-004, FR-017..FR-020"
Task: "Create tests/test_errors.py covering FR-005, FR-021, FR-022"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup — layout plus the constitution version pin.
2. Complete Phase 2: Foundational — harness, entry point, parser, byte-fidelity streams.
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: run quickstart scenario V1 and `pytest tests/test_redact_line.py
   tests/test_luhn.py tests/test_stdin.py`. The tool now redacts a piped log correctly.
5. This is shippable: a pipe-only redactor already delivers the protection the feature exists for.

### Incremental Delivery

1. Setup + Foundational → a byte-faithful `cat`.
2. Add US1 → redaction of piped input → **MVP**, validate with V1/V2/V3.
3. Add US2 → named files in order → validate with V4.
4. Add US3 → `--count` tally on stderr → validate with V5.
5. Add US4 → loud failure on an unreadable file → validate with V6.
6. Polish → fidelity and performance suites, broken-pipe path, spec corrections → validate V7/V8 and
   run the gate check.

Each step leaves the tool working and adds no regression to the previous ones.

### Parallel Team Strategy

Limited parallelism is available here, and forcing more would create merge conflicts in `cli.py`:

1. One developer carries Setup → Foundational → US1 on the critical path.
2. Meanwhile a second developer can write T014, T016, T018, T020, T021 (test files, no overlap with
   `cli.py`) against the contracts, which are specified precisely enough to write tests before the
   implementation exists.
3. After US1 lands, the first developer implements T015, T017, T019, T023 in `cli.py` in order,
   turning each already-written test file green.
4. T024 (spec corrections) is documentation-only and can be done by anyone at any time.

---

## Notes

- `[P]` tasks touch different files and have no incomplete dependency.
- Every test must name the requirement it covers in its test name or docstring — this is a
  constitutional gate (Principle III), not a style preference.
- The pattern alternation order in `redact.py` and the `start + 1` restart on a rejected card are the
  two details that carry FR-015; neither is obvious from reading the code, so both must keep their
  comments.
- Do not add `pytest.ini`, `pyproject.toml`, `setup.py`, or any configuration file: plain `pytest`
  from the repository root must work, and no install or build step is permitted.
- Do not introduce a dependency, a class, a category registry, or a configurable placeholder
  (Principle IV; the plan's justifications permit exactly four source files).
- Commit after each task or logical group. Stop at any checkpoint to validate a story independently.
