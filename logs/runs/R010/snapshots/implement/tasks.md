---

description: "Task list for 001-tarx-cli — Tar Archive Listing and Extraction Tool"
---

# Tasks: Tar Archive Listing and Extraction Tool

**Input**: Design documents from `/specs/001-tarx-cli/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md),
[quickstart.md](./quickstart.md)

**Tests**: Test tasks ARE included and are mandatory. Constitution Principle III and
Principle V require every `FR-xxx` and `SR-xxx` to map to at least one automated `pytest`
test, and SC-008 makes that mapping a gate enforced by `tests/test_traceability.py`. Tests
covering a requirement ship in the same phase as the code implementing it (constitution
Development Workflow: "Tests gate merges").

**Organization**: Tasks are grouped by user story so each story can be implemented, tested,
and delivered independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths appear in every task description

## Path Conventions

Single-project layout per plan.md "Structure Decision": the package lives in `src/tarx/`,
tests in `tests/`, both relative to the repository root. `pytest.ini` at the root carries
`pythonpath = src`; there is no install step and no package metadata (MC-002).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the single-project layout and the dev-only test configuration

- [X] T001 Create the package skeleton: directory `src/tarx/` and file `src/tarx/__init__.py` containing only a module docstring naming the package (package marker, no runtime logic, per plan.md Source Code tree)
- [X] T002 [P] Create `pytest.ini` at the repository root with a `[pytest]` section setting `pythonpath = src` and `testpaths = tests`; do NOT create `pyproject.toml`, `setup.py`, or any other package metadata, so the project cannot be mistaken for something requiring installation (MC-002, R-015, constitution Principle I)
- [X] T003 [P] Create `.gitignore` at the repository root ignoring `__pycache__/`, `*.pyc`, and `.pytest_cache/`; confirm `python3 --version` reports 3.11 or newer and `pytest --version` resolves (quickstart.md Prerequisites, MC-001)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The error model, name escaping, archive opening/bounded iteration, the argparse
CLI surface, and the test fixtures — every one of which both user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create `src/tarx/errors.py` defining exactly two classes: `TarxError(Exception)` holding a single-line, already-escaped `message` attribute with class attribute `exit_code = 2`, and `OverwriteConflict(TarxError)` with `exit_code = 3`. No other exception class and no other `exit_code` value may exist in the package — this is what makes FR-015's "no other exit status may be produced" auditable (data-model.md §7, R-009)
- [X] T005 [P] Create `src/tarx/paths.py` with `escape_name(name: str) -> str` as its only public function: escape a character when it is a C0 control (`< 0x20`), `DEL` (`0x7f`), a C1 control (`0x80`–`0x9f`), or has `unicodedata.category` in `{Cc, Cf, Cs, Co, Cn}`; use short forms `\n`, `\r`, `\t`, `\\` where they apply, otherwise `\xXX`, `\uXXXX`, or `\UXXXXXXXX`; escape a literal backslash to `\\`; emit every other character — including all printable non-ASCII — unchanged (SR-007, R-008, contracts/cli.md "Name escaping on output")
- [X] T006 [P] Create `src/tarx/archive.py` with the four resource-bound constants and nothing else yet: `MAX_MEMBERS = 10_000`, `MAX_TOTAL_BYTES = 1 << 30` (1 GiB), `MAX_MEMBER_BYTES = 1 << 30` (1 GiB), `COPY_CHUNK_BYTES = 64 * 1024`. Fixed constants, not configuration (data-model.md §8, SR-005, R-005)
- [X] T007 Add content-based format detection and opening to `src/tarx/archive.py`: `sniff_compression(path)` reads the first two bytes and returns `"gzip"` for `1f 8b` else `"none"`; `open_archive(path)` opens with `tarfile.open(mode="r:gz")` or `mode="r:"` accordingly — never `mode="r:*"`, never the filename extension — and converts `tarfile.TarError`, `EOFError`, `gzip.BadGzipFile`, `zlib.error`, and `OSError` into `TarxError` whose message names the archive path (FR-008, FR-013, R-002, R-010)
- [X] T008 Add `iter_members(tar)` to `src/tarx/archive.py` as a generator that iterates lazily with `for member in tar:` (never `getmembers()`, which would read the whole index before the member cap could fire) and enforces bounds incrementally as each header is read: refuse when the member counter would exceed `MAX_MEMBERS`, when any `member.size` exceeds `MAX_MEMBER_BYTES`, and when the running sum of declared sizes exceeds `MAX_TOTAL_BYTES`, raising `TarxError` that names the bound and the member; also re-wrap the T007 exception set raised mid-iteration, since truncation surfaces during iteration rather than at open (SR-005, FR-013, R-003, R-005, R-010)
- [X] T009 Create `src/tarx/cli.py` with the parser, dispatch, and the single exit-status handler: `argparse.ArgumentParser(prog="python -m tarx")` with `add_subparsers(dest="command", required=True)`, subparser `list ARCHIVE`, subparser `extract ARCHIVE DEST [--overwrite]` (`action="store_true"`); after parsing, reject an empty-string `ARCHIVE` or `DEST` as a usage error (argparse accepts `""`); `main(argv=None) -> int` wraps dispatch in `try/except TarxError` → write `python -m tarx: error: {message}` to stderr and return `err.exit_code`, plus a final `except OSError` → message built from `e.strerror` (never `repr(e)`) and return 2. No bare `except`, and no other code path anywhere may choose an exit status (FR-001, FR-015, FR-016, FR-017, SR-008, SR-010, R-004, R-009)
- [X] T010 [P] Create `src/tarx/__main__.py` containing only `from tarx import cli` and `raise SystemExit(cli.main())`, so `python -m tarx COMMAND ...` works with `src/` on `PYTHONPATH` and no install step (MC-002, R-004)
- [X] T011 [P] Create `tests/helpers.py` building archives in-process with `tarfile`/`TarInfo` into a caller-supplied path — no committed binary fixtures and no elevated privileges. Provide builders for: plain (`w`) and gzip (`w:gz`) archives from a `{name: bytes}` mapping; a valid empty archive (two zero blocks); and hostile members constructed by setting `TarInfo.name`, `.type`, `.size`, `.linkname`, `.mode` directly and calling `tf.addfile()` — absolute (`/abs.txt`), parent traversal (`../esc.txt`), backslash and `\\server\share` UNC forms, `C:` drive prefix, `SYMTYPE`/`LNKTYPE`, `CHRTYPE`/`BLKTYPE`/`FIFOTYPE`, duplicate mapped paths (`a/b` and `./a/b`), control characters in names, and a member whose declared `size` understates its real content length (R-016, SC-005)
- [X] T012 Create `tests/conftest.py` with `tmp_path`-based fixtures layering on `tests/helpers.py`: a fixture yielding a built photos-style gzip archive, one yielding the plain-tar equivalent, one yielding an empty archive, and a `run_cli` fixture that invokes `tarx.cli.main([...])` in-process capturing stdout/stderr and the returned status, plus a `snapshot_tree` helper returning a `{relative path: (kind, bytes-or-None)}` mapping of a destination directory for byte-for-byte before/after comparison (SC-006, R-016)
- [X] T013 Create `tests/test_cli_contract.py` covering the CLI surface built in T009, with each requirement identifier in the test name or docstring: no command; unrecognised command (`delete`); missing required argument (`extract x.tar`); extra argument (`list a.tar b.tar`); unrecognised option (`list --verbose a.tar`); `--overwrite` passed to `list`; empty-string `ARCHIVE`; empty-string `DEST` — each must write to stderr, leave stdout empty, and exit 2. Also assert `--help` writes usage to stdout and exits 0, that no traceback text appears on stderr, and that no error message contains a success line (FR-001, FR-015, FR-016, FR-017, SR-008, SR-010, contracts/cli.md "Usage errors")

**Checkpoint**: Foundation ready — `python -m tarx --help` works, usage errors behave per
contract, archives open and iterate under bounds, and user story implementation can begin

---

## Phase 3: User Story 1 - Extract an archive into a chosen directory (Priority: P1) 🎯 MVP

**Goal**: `extract ARCHIVE DEST` writes every regular-file and directory member beneath
`DEST`, preserving relative paths and byte-identical contents, prints exactly
`extracted N files`, and exits 0 — while refusing, before writing anything, any archive that
is invalid or that would write outside `DEST`, create a link or special file, exceed a
resource bound, map two members to one path, or overwrite an existing regular file.

**Independent Test**: Build an archive of a known directory tree (plain and gzip), extract it
into an empty destination, and compare the result tree against the original — identical
relative paths, byte-identical contents, printed count equal to the number of regular files,
exit 0. Then run every archive in the adversarial corpus and assert nothing is created or
modified outside `DEST` and the destination's contents are byte-for-byte unchanged.

**Scope note**: This story includes the protective default — an existing regular file at a
mapped path is refused via `OverwriteConflict` (exit 3) and nothing is written — because
spec.md states that guarantee belongs to User Story 1. The deliberate `--overwrite` opt-in
and its dedicated test coverage are User Story 3.

### Tests for User Story 1

> **NOTE: Write these tests FIRST and confirm they FAIL before implementing T017–T026**

- [X] T014 [P] [US1] Create `tests/test_extract.py` covering the round-trip and extraction contract, requirement identifiers in test names or docstrings: gzip archive with `photos/a.jpg` + `photos/b.jpg` → both files exist with identical contents, stdout exactly `extracted 2 files\n`, exit 0; plain archive with nested directories and a zero-byte member → all directories created, empty file is zero bytes, count excludes directories; non-existent `DEST` and missing parents created; empty archive → `DEST` created and stdout exactly `extracted 0 files\n`, exit 0; single-file archive → `extracted 1 files` (no pluralisation); gzip archive misnamed `.tar` and plain archive misnamed `.tar.gz` both extract correctly; names with spaces, non-ASCII characters, and a very long path round-trip faithfully; missing archive, arbitrary binary data, truncated archive, and zero-byte file each → stderr names the archive, stdout empty, no files created, exit 2; `DEST` exists as a regular file → exit 2 naming the destination (FR-004, FR-005, FR-006, FR-007, FR-008, FR-013, FR-014, FR-018, FR-019, SC-002)
- [X] T015 [P] [US1] Create `tests/test_security.py` as the adversarial corpus, one or more tests per identifier: member names `../esc.txt`, `a/../../esc.txt`, `/abs.txt`, `\abs.txt`, `\\server\share\x.txt`, `C:\x.txt` → exit 2 naming the member, nothing written, and `esc.txt` provably absent outside `DEST` (SR-001); `SYMTYPE` and `LNKTYPE` members → exit 2 naming the member, never skipped, no link created anywhere (SR-002); `CHRTYPE`, `BLKTYPE`, `FIFOTYPE` members → exit 2 naming the member and its kind (SR-003); a real symlink pre-created inside `DEST` as a path component of a member's destination → exit 2, nothing written, the symlink's target untouched (SR-004); extracted files are mode `0o600` and directories `0o700`, with an archive member carrying mode `0o7777` proving archive bits, setuid, setgid, and sticky are never applied and timestamps/ownership never restored (SR-006); a member named `evil\nextracted 99 files` and one containing `\x1b[2J` → the printed form is one line with a literal backslash escape and no terminal control byte reaches the stream (SR-007); every failure message contains no member contents, no environment variable values, and no traceback text (SR-008); two members mapping to one destination path (`a/b` and `./a/b`) → exit 2 naming both members and the path, nothing written (SR-009). Every case also asserts the destination snapshot is unchanged (SC-005, SC-006)
- [X] T016 [P] [US1] Create `tests/test_limits.py` covering SR-005 for `extract`: an archive with 10,001 members → exit 2 naming the bound, nothing written; a member declaring `size = (1 << 30) + 1` → exit 2; members whose declared sizes sum past `1 << 30` → exit 2; a member whose declared `size` understates its real content so the Pass 2 actual-byte counter fires → exit 2 with a message stating the destination may hold a partial extraction; and an assertion that each refusal is an error, never a truncated best-effort result (SR-005, SC-006)

### Implementation for User Story 1

- [X] T017 [US1] Add `validate_member_name(name)` to `src/tarx/paths.py` applying the name-shape rules lexically, in order, raising `TarxError` naming the escaped member on the first failure: name must be non-empty; `PurePosixPath(name)` must not be absolute (no leading `/`); the name must not begin with a backslash (covers `\…` and the `\\server\share` UNC prefix); it must not match `^[A-Za-z]:`; and no path component may equal `..`. `.` components are dropped rather than refused, because `tar -cf` conventionally emits `./x` (SR-001, R-006, data-model.md §5 rule 1)
- [X] T018 [US1] Add `map_member_path(dest_root, name)` to `src/tarx/paths.py` joining the surviving components onto `dest_root` and confirming, as a belt-and-braces containment check, that the result equals `dest_root` or lies under it using `os.path.normpath` comparison — never `pathlib.Path.resolve()` and never a bare `startswith`, because `resolve()` follows symlinks and would mask the very escape SR-004 guards and `startswith` mis-handles `destfoo` vs `dest` (SR-001, R-006, data-model.md §5 rule 2)
- [X] T019 [US1] Add `assert_no_symlink_components(dest_root, dest_path)` to `src/tarx/paths.py` walking the components of `dest_path` from `dest_root` downward and raising `TarxError` naming the member if `os.path.islink(partial)` is true for any component **at or below** `dest_root`; `dest_root` itself is made absolute once up front and a symlinked `DEST` supplied by the user is honoured, because the boundary is the user's choice — what is refused is a symlink inside it (SR-004, R-007, data-model.md §5 rule 5)
- [X] T020 [P] [US1] Create `src/tarx/extract.py` with the `PlannedEntry` dataclass only: `member_name: str` (raw name, escaped at print time), `kind: Literal["file", "dir"]`, `dest_path: Path`, `declared_size: int` (`0` for directories), `tarinfo: tarfile.TarInfo`, `exists_as_file: bool` (default `False`). These six fields are the whole plan record (data-model.md §5)
- [X] T021 [US1] Add `prepare_destination(dest)` to `src/tarx/extract.py`: make `dest` absolute once; if it exists and `os.path.lstat` shows it is not a directory, raise `TarxError` naming the destination path (exit 2); otherwise `os.makedirs(dest, mode=0o700, exist_ok=True)`, converting `OSError` into `TarxError` naming the destination. This runs **before** Pass 1 so an empty archive still yields a created `DEST` plus `extracted 0 files`, and so destination-state checks have a real directory to stat against; creating an empty directory destroys nothing, so SC-006's guarantee about destination *contents* still holds (FR-007, FR-018, SR-006, R-013, data-model.md §4)
- [X] T022 [US1] Add `build_plan(tar, dest_root, overwrite)` Pass 1 to `src/tarx/extract.py`, consuming `archive.iter_members(tar)` and applying the checks in exactly this order so the first failure wins: (1) name shape via `validate_member_name`; (2) containment via `map_member_path`; (3) kind — classify with `TarInfo.isreg()`/`isfile()` and `isdir()`, and refuse anything else unconditionally (never skip) with a message naming the member and the concrete kind derived from `issym()`, `islnk()`, `ischr()`, `isblk()`, `isfifo()`, falling back to `"an unsupported member type"`; (4) resource bounds, already enforced incrementally by `iter_members`; (5) `assert_no_symlink_components`; (6) uniqueness via a `dict[Path, str]` from mapped destination path to the first claiming member name, refusing a second claim with a message naming **both** members and the path; (7) the destination-state check from T023. Returns `list[PlannedEntry]` — nothing is written by this function (FR-014, SR-001, SR-002, SR-003, SR-004, SR-005, SR-009, R-003, R-012, R-014)
- [X] T023 [US1] Add the destination-state check to `src/tarx/extract.py`'s Pass 1, using `os.path.lstat` exclusively — never `os.stat`, so a symlink is seen as itself: file member + absent → plan a write; file member + regular file + no `overwrite` → raise `OverwriteConflict` naming that path, and only for the **first** such path (exit 3); file member + directory → `TarxError` type conflict naming the member and the path (exit 2); file member + symlink or any other type → `TarxError` (exit 2); dir member + absent → plan a `mkdir`; dir member + directory → reuse silently, never a conflict; dir member + regular file or other → `TarxError` type conflict (exit 2). `OverwriteConflict` has exactly one raise site in the whole package, which is what makes "refused *solely* because of overwrite" structurally true (FR-009, FR-011, FR-012, SR-003, SR-004, R-013, data-model.md §5 rule 7)
- [X] T024 [US1] Add `apply_plan(tar, plan)` Pass 2 to `src/tarx/extract.py`: for a `dir` entry call `os.mkdir(path, 0o700)` (tolerating an already-existing directory per FR-012); for a `file` entry call `os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)` and stream `tar.extractfile(entry.tarinfo)` into it in `COPY_CHUNK_BYTES` (64 KiB) chunks, so no member's contents are ever held whole in memory; count bytes actually read per member and in total against `MAX_MEMBER_BYTES` and `MAX_TOTAL_BYTES` and abort with a `TarxError` that names the member **and states the destination may contain a partial extraction** if either is crossed; map `OSError` with `errno.ELOOP` to a symlink refusal naming the member and other `OSError` to a `TarxError` built from `e.strerror`. Modes are passed to `os.open`/`os.mkdir` as the mode argument so they are set at creation — never a later `chmod` — and because `TarFile.extract`/`extractall` is never called, archive permission, ownership, and timestamp metadata is never consulted and setuid/setgid/sticky can never be set. Return the count of regular files written (FR-005, FR-019, SR-004, SR-005, SR-006, SC-007, R-003, R-007)
- [X] T025 [US1] Add `extract_archive(archive_path, dest, overwrite)` to `src/tarx/extract.py` sequencing the whole operation: `prepare_destination` → `archive.open_archive` (in a `with` block) → `build_plan` → **nothing written before this line** → `apply_plan` → return the files-written count as the `ExtractionResult`. The boundary between the two passes must be visible in this one function, since that is where FR-014 and SC-006 are enforced (FR-004, FR-014, SC-006, data-model.md §6, §9)
- [X] T026 [US1] Wire the `extract` command into `src/tarx/cli.py`: call `extract.extract_archive(args.archive, args.dest, args.overwrite)` and on success write exactly `extracted {n} files\n` to stdout and nothing else, returning 0; a failure must print no success line, with its message already routed through the single T009 handler. Member names in messages pass through `paths.escape_name` (FR-006, FR-016, FR-019, SR-007)

**Checkpoint**: User Story 1 is fully functional and testable on its own — `extract` round-trips
plain and gzip archives, refuses the whole adversarial corpus before writing anything, and
produces only statuses 0, 2, and 3. This is the MVP.

---

## Phase 4: User Story 2 - Inspect an archive's contents without extracting (Priority: P2)

**Goal**: `list ARCHIVE` prints every member name, one per line, in archive order, suitable for
piping, and changes nothing on disk.

**Independent Test**: Build an archive with a known member order, list it, compare stdout
line-for-line against the expected names, and assert via a before/after snapshot that no
filesystem change occurred. Confirm an empty archive prints nothing and exits 0, and a missing
or invalid archive exits 2 with a message on stderr.

### Tests for User Story 2

- [X] T027 [P] [US2] Create `tests/test_list.py`, requirement identifiers in test names or docstrings: gzip archive with `photos/a.jpg` then `photos/b.jpg` → stdout is exactly those two names in that order, one per line, exit 0; an archive whose members include directories, a symlink, a hard link, and a device node → **every** member name printed regardless of type, in archive order, exit 0 (listing is deliberately unfiltered, unlike `extract`); an empty archive → stdout empty, exit 0; a missing archive, arbitrary binary data, and a truncated archive → stderr message naming the archive, stdout empty, exit 2; the same gzip bytes named `.tar` and the same plain bytes named `.tar.gz` → identical listings, proving content-based detection; a snapshot of the working tree before and after every run → unchanged, nothing created, modified, or deleted; a member name containing a real newline and an ESC byte → printed escaped so one member still occupies exactly one output line; and an archive exceeding `MAX_MEMBERS` or a declared size bound → exit 2 (FR-002, FR-003, FR-008, FR-018, SR-005, SR-007)
- [X] T028 [US2] Add to `tests/test_list.py` the assertion that `list` applies the resource bounds but **not** the member-kind restrictions — an archive containing a symlink member lists successfully with exit 0, where `extract` on the same archive exits 2 — so the asymmetry that makes listing the safe way to inspect untrusted input is pinned by a test (FR-003, SR-002, SR-005, R-014, contracts/cli.md `list` section)

### Implementation for User Story 2

- [X] T029 [US2] Implement `run_list(archive_path)` in `src/tarx/cli.py`: `archive.open_archive` in a `with` block, iterate `archive.iter_members(tar)` so the resource bounds apply to `list` too, and `print(paths.escape_name(member.name))` for every member regardless of kind, in archive order, returning 0. The function must perform no filesystem write of any kind — no `mkdir`, no `open` for writing, no `stat`-driven side effect (FR-002, FR-003, FR-018, SR-005, SR-007, R-014)
- [X] T030 [US2] Add broken-pipe handling around the printing loop in `src/tarx/cli.py`: catch `BrokenPipeError`, then `os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())` before returning 2, so the interpreter's shutdown flush cannot emit Python's `Exception ignored in: <_io.TextIOWrapper name='<stdout>'...>` noise and `python -m tarx list big.tar | head -1` terminates without an unhandled crash report. Exit 2 rather than the POSIX-conventional 141, because FR-015 permits no other status (FR-015, FR-016, R-011, spec Edge Cases)
- [X] T031 [US2] Wire the `list` command into `src/tarx/cli.py`'s dispatch so `python -m tarx list ARCHIVE` reaches `run_list`, and add to `tests/test_cli_contract.py` the assertion that a `list` failure prints nothing on stdout (FR-001, FR-016)

**Checkpoint**: User Stories 1 and 2 both work independently — extraction and listing are each
complete against their contract sections.

---

## Phase 5: User Story 3 - Protect existing files, and overwrite deliberately (Priority: P3)

**Goal**: Turn the protective refusal into a deliberate, auditable pair of behaviours — refuse
with status 3 and an untouched destination by default, replace contents on explicit
`--overwrite` — and keep type conflicts and directory reuse distinct from both.

**Independent Test**: Extract an archive into the same destination twice — the second run must
exit 3, name the conflicting path on stderr, print no success line, and leave the destination
byte-for-byte unchanged — then a third time with `--overwrite` and confirm exit 0, the success
line counting every regular file, and replaced contents.

### Tests for User Story 3

- [X] T032 [P] [US3] Create `tests/test_overwrite.py`, requirement identifiers in test names or docstrings: destination already holding a file at a mapped path, no `--overwrite` → stderr names that path, destination snapshot byte-for-byte unchanged, stdout empty with no success line, exit 3; an archive with several conflicting paths → the message names only the **first** such path; the same situation with `--overwrite` → existing contents replaced by archived contents, `extracted N files` counting every regular file written, exit 0; destination already holding some of the archive's directories, no `--overwrite` → those directories reused without error, exit 0; a file member mapping to an existing directory, and a directory member mapping to an existing regular file → type conflict on stderr, destination unchanged, exit 2, asserted **both** with and without `--overwrite`; and `--overwrite` asserted not to suppress any contracts/cli.md case 1–9 or 11 — a traversal member, a symlink member, and an exceeded bound each still exit 2 when `--overwrite` is given (FR-009, FR-010, FR-011, FR-012, SC-006, contracts/cli.md `extract` failure table)

### Implementation for User Story 3

- [X] T033 [US3] Extend the destination-state check in `src/tarx/extract.py` (T023) to honour the `overwrite` flag: a file member mapping to an existing regular file with `overwrite=True` plans a truncating rewrite and sets `PlannedEntry.exists_as_file = True` instead of raising `OverwriteConflict`. The flag changes **only** this one branch — it must not relax the name-shape, containment, kind, bound, symlink, uniqueness, or type-conflict outcomes (FR-010, data-model.md §5 rule 7)
- [X] T034 [US3] Extend `apply_plan` in `src/tarx/extract.py` to select the open flags from the plan entry: `os.O_TRUNC` in place of `os.O_EXCL` when `entry.exists_as_file` is true, keeping `os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW` and mode `0o600` in both cases, so an overwrite still refuses to follow a symlink and still never applies archive permission bits (FR-010, SR-004, SR-006, R-007)
- [X] T035 [US3] Audit and tighten the message wording in `src/tarx/extract.py` for this story's three distinct signals, each naming what was rejected and why in operator-actionable terms: the `OverwriteConflict` message names the first conflicting destination path and mentions that `--overwrite` would permit it; the file-member-onto-directory and directory-member-onto-file messages name the member, the path, and the type conflict; and directory reuse emits no message at all (FR-009, FR-011, FR-012, FR-017, SR-007)
- [X] T036 [US3] Confirm `--overwrite` is threaded end to end in `src/tarx/cli.py` — parsed only on the `extract` subparser (never accepted by `list`), passed as `extract.extract_archive(..., overwrite=args.overwrite)` — and that `OverwriteConflict` reaches the single T009 handler so status 3 has exactly one origin in the package (FR-001, FR-015, SR-010)

**Checkpoint**: All three user stories are independently functional and the full
contracts/cli.md failure table is implemented.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: The gates the constitution and success criteria require across all stories

- [X] T037 [P] Create `tests/test_performance.py` covering SC-007: build a 1,000-member, ~50 MB archive into `tmp_path` and assert both `list` and `extract` complete in under 5 seconds; and extract an archive containing a single member far larger than `COPY_CHUNK_BYTES` while asserting peak memory stays bounded (for example via `tracemalloc` peak, proving no member is held whole in memory) (SC-007, contracts/cli.md invariant 8)
- [X] T038 [P] Create `tests/test_traceability.py` covering SC-008: parse every `FR-xxx` and `SR-xxx` identifier out of `specs/001-tarx-cli/spec.md`, scan the source of every module in `tests/` for each identifier, and fail with the list of unreferenced identifiers if any has no referencing test name or docstring — turning SC-008 from an aspiration into a merge gate (SC-008, constitution Principle III, R-015)
- [X] T039 [P] Add the exit-status exhaustiveness matrix to `tests/test_cli_contract.py` covering SC-004: a parametrised table mapping every specified scenario to its expected status, asserting 0, 2, and 3 are each produced by their specified scenarios **and by no others**, and that no invocation anywhere in the suite ever returns a status outside `{0, 2, 3}` (SC-004, FR-015, contracts/cli.md invariant 1)
- [X] T040 Add destination-snapshot before/after assertions (SC-006) to every failing-path test in `tests/test_extract.py`, `tests/test_security.py`, and `tests/test_overwrite.py` using the `snapshot_tree` helper from `tests/conftest.py`, with the SR-005 actual-bytes abort in `tests/test_limits.py` as the single documented exception that is allowed to differ and must report the partial extraction (SC-006, FR-014)
- [X] T041 [P] Audit every module in `src/tarx/` and confirm each import is standard library and that no runtime module imports `pytest` or anything outside the standard library; confirm the repository ships no `pyproject.toml`/`setup.py` and that `pytest.ini` is the only place test configuration lives (constitution Principle I and the Runtime dependency gate, MC-001, MC-002)
- [X] T042 Run `pytest` from the repository root and confirm the full suite passes, including `tests/test_traceability.py` and `tests/test_performance.py` (constitution: tests gate merges; quickstart.md Definition of done)
- [X] T043 Run the `quickstart.md` smoke run and the manual adversarial check end to end: verify the listing, `extracted 2 files`, `diff -r` identity, `stat -c '%a %n'` showing `700` for directories and `600` for files, status 3 on the second extraction, status 0 with `--overwrite`, the misnamed-`.tar` listing, status 2 with empty stdout for a missing archive, and that `../escaped.txt` never appears outside the destination (quickstart.md, SC-001, SC-005)
- [X] T044 Final review pass against the eight invariants at the end of `specs/001-tarx-cli/contracts/cli.md`, confirming each is upheld by code and pinned by at least one test, and against the plan's Constitution Check — in particular that `src/tarx/cli.py` is the only place an exit status is chosen and `src/tarx/errors.py` the only place one is defined (FR-015, FR-016, SR-008, constitution Review obligation)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational only — independent of US1
- **User Story 3 (Phase 5)**: Depends on Foundational **and** on US1's `extract.py` (T023, T024), which it extends
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start as soon as Phase 2 completes. No dependency on US2 or US3.
- **User Story 2 (P2)**: Can start as soon as Phase 2 completes, in parallel with US1 — it
  touches `src/tarx/cli.py` and `tests/test_list.py` only, and shares `archive.py` and
  `escape_name` as already-finished foundations. Independently testable.
- **User Story 3 (P3)**: Must follow US1, because T033/T034 modify the plan builder and writer
  that T023/T024 create. Independently testable once US1 is in place (the three-run journey in
  its Independent Test needs a working `extract`).

### Within Each User Story

- Tests are written first and must FAIL before the implementation tasks in that phase
- `paths.py` helpers before `extract.py` consumers (T017–T019 before T022)
- Pass 1 before Pass 2 (T022, T023 before T024)
- Both passes before the orchestration (T024 before T025)
- Orchestration before the CLI wiring (T025 before T026)
- Story complete and its checkpoint validated before moving to the next priority

### Parallel Opportunities

- T002 and T003 run in parallel in Setup
- T005, T006, T010, T011 run in parallel in Foundational (distinct files, no interdependency);
  T007 and T008 must follow T006 as they extend the same file, and T012 follows T011
- All three US1 test modules (T014, T015, T016) are written in parallel
- T020 runs in parallel with T017–T019 (different file, no shared state)
- US1 (Phase 3) and US2 (Phase 4) can be developed in parallel by two people after Phase 2
- T037, T038, T039, T041 run in parallel in Polish

---

## Parallel Example: Foundational Phase

```bash
# After T004 (errors.py) lands, launch these four together:
Task: "Create src/tarx/paths.py with escape_name only (SR-007)"
Task: "Create src/tarx/archive.py resource-bound constants (SR-005)"
Task: "Create src/tarx/__main__.py entry point (MC-002)"
Task: "Create tests/helpers.py in-process archive builders incl. hostile members (R-016)"
```

## Parallel Example: User Story 1 Tests

```bash
# Write all three US1 test modules together, before T017-T026:
Task: "Create tests/test_extract.py (FR-004-FR-008, FR-013, FR-014, FR-018, FR-019)"
Task: "Create tests/test_security.py adversarial corpus (SR-001-SR-004, SR-006-SR-009)"
Task: "Create tests/test_limits.py resource bounds (SR-005)"
```

## Parallel Example: Two Stories At Once

```bash
# After the Phase 2 checkpoint, two developers proceed independently:
Developer A: Phase 3 - User Story 1 (extract.py, paths.py validators, cli extract wiring)
Developer B: Phase 4 - User Story 2 (cli.py run_list + broken pipe, tests/test_list.py)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T013) — **blocks everything**
3. Complete Phase 3: User Story 1 (T014–T026)
4. **STOP and VALIDATE**: `pytest tests/test_extract.py tests/test_security.py tests/test_limits.py`,
   then the quickstart extraction smoke run and the manual adversarial check
5. The tool now delivers its primary value: safe extraction of plain and gzip archives

### Incremental Delivery

1. Setup + Foundational → `python -m tarx --help` works, usage errors conform, archives open
   under bounds
2. Add User Story 1 → validate independently → **MVP**: `extract` complete, adversarial corpus
   fully refused
3. Add User Story 2 → validate independently → `list` complete, safe inspection of untrusted
   archives
4. Add User Story 3 → validate independently → deliberate `--overwrite` opt-in and the distinct
   status-3 signal scripts can branch on
5. Polish → SC-004, SC-006, SC-007, SC-008 gates green and the full suite passing

Each story adds value without breaking the previous ones.

### Parallel Team Strategy

With two or three developers:

1. The team completes Setup + Foundational together (T004 first, then the four parallel tasks)
2. Once the Phase 2 checkpoint holds:
   - Developer A: User Story 1 (the largest slice, and US3's prerequisite)
   - Developer B: User Story 2, then the Polish test modules T037–T039
3. Developer A continues into User Story 3 once US1's checkpoint holds
4. The whole team closes out T040–T044 together

---

## Notes

- `[P]` tasks touch different files and have no dependency on an incomplete task
- `[Story]` labels map tasks to spec.md's user stories for traceability
- Every test function name or docstring MUST carry the `FR-xxx`/`SR-xxx` identifiers it covers;
  `tests/test_traceability.py` (T038) makes that a gate rather than a convention (SC-008)
- Tests covering a requirement ship in the same change as the code implementing it
  (constitution: "Tests gate merges")
- Verify each phase's tests FAIL before implementing that phase
- Commit after each task or logical group; the full `pytest` suite must pass before any merge
- Stop at any checkpoint to validate a story independently
- The destination-state table (T023) and the resource bounds (T008, T024) are the two places
  where a subtle change silently breaks a security requirement — re-run
  `tests/test_security.py` and `tests/test_limits.py` after touching either
