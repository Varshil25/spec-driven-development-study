---

description: "Task list for Log Redaction Tool (`logredact`)"
---

# Tasks: Log Redaction Tool (`logredact`)

**Input**: Design documents from `/specs/001-logredact-cli/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [contracts/redaction-patterns.md](./contracts/redaction-patterns.md)

**Tests**: INCLUDED. Tests are not optional for this feature — Constitution Principle III ("Every
Requirement Is Testable") requires every functional requirement to map to a citing `pytest` test,
and SC-004/SC-005 make that mapping a measurable success criterion. Test tasks therefore precede
the implementation tasks in each phase and must fail before the implementation lands.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and
delivered as an independent increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies). Two tasks that edit the same
  file are never both marked `[P]`.
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths are given in every task description.

## Path Conventions

Single project, per plan.md "Source Code (repository root)". All paths below are relative to the
repository root:

- Runtime code: `src/logredact/`
- Tests: `tests/`
- Config: `pyproject.toml` (pytest configuration only)

Invocation is always `PYTHONPATH=src python3 -m logredact ...` — the package is never installed.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Make the package importable and the test suite discoverable, with no `pip install`
step (Constitution Principle I).

- [X] T001 Create `pyproject.toml` at the repository root containing **only**
      `[tool.pytest.ini_options]` with `pythonpath = ["src"]`, `testpaths = ["tests"]`, and
      `markers = ["slow: large-input cases, deselected by default"]`. Do **not** add a build
      backend, a `[project]` table, or any dependency — per plan.md Constitution Check row "Runs
      on bare CPython, no install step" and research R-009, `pythonpath` is what puts `src/` on
      the path, not an install.
- [X] T002 [P] Create the package skeleton: `src/logredact/__init__.py` (empty — "exports
      nothing", plan.md Project Structure) and `src/logredact/__main__.py` containing only the
      entry call `import sys; from logredact import cli; sys.exit(cli.main(sys.argv[1:]))` so that
      `cli.main()` stays importable (contracts/cli.md "Internal entry point").
- [X] T003 [P] Create `tests/conftest.py` with a `run_cli(*args, stdin: bytes = b"")` helper that
      invokes the real CLI as a subprocess via `subprocess.run([sys.executable, "-m",
      "logredact", *args], input=stdin, capture_output=True)` with `PYTHONPATH` set to the
      repository's `src` directory, and returns `(stdout_bytes, stderr_bytes, returncode)`.
      Return raw `bytes`, never decoded text — research R-009: byte comparison is what makes the
      non-UTF-8 and line-ending assertions meaningful, and `capsys` cannot exercise the
      surrogateescape or broken-pipe paths at all.
- [X] T004 [P] Create `tests/test_stdlib_only.py`: the Principle I gate. Walk every `*.py` file
      under `src/`, parse it with `ast`, collect the top-level module name of every `import` and
      `from ... import`, and assert each one is in `sys.stdlib_module_names`. Assert also that
      `pytest` is not imported anywhere under `src/`.

**Checkpoint**: `python3 -m pytest` runs and collects `tests/test_stdlib_only.py` green from the
repository root with no arguments.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The regex fragments, placeholder data, stream setup, and argument parser that every
user story builds on. These are shared by all four stories, so none of them can start until this
phase is complete.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Create `src/logredact/redact.py` with the shared pattern **fragments** as module-level
      string constants (no compiled pattern yet), copied verbatim from
      contracts/redaction-patterns.md: `_LOCAL = r"[A-Za-z0-9._%+-]+"`,
      `_HOST = r"(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}"`,
      `_OCTET = r"(?:25[0-5]|2[0-4][0-9]|[01][0-9][0-9]|[0-9][0-9]|[0-9])"`,
      `_QUAD = rf"{_OCTET}(?:\.{_OCTET}){{3}}"`, `_SEP = r"[ \-]"`. The octet alternation is what
      accepts values 0–255 **including leading-zero forms** (`010`, `00.0.0.0` are octets, spec
      Assumptions) while rejecting 256 and above (FR-013). Every character class is ASCII so no
      surrogate standing in for an undecodable byte can ever match (FR-005a, research R-001).
- [X] T006 Add two module-level `dict[str, str]` constants to `src/logredact/redact.py` per
      data-model.md §2: `PLACEHOLDERS = {"email": "[EMAIL]", "ip": "[IP]", "card": "[CARD]"}` and
      `TALLY_KEYS = {"email": "emails", "ip": "ips", "card": "cards"}`. Placeholders are data, not
      patterns — they are appended to the output fragment list and never become part of the
      subject string, which is what makes FR-022 hold by construction.
- [X] T007 [P] Create `src/logredact/cli.py` with `class OutputWriteError(Exception)` — a direct
      `Exception` subclass, **deliberately not an `OSError`** — plus `_write(stream, text)` and
      `_flush(stream)` helpers that each wrap their operation in `try/except OSError` and
      `raise OutputWriteError(...) from exc`. Per plan.md Complexity Tracking and research R-007,
      the non-`OSError` base is load-bearing: a write failure raised inside the per-source loop
      must propagate *past* that loop's `except OSError` so it is never misreported as "cannot
      read FILE". Do not catch `BrokenPipeError` specifically — FR-031a also names a destination
      that runs out of space (plain `OSError`, ENOSPC).
- [X] T008 Add `_text_stream(binary_stream, *, write: bool)` to `src/logredact/cli.py`, returning
      `io.TextIOWrapper(binary_stream, encoding="utf-8", errors="surrogateescape",
      newline="\n")`, and use it to replace `sys.stdin` / `sys.stdout` over their `.buffer`
      attributes. All three settings are mandatory and each maps to a requirement (research
      R-001, R-002): `surrogateescape` round-trips undecodable bytes byte-for-byte with no
      U+FFFD (FR-005a); `newline="\n"` means **only** `\n` terminates a line and the terminator
      is returned untranslated, so `\r\n` survives as `\r\n` and a bare `\r` stays ordinary text
      (FR-007) and a missing final newline stays missing (FR-007a). Do **not** use
      `newline=None` (translates `\r\n`) or `newline=""` (still splits on `\r`).
- [X] T009 Add `_build_parser()` to `src/logredact/cli.py`:
      `argparse.ArgumentParser(prog="python -m logredact")` with
      `add_argument("--count", action="store_true")` and
      `add_argument("files", nargs="*", metavar="FILE")`. Set `prog` explicitly — under
      `python -m logredact` the computed default is `__main__.py`, which prints a usage line a
      reader cannot copy (research R-006). Add no custom error handling and no `exit_on_error`
      override: argparse's stock behaviour *is* the specified behaviour for FR-030 and FR-030a.
- [X] T010 Add `main(argv: list[str]) -> int` to `src/logredact/cli.py` as a skeleton that parses
      with **`parser.parse_intermixed_args(argv)`** (never `parse_args` — with `nargs="*"` the
      latter rejects `a.log --count b.log` with "unrecognized arguments", breaking US2 acceptance
      scenario 3; research R-006), sets up the streams via T008, and returns `0`. `main` returns
      the exit status rather than calling `sys.exit` (contracts/cli.md "Internal entry point").

**Checkpoint**: Foundation ready — `PYTHONPATH=src python3 -m logredact` exits 0,
`--help` already prints usage to stdout and exits 0, and `--nope` already prints usage to stderr
and exits 2 (both inherited from argparse). User story implementation can now begin.

---

## Phase 3: User Story 1 - Redact a log stream before sharing it (Priority: P1) 🎯 MVP

**Goal**: Piping text through `python -m logredact` with no arguments returns the same text with
every email, IPv4 address, and Luhn-valid 13–19 digit card number replaced by `[EMAIL]`, `[IP]`,
and `[CARD]`, and every other character — including undecodable bytes and original line endings —
passed through untouched.

**Independent Test**: Pipe a known line containing an email, an IPv4 address, and a Luhn-valid
card number into the tool with no arguments; confirm stdout contains that line with `[EMAIL]`,
`[IP]`, and `[CARD]` substituted, all surrounding text intact, and exit status 0.

### Tests for User Story 1

> **NOTE: Write these tests FIRST and confirm they FAIL before writing T015–T019.** Each test
> must cite its FR or SC identifier in its function name or docstring (Principle III, SC-004).

- [X] T011 [P] [US1] Create `tests/test_redact.py` with email and IPv4 recognition tests calling
      `redact.redact_line` directly. Email (FR-008, FR-009, FR-010): `jane@example.com`,
      `jane.doe+test@mail.example.com` (dots and `+` in the local part, multi-label domain —
      replaced in full by a **single** `[EMAIL]`, no fragment left behind), `a@b.io`,
      `admin@1.2.3.4` → one `[EMAIL]` (FR-021 worked example, admitted by the `quad` alternative
      from research R-000); must **not** match `admin@999.1.1.1`, `jane@localhost`,
      `jane@example`; and `jane@example.com.` → `[EMAIL].` (trailing dot not part of the match).
      IPv4 (FR-011, FR-012, FR-013, FR-014): match `192.168.0.10`, `10.0.0.7`, `1.2.3.4`,
      `0.0.0.0`, `255.255.255.255`, `010.0.0.1` (leading zero accepted), and `v1.2.3.4` →
      `v[IP]`; leave unchanged `999.1.1.1`, `256.1.1.1`, `1.2.3.4.5`, `1.2.3.45678`, `1.2.3`,
      `1.2.3.4.5.6`. Assert the returned per-line `Counter` alongside the text in each case.
- [X] T012 [US1] Add card recognition tests to `tests/test_redact.py` (same file as T011, so not
      parallel). FR-015, FR-016: `4111111111111111`, `4111 1111 1111 1111`,
      `4111-1111-1111-1111`, and mixed single separators `4111-1111 1111-1111` all → `[CARD]`.
      FR-017: `1234567890123` unchanged (13 digits, Luhn fails). FR-016: a 12-digit run unchanged
      (too short even if Luhn-valid); `4111  1111  1111  1111` (doubled spaces) unchanged —
      doubled separators break the run into 4-digit pieces. FR-018: an unbroken run of 20+ digits
      (e.g. `"9" * 25`, and a 25-digit run containing a Luhn-valid 16-digit stretch) left
      **entirely** unchanged — "length disqualifies the run and the checksum is never consulted
      to rescue part of it". FR-019a: `99 4111 1111 1111 1111` → `99 [CARD]` (the 18-digit
      candidate at offset 0 fails Luhn with sum 48 and the 14-digit one with sum 42; the 16
      digits after the space pass). FR-019: a start position where a longer *and* a shorter
      candidate both pass Luhn redacts the longer. Edge: `4111 1111 1111 11x1` unchanged.
      `4111 1111 1111 1111, ref` → `[CARD], ref` — a redaction never begins or ends on a space or
      hyphen.
- [X] T013 [US1] Add pass-through, overlap, and precedence tests to `tests/test_redact.py`.
      FR-005: every character not part of a match appears unchanged and in position. FR-006: a
      line with nothing to redact is returned identical, including leading and trailing
      whitespace, and blank/whitespace-only lines are returned exactly. FR-020: spans never
      overlap or nest — each character belongs to at most one match. FR-021: earliest start wins,
      and at the same start the order is email → IPv4 → card; cover `admin@1.2.3.4` → one
      `[EMAIL]` and `1234567890123@example.com` → one `[EMAIL]` (both alternatives can start at
      offset 0; email is written first and wins). FR-022: input already containing literal
      `[EMAIL]`, `[IP]`, or `[CARD]` passes through unchanged and uncounted, and substituted
      placeholder text is not rescanned. FR-026: three addresses on one line return a `Counter`
      with `emails == 3`, and an absent category reads as `0`.
- [X] T014 [P] [US1] Create `tests/test_cli.py` with the stdin contract tests, using the
      `run_cli` helper and comparing raw `bytes`. FR-002: with no FILE operand, input is read
      from standard input. SC-001 (byte-exact worked examples): `printf 'user jane@example.com
      from 10.0.0.7\n'` → stdout exactly `user [EMAIL] from [IP]\n`, exit 0; `printf 'paid with
      4111 1111 1111 1111, ref 1234567890123\n'` → stdout exactly `paid with [CARD], ref
      1234567890123\n`, exit 0. FR-007: a line ending `\r\n` comes back ending `\r\n`, a bare
      `\r` is ordinary text and not a line boundary, and a mixed-ending input keeps each line's
      own ending. FR-007a: a final line without a newline comes back without one, and one with a
      newline keeps it. FR-005a: input containing `b"\xff"` beside an email yields `[EMAIL]`, the
      `\xff` byte unchanged in the output, no U+FFFD, and exit 0. FR-027: a fully-read,
      fully-written run exits 0. Empty stdin → empty stdout, exit 0.

### Implementation for User Story 1

- [X] T015 [US1] Add `_luhn_valid(digits: str) -> bool` to `src/logredact/redact.py`: walking the
      digits right to left, double every second digit, subtract 9 from any product over 9, sum
      all values, and return `sum % 10 == 0`. One loop over the digit string, no lookup table
      (research R-004).
- [X] T016 [US1] Add the three alternative patterns and the single compiled alternation to
      `src/logredact/redact.py`, built from the T005 fragments:
      `_EMAIL = rf"{_LOCAL}@(?:{_HOST}|{_QUAD}(?![0-9.]))"`,
      `_IPV4 = rf"(?<![0-9.]){_QUAD}(?![0-9.])"`,
      `_CARD = rf"(?<![0-9])[0-9](?:{_SEP}?[0-9]){{12,18}}(?![0-9])"`, then
      `PATTERN = re.compile(rf"(?P<email>{_EMAIL})|(?P<ip>{_IPV4})|(?P<card>{_CARD})")`. The
      alternative **order is the precedence rule** (FR-021) — `re.search` returns the leftmost
      position where any alternative matches and tries alternatives in written order there, so do
      not reorder them. Every inner group must be non-capturing so `match.lastgroup` reliably
      names the category (data-model.md §3, research R-003). The `_QUAD` alternative inside
      `_EMAIL` is research R-000's resolution of the FR-009/FR-021 conflict; keep the amendment
      note in contracts/redaction-patterns.md pointing at it.
- [X] T017 [US1] Add the per-length card patterns and selection helper to
      `src/logredact/redact.py`: `_CARD_BY_LENGTH`, a tuple of compiled
      `rf"[0-9](?:{_SEP}?[0-9]){{{L - 1}}}(?![0-9])"` for `L` in 19, 18, … 13 (longest first),
      built from the **same** `_SEP` fragment as `_CARD` so the two can never disagree about what
      a candidate is (plan.md Complexity Tracking). Add
      `_longest_valid_card(line: str, start: int) -> int | None` that tries each pattern with
      `.match(line, start)` in order and returns the end offset of the first (hence longest)
      whose extracted digits pass `_luhn_valid`, or `None` if none does (FR-019).
- [X] T018 [US1] Add `redact_line(line: str) -> tuple[str, collections.Counter]` to
      `src/logredact/redact.py`, implementing the two-cursor scan from data-model.md §3. Keep
      `copy_from` (start of input not yet copied) and `search_from` (where the next `search`
      begins). Loop on `PATTERN.search(line, search_from)`; read the category from
      `match.lastgroup`. For `email` and `ip`, accept at `match.end()`. For `card`, call
      `_longest_valid_card`; on success accept at the returned end offset (which may be **shorter**
      than `match.end()`), on failure **emit nothing, leave `copy_from` where it is, and set
      `search_from = match.start() + 1`** so a rejected candidate cannot hide a later valid one
      (FR-019a) — resuming at `match.end()` instead is the exact bug FR-019a forbids. On
      acceptance, append `line[copy_from:match.start()]` then `PLACEHOLDERS[category]` to the
      fragment list, set both cursors to the accepted end offset, and increment
      `counts[TALLY_KEYS[category]]`. Append the trailing `line[copy_from:]` and return
      `("".join(fragments), counts)`. `search_from` strictly increases every iteration, which is
      what makes the loop terminate.
- [X] T019 [US1] Wire the stdin path in `src/logredact/cli.py`: in `main`, when `args.files` is
      empty, iterate the text-wrapped stdin from T008 line by line (`for line in stream:` — each
      item includes its trailing `\n` when present), pass each line through `redact.redact_line`,
      and write the redacted text with the `_write` helper from T007; after the loop, `_flush`
      stdout. Process **one line at a time** and write immediately — never `read()` the whole
      stream, so peak memory is bounded by the longest line rather than the total input (SC-006).
      Return 0.

**Checkpoint**: User Story 1 is fully functional and independently testable — the tool is a
usable stdin→stdout redaction filter. `tests/test_redact.py` and the stdin half of
`tests/test_cli.py` are green. This is the MVP.

---

## Phase 4: User Story 2 - Redact one or more log files (Priority: P2)

**Goal**: Named FILE operands are read in command-line order into one concatenated redacted
stream on stdout, with `--count` recognized at any position and never mistaken for a file name.

**Independent Test**: Create two small files each containing personal data, run the tool with
both paths as arguments, and confirm stdout is the redacted contents of the first file followed by
the redacted contents of the second.

### Tests for User Story 2

- [X] T020 [P] [US2] Add the file-operand tests to `tests/test_cli.py` using `tmp_path` and
      `run_cli`. FR-003: two readable files are read in the order given and stdin is **not** read
      (pass non-empty stdin and assert it does not appear in the output). FR-004: stdout is one
      concatenated stream — redacted `a.log` then redacted `b.log` — and reversing the operands
      reverses the output. FR-001 (US2 acceptance scenario 3): all of `--count a.log b.log`,
      `a.log --count b.log`, and `a.log b.log --count` are accepted, `--count` is never treated
      as a file name, and `files` keeps command-line order. A single readable file reproduces
      every line in its original order with redactions applied. An empty file as the only operand
      → empty stdout, exit 0. A FILE operand of `-` is treated as a **literal relative path** to
      a file named `-`, not as standard input (spec Assumptions, contracts/cli.md Operands):
      create a file named `-` and assert its contents are redacted.
- [X] T021 [US2] Add `_iter_source_lines(path: str)` to `src/logredact/cli.py`: a generator that
      opens `path` with `open(path, encoding="utf-8", errors="surrogateescape", newline="\n")` —
      the same three settings as T008, for the same three requirements — yields its lines, and
      closes it. Open each source **lazily, immediately before its first line is read, and close
      it before the next source is opened** (data-model.md §1 lifecycle); this is what makes
      FR-029's "output already written for earlier sources remains written" true, and it means no
      source is opened at all on a help run (FR-030a).
- [X] T022 [US2] Wire the source loop in `main` in `src/logredact/cli.py`: when `args.files` is
      non-empty, iterate the paths in order, and for each one stream its lines through
      `redact.redact_line` and `_write`; when `args.files` is empty, fall back to the stdin path
      from T019. Keep the *display name* for each source as the path **exactly as given on the
      command line** — not resolved, not made absolute — because FR-028's diagnostic must use
      that spelling (data-model.md §1).

**Checkpoint**: User Stories 1 and 2 both work independently — the tool reads from a pipe or from
named files.

---

## Phase 5: User Story 3 - Confirm how much was redacted (Priority: P3)

**Goal**: `--count` writes exactly one tally line to stderr after all redacted output has been
written and flushed, without disturbing stdout.

**Independent Test**: Run with `--count` on input with a known number of each kind of personal
data, redirect stdout and stderr to separate places, and confirm the tally matches the known
counts while the redacted log is unaffected.

### Tests for User Story 3

- [X] T023 [P] [US3] Add the tally tests to `tests/test_cli.py`. SC-001 third worked example:
      `printf 'a@b.io 1.2.3.4\n' | ... --count` → stdout exactly `[EMAIL] [IP]\n`, stderr exactly
      `emails=1 ips=1 cards=0\n`, exit 0. FR-023: the tally is a **single line of the exact form
      `emails=N ips=N cards=N` terminated by a newline** — assert the bytes verbatim, including
      the fixed key order. FR-026: three email addresses on one line give `emails=3` (counts
      replacements, not distinct values), and a category with no replacements reports `0`.
      FR-023 across sources: totals span multiple lines **and multiple files**, not per line or
      per file. FR-025: without `--count`, a successful run writes **nothing** to stderr (assert
      zero bytes). FR-024: with `--count`, stdout is complete before the tally is written.
      Nothing-to-redact input → `emails=0 ips=0 cards=0\n`.
- [X] T024 [US3] Accumulate the tally in `main` in `src/logredact/cli.py`: create a
      `collections.Counter` before the source loop and `total.update(line_counts)` with the
      `Counter` returned by each `redact_line` call. Reading a never-incremented key yields `0`,
      which is exactly what FR-026 requires for an absent category — do not pre-seed the keys
      (data-model.md §4).
- [X] T025 [US3] Write the tally in `main` in `src/logredact/cli.py`, **after** `_flush(stdout)`
      succeeds and only when `args.count` is true:
      `sys.stderr.write(f"emails={total['emails']} ips={total['ips']} cards={total['cards']}\n")`.
      Name the three keys explicitly in the format string — the order is fixed and must not come
      from the `Counter`'s insertion order (data-model.md §4). The flush-then-tally ordering is
      FR-024, and it is also what makes a flush failure suppress the tally rather than print a
      tally for a truncated log (research R-007).

**Checkpoint**: User Stories 1, 2, and 3 all work independently.

---

## Phase 6: User Story 4 - Fail clearly on an unreadable file (Priority: P3)

**Goal**: Every failure path — unreadable FILE, invalid usage, failed write to stdout — produces
a specific diagnostic on stderr, no tally, no traceback, and exit status 2; `--help` is a
success, not a usage error.

**Independent Test**: Run the tool naming a path that does not exist and confirm stderr names
that path and the exit status is 2.

### Tests for User Story 4

- [X] T026 [P] [US4] Add the unreadable-source tests to `tests/test_cli.py`. FR-028: a
      nonexistent path named as a FILE → stderr contains that path **as spelled on the command
      line** and exit status is 2; an existing file whose permissions deny reading → same (skip
      this case when running as root, which can read a mode-000 file — see quickstart V6).
      FR-029: a readable file followed by an unreadable one → the readable file's redacted output
      is still on stdout, the unreadable file is named on stderr, the later sources are never
      opened, and exit status is 2. FR-029 with `--count`: **no** tally line is written — the
      only stderr output is the error message — and exit status is 2. SC-005: assert `Traceback`
      does **not** appear in stderr on every one of these paths.
- [X] T027 [US4] Add the usage and help tests to `tests/test_cli.py` (same file as T026). FR-030:
      `--nope` → a usage diagnostic on stderr, nothing on stdout, exit status 2. FR-030a: `--help`
      and `-h` each → usage text on stdout, **zero bytes** on stderr, exit status 0; combined
      with `--count` and with a FILE operand naming a nonexistent file, still usage on stdout,
      no tally, the file never opened, and exit 0 — a help request is a successful run, not a
      usage error.
- [X] T028 [US4] Add the failed-write tests to `tests/test_cli.py` (same file as T026/T027).
      FR-031a: generate an input large enough that stdout's buffer forces a real write (quickstart
      V8 uses 200,000 lines), pipe the tool's stdout into a reader that closes after the first
      line, and assert the tool's own exit status is **2** (never 0), stderr carries one concise
      diagnostic that output could not be written, and stderr contains no `Traceback` and no
      `Exception ignored`. With `--count` also passed, assert no tally line appears. SC-009:
      assert a truncated run and a complete run are distinguishable by exit status alone. FR-031:
      assert no diagnostic ever appears on stdout and no redacted log content ever appears on
      stderr.

### Implementation for User Story 4

- [X] T029 [US4] Add read-failure handling to the source loop in `src/logredact/cli.py`: wrap
      each source's open-and-iterate in `try/except OSError as exc` and, on failure, write
      `f"logredact: error: cannot read {path!r}: {exc}\n"` to stderr using the path exactly as
      given on the command line (prefix is stable; the trailing OS message is not asserted
      verbatim — contracts/cli.md "Diagnostic form"), **stop reading further sources**, skip the
      tally entirely even when `--count` was passed, and return 2 (FR-028, FR-029). This is the
      only `except OSError` on the read side and it re-raises as a clearer diagnostic that still
      fails — never swallow (Constitution Principle II).
- [X] T030 [US4] Add write-failure handling to `main` in `src/logredact/cli.py`: wrap the whole
      output-producing body in `try/except OutputWriteError`. In the handler, write the single
      line `logredact: error: failed writing to standard output\n` to stderr, skip the tally, then
      **redirect file descriptor 1 to `os.devnull` with `os.dup2`** before returning 2. The
      `dup2` is required, not cosmetic: CPython flushes `sys.stdout` during interpreter shutdown
      and a failing flush prints `Exception ignored in: <_io.TextIOWrapper ...>` with a traceback
      to stderr, which FR-031a forbids and SC-005 asserts the absence of (research R-007). Do
      **not** set `signal.signal(SIGPIPE, SIG_DFL)` — CPython's inherited `SIG_IGN` is what makes
      a closed pipe arrive as a catchable `BrokenPipeError` instead of killing the process with
      no diagnostic and no exit status 2. Because `OutputWriteError` is not an `OSError`, it
      propagates past the T029 read handler to this one.
- [X] T031 [US4] Audit `src/logredact/cli.py` and `src/logredact/redact.py` for stream discipline
      and exception hygiene (FR-031, Constitution Principle II): confirm no diagnostic is ever
      written to stdout, no redacted content is ever written to stderr, there is no bare `except:`
      and no `except Exception: pass`, the only `except OSError` sites are the two from T007 and
      T029, and the only statuses `main` can return are 0 and 2 (status 1 is never produced).

**Checkpoint**: All four user stories are independently functional. Every failure path has its
own diagnostic and exit status 2.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The success criteria that span stories, the coverage audit the constitution demands,
and end-to-end validation.

- [X] T032 [P] Create `tests/test_fidelity.py` with SC-002 and SC-003. SC-002: a mixed fixture of
      at least 200 lines containing known planted personal data **and** known look-alikes
      (out-of-range octets, five-part dotted numbers, Luhn-failing digit runs, 20+ digit runs,
      doubled-separator groups); assert 100% of the planted data is redacted and 0% of the
      look-alike tokens are altered. SC-003: for input containing no personal data, output is
      byte-identical to input — cover blank lines, unusual whitespace, `\r\n` endings, mixed
      endings, a bare `\r`, bytes that are not valid UTF-8, and a missing final newline in one
      fixture (quickstart V2 is the manual form of this check).
- [X] T033 Add SC-008 to `tests/test_fidelity.py` (same file as T032): run with `--count` over a
      fixture and assert the tally for each category equals the number of placeholders of that
      category counted in the redacted stdout stream.
- [X] T034 [P] Create `tests/test_performance.py` with SC-007 and SC-006. SC-007: redact a
      100,000-line log in under 30 s. SC-006: a single line of at least 10 MB is redacted
      correctly with peak memory on the order of the line rather than a multiple of it, plus a
      `@pytest.mark.slow` test (deselected by default via the T001 marker) exercising a
      multi-hundred-MB stream to show resident memory stays flat. Record in the test's docstring
      that the 1 GB figure in SC-006 is reached by **extrapolation** from the flat-memory
      measurement rather than by a 1 GB run in the default suite (research R-008).
- [X] T035 [P] Audit the requirement-to-test mapping for SC-004 against the table in
      [quickstart.md](./quickstart.md): confirm all 32 identifiers — FR-001 through FR-031 plus
      FR-005a, FR-007a, FR-019a, FR-030a, FR-031a — are each cited by at least one test's name or
      docstring, and update the quickstart table if any test landed under a different name.
- [X] T036 Run the ten validation scenarios V1–V10 from [quickstart.md](./quickstart.md) by hand
      from the repository root and confirm each produces its stated outcome, including `cmp`
      reporting `IDENTICAL` for V2 and `exit=2` from `PIPESTATUS[0]` for V8.
- [X] T037 Run the constitution's four quality gates from the repository root and confirm all
      pass: `python3 -m pytest` is green with no arguments; every functional requirement has a
      citing test (T035); no third-party import appears in `src/` (`tests/test_stdlib_only.py`);
      and every invalid-input path — missing file, unreadable file, invalid usage, failed write —
      has a test asserting both its diagnostic and its exit status 2.
- [X] T038 Surface research item [R-000](./research.md) to the reviewer in the completion report:
      the FR-009 / FR-021 conflict over `admin@1.2.3.4` is resolved in favour of FR-021 by the
      `quad` alternative in the email pattern, so address-literal addresses like `user@10.0.0.7`
      redact to `[EMAIL]` and count toward `emails`, not `ips`. Confirm the amendment note in
      [contracts/redaction-patterns.md](./contracts/redaction-patterns.md) still matches the
      shipped `_EMAIL` pattern in `src/logredact/redact.py`; reversing the decision means deleting
      the `|{_QUAD}(?![0-9.])` alternative and amending FR-021 and the Edge Cases entry.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS all user stories.**
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on US2/US3/US4.
- **User Story 2 (Phase 4)**: Depends on Foundational. Reuses `redact_line` from US1 but needs no
  US1 *task* beyond it; its own tests are independent.
- **User Story 3 (Phase 5)**: Depends on Foundational. Counts whatever sources exist, so it is
  testable against stdin alone without US2.
- **User Story 4 (Phase 6)**: Depends on Foundational. The unreadable-FILE path (T026, T029) is
  most meaningful once US2 exists; the usage/help path (T027) and the failed-write path (T028,
  T030) are independent of US2.
- **Polish (Phase 7)**: Depends on all four stories being complete.

### User Story Dependencies

- **US1 (P1)**: Independent. Delivers the MVP on its own.
- **US2 (P2)**: Independent of US1's CLI wiring; shares only the `redact_line` function.
- **US3 (P3)**: Independent — testable with piped input alone.
- **US4 (P3)**: Independent — its three failure paths are separately testable. Note the design
  dependency recorded in plan.md Complexity Tracking: T030's handler only works because T007 made
  `OutputWriteError` a non-`OSError`, so T007 (Foundational) must land before T029/T030.

### Within Each User Story

- Tests are written first and MUST fail before the implementation tasks begin.
- In `redact.py`: fragments (T005) → Luhn (T015) → patterns (T016) → per-length selection (T017)
  → `redact_line` (T018).
- In `cli.py`: write helpers (T007) → streams (T008) → parser (T009) → `main` skeleton (T010) →
  stdin wiring (T019) → source loop (T021, T022) → tally (T024, T025) → failure handlers (T029,
  T030).
- Tasks editing the same file are sequential and are never both marked `[P]`.

### Parallel Opportunities

- **Setup**: T002, T003, T004 run in parallel after T001.
- **Foundational**: T007 (`cli.py`) runs in parallel with T005–T006 (`redact.py`); T008–T010 are
  sequential within `cli.py`.
- **US1**: T011 (`test_redact.py`) and T014 (`test_cli.py`) run in parallel; T012 and T013 follow
  T011 in the same file.
- **Across stories**: once Phase 2 is done, US1, US2, US3, and US4 can be staffed in parallel —
  but note that T020, T023, T026, T027, T028 all edit `tests/test_cli.py`, so those four stories'
  *test* tasks serialize on that one file unless the work is split by developer.
- **Polish**: T032 (`test_fidelity.py`), T034 (`test_performance.py`), and T035 (audit) run in
  parallel; T033 follows T032.

---

## Parallel Example: Setup and Foundational

```bash
# After T001 creates pyproject.toml, launch the three independent scaffolding tasks:
Task: "T002 Create src/logredact/__init__.py and src/logredact/__main__.py"
Task: "T003 Create tests/conftest.py with the run_cli() subprocess helper"
Task: "T004 Create tests/test_stdlib_only.py Principle I gate"

# In Phase 2, the two runtime modules start independently:
Task: "T005 Create src/logredact/redact.py with the shared pattern fragments"
Task: "T007 Create src/logredact/cli.py with OutputWriteError and the write helpers"
```

## Parallel Example: User Story 1

```bash
# The two test files are independent; write them together, confirm both fail:
Task: "T011 Email and IPv4 recognition tests in tests/test_redact.py"
Task: "T014 Stdin contract tests in tests/test_cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T004).
2. Complete Phase 2: Foundational (T005–T010) — **blocks everything**.
3. Complete Phase 3: User Story 1 (T011–T019).
4. **STOP and VALIDATE**: run quickstart V1 and V3; `printf 'user jane@example.com from
   10.0.0.7\n' | PYTHONPATH=src python3 -m logredact` must print `user [EMAIL] from [IP]` and
   exit 0.
5. The tool is already useful as a pipeline filter at this point.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. + US1 → redacts anything reachable by a shell pipe (**MVP**, quickstart V1–V3).
3. + US2 → reads named files in order (quickstart V4).
4. + US3 → `--count` tally for reviewers (quickstart V5).
5. + US4 → trustworthy failure signalling (quickstart V6–V8).
6. + Polish → SC-002/003/006/007/008 proven, coverage audited (quickstart V9–V10).

Each step leaves the previous steps working.

### Parallel Team Strategy

1. Everyone completes Setup + Foundational together.
2. Then: Developer A takes US1 (the largest, on the critical path), Developer B takes US2 + US3,
   Developer C takes US4. B and C coordinate on `tests/test_cli.py` to avoid conflicts.
3. Polish is done jointly once all four stories are green.

---

## Notes

- `[P]` means different files and no dependency on an incomplete task.
- `[Story]` maps each task to a user story for traceability; Setup, Foundational, and Polish
  tasks carry no story label by design.
- Every test cites its FR or SC identifier in its name or docstring — that citation is what
  SC-004 and Constitution Principle III are checked against, so it is not optional.
- Commit after each task or logical group; stop at any checkpoint to validate a story in
  isolation.
- Exit status is only ever 0 or 2. A truncated output stream must never exit 0 (FR-031a, SC-009).
