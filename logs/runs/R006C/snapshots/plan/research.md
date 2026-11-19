# Phase 0 Research: Phone Redaction and Output Folder

**Branch**: `002-phone-redaction-out-dir` | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

This is an amendment to a built and tested tool, so Phase 0 had a second job beyond resolving
unknowns: establishing which existing behaviour the amendment changes, deliberately or otherwise.
Numbering continues from [001's research.md](../001-logredact-cli/research.md) (R1–R14), so
cross-references stay unambiguous.

Every decision was taken against the constitution (standard library only, fail loudly, testable,
simplest sufficient design, secure by default). Where a decision rests on a measurement, the script
and result are recorded so a reviewer can reproduce it. Measurements were taken on Python 3.13.17
(the interpreter available here; the delivered floor is 3.11, per the user input for this step and
A-10).

## Summary of unknowns resolved

| # | Unknown from Technical Context | Status |
|---|---|---|
| R15 | The phone pattern, and whether it runs in linear time (SR-015) | Resolved — measured |
| R16 | How FR-021's four-way precedence is delivered without a rule table | Resolved — measured |
| R17 | Which existing behaviour the phone rule changes (SC-012) | Resolved — measured; one specified regression found |
| R18 | How to add `--out-dir` to the strict allowlist, and what a repeated `--out-dir` means | Resolved — measured; spec ambiguity, decision recorded |
| R19 | How to create DIR and its missing parents at owner-only permissions (SR-011) | Resolved — measured, naive approach rejected |
| R20 | How to open an output file satisfying SR-010, SR-011 and FR-026 at once | Resolved — measured |
| R21 | How to prove the output path is not the input before truncating anything (SR-012) | Resolved — measured |
| R22 | When `wrote N files` is written, what N counts, and what a mid-file failure leaves behind | Resolved — A-17/A-18 plus one spec gap |
| R23 | How to reject `--out-dir` with no operand without breaking `main`'s status contract | Resolved |
| R24 | Flush ordering of the two summary lines | Resolved — derived from FR-022, FR-027, A-3 |
| R25 | Test strategy for permissions, symlink confinement, and the SC-018 memory bound | Resolved — one test must be skipped as root |
| R26 | Awkward operand basenames (`logs/`, `.`, `..`, absolute paths) | Resolved — measured |

**No NEEDS CLARIFICATION items remain.** Two items (R18, R22) are spec ambiguities rather than
research questions; both are resolved below with the reasoning and the cost of reversal recorded.

Reproduce the measurements with:

```bash
python3 -I /tmp/proto/phone.py      # R15, R16, R17 — pattern cases, linearity, throughput
python3 -I /tmp/proto/overlap.py    # R17 — exhaustive search for changed card behaviour
python3 -I /tmp/proto/fsprims.py    # R18, R19, R20, R21, R26 — filesystem and argparse primitives
python3 -I /tmp/proto/writer.py     # R20 — byte-for-byte round trip through the output file
```

## R15 — The phone pattern and its cost

**Decision**: one new alternative in the existing single compiled pattern:

```python
_PHONE = r"\+[0-9]{8,15}(?![0-9])"
```

`[0-9]` rather than `\d`, consistently with `_CARD_RUN`: FR-019 says *decimal digits* and A-4 limits
the rules to ASCII, while `\d` also matches non-ASCII decimal digits. The `{8,15}` bounds are
FR-019's inclusive range. The negative lookahead is FR-020: a candidate may not be followed by a
digit. No lookbehind, because A-14 deliberately places no constraint on what precedes the `+`.

**Rationale**: the bounds are the whole guard against backtracking. `{8,15}` over a single character
class gives at most eight attempts at any start position — the engine tries 15 digits, fails the
lookahead, drops to 14, and so on to 8 — so the work per position is a constant, not a function of
line length. Unlike the email pattern of [R5](../001-logredact-cli/research.md), there is nothing
here that can be re-entered: no nested quantifier, no alternation inside the repetition.

**Measured** (`phone.py`, five adversarial shapes, sizes doubling to the 1 MiB cap):

| Line shape | 48 KiB | 97 KiB | 195 KiB | 390 KiB | 1 MiB |
|---|---|---|---|---|---|
| `+` then one long digit run | 2.6 ms | 5.2 ms | 10.3 ms | 20.8 ms | 56.6 ms |
| `+` repeated | 5.2 ms | 9.3 ms | 20.6 ms | 37.8 ms | 97.7 ms |
| `+` then 16 digits, repeated (worst case for the lookahead) | 11.5 ms | 22.9 ms | 45.3 ms | 99.0 ms | 265.9 ms |
| `+9` alternating | 22.5 ms | 57.4 ms | 78.0 ms | 155.3 ms | 424.9 ms |
| `+` then exactly 15 digits, repeated | 1.0 ms | 2.0 ms | 3.8 ms | 7.3 ms | 19.6 ms |

Every row doubles when the length doubles: linear, as SR-015 requires. The worst case, 425 ms for a
full 1 MiB line, is well inside the 10 s tripwire adopted in
[R14](../001-logredact-cli/research.md) and below the 3.4 s worst case the card scan already costs.
Peak memory is unchanged: `re.sub` is still applied to one line and no match list is accumulated
(SR-015, FR-034).

Throughput on realistic log text (timestamp, email, IPv4, phone number and card per line) measured
7.1 MB/s, up from the 4.7 MB/s recorded in R14 — the measurement is on a faster interpreter, not an
improvement, and the ≥1 MB/s goal holds either way.

**Alternatives considered**: a separate `re` pass for phone numbers — rejected, it would re-scan
text already replaced by a placeholder, which FR-021 forbids, and would double the per-line cost.
An explicit character scan like the card candidate walk — rejected: the card scan exists only
because Luhn and group boundaries cannot be expressed in a regular expression ([R8](../001-logredact-cli/research.md));
a phone number needs neither, so Principle IV prefers the pattern.

## R16 — How FR-021's four-way precedence is delivered

**Decision**: add the alternative between `ip` and `card`, so the written order of the single
compiled pattern is `email | ip | phone | card` — exactly FR-021's order. No rule table, no enum, no
registry; the alternation order *is* the precedence, as in
[R4](../001-logredact-cli/research.md).

**Finding worth recording**: only one of the two new precedence relations is actually decided by the
alternation order.

- **email over phone** *is* decided by it. `+14155552671@example.com` starts at the same position
  for both alternatives, and the first one written wins: measured `[EMAIL]`, counted once as an
  email (FR-021, spec Edge Cases).
- **phone over card** is decided by leftmost matching, not by order. A phone match begins at a `+`
  and a card run begins at a digit, so the two can never start at the same position; `re.sub`
  always takes the leftmost match, which is the `+`. Measured: `+4111111111111` (13 Luhn-valid
  digits) → `[PHONE]`, not `+[CARD]` — A-13's requirement, satisfied even though the relation is not
  what orders the alternatives.
- **phone and IPv4** cannot overlap at all: a phone match contains only `+` and digits, an IPv4
  match requires three dots. A-13 already says the ordering between them is for symmetry.

Writing the alternative in FR-021's position is still the right choice — it makes the code read as
the requirement reads — but a reviewer should know that moving it would not change the output, and
that the test pinning A-13 is therefore load-bearing: it is the only thing that would catch a future
rewrite in which phone and card *could* start at the same position.

**Measured**: 18 of 18 cases drawn from Story 1, Story 3 scenario 1 and the Edge Cases section pass,
including `++14155552671` → `+[PHONE]`, `99+14155552671` → `99[PHONE]`, `+ 14155552671` unchanged,
`+1-415-555-2671` unchanged, and both digit bounds.

## R17 — What the phone rule changes in existing behaviour

SC-012 requires that everything except the two stated changes keeps working, so "which existing
outputs change?" had to be answered by search rather than assumption.

**Decision**: the phone rule changes existing output in exactly one family of inputs — a `+`
immediately followed by 8–15 digits that today form, or begin, a Luhn-valid card candidate. This is
specified behaviour (FR-021, A-13), and it is accepted. One sub-case is a genuine narrowing of
redaction and is recorded here so it is a visible choice rather than an accident.

**Measured** (`overlap.py`, exhaustive over first-group lengths 8–15 and total lengths 13, 14 and 19,
both separators):

| Input | Today | After the amendment |
|---|---|---|
| `+4111111111111` | `+[CARD]` | `[PHONE]` — A-13, intended: the `+` is consumed |
| `+4111111111111111` (16 digits) | `+[CARD]` | `+[CARD]` — unchanged; the phone rule cannot fire |
| `+12345678 4111 1111 1111 1111` | `+12345678 [CARD]` | `[PHONE] [CARD]` — both values still removed |
| `+41111111 11119` | `+[CARD]` | `[PHONE] 11119` — **five digits of a card candidate remain** |

38 constructed inputs fall in the last row's shape. The mechanism: a card candidate must begin at a
digit group's first digit, and when that first group is 8–15 digits long the phone rule takes it
first; FR-021 forbids re-scanning the replacement, so the remaining groups are too short to form a
candidate on their own and survive as digits.

**Why this is accepted rather than designed around**:

1. It follows directly from FR-021 plus FR-021's no-re-scan clause. Avoiding it would require the
   card rule to win an overlap with the phone rule, which FR-021 explicitly forbids, or a
   backtracking "try the other kind" search that Principle IV rules out.
2. Real card groupings (4-4-4-4, or 4-6-5 for Amex) never have an 8–15 digit first group, and an
   unseparated 16–19 digit card after a `+` is unaffected, as the table's second row shows. The
   reachable real-world case is the one A-13 names and intends.
3. No digit of the *phone number* survives, which is what SR-006 and SC-013 require of the winning
   kind.

A test pins `+41111111 11119` so the choice is asserted, not merely argued. If the requester wants
the card to win that overlap instead, it is an amendment to FR-021 and a reordering of two
alternatives — one line plus one test.

**Also measured**, as the counterpart: a 48-line corpus of genuine international numbers (8–15
digits, at the start, middle and end of a line, and beside an email) is 100% redacted with no
fragment surviving (SC-013), and an 11-line near-miss corpus (`+` with 7, 16 and 20 digits, no `+`,
`+` then a space or a letter, separator-grouped, bare `+`, `++`) has 0 phone redactions (SC-014).

## R18 — `--out-dir` in the strict allowlist, and a repeated `--out-dir`

**Decision**: `parser.add_argument("--out-dir", dest="out_dir", action="append", metavar="DIR")`,
with a second occurrence rejected as a usage error.

**Measured** (`fsprims.py`): the existing parser's `add_help=False, allow_abbrev=False` settings
([R9](../001-logredact-cli/research.md)) already deliver everything SR-016 asks for, with no new
validation code:

| Argument vector | Result |
|---|---|
| `--out-dir clean a.log` | accepted, `out_dir=['clean']` |
| `--out-dir=clean a.log` | accepted — A-21's second form, for free |
| `--count --out-dir c a.log` | accepted, both options together (FR-032) |
| `-- -weird.log` | `-weird.log` is an operand, unchanged (C-20) |
| `--out_dir c a.log` | rejected, status 2 — Story 4 scenario 8 |
| `--out c a.log` | rejected, status 2 — Story 4 scenario 8 |
| `--out-di c` | rejected, status 2 — no abbreviation (SR-016) |
| `--out-dir` (no value) | rejected, status 2 — Story 4 scenario 9 |
| `--out-dir ""` | accepted by the parser, `out_dir=['']` — rejected later by FR-029, see R19 |

**The ambiguity**: FR-023 says `--out-dir` is accepted "at most once per invocation", and SR-016
says "`--out-dir` with one value", but neither states what the tool does when it appears twice.
Two readings, with materially different behaviour:

- *Last one wins* (argparse's default `store` action). Consistent with the existing treatment of a
  repeated `--count`, which is accepted today and is idempotent.
- *Reject the second occurrence.* Chosen. A repeated `--count` is harmless because both occurrences
  mean the same thing, whereas `--out-dir a --out-dir b` expresses two different intents and
  silently honouring one of them writes files somewhere the caller may not have meant. That is the
  "silent wrong answer" Principle II calls the highest-severity defect, and FR-023's "at most once"
  reads as a constraint the tool should enforce rather than a note to the reader.

`action="append"` is how this is detected: `len(args.out_dir) > 1` is a usage error. It costs two
lines and no new abstraction. Reversing the decision — if the requester prefers last-one-wins — is
deleting those two lines and one test. A repeated `--count` keeps its current behaviour, because
FR-035 requires everything not named by this spec to stay exactly as it is.

## R19 — Creating DIR and its missing parents at owner-only permissions

**Decision**: walk the missing ancestors and create each with `os.mkdir(path, 0o700)`, innermost
last. Do **not** use `os.makedirs(dir, mode=0o700, exist_ok=True)`.

**Rationale, measured**: `os.makedirs`'s `mode` has applied only to the leaf directory since Python
3.7. With umask 0o022, `os.makedirs("a/b/c", mode=0o700)` produced:

```
0o755  a
0o755  a/b
0o700  a/b/c
```

SR-011 requires *every* directory the tool creates to be owner-accessible only, and Story 2
scenario 4 has the tool create all three components of `a/b/c`. So `makedirs` would leave two
group- and world-readable directories holding redacted log data — a direct SR-011 and SC-020
failure, and exactly the kind of defect that only shows up in a permission assertion. The
per-component walk measured `0o700` on all three.

`os.mkdir`'s mode is masked by umask, which can only *remove* bits, so `0o700` is an upper bound: a
stricter umask yields something stricter still, never anything wider. That is why the test asserts
`mode & 0o077 == 0` rather than equality with `0o700` — it holds under any umask.

The walk also settles FR-029's failure cases without a separate validation pass, because the final
`os.mkdir` on DIR itself produces the diagnosis (measured):

| DIR | Outcome |
|---|---|
| already a directory | nothing created, used as it is (FR-025) |
| `a/b/c`, none existing | all three created at `0o700` (Story 2 scenario 4) |
| an existing regular file | `FileExistsError`, "File exists" — FR-029, Story 4 scenario 2 |
| `""` (empty value) | `FileNotFoundError`, "No such file or directory" — FR-029, spec Edge Cases |
| parent denies write | `PermissionError`, "Permission denied" — Story 4 scenario 3 (see R25) |

The diagnostic is assembled by the caller as `cannot create output directory 'DIR': REASON`, with
DIR being the string from the command line and REASON the operating system's `strerror`, so a
failure at an intermediate component still names DIR as given, which is what FR-029 requires.

**Alternatives considered**: `os.makedirs` followed by `chmod` on each created directory — rejected,
the Security Baseline requires permissions to be set at creation rather than relaxed and tightened
afterwards, and a reader with `0o755` in hand during the window between the two calls is exactly
what that rule exists to prevent. Setting `umask(0o077)` around a single `makedirs` call — rejected,
it mutates process-global state to achieve what a three-line loop achieves locally.

**Race**: a concurrent creator can win between the `isdir` check and the `mkdir`. The resulting
`FileExistsError` is reported as an error rather than silently tolerated; this is loud, not wrong,
and the spec describes no concurrent use.

## R20 — Opening an output file: one call for SR-010, SR-011 and FR-026

**Decision**:

```python
fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
handle = open(fd, "w", encoding="utf-8", errors="surrogateescape", newline="")
```

One system call satisfies four requirements at once, with no check-then-act window:

| Flag / argument | Requirement |
|---|---|
| `O_NOFOLLOW` | SR-010 — a symlink at the output path is refused, not followed out of DIR |
| `0o600` | SR-011 — owner-read/write at creation, never relaxed afterwards |
| `O_CREAT` without `O_EXCL` | FR-026 — an existing file is reused, not refused |
| `O_TRUNC` | FR-026 — its content is replaced in full, with no remnant |
| `OSError` | FR-030 — any failure is reported, naming the output path |

**Measured** (`fsprims.py`, `writer.py`):

- A new file is created `0o600` under umask 0o022.
- A pre-existing `0o644` file **keeps** `0o644` and is truncated to the new, shorter content (6
  bytes) — both halves of SR-011's second sentence and of Story 2 scenario 5, from one call. The
  mode argument applies only on creation, so the tool cannot widen or narrow a file its owner
  already manages.
- A symlink at the output path pointing outside DIR is refused with `ELOOP` ("Too many levels of
  symbolic links") and its target is left untouched — SR-010 and the corresponding Edge Case.
- A **dangling** symlink pointing outside DIR is also refused, and the target is *not* created.
  This matters: without `O_NOFOLLOW` this is the case that silently writes redacted data outside
  DIR, since there is no existing file for a check to notice.
- The text wrapper over the descriptor reproduces input byte-for-byte, including an invalid UTF-8
  byte (`\xe9`), a `\r\n`, a lone `\r`, and a missing final terminator — the FR-009 and A-4
  guarantees survive the new destination, because the settings are the same `STREAM_SETTINGS`
  already used for stdin and stdout (R3).
- A write to a full device surfaces as `OSError` "No space left on device" on `close`, which is why
  the operand is counted only after the handle has closed cleanly (FR-030, and SR-009's reasoning
  from [R12](../001-logredact-cli/research.md)).

**Note on strictness**: `O_NOFOLLOW` refuses *every* symlink at the output path, including one that
resolves to a regular file inside DIR. SR-010 only requires refusing those that resolve outside,
and the constitution permits a feature to be stricter than the baseline. Distinguishing the two
would need a resolve-and-compare dance with its own race window, for the sake of a case no
requirement asks for; Principle IV says do not build it.

**Alternatives considered**: `open(out_path, "w")` plus `os.chmod` — rejected, it widens a file to
the umask default before narrowing it (Security Baseline) and would overwrite the permissions of a
pre-existing file. `os.path.islink()` then `open()` — rejected, a check-then-act window where
`O_NOFOLLOW` has none. Writing to a temporary file and renaming — forbidden outright by SR-013 and
A-25.

## R21 — Proving the output path is not the input, before truncating it

**Decision**: open the input first, and before opening the output compare the *already-open* input
descriptor with the output path:

```python
try:
    collision = os.path.samestat(os.fstat(handle.fileno()), os.stat(out_path))
except FileNotFoundError:
    collision = False
```

**Rationale**: SR-012 requires the tool to establish that the output path is not the operand
*before any truncation of it could occur*, and `O_TRUNC` truncates during `os.open`. So the check
must precede the output open, and it must be on identity rather than on strings: `--out-dir .` with
operand `app.log`, `--out-dir /abs/dir` with operand `/abs/dir/app.log`, and a hard link all name
the same file by different paths. Comparing `st_dev`/`st_ino` catches all of them; comparing
normalised path strings catches none reliably.

Using `os.fstat` on the open input descriptor, rather than `os.stat` on the operand, removes the
input side of the race: whatever the operand pointed at when it was opened is the file being read
and the file being protected.

**Measured** (`fsprims.py`), with the input file's content verified intact afterwards:

| Output path | `samestat` | Outcome |
|---|---|---|
| the operand itself (`--out-dir .`) | `True` | refused — FR-036, Story 4 scenario 6 |
| a hard link to the operand | `True` | refused — beyond what FR-036 states, and correct |
| a symlink to the operand | `True` | refused (and `O_NOFOLLOW` would refuse it too) |
| does not exist | `False` | written normally |
| an unrelated existing file | `False` | replaced normally (FR-026) |

Opening the input first also means FR-028 is satisfied by construction: an operand that cannot be
opened never reaches the output stage, so no output file is created for it.

An `OSError` other than `FileNotFoundError` from `os.stat` (for example a permission failure on a
component of DIR) is reported under FR-030 rather than ignored — Principle II forbids swallowing it.

## R22 — When `wrote N files` is written, and what a mid-file failure leaves behind

A-17 and A-18 settle most of this; they are restated here only where the implementation needs them,
plus one gap the spec does not cover.

**Decided by the spec**:

- The line is written when every operand has been processed, including a run where some operand
  failed, with N counting only outputs actually written (A-17, FR-027, FR-028).
- It is **not** written when the run stopped before processing every operand: an over-length line
  (FR-033), a rejected argument (SR-016), a DIR that cannot be created (FR-029), or `--out-dir` with
  no operand (FR-031).
- Two operands sharing a final path component report `2` though one file remains (A-18, FR-026).
- The `--count` tally keeps its stricter rule — written only on a run exiting 0 (A-17), so with a
  failed operand the run writes `wrote N files` but no tally.

**The gap**: FR-028 says the tool "MUST NOT create an output file" for an operand that cannot be
*opened or read*. For an operand that opens and then fails mid-read (an I/O error after some lines),
the output file already exists and holds the lines read so far.

**Decision**: the partially written output file stays, the operand is not counted in N, the failure
is reported naming the input, and the run exits 2. Un-creating it would mean deleting a file, which
no requirement asks for and which a crash could not guarantee anyway; staging through a temporary
file is forbidden by SR-013 and A-25. This is the same posture A-25 takes for a run stopped by an
over-length line: a short output file can exist, and the non-zero status plus the missing or
undercounted `wrote N files` line is what tells the caller not to trust the folder. Reversible by
adding an `os.unlink` on that path, if the requester prefers it.

**Counting rule, stated precisely** so it is testable: an operand is counted when its input stream
reached end-of-file without a read error **and** its output handle flushed and closed without an
error. Anything else is not counted.

## R23 — `--out-dir` with no operand

**Decision**: detect it after parsing and report it with the existing `_error` helper, returning
`EXIT_ERROR` — not through `parser.error()`.

**Rationale**: both give exit status 2, which is what FR-031 requires. `parser.error()` raises
`SystemExit` from inside the run, which would break `main`'s documented contract ("Returns the
process exit status") and give this one usage error a different shape (an argparse usage block) from
the diagnostic every other in-run failure produces. The check must also run *before* DIR is
created, so that FR-031's "DIR not created" and "standard input not read" both hold; placing it
immediately after parsing achieves that.

Diagnostic: `python -m logredact: error: --out-dir requires at least one FILE operand`. It names
only the option, so SR-017 is satisfied trivially.

## R24 — Flush ordering of the two summary lines

**Decision**, when both options are given: close each output file as its operand finishes → write
`wrote N files` to stdout → flush stdout → write the tally to stderr.

**Rationale**: FR-022 keeps the tally's timing from FR-010 ("after all redacted output has been
written and flushed"), and A-3 wants a caller watching both streams to see the complete output
first. With `--out-dir` the redacted output is in files, so "written and flushed" means every output
handle is closed; `wrote N files` is itself stdout content and so must precede the tally too. The
existing single `out.flush()` before the tally in `_run` already sits at the right point — the
ordering falls out of writing the count line just before it.

This also keeps FR-030 enforceable: each output handle is closed as its operand finishes, so a
flush failure is attributed to the right operand and excluded from N before the count line is
written.

## R25 — Test strategy for permissions, confinement and the memory bound

The harness from [R13](../001-logredact-cli/research.md) — run the real `python -m logredact` in a
subprocess, compare raw bytes on stdout and stderr plus the exit status — carries over unchanged.
Three things in this feature need more than that:

**Permissions (SR-011, SC-020)**: assert `stat.S_IMODE(mode) & 0o077 == 0` on every file and
directory the tool creates, for both DIR and its parents. The mask form is umask-independent (R19).
A pre-existing output file is created `0o644` by the test and must still be `0o644` afterwards.

**Confinement (SR-010)**: create a symlink at the output path pointing to a file outside DIR, and
assert the run exits 2, names the output path, and leaves the target's bytes unchanged. Repeat with
a **dangling** symlink and assert the target was not created — the case that would otherwise pass
unnoticed.

**No file is ever opened for writing outside DIR and stdout (SR-013)**: snapshot the tree before
and after, as `test_no_files_created_or_modified` already does for 001, and additionally assert that
no path outside DIR changed mtime or size.

**Skipped as root (reported, not hidden)**: Story 4 scenario 3 (a parent directory that denies write
permission) and Story 4 scenario 5 (an output file that cannot be opened for writing) rely on
permission bits that root bypasses — measured: `os.mkdir` under a `0o500` parent *succeeded* as
root. The suite already has this situation and handles it with
`@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses file permissions")`
(`test_cli_errors.py:176`); the new tests use the same marker. The constitution requires a skipped
test to be reported rather than hidden, so the implementation gate must state that these two are
skipped when the suite runs as root — as it does in this environment — and that FR-029's and
FR-030's permission paths are therefore covered only by the other failure shapes (an existing
regular file at DIR, an empty DIR value, a symlinked output path, and `/dev/full`) unless the suite
is also run as a non-root user.

**SC-018 memory bound**: reuse the `test_resource_bounds.py` approach — at least 50 operands whose
total size is at least 100 MiB, with peak RSS sampled in the child — and assert the peak stays in
the same band as a single-operand run. The design makes this true by construction: one line and one
open output handle at a time (FR-034).

## R26 — Awkward operand basenames

**Decision**: the output name is `os.path.basename(operand)` with no further validation, because the
input is opened first and every awkward shape fails there or at the output open.

**Measured** (`fsprims.py`, `writer.py`):

| Operand | `basename` | What happens |
|---|---|---|
| `logs/2026/app.log` | `app.log` | written to `DIR/app.log` — FR-024, Story 2 scenario 3 |
| `/etc/passwd` | `passwd` | written to `DIR/passwd`; absolute operands contribute no path (SR-010) |
| `logs/` | `""` | the input open fails (`Is a directory`) before any output path is used |
| `.` / `..` / `a/..` | `.` / `..` / `..` | likewise; and `os.open` on such a path inside DIR gives `Is a directory` |

So no separate basename validation is needed, and none is added (Principle IV). `os.path.basename`
is a pure string operation — it does not resolve, normalise or follow anything, which is what SR-010
requires of path assembly: DIR plus one component, nothing from the input data.
