# Quickstart & Validation: Tar Archive List & Extract CLI

**Feature**: `001-tar-archive-cli` | **Date**: 2026-11-05

How to run the tool and how to prove it works end to end. Interface details live in
[contracts/cli-contract.md](./contracts/cli-contract.md); entity and validation details live in
[data-model.md](./data-model.md). This file does not duplicate them and contains no implementation
code.

## Prerequisites

- Python 3.11 or newer (`python3 --version`). Verified against CPython 3.13.17.
- `pytest` for the automated suite (`python3 -m pytest --version`). Verified against pytest 9.1.1.
  `pytest` is test-only; the program itself needs nothing beyond the standard library.
- No installation or build step. The package is run from the source tree.

## Running the tool

From the repository root, with `src/` on the import path:

```bash
export PYTHONPATH=src

python -m tarx list    ARCHIVE
python -m tarx extract ARCHIVE DEST [--overwrite]
```

## Running the automated suite

The constitution requires a bare invocation from the repository root to work; `pytest.ini` supplies
`pythonpath = src` so no environment setup is needed (research R10):

```bash
pytest
```

Everything must pass before the feature is considered complete. Tests that invoke
`python -m tarx` as a subprocess set `PYTHONPATH=src` in the child environment themselves, because
the `pythonpath` ini option applies only to the pytest process.

## Manual end-to-end walkthrough

Run in a scratch directory. This exercises one scenario from each user story.

### Setup — build a fixture archive

```bash
mkdir -p demo/photos demo/empty-dir
printf 'alpha' > demo/photos/a.jpg
printf 'bravo' > demo/photos/b.jpg
tar -cf photos.tar -C demo photos empty-dir
gzip -c photos.tar > photos.tar.gz
```

### Scenario 1 — list (User Story 1)

```bash
PYTHONPATH=src python -m tarx list photos.tar; echo "exit=$?"
```

Expected: the archive's members one per line in archive order, directory entries included and
printed without a trailing `/`, nothing on stderr, `exit=0`.

Repeat with `photos.tar.gz` — identical stdout and status, which demonstrates content-based
compression detection. Renaming `photos.tar.gz` to `mislabeled.tar` and listing it must also give
the same result.

### Scenario 2 — extract into a fresh destination (User Story 2)

```bash
PYTHONPATH=src python -m tarx extract photos.tar out; echo "exit=$?"
diff -r demo out && echo "contents match"
```

Expected: `extracted 2 files` on stdout, `exit=0`, `diff -r` reports no differences — so relative
paths and byte contents are preserved, `out/empty-dir` exists, and the empty directory is not
counted.

### Scenario 3 — refuse to clobber, then allow it (User Story 3)

```bash
PYTHONPATH=src python -m tarx extract photos.tar out; echo "exit=$?"
```

Expected: a diagnostic on stderr naming a conflicting path, nothing on stdout, `exit=3`, and
`diff -r demo out` still clean — the destination was not touched.

```bash
printf 'stale' > out/photos/a.jpg
PYTHONPATH=src python -m tarx extract photos.tar out --overwrite; echo "exit=$?"
cat out/photos/a.jpg; echo
```

Expected: `extracted 2 files`, `exit=0`, and `out/photos/a.jpg` reads `alpha` again.

A directory that already exists where the archive stores a directory is not a conflict — the second
run above proves it, since `out/photos` and `out/empty-dir` already existed.

### Scenario 4 — failures are scriptable (User Story 4)

```bash
PYTHONPATH=src python -m tarx list missing.tar;            echo "exit=$?"
head -c 500 /dev/urandom > junk.bin
PYTHONPATH=src python -m tarx list junk.bin;               echo "exit=$?"
PYTHONPATH=src python -m tarx list demo;                   echo "exit=$?"
touch blocker
PYTHONPATH=src python -m tarx extract photos.tar blocker;  echo "exit=$?"
PYTHONPATH=src python -m tarx;                             echo "exit=$?"
PYTHONPATH=src python -m tarx frobnicate photos.tar;       echo "exit=$?"
```

Expected for each: a short one-line diagnostic on stderr naming the offending path, empty stdout,
`exit=2`, and no Python traceback anywhere. The last two print usage guidance.

A hand-built archive containing a member named `../escape.txt` or `/etc/escape.txt` must also exit
`2` with the member named on stderr, and must create nothing outside the destination. This case
cannot be produced with GNU `tar` conveniently, so it is covered by a programmatically built fixture
in the suite rather than in this walkthrough.

## Acceptance checklist

Trace back to the success criteria in [spec.md](./spec.md). The feature is done when all hold:

- [ ] `pytest` passes from the repository root with no arguments.
- [ ] Every functional requirement FR-001 … FR-028 names at least one covering test, traceable by
      requirement id in the test name or docstring (SC-006, Constitution Principle III).
- [ ] `list` output matches member names and order exactly for compressed and uncompressed forms
      (SC-001).
- [ ] Extraction into an empty destination reproduces every regular file byte-identically with the
      correct count (SC-002).
- [ ] Re-extraction without `--overwrite` exits 3 and leaves pre-existing files byte-unchanged,
      verified by comparing before and after (SC-003).
- [ ] Re-extraction with `--overwrite` exits 0 and leaves targets byte-identical to the archive
      (SC-004).
- [ ] Every specified failure case exits with its assigned status and writes a non-empty diagnostic,
      with zero tracebacks (SC-005).
- [ ] An archive of 10,000 members lists in under 5 s and extracts in under 30 s, with memory flat
      with respect to the largest member (SC-007).
- [ ] Runtime code imports only the standard library and `tarx` itself (Constitution Principle I) —
      checkable by grepping the import lines under `src/`.
