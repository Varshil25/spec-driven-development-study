# Phase 0 Research: Expense Splitter

All technical parameters were supplied by the user input and the project constitution; there are no open `NEEDS CLARIFICATION` items. This document records the resolved decisions and the reasoning behind each.

## Decision 1: Parse currency strings to integer cents with `decimal.Decimal`

- **Decision**: Read each `amount` field as text, parse it with `decimal.Decimal`, reject any value with more than two fractional digits or a non-numeric/negative value, then convert to an `int` number of cents (`Decimal * 100`, verified to be integral).
- **Rationale**: `Decimal` parses the human-authored decimal string exactly (no binary float error), lets us detect >2-decimal precision precisely (e.g. `12.505` → reject), and gives an exact integer cent count. This satisfies Principle II (no float ever holds money) while honoring the assumption that over-precise amounts are rejected rather than rounded (spec Assumptions, FR-013).
- **Alternatives considered**:
  - *Parse with `float`*: rejected — introduces binary representation error and violates Principle II.
  - *Manual string splitting on `.`*: rejected — brittle against signs, whitespace, exponent forms, and thousands separators; `Decimal` handles these uniformly and we can validate its result.

## Decision 2: Distribute the equal share with a deterministic largest-remainder allocation

- **Decision**: Compute `base = total_cents // n` for each participant, then distribute the `total_cents % n` leftover cents one each to the first `r` participants in the supplied participant-list order.
- **Rationale**: Guarantees the assigned shares sum exactly to the group total (conservation, FR-004/FR-008/SC-001) and is fully deterministic because it keys off the caller-supplied list order, not hashing (Principle V, FR-017). Per-person shares differ by at most one cent (SC of User Story 3).
- **Alternatives considered**:
  - *Round each share independently*: rejected — can lose or invent cents; no conservation guarantee.
  - *Randomized remainder assignment*: rejected — violates determinism.

## Decision 3: Minimal-transaction settlement via a greedy debtor/creditor match

- **Decision**: Separate participants into debtors (negative net balance) and creditors (positive net balance), then repeatedly match the largest-magnitude debtor with the largest-magnitude creditor, transferring `min(|debt|, credit)` until all balances are zero. Order ties deterministically by the supplied participant-list order.
- **Rationale**: Produces at most `k-1` transactions for `k` participants with non-zero balance (SC-003), and because every transfer fully clears at least one party, the number of transactions is minimized in the common case. Working in integer cents makes the sum of transfers equal the total imbalance exactly (FR-008). Deterministic tie-breaking preserves byte-identical output (Principle V).
- **Alternatives considered**:
  - *Exact minimum-transaction (subset-sum / partition) solver*: rejected — NP-hard, unnecessary for a small utility, and risks non-determinism; the greedy approach meets the SC-003 bound and the spec's definition of "minimal" (see spec Assumptions: minimize transactions with a deterministic strategy).
  - *Every debtor pays every creditor proportionally*: rejected — produces far more than `k-1` transactions.

## Decision 4: Argument and I/O contract via `argparse`

- **Decision**: Use `argparse` with a positional CSV path and a `--participants` (comma-separated) option (exact CLI surface fixed in [contracts/cli.md](./contracts/cli.md)). Results to stdout, diagnostics to stderr, exit `0` on success, non-zero on any validation failure.
- **Rationale**: Standard library, gives usage/`--help` for free, and cleanly separates parsing from computation so `cli.py` can map validation errors to exit codes (Principle III, FR-010..FR-016).
- **Alternatives considered**:
  - *Hand-rolled `sys.argv` parsing*: rejected — reinvents `argparse`, more error-prone, no free help text.

## Decision 5: Typed validation errors raised by `parser.py`, formatted by `cli.py`

- **Decision**: `parser.py` raises a small `ValidationError` (subclass of `Exception`) carrying a human-readable message for each rejection class (missing file, missing/misnamed header, missing field, unknown payer, bad amount, empty/duplicate participant list). `cli.py` catches it, writes the message to stderr, and returns a non-zero exit code without touching stdout.
- **Rationale**: Keeps the failure decision close to the data (parser) while keeping process concerns (streams, exit codes) in `cli.py`; guarantees no partial stdout on rejection (FR-016). Testable in isolation (Principle IV).
- **Alternatives considered**:
  - *Return sentinel/None values*: rejected — easy to forget to check, muddies the happy path, harder to attach precise messages.
  - *`sys.exit()` inside `parser.py`*: rejected — couples the parser to process exit, making it hard to unit-test and reuse.

## Resolved unknowns

None outstanding. Language (Python 3.11+), dependencies (stdlib only), testing (pytest), project type (single-project CLI), and structure were all specified by the user input and constrained by the constitution.
