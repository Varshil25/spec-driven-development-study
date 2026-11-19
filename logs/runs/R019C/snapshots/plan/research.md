# Phase 0 Research: Phone Number Redaction and Output Folder

**Feature**: `002-phone-redaction-out-dir` | **Date**: 2026-11-14

**Input**: [spec.md](./spec.md); the existing implementation in `src/logredact/` and the
decisions it rests on in [`../001-redact-log-pii/research.md`](../001-redact-log-pii/research.md).

The spec carried **no NEEDS CLARIFICATION markers** into this phase — its three clarifications
(2026-11-14) settled the `+`-prefixed card question, the "only complete output files" guarantee,
and the timing of the collision check. What remained were *technical* unknowns: which mechanism
implements each settled rule. Those are resolved below.

Every pattern, every argparse behaviour, and every filesystem behaviour quoted here was
**executed and verified** during this phase, following the precedent set by 001 research.

---

## R-001: The phone number pattern

**Decision**: `_PHONE = r"\+\d{8,15}(?!\d)"`, added as a fourth named alternative, last:

```python
PATTERN = re.compile(rf"(?P<email>{_EMAIL})|(?P<ip>{_IP})|(?P<card>{_CARD})|(?P<phone>{_PHONE})")
```

**Rationale**: three requirements fall straight out of this one expression.

- The `+` is inside the match, so it is replaced with the digits (FR-002).
- `(?!\d)` is what makes "16 or more digits is not a phone number" true rather than "the first
  15 digits of it are" (FR-003). Without it, `\d{8,15}` happily matches a 15-digit prefix of a
  30-digit run and emits `[PHONE]` glued to the leftover digits — the exact failure the spec's
  "Longer digit run" edge case forbids. Verified: `+1234567890123456` (16 digits) and
  `+12345678901234567890123456789012` (32 digits) both come back **unchanged**.
- There is deliberately **no** `(?<!\d)` lookbehind on the `+`. The spec's "No phone inside a
  longer number" edge case requires `5+14155552671` to still be examined, because what precedes
  the `+` is not part of a phone number. Verified: `5+14155552671` → `5[PHONE]`.

**Alternatives considered**:

- *Possessive `\+\d{8,15}+(?!\d)`* — same result, no backtracking. Rejected only for
  readability: the non-possessive form is already O(1)-bounded by `{8,15}`, so the possessive
  form buys nothing here, unlike in `_CARD` where it is load-bearing.
- *Allowing separators (`+1 415 555 2671`)* — rejected by the spec's Assumptions: it would
  require inventing grouping rules the request does not state (Principle IV). Verified that both
  `+1 415 555 2671` and `+1-415-555-2671` are left alone and, importantly, are treated **exactly
  as today** (the residual card candidate `1 415 555 2671` is 13 digits but fails Luhn, with or
  without this feature).
- *A separate `re.sub` pass for phones* — rejected: a second pass would re-scan placeholders
  inserted by the first and would break the single left-to-right resolution FR-004 requires.

## R-002: Where the `+`-prefixed-card exclusion lives (FR-003a)

**Decision**: in the **validator**, not in the pattern. In `_replacement`, before the length and
Luhn checks:

```python
if _is_plus_prefixed_digit_run(match):
    return text          # FR-003a: never a card, whatever its length or Luhn status
```

where the test is "the candidate contains no separator **and** the character immediately before
it is `+`", read from `match.string[match.start() - 1]`.

**Rationale**: FR-003a excludes an *unbroken run of digits* preceded by `+`, and explicitly
preserves today's behaviour for the separated form: `+4111 1111 1111 1111` must still be
`+[CARD]`. The obvious pattern-level fix — adding `(?<!\+)` to `_CARD` — gets the unbroken case
right and the separated case **wrong**, because it blocks the candidate at the `4` and the
engine then restarts at the second group, yielding a 12-digit remainder that fails the length
check. Verified both ways:

| Input | `(?<!\+)` in `_CARD` | Validator check (chosen) | Spec requires |
|-------|----------------------|--------------------------|---------------|
| `pay +4111111111111111 now` | unchanged ✓ | unchanged ✓ | unchanged (FR-003a) |
| `+4111 1111 1111 1111` | **unchanged ✗** | `+[CARD]` ✓ | `+[CARD]` (FR-003a final sentence) |

The validator already exists for precisely this job — it is where the IPv4 octet range and the
card length + Luhn tests live, and its established contract is "a candidate that fails
validation is returned whole and unchanged and increments nothing". FR-003a is one more
validation rule in that same shape, so it adds a branch rather than a mechanism
(Principle IV). The regex stays a *recognition* device and the callback stays the place where
checks regexes cannot express are made — the split 001 chose.

**Alternatives considered**:

- *`_CARD = r"(?<!\d)(?:(?<!\+)\d++(?:[ -]\d++)*+|\d++(?:[ -]\d++)++)"`* — a doubled alternation
  that gets both cases right in-pattern. Rejected: two near-identical branches whose difference
  is a lookbehind, versus one `if` with a comment naming FR-003a.
- *Dropping the 15-digit upper bound so a 16-digit run becomes `[PHONE]`* — out of scope here;
  the spec's clarification considered and rejected it.

## R-003: Precedence and the leftmost rule with four types

**Decision**: append `phone` as the **last** alternative. No other change to resolution.

**Rationale**: `re.sub` scans positions left to right and, at each position, tries the
alternatives in written order. That gives FR-004 (earliest candidate wins, scanning resumes
after the replacement) and FR-005 (email → ip → card → phone at equal start) for free, exactly
as 001 obtained FR-018/FR-019. Two consequences were verified rather than assumed:

- `+4111111111119` → `[PHONE]`, counted as a phone. The phone candidate starts at the `+`, one
  character before the card candidate, so position — not alternation order — decides it.
- `+15551234567@example.com` → `[EMAIL]`, counted as an email. Both candidates start at the `+`
  (the email local-part class already contains `+`), and `email` is written first.
  `jane+15551234567@example.com` → `[EMAIL]` as well, by position.

The literal `[PHONE]` contains neither `+` nor a digit run, so FR-006 needs no mechanism:
verified that `[PHONE] [EMAIL] [IP] [CARD]` passes through with all four counters at zero.

## R-004: `--out-dir` and `parse_intermixed_args`

**Decision**: `parser.add_argument("--out-dir", dest="out_dir", default=None, metavar="DIR")`,
keeping `parse_intermixed_args`. Also give the positional `metavar="FILE"`.

**Rationale**: FR-009 requires the option to work in any position relative to `--count` and the
FILE arguments. `parse_intermixed_args` (chosen in 001 R-001 because plain `parse_args` rejects
a flag between two filenames) handles an option **with a value** in the same way. All four
orderings were verified:

```text
a.log --out-dir clean b.log   → out_dir='clean', files=['a.log','b.log']
--out-dir clean --count a.log → out_dir='clean', count=True, files=['a.log']
a.log b.log --count --out-dir x → out_dir='x', count=True, files=['a.log','b.log']
--out-dir=clean a.log         → out_dir='clean', files=['a.log']
```

`metavar="FILE"` makes the generated usage line
`usage: python -m logredact [-h] [--count] [--out-dir DIR] [FILE ...]`, which matches how the
001 contract document already wrote it. The one existing test over usage text asserts only that
`usage:` appears on stderr, so this is a documentation alignment, not a contract change.

**Alternatives considered**: `type=pathlib.Path` — rejected, because FR-016 and FR-018 require
the diagnostic to name the path **exactly as written on the command line**, and 001 R-007
already established that paths are never normalised for that reason. Keeping the raw string
removes the chance of a normalised path reaching a message.

## R-005: The pre-flight — order of the three failure checks

**Decision**: before any FILE is opened, in this order:

1. **FR-019** — `out_dir` given with no FILE → `parser.error("--out-dir requires at least one FILE")`.
2. **FR-020** — collision check over **every** FILE.
3. **FR-015** — `os.makedirs(out_dir, exist_ok=True)`.

**Rationale**:

- The usage check comes first so that a usage error never has a filesystem side effect. Routing
  it through `parser.error` reuses argparse's existing behaviour — usage line plus
  `python -m logredact: error: ...` on stderr, nothing on stdout, `SystemExit(2)` — which is
  already how FR-029 (unrecognised argument) behaves, so FR-019 introduces no new exit path and
  no new message shape. Standard input is never touched.
- The collision check comes **before** `makedirs` so that a doomed command line leaves the
  filesystem untouched, honouring FR-020's "the destination otherwise untouched". Ordering is
  safe in both directions: if DIR does not exist, no output path inside it can exist either, so
  no collision is detectable and the check trivially passes.
- `makedirs(..., exist_ok=True)` satisfies "created with missing parents" and "an existing DIR
  is used as it is" in one call (FR-011). Verified: a three-level missing path is created;
  pointed at an **existing regular file** it raises `FileExistsError` with `strerror`
  `"File exists"` — so the FR-016 diagnostic path is a plain `except OSError` reusing the
  existing `_report`, naming DIR as given.

**Collision test** (FR-020):

```python
def _collides(name, out_path):
    try:
        return os.path.samefile(name, out_path)
    except OSError:
        # One of the two does not exist (or cannot be stat'ed), so they cannot be
        # the same file on disk. A missing FILE is NOT a collision: it fails later,
        # in its own turn, with the FR-018 diagnostic.
        return False
```

`os.path.samefile` compares device and inode, so it catches `--out-dir . app.log`, a symlink,
and a hard link alike — all cases where "replace the existing file" would destroy the input
mid-read. Verified that it returns `True` for a file against itself reached by a different path
and raises `FileNotFoundError` when either side is missing. Swallowing that one error is a
*meaningful recovery* with a stated reason, not a silent catch (Principle II): a FILE that does
not exist must reach the existing FR-018 handler so that earlier FILEs keep their output, which
is exactly what Story 3 scenario 4 requires.

**Alternatives considered**: resolving both sides with `os.path.realpath` and comparing strings
— rejected, it misses hard links and is defeated by any path quirk `samefile` handles natively.

## R-006: The output file's text contract (FR-013)

**Decision**: `open(path, "w", encoding="utf-8", errors="surrogateescape", newline="")` —
character for character the settings `_configure_streams` pins on `sys.stdout`.

**Rationale**: FR-013 requires each output file to be byte-for-byte what stdout would have
received. Pinning the same encoding, the same `surrogateescape` error handler, and the same
`newline=""` (no line-ending translation on write) makes that true **by construction** rather
than by testing. Verified end to end: a file containing `a\r\nb\xff\xfe\nno-trailing` — CRLF,
an undecodable byte pair, and no final newline — read through the existing input settings and
written through these output settings is byte-identical to the original.

`"w"` mode supplies FR-012 (an existing file of that name is replaced, not appended to) in the
same call.

## R-007: Only complete output files ever remain (FR-017a)

**Decision**: two mechanisms, both at the per-FILE level.

1. **Open the input first, the output second.** The output file is created only after the input
   has opened successfully, so a FILE that cannot be opened leaves no file of its name in DIR.
2. **Remove a partly-written output file on failure.** When writing or reading stops partway, or
   when `close()` fails, `os.remove(out_path)` runs before the diagnostic is reported.

**Rationale**: FR-017a demands both halves, and neither is implied by the other. Ordering alone
cannot help once bytes are on disk; removal alone leaves a stray empty file for an unreadable
input. Point 1 costs nothing — it is just the order of two statements.

The **close** must be inside the failure scope, not left to a `with` block: on a full filesystem
the error typically surfaces when the buffer is flushed, which is at `close()`, not at `write()`.
Verified that when `close()` raises, the stream is nonetheless left in `closed == True` state and
the file is still on disk and still removable — so the sequence `close() → os.remove()` is sound.

```python
def _discard(path):
    try:
        os.remove(path)
    except OSError:
        # The run is already failing and its diagnostic is already written; a
        # destination we cannot even delete from has nothing left to report.
        pass
```

This is the one swallowed error in the design. It is narrow (`OSError`), it cannot hide a
successful run (the caller is on its way to exit 2 with a diagnostic already composed), and the
alternative — replacing the real failure with the removal's failure — would name the wrong
cause. Recorded in the plan's Complexity Tracking.

**Alternatives considered**: *write to a temporary file and `os.replace` it into position on
success*. This is the textbook atomic-write pattern and it does satisfy FR-017a. Rejected:
`os.replace` is only atomic within one filesystem, it leaves a stray temp file if the process is
killed, and it requires inventing a temp-name scheme — three moving parts to buy atomicity the
spec never asks for. FR-017a asks only that no *truncated or stray* file remain after a normal
failure exit, which create-late-and-remove delivers directly (Principle IV).

## R-008: Attributing a mid-stream failure to the right path

**Decision**: nest the write's error handling inside the read's, and return the path to name
rather than raising:

```python
def _redact_into(stream, out, totals, name, out_path):
    """None on success, or (path, error) naming what the diagnostic must report."""
    try:
        for line in stream:                      # read failures land in the outer handler
            text, counts = redact_line(line)
            _accumulate(totals, counts)
            try:
                out.write(text)
            except BrokenPipeError:
                raise                            # 001:FR-028 wins on the stdout path
            except OSError as error:
                return out_path, error           # FR-017: name the output file
    except BrokenPipeError:
        raise
    except OSError as error:
        return name, error                       # FR-018: name the input FILE
    return None
```

**Rationale**: FR-017 and FR-018 require *different* paths in the diagnostic, and once the read
loop and the write are interleaved in one `for`, a single handler cannot tell them apart.
`error.filename` is not a reliable discriminator — `open()` sets it, a failed `write()` does not.
Nesting makes attribution structural. Returning a `(path, error)` pair rather than raising a
custom exception avoids introducing an exception class for a value that only travels one frame
(Principle IV); a `return` from inside the inner `try` passes through the outer handler
untouched.

The two `except BrokenPipeError: raise` clauses are the same guard the existing code already
carries, for the same reason: `BrokenPipeError` **is** an `OSError`, and on the stdout path an
early-closing consumer is not a write failure and must reach the outer FR-028 handler, which
exits 0 in silence. On the `--out-dir` path `out` is a regular file and cannot raise it.

## R-009: Impact on the existing 001 test suite (SC-004)

**Decision**: the only edits required to the 1,405 existing test lines are the **count-shape**
assertions, which FR-007 forces.

**Rationale**: surveyed the suite directly.

- 14 assertions on the summary string (`tests/cli/test_count_flag.py`,
  `test_invocation.py`, `test_output_fidelity.py`) gain ` phones=N`, and the
  `SUMMARY` regex gains a fourth key. The assertions of the form
  `assert b"emails=" not in proc.stderr` — the suppression tests — are unaffected.
- 7 assertions on the `redact_line`/`new_counts` dictionaries
  (`tests/unit/test_counting.py`) gain a `"phones": 0` key.
- The usage test asserts only `b"usage:" in proc.stderr`, so R-004's `metavar` change does not
  reach it.
- **No existing test uses a `+`-prefixed digit run**, so FR-003a breaks nothing that is
  currently asserted. The two genuinely changed behaviours (`+4111111111119` → `[PHONE]`,
  `+4111111111111111` → unchanged) are new coverage, not amended coverage.

This is what SC-004 predicts: no behaviour moved except where the spec said it would.

---

## Resolved: no NEEDS CLARIFICATION remains

| Question | Resolution |
|----------|------------|
| Phone recognition mechanism | R-001 — one bounded alternative with a trailing digit guard |
| `+`-prefixed card exclusion (FR-003a) | R-002 — validator branch; pattern-level lookbehind proven wrong |
| Precedence with a fourth type | R-003 — append last; position still decides |
| Option parsing (FR-009) | R-004 — `parse_intermixed_args`, verified in four orderings |
| Pre-flight ordering (FR-015, FR-019, FR-020) | R-005 — usage, then collisions, then `makedirs` |
| Output byte fidelity (FR-013) | R-006 — identical open settings to stdout |
| Partial-output guarantee (FR-017a) | R-007 — create late, remove on failure; no temp-file dance |
| Which path a mid-stream failure names | R-008 — nested handlers, `(path, error)` return |
| Existing-suite blast radius (SC-004) | R-009 — count-shape assertions only |
