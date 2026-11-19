# Phase 0 Research: Tar Archive Listing and Extraction CLI

**Feature**: `001-tarx-cli` | **Date**: 2026-11-19

The Technical Context in [plan.md](./plan.md) carries no `NEEDS CLARIFICATION` markers: the
language, dependency policy, test framework, and package layout were all fixed by the feature
description and the constitution. What remained were (a) stdlib-mechanism choices and (b) a
handful of spec readings that the implementation has to settle one way or the other. Both are
resolved below.

---

## 1. Compression and format detection

**Decision**: Open with `tarfile.open(path, "r:*")` for both commands.

**Rationale**: FR-004 requires detection from content, not filename. The `"r:*"` mode sniffs the
stream and transparently handles uncompressed and gzip input (and other compressions tarfile
supports), so a gzip archive named `.tar` and a plain archive named `.tar.gz` both work with no
extension inspection anywhere in the code. It opens for random access, which the two-phase
`extract` needs in order to read member bodies after the validation pass. Non-tar input raises
`tarfile.ReadError`, which maps directly to exit 2 (FR-013).

**Alternatives considered**:
- Sniff the gzip magic bytes (`\x1f\x8b`) and pick `"r:gz"` / `"r:"` — reimplements what tarfile
  already does, and adds a failure mode of its own. Rejected.
- Branch on the filename extension — directly contradicts FR-004. Rejected.
- Stream mode `"r|*"` — non-seekable, so member bodies can only be read in the single forward
  pass. That forbids validate-then-write (FR-020). Usable for `list` alone, but running two
  different open modes for two commands buys nothing and costs a branch (Principle IV). Rejected.

---

## 2. Extraction mechanism

**Decision**: Do not use `TarFile.extractall` / `TarFile.extract`. Write members manually:
`os.makedirs(target, exist_ok=True)` for directory members, and for regular files
`tf.extractfile(member)` piped into an opened destination file with `shutil.copyfileobj`.

**Rationale**: Three requirements rule `extractall` out. FR-025 wants every problem reported in
one run, while `extractall` raises on the first; FR-020 wants zero writes when a problem is
detected, while `extractall` writes members as it walks; and the `filter="data"` safety hook that
would otherwise cover FR-014 landed in Python 3.12, above this project's 3.11 floor. Manual
writing also gives FR-022 its diagnostic for free — the member currently being written is in hand
when the `OSError` surfaces. `copyfileobj` uses a fixed-size buffer, satisfying the
larger-than-memory case in SC-008.

**Alternatives considered**:
- `extractall(filter="data")` plus a pre-pass for conflicts — would still abort mid-write on an
  unexpected error from a *different* code path than our own diagnostics, and raises the 3.11
  floor. Rejected.
- `extractall(members=[...])` with a pre-filtered member list — fixes neither the single-problem
  reporting nor the write-as-you-go ordering. Rejected.
- Also deliberately not used: metadata restoration (`chmod`, `utime`, ownership). The Assumptions
  section of the spec puts metadata preservation out of scope, so extracted files take ordinary
  defaults from the process umask.

---

## 3. Member path safety

**Decision**: Validate every member's name **lexically**, independent of filesystem state, before
any write:

1. Reject a name that is absolute (`os.path.isabs` on the POSIX name, i.e. a leading `/`).
2. Normalise with `os.path.normpath`; reject if the result is `..` or begins with `../`.
3. Reject when the normalised result is `.` or empty **and** the member is a regular file (a file
   has no path of its own in that case).
4. The destination target is `os.path.join(dest, normalised)`.

Validate this for **every** member regardless of type, including members that extraction will
skip (symlinks, devices, FIFOs).

**Rationale**: FR-014 says "any archive containing a member whose destination path resolves
outside `DEST`" — *any member*, with no type qualifier. Refusing the whole archive is also the
fail-loudly reading (Principle II): an archive carrying `../../etc/passwd` is hostile input
whether or not this tool would have created that entry. Lexical normalisation rather than
`Path.resolve()` keeps the check independent of symlinks that happen to exist under the
destination, so the verdict is a property of the archive and is reproducible in tests.

**Alternatives considered**:
- `os.path.realpath(target).startswith(realpath(dest))` — depends on live filesystem state, makes
  the result non-reproducible, and the `startswith` form has a classic prefix bug (`/out2` matches
  prefix `/out`). Rejected.
- Sanitising unsafe names by stripping leading `/` and `..` segments — the spec's Assumptions
  explicitly choose refusal over sanitisation. Rejected.
- Checking path safety only for members that would be written — defensible on a narrow reading of
  "destination path", but weaker and less literal than FR-014. Rejected; noted here because it is
  the one place where a reviewer might reasonably expect the other behaviour.

---

## 4. Conflict and type-mismatch classification

**Decision**: During validation, classify each problem into exactly one of two exit classes, then
exit 2 if any class-2 problem exists, else 3 if any class-3 problem exists, else write.

| Problem | Class |
|---------|-------|
| Archive missing / unreadable / not a tar archive | 2 |
| `DEST`, or an ancestor of `DEST`, exists and is not a directory | 2 |
| Member path escapes the destination (§3) | 2 |
| Existing directory where the member is a regular file | 2 |
| Existing non-directory where the member is a directory | 2 |
| Existing non-directory blocking a path needed as a member's **parent** directory | 2 |
| Archive itself stores a regular file at a path another member needs as a parent directory | 2 |
| Existing regular file that a regular-file member would replace, without `--overwrite` | 3 |

**Rationale**: FR-025 fixes the precedence (2 outranks 3, because status 3 means "re-run with
`--overwrite`" and that advice is false for unusable input), and FR-023 puts type mismatches in
the class-2 bucket under both overwrite settings. The last two rows extend FR-023's
"this includes a file sitting where a member's parent directory needs to be" to both sources of
such a block — the existing tree and the archive's own contents. The archive-internal case
(a file member at `a`, another member at `a/b`) is included because FR-020 demands "every check
it is capable of making"; without it, that archive passes validation and then dies with a raw
`NotADirectoryError` halfway through writing.

**Alternatives considered**:
- Let the archive-internal file/directory contradiction fall through to the FR-022 mid-write
  handler — technically compliant with FR-022's wording but a worse outcome: a detectable problem
  would leave a partial tree, which FR-020 is written to prevent. Rejected.
- Report at most one problem per member — unnecessary; the rule adopted instead is that a member
  rejected in step §3 is not checked further (its target path is meaningless), while independent
  problems on independent members are all reported. Keeps messages one-per-cause.

---

## 5. Problem reporting order and the skip notice

**Decision**: Emit problems in a deterministic order: destination-level problems first, then
member problems in archive order, one per line, each on stderr. "Skipped non-regular member"
notices are written on stderr in archive order too, but are **not** problems: they never affect
the exit status and never suppress the summary line.

**Rationale**: FR-025 requires all problems, one per line; determinism is what makes the messages
assertable in tests (Principle III). FR-015 is explicit that a skip alone must not cause a
non-zero exit.

---

## 6. Counting `N` for `extracted N files`

**Decision**: Build the write plan as a mapping keyed by destination path, keeping the **last**
member for each path, and report `N = len(file plan)` — the number of distinct destination file
paths written.

**Rationale**: FR-008 says `N` is "the count of regular files it wrote" and the Edge Cases say
that for duplicate member names "the later member wins at the destination". Counting both writes
of a duplicated path would report `N = 2` with one file on disk, contradicting SC-003 ("matches
the number of regular files actually present from that run"). Keying the plan by destination path
resolves both at once: the later member naturally wins, each path is written exactly once, and the
count matches what is on disk. The word `files` stays plural for every `N` including 0 and 1
(FR-008, clarification session Q5).

**Alternatives considered**:
- Count every write, writing duplicates twice — matches FR-008's most literal wording but breaks
  SC-003 and does redundant I/O. Rejected.
- Count only newly created files, excluding replacements — contradicted by FR-010 ("count every
  regular file it wrote — replaced or new"). Rejected.

---

## 7. Invalid invocations and exit code 2

**Decision**: Use `argparse` with two subparsers (`list`, `extract`) and rely on its default
error behaviour: usage message to stderr, exit status 2. No `type=` converters that touch the
filesystem.

**Rationale**: `argparse`'s own usage-error exit code is already 2, which is exactly what FR-017
and the spec's Assumptions require, so the requirement is met with zero custom code. Because
argument validation is purely syntactic, FR-017's "nothing is read or written" holds naturally.
`--help` exits 0 with usage on stdout, which is what SC-009 asks for (both commands, their
operands, and `--overwrite` discoverable from the tool itself).

**Alternatives considered**:
- Hand-rolled argv parsing — more code, and the usage text would have to be maintained by hand.
  Rejected under Principle IV.
- Catching `SystemExit` to re-map argparse's code — unnecessary, since the codes already agree.

---

## 8. Non-ASCII member names

**Decision**: `tarfile` decodes member names with `utf-8` and `errors="surrogateescape"` by
default. In `main`, reconfigure `sys.stdout` and `sys.stderr` with `errors="surrogateescape"`
before writing, so names round-trip to the exact bytes recorded in the archive.

**Rationale**: The Edge Cases require names to be listed and extracted "using the names recorded
in the archive". Without the reconfigure, a name that is not valid UTF-8 produces a
`UnicodeEncodeError` traceback — a crash rather than a diagnostic, which Principle II forbids.
`io.TextIOWrapper.reconfigure` is stdlib and available well below the 3.11 floor. Surrogate-escaped
names also pass through `os.path` and `open()` correctly on POSIX, so extraction needs no special
handling.

**Alternatives considered**:
- Write names to `sys.stdout.buffer` as bytes — bypasses the text layer and complicates mixing
  with the summary line and with pytest's `capsys`. Rejected.
- Replace undecodable characters — loses the exact name and silently alters output. Rejected under
  Principle II.

---

## 9. `list` output form for directory and `./` members

**Decision**: Print `member.name` with trailing `/` characters stripped. If stripping would leave
an empty string, print the name unchanged.

**Rationale**: FR-024 and clarification Q3 require no trailing slash so each line is directly
usable as a path. Many archives record a root member as `./`, which strips to `.` — a valid
relative path, so it is printed as-is rather than special-cased. The empty-result guard exists so
a pathological name consisting only of slashes still produces a line rather than a blank one.
`list` applies no normalisation beyond this and no filtering (FR-003): members of every type are
printed, in archive order, as many times as they appear.

---

## 10. Test strategy and requirement traceability

**Decision**: `pytest`, with archives built at test time by `tarfile` into `tmp_path` fixtures
(no committed binary assets). Most tests call `tarx.cli.main(argv)` in-process and assert on the
returned status plus `capsys` output; a small number run `python -m tarx` as a subprocess with
`PYTHONPATH=src` to prove the documented invocation and real process exit statuses. Requirement
IDs appear in test names and docstrings, and `tests/test_traceability.py` parses the FR IDs out of
`spec.md` and asserts each is referenced somewhere under `tests/`.

**Rationale**: Principle III requires an explicit, auditable requirement-to-test mapping, and
FR-021/SC-007 make that mapping itself a requirement — so it gets a test. In-process calls keep
the suite fast and let `test_validation.py` assert on `core`'s validation results directly;
the subprocess tests close the gap that in-process calls cannot cover (`__main__.py`, real exit
status, `src` on `PYTHONPATH`). `pythonpath = ["src"]` in pytest's config makes `import tarx` work
without installing anything, keeping runtime dependencies empty per Principle I.

**Alternatives considered**:
- Subprocess for every test — slower and gives no access to intermediate validation state, making
  per-problem assertions coarser. Rejected as the default, kept for the handful of cases that need
  it.
- Committed fixture archives — opaque in review, and awkward for the permission/large-archive
  cases. Rejected.
- `coverage`-based requirement auditing — a third-party tool, and line coverage does not prove
  requirement coverage anyway. Rejected.

---

## Open questions

None. All five clarification-session answers are reflected above (§3, §4, §5, §6, §9), and no
`NEEDS CLARIFICATION` marker remains in the Technical Context.
