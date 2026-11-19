# Feature Specification: Archive Creation Command

**Feature Branch**: `002-create-command`

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "This repository already contains `tarx`, a command-line tool for listing and extracting tar archives. Read the existing code and any documentation in the repository before changing it. Add a third command as described below; `list` and `extract` must keep working exactly as they do now.

- `python -m tarx create ARCHIVE PATH... [--overwrite]` creates a tar archive at ARCHIVE containing each PATH. A PATH is a file or a directory given relative to the current directory, such as `notes.txt` or `photos`; a directory is added together with everything inside it. Members are named by their relative path, so `python -m tarx create photos.tar.gz photos` produces members such as `photos/a.jpg`. If ARCHIVE ends in `.tar.gz` or `.tgz` the archive is gzip-compressed; otherwise it is a plain tar archive. When it finishes it prints `created ARCHIVE with N files` to standard output, where N is the number of regular files added.

If ARCHIVE already exists, `create` fails with exit status 3 and an error message on standard error, unless `--overwrite` is given, in which case the archive is replaced. If a PATH does not exist, it prints an error message naming that PATH to standard error, exits with status 2, and creates no archive. Archives made by `create` must be readable by the existing `list` and `extract` commands. Successful commands exit with status 0."

## Context

This feature extends the shipped `001-tarx-cli` feature, which delivered `list ARCHIVE` and
`extract ARCHIVE DEST [--overwrite]`. That feature's specification, its CLI contract, and its test
suite remain in force; this document adds a third command and changes nothing about the first two.
Where this document references a requirement of the earlier feature it names it explicitly (for
example "`001-tarx-cli` FR-004"); unqualified `FR-` identifiers below belong to this feature.

Three conventions established by `001-tarx-cli` are reused deliberately rather than reinvented,
because a user who has learned one command should not have to learn a different set of rules for
the next:

- **The three-status vocabulary**: `0` success, `2` unusable input, `3` refused overwrite, with
  `2` outranking `3` when a run exhibits both.
- **Validate everything before writing anything**, so a rejected run leaves the filesystem as it
  was.
- **Results to standard output, diagnostics to standard error, one problem per line.**

## Clarifications

### Session 2026-11-19

- Q: When `create` encounters an entry it cannot read inside a named directory, must it detect that before writing (no archive left behind), or may it fail partway and leave an incomplete archive? → A: Detect before writing — validation walks every named path in full and confirms each entry can be opened for reading, so an unreadable entry exits 2 with no archive created; an incomplete archive can then only result from a genuine mid-write failure such as a full disk.
- Q: In what order are the entries inside a named directory stored in the archive? → A: Sorted by full member path compared as text (for example `d/a.txt`, `d/b/c.txt`, `d/z.txt`), which also places a directory before the entries inside it; the same files therefore always produce the same archive.
- Q: When two names in the tree are two names for the same file on disk (a hard link), is each stored as an ordinary file or is the second one skipped? → A: Each name is stored and counted as an independent regular file with its own copy of the contents; "hard link" is a member type only when reading archives, so FR-015's skip list covers only what the filesystem itself distinguishes from a regular file — symbolic links, device nodes, FIFOs and sockets.
- Q: What happens when `ARCHIVE` names a path whose parent directory does not exist? → A: `create` refuses — a diagnostic naming the missing directory, exit status 2, and no archive and no directories created. `create` writes exactly one thing, the archive itself; it never creates directories, unlike `extract`'s destination.
- Q: How is SC-010's "archives a file larger than available memory" made testable? → A: Restated as a bounded measurement — archive a file of tens of megabytes and assert peak additional memory stays under a small fixed ceiling that does not grow with file size, so an implementation that reads a whole file into memory fails the test.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Package files and folders into an archive (Priority: P1)

Someone has files and folders in their current directory and wants a single archive file holding
them. They run the tool's `create` command, naming the archive they want and then each file or
folder to put in it. The archive appears, holding every file from every path they named, under
names that are exactly the relative paths they typed, and the tool reports how many files it put
in. Whether the archive is compressed follows from the name they chose for it.

**Why this priority**: This is the entire point of the feature and the smallest slice that
delivers standalone value. A user who has only this capability can already package their work.

**Independent Test**: Build a known directory tree, run `create` with a `.tar` name and again with
a `.tar.gz` name, and confirm each archive holds exactly the expected members in the expected
order, with the expected relative names and byte-identical contents, that the gzip-named one is
gzip-compressed and the other is not, and that standard output is the single summary line with the
correct count and the exit status is 0.

**Acceptance Scenarios**:

1. **Given** a directory `photos` containing `a.jpg` and `b.jpg`, **When** the user runs
   `create photos.tar.gz photos`, **Then** standard output is exactly
   `created photos.tar.gz with 2 files`, the exit status is 0, and the archive holds the members
   `photos`, `photos/a.jpg` and `photos/b.jpg` in exactly that order.
2. **Given** the same directory, **When** the user runs `create photos.tar photos`, **Then** the
   archive holds the same members with the same names and is an uncompressed tar archive.
3. **Given** a file `notes.txt` in the current directory, **When** the user runs
   `create notes.tgz notes.txt`, **Then** the archive holds the single member `notes.txt`, the
   archive is gzip-compressed, and standard output is `created notes.tgz with 1 files`.
4. **Given** several paths — a file and two directories — **When** the user runs `create` with all
   of them in one invocation, **Then** every one of them is in the archive, in the order the paths
   were given, and the reported count is the total number of regular files across all of them.
5. **Given** a directory tree nested several levels deep, **When** the user runs `create` on its
   top directory, **Then** every file at every depth is a member named by its full relative path,
   and the members appear sorted by name as text — `d`, `d/a.txt`, `d/b/c.txt`, `d/z.txt`.
6. **Given** a directory containing an empty subdirectory, **When** the user runs `create`,
   **Then** the empty subdirectory is recorded in the archive and does not count toward the
   reported file total.
7. **Given** a directory containing a zero-length file, **When** the user runs `create`, **Then**
   that file is a member of the archive and counts toward the reported total.
8. **Given** the same unchanged tree and the same invocation run twice, **When** the user lists
   both resulting archives, **Then** the two member sequences are identical.

---

### User Story 2 - Don't let a new archive destroy an old one (Priority: P2)

Someone runs `create` with an archive name that is already taken — a previous archive, or any
other file. Nothing is destroyed: the tool refuses, says which path is in the way, and exits with
a status their script can branch on. When they genuinely want the old archive gone, they re-run
with the overwrite option and the new archive replaces it.

**Why this priority**: `create` is the only command in the tool that writes a file the user names
directly, so it is the one that can destroy work with a single mistyped name. The refusal is what
makes the command safe to use from a script; the opt-in override is what makes repeat runs
practical.

**Independent Test**: Create an archive, then run the identical command again and confirm it fails
with status 3, writes a diagnostic naming the archive, writes nothing to standard output, and
leaves the first archive byte-for-byte unchanged; then run it once more with the overwrite option
and confirm it succeeds and the archive now reflects the current source tree.

**Acceptance Scenarios**:

1. **Given** an existing file at the archive path, **When** the user runs `create` without the
   overwrite option, **Then** an error message naming that path is written to standard error,
   standard output is empty, the exit status is 3, and the existing file is unchanged.
2. **Given** an existing archive at the archive path, **When** the user runs `create` with the
   overwrite option, **Then** the old archive is replaced by a new one holding the current
   contents of the named paths, the summary line is written, and the exit status is 0.
3. **Given** a source tree that has changed since the last run, **When** the user re-runs `create`
   with the overwrite option, **Then** the resulting archive reflects the current tree, not the
   previous one.
4. **Given** no file at the archive path, **When** the user runs `create` with the overwrite
   option, **Then** the behaviour is identical to running it without the option.
5. **Given** a directory sitting at the archive path, **When** the user runs `create` — with or
   without the overwrite option — **Then** an error message naming that path is written to
   standard error, the exit status is 2, and the directory is untouched.
6. **Given** an archive name inside a directory that does not exist, **When** the user runs
   `create` — with or without the overwrite option — **Then** an error message naming the missing
   directory is written to standard error, the exit status is 2, and neither the archive nor any
   directory is created.

---

### User Story 3 - Get a clear failure and no half-made archive (Priority: P3)

Someone mistypes one of the paths they want to archive, or names a path that is not theirs to
archive. The tool tells them exactly which path it could not use, and no archive file is left
behind for them to clean up or — worse — to mistake for a complete one.

**Why this priority**: A packaging command that produces a partial archive on failure is actively
dangerous, because the archive looks like a result. This slice is what makes a failed `create`
indistinguishable from never having run it.

**Independent Test**: Run `create` in a clean directory with one good path and one misspelled
path, and confirm the misspelled path is named on standard error, standard output is empty, the
exit status is 2, and no file exists at the archive path afterwards.

**Acceptance Scenarios**:

1. **Given** a path that does not exist, **When** the user runs `create`, **Then** an error
   message naming that path is written to standard error, standard output is empty, the exit
   status is 2, and no archive is created.
2. **Given** several paths of which more than one does not exist, **When** the user runs `create`,
   **Then** every missing path is named on standard error, one per line, and the exit status is 2.
3. **Given** a path that does not exist **and** an archive path that is already taken, **When** the
   user runs `create` without the overwrite option, **Then** both problems are reported on
   standard error and the exit status is 2, not 3.
4. **Given** an existing archive and a path that does not exist, **When** the user runs `create`
   with the overwrite option, **Then** the run fails with status 2 and the existing archive is
   left unchanged — the overwrite happens only when the whole run can succeed.
5. **Given** a path that is absolute, or that points above the current directory, **When** the
   user runs `create`, **Then** an error message naming that path is written to standard error,
   the exit status is 2, and no archive is created.
6. **Given** no paths at all after the archive name, or an unrecognised option, **When** the user
   invokes `create`, **Then** a usage message is written to standard error, the exit status is
   non-zero, and nothing is read or written.
7. **Given** a directory containing one file the user has no permission to read, **When** the user
   runs `create` on that directory, **Then** an error message naming that unreadable file is
   written to standard error, the exit status is 2, and no file exists at the archive path
   afterwards.

---

### User Story 4 - Everything that worked before still works (Priority: P4)

Someone already uses `list` and `extract`, perhaps from a script. After this feature ships, those
commands behave identically — same operands, same output, same exit statuses, same diagnostics —
and they can now also read the archives their colleagues produce with `create`.

**Why this priority**: It protects the value already delivered rather than adding new value, so it
ranks last; but a regression here would be worse than the absence of `create`, so it is specified
and tested rather than assumed.

**Independent Test**: Run the complete pre-existing test suite for `list` and `extract` unchanged
and confirm it passes; separately, create an archive with `create`, then list it and extract it and
compare the extracted tree against the original sources.

**Acceptance Scenarios**:

1. **Given** the shipped behaviour of `list` and `extract`, **When** this feature is complete,
   **Then** every pre-existing acceptance scenario for those two commands still holds, with no
   change to their operands, options, output, diagnostics, or exit statuses.
2. **Given** an archive produced by `create` from a known tree, **When** the user runs `list` on
   it, **Then** the output is the member names of that tree, one per line, with no trailing
   slashes.
3. **Given** an archive produced by `create` from a known tree, **When** the user runs `extract`
   on it into a fresh destination, **Then** the destination holds the same tree with
   byte-identical files and the reported extracted count equals the count `create` reported.
4. **Given** a gzip-compressed archive produced by `create`, **When** the user runs `list` or
   `extract` on it, **Then** it is handled correctly, as compression is detected from content
   (`001-tarx-cli` FR-004).
5. **Given** the tool's usage output, **When** a new user reads it, **Then** all three commands,
   their operands, and the overwrite option are discoverable from it.

---

### Edge Cases

- **A path given with a trailing slash or a leading `./`** (`photos/`, `./photos`): accepted and
  treated as the same path, with member names carrying neither the trailing slash nor the `./`
  prefix.
- **The same path given twice, or a path nested inside another given path** (`photos` and
  `photos/a.jpg` together): each file ends up as exactly one member, counted once; the archive
  never holds two members with the same name because of how the paths were listed.
- **The archive would land inside a directory being archived** (`create photos/all.tar photos`):
  the archive file itself is not added as a member of itself; everything else under the directory
  is.
- **Entries that are neither regular files nor directories** (symbolic links, device nodes, FIFOs,
  sockets) encountered while adding a directory, or named directly as a path: they are not stored,
  each is named on standard error so the user knows it was left out, they do not count toward the
  reported total, and their presence alone is not a failure.
- **Two names for the same file on disk** (a hard link — `notes.txt` and `backup/notes.txt` being
  two names for one file rather than two copies): both names are stored as ordinary regular file
  members, each with its own copy of the contents, and both count toward the reported total.
  Nothing is skipped, because neither name is distinguishable on disk from any other regular file
  (FR-015).
- **A path that exists but cannot be read** (permission denied on a file, or on a directory being
  walked): the run fails loudly with a diagnostic naming that path, exits 2, and creates no
  archive — readability is established across the whole tree during validation, before any writing
  begins (FR-016, FR-021).
- **An empty directory as the only path**: the archive is created holding that one directory
  member and the summary reads `created ARCHIVE with 0 files`, exit 0.
- **A count of exactly one**: the summary stays `created ARCHIVE with 1 files`; the line is a
  fixed template for scripts, not prose.
- **An archive name with no recognised extension at all** (`backup`, `data.bin`): treated as a
  plain, uncompressed tar archive, because only `.tar.gz` and `.tgz` select compression.
- **An archive name inside a directory that does not exist** (`backups/2026/photos.tar` with no
  `backups/2026`): refused with a diagnostic naming the missing directory and exit 2. No
  directories are created — `create` writes the archive and nothing else (FR-027).
- **An archive name whose extension disagrees with convention** (`photos.tar` asked to hold
  compressed data, or `photos.tar.gz` holding plain data): not possible — the name alone decides,
  and `list`/`extract` read either form regardless of name.
- **Non-ASCII and non-UTF-8 file names**: stored under the names the filesystem reports and
  reproduced by `list` and `extract`.
- **A very large file, or a tree larger than available memory**: archived successfully without
  holding a whole file or the whole archive in memory, which SC-010 checks as a bounded peak-memory
  measurement rather than by building such a file.
- **Filesystem error after writing has begun** (disk full, permission revoked, the archive's
  directory removed mid-run): the run fails loudly with a diagnostic and exits 2 with no summary
  line. An incomplete archive may remain at the archive path and must not be assumed valid; the
  tool does not roll back, matching `001-tarx-cli` FR-022.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST expose a third command, `create`, selected by the first operand
  alongside the existing `list` and `extract`, and MUST continue to reject any other command name
  with a usage diagnostic.
- **FR-002**: `create` MUST accept the operands `ARCHIVE PATH...` and the option `--overwrite`,
  MUST require at least one `PATH`, and MUST accept any number of further `PATH` operands.
- **FR-003**: Each `PATH` MUST be interpreted relative to the current directory. A `PATH` naming a
  regular file MUST contribute exactly one regular-file member; a `PATH` naming a directory MUST
  contribute that directory and every entry beneath it, at every depth.
- **FR-004**: Every member MUST be named by its path relative to the current directory, using `/`
  as the separator, with no leading `./`, no absolute component and no upward-traversing segment —
  so that `create photos.tar.gz photos` yields members such as `photos/a.jpg`.
- **FR-005**: When `ARCHIVE` ends in `.tar.gz` or `.tgz`, the archive MUST be gzip-compressed;
  for any other `ARCHIVE` name it MUST be an uncompressed tar archive.
- **FR-006**: Each stored regular file's contents MUST be byte-for-byte identical to the file on
  disk at the time it was read.
- **FR-007**: Directories MUST be recorded as directory members, including directories that
  contain no files, so that extraction recreates the tree's shape.
- **FR-008**: On success, `create` MUST write the single line `created ARCHIVE with N files` to
  standard output and nothing else, where `ARCHIVE` is echoed exactly as the user supplied it and
  `N` is the count of regular-file members added. The wording MUST NOT vary with `N`: the word
  `files` stays plural for every count, including 0 and 1.
- **FR-009**: Archives produced by `create` MUST be readable by this tool's `list` and `extract`
  commands: `list` MUST print every member's name, and `extract` MUST reproduce the archived tree
  with byte-identical file contents under its destination.
- **FR-010**: When a file already exists at `ARCHIVE` and `--overwrite` is not given, `create`
  MUST create no archive, MUST leave the existing file unchanged, MUST write an error message
  naming that path to standard error, and MUST exit with status 3.
- **FR-011**: With `--overwrite`, `create` MUST replace an existing regular file at `ARCHIVE` with
  the new archive, and MUST NOT touch that file until validation (FR-016) has found no problem, so
  that a rejected run leaves the previous archive intact.
- **FR-012**: When `ARCHIVE` exists and is not a regular file — a directory, symbolic link, device
  node, FIFO or socket — `create` MUST create no archive, MUST write an error message naming that
  path to standard error, and MUST exit with status 2, identically with and without
  `--overwrite`, which consents only to replacing a regular file.
- **FR-013**: When any `PATH` does not exist, `create` MUST write an error message naming that
  `PATH` to standard error, MUST create no archive, MUST leave any pre-existing file at `ARCHIVE`
  unchanged, and MUST exit with status 2.
- **FR-014**: When any `PATH` is absolute, or resolves outside the current directory, `create`
  MUST write an error message naming that `PATH` to standard error, MUST create no archive, and
  MUST exit with status 2.
- **FR-015**: Entries that are neither regular files nor directories MUST NOT be stored in the
  archive. Each such entry MUST be named on standard error as skipped, MUST NOT be counted in `N`,
  and its presence alone MUST NOT cause a non-zero exit status. The entries this covers are those
  the filesystem itself distinguishes from a regular file: symbolic links, device nodes, FIFOs and
  sockets. A file that merely carries more than one name on disk is an ordinary regular file for
  this purpose — each such name MUST be stored and counted as a regular file in its own right,
  with its own copy of the contents, so that no name beneath a given `PATH` is missing from the
  archive. The hard-link member type arises only when reading an archive, where `extract`
  continues to skip it unchanged (`001-tarx-cli` behaviour).
- **FR-016**: `create` MUST complete every check it is capable of making — the usability of
  `ARCHIVE`, the existence and safety of every `PATH`, and the readability of every entry beneath
  every `PATH` at every depth — before creating or modifying any file, so that a failure the tool
  detects leaves the filesystem exactly as it was. This means the source tree is traversed in full
  during validation, before the archive is opened for writing.
- **FR-017**: Every `create` run that completes its requested work MUST exit with status 0;
  command results MUST go only to standard output and diagnostics only to standard error.
- **FR-018**: When validation finds multiple problems, `create` MUST report all of them on
  standard error, one per line, rather than stopping at the first. When the problems span both
  failure classes, the exit status MUST be 2: unusable input takes precedence over a refused
  overwrite, because status 3 would wrongly imply that `--overwrite` makes the run succeed.
- **FR-019**: The archive being written MUST NOT be added to itself as a member when `ARCHIVE`
  lies inside a directory named by a `PATH`.
- **FR-020**: A file or directory that is reachable through more than one of the given `PATH`
  operands MUST appear in the archive exactly once and MUST be counted once in `N`, at the
  position earned by the first `PATH` operand that reaches it. Identity for this purpose is the
  member name, not the underlying file on disk, so two names for one file are two members
  (FR-015) while two routes to one name are one member.
- **FR-021**: When an entry that exists cannot be read, `create` MUST detect this during
  validation (FR-016), MUST write a diagnostic naming that entry to standard error, MUST create no
  archive, MUST leave any pre-existing file at `ARCHIVE` unchanged, and MUST exit with status 2.
  Separately, when an unexpected filesystem error interrupts `create` after writing has begun, the
  tool MUST write a diagnostic naming the path concerned to standard error, MUST NOT write the
  summary line to standard output, and MUST exit with status 2; an incomplete archive MAY remain at
  `ARCHIVE` and the tool does not undo it.
- **FR-022**: Invalid `create` invocations — a missing `ARCHIVE`, no `PATH` operands, an
  unrecognised option — MUST produce a usage diagnostic on standard error, a non-zero exit status,
  and no reads or writes of the archive or source paths.
- **FR-023**: The `list` and `extract` commands MUST keep their current observable behaviour
  exactly: the same operands and options, the same standard-output content, the same diagnostics,
  and the same exit statuses as before this feature.
- **FR-024**: The tool's usage output MUST name all three commands, their operands, and the
  `--overwrite` option, so the whole interface is discoverable from the tool itself.
- **FR-025**: Every functional requirement in this section MUST be covered by at least one
  automated test that fails when the requirement is unmet, with the covering test traceable to the
  requirement identifier, and the pre-existing tests for `list` and `extract` MUST continue to
  pass unmodified.
- **FR-026**: Member order MUST be fully determined by the invocation and the source tree, with no
  dependence on the order the filesystem happens to report directory entries. The members
  contributed by each `PATH` MUST be stored sorted by their full member name, compared as text —
  so `d`, `d/a.txt`, `d/b/c.txt`, `d/z.txt`, in that order — which also places a directory before
  the entries inside it. `PATH` operands MUST contribute their members in the order the operands
  were given. Archiving an unchanged tree with an unchanged invocation MUST therefore produce the
  same member sequence every time.
- **FR-027**: When the directory that would hold `ARCHIVE` does not exist, `create` MUST write an
  error message naming it to standard error, MUST create no archive and no directories, and MUST
  exit with status 2, identically with and without `--overwrite`. `create` MUST NOT create any
  directory under any circumstances: the archive file is the only thing it writes.

### Key Entities

- **Archive**: the file named by `ARCHIVE`. For `list` and `extract` it is input; for `create` it
  is the single output the command produces. Its name alone decides whether `create` compresses
  it; its content alone decides how `list` and `extract` read it.
- **Source path**: one `PATH` operand — a file or directory relative to the current directory.
  Supplies one or many members and is only ever read.
- **Member**: one entry in an archive, named by its relative path, with a type (regular file,
  directory, or other) and, for regular files, contents. The order in which members are stored is
  observable through `list` and is fully determined (FR-026): `PATH` operands contribute in the
  order they were given, and each operand's members are sorted by full member name as text.
- **Exit status**: the tool's machine-readable outcome — 0 for success, 3 for a refused overwrite
  of an existing archive, 2 for an unusable archive path, source path, or invocation. Exactly one
  status per run; when a run exhibits problems of both non-zero classes, 2 wins over 3.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can package any combination of files and directories from their current
  directory into one archive with a single command, and 100% of the regular files beneath the
  named paths appear as members under their relative paths.
- **SC-002**: For an archive created from a known tree and then extracted into a fresh
  destination, a comparison against the original tree shows zero differences in relative paths and
  zero differences in file bytes — for both the compressed and the uncompressed form.
- **SC-003**: The file count reported by `create` equals the number of regular-file members the
  archive actually holds, in 100% of runs.
- **SC-004**: Across every collision scenario exercised, the number of pre-existing files replaced
  or modified without the overwrite option being given is zero.
- **SC-005**: Each of the three documented outcomes — success, refused overwrite, unusable input —
  is distinguishable by exit status alone, with no overlap, in 100% of trials, including runs that
  exhibit more than one problem at once.
- **SC-006**: Every failing `create` run writes at least one non-empty diagnostic to standard
  error, writes nothing to standard output, and — for every failure the tool detects before
  writing — leaves no file at the archive path that was not there beforehand and creates no
  directory anywhere.
- **SC-007**: An archive whose name ends in `.tar.gz` or `.tgz` is gzip-compressed and every other
  archive is not, in 100% of runs, verifiable from the archive's own bytes.
- **SC-008**: Every archive produced by `create` is accepted by `list` and by `extract` with no
  diagnostics and exit status 0, in 100% of trials.
- **SC-009**: The complete pre-existing behaviour of `list` and `extract` is unchanged: their
  entire existing automated test suite passes without a single test being modified.
- **SC-010**: Creating an archive of 10,000 small files completes in under 10 seconds. Peak
  additional memory stays independent of both file count and file size: archiving a file of tens
  of megabytes raises peak memory by no more than a small fixed ceiling that does not grow with
  the file, so an implementation that holds a whole file or a whole archive in memory fails this
  criterion. That bounded measurement stands in for the untestable absolute — it is the property a
  file larger than available memory depends on.
- **SC-011**: Every functional requirement is traceable to at least one automated test that fails
  when that requirement is violated, with no requirement left uncovered.
- **SC-012**: Archiving the same unchanged tree with the same invocation produces the same member
  sequence in 100% of runs, independent of the order the filesystem reports directory entries.

## Assumptions

### Behavioural defaults chosen where the description was silent

- **Validation precedes writing**: the archive path and every source path are checked before the
  archive file is created, which is what makes "creates no archive" achievable for a missing path
  and matches the pre-write validation `001-tarx-cli` already established for `extract`. The
  alternative — writing members until a bad path is hit — would leave a partial archive behind.
- **Validation, not rollback, is the safety mechanism**: as in `001-tarx-cli` FR-022, unexpected
  filesystem errors *during* writing are not undone. The limit is stated in FR-021 rather than
  hidden, and an incomplete archive is explicitly not to be trusted. Because rollback is off the
  table, validation is made as complete as it can be: it traverses the whole source tree and
  establishes that every entry is readable before the archive is opened, so an unreadable file
  deep in a tree is a clean refusal rather than a partial archive. The cost is one extra traversal
  of the source tree, which is well inside the budget in SC-010; the benefit is that every failure
  the tool can foresee leaves the filesystem untouched.
- **Compression by name, reading by content**: `create` selects compression from the archive's
  name because the description says so, while `list` and `extract` keep detecting it from content.
  The two rules do not conflict: the name is load-bearing only at creation time.
- **Extension matching is literal and case-sensitive**: `.tar.gz` and `.tgz` in lower case select
  compression; `PHOTOS.TAR.GZ` does not. A literal rule is predictable and matches the wording of
  the description; nothing is lost, because a plain archive under a compressed-looking name is
  still read correctly by `list` and `extract`.
- **Non-regular entries are skipped, loudly**: the description scopes creation to "a file or a
  directory", so symbolic links, device nodes, FIFOs and sockets are not stored. Each skip is
  reported on standard error so the outcome is never silent, but a skip is not a failure — exactly
  the stance `extract` already takes on the same member types. This applies equally to an entry
  found while walking a directory and to a `PATH` that names such an entry directly.
- **Hard links are a reading concept, not a writing one**: when `extract` reads an archive, a
  hard-link member is a distinct member type it can recognise and skip. When `create` writes one,
  there is no such thing to recognise: every name in a directory listing that resolves to file
  contents is a regular file, and "which one is the original" is not a question the filesystem can
  answer. Treating the second name as a skippable link would therefore drop one of the user's
  files from the archive and leave `extract` rebuilding an incomplete tree — a silent wrong answer
  of exactly the kind Constitution Principle II forbids. Each name is stored instead, at the cost
  of duplicated bytes in the rare tree that uses hard links.
- **Symbolic links are not followed**: a link to a file or directory is skipped as a non-regular
  entry rather than dereferenced, so the archive never silently holds a second copy of data or
  descends outside the current directory through a link.
- **Source path safety**: absolute paths and paths that resolve above the current directory are
  refused rather than rewritten, because a member name derived from them could not be a relative
  path (FR-004) and `extract` would refuse the resulting archive as unsafe. The safety check is
  lexical, so its verdict is a property of the operand rather than of the filesystem.
- **Member order is sorted, not filesystem order**: directory entries are stored sorted by full
  member name as text rather than in the order the filesystem reports them, because an arbitrary
  order would make the archive differ between machines and runs for the same tree and would reduce
  every ordering check to a weaker set comparison. Sorting the full member name, rather than
  sorting within each directory, is what places a directory immediately before the entries inside
  it without a separate rule. Operand order still governs the top level, so what the user typed
  remains visible in the result.
- **Overlap is de-duplicated silently**: naming overlapping paths (`photos` and `photos/a.jpg`) is
  a convenience, not an error, so each file is stored once and counted once. Storing duplicates
  would make `N` disagree with the archive's content and would leave `extract` writing the same
  file twice.
- **The archive excludes itself**: writing an archive into a directory that is being archived is
  allowed, with the archive file omitted from its own contents, because including a file while it
  is being written could only store garbage.
- **`create` writes one file and creates no directories**: the archive is the command's single
  output, so a missing parent directory is refused rather than created (FR-027). This differs from
  `extract`, which does create its `DEST` with missing parents — but there the user has named a
  directory they are asking to have filled, whereas here they have named a file. Refusing also
  keeps FR-016's promise literally true: a run the tool rejects leaves nothing at all behind, not
  even an empty directory from a mistyped path.
- **`--overwrite` scope**: it consents to replacing a regular file at `ARCHIVE` and nothing else.
  It never removes a directory and never resolves a type mismatch (FR-012) — the same boundary
  `--overwrite` has in `extract`.
- **Usage errors use status 2**, matching `001-tarx-cli` FR-017.
- **Metadata is not preserved**: as with `extract`, permissions, ownership and timestamps are out
  of scope; stored members carry whatever defaults the archive format requires.
- **The option name is shared, not reinterpreted**: `--overwrite` means "replace what is already
  there, at my request" for both `extract` and `create`; it applies to the destination each command
  writes.
- **Scope boundary**: `create` takes one archive and a list of paths. Exclusion patterns, globbing
  beyond whatever the shell performs, compression levels, appending to or updating an existing
  archive, and archive formats other than tar and gzipped tar are all out of scope.

### Constraints inherited from the existing feature

These were set by `001-tarx-cli` and the project constitution and continue to apply; they are
implementation constraints rather than user-facing requirements.

- The tool is invoked as `python -m tarx COMMAND ...`, with the code in the `tarx` package under
  `src/` and `src/` on `PYTHONPATH`.
- Python 3.11 or newer, standard library only — no third-party runtime dependencies.
- `pytest` is the only sanctioned test runner, and every requirement is traceable to a test.

### Environment assumptions

- The directory that will hold `ARCHIVE` already exists and the user has write permission on it,
  and the user has read permission on the paths they name; a missing directory (FR-027) or a
  permission failure surfaces as an unusable-input diagnostic rather than a traceback.
- Source files are on the local filesystem and are not being modified by another process while the
  archive is written; the archive reflects the bytes read at the time each file was read.
- The terminal or consuming script treats standard output and standard error as separate streams,
  which is what makes the stream split above useful.
