# Feature Specification: Redact Personal Data From Log Files

**Feature Branch**: `001-redact-log-pii`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "Build a command-line tool that removes personal data from log files before they are shared. Run it as `python -m logredact [--count] [FILE ...]`. It reads each FILE in the order given, or standard input when no FILE is given, and writes every line to standard output with email addresses, IPv4 addresses, and Luhn-valid payment card numbers replaced by `[EMAIL]`, `[IP]`, and `[CARD]`. With `--count`, a summary `emails=N ips=N cards=N` is printed to standard error after all output. If a FILE cannot be read, an error naming the file goes to standard error and the exit status is 2; otherwise 0. Python 3.11+, standard library only, package `logredact` under `src/`."

## Clarifications

### Session 2026-11-13

- Q: Which character encoding should the tool use when reading and writing log text? → A: Always UTF-8 for input and output, with undecodable bytes preserved exactly and round-tripped, regardless of locale or environment
- Q: What should the tool do when the program reading its output closes early (e.g. piping to `head`)? → A: Stop quietly — nothing on standard error, no traceback, no `--count` summary, exit status 0
- Q: What is the expected output for `user@1.2.3.4`, where the text looks like an email address but its domain is a dotted number? → A: `[EMAIL]` — the email rule also accepts a dotted-number domain, so the local part is redacted too (safe direction)
- Q: What should happen when the tool is given an invalid command line, such as an unrecognised flag? → A: Usage diagnostic naming the offending argument to standard error, no redacted output, exit status 2
- Q: When a FILE argument names something that exists but is not a readable text file (e.g. a directory), should that count as an unreadable file? → A: Yes — it takes the FR-025 path: diagnostic naming it, processing stops, exit status 2

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sanitize a log stream before sharing it (Priority: P1)

An engineer is about to attach application log output to a support ticket. They pipe the log
through the tool and get back the same log with personal and payment identifiers replaced by
fixed placeholders, so the shared copy still reads like a log but no longer exposes anyone's
email address, network address, or card number.

**Why this priority**: This is the entire point of the feature. Without it there is nothing to
ship; with only this, the tool already solves the user's problem for the common case.

**Independent Test**: Pipe a log excerpt containing an email address, an IPv4 address, and a
Luhn-valid card number into the tool with no arguments, and confirm standard output contains
`[EMAIL]`, `[IP]`, and `[CARD]` in those positions and is otherwise identical to the input.

**Acceptance Scenarios**:

1. **Given** the single line `user jane@example.com from 10.0.0.7` on standard input, **When**
   the tool is run with no arguments, **Then** standard output is exactly
   `user [EMAIL] from [IP]` followed by a newline, and the exit status is 0.
2. **Given** the line `paid with 4111 1111 1111 1111, ref 1234567890123`, **When** the tool is
   run, **Then** standard output is exactly `paid with [CARD], ref 1234567890123` — the
   grouped card number is replaced and the Luhn-failing 13-digit reference is untouched.
3. **Given** a line containing nothing to redact, **When** the tool is run, **Then** that line
   appears on standard output byte-for-byte as it was read.
4. **Given** a line containing `999.1.1.1`, **When** the tool is run, **Then** the text
   `999.1.1.1` appears unchanged, because 999 is not a valid IPv4 octet.
5. **Given** input with several redactable items on one line, **When** the tool is run,
   **Then** every one of them is replaced, each with the placeholder for its own type.
6. **Given** the line `login from user@1.2.3.4`, **When** the tool is run, **Then** standard
   output is exactly `login from [EMAIL]` — the username is redacted along with the address —
   and with `--count` the summary reports `emails=1 ips=0 cards=0`.
7. **Given** a long input and a consumer that stops reading after the first few lines (for
   example piping into `head -5`), **When** the tool is run, **Then** those lines are redacted
   and written, nothing is written to standard error, and the exit status is 0.

---

### User Story 2 - Sanitize one or more named log files (Priority: P2)

The engineer has several rotated log files on disk. They name them on the command line in the
order they want them read and capture one sanitized stream, without having to concatenate the
files themselves first.

**Why this priority**: Named files are the primary real-world input (logs live on disk), but
the redaction behaviour from Story 1 must exist first and is demonstrable on its own via a
pipe.

**Independent Test**: Run the tool with two files as arguments and confirm standard output is
the redacted contents of the first file followed by the redacted contents of the second, in
that order.

**Acceptance Scenarios**:

1. **Given** two readable files, **When** the tool is run with both named in order, **Then**
   standard output contains the redacted lines of the first file followed by the redacted
   lines of the second, with no lines reordered, dropped, or duplicated, and the exit status
   is 0.
2. **Given** one readable file named twice, **When** the tool is run, **Then** its redacted
   contents appear twice.
3. **Given** an empty file, **When** the tool is run with it, **Then** standard output is
   empty and the exit status is 0.
4. **Given** one or more files are named, **When** the tool is run, **Then** standard input is
   not read at all.

---

### User Story 3 - See how much was redacted (Priority: P3)

Before sharing the sanitized log, the engineer wants a quick confirmation that redaction
actually fired, and how often, so they can sanity-check the result against what they expected
the log to contain.

**Why this priority**: A reporting convenience layered on top of redaction. Valuable for trust
and for spot-checking, but the tool is useful without it.

**Independent Test**: Run the tool with `--count` over input with a known number of each
identifier and confirm the summary line on standard error reports exactly those numbers while
standard output is unaffected.

**Acceptance Scenarios**:

1. **Given** the line `a@b.io 1.2.3.4`, **When** the tool is run with `--count`, **Then**
   standard output is `[EMAIL] [IP]` and standard error is `emails=1 ips=1 cards=0`.
2. **Given** input with nothing to redact, **When** the tool is run with `--count`, **Then**
   standard error is `emails=0 ips=0 cards=0`.
3. **Given** multiple files are named, **When** the tool is run with `--count`, **Then** a
   single summary covering all of them together is printed once, after all redacted output
   has been written.
4. **Given** any input, **When** the tool is run without `--count`, **Then** nothing is
   written to standard error and the exit status is 0.

---

### User Story 4 - Fail clearly when a log file cannot be read (Priority: P4)

The engineer mistypes a filename or points at a file they cannot open. Instead of silently
producing a sanitized stream that is missing data, the tool tells them which file it could not
read and reports failure, so the incomplete output is never mistaken for a complete one.

**Why this priority**: Guards against the worst failure mode (an apparently-complete sanitized
log that silently omits input), but only matters once the file-reading path of Story 2 exists.

**Independent Test**: Run the tool naming a file that does not exist and confirm standard error
names that file and the exit status is 2.

**Acceptance Scenarios**:

1. **Given** a named file that does not exist, **When** the tool is run, **Then** standard
   error contains a message that includes that file's name as given on the command line, and
   the exit status is 2.
2. **Given** a named file that exists but cannot be opened for reading, **When** the tool is
   run, **Then** standard error names that file and the exit status is 2.
3. **Given** a named argument that is a directory, **When** the tool is run, **Then** standard
   error names it with a message explaining it could not be read, no stack trace is shown, and
   the exit status is 2.
4. **Given** a readable file followed by an unreadable one, **When** the tool is run, **Then**
   the readable file's redacted output has been written, the unreadable file is named on
   standard error, processing stops there, and the exit status is 2.
5. **Given** every named file is readable, **When** the tool is run, **Then** no error message
   is produced and the exit status is 0.
6. **Given** an unrecognised flag such as `--redact-all`, **When** the tool is run, **Then**
   standard error carries a usage message naming that argument, standard output is empty, and
   the exit status is 2.

---

### Edge Cases

- **Empty input**: no input lines at all produces no output and, with `--count`, all-zero
  counts.
- **No trailing newline**: a final line that does not end with a newline is written without
  one; the tool does not add or remove line terminators.
- **Line endings**: carriage returns in the input (for example Windows-style endings) are
  preserved exactly in the output.
- **Adjacent and repeated matches**: several matches on one line, including matches separated
  by a single character, are all replaced.
- **Placeholder text already present**: input that already contains `[EMAIL]`, `[IP]`, or
  `[CARD]` passes through unchanged and is not double-counted.
- **Octet range boundaries**: `0.0.0.0` and `255.255.255.255` are redacted; any group above
  255 (such as `256.1.1.1` or `999.1.1.1`) leaves the whole candidate untouched.
- **Over-long dotted runs**: `1.2.3.4.5` is not an IPv4 address and is left alone, while a
  sentence-ending `from 10.0.0.7.` still redacts the address and keeps the full stop.
- **Digit-run boundaries**: a run of 12 digits is too short to be a card and a run of 20
  digits is too long; neither is partially redacted.
- **Separator strictness**: card groups separated by a single space or single hyphen are
  recognised; a doubled separator (`4111  1111 1111 1111`) breaks the candidate into runs that
  are individually too short to be cards.
- **Luhn-failing digit runs**: any 13-19 digit run that fails the checksum is left alone, which
  keeps ordinary long identifiers such as request IDs and timestamps intact.
- **Identifiers that look like each other**: `user@1.2.3.4` is redacted whole as `[EMAIL]`
  (counted as an email, not an IP), and a version-like dotted quad such as `10.0.0.7` standing
  on its own is redacted as `[IP]`. Both are indistinguishable from real identifiers in a log,
  and redacting is accepted as the safe direction to err.
- **Very long lines**: a single line far larger than a typical log line is processed without
  truncation.
- **Output consumer closes early**: piping into a command that stops reading (such as `head`)
  ends the run quietly with exit status 0 — no diagnostic, no traceback, and no count summary.
- **Undecodable bytes**: log bytes that are not valid UTF-8 are passed through to the output as
  the same bytes, rather than causing a crash or a substitution character.
- **Locale independence**: the same input file produces byte-identical output whichever locale
  or encoding environment settings the machine has.

## Requirements *(mandatory)*

### Functional Requirements

**Invocation and input selection**

- **FR-001**: The tool MUST be runnable as `python -m logredact`, accepting an optional
  `--count` flag and zero or more FILE arguments in any order relative to the flag.
- **FR-002**: With no FILE argument, the tool MUST read its input from standard input.
- **FR-003**: With one or more FILE arguments, the tool MUST read each file fully, in the order
  given on the command line, and MUST NOT read standard input.
- **FR-004**: The tool MUST write redacted output to standard output in input order, emitting
  every input line exactly once, with no lines added, dropped, reordered, or duplicated.
- **FR-005**: Any part of a line that is not a redacted match MUST be written out unchanged;
  a line containing nothing to redact MUST be written out byte-for-byte as it was read,
  including its line terminator or absence of one.

**Text handling**

- **FR-005a**: The tool MUST read and write all text as UTF-8, and MUST NOT vary its behaviour
  with the machine's locale or encoding environment settings: the same input MUST yield
  byte-identical output on any machine.
- **FR-005b**: Input bytes that are not valid UTF-8 MUST be carried through to the output as the
  same bytes. The tool MUST NOT abort, substitute a replacement character, or drop them.

**Email addresses**

- **FR-006**: The tool MUST replace each email address with the literal text `[EMAIL]`.
- **FR-007**: An email address is a local part of one or more characters drawn from letters,
  digits, `.`, `_`, `%`, `+`, and `-`, followed by `@`, followed by a domain that is EITHER one
  or more dot-separated labels of letters, digits, and hyphens ending in a final label of at
  least two letters, OR four dot-separated groups of one to three digits.
  `jane.doe+test@mail.example.com` MUST be recognised in full.
- **FR-007a**: When the domain is a dotted-number form, the whole address including its local
  part MUST be replaced by `[EMAIL]` and counted as an email — so `user@1.2.3.4` becomes
  `[EMAIL]`, not `user@[IP]`. The numeric groups MUST NOT be range-checked in this position, so
  `user@999.1.1.1` is also replaced in full; the preceding `local-part@` already identifies the
  text as an address, removing the version-number ambiguity that the range check of FR-011
  exists to avoid.
- **FR-008**: Punctuation immediately following an address (for example a trailing comma, full
  stop, or closing bracket) MUST NOT be consumed by the match.

**IPv4 addresses**

- **FR-009**: The tool MUST replace each IPv4 address with the literal text `[IP]`.
- **FR-010**: An IPv4 address is four groups of one to three digits separated by single dots,
  where every group has a numeric value from 0 to 255 inclusive.
- **FR-011**: A dotted-quad candidate with any group whose value exceeds 255 MUST be left
  entirely unchanged (for example `999.1.1.1`).
- **FR-012**: A candidate MUST NOT be recognised when it is directly adjacent to a digit, or
  when it is immediately preceded by a digit-and-dot or immediately followed by a dot-and-digit
  — so `1.2.3.4.5` is left alone, while `10.0.0.7.` at the end of a sentence is redacted and
  the full stop is preserved.

**Payment card numbers**

- **FR-013**: The tool MUST replace each payment card number with the literal text `[CARD]`.
- **FR-014**: A payment card number is a sequence of 13 to 19 digits, optionally written as
  groups of digits joined by single-character separators that are each either one space or one
  hyphen, whose digits pass the Luhn checksum. `4111 1111 1111 1111` and
  `4111-1111-1111-1111` MUST both be recognised, and the whole candidate including its
  separators MUST be replaced.
- **FR-015**: A candidate whose digits fail the Luhn checksum MUST be left entirely unchanged
  (for example `1234567890123`).
- **FR-016**: A candidate with fewer than 13 or more than 19 digits MUST be left entirely
  unchanged, and MUST NOT be partially redacted.
- **FR-017**: A card candidate MUST NOT be recognised when the digits at either end are
  directly adjacent to another digit, so no card is found inside a longer digit run.

**Match resolution**

- **FR-018**: The tool MUST resolve matches in a single left-to-right pass over each line: the
  match starting at the earliest position wins, and scanning resumes after the text it
  replaced, so redacted text is never re-examined and matches never overlap.
- **FR-019**: When two or more match types start at the same position, the tool MUST apply
  email first, then IPv4 address, then payment card number.
- **FR-020**: Placeholder text inserted by the tool MUST NOT itself be matched or counted.

**Counting**

- **FR-021**: With `--count`, the tool MUST write a single summary line in the exact form
  `emails=N ips=N cards=N` to standard error, after all redacted output has been written to
  standard output. The summary is written only for a run that processed every input to the end;
  it MUST be suppressed on the failure of FR-026 and on the early-close case of FR-028.
- **FR-022**: Each count MUST equal the number of replacements of that type actually made,
  totalled across every input read in this run, and MUST be reported as `0` when no replacement
  of that type was made.
- **FR-023**: Without `--count`, the tool MUST write nothing to standard error on a successful
  run.

**Exit status and failure reporting**

- **FR-024**: On a run where every named input was read successfully, the tool MUST exit with
  status 0.
- **FR-025**: When a named FILE cannot be opened or read, the tool MUST write a diagnostic to
  standard error that includes that file's name as given on the command line and states what
  went wrong, and MUST exit with status 2. This MUST cover every reason the input cannot be
  read as text — it does not exist, permission is denied, it is a directory, or reading it
  fails partway through — and the tool MUST NOT emit an unhandled error trace for any of them.
- **FR-026**: On that failure the tool MUST stop processing further inputs, and MUST NOT print
  the `--count` summary, so an incomplete run is never presented as a complete one.
- **FR-027**: Redacted output already written for earlier files MUST remain valid and complete
  for those files up to the point of failure.
- **FR-028**: When the consumer of standard output stops reading before the tool has finished
  writing, the tool MUST stop processing and terminate quietly with exit status 0: it MUST NOT
  write any diagnostic, error trace, or `--count` summary to standard error.
- **FR-029**: When the command line contains an argument the tool does not accept (such as an
  unrecognised flag), the tool MUST write a usage diagnostic to standard error that names the
  offending argument, MUST NOT read any input or write any redacted output, MUST NOT print a
  `--count` summary, and MUST exit with status 2. It MUST NOT silently ignore the argument or
  reinterpret it as a filename.

### Key Entities

- **Input source**: one named file, or standard input when no file is named. Sources are read
  in the order given and contribute their lines to one output stream.
- **Line**: the unit of reading and writing. Each line is scanned independently; no match spans
  a line boundary.
- **Redaction type**: one of email address, IPv4 address, or payment card number — each with
  its own recognition rule, its own fixed placeholder (`[EMAIL]`, `[IP]`, `[CARD]`), and its own
  counter name (`emails`, `ips`, `cards`).
- **Redaction counts**: three running totals, one per redaction type, accumulated across all
  input sources in a run and reported only when `--count` is given.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a sample log containing known email addresses, IPv4 addresses, and Luhn-valid
  card numbers (plain and in space- and hyphen-separated groups), 100% of them are absent from
  the output and replaced by the matching placeholder.
- **SC-002**: On a control sample of near-misses — bare out-of-range dotted quads not preceded
  by a `local-part@` (see FR-007a), Luhn-failing
  13-19 digit runs, 12-digit and 20-digit runs, doubled separators, and five-group dotted runs
  — the output is byte-identical to the input: zero false positives.
- **SC-003**: For input with no redactable content of any kind, the output is byte-identical to
  the input, including line terminators, a missing final newline, and any bytes that are not
  valid UTF-8 — and this holds unchanged under any locale or encoding environment setting.
- **SC-004**: The three reported counts match the number of placeholders present in the output,
  exactly, for every test input.
- **SC-005**: Every documented edge case and every functional requirement is covered by at
  least one automated test, and the full suite passes.
- **SC-006**: Naming an unreadable file always yields a standard-error message containing that
  filename and exit status 2; an unrecognised command-line argument always yields a usage
  message naming it, empty standard output, and exit status 2; every fully readable run yields
  exit status 0. The tool never exits with a status other than 0 or 2.
- **SC-007**: A one-million-line log is processed in under 60 seconds on a typical developer
  machine, with memory use that does not grow with input size (the tool streams rather than
  buffering whole inputs).

## Assumptions

**Explicit constraints carried from the request** (stated by the user, not chosen here): Python
3.11 or newer; standard library only, with no third-party runtime dependency; the code lives in
a package named `logredact` under `src/`, runnable as `python -m logredact` when `src/` is on
`PYTHONPATH`. These align with Constitution principles I (Standard Library Only) and the
project's text-in/text-out CLI contract.

Defaults chosen where the request did not specify:

- **Failure is fail-fast**: the first unreadable file stops the run (FR-026) rather than the
  tool skipping it and continuing. The request says the tool "prints an error message naming
  the file and exits with status 2" without saying whether later files are still processed;
  stopping, and suppressing the count summary, follows Constitution principle II (Fail Loudly)
  by never handing back a sanitized stream that silently omits input.
- **Early output close is a success, not a failure** (FR-028, clarified 2026-11-13): the request
  does not mention it. Exiting quietly with status 0 matches how standard text filters behave
  when piped into `head`, and keeps FR-023's "nothing on standard error" promise true for the
  most common invocation. This is a normal end of work, not input the tool failed to validate,
  so Constitution principle II (Fail Loudly) does not require a diagnostic here.
- **Bad usage reuses exit status 2** (FR-029, clarified 2026-11-13): the request names only
  statuses 0 and 2. Rather than introduce a third status, invalid usage reuses 2 — the two
  cases are already distinguishable by their diagnostics, and keeping the documented status set
  to {0, 2} is the simpler contract (Constitution principle IV).
- **Match precedence** (FR-018, FR-019) is not specified in the request. Leftmost-wins with a
  fixed email → IP → card tie-break is the simplest rule that makes output deterministic and
  testable.
- **Email shape** (FR-007) uses the common pragmatic address pattern rather than full RFC 5322
  validity, which would match text no log realistically contains and would be far harder to
  test.
- **Leading zeros in octets** are accepted: `010.0.0.7` is treated as an IPv4 address because
  each group's numeric value is in range. Logs do emit zero-padded addresses.
- **Mixed card separators** are accepted: each separator is independently judged, so
  `4111-1111 1111-1111` is recognised. Requiring one uniform separator would add a rule the
  request does not ask for.
- **Over-redaction is the safe direction**: dotted quads that may really be version numbers,
  and long digit runs that happen to pass Luhn, are redacted. A shared log losing a version
  string is cheaper than one leaking a card number.
- **Numeric-domain addresses redact whole** (FR-007a, clarified 2026-11-13): `user@1.2.3.4`
  could have been left as `user@[IP]`, which is what the original FR-007 wording produced. The
  safe direction was chosen instead: the local part of such an address is itself a personal
  identifier, so the whole span is replaced and the username is not left behind.
- **Encoding is fixed at UTF-8** (FR-005a, clarified 2026-11-13): the request did not name an
  encoding. A fixed UTF-8 contract is chosen over the platform/locale default so that output is
  reproducible on any machine, satisfying the constitution's "no hidden state" constraint.
- **Undecodable bytes round-trip**: input bytes that are not valid UTF-8 are passed through to
  the output as the same bytes rather than aborting the run or substituting replacement
  characters, to honour "lines with nothing to redact are output exactly as they were" for
  real-world logs.
- **Counts measure replacements, not distinct values**: the same email address appearing three
  times counts as three.
- **In-place editing, directory recursion, configurable placeholders, and additional identifier
  types** (phone numbers, national IDs, tokens) are out of scope for this feature. Out of scope
  does not mean undefined: a directory named as a FILE is a read failure handled by FR-025
  (clarified 2026-11-13), not unspecified behaviour.
- **Testing**: `pytest` is the test framework, with tests under `tests/` runnable by a bare
  `pytest` from the repository root, per the project constitution.
