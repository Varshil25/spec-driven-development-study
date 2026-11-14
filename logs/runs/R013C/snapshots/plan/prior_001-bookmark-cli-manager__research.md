# Phase 0 Research: Command-Line Bookmark Manager

**Feature**: `001-bookmark-cli-manager` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

The Technical Context in [plan.md](./plan.md) contains no `NEEDS CLARIFICATION` markers: the
language, dependency policy, storage engine, test runner, package layout and every externally
visible behaviour are fixed by the specification, the user input to `/speckit-plan`, and the
project constitution. This document therefore records the design decisions that the
specification leaves to the implementer, each with the requirement that forces it and the
alternatives rejected.

---

## D1. Never-reused ids require `AUTOINCREMENT`

**Decision**: the schema declares `id INTEGER PRIMARY KEY AUTOINCREMENT`.

**Rationale**: FR-008 and User Story 3 acceptance scenario 3 require that an id is never
reused after a deletion. A plain `INTEGER PRIMARY KEY` (rowid alias) assigns `max(rowid) + 1`,
so deleting the highest-numbered bookmark makes SQLite hand the *same* id to the next insert —
a direct violation. `AUTOINCREMENT` keeps a high-water mark in the internal `sqlite_sequence`
table and never descends.

**Alternatives considered**:

- *Plain `INTEGER PRIMARY KEY`*: rejected — reuses ids after deleting the tail row.
- *Application-managed counter in a separate `meta` table*: rejected — reimplements
  `AUTOINCREMENT` in Python, adds a table and a read-modify-write per insert, and buys nothing
  (Principle IV).

---

## D2. One table; tags stored as a normalised, sorted, comma-joined string

**Decision**: a single table

```sql
CREATE TABLE IF NOT EXISTS bookmarks (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    url   TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    tags  TEXT NOT NULL DEFAULT ''
);
```

where `tags` holds the bookmark's tags already trimmed, de-duplicated, sorted and joined with
`,` — exactly the text FR-015 and FR-019 must print.

**Rationale**: the only tag operations in scope are "store a set" (FR-011), "print
alphabetically" (FR-015, FR-019, FR-020) and "select bookmarks carrying tag T exactly"
(FR-013). No requirement asks to list all tags, rename a tag, count usage, or query tags
independently of bookmarks. Normalising on write makes the stored value the display value, so
listing and CSV export need no per-row computation and JSON needs only a `split`. Principle IV
("the smallest design that satisfies the specification", "prefer one module over several until
a concrete reason to split appears" — the same reasoning applies to tables) forbids the
relational structure a future tag feature *might* want.

Tag text cannot contain a comma, because the only input path is a comma-separated list
(FR-011), so the joined form is unambiguous.

**Alternatives considered**:

- *Normalised `tags` + `bookmark_tags` join tables*: rejected — three tables, an insert-or-get
  path per tag, and a `GROUP_CONCAT` with an `ORDER BY` in every read query, all to support
  queries no requirement asks for.
- *JSON array in a TEXT column via the `json1` extension*: rejected — more machinery than a
  comma-join for the same result, and relies on an extension's availability.
- *Storing tags in the order supplied*: rejected — FR-015/FR-019/FR-020 all require
  alphabetical presentation, so every reader would have to re-sort.

---

## D3. Filtering and case-insensitive search happen in Python, not in SQL

**Decision**: every read command issues one query — `SELECT id, url, title, tags FROM bookmarks
ORDER BY id` — and `list --tag` / `search` filter the resulting rows in Python
(`tag in row.tags.split(",")`, `needle.casefold() in (title + url).casefold()`).

**Rationale**:

1. *Correctness over SQL `LIKE`*: a `LIKE '%' || ? || '%'` search would silently treat `%` and
   `_` in the user's search text as wildcards unless every call escapes them with an `ESCAPE`
   clause. A quiet wrong answer is the failure mode Principle II names as the worst possible
   outcome. `str.casefold` has no metacharacters.
2. *Correct exact tag matching*: FR-013 requires a full, not substring, match. In SQL that
   means the delimiter trick `(',' || tags || ',') LIKE '%,' || ? || ',%'` — subtle, and again
   wildcard-unsafe. `in row.tags.split(",")` is self-evidently exact.
3. *Case folding*: SQLite's `lower()`/`LIKE` fold ASCII only. Python's `casefold()` folds
   Unicode, which exceeds the spec's "ASCII letters at minimum" assumption at no cost.
4. *Performance is not a constraint here*: SC-005 allows one second for 1,000 bookmarks.
   Selecting 1,000 short rows and scanning them in Python is on the order of a millisecond, and
   the store is a single-user local file.

**Alternatives considered**:

- *`WHERE` clauses with `LIKE`/`instr` and an index*: rejected — the wildcard-escaping and
  delimiter-matching subtleties above are real defect sources, and the performance they buy is
  three orders of magnitude beyond what SC-005 asks for. Revisit only if a requirement
  appears for collections large enough to matter.
- *SQLite FTS5*: rejected outright — a search engine for a substring match over a list that
  fits in memory.

---

## D4. Validate input before touching the store

**Decision**: `main` parses arguments and validates the URL prefix *before* opening a
connection. The store file is created only by a command that has already passed validation.

**Rationale**: FR-006 requires a failed command to leave the store unchanged, and the "store
cannot be opened or created" edge case says no partial store is left behind. `sqlite3.connect`
creates a zero-byte file eagerly, so connecting first and validating second would leave a new
`bookmarks.db` behind after an `add` rejected under FR-009 — observably a change. Validating
first makes "exit 2, nothing happened" literally true.

**Alternatives considered**:

- *Connect first, validate inside the command*: rejected — creates the store on a rejected
  `add` (see above).
- *Create the file, then unlink it on failure*: rejected — a delete path that can itself fail,
  guarding against a situation that correct ordering simply avoids.

---

## D5. Exit codes: 2 and 3 are reserved, so usage errors exit 1

**Decision**: a thin `ArgumentParser` subclass overrides `error()` to print the message to
stderr and exit **1**. Exit status meanings:

| Status | Meaning | Source |
|--------|---------|--------|
| 0 | requested work completed | FR-005 |
| 1 | usage error, unknown export format, store cannot be opened/read | FR-006, FR-021 |
| 2 | URL rejected by the `http://`/`https://` prefix check | FR-009 |
| 3 | `delete ID` for an id not in the store | FR-018 |

**Rationale**: `argparse` exits **2** on any usage error by default, which would make status 2
mean both "bad URL" and "you mistyped the command line". The spec's assumption that statuses
other than 2 and 3 are free for other failures only holds if 2 keeps its single documented
meaning, and SC-003 asks for the documented status in every case. The override is three lines
and is forced by FR-009 — the kind of justification Principle IV demands.

**Alternatives considered**:

- *Accept `argparse`'s 2 for usage errors*: not strictly a requirement violation (FR-006 only
  demands non-zero), but it makes exit 2 ambiguous for any caller scripting the tool, which is
  what the documented status table exists to prevent.
- *A distinct status per failure class (4, 5, 6 …)*: rejected — the spec fixes only 2 and 3;
  inventing more codes is speculative interface surface (Principle IV).

---

## D6. Standard-library tools, one per output format

**Decision**:

| Concern | Tool | Notes |
|---------|------|-------|
| Argument parsing | `argparse` | one top-level parser with `--db`, five subparsers |
| Storage | `sqlite3` | stdlib, satisfies "SQLite database file" |
| Listing / search lines | `str.join` with `"\t"` | FR-015; no escaping is defined for TSV |
| CSV export | `csv.writer(sys.stdout, lineterminator="\n")` | FR-019 quoting comes free |
| JSON export | `json.dump(..., ensure_ascii=False, indent=2)` | FR-020 |

**Rationale**: all four modules are standard library (Principle I). `csv.writer` gives
RFC-4180 quoting for values containing commas, quotes or newlines, which FR-019 requires and
which hand-rolled joining would get wrong. `lineterminator="\n"` overrides the module default
`\r\n`; the spec's CSV assumption permits either, and `\n` is what the surrounding POSIX
tooling expects. `ensure_ascii=False` keeps non-ASCII text literal per SC-006 (escaped output
would also parse correctly, but literal output is greppable).

The tab-separated listing is deliberately *not* produced with `csv.writer(delimiter="\t")`:
the spec's assumption section states the TSV format defines no escaping, and a CSV writer
would add quoting that the documented format does not have.

**Alternatives considered**:

- *`click`/`typer` for the CLI, `tabulate` for output*: rejected — third-party runtime
  dependencies, forbidden by Principle I without a constitution amendment.
- *Hand-written CSV quoting*: rejected — `csv` is in the standard library and already correct.

---

## D7. Deterministic output encoding

**Decision**: `main` calls `sys.stdout.reconfigure(encoding="utf-8")` (and the same for
stderr) before producing output.

**Rationale**: FR-023 and SC-006 require non-ASCII titles, URLs and tags to be reproduced
unchanged in every output format, for 100% of bookmarks. Without this, the output encoding is
the process locale's: under a `C`/`POSIX` locale that can be ASCII, and printing a stored
non-ASCII title then raises `UnicodeEncodeError` — a crash that depends on the environment
rather than on the data. Pinning UTF-8 makes the data-fidelity requirements hold everywhere.
This is a one-line explicit choice, not a silent fallback: no data is substituted or dropped,
and malformed output is never produced in place of an error.

**Alternatives considered**:

- *Leave the locale's encoding in place*: rejected — makes SC-006 conditional on the
  environment.
- *`errors="replace"`*: rejected outright — that is exactly the "coerced default that masks
  bad input" Principle II forbids; it would corrupt text silently.

---

## D8. Connection lifecycle: open, commit explicitly, close in `finally`

**Decision**: one connection per invocation, opened after validation, schema applied with
`CREATE TABLE IF NOT EXISTS`, writes committed explicitly, closed in a `finally` block.
`sqlite3.Error` and `OSError` raised while opening or using the store are caught, re-reported
as a diagnostic naming the store path and the underlying problem, and converted to exit 1.

**Rationale**: FR-003 forbids a separate initialisation step, so the schema statement runs on
every invocation (it is a no-op after the first). FR-006 requires a named diagnostic on
stderr for a store that cannot be opened; Principle II permits catching an exception precisely
to "wrap it with added context" or "convert it into an explicit error result", which is what
this does — the path and the original message both appear. `with sqlite3.connect(...)` is
*not* used as the sole guard because that context manager commits or rolls back without
closing the connection; the explicit `finally: conn.close()` is what releases the file.

**Alternatives considered**:

- *`isolation_level=None` (autocommit)*: rejected — each command performs at most one write,
  so an explicit `commit()` is no more code and keeps the rejected-command path trivially
  write-free (FR-006, SC-007).
- *A connection pool or module-level cached connection*: rejected — one process, one command;
  module-level mutable state is forbidden by the constitution's "No hidden state" constraint.

---

## D9. Tests: `pytest` with `pythonpath = ["src"]` in `pyproject.toml`

**Decision**: a single `pyproject.toml` at the repository root carries
`[tool.pytest.ini_options]` with `pythonpath = ["src"]` and `testpaths = ["tests"]`. Tests run
as `pytest` from the repository root with no further setup and no install step.

**Rationale**: the constitution requires tests discoverable "from the repository root without
configuration beyond a single config file", and Principle I forbids an install step for
runtime code. `pythonpath` is a built-in `pytest` ini option (pytest ≥ 7; 9.1.1 is installed),
so it needs no plugin. The package stays importable as `bookmarks` from `src/`, matching the
spec's "runnable as `python -m bookmarks` when `src/` is on `PYTHONPATH`".

End-to-end tests invoke the real entry point in a child process
(`subprocess.run([sys.executable, "-m", "bookmarks", ...], env={"PYTHONPATH": "src"})`) so
that exit statuses, stdout/stderr separation and cross-invocation persistence (FR-004, FR-005,
FR-009, FR-018) are observed exactly as a user would see them, against a `tmp_path` store.

**Alternatives considered**:

- *`pip install -e .` with a console-script entry point*: rejected — introduces a packaging
  install step the spec does not ask for, and the spec fixes the invocation as
  `python -m bookmarks`.
- *`sys.path` manipulation inside `conftest.py`*: rejected — the same effect by a less
  declarative route; the ini option exists for this.
- *Calling `main()` in-process only*: kept as the fast path for most assertions, but not
  alone — only a subprocess proves the real `python -m bookmarks` exit status, which SC-003
  measures.

---

## Resolved unknowns

| Item | Resolution | Source |
|------|-----------|--------|
| Language version | Python 3.11+ (3.13.17 available locally) | user input, constitution |
| Runtime dependencies | none; `sqlite3`, `argparse`, `csv`, `json` only | Principle I |
| Dev dependency | `pytest` only | Principle I/III, user input |
| Storage engine | SQLite file at `--db PATH`, default `./bookmarks.db` | FR-002 |
| Id generation | `INTEGER PRIMARY KEY AUTOINCREMENT` | D1 |
| Tag storage | sorted comma-joined TEXT column | D2 |
| Usage-error exit code | 1 (2 and 3 reserved) | D5 |
| Test invocation | `pytest` from repo root, `pythonpath = ["src"]` | D9 |
