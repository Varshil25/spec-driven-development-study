# Feature Specification: Command-Line Bookmark Manager

**Feature Branch**: `001-bookmark-manager-cli`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "Build a command-line bookmark manager that stores bookmarks in an SQLite database. Run it as `python -m bookmarks [--db PATH] COMMAND ...` with commands `add`, `list`, `search`, `delete`, and `export`, tab-separated listing output, CSV/JSON export, URL scheme validation with exit status 2, missing-id failure with exit status 3, Python 3.11+ standard library only, package `bookmarks` under `src/`."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Save a bookmark and see it again later (Priority: P1)

A person working in a terminal finds a page worth keeping. They record it with a single
command, optionally giving it a title and tags, and get back a short numeric identifier they
can use later. On a later run — in a new process, possibly days later — they list their
bookmarks and the saved entry is still there, in the order it was added.

**Why this priority**: Without durable capture and recall there is no product. This story
alone is a usable bookmark manager.

**Independent Test**: Run the tool to add two bookmarks, let the process exit, run it again
to list them, and confirm both appear with their ids, URLs, titles and tags. Fully testable
without `search`, `delete` or `export` existing.

**Acceptance Scenarios**:

1. **Given** no database file exists at the chosen location, **When** the user adds a
   bookmark with a URL, a title and the tags `python,docs`, **Then** the database is created,
   the bookmark is stored, the identifier `1` is printed on standard output, and the exit
   status is 0.
2. **Given** one bookmark already exists, **When** the user adds a second bookmark with no
   title and no tags, **Then** the identifier `2` is printed and the exit status is 0.
3. **Given** two bookmarks exist, **When** the user lists bookmarks in a new invocation,
   **Then** both are printed, one per line, ordered by ascending identifier, each line
   holding four tab-separated fields (identifier, URL, title, comma-joined tags in
   alphabetical order), with empty fields for the missing title and tags.
4. **Given** no database location is supplied, **When** the user adds a bookmark, **Then**
   the bookmark is stored in `bookmarks.db` in the current working directory.
5. **Given** a URL that does not begin with `http://` or `https://`, **When** the user tries
   to add it, **Then** an error message is written to standard error, nothing is written to
   standard output, no bookmark is stored, and the exit status is 2.

---

### User Story 2 - Find a bookmark among many (Priority: P2)

Once a collection grows past a screenful, listing everything is useless. The person recalls
a fragment of a title or URL, or remembers only which tag they filed it under, and narrows
the collection down to the handful of entries that match.

**Why this priority**: Retrieval is what makes a growing collection worth keeping, but it is
only valuable once capture (P1) works.

**Independent Test**: Seed several bookmarks with distinct titles, URLs and tags, then run a
case-insensitive text search and a tag-filtered listing and confirm only the matching
entries are printed, in identifier order.

**Acceptance Scenarios**:

1. **Given** bookmarks with titles and URLs of mixed letter case, **When** the user searches
   for `PYTHON`, **Then** every bookmark whose title or URL contains `python` in any letter
   case is printed, ordered by ascending identifier, in the same four-field tab-separated
   format as listing, and the exit status is 0.
2. **Given** bookmarks with assorted tags, **When** the user lists with a tag filter,
   **Then** only bookmarks carrying exactly that tag are printed, ordered by ascending
   identifier, and the exit status is 0.
3. **Given** no bookmark matches, **When** the user searches or filters by tag, **Then**
   nothing is printed on standard output, nothing is written to standard error, and the exit
   status is 0.
4. **Given** a bookmark whose title contains the literal characters `%` or `_`, **When** the
   user searches for text containing those characters, **Then** they are matched literally
   rather than as pattern wildcards.

---

### User Story 3 - Remove a bookmark that is no longer wanted (Priority: P3)

Links rot and interests move on. The person deletes an entry by its identifier and sees it
disappear from later listings, while every other entry — and every other entry's identifier
— stays exactly as it was.

**Why this priority**: Pruning keeps the collection trustworthy, but a collection is useful
before it can be pruned.

**Independent Test**: Add three bookmarks, delete the middle one, list the rest, and confirm
the remaining two keep their original identifiers; then attempt to delete an identifier that
does not exist and confirm the documented failure.

**Acceptance Scenarios**:

1. **Given** bookmarks with identifiers 1, 2 and 3, **When** the user deletes identifier 2,
   **Then** the exit status is 0 and a later listing prints only identifiers 1 and 3 with
   their original URLs, titles and tags.
2. **Given** identifier 2 has already been deleted, **When** the user deletes identifier 2
   again, **Then** an error message is written to standard error and the exit status is 3.
3. **Given** the highest identifier ever issued is 3 and bookmark 3 has been deleted,
   **When** the user adds a new bookmark, **Then** it receives identifier 4 — a deleted
   identifier is never reissued.
4. **Given** any state, **When** the user deletes a bookmark, **Then** the deletion survives
   process exit and is visible to the next invocation.

---

### User Story 4 - Hand the collection to another tool (Priority: P4)

The person wants their bookmarks somewhere else: a spreadsheet, a script, another
application. They export the whole collection in a machine-readable form on standard output
and pipe it onward.

**Why this priority**: Export protects the user from lock-in and enables scripting, but it
operates on a collection the earlier stories already produce.

**Independent Test**: Seed bookmarks with and without titles and tags, export as CSV and as
JSON, and confirm both outputs parse with a standard parser and carry every stored bookmark
with its identifier, URL, title and tags.

**Acceptance Scenarios**:

1. **Given** stored bookmarks, **When** the user exports as CSV, **Then** standard output
   begins with the header line `id,url,title,tags` followed by one row per bookmark in
   ascending identifier order, with tags comma-joined in alphabetical order inside the single
   `tags` field, and the exit status is 0.
2. **Given** stored bookmarks, **When** the user exports as JSON, **Then** standard output
   is a JSON array of objects with keys `id` (a number), `url`, `title` and `tags` (an array
   of strings), in ascending identifier order, and the exit status is 0.
3. **Given** a bookmark whose title contains a comma, a double quote or a newline, **When**
   the user exports as CSV or JSON, **Then** the output remains parseable by a standard
   parser and the title is recovered unchanged.
4. **Given** an empty collection, **When** the user exports, **Then** CSV output is the
   header line alone and JSON output is an empty array, with exit status 0.

---

### Edge Cases

- **Database absent, empty, or in a new directory**: a missing database file is created on
  first use; a database that exists but holds no bookmarks yields empty `list`/`search`
  output and header-only / empty-array exports. A `--db` path whose parent directory does not
  exist is a failure (exit status 1), not a silently created directory tree.
- **Rejected URLs**: empty string, whitespace only, `ftp://example.com`,
  `javascript:alert(1)`, `file:///etc/passwd`, `data:text/html,x`, `example.com`,
  `//example.com`, `HTTPS://example.com` (uppercase scheme), and `http:/example.com` are all
  rejected with exit status 2 and nothing stored.
- **Degenerate tag input**: `--tags ""`, `--tags ","`, `--tags "a,,b"`, `--tags " a , b "`
  and `--tags "a,a"` must all resolve to a definite tag set (see FR-012) rather than
  producing empty-string tags or duplicates.
- **Duplicate URLs**: adding the same URL twice is permitted and produces two bookmarks with
  distinct identifiers (see Assumptions).
- **Malformed identifier for `delete`**: `abc`, `1.5`, `-1`, `0` and an absent argument are
  argument-validation failures (exit status 2), distinct from a well-formed identifier that
  does not exist (exit status 3).
- **Unknown command, unknown option, or missing required argument**: usage error on standard
  error with exit status 2; nothing is read or written in the database.
- **`export` without `--format`, or with an unsupported format**: usage error on standard
  error with exit status 2.
- **Oversized input**: a URL, title, tag or search string beyond the documented limits is
  rejected with exit status 2 rather than stored (see SR-006).
- **Adversarial text**: SQL metacharacters (`'); DROP TABLE bookmarks;--`) in any text input
  are stored and matched as literal text; the database stays intact.
- **Tabs and newlines in a title**: the tab-separated `list`/`search` format cannot represent
  them unambiguously; see Assumptions for the chosen behaviour.
- **Unreadable or corrupt database file**: reported as an error on standard error with a
  non-zero exit status (1), never as an empty collection.

## Requirements *(mandatory)*

### Functional Requirements

**Invocation and storage**

- **FR-001**: The system MUST be invocable as `python -m bookmarks [--db PATH] COMMAND ...`
  with the subcommands `add`, `list`, `search`, `delete` and `export`.
- **FR-002**: The system MUST use the file given by `--db PATH` as its database, and MUST
  default to `bookmarks.db` in the current working directory when `--db` is absent.
- **FR-003**: The system MUST create the database file and its schema when the file does not
  exist, and MUST reuse the existing file otherwise, so that bookmarks persist across
  invocations.
- **FR-004**: Every successful command MUST exit with status 0.
- **FR-005**: Every error MUST write a human-readable message describing what was wrong to
  standard error, MUST leave standard output free of that message, and MUST exit non-zero:
  status 2 for invalid arguments or input (including an invalid URL), status 3 for a
  `delete` naming an identifier that does not exist, status 1 for any other failure such as
  an unusable database file.

**Adding**

- **FR-006**: `add URL [--title TITLE] [--tags TAGS]` MUST store a bookmark and print its
  numeric identifier, and nothing else, on standard output.
- **FR-007**: Identifiers MUST start at 1 and strictly increase with each added bookmark;
  an identifier MUST NOT be reused after its bookmark is deleted.
- **FR-008**: `add` MUST accept a URL only if it begins with the exact lowercase prefix
  `http://` or `https://`; every other value MUST be rejected under FR-005 with exit status
  2, and no bookmark, tag, or identifier MUST be created by a rejected `add`.
- **FR-009**: `--title` MUST default to the empty string when omitted.
- **FR-010**: `--tags` MUST accept a comma-separated list such as `python,cli`, and MUST
  default to no tags when omitted.
- **FR-011**: The system MUST NOT otherwise restrict the URL beyond FR-008 and SR-006 — no
  reachability check, no DNS lookup, no network access of any kind.
- **FR-012**: Tag parsing MUST split `--tags` on commas, strip leading and trailing
  whitespace from each entry, discard entries that are then empty, and keep each distinct tag
  only once, so that `" a , b "`, `"a,,b"` and `"a,b,a"` all yield the tag set `{a, b}`.

**Listing, filtering and searching**

- **FR-013**: `list` MUST print every stored bookmark in ascending identifier order.
- **FR-014**: `list --tag TAG` MUST print only the bookmarks carrying the tag `TAG`, matched
  as an exact (case-sensitive) string against the stored tags, in ascending identifier order.
- **FR-015**: `search TEXT` MUST print every bookmark whose title or URL contains `TEXT` as a
  case-insensitive substring, in ascending identifier order.
- **FR-016**: `search` MUST treat `TEXT` as literal text: pattern metacharacters in `TEXT`
  (such as `%` and `_`) MUST match only themselves.
- **FR-017**: `list` and `search` MUST print one bookmark per line as exactly four
  tab-separated fields in this order: identifier, URL, title, and the bookmark's tags joined
  with commas in ascending alphabetical (code-point) order. Absent titles and absent tag sets
  MUST appear as empty fields, so a bookmark with neither yields a line ending in two
  consecutive tabs.
- **FR-018**: A `list` or `search` that matches nothing MUST print nothing and exit 0.

**Deleting**

- **FR-019**: `delete ID` MUST remove the bookmark with identifier `ID`, together with that
  bookmark's tag associations, and exit 0.
- **FR-020**: `delete ID` MUST leave all other bookmarks, their identifiers, titles and tags
  unchanged.
- **FR-021**: `delete ID` where no bookmark has identifier `ID` MUST report the error under
  FR-005 and exit with status 3, changing nothing.
- **FR-022**: `delete ID` where `ID` is not a well-formed positive integer MUST be rejected
  as an argument error with exit status 2.

**Exporting**

- **FR-023**: `export --format csv` MUST print, on standard output, the header row
  `id,url,title,tags` followed by one row per bookmark in ascending identifier order, with
  the `tags` field holding that bookmark's tags joined with commas in ascending alphabetical
  order.
- **FR-024**: `export --format json` MUST print, on standard output, a JSON array holding one
  object per bookmark in ascending identifier order, each with the keys `id` (a JSON number),
  `url` (string), `title` (string) and `tags` (an array of strings in ascending alphabetical
  order).
- **FR-025**: Both export formats MUST escape field content according to the rules of the
  format, so that a title or URL containing a comma, a double quote, a newline or a non-ASCII
  character round-trips unchanged through a standard CSV or JSON parser.
- **FR-026**: `export` MUST require `--format` and MUST reject any value other than `csv` or
  `json` as an argument error with exit status 2.
- **FR-027**: `export` on an empty collection MUST print the CSV header alone, or an empty
  JSON array, and exit 0.

### Security Requirements

Derived from the OWASP Top 10 (A01 Broken Access Control, A03 Injection, A04 Insecure
Design, A05 Security Misconfiguration, A09 Logging Failures) and OWASP ASVS chapters V5
(Validation, Sanitisation and Encoding), V7 (Error Handling and Logging) and V12 (Files and
Resources), as required by Constitution Principle V. Each is stated to be mechanically
testable and each requires at least one automated test, including the negative case.

- **SR-001**: All database access MUST use parameterised statements; no SQL MUST be built by
  concatenating or interpolating user-supplied text. Negative test: adding and then searching
  for a URL, title or tag containing `'); DROP TABLE bookmarks;--` MUST store and return that
  text literally and MUST leave the schema and all other rows intact.
- **SR-002**: URL acceptance MUST be allow-list based exactly as in FR-008. Negative tests:
  each of `javascript:alert(1)`, `file:///etc/passwd`, `data:text/html,x`, `ftp://host/`,
  `HTTPS://host/`, `example.com`, `//example.com`, `` (empty) and `   ` (whitespace) MUST be
  rejected with exit status 2 and MUST leave the collection unchanged.
- **SR-003**: Every other argument MUST be validated before use: `delete` accepts only a
  decimal positive integer within the supported identifier range, `export --format` accepts
  only `csv` or `json`, and unknown commands or options are refused. Negative test: each
  malformed value exits 2 and performs no database write.
- **SR-004**: Text search MUST NOT let user input act as a pattern (FR-016). Negative test: a
  search for `%` MUST NOT match a bookmark that lacks a literal `%`.
- **SR-005**: The database file MUST be created with owner-only read/write permission
  (`0600`) at creation time, because a bookmark collection is personal data. Test: after
  first use on a POSIX system, the file mode bits are exactly `0600`.
- **SR-006**: Every input MUST have an enforced maximum size, rejected under FR-005 with exit
  status 2: URL at most 8192 characters, title at most 4096 characters, `--tags` string at
  most 4096 characters with at most 64 tags of at most 128 characters each, search text at
  most 1024 characters. Negative test: input one character beyond each limit is rejected and
  nothing is stored.
- **SR-007**: Reading the collection MUST be bounded in memory per operation — `list`,
  `search` and `export` MUST stream rows to standard output rather than materialising the
  whole collection, so that output memory does not grow with collection size. Test: exporting
  a collection of at least 50,000 bookmarks completes without memory growth proportional to
  the collection.
- **SR-008**: Error messages, and all output, MUST NOT disclose internal detail beyond what
  the user needs: no stack traces on any expected failure path (invalid URL, missing
  identifier, bad argument, unusable database), and no SQL text in user-facing messages.
  Test: each expected failure path produces a single-line message on standard error and no
  traceback.
- **SR-009**: A rejected or failed command MUST leave the database in its prior state — each
  command's writes MUST be atomic (a bookmark and its tags are committed together or not at
  all). Test: an `add` that fails validation, and an interrupted multi-statement write, leave
  no partial row or orphan tag association.
- **SR-010**: The program MUST NOT execute a shell, spawn a subprocess, open a network
  connection, or read any configuration file influenced by the environment; its only inputs
  are its command-line arguments and the database file. Test: no `subprocess`, `socket`, or
  shell invocation exists in shipped code.
- **SR-011**: The database schema and file MUST be the only persistent state written; no
  temporary file containing bookmark data MUST be left behind after any command, successful
  or failed.

### Key Entities *(include if feature involves data)*

- **Bookmark**: one saved link. Attributes: a numeric identifier unique within the
  collection, strictly increasing and never reused; a URL (required, `http://` or `https://`);
  a title (text, empty when not supplied); and a set of tags. Ordering among bookmarks is by
  identifier.
- **Tag**: a short label attached to a bookmark. Attributes: its text. A bookmark has zero or
  more distinct tags; a tag may apply to many bookmarks. Within one bookmark, tags are a set —
  order is not stored, and alphabetical order is imposed only when the tags are displayed or
  exported.
- **Collection**: the whole set of bookmarks held in one database file, identified by its
  path. Two different paths are two independent collections that never interact.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can save their first bookmark with one command and no prior setup —
  no configuration file, no initialisation step, no installation of anything beyond a Python
  interpreter — and sees the new bookmark's identifier printed immediately.
- **SC-002**: 100% of the acceptance scenarios in User Stories 1–4 and 100% of the functional
  and security requirements (FR-001…FR-027, SR-001…SR-011) are covered by automated tests,
  and the whole suite passes.
- **SC-003**: Every bookmark added in one invocation is present, unchanged, in every later
  invocation against the same database path until it is deleted: a sequence of 1,000 mixed
  add and delete commands leaves exactly the expected collection, with zero lost or altered
  entries.
- **SC-004**: Each command on a collection of 10,000 bookmarks returns its output in under
  one second on ordinary developer hardware, so that the tool feels instant in interactive
  use.
- **SC-005**: Every documented invalid input produces a message on standard error that names
  the problem, and the documented exit status (2 for invalid input, 3 for an unknown
  identifier), with zero cases of a silent success or a silently empty result.
- **SC-006**: `list` and `search` output can be split into four fields per line by a
  tab-splitting one-liner, and `export` output parses with an off-the-shelf CSV or JSON
  parser on the first attempt, for 100% of collections free of tabs and newlines in titles.
- **SC-007**: A reviewer can confirm the standard-library-only constraint mechanically: the
  shipped package imports nothing outside the Python standard library.

## Assumptions

Reasonable defaults chosen where the feature description was silent. Each is a decision the
tests will pin down.

- **Duplicate URLs are allowed.** No uniqueness constraint was stated, so adding the same URL
  twice creates two independent bookmarks with different identifiers.
- **Tag matching is exact and case-sensitive.** `list --tag Python` does not match a bookmark
  tagged `python`. Tags are stored as supplied (after the trimming in FR-012) rather than
  case-folded, so that display reproduces what the user typed.
- **Alphabetical tag order means ascending code-point order**, the ordinary sort of the
  stored text. Uppercase therefore sorts before lowercase (`Docs,python`).
- **Search is case-insensitive over ASCII letters at minimum.** Full Unicode case folding is
  not required; matching titles and URLs that differ only in ASCII letter case is.
- **Tabs and newlines inside a title are stored and reproduced verbatim**, with no escaping,
  in `list`/`search` output. Such a title makes that one line ambiguous to split; CSV and
  JSON export remain unambiguous (FR-025). No input is rejected for containing them, because
  the feature description defines exit status 2 only for an invalid URL.
- **CSV output is data-faithful, not spreadsheet-hardened.** Fields are quoted per standard
  CSV rules, but a leading `=`, `+`, `-` or `@` in a title is not prefixed or altered,
  because the specified header and field contents require exact round-tripping. Consumers
  that feed the output into a spreadsheet macro engine are out of scope — recorded here as a
  documented deviation from the "encode for the destination context" baseline, with the
  functional requirement FR-025 taking precedence.
- **The `--db` path is operator-supplied and deliberately arbitrary.** It is a first-party
  command-line argument from the person running the tool, so the constitution's path
  containment control does not apply: there is no allowed base directory to confine it to.
  The path is used as a file path only — never as a shell word — and a path that cannot be
  opened or created is an error (exit status 1), not a silent fallback to the default.
- **Single-process use.** Concurrent invocations against one database file are not a target
  scenario; the storage engine's own file locking is relied upon, and no additional
  cross-process coordination is specified.
- **Identifier allocation is monotonic per collection**, provided by the storage engine's
  own row-identifier allocation, and survives deletion of the highest identifier.
- **Output encoding is UTF-8** on standard output for all four commands.
- **No network access, no reachability check, no title fetching.** A URL is text to be
  stored, not a resource to be retrieved.
- **Scope boundaries.** There is no update/edit command, no tag rename or delete command, no
  import command, no deduplication, no interactive mode, no colour or pagination, and no
  configuration file. Only the five specified commands exist.

### Technical Constraints *(given in the feature description, not derived)*

These are stated by the requester and bind the implementation; they are recorded here rather
than in the requirements above so that the requirements stay behavioural.

- Python 3.11 or newer, standard library only (which includes the bundled SQLite binding) —
  consistent with Constitution Principle I.
- Storage is an SQLite database file.
- The code lives in a package named `bookmarks` under `src/`, runnable as
  `python -m bookmarks` when `src/` is on `PYTHONPATH`.
- Automated tests use `pytest`, per Constitution Principle III.
