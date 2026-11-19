---

description: "Task list for 002-create-command: the `tarx create` archive-creation command"
---

# Tasks: Archive Creation Command

**Input**: Design documents from `/specs/002-create-command/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/create-cli.md](./contracts/create-cli.md),
[quickstart.md](./quickstart.md), [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)

**Tests**: **INCLUDED and mandatory.** Not an option here — spec FR-025 and SC-011 require every
functional requirement to be covered by an automated test that fails when the requirement is
unmet, and Constitution Principle III makes that a merge gate.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested and
demonstrated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task belongs to (US1, US2, US3, US4)
- Exact file paths appear in every task description

## Path Conventions

Single project, as established by `001-tarx-cli` and kept unchanged by
[plan.md](./plan.md#project-structure):

- Runtime code: `src/tarx/core.py` (archive logic — **never prints, never exits**) and
  `src/tarx/cli.py` (**the only** module that touches streams and exit statuses)
- Tests: `tests/` at the repository root, flat, no `__init__.py`
- Repository root: `/root/sdd-study/runs/R035`

## Conventions binding on every task below

1. **Test naming (research.md §13)**: every new test function is named `test_create_fr_###_*` and
   its docstring cites `CREATE-FR-###`. Both specs number requirements `FR-001`-upward, so a bare
   `FR-###` token would be claimed by `001-tarx-cli`'s existing tests and the FR-025 audit would
   pass vacuously. The `CREATE-` prefix is what makes the audit mean something.
2. **No pre-existing test file is modified (research.md §12, SC-009)**. These seven files must stay
   byte-for-byte unchanged: `tests/conftest.py`, `tests/test_errors.py`, `tests/test_extract.py`,
   `tests/test_list.py`, `tests/test_overwrite.py`, `tests/test_traceability.py`,
   `tests/test_validation.py`. Their fixtures (`run_cli`, `run_module`, `snapshot_tree`,
   `make_archive`) are reused as they stand; new helpers go in `tests/create_support.py`.
3. **Diagnostic wording is contract (contracts/create-cli.md → Diagnostic templates)**. Templates
   C1–C11 are quoted verbatim in the tasks that produce them; assert them exactly.
4. **`create` operands are relative to the current directory**, so every test chdirs into a
   temporary directory first (helper in T004). `run_module` runs with `cwd=REPO_ROOT`, so
   subprocess-based tests must pass paths accordingly.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the pre-feature baseline. No code is written in this phase — the project,
its layout, its tooling and its dependency manifest already exist and this feature changes none
of them.

- [X] T001 Record the pre-feature baseline by running `python3 -m pytest` from the repository root `/root/sdd-study/runs/R035` and noting the passing test count; this is the figure the SC-009 / FR-023 regression gate in T047 is checked against
- [X] T002 [P] Confirm `pyproject.toml` needs no edit for this feature — `requires-python = ">=3.11"`, `dependencies = []` (Constitution Principle I), `pytest` isolated in `[dependency-groups] test`, `pythonpath = ["src"]`, and the `slow` marker under `[tool.pytest.ini_options]` are all already present; make no change to the file
- [X] T003 [P] Confirm the seven pre-existing files under `tests/` named in convention 2 above are the exact set that must remain byte-for-byte unchanged, and that `git status --short tests/` is clean before any work starts, so `git diff --stat` stays a valid mechanical check for SC-009

**Checkpoint**: Baseline recorded; nothing on disk has changed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared vocabulary every user story needs — test helpers, the new data holders,
the name/compression helpers, the `create` subparser, and the `core`/`cli` phase boundary.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Create `tests/create_support.py` with the source-tree builder and working-directory helper: `build_tree(root, spec)` materialising regular files with exact bytes, directories (including empty ones), symbolic links, FIFOs, sockets and hard links from a declarative spec, and `work_in(monkeypatch, path)` which `monkeypatch.chdir`s so `PATH` operands resolve inside a temporary directory. Leave `tests/conftest.py` untouched (research.md §12)
- [X] T005 Add the archive-inspection helpers to `tests/create_support.py`: `member_names(archive)` returning `tarfile.getnames()` in archive order, `member_entries(archive)` returning `(name, type byte, size)` triples so a `REGTYPE`/`DIRTYPE`/`LNKTYPE` distinction is assertable, `member_bytes(archive, name)` for byte-identity checks, and `is_gzip(archive)` testing the archive's own first two bytes against `b"\x1f\x8b"` (SC-007)
- [X] T006 [P] Add the `create` constants to `src/tarx/core.py`: `GZIP_SUFFIXES = (".tar.gz", ".tgz")`, and a source-entry label vocabulary yielding exactly `symbolic link`, `character device`, `block device`, `FIFO`, `socket`, with `unsupported file type` as the fallback — mirroring the existing `KIND_LABELS` vocabulary with `socket` added, since a filesystem can present one and an archive cannot (contracts/create-cli.md → Skipped entries, research.md §10)
- [X] T007 Add the `PlannedMember` data holder to `src/tarx/core.py`: fields `name: str` (relative, `/`-separated, no leading `./`, **no trailing `/` even for directories**), `kind: str` restricted to the existing `KIND_FILE` / `KIND_DIR` constants, and `path: str` (the filesystem path to read from). Data only, no behaviour (data-model.md → PlannedMember, Constitution Principle IV)
- [X] T008 Add the `CreatePlan` data holder to `src/tarx/core.py`: `members: dict[str, PlannedMember]` keyed by member name and insertion-ordered — so the dict **is** both the FR-020 de-duplication index and the FR-026 write order — and `skipped: list[tuple[str, str]]` holding `(path, label)` per non-regular entry in plan order (data-model.md → CreatePlan)
- [X] T009 Add `_archive_mode(archive)` to `src/tarx/core.py` returning `"w:gz"` when `archive.endswith(GZIP_SUFFIXES)` and `"w"` otherwise — a **literal, case-sensitive** suffix match on the string the user supplied, with no normalisation, so `PHOTOS.TAR.GZ` gets a plain archive (FR-005, research.md §2)
- [X] T010 Add the member-name helpers to `src/tarx/core.py`: `_member_name(operand)` returning `os.path.normpath(operand)` (which already collapses `photos/`, `./photos` and `photos/./a` correctly), with the value `"."` signalling "this operand contributes no member of its own, only its contents"; and `_child_name(parent_name, entry_name)` joining with a literal `/` (FR-004, research.md §5)
- [X] T011 Add the phase-boundary entry point `create(archive, paths, overwrite)` to `src/tarx/core.py` returning `(problems, skipped, count)` — the same shape the existing `extract()` returns, so `cli` needs no new reporting vocabulary. It calls `validate_and_plan(archive, paths, overwrite) -> (CreatePlan, list[Problem])` and, **only when the problem list is empty**, `write_archive(archive, plan) -> int`. Stub the two phases for now; they are filled in by US1–US3 (data-model.md → Phase boundary, FR-016)
- [X] T012 [P] Add the `create` subparser to `build_parser()` in `src/tarx/cli.py`: positional `archive` (metavar `ARCHIVE`), positional `paths` (metavar `PATH`, `nargs="+"` so at least one is required), and `--overwrite` (`action="store_true"`, `default=False`, help text naming it as consent to replacing an existing **regular file**). Update the top-level parser `description` and the per-command `help` strings so all three commands, their operands (`ARCHIVE`, `DEST`, `PATH`) and `--overwrite` are discoverable from the tool's own output. Add **no** `type=` converter — argument parsing stays purely syntactic so FR-022's "nothing is read or written" holds by construction (FR-002, FR-022, FR-024)
- [X] T013 Add `_run_create(archive, paths, overwrite)` to `src/tarx/cli.py` and dispatch `args.command == "create"` to it from `main()`: call `core.create(...)`; when problems exist, print every `problem.message` to **stderr** one per line, print **nothing** to stdout, and return `core.resolve_exit_status(problems)` (which already implements FR-018's "class 2 outranks class 3" — reuse, not re-implementation); otherwise print one `tarx: skipping non-regular path '{path}' ({label})` line per skipped entry to stderr, then print the **exact** template `created {archive} with {count} files` to stdout with `archive` echoed verbatim as supplied and `files` always plural, and return `core.EXIT_OK`. The summary is printed only after `core.create` returns successfully, so a failing run can never read as success (FR-008, FR-017, FR-018, Constitution Principle II)

**Checkpoint**: `python -m tarx create --help` works, `create` dispatches, and the test helpers
import. User story work can now begin.

---

## Phase 3: User Story 1 - Package files and folders into an archive (Priority: P1) 🎯 MVP

**Goal**: `create ARCHIVE PATH...` writes an archive holding every regular file and directory
beneath every named path, under member names that are exactly the relative paths the user typed,
in a fully determined order, compressed iff the archive's name says so — and reports the count.

**Independent Test**: Build a known directory tree, run `create` with a `.tar` name and again with
a `.tar.gz` name, and confirm each archive holds exactly the expected members in the expected
order with the expected names and byte-identical contents, that the gzip-named one starts `\x1f\x8b`
and the other does not, that stdout is the single summary line with the correct count, and that the
exit status is 0 with stderr empty.

### Tests for User Story 1 ⚠️

> Write these first and confirm each one **fails** before implementing. All land in
> `tests/test_create.py`, so they are written in sequence, not in parallel.

- [X] T014 [US1] Write failing tests for dispatch, operands and the summary line in `tests/test_create.py`: `create` is selected by the first operand alongside `list` and `extract` (`CREATE-FR-001`); one `PATH` accepted, many `PATH`s accepted, `--overwrite` parsed (`CREATE-FR-002`); stdout is **exactly** `created ARCHIVE with N files\n` with `ARCHIVE` echoed verbatim (not normalised, not made absolute) and the word `files` plural at N = 0, 1 **and** 2, with nothing else on stdout (`CREATE-FR-008`); success exits 0 and stderr is empty (`CREATE-FR-017`)
- [X] T015 [US1] Write failing tests for member coverage and naming in `tests/test_create.py`: a `PATH` naming a regular file contributes exactly one regular-file member; a `PATH` naming a directory contributes that directory plus every entry beneath it at every depth (`CREATE-FR-003`); member names are relative, `/`-separated, carry no leading `./`, no absolute component and **no trailing `/` even for directory members** — `tarfile.getnames()` returns `photos`, not `photos/` — and the operand spellings `photos`, `photos/` and `./photos` produce identical archives (`CREATE-FR-004`)
- [X] T016 [US1] Write failing tests for compression selection in `tests/test_create.py` using `create_support.is_gzip`: `.tar.gz` and `.tgz` names produce archives whose first two bytes are `\x1f\x8b`; `.tar`, `backup`, `data.bin` and `PHOTOS.TAR.GZ` produce archives that are not gzip, pinning the match as literal and case-sensitive (`CREATE-FR-005`, SC-007)
- [X] T017 [US1] Write failing tests for stored contents and directory members in `tests/test_create.py`: stored bytes are byte-for-byte identical to the source for a text file, a binary file and a zero-length file (`CREATE-FR-006`); a directory containing no files is recorded as a `DIRTYPE` member and does **not** count toward `N`, while a zero-length file **does** (`CREATE-FR-007`); the empty-directory-only case yields `created ARCHIVE with 0 files` and exit 0
- [X] T018 [US1] Write failing tests for ordering, de-duplication and self-exclusion in `tests/test_create.py`: members of one operand sorted by **full member name compared as text** — `d`, `d/a.txt`, `d/b`, `d/b/c.txt`, `d/empty`, `d/z.txt` in that order, which is what places a directory immediately before its contents; `PATH` operands contributing in the order given; the same unchanged tree with the same invocation producing an identical member sequence on a repeat run, independent of `os.scandir` order (`CREATE-FR-026`, SC-012); overlapping operands (`photos photos/a.jpg photos`) yielding each member exactly once, counted once, at the position the **first** operand earned it (`CREATE-FR-020`); and `create photos/all.tar photos` omitting `all.tar` from its own contents on **both** the first run and the `--overwrite` re-run where the archive really is present during the walk (`CREATE-FR-019`)
- [X] T019 [US1] Write failing tests for non-regular entries and hard links in `tests/test_create.py`: a symbolic link, a FIFO and a socket inside a named directory are not stored, each is named on stderr as `tarx: skipping non-regular path '{path}' ({label})` with the labels `symbolic link`, `FIFO`, `socket`, none counts toward `N`, and the exit status stays **0**; a `PATH` that names such an entry directly is skipped by the same rule and is not an error; a symbolic link is never dereferenced (the target's bytes do not appear in the archive); and two names for one inode are stored as **two** `REGTYPE` members, each of full size with its own copy of the contents, both counted in `N` (`CREATE-FR-015`)

### Implementation for User Story 1

- [X] T020 [US1] Implement `_classify_source(path)` in `src/tarx/core.py`: one `os.lstat` per entry, returning `KIND_FILE` for `stat.S_ISREG`, `KIND_DIR` for `stat.S_ISDIR`, and otherwise the skip label from T006. `lstat`, **not** `stat` — classifying a symbolic link as a link rather than as its target is what makes "symbolic links are not followed" true by construction. Hard-link detection is deliberately absent: a file carrying several names is a plain regular file here (FR-015, data-model.md → Classification of a source entry)
- [X] T021 [US1] Implement the recursive subtree collector in `src/tarx/core.py` (a helper of `validate_and_plan`) walking one operand with `os.scandir`, classifying each entry via T020, appending `PlannedMember`s to a per-operand list and non-regular entries to `plan.skipped`, and **omitting** any entry whose `os.path.normpath(os.path.abspath(path))` equals the same for `ARCHIVE` — an absolute-string comparison, so it works whether or not the archive exists yet, unlike `os.path.samefile` (FR-019, research.md §7)
- [X] T022 [US1] In `src/tarx/core.py`, sort each operand's collected list **once** by full member name as a Python string, then append to `plan.members`, skipping any name already present so the first operand to reach a name keeps its position. Sorting after full collection is what makes `os.scandir`'s reporting order irrelevant; do **not** use `os.walk` with `dirnames.sort()`, which emits a subdirectory's contents after all its siblings and would place `d/b/c.txt` after `d/z.txt` (FR-020, FR-026, research.md §6)
- [X] T023 [US1] Implement the happy path of `validate_and_plan(archive, paths, overwrite)` in `src/tarx/core.py`: compute the archive's absolute path once, iterate the `PATH` operands in the order given, derive each operand's member name with `_member_name` (T010), collect its subtree (T021–T022), and return `(plan, [])`. This function **writes nothing** — not one byte, not one directory (FR-016)
- [X] T024 [US1] Handle the operand that normalises to `"."` in `src/tarx/core.py`: contribute its entries under their plain relative names and **no** member for the operand itself, because FR-004 requires every member name to be a relative path with no leading `./` and `.` is not such a name. Do not refuse it — `.` does not resolve outside the current directory, so FR-014 does not reach it (research.md §5)
- [X] T025 [US1] Implement `write_archive(archive, plan)` in `src/tarx/core.py`: `tarfile.open(archive, _archive_mode(archive))`, then for each planned member in `plan.members` order build a `tarfile.TarInfo` **by hand** — setting `name`, `type` (`tarfile.REGTYPE` for files, `tarfile.DIRTYPE` for directories), `size`, `mode` and `mtime` — and write it with `addfile(info, fileobj)` for files and `addfile(info)` for directories. Do **not** call `TarFile.add()`: it keeps an inode cache and stores the second name of a hard-linked file as a zero-byte `LNKTYPE` member, which FR-015 forbids and which `001-tarx-cli`'s `extract` would silently skip (measured, research.md §4); it also appends a trailing `/` to directory names and re-`stat`s every entry
- [X] T026 [US1] Stream each regular file's bytes in `write_archive` in `src/tarx/core.py` by opening it and passing the file object to `addfile`, letting `tarfile`'s internal fixed-size buffer do the copying. Never read a whole file into memory and never build the archive in memory — measured peak additional allocation is 44 KiB for plain tar and 519 KiB for gzip on a 40 MB file, neither growing with file size (SC-010, research.md §9)
- [X] T027 [US1] Return `N` from `write_archive` in `src/tarx/core.py` as `sum(1 for m in plan.members.values() if m.kind == KIND_FILE)` — derived from the plan that was actually written, never counted independently, so the reported count cannot drift from what the archive holds (FR-008, SC-003)

**Checkpoint**: `create` fully works on valid input. US1's Independent Test passes end to end;
`python3 -m pytest tests/test_create.py` is green. This is the MVP — a user with only this can
already package their work.

---

## Phase 4: User Story 2 - Don't let a new archive destroy an old one (Priority: P2)

**Goal**: `create` never destroys what is already at `ARCHIVE` unless asked to, says what is in the
way, and distinguishes "re-run with `--overwrite`" (status 3) from "this path can never work"
(status 2).

**Independent Test**: Create an archive, run the identical command again and confirm it fails with
status 3, writes a diagnostic naming the archive, writes nothing to stdout and leaves the first
archive byte-for-byte unchanged; then re-run with `--overwrite` and confirm it succeeds and the
archive reflects the current source tree.

### Tests for User Story 2 ⚠️

> All land in `tests/test_create_overwrite.py`, so they are written in sequence. The `snapshot_tree`
> fixture from the untouched `tests/conftest.py` is what proves "byte-for-byte unchanged".

- [X] T028 [US2] Write failing tests for the refusal in `tests/test_create_overwrite.py`: with a regular file already at `ARCHIVE` and `--overwrite` absent, stderr is exactly `tarx: refusing to overwrite existing file '{archive}' (re-run with --overwrite)` (C3, wording shared verbatim with `001-tarx-cli`'s D10), stdout is empty, the exit status is **3**, and a `snapshot_tree` comparison before and after shows the existing file unchanged (`CREATE-FR-010`, SC-004)
- [X] T029 [US2] Write failing tests for the override in `tests/test_create_overwrite.py`: `--overwrite` replaces an existing archive with one holding the current contents of the named paths, writes the summary line and exits 0; a source tree changed since the previous run is reflected in the new archive, not the old one; and `--overwrite` with **nothing** at `ARCHIVE` behaves identically to omitting it (`CREATE-FR-011`)
- [X] T030 [US2] Write failing tests for type mismatch and missing parent in `tests/test_create_overwrite.py`: a directory, a symbolic link and a FIFO at `ARCHIVE` each produce `tarx: archive path '{archive}' exists but is not a regular file` (C4) with status **2**, identically with and without `--overwrite`, leaving the target untouched (`CREATE-FR-012`); `create backups/2026/photos.tar photos` with no `backups/2026` produces `tarx: cannot create archive 'backups/2026/photos.tar': directory 'backups/2026' does not exist` (C1) with status 2 and `backups` **not** created anywhere (`CREATE-FR-027`); and an `ARCHIVE` whose parent path exists but is not a directory produces `tarx: cannot create archive '{archive}': '{dir}' is not a directory` (C2) with status 2

### Implementation for User Story 2

- [X] T031 [US2] Implement `_check_archive_path(archive, overwrite)` in `src/tarx/core.py` returning **at most one** `Problem`, evaluated in exactly this order because a missing parent makes every other question moot: parent directory does not exist → C1, class 2; parent path exists but is not a directory → C2, class 2; a regular file exists at `ARCHIVE` and `--overwrite` was not given → C3, class **3**; `ARCHIVE` exists and is not a regular file (directory, symlink, FIFO, socket, device node) → C4, class 2; otherwise no problem. Reuse the existing `_is_real_dir` and `_is_real_file` helpers rather than re-implementing them, and create **no** directory under any circumstance (FR-010, FR-012, FR-027, data-model.md → State transitions of the archive path)
- [X] T032 [US2] Call `_check_archive_path` **first** inside `validate_and_plan` in `src/tarx/core.py`, before any operand is examined, so an archive-path problem is always reported ahead of any source-path problem (FR-018 ordering), and guarantee nothing opens, truncates or unlinks the file at `ARCHIVE` until `validate_and_plan` has returned an empty problem list — a run that fails for an unrelated reason leaves the previous archive intact (FR-011, US3 scenario 4)

**Checkpoint**: US1 and US2 both work independently. `python3 -m pytest tests/test_create.py
tests/test_create_overwrite.py` is green; zero pre-existing files are replaced without consent.

---

## Phase 5: User Story 3 - Get a clear failure and no half-made archive (Priority: P3)

**Goal**: Every failure `create` can detect is reported by name, reports **all** its problems at
once with the right status, and leaves the filesystem exactly as it was — no archive, no directory,
nothing to clean up and nothing to mistake for a result.

**Independent Test**: Run `create` in a clean directory with one good path and one misspelled path;
confirm the misspelled path is named on stderr, stdout is empty, the exit status is 2, and no file
exists at the archive path afterwards.

### Tests for User Story 3 ⚠️

> All land in `tests/test_create_errors.py`, so they are written in sequence.

- [X] T033 [US3] Write failing tests for a missing `PATH` in `tests/test_create_errors.py`: stderr carries `tarx: source path '{path}' does not exist` (C5) naming the operand exactly as typed, stdout is empty, the status is **2**, no archive exists afterwards, and any pre-existing file at `ARCHIVE` is unchanged; with several missing operands, **every** one is named, one per line, in operand order (`CREATE-FR-013`)
- [X] T034 [US3] Write failing tests for an unsafe `PATH` in `tests/test_create_errors.py`: an absolute operand (`/etc/hostname`) and one that escapes the directory (`../outside`) each produce `tarx: unsafe source path '{path}': resolves outside the current directory` (C6) with status **2** and no archive; and because C6 is checked **before** C5, an unsafe operand is reported as unsafe rather than as missing whether or not it exists (`CREATE-FR-014`)
- [X] T035 [US3] Write failing tests for an unreadable entry in `tests/test_create_errors.py`, **twice over** (research.md §8): a real `chmod 0o000` file inside a named directory producing `tarx: cannot read '{path}': Permission denied` (C7) with status 2 and no archive, marked `@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission bits")`; **and** always-running `monkeypatch`-injected `OSError` variants for both an unopenable regular file and an unlistable directory. The injected pair is what keeps this requirement genuinely covered in this repository's root test environment, where a permission-only test would pass vacuously (`CREATE-FR-021`, Constitution Principle III)
- [X] T036 [US3] Write failing tests for failures after writing has begun in `tests/test_create_errors.py`: a `monkeypatch`-injected `OSError` from `addfile` produces `tarx: failed while writing member '{name}' to archive '{archive}': {reason}` (C10) on stderr, **no** summary line on stdout, and status 2; an injected failure of the archive open produces `tarx: cannot create archive '{archive}': {reason}` (C9) with status 2. Assert that an incomplete archive is never reported as a success (`CREATE-FR-021`, Constitution Principle II)
- [X] T037 [US3] Write failing tests for multi-problem reporting and class precedence in `tests/test_create_errors.py`: all problems reported one per line in the documented order — archive-path problem first (at most one of C1–C4), then one source-path problem per operand in operand order, then C7 readability problems in plan order; and a run exhibiting both a refused overwrite **and** a missing `PATH` exits **2, not 3**, with the existing archive byte-for-byte unchanged even when `--overwrite` is given (`CREATE-FR-018`, SC-005, US3 scenario 4)
- [X] T038 [US3] Write failing tests for invalid invocations in `tests/test_create_errors.py`: `create` with no operands, `create out.tar` with no `PATH`, and `create out.tar photos --clobber` each produce argparse's own usage output on stderr with a non-zero status and **nothing read or written** (assert with `snapshot_tree` over the working directory); and an unrecognised command name is still rejected with a usage diagnostic, unchanged by this feature (`CREATE-FR-022`, `CREATE-FR-001`)
- [X] T039 [US3] Write the failing no-archive-left-behind sweep in `tests/test_create_errors.py`: parametrised across every detected-failure scenario above, assert stdout empty, stderr non-empty, no file at the archive path that was not there beforehand, and no directory created anywhere; plus a test proving validation traverses the **whole** tree before the archive is opened — inject the failure on the deepest file of a multi-level tree and assert the archive still does not exist (`CREATE-FR-016`, SC-006)

### Implementation for User Story 3

- [X] T040 [US3] Implement the per-operand check in `src/tarx/core.py` in exactly this order, with the first failure stopping the rest for that operand so one operand contributes at most one operand-level problem: **lexical safety** — reject when `os.path.isabs(given)`, or when `_member_name(given)` equals `".."` or starts with `"../"` → C6, class 2 (purely lexical, no `realpath`, so the verdict is a property of the operand rather than of whatever symlinks exist); then **existence** — reject when `os.path.lexists(given)` is false → C5, class 2 (`lexists`, not `exists`, so a dangling symbolic link counts as existing and is then skipped as non-regular rather than reported as missing). A failing operand contributes no members (FR-013, FR-014, data-model.md → SourceOperand validation rules)
- [X] T041 [US3] Add readability validation to the collector in `src/tarx/core.py`: an `os.scandir` failure on a directory and an `open(path, "rb")` failure on a planned regular file both become C7 `tarx: cannot read '{path}': {reason}`, class 2, with `{reason}` produced by the existing `_reason` helper (whitespace-collapsed, one problem per line). Every planned file is genuinely opened and closed during validation — **not** `os.access`-checked, which consults permission bits rather than attempting the operation and answers the wrong question for ACLs. Entries excluded by FR-019 are skipped before this check, avoiding a pointless open (FR-016, FR-021, research.md §8)
- [X] T042 [US3] Accumulate problems in `validate_and_plan` in `src/tarx/core.py` rather than returning at the first, and emit them in the documented deterministic order: archive-path problem, then source-path problems in operand order, then C7 problems in plan order (operand order outer, full-member-name order inner). Return them to `cli`, which collapses them to one status with the existing `resolve_exit_status` — already encoding "class 2 outranks class 3" (FR-018)
- [X] T043 [US3] Wrap the write phase in `src/tarx/core.py`: catch **only** `OSError` and `tarfile.TarError` — no bare `except`, nothing swallowed — and re-raise as `TarxError` with C9 (`tarx: cannot create archive '{archive}': {reason}`) for a failure of the open and C10 (`tarx: failed while writing member '{name}' to archive '{archive}': {reason}`) for a failure after writing began, both class 2. An incomplete archive may remain and is explicitly not rolled back; what must never happen is the summary line being printed, which T013 already guarantees by printing only after `core.create` returns (FR-021, Constitution Principle II)

**Checkpoint**: All three failure classes are distinguishable by status alone, every detected
failure leaves the filesystem untouched, and `python3 -m pytest tests/test_create.py
tests/test_create_overwrite.py tests/test_create_errors.py` is green.

---

## Phase 6: User Story 4 - Everything that worked before still works (Priority: P4)

**Goal**: `list` and `extract` are unchanged in every observable respect, and they read the archives
`create` produces.

**Independent Test**: Run the complete pre-existing test suite for `list` and `extract` unchanged
and confirm it passes; separately, create an archive with `create`, then `list` it and `extract` it
and compare the extracted tree against the original sources.

### Tests for User Story 4 ⚠️

> All land in `tests/test_create_roundtrip.py`, so they are written in sequence.

- [X] T044 [US4] Write failing round-trip tests in `tests/test_create_roundtrip.py`: for a known tree, `create` then `list` prints every member name one per line with **no** trailing slashes; `create` then `extract` into a fresh destination reproduces the tree with byte-identical file contents and an extracted count **equal** to the count `create` reported; exercised for both a plain `.tar` and a `.tar.gz` name, with zero differences in relative paths and zero differences in bytes (`CREATE-FR-009`, SC-001, SC-002, SC-003, SC-008)
- [X] T045 [US4] Write failing compression-interop tests in `tests/test_create_roundtrip.py`: a `create`-produced gzip archive is accepted by `list` and by `extract` with status 0 and empty stderr, because those commands detect compression from **content** (`001-tarx-cli` FR-004) while `create` selects it from the **name** (FR-005) — including the deliberate mismatch cases, a gzip archive named `.tgz` read fine and a plain archive named `PHOTOS.TAR.GZ` read fine (`CREATE-FR-009`)
- [X] T046 [US4] Write failing discoverability tests in `tests/test_create_roundtrip.py`: `python -m tarx --help` names `list`, `extract`, `create`, `ARCHIVE`, `DEST`, `PATH` and `--overwrite`; `python -m tarx create --help` names `ARCHIVE`, `PATH` and `--overwrite`; both write usage to **stdout** and exit **0** (`CREATE-FR-024`)
- [X] T047 [US4] Write failing behaviour-preservation tests in `tests/test_create_roundtrip.py`: `list` and `extract` keep the same operands and options, the same stdout content, the same diagnostics and the same exit statuses as before this feature — including that `extract` still skips `LNKTYPE` members unchanged, and that adding a third subcommand changed no `list`/`extract` output a caller could observe (`CREATE-FR-023`)
- [X] T048 [US4] Run the regression gate mechanically from `/root/sdd-study/runs/R035` and confirm both halves: `python3 -m pytest tests/test_list.py tests/test_extract.py tests/test_overwrite.py tests/test_validation.py tests/test_errors.py tests/test_traceability.py` passes with the T001 baseline count, **and** `git diff --stat -- tests/conftest.py tests/test_errors.py tests/test_extract.py tests/test_list.py tests/test_overwrite.py tests/test_traceability.py tests/test_validation.py` produces **no output**, proving not one pre-existing test was modified (SC-009)

**Checkpoint**: All four user stories are independently functional and the shipped behaviour of
`list` and `extract` is provably untouched.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The traceability audit, the scale and memory measurements, and the constitution gate —
each spanning all four stories.

- [X] T049 [P] Create `tests/test_create_traceability.py` implementing the FR-025 audit: parse only **requirement-definition** lines matching `^- \*\*FR-(\d{3})\*\*:` from `specs/002-create-command/spec.md` (anchoring on definition lines is what stops the spec's inline cross-references to `001-tarx-cli` FR-004/FR-017/FR-022 being mistaken for this feature's requirements), yielding exactly the 27 defined IDs; require each to appear somewhere in the `tests/` corpus as `CREATE-FR-###` or `create_fr_###` and fail with the **explicit list** of uncovered identifiers; and cross-check the requirement-to-test map in `specs/002-create-command/data-model.md` in **both** directions so the map cannot go stale. Add no `002` identifier to any `001-tarx-cli` document, which would break the pre-existing `tests/test_traceability.py` (`CREATE-FR-025`, SC-011, research.md §13)
- [X] T050 Add the SC-010 scale and memory checks to `tests/test_create.py`, both marked `@pytest.mark.slow` (the marker is already registered in `pyproject.toml`): 10,000 small files archived in under 10 seconds; and `tracemalloc` peak additional allocation around an in-process `create`, asserted under a single fixed 2 MiB ceiling at **two** different file sizes so that *growth*, not just magnitude, is what fails, for both the plain `w` and the `w:gz` mode. Reference measurements: 44 KiB and 519 KiB on a 40 MB file, against ~40 MB for a read-it-all-in implementation (SC-010, research.md §9)
- [X] T051 Review the new code in `src/tarx/core.py` and `src/tarx/cli.py` for docstrings and comments in the style the shipped `001-tarx-cli` code uses — citing the FR identifier and the C-template number each branch implements — and confirm the module seam still holds: `core.py` never prints and never calls `sys.exit`, `cli.py` holds no archive logic of its own
- [X] T052 [P] Walk every scenario in `specs/002-create-command/quickstart.md` by hand from a temporary directory with `PYTHONPATH=/root/sdd-study/runs/R035/src` and confirm each observed stdout, stderr and exit status matches the documented expectation, including the `test ! -e backups` and `test ! -e out.tar` checks and the `diff <(list once.tar) <(list twice.tar)` determinism check
- [X] T053 [P] Run the constitution gate from `/root/sdd-study/runs/R035`: `python3 -m pytest` fully green (Principle III, workflow gate 4); `grep -rn "^import \|^from " src/tarx/` showing every imported name is standard library — `tarfile`, `os`, `os.path`, `stat`, `argparse`, `sys` (Principle I); and `grep -n "dependencies" pyproject.toml` still showing `dependencies = []`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Setup — **blocks all four user stories**
- **User Story 1 (Phase 3)**: depends on Foundational only
- **User Story 2 (Phase 4)**: depends on Foundational only; its tests assert a successful
  `--overwrite` run, so they are *fully* green only once US1's write phase exists
- **User Story 3 (Phase 5)**: depends on Foundational only; its "no archive left behind" assertions
  are strongest once US1 exists to leave one behind
- **User Story 4 (Phase 6)**: depends on US1 (there must be an archive to round-trip) and, for the
  mismatch cases, on US2's `--overwrite` path
- **Polish (Phase 7)**: T049 depends on all four stories' tests existing; T050–T053 depend on the
  stories being complete

### User Story Dependencies

- **US1 (P1)** — independent. The MVP.
- **US2 (P2)** — the archive-path state machine is self-contained (T031–T032 touch only
  `validate_and_plan`'s first step); it is *demonstrated* through US1's write phase.
- **US3 (P3)** — the operand and readability checks are self-contained (T040–T042); the mid-write
  wrapper (T043) wraps US1's `write_archive`.
- **US4 (P4)** — adds no runtime code of its own beyond T012's help text; it verifies US1–US3
  against the pre-existing commands.

### Within Each User Story

- Tests are written **first** and must **fail** before the implementation tasks begin
- Classification before collection, collection before sorting, sorting before writing
- Validation complete before the archive is opened — this is FR-016 and a hard ordering constraint,
  not a preference: `tarfile.open(path, "w")` creates the file at open time (measured,
  research.md §3), so a single early write would make "creates no archive" unachievable
- Each story complete and its checkpoint validated before moving to the next priority

### Parallel Opportunities

- **Phase 1**: T002 and T003 run in parallel (both read-only, different files)
- **Phase 2**: three independent file tracks — T004→T005 (`tests/create_support.py`),
  T006→T007→T008→T009→T010→T011 (`src/tarx/core.py`), and T012→T013 (`src/tarx/cli.py`) — so
  T004, T006 and T012 can start together
- **Across stories**: once Phase 2 completes, the four story phases touch four different new test
  files (`test_create.py`, `test_create_overwrite.py`, `test_create_errors.py`,
  `test_create_roundtrip.py`), so four developers can write tests concurrently. Their
  implementation tasks all land in `src/tarx/core.py` and must be serialised there.
- **Phase 7**: T049, T052 and T053 run in parallel (new file, manual walkthrough, read-only checks)
- **Within a story**: the test tasks are **not** parallel with each other — every story's tests
  share one file

---

## Parallel Example: Phase 2 Foundational

```bash
# Three file tracks, three agents, no conflicts:
Task: "T004 Create tests/create_support.py with build_tree and work_in"
Task: "T006 Add GZIP_SUFFIXES and the source-entry label vocabulary to src/tarx/core.py"
Task: "T012 Add the create subparser to build_parser() in src/tarx/cli.py"
```

## Parallel Example: four stories' tests at once

```bash
# After Phase 2, four different new test files:
Task: "T014-T019 [US1] tests/test_create.py"
Task: "T028-T030 [US2] tests/test_create_overwrite.py"
Task: "T033-T039 [US3] tests/test_create_errors.py"
Task: "T044-T047 [US4] tests/test_create_roundtrip.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup — baseline recorded (T001–T003)
2. Phase 2: Foundational — **blocks everything** (T004–T013)
3. Phase 3: User Story 1 (T014–T027)
4. **STOP and VALIDATE**: `python3 -m pytest tests/test_create.py` green; run quickstart
   Scenario 1 by hand
5. Demo: `python -m tarx create photos.tar.gz photos` → `created photos.tar.gz with 2 files`

At this point `create` packages files and folders correctly, deterministically and without holding
file contents in memory. It does not yet refuse to clobber an existing archive, so it is a demo,
not a release.

### Incremental Delivery

1. Setup + Foundational → `create --help` works, helpers import
2. **+ US1** → packaging works (MVP; validate, demo)
3. **+ US2** → safe to use from a script; nothing gets destroyed by a mistyped name
4. **+ US3** → every failure is loud, complete and leaves nothing behind. **This is the first
   releasable point** — Constitution Principle II is not satisfied until US3's diagnostics exist
5. **+ US4** → round-trip and regression proof; `list`/`extract` demonstrably unchanged
6. **+ Polish** → traceability audit, scale and memory measurements, constitution gate. Workflow
   gate 4 requires the full suite green and every requirement covered before this feature is done

### Parallel Team Strategy

1. The whole team completes Phase 1 + Phase 2 together (it is short and everything depends on it)
2. Then, with one owner per new test file:
   - Developer A: US1 (`test_create.py`) — also the critical path, since US2–US4 demonstrate
     through its write phase
   - Developer B: US2 (`test_create_overwrite.py`)
   - Developer C: US3 (`test_create_errors.py`)
   - Developer D: US4 (`test_create_roundtrip.py`)
3. Serialise the `src/tarx/core.py` edits behind A, in story-priority order
4. Reconvene for Phase 7

---

## Notes

- `[P]` means different files and no dependency on an incomplete task
- `[Story]` maps a task to its user story for traceability; Setup, Foundational and Polish carry no
  story label by design
- Verify each test fails before implementing the behaviour it describes (Principle III: a
  requirement "covered" by a test that cannot fail is not covered — see T035, where a
  permission-only test would pass vacuously under root)
- Commit after each task or logical group; stop at any checkpoint to validate a story on its own
- Two accepted limits are recorded in [plan.md](./plan.md#constitution-check) and must not be
  "fixed" silently: an incomplete archive may remain after a genuine mid-write failure (FR-021),
  and plan memory is O(number of entries) (a joint consequence of FR-016, FR-020 and FR-026). File
  *contents* are never held — that is what SC-010 measures
- Avoid: calling `TarFile.add()` (FR-015), using `os.walk` for collection ordering (FR-026),
  `os.access` for readability (FR-021), `stat` instead of `lstat` (FR-015), writing to a temporary
  sibling and renaming (FR-027), creating any directory (FR-027), and modifying any pre-existing
  file under `tests/` (SC-009)
