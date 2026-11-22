# Phase 1 Quickstart: Validating Phone Redaction and the Output Folder

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Contract**:
[contracts/cli.md](./contracts/cli.md) | **Data model**: [data-model.md](./data-model.md)

Runnable validation for this feature's two user-visible changes. Each scenario maps to a user
story in the spec and asserts an outcome a reviewer can see on screen. The v1 guide
([001 quickstart](../001-logredact-cli/quickstart.md)) still applies to everything this feature
does not change; its Scenario 3 tally output is the one thing there that changes.

This is a run-and-check guide. Recognition criteria live in
[data-model.md](./data-model.md); stream and exit-status rules live in
[contracts/cli.md](./contracts/cli.md).

## Prerequisites

Python 3.11 or newer, standard library only. No installation, no configuration, no network.

```bash
cd /root/sdd-study/runs/R022
export PYTHONPATH=src
python3 --version          # 3.11+
```

Scenarios that write files use a scratch directory; create and discard one per run:

```bash
WORK=$(mktemp -d) && cd "$WORK"   # remember to come back for `pytest`
```

## Run the tests

From the repository root:

```bash
python3 -m pytest -q
```

`pythonpath = ["src"]` is set in `pyproject.toml`, so no `PYTHONPATH` is needed for pytest. The
baseline before this feature is **31 passed, 1 skipped** (the skip is the permission-denied test,
which skips when the suite runs as root). After this feature the count grows; nothing that passed
before may fail, except the tally-form assertions updated under FR-008 (SC-005).

Useful subsets while working:

```bash
python3 -m pytest -q -k phone        # the new redaction rule
python3 -m pytest -q -k out_dir      # the new output destination
python3 -m pytest -q -k "fr027 or sc005"   # the preservation guarantees
```

---

## Scenario 1 — Phone numbers become `[PHONE]` (User Story 1, P1)

```bash
export PYTHONPATH=/root/sdd-study/runs/R022/src

echo 'call +14155552671 now' | python3 -m logredact
# call [PHONE] now

echo '+442071838750 and +14155552671' | python3 -m logredact
# [PHONE] and [PHONE]
```

All four rules on one line:

```bash
echo 'a@b.io 10.0.0.7 4111 1111 1111 1111 +442071838750' | python3 -m logredact
# [EMAIL] [IP] [CARD] [PHONE]
```

**The bounds, and what must *not* change** — every line below must come back byte-identical:

```bash
printf '%s\n' \
  'ext +1234567' \
  'ref +1234567890123456' \
  'total 100+25 units' \
  '+1 415 555 2671' \
  '+1-415-555-2671' \
  '[PHONE] already here' \
  | python3 -m logredact
```

Seven digits is too few and sixteen is too many (FR-004, FR-005); separators are not permitted;
and a literal `[PHONE]` in the input is left alone. Watch specifically for a partial replacement
such as `[PHONE]67` on the sixteen-digit line — its absence is FR-004.

**Exact bounds and precedence**:

```bash
printf '%s\n' '+12345678' '+123456789012345' '++14155552671' '100+14155552671' \
  | python3 -m logredact
# [PHONE]        <- exactly 8 digits
# [PHONE]        <- exactly 15 digits
# +[PHONE]       <- match starts at the second +
# 100[PHONE]     <- what precedes the + is unconstrained

printf '%s\n' '+12345678@b.io' 'jane@example.com+14155552671' '+1.2.3.4' '+4111111111111111' \
  | python3 -m logredact
# [EMAIL]        <- email wins at an equal start; the domain is not exposed
# [EMAIL][PHONE]
# +[IP]          <- not a phone; the IPv4 rule applies
# +[CARD]        <- 16 digits, so not a phone; Luhn-valid, so a card
```

**Expected outcome**: exit status 0 throughout; the full precedence table is
[contract C-1](./contracts/cli.md#c-1--redaction-fr-001fr-007).

---

## Scenario 2 — One redacted copy per file in an output folder (User Story 2, P2)

This is the spec's Independent Test for Story 2: two files in different directories, a folder that
does not exist yet.

```bash
cd "$WORK"
mkdir -p logs/2026 other
printf 'user jane@example.com\n' > logs/2026/app.log
printf 'GET / from 10.0.0.7\n'   > other/web.log

python3 -m logredact --out-dir clean logs/2026/app.log other/web.log
# wrote 2 files

ls clean
# app.log  web.log      <- basenames only; logs/2026/ is not reproduced (FR-014)

cat clean/app.log       # user [EMAIL]
cat clean/web.log       # GET / from [IP]
echo $?                 # 0
```

**Missing parents are created** (FR-016):

```bash
python3 -m logredact --out-dir out/2026/clean logs/2026/app.log
# wrote 1 files
ls out/2026/clean       # app.log
```

Note `wrote 1 files` — the plural noun is fixed (FR-018).

**An existing output file is replaced entirely** (FR-017) — the check that matters is that no
trailing bytes of the old content survive:

```bash
python3 -c "open('clean/app.log','w').write('X'*5000)"
python3 -m logredact --out-dir clean logs/2026/app.log
wc -c clean/app.log     # 14  == len('user [EMAIL]\n'), not 5000-and-something
```

**An empty input gives an empty output, and still counts** (Story 2 scenario 7):

```bash
: > empty.log
python3 -m logredact --out-dir clean empty.log
# wrote 1 files
wc -c clean/empty.log   # 0
```

**Byte-identical to what stdout would have produced** (FR-015) — the decisive check, covering CRLF
and a missing final newline:

```bash
printf 'a@b.io\r\n\r\nno final newline 10.0.0.7' > fidelity.log
python3 -m logredact fidelity.log > from_stdout.bin
python3 -m logredact --out-dir clean fidelity.log > /dev/null
cmp from_stdout.bin clean/fidelity.log && echo "FR-015 OK: byte-identical"
```

**Without `--out-dir`, nothing changes and no file is created** (FR-022):

```bash
python3 -m logredact logs/2026/app.log other/web.log
# user [EMAIL]
# GET / from 10.0.0.7 -> GET / from [IP]
# ... and no `wrote N files` line
```

**Duplicate basenames collide, in argument order** (spec Edge Cases):

```bash
mkdir -p a b
printf 'first a@b.io\n'  > a/app.log
printf 'second 1.2.3.4\n' > b/app.log
python3 -m logredact --out-dir clean a/app.log b/app.log
# wrote 2 files           <- one per FILE processed, not per distinct output path
cat clean/app.log
# second [IP]             <- the second argument's content survives
```

---

## Scenario 3 — The four-figure tally (User Story 3, P3)

```bash
echo 'a@b.io +442071838750' | python3 -m logredact --count
# stdout: [EMAIL] [PHONE]
# stderr: emails=1 ips=0 cards=0 phones=1
```

Capture the streams separately to prove the split and the ordering:

```bash
echo 'a@b.io +442071838750' | python3 -m logredact --count 2>tally.txt >data.txt
cat data.txt    # [EMAIL] [PHONE]
cat tally.txt   # emails=1 ips=0 cards=0 phones=1
```

**Zeroes, not omissions** (FR-009):

```bash
echo 'nothing sensitive here' | python3 -m logredact --count
# stderr: emails=0 ips=0 cards=0 phones=0
```

**Occurrences, not distinct values** (FR-009):

```bash
printf '%s\n' '+14155552671' '+14155552671' '+14155552671' | python3 -m logredact --count
# stderr: emails=0 ips=0 cards=0 phones=3
```

**Folder mode: one tally for the whole run, after the stdout line** (FR-019):

```bash
cd "$WORK"
python3 -m logredact --count --out-dir clean logs/2026/app.log other/web.log
# stdout: wrote 2 files
# stderr: emails=1 ips=1 cards=0 phones=0
```

**Without `--count`, stderr is empty** (FR-010):

```bash
echo 'a@b.io +14155552671' | python3 -m logredact 2>stderr.txt >/dev/null
wc -c stderr.txt   # 0
```

---

## Scenario 4 — Failures name the offending path and exit 2 (User Story 4, P3)

Every case below must print its diagnostic to **stderr**, print **no** `wrote N files` line and
**no** tally, and exit **2** (FR-026). Run each and check `echo $?`.

**Missing `--out-dir` value** (FR-012) — nothing is read:

```bash
python3 -m logredact logs/2026/app.log --out-dir
# stderr: usage: python -m logredact [--count] [FILE ...]
# stderr: logredact: --out-dir requires a directory
# exit 2
```

The usage line is deliberately the unchanged v1 text and does not mention `--out-dir`
(research [D-105](./research.md#d-105-the-usage-string-stays-byte-identical)).

**`--out-dir` with no FILE** (FR-020) — stdin is not read and the folder is not created:

```bash
echo 'a@b.io' | python3 -m logredact --out-dir nope
# stderr: logredact: --out-dir requires at least one FILE
# exit 2
ls nope       # No such file or directory
```

**Folder cannot be created** (FR-024) — parent is a regular file:

```bash
touch blocker
python3 -m logredact --out-dir blocker/clean logs/2026/app.log
# stderr: logredact: blocker/clean: File exists
# exit 2
```

Also `touch plainfile && python3 -m logredact --out-dir plainfile logs/2026/app.log`. In both
cases the input is never opened.

**Output file cannot be written** (FR-025) — a directory sits where the file should go:

```bash
mkdir -p clean2/app.log
python3 -m logredact --out-dir clean2 logs/2026/app.log
# stderr: logredact: clean2/app.log: Is a directory
# exit 2
```

The diagnostic names the **output** path here, and the **input** path in the next case — that
distinction is FR-023 vs FR-025.

**Unreadable FILE mid-list** (FR-023) — earlier output stays, no stray file for the failure:

```bash
python3 -m logredact --out-dir clean3 logs/2026/app.log missing.log --count
# stderr: logredact: missing.log: No such file or directory
# exit 2
ls clean3     # app.log only -- no empty clean3/missing.log
```

`--count` does not change that: neither line is printed (FR-026).

**Option-shaped folder value** (FR-011) — the token after `--out-dir` is taken literally:

```bash
python3 -m logredact --out-dir --count logs/2026/app.log
# stdout: wrote 1 files
# stderr: (empty -- --count was consumed as the folder name, not as an option)
ls -d ./--count && cat ./--count/app.log
```

**`--out-dir=DIR` is not a recognised token** (spec Assumptions):

```bash
python3 -m logredact --out-dir=clean logs/2026/app.log
# stderr: usage: ... / logredact: unrecognized option: --out-dir=clean
# exit 2
```

**Last value wins** (FR-021):

```bash
python3 -m logredact --out-dir first --out-dir second logs/2026/app.log
# wrote 1 files
ls second     # app.log
ls first      # No such file or directory  -- `first` is never created
```

---

## Scenario 5 — Nothing that worked before has changed (FR-027, SC-005)

The point of this scenario is to run the **v1** guide and contract against the changed tool.

```bash
cd /root/sdd-study/runs/R022
python3 -m pytest -q          # every pre-existing test still passes
```

Then re-run the v1 contract's own worked examples (E-1…E-7 in
[001 contracts/cli.md](../001-logredact-cli/contracts/cli.md)). All reproduce unchanged **except
E-3's tally line**, which is now `emails=1 ips=1 cards=0 phones=0`:

```bash
export PYTHONPATH=/root/sdd-study/runs/R022/src
echo 'user jane@example.com from 10.0.0.7' | python3 -m logredact   # E-1 unchanged
echo 'paid with 4111 1111 1111 1111, ref 1234567890123' | python3 -m logredact   # E-2 unchanged
echo 'a@b.io 1.2.3.4' | python3 -m logredact --count                # E-3: four figures now
python3 -m logredact --verbose a.log; echo $?                       # E-6 unchanged, exit 2
```

---

## Scenario 6 — Streaming limits (SC-007)

The envelope carried over from `001/SC-006`, now measured for **both** destinations because the
fourth rule and the file writes are new.

```bash
cd "$WORK"
python3 -c "
open('big.log','w').writelines(
    f'{i} user jane@example.com from 10.0.0.7 card 4111 1111 1111 1111 tel +442071838750\n'
    for i in range(100000))
"

time python3 -m logredact big.log > /dev/null                 # under 10 s
time python3 -m logredact --out-dir bigout big.log            # under 10 s, prints `wrote 1 files`
cmp <(python3 -m logredact big.log) bigout/big.log && echo "destinations agree"
```

A 1 MB single line, to prove memory does not track line length:

```bash
python3 -c "print('x'*1000000 + ' +442071838750')" | python3 -m logredact | wc -c
# 1000008   (1000000 x's + ' ' + '[PHONE]' + '\n')
```

Flat memory for a large file — watch RSS rather than trusting the loop:

```bash
/usr/bin/time -v python3 -m logredact --out-dir bigout big.log 2>&1 | grep -i 'maximum resident'
```

**Closed stdout in folder mode** — only the `wrote N files` line can hit a closed pipe, so
redacted data can never be truncated by it, and there must be no traceback:

```bash
python3 -m logredact --out-dir bigout big.log | head -0; echo "${PIPESTATUS[0]}"
# 141, stderr empty
```

---

## Requirement → test map (SC-004)

Every FR maps to at least one named test whose id carries the requirement it verifies
(Constitution Principle III). `test_redact.py` exercises the engine directly; `test_cli.py` runs
the real command in a subprocess via the `run_cli()` helper in `conftest.py`. Test ids below are
the names the implementation phase must create — the `fr0nn` prefixes are **this feature's**
numbering, so they are added to the existing files alongside the v1 `fr0nn` tests, which keep
their own meaning.

Suggested new files: `tests/test_phone.py` for the rule, `tests/test_out_dir.py` for the folder.
Keeping them separate from `test_redact.py`/`test_cli.py` leaves the v1 files almost untouched,
which is how SC-005 stays easy to audit.

| Requirement | Test file | Test id |
|---|---|---|
| FR-001 | `test_phone.py` | `test_fr001_phone_replaced_with_placeholder` |
| FR-002 | `test_phone.py` | `test_fr002_recognises_plus_then_8_to_15_digits` |
| FR-003 | `test_phone.py` | `test_fr003_plus_sign_is_consumed_by_the_placeholder` |
| FR-004 | `test_phone.py` | `test_fr004_sixteen_or_more_digits_never_partially_replaced` |
| FR-005 | `test_phone.py` | `test_fr005_too_few_digits_unchanged_and_preceding_text_unconstrained` |
| FR-006 | `test_phone.py` | `test_fr006_precedence_email_ipv4_phone_card_and_placeholders_not_reexamined` |
| FR-007 | `test_out_dir.py` | `test_fr007_phone_redacted_for_stdin_files_stdout_and_out_dir` |
| FR-008 | `test_cli.py` | `test_fr008_tally_line_has_four_figures_in_order` |
| FR-009 | `test_phone.py`, `test_cli.py` | `test_fr009_phones_counts_occurrences_and_zero_when_none`, `test_fr009_other_three_figures_keep_their_meaning` |
| FR-010 | `test_cli.py` | `test_fr010_tally_after_all_stdout_and_stderr_empty_without_count` |
| FR-011 | `test_out_dir.py` | `test_fr011_out_dir_value_taken_literally_in_any_position` |
| FR-012 | `test_out_dir.py` | `test_fr012_out_dir_without_value_usage_error_nothing_read` |
| FR-013 | `test_out_dir.py` | `test_fr013_redacted_lines_go_to_files_not_stdout` |
| FR-014 | `test_out_dir.py` | `test_fr014_output_named_by_basename_only` |
| FR-015 | `test_out_dir.py` | `test_fr015_output_file_byte_identical_to_stdout_including_crlf_and_no_final_newline` |
| FR-016 | `test_out_dir.py` | `test_fr016_creates_dir_with_missing_parents_and_reuses_existing` |
| FR-017 | `test_out_dir.py` | `test_fr017_existing_output_file_truncated_no_leftover_bytes` |
| FR-018 | `test_out_dir.py` | `test_fr018_wrote_n_files_line_counts_files_processed_and_exits_zero` |
| FR-019 | `test_out_dir.py` | `test_fr019_out_dir_with_count_writes_both_lines_in_order` |
| FR-020 | `test_out_dir.py` | `test_fr020_out_dir_without_file_errors_without_reading_stdin` |
| FR-021 | `test_out_dir.py` | `test_fr021_last_out_dir_value_wins` |
| FR-022 | `test_out_dir.py` | `test_fr022_without_out_dir_output_unchanged_and_no_file_created` |
| FR-023 | `test_out_dir.py` | `test_fr023_unreadable_file_names_input_path_stops_and_exits_2` |
| FR-024 | `test_out_dir.py` | `test_fr024_uncreatable_dir_names_path_and_exits_2` |
| FR-025 | `test_out_dir.py` | `test_fr025_unwritable_output_file_names_output_path_and_exits_2` |
| FR-026 | `test_out_dir.py` | `test_fr026_no_wrote_line_and_no_tally_on_any_exit_2_path` |
| FR-027 | `test_cli.py`, `test_redact.py` | the **entire pre-existing suite**, passing unchanged, plus `test_fr027_v1_contract_examples_unchanged` |

### Success-criteria coverage

| Criterion | Where it is proven |
|---|---|
| SC-001 (worked examples byte-for-byte) | `test_out_dir.py::test_sc001_worked_examples_reproduce_exactly` — the W-1…W-3 blocks in [contracts/cli.md](./contracts/cli.md) |
| SC-002 (0% phone leak, existing 0% unchanged) | `test_corpus.py::test_sc002_no_known_value_survives`, extended with known international numbers — asserts no `+`-plus-digit-run from the corpus appears in the output |
| SC-003 (0% false positives on `+` text) | `test_corpus.py::test_sc003_non_sensitive_corpus_byte_identical`, extended with arithmetic, short and long digit runs, spaced and hyphenated numbers, and version strings whose build metadata is not an 8-15 digit run (see research [D-101](./research.md#d-101-phone-recognition--d815d-no-lookbehind)) |
| SC-004 (every FR tested, suite green) | the map above; `pytest` exits 0 |
| SC-005 (v1 suite passes unchanged but for the tally form) | run `pytest` on the pre-existing files; the only edits permitted are the `emails=…` assertion strings at `test_cli.py:107,130,141,154,158,323,345` |
| SC-006 (every new failure mode asserts message *and* status) | the FR-012, FR-020, FR-023, FR-024, FR-025 rows |
| SC-007 (100k lines <10 s both destinations, flat memory) | `test_out_dir.py::test_sc007_streams_large_input_to_folder_within_budget` plus Scenario 6 by hand |
| SC-008 (reproducible from the tool alone) | every test runs with no config, env var, or network — only `pythonpath = ["src"]` |

## Definition of done for this feature

- `pytest` passes from the repository root with no plugins, and the pre-existing tests pass
  unchanged apart from the seven tally assertions listed under SC-005.
- Every FR row above has a passing test; the failure-mode rows assert both the diagnostic and the
  exit status (Principle II and III).
- No third-party import appears in `src/`, and `pyproject.toml` still declares
  `dependencies = []` (Constitution merge gate).
- The `USAGE` constant is byte-identical to its v1 text
  (research [D-105](./research.md#d-105-the-usage-string-stays-byte-identical)).
- Scenario 6 has been run and its two timings recorded.
