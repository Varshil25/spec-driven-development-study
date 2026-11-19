# Quickstart & Validation Guide: Log Redaction CLI

**Branch**: `001-logredact-cli` | **Spec**: [spec.md](./spec.md) | **Contract**: [contracts/cli.md](./contracts/cli.md)

How to run the tool and how to prove it works end to end. Expected outputs are the contract's, not
restated here in detail — see [contracts/cli.md](./contracts/cli.md) for the worked example table and
[contracts/redaction-rules.md](./contracts/redaction-rules.md) for recognition rules.

## Prerequisites

- CPython **3.11+** (`python3 --version`).
- No runtime dependencies, no installation, no network access.
- `pytest` only to run the test suite: `python3 -m pip install pytest`.

## Running the tool

From the repository root, with `src/` on `PYTHONPATH`:

```bash
export PYTHONPATH=src

# Pipe a log through it (User Story 1)
printf 'user jane@example.com from 10.0.0.7\n' | python3 -m logredact

# Redact named files in order (User Story 2)
python3 -m logredact app.log audit.log > redacted.log

# Confirm what was removed; summary goes to stderr, not into the output (User Story 3)
python3 -m logredact --count app.log > redacted.log

# Flag position does not matter
python3 -m logredact app.log --count > redacted.log
```

Without setting `PYTHONPATH` globally: `PYTHONPATH=src python3 -m logredact ...`.

## Running the tests

```bash
cd <repo root>
python3 -m pytest          # or: pytest
```

A plain invocation from the root must work with no configuration file: `tests/conftest.py` puts
`src/` on `sys.path` and provides the subprocess helper used by the end-to-end tests. The suite must
pass in full with nothing skipped before any change is considered done (constitution, gate 2).

## Validation scenarios

Each scenario is independently runnable and corresponds to one user story or success criterion. Run
them from the repository root with `PYTHONPATH=src`.

### V1 — Redaction of a piped stream (US1, SC-001, SC-005)

```bash
printf 'user jane@example.com from 10.0.0.7\npaid with 4111 1111 1111 1111, ref 1234567890123\nhost 999.1.1.1 unreachable\n' \
  | python3 -m logredact
```

**Expect**: line 1 `user [EMAIL] from [IP]`; line 2 `paid with [CARD], ref 1234567890123`; line 3
unchanged. Exit 0, stderr empty. Proves recognised values are redacted and near-misses are not
touched.

### V2 — Byte fidelity (SC-004)

```bash
printf 'no secrets here\r\nlast line without newline' > /tmp/plain.log
python3 -m logredact /tmp/plain.log | cmp - /tmp/plain.log && echo IDENTICAL
```

**Expect**: `IDENTICAL`. The `\r` survives and no trailing newline is invented.

### V3 — Non-UTF-8 passthrough (Edge Cases)

```bash
printf 'caf\xe9 jane@example.com\n' > /tmp/latin.log
python3 -m logredact /tmp/latin.log | od -c | head -2
```

**Expect**: the `\xe9` byte appears unchanged in the output and the email is replaced by `[EMAIL]`.
Exit 0, no traceback.

### V4 — Multiple files in order (US2)

```bash
printf 'first a@b.io\n' > /tmp/one.log
printf 'second 1.2.3.4\n' > /tmp/two.log
python3 -m logredact /tmp/one.log /tmp/two.log
python3 -m logredact /tmp/one.log /tmp/one.log   # same file twice → content twice
```

**Expect**: first file's redacted content, then the second's, nothing reordered or dropped; the
repeat run prints the redacted content twice. Exit 0 both times.

### V5 — Count summary and stream separation (US3, SC-006)

```bash
printf 'a@b.io 1.2.3.4\n' | python3 -m logredact --count >/tmp/out.txt 2>/tmp/err.txt
cat /tmp/out.txt; cat /tmp/err.txt
```

**Expect**: `/tmp/out.txt` is `[EMAIL] [IP]`, `/tmp/err.txt` is `emails=1 ips=1 cards=0`. Nothing on
stderr when `--count` is omitted. Counts must equal the number of placeholders in the output.

### V6 — Unreadable input fails loudly (US4, SC-007)

```bash
python3 -m logredact /tmp/one.log /tmp/does-not-exist.log; echo "exit=$?"
python3 -m logredact /tmp; echo "exit=$?"            # a directory
python3 -m logredact --bogus; echo "exit=$?"         # unknown option
```

**Expect**: in each case a stderr diagnostic naming the offending path (or the bad option) and a
reason, and `exit=2`. In the first case the redacted content of `/tmp/one.log` has already been
written to stdout, and **no** summary line appears even with `--count`.

### V7 — Closed downstream pipe (Edge Cases)

```bash
python3 -m logredact /tmp/big.log | head -1 >/dev/null; echo "exit=${PIPESTATUS[0]}"
```

**Expect**: no traceback and no "Exception ignored" noise; a single-line diagnostic on stderr and
exit status 2 from the tool.

### V8 — Performance and flat memory (SC-008)

```bash
python3 - <<'PY'
with open('/tmp/big.log','w') as f:
    for i in range(100_000):
        f.write(f'{i} WARN user jane@example.com from 10.0.0.7 card 4111 1111 1111 1111\n')
PY
time python3 -m logredact --count /tmp/big.log > /dev/null
```

**Expect**: completes well under 10 seconds (the design prototype measured ~1.4 s for 100k dense
lines) and reports `emails=100000 ips=100000 cards=100000`. Memory does not grow with line count —
the tool holds one line at a time.

## Definition of done

1. All eight validation scenarios above behave as stated.
2. `pytest` passes in full from the repository root, nothing skipped.
3. Every requirement FR-001…FR-023 is named by at least one test — see the coverage map in
   [contracts/cli.md](./contracts/cli.md).
4. Every edge case in the spec has a test (SC-003).
5. No runtime import outside the standard library.
