# Phase 1 Data Model: Expense Splitter

All monetary quantities below are **integer cents** (`int`), never floats (Principle II). Entities are plain in-memory values produced during a single invocation; there is no persistence.

## Entity: Participant

A named member of the group, drawn from the supplied participant list.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | Unique within the group; exact match after trimming surrounding whitespace |
| `paid_cents` | `int` | Total contributed across all their expenses; ≥ 0; defaults to 0 if they never paid |
| `share_cents` | `int` | Assigned equal share of the group total (see remainder rule below) |

**Derived**: `net_cents = paid_cents - share_cents` (see Net Balance).

**Validation rules**:
- The participant list MUST be non-empty (FR-014).
- Names MUST be unique after trimming; duplicate names → reject (spec Edge Cases, Assumptions).
- Ordering is the order names appear in the supplied `--participants` argument; this order drives all deterministic output (FR-017).

## Entity: Expense

A single recorded payment read from one CSV data row.

| Field | Type | Notes |
|-------|------|-------|
| `payer` | `str` | MUST match a participant name exactly (FR-012) |
| `amount_cents` | `int` | ≥ 0; parsed exactly from the decimal string; `0` is valid (spec Edge Cases) |
| `description` | `str` | Informational only; never used in computation (FR — Assumptions) |

**Validation rules**:
- Row MUST contain non-blank `payer` and `amount` fields (FR-015; blank → reject).
- `amount` MUST be numeric, non-negative, and representable in whole cents (≤ 2 decimal places); otherwise reject naming the bad amount (FR-013).
- `payer` MUST be in the participant list; otherwise reject naming the payer (FR-012).
- The CSV MUST have a header row with columns `payer`, `amount`, `description`; missing/misnamed header → reject (FR-002, FR-015).

## Entity: Net Balance

Per-participant result of `paid_cents - share_cents`.

| Field | Type | Notes |
|-------|------|-------|
| `participant` | `str` | Participant name |
| `net_cents` | `int` | Positive → creditor (group owes them); negative → debtor (owes group); zero → settled |

**Invariants**:
- The sum of all `net_cents` across participants MUST equal `0` (conservation, Principle II).
- The sum of assigned `share_cents` MUST equal the group total exactly (FR-004).

## Entity: Payment

A proposed transfer in the settlement plan.

| Field | Type | Notes |
|-------|------|-------|
| `from_name` | `str` | A net debtor |
| `to_name` | `str` | A net creditor |
| `amount_cents` | `int` | > 0 |

**Invariants**:
- The sum of all `amount_cents` MUST equal the total imbalance (sum of positive `net_cents`) exactly (FR-008, SC-001).
- Applying all payments MUST bring every participant's `net_cents` to `0` (SC-002).
- The count of payments MUST NOT exceed `(number of participants with non-zero net balance) - 1` (FR-007, SC-003).
- When all balances are zero, the payment list is empty and the tool reports "already settled" (FR-010, spec Edge Cases).

## Share remainder rule (deterministic)

Given `total_cents` and `n` participants:
- `base = total_cents // n`, `r = total_cents % n`.
- Every participant gets `share_cents = base`; the first `r` participants **in supplied list order** get `+1` cent.
- Result: `sum(share_cents) == total_cents` exactly, and any two shares differ by at most one cent.

## Error taxonomy (raised by `parser.py`, formatted by `cli.py`)

| Condition | Requirement |
|-----------|-------------|
| CSV file missing/unreadable | FR-011 |
| Missing/misnamed header or missing required column | FR-015, FR-002 |
| Row missing a required field (blank payer/amount) | FR-015 |
| Payer not in participant list | FR-012 |
| Amount non-numeric, negative, or >2 decimals | FR-013 |
| Empty participant list | FR-014 |
| Duplicate participant names | spec Edge Cases / Assumptions |

Every error → clear stderr message + non-zero exit + **no** stdout settlement (FR-016, Principle III).
