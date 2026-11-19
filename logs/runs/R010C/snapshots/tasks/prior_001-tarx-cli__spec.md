# Feature Specification: Tar Archive Listing and Extraction Tool

**Feature Branch**: `001-tarx-cli`

**Created**: 2026-11-12

**Status**: Draft

**Input**: User description: "Build a command-line tool for listing and extracting tar archives. Run it as `python -m tarx COMMAND ...` with two commands: `list ARCHIVE` prints the name of every member of the archive, one per line, in the order they appear in the archive; `extract ARCHIVE DEST [--overwrite]` extracts the archive's files and directories into the directory DEST, keeping their relative paths and file contents, and prints `extracted N files` where N is the number of regular files written. Both plain tar (`.tar`) and gzip-compressed tar (`.tar.gz`, `.tgz`) must work. Existing files are never overwritten unless `--overwrite` is given; an overwrite conflict fails with exit status 3 and an error on stderr. A missing or invalid archive prints an error to stderr and exits 2. Successful commands exit 0. Python 3.11+, standard library only, package `tarx` under `src/`."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extract an archive into a chosen directory (Priority: P1)

Someone has received a tar archive — plain or gzip-compressed — and wants its files on disk in a directory they pick, with the archive's internal folder structure preserved and the file contents unchanged. They run one extract command, naming the archive and the destination directory, and get a one-line confirmation of how many files were written. If the archive is damaged, missing, or contains anything that would write outside the destination, nothing is written and they are told why.

**Why this priority**: This is the core value of the tool. Without it there is no reason for the tool to exist; listing alone can be satisfied by reading the archive by other means.

**Independent Test**: Create an archive of a known directory tree, extract it into an empty destination, and compare the result tree against the original — same relative paths, byte-identical contents, and the printed count equal to the number of regular files. Fully testable on its own and delivers the tool's primary value.

**Acceptance Scenarios**:

1. **Given** a gzip-compressed archive containing `photos/a.jpg` and `photos/b.jpg` and an empty working directory, **When** the user extracts it into `out`, **Then** `out/photos/a.jpg` and `out/photos/b.jpg` exist with contents identical to the archived files, `extracted 2 files` is printed to standard output, and the exit status is 0.
2. **Given** a plain (uncompressed) archive containing nested directories and an empty file, **When** the user extracts it, **Then** all directories are created, the empty file exists with zero bytes, and the printed count counts only regular files, not directories.
3. **Given** a destination directory that does not yet exist, **When** the user extracts into it, **Then** the destination (and any missing parent directories) is created and extraction succeeds.
4. **Given** an archive path that does not exist, **When** the user extracts it, **Then** an error message naming the archive is written to standard error, nothing is written to standard output, no files are created, and the exit status is 2.
5. **Given** a file that is not a valid tar archive (for example, arbitrary binary data or a truncated archive), **When** the user extracts it, **Then** an error message is written to standard error, no files are created, and the exit status is 2.
6. **Given** an archive containing a member whose path would resolve outside the destination directory, **When** the user extracts it, **Then** the command refuses with an error on standard error, writes no files at all, and exits with status 2.

---

### User Story 2 - Inspect an archive's contents without extracting (Priority: P2)

Before committing to extraction, someone wants to see what an archive contains. They run one list command and get every member name, one per line, in archive order, suitable for piping into other text tools. Nothing on disk changes.

**Why this priority**: Valuable and independently useful — it is the safe way to inspect an untrusted archive — but it is a smaller slice of value than extraction and can ship after it.

**Independent Test**: Build an archive with a known member order, list it, and compare the output line-for-line against the expected names; confirm no filesystem changes occurred.

**Acceptance Scenarios**:

1. **Given** a gzip-compressed archive containing `photos/a.jpg` then `photos/b.jpg`, **When** the user lists it, **Then** standard output is exactly those two names in that order, one per line, and the exit status is 0.
2. **Given** an archive whose members include directories and non-file entries such as symbolic links, **When** the user lists it, **Then** every member name is printed regardless of its type, in archive order.
3. **Given** an archive containing no members, **When** the user lists it, **Then** nothing is printed to standard output and the exit status is 0.
4. **Given** a missing or invalid archive, **When** the user lists it, **Then** an error message is written to standard error and the exit status is 2.

---

### User Story 3 - Protect existing files, and overwrite deliberately (Priority: P3)

Someone extracts into a directory that already holds files. By default the tool refuses rather than destroying anything: it reports the conflicting path and stops without touching the destination. When the user actually wants to refresh the contents, they repeat the command with an explicit overwrite option and the existing files are replaced.

**Why this priority**: The protective default is part of User Story 1's guarantee; this story adds the deliberate opt-in and the distinct failure signal that lets scripts tell "conflict" apart from "broken archive". It is the last slice that can ship.

**Independent Test**: Extract an archive twice into the same destination — the second run must fail with the conflict status and leave the destination unchanged — then run it a third time with the overwrite option and confirm success and replaced contents.

**Acceptance Scenarios**:

1. **Given** a destination that already contains a file at a path the archive would write, **When** the user extracts without the overwrite option, **Then** an error message naming the conflicting path is written to standard error, the destination is left byte-for-byte unchanged, no success line is printed, and the exit status is 3.
2. **Given** the same situation, **When** the user extracts with the overwrite option, **Then** the existing file's contents are replaced by the archived contents, the success line counts every regular file written, and the exit status is 0.
3. **Given** a destination that already contains some of the archive's directories, **When** the user extracts without the overwrite option, **Then** the pre-existing directories are reused without error, because only regular files are subject to overwrite protection.
4. **Given** a destination where an archive file member's path already exists as a directory (or a directory member's path already exists as a regular file), **When** the user extracts with or without the overwrite option, **Then** the command reports the type conflict on standard error, leaves the destination unchanged, and exits with status 2.

---

### Edge Cases

- **Archive is empty**: listing prints nothing; extraction creates the destination and prints `extracted 0 files`. Both exit 0.
- **Archive member is a zero-byte file**: it is created as an empty file and counted.
- **Member names contain spaces, non-ASCII characters, or very long paths**: names are reproduced faithfully on disk and in listings.
- **Member name contains control characters** (newline, carriage return, escape): the on-screen name is escaped so one member still occupies one output line and no terminal control sequence can be injected (SR-007).
- **Member path escapes the destination** via `..` segments, a leading `/`, or a platform-specific absolute form: rejected before anything is written (SR-001).
- **Archive contains symbolic links, hard links, device nodes, FIFOs, or other non-file, non-directory members**: extraction refuses the archive with a message identifying the member; it does not silently skip it (SR-002, SR-003).
- **A path component inside the destination is an existing symbolic link**: extraction refuses rather than following it out of the destination (SR-004).
- **Two members in one archive map to the same destination path**: rejected, so a later member cannot quietly overwrite an earlier one and bypass overwrite protection (SR-009).
- **Archive is a decompression bomb or otherwise oversized** (member count or uncompressed size beyond the documented limits, including headers that understate the real size): rejected with an error (SR-005).
- **Compression does not match the filename**: a gzip-compressed archive named `.tar`, or a plain archive named `.tar.gz`, still works, because the format is determined from the archive's content (FR-008).
- **Destination path exists but is a regular file, or is not writable**: reported on standard error with exit status 2.
- **Archive exists but is not readable** by the current user: reported on standard error with exit status 2.
- **No command, an unknown command, or the wrong number of arguments**: usage error on standard error with exit status 2.
- **Standard output is closed or a broken pipe** (for example `list` piped into a command that exits early): the tool terminates without an unhandled crash report.

## Requirements *(mandatory)*

### Functional Requirements

**Commands and invocation**

- **FR-001**: The tool MUST provide exactly two commands, `list` and `extract`. A missing command, an unrecognised command, a missing required argument, an extra argument, or an unrecognised option MUST produce a usage message on standard error and exit status 2.
- **FR-002**: `list ARCHIVE` MUST write the name of every member of ARCHIVE to standard output, one name per line, in the order the members appear in the archive, then exit with status 0.
- **FR-003**: `list` MUST include every member regardless of member type (regular file, directory, link, or any other type) and MUST NOT create, modify, or delete anything on the filesystem.
- **FR-004**: `extract ARCHIVE DEST [--overwrite]` MUST write every regular-file and directory member of ARCHIVE beneath DEST, preserving each member's path relative to the archive's root.
- **FR-005**: The contents of each extracted regular file MUST be byte-for-byte identical to the member's contents in the archive.
- **FR-006**: On success, `extract` MUST write exactly `extracted N files`, followed by a newline, to standard output and nothing else, where N is the count of regular files written, and MUST exit with status 0.
- **FR-007**: `extract` MUST create DEST, including any missing parent directories, when it does not exist. If DEST exists and is not a directory, or cannot be created or written to, the tool MUST report the problem on standard error and exit with status 2.
- **FR-008**: Both uncompressed tar archives and gzip-compressed tar archives MUST be supported by both commands. The format MUST be determined from the archive's content, not from its filename, so that `.tar`, `.tar.gz`, `.tgz`, and misnamed archives all behave correctly.

**Overwrite behaviour**

- **FR-009**: Without `--overwrite`, if any regular-file member of the archive maps to a path that already exists, `extract` MUST write no files at all, report the first such conflicting path on standard error, print no success line, and exit with status 3.
- **FR-010**: With `--overwrite`, `extract` MUST replace the contents of existing regular files at the mapped paths, reuse existing directories without error, and complete normally per FR-006.
- **FR-011**: If a regular-file member maps to a path that already exists as a directory, or a directory member maps to a path that already exists as a regular file, `extract` MUST report the type conflict on standard error, leave the destination unchanged, and exit with status 2, with or without `--overwrite`.
- **FR-012**: Pre-existing directories in the destination MUST NOT be treated as overwrite conflicts; overwrite protection applies to regular files only.

**Failure behaviour and output discipline**

- **FR-013**: If ARCHIVE does not exist, cannot be read, or is not a valid tar archive (including a truncated or corrupt archive), the tool MUST write an error message naming the archive to standard error and exit with status 2, having created no files.
- **FR-014**: `extract` MUST validate the whole archive — every member's name, type, size, and destination mapping, plus all overwrite and type checks — before writing any file or directory. If any check fails, the destination MUST be left exactly as it was.
- **FR-015**: Exit statuses MUST be: `0` for a successful command; `3` when extraction was refused solely because it would overwrite an existing regular file and `--overwrite` was not given; `2` for every other failure, including usage errors, unreadable or invalid archives, unusable destinations, rejected members, and exceeded limits. No other exit status may be produced.
- **FR-016**: All error and diagnostic messages MUST go to standard error. Standard output MUST carry only the data the command promises: member names for `list`, the single success line for `extract`. A failing command MUST NOT print a success line.
- **FR-017**: Every error message MUST name what was rejected and why, in terms the operator can act on — the archive path, the member name, or the destination path at issue.
- **FR-018**: An archive with no members MUST be handled as a normal success: `list` prints nothing; `extract` creates DEST and prints `extracted 0 files`.
- **FR-019**: The count N in FR-006 MUST count regular files written only — directories, and any member not written, are excluded.

### Security Requirements

Required by the project constitution (Principle V); each is testable and must be covered by at least one automated test. Threats addressed are drawn from the OWASP Top 10 categories for injection, broken access control, and security misconfiguration, and from the OWASP ASVS file-handling requirements. An archive is untrusted input in its entirety: member names, types, and declared sizes.

- **SR-001**: `extract` MUST reject any member whose destination path, after resolving the name against DEST, does not lie inside DEST. This includes names containing `..` segments, names beginning with a path separator, and platform-specific absolute forms such as drive letters or UNC prefixes. The command MUST write nothing, report the offending member, and exit 2.
- **SR-002**: `extract` MUST reject archives containing symbolic-link or hard-link members, and MUST never create a link. The rejection MUST name the member and exit 2 — the member MUST NOT be silently skipped.
- **SR-003**: `extract` MUST reject archives containing any member that is neither a regular file nor a directory nor a link already covered by SR-002 — including character devices, block devices, FIFOs, and sockets — naming the member and exiting 2.
- **SR-004**: When resolving a destination path, `extract` MUST NOT follow a symbolic link that already exists inside DEST. If any component of a member's destination path is an existing symbolic link, the command MUST refuse, write nothing, and exit 2.
- **SR-005**: Both commands MUST bound the resources a single archive can consume, and MUST treat an exceeded bound as an error (exit 2), never as a truncated best-effort result. The bounds are: at most 10,000 members per archive; at most 1 GiB total uncompressed bytes across all members; at most 1 GiB for any single member. Declared sizes MUST be checked before writing, and the bytes actually read MUST also be counted while writing, so that an archive whose headers understate the real size is still stopped. If writing is aborted because actual bytes exceeded a bound, the error message MUST state that the destination may hold a partial extraction.
- **SR-006**: Extracted files and directories MUST be created with the narrowest workable permissions, set at creation: owner read and write for files, owner read, write, and execute for directories. Permission bits recorded in the archive MUST NOT be applied, and setuid, setgid, and sticky bits MUST never be set. Ownership and timestamps from the archive MUST NOT be restored.
- **SR-007**: Any member name written to standard output or standard error MUST have control characters — including newline, carriage return, and escape — rendered in a visible escaped form, so that a crafted member name cannot inject terminal control sequences or additional output lines. Names made only of printable characters MUST be printed unchanged.
- **SR-008**: Error messages and diagnostics MUST NOT include the contents of archive members, environment variable values, or any data beyond the paths and reasons required by FR-017. No stack trace may reach standard error for any of the failure conditions specified here.
- **SR-009**: `extract` MUST reject an archive in which two or more members map to the same destination path, so that a second member cannot overwrite a file written earlier in the same run and thereby bypass FR-009. The rejection happens during validation (FR-014), so nothing is written.
- **SR-010**: Command-line arguments MUST be validated before use: the archive path and destination path MUST be non-empty, and the only accepted option is `--overwrite` on `extract`. Invalid arguments are a usage error under FR-001 (exit 2). Argument values MUST be used as filesystem paths directly, never interpolated into a shell command or any other string-built interface.

### Mandated Constraints *(explicitly specified by the requester; recorded here for the planning phase)*

- **MC-001**: The implementation targets Python 3.11 or newer and uses the Python standard library only (consistent with constitution Principle I).
- **MC-002**: The code lives in a package named `tarx` under `src/`, and the tool runs as `python -m tarx COMMAND ...` when `src/` is on `PYTHONPATH` — no installation step.

### Key Entities

- **Archive**: the input file named by ARCHIVE. Either an uncompressed tar archive or a gzip-compressed one; holds an ordered sequence of members. Treated as untrusted data throughout.
- **Member**: one entry in an archive. Has a name (a relative path), a type (regular file, directory, link, or other), a declared size, and, for regular files, contents. Only name, type, size, and contents matter to this feature; recorded permissions, ownership, and timestamps are deliberately ignored (SR-006).
- **Destination**: the directory named by DEST, the single boundary inside which every extracted path must fall. Created if absent.
- **Extraction result**: the outcome reported to the caller — the count of regular files written plus an exit status, or an error message plus a non-zero exit status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can list an archive's contents or extract it with a single command, with no installation, configuration, or network access step.
- **SC-002**: For every archive in the acceptance corpus — uncompressed and gzip-compressed, nested directories, empty archive, zero-byte files, names with spaces and non-ASCII characters — extraction reproduces the original tree exactly: identical relative paths and byte-identical file contents, verified by automated comparison in 100% of cases.
- **SC-003**: For every archive in the acceptance corpus, listing reproduces the member names and their archive order exactly, verified line-for-line in 100% of cases.
- **SC-004**: Each of the three documented exit statuses (0, 2, 3) is produced by its specified scenarios and by no other, verified by automated tests covering every failure condition named in FR-013, FR-015, and the Security Requirements.
- **SC-005**: No archive in the adversarial corpus — path traversal, absolute member paths, symlink escape, link and special-file members, duplicate destination paths, oversized and decompression-bomb archives, control characters in names — causes any file to be created or modified outside the destination directory, or any existing file to be replaced without the overwrite option. Zero violations permitted.
- **SC-006**: A command that fails with exit status 3, or with exit status 2 for a rejected member, invalid archive, or unusable destination, leaves the destination directory byte-for-byte unchanged, verified by comparing the destination before and after in 100% of such cases. The single documented exception is an abort on an archive whose headers understated its real size (SR-005), which must report the partial extraction.
- **SC-007**: Listing or extracting a 1,000-member, 50 MB archive completes in under 5 seconds on a typical developer machine, and memory use stays bounded regardless of individual member size (no member is held wholly in memory).
- **SC-008**: Every requirement identifier in this specification (FR-xxx and SR-xxx) appears in the name or docstring of at least one automated test, giving 100% auditable requirement coverage as required by constitution Principle III.

## Assumptions

Defaults chosen where the feature description was silent. Each is a decision that can be revisited.

- **Member types**: the description promises only "files and directories", so extraction handles exactly regular files and directories and refuses everything else loudly (SR-002, SR-003) rather than skipping it silently, which the constitution's Fail Loudly principle forbids. A plausible alternative — extract files and directories while skipping links that stay inside the destination — was rejected as less predictable and harder to audit. This means an archive containing symbolic links cannot be extracted at all by this tool.
- **Exit status reuse**: the description names only statuses 0, 2, and 3, so every failure other than an overwrite conflict reports status 2, including rejected members, exceeded limits, usage errors, and unusable destinations. No new exit statuses are invented.
- **All-or-nothing extraction**: "if extraction *would* overwrite" is read as requiring a check before any write, so validation precedes writing and a rejected archive leaves the destination untouched (FR-014).
- **Resource limits**: the specific bounds in SR-005 (10,000 members, 1 GiB total, 1 GiB per member) are chosen as generous defaults for ordinary archives while still stopping decompression bombs. They are fixed constants, not user-configurable, to keep the tool simple; making them configurable would be a later change.
- **Permissions**: archive permission bits are ignored and extracted entries are owner-only (SR-006), because the description says nothing about preserving modes and the constitution requires the narrowest workable permissions. Consequently, an extracted tree is not a faithful copy of recorded modes, ownership, or timestamps — only of paths and contents, which is what the description asks for.
- **Duplicate members**: archives with two members mapping to the same path are rejected (SR-009) rather than applying last-member-wins, because last-member-wins would let an archive overwrite a file without the overwrite option.
- **Output format**: the success line is exactly `extracted N files` for every N, including `extracted 0 files` and `extracted 1 files` — no pluralisation, matching the literal string in the description so scripts can parse it.
- **Listing is non-destructive and unfiltered**: `list` prints all member names including those extraction would refuse, since listing writes nothing and is the safe way to inspect an untrusted archive. Control characters in names are still escaped for display (SR-007).
- **Scope boundaries**: creating or modifying archives, filtering or selecting a subset of members, progress reporting, recursive or multi-archive invocation, compression formats other than gzip (bzip2, xz, zstd), and preserving extended attributes or sparse-file layout are all out of scope.
- **Environment**: the tool runs on a POSIX-like filesystem as a non-privileged user, reads archives from a local path, and needs no network access. Platform-specific absolute path forms are still rejected defensively (SR-001).
