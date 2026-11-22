# Phase 1 Quickstart: Validating the Log Redaction CLI

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Contract**:
[contracts/cli.md](./contracts/cli.md)

How to run the tool and prove it works end to end. This is a validation guide, not an
implementation guide — it contains no module bodies or test suites; those belong to
`/speckit-tasks` and the implementation phase.

## Prerequisites

- Python **3.11 or newer** (`python3 -VV`). This environment has 3.13.17.
- `pytest` **7 or newer**, for the built-in `pythonpath` setting. This environment has 9.1.1.
- No other installation step: the tool has no runtime dependencies (Constitution principle I), so
  there is nothing to `pip install` for running it.

## Run it

`src/` must be on `PYTHONPATH`, which is what makes `python -m logredact` resolve:

```bash
cd <repo root>
export PYTHONPATH=src
```

Then any of:

```bash
# stdin
echo 'user jane@example.com from 10.0.0.7' | python3 -m logredact

# named files, in order, one sanitised stream out
python3 -m logredact a.log b.log > safe-to-attach.log

# with the tally, captured separately from the data
python3 -m logredact --count a.log > safe.log 2> tally.txt
```

## Run the tests

From the repository root, with no plugins or services (Constitution principle III):

```bash
python3 -m pytest          # or: pytest
```

`pyproject.toml` sets `pythonpath = ["src"]` under `[tool.pytest.ini_options]`, so tests import
`logredact` without an install step or a `conftest.py` path hack.

---

## Scenario 1 — Core redaction on a piped stream (User Story 1, P1)

Proves the three rules fire together and everything else survives untouched.

```bash
printf 'user jane@example.com from 10.0.0.7\npaid with 4111 1111 1111 1111, ref 1234567890123\nGET /health 200 in 4ms\n' \
  | python3 -m logredact
```

**Expected** — exit status `0`, stderr empty, stdout exactly:

```text
user [EMAIL] from [IP]
paid with [CARD], ref 1234567890123
GET /health 200 in 4ms
```

Line 2 is the discriminating one: the grouped Luhn-valid number is replaced by a single
`[CARD]` including its spaces, while the Luhn-invalid 13-digit `1234567890123` is left alone.

**Also check** (one line each, all must come back unchanged): `999.1.1.1`, `1.2.3.4.5`,
`jane@localhost`, `4111  1111 1111 1111` (double space), `11111111111111111111` (20 digits). And
`connect to 192.168.0.10.` → `connect to [IP].`, keeping the sentence period.

**Empty input**: `printf '' | python3 -m logredact` → empty stdout, exit `0`.

## Scenario 2 — Named files in argument order (User Story 2, P2)

```bash
printf 'first a@b.io\n'  > /tmp/a.log
printf 'second 1.2.3.4'  > /tmp/b.log     # note: no trailing newline
python3 -m logredact /tmp/a.log /tmp/b.log | od -c | tail -3
```

**Expected** — `first [EMAIL]\nsecond [IP]` with **no** newline after `[IP]`: the missing
terminator is preserved, not invented (FR-006). Reverse the two arguments and the output order
reverses with them. Pass `/tmp/a.log` twice and its content appears twice.

**Stdin is ignored when files are given**:

```bash
echo 'LEAK x@y.io' | python3 -m logredact /tmp/a.log
```

**Expected** — `first [EMAIL]` only. The string `LEAK` must not appear anywhere in stdout.

## Scenario 3 — The tally (User Story 3, P3)

```bash
echo 'a@b.io 1.2.3.4' | python3 -m logredact --count > /tmp/out.txt 2> /tmp/err.txt
cat /tmp/out.txt   # [EMAIL] [IP]
cat /tmp/err.txt   # emails=1 ips=1 cards=0
```

**Expected** — exit `0`; the tally is on stderr only, so redirecting stdout alone never
contaminates the sanitised data.

**Occurrences, not distinct values**:

```bash
echo 'a@b.io a@b.io a@b.io' | python3 -m logredact --count 2>&1 >/dev/null
# emails=3 ips=0 cards=0
```

**One tally for all files combined**, and `--count` works in any position (FR-001):

```bash
python3 -m logredact /tmp/a.log --count /tmp/b.log 2>&1 >/dev/null
# emails=1 ips=1 cards=0   — a single line, after all output
```

That interspersed form is the case plain `argparse` gets wrong (research D-007), so it is worth
running by hand even once the suite is green.

**No flag, no stderr**: `echo 'a@b.io' | python3 -m logredact 2>/tmp/err.txt` leaves
`/tmp/err.txt` empty (FR-021).

## Scenario 4 — Unreadable input fails loudly (User Story 4, P3)

```bash
python3 -m logredact /tmp/nope.log; echo "status=$?"
```

**Expected** — stdout empty; stderr names the path, e.g.
`logredact: /tmp/nope.log: No such file or directory`; `status=2`.

**Mid-list failure, with `--count`** — the case that must not look like success:

```bash
python3 -m logredact /tmp/a.log /tmp/nope.log --count > /tmp/out.txt 2> /tmp/err.txt
echo "status=$?"
```

**Expected** — `/tmp/out.txt` holds the redacted `/tmp/a.log` (already written, not retracted);
`/tmp/err.txt` names `/tmp/nope.log` and contains **no** tally line; `status=2`.

**Failure before a readable file** — processing stops at the first failure:

```bash
python3 -m logredact /tmp/nope.log /tmp/b.log; echo "status=$?"
```

**Expected** — nothing from `/tmp/b.log` on stdout; `status=2`.

**Directory, permission denied, undecodable bytes** — all three are read failures:

```bash
python3 -m logredact /tmp; echo "status=$?"                      # Is a directory
printf 'x' > /tmp/no.log && chmod 000 /tmp/no.log
python3 -m logredact /tmp/no.log; echo "status=$?"               # Permission denied
printf '\xff\xfe\x00bad' > /tmp/bin.log
python3 -m logredact /tmp/bin.log; echo "status=$?"              # invalid start byte
```

Each names the path on stderr and exits `2`.

**Unrecognised option**:

```bash
python3 -m logredact --verbose /tmp/a.log; echo "status=$?"
```

**Expected** — usage line plus `logredact: unrecognized option: --verbose` on stderr, stdout
empty, `status=2`, and `/tmp/a.log` never opened.

## Scenario 5 — Streaming limits (SC-006) and a closed pipe

```bash
python3 -c "
open('/tmp/big.log','w').write(''.join(
  f'{i} user{i}@ex.com 10.0.{i%256}.1 card 4111 1111 1111 1111\n' for i in range(100000)))"

time python3 -m logredact /tmp/big.log --count > /dev/null
```

**Expected** — `emails=100000 ips=100000 cards=100000` and well under 10 seconds (the Phase 0
probe measured 1.40 s on this shape of input; see research.md).

```bash
python3 -m logredact /tmp/big.log | head -2; echo "status=${PIPESTATUS[0]}"
```

**Expected** — two lines, empty stderr, `status=141`. Any traceback here is a defect
(research D-010).

**Very long line** — a 1 MB single line passes through without truncation and memory stays flat:

```bash
python3 -c "print('x'*1000000 + ' a@b.io')" | python3 -m logredact | wc -c
# 1000009  (1000000 x's + ' ' + '[EMAIL]' + '\n')
```

---

## Requirement → test map (SC-004)

Every FR maps to at least one named test, and each test id carries the requirement it verifies,
as Constitution principle III requires. `test_redact.py` exercises the engine directly;
`test_cli.py` runs the real command in a subprocess via the `run_cli()` helper in `conftest.py`.

| Requirement | Test file | Test id |
|---|---|---|
| FR-001 | `test_cli.py` | `test_fr001_count_flag_accepted_before_between_and_after_files` |
| FR-002 | `test_cli.py` | `test_fr002_reads_stdin_when_no_file_given` |
| FR-003 | `test_cli.py` | `test_fr003_reads_files_in_order_and_ignores_stdin` |
| FR-004 | `test_cli.py` | `test_fr004_output_concatenated_in_argument_order` |
| FR-005 | `test_redact.py` | `test_fr005_line_count_and_order_unchanged` |
| FR-006 | `test_cli.py` | `test_fr006_byte_identical_passthrough_crlf_blank_and_no_final_newline` |
| FR-007 | `test_redact.py` | `test_fr007_email_replaced_with_placeholder` |
| FR-008 | `test_redact.py` | `test_fr008_email_grammar_accepts_dots_plus_and_subdomains` |
| FR-009 | `test_redact.py` | `test_fr009_non_email_text_left_unchanged` |
| FR-010 | `test_redact.py` | `test_fr010_ipv4_replaced_with_placeholder` |
| FR-011 | `test_redact.py` | `test_fr011_ipv4_octet_range_boundaries` |
| FR-012 | `test_redact.py` | `test_fr012_out_of_range_or_wrong_part_count_left_unchanged` |
| FR-013 | `test_redact.py` | `test_fr013_ipv4_digit_boundary_and_trailing_period` |
| FR-014 | `test_redact.py` | `test_fr014_card_replaced_including_separators` |
| FR-015 | `test_redact.py` | `test_fr015_card_length_separator_shapes_and_luhn` |
| FR-016 | `test_redact.py` | `test_fr016_luhn_failure_length_and_digit_adjacency_left_unchanged` |
| FR-017 | `test_redact.py` | `test_fr017_leftmost_match_wins_and_email_beats_ipv4` |
| FR-018 | `test_redact.py` | `test_fr018_placeholders_not_reexamined` |
| FR-019 | `test_cli.py` | `test_fr019_count_writes_single_tally_line_after_output` |
| FR-020 | `test_redact.py`, `test_cli.py` | `test_fr020_counts_occurrences_not_distinct_values`, `test_fr020_single_tally_across_all_files` |
| FR-021 | `test_cli.py` | `test_fr021_stderr_empty_without_count` |
| FR-022 | `test_cli.py` | `test_fr022_diagnostic_names_path_for_missing_denied_directory_and_undecodable` |
| FR-023 | `test_cli.py` | `test_fr023_stops_at_first_failure_suppresses_tally_exits_2` |
| FR-024 | `test_cli.py` | `test_fr024_unrecognized_option_usage_to_stderr_nothing_processed` |
| FR-025 | `test_cli.py` | `test_fr025_exit_zero_when_all_inputs_read` |

### Success-criteria coverage

| Criterion | Where it is proven |
|---|---|
| SC-001 (worked examples byte-for-byte) | `test_cli.py::test_sc001_worked_examples_reproduce_exactly` — the E-1…E-3 blocks in [contracts/cli.md](./contracts/cli.md) |
| SC-002 (0% leak rate) | `test_corpus.py::test_sc002_no_known_value_survives` — asserts no known email, address, or card digit sequence appears in the output |
| SC-003 (0% false positives) | `test_corpus.py::test_sc003_non_sensitive_corpus_byte_identical` — Luhn-invalid runs, out-of-range quads, dates, versions, timestamps |
| SC-004 (every FR tested, suite green) | the map above; `pytest` exits 0 |
| SC-005 (failure modes assert message *and* status) | the FR-022/FR-023/FR-024 rows |
| SC-006 (100k lines <10 s, flat memory) | `test_cli.py::test_sc006_streams_large_input_within_budget` plus Scenario 5 by hand |
| SC-007 (reproducible from the tool alone) | every test runs with no config, env var, or network — only `PYTHONPATH=src` |

## Definition of done for this feature

- `pytest` passes from the repository root with no plugins.
- Every FR row above has a passing test, and the failure-mode rows assert both the diagnostic and
  the exit status.
- No third-party import appears in `src/` (Constitution merge gate).
- Scenarios 1-5 behave as written when run by hand.
