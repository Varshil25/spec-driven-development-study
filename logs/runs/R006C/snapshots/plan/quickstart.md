# Quickstart: validating Phone Redaction and the Output Folder

**Branch**: `002-phone-redaction-out-dir` | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

How to prove end-to-end that this amendment does what the spec requires, and that everything else
still works. Runnable from the repository root. The interface itself lives in
[contracts/cli.md](./contracts/cli.md); the recognition rules in
[contracts/redaction-rules.md](./contracts/redaction-rules.md); the reasoning in
[research.md](./research.md).

001's [quickstart](../001-logredact-cli/quickstart.md) still applies for everything this amendment
does not touch — run it too, with ` phones=0` appended to its expected tally lines.

## Prerequisites

- Python 3.11 or newer (`python3 -VV`). No runtime dependencies — standard library only
  (Principle I).
- `pytest` for the test suite. The only development dependency.
- Nothing to install or build (A-10):

```bash
export PYTHONPATH=src
```

- A POSIX filesystem that supports symbolic links, for the SR-010 confinement checks.

## 1. The three worked examples (SC-011)

All three must reproduce byte-for-byte, with the stated exit statuses.

```bash
# C-27 — a phone number becomes [PHONE]
printf 'call +14155552671 now\n' | python3 -m logredact; echo "status=$?"
# expect: call [PHONE] now        status=0

# C-42 — the four-field tally on stderr, redacted text on stdout
printf 'a@b.io +442071838750\n' | python3 -m logredact --count
# expect stdout: [EMAIL] [PHONE]
# expect stderr: emails=1 ips=0 cards=0 phones=1

# C-48 — an output folder, created, with one file per operand
rm -rf /tmp/qs && mkdir -p /tmp/qs && cd /tmp/qs
printf 'user jane@example.com\n' > app.log
printf 'GET / from 10.0.0.7\n'   > web.log
python3 -m logredact --out-dir clean app.log web.log; echo "status=$?"
# expect stdout: wrote 2 files   stderr: empty   status=0
cat clean/app.log clean/web.log
# expect: user [EMAIL]   /   GET / from [IP]
cd - >/dev/null
```

## 2. Phone recognition boundaries (SC-013, SC-014)

Both bounds are inclusive; a near miss must lose no digit to the phone rule.

```bash
printf '+12345678\n+123456789012345\n' | python3 -m logredact
# expect two lines, each exactly: [PHONE]

printf '+1234567\n14155552671\n+ 14155552671\n+1-415-555-2671\n+abc\n' | python3 -m logredact
# expect all five lines unchanged

printf '+1234567890123456\n' | python3 -m logredact
# expect unchanged: 16 digits is not a phone number, and no leading part is replaced

printf '+14155552671@example.com\n' | python3 -m logredact
# expect exactly: [EMAIL]   — email has the highest precedence

printf '++14155552671\n99+14155552671\n' | python3 -m logredact
# expect: +[PHONE]   then   99[PHONE]

printf '+4111111111111\n+41111111 11119\n' | python3 -m logredact
# expect: [PHONE]   then   [PHONE] 11119
# the second line is the one recorded consequence of FR-021 — see research.md R17
```

## 3. The output folder

```bash
rm -rf /tmp/qs && mkdir -p /tmp/qs/logs/2026 && cd /tmp/qs
printf 'user jane@example.com called +14155552671\n' > logs/2026/app.log
printf 'card 4111 1111 1111 1111\n'                  > web.log
: > empty.log

# C-50, C-51 — only the final path component names the output file; parents are created
python3 -m logredact --out-dir out/a/b logs/2026/app.log web.log empty.log
# expect stdout: wrote 3 files
find out -type d -o -type f | sort
# expect out, out/a, out/a/b, out/a/b/app.log, out/a/b/empty.log, out/a/b/web.log
# and NO out/a/b/logs or out/a/b/2026

# C-57 — an empty input yields an empty output file, and it is counted
test ! -s out/a/b/empty.log && echo "empty output file present"

# C-60, SC-020 — nothing the tool created is readable by group or other
find out -exec stat -c '%a %n' {} \;
# expect every mode to be 700 or 600

# C-52, C-61 — an existing file is replaced in full and keeps its own permissions
printf 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX\n' > out/a/b/web.log
chmod 644 out/a/b/web.log
python3 -m logredact --out-dir out/a/b web.log
cat out/a/b/web.log; stat -c '%a' out/a/b/web.log
# expect: card [CARD]   and   644   — no remnant of the X's

# C-54, SC-017 — no operand is modified
md5sum web.log logs/2026/app.log
python3 -m logredact --out-dir out/a/b web.log logs/2026/app.log >/dev/null
md5sum web.log logs/2026/app.log
# expect identical digests before and after

# C-46 — both options together: tally on stderr, count line on stdout, neither in a file
python3 -m logredact --count --out-dir out/a/b web.log
# expect stdout: wrote 1 files   stderr: emails=0 ips=0 cards=1 phones=0
grep -c 'emails=\|wrote ' out/a/b/web.log || echo "no summary text in the output file"

# C-55 — without --out-dir nothing changed: redaction on stdout, no count line
python3 -m logredact web.log
# expect: card [CARD]   and no "wrote N files" line
cd - >/dev/null
```

## 4. Failure paths (Story 4, SC-019, SC-021)

Each must name what went wrong on stderr, with no traceback and no input data.

```bash
rm -rf /tmp/qs && mkdir -p /tmp/qs && cd /tmp/qs
printf 'user jane@example.com\n' > app.log
printf 'GET / from 10.0.0.7\n'   > web.log

# C-62 — an unreadable operand: the readable ones are still written in full
python3 -m logredact --out-dir clean app.log missing.log web.log; echo "status=$?"
# expect stdout: wrote 2 files   stderr names missing.log   status=2
ls clean   # expect app.log and web.log only

# C-63 — DIR exists as a regular file: nothing is read, nothing is written
: > notadir
python3 -m logredact --out-dir notadir app.log; echo "status=$?"
# expect stderr naming notadir, empty stdout, status=2

# C-72 — an empty DIR value
python3 -m logredact --out-dir "" app.log; echo "status=$?"
# expect stderr naming the empty directory, status=2

# C-65 — --out-dir with no operand is a usage error, and DIR is not created
python3 -m logredact --out-dir nope </dev/null; echo "status=$?"
# expect stderr describing the usage, status=2
test ! -e nope && echo "nope was not created"

# C-67, SC-017 — the output path is the input file: refuse, do not truncate
md5sum app.log
python3 -m logredact --out-dir . app.log web.log; echo "status=$?"
# expect stderr naming app.log, web.log still processed, status=2
md5sum app.log   # expect the same digest

# C-73, C-74, SR-010 — a symlink at the output path is refused, not followed
mkdir -p clean2
printf 'SECRET\n' > outside.txt
ln -s ../outside.txt clean2/app.log
ln -s ../never-created.txt clean2/web.log
python3 -m logredact --out-dir clean2 app.log web.log; echo "status=$?"
# expect stderr naming both output paths, status=2
cat outside.txt                      # expect SECRET, untouched
test ! -e never-created.txt && echo "dangling target not created"

# C-69, C-70, C-75 — the allowlist stays closed
for bad in "--out_dir clean" "--out clean" "--out-di clean" "--out-dir"; do
  python3 -m logredact $bad app.log >/dev/null 2>/tmp/err; echo "$bad -> status=$?"
done
python3 -m logredact --out-dir a --out-dir b app.log; echo "status=$?"
# expect every one non-zero, with nothing on stdout and no directory created
ls   # expect no a, b or clean directory from these runs

# C-68 — an over-length line stops the run and suppresses the count line
python3 -c "
import sys
sys.stdout.write('ok line\n')
sys.stdout.write('x' * (1 << 20) + '\n')
" > big.log
python3 -m logredact --out-dir clean3 big.log app.log; echo "status=$?"
# expect stderr naming big.log and the maximum length, NO "wrote N files" on stdout, status=2
cat clean3/big.log                   # expect only: ok line
test ! -e clean3/app.log && echo "the run stopped: app.log was not read"

# C-71, SC-021 — no traceback and no input data on stderr, on any of the above
cd - >/dev/null
```

## 5. Resource bounds (SR-015, SC-018)

```bash
# the phone rule stays linear: these must scale with length, not explode
python3 - <<'PY'
import sys, time
sys.path.insert(0, "src")
from logredact.redact import redact_line
for n in (1 << 16, 1 << 18, 1 << 20):
    for make in (lambda n: "+" + "9" * n, lambda n: "+9" * (n // 2),
                 lambda n: "+9999999999999999" * (n // 17)):
        line = make(n)
        t = time.perf_counter()
        redact_line(line, {"emails": 0, "ips": 0, "cards": 0, "phones": 0})
        print(f"{len(line) >> 10:5} KiB  {(time.perf_counter() - t) * 1000:8.1f} ms")
PY
# expect each shape's time to roughly double when the length doubles, and to stay under 10 s

# memory stays flat across many large operands (SC-018)
rm -rf /tmp/qs && mkdir -p /tmp/qs/in && cd /tmp/qs
python3 -c "
open('/tmp/qs/one.log','w').write(('user jane@example.com +14155552671 10.0.0.7\n') * 50000)
"
for i in $(seq 1 50); do cp /tmp/qs/one.log in/log$i.log; done
du -sh in
/usr/bin/time -v python3 -m logredact --out-dir out in/*.log 2>&1 | grep -E 'wrote|Maximum resident'
# expect "wrote 50 files" and a peak RSS in the same band as a single-operand run (~2 MiB over
# the interpreter baseline), not growing with the number or size of the operands
cd - >/dev/null
```

## 6. The test suite (the implementation gate)

```bash
python3 -m pytest -q                    # everything, including the slow resource tests
python3 -m pytest -q -m "not slow"      # fast loop
python3 -m pytest -q -rs                # -rs: show which tests were SKIPPED and why
```

The gate is met when the full suite passes and every FR, SR and SC item in
[spec.md](./spec.md) has at least one passing test — the mapping is in
[plan.md](./plan.md#requirement-to-test-mapping).

**Report the skips.** Two tests (C-64 and C-66) are skipped when the suite runs as root, because
root bypasses the permission bits they depend on; `-rs` makes that visible. The constitution
requires a skipped test to be reported, never hidden, so state it with the results. To cover those
two paths, run the suite once as a non-root user:

```bash
# optional, if a non-root user is available
sudo -u nobody env PYTHONPATH=$PWD/src python3 -m pytest -q -rs tests/test_cli_outdir_errors.py
```

## What success looks like

| Check | Expected | Source |
|---|---|---|
| Three worked examples | byte-for-byte on stdout, stderr and in the folder | SC-011 |
| 001's suite | passes, changing only the expected `--count` text | SC-012 |
| Genuine phone corpus | 100% `[PHONE]`, no digit surviving | SC-013 |
| Near-miss corpus | 0 redacted by the phone rule | SC-014 |
| K readable operands | exactly K files, each the redaction of its operand, `wrote K files` | SC-015 |
| Operand contents | never changed, in every trial | SC-017 |
| Peak memory over 50 operands / 100× the cap | flat | SC-018 |
| Unreadable operand | status 2, named on stderr, every other output complete | SC-019 |
| Created files and directories | `mode & 0o077 == 0` | SC-020 |
| stderr and the `wrote N files` line | no personal data, ever | SC-021 |
