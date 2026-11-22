# Quickstart & Validation Guide

**Feature**: `001-bookmark-manager-cli` | **Date**: 2026-11-20

How to run the tool and how to prove the feature works end to end. Command surface and exact
output rules: [contracts/cli-contract.md](./contracts/cli-contract.md). Entities and schema:
[data-model.md](./data-model.md). Requirement-to-test mapping:
[contracts/requirements-test-matrix.md](./contracts/requirements-test-matrix.md).

## Prerequisites

- Python 3.11 or newer (`python3 -V`). Nothing else at runtime — no `pip install`, no
  configuration file, no initialisation step (SC-001).
- `pytest` to run the automated suite (test-only dependency).

## Setup

From the repository root:

```bash
export PYTHONPATH=src          # so `python -m bookmarks` resolves src/bookmarks/
python -m bookmarks --help     # should list: add, list, search, delete, export
```

No database preparation is needed; the file is created on first use.

## Scenario 1 — Save a bookmark and see it again later (User Story 1, P1)

Proves durable capture and recall across separate processes, the default database path, the
four-field listing format, and URL rejection.

```bash
cd "$(mktemp -d)"            # empty directory, no database yet
export PYTHONPATH=/path/to/repo/src

python -m bookmarks add https://docs.python.org --title "Python docs" --tags "python,docs"
# expect: 1

python -m bookmarks add https://example.com
# expect: 2

python -m bookmarks list | cat -A | head
# expect two lines, tab-separated, four fields each:
#   1→https://docs.python.org→Python docs→docs,python
#   2→https://example.com→→            (line ends in two tabs)

ls bookmarks.db              # created in the cwd because --db was absent
```

Expected outcomes: identifiers `1` then `2` on stdout and nothing else; both bookmarks listed
in ascending id order by a *later* process; tags rendered in code-point order (`docs,python`);
the untitled, untagged bookmark's line ending in two consecutive tabs.

Now the rejection path:

```bash
python -m bookmarks add ftp://example.com; echo "status=$?"
# expect: one-line message on stderr, nothing on stdout, status=2
python -m bookmarks list | wc -l
# expect: 2 — the rejected add stored nothing
```

Check the file permission required by SR-005:

```bash
stat -c '%a' bookmarks.db    # expect: 600
```

## Scenario 2 — Find a bookmark among many (User Story 2, P2)

Proves case-insensitive substring search, exact case-sensitive tag filtering, the
empty-result-is-success rule, and literal `%` handling.

```bash
python -m bookmarks add https://PYTHON.org/downloads --title "Downloads" --tags "python"
python -m bookmarks add https://example.org/x --title "100% coverage" --tags "Testing"

python -m bookmarks search PYTHON
# expect: every bookmark whose title OR url contains "python" in any case, id order

python -m bookmarks list --tag python
# expect: only bookmarks tagged exactly `python` — the one tagged `Testing` is absent,
#         and a bookmark tagged `Python` would also be absent (case-sensitive)

python -m bookmarks search '%'; echo "status=$?"
# expect: only the "100% coverage" bookmark; % is literal, not a wildcard

python -m bookmarks search zzzznothing; echo "status=$?"
# expect: no output on stdout, no output on stderr, status=0
```

## Scenario 3 — Remove a bookmark (User Story 3, P3)

Proves deletion, identifier stability for survivors, non-reuse of identifiers, and the
distinct exit statuses 2 and 3.

```bash
db=$(mktemp -u)/x.db; mkdir -p "$(dirname "$db")"
python -m bookmarks --db "$db" add https://a.example --title A
python -m bookmarks --db "$db" add https://b.example --title B
python -m bookmarks --db "$db" add https://c.example --title C

python -m bookmarks --db "$db" delete 2; echo "status=$?"     # expect status=0
python -m bookmarks --db "$db" list
# expect ids 1 and 3 only, with their original urls and titles

python -m bookmarks --db "$db" delete 2; echo "status=$?"     # expect status=3 + stderr line
python -m bookmarks --db "$db" delete 3; echo "status=$?"     # expect status=0
python -m bookmarks --db "$db" add https://d.example
# expect: 4 — a deleted identifier is never reissued

python -m bookmarks --db "$db" delete abc; echo "status=$?"   # expect status=2 (malformed)
python -m bookmarks --db "$db" delete 0;   echo "status=$?"   # expect status=2
```

The 2-versus-3 distinction is the point of the last two commands: malformed identifier → 2,
well-formed but absent → 3.

## Scenario 4 — Hand the collection to another tool (User Story 4, P4)

Proves both export formats parse with off-the-shelf parsers and that awkward characters
round-trip.

```bash
python -m bookmarks add https://x.example --title 'Comma, "quote" and
newline' --tags "b,a"

python -m bookmarks export --format csv
# expect: first line exactly `id,url,title,tags`; quoted fields where needed

python -m bookmarks export --format json | python -c 'import json,sys; print(json.load(sys.stdin))'
# expect: parses first time; id is an int, tags is a sorted list of strings

# round-trip check — the title must come back byte-identical
python -m bookmarks export --format json \
  | python -c 'import json,sys; print(repr(json.load(sys.stdin)[-1]["title"]))'

python -m bookmarks export --format xml; echo "status=$?"   # expect status=2
python -m bookmarks export; echo "status=$?"                # expect status=2 (--format required)
```

On an empty collection, `export --format csv` prints the header line alone and
`export --format json` prints `[]`, both with status 0.

## Error-path spot checks

```bash
python -m bookmarks --db /nonexistent-dir/x.db list; echo "status=$?"
# expect: status=1, one-line stderr message, no directory created

python -m bookmarks frobnicate; echo "status=$?"       # expect status=2 usage error
python -m bookmarks add; echo "status=$?"              # expect status=2 missing argument
```

Every one of these must print a single line to stderr with **no traceback** and no SQL text
(SR-008), and leave stdout empty.

## Automated suite

The suite is the authoritative validation; the manual scenarios above exist to confirm the
real command line is wired up.

```bash
pytest                 # full suite; `pythonpath = src` comes from pytest.ini
pytest tests/security  # Principle V gate: every SR with its negative case
pytest tests/contract  # command surface, output formats, exit statuses
pytest -m "not slow"   # skips the 10k/50k performance and memory cases
```

Expected: all tests pass, with zero skipped tests other than the POSIX-only file-mode check on
a non-POSIX host. A skipped or disabled test counts as a failing requirement under the
constitution's Test gate.

## Definition of done

- [x] All four scenarios above behave exactly as described, run by hand from a clean directory.
- [x] `pytest` passes with no failures and no unexpected skips.
- [x] Every row of [the test matrix](./contracts/requirements-test-matrix.md) has a passing
      test — 27 FR + 11 SR, including each SR's negative case.
- [x] `stat -c '%a' bookmarks.db` is `600`, and no `-journal`/`-wal`/`-shm` file remains after
      any command.
- [x] `pytest tests/security/test_security_stdlib_only.py` passes, proving the shipped package
      imports nothing outside the standard library.
