# Feature Specification: Tar Archive List & Extract CLI

**Feature Branch**: `001-tar-archive-cli`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "Build a command-line tool for listing and extracting tar archives. Run it as `python -m tarx COMMAND ...` with two commands: `list ARCHIVE` prints the name of every member of the archive, one per line, in the order they appear in the archive; `extract ARCHIVE DEST [--overwrite]` extracts the archive's files and directories into the directory DEST, keeping their relative paths and file contents, then prints `extracted N files`. Both plain tar (`.tar`) and gzip-compressed tar (`.tar.gz`, `.tgz`) must work. Existing files are never overwritten unless `--overwrite` is given; an overwrite conflict without `--overwrite` fails with exit status 3 and an error on stderr. A missing or invalid archive prints an error to stderr and exits 2. Success exits 0. Python 3.11+, standard library only, package `tarx` under `src/`."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect what an archive contains (Priority: P1)

Someone has a tar archive and wants to know what is inside it before committing to unpacking it. They run the tool's `list` command with the archive path and get a plain, one-name-per-line listing of every entry in the archive, in the same order the archive stores them, so the output can be read directly or piped into other text tools.

**Why this priority**: This is the smallest slice that delivers standalone value and depends on nothing else. Being able to see inside an archive is useful on its own, even if extraction is never implemented.

**Independent Test**: Create an archive with known members in a known order, run the `list` command against it, and confirm stdout contains exactly those member names, one per line, in that order, with exit status 0. No extraction behavior is required.

**Acceptance Scenarios**:

1. **Given** an uncompressed archive `photos.tar` containing members `photos/a.jpg` then `photos/b.jpg`, **When** the user runs the list command on it, **Then** stdout is exactly `photos/a.jpg` and `photos/b.jpg` on separate lines, in that order, and the exit status is 0.
2. **Given** a gzip-compressed archive `photos.tar.gz` with the same two members, **When** the user runs the list command on it, **Then** the output and exit status are identical to the uncompressed case.
3. **Given** an archive containing both directory entries and file entries, **When** the user runs the list command, **Then** every entry in the archive is printed, including the directory entries, in archive order.
4. **Given** an archive with no members, **When** the user runs the list command, **Then** nothing is printed to stdout and the exit status is 0.

---

### User Story 2 - Unpack an archive into a chosen directory (Priority: P2)

Someone wants the contents of an archive placed on disk under a directory they name. They run the `extract` command with the archive and a destination directory; the archive's files and directories are recreated under that destination with their relative paths and contents intact, and the tool reports how many regular files it wrote.

**Why this priority**: This is the primary purpose of the tool, but it builds on being able to read an archive (P1). It is independently valuable and independently testable once reading works.

**Independent Test**: Create an archive with known files, contents, and nested directories; extract it into an empty destination; confirm every file exists at the expected relative path with byte-identical contents, that the summary line reports the correct count, and that the exit status is 0.

**Acceptance Scenarios**:

1. **Given** an archive containing `photos/a.jpg` and `photos/b.jpg` and a destination `out` that does not exist, **When** the user runs the extract command, **Then** `out/photos/a.jpg` and `out/photos/b.jpg` exist with contents byte-identical to the archived files, stdout is exactly `extracted 2 files`, and the exit status is 0.
2. **Given** a gzip-compressed archive with the same contents, **When** the user runs the extract command, **Then** the resulting files, the summary line, and the exit status are identical to the uncompressed case.
3. **Given** an archive containing nested directories several levels deep, including a directory with no files in it, **When** the user runs the extract command, **Then** the full directory structure is recreated under the destination and the reported count includes only regular files, not directories.
4. **Given** an archive with no members and an empty destination, **When** the user runs the extract command, **Then** stdout is exactly `extracted 0 files` and the exit status is 0.
5. **Given** a destination directory that already contains unrelated files, **When** the user extracts an archive whose member paths do not collide with them, **Then** the unrelated files are left untouched and extraction succeeds.

---

### User Story 3 - Never clobber existing files by accident (Priority: P3)

Someone extracts into a directory that already holds output from an earlier extraction. By default the tool refuses rather than silently replacing their files: it reports the conflict on stderr and exits with the distinct status 3, leaving the existing files as they were. When they genuinely want to refresh the contents, they re-run with `--overwrite` and the existing files are replaced.

**Why this priority**: It protects against data loss and gives scripts a distinct signal to branch on, but the tool is already useful for fresh extractions without it.

**Independent Test**: Extract an archive into a destination twice. The second run must fail with exit status 3, print a diagnostic on stderr, and leave the previously extracted files unmodified. Repeat the second run with `--overwrite` and confirm it succeeds, replaces the file contents, and reports the full count.

**Acceptance Scenarios**:

1. **Given** a destination already containing a file at a path the archive would write, **When** the user runs the extract command without `--overwrite`, **Then** a diagnostic naming the conflicting path is written to stderr, the exit status is 3, and no file under the destination has been created or modified.
2. **Given** the same situation, **When** the user runs the extract command with `--overwrite`, **Then** the existing file's contents are replaced with the archived contents, stdout is exactly `extracted N files` counting every regular file written, and the exit status is 0.
3. **Given** a destination that already contains some but not all of the archive's files, **When** the user runs the extract command without `--overwrite`, **Then** the command fails with exit status 3 and the files the archive would otherwise have added are not created.
4. **Given** a destination where a directory already exists at a path the archive also stores as a directory, **When** the user runs the extract command without `--overwrite`, **Then** this is not treated as a conflict and extraction proceeds.

---

### User Story 4 - Clear, scriptable failure for unusable input (Priority: P4)

Someone points the tool at a path that does not exist, is not readable, or is not a tar archive at all. Instead of a stack trace or a silent empty result, they get a short message on stderr that names the offending path and the reason, and a non-zero exit status their script can act on.

**Why this priority**: Both earlier commands need this to be trustworthy in scripts, but it is a cross-cutting hardening slice rather than a new capability.

**Independent Test**: Run each command against a nonexistent path, a directory, and a file of random bytes. Each run must print a diagnostic on stderr, print nothing on stdout, and exit with status 2.

**Acceptance Scenarios**:

1. **Given** a path that does not exist, **When** the user runs either command on it, **Then** stderr contains a message naming that path, stdout is empty, and the exit status is 2.
2. **Given** a file whose contents are not a valid tar archive, **When** the user runs either command on it, **Then** stderr contains a message naming that path and indicating it is not a valid archive, stdout is empty, and the exit status is 2.
3. **Given** a valid archive but a destination path that already exists as a regular file, **When** the user runs the extract command, **Then** stderr contains a message naming the destination, no extraction occurs, and the exit status is 2.
4. **Given** no command, an unrecognized command, or a missing required argument, **When** the user invokes the tool, **Then** usage guidance is written to stderr and the exit status is non-zero.

---

### Edge Cases

- **Archive order vs. sorted order**: members are reported and extracted in the order recorded in the archive; no sorting or de-duplication is applied.
- **Duplicate member names**: if an archive stores the same path twice, the later entry's contents end up on disk, and the overwrite rule is evaluated against the pre-existing state of the destination, not against files written earlier in the same run. The reported count counts files written, so a duplicated path contributes once.
- **Empty archive**: list prints nothing; extract prints `extracted 0 files`. Both exit 0.
- **Destination does not exist**: it is created, including any missing parent directories.
- **Destination exists as a regular file or is otherwise unusable**: the command fails with a diagnostic and exit status 2 before writing anything.
- **Existing directory where the archive stores a regular file**: the command fails with a diagnostic and exit status 2; a directory is never replaced by a file, even with `--overwrite`.
- **Existing regular file where the archive stores a directory**: the command fails with a diagnostic and exit status 2 for the same reason.
- **Member paths that escape the destination** (absolute paths, or paths containing `..` that resolve outside the destination): the command refuses to write anything outside the destination, reports the offending member on stderr, and exits 2.
- **Archive member types other than regular files and directories** (symbolic links, hard links, device nodes, FIFOs): these are skipped during extraction and are not counted in the summary; they are still reported by the list command because they are members of the archive.
- **Compression detected from content, not file name**: a gzip-compressed archive named `.tar`, or an uncompressed archive named `.tar.gz`, is handled correctly.
- **Zero-length archived files**: recreated as empty files and counted in the summary.
- **Permission denied while reading the archive or writing into the destination**: reported on stderr with the offending path and exit status 2.
- **Partial write interrupted by an error**: any failure after writing has begun still reports a diagnostic on stderr and exits non-zero rather than reporting success.

## Requirements *(mandatory)*

### Functional Requirements

#### Invocation

- **FR-001**: The tool MUST be invocable as a command-line program that takes a subcommand as its first argument, supporting exactly two subcommands: `list` and `extract`.
- **FR-002**: `list` MUST accept exactly one positional argument, the archive path.
- **FR-003**: `extract` MUST accept exactly two positional arguments, the archive path and the destination directory, plus an optional `--overwrite` flag.
- **FR-004**: Given no subcommand, an unrecognized subcommand, a wrong number of positional arguments, or an unrecognized option, the tool MUST write usage guidance to stderr and exit with a non-zero status, performing no other action.

#### Listing

- **FR-005**: `list` MUST write the recorded path of every member of the archive to stdout, one member per line, terminated by a newline.
- **FR-006**: `list` MUST emit members in the order they appear in the archive, applying no sorting, filtering, or de-duplication.
- **FR-007**: `list` MUST include every member type present in the archive, including directory entries and entries that are neither regular files nor directories.
- **FR-008**: Directory member names MUST be printed without a trailing path separator.
- **FR-009**: On success, `list` MUST exit with status 0 and MUST write nothing to stderr.

#### Extraction

- **FR-010**: `extract` MUST recreate each regular-file member of the archive as a regular file under the destination directory, at the member's recorded path relative to the destination, with contents byte-identical to the archived contents.
- **FR-011**: `extract` MUST create every directory needed by an extracted member, and MUST also create directory members that contain no files.
- **FR-012**: `extract` MUST create the destination directory, including missing parent directories, when it does not already exist.
- **FR-013**: `extract` MUST leave pre-existing files and directories under the destination that do not collide with any archive member unmodified.
- **FR-014**: On success, `extract` MUST write exactly the line `extracted N files` to stdout, where N is the decimal count of regular files it wrote, and MUST exit with status 0 and write nothing to stderr.
- **FR-015**: The reported count MUST include only regular files written, excluding directories and excluding skipped members, and MUST use the literal word `files` regardless of the value of N.
- **FR-016**: `extract` MUST skip archive members that are neither regular files nor directories, without failing and without counting them.

#### Compression

- **FR-017**: Both subcommands MUST handle uncompressed tar archives and gzip-compressed tar archives identically from the user's point of view.
- **FR-018**: Compression MUST be determined from the archive's content rather than its file name extension, so that any of `.tar`, `.tar.gz`, `.tgz`, or an unconventional name works.

#### Overwrite protection

- **FR-019**: Without `--overwrite`, if any regular-file member of the archive would be written to a path where a file or directory already exists under the destination, `extract` MUST fail: write a diagnostic naming at least one conflicting path to stderr, exit with status 3, and write nothing to stdout.
- **FR-020**: When `extract` fails for an overwrite conflict, it MUST NOT create, modify, truncate, or delete any file under the destination; the conflict MUST be detected before any member is written.
- **FR-021**: With `--overwrite`, `extract` MUST replace the contents of existing regular files at colliding paths and MUST count them among the files written.
- **FR-022**: An existing directory at the path of a directory member MUST NOT be treated as a conflict, with or without `--overwrite`; directory structures merge.
- **FR-023**: A collision between a regular-file member and an existing directory, or between a directory member and an existing regular file, MUST fail with a diagnostic on stderr and exit status 2, even when `--overwrite` is given, because the existing entry cannot be replaced in kind.

#### Failure reporting

- **FR-024**: If the archive path does not exist, is not readable, is a directory, or does not contain a valid tar archive, the tool MUST write a diagnostic to stderr that names the path and states the reason, write nothing to stdout, and exit with status 2.
- **FR-025**: If the destination path already exists as something other than a directory, or cannot be created or written to, `extract` MUST write a diagnostic to stderr that names the path, and exit with status 2.
- **FR-026**: `extract` MUST refuse to write outside the destination directory. Any member whose recorded path is absolute, or resolves outside the destination, MUST cause failure with a diagnostic naming that member on stderr and exit status 2, with nothing written outside the destination.
- **FR-027**: Every failure MUST produce a human-readable one-line-or-short diagnostic on stderr naming the offending path or member; no failure may be reported solely by exit status, and no failure may surface as an uncaught internal error trace.
- **FR-028**: Exit statuses MUST be used consistently and exclusively as follows: 0 for success, 3 for an overwrite conflict without `--overwrite`, and 2 for every other failure, including invocation errors.

### Key Entities

- **Archive**: a tar container, optionally gzip-compressed, identified by a filesystem path. Holds an ordered sequence of members.
- **Member**: one entry in an archive, with a recorded relative path, a type (regular file, directory, or other), and, for regular files, byte contents.
- **Destination**: the directory under which extracted members are recreated. May or may not exist before extraction; pre-existing contents determine whether an overwrite conflict arises.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For an archive of known members, the list command's output matches the archive's member names and order exactly, character for character, for 100% of tested archives in both compressed and uncompressed form.
- **SC-002**: After extracting an archive into an empty destination, 100% of the archive's regular files are present at their expected relative paths with byte-identical contents, and the printed count equals the number of regular files in the archive.
- **SC-003**: Re-extracting an archive into a destination that already holds its output, without the overwrite option, fails with exit status 3 in 100% of attempts and leaves every pre-existing file byte-for-byte unchanged, verified by comparing contents before and after.
- **SC-004**: Re-extracting with the overwrite option succeeds in 100% of attempts, leaving every target file byte-identical to the archived contents.
- **SC-005**: For every specified failure case (missing archive, unreadable archive, non-archive file, archive that is a directory, unusable destination, member path escaping the destination), the tool exits with the status this specification assigns and writes a non-empty diagnostic to stderr in 100% of attempts, with zero occurrences of an uncaught internal error trace.
- **SC-006**: Each functional requirement in this specification is covered by at least one automated test that fails when the requirement is unmet, traceable to the requirement identifier; the full automated suite passes.
- **SC-007**: An archive containing 10,000 members is listed in under 5 seconds and extracted in under 30 seconds on a routine development machine, with memory use that does not grow in proportion to the size of the largest member.
- **SC-008**: A user who knows only the two example invocations can complete both listing and extraction on their first attempt without consulting further documentation, because output and diagnostics are self-explanatory.

## Assumptions

These are reasonable defaults chosen where the feature description did not specify a detail. Each is stated so it can be challenged during clarification or planning.

- **Mandated implementation constraints** (given by the requester, recorded here rather than as functional requirements): Python 3.11 or newer; standard library only, no third-party runtime dependencies; code lives in a package named `tarx` under `src/`, runnable as `python -m tarx` when `src/` is on `PYTHONPATH`. These also satisfy the constitution's Standard Library Only principle.
- **Atomic conflict detection**: overwrite conflicts are detected by checking all destination paths before writing any file, so a conflict leaves the destination exactly as it was. The alternative — failing part-way through — was rejected because it leaves users with a half-populated directory and no clean retry.
- **Exit status 2 is the general failure status**: the description names only 0, 2, and 3. Failures it does not enumerate (unusable destination, path escaping the destination, permission errors, invocation errors) are mapped to 2, reserving 3 exclusively for the overwrite conflict so scripts can distinguish that one case.
- **Non-file, non-directory members are skipped, not fatal**: the description says extraction handles "files and directories". Symbolic links, hard links, device nodes, and FIFOs are therefore ignored during extraction rather than extracted or treated as errors. They remain visible via the list command.
- **Path containment is enforced**: archives may contain absolute or `..` paths. Writing outside the destination is treated as a failure rather than performed, which is the standard safe behavior for archive extraction tools.
- **File metadata is out of scope**: only relative paths and file contents are specified as preserved. Permission bits, ownership, and modification times are not required to be reproduced, and no requirement depends on them.
- **Output is plain text with no formatting**: no headers, totals, colors, or progress output beyond the specified lines, so output is pipe-friendly. The summary line uses `files` even when N is 1.
- **Single-archive, local-filesystem scope**: one archive per invocation, read from a local path. Archive creation, member filtering or selection, compression formats other than gzip, reading from stdin, remote URLs, and recursive archive handling are all out of scope for this feature.
- **No configuration surface**: behavior is determined entirely by the command-line arguments; there are no environment variables, config files, or plugin points, in line with the constitution's Simplicity principle.
- **Trusted-but-verified input**: archives may be untrusted, which is why path containment is enforced, but defenses against resource-exhaustion attacks (decompression bombs, absurd member counts) are not specified and are out of scope.
