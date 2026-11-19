# Phase 1 Data Model: Tar Archive Listing and Extraction CLI

**Feature**: `001-tarx-cli` | **Date**: 2026-11-19

The tool holds no persistent state. "Data model" here means the in-memory structures that carry a
run from argv to exit status, plus the validation rules attached to them. All of these live in
`src/tarx/core.py` except `Invocation`, which belongs to `src/tarx/cli.py`.

---

## Entities

### Invocation

Parsed command line. Produced by `argparse`, consumed by the dispatch in `cli.main`.

| Field | Type | Notes |
|-------|------|-------|
| `command` | `"list"` \| `"extract"` | FR-001; any other value is rejected by argparse before this exists |
| `archive` | `str` | Path as given; never normalised, so diagnostics echo what the user typed |
| `dest` | `str` \| absent | `extract` only |
| `overwrite` | `bool` | `extract` only; defaults to `False` (FR-009) |

No field is validated against the filesystem at parse time — FR-017 requires that an invalid
invocation read and write nothing.

---

### Archive

The opened input, i.e. a `tarfile.TarFile` obtained from `tarfile.open(path, "r:*")`, used as a
context manager. Read-only in every operation (spec Key Entities). Compression is determined by
content (FR-004). Failure to open maps to exit 2: a missing or unreadable path (FR-012) and a
non-tar, corrupt, or truncated file (FR-013) produce different messages but the same status.

---

### Member

One `tarfile.TarInfo` from the archive, interpreted through three derived values:

| Derived value | Definition |
|---------------|------------|
| `name` | `TarInfo.name` exactly as recorded, including any trailing `/` |
| `display_name` | `name` with trailing `/` stripped; falls back to `name` if that empties it — this is what `list` prints (FR-024) |
| `kind` | `FILE` if `TarInfo.isreg()`, `DIR` if `TarInfo.isdir()`, else `OTHER` (symlink, hardlink, char/block device, FIFO) |

Archive order is significant and observable (`list` preserves it, FR-002; duplicates win in order,
see `WritePlan`). `OTHER` members are never created (FR-015).

---

### MemberTarget

A member paired with its resolved destination, produced during validation.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | Source member's name, exactly as recorded. (Named `name` rather than `member` because `check_member_path` is handed the name, not the `TarInfo`; the `TarInfo` itself is carried by `WritePlan.files`, so holding it here too would be redundant) |
| `relative` | `str` | `os.path.normpath(name)` after the safety checks below |
| `target` | `str` | `os.path.join(dest, relative)` |

**Path safety rules** (FR-014; applied to every member regardless of `kind`, see
[research.md §3](./research.md#3-member-path-safety)). A member failing any rule yields a
`Problem` and is excluded from all further checks:

1. `name` MUST NOT be absolute.
2. `os.path.normpath(name)` MUST NOT be `..` and MUST NOT start with `..` + separator.
3. If `kind` is `FILE`, the normalised path MUST NOT be `.` or empty.

---

### Problem

One detected reason the run cannot proceed. Validation accumulates a list of these rather than
raising on the first (FR-025).

| Field | Type | Notes |
|-------|------|-------|
| `exit_class` | `2` \| `3` | Class 2 = unusable input; class 3 = refused overwrite |
| `message` | `str` | Full stderr line, per the templates in [contracts/cli.md](./contracts/cli.md) |

**Classification table** and its reasoning: [research.md §4](./research.md#4-conflict-and-type-mismatch-classification).

**Resolution rule**: exit `2` if any problem has `exit_class == 2`; else exit `3` if the list is
non-empty; else proceed to write (FR-025). Reporting order is destination-level problems first,
then member problems in archive order (FR-025, one per line).

---

### WritePlan

What validation hands to the write phase. Empty-but-valid is a success case (FR-018).

| Field | Type | Notes |
|-------|------|-------|
| `directories` | `list[tuple[str, str]]` | `(member name, target path)` for `DIR` members, archive order. The member name is carried because template D11 names the member being written, so a failed `makedirs` needs one in hand (FR-022) |
| `files` | `dict[str, Member]` | Keyed by target path, insertion-ordered, **last member wins** — this implements duplicate handling and makes each path written exactly once |
| `skipped` | `list[tuple[str, str]]` | `(name, kind-label)` for `OTHER` members, archive order; reported but harmless (FR-015) |

`N` in the summary line is `len(files)` — the number of distinct destination file paths written
(FR-008, FR-010; rationale in [research.md §6](./research.md#6-counting-n-for-extracted-n-files)).

---

### Outcome / exit status

The run's single machine-readable result (spec Key Entities). Constants in `core.py`:

| Constant | Value | Meaning |
|----------|-------|---------|
| `EXIT_OK` | `0` | Requested work completed (FR-016) |
| `EXIT_INPUT` | `2` | Unusable archive, destination, member path, or invocation; also a mid-write filesystem failure (FR-012…FR-014, FR-017, FR-019, FR-022, FR-023) |
| `EXIT_REFUSED_OVERWRITE` | `3` | Refused overwrite, and nothing worse (FR-009) |

Exactly one status per run; 2 outranks 3 (FR-025).

---

## Lifecycle

### `list ARCHIVE`

```text
parse argv ──▶ open archive ──▶ for each member: print display_name ──▶ exit 0
                    │
                    └── open/format failure ──▶ stderr diagnostic ──▶ exit 2
```

Nothing is written to disk; member bodies are never read.

### `extract ARCHIVE DEST [--overwrite]`

```text
parse argv
   │
   ├─▶ phase 1: open archive, check DEST and its ancestors, walk every member
   │              building MemberTargets, Problems and the WritePlan
   │              (no filesystem writes at all)
   │
   ├─ problems? ──▶ print every problem line to stderr ──▶ exit 2 or 3, destination untouched
   │
   └─▶ phase 2: makedirs(DEST), create planned directories, stream each planned file
                 │
                 ├─ OSError mid-write ──▶ stderr diagnostic naming the member, no summary ──▶ exit 2
                 │                        (files already written remain; FR-022)
                 │
                 └─▶ print skip notices to stderr, print "extracted N files" ──▶ exit 0
```

The hard boundary between phase 1 and phase 2 is FR-020: every failure the tool can detect is
found before the first byte is written.

---

## State transitions of a destination path

For one member target path, given the existing filesystem entry and the member's `kind`:

| Existing entry | Member `kind` = `DIR` | Member `kind` = `FILE` |
|----------------|----------------------|------------------------|
| nothing | create directory | create file, count it |
| directory | reuse, no conflict (FR-011) | **class 2** type mismatch (FR-023) |
| regular file | **class 2** type mismatch (FR-023) | `--overwrite` → replace and count (FR-010); otherwise **class 3** (FR-009) |
| other (symlink, FIFO, device) | **class 2** type mismatch (FR-023) | **class 2** type mismatch (FR-023) — `--overwrite` consents to replacing a regular file only |

Additionally, for every ancestor directory of a target path (between `DEST` and the target): an
existing non-directory entry there is a **class 2** problem, as is a regular-file member of the
same archive at that path (FR-023, FR-020).

---

## Requirement-to-test map

Principle III and FR-021 require this mapping to be explicit and auditable. Test IDs are the
requirement IDs, carried in test names and docstrings; `tests/test_traceability.py` asserts that
every `FR-###` appearing in `spec.md` is referenced by at least one test under `tests/`.

| Requirement | Covering test file | Focus of the covering test(s) |
|-------------|--------------------|-------------------------------|
| FR-001 | `test_errors.py` | both commands dispatch; unknown command → usage on stderr, non-zero exit |
| FR-002 | `test_list.py` | every member printed, one per line, archive order |
| FR-003 | `test_list.py` | directory and non-regular members present, unfiltered, unreordered |
| FR-004 | `test_list.py`, `test_extract.py` | gzip archive named `.tar` and plain archive named `.tar.gz` both work |
| FR-005 | `test_extract.py` | nested relative paths reproduced under `DEST` |
| FR-006 | `test_extract.py` | extracted bytes compared to source bytes, including a zero-length file |
| FR-007 | `test_extract.py` | missing `DEST` with missing parents created; existing `DEST` reused |
| FR-008 | `test_extract.py` | `extracted N files` is the only stdout line; plural at `N` = 0, 1, 2 |
| FR-009 | `test_overwrite.py` | no-flag conflict → zero files written, every conflicting path on stderr, exit 3 |
| FR-010 | `test_overwrite.py` | `--overwrite` replaces contents; replaced files counted in `N` |
| FR-011 | `test_extract.py` | pre-existing destination directory is not a conflict, with and without the flag |
| FR-012 | `test_errors.py` | missing archive path → path named on stderr, exit 2, both commands |
| FR-013 | `test_errors.py` | non-tar file and truncated archive → exit 2 |
| FR-014 | `test_errors.py`, `test_validation.py` | absolute and `..`-escaping members → nothing written, member named, exit 2 |
| FR-015 | `test_extract.py` | symlink/FIFO members skipped, named on stderr, excluded from `N`, exit 0 |
| FR-016 | `test_list.py`, `test_extract.py` | success → exit 0, empty stderr (where no skips), results only on stdout |
| FR-017 | `test_errors.py` | unknown command, missing operand, bad option → usage on stderr, non-zero, no filesystem touch |
| FR-018 | `test_list.py`, `test_extract.py` | empty archive → no output / `extracted 0 files`, exit 0 |
| FR-019 | `test_errors.py` | `DEST` is an existing regular file → exit 2, file unchanged |
| FR-020 | `test_overwrite.py`, `test_errors.py` | conflict at the last member → destination byte-identical to before |
| FR-021 | `test_traceability.py` | every FR ID in `spec.md` is referenced by a test |
| FR-022 | `test_errors.py` | write failure injected after writing begins → member named on stderr, no summary, exit 2 |
| FR-023 | `test_errors.py`, `test_validation.py` | dir-blocks-file, file-blocks-dir, file-blocks-parent; identical with and without `--overwrite` |
| FR-024 | `test_list.py` | directory member printed without trailing slash |
| FR-025 | `test_errors.py`, `test_validation.py` | multiple problems all reported, one per line; mixed 2-and-3 archive exits 2 |
