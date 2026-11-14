# Quickstart: validating phone redaction and `--out-dir`

**Feature**: `002-phone-redaction-out-dir` | **Date**: 2026-11-14

Runnable checks that prove this feature works end to end. Each block is copy-pasteable from the
repository root. Full rules are in [`contracts/redaction-rules.md`](./contracts/redaction-rules.md);
the full command surface is in [`contracts/cli-contract.md`](./contracts/cli-contract.md).

## Prerequisites

- Python 3.11 or newer (`python3 --version`)
- No installation and no `pip install` — the tool is standard library only
- `pytest` for the test suite only

```bash
cd <repository root>
export PYTHONPATH=src
```

---

## 1. Phone numbers are redacted (Story 1, SC-001)

```bash
echo 'call +14155552671 now' | python3 -m logredact
```

```text
call [PHONE] now
```

With the four-key summary (FR-007):

```bash
echo 'a@b.io +442071838750' | python3 -m logredact --count
```

```text
stdout: [EMAIL] [PHONE]
stderr: emails=1 ips=0 cards=0 phones=1
```

All four types together:

```bash
echo 'jane@example.com 10.0.0.7 4111111111111111 +14155552671' | python3 -m logredact --count
```

```text
stdout: [EMAIL] [IP] [CARD] [PHONE]
stderr: emails=1 ips=1 cards=1 phones=1
```

## 2. Near-misses are left byte-identical (SC-002)

Every line below must come back **exactly as typed** — no placeholder, no partial redaction:

```bash
printf '%s\n' \
  '+1234567' \
  '+1234567890123456' \
  '+1 415 555 2671' \
  '+1-415-555-2671' \
  'pay +4111111111111111 now' \
  | python3 -m logredact --count
```

```text
stdout: identical to the input, all five lines
stderr: emails=0 ips=0 cards=0 phones=0
```

The fifth line is the FR-003a case: a `+`-prefixed Luhn-valid 16-digit run is **not** a card and
is left alone, where today it prints `pay +[CARD] now`.

The two shapes that *do* change, checked side by side:

```bash
echo '+4111111111119'       | python3 -m logredact --count   # → [PHONE]   phones=1
echo '+4111 1111 1111 1111' | python3 -m logredact --count   # → +[CARD]   cards=1
echo '4111111111111111'     | python3 -m logredact --count   # → [CARD]    cards=1  (unchanged)
```

## 3. Precedence is unchanged (FR-005)

```bash
echo '+15551234567@example.com' | python3 -m logredact --count
```

```text
stdout: [EMAIL]
stderr: emails=1 ips=0 cards=0 phones=0
```

## 4. `--out-dir` writes one file per input (Story 2, SC-005)

```bash
rm -rf /tmp/qs && mkdir -p /tmp/qs && cd /tmp/qs
printf 'user jane@example.com\n' > app.log
printf 'GET / from 10.0.0.7\n'   > web.log
PYTHONPATH=<repo>/src python3 -m logredact --out-dir clean app.log web.log
```

```text
stdout: wrote 2 files
stderr: (empty)
status: 0
```

```bash
cat clean/app.log   # user [EMAIL]
cat clean/web.log   # GET / from [IP]
```

Verify the folder is the only destination — no redacted line reached stdout — and that the
option works in any position:

```bash
python3 -m logredact app.log --out-dir clean --count web.log
```

```text
stdout: wrote 2 files
stderr: emails=1 ips=1 cards=0 phones=0      # one combined summary, after the stdout line
```

Missing parents are created, the input's directories are not reproduced, and the wording never
pluralises:

```bash
mkdir -p logs/2026 && cp app.log logs/2026/
python3 -m logredact --out-dir a/b/c logs/2026/app.log
ls a/b/c          # app.log   — not a/b/c/logs/2026/app.log
```

```text
stdout: wrote 1 files
```

Replacement of an existing same-named file (FR-012):

```bash
echo 'stale contents that must disappear' > clean/app.log
python3 -m logredact --out-dir clean app.log
cat clean/app.log   # user [EMAIL]  — and nothing of the stale text
```

## 5. Byte fidelity of output files (FR-013, SC-005)

The output file must be byte-for-byte what stdout would have received:

```bash
printf 'a\r\nb@c.io \xff\xfe\n+14155552671 no-trailing-newline' > odd.log
python3 -m logredact odd.log > expected.out
python3 -m logredact --out-dir clean odd.log
cmp clean/odd.log expected.out && echo "byte-identical"
```

```text
wrote 1 files
byte-identical
```

## 6. Failure paths (Story 3, SC-006)

Each must print a diagnostic naming the offending path, no `wrote N files`, no summary, no stack
trace, and exit 2.

```bash
# No FILE at all (FR-019) — stdin is not read, stdout is empty
python3 -m logredact --out-dir clean </dev/null; echo "status=$?"
# usage: python -m logredact [-h] [--count] [--out-dir DIR] [FILE ...]
# python -m logredact: error: --out-dir requires at least one FILE
# status=2

# Destination is an existing regular file (FR-016) — nothing is read
touch not-a-dir
python3 -m logredact --out-dir not-a-dir --count app.log; echo "status=$?"   # names not-a-dir, no summary

# Output path is an existing directory (FR-017)
mkdir -p clean2/app.log
python3 -m logredact --out-dir clean2 app.log; echo "status=$?"              # names clean2/app.log

# Unreadable input, second of two (FR-018, FR-017a)
rm -rf clean3
python3 -m logredact --out-dir clean3 app.log missing.log; echo "status=$?"
ls clean3        # app.log only — NO missing.log left behind
cat clean3/app.log   # complete and valid

# Output path is its own input (FR-020), first position
python3 -m logredact --out-dir . app.log; echo "status=$?"
cat app.log      # unmodified

# Output path is its own input, second position — fails before reading anything
mkdir -p out && cp app.log out/b.log
python3 -m logredact --out-dir out app.log out/b.log; echo "status=$?"
ls out           # b.log only — NO out/app.log was written
```

## 7. Nothing else moved (FR-023, SC-004)

The 001 examples must still behave identically:

```bash
echo 'user jane@example.com from 10.0.0.7' | python3 -m logredact   # user [EMAIL] from [IP]
echo '999.1.1.1'                           | python3 -m logredact   # 999.1.1.1
echo 'paid with 4111 1111 1111 1111, ref 1234567890123' | python3 -m logredact
                                                     # paid with [CARD], ref 1234567890123
python3 -m logredact --redact-all; echo "status=$?"                 # usage naming --redact-all, 2
```

Early-closing consumer, including on the `wrote N files` line — silent, status 0:

```bash
python3 -m logredact big.log | head -5          # no traceback, nothing on stderr
```

## 8. Performance (SC-007)

Memory must stay flat and a million lines must finish well under 60 s, with `--out-dir` too:

```bash
python3 -c "print('user jane@example.com from 10.0.0.7 call +14155552671'*1)" > line.txt
for i in $(seq 20); do cat line.txt line.txt > tmp && mv tmp line.txt; done   # ~1M lines
time python3 -m logredact --out-dir perf line.txt
```

## 9. The full test suite

```bash
cd <repository root>
pytest
```

Every functional requirement and every edge case in [`spec.md`](./spec.md) has at least one
covering test (SC-008), and the complete 001 suite passes with only its count-shape assertions
updated for the fourth key (SC-004).
