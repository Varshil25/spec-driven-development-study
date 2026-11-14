# Data Model: Tar Archive Create Command

**Feature**: `002-create-command` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

This feature has no persistent data store and no schema. "Data model" here means the three
entities the specification names, the shape each one takes in the running program, and the
validation rules and ordering that govern them. It is the reference the contract's exit statuses
and diagnostics are derived from.

Per Constitution Principle IV, **no entity is given a class of its own**. Each is either a plain
string, a stdlib object (`TarInfo`, `TarFile`), or a tuple of those. The only class involved is the
pre-existing `TarxError`, reused unchanged from 001.

---

## Entity: Archive

The tar container being written, identified by the path the user typed.

| Attribute | Representation | Source | Requirements |
|---|---|---|---|
| Typed path | `str`, exactly as given on the command line | `args.archive` | FR-030, FR-038 |
| Compression form | `bool` derived from the typed path's lower-cased suffix | `path.lower().endswith((".tar.gz", ".tgz"))` | FR-040, FR-041, FR-042 |
| Write mode | `"w:gz"` when compressed, else `"w"` | derived from the above | FR-040, FR-041 |
| Prior existence | `Path(path).exists()` | filesystem, read-only | FR-043, FR-046 |
| Prior kind | `Path(path).is_dir()`, `Path(path).is_file()` | filesystem, read-only | FR-044, FR-045 |
| Open handle | `tarfile.TarFile` | `tarfile.open(path, mode)` | FR-032, FR-033 |

**Invariants**

1. The typed path is never normalised, resolved, or rewritten. The summary line echoes it verbatim
   (FR-038), so `./photos.tar` prints as `./photos.tar`.
2. The compression form depends on the typed path **only** — never on any source path's name or
   content (FR-042).
3. The archive is never a member of itself (FR-037). Guaranteed by `TarFile.add`'s comparison of
   `os.path.abspath(name)` against `TarFile.name`, not by code in this project
   ([research R14](./research.md#r14--the-archive-is-never-stored-inside-itself)).
4. The archive file is **created or truncated at open time**, which is therefore the first
   observable filesystem effect of a `create` run. Every validation rule below runs before it
   ([research R18](./research.md#r18--all-validation-must-precede-opening-the-archive)).

### Archive target validation

Evaluated in this order, before the archive is opened. Each row's condition is checked against the
filesystem but writes nothing.

| # | Condition | Outcome | Requirement |
|---|---|---|---|
| A1 | Path exists and is a directory | exit 2, diagnostic names the path; applies with and without `--overwrite` | FR-045 |
| A2 | Path exists and `--overwrite` not given | exit 3, diagnostic names the path; the existing file is left byte-for-byte unmodified | FR-043 |
| A3 | Path exists, `--overwrite` given, and it is not a regular file | exit 2, diagnostic names the path | FR-044 (gap resolved in [research R20](./research.md#r20--the-archive-paths-prior-existence-and-kind-exit-2-versus-exit-3)) |
| A4 | Path does not exist | proceed; `--overwrite` is accepted without complaint | FR-046 |
| A5 | `tarfile.open` raises `OSError` (missing parent directory, not writable, …) | exit 2, diagnostic names the path | FR-053 |

A1 precedes A2 because FR-056 gives status 2 priority over status 3, so status 3 always means
"re-run with `--overwrite`".

---

## Entity: Source path

One path named on the command line, relative to the current directory.

| Attribute | Representation | Source | Requirements |
|---|---|---|---|
| Typed path | `str`, as given | `args.paths[i]` | FR-030 |
| Normalised relative path | `str` from `posixpath.normpath(typed)` | derived, purely lexical | FR-034, FR-052 |
| Kind | not recorded; `TarFile.add` re-stats each entry as it walks | filesystem | FR-032, FR-033, FR-036 |

**Invariants**

1. The *typed* path appears in diagnostics (so the message echoes what the user wrote); the
   *normalised* path becomes the `arcname`, and hence the recorded member name (FR-034).
2. Normalisation is purely lexical — no `realpath`, no `Path.resolve()`, no filesystem access. A
   symbolic link is therefore never followed to decide containment; it is skipped as a member
   instead (FR-036), which closes the same hole from the other side
   ([research R19](./research.md#r19--sourcepath-containment-and-the-current-directory-as-a-source)).
3. Order is significant: paths are processed in command-line order (FR-035), and validation reports
   the **first** offending path in that order.
4. No de-duplication. The same path named twice, or a directory and a file inside it, is stored
   twice and counted twice (specification edge case *A path named twice*; see
   [research R22](./research.md#r22--counting-regularfile-members-and-the-fr048-countequality-ambiguity)).

### Source path validation

Both passes below run over **all** source paths before the archive is opened, so a rejected
invocation creates no archive and leaves any pre-existing archive untouched (FR-050, FR-051).
Containment is checked first for every path, then existence for every path; within each pass, paths
are visited in command-line order.

| # | Condition on the typed path `p` | Outcome | Requirement |
|---|---|---|---|
| S1 | `posixpath.isabs(p)` | exit 2, diagnostic names `p` | FR-052 |
| S2 | `posixpath.normpath(p)` is `..` or starts with `../` | exit 2, diagnostic names `p` | FR-052 |
| S3 | `posixpath.normpath(p)` is `.` (which includes `p == ""`) | exit 2, diagnostic names `p` | FR-034 + FR-052, gap resolved in [research R19](./research.md#r19--sourcepath-containment-and-the-current-directory-as-a-source) |
| S4 | `not os.path.lexists(p)` | exit 2, diagnostic names `p` | FR-050 |
| S5 | `p` exists but cannot be read (detected only when the walk reaches it) | exit 2, diagnostic names the unreadable path | FR-054 |

S1–S4 are checked ahead of the archive target rules A1–A3, so a run with both a bad source path and
an existing archive reports the source path and exits 2 — which FR-056 requires, since status 2
outranks status 3.

S5 cannot be pre-checked reliably (`os.access` lies under `root` and races under any user), so it is
handled as a backstop during the write pass, converted to a named diagnostic and exit 2 — never
swallowed, and never reported as success
([research R24](./research.md#r24--permissiondenied-cases-are-untestable-as-root)).

**Accepted forms** (verified, [research R19](./research.md#r19--sourcepath-containment-and-the-current-directory-as-a-source)):

| Typed | Normalised / `arcname` | Note |
|---|---|---|
| `notes.txt` | `notes.txt` | regular file |
| `photos` | `photos` | directory |
| `photos/` | `photos` | trailing separator is immaterial |
| `./photos` | `photos` | leading `./` stripped, satisfying FR-034 |
| `photos/../photos` | `photos` | normalises back inside; accepted |
| `a/b/c.txt` | `a/b/c.txt` | nested path, no intermediate directory members created for `a` or `b` |

**Refused forms**: `/etc/passwd` (S1), `../outside` and `a/../../outside` (S2), `.` and `""` (S3),
`missing-folder` (S4).

---

## Entity: Member

One entry written into the archive. Represented by a stdlib `tarfile.TarInfo`, produced by
`TarFile.gettarinfo` during the walk. This project constructs none of its own.

| Attribute | Representation | Requirements |
|---|---|---|
| Recorded name | `TarInfo.name` — the `arcname` joined with each path component below it, separators normalised to `/`, any leading `/` stripped | FR-034 |
| Kind | `TarInfo.isreg()` / `TarInfo.isdir()` / neither | FR-032, FR-033, FR-036 |
| Content | streamed from the file by `TarFile.addfile` in `bufsize` chunks, never materialised | FR-032, SC-017 |
| Counted | yes iff `isreg()` | FR-039 |

### Member classification

Exactly three cases, decided by the `filter` callable passed to `TarFile.add`
([research R16](./research.md#r16--skipping-entries-that-are-neither-regular-files-nor-directories)):

| Case | Action | Counted in `N` | Requirement |
|---|---|---|---|
| Regular file | store the member with its content | **yes** | FR-032, FR-039 |
| Directory | store a directory member, then recurse into its entries in `sorted()` order | no | FR-033, FR-035, FR-039 |
| Anything else (symlink, FIFO, device node, socket) | return `None` — member dropped, run continues | no | FR-036, FR-039 |

The third case applies identically to a directly-named source path and to an entry found while
walking, which is what FR-036 requires. A source path of the third kind therefore contributes
nothing to the archive and nothing to `N`, and the run still succeeds.

### Member naming

The recorded name is the normalised relative path of the entry, built by `TarFile.add` from the
`arcname` this project supplies. Verified end to end
([research R17](./research.md#r17--directory-member-names-the-trailing-separator-and-the-archive-format)):

| Source tree entry | Recorded name as this tool's `list` prints it | On-wire header |
|---|---|---|
| `photos` (directory) | `photos` | `photos/` |
| `photos/a.jpg` | `photos/a.jpg` | `photos/a.jpg` |
| `photos/empty` (empty directory) | `photos/empty` | `photos/empty/` |
| `notes.txt` | `notes.txt` | `notes.txt` |

The trailing `/` on directory headers is the universal tar convention — GNU `tar` writes it, and
`tarfile` strips it again when reading (001 research R3), which is why `list` satisfies FR-008 with
no code. FR-034's "no trailing separator" therefore holds at the level every acceptance scenario
observes. An independent reader such as GNU `tar -tf` displays directory entries with the
separator and file entries character-for-character identical.

### Member order

Deterministic for a given invocation and tree (FR-035):

1. Source paths in command-line order.
2. Within a directory: the directory's own member first, then its entries in
   `sorted(os.listdir(...))` order — code-point order, independent of locale and of filesystem
   readdir order. Files and subdirectories interleave by name.

Example, for `create photos.tar photos notes.txt` over
`photos/{a.jpg, b.jpg, empty/, raw/r.cr2}` and `notes.txt` (verified):

```text
photos
photos/a.jpg
photos/b.jpg
photos/empty
photos/raw
photos/raw/r.cr2
notes.txt
```

---

## Derived value: the reported count `N`

| Property | Value |
|---|---|
| Type | `int`, a plain counter incremented in the classification filter |
| Counts | regular-file members actually stored |
| Excludes | directory members, dropped members (FR-036), the archive itself (FR-037) |
| Duplicates | counted **once per stored member**, so an overlapping source path inflates `N` by design |
| Rendered as | `created ARCHIVE with N files` — the word `files` for every `N`, including `0` and `1` (FR-039) |

A counter rather than 001's set-of-paths, because `create` and `extract` count different things:
`create` counts members stored (duplicates count twice), `extract` counts distinct destination paths
written (duplicates count once). Both are specified explicitly, and the divergence between them for
overlapping source paths is the FR-048 ambiguity recorded in
[research R22](./research.md#r22--counting-regularfile-members-and-the-fr048-countequality-ambiguity).

---

## Run state machine

```text
                         parse argv  ──unrecognised/no paths──▶  usage on stderr, exit 2  (FR-031)
                              │
                              ▼
          validate source paths  S1,S2,S3  ──fail──▶  diagnostic, exit 2  (FR-052)
                              │
                              ▼
          validate source paths  S4        ──fail──▶  diagnostic, exit 2  (FR-050)
                              │
                              ▼
          validate archive target A1       ──fail──▶  diagnostic, exit 2  (FR-045)
                              │
                              ▼
          validate archive target A2       ──fail──▶  diagnostic, exit 3  (FR-043)
                              │
                              ▼
          validate archive target A3       ──fail──▶  diagnostic, exit 2  (FR-044/R20)
                              │
          ════════════════════╪════════════════════  nothing above touches a file
                              ▼
          open archive (create/truncate)   ──OSError──▶  diagnostic, exit 2  (FR-053, A5)
                              │
                              ▼
          add each source path in order    ──OSError──▶  diagnostic, exit 2  (FR-053, FR-054, S5)
          (walk, classify, stream, count)
                              │
                              ▼
          print  created ARCHIVE with N files , exit 0   (FR-038)
```

Every transition above the double line is read-only with respect to the filesystem. That is what
makes FR-051 ("a rejected invocation never leaves a new or partially rebuilt archive behind") a
structural property of the design rather than a promise — the same split 001 used to make FR-020
structural for `extract`.

Below the line, a failure leaves a partial archive on disk but never prints the summary line, which
is exactly what FR-053 and the specification's *Failure after writing has begun* edge case require
— no rollback machinery, per
[research R21](./research.md#r21--failure-partway-through-writing-no-temporary-file-no-rollback).

---

## Reused, unchanged from 001

| Thing | Why it needs no change |
|---|---|
| `TarxError(message, code)` | Carries a one-line diagnostic plus an exit status; FR-055 and FR-056 are the same obligations as FR-027 and FR-028 |
| `EXIT_OK` / `EXIT_ERROR` / `EXIT_CONFLICT` | FR-056 assigns `create` the same three statuses with the same meanings |
| `main`'s single `except TarxError` site | Keeps "exactly one place formats a diagnostic and chooses a status" true for three subcommands instead of two |
| `cmd_list`, `cmd_extract`, `open_archive`, `build_plan`, `write_members`, `escapes_destination` | Untouched. FR-049 and SC-015 require their behaviour to be bit-identical, verified by running the pre-existing suite unmodified |
