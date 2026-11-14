# Quickstart & Validation Guide: Command-Line Bookmark Manager

**Feature**: `001-bookmark-cli-manager` | **Date**: 2026-11-14

Runnable scenarios that prove the feature works end to end. Each maps to a user story or
success criterion in [spec.md](./spec.md). Formats are defined in
[contracts/output-formats.md](./contracts/output-formats.md); commands and exit statuses in
[contracts/cli.md](./contracts/cli.md).

## Prerequisites

- CPython **3.11 or newer** (`python3 --version`). No runtime dependencies — standard library
  only.
- `pytest` for the test suite (the only development dependency).
- Repository checked out; all commands below run from the repository root.

## Setup

No build and no install step. Put `src/` on the import path:

```bash
export PYTHONPATH=src
python -m bookmarks --help          # prints usage, exits 0
```

Use a throwaway store so the scenarios do not touch your real one:

```bash
export BM_DB=/tmp/bm-demo.db
rm -f "$BM_DB"
```

`--db` is optional; without it the store is `bookmarks.db` in the current directory.

## Run the test suite

```bash
pytest                              # from the repository root; config lives in pyproject.toml
```

Expected: all tests pass, none skipped. Every one of FR-001…FR-023 is named by at least one
test (constitution Principle III); the mapping is in [plan.md](./plan.md#testing-strategy).

## Scenario 1 — Capture and recall (User Story 1, FR-003/004/007/008/015)

```bash
python -m bookmarks --db "$BM_DB" add https://docs.python.org \
    --title "Python docs" --tags python,docs     # → 1
python -m bookmarks --db "$BM_DB" add https://example.com      # → 2
python -m bookmarks --db "$BM_DB" list
```

Expected: the two `add` calls print `1` then `2` and exit 0; the store file now exists although
no initialisation command was run; `list` prints exactly two lines, in ascending id order:

```text
1	https://docs.python.org	Python docs	docs,python
2	https://example.com		
```

Note the alphabetised tags (`docs,python`, not the `python,docs` supplied) and the two trailing
empty fields on line 2. Each command was a separate process, so this also demonstrates
persistence across runs (FR-004, SC-002).

## Scenario 2 — Rejected URL changes nothing (FR-006/009, SC-003/007)

```bash
python -m bookmarks --db "$BM_DB" list > /tmp/bm-before.txt
python -m bookmarks --db "$BM_DB" add ftp://example.com; echo "status=$?"
python -m bookmarks --db "$BM_DB" list | diff /tmp/bm-before.txt -
```

Expected: `status=2`; a diagnostic naming the URL and the expected `http://`/`https://`
prefixes on **stderr**; nothing on stdout; `diff` reports no difference. Same result for a bare
domain, an empty string, and `HTTPS://example.com` — the prefix check is case-sensitive by
design (spec Assumptions).

Verify the store is not even created when validation fails first:

```bash
python -m bookmarks --db /tmp/bm-never.db add notaurl; echo "status=$?"
test -e /tmp/bm-never.db && echo UNEXPECTED || echo "store not created"
```

## Scenario 3 — Search and tag filter (User Story 2, FR-013/014/016)

```bash
python -m bookmarks --db "$BM_DB" search PYTHON     # bookmark 1 only (case ignored)
python -m bookmarks --db "$BM_DB" search EXAMPLE    # bookmark 2 (matched in its URL)
python -m bookmarks --db "$BM_DB" list --tag docs   # bookmark 1 only
python -m bookmarks --db "$BM_DB" list --tag doc; echo "status=$?"
```

Expected: the first three print the stated subsets in ascending id order, each exiting 0. The
last prints nothing and still exits 0 — `--tag` matches a whole tag, so `doc` does not match
`docs` (FR-013), and "no matches" is a success (FR-016).

## Scenario 4 — Delete, including the error path (User Story 3, FR-017/018, SC-003)

```bash
python -m bookmarks --db "$BM_DB" delete 1; echo "status=$?"   # 0
python -m bookmarks --db "$BM_DB" list                         # bookmark 2 only
python -m bookmarks --db "$BM_DB" delete 42; echo "status=$?"   # 3, stderr names 42
python -m bookmarks --db "$BM_DB" delete two; echo "status=$?"  # 1, usage error
```

Then confirm ids are never recycled:

```bash
python -m bookmarks --db "$BM_DB" delete 2
python -m bookmarks --db "$BM_DB" add https://example.net       # → 3, never 1 or 2
```

Expected: the new id exceeds every id ever assigned in this store (FR-008).

## Scenario 5 — Export round-trip (User Story 4, FR-019/020/021/022, SC-006)

```bash
python -m bookmarks --db "$BM_DB" export --format csv
python -m bookmarks --db "$BM_DB" export --format json
python -m bookmarks --db "$BM_DB" export --format xml; echo "status=$?"
```

Expected: CSV starts with the exact header `id,url,title,tags`; JSON is an array of objects
with `id` as a number and `tags` as an alphabetical array; `xml` writes a diagnostic to stderr
and exits non-zero (1). Prove both formats re-read with standard parsers:

```bash
python -m bookmarks --db "$BM_DB" export --format csv  | python -c \
  "import csv,sys; rows=list(csv.DictReader(sys.stdin)); print(len(rows), rows[:1])"
python -m bookmarks --db "$BM_DB" export --format json | python -c \
  "import json,sys; d=json.load(sys.stdin); print(len(d), d[:1])"
```

Empty-store behaviour (FR-022):

```bash
rm -f /tmp/bm-empty.db
python -m bookmarks --db /tmp/bm-empty.db export --format csv    # header line only, exit 0
python -m bookmarks --db /tmp/bm-empty.db export --format json   # [] , exit 0
python -m bookmarks --db /tmp/bm-empty.db list; echo "status=$?" # no output, status=0
```

## Scenario 6 — Non-ASCII fidelity (FR-023, SC-006)

```bash
python -m bookmarks --db /tmp/bm-i18n.db add https://例え.jp \
    --title "日本語のページ — notes" --tags 日本語,ドキュメント
python -m bookmarks --db /tmp/bm-i18n.db list
python -m bookmarks --db /tmp/bm-i18n.db export --format json
```

Expected: the title, URL and tags come back character-for-character identical in the listing
and in both export formats, with no escaping or substitution in JSON.

## Scenario 7 — Performance at 1,000 bookmarks (SC-005)

```bash
rm -f /tmp/bm-perf.db
python - <<'PY'
import subprocess, sys, os
env = dict(os.environ, PYTHONPATH="src")
for i in range(1000):
    subprocess.run([sys.executable, "-m", "bookmarks", "--db", "/tmp/bm-perf.db",
                    "add", f"https://example.com/{i}", "--title", f"Page {i}",
                    "--tags", "bulk,python" if i % 2 else "bulk"],
                   check=True, stdout=subprocess.DEVNULL, env=env)
PY
time python -m bookmarks --db /tmp/bm-perf.db list    > /dev/null
time python -m bookmarks --db /tmp/bm-perf.db search Page > /dev/null
time python -m bookmarks --db /tmp/bm-perf.db export --format json > /dev/null
```

Expected: each of the three timed commands finishes in well under one second, including
interpreter start-up. (The populate loop is 1,000 separate processes and takes longer; it is
setup, not a measured path.)

## Default store location (FR-002)

```bash
cd "$(mktemp -d)" && PYTHONPATH="$OLDPWD/src" python -m bookmarks add https://example.com
ls bookmarks.db     # created in the current directory because --db was omitted
```

## Cleanup

```bash
rm -f /tmp/bm-demo.db /tmp/bm-empty.db /tmp/bm-i18n.db /tmp/bm-perf.db /tmp/bm-before.txt
```

## Done when

- Scenarios 1–7 behave as described, with the stated exit statuses.
- `pytest` passes from the repository root with no skipped in-scope tests.
- No runtime module imports anything outside the standard library.
