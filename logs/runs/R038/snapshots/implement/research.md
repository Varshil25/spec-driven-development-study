# Phase 0 Research: Command-Line Bookmark Manager

**Feature**: `001-bookmark-manager-cli` | **Date**: 2026-11-20 | **Plan**: [plan.md](./plan.md)

## NEEDS CLARIFICATION status

**None outstanding.** The Technical Context in [plan.md](./plan.md) was filled without any
`NEEDS CLARIFICATION` marker: language, dependencies, storage, testing, platform, project
type, performance goals, constraints and scope are all fixed either by the spec's Technical
Constraints section, by the user input for this planning step (Python 3.11+, standard library
only, exact interface from the spec, pytest), or by the spec's measurable outcomes
(SC-003/SC-004 give the performance and scale figures). The spec's own Assumptions section
had already resolved the behavioural ambiguities (duplicate URLs, tag case sensitivity, tag
sort order, tabs in titles, `--db` arbitrariness, single-process use).

The research below therefore covers the second and third Phase 0 categories — best practices
for each chosen technology, and integration patterns — plus the design questions where more
than one standard-library approach could satisfy a requirement. Each decision was verified
against the interpreter and SQLite actually present (Python 3.13.17, SQLite 3.45.1); where a
decision depends on a minimum version, that minimum is stated so the code stays valid on any
Python 3.11+.

---

## R1. Identifier allocation that never reuses a deleted id

**Decision**: `id INTEGER PRIMARY KEY AUTOINCREMENT` on the `bookmarks` table.

**Rationale**: FR-007 and User Story 3 acceptance scenario 3 require that after the highest
identifier is deleted, the next `add` receives a *higher* identifier, never the deleted one.
A plain `INTEGER PRIMARY KEY` is an alias for SQLite's `rowid` and allocates `max(rowid)+1`,
which *does* reuse an identifier once the maximum row is deleted. `AUTOINCREMENT` makes
SQLite keep a high-water mark in the internal `sqlite_sequence` table, so allocation is
strictly monotonic for the life of the file. Verified empirically: inserting ids 1 and 2,
deleting 2, then inserting again yields 3. This also satisfies the spec's assumption that
"identifier allocation is monotonic per collection, provided by the storage engine's own
row-identifier allocation".

**Alternatives considered**:
- *Plain `INTEGER PRIMARY KEY`* — rejected: reuses the deleted maximum, directly violating
  FR-007.
- *Soft delete (a `deleted` flag)* — rejected: keeps data the user asked to remove, forces
  every read query to carry a predicate, and adds a column with no requirement behind it
  (Principle IV).
- *An application-managed counter row* — rejected: reimplements in Python, with its own
  transaction concerns, what the storage engine already guarantees.

**Consequence for the exhaustion edge**: `AUTOINCREMENT` fails with `SQLITE_FULL` once the
sequence reaches 2^63−1. That is unreachable in practice and is handled by the generic
exit-status-1 path, not by special-case code.

## R2. Creating the database file with `0600` at creation time

**Decision**: open the path with `os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)`
and close the descriptor, *then* call `sqlite3.connect(path)`. Only do this when the file does
not already exist; an existing file's mode is left untouched.

**Rationale**: SR-005 and the constitution's "File permissions" control both require
owner-only mode set *at creation time*, not by a later `chmod` (which leaves a window where
the file is group/world readable). `sqlite3.connect()` has no mode parameter and creates the
file through the SQLite C library at `0644 & ~umask`, so the file must exist with the right
mode before SQLite first opens it. Pre-creating an empty file is safe: SQLite treats a
zero-length file as a valid empty database. `O_EXCL` means the create path cannot be used to
clobber or follow a pre-existing file, and the `FileNotFoundError` it raises when the parent
directory is missing is exactly the exit-status-1 case the spec's Edge Cases demand (a
missing parent directory must not be created silently). Verified: mode is `0o600` after first
use, and no `-journal`, `-wal` or `-shm` file remains after commit.

**Alternatives considered**:
- *`os.chmod` after `connect`* — rejected: the mode is set after creation, which the
  constitution's control explicitly forbids, and the race is real.
- *Process-wide `os.umask(0o077)`* — rejected: a global side effect that affects every file
  the process touches, and it is advisory rather than an assertion about this file.
- *`PRAGMA journal_mode=WAL`* — rejected: WAL leaves `-wal` and `-shm` files beside the
  database between connections, which conflicts with SR-011 ("no temporary file containing
  bookmark data left behind after any command"). The default `delete` journal mode removes
  the rollback journal on commit and is sufficient for single-process use (spec Assumptions).

## R3. Literal, case-insensitive substring search

**Decision**: `WHERE instr(lower(b.title), lower(:text)) > 0 OR instr(lower(b.url),
lower(:text)) > 0`, with `:text` bound as a parameter.

**Rationale**: FR-015 wants a case-insensitive substring match; FR-016 and SR-004 require
that `%` and `_` in the search text match only themselves. `LIKE` would interpret both as
wildcards, and the usual fix — `LIKE ? ESCAPE '\'` with the text pre-escaped in Python — adds
an escaping function that must itself be correct and tested. `instr()` has no pattern
language at all, so literalness is structural rather than something the code must maintain.
Wrapping both sides in `lower()` gives the ASCII-case-insensitive behaviour the spec's
Assumptions call for ("case-insensitive over ASCII letters at minimum"; full Unicode case
folding explicitly not required — SQLite's built-in `lower()` is ASCII-only, which matches).
`instr()` has been available since SQLite 3.7.15 (2012), far below anything bundled with
Python 3.11+. Verified: a search for `%` matches only the row whose title literally contains
`%`, and a non-matching needle returns no rows.

**Alternatives considered**:
- *`LIKE '%' || ? || '%' ESCAPE '\'` with Python-side escaping* — rejected: correct but adds
  an escaping step, a second failure mode, and more tests for no behavioural gain.
- *Filtering in Python after `SELECT`-ing every row* — rejected: moves the scan out of the
  engine and, done naively, conflicts with the streaming requirement; also loses the index-
  free but C-speed `instr` scan.
- *FTS5 virtual table* — rejected: substring (not token) matching is required, FTS5 brings a
  second schema and tokeniser configuration, and Principle IV forbids the machinery for a
  requirement this small.

## R4. Reading each bookmark with its ordered tags, in bounded memory

**Decision**: one query per read command — a `LEFT JOIN` from `bookmarks` to `bookmark_tags`
ordered by `(b.id, t.tag)` — iterated row by row, with adjacent rows sharing a bookmark id
grouped into one bookmark by a Python generator that yields a bookmark as soon as its id
changes.

**Rationale**: three requirements pull against each other. FR-017/FR-023/FR-024 need each
bookmark's tags joined in ascending code-point order; SR-007 needs rows streamed rather than
the collection materialised; SC-004 needs a command on 10,000 bookmarks to finish inside a
second. The `LEFT JOIN` + adjacent-row grouping satisfies all three: a single cursor, one
round trip, `ORDER BY` done by the engine using the primary-key and tag indexes, and at most
one bookmark's worth of tags held in memory at a time. `LEFT JOIN` (not inner) is what makes
a tagless bookmark still appear, as FR-017 requires with its empty trailing field.

**Alternatives considered**:
- *`group_concat(tag, ',')` in SQL* — rejected: `group_concat` had no defined output ordering
  before SQLite 3.44's `ORDER BY` clause inside aggregates, and the Python that ships with
  3.11 may bundle an older SQLite. Relying on the ordering an ordered subquery happens to
  produce is undefined behaviour; FR-017's ordering is a hard requirement.
- *An N+1 pattern (stream bookmarks, query tags per bookmark)* — rejected: 10,001 queries for
  the SC-004 scenario, and the outer cursor stays open across writes-free reads but gains
  nothing in clarity.
- *`SELECT` all rows then group with `itertools.groupby` on a materialised list* — rejected:
  memory grows with the collection, violating SR-007. (`itertools.groupby` over the *cursor
  iterator* would in fact be fine and is an acceptable implementation of the chosen decision;
  what is rejected is materialising a list first.)

## R5. Exit statuses from `argparse` without losing the specified mapping

**Decision**: use `argparse` for the parser, rely on its built-in behaviour (usage message to
stderr, `SystemExit(2)`) for unknown commands, unknown options and missing arguments; express
`delete ID` and `export --format` validation as argparse `type=`/`choices=` so they produce
the same exit 2; and have `main(argv)` *return* an int for the cases argparse cannot express
(invalid URL → 2, missing identifier → 3, unusable database → 1), with `__main__.py` doing
the single `sys.exit(main(...))`.

**Rationale**: FR-005 fixes four statuses, and argparse's native usage-error status is
already 2, so the parser needs no `exit_on_error` override or custom `error()` for the whole
"Unknown command, unknown option, or missing required argument" edge case. A `type=` callable
raising `argparse.ArgumentTypeError` routes `abc`, `1.5`, `-1`, `0` and an out-of-range
identifier through the same path, satisfying FR-022 and SR-003 without hand-written branches.
`choices=("csv", "json")` plus `required=True` covers FR-026. Keeping `main()` a function
that returns a status (rather than exiting) is what makes the suite able to assert statuses
with `capsys` and no subprocess, which in turn keeps the tests fast enough for SC-004's
timing assertions to be meaningful.

The validation order matters and is fixed by the design: argparse-level checks first, then
size limits (SR-006), then URL shape (FR-008), and only then is the database touched. That
ordering is what makes "nothing is read or written in the database" true for every exit-2
case, and it is asserted directly in `tests/security/test_security_args.py`.

**Alternatives considered**:
- *Hand-rolled `sys.argv` parsing* — rejected: reimplements subcommands, usage text and the
  exit-2 convention that argparse already provides correctly (Principle IV).
- *`parser.exit_on_error = False` with a top-level `try`* — rejected: adds a branch to
  reproduce the behaviour the default already has.
- *Raising a custom exception for every failure and mapping it at the top* — partially
  adopted: one small `BookmarksError(message, status)` carries the non-argparse failures so
  each command function stays a straight line, but argparse keeps its own path rather than
  being wrapped.

## R6. Streaming CSV and JSON export

**Decision**: CSV via `csv.writer(sys.stdout, lineterminator="\n")`, writing the header then
one `writerow` per bookmark as it arrives from the cursor. JSON by emitting the array
punctuation directly — `[`, then `json.dumps(obj, ensure_ascii=False)` per element separated
by `,`, then `]` — rather than `json.dumps` over a list.

**Rationale**: FR-025 requires commas, double quotes, newlines and non-ASCII characters to
round-trip through a standard parser, which is precisely what `csv.writer`'s RFC 4180 quoting
and `json.dumps`'s string escaping give; writing either format by hand would be the
"string-built interpretation" the constitution forbids. SR-007 requires bounded memory, which
rules out `json.dumps(list(rows))`; per-element dumping keeps peak memory at one bookmark
while still producing a single valid JSON array. `ensure_ascii=False` keeps non-ASCII text
readable on the UTF-8 stdout the spec assumes, and remains valid JSON. `lineterminator="\n"`
overrides the csv module's `\r\n` default to give ordinary Unix line endings; `\n` is accepted
by `csv.reader` and every mainstream CSV parser, and it keeps FR-023's "header row followed
by one row per bookmark" shell-friendly (SC-006 expects a tab/CSV one-liner to work).
`sys.stdout` is reconfigured to UTF-8 (`sys.stdout.reconfigure(encoding="utf-8",
newline="\n")`) once at entry, which also stops the csv module's documented `\r\n` translation
problem on platforms that would otherwise newline-translate.

**Alternatives considered**:
- *`json.dumps` of a fully built list* — rejected: O(collection) memory, violating SR-007
  and its 50,000-bookmark test.
- *`json.JSONEncoder().iterencode(generator)`* — rejected: `iterencode` does not accept a
  generator as a top-level array, so it would need a fake-list shim — more machinery than the
  three-line manual array.
- *Default `\r\n` CSV terminator* — rejected as the primary choice for shell ergonomics,
  though it would also be spec-conformant; the choice is recorded here so the test asserts one
  definite behaviour rather than accepting either.

## R7. Transaction boundaries and atomicity

**Decision**: one explicit transaction per mutating command, using `with connection:` around
the write (`sqlite3`'s context manager commits on success and rolls back on any exception).
Validation happens entirely before the transaction opens. `PRAGMA foreign_keys = ON` is set
on every connection, and `bookmark_tags` declares `REFERENCES bookmarks(id) ON DELETE
CASCADE`.

**Rationale**: SR-009 requires a bookmark and its tags to be committed together or not at
all, and a failed command to leave the prior state. `add` is one `INSERT` into `bookmarks`
plus up to 64 `INSERT`s into `bookmark_tags`; wrapping them in one transaction makes the
bookmark-plus-tags unit atomic, so an interrupted write cannot leave a bookmark with half its
tags or an orphan association. For `delete`, the `ON DELETE CASCADE` plus the enabled pragma
means a single `DELETE FROM bookmarks WHERE id = ?` removes the tag associations in the same
statement and the same transaction, satisfying FR-019 with no second statement to get wrong —
and `cursor.rowcount == 0` is exactly the FR-021 "no such identifier" signal, read inside the
transaction so the 3-status path commits nothing. The foreign-key pragma must be set per
connection because SQLite defaults it off for backward compatibility; without it the CASCADE
is declared but inert, which is the orphan-association bug SR-009's test looks for.

**Alternatives considered**:
- *Autocommit with individual statements* — rejected: a crash between the bookmark insert and
  its tag inserts leaves a partial row, violating SR-009.
- *Two explicit `DELETE` statements for `delete`* — rejected: the declared foreign key already
  expresses the relationship, and relying on it keeps the invariant in the schema where it
  cannot be forgotten by a future caller.
- *`SELECT` to check existence, then `DELETE`* — rejected: a time-of-check-to-time-of-use gap
  and an extra query; `rowcount` after the `DELETE` answers the same question atomically.

## R8. Tag storage shape

**Decision**: two tables. `bookmark_tags(bookmark_id, tag)` stores the tag *text* directly in
the association row, with `PRIMARY KEY (bookmark_id, tag)`.

**Rationale**: the spec's Key Entities describe a Tag with a single attribute (its text), a
bookmark holding a set of distinct tags, and a tag applying to many bookmarks. All three hold
in the two-table shape: the composite primary key enforces the per-bookmark set property in
the schema (so FR-012's deduplication is belt-and-braces rather than the only defence), and
the same tag text appearing in rows for different bookmarks is exactly "a tag may apply to
many bookmarks". Principle IV then decides between this and a normalised three-table design.

**Alternatives considered**:
- *A `tags(id, name UNIQUE)` lookup table plus `bookmark_tags(bookmark_id, tag_id)`* —
  rejected: it buys storage normalisation and cheap global tag rename, neither of which any
  requirement asks for (the spec's Scope boundaries explicitly exclude tag rename and tag
  delete commands), and it costs an upsert-and-lookup on every `add`, a join on every read,
  and orphan-tag cleanup on every `delete` — three new moving parts and a new class of bug
  (orphan rows in `tags`) for no specified behaviour.
- *A denormalised `tags TEXT` column on `bookmarks` holding a comma-joined string* —
  rejected: `list --tag TAG` (FR-014) would become a substring match, which cannot distinguish
  tag `py` from tag `python`, and FR-019's "that bookmark's tag associations" language implies
  real associations.

## R9. Proving the standard-library-only constraint mechanically

**Decision**: a test that walks every `.py` file under `src/bookmarks/` with `ast.parse`,
collects the top-level module name of every `import` and `from ... import`, and asserts each
is in `sys.stdlib_module_names`; the same test asserts that `subprocess`, `socket` and
`os.system`/`os.popen` appear nowhere in the shipped source.

**Rationale**: SC-007 asks for a *mechanical* reviewer check and SR-010 forbids shelling out,
spawning processes, opening sockets or reading environment-driven configuration.
`sys.stdlib_module_names` (available since Python 3.10) is the authoritative frozen set of
standard-library top-level modules, so the check needs no curated allow-list to maintain.
Parsing the AST rather than grepping text avoids both false positives from comments and false
negatives from unusual formatting. The negative half of the test — asserting the forbidden
names are absent — is what makes SR-010 a tested requirement rather than a convention.

**Alternatives considered**:
- *Running `pip freeze` / inspecting a lockfile* — rejected: proves nothing about what the
  code imports, and there is no dependency manifest to inspect.
- *Importing the package in a clean virtualenv* — rejected: a true but coarse check that
  cannot tell `subprocess` usage from legitimate standard-library usage, and is slow.
- *Text `grep` for `import`* — rejected: brittle against comments and strings; the AST walk is
  barely longer.

## R10. Test harness shape

**Decision**: `pytest` with `pythonpath = src` in `pytest.ini`; a `conftest.py` fixture
`run(*argv)` that calls `bookmarks.cli.main(list(argv))` in-process and returns
`(status, stdout, stderr)` via `capsys`, plus a `db` fixture giving a `tmp_path`-based
database path. Tests pass `--db` explicitly except where the default-path behaviour (FR-002)
is under test, which uses `monkeypatch.chdir(tmp_path)`.

**Rationale**: Constitution Principle III requires every requirement to map to an automated
pytest test, and SC-002 requires 100% coverage of the FR/SR sets, so the harness has to make
writing ~50 small assertions cheap. In-process invocation costs microseconds where
`subprocess` would cost tens of milliseconds, which matters for the 1,000-command persistence
test (SC-003) and the 50,000-bookmark export test (SR-007). It also keeps the suite free of
`subprocess`, consistent with SR-010's spirit for the tests themselves. The one thing
in-process testing cannot check is that `python -m bookmarks` actually wires up — so
`tests/contract/test_cli_surface.py` includes a single `runpy`-based check that the
`__main__` module exists and is importable, and the quickstart's manual steps exercise the
real command line.

**Alternatives considered**:
- *`subprocess.run([sys.executable, "-m", "bookmarks", ...])` everywhere* — rejected: 100×
  slower per case, makes the performance tests measure process startup, and introduces
  subprocess use into the project.
- *`click.testing`-style runner from a third-party package* — rejected: Principle I; `capsys`
  already does this.
- *Golden-file comparison of whole outputs* — rejected for most cases: a field-level
  assertion names the requirement it checks, which the FR/SR traceability matrix needs; golden
  files are used only for the CSV/JSON escaping round-trip cases, where re-parsing with `csv`
  and `json` is the actual assertion.

---

## Summary of resolved unknowns

| Question | Resolution | Requirement |
|---|---|---|
| Never-reused identifiers | `AUTOINCREMENT` high-water mark | FR-007 |
| `0600` at creation | `os.open(..., O_CREAT\|O_EXCL, 0o600)` before `connect` | SR-005 |
| Literal case-insensitive search | `instr(lower(col), lower(?))`, no `LIKE` | FR-015, FR-016, SR-004 |
| Ordered tags + bounded memory | single `LEFT JOIN` ordered by `(id, tag)`, grouped while streaming | FR-017, SR-007 |
| Exit statuses | argparse native 2; `main()` returns 0/1/2/3 | FR-005, FR-022, FR-026, SR-003 |
| Faithful streaming export | `csv.writer` + per-element `json.dumps` | FR-023…FR-025, SR-007 |
| Atomic writes, no orphans | one transaction per command; FK `ON DELETE CASCADE` with pragma on | FR-019, SR-009 |
| Tag schema | two tables, tag text in the association row | FR-012, FR-014, Key Entities |
| Stdlib-only proof | AST import walk against `sys.stdlib_module_names` | SC-007, SR-010 |
| Test harness | in-process `main(argv)` + `capsys`, `pythonpath = src` | Principle III, SC-002 |
