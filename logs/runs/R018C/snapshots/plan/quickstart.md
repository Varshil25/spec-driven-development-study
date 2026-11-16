# Quickstart: Validating Import and HTML Export

**Feature**: `002-import-html-export` | **Date**: 2026-11-16

How to prove this feature works end to end, by hand and by suite. Rules and byte layouts are not
repeated here — see [contracts/cli-contract-002.md](./contracts/cli-contract-002.md) for the
interface and [data-model.md](./data-model.md) for the file shapes.

## Prerequisites

- Python 3.11 or newer (`python3 -VV`). Standard library only — nothing to install at runtime.
- `pytest` for the suite (the single development dependency).
- Run everything from the repository root. `src/` must be on `PYTHONPATH`; the test suite gets
  this from `pyproject.toml`, and the shell commands below set it explicitly.

```bash
cd /root/sdd-study/runs/R018
export PYTHONPATH=src
python3 -VV
```

Work in a scratch directory so no check touches a real collection:

```bash
mkdir -p /tmp/bmcheck && cd /tmp/bmcheck
```

---

## Scenario 1 — Import both shapes into a fresh store (User Story 1, P1)

Write one file of each shape, import each into its own fresh store, and list the result.

```bash
printf 'id,url,title,tags\n1,https://docs.python.org,Python docs,"docs,python"\n2,https://example.com,,\n' > two.csv
cat > two.json <<'JSON'
[{"id": 7, "url": "https://docs.python.org", "title": "Python docs", "tags": ["python", "docs"]},
 {"id": 9, "url": "https://example.com", "title": "", "tags": []}]
JSON

python3 -m bookmarks --db from-csv.db import two.csv --format csv
python3 -m bookmarks --db from-csv.db list
python3 -m bookmarks --db from-json.db import two.json --format json
python3 -m bookmarks --db from-json.db list
```

**Expected**: each import prints `imported 2` and exits 0. Each listing shows identifiers `1` and
`2` in file order, labels lower-cased, comma-joined and alphabetical — so the file's `id` values
`7` and `9` were disregarded (FR-002, FR-004, FR-005). The two listings are identical to each
other.

Check that importing into a populated store appends rather than replaces:

```bash
python3 -m bookmarks --db from-csv.db import two.json --format json   # expect: imported 2
python3 -m bookmarks --db from-csv.db list                            # expect: ids 1..4
```

**Expected**: the first two bookmarks are unchanged and the new ones carry identifiers above
every identifier previously issued (FR-004).

### Successful import of an empty file creates the store (FR-002a)

```bash
printf 'id,url,title,tags\n' > empty.csv
python3 -m bookmarks --db fresh.db import empty.csv --format csv   # expect: imported 0, status 0
ls fresh.db                                                        # expect: the file exists
python3 -m bookmarks --db fresh.db add https://a.example.com       # expect: 1
```

---

## Scenario 2 — Every damaged file is rejected cleanly (FR-010, FR-011, SC-003)

The point of each check is the same triple: a diagnostic on stderr, **nothing** on stdout, exit
**2**. Build a set of damaged files and run them all:

```bash
mkdir -p adir
printf 'name,link\n' > badheader.csv
printf 'id,url,title,tags\n1,https://a.example.com,A\n' > shortrow.csv
printf 'id,url,title,tags\n1,https://a.example.com,A,x\n\n' > blankline.csv
printf 'id,url,title,tags\n1,ftp://a.example.com,A,x\n' > badscheme.csv
printf '{"url": "https://a.example.com"}\n' > notalist.json
printf '[{"url": "https://a.example.com", "title": "A"}]\n' > missingkey.json
printf '[{"url": "https://a.example.com", "title": "A", "tags": "x"}]\n' > tagsstring.json
printf '[{"url": "https://a.example.com", "title": "A", "tags": [], "note": "n"}]\n' > extrakey.json
printf '[{"url": "https://a.example.com",\n' > broken.json
: > zero.csv
printf '\xff\xfe\x00bad' > badutf8.csv

for f in missing.csv adir badheader.csv shortrow.csv blankline.csv badscheme.csv zero.csv badutf8.csv; do
  python3 -m bookmarks --db target.db import "$f" --format csv > out.txt 2> err.txt
  echo "$f -> status $? stdout:$(wc -c < out.txt) bytes stderr:$(head -c 120 err.txt)"
done
for f in notalist.json missingkey.json tagsstring.json extrakey.json broken.json; do
  python3 -m bookmarks --db target.db import "$f" --format json > out.txt 2> err.txt
  echo "$f -> status $? stdout:$(wc -c < out.txt) bytes stderr:$(head -c 120 err.txt)"
done
ls target.db 2>&1
```

**Expected**: every line reports `status 2`, `stdout:0 bytes`, and a message naming the file and
what was wrong and what was expected. The final `ls` reports **no such file** — a failed import
creates no store (FR-011).

Then confirm the identifier sequence was untouched by the failures:

```bash
python3 -m bookmarks --db target.db add https://a.example.com   # expect: 1
```

Two more checks from the same family:

```bash
# The declared shape is never second-guessed: each file is valid, in the other shape (FR-008).
python3 -m bookmarks --db target.db import two.json --format csv ; echo "status $?"   # expect 2
python3 -m bookmarks --db target.db import two.csv --format json ; echo "status $?"   # expect 2

# A store problem is status 1, not 2 — the two classes stay distinct (FR-017).
python3 -m bookmarks --db no/such/dir/x.db import two.csv --format csv ; echo "status $?"  # expect 1
```

### Accepted oddities (these must *succeed*)

```bash
printf '\xef\xbb\xbfid,url,title,tags\n1,https://a.example.com,A,x\n' > bom.csv
printf 'id,url,title,tags\r\n1,https://a.example.com,A,"x,y"\r\n' > crlf.csv
printf '"id","url","title","tags"\n1,https://a.example.com,A,x\n' > quotedheader.csv

for f in bom.csv crlf.csv quotedheader.csv; do
  python3 -m bookmarks --db "ok-$f.db" import "$f" --format csv && python3 -m bookmarks --db "ok-$f.db" list
done
```

**Expected**: `imported 1` each. The BOM is gone (the first address is intact, not prefixed), the
CRLF file's quoted `x,y` became the two labels `x,y`, and the quoted header was accepted
(FR-006, FR-009, Clarifications).

---

## Scenario 3 — The HTML page (User Story 2, P2)

```bash
python3 -m bookmarks --db page.db add https://docs.python.org --title "Python docs" --tags python,docs
python3 -m bookmarks --db page.db add https://example.com
python3 -m bookmarks --db page.db export --format html
```

**Expected**: exactly the page in the contract's worked example — five fixed opening lines, one
`<li>` line per bookmark in identifier order, three fixed closing lines, one trailing newline.
The second bookmark's link text is empty and its `<small>` element is present but empty
(FR-012, FR-013).

```bash
python3 -m bookmarks --db empty-page.db export --format html | diff - <(python3 -m bookmarks --db empty-page.db export --format html) && echo stable
python3 -m bookmarks --db empty-page.db export --format html | grep -c '<li>'   # expect: 0
python3 -m bookmarks --db page.db export --format html | tail -c 20 | xxd | tail -1
```

**Expected**: an empty collection still prints the whole page with no `<li>` line, and the final
byte is a single `0a` (FR-012, FR-013).

Escaping, including the characters that must stay **literal**:

```bash
python3 -m bookmarks --db esc.db add 'https://x.example.com/?a=1&b=2"z' --title 'Tom'\''s "A&B" <tag>'
python3 -m bookmarks --db esc.db export --format html | grep '<li>'
```

**Expected**: the one `<li>` line in the contract's escaping example — `&` and the angle brackets
substituted in both places, `"` substituted **only** inside `href`, and the apostrophe in `Tom's`
literal (FR-014).

Non-ASCII stays literal, and the other two formats are untouched:

```bash
python3 -m bookmarks --db esc.db add https://café.example.com --title "Café — ünïcode"
python3 -m bookmarks --db esc.db export --format html | grep Café   # expect: literal, no entities
python3 -m bookmarks --db esc.db export --format fancy ; echo "status $?"   # expect: usage error, 2
```

---

## Scenario 4 — Round trip between stores (User Story 3, P3)

Export a collection full of awkward values, import it into an empty store, compare field by
field. This is the check that the import really does accept what the export writes.

```bash
python3 -m bookmarks --db src.db add https://a.example.com --title 'Comma, inside' --tags b,a
python3 -m bookmarks --db src.db add https://b.example.com --title 'Quote " inside'
python3 -m bookmarks --db src.db add https://c.example.com --title 'Line
break inside'
python3 -m bookmarks --db src.db add https://café.example.com --title 'Café — ünïcode' --tags café
python3 -m bookmarks --db src.db add https://a.example.com --title 'Duplicate address'

for fmt in csv json; do
  python3 -m bookmarks --db src.db export --format $fmt > round.$fmt
  python3 -m bookmarks --db "rt-$fmt.db" import round.$fmt --format $fmt
  diff <(python3 -m bookmarks --db src.db list) <(python3 -m bookmarks --db "rt-$fmt.db" list) \
    && echo "$fmt round trip identical"
done
```

**Expected**: `imported 5` for each shape, and both `diff`s empty — titles with commas, quotation
marks, embedded line breaks and non-ASCII characters all survive, the duplicate address appears
twice (no de-duplication), and the identifiers renumber from 1, which here match the source
because the source also started from 1 (SC-001, FR-011 context).

---

## Scenario 5 — Performance budget (SC-005)

```bash
python3 -m bookmarks --db big.db add https://seed.example.com >/dev/null
python3 - <<'PY'
import csv
with open("/tmp/bmcheck/big.csv", "w", newline="") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(["id", "url", "title", "tags"])
    for i in range(1000):
        w.writerow([i, f"https://example.com/page/{i}", f"Page {i}", f"tag{i % 10},common"])
PY
time python3 -m bookmarks --db big.db import big.csv --format csv     # expect: imported 1000, < 5s
time python3 -m bookmarks --db big.db export --format html > /dev/null  # expect: < 1s
```

---

## Scenario 6 — Nothing that worked before has changed (FR-015, SC-006)

```bash
cd /root/sdd-study/runs/R018
python3 -m pytest -q
```

**Expected**: every pre-existing test passes with **no test file modified** (the baseline before
this feature was 131 passed, 2 skipped), plus the new tests for this feature. Per constitution
Principle III, each new test names the requirement it covers, so the mapping can be read
straight off the output:

```bash
python3 -m pytest tests/test_import.py tests/test_html_export.py -v
python3 -m pytest -q -k "fr014 or fr011"     # spot-check one requirement's coverage
git status --short tests/                     # expect: only new files, none modified
```

A requirement with no test is treated as unimplemented regardless of the state of the code, so
this scenario — not Scenarios 1–5 — is the gate that decides the feature is done.

## Cleanup

```bash
rm -rf /tmp/bmcheck
```
