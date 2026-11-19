# Feature Specification: Bookmark Import and HTML Export

**Feature Branch**: `002-import-html-export`

**Created**: 2026-11-14

**Status**: Draft

**Input**: User description: "This repository already contains `bookmarks`, a command-line bookmark manager that stores bookmarks in SQLite. Read the existing code and any documentation in the repository before changing it. Add the two features below; every existing command must keep working exactly as it does now. 1. **Import.** `python -m bookmarks [--db PATH] import FILE --format csv|json` reads bookmarks from FILE in the same formats that `export` writes: CSV with the header row `id,url,title,tags`, or a JSON array of objects with the keys `url`, `title` and `tags` (a list of strings). Each bookmark in the file is added exactly as the `add` command would add it, with the same rules for URLs, titles and tags. The `id` in the file is ignored, and new ids are assigned as usual. When it finishes it prints `imported N` to standard output, where N is the number of bookmarks added. If FILE cannot be read, or is not valid CSV or JSON of that shape, it prints an error message to standard error, imports nothing, and exits with status 2. 2. **HTML export.** `export --format html` prints all bookmarks, ordered by id, as an HTML page (DOCTYPE, head with charset and title `Bookmarks`, body, `<ul>`, one `<li><a href=\"URL\">TITLE</a> <small>TAGS</small></li>` per bookmark, `</ul>`), where TAGS are the bookmark's tags joined with commas in alphabetical order."

**Extends**: [`001-bookmark-cli-manager`](../001-bookmark-cli-manager/spec.md). Requirement ids continue that
spec's sequence (FR-024…, SC-008…) so that a requirement id means one thing across the whole tool.
FR-001…FR-023 and SC-001…SC-007 of feature 001 remain in force unchanged.

## User Scenarios & Testing *(mandatory)*

The actor throughout is the same single person working in a terminal as in feature 001: someone who
keeps a durable list of web links in one SQLite file and drives it entirely from the command line.

### User Story 1 - Bring an existing collection in (Priority: P1)

The user already has bookmarks somewhere else — a CSV they exported from this tool on another
machine, a JSON file a script produced, a backup taken before they wiped a laptop. Instead of
re-typing one `add` command per link, they point the tool at the file, say which format it is in,
and get told how many bookmarks were added. Afterwards the imported bookmarks are ordinary
bookmarks: listed, searched, tagged and deleted exactly like hand-added ones.

**Why this priority**: Bulk entry is the only part of the tool a user cannot work around today
(the existing commands can read everything out, but nothing can put a collection back in). It is
also what makes the existing export trustworthy — an export you cannot restore is not a backup.

**Independent Test**: Write a small CSV file and a small JSON file by hand, import each into a
fresh store, confirm the printed count, then list the store and confirm every bookmark is present
with the expected id, URL, title and alphabetised tags.

**Acceptance Scenarios**:

1. **Given** an empty store and a JSON file containing `[{"url": "https://docs.python.org", "title": "Python docs", "tags": ["python", "docs"]}, {"url": "https://example.com", "title": "Example", "tags": []}]`, **When** the user imports it as JSON, **Then** standard output is exactly `imported 2`, the exit status is 0, and a subsequent listing prints exactly `1<TAB>https://docs.python.org<TAB>Python docs<TAB>docs,python` and `2<TAB>https://example.com<TAB>Example<TAB>`.
2. **Given** an empty store and a CSV file whose first line is `id,url,title,tags` followed by two bookmark rows, **When** the user imports it as CSV, **Then** `imported 2` is printed, the exit status is 0, and the two bookmarks are listed with ids 1 and 2 in file order.
3. **Given** a store that already holds bookmarks with ids 1 and 2, **When** the user imports a file holding two more bookmarks, **Then** the existing bookmarks are untouched and the imported ones receive the next ids (3 and 4) — the `id` column or key in the file has no effect on the ids assigned.
4. **Given** a file whose bookmarks carry untidy tag input such as ` python , , docs ` or a repeated tag, **When** the user imports it, **Then** each imported bookmark's tags are trimmed, de-duplicated and stored alphabetically, exactly as `add --tags` would have stored them.
5. **Given** any store, **When** the user imports a path that does not exist or cannot be read, **Then** an error naming the file and the problem is written to standard error, nothing is printed to standard output, nothing is added, and the exit status is 2.
6. **Given** any store, **When** the user imports a file that is not valid CSV or JSON of the documented shape (for example a JSON object instead of an array, an element missing its `url` key, a `tags` value that is not a list of strings, or a CSV file whose first line is not `id,url,title,tags`), **Then** an error naming the problem is written to standard error, nothing is added, and the exit status is 2.
7. **Given** any store, **When** the imported file contains a bookmark whose URL does not begin with `http://` or `https://`, **Then** the import is rejected as a whole: an error naming the offending URL is written to standard error, **no** bookmark from that file is added, and the exit status is 2.
8. **Given** an empty store and a file holding no bookmarks (a CSV with the header row alone, or the JSON array `[]`), **When** the user imports it, **Then** standard output is exactly `imported 0`, the exit status is 0, and the store is still empty.

---

### User Story 2 - Publish the collection as a web page (Priority: P2)

The user wants to look at their bookmarks in a browser, or hand the list to someone who does not
use the command line — put it on an internal page, mail it, keep it in a notes folder. They export
the collection as HTML and get a complete, self-contained page whose links are clickable and whose
tags are visible next to each title.

**Why this priority**: It extends an existing capability (export) rather than unlocking a blocked
workflow, so it matters less than import — but it is the only output of the tool a non-technical
reader can use directly, and it is independently valuable and testable.

**Independent Test**: With a known set of bookmarks, export as HTML and confirm the page has the
documented skeleton and exactly one list item per bookmark, in ascending id order, each carrying
that bookmark's URL as the link target, its title as the link text and its alphabetised tags.

**Acceptance Scenarios**:

1. **Given** a store holding bookmark 1 (`https://docs.python.org`, `Python docs`, tags `docs,python`) and bookmark 2 (`https://example.com`, `Example`, no tags), **When** the user exports as HTML, **Then** the exit status is 0 and standard output is an HTML page that opens with the document type declaration, carries a head declaring UTF-8 and the page title `Bookmarks`, and whose list contains the two items `<li><a href="https://docs.python.org">Python docs</a> <small>docs,python</small></li>` and `<li><a href="https://example.com">Example</a> <small></small></li>`, in that order.
2. **Given** a store whose bookmarks were added out of id order of their titles, **When** the user exports as HTML, **Then** the list items appear in ascending id order — the same order as `list`, `export --format csv` and `export --format json`.
3. **Given** an empty store, **When** the user exports as HTML, **Then** the page is still printed with its skeleton intact, containing no list items, and the exit status is 0.
4. **Given** any store, **When** the user exports with `--format csv` or `--format json`, **Then** the output is byte-for-byte what it was before this feature existed.
5. **Given** any store, **When** the user requests a format other than `csv`, `json` or `html`, **Then** an error is written to standard error and the exit status is non-zero, as before.

---

### User Story 3 - Move a collection between stores (Priority: P3)

The user has two stores — a work one and a personal one, or a laptop one and a server one — and
wants the contents of one in the other. They export from the first store and import the result
into the second, and every bookmark arrives with its URL, title and tags intact.

**Why this priority**: It is the pay-off of having both halves and the strongest single check that
the two formats really are the same formats on the way in and on the way out, but it is a
combination of stories 1 and 2 rather than new behaviour of its own.

**Independent Test**: Populate store A (including a bookmark with no tags, one with several tags, a
title containing a comma and a double quote, and non-ASCII text), export it to a file in each
format, import that file into empty store B, and compare the listings of A and B field by field,
ignoring ids.

**Acceptance Scenarios**:

1. **Given** a store A holding several bookmarks, including one with no tags, one with multiple tags, one whose title contains a comma and a double quote, and one with non-ASCII text, **When** its CSV export is imported into an empty store B, **Then** `imported N` reports every bookmark in A and B's listing matches A's listing exactly, field for field, with ids renumbered from 1 in ascending id order of A.
2. **Given** the same store A, **When** its JSON export is imported into an empty store B, **Then** the same equality holds.
3. **Given** a store that is imported into twice from the same file, **When** the second import finishes, **Then** it succeeds and the store holds two copies of every bookmark as independent entries with distinct ids — importing does not deduplicate, just as `add` does not.

---

### Edge Cases

- **File missing, a directory, or unreadable**: diagnostic on standard error naming the path, nothing imported, exit status 2 — never a traceback and never a partially filled store.
- **File is not valid UTF-8**: treated as unreadable input — diagnostic on standard error, nothing imported, exit status 2.
- **JSON of the wrong shape**: top-level value is not an array; an element is not an object; `url`, `title` or `tags` is missing; `url` or `title` is not a string; `tags` is not a list, or holds a non-string entry. Each is rejected with a diagnostic and exit status 2, importing nothing.
- **CSV of the wrong shape**: first line is not exactly `id,url,title,tags`; a row has more or fewer than four fields; the file is empty (no header at all). Each is rejected with a diagnostic and exit status 2, importing nothing.
- **Extra JSON keys**: an element carrying `id` (as `export --format json` writes) is accepted and its `id` ignored; other unrecognised keys are likewise ignored rather than rejected, so a file from a later version of the tool still imports.
- **Bad URL inside a valid file**: the whole import is rejected (exit status 2, nothing imported). A file is either imported in full or not at all — the user never has to work out how far it got.
- **Empty tags field**: an empty CSV `tags` field or an empty JSON `tags` array yields a bookmark with no tags, printed as an empty field by `list` and as `<small></small>` by the HTML export.
- **Tag order in the file**: tags are stored and shown alphabetically regardless of the order the file lists them in.
- **Blank or whitespace-only title**: stored verbatim, as `add --title` would store it; it is not turned into a missing title.
- **Store cannot be opened or created during import**: diagnostic on standard error, exit status 1 (as for every other command), nothing imported.
- **Characters with meaning in HTML** (`&`, `<`, `>`, `"`) inside a URL, title or tag: escaped in the HTML export so the page stays well-formed and a browser shows the stored text (see Assumptions); every other output format is unaffected.
- **Non-ASCII text**: preserved exactly through import and through the HTML export, whose head declares UTF-8.
- **An existing command**: unchanged in arguments, output bytes and exit status — adding these two features may not alter `add`, `list`, `search`, `delete` or the CSV and JSON exports in any observable way.

## Requirements *(mandatory)*

### Functional Requirements

Import — command surface:

- **FR-024**: The tool MUST accept `python -m bookmarks [--db PATH] import FILE --format csv|json` as a sixth command, with `FILE` a required positional path and `--format` required and limited to `csv` or `json`.
- **FR-025**: `import` MUST read the bookmarks held in `FILE` and add each of them to the store named by `--db` (or the default store), in the order the file lists them.
- **FR-026**: On success `import` MUST print exactly `imported N` followed by a newline to standard output, where N is the number of bookmarks added, and nothing else, and MUST exit with status 0.

Import — CSV input:

- **FR-027**: `import --format csv` MUST require the file's first line to be exactly the header `id,url,title,tags` — the same header `export --format csv` writes — and MUST read each following row as one bookmark whose four fields are, in order, an ignored id, the URL, the title and the tags.
- **FR-028**: The CSV `tags` field MUST be read as a comma-separated tag list, interpreted by the same rules as `add --tags` (trimmed, empty entries discarded, duplicates kept once, stored alphabetically — FR-011), so that the multi-tag field written by `export --format csv` reads back as the same tag set.
- **FR-029**: `import --format csv` MUST accept standard CSV quoting (quoted fields containing commas, doubled quotes, embedded line breaks) so that any file written by `export --format csv` is read back as the same field values.

Import — JSON input:

- **FR-030**: `import --format json` MUST require the file to hold a JSON array whose elements are objects carrying the keys `url` (string), `title` (string) and `tags` (array of strings), and MUST read each element as one bookmark.
- **FR-031**: `import --format json` MUST ignore an `id` key and any other unrecognised key on an element, so the output of `export --format json` imports unchanged.

Import — the same rules as `add`:

- **FR-032**: Every bookmark read from a file MUST be added exactly as `add` would add it: the URL prefix rule (FR-009), the title stored verbatim (FR-010, FR-023), the tag rules (FR-011), ids assigned by the store and never reused (FR-008), and duplicate URLs kept as distinct bookmarks.
- **FR-033**: Any `id` present in the file MUST be ignored; imported bookmarks MUST receive ids assigned as for `add`, continuing after the highest id ever used in that store.

Import — failure:

- **FR-034**: If `FILE` cannot be read (it does not exist, is not readable, is not a regular file, or is not valid UTF-8 text), `import` MUST write a diagnostic naming the file and the problem to standard error, add nothing, print nothing to standard output, and exit with status 2.
- **FR-035**: If `FILE` is not valid CSV or JSON of the shape required by FR-027 or FR-030, `import` MUST write a diagnostic naming the problem to standard error, add nothing, print nothing to standard output, and exit with status 2.
- **FR-036**: If any bookmark in `FILE` has a URL that `add` would reject (FR-009), `import` MUST reject the whole file: a diagnostic naming the offending URL on standard error, nothing added, and exit status 2.
- **FR-037**: A failed `import` MUST leave the store exactly as it was — all or nothing. No bookmark from a rejected file may remain, and the highest id ever used MUST be unchanged, so a later `add` is unaffected.
- **FR-038**: A file holding no bookmarks (a CSV with the header row alone, or the JSON array `[]`) MUST be a success, printing `imported 0` and exiting with status 0.

HTML export:

- **FR-039**: `export --format html` MUST be accepted alongside `csv` and `json`, and MUST print every bookmark in the store, in ascending id order, as a single HTML page on standard output, exiting with status 0.
- **FR-040**: The page MUST have exactly this shape: an opening `<!DOCTYPE html>` line, `<html>`, a `<head>` line declaring the UTF-8 character set and the page title `Bookmarks`, `<body>`, `<ul>`, then the bookmark items, then `</ul>`, `</body>` and `</html>`, one element per line as shown in the Input above.
- **FR-041**: Each bookmark MUST appear as exactly one line of the form `<li><a href="URL">TITLE</a> <small>TAGS</small></li>`, where URL is the bookmark's URL, TITLE its title, and TAGS its tags joined by commas in alphabetical order (empty when it has none).
- **FR-042**: Characters that carry meaning in HTML (`&`, `<`, `>`, `"`) occurring in a URL, title or tag MUST be escaped in the HTML export so the page is well-formed and a browser renders the stored text; text free of those characters MUST appear verbatim.
- **FR-043**: Exporting an empty store as HTML MUST succeed, printing the page skeleton with no bookmark items and exiting with status 0.
- **FR-044**: `export` MUST continue to reject a format other than `csv`, `json` or `html` with a diagnostic on standard error and a non-zero exit status (FR-021 as amended).

Compatibility:

- **FR-045**: Every existing command (`add`, `list`, `search`, `delete`, `export --format csv`, `export --format json`) MUST keep its current arguments, standard output bytes, standard error behaviour and exit statuses unchanged, and the existing test suite MUST pass unmodified.
- **FR-046**: The store file format MUST stay compatible in both directions: a store written before this feature MUST be usable by the new commands, and a store used by the new commands MUST remain usable by the previous version of the tool.
- **FR-047**: Exit status meanings MUST stay as documented in feature 001, with status 2 now additionally meaning "`import` rejected the file" — a usage error (unknown format, missing argument) MUST still exit 1, and a store that cannot be opened MUST still exit 1.

### Key Entities

- **Bookmark**, **Tag**, **Store**: unchanged from feature 001 — this feature adds no attribute and changes no rule about them.
- **Import file**: an external file holding a collection of bookmarks to be added, in either of the two formats `export` writes. It is read-only input; the tool never writes to it. It carries url, title and tags per bookmark, plus an id that is informational only and is ignored on the way in.
- **Exported page**: the HTML rendering of the whole collection — one document, one list, one list item per bookmark, ordered by id. It is output only; it is not an input format and `import --format html` does not exist.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-008**: A user can load a collection of 1,000 bookmarks from one file with a single command, and the printed count equals the number of bookmarks in the file, 100% of the time.
- **SC-009**: Export-then-import round-trips are lossless: for both CSV and JSON, every bookmark's URL, title and tag set is identical after the round trip for 100% of bookmarks, including those with commas, quotes, empty tag sets and non-ASCII text.
- **SC-010**: A rejected import never changes the collection: after any failed import, a listing is byte-identical to the listing taken before it, and the next added bookmark receives the id it would have received anyway — 100% of the failure cases in the acceptance scenarios.
- **SC-011**: Every failure of `import` is reported on standard error with a message naming the file or the offending value, with exit status 2 and empty standard output — no traceback and no silent partial import, in 100% of cases.
- **SC-012**: The HTML export opens in a browser as a page of clickable links with visible tags, with one list entry per stored bookmark and no missing or mangled text, including for titles containing `&`, `<`, `>` or `"` and for non-ASCII text.
- **SC-013**: All 24 new functional requirements (FR-024…FR-047), including every error path, are covered by at least one automated test that names the requirement it verifies.
- **SC-014**: Every pre-existing automated test passes without modification, and the observable behaviour of the five original commands is unchanged for 100% of the earlier acceptance scenarios.
- **SC-015**: Importing 1,000 bookmarks and exporting 1,000 bookmarks as HTML each complete in under five seconds on ordinary developer hardware, so bulk operations feel interactive.

## Assumptions

Chosen defaults where the request did not specify (each is a decision, not an open question):

- **Import is all-or-nothing**: the request says a rejected file "imports nothing", and the only sensible reading for a bad URL found part-way through a file is the same — the whole file is rejected with exit status 2 and the store is untouched. This also satisfies the constitution's ban on partial results presented as complete.
- **A bad URL inside the file is a status-2 failure**, the same status the request assigns to an unreadable or malformed file and the same status `add` already uses for a rejected URL, so status 2 keeps one coherent meaning: "this input was refused".
- **Shape checking is strict, not forgiving**: a JSON element missing `title` or `tags`, or a CSV row with the wrong number of fields, is a malformed file rather than an occasion for a silent default, because coerced defaults that mask bad input are forbidden by the constitution. Unrecognised *extra* keys are the one exception: they are ignored, so `export --format json` output (which carries `id`) imports as-is.
- **Files are read as UTF-8**, matching the encoding the export side writes; a file that is not valid UTF-8 is reported as unreadable rather than guessed at or read with replacement characters.
- **Import order is file order**, so ids reflect the order bookmarks appear in the file, and importing an export preserves the original relative order.
- **No deduplication on import**: a URL already in the store is added again as a separate bookmark, consistent with `add`. Merging or skipping duplicates is out of scope.
- **`imported N` is the whole of standard output** for a successful import — no per-bookmark lines, no ids printed, nothing on an empty file beyond `imported 0`.
- **The HTML page is escaped, not templated verbatim**: the five characters with HTML meaning are replaced by their character references in the URL, title and tags. For the plain text in the examples this is byte-identical to literal substitution; for a title containing `&` or `<` it is the difference between a valid page and a broken one.
- **The HTML skeleton is fixed and minimal**: exactly the lines shown in the request, no CSS, no generation timestamp, no bookmark count, no ids in the markup, and a trailing newline after `</html>`. Styling and richer markup are out of scope.
- **HTML is export-only**: `import --format html` is not offered, and `--format` for `import` accepts only `csv` and `json`.
- **No new commands or options beyond these two**: no `import --dry-run`, no `--skip-invalid`, no update-on-conflict, no HTML import, no export to a file (standard output plus shell redirection remains the way to write a file).
- **Reading the whole file into memory before the first insert is acceptable** at the scale this tool targets (thousands of bookmarks, not millions); that is what makes all-or-nothing validation straightforward.

Constraints carried over from feature 001 and the project constitution (recorded because they bound
the solution rather than describing user-visible behaviour):

- Python 3.11 or newer, standard library only at runtime (`csv`, `json`, `sqlite3`, `html` all qualify); `pytest` is the one permitted development dependency.
- The code stays in the package `bookmarks` under `src/`, runnable as `python -m bookmarks`, with SQL confined to the storage module and all input/output and exit-status choices confined to the CLI module.
- Diagnostics on standard error with meaningful non-zero exit statuses; no silent fallbacks, no swallowed exceptions, and no writes outside the store path the caller supplied — in particular, `import` never writes to the file it reads.
- Every new functional requirement is covered by a named automated test, and the full suite must pass before the change is complete.
