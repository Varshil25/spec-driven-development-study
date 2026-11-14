# Phase 0 Research: Bookmark Import and HTML Export

**Feature**: `002-import-html-export` | **Date**: 2026-11-14 | **Plan**: [plan.md](./plan.md)

Decision numbering continues feature 001's [research.md](../001-bookmark-cli-manager/research.md)
(D1–D9), so a decision id means one thing across the whole tool, exactly as requirement ids do.
D1–D9 remain in force unchanged; this feature adds D10–D19.

The Technical Context in [plan.md](./plan.md) contains no NEEDS CLARIFICATION markers: the
specification, the existing code and the user's planning input (Python 3.11+, standard library
only, the interface exactly as specified, `pytest` for tests) fix every choice. The decisions
below are therefore *design* decisions, each traced to the requirement that forces it.

---

## D10. Import is read → validate → insert, with no insert before the file is fully valid

**Decision**: `import` runs as three strictly ordered steps:

1. read the whole file into one `str` (UTF-8);
2. parse and validate it completely, producing an in-memory list of
   `(url, title, tags)` triples with tags already normalised;
3. open the store and insert all of them in a single transaction.

No bookmark is inserted until every bookmark in the file has passed every check, including the
URL prefix rule.

**Rationale**: FR-037 requires all-or-nothing — a rejected file leaves the store byte-identical
*and* leaves the highest id ever used unchanged. Validating first makes that the default rather
than something to recover from: at the moment of the first `INSERT` there is no reachable
rejection left, so there is no partial state to undo. The spec's own Assumptions endorse it
("Reading the whole file into memory before the first insert is acceptable … that is what makes
all-or-nothing validation straightforward"), and the scale (SC-008/SC-015: 1,000 bookmarks) makes
memory a non-issue. It also extends D4 ("validate input before touching the store") rather than
contradicting it: a rejected import never even creates the store file.

**Alternatives considered**:

- *Insert as we parse, roll back on error.* Rejected: it relies on the rollback for correctness
  on every failure path, and the failure paths are the ones the spec cares most about (SC-010).
  It also means a malformed file can create an empty store as a side effect.
- *Two passes over the file (validate, then re-read and insert).* Rejected: twice the I/O and
  the risk of the file changing between passes, for no benefit over holding the parsed triples.
- *Stream with `SAVEPOINT`.* Rejected: SQLite machinery for a problem that does not exist at this
  scale (Principle IV).

**Belt and braces**: the single transaction in step 3 is still explicit (one `executemany`, one
`commit`), so even a `sqlite3.Error` mid-insert — the one failure left after validation — cannot
leave half an import behind. Verified: rolling back a transaction also rolls back
`sqlite_sequence`, so the next `add` receives the id it would have received anyway (FR-037).

---

## D11. No new runtime module: parsing lives in `cli.py`, one new query in `storage.py`

**Decision**: add to `cli.py` the pure functions `parse_csv_import`, `parse_json_import`,
`render_html` and the handler `_import`; add to `storage.py` exactly one function,
`add_bookmarks(conn, records)`. Create no `importer.py`, no `formats/` package, no classes.

**Rationale**: Principle IV ("prefer one module over several until a concrete reason to split
appears") and the seam feature 001 already drew — SQL in `storage.py`, every input/output and
exit-status choice in `cli.py`. Import parsing is pure text-to-data logic with no SQL, and it is
the mirror image of `export_csv`/`export_json`, which already live in `cli.py`; splitting it out
would separate the writer from the reader of the same format. The two modules stay small
(`cli.py` ~430 lines, `storage.py` ~85) and neither acquires the other's concerns.

`add_bookmarks` is a second insert function rather than a loop over `add_bookmark` in the CLI
because `add_bookmark` commits per row (FR-007 needs the new id immediately), which would defeat
the single transaction in D10. Keeping the loop in `storage.py` also keeps the only `executemany`
next to the schema it writes.

**Alternatives considered**:

- *A new `importer.py`.* Rejected: nothing in the requirements forces the split, and the module
  would be a ~70-line satellite that must import `normalise_tags`/`validate_url` back from
  `cli.py` — a cycle in all but name.
- *Reuse `add_bookmark` in a CLI loop with a manual `BEGIN`.* Rejected: it puts transaction
  control in the module that is supposed to issue no SQL.
- *An `Importer` class or a format-handler registry.* Rejected outright: "speculative extension
  points … are forbidden" (Principle IV). Two formats, two functions, one `if`.

---

## D12. A rejected file is signalled by one dedicated exception carrying the diagnostic

**Decision**: define `class ImportRejected(Exception)` in `cli.py`. Every shape, encoding and
readability failure raises it with the user-facing diagnostic as its message. `_import` is the
only place that catches it, writes `error: {message}` to stderr and returns 2.

**Rationale**: Principle II permits catching an exception "to wrap it with added context, or to
convert it into an explicit error result", and forbids silent fallbacks. One narrow exception type
gives exactly one conversion point: the parsers cannot be made to print, and the handler cannot be
made to guess a status. Crucially it is *not* `ValueError`: `json.JSONDecodeError` is a
`ValueError` subclass, so catching `ValueError` in the handler would also swallow genuine bugs in
our own code. Instead the parsers catch `json.JSONDecodeError`, `csv.Error`, `UnicodeDecodeError`
and `OSError` narrowly and re-raise them wrapped as `ImportRejected` with the file name and the
problem.

**Alternatives considered**:

- *Return `(records, error)` tuples.* Rejected: every helper gains a two-value contract and the
  handler gains an `if error` after each call; an unchecked return is a silent wrong answer
  waiting to happen, which Principle II treats as the worst outcome.
- *`sys.exit(2)` inside the parsers.* Rejected: it would put exit-status and stderr decisions
  outside `cli.py`'s single dispatch point and make the parsers untestable as pure functions.
- *Reuse `SystemExit`.* Rejected: indistinguishable from argparse's usage exits (status 1).

---

## D13. CSV input: `csv.reader` over the whole text, strict header, exactly four fields

**Decision**: parse with `csv.reader(io.StringIO(text, newline=""))`. The first row must compare
equal to `["id", "url", "title", "tags"]`; every following row must have exactly four fields, read
as `(ignored id, url, title, tags)`; the tags field goes through the existing `normalise_tags`.
An empty file (no header row at all) is rejected.

**Rationale**: FR-027 makes the header an exact requirement and FR-029 requires that anything
`export --format csv` writes reads back identically — the same `csv` module on both sides is the
only way to guarantee that for quoted commas, doubled quotes and embedded line breaks. Verified:
`io.StringIO(text, newline="")` reproduces the `newline=""` contract the `csv` docs require, so a
quoted field containing `\n` survives as one field. Comparing the parsed first row (rather than the
raw first line) means `id, url, title, tags` with spaces is rejected, as FR-027's "exactly" demands,
while a CRLF file is accepted. Rejecting a wrong field count rather than padding or truncating is
required by the spec's Assumptions ("coerced defaults that mask bad input are forbidden").

A consequence, accepted deliberately: a blank line inside the file parses as a zero-field row and
is therefore rejected. A single trailing newline produces no extra row, so files written by
`export --format csv` are unaffected.

**Alternatives considered**:

- *`csv.DictReader`.* Rejected: it silently tolerates missing and extra fields (`None` /
  `restkey`), exactly the coerced defaults FR-035 forbids, and it would make a wrong field count
  invisible.
- *Hand-rolled `line.split(",")`.* Rejected: breaks FR-029 for every quoted value.
- *Accepting any header whose column names match in any order.* Rejected: FR-027 says exactly.

---

## D14. JSON input: strict shape check, extra keys ignored, tags reduced by the `add` rules

**Decision**: `json.loads(text)` must yield a `list`; each element must be a `dict` carrying
`url` (`str`), `title` (`str`) and `tags` (`list` of `str`). Any other key, `id` included, is
ignored. Tags become `normalise_tags(",".join(tags))`. `bool` is not accepted where `str` is
required (an explicit `isinstance(x, str)` test does this already).

**Rationale**: FR-030 fixes the shape, FR-031 requires `export --format json` output (which
carries `id`) to import unchanged, and the spec's Assumptions make the strict/forgiving split
explicit: missing keys are malformed, extra keys are ignored, so a file from a later version of
the tool still imports. Reusing `normalise_tags` on the comma-joined list is not a shortcut but
the literal reading of FR-032 ("added exactly as `add` would add it"): the one observable
difference — a JSON tag that itself contains a comma splits in two — is precisely what
`add --tags` would do with that text, and no tag the tool stores can contain a comma anyway.

Diagnostics name the offending element by its zero-based index and the key at fault, so a
1,000-line file is debuggable (SC-011 requires the message to name the file or the offending
value).

**Alternatives considered**:

- *A `TypedDict`/`dataclass` plus a validation helper per field.* Rejected: more structure than
  three `isinstance` checks need (Principle IV).
- *Sorting/deduplicating tags in the parser.* Rejected: it would be a second implementation of
  FR-011's rules; `normalise_tags` is already the single definition.
- *Accepting a bare object (one bookmark) as well as an array.* Rejected: FR-030 says array, and
  the spec lists "a JSON object instead of an array" as a rejection case.

---

## D15. The file is read as UTF-8, and its read errors become status 2 — never status 1

**Decision**: read with `open(path, encoding="utf-8", newline="")` inside the parser step, and
catch `OSError` and `UnicodeDecodeError` *there*, converting both into `ImportRejected` (status 2)
with a message naming the path. The store is opened only afterwards, so the `OSError` handler in
`main()` — which means "the store could not be used", status 1 — can never see a *file* error.

**Rationale**: FR-034 demands status 2 for "does not exist, is not readable, is not a regular
file, or is not valid UTF-8", while FR-047 and the spec's edge cases keep status 1 for a store
that cannot be opened. Both conditions surface as `OSError`, so the only way to keep the two
statuses honest is to catch the file error at the point where the file is read. Ordering the read
before the store open also means a bad path cannot create the store file (D4, FR-037). UTF-8 with
no fallback and no `errors="replace"` matches what the export side writes and the Assumptions'
"reported as unreadable rather than guessed at".

`IsADirectoryError` (a directory) and `PermissionError` are `OSError` subclasses, so "is not a
regular file" and "is not readable" are covered by the same handler without a separate
`os.path.isfile` probe — one check fewer, and no time-of-check/time-of-use gap.

**Alternatives considered**:

- *Let `main()`'s existing `OSError` handler report it.* Rejected: it would exit 1 where FR-034
  requires 2, and would name the store instead of the file.
- *`Path.read_text(encoding="utf-8")`.* Rejected: it cannot pass `newline=""` on Python 3.11
  (that parameter arrived in 3.13), and D13 needs it for embedded line breaks.
- *`errors="surrogateescape"` or a latin-1 fallback.* Rejected: a silent fallback (Principle II),
  and it would let mojibake into the store.

---

## D16. HTML escaping covers exactly `&`, `<`, `>` and `"` — not the apostrophe

**Decision**: escape with `html.escape(value, quote=False).replace('"', "&quot;")`, applied to the
URL, the title and the joined tags.

**Rationale**: FR-042 names those four characters *and* requires that "text free of those
characters MUST appear verbatim". `html.escape`'s default `quote=True` also rewrites `'` as
`&#x27;`, so a title like `Bob's links` would come out altered — a direct FR-042 violation, and
visible in SC-012's "no mangled text". Verified against the interpreter: `quote=False` leaves both
quote characters alone, so the `"` → `&quot;` replacement must follow, and running it *after* the
`&` escaping is what keeps the `&` inside `&quot;` from being double-escaped. The order is
therefore load-bearing and is commented in the code.

**Alternatives considered**:

- *`html.escape(value)` (the default).* Rejected: alters apostrophes, as above.
- *Four chained `str.replace` calls.* Rejected: equivalent only if `&` is replaced first — the
  same ordering trap, hand-written, with no stdlib guarantee behind it.
- *Escaping the URL with `urllib.parse.quote`.* Rejected: it would rewrite stored URLs (percent-
  encoding `&` in a query string), which FR-041 forbids — the `href` must carry the bookmark's URL.

---

## D17. The HTML page is a fixed list of lines, assembled then printed

**Decision**: `render_html(rows)` returns the page as a single `str` built from a fixed list of
lines — DOCTYPE, `<html>`, the one-line `<head>`, `<body>`, `<ul>`, one `<li>` per bookmark,
`</ul>`, `</body>`, `</html>` — ending with a trailing newline. `export --format html` writes it
to stdout. `html` is added to `--format`'s `choices`.

**Rationale**: FR-040 fixes the skeleton line by line and FR-043 requires the skeleton to print
unchanged for an empty store; a fixed line list makes both the implementation and the test a
literal comparison, and makes the empty case fall out for free (zero `<li>` lines, no special
case). Returning a string rather than writing as it goes keeps the function pure and testable
without `capsys`, matching how `format_bookmark_line` is already tested. Adding `html` to
`choices` leaves FR-044 — any other format is a usage error on stderr with status 1 — to the
existing argparse machinery and `_Parser.error`, so no new error path appears at all.

The exact bytes are fixed in [contracts/html-export.md](./contracts/html-export.md): no CSS, no
timestamp, no count, no ids in the markup (the spec's Assumptions put all of that out of scope).

**Alternatives considered**:

- *`string.Template` or an f-string template with a joined middle.* Rejected: no simpler than a
  list of lines, and it hides where the newlines are — the thing the test asserts.
- *`xml.etree.ElementTree` / `html.parser`-based generation.* Rejected: it cannot emit
  `<!DOCTYPE html>` or the exact line breaks FR-040 requires, and would be far more machinery
  than nine lines of text need.
- *Writing each line with `print` as rows are read.* Rejected: untestable without capture, and it
  would stream a half page to stdout if a later row raised.

---

## D18. Status 2 gains a second, compatible meaning; `import` reuses `validate_url`

**Decision**: status 2 now means "this input was refused" — `add`'s bad URL prefix (FR-009) or
`import`'s rejected file (FR-034…FR-036). `import` checks URLs by calling the existing
`validate_url`, whose diagnostic already names the URL and the expected prefixes, and returns 2
for the whole command as soon as one URL fails (after the shape parse, before any insert).

**Rationale**: D5 reserved 2 and 3 for single fixed meanings so that a mistyped command line could
never be confused with a refused value. FR-047 extends 2 deliberately, and the extension keeps
D5's property intact: usage errors (unknown format, missing argument) still exit 1 through
`_Parser.error`, and 3 still belongs to `delete` alone. Reusing `validate_url` is what makes
FR-036 and FR-032 true by construction rather than by a second copy of the prefix rule — if the
rule ever changes, `add` and `import` cannot drift apart.

**Alternatives considered**:

- *A new status (4) for a rejected import.* Rejected: FR-034 and FR-047 specify 2.
- *A separate URL check for imports (e.g. collecting every bad URL).* Rejected: FR-036 rejects the
  file on the first offending URL and names it; collecting all of them is scope the spec excludes
  ("no `--skip-invalid`"), and a second prefix test would be a second source of truth.

---

## D19. Tests: four new `pytest` modules, the existing five untouched

**Decision**: add `tests/test_import.py` (FR-024…FR-038), `tests/test_export_html.py`
(FR-039…FR-044), `tests/test_roundtrip.py` (User Story 3, SC-009), and
`tests/test_compatibility.py` (FR-045…FR-047). Do not touch the five existing modules or
`conftest.py`; reuse its `db_path`, `run` and `run_cli` fixtures, with import files written into
`tmp_path`. Each test names its requirement in the name or docstring.

**Rationale**: Principle III and SC-013 require a named covering test per requirement; FR-045 and
SC-014 require the existing suite to pass *unmodified*, which is only demonstrable if the files
are not edited at all. The existing `conftest.py` already provides everything the new tests need
(a throwaway store, an in-process runner for fast assertions, a subprocess runner for real exit
statuses and stream separation), so no fixture changes are needed — which is itself evidence that
the feature adds no new kind of observable.

Performance (SC-015, 1,000 bookmarks in under five seconds) is validated by a timed scenario in
[quickstart.md](./quickstart.md), not by a wall-clock assertion in the suite, continuing the
choice made for SC-005 in feature 001 so test runs stay deterministic on shared hardware.

**Alternatives considered**:

- *Extend `test_export.py` with the HTML cases.* Rejected: it edits a file FR-045 wants proven
  untouched, for no gain.
- *One big `test_002.py`.* Rejected: the existing suite is split by command, and the mapping
  table in plan.md is per module.

---

## Resolved unknowns

| Question | Resolution |
|----------|-----------|
| Python version and dependencies | Python 3.11+ (local 3.13.17), standard library only; `csv`, `json`, `io`, `html`, `sqlite3`, `argparse`, `sys`. `pytest` stays the single dev dependency (user input; Principle I) |
| How is "all or nothing" guaranteed? | Full validation before the first insert, plus one explicit transaction for the inserts (D10) |
| Does a rolled-back import burn ids? | No — `sqlite_sequence` is restored by the rollback; verified against the interpreter (D10, FR-037) |
| Which status for an unreadable file vs. an unusable store? | 2 for the file, 1 for the store, separated by catching the file error at the read site (D15) |
| Are CSV quoting and embedded newlines handled? | Yes — same `csv` module both ways, `newline=""` preserved via `io.StringIO(text, newline="")` (D13) |
| What happens to an `id` in the file? | Parsed and discarded for CSV, ignored as an unrecognised key for JSON (D13, D14, FR-033) |
| Exactly which characters does the HTML export escape? | `&`, `<`, `>`, `"` only; `'` stays verbatim (D16, FR-042) |
| Where do the new tests go, and is the old suite edited? | Four new modules, nothing existing edited (D19, FR-045) |

No unknown remains open; Phase 1 proceeded on these decisions.
