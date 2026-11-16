# Phase 0 Research: Bookmark Manager CLI

**Feature**: `001-bookmark-manager-cli` | **Date**: 2026-11-16

**Input**: [spec.md](./spec.md), [constitution](../../.specify/memory/constitution.md)

All Technical Context unknowns are resolved below. Every decision was checked against the
constitution's four principles (Standard Library Only, Fail Loudly, Every Requirement Is
Testable, Simplicity). Findings marked **verified** were confirmed by running the code on
Python 3.13.17 / SQLite 3.45.1 during this phase.

---

## R-001: Python version floor and standard-library surface

**Decision**: Target Python 3.11 as the declared minimum. Runtime imports are limited to
`argparse`, `sqlite3`, `csv`, `json`, `sys`, `pathlib` (or `os.path`). No third-party runtime
import anywhere.

**Rationale**: FR-025 states 3.11+ and standard library only; the user input confirms it. Every
module needed is in the standard library, so Principle I is satisfied without exception. Nothing
in the design needs a feature newer than 3.11, so the floor can stay at the specified version
even though development happens on 3.13.

**Alternatives considered**:

- *Targeting 3.13 (the installed interpreter)*: rejected — narrows supported platforms for no
  gain; no required feature is newer than 3.11.
- *Adding `click`/`typer` for the CLI*: rejected — forbidden by Principle I, and `argparse`
  already produces the exact exit status the spec requires (see R-003).

---

## R-002: Detecting an unusable store without ever modifying it (FR-003a, SC-009)

**Decision**: Three-step open sequence.

1. If the target file **does not exist**, open with the SQLite URI `file:<path>?mode=rwc` to
   create it, then run `CREATE TABLE IF NOT EXISTS` for both tables.
2. If the target file **does exist**, open with `file:<path>?mode=rw` (never `rwc`, so no file
   is created on a typo) and immediately run
   `SELECT name FROM sqlite_master WHERE type='table'`:
   - raises `sqlite3.DatabaseError` → the file is not a SQLite database → exit 1;
   - returns a table set that contains neither `bookmarks` nor `tags` **and is non-empty** → a
     database belonging to another program → exit 1;
   - returns an empty table set (a 0-byte or freshly created empty database) → initialise the
     schema and continue;
   - contains our tables → use as-is.
3. `sqlite3.OperationalError` from the connect/first-query step (missing parent directory,
   permission denied) → exit 1.

Percent-encode the path before building the URI so that a path containing `?` or `#` is not
misread as URI syntax.

**Verified**:

- `sqlite3.connect("file:text.db?mode=rw", uri=True)` on a plain text file **succeeds**; the
  error surfaces only on the first query, as `DatabaseError: file is not a database`. So the
  validation query is mandatory — connecting alone proves nothing.
- The text file was byte-for-byte identical (same SHA-256, same size) after the failed attempt,
  satisfying SC-009.
- `mode=rw` against a missing parent directory raises `OperationalError: unable to open database
  file` and creates **no** directory and **no** file.
- `mode=rw` against an absent file raises the same error and does **not** create the file.

**Rationale**: `mode=rw` is the only way to ask SQLite to open without creating. Deferring the
verdict to a read-only query means the failure path never writes. This is Fail Loudly applied to
storage: no repair, no re-initialisation, no truncation — just a named path, a named reason, and
status 1.

**Alternatives considered**:

- *Reading the 16-byte `SQLite format 3\0` header magic ourselves*: rejected — duplicates logic
  SQLite already has, and would accept a corrupt file whose header happens to be right.
- *`mode=ro` for read-only commands (`list`, `search`, `export`)*: rejected — it would make the
  same store usable for some commands and not others, and a brand-new store needs write access
  to be created at all. One uniform `rw` requirement is simpler and matches FR-003a's wording
  ("the required read or write access"). Documented as a deliberate consequence: a read-only
  file fails with status 1 even for `list`.
- *`sqlite3.connect(path)` plainly*: rejected — creates the file as a side effect, which breaks
  FR-003a's "MUST create no new file".

**Test-environment caveat**: a permission-denied test (`chmod 000`) does **not** fail when the
suite runs as `root`, which is the case in this environment — root bypasses the mode bits. The
permission case must be covered by a test that skips itself when `os.geteuid() == 0`, so the
suite stays honest instead of silently passing. The missing-parent-directory and
not-a-database cases have no such caveat and carry the weight of SC-009.

---

## R-003: Mapping usage mistakes to exit status 2 (FR-024)

**Decision**: Let `argparse` handle every usage mistake. Its default `error()` already writes a
specific diagnostic to stderr and exits **2**, which is exactly the status FR-024 demands. Wire
it up so that each usage mistake in the spec falls out of the parser declaration:

| Spec case (FR-024)        | Parser declaration                                     |
| ------------------------- | ------------------------------------------------------ |
| unknown command           | `add_subparsers(dest="command", required=True)`         |
| missing required argument | positional arguments (`url`, `text`, `id`)              |
| non-numeric `delete` id   | `type=int` on the `id` positional                       |
| unsupported export format | `--format`, `required=True`, `choices=["csv", "json"]`  |

The rejected-URL case (FR-007) is a domain rule, not a grammar rule, so it is raised by the
application code and mapped to status 2 by the same table of codes.

**Verified** on Python 3.13.17 — observed exit statuses and last stderr line:

```text
(no args)              -> 2  error: the following arguments are required: command
bogus                  -> 2  error: argument command: invalid choice: 'bogus' ...
delete abc             -> 2  error: argument id: invalid int value: 'abc'
export --format xml    -> 2  error: argument --format: invalid choice: 'xml' ...
add                    -> 2  error: the following arguments are required: url
--help                 -> 0
```

**Rationale**: Zero hand-written validation for four of the five usage cases, and the messages
name both what was invalid and what was expected — Principle II satisfied by the library's own
output. Principle IV says do not write code a requirement does not demand; argparse's default
already *is* the requirement.

**Alternatives considered**:

- *Custom `ArgumentParser.error` override*: rejected — it would have to re-implement status 2,
  which is already the default.
- *Hand-rolled `sys.argv` parsing*: rejected — more code, worse messages, no `--help`.
- *Validating the id with a manual `int()` call*: rejected — `type=int` gets status 2 and a
  precise message for free, and keeps status 3 strictly reserved for the well-formed-but-absent
  identifier (the spec is emphatic about this distinction).

**Note**: `argparse`'s default `prog` under `python -m bookmarks` is the literal string
`__main__.py` (**verified**), which would make every diagnostic misname the tool. `prog` must be
set explicitly to `python -m bookmarks`.

---

## R-004: Identifiers that are never reused (FR-006)

**Decision**: `id INTEGER PRIMARY KEY AUTOINCREMENT`.

**Rationale**: A bare `INTEGER PRIMARY KEY` is an alias for SQLite's `rowid`, and its default
allocation is `max(rowid) + 1` — so deleting the highest row **reuses** that identifier on the
next insert. That is precisely the behaviour acceptance scenario 4 of User Story 3 forbids.
`AUTOINCREMENT` makes SQLite keep a high-water mark in the internal `sqlite_sequence` table, so
an issued identifier is never issued again. Identifiers also start at 1 in a fresh database, as
FR-006 requires.

**Alternatives considered**:

- *Bare `INTEGER PRIMARY KEY`*: rejected — reuses identifiers after deleting the maximum.
- *Application-managed counter in a separate table*: rejected — reimplements `AUTOINCREMENT`
  with more moving parts and a race the single-user assumption does not even need solved.

---

## R-005: Case-insensitive matching for `search` and `--tag` (FR-012, FR-013)

**Decision**: Do the `search TEXT` match in **Python**, not SQL: read the candidate rows and keep
those where `text.lower()` is a substring of `title.lower()` or `url.lower()`. The `--tag TAG`
filter stays in SQL as plain `=` equality, because stored tags are already normalised to lower
case (FR-010) and the filter value is trimmed and lower-cased with the same function before the
query.

**Rationale**: Two correctness traps make SQL `LIKE` the wrong tool for `search`:

- SQLite's `LIKE` and `lower()` are **ASCII-only** by default, so a non-ASCII title would not
  fold case — a silent wrong answer, the defect Principle II ranks highest.
- `LIKE` treats `%` and `_` as wildcards, so searching for `100%` or `a_b` would match rows it
  must not. Correct use needs `ESCAPE` plus manual escaping of the user's text — more code and a
  classic place to get it subtly wrong.

Python's `str.lower()` is Unicode-aware and substring containment has no metacharacters, so the
Python-side filter is both shorter and more correct. SC-007 allows a full second for 1,000
bookmarks; scanning 1,000 rows in Python is microseconds, so there is no cost to pay.

Whole-tag matching (FR-012: `py` must not match `python`) comes free from SQL `=`.

**Alternatives considered**:

- *`WHERE lower(title) LIKE '%'||lower(?)||'%'`*: rejected — ASCII-only folding and unescaped
  wildcards, as above.
- *`LIKE ... ESCAPE '\'` with manual escaping*: rejected — fixes the wildcard trap but not the
  Unicode one, and adds code.
- *Registering a Python `lower` via `create_function`*: rejected — pushes Unicode-correct folding
  into SQL, but still needs wildcard escaping and adds indirection for no benefit over filtering
  in Python.
- *`COLLATE NOCASE`*: rejected — also ASCII-only, same silent-wrong-answer risk.

---

## R-006: Tag storage — join table versus a single delimited column

**Decision**: Two tables. `bookmarks(id, url, title)` and `tags(bookmark_id, tag)` with a
composite primary key `(bookmark_id, tag)` and
`FOREIGN KEY(bookmark_id) REFERENCES bookmarks(id) ON DELETE CASCADE`. Enable
`PRAGMA foreign_keys = ON` on every connection, since SQLite leaves foreign keys off by default.

**Rationale**: FR-012 requires whole-tag matching that a `py`/`python` substring must not satisfy.
With a join table that is the single character `=`; with a delimited column it becomes
`LIKE '%,' || tag || ',%'` over a sentinel-padded string — a construction that is easy to get
wrong and hard to read, and that re-introduces the wildcard-escaping trap from R-005. The
composite primary key also enforces FR-010's "each distinct tag at most once per bookmark" at
the storage layer rather than trusting application code. `ON DELETE CASCADE` gives FR-016
("remove the bookmark together with its tags") in one declaration instead of two `DELETE`
statements that could drift apart.

This is the simplest design that satisfies the requirements, which is what Principle IV asks for
— not the fewest tables in the abstract. Two tables is also the plain reading of the spec, which
names Bookmark and Tag as separate key entities.

**Alternatives considered**:

- *`bookmarks.tags` as a comma-joined string*: rejected — one fewer table, but makes the
  whole-tag filter a fragile `LIKE` pattern and moves the uniqueness invariant into application
  code. Fewer tables, more moving parts in the part that matters.
- *A shared `tags(id, name)` dictionary table plus a `bookmark_tags` link table*: rejected —
  three tables and a join to resolve a short string. Nothing in the spec needs tag identity,
  renaming, or per-tag metadata; this is the speculative generality Principle IV forbids.

**Indexes**: none beyond the two primary keys. An index on `tags(tag)` would speed the `--tag`
filter, but SC-007's budget is one second for 1,000 bookmarks and the primary-key index on
`(bookmark_id, tag)` already orders the data by bookmark. Adding an index no requirement demands
is exactly the scope Principle IV calls a defect. Revisit only if a measured test fails.

---

## R-007: UTF-8 output regardless of locale, and LF-only CSV (FR-019a, FR-023a)

**Decision**: Reconfigure both streams once, at the top of the entry point:

```python
sys.stdout.reconfigure(encoding="utf-8", newline="")
sys.stderr.reconfigure(encoding="utf-8")
```

Then write CSV with `csv.writer(sys.stdout, lineterminator="\n")` and JSON with
`json.dumps(rows, indent=2, ensure_ascii=False)` followed by a single `"\n"`.

**Rationale**: `reconfigure(encoding="utf-8")` (`io.TextIOWrapper`, 3.7+) makes output UTF-8 even
when the machine's locale is `C`/ASCII, which FR-023a requires and which would otherwise raise
`UnicodeEncodeError` on a non-ASCII title. `newline=""` disables newline translation on stdout,
which is what the `csv` module documents as the correct setup and which keeps a line break
*inside* a quoted field intact on every platform (FR-019a). `lineterminator="\n"` overrides
`csv`'s RFC-4180 default of `\r\n`, as the clarification session decided.

**Verified**: with that configuration, the writer emits
`id,url,title,tags\n1,https://x,"He said ""hi"", then\nleft","a,b"\n` — no `\r\n` anywhere,
quoting applied exactly where needed, and `csv.reader` recovers `He said "hi", then\nleft`
unchanged (FR-019, SC-006). `json.dumps(..., indent=2, ensure_ascii=False)` emits `café — ü`
literally rather than as `\uXXXX` escapes (FR-020a).

**Alternatives considered**:

- *`PYTHONIOENCODING` or wrapping `sys.stdout.buffer` by hand*: rejected — the environment
  variable is outside the program's control (and Principle "Configuration" forbids implicit
  environment-based behaviour switches), and a manual `TextIOWrapper` is more code for the same
  effect.
- *Building CSV rows with manual quoting*: rejected — the `csv` module's quoting is correct and
  round-trip tested; hand-rolled quoting is a known source of data-corrupting bugs (SC-006).
- *`json.dump` straight to the stream*: acceptable, but `dumps` plus one explicit write makes the
  "exactly one trailing newline" guarantee of FR-020a visible in a single line.

---

## R-008: Error reporting and the exit-status map (FR-024)

**Decision**: One exception type carrying its own status —
`BookmarkError(message, status)` — raised where the problem is detected (rejected URL → 2,
unusable store → 1, missing identifier → 3). The entry point has exactly one handler: it writes
`f"bookmarks: {message}"` to stderr and returns `status`. Usage mistakes never reach it, because
`argparse` has already exited 2 (R-003).

**Rationale**: Principle II forbids broad handlers that swallow errors and permits catching only
to re-raise or to convert into a clearer diagnostic — which is exactly this handler's job. One
handler at one place keeps the status map auditable against FR-024 by reading a single function.
Results are written to stdout only after the work succeeds, so a failing command cannot emit
partial output (FR-023).

**Alternatives considered**:

- *A distinct exception class per status*: rejected — three near-empty classes where one field
  does the job.
- *Returning status codes up through the call chain*: rejected — every intermediate function
  would have to check and forward, and a forgotten check becomes a silent success.
- *Catching `sqlite3.Error` broadly at the top*: rejected — would convert unexpected database
  faults into one of the four documented statuses and hide genuine bugs. Only the specific,
  expected store-open failures of R-002 are converted; anything else propagates and crashes
  loudly, which Principle II prefers over a wrong answer.

---

## R-009: Running `python -m bookmarks` and importing it from tests (FR-026, FR-027)

**Decision**: Code lives in `src/bookmarks/`, with `__main__.py` as the `-m` entry point. Tests
reach the package through pytest's built-in `pythonpath` ini option, declared in
`pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Tests that exercise the real contract (exit status, stream separation) invoke the CLI as a
subprocess: `subprocess.run([sys.executable, "-m", "bookmarks", ...], env={**os.environ,
"PYTHONPATH": "src"}, capture_output=True)`.

**Rationale**: `pythonpath` (pytest 7.0+; 9.1.1 is installed) replaces the usual
`sys.path.insert` boilerplate in `conftest.py` with one declarative line, and needs no install
step or packaging metadata — so `python -m bookmarks` with `src` on `PYTHONPATH` stays the real
invocation, exactly as FR-026 words it. Subprocess tests are the only way to assert FR-022/FR-024
exit statuses and FR-023's stdout/stderr split honestly; asserting on a function's return value
would test a stand-in rather than the delivered contract.

**Alternatives considered**:

- *`pip install -e .`*: rejected — adds packaging and an install step the spec does not ask for,
  and would let tests pass against an installed copy that differs from the tree.
- *`sys.path` manipulation in `conftest.py`*: rejected — works, but `pythonpath` is the supported
  mechanism and one line shorter.
- *Testing only via in-process `main(argv)` calls*: rejected — cannot observe a real process exit
  status; Principle III requires tests that assert the status itself.

**Performance test note**: SC-007 and SC-002 use a 1,000-bookmark store. Seeding it with 1,000
subprocess calls would cost minutes, so the fixture seeds the store through one direct
`store`-module call (or a single multi-row insert) and then measures the user-visible commands
via subprocess. The contract under test is the command's response time, not the seeding route.

---

## R-010: Module layout

**Decision**: Four files under `src/bookmarks/`:

| File          | Responsibility                                                          |
| ------------- | ----------------------------------------------------------------------- |
| `__init__.py` | empty marker                                                            |
| `__main__.py` | `sys.exit(main(sys.argv[1:]))` — the `-m` entry point and nothing else  |
| `cli.py`      | argparse grammar, stream setup, command dispatch, output formatting, the single error handler |
| `store.py`    | open/validate the database, schema, tag normalisation, URL check, CRUD   |

**Rationale**: Principle IV asks for a flat layout and for packages only when module count makes
a flat layout unnavigable. Four files is navigable. The split is along the one seam that pays for
itself: data rules and SQL on one side, argument grammar and presentation on the other — which
also lets `store.py` be exercised directly by the seeding fixture in R-009. A separate
`formats.py` was considered and rejected: TSV/CSV/JSON rendering is presentation, it is three
short functions, and splitting it would add a file without removing any complexity.

**Alternatives considered**:

- *Single `__main__.py` holding everything*: rejected — the seeding fixture and unit-level tag
  tests would have to import `__main__`, re-running the entry-point module.
- *`models/`, `services/`, `cli/` package tree (the plan template's default)*: rejected outright
  by Principle IV — subpackages for four modules, and an abstraction layer no requirement
  demands.

---

## Resolved unknowns summary

| Unknown from Technical Context | Resolution |
| ------------------------------ | ---------- |
| Language/version floor         | Python 3.11+, developed on 3.13.17 (R-001) |
| Primary dependencies           | Standard library only: `argparse`, `sqlite3`, `csv`, `json`, `sys` (R-001) |
| Storage engine and schema      | SQLite, two tables, `AUTOINCREMENT` ids (R-004, R-006) |
| Unusable-store detection       | `mode=rw` URI plus a read-only validation query (R-002) |
| Usage-mistake exit status      | `argparse` default, already 2 (R-003) |
| Case-insensitive matching      | Python-side for `search`, SQL `=` for `--tag` (R-005) |
| Encoding and line endings      | `reconfigure(encoding="utf-8", newline="")`, `lineterminator="\n"` (R-007) |
| Testing approach               | pytest, `pythonpath = ["src"]`, subprocess for contract tests (R-009) |
| Module layout                  | Four flat modules (R-010) |

No NEEDS CLARIFICATION items remain.
