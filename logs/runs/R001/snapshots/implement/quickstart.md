# Quickstart & Validation: Expense Splitter

This guide proves the feature works end to end. It references [contracts/cli.md](./contracts/cli.md) for the exact CLI surface and [data-model.md](./data-model.md) for entity/invariant details rather than repeating them.

## Prerequisites

- Python 3.11+ (`python --version`)
- `pytest` for the test suite (development-only dependency): `python -m pip install pytest`
- No third-party runtime dependencies (Constitution Principle I)

## Setup

From the repository root, put the package on the import path:

```bash
export PYTHONPATH=src
```

## Scenario 1 — Basic settlement (User Story 1, FR-001..FR-010)

```bash
cat > /tmp/trip.csv <<'CSV'
payer,amount,description
Alice,30.00,Hotel
Bob,0,none
CSV

python -m splitter /tmp/trip.csv --participants "Alice,Bob"
```

**Expected**: exit code `0`, and stdout:

```text
Bob pays Alice 15.00
```

## Scenario 2 — Already settled (FR-010, Edge Cases)

```bash
cat > /tmp/even.csv <<'CSV'
payer,amount,description
Alice,10.00,Lunch
Bob,10.00,Dinner
CSV

python -m splitter /tmp/even.csv --participants "Alice,Bob"
```

**Expected**: exit code `0`, stdout states no payments are needed (e.g. `Already settled — no payments needed.`).

## Scenario 3 — Uneven split conserves every cent (User Story 3, FR-004/FR-008, SC-001)

```bash
cat > /tmp/three.csv <<'CSV'
payer,amount,description
Alice,10.00,Coffee
CSV

python -m splitter /tmp/three.csv --participants "Alice,Bob,Carol"
```

**Expected**: exit code `0`. Shares are `3.34 / 3.33 / 3.33` (sum exactly `10.00`); printed payments sum to exactly the total imbalance, and applying them zeroes every balance.

## Scenario 4 — Malformed input fails loudly (User Story 2, FR-011..FR-016, SC-004)

Each command below MUST print an error to **stderr**, print **nothing** to stdout, and exit **non-zero**.

```bash
# Missing file (FR-011)
python -m splitter /tmp/does-not-exist.csv --participants "Alice,Bob"; echo "exit=$?"

# Unknown payer (FR-012)
printf 'payer,amount,description\nCarol,5.00,x\n' > /tmp/bad_payer.csv
python -m splitter /tmp/bad_payer.csv --participants "Alice,Bob"; echo "exit=$?"

# Negative / non-numeric / over-precise amount (FR-013)
printf 'payer,amount,description\nAlice,-5.00,x\n' > /tmp/bad_amt.csv
python -m splitter /tmp/bad_amt.csv --participants "Alice,Bob"; echo "exit=$?"

# Empty participant list (FR-014)
printf 'payer,amount,description\nAlice,5.00,x\n' > /tmp/ok.csv
python -m splitter /tmp/ok.csv --participants ""; echo "exit=$?"

# Missing header column (FR-015)
printf 'payer,amount\nAlice,5.00\n' > /tmp/bad_header.csv
python -m splitter /tmp/bad_header.csv --participants "Alice,Bob"; echo "exit=$?"
```

**Expected**: every case prints a clear stderr message naming the problem and reports a non-zero `exit=`.

## Scenario 5 — Deterministic output (FR-017, SC-005)

```bash
python -m splitter /tmp/three.csv --participants "Alice,Bob,Carol" > /tmp/run1.txt
python -m splitter /tmp/three.csv --participants "Alice,Bob,Carol" > /tmp/run2.txt
diff /tmp/run1.txt /tmp/run2.txt && echo "byte-identical"
```

**Expected**: `diff` reports no differences (`byte-identical`).

## Run the automated suite

```bash
python -m pytest
```

**Expected**: all tests pass. The suite covers money helpers (`test_money.py`), settlement + conservation + minimality (`test_settle.py`), CSV/participant validation (`test_parser.py`), and end-to-end CLI behavior including exit codes and stderr (`test_cli.py`) — one or more tests per functional requirement (Constitution Principle IV).

## Requirement coverage map

| Requirement group | Validated by |
|-------------------|--------------|
| FR-001..FR-010 (read, compute, settle, output) | Scenarios 1–3; `test_settle.py`, `test_cli.py` |
| FR-004, FR-008, FR-009 (conservation, integer cents) | Scenario 3; `test_money.py`, `test_settle.py` |
| FR-007 (minimal transactions) | `test_settle.py` (SC-003 bound) |
| FR-011..FR-016 (fail loudly, no partial stdout) | Scenario 4; `test_parser.py`, `test_cli.py` |
| FR-017, FR-018 (deterministic, formatted output) | Scenarios 1 & 5; `test_cli.py` |
