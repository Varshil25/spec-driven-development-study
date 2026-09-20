# CLI Contract: Expense Splitter

The tool's external interface is its command-line invocation, its stdout/stderr streams, and its exit code. This contract is the source of truth for the end-to-end tests in `tests/test_cli.py`.

## Invocation

```text
python -m splitter <expenses.csv> --participants "Name1,Name2,Name3"
```

| Argument | Kind | Required | Meaning |
|----------|------|----------|---------|
| `expenses.csv` | positional | yes | Path to the CSV file of expenses |
| `--participants` | option (string) | yes | Comma-separated participant names; whitespace around each name is trimmed |

Running from source requires `src/` on the import path (e.g. `PYTHONPATH=src python -m splitter ...`).

## Input CSV format

- First line is a header with exactly the columns `payer`, `amount`, `description`.
- Each subsequent line is one expense.
- `amount` is a decimal currency value with at most two fractional digits (e.g. `12.50`, `30`, `0`).

Example:

```csv
payer,amount,description
Alice,30.00,Hotel
Bob,0,none
```

## Success output (stdout, exit 0)

- A deterministic, human-readable list of transfers, one per line, of the form:

  ```text
  Bob pays Alice 15.00
  ```

  Amounts are formatted at the output boundary as a plain decimal with two fractional digits (whole-cent precision, no locale symbol) — FR-018.

- When the group is already settled (all net balances zero), stdout states that no payments are needed and the tool exits `0` (FR-010). Example:

  ```text
  Already settled — no payments needed.
  ```

- Payment ordering is deterministic and derived from the supplied participant-list order (FR-017, SC-005). Repeated runs on identical input produce byte-identical stdout.

**Guarantees** (asserted by tests):
- Sum of printed payment amounts == total imbalance, exactly (FR-008, SC-001).
- Applying printed payments zeroes every net balance (SC-002).
- Number of payments ≤ (participants with non-zero balance) − 1 (SC-003).

## Error output (stderr, non-zero exit)

On any invalid input the tool writes a clear message to **stderr**, writes **nothing** to stdout, and exits with a **non-zero** status (Principle III, FR-011..FR-016). The message identifies the specific problem.

| Case | stderr message (illustrative) |
|------|-------------------------------|
| File not found / unreadable | `error: cannot read expenses file: no such file 'missing.csv'` |
| Missing/misnamed header | `error: CSV header must have columns: payer, amount, description` |
| Row missing a field | `error: row 3: missing required field 'amount'` |
| Unknown payer | `error: row 2: payer 'Carol' is not in the participant list` |
| Bad amount (non-numeric) | `error: row 2: amount 'abc' is not a valid number` |
| Negative amount | `error: row 2: amount '-5.00' must not be negative` |
| Over-precise amount | `error: row 2: amount '12.505' has more than two decimal places` |
| Empty participant list | `error: participant list must not be empty` |
| Duplicate participants | `error: duplicate participant name 'Alice'` |

Exact message wording is an implementation detail fixed by the tests; the contract requires that the message is on stderr, names the offending element, stdout is empty, and the exit code is non-zero.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success — settlement (or "already settled") printed to stdout |
| non-zero | Any validation or I/O error — message on stderr, no stdout settlement |
