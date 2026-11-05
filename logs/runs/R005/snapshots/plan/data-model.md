# Phase 1 Data Model: Tar Archive List & Extract CLI

**Feature**: `001-tar-archive-cli` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

This feature has no persistent storage and no schema. The "data model" is the small set of
in-memory values that flow from the command line, through the archive, to the filesystem. Per
Principle IV (Simplicity) these are plain data — stdlib types and one tuple-like record — not
custom classes, except where a behavior requires otherwise.

## Entities

### Archive

The tar container named on the command line, optionally gzip-compressed.

| Aspect | Representation |
|---|---|
| Identity | `pathlib.Path` from the `ARCHIVE` argument |
| Runtime type | `tarfile.TarFile`, opened `mode="r:*"` (see research R2) |
| Contents | An ordered sequence of members; order is the archive's recorded order |
| Lifetime | Open for the duration of one subcommand, closed via `with` |

- **No custom wrapper type.** `tarfile.TarFile` already is the archive; wrapping it would be the
  speculative generality Principle IV prohibits.
- **Validation** (FR-024, all → exit 2): must exist, must be readable, must not be a directory,
  must parse as a tar archive. Enforced by catching `FileNotFoundError`, `IsADirectoryError`,
  `PermissionError`, `OSError`, and `tarfile.ReadError` around the open and around member parsing,
  then reporting the project's own one-line diagnostic (research R4).
- **No sorting, filtering, or de-duplication** is applied to the member sequence (FR-006).

### Member

One entry in an archive.

| Field | Source | Used for |
|---|---|---|
| `name` | `TarInfo.name` — recorded path, POSIX separators, no trailing `/` on directories (research R3) | `list` output (FR-005/008); extraction target path; diagnostics |
| kind | `TarInfo.isreg()` / `TarInfo.isdir()` | dispatch between write-file, make-directory, and skip |
| `size` | `TarInfo.size` | implicit; streaming copy reads to EOF |
| contents | `TarFile.extractfile(member)` — lazy file-like object | byte-identical file contents (FR-010) |

**Kind taxonomy** — exactly three cases, derived rather than stored:

| Kind | Predicate | `list` | `extract` |
|---|---|---|---|
| Regular file | `isreg()` | printed | written, counted |
| Directory | `isdir()` | printed | created, **not** counted |
| Other (symlink, hardlink, device, FIFO) | neither | printed (FR-007) | skipped silently, not counted (FR-016) |

- **Member name validation** (FR-026, → exit 2), purely lexical, no filesystem access:
  - rejected if `posixpath.isabs(name)`;
  - rejected if the name carries a Windows drive letter or UNC prefix;
  - rejected if `posixpath.normpath(name)` is `..` or starts with `../`.
  - Otherwise the normalized name is the member's path relative to the destination.
- Members of kind *other* are skipped before name validation is relevant to writing, but they are
  still listed, so `list` never rejects a name.

### Destination

The directory under which members are recreated. `extract` only.

| Aspect | Representation |
|---|---|
| Identity | `pathlib.Path` from the `DEST` argument |
| Pre-state | may not exist; may exist as a directory; may exist as a non-directory |

- **Validation** (FR-025, → exit 2): if the path exists and is not a directory, fail before doing
  anything else. If it does not exist, it is created with `mkdir(parents=True, exist_ok=True)`
  (FR-012) — but only once validation has passed, so a failed run leaves no new directories.
- Pre-existing entries that no member collides with are never touched (FR-013).

### ExtractionPlan (derived, transient)

Not a spec entity, but the design's one intermediate value: the result of reading all members and
deciding what to do, computed **before any write** so FR-020's "nothing created, modified,
truncated, or deleted" holds by construction.

```text
plan        : list of (member, target_path, kind)   # archive order preserved
skipped     : count of "other"-kind members          # dropped from the plan
violations  : member names failing containment       # → exit 2
collisions  : kind mismatches against existing paths # → exit 2
conflicts   : regular-file targets that already exist as regular files  # → exit 3 unless --overwrite
```

- Represented as plain lists/tuples built by one function; no class.
- **Validation order is fixed** (research R8): `violations` → exit 2, then `collisions` → exit 2,
  then `conflicts` → exit 3. Exit 2 outranks exit 3 so that status 3 always means "re-run with
  `--overwrite`".
- `collisions` also covers an **existing non-directory ancestor**: for each planned target, any
  path between the destination and the target that already exists and is not a directory is a
  collision, caught here rather than as a mid-write `NotADirectoryError`.

### WrittenSet (derived, transient)

A set of destination paths written during the write pass. `len(written)` is the `N` in
`extracted N files`.

- Exists because a path stored twice in one archive must contribute **once** to the count while the
  later entry's contents win (FR-015, Edge Cases "Duplicate member names"; research R9). A plain
  counter would over-report, so this is the minimum structure that satisfies the requirement.

## State transitions

`extract` is a two-phase pipeline. Phase boundaries are where the exit statuses are decided.

```text
          ┌──────────────── exit 2 ─────────────┐
          │                                     │
  argv ──▶ open archive ──▶ validate dest ──▶ build plan ──▶ writes ──▶ "extracted N files" ──▶ exit 0
                                                   │
                                                   ├─ containment violation ──▶ exit 2
                                                   ├─ kind collision ─────────▶ exit 2
                                                   └─ overwrite conflict ─────▶ exit 3   (no --overwrite)
```

- Everything left of `writes` is read-only with respect to the filesystem. Exit 2 and exit 3 from
  the planning phase therefore leave the destination byte-for-byte as it was (FR-020, SC-003).
- A failure *during* `writes` (for example `PermissionError` on a target, or a truncated archive)
  still reports a diagnostic and exits 2 rather than printing a success line (Edge Cases "Partial
  write interrupted by an error"). Files already written are left in place; the spec does not
  require rollback.

`list` has a single phase: open, iterate, print, exit 0 — or exit 2 from the open/iterate step.

## Error record

One internal exception type carries every specified failure, so the entry point has exactly one
place that formats diagnostics and chooses a status.

| Field | Meaning |
|---|---|
| message | human-readable, one line, names the offending path or member (FR-027) |
| code | `2` or `3` (FR-028) |

- `0` is never carried by an error; success returns it directly.
- A class is used here, rather than a tuple, because Python's `raise` requires an exception type —
  the one place Principle IV's "prefer a plain data structure" is overridden by the language.
- Exit statuses are named constants (`EXIT_OK = 0`, `EXIT_ERROR = 2`, `EXIT_CONFLICT = 3`) so that
  FR-028's "consistently and exclusively" is checkable by reading the three definitions.
