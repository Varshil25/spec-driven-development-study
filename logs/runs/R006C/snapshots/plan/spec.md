# Feature Specification: Phone Redaction and Output Folder

**Feature Branch**: `002-phone-redaction-out-dir`

**Created**: 2026-11-09

**Status**: Draft

**Input**: User description: "This repository already contains `logredact`, a command-line tool that removes personal data from log files. Read the existing code and any documentation in the repository before changing it. Change it as follows; everything else it does now must keep working exactly as it does. 1. **Phone numbers.** Phone numbers in international format, a `+` followed by 8 to 15 digits such as `+14155552671`, become `[PHONE]`. With `--count`, the summary on standard error becomes `emails=N ips=N cards=N phones=N`. 2. **Output folder.** A new option `--out-dir DIR` writes the redacted lines of each FILE to a file with the same name in DIR (the file's name only, without its directories) instead of to standard output. DIR is created, with any missing parent directories, if it does not exist, and an existing file of that name in DIR is replaced. When every FILE has been processed, the tool prints `wrote N files` to standard output, where N is the number of output files written. A FILE that cannot be read is handled as it is now: an error message naming the file on standard error, and exit status 2."

## Context: this feature amends an existing tool

The tool specified in [`specs/001-logredact-cli/spec.md`](../001-logredact-cli/spec.md) is already
built and tested. This specification is an **amendment**: it adds a fourth redaction category and a
second output destination, and it changes exactly two existing observable behaviours — the
`--count` summary line, and where redacted lines go when `--out-dir` is supplied.

Numbering continues from the 001 specification (FR-019, SR-010, SC-011, A-13 onwards) so that every
cross-reference stays unambiguous. Where a requirement of 001 is changed rather than added to, this
document says so explicitly and the amended wording here governs.

**Requirements of 001 amended by this feature**: FR-010, FR-013, FR-014, FR-016, FR-017, SR-001,
SR-004, SR-005, SR-007, A-8, A-9.

**Everything else in 001 is unchanged and MUST keep working exactly as it does today** — the email,
IPv4 and card rules, pass-through of unmatched text, line terminators, non-UTF-8 bytes, operand
order, the 1 MiB line cap, exit statuses 0/2/141, and the content of every diagnostic.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Redact phone numbers from a log (Priority: P1)

An engineer is about to share a support log that contains customer telephone numbers in
international format. They pipe the log through the tool and the numbers come back as a fixed
placeholder, alongside the email addresses, IP addresses and card numbers the tool already removes,
so the log is safe to attach to a ticket.

**Why this priority**: A phone number is personal data that the tool currently lets through. Until
this story is implemented, the tool silently produces output that looks redacted but is not — the
most expensive failure mode this tool has. It is also the smallest useful slice: it needs no new
option and no file handling.

**Independent Test**: Feed a line containing an international-format phone number on standard input
with no arguments and compare standard output byte-for-byte against the expected redacted line.
Delivers the protective value on its own, with no new flags involved.

**Acceptance Scenarios**:

1. **Given** no FILE arguments and no options, **When** `call +14155552671 now\n` is written to
   standard input, **Then** standard output is exactly `call [PHONE] now\n` and the exit status
   is 0.
2. **Given** no FILE arguments, **When** `+442071838750\n` is written to standard input, **Then**
   standard output is exactly `[PHONE]\n` (12 digits, inside the 8-15 range).
3. **Given** no FILE arguments, **When** `+12345678\n` (8 digits) and `+123456789012345\n`
   (15 digits) are written to standard input, **Then** each line is exactly `[PHONE]\n` — both
   bounds are inclusive.
4. **Given** no FILE arguments, **When** `+1234567\n` (7 digits) is written to standard input,
   **Then** standard output is exactly `+1234567\n`, unchanged.
5. **Given** no FILE arguments, **When** `+1234567890123456\n` (16 digits) is written to standard
   input, **Then** no `[PHONE]` appears in standard output and no digit of the run is removed by
   the phone rule.
6. **Given** no FILE arguments, **When** `14155552671\n` (no leading `+`) is written to standard
   input, **Then** standard output is exactly `14155552671\n`, unchanged.
7. **Given** no FILE arguments, **When** `user jane@example.com from 10.0.0.7\n` is written to
   standard input, **Then** standard output is exactly `user [EMAIL] from [IP]\n` — the existing
   categories are untouched by this change.
8. **Given** no FILE arguments, **When** `paid with 4111 1111 1111 1111, ref 1234567890123\n` is
   written to standard input, **Then** standard output is exactly
   `paid with [CARD], ref 1234567890123\n` — the card rule is untouched by this change.

---

### User Story 2 - Redact a set of log files into an output folder (Priority: P2)

An operator has a directory of rotated log files to hand to a vendor. Instead of redacting each one
with a separate command and a separate redirection, they name all the files once and give an output
folder. They get back one redacted copy per input file, named the same as its input, and a one-line
confirmation of how many files were written.

**Why this priority**: It is the main ergonomic win of this feature and the common real-world
invocation, but it is additive — the redaction behaviour it depends on is already proven, and the
tool remains fully usable without it by redirecting standard output one file at a time.

**Independent Test**: Create two small files with known content, run the tool with both names and
`--out-dir` pointing at a folder that does not exist, then confirm the folder was created, that it
contains exactly two files named after the inputs with the expected redacted contents, and that
standard output is exactly `wrote 2 files\n`. Testable without `--count` and without error cases.

**Acceptance Scenarios**:

1. **Given** files `app.log` (containing `user jane@example.com`) and `web.log` (containing
   `GET / from 10.0.0.7`) exist and `clean` does not exist, **When** the tool is run with
   `--out-dir clean app.log web.log`, **Then** `clean/app.log` contains the redaction of `app.log`,
   `clean/web.log` contains the redaction of `web.log`, standard output is exactly
   `wrote 2 files\n`, standard error is empty, and the exit status is 0.
2. **Given** `--out-dir` is supplied, **When** the run succeeds, **Then** no redacted line appears
   on standard output — the only thing standard output carries is the `wrote N files` line.
3. **Given** the operands are `logs/2026/app.log`, **When** the tool is run with `--out-dir clean`,
   **Then** the output file is `clean/app.log` — only the final path component of the operand is
   used, and no `logs` or `2026` directory is created inside `clean`.
4. **Given** `--out-dir a/b/c` where none of `a`, `b` or `c` exists, **When** the tool runs,
   **Then** all three directories are created and the output files appear in `a/b/c`.
5. **Given** `clean/app.log` already exists with unrelated content that is longer than the new
   output, **When** the tool is run with `--out-dir clean app.log`, **Then** `clean/app.log`
   contains exactly the redaction of `app.log` and no remnant of its previous content.
6. **Given** `--out-dir clean` and a single operand, **When** the run succeeds, **Then** standard
   output is exactly `wrote 1 files\n` — a fixed format, not pluralised.
7. **Given** `--out-dir clean app.log` where `app.log` is readable, **When** the tool exits,
   **Then** `app.log` is byte-for-byte unchanged.
8. **Given** `--out-dir` is **not** supplied, **When** the tool runs with FILE operands, **Then**
   the behaviour is exactly as it is today: the redaction of every operand on standard output, in
   operand order, and no `wrote N files` line.

---

### User Story 3 - See the phone total in the summary (Priority: P3)

A reviewer approving a log for release reads the one-line tally to confirm what was removed. The
tally now reports phone numbers alongside the three existing categories, so the reviewer can see at
a glance that phone numbers were looked for and how many were found.

**Why this priority**: It is a verification aid layered on Story 1, not a protective function. The
tool is already safe without it.

**Independent Test**: Run with `--count` over input with a known number of each kind of match and
assert the exact standard-error line, while standard output is unaffected by the flag.

**Acceptance Scenarios**:

1. **Given** `--count` is supplied, **When** `a@b.io +442071838750\n` is read from standard input,
   **Then** standard output is exactly `[EMAIL] [PHONE]\n` and standard error is exactly
   `emails=1 ips=0 cards=0 phones=1\n`.
2. **Given** `--count` is supplied, **When** the input contains no redactable values, **Then**
   standard error is exactly `emails=0 ips=0 cards=0 phones=0\n` and the exit status is 0.
3. **Given** `--count` is supplied, **When** `a@b.io 1.2.3.4\n` is read from standard input,
   **Then** standard error is exactly `emails=1 ips=1 cards=0 phones=0\n` — the previously
   specified line with the new field appended.
4. **Given** `--count` is supplied and multiple FILE operands are read, **When** the run finishes,
   **Then** the summary reports the totals across all operands, not per file, including the phone
   total.
5. **Given** `--count` and `--out-dir clean` are both supplied, **When** the run succeeds, **Then**
   standard error is exactly the four-field tally line, standard output is exactly
   `wrote N files\n`, and no tally text appears in any output file.
6. **Given** `--count` is not supplied, **When** the run succeeds, **Then** nothing is written to
   standard error.

---

### User Story 4 - Fail loudly when the output folder cannot be used (Priority: P3)

An operator points `--out-dir` at a path they cannot create, or names an input file that does not
exist. Instead of quietly producing fewer redacted files than expected, the tool names what went
wrong on standard error and exits with a failure status their script can detect.

**Why this priority**: Low frequency, but a missing or truncated output file that is mistaken for a
complete redaction is exactly the failure this tool exists to prevent.

**Independent Test**: Run with `--out-dir` naming a path that cannot be created and assert the exit
status is 2, that standard error identifies the path, and that no output file was produced.

**Acceptance Scenarios**:

1. **Given** operands `app.log missing.log web.log` and `--out-dir clean`, **When** the tool runs,
   **Then** `clean/app.log` and `clean/web.log` are written in full, no `clean/missing.log` is
   created, standard error contains a message naming `missing.log`, standard output is exactly
   `wrote 2 files\n`, and the exit status is 2.
2. **Given** `--out-dir` names a path that already exists as a regular file, **When** the tool
   runs, **Then** standard error names that path, no input file is read, no output file is written,
   nothing is written to standard output, and the exit status is 2.
3. **Given** `--out-dir` names a path that cannot be created because a parent directory denies
   write permission, **When** the tool runs, **Then** standard error names that path, nothing is
   written to standard output, and the exit status is 2.
4. **Given** `--out-dir clean` is supplied with **no** FILE operand, **When** the tool runs,
   **Then** standard error describes the rejected usage, standard input is not read, nothing is
   written to standard output, no directory is created, and the exit status is 2.
5. **Given** `--out-dir clean app.log` where `clean/app.log` cannot be opened for writing,
   **When** the tool runs, **Then** standard error names the output path, the remaining operands
   are still processed, and the exit status is 2.
6. **Given** `--out-dir .` and operand `app.log` in the current directory, so the output path is
   the input file itself, **When** the tool runs, **Then** `app.log` is **not** truncated or
   modified, standard error names it, the remaining operands are still processed, and the exit
   status is 2.
7. **Given** `--out-dir clean` and an operand whose second line is 1 MiB + 1 characters long,
   **When** the tool runs, **Then** the run stops, no part of the over-length line is written to
   any output file, standard error names the input source and reports that a line exceeded the
   maximum length, no `wrote N files` line is written to standard output, and the exit status is 2.
8. **Given** an unrecognised option such as `--out_dir` or `--out`, **When** the tool runs,
   **Then** standard error describes the rejected option, nothing is written to standard output,
   no directory is created, and the exit status is non-zero.
9. **Given** `--out-dir` is supplied with no value as the last argument, **When** the tool runs,
   **Then** standard error describes the rejected usage and the exit status is non-zero.
10. **Given** any failing `--out-dir` run, **When** the tool exits, **Then** standard error
    contains no Python traceback and no contents of any input file.

---

### Edge Cases

**Phone recognition**

- **Digit count bounds**: `+` with 8 digits and `+` with 15 digits are phone numbers; `+` with 7 or
  fewer, and `+` with 16 or more, are not (FR-019, FR-020). A 16-digit run after a `+` is not
  partially redacted — the phone rule either takes all of a run's digits or none of them, so no
  digits of a near-miss are removed and none are left behind (SR-006).
- **No separators inside a phone number**: only an unbroken digit run counts. `+1 415 555 2671`
  and `+1-415-555-2671` are not phone numbers under FR-019; their digit groups are then considered
  by the existing card rule as they are today.
- **A phone number that is also a card candidate**: a `+` followed by 13 to 15 Luhn-valid digits
  matches both rules. The phone rule wins and the `+` is consumed as part of the replacement, so
  the output is `[PHONE]` and not `+[CARD]` (FR-021, A-13).
- **A phone number inside an email address**: `+14155552671@example.com` is a single `[EMAIL]`,
  because the email rule has the highest precedence and the local part may contain `+` and digits
  (FR-021). It is counted once, as an email.
- **Repeated `+`**: in `++14155552671` the match begins at the second `+`, leaving the first in
  place: `+[PHONE]`.
- **A digit immediately before the `+`**: in `99+14155552671` the phone number is still recognised
  (`99[PHONE]`); the digits before the `+` are not part of a phone number and are left to the
  existing rules (A-14).
- **A `+` followed by non-digits**: `+abc`, `+`, `+ 14155552671` (space after the `+`) are left
  unchanged.
- **Phone-like text at a line boundary**: a phone number at the very start or very end of a line,
  with or without a terminator, is redacted the same as one in the middle.

**Output folder**

- **Operand with directories**: only the final path component names the output file; `--out-dir`
  never reproduces the operand's directory structure (FR-024, Story 2 scenario 3).
- **Two operands with the same final path component** (for example `a/app.log b/app.log`): the
  second output write replaces the first, so one file remains in DIR holding the redaction of the
  second operand, and the count reported is 2 because two operand outputs were written (A-18).
- **The same operand named twice**: its redaction is written twice to the same output file; the
  final content is one redaction of it, and the reported count is 2 (A-18).
- **Output folder already exists**: it is used as it is; it is not emptied, and files in it that no
  operand names are left alone (FR-025).
- **Output path is the input file**: refused for that operand rather than truncating the input,
  which FR-017 forbids (Story 4 scenario 6, A-19).
- **Output path inside DIR is an existing symbolic link that points outside DIR**: the write is
  refused rather than following the link out of DIR (SR-010).
- **`--out-dir` with an empty value** (`--out-dir ""`): the folder cannot be created, so it is a
  failure reported on standard error with exit status 2 (FR-029).
- **`--out-dir` with no FILE operand**: a usage error, not a silent fall back to standard output
  and not a file named after standard input (FR-031, A-16).
- **A later operand is unreadable after earlier output files were written**: the files already
  written stay written and complete; the run still reports the failure and exits 2, and the
  `wrote N files` line counts only the files actually written (FR-028, A-17).
- **The run stops early** because a line exceeded the 1 MiB cap: output files already completed
  stay, the output file of the operand being read keeps the lines written before the offending one,
  and **no** `wrote N files` line is written, so a partial count cannot be mistaken for a complete
  one (FR-033, A-17).
- **Downstream pipe closed early** with `--out-dir`: only the short `wrote N files` line goes to
  standard output, so a closed consumer is handled exactly as it is today (A-7 of 001 is unchanged).
- **Empty input file with `--out-dir`**: an empty output file of the same name is created and
  counted — an empty redaction is still a redaction that was written.

## Requirements *(mandatory)*

### Functional Requirements

**Phone numbers**

- **FR-019**: The tool MUST replace every international-format phone number in the input with the
  literal `[PHONE]`. An international-format phone number is a literal `+` immediately followed by
  8 to 15 decimal digits, both bounds inclusive, with no separator, space or other character inside
  the digit run. The `+` is part of the match and MUST be replaced along with the digits.
- **FR-020**: A phone candidate MUST NOT be immediately followed by a decimal digit. This extends
  the no-fragment rule of FR-013 to the new category: a `+` followed by 16 or more digits contains
  no phone number, and no leading part of such a run may be replaced.
- **FR-021**: The fixed precedence of FR-014 becomes **email, then IPv4 address, then phone number,
  then card number**. An overlapping region is still redacted exactly once, counted once, under the
  winning kind, and text already replaced by a placeholder MUST NOT be re-scanned. This amends
  FR-014; every other clause of FR-014 is unchanged.
- **FR-022**: With `--count`, the single line the tool writes to standard error after all redacted
  output has been written and flushed MUST be of the form `emails=N ips=N cards=N phones=N`, in
  that field order, where each N is the total number of replacements of that kind across all inputs
  in the run. This amends the format in FR-010; the timing, the stream, the accumulation across
  sources, and the rule that no tally is written on a failing run are unchanged.

**Output folder**

- **FR-023**: The tool MUST accept a new option `--out-dir DIR`, taking one directory path as its
  value, at most once per invocation. This extends the argument allowlist of SR-001; see SR-016.
- **FR-024**: With `--out-dir DIR` and one or more FILE operands, the tool MUST write the redacted
  lines of each FILE to a file in DIR whose name is the **final path component of that FILE operand
  only**, with every directory part of the operand discarded, and MUST NOT write any redacted line
  to standard output.
- **FR-025**: If DIR does not exist, the tool MUST create it, including every missing parent
  directory. If DIR already exists as a directory, the tool MUST use it as it is, without removing
  or altering any file in it that no FILE operand names.
- **FR-026**: If a file of that name already exists in DIR, its content MUST be replaced in full by
  the redacted output, with no remnant of its previous content.
- **FR-027**: When every FILE operand has been processed, the tool MUST write exactly one line,
  `wrote N files`, to standard output, where N is the decimal number of operand outputs written in
  full during the run. The format is fixed and is not pluralised: a single file reports
  `wrote 1 files`.
- **FR-028**: If a FILE operand cannot be opened or read while `--out-dir` is in effect, the tool
  MUST behave as FR-012 already requires — write a message to standard error that includes that
  file name as given on the command line, process every remaining operand, and exit with status 2 —
  and MUST NOT create an output file for that operand. The `wrote N files` line is still written,
  with N counting only the operand outputs actually written.
- **FR-029**: If DIR cannot be created, or exists but is not a directory, the tool MUST write a
  message to standard error naming DIR as given on the command line, MUST NOT read any FILE
  operand, MUST write nothing to standard output, and MUST exit with status 2.
- **FR-030**: If an output file cannot be opened, written or flushed, the tool MUST write a message
  to standard error naming that output path, MUST process every remaining operand, and MUST exit
  with status 2. That operand's output is not counted in N.
- **FR-031**: `--out-dir` supplied with no FILE operand MUST be rejected as a usage error: a
  message on standard error, nothing on standard output, standard input not read, DIR not created,
  and exit status 2.
- **FR-032**: `--out-dir` and `--count` MUST be usable together. The tally goes to standard error
  per FR-022, the `wrote N files` line goes to standard output per FR-027, and neither appears in
  any output file.
- **FR-033**: When a run with `--out-dir` stops early under FR-018 (a line over the 1 MiB cap), no
  `wrote N files` line may be written, so a partial count cannot be mistaken for a complete one.
  Output already written to any output file remains written, and no part of the over-length line is
  written to any output file.
- **FR-034**: Output to a file in DIR MUST be written as the input is read, so that peak memory
  stays bounded by one line regardless of how large any FILE is and how many FILE operands there
  are. This extends FR-016 to the new destination.
- **FR-035**: Without `--out-dir`, every observable behaviour of the tool MUST be exactly as it is
  today, with the sole exception of the two changes this specification makes to redaction and to
  the `--count` line (FR-019 to FR-022).
- **FR-036**: The tool MUST NOT write to a FILE operand through an `--out-dir` destination. If the
  output path for an operand names the same file as that operand, the tool MUST refuse to write it,
  leaving the operand unmodified, report it on standard error, process every remaining operand, and
  exit with status 2. This upholds FR-017 under the new write path.

### Security Requirements

Derived from OWASP ASVS and the project Security Baseline; each is a functional requirement and
MUST have at least one automated test. SR-001 to SR-009 of 001 remain in force except where amended
below.

- **SR-010**: The output path for an operand MUST be formed from DIR plus the operand's final path
  component only. No other part of any operand may contribute to a path, and no input data may.
  The tool MUST NOT write outside DIR: if the output path inside DIR is a symbolic link that
  resolves outside DIR, the write MUST be refused and reported rather than followed (Security
  Baseline — path confinement, no path assembly from untrusted input; ASVS V12 file handling).
- **SR-011**: Files and directories the tool creates MUST be created with the narrowest permissions
  that let the feature work, set at creation and not relaxed afterwards: an output file created by
  the tool MUST be owner-read/write only, and a directory created by the tool MUST be
  owner-accessible only. An output file that already exists keeps the permissions its owner chose;
  the tool MUST NOT widen them (Security Baseline — file permissions).
- **SR-012**: No FILE operand may be opened for writing, creation or truncation at any point,
  including through an `--out-dir` destination (FR-036). The tool MUST establish that the output
  path is not the operand before any truncation of it could occur.
- **SR-013**: Input data MUST NOT be written anywhere other than standard output and, when
  `--out-dir` is supplied, the destination files inside DIR. The tool MUST NOT create temporary
  files, caches, or log files containing input data, and MUST NOT stage output through a temporary
  path. This amends SR-007 by adding exactly one permitted destination.
- **SR-014**: Neither summary line may disclose personal data. The `--count` tally MUST consist
  only of the four integer totals in the FR-022 format, and the `wrote N files` line MUST consist
  only of its fixed literals and the decimal count. Neither may include sample values, line
  numbers, file names, or any other content derived from the input. This amends SR-004.
- **SR-015**: Recognition of a phone number MUST run in time linear in the length of the line, with
  no input able to trigger catastrophic backtracking, and MUST NOT increase peak memory beyond the
  existing one-line bound. The 8-15 digit bounds are a fixed upper bound on the match length. This
  extends SR-005, whose 1 MiB line cap and FR-018 handling are unchanged.
- **SR-016**: The argument allowlist of SR-001 becomes exactly: `--count`, `--out-dir` with one
  value, the `--` end-of-options separator, and FILE operands. Any other option, any abbreviation
  of an allowed option, and `--out-dir` without a value MUST be rejected with a diagnostic on
  standard error and a non-zero exit status, with nothing written to standard output and no
  directory created. This amends SR-001 by adding one option and nothing else.
- **SR-017**: Diagnostics about the output folder MUST NOT disclose personal data. A message may
  name DIR or an output path as derived from the caller's own arguments, but MUST NOT include any
  input line, any matched value, or any fragment of one, and no Python traceback may reach standard
  error on a handled error path. This applies SR-003 to the new failure paths.

### Key Entities

- **Redaction kind**: now one of email, IPv4 address, **phone number**, or card number; each has a
  recognition rule, a fixed placeholder (`[EMAIL]`, `[IP]`, `[PHONE]`, `[CARD]`), and a precedence
  rank (FR-021).
- **Run tally**: now four non-negative integers, one per redaction kind, accumulated over the whole
  run and reported only when `--count` is given and the run exits 0.
- **Output destination**: either standard output (the default, unchanged) or, when `--out-dir` is
  supplied, one file per FILE operand inside DIR, named by that operand's final path component.
- **Output folder**: the directory named by `--out-dir`; created with missing parents if absent,
  reused as it is if present, and the only place outside standard output that redacted data is
  written.
- **Write tally**: one non-negative integer, the number of operand outputs written in full,
  reported as `wrote N files` only when every operand has been processed.
- **Input source** and **Line** and **Match**: unchanged from 001.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-011**: All three worked examples in the feature description reproduce byte-for-byte on
  standard output, standard error, and in the output folder, with the stated exit statuses — 3 of 3.
- **SC-012**: Every behaviour of the existing tool other than the two changes this specification
  makes is unchanged: the whole existing automated test suite passes, with changes confined to the
  expected text of the `--count` line — 100% of existing tests passing.
- **SC-013**: Across a corpus of genuine international-format phone numbers covering 8 to 15 digits
  and positions at the start, middle and end of a line, 100% are replaced by `[PHONE]` and no digit
  of any of them appears anywhere in the output.
- **SC-014**: Across a corpus of near-miss phone candidates (`+` with 7 digits, `+` with 16 and 20
  digits, a bare digit run with no `+`, `+` followed by a space or a letter, `+` followed by
  separator-grouped digits), 0 are replaced by `[PHONE]` and 0 have any digit removed by the phone
  rule.
- **SC-015**: For every `--out-dir` run over K readable operands with distinct final path
  components, exactly K files appear in DIR, each named by its operand's final path component and
  each byte-for-byte equal to the redaction of that operand, and standard output is exactly
  `wrote K files` followed by a newline — 100% of trials.
- **SC-016**: 100% of FR and SR items in this specification map to at least one automated test, with
  no unmapped requirement at the implementation gate.
- **SC-017**: No FILE operand's content or size changes in any trial, including every `--out-dir`
  trial and every trial where the output path coincides with an input path — 100% of trials.
- **SC-018**: Peak memory for a `--out-dir` run stays within the same fixed bound as today —
  roughly the 1 MiB line cap — regardless of the number of operands and their total size, measured
  over a run of at least 50 operands whose total size is at least 100 times that bound.
- **SC-019**: Every trial naming an unreadable operand under `--out-dir` exits 2 with that operand
  named on standard error, while every readable operand's output file is present and complete —
  100% of trials.
- **SC-020**: Every output file and directory the tool creates is inaccessible to group and other
  at the moment it is created — 100% of trials.
- **SC-021**: In every trial, no email address, IP address, phone number, card number, or fragment
  of one appears on standard error or in the `wrote N files` line — 100% of trials, including error,
  `--count` and `--out-dir` runs.
- **SC-022**: A reviewer can confirm from the two summary lines alone how many values of each of the
  four kinds were removed and how many files were written, without opening any redacted output.

## Assumptions

Numbering continues from 001; A-1 to A-7 and A-10 to A-12 of 001 are unchanged.

- **A-13** (phone precedence): The phone rule is placed **before** the card rule in FR-021 because
  it is the more specific one — it requires a literal `+` — and because it consumes that `+`. If
  the card rule won an overlap, a 13-to-15-digit Luhn-valid number after a `+` would be emitted as
  `+[CARD]`, which still discloses that the value was a phone number and leaves a character of the
  original in place. The phone rule is placed **after** the IPv4 rule for symmetry with FR-014,
  although the two cannot overlap: a phone match contains only `+` and digits, and an IPv4 match
  requires three dots. The email rule stays first, so a `+`-prefixed local part is redacted as one
  `[EMAIL]`.
- **A-14** (phone boundaries): A phone candidate must not be followed by a digit (FR-020), mirroring
  FR-013, because replacing the first 15 digits of a longer run would leave the remaining digits in
  the output — a partial redaction that SR-006 forbids. No constraint is placed on what precedes the
  `+`: digits before a `+` are not part of the phone number, so matching `99+14155552671` as
  `99[PHONE]` discloses nothing of the number itself.
- **A-15** (tally field order): The tally field order is `emails ips cards phones` exactly as the
  requester wrote it — the new field is appended rather than inserted in precedence order — so that
  a caller parsing the first three fields of the old line is affected as little as possible.
- **A-16** (`--out-dir` needs operands): `--out-dir` with no FILE operand is a usage error
  (FR-031). Standard input has no name to derive an output file name from, inventing one would be
  surprising, and silently falling back to standard output would make the option look as though it
  had been honoured. Failing loudly is what constitution Principle II requires.
- **A-17** (when `wrote N files` is written): The line is written when every operand has been
  processed, even if some operand failed, with N counting only the outputs actually written — the
  requester defined N as "the number of output files written", which is only meaningful if it can
  differ from the operand count, and the non-zero exit status already tells the caller the run
  failed. It is **not** written when the run stopped before processing every operand: an
  over-length line (FR-033), a rejected argument, or a DIR that cannot be created. The `--count`
  tally keeps its existing, stricter rule — written only on a run that exits 0 — because a tally
  that undercounts redactions could be mistaken for proof that the data was clean, whereas
  `wrote N files` is a factual statement about files that do exist.
- **A-18** (colliding output names): When two operands share a final path component, the later write
  replaces the earlier one, which follows directly from FR-026, and N counts operand outputs
  written rather than distinct files remaining — so two operands always report 2. This keeps N
  testable and keeps the reported number aligned with the work the tool actually did. A collision is
  not treated as an error because the requester specified replacement, not refusal.
- **A-19** (output path equal to an input path): Refusing that operand (FR-036) is the only option
  consistent with FR-017, which this feature does not amend. Truncating the operand would destroy
  the input before it was read; writing it anyway is not possible without doing so.
- **A-20** (permissions): Created output files are owner-read/write only and created directories are
  owner-accessible only (SR-011), per the Security Baseline's requirement that permissions be
  narrowest at creation. Redacted output is intended for sharing, but it is derived from logs that
  may hold other sensitive content, and the caller can widen permissions deliberately afterwards.
  An existing output file's permissions are left as its owner set them, because narrowing them would
  be an unrequested change to a file the caller already manages.
- **A-21** (option syntax): Both `--out-dir DIR` and `--out-dir=DIR` are accepted, as is
  conventional for an option taking a value. No abbreviation is accepted, consistent with the
  existing rejection of `--cou` (SR-016).
- **A-22** (scope): A-8 of 001 is amended — phone numbers in international format are now in scope.
  Phone numbers written in any other form (national format, with separators, with parentheses, with
  an `00` international prefix instead of `+`) remain out of scope, as do names, MAC addresses, IPv6
  addresses, national identifiers, and URLs containing credentials.
- **A-23** (no configuration): A-9 of 001 is amended only to add `--out-dir`. Placeholders, patterns,
  the digit bounds, the tally format and the `wrote N files` format stay fixed: there is no
  configuration file, no environment variable, and no option other than `--count` and `--out-dir`.
- **A-24** (tally scope under `--out-dir`): The `--count` tally stays a single run-level total
  across all sources; it is not reported per output file, and no per-file summary is added.
- **A-25** (no atomic replacement): Output files are written in place rather than staged through a
  temporary file and renamed, because SR-013 forbids a temporary file holding input data. A run that
  stops early can therefore leave a short output file; the non-zero exit status and the absence of
  the `wrote N files` line are what tell the caller not to trust the folder.
