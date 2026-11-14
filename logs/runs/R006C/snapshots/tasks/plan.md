# Implementation Plan: Phone Redaction and Output Folder

**Branch**: `002-phone-redaction-out-dir` | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-phone-redaction-out-dir/spec.md`

## Summary

An amendment to the built and tested `logredact` CLI
([001](../001-logredact-cli/spec.md)). Two additions and two changed behaviours:

1. **Phone numbers.** One new alternative, `\+[0-9]{8,15}(?![0-9])`, in the existing single compiled
   pattern, written between `ip` and `card` so the source order is FR-021's precedence order. The
   `--count` tally gains a fourth field, appended: `emails=N ips=N cards=N phones=N`.
2. **`--out-dir DIR`.** One new option. With it, each FILE operand's redacted lines go to
   `DIR/<final path component of that operand>` instead of standard output, DIR and its missing
   parents are created owner-accessible-only, and standard output carries exactly one line,
   `wrote N files`, once every operand has been processed.

The approach stays as small as the existing design: **no new module, no new class, no new
abstraction**. `redact.py` gains a pattern, a placeholder constant and a replacer branch;
`cli.py` gains an argparse option, two helper functions and a destination branch in the operand
loop. `_redact_stream` already takes its destination as a parameter, so the line loop is untouched
and the memory bound of FR-034 holds for the new destination by construction.

Four Phase 0 findings shaped the design, all measured ([research.md](./research.md)):

1. **`os.makedirs(dir, mode=0o700)` would leave world-readable parents.** Since Python 3.7 the
   `mode` argument applies only to the leaf: `makedirs("a/b/c", mode=0o700)` measured `0o755` on `a`
   and `a/b`. Story 2 scenario 4 has the tool create all three, so this is a direct SR-011 and
   SC-020 failure. DIR and each missing parent are created individually with
   `os.mkdir(path, 0o700)` ([R19](./research.md)).
2. **One `os.open` call satisfies four requirements at once.**
   `os.open(path, O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW, 0o600)` delivers SR-010 (a symlink at the
   output path is refused, including a dangling one that would otherwise silently write outside
   DIR), SR-011 (owner-only at creation, and a pre-existing file keeps its own mode — measured
   `0o644` preserved), and FR-026 (content replaced in full), with no check-then-act window
   ([R20](./research.md)).
3. **The same-file check must be on identity, not on path strings.** `--out-dir .`, an absolute DIR
   containing the operand, and a hard link all name one file by different paths.
   `os.path.samestat(os.fstat(input_fd), os.stat(out_path))` against the *already-open* input
   descriptor catches all three, before `O_TRUNC` could destroy the input (FR-036, SR-012,
   [R21](./research.md)).
4. **The phone rule changes existing card output in exactly one family of inputs**, found by
   exhaustive search rather than assumed: a `+` followed by 8–15 digits that today form or begin a
   Luhn-valid card candidate. `+4111111111111` → `[PHONE]` instead of `+[CARD]` is A-13's intent;
   `+41111111 11119` → `[PHONE] 11119` leaves five digits of a card candidate behind and is a
   narrowing of redaction. It follows directly from FR-021's no-re-scan clause, is unreachable with
   real card groupings, and is accepted with a test pinning it ([R17](./research.md)).

A prototype of the phone rule passes 18 of 18 cases drawn from Story 1, Story 3 and the Edge Cases,
is measured linear from 48 KiB to 1 MiB on five adversarial shapes (worst case 425 ms per 1 MiB
line), and every filesystem primitive above is measured against its failure shapes.

## Technical Context

**Language/Version**: Python 3.11+ (A-10 and the user input for this step; verified here on
3.13.17). Nothing newer than 3.11 is used: `os.O_NOFOLLOW`, `os.path.samestat` and `os.mkdir`'s mode
argument all predate it.

**Primary Dependencies**: None. Standard library only — `re`, `os`, `sys`, `signal`, `argparse`,
unchanged from 001; `os.path` and `os.open`/`os.mkdir` are the only additions, and `stat` appears in
tests only (Principle I, A-10).

**Storage**: Files written to the directory the caller names with `--out-dir`, and nothing else.
No persistence of the tool's own, no temporary files, no caches, no logs (SR-013, A-25).

**Testing**: `pytest` (A-11) — the only development dependency the constitution permits without
justification, and the one the user input for this step specifies. Unit tests against
`redact_line()`; contract tests running `python -m logredact` in a subprocess and comparing raw
bytes on stdout and stderr, the exit status, and now also the contents and the permission bits of
files in DIR ([R25](./research.md)).

**Target Platform**: Any POSIX-like system with CPython 3.11+. This feature adds a second
platform-specific dependency beside 001's `SIGPIPE` path: `O_NOFOLLOW`, which POSIX defines and
Windows does not.

**Project Type**: Single-package CLI tool, `logredact` under `src/`, run as `python -m logredact`
with `src/` on `PYTHONPATH`. Unchanged.

**Performance Goals**: The tripwires adopted in [R14](../001-logredact-cli/research.md) are
unchanged and still met: ≥1 MB/s on realistic log text (measured 7.1 MB/s with the phone rule
added), any adversarial 1 MiB line under 10 s (phone worst case measured 425 ms; the card scan's
3.4 s remains the overall worst case), every pattern linear in line length (SR-015, measured).

**Constraints**: Peak memory bounded by roughly the 1 MiB line cap, independent of total input size
*and now of the number of operands* — one line and one open output handle at a time (FR-034,
SC-018). Byte-for-byte pass-through, including invalid UTF-8 and every line terminator, in files in
DIR exactly as on stdout (FR-009, A-4, measured in [R20](./research.md)). Exit statuses still
limited to 0, 2 and 141. Permissions owner-only at creation for everything the tool creates
(SR-011).

**Scale/Scope**: One new option, one new redaction kind, one new output destination. Roughly 70
added lines across the two existing source files; no new source file. 18 new functional, 8 new
security and 12 new success-criteria items to cover with tests, plus the whole 001 suite kept green
with one textual change.

**No NEEDS CLARIFICATION items remain.** All twelve Phase 0 unknowns are resolved in
[research.md](./research.md). Two were spec ambiguities rather than research questions; both are
resolved there with the reasoning and the cost of reversal recorded, and are flagged here so the
decisions are visible before implementation:

- **[R18](./research.md)**: FR-023's "at most once per invocation" is enforced — a **second
  `--out-dir` is rejected** as a usage error rather than last-one-wins, because two occurrences
  express two different destinations and silently honouring one is the silent wrong answer
  Principle II forbids. A repeated `--count` keeps today's accepting behaviour, as FR-035 requires.
  Reversible in two lines plus one test.
- **[R22](./research.md)**: FR-028 covers an operand that cannot be *opened or read*; for one that
  opens and then fails mid-read, the **partially written output file stays**, the operand is not
  counted in N, and the run exits 2. Deleting it is unrequested, and staging through a temporary
  file is forbidden by SR-013 and A-25. Consistent with A-25's posture for a run stopped early.
  Reversible by adding one `os.unlink`.

One further decision is not an ambiguity but should be visible: **[R17](./research.md)**'s
`+41111111 11119` → `[PHONE] 11119`. It follows from FR-021 as written; if the requester wants the
card rule to win that overlap it is an amendment to FR-021, plus reordering two alternatives and one
test.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0. Initial check (pre-Phase 0) and re-check (post-Phase 1) are both
recorded; the re-check column is what the gate is decided on.

| Principle | Requirement | Initial | Post-design | Evidence |
|---|---|---|---|---|
| I. Standard Library Only | No runtime third-party imports; runnable with no dependency resolution; only `pytest` for dev | PASS | **PASS** | Additions are `os.path`, `os.open`, `os.mkdir`, `os.fstat` — all standard library. No capability needed a third-party package; `pyproject.toml` still carries pytest configuration only ([R1](../001-logredact-cli/research.md)) |
| II. Fail Loudly | Diagnostic to stderr + non-zero status for every invalid input; no swallowed exceptions; no sentinel returns; defaults only where specified | PASS | **PASS** | Every new failure path enumerated below with its message, status and continue/stop behaviour. `OSError` is caught narrowly at each new boundary — DIR creation, output open, output flush/close — and always reported. No bare `except`, no `except Exception`. The one new `None` return is justified below |
| III. Every Requirement Is Testable | Every FR and SR maps to at least one automated test; mapping recorded in the plan | PASS | **PASS** | Mapping table below covers FR-019…036, SR-010…017 and SC-011…022 with no unmapped item. Two tests are skipped as root and that is reported, not hidden ([R25](./research.md)) |
| IV. Simplicity | Smallest sufficient design; every abstraction justified against the requirement forcing it | PASS | **PASS** | No new module, no new class, no new data structure beyond one `int` and one `str`; the existing `out` parameter of `_redact_stream` *is* the output-destination abstraction. Four departures from the most obvious code are justified in Complexity Tracking |
| V. Secure by Default | Security requirements stated, testable, each mapped to baseline controls and to a test | PASS | **PASS** | SR-010…017 mapped to Security Baseline controls below and to tests in the mapping table. This feature engages two controls 001 did not — path confinement and file permissions — and both are satisfied at creation time rather than by a later check |

No Security Baseline control is waived, and none that 001 relied on is weakened.

### Principle II — error behaviour for every invalid-input case

Required explicitly by the planning gate. 001's table stays in force; these are the new cases.
Message shapes are in [contracts/cli.md](./contracts/cli.md#diagnostics).

| Invalid input | Behaviour | Status | Requirement |
|---|---|---|---|
| `--out_dir`, `--out`, `--out-di`, any other abbreviation | argparse usage + message on stderr; nothing read; nothing on stdout; no directory created | 2 | SR-016, [R18](./research.md) |
| `--out-dir` with no value | argparse usage + `expected one argument`; nothing read or created | 2 | SR-016, Story 4 scenario 9 |
| `--out-dir` given twice | `--out-dir may be given at most once`; nothing read; neither directory created | 2 | FR-023, [R18](./research.md) |
| `--out-dir` with no FILE operand | `--out-dir requires at least one FILE operand`; stdin **not** read; DIR **not** created; stdout empty | 2 | FR-031, A-16, [R23](./research.md) |
| DIR exists but is not a directory | `cannot create output directory 'DIR': File exists`; no operand read; stdout empty | 2 | FR-029 |
| DIR cannot be created (parent denies write) | `cannot create output directory 'DIR': Permission denied`; no operand read; stdout empty | 2 | FR-029 |
| `--out-dir ""` | `cannot create output directory '': No such file or directory`; no operand read | 2 | FR-029, spec Edge Cases |
| Operand unreadable, `--out-dir` in effect | `cannot read 'FILE': REASON`; **no output file created for it**; remaining operands processed; `wrote N files` still written, excluding it | 2, at end of run | FR-028, A-17 |
| Output path names the operand being read | `refusing to write 'OUTPATH': it is the input file 'FILE'`; operand left unmodified and **not truncated**; remaining operands processed | 2, at end of run | FR-036, SR-012, [R21](./research.md) |
| Output path is a symbolic link | `cannot write 'OUTPATH': Too many levels of symbolic links`; link not followed; target untouched and not created; remaining operands processed | 2, at end of run | SR-010, [R20](./research.md) |
| Output file cannot be opened | `cannot write 'OUTPATH': REASON`; remaining operands processed; not counted in N | 2, at end of run | FR-030 |
| Output write, flush or close fails | same shape; the operand is **not** counted in N, because it is counted only after a clean close | 2, at end of run | FR-030, [R22](./research.md) |
| Operand fails mid-read, `--out-dir` in effect | `cannot read 'FILE': REASON`; the partial output file stays; not counted in N; remaining operands processed | 2, at end of run | FR-028, [R22](./research.md) |
| Line over 1 MiB, `--out-dir` in effect | `SOURCE: line exceeds the maximum length of 1048576 characters`; no part of the line in any output file; lines before it stay; **no** `wrote N files` line; run stops, later operands not read | 2, at once | FR-033, A-25 |

No case returns a sentinel a caller could mistake for success, and no case produces a silent partial
success: every non-zero status means the output — on stdout or in DIR — is incomplete.

**The one new `None` return, examined** because Principle II forbids sentinels. The helper that opens
an operand's output file returns the open handle, or `None` *after having written its diagnostic and
set the run's failure flag*. This is not a value a caller can mistake for a valid result: it is the
same convention `_redact_stream` already uses (`False` meaning "reported, skip this source"), the
only use the caller makes of the return value is as a context manager, and the alternative — a
private exception class — is what 001's Complexity Tracking already had to justify for
`_OverLengthLine` and is not warranted here, because this failure does **not** unwind past the
operand loop. Recorded so a reviewer can challenge it.

### Principle V — security requirements mapped to Security Baseline controls

001's SR-001…009 mapping stays in force. These are this feature's requirements. Two baseline
controls that 001 did not engage — *path confinement* and *file permissions* — are engaged here.

| Spec requirement | Baseline control relied on | How this design satisfies it |
|---|---|---|
| SR-010 output path from DIR + final component only; never outside DIR; symlink not followed | *No string concatenation into interpreters* — "file paths MUST be resolved and confirmed to lie inside an allowed base directory, and symbolic links MUST NOT be followed out of that directory" | The path is `os.path.join(DIR, os.path.basename(operand))`: one component, from the caller's own argument, never from input data; `os.path.basename` resolves and normalises nothing. `O_NOFOLLOW` refuses any symlink at that path, dangling ones included, with no check-then-act window ([R20](./research.md), [R26](./research.md)) |
| SR-011 narrowest permissions, set at creation | *File permissions* — "narrowest permissions that allow the feature to work, set at creation rather than relaxed and tightened afterwards"; "`0o600` for data files, `0o700` for directories holding them" | `os.mkdir(path, 0o700)` per created component — `os.makedirs(mode=…)` would leave `0o755` parents, measured ([R19](./research.md)); `os.open(..., 0o600)` sets the mode as the file is created, and leaves a pre-existing file's mode untouched, measured ([R20](./research.md)). No `chmod` anywhere |
| SR-012 no operand ever opened for writing, creation or truncation | *File permissions* / fail-loudly | Identity check with `os.path.samestat(os.fstat(input_fd), os.stat(out_path))` **before** the output open, so `O_TRUNC` can never reach the operand; catches path aliases, hard links and symlinks ([R21](./research.md)). Operands are still opened `"r"` with the string verbatim (SR-008) |
| SR-013 input data written only to stdout and files in DIR; no temporary files or staging | *File permissions* — "temporary files MUST be created with `tempfile`… never at a predictable path", satisfied here by creating none | No `tempfile`, no `logging` handler, no rename-based staging (A-25); the only sinks are stdout, stderr and the per-operand file in DIR. Asserted by a before/after tree snapshot outside DIR |
| SR-014 neither summary line discloses personal data | *Output, logs, and errors* | Both lines are fixed format strings over integers: `"emails=%d ips=%d cards=%d phones=%d\n"` and `"wrote %d files\n"`. Nothing derived from the data can reach either |
| SR-015 phone recognition linear, no backtracking blow-up, memory unchanged | *Resource limits* — "regular expressions MUST NOT be applied to unbounded untrusted input in a form subject to catastrophic backtracking" | `{8,15}` over one character class bounds the work at any start position to at most 8 attempts; measured linear from 48 KiB to 1 MiB on five adversarial shapes, worst case 425 ms ([R15](./research.md)). The 1 MiB cap and `readline(CAP + 1)` are unchanged |
| SR-016 argument allowlist = `--count`, `--out-dir` + value, `--`, operands | *Untrusted input* — validate against an explicit allowlist at the trust boundary | The existing `add_help=False, allow_abbrev=False` parser rejects every abbreviation and unknown option before any I/O, measured against `--out_dir`, `--out`, `--out-di` and a valueless `--out-dir`; the duplicate check and the "needs an operand" check run immediately after parsing, still before any read or any directory creation ([R18](./research.md), [R23](./research.md)) |
| SR-017 output-folder diagnostics disclose no personal data; no traceback | *Output, logs, and errors* — "report that a field was rejected and why, not its contents" | Messages are fixed literals plus DIR or an output path (both derived from the caller's arguments) plus the OS `strerror`. No input line, match or fragment is formatted into any message, and every new failure path is a handled `OSError`, so no traceback reaches stderr |

Controls not engaged by this feature are unchanged from 001: no SQL, no secrets storage, no
randomness, no access control, no archive extraction, no decompression, no subprocess.

### Requirement-to-test mapping

Required by Principle III and the planning gate: an unmapped requirement must be visible before
implementation starts. Contract IDs (C-nn) are defined in [contracts/cli.md](./contracts/cli.md).
Test files are listed under Project Structure.

| Requirement | Test |
|---|---|
| FR-019 phone → `[PHONE]`, `+` consumed, bounds inclusive | `test_redaction_rules.py::test_phone_shapes`, `::test_phone_digit_bounds` (C-27…C-29) |
| FR-020 candidate not followed by a digit; no leading fragment replaced | `test_redaction_rules.py::test_sixteen_digit_run_has_no_phone` (C-31), `::test_no_phone_fragment_replaced` |
| FR-021 precedence email > ip > phone > card; redacted and counted once; no re-scan | `test_redaction_rules.py::test_email_beats_phone` (C-35), `::test_phone_beats_card` (C-40), `::test_phone_placeholder_not_rescanned`, `::test_phone_card_overlap_is_pinned` (C-41) |
| FR-022 tally format, field order, run totals, timing | `test_cli_count.py::test_count_format` (C-42), `::test_zero_counts` (C-43), `::test_appended_field_order` (C-44), `::test_totals_across_operands` (C-45), `::test_summary_after_output` |
| FR-023 `--out-dir` accepted, `=` form, at most once | `test_cli_outdir.py::test_out_dir_accepted`, `::test_equals_form`; `test_cli_outdir_errors.py::test_repeated_out_dir_rejected` (C-75) |
| FR-024 one file per operand, named by the final component; no redacted line on stdout | `test_cli_outdir.py::test_writes_one_file_per_operand` (C-48), `::test_only_final_path_component` (C-50), `::test_no_redacted_line_on_stdout` (C-49) |
| FR-025 DIR created with missing parents; existing DIR used as it is | `test_cli_outdir.py::test_creates_missing_parents` (C-51), `::test_existing_dir_reused_and_untouched` (C-56) |
| FR-026 existing output file replaced in full | `test_cli_outdir.py::test_existing_output_replaced_in_full` (C-52) |
| FR-027 `wrote N files`, fixed format, not pluralised | `test_cli_outdir.py::test_count_line` (C-48), `::test_count_line_not_pluralised` (C-53) |
| FR-028 unreadable operand: named, no output file, others still written, N excludes it | `test_cli_outdir_errors.py::test_unreadable_operand_skipped` (C-62) |
| FR-029 DIR not creatable / not a directory: named, nothing read or written | `test_cli_outdir_errors.py::test_dir_is_a_regular_file` (C-63), `::test_empty_dir_value` (C-72), `::test_dir_parent_denies_write` (C-64, **skipped as root**) |
| FR-030 output open/write/flush failure: named, others processed, not counted | `test_cli_outdir_errors.py::test_output_file_cannot_be_opened` (C-66, **skipped as root**), `::test_output_flush_failure_fails_run` |
| FR-031 `--out-dir` with no operand | `test_cli_outdir_errors.py::test_out_dir_without_operand` (C-65) |
| FR-032 `--out-dir` and `--count` together | `test_cli_outdir.py::test_count_and_out_dir` (C-46), `::test_no_stderr_without_count` (C-47) |
| FR-033 over-length line: no `wrote N files`, no part of the line written | `test_cli_outdir_errors.py::test_over_length_line_suppresses_count_line` (C-68) |
| FR-034 written as read; memory bounded by one line regardless of operand count | `test_resource_bounds.py::test_out_dir_memory_independent_of_operands` (SC-018) |
| FR-035 without `--out-dir`, behaviour exactly as today | `test_cli_outdir.py::test_without_out_dir_unchanged` (C-55) + the whole 001 suite (SC-012) |
| FR-036 output path equals the operand: refused, operand unmodified, others processed | `test_cli_outdir_errors.py::test_output_path_is_the_input` (C-67) |
| SR-010 path = DIR + final component only; no write outside DIR; symlink refused | `test_cli_outdir.py::test_only_final_path_component` (C-50), `::test_absolute_operand_contributes_no_path`, `::test_no_file_written_outside_dir`; `test_cli_outdir_errors.py::test_symlink_output_refused` (C-73), `::test_dangling_symlink_refused_and_target_not_created` (C-74) |
| SR-011 owner-only at creation; existing file's mode untouched | `test_cli_outdir.py::test_created_modes_are_owner_only` (C-60, SC-020), `::test_existing_output_keeps_its_mode` (C-61) |
| SR-012 no operand opened for writing/creation/truncation | `test_cli_outdir_errors.py::test_output_path_is_the_input` (C-67), `::test_operand_not_truncated_when_refused`; `test_cli_outdir.py::test_operands_unmodified` (C-54) |
| SR-013 input data only to stdout and files in DIR; no temp file, no staging | `test_cli_outdir.py::test_no_file_written_outside_dir` (tree snapshot), `::test_no_staging_path_appears_during_the_run`, static check `::test_no_tempfile_import` |
| SR-014 neither summary line discloses data | `test_cli_count.py::test_summary_is_exactly_four_integers`, `test_cli_outdir.py::test_count_line_is_only_literals_and_an_integer` (SC-021) |
| SR-015 phone recognition linear; memory unchanged | `test_resource_bounds.py::test_phone_adversarial_lines_are_linear` (parametrised over five shapes, doubling sizes), `::test_out_dir_memory_independent_of_operands` |
| SR-016 allowlist: exactly `--count`, `--out-dir` + value, `--`, operands | `test_cli_outdir_errors.py::test_rejected_out_dir_spellings` (C-69, parametrised: `--out_dir`, `--out`, `--out-di`, `--outdir`), `::test_out_dir_without_value` (C-70), `::test_repeated_out_dir_rejected` (C-75); `test_cli_errors.py::test_double_dash_separator` (C-20, unchanged) |
| SR-017 output-folder diagnostics disclose nothing; no traceback | `test_cli_outdir_errors.py::test_no_input_data_in_diagnostics` (C-71), `::test_no_traceback_on_any_out_dir_error_path` |
| SC-011 three worked examples byte-for-byte | `test_cli_stream.py::test_worked_examples_002` (C-27, C-42), `test_cli_outdir.py::test_worked_example_out_dir` (C-48) |
| SC-012 everything else unchanged; 001 suite passes | the whole existing suite, with ` phones=N` appended in `test_cli_count.py` and `test_resource_bounds.py` only; checked at the implementation gate |
| SC-013 genuine phone corpus 100% redacted, no digit surviving | `test_redaction_rules.py::test_phone_corpus_fully_redacted` |
| SC-014 near-miss corpus 0 redacted, no digit removed by the phone rule | `test_redaction_rules.py::test_phone_near_miss_corpus_untouched` |
| SC-015 K operands → exactly K files, each the redaction of its operand, `wrote K files` | `test_cli_outdir.py::test_k_operands_produce_k_files` (parametrised over K) |
| SC-016 100% of FR/SR mapped to a test | this table, checked at the implementation gate |
| SC-017 no operand's content or size ever changes | `test_cli_outdir.py::test_operands_unmodified` (content, size and mtime), `test_cli_outdir_errors.py::test_operand_not_truncated_when_refused` |
| SC-018 peak memory flat over ≥50 operands totalling ≥100× the cap | `test_resource_bounds.py::test_out_dir_memory_independent_of_operands` (marked `slow`) |
| SC-019 unreadable operand → 2, named, every other output complete | `test_cli_outdir_errors.py::test_unreadable_operand_skipped` |
| SC-020 created files and directories inaccessible to group and other | `test_cli_outdir.py::test_created_modes_are_owner_only` |
| SC-021 no personal data on stderr or in the `wrote N files` line | `test_cli_outdir_errors.py::test_no_input_data_in_diagnostics`, `test_cli_outdir.py::test_count_line_is_only_literals_and_an_integer`, `test_cli_count.py::test_summary_is_exactly_four_integers` |
| SC-022 the two summary lines alone answer "what was removed, how many files" | `test_cli_outdir.py::test_count_and_out_dir` (the two formats together are the whole contract) |

**Phase 0 regression tests also required**, for defects found while prototyping:
`test_created_modes_are_owner_only` must assert the mode of DIR's **parents** as well as DIR
([R19](./research.md) — `makedirs` left them `0o755`), and
`test_dangling_symlink_refused_and_target_not_created` must assert the target was not created
([R20](./research.md) — the case an existence check would miss).

**Skips must be reported, not hidden** (constitution, Reporting). `test_dir_parent_denies_write`
(C-64) and `test_output_file_cannot_be_opened` (C-66) carry
`@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permissions")`, matching
`test_cli_errors.py:176`, because root ignores the permission bits they depend on — measured in
[R19](./research.md). Run `pytest -rs` and state both skips with the results; FR-029's and FR-030's
permission paths are otherwise covered only by their non-permission failure shapes (an existing
regular file at DIR, an empty DIR value, a symlinked output path, `/dev/full`).

## Project Structure

### Documentation (this feature)

```text
specs/002-phone-redaction-out-dir/
├── plan.md                        # This file
├── spec.md                        # Feature specification (amendment to 001)
├── research.md                    # Phase 0 output — 12 decisions, R15…R26, with measurements
├── data-model.md                  # Phase 1 output — amended and new in-memory entities
├── quickstart.md                  # Phase 1 output — runnable validation guide
├── contracts/
│   ├── cli.md                     # Phase 1 output — amended interface, C-27…C-75
│   └── redaction-rules.md         # Phase 1 output — the phone rule and four-way precedence
├── checklists/
│   └── requirements.md            # Spec quality checklist (from /speckit-specify)
└── tasks.md                       # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml                     # unchanged — pytest configuration only, no packaging, no dependencies

src/
└── logredact/
    ├── __init__.py                # unchanged
    ├── __main__.py                # unchanged
    ├── redact.py                  # CHANGED: _PHONE pattern, PHONE_PLACEHOLDER, phone branch in _replace
    └── cli.py                     # CHANGED: --out-dir option, _prepare_out_dir(), _open_output(),
                                   #          four-field tally, destination branch and write tally in _run

tests/
├── conftest.py                    # unchanged — the subprocess byte-comparison harness
├── test_redaction_rules.py        # EXTENDED: phone recognition, precedence, corpora (FR-019…021, SC-013, SC-014)
├── test_cli_stream.py             # EXTENDED: Story 1 end to end, the 002 worked examples
├── test_cli_files.py              # unchanged
├── test_cli_count.py              # AMENDED: four-field tally text (FR-022, SR-014)
├── test_cli_errors.py             # unchanged
├── test_cli_outdir.py             # NEW: Story 2 — folder, files, permissions, confinement (FR-023…027, 032, 034, 035, SR-010, 011, 013, 014)
├── test_cli_outdir_errors.py      # NEW: Story 4 — every --out-dir failure path (FR-028…031, 033, 036, SR-012, 016, 017)
└── test_resource_bounds.py        # EXTENDED: phone linearity (SR-015), many-operand memory (SC-018)
```

**Structure Decision**: the layout of 001 is kept exactly, and **no source file is added**. The
feature's two halves land in the two existing modules along the split that already exists —
`redact.py` stays pure (text in, text and counter increments out), so the phone recognition and
precedence cases run as fast in-process unit tests, while everything touching the filesystem lands
in `cli.py` and is exercised through the real `python -m logredact` interface.

A third module for the output folder was considered and rejected: it would hold two short functions
that nothing else calls, and the `--out-dir` logic is inseparable from the operand loop that drives
it, so the split would add a file and an import without removing any coupling (Principle IV). Two
new test files *are* added, because `test_cli_errors.py` is already 529 lines and Stories 2 and 4
are independently testable slices that a reader should be able to find by name.

## Complexity Tracking

The Constitution Check passes with no violations, so no justification is owed. Four places
nevertheless depart from the most obvious implementation, and Principle IV requires each to be
justified against the requirement that forces it. Recorded here so a reviewer can challenge them.

| Departure | Why needed | Simpler alternative rejected because |
|---|---|---|
| Per-component `os.mkdir(path, 0o700)` loop instead of `os.makedirs(DIR, mode=0o700, exist_ok=True)` | SR-011 and SC-020 require *every* directory the tool creates to be owner-accessible only, and Story 2 scenario 4 has it create all three components of `a/b/c` | `makedirs`'s `mode` applies only to the leaf since Python 3.7: measured `0o755` on `a` and `a/b` under umask 0o022, leaving two group- and world-readable directories holding redacted log data. `makedirs` + `chmod` is rejected too — the baseline requires permissions set at creation, not relaxed then tightened ([R19](./research.md)) |
| Raw `os.open(..., O_WRONLY\|O_CREAT\|O_TRUNC\|O_NOFOLLOW, 0o600)` wrapped in `open(fd, "w", …)`, instead of `open(path, "w", …)` | SR-010 (no symlink followed out of DIR), SR-011 (owner-only at creation, pre-existing mode untouched) and FR-026 (replaced in full) — all three, with no check-then-act window | `open(path, "w")` follows a symlink straight out of DIR, including a dangling one that no existence check would notice, and creates at the umask default so the file would have to be chmod-ed afterwards. `os.path.islink()` then `open()` leaves a race where `O_NOFOLLOW` leaves none ([R20](./research.md)) |
| `os.path.samestat(os.fstat(input_fd), os.stat(out_path))` instead of comparing normalised path strings | FR-036 and SR-012 — the output must be proven not to be the operand *before* `O_TRUNC` could destroy it | String comparison misses `--out-dir .`, an absolute DIR that contains the operand, and hard links — measured: all three are the same file by `st_dev`/`st_ino` and none is the same string. Using the already-open input descriptor also removes the input side of the race ([R21](./research.md)) |
| `--out-dir` declared with `action="append"` plus an explicit duplicate check, instead of the default `store` | FR-023's "at most once per invocation", read as a constraint the tool enforces | Default `store` silently takes the last of two different destinations, writing files somewhere the caller may not have meant — the silent wrong answer Principle II calls the highest-severity defect. Two lines, and reversible in two lines if the requester prefers last-one-wins ([R18](./research.md)) |

One further item is not a departure from the obvious but is recorded because Principle II names it:
the output-opening helper returns `None` to mean "already reported, skip this operand", following
`_redact_stream`'s existing `False` convention rather than adding a second private exception class.
Examined under **Principle II** above.

## Phase status

- [x] **Phase 0** — research complete; 12 unknowns resolved (R15…R26), 0 NEEDS CLARIFICATION
      remaining → [research.md](./research.md)
- [x] **Phase 1** — design complete → [data-model.md](./data-model.md),
      [contracts/cli.md](./contracts/cli.md),
      [contracts/redaction-rules.md](./contracts/redaction-rules.md),
      [quickstart.md](./quickstart.md)
- [x] **Constitution Check** re-evaluated after design: PASS on all five principles; no baseline
      control waived, and none of 001's weakened
- [ ] **Phase 2** — task breakdown (`/speckit-tasks`, not part of this command)
