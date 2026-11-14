# Quickstart: Validating `logredact`

**Feature**: `001-redact-log-pii` | **Date**: 2026-11-13

Runnable scenarios that prove the feature works end to end. Each maps to acceptance criteria in
[`spec.md`](./spec.md); the authoritative behaviour is in
[`contracts/cli-contract.md`](./contracts/cli-contract.md) and
[`contracts/redaction-rules.md`](./contracts/redaction-rules.md).

---

## Prerequisites

- Python **3.11 or newer** (`python3 --version`). Possessive quantifiers in the card pattern
  require 3.11.
- `pytest` (test-time only — the tool itself needs nothing beyond the standard library).
- No installation step: the package is run from the source tree.

```bash
cd <repo root>
export PYTHONPATH=src
python3 -m logredact --help     # usage: python -m logredact [--count] [FILE ...]
```

---

## Scenario 1 — Redact a piped log (US1, FR-002, FR-004 … FR-020)

```bash
echo 'user jane@example.com from 10.0.0.7' | python3 -m logredact
```

Expected stdout, exactly, with a trailing newline, and **nothing on stderr**; exit status 0:

```text
user [EMAIL] from [IP]
```

Then the card case, confirming the Luhn-failing reference survives:

```bash
echo 'paid with 4111 1111 1111 1111, ref 1234567890123' | python3 -m logredact
# -> paid with [CARD], ref 1234567890123
```

## Scenario 2 — No false positives (SC-002)

```bash
printf '999.1.1.1\n1.2.3.4.5\n123456789012\n12345678901234567890\n4111  1111 1111 1111\n[EMAIL] [IP] [CARD]\n' \
  | python3 -m logredact
```

Expected: output **byte-identical** to the input; exit status 0. To assert that mechanically:

```bash
printf '999.1.1.1\n1.2.3.4.5\n123456789012\n' > /tmp/near-miss.log
python3 -m logredact /tmp/near-miss.log | diff - /tmp/near-miss.log && echo "no false positives"
```

## Scenario 3 — Named files in order (US2, FR-003)

```bash
printf 'first a@b.io\n' > /tmp/one.log
printf 'second 10.0.0.7\n' > /tmp/two.log
python3 -m logredact /tmp/one.log /tmp/two.log
```

Expected, in this order, exit status 0:

```text
first [EMAIL]
second [IP]
```

Repeating a file repeats its output; standard input is not read at all when files are named:

```bash
python3 -m logredact /tmp/one.log /tmp/one.log < /tmp/two.log   # prints "first [EMAIL]" twice
```

## Scenario 4 — Count summary (US3, FR-021 … FR-023)

```bash
echo 'a@b.io 1.2.3.4' | python3 -m logredact --count
```

Expected: `[EMAIL] [IP]` on stdout and `emails=1 ips=1 cards=0` on stderr; exit status 0.
Separate the streams to check each:

```bash
echo 'a@b.io 1.2.3.4' | python3 -m logredact --count 2>/tmp/summary.txt
cat /tmp/summary.txt                      # emails=1 ips=1 cards=0
```

One combined summary covers multiple files, and the flag may sit anywhere on the command line
(FR-001):

```bash
python3 -m logredact /tmp/one.log --count /tmp/two.log 2>&1 >/dev/null
# -> emails=1 ips=1 cards=0   (a single line, after all output)
```

Without `--count`, stderr stays empty:

```bash
echo 'a@b.io' | python3 -m logredact 2>/tmp/err.txt; wc -c < /tmp/err.txt   # -> 0
```

## Scenario 5 — Unreadable file (US4, FR-025 … FR-027)

```bash
python3 -m logredact /tmp/one.log /tmp/missing.log; echo "exit=$?"
```

Expected: the redacted contents of `/tmp/one.log` on stdout, a diagnostic on stderr naming
`/tmp/missing.log`, **no** stack trace, **no** count summary even with `--count`, and
`exit=2`. Processing stops there — a third file named after it is never read.

A directory takes the same path:

```bash
python3 -m logredact /tmp; echo "exit=$?"        # names /tmp, no traceback, exit=2
```

## Scenario 6 — Invalid command line (FR-029)

```bash
python3 -m logredact --redact-all >/tmp/out.txt; echo "exit=$?"
wc -c < /tmp/out.txt                              # -> 0, stdout empty
```

Expected on stderr: a usage line plus an error naming `--redact-all`; `exit=2`.

## Scenario 7 — Consumer closes early (FR-028)

```bash
python3 -c "
for i in range(200000): print(f'line {i} jane@example.com')
" > /tmp/big.log
python3 -m logredact --count /tmp/big.log 2>/tmp/err.txt | head -5; echo "exit=${PIPESTATUS[0]}"
wc -c < /tmp/err.txt
```

Expected: five redacted lines, `exit=0`, and **0 bytes** on stderr — no traceback, no summary.

## Scenario 8 — Byte fidelity and encoding (FR-005, FR-005a, FR-005b, SC-003)

```bash
printf 'caf\xe9 jane@example.com\r\nno trailing newline' > /tmp/odd.log
python3 -m logredact /tmp/odd.log | xxd | tail -3
```

Expected: the invalid byte `\xe9` survives unchanged, the CRLF is preserved, and the last line
has no newline added. Locale independence:

```bash
LC_ALL=C      python3 -m logredact /tmp/odd.log > /tmp/a.bin
LC_ALL=C.UTF-8 PYTHONIOENCODING=latin-1 python3 -m logredact /tmp/odd.log > /tmp/b.bin
cmp /tmp/a.bin /tmp/b.bin && echo "locale independent"
```

## Scenario 9 — Streaming performance (SC-007)

```bash
time python3 -m logredact --count /tmp/big.log > /dev/null
```

Expected: well under 60 seconds for a million lines, with flat memory (watch RSS — it must not
grow with input size).

---

## Running the test suite

From the repository root, with no arguments and no install step:

```bash
pytest
```

`pytest.ini` puts `src` on the import path, so this works on a clean checkout. The full suite
must pass before the change is complete (Constitution, Principle III and the merge gate).

Useful subsets once tests exist:

```bash
pytest tests/unit            # pattern, Luhn, and counting units
pytest tests/cli             # subprocess-level exit status, stdout/stderr, broken pipe
pytest -k luhn -v
```

---

## Acceptance checklist

The feature is validated when all of these hold:

- [X] Scenarios 1–9 above produce the stated results. *(Scenario 8 inspected with `od -c`;
      `xxd` is not installed in this environment. Byte `\xe9` shows as octal `351`, the CRLF and
      the missing final newline are both preserved.)*
- [X] `pytest` passes in full from the repository root — 153 passed, 1 skipped (the `chmod 000`
      case self-skips when the suite runs as root).
- [X] Every functional requirement (FR-001 … FR-029) has at least one covering test (SC-005).
- [X] The three reported counts equal the number of placeholders in the output, for every test
      input (SC-004).
- [X] No exit status other than 0 or 2 is ever produced (SC-006).
- [X] No third-party import appears anywhere under `src/` (Constitution, Principle I).
