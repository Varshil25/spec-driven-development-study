# Feature Specification: Log Redaction CLI

**Feature Branch**: `001-logredact-cli`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "Build a command-line tool that removes personal data from log files before they are shared. Run it as `python -m logredact [--count] [FILE ...]`. It reads each FILE in the order given, or standard input when no FILE is given, and writes every line to standard output with emails replaced by `[EMAIL]`, IPv4 addresses by `[IP]`, and Luhn-valid 13-19 digit payment card numbers (optionally grouped by single spaces or hyphens) by `[CARD]`. Everything else is output unchanged. With `--count`, a summary `emails=N ips=N cards=N` is printed to standard error after all output. An unreadable FILE produces an error naming the file on standard error and exit status 2; otherwise exit status 0."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Redact a piped log stream (Priority: P1)

An engineer is about to paste a chunk of application log into a support ticket. They pipe the
text through the tool and get back the same log with every email address, IPv4 address, and
payment card number replaced by a fixed placeholder, so the text is safe to share while the
surrounding message, timestamps, and identifiers remain readable.

**Why this priority**: This is the core value of the feature — sanitised text out of arbitrary
text in. With only this story implemented the tool is already useful for the most common case
(ad-hoc piping), and every other story builds on the same redaction behaviour.

**Independent Test**: Pipe a log excerpt containing each kind of sensitive value on standard
input with no file arguments, and confirm standard output contains `[EMAIL]`, `[IP]`, and
`[CARD]` in place of those values, with all other characters on each line unchanged and the
line order preserved.

**Acceptance Scenarios**:

1. **Given** the single line `user jane@example.com from 10.0.0.7`, **When** the tool is run
   with no arguments and that line on standard input, **Then** standard output is
   `user [EMAIL] from [IP]` followed by a newline, and the exit status is 0.
2. **Given** the line `paid with 4111 1111 1111 1111, ref 1234567890123`, **When** the tool is
   run with no arguments, **Then** standard output is `paid with [CARD], ref 1234567890123` —
   the grouped Luhn-valid number is redacted and the Luhn-invalid 13-digit number is not.
3. **Given** a line with nothing to redact, such as `GET /health 200 in 4ms`, **When** the tool
   is run, **Then** standard output reproduces that line exactly, character for character.
4. **Given** a line containing `999.1.1.1`, **When** the tool is run, **Then** that text is
   left unchanged because at least one part exceeds 255.
5. **Given** empty input on standard input, **When** the tool is run, **Then** standard output
   is empty and the exit status is 0.

---

### User Story 2 - Redact one or more named log files (Priority: P2)

A release engineer needs to attach three rotated log files to an incident report. They pass all
three paths to the tool in chronological order and receive one sanitised stream on standard
output, in the same order as the arguments, which they redirect into a single file to attach.

**Why this priority**: Named files are the stated primary use ("log files"), but the redaction
engine from Story 1 is a prerequisite; file handling is a thin layer on top of it.

**Independent Test**: Create two small files with known sensitive content, run the tool with
both paths as arguments, and confirm standard output equals the redacted first file followed by
the redacted second file, with standard input ignored.

**Acceptance Scenarios**:

1. **Given** two readable files `a.log` and `b.log`, **When** the tool is run as
   `python -m logredact a.log b.log`, **Then** standard output contains all redacted lines of
   `a.log` followed by all redacted lines of `b.log`, and the exit status is 0.
2. **Given** the same two files passed in the reverse order, **When** the tool is run, **Then**
   the output order is reversed accordingly — argument order determines output order.
3. **Given** one readable file argument and content also available on standard input, **When**
   the tool is run with that file argument, **Then** standard input is not read and does not
   appear in the output.
4. **Given** a readable file whose last line has no trailing newline, **When** the tool is run,
   **Then** the corresponding output line also has no trailing newline added.
5. **Given** the same file path passed twice, **When** the tool is run, **Then** its redacted
   content appears twice in the output.

---

### User Story 3 - Report how much was redacted (Priority: P3)

A privacy reviewer wants evidence that a sanitisation pass actually found something, and how
much, without inspecting the output by hand. They add `--count` and read a one-line tally on
standard error, which they can capture separately from the sanitised data on standard output.

**Why this priority**: Valuable for auditing and for spot-checking that patterns are matching,
but the tool fully performs its protective job without it.

**Independent Test**: Run the tool with `--count` on input with a known number of each kind of
value, capture standard error separately from standard output, and confirm the tally line
matches the known counts while standard output is unaffected by the flag.

**Acceptance Scenarios**:

1. **Given** the line `a@b.io 1.2.3.4`, **When** the tool is run with `--count`, **Then**
   standard output is `[EMAIL] [IP]` and standard error is `emails=1 ips=1 cards=0`.
2. **Given** input with no redactable values, **When** the tool is run with `--count`, **Then**
   standard error is `emails=0 ips=0 cards=0` and the exit status is 0.
3. **Given** input where the same email address appears three times, **When** the tool is run
   with `--count`, **Then** the tally reports `emails=3` — occurrences are counted, not
   distinct values.
4. **Given** multiple file arguments and `--count`, **When** the tool is run, **Then** a single
   tally covering all files combined is printed once, after all sanitised output.
5. **Given** any input, **When** the tool is run without `--count`, **Then** standard error is
   empty.

---

### User Story 4 - Learn immediately when a log file cannot be read (Priority: P3)

Someone scripting a bulk sanitisation pass mistypes a path. Instead of silently producing a
short or empty result that looks successful, the tool names the offending file on standard
error and exits with a distinct non-zero status the script can detect.

**Why this priority**: A failure that looks like success is the most damaging outcome for a
privacy tool, but it only applies to the named-file mode introduced in Story 2.

**Independent Test**: Run the tool with a path that does not exist and confirm standard error
names that exact path, standard output contains no fabricated content, and the exit status is 2.

**Acceptance Scenarios**:

1. **Given** a path that does not exist, **When** the tool is run with it as the only argument,
   **Then** standard error contains a message naming that path, and the exit status is 2.
2. **Given** an existing file whose permissions deny reading, **When** the tool is run with it,
   **Then** standard error names that path and the exit status is 2.
3. **Given** two arguments where the first is readable and the second does not exist, **When**
   the tool is run, **Then** the redacted content of the first file has already been written to
   standard output, standard error names the second path, and the exit status is 2.
4. **Given** two arguments where the first does not exist and the second is readable, **When**
   the tool is run, **Then** processing stops at the first path: standard output contains no
   content from the second file, and the exit status is 2.
5. **Given** an unreadable path together with `--count`, **When** the tool is run, **Then** no
   tally line is printed and the exit status is 2.

---

### Edge Cases

- **Value split across lines**: a sensitive value whose text is broken by a line ending is not
  recognised; each line is redacted on its own.
- **Multiple values on one line**: every occurrence on a line is redacted, including adjacent
  ones such as `a@b.io 1.2.3.4`.
- **Overlapping candidates**: text that could be read as more than one kind of value is
  redacted once, under the precedence rule in FR-017 (for example `user@1.2.3.4` yields
  `user@[IP]`, because a bare dotted quad is not an accepted email domain).
- **IPv4 inside a longer dotted run**: `1.2.3.4.5` is left unchanged — it is not a four-part
  dotted quad bounded by non-digit, non-dot characters.
- **Sentence-final address**: `connect to 192.168.0.10.` is redacted to `connect to [IP].` —
  the trailing sentence period is not part of the address.
- **Digit run longer than 19**: a 20+ digit run with no separators is left unchanged, even if
  some substring of it would pass the Luhn check.
- **Short digit runs**: fewer than 13 digits is never a card, regardless of Luhn result.
- **Separator shapes**: double spaces, double hyphens, commas, or slashes between digit groups
  break the candidate, so `4111  1111 1111 1111` is not matched as a single card.
- **Date-like digit strings**: a hyphen-grouped 13-19 digit run that happens to pass Luhn, such
  as a long correlation id, is redacted; this false positive is accepted (see Assumptions).
- **Card-like value already redacted**: literal text `[CARD]`, `[IP]`, or `[EMAIL]` already
  present in the input is passed through unchanged and not double-counted.
- **Very long lines**: a single line far larger than typical (for example 1 MB) is processed and
  emitted without truncation.
- **No trailing newline**: the final line of the final input is emitted exactly as read, with no
  newline appended.
- **Blank lines and whitespace**: blank lines, leading, and trailing whitespace are preserved
  exactly.
- **Non-text bytes**: a file whose bytes cannot be decoded as text is treated as unreadable —
  it is reported by name with exit status 2 rather than producing mangled output.
- **Unknown option**: an unrecognised flag produces a usage message on standard error and a
  non-zero exit status; no input is processed.
- **Directory as argument**: a path naming a directory is reported as unreadable, exit status 2.
- **Closed output**: if standard output is closed early (for example by a pipe to `head`), the
  tool terminates without an unhandled crash report.

## Requirements *(mandatory)*

### Functional Requirements

**Invocation and input selection**

- **FR-001**: The tool MUST be invocable as `python -m logredact [--count] [FILE ...]`, with
  `--count` accepted in any position relative to file arguments.
- **FR-002**: When no FILE argument is given, the tool MUST read its input from standard input.
- **FR-003**: When one or more FILE arguments are given, the tool MUST read them in the order
  given and MUST NOT read standard input.
- **FR-004**: The tool MUST write all sanitised output to standard output, concatenated in
  input order, preserving line order within each input.

**Output fidelity**

- **FR-005**: The tool MUST write every input line to standard output, applying only the
  replacements defined in FR-007 through FR-016; it MUST NOT add, drop, reorder, merge, or split
  lines.
- **FR-006**: A line containing nothing to redact MUST be reproduced on standard output exactly
  as read, including whitespace and the presence or absence of a trailing line ending.

**Email redaction**

- **FR-007**: The tool MUST replace each email address occurrence with the literal `[EMAIL]`.
- **FR-008**: An email address MUST be recognised as a local part of one or more characters
  drawn from letters, digits, and the characters `.`, `_`, `%`, `+`, and `-`, followed by `@`,
  followed by one or more dot-separated labels of letters, digits, and `-`, ending in a final
  label of at least two letters. `jane.doe+test@mail.example.com` MUST be recognised.
- **FR-009**: Text that does not satisfy FR-008 MUST be left unchanged; for example a bare `@`,
  an address with no domain dot such as `jane@localhost`, or a domain whose final label is not
  at least two letters.

**IPv4 redaction**

- **FR-010**: The tool MUST replace each IPv4 address occurrence with the literal `[IP]`.
- **FR-011**: An IPv4 address MUST be recognised as exactly four dot-separated decimal numbers,
  each in the range 0 to 255 inclusive, written without a leading `+` or `-`.
- **FR-012**: A dotted numeric run in which any part exceeds 255, or which has more or fewer
  than four parts, MUST be left unchanged — `999.1.1.1` and `1.2.3` are not redacted.
- **FR-013**: An IPv4 candidate MUST NOT be matched when it is immediately preceded or followed
  by a digit, or immediately followed by a `.` that is itself followed by a digit; so `1.2.3.4.5`
  is left unchanged, while `192.168.0.10.` at the end of a sentence is redacted.

**Payment card redaction**

- **FR-014**: The tool MUST replace each payment card number occurrence, including any internal
  group separators, with the single literal `[CARD]`.
- **FR-015**: A payment card number MUST be recognised as a run of 13 to 19 digits, whose digit
  groups may optionally be separated by single space or single hyphen characters, and whose
  digits taken in order pass the Luhn checksum. `4111 1111 1111 1111` and
  `4111-1111-1111-1111` MUST be recognised.
- **FR-016**: A candidate digit run that fails the Luhn checksum, that has fewer than 13 or more
  than 19 digits, or that is immediately preceded or followed by a digit MUST be left unchanged;
  `1234567890123` MUST NOT be redacted.

**Overlap resolution**

- **FR-017**: Each character of a line MUST be redacted at most once. Where candidate matches
  overlap, the match starting at the leftmost position MUST win; where candidates start at the
  same position, email MUST take precedence over IPv4, and IPv4 over payment card.
- **FR-018**: Replacement placeholders MUST NOT themselves be re-examined for redaction, so the
  output of one rule cannot be altered by another.

**Counting**

- **FR-019**: With `--count`, the tool MUST write exactly one summary line to standard error,
  in the form `emails=N ips=N cards=N`, after all standard output has been written.
- **FR-020**: Each N MUST be the total number of replacement occurrences of that kind across all
  inputs combined, counting repeated values once per occurrence, and MUST be `0` when none
  occurred.
- **FR-021**: Without `--count`, the tool MUST write nothing to standard error on a successful
  run.

**Errors and exit status**

- **FR-022**: When a FILE argument cannot be read — because it does not exist, cannot be opened,
  names a directory, or contains undecodable bytes — the tool MUST write a message to standard
  error that names that file path and states what went wrong.
- **FR-023**: After reporting an unreadable FILE, the tool MUST stop processing further FILE
  arguments, MUST NOT write a `--count` summary, and MUST exit with status 2.
- **FR-024**: An unrecognised command-line option MUST produce a usage message on standard error
  and a non-zero exit status, with no input processed and no output written to standard output.
- **FR-025**: On any run where all requested inputs were read successfully, the tool MUST exit
  with status 0.

### Key Entities

- **Input source**: one named log file, or standard input when no file is named. Ordered;
  identified by its path for diagnostics.
- **Log line**: a single line of text from an input source, the unit of redaction. Carries no
  structure the tool depends on.
- **Redaction rule**: a named category of sensitive value (email, IPv4 address, payment card)
  paired with its recognition criteria and its fixed placeholder.
- **Redaction tally**: three running totals, one per rule, over all inputs of a single run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All three worked examples in the feature description reproduce byte-for-byte —
  including which stream each byte goes to and the exit status — when run as written.
- **SC-002**: Across a review corpus of log lines containing known emails, IPv4 addresses, and
  Luhn-valid card numbers, zero of those known values survive in the output: the leak rate is
  0%.
- **SC-003**: Across a review corpus of log lines containing no redactable values — including
  Luhn-invalid digit runs, out-of-range dotted quads, dates, version strings, and timestamps —
  100% of lines are reproduced byte-identically: the false-positive rate on those lines is 0%.
- **SC-004**: 100% of the functional requirements FR-001 through FR-025 are covered by at least
  one automated test that names the requirement it verifies, and the full suite passes.
- **SC-005**: Every specified failure mode (unreadable file, unreadable file mid-list,
  unrecognised option) is verified by a test asserting both the diagnostic naming the input and
  the exit status.
- **SC-006**: A 100,000-line log file is sanitised in under 10 seconds on a standard developer
  laptop, and memory use does not grow with file size (a 1 GB file completes without exhausting
  memory).
- **SC-007**: A reviewer can confirm the tool's complete behaviour from its own output alone —
  no configuration file, environment variable, or network access is required to reproduce any
  acceptance scenario.

## Assumptions

Decisions taken where the feature description left room for interpretation. Each is a default
chosen to keep behaviour predictable and testable; any of them can be revisited in
`/speckit-clarify`.

- **Carried-over technical constraints (stated by the requester, recorded here for planning)**:
  Python 3.11 or newer, standard library only, code in a package named `logredact` under `src/`,
  runnable as `python -m logredact` when `src/` is on `PYTHONPATH`. These align with
  Constitution principles I (Standard Library Only) and IV (Simplicity).
- **Fail fast on unreadable input** (FR-023): the tool stops at the first unreadable FILE rather
  than continuing with the remaining ones. Output already written to standard output is left in
  place; it is already-sanitised data and is not retracted. Rationale: exit status 2 then means
  "the output is incomplete", which is the safer signal for scripts.
- **No tally on failure** (FR-023): a `--count` summary is suppressed on the exit-status-2 path,
  so a printed tally always describes a complete run.
- **Occurrence counting** (FR-020): repeated identical values each add to the tally; the tool
  does not track distinct values.
- **Decode failures are read failures**: a file whose bytes are not decodable text is reported
  as unreadable (exit 2) rather than being redacted approximately or passed through with
  replacement characters. Rationale: Constitution principle II (Fail Loudly) — a silently
  mangled redaction pass is worse than a refusal.
- **Input encoding**: inputs are assumed to be UTF-8 text, the standard for log files in this
  project's environment; output uses the same encoding.
- **Mixed group separators** (FR-015): a candidate may mix single spaces and single hyphens
  between groups (`4111-1111 1111-1111` is matched). Separator positions and group sizes are not
  otherwise constrained — grouping is cosmetic and is not validated against card-brand formats.
- **No brand or BIN validation** (FR-015): any 13-19 digit Luhn-valid run qualifies, regardless
  of issuer prefix. Accepted consequence: some non-card identifiers that pass Luhn are redacted.
  This errs toward over-redaction, which is the safe direction for a privacy tool.
- **Hyphen ambiguity accepted**: because hyphens are accepted separators, a long hyphenated
  identifier or date-like string of 13-19 digits that passes Luhn is redacted. This follows
  directly from the stated rule and is treated as intended, not a defect.
- **`-` is a literal path**: a FILE argument of `-` is treated as a file named `-`, not as a
  request to read standard input; no such convention was specified.
- **Line-oriented processing**: input is processed one line at a time and streamed out, so
  memory use is bounded by the longest line (supports SC-006).
- **No in-place editing, no backups, no logging**: the tool only writes the two standard streams.
  It never modifies or deletes an input file.
- **Placeholders are fixed**: `[EMAIL]`, `[IP]`, and `[CARD]` are literal and not configurable;
  no requirement asks for customisation (Constitution principle IV).
- **Out of scope for this feature**: IPv6 addresses, phone numbers, national identity numbers,
  names, URLs, API keys, JSON-aware or structured-log-aware redaction, reversible or hashed
  pseudonymisation, and any form of allowlisting or exclusion rules.
