# Quickstart: Create Tar Archives (`create` command)

**Feature**: `002-create-archive-command` | **Date**: 2026-11-12 | **Spec**: [spec.md](./spec.md)

How to run and validate this feature end to end. Behaviour details live in
[`contracts/create-cli.md`](./contracts/create-cli.md); the in-memory shapes and validation
order live in [`data-model.md`](./data-model.md); the decisions behind them live in
[`research.md`](./research.md).

---

## Prerequisites

- Python 3.11 or newer (`python3 -V`). No third-party package is needed or permitted at runtime.
- `pytest` for the test suite — the only development dependency.
- A POSIX-like filesystem and a non-privileged user. No network access.
- No installation step: the package is run from the source tree with `src/` on `PYTHONPATH`.

```bash
cd /root/sdd-study/runs/R010
export PYTHONPATH=src
python3 -m tarx --help
```

---

## Scenario 1 — Create, inspect, and round-trip (User Story 1)

Proves FR-104 – FR-111 and the SC-101 – SC-103 outcomes.

```bash
cd "$(mktemp -d)" && export PYTHONPATH=/root/sdd-study/runs/R010/src
mkdir -p photos/empty-sub
printf 'alpha' > photos/a.jpg
printf 'beta'  > photos/b.jpg
printf 'hello' > notes.txt

python3 -m tarx create photos.tar.gz photos        # → created photos.tar.gz with 2 files
echo "status=$?"                                   # → status=0

python3 -m tarx list photos.tar.gz                 # → photos / photos/a.jpg / photos/b.jpg / photos/empty-sub
python3 -m tarx extract photos.tar.gz out          # → extracted 2 files
diff -r photos out/photos && test -d out/photos/empty-sub && echo "round trip OK"
```

**Expected**: the success line is exactly `created photos.tar.gz with 2 files`; `list` prints the
directory member before its contents, contents in sorted order; `diff -r` reports nothing; the
empty subdirectory exists under `out/`.

Several paths at once, and plain versus gzip:

```bash
python3 -m tarx create backup.tar notes.txt photos   # → created backup.tar with 3 files
file backup.tar photos.tar.gz                        # → POSIX tar archive / gzip compressed data
python3 -m tarx create same.tgz photos && python3 -m tarx create again.tgz photos
cmp same.tgz again.tgz && echo "reruns are byte-identical"
```

**Expected**: `backup.tar` reports 3 files (`notes.txt` plus the two photos; the two directory
members are not counted); the `.tgz` name produces gzip; two runs over an unchanged tree produce
identical bytes.

No account metadata is recorded (SC-107):

```bash
tar -tvf backup.tar      # owner/group columns show 0/0 (or root/root by uid lookup), mode rw-r--r--
```

---

## Scenario 2 — Refusing to clobber (User Story 2)

Proves FR-114 – FR-116, FR-121, SC-106.

```bash
cp photos.tar.gz keep.bytes
python3 -m tarx create photos.tar.gz photos        # error on stderr, nothing on stdout
echo "status=$?"                                   # → status=3
cmp photos.tar.gz keep.bytes && echo "existing archive untouched"

python3 -m tarx create photos.tar.gz photos --overwrite
echo "status=$?"                                   # → status=0, archive replaced

mkdir adir
python3 -m tarx create adir photos --overwrite
echo "status=$?"                                   # → status=2 (a directory is not status 3)
test -d adir && echo "directory untouched"

python3 -m tarx create nosuchdir/x.tar photos
echo "status=$?"                                   # → status=2, no directory created
```

**Expected**: status 3 **only** for the pre-existing regular file without `--overwrite`; status 2
for a directory at the archive path and for a missing parent directory; the existing file and
directory are untouched in every refused case.

---

## Scenario 3 — Failing cleanly (User Story 3)

Proves FR-117 – FR-120, FR-122, SR-101 – SR-104, SR-109, SC-105, SC-106.

```bash
python3 -m tarx create other.tar missing-folder
echo "status=$?"; test ! -e other.tar && echo "no archive created"     # → 2, no archive

python3 -m tarx create other.tar notes.txt missing-folder              # → 2: fails before writing
test ! -e other.tar && echo "existing paths were not archived anyway"

ln -s /etc/hostname photos/link
python3 -m tarx create other.tar photos                                # → 2: names the link and its kind
rm photos/link

python3 -m tarx create other.tar /etc                                  # → 2: absolute path refused
python3 -m tarx create other.tar ../outside                            # → 2: '..' refused
python3 -m tarx create other.tar .                                     # → 2: '.' refused
python3 -m tarx create other.tar photos photos                         # → 2: duplicate member
python3 -m tarx create other.tar photos photos/a.jpg                   # → 2: nested duplicate
ls | grep -c tarx                                                      # → 0: no temporary file left
```

**Expected**: status 2 every time, each message naming the offending `PATH` or member (and its
kind, for a link), no archive at `other.tar`, and no leftover temporary file in the directory.

The archive inside its own tree, and a failed overwrite:

```bash
python3 -m tarx create photos/out.tar photos       # succeeds; out.tar is not its own member
python3 -m tarx list photos/out.tar | grep -c out.tar   # → 0
cp photos/out.tar keep2.bytes
python3 -m tarx create photos/out.tar photos missing --overwrite
echo "status=$?"; cmp photos/out.tar keep2.bytes && echo "unchanged after failed overwrite"
```

---

## Scenario 4 — Bounds and large inputs

Proves SR-105, SR-106, SC-108.

```bash
mkdir big && python3 -c "
import pathlib
d = pathlib.Path('big')
for i in range(1000):
    (d / f'f{i:04d}.bin').write_bytes(b'x' * 50_000)
"
time python3 -m tarx create big.tar big        # → created big.tar with 1000 files, well under 5 s
```

**Expected**: completes in under 5 seconds for a 1,000-file ≈50 MB tree, with memory use
independent of file size (contents are streamed in 64 KiB chunks). A tree over 10,000 members or
1 GiB fails with status 2 and leaves no archive.

---

## Automated validation

```bash
cd /root/sdd-study/runs/R010
python3 -m pytest -q                       # whole suite, including the 001 behaviour tests
python3 -m pytest -q tests/test_create.py tests/test_create_roundtrip.py \
                     tests/test_create_overwrite.py tests/test_create_failures.py \
                     tests/test_create_security.py tests/test_create_limits.py
python3 -m pytest -q tests/test_traceability.py    # requirement-coverage gate (SC-110)
```

**Expected on completion**:

- The 144 tests inherited from `001-tarx-cli` pass **unmodified** (MC-102, SC-109).
- `tests/test_traceability.py` passes, meaning every `FR-1xx` and `SR-1xx` identifier in this
  spec is named by at least one test (SC-110, constitution Principle III).

> Before this feature's tests exist, `test_traceability.py` fails — it scans every
> `specs/*/spec.md`, so this spec's new identifiers are reported as uncovered the moment the
> spec is merged. That failure is the gate working as designed and is cleared by implementing
> the tests, not by changing the gate. See [research.md](./research.md) R-118.

---

## Things to check by hand after implementing

- `python3 -m tarx list x.tar.gz` and `python3 -m tarx extract x.tar out` still behave exactly as
  [`001-tarx-cli/contracts/cli.md`](../001-tarx-cli/contracts/cli.md) describes (FR-101).
- `stat -c %a` on a freshly created archive reports `600` (SR-107).
- `python3 -m tarx create 'odd name.tar' $'weird\tdir'` prints escaped names, one line only
  (SR-110).
- `python3 -m tarx create out.tar photos | head -0` exits 2 with nothing on stderr, and
  `out.tar` is complete (spec Edge Cases).
