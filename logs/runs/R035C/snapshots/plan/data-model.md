# Phase 1 Data Model: Archive Creation Command

**Feature**: `002-create-command` | **Date**: 2026-11-19

The entities below are the in-process vocabulary of `create`. Three of them are new; three are
reused from `001-tarx-cli` unchanged. Nothing here is persisted — the only artifact that outlives
the process is the archive file itself.

---

## Reused from `001-tarx-cli` (no change)

| Entity | Where | Role in `create` |
|--------|-------|------------------|
| `Problem(exit_class, message)` | `core.py` | One detected reason the run cannot proceed. Accumulated in a list so all problems are reported together (FR-018). |
| `TarxError(message, exit_class)` | `core.py` | A fatal condition carrying its finished diagnostic. Raised for failures discovered *after* validation — opening the archive for writing (C9) and mid-write failures (C10). |
| `resolve_exit_status(problems)` | `core.py` | Collapses a problem list to one status. Already implements "class 2 outranks class 3", which is FR-018's precedence rule — reused, not re-implemented. |
| `EXIT_OK` = 0, `EXIT_INPUT` = 2, `EXIT_REFUSED_OVERWRITE` = 3 | `core.py` | The entire status vocabulary. `create` adds no new status. |

---

## New entities

### SourceOperand

One `PATH` operand as the user typed it, paired with the member name it will contribute.

| Field | Type | Meaning |
|-------|------|---------|
| `given` | `str` | The operand verbatim, echoed into diagnostics and never normalised for display (`photos/`, `./photos`). |
| `member` | `str` | `os.path.normpath(given)` — the member name of the operand itself, or `"."` for the current directory. |

Not a class in the implementation: operands are handled as a `(given, member)` pair inside the
validation loop. Recorded here because the distinction between *what the user typed* (diagnostics)
and *what gets stored* (member names) is load-bearing for FR-004 and the C5/C6 templates.

**Validation rules** (in this order; the first failure stops the rest for that operand):

1. **Lexical safety** (FR-014) — reject if `os.path.isabs(given)`, or if `member` is `".."` or
   starts with `"../"`. The check is purely lexical: no `realpath`, so the verdict is a property
   of the operand rather than of whatever symlinks exist. → **C6**, class 2.
2. **Existence** (FR-013) — reject if `os.path.lexists(given)` is false. `lexists`, not `exists`,
   so a dangling symbolic link counts as existing and is then skipped as non-regular rather than
   reported as missing. → **C5**, class 2.
3. **Traversability** — each directory is listed during collection; a directory that cannot be
   listed is reported as unreadable. → **C7**, class 2.

### PlannedMember

One entry that will be written to the archive.

| Field | Type | Meaning |
|-------|------|---------|
| `name` | `str` | The member name: `/`-separated, relative, no leading `./`, no trailing `/` even for directories (FR-004, research.md §5). This is also the identity for de-duplication (FR-020) and the sort key (FR-026). |
| `kind` | `"file"` \| `"dir"` | Classified by `os.lstat` + `stat.S_ISREG`/`S_ISDIR`. Non-regular entries never become `PlannedMember`s. |
| `path` | `str` | The filesystem path to read from, relative to the current directory. |

**Invariants**:

- `name` is unique across the plan (FR-020).
- `name` is never the archive's own path (FR-019).
- Every `kind == "file"` member was opened for reading successfully during validation (FR-016).
- Two names for one inode are two distinct `PlannedMember`s, each `kind == "file"` (FR-015).

### CreatePlan

What validation hands to the write phase.

| Field | Type | Meaning |
|-------|------|---------|
| `members` | `dict[str, PlannedMember]` | Keyed by member name, insertion-ordered — so the dict *is* both the de-duplication index (FR-020) and the write order (FR-026). |
| `skipped` | `list[tuple[str, str]]` | `(path, label)` per non-regular entry, in plan order. Reported on stderr only when the run succeeds (FR-015, research.md §10). |

`N`, the count in the summary line, is `sum(1 for m in members.values() if m.kind == "file")` —
derived from the plan, never counted separately, so FR-008's `N` cannot drift from what the archive
holds (SC-003).

An empty-but-valid plan is a success case: `create x.tar emptydir` writes one directory member and
reports `created x.tar with 0 files`, exit 0.

---

## Ordering model (FR-026, SC-012)

Two levels, applied in this order:

1. **Operands contribute in the order given.** `create a.tar docs photos` stores every `docs`
   member before every `photos` member.
2. **Within one operand, members are sorted by full member name as text.** The whole subtree is
   collected first, then sorted once — so the order `os.scandir` reports entries is irrelevant,
   which is the substance of SC-012.

Sorting the *full* name is what places a directory immediately before its contents, with no
separate directory-first rule:

```text
d, d/a.txt, d/b/c.txt, d/z.txt
```

De-duplication keeps the **first** position earned: with `create a.tar photos photos/a.jpg`, the
member `photos/a.jpg` appears once, in the position `photos` gave it.

---

## State transitions of the archive path

Evaluated before anything is written. `ARCHIVE`'s parent directory is checked first, because a
missing parent makes every other question moot.

| State of `ARCHIVE` | Parent directory | `--overwrite` | Outcome | Template | Status |
|--------------------|------------------|---------------|---------|----------|--------|
| any | missing | either | refuse; create nothing, not even a directory | C1 | 2 |
| any | exists, not a directory | either | refuse | C2 | 2 |
| absent | exists | absent | create the archive | — | 0 |
| absent | exists | present | create the archive (identical behaviour) | — | 0 |
| existing regular file | exists | absent | refuse; leave the file byte-for-byte unchanged | C3 | 3 |
| existing regular file | exists | present | replace, but only after validation passes | — | 0 |
| existing directory | exists | either | refuse; leave it untouched | C4 | 2 |
| existing symlink, FIFO, socket, device node | exists | either | refuse | C4 | 2 |

Two consequences the tests pin down:

- `--overwrite` consents to replacing a **regular file** and nothing else — the same boundary it
  has in `extract` (FR-012).
- The existing archive is not touched until validation has found no problem anywhere, so a run
  that fails for an unrelated reason (a missing `PATH`) leaves the previous archive intact
  (FR-011, US3 scenario 4).

---

## Classification of a source entry

One `os.lstat` per entry decides everything:

| `lstat` says | Stored as | Counts in `N` | Diagnostic |
|--------------|-----------|---------------|------------|
| regular file (`S_ISREG`) | regular-file member | yes | — |
| directory (`S_ISDIR`) | directory member | no | — |
| symbolic link | not stored, not followed | no | C8 skip notice |
| FIFO, socket, character device, block device | not stored | no | C8 skip notice |
| anything else | not stored | no | C8 skip notice (`unsupported file type`) |

`lstat`, not `stat`: a symbolic link is classified as a link rather than as its target, which is
what makes "symbolic links are not followed" true by construction rather than by a later check.
A file carrying several names is a plain regular file in this table — hard-link detection is
deliberately absent (FR-015, research.md §4).

---

## Phase boundary

```text
validate_and_plan(archive, paths, overwrite) -> (CreatePlan, list[Problem])
    │  reads only: lstat, scandir, open-for-read
    │  writes: nothing — not one byte, not one directory
    ▼
problems non-empty ──► report every problem to stderr, status = resolve_exit_status(problems)
    │                   nothing on stdout; filesystem exactly as it was
    ▼ problems empty
write_archive(archive, plan) -> int                        # the count N
    │  tarfile.open(archive, "w"|"w:gz")   ← the first write of the whole run
    ▼
report skip notices to stderr, then `created ARCHIVE with N files` to stdout, status 0
```

The boundary is FR-016 and is not softened by any early write. Because
`tarfile.open(..., "w")` creates the file at open time (research.md §3), the boundary is also the
exact moment the archive comes into existence.

---

## Requirement-to-test map

Every requirement in [spec.md](./spec.md) and the module that covers it. Test names use the
`create_fr_###` form and docstrings cite `CREATE-FR-###`, so the audit in
`tests/test_create_traceability.py` can distinguish this feature's identifiers from
`001-tarx-cli`'s identically-numbered ones (research.md §13).

| Requirement | Covering tests | Module |
|-------------|----------------|--------|
| FR-001 | `create` dispatches; unknown command still rejected | `test_create.py`, `test_create_errors.py` |
| FR-002 | operands accepted; one `PATH`, many `PATH`s; `--overwrite` parsed | `test_create.py` |
| FR-003 | file operand → one member; directory operand → whole subtree at every depth | `test_create.py` |
| FR-004 | member names are relative, `/`-separated, no leading `./`, trailing-slash and `./` operand forms | `test_create.py` |
| FR-005 | `.tar.gz` and `.tgz` are gzip; `.tar`, `backup`, `data.bin` are plain; `PHOTOS.TAR.GZ` is plain | `test_create.py` |
| FR-006 | stored bytes equal source bytes, including zero-length and binary | `test_create.py` |
| FR-007 | directory members recorded, including empty subdirectories | `test_create.py` |
| FR-008 | exact summary line; plural `files` at N = 0, 1, 2; nothing else on stdout | `test_create.py` |
| FR-009 | round-trip through `list` and `extract`, plain and gzip | `test_create_roundtrip.py` |
| FR-010 | existing archive without `--overwrite` → C3, status 3, file unchanged | `test_create_overwrite.py` |
| FR-011 | `--overwrite` replaces; previous archive intact when validation fails | `test_create_overwrite.py` |
| FR-012 | directory / symlink / FIFO at `ARCHIVE` → C4, status 2, with and without `--overwrite` | `test_create_overwrite.py` |
| FR-013 | missing `PATH` → C5, status 2, no archive | `test_create_errors.py` |
| FR-014 | absolute and `../` operands → C6, status 2 | `test_create_errors.py` |
| FR-015 | symlink/FIFO/socket skipped with notice, status 0, excluded from `N`; both hard-link names stored and counted | `test_create.py`, `test_create_errors.py` |
| FR-016 | every detected failure leaves no archive and no directory; validation reads the whole tree before writing | `test_create_errors.py` |
| FR-017 | success exits 0; stream split asserted on every path | `test_create.py` |
| FR-018 | multiple problems all reported, one per line; mixed classes → 2, not 3 | `test_create_errors.py` |
| FR-019 | `create photos/all.tar photos` omits the archive from itself | `test_create.py` |
| FR-020 | overlapping and repeated operands → each member once, counted once, first position kept | `test_create.py` |
| FR-021 | unreadable entry → C7, status 2, no archive (real + injected); mid-write failure → C10, status 2, no summary | `test_create_errors.py` |
| FR-022 | missing `ARCHIVE`, no `PATH`, unknown option → usage, non-zero, nothing read or written | `test_create_errors.py` |
| FR-023 | pre-existing `list`/`extract` suite passes unmodified; no pre-existing test file changed | `test_create_roundtrip.py` |
| FR-024 | top-level and `create --help` name all three commands, operands and `--overwrite` | `test_create_roundtrip.py` |
| FR-025 | the audit itself: every requirement referenced, and this map is not stale | `test_create_traceability.py` |
| FR-026 | full-member-name sort; operand order; scandir order made irrelevant; repeat runs identical | `test_create.py` |
| FR-027 | missing parent directory → C1, status 2, no archive and no directory created | `test_create_errors.py` |

### Success-criteria coverage

| Criterion | How it is measured |
|-----------|--------------------|
| SC-001, SC-002 | create → extract → compare trees, plain and gzip (`test_create_roundtrip.py`) |
| SC-003 | reported `N` compared against regular-file members counted from the archive |
| SC-004 | `snapshot_tree` before/after every refusal scenario |
| SC-005 | status asserted for every outcome, including mixed-problem runs |
| SC-006 | every failing run: stdout empty, stderr non-empty, nothing new on disk |
| SC-007 | gzip magic bytes (`\x1f\x8b`) read from the archive itself |
| SC-008 | every created archive fed to `list` and `extract`, status 0, stderr empty |
| SC-009 | existing suite runs unmodified; `git diff` shows no pre-existing test file touched |
| SC-010 | 10,000-file run under 10 s; `tracemalloc` peak under a fixed ceiling at two file sizes (both `@pytest.mark.slow`) |
| SC-011 | `test_create_traceability.py` |
| SC-012 | same tree archived twice → identical member sequences |
