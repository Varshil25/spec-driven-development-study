# Phase 1 Data Model: Command-Line Bookmark Manager

**Feature**: `001-bookmark-cli-manager` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

Entities come from the spec's Key Entities section; the storage shape follows decisions
[D1](./research.md#d1-never-reused-ids-require-autoincrement) and
[D2](./research.md#d2-one-table-tags-stored-as-a-normalised-sorted-comma-joined-string).

## Entities

### Bookmark

One saved link; the only persisted entity.

| Field | Type (Python) | Type (SQLite) | Required | Default | Rules |
|-------|---------------|---------------|----------|---------|-------|
| `id` | `int` | `INTEGER PRIMARY KEY AUTOINCREMENT` | assigned by the tool | — | positive, unique within a store, strictly increasing, never reused (FR-008) |
| `url` | `str` | `TEXT NOT NULL` | yes | — | MUST begin with literal `http://` or `https://`, case-sensitive (FR-009); stored verbatim (FR-023) |
| `title` | `str` | `TEXT NOT NULL DEFAULT ''` | no | `''` | free text, stored verbatim (FR-010, FR-023) |
| `tags` | `list[str]` in memory | `TEXT NOT NULL DEFAULT ''` | no | `''` (empty set) | normalised set, persisted sorted and comma-joined (FR-011, FR-015) |

### Tag

Not a table. A tag is an element of a Bookmark's tag set: a non-empty string with no
surrounding whitespace and no comma. Tags have no attributes of their own, so no requirement
needs them addressable independently of the bookmark carrying them
([D2](./research.md#d2-one-table-tags-stored-as-a-normalised-sorted-comma-joined-string)).
The same label may appear on any number of bookmarks.

### Store

One SQLite file = one independent collection. Identified by the `--db PATH` argument, default
`bookmarks.db` in the current working directory (FR-002). Created on first use with no
initialisation step (FR-003); two paths never interact. The store is the unit of persistence
across invocations (FR-004).

## Schema

Applied on every invocation (idempotent), satisfying FR-003:

```sql
CREATE TABLE IF NOT EXISTS bookmarks (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    url   TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    tags  TEXT NOT NULL DEFAULT ''
);
```

No indexes: every read is a full `ORDER BY id` scan by design
([D3](./research.md#d3-filtering-and-case-insensitive-search-happen-in-python-not-in-sql)), and
`id` is already the primary key. No `UNIQUE` constraint on `url` — duplicates are explicitly
allowed (spec Assumptions, "No deduplication").

`AUTOINCREMENT` causes SQLite to maintain an internal `sqlite_sequence` row; this is what keeps
ids from being reused after a deletion, and it is never read or written by application code.

## Validation rules

Applied in this order, before the store is opened
([D4](./research.md#d4-validate-input-before-touching-the-store)):

1. **Argument shape** — handled by `argparse`: unknown command, unknown option, missing
   required argument, non-integer `delete ID`, export format outside `{csv, json}`. Failure →
   diagnostic on stderr, exit 1 ([D5](./research.md#d5-exit-codes-2-and-3-are-reserved-so-usage-errors-exit-1)).
2. **URL prefix** (`add` only) — `url.startswith(("http://", "https://"))`, literal and
   case-sensitive. Failure → diagnostic naming the URL and the expected prefixes on stderr,
   exit 2, nothing stored, store file not created (FR-009).
3. **Store reachable** — opening/initialising the SQLite file. Failure (`sqlite3.Error`,
   `OSError`) → diagnostic naming the path and the underlying problem, exit 1 (FR-006).
4. **Referenced id exists** (`delete` only) — determined by the `DELETE`'s affected-row count;
   zero rows → diagnostic naming the id, exit 3, nothing deleted (FR-018).

### Tag normalisation (FR-011)

Input is one comma-separated string. Transformation, applied on write only:

```text
"  python , , cli, python "  →  split on ","  →  strip each  →  drop empties
                             →  de-duplicate  →  sort  →  "cli,python"
```

Consequences: display order is always alphabetical (FR-015, FR-019, FR-020) with no sorting at
read time; omitted `--tags` and `--tags ","` both yield `''`, which renders as an empty TSV/CSV
field and as `[]` in JSON. Sorting is Python's default string ordering (code-point), which is
the "alphabetical" order the spec requires for ASCII tags and is deterministic for any others.

### In-memory representation

Rows are read as `sqlite3.Row` and passed to formatters as plain tuples/dicts — no model class
(Principle IV). `tags` crosses the boundary as the stored string and is split only where a
structured value is required (JSON export, tag filtering).

## State transitions

A bookmark has two states and no update path (no edit command is in scope):

```text
            add (URL valid)                     delete ID (id present)
   (none) ──────────────────────▶ stored ──────────────────────────────▶ (deleted, id retired)
      │                              │
      │ add (URL invalid) → exit 2   │ list / search / export: read-only, no transition
      ▼                              ▼
   (none, store untouched)        stored
```

- Ids of deleted bookmarks are retired permanently; the next `add` receives an id greater than
  every id ever assigned in that store (FR-008, User Story 3 scenario 3).
- Read commands never alter state, so a listing taken before and after any rejected command is
  identical (SC-007).

## Store lifecycle

| Event | Effect |
|-------|--------|
| First command against a path | file created, schema applied, command proceeds (FR-003) |
| Subsequent commands | `CREATE TABLE IF NOT EXISTS` is a no-op; data from earlier invocations is visible (FR-004) |
| Command rejected at validation step 1 or 2 | store neither created nor modified (FR-006, D4) |
| Command fails at step 3 | nothing written; diagnostic names the path |
| Concurrent access | out of scope (spec Assumptions: single user, one command at a time) |
