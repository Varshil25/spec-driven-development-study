# Phase 1 Data Model: Command-Line Bookmark Manager

**Feature**: `001-bookmark-manager-cli` | **Date**: 2026-11-20 | **Plan**: [plan.md](./plan.md)

Entities are taken from the spec's Key Entities section; validation rules are taken from the
functional and security requirements and are cited inline. Design rationale for the chosen
shape is in [research.md](./research.md) (decisions R1, R7, R8).

## Entities

### Bookmark

One saved link.

| Field | Type | Rules |
|---|---|---|
| `id` | integer | Unique within the collection. Starts at 1, strictly increasing, **never reused** after deletion (FR-007). Assigned by the store, never by the caller. Range 1 … 2^63−1. |
| `url` | text | Required. MUST begin with the exact lowercase prefix `http://` or `https://` (FR-008, SR-002). At most 8192 characters (SR-006). No other restriction — no reachability or DNS check (FR-011). Stored verbatim, including SQL metacharacters (SR-001). |
| `title` | text | Optional; empty string when omitted (FR-009). At most 4096 characters (SR-006). Stored verbatim, including tabs, newlines, quotes, commas and non-ASCII characters (spec Assumptions, FR-025). |
| `tags` | set of Tag | Zero or more distinct tags (FR-010, FR-012). Unordered in storage; alphabetical order is imposed only on display and export (FR-017, FR-023, FR-024). |

**Ordering**: bookmarks are ordered by ascending `id` everywhere they are presented — `list`,
`list --tag`, `search`, `export --format csv`, `export --format json` (FR-013, FR-014,
FR-015, FR-023, FR-024).

**State transitions**: a bookmark has two states, *absent* and *stored*. `add` moves absent →
stored and allocates the id; `delete` moves stored → absent and retires the id permanently.
There is no update or edit transition (spec Scope boundaries), so a stored bookmark's `url`,
`title` and `tags` are immutable for its lifetime.

```text
            add (valid URL)                 delete ID
  absent ──────────────────────▶ stored ──────────────────────▶ absent
     │                                                             │
     │  add (invalid URL / oversized input) → stays absent,        │  id never reissued
     └──  exit 2, nothing written (FR-008, SR-006, SR-009)         └──  (FR-007)
```

A rejected `add` performs no state transition at all: no bookmark, no tag association, and no
identifier is consumed (FR-008). A `delete` naming an absent id performs no transition and
exits 3 (FR-021).

### Tag

A short label attached to a bookmark.

| Field | Type | Rules |
|---|---|---|
| `text` | text | Non-empty after trimming. At most 128 characters; at most 64 tags per bookmark; the whole `--tags` string at most 4096 characters (SR-006). Matched exactly and case-sensitively by `list --tag` (FR-014, spec Assumptions). Stored as supplied after trimming, not case-folded. |

**Parsing rule (FR-012)** — the single normalisation applied to `--tags`:

1. Split the raw string on `,`.
2. Strip leading and trailing whitespace from each entry.
3. Discard entries that are then empty.
4. Keep each distinct entry once.

Consequences, each of which is a unit-test case: `""` → `{}`; `","` → `{}`; `"a,,b"` →
`{a, b}`; `" a , b "` → `{a, b}`; `"a,a"` → `{a}`; `"Python,python"` → `{Python, python}`
(two distinct tags — matching is case-sensitive).

**Relationship**: many-to-many with Bookmark. A bookmark holds a *set* of tags (no duplicates,
no order); a tag's text may appear on any number of bookmarks. Deleting a bookmark removes
that bookmark's tag associations and nothing else (FR-019, FR-020).

**Display order**: ascending code-point order of the tag text, joined with `,` (FR-017,
FR-023, FR-024). Because this is code-point order rather than locale collation, uppercase
sorts before lowercase: `{python, Docs}` renders as `Docs,python` (spec Assumptions).

### Collection

The whole set of bookmarks in one database file, identified by its path.

| Field | Type | Rules |
|---|---|---|
| `path` | file path | From `--db PATH`, defaulting to `bookmarks.db` in the current working directory (FR-002). Created with mode `0600` if absent (FR-003, SR-005). A path whose parent directory does not exist, or which cannot be opened, is an error with exit status 1 — never a silent fallback to the default (spec Edge Cases). |

Two different paths are two independent collections that never interact; identifier sequences
are per collection. A collection that exists but holds no bookmarks is valid and yields empty
`list`/`search` output and header-only / empty-array exports (FR-018, FR-027). A file that
exists but is not a readable SQLite database is an error with exit status 1, never an empty
collection (spec Edge Cases).

## Physical schema

Applied once, inside a transaction, when the database is first created or opened
(`CREATE TABLE IF NOT EXISTS` makes opening an existing collection a no-op).

```sql
PRAGMA foreign_keys = ON;          -- per connection; required for the CASCADE below (R7)

CREATE TABLE IF NOT EXISTS bookmarks (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,   -- never reuses an id (FR-007, R1)
    url   TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT ''             -- absent title is '' , not NULL (FR-009)
);

CREATE TABLE IF NOT EXISTS bookmark_tags (
    bookmark_id INTEGER NOT NULL REFERENCES bookmarks(id) ON DELETE CASCADE,
    tag         TEXT NOT NULL,
    PRIMARY KEY (bookmark_id, tag)             -- enforces the per-bookmark set (FR-012)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_bookmark_tags_tag ON bookmark_tags(tag);
```

Schema notes:

- `AUTOINCREMENT` creates SQLite's internal `sqlite_sequence` table. That is engine-managed
  state inside the same file, not additional application state, and it is what makes FR-007
  hold across deletions of the highest id.
- `title TEXT NOT NULL DEFAULT ''` keeps `NULL` out of the data entirely, so formatting code
  has one case to handle instead of two.
- `WITHOUT ROWID` on the association table stores rows directly in the primary-key index —
  one b-tree instead of two for a table that is only ever reached by its key.
- `idx_bookmark_tags_tag` serves `list --tag TAG` (FR-014); the primary key serves the
  `(bookmark_id, tag)`-ordered join used by every read (R4).
- No `UNIQUE` constraint on `url`: duplicate URLs are explicitly permitted and produce
  distinct bookmarks (spec Assumptions).
- Journal mode is left at SQLite's default (`delete`), never WAL, so no `-wal`/`-shm` file
  survives a command (SR-011, R2).

## Queries

All statements are fixed strings with `?`/`:name` placeholders; no SQL is ever assembled from
user text (SR-001). Reads return a cursor that is iterated lazily (SR-007).

| Operation | Statement shape |
|---|---|
| `add` | `INSERT INTO bookmarks(url, title) VALUES (?, ?)` then one `INSERT INTO bookmark_tags(bookmark_id, tag) VALUES (?, ?)` per tag — all inside one transaction (SR-009). The new id is `cursor.lastrowid`. |
| `list` | `SELECT b.id, b.url, b.title, t.tag FROM bookmarks b LEFT JOIN bookmark_tags t ON t.bookmark_id = b.id ORDER BY b.id, t.tag` |
| `list --tag` | the `list` statement plus `WHERE b.id IN (SELECT bookmark_id FROM bookmark_tags WHERE tag = ?)` — the filter selects the bookmarks, the join still returns *all* of each matched bookmark's tags for display (FR-014 + FR-017) |
| `search` | the `list` statement plus `WHERE instr(lower(b.title), lower(:text)) > 0 OR instr(lower(b.url), lower(:text)) > 0` (FR-015, FR-016, SR-004) |
| `delete` | `DELETE FROM bookmarks WHERE id = ?`; associations go with it via `ON DELETE CASCADE`. `cursor.rowcount == 0` ⇒ exit 3, transaction commits nothing (FR-021) |
| `export` | the `list` statement, unfiltered — the same row stream feeds both formats (FR-023, FR-024) |

**Row-to-bookmark grouping.** Every read uses the one `LEFT JOIN` above and yields a
`Bookmark(id, url, title, tags)` as soon as the cursor's `id` changes, holding at most one
bookmark's tags in memory. A tagless bookmark arrives as a single row with `tag IS NULL` and
yields an empty tag set, which renders as the empty fourth field FR-017 requires. Because the
engine supplies `ORDER BY b.id, t.tag`, both the bookmark order and the tag order are already
correct when they reach the formatter — no Python-side sorting of the collection is needed,
which is what keeps memory flat (R4).
