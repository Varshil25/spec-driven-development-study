# Phase 1 Data Model: Bookmark Import and HTML Export

**Feature**: `002-import-html-export` | **Date**: 2026-11-14 | **Plan**: [plan.md](./plan.md)

This feature adds **no stored state**. The schema, the entities and every validation rule in
[feature 001's data model](../001-bookmark-cli-manager/data-model.md) apply unchanged — that is
what FR-046 (both-directions store compatibility) requires. What follows describes the two new
*transient* shapes the feature introduces and the rules that convert between them.

## Stored entities — unchanged

| Entity | Status in this feature |
|--------|-----------------------|
| **Bookmark** (`id`, `url`, `title`, `tags`) | unchanged. No column added, no type changed, no constraint changed |
| **Tag** | unchanged: still a substring of the bookmark's normalised `tags` string, never an own row |
| **Store** | unchanged: one SQLite file, `CREATE TABLE IF NOT EXISTS` on connect, `AUTOINCREMENT` ids |

```sql
-- storage.SCHEMA, byte-identical to feature 001 (FR-046)
CREATE TABLE IF NOT EXISTS bookmarks (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    url   TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    tags  TEXT NOT NULL DEFAULT ''
)
```

A store written before this feature is read and written by the new code with no migration, and a
store the new code has written is still an ordinary one-table store the previous version opens
(FR-046). Nothing in `import` or the HTML export touches `sqlite_master`, adds a table, or writes
a marker row.

## Import file (transient input)

An external, read-only file holding a collection of bookmarks in one of the two formats
`export` writes. The tool never writes to it (constitution: no writes outside the caller-supplied
store path).

| Field | In CSV | In JSON | Type required | Use |
|-------|--------|---------|---------------|-----|
| id | column 1, header `id` | key `id` (optional) | any | **ignored** — parsed and discarded (FR-033) |
| url | column 2, header `url` | key `url` (required) | string | validated by the `add` prefix rule (FR-009, FR-036) |
| title | column 3, header `title` | key `title` (required) | string | stored verbatim (FR-010, FR-023) |
| tags | column 4, header `tags` | key `tags` (required) | CSV: a comma-separated string. JSON: array of strings | normalised by the `add --tags` rules (FR-011, FR-028) |
| anything else | a fifth column → **rejected** | any other key → **ignored** (FR-031) | — | lets a file from a later version import |

The asymmetry is deliberate and specified: extra *keys* are tolerated, extra *columns* are not,
because a CSV row's meaning is positional and a row of the wrong width means the file is not the
documented shape (FR-027, FR-035).

### Parsed record (in-memory)

Both parsers produce the same value, and nothing else crosses into the storage layer:

```python
records: list[tuple[str, str, str]]   # (url, title, tags) — tags already normalised
```

A plain tuple, not a `dataclass` or `dict`: it is consumed once, by one `executemany`, three
positional fields wide (Principle IV, D11). The list is ordered as the file orders its bookmarks
(FR-025), which is what makes ids reflect file order.

## Exported page (transient output)

The HTML rendering of the whole collection: one document, one `<ul>`, one `<li>` per bookmark in
ascending id order. Output only — there is no `import --format html` (spec Assumptions). Its exact
bytes are the contract in [contracts/html-export.md](./contracts/html-export.md); its content is
derived from stored fields with no new data:

| Page element | Source | Transformation |
|--------------|--------|----------------|
| `href` attribute | `url` | HTML-escaped (D16) |
| link text | `title` | HTML-escaped; empty title → empty link text |
| `<small>` text | `tags` | the stored string as-is (already alphabetical, comma-joined), HTML-escaped; no tags → empty |
| document skeleton | — | fixed lines, independent of the data (FR-040, FR-043) |

## Validation rules

Applied in this order; the first failure rejects the whole file, inserts nothing, and exits 2
(FR-034…FR-037). Steps 1–4 all complete before the store is opened (D10, D15).

| # | Rule | Failure | Requirement |
|---|------|---------|-------------|
| 1 | The path can be opened and read as a regular, readable file | diagnostic names the path and the OS problem; exit 2 | FR-034 |
| 2 | Its bytes decode as UTF-8 | diagnostic names the path and the decoding problem; exit 2 | FR-034 |
| 3a | **CSV**: first row is exactly `["id","url","title","tags"]`; file is not empty | diagnostic names the header found (or the empty file); exit 2 | FR-027, FR-035 |
| 3b | **CSV**: every following row has exactly 4 fields | diagnostic names the row number and the field count; exit 2 | FR-027, FR-035 |
| 3c | **CSV**: the text is well-formed CSV (`csv.Error`) | diagnostic names the problem; exit 2 | FR-029, FR-035 |
| 4a | **JSON**: the text parses as JSON | diagnostic names the parse error with line and column; exit 2 | FR-035 |
| 4b | **JSON**: the top level is an array | diagnostic names the type found; exit 2 | FR-030, FR-035 |
| 4c | **JSON**: each element is an object with `url`, `title` (strings) and `tags` (array of strings) | diagnostic names the element index and the missing/ill-typed key; exit 2 | FR-030, FR-035 |
| 5 | Every record's URL begins with `http://` or `https://` | diagnostic names the offending URL (the existing `validate_url` message); exit 2, nothing inserted | FR-009, FR-036 |
| 6 | The store can be opened or created | diagnostic names the store path; exit 1 | FR-047 |

Rules deliberately **not** applied, because `add` does not apply them either (FR-032):

- no duplicate-URL check — a URL already in the store is added again as a distinct bookmark;
- no title rule — blank, whitespace-only and non-ASCII titles are stored verbatim (FR-010, FR-023);
- no non-empty-collection rule — zero bookmarks is a success, `imported 0` (FR-038);
- no URL syntax, reachability or DNS check — the prefix test is the whole of the rule (D4).

### Tag normalisation on import (FR-028)

The same single implementation as `add --tags` (`normalise_tags`, FR-011): split on commas, trim
each entry, drop empties, keep a repeated tag once, sort by code point, join with commas.

| Source field | Fed to `normalise_tags` as | Stored |
|--------------|---------------------------|--------|
| CSV `tags` = `python,docs` | `"python,docs"` | `docs,python` |
| CSV `tags` = `" python , , docs "` | `" python , , docs "` | `docs,python` |
| CSV `tags` = `""` | `""` | `""` |
| JSON `tags` = `["python","docs"]` | `"python,docs"` (joined) | `docs,python` |
| JSON `tags` = `[]` | `""` | `""` |
| JSON `tags` = `["docs","docs"]` | `"docs,docs"` | `docs` |

Because the stored value is the displayed value (D2), a tag set written by `export` and read back
by `import` is the same tag set, which is what SC-009 measures.

## State transitions

```text
file on disk ──read(UTF-8)──▶ text ──parse+validate──▶ records ──executemany+commit──▶ bookmarks
     │ (rule 1,2 fail)            │ (rule 3,4 fail)        │ (rule 5 fail)
     └──── exit 2, store untouched ┴────────────────────────┘

bookmarks ──SELECT ... ORDER BY id──▶ rows ──render_html──▶ page on stdout
```

Effects on the store:

| Event | Rows | Highest id ever used | Store file |
|-------|------|---------------------|------------|
| Successful import of N ≥ 1 bookmarks | N rows appended, each with the next id in file order | advances by N | created if absent |
| Successful import of 0 bookmarks | unchanged | unchanged | created if absent (connecting is what creates it) |
| Rejected import (any rule 1–5) | unchanged | **unchanged** — a later `add` gets the id it would have got anyway (FR-037, SC-010) | not created: the file is read, and rejected, before the store is opened |
| Store unusable (rule 6) | unchanged | unchanged | — |
| HTML export | unchanged — read-only | unchanged | created if absent, as for every other read command |

No bookmark is ever modified or deleted by either new command: `import` only appends, the HTML
export only reads.
