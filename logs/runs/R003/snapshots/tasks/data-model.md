# Phase 1 Data Model: Shared Expense Settle-Up

**Feature**: `001-expense-splitter` | **Date**: 2026-11-03

All monetary values below are **integer cents** (`int`), never `float` or `Decimal` — see
[research.md](./research.md) D1. All name ordering is ascending Unicode code-point order of the
trimmed name, i.e. Python's default `str` comparison (D5, FR-011a).

---

## Entities

### Participant

A named member of the group, supplied on the command line.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | The trimmed name; serves as the identity |

Represented as a plain `str` — it has exactly one field, so a wrapper class would be indirection
with no behaviour (Principle IV). The group is a `list[str]` in command-line order, sorted only
where ordering matters.

**Validation** (all raise `SplitterError`, checked in this order — D9):

| Rule | Requirement | Rejection trigger |
|------|-------------|-------------------|
| At least one name | FR-007 | the `--participants` value yields no names after splitting and trimming |
| No empty element | FR-007 | any comma-separated element is empty or whitespace-only after trimming (`Alice,,Bob`, `Alice,Bob,`) |
| No duplicates | FR-008 | the same trimmed name appears more than once |

**Derivation**: `raw.split(",")` → trim each element → reject empties → reject duplicates. An empty
element is never silently dropped, because the group size determines every share.

**Comparison**: case-sensitive and exact after trimming. ` Alice ` and `Alice` are the same person;
`alice` and `Alice` are two different people (FR-006).

---

### Expense

One recorded payment, read from one non-blank data row of the expenses file.

| Field | Type | Notes |
|-------|------|-------|
| `payer` | `str` | Trimmed; must be an existing participant (FR-006) |
| `amount_cents` | `int` | `>= 0` (FR-003, FR-005) |
| `line` | `int` | 1-based physical line in the file, used only for error messages |

Implemented as a frozen dataclass. The **description column is not a field**: FR-018 makes it
computationally inert, so it is read to satisfy the three-field count check and then discarded. Not
storing it is what makes acceptance scenario 1.5 (two files differing only in description produce
identical output) true by construction.

**Validation** (per row, in this order — D9):

| Rule | Requirement | Rejection trigger |
|------|-------------|-------------------|
| Exactly three fields | FR-010 | row length != 3 |
| Known payer | FR-006 | trimmed column 1 is not one of the participants |
| Valid amount | FR-003, FR-004 | trimmed column 2 fails `^\+?\d+(?:\.\d{1,2})?$` |

`amount_cents = 0` is valid and contributes nothing (FR-005); a row with amount `0.00` is
indistinguishable in effect from an absent row.

---

### ExpenseFile (transient, not a stored entity)

The parse of the whole file. Reading yields `list[Expense]`; the file-level rules are:

| Rule | Requirement | Rejection trigger |
|------|-------------|-------------------|
| Readable path | FR-009 | `OSError` from `open` — message names the path |
| Valid UTF-8 | FR-002a | `UnicodeDecodeError` — message names the path; a leading BOM is consumed by `utf-8-sig`, not an error |
| Header present and exact | FR-002, FR-010 | first non-blank row != `["payer", "amount", "description"]` (exact, no trimming, no case-folding) |

Blank rows — those `csv.reader` yields as `[]`, or as a single whitespace-only field — are skipped
wherever they appear, including before the header. A row of `,,` is **not** blank: it is a
three-field data row with an empty payer, and is rejected as an unknown payer.

---

### Share (derived)

The portion of the group total charged to one participant. Not a class — a `dict[str, int]` keyed by
participant name.

**Derivation** (FR-011, D6):

```text
total_cents = sum(e.amount_cents for e in expenses)
base, remainder = divmod(total_cents, len(participants))
share[name] = base + 1  for the first `remainder` names in ascending code-point order
share[name] = base      for the rest
```

**Invariants**:

- `sum(share.values()) == total_cents` exactly — guaranteed by `divmod` (FR-011).
- `0 <= remainder < len(participants)`, so at most one extra cent per participant.
- Every participant has a share whether or not they appear in any expense row (acceptance 1.4).
- With one participant, that participant's share is the whole total.

---

### NetBalance (derived)

What one participant paid minus what they owe.

**Derivation** (FR-012):

```text
paid[name]    = sum of amount_cents of that participant's expenses (0 if they paid nothing)
balance[name] = paid[name] - share[name]
```

**Invariants**:

- `sum(balance.values()) == 0` exactly — follows from `sum(paid) == total == sum(share)` (FR-012).
- `balance > 0` → the group owes this participant; `< 0` → this participant owes the group;
  `== 0` → settled, and they appear in no payment.
- A single participant always has balance 0, so nothing is printed (edge case: group of one).

---

### Payment (derived output)

A single whole-cent transfer from a participant who owes to one who is owed.

| Field | Type | Notes |
|-------|------|-------|
| `payer` | `str` | Had a negative balance |
| `payee` | `str` | Had a positive balance |
| `amount_cents` | `int` | `>= 1` (FR-013) |

Implemented as a frozen dataclass. The settlement is an ordered `list[Payment]`; its order is the
generation order of the algorithm below and is part of the output contract (FR-015).

**Derivation** (FR-015, D7):

```text
remaining = {name: bal for name, bal in balance.items() if bal != 0}
while any balance in remaining is negative:
    debtor   = the name minimising (remaining[name],  name)   # most negative, then name ascending
    creditor = the name minimising (-remaining[name], name)   # largest credit, then name ascending
    amount   = min(-remaining[debtor], remaining[creditor])
    emit Payment(debtor, creditor, amount)
    remaining[debtor]   += amount
    remaining[creditor] -= amount
```

**Invariants**:

- `len(payments) <= len(participants) - 1` — each iteration zeroes at least one participant, and the
  last zeroes two (FR-013, SC-003).
- `sum(p.amount_cents) == sum(b for b in balance.values() if b > 0)` — the total imbalance, exactly
  (FR-014, SC-002).
- Every `amount_cents >= 1`, so no `0.00` line is ever printed (FR-013, SC-003).
- Applying every payment leaves all balances at exactly 0 (SC-002).
- The loop terminates: balances sum to zero, so a negative balance implies a positive one exists,
  and each iteration strictly reduces the number of non-zero balances.
- Fully determined by the input — no dict-iteration-order or locale dependence (FR-015, SC-005).

---

## Transformation pipeline

```text
argv
 │  argparse (FR-001)                      ─ malformed command line ─────► exit 2 (FR-020)
 ▼
(path: str, participants_raw: str)
 │  parse_participants (FR-007, FR-008)    ─ empty / empty element / dup ─► SplitterError ► exit 1
 ▼
participants: list[str]
 │  read_expenses (FR-002, FR-002a,        ─ unreadable / undecodable /  ─► SplitterError ► exit 1
 │   FR-003..FR-006, FR-009, FR-010)          bad header / bad row
 ▼
expenses: list[Expense]                    (descriptions already discarded — FR-018)
 │  compute_shares (FR-011, FR-011a)
 ▼
shares: dict[str, int]                     sum == total_cents
 │  compute_balances (FR-012)
 ▼
balances: dict[str, int]                   sum == 0
 │  settle (FR-013, FR-014, FR-015)
 ▼
payments: list[Payment]                    sum == total imbalance; len <= n-1; each >= 1 cent
 │  format_payment (FR-016)
 ▼
stdout: "PAYER pays PAYEE 0.00\n" per payment, or nothing at all (FR-017) ► exit 0
```

No state is retained between stages beyond these values, nothing is written to disk at any stage
(FR-021, SC-008), and every rejection leaves stdout untouched because formatting happens only after
the whole pipeline has succeeded (FR-019, D8).

---

## Worked example (acceptance scenario 3.1, FR-011/FR-014)

Expenses: Alice paid `10.00`. Participants: `Alice,Bob,Carol`.

| Step | Value |
|------|-------|
| `total_cents` | 1000 |
| `divmod(1000, 3)` | `base = 333`, `remainder = 1` |
| Sorted names | `["Alice", "Bob", "Carol"]` |
| Shares | Alice 334, Bob 333, Carol 333 — sums to 1000 ✓ |
| Paid | Alice 1000, Bob 0, Carol 0 |
| Balances | Alice +666, Bob −333, Carol −333 — sums to 0 ✓ |
| Settlement step 1 | debtor Bob (tie −333 with Carol, `Bob` < `Carol`), creditor Alice, amount 333 |
| Settlement step 2 | debtor Carol, creditor Alice, amount 333 |
| Payments | `Bob pays Alice 3.33`, `Carol pays Alice 3.33` — sums to 666 = 6.67? |

The two payments total 666 cents = `6.66`, while Alice's positive balance is 666 cents. The sum of
printed payments equals the total imbalance exactly, as FR-014 requires.

> **Discrepancy to resolve before implementation**: acceptance scenario 3.1 states the printed
> amounts sum to exactly **6.67**. Under FR-011's ordered-remainder rule the odd cent is charged to
> *Alice* (first in name order), which raises her share to 334 and therefore *lowers* her credit to
> 666 — so the payments sum to 6.66, not 6.67. 6.67 would be the total only if the odd cent were
> charged to a debtor (e.g. shares Alice 333, Bob 334, Carol 333 → payments 3.34 + 3.33 = 6.67).
> FR-011/FR-011a are the normative rule and are self-consistent; the `6.67` figure in scenario 3.1
> appears to be an arithmetic slip in the example, not a separate requirement. **Planned
> resolution**: implement FR-011 as written, and have `/speckit-tasks` include a task to correct
> scenario 3.1's expected total to `6.66`. No cent is lost either way — the conservation property
> SC-002 holds under FR-011; only the example's arithmetic is wrong. Flagging rather than silently
> choosing, because the fix touches the spec.
