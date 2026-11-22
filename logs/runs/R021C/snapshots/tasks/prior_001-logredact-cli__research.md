# Phase 0 Research: Log Redaction Tool (`logredact`)

**Feature**: `001-logredact-cli` | **Date**: 2026-11-20 | **Plan**: [plan.md](./plan.md)

The Technical Context in [plan.md](./plan.md) contains no `NEEDS CLARIFICATION` markers: the
language floor, the dependency policy, and the test runner were all fixed by the specification,
the constitution, and the user's planning input. The research below therefore covers the
mechanism decisions those constraints leave open, plus one genuine conflict inside the
specification that had to be resolved before design could proceed.

---

## R-000: Conflict between FR-009 and FR-021 on `admin@1.2.3.4`

**This is the one place where the delivered design knowingly departs from a literal reading of a
requirement, because the requirements cannot all be satisfied at once.**

**The conflict**: FR-009 defines a recognized email domain as "two or more dot-separated labels
of letters, digits, and hyphens, **whose final label is two or more letters**". In
`admin@1.2.3.4` the final label is `4` — one character, not a letter — so under FR-009 the text
contains no email address. But FR-021 states that "`admin@1.2.3.4` MUST produce exactly one
`[EMAIL]`", and the Edge Cases section repeats it: "an address like `admin@1.2.3.4` yields one
`[EMAIL]`, not an `[EMAIL]` plus an `[IP]`". Under FR-009 alone, the only match in that string is
the IPv4 address, so the output would be `admin@[IP]` — one redaction, but an `[IP]`, not an
`[EMAIL]`, and with the local part `admin` left exposed.

**Decision**: Recognize an email domain as *either* (a) the FR-009 form — one or more
`label.` groups followed by a final label of two or more letters — *or* (b) a valid IPv4
dotted-quad subject to the same boundary rule as FR-014 (not followed by a digit or a dot).
`admin@1.2.3.4` therefore matches as an email and produces one `[EMAIL]`.

**Rationale**: Three reasons. First, the `admin@1.2.3.4` outcome is stated twice, in a
requirement and in an edge case, with the reasoning attached ("not an `[EMAIL]` plus an `[IP]`"),
whereas the final-label clause in FR-009 reads as a rule for ordinary hostnames that simply did
not consider an address-literal domain. Second, the privacy outcome is strictly better: redacting
only the IP leaves `admin@` in a log the whole tool exists to sanitize, and a local part is
personal data. Third, it is the narrower change — it widens one alternative in one pattern and
leaves every other FR-009 behaviour (`jane.doe+test@mail.example.com` recognized in full, a
single `[EMAIL]`) untouched.

**Alternatives considered**:

- *Follow FR-009 literally; emit `admin@[IP]`.* Rejected: it contradicts an explicit worked
  example given twice, and it leaks the local part. A test citing FR-021 would fail.
- *Make any final label acceptable (drop "two or more letters").* Rejected: far broader than the
  conflict requires. It would make `build@1.2` and `user@a.b` matches, changing behaviour on
  inputs the spec never put in question.
- *Special-case the precedence loop: suppress an `[IP]` whose match is immediately preceded by
  `@` and a local part.* Rejected: it produces the right output by a second, parallel mechanism
  rather than by the recognition grammar, so the grammar in `contracts/redaction-patterns.md`
  would no longer describe what the tool does.

**Consequence to surface to the reviewer**: `user@10.0.0.7` and similar address-literal
addresses now redact to `[EMAIL]` and count toward `emails`, not `ips`. `admin@999.1.1.1`
remains unchanged (the domain is neither a valid IPv4 nor an FR-009 hostname, and `999.1.1.1` is
not an IPv4 address), consistent with the out-of-range-octet edge case. If the reviewer prefers
the literal FR-009 reading instead, the fix is to delete alternative (b) from the email pattern
and amend FR-021 and the Edge Cases entry; nothing else in the design depends on the choice.

---

## R-001: Preserving bytes that are not valid UTF-8 (FR-005a, SC-003)

**Decision**: Decode and encode both streams as UTF-8 with `errors="surrogateescape"`. Input
files are opened with `open(path, encoding="utf-8", errors="surrogateescape", newline="\n")`;
`sys.stdin` and `sys.stdout` are replaced by `io.TextIOWrapper` instances built over
`sys.stdin.buffer` / `sys.stdout.buffer` with the same three settings.

**Rationale**: `surrogateescape` maps each undecodable byte to a lone surrogate code point in the
range U+DC80–U+DCFF, and re-encoding with the same handler restores that exact byte. The
round-trip is byte-exact and needs no special-casing in the redaction layer. Just as important,
lone surrogates cannot match any of the three recognition patterns — every character class in use
is ASCII (`[A-Za-z0-9._%+-]`, `[0-9]`, `[ -]`) — so FR-005a's "such bytes MUST NOT match any
redaction category" holds by construction, and a digit run interrupted by an undecodable byte is
correctly not a contiguous card candidate. The handler is also the reason no decode error can
occur, which keeps FR-028's "cannot be read" meaning exactly what the spec's Assumptions say it
means: open or read failed, not decode failed.

**Alternatives considered**:

- *Process as `bytes` with byte-pattern regexes.* Rejected: it works, but every pattern, the
  Luhn digit extraction, and every test fixture would carry `b"..."` noise, and the spec talks
  about text. No requirement needs byte-level matching.
- *`errors="replace"`.* Rejected outright — it substitutes U+FFFD, which FR-005a forbids by name.
- *`errors="strict"` and treating a decode error as unreadable.* Rejected: the clarification
  session explicitly chose pass-through-and-exit-0 over failure.

---

## R-002: Line splitting that treats only `\n` as a terminator (FR-007, FR-007a)

**Decision**: Open every text stream with `newline="\n"` and iterate it directly
(`for line in stream:`). The yielded string includes its trailing `\n` when one is present.

**Rationale**: Python's `newline` parameter has three distinct behaviours and only one of them is
correct here. `newline=None` (the default) is universal-newlines mode *with* translation: it
would rewrite `\r\n` to `\n`, violating FR-007. `newline=""` disables translation but still
*splits* on `\r`, `\n`, and `\r\n`, so a bare carriage return would become a line boundary —
FR-007 forbids exactly that, and the splitting would also prevent a match from spanning a `\r`
the way it spans any other ordinary character. `newline="\n"` does what the requirement says:
lines are terminated only by `\n` and the terminator is returned to the caller untranslated, so
`\r\n` survives intact, a mixed-ending file keeps each line's own ending, and a bare `\r` is just
a character in the middle of a line. FR-007a follows for free: because the terminator is part of
the yielded string and is written back verbatim, a final line without a newline round-trips
without one, and the tool never appends one.

**Alternatives considered**:

- *Read in binary and split on `b"\n"` manually.* Rejected: reimplements buffered line iteration
  for no behavioural gain, and `newline="\n"` is already exact.
- *`newline=""` plus re-joining `\r`-split fragments.* Rejected: strictly more code to undo
  splitting that did not need to happen.

---

## R-003: Single-pass matching for overlap and precedence (FR-020, FR-021)

**Decision**: One compiled pattern, `(?P<email>…)|(?P<ip>…)|(?P<card>…)`, searched repeatedly
across the line with `pattern.search(line, search_from)`. The category of a match is read from
`match.lastgroup`; all internal groups are non-capturing so that stays unambiguous.

**Rationale**: Python's `re.search` returns the match at the *leftmost* position where any
alternative can match, and at that position it tries alternatives in written order. That is
precisely FR-021: earliest-starting match wins, and ties at the same start resolve email → IPv4
→ card. FR-020 ("each character belongs to at most one redaction") follows from advancing the
copy cursor to `match.end()` and never re-examining emitted text, which is also FR-022: a
substituted `[EMAIL]` is appended to the output list, not to the subject string, so it cannot be
rescanned, and a literal `[EMAIL]` already in the input matches nothing and is passed through
uncounted.

Worked check of the precedence tie, `1234567890123@example.com`: both the email and the card
alternative can begin at offset 0 (a 13-digit local part is also a 13-digit card candidate). The
email alternative is written first, so it wins, and the whole address becomes one `[EMAIL]` —
FR-021's required ordering.

**Alternatives considered**:

- *Three sequential passes, one per category.* Rejected: it cannot express FR-020/FR-021 without
  a separate span-reservation table, and the second pass would see the first pass's placeholders,
  which FR-022 forbids.
- *`re.sub` with a callback.* Rejected: a callback cannot decline a match. A Luhn-failing card
  candidate must be left as-is *and* the scan must resume one character later (FR-019a), which
  `sub`'s "resume after the match" advance makes impossible.

---

## R-004: Card candidate selection — longest valid, and resuming after rejection (FR-016–FR-019a)

**Decision**: The alternation's card branch is
`(?<![0-9])[0-9](?:[ \-]?[0-9]){12,18}(?![0-9])`. When it matches at position *p*, seven
fixed-length patterns `[0-9](?:[ \-]?[0-9]){L-1}(?![0-9])` for L = 19 … 13 are tried with
`.match(line, p)`, and the first (hence longest) whose digits pass Luhn is redacted. If none
passes, nothing is emitted and the search cursor moves to *p* + 1 while the copy cursor stays
put; the loop then re-searches from there.

**Rationale**: The structural requirements fall out of the pattern shape. `[0-9]` at both ends
gives "begins and ends with a digit"; `[ \-]?` permits at most one separator between adjacent
digits, so doubled separators break the run and mixed single separators are fine; `{12,18}`
repetitions of "optional separator plus digit" gives 13–19 digits.

FR-018 — and with it the "a run of 20+ digits is never a card" rule from the clarification
session — is produced entirely by the two lookarounds, with no length counting. Inside a
20-digit run the engine starts at the first digit (`(?<![0-9])` satisfied), tries 19 digits and
fails `(?![0-9])` because a digit follows, backtracks through 18, 17, … 13 and fails the same
lookahead every time; it then advances the start, where `(?<![0-9])` now fails for every
remaining position in the run. So no candidate exists anywhere in the run, and the checksum is
never consulted to rescue part of it — exactly what the spec demands.

FR-019a is why the two cursors are separate. Verified against the spec's own example,
`99 4111 1111 1111 1111`: the leftmost card candidate starts at offset 0 and is the whole string,
18 digits (`994111111111111111`), whose Luhn sum is 48 — it fails. The shorter lengths at offset 0
either run past the available digits (19) or end with a digit following (17, 16, 15, 13), except
14, which is `99 4111 1111 1111` — Luhn sum 42, also failing. With every candidate at offset 0
rejected, the cursor advances; offsets 1 and 2 are blocked by `(?<![0-9])` and by not being a
digit; offset 3 is the `4`, preceded by a space, where the 16-digit `4111 1111 1111 1111` passes.
The emitted text is the untouched `99 ` followed by `[CARD]`, giving `99 [CARD]`.

The seven patterns rather than a hand-written character walk is a deliberate duplication, logged
in the plan's Complexity Tracking: they are built from the same separator fragment as the main
branch, so the two can never disagree about what a candidate is.

**Alternatives considered**:

- *Strip separators from the line and scan digit runs.* Rejected: it loses the mapping from digit
  positions back to character offsets, which the replacement needs, and it would have to
  reconstruct the "never begins or ends on a separator" rule afterwards.
- *Check Luhn on the longest candidate only.* Rejected: FR-019 asks for the longest *valid* one,
  not the validity of the longest one.
- *On rejection, resume at `match.end()`.* Rejected: this is the bug FR-019a was written to
  forbid; it would output `99 4111 1111 1111 1111` unredacted.

**Luhn implementation**: double every second digit from the right, subtract 9 from any product
above 9, sum, and require a multiple of 10. One loop over the digit string, no table.

---

## R-005: IPv4 octet matching with leading zeros and boundary rules (FR-012–FR-014)

**Decision**: Octet fragment `(?:25[0-5]|2[0-4][0-9]|[01][0-9][0-9]|[0-9][0-9]|[0-9])`, four of
them dot-separated, wrapped in `(?<![0-9.])` … `(?![0-9.])`.

**Rationale**: The alternation accepts 0–255 and, via the `[01][0-9][0-9]` branch, accepts the
leading-zero forms (`010`, `00.0.0.0`) that the spec's Assumptions require, while rejecting 256
and above. The boundary lookarounds give FR-014 directly, and they are what make the
look-alike edge cases come out right — each verified against the pattern:

- `999.1.1.1`: at the first `9` the octet fragment can match `99` or `9`, but a `.` must follow
  and a digit does; later positions are blocked by `(?<![0-9.])`. Unchanged.
- `256.1.1.1`: `25` matches but is followed by `6`, not `.`; `2` likewise. Unchanged.
- `1.2.3.45678`: the fourth octet can be `45` or `4`, but `(?![0-9.])` rejects both. Unchanged.
- `1.2.3.4.5`: `1.2.3.4` is followed by `.`, which `(?![0-9.])` rejects; no later start survives
  the lookbehind. Unchanged.
- `1.2.3`: only three groups. Unchanged.

**Alternatives considered**:

- *Match `\d{1,3}(\.\d{1,3}){3}` and validate the four values in code.* Rejected: it would make
  the IPv4 branch need the same accept/reject-and-resume machinery as cards, for a rule a regex
  expresses exactly. Simplicity (Principle IV) favours the fragment.
- *`ipaddress.IPv4Address` for validation.* Rejected: `ipaddress` accepts forms the spec does not
  (and in 3.9.5+ rejects leading zeros, which the spec requires accepting), so it would have to
  be fenced in by the same regex anyway.

---

## R-006: Argument parsing (FR-001, FR-030, FR-030a)

**Decision**: `argparse.ArgumentParser(prog="python -m logredact", ...)` with
`add_argument("--count", action="store_true")` and
`add_argument("files", nargs="*", metavar="FILE")`, parsed with
**`parser.parse_intermixed_args(argv)`** — *not* `parse_args`. No custom error handling.

**Rationale**: argparse's stock behaviour is the specified behaviour almost everywhere, which
makes it the smallest design. Unrecognized options print usage plus the error to **stderr** and
raise `SystemExit(2)` — FR-030. `-h`/`--help` are added automatically, print to **stdout**, and
exit 0 — FR-030a; because argparse exits during parsing, no input source is opened and no tally
is written even when `--count` is also present. A lone `-` is returned as a positional value
rather than treated as an option (argparse classifies a one-character prefix string as a
positional), so the spec's `-`-is-a-path assumption holds with no special case.

The one place stock behaviour is *not* enough is FR-001's "in any order", and it was caught by
running it rather than by reading the docs. With `nargs="*"`, `parse_args` consumes positionals
as a single greedy group, so an operand list split around an optional fails:
`logredact a.log --count b.log` exits 2 with `unrecognized arguments: b.log` — which would break
Story 2's acceptance scenario 3. `parse_intermixed_args` exists precisely for this case and
parses all of `--count a.log b.log`, `a.log --count b.log`, `a.log b.log --count`, and
`- a.log --count b.log` into the same namespace with `files` in command-line order. It preserves
the `--help`-to-stdout-exit-0 and bad-option-to-stderr-exit-2 behaviours unchanged, so FR-030 and
FR-030a still come for free. Verified against all four orderings plus the bare `-`, empty, and
single-operand cases.

`prog` is set explicitly because under `python -m logredact` the computed default is
`__main__.py`, which would print a usage line a reader cannot copy.

**Alternatives considered**:

- *`parse_args` with `nargs="*"`.* Rejected — it is the bug described above. Worth recording
  because it is the obvious first choice and it fails on a specific acceptance scenario.
- *Hand-rolled `sys.argv` scan.* Rejected: more code, and it would have to re-derive the exit-2
  usage behaviour and the help text argparse already provides.
- *`parse_known_args` plus manually folding the leftovers into `files`.* Rejected: it would also
  silently absorb genuinely unrecognized options, destroying FR-030.
- *`parser.exit_on_error = False` with a custom message.* Rejected: nothing in the spec requires
  a message different from argparse's.

---

## R-007: Detecting and reporting a failed write to stdout (FR-031a, SC-005)

**Decision**: Every write and the final flush go through a helper that catches `OSError` and
raises `OutputWriteError` (a direct `Exception` subclass, deliberately *not* an `OSError`).
`cli.main` handles it by writing one line — `logredact: error: failed writing to standard
output` — to stderr, skipping the tally, redirecting file descriptor 1 to `os.devnull` via
`os.dup2`, and returning 2.

**Rationale**: Three problems had to be solved together. (1) *Attribution*: a write failure
raised while iterating a file would be caught by that file's `except OSError` and reported as
"cannot read FILE" — a wrong diagnostic, which Principle II treats as a failure in itself. A
non-`OSError` exception type propagates past the read handler to its own. (2) *No traceback*:
CPython flushes `sys.stdout` during interpreter shutdown, and if that flush fails it prints
`Exception ignored in: <_io.TextIOWrapper ...>` with a traceback to stderr. FR-031a forbids that
text and SC-005 asserts its absence, so fd 1 is pointed at `/dev/null` before returning; the
shutdown flush then succeeds silently. This is the idiom the Python documentation recommends in
its note on SIGPIPE. (3) *Reaching our handler at all*: CPython sets `SIGPIPE` to `SIG_IGN`, so a
closed pipe surfaces as `BrokenPipeError` (an `OSError`) from `write`/`flush` instead of killing
the process — the default disposition must therefore be left alone, because restoring `SIG_DFL`
would make the process die by signal with no diagnostic and no exit status 2.

Because stdout is block-buffered when piped, the failure typically surfaces on a later `write` or
on the final `flush`, not on the write whose data was discarded. Both call sites go through the
same helper, so either is reported identically. The flush ordering also satisfies FR-024: stdout
is flushed, and only then is the tally written to stderr — so a flush failure suppresses the
tally rather than printing a tally for a truncated log.

**Alternatives considered**:

- *Let `BrokenPipeError` propagate.* Rejected: exit status would be 1 with a traceback, failing
  FR-031a twice over.
- *`signal.signal(SIGPIPE, SIG_DFL)`.* Rejected: the conventional filter idiom, but here it
  defeats the requirement — death by SIGPIPE produces neither the diagnostic nor exit 2.
- *Catching only `BrokenPipeError`.* Rejected: FR-031a names "a destination that runs out of
  space" too, which raises a plain `OSError` (ENOSPC).

---

## R-008: Streaming shape and how SC-006 / SC-007 get verified

**Decision**: Process one line at a time from a lazily-opened source generator; write each
redacted line immediately. Verify SC-007 with a 100,000-line timing test, and verify SC-006 with
a 10 MB single-line case plus a multi-hundred-MB streaming case guarded by a `slow` marker and
skipped by default.

**Rationale**: Peak memory is bounded by the longest line plus the fragment list for that line,
not by total input, which is what SC-006 asks for; opening each file only when the loop reaches
it is also what makes FR-029's "output already written for earlier sources remains written" true.
The honest part to state plainly: a literal 1 GB fixture is not something to generate on every
`pytest` run, so the default suite proves the two properties SC-006 actually rests on — that a
single 10 MB line is handled, and that resident memory is flat while a stream much larger than
memory passes through — and the 1 GB figure is reached by extrapolation from the flat-memory
measurement rather than by a 1 GB run. The slow-marked test does run the large case for anyone
who wants the direct evidence. This limitation is recorded here rather than left implicit.

**Alternatives considered**:

- *`sys.stdin.read()` then one `re.sub` over the whole text.* Rejected: memory proportional to
  input, failing SC-006, and `re.sub` cannot decline a card candidate (R-003).
- *`fileinput`.* Rejected: it cannot be given `encoding`/`errors`/`newline` per the needs of
  R-001 and R-002 in a way that also lets us name the failing path on open, and its
  `inplace`/backup machinery is unwanted surface.

---

## R-009: Test layout and the requirement-to-test mapping (Principle III, SC-004)

**Decision**: `pytest` from the repository root, with `pyproject.toml` carrying only
`[tool.pytest.ini_options]` (`pythonpath = ["src"]`, `testpaths = ["tests"]`, and a `slow`
marker). Unit tests call `redact.redact_line` directly; contract tests invoke the real CLI as a
subprocess through a `run_cli()` helper in `conftest.py` that sets `PYTHONPATH=src` and returns
`(stdout_bytes, stderr_bytes, returncode)`. Every test cites its FR or SC identifier in its name
or docstring; the full matrix lives in [quickstart.md](./quickstart.md).

**Rationale**: `pythonpath` makes `src/` importable without an install step, keeping Principle
I's "runnable on a bare CPython interpreter" literally true — nothing is installed, by tests or
otherwise. Subprocess tests are not a stylistic preference here: SC-001 and SC-003 require
*byte-identical* stdout and stderr and a specific exit status, and FR-031a requires that a
closed pipe be observable; `capsys` replaces `sys.stdout` with an object that has no `buffer`,
so the surrogateescape path and the broken-pipe path cannot be exercised in-process at all.
Comparing raw `bytes` rather than decoded strings is what makes the non-UTF-8 and line-ending
assertions meaningful.

**Alternatives considered**:

- *`capsys`/`capfd` throughout.* Rejected for the contract layer for the reasons above; the unit
  layer needs no capture at all, since `redact_line` returns its result.
- *A root `conftest.py` that mutates `sys.path`.* Rejected: `pythonpath` is declarative and does
  the same job without import-time side effects.
- *Installing the package in editable mode.* Rejected: it introduces the `pip install` step the
  constitution says the project must not need.

---

## Open items carried into Phase 1

None blocking. One item needs a human decision but does not block implementation: the R-000
resolution of the FR-009 / FR-021 conflict is reported to the reviewer in the completion summary,
and reversing it is a one-line pattern change plus a spec amendment.
