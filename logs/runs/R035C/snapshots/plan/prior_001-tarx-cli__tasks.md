---

description: "Task list for Tar Archive Listing and Extraction CLI"
---

# Tasks: Tar Archive Listing and Extraction CLI

**Input**: Design documents from `/specs/001-tarx-cli/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: Test tasks ARE included and are mandatory for this feature. FR-021 makes
requirement-to-test traceability itself a functional requirement, and Constitution Principle III
("Every Requirement Is Testable") plus Quality Gate 3 ("code and its covering tests land together")
make tests a precondition for calling any task done. Within each story phase, tests are written
first and must fail before the implementation tasks in that phase are started.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and
delivered independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths are given in every task

## Path Conventions

Single project, `src/` layout (plan.md → Project Structure). All paths below are relative to the
repository root `/root/sdd-study/runs/R035/`:

- Runtime code: `src/tarx/`
- Tests: `tests/`
- Project metadata: `pyproject.toml`

Diagnostic template IDs (`D1`…`D12`) refer to the table in
[contracts/cli.md](./contracts/cli.md#diagnostic-templates). Message wording there is **exact** and
must be reproduced verbatim.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository scaffolding and the test runner, so that `import tarx` and `python -m pytest` work before any logic exists

- [X] T001 Create the directory skeleton `src/tarx/` and `tests/` at the repository root, exactly as laid out in plan.md → Source Code; do not create `models/`, `services/`, `cli/`, or `lib/` subdirectories (plan.md Structure Decision explicitly drops them under Principle IV)
- [X] T002 Create `pyproject.toml` at the repository root with: `[project]` `name = "tarx"`, `requires-python = ">=3.11"`, an **empty** `dependencies = []` (Constitution Principle I — runtime requirements MUST remain empty), a separate `[dependency-groups]` entry `test = ["pytest"]` (test tooling declared separately so the distinction stays visible), and `[tool.pytest.ini_options]` with `pythonpath = ["src"]` and `testpaths = ["tests"]` so tests import `tarx` with no editable install
- [X] T003 [P] Create `src/tarx/__init__.py` as a bare package marker — a module docstring only, nothing executable (plan.md: "package marker; nothing executable")
- [X] T004 Confirm the toolchain from the repository root: `python3 --version` reports 3.11 or newer, and `python -m pytest` collects from `tests/` without an import error (expect "no tests ran"); record the interpreter version observed, since plan.md keeps the 3.11 floor by review discipline on a 3.13 interpreter

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The archive-reading, error-signalling, and argument-parsing substrate that every user story needs. `open_archive` lives here rather than in a story phase because `list` (US1) and `extract` (US2) both depend on it and neither can run without it.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Create `src/tarx/core.py` with the exit-status constants from data-model.md → Outcome: `EXIT_OK = 0`, `EXIT_INPUT = 2`, `EXIT_REFUSED_OVERWRITE = 3`. These three values are the whole status vocabulary (contracts/cli.md → Exit statuses); no other status may ever be returned
- [X] T006 Add `class TarxError(Exception)` to `src/tarx/core.py` carrying `message: str` (the full, already-formatted stderr line including the `tarx: ` prefix) and `exit_class: int` (constrained to `EXIT_INPUT` or `EXIT_REFUSED_OVERWRITE`). This is how `core` reports a fatal condition to `cli` without printing or calling `sys.exit` itself — Principle II forbids swallowing, and keeping the raise/print split is what lets `tests/test_validation.py` assert on `core` in-process
- [X] T007 Add member-interpretation helpers to `src/tarx/core.py` per data-model.md → Member: `KIND_FILE = "file"`, `KIND_DIR = "dir"`, `KIND_OTHER = "other"`; `member_kind(info)` returning `KIND_FILE` if `info.isreg()`, `KIND_DIR` if `info.isdir()`, else `KIND_OTHER`; `display_name(name)` stripping **trailing** `/` characters and falling back to the unchanged `name` if stripping would leave an empty string (research.md §9); and a `KIND_LABELS` mapping producing exactly the labels `symbolic link`, `hard link`, `character device`, `block device`, `FIFO`, with `unsupported member type` as the fallback (contracts/cli.md → Skipped members)
- [X] T008 Add `open_archive(path)` to `src/tarx/core.py` as a context manager wrapping `tarfile.open(path, "r:*")` (research.md §1 — content-based format and compression detection, FR-004). Catch `OSError` and raise `TarxError` with template D1 `tarx: cannot open archive '{path}': {reason}`; catch `tarfile.TarError` and raise `TarxError` with template D2 `tarx: '{path}' is not a readable tar archive: {reason}`; both carry `exit_class = EXIT_INPUT`. `{path}` echoes the path exactly as the user typed it (data-model.md → Invocation: never normalised). No bare `except` and no other exception type caught (Principle II)
- [X] T009 Create `src/tarx/cli.py` with `build_parser()` returning an `argparse.ArgumentParser(prog="tarx")` with required subcommands `list` (positional `ARCHIVE`) and `extract` (positionals `ARCHIVE`, `DEST`, plus the `--overwrite` store-true flag defaulting to `False`), per contracts/cli.md → Invocation. Help strings must name both commands, both operands, and `--overwrite` so SC-009 is satisfied from the tool's own output. No `type=` converter may touch the filesystem — FR-017 requires an invalid invocation to read and write nothing (research.md §7)
- [X] T010 Add `main(argv=None)` to `src/tarx/cli.py`: reconfigure `sys.stdout` and `sys.stderr` with `errors="surrogateescape"` before any write (research.md §8, so non-UTF-8 member names round-trip to the exact archive bytes instead of raising), parse `argv`, dispatch on the subcommand, catch `core.TarxError` by writing `err.message` to stderr and **returning** `err.exit_class`, and return an `int` status in every path. `main` must never call `sys.exit` itself, so in-process tests can assert the returned status
- [X] T011 Create `src/tarx/__main__.py` containing only the `python -m tarx` entry point: `sys.exit(cli.main())` under an `if __name__ == "__main__":` guard (plan.md). Depends on T010
- [X] T012 [P] Create `tests/conftest.py` with the fixtures every test phase uses: a `make_archive` factory that builds an archive in `tmp_path` from a list of `(name, kind, contents)` entries using `tarfile` — supporting regular files (including zero-length), directory members, duplicate names, non-regular members (symlink, hard link, FIFO), non-ASCII and surrogate-escaped names, and arbitrary member order — with a `compress` switch for plain vs gzip and a `filename` switch so a gzip archive can be given a `.tar` name (FR-004); an `empty_archive` fixture; a `run_cli(*argv)` helper calling `tarx.cli.main(list(argv))` and returning `(status, stdout, stderr)` via `capsys`; and a `run_module(*argv)` helper invoking `[sys.executable, "-m", "tarx", *argv]` through `subprocess.run` with `PYTHONPATH=src`. No binary fixture archives are committed (research.md §10)

**Checkpoint**: `python -m tarx --help` prints usage and exits 0; `core` can open an archive and signal failures. User story work can now begin.

---

## Phase 3: User Story 1 - Inspect what is inside an archive (Priority: P1) 🎯 MVP

**Goal**: `list ARCHIVE` prints every member's archive-relative path, one per line, in archive order, for both plain and gzip-compressed archives, writing nothing to disk.

**Independent Test**: Build a plain archive and a gzip-compressed archive with known members in a known order, run `list` on each, and confirm stdout is exactly those names — one per line, in that order, directory members without a trailing slash — with exit status 0 and empty stderr.

### Tests for User Story 1 ⚠️

> **Write these first and confirm they FAIL before starting T016.** The three tasks below all edit `tests/test_list.py`, so they are sequential, not parallel.

- [X] T013 [US1] In `tests/test_list.py`, add the happy-path listing tests: FR-002 (every member printed, one name per line, in the order the archive stores them — build the archive with members deliberately out of alphabetical order so an accidental sort fails the test), FR-016 (exit status 0, stdout carries the results only, stderr empty), and FR-018 (an archive with no members produces completely empty stdout and exit 0)
- [X] T014 [US1] In `tests/test_list.py`, add the member-form tests: FR-003 (directory members and non-regular members such as a symlink are all listed, unfiltered and unreordered; a duplicated member name appears once per occurrence) and FR-024 (a directory member recorded as `photos/` prints as `photos` with no trailing slash; a member recorded as `./` prints as `.`; a pathological name consisting only of slashes is printed unchanged rather than as a blank line — research.md §9). Also assert a non-ASCII member name is printed with the bytes recorded in the archive (research.md §8)
- [X] T015 [US1] In `tests/test_list.py`, add the format-detection and invocation tests: FR-004 (a gzip-compressed archive given a `.tar` filename and a plain archive given a `.tar.gz` filename both list identically to their correctly-named equivalents, proving detection is by content not extension), plus one `run_module` subprocess test asserting that `python -m tarx list ARCHIVE` with `PYTHONPATH=src` produces the same stdout and a real process exit status of 0 (covers `src/tarx/__main__.py`, which in-process tests cannot reach)

### Implementation for User Story 1

- [X] T016 [US1] Add `iter_member_names(archive_path)` to `src/tarx/core.py`: open via `open_archive`, iterate `tf` member headers in archive order, and yield `display_name(info.name)` for every member regardless of kind. Member **bodies** must never be read — this is what meets the 10,000-members-under-5-seconds half of SC-008 (plan.md Performance Goals)
- [X] T017 [US1] Add the `list` command handler to `src/tarx/cli.py`: call `core.iter_member_names`, print each name to stdout on its own line with no header, footer, count, or separator (contracts/cli.md → `list ARCHIVE`), and return `core.EXIT_OK`. Failures propagate as `TarxError` and are handled by the `main` handler from T010 — no `try` block here

**Checkpoint**: User Story 1 is fully functional and independently testable. `python -m tarx list` works on both archive formats and is a usable archive inspector on its own.

---

## Phase 4: User Story 2 - Extract an archive into a destination directory (Priority: P2)

**Goal**: `extract ARCHIVE DEST` reproduces the archive's regular files and directories under `DEST` with paths and bytes intact, reports `extracted N files`, and refuses — writing nothing at all — when a member would replace an existing regular file.

**Independent Test**: Extract a known archive into a fresh empty destination, compare the resulting tree against the known contents file by file, and confirm the summary line and exit status 0. Then drop a conflicting file into the destination, re-run without `--overwrite`, and confirm exit 3, the conflicting path named on stderr, and that not one file was written.

**Note on scope**: this phase builds the two-phase validate-then-write skeleton (plan.md Summary, FR-020), including path-safety rejection (D5) because the write phase cannot be allowed to run without it. Destination-type checks, type mismatches, and the mid-write handler are deliberately deferred to US4.

### Tests for User Story 2 ⚠️

> **Write these first and confirm they FAIL before starting T022.** T018–T019 share `tests/test_extract.py` and are sequential; T020 and T021 are in different files and can run in parallel with each other.

- [X] T018 [US2] In `tests/test_extract.py`, add the core extraction tests: FR-005 (nested archive-relative paths reproduced beneath `DEST`), FR-006 (every extracted file's bytes compared byte-for-byte against the source, including a zero-length member created as an empty file), FR-007 (a missing `DEST` with missing **parent** directories is created; an existing `DEST` directory is reused), and FR-008 (stdout is exactly the one line `extracted N files` and nothing else, asserted at `N` = 0, 1, and 2 — the literal `extracted 1 files` with the plural `files` at a count of one, per clarification Q5)
- [X] T019 [US2] In `tests/test_extract.py`, add the surrounding-behaviour tests: FR-004 (extraction from a gzip archive and from a misnamed archive matches the plain case), FR-011 (a directory that already exists at a directory member's path is not a conflict and the run still exits 0), FR-015 (symlink, hard-link and FIFO members are not created, each is named on stderr as `tarx: skipping non-regular member '{name}' ({label})` with the exact labels from T007, they are excluded from `N`, and their presence alone keeps the status at 0), FR-016/FR-018 (empty archive → stdout `extracted 0 files`, exit 0), an assertion that a pre-existing unrelated file in `DEST` that the archive does not contain is left untouched (spec US2 scenario 4), and one `run_module` subprocess test of `python -m tarx extract` asserting a real exit status of 0
- [X] T020 [P] [US2] Create `tests/test_overwrite.py` with the refusal tests: FR-009 (without `--overwrite`, an archive member that would replace an existing regular file causes **zero** files to be written — assert the whole destination tree is byte-identical to a snapshot taken before the run, including the non-conflicting members — with every conflicting destination path named on stderr using exact template D10 `tarx: refusing to overwrite existing file '{path}' (re-run with --overwrite)`, one per line, stdout completely empty, and exit status 3) and FR-020 (place the only conflict at the **last** member of the archive and assert the destination is still unchanged, proving validation completes before the first write rather than aborting mid-stream)
- [X] T021 [P] [US2] Create `tests/test_validation.py` with the FR-014 path-safety unit tests, calling `core`'s check directly rather than through the CLI: reject an absolute member name (`/etc/passwd`), reject a name normalising to `..`, reject one starting with `../`, reject one that escapes via interior segments (`a/../../b`), reject `.` or an empty normalised path **for a regular-file member**, accept ordinary relative names including ones with harmless interior `.`/`..` that stay inside (`a/./b`, `a/b/../c`), and assert the check applies to `KIND_OTHER` members too — FR-014 names "any member" with no type qualifier, so a hostile symlink entry refuses the whole archive (research.md §3)

### Implementation for User Story 2

- [X] T022 [US2] Add the problem-accumulation types to `src/tarx/core.py` per data-model.md → Problem: a `Problem` data holder with `exit_class: int` (`EXIT_INPUT` or `EXIT_REFUSED_OVERWRITE`) and `message: str` (the full stderr line), plus `resolve_exit_status(problems)` implementing the FR-025 precedence rule — return `EXIT_INPUT` if any problem has `exit_class == EXIT_INPUT`, else `EXIT_REFUSED_OVERWRITE` if the list is non-empty, else `EXIT_OK`. Validation accumulates problems in a list and never raises on the first one
- [X] T023 [US2] Add `MemberTarget` and `check_member_path(name, kind, dest)` to `src/tarx/core.py` per data-model.md → MemberTarget: a holder with `member`, `relative` (`os.path.normpath(name)`), and `target` (`os.path.join(dest, relative)`); the check applies research.md §3's three rules **lexically**, with no `realpath`/`resolve` call so the verdict is a property of the archive and reproducible in tests, returning either a `MemberTarget` or a class-2 `Problem` using exact template D5 `tarx: unsafe member path '{name}': resolves outside destination '{dest}'`. A member rejected here is excluded from all further checks, so it contributes at most one problem line
- [X] T024 [US2] Add `build_plan(tf, dest, overwrite)` to `src/tarx/core.py` returning `(WritePlan, list[Problem])` and performing **no filesystem writes whatsoever** (FR-020). Build the `WritePlan` of data-model.md → WritePlan: `directories` as target paths for `KIND_DIR` members in archive order; `files` as a `dict` keyed by target path holding the member, insertion-ordered with **last member wins** so a duplicated name is written exactly once and `N = len(files)` matches what ends up on disk (research.md §6, SC-003); `skipped` as `(name, kind_label)` pairs for `KIND_OTHER` members in archive order. Run every member through T023's check first, then — for a `KIND_FILE` member whose target is an existing regular file and `overwrite` is `False` — append a class-3 `Problem` with template D10. Members are walked via header metadata only; no body is read in this phase
- [X] T025 [US2] Add `write_plan(tf, dest, plan)` to `src/tarx/core.py` — the write phase, entered only when the problem list is empty: `os.makedirs(dest, exist_ok=True)` (FR-007, creating missing parents), then `os.makedirs(path, exist_ok=True)` for each planned directory and for each planned file's parent, then for each planned file stream `tf.extractfile(member)` into the target opened `"wb"` using `shutil.copyfileobj`, which bounds memory by one fixed-size buffer regardless of member size (SC-008, research.md §2). Return the number of files written. Do **not** call `TarFile.extractall`/`extract` and do **not** restore permissions, ownership, or timestamps — metadata preservation is out of scope (plan.md Complexity Tracking, spec Assumptions)
- [X] T026 [US2] Add the `extract(archive_path, dest, overwrite)` orchestrator to `src/tarx/core.py`: open via `open_archive`, call `build_plan`, and if the problem list is non-empty return the problems and the resolved status **without entering the write phase**; otherwise call `write_plan` and return the written count plus the plan's skip list. The hard boundary between the two phases is FR-020 and must not be softened by any early write
- [X] T027 [US2] Add the `extract` command handler to `src/tarx/cli.py`: on problems, write every problem's `message` to stderr one per line and return `resolve_exit_status(...)` with **nothing** written to stdout (SC-006); on success, write each skip notice to stderr in archive order and then the single exact line `extracted N files` to stdout, and return `core.EXIT_OK`. The summary line is written only on success, so a failing run never looks successful (Principle II)

**Checkpoint**: User Stories 1 AND 2 both work independently. Extraction is safe by default — it refuses rather than replacing, and a refused run leaves the destination untouched.

---

## Phase 5: User Story 3 - Deliberately replace existing files (Priority: P3)

**Goal**: `--overwrite` lets regular-file members replace existing regular files at their destination paths, with replaced files counted in `N`, while still never removing a directory and never resolving a type mismatch.

**Independent Test**: Extract an archive into a destination twice in a row, the second time with `--overwrite`, and confirm the second run exits 0, reports the same file count as the first, and leaves every file matching the archive's bytes.

### Tests for User Story 3 ⚠️

> **Write T028 first and confirm it FAILS before starting T029.**

- [X] T028 [US3] In `tests/test_overwrite.py`, add the opt-in replacement tests: FR-010 (a second extraction into a populated destination with `--overwrite` exits 0, reports the **full** file count including replaced files, and leaves contents matching the archive; an existing file whose contents differ from the archive's version matches the archive's bytes exactly afterwards), FR-011 (an existing directory at a directory member's path is still not a conflict with the flag set), spec US3 scenario 3 (with no conflicting files present, `--overwrite` behaves identically to omitting it — same stdout, same status, same tree), and an assertion that a destination file absent from the archive is **not** deleted or modified even with the flag, since extraction merges into the destination rather than replacing it wholesale (contracts/cli.md → Guarantees)
- [X] T029 [US3] In `src/tarx/core.py`, extend `build_plan` from T024 so that when `overwrite` is `True` an existing regular file at a `KIND_FILE` member's target produces **no** `Problem` and the member is planned for writing instead. Keep the scope exactly as contracts/cli.md states: the flag consents to replacing a regular file with a regular file only — it must not remove a directory, must not suppress any class-2 problem, and must not delete destination files the archive does not contain
- [X] T030 [US3] In `src/tarx/core.py`, confirm `write_plan`'s `"wb"` open truncates and replaces an existing regular file in place, and that the returned count is `len(plan.files)` so replaced files are counted in `N` alongside newly created ones (FR-010, SC-003). Add no separate replace path — one write path serves both cases (Principle IV)
- [X] T031 [US3] In `src/tarx/cli.py`, thread `args.overwrite` from the parser through the `extract` handler into `core.extract`, and confirm the flag defaults to `False` when absent so US2's refusal behaviour is unchanged (FR-009)

**Checkpoint**: All three happy-path stories are independently functional. Repeat-extraction and refresh workflows now work.

---

## Phase 6: User Story 4 - Get a clear, actionable failure instead of a surprise (Priority: P4)

**Goal**: Every failure mode the tool can detect yields a specific stderr diagnostic, a documented non-zero status, empty stdout, and no partial tree at the destination — with all problems in one run reported together and status 2 outranking status 3.

**Independent Test**: Drive each failure mode in turn — missing archive, non-archive file, truncated archive, unknown command, missing operand, destination that is not a directory, member path escaping the destination, existing entry of the wrong type, mid-write filesystem failure — and assert on the exit status, a non-empty stderr message, empty stdout, and the absence of any new file at the destination.

### Tests for User Story 4 ⚠️

> **Write these first and confirm they FAIL before starting T039.** T032–T037 all edit `tests/test_errors.py` and are sequential; T038 is in a different file and can run in parallel with them.

- [X] T032 [US4] Create `tests/test_errors.py` with the archive-level failures: FR-012 (a non-existent archive path makes **either** command write a message naming that path to stderr, leave stdout empty, and exit 2 — assert the message echoes the path exactly as passed, not a normalised form) and FR-013 (a file that exists but is not a tar archive, and a deliberately truncated archive, both exit 2 with a message on stderr; for `extract`, assert the destination is left without any partially extracted tree)
- [X] T033 [US4] In `tests/test_errors.py`, add the invocation-level failures: FR-001 (an unknown command name is rejected with a usage diagnostic) and FR-017 (a missing required operand and an unrecognised option each produce a usage message on stderr and a non-zero status, and nothing is read or written — assert a sentinel archive file's mtime and contents are unchanged and that no destination directory was created). Add `run_module` subprocess assertions that the real process status for these cases is 2 (argparse's own code, research.md §7, template D12), and assert `--help` and `extract --help` print usage naming both commands, `ARCHIVE`, `DEST`, and `--overwrite` to **stdout** with status 0 (SC-009)
- [X] T034 [US4] In `tests/test_errors.py`, add the destination-level failures: FR-019 (`DEST` is an existing regular file → exact template D3 `tarx: destination '{path}' exists but is not a directory`, exit 2, and the existing file's bytes unchanged) and the ancestor case (a regular file occupies a parent of the requested `DEST` → exact template D4 `tarx: cannot create destination '{dest}': '{path}' is not a directory`, exit 2, nothing created)
- [X] T035 [US4] In `tests/test_errors.py`, add the FR-023 type-mismatch failures, each asserted **both with and without** `--overwrite` since the flag must not change the outcome, each with zero files written and exit 2: an existing directory where a file member goes (D6), an existing non-directory where a directory member goes (D7), an existing regular file blocking a path needed as a member's parent directory (D8), and an archive that itself stores a regular file at a path another member needs as a parent directory (D9). Assert each exact template from contracts/cli.md and assert that stdout is empty in every case
- [X] T036 [US4] In `tests/test_errors.py`, add the FR-022 mid-write failure test: let validation pass, then inject a filesystem failure once writing has begun (monkeypatch `shutil.copyfileobj` or the builtin `open` used by the write phase to raise `OSError` on the second member, or revoke write permission on a created subdirectory) and assert stderr carries exact template D11 `tarx: failed while writing member '{name}' to '{path}': {reason}` naming the member being written, stdout contains **no** `extracted N files` summary, and the status is 2. Assert explicitly that files written before the failure are still present — the tool does not roll back, and the test pins that documented limit (clarification Q1)
- [X] T037 [US4] In `tests/test_errors.py`, add the FR-025 aggregation tests end to end: an archive with several independent problems reports **all** of them, one per line on stderr, rather than stopping at the first; an archive mixing an unsafe member path (class 2) with a refused overwrite (class 3) exits **2, not 3**, with both lines present; and the FR-014 end-to-end case — an archive containing an absolute-path or `..`-escaping member writes no files, names every offending member via D5, and exits 2 with the destination unchanged
- [X] T038 [P] [US4] In `tests/test_validation.py`, add unit-level coverage of the classification and reporting rules by calling `core.build_plan` and `core.resolve_exit_status` directly: one case per row of data-model.md → "State transitions of a destination path" (nothing / directory / regular file / other existing entry × `DIR` and `FILE` member, for both `overwrite` settings), the ancestor rules below that table, `resolve_exit_status` precedence (2-only → 2, 3-only → 3, mixed → 2, empty → 0), the reporting order (destination-level problems D3/D4 first, then member problems in archive order), and that a member rejected by D5 contributes exactly one problem line and is not additionally reported under D6–D10 (FR-023, FR-025, research.md §4–§5)

### Implementation for User Story 4

> T039–T042 all edit `src/tarx/core.py` and are sequential.

- [X] T039 [US4] In `src/tarx/core.py`, add the destination checks to the start of the validation phase (before any member is walked): if `DEST` exists and is not a directory, append a class-2 `Problem` with exact template D3; if an existing ancestor of `DEST` is not a directory, append a class-2 `Problem` with exact template D4. Use `os.path.isdir`/`os.path.lexists` only — no write, no `makedirs` (FR-019, FR-020)
- [X] T040 [US4] In `src/tarx/core.py`, extend `build_plan` with the FR-023 type-mismatch checks, each appending a class-2 `Problem` with its exact template: existing directory at a `KIND_FILE` member's target (D6); existing non-directory — regular file, symlink, FIFO or device — at a `KIND_DIR` member's target (D7); existing non-directory at any ancestor path between `DEST` and a member's target (D8); and the archive-internal case where another member of the same archive stores a regular file at a path this member requires to be a directory (D9), which needs the set of parent paths implied by the plan compared against the planned file paths (research.md §4). All of these are class 2 under **both** overwrite settings — `--overwrite` consents only to replacing a regular file with a regular file, so status 3's "re-run with `--overwrite`" would be false advice here
- [X] T041 [US4] In `src/tarx/core.py`, wrap the write phase's directory creation and file streaming in a narrow `except OSError` that raises `TarxError` with exact template D11 and `exit_class = EXIT_INPUT`, naming the member and target path in hand when the error surfaced (FR-022). Catch `OSError` only — no bare `except`, no `Exception` (Principle II) — and ensure the raise propagates before any summary line can be written, so `cli` suppresses stdout entirely for this case
- [X] T042 [US4] In `src/tarx/core.py`, fix the problem **reporting order** so it is deterministic and assertable: destination-level problems (D3, D4) first, then member problems in archive order, with each member contributing at most one problem line because a member rejected by D5 skips the D6–D10 checks (research.md §5, FR-025). Verify the skip notices of FR-015 remain outside this list — they are written on stderr in archive order but are not problems, never affect the exit status, and never suppress the summary

**Checkpoint**: All four user stories are independently functional. Every documented failure path is loud, specific, tested, and distinguishable by exit status alone.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The traceability audit, the scale criteria, and the constitution's merge gate

- [X] T043 Create `tests/test_traceability.py` implementing the FR-021 / SC-007 audit: parse every `FR-###` identifier out of `specs/001-tarx-cli/spec.md`, scan all files under `tests/`, and assert each identifier is referenced by at least one test name or docstring, failing with the list of uncovered identifiers. Cross-check the result against the requirement-to-test map in [data-model.md](./data-model.md#requirement-to-test-map) and fix any divergence in whichever is wrong
- [X] T044 [P] Add the SC-008 scale checks as tests under `tests/test_extract.py` (or mark them slow): build a 10,000-member archive in `tmp_path` as shown in quickstart.md → Scale checks and assert `list` emits 10,000 lines in under 5 seconds, and assert extraction streams a member far larger than a plausible buffer without resident memory growing with member size (`shutil.copyfileobj`'s fixed buffer, plan.md Performance Goals)
- [X] T045 Run every scenario in [quickstart.md](./quickstart.md) from the repository root with `PYTHONPATH=src` — Scenarios 1 through 8 — and confirm each observed stdout, stderr, and exit status matches the documented expectation; correct the implementation where it diverges, or quickstart.md where the document is the thing that is wrong
- [X] T046 Audit compliance against the Constitution gates: grep `src/tarx/` for imports and confirm every one is standard library (Principle I); confirm `[project.dependencies]` in `pyproject.toml` is still empty and `pytest` appears only in the test group; grep for `except:` and `except Exception` and confirm there are none, and that every `except OSError` / `except tarfile.TarError` re-raises as a named `TarxError` diagnostic (Principle II); confirm no post-3.11 stdlib API is used — specifically no `tarfile` extraction filters and no `Path.walk` (plan.md Technical Context)
- [X] T047 Review `src/tarx/core.py` and `src/tarx/cli.py` against Principle IV: confirm the module set is exactly the four files plan.md specifies, that no class exists beyond the plain data holders (`TarxError`, `Problem`, `MemberTarget`, `WritePlan`), that no configuration option, plugin seam, or caching layer was introduced, and that total runtime size is in the expected 250–350 line range; remove any speculative structure found
- [X] T048 Run the merge gate: `python -m pytest` from the repository root with the full suite green, including `tests/test_traceability.py`. Constitution Quality Gate 4 makes this a hard precondition — a change leaving any specified requirement without a passing covering test must not be merged

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1, T001–T004)**: No dependencies — start immediately
- **Foundational (Phase 2, T005–T012)**: Depends on Setup — **BLOCKS all user stories**
- **User Story 1 (Phase 3, T013–T017)**: Depends on Foundational only
- **User Story 2 (Phase 4, T018–T027)**: Depends on Foundational only
- **User Story 3 (Phase 5, T028–T031)**: Depends on Foundational, and on US2's `build_plan`/`write_plan` (T024, T025) because it extends them rather than adding a parallel path
- **User Story 4 (Phase 6, T032–T042)**: Depends on Foundational, and on US2's validation skeleton (T022–T027) because its checks are additional `Problem` producers inside `build_plan`
- **Polish (Phase 7, T043–T048)**: Depends on all stories being complete — T043 and T048 can only pass once every FR has a covering test

### User Story Dependencies

- **US1 (P1)**: Independent. Needs nothing from any other story — this is why it is the MVP
- **US2 (P2)**: Independent of US1 at the code level (it shares only `open_archive` from Foundational) and independently testable
- **US3 (P3)**: Extends US2's plan builder. Not startable before T024/T025 exist, but independently testable once done
- **US4 (P4)**: Extends US2's validation phase. Hardens all three stories above; independently testable per failure mode

### Within Each User Story

- Tests are written first and MUST fail before the implementation tasks in the same phase begin (Constitution Principle III, Quality Gate 3)
- In `core.py`: constants and helpers → `open_archive` → `Problem`/`MemberTarget` → `build_plan` → `write_plan` → `extract`
- `core.py` before `cli.py`; `cli.py` before `__main__.py`
- Validation before writing — this ordering is itself the FR-020 requirement, not a convenience

### Parallel Opportunities

- T002 and T003 are in different files and can run together
- T012 (`tests/conftest.py`) can be written alongside the `core.py` tasks T005–T008
- Once Foundational completes, **US1 (Phase 3) and US2 (Phase 4) can be developed in parallel** by different people — they share no file except `cli.py`, where each adds its own command handler
- Within US2, T020 (`tests/test_overwrite.py`) and T021 (`tests/test_validation.py`) are different files and run in parallel
- Within US4, T038 (`tests/test_validation.py`) runs in parallel with T032–T037 (`tests/test_errors.py`)
- T044 is a different file from T043 and can run alongside it
- **Not** parallel: tasks sharing a file. T005–T008 and T039–T042 all edit `src/tarx/core.py`; T013–T015 all edit `tests/test_list.py`; T032–T037 all edit `tests/test_errors.py`

---

## Parallel Example: Foundational and User Story 1

```bash
# Phase 2 — the conftest fixtures are independent of the core module:
Task: "T012 Create tests/conftest.py with archive-building fixtures and CLI helpers"
Task: "T005 Add exit-status constants to src/tarx/core.py"   # then T006, T007, T008 in sequence

# After the Foundational checkpoint — two stories, two developers:
Task: "Phase 3 (T013-T017) User Story 1: list command + tests/test_list.py"
Task: "Phase 4 (T018-T027) User Story 2: extract command + tests/test_extract.py"

# Within Phase 4 — two different test files:
Task: "T020 tests/test_overwrite.py refusal tests (FR-009, FR-020)"
Task: "T021 tests/test_validation.py path-safety unit tests (FR-014)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T004)
2. Complete Phase 2: Foundational (T005–T012) — blocks everything
3. Complete Phase 3: User Story 1 (T013–T017)
4. **STOP and VALIDATE**: run `python -m pytest tests/test_list.py`, then quickstart.md Scenario 1 by hand
5. At this point `python -m tarx list` is a working, safe-by-construction archive inspector that writes nothing to disk — deliverable on its own

### Incremental Delivery

1. Setup + Foundational → substrate ready
2. **+ US1** → listing works for both formats → validate → **MVP**
3. **+ US2** → extraction works and refuses to clobber → validate with quickstart Scenarios 2, 3, 5 → deliverable
4. **+ US3** → `--overwrite` enables refresh workflows → validate with Scenario 4 → deliverable
5. **+ US4** → every failure path is loud, specific, and distinguishable → validate with Scenarios 6, 7 → deliverable
6. **+ Polish** → traceability audit green, scale criteria met, constitution gate passed → done

Each step adds value without breaking the previous ones. US1 and US2 are the two that can be built concurrently; US3 and US4 both layer onto US2's plan builder, so they are best taken in that order by one person, or split with care since both edit `build_plan`.

### Parallel Team Strategy

With three developers:

1. Everyone on Setup + Foundational (T001–T012), with T012 split off to one person
2. Once the Foundational checkpoint passes:
   - Developer A: US1 (Phase 3) — self-contained, finishes first
   - Developer B: US2 (Phase 4) — the largest phase
   - Developer C: writes the US4 test files (T032–T038) against the contracts, which need no US2 code to **author**, only to pass
3. Developer A moves to US3 (Phase 5) once B's T024/T025 land; B and C converge on US4's implementation (T039–T042)
4. Polish (Phase 7) is shared, with T048 run last by whoever merges

---

## Notes

- `[P]` tasks touch different files and have no dependency on an incomplete task; tasks listed under the same file are deliberately sequential
- `[Story]` labels map each task to a spec user story for traceability; Setup, Foundational and Polish tasks carry no story label by design
- Diagnostic wording from [contracts/cli.md](./contracts/cli.md#diagnostic-templates) marked **exact** is part of the contract — reproduce the templates verbatim, including the `tarx: ` prefix, and assert on them in tests
- Every test must name its requirement ID in the test name or docstring, or T043 will fail
- Verify tests fail before implementing — a test that passes against missing code is testing nothing (Principle III)
- Commit after each task or logical group; stop at any checkpoint to validate a story independently
- Avoid: `TarFile.extractall` (plan.md Complexity Tracking), any filesystem write during the validation phase (FR-020), bare `except` (Principle II), and any runtime import outside the standard library (Principle I)
