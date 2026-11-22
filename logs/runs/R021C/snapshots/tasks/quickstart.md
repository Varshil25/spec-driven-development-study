# Quickstart: validating Phone Redaction and Output Folder

**Feature**: `002-phone-redaction-out-dir` | **Date**: 2026-11-20 | **Plan**: [plan.md](./plan.md)

How to run this feature and convince yourself it works. Details that belong elsewhere are linked,
not duplicated: the recognition grammar is in
[contracts/redaction-patterns.md](./contracts/redaction-patterns.md), the command-line surface in
[contracts/cli.md](./contracts/cli.md), and the value representations in
[data-model.md](./data-model.md).

---

## Prerequisites

- CPython 3.11 or newer. Nothing to install: the tool imports only the standard library
  (Constitution Principle I).
- `pytest`, the one permitted development dependency, to run the suite.
- The repository root as the working directory. `src/` reaches the import path through
  `[tool.pytest.ini_options] pythonpath = ["src"]` for tests, and through `PYTHONPATH=src` for
  manual runs.

```bash
cd /path/to/repo
python3 --version          # expect 3.11 or newer
python3 -m pytest --version
```

## Run the full suite

```bash
python3 -m pytest
```

Expected: every test passes. Large-input cases are marked `slow` and deselected by default
(`addopts = ["-m", "not slow"]`); select them explicitly when you want the memory and throughput
criteria measured for real:

```bash
python3 -m pytest -m slow        # SC-018 (1 GB, bounded memory), SC-019 (throughput)
```

## Scenario 1 — a phone number in piped input (US1, FR-032)

```bash
printf 'call +14155552671 now\n' | PYTHONPATH=src python3 -m logredact
```

Expected stdout, byte-exact: `call [PHONE] now` plus a newline. Exit status 0. Nothing on stderr.

Then walk the boundaries — the point of these is that four of the six are *not* redacted:

```bash
printf '+12345678\n+123456789012345\n+1234567\n+1234567890123456\n+٠١٢٣٤٥٦٧٨\n+12345678٩\n' \
  | PYTHONPATH=src python3 -m logredact
```

Expected, line for line:

```text
[PHONE]            # 8 digits, the lower bound
[PHONE]            # 15 digits, the upper bound
+1234567           # 7 digits: too short
+1234567890123456  # 16 digits: no [PHONE] at all (FR-034)
+٠١٢٣٤٥٦٧٨         # not 0-9 digits (FR-033a)
[PHONE]٩           # the foreign digit neither extends nor excludes (FR-033a)
```

## Scenario 2 — the output folder (US2, FR-040 – FR-045)

```bash
rm -rf clean
printf 'user jane@example.com\n' > app.log
printf 'GET / from 10.0.0.7\n'   > web.log
PYTHONPATH=src python3 -m logredact --out-dir clean app.log web.log
echo "exit=$?"
cat clean/app.log clean/web.log
```

Expected: stdout is exactly `wrote 2 files` plus a newline — **no redacted log content on stdout**
— exit 0, and `clean/` holds `app.log` containing `user [EMAIL]` and `web.log` containing
`GET / from [IP]`.

Three variations worth running by hand:

```bash
# Nested creation (FR-042): all three directories appear.
PYTHONPATH=src python3 -m logredact --out-dir reports/clean/today app.log

# Base name only (FR-041): output is clean/app.log, not clean/logs/2026/app.log.
mkdir -p logs/2026 && cp app.log logs/2026/app.log
PYTHONPATH=src python3 -m logredact --out-dir clean logs/2026/app.log

# Replacement, not append (FR-043): the file holds only the redacted input.
printf 'STALE\n' > clean/app.log
PYTHONPATH=src python3 -m logredact --out-dir clean app.log && cat clean/app.log
```

## Scenario 3 — the four-field tally (US3, FR-038)

```bash
printf 'a@b.io +442071838750\n' | PYTHONPATH=src python3 -m logredact --count
```

Expected: stdout `[EMAIL] [PHONE]`, stderr exactly `emails=1 ips=0 cards=0 phones=1`, exit 0.
Redirect the streams separately to see the ordering guarantee (FR-024, FR-046): with `--out-dir`
the summary line reaches stdout before the tally reaches stderr.

```bash
PYTHONPATH=src python3 -m logredact --count --out-dir clean app.log 1>out.txt 2>err.txt
cat out.txt   # wrote 1 files      <- literal; not pluralised for N=1 (FR-045)
cat err.txt   # emails=1 ips=0 cards=0 phones=0
```

## Scenario 4 — the failure paths (US4, FR-047 – FR-050)

Each of these must produce a diagnostic naming the offending path or conflict, **no**
`wrote N files` line, no tally even with `--count`, no traceback, and exit status 2.

```bash
# No FILE operand: stdin is not read and `clean2` is not created (FR-047).
rm -rf clean2
printf 'x\n' | PYTHONPATH=src python3 -m logredact --out-dir clean2; echo "exit=$?"; ls clean2

# Unreadable FILE: `clean` is created but stays empty (FR-050, US4.1).
rm -rf clean
PYTHONPATH=src python3 -m logredact --out-dir clean missing.log; echo "exit=$?"; ls -A clean

# DIR exists as a regular file (FR-048, US4.5).
: > notadir
PYTHONPATH=src python3 -m logredact --out-dir notadir app.log; echo "exit=$?"

# Output path is its own input file (FR-049). app.log must be untouched afterwards.
cp app.log app.log.bak
PYTHONPATH=src python3 -m logredact --out-dir . app.log; echo "exit=$?"
diff app.log app.log.bak && echo "input intact"

# Same file, different spelling (FR-049a, US4.7a).
PYTHONPATH=src python3 -m logredact --out-dir ./logs/2026 logs/2026/app.log; echo "exit=$?"

# --out-dir with no value: argparse usage to stderr (FR-040).
PYTHONPATH=src python3 -m logredact --out-dir; echo "exit=$?"

# Help wins over everything, and creates nothing (FR-051).
rm -rf clean3
PYTHONPATH=src python3 -m logredact --help --out-dir clean3; echo "exit=$?"; ls clean3
```

The last one must print usage text **documenting `--out-dir`** on stdout, write nothing to stderr,
leave `clean3` nonexistent, and exit 0.

## Scenario 5 — nothing else changed (FR-052, FR-053, SC-012, SC-013)

The honest check is to run the feature-001 suite and see what moves:

```bash
python3 -m pytest tests/test_cli.py tests/test_redact.py tests/test_fidelity.py
```

Expected: the only assertions that needed editing for this feature are the ones on the tally
line, which gained a `phones=N` field. Any other feature-001 failure is a regression, not a
documented difference. Then confirm the no-`+` corpus is byte-identical:

```bash
PYTHONPATH=src python3 -m logredact tests/fixtures/no_plus.log > after.bin
# compare against output captured from the pre-feature tool
cmp before.bin after.bin && echo "byte-identical (SC-013)"
```

## Scenario 6 — fidelity of output files (FR-044, SC-014)

For each of three awkward inputs — CRLF endings, a missing final newline, and bytes that are not
valid UTF-8 — the output file must equal the stdout of the same tool on the same single file:

```bash
for f in crlf.log no_final_nl.log invalid_utf8.log; do
  PYTHONPATH=src python3 -m logredact "$f" > "expected_$f"
  PYTHONPATH=src python3 -m logredact --out-dir outdir "$f" >/dev/null
  cmp "expected_$f" "outdir/$f" && echo "$f: identical"
done
```

---

## Requirement-to-test matrix

Constitution Principle III requires this mapping to be explicit, and SC-015 makes it measurable.
`tests/test_requirement_coverage.py` enforces it mechanically: it fails the suite if any
identifier below loses its last citing test, so this table and the suite cannot drift.

**25 functional requirements** — FR-032 through FR-054 plus the lettered additions FR-033a and
FR-049a — and **10 success criteria**, SC-010 through SC-019.

| Requirement | Covered by | Shape |
|---|---|---|
| FR-032 phone → `[PHONE]` | `tests/test_phone.py` | unit on `redact_line` |
| FR-033 `+` and 8–15 digits | `tests/test_phone.py` | unit, both bounds and both rejections |
| FR-033a digits are `0`–`9` only | `tests/test_phone.py` | unit, Arabic-Indic in and after a candidate |
| FR-034 followed-by-a-digit exclusion | `tests/test_phone.py` | unit, 16 digits and `+4111111111111111` → `+[CARD]` |
| FR-035 single-claim rule | `tests/test_phone.py` | unit, all four categories on one line |
| FR-036 precedence email → ip → card → phone | `tests/test_phone.py` | unit, `+…@example.com` and `+4111111111119` |
| FR-037 no re-examination, literal `[PHONE]` | `tests/test_phone.py` | unit, uncounted pass-through |
| FR-038 four-field tally form | `tests/test_cli.py` | subprocess, byte-exact stderr |
| FR-039 `phones` counts like the rest | `tests/test_cli.py` | subprocess, three phones over two files |
| FR-040 `--out-dir DIR` accepted anywhere; missing value is usage | `tests/test_out_dir.py` | subprocess, four argument orders + no value |
| FR-041 base name, not stdout | `tests/test_out_dir.py` | subprocess, `logs/2026/app.log` |
| FR-042 `DIR` and parents created | `tests/test_out_dir.py` | subprocess, `reports/clean/today` |
| FR-043 replaced, not appended | `tests/test_out_dir.py` | subprocess, pre-existing file + duplicate base names |
| FR-044 output bytes equal stdout bytes | `tests/test_fidelity.py` | subprocess, CRLF / no final NL / invalid UTF-8 |
| FR-045 `wrote N files`, stdout only | `tests/test_out_dir.py` | subprocess, byte-exact stdout, `N=1` literal |
| FR-046 tally after summary | `tests/test_out_dir.py` | subprocess, separate stream redirection |
| FR-047 `--out-dir` without FILE | `tests/test_out_dir.py` | subprocess, asserts stdin unread and `DIR` absent |
| FR-048 `DIR` or output file unusable | `tests/test_out_dir.py` | subprocess, three shape-based fixtures (research R-113) |
| FR-049 output path is its input | `tests/test_out_dir.py` | subprocess, `--out-dir .`, input unmodified |
| FR-049a identity, not path text | `tests/test_out_dir.py` | subprocess, `./logs` spelling, symlink, hard link, nonexistent path accepted |
| FR-050 unreadable FILE under `--out-dir` | `tests/test_out_dir.py` | subprocess, earlier output intact, no summary, no tally |
| FR-051 `--help` with `--out-dir` | `tests/test_out_dir.py` | subprocess, usage mentions `--out-dir`, `DIR` absent, stderr empty |
| FR-052 stdout path unchanged | `tests/test_preservation.py` | subprocess, replays feature-001 stdout behaviour |
| FR-053 no-`+` input unchanged | `tests/test_preservation.py` | subprocess, byte-identity over a no-`+` corpus |
| FR-054 order of checks | `tests/test_out_dir.py` | subprocess, three-operand collision leaves no output file |

| Criterion | Covered by |
|---|---|
| SC-010 three worked examples reproduce byte-exactly | `tests/test_out_dir.py`, `tests/test_cli.py` |
| SC-011 50-line fixture: 100% of planted phones, 0% of look-alikes | `tests/test_phone.py` |
| SC-012 the differing input shapes are exactly two, demonstrated | `tests/test_preservation.py` (+ the replay in Scenario 5) |
| SC-013 no-`+` corpus byte-identical | `tests/test_preservation.py` |
| SC-014 three awkward files, output file == stdout | `tests/test_fidelity.py` |
| SC-015 every new FR has a citing test | `tests/test_requirement_coverage.py` |
| SC-016 every new failure path: diagnostic + exit 2 + no traceback | `tests/test_out_dir.py` |
| SC-017 `wrote N files` only on exit 0 | `tests/test_out_dir.py` |
| SC-018 bounded memory on ≥ 1 GB across operands | `tests/test_performance.py` (`slow`) |
| SC-019 100,000 lines under 30 s across operands | `tests/test_performance.py` (`slow`) |

## Constitution quality gates

Run before declaring the feature complete. These are the constitution's four verification gates,
not advice.

```bash
python3 -m pytest                                  # gate 1: the full suite passes
python3 -m pytest tests/test_requirement_coverage.py  # gate 2: every FR has a citing test
python3 -m pytest tests/test_stdlib_only.py           # gate 3: no third-party import in src/
python3 -m pytest tests/test_out_dir.py -k "error or cannot or usage or overwrite"  # gate 4
```

Gate 4's cases each assert three things: the diagnostic names the offending path or conflict, the
exit status is 2, and `Traceback` does not appear on stderr.
