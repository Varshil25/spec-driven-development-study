# Phase 0 Research: Create Tar Archives (`create` command)

**Feature**: `002-create-archive-command` | **Date**: 2026-11-12 | **Spec**: [spec.md](./spec.md)

Decisions taken before design, each recorded as **Decision / Rationale / Alternatives considered**.
Identifiers `R-101 …` continue the scheme of [`001-tarx-cli/research.md`](../001-tarx-cli/research.md)
(`R-001 … R-016`) without colliding with it.

Every item marked **verified** was checked by running the code in this environment
(CPython 3.13.17, POSIX filesystem) before being written down.

---

## R-101 — Build every `TarInfo` by hand; never `TarFile.add()`

**Decision**: members are written with `TarFile.addfile(tarinfo, fileobj)` using a `TarInfo`
constructed field by field. `TarFile.add()` and `TarFile.gettarinfo()` are not used anywhere.

**Rationale**: `gettarinfo()` copies the on-disk `st_uid`, `st_gid`, `st_mode`, and `st_mtime`
into the header and resolves the local account's user and group names — exactly what SR-108
forbids. `add(recursive=True)` additionally chooses its own traversal order (FR-106 fixes
ours), follows nothing but records symlinks as symlink members (SR-102 refuses them), and
offers no hook to exclude the archive being written (SR-109). Hand-built headers make all
four requirements structural rather than something to remember.

Fixed field values: `uid = gid = 0`, `uname = gname = ""`, `mtime = 0`, `mode = 0o644` for
regular files and `0o755` for directories, `type` ∈ {`REGTYPE`, `DIRTYPE`} only. No other
field is ever set from disk. **Verified**: a round trip through the existing `list` and
`extract` shows `uid=0 uname='' mode=0o644 mtime=0` on every member.

**Alternatives considered**: `TarFile.add()` with a `filter=` callback that scrubs the header —
rejected because the filter runs *after* `gettarinfo()` has already stat'd and name-resolved
the file, so it is a correction rather than a prevention, and it still leaves traversal order
and symlink handling to `tarfile`.

---

## R-102 — Write PAX format explicitly

**Decision**: `format=tarfile.PAX_FORMAT`, named explicitly rather than relying on
`tarfile.DEFAULT_FORMAT`.

**Rationale**: PAX stores long and non-ASCII member names in a UTF-8 extended header, which is
what makes the spec's "names with spaces, non-ASCII characters" edge case round-trip exactly;
USTAR would truncate at 100 bytes and mangle non-UTF-8-representable names. Naming the format
explicitly keeps the output stable if a future CPython changes its default. `tarfile` consumes
PAX extended headers while reading and does not surface them as members, so `list` shows
exactly the names `create` recorded and the SR-105 member cap counts real members only.
**Verified**: `photos/a ü.jpg` survives `create` → `list` → `extract` byte-for-byte.

**Alternatives considered**: `GNU_FORMAT` — equally capable for long names but less portable
to other tar implementations; `USTAR_FORMAT` — rejected outright, it cannot represent the
spec's required names.

---

## R-103 — Compress with `gzip.GzipFile(filename="", mtime=0)`, not `mode="w:gz"`

**Decision**: for a gzip archive, open the output file descriptor, wrap it in
`gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0)`, and wrap *that* in
`tarfile.open(fileobj=gz, mode="w:", format=PAX_FORMAT)`. Plain archives skip the middle layer.

**Rationale**: `tarfile.open(name, mode="w:gz")` writes a gzip header carrying the current
clock time and the output file's own name. Both are avoidable disclosures in the same spirit
as SR-108, and the timestamp would make byte-identical reruns impossible. Setting
`filename=""` and `mtime=0` removes both. **Verified**: two runs over an unchanged tree
produce byte-identical `.tar.gz` files, and the existing content-sniffing
`archive.sniff_compression` recognises the result as gzip.

**Alternatives considered**: `mode="w:gz"` with a post-hoc patch of the gzip header bytes —
more code, more fragile, same result; leaving the timestamp in — rejected, it costs nothing to
remove and determinism makes FR-106's "same member names in the same order" testable at the
file level too.

---

## R-104 — All-or-nothing via `mkstemp` + `os.rename` in the archive's own directory

**Decision**: write to a temporary file created by `tempfile.mkstemp(dir=<ARCHIVE's directory>,
prefix=".tarx-", suffix=".tmp")`, then `os.rename()` it onto ARCHIVE. A `try/finally` unlinks
the temporary file on every path that does not reach the rename.

**Rationale**: FR-119 demands that *no* failure — including one in the middle of streaming a
multi-gigabyte file — leaves a partial archive, and that a pre-existing archive is byte-for-byte
unchanged after a failure. Writing in place cannot deliver that; a temporary file plus a rename
can, because `rename(2)` is atomic within a filesystem and either replaces the target wholly or
not at all. The temporary must live in ARCHIVE's own directory so the rename never crosses a
filesystem boundary (a cross-device `rename` fails with `EXDEV`, and copying instead would
reintroduce the partial-write window). `mkstemp` creates with `O_CREAT|O_EXCL` and mode `0o600`
at creation, which is precisely SR-107. **Verified**: `mkstemp` yields mode `0o600`.

The temporary file is created only *after* member enumeration has finished, so it can never
become a member of the archive being written (SR-109), even when ARCHIVE sits inside a PATH.

**Alternatives considered**: writing straight to ARCHIVE and unlinking on failure — rejected,
it destroys a pre-existing archive before knowing whether the new one can be completed, which is
exactly the loss User Story 2 exists to prevent; a temporary file in `/tmp` plus a copy —
rejected for the `EXDEV` copy window above and because it would briefly place the user's data
on another filesystem.

---

## R-105 — Archive-path state decided by one `os.lstat`, re-checked before the rename

**Decision**: a single `os.lstat(ARCHIVE)` classifies the target before any work:

| State at ARCHIVE | Outcome |
|---|---|
| absent, parent directory exists and is a directory | proceed |
| absent, parent missing or not a directory | `TarxError` → exit 2 (FR-116) |
| regular file, no `--overwrite` | `OverwriteConflict` → exit **3** (FR-114) |
| regular file, `--overwrite` | proceed; the rename replaces it (FR-115) |
| directory, symlink, FIFO, device, socket | `TarxError` → exit 2, with or without `--overwrite` (FR-116) |

`os.lstat` (never `os.stat`) is what makes a symlinked ARCHIVE visible as a link rather than as
its target, so SR-102's "MUST NOT follow such a link" holds for the output path as well as for
inputs. The check is repeated immediately before `os.rename`, and a regular file that appeared
in the meantime without `--overwrite` raises the same `OverwriteConflict`.

**Rationale**: exit 3 must mean *solely* a pre-existing regular file (FR-121), so the branch
that produces it is one line in one function, mirroring how `extract` keeps its single exit-3
raise site. The repeat check costs one `lstat` and narrows the window in which a concurrently
created archive would be silently replaced — cheap insurance against the one mistake the spec
calls the most expensive this tool can make.

**Alternatives considered**: `os.link(tmp, ARCHIVE)` + `unlink(tmp)` for the no-overwrite case,
which fails with `EEXIST` atomically — rejected as filesystem-dependent (hard links are not
universally available) and because it splits the finalisation into two code paths for a race
that is outside the threat model of a single non-privileged user (consistent with
[`001-tarx-cli/research.md`](../001-tarx-cli/research.md) R-007). The repeated `lstat` is the
cheaper 90% of the benefit with none of the branch.

---

## R-106 — Iterative traversal with `os.scandir(follow_symlinks=False)`

**Decision**: directories are walked with an explicit stack (a list used LIFO), never by
recursion. Each entry's kind is taken from `DirEntry.is_dir(follow_symlinks=False)`,
`is_file(follow_symlinks=False)`, and `is_symlink()`.

**Rationale**: SR-103 requires traversal that cannot be steered outside the named trees;
`follow_symlinks=False` answers the kind question from the entry itself, so a symlink to a
directory is seen as a symlink and refused by SR-102 rather than descended into.
**Verified**: for a tree containing `f.txt`, `sub/`, and `link → /etc`, `scandir` reports
`is_dir(follow_symlinks=False)` false and `is_symlink()` true for `link`.

Recursion is avoided for a specific reason: the spec's "very large or very deep tree" edge case
must fail through the SR-105 bounds, but a tree deeper than `sys.getrecursionlimit()` would
raise `RecursionError` first — not an `OSError`, so it would escape `cli.main`'s handler as a
traceback on stderr and breach SR-111. An explicit stack cannot raise it. `os.walk` is also
unsuitable: it cannot produce FR-106's "directory member first, then its entries in sorted
order, each directory's contents immediately following it" ordering without reordering its
output, and it swallows per-directory errors by default.

**Alternatives considered**: `os.walk(followlinks=False)` — rejected for ordering and for its
silent `onerror=None` default, which would turn an unreadable subdirectory into a missing
member (forbidden by the spec's "Unreadable PATH" edge case); `pathlib.Path.rglob("*")` —
rejected, it follows symlinked directories and gives no control over ordering.

---

## R-107 — The ordering rule, concretely

**Decision**: PATHs are processed in command-line order. For a file PATH, one file member. For
a directory PATH: emit the directory member, then push its entries sorted by name so they are
visited in ascending order, each subdirectory's contents following immediately after its own
member (pre-order depth-first). Sorting is on the entry name as a Python `str`, i.e. by
code point.

**Rationale**: FR-106 names exactly this order, and code-point sorting is the only ordering
that is stable across locales and filesystems — a locale-sensitive collation would make
"running `create` twice produces the same order" false on a machine where `LC_COLLATE` changes.
Pre-order (directory before contents) is also what `extract` needs: it creates parents before
children, so the archive never asks it to create a file inside a directory it has not yet seen.

**Alternatives considered**: sorting by raw `bytes` via `os.fsencode` — identical for all names
`tarfile` can record and harder to read; breadth-first order — rejected, it violates FR-106's
"each directory's contents immediately following it".

---

## R-108 — Duplicate and nesting detection by member-name map

**Decision**: enumeration maintains an ordered `dict` from member name to the PATH that
produced it. Inserting a name that is already present is the single detection point for all
three cases SR-104 names: the same PATH given twice, two PATHs that normalise to the same
location, and one PATH nested inside a directory PATH.

**Rationale**: all three collapse into "two members would carry the same name" once PATHs are
normalised (FR-104), so one check covers them, and the message can name both the duplicated
member and the two PATHs responsible (FR-113). This also guarantees the stronger downstream
property: `extract` refuses an archive with duplicate members (001's SR-009), so an archive
that passes this check cannot be rejected by `extract` for that reason (FR-109).

**Alternatives considered**: pairwise prefix comparison of the PATHs before traversal —
rejected, it catches `photos` + `photos/a` but not two different spellings of the same file
reached through different normalisation, so the name map would be needed anyway.

---

## R-109 — Excluding the archive from itself (SR-109)

**Decision**: the normalised ARCHIVE path is compared against every candidate member during
enumeration. A match **discovered by traversal** is omitted from the member list silently and
is not counted in N. A match where ARCHIVE is **named directly as a PATH** is refused with an
error naming it, exit 2.

**Rationale**: the two cases differ in what the user asked for. `create photos/out.tar photos`
is a normal, documented request (spec Edge Cases) that must succeed, and it can only succeed if
`out.tar` is dropped when traversal finds it — which happens only on a rerun with
`--overwrite`, since on the first run the file does not yet exist. By contrast,
`create out.tar out.tar` asks for something that cannot be honoured at all, and Principle II
forbids quietly producing an archive that omits a thing the user explicitly named. Silent
omission is therefore confined to the one case SR-109 mandates it.

The temporary file needs no exclusion rule of its own: R-104 creates it after enumeration ends,
so it is never a candidate.

**Alternatives considered**: refusing both cases — rejected, it would make the spec's own edge
case impossible; omitting both silently — rejected under Principle II.

---

## R-110 — Detecting a file that changes size while it is read (FR-120)

**Decision**: each regular file is opened once with `os.open(path, O_RDONLY | O_NOFOLLOW)`; its
size is taken from `os.fstat` **on that descriptor**; the header declares that size; the
contents are streamed through a reader object that fills every `read()` request exactly and
raises a `TarxError` if the descriptor reaches EOF before the declared size is delivered. After
`addfile` returns, one extra `os.read(fd, 1)` must come back empty; a non-empty result means
the file grew. Either way the command fails under FR-119, leaving no archive.

**Rationale**: fstat-on-the-open-descriptor removes the stat/open race, `O_NOFOLLOW` closes the
window between the enumeration-time kind check and the read (a file replaced by a symlink in
between fails with `ELOOP` rather than being followed, SR-102), and the two probes catch the
two directions a size can change in. **Verified**: a file shrunk from 200 to 100 bytes raises
through our reader with our own message; a file grown from 100 to 150 leaves a readable
leftover byte; an unchanged 300 KB file passes both probes and round-trips byte-for-byte.

The reader must fill each request exactly because `tarfile.copyfileobj` treats a short read as
an error — **verified**: left to itself `tarfile` raises a bare `OSError("unexpected end of
data")`, which would reach the operator as a generic message naming no file. Detecting the
condition ourselves is what lets FR-113's "name what was rejected and why" hold.

Reads are issued in `archive.COPY_CHUNK_BYTES` (64 KiB) chunks, the constant the extract path
already uses, so no file's contents are ever held whole in memory (SR-106).

**Alternatives considered**: catching `tarfile`'s `OSError` and rewording it — rejected, it is
indistinguishable from a genuine write failure on the output descriptor; comparing `st_size`
before and after without streaming checks — rejected, it misses a file that is rewritten to the
same length, which the exact-fill reader and leftover probe do not claim to catch either but
which FR-107 does not require (the member matches what was read).

---

## R-111 — Bounds enforced twice: declared at enumeration, actual at write

**Decision**: enumeration counts members against `archive.MAX_MEMBERS` and sums `st_size`
against `archive.MAX_TOTAL_BYTES`, rejecting any single file over `archive.MAX_MEMBER_BYTES`.
The write pass counts the bytes it actually streams against the same two byte bounds. The
constants are imported from `tarx.archive`; no new constant is defined and none becomes an
option.

**Rationale**: SR-105 fixes the bounds as "the same as those the existing commands enforce", so
sharing the module-level constants makes that identity structural — if one is ever changed, both
ends move together and the round-trip promise of FR-109 cannot drift. Checking at enumeration
is what FR-118 requires (all checks before any content is written); checking again during
writing catches a tree that grows between the two passes. Because the write target is a
temporary file (R-104), an exceeded bound mid-write still leaves no archive — unlike `extract`,
`create` has no "may be partially written" exception to document.

**Alternatives considered**: enumeration-time checks only — rejected, a tree can change between
the passes; separate create-side constants — rejected, they could drift apart from the bounds
`list` and `extract` apply.

---

## R-112 — Validate the computed member names with the *existing* validator

**Decision**: every member name produced by enumeration is passed through the existing
`paths.validate_member_name` before the write pass begins, in addition to the source-path checks
of R-113.

**Rationale**: FR-109 promises that no member of a created archive is rejected by any
requirement of the 001 spec, and `validate_member_name` *is* the function `extract` uses to
decide that. Running the producer's output through the consumer's own gate turns that promise
from a code-review argument into an executed check, at the cost of one lexical pass over at most
10,000 names. It also means a future change to either side cannot silently break the round trip.

**Alternatives considered**: trusting construction — rejected; the whole point of FR-109 is that
the two commands must agree, and agreement that is asserted rather than checked is the kind of
thing that regresses.

---

## R-113 — Source-path validation lives in `paths.py`, as a new function

**Decision**: add `validate_source_path(path) -> tuple[str, ...]` to `src/tarx/paths.py`,
reusing the module's existing `_components()` helper and `_DRIVE_PREFIX` pattern. The existing
`validate_member_name` is left byte-for-byte unchanged.

**Rationale**: 001's Structure Decision makes `paths.py` "every decision about a member *name*",
so SR-101's rules belong beside SR-001's. The two cannot be the same function because their
messages differ in the only way that matters to an operator: `validate_member_name` talks about
a member inside an archive and the destination it must stay within, while SR-101 must name *the
PATH as the user typed it* (FR-113). Sharing the private helpers keeps the normalisation rules
identical, which is what makes `./photos/` and `photos` name the same member (FR-104).

Rules, first failure wins: non-empty; not absolute; no leading backslash (covers `\dir` and the
`\\server\share` UNC form); no `C:`-style drive prefix; no `..` component; and — specific to
sources — the normalised component tuple must be non-empty, which is what rejects `.`, `./`,
and `""` as PATHs naming the current directory itself.

**Alternatives considered**: a new `sources.py` module — rejected under Principle IV, it would
split name handling across two files for one function; generalising `validate_member_name` with
a "context" parameter — rejected, a flag that only selects message wording is the kind of
configurability the constitution asks us not to add, and it would touch code the 001 suite
depends on.

---

## R-114 — `create` is a third `argparse` subparser

**Decision**: add a `create` subparser with `ARCHIVE` (one positional), `PATH` (`nargs="+"`),
and `--overwrite`. Extend the existing empty-string guard in `cli._parse` to reject an empty
ARCHIVE and any empty PATH.

**Rationale**: `argparse` already produces FR-102's exact behaviour — a missing ARCHIVE, a
missing PATH, an unrecognised option, and an unknown command each write usage to stderr and exit
2 — which is why 001 chose it (R-004); a third subparser inherits all of that for free and
cannot change how `list` and `extract` parse (FR-101). The empty-string checks must stay ours
because `argparse` accepts `""` for a positional.

Consequence recorded for the contract: a PATH beginning with `-` is read as an option and is a
usage error; `--` ends option parsing, so `create out.tar -- -weird-name` works. This matches
every other POSIX tool and needs no code.

**Alternatives considered**: a hand-rolled parser for `create` — rejected, it would make FR-101's
"no observable change to `list` and `extract`" harder to argue, not easier.

---

## R-115 — The success line, and a closed stdout

**Decision**: `cli.run_create` prints `created {escaped ARCHIVE} with {N} files` inside a
`try/except BrokenPipeError` that calls the existing `_silence_stdout_at_shutdown()` and returns
2, exactly as `run_list` does.

**Rationale**: the spec's last edge case requires that a closed stdout be reported as a failure
(status 2) *after* the archive has been completed, without a crash report on stderr. The
existing helper exists for precisely this and is already covered by 001's tests; reusing it
keeps one implementation of the shutdown-flush suppression. ARCHIVE is echoed through
`escape_name` before printing (SR-110), so a crafted archive name cannot inject a second line
that looks like another command's output.

**Alternatives considered**: `signal.signal(SIGPIPE, SIG_DFL)` — rejected in 001 (R-011) because
exit 141 is not among the three statuses FR-121 permits, and nothing has changed.

---

## R-116 — Unreadable inputs need no separate pre-check

**Decision**: no explicit readability probe is performed. An unreadable directory fails at
`os.scandir` during enumeration; an unreadable file fails at `os.open` during the write pass.
Both become a `TarxError` naming the path, exit 2.

**Rationale**: the spec's "Unreadable PATH" edge case requires failure with no archive, not
failure at a particular moment, and R-104's temporary-file design makes a late failure
indistinguishable in its effects from an early one — nothing appears at ARCHIVE either way. A
pre-check would be a second `open()` of every file, doubling the syscalls for a guarantee the
design already provides, and it would still be a time-of-check/time-of-use approximation.

**Alternatives considered**: `os.access(path, os.R_OK)` during enumeration — rejected, it
answers for the real uid rather than the effective one and is explicitly documented as
race-prone; opening every file in pass 1 and holding the descriptors — rejected, it would exhaust
the file-descriptor limit on a 10,000-member tree.

---

## R-117 — Compression chosen by suffix, case-insensitively

**Decision**: `ARCHIVE.lower().endswith((".tar.gz", ".tgz"))` selects gzip; anything else is a
plain tar. The comparison is on the archive name as given.

**Rationale**: FR-108 states the rule and SR-110's escaping applies only to display, not to this
decision. `str.lower()` is the whole of "ignore letter case" for the ASCII suffixes in question.
This is the one place in the tool where a filename determines a format; `list` and `extract`
keep deciding from content (001 FR-008), so a deliberately misnamed archive still reads
correctly — a property worth a test of its own.

**Alternatives considered**: `os.path.splitext` twice — rejected, it mishandles `.TGZ` and names
like `archive.tar.gz.bak` no better than a direct suffix test does.

---

## R-118 — Test placement and the traceability gate

**Decision**: six new test modules under `tests/`, plus one new case in `tests/test_performance.py`
and new source-tree builders in `tests/helpers.py` and `tests/conftest.py`. No existing test file
is modified except by addition.

**Rationale**: `tests/test_traceability.py` already scans **all** `specs/*/spec.md` files, so the
moment this spec was merged the gate began failing for the uncovered `FR-1xx`/`SR-1xx`
identifiers — **verified**: the suite is currently `144 passed, 1 failed`, the single failure
being that gate. That is the intended behaviour of the gate and it is what this feature's tests
resolve; it is also why MC-102's "the existing suite must continue to pass unmodified" is read
as *the 001 behaviour tests* passing unmodified, which they do today and must continue to.

**Alternatives considered**: relaxing the gate to one spec at a time — rejected, it would weaken
the only mechanical enforcement of Principle III the project has.
