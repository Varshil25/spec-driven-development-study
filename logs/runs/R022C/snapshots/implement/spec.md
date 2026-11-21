# Feature Specification: Phone Redaction and Output Folder

**Feature Branch**: `002-phone-redact-out-dir`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "This repository already contains `logredact`, a command-line tool that removes personal data from log files. Read the existing code and any documentation in the repository before changing it. Change it as follows; everything else it does now must keep working exactly as it does. (1) Phone numbers. Phone numbers in international format, a `+` followed by 8 to 15 digits such as `+14155552671`, become `[PHONE]`. With `--count`, the summary on standard error becomes `emails=N ips=N cards=N phones=N`. (2) Output folder. A new option `--out-dir DIR` writes the redacted lines of each FILE to a file with the same name in DIR (the file's name only, without its directories) instead of to standard output. DIR is created, with any missing parent directories, if it does not exist, and an existing file of that name in DIR is replaced. When every FILE has been processed, the tool prints `wrote N files` to standard output, where N is the number of output files written. A FILE that cannot be read is handled as it is now: an error message naming the file on standard error, and exit status 2."

## Context: what already exists

This is a change to a shipped tool, not a new one. The existing behaviour is specified in
[specs/001-logredact-cli/spec.md](../001-logredact-cli/spec.md) (FR-001…FR-025 there) and its
[CLI contract](../001-logredact-cli/contracts/cli.md): `python -m logredact [--count] [FILE ...]`
redacts emails to `[EMAIL]`, IPv4 addresses to `[IP]`, and Luhn-valid 13-19 digit card numbers to
`[CARD]`, streaming every input line to standard output; `--count` prints
`emails=N ips=N cards=N` to standard error; an unreadable FILE is named on standard error with
exit status 2.

Requirement identifiers in **this** document (FR-001…) are local to this feature. Where a
requirement of the earlier specification is referred to, it is written as, for example,
`001/FR-019`. This feature adds a fourth redaction rule and a new output destination; **every
other behaviour of the tool must remain exactly as it is** (FR-027).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Redact international phone numbers (Priority: P1)

A support engineer pastes a chunk of application log into a ticket. The log contains customer
callback numbers written in international format. They pipe the text through the tool and those
numbers come back as a fixed placeholder, alongside the email addresses, IP addresses, and card
numbers the tool already removes, so the whole excerpt is safe to share.

**Why this priority**: Phone numbers are personal data that the tool currently leaks; closing
that gap is the core value of this change and is independent of where the output is written.

**Independent Test**: Pipe a line containing an international-format number on standard input
with no file arguments, and confirm standard output has `[PHONE]` in place of the number with
every other character on the line unchanged.

**Acceptance Scenarios**:

1. **Given** the single line `call +14155552671 now`, **When** the tool is run with no arguments
   and that line on standard input, **Then** standard output is `call [PHONE] now` followed by a
   newline, and the exit status is 0.
2. **Given** the line `+442071838750 and +14155552671`, **When** the tool is run, **Then**
   standard output is `[PHONE] and [PHONE]` — every occurrence on a line is redacted.
3. **Given** the line `ext +1234567` (a `+` followed by seven digits), **When** the tool is run,
   **Then** the line is reproduced exactly — fewer than eight digits is not a phone number.
4. **Given** the line `ref +1234567890123456` (a `+` followed by sixteen digits), **When** the
   tool is run, **Then** the sixteen-digit run is not redacted as a phone number — more than
   fifteen digits is not a phone number.
5. **Given** the line `total 100+25 units`, **When** the tool is run, **Then** the line is
   reproduced exactly — a `+` not followed by at least eight digits is ordinary text.
6. **Given** a line containing an email address, an IPv4 address, a Luhn-valid card number, and
   a phone number, **When** the tool is run, **Then** all four are replaced by their respective
   placeholders on the same line.

---

### User Story 2 - Write redacted copies into an output folder (Priority: P2)

A release engineer has a directory of rotated log files to attach to an incident report. Instead
of redirecting one concatenated stream, they name an output folder; the tool writes one sanitised
copy per input file, keeping the original file names, and reports how many files it wrote. They
can hand over the whole folder.

**Why this priority**: It changes the tool from "one stream out" to "a sanitised copy of each
file", which is what a bulk sanitisation pass needs. It depends on the existing redaction engine
but not on phone redaction, so it can ship separately.

**Independent Test**: Create two small files with known sensitive content in different
directories, run the tool with both paths and `--out-dir` naming a folder that does not exist,
and confirm the folder is created, contains one redacted file per input named after the input's
own file name, that standard output is exactly the `wrote N files` line, and the exit status is 0.

**Acceptance Scenarios**:

1. **Given** readable files `app.log` (containing `user jane@example.com`) and `web.log`
   (containing `GET / from 10.0.0.7`), **When** the tool is run as
   `python -m logredact --out-dir clean app.log web.log`, **Then** standard output is
   `wrote 2 files` followed by a newline, `clean/app.log` contains `user [EMAIL]`,
   `clean/web.log` contains `GET / from [IP]`, and the exit status is 0.
2. **Given** the same files and a folder path `clean` that does not exist, **When** the tool is
   run, **Then** `clean` is created before the output files are written.
3. **Given** an output folder path with missing intermediate directories such as
   `out/2026/clean`, **When** the tool is run, **Then** every missing parent directory is created.
4. **Given** an input path with directory components such as `logs/2026/app.log`, **When** the
   tool is run with `--out-dir clean`, **Then** the output file is `clean/app.log` — only the
   input's own file name is used, and the input's directories are not reproduced inside the
   folder.
5. **Given** an output folder that already contains a file named `app.log` with other content,
   **When** the tool is run with `app.log` as input, **Then** that file's previous content is
   entirely replaced by the redacted content, with no leftover trailing bytes.
6. **Given** no `--out-dir` option, **When** the tool is run with file arguments, **Then**
   redacted lines go to standard output exactly as they do today and no `wrote N files` line is
   printed.
7. **Given** a readable but empty input file, **When** the tool is run with `--out-dir`, **Then**
   an empty output file of the same name is created and it is included in the `wrote N files`
   count.

---

### User Story 3 - See phone numbers in the tally (Priority: P3)

A privacy reviewer checks that a sanitisation pass found what it was supposed to find. The tally
on standard error now has a fourth figure, so phone redactions are auditable the same way the
other three are.

**Why this priority**: Auditing is valuable but the protective behaviour is complete without it;
it is a one-field extension of an existing output line.

**Independent Test**: Run the tool with `--count` on input with a known number of phone numbers,
capture standard error separately, and confirm the tally line carries the four figures in the
specified order with the correct phone count.

**Acceptance Scenarios**:

1. **Given** the line `a@b.io +442071838750`, **When** the tool is run with `--count`, **Then**
   standard output is `[EMAIL] [PHONE]` and standard error is `emails=1 ips=0 cards=0 phones=1`.
2. **Given** input with no redactable values, **When** the tool is run with `--count`, **Then**
   standard error is `emails=0 ips=0 cards=0 phones=0`.
3. **Given** input where the same phone number appears three times, **When** the tool is run with
   `--count`, **Then** the tally reports `phones=3` — occurrences are counted, not distinct
   values.
4. **Given** multiple file arguments, `--count`, and `--out-dir`, **When** the tool is run,
   **Then** standard output is the `wrote N files` line, and standard error carries one tally
   covering all files combined, printed after that line.
5. **Given** any input, **When** the tool is run without `--count`, **Then** standard error is
   empty.

---

### User Story 4 - Learn immediately when an output folder cannot be used (Priority: P3)

Someone scripting a bulk pass names a folder they cannot create, or forgets the folder's value
after the option. The tool says what was wrong and exits non-zero rather than quietly writing
nothing, or writing redacted data somewhere unexpected.

**Why this priority**: A privacy tool that looks successful while producing nothing is the most
damaging outcome, but this applies only to the new option introduced in Story 2.

**Independent Test**: Run the tool with `--out-dir` naming a path that cannot be created (for
example a path whose parent is an existing regular file) and confirm standard error names that
path, no `wrote N files` line is printed, and the exit status is 2.

**Acceptance Scenarios**:

1. **Given** an output folder path that cannot be created, such as one whose parent component is
   an existing regular file, **When** the tool is run, **Then** standard error contains a message
   naming that path and stating what went wrong, standard output has no `wrote N files` line, and
   the exit status is 2.
2. **Given** `--out-dir` as the final command-line token with no value after it, **When** the tool
   is run, **Then** standard error contains a usage message, nothing is read, nothing is written
   to standard output, and the exit status is 2.
3. **Given** `--out-dir` with no FILE arguments, **When** the tool is run, **Then** standard error
   contains a message stating that `--out-dir` requires at least one FILE, nothing is read from
   standard input, standard output is empty, and the exit status is 2.
4. **Given** two file arguments and `--out-dir`, where the first is readable and the second does
   not exist, **When** the tool is run, **Then** the first input's output file has been written,
   standard error names the second path, no `wrote N files` line is printed, and the exit status
   is 2.
5. **Given** `--out-dir` and an unreadable FILE together with `--count`, **When** the tool is run,
   **Then** neither the `wrote N files` line nor a tally line is printed, and the exit status
   is 2.
6. **Given** an output file inside the folder that cannot be written (for example because a
   directory already exists at that name), **When** the tool is run, **Then** standard error
   names that output path, no `wrote N files` line is printed, and the exit status is 2.

---

### Edge Cases

**Phone recognition**

- **Phone-shaped run inside a longer digit run**: a `+` followed by sixteen or more digits is not
  a phone number; no prefix of the run is redacted as one, so no partial `[PHONE]` followed by
  leftover digits is ever produced.
- **Phone digits that also form a card**: `+4417123456789012` is a `+` followed by sixteen digits,
  so it is not a phone number; if those sixteen digits are Luhn-valid they are redacted by the
  existing card rule, giving `+[CARD]`.
- **Separators inside a number**: `+1 415 555 2671` and `+1-415-555-2671` are not phone numbers —
  the digits must directly follow the `+` with nothing between them. The leading `+1` has only one
  digit, so nothing is redacted as a phone; the remaining text is subject to the existing rules
  only.
- **Doubled sign**: in `++14155552671` the match begins at the second `+`, giving `+[PHONE]`.
- **Sign preceded by a digit**: `100+14155552671` is redacted to `100[PHONE]` — what precedes the
  `+` places no constraint on the match.
- **Phone-shaped email local part**: `+12345678@b.io` is redacted once, to `[EMAIL]`, because the
  email rule takes precedence at the same starting position; the domain is not left exposed.
- **Phone after an email**: in `jane@example.com+14155552671` the email ends at `.com` and the
  phone follows, giving `[EMAIL][PHONE]`.
- **Dotted form**: `+1.2.3.4` is not a phone number; the existing IPv4 rule applies to `1.2.3.4`,
  giving `+[IP]`.
- **Value split across lines**: a number broken by a line ending is not recognised; each line is
  redacted on its own.
- **Literal placeholder in input**: text `[PHONE]` already present in the input passes through
  unchanged and is not counted.
- **Exact bounds**: a `+` followed by exactly eight digits and a `+` followed by exactly fifteen
  digits are both redacted.

**Output folder**

- **Duplicate file names from different directories**: `a/app.log` and `b/app.log` both map to
  `DIR/app.log`; they are processed in argument order, so the second replaces the first and the
  surviving file holds the second input's redacted content. The count reports one output file per
  input processed (`wrote 2 files`) — see Assumptions.
- **Same path given twice**: the input is read twice and its output file is written twice, and the
  count reports one per input processed.
- **Folder already exists**: it is used as it is; existing unrelated files in it are left alone.
- **Folder path that is an existing regular file**: it cannot be created as a directory, so the
  run fails by naming it with exit status 2.
- **Folder that is also an input's own directory**: the output file replaces the input file of
  that name while it is being read. This is a destructive invocation the tool does not guard
  against — see Assumptions.
- **Option-shaped folder value**: in `--out-dir --count`, the token after `--out-dir` is taken as
  the folder value; it is not interpreted as an option.
- **Option repeated**: with `--out-dir a --out-dir b`, the last value wins.
- **Very long lines and large files**: output files are written as the input streams, so a 1 MB
  line works and memory does not grow with file size, exactly as for standard output today.
- **Line fidelity**: a final line with no trailing newline is written to the output file with no
  newline added; blank lines, whitespace, and CRLF terminators round-trip exactly.
- **Closed standard output**: the `wrote N files` line is the only thing on standard output, so a
  closed standard output cannot truncate redacted data; the tool still terminates without an
  unhandled crash report.

## Requirements *(mandatory)*

### Functional Requirements

**Phone number redaction**

- **FR-001**: The tool MUST replace each phone number occurrence with the literal `[PHONE]`.
- **FR-002**: A phone number MUST be recognised as a `+` character immediately followed by 8 to 15
  decimal digits, with no other character between the `+` and the digits or between the digits.
  `+14155552671` and `+442071838750` MUST be recognised.
- **FR-003**: The replaced text MUST include the leading `+` as well as its digits, so no `+`
  remains beside the placeholder.
- **FR-004**: A phone number candidate MUST NOT be matched when it is immediately followed by a
  further decimal digit; so a `+` followed by 16 or more digits is left unredacted by this rule
  rather than partially replaced.
- **FR-005**: A `+` followed by fewer than 8 digits MUST be left unchanged, and the characters
  preceding the `+` MUST place no constraint on the match.
- **FR-006**: Each character MUST still be redacted at most once, with the leftmost match winning;
  where candidates start at the same position the precedence MUST be email, then IPv4 address,
  then phone number, then payment card number. Placeholders MUST NOT be re-examined for redaction
  (extends `001/FR-017` and `001/FR-018`).
- **FR-007**: Phone redaction MUST apply to every input source and both output destinations —
  standard input, named FILE arguments, standard output, and the output folder of FR-013.

**Counting**

- **FR-008**: With `--count`, the single summary line written to standard error MUST have the form
  `emails=N ips=N cards=N phones=N`, with the four figures in that order, replacing the previous
  three-figure form (supersedes `001/FR-019`).
- **FR-009**: The `phones` figure MUST be the total number of phone number replacements across all
  inputs of the run, counting repeated values once per occurrence, and MUST be `0` when none
  occurred. The `emails`, `ips`, and `cards` figures MUST keep their existing meanings.
- **FR-010**: The summary line MUST still be written after all standard output has been written,
  and MUST still be the only thing written to standard error on a successful run; without
  `--count`, standard error MUST remain empty on a successful run (`001/FR-021`).

**Output folder**

- **FR-011**: The tool MUST accept a new option `--out-dir`, whose value is the immediately
  following command-line token, taken literally as the output folder path whatever its shape. The
  option MUST be accepted in any position relative to FILE arguments and to `--count`.
- **FR-012**: When `--out-dir` is given with no following token, the tool MUST write a usage
  message to standard error, read no input, write nothing to standard output, and exit with
  status 2.
- **FR-013**: With `--out-dir DIR` and one or more FILE arguments, the tool MUST write the redacted
  lines of each FILE to a file inside DIR, and MUST NOT write redacted lines to standard output.
- **FR-014**: The name of each output file MUST be the final path component of its FILE argument —
  the file's own name without any directory components — so `logs/2026/app.log` is written to
  `DIR/app.log`.
- **FR-015**: The content of each output file MUST be byte-identical to what the same FILE's
  redacted lines would have been written to standard output, preserving line order, line
  terminators, the absence of a trailing newline, and encoding (`001/FR-004`…`001/FR-006`).
- **FR-016**: The tool MUST create DIR, together with any missing parent directories, when it does
  not already exist, and MUST use an already-existing DIR as it is without disturbing unrelated
  files in it.
- **FR-017**: When an output file of that name already exists in DIR, the tool MUST replace its
  content entirely, leaving no bytes of the previous content.
- **FR-018**: After every FILE has been processed successfully, the tool MUST write exactly one
  line `wrote N files` to standard output, where N is the number of output files written — one per
  FILE argument processed — and MUST then exit with status 0.
- **FR-019**: With `--out-dir` and `--count` together, the tool MUST write the `wrote N files` line
  to standard output and the summary line of FR-008 to standard error, the summary after all
  standard output.
- **FR-020**: When `--out-dir` is given with no FILE argument, the tool MUST write a message to
  standard error stating that `--out-dir` requires at least one FILE, MUST NOT read standard
  input, MUST write nothing to standard output, and MUST exit with status 2.
- **FR-021**: When `--out-dir` is given more than once, the last value MUST be used.
- **FR-022**: Without `--out-dir`, every aspect of output MUST remain as it is today: redacted
  lines to standard output, no `wrote N files` line, and no file created anywhere.

**Errors and exit status**

- **FR-023**: With `--out-dir`, a FILE that cannot be read MUST be handled as it is today: a
  message naming that file path and stating what went wrong on standard error, no further FILE
  processed, and exit status 2 (`001/FR-022`, `001/FR-023`).
- **FR-024**: When DIR cannot be created or used as a directory, the tool MUST write a message to
  standard error naming that path and stating what went wrong, MUST NOT write a `wrote N files`
  line, and MUST exit with status 2.
- **FR-025**: When an output file cannot be created or written, the tool MUST write a message to
  standard error naming that output path and stating what went wrong, MUST NOT write a
  `wrote N files` line, and MUST exit with status 2.
- **FR-026**: On any run that exits with status 2, the tool MUST NOT write the `wrote N files`
  line and MUST NOT write the summary line of FR-008, so each of those lines always describes a
  complete run.

**Preservation of existing behaviour**

- **FR-027**: Every behaviour specified in `specs/001-logredact-cli/spec.md` that this document
  does not explicitly change MUST continue to hold unchanged — the invocation form, email, IPv4
  and card recognition and placeholders, input selection and ordering, line fidelity, unrecognised
  option handling, and all exit statuses. The only changes are the fourth redaction rule
  (FR-001…FR-007), the fourth figure in the summary line (FR-008, FR-009), and the output folder
  option (FR-011…FR-026).

### Key Entities

- **Redaction rule**: unchanged in kind, extended by a fourth member — a named category of
  sensitive value (email, IPv4 address, payment card, **phone number**) paired with its
  recognition criteria and its fixed placeholder.
- **Redaction tally**: now four running totals, one per rule, over all inputs of a single run.
- **Output destination**: either standard output (today's behaviour) or, with `--out-dir`, one
  output file per FILE argument, named by that argument's final path component and located in the
  output folder.
- **Output folder**: a directory path given on the command line, created on demand, holding the
  output files of a run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All three worked examples in the feature description reproduce byte-for-byte —
  including which stream each byte goes to, the files created, their contents, and the exit
  status — when run as written.
- **SC-002**: Across a review corpus of log lines containing known international-format phone
  numbers, zero of those numbers survive in the output: the leak rate for phone numbers is 0%, and
  the pre-existing 0% leak rate for emails, IPv4 addresses, and card numbers is unchanged
  (`001/SC-002`).
- **SC-003**: Across a review corpus of lines containing `+` characters that are not phone numbers
  — arithmetic expressions, `+` followed by fewer than 8 or more than 15 digits, numbers written
  with spaces or hyphens after the `+`, and signed version strings — 100% of lines are reproduced
  byte-identically, and the pre-existing 0% false-positive corpus (`001/SC-003`) still passes
  unchanged.
- **SC-004**: 100% of this document's functional requirements FR-001 through FR-027 are covered by
  at least one automated test that names the requirement it verifies, and the full suite passes.
- **SC-005**: The entire test suite written for the earlier specification passes unchanged, except
  for the tests of the summary line's form, which are updated for FR-008 — demonstrating FR-027
  rather than asserting it.
- **SC-006**: Every specified failure mode new to this feature (missing `--out-dir` value,
  `--out-dir` with no FILE, uncreatable folder, unwritable output file, unreadable FILE with
  `--out-dir`) is verified by a test asserting both the diagnostic naming the offending input and
  the exit status.
- **SC-007**: A 100,000-line log file is sanitised in under 10 seconds, to standard output and to
  an output folder alike, and memory use does not grow with file size (a 1 GB file completes
  without exhausting memory) — the pre-existing performance envelope (`001/SC-006`) is preserved
  with the fourth rule in place.
- **SC-008**: A reviewer can confirm the tool's complete behaviour from its own output and the
  files it writes alone — no configuration file, environment variable, or network access is
  required to reproduce any acceptance scenario.

## Assumptions

Decisions taken where the change description left room for interpretation. Each is a default
chosen to keep behaviour predictable and testable; any of them can be revisited in
`/speckit-clarify`.

- **Carried-over constraints**: the Assumptions of `specs/001-logredact-cli/spec.md` continue to
  apply unless listed below — Python 3.11+, standard library only, the `logredact` package under
  `src/`, UTF-8 text, line-oriented streaming, fixed non-configurable placeholders, `-` as a
  literal path, fail-fast on the first unreadable FILE, and no tally on the failure path.
- **`[PHONE]` is a fixed literal** (FR-001), like the three existing placeholders; nothing asks
  for it to be configurable (Constitution principle IV).
- **Digits only, directly after the `+`** (FR-002): the description gives exactly one shape, `+`
  then 8-15 digits. Numbers written with internal spaces, hyphens, parentheses, or dots are **not**
  recognised, and neither are national formats without a `+`. This keeps the false-positive
  surface small; broader phone formats are out of scope.
- **Trailing-digit boundary** (FR-004): a longer digit run is left alone rather than having its
  first 15 digits replaced, by analogy with the existing card rule (`001/FR-016`), because a
  partial replacement such as `[PHONE]67` would both corrupt the line and leak part of the value.
  No equivalent boundary is imposed before the `+`, since the `+` is itself a non-digit delimiter.
- **Precedence placement** (FR-006): phone sits after IPv4 and before card. Only the email case is
  observable — `+12345678@b.io` matches both rules at the same position — and email winning
  redacts the whole address rather than leaving `[PHONE]@b.io`, which would leak the domain.
- **Summary line replaces rather than extends conditionally** (FR-008): the four-figure form is
  always used with `--count`; there is no option to get the old three-figure form. This is a
  deliberate, breaking change to that one line, as the description requires.
- **`--out-dir` requires its value as a separate token** (FR-011): the form `--out-dir DIR` is
  supported, matching the description. `--out-dir=DIR` is not a recognised token and therefore
  falls through to the existing unrecognised-option error (`001/FR-024`), exit status 2.
- **`--out-dir` with no FILE is an error** (FR-020): standard input has no file name to derive an
  output name from, so there is no sensible output file. Silently writing to standard output
  instead would make the option look as if it had worked. Constitution principle II (Fail Loudly)
  favours a named error and exit status 2.
- **N counts one output file per FILE processed** (FR-018): with two FILE arguments the line is
  `wrote 2 files`, including when both arguments share a final path component and therefore the
  same output file, and including when the same path is given twice. The alternative — counting
  distinct output paths — adds bookkeeping for an invocation that is already ambiguous, and the
  simpler rule matches the example in the description. The plural noun is used for every N,
  including `wrote 1 files`, because the description specifies a fixed line shape.
- **Output folder is created up front** (FR-016, FR-024): DIR is created before the first FILE is
  read, so an unusable folder fails before any work is done and before any output file exists. A
  run that then fails on an unreadable FILE leaves the folder in place, possibly empty or
  partially filled; already-written output files are not retracted, consistent with the existing
  rule that already-written standard output is not retracted.
- **No atomic or temporary-file writes** (FR-017): each output file is opened and truncated in
  place and written as the input streams. A run that fails part-way may leave a partially written
  output file; the non-zero exit status is the signal that the output is incomplete.
- **Self-overwrite is not guarded**: naming an input file's own directory as DIR (for example
  `--out-dir . app.log`) makes the output file the input file. The description states that an
  existing file of that name in DIR is replaced, and that is what happens; because output is
  written while the input is being read, the result is not well defined and the input is
  destroyed. This revises the earlier assumption that the tool never modifies an input file: with
  `--out-dir` it can, if the user points the folder at its own input. Flagged here as a known
  hazard rather than specified as a refusal, since no requirement asks the tool to reject it.
- **Output files are written with the same encoding and newline handling as standard output**
  (FR-015): UTF-8, no newline translation, so terminators round-trip exactly.
- **Nothing else is written to standard output with `--out-dir`** (FR-013, FR-018): no per-file
  progress lines, only the single `wrote N files` line at the end.
- **Out of scope for this feature**: phone numbers without a `+`, phone numbers with internal
  separators or extensions, IPv6 addresses, national identity numbers, names, URLs, API keys,
  structured-log awareness, pseudonymisation, allowlisting, configurable placeholders,
  `--out-dir` with standard input, preserving input directory structure inside the output folder,
  in-place editing of input files, and any output-file naming scheme other than the input's own
  file name.
