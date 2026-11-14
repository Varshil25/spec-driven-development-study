# Phase 1 Data Model: Create Tar Archives (`create` command)

**Feature**: `002-create-archive-command` | **Date**: 2026-11-12 | **Spec**: [spec.md](./spec.md)

There is no database and no persisted state. The "data model" is the small set of in-memory
values `create` builds between reading the command line and writing the archive, plus the
validation rules that govern them. Rule numbering continues from
[`001-tarx-cli/data-model.md`](../001-tarx-cli/data-model.md); nothing in that document changes.

---

## 1. `SourcePath` — one PATH as given on the command line

| Field | Type | Meaning |
|---|---|---|
| `given` | `str` | the PATH exactly as the user typed it, kept for messages (FR-113) |
| `components` | `tuple[str, ...]` | the surviving components after normalisation (FR-104) |
| `name` | `str` | `"/".join(components)` — the member name this PATH contributes |

Derived, never mutated. `given` is the only value ever printed (through `escape_name`);
`components` is the only value ever used to touch the filesystem. `./photos/` and `photos`
produce different `given` values and identical `components`, which is what FR-104 requires.

**Entity mapping**: the spec's *Source path (PATH)*.

---

## 2. `PlannedMember` — one entry to be recorded in the archive

| Field | Type | Meaning |
|---|---|---|
| `name` | `str` | the member name, `/`-joined relative path, no trailing slash (FR-104) |
| `kind` | `Literal["file", "dir"]` | nothing else is representable (SR-102) |
| `path` | `Path` | the location on disk to read, relative to the current directory |
| `size` | `int` | `st_size` at enumeration time; `0` for a directory |
| `origin` | `str` | the `given` PATH this member came from, for duplicate messages (SR-104) |

`kind` is a closed two-value set by construction: enumeration refuses everything that is not a
regular file or a directory (rule 4 below), so there is no third case to handle downstream. A
directory's `size` is zero because a directory member carries no content.

`size` is the value the *bounds* are checked against (rule 6). It is **not** the value written
into the header: the header takes the size from `os.fstat` on the open descriptor at write time,
and a disagreement between the two is FR-120's failure (rule 9).

**Entity mapping**: the spec's *Member*.

---

## 3. `CreationPlan` — the complete, validated set of members

| Field | Type | Meaning |
|---|---|---|
| `members` | `list[PlannedMember]` | every member, in the exact order they will be written (FR-106) |
| `file_count` | `int` | members with `kind == "file"` — the `N` of the success line (FR-111) |
| `total_bytes` | `int` | sum of `size` over file members, bounded by rule 6 |

Built by a pass that writes nothing. Its completion is the boundary FR-118 demands: by the time
a `CreationPlan` exists, every check in rules 1–8 has passed.

`file_count` is computed here rather than counted during writing, so the number reported on
success is the number that was validated (FR-110, FR-111).

**Entity mapping**: the spec's *Source tree*, flattened — the spec says a source tree is
"flattened into members during validation", and `CreationPlan.members` is that flattening.

---

## 4. `ArchiveTarget` — the decision about where the archive goes

| Field | Type | Meaning |
|---|---|---|
| `given` | `str` | ARCHIVE as the user typed it; echoed on the success line (FR-110) |
| `path` | `Path` | the normalised output path |
| `compressed` | `bool` | `True` iff `given` ends in `.tar.gz`/`.tgz`, case-insensitively (FR-108) |
| `replacing` | `bool` | `True` iff a regular file is there and `--overwrite` was given (FR-115) |

Classified by a single `os.lstat` before any other work (research R-105). Every state other than
"absent with a usable parent directory" and "regular file" is a rule-7 failure.

Until the final rename succeeds, **no archive exists at `path`** — the spec's *Output archive*
entity says exactly this, and R-104's temporary file is what makes it true.

**Entity mapping**: the spec's *Output archive (ARCHIVE)*.

---

## 5. `CreationResult` — what the caller gets

Not a class: `create_archive()` returns `int`, the count of regular files added, and raises on
every failure. Success is `(N, exit 0)`; failure is `(message on stderr, exit 2 or 3, no
archive)`. Representing failure as an exception rather than a return value is what keeps the
success line unreachable on a failing run (FR-112) — `cli.main` is the only place a status is
chosen, as in 001.

**Entity mapping**: the spec's *Creation result*.

---

## 6. Validation rules, in execution order

The order is normative: the **first** failure wins, and its message is the one the operator
sees. Rules 1–8 all run before any content is written (FR-118).

| # | Rule | Raised as | Requirement |
|---|---|---|---|
| 1 | ARCHIVE and every PATH are non-empty; exactly one ARCHIVE; at least one PATH; the only option is `--overwrite` | usage message, exit 2 | FR-102, SR-112 |
| 2 | Each PATH is relative, free of `..`, has no leading `/` or `\`, has no drive prefix, and normalises to a non-empty component tuple (so `.` and `..` are refused) | `TarxError`, exit 2 | SR-101 |
| 3 | ARCHIVE's state is classified: absent + usable parent → proceed; regular file + `--overwrite` → replace; regular file without `--overwrite` → **exit 3**; anything else (directory, symlink, FIFO, device, socket, missing parent) → exit 2 | `OverwriteConflict` / `TarxError` | FR-114, FR-115, FR-116 |
| 4 | Each PATH exists (`os.lstat`) and is a regular file or a directory; so is every entry found beneath a directory PATH. A symlink, hard link, device, FIFO, or socket is refused, naming the member and its kind — never skipped, never followed | `TarxError`, exit 2 | FR-117, SR-102, SR-103 |
| 5 | A candidate whose normalised path equals ARCHIVE's is omitted when found by traversal, and refused when named directly as a PATH | `TarxError`, exit 2 (direct case only) | SR-109 |
| 6 | Member count ≤ `MAX_MEMBERS` (10,000); each file `size` ≤ `MAX_MEMBER_BYTES` (1 GiB); running total ≤ `MAX_TOTAL_BYTES` (1 GiB) — checked as each member is appended, so the cap fires before the whole tree is walked | `TarxError`, exit 2 | SR-105 |
| 7 | No two members carry the same `name`; the message names the duplicated member and both origins | `TarxError`, exit 2 | SR-104 |
| 8 | Every computed member name is accepted by the existing `paths.validate_member_name` — the gate `extract` itself applies | `TarxError`, exit 2 | FR-109, R-112 |
| 9 | At write time, each file's `os.fstat` size is what the header declares; the stream delivers exactly that many bytes and no more | `TarxError`, exit 2, no archive | FR-107, FR-120 |
| 10 | Actual bytes streamed stay within `MAX_MEMBER_BYTES` and `MAX_TOTAL_BYTES` | `TarxError`, exit 2, no archive | SR-105 |
| 11 | ARCHIVE's state is re-confirmed immediately before the rename | `OverwriteConflict` / `TarxError` | FR-114 |

Rules 9–11 are the only ones that run after writing has begun, and none of them can leave an
archive behind: the writing happens in a temporary file that is unlinked unless rule 11 passes
(FR-119).

---

## 7. Member header fields — fixed, never read from disk

| Field | Value | Requirement |
|---|---|---|
| `name` | the member name from `PlannedMember.name` | FR-104 |
| `type` | `REGTYPE` or `DIRTYPE` only | SR-102 |
| `size` | `os.fstat` size on the open descriptor; `0` for directories | FR-107, FR-120 |
| `mode` | `0o644` (file) / `0o755` (directory) — fixed, no setuid/setgid/sticky bit possible | SR-108 |
| `uid`, `gid` | `0`, `0` | SR-108 |
| `uname`, `gname` | `""`, `""` | SR-108 |
| `mtime` | `0` | SR-108, FR-106 (determinism) |
| `linkname` | `""` — no member can be a link | SR-102 |

The on-disk `st_mode`, `st_uid`, `st_gid`, and `st_mtime` are read by `create` only to answer
"what kind of thing is this and how big is it". No part of them reaches the archive, which is
why `TarFile.add()`/`gettarinfo()` is never used (research R-101).

The gzip container, when used, carries `filename=""` and `mtime=0` for the same reason
(research R-103).

---

## 8. State transitions

The archive path has exactly three observable states and only two legal transitions:

```text
absent ──────────────── rename ───────────────► complete archive       (FR-110)
regular file (old) ──── rename (--overwrite) ──► complete archive       (FR-115)
regular file (old) ──── any failure ───────────► regular file (old)     (FR-119, SC-106)
absent ──────────────── any failure ───────────► absent                 (FR-119, SC-106)
```

There is no "partially written" state, and no state in which a temporary file survives the
command. The directory containing ARCHIVE holds one extra entry only between `mkstemp` and
`rename`/`unlink`, both inside the same `try/finally`.

Everything named by a PATH is **read-only** throughout: `create` performs no write syscall
against any source path (FR-122).

---

## 9. Relationship to the 001 model

| 001 entity | Relationship |
|---|---|
| `PlannedEntry` (extract) | `PlannedMember` is its mirror image — one validated unit, named before it is acted on. They are deliberately separate types: `PlannedEntry` carries a `TarInfo` read *from* an archive and a destination path, `PlannedMember` carries a source path and the header fields to be written. |
| `TarxError` / `OverwriteConflict` | Reused unchanged. `create` adds the package's second `OverwriteConflict` raise site (the archive-exists check), so that class's docstring is updated from "exactly one raise site" to name both; the exit statuses themselves are untouched. |
| `MAX_MEMBERS`, `MAX_TOTAL_BYTES`, `MAX_MEMBER_BYTES`, `COPY_CHUNK_BYTES` | Imported from `tarx.archive`, not redefined, so SR-105's "the same bounds" is structural. |
| `escape_name`, `validate_member_name`, `_components` | Reused unchanged; `validate_source_path` is added beside them. |
