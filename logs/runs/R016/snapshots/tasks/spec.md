# Feature Specification: Log Redaction CLI

**Feature Branch**: `001-logredact-cli`

**Created**: 2026-11-14

**Status**: Draft

**Input**: User description: "Build a command-line tool that removes personal data from log files before they are shared. Run it as `python -m logredact [--count] [FILE ...]`. It reads each FILE in the order given, or standard input when no FILE is given, and writes every line to standard output with the following replaced: email addresses become `[EMAIL]`; IPv4 addresses become `[IP]`; payment card numbers (13-19 digits, optional single space or hyphen groupings, passing Luhn) become `[CARD]`. Everything else on a line is output unchanged. With `--count`, after all output has been written the tool prints a summary to standard error in the form `emails=N ips=N cards=N`. If a FILE cannot be read, the tool prints an error message naming the file to standard error and exits with status 2. Otherwise it exits with status 0. Use Python 3.11 or newer and the standard library only. Put the code in a package named `logredact` under `src/`, so that it runs with `python -m logredact` when `src/` is on `PYTHONPATH`."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Redact a piped log stream (Priority: P1)

An engineer is about to paste log output into a ticket, a chat message, or a bug report. They pipe the log
through the tool and receive the same text back with every email address, IPv4 address, and payment card
number replaced by a fixed placeholder, so the text is safe to share while remaining readable and
diagnosable.

**Why this priority**: This is the entire point of the feature. Reading standard input and writing
redacted text to standard output is the smallest slice that delivers the protection the user wants; a tool
that only did this would already be useful on its own, because logs are most often reached through a pipe.

**Independent Test**: Pipe a block of text containing emails, IPv4 addresses, card numbers, near-miss
values, and ordinary text into the tool with no file arguments and no flags; confirm the output text has
exactly the sensitive values replaced and everything else byte-identical.

**Acceptance Scenarios**:

1. **Given** the input line `user jane@example.com from 10.0.0.7`, **When** the tool is run with no
   arguments, **Then** standard output is exactly `user [EMAIL] from [IP]` followed by a newline.
2. **Given** the input line `paid with 4111 1111 1111 1111, ref 1234567890123`, **When** the tool is run
   with no arguments, **Then** standard output is exactly `paid with [CARD], ref 1234567890123` followed by
   a newline, because the second digit sequence fails the Luhn checksum.
3. **Given** an input line containing none of the three sensitive categories, **When** the tool is run,
   **Then** that line is reproduced on standard output exactly as it was received, character for character.
4. **Given** an input line containing several sensitive values of different categories, **When** the tool is
   run, **Then** every one of them is replaced in place, and the surrounding text, spacing, and punctuation
   are unchanged.
5. **Given** the input line `contact jane.doe+test@mail.example.com`, **When** the tool is run, **Then**
   standard output is `contact [EMAIL]`, showing that dotted, plus-tagged local parts and multi-label
   domains are recognised.
6. **Given** the input line `host 999.1.1.1 unreachable`, **When** the tool is run, **Then** the line is
   output unchanged, because `999.1.1.1` is not a valid IPv4 address and no part of it may be redacted.
7. **Given** standard input containing no data at all, **When** the tool is run, **Then** standard output
   is empty and the exit status is 0.

---

### User Story 2 - Redact one or more named log files (Priority: P2)

A support engineer has several log files on disk that need to be bundled for a vendor. They name the files
on the command line, in the order they want them, and capture a single redacted stream.

**Why this priority**: Naming files is the second natural way to reach logs, and it is required for the
common case of sharing archived files rather than live output. It builds directly on the redaction engine
proven by User Story 1 and adds only input selection, so it is valuable but not the core.

**Independent Test**: Create two small files with known sensitive content, run the tool with both file
names as arguments, and confirm the output is the redacted content of the first file followed by the
redacted content of the second, with nothing reordered, dropped, or duplicated.

**Acceptance Scenarios**:

1. **Given** two readable files, **When** the tool is run with both file names as arguments, **Then** the
   redacted contents appear on standard output in the order the files were named on the command line.
2. **Given** one readable file named on the command line, **When** the tool is run, **Then** standard input
   is not read at all and the exit status is 0.
3. **Given** the same file named twice on the command line, **When** the tool is run, **Then** its redacted
   contents appear twice on standard output.
4. **Given** a readable but completely empty file, **When** the tool is run with that file as its only
   argument, **Then** standard output is empty and the exit status is 0.

---

### User Story 3 - Confirm how much was redacted (Priority: P3)

Before sending a redacted log out, the user wants evidence that the tool actually found something — or
confirmation that there was nothing to find. They add `--count` and read a one-line tally that does not
pollute the redacted output itself.

**Why this priority**: This is a trust and verification aid rather than protection. The redaction is
already complete and correct without it, but without a tally the user cannot cheaply tell "nothing was
sensitive" apart from "the tool failed to recognise anything".

**Independent Test**: Run the tool with `--count` over input with a known number of each category, with
standard output and standard error captured separately; confirm the redacted text appears only on standard
output and exactly one summary line appears only on standard error.

**Acceptance Scenarios**:

1. **Given** the input line `a@b.io 1.2.3.4`, **When** the tool is run with `--count`, **Then** standard
   output is `[EMAIL] [IP]` followed by a newline and standard error is `emails=1 ips=1 cards=0` followed by
   a newline.
2. **Given** input with no sensitive values at all, **When** the tool is run with `--count`, **Then**
   standard error is `emails=0 ips=0 cards=0` and the exit status is 0.
3. **Given** input where the same email address occurs three times, **When** the tool is run with
   `--count`, **Then** the summary reports `emails=3`, because every individual replacement is counted.
4. **Given** several input files named together with `--count`, **When** the tool is run, **Then** exactly
   one summary line is produced, totalling the replacements across all of the files.
5. **Given** any input, **When** the tool is run without `--count`, **Then** standard error receives
   nothing.
6. **Given** any input, **When** the tool is run with `--count`, **Then** the summary line is written only
   after all redacted output has been written.

---

### User Story 4 - Learn immediately when a log cannot be read (Priority: P3)

The user mistypes a file name, or names a file they do not have permission to read. Rather than silently
producing a short or empty redacted log that looks complete, the tool tells them which file was the problem
and fails with a distinct exit status their script can detect.

**Why this priority**: A silently truncated "redacted" log is worse than no output, because the user may
share it believing it is the whole log. The failure path is low-frequency but high-consequence, and it is
independently testable from the redaction behaviour.

**Independent Test**: Run the tool naming a file that does not exist; confirm standard error contains a
message naming that exact file, and the exit status is 2.

**Acceptance Scenarios**:

1. **Given** a file name that does not exist on disk, **When** the tool is run with it, **Then** a message
   naming that file is written to standard error and the exit status is 2.
2. **Given** a file that exists but cannot be opened for reading because of its permissions, **When** the
   tool is run with it, **Then** a message naming that file is written to standard error and the exit status
   is 2.
3. **Given** a name that refers to a directory rather than a file, **When** the tool is run with it,
   **Then** a message naming it is written to standard error and the exit status is 2.
4. **Given** two file names where the first is readable and the second is not, **When** the tool is run,
   **Then** the redacted contents of the first file have been written to standard output, a message naming
   the second file is on standard error, and the exit status is 2.
5. **Given** a failing file name, **When** the tool is run, **Then** the error message on standard error
   states both the file named and the reason it could not be read.
6. **Given** all named files are readable, **When** the tool is run, **Then** the exit status is 0.

---

### Edge Cases

- **Not-quite IPv4 addresses**: `999.1.1.1`, `256.0.0.1`, and `1.2.3` are left completely unchanged — in
  particular, no shorter valid-looking fragment inside them (such as `9.1.1.1` or `56.0.0.1`) may be
  redacted.
- **Over-long dotted runs**: `1.2.3.4.5` is left unchanged, because the run as a whole is not a four-part
  IPv4 address.
- **IPv4 boundaries**: `v1.2.3.4` and `1.2.3.45678` are not IPv4 addresses; a value is only an address when
  it is not butted up against another digit or dot.
- **Luhn near-misses**: a 13-to-19-digit sequence that fails the Luhn checksum (for example
  `1234567890123`) is left unchanged, even though it has a card-like length.
- **Digit runs of the wrong length**: 12 digits or fewer, and 20 digits or more, are never redacted as a
  card, even if some 13-to-19-digit window inside them would pass Luhn.
- **Card grouping**: single spaces and single hyphens between digit groups are part of the number, so
  `4111 1111 1111 1111` and `4111-1111-1111-1111` are each one card. A doubled separator (`4111  1111`)
  ends the number, leaving two shorter sequences to be judged on their own.
- **Overlapping categories**: in `user@1.2.3.4`, the whole value is recognised as one email address and
  becomes `[EMAIL]`; the embedded address is not separately redacted and is not counted as an IP.
- **Several values touching each other**: `a@b.io,1.2.3.4` has both values replaced and the comma preserved.
- **A whole line that is one sensitive value**: the line becomes exactly the placeholder.
- **Final line without a trailing newline**: the redacted final line is written without a newline being
  invented for it.
- **Blank and whitespace-only lines**: reproduced exactly, including trailing spaces and tab characters.
- **Very long lines**: a single line far longer than a typical log line is still redacted and reproduced in
  full.
- **Carriage returns**: a `\r` before the line ending is part of the line content and is preserved as-is.
- **Non-UTF-8 bytes**: a line containing bytes that are not valid UTF-8 is still processed, and those bytes
  are reproduced unchanged rather than being replaced, dropped, or causing a crash.
- **No input at all**: empty standard input, and an empty named file, both produce empty output and exit 0.
- **`--count` after a failure**: when the run fails because a file could not be read, no summary line is
  produced, because not all output was written.
- **`--count` placement**: the flag is accepted before or after file names.
- **Output cannot be written**: if standard output is closed early (for example a downstream `head` exits),
  the tool stops without a traceback.

## Requirements *(mandatory)*

### Functional Requirements

#### Invocation and input selection

- **FR-001**: The tool MUST be runnable as `python -m logredact [--count] [FILE ...]`.
- **FR-002**: The tool MUST read each `FILE` operand in the order given on the command line and treat the
  concatenation as one stream of lines.
- **FR-003**: The tool MUST read standard input, and only standard input, when no `FILE` operand is given.
- **FR-004**: The tool MUST accept `--count` in any position among the operands, and MUST accept zero or
  more `FILE` operands with or without `--count`.
- **FR-005**: The tool MUST reject an unrecognised option with a diagnostic on standard error and exit
  status 2, rather than treating it as a file name.

#### Output fidelity

- **FR-006**: The tool MUST write every input line to standard output, with the redactions of FR-008 to
  FR-013 applied and nothing else altered.
- **FR-007**: The tool MUST reproduce a line that contains nothing to redact exactly as it was received,
  including leading and trailing whitespace, punctuation, and the absence of a trailing newline on a final
  line that had none.

#### Email redaction

- **FR-008**: The tool MUST replace each email address with the literal text `[EMAIL]`.
- **FR-009**: The tool MUST recognise as an email address a local part of one or more letters, digits, or
  the characters `.`, `_`, `%`, `+`, or `-`, followed by `@`, followed by one or more domain labels of
  letters, digits, or `-` separated by `.`, ending in a final label of at least two letters — so that
  `jane.doe+test@mail.example.com` and `a@b.io` are both recognised.

#### IPv4 redaction

- **FR-010**: The tool MUST replace each IPv4 address with the literal text `[IP]`.
- **FR-011**: The tool MUST recognise as an IPv4 address exactly four dot-separated components, each of one
  to three digits with a numeric value from 0 to 255 inclusive, and MUST leave unchanged any dotted run that
  does not meet this definition, redacting no fragment of it.

#### Payment card redaction

- **FR-012**: The tool MUST replace each payment card number with the literal text `[CARD]`.
- **FR-013**: The tool MUST recognise as a payment card number a sequence of 13 to 19 digits, optionally
  broken into groups by single space or single hyphen separators, whose digits pass the Luhn checksum; and
  MUST leave unchanged any digit sequence that fails the Luhn checksum or falls outside the 13-to-19-digit
  length range.

#### Redaction consistency

- **FR-014**: The tool MUST redact every occurrence on a line, not only the first.
- **FR-015**: The tool MUST resolve overlapping candidates deterministically by scanning each line once
  from left to right and, at each position, preferring an email address, then an IPv4 address, then a
  payment card number; text consumed by one replacement MUST NOT be considered again.
- **FR-016**: The tool MUST produce output that depends only on the input text, so that running it twice on
  the same input gives identical output.

#### Counting

- **FR-017**: The tool MUST, when `--count` is given, write exactly one line to standard error in the form
  `emails=N ips=N cards=N`, where each N is the total number of replacements of that category across all
  input read during the run.
- **FR-018**: The tool MUST write the summary line only after all redacted output has been written.
- **FR-019**: The tool MUST write nothing to standard error when `--count` is not given and no error occurs.
- **FR-020**: The tool MUST keep the summary out of standard output, so that standard output contains only
  redacted log text.

#### Failure behaviour

- **FR-021**: The tool MUST, when a named file cannot be opened or read, write a message to standard error
  that names that file and states the reason, and MUST exit with status 2.
- **FR-022**: The tool MUST NOT write a `--count` summary when it exits because a file could not be read.
- **FR-023**: The tool MUST exit with status 0 when all requested input was read and written successfully.

### Key Entities

- **Input source**: a named file or standard input, consumed as an ordered sequence of text lines.
- **Redaction category**: one of email, IPv4 address, or payment card number; each has a recognition rule
  and exactly one fixed placeholder (`[EMAIL]`, `[IP]`, `[CARD]`).
- **Replacement tally**: three counts, one per category, accumulated over the whole run and reported only
  when `--count` is requested.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All three example invocations given in the feature description reproduce their documented
  standard output and standard error byte for byte.
- **SC-002**: 100% of the functional requirements FR-001 to FR-023 are covered by at least one automated
  test that names the requirement it covers.
- **SC-003**: Every edge case listed in the Edge Cases section has a corresponding automated test.
- **SC-004**: For input containing no sensitive values, the output is byte-identical to the input in 100%
  of cases, including files with no trailing newline.
- **SC-005**: Of the recognised sensitive values placed in test input, 100% are redacted, and of the
  near-miss values placed in test input (invalid addresses, Luhn failures, wrong-length digit runs), 0% are
  altered.
- **SC-006**: The `--count` tally matches the number of placeholders present in the output for every test
  input.
- **SC-007**: Every run that cannot produce the complete redacted output — an unreadable file, or an
  invalid command line — exits with status 2 and explains itself on standard error, naming the offending
  file where one is involved; every run that does produce complete output exits with status 0.
- **SC-008**: A 100,000-line log file is redacted in under 10 seconds on a developer laptop, and memory use
  does not grow with the number of lines, so arbitrarily large logs can be processed.
- **SC-009**: A user can redact a log and confirm what was removed in a single command, with no
  configuration file, no installation step beyond obtaining the source, and no network access.

## Assumptions

Constraints stated by the user and carried into this specification:

- The runtime is Python 3.11 or newer, using the standard library only, with no third-party runtime
  dependency.
- The code lives in a package named `logredact` under `src/`, and runs as `python -m logredact` when `src/`
  is on `PYTHONPATH`.
- Automated tests are written for `pytest`, per the project constitution; `pytest` is the only permitted
  development dependency.

Reasonable defaults chosen where the description did not specify:

- **Streaming failure, not pre-flight validation**: files are opened in the order given, so output from
  earlier readable files is already on standard output when a later file fails. The tool does not check all
  files for readability before producing any output. This keeps behaviour identical for files and pipes.
- **No summary on failure**: because the summary is specified to come after all output has been written, a
  run that exits with status 2 produces no summary, even with `--count`.
- **Counting unit**: one replacement counts as one, so the same value appearing three times counts three
  times, and counts accumulate across all files in a run.
- **Precedence order**: email, then IPv4, then card, resolved left to right (FR-015). Chosen so that a
  value such as `user@1.2.3.4` is redacted once as an email rather than being partly redacted twice.
- **Token boundaries**: a candidate is only recognised when it is not immediately adjacent to a character
  that would extend it — a digit or a dot for an IPv4 address, a digit for a card number. This is what makes
  `999.1.1.1` and a 20-digit run safe from partial redaction.
- **IPv4 component form**: one to three digits with a value of 0 to 255, so leading zeros such as
  `010.0.0.1` are accepted as an address. No separate rule for leading zeros is imposed.
- **Card separators may be mixed**: each separator is judged independently as a single space or single
  hyphen, so `4111-1111 1111-1111` is one card. Group sizes are not constrained; only the total digit count
  and the Luhn checksum matter. This is the simplest rule that satisfies the stated examples.
- **Text handling**: input is treated as UTF-8 text; bytes that are not valid UTF-8 are passed through
  unchanged rather than causing a failure, so redaction never corrupts an otherwise shareable log.
- **Line-based processing**: a sensitive value is recognised only within a single line; a value split
  across a line ending is not redacted.
- **Scope boundaries**: no other category of personal data (names, phone numbers, IPv6 addresses, URLs,
  tokens), no in-place file rewriting, no configuration of the placeholder text, no reversible or
  consistent pseudonymisation, and no detection of already-redacted output are in scope.
