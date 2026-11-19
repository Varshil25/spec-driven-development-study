# Phase 0 Research: Archive Creation Command

**Feature**: `002-create-command` | **Date**: 2026-11-19

The specification carries no `NEEDS CLARIFICATION` markers — its five clarification rounds and its
Assumptions section settled the behavioural questions. What remains is *technical*: which stdlib
mechanisms deliver the specified behaviour, and where the obvious mechanism would quietly violate a
requirement. Each section below records a decision, the rationale, and the alternatives evaluated.
Claims marked **measured** were verified against CPython 3.13.17 before being written down; the
probe output is quoted inline.

---

## 1. Where the new code lives

**Decision**: Extend `src/tarx/core.py` (validation, planning, writing) and `src/tarx/cli.py`
(parser, dispatch, streams). No new runtime module.

**Rationale**: `001-tarx-cli` split the package along a single seam — `core` never prints and never
exits, `cli` is the only module that touches streams and statuses — and that seam is what makes
validation assertable in-process. `create` fits inside it unchanged. It also reuses six existing
pieces: `TarxError`, `Problem`, `resolve_exit_status`, `_reason`, `_is_real_dir`, `_is_real_file`.
Notably `resolve_exit_status` already implements FR-018's "class 2 outranks class 3" rule, so that
requirement is satisfied by reuse rather than by new code.

**Alternatives considered**: a new `src/tarx/create.py`. Rejected — it would import those six
names back out of `core`, adding a file and an import edge without removing any moving part
(Principle IV). `core.py` grows from 516 to roughly 700 lines, which is still one readable module.

---

## 2. Selecting compression from the archive name

**Decision**: `mode = "w:gz" if archive.endswith((".tar.gz", ".tgz")) else "w"`. Literal,
case-sensitive suffix match on the string the user supplied, with no normalisation.

**Rationale**: FR-005 and the spec's "Extension matching is literal and case-sensitive" assumption
say exactly this. `str.endswith` with a tuple is the whole implementation. The asymmetry with
`list`/`extract` — which sniff content via `"r:*"` — is deliberate and non-conflicting: the name is
load-bearing only at creation time (FR-005 vs `001-tarx-cli` FR-004).

**Alternatives considered**: `mimetypes.guess_type` (drags in extension tables and would accept
`.gz` alone); case-insensitive matching (rejected by the spec); inspecting `os.path.splitext`
twice (equivalent but wordier, and mishandles `.tgz`).

---

## 3. Validation must finish before the archive is opened

**Decision**: Run the complete validation pass — archive path, every operand, every entry in every
named tree — and return problems to `cli` *before* calling `tarfile.open(..., "w")`.

**Rationale**: **Measured** — `tarfile.open(name, "w")` creates the file at open time:

```text
3) before: False
3) after open: True        # immediately after tarfile.open("created.tar", "w")
```

So "creates no archive" (FR-013, FR-014, FR-021, FR-027, SC-006) is only achievable if the archive
is opened last. This makes FR-016 a hard ordering constraint on the implementation rather than a
stylistic preference, and it is why the readability of every entry is established during
validation (the FR-016 clarification) rather than discovered during the write.

**Alternatives considered**: writing to a temporary file and renaming on success. This would give
true all-or-nothing semantics even for mid-write failures — but FR-027 forbids creating anything
other than the archive itself, a temporary sibling is still a file the user did not ask for, and
FR-021 explicitly sanctions leaving an incomplete archive. Rejected as both non-compliant and
more machinery than the spec wants.

---

## 4. Hand-built `TarInfo` instead of `TarFile.add()` — the hard-link trap

**Decision**: Build each member's `TarInfo` directly (`name`, `type`, `size`, `mode`, `mtime`) and
write it with `addfile(info, fileobj)`. Do not use `TarFile.add()`.

**Rationale**: **Measured** — `TarFile.add()` maintains an inode cache and stores the *second* name
of a hard-linked file as a zero-byte link member:

```text
1)  add() types:    [('t/a.txt', '0', 1), ('t/d/link.txt', '1', 0)]   # type '1' = LNKTYPE, size 0
1b) manual types:   [('t/a.txt', '0', 1), ('t/d/link.txt', '0', 1)]   # both REGTYPE, both size 1
```

FR-015 is explicit that a file carrying more than one name is an ordinary regular file for
`create`'s purposes, that each such name must be stored and counted with its own copy of the
contents, and that "no name beneath a given `PATH` is missing from the archive". `add()` would
produce an archive whose second name extracts to nothing under `001-tarx-cli`'s `extract` (which
skips link members) — a silent wrong answer, forbidden by Constitution Principle II. Two further
benefits: `add()` appends a trailing `/` to directory names (see §5) and re-`stat`s every entry,
both of which hand-building avoids.

**Alternatives considered**: calling `gettarinfo()` and then forcing `info.type = REGTYPE` and
`info.linkname = ""`. Works, but it relies on correcting a cache mutation after the fact and still
leaves the trailing-slash behaviour to undo — more indirection for the same result.

---

## 5. Member names: normalisation, and directories without a trailing slash

**Decision**: A member name is `os.path.normpath(operand)` for the operand itself, and that joined
with `/`-separated components for entries beneath it. Directory members are stored **without** a
trailing slash. A `PATH` that normalises to `.` contributes no member of its own; its entries are
contributed under their plain relative names.

**Rationale**: **Measured** — `normpath` already implements every normalisation the spec's edge
cases ask for, so no hand-rolled string surgery is needed:

```text
5) 'photos/'    -> 'photos'     5) './photos'  -> 'photos'
5) 'photos/./a' -> 'photos/a'   5) '../x'      -> '../x'    isabs False
5) '.'          -> '.'          5) '/abs'                   isabs True
```

Directory members are stored without a trailing slash because the tar *type byte*, not the name,
is what records directory-ness. **Measured**:

```text
2) names: ['photos', 'photos/a.jpg']   [('photos', True), ('photos/a.jpg', False)]
```

`isdir()` is `True` for `photos` stored as `DIRTYPE`. This makes the stored name identical to what
`list` prints (no stripping needed), identical to what the spec's acceptance scenarios name
("the archive holds the members `photos`, `photos/a.jpg`"), and identical to the FR-026 sort key —
one string instead of three variants. `tarfile.getnames()` therefore matches the spec's wording
directly, which keeps the US1 ordering tests honest.

The `PATH = "."` case is the one genuine gap in the spec, and it is resolved by FR-004 rather than
invented: FR-004 requires every member name to be a relative path with no leading `./`, and `.` is
not such a name. So the current directory contributes its *contents*, not itself. Extraction
recreates that shape correctly, because `extract`'s `DEST` plays the role of the directory.

**Alternatives considered**: storing `photos/` as GNU tar does (rejected — observable through
`list` and `tarfile.getnames()`, and it would complicate the sort key for no gain); refusing `.`
as an unsafe path (rejected — `.` does not resolve outside the current directory, so FR-014 does
not reach it, and refusing would be inventing a rule the spec does not state).

---

## 6. Ordering and de-duplication

**Decision**: Collect each operand's subtree, sort it by full member name compared as a Python
string, and append to the plan in operand order. Skip any member name already in the plan
(`dict` keyed by member name, insertion-ordered).

**Rationale**: FR-026 specifies exactly this two-level rule — operands in the order given, each
operand's members sorted by full member name as text — and the clarification session confirmed
that sorting the *full* name is what places `d` before `d/a.txt` before `d/b/c.txt` before
`d/z.txt` without a separate directory-first rule. Because the whole subtree is sorted after
collection, the order `os.scandir` happens to report entries is irrelevant, which is the
substance of SC-012. FR-020 makes identity the member *name*, so a `dict` keyed by name gives
"first operand to reach it wins the position" for free — and, with §4, correctly stores two names
for one inode as two members while collapsing two routes to one name into one member.

Sorting is by Python string comparison, i.e. Unicode code point order; names that are not valid
UTF-8 arrive as surrogate-escaped `str` and sort by their surrogate code points — arbitrary but
deterministic, which is all FR-026 and SC-012 require.

**Alternatives considered**: `os.walk(topdown=True)` with `dirnames.sort()`. This yields
directory-then-contents order per directory but *not* globally sorted full-name order (a
subdirectory's contents are emitted after all of its siblings' names), so `d/b/c.txt` would land
after `d/z.txt`, contradicting FR-026's worked example. Rejected. A recursive `os.scandir`
collector feeding one final `sorted()` is both simpler and correct.

---

## 7. Keeping the archive out of itself

**Decision**: Compare `os.path.normpath(os.path.abspath(entry))` against the same for `ARCHIVE`,
and omit the matching entry from the plan silently.

**Rationale**: FR-019. An absolute-path string comparison is deterministic, needs no filesystem
call, and works whether or not the archive exists yet — which matters because `os.path.samefile`
requires both paths to exist, and on a first run the archive does not. The exclusion is what makes
repeat runs with `--overwrite` produce the same member sequence as the first run (SC-012): on run
two the archive *is* present inside the tree being walked, and without this rule it would appear
as a member. Excluding it before the readability check also avoids a pointless open.

**Alternatives considered**: `os.path.samefile` guarded by `os.path.exists` (more calls, same
answer, fails on the common case); comparing by `(st_dev, st_ino)` (same problem, plus it would
make the archive's own identity depend on an inode that is about to be replaced).

---

## 8. Validating readability — and the root-privilege testability problem

**Decision**: During validation, open every planned regular file for reading and close it
immediately; rely on `os.scandir` raising for an unlistable directory. Report either failure as
C7 (`cannot read '{path}'`), class 2. In the test suite, cover this requirement **twice**: a real
`chmod 0o000` test marked `skipif(os.geteuid() == 0)`, and a `monkeypatch`-injected `OSError` test
that runs unconditionally.

**Rationale**: The FR-016 clarification requires readability to be established before writing, and
an actual open is the only check that is true at the moment it is made. `os.access(path, os.R_OK)`
was rejected: it consults permission bits rather than attempting the operation, and it answers the
wrong question for ACLs.

The testability note is the important half. **Root bypasses permission bits**, so a `chmod 0o000`
file is still readable when the suite runs as root — and this repository's test environment does
run as root. A permission test alone would therefore pass vacuously, which Principle III forbids
(a requirement "covered" by a test that cannot fail is not covered). Pairing a skipped-under-root
real test with an always-running injected-error test keeps FR-021's validation branch genuinely
exercised everywhere. The same technique covers the mid-write failure of FR-021's second half,
which is otherwise reachable only by filling a disk.

**Alternatives considered**: running the permission test under an unprivileged subprocess user
(needs account setup, not portable); skipping the requirement's test and noting it as unverifiable
(forbidden by Principle III).

---

## 9. Memory and time budget

**Decision**: Stream every file through `addfile(info, fileobj)`, which copies via `tarfile`'s
internal fixed-size buffer. Never read a file whole, never build the archive in memory.

**Rationale**: **Measured** on a 40 MB file, peak additional Python allocation via `tracemalloc`:

| Mode | Peak | Archive size |
|------|------|--------------|
| `w` (plain tar) | **44 KiB** | 40 MB |
| `w:gz` (gzip) | **519 KiB** | 40 MB |

Plain-tar peak is the copy buffer and nothing else; the gzip figure is zlib's compressor state,
also fixed. Neither grows with the file, which is precisely the property SC-010's restated form
measures ("peak additional memory stays under a small fixed ceiling that does not grow with file
size"). A read-it-all-in implementation would peak near 40 MB and fail the test, so the check has
teeth. Recommended test ceiling: 2 MiB, asserted at two different file sizes so that *growth*, not
just magnitude, is what fails.

The 10,000-file time budget is met comfortably: both the validation walk and the write pass are
linear in entry count, with two `open`+`close` pairs and one `stat` per file.

**Alternatives considered**: `shutil.copyfileobj` into a manually written tar header (reimplements
`tarfile`); `tarfile.open(mode="w|gz")` streaming mode (needless — we have a seekable file, and
stream mode forbids the random access `tarfile` uses for its own bookkeeping).

---

## 10. Classifying entries, and the skip vocabulary

**Decision**: Classify with a single `os.lstat` per entry and `stat.S_ISREG` / `S_ISDIR`;
everything else is skipped with a label derived from the mode bits — `symbolic link`,
`character device`, `block device`, `FIFO`, `socket`, `unsupported file type`. Never follow a
symbolic link.

**Rationale**: `lstat` is what makes "symbolic links are not followed" true by construction
(`stat` would report the target's type and silently store a second copy of the data, or descend
outside the current directory). The label set mirrors `001-tarx-cli`'s `KIND_LABELS` so a user sees
the same vocabulary from both commands, with `socket` added — the filesystem can present one and
an archive cannot, whereas the reverse direction (`hard link`) is a reading-only concept (FR-015).
Skip notices are emitted **only on a successful run**, matching `extract`'s existing behaviour:
on a failed run no archive exists, so nothing was "left out of" anything, and SC-006 wants a
failing run's stderr to carry the problems.

An operand that *names* a non-regular entry directly is skipped by the same rule and is not an
error (spec edge cases), so `create x.tar alink` succeeds with `created x.tar with 0 files` and one
skip notice. A consequence worth recording: an operand written as `alink/` is also skipped rather
than dereferenced, because normalisation strips the trailing slash before `lstat` sees it. POSIX
shells would resolve `alink/` to the target directory; `create` does not, which is the stricter and
more predictable reading of "symbolic links are not followed".

---

## 11. Diagnostics: a separate template namespace

**Decision**: Number `create`'s templates **C1–C11** in
[contracts/create-cli.md](./contracts/create-cli.md), leaving `001-tarx-cli`'s D1–D14 untouched.
Reuse D10's exact wording for the refused-overwrite line.

**Rationale**: D-numbers are referenced by the existing contract and by comments in shipped code;
reusing or extending that sequence would make two documents disagree about what "D11" means.
A fresh prefix keeps both contracts readable in isolation. The one place wording is *shared* is the
refused-overwrite diagnostic — `tarx: refusing to overwrite existing file '{path}' (re-run with
--overwrite)` — because `--overwrite` means the same thing in both commands and a user who has
learned one message should not meet a second phrasing of it (spec: "The option name is shared, not
reinterpreted").

---

## 12. Test suite additions that touch no existing file

**Decision**: Put new shared helpers in a new module `tests/create_support.py`, imported by the
new test modules. Leave `tests/conftest.py` and all six existing test modules byte-for-byte
unchanged, reusing their `run_cli`, `run_module`, `tmp_path` and `snapshot_tree` fixtures as they
stand.

**Rationale**: SC-009 demands that the existing suite "passes without a single test being
modified". Keeping every pre-existing file unchanged turns that from a claim into a mechanical
check — `git diff --stat` must show no pre-existing file under `tests/` — which is strictly
stronger than "the tests still pass". `tests/` has no `__init__.py`, so pytest's default `prepend`
import mode puts the directory on `sys.path` and a sibling `import create_support` resolves.

Verified that adding a third subcommand cannot break the existing suite: every help-text assertion
is a substring check (`for token in ("list", "extract", "ARCHIVE", "DEST", "--overwrite"): assert
token in result.stdout`) and `test_fr_001_both_commands_dispatch` only asserts that `list` and
`extract` still dispatch. Nothing asserts an exact usage string or an exhaustive command list, so
`{list,extract,create}` in argparse's output is compatible. `test_traceability.py` scans the
`tests/` corpus for 001's `FR-###` tokens, and adding files can only add matches.

**Alternatives considered**: adding fixtures to `tests/conftest.py` (defensible — a fixture is not
a test — but it gives up the mechanical check for nothing); a `tests/create/` subdirectory with its
own `conftest.py` (inherits root fixtures correctly, but adds a directory level the flat suite
does not otherwise use).

---

## 13. Requirement-to-test traceability across two specs with colliding IDs

**Decision**: Reference this feature's requirements as `CREATE-FR-###` in docstrings and
`create_fr_###` in test names. The new audit test parses only *requirement-definition* lines
(`- **FR-###**:` at the start of a line) from this feature's `spec.md`, and requires each ID to
appear in the test corpus in one of those two create-specific forms.

**Rationale**: Both specs number their requirements `FR-001`-upward, so a naive second audit would
pass vacuously: 001's existing tests already mention `FR-001` through `FR-025`, which would
"cover" 002's FR-001 through FR-025 without a single new test existing. The namespace prefix
removes the collision, leaving the audit meaningful for all 27 requirements.

Parsing only definition lines matters too: this spec cites the earlier feature inline as
"`001-tarx-cli` FR-004", "FR-017" and "FR-022", and a bare `\bFR-(\d{3})\b` sweep would treat those
cross-references as requirements of this feature. Anchoring on `- **FR-###**:` yields exactly the
27 defined IDs.

The existing `test_traceability.py` is left alone, including its third test, which cross-checks
001's spec against **001's** `data-model.md`. This feature's `data-model.md` carries its own
requirement-to-test map and its own cross-check; no 002 identifier is added to any 001 document,
which would otherwise fail that pre-existing test.

---

## Summary of decisions

| # | Decision |
|---|----------|
| 1 | Extend `core.py` + `cli.py`; no new runtime module |
| 2 | Compression from a literal, case-sensitive `.tar.gz`/`.tgz` suffix match |
| 3 | Full validation (including readability) completes before `tarfile.open(..., "w")` |
| 4 | Hand-built `TarInfo` + `addfile`, never `TarFile.add` — hard links must stay regular files |
| 5 | `normpath`-based member names; directories stored with no trailing slash; `.` contributes contents only |
| 6 | Operand order outer, full-member-name sort inner, de-duplicate by member name |
| 7 | Archive excluded from itself by absolute-path comparison |
| 8 | Readability proven by a real `open`; tested via skip-under-root plus injected `OSError` |
| 9 | Stream with `addfile(info, fileobj)`; measured peak 44 KiB (tar) / 519 KiB (gz) on 40 MB |
| 10 | `lstat`-based classification; symlinks never followed; skip notices only on success |
| 11 | New diagnostic namespace C1–C11; refused-overwrite wording shared with D10 |
| 12 | New helpers in `tests/create_support.py`; zero pre-existing test files touched |
| 13 | `CREATE-FR-###` reference namespace; audit parses requirement-definition lines only |

**All `NEEDS CLARIFICATION` items: none outstanding.** The specification arrived fully clarified,
and the five technical ambiguities found while planning (§5 `PATH = "."`, §8 root-privilege
testability, §10 trailing slash on a symlink operand, §12 untouched existing tests, §13 colliding
requirement IDs) are resolved above against stated requirements.
