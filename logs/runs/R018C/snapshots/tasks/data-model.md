# Data Model: Import and HTML Export

**Feature**: `002-import-html-export` | **Date**: 2026-11-16

**Input**: [spec.md](./spec.md), [research.md](./research.md)

## Scope of change

**The stored schema does not change.** `bookmarks` and `tags` are exactly as
[`001-bookmark-manager-cli/data-model.md`](../001-bookmark-manager-cli/data-model.md) defines
them, with no migration step and no new storage rule (FR-016). A store written by the previous
version is used as-is.

This document therefore covers only what is new: the two **import record** shapes (external,
read-only, transient) and the **HTML page** projection (derived, write-only). Neither is
persisted.

```text
import file  ──parse──▶  ImportRecord[]  ──validate──▶  store.add_bookmarks  ──▶  bookmarks + tags
                                                                                        │
                                                                        list_bookmarks  ▼
                                                                                   HTML page
```

---

## Entity: ImportRecord (transient)

One bookmark as it appears in an import file: a plain `dict` with the keys `url`, `title`, `tags`,
produced by whichever parser the declared `--format` selected, and consumed immediately by
`store.add_bookmarks`. It is never stored and has no identity of its own.

| Field   | Type  | Constraint | Source |
| ------- | ----- | ---------- | ------ |
| `url`   | `str` | Must begin with the literal `http://` or `https://` | FR-003, `001:FR-007` |
| `title` | `str` | Any text, including empty; stored verbatim | FR-003, `001:FR-008` |
| `tags`  | `str` | Comma-joined label text, normalised by `store.normalise_tags` | FR-003, `001:FR-009`, `001:FR-010`, research R-104 |

`tags` is carried as the **comma-joined string form** in both shapes, so that a record reaching
the store is indistinguishable from an `add --title … --tags …` invocation (research R-104). The
JSON parser joins its array with `,` to produce it.

An `id` in the file is **not** a field of this entity: it is read and discarded at the parser
boundary (FR-004). No record ever carries an identifier into the store.

### Derived at insert time, never from the file

| Property | Rule |
| -------- | ---- |
| Identifier | Issued by the store's existing `AUTOINCREMENT`: starts at 1 in a fresh store, increases, never reissued (FR-004, `001:FR-006`) |
| Insert order | File order, so identifiers ascend in file order (FR-005) |
| Tag set | `normalise_tags`: split on `,`, strip, drop empties, lower-case, de-duplicate, sort (FR-003, `001:FR-010`) |
| Uniqueness | None. The same address may appear any number of times, each occurrence becoming its own bookmark (FR-011 context, spec Edge Cases) |

### Worked normalisation cases (import vs. `add`, which must agree)

| File value for the labels | Stored tag set |
| ------------------------- | -------------- |
| `python,docs` (CSV field) / `["python","docs"]` (JSON) | `docs`, `python` |
| `Python, DOCS ,python` / `["Python"," DOCS ","python"]` | `docs`, `python` |
| `` (empty) / `[]` | none |
| `,,` / `["","  "]` | none |

The last two rows are why a bookmark with no labels and an empty title is stored exactly as
`add URL` with both options omitted stores it (Acceptance Scenario 1.5).

---

## Shape A: the CSV file (`--format csv`)

Read as the form `export --format csv` writes (FR-006, `001:FR-018`, `001:FR-019`).

```text
id,url,title,tags
1,https://docs.python.org,Python docs,"docs,python"
2,https://example.com,,
```

| Position | Record | Rule |
| -------- | ------ | ---- |
| First | Header | Must parse to exactly the four values `id`, `url`, `title`, `tags`, **in that order** (FR-006) |
| Rest | Bookmark rows | Must each hold exactly **4** fields, in the order `id`, `url`, `title`, `tags` (FR-006a) |

- The header is compared **after** CSV parsing, so `id,url,title,tags` and
  `"id","url","title","tags"` are equally acceptable, while wrong names, wrong order, a wrong
  count, or no header record at all is a failure (FR-006, Clarifications).
- Field 0 (`id`) is parsed and discarded — any value, including non-numeric, is accepted and
  ignored (FR-004). It is not validated, because it is not used.
- Field 3 holds the labels of *one* bookmark joined by commas; the export quotes it for exactly
  that reason, and it must yield several labels rather than a parse error (FR-006, Edge Cases).
- Standard CSV quoting is honoured: a quoted field may contain commas, doubled quotation marks
  and line breaks (FR-006).
- Both `\n` and `\r\n` terminate a record (FR-006).
- A **blank line is a record of zero fields** and therefore fails the 4-field rule, wherever it
  occurs; blank lines are never skipped. The single line feed ending the final row is that row's
  terminator, not a blank record (FR-006a).
- The header record alone → 0 bookmarks, success (FR-006).

## Shape B: the JSON file (`--format json`)

Read as the form `export --format json` writes (FR-007, `001:FR-020`).

```json
[
  {"id": 1, "url": "https://docs.python.org", "title": "Python docs", "tags": ["docs", "python"]},
  {"id": 2, "url": "https://example.com", "title": "", "tags": []}
]
```

| Level | Required type | Failure if otherwise |
| ----- | ------------- | -------------------- |
| Document | array | FR-007, FR-010 |
| Element | object | FR-007, FR-010 |
| `url` | string, required | FR-007, FR-010 |
| `title` | string, required | FR-007, FR-010 |
| `tags` | array of strings, required | FR-007, FR-010 |
| `id` | any, optional | Accepted, value disregarded (FR-004, FR-007) |
| Any other key | — | Failure: an unrecognised key is a shape error, not silently dropped data (FR-010, spec Assumptions) |

- A missing `title` or `tags` is an error, **not** a default of empty (spec Assumptions).
- An empty array → 0 bookmarks, success (FR-007).
- A single object instead of an array → failure (Edge Cases).

## Common to both shapes

- Decoded as UTF-8; a single leading byte-order mark is discarded before parsing; bytes that are
  not valid UTF-8 are a failure (FR-009, research R-101).
- The declared `--format` alone decides the shape. The file name, extension and contents are
  never consulted, and there is no fallback to the other shape (FR-008).

---

## Validation order and the atomicity invariant

The validation sequence is load-bearing, not incidental (research R-105):

1. **Read** the file (decode UTF-8, discard the BOM). Failure → status 2.
2. **Parse** it in the declared shape. Failure → status 2.
3. **Validate** every record's structure, then every record's address against the scheme rule.
   Failure → status 2.
4. **Only now** open the store, insert every record in file order, commit once.
5. Print `imported N`.

**Invariant**: no store call of any kind occurs before step 4. Consequences, each a requirement:

| Consequence | Requirement |
| ----------- | ----------- |
| A failed import adds nothing — not even records preceding the fault | FR-011 |
| A failed import creates no store file when none existed | FR-011 |
| A failed import advances no identifier, so the next `add` gets the identifier it would have got | FR-011 |
| A file problem is never reported as status 1 (a store problem) | FR-017 |
| A *successful* import — even of 0 bookmarks — does open the store, so an absent store file is created and left empty | FR-002a |

Steps 1–3 are "all-or-nothing" by construction: there is nothing to undo.

---

## Projection: the HTML page

A derived, read-only rendering of the whole collection in ascending identifier order, built from
the same `list_bookmarks` rows the CSV and JSON exports use. It carries each bookmark's address,
title and labels but **not** its identifier, which is why it is a presentation form and not a
round-trip shape — there is no `import --format html` (FR-012, spec Key Entities and Assumptions).

| Page element | Value | Rule |
| ------------ | ----- | ---- |
| Fixed lines | Emitted verbatim | FR-012, FR-014 |
| One `<li>` line | Per bookmark, ascending identifier order | FR-012 |
| `href` value | The address | escaped per FR-014, including `"` |
| Link text | The title, including when empty | escaped per FR-014; no placeholder for an empty title |
| `<small>` text | Labels joined by `,`, alphabetical, no spaces; the element is present even when empty | FR-012 |

### The closed escaping rule (FR-014)

| Character | In `href` | In title and labels | Note |
| --------- | --------- | ------------------- | ---- |
| `&` | `&amp;` | `&amp;` | Substituted **first**, so no escape is doubly escaped |
| `<` | `&lt;` | `&lt;` | |
| `>` | `&gt;` | `&gt;` | |
| `"` | `&quot;` | *literal* | Only the attribute value needs it |
| `'` | *literal* | *literal* | Deliberately **not** escaped |
| Everything else, including non-ASCII, tabs, line breaks | *literal* | *literal* | Written as UTF-8 (FR-013) |

The set is closed — exactly these four substitutions and no others — which is what makes the page
byte-predictable and assertable byte-for-byte, like the CSV and JSON exports (FR-014, SC-004).

Every line, including the last, ends with a single `\n`, and the page ends with exactly one
trailing newline (FR-013). An empty collection yields the same page with no `<li>` line between
`<ul>` and `</ul>` (FR-012).

See [contracts/cli-contract-002.md](./contracts/cli-contract-002.md) for the exact byte layout.
