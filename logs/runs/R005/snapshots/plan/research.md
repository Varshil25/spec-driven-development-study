# Phase 0 Research: Tar Archive List & Extract CLI

**Feature**: `001-tar-archive-cli` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

All findings below were verified empirically on the development machine (CPython 3.13.17,
`pytest` 9.1.1) before being recorded. Nothing here is assumed from documentation alone.

## Summary of unknowns resolved

| # | Unknown from Technical Context | Status |
|---|---|---|
| R1 | Python version / interpreter available | Resolved |
| R2 | How to detect gzip vs. plain tar from content, not file name | Resolved |
| R3 | How `tarfile` reports directory member names (trailing separator) | Resolved |
| R4 | Which exceptions map to exit status 2, and their message quality | Resolved |
| R5 | Whether an empty archive is readable | Resolved |
| R6 | Constant-memory extraction of large members | Resolved |
| R7 | `argparse` program name under `python -m tarx` | Resolved |
| R8 | Precedence between exit status 2 and exit status 3 (spec ambiguity) | Resolved |
| R9 | Counting rule for duplicate member paths | Resolved |
| R10 | Making a bare `pytest` run from the repository root import `src/tarx` | Resolved |
| R11 | Whether to use `TarFile.extractall` or write members directly | Resolved |

---

## R1 — Language and version

- **Decision**: Target Python 3.11+ as the specification mandates; develop and verify against the
  installed CPython **3.13.17**. Use no syntax or stdlib API newer than 3.11.
- **Rationale**: The spec's "Mandated implementation constraints" assumption fixes 3.11 as the
  floor. Everything this feature needs (`tarfile`, `argparse`, `pathlib`, `shutil`, `posixpath`)
  has been stable since well before 3.11, so there is no reason to raise the floor.
- **Alternatives considered**: Pinning to 3.13 (rejected — narrows the supported range for no
  gain); using `tarfile`'s extraction *filters* (added 3.12, see R11) — rejected because it would
  break the 3.11 floor and is not needed.

## R2 — Content-based compression detection

- **Decision**: Open every archive with `tarfile.open(path, mode="r:*")`.
- **Rationale**: Verified that `r:*` sniffs the stream and reads a gzip-compressed tar whose name
  is `mis.tar` (output: `['a.txt']`), satisfying FR-018 with a single stdlib call and zero custom
  magic-byte code. `mode="r"` behaves identically; `r:*` is written explicitly so the intent is
  readable.
- **Side effect, accepted deliberately**: `r:*` also accepts bzip2- and xz-compressed tars. The
  spec requires that tar and gzip work and lists other compression formats as out of scope; it does
  not require other formats to be *rejected*, and a bzip2-compressed tar is still a valid tar
  archive, so FR-024 is not contradicted. Accepting the superset is strictly less code than
  restricting it, which is what Principle IV (Simplicity) asks for.
- **Alternatives considered**: Sniffing the gzip magic bytes (`\x1f\x8b`) and choosing `r:gz` or
  `r:` by hand — rejected: more code, more failure modes, no requirement behind it.

## R3 — Directory member names

- **Decision**: Print `TarInfo.name` verbatim; add no trailing-separator handling.
- **Rationale**: FR-008 requires directory names without a trailing separator. Verified against an
  archive produced by system GNU `tar` (which stores directories as `real/`): `tarfile` reports
  `'real'` and `'real/sub'` — it strips the trailing slash while parsing the header. Archives
  written by `tarfile` itself also report no trailing slash. So FR-008 holds with no extra code.
- **Alternatives considered**: Defensively `rstrip("/")` — rejected as dead code; a test asserting
  the GNU-`tar` case covers the requirement instead.

## R4 — Failure exceptions and diagnostics

Verified mapping from input to raised exception when calling `tarfile.open(..., "r:*")`:

| Input | Exception | Exit status (FR-024/028) |
|---|---|---|
| Path does not exist | `FileNotFoundError` | 2 |
| Path is a directory | `IsADirectoryError` | 2 |
| Path unreadable | `PermissionError` | 2 |
| File of random bytes | `tarfile.ReadError` | 2 |
| Zero-byte file | `tarfile.ReadError` | 2 |

- **Decision**: Catch these and re-raise as one internal error type carrying a message and an exit
  status; the entry point prints `tarx: <message>` on one line to stderr and returns the status.
  Never let the raw exception text reach the user.
- **Rationale**: `ReadError` from `r:*` is **multi-line** — the observed text was:

  ```
  file could not be opened successfully:
  - method gz: ReadError('not a gzip file')
  - method bz2: ReadError('not a bzip2 file')
  - method xz: ReadError('not an lzma file')
  - method tar: ReadError('invalid header')
  ```

  FR-027 demands a short one-line diagnostic naming the offending path, so this text must be
  replaced, not forwarded. This finding is the direct reason the design owns its own message
  catalogue (see [contracts/cli-contract.md](./contracts/cli-contract.md)).
- **Alternatives considered**: Letting exceptions propagate (violates FR-027 and Principle II's
  "no uncaught internal error trace"); printing `str(exc)` (violates the one-line requirement).

## R5 — Empty archives

- **Decision**: Treat an archive with zero members as an ordinary success path; no special case.
- **Rationale**: Verified that a valid tar holding only end-of-archive blocks (10240 bytes, as
  written by `tarfile.open(..., "w")` with nothing added) opens cleanly and reports
  `getmembers() == []`. So `list` prints nothing and `extract` prints `extracted 0 files`, both
  exit 0, with no branch needed. Distinctly, a **zero-byte** file is *not* a valid archive and
  raises `ReadError` → exit 2. These two cases are easy to conflate and get separate tests.

## R6 — Constant-memory extraction

- **Decision**: Copy each regular member with `shutil.copyfileobj(src, dst, length=64 * 1024)`
  where `src = tar.extractfile(member)`.
- **Rationale**: SC-007 requires memory that does not grow with the size of the largest member.
  `copyfileobj` with an explicit buffer length streams in fixed-size chunks; `extractfile` returns
  a lazy file-like object over the archive stream. `member.read()` / `extractfile(...).read()`
  would buffer a whole member in RAM and fail SC-007.
- For `list`, iterate the `TarFile` object directly (`for member in tar:`) rather than calling
  `getmembers()`, so member metadata is consumed as it is parsed. For `extract`, `getmembers()` is
  used because the design needs two passes (validate, then write); 10,000 `TarInfo` headers is a
  few megabytes of metadata, independent of member *contents*, so SC-007 still holds.

## R7 — `argparse` program name under `python -m`

- **Decision**: Construct the parser with an explicit `prog="tarx"`.
- **Rationale**: Verified that running a package as `python -m probepkg` sets
  `sys.argv[0]` to `.../probepkg/__main__.py`, so `argparse` derives `prog == "__main__.py"`.
  Usage text reading `usage: __main__.py ...` would undercut SC-008 (self-explanatory output).
  Setting `prog` explicitly is a one-argument fix.
- **Alternatives considered**: Rewriting `sys.argv[0]` (obscure side effect); accepting the default
  (fails SC-008).

## R8 — Exit-status precedence (spec ambiguity resolved)

The specification is internally ambiguous for one case: **no `--overwrite`, a regular-file member,
and a directory already at that destination path.**

- FR-019 says any file member whose target path holds "a file or directory" → exit **3**.
- FR-023 and the Edge Cases entry "Existing directory where the archive stores a regular file" say
  that collision fails with exit **2**, "even when `--overwrite` is given".

- **Decision**: **Exit 2 wins.** Kind collisions (file member vs. existing directory, directory
  member vs. existing non-directory) are exit 2 regardless of `--overwrite`. Exit 3 is reserved for
  the case `--overwrite` would actually have fixed: a regular-file member whose target is an
  existing regular file.
- **Rationale**: FR-023 and the Edge Cases list are the more specific statements and are explicit
  about being flag-independent. It also gives the flag a coherent meaning: exit 3 means "re-run with
  `--overwrite`", and it would be misleading to return 3 for a conflict that `--overwrite` cannot
  resolve. Validation therefore runs in a fixed order: (a) member-path containment → 2,
  (b) kind collisions → 2, (c) overwrite conflicts → 3.
- **Follow-on decision**: Archive errors are reported before destination errors, so an invalid
  archive plus an unusable destination reports the archive. Both are exit 2, so no observable status
  depends on this; it is fixed only so the diagnostic is deterministic.

## R9 — Duplicate member paths

- **Decision**: Count **distinct destination paths written**, not members processed. Track written
  targets in a set and report `len(written)`.
- **Rationale**: The Edge Cases entry "Duplicate member names" requires that a path stored twice
  contributes **once** to the count while the later entry's contents win. Writing in archive order
  gives "later entry wins" for free; the set gives the count. A naive `count += 1` per regular
  member would over-report.
- Overwrite conflicts are evaluated against the destination's **pre-existing** state only. Because
  all validation happens before any write (FR-020), a path written earlier in the same run can never
  be mistaken for a pre-existing conflict — the ordering requirement is satisfied structurally
  rather than by a special case.

## R10 — Bare `pytest` from the repository root

- **Decision**: Add a minimal `pytest.ini` at the repository root with `pythonpath = src` and
  `testpaths = tests`.
- **Rationale**: The constitution's Technology Constraints require tests to live under `tests/` and
  be "runnable with a bare `pytest` invocation from the repository root", while the spec requires the
  package to live under `src/`. pytest's `pythonpath` ini option (pytest ≥ 7; installed version is
  9.1.1) inserts `src` on `sys.path` for the test session, which bridges the two with three lines of
  configuration and no runtime dependency declaration.
- **Alternatives considered**: `pyproject.toml` with `[tool.pytest.ini_options]` — equivalent, but
  pulls in a packaging file this feature does not otherwise need; a `conftest.py` that mutates
  `sys.path` — more code and more magic for the same effect; requiring `PYTHONPATH=src pytest` —
  violates the "bare `pytest`" constraint.
- Tests that exercise `python -m tarx` as a subprocess must pass `PYTHONPATH=src` in the child
  environment explicitly, since `pythonpath` only affects the pytest process.

## R11 — Direct writes instead of `TarFile.extractall`

- **Decision**: Do **not** use `TarFile.extract` / `extractall`. Create directories with
  `Path.mkdir(parents=True, exist_ok=True)` and write regular files with an explicit `open(..., "wb")`
  plus `copyfileobj`.
- **Rationale**: Three requirements are unreachable through `extractall`:
  1. FR-019/FR-020 — refusing to overwrite, with *nothing written* before the refusal. `extractall`
     overwrites unconditionally.
  2. FR-015/FR-021 — an exact count of regular files written, with duplicates counted once.
  3. FR-016/FR-026 — skipping non-file/non-directory members and rejecting escaping paths with the
     project's own diagnostics and exit statuses.

  `extractall` would also apply file metadata (modes, mtimes), which the spec explicitly leaves out
  of scope. Writing the two member types directly is roughly a dozen lines and keeps every specified
  behavior in code this project controls.
- **Secondary benefit**: it sidesteps the `tarfile` extraction-filter transition entirely. The
  `filter=` parameter arrived in 3.12 and the default changes across versions; a design that never
  calls `extract*` has no version-dependent behavior and no `DeprecationWarning` to manage, which
  keeps the 3.11+ support range honest.
- **Path containment approach**: reject a member when `posixpath.isabs(name)`, when the name has a
  Windows drive or UNC prefix, or when `posixpath.normpath(name)` equals `..` or begins with `../`.
  This is a purely lexical check on the recorded name — it needs no filesystem access, cannot be
  defeated by symlinks already present in the destination, and is evaluated before anything is
  written, as FR-026 requires.
- **Alternatives considered**: `os.path.realpath` containment checks against the resolved
  destination — rejected: it touches the filesystem, its result depends on symlinks inside the
  destination, and it cannot run before the destination exists.
