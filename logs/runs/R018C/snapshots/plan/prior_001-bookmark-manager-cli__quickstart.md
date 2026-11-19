# Quickstart & Validation Guide: Bookmark Manager CLI

**Feature**: `001-bookmark-manager-cli` | **Date**: 2026-11-16

Runnable scenarios that prove the feature works end to end. Field layouts and the exit-status map
live in [contracts/cli-contract.md](./contracts/cli-contract.md); storage rules live in
[data-model.md](./data-model.md). This guide does not repeat them, and contains no
implementation code.

---

## Prerequisites

- Python **3.11 or newer** (`python3 --version`)
- `pytest` for the automated suite — the only development dependency, and never imported by
  shipped code
- No other installation step: the runtime uses the standard library only, so there is nothing to
  `pip install` for the tool itself

## Setup

Run from the repository root. `src/` must be on `PYTHONPATH` for `python -m bookmarks` to resolve:

```bash
export PYTHONPATH=src
cd "$(mktemp -d)"     # a scratch directory, so the default store is fresh
```

Each scenario below assumes a fresh scratch directory. `cd` back to the repository root before
running the test suite.

---

## Scenario 1 — Save a bookmark and get it back later (User Story 1)

Proves creation of the store, identifier assignment, persistence across processes, and the TSV
layout.

```bash
python -m bookmarks add https://docs.python.org --title "Python docs" --tags python,docs
python -m bookmarks add https://example.com
python -m bookmarks list
```

**Expected**: the first `add` prints `1`, the second prints `2`, each exiting 0. `list` — a
separate process, reading the store written by the earlier ones — prints two lines in ascending
identifier order, four tab-separated fields each. Bookmark 2 has an empty title field and an
empty tags field, so its line ends with two consecutive tabs.

Check the store was created where expected and nothing else was:

```bash
ls bookmarks.db
```

## Scenario 2 — A rejected URL stores nothing (User Story 1, scenario 5)

```bash
python -m bookmarks add ftp://example.com; echo "exit=$?"
python -m bookmarks list
```

**Expected**: `exit=2`. The diagnostic naming the rejected URL and the accepted schemes appears
on **stderr**, nothing on stdout, and `list` prints nothing — the rejection happened before any
write. Repeat with `example.com`, `""`, and `"see https://x"` (scheme not at the start); all four
behave identically, which is the shape SC-004 asks for across at least five malformed inputs.

To confirm the stream split rather than trusting the terminal:

```bash
python -m bookmarks add ftp://example.com 2>/dev/null   # prints nothing at all
```

## Scenario 3 — Find the bookmark I am looking for (User Story 2)

Seed a store with mixed-case tags, then filter and search:

```bash
python -m bookmarks add https://docs.python.org --title "Python docs" --tags Python,Docs
python -m bookmarks add https://news.example.com --title "News" --tags news
python -m bookmarks list --tag python      # case-insensitive, whole-tag
python -m bookmarks list --tag PYTHON      # same result
python -m bookmarks list --tag py          # no match
python -m bookmarks search PYTHON          # matches the title, ignoring case
python -m bookmarks search example         # matches the URL, not the title
python -m bookmarks search zzz             # no match
```

**Expected**: the two `--tag` spellings each return the Python docs bookmark, and its tags field
reads `docs,python` — lower-cased and alphabetical whatever case was typed. `--tag py` returns
nothing and exits 0, proving whole-tag matching. `search PYTHON` returns the docs bookmark;
`search example` returns the news bookmark, proving URLs are searched too. `search zzz` prints
nothing and exits 0. Also try `search ""` — it matches every bookmark.

## Scenario 4 — Remove a bookmark, and the identifier stays retired (User Story 3)

```bash
python -m bookmarks add https://a.example.com
python -m bookmarks add https://b.example.com
python -m bookmarks delete 2; echo "exit=$?"
python -m bookmarks list
python -m bookmarks add https://c.example.com     # new identifier, not a reused 2
python -m bookmarks delete 2; echo "exit=$?"      # already gone
python -m bookmarks delete 99; echo "exit=$?"     # never issued
python -m bookmarks delete abc; echo "exit=$?"    # not a number
```

**Expected**: the first `delete` exits 0 and `list` then shows bookmark 1 only. The next `add`
prints **3**, not 2 — identifiers are never reissued, which is the behaviour `AUTOINCREMENT`
guarantees and the single most likely thing to regress. Deleting 2 again and deleting 99 both
exit **3** with a diagnostic naming the identifier. `delete abc` exits **2** — a usage mistake,
never 3. That 2-versus-3 distinction is the point of the scenario.

## Scenario 5 — Take the collection somewhere else (User Story 4)

Seed values that stress quoting, then export both ways:

```bash
python -m bookmarks add https://docs.python.org --title "Python docs" --tags python,docs
python -m bookmarks add https://example.com --title 'He said "hi", then
left'
python -m bookmarks add https://café.example.com --title "Café — ünïcode"
python -m bookmarks export --format csv
python -m bookmarks export --format json
python -m bookmarks export --format xml; echo "exit=$?"
```

**Expected**: CSV begins with the header `id,url,title,tags`, quotes the title containing a
comma, a quotation mark and a line break, doubles the embedded quotes, and terminates every line
with a bare `\n`. JSON is a two-space-indented array with `id` as a number, `tags` as an
alphabetical array, non-ASCII written literally, and one trailing newline.
`--format xml` exits **2** with a diagnostic.

Verify the exports are genuinely lossless rather than merely plausible — this is SC-006, and
eyeballing quoted CSV is how round-trip bugs survive:

```bash
python -m bookmarks export --format csv  | python3 -c 'import csv,sys; [print(r) for r in csv.reader(sys.stdin)]'
python -m bookmarks export --format json | python3 -c 'import json,sys; print(json.load(sys.stdin))'
```

Each field must come back exactly as it went in, including the embedded newline and quote.
Confirm the CSV line endings directly:

```bash
python -m bookmarks export --format csv | od -c | grep -c '\\r'   # expect 0
```

## Scenario 6 — Empty store (User Story 4, scenario 4)

```bash
cd "$(mktemp -d)"
python -m bookmarks list;                 echo "exit=$?"
python -m bookmarks search anything;      echo "exit=$?"
python -m bookmarks export --format csv;  echo "exit=$?"
python -m bookmarks export --format json; echo "exit=$?"
```

**Expected**: all exit 0. `list` and `search` print nothing. CSV prints the header line alone.
JSON prints `[]` and a newline.

## Scenario 7 — Unusable store is never damaged (FR-003a, SC-009)

The most important failure path: the tool must refuse rather than repair.

```bash
# (a) parent directory does not exist
python -m bookmarks --db /tmp/nope-$$/x.db list; echo "exit=$?"
ls -d /tmp/nope-$$ 2>&1            # must NOT exist — no directory was created

# (b) the path is not a bookmark database
printf 'this is not a database\n' > plain.txt
sha256sum plain.txt > before.sha
python -m bookmarks --db plain.txt list; echo "exit=$?"
python -m bookmarks --db plain.txt add https://x.example.com; echo "exit=$?"
sha256sum -c before.sha            # must report OK
```

**Expected**: every command exits **1** with a diagnostic on stderr naming the path and the
reason, and nothing on stdout. In (a) no directory and no file is created. In (b) the checksum
matches — the file was not overwritten, truncated, re-initialised or repaired, by the read path
or the write path.

```bash
# (c) a database belonging to another program
python3 -c "import sqlite3; c=sqlite3.connect('other.db'); c.execute('CREATE TABLE other(x)'); c.commit()"
python -m bookmarks --db other.db list; echo "exit=$?"
```

**Expected**: exit **1**. A valid SQLite file with foreign tables is still not our store, and is
left untouched.

## Scenario 8 — Separate stores, explicit and default (FR-002)

```bash
cd "$(mktemp -d)" && python -m bookmarks add https://one.example.com    # prints 1
mkdir elsewhere && cd elsewhere
python -m bookmarks add https://two.example.com                         # prints 1 again
python -m bookmarks list                                                # one bookmark only
python -m bookmarks --db ../bookmarks.db list                           # the other collection
```

**Expected**: each directory has its own `bookmarks.db`, so both `add` calls print `1`, and
`--db` reaches across to the first collection.

## Scenario 9 — Usage mistakes (FR-024)

```bash
python -m bookmarks;                      echo "exit=$?"   # no command
python -m bookmarks bogus;                echo "exit=$?"   # unknown command
python -m bookmarks add;                  echo "exit=$?"   # missing URL
python -m bookmarks export;               echo "exit=$?"   # missing --format
python -m bookmarks --help;               echo "exit=$?"   # help is not an error
```

**Expected**: the first four exit **2**, each with a diagnostic on stderr naming what was
missing or invalid. `--help` prints usage to stdout and exits **0**.

## Scenario 10 — Non-ASCII output under a C locale (FR-023a)

```bash
LC_ALL=C LANG=C python -m bookmarks add https://café.example.com --title "Café ünïcode"
LC_ALL=C LANG=C python -m bookmarks list
LC_ALL=C LANG=C python -m bookmarks export --format json
```

**Expected**: the accented characters appear correctly in all three, with no
`UnicodeEncodeError`. This fails loudly if stream reconfiguration was skipped, and an
ASCII-locale machine is where it would otherwise first be noticed — by a user, not a test.

---

## Automated suite

From the repository root:

```bash
pytest                 # the whole suite must pass
pytest -q              # quiet
pytest -k export       # one area
```

`pytest` resolves the package through `pythonpath = ["src"]` in `pyproject.toml`; no install step
and no `PYTHONPATH` export is needed for the suite itself.

### What "done" means

The constitution's quality gates, as they apply here:

- **Traceability** — every functional requirement FR-001 … FR-027 is named by at least one test
  (in the test's name or a comment), per Principle III and FR-027. A requirement with no test
  counts as unimplemented regardless of the code.
- **Suite green** — the full suite passes.
- **Dependency check** — no third-party import in `src/bookmarks/`; `grep -r "^import\|^from"
  src/bookmarks/` should show standard-library modules only.
- **Failure-path check** — each of exit statuses 1, 2 and 3 has a test asserting both the status
  and the message content, not just the status.
- **Simplicity review** — no code that no requirement demands.

Exit statuses and stream separation are asserted by running the CLI as a subprocess, because an
in-process call cannot observe a real process exit status.

### Performance validation (SC-002, SC-007)

Seed 1,000 bookmarks through the store module directly — 1,000 subprocess calls would take
minutes and the seeding route is not what is under test — then time the user-visible commands:

```bash
pytest -k performance
```

**Expected**: `list`, `search`, `export` and `delete` each return in under one second on a
1,000-bookmark store (SC-007), and all 1,000 come back with URLs, titles and tags identical to
what was stored (SC-002).
