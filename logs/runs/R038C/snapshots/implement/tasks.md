---

description: "Task list for Bookmark Import and HTML Export"
---

# Tasks: Bookmark Import and HTML Export

**Input**: Design documents from `/specs/002-import-html-export/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-contract.md,
contracts/requirements-test-matrix.md, quickstart.md

**Tests**: Test tasks ARE included and are not optional for this feature. Constitution
Principle III requires every FR and SR to map to an automated `pytest` test, SC-010 requires
100% coverage of FR-028…FR-044 and SR-012…SR-019 with no skipped test, and
[contracts/requirements-test-matrix.md](./contracts/requirements-test-matrix.md) already names
every test file and test function as a planned contract. Each test task below creates exactly
the named functions from that matrix.

**Organization**: Tasks are grouped by user story. US1 (import) and US2 (HTML export) are
independent of each other and can be built in either order; US3 is their composition.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are given in every task

## Path Conventions

Single project, layout unchanged from feature 001. Shipped code in `src/bookmarks/`, tests in
`tests/{unit,contract,integration,security}/`, run from the repository root with
`pythonpath = src` from the existing `pytest.ini`.

**No file is added to or removed from `src/`.** Only `cli.py`, `output.py` and `storage.py` are
modified (plan.md, research.md R1). **No feature-001 test file is edited** (SC-011).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the pre-change baseline that FR-028, FR-029 and SC-011 are measured
against. Nothing here modifies shipped code.

- [X] T001 Confirm the toolchain and record the pre-change baseline: `python3 --version` (3.11+ required), `python3 -m pytest --version`, then `python3 -m pytest -q` and `python3 -m pytest -q -m slow` from the repository root — both must report 0 failures and 0 errors before any edit. Record the pass/skip counts (the POSIX-only `0600` guard in `tests/security/test_security_file_mode.py` is the only permitted skip) in the task notes; do not change `pytest.ini` (`slow` marker and `pythonpath = src` already exist).
- [X] T002 [P] Capture the FR-028 golden values: with `PYTHONPATH=src`, seed a fixed collection (at least one bookmark with tags, one without a title, one whose title holds a comma, a `"`, a newline and non-ASCII text) and record the exact stdout, stderr and exit status of `add`, `list`, `list --tag T`, `search TEXT`, `delete ID`, `export --format csv` and `export --format json` as literals to be embedded in `tests/integration/test_compatibility.py` by T007.
- [X] T003 [P] Capture the SC-011 digests: compute the SHA-256 of every feature-001 test module (`tests/conftest.py`, `tests/contract/test_cli_surface.py`, `test_output_formats.py`, `test_exit_statuses.py`, all six `tests/integration/test_story*.py`/`test_persistence.py`/`test_performance.py`, all twelve `tests/security/test_security_*.py`, all three `tests/unit/test_*.py`) **before** T004 edits `tests/conftest.py`, and record them as literals for `tests/integration/test_compatibility.py`. Note that `tests/conftest.py` is intentionally excluded from the digest set because T004/T005 add fixtures to it; every other 001 module is included.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The two additive test fixtures every new test uses, and the compatibility
guardrail that makes an accidental regression in the five existing commands a test failure
rather than a silent change.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete — every US1 and US2
test task depends on the fixtures, and the guardrail must exist before shipped code is touched.

- [X] T004 Add a `write_file` fixture to `tests/conftest.py`: `write_file(name, text_or_bytes) -> str` creates a file under `tmp_path`, writing `str` content with `encoding="utf-8", newline=""` (so a `\n` inside a quoted CSV field is preserved byte-for-byte) and `bytes` content in binary mode (so invalid-UTF-8 and BOM cases are expressible), returning the path as `str`. Purely additive — do not rename, move or change `run`, `db`, `bulk_seed`, `stored_bookmarks`, `stored_tag_links` or `_query` (SC-011).
- [X] T005 Add a `database_fingerprint` fixture to `tests/conftest.py`: `database_fingerprint(path) -> tuple | None` returns `None` when the path does not exist, else `(sha256-of-bytes, st_size, st_mtime_ns)`, so SR-013/SR-015/SR-017 tests can assert "unchanged, or still absent if it did not exist". Append below the existing fixtures; do not reorder the file.
- [X] T006 Create `tests/integration/test_compatibility.py` with `test_feature_001_test_files_are_unmodified` — assert each 001 test module's SHA-256 equals the literal recorded in T003, so an accidental edit to a 001 test fails the suite rather than passing quietly (SC-011).
- [X] T007 Add `test_existing_commands_are_byte_identical` to `tests/integration/test_compatibility.py` — drive the `run` fixture over the same seeded collection as T002 and assert the stdout, stderr and status of `add`, `list`, `list --tag`, `search`, `delete`, `export --format csv` and `export --format json` equal the T002 golden literals exactly (FR-028, and US2 AS6 for the two export formats).

**Checkpoint**: `python3 -m pytest -q` still green; fixtures available; regressions in the five existing commands are now caught automatically. US1 and US2 can start, in parallel if staffed.

---

## Phase 3: User Story 1 - Bring an existing collection in from a file (Priority: P1) 🎯 MVP

**Goal**: `python -m bookmarks [--db PATH] import FILE --format csv|json` appends every record
of FILE to the collection in file order, printing `imported N`, with every record validated by
`add`'s own rules and the whole import committing as one unit or not at all.

**Independent Test**: Write a small JSON file and a small CSV file by hand, import each into an
empty database, and confirm `imported 2`, the assigned identifiers 1 and 2, and that a
following `list` shows exactly the imported bookmarks in file order. Then import a file whose
last record has an invalid URL and confirm status 2, one stderr line, empty stdout and a
collection (indeed a database file) that was never created. Fully testable without HTML export
existing.

### Tests for User Story 1

> **NOTE: Write these tests FIRST and confirm they FAIL (they will error on the missing `import` subcommand with status 2) before starting T020.**

- [X] T008 [P] [US1] Create `tests/unit/test_import_records.py` with the FR-032 CSV-shape tests: `test_csv_header_and_four_fields_required` (first row must equal `id,url,title,tags`; a reordered `url,id,title,tags`, a re-cased `ID,URL,TITLE,TAGS`, a 3-field row and a 5-field row each exit 2), `test_csv_quoting_round_trips` (a field holding a comma, a `"` and a `\n` is recovered unchanged), `test_csv_tags_field_uses_add_rules` (`"a,,b"` → tags `a`, `b`).
- [X] T009 [US1] Add the FR-033 JSON-shape tests to `tests/unit/test_import_records.py`: `test_json_array_of_objects_required` (top-level object, string, number and `null` each exit 2; an array element that is not an object exits 2), `test_json_requires_all_three_keys_with_types` (each of missing/mistyped `url`, `title`, `tags` exits 2 — including `"url": 42`, `"url": true`, `"tags": "a,b"` and `"tags": [1]` — nothing defaulted), `test_json_extra_keys_ignored` (`{"id": 7, "colour": "red", "url": …, "title": …, "tags": []}` imports with the extras discarded).
- [X] T010 [US1] Add the FR-035 record-rule tests to `tests/unit/test_import_records.py`: `test_imported_record_matches_add_exactly` (parametrised over (url, title, tags) triples, assert the `bookmarks` and `bookmark_tags` rows written by `import` equal those written by `add` with the same values, using `stored_bookmarks`/`stored_tag_links`), `test_degenerate_tag_values` (CSV `""`, `","`, `"a,,b"`, `" a , b "`, `"a,a"` and JSON `[]`, `["a","a"]`, `[" a ","b "]`, `[""]` give exactly the tag sets `parse_tags` produces), `test_invalid_url_fails_whole_import` (`ftp://example.com`, `javascript:alert(1)`, `HTTPS://example.com`, `example.com`, `""` each exit 2 with nothing stored).
- [X] T011 [P] [US1] Create `tests/contract/test_cli_surface_v2.py` with the FR-030 and FR-031 surface tests: `test_sixth_subcommand_exists` (`import f --format csv` parses with `command == "import"`), `test_import_uses_global_db_option` (`--db` before the command is honoured), `test_import_creates_missing_database` (a successful import creates the absent database file at mode `0600`, POSIX-only guard matching the existing `test_security_file_mode.py` style), `test_import_requires_file_and_format` (omitting `FILE` or `--format` exits 2), `test_import_rejects_other_formats` (`html`, `CSV`, `xml`, `""` exit 2), `test_format_is_not_inferred_from_extension` (a JSON document named `x.csv` imported with `--format json` succeeds; the same file with `--format csv` exits 2).
- [X] T012 [P] [US1] Create `tests/contract/test_import_contract.py` with `test_success_prints_only_the_count` (stdout is exactly `imported 2\n`, stderr empty, status 0), `test_empty_input_is_success` (a CSV holding only `id,url,title,tags\n` and the JSON document `[]` each print exactly `imported 0\n`, status 0, collection unchanged — US1 AS7), and `test_every_input_fault_exits_two_with_nothing_stored` parametrised over **every row** of the failure table in [contracts/cli-contract.md](./contracts/cli-contract.md#failure-contract), asserting status 2, empty stdout, exactly one stderr line, zero new bookmark rows and zero new tag links (FR-038, FR-039, SC-012, US1 AS5/AS6).
- [X] T013 [P] [US1] Create `tests/integration/test_story5_import.py` covering US1 AS1–AS7 end to end: `test_file_ids_are_ignored` (a file with ids `7,8,9` into an empty collection yields ids `1,2,3`; absent and non-numeric `id` fields import identically — FR-034, AS4), `test_ids_follow_file_order` (ascending id order reproduces file order in both formats; importing three records into a collection holding 1 and 2 assigns 3, 4, 5 in file order — FR-036, AS1/AS3), `test_existing_bookmarks_untouched` and `test_import_never_deduplicates` (prior rows, titles and tag links byte-identical; a URL already stored and a URL repeated twice in the file each produce an extra bookmark — FR-037, AS3). Assert AS1's exact `list` output `1<TAB>https://docs.python.org<TAB>Python docs<TAB>docs,python` and `2<TAB>https://example.com<TAB>Example<TAB>`.
- [X] T014 [P] [US1] Create `tests/security/test_security_import_shape.py` with `test_malformed_shapes_are_rejected_with_nothing_stored`, parametrised over the 14 SR-013 shapes: wrong CSV header, reordered header, upper-case header, a 3-field row, a 5-field row, a blank row between data rows, a top-level JSON object, a non-object array element, a missing `title`, `tags` as a string, `tags` holding a number, invalid UTF-8 bytes, a UTF-8 BOM, a zero-byte file. Each must give status 2, exactly one stderr line, an unchanged collection, and — via `database_fingerprint` — a database file whose bytes and `st_mtime_ns` are unchanged, or that is still absent if it did not exist.
- [X] T015 [P] [US1] Create `tests/security/test_security_import_limits.py` with `test_file_one_byte_over_limit_rejected` (33,554,433 bytes → status 2; mark `slow`), `test_record_count_over_limit_rejected` (50,001 records → status 2; mark `slow`), `test_each_field_limit_rejected_one_char_over` (a 8193-character URL, a 4097-character title, a 4097-character tag text, 65 distinct tags, a 129-character tag — each status 2 with nothing stored), `test_deeply_nested_json_rejected` (`"[" * 100000 + "]" * 100000` → status 2, exactly one stderr line, and no `RecursionError` or traceback escaping) (SR-014).
- [X] T016 [P] [US1] Create `tests/security/test_security_import_atomicity.py` with `test_last_record_invalid_adds_none_of_the_first_99` (100 records, record 100 has URL `ftp://bad.example` → zero new bookmark rows, zero new tag links), `test_storage_failure_mid_write_rolls_back` (monkeypatch so an insert part-way through raises `sqlite3.Error` → status 1, collection byte-identical, no orphan row in `bookmark_tags`), `test_next_add_identifier_is_unaffected` (after a failed import of 5 records, the next successful `add` receives the identifier it would have received without the import — the `sqlite_sequence` high-water mark rolls back, research.md R4) (SR-015).
- [X] T017 [P] [US1] Create `tests/security/test_security_import_no_execution.py` with `test_file_content_is_never_executed_or_fetched`: a file whose fields hold `$(touch /tmp/x)`, `` `id` ``, `; rm -rf /`, `../../etc/passwd`, `{{7*7}}` and the URL `http://127.0.0.1:1/unreachable` imports successfully with every value stored as literal text; `socket.socket`, `socket.create_connection` and `os.posix_spawn` are monkeypatched to fail the test if called; no new file appears anywhere under `tmp_path` (SR-016).
- [X] T018 [P] [US1] Create `tests/security/test_security_import_readonly.py` with `test_input_file_is_untouched` (after a **successful** and after a **failed** import, FILE's bytes, `st_size` and `st_mtime_ns` are unchanged, via `database_fingerprint` applied to FILE) and `test_no_extra_files_created` (after both outcomes the database's directory holds only the database file — no journal, no temp file, no copy — and a FILE read from a read-only directory still imports) (SR-017).
- [X] T019 [P] [US1] Create `tests/security/test_security_import_messages.py` with `test_every_failure_is_one_clean_line`, parametrised over every documented status-2 import failure plus the unusable-database and corrupt-database cases: stderr holds exactly one line of ≥ 3 words containing none of `SELECT`, `INSERT`, `DELETE`, `UPDATE`, `PRAGMA`, `FROM bookmarks`, `VALUES (` nor, case-insensitively, `traceback`, `sqlite`, `file "`, `line `, `.py`; the only absolute path permitted in the line is one the test passed in (SR-018, matching the inherited `tests/security/test_security_no_traceback.py` vocabulary).

### Implementation for User Story 1

- [X] T020 [US1] In `src/bookmarks/storage.py`, extract the row-and-tags write of `add_bookmark` into a private `_insert_bookmark(connection, url, title, tags) -> int` that executes the existing `INSERT_BOOKMARK_SQL` with `(url, title)`, takes `cursor.lastrowid`, then executes the existing `INSERT_TAG_SQL` once per tag with `(bookmark_id, tag)` — **no transaction of its own** and **no new SQL statement**. Refactor `add_bookmark` to call it inside its existing `with connection:` and keep its `sqlite3.Error` → `BookmarksError("could not store the bookmark; nothing was changed", 1)` mapping and its `int` return unchanged; `tests/security/test_security_atomicity.py` and all other 001 tests must stay green.
- [X] T021 [US1] In `src/bookmarks/storage.py`, add `add_bookmarks(connection, records) -> int` next to `add_bookmark`: one `with connection:` block looping `_insert_bookmark` over `records` (an iterable of `(url, title, tags)` in file order) and returning the count written, with `sqlite3.Error` mapped to `BookmarksError("could not store the bookmarks; nothing was changed", 1)` so every insert of one import commits together or rolls back together (SR-015, FR-036). Do not use `executemany` — `lastrowid` is undefined for it and each bookmark's tags need its identifier (research.md R4).
- [X] T022 [US1] In `src/bookmarks/cli.py`, add `import csv` and `import json` to the module's import block (both already inside the whitelist asserted by `tests/security/test_security_stdlib_only.py`; **do not** add any other import), and add the two limit constants beside the existing SR-006 constants: `MAX_IMPORT_BYTES = 32 * 1024 * 1024` (33,554,432 bytes) and `MAX_IMPORT_RECORDS = 50_000` (SR-014).
- [X] T023 [US1] In `src/bookmarks/cli.py` `build_parser()`, add the sixth subparser after `export`: `importer = commands.add_parser("import", help="add bookmarks from a file")`, `importer.add_argument("file", metavar="FILE")`, `importer.add_argument("--format", required=True, choices=("csv", "json"), dest="fmt")` — matching `export`'s existing spelling so argparse alone rejects a missing `FILE`, a missing `--format` and any other `--format` value with status 2 through the existing `_Parser.error` override (FR-030, FR-031, research.md R14). `import` is a Python keyword but an ordinary subparser name; the dispatch key is the string `"import"`.
- [X] T024 [US1] In `src/bookmarks/cli.py`, add `_validate_record(index, url, title, tag_text) -> tuple[str, str, tuple[str, ...]]` that runs **`add`'s own validators in `cmd_add`'s order**: `_check_length(title, MAX_TITLE_LENGTH, "title")`, then `parse_tags(tag_text)`, then `validate_url(url)` (which checks `MAX_URL_LENGTH` itself) — so the limits are exactly "URL 8192 characters, title 4096, tag list 4096 with at most 64 tags of at most 128 characters" with no restatement. Catch the `BookmarksError` each validator raises and re-raise it as `BookmarksError(f"record {index}: {exc.message}", 2)`, preserving `add`'s own wording (FR-035, research.md R9, R11). Reimplementing any rule is a defect.
- [X] T025 [US1] In `src/bookmarks/cli.py`, add `_read_csv_records(path) -> list[tuple[str, str, tuple[str, ...]]]`: `open(path, encoding="utf-8", newline="")` (strict UTF-8 so a BOM and any invalid byte are rejected; `newline=""` so a `\n` inside a quoted field is data, research.md R6, R7) and iterate `csv.reader(handle)`. The first row must equal `list(output.CSV_HEADER)` — reuse the constant, never a literal tuple — else `invalid CSV: the first row must be exactly 'id,url,title,tags'`; no first row at all is `invalid CSV: the header row is missing`. Every later non-empty row must hold exactly 4 fields, else `invalid CSV: row {n} has {k} fields, exactly 4 required`, with `n` 1-based counting the header as row 1. An empty row sets a `pending_blank` flag; a later non-empty row while it is set is `invalid CSV: row {n} is blank` (so a single trailing blank line is ignored but a blank line between data rows is rejected). Discard field 1 (`id`) without interpreting it (FR-034) and pass fields 2, 3, 4 to `_validate_record`. Refuse a 50,001st record **before appending it** with `too many bookmarks to import: at most 50000 allowed` (SR-014, research.md R10). All messages carry status 2.
- [X] T026 [US1] In `src/bookmarks/cli.py`, add `_read_json_records(path) -> list[tuple[str, str, tuple[str, ...]]]`: read the file's text with `encoding="utf-8"` (strict), then `json.loads`, catching `(ValueError, RecursionError)` — `JSONDecodeError` is a `ValueError`, and deep nesting raises `RecursionError` rather than crashing (research.md R8) — and raising `invalid JSON: the document could not be parsed` or `invalid JSON: the document is nested too deeply` respectively. Then allow-list validate: the document must be a `list` else `invalid JSON: the document must be an array of bookmark objects`; `len(document)` over `MAX_IMPORT_RECORDS` is `too many bookmarks to import: at most 50000 allowed`; each element must be a `dict` with `url` and `title` present and `isinstance(..., str)` else `invalid JSON: record {n} must be an object with 'url', 'title' and 'tags'`; `tags` must be present and a `list` whose every element is a `str` else `invalid JSON: record {n} must give 'tags' as an array of strings`, with `n` 1-based over array elements. Any other key, `id` included, is silently dropped (FR-033). Convert `tags` with `",".join(tags)` and hand the joined text to `_validate_record` so the SR-006 4096-character tag-list limit and FR-012's split/trim/dedupe apply to exactly the string `add --tags` would have received (research.md R9). Nothing is coerced, defaulted or skipped; `"url": true` is rejected because `bool` is not a `str`. All messages carry status 2.
- [X] T027 [US1] In `src/bookmarks/cli.py`, add `cmd_import(args) -> int` and register `"import": cmd_import` in the `COMMANDS` dict. Order is **two-phase and load-bearing** (research.md R3): first the file gate — `os.path.isfile(args.file)` false → `cannot read {args.file!r}: it is not a readable file` (covers a missing path, a directory, a dangling symlink and a FIFO), then `os.path.getsize(args.file) > MAX_IMPORT_BYTES` → `{args.file!r} is too large to import: {n} bytes, at most 33554432 allowed`; then call `_read_csv_records` or `_read_json_records` per `args.fmt`, wrapping `UnicodeDecodeError` as `cannot read {args.file!r}: it is not valid UTF-8 text` and `OSError`/`PermissionError` as `cannot read {args.file!r}: permission denied` — all status 2. Only once every record is validated, open the collection with the existing `_open_collection(args.db)` and call `storage.add_bookmarks`, then `sys.stdout.write(f"imported {count}\n")` and return 0. Nothing may be written to stdout on any failure path, and `storage.connect` must not be reached on an input fault, so a non-existent database file is not created (FR-038, FR-039, SR-013, SR-015, SR-017). Add no new `except` that swallows, defaults or truncates; `main()`'s existing `BookmarksError` handling carries every message to stderr as one line (research.md R13).
- [X] T028 [US1] Add the FR-029 migration tests to `tests/integration/test_compatibility.py`: `test_pre_feature_database_still_works` (build a database using only feature 001's `init_schema` and insert statements, then read it with all six commands — no migration step) and `test_post_feature_database_works_with_old_commands` (a database written by `import` is listed, searched, deleted from and exported correctly).
- [X] T029 [US1] Run `python3 -m pytest -q` and `python3 -m pytest -q -m slow` and confirm every US1 test from T008–T019 and T028 passes together with the whole unmodified feature-001 suite — in particular `tests/security/test_security_stdlib_only.py` (still five shipped modules, still the same import whitelist), `tests/security/test_security_no_traceback.py` and `tests/contract/test_cli_surface.py::test_no_sixth_subcommand`.

**Checkpoint**: `import` is fully functional and independently testable. Quickstart checks 2–7, 13 and 14 pass by hand. This is the MVP — the only capability a person cannot otherwise get from the tool at all.

---

## Phase 4: User Story 2 - Read the collection as a web page (Priority: P2)

**Goal**: `export --format html` prints the fixed eight-line page skeleton with exactly one
`<li><a href="URL">TITLE</a> <small>TAGS</small></li>` line per bookmark in ascending
identifier order, escaped per context, streamed, with `csv` and `json` output unchanged.

**Independent Test**: Seed bookmarks with and without titles and tags, run
`export --format html`, and confirm the output is the specified page byte-for-byte, holds one
list item per bookmark in identifier order, and that `html.parser` recovers each URL, title and
tag list unchanged. Fully testable without import existing — can be built in parallel with
Phase 3.

### Tests for User Story 2

> **NOTE: Write these tests FIRST and confirm they FAIL (argparse rejects `--format html` with status 2) before starting T035.**

- [X] T030 [P] [US2] Create `tests/unit/test_html_escaping.py` with the FR-043 tests against `output._escape_text` and `output._escape_attr`: `test_element_text_escapes_amp_lt_gt` (`&<>` → `&amp;&lt;&gt;`, and `"` is left literal in element text), `test_attribute_also_escapes_quote` (`"` → `&quot;` on top of the three), `test_ampersand_is_escaped_first` (a stored `&amp;` becomes `&amp;amp;`, and `<` never becomes `&amp;lt;` — this is the one real hazard of hand-rolled escaping, research.md R2), `test_unescapable_text_is_literal` (text containing none of those characters is returned unchanged, so US2 AS2's line holds byte-for-byte).
- [X] T031 [P] [US2] Create `tests/contract/test_html_format.py` with `test_page_skeleton_is_exact` (the first five lines are `<!DOCTYPE html>`, `<html>`, `<head><meta charset="utf-8"><title>Bookmarks</title></head>`, `<body>`, `<ul>` and the last three are `</ul>`, `</body>`, `</html>`, each `\n`-terminated, with no other line outside `<ul>`/`</ul>` — FR-041, US2 AS1), `test_one_li_line_per_bookmark_in_id_order` (count equals the bookmark count, order ascending by id), `test_li_line_is_byte_exact` (US2 AS2's `<li><a href="https://docs.python.org">Python docs</a> <small>docs,python</small></li>`, noting the single space between `</a>` and `<small>`), `test_empty_title_and_tags_still_emit_a_line` (US2 AS3's `<li><a href="URL"></a> <small></small></li>`), `test_html_tags_match_csv_tags` (each line's `<small>` text equals that bookmark's `tags` field from `export --format csv`), `test_empty_collection_prints_bare_skeleton` (FR-044, US2 AS5 — exactly the eight lines, status 0, stderr empty).
- [X] T032 [P] [US2] Create `tests/security/test_security_html_escaping.py` with `test_stored_data_cannot_become_markup` (a collection holding title `<script>alert(1)</script>`, title `" onmouseover=x`, title `a & b` and a URL containing `"` and `&` produces a page with no raw `<script>` and no unescaped `"` inside any `href`) and `test_html_parser_recovers_originals` (`html.parser.HTMLParser` recovers every original URL, title and tag string exactly, on the first attempt, over titles/URLs/tags holding `<`, `>`, `&`, `"` and non-ASCII characters) (SR-012, SC-014). Tests may import `html.parser` freely — only the shipped package is bound by the import whitelist.
- [X] T033 [P] [US2] Create `tests/integration/test_story6_html_export.py` covering US2 AS1–AS5 end to end through the `run` fixture: a seeded collection exports the specified page with status 0 and empty stderr; a bookmark with no title and no tags still gets its `<li>`; a title or URL holding `<`, `>`, `&` or `"` appears escaped and the page stays well-formed; an empty collection prints the bare skeleton.
- [X] T034 [US2] Add the FR-040 tests to `tests/contract/test_cli_surface_v2.py`: `test_export_accepts_three_formats` (`csv`, `json` and `html` all parse and exit 0) and `test_export_rejects_other_formats` (`HTML`, `xml`, `""` exit 2 with one stderr line).

### Implementation for User Story 2

- [X] T035 [US2] In `src/bookmarks/output.py`, add the two page constants beside `CSV_HEADER`: `HTML_PROLOGUE` holding the five lines `<!DOCTYPE html>`, `<html>`, `<head><meta charset="utf-8"><title>Bookmarks</title></head>`, `<body>`, `<ul>` and `HTML_EPILOGUE` holding `</ul>`, `</body>`, `</html>`, each line `\n`-terminated, so FR-041's byte-exact sequence is reviewable in one place (research.md R12).
- [X] T036 [US2] In `src/bookmarks/output.py`, add `_escape_text(value) -> str` replacing `&` → `&amp;`, then `<` → `&lt;`, then `>` → `&gt;` and `_escape_attr(value) -> str` doing the same three plus `"` → `&quot;`. **`&` must be replaced first** or `<` would become `&amp;lt;`. Use plain `str.replace` only — **do not `import html`**: `tests/security/test_security_stdlib_only.py::test_whole_package_imports_only_these_standard_modules` asserts the package's imports are a subset of a whitelist that excludes `html`, and editing that 001 test is forbidden by SC-011 (research.md R2, plan.md Complexity Tracking).
- [X] T037 [US2] In `src/bookmarks/output.py`, add `write_html(bookmarks, stream) -> None` in the same shape as `write_csv`/`write_json`: write `HTML_PROLOGUE`, then for each bookmark **as it arrives from the iterator** write `f'<li><a href="{_escape_attr(bookmark.url)}">{_escape_text(bookmark.title)}</a> <small>{_escape_text(join_tags(bookmark.tags))}</small></li>\n'`, then write `HTML_EPILOGUE`. Reuse the existing `join_tags()` so `TAGS` is identical to the CSV `tags` field by construction (FR-042). Accumulate nothing, so peak memory does not grow with the collection (SR-019).
- [X] T038 [US2] In `src/bookmarks/cli.py`, add `"html"` to `export`'s existing `choices=("csv", "json")` tuple in `build_parser()` and extend `cmd_export`'s format selection to dispatch `html` to `output.write_html`, keeping `csv` → `write_csv` and `json` → `write_json` and the existing lazy `storage.iter_bookmarks(storage.list_bookmarks(connection))` argument unchanged so csv and json output stays byte-for-byte identical (FR-028, FR-040).
- [X] T039 [US2] Run `python3 -m pytest -q` and confirm T030–T034 pass alongside the whole 001 suite, including `tests/contract/test_output_formats.py` and `tests/integration/test_story4_export.py` (csv and json unchanged) and `test_existing_commands_are_byte_identical` from T007.

**Checkpoint**: Both US1 and US2 work independently. Quickstart checks 8–10 pass by hand.

---

## Phase 5: User Story 3 - Move a collection from one database to another (Priority: P3)

**Goal**: Export and import are inverses — exporting a collection as CSV or JSON and importing
the result into an empty database reproduces every URL, title and tag set in the original
order.

**Independent Test**: Seed a database with awkward text, export to CSV and to JSON, import each
file into a fresh database, and compare the two collections' `list` output ignoring the
identifier column.

**Dependency note**: US3 is the composition of US1 and US2's import/export halves — it needs
Phase 3 complete and the pre-existing `export --format csv|json` (feature 001). It does **not**
need Phase 4.

### Tests for User Story 3

- [X] T040 [P] [US3] Create `tests/integration/test_story7_roundtrip.py` with `test_export_import_is_an_inverse` (parametrised over `csv` and `json`: seed titles holding a comma, a `"`, a `\n`, a tab and non-ASCII text plus tags needing sorting, export to a file under `tmp_path`, import into a fresh database, and compare `list` output with the identifier column dropped — US3 AS1/AS2/AS3, SC-009), `test_empty_collection_round_trips` (exporting an empty collection in either format and importing the result prints `imported 0` and leaves the target empty — US3 AS4), `test_thousand_bookmarks_in_one_command` (1,000 records, one invocation, exactly `imported 1000`, 1,000 rows stored — SC-008).
- [X] T041 [US3] Run `python3 -m pytest -q` and resolve any round-trip divergence **in favour of the contract, not the test**: a mismatch here means the CSV reader's quoting handling (T025) or the JSON `tags` joining (T026) diverges from what `export` writes, since `export`'s bytes are frozen by FR-028 and may not be changed to make a round-trip pass.

**Checkpoint**: All three user stories independently functional. Quickstart check 11 passes by hand.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: The scale and memory requirements that span both stories, and the final gates.

- [X] T042 [P] Create `tests/integration/test_performance_v2.py` with `test_html_export_of_10k_under_one_second` and `test_import_of_10k_under_ten_seconds`, both marked `@pytest.mark.slow`, using the existing `bulk_seed` fixture and the same discarding-sink style as `tests/integration/test_performance.py` (SC-013).
- [X] T043 [P] Create `tests/security/test_security_html_streaming.py` with `test_html_export_of_50k_is_memory_bounded` (`tracemalloc` peak for `export --format html` of 50,000 bookmarks within the same ceiling as 5,000, reusing the discarding-sink harness of `tests/security/test_security_streaming.py`) and `test_import_memory_does_not_grow_with_collection` (importing a 50,000-record file into a collection already holding 50,000 bookmarks peaks within the same ceiling as importing it into an empty one), both marked `@pytest.mark.slow` (SR-019).
- [X] T044 [P] Add or extend the module and function docstrings in `src/bookmarks/cli.py`, `src/bookmarks/output.py` and `src/bookmarks/storage.py` to cite the requirement each new function implements (as the existing 001 docstrings do), and update `cli.py`'s module docstring so its documented validation-order invariant explicitly covers `import`'s two-phase ordering (research.md R3). No behaviour change.
- [X] T045 Walk quickstart checks 2–14 in [quickstart.md](./quickstart.md) by hand from the repository root with `PYTHONPATH=src` and confirm each produces the documented output, including check 10's byte-exact escaped `<li>` line and check 14's "no journal or temporary file left beside the database".
- [X] T046 Run the final gates: `python3 -m pytest -q`, `python3 -m pytest -q -m slow` and `python3 -m pytest -q --strict-markers` — 0 failures, 0 errors, and no skip other than the pre-existing POSIX-only `0600` guard (SC-010). Confirm `git diff --stat` shows **no** change under `tests/` to any feature-001 module and no file added to or removed from `src/bookmarks/`.
- [X] T047 Audit [contracts/requirements-test-matrix.md](./contracts/requirements-test-matrix.md) against the delivered suite: every one of the 25 rows (FR-028…FR-044, SR-012…SR-019) names a test function that now exists and passes, 0 unmapped, 0 skips; correct the matrix if an implemented test was renamed, and tick the "Done when" list in [quickstart.md](./quickstart.md).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — must run before any shipped-code edit, because T002 and T003 capture a *pre-change* baseline.
- **Foundational (Phase 2)**: Depends on T002/T003 for its literals — BLOCKS all user stories (every new test uses `write_file` and most use `database_fingerprint`).
- **User Story 1 (Phase 3)**: Depends on Phase 2. Independent of US2.
- **User Story 2 (Phase 4)**: Depends on Phase 2. Independent of US1.
- **User Story 3 (Phase 5)**: Depends on Phase 3 (import) and on feature 001's existing `export --format csv|json`. Does **not** depend on Phase 4.
- **Polish (Phase 6)**: T042 and T043 depend on both Phase 3 and Phase 4; T045–T047 depend on everything.

### User Story Dependencies

- **US1 (P1)**: No dependency on another story. Delivered alone, it is the MVP.
- **US2 (P2)**: No dependency on another story. Could ship before US1 if priorities changed.
- **US3 (P3)**: A composition — needs US1's import. Adds no shipped code of its own (T041 only fixes divergence inside US1's readers).

### Within Each User Story

- Tests are written first and must FAIL before implementation starts (T008–T019 before T020; T030–T034 before T035).
- Storage before CLI: T020 → T021 before T027 needs `add_bookmarks`.
- Helpers before the command: T024 → T025/T026 → T027.
- Renderer before dispatch: T035 → T036 → T037 before T038.
- Single-file serialisation: all tasks touching `src/bookmarks/cli.py` (T022, T023, T024, T025, T026, T027, T038) run one at a time; likewise `src/bookmarks/output.py` (T035, T036, T037), `src/bookmarks/storage.py` (T020, T021), `tests/conftest.py` (T004, T005), `tests/integration/test_compatibility.py` (T006, T007, T028), `tests/contract/test_cli_surface_v2.py` (T011, T034) and `tests/unit/test_import_records.py` (T008, T009, T010).

### Parallel Opportunities

- T002 and T003 run in parallel (both read-only against the pre-change tree).
- US1's nine independent test files — T008, T011, T012, T013, T014, T015, T016, T017, T018, T019 — are ten tasks across ten distinct files and all run in parallel.
- US2's four independent test files — T030, T031, T032, T033 — run in parallel.
- Phase 3 and Phase 4 run in parallel in full once Phase 2 completes, because US1 touches `storage.py` plus `cli.py`'s import section and US2 touches `output.py` plus one line of `cli.py` — only T038 must be sequenced against the Phase 3 `cli.py` tasks.
- T042, T043 and T044 run in parallel.

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all ten independent US1 test files together (after T004–T007):
Task: "Create tests/unit/test_import_records.py with the FR-032 CSV-shape tests"           # T008
Task: "Create tests/contract/test_cli_surface_v2.py with the FR-030/FR-031 surface tests"  # T011
Task: "Create tests/contract/test_import_contract.py (FR-038, FR-039, SC-012)"             # T012
Task: "Create tests/integration/test_story5_import.py (US1 AS1-AS7)"                       # T013
Task: "Create tests/security/test_security_import_shape.py (SR-013)"                       # T014
Task: "Create tests/security/test_security_import_limits.py (SR-014)"                      # T015
Task: "Create tests/security/test_security_import_atomicity.py (SR-015)"                   # T016
Task: "Create tests/security/test_security_import_no_execution.py (SR-016)"                # T017
Task: "Create tests/security/test_security_import_readonly.py (SR-017)"                    # T018
Task: "Create tests/security/test_security_import_messages.py (SR-018)"                    # T019
```

## Parallel Example: User Story 2 Tests

```bash
Task: "Create tests/unit/test_html_escaping.py (FR-043)"                      # T030
Task: "Create tests/contract/test_html_format.py (FR-041, FR-042, FR-044)"    # T031
Task: "Create tests/security/test_security_html_escaping.py (SR-012, SC-014)" # T032
Task: "Create tests/integration/test_story6_html_export.py (US2 AS1-AS5)"     # T033
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (T001–T003) — capture the baseline before touching anything.
2. Phase 2: Foundational (T004–T007) — CRITICAL, blocks both stories.
3. Phase 3: User Story 1 (T008–T029) — tests first, then storage, then CLI.
4. **STOP and VALIDATE**: quickstart checks 2–7, 13, 14; full suite green including all of feature 001.
5. `import` alone is shippable: it is the only capability the tool cannot otherwise offer at all.

### Incremental Delivery

1. Setup + Foundational → the compatibility guardrail is live.
2. Add US1 → validate → ship (MVP).
3. Add US2 → validate (quickstart 8–10) → ship.
4. Add US3 → validate (quickstart 11) → ship; it is tests only, and proves the two halves agree.
5. Polish (T042–T047) → scale, memory, and the SC-010/SC-011 gates.

### Parallel Team Strategy

1. Everyone completes Phase 1 and Phase 2 together.
2. Then: Developer A takes US1 (Phase 3), Developer B takes US2 (Phase 4) — disjoint files except the single-line `cli.py` edit in T038, which B sequences after A's `cli.py` tasks.
3. US3 (Phase 5) starts as soon as Phase 3 lands.

---

## Notes

- **The three hard constraints, repeated because every implementation task is bound by them**: no sixth file under `src/bookmarks/` (five shipped modules exactly); no import in the package outside `{__future__, argparse, contextlib, csv, dataclasses, json, os, sqlite3, sys, typing}` — in particular **not `html`**; and no edit to any feature-001 test file. All three are asserted by tests that already exist (SC-011).
- Error-message wording is fixed by the failure table in [contracts/cli-contract.md](./contracts/cli-contract.md#failure-contract) and research.md R11. Positions are `row N` / `record N` — **never** `line N` — and paths render as `{path!r}`, because the inherited disclosure test forbids the substrings `line `, `file "` and `.py`.
- Nothing on any failure path may be defaulted, coerced, skipped or silently repaired (Constitution Principle II): a missing `title` is a rejection, not `""`; `"tags": "a,b"` is a rejection, not a parse; invalid UTF-8 is a rejection, not a replacement character.
- `imported 0` on an empty input file is a **success** with status 0, not an error (FR-038).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
