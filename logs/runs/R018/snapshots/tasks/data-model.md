# Phase 1 Data Model: Bookmark Manager CLI

**Feature**: `001-bookmark-manager-cli` | **Date**: 2026-11-16

Derived from the Key Entities and Functional Requirements in [spec.md](./spec.md); storage
decisions are justified in [research.md](./research.md) (R-004, R-006).

---

## Entities

### Bookmark

One saved web address. Identified by an integer that is unique within a store and never reused.

| Field   | Type               | Required | Notes |
| ------- | ------------------ | -------- | ----- |
| `id`    | integer            | yes      | Assigned by the store, starts at 1, strictly increasing, never reused (FR-006) |
| `url`   | text               | yes      | Stored verbatim as supplied, after the scheme check passes (FR-007) |
| `title` | text               | yes      | Empty string when `--title` is omitted — never `NULL`, never a placeholder (FR-008) |
| `tags`  | set of Tag         | no       | Possibly empty; held in the `tags` relation, not as a column (FR-009) |

Ordering between bookmarks is always ascending `id` (FR-011, FR-013, FR-018, FR-020).

### Tag

A short lower-case label grouping bookmarks. Has no attributes beyond its text and no meaning
beyond grouping.

| Field         | Type    | Required | Notes |
| ------------- | ------- | -------- | ----- |
| `bookmark_id` | integer | yes      | The bookmark carrying the tag |
| `tag`         | text    | yes      | Already normalised: trimmed, lower-cased, non-empty (FR-010) |

### Relationship

`Bookmark` 1 — 0..n `Tag`. A bookmark carries each distinct tag at most once; a tag text may be
shared by any number of bookmarks. Deleting a bookmark deletes its tag rows (FR-016).

---

## Schema

```sql
CREATE TABLE IF NOT EXISTS bookmarks (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    url   TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tags (
    bookmark_id INTEGER NOT NULL REFERENCES bookmarks(id) ON DELETE CASCADE,
    tag         TEXT    NOT NULL,
    PRIMARY KEY (bookmark_id, tag)
);
```

Every connection runs `PRAGMA foreign_keys = ON`, because SQLite leaves foreign keys disabled by
default and the `ON DELETE CASCADE` above would otherwise do nothing.

Why each clause is present, and not more:

- **`AUTOINCREMENT`** — without it, `id` is a plain `rowid` alias whose next value is
  `max(rowid) + 1`, which **reuses** the identifier of a deleted highest row. FR-006 and User
  Story 3 acceptance scenario 4 forbid reuse, so the keyword is load-bearing, not decoration.
- **`title TEXT NOT NULL DEFAULT ''`** — makes "no title means empty string" a storage
  invariant, so no read path has to translate `NULL` into `''` (FR-008).
- **`PRIMARY KEY (bookmark_id, tag)`** — enforces FR-010's at-most-once rule in the database
  rather than trusting the caller. Also supplies the only index the tag queries need.
- **No index on `tags(tag)`** — the `--tag` filter would be faster with one, but SC-007 allows a
  full second for 1,000 bookmarks and the measured workload is far inside that. Adding storage
  no requirement demands is the scope creep Principle IV calls a defect (research R-006).
- **No `UNIQUE` on `bookmarks.url`** — the spec is explicit that the same address may be saved
  more than once, each time receiving its own identifier.
- **No timestamps, no `visit_count`, no `folder`** — nothing in the spec reads them.

---

## Validation rules

Applied in `store.py` so that no caller can bypass them.

### URL scheme (FR-007)

Accept only a `url` that begins with the literal text `http://` or `https://`. The check is a
literal prefix test — the spec's Assumptions say so explicitly: no parsing, no host validation,
no reachability check. Consequences the spec calls out as rejections: `ftp://example.com`, bare
`example.com`, the empty string, and any string where the scheme appears somewhere other than the
start (for example `"see https://x"`). A rejected URL stores nothing and exits 2.

### Tag normalisation (FR-010)

`"TAGS"` → set of tags, in this order:

1. split on `,`
2. strip surrounding whitespace from each entry
3. drop entries that are empty after stripping
4. lower-case each remaining entry
5. collapse duplicates

Worked cases from the spec:

| Input                      | Stored tags        |
| -------------------------- | ------------------ |
| `python,cli`               | `cli`, `python`    |
| `python,,docs`             | `docs`, `python`   |
| `""` (or omitted)          | *none*             |
| `"  python  ,  docs "`     | `docs`, `python`   |
| `Python,python,PYTHON`     | `python`           |
| `Python,Docs`              | `docs`, `python`   |

The same function normalises the `--tag` filter value before comparison, which is what makes
`--tag Python`, `--tag python` and `--tag " PYTHON "` select the same bookmarks (FR-012). Reusing
one function for both sides is what guarantees the two can never disagree.

Normalisation stops there — no stemming, no synonyms, no Unicode form folding beyond
`str.lower()`.

### Identifier (FR-017, FR-024)

A `delete` identifier must be a well-formed integer; a non-numeric one is a usage mistake caught
by the parser and exits 2. A well-formed identifier that no bookmark holds exits 3. These two
statuses must never be confused — status 3 means "well-formed but absent" and nothing else.

---

## Derived values

Neither is stored; both are computed on read.

- **Tag list for display** — a bookmark's tags sorted with Python's default string ordering.
  Because stored tags are always lower case, this is ordinary alphabetical order with no
  case-related surprises (FR-014, FR-018, FR-020). Rendered comma-joined for TSV and CSV, as a
  JSON array for JSON.
- **Match sets** — `search` filters candidate rows in Python on lower-cased substring
  containment against `title` and `url`; `--tag` filters in SQL with `=` against the normalised
  filter value. The reasons for that split (Unicode case folding, `LIKE` wildcards, whole-tag
  matching) are in research R-005.

---

## State transitions

A bookmark has one lifecycle, and it is deliberately short — the spec defines no update or edit
command.

```text
            add (URL accepted)                 delete ID
(absent) ──────────────────────▶ (stored) ──────────────────▶ (absent, id retired)
    │                                                               │
    │ add (URL rejected, FR-007)                      delete ID again (FR-017)
    └──▶ (absent, nothing written, exit 2)            └──▶ exit 3, store unchanged
```

- There is no transition back into `stored` for a retired identifier: `AUTOINCREMENT` guarantees
  a new bookmark gets a number above every identifier ever issued.
- `list`, `search` and `export` cause no transition.
- A failed `add` leaves the store exactly as it was — the scheme check runs before any insert.

### Store lifecycle

```text
path absent, parent exists      ──▶ created with schema, then used        (FR-003)
path absent, parent missing     ──▶ exit 1, no file and no directory made (FR-003a)
valid empty SQLite database     ──▶ schema initialised, then used        (FR-003)
store with our tables           ──▶ opened and appended to, never reset  (FR-003)
not a SQLite database           ──▶ exit 1, file byte-for-byte unchanged (FR-003a, SC-009)
SQLite database of another app  ──▶ exit 1, file byte-for-byte unchanged (FR-003a, SC-009)
read or write access denied     ──▶ exit 1, file unchanged               (FR-003a)
```

The sequence that makes the failing branches non-destructive — opening with `mode=rw` so no file
is created, and deferring the verdict to a read-only query so no write ever happens — is
described and verified in research R-002.
