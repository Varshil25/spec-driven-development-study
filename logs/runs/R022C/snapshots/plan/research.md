# Phase 0 Research: Phone Redaction and Output Folder

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

This feature changes a shipped tool. The decisions below are therefore *deltas* against the
existing design recorded in [specs/001-logredact-cli/research.md](../001-logredact-cli/research.md)
(decisions D-001…D-010 there, referenced here as `001/D-00n`). Where this document is silent, the
earlier decision stands unchanged — that silence is what implements FR-027.

Every decision below was checked against the live code (`src/logredact/redact.py`,
`src/logredact/__main__.py`) and, where it concerns pattern behaviour, executed against the
spec's edge cases before being written down. The verification transcript is summarised in
[Pattern verification](#pattern-verification).

## Status of unknowns

The Technical Context in [plan.md](./plan.md) carries no `NEEDS CLARIFICATION` markers. The three
items that would otherwise have been unknown were fixed by the user's input to `/speckit-plan`
and by the carried-over Assumptions of the earlier spec:

| Item | Resolution | Source |
|---|---|---|
| Language/version | Python 3.11+ | User input; Constitution "Additional Constraints"; existing `pyproject.toml` `requires-python = ">=3.11"` |
| Runtime dependencies | Standard library only | User input; Constitution Principle I; existing `dependencies = []` |
| Test framework | pytest, no plugins | User input; Constitution Principle III; existing `[tool.pytest.ini_options]` |
| Interface shape | Exactly as the spec states it | User input; [contracts/cli.md](./contracts/cli.md) transcribes it |

No research task was dispatched to a subagent: the whole question space is this repository's own
200 lines of source plus the `re`, `os`, and `io` modules, so direct reading and direct execution
were cheaper and more reliable than delegation.

---

## D-101: Phone recognition — `\+\d{8,15}(?!\d)`, no lookbehind

**Decision**: the phone rule is the pattern

```python
PHONE = r"\+\d{8,15}(?!\d)"
```

**Rationale**, clause by clause against the requirements:

- `\+` — the `+` is *inside* the match, so the replacement consumes it and no stray `+` is left
  beside the placeholder (FR-003). This is why the rule cannot be written as a lookbehind for `+`.
- `\d{8,15}` — FR-002 verbatim: 8 to 15 decimal digits. `{8,15}` is greedy, so the longest
  admissible run is taken first; that matters only in combination with the next clause.
- `(?!\d)` — FR-004. The interesting part is *why this suffices*. For a `+` followed by 16 digits
  the engine tries 15 digits, fails the lookahead on the 16th, backtracks to 14, fails again, and
  so on down to 8; every length fails because a digit always follows. The candidate is abandoned
  at that start position, and the engine then advances to the next character, which is a digit,
  not a `+`. So no prefix of a long run is ever replaced, and `[PHONE]67` — a corrupted line that
  also leaks part of the value — is structurally impossible rather than merely untested.
- **No leading lookbehind at all** — FR-005 states that the characters preceding the `+` place no
  constraint on the match, which is a requirement *not* to add the `(?<!\d)` guard the card rule
  carries (`001/D-003`). This is what makes `100+14155552671` → `100[PHONE]` and `++14155552671`
  → `+[PHONE]` (the match starts at the second `+`, because `\+` cannot match a `+` followed by
  another `+`).
- `\d` rather than `[0-9]`: the module is already on `re` defaults where `\d` is Unicode-aware,
  so `\d` would also accept non-ASCII decimal digits such as `١٢٣٤٥٦٧٨`. This is deliberate and
  consistent — the existing card and IPv4 rules use `\d` under the same defaults (`001/D-002`,
  `001/D-003`), and FR-027 requires consistency with them over local purity. An
  over-redaction of an Arabic-Indic digit run preceded by `+` is a conservative failure for a
  privacy tool, in the safe direction.

**Alternatives considered**:

| Alternative | Rejected because |
|---|---|
| `\+\d{8,15}\b` | `\b` is the wrong boundary. After the 15th digit of a 16-digit run, digit-to-digit is *not* a word boundary, so this happens to work for FR-004 — but it also fails where the number is followed by a letter or underscore (`+14155552671x`), which no requirement excludes. `(?!\d)` says exactly what FR-004 says and nothing else. |
| `\+\d{8,15}(?![\d])` plus `(?<!\d)` before the `+` | Directly contradicts FR-005 and would leave `100+14155552671` unredacted — a leak. |
| `\+[\d\s\-().]{8,}` (tolerant of separators) | Out of scope by the spec's Assumptions ("Digits only, directly after the `+`") and a large false-positive surface: it would eat arithmetic and ranges. SC-003 measures exactly this. |
| Python-side length check on a looser pattern | Adds a second code path for something `{8,15}` already expresses, against Principle IV, and reintroduces the partial-replacement hazard the lookahead closes. |

**Accepted consequence** (worth stating because it will look like a bug): a `+` immediately
followed by 8-15 digits is redacted *whatever precedes it*, so semantic-version build metadata
such as `1.0.0+20260101` becomes `1.0.0[PHONE]`. This follows necessarily from FR-002 and FR-005
and cannot be narrowed without contradicting FR-005. It is in the over-redaction direction, so
nothing leaks. SC-003's "signed version strings" corpus must therefore be built from version
strings whose build metadata is *not* an 8-to-15-digit run (`1.0.0+build.1`, `2.3.4+exp.sha.5114f85`),
which is the ordinary shape; a date-stamped build is the exception. Flagged for
`/speckit-clarify` if that trade is unwanted.

## D-102: Precedence — phone becomes a third branch of the existing pass A alternation

**Decision**: extend the single compiled alternation to three named branches, in this order:

```python
EMAIL_OR_IPV4_OR_PHONE = re.compile(rf"(?P<email>{_EMAIL})|(?P<ip>{_IPV4})|(?P<phone>{_PHONE})")
```

Cards stay in their own second pass, unchanged (`001/D-004`, `001/D-005`).

**Rationale**: FR-006 requires the precedence *email → IPv4 → phone → card* at an equal start
position. Python's alternation is leftmost-first: the earliest start position wins, and at an
equal start position the earlier branch wins. Writing phone third therefore *is* FR-006 for the
first three rules, with no arbitration code at all — the same argument `001/D-004` made for email
beating IPv4.

The phone-before-card half of FR-006 needs a different argument, and gets one for free:

- The two rules can never start at the same position. `CARD` begins `(?<!\d)\d` — a digit — and
  phone begins `\+`. So "equal start position" is vacuous between them, and FR-006's ordering is
  observable only as *overlap* resolution.
- Overlap is resolved by pass order: pass A runs first, and `re.sub` never rescans its own
  replacement text (`001/D-005`), so anything phone claims is invisible to the card pass. A
  Luhn-valid `+123456789012345` (15 digits) becomes `[PHONE]`, not `+[CARD]`.
- Conversely, when phone *declines* a candidate under FR-004, the card pass sees the raw digits
  and may claim them: `+4111111111111111` → `+[CARD]`, which is the spec's own edge case
  ("Phone digits that also form a card"). Verified below.

**Why this is not a regression risk** (FR-027, SC-005): adding a branch to a leftmost-first
alternation can only add matches at positions where no earlier branch matched, or preempt a
*later-starting* email/IPv4 match that overlaps the new one. The second case is where a
regression would hide, so it was reasoned through and then tested:

- An IPv4 match cannot overlap a phone match from a later start. A phone match's interior is all
  digits and an IPv4 address needs dots, and the phone match ends on a non-digit, so no octet
  quad can begin inside one and continue past it.
- An email match *can* overlap, because `+` and digits are both legal local-part characters. But
  the email rule's own lookbehind `(?<![A-Za-z0-9._%+\-])` means that wherever an email overlaps a
  phone candidate, the email's start position is at or before the phone's — so the email is
  leftmost and still wins. `+12345678@b.io` → `[EMAIL]` (equal start, email branch first);
  `x+12345678@b.io` → `[EMAIL]` (email starts one character earlier). In both the whole address
  is redacted and the domain is not left exposed, which is the outcome the spec's Assumptions
  ("Precedence placement") ask for.
- Lines with no `+`-plus-8-digit run are byte-for-byte unaffected, because the new branch cannot
  match. That is the bulk of SC-005.

**Alternative rejected**: a fourth separate pass for phone, between pass A and the card pass.
It would need its own `re.sub` over the whole line — a measurable second scan of every line for
no behavioural gain (the alternation already delivers FR-006) — and it would get the email case
*wrong*: running after pass A, a phone pass would see `+12345678@b.io` only if email had not
already claimed it, which it has; but running before pass A it would produce `[PHONE]@b.io` and
leak the domain. Branch ordering inside one alternation is both cheaper and correct by
construction.

## D-103: The tally gains a fourth field, and `Counts` gains `__add__`

**Decision**: `Counts` becomes four fields, with `phones` appended last and defaulted:

```python
@dataclass(frozen=True, slots=True)
class Counts:
    emails: int = 0
    ips: int = 0
    cards: int = 0
    phones: int = 0

    def __add__(self, other: "Counts") -> "Counts": ...
```

**Rationale for appending with a default**: every existing unit test constructs `Counts` by
keyword with a subset of fields (`Counts(emails=1)`, `Counts(emails=2, ips=1, cards=2)`). A new
trailing field defaulting to `0` keeps all of them passing *and still asserting the same thing*,
because a run with no phone numbers has `phones=0`. That is SC-005 for `tests/test_redact.py`
discharged by construction rather than by editing tests.

**Rationale for `__add__`**: the CLI sums counts in two places — per line inside the copy loop,
and per file in `main`. With three fields that was six `+=` statements; with four it becomes
eight, each a place to transpose a field name silently. `__add__` replaces all of them with
`total = total + counts`, which is less code overall, not more, and makes a transposition
impossible. Under Principle IV this is a net deletion of moving parts, so it needs no complexity
justification — but it is recorded here because it widens the `Counts` surface, which is a public
engine type.

Deliberately **not** added: `__radd__` (so `sum()` works), `__sub__`, mutation, or a `total`
property. None has a caller. The accumulator starts from an explicit `Counts()`.

**Alternative rejected**: keep returning a plain tuple of ints from the copy helper, as today.
It scales worst of the options — a 4-tuple unpacked at two call sites, with position rather than
name carrying the meaning.

## D-104: Argument parsing — index-based loop, value token taken literally

**Decision**: the existing `for token in argv` becomes an indexed `while` loop, because
`--out-dir` has to consume the *following* token. The classification table becomes:

| Token | Action |
|---|---|
| `--count` | set the tally flag (unchanged, any position) |
| `--out-dir` | take `argv[i+1]` verbatim as the folder path; if there is no `argv[i+1]`, usage error, exit 2 (FR-012) |
| anything else starting with `-` and longer than 1 char | unrecognised option, exit 2 (unchanged) |
| anything else | a FILE path (unchanged) |

**Rationale**: FR-011 says the value is "the immediately following command-line token, taken
literally as the output folder path whatever its shape". Consuming `argv[i+1]` unconditionally —
*without* testing whether it looks like an option — is that requirement exactly, and it is what
makes `--out-dir --count` use a folder named `--count` (spec Edge Cases, "Option-shaped folder
value"). Assigning on each occurrence makes the last one win (FR-021) with no extra code.

`--out-dir=DIR` is **not** recognised: it falls through to the unrecognised-option branch and
exits 2, per the spec's Assumptions. This is behaviour inherited unchanged from `001/FR-024`, and
is why the `=` form needs no code.

`argparse` remains rejected for the reason given in `001/D-007` — it cannot accept
`logredact a.log --count b.log` — and the new option does not change that calculus.

## D-105: The `USAGE` string stays byte-identical

**Decision**: `USAGE` keeps its current text, *without* mentioning `--out-dir`:

```text
usage: python -m logredact [--count] [FILE ...]
```

**Rationale**: this is a genuine conflict between two things a reasonable engineer wants, and the
spec settles it. `tests/test_cli.py::test_fr024_unrecognized_option_usage_to_stderr_nothing_processed`
asserts that exact line. SC-005 requires the earlier suite to pass **unchanged except for the
tests of the summary line's form**, and FR-027 preserves "unrecognised option handling" — of
which the emitted usage text is part. No requirement in FR-001…FR-026 asks the usage line to
document `--out-dir`; FR-012 asks only for "a usage message", which this is.

So the stale-looking usage line is the specified outcome, not an oversight. The cost is real: a
user who mistypes an option is not told `--out-dir` exists. The option is documented instead in
[contracts/cli.md](./contracts/cli.md) and [quickstart.md](./quickstart.md).

**Flagged for `/speckit-clarify`**: if the intent was that the usage line should grow to
`usage: python -m logredact [--count] [--out-dir DIR] [FILE ...]`, then SC-005's exception list
needs a second entry (the usage-line test) and this decision reverses. It is a one-line change in
each place; it is left undone only because the spec as written forbids it.

**Alternative rejected**: a second, longer usage string used only for the new option's errors.
Two usage texts for one command line is a moving part with no requirement behind it (Principle IV)
and would read as a bug.

## D-106: Order of operations — validate fully, then create the folder, then read

**Decision**: `main` proceeds in four strictly ordered stages:

1. Parse all tokens (may exit 2: unrecognised option, `--out-dir` with no value).
2. Validate the combination: `--out-dir` with an empty FILE list exits 2 (FR-020).
3. Create the folder with `os.makedirs(out_dir, exist_ok=True)` (may exit 2: FR-024).
4. Loop over FILE arguments; emit `wrote N files`, then the tally.

**Rationale**: every stage is ordered by "cheapest and least destructive check first", which is
what the three spec scenarios demand jointly. FR-020 requires that `--out-dir` with no FILE reads
*nothing* and writes *nothing to stdout* — putting it before stage 3 also means it creates no
directory, which the spec does not require but which keeps a pure-usage-error invocation free of
filesystem side effects. The spec's Assumptions ("Output folder is created up front") require
stage 3 before stage 4, so an unusable folder fails before any input is read and before any
output file exists.

Note what stage 2 protects: without it, `--out-dir clean` with no FILE would fall through to the
stdin branch and stream redacted data to stdout, making the option look as though it had worked
while writing nothing to `clean`. Constitution Principle II is explicit that a plausible-looking
wrong answer is the worst outcome.

## D-107: Folder creation — `os.makedirs(..., exist_ok=True)` covers FR-016 and FR-024 together

**Decision**: one call, `os.makedirs(out_dir, exist_ok=True)`, wrapped in `except OSError`.

**Rationale**: CPython implements `exist_ok=True` as "attempt `mkdir`; on `OSError`, re-raise
unless the path is now a directory". That gives all three required behaviours from one call:

| Situation | Outcome | Requirement |
|---|---|---|
| `DIR` missing, parents missing | created recursively | FR-016 |
| `DIR` already a directory | used as-is, contents untouched | FR-016 |
| `DIR` exists as a regular file | `FileExistsError` (an `OSError`) → diagnostic, exit 2 | FR-024 |
| a *parent* component is a regular file | the recursive step raises `FileExistsError` → exit 2 | FR-024 |
| `DIR` unwritable parent | `PermissionError` → exit 2 | FR-024 |
| `DIR` is the empty string | `FileNotFoundError` → exit 2 (the literal-value rule of FR-011 taken to its conclusion) | FR-024 |

The diagnostic names the path **as the user gave it** — `logredact: {out_dir}: {reason}` — not the
failing intermediate component, matching the existing diagnostic shape (`001/D-009`). For
`--out-dir out/2026/clean` where `out` is a file, that reads
`logredact: out/2026/clean: File exists`: it names the path the user typed and states what went
wrong, which is FR-024 and Principle II.

**Alternative rejected**: a pre-flight `os.path.isdir` / `os.access` check before `makedirs`.
Rejected for the same two reasons as `001/D-009` — it is a TOCTOU race, and it builds a second
code path for a failure the exception already describes better.

## D-108: Output file naming and open mode

**Decision**:

```python
out_path = os.path.join(out_dir, os.path.basename(path))
open(out_path, "w", encoding="utf-8", newline="", errors="strict")
```

**Rationale**:

- `os.path.basename` is FR-014 exactly: the final path component, so `logs/2026/app.log` →
  `DIR/app.log` and the input's directories are not reproduced inside the folder. It is also what
  makes the spec's "duplicate file names from different directories" edge case fall out —
  `a/app.log` and `b/app.log` both resolve to `DIR/app.log`, processed in argument order, second
  wins — with no deduplication code.
- Mode `"w"` truncates on open. That is FR-017 ("no bytes of the previous content") with no
  explicit truncate call and no stat-then-decide branch.
- The three keyword arguments are **the same three the stdout wrapper uses**
  (`001/D-008`). That identity is the whole of FR-015: same encoding, same disabled newline
  translation, therefore byte-identical output and exact round-tripping of CRLF and a missing
  final newline. Any divergence here would be the one way to silently break line fidelity, so it
  is worth stating as an invariant: *the destination is opened with the same arguments as the
  stdout wrapper, or FR-015 is broken.*
- Writing streams line by line through the existing copy helper, so SC-007's memory envelope is
  unchanged — a 1 MB line and a 1 GB file behave as they do for stdout today.

**No atomic write**: no temporary file plus rename. The spec's Assumptions say so explicitly ("No
atomic or temporary-file writes"), and the non-zero exit status is the documented signal that a
part-written output file may exist.

## D-109: Attributing a failure to the input path or the output path

**Decision**: open the input first, then the output, with the output's handling *nested inside*
the input's:

```text
try:                                  # outer: input
    with open(path, ...) as source:
        try:                          # inner: output
            with open(out_path, "w", ...) as destination:
                counts = copy(source, destination)
        except OSError as exc:
            -> "logredact: {out_path}: {reason}", exit 2      # FR-025
except (OSError, UnicodeDecodeError) as exc:
    -> "logredact: {path}: {reason}", exit 2                  # FR-023
```

**Rationale**: FR-023 and FR-025 require *different* diagnostics — one naming the FILE, one naming
the output path — so the two failures must be distinguishable, and the obvious single `try` around
both would conflate them. Nesting resolves it positionally for the two opens, which is where every
specified failure mode actually arises (missing input, input is a directory, permission denied,
output path is a directory, output not writable).

Two consequences are deliberate and documented rather than accidental:

- **Input is opened before output**, so an unreadable FILE fails *without* leaving a stray empty
  output file named after it. This is what makes the spec's Story 4 scenario 4 clean: first file's
  output written, second file named on stderr, exit 2, and no empty `DIR/missing.log`.
- **During the copy loop**, `UnicodeDecodeError` escapes the inner handler (it is not an
  `OSError`) and is attributed to the **input** — correct, since only the input is being decoded.
  An `OSError` raised mid-copy is attributed to the **output**. That is a judgement call: a
  mid-stream `OSError` is almost always a write failure (`ENOSPC`, `EPIPE` on the target), while a
  mid-stream read failure needs failing hardware. Neither case is in the spec's failure list and
  neither is reachable in a test without fault injection, so the simpler attribution is taken and
  recorded here instead of being discovered later.

`except OSError` — never a bare `except` and never `except Exception: pass` — keeps Principle II
satisfied: the exception is caught only to add the path context and translate to an exit status.

## D-110: `wrote N files` — counted as files processed, written before the tally

**Decision**: increment a counter after each output file is closed successfully; after the loop,
write exactly one `wrote {n} files\n` line to the stdout wrapper, then the tally line to stderr.

**Rationale**: FR-018 defines N as "the number of output files written — one per FILE argument
processed", and the spec's Assumptions make the consequences explicit: `wrote 2 files` for two
arguments that collide on the same output name, and `wrote 1 files` for one argument — the plural
noun is fixed, with no pluralisation branch. On the success path the counter is necessarily
`len(paths)`, so it carries no new information; it is incremented as the loop runs anyway, because
that makes it impossible for a future partial-failure path to report files it did not write.

Ordering: `wrote N files` goes to stdout, the tally to stderr *after* all stdout is flushed
(FR-019, preserving `001/FR-019`'s "after all standard output" rule). FR-026 is satisfied
structurally — both writes sit after every `return 2`, so no exit-2 path can reach either.

The `wrote N files` line is the **only** thing on stdout in `--out-dir` mode (FR-013, FR-018: no
per-file progress). A side benefit noted in the spec's Edge Cases: because no redacted data goes
to stdout, a closed stdout cannot truncate redacted output. The existing `SIGPIPE` restoration
(`001/D-010`) still applies to that one line, so the process dies with status 141 and no
traceback rather than crashing.

## Pattern verification

D-101 and D-102 were executed against every phone and precedence case the spec names, using the
real `_EMAIL`, `_IPV4`, `CARD`, and `luhn` from `src/logredact/redact.py` with the candidate
alternation spliced in. All 19 asserted cases produced the spec's stated output:

```text
'call +14155552671 now'                 -> 'call [PHONE] now'          Scenario 1.1
'+442071838750 and +14155552671'        -> '[PHONE] and [PHONE]'       Scenario 1.2
'ext +1234567'                          -> unchanged                   Scenario 1.3  (7 digits)
'ref +1234567890123456'                 -> unchanged                   Scenario 1.4  (16 digits)
'total 100+25 units'                    -> unchanged                   Scenario 1.5
'+12345678'                             -> '[PHONE]'                   Exact lower bound
'+123456789012345'                      -> '[PHONE]'                   Exact upper bound
'++14155552671'                         -> '+[PHONE]'                  Doubled sign
'100+14155552671'                       -> '100[PHONE]'                Sign preceded by a digit
'+12345678@b.io'                        -> '[EMAIL]'                   Email precedence, equal start
'x+12345678@b.io'                       -> '[EMAIL]'                   Email precedence, earlier start
'jane@example.com+14155552671'          -> '[EMAIL][PHONE]'            Phone after an email
'+1.2.3.4'                              -> '+[IP]'                     Dotted form
'1.2.3.4+12345678'                      -> '[IP][PHONE]'
'+1 415 555 2671'                       -> unchanged                   Separators inside a number
'+1-415-555-2671'                       -> unchanged                   Separators inside a number
'[PHONE] already'                       -> unchanged                   Literal placeholder in input
'+4111111111111111'                     -> '+[CARD]'                   Phone digits that form a card
'a@b.io 10.0.0.7 4111 1111 1111 1111 +442071838750'
                                        -> '[EMAIL] [IP] [CARD] [PHONE]'   Scenario 1.6
```

Two notes from the run, both already covered above: the spec's illustrative
`+4417123456789012` is **not** Luhn-valid (`luhn("4417123456789012") is False`), so it is left
unchanged — the spec's edge case is conditional ("*if* those sixteen digits are Luhn-valid"), and
`+4111111111111111` is the case that exercises the `+[CARD]` outcome. And
`1.0.0+20260101` → `1.0.0[PHONE]`, the accepted consequence recorded in D-101.

Baseline before any change: `python -m pytest -q` → **31 passed, 1 skipped**. That is the number
SC-005 is measured against; the skip is the pre-existing permission-denied test, skipped when the
suite runs as root.

## Throughput (SC-007)

SC-007 carries forward `001/SC-006`'s envelope with a fourth rule in place, so it must be
re-measured rather than assumed. The cost model says it will hold: the phone branch adds no new
scan (D-102 folds it into the existing alternation) and the branch is anchored on a literal `+`,
which the regex engine's prefix scan skips cheaply on lines without one. The `--out-dir` path adds
one `open`/`close` per FILE and writes the same bytes to a file instead of a pipe.

Measurement is therefore a task for the implementation phase, not a decision here: time a
100 000-line file to stdout *and* to `--out-dir`, both under 10 s, and confirm resident memory is
flat for a 1 GB input. The procedure is in [quickstart.md](./quickstart.md) Scenario 6.

## Consolidated decision summary

| # | Decision | Chief alternative rejected | Requirements |
|---|---|---|---|
| D-101 | Phone pattern `\+\d{8,15}(?!\d)`, no lookbehind | `\b` boundary; separator-tolerant pattern | FR-002…FR-005 |
| D-102 | Phone as the third branch of the existing pass-A alternation | A fourth separate `re.sub` pass | FR-001, FR-006, FR-007 |
| D-103 | `Counts` gains `phones` (defaulted, last) and `__add__` | Plain int/tuple accumulators | FR-008, FR-009, SC-005 |
| D-104 | Indexed parse loop; `--out-dir` eats the next token literally | `argparse`; `--out-dir=DIR` support | FR-011, FR-012, FR-021 |
| D-105 | `USAGE` text left byte-identical | Adding `--out-dir` to the usage line | FR-012, FR-027, SC-005 |
| D-106 | Parse → validate → create folder → read | Creating the folder during parsing | FR-012, FR-016, FR-020 |
| D-107 | One `os.makedirs(..., exist_ok=True)` under `except OSError` | `isdir`/`access` pre-flight check | FR-016, FR-024 |
| D-108 | `basename` + mode `"w"` + the stdout wrapper's own open arguments | Mirroring input directories; atomic rename | FR-014, FR-015, FR-017 |
| D-109 | Input opened first; output handling nested inside | One `try` around both opens | FR-023, FR-025 |
| D-110 | Count files as processed; `wrote N files` to stdout, then the tally | Reporting `len(paths)`; pluralising the noun | FR-018, FR-019, FR-026 |
