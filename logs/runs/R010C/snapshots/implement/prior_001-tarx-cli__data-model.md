# Phase 1 Data Model: Tar Archive Listing and Extraction Tool

**Feature**: `001-tarx-cli` | **Date**: 2026-11-12 | **Spec**: [spec.md](./spec.md)

This feature has no database and no persisted state. The "data model" is the set of
in-memory values that flow from command line → archive header → destination path, plus the
validation rules attached to each. Rules trace to the requirement that imposes them.

---

## 1. `Invocation`

Parsed command-line input. Produced by `cli.parse_args`, consumed by the operations.

| Field | Type | Notes |
|---|---|---|
| `command` | `"list" \| "extract"` | Required; anything else is a usage error (FR-001) |
| `archive` | `str` | Path to the archive, as given |
| `dest` | `str \| None` | Present only for `extract` |
| `overwrite` | `bool` | `extract` only; default `False` |

**Validation**

- `command` must be exactly one of the two values; a missing, unknown, or extra argument, or
  an unknown option, is a usage error → stderr + exit 2 (FR-001, SR-010).
- `archive` and `dest` must be non-empty strings (SR-010).
- `--overwrite` is the only accepted option, and only on `extract` (SR-010).
- Values are used as filesystem paths directly; they are never interpolated into a shell
  command or any other string-built interface (SR-010, Security Baseline).

**No state transitions.** An `Invocation` is immutable once parsed.

---

## 2. `Archive`

The opened input. Not a stored record — a handle plus the facts derived from its first bytes.

| Field | Type | Notes |
|---|---|---|
| `path` | `Path` | The archive as named on the command line |
| `compression` | `"gzip" \| "none"` | Determined from the leading magic bytes, never the filename (FR-008) |
| `tar` | `tarfile.TarFile` | Opened `"r:gz"` or `"r:"` accordingly |

**Validation**

- Must exist and be readable; otherwise error naming the archive → exit 2 (FR-013).
- Must be a valid tar archive, including not truncated and not corrupt → exit 2 (FR-013).
  Invalidity may surface at open time *or* partway through iteration, so both are guarded.
- An archive with zero members is **valid**, not an error (FR-018).

**Treated as untrusted in its entirety** — names, types, and declared sizes alike
(spec Key Entities, Security Baseline "Untrusted input").

---

## 3. `Member`

One archive entry, as reported by the header. Backed by `tarfile.TarInfo`; the fields below
are the only ones this feature reads.

| Field | Source | Notes |
|---|---|---|
| `name` | `TarInfo.name` | A path as recorded in the archive; arbitrary bytes-as-text |
| `kind` | `isreg/isdir/issym/islnk/ischr/isblk/isfifo` | Mapped to `file`, `dir`, or a rejected kind |
| `size` | `TarInfo.size` | **Declared** size in bytes; may understate reality (SR-005) |
| `contents` | `TarFile.extractfile(...)` | A stream, read in chunks; never materialised whole (SC-007) |

**Deliberately ignored**: recorded permission bits, ownership (uid/gid/uname/gname),
timestamps, extended attributes, and sparse-file layout (SR-006, spec Assumptions).

**Member kind classification**

| Classification | Accepted by `extract`? | Accepted by `list`? |
|---|---|---|
| regular file | yes | yes |
| directory | yes | yes |
| symbolic link | **no** — exit 2, naming the member (SR-002) | yes |
| hard link | **no** — exit 2, naming the member (SR-002) | yes |
| char device, block device, FIFO, socket, any other | **no** — exit 2, naming the member (SR-003) | yes |

`list` prints every member regardless of kind and never touches the filesystem (FR-003); the
asymmetry is intentional — listing is the safe way to inspect an untrusted archive.

---

## 4. `Destination`

The single boundary inside which every extracted path must fall.

| Field | Type | Notes |
|---|---|---|
| `root` | `Path` | `DEST` as given, made absolute once up front |

**Validation**

- If `root` exists and is not a directory → exit 2 (FR-007).
- If absent, `root` and any missing parents are created with mode `0o700` (FR-007, SR-006).
- If it cannot be created or written to → exit 2 (FR-007).
- `root` is created **before** member validation, so an empty archive still yields a created
  `DEST` plus `extracted 0 files` (FR-018).
- A symlinked `DEST` supplied by the user is honoured — the user chose the boundary. What is
  refused is a symlink *inside* the boundary (SR-004).

---

## 5. `PlannedEntry`

One validated, ready-to-write unit. Pass 1 produces a list of these; Pass 2 consumes it.
Nothing is written until the whole list exists (FR-014).

| Field | Type | Notes |
|---|---|---|
| `member_name` | `str` | Raw name, kept for error messages (escaped at print time per SR-007) |
| `kind` | `"file" \| "dir"` | Only these two reach Pass 2 |
| `dest_path` | `Path` | `Destination.root` joined with the validated relative path |
| `declared_size` | `int` | `0` for directories |
| `tarinfo` | `tarfile.TarInfo` | Handle used by Pass 2 to open the content stream |
| `exists_as_file` | `bool` | True when overwriting an existing regular file (`--overwrite`) |

**Validation rules applied while building an entry** — in this order, first failure wins:

1. **Name shape** (SR-001): non-empty; not absolute (`/…`); no leading backslash (covers
   `\…` and `\\server\share`); no `^[A-Za-z]:` drive prefix; no `..` component.
   `.` components are dropped, not refused (`tar -cf` conventionally emits `./x`).
2. **Containment** (SR-001): the mapped path must equal `root` or lie under it, checked
   lexically with `os.path.normpath` — never with `resolve()`, which would follow symlinks
   and mask the very escape SR-004 guards.
3. **Kind** (SR-002, SR-003): must be regular file or directory; anything else is refused by
   name and kind.
4. **Resource bounds** (SR-005), incrementally: member index < 10,000; `declared_size` ≤
   1 GiB; running total of declared sizes ≤ 1 GiB.
5. **No symlink in the path** (SR-004): no component of `dest_path` at or below `root` may be
   an existing symlink (`os.path.islink`).
6. **Uniqueness** (SR-009): `dest_path` must not already be claimed by an earlier member;
   the mapped path is compared, so `a/b`, `./a/b`, and `a//b` collide as they should.
7. **Destination state** (FR-009, FR-011, FR-012) via `os.path.lstat` — never `stat`, so a
   symlink is seen as itself:

   | kind | existing state | outcome |
   |---|---|---|
   | file | absent | plan a write |
   | file | regular file, no `--overwrite` | **exit 3**, naming the first such path (FR-009) |
   | file | regular file, with `--overwrite` | plan a truncating rewrite (FR-010) |
   | file | directory | **exit 2**, type conflict (FR-011) |
   | file | symlink or other | **exit 2** (SR-004, SR-003) |
   | dir | absent | plan a `mkdir` |
   | dir | directory | reuse silently — not a conflict (FR-012) |
   | dir | regular file or other | **exit 2**, type conflict (FR-011) |

---

## 6. `ExtractionResult`

What a successful `extract` reports.

| Field | Type | Notes |
|---|---|---|
| `files_written` | `int` | Count of **regular files** written; directories excluded (FR-019) |

Rendered as exactly `extracted {files_written} files\n` on stdout — no pluralisation, for
every value including `0` and `1` (FR-006, FR-018, spec Assumptions). A failing command never
prints this line (FR-016).

---

## 7. Error model

| Type | `exit_code` | Raised for |
|---|---|---|
| `TarxError` | `2` | Every failure except an overwrite conflict: unreadable or invalid archive, unusable destination, rejected member name/kind, symlink in path, duplicate destination, exceeded bound (FR-013, FR-015) |
| `OverwriteConflict(TarxError)` | `3` | **Only** an existing regular file with no `--overwrite` (FR-009, FR-015) |

**Invariants**

- Each carries a single-line, operator-actionable `message` naming the archive path, member
  name, or destination path at issue (FR-017), with member names escaped per SR-007.
- Messages never contain member contents, environment values, or any data beyond paths and
  reasons; no stack trace reaches stderr for any specified failure (SR-008).
- `exit_code` 3 has exactly one raise site, which is what makes FR-009's "refused *solely*
  because of overwrite" structurally true rather than conventional.
- Exactly one handler, in `cli.main`, turns a `TarxError` into stderr output plus a return
  code. No other code path chooses an exit status, so FR-015's "no other exit status may be
  produced" is checkable by reading one function.

---

## 8. Resource bounds (constants, not configuration)

| Constant | Value | Requirement |
|---|---|---|
| `MAX_MEMBERS` | 10,000 | SR-005 |
| `MAX_TOTAL_BYTES` | 1 GiB (`1 << 30`) | SR-005 |
| `MAX_MEMBER_BYTES` | 1 GiB (`1 << 30`) | SR-005 |
| `COPY_CHUNK_BYTES` | 64 KiB | SC-007 (bounded memory) |

Declared sizes are checked in Pass 1, before any write. Bytes **actually read** are counted
again in Pass 2's copy loop against the same two size bounds, so an archive whose headers
understate its real size is still stopped. That abort is the single documented case where the
destination may be left partially written, and its message says so (SR-005, SC-006).

Not user-configurable, by decision recorded in the spec's Assumptions and under
Principle IV.

---

## 9. Lifecycle

```
Invocation ──parse/validate──► (archive path, dest path, overwrite flag)
     │
     ├─ list:    Archive ──lazy iterate, bounds──► Member.name ──escape──► stdout
     │                                                                     (no writes)
     └─ extract: Destination created
                 Archive ──lazy iterate, bounds──► Member ──validate──► [PlannedEntry]
                                                                            │
                                     ─── nothing written before this line ──┘
                                                                            ▼
                      mkdir 0o700 / os.open(…O_NOFOLLOW, 0o600) + chunked copy
                                                                            ▼
                                                           ExtractionResult ──► stdout
```

Any failure before the "nothing written" line leaves the destination contents byte-for-byte
unchanged (FR-014, SC-006). The only exception is an SR-005 actual-byte abort during the
write phase, which reports the possible partial extraction.
