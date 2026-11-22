# Quickstart & Validation Guide: `logredact`

**Feature**: `001-logredact-cli` | **Date**: 2026-11-20 | **Plan**: [plan.md](./plan.md)

How to run the tool and how to prove it works end to end. Behavioural details are not repeated
here — see [contracts/cli.md](./contracts/cli.md) for the command-line contract,
[contracts/redaction-patterns.md](./contracts/redaction-patterns.md) for the recognition grammar,
and [data-model.md](./data-model.md) for the entities.

---

## Prerequisites

- CPython 3.11 or newer (`python3 --version`)
- `pytest` for the test suite — the only development dependency
- Nothing to install for the tool itself: no `pip install`, no build step, no third-party runtime
  package

```bash
cd <repo root>
python3 --version
python3 -m pytest --version
```

## Running the tool

`src/` must be on `PYTHONPATH`; the package is not installed.

```bash
# From a pipe
printf 'user jane@example.com from 10.0.0.7\n' | PYTHONPATH=src python3 -m logredact

# From files, in order, with a tally
PYTHONPATH=src python3 -m logredact --count a.log b.log

# Keep the log and the tally apart
PYTHONPATH=src python3 -m logredact --count app.log > clean.log 2> tally.txt

# Usage
PYTHONPATH=src python3 -m logredact --help
```

## Running the test suite

Discoverable from the repository root with no arguments (`pythonpath` and `testpaths` come from
`pyproject.toml`).

```bash
python3 -m pytest                 # full default suite; must be green
python3 -m pytest -m slow         # the large-input cases, deselected by default
python3 -m pytest tests/test_redact.py -q    # recognition rules only, fast
```

---

## Validation scenarios

Each scenario is a runnable check with a stated expected outcome, and each has an automated
counterpart in the suite. Byte-exactness matters: compare with `cmp`/`diff` or inspect with
`od -c` rather than eyeballing terminal output.

### V1 — Story 1: the three worked examples reproduce byte-exactly (SC-001)

```bash
printf 'user jane@example.com from 10.0.0.7\n' | PYTHONPATH=src python3 -m logredact; echo "exit=$?"
printf 'paid with 4111 1111 1111 1111, ref 1234567890123\n' | PYTHONPATH=src python3 -m logredact; echo "exit=$?"
printf 'a@b.io 1.2.3.4\n' | PYTHONPATH=src python3 -m logredact --count; echo "exit=$?"
```

Expected, in order: `user [EMAIL] from [IP]` / `paid with [CARD], ref 1234567890123` /
`[EMAIL] [IP]` on stdout with `emails=1 ips=1 cards=0` on stderr. Exit 0 each time. Note the
second line: the grouped card is redacted and the Luhn-failing 13-digit number is not.

### V2 — Pass-through is byte-identical when there is nothing to redact (SC-003)

```bash
printf 'plain line\r\nbare\rCR text\n\n   \nno trailing newline' > /tmp/fidelity.log
printf 'raw byte: \xff here\n' >> /tmp/fidelity.log
PYTHONPATH=src python3 -m logredact /tmp/fidelity.log > /tmp/fidelity.out
cmp /tmp/fidelity.log /tmp/fidelity.out && echo IDENTICAL
```

Expected: `IDENTICAL`, exit 0. This one check covers CRLF preservation, a bare `\r` not acting as
a line break, blank and whitespace-only lines, a missing final newline, and an undecodable byte.

### V3 — Redaction works around an undecodable byte (FR-005a)

```bash
printf 'mail \xff jane@example.com\n' | PYTHONPATH=src python3 -m logredact | od -c | head -2
```

Expected: the `\xff` byte appears unchanged, the address is `[EMAIL]`, exit 0, and with `--count`
the byte contributes nothing to the tally.

### V4 — Story 2: several files concatenate in command-line order (FR-003, FR-004)

```bash
printf 'first 1.1.1.1\n' > /tmp/a.log
printf 'second a@b.io\n' > /tmp/b.log
PYTHONPATH=src python3 -m logredact /tmp/a.log /tmp/b.log
PYTHONPATH=src python3 -m logredact /tmp/b.log /tmp/a.log       # order follows the operands
PYTHONPATH=src python3 -m logredact /tmp/a.log --count /tmp/b.log   # flag position is free
```

Expected: `first [IP]` then `second [EMAIL]` for the first command, reversed for the second, and
the third behaves as the first plus `emails=1 ips=1 cards=0` on stderr. Exit 0 throughout.

### V5 — Story 3: the tally is accurate, ordered, and quiet without the flag (FR-023–FR-026, SC-008)

```bash
printf 'a@b.io c@d.io e@f.io 1.2.3.4\n' | PYTHONPATH=src python3 -m logredact --count
printf 'nothing here\n' | PYTHONPATH=src python3 -m logredact --count
printf 'a@b.io\n' | PYTHONPATH=src python3 -m logredact 2>&1 1>/dev/null | wc -c
```

Expected: `emails=3 ips=1 cards=0`; then `emails=0 ips=0 cards=0`; then `0` bytes of stderr. The
tally always arrives after the full log, so the redirected-streams form in "Running the tool"
yields a complete `clean.log` before `tally.txt` is written.

### V6 — Story 4: an unreadable file is named, and fails the run (FR-028, FR-029, SC-005)

```bash
PYTHONPATH=src python3 -m logredact /tmp/a.log /tmp/does-not-exist.log; echo "exit=$?"
install -m 000 /dev/null /tmp/denied.log
PYTHONPATH=src python3 -m logredact --count /tmp/denied.log; echo "exit=$?"
```

Expected: the first prints `first [IP]` on stdout (the readable file's output stays written),
names `/tmp/does-not-exist.log` on stderr, and exits 2. The second names `/tmp/denied.log`,
writes **no** tally despite `--count`, and exits 2. Neither stderr contains `Traceback`. Run the
permission case as a non-root user — root can read a mode-000 file.

### V7 — Invalid usage and help (FR-030, FR-030a)

```bash
PYTHONPATH=src python3 -m logredact --nope; echo "exit=$?"
PYTHONPATH=src python3 -m logredact --help 2>/tmp/help.err; echo "exit=$?"; wc -c < /tmp/help.err
PYTHONPATH=src python3 -m logredact --help --count /tmp/does-not-exist.log; echo "exit=$?"
```

Expected: usage on stderr and exit 2 for `--nope`; usage on stdout, `0` bytes of stderr, and exit
0 for `--help`. The third shows a help request wins over everything: usage on stdout, no tally,
the nonexistent file never opened, exit 0.

### V8 — A reader that stops early is a failure, not a success (FR-031a)

```bash
seq 1 200000 | sed 's/$/ a@b.io/' > /tmp/big.log      # large enough that the pipe closes mid-run
PYTHONPATH=src python3 -m logredact /tmp/big.log | head -1; echo "exit=${PIPESTATUS[0]}"
```

Expected: `1 [EMAIL]` on stdout, one concise diagnostic on stderr with no `Traceback`, and
`exit=2` from the tool — never 0, so a truncated redacted log cannot be mistaken for a complete
one (SC-009). `PIPESTATUS` is a bash/zsh feature; under another shell, use `set -o pipefail` and
read `$?`.

### V9 — Look-alikes survive untouched (SC-002)

```bash
printf '999.1.1.1 256.1.1.1 1.2.3.4.5 1.2.3.45678 1.2.3 1234567890123 123456789012\n' \
  | PYTHONPATH=src python3 -m logredact --count
printf '99 4111 1111 1111 1111\n' | PYTHONPATH=src python3 -m logredact
printf '4111  1111  1111  1111\n' | PYTHONPATH=src python3 -m logredact
python3 -c "print('9'*25)" | PYTHONPATH=src python3 -m logredact
printf 'admin@1.2.3.4 [EMAIL] [IP] [CARD]\n' | PYTHONPATH=src python3 -m logredact --count
```

Expected: the first line is echoed unchanged with `emails=0 ips=0 cards=0`; `99 [CARD]`;
the doubled-space card unchanged; the 25-digit run unchanged in full; and
`[EMAIL] [EMAIL] [IP] [CARD]` with `emails=1 ips=0 cards=0` — the pre-existing placeholders are
passed through and uncounted, and `admin@1.2.3.4` is one `[EMAIL]` (see the amendment note in
[contracts/redaction-patterns.md](./contracts/redaction-patterns.md)).

### V10 — Large inputs stay bounded (SC-006, SC-007)

```bash
python3 -c "print('x '*5_000_000 + 'a@b.io')" > /tmp/longline.log   # ~10 MB, one line
/usr/bin/time -v PYTHONPATH=src python3 -m logredact /tmp/longline.log > /dev/null
seq 1 100000 | sed 's/$/ jane@example.com 10.0.0.7 4111 1111 1111 1111/' > /tmp/100k.log
time PYTHONPATH=src python3 -m logredact --count /tmp/100k.log > /dev/null
```

Expected: the 10 MB single line is redacted with peak RSS on the order of the line, not a
multiple of it; the 100,000-line run finishes well under 30 s. Peak RSS stays flat as the input
grows in line count — that flatness, not a 1 GB run, is what the default suite asserts; see
research item R-008 for why the 1 GB figure is reached by extrapolation and which `slow`-marked
test exercises the large case directly.

---

## Requirement-to-test mapping

Principle III requires every functional requirement to cite a test. Each test below names its
identifier in its function name or docstring.

| Requirement | Test location |
|---|---|
| FR-001 flags and operands in any order | `test_cli.py::test_fr001_*` |
| FR-002 stdin when no operand | `test_cli.py::test_fr002_*` |
| FR-003 operand order, stdin not read | `test_cli.py::test_fr003_*` |
| FR-004 single concatenated stream | `test_cli.py::test_fr004_*` |
| FR-005 non-match pass-through | `test_redact.py::test_fr005_*` |
| FR-005a undecodable bytes | `test_cli.py::test_fr005a_*`, `test_fidelity.py` |
| FR-006 untouched line reproduced exactly | `test_redact.py::test_fr006_*` |
| FR-007 line terminators, bare `\r` | `test_cli.py::test_fr007_*`, `test_fidelity.py` |
| FR-007a final newline presence | `test_cli.py::test_fr007a_*` |
| FR-008, FR-009, FR-010 email | `test_redact.py::test_fr008_*`, `test_fr009_*`, `test_fr010_*` |
| FR-011, FR-012, FR-013, FR-014 IPv4 | `test_redact.py::test_fr011_*` … `test_fr014_*` |
| FR-015, FR-016, FR-017 card shape and Luhn | `test_redact.py::test_fr015_*` … `test_fr017_*` |
| FR-018 digit-run flanking, 20+ run never a card | `test_redact.py::test_fr018_*` |
| FR-019 longest valid at a start | `test_redact.py::test_fr019_*` |
| FR-019a rejection does not hide a later match | `test_redact.py::test_fr019a_*` |
| FR-020 no overlap or nesting | `test_redact.py::test_fr020_*` |
| FR-021 precedence (incl. `admin@1.2.3.4`) | `test_redact.py::test_fr021_*` |
| FR-022 placeholders not rescanned or counted | `test_redact.py::test_fr022_*` |
| FR-023, FR-024, FR-025, FR-026 tally | `test_cli.py::test_fr023_*` … `test_fr026_*` |
| FR-027 exit 0 on full success | `test_cli.py::test_fr027_*` |
| FR-028 unreadable file named, exit 2 | `test_cli.py::test_fr028_*` |
| FR-029 stop reading, no tally | `test_cli.py::test_fr029_*` |
| FR-030 invalid usage | `test_cli.py::test_fr030_*` |
| FR-030a `--help` / `-h` | `test_cli.py::test_fr030a_*` |
| FR-031 stream discipline | `test_cli.py::test_fr031_*` |
| FR-031a failed write | `test_cli.py::test_fr031a_*` |
| SC-001 worked examples byte-exact | `test_cli.py::test_sc001_*` |
| SC-002 200-line mixed fixture | `test_fidelity.py::test_sc002_*` |
| SC-003 byte-identical pass-through | `test_fidelity.py::test_sc003_*` |
| SC-004 every FR cited | this table plus `test_stdlib_only.py` gate review |
| SC-005 failure paths, no traceback | `test_cli.py::test_sc005_*` |
| SC-006 bounded memory | `test_performance.py::test_sc006_*` (`slow` for the largest case) |
| SC-007 100k lines under 30 s | `test_performance.py::test_sc007_*` |
| SC-008 tally equals placeholder count | `test_fidelity.py::test_sc008_*` |
| SC-009 success distinguishable by status | `test_cli.py::test_sc009_*` |
| Principle I no third-party runtime import | `test_stdlib_only.py` |

## Definition of done

From the constitution's quality gates — all four must hold before the feature is reported
complete:

1. `python3 -m pytest` from the repository root is green.
2. Every functional requirement above has at least one citing test.
3. No third-party import appears in `src/` (asserted by `test_stdlib_only.py`).
4. Every invalid-input path — missing file, unreadable file, invalid usage, failed write — has a
   test asserting both its diagnostic and its exit status 2.
