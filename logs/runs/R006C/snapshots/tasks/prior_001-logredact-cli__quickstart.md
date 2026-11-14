# Quickstart: validating the Log Redaction CLI

**Branch**: `001-logredact-cli` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

How to run the tool and prove end-to-end that it does what the spec requires. Everything here is
runnable from the repository root. Details of the interface live in
[contracts/cli.md](./contracts/cli.md); the recognition rules live in
[contracts/redaction-rules.md](./contracts/redaction-rules.md).

## Prerequisites

- Python 3.11 or newer (`python3 -VV`). No runtime dependencies — standard library only
  (Principle I).
- `pytest` for the test suite. The only development dependency.
- Nothing to install or build: `src/` on `PYTHONPATH` is the whole setup (A-10).

```bash
export PYTHONPATH=src
```

## Smoke check — the spec's worked examples

These are SC-001. All three must reproduce byte-for-byte.

```bash
# 1. email + IPv4  ->  "user [EMAIL] from [IP]", status 0
printf 'user jane@example.com from 10.0.0.7\n' | python3 -m logredact; echo "status=$?"

# 2. Luhn-valid card redacted, Luhn-failing 13-digit run untouched
printf 'paid with 4111 1111 1111 1111, ref 1234567890123\n' | python3 -m logredact

# 3. out-of-range quad untouched, valid one redacted
printf 'host 999.1.1.1 and 192.168.0.10\n' | python3 -m logredact

# 4. the tally goes to stderr, not stdout
printf 'a@b.io 1.2.3.4\n' | python3 -m logredact --count
```

Expected, in order: `user [EMAIL] from [IP]` / `status=0`; `paid with [CARD], ref 1234567890123`;
`host 999.1.1.1 and 192.168.0.10` → `host 999.1.1.1 and [IP]`; then `[EMAIL] [IP]` on stdout with
`emails=1 ips=1 cards=0` on stderr.

## Scenario 1 — redact a piped stream (Story 1, P1)

The minimum useful slice: redaction with no files and no flags.

```bash
# byte-for-byte pass-through of a line with nothing to redact (SC-003)
printf 'GET /health 200 in 3ms\n' | python3 -m logredact | cmp - <(printf 'GET /health 200 in 3ms\n') \
  && echo "pass-through OK"

# empty input -> empty output, status 0
printf '' | python3 -m logredact; echo "status=$? (expect 0)"

# invalid UTF-8 survives unchanged (A-4)
printf 'caf\xe9 jane@example.com\n' | python3 -m logredact | od -c | head -2
```

The last command must show the raw `\351` byte intact and `[EMAIL]` in place of the address.

## Scenario 2 — redact named files in order (Story 2, P2)

```bash
printf 'first jane@example.com\n'  > /tmp/a.log
printf 'second 10.0.0.7\n'         > /tmp/b.log

python3 -m logredact /tmp/a.log /tmp/b.log     # a then b
python3 -m logredact /tmp/b.log /tmp/a.log     # order honoured, not sorted
python3 -m logredact /tmp/a.log /tmp/a.log     # same operand twice -> output twice

# with an operand present, stdin is never read: this must not block or consume the input
printf 'ignored jane@example.com\n' | python3 -m logredact /tmp/a.log
```

The last command must print only the redaction of `a.log`.

## Scenario 3 — see how much was redacted (Story 3, P3)

```bash
# stdout clean enough to redirect; the tally stays out of the file (Story 3 scenario 5)
python3 -m logredact --count /tmp/a.log /tmp/b.log > /tmp/out.log
grep -c 'emails=' /tmp/out.log    # expect 0
cat /tmp/out.log

# totals are per run, not per file
python3 -m logredact --count /tmp/a.log /tmp/a.log > /dev/null   # expect emails=2 ips=0 cards=0

# without --count a successful run says nothing on stderr (FR-011)
python3 -m logredact /tmp/a.log 2>/tmp/err.log >/dev/null; wc -c < /tmp/err.log   # expect 0
```

## Scenario 4 — fail loudly (Story 4, P3)

```bash
python3 -m logredact /tmp/does-not-exist.log; echo "status=$? (expect 2)"
python3 -m logredact /tmp;                    echo "status=$? (expect 2)"   # a directory
python3 -m logredact --verbose;               echo "status=$? (expect 2)"   # rejected option

# an unreadable operand is reported and skipped; the readable ones are still redacted,
# and the run exits 2 at the end (FR-012, research.md R10)
python3 -m logredact /tmp/a.log /tmp/does-not-exist.log /tmp/b.log; echo "status=$? (expect 2)"

# one diagnostic per failing operand, in operand order
python3 -m logredact /tmp/missing1.log /tmp/missing2.log /tmp/a.log 2>&1 >/dev/null | wc -l
```

The first of those two must print the redaction of `a.log` and `b.log` on stdout — both files, not
just the first — with one diagnostic naming `does-not-exist.log` on stderr. The second must print
`2`, one line per missing operand.

```bash
# the line-length cap: 1 MiB is accepted, one character more fails (FR-018)
python3 - <<'PY'
cap = 1 << 20
open('/tmp/long.log','w').write('ok jane@example.com\n' * 2 + 'x' * cap + '\n')
PY
python3 -m logredact --count /tmp/long.log; echo "status=$? (expect 2)"

# an over-length line stops the whole run: a later operand is never read (FR-018)
python3 -m logredact /tmp/long.log /tmp/a.log; echo "status=$? (expect 2)"
```

For the over-length run: the first two lines must appear redacted on stdout, **no part** of the
long line may appear, stderr must name `/tmp/long.log` and report the length, and **no tally** may
be printed even though `--count` was given (Story 4 scenario 8).

In the second command, nothing from `a.log` may appear. The asymmetry with the unreadable-operand
case above is deliberate: FR-018 requires an over-length line to stop processing, while an
unreadable operand is skipped and the run continues ([research.md R10](./research.md)).

```bash
# no traceback on any failure path (SR-003)
python3 -m logredact /tmp/does-not-exist.log 2>&1 >/dev/null | grep -c Traceback   # expect 0

# closed downstream pipe: no traceback, not reported as success (A-7)
yes 'jane@example.com' | python3 -m logredact | head -1
```

> Running as **root** bypasses file permissions, so the "permissions deny reading" check cannot be
> demonstrated as root — `chmod 000` files stay readable. Use an unprivileged user for that one
> case; the matching test is skipped automatically when `os.geteuid() == 0`
> ([research.md R13](./research.md)).

## Resource bounds (SC-006, SC-010)

Peak memory must be bounded by roughly the 1 MiB line cap and must not grow with input size.

```bash
# ~200 MiB of input through a tool whose peak memory is a few MiB
python3 -c "
import sys
line = 'user jane@example.com from 10.0.0.7 card 4111 1111 1111 1111\n'
for _ in range(3_500_000): sys.stdout.write(line)
" | /usr/bin/time -v python3 -m logredact --count > /dev/null
```

Check `Maximum resident set size` in the output: it must stay in the low megabytes, not scale with
the 200 MiB input. Exit status must be 0.

```bash
# a single 1 GB line must be refused, not loaded (SC-010)
python3 -c "
import sys
sys.stdout.write('x' * (1 << 30)); sys.stdout.write('\n')
" | /usr/bin/time -v python3 -m logredact > /dev/null; echo "status=$? (expect 2)"
```

## Running the test suite

```bash
pytest -q                 # whole suite; must be green with nothing skipped except the root-only case
pytest -q -m "not slow"   # fast subset, skips the 1 MiB-line and large-input tests
pytest -q tests/test_redaction_rules.py   # recognition rules only
```

`pythonpath = ["src"]` is set in `pyproject.toml`, so `pytest` needs no `PYTHONPATH` of its own.

The implementation gate (constitution, *Development Workflow and Quality Gates*) is met only when
the full suite passes **and** every FR, SR, and SC item maps to a passing test. The mapping table
is in [plan.md](./plan.md); a failing or skipped test must be reported, never hidden.

## Expected performance

Measured during Phase 0 on the prototype ([research.md R14](./research.md)) — treat these as the
regression tripwires:

| Input | Expectation |
|---|---|
| realistic log lines | at least 1 MB/s (measured 4.7 MB/s, ~50,000 lines/s) |
| adversarial 1 MiB line (`"1 " * 524288`, `"a" * 1048576`, `"a"*n + "@" + "1."*n`) | under 10 s (measured 3.4 s worst case) |
| 8 MiB single line (rejected) | peak traced memory ~2 MiB |

A regression here is not a slowdown but a hang: the pre-guard email pattern took an extrapolated
~1.5 hours on a single 1 MiB line.
