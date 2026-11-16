# Phase 0 Research: Phone Redaction and Output Folder

**Branch**: `002-phone-redaction-out-dir` | **Date**: 2026-11-16 | **Spec**: [spec.md](./spec.md)

Purpose: resolve every technical unknown in the specification before design, and verify each
decision against the **existing** implementation rather than against a fresh design — this feature
amends a working tool, and spec Context requires every other behaviour to stay byte-identical.

Each section states a Decision, a Rationale, and the Alternatives considered. Where a decision was
executed before being written down, the evidence is recorded.

**Prototype evidence**: the combined pattern and scan loop below were run against all 19 concrete
phone examples in the spec (User Story 1 scenarios, User Story 3 scenario 1, and every Edge Case
bullet under "Phone recognition") plus 8 regression cases drawn from feature 001's contract —
**27/27 produced the specified text and tally** before this document was written. Filesystem
behaviour (`os.makedirs`, truncation, collision errors, `basename`), `argparse` intermixed parsing of
`--out-dir`, output-file byte fidelity, and throughput were likewise executed, not assumed.

## Summary of unresolved items entering Phase 0

| # | Item | Status |
|---|------|--------|
| R1 | Phone grammar as a regular expression, including the over-long-run rule | Resolved |
| R2 | Where the phone alternative goes in the existing combined pattern | Resolved |
| R3 | Tally shape: `redact_line` returns a 3-tuple today, needs four counts | Resolved (SC-004 nuance flagged) |
| R4 | `--out-dir` parsing alongside `parse_intermixed_args` | Resolved |
| R5 | Output file naming from a `FILE` operand | Resolved |
| R6 | Directory creation: mechanism and *when* it happens | Resolved |
| R7 | Open ordering, and attributing a failure to the input or the output path | Resolved (residual window recorded) |
| R8 | `--out-dir` with zero operands | Resolved |
| R9 | Byte fidelity of output files | Resolved |
| R10 | `wrote N files` — counting rule and ordering against the `--count` summary | Resolved |
| R11 | Performance and flat memory with the fourth category and with `--out-dir` | Resolved |
| R12 | Testing an unwritable output directory when the suite runs as root | Resolved |

---

## R1. Phone grammar as a regular expression

**Decision**:

```python
PHONE = r"\+\d{8,15}(?!\d)"
```

Replacement `[PHONE]`. A literal `+`, then 8–15 digits, then a guard that the run does not continue
with a further digit.

**Rationale**:

- FR-002 is "a `+` followed immediately by an unbroken run of 8 to 15 digits", which `\+\d{8,15}` is
  verbatim. No separator class, no optional spacing: the spec's Assumptions fix the grammar to
  exactly this form and warn that a broader one risks redacting ordinary numeric log data.
- The trailing `(?!\d)` is what implements FR-003. Without it, `+1234567890123456` (16 digits) would
  match its first 15 digits and the tool would emit `[PHONE]6` — redacting a *fragment*, which FR-003
  forbids. With it, the engine tries 15, 14, … 8 digits at the `+`, every attempt is followed by a
  digit, all fail, and because `\+` requires a literal `+` **no interior offset can match either** —
  so the whole run is reproduced unchanged. Verified: `ref +1234567890123456` is returned untouched
  with a zero tally.
- No *leading* guard (`(?<!\d)` or similar) is added. FR-002 conditions the match on the `+` and what
  follows it, and nothing in the spec excludes a `+` that happens to follow another character. Adding
  a lookbehind would be unrequested machinery (Principle IV) and could only *reduce* redaction.
- The 8 and 15 boundaries are inclusive and come straight from the quantifier, so `+12345678` and
  `+123456789012345` both match and `+1234567` does not. Verified.
- A broken run needs no special rule: `+ 14155552671` and `+1 415 555 2671` simply fail `\d{8,15}`
  immediately after the `+`, and the remaining digit runs are then judged by the unchanged card rule,
  which rejects them on length. Verified unchanged.

**Alternatives considered**:

- `\+\d{8,15}\b` — rejected: `\b` after a digit is satisfied by any non-word character, but
  `+12345678901234567`'s 15-digit prefix is followed by a digit, which is a word character, so `\b`
  would also fail there. It behaves identically in the cases at hand but is weaker in intent and
  additionally fails before `_`, which has nothing to do with the length rule.
- `\+\d{8,15}(?![\d])` with a leading `(?<!\d)` — rejected as above: not required, reduces redaction.
- Matching a maximal run `\+\d+` and length-checking it in code, mirroring the card rule — rejected:
  the card rule *needs* code validation because Luhn is not expressible in `re`, whereas a length
  range is. Pushing the check into Python would add a second rejectable candidate and a second
  restart path in the scan loop for no gain (Principle IV).

## R2. Placement of the phone alternative in the combined pattern

**Decision**:

```python
COMBINED = re.compile(
    f"(?P<email>{EMAIL})|(?P<ip>{IP})|(?P<card>{CARD})|(?P<phone>{PHONE})"
)
```

The phone alternative is **appended** after the three existing ones. The scan loop, the card
rejection/restart rule, and `match.lastgroup` dispatch are reused unchanged.

**Rationale**:

- Python's `re` prefers the leftmost match and, among alternatives starting at the same offset, the
  first one listed. Feature 001 already relies on exactly this (contracts/redaction-rules.md), so
  FR-004's precedence is obtained by ordering, with no new code.
- **Email must precede phone, and this is load-bearing.** The email local part already admits `+`,
  so `+14155552671@example.com` has an email candidate *and* a phone candidate starting at the same
  offset. Executed both ways: with email first the match is the whole `+14155552671@example.com` as
  `email`; with phone first it is `+14155552671` as `phone`, producing `[PHONE]@example.com` and
  violating FR-004. The existing order already places email first, so appending phone satisfies this
  automatically.
- **Phone's position relative to `ip` and `card` is behaviourally irrelevant**, because a phone
  candidate starts at a `+` while both an IPv4 and a card candidate start at a digit — they can never
  begin at the same offset. Executed `email|ip|card|phone` and `email|phone|ip|card` over
  `+378282246310005`, `+4111111111111111`, `+1.2.3.4`, `+12345678`, `1.2.3.4`: identical results.
  Appending is therefore chosen for the smaller diff and because it keeps the documented
  email→IPv4→card order of feature 001 literally intact.
- **Phone beats card by leftmost match, with no special case.** For `+378282246310005` the phone
  candidate starts at offset 0 and the card candidate at offset 1, so `search` finds the phone first:
  `[PHONE]`, as the spec's Edge Cases require. For `+4111111111111111` (16 digits) no phone candidate
  exists, the card candidate at offset 1 wins, and the result is `+[CARD]` — also as required. Both
  verified.
- **The card rejection/restart rule still prevents fragments.** After a rejected over-long card
  candidate the loop restarts one character in, but `CARD`'s `(?<!\d)` lookbehind — which `re`
  evaluates against the real string, not from the `pos` argument — blocks every interior digit
  offset. Verified: `+1234567890123456` and `+1234567890123456789012` both come back untouched.
- `PHONE` contains no capturing group, so `match.lastgroup` continues to name the matched category
  unambiguously.

**Alternatives considered**: a separate pre-pass or post-pass for phones (rejected — two passes
cannot express "no text reused" and would let a phone redaction eat part of an email); a fourth
pattern matched position-by-position (rejected for the same reason feature 001 rejected it in
research R2 — it moves scanning out of the C engine).

## R3. Tally shape: three counters become four

**Decision**: `redact_line` returns `tuple[str, tuple[int, int, int, int]]`, the counts ordered
`(emails, ips, cards, phones)` — matching the field order of the summary line in FR-006. The CLI
keeps four plain `int` accumulators.

**Rationale**: FR-006 fixes both the four categories and their order, so a 4-tuple in that order is
the smallest value that carries the tally, and `phones` appended last keeps positional access to the
first three stable. No `dict`, `Counter`, `NamedTuple`, or class is introduced: the spec fixes the
set of categories at four and offers nothing to configure, so a keyed structure would add indirection
with no second value (Principle IV).

**Known cost, flagged for the spec owner**: SC-004 says the existing test suite passes "updated only
for that format change". Changing the tuple's arity means ~20 assertions in `tests/test_redact_line.py`,
`tests/test_luhn.py` and `tests/test_performance.py` that compare against 3-tuples
(`assert counts == (1, 0, 0)`, `text, (emails, ips, cards) = redact_line(...)`, and one explicit
`len(counts) == 3`) must also gain a fourth element. These are unit assertions on an internal
function, not acceptance scenarios: **no asserted behaviour changes**, each edit appends ` 0` or a
fourth name. The reading taken here is that SC-004 constrains externally observable behaviour — where
the summary line is indeed the single change — and that mechanical arity updates to internal unit
tests are in scope. Recorded because SC-004's literal wording is narrower than that.

**Alternatives considered**: keeping a 3-tuple and returning phones separately (rejected — two return
channels for one tally); making the counts object compare equal to a 3-tuple (rejected — machinery
whose only purpose is to avoid editing tests).

## R4. `--out-dir DIR` and `parse_intermixed_args`

**Decision**:

```python
parser.add_argument("--out-dir", metavar="DIR", default=None,
                    help="write each FILE's redacted lines to DIR/<name> instead of standard output")
```

`argparse` derives `args.out_dir` from the option name; no `dest` is needed. The existing
`parse_intermixed_args` call is kept.

**Rationale**: FR-019 requires the option in any position among the operands, in any combination with
`--count`. Feature 001 already uses `parse_intermixed_args` for that reason (a plain `parse_args`
rejects `a.log --count b.log` against a `nargs="*"` positional). A value-taking store option is
compatible with it — executed `a.log --out-dir clean b.log`, `--out-dir clean a.log`,
`a.log b.log --out-dir clean --count`, `--count a.log --out-dir clean`, `--out-dir=clean a.log`, and
`--out-dir clean`: all parsed with the operand list and `--count` flag intact. A missing value
(`--out-dir` with nothing after it) is rejected by `argparse` with a usage message and exit 2, which
is the existing FR-005 contract for a malformed command line.

**Alternatives considered**: hand-rolled parsing (rejected — argparse already satisfies the
requirement); `nargs=1` (rejected — would make the value a one-element list for no reason).

## R5. Output file naming

**Decision**: `os.path.basename(name)` of the `FILE` operand, joined to `DIR` with `os.path.join`.

**Rationale**: FR-009 is "only the final name component … discarding any directory part", which is
`basename`. Executed: `logs/app.log` → `app.log`, `app.log` → `app.log`,
`/var/log/app.log` → `app.log`, `./a//b.log` → `b.log`. The degenerate results —
`basename("logs/") == ""` and `basename(".") == "."` — are unreachable as *successful* writes,
because such an operand is a directory and its input `open()` fails first with `IsADirectoryError`
(verified), which is the pre-existing FR-015 path: `cannot read 'logs/'`, exit 2.

Two operands sharing a basename need no special handling: each is processed in turn, the second
`open(..., "w")` truncates the first's output, and the counter still increments twice — which is
exactly the spec's "both map to the same name … reports `wrote 2 files`".

**Alternatives considered**: `pathlib.Path(name).name` (equivalent; `os.path` is already imported by
`cli.py`, so no new import); de-duplicating or disambiguating colliding names (rejected — the spec
explicitly specifies replacement and double counting).

## R6. Creating the output directory, and when

**Decision**: `os.makedirs(args.out_dir, exist_ok=True)`, called **once**, after the zero-operand
check of R8 and before the first input is opened. Failure is reported as a write failure (R7).

**Rationale**:

- FR-010 is "create `DIR` together with any missing parent directories … use an existing directory
  as-is", which is `makedirs(..., exist_ok=True)` exactly. Verified: nested `a/b/c` created; a second
  call on the existing path succeeds silently.
- Creating it once, up front, means a bad destination is diagnosed before any input is read, so the
  tool does not do work it must throw away. It also keeps FR-018's "no folder created" guarantee easy
  to honour: the zero-operand check runs first.
- The "path exists but is not a folder" edge case is handled by `makedirs` itself: `exist_ok=True`
  suppresses `FileExistsError` only when the existing path *is* a directory. Verified against a
  regular file — `FileExistsError`, `errno 17`, `strerror "File exists"`, `filename` set to the
  path — which supplies both halves of the FR-017 diagnostic (path and reason).
- `--out-dir ""` raises `FileNotFoundError` from `makedirs` (verified) and so becomes an ordinary
  FR-017 failure rather than a silent no-op.

**Alternatives considered**: creating the directory lazily before the first write (rejected — the
diagnostic would arrive after output had already been produced, and the zero-operand and bad-path
cases become harder to keep distinct); `os.mkdir` plus a manual parent walk (rejected — `makedirs`
is the stdlib answer); pre-checking with `os.path.isdir` and then creating (rejected — a
check-then-act race, and `exist_ok=True` already encodes the intent).

## R7. Open ordering and failure attribution

**Decision**: per `FILE` operand, in this order:

1. `open(name, **_STREAM_KWARGS)` — the input. An `OSError` here is the **input** failure of FR-015:
   `logredact: cannot read '<name>': <reason>`, exit 2. Unchanged from today.
2. `open(os.path.join(dir, basename), "w", **_STREAM_KWARGS)` — the output, opened **only after step
   1 succeeded**. An `OSError` here is the **output** failure of FR-017:
   `logredact: cannot write '<path>': <reason>`, exit 2.
3. Stream line by line, redacting; close the output before the next input is opened.

Errors are attributed by the operation that raised them, not by guesswork: the read loop's `OSError`
names the input, and the output `open`, each `write`, and the close name the output path. Guarding an
individual `dest.write(...)` costs nothing at run time under Python 3.11+ zero-cost exception
handling, so exact attribution does not trade against SC-010.

**Rationale**:

- Step 2 *after* step 1 is what satisfies the spec's "No output file is created for an input that
  cannot be read": every unreadable-input case the suite can construct — missing file, permission
  denied, a directory operand, an over-long path — fails at `open()`, before any output file exists.
  Verified that a directory operand raises `IsADirectoryError` at open rather than at read.
- Only one input and one output are open at a time, which is the spec's stated assumption and keeps
  memory flat in the number of operands (SC-010).
- FR-015 and FR-017 demand *different* diagnostics naming *different* paths, and only the raising
  operation knows which path is at fault — that one sentence is the justification Principle IV
  requires for splitting the handlers.
- FR-016's second half ("retain the output files already written for earlier operands") needs no
  code: earlier outputs are closed before the failing operand is reached.

**Residual window, accepted and recorded**: if both opens succeed and an I/O error then occurs
mid-stream (ENOSPC, a hardware error), the run still fails loudly — diagnostic naming the offending
path, exit 2, no `wrote N files`, no summary — but a partially written output file may remain, which
is narrower than the Edge Cases phrase "leaves no empty or partial file of that name behind". Nothing
is built to remove it, because the removal could not be covered by a test: on a successfully opened
regular file, read and write failures cannot be provoked in-suite without exotic, platform-specific
devices, and Principle III makes untestable machinery incomplete work while Principle IV forbids
building it speculatively. The edge case as *titled* — "No output file is created for an input that
cannot be read" — is fully satisfied by the ordering rule above.

**Alternatives considered**: writing to a temporary file in `DIR` and `os.replace`-ing it into place
(rejected — leaves stray temp files on an abnormal exit, needs the same unlink it was meant to avoid,
and FR-011 does not ask for atomic replacement); opening the output first (rejected — leaves an empty
file for an unreadable input, the precise thing the Edge Cases forbid); inferring the faulting path
from `OSError.filename` (rejected — verified set for `open()` failures but not for mid-stream
read/write errors, so it cannot carry the attribution).

## R8. `--out-dir` with zero `FILE` operands

**Decision**: checked in `_run` before anything else happens — before `makedirs`, before any stream
is touched:

```text
logredact: --out-dir requires at least one FILE
```

on stderr, exit 2.

**Rationale**: FR-018 requires all four of a diagnostic, no directory created, standard input not
read, and exit 2. Placing the check first gives all four at once. The message states what was
expected, as Principle II requires. It is written directly rather than via `parser.error()` so the
text is the specified sentence rather than a usage block, and so the check lives next to the logic it
protects; the exit status is 2 either way.

**Alternatives considered**: reading standard input and inventing a name such as `stdin.log`
(rejected — the spec forbids it, and it would silently guess at the user's intent); ignoring
`--out-dir` and writing to standard output (rejected — Principle II forbids proceeding as if an
option the user gave did not exist); an argparse mutually-exclusive/required construct (rejected —
cannot express "required only when another option is present", and `parse_intermixed_args` does not
support mutually exclusive groups).

## R9. Byte fidelity of output files

**Decision**: open each output with the *same* `_STREAM_KWARGS` already used for inputs and standard
output — `encoding="utf-8"`, `errors="surrogateescape"`, `newline=""` — plus mode `"w"`, and write
each redacted line with `write()`.

**Rationale**: FR-014 requires an output file to contain exactly what standard output would have
received, so the only safe answer is the identical text layer. `newline=""` suppresses newline
translation on the way out as well as in, and `surrogateescape` on an output encoder converts the
lone surrogates produced by undecodable input bytes back to those exact bytes. Executed on input
containing `\r\n`, the invalid UTF-8 bytes `\xff\xfe`, a tab-and-trailing-space line, and a final
line with no newline: the output file was **byte-identical** to the input. `write()` rather than
`print()` for the same reason as today — `print` would invent a trailing newline. Mode `"w"`
truncates, which is FR-011 ("retaining none of its previous content"); verified that a 9-byte file
rewritten with 3 bytes contains only the 3.

**Alternatives considered**: binary mode with manual encoding (rejected — duplicates what the text
layer already does correctly and diverges from the stdout path); `newline="\n"` or default newline
handling (rejected — would translate `\r\n`, breaking FR-014).

## R10. `wrote N files`: counting and ordering

**Decision**: a single `int` counter incremented once per `FILE` operand whose output file was
written and closed successfully. After the loop completes with no failure:

1. `sys.stdout.write(f"wrote {count} files\n")`
2. `sys.stdout.flush()`
3. if `--count`, the summary line on stderr.

**Rationale**:

- FR-012 requires the line after *all* output files are written, so it is emitted after the loop, not
  inside it. FR-013 is satisfied because nothing else is ever written to stdout in this mode.
- The literal `files` for every N, including `wrote 1 files`, is the spec's explicit instruction —
  not a bug to fix.
- Counting one write per operand (not per distinct name) is the spec's stated assumption, and it is
  what the natural loop produces.
- The existing single pre-summary `flush()` already guarantees the spec's ordering of the tally after
  the status line; it moves from inside the `if args.count:` block to just before it, so the status
  line is flushed in both modes. There is still no per-line flush (feature 001 research R9).
- A failing operand returns before this block, so neither the status line nor the summary is produced
  (FR-015, FR-007) — the same early-return shape the current code uses to suppress the tally.

**Alternatives considered**: pluralising the word (rejected — contradicts the spec); printing the
line incrementally per file (rejected — contradicts FR-012's ordering and FR-013's "only the
`wrote N files` line").

## R11. Performance and memory

**Decision**: no performance work is needed; the existing line-at-a-time design carries over.

**Evidence** (same machine, CPython 3.13.17, 100,000 iterations of the dense quickstart line):

| Engine / input | Time for 100k lines | Budget |
|---|---|---|
| Current 3-category engine, current dense line | 0.94 s | 10 s |
| 4-category engine, same line | 0.90 s | 10 s |
| 4-category engine, dense line **plus** a phone number | 0.96 s | 10 s |

Adding a fourth alternative is free in practice: it is a literal-`+`-anchored branch that the engine
discards immediately at every non-`+` position. Copying 100,000 lines through the text layer into an
output file took 0.04 s, so `--out-dir` is not measurable against the budget. Memory stays flat: one
line at a time, one input and one output open at a time, four `int` counters and one `int` file
count, regardless of operand count (SC-010).

**Alternatives considered**: none needed — nothing in this feature changes the asymptotics.

## R12. Testing an unwritable output destination under root

**Problem**: the suite may run as uid 0, which bypasses permission bits — the trick feature 001 used
for its permission-denied test. `chmod 0o500` on an output directory is therefore not enough on its
own to exercise FR-017.

**Decision**: cover FR-017 with failures that are **privilege-independent**, and keep the
permission-bit case using the existing probe pattern:

| Setup | Error provoked | Privilege-independent |
|---|---|---|
| `--out-dir` names an existing **regular file** | `FileExistsError` "File exists" from `makedirs` | yes — verified |
| `DIR/<basename>` already exists as a **subdirectory** | `IsADirectoryError` "Is a directory" from `open(..., "w")` | yes — verified |
| `--out-dir` path with an over-long component | `ENAMETOOLONG` from `makedirs` | yes — same trick as 001's `test_fr021_an_unopenable_path_names_it_and_exits_two` |
| `DIR` chmod `0o500` | `PermissionError`, or success under root | no — probe first, assert the matching contract, as 001 does |

**Rationale**: constitution gate 2 forbids skipped tests masking unfinished work, so each FR-017 test
must run and assert something on every platform the suite runs on. The first three rows fail for
*every* user because the obstacle is the file type or the path, not the permission bits. Verified by
execution: `open("DIR/sub.log", "w")` against a directory of that name raises `IsADirectoryError`
with `strerror` "Is a directory" and `filename` set, even as root; `open` in a `0o500` directory
*succeeded* as root, confirming the probe is necessary there.

**Alternatives considered**: `pytest.mark.skipif(os.geteuid() == 0)` (rejected — constitution gate 2);
mocking the filesystem (rejected — the end-to-end tests drive a real subprocess, and a mock would
stop testing the thing FR-017 is about).
