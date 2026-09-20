# Feature Specification: Expense Splitter

**Feature Branch**: `001-expense-splitter`

**Created**: 2026-09-17

**Status**: Draft

**Input**: User description: "Build a command-line tool that reads a CSV file of shared group expenses and prints who owes whom in order to settle up. The CSV has a header row with columns payer, amount, description. The participant list is supplied separately as a comma-separated argument. Every participant owes an equal share of the group total. The tool computes each person's net balance and prints a minimal list of payments that settles every balance to zero. All money is handled in whole cents and rounding must never lose or invent money: the payments printed must sum exactly to the total imbalance. Malformed input (missing file, unknown payer not in the participant list, non-numeric or negative amount, empty participant list) must produce a clear error on stderr and a non-zero exit code. Python 3, standard library only."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Settle up a shared trip (Priority: P1)

A group of people shared costs during a trip. One person has a CSV of who paid for what, plus the list of everyone who was there. They want a short, unambiguous list of transfers so that after those transfers happen, everyone has paid an equal share of the total.

**Why this priority**: This is the entire reason the tool exists — turning a ledger of payments into a settlement plan. Without it there is no product.

**Independent Test**: Provide a valid CSV of expenses and a participant list; confirm the tool prints a list of "A pays B <amount>" transfers whose totals bring every participant to an equal share.

**Acceptance Scenarios**:

1. **Given** a CSV where Alice paid 30.00 and Bob paid 0, with participants "Alice,Bob", **When** the tool runs, **Then** it prints exactly one payment: Bob pays Alice 15.00.
2. **Given** a CSV where everyone already paid an equal share, **When** the tool runs, **Then** it prints no payments (and reports that the group is already settled) and exits successfully.
3. **Given** a CSV with multiple expenses across three or more participants, **When** the tool runs, **Then** the printed payments sum exactly to the total amount owed by net debtors, and applying them zeroes every net balance.

---

### User Story 2 - Reject malformed input clearly (Priority: P1)

A user runs the tool against a file that is missing, contains a bad amount, references a payer who is not in the participant list, or supplies no participants. They need an immediate, understandable error rather than a wrong settlement.

**Why this priority**: For a money tool, a silently wrong answer is worse than a visible failure. Correct rejection of bad input is a first-class requirement, not an afterthought.

**Independent Test**: Feed each malformed-input variant to the tool and confirm it writes a clear message to stderr, prints nothing to stdout, and exits with a non-zero status.

**Acceptance Scenarios**:

1. **Given** a CSV file path that does not exist, **When** the tool runs, **Then** it writes a clear "file not found" style message to stderr and exits non-zero.
2. **Given** a CSV row whose payer is not in the participant list, **When** the tool runs, **Then** it names the offending payer on stderr and exits non-zero.
3. **Given** a CSV row whose amount is non-numeric or negative, **When** the tool runs, **Then** it identifies the bad amount on stderr and exits non-zero.
4. **Given** an empty participant list, **When** the tool runs, **Then** it writes a clear message on stderr and exits non-zero.

---

### User Story 3 - Trust that no money is lost or invented (Priority: P2)

A user splits a total that does not divide evenly among participants (e.g., 10.00 across 3 people). They need the reported transfers to still sum to exactly the group's imbalance, with leftover cents distributed rather than dropped or duplicated.

**Why this priority**: Correct settlement is P1; exact conservation under uneven division is the specific guarantee that makes the results trustworthy in the awkward-but-common case.

**Independent Test**: Run a case whose equal share is not a whole number of cents and verify the sum of printed payments equals the total amount owed by debtors to the cent, and that per-person shares differ by at most one cent.

**Acceptance Scenarios**:

1. **Given** a total of 10.00 split across three participants, **When** the tool runs, **Then** the shares assigned sum to exactly 10.00 (e.g., 3.34 / 3.33 / 3.33) with no cent lost or added.
2. **Given** any valid input, **When** the tool runs, **Then** the sum of all printed payment amounts equals the sum of the positive net balances (total imbalance) exactly.

---

### Edge Cases

- **Empty expense file (header only, no rows)**: total is zero, every balance is zero; the tool reports the group is already settled and exits successfully.
- **Participant who never paid**: still owes their equal share and appears as a debtor.
- **Payer listed multiple times / multiple expenses per payer**: contributions accumulate; only net balances matter.
- **Duplicate names in the participant list**: treated as an invalid participant list (ambiguous identity) and rejected on stderr with a non-zero exit.
- **Amount with more precision than whole cents** (e.g., three decimal places): rejected as an amount that cannot be represented exactly in whole cents.
- **Amount of exactly zero**: accepted (a recorded expense of nothing contributes nothing).
- **Missing or misnamed CSV header, or missing required columns**: rejected on stderr with a non-zero exit.
- **Blank payer or blank amount in a row**: rejected on stderr with a non-zero exit.
- **Rounding remainder** (imbalance does not divide evenly): leftover cents are distributed deterministically so the printed payments still sum exactly to the total imbalance.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tool MUST accept a path to a CSV file of expenses and a separately supplied, comma-separated list of participants.
- **FR-002**: The tool MUST read the CSV as having a header row with columns `payer`, `amount`, and `description`, and MUST treat each subsequent row as one expense.
- **FR-003**: The tool MUST compute the group total as the sum of all expense amounts.
- **FR-004**: The tool MUST assign every participant an equal share of the group total, distributing any indivisible remainder cents deterministically so that the assigned shares sum exactly to the group total.
- **FR-005**: The tool MUST compute each participant's net balance as the amount they paid minus their assigned share.
- **FR-006**: The tool MUST produce a list of payments (from net debtors to net creditors) that, when applied, brings every participant's net balance to zero.
- **FR-007**: The list of payments MUST be minimal in the number of transactions for the computed balances.
- **FR-008**: The sum of all printed payment amounts MUST equal the total imbalance (the sum of positive net balances) exactly, to the cent, in every case.
- **FR-009**: All monetary computation MUST be performed in whole cents with no loss or invention of money at any step.
- **FR-010**: On success, the tool MUST write the settlement result to standard output and exit with a zero status; when the group is already settled it MUST indicate that no payments are needed and still exit zero.
- **FR-011**: The tool MUST write a clear, human-readable error message to standard error and exit with a non-zero status when the CSV file is missing or unreadable.
- **FR-012**: The tool MUST reject and report, on standard error with a non-zero exit, any expense whose payer is not present in the participant list, naming the offending payer.
- **FR-013**: The tool MUST reject and report, on standard error with a non-zero exit, any amount that is non-numeric, negative, or cannot be represented exactly in whole cents.
- **FR-014**: The tool MUST reject and report, on standard error with a non-zero exit, an empty participant list.
- **FR-015**: The tool MUST reject and report, on standard error with a non-zero exit, a CSV that lacks the required header columns or contains a row missing a required field.
- **FR-016**: When any input is rejected, the tool MUST NOT print a partial or best-guess settlement to standard output.
- **FR-017**: Given identical input and invocation, the tool MUST produce byte-identical output (deterministic ordering of participants and payments).
- **FR-018**: Monetary amounts in output MUST be formatted as a human-readable currency value (whole-cent precision) at the output boundary only.

### Key Entities *(include if feature involves data)*

- **Participant**: A named member of the group. Identified by a unique name drawn from the supplied participant list. Has an amount paid (possibly zero) and an assigned equal share.
- **Expense**: A single recorded payment. Attributes: payer (must be a participant), amount (non-negative, whole-cent-representable), description (free text, not used in computation).
- **Net Balance**: Per participant, amount paid minus assigned share. Positive means the group owes them (creditor); negative means they owe the group (debtor). All net balances sum to zero.
- **Payment**: A proposed transfer in the settlement plan. Attributes: from (a net debtor), to (a net creditor), amount (positive whole-cent value).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every valid input, the sum of printed payment amounts equals the total imbalance exactly, with zero cents lost or invented (verified across a suite of cases including uneven splits).
- **SC-002**: For every valid input, applying the printed payments brings all participants' net balances to exactly zero.
- **SC-003**: The number of printed payments never exceeds one less than the number of participants with a non-zero net balance.
- **SC-004**: 100% of the specified malformed-input cases (missing file, unknown payer, non-numeric amount, negative amount, empty participant list, missing header/field) produce a clear stderr message, no stdout settlement, and a non-zero exit code.
- **SC-005**: Repeated runs on identical input produce byte-identical output every time.
- **SC-006**: A user can obtain a correct settlement for a typical group (up to a few dozen expenses) from a single command invocation with no further interaction.

## Assumptions

- **Amount format**: CSV `amount` values are decimal currency amounts (e.g., `12.50`) in a single, common currency, parsed exactly into whole cents. Values with more than two decimal places are rejected rather than rounded, so no money is silently lost.
- **Currency**: A single currency is used throughout; no currency conversion is in scope. Output uses a plain decimal currency format (e.g., `15.00`) without a locale-specific symbol unless otherwise specified.
- **Participant identity**: Participants are identified by exact name match (case- and whitespace-sensitive after trimming surrounding whitespace); duplicate names in the participant list are treated as invalid.
- **Invocation**: The CSV path and the participant list are provided as command-line arguments; the tool runs to completion in one invocation without interactive prompts.
- **Minimal payments**: "Minimal" refers to minimizing the number of transactions needed to settle the computed balances; the tool uses a deterministic settlement strategy that both minimizes transactions in the common case and guarantees exact conservation.
- **Runtime**: The tool is implemented in Python 3 using only the standard library at runtime, consistent with the project constitution.
- **Description column**: The `description` field is informational only and does not affect any computation.
