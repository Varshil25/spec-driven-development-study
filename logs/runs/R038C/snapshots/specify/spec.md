# Feature Specification: Bookmark Import and HTML Export

**Feature Branch**: `002-import-html-export`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "This repository already contains `bookmarks`, a command-line bookmark manager that stores bookmarks in SQLite. Read the existing code and any documentation in the repository before changing it. Add the two features below; every existing command must keep working exactly as it does now. (1) Import: `python -m bookmarks [--db PATH] import FILE --format csv|json` reads bookmarks from FILE in the same formats that `export` writes — CSV with the header row `id,url,title,tags`, or a JSON array of objects with the keys `url`, `title` and `tags` (a list of strings). Each bookmark in the file is added exactly as the `add` command would add it, with the same rules for URLs, titles and tags. The `id` in the file is ignored, and new ids are assigned as usual. When it finishes it prints `imported N` to standard output, where N is the number of bookmarks added. If FILE cannot be read, or is not valid CSV or JSON of that shape, it prints an error message to standard error, imports nothing, and exits with status 2. (2) HTML export: `export --format html` prints all bookmarks, ordered by id, as an HTML page with a fixed skeleton and one `<li><a href=\"URL\">TITLE</a> <small>TAGS</small></li>` line per bookmark, where TAGS are the bookmark's tags joined with commas in alphabetical order."

## Context: an extension of an existing feature

This feature extends the shipped command-line bookmark manager specified in
[`specs/001-bookmark-manager-cli/spec.md`](../001-bookmark-manager-cli/spec.md). That
specification and its CLI contract state that *exactly five commands exist* and that there is
*no import command*; this specification supersedes those two scope boundaries and nothing
else. Every other requirement of feature 001 (FR-001…FR-027, SR-001…SR-011) remains in force
unchanged, and this specification numbers its own requirements from FR-028 and SR-012 onward
so that the two documents can be cited together without collision.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bring an existing collection in from a file (Priority: P1)

A person has bookmarks somewhere else: a file another tool exported, a collection they
exported from this tool on a different machine, or a hand-written list. Instead of running
`add` once per link, they point the tool at the file, say which of the two formats it is in,
and get back a count of how many bookmarks were added. The bookmarks they already had are
untouched, and the new ones are indistinguishable from bookmarks they had typed in by hand.

**Why this priority**: Bulk entry is the only part of the tool a person cannot already do at
all. Without it, moving a collection of any size into the tool is impractical, and the
existing `export` is a one-way door.

**Independent Test**: Write a small JSON file and a small CSV file by hand, import each into
an empty database, and confirm the printed count, the assigned identifiers, and that a
following `list` shows exactly the imported bookmarks in the file's order. Fully testable
without HTML export existing.

**Acceptance Scenarios**:

1. **Given** an empty collection and a file `in.json` holding
   `[{"url": "https://docs.python.org", "title": "Python docs", "tags": ["python", "docs"]}, {"url": "https://example.com", "title": "Example", "tags": []}]`,
   **When** the user runs `import in.json --format json`, **Then** standard output is exactly
   `imported 2`, standard error is empty, the exit status is 0, and a following `list` prints
   `1<TAB>https://docs.python.org<TAB>Python docs<TAB>docs,python` and
   `2<TAB>https://example.com<TAB>Example<TAB>` in that order.
2. **Given** an empty collection and a CSV file whose first line is `id,url,title,tags`
   followed by two data rows, **When** the user runs `import FILE --format csv`, **Then**
   `imported 2` is printed, the exit status is 0, and both bookmarks are listed with their
   URLs, titles and tags.
3. **Given** a collection that already holds bookmarks 1 and 2, **When** the user imports a
   file holding three bookmarks, **Then** `imported 3` is printed, the existing bookmarks 1
   and 2 are unchanged, and the new bookmarks receive identifiers 3, 4 and 5 in file order.
4. **Given** an input file whose rows or objects carry an `id` field, **When** the user
   imports it, **Then** those values are ignored and identifiers are assigned by the
   collection's own rule, so importing a file whose ids are `7,8,9` into an empty collection
   produces bookmarks 1, 2 and 3.
5. **Given** a path that does not exist, names a directory, or cannot be read, **When** the
   user imports it, **Then** a message naming the problem is written to standard error,
   nothing is written to standard output, no bookmark is added, and the exit status is 2.
6. **Given** a file that is not valid input for the requested format — a CSV whose first line
   is not `id,url,title,tags`, a JSON document that is not an array of objects with the
   required keys, a record whose URL does not begin with `http://` or `https://`, or a record
   that exceeds a documented size limit — **When** the user imports it, **Then** a message is
   written to standard error, nothing is written to standard output, **not one** bookmark from
   the file is added, and the exit status is 2.
7. **Given** a file holding no bookmarks (a CSV with only its header line, or the JSON
   document `[]`), **When** the user imports it, **Then** `imported 0` is printed, the
   collection is unchanged, and the exit status is 0.

---

### User Story 2 - Read the collection as a web page (Priority: P2)

The person wants to look at their bookmarks, or hand them to someone who does not use a
terminal. They export the collection as an HTML page, redirect it to a file, and open it in a
browser: a single list of clickable links, each with its tags beside it.

**Why this priority**: It turns the collection into something a human can browse and click
rather than something only a script can parse, but it adds no new data and nothing depends on
it.

**Independent Test**: Seed bookmarks with and without titles and tags, run
`export --format html`, and confirm the output is the specified page, that it holds one list
item per bookmark in identifier order, and that a standard HTML parser recovers each URL,
title and tag list unchanged. Fully testable without import existing.

**Acceptance Scenarios**:

1. **Given** stored bookmarks, **When** the user runs `export --format html`, **Then**
   standard output is the fixed page skeleton of FR-040 with one `<li>` line per bookmark in
   ascending identifier order, standard error is empty, and the exit status is 0.
2. **Given** a bookmark with URL `https://docs.python.org`, title `Python docs` and tags
   `python` and `docs`, **When** the user exports as HTML, **Then** the output contains the
   line `<li><a href="https://docs.python.org">Python docs</a> <small>docs,python</small></li>`.
3. **Given** a bookmark with no title and no tags, **When** the user exports as HTML,
   **Then** its line is `<li><a href="URL"></a> <small></small></li>` — the link text and the
   tag text are both empty, and the line is still present.
4. **Given** a bookmark whose title or URL contains `<`, `>`, `&` or `"`, **When** the user
   exports as HTML, **Then** those characters appear in their escaped form, the page remains
   well-formed, and a standard HTML parser recovers the original title and URL exactly.
5. **Given** an empty collection, **When** the user exports as HTML, **Then** the page
   skeleton is printed with no `<li>` lines between `<ul>` and `</ul>`, and the exit status
   is 0.
6. **Given** any collection, **When** the user runs `export --format csv` or
   `export --format json`, **Then** the output is byte-for-byte what it was before this
   feature existed.

---

### User Story 3 - Move a collection from one database to another (Priority: P3)

The person has a collection on one machine, or in one database file, and wants it in another.
They export it and import the exported file into the other database, and the two collections
hold the same bookmarks — same URLs, same titles, same tags.

**Why this priority**: It is the pay-off of having both halves and the strongest single check
that the two formats agree, but it is a composition of stories 1 and 2 rather than new
behaviour.

**Independent Test**: Seed a database with bookmarks including awkward text, export to CSV
and to JSON, import each file into a fresh database, and compare the two collections' `list`
output ignoring identifiers.

**Acceptance Scenarios**:

1. **Given** a collection of bookmarks, **When** the user exports it as CSV and imports that
   file into an empty database, **Then** the new collection holds the same bookmarks with the
   same URLs, titles and tag sets, in the same order, with identifiers renumbered from 1.
2. **Given** the same collection, **When** the user exports it as JSON and imports that file
   into an empty database, **Then** the result is the same collection as in scenario 1.
3. **Given** a bookmark whose title contains a comma, a double quote, a newline or a
   non-ASCII character, **When** the user exports and re-imports it, **Then** the title is
   recovered unchanged.
4. **Given** an empty collection, **When** the user exports it in either format and imports
   the result, **Then** `imported 0` is printed and the target collection stays empty.

---

### Edge Cases

**Import — the file itself**

- **Unreadable path**: a path that does not exist, names a directory, denies read permission,
  or is a dangling symbolic link is an input failure (status 2), not a database failure.
- **Empty file**: a zero-byte file is invalid in both formats (CSV requires its header line,
  JSON requires a document) — status 2.
- **Not the requested format**: importing a JSON file with `--format csv`, or a CSV file with
  `--format json`, fails with status 2. The format is taken from `--format` only; the file
  name and its extension are never inspected.
- **Non-UTF-8 bytes**: a file that is not valid UTF-8 is rejected with status 2 rather than
  importing replacement characters.
- **Oversized file**: a file beyond the documented size or record-count limit is rejected with
  status 2 before any bookmark is added (see SR-014).

**Import — CSV shape**

- First line not exactly `id,url,title,tags`: rejected. This includes a reordered header
  (`url,id,title,tags`), a header with different letter case (`ID,URL,TITLE,TAGS`), extra or
  missing columns, and a file whose first line is already a data row.
- A data row with fewer or more than four fields: rejected.
- Quoted fields holding commas, double quotes or newlines: read back unchanged, per standard
  CSV quoting — this is what makes `export --format csv` output re-importable.
- A trailing blank line at the end of the file is ignored; a blank line between data rows is
  a row with the wrong field count and is rejected.
- A non-numeric or absent `id` field is accepted and ignored — the `id` column's content is
  never interpreted.

**Import — JSON shape**

- Top-level document is not an array (an object, a string, a number, `null`): rejected.
- An array element that is not an object: rejected.
- An element missing `url`, `title` or `tags`: rejected.
- `url` or `title` not a string; `tags` not an array, or an array holding a non-string:
  rejected.
- Extra keys (`id`, or anything else) are ignored.
- Deeply nested JSON is rejected with status 2 and a single-line message, never a crash or a
  traceback.

**Import — record content**

- A record whose URL is `ftp://example.com`, `javascript:alert(1)`, `example.com`, `` (empty)
  or `HTTPS://example.com` fails the whole import with status 2, because `add` would reject
  it.
- Degenerate tag values (`""`, `","`, `"a,,b"`, `" a , b "`, `"a,a"` in CSV, and the JSON
  arrays `[]`, `["a", "a"]`, `[" a ", "b "]`, `[""]`) resolve to the same tag sets `add`
  would produce, rather than being rejected or producing empty or duplicate tags.
- A record that duplicates a URL already in the collection, or another URL in the same file,
  is added as a separate bookmark — import never deduplicates.
- A record one character beyond a size limit of SR-006 fails the whole import with status 2.

**Import — the database**

- The target database does not exist: it is created exactly as any other command creates it,
  with the same file permissions.
- The target database is unusable or corrupt: that is a database failure with status 1, not
  status 2 — the distinction between "the file I was asked to read is wrong" (2) and "the
  collection I was asked to write to is broken" (1) is preserved.
- A failure part-way through writing leaves the collection exactly as it was: no partial
  bookmark, no orphan tag, and no change to the next identifier that will be issued.

**HTML export**

- A title containing `<script>alert(1)</script>`, `"`, `&`, or a lone `<` is escaped, so the
  page cannot be made to carry markup or script from stored data.
- A title containing a tab or a newline (which feature 001 stores verbatim) appears inside the
  link text as that character; the page stays well-formed, though the one-`<li>`-per-line
  shape of the output is broken by an embedded newline.
- A tag containing `<`, `>`, `&` or `"` is escaped inside `<small>`.
- Stored URLs are always `http://` or `https://` by FR-008, so no `href` can carry a
  `javascript:` or `data:` scheme; the escaping of FR-042 is what prevents an `href` from
  being broken out of.
- `export --format HTML` (uppercase) or any other unsupported value is an argument error with
  status 2, as before.

## Requirements *(mandatory)*

### Functional Requirements

**Compatibility with the existing tool**

- **FR-028**: Every behaviour specified by feature 001 MUST be preserved exactly: `add`,
  `list`, `search`, `delete` and `export --format csv|json` MUST accept the same arguments,
  write the same bytes to standard output and standard error, and return the same exit
  statuses as they do before this feature is added. No requirement FR-001…FR-027 or
  SR-001…SR-011 is weakened or changed.
- **FR-029**: A database file written by the tool before this feature MUST remain usable
  afterwards with no migration step, and a database written after this feature MUST remain
  usable by the five existing commands.

**The `import` command**

- **FR-030**: The system MUST be invocable as
  `python -m bookmarks [--db PATH] import FILE --format csv|json`, where `import` is a sixth
  subcommand alongside the existing five. `--db` MUST keep the meaning and default of FR-002,
  and the database file MUST be created when absent exactly as FR-003 requires.
- **FR-031**: `import` MUST require both the positional `FILE` and the `--format` option, and
  MUST reject any `--format` value other than `csv` or `json` as an argument error with exit
  status 2. The format MUST be determined by `--format` alone — never by the file's name,
  extension or content.
- **FR-032**: With `--format csv`, the system MUST read FILE as CSV whose first line is
  exactly `id,url,title,tags` and whose remaining lines each hold four fields in that order,
  parsed by standard CSV rules so that a quoted field containing a comma, a double quote or a
  newline is recovered unchanged. The `tags` field MUST be interpreted as the same
  comma-separated tag list `add --tags` accepts.
- **FR-033**: With `--format json`, the system MUST read FILE as a JSON array in which every
  element is an object carrying the keys `url` (a string), `title` (a string) and `tags` (an
  array of strings). Any other key in an element MUST be ignored.
- **FR-034**: The `id` present in the input MUST be ignored entirely. Each imported bookmark
  MUST receive a new identifier under the existing rule FR-007 — strictly increasing within
  the collection, continuing from the highest identifier the collection has ever issued, and
  never reusing one.
- **FR-035**: Each bookmark in the file MUST be added exactly as `add` would add it: the URL
  MUST satisfy FR-008 (an exact lowercase `http://` or `https://` prefix), the title MUST be
  stored verbatim as FR-009 requires, the tags MUST be derived by the parsing rule of FR-012
  (split on commas, trim each entry, discard entries that are then empty, keep each distinct
  tag once, preserving first-appearance order), and every size limit of SR-006 MUST apply
  unchanged. An imported bookmark MUST be indistinguishable from the same bookmark entered
  with `add`.
- **FR-036**: Bookmarks MUST be added in the order they appear in the file, so that ascending
  identifier order reproduces file order.
- **FR-037**: `import` MUST NOT remove, modify or reorder any bookmark already in the
  collection, and MUST NOT deduplicate: a URL already present, or repeated within the file,
  MUST produce an additional bookmark with its own identifier.
- **FR-038**: On success `import` MUST write exactly `imported N` followed by a newline to
  standard output — where N is the decimal count of bookmarks added — and nothing else, MUST
  write nothing to standard error, and MUST exit with status 0. A file holding no bookmarks
  (a CSV header line alone, or the JSON document `[]`) is a success that prints `imported 0`
  and changes nothing.
- **FR-039**: `import` MUST fail with exit status 2, a single human-readable line on standard
  error naming the problem, nothing on standard output, and **no bookmark added at all**,
  whenever any of the following holds: FILE cannot be opened or read; FILE is not valid UTF-8;
  FILE is not valid CSV or JSON of the shape required by FR-032 or FR-033; any record in FILE
  would be rejected by FR-035; or FILE exceeds a limit of SR-014. The import is
  all-or-nothing: a file whose last record is invalid MUST add none of its earlier records.
  A failure of the target database itself remains status 1 under FR-005, not status 2.

**`export --format html`**

- **FR-040**: `export --format html` MUST be accepted in addition to `csv` and `json`. The
  output of `export --format csv` and `export --format json` MUST NOT change, and any
  `--format` value outside `csv`, `json` and `html` MUST remain an argument error with exit
  status 2 (amending FR-026 only by adding `html` to the accepted set).
- **FR-041**: `export --format html` MUST write to standard output exactly these lines, in
  this order, each terminated by a newline:

  ```text
  <!DOCTYPE html>
  <html>
  <head><meta charset="utf-8"><title>Bookmarks</title></head>
  <body>
  <ul>
  ...one line per bookmark...
  </ul>
  </body>
  </html>
  ```

- **FR-042**: Between the `<ul>` and `</ul>` lines there MUST be exactly one line per stored
  bookmark, in ascending identifier order, of the form
  `<li><a href="URL">TITLE</a> <small>TAGS</small></li>` — where URL is the bookmark's URL,
  TITLE its title, and TAGS its tags joined with commas in ascending alphabetical (code-point)
  order, identical to the `tags` field of `export --format csv` and the fourth field of a
  listing line. A bookmark with no title yields empty link text, and a bookmark with no tags
  yields `<small></small>`; the line is still written.
- **FR-043**: Bookmark text placed in the page MUST be encoded for the HTML context it
  appears in, so that the page is well-formed whatever the stored text contains and a
  standard HTML parser recovers the stored URL, title and tag string unchanged. At minimum
  `&`, `<` and `>` MUST be escaped in element text, and `&`, `<`, `>` and `"` MUST be escaped
  inside the `href` attribute value. Text that contains none of those characters MUST appear
  literally, so the line in US2 scenario 2 holds byte-for-byte.
- **FR-044**: `export --format html` on an empty collection MUST print the skeleton of FR-041
  with no `<li>` line between `<ul>` and `</ul>`, and MUST exit 0.

### Security Requirements

Derived from the OWASP Top 10 (A03 Injection — including cross-site scripting, A04 Insecure
Design, A05 Security Misconfiguration) and OWASP ASVS chapters V5 (Validation, Sanitisation
and Encoding), V7 (Error Handling and Logging) and V12 (Files and Resources), as Constitution
Principle V requires. These add to the baseline of SR-001…SR-011, which continue to apply to
the new command and the new format; each requirement below is stated to be mechanically
testable and each needs at least one automated test including the negative case.

- **SR-012**: Output written into the HTML page MUST be encoded for its context (FR-043), so
  that stored data can never become markup. Negative test: a bookmark whose title is
  `<script>alert(1)</script>`, whose title contains `" onmouseover=x`, and whose URL contains
  `"` and `&`, MUST produce a page in which no raw `<script>` or unescaped attribute-breaking
  quote appears, and from which a standard HTML parser recovers the original strings.
- **SR-013**: The content of FILE MUST be treated as wholly untrusted and validated against
  the allowed shape before any of it is stored (FR-032, FR-033, FR-035) — accepting only the
  known-good header, field count, JSON types and keys rather than rejecting known-bad ones.
  Negative test: each of a wrong or reordered CSV header, a row with three or five fields, a
  top-level JSON object, an array element that is not an object, a missing `title`, a `tags`
  value that is a string rather than an array, a `tags` array holding a number, and a file of
  invalid UTF-8 bytes MUST exit 2 with the collection unchanged and the database file
  unmodified.
- **SR-014**: Every import input MUST have an enforced maximum size, rejected under FR-039
  with status 2: FILE at most 32 MiB, at most 50,000 records per import, and every record
  subject to the per-field limits of SR-006 (URL 8192 characters, title 4096, tag list 4096
  with at most 64 tags of at most 128 characters). Parsing MUST NOT recurse without bound:
  deeply nested JSON MUST be rejected with status 2 and a single-line message rather than
  exhausting the stack. Negative test: a file one record over the record limit, a file one
  byte over the size limit, a record one character over each field limit, and a JSON document
  nested thousands of levels deep are each rejected with nothing stored.
- **SR-015**: An import that fails for any reason MUST leave the collection byte-identical to
  its prior state — the whole import MUST commit as one unit or not at all (extending
  SR-009). Negative test: a file of 100 valid records whose last record has an invalid URL,
  and an import interrupted mid-write, each leave zero new rows in the collection and no
  orphan tag association; the identifier issued by the next successful `add` is unaffected by
  the abandoned import.
- **SR-016**: FILE MUST be used as a path to read and never as a shell word, a command, or a
  template; the system MUST NOT execute, import, or evaluate any part of FILE's content, and
  MUST NOT follow references contained in it (no included files, no URLs fetched, no network
  access of any kind — extending FR-011 and SR-010). Negative test: an import file whose
  fields contain shell metacharacters, a path-traversal sequence, and an `http://` URL that
  would error if fetched completes with those values stored as literal text and no process
  spawned and no socket opened.
- **SR-017**: FILE MUST be opened for reading only; `import` MUST NOT create, truncate,
  modify or delete FILE or anything else on the filesystem other than the database file and
  the storage engine's own transient files. Negative test: after a successful and after a
  failed import, FILE's content, size and modification time are unchanged, and the database
  directory holds only the database file (extending SR-011).
- **SR-018**: Every expected failure of `import` and of `export --format html` MUST produce
  exactly one line on standard error, with no stack trace and no internal detail — no SQL
  text, no Python exception class name, no absolute path other than one the user supplied
  (extending SR-008). Negative test: each documented status-2 import failure and each unusable
  database case produces a single-line message containing no `Traceback`, no `sqlite3`, and no
  SQL keyword.
- **SR-019**: `export --format html` MUST stream its output, so that peak memory does not grow
  with the collection size (extending SR-007 to the new format), and `import` memory MUST stay
  bounded by the limits of SR-014 rather than by the collection's size. Test: exporting 50,000
  bookmarks as HTML has a peak memory cost comparable to exporting 5,000, and importing a
  file at the record limit into a collection of 50,000 bookmarks does not grow memory with
  the collection.

### Key Entities *(include if feature involves data)*

The stored entities are unchanged from feature 001 — **Bookmark**, **Tag** and **Collection**
keep their definitions, attributes and relationships, and the storage schema needs no new
field. This feature adds one transient entity:

- **Import file**: a file supplied by the user holding a sequence of bookmark records in one
  of the two supported formats. Attributes: its path, its declared format, and its records.
  Each record carries a URL, a title and a tag list, plus an ignored identifier. It is read
  once, never written, and nothing about it is retained after the command finishes — the
  collection keeps no record of where a bookmark was imported from.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-008**: A person can move a collection of 1,000 bookmarks into a new database with a
  single command and no per-bookmark work, and the printed count matches the number of
  records in the file exactly.
- **SC-009**: Export and import are inverses: for 100% of collections, exporting as CSV or
  JSON and importing the result into an empty database reproduces every bookmark's URL,
  title and tag set in the original order, including titles holding commas, double quotes,
  newlines and non-ASCII text.
- **SC-010**: 100% of this feature's functional and security requirements (FR-028…FR-044,
  SR-012…SR-019) and 100% of the acceptance scenarios in User Stories 1–3 are covered by
  automated tests, and the whole suite — the tests of feature 001 included — passes with no
  skipped or disabled test.
- **SC-011**: Every test written for feature 001 passes unchanged after this feature is
  added, demonstrating mechanically that no existing command's behaviour moved.
- **SC-012**: Of the documented invalid import inputs, 100% produce a message on standard
  error, exit status 2, and a collection that is provably unchanged — zero cases of a partial
  import, a silent skip of a bad record, or a success status on bad input.
- **SC-013**: HTML export of a collection of 10,000 bookmarks completes in under one second
  on ordinary developer hardware, and importing a file of 10,000 records completes in under
  ten seconds, so neither feels like a batch job.
- **SC-014**: The HTML page parses with a standard HTML parser on the first attempt for 100%
  of collections, including collections whose titles, URLs and tags contain `<`, `>`, `&`,
  `"` and non-ASCII characters, and the parser recovers each stored value unchanged.
- **SC-015**: The standard-library-only constraint still holds mechanically: the shipped
  package imports nothing outside the Python standard library after this feature is added.

## Assumptions

Reasonable defaults chosen where the feature description was silent. Each is a decision the
tests will pin down. The assumptions of feature 001 (duplicate URLs allowed, exact
case-sensitive tag matching, code-point tag ordering, UTF-8 output, single-process use,
operator-supplied `--db` path, no network access) carry over unchanged.

- **A bad record fails the whole import.** The description says each bookmark is added
  "exactly as the `add` command would add it" and that a file which is not valid "imports
  nothing" and exits 2. A record whose URL `add` would reject, or whose field exceeds a size
  limit, is therefore treated as invalid input for the file as a whole: the import adds
  nothing and exits 2, rather than skipping the record or importing the rest. This is the
  reading that keeps "imported N" trustworthy and matches Constitution Principle II, which
  forbids reporting partial success as success.
- **Import is atomic.** "Imports nothing" is taken to mean the collection is unchanged, so
  all records of a file commit together or not at all.
- **The JSON `tags` list is parsed by `add`'s tag rules.** The list's entries are treated as
  the same comma-separated tag text `add --tags` accepts, so entries are trimmed, empty
  entries are dropped, duplicates collapse to one, and an entry that itself contains a comma
  becomes two tags. This keeps imported tag sets exactly what `add` can produce, which is
  what FR-035 requires; it also means a tag containing a comma cannot be imported, matching
  the fact that `export` cannot represent one either.
- **A JSON element must carry all three keys.** `url`, `title` and `tags` are each required
  with the stated type, rather than defaulting a missing `title` to `""` or a missing `tags`
  to `[]`. This is allow-list validation of the shape the description gives and the shape
  `export` writes, and it fails loudly on a file that is almost but not quite right.
- **The input encoding is UTF-8 without a byte-order mark**, matching what `export` writes. A
  file carrying a BOM, or any byte sequence that is not valid UTF-8, is rejected with status 2
  rather than silently stripped or replaced.
- **A trailing newline at the end of the input file is normal and ignored**; a blank line
  between CSV data rows is a malformed row.
- **`import` has no dry-run, no progress output, and no summary beyond the count.** The
  description specifies exactly one line of output, so nothing else is printed on success —
  no per-record log, no skipped-record report (there are none, by the first assumption).
- **The `FILE` path is operator-supplied and deliberately arbitrary**, exactly like `--db`:
  it is a first-party command-line argument, so the constitution's path-containment control
  does not apply, as there is no allowed base directory to confine it to. The path is used as
  a file path only, is opened read-only, and a path that cannot be read is an input error
  (status 2) rather than a silent empty import.
- **Status 2 is for the input file, status 1 for the database.** Where both could apply — an
  unreadable input file and an unusable database in the same invocation — the input file is
  validated first, so status 2 wins. This preserves the existing meaning of the two statuses.
- **Import limits are chosen, not given.** The description states no bound, and the
  constitution requires one, so SR-014 sets 32 MiB and 50,000 records per import. Both are
  far above any plausible hand-managed collection and keep worst-case memory and time
  bounded; the per-field limits are inherited from SR-006 rather than re-chosen.
- **HTML escaping is required even though the description's skeleton shows raw `URL` and
  `TITLE` placeholders.** The constitution's "encode output for the context it is written
  into" baseline control is non-negotiable and cannot be weakened by a feature, and the
  description's own example (`<a href="https://docs.python.org">Python docs</a>`) is
  unaffected because that text contains no character needing escape.
- **The HTML page is plain and unstyled.** No CSS, no JavaScript, no identifier column, no
  heading, no counts, no links to anything other than the bookmarks themselves, and no
  per-tag grouping — only the lines FR-041 and FR-042 specify. This also means the page needs
  no external resource and works offline.
- **The HTML page is not in the Netscape bookmark-file format** that browsers import
  (`<DT><A HREF=...>` inside `<DL>`); the description gives an explicit, different skeleton
  and that skeleton governs. Browser import compatibility is out of scope.
- **`export --format html` is output only.** There is no `import --format html`; the two
  importable formats are exactly `csv` and `json`.
- **Scope boundaries.** This feature adds one command and one export format and nothing else:
  no update or edit command, no tag rename, no deduplication or merge-on-import, no
  interactive mode, no configuration file, and no change to the storage schema.

### Technical Constraints *(inherited from the existing implementation, not derived)*

- Python 3.11 or newer, standard library only — which supplies CSV, JSON and HTML-escaping
  support, so no third-party dependency is needed (Constitution Principle I).
- The new behaviour lives in the existing `bookmarks` package under `src/`, runnable as
  `python -m bookmarks`, and reuses the existing validation, storage and rendering code
  rather than duplicating it (Constitution Principle IV).
- Storage remains the single SQLite database file, with the schema of feature 001 unchanged.
- Automated tests use `pytest` and sit alongside the existing suite (Constitution
  Principle III).
