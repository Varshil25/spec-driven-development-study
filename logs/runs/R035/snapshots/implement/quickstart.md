# Quickstart: Validating the `tarx` CLI

**Feature**: `001-tarx-cli` | **Date**: 2026-11-19

Runnable scenarios that prove the feature works end to end. Each one maps to a user story or edge
case in [spec.md](./spec.md); the authoritative output and exit-status definitions live in
[contracts/cli.md](./contracts/cli.md), and the validation rules in
[data-model.md](./data-model.md). Nothing here is implementation code — it is what you run to
check the implementation.

## Prerequisites

- Python 3.11 or newer (`python3 --version`)
- `pytest` for the automated suite (the only development dependency; runtime dependencies are
  empty by Constitution Principle I)
- Repository root as the working directory, with `src/tarx/` implemented

```bash
export PYTHONPATH=src          # required for `python -m tarx`
```

## Build sample archives

Run once; every scenario below uses these.

```bash
mkdir -p /tmp/tarx-demo/photos && cd /tmp/tarx-demo
printf 'alpha' > photos/a.jpg
printf 'beta'  > photos/b.jpg
tar  -cf  plain.tar  photos
tar  -czf gz.tgz     photos
cp   gz.tgz misnamed.tar          # gzip content, .tar name — exercises FR-004
tar  -cf  empty.tar  --files-from /dev/null
cd -
```

## Scenario 1 — List both formats (User Story 1, FR-002/FR-004/FR-024)

```bash
python -m tarx list /tmp/tarx-demo/plain.tar
python -m tarx list /tmp/tarx-demo/gz.tgz
python -m tarx list /tmp/tarx-demo/misnamed.tar
```

Expected, identically for all three: the three members `photos`, `photos/a.jpg`, `photos/b.jpg`,
one per line, in **archive order** — compare against `tar -tf /tmp/tarx-demo/plain.tar`, since
`tar -cf` records directory entries in filesystem read order, not alphabetically. The directory
member carries **no** trailing slash, stderr is empty, `echo $?` → `0`.

```bash
diff <(python -m tarx list /tmp/tarx-demo/plain.tar) \
     <(tar -tf /tmp/tarx-demo/plain.tar | sed 's:/$::')   # expect no differences
```

## Scenario 2 — Extract into a fresh destination (User Story 2, FR-005…FR-008)

```bash
rm -rf /tmp/out && python -m tarx extract /tmp/tarx-demo/plain.tar /tmp/out
echo "status=$?"
find /tmp/out -type f | sort
cmp /tmp/out/photos/a.jpg /tmp/tarx-demo/photos/a.jpg
```

Expected: stdout exactly `extracted 2 files`, status `0`, both files present under
`/tmp/out/photos/`, `cmp` silent (byte-identical). `/tmp/out` and its parents were created by the
tool.

## Scenario 3 — Refuse to clobber (User Story 2, FR-009/FR-020)

```bash
printf 'mine' > /tmp/out/photos/a.jpg
python -m tarx extract /tmp/tarx-demo/plain.tar /tmp/out; echo "status=$?"
cat /tmp/out/photos/a.jpg
```

Expected: status `3`, stdout empty, and `a.jpg` still reading `mine` — **no** file was written.

stderr names **both** `/tmp/out/photos/b.jpg` and `/tmp/out/photos/a.jpg`, one line each in
archive order, each suggesting `--overwrite`. Both are named because Scenario 2 already created
both files, so both would be replaced, and FR-009 requires *every* conflicting path to be
reported rather than just the first. To see the single-conflict form instead, delete `b.jpg`
(`rm /tmp/out/photos/b.jpg`) before re-running — then only `a.jpg` is reported, and `b.jpg` is
still **not** created, which is the FR-020 point: a refused run writes nothing at all, not even
the members that had no conflict.

## Scenario 4 — Deliberate replacement (User Story 3, FR-010)

```bash
python -m tarx extract /tmp/tarx-demo/plain.tar /tmp/out --overwrite; echo "status=$?"
cat /tmp/out/photos/a.jpg
```

Expected: stdout `extracted 2 files`, status `0`, `a.jpg` now reads `alpha`. Replaced files count
toward `N`. An unrelated file you drop into `/tmp/out` beforehand is left untouched.

## Scenario 5 — Empty archive (Edge case, FR-018)

```bash
python -m tarx list /tmp/tarx-demo/empty.tar; echo "list status=$?"
python -m tarx extract /tmp/tarx-demo/empty.tar /tmp/out-empty; echo "extract status=$?"
```

Expected: `list` prints nothing, status `0`; `extract` prints `extracted 0 files` — plural at zero
— status `0`.

## Scenario 6 — Failure modes (User Story 4, FR-012/FR-013/FR-017/FR-019)

```bash
python -m tarx list /tmp/tarx-demo/nope.tar;                     echo "missing=$?"      # 2
printf 'not a tar' > /tmp/plain.txt
python -m tarx list /tmp/plain.txt;                              echo "not-tar=$?"      # 2
python -m tarx extract /tmp/tarx-demo/plain.tar /tmp/plain.txt;  echo "dest-file=$?"    # 2
python -m tarx frobnicate /tmp/tarx-demo/plain.tar;              echo "bad-cmd=$?"      # non-zero
python -m tarx extract /tmp/tarx-demo/plain.tar;                 echo "missing-arg=$?"  # non-zero
```

Expected in every case: a specific message on stderr, empty stdout, and `/tmp/plain.txt`
unmodified.

## Scenario 7 — Unsafe member paths and multiple problems (FR-014/FR-023/FR-025)

```bash
cd /tmp/tarx-demo && printf 'x' > escape.txt
tar -cf unsafe.tar --transform 's|^escape.txt|../escape.txt|' escape.txt photos && cd -
rm -rf /tmp/out2 && mkdir -p /tmp/out2 && printf 'mine' > /tmp/out2/escape.txt
python -m tarx extract /tmp/tarx-demo/unsafe.tar /tmp/out2; echo "status=$?"
ls /tmp/out2
```

Expected: status `2` (not `3` — unusable input outranks a refused overwrite), **every** problem
reported one per line on stderr, stdout empty, and `/tmp/out2` still containing only your
`escape.txt` with its original contents.

## Scenario 8 — Discoverability (SC-009)

```bash
python -m tarx --help
python -m tarx extract --help
```

Expected: usage on **stdout**, exit `0`, naming both commands, `ARCHIVE`, `DEST`, and
`--overwrite` — no external documentation needed.

## Automated suite (the real gate)

The scenarios above are for eyes-on confirmation. The binding check is the full suite, which must
pass before any change is considered done (Constitution, Quality Gate 4):

```bash
python -m pytest            # pythonpath = ["src"] comes from pyproject.toml
```

Expect all tests green, including `tests/test_traceability.py`, which fails if any `FR-###` in
`spec.md` lacks a referencing test (FR-021 / SC-007). The requirement-to-test map is in
[data-model.md](./data-model.md#requirement-to-test-map).

## Scale checks (SC-008)

```bash
python - <<'PY'
import io, tarfile
with tarfile.open('/tmp/tarx-demo/many.tar', 'w') as tf:
    for i in range(10_000):
        info = tarfile.TarInfo(f'd{i // 100}/f{i}.txt'); info.size = 1
        tf.addfile(info, io.BytesIO(b'x'))
PY
time python -m tarx list /tmp/tarx-demo/many.tar | wc -l
```

Expected: `10000` lines in well under 5 seconds. For the larger-than-memory case, extract an
archive containing a file bigger than available RAM and confirm it succeeds — member bodies are
streamed through a fixed buffer, so resident memory stays flat.

## Cleanup

```bash
rm -rf /tmp/tarx-demo /tmp/out /tmp/out2 /tmp/out-empty /tmp/plain.txt
```
