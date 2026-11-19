# Phase 0 Research: Tar Archive Listing and Extraction Tool

**Feature**: `001-tarx-cli` | **Date**: 2026-11-12 | **Spec**: [spec.md](./spec.md)

All items below were resolved before design. The Technical Context in [plan.md](./plan.md)
contains no `NEEDS CLARIFICATION` markers.

Every claim marked **Verified** was checked by running the relevant standard-library call
on the target interpreter (CPython 3.13.17 available in this environment; nothing used is
newer than 3.11).

---

## R-001: Language, dependencies, and test runner

- **Decision**: Python 3.11+ (no syntax or API newer than 3.11), standard library only for
  all runtime code, `pytest` as the only development dependency.
- **Rationale**: Mandated by the requester (MC-001) and by constitution Principle I.
  `pytest` is explicitly permitted as dev-only tooling and is never imported by runtime
  modules.
- **Alternatives considered**: `unittest` (std-lib, would remove even the dev dependency)
  — rejected because the requester asked for pytest and the constitution permits it;
  pytest's `tmp_path` fixture and parametrisation materially shorten the adversarial-corpus
  tests. Third-party helpers (`click`, `typer`, `pytest-cov`) — rejected, Principle I and IV.

## R-002: Determining tar vs. gzip from content, not filename (FR-008)

- **Decision**: Read the first two bytes of the archive file. `1f 8b` → open with
  `tarfile.open(fileobj=…, mode="r:gz")`; anything else → `mode="r:"`. Never use the
  filename extension, and never use `mode="r:*"`.
- **Rationale**: Explicit two-byte sniffing is content-based (satisfies FR-008 for `.tar`,
  `.tar.gz`, `.tgz`, and misnamed archives) *and* restricts the accepted formats to exactly
  the two in scope. `mode="r:*"` would silently also accept bzip2, xz, and (3.14+) zstd,
  which the spec puts out of scope; accepting them would be scope creep and would widen the
  decompression-bomb surface.
- **Verified**: a gzip-compressed tar has magic `1f8b`; an uncompressed tar starts with the
  first byte of the member name. `extractfile()` works after fully iterating a
  `mode="r:gz"` archive, because `gzip.GzipFile` is seekable.
- **Alternatives considered**: `tarfile.is_tarfile()` first then fall back — rejected, it
  opens the archive twice and still consults compression auto-detection. Trusting the
  extension — rejected, FR-008 forbids it.

## R-003: Validate-everything-before-writing with bounded memory (FR-014, SC-007)

- **Decision**: Two passes over one open `TarFile`.
  - **Pass 1 (validate)**: iterate the archive lazily with `for member in tf:` (i.e.
    `TarFile.__iter__`/`next()`), enforcing the resource bounds as we go, validating each
    member, and accumulating a small plan entry per member (destination path, kind,
    declared size) plus the original `TarInfo`.
  - **Pass 2 (apply)**: for each planned entry, `tf.extractfile(tarinfo)` and copy to the
    destination in fixed-size chunks (64 KiB).
- **Rationale**: Lazy iteration is what makes the member-count bound enforceable — see
  R-005. Holding at most 10,000 `TarInfo` objects is bounded memory; no member's contents
  are ever held whole in memory, so SC-007's memory requirement holds for arbitrarily large
  members. `extractfile` + chunked copy is the only std-lib way to control permissions and
  symlink-following at write time (R-007).
- **Verified**: iteration is genuinely lazy — after `next()` twice on a 50-member,
  30,720-byte archive only 8,192 bytes (one buffered read) had been consumed from the
  underlying stream. `extractfile()` after a full iteration returns correct contents for
  both plain and gzip archives.
- **Alternatives considered**: `tf.getmembers()` — rejected, it reads the *entire* archive
  index before returning, so a 10-million-member archive is fully parsed before the member
  cap could fire (SR-005 violation). `TarFile.extractall(filter="data")` — rejected on
  three counts: it writes before all members are validated (FR-014), it *skips or rewrites*
  unsafe members where SR-002/SR-003 require a loud refusal, and it restores archive
  permission bits where SR-006 forbids it. Streaming mode `"r|gz"` — rejected, it forbids
  the random access Pass 2 needs and would force buffering member contents.

## R-004: Argument parsing and usage errors (FR-001, SR-010)

- **Decision**: `argparse.ArgumentParser(prog="python -m tarx")` with
  `add_subparsers(dest="command", required=True)` and two subparsers, `list ARCHIVE` and
  `extract ARCHIVE DEST [--overwrite]` (`--overwrite` as `action="store_true"`).
  `main()` returns an int; `__main__.py` does `raise SystemExit(main())`.
- **Rationale**: argparse already does exactly what FR-001 demands — a missing command, an
  unknown command, a missing or extra positional, and an unknown option each print a usage
  message to **stderr** and exit **2**. Reusing that is the smallest design (Principle IV)
  and removes a whole class of hand-rolled parsing bugs. After parsing, `main()` additionally
  rejects an empty `ARCHIVE` or `DEST` string as a usage error (SR-010), since argparse
  accepts `""` for a positional.
- **Alternatives considered**: hand-written parsing — rejected, more code and more ways to
  get exit codes wrong. `getopt` — rejected, no subcommand support, so the dispatch and all
  usage text would still be hand-written.
- **Note on argument safety (SR-010)**: no subprocess is ever spawned and no shell is ever
  invoked by this tool, so there is no shell-interpolation path at all. Argument values are
  passed to `os`/`pathlib` calls as path objects, never interpolated into a command string.

## R-005: Resource bounds (SR-005)

- **Decision**: Three module-level constants in `archive.py` —
  `MAX_MEMBERS = 10_000`, `MAX_TOTAL_BYTES = 1 << 30` (1 GiB),
  `MAX_MEMBER_BYTES = 1 << 30` (1 GiB). Enforcement:
  1. **During Pass 1**, incrementally: refuse as soon as the member counter would exceed
     `MAX_MEMBERS`, as soon as any `member.size` exceeds `MAX_MEMBER_BYTES`, and as soon as
     the running sum of declared sizes exceeds `MAX_TOTAL_BYTES`. All three fire *before any
     write*, so the destination is untouched (SC-006).
  2. **During Pass 2**, on bytes actually read: the chunked copy loop counts real bytes per
     member and in total, and aborts if either bound is crossed. That abort is the one
     documented case where the destination may be left partially written, so its message
     ends with `the destination may contain a partial extraction` (SR-005, SC-006).
  3. Both bounds apply to `list` as well: `list` enforces the member cap and the declared
     per-member/total size caps while iterating, because SR-005 says *both* commands bound
     what one archive can consume.
- **Rationale**: Checking declared sizes catches the ordinary bomb cheaply; counting real
  bytes catches an archive whose headers understate reality. Constants, not options, per the
  spec's Assumptions and Principle IV.
- **Verified**: `tarfile`'s `ExFileObject` already truncates reads at the member's declared
  size (a member declaring 2 bytes yields exactly 2), so under current CPython the Pass 2
  actual-byte counter is defence in depth rather than the primary control. It is implemented
  anyway because SR-005 requires it explicitly and because the guarantee is not documented
  API.
- **Alternatives considered**: bounding only decompressed stream bytes with a counting
  file-object wrapper — rejected as redundant: a tar member's declared size governs how much
  is written, the two zero blocks terminate the archive, and the declared-size sum already
  bounds the total. Making the limits configurable — rejected, Principle IV and the spec's
  stated assumption.

## R-006: Member path containment, purely lexically (SR-001)

- **Decision**: Reject a member name before mapping it if any of the following hold:
  the name is empty; `PurePosixPath(name)` is absolute (leading `/`); the name begins with a
  backslash (covers `\…` and the `\\server\share` UNC prefix); the name matches
  `^[A-Za-z]:` (a Windows drive prefix); or any path component equals `..`. Otherwise the
  destination is `dest_root / <components of name, with "." components dropped>`, and as a
  belt-and-braces check the mapped path must still be `dest_root` or lie under it
  (`os.path.normpath` comparison, no `resolve()`).
- **Rationale**: Validation is **lexical** and happens on the name as recorded in the
  archive header, so it cannot be defeated by filesystem state, and it is deliberately kept
  separate from the symlink question (R-007). Dropping `.` components is needed because
  `tar -cf` conventionally prefixes names with `./`; `..` is never dropped, only refused.
  `resolve()` is *not* used for the containment test because `resolve()` follows symlinks and
  would mask exactly the escape SR-004 is about.
- **Verified**: `tarfile` does **not** sanitise names — reading an archive built with members
  `/abs.txt`, `../esc.txt`, `./dot.txt`, `a//b.txt` returns those names verbatim. So the raw
  hostile forms really do reach our validator and really are testable.
- **Alternatives considered**: `os.path.realpath` + `startswith` — rejected, string prefix
  comparison mis-handles `destfoo` vs `dest`, and realpath follows symlinks.
  `tarfile.data_filter` — rejected, it *rewrites or skips* rather than refusing (SR-002/003)
  and it reports through exceptions we would have to re-map anyway.

## R-007: Not following symlinks that already exist in the destination (SR-004, SR-006)

- **Decision**: Two complementary measures.
  - **At validation**: for each mapped destination path, walk its components from
    `dest_root` downward and refuse if `os.path.islink(partial)` is true for any component
    at or below `dest_root` (`dest_root` itself is resolved once up front, so a symlinked
    `DEST` supplied by the user is honoured — the boundary is the user's choice; what is
    refused is a symlink *inside* it).
  - **At write time**: create files with
    `os.open(path, O_WRONLY | O_CREAT | (O_EXCL or O_TRUNC) | O_NOFOLLOW, 0o600)` and
    directories with `os.mkdir(path, 0o700)`. `O_EXCL` is used without `--overwrite`,
    `O_TRUNC` with it.
- **Rationale**: The validation walk gives the loud, pre-write refusal FR-014 and SR-004
  require. The `O_NOFOLLOW` / `O_EXCL` flags close the time-of-check-to-time-of-use window
  between validation and writing, and the mode argument sets the narrowest permissions **at
  creation** rather than with a later `chmod`, exactly as SR-006 requires. Because we write
  with `os.open`/`os.mkdir` ourselves and never call `TarFile.extract`, archive permission,
  owner, and timestamp metadata is simply never consulted — setuid/setgid/sticky bits cannot
  be set even by accident.
- **Verified**: `os.open(..., O_NOFOLLOW)` on an existing symlink raises `OSError` with
  `errno.ELOOP` (40, "Too many levels of symbolic links"); a file created with mode `0o600`
  has exactly mode `0o600` (umask can only clear further bits, never add).
- **Alternatives considered**: `O_PATH`/`openat` directory-fd walking for a fully
  race-free descent — rejected under Principle IV: it is substantially more code, is not
  portable, and the spec's threat model is a hostile *archive*, not a hostile concurrent
  local process. The `O_NOFOLLOW` + `O_EXCL` pair already prevents the symlink write.

## R-008: Escaping control characters in displayed names (SR-007)

- **Decision**: One helper, `escape_name(name)`, applied to **every** member name written to
  stdout or stderr. A character is escaped when it is a C0 control (`< 0x20`), `DEL`
  (`0x7f`), a C1 control (`0x80`–`0x9f`), or has Unicode category `Cc`, `Cf`, `Cs`, `Co`, or
  `Cn` (via `unicodedata.category`). Escapes use Python's familiar short forms where they
  exist (`\n`, `\r`, `\t`, `\\`) and `\xXX` / `\uXXXX` / `\UXXXXXXXX` otherwise. A literal
  backslash is escaped to `\\` so the rendering is unambiguous. Every other character —
  including all printable non-ASCII — is emitted unchanged.
- **Rationale**: Guarantees one member per output line and makes terminal escape-sequence
  injection impossible, while keeping the Edge Case promise that names with spaces and
  non-ASCII characters are reproduced faithfully in listings.
- **Alternatives considered**: `name.encode("unicode_escape").decode("ascii")` — rejected,
  it escapes *all* non-ASCII, breaking the non-ASCII faithfulness requirement.
  `repr(name)` — rejected, it adds surrounding quotes and escapes quotes, changing names
  that contain no control characters at all (SR-007's last sentence).
- **Consequence to document**: an escaped name is a *display* form. The file on disk still
  carries the real name, so a listing is not always a verbatim shell-pasteable path. That is
  the intended trade: SR-007 ranks terminal safety above round-tripping.

## R-009: Mapping failures to exit statuses (FR-015, SR-008)

- **Decision**: One exception hierarchy in `errors.py`: `TarxError(Exception)` carrying a
  one-line, already-escaped `message` and a class attribute `exit_code = 2`; a single
  subclass `OverwriteConflict(TarxError)` with `exit_code = 3`. `cli.main()` wraps the whole
  operation in `try/except TarxError` → print `python -m tarx: error: {message}` to stderr,
  return `err.exit_code`. A final `except OSError` maps unforeseen filesystem errors to a
  message built from `e.strerror` and exit 2, so no traceback can escape.
- **Rationale**: Exactly one place decides exit codes, which is what makes FR-015's "no
  other exit status may be produced" and SC-004 auditable. Status 3 is reachable from exactly
  one raise site, so "refused *solely* because of overwrite" is structurally true rather than
  a convention. Catching `OSError` (not bare `except`) and reporting `e.strerror` rather than
  `repr(e)` satisfies SR-008: no stack trace, no member contents, no environment values.
  Principle II is satisfied because nothing is swallowed — every caught error becomes a
  message plus a non-zero status.
- **Alternatives considered**: returning `(code, message)` tuples through the call stack —
  rejected, every intermediate function would have to propagate them, and a forgotten check
  becomes a silent success. One exception class per failure mode — rejected, the exit code is
  the only behavioural difference, so two classes suffice (Principle IV).

## R-010: Error sources that must be caught when reading an archive (FR-013)

- **Decision**: Treat `tarfile.TarError` (notably `ReadError`), `EOFError`, `gzip.BadGzipFile`,
  `zlib.error`, and `OSError` as "archive is missing, unreadable, or invalid" → exit 2, at
  **both** `tarfile.open` time and during iteration/reading, since a truncation only
  surfaces partway through.
- **Verified**: non-tar data → `tarfile.ReadError: invalid header`; a truncated archive →
  `ReadError: unexpected end of data` raised *during iteration*, not at open; a zero-byte
  file → `ReadError: empty file`; `\x1f\x8b` followed by garbage → **`EOFError`**, which is
  *not* an `OSError` and would otherwise escape as a traceback. A valid empty archive (two
  zero blocks) opens cleanly and yields `[]`, which is what makes FR-018 a plain success
  rather than a special case.
- **Alternatives considered**: catching only `tarfile.TarError` — rejected, the verified
  `EOFError` from a corrupt gzip stream would crash with a traceback and violate SR-008.

## R-011: Broken pipe on stdout (Edge Case, FR-016)

- **Decision**: `list` writes with `print()` inside a `try/except BrokenPipeError`. On
  `BrokenPipeError`, redirect fd 1 to `os.devnull` with `os.dup2` before returning, so the
  interpreter's shutdown flush cannot emit Python's "Exception ignored in: …sys.stdout"
  noise, and return 2.
- **Rationale**: This is the documented CPython recipe for the `yourtool | head -1` case. It
  meets the Edge Case ("terminates without an unhandled crash report") while keeping exit
  statuses to the three FR-015 allows — a broken pipe is a failure, so it is 2.
- **Consequence to document**: a POSIX tool killed by `SIGPIPE` would exit 141; this tool
  deliberately reports 2 instead because FR-015 forbids any other status. Worth noting for
  anyone scripting around it.
- **Alternatives considered**: restoring the default `SIGPIPE` disposition with
  `signal.signal(SIGPIPE, SIG_DFL)` — rejected, it produces exit status 141 and violates
  FR-015.

## R-012: Detecting duplicate destination paths (SR-009)

- **Decision**: During Pass 1 keep a `dict[Path, str]` from mapped destination path to the
  first member name that claimed it. A second claim on the same path is refused, naming both
  members. The comparison uses the mapped path, so `a/b`, `./a/b`, and `a//b` are correctly
  recognised as the same destination.
- **Rationale**: Comparing *mapped* paths rather than raw names is what actually prevents the
  FR-009 bypass. A directory member and a file member claiming one path is also a conflict
  and is caught by the same check (and is in any case a type conflict under FR-011).
- **Alternatives considered**: comparing raw `member.name` strings — rejected, `./a/b` and
  `a/b` would slip through as distinct names mapping to one file.

## R-013: Pre-existing destination state checks (FR-007, FR-009, FR-011, FR-012)

- **Decision**: All destination-state checks run in Pass 1, using `os.path.lstat` (never
  `stat`, so a symlink is seen as a symlink rather than its target):
  | Member kind | Existing path state | Outcome |
  |---|---|---|
  | file | absent | write it |
  | file | regular file, no `--overwrite` | **exit 3**, naming the path (first conflict only) |
  | file | regular file, with `--overwrite` | truncate and rewrite |
  | file | directory | **exit 2**, type conflict |
  | file | symlink / other | **exit 2** (SR-004 / SR-003) |
  | dir | absent | create it |
  | dir | directory | reuse silently (FR-012) |
  | dir | regular file or other | **exit 2**, type conflict |
  `DEST` itself: if it exists and is not a directory → exit 2; otherwise
  `os.makedirs(dest, mode=0o700, exist_ok=True)` creates it and any missing parents (FR-007).
  `DEST` is created *before* Pass 1 so that FR-018's `extracted 0 files` still creates it, and
  so that destination-state checks have a real directory to stat against.
- **Rationale**: Doing every check before any write is FR-014. Reporting only the *first*
  overwrite conflict is FR-009's exact wording. Creating `DEST` up front is the one write that
  precedes validation; it is not a destructive act (it creates an empty directory, and a
  pre-existing `DEST` is left exactly as it was), so SC-006's "byte-for-byte unchanged"
  guarantee about *destination contents* still holds.
- **Alternatives considered**: creating `DEST` only after validation succeeds — rejected,
  FR-007 and FR-018 require `DEST` to exist after a successful empty-archive extraction, and
  deferring creation would mean destination-state checks run against a non-existent directory.

## R-014: Non-file, non-directory members (SR-002, SR-003)

- **Decision**: In Pass 1, classify with `TarInfo.isreg()` / `isfile()` and `isdir()`.
  Anything else is refused with a message naming the member and the kind it is, derived from
  `issym()`, `islnk()`, `ischr()`, `isblk()`, `isfifo()`, falling back to
  `"an unsupported member type"`. Refusal is unconditional — never a skip.
- **Rationale**: Principle II (Fail Loudly) and the spec's explicit Assumption that silent
  skipping is forbidden. Naming the concrete kind makes the message actionable (FR-017).
- **Note**: `list` does **not** apply this classification — it prints every member of every
  type (FR-003), which is the whole point of having a safe way to inspect an untrusted
  archive.

## R-015: Test layout and requirement traceability (Principle III, SC-008)

- **Decision**: `pytest.ini` at the repo root with `pythonpath = src`, so `import tarx`
  works with no install step (MC-002) and the setting is unambiguously dev-only tooling.
  Tests live in `tests/`, grouped by concern, and **every** test function name or docstring
  carries the requirement identifiers it covers (e.g.
  `def test_extract_refuses_parent_traversal(): """SR-001: …"""`). A single
  `test_traceability.py` test greps the test suite's own source for each `FR-xxx`/`SR-xxx`
  identifier appearing in `spec.md` and fails if any is unreferenced — turning SC-008 from an
  aspiration into a gate.
- **Rationale**: Principle III demands the spec-to-test mapping be *auditable, not assumed*;
  a mechanical check is the only way that survives later edits. `pytest.ini` over
  `pyproject.toml` because the project ships no package metadata and must not look installable
  (MC-002, Principle I).
- **Alternatives considered**: a hand-maintained traceability table in Markdown — rejected,
  it drifts and nothing fails when it does.

## R-016: Archive fixtures for tests, including hostile ones

- **Decision**: Build every fixture archive in-process with `tarfile` and `TarInfo` objects
  written to a `tmp_path` file; no binary fixtures are committed. Hostile members (absolute
  names, `..`, symlinks, device nodes, duplicates, understated sizes) are constructed by
  setting `TarInfo.name`, `.type`, `.size`, `.linkname`, `.mode` directly and using
  `tf.addfile()` — this needs no special privileges, because the tool under test rejects such
  members from the *header*, never needing a real device node on disk.
- **Rationale**: Keeps the adversarial corpus (SC-005) readable, reviewable, and diffable, and
  lets CI run unprivileged. Committed binary blobs would be unauditable in review.
- **Verified**: a plain `TarInfo` with a hostile `name` round-trips through `tarfile` intact
  (see R-006), so the fixtures genuinely exercise the validator.
