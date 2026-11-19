# Feature Specification: Bookmark Manager CLI

**Feature Branch**: `001-bookmark-manager-cli`

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "Build a command-line bookmark manager that stores bookmarks in an SQLite database. Run it as `python -m bookmarks [--db PATH] COMMAND ...` with commands add, list, search, delete and export; tab-separated output for list/search; CSV and JSON export; validation of URL scheme with exit status 2; missing-id deletion with exit status 3."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Save a bookmark and get it back later (Priority: P1)

Someone finds a page worth keeping. They run the tool with the page address, optionally giving it a readable name and a few labels. The tool answers with a number that identifies the saved bookmark. Later — in a different session, on a different day — they ask the tool to show everything they have saved, and the bookmark is still there with its name and labels intact.

**Why this priority**: Without storing and recalling bookmarks there is no product. This single story is a usable tool on its own: capture and review.

**Independent Test**: Run the add command twice against a fresh, empty store, then run the list command in a separate invocation. Fully testable without search, delete or export existing.

**Acceptance Scenarios**:

1. **Given** no store file exists at the chosen location, **When** the user adds a bookmark for `https://docs.python.org` with the name "Python docs" and the labels `python,docs`, **Then** the tool creates the store, prints `1`, and finishes successfully.
2. **Given** one bookmark already stored, **When** the user adds a second bookmark with no name and no labels, **Then** the tool prints `2` and finishes successfully.
3. **Given** two bookmarks stored by earlier, separate invocations, **When** the user lists bookmarks, **Then** both are printed in ascending identifier order, one per line, each as four tab-separated fields — identifier, address, name, labels joined by commas in alphabetical order — with an empty name and empty label field shown as empty text.
4. **Given** an empty store, **When** the user lists bookmarks, **Then** nothing is printed and the command finishes successfully.
5. **Given** a bookmark whose address does not begin with `http://` or `https://`, **When** the user tries to add it, **Then** the tool prints a diagnostic naming the rejected address and the expected form on the diagnostic stream, prints nothing on the result stream, stores nothing, and reports failure code 2.

---

### User Story 2 - Find the bookmark I am looking for (Priority: P2)

Once a collection grows past a screenful, reading the whole list stops working. The user narrows it down two ways: by a label they assigned, or by typing part of a name or address they half remember, without worrying about capitalization.

**Why this priority**: Retrieval value grows with collection size. It depends on bookmarks existing (P1) but nothing else depends on it.

**Independent Test**: Seed a store with several bookmarks carrying different labels, then run the label-filtered listing and the text search and check which lines come back.

**Acceptance Scenarios**:

1. **Given** bookmarks where some carry the label `python`, **When** the user lists with the label filter `python`, **Then** only those bookmarks are printed, in ascending identifier order, in the same four-field layout as an unfiltered listing.
2. **Given** a label filter naming a label no bookmark carries, **When** the user lists, **Then** nothing is printed and the command finishes successfully.
3. **Given** a bookmark named "Python docs" at `https://docs.python.org`, **When** the user searches for `PYTHON`, **Then** that bookmark is printed, demonstrating that capitalization is ignored.
4. **Given** bookmarks whose addresses contain the search text but whose names do not, **When** the user searches, **Then** those bookmarks are printed — the text is matched against name and address alike.
5. **Given** search text that appears nowhere, **When** the user searches, **Then** nothing is printed and the command finishes successfully.

---

### User Story 3 - Remove a bookmark I no longer want (Priority: P3)

Links rot and interests move on. The user names the identifier of a bookmark and it is gone from every later listing, search and export. Naming an identifier that is not there is reported as a mistake rather than silently accepted.

**Why this priority**: Pruning matters, but a collection stays useful without it longer than it stays useful without retrieval.

**Independent Test**: Add bookmarks, delete one by identifier, list the remainder; separately delete an identifier that was never issued and check the diagnostic and failure code.

**Acceptance Scenarios**:

1. **Given** bookmarks 1 and 2 stored, **When** the user deletes bookmark 1, **Then** the command finishes successfully and a later listing shows only bookmark 2.
2. **Given** no bookmark with identifier 99, **When** the user deletes identifier 99, **Then** the tool prints a diagnostic naming identifier 99 on the diagnostic stream, changes nothing in the store, and reports failure code 3.
3. **Given** bookmark 1 was deleted, **When** the user deletes identifier 1 again, **Then** the tool reports failure code 3 with a diagnostic.
4. **Given** bookmark 2 is the highest identifier and is then deleted, **When** the user adds a new bookmark, **Then** the new bookmark receives an identifier greater than every identifier previously issued — identifiers are never reused.

---

### User Story 4 - Take the collection somewhere else (Priority: P3)

The user wants the whole collection in a form another program can read: a spreadsheet-friendly table, or structured data for a script.

**Why this priority**: Valuable for portability and backup, but nothing in daily use depends on it.

**Independent Test**: Seed a store, run each export form, and check the produced text against the required layout.

**Acceptance Scenarios**:

1. **Given** bookmarks in the store, **When** the user exports in table form, **Then** the output begins with the header line `id,url,title,tags` followed by one row per bookmark in ascending identifier order, with each bookmark's labels joined by commas in alphabetical order in the final column.
2. **Given** a bookmark whose name contains a comma or a quotation mark, or a bookmark carrying more than one label, **When** the user exports in table form, **Then** the affected fields are quoted so that a standard table reader recovers the original values exactly.
3. **Given** bookmarks in the store, **When** the user exports in structured form, **Then** the output is a single list of records in ascending identifier order, each record carrying the identifier as a number, the address, the name, and the labels as a list of separate values in alphabetical order.
4. **Given** an empty store, **When** the user exports in table form, **Then** only the header line is printed; **When** the user exports in structured form, **Then** an empty list is printed. Both finish successfully.
5. **Given** an export form that is neither of the two supported forms, **When** the user requests it, **Then** the tool prints a diagnostic on the diagnostic stream and reports a non-zero failure code.

---

### Edge Cases

- **Address rejected**: any address not beginning with `http://` or `https://` — including `ftp://example.com`, a bare `example.com`, empty text, or text where the scheme appears later in the string — is rejected before anything is stored, with failure code 2.
- **Store does not exist yet**: the first command that needs the store creates it, including when `--db` points at a path whose file is absent. A path whose parent directory does not exist is a failure, reported with a diagnostic and a non-zero code.
- **No `--db` given**: the store is the file `bookmarks.db` in the directory the command was run from, so running from two different directories uses two different collections.
- **Existing store**: a store created by an earlier run is opened and added to, never reset or overwritten.
- **Empty and whitespace-only labels**: `--tags "python,,docs"`, `--tags ""`, and surrounding spaces produce the label set that a reader would expect — no empty label is ever stored or printed.
- **Duplicate labels on one bookmark**: naming the same label twice leaves the bookmark carrying it once.
- **Label order**: labels are always printed in alphabetical order regardless of the order they were supplied in.
- **Same address added twice**: both bookmarks are kept, each with its own identifier; addresses are not required to be unique.
- **Empty name**: a bookmark added without a name has an empty name field in listings, searches and exports — not a placeholder.
- **Search text that is empty**: matches every bookmark, since every name and address contains empty text.
- **Label filter matches whole labels only**: filtering by `py` does not return a bookmark labelled `python`.
- **Identifier that is not a number**: deleting with a non-numeric identifier is reported as a usage mistake with a diagnostic and a non-zero code, distinct from a successful deletion.
- **Name or label containing a tab or newline**: stored and returned unchanged; the specification does not require escaping in the tab-separated listing, but table and structured exports must still round-trip such values.

## Requirements *(mandatory)*

### Functional Requirements

**Invocation and storage**

- **FR-001**: The tool MUST be invocable as `python -m bookmarks [--db PATH] COMMAND ...` and MUST support the commands `add`, `list`, `search`, `delete` and `export`.
- **FR-002**: The tool MUST store bookmarks in a single SQLite database file, which MUST be the path given by `--db` when present and `bookmarks.db` in the current working directory otherwise.
- **FR-003**: The tool MUST create the database file and its structure when it does not already exist, and MUST open an existing file without destroying its contents.
- **FR-004**: Bookmarks MUST persist across separate invocations of the tool.

**Adding**

- **FR-005**: `add URL` MUST store a bookmark and print its identifier, and nothing else, on standard output.
- **FR-006**: Identifiers MUST start at 1 for the first bookmark in a database and MUST increase; an identifier that has been issued MUST NOT be issued again, including after the bookmark holding it is deleted.
- **FR-007**: `add` MUST reject any URL that does not begin with the literal text `http://` or `https://`, writing a diagnostic naming the rejected URL and the accepted schemes to standard error, storing nothing, and exiting with status 2.
- **FR-008**: `--title TITLE` MUST set the bookmark's title; when omitted the title MUST be the empty string.
- **FR-009**: `--tags TAGS` MUST interpret TAGS as a comma-separated list of tags (for example `python,cli`); when omitted the bookmark MUST have no tags.
- **FR-010**: Tag parsing MUST discard empty entries, MUST trim surrounding whitespace from each tag, and MUST store each distinct tag at most once per bookmark.

**Listing and searching**

- **FR-011**: `list` MUST print every bookmark in ascending identifier order.
- **FR-012**: `list --tag TAG` MUST print only bookmarks carrying a tag exactly equal to TAG, in ascending identifier order.
- **FR-013**: `search TEXT` MUST print every bookmark whose title or URL contains TEXT when capitalization is disregarded, in ascending identifier order.
- **FR-014**: `list` and `search` MUST print one bookmark per line as exactly four tab-separated fields in this order: identifier, URL, title, and the bookmark's tags joined by commas in alphabetical order. A bookmark with no tags MUST have an empty fourth field.
- **FR-015**: `list` and `search` that match no bookmarks MUST print nothing on standard output and exit with status 0.

**Deleting**

- **FR-016**: `delete ID` MUST remove the bookmark with that identifier, together with its tags, so that it no longer appears in any later listing, search or export.
- **FR-017**: `delete ID` where no bookmark holds that identifier MUST write a diagnostic naming the identifier to standard error, leave the store unchanged, and exit with status 3.

**Exporting**

- **FR-018**: `export --format csv` MUST print the header line `id,url,title,tags` followed by one row per bookmark in ascending identifier order, with the tags column holding that bookmark's tags joined by commas in alphabetical order.
- **FR-019**: CSV output MUST quote fields as needed so that values containing commas, quotation marks or line breaks are recovered unchanged by a standard CSV reader.
- **FR-020**: `export --format json` MUST print a single JSON array of objects, in ascending identifier order, each with the keys `id` (a number), `url`, `title` and `tags` (an array of strings in alphabetical order).
- **FR-021**: Export of an empty store MUST print the header line alone in CSV form and an empty array in JSON form, exiting with status 0 in both cases.

**Exit statuses and streams**

- **FR-022**: Every command that completes its work MUST exit with status 0.
- **FR-023**: All command results MUST be written to standard output and all diagnostics to standard error; a failing command MUST NOT write partial results to standard output.
- **FR-024**: Status 2 MUST be used for a rejected URL and status 3 for deleting an identifier that does not exist. Other usage mistakes — an unknown command, a missing required argument, a non-numeric identifier, an unsupported export format — MUST produce a diagnostic on standard error and a non-zero exit status.

**Platform**

- **FR-025**: The tool MUST run on Python 3.11 or newer using only the Python standard library, with no third-party runtime dependency.
- **FR-026**: The code MUST live in a package named `bookmarks` under `src/`, runnable as `python -m bookmarks` when `src/` is on `PYTHONPATH`.
- **FR-027**: Every functional requirement above MUST be covered by at least one automated pytest test that identifies the requirement it covers, per the project constitution.

### Key Entities

- **Bookmark**: one saved web address. Carries an identifier unique within the store and never reused, the URL, a title (possibly empty), and a set of tags (possibly empty). Ordering among bookmarks is by identifier.
- **Tag**: a short label attached to a bookmark. A bookmark carries each tag at most once; a tag may be shared by many bookmarks. Tags have no meaning beyond grouping and are presented in alphabetical order.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who has never used the tool can save their first bookmark and see it listed with two commands and no configuration step.
- **SC-002**: Bookmarks saved in one session are returned unchanged in a later session: for a store of 1,000 bookmarks, listing returns all 1,000 with identical URLs, titles and tags.
- **SC-003**: Every listing, search and export returns bookmarks in ascending identifier order and every tag group in alphabetical order, in 100% of cases.
- **SC-004**: 100% of URLs lacking an `http://` or `https://` prefix are refused, with nothing stored and failure signalled by exit status 2, verified across at least five differently malformed inputs.
- **SC-005**: Deleting an identifier that does not exist signals failure by exit status 3 and leaves the stored collection byte-for-byte unchanged, in 100% of attempts.
- **SC-006**: CSV and JSON exports of a collection containing commas, quotation marks, multiple tags and empty titles are read back by standard tools with no value altered or lost.
- **SC-007**: Each command on a store of 1,000 bookmarks returns its result in under one second on ordinary hardware.
- **SC-008**: Every functional requirement is demonstrated by at least one automated test, and the full suite passes.

## Assumptions

- The tool serves one person working in a terminal on their own machine; concurrent use of the same store by several processes is out of scope, as are multi-user accounts and synchronisation.
- Scheme validation is a literal prefix check for `http://` and `https://`, matching the stated requirement; no further URL structure is validated and the address is not fetched or checked for reachability.
- URLs are not required to be unique — the same address may be saved more than once, each time receiving its own identifier — because the description gives no de-duplication rule.
- Identifiers are never reused after deletion, matching the stated rule that identifiers "start at 1 and increase".
- Tag matching in `list --tag` is exact and case-sensitive; only `search` is specified as ignoring capitalization.
- Tags are stored as given apart from trimming surrounding whitespace, dropping empty entries, and collapsing exact duplicates; no case folding or other normalisation is applied.
- Alphabetical tag ordering is the standard ordering of the stored text, which for the plain lowercase tags in the examples is ordinary alphabetical order.
- `list` and `search` emit raw tab-separated fields with no escaping, as shown in the examples; a title containing a tab would therefore be ambiguous in that view, which is accepted because the lossless views are the CSV and JSON exports.
- Output is plain text on standard output with no colour, paging or interactive prompting, so the tool composes with other command-line tools.
- There is no update or edit command, no import, and no archiving of page content; the five listed commands are the whole scope.
- pytest is available for development and testing; it is not imported by the shipped code, per the project constitution.
