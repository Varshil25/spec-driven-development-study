# Feature Specification: Phone Redaction and Output Folder (`logredact`)

**Feature Branch**: `002-phone-redaction-out-dir`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "This repository already contains `logredact`, a command-line tool that removes personal data from log files. Read the existing code and any documentation in the repository before changing it. Change it as follows; everything else it does now must keep working exactly as it does. 1. **Phone numbers.** Phone numbers in international format, a `+` followed by 8 to 15 digits such as `+14155552671`, become `[PHONE]`. With `--count`, the summary on standard error becomes `emails=N ips=N cards=N phones=N`. 2. **Output folder.** A new option `--out-dir DIR` writes the redacted lines of each FILE to a file with the same name in DIR (the file's name only, without its directories) instead of to standard output. DIR is created, with any missing parent directories, if it does not exist, and an existing file of that name in DIR is replaced. When every FILE has been processed, the tool prints `wrote N files` to standard output, where N is the number of output files written. A FILE that cannot be read is handled as it is now: an error message naming the file on standard error, and exit status 2."

## Context: What Already Exists

This feature amends the shipped tool specified in [`specs/001-logredact-cli/spec.md`](../001-logredact-cli/spec.md)
(requirements FR-001 through FR-031a, success criteria SC-001 through SC-009). That
specification remains in force in full. This document adds two capabilities and amends
exactly three of its statements:

| Existing statement | Amendment |
|---|---|
| FR-023 (tally form `emails=N ips=N cards=N`) | A fourth field `phones=N` is appended. |
| FR-021 (precedence: email, IPv4, card) | A fourth category, phone, joins the precedence order last. |
| FR-004 / FR-031 (all redacted output goes to standard output) | With `--out-dir`, redacted output goes to files in that directory instead, and standard output carries only a one-line summary. |

Everything else the tool does today — pass-through fidelity, line-ending and non-UTF-8 byte
preservation, email/IPv4/card recognition, `--help`, exit statuses, read-failure and
write-failure handling — MUST continue to behave exactly as it does now. Requirement FR-049
below makes that preservation itself a testable requirement rather than an aspiration.

New requirement identifiers continue the existing sequence at **FR-032**; new success
criteria continue at **SC-010**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Redact phone numbers from a log (Priority: P1)

An engineer's logs carry customer and on-call phone numbers written in international format.
They pipe the log through the tool, as they already do, and the phone numbers come back as
`[PHONE]` alongside the email, IP, and card redactions they already get — so a log that was
previously unshareable because of a phone number is now shareable with no change to how they
invoke the tool.

**Why this priority**: This is the first of the two requested changes and it delivers value on
its own with no other new behaviour: a phone number in piped input is redacted, and nothing
about the existing invocation, output stream, or exit status changes.

**Independent Test**: Pipe a line containing an international-format phone number into the
tool with no options and confirm standard output contains the same line with the number
replaced by `[PHONE]` and all surrounding text intact.

**Acceptance Scenarios**:

1. **Given** no FILE arguments and no options, **When** `printf 'call +14155552671 now\n' | python -m logredact` runs, **Then** standard output is exactly `call [PHONE] now\n` and the exit status is 0.
2. **Given** the input `+442071838750`, **When** it is piped through the tool, **Then** standard output is `[PHONE]` — a `+` followed by 12 digits is recognized.
3. **Given** the input `+12345678` (eight digits, the shortest accepted) and the input `+123456789012345` (fifteen digits, the longest accepted), **When** each is piped through the tool, **Then** each is replaced in full by a single `[PHONE]`.
4. **Given** the input `+1234567` (seven digits), **When** it is piped through the tool, **Then** it appears in the output unchanged — too short to be a phone number.
5. **Given** the input `+1234567890123456` (sixteen digits), **When** it is piped through the tool, **Then** no `[PHONE]` appears in the output, because a candidate immediately followed by a further digit is not a phone number.
6. **Given** a line containing a phone number, an email address, an IPv4 address, and a Luhn-valid card number, **When** it is piped through the tool, **Then** all four are replaced by their respective placeholders and the rest of the line is unchanged.
7. **Given** input that already contains the literal text `[PHONE]`, **When** it is piped through the tool, **Then** that text is passed through unchanged and is not counted.
8. **Given** a log containing no `+` character at all, **When** it is piped through the tool, **Then** the output is byte-identical to what the tool produced for that input before this feature.

---

### User Story 2 - Write redacted copies into an output folder (Priority: P2)

An operator has a set of rotated log files to hand to a vendor. Instead of one concatenated
stream on standard output that they then have to split apart, they name an output folder and
get one redacted file per input file, named the same as its input, ready to attach or archive.
The tool tells them how many files it wrote.

**Why this priority**: This is the second requested change. It depends only on redaction
already working and can be added on top of the existing file-reading path; it is the larger
of the two changes in surface area, which is why it follows the phone work.

**Independent Test**: Create two small files containing personal data, run the tool with both
paths and `--out-dir` naming a directory that does not exist, and confirm the directory is
created, contains one correctly redacted file per input named after it, and that standard
output is exactly the summary line.

**Acceptance Scenarios**:

1. **Given** readable files `app.log` (containing `user jane@example.com`) and `web.log` (containing `GET / from 10.0.0.7`) and no directory named `clean`, **When** `python -m logredact --out-dir clean app.log web.log` runs, **Then** standard output is exactly `wrote 2 files\n`, the exit status is 0, `clean/app.log` contains `user [EMAIL]` and `clean/web.log` contains `GET / from [IP]`.
2. **Given** the same two files, **When** the tool is run with `--out-dir clean`, **Then** no redacted log content appears on standard output — standard output carries the summary line and nothing else.
3. **Given** a FILE argument that includes directories, such as `logs/2026/app.log`, **When** `--out-dir clean` is used, **Then** the output file is `clean/app.log` — the file's name only, with its directories discarded.
4. **Given** `--out-dir reports/clean/today` where none of `reports`, `reports/clean`, or `reports/clean/today` exists, **When** the tool runs with one FILE, **Then** all three directories are created and the output file is written inside the innermost one.
5. **Given** a directory `clean` that already contains a file named `app.log` with other content, **When** the tool runs with `--out-dir clean app.log`, **Then** `clean/app.log` contains only the redacted contents of the input — the previous content is gone, not appended to.
6. **Given** an empty input file, **When** it is processed with `--out-dir`, **Then** an empty output file of the same name exists in the directory and it counts toward the summary.
7. **Given** one FILE and `--out-dir`, **When** the tool runs, **Then** standard output is exactly `wrote 1 files\n` — the summary wording is fixed and is not adjusted for the singular.
8. **Given** `--out-dir`, FILE operands, and `--count` in any order on the command line, **When** the tool runs, **Then** every option is recognized regardless of position and none is treated as a file name.
9. **Given** files whose line endings are carriage-return-plus-newline, whose last line lacks a trailing newline, and which contain bytes that are not valid UTF-8, **When** they are processed with `--out-dir`, **Then** each output file is byte-for-byte what standard output would have carried for that input file without `--out-dir`.
10. **Given** two FILE operands in different directories but with the same file name, such as `a/app.log b/app.log`, **When** `--out-dir clean` is used, **Then** `clean/app.log` holds the redacted contents of `b/app.log` (the later operand replaced the earlier one's output) and standard output is `wrote 2 files\n`.

---

### User Story 3 - Confirm how many phone numbers were redacted (Priority: P3)

A reviewer checking a log before approval already reads the `--count` tally. The tally now
carries a fourth figure so they can see at a glance that phone numbers were found and
replaced, in the same single line they already parse.

**Why this priority**: Valuable for trust, but the redaction itself is the deliverable; the
tally is evidence about it. It also must not disturb the three existing fields, which
downstream readers may already depend on.

**Independent Test**: Run the tool with `--count` on input with a known number of each of the
four kinds, capture standard error separately, and confirm the line matches the known counts
in the fixed field order.

**Acceptance Scenarios**:

1. **Given** the input line `a@b.io +442071838750`, **When** `python -m logredact --count` runs on it, **Then** standard output is `[EMAIL] [PHONE]\n`, standard error is exactly `emails=1 ips=0 cards=0 phones=1\n`, and the exit status is 0.
2. **Given** input with nothing to redact, **When** `--count` is used, **Then** standard error is exactly `emails=0 ips=0 cards=0 phones=0\n`.
3. **Given** input containing three phone numbers across two lines and two files, **When** `--count` is used, **Then** the `phones` field reports `3` — the total across all input, not per line or per file.
4. **Given** `--count` and `--out-dir` together, **When** the run succeeds, **Then** standard output is the summary line, standard error is the four-field tally, and the tally is written only after the summary line has been written.
5. **Given** `--count` is not passed, **When** the run succeeds, **Then** nothing is written to standard error, exactly as before.

---

### User Story 4 - Fail clearly when input or output cannot be handled (Priority: P3)

An operator names a file that does not exist, or an output folder they cannot create, or
accidentally points the output folder at the very files being read. In each case the tool says
what it could not do and reports failure, rather than printing a summary that implies a
complete set of redacted files exists.

**Why this priority**: Small in scope, but it is what keeps the new summary line trustworthy.
A `wrote N files` line after a partial run is the expensive failure this story prevents.

**Independent Test**: Run the tool with `--out-dir` and a path that does not exist as a FILE,
and confirm standard error names that path, no summary line is printed, and the exit status
is 2.

**Acceptance Scenarios**:

1. **Given** `--out-dir clean` and a FILE path that does not exist, **When** the tool runs, **Then** an error message including that path is written to standard error, no `wrote N files` line appears on standard output, and the exit status is 2.
2. **Given** `--out-dir clean`, a readable file followed by an unreadable one, **When** the tool runs, **Then** the readable file's output file exists in `clean` with its redacted contents, the unreadable file is named on standard error, no summary line is printed, and the exit status is 2.
3. **Given** `--out-dir clean`, an unreadable FILE, and `--count`, **When** the tool fails, **Then** no tally line is written — the only standard-error output is the error message — and the exit status is 2.
4. **Given** `--out-dir` and no FILE operands, **When** the tool runs, **Then** a diagnostic naming the conflict is written to standard error, standard input is not read, no directory is created, and the exit status is 2.
5. **Given** `--out-dir` naming a path that exists as a regular file rather than a directory, **When** the tool runs, **Then** a diagnostic naming that path is written to standard error and the exit status is 2.
6. **Given** `--out-dir` naming a directory that cannot be created or written to because of permissions, **When** the tool runs, **Then** a diagnostic naming that directory is written to standard error, no summary line is printed, and the exit status is 2.
7. **Given** a FILE whose output file in DIR would be that same file — for example `python -m logredact --out-dir . app.log` run in the directory holding `app.log` — **When** the tool runs, **Then** a diagnostic naming that file is written to standard error, the file's contents are left untouched, and the exit status is 2.
8. **Given** `--help` together with `--out-dir`, **When** the tool runs, **Then** usage text describing `--out-dir` appears on standard output, the directory is not created, no input is read, standard error is empty, and the exit status is 0.
9. **Given** `--out-dir` without a directory argument after it, **When** the tool runs, **Then** a usage message is written to standard error and the exit status is 2.

---

### Edge Cases

**Phone recognition**

- **Too short**: `+1234567` (seven digits) is left unchanged; eight is the minimum.
- **Too long**: `+1234567890123456` (sixteen digits) yields no `[PHONE]`, because the
  fifteen-digit candidate is immediately followed by another digit. The run of digits is then
  considered for the existing card rule exactly as it is today, so a `+` in front of a
  sixteen-digit Luhn-valid card number still produces `+[CARD]` as it does now.
- **Separators are not accepted**: `+1 415 555 2671` and `+1-415-555-2671` contain no phone
  number by this rule; the digit groups are too short to be anything else, so these lines pass
  through unchanged. (Grouped phone formats are out of scope — see Assumptions.)
- **No plus sign**: `14155552671` has no leading `+` and is not a phone number. Ten or eleven
  bare digits are also too short to be a card candidate, so such text is unchanged.
- **Plus sign alone or followed by non-digits**: `+`, `++14155552671`, and `+abc12345678` yield
  no phone redaction at the `+`; in `++14155552671` the second `+` begins a valid candidate, so
  the output is `+[PHONE]`.
- **Phone inside an email address**: `+14155552671@example.com` is a single `[EMAIL]`, not a
  `[PHONE]` followed by a domain, because the email local part may contain `+` and digits and
  email takes precedence at the same starting position.
- **Phone adjacent to a card number**: a `+` followed by 13 to 15 digits that also pass the
  Luhn checksum becomes `[PHONE]`, not `[CARD]`, because the phone candidate starts one
  character earlier and the earliest-starting match wins. This is a deliberate, documented
  change in outcome for that specific input shape — see Assumptions.
- **Arithmetic-looking text**: `total=5+12345678` becomes `total=5[PHONE]`. The recognition
  rule is purely `+` followed by 8-15 digits and does not inspect what precedes the `+`.
- **Non-UTF-8 byte inside the digits**: a byte that is not valid UTF-8 between the `+` and the
  digits, or interrupting them, breaks the candidate; the byte still passes through unchanged.
- **Phone split across lines**: a `+` at the end of one line and digits at the start of the
  next is not a phone number; matching never spans a line boundary.

**Output folder**

- **Directory already exists**: an existing `DIR` is used as it is; its other contents are
  left alone and only files whose names match an input file are replaced.
- **Nested directory creation**: missing parent directories of `DIR` are created too.
- **Duplicate input file names**: two FILE operands with the same base name write to the same
  output path; the later operand's output replaces the earlier one's, and the summary counts
  each FILE processed, so two operands report `wrote 2 files`.
- **A FILE of `-`**: still a literal path to a file named `-`, whose output file in DIR is
  therefore also named `-`.
- **Zero files is a usage error, not a zero count**: `--out-dir` with no FILE operands fails
  rather than reading standard input or printing `wrote 0 files`, because either of those
  would discard or misreport the user's input.
- **Summary when a read fails**: no `wrote N files` line is printed on a failing run, so the
  line never implies files that are not there. Output files already completed stay on disk.
- **Output path collides with an input file**: the run fails before the input is truncated,
  so `--out-dir .` cannot destroy the log it was asked to redact.
- **Standard output still matters**: if writing the summary line to standard output fails,
  the run fails with the existing output-write diagnostic and exit status 2, and no tally is
  written.
- **`--out-dir` is not required**: without it, output goes to standard output exactly as it
  does today, including the concatenation order of multiple FILE operands.

## Requirements *(mandatory)*

### Functional Requirements

**Phone number redaction**

- **FR-032**: The tool MUST replace each recognized phone number in the input with the literal
  text `[PHONE]`.
- **FR-033**: A recognized phone number MUST be a `+` character followed immediately by 8 to
  15 decimal digits, inclusive, with no separators, spaces, or other characters between them.
  `+14155552671` and `+442071838750` MUST be recognized; `+1234567` MUST NOT.
- **FR-034**: A phone number candidate that is immediately followed by a further digit MUST
  NOT be redacted. Consequently a `+` followed by 16 or more digits produces no `[PHONE]`, and
  the digits are then subject to the existing card rule (FR-016 through FR-019a) unchanged.
- **FR-035**: Phone numbers MUST participate in the existing single-claim rule (FR-020): each
  character of a line belongs to at most one redaction and redactions never nest or overlap.
- **FR-036**: FR-021's precedence order is amended to four categories. The earliest-starting
  match MUST still win; where two categories start at the same position, precedence MUST be
  email, then IPv4, then card, then phone. `+14155552671@example.com` MUST therefore produce
  exactly one `[EMAIL]`.
- **FR-037**: FR-022 MUST continue to hold for the new category: substituted `[PHONE]` text
  MUST NOT be re-examined for redaction, and the literal text `[PHONE]` already present in the
  input MUST be passed through unchanged and uncounted.

**Counting**

- **FR-038**: FR-023's tally form is amended. With `--count`, the tool MUST write to standard
  error a single line of the exact form `emails=N ips=N cards=N phones=N`, terminated by a
  newline, in that field order, where each N is the total number of replacements of that kind
  across all input read.
- **FR-039**: The `phones` field MUST count phone replacements on the same basis as the other
  three (FR-026): three phone numbers on one line contribute 3, and the field MUST report `0`
  when no phone number was replaced.

**Output folder**

- **FR-040**: The tool MUST accept an option `--out-dir DIR` taking one directory path, usable
  together with `--count` and with FILE operands in any order on the command line (FR-001).
  `--out-dir` given without a directory argument MUST be a usage error under FR-030.
- **FR-041**: With `--out-dir DIR`, the redacted lines of each FILE MUST be written to a file
  inside `DIR` whose name is that FILE's base name — the final path component only, with any
  leading directories discarded — and MUST NOT be written to standard output.
- **FR-042**: If `DIR` does not exist, the tool MUST create it, including any missing parent
  directories.
- **FR-043**: If a file of the target name already exists in `DIR`, its previous content MUST
  be replaced in full; the redacted output MUST NOT be appended to it. Where two FILE operands
  share a base name, the later operand's output replaces the earlier operand's.
- **FR-044**: Each output file MUST contain exactly the bytes that standard output would have
  carried for that FILE had `--out-dir` not been given, so the fidelity requirements FR-005,
  FR-005a, FR-006, FR-007, and FR-007a hold for output files as written.
- **FR-045**: When every FILE has been processed successfully, the tool MUST write to standard
  output a single line of the exact form `wrote N files`, terminated by a newline, where N is
  the number of output files written, counting one per FILE processed. The wording is fixed and
  MUST NOT be pluralized differently for N of 1. On such a run standard output MUST contain
  that line and nothing else, and the exit status MUST be 0.
- **FR-046**: With `--count` and `--out-dir` together, the tally line (FR-038) MUST be written
  to standard error only after the summary line (FR-045) has been written and flushed to
  standard output, preserving FR-024's ordering guarantee.
- **FR-047**: `--out-dir` given with no FILE operand MUST be a usage error: the tool MUST write
  a diagnostic to standard error that names the conflict, MUST NOT read standard input, MUST
  NOT create `DIR`, MUST NOT write a summary line or a tally line, and MUST exit with status 2.
- **FR-048**: If `DIR` cannot be created or used as a directory, or an output file cannot be
  created, replaced, written, or closed, the tool MUST write to standard error a diagnostic
  naming the directory or the output file path it could not use, MUST NOT write a summary line,
  MUST NOT write a tally line even if `--count` was passed, MUST NOT emit a stack trace or
  other unhandled-error text, and MUST exit with status 2.
- **FR-049**: If the output file computed for a FILE would be that same FILE, the tool MUST
  write to standard error a diagnostic naming that file, MUST leave that file's contents
  unmodified, MUST NOT write a summary line, and MUST exit with status 2.
- **FR-050**: On encountering an unreadable FILE while `--out-dir` is in effect, the existing
  behaviour (FR-028, FR-029) MUST apply unchanged: a diagnostic naming the path as given on the
  command line, no further sources read, exit status 2. Additionally, no summary line and no
  tally line MUST be written, and output files already completed for earlier FILE operands MUST
  remain on disk.
- **FR-051**: `--help` and `-h` MUST continue to satisfy FR-030a when `--out-dir` is also
  given: usage text — which MUST document `--out-dir` — goes to standard output, `DIR` is not
  created, no input source is opened, standard error is empty, and the exit status is 0.

**Preservation of existing behaviour**

- **FR-052**: Without `--out-dir`, every behaviour specified by FR-001 through FR-031a MUST be
  unchanged, including writing all redacted output to standard output as a single concatenated
  stream, the handling of a failed standard-output write (FR-031a), and the exit statuses.
- **FR-053**: For input containing no `+` character, the tool's standard output, standard
  error, and exit status MUST be unchanged by this feature, except that a `--count` tally line
  gains the `phones=0` field required by FR-038.

### Key Entities

- **Redaction category**: now one of **four** — email, IPv4 address, payment card number, or
  phone number — each with its own recognition rule and its own fixed placeholder (`[EMAIL]`,
  `[IP]`, `[CARD]`, `[PHONE]`).
- **Tally**: now **four** non-negative totals, one per category, accumulated over all input and
  reported in the fixed order emails, ips, cards, phones only on request.
- **Output destination**: either standard output (the default, unchanged) or a directory given
  by `--out-dir`, in which one output file per FILE operand is created, named after that
  operand's base name.
- **Run summary**: the count of output files written, reported on standard output only on a
  fully successful `--out-dir` run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-010**: All three worked examples from the feature description reproduce exactly —
  byte-identical standard output, byte-identical standard error, the stated output files and
  their contents, and the stated exit status — with no manual interpretation needed.
- **SC-011**: On a fixture of at least 50 lines containing known international-format phone
  numbers and known look-alikes (7-digit, 16-digit, separator-grouped, and unprefixed digit
  runs), 100% of the planted phone numbers are redacted and 0% of the look-alike tokens are
  altered.
- **SC-012**: The complete list of input shapes whose redacted output differs from before this
  feature is exactly two — text containing a `+` followed by 8 to 15 digits, and a `--count`
  tally line — and that list is demonstrated rather than asserted, by replaying the feature-001
  acceptance scenarios and recording every difference observed.
- **SC-013**: For a corpus containing no `+` character, the tool's standard output is
  byte-identical before and after this feature in 100% of cases.
- **SC-014**: For a set of at least three input files exercising carriage-return-plus-newline
  endings, a missing final newline, and bytes that are not valid UTF-8, each `--out-dir` output
  file is byte-identical to the standard output the same tool produces for that single file
  without `--out-dir`, in 100% of cases.
- **SC-015**: Every new functional requirement FR-032 through FR-053 is covered by at least one
  automated test that cites its identifier, and the full suite passes.
- **SC-016**: Every new failure path (no FILE with `--out-dir`, `DIR` unusable, output file
  unwritable, output path equal to its input, unreadable FILE under `--out-dir`, `--out-dir`
  missing its argument) has a test asserting both the diagnostic naming the offending path or
  conflict and the exit status 2, and asserting that no stack trace appears on standard error.
- **SC-017**: A reviewer can tell from the tool's output alone whether a complete set of
  redacted files was produced, because `wrote N files` appears only on a run that exits 0 and
  never on a run that exits 2.
- **SC-018**: Memory use for an `--out-dir` run stays bounded by the longest input line rather
  than growing with total input size or with the number of FILE operands, verified on a
  multi-file input of at least 1 GB in total.

## Assumptions

Reasonable defaults chosen where the feature description did not specify. Each states what
was decided and why, so a different choice can be made deliberately rather than by accident.

- **Phone candidates followed by more digits are not phone numbers (FR-034)**: the description
  gives the rule as "a `+` followed by 8 to 15 digits" without saying what happens when more
  digits follow. Taking the first 15 digits of a longer run would change today's output for
  input such as `+4111111111111111`, which the tool currently renders `+[CARD]`; the
  not-followed-by-a-digit guard is what makes the requester's "everything else must keep
  working exactly as it does" true. It also mirrors the existing FR-014 and FR-018 adjacency
  rules, so all four categories now share one convention.
- **No restriction on what precedes the `+`**: the rule is applied literally, so
  `total=5+12345678` is redacted. Adding a left-hand guard would be a judgement about
  arithmetic-looking text that the description does not ask for, and Principle IV favours the
  smaller design. The consequence is recorded as an edge case so it is a known trade-off.
- **Phone outranks card when a `+` precedes a valid card number (FR-036)**: a `+` followed by
  13 to 15 Luhn-valid digits becomes `[PHONE]` where it previously became `+[CARD]`. This
  follows from the existing earliest-starting-match rule rather than from a new decision — the
  phone candidate begins one character earlier — and a leading `+` is a strong signal of a
  phone number. It is the one input shape where existing redaction output changes; the change
  is a different placeholder on text that was already being redacted, never a leak.
- **Email outranks phone at the same position (FR-036)**: phone is placed last in the
  precedence order so that `+14155552671@example.com` stays a single `[EMAIL]`, preserving
  today's behaviour for addresses whose local part begins with `+`.
- **Grouped and national phone formats are out of scope**: only the international form the
  description gives is recognized. Separator-grouped forms (`+1 415 555 2671`), parenthesized
  area codes, `00`-prefixed international prefixes, and national formats without a `+` are not
  redacted. Widening recognition would raise the false-positive rate against ordinary log text
  and is not what was asked for.
- **`--out-dir` with no FILE operand fails (FR-047)**: the description defines `--out-dir` in
  terms of "each FILE", and standard input has no file name to derive an output name from. The
  alternatives — silently writing standard input's redacted output to standard output anyway,
  or printing `wrote 0 files` after discarding it — are both exactly the "plausible-looking
  wrong answer" the project constitution's Fail Loudly principle forbids.
- **An output path that is also an input path fails (FR-049)**: `--out-dir .` on a log in the
  current directory would otherwise truncate the input while it was being read, producing a
  partly-empty "redacted" file and no diagnostic. This guard is a deliberate, small addition
  beyond the literal description, justified by Fail Loudly; it is the only new failure mode the
  description does not imply, and removing it would mean accepting silent data loss.
- **`wrote N files` counts FILE operands processed (FR-045)**: with duplicate base names two
  operands write to one path, and the summary reports `2`. The count describes the work done,
  it matches the operand count a user can see on their own command line, and the description's
  worked example (two operands, `wrote 2 files`) is consistent with it.
- **The summary wording is literal (FR-045)**: `wrote 1 files` is printed for a single file.
  The description fixes the text as `wrote N files`; inventing a singular form would be output
  a caller parsing the line did not ask for.
- **`--count` and `--out-dir` compose (FR-046)**: the description does not say they conflict,
  so both work together, the tally still counts across all input, and the existing
  output-before-tally ordering is preserved with the summary line taking the place of the
  redacted stream.
- **The summary goes to standard output, not standard error (FR-045)**: the description says
  so explicitly. It is a result, not a diagnostic, and FR-031 is read accordingly: on an
  `--out-dir` run standard output legitimately carries the summary and no log content.
- **Output files are written as the input is read**: output is streamed line by line into each
  output file rather than buffered and written at the end, so memory stays bounded (SC-018) and
  a later failure leaves earlier files complete (FR-050). No temporary-file-and-rename scheme is
  specified; a run that fails partway may leave a partially written output file for the FILE it
  failed on, and the exit status 2 is what tells the caller not to trust the set.
- **Directories are created when needed, not eagerly**: `DIR` is created on a run that will
  actually write to it, which is why a help run (FR-051) and a usage error (FR-047) leave the
  filesystem untouched.
- **Existing constraints carry over unchanged**: Python 3.11 or newer, standard library only,
  the `logredact` package under `src/`, invoked as `python -m logredact`, one line resident at a
  time, no network access, and no modification of named input files. The new `--out-dir` writes
  are writes to a path the caller named, which the constitution's no-hidden-state constraint
  permits.
- **No other personal data becomes in scope**: names, MAC addresses, URLs, usernames, and
  session tokens are still not redacted. This feature adds exactly one category.
- **Placeholders remain fixed and non-configurable**: `[PHONE]` is not configurable and there
  is still no flag to enable or disable an individual category.
