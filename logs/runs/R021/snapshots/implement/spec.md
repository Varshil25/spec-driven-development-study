# Feature Specification: Log Redaction Tool (`logredact`)

**Feature Branch**: `001-logredact-cli`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "Build a command-line tool that removes personal data from log files before they are shared. Run it as `python -m logredact [--count] [FILE ...]`. It reads each FILE in the order given, or standard input when no FILE is given, and writes every line to standard output with emails replaced by `[EMAIL]`, IPv4 addresses by `[IP]`, and Luhn-valid 13-19 digit payment card numbers (optionally grouped with single spaces or hyphens) by `[CARD]`. Everything else is output unchanged. With `--count`, a summary `emails=N ips=N cards=N` is printed to standard error after all output. An unreadable FILE produces an error message naming the file on standard error and exit status 2; otherwise exit status 0. Python 3.11+, standard library only, package `logredact` under `src/`."

## Clarifications

### Session 2026-11-20

- Q: When an input line ends with a carriage-return + newline (or a bare carriage return), should those exact characters be reproduced, or may they be normalized to a plain newline? → A: Preserve exactly; only a newline ends a line and a carriage return is ordinary text.
- Q: If an input file or stream contains bytes that are not valid UTF-8, should the tool pass them through untouched and continue, or treat the input as unreadable and fail? → A: Pass the bytes through unchanged, redact the surrounding text normally, exit 0.
- Q: What should happen if writing to standard output fails partway through, such as a closed pipe or a full disk? → A: Treat it as a run failure: short diagnostic, no stack trace, no tally, exit 2.
- Q: When a stretch of digits has no valid card number at its earliest starting position but does contain one starting later, should the tool keep scanning and redact the later number? → A: An unbroken run of more than 19 digits is never a card number and is left unchanged even if part of it passes the checksum; where a separator makes a later candidate eligible, scanning continues and that candidate is redacted.
- Q: Should the tool support `--help`, and if so where should the help text go and what exit status should it use? → A: Support `--help` and `-h`; write usage to standard output, read no input, write no tally, exit 0.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Redact a log stream before sharing it (Priority: P1)

An engineer is about to paste or pipe log output to a colleague, a vendor, or a ticket. They pipe the text through the tool and get back the same text with personal data replaced by fixed placeholders, so the log is still readable and diagnosable but no longer carries identifying data.

**Why this priority**: This is the whole point of the tool and the smallest thing that delivers value. Piped input alone is a usable product: an engineer can redact anything reachable by a shell pipeline without any other feature existing.

**Independent Test**: Pipe a known line containing an email, an IPv4 address, and a Luhn-valid card number into the tool with no arguments, and confirm standard output contains the same line with `[EMAIL]`, `[IP]`, and `[CARD]` substituted and all surrounding text intact.

**Acceptance Scenarios**:

1. **Given** no FILE arguments, **When** `printf 'user jane@example.com from 10.0.0.7\n' | python -m logredact` runs, **Then** standard output is exactly `user [EMAIL] from [IP]\n` and the exit status is 0.
2. **Given** no FILE arguments, **When** `printf 'paid with 4111 1111 1111 1111, ref 1234567890123\n' | python -m logredact` runs, **Then** standard output is exactly `paid with [CARD], ref 1234567890123\n` — the Luhn-valid grouped number is redacted and the Luhn-invalid 13-digit number is left alone.
3. **Given** a line with nothing to redact, **When** it is piped through the tool, **Then** that line is reproduced on standard output unchanged, character for character.
4. **Given** an input stream whose last line has no trailing newline, **When** it is piped through the tool, **Then** the output's last line also has no trailing newline.
5. **Given** an email whose local part uses dots and a plus tag and whose domain has several labels (`jane.doe+test@mail.example.com`), **When** it is piped through the tool, **Then** the entire address is replaced by a single `[EMAIL]`.
6. **Given** the text `999.1.1.1`, **When** it is piped through the tool, **Then** it is output unchanged, because an octet above 255 is not an IPv4 address.
7. **Given** the text `99 4111 1111 1111 1111`, **When** it is piped through the tool, **Then** standard output is `99 [CARD]` — the 18-digit candidate fails the checksum but the valid 16-digit number after the space is still found and redacted.
8. **Given** a line whose ending is a carriage return followed by a newline, **When** it is piped through the tool, **Then** the output line ends with the same two characters, not a bare newline.
9. **Given** input containing a byte that is not valid UTF-8 alongside an email address, **When** it is piped through the tool, **Then** the address is replaced by `[EMAIL]`, the invalid byte appears in the output unchanged, and the exit status is 0.

---

### User Story 2 - Redact one or more log files (Priority: P2)

An operator has rotated log files on disk. They name the files on the command line, in the order they want them read, and receive one redacted stream on standard output that they can save or forward.

**Why this priority**: Files are the common real-world input, but this story depends on nothing from Story 1 beyond the redaction itself and can be added on top of a working stdin path.

**Independent Test**: Create two small files each containing personal data, run the tool with both paths as arguments, and confirm the output is the redacted contents of the first file followed by the redacted contents of the second.

**Acceptance Scenarios**:

1. **Given** two readable files `a.log` and `b.log`, **When** `python -m logredact a.log b.log` runs, **Then** standard output is the fully redacted contents of `a.log` followed by the fully redacted contents of `b.log`, in that order, and the exit status is 0.
2. **Given** a single readable file, **When** the tool is run with that one path, **Then** every line of the file appears on standard output in its original order with redactions applied.
3. **Given** both FILE arguments and the `--count` flag in any order on the command line, **When** the tool runs, **Then** the flag is recognized regardless of its position and is not treated as a file name.
4. **Given** an empty file, **When** it is named as the only FILE, **Then** standard output is empty and the exit status is 0.

---

### User Story 3 - Confirm how much was redacted (Priority: P3)

A reviewer needs evidence that redaction actually happened before approving a log for sharing. They add `--count` and read a one-line tally on standard error, which they can inspect separately from the redacted log on standard output.

**Why this priority**: Valuable for trust and for spot-checking, but the tool is already useful without it; it also must not interfere with the primary output stream.

**Independent Test**: Run the tool with `--count` on input with a known number of each kind of personal data, redirect standard output and standard error to separate places, and confirm the tally line matches the known counts while the redacted log is unaffected.

**Acceptance Scenarios**:

1. **Given** the input line `a@b.io 1.2.3.4`, **When** `python -m logredact --count` runs on it, **Then** standard output is `[EMAIL] [IP]\n`, standard error is `emails=1 ips=1 cards=0\n`, and the exit status is 0.
2. **Given** input containing several items of each kind across multiple lines and multiple files, **When** `--count` is used, **Then** the tally reports the total number of replacements of each kind across all input, not per line or per file.
3. **Given** input with nothing to redact, **When** `--count` is used, **Then** standard error is `emails=0 ips=0 cards=0\n`.
4. **Given** `--count` is not passed, **When** the run succeeds, **Then** nothing is written to standard error.
5. **Given** `--count` is passed, **When** the run succeeds, **Then** the tally is written only after all redacted output has been written.

---

### User Story 4 - Fail clearly on an unreadable file (Priority: P3)

An operator mistypes a path or names a file they cannot open. Rather than silently skipping it and handing back an incomplete log that looks complete, the tool says which file it could not read and reports failure.

**Why this priority**: Small in scope, but it is what makes the tool's success signal trustworthy — a partial redacted log mistaken for a full one is the expensive failure.

**Independent Test**: Run the tool naming a path that does not exist and confirm standard error names that path and the exit status is 2.

**Acceptance Scenarios**:

1. **Given** a path that does not exist, **When** it is named as a FILE, **Then** an error message that includes that path is written to standard error and the exit status is 2.
2. **Given** an existing file whose permissions deny reading, **When** it is named as a FILE, **Then** an error message that includes that path is written to standard error and the exit status is 2.
3. **Given** a readable file followed by an unreadable one, **When** the tool runs, **Then** the readable file's redacted output has been written to standard output, the unreadable file is named on standard error, and the exit status is 2.
4. **Given** an unreadable file and `--count`, **When** the tool fails, **Then** no tally line is written — the only standard-error output is the error message — and the exit status is 2.
5. **Given** an unrecognized option such as `--nope`, **When** the tool runs, **Then** a usage message is written to standard error and the exit status is 2.
6. **Given** a large readable file, **When** the output is piped to a reader that stops after the first line (`python -m logredact big.log | head -1`), **Then** a concise diagnostic about the failed write appears on standard error, no stack trace appears, and the exit status is 2.
7. **Given** `--help` is passed, with or without FILE operands and `--count`, **When** the tool runs, **Then** usage text appears on standard output, standard error is empty, no input file is opened, and the exit status is 0.

---

### Edge Cases

- **Octet out of range**: `999.1.1.1` and `256.1.1.1` are not IPv4 addresses and are output unchanged.
- **Too many dotted numbers**: `1.2.3.4.5` contains no IPv4 address to redact and is output unchanged, because the candidate is adjacent to a further dotted number.
- **IPv4 inside a longer number**: `1.2.3.45678` is left unchanged; a candidate immediately followed by a digit is not an address.
- **Version-like strings**: `1.2.3` has only three parts and is left unchanged.
- **Luhn failure**: `1234567890123` has a card-shaped length but fails the checksum, so it is left unchanged.
- **Digit run too long**: a run of 20 or more consecutive digits contains no card number and is left entirely unchanged, even if a 13-to-19-digit stretch inside it would pass the checksum. Length disqualifies the run outright; the checksum is never consulted to rescue part of it.
- **Valid card after a failed candidate**: in `99 4111 1111 1111 1111` the 18-digit candidate fails the checksum, but the final 16 digits start after a space and pass, so the output is `99 [CARD]`. A rejected candidate never hides a valid one further along the line.
- **Digit run too short**: a 12-digit run is left unchanged even if it would pass the checksum.
- **Separator forms**: `4111 1111 1111 1111` and `4111-1111-1111-1111` are both redacted; a run with mixed single separators (`4111-1111 1111-1111`) is also redacted; doubled separators (`4111  1111...`) break the run into parts that are too short to be cards.
- **Separators at the edges**: a redaction never begins or ends on a space or hyphen — trailing punctuation such as the comma in `4111 1111 1111 1111, ref` is preserved.
- **Overlapping categories**: an address like `admin@1.2.3.4` yields one `[EMAIL]`, not an `[EMAIL]` plus an `[IP]`; each character of the input belongs to at most one redaction.
- **Placeholder text already present**: input that already contains the literal text `[EMAIL]`, `[IP]`, or `[CARD]` is passed through unchanged and is not counted.
- **Repeats on one line**: a line containing three email addresses yields three `[EMAIL]` placeholders and contributes 3 to the email tally.
- **Very long lines**: a single line far longer than a typical log line is redacted correctly rather than truncated or split.
- **Empty input**: empty standard input produces empty standard output and exit status 0 (with `emails=0 ips=0 cards=0` if `--count` was passed).
- **Blank and whitespace-only lines**: reproduced exactly, including their original whitespace.
- **Output cut short**: output piped to a reader that stops early (for example `| head -1`) is a failure, not a success — a concise diagnostic goes to standard error, no tally is printed, and the exit status is 2 rather than 0, so a truncated redacted log can never be mistaken for a complete one.
- **Non-UTF-8 bytes**: a log containing stray bytes that are not valid UTF-8 is redacted normally around them and those bytes appear unchanged in the output; they never trigger a failure and never count toward the tally.
- **Windows line endings**: a log whose lines end with carriage-return-plus-newline is reproduced with those endings intact, and a file mixing both ending styles keeps each line's original ending. A bare carriage return is ordinary text, so a redaction may span it only as it would any other character.
- **Standard input named explicitly**: a FILE argument of `-` is treated as a literal file path, not as standard input.
- **Help requested**: `--help` or `-h` prints usage on standard output and exits 0 without reading any input, even when combined with `--count` or FILE operands; an unrecognized option still goes to standard error with exit 2.

## Requirements *(mandatory)*

### Functional Requirements

**Invocation and input sources**

- **FR-001**: The tool MUST accept zero or more FILE operands, an optional `--count` flag, and the optional help flags `--help` and `-h`, in any order on the command line.
- **FR-002**: When no FILE operand is given, the tool MUST read its input from standard input, except on a help request (FR-030a), where no input is read.
- **FR-003**: When one or more FILE operands are given, the tool MUST read them in the order given and MUST NOT read standard input.
- **FR-004**: The tool MUST write all redacted output to standard output as a single concatenated stream, preserving the order of input lines within each source and the order of sources on the command line.

**Pass-through fidelity**

- **FR-005**: Every character of input that is not part of a redacted match MUST appear in the output unchanged and in its original position relative to surrounding text.
- **FR-005a**: Input is read as UTF-8 text. Bytes that are not valid UTF-8 MUST be written to the output unchanged, byte for byte, and MUST NOT cause a failure, a diagnostic, or a substituted replacement character. Such bytes MUST NOT match any redaction category, and text surrounding them MUST still be redacted normally; a digit run interrupted by an undecodable byte is not a contiguous card candidate under FR-016.
- **FR-006**: A line containing nothing to redact MUST be reproduced in the output exactly as it was read, including leading and trailing whitespace.
- **FR-007**: The tool MUST preserve the input's line terminators exactly. Only a newline character ends a line; a carriage return is ordinary text that passes through unchanged, so a line read as carriage-return-plus-newline MUST be written back the same way and a bare carriage return MUST NOT be converted, removed, or treated as a line boundary. Line endings MUST NOT be normalized to a single form.
- **FR-007a**: The tool MUST preserve whether the final line of the input ends with a newline; it MUST NOT add a trailing newline that was absent, nor remove one that was present.

**Email redaction**

- **FR-008**: The tool MUST replace each email address in the input with the literal text `[EMAIL]`.
- **FR-009**: A recognized email address MUST consist of a local part of one or more characters drawn from letters, digits, and the characters `.`, `_`, `%`, `+`, and `-`, followed by `@`, followed by a domain of two or more dot-separated labels of letters, digits, and hyphens, whose final label is two or more letters. `jane.doe+test@mail.example.com` MUST be recognized in full and replaced by a single `[EMAIL]`.
- **FR-010**: An email match MUST extend over the whole address, so that no fragment of it (for example its domain) is separately redacted or left behind.

**IPv4 redaction**

- **FR-011**: The tool MUST replace each IPv4 address in the input with the literal text `[IP]`.
- **FR-012**: A recognized IPv4 address MUST be exactly four dot-separated groups of one to three digits, each group having a numeric value from 0 to 255 inclusive. `192.168.0.10` and `10.0.0.7` MUST be recognized.
- **FR-013**: A candidate with any group whose value exceeds 255 MUST be left unchanged; `999.1.1.1` MUST appear in the output unchanged.
- **FR-014**: A candidate that is immediately preceded or immediately followed by a digit or a dot MUST NOT be redacted, so `1.2.3.4.5` and `1.2.3.45678` are left unchanged.

**Payment card redaction**

- **FR-015**: The tool MUST replace each payment card number in the input with the literal text `[CARD]`.
- **FR-016**: A card number candidate MUST be a sequence of 13 to 19 digits, optionally written as groups separated by single space or single hyphen characters, where the sequence both begins and ends with a digit and no two separators are adjacent. `4111111111111111`, `4111 1111 1111 1111`, and `4111-1111-1111-1111` MUST all be recognized as candidates.
- **FR-017**: The tool MUST redact a candidate only if its digits pass the Luhn checksum; a candidate that fails the checksum MUST be left unchanged, so `1234567890123` appears in the output unchanged.
- **FR-018**: A candidate that is immediately preceded or immediately followed by a digit MUST NOT be redacted. Consequently an unbroken run of 20 or more digits is never a card number and MUST be left entirely unchanged, even when some shorter sequence within it would pass the checksum; the tool MUST NOT redact any part of such a run.
- **FR-019**: When several card candidates start at the same position in a line, the tool MUST redact the longest one that passes the checksum; where candidates would overlap, the one starting earliest in the line MUST win.
- **FR-019a**: A candidate that fails the checksum MUST NOT suppress a later valid one. After rejecting all candidates beginning at a given position, the tool MUST continue scanning from the next eligible starting position, so in `99 4111 1111 1111 1111` — where the full 18-digit candidate fails the checksum but the final 16 digits begin just after a space and pass it — the output MUST be `99 [CARD]`. This never reopens positions that FR-018 excludes, because a candidate inside an unbroken digit run is flanked by digits.

**Overlap and precedence**

- **FR-020**: Each character of a line MUST belong to at most one redaction; redactions MUST NOT nest or overlap.
- **FR-021**: Where an email, an IPv4, and a card candidate would claim the same characters, the earliest-starting match MUST win, and at the same starting position precedence MUST be email, then IPv4, then card. `admin@1.2.3.4` MUST produce exactly one `[EMAIL]`.
- **FR-022**: Substituted placeholder text MUST NOT itself be re-examined for redaction, and placeholder text already present in the input MUST be passed through unchanged and uncounted.

**Counting**

- **FR-023**: With `--count`, the tool MUST write to standard error a single line of the exact form `emails=N ips=N cards=N`, terminated by a newline, where each N is the total number of replacements of that kind across all input read.
- **FR-024**: The tally MUST be written only after all redacted output has been written to standard output.
- **FR-025**: Without `--count`, a successful run MUST write nothing to standard error.
- **FR-026**: The tally MUST count replacements, so three email addresses on one line contribute 3, and MUST report `0` for a kind with no replacements.

**Exit status and failure reporting**

- **FR-027**: On a run where all named input sources were read to completion and all redacted output was written successfully, the tool MUST exit with status 0. Reading every source is not on its own sufficient; a run whose output could not be fully written fails under FR-031a.
- **FR-028**: If a named FILE cannot be opened or read, the tool MUST write to standard error a message that includes that file's path as given on the command line, and MUST exit with status 2.
- **FR-029**: On encountering an unreadable FILE, the tool MUST stop reading further sources; output already written for earlier sources remains written, and no tally line is written even if `--count` was passed.
- **FR-030**: Invalid command-line usage, such as an unrecognized option, MUST produce a diagnostic on standard error and exit status 2.
- **FR-030a**: The tool MUST accept `--help` and `-h`. Either one MUST cause the tool to write its usage and option descriptions to standard output, read no input source, write no tally line even if `--count` was also passed, write nothing to standard error, and exit with status 0. A help request is a successful run, not a usage error.
- **FR-031**: The tool MUST NOT write diagnostics to standard output, and MUST NOT write redacted log content to standard error. The help text required by FR-030a is not a diagnostic: on a help run no input is processed, so standard output carries the help text and nothing else.
- **FR-031a**: If writing redacted output to standard output fails for any reason — including a reader that closes the pipe early and a destination that runs out of space — the tool MUST treat the run as failed: it MUST write a single concise diagnostic to standard error identifying that output could not be written, MUST NOT write a tally line even if `--count` was passed, MUST NOT emit a stack trace or other unhandled-error text, and MUST exit with status 2. A run whose output was truncated MUST NEVER exit with status 0.

### Key Entities

- **Input source**: a named file or standard input, supplying a sequence of text lines; sources are consumed in command-line order.
- **Redaction category**: one of email, IPv4 address, or payment card number — each with its own recognition rule and its own fixed placeholder (`[EMAIL]`, `[IP]`, `[CARD]`).
- **Match**: a span of characters on one line claimed by exactly one category, replaced by that category's placeholder and counted once.
- **Tally**: three non-negative totals, one per category, accumulated over all input and reported only on request.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All three worked examples from the feature description reproduce exactly — byte-identical standard output, byte-identical standard error, and the stated exit status — with no manual interpretation needed.
- **SC-002**: On a mixed fixture of at least 200 lines containing known personal data and known look-alikes (out-of-range octets, five-part dotted numbers, Luhn-failing digit runs, over-length digit runs), 100% of the planted personal data is redacted and 0% of the look-alike tokens are altered.
- **SC-003**: For input containing no personal data, the output is byte-identical to the input in 100% of cases, including blank lines, unusual whitespace, carriage-return-plus-newline and mixed line endings, bytes that are not valid UTF-8, and a missing final newline.
- **SC-004**: Every functional requirement FR-001 through FR-031, including the lettered additions FR-005a, FR-007a, FR-019a, FR-030a, and FR-031a, is covered by at least one automated test that cites its identifier, and the full suite passes.
- **SC-005**: Every failure path (missing file, unreadable file, invalid usage, failed output write) has a test asserting both the diagnostic identifying the offending input or stream and the exit status 2, and asserting that no stack trace appears on standard error.
- **SC-006**: A single run can redact a log of at least 1 GB, or a single line of at least 10 MB, without memory use growing in proportion to total input size.
- **SC-007**: A 100,000-line log is redacted in under 30 seconds on an ordinary developer machine.
- **SC-008**: The `--count` tally equals the number of placeholders present in the output for each category, verified by counting placeholders in the redacted stream.
- **SC-009**: A reviewer can determine from the tool's output alone whether a shared log was fully processed, because success and failure are distinguishable by exit status without inspecting the log.

## Assumptions

Reasonable defaults chosen where the feature description did not specify:

- **Mandated technical constraints (given, not assumed)**: Python 3.11 or newer, standard library only, code in a package named `logredact` under `src/`, runnable as `python -m logredact` when `src/` is on `PYTHONPATH`. These were specified by the requester and also match the project constitution's Standard Library Only principle.
- **Text encoding**: input is treated as UTF-8 text, and bytes that are not valid UTF-8 are carried through to the output unchanged rather than repaired, replaced, or treated as a read failure (FR-005a). This preserves byte fidelity without risking a silent wrong answer, because undecodable bytes cannot resemble any redaction category. "Cannot be read" (FR-028) therefore means the source could not be opened or a read operation on it failed — not that its contents failed to decode.
- **Multiple failures**: the tool stops at the first unreadable FILE rather than continuing and reporting a list at the end (FR-029). The single exit status 2 in the description reads as a single failure point.
- **Line-oriented processing**: input is processed one line at a time and a match never spans a line boundary, so a card number split across two lines is not redacted.
- **Leading zeros in octets**: a group such as `010` is accepted as an octet because its numeric value is within 0-255; `00.0.0.0` is likewise accepted.
- **IPv6 is out of scope**: only dotted-quad IPv4 addresses are recognized; the description names IPv4 explicitly.
- **Other personal data is out of scope**: names, phone numbers, MAC addresses, URLs, usernames, and session tokens are not redacted. The tool redacts exactly the three categories named.
- **Placeholders are fixed**: the replacement texts are not configurable, and there is no flag to enable or disable individual categories.
- **No in-place editing**: the tool never modifies the named input files and writes nothing outside standard output and standard error.
- **`-` is a path**: a FILE operand of `-` means a file named `-`, not standard input; the description gives no special meaning to it.
- **Order of output and tally**: the tally goes to standard error after output is flushed, so a consumer redirecting the two streams separately sees a complete log before the summary.
- **Exit status 1 is unused**: the description names only 0 and 2; no other status is produced for the specified behaviors.
