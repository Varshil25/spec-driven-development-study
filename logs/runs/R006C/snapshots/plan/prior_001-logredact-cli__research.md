# Phase 0 Research: Log Redaction CLI

**Branch**: `001-logredact-cli` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

Every decision below was taken against the constitution (standard library only, fail loudly,
testable, simplest sufficient design, secure by default) and the spec's own requirements. Where a
decision rests on a measurement, the measurement command and result are recorded so a reviewer can
reproduce it. Measurements were taken on Python 3.13.17 (the interpreter available here; the
delivered floor is 3.11).

## Summary of unknowns resolved

| # | Unknown from Technical Context | Status |
|---|---|---|
| R1 | Runtime, packaging, and interpreter floor | Resolved — given by A-10 |
| R2 | How to enforce the 1 MiB line cap without reading an unbounded line | Resolved — measured |
| R3 | How to pass non-UTF-8 bytes and line terminators through byte-for-byte | Resolved — measured |
| R4 | How to implement FR-014 precedence without re-scanning placeholders | Resolved |
| R5 | Whether the email pattern can run in linear time (SR-005) | Resolved — measured, design changed |
| R6 | Whether FR-004 requires a dot in the domain | Resolved — spec ambiguity, decision recorded |
| R7 | Behaviour of a dotted quad inside a longer token (`v10.0.0.7-beta`) | Resolved — derived from FR-013 |
| R8 | How to find card sub-candidates inside a longer digit run in bounded time/memory | Resolved — measured, design changed |
| R9 | How to make argument parsing a strict allowlist (SR-001) | Resolved — measured |
| R10 | Whether to continue past an unreadable operand; whether to print `--count` on failure | Resolved — spec gap; continue-and-report directed by the requester, tally suppressed per FR-018's reasoning |
| R11 | Exit behaviour when the downstream pipe closes (A-7) | Resolved |
| R12 | How to detect a failed write (SR-009) | Resolved |
| R13 | Test strategy, including how to test an unreadable file as root | Resolved — measured |
| R14 | Performance goals (none stated in the spec) | Resolved — measured, goals proposed |

---

## R1 — Runtime, packaging, interpreter floor

**Decision**: Python 3.11+, standard library only, package `logredact` under `src/`, run as
`python -m logredact` with `src/` on `PYTHONPATH`. `pytest` is the only development dependency.

**Rationale**: Fixed by Assumption A-10 and by the user input for this planning step; it is also
exactly what Principle I requires. No capability in this feature needs a third-party package:
`re`, `io`, `sys`, `os`, and `argparse` cover all of it.

**Alternatives considered**: An installable distribution with `pyproject.toml` packaging metadata
and a console script — rejected, because A-10 fixes the invocation as `python -m logredact` with
`src/` on `PYTHONPATH`, and a console script would add an install step the constitution's
"runnable with no dependency resolution step" wording discourages. A `pyproject.toml` is still
added, but only to carry `pytest` configuration (see R13), not packaging.

---

## R2 — Enforcing the 1 MiB line cap in bounded memory

**Decision**: Read each line with `stream.readline(CAP + 1)` where `CAP = 1 << 20`, on a
`TextIOWrapper`. A returned chunk of exactly `CAP + 1` characters means the line (including its
terminator) exceeds the cap, and the run fails per FR-018. Any shorter chunk is a complete line.

**Rationale**: This is the only formulation that satisfies SR-005's "MUST NOT read more than the
cap plus a small fixed margin of a single line into memory before rejecting it" while staying a
one-liner. The correctness argument is that `readline(limit)` stops at the first of: a line
terminator, `limit` characters, or EOF. So:

- `len(chunk) < CAP + 1` → the chunk ended at a terminator or EOF, hence it is a whole line whose
  total length including terminator is `<= CAP`. Accepted (the cap is inclusive, as the spec's
  "exactly 1 MiB including its terminator" edge case requires).
- `len(chunk) == CAP + 1` → the line is at least `CAP + 1` characters including whatever
  terminator follows, so it exceeds the cap whether or not more characters remain. Rejected.
- `chunk == ""` → EOF.

**Measurement** (`/tmp/exp1/readline_probe.py`, an 8 MiB single line fed through a raw stream that
counts bytes pulled):

```
len(chunk) = 1048577 (= CAP+1)
bytes pulled from raw = 1056768  => margin over cap: 8192
tracemalloc peak = 2.01 MiB
```

The margin is one `TextIOWrapper` read chunk (8 KiB), which is the "small fixed margin" SR-005
allows. Peak traced memory is ~2 MiB because the cap is counted in characters and the decoder
holds both the byte buffer and the decoded string; it does not grow with the length of the
offending line.

**Alternatives considered**:
- Plain `readline()` then check the length — rejected: it reads the whole line into memory first,
  so a 1 GB line exhausts memory. This is the exact failure SC-010 names.
- Reading fixed-size blocks and splitting on terminators by hand — rejected: more code, and it
  re-implements what `readline(limit)` already does correctly.
- Counting the cap in bytes on the binary layer — rejected: SR-005 states the cap in characters
  (1,048,576 characters), and a character cap cannot be enforced on the byte layer without either
  rejecting valid lines or allowing up to 4x the memory.

---

## R3 — Encoding and byte-for-byte pass-through

**Decision**: Open every input (and standard output) as text with
`encoding="utf-8", errors="surrogateescape", newline=""`.

**Rationale**: `surrogateescape` maps each undecodable byte to a lone surrogate and re-encodes it
to the identical byte on output, which is exactly Assumption A-4. `newline=""` disables newline
translation, so `\n`, `\r\n`, and a missing final terminator all survive unchanged (FR-009 and the
"CRLF" and "last line without a trailing newline" edge cases). Working in text rather than bytes
lets the redaction patterns be plain `str` patterns; surrogate characters are outside every
character class used, so they can never be part of a match and pass straight through.

**Measurement** (`/tmp/exp1/misc_probe.py`): input `b"caf\xe9 jane@example.com\r\n\xff\xfe no
newline at eof"` read line-by-line through such a wrapper and written back out —
`byte-identical round trip: True`, with the `\r\n` preserved and the unterminated final line
preserved.

**Note on `newline=""`**: it also makes a lone `\r` a line terminator. This cannot create a
redaction gap, because `\r` is not a valid character inside any of the three match kinds (it is
not an email, domain, octet, digit, space, or hyphen character), so no match can straddle it.

**Alternatives considered**:
- Binary mode with `bytes` patterns — rejected: equivalent power, but then the SR-005 cap and the
  spec's character-counted cap disagree (see R2), and `bytes` patterns make the code less legible
  for no gain.
- `errors="replace"` or `errors="strict"` — rejected: `replace` mutates bytes that the spec says
  must pass through unchanged; `strict` turns a log with a few corrupt bytes into a failed run,
  which A-4 explicitly rejects.

---

## R4 — Precedence and single-pass replacement

**Decision**: One compiled pattern with three named alternatives in precedence order —
`(?P<email>…)|(?P<ip>…)|(?P<card>…)` — applied with `pattern.sub(replacer, line)`.

**Rationale**: This delivers FR-014 with no bookkeeping of our own. `re.sub` scans left to right,
tries the alternatives in written order at each position, and builds the result from
non-overlapping matches without ever re-examining what it has written. So:

- *Overlap resolved once, under one kind*: a position can only be claimed by one alternative.
- *Precedence email → IPv4 → card*: alternation order at a shared start position.
- *Placeholders never re-scanned*: a property of `re.sub`, not something we must enforce.
- *Counting once per replacement* (A-1): the replacer function is called exactly once per match.

An overlap between an email and an IPv4 address always shares a start position or starts earlier
for the email, because every character that can begin an IPv4 address (a digit) and every
character that can continue one (digit or dot) is also an email local-part character. So the
leftmost-match rule and the precedence rule never disagree, and `re.sub`'s plain behaviour is
FR-014-compliant.

**Alternatives considered**:
- Three sequential `re.sub` passes, one per kind — rejected: the second pass would scan the
  placeholders written by the first (`[EMAIL]`) and the third would scan both, which FR-014
  forbids outright; guarding against that needs a placeholder-escaping scheme, i.e. more
  machinery for a worse result.
- A hand-written scanner over the line — rejected under Principle IV: `re` already provides
  leftmost, non-overlapping, ordered-alternative scanning, which is the whole algorithm.

---

## R5 — The email pattern must be guarded to run in linear time

**Decision**: Prefix the email alternative with a negative lookbehind for a local-part character:

```
(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}
```

**Rationale**: This was the single largest design risk in the feature, and the first design failed
SR-005. The unguarded pattern is quadratic in line length: at every start position inside a run of
local-part characters, the engine re-consumes the whole run before failing. SR-005 requires time
linear in the length of the line with no input able to trigger catastrophic backtracking, and the
spec permits lines up to 1 MiB, so the unguarded pattern is a usable denial of service.

The lookbehind makes the attempt fail in one character comparison at every position except the
first character of each local-part run, which restores linearity.

The guard does not change which text is matched. The local part must end at the `@`, so for any
start position within one run the engine reaches the same `@` and evaluates the same domain text;
the domain either matches for all starts in that run or for none. Rejecting every start but the
run's first therefore removes only duplicate work, never a match. (It is also independently
desirable: it stops an email being matched from the middle of a longer token, the same property
FR-013 mandates for the other two kinds.)

**Measurement** (`/tmp/exp1/regex_probe.py`, `findall` over adversarial inputs, doubling size):

| input | 20,000 chars | 40,000 chars | 80,000 chars |
|---|---|---|---|
| unguarded, `"a"*n` (no `@`) | 441 ms | 1,757 ms | 7,142 ms |
| unguarded, `"a"*n/2 + "@" + "1."*n/4` | 1,900 ms | 7,982 ms | 32,638 ms |
| **guarded**, `"a"*n` | **0.3 ms** | **0.7 ms** | **1.2 ms** |
| **guarded**, `"a"*n/2 + "@" + "1."*n/4` | **0.7 ms** | **1.5 ms** | **2.4 ms** |

The unguarded rows quadruple as the size doubles (quadratic); extrapolated to one 1 MiB line that
is roughly 1.5 hours for a single line. The guarded rows double as the size doubles (linear).

**Alternatives considered**:
- Bounding the quantifiers with RFC 5321 limits (`{1,64}` local part, `{1,63}` labels) — this also
  restores linearity, but it was **rejected because it creates a redaction gap**: an email with a
  65-character local part would stop being redacted. Under-redaction is the failure mode this tool
  exists to prevent (A-12's reasoning), so a fix that trades completeness for speed is the wrong
  trade.
- Possessive quantifiers / atomic groups (`++`, `(?>…)`, available from 3.11) — rejected: they
  stop the engine backtracking *within* one attempt, but the cost here is the *re-attempt at every
  start position*, which they do not address. Measured behaviour confirmed no improvement.
- Matching `@` first and expanding outwards by hand — rejected under Principle IV: it is linear,
  but it replaces a one-line guard with a hand-written scanner.

---

## R6 — Does FR-004 require a dot in the domain?

**Decision**: Yes. The domain must have at least two labels, so `jane@example.com` is redacted and
`user@localhost` is **not**. This is what the pattern in R5 implements (`[A-Za-z0-9-]+` then zero
or more dotted labels then a mandatory `\.[A-Za-z]{2,}`).

**Rationale**: FR-004 says "a dot-separated domain of letter/digit/hyphen labels whose last label
is at least two letters". "Dot-separated" implies a separator is present, and the illustrative
example is `mail.example.com`. The reading also agrees with the rest of the spec: a bare
`user@host` is a host reference rather than an email address, and A-8 puts other identifiers out
of scope, while SC-003 requires lines with no personal data to come back byte-for-byte — redacting
`nginx@localhost started` would break SC-003 for an ordinary log line.

**This is a spec ambiguity, not a settled fact.** FR-004 can also be read as allowing a
single-label domain. If the requester wants `user@localhost` redacted, the change is to make the
final `\.` optional in one pattern plus one test; it is a ten-minute change, not a redesign.
Flagged here so the choice is visible before implementation.

**Alternatives considered**: Allowing single-label domains — rejected for the reasons above, and
because it is the over-redacting direction, which costs SC-003 and SC-004 compliance on ordinary
log text (`systemd@system`, `root@localhost`).

---

## R7 — A dotted quad inside a longer token

**Decision**: `v10.0.0.7-beta` becomes `v[IP]-beta`. It is redacted.

**Rationale**: The spec lists this case under Edge Cases and deliberately defers it — "behaviour is
fixed by FR-013 (an IPv4 candidate must not be flanked by a digit or a dot)". Applying FR-013
literally: `10.0.0.7` here is preceded by `v` (not a digit, not a dot) and followed by `-` (not a
digit, not a dot), so FR-013 does not block it and FR-005 requires the replacement. Recorded
explicitly because the surrounding prose might lead a reader to expect the opposite, and because
it needs a test that asserts the redaction rather than the pass-through.

By the same rule, `01.2.3.4` is left entirely alone: `01` is not a valid octet (FR-005 forbids
leading zeros), and the `1.2.3.4` fragment inside it is blocked by FR-013 because it is preceded
by the digit `0`. Both behaviours were verified in the prototype.

**Octet pattern**: `(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])`, with
`(?<![0-9.])` before the quad and `(?![0-9.])` after it. The branches are mutually exclusive at
each start position, so there is nothing to backtrack into; it is linear by construction.

---

## R8 — Finding card numbers inside a longer digit run

**Decision**: The card alternative matches a *maximal* run of digit groups joined by single spaces
or hyphens, `(?<!\d)\d+(?:[ -]\d+)*`. The replacer then walks that run itself and redacts every
Luhn-valid 13–19 digit candidate inside it, using leftmost-longest selection, group boundaries as
candidate boundaries, an incrementally updated Luhn sum, and O(1) extra memory.

**Rationale** — three requirements force this, and each one rules out something simpler:

1. *A card must still be found when it follows other bare numbers.* `log 1 2 3 4111 1111 1111 1111
   end` is a single run of space-joined groups totalling 19 digits. Checking only the whole run
   (the obvious implementation) computes Luhn over `1234111111111111111`, fails, and leaves the
   card in the output — a silent redaction gap, and a direct SC-005 failure ("100% are redacted").
   So sub-candidates within a run must be considered.
2. *Candidate boundaries are group boundaries, not digit positions* (FR-013). A candidate's first
   digit must not be preceded by a digit and its last must not be followed by one, so a candidate
   can only start at the first digit of a group and end at the last digit of a group. This is also
   what makes the spec's `1234114111111111111111` case (a 22-digit run containing a Luhn-valid
   16-digit substring) correctly *not* a card.
3. *Bounded time and memory* (SR-005, SC-010). A candidate holds at most 19 digits, so from any
   start group only the next ~19 digits' worth of groups can matter. Extending a candidate
   forward one digit at a time keeps the Luhn sum up to date in constant time per digit, using the
   identity that appending a digit flips the doubling parity of every earlier digit: carrying both
   parities (`A` for the real checksum, `B` for the flipped one) gives
   `A' = B + digit`, `B' = A + doubled(digit)`. So each start costs ~19 constant-time steps and
   the whole run is linear with O(1) extra state.

"Same separator throughout" (FR-006) is enforced while extending: the first separator crossed
fixes the candidate's separator and a different one ends the candidate. This yields the spec's
required behaviour for `4111 1111-1111 1111` (mixed — no candidate is long enough, so it is left
alone) and for `4111  1111  1111  1111` and `4111--1111--1111--1111` (doubled separators do not
match `[ -]`, so the run breaks into four 4-digit groups, none long enough).

**Measurement** (`/tmp/exp1/card_probe2.py`, worst of ten adversarial and realistic line shapes,
doubling size):

| line size | worst case | shape |
|---|---|---|
| 262,144 | 845 ms | `"1 " * n/2` |
| 524,288 | 1,809 ms | `"1 " * n/2` |
| 1,048,576 | 3,435 ms | `"1 " * n/2` |

Linear (doubles as the size doubles). The first design, which tokenised the run with
`re.findall` and recomputed Luhn from a joined string per candidate, measured **15,850 ms** for
the same 1 MiB line and also materialised ~500,000 token strings — tens of megabytes for one line,
which would have broken SC-010's memory bound. The redesign is 4.6x faster and allocates nothing
per candidate.

Realistic throughput on a typical log line
(`2026-11-05T10:00:00 INFO user jane.doe@example.com from 10.0.0.7 paid 4111 1111 1111 1111 ok`):
**4.7 MB/s, ~50,000 lines/s**.

**Correctness check**: a 28-case prototype covering every worked example, every card grouping in
the spec's edge cases, both FR-013 flanking directions, octet boundaries, email shapes, the
email-over-IPv4 overlap, CRLF, and the empty line passes 28/28. Two defects were found and fixed
during prototyping, both worth a regression test: separators between two adjacent cards were being
swallowed (`[CARD][CARD]` instead of `[CARD] [CARD]`, an FR-008 violation), and the first
tokenising design had the performance and memory problem above.

**Alternatives considered**:
- Check only the maximal run — rejected: redaction gap, see (1).
- Allow candidates to start or end mid-group — rejected: contradicts FR-013 and would redact the
  16-digit substring of a 22-digit run that the spec explicitly says is not a card.
- Prefix-sum arrays over the run's digits for O(1) candidate checks — faster still, but rejected:
  it allocates four arrays proportional to the run length, which fights SC-010's "fixed bound"
  for a line that is already allowed to be 1 MiB, and the sliding approach is already linear.
- Leftmost-shortest selection — rejected: prefer the longest match, so that a longer valid card
  is replaced whole rather than leaving some of its digits in the output (SR-006).

---

## R9 — Argument parsing as a strict allowlist

**Decision**: `argparse.ArgumentParser(prog="python -m logredact", add_help=False,
allow_abbrev=False, usage="%(prog)s [--count] [FILE ...]")` with one `--count` flag and
`nargs="*"` file operands.

**Rationale**: SR-001 allows exactly `--count`, `--`, and file operands, and requires anything else
to be rejected with a diagnostic on stderr, a non-zero status, and nothing on stdout. Two argparse
defaults would violate that allowlist and both must be turned off:

- `allow_abbrev=True` (the default) accepts `--cou` as `--count`, which is an option outside the
  allowlist.
- `add_help=True` (the default) adds `-h/--help`, which writes to **stdout** and exits **0** — a
  direct contradiction of SR-001's "nothing written to standard output" and "non-zero exit status"
  for an option that is not `--count`. A-9 ("no option other than `--count`") agrees.

With both disabled, argparse's own error path gives exactly the required behaviour: usage and
message to stderr, exit status 2 (which is also what A-5 asks for), nothing on stdout.

**Measurement** (`/tmp/exp1/misc_probe.py`):

```
['--count', 'a.log']  -> OK count=True files=['a.log']
['--cou']             -> SystemExit(2)
['--verbose']         -> SystemExit(2)
['-h']                -> SystemExit(2)
['--help']            -> SystemExit(2)
['--count=1']         -> SystemExit(2)
['--', '-weird.log']  -> OK count=False files=['-weird.log']
['a.log', 'b.log']    -> OK count=False files=['a.log', 'b.log']
[]                    -> OK count=False files=[]
```

**Consequence to flag**: `python -m logredact --help` fails with a usage message instead of
printing help. That is the spec-faithful behaviour, but it is unconventional for a CLI, and the
usage line argparse prints on the error path is the only help available. If the requester prefers
a conventional `--help`, it is an amendment to SR-001/A-9 plus one line of code — recorded here
rather than silently chosen.

**Alternatives considered**: Hand-written parsing — rejected under Principle IV; argparse with
those two flags set is both shorter and already handles `--`. Keeping `add_help=True` — rejected:
it breaks SR-001 as shown.

---

## R10 — Behaviour on an unreadable operand, and `--count` on a failed run

**Decision**:
1. **Continue past an unreadable operand.** Report *each* operand that cannot be opened or read on
   standard error as it is encountered, process every remaining operand, and exit 2 at the end of
   the run. *(Directed by the requester, 2026-11-09; see the revision note below.)*
2. Write **no** `--count` summary on any run that exits non-zero. *(Unchanged.)*

**Rationale**: The spec requires a diagnostic naming the file and status 2 (FR-012) and says output
already written stays written, but it does not say whether processing continues, and it only
forbids the summary for the over-length case (FR-018).

For (1), this is `cat`-style behaviour and it is what the requester asked for. It is also the more
useful of the two readings in the operator's situation: given `app.log applog app2.log`, an
operator who mistyped one name learns about that one name *and* still gets the other two files
redacted in one pass, instead of discovering the typos one run at a time. FR-012's "write a message
to standard error that includes that file name" is satisfied per failing operand, which is what
makes "which ones failed" answerable from the diagnostics alone. The contract that protects the
caller is unchanged and is carried entirely by the exit status: **non-zero means this output is
incomplete**.

For (2), suppressing the summary on failure generalises FR-018's stated reason — "so a partial
tally cannot be mistaken for a complete one" — which applies identically here: a tally printed
after a run that skipped an unreadable operand covers only the operands that were read, not the
operands the caller asked for. The requester's instruction did not touch this, so it stands;
flagged again below because the two decisions are easy to conflate.

### Important: this does *not* change FR-018

An **over-length line still ends the run immediately** and later operands are *not* processed.
FR-018 states it directly — "the tool MUST stop processing" — so this is a specification
requirement, not a choice available to the plan. The two failure modes therefore differ on purpose:

| Failure | Remaining operands | Status | Source |
|---|---|---|---|
| Operand cannot be opened or read | processed; each failure reported | 2 at end of run | FR-012 + this decision |
| Line exceeds the 1 MiB cap | **not** processed; run stops at once | 2 | FR-018 (mandatory) |

The asymmetry is defensible on the spec's own terms: an unreadable operand is a self-contained,
fully-diagnosed gap (the caller knows exactly which file is missing from the output), whereas an
over-length line means the tool has met input it cannot safely process at all, and A-12's reasoning
is that it must refuse rather than continue producing output that looks clean.

**Revision note**: this section originally decided the opposite for (1) — stop at the first
unreadable operand — on the grounds that continuing maximises the output produced after a known
failure. The requester directed the `cat`-style behaviour instead. Recorded rather than
overwritten, because the rejected reasoning is the thing a reviewer would otherwise re-raise: the
answer is that the exit status, not the volume of output, is what tells the caller the output is
incomplete, and the per-file diagnostics make the gap identifiable.

**Alternatives considered**: Stopping at the first failure — rejected per the above. Printing the
partial tally — rejected for the reason FR-018 gives. Validating every operand before writing
anything — rejected: it contradicts the spec's own edge case, which contemplates output already
written when a later operand fails. Exiting with a count of failures, or a distinct status per
failure kind — rejected: A-5 keeps a single failure status, 2.

---

## R11 — Closed downstream pipe

**Decision**: Catch `BrokenPipeError`, redirect the stdout file descriptor to `os.devnull` so the
interpreter cannot emit a second failure at shutdown, write nothing further, and exit
`128 + signal.SIGPIPE` (141).

**Rationale**: A-7 requires terminating "by the usual convention for that signal, without a
traceback", and explicitly says this is not a successful complete run. 141 is that convention.
The devnull redirection is the standard Python idiom: without it, CPython tries to flush stdout
during shutdown, fails again, and prints `Exception ignored in: <_io.TextIOWrapper …>` to stderr —
which would violate FR-011 ("without `--count`, a successful run writes nothing to stderr") in
spirit and SR-003's no-traceback rule.

This does not conflict with FR-015 ("any run that is not an error MUST exit 0"), because a run cut
short by a closed pipe is not a successful run.

**Alternatives considered**: Exiting 2 — rejected: the spec reserves 2 for diagnosable failures
and A-7 asks for the signal convention. Restoring `SIGPIPE` to `SIG_DFL` at start-up so the
process dies by the signal — equivalent outcome, but it changes interpreter-wide signal state and
makes the behaviour harder to test; rejected under Principle IV.

---

## R12 — Detecting write failures (SR-009)

**Decision**: Flush standard output explicitly before writing any `--count` summary and before
returning success; treat an `OSError` from a write or flush as a failed run (diagnostic to stderr,
status 2), with `BrokenPipeError` handled per R11.

**Rationale**: SR-009 forbids reporting success for a run whose output was not fully written.
Buffered writes mean an ENOSPC or EIO can surface only at flush time, after the last `write()`
returned successfully — so without an explicit flush before the success path, the tool could exit
0 having lost data. The explicit flush before the summary is required anyway by A-3 (the caller
must see the complete log before the tally).

---

## R13 — Test strategy

**Decision**:
- Unit tests call `redact_line()` directly for the recognition, precedence, counting, and
  linearity requirements — fast, and they can assert exact strings and tallies.
- Contract tests run the real CLI in a subprocess (`sys.executable -m logredact`, with
  `PYTHONPATH=src`) and compare raw `bytes` on stdout and stderr plus the exit status. This is the
  only way to verify FR-001, the stream separation of FR-010/FR-011, the exit statuses, and the
  byte-for-byte guarantees against the actual delivered interface.
- `pytest` configuration lives in `pyproject.toml` as `[tool.pytest.ini_options]` with
  `pythonpath = ["src"]`, so `pytest` works from the repo root with no `PYTHONPATH` juggling and
  no `sys.path` edits in `conftest.py`.
- Slow tests (the 1 MiB adversarial lines and the large-input memory run) are marked and kept
  runnable, not skipped by default.

**Measured constraint that affects one test**: this environment runs as **root**, and for root a
`chmod 000` file is still readable — verified: `open("/etc/shadow")` succeeded in the probe. So
the Story 4 scenario 2 test (permissions deny reading) must be
`@pytest.mark.skipif(os.geteuid() == 0, …)`, and the directory-operand and missing-path tests
(which fail for root too, as `IsADirectoryError` and `FileNotFoundError`) carry the FR-012
coverage unconditionally. Without this, the permission test would silently pass-by-not-failing or
fail outright depending on who runs it.

**Timing assertions**: the linearity tests assert a generous wall-clock ceiling (a 1 MiB
adversarial line in under 10 s, against a measured worst case of ~3.4 s) rather than a tight
bound, so they catch a reintroduced quadratic blow-up — which costs hours, not seconds — without
being flaky on a loaded machine.

**Alternatives considered**: Only subprocess tests — rejected: too slow for the ~60 recognition
cases and they cannot isolate the tally from the formatting. Only in-process tests with injected
streams — rejected: they would not test `python -m logredact`, which is FR-001.

---

## R14 — Performance goals

**Decision**: Adopt these as the feature's performance goals, since the spec states none:
sustained throughput of at least 1 MB/s on realistic log text (measured 4.7 MB/s), and a worst-case
adversarial 1 MiB line in under 10 s (measured 3.4 s), with peak memory bounded by a small
multiple of the 1 MiB line cap and independent of total input size (measured ~2 MiB while
rejecting an 8 MiB line).

**Rationale**: SR-005 and SC-010 constrain memory and the *growth rate* of time, but nothing in the
spec bounds the constant. Recording measured numbers turns "linear" into something the
implementation gate can actually check, as Principle III requires, and gives the quadratic
regression in R5 a tripwire.
