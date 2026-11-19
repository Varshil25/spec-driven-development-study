# Quickstart & Validation Guide

**Feature**: `001-tarx-cli` | **Date**: 2026-11-12 | **Spec**: [spec.md](./spec.md) |
**Contract**: [contracts/cli.md](./contracts/cli.md)

How to run the tool and how to prove it works end to end. Scenario details live in the
[CLI contract](./contracts/cli.md) and [data model](./data-model.md); this file does not
repeat them and contains no implementation code.

---

## Prerequisites

- Python 3.11 or newer (`python3 --version`)
- `pytest` for the test suite — the only development dependency, and never imported by
  runtime code (constitution Principle I)
- No installation, configuration, or network access of any kind (SC-001)

## Setup

Nothing to install. `src/` only has to be importable:

```bash
cd <repo root>
export PYTHONPATH=src
python -m tarx --help
```

`pytest.ini` sets `pythonpath = src`, so the test suite needs no `PYTHONPATH` export of its
own.

---

## Smoke run (2 minutes)

```bash
# Build a small archive to play with
mkdir -p /tmp/tarx-demo/photos && cd /tmp/tarx-demo
printf 'alpha' > photos/a.jpg
printf 'beta'  > photos/b.jpg
tar -czf photos.tar.gz photos

cd <repo root>
export PYTHONPATH=src

# Inspect without extracting
python -m tarx list /tmp/tarx-demo/photos.tar.gz

# Extract
python -m tarx extract /tmp/tarx-demo/photos.tar.gz /tmp/tarx-demo/out
echo "status=$?"
```

Expected: `list` prints each member on its own line in archive order, exit 0. `extract`
prints `extracted 2 files` and exits 0. Then:

```bash
# Same tree, byte-identical contents?
diff -r /tmp/tarx-demo/photos /tmp/tarx-demo/out/photos && echo IDENTICAL

# Narrowest permissions, set at creation (SR-006)
stat -c '%a %n' /tmp/tarx-demo/out/photos /tmp/tarx-demo/out/photos/a.jpg
# expect: 700 for the directory, 600 for the file

# Overwrite protection: refuses, destination untouched, status 3 (FR-009)
python -m tarx extract /tmp/tarx-demo/photos.tar.gz /tmp/tarx-demo/out
echo "status=$?"   # expect 3, message on stderr, no success line

# Deliberate overwrite succeeds (FR-010)
python -m tarx extract /tmp/tarx-demo/photos.tar.gz /tmp/tarx-demo/out --overwrite
echo "status=$?"   # expect 0 and "extracted 2 files"

# Content-based format detection: gzip archive misnamed .tar still works (FR-008)
cp /tmp/tarx-demo/photos.tar.gz /tmp/tarx-demo/misnamed.tar
python -m tarx list /tmp/tarx-demo/misnamed.tar   # expect the same listing, exit 0

# Missing archive: error on stderr, nothing on stdout, status 2 (FR-013)
python -m tarx extract /tmp/tarx-demo/nope.tar.gz /tmp/tarx-demo/out2 >/tmp/tarx-demo/stdout.txt
echo "status=$?"                 # expect 2
test ! -s /tmp/tarx-demo/stdout.txt && echo "stdout empty as required"
```

---

## Full validation

```bash
cd <repo root>
pytest                 # must pass in full before any merge (constitution)
pytest -q tests/test_security.py     # the adversarial corpus alone
pytest -q tests/test_traceability.py # SC-008: every FR-xxx/SR-xxx is referenced by a test
```

The suite is the enforceable record of what the tool promises (Principle III). Every test
function names the requirement identifiers it covers in its name or docstring, and
`test_traceability.py` fails if any identifier in `spec.md` has no referencing test — so
SC-008 is a gate, not an aspiration.

### What the suite must demonstrate

Grouped by the success criterion each group discharges. Expected behaviour for every row is
specified in [contracts/cli.md](./contracts/cli.md).

| Group | Covers | Scenarios |
|---|---|---|
| Round-trip corpus | SC-002, SC-003 | uncompressed and gzip archives; nested directories; empty archive; zero-byte members; names with spaces and non-ASCII characters; very long paths — extracted tree compared to the original for identical relative paths and byte-identical contents, and listings compared line-for-line in archive order |
| Listing | FR-002, FR-003, FR-018 | archive order preserved; every member type printed; empty archive prints nothing; filesystem provably unchanged |
| Extraction | FR-004 – FR-008, FR-019 | counts regular files only; creates missing `DEST` and parents; content-based gzip detection including misnamed archives; exact `extracted N files` line, `N` = 0 and 1 included |
| Overwrite | FR-009 – FR-012 | refusal with status 3 and an unchanged destination; `--overwrite` replaces contents; pre-existing directories reused silently; file↔directory type conflicts exit 2 with and without `--overwrite` |
| Exit statuses | SC-004 | each of 0, 2, 3 produced by its specified scenarios **and by no others** — every failure condition in FR-013, FR-015, and the Security Requirements |
| Adversarial corpus | SC-005 | `..` traversal, absolute and drive-letter/UNC member names, symlink-escape via an existing symlink in `DEST`, symlink/hard-link members, device/FIFO members, duplicate destination paths, oversized and decompression-bomb archives, control characters in names — **zero** files created or modified outside `DEST`, and zero existing files replaced without `--overwrite` |
| Atomicity | SC-006 | destination snapshotted before and after every failing run and compared byte-for-byte; the SR-005 actual-bytes abort is the only case allowed to differ, and must report the partial extraction |
| Output hygiene | FR-016, FR-017, SR-007, SR-008 | errors only on stderr; no success line on failure; control characters in names escaped so one member is one line; no traceback, no member contents, no environment values in messages |
| Usage errors | FR-001, SR-010 | no command, unknown command, missing/extra argument, unknown option, `--overwrite` on `list`, empty-string `ARCHIVE`/`DEST` — all stderr + exit 2 |
| Performance | SC-007 | a 1,000-member, 50 MB archive lists and extracts in under 5 s; a single member far larger than any buffer is streamed, proving no member is held whole in memory |

### Fixtures

All archives, including the hostile ones, are built in-process with `tarfile`/`TarInfo` into
`tmp_path`. No binary fixtures are committed, and no elevated privileges are needed — hostile
members are rejected from their *headers*, so no real device node or escaping symlink has to
exist on disk (see [research.md](./research.md) R-016).

---

## Manual adversarial check (optional, ~1 minute)

Confirms the headline safety property by hand:

```bash
cd /tmp/tarx-demo
python3 -c "
import io, tarfile
with tarfile.open('evil.tar','w') as t:
    i = tarfile.TarInfo('../escaped.txt'); i.size = 5
    t.addfile(i, io.BytesIO(b'pwned'))
"
cd <repo root>
PYTHONPATH=src python -m tarx extract /tmp/tarx-demo/evil.tar /tmp/tarx-demo/safe
echo "status=$?"                              # expect 2, message naming the member
test ! -e /tmp/tarx-demo/escaped.txt && echo "nothing escaped the destination"
```

`list` on the same archive is expected to print `../escaped.txt` and exit 0 — listing is
non-destructive and deliberately unfiltered, which is what makes it the safe way to inspect
an untrusted archive (FR-003).

---

## Definition of done

- [ ] `pytest` passes in full
- [ ] Every `FR-xxx` and `SR-xxx` in `spec.md` is referenced by at least one test name or
      docstring, enforced by `test_traceability.py` (SC-008)
- [ ] No runtime module imports anything outside the standard library (Principle I)
- [ ] Both commands behave exactly as [contracts/cli.md](./contracts/cli.md) specifies,
      including all eight invariants listed at the end of it
