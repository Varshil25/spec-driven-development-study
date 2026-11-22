# Phase 0 Research: Bookmark Import and HTML Export

**Feature**: `002-import-html-export` | **Date**: 2026-11-20 | **Spec**: [spec.md](./spec.md)

This feature extends shipped code, so Phase 0 is mostly *reading* rather than choosing: the
existing `bookmarks` package, its documented invariants and — critically — the feature-001
test suite constrain the design more tightly than the specification alone does. Every decision
below is recorded with the alternative that was rejected, as Constitution Principle IV
requires for any complexity and the Plan gate requires for the approach as a whole.

**Technical Context unknowns: none.** The specification's *Technical Constraints* section
fixes the language (Python 3.11+), the dependency policy (standard library only), the package
layout (`src/bookmarks`, `python -m bookmarks`), the storage engine (the existing SQLite
schema, unchanged) and the test framework (`pytest`). The user input for this plan restates
all four. No `NEEDS CLARIFICATION` marker was raised in Technical Context, so there is nothing
for this phase to resolve; the work below is the best-practices and integration-pattern
research the phase also calls for.

---

## Constraints discovered by reading the existing code

These are not choices. They are facts about the repository that the design has to satisfy, and
two of them are surprising enough to drive decisions R1 and R2.

| Source | Fact | Consequence |
|---|---|---|
| `src/bookmarks/cli.py` module docstring | "Validation order is fixed: argparse-level parsing, then the size limits below (SR-006), then the URL shape (FR-008), and only then is the database touched. Every status-2 case is therefore decided before the collection is opened, so a rejected command performs no read and no write (SR-009)." | A documented invariant of the module. `import` must uphold it (R3). |
| `tests/security/test_security_stdlib_only.py::test_shipped_files_are_the_five_planned_modules` | Asserts the shipped file list is **exactly** `__init__.py`, `__main__.py`, `cli.py`, `output.py`, `storage.py`. | A new shipped module would fail a feature-001 test, breaking SC-011 (R1). |
| `tests/security/test_security_stdlib_only.py::test_whole_package_imports_only_these_standard_modules` | Asserts every top-level import across the package is within `{__future__, argparse, contextlib, csv, dataclasses, json, os, sqlite3, sys, typing}`. | `csv` and `json` are already permitted; `html`, `io`, `stat` and `pathlib` are **not** (R2, R5, R7). |
| `tests/security/test_security_no_traceback.py` | Forbids the substrings `SELECT`, `INSERT`, `DELETE`, `UPDATE`, `PRAGMA`, `FROM bookmarks`, `VALUES (` and, case-insensitively, `traceback`, `sqlite`, `file "`, `line `, `.py` in any expected failure message. | `import` messages may not say "line 7" or `file "x"` (R11). |
| `tests/contract/test_cli_surface.py::test_no_sixth_subcommand` | Only asserts that `frobnicate` is rejected with status 2 — not that the parser has exactly five subparsers. | Adding the `import` subcommand keeps this test green. |
| `src/bookmarks/output.py` | `CSV_HEADER = ("id", "url", "title", "tags")`; `join_tags()` sorts by code point. | Import's header check and HTML's `TAGS` field both reuse these rather than restating them (R7, R12). |
| `src/bookmarks/cli.py` | `validate_url`, `parse_tags`, `_check_length` and the SR-006 limit constants already implement FR-008, FR-012 and the per-field limits. | FR-035 ("added exactly as `add` would add it") is satisfied by *calling* them, not by reimplementing them (R9). |

---

## Decisions

### R1 — No new shipped module: `import` lives in `cli.py`, HTML in `output.py`

**Decision**: Add the import command's reading and validation to `cli.py` and the HTML renderer
to `output.py`. Add one write helper to `storage.py`. Ship the same five files as before.

**Rationale**: SC-011 requires every feature-001 test to pass *unchanged*, and
`test_shipped_files_are_the_five_planned_modules` pins the shipped file list to exactly five
names. A sixth module (`importer.py`) would fail it. The placement is also the one the existing
separation of concerns already implies: `cli.py` is where untrusted input is validated,
`output.py` is where bookmarks are rendered, `storage.py` is where SQL lives. Principle IV
(fewest moving parts) points the same way — this feature adds roughly 120 lines, which does not
warrant a module.

**Alternatives considered**:

- *New `src/bookmarks/importer.py`* — cleaner by file size, but fails a feature-001 test and so
  violates SC-011. Rejected.
- *Amend the test's expected file list* — the smallest possible edit, but it is still an edit to
  a feature-001 test, which SC-011 forbids in as many words. Rejected; recorded as a deviation
  the user could choose to take instead (see plan.md Complexity Tracking).

### R2 — HTML escaping by explicit replacement, not `html.escape`

**Decision**: Implement two small functions in `output.py`:
`_escape_text()` replacing `&`, `<`, `>` (in that order, `&` first) and `_escape_attr()` adding
`"`. No `import html`.

**Rationale**: `test_whole_package_imports_only_these_standard_modules` asserts the package's
import set is a subset of a fixed list that does not contain `html`; importing `html.escape`
would fail a feature-001 test and break SC-011. The replacement set required is exactly what
FR-043 specifies as the minimum (`&`, `<`, `>` in element text; those plus `"` in the `href`
value), it is three and four `str.replace` calls respectively, and SR-012 plus SC-014 pin it
down with a negative test and a `html.parser` round-trip — so the usual objection to
hand-rolled escaping (nobody checks it) does not apply here.

Ordering is the one real hazard: `&` must be replaced first, or `<` → `&lt;` would itself be
re-escaped into `&amp;lt;`. A dedicated unit test asserts `&<>"` → `&amp;&lt;&gt;&quot;` and
that `&amp;` in a stored title survives as `&amp;amp;`.

**Alternatives considered**:

- *`html.escape(value, quote=True)`* — the obvious stdlib answer and what this plan would
  choose in a vacuum. It also escapes `'` to `&#x27;`, which FR-043 neither requires nor
  forbids. Rejected only because of the import whitelist / SC-011; noted in plan.md
  Complexity Tracking as a one-line alternative if the user prefers to amend that test.
- *`xml.sax.saxutils.escape`* — same whitelist problem, and it does not escape `"` by default.
  Rejected.
- *Build the page with `xml.etree.ElementTree`* — would produce a different byte layout than
  the fixed skeleton FR-041 mandates, cannot emit `<!DOCTYPE html>`, and is not streaming.
  Rejected.

### R3 — Two-phase import: validate the whole file, *then* touch the database

**Decision**: `cmd_import` reads and validates FILE completely into an in-memory list of
`(url, title, tags)` records. Only if every record is valid does it open the collection and
write. Any input fault raises `BookmarksError(msg, 2)` before `storage.connect` is ever called.

**Rationale**: This upholds `cli.py`'s documented invariant verbatim ("every status-2 case is
decided before the collection is opened") and it makes four separate requirements fall out for
free rather than needing machinery:

- **FR-039 / SR-015** (all-or-nothing): a bad record means no write was ever attempted.
- **SR-013** ("the database file unmodified"): on a status-2 import the database file is not
  opened — and if it did not exist, it is not even *created*.
- **SR-017** ("the database directory holds only the database file"): no journal is created on
  a rejected import because no transaction is started.
- The spec Assumption that "the input file is validated first, so status 2 wins" when both the
  file and the database are broken: true by construction, not by ordering care.

Memory cost is bounded by SR-014's own limits (≤ 32 MiB of file text), which SR-019 explicitly
permits: "`import` memory MUST stay bounded by the limits of SR-014 rather than by the
collection's size." It is independent of how many bookmarks the collection already holds.

**Alternatives considered**:

- *Stream records straight into one open transaction and roll back on the first bad record* —
  O(1) record memory, and `sqlite3`'s rollback does restore correctness. Rejected because it
  creates the database file and a rollback journal before deciding a status-2 case, which makes
  SR-013's "database file unmodified" and SR-017's "only the database file" assertions
  materially harder to honour, and it inverts the module's documented validate-then-write
  order for one command out of six.
- *Two passes over the file (validate, then re-read and insert)* — O(1) memory and keeps the
  ordering, but reads the file twice, so the file could change between passes. Rejected: a
  time-of-check-to-time-of-use gap the constitution's access-control control names explicitly.

### R4 — Atomicity by one `sqlite3` transaction; the identifier sequence rolls back with it

**Decision**: All inserts for one import happen inside a single `with connection:` block via a
new `storage.add_bookmarks(connection, records) -> int`.

**Rationale**: `with connection:` commits on success and rolls back on any exception, which is
the pattern `add_bookmark` and `delete_bookmark` already use. SR-015 additionally requires that
"the identifier issued by the next successful `add` is unaffected by the abandoned import" —
that is a real question about SQLite's `AUTOINCREMENT`, which keeps its high-water mark in the
`sqlite_sequence` table. **Verified empirically on this machine** (Python 3.13.17): inserting
one row, then inserting five rows inside a transaction that then raises, then inserting again,
yields identifier **2** — the sequence update was rolled back with the data. So no extra work
is needed to satisfy that clause.

`add_bookmark` and `add_bookmarks` share a private `_insert_bookmark()` helper so the row+tags
insert exists once; the transaction boundary stays with the caller, which is what makes
one-per-`add` and all-per-`import` both correct.

**Alternatives considered**: `executemany` for the bookmark rows — faster, but `lastrowid` is
undefined for it, and each bookmark's tags need its identifier. Rejected. `SAVEPOINT` nesting —
no requirement needs partial rollback. Rejected (Principle IV).

### R5 — File gate: `os.path.isfile` then `os.path.getsize`, before any read

**Decision**: Before opening FILE: reject with status 2 if `os.path.isfile(path)` is false, then
reject if `os.path.getsize(path) > 32 * 1024 * 1024`.

**Rationale**: `os.path.isfile` follows symlinks and returns `True` only for a regular file, so
one check covers every "unreadable path" case the spec lists — missing path, a directory, a
dangling symlink, a FIFO — and keeps them all status 2 rather than letting a directory surface
as an `IsADirectoryError` later. `os.path.getsize` enforces SR-014's 32 MiB bound *before*
reading a byte, so an oversized file costs one `stat`, not 32 MiB of I/O. A file that denies
read permission passes both checks and fails at `open()`, which is caught and mapped to status
2 as well.

`stat.S_ISREG` would be the more explicit spelling, but `stat` is not in the import whitelist
(see R2's constraint), and `os.path.isfile` is exactly equivalent for this purpose.

**Alternatives considered**: reading with `handle.read(LIMIT + 1)` as the only bound — in text
mode that counts *characters*, not bytes, so it does not implement a byte limit. Kept as a
belt-and-braces second check for the JSON path, where the whole text is read anyway, but not
as the primary gate. Rejected as the sole mechanism.

### R6 — UTF-8 strict, and a byte-order mark is a rejection

**Decision**: Open FILE with `encoding="utf-8"` (not `utf-8-sig`) and the default strict error
handler. A `UnicodeDecodeError` anywhere becomes status 2.

**Rationale**: Strict decoding is what makes the spec's "importing replacement characters" an
impossibility and satisfies the constitution's allow-list-encoding control. Choosing `utf-8`
over `utf-8-sig` is what rejects a BOM, per the spec Assumption: with plain `utf-8` a leading
BOM decodes to `﻿`, so the CSV header comparison fails and `json.loads` raises — both
status 2, with no special-case code. This is also exactly the encoding `export` writes, so
round-tripping (SC-009) is unaffected.

### R7 — CSV: `csv.reader` straight over the file handle, header compared to `output.CSV_HEADER`

**Decision**: `open(path, encoding="utf-8", newline="")` and iterate `csv.reader(handle)`. The
first row must equal `list(output.CSV_HEADER)`. Every subsequent row must hold exactly four
fields.

**Rationale**: `newline=""` is what the `csv` module's documentation requires so that a `\n`
inside a quoted field is returned as data rather than ending the record. **Verified
empirically**: a row written by this project's own `export --format csv` whose title is
`two\nlines, and "quotes"` reads back through `csv.reader` as that exact string — which is the
mechanism behind SC-009 and FR-032's round-trip clause. Comparing against `output.CSV_HEADER`
rather than a literal tuple means the importer cannot drift from the exporter.

Passing the handle (rather than a `StringIO` over the whole text) also avoids needing `io`,
which is not in the import whitelist, and avoids `text.splitlines(True)`, which splits on
`\x0b`, `\x0c` and ` ` as well and would therefore corrupt a quoted field containing any
of them.

**Blank lines**: `csv.reader` yields `[]` for a genuinely blank line and yields nothing extra
for a trailing newline after the last record (**verified empirically**). The spec wants a
trailing blank line ignored but a blank line *between* rows rejected, so the reader keeps a
`pending_blank` flag: an empty row sets it, and a later non-empty row with the flag set is a
rejection. A blank line that is last therefore costs nothing.

**Alternatives considered**: `csv.DictReader` — it would silently tolerate a reordered header
and fill missing columns with `None`, the opposite of SR-013's allow-list requirement.
Rejected. Sniffing the dialect with `csv.Sniffer` — FR-031 says the format comes from
`--format` alone and the dialect is the one `export` writes. Rejected.

### R8 — JSON: `json.loads` on the whole text, catching `RecursionError` as well as `ValueError`

**Decision**: Read the text, then `json.loads`, catching `(ValueError, RecursionError)` and
mapping both to a single-line status-2 message.

**Rationale**: SR-014 requires that "deeply nested JSON MUST be rejected with status 2 and a
single-line message rather than exhausting the stack." **Verified empirically**: `json.loads`
on `"[" * 100000 + "]" * 100000` raises `RecursionError`, not a segfault — so catching it is
sufficient and no hand-written depth pre-scan is needed. `json.JSONDecodeError` is a subclass
of `ValueError`, so one `except` clause covers malformed JSON too.

The validation that follows is strictly allow-list (SR-013): the document must be a `list`;
each element must be a `dict`; `url` and `title` must be present and be `str`; `tags` must be
present and be a `list` whose every element is a `str`. Any other key is dropped silently, as
FR-033 requires. Because `bool` is not a `str`, `"url": true` is rejected without a special
case.

**Alternatives considered**: `sys.setrecursionlimit` to a lower value — global, affects
unrelated code, and does not remove the need to catch the error. Rejected. A hand-written
incremental JSON array parser to avoid materialising the document — the stdlib has no
incremental array API, so this means writing a parser: a large amount of new, security-relevant
code to save memory the spec already bounds. Rejected (Principle IV); the consequence is
recorded in plan.md Complexity Tracking.

### R9 — Every record is validated by calling `add`'s own validators

**Decision**: For each record, in the same order `cmd_add` uses:
`_check_length(title, MAX_TITLE_LENGTH, "title")`, then `parse_tags(tag_text)`, then
`validate_url(url)` (which checks `MAX_URL_LENGTH` itself).

**Rationale**: FR-035 says an imported bookmark "MUST be indistinguishable from the same
bookmark entered with `add`". The only way to guarantee that mechanically — and to keep it true
if `add`'s rules ever change — is to run the same functions in the same order, not a parallel
copy of the rules. This is also what makes the degenerate-tag edge cases (`","`, `"a,,b"`,
`" a , b "`, `"a,a"`) resolve identically without a single line of import-specific tag code.

**JSON `tags` arrays** are converted with `",".join(tags)` and handed to the same
`parse_tags`, per the spec Assumption that the list's entries are "the same comma-separated tag
text `add --tags` accepts". So `["a", "a"]` collapses to one tag, `[" a ", "b "]` trims,
`[""]` and `[]` give no tags, and an entry containing a comma becomes two tags — all inherited
from FR-012 rather than re-specified. The SR-006 4096-character tag-list limit applies to the
joined text, which is the same string `add --tags` would have received.

**Alternatives considered**: treating each JSON array element as one literal tag (so a comma
inside an element stays in the tag). Rejected: the spec Assumption decides against it, and it
would let `import` create a tag `export` cannot represent.

### R10 — Record-count limit checked as records accumulate

**Decision**: Reject with status 2 when a 50,001st record is encountered, before it is appended.

**Rationale**: SR-014's "at most 50,000 records per import" needs to bite before the list grows
past the bound, not after the file is fully parsed, so that a hostile file cannot make the
process allocate past the limit. For CSV this is a check inside the row loop. For JSON the
document is already materialised by `json.loads` (R8), so the check is on `len(document)`
before per-element validation — the 32 MiB file gate (R5) is what bounds memory on that path.

### R11 — Error-message vocabulary chosen against the inherited disclosure test

**Decision**: Import failure messages are one line, name the problem and the position, use
`{path!r}` for the user-supplied path, and say **"row N"** — never "line N", never
`file "..."`.

**Rationale**: `test_security_no_traceback.py` (feature 001) forbids the case-insensitive
substrings `line `, `.py`, `file "`, `traceback` and `sqlite` in any expected failure message,
and SR-018 extends that same standard to every new failure. "line 7" would trip `line `, and
`file "in.csv"` would trip `file "`. `{path!r}` renders as `'in.csv'` — single quotes — which is
what the existing `storage.py` messages already do. "row" is not in the forbidden SQL
vocabulary.

Planned messages (each one line, each ≥ 3 words so the actionability assertion holds):

| Case | Message |
|---|---|
| Not a readable regular file | `cannot read {path!r}: it is not a readable file` |
| Over 32 MiB | `{path!r} is too large to import: {n} bytes, at most 33554432 allowed` |
| Not valid UTF-8 | `cannot read {path!r}: it is not valid UTF-8 text` |
| Permission denied | `cannot read {path!r}: permission denied` |
| CSV header wrong | `invalid CSV: the first row must be exactly 'id,url,title,tags'` |
| CSV field count | `invalid CSV: row {n} has {k} fields, exactly 4 required` |
| CSV blank row | `invalid CSV: row {n} is blank` |
| CSV empty file | `invalid CSV: the header row is missing` |
| Malformed JSON | `invalid JSON: the document could not be parsed` |
| JSON too deep | `invalid JSON: the document is nested too deeply` |
| JSON not an array | `invalid JSON: the document must be an array of bookmark objects` |
| JSON element shape | `invalid JSON: record {n} must be an object with 'url', 'title' and 'tags'` |
| JSON tags shape | `invalid JSON: record {n} must give 'tags' as an array of strings` |
| Too many records | `too many bookmarks to import: at most 50000 allowed` |
| Bad record content | the message `add` itself raises, prefixed `record {n}: ` |

The last row matters: an invalid URL inside an import reuses `validate_url`'s own wording, so
the user gets the same explanation `add` would give, with the record number added.

### R12 — HTML export streams, and reuses `join_tags`

**Decision**: `output.write_html(bookmarks, stream)` writes the five prologue lines, then one
`<li>` line per bookmark as it arrives from the cursor, then the three epilogue lines. `TAGS`
comes from the existing `join_tags()`.

**Rationale**: This is the same shape as `write_csv`/`write_json`, so SR-019's streaming
requirement is met by the mechanism already proven by `test_security_streaming.py` — the
bookmark iterator is a lazy cursor and nothing accumulates. Reusing `join_tags()` is what makes
FR-042's "identical to the `tags` field of `export --format csv`" true by construction rather
than by coincidence: one code-point sort, one join, three call sites.

The skeleton is stored as two module constants rather than being assembled per call, so
FR-041's byte-exact line sequence is reviewable in one place and `export --format html` on an
empty collection (FR-044) is simply "prologue then epilogue".

### R13 — Status 2 is the input file; status 1 stays the database

**Decision**: No change to `main()`'s error handling. `BookmarksError(msg, 2)` for every input
fault, `BookmarksError(msg, 1)` for a storage fault, raised from the same places as before.

**Rationale**: `main()` already maps `BookmarksError.status` to the return value and writes
`exc.message` to stderr, so the new command needs no new error plumbing — which is both
Principle IV and the cheapest way to inherit SR-018's single-line guarantee. The precedence the
spec asks for (file first) is a consequence of R3's ordering.

### R14 — `--format` on `import` is an argparse `choices` tuple

**Decision**: `import_parser.add_argument("--format", required=True, choices=("csv", "json"), dest="fmt")`,
matching `export`'s existing spelling; `export`'s own choices tuple gains `"html"`.

**Rationale**: argparse rejects any other value with status 2 on stderr through the project's
`_Parser.error` override, which already trims the usage block to one line — so FR-031's and
FR-040's "argument error with exit status 2" needs no code of its own. `required=True` gives
the same treatment to a missing `--format`. Note that `import` is a Python keyword but a
perfectly ordinary subparser *name*; the handler is `cmd_import` and the dispatch dict key is
the string `"import"`.

**Alternatives considered**: accepting `--format html` for `import` and failing later — the
spec says the importable formats are exactly `csv` and `json`, and `choices` is the allow-list
the constitution asks for. Rejected.

---

## Best practices consulted for the chosen standard-library tools

- **`csv`** — the documented requirement to open with `newline=""` is the single most common
  defect in stdlib CSV code and is the reason embedded newlines round-trip (R7). Field count is
  checked explicitly because `csv.reader` has no schema of its own.
- **`json`** — `JSONDecodeError` is a `ValueError`; recursion on nested input raises
  `RecursionError` rather than crashing; `json.loads` has no depth or size parameter, so limits
  must be imposed around it (R8, R10).
- **HTML escaping** — escape `&` first; escape `"` only where the value lands in an attribute;
  escaping is per-context, which is why R2 defines two functions rather than one (ASVS V5).
- **`sqlite3`** — `with connection:` is a transaction, not a close; `lastrowid` is meaningless
  after `executemany`; `AUTOINCREMENT` high-water marks live in `sqlite_sequence` and roll back
  with the transaction (R4, verified).

## Observations recorded, no action taken

- A CSV field containing a NUL character passes through `csv.reader` unchanged (**verified**)
  and would be stored verbatim, consistent with FR-009's "stored verbatim" and FR-035's
  "indistinguishable from `add`" — `add --title $'a\0b'` behaves the same way. No requirement
  addresses NUL, so no special case is added; noted so a reviewer need not rediscover it.
- A title containing a newline produces an `<li>` element spanning two physical lines in the
  HTML output. The spec's Edge Cases call this out and accept it; the page stays well-formed
  and the parser round-trip of SC-014 still holds.
