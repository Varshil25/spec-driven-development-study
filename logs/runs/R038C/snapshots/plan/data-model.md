# Data Model: Bookmark Import and HTML Export

**Feature**: `002-import-html-export` | **Date**: 2026-11-20 | **Spec**: [spec.md](./spec.md)

## Summary

**The stored data model does not change.** The schema of feature 001 —
[`specs/001-bookmark-manager-cli/data-model.md`](../001-bookmark-manager-cli/data-model.md) —
is used exactly as it stands: two tables, no new column, no new index, no migration (FR-029).
This feature adds one *transient* entity that exists only while the `import` command runs and
is never persisted.

---

## Unchanged stored entities (feature 001, restated for reference only)

| Entity | Storage | Relevance to this feature |
|---|---|---|
| **Bookmark** | `bookmarks(id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL, title TEXT NOT NULL DEFAULT '')` | `import` inserts rows here; `export --format html` reads them. |
| **Tag** | `bookmark_tags(bookmark_id INTEGER REFERENCES bookmarks(id) ON DELETE CASCADE, tag TEXT NOT NULL, PRIMARY KEY (bookmark_id, tag)) WITHOUT ROWID` | `import` inserts one row per distinct tag of each imported bookmark. |
| **Collection** | One SQLite file, default `./bookmarks.db`, selected by `--db PATH` | `import` writes to it; a collection file written before this feature is readable after it and vice versa (FR-029). |

The in-memory projection `storage.Bookmark(id, url, title, tags)` is likewise unchanged and is
what `write_html` consumes.

**No field is added to record provenance.** The specification's Key Entities section is
explicit: "the collection keeps no record of where a bookmark was imported from." An imported
bookmark is byte-identical in storage to the same bookmark added by hand (FR-035).

---

## New transient entity: Import file

A file supplied by the user holding a sequence of bookmark records. Read once, never written,
and nothing about it survives the command.

| Attribute | Type | Source | Validation |
|---|---|---|---|
| `path` | `str` | positional `FILE` argument | Must name a readable regular file (`os.path.isfile`), at most 33,554,432 bytes (SR-014). Used only as a filesystem path, opened read-only (SR-016, SR-017). |
| `format` | `"csv"` \| `"json"` | `--format` option **only** | argparse `choices`; never inferred from the path or the content (FR-031). |
| `records` | ordered sequence of **Import record** | the file's bytes, decoded as strict UTF-8 | At most 50,000 (SR-014). File order is preserved and becomes identifier order (FR-036). |

### Import record

One element of the sequence. In CSV it is one data row; in JSON it is one array element.

| Field | CSV source | JSON source | Validation (all inherited from `add`) |
|---|---|---|---|
| *ignored id* | field 1 | key `id`, if present | **Never interpreted.** Any content, numeric or not, present or absent, is discarded (FR-034). |
| `url` | field 2 | key `url`, must be a `str` | ≤ 8192 characters, then must begin with the exact lowercase `http://` or `https://` — `cli.validate_url` (FR-008, FR-035, SR-006). |
| `title` | field 3 | key `title`, must be a `str` | ≤ 4096 characters; stored verbatim, including tabs and newlines (FR-009, FR-035, SR-006). |
| `tags` | field 4, a comma-separated string | key `tags`, must be a `list` of `str`, joined with commas | `cli.parse_tags`: split on commas, trim, drop empties, keep each distinct tag once in first-appearance order; ≤ 4096 characters of text, ≤ 64 tags, each ≤ 128 characters (FR-012, FR-035, SR-006). |
| *any other key* | — | ignored | FR-033. |

In code an import record is a plain `tuple[str, str, tuple[str, ...]]` of
`(url, title, tags)` — the exact argument triple `storage.add_bookmark` already takes. No
dataclass is introduced for it (Constitution Principle IV); it exists only inside
`cmd_import`'s local list.

### Shape rules enforced before anything is stored (SR-013, allow-list)

**CSV** — accepted only when all of these hold:

1. The file decodes as strict UTF-8 with no byte-order mark.
2. At least one row exists, and the first row equals `output.CSV_HEADER` — the tuple
   `("id", "url", "title", "tags")` — compared element-wise. A reordered, re-cased, extended or
   truncated header is a rejection, as is a file whose first row is already data.
3. Every subsequent non-empty row holds exactly 4 fields.
4. A blank row may appear only as the last row (a trailing newline produces no row at all).

**JSON** — accepted only when all of these hold:

1. The file decodes as strict UTF-8 with no byte-order mark and parses as JSON.
2. The top-level value is an **array**.
3. Every element is an **object**.
4. Every element has `url` → `str`, `title` → `str`, `tags` → `list` of `str`.

Anything not on these lists is rejected; nothing is coerced, defaulted or skipped.

---

## State transitions

The import file has no state. The *collection* has exactly two outcomes per `import`
invocation, and no third:

```text
                 ┌───────────────────────────────────────────┐
                 │ collection as it was before the command   │
                 └───────────────────────────────────────────┘
                        │                           │
   every record valid   │                           │  any fault (input or storage)
   and the write commits │                           │
                        ▼                           ▼
       ┌────────────────────────────┐   ┌───────────────────────────────┐
       │ prior bookmarks unchanged, │   │ byte-identical to before:     │
       │ N new bookmarks appended   │   │ no row, no tag association,   │
       │ with fresh ids in file     │   │ no change to the next id to   │
       │ order; stdout "imported N" │   │ be issued; stdout empty       │
       └────────────────────────────┘   └───────────────────────────────┘
                 status 0                   status 2 (input) / 1 (storage)
```

There is no partial state (SR-015). Mechanism, per [research.md](./research.md) R3 and R4:

- An **input** fault is detected while validating the file, which happens entirely before
  `storage.connect` is called — so no write is attempted and, if the collection file did not
  exist, it is not created.
- A **storage** fault happens inside a single `with connection:` transaction covering every
  insert of the import, so `sqlite3` rolls the whole batch back. The `AUTOINCREMENT`
  high-water mark in `sqlite_sequence` is rolled back with it (verified in research.md R4), so
  the identifier the next successful `add` receives is unaffected.

### Identifier assignment

Unchanged rule FR-007: identifiers come from the engine's own monotonic sequence, strictly
increasing, never reused. Within one import, records are inserted in file order, so ascending
identifier order reproduces file order (FR-036). An `id` present in the file has no influence
whatsoever (FR-034) — importing a file whose ids are `7,8,9` into an empty collection produces
`1,2,3`.

### Writes performed per import

One transaction containing, per record in file order:

| Statement | Reused from | Parameters |
|---|---|---|
| `storage.INSERT_BOOKMARK_SQL` | feature 001, unchanged | `(url, title)` |
| `storage.INSERT_TAG_SQL`, once per tag | feature 001, unchanged | `(bookmark_id, tag)` |

Both are fixed strings with `?` placeholders (SR-001, unchanged). `import` introduces **no new
SQL statement**; the new `storage.add_bookmarks()` helper is a loop over the two existing ones.

---

## Derived values for HTML export

`export --format html` adds no stored field. Each `<li>` line is computed from a
`storage.Bookmark` already in memory:

| Placeholder | Expression | Notes |
|---|---|---|
| `URL` | `_escape_attr(bookmark.url)` | `&`, `<`, `>`, `"` escaped (FR-043). Stored URLs are always `http://`/`https://` by FR-008, so no `javascript:` or `data:` scheme can occur. |
| `TITLE` | `_escape_text(bookmark.title)` | `&`, `<`, `>` escaped. An absent title is `""` and yields empty link text (FR-042). |
| `TAGS` | `_escape_text(output.join_tags(bookmark.tags))` | `join_tags` is the **same** function CSV and JSON export and the listing format use: comma-joined, ascending code-point order. An empty tag set yields `<small></small>` (FR-042). |

No tag can contain a comma, because FR-012 splits on commas when the tag set is created — so
the comma-joined `TAGS` string is unambiguous, for HTML exactly as it already is for CSV.
