# Quickstart: Validating phone redaction and `--out-dir`

**Feature**: `002-redact-phones-out-dir` | **Date**: 2026-11-14

Runnable scenarios that prove this feature works end to end. Each maps to acceptance criteria in
[`spec.md`](./spec.md); the authoritative behaviour is in
[`contracts/cli-contract.md`](./contracts/cli-contract.md) and
[`contracts/redaction-rules.md`](./contracts/redaction-rules.md).

Feature 001's [`quickstart.md`](../001-redact-log-pii/quickstart.md) still applies unchanged: its
nine scenarios must keep producing the same results, with the single exception of the `--count`
summary text, which now has four keys.

---

## Prerequisites

- Python **3.11 or newer** (`python3 --version`).
- `pytest` (test-time only — the tool itself needs nothing beyond the standard library).
- No installation step: the package is run from the source tree.

```bash
cd <repo root>
export PYTHONPATH=src
python3 -m logredact --help
# usage: python -m logredact [-h] [--count] [--out-dir DIR] [files ...]
```

Fixtures used by the `--out-dir` scenarios:

```bash
cd "$(mktemp -d)" && export PYTHONPATH=<repo root>/src
mkdir -p var/logs
printf 'call +14155552671 now\n'                      > app.log
printf 'ip 10.0.0.7 card 4111111111111111 a@b.io\n'   > web.log
printf '+442071838750 rotated\n'                      > var/logs/old.log
: > empty.log
```

---

## Scenario 1 — A phone number disappears (US1, FR-030, FR-031)

```bash
echo 'call +14155552671 now' | python3 -m logredact
```

Expected stdout exactly, with a trailing newline, **nothing on stderr**, exit status 0:

```text
call [PHONE] now
```

The `+` is gone with the digits — a leftover `+[PHONE]` is a failure.

---

## Scenario 2 — Length boundaries and no partial redaction (US1-3, US1-4, FR-032, FR-033)

```bash
printf '+1234567\n+12345678\n+455673758689985\n+1234567890123456\n' | python3 -m logredact
```

Expected stdout:

```text
+1234567
[PHONE]
[PHONE]
+1234567890123456
```

7 digits is below the minimum; 8 and 15 are the bounds; 16 is rejected **whole** — seeing
`[PHONE]6` or any truncation is a failure.

---

## Scenario 3 — The `+`-prefixed card is left alone (US1-9, FR-032a)

```bash
echo '+4111111111111111' | python3 -m logredact --count
```

Expected stdout `+4111111111111111` — **no `[PHONE]`** (16 digits is too long) and **no `[CARD]`**
(the leading `+` takes the run out of the card rule) — and on stderr:

```text
emails=0 ips=0 cards=0 phones=0
```

Contrast, to confirm the card rule itself still works:

```bash
echo '4111111111111111' | python3 -m logredact      # -> [CARD]
```

---

## Scenario 4 — Precedence and no left-hand guard (US1-5, US1-8, FR-031a, FR-036)

```bash
printf '+12345678@example.com\nbuild v2+12345678 ok\nx=99+12345678\n+14155552671 10.0.0.7\n' \
  | python3 -m logredact --count
```

Expected stdout:

```text
[EMAIL]
build v2[PHONE] ok
x=99[PHONE]
[PHONE] [IP]
```

Line 1 is `[EMAIL]`, not `[PHONE]@example.com` — email wins at a shared start. Lines 2 and 3 show
the accepted over-redaction: nothing before the `+` prevents a match. Expected stderr:

```text
emails=1 ips=1 cards=0 phones=3
```

---

## Scenario 5 — The four-key summary (US2, FR-037, FR-038)

```bash
echo 'a@b.io +442071838750' | python3 -m logredact --count
```

Expected stdout `[EMAIL] [PHONE]`; expected stderr, exactly one line:

```text
emails=1 ips=0 cards=0 phones=1
```

All four keys, always in this order, `0` when none, and nothing on stderr at all without the flag:

```bash
echo 'a@b.io +442071838750' | python3 -m logredact 2>&1 >/dev/null | wc -c    # -> 0
```

---

## Scenario 6 — A folder of clean copies (US3-1, US3-2, FR-041 … FR-046)

```bash
rm -rf clean
python3 -m logredact --out-dir clean app.log web.log var/logs/old.log
```

Expected stdout exactly one line, nothing on stderr, exit status 0:

```text
wrote 3 files
```

Then check the folder:

```bash
ls clean                      # app.log  old.log  web.log   (the name only; 'var/logs' dropped)
cat clean/app.log             # call [PHONE] now
cat clean/old.log             # [PHONE] rotated
cat clean/web.log             # ip [IP] card [CARD] [EMAIL]
```

**The byte-identity check that matters** (FR-044) — an output file must equal what standard output
would have produced for the same FILE:

```bash
python3 -m logredact web.log | cmp - clean/web.log && echo "byte-identical"
```

---

## Scenario 7 — Missing parents, replacement, and bystanders (US3-3 … US3-5, FR-042, FR-043)

```bash
rm -rf deep
python3 -m logredact --out-dir deep/a/b app.log      # -> wrote 1 files
ls deep/a/b                                          # app.log — every missing parent created

printf 'STALE CONTENT THAT IS MUCH LONGER\n' > clean/app.log
printf 'keep me\n'                                   > clean/unrelated.txt
python3 -m logredact --out-dir clean app.log         # -> wrote 1 files
cat clean/app.log                                    # call [PHONE] now   (replaced, not appended)
wc -c < clean/app.log                                # 21 — not 55
cat clean/unrelated.txt                              # keep me — untouched
```

An existing folder is used as it is: it is never emptied, and files this run does not write are
left alone.

---

## Scenario 8 — Empty input, both flags, and the default destination (US3-6 … US3-8, FR-047, FR-052)

```bash
python3 -m logredact --out-dir clean --count empty.log app.log
```

Expected stdout `wrote 2 files`; expected stderr `emails=0 ips=0 cards=0 phones=1`; the
confirmation line comes before the summary when both are redirected together. An empty input gives
an empty output file that still counts:

```bash
wc -c < clean/empty.log       # 0
```

Without `--out-dir`, nothing changes and no confirmation line is ever printed:

```bash
python3 -m logredact app.log | grep -c 'wrote'    # -> 0
```

---

## Scenario 9 — Failing clearly, and leaving no truncated file (US4-1, US4-2, FR-048, FR-050a, SC-013a)

```bash
rm -rf out && python3 -m logredact --out-dir out app.log nope.log web.log --count
echo "status=$?"
```

Expected: **nothing** on stdout — no `wrote N files`, no summary — a diagnostic on stderr naming
the file as typed, and status 2:

```text
python -m logredact: nope.log: No such file or directory
status=2
```

The folder must hold exactly one file, complete, and `web.log` must never have been opened:

```bash
ls out                                           # app.log  — and nothing else
python3 -m logredact app.log | cmp - out/app.log && echo "earlier file complete"
```

---

## Scenario 10 — The other three failure paths (US4-3 … US4-5, FR-049, FR-050, FR-051)

```bash
# DIR cannot be created — its parent is a regular file. No input is read.
printf 'x\n' > blocker
python3 -m logredact --out-dir blocker/sub app.log; echo "status=$?"
# -> python -m logredact: blocker/sub: Not a directory        status=2

# The output path exists as a directory.
mkdir -p out2/app.log
python3 -m logredact --out-dir out2 app.log --count; echo "status=$?"
# -> python -m logredact: out2/app.log: Is a directory        status=2   (no summary)

# --out-dir with no FILE: invalid usage. stdin is not read and the folder is not created.
echo '+14155552671' | python3 -m logredact --out-dir never; echo "status=$?"
# -> usage: python -m logredact [-h] [--count] [--out-dir DIR] [files ...]
#    python -m logredact: error: --out-dir requires at least one FILE     status=2
test ! -e never && echo "folder not created"

# And the inherited usage path is untouched.
python3 -m logredact --redact-all; echo "status=$?"     # usage naming --redact-all, status=2
```

Every one of these must print no stack trace and write nothing to stdout.

---

## Scenario 11 — The partial file is deleted (US4-8, US4-9, FR-050a)

A write failure partway through a file, forced with `/dev/full`, with a pre-existing file of that
name in place to confirm it is **not** restored:

```bash
rm -rf out3 && mkdir out3
for i in $(seq 5000); do echo '+14155552671'; done > big.log
printf 'PRE-EXISTING\n' > out3/big.log        # will be replaced the moment the sink opens
ln -sf /dev/full out3/big.log                 # force the write to fail
python3 -m logredact --out-dir out3 big.log --count; echo "status=$?"
```

Expected: a diagnostic naming the **output path** (not the input), no confirmation line, no
summary, status 2 — and the name gone from the folder:

```text
python -m logredact: out3/big.log: No space left on device
status=2
```

```bash
ls out3                 # empty — no truncated file, and the previous contents are not restored
```

The read-failure counterpart, where the input opens cleanly and then fails:

```bash
rm -rf out4
python3 -m logredact --out-dir out4 app.log /proc/self/mem; echo "status=$?"
# -> python -m logredact: /proc/self/mem: Input/output error        status=2
ls out4                 # app.log only — the sink opened for /proc/self/mem was deleted
```

---

## Scenario 12 — Fidelity, early close, and performance (FR-044, FR-028, SC-017)

Undecodable bytes round-trip into an output file, byte for byte:

```bash
printf 'bad \377 byte +14155552671\n' > raw.log
rm -rf out5 && python3 -m logredact --out-dir out5 raw.log
od -c out5/raw.log | head -2        # 377 present; '[PHONE]' in place of the number
```

The early-close path is unchanged — silent, exit 0:

```bash
python3 -m logredact big.log | head -5 ; echo "status=${PIPESTATUS[0]}"    # status=0, stderr empty
```

Performance, in both destinations (SC-017 allows 60 s; Phase 0 measured ≈8.5 s for each, against
≈8.6 s for the pre-change tool):

```bash
python3 - <<'PY'
with open('mil.log','w') as f:
    for _ in range(1_000_000):
        f.write('user jane@example.com from 10.0.0.7 ref +14155552671 card 4111111111111111\n')
PY
time python3 -m logredact mil.log > /dev/null
rm -rf out6 && time python3 -m logredact --out-dir out6 mil.log --count
```

Memory must not grow with input size — nothing is accumulated and no file is buffered whole.

---

## Running the tests

```bash
cd <repo root>
pytest                       # the whole suite, from the repository root
```

Useful subsets:

```bash
pytest tests/unit                      # recognition rules, Luhn, precedence, counting
pytest tests/cli/test_out_dir.py       # User Story 3 — the output folder works
pytest tests/cli/test_out_dir_failures.py   # User Story 4 — it fails correctly
pytest -k phone -v
```

Phase 0 measured the exact cost of this feature to the existing suite (SC-015): **25 assertions**
fail against the new behaviour, all of them on the summary shape — 15 three-key dict literals in
`tests/unit/`, 10 three-key summary lines in `tests/cli/`. No test fails on redacted output. Those
25 are updated to the four-key form; anything else failing is a regression, not an expected update.

---

## Acceptance checklist

The feature is validated when all of these hold:

- [ ] Scenarios 1–12 above produce the stated results.
- [ ] Feature 001's nine scenarios still produce their stated results, with the summary text in its
      four-key form.
- [ ] `pytest` passes in full from the repository root.
- [ ] Every requirement FR-030 … FR-054, including FR-031a, FR-032a, and FR-050a, has at least one
      covering test (SC-016).
- [ ] The four reported counts equal the number of placeholders of each type in the output, for
      every test input (SC-010).
- [ ] An input containing neither a phone number nor a `+`-prefixed digit run produces
      byte-identical output to the pre-change tool (SC-015, FR-054).
- [ ] No exit status other than 0 or 2 is ever produced (SC-014).
- [ ] After any failed `--out-dir` run, every file left in the folder is a complete redaction of its
      input (SC-013a).
- [ ] No third-party import appears anywhere under `src/` (Constitution, Principle I).
