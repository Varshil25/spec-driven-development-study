---

description: "Task list for Command-Line Bookmark Manager"
---

# Tasks: Command-Line Bookmark Manager

**Input**: Design documents from `/specs/001-bookmark-manager-cli/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-contract.md, contracts/requirements-test-matrix.md, quickstart.md

**Tests**: Test tasks **are** included and are mandatory for this feature. Constitution
Principle III requires every functional and security requirement to map to at least one
automated `pytest` test; Principle V requires a negative test per security requirement;
SC-002 requires 100% coverage of FR-001…FR-027 and SR-001…SR-011. Test file and function
names below are taken verbatim from
[contracts/requirements-test-matrix.md](./contracts/requirements-test-matrix.md), which is the
artifact the Test gate is audited against.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested and
shipped independently, in the spec's priority order (P1 → P4).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project (per plan.md Structure Decision): package `src/bookmarks/`, tests `tests/`,
`pytest.ini` at the repository root. The template's `models/`/`services/`/`lib/` subdivision is
deliberately **not** used — four shipped files only.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton and test-runner configuration — no behaviour yet

- [X] T001 Create the single-project directory skeleton per plan.md: `src/bookmarks/` and `tests/contract/`, `tests/integration/`, `tests/security/`, `tests/unit/`
- [X] T002 Create `pytest.ini` at the repository root with `pythonpath = src`, `testpaths = tests`, and a `markers` entry registering `slow` (so `pytest -m "not slow"` from quickstart.md works without a warning)
- [X] T003 [P] Create `src/bookmarks/__init__.py` holding only a version constant (`__version__`) — package marker, no imports, no logic (plan.md Project Structure)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The storage connection, schema, error carrier, row streaming, argparse skeleton and
test harness that every user story needs

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Define `BookmarksError(Exception)` carrying a `message: str` and a `status: int` in `src/bookmarks/storage.py` — the single carrier for every non-argparse failure (exit 1 and exit 3), per research.md R5
- [X] T005 Implement `connect(path)` in `src/bookmarks/storage.py`: when the file does not exist, create it with `os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)` and close the descriptor **before** calling `sqlite3.connect(path)`; leave an existing file's mode untouched; map `FileNotFoundError` (missing parent directory), `PermissionError`, `IsADirectoryError` and `sqlite3.DatabaseError` (corrupt file) to `BookmarksError(status=1)` — never a silent fallback to `bookmarks.db` and never an empty collection (FR-002, FR-003, SR-005, research.md R2)
- [X] T006 Implement `init_schema(conn)` in `src/bookmarks/storage.py`: execute `PRAGMA foreign_keys = ON` on every connection, then in one transaction the exact DDL from data-model.md — `bookmarks(id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL, title TEXT NOT NULL DEFAULT '')`, `bookmark_tags(bookmark_id INTEGER NOT NULL REFERENCES bookmarks(id) ON DELETE CASCADE, tag TEXT NOT NULL, PRIMARY KEY (bookmark_id, tag)) WITHOUT ROWID`, `CREATE INDEX IF NOT EXISTS idx_bookmark_tags_tag ON bookmark_tags(tag)` — all `IF NOT EXISTS`, and leave journal mode at SQLite's default `delete`, never WAL (FR-003, FR-007, SR-011, research.md R1/R7)
- [X] T007 Implement the frozen dataclass `Bookmark(id: int, url: str, title: str, tags: tuple[str, ...])` and the grouping generator `iter_bookmarks(cursor)` in `src/bookmarks/storage.py`: iterate the cursor lazily and yield one `Bookmark` as soon as the `id` column changes, holding at most one bookmark's tags in memory; a row with `tag IS NULL` yields an empty tag set (FR-017, SR-007, research.md R4)
- [X] T008 Create `src/bookmarks/cli.py` with the SR-006 limit constants quoted verbatim from the spec — URL **at most 8192 characters**, title **at most 4096 characters**, `--tags` string **at most 4096 characters** with **at most 64 tags** of **at most 128 characters each**, search text **at most 1024 characters** — plus the argparse `type=` validator `positive_id` accepting only a decimal positive integer in **1 … 2^63−1** (rejecting `abc`, `1.5`, `-1`, `0` with `argparse.ArgumentTypeError`), and a one-time `sys.stdout.reconfigure(encoding="utf-8", newline="\n")` at entry (FR-022, SR-003, SR-006, research.md R5/R6)
- [X] T009 Build the argparse parser in `src/bookmarks/cli.py` per contracts/cli-contract.md: global `--db PATH` defaulting to `bookmarks.db` in the current working directory and required to precede the command, and five subparsers `add URL [--title TITLE] [--tags TAGS]`, `list [--tag TAG]`, `search TEXT`, `delete ID`, `export --format {csv,json}` with `required=True, choices=("csv", "json")`; rely on argparse's native usage-message-to-stderr and `SystemExit(2)` for unknown commands, unknown options and missing arguments (FR-001, FR-026, SR-003, research.md R5)
- [X] T010 Implement `main(argv)` in `src/bookmarks/cli.py`: parse, dispatch through a plain dict of five command functions, and **return** an int status 0/1/2/3 without ever calling `sys.exit`; catch `BookmarksError` and `SystemExit` from argparse, writing one single-line message to stderr with no traceback, no `sqlite3` text and no SQL keywords, and keeping stdout free of it (FR-004, FR-005, SR-008)
- [X] T011 [P] Create `src/bookmarks/__main__.py` whose only behaviour is `sys.exit(cli.main(sys.argv[1:]))` under an `if __name__ == "__main__"` guard, so `python -m bookmarks` works with `src/` on `PYTHONPATH` (FR-001)
- [X] T012 [P] Create `src/bookmarks/output.py` with `join_tags(tags)` — ascending code-point sort of the tag text then comma-join, returning `""` for an empty set (so `{python, Docs}` renders `Docs,python`) — shared by the listing, CSV and JSON formats (FR-017, FR-023, FR-024)
- [X] T013 Create `tests/conftest.py` with the in-process `run(*argv)` fixture that calls `bookmarks.cli.main(list(argv))` and returns `(status, stdout, stderr)` via `capsys`, and a `db` fixture giving a `tmp_path`-based database path; no `subprocess` anywhere in the suite (research.md R10)
- [X] T014 [P] Write `tests/contract/test_cli_surface.py::test_five_subcommands_exist` and `::test_module_is_runnable` — each of `add`/`list`/`search`/`delete`/`export` parses, and a `runpy`-based check that `bookmarks.__main__` imports and exposes the entry call (FR-001)
- [X] T015 [P] Write `tests/security/test_security_file_mode.py::test_file_mode_is_0600` — after first use `path.stat().st_mode & 0o777 == 0o600`, asserted immediately after creation (not re-chmodded), under a POSIX-only skip guard (SR-005)
- [X] T016 [P] Write `tests/security/test_security_stdlib_only.py::test_no_network_or_subprocess_imports` and `::test_no_shell_subprocess_socket_or_env_config` — `ast.parse` every `.py` under `src/bookmarks/`, assert every imported top-level module name is in `sys.stdlib_module_names`, and assert `subprocess`, `socket`, `urllib.request`, `os.system`, `os.popen` and `os.environ` appear nowhere in shipped code (FR-011, SR-010, SC-007)

**Checkpoint**: Database opens at mode `0600`, schema applies, `python -m bookmarks --help` lists five commands, the test harness runs. User story implementation can begin.

---

## Phase 3: User Story 1 - Save a bookmark and see it again later (Priority: P1) 🎯 MVP

**Goal**: `add URL [--title TITLE] [--tags TAGS]` stores a bookmark and prints its identifier; `list` prints every bookmark in ascending id order as four tab-separated fields; data survives process exit; an invalid URL is rejected with exit 2 and stores nothing.

**Independent Test**: Add two bookmarks, let the process exit, run `list` in a new invocation and confirm both appear with their ids, URLs, titles and tags — then `add ftp://example.com` and confirm exit 2 with the collection unchanged. Passes with no `search`, `delete` or `export` implemented.

### Tests for User Story 1 ⚠️

> Write these first and confirm they FAIL before implementing T023–T028.

- [X] T017 [P] [US1] Write `tests/unit/test_url_validation.py::test_only_lowercase_http_https_prefix_accepted` — parametrised accept/reject list; a rejected `add` creates no bookmark row and no tag row (FR-008)
- [X] T018 [P] [US1] Write `tests/unit/test_tag_parsing.py::test_comma_list_parsed_and_absent_means_no_tags` and `::test_degenerate_tag_inputs` — `python,cli` → 2 tags, omitted → 0 tags, and the data-model.md cases `""` → `{}`, `","` → `{}`, `"a,,b"` → `{a,b}`, `" a , b "` → `{a,b}`, `"a,a"` → `{a}`, `"Python,python"` → `{Python, python}` (FR-010, FR-012)
- [X] T019 [P] [US1] Write `tests/unit/test_formatting.py::test_absent_title_defaults_to_empty_string` plus tag-sort-order and empty-field rendering cases — stored title is `""` and renders as an empty field; `{python, Docs}` renders `Docs,python` (FR-009, FR-017)
- [X] T020 [P] [US1] Write `tests/contract/test_output_formats.py::test_listing_is_four_tab_separated_fields`, `::test_tags_sorted_by_code_point` and `::test_listing_splits_into_four_fields` — `line.split("\t")` has length exactly 4, a titleless and tagless bookmark's line ends in two consecutive tabs, no header and no trailing blank line (FR-017, SC-006)
- [X] T021 [P] [US1] Write `tests/integration/test_story1_add_and_list.py` covering US1 AS1–AS5: `test_add_prints_only_the_identifier` (stdout exactly `"1\n"`, stderr empty), `test_db_option_is_used`, `test_default_db_is_cwd_bookmarks_db` (via `monkeypatch.chdir(tmp_path)`), `test_list_prints_all_in_id_order`, `test_first_add_needs_no_setup` (FR-002, FR-006, FR-013, SC-001)
- [X] T022 [P] [US1] Write `tests/security/test_security_urls.py::test_url_allowlist_rejects` — parametrised over `javascript:alert(1)`, `file:///etc/passwd`, `data:text/html,x`, `ftp://host/`, `HTTPS://host/`, `example.com`, `//example.com`, `http:/example.com`, `""`, `"   "` → status 2, nothing on stdout, collection unchanged (SR-002, US1 AS5)

### Implementation for User Story 1

- [X] T023 [US1] Implement `validate_url(value)` in `src/bookmarks/cli.py` — allow-list: accept only a value beginning with the exact lowercase prefix `http://` or `https://` and **at most 8192 characters**; no reachability check, no DNS lookup, no network access; rejection returns status 2 **before** the database is opened (FR-008, FR-011, SR-002, SR-006)
- [X] T024 [US1] Implement `parse_tags(raw)` in `src/bookmarks/cli.py` — split on `,`, strip leading/trailing whitespace from each entry, discard entries that are then empty, keep each distinct entry once; enforce raw string **at most 4096 characters**, **at most 64 tags**, each tag **at most 128 characters** (over-limit → status 2, nothing stored) (FR-010, FR-012, SR-006)
- [X] T025 [US1] Implement `add_bookmark(conn, url, title, tags)` in `src/bookmarks/storage.py` — one `with conn:` transaction containing `INSERT INTO bookmarks(url, title) VALUES (?, ?)` followed by one `INSERT INTO bookmark_tags(bookmark_id, tag) VALUES (?, ?)` per tag, returning `cursor.lastrowid`; fixed statement strings with `?` placeholders only (FR-006, FR-007, SR-001, SR-009)
- [X] T026 [US1] Implement the unfiltered read `list_bookmarks(conn)` in `src/bookmarks/storage.py` — the single statement `SELECT b.id, b.url, b.title, t.tag FROM bookmarks b LEFT JOIN bookmark_tags t ON t.bookmark_id = b.id ORDER BY b.id, t.tag`, returning the cursor for lazy iteration through `iter_bookmarks` (FR-013, FR-017, SR-007)
- [X] T027 [US1] Implement `format_listing_line(bookmark)` in `src/bookmarks/output.py` — exactly `{id}\t{url}\t{title}\t{tags}` plus `\n`, using `join_tags`, with the title reproduced verbatim including tabs and newlines and `""` for an absent title (FR-009, FR-017)
- [X] T028 [US1] Wire the `add` and `list` command functions in `src/bookmarks/cli.py` in the fixed validation order argparse → SR-006 size limits → URL shape → database access; `add` prints only the identifier and nothing else to stdout, `list` streams one formatted line per bookmark to stdout and exits 0 even when the collection is empty (FR-006, FR-013, FR-018, contracts/cli-contract.md validation order)

**Checkpoint**: User Story 1 is fully functional and independently testable — a usable bookmark manager.

---

## Phase 4: User Story 2 - Find a bookmark among many (Priority: P2)

**Goal**: `search TEXT` matches a case-insensitive literal substring of title or URL; `list --tag TAG` filters on an exact case-sensitive tag; a no-match result is a success with no output.

**Independent Test**: Seed bookmarks with distinct mixed-case titles, URLs and tags, then run `search PYTHON`, `list --tag python` and `search '%'` and confirm only the matching entries print, in id order, with `%` matched literally; `search zzzznothing` prints nothing on either stream and exits 0.

### Tests for User Story 2 ⚠️

- [X] T029 [P] [US2] Write `tests/integration/test_story2_search_and_tag_filter.py::test_search_is_case_insensitive_substring` and `::test_tag_filter_is_exact_and_case_sensitive` — `PYTHON` matches mixed-case titles and URLs (US2 AS1); `--tag python` excludes a bookmark tagged `Python`, and a matched bookmark still displays **all** of its tags (US2 AS2) (FR-014, FR-015)
- [X] T030 [P] [US2] Write `tests/security/test_security_search_literal.py::test_percent_and_underscore_are_literal` and `::test_search_for_percent_does_not_match_row_without_percent` — searching `%` returns only the row whose title literally contains `%`, and no rows when none does (FR-016, SR-004, US2 AS4)
- [X] T031 [P] [US2] Write `tests/contract/test_exit_statuses.py::test_no_match_prints_nothing_and_exits_zero` — a `list`, `list --tag` and `search` that match nothing leave stdout and stderr both empty with status 0 (FR-018, US2 AS3)

### Implementation for User Story 2

- [X] T032 [US2] Add the tag-filter variant to the read in `src/bookmarks/storage.py` — the T026 statement plus `WHERE b.id IN (SELECT bookmark_id FROM bookmark_tags WHERE tag = ?)`, so the subquery selects the bookmarks while the `LEFT JOIN` still returns every tag of each matched bookmark for display (FR-014, FR-017)
- [X] T033 [US2] Implement `search_bookmarks(conn, text)` in `src/bookmarks/storage.py` — the T026 statement plus `WHERE instr(lower(b.title), lower(:text)) > 0 OR instr(lower(b.url), lower(:text)) > 0` with `:text` bound as a parameter; never `LIKE`, so `%` and `_` are structurally literal (FR-015, FR-016, SR-004, research.md R3)
- [X] T034 [US2] Wire `list --tag TAG` and the `search TEXT` command in `src/bookmarks/cli.py`, enforcing search text **at most 1024 characters** before the database is opened and streaming results through `format_listing_line` in ascending id order (FR-014, FR-015, FR-018, SR-006)

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Remove a bookmark that is no longer wanted (Priority: P3)

**Goal**: `delete ID` removes the bookmark and its tag associations and exits 0; every other bookmark and identifier is untouched; a well-formed but absent id exits 3 and a malformed id exits 2; a deleted identifier is never reissued.

**Independent Test**: Add three bookmarks, delete the middle one, list the rest and confirm ids 1 and 3 keep their original URLs, titles and tags; delete the same id again and confirm exit 3; delete the highest id, add again and confirm the new id is 4; `delete abc` and `delete 0` both exit 2.

### Tests for User Story 3 ⚠️

- [X] T035 [P] [US3] Write `tests/integration/test_story3_delete.py::test_delete_removes_bookmark_and_its_tags`, `::test_delete_leaves_others_unchanged`, `::test_delete_missing_id_exits_three` and `::test_ids_increase_and_are_never_reused` — covering US3 AS1–AS4: no `bookmark_tags` row survives for the deleted id, survivors are byte-identical, a repeat delete gives status 3 with a stderr message and an unchanged collection, and ids 1,2,3 → delete 3 → next add is 4 (FR-007, FR-019, FR-020, FR-021)
- [X] T036 [P] [US3] Write `tests/security/test_security_args.py::test_malformed_delete_id_exits_two` and `::test_every_malformed_argument_exits_two_without_writing` (delete/unknown-command/unknown-option cases) — `abc`, `1.5`, `-1`, `0` and an absent argument give status 2, and the database file is untouched (same mtime and size, or still absent) (FR-022, SR-003)

### Implementation for User Story 3

- [X] T037 [US3] Implement `delete_bookmark(conn, bookmark_id)` in `src/bookmarks/storage.py` — one `with conn:` transaction executing `DELETE FROM bookmarks WHERE id = ?`, relying on the already-enabled `PRAGMA foreign_keys = ON` and `ON DELETE CASCADE` to remove the tag associations in the same statement; read `cursor.rowcount` inside the transaction and raise `BookmarksError(status=3)` when it is 0 so nothing commits; no prior `SELECT` existence check (FR-019, FR-020, FR-021, SR-009, research.md R7)
- [X] T038 [US3] Wire the `delete` command in `src/bookmarks/cli.py` using the `positive_id` argparse `type=` validator from T008 for the status-2 path and mapping the storage not-found error to status 3, keeping stdout empty on success and the stderr message to one line (FR-005, FR-019, FR-021, FR-022)

**Checkpoint**: User Stories 1, 2 and 3 all work independently.

---

## Phase 6: User Story 4 - Hand the collection to another tool (Priority: P4)

**Goal**: `export --format csv` prints the header `id,url,title,tags` then one row per bookmark; `export --format json` prints a JSON array of objects; both round-trip awkward characters through standard parsers; an empty collection gives the header alone or `[]`; a missing or unsupported `--format` exits 2.

**Independent Test**: Seed bookmarks with and without titles and tags, including one title containing a comma, a double quote, a newline and a non-ASCII character; export as CSV and as JSON and confirm both parse with `csv.reader` / `json.loads` on the first attempt and recover every field unchanged; then `export --format xml` and bare `export` both exit 2.

### Tests for User Story 4 ⚠️

- [X] T039 [P] [US4] Write `tests/integration/test_story4_export.py::test_csv_header_and_rows`, `::test_json_array_shape`, `::test_special_characters_round_trip` and `::test_empty_collection_exports` — covering US4 AS1–AS4: first CSV line exactly `id,url,title,tags` with rows in id order and tags comma-joined and sorted inside the single `tags` field; `json.loads` gives a list of dicts with `id` an `int` and `tags` a sorted `list[str]`; a title with `,`, `"`, `\n` and non-ASCII recovered unchanged; empty collection gives header-only CSV and `[]` with status 0 (FR-023, FR-024, FR-025, FR-027)
- [X] T040 [P] [US4] Write `tests/contract/test_output_formats.py::test_export_parses_with_stdlib_parsers` — the CSV output parses with `csv.reader` and the JSON output with `json.loads` on the first attempt, with `\n` line terminators (SC-006)
- [X] T041 [US4] Add `tests/security/test_security_args.py::test_export_format_required_and_restricted` to the file created in T036 — a missing `--format` exits 2, and `xml`, `CSV` and `""` each exit 2 with no database write (FR-026, SR-003)
- [X] T042 [P] [US4] Write `tests/security/test_security_streaming.py::test_export_of_50k_bookmarks_is_memory_bounded`, marked `slow` — seed at least 50,000 bookmarks, export under `tracemalloc`, assert peak stays below a fixed ceiling independent of collection size and compare the peak at 5k versus 50k to show no proportional growth (SR-007)

### Implementation for User Story 4

- [X] T043 [US4] Implement `write_csv(bookmarks, stream)` in `src/bookmarks/output.py` — `csv.writer(stream, lineterminator="\n")`, write the header row `id,url,title,tags` then one `writerow` per bookmark **as it arrives from the generator**, with the `tags` field from `join_tags`; RFC 4180 quoting is left entirely to the writer and fields are **not** spreadsheet-hardened (a leading `=`/`+`/`-`/`@` is emitted as-is — documented deviation in plan.md Complexity Tracking) (FR-023, FR-025, FR-027, SR-007, research.md R6)
- [X] T044 [US4] Implement `write_json(bookmarks, stream)` in `src/bookmarks/output.py` — emit `[`, then one `json.dumps({"id": ..., "url": ..., "title": ..., "tags": [...]}, ensure_ascii=False)` per bookmark separated by `,`, then `]`; `id` a JSON number, `title` a string (`""` when absent), `tags` an array of strings in ascending code-point order (`[]` when none); never `json.dumps` over a materialised list (FR-024, FR-025, FR-027, SR-007, research.md R6)
- [X] T045 [US4] Wire the `export` command in `src/bookmarks/cli.py` — reuse the unfiltered read from T026 and dispatch on the already-validated `--format` to `write_csv` or `write_json`, streaming from the one cursor to stdout and exiting 0 (FR-023, FR-024, FR-027)

**Checkpoint**: All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The requirements that span every command — the full exit-status mapping, the
remaining security requirements, persistence and performance, and the gate audits

- [X] T046 [P] Write `tests/contract/test_exit_statuses.py::test_every_successful_command_exits_zero` and `::test_error_status_and_stream_mapping` in the file started at T031 — all five commands return 0 on valid input; a parametrisation over every documented failure asserts the message is on stderr, stdout is clean of it, and the status matches the contracts/cli-contract.md table (1 / 2 / 3), including `delete abc` → 2 versus `delete 999` → 3 (FR-004, FR-005, SC-005)
- [X] T047 [P] Write `tests/security/test_security_injection.py::test_sql_metacharacters_are_literal_text` — add `'); DROP TABLE bookmarks;--` as URL suffix, as title and as a tag, then search for it; the text is stored and returned verbatim, the `bookmarks` table still exists, and all other rows are intact (SR-001)
- [X] T048 [P] Write `tests/security/test_security_limits.py::test_one_char_over_each_limit_is_rejected` — URL at 8193, title at 4097, `--tags` string at 4097 characters, 65 tags, a 129-character tag and search text at 1025 each give status 2 with nothing stored, while the boundary-exact values 8192 / 4096 / 64 / 128 / 1024 are accepted (SR-006)
- [X] T049 [P] Write `tests/security/test_security_no_traceback.py::test_expected_failures_are_single_line_and_disclose_nothing` — for each of invalid URL, missing identifier, bad argument and unusable database, stderr is exactly one line containing no `Traceback`, no `sqlite3` and no `SELECT`/`INSERT`/`DELETE` (SR-008)
- [X] T050 [P] Write `tests/security/test_security_atomicity.py::test_failed_add_leaves_no_partial_row_or_orphan_tag` — an `add` that fails validation, and an `add` whose tag insert is monkeypatched to raise mid-transaction, both leave zero `bookmarks` rows and zero `bookmark_tags` rows; a `delete` of a missing id commits nothing (SR-009)
- [X] T051 [P] Write `tests/security/test_security_no_residual_files.py::test_no_temp_or_journal_files_remain` — after each of the five commands, and after a failing one, the database directory contains exactly the database file: no `-journal`, `-wal`, `-shm` or temporary file (SR-011)
- [X] T052 [P] Write `tests/security/test_security_db_path.py` — a `--db` whose parent directory does not exist, a `--db` pointing at a directory, and a `--db` naming a file that is not a valid SQLite database each exit 1 with a one-line stderr message, create no directory tree, and never fall back to `bookmarks.db` (FR-002, spec Edge Cases, plan.md path-containment deviation)
- [X] T053 [P] Write `tests/integration/test_persistence.py::test_missing_file_is_created_with_schema`, `::test_existing_file_is_reused` and `::test_thousand_mixed_commands_leave_expected_collection` — first use creates the file and schema, a second invocation sees the prior rows, and 1,000 scripted add/delete operations match a Python-side model exactly with zero lost or altered entries (FR-003, SC-003)
- [X] T054 [P] Write `tests/integration/test_performance.py::test_each_command_under_one_second_at_10k`, marked `slow` — seed 10,000 bookmarks and bound each of the five commands with `perf_counter` under one second (SC-004)
- [X] T055 Run `pytest` from the repository root and confirm zero failures and zero skips other than the POSIX-only file-mode guard (Constitution Test gate, SC-002)
- [X] T056 Audit every row of `specs/001-bookmark-manager-cli/contracts/requirements-test-matrix.md` against the implemented suite — 27 FR + 11 SR = 38 requirements mapped to a passing test, each SR with its negative case; record any gap as a new task rather than a note (Principle III, Principle V, SC-002)
- [X] T057 Run the quickstart.md scenarios 1–4 and the error-path spot checks by hand from a clean directory with `PYTHONPATH=src`, including `stat -c '%a' bookmarks.db` → `600`, and tick off quickstart.md's Definition of done
- [X] T058 [P] Review the four shipped files (`src/bookmarks/__init__.py`, `__main__.py`, `cli.py`, `storage.py`, `output.py`) against Constitution principles I–V — no third-party runtime import, no swallowed exception or silent fallback, no untested requirement, no layer or abstraction beyond the plan's design, every baseline control met — and confirm plan.md's Complexity Tracking still lists exactly the one documented CSV deviation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Setup — **blocks every user story**
- **User Story phases (3–6)**: all depend on Phase 2 only; they may then run in parallel or sequentially in priority order P1 → P2 → P3 → P4
- **Polish (Phase 7)**: T046–T052 and T058 depend on all four stories being complete (they parametrise over every command); T053 depends on US1 + US3; T054 depends on all five commands existing; T055–T057 are the final gates

### User Story Dependencies

- **US1 (P1)**: independent. Needs only Phase 2.
- **US2 (P2)**: independent of US3/US4. Shares the read statement from T026, so it is cheapest right after US1, but its tests seed their own data and pass without `delete` or `export`.
- **US3 (P3)**: independent of US2/US4. Needs only Phase 2 plus `add`/`list` from US1 to be observable.
- **US4 (P4)**: independent of US2/US3. Shares the read from T026 and `join_tags` from T012.

### Within Each User Story

- Tests are written first and MUST fail before the implementation tasks in the same phase
- Storage statements before command wiring; output formatters before the command that uses them
- The last task of each story phase is the `cli.py` wiring, which is where the story becomes observable

### File-Serialisation Notes (why some tasks lack [P])

- `src/bookmarks/cli.py` is touched by T008, T009, T010, T023, T024, T028, T034, T038, T045 — all sequential
- `src/bookmarks/storage.py` is touched by T004, T005, T006, T007, T025, T026, T032, T033, T037 — all sequential
- `src/bookmarks/output.py` is touched by T012, T027, T043, T044 — all sequential
- `tests/contract/test_output_formats.py` (T020, T040), `tests/contract/test_exit_statuses.py` (T031, T046) and `tests/security/test_security_args.py` (T036, T041) are each written across two phases — the later task appends, so it is not marked [P] against the earlier one

### Parallel Opportunities

- T003 within Setup
- T011, T012, T014, T015, T016 within Foundational (after T004–T010)
- All six US1 test tasks T017–T022 together
- All three US2 test tasks T029–T031 together
- Both US3 test tasks T035–T036 together
- T039, T040, T042 together in US4
- T046–T054 and T058 together in Polish (nine independent test files)
- With multiple developers, US1–US4 can proceed concurrently once Phase 2 is done

---

## Parallel Example: User Story 1

```bash
# All six User Story 1 test tasks write different files — launch together:
Task: "Write tests/unit/test_url_validation.py::test_only_lowercase_http_https_prefix_accepted"
Task: "Write tests/unit/test_tag_parsing.py degenerate-input cases"
Task: "Write tests/unit/test_formatting.py title/tag rendering cases"
Task: "Write tests/contract/test_output_formats.py listing-format cases"
Task: "Write tests/integration/test_story1_add_and_list.py AS1-AS5"
Task: "Write tests/security/test_security_urls.py::test_url_allowlist_rejects"

# Implementation then runs sequentially: cli.py (T023, T024), storage.py (T025, T026),
# output.py (T027), cli.py wiring (T028) — three files, each touched by one task at a time.
```

## Parallel Example: Polish

```bash
# Nine independent test files — launch together:
Task: "tests/contract/test_exit_statuses.py full status mapping"
Task: "tests/security/test_security_injection.py"
Task: "tests/security/test_security_limits.py"
Task: "tests/security/test_security_no_traceback.py"
Task: "tests/security/test_security_atomicity.py"
Task: "tests/security/test_security_no_residual_files.py"
Task: "tests/security/test_security_db_path.py"
Task: "tests/integration/test_persistence.py"
Task: "tests/integration/test_performance.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup (T001–T003)
2. Phase 2 Foundational (T004–T016) — **blocks everything**
3. Phase 3 User Story 1 (T017–T028)
4. **STOP and VALIDATE**: run quickstart.md Scenario 1 by hand and `pytest tests/unit tests/integration/test_story1_add_and_list.py tests/security/test_security_urls.py`
5. At this point `add` + `list` is a shippable bookmark manager

### Incremental Delivery

1. Setup + Foundational → database opens at `0600`, schema applies, five commands parse
2. + US1 → save and recall (**MVP**)
3. + US2 → search and tag filtering
4. + US3 → deletion with non-reused identifiers
5. + US4 → CSV and JSON export
6. + Polish → full FR/SR matrix green, persistence and performance criteria met

Each increment adds value without breaking the previous one, and each story's test module
passes with only that story's commands implemented (requirements-test-matrix.md, final note).

### Parallel Team Strategy

1. The team completes Phase 1 + Phase 2 together — nothing else can start
2. Then: Developer A → US1, Developer B → US2, Developer C → US3, Developer D → US4
3. Serialise the `cli.py` wiring tasks (T028, T034, T038, T045) between developers, or let the
   US1 developer land T028 first since the others' tests observe behaviour through `list`
4. Polish is split across the team by test file, then T055–T057 run once at the end

---

## Notes

- Tests are **not** optional here: the Constitution's Test gate treats a skipped or disabled test as a failing requirement, and SC-002 demands 100% FR/SR coverage
- Every SQL statement is a fixed string with `?`/`:name` placeholders — no statement is ever assembled from user text (SR-001)
- Validation order is fixed and asserted: argparse → SR-006 size limits → URL shape → database access, so every exit-2 case happens before the database is opened
- Exit statuses are exactly 0 (success), 1 (unusable database or other failure), 2 (invalid argument or input), 3 (`delete` of an absent identifier) — nothing else
- `main(argv)` returns a status and never calls `sys.exit`; only `__main__.py` exits
- [P] means different files with no dependency on an incomplete task; see File-Serialisation Notes for the three source files that are deliberately sequential
- Commit after each task or logical group; stop at any checkpoint to validate a story independently
