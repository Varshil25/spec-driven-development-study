# Quickstart & Validation Guide: Phone Redaction and Output Folder

**Branch**: `002-phone-redaction-out-dir` | **Spec**: [spec.md](./spec.md) | **Contract**: [contracts/cli.md](./contracts/cli.md)

How to run the amended tool and how to prove this feature works end to end. Expected outputs are the
contract's and are not restated in detail here — see [contracts/cli.md](./contracts/cli.md) for the
worked-example table and [contracts/redaction-rules.md](./contracts/redaction-rules.md) for the phone
grammar and precedence rows. Feature 001's
[quickstart](../001-logredact-cli/quickstart.md) still applies to everything this feature does not
change.

## Prerequisites

- CPython **3.11+** (`python3 --version`).
- No runtime dependencies, no installation, no network access.
- `pytest` only to run the test suite: `python3 -m pip install pytest`.

## Running the tool

From the repository root, with `src/` on `PYTHONPATH`:

```bash
export PYTHONPATH=src

# Phone numbers are now redacted too (User Story 1)
printf 'call +14155552671 now\n' | python3 -m logredact

# The tally has a fourth field (User Story 3)
printf 'a@b.io +442071838750\n' | python3 -m logredact --count

# One redacted copy per input file, in a folder that need not exist yet (User Story 2)
python3 -m logredact --out-dir clean app.log web.log

# Both options, in any position
python3 -m logredact app.log --out-dir clean --count web.log
```

Without `--out-dir`, every existing invocation behaves exactly as before.

## Running the tests

```bash
cd <repo root>
python3 -m pytest          # or: pytest
```

A plain invocation from the root must work with no configuration file: `tests/conftest.py` puts
`src/` on `sys.path` and provides the `run_cli` subprocess helper whose `stdout`/`stderr` come back as
`bytes` so byte fidelity can be asserted. The suite must pass **in full with nothing skipped**
(constitution gate 2) — including the pre-existing 001 tests, whose only required change is the
four-field summary format and the fourth element in `redact_line`'s tally tuple (research R3).

## Validation scenarios

Each scenario is independently runnable and corresponds to one user story or success criterion. Run
them from the repository root with `PYTHONPATH=src`. Byte-exact expectations are easiest to check with
`| xxd` or by comparing against a file.

### V1 — Phone redaction on a piped stream (US1, SC-001, SC-005)

```bash
printf 'call +14155552671 now\nuk +442071838750 us +14155552671\next +1234567\nref +1234567890123456\ndial 14155552671 please\n' \
  | python3 -m logredact
```

**Expect**: `call [PHONE] now`; `uk [PHONE] us [PHONE]`; then the last three lines **reproduced
unchanged** — 7 digits is below the range, 16 digits above it (with no fragment redacted), and a bare
digit run has no `+`. Exit 0, stderr empty.

### V2 — Nothing else changed (US1 scenarios 6–7, SC-006)

```bash
printf 'user jane@example.com from 10.0.0.7\npaid with 4111 1111 1111 1111\nhost 999.1.1.1 unreachable\n123 1.2.3.4\n' \
  | python3 -m logredact
```

**Expect**: `user [EMAIL] from [IP]`; `paid with [CARD]`; `host 999.1.1.1 unreachable`;
`123 [IP]` — identical to the current tool's output for this input.

**Stronger form of the same check**: run the same input through the pre-change tool and the amended
one and diff. For any input with no `+`-prefixed 8–15 digit run the two must be byte-identical.

### V3 — Phone boundaries and precedence (Edge Cases, SC-005)

```bash
printf '+12345678\n+123456789012345\n+ 14155552671\n+1 415 555 2671\n+14155552671@example.com\n+378282246310005\n+4111111111111111\ncall +14155552671.\n' \
  | python3 -m logredact --count
```

**Expect**, line by line: `[PHONE]`, `[PHONE]`, unchanged, unchanged, `[EMAIL]`, `[PHONE]`,
`+[CARD]`, `call [PHONE].`; and on stderr `emails=1 ips=0 cards=1 phones=4`. The 6th and 7th lines
are the documented card/phone precedence rows — see
[contracts/redaction-rules.md](./contracts/redaction-rules.md).

### V4 — The four-field tally (US3, SC-007)

```bash
printf 'a@b.io +442071838750\n' | python3 -m logredact --count
printf 'nothing sensitive here\n' | python3 -m logredact --count
printf 'x +14155552671 y +14155552671 z +14155552671\n' | python3 -m logredact --count
```

**Expect** on stderr, respectively: `emails=1 ips=0 cards=0 phones=1`,
`emails=0 ips=0 cards=0 phones=0`, `emails=0 ips=0 cards=0 phones=3`. stdout carries only the
redacted text in each case; stderr carries exactly one line.

### V5 — One output file per input, in a new folder (US2, SC-001, SC-008)

```bash
rm -rf clean
printf 'user jane@example.com\n' > app.log
printf 'GET / from 10.0.0.7\n'   > web.log
python3 -m logredact --out-dir clean app.log web.log
cat clean/app.log clean/web.log
```

**Expect**: stdout is exactly `wrote 2 files` and nothing else; `clean/app.log` contains
`user [EMAIL]`; `clean/web.log` contains `GET / from [IP]`; exit 0; `app.log` and `web.log`
unmodified (FR-020 — compare their checksums before and after).

### V6 — Missing parents created; basename only; replacement (US2 scenarios 2–4)

```bash
rm -rf out
mkdir -p logs && printf 'tel +14155552671\n' > logs/app.log
python3 -m logredact --out-dir out/deep/nested logs/app.log
cat out/deep/nested/app.log

printf 'STALE CONTENT THAT MUST NOT SURVIVE\n' > out/deep/nested/app.log
python3 -m logredact --out-dir out/deep/nested logs/app.log
cat out/deep/nested/app.log
```

**Expect**: `out/deep/nested` and both missing parents created; the output written to
`out/deep/nested/app.log` — the **basename only**, with `logs/` dropped; content `tel [PHONE]`. The
second run replaces the file entirely, so `STALE` appears nowhere in it.

### V7 — `--out-dir` combined with `--count`, in any position (US3 scenario 5, FR-019)

```bash
python3 -m logredact app.log --out-dir clean --count web.log
```

**Expect**: stdout exactly `wrote 2 files`; stderr exactly one four-field summary totalling both
files; the two redacted copies in `clean/`; exit 0. The status line is on stdout and the tally on
stderr, in that order.

### V8 — Empty input, and `wrote 1 files` is not pluralised (US2 scenario 6, Edge Cases)

```bash
rm -rf clean && : > empty.log
python3 -m logredact --out-dir clean empty.log
ls -l clean/empty.log
```

**Expect**: stdout exactly `wrote 1 files` — literally `files`; `clean/empty.log` exists and is
0 bytes; exit 0.

### V9 — Byte fidelity of output files (FR-014, SC-008)

```bash
printf 'plain\r\nlatin\xff\xfe bytes\n\ttrailing   \nno final newline' > odd.log
rm -rf clean && python3 -m logredact --out-dir clean odd.log
cmp odd.log clean/odd.log && echo IDENTICAL

# and the mode-equivalence check behind SC-008
python3 -m logredact odd.log > via_stdout.log
cmp via_stdout.log clean/odd.log && echo SAME-AS-STDOUT
```

**Expect**: both `cmp`s succeed. The file has nothing to redact, so it survives byte for byte —
`\r\n`, the invalid UTF-8 bytes, trailing whitespace, and the missing final newline — and the
output-folder path produces exactly what the stdout path does.

**General form of SC-008**: for any successful multi-file run, the concatenation of the output files
in operand order equals the stdout of the same run without `--out-dir`.

### V10 — Failure paths (US2 scenarios 7–8, FR-015 to FR-018, SC-009)

```bash
rm -rf clean
python3 -m logredact --out-dir clean app.log nope.log; echo "exit=$?"
ls clean                                   # app.log present, nope.log absent

rm -rf fresh
python3 -m logredact --out-dir fresh; echo "exit=$?"          # no operands
test -e fresh || echo "no directory created"

: > notadir && python3 -m logredact --out-dir notadir app.log; echo "exit=$?"

rm -rf clean3 && mkdir -p clean3/app.log
python3 -m logredact --out-dir clean3 app.log; echo "exit=$?"
```

**Expect**, in order:

1. Unreadable second operand: `clean/app.log` **is** written and kept, `clean/nope.log` was never
   created, stderr names `nope.log` with a reason, stdout is empty (**no** `wrote N files`), exit 2.
2. No operands: stderr is `logredact: --out-dir requires at least one FILE`, no directory created,
   standard input not read, exit 2.
3. `--out-dir` naming a regular file: stderr names `notadir` with a reason, exit 2.
4. Output name colliding with a subdirectory: stderr names `clean3/app.log` with a reason, exit 2.

Add `--count` to any of these and **no summary line** must appear (FR-007).

### V11 — Performance and flat memory (SC-010)

```bash
python3 - <<'EOF' > big.log
line = "{i} WARN user jane@example.com from 10.0.0.7 tel +14155552671 card 4111 1111 1111 1111\n"
import sys
for i in range(100_000): sys.stdout.write(line.format(i=i))
EOF

time python3 -m logredact --count big.log > /dev/null
rm -rf clean && time python3 -m logredact --count --out-dir clean big.log
```

**Expect**: both well under the 10 s budget — the design prototype measured ~0.96 s for the
redaction and ~0.04 s for the file copy (research R11) — and the tally reporting 100,000 of each of
the four categories. Memory must not grow with line count or operand count: processing is one line at
a time with at most one input and one output open.

### V12 — Regression: the 001 suite still holds (SC-004)

```bash
python3 -m pytest -q
```

**Expect**: the whole suite green, nothing skipped. The only permitted changes to pre-existing tests
are the four-field summary string and the fourth element of `redact_line`'s tally tuple; every other
001 assertion must pass as written.
