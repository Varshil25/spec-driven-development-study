# Tasks: Import and HTML Export

**Input**: Design documents from `/specs/002-import-html-export/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/cli-contract-002.md](./contracts/cli-contract-002.md),
[quickstart.md](./quickstart.md)

**Tests**: Test tasks are **included and mandatory** for this feature. They are not an optional
extra here: FR-020 requires "at least one automated pytest test that identifies the requirement it
covers" for every functional requirement, and constitution Principle III (NON-NEGOTIABLE) treats a
requirement with no test as unimplemented regardless of the state of the code.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested and
delivered on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths appear in every task description

## Path Conventions

Single project, existing layout (plan.md "Project Structure"): package in `src/bookmarks/`, tests
flat in `tests/`, `src/` reached via `pythonpath = ["src"]` in `pyproject.toml`. All paths below
are relative to the repository root `/root/sdd-study/runs/R018`.

Files this feature touches, and no others:

| File | Status |
| ---- | ------ |
| `src/bookmarks/importer.py` | NEW |
| `src/bookmarks/store.py` | MODIFIED (`_insert_bookmark`, `add_bookmarks`) |
| `src/bookmarks/cli.py` | MODIFIED (`render_html`, `handle_import`, `import` subparser, `RENDERERS` key) |
| `tests/test_import.py` | NEW |
| `tests/test_html_export.py` | NEW |
| `tests/test_performance_002.py` | NEW (see Notes — deviation from plan.md recorded there) |

No existing test file is modified, and `src/bookmarks/__init__.py`, `src/bookmarks/__main__.py`,
`tests/conftest.py` and `pyproject.toml` are left untouched (FR-015, FR-019, FR-020, SC-006).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the environment and capture the pre-change baseline. No source file changes.

- [X] T001 Verify the interpreter and capture the pre-change suite baseline: run `python3 -VV`
      from the repository root and confirm the version is 3.11 or newer, then run
      `python3 -m pytest -q` and record the summary line verbatim (research.md records the
      expected baseline as `131 passed, 2 skipped`). This recorded line is the FR-015/SC-006
      reference that every later phase is compared against. Change no file.
- [X] T002 [P] Confirm `pyproject.toml` at the repository root needs no edit: it already declares
      `requires-python = ">=3.11"`, `pythonpath = ["src"]` and pytest as the only development
      dependency, and this feature adds no runtime dependency — the only new import anywhere is
      the standard-library `html` (FR-019, constitution Principle I, research R-107). Read-only
      check; make no change.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one decision both user stories depend on before any source file is edited.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T003 Confirm the fixtures already in `tests/conftest.py` — `db` (a fresh, not-yet-created
      store path), `run_cli` (real-subprocess CLI runner exposing `returncode`, `stdout`,
      `stderr` separately), `seed` and `seed_many` — cover everything `tests/test_import.py` and
      `tests/test_html_export.py` need, so neither new test file requires a change to
      `tests/conftest.py` or to any existing test file. Import files are written with pytest's
      `tmp_path`. Record the confirmation; change no file. This is what makes the FR-020/SC-006
      regression gate (`git status --short tests/` showing only new files) achievable
      (research R-110).

**Checkpoint**: Baseline recorded and fixture reuse confirmed — User Story 1 and User Story 2 can
now proceed, in parallel if staffed, since they share no source change.

---

## Phase 3: User Story 1 - Bring an existing collection in (Priority: P1) 🎯 MVP

**Goal**: `python -m bookmarks [--db PATH] import FILE --format csv|json` bulk-loads bookmarks
from either shape `export` writes, adds each one exactly as `add` would, prints `imported N`, and
on any file fault adds nothing at all, diagnoses what was wrong on stderr and exits 2 — leaving no
store file behind when none existed.

**Independent Test**: Write a small file in each shape, import each into a fresh store, then
`list` the collection in a separate invocation and check identifiers, titles and tags. Then repeat
with the thirteen damaged files of SC-003 and check the collection — and the absence of the store
file — afterwards. Fully testable without the HTML export existing.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST and confirm they FAIL before the implementation tasks T012–T019.**
> Every test name carries the requirement it covers, matching the existing convention
> (`test_fr018_…`), per constitution Principle III and research R-110. All of T004–T011 write to
> the same new file `tests/test_import.py`, so they are sequential, not parallel.

- [X] T004 [US1] Create `tests/test_import.py` with a module docstring naming its requirement
      range (FR-001 … FR-011 plus the User Story 3 round trip) and the FR-001 command-grammar
      tests, driven through the `run_cli` and `db` fixtures: `import` with no `FILE`, `import FILE`
      with no `--format`, and `import FILE --format html` / `--format xml` each write argparse's
      own usage diagnostic to stderr, write exactly `""` to stdout, and exit 2.
- [X] T005 [US1] Add the success-path tests for FR-002, FR-002a, FR-004 and FR-005 to
      `tests/test_import.py`: a two-record file in each shape prints exactly `imported 2\n` on
      stdout and nothing else, exiting 0; a header-only CSV and an empty JSON array each print
      exactly `imported 0\n` and exit 0; against a `--db` path that does not exist beforehand a
      successful `imported 0` **creates** the store file and leaves it holding no bookmarks, and a
      following `add https://a.example.com` prints `1`; file `id` values of `7` and `9` are
      disregarded so the bookmarks receive 1 and 2; importing three records into a store already
      holding two prints `imported 3`, leaves identifiers 1 and 2 unchanged, and issues
      identifiers above every identifier previously issued; identifiers ascend in file order.
- [X] T006 [US1] Add the FR-003 equivalence tests to `tests/test_import.py` — an imported bookmark
      is stored exactly as `add` would store it. Cover the four worked normalisation cases quoted
      from data-model.md, for **both** shapes: CSV field `python,docs` / JSON `["python","docs"]`
      → stored tag set `docs,python`; CSV `Python, DOCS ,python` / JSON
      `["Python"," DOCS ","python"]` → `docs,python` (trimmed, lower-cased, de-duplicated,
      alphabetical); CSV empty field / JSON `[]` → no tags; CSV `,,` / JSON `["","  "]` → no tags.
      Also assert a record with an empty title and no tags lists identically to a bookmark created
      by `add URL` with both options omitted, and that a title is stored verbatim.
- [X] T007 [US1] Add the FR-006 and FR-006a CSV shape tests to `tests/test_import.py`.
      **Accepted**: the header record `id,url,title,tags` exactly as `export --format csv` writes
      it; the header `"id","url","title","tags"`, which parses to the same four values in the same
      order (compared *after* CSV parsing, per the Clarifications); the header record alone →
      `imported 0`, exit 0; a quoted fourth field `"docs,python"` yielding **two** tags rather
      than a parse error; `\r\n` record terminators; a quoted field containing an embedded line
      break and a doubled `""`. **Rejected with exit 2**: header `name,link`; a zero-byte file
      (no header record at all); a row of 3 fields; a row of 5 fields; a completely blank line
      between rows; a blank line after the last row. Assert explicitly that the single line feed
      terminating the final row is *not* a blank record, by importing the tool's own
      `export --format csv` output without error.
- [X] T008 [US1] Add the FR-007 JSON shape tests to `tests/test_import.py`. **Accepted**: an array
      of objects each carrying `url` (string), `title` (string) and `tags` (array of strings); an
      `id` key present, with its value disregarded; an empty array → `imported 0`, exit 0.
      **Rejected with exit 2**: a top level that is a single object rather than an array; an
      element that is a string rather than an object; a record missing `tags`; a record missing
      `title`; a record missing `url`; `tags` holding a string; `tags` holding a number; `tags`
      holding a list containing a non-string; a record carrying the unrecognised key `note`;
      malformed JSON text that `json.loads` cannot parse at all.
- [X] T009 [US1] Add the FR-008 and FR-009 tests to `tests/test_import.py`: a valid JSON file
      declared `--format csv` and a valid CSV file declared `--format json` each exit 2 with a
      diagnostic — the shape is never inferred from the file's name, extension or contents and
      never falls back to the other shape; a CSV file and a JSON file each prefixed with a UTF-8
      byte-order mark import normally, with the first header field read as `id` (not `﻿id`)
      and the first address intact; a file whose bytes are `b"\xff\xfe\x00bad"` exits 2 with a
      diagnostic naming the file, because invalid UTF-8 is a file problem.
- [X] T010 [US1] Add the FR-010 diagnostic-shape test to `tests/test_import.py` as a single
      `pytest.mark.parametrize` over the damage kinds SC-003 enumerates — absent file, a
      directory, zero-byte file, wrong header record, wrong field count, blank line, bytes that
      are not valid UTF-8, malformed JSON text, top level not a list, element not an object,
      record missing a key, unrecognised key, `tags` not an array of strings, and an address
      failing the scheme rule — asserting the same triple for every one: `result.returncode == 2`,
      `result.stdout == ""`, and a non-empty `result.stderr` that names the file (where a file is
      at fault) together with what was invalid and what was expected.
- [X] T011 [US1] Add the FR-011 and FR-017 atomicity tests to `tests/test_import.py`: after a
      failing import against a `--db` path that did not exist beforehand, the store file **does
      not exist** and a following `add` prints `1`; after a failing import against a store already
      holding two bookmarks, `list` output is byte-identical to before and the next `add` receives
      identifier 3; a file whose *last* record has an address failing the scheme rule adds none of
      the valid records preceding it; `--db no/such/dir/x.db` with a wholly valid import file exits
      **1** (a store problem) and not 2, leaving the two error classes distinct; and no import
      invocation in any of the above exits 3.

### Implementation for User Story 1

- [X] T012 [US1] Extract `_insert_bookmark(connection, url, title, tags)` in
      `src/bookmarks/store.py` from the body of the existing `add_bookmark`: insert the
      `bookmarks` row, call the existing `normalise_tags`, insert the `tags` rows when the
      normalised list is non-empty, **do not commit**, and return `cursor.lastrowid`.
      `add_bookmark` becomes `check_url` → `_insert_bookmark` → `connection.commit()` → return the
      identifier, with behaviour identical to today. The pre-existing `tests/test_add.py` and
      `tests/test_store.py` must still pass unmodified (FR-003, FR-015, research R-106).
- [X] T013 [US1] Add `add_bookmarks(connection, records)` to `src/bookmarks/store.py`: call the
      existing `check_url` on **every** record's `url` first, then call `_insert_bookmark` for each
      record in list order, then `connection.commit()` exactly **once**, returning the number
      inserted. Records are the `{"url", "title", "tags"}` dicts of data-model.md, with `tags` the
      comma-joined string form. Checking all addresses before inserting any is what keeps the
      atomicity guarantee intact even though `check_url` lives in this module; the single commit is
      what keeps 1,000 inserts inside the SC-005 budget (FR-003, FR-005, FR-010, FR-011, SC-005,
      research R-105, R-106).
- [X] T014 [P] [US1] Create `src/bookmarks/importer.py` with a module docstring naming its
      requirements, `import csv`, `import json`, `from . import store`, and the file reader: open
      the path with `open(path, encoding="utf-8-sig", newline="")` and read the whole text inside
      one `try`/`except (OSError, UnicodeDecodeError)` that raises
      `store.BookmarkError(f"cannot read {path}: …", 2)` naming the file and the reason. The
      `utf-8-sig` codec does UTF-8 decoding and the single-leading-byte-order-mark rule in one
      step; `newline=""` keeps a line break inside a quoted CSV field part of that field; no
      `errors=` parameter is passed, so undecodable bytes raise rather than becoming U+FFFD.
      `IsADirectoryError` and `PermissionError` are `OSError` subclasses, so absent / directory /
      access-denied are one clause. This module **opens no database** (FR-009, FR-010, FR-011,
      research R-101, R-109). Parallel with T012/T013 — different file.
- [X] T015 [US1] Add the CSV parser to `src/bookmarks/importer.py`: `csv.reader` over the text with
      the **default dialect** (the writer side uses defaults, so the reader must too, or the
      SC-001 round trip is not a round trip). Compare the first yielded record against
      `["id", "url", "title", "tags"]`; if it differs, or if no record was yielded at all (a
      zero-byte file has no header), raise `store.BookmarkError(…, 2)` naming the file, the
      expected header record `id,url,title,tags` and what was found. Require
      `len(record) == 4` for every later record, raising `store.BookmarkError(…, 2)` naming the
      file, the 1-based line number, the expected count of 4 and the count found — a completely
      blank line yields `[]`, length 0, and so fails this check wherever it occurs. Do not filter
      or skip any record. Build `{"url": record[1], "title": record[2], "tags": record[3]}`,
      discarding field 0 unvalidated because it is not used (FR-004, FR-006, FR-006a, FR-010,
      research R-102). Do **not** use `csv.DictReader`: it would silently absorb a wrong header
      and a wrong field count.
- [X] T016 [US1] Add the JSON parser to `src/bookmarks/importer.py`: `json.loads(text)`, catching
      `json.JSONDecodeError` and raising `store.BookmarkError(…, 2)` naming the file and the
      decoder's own message. Then validate by hand in exactly this fixed order, each failure
      raising `store.BookmarkError(…, 2)` with its own message naming the file, the 1-based record
      number where applicable, what was wrong and what was expected: the top level is a `list`;
      each element is a `dict`; the element's key set contains `url`, `title` and `tags` (a missing
      one is reported as a missing required key, **never** defaulted to empty) and contains nothing
      outside `{"id", "url", "title", "tags"}` (an unrecognised key is a shape error, not silently
      dropped data); `url` and `title` are each `str`; `tags` is a `list` whose every element is a
      `str`. Build `{"url": record["url"], "title": record["title"], "tags": ",".join(record["tags"])}`
      — joining with `,` so the value reaches the existing `store.normalise_tags` in the same form
      an `add --tags` value does, and discarding any `id` (FR-004, FR-007, FR-010, research R-103,
      R-104). No separate element-wise tag normaliser is written.
- [X] T017 [US1] Add the public entry point `read_records(path, shape)` to
      `src/bookmarks/importer.py`: read the file with T014's reader, then dispatch to T015's or
      T016's parser on the declared `shape` **alone**, returning the list of
      `{"url", "title", "tags"}` dicts in file order. The file's name, extension and contents are
      never consulted, and there is no fallback to the other shape when the declared one does not
      parse (FR-005, FR-008, research R-101).
- [X] T018 [US1] Add `handle_import(args)` to `src/bookmarks/cli.py` beside the existing handlers:
      call `importer.read_records(args.file, args.format)` **before** `store.open_store` — the
      ordering is load-bearing, since `open_store` is what creates the store file, so validating
      first is the only design that delivers "a failed import creates no store file" and keeps file
      failures (status 2) structurally separate from store failures (status 1). Then
      `store.open_store(args.db)`, `store.add_bookmarks(connection, records)` inside a
      `try`/`finally` that closes the connection, then `print(f"imported {count}")`, then
      `return 0`. Add `from . import importer` to the module imports. Raise nothing new:
      `store.BookmarkError` carries its status as data, so `cli.main`'s single existing `except`
      clause renders every FR-010 diagnostic with no new error path (FR-002, FR-002a, FR-010,
      FR-011, FR-017, FR-018, research R-105, R-109).
- [X] T019 [US1] Register the `import` subcommand in `build_parser()` in `src/bookmarks/cli.py`:
      `subcommands.add_parser("import", help=…)`, a positional `file` with `metavar="FILE"`, and
      `--format` with `required=True, choices=("csv", "json")` — deliberately **not**
      `sorted(RENDERERS)`, because `html` is an export form only and `import --format html` does
      not exist — then `set_defaults(handler=handle_import)`. `ArgumentParser.error` stays
      un-overridden, so a missing `FILE`, a missing `--format` or an unsupported `--format` value
      gets argparse's own stderr diagnostic and exit 2 with no hand-written validation (FR-001,
      FR-008, spec Assumptions).
- [X] T020 [US1] Run `python3 -m pytest tests/test_import.py -v` and confirm every test added in
      T004–T011 now passes, then run `python3 -m pytest -q` and confirm the whole suite is green
      with the baseline recorded in T001 unchanged, and `git status --short tests/` lists
      `tests/test_import.py` as new with no existing test file modified.

**Checkpoint**: User Story 1 is complete and independently testable — bulk import works for both
shapes, every damaged file is rejected cleanly with nothing added and no store file created, and
every pre-existing command still behaves exactly as before. **This is the MVP.**

---

## Phase 4: User Story 2 - Publish the collection as a web page (Priority: P2)

**Goal**: `export --format html` prints the whole collection in ascending identifier order as one
fixed, byte-predictable HTML page, escaping exactly the four substitutions of FR-014 and no
others — while `export --format csv` and `export --format json` stay byte-for-byte unchanged.

**Independent Test**: Seed a store, request `export --format html`, and compare the produced text
byte-for-byte with the page in the contract's worked example. Fully testable without the import
command existing — this phase shares no source change with Phase 3 and may be built in parallel.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST and confirm they FAIL before T026–T027.** T021–T025 all write to
> the same new file `tests/test_html_export.py`, so they are sequential; T021 is parallel with
> Phase 3's test tasks, which write to a different file.

- [X] T021 [P] [US2] Create `tests/test_html_export.py` with a module docstring naming its
      requirement range (FR-012 … FR-014, FR-015, SC-004) and the FR-012 page-layout tests, using
      the `db`, `seed` and `run_cli` fixtures: for the contract's two-bookmark store
      (`https://docs.python.org` / `Python docs` / `python,docs`, then `https://example.com` / no
      title / no tags) assert `result.stdout` equals the worked-example page **byte for byte** —
      the five fixed opening lines, the two `<li>` lines, the three fixed closing lines — with
      exit 0; an empty collection prints the same page with **no** `<li>` line between `<ul>` and
      `</ul>` and exits 0; a bookmark with no tags still carries `<small></small>`; the `<li>`
      lines appear in ascending identifier order; and no bookmark identifier appears anywhere on
      the page.
- [X] T022 [US2] Add the FR-013 byte tests to `tests/test_html_export.py`: every line of the page,
      including the last, is terminated by a single `\n`; the page ends with exactly one trailing
      newline and no additional blank line; no `\r` appears anywhere in the output; and a title
      containing non-ASCII characters (`Café — ünïcode`) is emitted literally as UTF-8 rather than
      as entities or escapes. Read the output as bytes where the assertion is about bytes.
- [X] T023 [US2] Add the FR-014 closed-escaping tests to `tests/test_html_export.py`: for the
      contract's worked example — address `https://x.example.com/?a=1&b=2"z`, title
      `Tom's "A&B" <tag>` — assert the single `<li>` line byte for byte, which pins all four
      substitutions at once. Then assert each half of the closed set separately: `&` → `&amp;`,
      `<` → `&lt;`, `>` → `&gt;` in the `href` value, the link text and the `<small>` text; `"` →
      `&quot;` inside the `href` value **only**, staying literal in the title and the tags; the
      apostrophe staying literal in both places; a stored title already containing the text
      `&amp;` emitting `&amp;amp;`, proving `&` is substituted first and no escape is doubly
      escaped; and nothing else substituted — `/`, `=`, `?`, `:` and non-ASCII characters all
      literal.
- [X] T024 [US2] Add the SC-004 reader test to `tests/test_html_export.py`: for a collection whose
      titles and addresses include ampersands, angle brackets, quotation marks and non-English
      characters, parse the emitted page with `html.parser.HTMLParser` (standard library, used
      test-side only) and assert it finds exactly one `<a>` element per bookmark, in identifier
      order, each element's `href` equal to the stored address and each element's text equal to the
      stored title. This checks the escaping is *correct*, not merely stable.
- [X] T025 [US2] Add the FR-015 preserved-behaviour tests to `tests/test_html_export.py` (in the
      new file — `tests/test_export.py` is the untouched regression evidence and must not be
      edited): for a seeded store, `export --format csv` and `export --format json` stdout is
      exactly what the pre-existing contract specifies, unaffected by the new format;
      `export --format fancy` writes argparse's diagnostic to stderr, writes exactly `""` to
      stdout and exits 2; and `export --help` lists the choices as `csv,html,json`.
- [X] T026 [US2] Implement `render_html(rows)` in `src/bookmarks/cli.py`, beside the existing
      `render_csv` and `render_json`: write the five fixed opening lines (`<!DOCTYPE html>`,
      `<html>`, `<head><meta charset="utf-8"><title>Bookmarks</title></head>`, `<body>`, `<ul>`),
      then one `<li><a href="URL">TITLE</a> <small>TAGS</small></li>` line per row in the order
      `rows` arrives (already ascending by identifier from `list_bookmarks`), then the three fixed
      closing lines (`</ul>`, `</body>`, `</html>`). Emit through `sys.stdout.write` with an
      explicit `"\n"` on every line including the last, which is unambiguous under the
      `newline=""` stdout reconfiguration `main` already performs. Escape with
      `html.escape(value, quote=False)` for the title and the tag text, and
      `html.escape(url, quote=False).replace('"', "&quot;")` for the `href` value — the
      `quote=False` branch is exactly `&`→`&amp;`, `<`→`&lt;`, `>`→`&gt;` in that order, leaving
      `"` and `'` literal, so the explicit `"` replacement applies to the one attribute only and
      runs after an escape that never introduces a `"`. `quote=True` is unusable: it would also
      rewrite `'` as `&#x27;`, which FR-014 forbids. `TAGS` is `",".join(row["tags"])`, the rows
      already being alphabetical, with no spaces around the commas and the element present even
      when the join is empty (FR-012, FR-013, FR-014, research R-107, R-108).
- [X] T027 [US2] Add `import html` to the standard-library imports at the top of
      `src/bookmarks/cli.py` and register `"html": render_html` in the existing `RENDERERS` dict.
      That one key delivers dispatch through the existing `RENDERERS[args.format](rows)` in
      `handle_export`, the `--format` choices through the existing `choices=sorted(RENDERERS)` (now
      `csv, html, json`), the help text, and argparse's own diagnostic plus exit 2 for an
      unsupported value — with no new validation code and nothing on the CSV or JSON path touched,
      which is what makes FR-015/SC-006 true by construction (FR-012, FR-015, research R-108).
- [X] T028 [US2] Run `python3 -m pytest tests/test_html_export.py -v` and confirm T021–T025 pass,
      then run `python3 -m pytest tests/test_export.py tests/test_cli_contract.py -q` and confirm
      the pre-existing export and contract tests pass **unmodified** — the FR-015/SC-006 evidence.

**Checkpoint**: User Stories 1 and 2 both work independently. The HTML page is byte-predictable and
the CSV and JSON exports are untouched.

---

## Phase 5: User Story 3 - Move a collection between machines (Priority: P3)

**Goal**: A collection exported on one machine imports on another, in either shape, with every
address, title and label surviving the trip — including commas, quotation marks, embedded line
breaks and non-English characters.

**Independent Test**: Seed a store with awkward values, export it, import the result into a second
empty store, and compare the two `list` outputs field by field.

**Depends on**: Phase 3 (import) **and** Phase 4 is *not* required — the round trip uses the CSV
and JSON shapes only, so this phase needs Phase 3 alone.

- [X] T029 [US3] Append the round-trip tests to `tests/test_import.py` (the round trip is
      import-driven and belongs with the import tests, per research R-110): seed a store with the
      awkward values of the spec's Acceptance Scenarios — a title containing a comma, a title
      containing a quotation mark, a title containing an embedded line break, a title with
      non-English characters (`Café — ünïcode`), a bookmark carrying several tags, a bookmark
      carrying none, and a second bookmark reusing an address already stored. For each of `csv`
      and `json`: run `export --format FMT`, write the stdout to a file under `tmp_path`, import
      that file into a second, previously non-existent store with the same format, and assert the
      second store's `list` stdout is identical to the first's — proving identifiers renumber from
      1 while addresses, titles and tags match field for field. Assert the duplicate address is
      present **twice** afterwards: the import performs no merging and no de-duplication.
- [X] T030 [US3] Add the SC-001 fidelity test to `tests/test_import.py`: seed 1,000 bookmarks with
      the existing `seed_many` fixture, and for each of `csv` and `json` export the collection,
      import it into a fresh store, and assert all 1,000 arrive with addresses, titles and tags
      identical to the originals and in the same order — one export command and one import command
      per shape, compared as whole `list` outputs.
- [X] T031 [US3] Run `python3 -m pytest tests/test_import.py -q` and confirm the round-trip and
      fidelity tests pass alongside the Phase 3 tests in the same file.

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T032 [P] Create `tests/test_performance_002.py` with the two SC-005 budgets, following the
      timing pattern of the existing `tests/test_performance.py` (a `time.perf_counter()` bracket
      around a real `run_cli` subprocess, asserting `returncode == 0` first): generate a
      1,000-record CSV file under `tmp_path` with `csv.writer(..., lineterminator="\n")`, assert
      `import big.csv --format csv` prints `imported 1000` and completes in under 5 seconds; then,
      for a store seeded by `seed_many` with 1,000 bookmarks, assert `export --format html`
      returns in under 1 second. A **new** file rather than an edit to
      `tests/test_performance.py` — see Notes for why.
- [X] T033 Run the quickstart validation by hand from the repository root, following
      [quickstart.md](./quickstart.md) Scenarios 1–5 in order in a scratch directory: both shapes
      into a fresh store and the append check, the empty-file-creates-the-store check, all thirteen
      damaged files checked for the stderr / empty-stdout / status-2 triple plus the final `ls`
      reporting no store file, the accepted oddities (byte-order mark, CRLF, quoted header), the
      HTML page including the characters that must stay literal, the round trip through both
      shapes, and the two performance budgets. Record any discrepancy against the contract as a
      defect rather than adjusting the expectation.
- [X] T034 Run the FR-015/SC-006 regression gate — quickstart.md Scenario 6, which is the gate that
      decides the feature is done: `python3 -m pytest -q` from the repository root passes with the
      T001 baseline count unchanged and the new tests added; `python3 -m pytest -q -k "fr014 or
      fr011"` spot-checks that a requirement's coverage is reachable by name; and
      `git status --short tests/` lists only the three new test files with **no existing test file
      modified**.
- [X] T035 Review the requirement-to-test mapping for completeness (constitution Principle III,
      Gate 1): confirm each of FR-001 … FR-020 in [spec.md](./spec.md) is named by at least one
      test in `tests/test_import.py`, `tests/test_html_export.py` or
      `tests/test_performance_002.py`, or — for FR-015, FR-016, FR-019 and FR-020 — is evidenced by
      the pre-existing suite passing unmodified and by the untouched `pyproject.toml`. Add a test
      for any requirement that turns out to be unnamed, and record the mapping in the commit
      message.
- [X] T036 Simplicity and dependency review (constitution Gates 3 and 5) across
      `src/bookmarks/importer.py`, `src/bookmarks/store.py` and `src/bookmarks/cli.py`: confirm no
      third-party import appears in any shipped module and that the only new import anywhere is the
      standard-library `html`; confirm nothing was built that no requirement demands — in
      particular that none of the alternatives research explicitly rejected has crept in (a JSON
      schema-validation layer, a second element-wise tag normaliser, a separate `html.py` module, a
      new exception type for file errors, rollback machinery, a `--continue-on-error` or dry-run
      option, `import --format html`, or any page styling); and confirm the docstrings in the new
      and changed functions name the requirements they implement, matching the convention already
      used throughout `store.py` and `cli.py`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1, T001–T002)**: no dependencies; start immediately.
- **Foundational (Phase 2, T003)**: depends on Setup; blocks both user stories.
- **User Story 1 (Phase 3, T004–T020)**: depends on Phase 2 only.
- **User Story 2 (Phase 4, T021–T028)**: depends on Phase 2 only. Shares **no source change** with
  Phase 3, so the two phases are genuinely independent and may run concurrently.
- **User Story 3 (Phase 5, T029–T031)**: depends on Phase 3 (the import command). Does **not**
  depend on Phase 4 — the round trip uses the CSV and JSON shapes only.
- **Polish (Phase 6, T032–T036)**: T032 depends on Phase 3 and Phase 4; T033–T036 depend on every
  story phase that is being delivered.

### Within User Story 1

- Tests T004–T011 are written first and must fail before T012–T019 (constitution Principle III).
- T012 (extract `_insert_bookmark`) before T013 (`add_bookmarks`, which calls it).
- T014 (file reader) before T015 and T016 (the two parsers, which consume its text) before T017
  (dispatch, which calls both).
- T013 and T017 before T018 (`handle_import` calls both).
- T018 before T019 (the subparser's `set_defaults(handler=handle_import)` needs the handler).
- T020 last in the phase.

### Within User Story 2

- Tests T021–T025 are written first and must fail before T026–T027.
- T026 (`render_html`) before T027 (registering it in `RENDERERS`).
- T028 last in the phase.

### Parallel Opportunities

- T002 runs in parallel with T001.
- **T014 runs in parallel with T012 and T013**: `src/bookmarks/importer.py` is a new file and
  `src/bookmarks/store.py` is a different one.
- **All of Phase 4 runs in parallel with all of Phase 3**: Phase 3 touches `store.py`,
  `importer.py` and `cli.py`'s handlers and parser; Phase 4 touches `cli.py`'s renderers and
  `RENDERERS` dict. The only shared file is `cli.py`, in non-overlapping regions, so with two
  people the two stories can proceed at once with one merge of that file.
- **T021 runs in parallel with T004–T011**: different new test files.
- T032 runs in parallel with T033.
- Everything else within a story is sequential, because the tasks write to the same file.

---

## Parallel Example: Phase 3 and Phase 4 together

```bash
# Two people, after T003 is done. No source file is contended except cli.py,
# in non-overlapping regions.

# Person A — User Story 1 (import):
Task: "T004–T011 write tests/test_import.py"
Task: "T012–T013 modify src/bookmarks/store.py"
Task: "T014–T017 create src/bookmarks/importer.py"
Task: "T018–T019 add handle_import and the import subparser to src/bookmarks/cli.py"

# Person B — User Story 2 (HTML export):
Task: "T021–T025 write tests/test_html_export.py"
Task: "T026–T027 add render_html and its RENDERERS key to src/bookmarks/cli.py"
```

## Parallel Example: inside User Story 1

```bash
# T014 touches a brand-new file; T012 and T013 touch an existing, different one.
Task: "T012 Extract _insert_bookmark in src/bookmarks/store.py"
Task: "T014 Create src/bookmarks/importer.py with the utf-8-sig file reader"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (T001–T002) — record the baseline.
2. Phase 2: Foundational (T003) — confirm fixture reuse.
3. Phase 3: User Story 1 (T004–T020) — the import command.
4. **STOP and VALIDATE**: run quickstart.md Scenarios 1 and 2 plus
   `python3 -m pytest tests/test_import.py -v`, and confirm the pre-existing suite still passes
   unmodified.
5. Deliverable: bulk entry into the collection, with every damaged file rejected cleanly and no
   store file left behind on failure. This is the half that writes to the collection and carries
   all the risk, which is why it is first.

### Incremental Delivery

1. Setup + Foundational → baseline recorded, fixtures confirmed.
2. Add User Story 1 → validate independently → **MVP**.
3. Add User Story 2 → validate independently (the page is byte-asserted, and CSV/JSON are proven
   unchanged by the untouched `tests/test_export.py`).
4. Add User Story 3 → validate independently (the round trip proves the two halves agree about the
   file shapes).
5. Polish (T032–T036) → performance budgets, quickstart by hand, the regression gate, the
   requirement-to-test mapping, and the simplicity review.

Each story adds value without changing anything an earlier one delivered.

---

## Notes

- **One deviation from plan.md, recorded deliberately.** plan.md's "Project Structure" lists
  `tests/test_performance.py` as MODIFIED, while the same plan's Testing paragraph, research R-110,
  FR-020, SC-006 and quickstart.md Scenario 6 all require that **no existing test file is
  modified** — Scenario 6 checks it mechanically with `git status --short tests/`. The two cannot
  both hold. T032 therefore puts the SC-005 budgets in a **new** `tests/test_performance_002.py`
  rather than editing `tests/test_performance.py`, which satisfies the mechanically checked
  requirement and keeps the performance tests recognisably together. If the plan's file list is
  preferred instead, T032 and T034 are the only tasks that change.
- **Three further deviations, found while implementing and recorded here** (all verified by the
  full suite and by quickstart Scenarios 1–6):
  1. **The scheme check runs in `importer.read_records`, not only in `store.add_bookmarks`.**
     T013's placement alone was not enough: with `check_url` reached only from
     `add_bookmarks`, which runs *after* `open_store`, a file whose record carried
     `ftp://…` exited 2 but **left a store file behind** — a direct FR-011 breach, caught by
     T011's test. data-model.md's validation order puts the address check at step 3, before the
     store is opened, so `read_records` now performs it too. `add_bookmarks` keeps its own check
     so its all-or-nothing guarantee holds for any caller; the repeat costs one string
     comparison per record.
  2. **`cli.py` does not import `html`.** Research R-107 and T026/T027 chose
     `html.escape(value, quote=False)`, but the pre-existing `tests/test_cli_contract.py` pins
     the runtime import surface to an exact six-module set, and FR-020 and SC-006 require the
     earlier suite to pass **with no test file modified** — the gate T034 checks mechanically.
     Importing `html` would have forced an edit to that test. FR-014's substitution set is
     *closed* at four entries, so `_escape` spells the three replacements out in `&`-first order
     and `_escape_attribute` adds `"`→`&quot;`. Equivalence is not assumed: a new test in
     `tests/test_html_export.py` asserts both functions agree with
     `html.escape(…, quote=False)` over twelve inputs, keeping the standard library as the
     oracle on the test side, where importing it is free.
  3. **`importer.py` does not import `io`.** For the same pinned-import-surface reason, the CSV
     text is chunked for `csv.reader` by a four-line `_chunks` helper that splits on `\n` alone
     (verified: `csv.reader` strips a trailing `\r`, so FR-006's two record terminators both
     work, and a break inside a quoted field is preserved because the reader concatenates
     chunks while inside the quotes). `str.splitlines` would have been wrong — it also splits on
     form feed, vertical tab and U+2028, which are ordinary characters inside a CSV field.
  Net effect: this feature adds **no new runtime import at all**, which is stricter than
  FR-019 and constitution Principle I require.
- One test assumption was corrected rather than the code: a round-trip count used
  `splitlines()` on `list` output, which over-counts when a title holds a line break — accepted
  behaviour per the spec's Edge Cases. The test now reassembles records on the `^\d+\t` boundary.
- `[P]` means a different file and no dependency on an incomplete task. Tasks writing to the same
  file are never marked `[P]`, which is why most tasks within a story are sequential.
- Test names carry the requirement they cover (`test_fr006a_…`), matching the existing convention
  in `tests/`; constitution Principle III makes the mapping, not just the coverage, a requirement.
- CLI behaviour is asserted through the existing `run_cli` subprocess fixture, because the exit
  statuses of FR-010 and FR-017 are **process** statuses that an in-process call to `cli.main`
  cannot evidence — `main` returns a status rather than exiting.
- The validate-before-open ordering of T018 is the single source of four separate guarantees
  (nothing added, no store file created, the identifier sequence unadvanced, and a file problem
  never reported as status 1). Reordering it breaks FR-011 and FR-017 silently, so it is worth a
  comment in the code.
- The HTML page is asserted **byte for byte**, not parsed, because FR-014's substitution set is
  closed and the page is therefore fully determined by the collection. T024 adds a parse on top,
  to check the escaping is correct rather than merely stable.
- Commit after each task or logical group. Stop at any checkpoint to validate a story on its own.
