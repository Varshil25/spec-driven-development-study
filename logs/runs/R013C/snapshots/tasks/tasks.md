---
description: "Task list for feature 002-import-html-export"
---

# Tasks: Bookmark Import and HTML Export

**Input**: Design documents from `/specs/002-import-html-export/`

**Prerequisites**: plan.md, spec.md, research.md (D10–D19), data-model.md, contracts/import-command.md, contracts/html-export.md, quickstart.md

**Tests**: REQUIRED for this feature. Constitution Principle III and SC-013 demand that every one of
FR-024…FR-047 be covered by at least one automated test whose name or docstring names the
requirement, so test tasks are mandatory and are written before the implementation they cover
(research.md D19).

**Organization**: Tasks are grouped by user story so each story can be implemented, tested and
delivered independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 = import, US2 = HTML export, US3 = cross-store round trip
- Exact file paths appear in every task

## Path Conventions

Single project, unchanged from feature 001 (plan.md "Structure Decision"):

- Runtime code: `src/bookmarks/cli.py`, `src/bookmarks/storage.py` — **no new runtime module** (D11)
- Tests: `tests/` at repository root; four **new** modules, and `tests/conftest.py` plus the five
  pre-existing modules (`test_add.py`, `test_list_search.py`, `test_delete.py`, `test_export.py`,
  `test_cli.py`) **must not be edited** — their passing unmodified is how FR-045/SC-014 are
  demonstrated (D19)
- `pyproject.toml` is unchanged: no runtime dependency exists to add (Principle I)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the toolchain and create the new test files; no production code yet.

- [ ] T001 Verify the toolchain from the repository root: `python3 --version` reports 3.11 or newer and `pytest --version` succeeds; confirm `pyproject.toml` already carries `pythonpath = ["src"]` and leave it unmodified (plan.md Technical Context, Principle I — no runtime dependency is added)
- [ ] T002 [P] Create the four new, empty test modules `tests/test_import.py`, `tests/test_export_html.py`, `tests/test_roundtrip.py`, `tests/test_compatibility.py`, each with a module docstring naming the requirements it will cover (FR-024…FR-038; FR-039…FR-044; User Story 3 + SC-009; FR-045…FR-047), importing nothing beyond `pytest`/stdlib and reusing the existing `db_path`, `run`, `run_cli` fixtures from `tests/conftest.py` without editing it (research.md D19)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The baseline record and the shared edits to `src/bookmarks/cli.py` that both new
features build on.

**⚠️ CRITICAL**: No user story work may begin until this phase is complete — both stories edit the
same import block and the same module docstring in `src/bookmarks/cli.py`.

- [ ] T003 Run `pytest` from the repository root and record the pre-change baseline in the task notes: the five existing modules in `tests/` all pass with no skips. This is the reference for FR-045/SC-014 — if it is not green before any edit, stop and fix that first
- [ ] T004 Extend the stdlib import block at the top of `src/bookmarks/cli.py` to `argparse`, `csv`, `html`, `io`, `json`, `sqlite3`, `sys` (alphabetical, one per line, matching the existing style); `html` is used only by `escape_html` and `io` only by `parse_csv_import`, and no third-party module may appear (Principle I, plan.md "Primary Dependencies")
- [ ] T005 Update the exit-status table in the module docstring of `src/bookmarks/cli.py` so row `2` reads "``add`` rejected the URL's prefix (FR-009), or ``import`` rejected the file (FR-034…FR-036)" while rows `0`, `1` and `3` stay exactly as they are — status 1 remains usage error / unusable store and status 3 remains `delete` alone (FR-047, research.md D18)

**Checkpoint**: Baseline recorded, shared edits in place — User Story 1 and User Story 2 can now
proceed (in parallel if staffed).

---

## Phase 3: User Story 1 - Bring an existing collection in (Priority: P1) 🎯 MVP

**Goal**: `python -m bookmarks [--db PATH] import FILE --format csv|json` reads the formats
`export` writes, adds every bookmark exactly as `add` would, prints `imported N`, and is
all-or-nothing: any unreadable file, wrong shape, or single rejected URL fails with status 2 and
leaves the store — including the highest id ever used — exactly as it was.

**Independent Test**: Write a small CSV file and a small JSON file by hand, import each into a
fresh store, confirm the printed count, then `list` the store and confirm every bookmark is present
with the expected id, URL, title and alphabetised tags (quickstart.md Scenarios 1–4).

### Tests for User Story 1 ⚠️

> Write these FIRST and confirm they FAIL before implementing T012–T018. All six tasks edit
> `tests/test_import.py`, so they run sequentially, not in parallel. Each test names its
> requirement in its name or docstring (e.g. `def test_import_rejects_whole_file_for_one_bad_url(): """FR-036, FR-037"""`).

- [ ] T006 [US1] In `tests/test_import.py` add the command-surface tests for FR-024 and FR-026: `import FILE --format csv` and `--format json` are accepted through `run_cli`; a missing `FILE` and a missing `--format` each exit **1**; `--format html` and `--format xml` exit **1** (a usage error, not a rejected file — contracts/import-command.md "Invocation"); on success stdout is exactly `imported 2\n` and nothing else, stderr is empty and the status is 0
- [ ] T007 [US1] In `tests/test_import.py` add the CSV input tests for FR-027, FR-028, FR-029: the header must be exactly `id,url,title,tags` (accepted), while `url,title,tags`, `id, url, title, tags` (with spaces, compared **after** CSV parsing) and a completely empty file are rejected with status 2; a 3-field and a 5-field row are rejected naming "the row number and the count found"; the id column is ignored; tags `" python , , docs "` → `docs,python` and `"notes,notes"` → `notes` and `""` → no tags; a row whose title holds a comma, a doubled quote (`""`) and an embedded newline reads back as the original value; a blank line between rows is rejected (zero-field row) and a single trailing newline is accepted
- [ ] T008 [US1] In `tests/test_import.py` add the JSON input tests for FR-030 and FR-031: an array of objects with `url` (string), `title` (string), `tags` (array of strings) is accepted; each of a top-level object, a top-level scalar, a non-object element, a missing `url`/`title`/`tags`, a non-string `url`/`title`, a `tags` that is not an array, and a `tags` holding a number is rejected with status 2 and a diagnostic naming "the element's zero-based index and the key at fault" (contracts/import-command.md Diagnostics); an element carrying `id` plus an unknown extra key imports with the `id` ignored; `["python","docs"]` → `docs,python`, `["docs","docs"]` → `docs`, `[]` → no tags
- [ ] T009 [US1] In `tests/test_import.py` add the add-equivalence and id tests for FR-025, FR-032, FR-033: ids follow **file order**; a store already holding ids 1–2 continues at 3, 4; ids `99`/`100` in the file produce 3/4; after deleting the highest id a later import does not reuse it; an imported bookmark equals the `add`-created one field for field (URL prefix rule, title verbatim including blank, whitespace-only and non-ASCII, tag rules, duplicate URLs kept as distinct bookmarks)
- [ ] T010 [US1] In `tests/test_import.py` add the rejection tests for FR-034, FR-035, FR-036, FR-037 (SC-010, SC-011): a missing path, a directory, an unreadable file (chmod 000) and non-UTF-8 bytes (`b"\xff\xfe"`) each exit **2** with stderr naming the path and **empty stdout**; a store that did not exist is **not created** by a rejected import; a valid file whose second bookmark is `ftp://nope.com` exits 2 naming that URL with **neither** bookmark added; across every rejection case a `list` taken before and after is byte-identical and the next `add` receives the pre-import id; no traceback appears on stderr in any case
- [ ] T011 [US1] In `tests/test_import.py` add the empty-input test for FR-038: a CSV holding only the header row and the JSON text `[]` each print exactly `imported 0\n` with status 0 and leave the store empty

### Implementation for User Story 1

- [ ] T012 [US1] Add `class ImportRejected(Exception)` to `src/bookmarks/cli.py` with a docstring stating that its message is the user-facing diagnostic and that `_import` is the only place that catches it; it MUST NOT derive from `ValueError`, because `json.JSONDecodeError` is a `ValueError` subclass and catching that would swallow genuine bugs (research.md D12)
- [ ] T013 [US1] Add `read_import_text(path)` to `src/bookmarks/cli.py`: `open(path, encoding="utf-8", newline="")` and return the whole text; catch `OSError` and `UnicodeDecodeError` **narrowly at this call site** and re-raise each as `ImportRejected` whose message names the path and the problem, so a file error exits 2 and can never reach `main()`'s `OSError` handler (which means "the store could not be used", status 1). No `errors="replace"`, no encoding fallback, no `os.path.isfile` probe — `IsADirectoryError` and `PermissionError` are already `OSError` subclasses (FR-034, research.md D15)
- [ ] T014 [US1] Add `parse_csv_import(text)` to `src/bookmarks/cli.py` returning `list[tuple[str, str, str]]` of `(url, title, tags)`: read with `csv.reader(io.StringIO(text, newline=""))`; the first row MUST compare equal to `["id", "url", "title", "tags"]` (an empty file has no first row → rejected); every following row MUST have **exactly four fields** read as `(ignored id, url, title, tags)`, any other count rejected — never padded or truncated; tags go through the existing `normalise_tags`; catch `csv.Error` narrowly and re-raise as `ImportRejected`. Every rejection raises `ImportRejected` naming the required header and what was found, or the row number and the field count. Do not use `csv.DictReader` (it silently tolerates missing and extra fields) (FR-027, FR-028, FR-029, FR-035, research.md D13)
- [ ] T015 [US1] Add `parse_json_import(text)` to `src/bookmarks/cli.py` returning the same `list[tuple[str, str, str]]`: `json.loads(text)` (catch `json.JSONDecodeError` narrowly and re-raise as `ImportRejected` naming the parse problem with line and column) MUST yield a `list`; each element MUST be a `dict` with `url` (`isinstance(..., str)`), `title` (`isinstance(..., str)`) and `tags` (a `list` whose every entry is `str` — an explicit `isinstance` test, which also excludes `bool` where `str` is required); `id` and every other unrecognised key are **ignored**; tags become `normalise_tags(",".join(tags))`. Each rejection raises `ImportRejected` naming the element's **zero-based index** and the key at fault, or the top-level type found (FR-030, FR-031, FR-035, research.md D14)
- [ ] T016 [P] [US1] Add `add_bookmarks(conn, records)` to `src/bookmarks/storage.py`: one `conn.executemany("INSERT INTO bookmarks (url, title, tags) VALUES (?, ?, ?)", records)` followed by one `conn.commit()`, returning the number of rows inserted. A single transaction, not a loop over `add_bookmark` (which commits per row), so even a `sqlite3.Error` mid-insert cannot leave half an import behind and a rollback also restores `sqlite_sequence`. `SCHEMA` and the four existing functions stay byte-identical — no new column, no new table (FR-025, FR-032, FR-033, FR-037, FR-046, research.md D10, D11)
- [ ] T017 [US1] Add the `_import(args)` handler to `src/bookmarks/cli.py` in the strict order read → parse → validate URLs → open store → insert (depends on T012–T016): call `read_import_text(args.file)`, then `parse_csv_import` or `parse_json_import` on `args.format`, then `validate_url` on every record's URL returning its status (2) as soon as one fails, and only then `_with_store(args.db, lambda conn: storage.add_bookmarks(conn, records))`; print `imported {n}` and return 0. Wrap the read/parse/validate steps so that `ImportRejected` is caught **here and only here**, writing `error: {exc}` to stderr and returning 2 with nothing on stdout. No insert may be reachable while a rejection is still possible, and the store must not be opened before validation passes (FR-024…FR-026, FR-032, FR-036, FR-037, FR-038, research.md D10, D12, D18)
- [ ] T018 [US1] Add the `import` subparser in `build_parser()` in `src/bookmarks/cli.py`: `commands.add_parser("import", help="add bookmarks read from a CSV or JSON file")` with positional `FILE` (`dest="file"`, required) and `--format` `required=True, choices=["csv", "json"]` — **not** `html`, which is export-only — then `set_defaults(handler=_import)`. `choices` leaves any other format to argparse and `_Parser.error`, i.e. stderr plus status 1, so no new error path appears (FR-024, FR-047, research.md D17, D18)
- [ ] T019 [US1] Run `pytest tests/test_import.py` and then the full `pytest` from the repository root; confirm every FR-024…FR-038 test passes and the five pre-existing modules still pass unmodified

**Checkpoint**: `import` is fully functional and independently testable — MVP complete.

---

## Phase 4: User Story 2 - Publish the collection as a web page (Priority: P2)

**Goal**: `export --format html` prints the whole collection as one fixed, minimal HTML page —
DOCTYPE, a one-line `<head>` declaring UTF-8 and the title `Bookmarks`, `<body>`, `<ul>`, one
`<li><a href="URL">TITLE</a> <small>TAGS</small></li>` per bookmark in ascending id order, then the
closing tags — with `&`, `<`, `>` and `"` escaped and everything else verbatim.

**Independent Test**: With a known set of bookmarks, export as HTML and confirm the page matches the
documented skeleton line for line with exactly one list item per bookmark, in ascending id order,
each carrying that bookmark's URL as link target, its title as link text and its alphabetised tags
(quickstart.md Scenarios 5–6).

**Independence note**: this story shares no code with User Story 1 beyond the Phase 2 edits; it can
be built before, after or alongside it.

### Tests for User Story 2 ⚠️

> Write these FIRST and confirm they FAIL before implementing T024–T027. All four tasks edit
> `tests/test_export_html.py`, so they run sequentially; they are parallel with the User Story 1
> test tasks, which touch a different file.

- [ ] T020 [US2] In `tests/test_export_html.py` add the page-shape tests for FR-039 and FR-040: with bookmark 1 (`https://docs.python.org`, `Python docs`, tags `docs,python`) and bookmark 2 (`https://example.com`, `Example`, no tags), stdout equals the nine-line skeleton of contracts/html-export.md **exactly**, line for line, with a trailing newline after `</html>` — `<!DOCTYPE html>`, `<html>`, `<head><meta charset="utf-8"><title>Bookmarks</title></head>`, `<body>`, `<ul>`, the items, `</ul>`, `</body>`, `</html>`; no CSS, no timestamp, no count, no ids in the markup, no `lang` attribute, no blank lines, no indentation; status 0; and items appear in ascending id order even when titles sort differently from ids
- [ ] T021 [US2] In `tests/test_export_html.py` add the item-format and empty-store tests for FR-041 and FR-043: each bookmark is exactly one line `<li><a href="URL">TITLE</a> <small>TAGS</small></li>` with exactly one space between `</a>` and `<small>` and no other whitespace inside the line; TAGS is the stored tags string (already comma-joined and alphabetical) and no tags gives `<small></small>`; an empty title gives `<a href="…"></a>`; an empty store prints the skeleton with zero `<li>` lines and status 0
- [ ] T022 [US2] In `tests/test_export_html.py` add the escaping tests for FR-042 (SC-012): with url `https://example.com/?a=1&b=2`, title `Tom's "A&B" <notes>` and tags `a&b,c<d`, the line is exactly `<li><a href="https://example.com/?a=1&amp;b=2">Tom's &quot;A&amp;B&quot; &lt;notes&gt;</a> <small>a&amp;b,c&lt;d</small></li>` — `&`→`&amp;`, `<`→`&lt;`, `>`→`&gt;`, `"`→`&quot;` in URL, title and tags, no double-escaping of the `&` inside `&quot;`, the **apostrophe left verbatim** (not `&#x27;`) and non-ASCII text verbatim; and the whole page feeds through `html.parser.HTMLParser()` without error
- [ ] T023 [US2] In `tests/test_export_html.py` add the format-rejection test for FR-044: `export --format xml` and `export` with no `--format` each write an argparse diagnostic to stderr and exit **1** (not 2), while `--format csv` and `--format json` still exit 0

### Implementation for User Story 2

- [ ] T024 [US2] Add `escape_html(value)` to `src/bookmarks/cli.py` returning `html.escape(value, quote=False).replace('"', "&quot;")`, with a comment recording that the order is load-bearing (the `"` replacement must follow the `&` escaping so the `&` inside `&quot;` is not double-escaped) and that `quote=True` is rejected because it would rewrite `'` as `&#x27;`, breaking FR-042's "text free of those characters MUST appear verbatim" (FR-042, research.md D16)
- [ ] T025 [US2] Add `render_html(rows)` to `src/bookmarks/cli.py` returning the whole page as one `str` built from a fixed list of lines — `<!DOCTYPE html>`, `<html>`, `<head><meta charset="utf-8"><title>Bookmarks</title></head>`, `<body>`, `<ul>`, then `f'<li><a href="{escape_html(row["url"])}">{escape_html(row["title"])}</a> <small>{escape_html(row["tags"])}</small></li>'` per row in the order given, then `</ul>`, `</body>`, `</html>` — joined with `"\n"` and ending with a trailing newline. A pure function returning a string (no `print`, no template engine, no `ElementTree`), so the empty-store case falls out with zero `<li>` lines and no special branch (FR-040, FR-041, FR-043, research.md D17)
- [ ] T026 [US2] Add the `html` branch to `_export(args)` in `src/bookmarks/cli.py`: `elif args.format == "html": sys.stdout.write(render_html(rows))`, placed after the existing `csv` and `json` branches and before the unreachable-format `raise ValueError`, which stays as it is. The `csv` and `json` branches MUST NOT be touched — their bytes stay identical (FR-039, FR-045)
- [ ] T027 [US2] Change the `export` subparser's `--format` in `build_parser()` in `src/bookmarks/cli.py` to `choices=["csv", "json", "html"]` and update that subparser's `help` text to mention HTML; keep `required=True` so a missing or unknown format stays an argparse usage error reported by `_Parser.error` with status 1 (FR-039, FR-044)
- [ ] T028 [US2] Run `pytest tests/test_export_html.py` and then the full `pytest` from the repository root; confirm every FR-039…FR-044 test passes and `tests/test_export.py` still passes unmodified

**Checkpoint**: Both `import` and `export --format html` work and are independently testable.

---

## Phase 5: User Story 3 - Move a collection between stores (Priority: P3)

**Goal**: An export of store A imported into empty store B reproduces every bookmark's URL, title
and tag set exactly, in both formats.

**Independent Test**: Populate store A (a bookmark with no tags, one with several tags, one whose
title contains a comma and a double quote, one with non-ASCII text), export it in each format,
import into empty store B, and compare the two listings field by field ignoring ids
(quickstart.md Scenario 7).

**Dependency**: requires User Story 1 (`import`); it uses the pre-existing CSV and JSON exports, so
it does **not** depend on User Story 2.

- [ ] T029 [US3] In `tests/test_roundtrip.py` add the CSV round-trip test for SC-009: build store A holding a bookmark with no tags, one with several tags, one whose title contains a comma and a double quote, and one with non-ASCII text; `export --format csv` to a file in `tmp_path`; import it into empty store B; assert `imported N` reports every bookmark in A and that B's listing equals A's listing field for field with ids renumbered from 1 in ascending id order of A
- [ ] T030 [US3] In `tests/test_roundtrip.py` add the JSON round-trip test for SC-009: the same store A and the same field-for-field equality via `export --format json` into empty store C, confirming that the `id` key the JSON export writes is ignored on the way in (FR-031)
- [ ] T031 [US3] In `tests/test_roundtrip.py` add the double-import test: importing the same file into one store twice succeeds and leaves two independent copies of every bookmark with distinct ids — import never deduplicates, just as `add` does not (spec User Story 3 scenario 3)
- [ ] T032 [US3] Run `pytest tests/test_roundtrip.py` and then the full `pytest` from the repository root; confirm both round trips are lossless

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Prove nothing old changed, then validate the whole feature as a user sees it.

- [ ] T033 In `tests/test_compatibility.py` add the unchanged-behaviour tests for FR-045 (SC-014): `add`, `list`, `list --tag`, `search`, `delete` and `export --format csv` / `--format json` compared against **literal expected bytes**, with statuses 0 (`delete` of an existing id), 2 (`add ftp://nope`) and 3 (`delete` of an absent id) preserved
- [ ] T034 In `tests/test_compatibility.py` add the store-compatibility tests for FR-046: a store created by a connection that applies only feature 001's schema text is read and written by the new commands with no migration; after an `import` and an HTML export, `SELECT name, sql FROM sqlite_master` still shows exactly the one `bookmarks` table (plus SQLite's own `sqlite_sequence`) — no added table, column or marker row
- [ ] T035 In `tests/test_compatibility.py` add the exit-status table test for FR-047: usage error → 1; a store path that cannot be created (e.g. `--db` under a non-existent directory) with an otherwise valid `import` → **1**; a rejected `import` → 2; `add` with a bad URL prefix → 2; `delete` of an absent id → 3
- [ ] T036 Review the new code in `src/bookmarks/cli.py` and `src/bookmarks/storage.py` against constitution Principle II: no bare `except`, no `except Exception: pass`, every `except` clause narrow (`OSError`, `UnicodeDecodeError`, `csv.Error`, `json.JSONDecodeError`) and present only to re-raise as `ImportRejected` with added context; no coerced default anywhere (no padded CSV row, no missing-key default, no `errors="replace"`)
- [ ] T037 [P] Confirm Principle I and IV mechanically: `grep` the runtime imports in `src/bookmarks/` to verify only `argparse`, `csv`, `html`, `io`, `json`, `sqlite3`, `sys` and the local `bookmarks.storage` appear, that no runtime module imports `pytest`, and that `git diff --stat` shows no new runtime module, no new class beyond `ImportRejected`, and no change to `pyproject.toml`
- [ ] T038 [P] Confirm FR-045/SC-014 as a diff property: `git diff --name-only` lists no change to `tests/conftest.py`, `tests/test_add.py`, `tests/test_list_search.py`, `tests/test_delete.py`, `tests/test_export.py` or `tests/test_cli.py`
- [ ] T039 Verify the SC-013 coverage map: every requirement FR-024…FR-047 is named in at least one test name or docstring across `tests/test_import.py`, `tests/test_export_html.py`, `tests/test_roundtrip.py` and `tests/test_compatibility.py`, matching the Testing Strategy table in `specs/002-import-html-export/plan.md`
- [ ] T040 Run the full `pytest` from the repository root one final time: all nine modules pass, no skips (constitution Quality Gate 4)
- [ ] T041 Walk `specs/002-import-html-export/quickstart.md` Scenarios 1–8 in a terminal and tick its "Done when" boxes, confirming the exact `imported N` counts, the documented page bytes, every rejection exiting 2 with empty stdout and an unchanged store, and the five original commands byte-identical
- [ ] T042 Run quickstart.md Scenario 9 (bulk performance, SC-008/SC-015): generate 1,000 bookmarks, `time` the import and the HTML export, confirm `imported 1000`, exactly 1,000 `<li>` lines in the page, and each command well under five seconds

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Setup; **blocks both stories** (shared edits to the import block and module docstring of `src/bookmarks/cli.py`)
- **User Story 1 (Phase 3)**: depends on Phase 2 only
- **User Story 2 (Phase 4)**: depends on Phase 2 only — independent of User Story 1
- **User Story 3 (Phase 5)**: depends on Phase 2 **and User Story 1** (it imports); independent of User Story 2
- **Polish (Phase 6)**: depends on every story that is being delivered

### User Story Dependencies

- **US1 (P1)**: no dependency on another story — the MVP
- **US2 (P2)**: no dependency on another story; touches different functions in `cli.py` and a different test file
- **US3 (P3)**: needs US1; it is the pay-off of having both halves rather than new behaviour

### Within Each User Story

- Tests are written and MUST fail before the implementation they cover
- `ImportRejected` (T012) before the parsers that raise it (T013–T015)
- Parsers and `add_bookmarks` (T013–T016) before the `_import` handler (T017)
- `_import` (T017) before its subparser wiring (T018)
- `escape_html` (T024) before `render_html` (T025) before the `_export` branch (T026) before the `choices` change (T027)

### Parallel Opportunities

- T002 (new test files) is independent of T001
- T016 edits `src/bookmarks/storage.py` and is parallel with every `cli.py` task in Phase 3
- Once Phase 2 is done, US1 and US2 can run fully in parallel: their test tasks are in different files (`test_import.py` vs `test_export_html.py`) and their implementation tasks touch disjoint functions in `cli.py` (coordinate only on the final `build_parser()` edits, T018 and T027)
- T037 and T038 are read-only diff checks over different paths and can run together
- Within a single test module the tasks are sequential — they edit the same file, so none is marked [P]

---

## Parallel Example: after Phase 2

```bash
# Two developers, one per story:
Developer A: T006 → T011 (tests/test_import.py), then T012 → T019
Developer B: T020 → T023 (tests/test_export_html.py), then T024 → T028

# Within User Story 1, these two touch different files and can overlap:
Task: "Add add_bookmarks(conn, records) to src/bookmarks/storage.py"        # T016
Task: "Add parse_csv_import(text) to src/bookmarks/cli.py"                  # T014
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (T001–T002)
2. Phase 2: Foundational (T003–T005) — **blocks everything**
3. Phase 3: User Story 1 (T006–T019)
4. **STOP and VALIDATE**: quickstart.md Scenarios 1–4 — import works, every rejection exits 2 with an untouched store
5. Ship: bulk entry, the one thing the tool could not do, now works and the existing export is a real backup

### Incremental Delivery

1. Setup + Foundational → both stories unblocked
2. + User Story 1 → validate Scenarios 1–4 → MVP
3. + User Story 2 → validate Scenarios 5–6 → the collection is a browsable page
4. + User Story 3 → validate Scenario 7 → collections move between stores losslessly
5. + Polish → Scenarios 8–9 prove nothing old changed and 1,000 bookmarks stay interactive

### Parallel Team Strategy

1. Everyone on Setup + Foundational (three small tasks, one file)
2. Developer A takes User Story 1, Developer B takes User Story 2 — different test files, disjoint functions
3. Developer A continues into User Story 3 once import lands; Phase 6 is shared

---

## Notes

- [P] = different files, no dependency on an incomplete task
- Every task names its file path; story tasks carry [US1]/[US2]/[US3], Setup/Foundational/Polish tasks carry none
- Verify each test fails before writing the code it covers (constitution Principle III)
- Commit after each task or logical group
- The hard constraints to re-read before each implementation task: `tests/conftest.py` and the five pre-existing test modules are never edited (FR-045); nothing is inserted until the whole file has validated (FR-037); file read errors exit 2 while store errors exit 1 (FR-034, FR-047); exactly four characters are HTML-escaped and the apostrophe is not one of them (FR-042)
