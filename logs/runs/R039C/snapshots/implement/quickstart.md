# Quickstart: validating Phone Redaction and the Output Folder

**Feature**: 002-phone-redaction-out-dir | **Date**: 2026-11-21

Runnable end-to-end checks that prove this feature works, and that feature 001 still works. Each
scenario names the user story, requirements, and success criteria it validates, and states the
expected outcome precisely enough to be checked by eye or by `diff`.

Interface details are **not** repeated here — see [contracts/cli.md](./contracts/cli.md),
[contracts/redaction-rules.md](./contracts/redaction-rules.md), and
[data-model.md](./data-model.md).

## Prerequisites

- CPython 3.11 or newer, on Linux or macOS (see research.md D-113).
- `pytest` for the automated suite. Nothing else: the tool itself needs no installation and no
  third-party package (FR-018).
- Run every command from the repository root, with a `umask` of `022` or stricter.

```bash
cd /path/to/repo
export PYTHONPATH=src
python3 --version          # expect 3.11 or newer
```

`$TMP` below is a scratch directory you can delete afterwards:

```bash
TMP=$(mktemp -d); echo "$TMP"
```

---

## Scenario 1 — Phone numbers are redacted (US1, P1, FR-001/FR-002, SC-001/SC-002)

```bash
printf 'call +14155552671 now\n' | python3 -m logredact
printf 'a@b.io +442071838750\n'  | python3 -m logredact
printf 'at +12345678 and +123456789012345\n' | python3 -m logredact
```

Expected, in order:

```text
call [PHONE] now
[EMAIL] [PHONE]
at [PHONE] and [PHONE]
```

Near-misses must come back **byte-for-byte unchanged** (SC-002). This prints nothing if correct:

```bash
printf 'code +1234567\nref +1234567890123456\ntel +1 415 555 2671\n+ 14155552671\n+\n' > "$TMP/near.log"
python3 -m logredact "$TMP/near.log" | diff - "$TMP/near.log" && echo "SC-002 ok"
```

Overlap with the higher ranks — note that `+4222222222222` stays `[CARD]`, which is the whole point
of ranking phone last (FR-003):

```bash
printf '+14155552671@example.com\n+10.0.0.7\n+4222222222222\nx ++14155552671\n100+14155552671\n' \
  | python3 -m logredact
```

Expected:

```text
[EMAIL]
+[IP]
+[CARD]
x +[PHONE]
100[PHONE]
```

## Scenario 2 — Nothing else changed (FR-005, SC-003)

Feature 001's own samples contain no phone numbers, so their output must be identical to before.

```bash
printf 'user jane@example.com from 10.0.0.7 card 4111 1111 1111 1111\n' > "$TMP/001.log"
python3 -m logredact "$TMP/001.log"
```

Expected exactly `user [EMAIL] from [IP] card [CARD]`.

For a wider check, run feature 001's quickstart scenarios 1–7
([../001-log-data-redaction-cli/quickstart.md](../001-log-data-redaction-cli/quickstart.md))
unchanged. Every one must still produce its documented output and exit status, except
001 Scenario 3's three-field `--count` summary, which FR-004 supersedes.

## Scenario 3 — Output folder (US2, P2, FR-006 – FR-011, FR-013, SC-005)

```bash
mkdir -p "$TMP/logs/2026"
printf 'user jane@example.com\n'   > "$TMP/logs/2026/app.log"
printf 'GET / from 10.0.0.7\n'     > "$TMP/web.log"
cd "$TMP" && PYTHONPATH=/path/to/repo/src python3 -m logredact --out-dir clean logs/2026/app.log web.log
```

Expected:

- stdout is exactly `wrote 2 files`, and **nothing else** — no redacted content (FR-007, FR-010).
- stderr is empty; exit status 0.
- `clean/app.log` contains `user [EMAIL]`; `clean/web.log` contains `GET / from [IP]`.
- The input's directories did not travel: there is **no** `clean/logs` (FR-007, US2-5).

```bash
ls -R clean; cat clean/app.log clean/web.log; echo "status=$?"
```

Singular form, nested creation, replacement, and position-independence:

```bash
python3 -m logredact --out-dir one web.log                  # expect: wrote 1 file
python3 -m logredact --out-dir reports/2026/clean web.log   # all three levels created
printf 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX\n' > clean/app.log   # longer stale content
python3 -m logredact --out-dir clean logs/2026/app.log      # expect full replacement
cat clean/app.log                                           # expect: user [EMAIL]
python3 -m logredact web.log --out-dir clean logs/2026/app.log   # option in any position
python3 -m logredact --out-dir=clean web.log                # the "=" form
```

Equivalence with the streaming mode — each output file must be byte-identical to piping that one
file through the tool (SC-005). This prints nothing if correct:

```bash
for f in logs/2026/app.log web.log; do
  python3 -m logredact "$f" | diff - "clean/$(basename "$f")"
done && echo "SC-005 ok"
```

Structure preservation (FR-013): an empty input gives an empty output file, an unterminated final
line gains no terminator, and non-UTF-8 bytes survive.

```bash
: > empty.log
printf 'no newline at end' > bare.log
printf 'caf\xe9 jane@example.com\n' > latin.log
python3 -m logredact --out-dir clean empty.log bare.log latin.log   # expect: wrote 3 files
test ! -s clean/empty.log && echo "empty ok"
xxd clean/bare.log | tail -1      # must not end with 0a
xxd clean/latin.log | head -1     # expect the raw c3? byte run preserved as 0xe9
```

## Scenario 4 — Four-field count (US3, P3, FR-004, FR-016, SC-004)

```bash
printf 'a@b.io +442071838750\n' | python3 -m logredact --count >/dev/null
printf 'nothing here\n'         | python3 -m logredact --count >/dev/null
printf '+14155552671\n+14155552671\n+14155552671\n' | python3 -m logredact --count >/dev/null
```

Expected on **stderr** only (stdout was discarded above):

```text
emails=1 ips=0 cards=0 phones=1
emails=0 ips=0 cards=0 phones=0
emails=0 ips=0 cards=0 phones=3
```

Combined with `--out-dir`, the tally comes first on stdout and the single run-wide summary second on
stderr (FR-016, US3-5):

```bash
cd "$TMP" && python3 -m logredact --count --out-dir clean logs/2026/app.log web.log
```

Expected: `wrote 2 files` on stdout, `emails=1 ips=1 cards=0 phones=0` on stderr, exit 0.
Without `--count`, stderr is empty either way (US3-6).

## Scenario 5 — Failures are loud (US4, P3, FR-012/FR-014/FR-015, SC-008)

Each command must print a diagnostic naming the problem on stderr, write **no** `wrote N files`
line, write **no** summary, and exit **2**:

```bash
cd "$TMP"
python3 -m logredact --out-dir clean missing.log           ; echo "status=$?"   # unreadable FILE
python3 -m logredact --out-dir clean                       ; echo "status=$?"   # no FILE
python3 -m logredact --out-dir                             ; echo "status=$?"   # no value
python3 -m logredact --out-dir "" web.log                  ; echo "status=$?"   # empty value
: > notadir ; python3 -m logredact --out-dir notadir web.log ; echo "status=$?" # DIR is a file
mkdir -p clean/busy.log ; python3 -m logredact --out-dir clean busy.log ; echo "status=$?"
python3 -m logredact --out-dir . web.log                   ; echo "status=$?"   # output == input
```

Partial success is preserved and reported as failure (US4-1):

```bash
rm -rf part && python3 -m logredact --out-dir part web.log missing.log; echo "status=$?"
ls part            # expect web.log present and complete
cat part/web.log   # expect GET / from [IP]
```

`--out-dir` with no FILE must not read stdin and must not create the folder (FR-012):

```bash
rm -rf never
printf 'jane@example.com\n' | python3 -m logredact --out-dir never; echo "status=$?"
test ! -e never && echo "FR-012 ok: nothing created"
```

## Scenario 6 — Containment and permissions (SR-005 – SR-008, SC-006/SC-007)

A FILE's directories, `..` segments, and absolute root can only ever name a file **inside** DIR:

```bash
cd "$TMP" && rm -rf jail && mkdir jail
printf 'secret 10.0.0.7\n' > "$TMP/outside.log"
# Run from a *subdirectory*, so "../outside.log" resolves to the file just
# created. Invoked from "$TMP" the ".." would point at "$TMP"'s parent, and the
# command would exit 2 as an unreadable FILE before the containment rule was
# ever reached — proving nothing.
cd "$TMP/logs"
python3 -m logredact --out-dir "$TMP/jail" ../outside.log /etc/hostname; echo "status=$?"
```

Expected: `wrote 2 files`, exit 0, and both outputs **inside** `jail`:

```bash
ls "$TMP/jail"                  # expect exactly: hostname  outside.log
cat "$TMP/jail/outside.log"     # expect: secret [IP]
cat "$TMP/outside.log"          # input unchanged: secret 10.0.0.7
test ! -e /tmp/hostname && echo "ok: nothing created above jail"
```

A planted symlink must not become a write through it (SR-006, SC-006):

```bash
rm -f escape.txt && ln -s "$TMP/escape.txt" jail/web.log
python3 -m logredact --out-dir jail web.log; echo "status=$?"    # expect 2, names jail/web.log
test ! -e escape.txt && echo "SR-006 ok: link not followed"
```

Owner-only permissions on everything the tool creates (SR-007, SC-007):

```bash
rm -rf perms && python3 -m logredact --out-dir perms/a/b web.log
stat -c '%a %n' perms perms/a perms/a/b perms/a/b/web.log    # expect 700 700 700 600
```

Pre-existing output files end the run narrowed, not widened:

```bash
chmod 666 perms/a/b/web.log && python3 -m logredact --out-dir perms/a/b web.log
stat -c '%a %n' perms/a/b/web.log                            # expect 600
```

Nothing on disk when `--out-dir` is absent (FR-017, G-3):

```bash
cd "$TMP" && rm -rf probe && mkdir probe && cd probe
printf 'jane@example.com +14155552671\n' | PYTHONDONTWRITEBYTECODE=1 python3 -B -m logredact >/dev/null
find . -mindepth 1 | head     # expect no output at all
```

## Scenario 7 — Bounds and performance (SR-004, SR-011, SC-009/SC-010)

```bash
cd "$TMP"
python3 -c "print('+'*10000)"            > adv1.log
python3 -c "print('1'*10000)"            > adv2.log
python3 -c "print('+1'*5000)"            > adv3.log
python3 -c "print(('+'+'1'*16)*588)"     > adv4.log
for f in adv1 adv2 adv3 adv4; do /usr/bin/time -f "$f %e s" python3 -m logredact "$f.log" >/dev/null; done
```

Expected: each well under 1 s (SC-010; measured worst case 6.78 ms).

Throughput and bounded memory (SC-009) — 10 MB must redact in under 10 s, to either destination,
with memory bounded by the 1 MiB per-line limit regardless of file count:

```bash
python3 -c "
open('big.log','w').write('user jane@example.com from 10.0.0.7 call +14155552671\n'*200000)"
/usr/bin/time -v python3 -m logredact big.log > /dev/null 2>  time.txt; grep -E 'Elapsed|Maximum resident' time.txt
rm -rf many && mkdir many && for i in $(seq 1 10); do cp big.log many/$i.log; done
/usr/bin/time -v python3 -m logredact --out-dir batch many/*.log 2> time2.txt; grep -E 'Elapsed|Maximum resident' time2.txt
```

An over-long line fails loudly without quoting itself (SR-011):

```bash
python3 -c "open('long.log','w').write('+'+'1'*1048600+'\n')"
python3 -m logredact --out-dir clean long.log; echo "status=$?"   # expect 2, no digits in the message
```

## Scenario 8 — Nothing unredacted reaches disk or the terminal (SR-001, SR-010, SC-012)

After running every scenario above, no prepared sample value may appear in any captured output or
in any file under any output folder:

```bash
cd "$TMP"
grep -rIn -e 'jane@example.com' -e '10\.0\.0\.7' -e '4111' -e '14155552671' -e '442071838750' \
  clean one part jail perms batch reports 2>/dev/null && echo "FAIL: sample value on disk" \
  || echo "SC-012 ok"
```

Expect `SC-012 ok`. (Input files are excluded deliberately — they are the user's own and are opened
read-only.)

## Automated suite

The suite is the authority; the scenarios above are the human-checkable mirror of it.

```bash
cd /path/to/repo
python3 -m pytest -q          # expect: all tests pass, 0 skipped, 0 xfailed
```

Constitution gates to confirm before calling the change complete:

```bash
# Principle I — no third-party runtime import anywhere under src/.
# The second filter drops intra-package relative imports ("from .redact import
# redact_line"), which are the package's own modules and not a dependency.
grep -rnE '^\s*(import|from)\s+' src/ --include='*.py' \
  | grep -vE '^[^:]+:[0-9]+:\s*from\s+\.' \
  | grep -vE '\b(re|os|io|sys|stat|errno|argparse|pathlib)\b' \
  && echo "FAIL: non-stdlib import" || echo "stdlib-only ok"

# Principle III — no skipped or expected-failure tests. Matches the actual
# markers only: the bare words appear throughout these test docstrings, which
# state *why* a case is reached without skipping, and must not count as
# violations. --include='*.py' keeps __pycache__ out of the result.
grep -rnE '@pytest\.mark\.(skipif|skip|xfail)|pytest\.skip\(|pytest\.xfail\(|pytest\.importorskip' \
  tests/ --include='*.py' && echo "FAIL: skip/xfail present" || echo "no skips ok"
```

`pytest -q`'s own summary line is the independent confirmation for Principle III:
it must report neither `skipped` nor `xfailed`.

Clean up: `rm -rf "$TMP"`.
