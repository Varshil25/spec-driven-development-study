# Phase 0 Research: Tar Archive Create Command

**Feature**: `002-create-command` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

Decision identifiers continue the sequence of
[`001-tar-archive-cli/research.md`](../001-tar-archive-cli/research.md) (R1 … R11), because the
existing runtime code cites those identifiers in its docstrings and reusing numbers would make
those citations ambiguous. This document starts at **R12**.

Every claim below was verified against the interpreter this repository is developed on
(**CPython 3.13.17**, Linux 6.18), using throwaway scripts outside the repository, and against
system GNU `tar` 1.35 and `gzip` where interoperability was at stake. "Verified" in this document
means a probe was run and its output observed, not that the documentation was read.

The Technical Context in [plan.md](./plan.md) contains **no** `NEEDS CLARIFICATION` markers: the
specification's *Assumptions* section already fixed language, dependency policy, package location,
and scope. The research below therefore resolves *design* unknowns and two genuine internal
ambiguities in the specification (R20, R22), rather than filling in missing context.

---

## R12 — Choosing the write mode from the archive name

**Decision**: Select `tarfile.open(path, "w:gz")` when the archive path's name, lower-cased, ends
in `.tar.gz` or `.tgz`; otherwise `tarfile.open(path, "w")`.

**Rationale**: FR-040/FR-041/FR-042 make the suffix of the typed archive path the *only* input to
this choice. A two-line `str.lower().endswith((".tar.gz", ".tgz"))` test expresses exactly that and
nothing more. Lower-casing implements the specification's assumption that the comparison is
case-insensitive, so `.TGZ` and `.TAR.GZ` compress. Verified: `photos.tar.gz`, `photos.tgz`,
`photos.TGZ`, `x.TAR.GZ` → compressed; `photos.tar`, `bundle`, `bundle.bin` → plain. Verified that
`w:gz` output starts with the gzip magic `1f 8b` and that `w` output does not, that `gzip -t`
accepts the compressed archive (exit 0), and that GNU `tar -tzf` lists it.

**Alternatives considered**:

- `pathlib.PurePath.suffixes` — would need re-joining and case-folding to recognise the two-part
  `.tar.gz`, and mis-handles a name like `my.photos.2026.tgz` unless the last suffix is isolated.
  More code for the same answer.
- `mimetypes.guess_type` — drags in a module whose answer depends on system MIME databases, which
  makes a specified behaviour environment-dependent. Rejected outright.
- Sniffing the source files to decide — explicitly prohibited by FR-042.

**Note on asymmetry**: the read commands sniff compression from content (001 research R2) while
`create` decides from the name. This is deliberate and self-consistent: a content-sniffing reader
accepts whatever a name-driven writer produces, which is why FR-047/FR-048 can hold even for a
deliberately unconventional name such as `bundle`.

---

## R13 — `TarFile.add(recursive=True, filter=...)` instead of a hand-written walk

**Decision**: Build each archive with one `tar.add(source, arcname=normalized, recursive=True,
filter=classify)` call per command-line source path. Do not write an `os.walk` loop.

**Rationale**: a single stdlib call already delivers five separate requirements, each of which
would otherwise be our code to write and test:

| Requirement | What `TarFile.add` does |
|---|---|
| FR-033 recursive expansion, directory member for the named directory itself | adds the directory member, then recurses into its entries |
| FR-034 member naming | joins `arcname` with each child name, normalises separators to `/`, strips any leading `/` |
| FR-035 deterministic order | recurses over `sorted(os.listdir(name))` (CPython ≥ 3.7) |
| FR-036 skipping other kinds | `filter` returning `None` excludes a member; `gettarinfo` already returns `None` for types it cannot represent (e.g. sockets) |
| FR-037 never archiving the archive | `add` returns early when `os.path.abspath(name) == self.name` |
| SC-017 flat memory | `addfile` streams file contents through `copyfileobj` in `bufsize` chunks, never reading a member whole |

Principle IV ("when two designs both satisfy the specification, the one with fewer moving parts
MUST be chosen") makes this the required choice, not merely the convenient one.

Verified in one probe, with the archive deliberately written *inside* the named directory
(`tarfile.open("photos/out.tar", "w")`, then `add("photos")`): members came out as `photos`,
`photos/a.jpg`, `photos/b.jpg`, `photos/empty`, `photos/raw`, `photos/raw/r.cr2`,
`photos/zero.bin`, `notes.txt` — alphabetically ordered within each directory, the empty directory
present, the zero-length file present, and `photos/out.tar` **absent**.

**Alternatives considered**:

- **Hand-rolled `os.walk` + `tar.addfile`** — roughly 25 lines replacing one, and it would have to
  re-implement sorting, self-exclusion, separator normalisation, and chunked copying. Every one of
  those is a place to get a specified behaviour subtly wrong. Rejected.
- **`tar.add(..., recursive=True)` with no filter** — would store symbolic links and FIFOs as
  members, violating FR-036, and gives no hook for counting.
- **`shutil.make_archive`** — cannot name members by a chosen relative path, cannot exclude the
  archive from itself, cannot report a count, and chooses compression from a format argument rather
  than the typed suffix. Rejected.

**One caveat recorded for the implementation**: in `TarFile.add`, a `filter` that returns `None`
for a *directory* also suppresses recursion into it, because the early return happens before the
recursive branch. The design never excludes directories, so this is latent rather than live — but
it means the filter must not grow a "skip this directory" responsibility later without revisiting
recursion.

---

## R14 — The archive is never stored inside itself

**Decision**: Rely on `TarFile.add`'s built-in self-exclusion; add no check of our own.

**Rationale**: FR-037 is satisfied structurally. `TarFile.__init__` records
`self.name = os.path.abspath(name)`, and `add` compares `os.path.abspath(name)` against it before
doing anything else, on every recursive call as well as the top-level one. `os.path.abspath`
normalises away `./` prefixes and trailing separators, so `./photos/out.tar` and `photos/out.tar`
compare equal.

Verified for both write modes: `tarfile.open("photos/out.tar", "w")` and `"w:gz"` both set
`TarFile.name` to the absolute path, and in the R13 probe the archive did not appear among its own
members.

**Alternatives considered**: comparing `Path.resolve()` of every candidate against the archive
before adding it — duplicate machinery for a guarantee the stdlib already makes, and `resolve()`
follows symlinks, which this feature deliberately does not.

**Limitation, deliberately not addressed**: the comparison is path-based, so a *different* path
that reaches the same file (a hard link, or a symlinked parent directory) is not recognised as the
archive. Nothing in the specification asks for that, and symbolic links are skipped anyway
(FR-036), so the unbounded-growth concern the edge case names cannot arise through the paths this
tool walks.

---

## R15 — Deterministic member order

**Decision**: Source paths are added in command-line order; within a directory, `TarFile.add`'s
`sorted(os.listdir(name))` fixes the order. No sorting of our own.

**Rationale**: FR-035 requires only that the order be "fixed, repeatable" — not any particular
collation. `sorted()` on the raw entry names gives code-point order, which is repeatable across
runs and machines and independent of locale (unlike a `locale.strcoll` sort) and of filesystem
readdir order (unlike bare `os.listdir`). Verified: the R13 probe's member list is in ascending
name order within each directory, with files and subdirectories interleaved by name rather than
grouped.

**Alternatives considered**: `os.scandir` without sorting (faster, but order depends on the
filesystem — fails FR-035); depth-first-files-then-directories grouping (no requirement asks for
it).

---

## R16 — Skipping entries that are neither regular files nor directories

**Decision**: Pass a `filter` callable that returns the `TarInfo` for `isreg()` and `isdir()`
members, increments a counter for `isreg()`, and returns `None` for everything else.

**Rationale**: this is the one line FR-036 needs, and it is also the natural place to satisfy
FR-039 (count regular-file members only), since the filter sees exactly the members that will be
written and nothing else. Verified: a directory containing a symbolic link and a FIFO alongside
four regular files produced the four file members plus the directory members, with the link
(`SYMTYPE`) and FIFO (`FIFOTYPE`) reported to the filter and dropped — the run did **not** fail,
as FR-036 requires.

Verified separately from CPython's `gettarinfo`: types `tarfile` cannot represent at all (a UNIX
socket) make `gettarinfo` return `None`, and `add` then returns before the filter is consulted. So
such entries are skipped and uncounted too, by a different route to the same specified outcome.

A directly-named non-file, non-directory source path takes the same route: it passes existence
validation (it does exist), reaches the filter, and is dropped — an archive is still created, with
that path contributing nothing to `N`. That is what FR-036's "whether named directly or encountered
while walking" asks for.

**Alternatives considered**: pre-filtering with `os.walk` and `stat` before calling `add` — a
second traversal that can disagree with the first (a file replaced between passes) for no benefit.

---

## R17 — Directory member names, the trailing separator, and the archive format

**Decision**: Pass the normalised relative path as `arcname` and let `tarfile` write the header.
Do not set `format=`; the default (`PAX_FORMAT`) is correct. Do not attempt to strip the trailing
`/` that tar headers carry for directory members.

**Rationale**: FR-034 requires recorded member names with "no leading `./`, no trailing separator,
and no absolute prefix". Verified behaviour, with `arcname="photos"`:

- **Python `tarfile` reader** reports `photos`, `photos/a.jpg`, `photos/empty` — exactly FR-034's
  form, and exactly what this tool's own `list` prints (confirmed by running the real
  `python -m tarx list` against a prototype archive).
- **On-wire header** stores the directory name as `photos/`. This is written by `TarInfo.get_info`,
  which appends `/` to a `DIRTYPE` name, and it is the universal tar convention: GNU `tar` writes
  it, and 001 research R3 established that `tarfile` strips it again when reading, which is why
  `list` needs no code for FR-008.
- **GNU `tar -tf`** therefore prints `photos/`, `photos/a.jpg`, `photos/empty/`.

So FR-034 is met at the level the specification's own acceptance scenarios observe — US2 scenario 1
asks for "the directory entry `photos` without a trailing separator" from the `list` command, and
that is what comes out. Suppressing the on-wire `/` would be both extra code and actively harmful:
it is how every tar reader distinguishes a directory entry, and removing it would break the
interoperability SC-012 and SC-009 demand. **Recorded so a reviewer of SC-009 is not surprised**:
an independent reader shows directory names with the conventional trailing separator; file names
match character for character.

On `format`: the default PAX format writes a `././@PaxHeader` pseudo-entry when a field does not
fit the historic USTAR layout (long names, sub-second mtimes). Verified that this pseudo-entry is
consumed by the reader and is **not** surfaced as a member by either Python `tarfile` (3 members
reported) or GNU `tar` (3 entries listed), so it cannot leak into `list` output or inflate the
extraction count. PAX is also what makes member names longer than 100 characters work at all.
Pinning `format=tarfile.USTAR_FORMAT` would trade that away for nothing.

**Alternatives considered**: `GNU_FORMAT` (equivalent here, less portable); `USTAR_FORMAT` (breaks
on long paths); post-processing `TarInfo.name` in the filter to drop the separator (fights the
library, breaks readers).

---

## R18 — All validation must precede opening the archive

**Decision**: Validate every source path, and the archive path's existence and kind, *before*
calling `tarfile.open(..., "w")`. The open call is the first operation in a `create` run that
touches the filesystem in a way the user can observe.

**Rationale**: this is the single most load-bearing finding of Phase 0, because the obvious
ordering silently violates three requirements. Verified: a pre-existing `pre.tar` of 140 bytes was
**truncated to 0 bytes** by `tarfile.open("pre.tar", "w")` even though the subsequent `add` failed
immediately with `FileNotFoundError`. A design that opens first and validates during the walk would
therefore destroy the user's archive in exactly the case FR-050 and US4 scenario 3 single out
("the pre-existing archive is left byte-for-byte unchanged"), and would leave a 0-byte archive
behind in the case FR-050 and US4 scenario 1 forbid (`other.tar` does not exist).

Verified in the same probe that a failed `add` leaves the newly-created archive file on disk
(0 bytes for an immediate failure, 10240 bytes after some members were written) — so "create no
archive" is only achievable by not opening it.

Making validation a separate, filesystem-write-free pass turns FR-051 into a structural property
rather than a promise, exactly as 001's plan/write split did for `extract` (001 research R9).

**Alternatives considered**:

- Open with mode `"x"` (exclusive create) to get overwrite protection from the OS — attractive, but
  it conflates "already exists" (exit 3) with every other `OSError` (exit 2), cannot distinguish an
  existing directory (FR-045, exit 2) from an existing file (FR-043, exit 3), and gives no place to
  report the first offending *source* path. Rejected: the explicit checks are needed anyway.
- Write to a temporary file and `os.replace` it into place on success — see R21.

---

## R19 — Source-path containment, and the current directory as a source

**Decision**: Validate each source path **lexically**: reject it if `posixpath.isabs` is true, if
`posixpath.normpath` yields `..` or a value starting `../`, or if `normpath` yields `.`. Use the
normalised value as the `arcname`.

**Rationale**: FR-052 requires refusing a source path that is absolute or resolves outside the
current directory, and FR-034 requires the member name to be the normalised relative path — so the
normalisation has to happen regardless, and the containment test is three comparisons on its
result. Verified: `photos/` → `photos`; `./photos` → `photos`; `photos/../photos` → `photos`
(inside, accepted); `/etc` → absolute (refused); `../x` and `a/../../x` → both `../x` (refused).

Lexical rather than `Path.resolve()`-based, for the same reasons 001 research R11 gave for
`escapes_destination`: `resolve()` follows symbolic links, and this feature deliberately does not
follow them (FR-036 skips them). A symlink inside the working directory that points outside it is
therefore skipped as a member, never followed to reach outside — so the lexical check and the
skipping rule together close the hole that a realpath check would otherwise be needed for.

**The current directory itself (`.`, or an empty string, which `normpath` also maps to `.`) is
refused with exit status 2.** This resolves a gap in the specification. Verified that
`add(".", arcname=".")` produces member names `.`, `./photos`, `./photos/a.jpg` — every one of them
carrying the leading `./` that FR-034 explicitly forbids. The specification describes a source path
as naming "a file or a directory ... such as `notes.txt` or `photos`", whose members are "named by
their relative path"; the current directory's relative path is empty, so it has no FR-034-conformant
member name. Refusing loudly (Principle II) beats inventing a naming rule the specification does not
state, and beats emitting names it forbids. **Flagged for a reviewer**: this behaviour is decided
here, not in the specification, and may warrant a spec amendment.

**Alternatives considered**:

- Accepting `.` and rewriting its members to drop the `./` prefix — invents an unspecified rule,
  and makes `create x.tar .` archive the archive's own directory, including unrelated siblings.
- Accepting `.` as-is — emits names FR-034 forbids, and 001's `extract` would then normalise them
  back on the way out, making the round trip pass by luck rather than by design.

---

## R20 — The archive path's prior existence and kind; exit 2 versus exit 3

**Decision**: Check the archive path in this order, before any source data is written:

1. exists and is a directory → exit **2** (FR-045), with or without `--overwrite`;
2. exists and `--overwrite` was **not** given → exit **3** (FR-043);
3. exists, `--overwrite` was given, and it is **not** a regular file → exit **2**;
4. otherwise open it for writing; any `OSError` → exit **2** (FR-053).

**Rationale**: FR-056 states that when a status-2 condition and the status-3 condition are both
present, status 2 is reported, so status 3 always means "re-run with `--overwrite`". That forces
the directory check (step 1) ahead of the existence check (step 2) — the literal reading of FR-043
("if the archive path already exists ... exit with status 3") would otherwise capture a directory
too and contradict FR-045.

Step 3 resolves a second gap. FR-044 obliges `--overwrite` to replace an existing **regular file**
and says nothing about an existing FIFO, socket, or device node. Attempting to honour `--overwrite`
there is not merely unspecified but actively harmful: opening a FIFO for writing *blocks* until a
reader appears, so the command would hang rather than fail. Refusing with exit 2 and a diagnostic
naming the path keeps the failure loud, bounded, and consistent with FR-045's "not replaceable in
kind" stance. **Flagged for a reviewer** as a decision made here rather than in the specification.

The asymmetry this leaves — a FIFO at the archive path yields exit 3 without `--overwrite` (FR-043
is explicit that *any* existing path does) and exit 2 with it — is the price of following FR-043
literally. It is recorded rather than smoothed over, and is a candidate for the same spec amendment
as step 3.

Verified for step 4: `tarfile.open("adir", "w")` and `"w:gz"` both raise `IsADirectoryError`
(errno 21), and a missing parent directory raises `FileNotFoundError` (errno 2); both carry
`filename` and `strerror`, which is what the diagnostics in the contract are built from. The
explicit directory check in step 1 still precedes this, because `IsADirectoryError` alone cannot be
told apart from the other write failures that must report exit 2 *after* the exit-3 check.

**Interaction with source validation**: source paths are validated *before* the archive path, so a
run with both a bad source and an existing archive reports the source (exit 2 either way, which is
what FR-056 demands). US4 scenario 3 — existing archive, `--overwrite`, one missing source — is
therefore exit 2 with the archive untouched, because nothing has opened it.

---

## R21 — Failure part-way through writing: no temporary file, no rollback

**Decision**: Write directly to the archive path. Convert any `OSError` or `tarfile` error raised
during the write pass into a one-line diagnostic plus exit 2, and never print the summary line. Do
**not** write to a temporary file and `os.replace` it into position.

**Rationale**: FR-053 requires that a mid-write error produce a diagnostic naming the archive path,
exit 2, and "MUST NOT report success" — a statement about what is *announced*, not about what is
left on disk. The specification's edge case agrees in the same terms: "still reports a diagnostic
... rather than reporting success, so no incomplete archive is ever announced as created". FR-051's
"never leaves a new or partially rebuilt archive behind" is scoped to a *rejected invocation*, i.e.
one that fails validation — which R18's ordering already guarantees without a temporary file.

Temp-file-and-rename would additionally protect the *pre-existing* archive during an `--overwrite`
run that fails mid-write. No requirement asks for that, and Principle IV prohibits structure
without "a current specified requirement that needs it". It also brings real costs: a second path
to validate, a cleanup path for the temporary file (itself able to fail), transient double disk
usage on a large archive, and a hole in FR-037 — the temporary file would sit inside a named
directory under a name `TarFile.add`'s self-exclusion does not recognise, so it could be archived
into itself.

**Consequence, stated plainly**: an `--overwrite` run that fails part-way through leaves a truncated
archive where the old one was. This is a deliberate, specification-permitted outcome, and the
failure is loud. **Flagged for a reviewer** as the strongest candidate for a future requirement if
the project later decides durability matters more than simplicity.

**Alternatives considered**: `os.replace` from a temp file (above); unlinking the partial archive in
an `except` block (turns one failure into two possible failures, and destroys the pre-existing
archive's remains for no gain).

---

## R22 — Counting regular-file members, and the FR-048 count-equality ambiguity

**Decision**: Count with a plain integer incremented in the filter — one increment per regular-file
member actually stored.

**Rationale**: FR-039 counts "regular-file members", and the specification's edge case *A path named
twice* states that overlapping entries "are stored more than once, since no de-duplication is
applied; the reported count counts each stored regular file". An integer is therefore not merely
sufficient but *required*. Note this is the opposite of 001's `extract`, which deliberately used a
`set` of written paths because FR-015 counts distinct *destination* paths (001 research R9) — the
two commands count different things, and the difference is specified in both directions.

**Ambiguity found and resolved**: FR-048 requires that for every archive `create` produces, "the
extraction count equals the count `create` reported". When the named source paths **overlap** — the
same path given twice, or a directory and a file inside it — `create` stores a regular file twice
and reports 2, while `extract` writes one destination path and reports 1. FR-048 and the
*A path named twice* edge case cannot both hold for such an archive.

Resolution: the edge case is the more specific statement and governs `create`'s count; FR-048's
count-equality is read as holding for archives built from non-overlapping source paths, which is
every case the acceptance scenarios and success criteria exercise. The contract records this
restriction explicitly, and the test suite will assert both halves — equality for disjoint sources,
and the documented divergence for overlapping ones — so neither behaviour can regress unnoticed.
**Flagged for a reviewer**: this is a specification-internal conflict resolved in the plan, the
direct counterpart of 001 research R8.

**Alternatives considered**: de-duplicating source paths so the counts always agree — contradicts
the edge case outright and adds overlap-detection machinery Principle IV forbids. Counting distinct
stored names instead — same contradiction, in the reporting rather than the storing.

---

## R23 — Performance (SC-017)

**Decision**: No performance work beyond using `TarFile.add`. No chunk-size tuning, no parallelism.

**Rationale**: measured, on a tree of 10,000 regular files across 100 directories plus one 120 MiB
file, on this development machine:

| Archive | Files | Wall clock | Budget (SC-017) |
|---|---|---|---|
| plain `w` | 10,001 | **0.97 s** | 30 s |
| gzip `w:gz` | 10,001 | **1.98 s** | 30 s |

A 15–30× margin, so there is nothing to optimise. Memory flatness with respect to the largest
member is structural rather than measured-in-isolation: `TarFile.addfile` copies the member through
`shutil.copyfileobj` in `bufsize`-sized chunks and never materialises it, which is the same
guarantee 001 research R6 relied on for extraction. (The probe's own peak RSS was dominated by the
120 MiB buffer it allocated to *create* the large file, so it is not quoted as evidence here.)

**Alternatives considered**: tuning `tarfile`'s `bufsize`, or a `gzip` `compresslevel` below the
default 9 — both are optimisation against a 15× margin, i.e. complexity with no forcing requirement.

---

## R24 — Permission-denied cases are untestable as root

**Decision**: Specify the permission failures (FR-053 unwritable archive location, FR-054
unreadable source) as tests that skip when `os.geteuid() == 0`, following the precedent already set
in this repository.

**Rationale**: verified that `chmod 0o000` denies nothing to root — `tar.add` read both a
`0o000` directory and a `0o000` file without error in the probe, and the development environment
runs as euid 0. `tests/test_failures.py:63` already guards two 001 tests this way
(`SKIPPED [2] ... running as root: mode 0o000 does not deny access`), and the suite reports
63 passed / 2 skipped. Reusing that exact pattern keeps the requirement covered and traceable on
any non-root machine without making the suite fail or, worse, silently assert nothing here.

**Alternatives considered**: simulating the failure by monkeypatching `tarfile.open` or `TarFile.add`
to raise `PermissionError` — tests the error-formatting code without testing that the real
`PermissionError` is raised and attributed to the right path. Worth adding *alongside* the skipping
test, not instead of it, so the diagnostic and status are asserted even under root.

---

## R25 — Where the code lives

**Decision**: Extend `src/tarx/cli.py` with `cmd_create` and its helpers, and register the
subcommand in the existing `build_parser`. Create no new module, no new package, no new exception
type.

**Rationale**: Principle IV prefers "a module to a package" and prohibits structure without a
forcing requirement. `create` reuses `TarxError`, `EXIT_OK`/`EXIT_ERROR`/`EXIT_CONFLICT`, and the
single diagnostic-formatting site in `main` — exactly the machinery 001's plan justified, and the
only way FR-055 and FR-056 stay true by construction rather than by duplication. The additions are
roughly 60 lines in one file.

Changes to existing code are confined to three additive edits: a third `add_parser` block, a third
entry in `main`'s `handlers` dict, and the module and parser description strings. Verified that no
existing test asserts the parser's `description`; the invocation tests assert only
`usage: tarx`-prefixed strings and `usage: tarx list` / `usage: tarx extract`, none of which a
third subparser changes. FR-049 and SC-015 are nonetheless verified empirically by running the
pre-existing suite unmodified (baseline recorded above: 63 passed, 2 skipped).

**Alternatives considered**: a new `create.py` module (a second file, two import edges, and a
shared-error-type question, for 60 lines); a `tarx.archive` package with writer/reader submodules
(textbook speculative generality — Principle IV prohibits it explicitly).

---

## Round-trip verification (the whole design, end to end)

Before any of the above was written up, a prototype implementing R12–R17 was run against the
**real, unmodified** `python -m tarx list` and `python -m tarx extract`, on a tree containing
`notes.txt` and `photos/{a.jpg,b.jpg,raw/r.cr2,empty/}`:

| Check | Plain `photos.tar` | Gzip `photos.tar.gz` |
|---|---|---|
| prototype summary count | 4 | 4 |
| `list` exit / stderr | 0 / empty | 0 / empty |
| `list` output | `photos`, `photos/a.jpg`, `photos/b.jpg`, `photos/empty`, `photos/raw`, `photos/raw/r.cr2`, `notes.txt` | identical |
| `extract` stdout | `extracted 4 files` | `extracted 4 files` |
| extracted tree | `notes.txt`, `photos/{a.jpg,b.jpg,empty/,raw/r.cr2}` | identical |
| contents byte-identical | yes | yes |

This closes FR-047, FR-048, SC-009, SC-010, and SC-012 as *reachable* by this design before a line
of production code is written. The empty directory survives the round trip, the directory entry
lists without a trailing separator, the two forms are indistinguishable after reading, and the
extraction count equals the creation count.

---

## Summary of unresolved specification issues

None blocks implementation. All three are recorded for a reviewer and are candidates for a spec
amendment; each is resolved in the contract and covered by tests.

| # | Issue | Resolution |
|---|---|---|
| R19 | The specification does not say what `.` (or an empty string) means as a source path, and accepting it emits member names FR-034 forbids | Refused with exit 2 and a diagnostic |
| R20 | FR-044 does not say what `--overwrite` means when the archive path exists as a FIFO, socket, or device node; honouring it could hang | Refused with exit 2; FR-043 still gives exit 3 without the flag |
| R22 | FR-048's count equality conflicts with the *A path named twice* edge case when source paths overlap | Edge case governs `create`'s count; FR-048 read as scoped to non-overlapping sources |
