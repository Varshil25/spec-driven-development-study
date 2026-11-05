---

description: "Task list for Tar Archive List & Extract CLI"
---

# Tasks: Tar Archive List & Extract CLI

**Input**: Design documents from `/specs/001-tar-archive-cli/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli-contract.md](./contracts/cli-contract.md), [quickstart.md](./quickstart.md)

**Tests**: Test tasks ARE included and are mandatory for this feature. SC-006 requires every functional requirement to be covered by at least one automated test traceable to its requirement id, and Constitution Principle III ("Every Requirement Is Testable") makes the same demand a merge gate. Tests are therefore not optional here.

**Organization**: Tasks are grouped by user story (US1–US4, priorities P1–P4) so each story can be implemented, tested, and delivered as an independent increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project, per plan.md *Project Structure*. Repository root holds `pytest.ini`; runtime code lives in `src/tarx/`; tests live in `tests/`. There are exactly three runtime files (`__init__.py`, `__main__.py`, `cli.py`) — no `models/`, `services/`, or `lib/` directories (Constitution Principle IV).

**Note on same-file sequencing**: nearly all implementation lands in the single module `src/tarx/cli.py`, so implementation tasks within a phase are *not* marked `[P]` even when logically independent. Test files are separate per requirement cluster and are frequently parallelizable.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the file skeleton and test configuration so a bare `pytest` from the repository root can import the package.

- [ ] T001 Create the directory skeleton `src/tarx/` and `tests/` at the repository root, matching plan.md *Project Structure* exactly (no `models/`, `services/`, or `lib/` subdirectories)
- [ ] T002 [P] Create `pytest.ini` at the repository root containing a `[pytest]` section with `pythonpath = src` and `testpaths = tests`, so a bare `pytest` from the root imports `src/tarx` with no environment setup (research R10, Constitution Technology Constraints)
- [ ] T003 [P] Create `src/tarx/__init__.py` as an empty package marker with no logic — it exists only because `python -m tarx` requires a package (plan.md Principle IV justification 1)
- [ ] T004 [P] Add `__pycache__/` and `.pytest_cache/` entries to the repository-root `.gitignore` if not already present

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The error-reporting spine, argument-parser shell, entry point, and shared archive-opening helper. Every user story depends on these; none of them is story-specific.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 Create `src/tarx/cli.py` with a module docstring and the three exit-status constants `EXIT_OK = 0`, `EXIT_ERROR = 2`, `EXIT_CONFLICT = 3` so FR-028's "consistently and exclusively" is checkable by reading three definitions (FR-028, data-model.md *Error record*)
- [ ] T006 Add the single internal exception class `TarxError(Exception)` to `src/tarx/cli.py` carrying exactly two fields — `message` (human-readable, one line, names the offending path or member) and `code` (either `2` or `3`; `0` is never carried by an error) (FR-027, FR-028, data-model.md *Error record*; this is the one place Principle IV's "prefer a plain data structure" is overridden because Python's `raise` requires an exception type)
- [ ] T007 Implement `build_parser()` in `src/tarx/cli.py` returning an `argparse.ArgumentParser` constructed with an explicit `prog="tarx"` and a subparsers object with `dest="command", required=True`; register no subcommands yet (FR-001, FR-004, research R7 — the default `prog` would render `usage: __main__.py ...` and undercut SC-008)
- [ ] T008 Implement `main(argv)` in `src/tarx/cli.py`: build the parser, parse `argv`, dispatch to the selected subcommand handler, and wrap the dispatch in a single `except TarxError` that writes exactly `tarx: <message>` plus a newline to `sys.stderr` and returns `error.code`; return `EXIT_OK` on success. This must be the *only* place in the codebase that formats a diagnostic or chooses an exit status (FR-027, FR-028, contracts/cli-contract.md *Diagnostics* format `tarx: <message>`)
- [ ] T009 Create `src/tarx/__main__.py` as a two-line entry point that imports `main` from `src/tarx/cli.py` and calls `sys.exit(main(sys.argv[1:]))` — no logic beyond this (plan.md Principle IV justification 1)
- [ ] T010 Implement the shared helper `open_archive(path)` in `src/tarx/cli.py` using `tarfile.open(path, mode="r:*")` (written explicitly so content-sniffing intent is readable), converting each failure to a `TarxError` with the contract's own message text and code `2`: `FileNotFoundError` → `cannot read archive '<path>': no such file`; `IsADirectoryError` → `cannot read archive '<path>': is a directory`; `PermissionError` → `cannot read archive '<path>': permission denied`; `tarfile.ReadError` → `'<path>' is not a valid tar archive`; any other `OSError` → `cannot read archive '<path>': <reason>`. Never forward `tarfile.ReadError`'s own text, which research R4 verified is multi-line and would violate FR-027 (FR-018, FR-024, research R2/R4, contracts/cli-contract.md *Diagnostics*)
- [ ] T011 Create `tests/conftest.py` with the shared archive-building fixtures used across the suite, each building into `tmp_path`: (a) a plain `.tar` with members `photos/a.jpg` then `photos/b.jpg` in that order with distinct known bytes; (b) the gzip-compressed equivalent `.tar.gz`; (c) a gzip-compressed archive deliberately **named** `mislabeled.tar`; (d) a nested archive several levels deep that also contains a directory member with no files in it; (e) a valid empty archive built by `tarfile.open(..., "w")` with nothing added (research R5 verified this opens cleanly with `getmembers() == []`); (f) a zero-byte file, which is **not** a valid archive and must stay distinct from case (e); (g) a file of random bytes; (h) an archive containing a symbolic-link member alongside a regular file and a directory. Also provide a helper that runs `python -m tarx` as a subprocess with `PYTHONPATH=src` set explicitly in the child environment, since `pytest.ini`'s `pythonpath` affects only the pytest process (research R10)
- [ ] T012 Create `tests/test_invocation.py` with a foundational smoke test asserting that `python -m tarx --help` exits 0 and that its usage line begins `usage: tarx` rather than `usage: __main__.py` (FR-001, research R7)

**Checkpoint**: `pytest` runs green from the repository root; `python -m tarx --help` prints correct usage; no subcommand behavior exists yet. User story implementation can now begin.

---

## Phase 3: User Story 1 - Inspect what an archive contains (Priority: P1) 🎯 MVP

**Goal**: `python -m tarx list ARCHIVE` prints the recorded name of every archive member, one per line, in archive order, for both plain and gzip-compressed archives, exiting 0 with empty stderr.

**Independent Test**: Create an archive with known members in a known order, run the list command against it, and confirm stdout contains exactly those member names, one per line, in that order, with exit status 0 and empty stderr. Repeat with the gzip form and with a gzip archive misnamed `.tar` — output must be identical. No extraction behavior is required.

### Tests for User Story 1

> **NOTE: Write these tests FIRST and confirm they FAIL before implementing T016–T018.**

- [ ] T013 [P] [US1] Create `tests/test_list.py` covering FR-005 through FR-009, with the requirement id in each test name or docstring: every member's recorded path on its own line terminated by `\n` (FR-005); archive order preserved with no sorting, filtering, or de-duplication applied (FR-006); every member type printed including directory entries and the symbolic-link member from the conftest fixture (FR-007); directory member names printed **without** a trailing path separator, asserted against an archive whose directory headers store `real/` (FR-008, research R3); exit status 0 and empty stderr on success (FR-009); and the empty-archive case printing nothing with exit 0 (US1 acceptance scenario 4, research R5)
- [ ] T014 [P] [US1] Create `tests/test_compression.py` covering the list side of FR-017 and FR-018: listing the plain archive and listing its gzip-compressed twin produce byte-identical stdout and the same exit status (FR-017); listing the gzip archive deliberately named `mislabeled.tar` produces that same output, proving detection comes from content and not from the file-name extension (FR-018, research R2)
- [ ] T015 [US1] Extend `tests/test_invocation.py` with FR-002 coverage: `list` with zero positional arguments and `list` with two positional arguments each write usage guidance to stderr, write nothing to stdout, and exit non-zero (FR-002)

### Implementation for User Story 1

- [ ] T016 [US1] Register the `list` subparser in `build_parser()` in `src/tarx/cli.py` with exactly one positional argument `ARCHIVE` and no options (FR-002, contracts/cli-contract.md *`list ARCHIVE`*)
- [ ] T017 [US1] Implement `cmd_list(args)` in `src/tarx/cli.py`: open the archive via `open_archive`, iterate the `TarFile` object directly with `for member in tar:` (**not** `getmembers()`, so metadata is consumed as it is parsed and memory stays flat — research R6), print `member.name` verbatim with no trailing-separator handling (research R3 verified `tarfile` already strips it), and return `EXIT_OK`. Use a `with` block so the archive is closed; write nothing to stderr (FR-005, FR-006, FR-007, FR-008, FR-009)
- [ ] T018 [US1] Wire the `list` command into `main()`'s dispatch in `src/tarx/cli.py`, and wrap member iteration so a `tarfile.ReadError` or `OSError` raised mid-parse (a truncated archive) still surfaces as a `TarxError` with code `2` rather than a traceback (FR-024, FR-027)

**Checkpoint**: User Story 1 is fully functional and independently testable — listing works for plain, gzip, and misnamed archives, and `pytest` is green.

---

## Phase 4: User Story 2 - Unpack an archive into a chosen directory (Priority: P2)

**Goal**: `python -m tarx extract ARCHIVE DEST` recreates every regular-file and directory member under `DEST` at its recorded relative path with byte-identical contents, creating `DEST` and missing parents as needed, skipping member types it does not handle, and printing exactly `extracted N files`.

**Independent Test**: Create an archive with known files, contents, and nested directories including one empty directory; extract it into a destination that does not yet exist; confirm every regular file exists at the expected relative path with byte-identical contents, the full directory structure exists, stdout is exactly `extracted N files` with N counting only regular files, and the exit status is 0.

### Tests for User Story 2

> **NOTE: Write these tests FIRST and confirm they FAIL before implementing T023–T028.**

- [ ] T019 [P] [US2] Create `tests/test_extract.py` covering FR-010 through FR-016 with requirement ids in test names or docstrings: each regular-file member recreated at `DEST/<member name>` with byte-identical contents (FR-010); every directory needed by a member created, **and** directory members containing no files also created (FR-011); a `DEST` that does not exist created along with its missing parents (FR-012); pre-existing non-colliding entries under `DEST` left unmodified (FR-013, US2 acceptance scenario 5); stdout exactly the single line `extracted N files\n` with exit 0 and empty stderr (FR-014); the count including only regular files written — excluding directories and excluding skipped members — and using the literal word `files` for every N including `0` and `1` (FR-015); the symbolic-link member from the conftest fixture skipped without failing and not counted (FR-016); plus the empty-archive case printing exactly `extracted 0 files` with exit 0 (US2 acceptance scenario 4)
- [ ] T020 [P] [US2] Extend `tests/conftest.py` with an archive fixture that stores the **same** member path twice with different contents, built programmatically since GNU `tar` will not produce it conveniently; and a fixture producing a zero-length archived file (research R9, spec Edge Cases *Duplicate member names* and *Zero-length archived files*)
- [ ] T021 [US2] Extend `tests/test_extract.py` with the duplicate-path and zero-length cases: a path stored twice ends on disk with the **later** entry's contents and contributes **once** to the reported count (FR-015, research R9); a zero-length archived file is recreated as an empty file and **is** counted in the summary (spec Edge Cases)
- [ ] T022 [US2] Extend `tests/test_compression.py` with the extract side of FR-017: extracting the gzip-compressed archive and extracting its plain twin produce identical file trees, identical summary lines, and identical exit statuses; extracting the gzip archive named `mislabeled.tar` behaves the same (FR-017, FR-018, US2 acceptance scenario 2)
- [ ] T023 [US2] Extend `tests/test_invocation.py` with FR-003 coverage: `extract` with one positional argument and `extract` with three positional arguments each write usage to stderr and exit non-zero; `extract ARCHIVE DEST --overwrite` is accepted as a valid invocation (FR-003)

### Implementation for User Story 2

- [ ] T024 [US2] Register the `extract` subparser in `build_parser()` in `src/tarx/cli.py` with exactly two positional arguments `ARCHIVE` then `DEST`, plus `--overwrite` as a `store_true` flag (FR-003, contracts/cli-contract.md *`extract ARCHIVE DEST [--overwrite]`*)
- [ ] T025 [US2] Implement `member_target(name, dest)` in `src/tarx/cli.py` resolving a member's recorded name to its destination path: compute `posixpath.normpath(name)` and join it under `dest`. Keep the resolution purely lexical with **no filesystem access** so it can run before the destination exists (data-model.md *Member name validation*; containment rejection itself is added in Phase 6 / T038)
- [ ] T026 [US2] Implement `build_plan(tar, dest)` in `src/tarx/cli.py` returning a plain tuple of plain lists — `(plan, skipped)` where `plan` is a list of `(member, target_path, kind)` triples in **preserved archive order** and `skipped` counts members that are neither regular files nor directories. Classify each member by exactly three cases using `TarInfo.isreg()` / `TarInfo.isdir()` / neither; drop the "other" kind from the plan rather than failing. Use no classes and no custom types (FR-006, FR-016, data-model.md *Kind taxonomy* and *ExtractionPlan*)
- [ ] T027 [US2] Implement destination preparation in `src/tarx/cli.py`: after planning succeeds, create the destination with `Path(dest).mkdir(parents=True, exist_ok=True)` so missing parent directories are created — and only at this point, so a run that fails during planning leaves no new directories behind (FR-012, FR-020, data-model.md *Destination*)
- [ ] T028 [US2] Implement the write pass in `src/tarx/cli.py`: walk `plan` in archive order; for a directory member call `Path.mkdir(parents=True, exist_ok=True)`; for a regular-file member create its parent directories then `open(target, "wb")` and `shutil.copyfileobj(tar.extractfile(member), dst, length=64 * 1024)` — streaming in fixed-size chunks so memory does not grow with the size of the largest member, never `extractfile(...).read()` (SC-007, research R6). Add each written regular-file target to a `WrittenSet` (a `set` of destination paths, **not** an integer counter, because a path stored twice must contribute once while the later entry's contents win). Do **not** call `TarFile.extract` or `extractall`, and do not apply member metadata — modes, ownership, and mtimes are explicitly out of scope (FR-010, FR-011, FR-013, FR-015, research R9/R11, data-model.md *WrittenSet*)
- [ ] T029 [US2] Implement `cmd_extract(args)` in `src/tarx/cli.py` as the two-phase pipeline — open archive, build plan, prepare destination, run the write pass — then print exactly `extracted {len(written)} files` to stdout and return `EXIT_OK`, writing nothing to stderr. Use the literal word `files` unconditionally (FR-014, FR-015, contracts/cli-contract.md). Wire `extract` into `main()`'s dispatch

**Checkpoint**: User Stories 1 AND 2 both work independently — listing and fresh extraction are complete for plain and gzip archives, and `pytest` is green. Overwrite protection and the full failure matrix are not yet in place.

---

## Phase 5: User Story 3 - Never clobber existing files by accident (Priority: P3)

**Goal**: Without `--overwrite`, an extraction that would replace an existing regular file fails with exit status 3, a diagnostic naming the conflicting path, and **nothing written**. A kind mismatch fails with exit status 2 regardless of the flag. With `--overwrite`, colliding regular files are replaced and counted.

**Independent Test**: Extract an archive into a destination twice. The second run must exit 3, print a diagnostic on stderr naming a conflicting path, print nothing to stdout, and leave every previously extracted file byte-for-byte unchanged (verified by comparing contents before and after). Repeat the second run with `--overwrite` and confirm it exits 0, replaces the file contents, and reports the full count. Separately, confirm a directory that already exists where the archive stores a directory is **not** a conflict.

### Tests for User Story 3

> **NOTE: Write these tests FIRST and confirm they FAIL before implementing T031–T034.**

- [ ] T030 [P] [US3] Create `tests/test_overwrite.py` covering FR-019 through FR-023 with requirement ids in test names or docstrings: without `--overwrite`, a regular-file member whose target already exists as a regular file produces the diagnostic `tarx: '<path>' already exists; use --overwrite to replace it` on stderr, empty stdout, and exit status **3** (FR-019); that failing run creates, modifies, truncates, and deletes nothing under the destination, asserted by hashing the whole destination tree before and after (FR-020, SC-003); with `--overwrite`, existing regular files at colliding paths have their contents replaced and are counted among the files written, stdout is exactly `extracted N files`, exit 0 (FR-021); an existing directory at the path of a directory member is not a conflict with or without the flag — structures merge (FR-022, US3 acceptance scenario 4); a partially-populated destination still fails with exit 3 without adding any of the archive's other files (US3 acceptance scenario 3)
- [ ] T031 [US3] Extend `tests/test_overwrite.py` with the kind-collision cases, each exiting **2 even when `--overwrite` is given** (FR-023, research R8): a regular-file member whose target already exists as a directory gives `tarx: cannot replace directory '<path>' with file from member '<name>'`; a directory member whose target already exists as a regular file gives `tarx: cannot replace '<path>' with directory from member '<name>'`. Add an explicit regression test for research R8's resolved ambiguity — no `--overwrite`, file member, existing directory at the target — asserting exit **2** and not 3, since exit 3 must mean "re-running with `--overwrite` would fix this". Also cover an existing **non-directory ancestor** between the destination and a planned target, which must be reported as a collision at planning time rather than surfacing as a mid-write `NotADirectoryError` (data-model.md *ExtractionPlan*)

### Implementation for User Story 3

- [ ] T032 [US3] Extend `build_plan` in `src/tarx/cli.py` to also collect `conflicts`: for each planned regular-file target that already exists as a regular file, record the path. Evaluate conflicts against the destination's **pre-existing** state only — because all validation precedes any write, a path written earlier in the same run can never be mistaken for a pre-existing conflict (FR-019, research R9)
- [ ] T033 [US3] Extend `build_plan` in `src/tarx/cli.py` to also collect `collisions`: a regular-file member whose target exists as a directory; a directory member whose target exists as a non-directory; and, for each planned target, any path between the destination and the target that already exists and is **not** a directory (the non-directory-ancestor case) (FR-023, data-model.md *ExtractionPlan*)
- [ ] T034 [US3] Enforce the fixed validation order in `cmd_extract` in `src/tarx/cli.py` before any write and before the destination is created: `collisions` → `TarxError(code=EXIT_ERROR)`, then `conflicts` → `TarxError(code=EXIT_CONFLICT)` when `--overwrite` was not given. Exit 2 outranks exit 3 so status 3 always means "re-run with `--overwrite`". Because the whole planning phase is read-only with respect to the filesystem, FR-020's "nothing created, modified, truncated, or deleted" holds by construction rather than by promise (FR-019, FR-020, FR-023, research R8, contracts/cli-contract.md *Validation order within `extract`*)
- [ ] T035 [US3] Honor `--overwrite` in `src/tarx/cli.py`: when set, skip raising on `conflicts` so the write pass replaces the existing files' contents and counts them in the `WrittenSet`; `collisions` still raise exit 2 regardless of the flag. Confirm a directory member targeting an existing directory is never recorded as a conflict in either mode (FR-021, FR-022)

**Checkpoint**: User Stories 1, 2, AND 3 are independently functional — data loss is prevented by default, `--overwrite` works, kind collisions are rejected, and `pytest` is green.

---

## Phase 6: User Story 4 - Clear, scriptable failure for unusable input (Priority: P4)

**Goal**: Every specified failure — unusable archive, unusable destination, member path escaping the destination, invocation error, permission error, mid-write error — produces a short one-line diagnostic on stderr naming the offending path or member, empty stdout, and the exit status this specification assigns, with zero uncaught tracebacks.

**Independent Test**: Run each command against a nonexistent path, a directory, and a file of random bytes; run `extract` against a destination that already exists as a regular file and against an archive containing an escaping member; and invoke the tool with no subcommand and with an unrecognized subcommand. Each run must print a non-empty diagnostic on stderr, print nothing on stdout, exit with its assigned status, and produce no Python traceback.

### Tests for User Story 4

> **NOTE: Write these tests FIRST and confirm they FAIL before implementing T039–T043.**

- [ ] T036 [P] [US4] Extend `tests/conftest.py` with programmatically-built archive fixtures whose members escape the destination — one with an absolute POSIX member name such as `/etc/escape.txt`, one with a traversing name such as `../escape.txt`, one whose normalized name begins `../`, one carrying a Windows drive-letter prefix, and one carrying a UNC prefix. These cannot be produced conveniently with GNU `tar`, so build them with `tarfile` directly (quickstart.md *Scenario 4*, data-model.md *Member name validation*)
- [ ] T037 [P] [US4] Create `tests/test_failures.py` covering FR-024 through FR-028 with requirement ids in test names or docstrings. For **both** subcommands: a nonexistent archive path gives `tarx: cannot read archive '<path>': no such file`, empty stdout, exit 2; an archive path that is a directory gives `... : is a directory`; an unreadable archive (mode `0o000`, skipped when running as root) gives `... : permission denied`; a file of random bytes and a **zero-byte** file each give `tarx: '<path>' is not a valid tar archive` — the zero-byte case asserted distinctly from the valid-empty-archive success case (FR-024, research R4/R5). For `extract`: a destination that already exists as a regular file gives `tarx: destination '<path>' exists and is not a directory` with exit 2 and no extraction performed (FR-025, US4 acceptance scenario 3); each escaping-member fixture gives `tarx: refusing to extract member '<name>' outside destination` with exit 2 and **nothing created outside the destination**, verified by checking the surrounding filesystem (FR-026). Assert for every failure case that stderr is non-empty, is a single line, names the offending path or member, and contains no `Traceback (most recent call last)` (FR-027, SC-005)
- [ ] T038 [US4] Extend `tests/test_invocation.py` with FR-004 coverage: no subcommand at all, an unrecognized subcommand such as `frobnicate`, and an unrecognized option each write usage guidance to stderr, write nothing to stdout, exit with status 2, and perform no other action (FR-004, contracts/cli-contract.md — this is `argparse`'s own default behavior and must be confirmed rather than reimplemented). Add an FR-028 exclusivity test asserting the observed status set across the whole suite is exactly `{0, 2, 3}` with 3 produced only by the no-`--overwrite` file-replacement conflict

### Implementation for User Story 4

- [ ] T039 [US4] Implement `validate_destination(dest)` in `src/tarx/cli.py`, called from `cmd_extract` **after** the archive opens successfully and **before** planning: if the path exists and is not a directory, raise `TarxError("destination '<path>' exists and is not a directory", EXIT_ERROR)`. Report archive errors before destination errors so the diagnostic is deterministic when both are present (FR-025, research R8 follow-on decision, contracts/cli-contract.md *Validation order*)
- [ ] T040 [US4] Wrap the destination `mkdir` in `src/tarx/cli.py` so a failure to create or write to the destination raises `TarxError("cannot write to destination '<path>': <reason>", EXIT_ERROR)` rather than surfacing a raw `OSError` (FR-025, FR-027)
- [ ] T041 [US4] Add containment rejection to the plan-building path in `src/tarx/cli.py`, collecting a `violations` list of member names that fail a **purely lexical** check on the recorded name, with no filesystem access: rejected if `posixpath.isabs(name)`; rejected if the name carries a Windows drive letter or UNC prefix; rejected if `posixpath.normpath(name)` is `..` or starts with `../`. Otherwise the normalized name is the member's path relative to the destination. Do not use `os.path.realpath` containment checks — they touch the filesystem, depend on symlinks already inside the destination, and cannot run before the destination exists (FR-026, data-model.md *Member name validation*, research R11)
- [ ] T042 [US4] Insert the `violations` check as the **first** validation in `cmd_extract` in `src/tarx/cli.py`, ahead of `collisions` and `conflicts`, raising `TarxError("refusing to extract member '<name>' outside destination", EXIT_ERROR)`. The complete order is now: archive opens and parses → 2; destination exists and is not a directory → 2; member path escapes → 2; kind collision → 2; overwrite conflict without the flag → 3; writes begin. Steps before "writes begin" must touch no files (FR-026, FR-020, contracts/cli-contract.md *Validation order within `extract`*)
- [ ] T043 [US4] Add an `OSError` backstop around the write pass in `src/tarx/cli.py` converting any mid-write failure — a `PermissionError` on a target, a truncated archive discovered during streaming — into a `TarxError` with code `EXIT_ERROR` and a message naming the offending path, so the command reports a diagnostic and exits non-zero rather than printing a success line. Files already written are left in place; the spec requires no rollback. The backstop must convert to a named diagnostic, never swallow (spec Edge Cases *Partial write interrupted by an error*, FR-027, Constitution Principle II)
- [ ] T044 [US4] Audit `src/tarx/cli.py` for FR-027 and FR-028 compliance: confirm every exit flows through `EXIT_OK` / `EXIT_ERROR` / `EXIT_CONFLICT`, that no numeric status literal appears anywhere else, that there is exactly one place that formats a diagnostic (`main`), and that no `except` clause is bare or silently discards an error. Confirm by reading every `raise`, `return`, and `except` in the module that no code path can let an exception escape `main` uncaught (FR-027, FR-028, Constitution Principle II)

**Checkpoint**: All four user stories are independently functional. The full failure matrix is covered and no input produces a traceback.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Performance verification, traceability closure, and the constitution's quality gates.

- [ ] T045 [P] Create `tests/test_performance.py` covering SC-007, kept in its own file because it is the only slow test (plan.md *Structure Decision*): build an archive of 10,000 members, assert `list` completes in under 5 seconds and `extract` completes in under 30 seconds, and assert memory does not grow in proportion to the size of the largest member by extracting an archive containing one large member while sampling peak memory with `tracemalloc` (SC-007, research R6)
- [ ] T046 [P] Verify SC-006 traceability: confirm every requirement FR-001 through FR-028 is named by at least one test's name or docstring in `tests/`, and that each such test fails when its requirement is unmet. Add any missing coverage (SC-006, Constitution Principle III)
- [ ] T047 [P] Verify Constitution Principle I by reading every import line under `src/` and confirming each resolves to the standard library or to `tarx` itself — the expected set is `tarfile`, `argparse`, `pathlib`, `posixpath`, `shutil`, `sys`, `os`. Confirm `pytest` is imported nowhere under `src/` (Constitution Principle I, quickstart.md acceptance checklist)
- [ ] T048 [P] Verify Constitution Principle IV by confirming the runtime tree is exactly `src/tarx/__init__.py`, `src/tarx/__main__.py`, and `src/tarx/cli.py`, that `__init__.py` holds no logic, that `__main__.py` is the two-line entry point, and that no fifth structure beyond plan.md's four written justifications has appeared (Constitution Principle IV, plan.md *Simplicity justifications*)
- [ ] T049 Run the manual end-to-end walkthrough in [quickstart.md](./quickstart.md) — all four scenarios — and confirm each observed output, diagnostic, and exit status matches the documented expectation
- [ ] T050 Run `pytest` bare from the repository root with no arguments and confirm the full suite passes, then walk the acceptance checklist at the end of [quickstart.md](./quickstart.md) and confirm every box holds (Constitution *Development Workflow & Quality Gates*, SC-006)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational only
- **User Story 3 (Phase 5)**: Depends on Foundational; extends US2's `build_plan` and `cmd_extract`, so US2 must land first in practice
- **User Story 4 (Phase 6)**: Depends on Foundational; extends US2's plan-building and US3's validation ordering, so both must land first in practice
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

Unlike the typical greenfield feature, these four stories are **not** fully independent, because all runtime logic lives in one module by constitutional design (Principle IV). Each story is independently *testable* and independently *valuable*, but the later ones extend code the earlier ones introduce:

- **US1 (P1) — list**: Fully independent after Foundational. No other story's code is needed. This is the MVP.
- **US2 (P2) — extract**: Independent of US1 at the code level (it shares only `open_archive`), so US1 and US2 could be built in parallel by two people after Foundational. Spec.md notes US2 "builds on being able to read an archive", which Foundational already delivers.
- **US3 (P3) — overwrite protection**: Extends `build_plan` (T026) and `cmd_extract` (T029) from US2. Cannot be meaningfully implemented before US2 lands.
- **US4 (P4) — failure reporting**: Extends US2's plan-building and inserts a check ahead of US3's validation order (T042). Depends on both. Its FR-024 half is already satisfied by Foundational's `open_archive` (T010), so the archive-failure behavior is correct from the US1 checkpoint onward — US4 adds the destination, containment, and invocation halves plus the full test matrix.

### Within Each User Story

- Tests are written FIRST and must FAIL before the matching implementation task begins
- `build_parser` registration before the command handler that uses it
- `member_target` before `build_plan` before the write pass before `cmd_extract`
- Planning-phase code before write-phase code — the read-only/write split is what makes FR-020 structural
- Story complete and `pytest` green before moving to the next priority

### Parallel Opportunities

- Setup: T002, T003, T004 are all `[P]` — three different files, run together after T001
- Foundational: T005–T010 are strictly sequential (all in `src/tarx/cli.py`); T011 and T012 touch different test files and can run alongside each other once T009 exists
- US1: T013 and T014 are `[P]` — different test files
- US2: T019, T020 are `[P]`; T021 and T022 depend on T020 and T019 respectively
- US3: T030 is the only `[P]` task; T031 extends the same file
- US4: T036 and T037 are `[P]` — different test files
- Polish: T045, T046, T047, T048 are all `[P]`; T049 and T050 run last
- **Across stories**: after the Foundational checkpoint, one developer can take US1 (Phase 3) while another takes US2 (Phase 4) — they share only `open_archive`, which is already frozen. US3 and US4 cannot start until US2 lands.

---

## Parallel Example: User Story 1

```bash
# Launch both test files for User Story 1 together (write tests first, confirm they fail):
Task: "Create tests/test_list.py covering FR-005 through FR-009"
Task: "Create tests/test_compression.py covering the list side of FR-017 and FR-018"

# Then implement sequentially — all three tasks edit src/tarx/cli.py:
Task: "Register the list subparser in build_parser()"
Task: "Implement cmd_list(args) streaming with for member in tar:"
Task: "Wire the list command into main()'s dispatch"
```

## Parallel Example: Foundational + first two stories (two developers)

```bash
# Both developers complete Phase 1 and Phase 2 together, then split:
Developer A: Phase 3 (US1 — list):    T013 … T018
Developer B: Phase 4 (US2 — extract): T019 … T029
# Rejoin for Phase 5 (US3) and Phase 6 (US4), which both extend US2's code.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup — four files, no logic
2. Complete Phase 2: Foundational — exit codes, `TarxError`, parser shell, `main`, entry point, `open_archive`, fixtures (CRITICAL — blocks everything)
3. Complete Phase 3: User Story 1 — `list`
4. **STOP and VALIDATE**: run the Independent Test for US1 and quickstart.md Scenario 1
5. At this point `python -m tarx list ARCHIVE` is a complete, shippable tool that handles plain, gzip, and misnamed archives and fails cleanly on an unusable archive

### Incremental Delivery

1. Setup + Foundational → spine ready, `pytest` green, `--help` correct
2. Add US1 → validate with quickstart Scenario 1 → **MVP: archive inspection**
3. Add US2 → validate with quickstart Scenario 2 → **fresh extraction works**
4. Add US3 → validate with quickstart Scenario 3 → **no accidental data loss**
5. Add US4 → validate with quickstart Scenario 4 → **scriptable failure for every specified bad input**
6. Polish → SC-007 performance, SC-006 traceability, constitution gates
7. Each story adds value without breaking the previous ones; `pytest` must be green at every checkpoint

### Constitution Gates (checked at every checkpoint, not just at the end)

Per *Development Workflow & Quality Gates*, a phase is not complete until all five hold:

- The full `pytest` suite passes from the repository root with no arguments
- Every functional requirement implemented so far has a covering test traceable to its requirement id
- Runtime code under `src/` imports only the standard library and `tarx` itself
- Every specified invalid-input case reachable at this checkpoint produces a one-line diagnostic on stderr and a non-zero exit status
- No structure exists beyond what the specification requires, or it is justified in writing in plan.md

---

## Notes

- `[P]` tasks = different files, no dependencies. Most implementation tasks are **not** `[P]` because all runtime logic lives in `src/tarx/cli.py` by design (Constitution Principle IV).
- `[Story]` labels map tasks to US1–US4 for SC-006 traceability.
- Verify each test fails before implementing against it.
- Commit after each task or logical group.
- Stop at any checkpoint to validate that story independently.
- **Two design decisions are load-bearing and must not be refactored away**: (a) never call `TarFile.extract`/`extractall` — three requirement clusters are unreachable through it and it would reintroduce version-dependent extraction filters (research R11); (b) keep the planning pass strictly read-only and ahead of every write — that split is what makes FR-020 a structural property rather than a promise.
- **One spec ambiguity is resolved in the plan, not the spec**: research R8 decides that a kind collision exits 2 even without `--overwrite`, where FR-019 read literally would say 3. T031 locks this in with a regression test. This may warrant a spec amendment; it is flagged in plan.md for reviewer attention.
