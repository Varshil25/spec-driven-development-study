# Quickstart: validating the Log Data Redaction CLI

**Feature**: 001-log-data-redaction-cli | **Date**: 2026-11-21

Runnable scenarios that prove the feature works end to end. Each maps to user stories and success
criteria in [spec.md](./spec.md). The full interface is in [contracts/cli.md](./contracts/cli.md);
recognition rules are in [contracts/redaction-rules.md](./contracts/redaction-rules.md).

This is a validation guide, not an implementation guide — no implementation code appears here.

---

## Prerequisites

- CPython **3.11 or newer** (`python3 --version`)
- `pytest` for the automated suite (developer tooling only; never imported by shipped code)
- No other installation: the tool itself imports only the standard library (FR-015)
- No network access is needed or used

All commands run from the repository root. `src/` must be on the module search path (FR-001):

```bash
export PYTHONPATH=src
```

---

## Scenario 1 — Redact a stream (US1, P1, SC-001/SC-002/SC-003)

```bash
printf 'user jane@example.com from 10.0.0.7\n' | python -m logredact
```

Expected stdout, exactly:

```text
user [EMAIL] from [IP]
```

Exit status 0, stderr empty (FR-011).

More of the same scenario, each run as `printf '…' | python -m logredact`:

| Input | Expected stdout |
|---|---|
| `paid with 4111 1111 1111 1111, ref 1234567890123` | `paid with [CARD], ref 1234567890123` |
| `jane.doe+test@mail.example.com logged in` | `[EMAIL] logged in` |
| `hit 999.1.1.1 today` | unchanged |
| `a@1.2.3.4` | `a@[IP]` |
| `4111 1111 1111 1111 1234` | `[CARD] 1234` |
| `over 1.2.3.4.5 here` | unchanged |
| `zero 010.0.0.7 ok` | `zero [IP] ok` |
| `4111-1111 1111-1111` | `[CARD]` |
| `4111  1111 1111 1111` | unchanged |
| `12345678903@example.com` | `[EMAIL]` |

**No trailing newline added** (US1-6) — the byte counts must match:

```bash
printf 'no newline jane@example.com' | python -m logredact | xxd | tail -1
```

The output must end with `...[EMAIL]` and no `0a` byte.

**Nothing else changed** (SC-003) — diff a log against its redaction and confirm every differing
line differs only by placeholders:

```bash
python -m logredact sample.log > redacted.log
diff sample.log redacted.log
```

---

## Scenario 2 — Named files in order (US2, P2)

```bash
printf 'from a jane@example.com\n' > /tmp/a.log
printf 'from b 10.0.0.7\n'        > /tmp/b.log
: > /tmp/empty.log

python -m logredact /tmp/a.log /tmp/b.log     # a's lines, then b's
python -m logredact /tmp/b.log /tmp/a.log     # order reverses
python -m logredact /tmp/a.log /tmp/a.log     # content emitted twice
python -m logredact /tmp/empty.log            # empty stdout, status 0
```

**stdin is not read when FILEs are given** (US2-5) — this must terminate immediately and never
block, and `SHOULD NOT APPEAR` must be absent from the output:

```bash
printf 'SHOULD NOT APPEAR\n' | python -m logredact /tmp/a.log
```

---

## Scenario 3 — Counts on stderr (US3, P3, SC-004/SC-005)

```bash
printf 'a@b.io 1.2.3.4\n' | python -m logredact --count >/tmp/out.txt 2>/tmp/err.txt
cat /tmp/out.txt   # [EMAIL] [IP]
cat /tmp/err.txt   # emails=1 ips=1 cards=0
```

| Run | Expected stderr |
|---|---|
| `--count` on input with no redactable values | `emails=0 ips=0 cards=0` |
| `--count` with empty input | `emails=0 ips=0 cards=0` |
| no `--count`, successful run | *empty* |

**Flag position is free** (FR-012) — all three must produce identical output and counts:

```bash
python -m logredact --count /tmp/a.log /tmp/b.log
python -m logredact /tmp/a.log --count /tmp/b.log
python -m logredact /tmp/a.log /tmp/b.log --count
```

**Stream separation** (SC-005): `/tmp/out.txt` must contain no `emails=` text and `/tmp/err.txt`
must contain no log text. Counts are **replacement** counts — a value repeated on one line counts
once per occurrence (US3-3).

---

## Scenario 4 — Unreadable input fails loudly (US4, P3, SC-006)

```bash
python -m logredact /tmp/does-not-exist.log ; echo "status=$?"   # status=2
python -m logredact /tmp                     ; echo "status=$?"   # directory → status=2
python -m logredact --bogus                  ; echo "status=$?"   # usage error → status=2
```

Each must write a diagnostic naming the problem to stderr and exit **2**. No case exits 0.

**Partial output is kept, then the run stops** (US4-4):

```bash
python -m logredact /tmp/a.log /tmp/does-not-exist.log >/tmp/out.txt 2>/tmp/err.txt
echo "status=$?"          # 2
cat /tmp/out.txt          # a.log's redacted content, already written
cat /tmp/err.txt          # names /tmp/does-not-exist.log
```

**No summary on failure** (US4-5) — `/tmp/err.txt` must contain no `emails=` text:

```bash
python -m logredact --count /tmp/does-not-exist.log 2>&1 | grep -c 'emails=' ; echo "expect 0"
```

Permission-denied (US4-2) is covered by the automated suite rather than by a shell command here:
the development environment runs as root, where `chmod 000` does not prevent reading. The suite
injects a `PermissionError` at the open call so the assertion is deterministic on any uid — see
[research.md](./research.md) D-008.

---

## Scenario 5 — Non-UTF-8 bytes round-trip (FR-017)

```bash
printf 'caf\xe9 jane@example.com \xff\xfe 10.0.0.7\n' > /tmp/mixed.log
python -m logredact /tmp/mixed.log | xxd
```

The `e9`, `ff`, and `fe` bytes must appear **unchanged** — no `efbfbd` (U+FFFD) substitution, no
error, status 0.

---

## Scenario 6 — Bounds and performance (SR-005, SC-007, SC-008)

**Over-long line fails loudly** — one line above 1 MiB:

```bash
python - <<'EOF'
open("/tmp/toolong.log", "w").write("x" * (1024 * 1024 + 10) + "\n")
EOF
python -m logredact /tmp/toolong.log ; echo "status=$?"   # status=2
```

stderr must name the input source, state the limit, and **not quote the line** (SR-001).

**Throughput** (SC-007) — a 10 MB log must redact in under 10 seconds; the design measures ~1.9 s:

```bash
python - <<'EOF'
line = "2026-11-21T10:00:00 INFO user jane.doe@example.com from 10.0.0.7 paid 4111 1111 1111 1111 ok\n"
open("/tmp/big.log", "w").writelines([line] * 100000)
EOF
time python -m logredact /tmp/big.log > /dev/null
```

**Bounded memory** — a far larger input must not grow memory; peak stays bounded by the per-line
limit:

```bash
yes 'user jane@example.com from 10.0.0.7' | head -c 200000000 | /usr/bin/time -v python -m logredact > /dev/null
```

**No catastrophic backtracking** (SC-008) — each adversarial 10 000-character line must finish well
under 1 second; measured worst case is 117 ms:

```bash
python - <<'EOF'
lines = ("9" * 10000, "1 " * 5000, "a." * 2500 + "@" + "a." * 2500, "1." * 5000, "a" * 10000 + "@")
open("/tmp/adversarial.log", "w").write("\n".join(lines) + "\n")
EOF
time python -m logredact /tmp/adversarial.log > /dev/null
```

---

## Scenario 7 — No artifacts on disk (SR-008)

```bash
cd "$(mktemp -d)" && printf 'jane@example.com\n' > in.log
PYTHONPATH=/path/to/repo/src python -B -m logredact in.log > /dev/null
ls -a    # only . .. in.log — nothing created
```

`-B` suppresses CPython's own bytecode cache so the assertion is about the tool's behaviour, not the
interpreter's (research.md D-009). The input file's mtime must be unchanged and it must still
contain the original unredacted value — the tool opens it read-only.

---

## Automated suite

```bash
pytest                 # pythonpath=src comes from pyproject.toml
pytest -q --tb=short
```

**Gate** (Constitution Principles III and V, SC-009): the suite must pass with **no skipped and no
expected-failure tests**, and every functional and security requirement must map to at least one
test. The requirement-to-test mapping is recorded in [plan.md](./plan.md).

Confirm the suite leaks nothing (SC-010):

```bash
pytest -q 2>&1 | grep -E 'jane@example\.com|4111 ?1111|10\.0\.0\.7' ; echo "expect no matches"
```

Confirm no third-party runtime import crept in (FR-015, Principle I):

```bash
grep -rnE '^\s*(import|from)\s+' src/ | grep -vE ':\s*from \.' \
  | grep -vE '\b(re|sys|os|io|argparse|typing)\b' ; echo "expect no matches"
```

The `grep -vE ':\s*from \.'` filter drops the package's **own** relative imports
(`from .redact import redact_line`, `from .cli import main`). They are not third-party imports, but
the allowlist alternation does not match them either — `\bre\b` does not match `redact` — so without
this filter the gate reports them and can never pass. The authoritative check is
`test_every_runtime_import_is_standard_library` in `tests/test_security.py`, which parses each module
with `ast`, skips relative imports, and asserts every absolute import is in
`sys.stdlib_module_names`. Observed absolute imports: `argparse`, `os`, `re`, `sys` — a subset of the
planned set.
