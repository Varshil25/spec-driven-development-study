# Quickstart: Validating the `create` Command

**Feature**: `002-create-command` | **Date**: 2026-11-19

Runnable scenarios that prove the feature works end to end. Each one maps to a user story or a
success criterion from [spec.md](./spec.md); message wording and member order come from
[contracts/create-cli.md](./contracts/create-cli.md); entity and ordering details from
[data-model.md](./data-model.md). No implementation code here — that belongs to `tasks.md` and the
implement phase.

## Prerequisites

- Python 3.11 or newer (`python3 --version`).
- `pytest` available (`python3 -m pytest --version`). It is the only test dependency; the runtime
  needs nothing outside the standard library.
- Run everything from the repository root. `pyproject.toml` already sets
  `pythonpath = ["src"]` for pytest; for manual runs, export `PYTHONPATH=src`.

```bash
cd /root/sdd-study/runs/R035
export PYTHONPATH=src
```

---

## Scenario 1 — Package files and folders (User Story 1)

```bash
cd "$(mktemp -d)" && export PYTHONPATH=/root/sdd-study/runs/R035/src
mkdir -p photos d/b && printf 'A' > photos/a.jpg && printf 'B' > photos/b.jpg
printf 'hello' > notes.txt
printf 'x' > d/z.txt && printf 'y' > d/a.txt && printf 'z' > d/b/c.txt && mkdir d/empty

python -m tarx create photos.tar.gz photos
python -m tarx create photos.tar   photos
python -m tarx create notes.tgz    notes.txt
python -m tarx create all.tar      notes.txt d photos
```

Expected:

| Command | stdout | stderr | status |
|---------|--------|--------|--------|
| `create photos.tar.gz photos` | `created photos.tar.gz with 2 files` | empty | 0 |
| `create photos.tar photos` | `created photos.tar with 2 files` | empty | 0 |
| `create notes.tgz notes.txt` | `created notes.tgz with 1 files` | empty | 0 |
| `create all.tar notes.txt d photos` | `created all.tar with 6 files` | empty | 0 |

Note `with 1 files` — plural at every count, by contract (FR-008).

Check members, order, and compression:

```bash
python -m tarx list photos.tar.gz          # photos, photos/a.jpg, photos/b.jpg — in that order
python -m tarx list all.tar                # notes.txt, d, d/a.txt, d/b, d/b/c.txt, d/empty, d/z.txt, photos, …
head -c2 photos.tar.gz | xxd               # 1f8b  → gzip
head -c2 photos.tar   | xxd                # not 1f8b → plain tar
head -c2 notes.tgz    | xxd                # 1f8b  → gzip
```

`all.tar` demonstrates both ordering rules at once (FR-026): operands in the order typed
(`notes.txt`, then `d`, then `photos`), and each operand's members sorted by full member name as
text — which is what puts `d/b` before `d/b/c.txt` before `d/empty` before `d/z.txt`.

Determinism (SC-012) — the same tree twice yields the same sequence:

```bash
python -m tarx create once.tar d && python -m tarx create twice.tar d
diff <(python -m tarx list once.tar) <(python -m tarx list twice.tar) && echo "identical"
```

Empty directories are recorded but not counted (FR-007):

```bash
mkdir -p lonely/sub && python -m tarx create lonely.tar lonely
# created lonely.tar with 0 files
python -m tarx list lonely.tar             # lonely, lonely/sub
```

---

## Scenario 2 — An existing archive is not destroyed (User Story 2)

```bash
python -m tarx create photos.tar.gz photos; echo "status=$?"
#   tarx: refusing to overwrite existing file 'photos.tar.gz' (re-run with --overwrite)
#   status=3        ← stdout empty, archive byte-for-byte unchanged

sha256sum photos.tar.gz > before.sha
python -m tarx create photos.tar.gz photos --overwrite; echo "status=$?"
#   created photos.tar.gz with 2 files
#   status=0
sha256sum -c before.sha || echo "replaced, as requested"

mkdir inthe.way
python -m tarx create inthe.way photos --overwrite; echo "status=$?"
#   tarx: archive path 'inthe.way' exists but is not a regular file
#   status=2        ← --overwrite consents to replacing a regular file and nothing else

python -m tarx create backups/2026/photos.tar photos; echo "status=$?"
#   tarx: cannot create archive 'backups/2026/photos.tar': directory 'backups/2026' does not exist
#   status=2
test ! -e backups && echo "no directory was created"   # FR-027
```

---

## Scenario 3 — Clear failure, no half-made archive (User Story 3)

```bash
python -m tarx create out.tar photos nosuch; echo "status=$?"
#   tarx: source path 'nosuch' does not exist
#   status=2
test ! -e out.tar && echo "no archive left behind"

python -m tarx create out.tar nosuch alsomissing; echo "status=$?"
#   tarx: source path 'nosuch' does not exist
#   tarx: source path 'alsomissing' does not exist
#   status=2        ← every problem reported, one per line (FR-018)

python -m tarx create out.tar /etc/hostname; echo "status=$?"   # absolute PATH
#   tarx: unsafe source path '/etc/hostname': resolves outside the current directory
#   status=2
python -m tarx create out.tar ../outside;    echo "status=$?"   # escapes the directory
#   tarx: unsafe source path '../outside': resolves outside the current directory
#   status=2        ← C6 is checked before C5, so an unsafe path is reported as unsafe
#                     rather than as missing, whether or not it exists

# mixed classes: 2 wins over 3 (FR-018)
python -m tarx create photos.tar.gz photos nosuch; echo "status=$?"
#   tarx: refusing to overwrite existing file 'photos.tar.gz' (re-run with --overwrite)
#   tarx: source path 'nosuch' does not exist
#   status=2        ← and photos.tar.gz is still unchanged, even with --overwrite (FR-011)

python -m tarx create; echo "status=$?"                  # usage, non-zero
python -m tarx create out.tar; echo "status=$?"          # no PATH → usage, non-zero
python -m tarx create out.tar photos --clobber; echo "status=$?"   # unknown option
```

Non-regular entries are skipped loudly but are not failures (FR-015):

```bash
mkdir -p mixed && printf 'real' > mixed/f.txt
ln -s f.txt mixed/latest.txt && mkfifo mixed/pipe
python -m tarx create skip.tar mixed; echo "status=$?"
#   tarx: skipping non-regular path 'mixed/latest.txt' (symbolic link)
#   tarx: skipping non-regular path 'mixed/pipe' (FIFO)
#   created skip.tar with 1 files
#   status=0        ← skips on stderr, summary on stdout, neither counted in N
```

Two names for one file are two members, both counted (FR-015):

```bash
mkdir -p hl && printf 'data' > hl/one.txt && ln hl/one.txt hl/two.txt
python -m tarx create hl.tar hl        # created hl.tar with 2 files
python -m tarx extract hl.tar outhl && cat outhl/hl/two.txt   # "data", not empty
```

> **Permission checks and root.** The unreadable-entry path (FR-021) cannot be exercised with
> `chmod 000` while running as root, because root bypasses permission bits — the file stays
> readable and the test would pass vacuously. The suite therefore covers it twice: a real
> permission test marked `skipif(os.geteuid() == 0)`, and a `monkeypatch`-injected `OSError` test
> that runs everywhere. To see the real behaviour, run as a non-root user:
>
> ```bash
> mkdir -p locked && printf 'secret' > locked/f.txt && chmod 000 locked/f.txt
> python -m tarx create locked.tar locked; echo "status=$?"
> #   tarx: cannot read 'locked/f.txt': Permission denied
> #   status=2   ← detected during validation, so no archive exists
> test ! -e locked.tar && echo "no archive left behind"
> ```

---

## Scenario 4 — Round-trip and no regressions (User Story 4)

```bash
python -m tarx create round.tar.gz photos d notes.txt     # created round.tar.gz with 6 files
python -m tarx extract round.tar.gz restored              # extracted 6 files
diff -r photos restored/photos && diff -r d restored/d && echo "trees identical"
```

The extracted count equals the created count, and the comparison shows zero differences in both
relative paths and file bytes (SC-002, SC-008). Repeat with a plain `.tar` name for the
uncompressed form.

The archive excludes itself (FR-019) — written into its own source directory, twice, to show that
the exclusion holds on the re-run where the archive is actually present during the walk:

```bash
mkdir -p selfdir && printf '1' > selfdir/f.txt
python -m tarx create selfdir/all.tar selfdir                   # created selfdir/all.tar with 1 files
python -m tarx create selfdir/all.tar selfdir --overwrite       # created selfdir/all.tar with 1 files
python -m tarx list selfdir/all.tar                             # selfdir, selfdir/f.txt — no all.tar
```

Overlapping operands de-duplicate silently (FR-020):

```bash
python -m tarx create dup.tar photos photos/a.jpg photos
#   created dup.tar with 2 files           ← not 4
python -m tarx list dup.tar | sort | uniq -d    # prints nothing: no duplicate members
```

Interface discoverability (FR-024):

```bash
python -m tarx --help            # names list, extract, create, ARCHIVE, DEST, PATH, --overwrite
python -m tarx create --help     # names ARCHIVE, PATH, --overwrite
```

---

## Running the test suite

```bash
cd /root/sdd-study/runs/R035
python3 -m pytest                      # everything, including the pre-existing 001 suite
python3 -m pytest -m "not slow"        # fast feedback loop
python3 -m pytest -m slow              # SC-010 scale and memory checks only
python3 -m pytest tests/test_create.py tests/test_create_errors.py \
                  tests/test_create_overwrite.py tests/test_create_roundtrip.py
```

### Regression gate (SC-009, FR-023)

The pre-existing suite must pass **unmodified**, so verify that too — not just that it is green:

```bash
python3 -m pytest tests/test_list.py tests/test_extract.py tests/test_overwrite.py \
                  tests/test_validation.py tests/test_errors.py tests/test_traceability.py
git diff --stat -- tests/conftest.py tests/test_list.py tests/test_extract.py \
                   tests/test_overwrite.py tests/test_validation.py tests/test_errors.py \
                   tests/test_traceability.py
# expected: no output — no pre-existing test file was touched
```

### Traceability gate (FR-025, SC-011)

```bash
python3 -m pytest tests/test_create_traceability.py -v
```

Fails with the explicit list of uncovered identifiers if any `CREATE-FR-###` lacks a referencing
test, and also fails if the requirement-to-test map in `data-model.md` has gone stale in either
direction.

### Scale and memory (SC-010)

```bash
python3 -m pytest -m slow -v
```

Two checks:

- **10,000 small files** archived in under 10 seconds.
- **Peak memory does not grow with file size.** Measured with `tracemalloc` around an in-process
  `create` at two file sizes; both must stay under one fixed ceiling. Reference measurements on
  CPython 3.13 for a 40 MB file: **44 KiB** peak for a plain `.tar`, **519 KiB** for `.tar.gz`
  (zlib's compressor state) — against ~40 MB for an implementation that reads a whole file into
  memory, which is what makes the check meaningful rather than decorative.

### Constitution gate

```bash
python3 -m pytest                                   # the whole suite must pass before done
grep -rn "^import \|^from " src/tarx/               # every name must be stdlib (Principle I)
grep -n "dependencies" pyproject.toml               # must remain []
```
