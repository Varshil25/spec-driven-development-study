# Quickstart & Validation: Shared Expense Settle-Up

**Feature**: `001-expense-splitter` | **Date**: 2026-11-03

How to run the tool and confirm end to end that the feature works. Interface details live in
[`contracts/cli.md`](./contracts/cli.md); entity rules and invariants in
[`data-model.md`](./data-model.md). This guide contains no implementation code.

## Prerequisites

- Python 3.11 or newer (`python3 --version`)
- `pytest` for the test suite — the only development dependency; the tool itself needs nothing
  beyond the standard library
- No install step, virtualenv, build, or network access required

## Setup

Run everything from the repository root. `src` must be on the import path:

```bash
cd /root/sdd-study/runs/R003
export PYTHONPATH=src
```

`pytest.ini` already sets `pythonpath = src`, so the test suite needs no environment variable — the
export above is only for running the tool by hand.

## Run the tool

```bash
cat > /tmp/trip.csv <<'EOF'
payer,amount,description
Alice,30.00,Hotel
EOF

python -m splitter /tmp/trip.csv --participants "Alice,Bob"
```

Expected — exactly one line on stdout, exit status 0:

```text
Bob pays Alice 15.00
```

Check the status explicitly:

```bash
python -m splitter /tmp/trip.csv --participants "Alice,Bob"; echo "exit=$?"
```

## Run the test suite

```bash
pytest                 # whole suite, from the repository root
pytest -q              # quiet
pytest tests/test_settle.py -v     # just the cent-arithmetic invariants
```

Expected: all tests pass. Every functional requirement FR-001…FR-021 has at least one test naming
it (see the traceability table in [`plan.md`](./plan.md)); the suite is the merge gate.

---

## Validation scenarios

Each scenario below is a runnable check of one acceptance requirement. Together they cover the three
user stories. All of them assume `export PYTHONPATH=src` from Setup.

### V1 — Reference case (SC-001, FR-016)

```bash
printf 'payer,amount,description\nAlice,30.00,Hotel\n' > /tmp/v1.csv
python -m splitter /tmp/v1.csv --participants "Alice,Bob"
```

**Expect**: stdout is exactly `Bob pays Alice 15.00`, exit 0.

### V2 — Participant who paid nothing is still charged (FR-011, acceptance 1.2 & 1.4)

```bash
printf 'payer,amount,description\nAlice,60.00,Flights\nBob,30.00,Food\n' > /tmp/v2.csv
python -m splitter /tmp/v2.csv --participants "Alice,Bob,Carol"
```

**Expect**: at most two lines; Carol appears as a payer; the printed amounts total `30.00` (Carol's
share), and applying them zeroes all three balances.

### V3 — Already settled prints nothing (FR-017, acceptance 1.3)

```bash
printf 'payer,amount,description\nAlice,10.00,A\nBob,10.00,B\n' > /tmp/v3.csv
python -m splitter /tmp/v3.csv --participants "Alice,Bob"; echo "exit=$?"
```

**Expect**: no output at all before `exit=0`.

### V4 — Awkward split loses no cent (SC-002, FR-011, FR-014)

```bash
printf 'payer,amount,description\nAlice,10.00,Taxi\n' > /tmp/v4.csv
python -m splitter /tmp/v4.csv --participants "Alice,Bob,Carol"
```

**Expect**: two lines whose amounts sum to exactly Alice's positive balance, with every cent
accounted for. Verify the sum mechanically:

```bash
python -m splitter /tmp/v4.csv --participants "Alice,Bob,Carol" \
  | awk '{ total += $NF } END { printf "paid out: %.2f\n", total }'
```

**Expect** (acceptance 3.1): `paid out: 6.66` — per FR-011 the leftover cent is charged to `Alice`,
first in name order, so her share is 3.34 and the two payments are 3.33 each.

### V5 — Description text is inert (FR-018, acceptance 1.5)

```bash
printf 'payer,amount,description\nAlice,30.00,Hotel\n'        > /tmp/v5a.csv
printf 'payer,amount,description\nAlice,30.00,"Hotel, nice"\n' > /tmp/v5b.csv
diff <(python -m splitter /tmp/v5a.csv --participants "Alice,Bob") \
     <(python -m splitter /tmp/v5b.csv --participants "Alice,Bob") && echo "identical"
```

**Expect**: `identical`. Note the second file's quoted description contains a comma — it must still
parse as three fields.

### V6 — Byte-order mark tolerated (FR-002a, acceptance 1.7)

```bash
printf 'payer,amount,description\nAlice,30.00,Hotel\n'           > /tmp/v6a.csv
printf '\xef\xbb\xbfpayer,amount,description\nAlice,30.00,Hotel\n' > /tmp/v6b.csv
diff <(python -m splitter /tmp/v6a.csv --participants "Alice,Bob") \
     <(python -m splitter /tmp/v6b.csv --participants "Alice,Bob") && echo "identical"
```

**Expect**: `identical`, both exit 0.

### V7 — Determinism, including across locales (SC-005, FR-015)

```bash
LC_ALL=C      python -m splitter /tmp/v2.csv --participants "Alice,Bob,Carol" > /tmp/run1
LC_ALL=en_US.UTF-8 python -m splitter /tmp/v2.csv --participants "Alice,Bob,Carol" > /tmp/run2
cmp /tmp/run1 /tmp/run2 && echo "byte-identical"
```

**Expect**: `byte-identical`.

### V8 — Error cases all fail loudly (FR-019, FR-020, SC-004, SC-007)

Each command must print one message on stderr naming the problem, print **nothing** on stdout, and
exit non-zero. Exact message texts are in [`contracts/cli.md`](./contracts/cli.md).

```bash
printf 'payer,amount,description\nAlice,30.00,Hotel\n' > /tmp/ok.csv

# exit 1 — input and validation failures
python -m splitter /tmp/does-not-exist.csv --participants "Alice,Bob"   # unreadable path (FR-009)
printf 'payer,amount,description\nDave,5.00,X\n' > /tmp/e1.csv
python -m splitter /tmp/e1.csv --participants "Alice,Bob"               # unknown payer (FR-006)
printf 'payer,amount,description\nAlice,abc,X\n' > /tmp/e2.csv
python -m splitter /tmp/e2.csv --participants "Alice,Bob"               # non-numeric (FR-004)
printf 'payer,amount,description\nAlice,-5.00,X\n' > /tmp/e3.csv
python -m splitter /tmp/e3.csv --participants "Alice,Bob"               # negative (FR-004)
printf 'payer,amount,description\nAlice,1.005,X\n' > /tmp/e4.csv
python -m splitter /tmp/e4.csv --participants "Alice,Bob"               # over-precise (FR-004)
python -m splitter /tmp/ok.csv --participants ""                        # empty list (FR-007)
python -m splitter /tmp/ok.csv --participants "Alice,,Bob"              # empty name (FR-007)
python -m splitter /tmp/ok.csv --participants "Alice,Alice"             # duplicate (FR-008)
printf 'Payer,Amount,Description\nAlice,5.00,X\n' > /tmp/e5.csv
python -m splitter /tmp/e5.csv --participants "Alice,Bob"               # bad header (FR-002)
printf 'payer,amount,description\nAlice,5.00\n' > /tmp/e6.csv
python -m splitter /tmp/e6.csv --participants "Alice,Bob"               # bad row length (FR-010)
printf 'payer,amount,description\nAlice,5.00,\xff\xfe\n' > /tmp/e7.csv
python -m splitter /tmp/e7.csv --participants "Alice,Bob"               # bad UTF-8 (FR-002a)

# exit 2 — malformed command line (FR-020)
python -m splitter /tmp/ok.csv                                          # missing --participants
python -m splitter --participants "Alice,Bob"                           # missing path
python -m splitter /tmp/ok.csv --participants "Alice,Bob" --verbose     # unknown option
```

Confirm stdout stays empty and the status is right for one of them:

```bash
out=$(python -m splitter /tmp/e2.csv --participants "Alice,Bob" 2>/tmp/err); status=$?
echo "stdout=[$out] exit=$status"; cat /tmp/err
```

**Expect**: `stdout=[] exit=1`, and the message names both the row and the value `abc`.

### V9 — Only the first problem is reported (FR-010a, acceptance 2.8)

```bash
printf 'payer,amount,description\nAlice,abc,X\nDave,xyz,Y\n' > /tmp/v9.csv
python -m splitter /tmp/v9.csv --participants "Alice,Bob" 2>&1 | wc -l
```

**Expect**: `1` — exactly one message, concerning line 2 (`abc`), with nothing about line 3.

### V10 — The expenses file is never modified (FR-021, SC-008)

```bash
md5sum /tmp/v2.csv > /tmp/before
python -m splitter /tmp/v2.csv --participants "Alice,Bob,Carol" >/dev/null
python -m splitter /tmp/e2.csv --participants "Alice,Bob" 2>/dev/null
md5sum -c /tmp/before && echo "unchanged"
```

**Expect**: `unchanged` after both a successful and a failed run.

### V11 — Performance ceiling (SC-006)

```bash
python - <<'EOF'
import random
names = [f"P{i:02d}" for i in range(50)]
with open("/tmp/big.csv", "w", encoding="utf-8") as fh:
    fh.write("payer,amount,description\n")
    for i in range(1000):
        fh.write(f"{random.choice(names)},{random.randint(1, 50000)/100:.2f},item{i}\n")
EOF
time python -m splitter /tmp/big.csv --participants "$(python -c 'print(",".join(f"P{i:02d}" for i in range(50)))')" | tail -1
```

**Expect**: completes in well under two seconds; at most 49 payment lines.

## Done when

- [ ] `pytest` passes from the repository root with no arguments
- [ ] V1–V11 each produce the expected result
- [ ] No third-party module is imported by anything under `src/`
- [ ] `git status` is clean after a run — the tool created and changed nothing
