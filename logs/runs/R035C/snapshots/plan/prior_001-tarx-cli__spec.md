# Feature Specification: Tar Archive Listing and Extraction CLI

**Feature Branch**: `001-tarx-cli`

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "Build a command-line tool for listing and extracting tar archives. Run it as `python -m tarx COMMAND ...` with two commands: `list ARCHIVE` prints the name of every member of the archive, one per line, in the order they appear in the archive; `extract ARCHIVE DEST [--overwrite]` extracts the archive's files and directories into the directory DEST, keeping their relative paths and file contents, then prints `extracted N files` to standard output, where N is the number of regular files written. Both plain tar archives (`.tar`) and gzip-compressed tar archives (`.tar.gz` or `.tgz`) must work. Existing files are never overwritten unless `--overwrite` is given; a would-be overwrite without the flag fails with exit status 3 and an error message on standard error. If ARCHIVE does not exist or is not a valid tar archive, the command prints an error message to standard error and exits with status 2. Successful commands exit with status 0. Use Python 3.11 or newer and the standard library only. Put the code in a package named `tarx` under `src/`, so that it runs with `python -m tarx` when `src/` is on `PYTHONPATH`."

## Clarifications

### Session 2026-11-19

- Q: If `extract` has already started writing files and then hits an unexpected error (disk full, permission revoked mid-run), must it undo the files it already wrote, or is pre-write validation enough? → A: Validate everything before the first write; no post-write rollback. An interrupted write exits 2 with a diagnostic and may leave partial files, which the spec states explicitly rather than promising atomicity it cannot keep under `--overwrite`.
- Q: What should happen when an archive member's type disagrees with what already exists at its destination path — a file where a directory exists, or a directory where a file exists? → A: Always a hard failure: no files written, the offending path named on standard error, exit 2, with or without `--overwrite`. Overwrite consents only to replacing a regular file, so exit 3 ("re-run with `--overwrite`") would be false advice here.
- Q: When `list` prints a directory member, should the name end with a trailing slash (`photos/`) or not (`photos`)? → A: No trailing slash — every line is a plain relative path, so output pipes directly into other commands without post-processing.
- Q: When the pre-write check finds more than one problem in the same archive, should the tool report every problem or just the first, and which exit status wins? → A: Report every problem found, one per line on standard error; status 2 (unusable input: unsafe path, type mismatch) takes precedence over status 3 (refused overwrite), since an unsafe archive cannot be fixed by passing `--overwrite`.
- Q: When exactly one file is extracted, should the summary read `extracted 1 files` or `extracted 1 file`? → A: Always the literal template `extracted N files`, plural regardless of N, so the line's shape never varies for a script parsing it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect what is inside an archive (Priority: P1)

Someone has a tar archive in front of them — plain or gzip-compressed — and wants to know what it contains before doing anything with it. They run the tool's `list` command against the archive and get back the name of every member, one per line, in the same order the archive stores them.

**Why this priority**: This is the smallest slice that delivers standalone value and it is safe by construction — it reads an archive and writes nothing to disk. A user who has only this capability already has a usable archive inspector, and it exercises both archive formats end to end.

**Independent Test**: Create a plain archive and a gzip-compressed archive with known members in a known order, run `list` on each, and confirm the output is exactly those member names, one per line, in that order, with exit status 0 and nothing on standard error.

**Acceptance Scenarios**:

1. **Given** a plain tar archive containing `photos/a.jpg` and `photos/b.jpg` in that order, **When** the user runs `list` on it, **Then** standard output is the two names on separate lines in that order and the exit status is 0.
2. **Given** a gzip-compressed tar archive with the same two members, **When** the user runs `list` on it, **Then** the output is identical to the plain-archive case.
3. **Given** an archive that contains directory members as well as file members, **When** the user runs `list`, **Then** every member is listed, including the directories, in archive order, and each directory name appears without a trailing slash.
4. **Given** an archive with no members, **When** the user runs `list`, **Then** standard output is empty and the exit status is 0.

---

### User Story 2 - Extract an archive into a destination directory (Priority: P2)

Someone wants the contents of an archive as real files on disk. They run the tool's `extract` command with the archive and a destination directory. The archive's files and directories appear under that destination with their relative paths intact and their contents unchanged, and the tool reports how many files it wrote. Nothing that already exists on disk is disturbed: if the extraction would replace an existing file, it refuses rather than destroying data.

**Why this priority**: This is the primary reason the tool exists, but it builds on the archive-reading capability proven by User Story 1. Delivered on its own it is already safe, because the refuse-rather-than-replace behaviour is part of this slice; the opt-in override is a separate increment.

**Independent Test**: Extract a known archive into a fresh empty destination, then compare the resulting tree against the known contents file by file, and confirm the summary line and exit status 0.

**Acceptance Scenarios**:

1. **Given** an archive containing `photos/a.jpg` and `photos/b.jpg` and a destination `out` that does not exist, **When** the user runs `extract`, **Then** `out/photos/a.jpg` and `out/photos/b.jpg` exist with byte-identical contents, standard output is `extracted 2 files`, and the exit status is 0.
2. **Given** an archive containing nested directories, **When** the user runs `extract`, **Then** the directory structure under the destination mirrors the relative paths in the archive.
3. **Given** a gzip-compressed archive, **When** the user runs `extract`, **Then** the result is the same as for the equivalent plain archive.
4. **Given** a destination that already contains an unrelated file not present in the archive, **When** the user runs `extract`, **Then** that file is left untouched and the extraction succeeds.
5. **Given** an archive whose contents include a file that already exists at the destination path, **When** the user runs `extract` without the overwrite option, **Then** no files are written at all, an error message naming the conflicting path is written to standard error, and the exit status is 3.
6. **Given** an archive with no members, **When** the user runs `extract`, **Then** standard output is `extracted 0 files` and the exit status is 0.
7. **Given** an archive containing exactly one regular file, **When** the user runs `extract`, **Then** standard output is `extracted 1 files` — the wording does not change for a count of one — and the exit status is 0.

---

### User Story 3 - Deliberately replace existing files (Priority: P3)

Someone has already extracted an archive once, or has files at the destination from another source, and now wants the archive's versions to win. They re-run `extract` with the overwrite option and the existing files are replaced.

**Why this priority**: It is an opt-in convenience layered on top of User Story 2. Without it the tool is still correct and safe; with it, repeat extraction and refresh workflows become possible.

**Independent Test**: Extract an archive into a destination twice in a row — the second time with the overwrite option — and confirm the second run succeeds, reports the same file count, and leaves the files matching the archive.

**Acceptance Scenarios**:

1. **Given** a destination already holding the result of a previous extraction, **When** the user runs `extract` with the overwrite option, **Then** the existing files are replaced with the archive's contents, standard output reports the full file count, and the exit status is 0.
2. **Given** an existing destination file whose contents differ from the archive's version of the same path, **When** the user runs `extract` with the overwrite option, **Then** that file's contents afterwards match the archive's version exactly.
3. **Given** a destination with no conflicting files, **When** the user runs `extract` with the overwrite option, **Then** the behaviour is identical to running it without the option.

---

### User Story 4 - Get a clear, actionable failure instead of a surprise (Priority: P4)

Someone mistypes an archive path, points the tool at a file that is not a tar archive, or asks for a command the tool does not have. In every case they get a specific message on standard error saying what was wrong, a documented non-zero exit status their scripts can branch on, and no half-finished mess on disk.

**Why this priority**: Correct behaviour on the happy paths comes first, but a tool used in scripts is only trustworthy if its failures are loud, specific, and distinguishable. This slice hardens every path delivered by the stories above.

**Independent Test**: Drive each failure mode — missing archive, non-archive file, unknown command, missing operand, destination that is not a directory, member path escaping the destination, existing entry of the wrong type — and assert on the exit status, the presence of a message on standard error, the emptiness of standard output, and the absence of any new files at the destination.

**Acceptance Scenarios**:

1. **Given** an archive path that does not exist, **When** the user runs either command, **Then** an error message naming the path is written to standard error, standard output is empty, and the exit status is 2.
2. **Given** a file that exists but is not a tar archive, **When** the user runs either command, **Then** an error message is written to standard error and the exit status is 2.
3. **Given** a corrupt or truncated archive, **When** the user runs `extract`, **Then** an error message is written to standard error, the exit status is 2, and the destination is left without a partially extracted tree.
4. **Given** an archive containing a member whose path would place it outside the destination directory, **When** the user runs `extract`, **Then** no files are written, an error message naming the offending member is written to standard error, and the exit status is 2.
5. **Given** an unknown command name or a missing required operand, **When** the user invokes the tool, **Then** a usage message is written to standard error, the exit status is non-zero, and nothing is read or written beyond that.
6. **Given** a destination where a directory already occupies the path of a member stored as a regular file (or vice versa), **When** the user runs `extract` — with or without the overwrite option — **Then** no files are written, the offending path is named on standard error, and the exit status is 2.

---

### Edge Cases

- **Empty archive**: `list` produces no output; `extract` produces `extracted 0 files`. Both exit 0.
- **Compression that disagrees with the file extension**: a gzip-compressed archive named `.tar`, or a plain archive named `.tar.gz`, is handled by its actual content rather than its name.
- **Member path escaping the destination**: a member stored with an absolute path or with `..` segments that resolve outside the destination is refused; the whole command fails before anything is written.
- **Destination exists but is not a directory**: the command fails with a diagnostic rather than clobbering the existing file.
- **Destination does not exist**: it is created, including any missing parent directories.
- **Directory already present at the destination**: reusing an existing directory is not a conflict; the only overwrite conflict is an existing regular file that a file member would replace. A path occupied by the wrong kind of entry is a separate failure, below.
- **Several problems in one archive**: all of them are reported, one per line on standard error, and the exit status is 2 if any unusable-input problem is among them, otherwise 3.
- **Existing entry of the wrong type**: a member's path already occupied by the opposite kind of thing — a directory where the archive has a file, or a file where the archive has a directory — fails with status 2 before anything is written, with or without `--overwrite`. This includes a file sitting where a member's parent directory needs to be.
- **Members that are neither regular files nor directories** (symbolic links, hard links, device nodes, FIFOs): they are not extracted, each one is named on standard error so the user knows it was skipped, and they do not count toward the reported file total.
- **Duplicate member names within one archive**: the archive's own order decides; the later member wins at the destination, and `list` shows the name as many times as it appears.
- **Overwrite conflict detected mid-archive**: the destination is left exactly as it was — the conflict is detected before any file is written, not after some have been.
- **Filesystem error after writing has begun** (disk full, permission revoked, destination removed mid-run): the run fails loudly with a diagnostic naming the member being written and exits 2, with no summary line on standard output. Files written before the error remain on disk; the tool does not roll back.
- **Zero-length files in the archive**: created as empty files and counted in the reported total.
- **A count of exactly one**: the summary stays `extracted 1 files`; the line is a fixed template for scripts, not prose.
- **Non-ASCII member names**: listed and extracted using the names recorded in the archive.
- **Very large archive**: contents are processed without requiring the whole archive to be held in memory at once.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST expose exactly two commands, `list` and `extract`, selected by the first operand, and MUST reject any other command name with a usage diagnostic.
- **FR-002**: `list ARCHIVE` MUST write the name of every member of the archive to standard output, one name per line, in the order the members appear in the archive.
- **FR-003**: `list` MUST include members of every type — regular files, directories, and any other member type the archive records — without filtering or reordering. The exact form of each printed name is specified by FR-024.
- **FR-004**: Both commands MUST accept uncompressed tar archives and gzip-compressed tar archives, and MUST determine which one they have been given from the archive's content rather than from its filename or extension.
- **FR-005**: `extract ARCHIVE DEST` MUST write the archive's regular-file and directory members beneath `DEST`, reproducing each member's archive-relative path.
- **FR-006**: Each extracted regular file's contents MUST be byte-for-byte identical to the contents stored in the archive.
- **FR-007**: `extract` MUST create `DEST`, including any missing parent directories, when it does not already exist, and MUST reuse it when it is an existing directory.
- **FR-008**: On success, `extract` MUST write the single line `extracted N files` to standard output, where `N` is the count of regular files it wrote, and MUST write nothing else to standard output. The wording MUST NOT vary with `N`: the word `files` stays plural for every count, including 0 and 1.
- **FR-009**: Without `--overwrite`, if any member of the archive would replace an existing regular file under `DEST`, `extract` MUST write no files at all, MUST write an error message to standard error identifying every such conflicting path — one per line — and MUST exit with status 3.
- **FR-010**: With `--overwrite`, `extract` MUST replace existing regular files at conflicting destination paths with the archive's versions, and MUST count every regular file it writes — replaced or new — in `N`.
- **FR-011**: An existing directory at a path where the archive stores a directory MUST NOT be treated as a conflict under either overwrite setting. Paths where the existing entry and the member disagree in type are governed by FR-023 instead.
- **FR-012**: When `ARCHIVE` does not exist or cannot be opened for reading, either command MUST write an error message identifying the path to standard error and exit with status 2.
- **FR-013**: When `ARCHIVE` exists but is not a readable tar archive — wrong format, corrupt, or truncated — either command MUST write an error message to standard error and exit with status 2.
- **FR-014**: `extract` MUST refuse any archive containing a member whose destination path resolves outside `DEST` — including absolute paths and paths with upward-traversing segments — by writing no files, naming every offending member on standard error, and exiting with status 2.
- **FR-015**: `extract` MUST NOT create members that are neither regular files nor directories; each such member MUST be named on standard error as skipped and MUST NOT be counted in `N`, and its presence alone MUST NOT cause a non-zero exit status.
- **FR-016**: Every command that completes its requested work MUST exit with status 0; command results MUST go only to standard output and diagnostics only to standard error.
- **FR-017**: Invalid invocations — unknown command, missing required operand, unrecognised option — MUST produce a usage diagnostic on standard error, a non-zero exit status, and no reads or writes of archive or destination paths.
- **FR-018**: An archive with no members MUST be handled as a success: `list` writes nothing, `extract` writes `extracted 0 files`, and both exit 0.
- **FR-019**: When `DEST` exists but is not a directory, `extract` MUST write an error message to standard error, exit with status 2, and leave the existing path untouched.
- **FR-020**: `extract` MUST complete every check it is capable of making — archive readability and format, destination type, member path safety, and overwrite conflicts across the whole archive — before writing the first file, so that any failure the tool detects leaves the destination exactly as it was and a rejected run is never mistaken for a partial success.
- **FR-021**: Every functional requirement in this section MUST be covered by at least one automated test that fails when the requirement is unmet, with the covering test traceable to the requirement identifier.
- **FR-022**: If an unexpected filesystem error — exhausted disk space, a revoked permission, a vanished destination — interrupts `extract` after writing has begun, the tool MUST write a diagnostic naming the member it was writing to standard error, MUST NOT write the `extracted N files` summary to standard output, and MUST exit with status 2. Files already written MAY remain; the tool does not attempt to undo them.
- **FR-023**: When an existing entry under `DEST` disagrees in type with the member that would occupy its path — the archive stores a regular file where a directory exists, or a directory where a regular file or other non-directory entry exists — `extract` MUST write no files, MUST name every offending path on standard error, and MUST exit with status 2. This applies identically with and without `--overwrite`, which consents only to replacing an existing regular file with a regular file.
- **FR-024**: Each name `list` prints MUST be the member's archive-relative path with no trailing slash, including for directory members, so that every output line is directly usable as a path.
- **FR-025**: When the pre-write validation finds multiple problems, `extract` MUST report all of them on standard error, one per line, rather than stopping at the first. When the problems span both failure classes, the exit status MUST be 2: unusable input (unsafe member path per FR-014, type mismatch per FR-023, unusable archive or destination) takes precedence over a refused overwrite (FR-009), because status 3 would wrongly imply that `--overwrite` makes the run succeed.

### Key Entities

- **Archive**: the input file named by `ARCHIVE`. Holds an ordered sequence of members and may be stored uncompressed or gzip-compressed. Read-only in every operation.
- **Member**: one entry in an archive. Has a name that doubles as its archive-relative path, a type (regular file, directory, or other), and — for regular files — contents. Order within the archive is significant and observable.
- **Destination directory**: the directory named by `DEST` under which extracted members are placed. May exist or not before the command runs; its pre-existing contents are never modified except as permitted by the overwrite setting.
- **Exit status**: the tool's machine-readable outcome — 0 for success, 3 for a refused overwrite, 2 for an unusable archive, destination, member path, or invocation. Exactly one status is reported per run; when an archive exhibits problems of both non-zero classes, 2 wins over 3.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can see the complete member list of either archive format with one command and no options, and 100% of the archive's members appear in the output in archive order.
- **SC-002**: For any archive in either format, an extracted tree compared against the archive's original contents shows zero differences in relative paths and zero differences in file bytes.
- **SC-003**: The file count the tool reports after extraction matches the number of regular files actually present from that run, in 100% of runs.
- **SC-004**: Across every collision scenario exercised, the number of pre-existing files modified without the overwrite option being given is zero.
- **SC-005**: Each of the three documented outcomes — success, refused overwrite, unusable input — is distinguishable by exit status alone, with no overlap, in 100% of trials, including archives that exhibit more than one problem at once.
- **SC-006**: Every failing run writes at least one non-empty diagnostic to standard error and writes nothing to standard output; and for every failure the tool detects by validation — unusable archive, unusable destination, unsafe member path, refused overwrite — zero files are left behind at the destination.
- **SC-007**: Every functional requirement is traceable to at least one automated test that fails when that requirement is violated, with no requirement left uncovered.
- **SC-008**: Listing a 10,000-member archive completes in under 5 seconds, and extracting an archive larger than available memory completes successfully.
- **SC-009**: A new user can discover both commands, their operands, and the overwrite option from the tool's own usage output without consulting external documentation.

## Assumptions

### Behavioural defaults chosen where the description was silent

- **Conflict detection precedes writing**: the entire archive is checked for overwrite conflicts and unsafe member paths before the first file is written, so a rejected extraction leaves the destination untouched. The alternative — writing until a conflict is hit — would leave partial results behind and was rejected.
- **Validation, not rollback, is the safety mechanism**: every failure the tool can anticipate is caught by the pre-write validation above, so in practice a failed run writes nothing. Guaranteeing atomicity against *unexpected* filesystem errors as well would require staging every member elsewhere and moving it into place, and under `--overwrite` no amount of deleting can restore a file that was already replaced — a best-effort cleanup would risk deleting the user's data to tidy up after itself. The simpler design was chosen and its limit is stated in FR-022 rather than hidden.
- **Format detection by content**: compression is detected from the archive's bytes, not its extension, so misnamed archives still work. The extensions `.tar`, `.tar.gz`, and `.tgz` are therefore descriptive rather than load-bearing.
- **Destination creation**: a missing `DEST` is created rather than being treated as an error, matching the worked example in the feature description where `out` does not exist beforehand.
- **Non-regular members are skipped, loudly**: the description scopes extraction to "files and directories", so links, device nodes, and FIFOs are not created. Each skip is reported on standard error so the outcome is never silent, but a skip is not a failure.
- **Member path safety**: archives whose members would write outside `DEST` are refused outright rather than sanitised, and the refusal uses status 2 because such an archive is unusable input for this tool. This applies with and without `--overwrite`.
- **Usage errors use status 2**: the description assigns 0, 2, and 3 but does not cover malformed invocations. They share status 2 with other unusable input, following the common convention for command-line usage errors.
- **Metadata is not preserved**: the description requires relative paths and file contents. Restoring permissions, ownership, and timestamps from the archive is therefore out of scope; extracted files get ordinary defaults.
- **Overwrite scope**: `--overwrite` governs replacement of existing regular files with regular files only. It never removes directories, never resolves a type mismatch (FR-023), and never deletes destination files that the archive does not contain — extraction merges into the destination rather than replacing it wholesale.
- **Type mismatches are unusable input, not refused overwrites**: status 3 exists to tell the user "re-run with `--overwrite`". For a path where a directory blocks a file or a file blocks a directory, that advice would be wrong, so these use status 2. Deleting the existing entry to force the archive's version through was rejected as data loss the user never asked for.
- **Duplicate member names** within one archive are extracted in archive order, so the last occurrence is what remains on disk.
- **Single-archive invocations**: each command operates on exactly one archive; globs, multiple archives, and member-selection filters are out of scope.

### Constraints given by the requester

These were stated in the feature description and are recorded here so planning honours them; they are implementation constraints rather than user-facing requirements.

- The tool is invoked as `python -m tarx COMMAND ...`.
- Python 3.11 or newer, standard library only — no third-party runtime dependencies. This matches Constitution Principle I.
- The code lives in a package named `tarx` under `src/`, runnable via `python -m tarx` with `src/` on `PYTHONPATH`.

### Environment assumptions

- The user has read permission on the archive and write permission on the destination's parent; permission failures surface as unusable-input diagnostics.
- Archives come from the local filesystem; fetching archives over a network is out of scope.
- The terminal or consuming script treats standard output and standard error as separate streams, which is what makes the stdout/stderr split above useful.
