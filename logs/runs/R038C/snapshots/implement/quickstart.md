# Quickstart: Validating Import and HTML Export

**Feature**: `002-import-html-export` | **Date**: 2026-11-20

Runnable checks that prove this feature works end to end. Interface details live in
[contracts/cli-contract.md](./contracts/cli-contract.md); field rules and the storage model are
in [data-model.md](./data-model.md); design rationale is in [research.md](./research.md).

## Prerequisites

- Python 3.11 or newer (`python3 --version`; this machine has 3.13.17).
- `pytest` (`python3 -m pytest --version`; this machine has 9.1.1).
- No other package. The shipped code imports only the standard library (SC-015).
- Run everything from the repository root. `pytest.ini` already sets `pythonpath = src`; for
  manual CLI runs, export it yourself:

```bash
cd /root/sdd-study/runs/R038
export PYTHONPATH=src
```

## 1. The full suite, including every feature-001 test

This is the primary gate. SC-010 and SC-011 require a clean run with no skipped test other
than the pre-existing POSIX-only file-mode guard.

```bash
python3 -m pytest -q                 # fast suite
python3 -m pytest -q -m slow         # the 10k / 50k scale cases (SC-013, SR-019)
python3 -m pytest -q --strict-markers
```

**Expected**: 0 failures, 0 errors. The feature-001 modules under `tests/contract`,
`tests/integration`, `tests/security` and `tests/unit` pass **unchanged** — in particular
`tests/security/test_security_stdlib_only.py`, which pins the shipped package to five modules
and a fixed import whitelist.

## 2. Import a JSON file into an empty collection (US1 AS1)

```bash
cd "$(mktemp -d)" && export PYTHONPATH=/root/sdd-study/runs/R038/src
cat > in.json <<'JSON'
[{"url": "https://docs.python.org", "title": "Python docs", "tags": ["python", "docs"]},
 {"url": "https://example.com", "title": "Example", "tags": []}]
JSON
python3 -m bookmarks --db b.db import in.json --format json
python3 -m bookmarks --db b.db list
```

**Expected**:

```text
imported 2
1	https://docs.python.org	Python docs	docs,python
2	https://example.com	Example	
```

stderr empty, status 0. Note the second line ends with a tab and nothing after it (no tags),
and that the tags are reordered to code-point order by the listing format, not by the import.

## 3. Import a CSV file, and confirm file ids are ignored (US1 AS2, AS4)

```bash
printf 'id,url,title,tags\n7,https://a.example,Alpha,"b,a"\n8,https://b.example,,\n' > in.csv
python3 -m bookmarks --db fresh.db import in.csv --format csv
python3 -m bookmarks --db fresh.db list
```

**Expected**: `imported 2`, then ids **1 and 2** — not 7 and 8 (FR-034):

```text
imported 2
1	https://a.example	Alpha	a,b
2	https://b.example		
```

## 4. Import appends; it never deduplicates or renumbers (US1 AS3, FR-037)

```bash
python3 -m bookmarks --db b.db add https://keep.example --title Keep
python3 -m bookmarks --db b.db import in.csv --format csv
python3 -m bookmarks --db b.db import in.csv --format csv
python3 -m bookmarks --db b.db list
```

**Expected**: `imported 2` twice; the `Keep` bookmark still holds the id it was given; the new
bookmarks take the next ids in file order; `https://a.example` now appears **twice**, each with
its own id.

## 5. A bad record fails the whole import (US1 AS6, FR-039, SR-015)

```bash
printf 'id,url,title,tags\n1,https://good.example,Good,\n2,ftp://bad.example,Bad,\n' > mixed.csv
python3 -m bookmarks --db atomic.db import mixed.csv --format csv; echo "status=$?"
python3 -m bookmarks --db atomic.db list; echo "list-status=$?"
```

**Expected**: one line on **stderr** naming the problem and the record, nothing on stdout,
`status=2`. The following `list` prints **nothing** — the valid first record was not stored
either. The `atomic.db` file is not even created, because the whole file is validated before
the collection is opened (research.md R3).

## 6. Empty input is a success, not a failure (US1 AS7, FR-038)

```bash
printf 'id,url,title,tags\n' > empty.csv
echo '[]' > empty.json
python3 -m bookmarks --db e.db import empty.csv --format csv; echo "status=$?"
python3 -m bookmarks --db e.db import empty.json --format json; echo "status=$?"
```

**Expected**: `imported 0` and `status=0` both times; `e.db` exists and holds no bookmark.

## 7. Unreadable and misdeclared input (US1 AS5, FR-031)

```bash
python3 -m bookmarks --db e.db import ./no-such-file --format csv; echo "status=$?"
python3 -m bookmarks --db e.db import . --format json;           echo "status=$?"
python3 -m bookmarks --db e.db import in.json --format csv;      echo "status=$?"
python3 -m bookmarks --db e.db import in.csv --format html;      echo "status=$?"
```

**Expected**: `status=2` every time, one stderr line each, stdout empty. The third shows the
format comes from `--format` alone — a perfectly valid JSON file declared as CSV is rejected.
The fourth is an argparse error: `html` is not an importable format.

Each message is one line with no traceback, no `sqlite3`, no SQL text and no internal path
(SR-018), and reports positions as `row N` / `record N`.

## 8. Export as HTML (US2 AS1, AS2)

```bash
python3 -m bookmarks --db fresh.db export --format html
```

**Expected**, byte-for-byte:

```html
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Bookmarks</title></head>
<body>
<ul>
<li><a href="https://a.example">Alpha</a> <small>a,b</small></li>
<li><a href="https://b.example"></a> <small></small></li>
</ul>
</body>
</html>
```

The second line is US2 AS3: a bookmark with no title and no tags still gets its `<li>`, with
empty link text and an empty `<small>`.

## 9. An empty collection still prints the skeleton (US2 AS5, FR-044)

```bash
python3 -m bookmarks --db blank.db export --format html; echo "status=$?"
```

**Expected**: the eight skeleton lines with nothing between `<ul>` and `</ul>`, and `status=0`.

## 10. Stored data cannot become markup (US2 AS4, SR-012, SC-014)

```bash
python3 -m bookmarks --db xss.db add 'https://x.example/?a=1&b="2"' \
  --title '<script>alert(1)</script> & "quoted"' --tags 'a<b,c&d'
python3 -m bookmarks --db xss.db export --format html
```

**Expected**: no raw `<script>` anywhere, no bare `"` inside the `href`, and a well-formed
page:

```html
<li><a href="https://x.example/?a=1&amp;b=&quot;2&quot;">&lt;script&gt;alert(1)&lt;/script&gt; &amp; "quoted"</a> <small>a&lt;b,c&amp;d</small></li>
```

Note the `"` in the **title** is left as a literal `"` — it is element text, where a quote
needs no escape — while the `"` in the **href** becomes `&quot;` (FR-043, two contexts, two
escapes).

Confirm a standard parser recovers the originals:

```bash
python3 -m bookmarks --db xss.db export --format html > page.html
python3 - <<'PY'
from html.parser import HTMLParser

class Check(HTMLParser):
    def __init__(self):
        super().__init__(); self.href = None; self.text = []; self.tags = None; self.where = None
    def handle_starttag(self, tag, attrs):
        self.where = tag
        if tag == "a":
            self.href = dict(attrs).get("href")
    def handle_endtag(self, tag):
        # Required: without it `where` stays set past `</small>`, and the newline after
        # `</li>` overwrites the tag text with whitespace.
        self.where = None
    def handle_data(self, data):
        if self.where == "a":
            self.text.append(data)
        elif self.where == "small":
            self.tags = data

c = Check(); c.feed(open("page.html", encoding="utf-8").read())
print("href:", c.href)
print("title:", "".join(c.text))
print("tags:", c.tags)
PY
```

**Expected**: `https://x.example/?a=1&b="2"`, `<script>alert(1)</script> & "quoted"`, and
`a<b,c&d` — the stored strings, recovered unchanged.

## 11. Export and import are inverses (US3, SC-009)

```bash
cd "$(mktemp -d)" && export PYTHONPATH=/root/sdd-study/runs/R038/src
python3 -m bookmarks --db src.db add https://one.example \
  --title 'has, a comma and "quotes" and ünïcode' --tags 'z,a'
python3 -m bookmarks --db src.db add https://two.example --title "$(printf 'two\nlines')"

for fmt in csv json; do
  python3 -m bookmarks --db src.db export --format $fmt > round.$fmt
  python3 -m bookmarks --db "copy-$fmt.db" import round.$fmt --format $fmt
  diff <(python3 -m bookmarks --db src.db      list | cut -f2-) \
       <(python3 -m bookmarks --db "copy-$fmt.db" list | cut -f2-) \
    && echo "$fmt round-trip: identical"
done
```

**Expected**: `imported 2` for each format, then `csv round-trip: identical` and
`json round-trip: identical`. Identifiers are renumbered from 1 in the copies, which is why the
comparison drops the first column.

## 12. Existing commands are untouched (FR-028, US2 AS6)

```bash
python3 -m bookmarks --db src.db export --format csv  | md5sum
python3 -m bookmarks --db src.db export --format json | md5sum
git stash && python3 -m bookmarks --db src.db export --format csv | md5sum && git stash pop
```

**Expected**: the CSV and JSON digests before and after this feature match. The automated
version of this check is `test_existing_commands_are_byte_identical`, which compares against
golden values committed with the tests rather than relying on `git stash`.

## 13. Limits are enforced (SR-014)

```bash
python3 - <<'PY'
with open("huge.csv", "w", encoding="utf-8", newline="") as fh:
    fh.write("id,url,title,tags\n")
    for n in range(50_001):
        fh.write(f"{n},https://e.example/{n},T{n},\n")
PY
python3 -m bookmarks --db lim.db import huge.csv --format csv; echo "status=$?"

python3 -c "open('deep.json','w').write('['*100000 + ']'*100000)"
python3 -m bookmarks --db lim.db import deep.json --format json; echo "status=$?"
```

**Expected**: `status=2` both times, one stderr line each — for the deep document a plain
message, **not** a `RecursionError` traceback. Nothing stored.

## 14. The input file is only ever read (SR-016, SR-017)

```bash
md5sum in.csv > before.txt && stat -c '%s %Y' in.csv >> before.txt
python3 -m bookmarks --db ro.db import in.csv --format csv
python3 -m bookmarks --db ro.db import mixed.csv --format csv 2>/dev/null
md5sum in.csv > after.txt && stat -c '%s %Y' in.csv >> after.txt
diff before.txt after.txt && echo "input file untouched"
ls -a "$(dirname "$(readlink -f ro.db)")" | grep -c journal   # expect 0
```

**Expected**: `input file untouched`, and no rollback journal or temporary file left beside the
database after either the successful or the failed import.

## Done when

- [X] `python3 -m pytest -q` and `python3 -m pytest -q -m slow` both pass with 0 failures and
      no new skips. — 528 passed, 0 failures, 0 errors, **0 skips**; `-m slow` selects 24.
      `--strict-markers` also clean.
- [X] Every feature-001 test module is byte-identical to its pre-feature state (SC-011). —
      asserted by `test_feature_001_test_files_are_unmodified` and confirmed by
      `git diff --name-only HEAD -- tests/`, whose only entry is the additive `conftest.py`.
- [X] Checks 2–14 above produce the expected output by hand. — all confirmed, including check
      8's and check 10's byte-exact lines and check 14's empty database directory. Check 12 was
      run against the pre-feature modules recovered from `git show HEAD:…` rather than via
      `git stash`: the `csv` and `json` export digests, and `list`/`search`/`list --tag`, are
      identical.
- [X] The matrix in [contracts/requirements-test-matrix.md](./contracts/requirements-test-matrix.md)
      shows 25/25 requirements mapped with 0 planned skips. — audited mechanically: all 61 test
      functions it names exist in the collected suite and pass.
