# Quickstart & Validation Guide: Bookmark Import and HTML Export

**Feature**: `002-import-html-export` | **Date**: 2026-11-14 | **Plan**: [plan.md](./plan.md)

Runnable scenarios that prove this feature works end to end, from a terminal, as a user sees it.
Field semantics are in [data-model.md](./data-model.md); exact bytes are in
[contracts/import-command.md](./contracts/import-command.md) and
[contracts/html-export.md](./contracts/html-export.md). Nothing here duplicates implementation
code — the scenarios drive the installed tool only.

## Prerequisites

- CPython **3.11 or newer** (`python3 --version`); no runtime dependencies to install.
- `pytest` for the test suite (development only).
- A clone of this repository, and a scratch directory for throwaway stores and files.

## Setup

```bash
cd /path/to/repo            # repository root (holds pyproject.toml, src/, tests/)
export PYTHONPATH=src       # no install step — see 001/research.md D9
mkdir -p /tmp/bm && cd /tmp/bm   # scratch dir; commands below use absolute --db paths
```

Throughout, `BM` is shorthand for the invocation and `DB` for a throwaway store:

```bash
cd /path/to/repo
BM="python3 -m bookmarks"
DB=/tmp/bm/demo.db
rm -f "$DB"
```

## Run the test suite

```bash
pytest                      # from the repository root
```

Expected: all tests pass, none skipped — the five pre-existing modules **unmodified** plus
`test_import.py`, `test_export_html.py`, `test_roundtrip.py`, `test_compatibility.py`
(FR-045, SC-013, SC-014).

## Scenario 1 — Import a JSON file (User Story 1, FR-024/025/026/030/031)

```bash
cat > /tmp/bm/in.json <<'EOF'
[{"url": "https://docs.python.org", "title": "Python docs", "tags": ["python", "docs"]},
 {"url": "https://example.com", "title": "Example", "tags": []}]
EOF
rm -f "$DB"
$BM --db "$DB" import /tmp/bm/in.json --format json; echo "status=$?"
$BM --db "$DB" list
```

Expected: stdout is exactly `imported 2`, `status=0`, then the listing

```text
1	https://docs.python.org	Python docs	docs,python
2	https://example.com	Example	
```

(tab-separated; the second line ends with an empty tags field). Note the alphabetised tags
although the file listed `python` first.

## Scenario 2 — Import a CSV file, and ids ignore the file (FR-027/028/029/033)

```bash
cat > /tmp/bm/in.csv <<'EOF'
id,url,title,tags
99,https://example.org,"He said ""hi"", loudly"," notes , , notes "
100,https://example.net,Plain,
EOF
$BM --db "$DB" import /tmp/bm/in.csv --format csv; echo "status=$?"
$BM --db "$DB" list
```

Expected: `imported 2`, `status=0`, and the two new bookmarks appear as ids **3 and 4** — the
file's `99`/`100` have no effect (FR-033). The quoted title keeps its comma and its single
double quote; the untidy tags field is stored as `notes` (trimmed, de-duplicated — FR-028).

## Scenario 3 — Empty input is a success (FR-038)

```bash
rm -f /tmp/bm/empty.db
printf 'id,url,title,tags\n' > /tmp/bm/header-only.csv
echo '[]' > /tmp/bm/empty.json
python3 -m bookmarks --db /tmp/bm/empty.db import /tmp/bm/header-only.csv --format csv
python3 -m bookmarks --db /tmp/bm/empty.db import /tmp/bm/empty.json --format json
python3 -m bookmarks --db /tmp/bm/empty.db list; echo "status=$?"
```

Expected: `imported 0` twice, each with status 0, and an empty listing with `status=0`.

## Scenario 4 — Every rejection path leaves the store untouched (FR-034/035/036/037, SC-010/011)

```bash
$BM --db "$DB" list > /tmp/bm/before.txt          # baseline listing

$BM --db "$DB" import /tmp/bm/nope.csv --format csv;        echo "missing      -> $?"
$BM --db "$DB" import /tmp/bm --format csv;                 echo "directory    -> $?"
printf '\xff\xfe' > /tmp/bm/bad.csv
$BM --db "$DB" import /tmp/bm/bad.csv --format csv;         echo "not UTF-8    -> $?"
printf 'url,title,tags\nhttps://a.com,A,\n' > /tmp/bm/hdr.csv
$BM --db "$DB" import /tmp/bm/hdr.csv --format csv;         echo "bad header   -> $?"
printf 'id,url,title,tags\n1,https://a.com,A\n' > /tmp/bm/short.csv
$BM --db "$DB" import /tmp/bm/short.csv --format csv;       echo "short row    -> $?"
echo '{"url": "https://a.com"}' > /tmp/bm/obj.json
$BM --db "$DB" import /tmp/bm/obj.json --format json;       echo "not array    -> $?"
echo '[{"url": "https://a.com", "tags": []}]' > /tmp/bm/nokey.json
$BM --db "$DB" import /tmp/bm/nokey.json --format json;     echo "no title     -> $?"
echo '[{"url": "https://a.com", "title": "A", "tags": "x"}]' > /tmp/bm/badtags.json
$BM --db "$DB" import /tmp/bm/badtags.json --format json;   echo "tags not arr -> $?"
cat > /tmp/bm/badurl.json <<'EOF'
[{"url": "https://ok.com", "title": "Ok", "tags": []},
 {"url": "ftp://nope.com", "title": "Bad", "tags": []}]
EOF
$BM --db "$DB" import /tmp/bm/badurl.json --format json;    echo "bad URL      -> $?"

$BM --db "$DB" list > /tmp/bm/after.txt
diff /tmp/bm/before.txt /tmp/bm/after.txt && echo "store unchanged"
$BM --db "$DB" add https://next.example --title Next   # id continues as if nothing happened
```

Expected: every line prints `-> 2`; each failure writes a diagnostic to **stderr** naming the
file or the offending value (`ftp://nope.com` for the last one) and **nothing to stdout**; no
traceback anywhere; `diff` reports no change and prints `store unchanged`; the final `add` prints
`5` — the id it would have received had no import been attempted (FR-037, SC-010). Note that the
bad-URL file was rejected **whole**: `https://ok.com` was not added either.

To confirm a rejected import does not even create a store:

```bash
rm -f /tmp/bm/never.db
python3 -m bookmarks --db /tmp/bm/never.db import /tmp/bm/nope.csv --format csv; echo "status=$?"
test -e /tmp/bm/never.db && echo "UNEXPECTED: store created" || echo "store not created"
```

## Scenario 5 — HTML export (User Story 2, FR-039/040/041/043)

```bash
$BM --db "$DB" export --format html; echo "status=$?"
```

Expected (`status=0`): the page from
[contracts/html-export.md](./contracts/html-export.md) — `<!DOCTYPE html>` first, a `<head>` line
declaring `utf-8` and the title `Bookmarks`, then `<ul>`, one
`<li><a href="URL">TITLE</a> <small>TAGS</small></li>` per bookmark in ascending id order, then
`</ul></body></html>` one per line. A bookmark with no tags shows `<small></small>`.

Empty store and the unchanged formats:

```bash
rm -f /tmp/bm/empty2.db
python3 -m bookmarks --db /tmp/bm/empty2.db export --format html | tee /tmp/bm/empty.html
python3 -m bookmarks --db /tmp/bm/empty2.db export --format html | grep -c '<li>'   # expect 0
$BM --db "$DB" export --format xml; echo "bad format -> $?"                          # expect 1
```

Expected: the skeleton prints with no `<li>` lines (`grep -c` prints `0`), status 0 (FR-043); the
unknown format writes an argparse diagnostic to stderr and exits **1** (FR-044).

## Scenario 6 — Escaping and non-ASCII in the page (FR-042, SC-012)

```bash
rm -f /tmp/bm/esc.db
E="python3 -m bookmarks --db /tmp/bm/esc.db"
$E add 'https://example.com/?a=1&b=2' --title 'Tom'"'"'s "A&B" <notes>' --tags 'a&b,c<d'
$E add 'https://例え.jp' --title '日本語のページ' --tags '日本語'
$E export --format html > /tmp/bm/esc.html
cat /tmp/bm/esc.html
python3 -c "import sys,html.parser as p; p.HTMLParser().feed(open('/tmp/bm/esc.html',encoding='utf-8').read()); print('well-formed')"
xdg-open /tmp/bm/esc.html 2>/dev/null   # optional: look at it in a browser
```

Expected: `&`, `<`, `>` and `"` appear as `&amp;`, `&lt;`, `&gt;`, `&quot;`; the apostrophe in
`Tom's` and all Japanese text appear **verbatim**; the parser prints `well-formed`; in a browser
the titles read exactly as stored and the links are clickable.

## Scenario 7 — Round trip between stores (User Story 3, SC-009)

```bash
rm -f /tmp/bm/b.db /tmp/bm/c.db
$BM --db "$DB" export --format csv  > /tmp/bm/a.csv
$BM --db "$DB" export --format json > /tmp/bm/a.json
python3 -m bookmarks --db /tmp/bm/b.db import /tmp/bm/a.csv  --format csv
python3 -m bookmarks --db /tmp/bm/c.db import /tmp/bm/a.json --format json

$BM --db "$DB" list | cut -f2- > /tmp/bm/a.fields
python3 -m bookmarks --db /tmp/bm/b.db list | cut -f2- > /tmp/bm/b.fields
python3 -m bookmarks --db /tmp/bm/c.db list | cut -f2- > /tmp/bm/c.fields
diff /tmp/bm/a.fields /tmp/bm/b.fields && echo "CSV round trip lossless"
diff /tmp/bm/a.fields /tmp/bm/c.fields && echo "JSON round trip lossless"
```

Expected: both imports report `imported N` for the full count of store A, and both `diff`s are
silent — URL, title and tag set survive both formats, including the comma, the double quote and
the non-ASCII text (ids are renumbered from 1, which is why they are cut away). Importing
`/tmp/bm/a.csv` into store B a second time doubles its contents with fresh ids — import never
deduplicates.

## Scenario 8 — Nothing about the old commands changed (FR-045/046, SC-014)

```bash
rm -f /tmp/bm/compat.db
C="python3 -m bookmarks --db /tmp/bm/compat.db"
$C add https://docs.python.org --title 'Python docs' --tags python,docs
$C add https://example.com
$C list; $C search PYTHON; $C list --tag docs
$C export --format csv; $C export --format json
$C delete 2; echo "delete -> $?"; $C delete 99; echo "absent id -> $?"
$C add ftp://nope; echo "bad url -> $?"
```

Expected: byte-for-byte the output documented for feature 001 — TSV lines from `list`/`search`,
the `id,url,title,tags` CSV and the indented JSON array unchanged, `delete 2` status 0,
`delete 99` status **3**, `add ftp://nope` status **2**. A store created by the previous version
of the tool opens unchanged under the new one, and a store the new commands have written is still
readable by the previous version (FR-046) — the schema is untouched.

## Scenario 9 — Bulk performance (SC-008, SC-015)

```bash
python3 - <<'EOF'
import json
json.dump([{"url": f"https://example.com/{i}", "title": f"Page {i}",
            "tags": ["bulk", f"t{i % 10}"]} for i in range(1000)],
          open("/tmp/bm/1000.json", "w"))
EOF
rm -f /tmp/bm/bulk.db
time python3 -m bookmarks --db /tmp/bm/bulk.db import /tmp/bm/1000.json --format json
time python3 -m bookmarks --db /tmp/bm/bulk.db export --format html > /tmp/bm/bulk.html
grep -c '<li>' /tmp/bm/bulk.html    # expect 1000
```

Expected: `imported 1000` from a single command, each `time` well under **five seconds** on
ordinary developer hardware, and exactly 1,000 list items in the page.

## Cleanup

```bash
rm -rf /tmp/bm
```

## Done when

- [ ] `pytest` passes from the repository root with no skips, the five pre-existing test modules unmodified (FR-045, SC-014).
- [ ] Scenarios 1–3 print the exact `imported N` counts and listings shown, with status 0.
- [ ] Scenario 4: every rejection exits 2 with a named diagnostic on stderr, empty stdout, an unchanged listing, no store created where none existed, and the next `add` gets the id it would have got (FR-037, SC-010/011).
- [ ] Scenario 5 reproduces the documented page exactly, the empty store still prints the skeleton, and an unknown format exits 1.
- [ ] Scenario 6: the four HTML characters are escaped, the apostrophe and non-ASCII text are verbatim, the page parses.
- [ ] Scenario 7: both round trips are field-for-field lossless (SC-009).
- [ ] Scenario 8: all five original commands behave byte-identically with unchanged statuses.
- [ ] Scenario 9: 1,000 bookmarks import and export in under five seconds each (SC-015).
