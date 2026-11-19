# Quickstart & Validation Guide: `tarx create`

**Feature**: `002-create-command` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

Runnable scenarios that prove the feature works end to end. Each maps to the user stories and
success criteria in [spec.md](./spec.md); the exact strings and statuses are normative in
[contracts/create-contract.md](./contracts/create-contract.md), and the design rationale is in
[research.md](./research.md) and [data-model.md](./data-model.md).

This is a validation guide, not an implementation guide. It contains no production code and no test
bodies — those belong to `tasks.md` and the implementation phase.

## Prerequisites

- Python **3.11+** (developed and verified on CPython 3.13.17). Standard library only; nothing to
  install for the program itself.
- `pytest` for the test suite (test-time only, never imported by runtime code).
- Optional, for the independent-reader checks: system GNU `tar` and `gzip`. Scenario 3 skips
  gracefully without them, as 001's `gnu_tar_dir_archive` fixture already does.

```bash
cd <repo root>
python -m pytest -q          # baseline before this feature: 63 passed, 2 skipped
```

`pytest.ini` already sets `pythonpath = src` and `testpaths = tests`, so a bare `pytest` works from
the repository root. Running the CLI directly needs `src` on `PYTHONPATH`:

```bash
export PYTHONPATH="$PWD/src"
```

## Setup: a known source tree

Every scenario below runs inside a scratch directory, because `create` names members relative to
the current directory.

```bash
mkdir -p /tmp/tarx-demo && cd /tmp/tarx-demo
mkdir -p photos/raw photos/empty
printf 'AAA'  > photos/a.jpg
printf 'BBBB' > photos/b.jpg
printf 'R'    > photos/raw/r.cr2
printf ''     > photos/zero.bin
printf 'notes' > notes.txt
```

Four regular files, one empty directory, one zero-length file.

---

## Scenario 1 — Create, compressed and plain (US1, SC-009, SC-011, SC-012)

```bash
python -m tarx create photos.tar.gz photos notes.txt
python -m tarx create photos.tar    photos notes.txt
```

Expected, for each command:

- stdout exactly `created photos.tar.gz with 5 files` / `created photos.tar with 5 files`
- stderr empty, exit status `0`
- the count is 5: four files under `photos` plus `notes.txt`; the two directory members and the
  empty directory are **not** counted (FR-039)

Check the compression form was chosen by name alone (FR-040 … FR-042, SC-012):

```bash
gzip -t photos.tar.gz && echo "gzip OK"       # exit 0
head -c2 photos.tar | xxd                     # NOT 1f 8b
python -m tarx create bundle photos           # no recognised suffix → plain tar
```

---

## Scenario 2 — The round trip (US2, SC-010, FR-047, FR-048)

```bash
python -m tarx list photos.tar.gz
python -m tarx extract photos.tar.gz out/
diff -r photos out/photos && diff notes.txt out/notes.txt && echo "identical"
test -d out/photos/empty && echo "empty directory survived"
```

Expected `list` output, in exactly this order (FR-034, FR-035) — note `photos` and `photos/empty`
appear **without** a trailing separator:

```text
photos
photos/a.jpg
photos/b.jpg
photos/empty
photos/raw
photos/raw/r.cr2
photos/zero.bin
notes.txt
```

Expected `extract`: stdout `extracted 5 files`, stderr empty, exit `0` — the same count `create`
reported (FR-048). Repeating both commands against `photos.tar` must give byte-identical output.

This scenario was run against the real, unmodified `list` and `extract` during Phase 0; the
observed results are tabulated at the end of [research.md](./research.md).

---

## Scenario 3 — Verified by a reader that is not this tool (SC-009, SC-012)

```bash
tar -tf  photos.tar
tar -tzf photos.tar.gz
tar -xzf photos.tar.gz -C verify/ && diff -r photos verify/photos
```

Expected: GNU `tar` lists the same entries and extracts byte-identical contents. **Directory
entries appear as `photos/` and `photos/empty/`** — tar's universal convention for directory
headers, which this tool's own `list` strips. File names match character for character. See
[research R17](./research.md#r17--directory-member-names-the-trailing-separator-and-the-archive-format)
before reading this as an FR-034 violation.

---

## Scenario 4 — Overwrite protection (US3, SC-013)

```bash
cp photos.tar guard.tar
sha256sum guard.tar > before.txt

python -m tarx create guard.tar photos ; echo "exit=$?"
sha256sum -c before.txt
```

Expected: a diagnostic on stderr naming `guard.tar`, stdout **empty**, exit `3`, and the checksum
still matches — the existing archive is byte-for-byte untouched (FR-043).

```bash
python -m tarx create guard.tar notes.txt --overwrite ; echo "exit=$?"
python -m tarx list guard.tar                      # now just: notes.txt
python -m tarx create fresh.tar notes.txt --overwrite ; echo "exit=$?"   # 0, no complaint
mkdir adir && python -m tarx create adir photos --overwrite ; echo "exit=$?"
```

Expected: `--overwrite` replaces the regular file (exit `0`, FR-044); `--overwrite` on a
non-existent archive is accepted silently (exit `0`, FR-046); an archive path that is a **directory**
fails with exit `2` and leaves the directory alone, with or without the flag (FR-045).

---

## Scenario 5 — Failures are loud, scriptable, and leave nothing behind (US4, SC-014)

Each command must print a one-line diagnostic naming the offending path to stderr, print nothing to
stdout, and create no archive.

```bash
python -m tarx create other.tar missing-folder            ; echo "exit=$? "; ls other.tar
python -m tarx create other.tar photos missing-folder     ; echo "exit=$? "; ls other.tar
python -m tarx create other.tar /etc/passwd               ; echo "exit=$?"
python -m tarx create other.tar ../outside                ; echo "exit=$?"
python -m tarx create other.tar .                         ; echo "exit=$?"
python -m tarx create nodir/other.tar photos              ; echo "exit=$? "; ls -d nodir
python -m tarx create other.tar                           ; echo "exit=$?"
python -m tarx create other.tar photos --bogus            ; echo "exit=$?"
```

| Command | Status | Must also hold |
|---|---|---|
| missing source | `2` | `other.tar: No such file` — no archive created (FR-050) |
| one of several sources missing | `2` | no archive created even though `photos` was valid (FR-051) |
| absolute source path | `2` | FR-052 |
| source reaching outside the current directory | `2` | FR-052 |
| the current directory as a source | `2` | FR-052 / [research R19](./research.md#r19--sourcepath-containment-and-the-current-directory-as-a-source) |
| archive's parent directory missing | `2` | `nodir` is **not** created (FR-053) |
| no source paths | `2` | `argparse` usage guidance on stderr (FR-031) |
| unknown option | `2` | `argparse` usage guidance on stderr (FR-031) |

The combined case FR-056 singles out:

```bash
python -m tarx create guard.tar missing-folder --overwrite ; echo "exit=$?"
sha256sum guard.tar     # unchanged from before the command
```

Expected: exit `2`, not `3` — status 2 outranks status 3 — and `guard.tar` byte-for-byte unchanged,
because validation completes before the archive is ever opened
([research R18](./research.md#r18--all-validation-must-precede-opening-the-archive)).

Permission cases (FR-053 unwritable location, FR-054 unreadable source) behave the same way but
**cannot be exercised as `root`**, which bypasses mode bits. Their tests skip on
`os.geteuid() == 0`, following the pattern already in `tests/test_failures.py`
([research R24](./research.md#r24--permissiondenied-cases-are-untestable-as-root)).

---

## Scenario 6 — Edge cases worth seeing once

```bash
mkdir hollow && python -m tarx create hollow.tar hollow
# → "created hollow.tar with 0 files", exit 0, and `list hollow.tar` prints `hollow`

python -m tarx create photos/inside.tar photos
python -m tarx list photos/inside.tar | grep inside.tar   # no match: the archive is not inside itself

python -m tarx create trail.tar photos/
# → identical members to `create trail.tar photos`

ln -s a.jpg photos/link.jpg && mkfifo photos/pipe
python -m tarx create skip.tar photos
# → the link and the FIFO are skipped silently and not counted; exit 0
```

| Edge case | Expected | Requirement |
|---|---|---|
| directory with no files | `created hollow.tar with 0 files`, exit `0`, directory member present | FR-039, US1 §6 |
| archive written inside a named directory | archive absent from its own member list | FR-037 |
| trailing separator on a source path | identical member names | FR-034 |
| symlink / FIFO in the tree | skipped, uncounted, run still succeeds | FR-036 |
| zero-length file | stored as an empty member and **counted** | FR-032, FR-039 |
| same path named twice | stored twice, counted twice; `extract` then reports the lower count | [research R22](./research.md#r22--counting-regularfile-members-and-the-fr048-countequality-ambiguity) |

---

## Scenario 7 — Performance (SC-017)

```bash
python - <<'EOF'
import pathlib
for i in range(100):
    d = pathlib.Path(f"big/d{i:03d}"); d.mkdir(parents=True, exist_ok=True)
    for j in range(100): (d/f"f{j:03d}.txt").write_bytes(b"payload")
EOF
time python -m tarx create big.tar    big
time python -m tarx create big.tar.gz big
```

Expected: 10,000 files in well under the 30 s budget — Phase 0 measured **0.97 s** plain and
**1.98 s** gzip for 10,001 files on this machine
([research R23](./research.md#r23--performance-sc017)). Memory must not grow with the size of the
largest member: `tarfile` streams each member in `bufsize` chunks.

---

## Acceptance checklist

The implementation is complete only when all of the following hold (Constitution Principle III and
*Development Workflow & Quality Gates*):

- [ ] **The pre-existing suite passes unmodified** — `python -m pytest -q` still reports the 001
      tests green with zero edits to their expected stdout, stderr, or exit statuses (FR-049,
      SC-015). Baseline to match: 63 passed, 2 skipped.
- [ ] Every requirement **FR-029 … FR-056** has at least one `pytest` test that fails when the
      requirement is unmet, traceable by requirement identifier in the test name or docstring
      (SC-016).
- [ ] Every failure case in Scenario 5 asserts **both** the non-empty stderr diagnostic naming the
      offending path **and** the exact exit status — never merely "it failed" (Principle II).
- [ ] No test observes an uncaught traceback on stderr, for any input (FR-055).
- [ ] Scenarios 1–7 above all behave as stated.
- [ ] Runtime imports in `src/tarx/` resolve only to the standard library and this package
      (Principle I); `pytest` appears in no runtime import.
- [ ] No structure beyond the minimum: no new module, no new package, no new exception type, no
      configuration surface — or any addition justified in writing in [plan.md](./plan.md)
      (Principle IV, [research R25](./research.md#r25--where-the-code-lives)).
- [ ] The three decisions this plan made where the specification was silent (`.` as a source path,
      `--overwrite` onto a non-regular file, the FR-048 count-equality scope) are each covered by a
      test asserting the chosen behavior, so a future spec amendment would show up as a failing
      test rather than a silent drift.
