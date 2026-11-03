# Feature Specification: Shared Expense Settle-Up

**Feature Branch**: `001-expense-splitter`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Build a command-line tool that reads a CSV file of shared group expenses and prints who owes whom in order to settle up. The CSV has a header row with columns payer, amount, description. The participant list is supplied separately as a comma-separated argument. Every participant owes an equal share of the group total. The tool computes each person's net balance and prints a minimal list of payments that settles every balance to zero. All money is handled in whole cents and rounding must never lose or invent money: the payments printed must sum exactly to the total imbalance. Malformed input (missing file, unknown payer not in the participant list, non-numeric or negative amount, empty participant list) must produce a clear error on stderr and a non-zero exit code. Python 3, standard library only. Run it as `python -m splitter EXPENSES.csv --participants NAMES`, with the package `splitter` under `src/`. Each payment is printed on its own line as `PAYER pays PAYEE AMOUNT`, with the amount to two decimal places."

## Clarifications

### Session 2026-11-03

- Q: Must the expenses file header match `payer,amount,description` exactly in that order and spelling, or be matched by name in any order with extra columns tolerated? → A: Strict — exactly those three names, in that order, lower-case, no extra columns
- Q: What does "ascending order of name" mean for the leftover-cent and payment tie-breaks? → A: Ascending Unicode code-point order, no locale collation
- Q: Which character encoding is the expenses file read as, and what happens if its bytes cannot be decoded? → A: UTF-8; undecodable bytes are an error; a leading byte-order mark is ignored
- Q: When several rows are malformed, does the tool report every problem or stop at the first? → A: Stop at the first problem in file order
- Q: Is an empty element in the participant list (for example `Alice,,Bob`, or a trailing comma) an error or silently skipped? → A: An error

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Settle up after a shared trip (Priority: P1)

A group of people has shared costs on a trip. One person kept a record of who paid for what in a
spreadsheet exported as a CSV file. They want to know, in as few payments as possible, who should
pay whom so that everyone has borne an equal share of the total cost. They run the tool with the
file and the list of everyone who took part, and read off the payments to make.

**Why this priority**: This is the whole purpose of the feature. Without it nothing of value is
delivered; with it alone the group can settle up, so it is a complete MVP on its own.

**Independent Test**: Fully testable by preparing a CSV of expenses and a participant list, running
the tool, and checking the printed payments both settle every balance to zero and are the expected
set of payments. Requires nothing from the other stories.

**Acceptance Scenarios**:

1. **Given** an expenses file containing a header row and the single row `Alice,30.00,Hotel`,
   **When** the tool is run with participants `Alice,Bob`,
   **Then** standard output is exactly the one line `Bob pays Alice 15.00` and the exit status is zero.
2. **Given** an expenses file where Alice paid 60.00 and Bob paid 30.00,
   **When** the tool is run with participants `Alice,Bob,Carol`,
   **Then** the printed payments leave every participant's net balance at zero and total exactly
   30.00 (Carol's share), and the number of payment lines is at most two.
3. **Given** an expenses file in which every participant has already paid exactly an equal share,
   **When** the tool is run,
   **Then** nothing is printed to standard output and the exit status is zero.
4. **Given** any valid expenses file,
   **When** a participant appears in the participant list but in no expense row,
   **Then** that participant is still charged an equal share and appears as a payer in the output
   when they owe money.
5. **Given** two expenses files that differ only in the text of their description column,
   **When** the tool is run on each with the same participants,
   **Then** both runs print the same payments.
6. **Given** an expenses file containing a row whose amount is `0.00`,
   **When** the tool is run,
   **Then** the result is the same as if that row were absent.
7. **Given** two expenses files with identical content where one begins with a UTF-8 byte-order mark
   and the other does not,
   **When** the tool is run on each with the same participants,
   **Then** both runs succeed and print the same payments.

---

### User Story 2 - Be told clearly when the input is wrong (Priority: P2)

Someone runs the tool against a file that does not exist, a typo'd name, or a malformed amount.
Rather than a silently wrong answer or an unreadable crash, they want a short message that names
exactly what is wrong so they can fix the file or the command, and a failure status that a script
calling the tool can detect.

**Why this priority**: A settle-up answer that is quietly wrong is worse than no answer, because
money moves on the strength of it. This story protects the correctness of Story 1, but Story 1 is
still demonstrable without it.

**Independent Test**: Fully testable by running the tool once per malformed-input case and checking
that a specific message naming the problem appears on standard error, that standard output is
empty, and that the exit status is non-zero.

**Acceptance Scenarios**:

1. **Given** a path that does not name an existing readable file, **When** the tool is run,
   **Then** standard error names the path as unreadable, standard output is empty, and the exit
   status is non-zero.
2. **Given** an expenses file with a payer name that is not in the participant list, **When** the
   tool is run, **Then** standard error names that payer and the row it appeared on, standard output
   is empty, and the exit status is non-zero.
3. **Given** an expense row whose amount is not a plain non-negative decimal number (for example
   `abc`, `1,200.00`, `$5`, `1e3`, `-5.00`, or `1.005`), **When** the tool is run, **Then** standard
   error names the offending value and row, standard output is empty, and the exit status is
   non-zero.
4. **Given** an empty participant list, **When** the tool is run, **Then** standard error states that
   at least one participant is required, standard output is empty, and the exit status is non-zero.
5. **Given** a participant list containing an empty element (for example `Alice,,Bob` or
   `Alice,Bob,`), **When** the tool is run, **Then** standard error states that an empty participant
   name is not allowed, standard output is empty, and the exit status is non-zero.
6. **Given** an expenses file whose bytes are not valid UTF-8, **When** the tool is run, **Then**
   standard error names the path and reports that it could not be decoded, standard output is empty,
   and the exit status is non-zero.
7. **Given** an expenses file whose header is `Payer,Amount,Description`, or
   `amount,payer,description`, or `payer,amount,description,date`, **When** the tool is run,
   **Then** standard error reports the header as incorrect, standard output is empty, and the exit
   status is non-zero.
8. **Given** an expenses file containing two malformed rows, **When** the tool is run, **Then**
   standard error reports only the earlier of the two rows, standard output is empty, and the exit
   status is non-zero.

---

### User Story 3 - Trust the cent-level arithmetic on an awkward split (Priority: P3)

A group's total does not divide evenly by the number of people — for example 10.00 split three ways.
The user wants assurance that the payments printed account for every single cent: no cent is
dropped, and no cent is created, however the shares fall out.

**Why this priority**: It is a correctness guarantee on top of the working tool rather than a
separate capability, but it is the guarantee that makes the output safe to act on without a manual
re-check.

**Independent Test**: Fully testable by running the tool on inputs whose totals are deliberately not
divisible by the participant count and checking that the printed amounts sum to exactly the total
owed and that applying them zeroes every balance to the cent.

**Acceptance Scenarios**:

1. **Given** an expenses file whose total is 10.00 and participants `Alice,Bob,Carol` where Alice
   paid everything, **When** the tool is run, **Then** the printed amounts sum to exactly 6.67 and
   applying them leaves all three balances at exactly zero.
2. **Given** any valid input, **When** the tool is run, **Then** the sum of the printed payment
   amounts equals the sum of the positive net balances exactly, with no rounding difference.
3. **Given** the same input run twice, **When** the outputs are compared, **Then** they are
   identical line for line.

---

### Edge Cases

- **Expenses file with a header row but no data rows**: group total is zero, every balance is zero,
  nothing is printed, exit status is zero.
- **Total not divisible by the number of participants**: the leftover cents are assigned
  deterministically (see FR-011) so that the shares sum to exactly the total.
- **A single participant**: that person's share is the whole total, their balance is zero, and no
  payments are printed.
- **Amount of exactly zero** (for example a comped meal recorded for completeness): accepted,
  contributes nothing to the total.
- **The same person paying in several rows**: their payments are summed.
- **A participant who paid nothing**: still owes a full share.
- **A duplicate name in the participant list**: rejected, because it is ambiguous whether the group
  has one such member or two (FR-008).
- **Names with surrounding whitespace** in the participant list or the payer column: the surrounding
  whitespace is ignored, so ` Alice ` and `Alice` are the same person.
- **Names differing only in letter case**: `alice` and `Alice` are different people (FR-006), and in
  name order `Alice` comes before `alice` because ordering is by Unicode code point (FR-011a).
- **An empty name in the participant list** (`Alice,,Bob`, or a trailing comma): rejected, because
  silently skipping it would change the group size and therefore every share (FR-007).
- **A data row with the wrong number of fields, or a missing/incorrect header row**: rejected with a
  message naming the row (FR-010). A header that is reordered, capitalised differently, or carries a
  fourth column is incorrect and is rejected (FR-002).
- **Several problems in one input**: only the first in file order is reported, and the tool stops
  there rather than listing the rest or printing a partial settlement (FR-010a).
- **A leading byte-order mark** on the expenses file, as produced by some spreadsheet exports:
  ignored, so the header still matches (FR-002a).
- **An expenses file whose bytes are not valid UTF-8**: rejected with a message naming the path,
  rather than decoded with replacement characters (FR-002a).
- **Non-ASCII names** such as `José`: handled like any other name — matched exactly after trimming,
  and ordered by Unicode code point (FR-006, FR-011a).
- **Blank lines in the expenses file**: ignored rather than treated as malformed rows.
- **A payment amount that would round to 0.00**: never printed; only payments of at least one cent
  appear (FR-013).

## Requirements *(mandatory)*

### Functional Requirements

**Invocation and input**

- **FR-001**: The tool MUST accept exactly one positional argument giving the path of the expenses
  file, and one required option `--participants` whose value is a comma-separated list of
  participant names.
- **FR-002**: The tool MUST read the expenses file as comma-separated text whose first non-blank
  line is a header consisting of exactly the three fields `payer`, `amount`, and `description`, in
  that order and in lower case, with no further columns, and MUST treat each subsequent non-blank
  line as one expense. A header that reorders, re-cases, renames, omits, or adds a column MUST be
  rejected under FR-010.
- **FR-002a**: The tool MUST decode the expenses file as UTF-8, ignoring a byte-order mark at the
  start of the file if one is present. A file whose bytes are not valid UTF-8 MUST be rejected with
  an error that names the path; the tool MUST NOT substitute replacement characters or guess another
  encoding.
- **FR-003**: The tool MUST interpret each amount as an exact money value in whole cents. An amount
  is valid only if it consists of digits with an optional single decimal point followed by at most
  two digits (for example `30`, `30.5`, `30.00`), optionally preceded by a `+` sign.
- **FR-004**: The tool MUST reject, with an error, any amount that is not valid per FR-003 —
  including non-numeric text, a negative value, a value with more than two decimal places, a value
  carrying a currency symbol or thousands separator, an exponent form, and the special values
  infinity and not-a-number.
- **FR-005**: The tool MUST accept an amount of exactly zero and treat it as contributing nothing to
  the group total.
- **FR-006**: The tool MUST reject, with an error, any expense whose payer — after surrounding
  whitespace is removed — is not exactly one of the supplied participants, compared
  case-sensitively.
- **FR-007**: The tool MUST reject, with an error, a participant list that yields no names (empty
  value, or only separators and whitespace), and MUST likewise reject a list containing any element
  that is empty or whitespace-only after surrounding whitespace is removed — for example `Alice,,Bob`
  or a trailing comma. An empty element MUST NOT be silently skipped, because the number of
  participants determines every share.
- **FR-008**: The tool MUST reject, with an error, a participant list containing the same name more
  than once after surrounding whitespace is removed.
- **FR-009**: The tool MUST reject, with an error that names the path, an expenses file that does not
  exist or cannot be read.
- **FR-010**: The tool MUST reject, with an error, an expenses file whose header is not exactly the
  three required columns as specified in FR-002, and any data row that does not have exactly three
  fields; the message MUST identify the offending row by its line number in the file.
- **FR-010a**: Where an input contains more than one problem, the tool MUST report only the first one
  encountered in file order — command line first, then the header, then data rows by increasing line
  number — and MUST stop at that point without attempting to list further problems or to compute a
  partial settlement.
- **FR-011**: Each participant's share MUST be the group total in cents divided by the number of
  participants; where the division leaves a remainder of *r* cents, exactly *r* participants MUST be
  charged one extra cent, chosen in ascending name order as defined in FR-011a, so that the shares
  sum to exactly the group total.
- **FR-011a**: Wherever this specification orders participants by name, the order MUST be ascending
  Unicode code-point order of the trimmed name — the ordering of the names' characters by their
  Unicode code-point values. No locale-specific collation, case-folding, or accent-folding may be
  applied, so `Alice` precedes `Bob` and `Bob` precedes `alice`. This ordering MUST be identical on
  every machine and under every locale setting.
- **FR-012**: Each participant's net balance MUST be the total cents they paid minus their share from
  FR-011; the net balances MUST sum to exactly zero.

**Output**

- **FR-013**: The tool MUST print a set of payments that, when applied, brings every participant's
  net balance to exactly zero, using at most (number of participants − 1) payments, where every
  printed payment is for at least one cent.
- **FR-014**: The sum of the printed payment amounts MUST equal exactly the sum of the positive net
  balances — the total imbalance — so that no money is lost or invented.
- **FR-015**: The set and order of payments MUST be fully determined by the input: the participant
  with the largest remaining debt is paired with the participant owed the largest remaining amount
  (ties broken in ascending name order as defined in FR-011a) and transfers the lesser of the two
  outstanding amounts; this repeats until no debt remains. Identical input MUST always produce
  identical output.
- **FR-016**: Each payment MUST be printed on its own line to standard output in the form
  `PAYER pays PAYEE AMOUNT`, where the amount is shown with exactly two decimal places and no
  currency symbol or thousands separator.
- **FR-017**: When every net balance is already zero — including the case of an expenses file with no
  data rows — the tool MUST print nothing to standard output and exit with status zero.
- **FR-018**: The contents of the description column MUST NOT affect any computed balance or payment.

**Failure behaviour**

- **FR-019**: Every rejection in FR-002a, FR-004, FR-006, FR-007, FR-008, FR-009, and FR-010 MUST
  write a single message to standard error that names the specific problem and, where the problem
  lies in the file, the row and value at fault; nothing MUST be written to standard output in that
  case. Per FR-010a that message describes the first problem found, not a list of all of them.
- **FR-020**: Exit status MUST be zero on success and non-zero on any rejection: status 1 for the
  input and validation failures of FR-019, and status 2 when the command line itself is malformed
  (missing file argument, missing `--participants`, unrecognised option).
- **FR-021**: The tool MUST NOT create, modify, or delete any file; the expenses file MUST be read
  only.

### Key Entities

- **Participant**: a named member of the group, supplied on the command line. Identified by their
  exact name after surrounding whitespace is removed. Every participant owes a share whether or not
  they paid anything.
- **Expense**: one recorded payment, read from a row of the expenses file. Has a payer (who must be a
  participant), an amount in whole cents that is zero or more, and a description that carries no
  computational meaning.
- **Share**: the portion of the group total charged to one participant — an equal split, with
  leftover cents allocated deterministically so the shares sum to the total exactly.
- **Net balance**: for one participant, what they paid minus their share. Positive means the group
  owes them; negative means they owe the group. Across all participants these sum to zero.
- **Payment**: a single transfer of a whole-cent amount from one participant who owes to one who is
  owed. The printed payments are the settlement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the stated reference case (a file holding one expense of 30.00 paid by Alice, with
  participants Alice and Bob), the output is exactly `Bob pays Alice 15.00` and the run succeeds.
- **SC-002**: Across every valid input exercised — including totals that are not divisible by the
  number of participants, totals of zero, and groups of one — the printed payments sum to exactly the
  total imbalance and applying them leaves every balance at exactly zero cents, in 100% of cases.
  No case loses or invents a single cent.
- **SC-003**: For every valid input exercised, the number of payment lines printed is at most one
  fewer than the number of participants, and no line shows an amount below 0.01.
- **SC-004**: Each malformed-input case named in this specification — missing file, unreadable
  encoding, unknown payer, non-numeric amount, negative amount, over-precise amount, empty
  participant list, empty participant name, duplicate participant, bad header, bad row length —
  produces a non-empty message on standard error that names the problem, no output on standard
  output, and a non-zero exit status: 11 of 11 cases. Where an input holds several problems, exactly
  one message is written and it concerns the earliest problem.
- **SC-005**: Running the tool twice on the same input produces byte-identical output, in 100% of
  repeated runs, including when the two runs are made under different locale settings.
- **SC-006**: A user can read their settlement for a file of 1,000 expenses across 50 participants in
  under two seconds on an ordinary laptop.
- **SC-007**: A user who mistypes a name or a number learns which row and which value is at fault
  from the error message alone, without opening the tool's source or re-running it with extra flags.
- **SC-008**: The expenses file is byte-identical before and after every run, successful or failed,
  and no run creates or deletes any other file.

## Assumptions

These were chosen as reasonable defaults where the feature description did not specify the detail.
Each is a decision a reviewer may overturn.

- **"Minimal list of payments" means at most one fewer payment than there are participants**,
  produced by repeatedly settling the largest debt against the largest credit (FR-015). Computing a
  provably smallest possible number of transfers for every input is a hard combinatorial problem and
  is out of scope; the chosen rule is the standard approach for settle-up tools, always terminates,
  and never exceeds participants − 1 payments.
- **Leftover cents are charged to participants in ascending name order** (FR-011), where that order
  is by Unicode code point rather than locale collation (FR-011a). The description requires only
  that no money be lost or invented; some deterministic tie-break is needed, and code-point name
  order makes the result reproducible and explainable on any machine.
- **Amounts with more than two decimal places are rejected rather than rounded** (FR-004). Silently
  rounding `1.005` would quietly change the group total, which the "never lose or invent money"
  requirement rules out, and a loud rejection lets the user correct the source data.
- **Names are compared case-sensitively, with surrounding whitespace ignored.** Trimming handles the
  ordinary spreadsheet artefact of a stray space; case-folding would silently merge two people who
  genuinely spell their names differently, so it is not applied.
- **Duplicate participant names, and empty ones, are an error** rather than deduplicated or skipped
  (FR-007, FR-008), because the group size — and therefore every share — would otherwise depend on
  an unstated guess.
- **Blank lines in the expenses file are skipped**; a trailing newline at end of file is normal and
  not an error.
- **The expenses file is plain comma-separated UTF-8 text** (FR-002a), with standard quoting
  available for descriptions containing commas. Alternative delimiters, other encodings,
  spreadsheets in binary formats, and multiple currencies are out of scope; an undecodable file is
  reported rather than guessed at.
- **The header is matched strictly** (FR-002) rather than leniently. A lenient match would be a
  second way to express one thing and more paths to test, against no stated requirement; a strict
  rule gives one unambiguous rejection to verify, and the message tells the user exactly what the
  header must say.
- **Only the first problem in an input is reported** (FR-010a). Collecting and ranking every problem
  is more machinery than the specification asks for, and a user fixing a file one error at a time is
  the ordinary workflow; the stop-at-first rule also keeps the error output deterministic.
- **All amounts are in one unspecified currency** and are printed as bare numbers with two decimal
  places; no currency symbol, locale-specific separator, or conversion is involved.
- **Output goes to standard output and diagnostics to standard error**, so the payment list can be
  piped into another command while errors stay visible.
- **The tool is run on demand by one user at a time**; there is no persistence, no configuration
  file, and no network access.

## Given Constraints

Supplied by the requester and carried into planning rather than inferred:

- Implemented in Python 3 using only the standard library.
- Invoked as `python -m splitter EXPENSES.csv --participants NAMES`.
- The `splitter` package lives under `src/`.
