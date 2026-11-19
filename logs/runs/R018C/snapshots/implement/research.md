# Phase 0 Research: Import and HTML Export

**Feature**: `002-import-html-export` | **Date**: 2026-11-16

**Input**: [spec.md](./spec.md), [constitution](../../.specify/memory/constitution.md),
existing code in `src/bookmarks/` and research for
[`001-bookmark-manager-cli`](../001-bookmark-manager-cli/research.md)

This feature adds one command and one export format to a working tool. The decisions below are
therefore mostly about *where to put the new code without disturbing the old*, and about the
exact standard-library behaviour the byte-level requirements depend on.

Findings marked **verified** were confirmed by running the code during this phase on
Python 3.13.17 / SQLite 3.45.1 (the development interpreter; the declared floor stays 3.11, per
`pyproject.toml`). The pre-existing suite was run as a baseline: **131 passed, 2 skipped**.

No `NEEDS CLARIFICATION` markers remain in the Technical Context.

---

## R-101: Reading the import file — encoding, byte-order mark, and invalid UTF-8

**Decision**: Open the file once with `open(path, encoding="utf-8-sig", newline="")` and let the
text layer do all three jobs: decode as UTF-8 (FR-009), discard a single leading byte-order mark,
and leave line endings untranslated for the CSV reader. Wrap the open and the read in one
`try`/`except (OSError, UnicodeDecodeError)` that raises `BookmarkError(..., 2)`.

**Rationale**: The `utf-8-sig` codec strips exactly one leading BOM and is otherwise identical to
`utf-8`, which is precisely the clarified rule ("a single leading byte-order mark is discarded
before parsing, for both file shapes"). Using it on both shapes means the BOM rule has one
implementation rather than two. `newline=""` is the same setting the CSV writer side already uses
(`cli.main` reconfigures stdout that way) and is what keeps a line break inside a quoted field
part of that field (FR-006).

**Verified**:

- `\xef\xbb\xbfid,url,title,tags\n…` read with `utf-8-sig` yields the first field as `id`, not
  `﻿id` — the mark never reaches the header comparison (FR-009).
- `b"\xff\xfe\x00bad"` raises `UnicodeDecodeError` (`'utf-8' codec can't decode byte 0xff in
  position 0`) — a message that already names the file problem (FR-010).
- Opening a directory raises `IsADirectoryError`, a subclass of `OSError`, so the absent /
  directory / permission-denied cases of FR-010 are one except clause.

**Alternatives considered**:

- *Read bytes, strip `codecs.BOM_UTF8` by hand, then `.decode("utf-8")`*: rejected — three steps
  where the codec is one, and it re-implements a standard-library behaviour (Principle IV).
- *`encoding="utf-8", errors="replace"`*: rejected outright — it would silently substitute
  U+FFFD for undecodable bytes, the exact "silent wrong answer" Principle II ranks as the
  highest-severity defect. FR-009 requires failure.
- *Streaming the file record by record instead of reading it whole*: rejected — atomicity
  (FR-011) requires the entire file to be validated before the store is touched, so the records
  must be held in memory anyway. At 1,000 bookmarks (SC-001, SC-005) the memory cost is trivial.

---

## R-102: Parsing the CSV shape — header, field count, and blank lines

**Decision**: Feed the open file object straight to `csv.reader` with default dialect settings.
Compare the **first yielded record** against the list `["id", "url", "title", "tags"]`. Require
every later record to have `len(record) == 4`. Do not filter or skip any record.

**Rationale**: Every clarified CSV rule falls out of `csv.reader`'s own behaviour, with no
hand-written text handling:

| Requirement | How `csv.reader` satisfies it |
| --- | --- |
| Header compared after parsing, so `"id","url","title","tags"` is accepted (FR-006) | The reader strips the quotes before the comparison sees the values |
| Quoted fields may hold commas, doubled quotes, line breaks (FR-006) | Standard dialect, `newline=""` on the file |
| `\n` and `\r\n` both accepted (FR-006) | The reader accepts either terminator |
| A blank line is a record of zero fields and must fail (FR-006a) | A blank line yields `[]`, whose length is 0, not 4 |
| The newline ending the last row is not a blank record (FR-006a) | A trailing `\n` after the final row yields no extra record |
| A header line alone imports 0 and succeeds (FR-006) | The reader yields exactly one record |
| An empty file fails (Edge Cases) | The reader yields nothing, so there is no header record |

**Verified**, in one probe:

- `id,url,title,tags\r\n1,https://a,A,"x,y"\r\n\r\n` →
  `[['id','url','title','tags'], ['1','https://a','A','x,y'], []]`. The quoted `x,y` arrives as
  **one** field holding two labels (FR-006, Edge Cases), and the blank line arrives as `[]`,
  which the length check rejects (FR-006a).
- `1,"a\nb",t,x\n` → `[['1','a\nb','t','x']]`: the embedded line break stays inside the field and
  the single trailing newline produces no blank record, so the tool's own
  `export --format csv` output imports cleanly (FR-006a).

**Alternatives considered**:

- *`csv.DictReader`*: rejected — it would hide both failures the spec cares about. A wrong header
  silently becomes wrong key names, and a short or long row silently becomes `None` /
  `restkey` values instead of an error (FR-006a, Principle II).
- *Comparing the header as raw text (`line == "id,url,title,tags"`)*: rejected — contradicts the
  clarification that `"id","url","title","tags"` must be accepted.
- *`skipinitialspace` or any non-default dialect*: rejected — the writer side uses defaults, so
  the reader must too, or the round trip of SC-001 is not a round trip.

---

## R-103: Parsing the JSON shape — structure validation

**Decision**: `json.loads(text)`, catching `json.JSONDecodeError` → status 2. Then validate by
hand, in this order: the top level is a `list`; each element is a `dict`; its key set contains
`url`, `title`, `tags` and nothing outside `{"id", "url", "title", "tags"}`; `url` and `title`
are `str`; `tags` is a `list` whose every element is a `str`.

**Rationale**: FR-007 and FR-010 enumerate exactly these failures, and each needs a diagnostic
naming what was wrong and what was expected (Principle II), which a bare `json.loads` cannot
give. The `id`-accepted-and-ignored rule (FR-007) and the unrecognised-key-is-an-error rule
(FR-010) are the two halves of one key-set comparison.

`isinstance(value, bool)` deserves a note: in Python `True` is an `int`, not a `str`, so a JSON
`true` in a `url` field is already rejected by the `str` check. No extra guard is needed.

**Alternatives considered**:

- *`dataclasses` + a generic validator, or `json.JSONDecoder(object_hook=…)`*: rejected — a
  framework for two fixed shapes (Principle IV). Four explicit checks read better than a schema
  engine and produce better messages.
- *Accepting a single object as a one-element array*: rejected — FR-007 and the Edge Cases
  require status 2 for a top level that is not an array.
- *Defaulting a missing `title` or `tags` to empty*: rejected — Principle II forbids substituting
  a default, and the spec's Assumptions call a gap in a specified shape a reportable mistake.

---

## R-104: Where tag normalisation happens for each shape

**Decision**: Both shapes converge on the existing `store.normalise_tags`, which takes the
comma-joined string form. CSV passes its fourth field through unchanged. JSON joins its list with
`","` first: `normalise_tags(",".join(record["tags"]))`.

**Rationale**: FR-003 requires labels to end up exactly as `add --tags` would store them, and the
only way to *guarantee* that is to call the same function on the same kind of value. Joining the
JSON list is lossless for every file the tool itself writes, because a stored tag can never
contain a comma — `normalise_tags` splits on commas, so no comma survives into storage. For a
hand-written file whose `tags` holds `["a,b"]`, joining yields the two labels `a` and `b`, which
is precisely what `add --tags "a,b"` does; "added exactly as `add` would add it" is honoured
rather than bent.

**Alternatives considered**:

- *Normalising the JSON list element-wise (strip, lower, drop empties, de-duplicate) in a second
  function*: rejected — a second implementation of FR-010's five steps is a drift risk for no
  behavioural gain on any file the export writes, and the two would disagree on an element
  containing a comma, with no requirement to say which is right.
- *Rejecting a `tags` element that contains a comma*: rejected — no requirement asks for it, and
  it would be scope beyond the spec (Principle IV).

---

## R-105: Atomicity — validate the whole file before opening the store

**Decision**: Order the import strictly as: **read and decode** the file → **parse** it →
**validate every record**, including `store.check_url` for every address → **then**
`store.open_store` → insert all records → commit once → print `imported N`. No store call of any
kind happens until the file is known to be wholly good.

**Rationale**: This single ordering satisfies four requirements at once, with no rollback
machinery:

- FR-011 (nothing added on failure): no insert has been issued.
- FR-011 (no store file created on failure): `open_store` is what creates the file, and it has
  not been called. This is the only way to get the behaviour, since `open_store` creates the
  file as its first act.
- FR-011 (the next identifier is unaffected): no `INSERT` ran, so SQLite's `AUTOINCREMENT`
  counter never advanced.
- FR-002a / FR-017 (a file problem is never reported as status 1): the file is fully judged
  before the store can raise its own status-1 error, so the two error classes cannot be confused.

The spec's Assumptions reach the same conclusion from the other direction ("the import file is
read and validated before the store is opened, which is what makes 'creates no store file on
failure' achievable"), so this is the specified design, not merely a convenient one.

**Alternatives considered**:

- *Insert inside a transaction and roll back on the first bad record*: rejected — it does not
  satisfy "no store file is created", because opening the store creates the file before any
  transaction begins. It is also more machinery for a weaker guarantee (Principle IV).
- *Validate lazily and delete the store file if it turns out we created it*: rejected — deleting
  a file on an error path is the kind of destructive recovery that goes wrong; and it is
  unnecessary given the ordering above.

---

## R-106: One insert path shared by `add` and `import`

**Decision**: Extract the body of the existing `store.add_bookmark` into an unexported
`_insert_bookmark(connection, url, title, tags)` that inserts without committing. `add_bookmark`
becomes `check_url` → `_insert_bookmark` → `commit` (identical behaviour to today).
A new `store.add_bookmarks(connection, records)` checks every URL, calls `_insert_bookmark` for
each record in file order, commits **once**, and returns the number inserted.

**Rationale**: FR-003 ("added exactly as `add` would add it") is strongest when it is structural:
one INSERT path means `add` and `import` cannot drift in how they store a title or a tag set.
FR-005 (identifiers ascend in file order) falls out of inserting in order. The single commit is
also what makes SC-005 comfortable — 1,000 separate commits mean 1,000 fsyncs, which on ordinary
hardware is the one plausible way to miss a five-second budget, whereas one commit is a single
flush.

Checking *all* URLs before inserting *any* keeps R-105's guarantee intact even though
`check_url` lives in the store module: the check needs no database.

**Alternatives considered**:

- *Have the import call the existing `add_bookmark` in a loop*: rejected on performance (a commit
  per bookmark against SC-005) — though it is worth recording that it would be *correct*, since
  all validation precedes the loop.
- *Hand the import its own INSERT statements in `importer.py`*: rejected — duplicates the schema
  knowledge and the tag-insert rule, and breaks the structural guarantee of FR-003.
- *Wrapping the inserts in an explicit `BEGIN`/`ROLLBACK`*: rejected — nothing inside the loop
  can fail for a reason the spec covers, and `sqlite3`'s implicit transaction already means an
  uncaught fault commits nothing.

---

## R-107: Escaping the HTML page as a closed set of four substitutions

**Decision**: Use `html.escape(value, quote=False)` for the title and the labels, and
`html.escape(value, quote=False).replace('"', "&quot;")` for the `href` value.

**Rationale**: FR-014 defines a *closed* set — `&`, `<`, `>` everywhere, plus `"` inside `href`
only — and explicitly requires the apostrophe to stay literal and `&` to be substituted first.
`html.escape`'s `quote=False` branch is exactly those three substitutions, in that order.
`quote=True` is unusable here: it also rewrites `'` as `&#x27;`, which FR-014 and Acceptance
Scenario 2.6 forbid. Hence the explicit `"` replacement for the one attribute, applied after the
escape (which never introduces a `"`), so no escape is doubly escaped.

**Verified** by reading `html.escape`'s source and running it:

- `html.escape('a&<>"\'b', quote=False)` → `a&amp;&lt;&gt;"'b` — the double quote and the
  apostrophe both literal, `&` done first (the source comments `# Must be done first!`).
- `html.escape('a&<>"\'b')` → `a&amp;&lt;&gt;&quot;&#x27;b` — confirming why the default is
  rejected.

**Alternatives considered**:

- *Hand-rolled `.replace()` chain*: rejected — `html.escape(quote=False)` is the same three
  replacements already written, tested, and ordered correctly in the standard library.
- *`xml.sax.saxutils.escape`*: rejected — equivalent for the three characters but a heavier
  import from an XML package, and `quote`-style extras are specified via a dict rather than the
  plain flag.
- *A real HTML generator (`xml.etree`, templates)*: rejected — FR-012/FR-013 require specific
  bytes, specific line breaks and exactly one trailing newline; a generator would have to be
  fought to produce them (Principle IV).

---

## R-108: Emitting the page, and leaving CSV/JSON untouched

**Decision**: Add `render_html(rows)` to `cli.py` beside `render_csv`/`render_json` and register
it in the existing `RENDERERS` dict. Emit the five fixed opening lines, one `<li>` line per row,
then the three fixed closing lines, each written with an explicit `\n`.

**Rationale**: `handle_export` already dispatches through `RENDERERS[args.format]`, and the
parser already derives its `choices` from `sorted(RENDERERS)`. Adding one key therefore delivers
FR-012 *and* FR-001's sibling rule for export (an unsupported `--format` gets argparse's own
diagnostic and status 2, Acceptance Scenario 2.9) with no new validation code, and — because
nothing on the CSV or JSON path is touched — satisfies FR-015/SC-006 by construction rather than
by inspection.

`sorted(RENDERERS)` becomes `csv, html, json`; the help text and error messages pick that up
automatically. Writing explicit `"\n"` (rather than relying on `print`) matches FR-013 and is
unambiguous under the `newline=""` stdout reconfiguration `main` already performs; non-ASCII
characters pass through literally because that same stdout is UTF-8 (FR-013, `001:FR-023a`).

**Alternatives considered**:

- *A separate `html.py` renderer module*: rejected — one function of a dozen lines next to its
  two siblings; a module for it would be a package layer with no requirement behind it
  (Principle IV, "prefer a flat module layout").
- *A `--format html` branch written as an `if` in `handle_export`*: rejected — it would bypass
  the `RENDERERS`/`choices` coupling that makes the invalid-format path free.

---

## R-109: Where the import code lives

**Decision**: A new module `src/bookmarks/importer.py` holding the file reading, both parsers and
the record validation. `cli.py` gains a thin `handle_import` and the `import` subparser; `store.py`
gains only `add_bookmarks` (R-106). No other file changes.

**Rationale**: The parsing logic is ~60 lines with two shapes and a dozen failure messages — the
largest single piece of this feature, and the only one with no natural home in the existing two
modules. It is neither command grammar (`cli.py`) nor storage (`store.py`); folding it into
either would make that module about two things. The layout stays flat, as the constitution
prefers: three modules in one package, no subpackages.

The module is named `importer.py`, not `import.py`: `import` is a reserved word, so `import.py`
could never be imported.

Reusing `store.BookmarkError` for the file failures is deliberate — the status is data on the
exception (`001` research R-008), so `cli.main`'s single `except` clause already renders a
status-2 file diagnostic correctly with no new handler. The error type stays in `store.py` rather
than moving, so no existing import or test changes.

**Alternatives considered**:

- *Put it all in `cli.py`*: rejected — pushes one module past 300 lines and mixes argument
  grammar with file parsing.
- *Put it in `store.py`*: rejected — the import file is explicitly *not* part of the collection
  (spec Key Entities: "It is read, never written"), and `store.py` is the module that owns the
  collection.
- *A new exception type for file failures*: rejected — would require a second handler in `main`
  for no behavioural difference (Principle IV).

---

## R-110: Testing approach for the new surface

**Decision**: Two new test files, `tests/test_import.py` (FR-001 … FR-011) and
`tests/test_html_export.py` (FR-012 … FR-014), plus additions to the existing performance test
for SC-005. Every test name carries the requirement it covers, matching the existing convention
(`test_fr018_…`). All CLI behaviour is exercised through the existing `run_cli` subprocess
fixture; import files are written with `tmp_path`. **No existing test file is modified** (FR-015,
SC-006, FR-020).

**Rationale**: Constitution Principle III requires an explicit requirement-to-test mapping, and
the repository already expresses it in test names. The exit statuses of FR-010 and FR-017 are
process statuses, which only a subprocess can observe (`001` research R-009) — the `run_cli`
fixture exists for exactly that. The two-file split mirrors the two user stories, so each story's
"Independent Test" can be run alone.

Byte-for-byte assertions are the right instrument for FR-013/FR-014/SC-004: the page is fully
determined by the collection, so the test compares the whole string, not a parse of it. SC-004
additionally asks that a *standard page reader* recover the values, which `html.parser`
(standard library, test-side) supplies — a check that the escaping is correct, not merely stable.

**Alternatives considered**:

- *Adding the new cases to `tests/test_export.py`*: rejected — FR-020 and SC-006 require the
  pre-existing tests to pass **unmodified**, and the cleanest way to be able to prove that is to
  not touch the files at all.
- *In-process calls to `cli.main` for speed*: rejected for the status assertions; `main` returns
  a status rather than exiting, so it cannot evidence the process-level contract.
- *A third test file for the round trip (User Story 3)*: rejected — the round trip is
  import-driven and belongs with the import tests; a file per story would split fixtures for no
  gain.

---

## Resolved unknowns summary

| Unknown from Technical Context | Resolved by |
| --- | --- |
| How to discard a byte-order mark for both shapes | R-101 (`utf-8-sig`) |
| How invalid UTF-8 becomes status 2, not a crash | R-101 |
| How "blank line = zero fields" is detected | R-102 (`csv.reader` yields `[]`) |
| How a quoted header is accepted but a wrong one rejected | R-102 (compare parsed record) |
| Which JSON structural checks are needed, and their order | R-103 |
| How JSON `tags` reaches the existing normaliser | R-104 (comma join) |
| How "no store file on failure" is achieved | R-105 (validate before `open_store`) |
| How 1,000 inserts stay inside the time budget | R-106 (single commit) |
| How FR-014's closed substitution set maps to the stdlib | R-107 (`html.escape(quote=False)`) |
| How CSV/JSON output is guaranteed unchanged | R-108 (new dict key only) |
| Where the new code lives without growing the layout | R-109 (`importer.py`) |
| How each requirement gets an identified test | R-110 |
