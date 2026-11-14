# Feature Specification: Redact Phone Numbers and Write Sanitized Copies to an Output Folder

**Feature Branch**: `002-redact-phones-out-dir`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "This repository already contains `logredact`, a command-line tool that removes personal data from log files. Read the existing code and any documentation in the repository before changing it. Change it as follows; everything else it does now must keep working exactly as it does. 1. **Phone numbers.** Phone numbers in international format, a `+` followed by 8 to 15 digits such as `+14155552671`, become `[PHONE]`. With `--count`, the summary on standard error becomes `emails=N ips=N cards=N phones=N`. 2. **Output folder.** A new option `--out-dir DIR` writes the redacted lines of each FILE to a file with the same name in DIR (the file's name only, without its directories) instead of to standard output. DIR is created, with any missing parent directories, if it does not exist, and an existing file of that name in DIR is replaced. When every FILE has been processed, the tool prints `wrote N files` to standard output, where N is the number of output files written. A FILE that cannot be read is handled as it is now: an error message naming the file on standard error, and exit status 2."

## Context

This feature **extends an existing, shipped tool**. The behaviour it starts from is specified in
[`../001-redact-log-pii/spec.md`](../001-redact-log-pii/spec.md) (requirements FR-001 through
FR-029) and its CLI contract in
[`../001-redact-log-pii/contracts/cli-contract.md`](../001-redact-log-pii/contracts/cli-contract.md).

Everything that tool does today MUST continue to work exactly as it does, with one deliberate,
user-requested amendment: the `--count` summary gains a fourth key. Requirement numbering below
**continues the existing series at FR-030**, so a reference to FR-001…FR-029 anywhere in this
document unambiguously means a requirement of the existing specification.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Phone numbers disappear from a shared log (Priority: P1)

An engineer sanitizes a log that records customer callbacks and SMS gateway traffic. Those lines
carry telephone numbers in international format. After running the tool the numbers are gone,
replaced by a fixed placeholder, while the rest of the line still reads exactly as it did.

**Why this priority**: A phone number is a direct personal identifier; a log that still contains
one is not safe to share, so this is the whole point of the change. It is useful on its own even
if nothing else in this feature ships.

**Independent Test**: Pipe a line containing `+14155552671` into the tool with no arguments and
confirm standard output contains `[PHONE]` in that position and is otherwise identical to the
input.

**Acceptance Scenarios**:

1. **Given** the line `call +14155552671 now` on standard input, **When** the tool is run with no
   arguments, **Then** standard output is exactly `call [PHONE] now` followed by a newline, and
   the exit status is 0.
2. **Given** the line `a@b.io +442071838750`, **When** the tool is run, **Then** standard output
   is exactly `[EMAIL] [PHONE]` — both identifiers are replaced, each with its own placeholder.
3. **Given** a line containing `+1234567` (seven digits), **When** the tool is run, **Then** the
   text appears unchanged, because eight digits is the minimum.
4. **Given** a line containing `+1234567890123456` (sixteen digits), **When** the tool is run,
   **Then** the whole text appears unchanged and no part of it is replaced, because fifteen
   digits is the maximum.
5. **Given** the line `+12345678@example.com`, **When** the tool is run, **Then** standard output
   is exactly `[EMAIL]` — an address whose local part begins with `+` is redacted whole, not left
   as `[PHONE]@example.com`.
6. **Given** a line containing several phone numbers and other identifiers, **When** the tool is
   run, **Then** every one of them is replaced, each with the placeholder for its own type.
7. **Given** a line where a `+` and 13-to-19 digits could also be read as a payment card,
   **When** the tool is run, **Then** the whole span including the `+` becomes `[PHONE]` and no
   `[CARD]` appears, because the phone candidate starts one character earlier.

---

### User Story 2 - See how many phone numbers were redacted (Priority: P2)

Before sharing the sanitized log, the engineer checks the `--count` summary and now sees a fourth
figure telling them how many telephone numbers were removed, alongside the three they already
relied on.

**Why this priority**: A reporting convenience layered on top of Story 1 — the redaction itself is
what makes the log safe — but it is how the engineer confirms the new rule actually fired.

**Independent Test**: Run the tool with `--count` over input with a known number of phone numbers
and confirm the single summary line on standard error reports exactly those numbers in the new
four-key form, while standard output is unaffected.

**Acceptance Scenarios**:

1. **Given** the line `a@b.io +442071838750`, **When** the tool is run with `--count`, **Then**
   standard output is `[EMAIL] [PHONE]` and standard error is exactly
   `emails=1 ips=0 cards=0 phones=1`.
2. **Given** input with nothing to redact, **When** the tool is run with `--count`, **Then**
   standard error is exactly `emails=0 ips=0 cards=0 phones=0`.
3. **Given** multiple files are named, **When** the tool is run with `--count`, **Then** one
   summary covering all of them together is printed once, after all redacted output.
4. **Given** any input, **When** the tool is run without `--count`, **Then** nothing is written to
   standard error and the exit status is 0.

---

### User Story 3 - Sanitize a folder of logs into a folder of clean copies (Priority: P3)

The engineer has several rotated log files and wants one sanitized copy per file, keeping the
original filenames, rather than a single concatenated stream they would have to split apart
again. They name an output folder and get back a folder of clean, same-named files, plus a short
confirmation of how many were written.

**Why this priority**: A genuinely new capability and the main reason the engineer would upgrade
for workflow reasons — but the redaction rules of Story 1 must be right first, and the existing
single-stream mode already covers the common case.

**Independent Test**: Run the tool with `--out-dir` and two files, and confirm the named folder
afterwards holds two files with the same names whose contents are the redacted contents of the
inputs, while standard output is just the confirmation line.

**Acceptance Scenarios**:

1. **Given** readable files `app.log` and `web.log` and a folder `clean` that does not exist,
   **When** the tool is run as `--out-dir clean app.log web.log`, **Then** `clean` is created,
   `clean/app.log` holds the redacted contents of `app.log`, `clean/web.log` holds the redacted
   contents of `web.log`, standard output is exactly `wrote 2 files` followed by a newline,
   nothing else is written to standard output, and the exit status is 0.
2. **Given** a FILE named with directories such as `var/logs/app.log`, **When** the tool is run
   with `--out-dir clean`, **Then** the output file is `clean/app.log` — the name only, with the
   input's directories dropped.
3. **Given** an output folder path several levels deep that does not exist, **When** the tool is
   run, **Then** the folder and every missing parent are created.
4. **Given** the output folder already contains a file with the output name, **When** the tool is
   run, **Then** that file's previous contents are gone and it holds only this run's redacted
   output — nothing is appended.
5. **Given** the output folder already exists and holds unrelated files, **When** the tool is
   run, **Then** those files are untouched.
6. **Given** `--count` is given as well, **When** the tool is run, **Then** `wrote N files` is on
   standard output and the single four-key summary covering all files is on standard error.
7. **Given** no `--out-dir` is given, **When** the tool is run, **Then** output goes to standard
   output exactly as it does today and no `wrote N files` line is ever printed.
8. **Given** a readable file that is empty, **When** the tool is run with `--out-dir`, **Then** an
   empty output file of that name is created and it counts towards N.

---

### User Story 4 - Fail clearly when a sanitized copy cannot be produced (Priority: P4)

Something goes wrong — a mistyped input filename, an output folder that cannot be created, a full
disk. The engineer is told which path failed and why, and gets a failure status, so a partial
folder of clean copies is never mistaken for a complete one.

**Why this priority**: Guards the worst failure mode of Story 3 (an apparently complete set of
sanitized files that is silently missing one), but only matters once Story 3 exists.

**Independent Test**: Run the tool with `--out-dir` naming one readable and one missing file, and
confirm standard error names the missing file, no `wrote N files` line is printed, and the exit
status is 2.

**Acceptance Scenarios**:

1. **Given** a named file that cannot be read, **When** the tool is run with `--out-dir`, **Then**
   standard error contains a message including that file's name as given on the command line, no
   `wrote N files` line and no summary are printed, and the exit status is 2.
2. **Given** a readable file followed by an unreadable one, **When** the tool is run with
   `--out-dir`, **Then** the first file's output file has been written and remains complete, the
   unreadable file is named on standard error, no later file is opened, and the exit status is 2.
3. **Given** an output folder that cannot be created (for example its parent is a regular file or
   is not writable), **When** the tool is run, **Then** standard error names that folder and what
   went wrong, no input is read, no stack trace is shown, and the exit status is 2.
4. **Given** an output file that cannot be opened or written (for example the name already exists
   as a directory, or the disk is full), **When** the tool is run, **Then** standard error names
   that path and what went wrong, processing stops, no `wrote N files` line and no summary are
   printed, and the exit status is 2.
5. **Given** `--out-dir` is given with no FILE argument at all, **When** the tool is run, **Then**
   standard error carries a usage message saying `--out-dir` requires at least one FILE, standard
   input is not read, the folder is not created, standard output is empty, and the exit status
   is 2.
6. **Given** every named file is readable and every output file is written, **When** the tool is
   run, **Then** nothing but `wrote N files` appears on standard output, and the exit status is 0.
7. **Given** an unrecognised flag, **When** the tool is run, **Then** behaviour is as it is today:
   a usage message naming that argument on standard error, empty standard output, exit status 2.

---

### Edge Cases

**Phone numbers**

- **Length boundaries**: exactly 8 digits and exactly 15 digits after the `+` are redacted; 7 and
  16 are not, and a too-long run is never partially redacted.
- **Trailing digit**: a `+` followed by more than 15 digits is not shortened to the first 15 — the
  candidate is rejected whole, so `+1234567890123456` keeps all of its digits.
- **Trailing punctuation**: `+14155552671.` at the end of a sentence is redacted and the full stop
  is preserved; `(+14155552671)` keeps its brackets.
- **Separators are not accepted**: `+1 415 555 2671` and `+1-415-555-2671` are not international
  format for this rule. The digit runs inside them are judged by the existing IPv4 and card rules
  on their own merits, which in this example leaves them unchanged.
- **No plus sign**: `14155552671` without a leading `+` is not a phone number; it falls through to
  the existing card rule, which rejects it as too short.
- **Bare plus**: a `+` with no digits after it, or followed by letters, is left alone.
- **Plus inside an address**: `jane+orders@example.com` is still `[EMAIL]`; the `+` is not followed
  by eight digits, so no phone candidate exists at all.
- **Address with a numeric local part**: `+12345678@example.com` is `[EMAIL]`, not
  `[PHONE]@example.com` — email wins the tie at the same starting position.
- **Phone overlapping a card**: a `+` followed by 13-to-19 Luhn-valid digits becomes `[PHONE]`,
  counted once as a phone and never also as a card, because matches never overlap.
- **Phone next to an IPv4 address**: `+14155552671 10.0.0.7` yields `[PHONE] [IP]`.
- **Adjacent matches**: `+14155552671+442071838750` is two phone candidates; the first ends at the
  `+` that starts the second, so both are replaced.
- **Placeholder already present**: input that already contains the literal text `[PHONE]` passes
  through unchanged and is not counted.

**Output folder**

- **Repeated input name**: two FILE arguments whose names (ignoring directories) are the same
  write to the same output file; the later one replaces the earlier one's contents, and each still
  counts towards N (see Assumptions).
- **Same file named twice**: naming one file twice writes it twice to the same output file, which
  ends up holding one redacted copy, and N counts it twice.
- **Output folder that already exists**: used as it is; it is not emptied, and files in it that
  this run does not write are untouched.
- **Output folder is the input's own folder**: pointing `--out-dir` at a directory that holds one
  of the FILE arguments replaces that input file; this destroys the original (see Assumptions).
- **Empty input file**: produces an empty output file, which counts towards N.
- **`--out-dir` without `--count`**: `wrote N files` goes to standard output and standard error
  stays empty.
- **Flag ordering**: `--out-dir`, `--count`, and FILE arguments may be interleaved in any order.
- **Output consumer closes early**: the only thing written to standard output under `--out-dir` is
  the final confirmation line, so the early-close path is unchanged and still ends quietly with
  exit status 0.

**Carried over unchanged**

- Every edge case of the existing specification — empty input, missing final newline, carriage
  returns, octet range boundaries, over-long dotted runs, digit-run boundaries, separator
  strictness, Luhn-failing runs, very long lines, undecodable bytes, locale independence —
  continues to hold, now also for text written to an output file.

## Requirements *(mandatory)*

Requirement numbering continues the existing specification's series. FR-001 through FR-029 live in
[`../001-redact-log-pii/spec.md`](../001-redact-log-pii/spec.md).

### Functional Requirements

**Phone numbers**

- **FR-030**: The tool MUST replace each international-format phone number with the literal text
  `[PHONE]`.
- **FR-031**: An international-format phone number is a literal `+` immediately followed by 8 to
  15 digits with no separators of any kind. The `+` and all of its digits are part of the match
  and MUST be replaced together, so `+14155552671` becomes `[PHONE]` with no leading `+` left
  behind.
- **FR-032**: A candidate MUST NOT be recognised when its digit run is immediately followed by
  another digit. A `+` followed by 16 or more digits is therefore not a phone number and MUST be
  left entirely unchanged, never truncated to its first 15 digits and never partially redacted.
- **FR-033**: A `+` followed by fewer than 8 digits, or by something that is not a digit, MUST be
  left entirely unchanged.
- **FR-034**: Punctuation or any non-digit character immediately following the digits MUST NOT be
  consumed by the match.
- **FR-035**: Phone matches MUST obey the existing single left-to-right pass of FR-018: a phone
  candidate starts at its `+`, which is earlier than any IPv4 or payment-card candidate lying
  inside its digits, so the phone match wins and the digits it replaced MUST NOT be re-examined or
  counted as any other type.
- **FR-036**: The same-start-position precedence of FR-019 becomes: email address, then IPv4
  address, then payment card number, then phone number. A string such as `+12345678@example.com`,
  where an email match and a phone match both begin at the `+`, MUST be replaced by `[EMAIL]` and
  counted as an email.

**Counting**

- **FR-037**: With `--count`, the summary line written to standard error MUST be exactly
  `emails=N ips=N cards=N phones=N` — four keys, always all four, always in this order, single-
  space separated, one line. This replaces the three-key form of FR-021; every other property of
  FR-021 (single summary per run, written once after all redacted output has been written) is
  unchanged.
- **FR-038**: The `phones` count MUST equal the number of phone-number replacements actually made,
  totalled across every input read in this run, and MUST be reported as `0` when none was made.
- **FR-039**: The summary MUST continue to be suppressed on the read-failure path (FR-026), on the
  early-close path (FR-028), on the invalid-usage path (FR-029), and on the new failure paths
  FR-049 and FR-050 below.

**Output folder**

- **FR-040**: The tool MUST accept a new option `--out-dir DIR` taking exactly one value, which
  may appear anywhere relative to the `--count` flag and the FILE arguments, extending FR-001 to
  `python -m logredact [--count] [--out-dir DIR] [FILE ...]`.
- **FR-041**: With `--out-dir DIR` and one or more FILE arguments, the redacted lines of each FILE
  MUST be written to a file inside DIR named by the final path component of that FILE as given on
  the command line — its name only, without any of its directories — and MUST NOT be written to
  standard output.
- **FR-042**: DIR MUST be created if it does not exist, together with any missing parent
  directories. An existing DIR MUST be used as it is: it MUST NOT be emptied, and files in it that
  this run does not write MUST be left untouched.
- **FR-043**: When DIR already contains a file with the output name, that file MUST be replaced:
  after the run it holds only this run's redacted output, with none of its previous contents
  retained or appended to.
- **FR-044**: Each output file MUST carry exactly the text contract standard output carries today:
  UTF-8 (FR-005a), undecodable input bytes round-tripped as the same bytes (FR-005b), every input
  line emitted exactly once in input order with nothing added, dropped, reordered, or duplicated
  (FR-004), and all non-matching text — including line terminators and a missing final newline —
  byte-for-byte as it was read (FR-005).
- **FR-045**: DIR MUST be created before the first FILE is opened, so a DIR that cannot be created
  is reported before any input is read.
- **FR-046**: When every FILE has been processed successfully, the tool MUST write exactly one
  line `wrote N files` to standard output and exit with status 0, where N is the number of output
  files written — one per FILE argument processed.
- **FR-047**: `wrote N files` MUST be the only thing the tool writes to standard output on an
  `--out-dir` run, MUST NOT be written on any run without `--out-dir`, and MUST NOT be written on
  a run that failed (FR-048, FR-049, FR-050).
- **FR-048**: When a named FILE cannot be opened or read during an `--out-dir` run, behaviour MUST
  be exactly as FR-025, FR-026, and FR-027 already require: a diagnostic on standard error
  including that file's name as given on the command line and what went wrong, no stack trace, no
  later FILE opened, no `wrote N files` line, no `--count` summary, and exit status 2. Output files
  already completed for earlier FILE arguments MUST remain valid and complete.
- **FR-049**: When DIR cannot be created, the tool MUST write a diagnostic to standard error
  naming DIR and stating what went wrong, MUST NOT read any input, MUST NOT write any redacted
  output, MUST NOT emit an unhandled error trace, and MUST exit with status 2.
- **FR-050**: When an output file cannot be opened, written, or closed, the tool MUST write a
  diagnostic to standard error naming that output path and stating what went wrong, MUST stop
  processing further FILE arguments, MUST NOT emit an unhandled error trace, MUST NOT print
  `wrote N files` or the `--count` summary, and MUST exit with status 2.
- **FR-051**: `--out-dir` given with no FILE argument MUST be treated as invalid usage under
  FR-029: a usage diagnostic on standard error stating that `--out-dir` requires at least one FILE,
  standard input not read, DIR not created, standard output empty, no summary, and exit status 2.
  The option MUST NOT be silently ignored.
- **FR-052**: With both `--count` and `--out-dir`, the counts MUST cover all FILE arguments
  together as they do today, `wrote N files` MUST go to standard output, and the summary MUST go
  to standard error after the confirmation line has been written.

**Unchanged behaviour**

- **FR-053**: Every requirement FR-001 through FR-029 of the existing specification MUST remain in
  force, with the single exception of FR-021's three-key summary form, which FR-037 replaces. In
  particular: the `[EMAIL]`, `[IP]`, and `[CARD]` placeholder strings and their recognition rules
  are unchanged; the exit-status set stays exactly `{0, 2}`; a run with no `--out-dir` writes
  redacted output to standard output and nothing else; diagnostics go to standard error; a
  successful run without `--count` writes nothing to standard error; and the early-close and
  invalid-usage paths behave as before.
- **FR-054**: Adding the phone rule MUST NOT change the output of any input that contains no
  international-format phone number: such inputs MUST produce byte-identical output to the
  existing tool's.

### Key Entities

- **Redaction type**: now one of email address, IPv4 address, payment card number, or phone number
  — each with its own recognition rule, its own fixed placeholder (`[EMAIL]`, `[IP]`, `[CARD]`,
  `[PHONE]`), and its own counter name (`emails`, `ips`, `cards`, `phones`).
- **Redaction counts**: four running totals, one per redaction type, accumulated across all input
  sources in a run and reported only when `--count` is given.
- **Output destination**: either standard output (the default, one combined stream) or an output
  folder (one file per FILE argument). Exactly one destination is in effect for a run.
- **Output file**: one file inside the output folder, named by the final path component of a FILE
  argument, holding that FILE's redacted lines and nothing else.
- **Write confirmation**: a single line reporting how many output files the run wrote, printed
  only on a fully successful output-folder run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-008**: On a sample log containing known international-format phone numbers of varying
  lengths from 8 to 15 digits, 100% of them are absent from the output and replaced by `[PHONE]`.
- **SC-009**: On a control sample of phone near-misses — a `+` with 7 digits, a `+` with 16 or
  more digits, a `+` followed by letters, a bare `+`, and digit runs with no `+` — the output is
  byte-identical to the input: zero false positives and zero partial redactions.
- **SC-010**: The four reported counts match the number of placeholders of each type present in
  the output, exactly, for every test input.
- **SC-011**: Running with `--out-dir` over K readable files leaves the output folder holding one
  file per input name whose content is byte-identical to that input's redacted stream, and
  standard output holds exactly the one line `wrote K files`.
- **SC-012**: An output folder path whose parents do not exist is created in full; a pre-existing
  file of the output name is replaced, never appended to, verified by its byte length and content
  after the run.
- **SC-013**: Every failure path of this feature — unreadable input, uncreatable folder,
  unwritable output file, `--out-dir` with no FILE — produces a standard-error message naming the
  offending path or option, no `wrote N files` line, no summary, no stack trace, and exit status 2.
- **SC-014**: Across every scenario in this specification and the existing one, the tool exits
  with status 0 or 2 and no other value.
- **SC-015**: The existing automated test suite continues to pass unchanged except for assertions
  on the `--count` summary text, which are updated to the four-key form; for any input containing
  no international-format phone number, output is byte-identical to the pre-change tool's.
- **SC-016**: Every requirement FR-030 through FR-054 and every edge case listed above is covered
  by at least one automated test, and the full suite passes.
- **SC-017**: Performance is unchanged in character: a one-million-line log is processed in under
  60 seconds on a typical developer machine, and memory use does not grow with input size, in both
  standard-output and output-folder modes.

## Assumptions

**Explicit constraints carried from the request** (stated by the user, not chosen here): the two
changes above, and that everything else the tool does keeps working exactly as it does. The
existing constraints continue to apply: Python 3.11 or newer, standard library only, the package
`logredact` under `src/`, run as `python -m logredact` (Constitution principle I).

Defaults chosen where the request did not specify:

- **The `--count` summary change is a deliberate contract amendment**: the existing CLI contract
  lists the summary format and its key names as stable, not to be changed without a spec
  amendment. The user has asked for exactly that, so FR-037 is that amendment, and the existing
  contract document and the tests asserting the three-key form are updated as part of this
  feature rather than treated as regressions.
- **`--out-dir` with no FILE is a usage error** (FR-051): the request defines `--out-dir` purely in
  terms of "each FILE", and standard input has no filename to derive an output name from. Falling
  back to standard output would silently ignore an option the user explicitly gave, which
  Constitution principle II forbids; inventing a name would be hidden behaviour. Failing with a
  usage diagnostic and exit status 2 reuses the existing invalid-usage path (FR-029) rather than
  adding a third exit status.
- **N counts FILE arguments processed, not distinct output paths** (FR-046): the request says "the
  number of output files written". When two FILE arguments share a name, two writes happen but one
  file remains. Counting writes — one per FILE — is the simpler, more predictable rule
  (Constitution principle IV) and matches the overwhelmingly common case where N is also the
  number of files on disk. The collision case is noted as an edge case so the choice is visible.
- **Colliding output names replace, they do not merge** (FR-043 applied per write): a later FILE
  with the same name replaces the earlier one's output rather than appending to it, because
  FR-043's "replaced" rule is applied consistently at every write. Merging would silently produce a
  file whose name matched neither input's content.
- **Failure is fail-fast, as it already is** (FR-048, FR-050): the first unreadable input or
  unwritable output stops the run, leaving earlier output files complete and suppressing both the
  confirmation line and the summary. This extends the existing FR-026 choice so a partial folder of
  clean copies is never presented as a complete one.
- **The output folder is created before any input is opened** (FR-045): this makes the diagnostic
  deterministic when both the folder and the first input are bad, and avoids reading input that
  could never be written anywhere.
- **Pointing `--out-dir` at a folder containing an input FILE is destructive and is not
  prevented**: FR-043 says an existing file of that name in DIR is replaced, and an input file
  sitting in DIR is exactly such a file. The tool does no same-path detection — that would mean
  resolving symlinks, hard links, and case-insensitive filesystems, complexity no requirement asks
  for (Constitution principle IV). The resulting contents of such a file are therefore not part of
  the tested contract; the behaviour is documented as a caveat rather than specified.
- **Phone format is strictly digits after the `+`** (FR-031): the request gives `+14155552671` as
  the example and says "a `+` followed by 8 to 15 digits". Spaces, hyphens, parentheses, and
  leading `00` forms are therefore not recognised. This matches E.164, keeps the rule testable,
  and avoids a looser pattern that would start consuming ordinary log text.
- **Phone rejects rather than truncates an over-long run** (FR-032): matching the first 15 digits
  of a 20-digit run would leave a fragment of the original number in the output and would
  contradict the existing "never partially redact a candidate" treatment of cards (FR-016) and
  IPv4 addresses (FR-011).
- **Email beats phone at the same position** (FR-036): `+12345678@example.com` could have been read
  as a phone followed by a domain, leaving `[PHONE]@example.com`. Email is placed first because the
  existing precedence already puts it first and because redacting the whole address is the safe
  direction — the same reasoning FR-007a already records for `user@1.2.3.4`.
- **Phone is placed last in the tie-break order** (FR-036): appending it leaves the existing
  email → IPv4 → card ordering untouched, which is the smallest change that keeps output
  deterministic. In practice only email can begin at the same position as a phone candidate, since
  IPv4 and card candidates both begin with a digit.
- **Output files use the same encoding contract as standard output** (FR-044): the request does not
  mention encoding for the new destination. Reusing the existing contract — fixed UTF-8,
  undecodable bytes carried through unchanged, no line-ending translation — is the only choice
  that preserves the round-trip guarantee the
  tool already makes, and keeps `--out-dir` output byte-identical to what standard output would
  have produced for the same FILE.
- **Output files are written streaming, one at a time**, so the existing memory and throughput
  properties (SC-007) hold unchanged; the tool does not buffer a whole file before writing it.
- **`wrote N files` is plain and unconditional in wording**: it is printed as the literal form
  given in the request, including `wrote 1 files` for a single file. Pluralising would change the
  exact output string the request specifies.
- **Out of scope**: recursive directory input, preserving an input's directory structure under
  DIR, renaming or suffixing output files, in-place editing, configurable placeholders, and any
  further identifier types. Phone formats other than the `+`-and-digits form above are also out of
  scope.
- **Testing**: `pytest` remains the test framework, with tests under `tests/` runnable by a bare
  `pytest` from the repository root, per the project constitution.
