# Phase 0 Research: Phone Redaction and Output Folder

**Feature**: `002-phone-redaction-out-dir` | **Date**: 2026-11-20 | **Plan**: [plan.md](./plan.md)

Every item below was resolved against the shipped code (`src/logredact/redact.py`,
`src/logredact/cli.py`) and, where behaviour was in question, by running CPython 3.13 rather
than by reasoning about the documentation. The "Verified by" lines name what was actually
executed. No `NEEDS CLARIFICATION` marker remains in [plan.md](./plan.md).

The four questions the spec's own Clarifications session already settled — filesystem identity
for FR-049a, up-front checking for FR-054, ASCII-only digits for FR-033a, and the speed budget
for SC-019 — are treated as inputs here, not as open research.

---

## R-101: How is "`+` followed by 8–15 digits, not followed by a further digit" expressed?

**Decision**: one new alternative in the existing compiled alternation:

```python
_PHONE = r"\+[0-9]{8,15}(?![0-9])"
```

placed **last**, after `email`, `ip`, and `card`.

**Rationale**: the trailing negative lookahead does all the work of FR-034, including the part
that is easy to get wrong. A naive reading expects `+1234567890123456` (16 digits) to match the
first 15 digits and leave a stray `6`; it does not. The engine tries 15 digits, the lookahead
fails, and it backtracks through 14, 13, … 8 digits — at every one of those lengths the next
character is still a digit, so the lookahead fails again and the whole alternative fails at that
position. There is no length at which a 16-digit run can satisfy the pattern, which is exactly
FR-034's "a `+` followed by 16 or more digits produces no `[PHONE]`". The card rule then gets its
turn one character to the right, unchanged.

`[0-9]` is written out rather than `\d` deliberately: `\d` matches Arabic-Indic, Devanagari, and
full-width digits in Python's default Unicode mode, which would break FR-033a in both directions
— `+٠١٢٣٤٥٦٧٨` would be redacted, and the `٩` in `+12345678٩` would trip the exclusion
lookahead. This also matches the three existing rules, every one of which already spells out
`[0-9]`.

**Verified by**: compiling the four-way alternation and searching 17 probe strings drawn from the
spec's acceptance scenarios and edge cases. Results (category, span):

| Input | Match | Note |
|---|---|---|
| `+14155552671` | `phone` (0, 12) | US1.1 |
| `+442071838750` | `phone` (0, 13) | US1.2 |
| `+12345678` / `+123456789012345` | `phone`, whole token | US1.3, the 8- and 15-digit bounds |
| `+1234567` | none | US1.4, too short |
| `+1234567890123456` | `card` (1, 17) | US1.5 + FR-034: no `[PHONE]`, 16 digits fall to the card rule |
| `+4111111111111111` | `card` (1, 17) | today's `+[CARD]` output is preserved |
| `+14155552671@example.com` | `email` (0, 24) | FR-036: email wins at the same start position |
| `total=5+12345678` | `phone` (7, 16) | no left-hand guard |
| `+٠١٢٣٤٥٦٧٨` | none | FR-033a |
| `+12345678٩` | `phone` (0, 9) | FR-033a: `٩` neither extends nor excludes |
| `++14155552671` | `phone` (1, 13) | the second `+` starts the candidate |
| `+abc12345678`, `+1 415 555 2671`, `[PHONE]` | none | FR-033, FR-037 |
| `4111 1111 1111 1111` | `card` (0, 19) | unchanged |

**Alternatives considered**:

- *A separate scan pass for phones.* Rejected: two passes cannot express FR-035's single-claim
  rule without a reconciliation step that decides overlaps by hand — precisely the logic the one
  alternation already gets right for free.
- *`\+[0-9]{8,15}\b`.* Rejected: `\b` is a word boundary, so it is satisfied by a following
  letter or underscore but **not** by a following digit — close, but it also accepts
  `+12345678abc` differently from the spec's intent and it makes `+12345678٩` a non-match,
  because `٩` is a word character. The explicit `(?![0-9])` says what FR-034 says.
- *Checking length after a greedy `\+[0-9]+` match.* Rejected: post-validation is the shape the
  card rule is forced into by Luhn, and it is the most complicated part of the existing module.
  Phone needs no checksum, so it needs no post-validation.

---

## R-102: Does placing `phone` last in the alternation give the precedence FR-036 requires?

**Decision**: yes, and the order of the four alternatives *is* the precedence rule. The written
order must be `email | ip | card | phone`.

**Rationale**: `re.search` scans start positions left to right and, at each position, tries the
alternatives in written order. That gives earliest-start-wins with written order as the
tiebreak, which is FR-021 as amended by FR-036 verbatim. The existing module already documents
this; appending one alternative extends the existing mechanism rather than adding a new one.

Two consequences are worth stating because they are the spec's two deliberate outcomes:

- `+14155552671@example.com` → one `[EMAIL]`. The email alternative matches at offset 0 because
  the existing `_LOCAL` class already contains `+`, and email is written first.
- `+4111111111119` (13 Luhn-valid digits) → `[PHONE]`, where today it is `+[CARD]`. The phone
  candidate starts at the `+`, one character earlier than the card candidate, so
  earliest-start-wins settles it without any new rule. This is the single input shape whose
  redaction output changes (spec Assumptions, SC-012).

**Verified by**: the probe table in R-101 (`email` wins at offset 0; `phone` wins at offset 0 for
13–15 digit runs) plus `_luhn_valid("4111111111119") is True`.

**Alternatives considered**: placing `phone` before `card` was rejected — it changes nothing,
since the two can never start at the same position (a card candidate starts on a digit, a phone
candidate on `+`), so the spec's stated order is kept because it is the spec's stated order.

---

## R-103: Does the rejected-card resume loop interact badly with the new alternative?

**Decision**: no change to `redact_line`'s two-cursor loop is needed.

**Rationale**: the loop advances `search_from` by one character when a card candidate fails Luhn
(FR-019a) and otherwise to the end of an accepted match. A phone candidate can only begin at a
`+`, and a card candidate contains no `+` — the two categories can never start at the same
offset, and the one-character resume never jumps *forward* over anything, so a `+` that follows a
rejected card candidate is still reached. `search_from` still strictly increases, so termination
is unaffected.

**Verified by**: `1234567890123+12345678` → `1234567890123[PHONE]` (the 13-digit run is
Luhn-invalid, is copied through verbatim, and the phone further right is still found).

---

## R-104: Does `--out-dir` survive `parse_intermixed_args`?

**Decision**: `parser.add_argument("--out-dir", dest="out_dir", metavar="DIR")` with the existing
`parse_intermixed_args` call. No custom parsing, no `exit_on_error` override.

**Rationale**: FR-040 requires `--out-dir` to be accepted anywhere on the command line and never
to be mistaken for a FILE, and requires a missing directory argument to be the usage error of
FR-030. An option that takes exactly one value gives argparse everything it needs for both:
argparse consumes the value itself, and a trailing `--out-dir` with nothing after it produces the
stock usage-to-stderr, exit-2 behaviour. This mattered enough to test because `--out-dir` is the
first value-taking option in the tool, and `parse_intermixed_args` is documented as having
restrictions around positionals.

**Verified by**: parsing six argument vectors:

| `argv` | Result |
|---|---|
| `--out-dir clean a.log b.log` | `out_dir='clean'`, `files=['a.log','b.log']` |
| `a.log --out-dir clean b.log` | `out_dir='clean'`, `files=['a.log','b.log']` |
| `a.log b.log --count --out-dir clean` | `out_dir='clean'`, `count=True`, `files=['a.log','b.log']` |
| `--out-dir=clean a.log` | `out_dir='clean'`, `files=['a.log']` |
| `--count` | `out_dir=None`, `files=[]` |
| *(empty)* | `out_dir=None`, `files=[]` |

No vector mis-assigned the directory to `files`, which is US2.8.

**Alternatives considered**: `nargs=1` (rejected — yields a one-element list for no benefit) and
`required=False, default=None` written out (rejected — that is already the default).

---

## R-105: How is `DIR` created and confirmed usable, and what does failure look like?

**Decision**: `os.makedirs(out_dir, exist_ok=True)` inside a `try`, converting `OSError` into a
diagnostic naming the directory and exit 2. No separate `isdir` check is needed.

**Rationale**: `exist_ok=True` suppresses the error only when the path already exists **as a
directory**; when it exists as a regular file, `makedirs` raises `FileExistsError`, which is
FR-048 and US4.5 in one call. Missing parents are created by the same call, which is FR-042 and
US2.4. A path whose own parent is a regular file raises `NotADirectoryError`. So one call covers
"create it", "accept an existing directory", and "reject anything else", and the follow-up
`os.path.isdir` that would seem prudent is unreachable.

**Verified by**: in a temporary directory containing a regular file `notadir`:

- `os.makedirs("…/notadir", exist_ok=True)` → `FileExistsError: [Errno 17] File exists:
  '…/notadir'`
- `os.makedirs("…/notadir/x", exist_ok=True)` → `NotADirectoryError: [Errno 20] Not a directory:
  '…/notadir/x'`

Both messages already carry the offending path, so the diagnostic can quote the path as the user
spelled it and append the OS message, matching the existing read diagnostic's shape.

**Alternatives considered**: `Path(dir).mkdir(parents=True, exist_ok=True)` behaves identically;
`os` is already imported by `cli.py` and `pathlib` is not, so no new import is taken on.

---

## R-106: How is "the output file would be the input file" decided (FR-049a)?

**Decision**: compare `(st_dev, st_ino)` from `os.stat` on both paths, via a helper that returns
`None` when a path cannot be stat'ed:

```python
def _file_identity(path: str) -> tuple[int, int] | None:
    try:
        info = os.stat(path)          # follows symlinks
    except OSError:
        return None                   # nothing there to collide with
    return info.st_dev, info.st_ino
```

A collision is `identity(out_path) is not None and identity(out_path) == identity(file)`.

**Rationale**: the Clarifications session fixed the criterion as filesystem identity, and
`(st_dev, st_ino)` is exactly what `os.path.samefile` compares. Because `os.stat` follows
symlinks it catches US4.7b (an output path that is a symlink to the input) and, because a hard
link shares an inode, it catches hard links too. Because it resolves the path rather than
comparing text, it catches US4.7a (`logs/app.log` with `--out-dir ./logs`). An output path that
does not exist yields `None` and is therefore not a collision, which FR-049a requires explicitly.

`os.path.samefile` would be the obvious call, but it raises when *either* path is missing, and
"the output file does not exist yet" is the overwhelmingly common case — so the exception
handling would be load-bearing rather than exceptional. The helper makes the "no identity known"
answer a value instead of an exception.

**The `except OSError: return None` is not an error being swallowed**, which Principle II
forbids. `_file_identity` is a query — "which file, if any, does this path name?" — and `None` is
a truthful answer to it, not a sentinel standing in for a failed operation. Critically, a missing
*input* file is still reported: it is not reported *here*, it is reported by the existing
read-failure path when the operand is streamed, with the FR-028 diagnostic naming the path. This
is what US4.1 requires — a nonexistent FILE under `--out-dir` fails with a read diagnostic and an
empty `DIR`, not with a collision diagnostic.

**Verified by**: `os.stat` semantics are relied on, not probed, for symlink following and inode
sharing; the probe confirmed only that a missing path raises `OSError` (`FileNotFoundError`) from
`os.stat` rather than returning a sentinel.

**Alternatives considered**:

- *Comparing `os.path.realpath` strings.* Rejected: it resolves symlinks but not hard links, and
  the Clarifications answer named filesystem identity rather than canonical paths.
- *`os.path.samefile` wrapped in `try`.* Rejected for the reason above; it is the same two
  `stat` calls with a less useful failure mode.

---

## R-107: When is the collision check run, and is one sweep enough?

**Decision**: two checks, and both are FR-049 compliance rather than belt-and-braces:

1. **Up-front sweep** (FR-054 step 3): after `DIR` is created and before any input source is
   opened, every operand's computed output path is checked. Any collision fails the run then and
   there, so no output file has been opened, created, or truncated — US4.7c.
2. **Re-check immediately before each output file is opened**: the same `_file_identity`
   comparison for the operand about to be streamed, after its input has been opened and before
   the output is opened for writing.

**Rationale**: the sweep alone leaves one real hole. Run
`python -m logredact --out-dir clean a.log clean/a.log`. At sweep time `clean/a.log` does not
exist, so FR-049a says — correctly and explicitly — that it cannot collide and must not be
rejected. Operand 1 then creates it. Operand 2 now reads `clean/a.log` and computes the output
path `clean/a.log`, which is the very file it is reading: opening it `"w"` truncates the input
mid-read and produces an empty "redacted" file with exit status 0 and a `wrote 2 files` line.
That is a silent wrong answer about the user's data, which Principle II treats as the most
expensive failure available.

The re-check closes it without contradicting anything. FR-049 states the obligation ("if the
output file computed for a FILE would be that same FILE … exit 2") without constraining *when*
it is discovered; FR-049a constrains only the *criterion*; FR-054 mandates that the sweep happen
before any output is written, not that it be the only check. At re-check time the path does exist
and does name the same file, so FR-049a's "does not yet exist cannot collide" exemption does not
apply to it.

The re-check cannot fire on any scenario the spec requires to succeed. It compares the operand
being read against its own output path only: for `a/app.log b/app.log --out-dir clean` (US2.10),
operand 2's output `clean/app.log` exists by then but names a different file from `b/app.log`, so
the duplicate-base-name case still succeeds and still reports `wrote 2 files`.

**Open question for the spec owner**: this is the one place where the implementation does
something the acceptance scenarios do not describe. It is reported in the plan's Complexity
Tracking, and if the owner would rather the hole stayed open, deleting the re-check is a
three-line change.

---

## R-108: How are output-file write failures kept distinct from read failures?

**Decision**: generalise the existing `OutputWriteError` to carry a per-destination message and
an `is_stdout` flag, and raise it from every output-side operation — opening, writing, flushing,
and closing an output file, as well as the existing stdout write and flush.

```python
class OutputWriteError(Exception):
    def __init__(self, message: str, *, is_stdout: bool) -> None: ...
```

**Rationale**: the existing design note in `cli.py` already explains why this class must not
inherit from `OSError`: a write failure raised while a source file is being iterated would
otherwise be caught by the per-source loop's `except OSError` and misreported as "cannot read
FILE". Writing to an output file inside that same loop makes the hazard worse rather than new —
now *both* directions of I/O happen under one `except OSError`. Keeping the output side on a
non-`OSError` channel is what lets FR-048 ("naming the output file") and FR-050 ("naming the
unreadable FILE") produce different, correct diagnostics from the same loop.

One class with two message shapes rather than two classes: the handler is a single
`except OutputWriteError`, and the only thing it branches on is whether to redirect file
descriptor 1 (needed only for a stdout failure, per the existing `_silence_stdout` note). The
stdout message text is unchanged — `failed writing to standard output` — so FR-052 holds and the
existing tests that assert it keep passing.

**Alternatives considered**: inspecting `errno` or the exception type inside the read handler to
guess which side failed. Rejected for the reason already recorded in the feature-001 plan: it
enumerates failure modes and gets attribution wrong for any mode not enumerated.

---

## R-109: Which stream is opened first for an operand, input or output?

**Decision**: **input first, then output.** Open the source file; only if that succeeds, open the
output file.

**Rationale**: this is forced by US4.1. A single nonexistent FILE under `--out-dir clean` must
leave `clean` "in place and empty — … no output file was written". Opening the output file first
would create `clean/missing.log` before the read was attempted, leaving a zero-byte output file
for an operand that was never processed and contradicting the scenario.

It also follows that the existing lazy generator `_iter_source_lines` can no longer carry the
open, because its laziness means the file is opened on first `next()` — i.e. *after* the output
file would have been opened. For the `--out-dir` path the source is opened eagerly so the read
failure is observable before the output file exists. The stdout path keeps the generator exactly
as it is (FR-052).

**Consequence worth noting**: a FILE that is a directory (`logs/`) is caught here as a read
failure, `IsADirectoryError`, with the FR-028 diagnostic — not as an output-file failure. This is
also why a trailing-slash operand needs no special handling: `os.path.basename("logs/")` is `""`,
but the run never reaches the output path because the input open fails first.

---

## R-110: What text configuration do output files use?

**Decision**: the same three settings the existing streams use —
`open(path, "w", encoding="utf-8", errors="surrogateescape", newline="\n")`.

**Rationale**: FR-044 requires each output file to hold exactly the bytes stdout would have
carried, so it must use exactly the stdout configuration. `errors="surrogateescape"` turns the
lone surrogates produced by the reader back into the original bytes (FR-005a); `newline="\n"` on
a write-only stream means a written `\n` is emitted as `\n` with no translation, so `\r\n`
survives (FR-007) and a missing final newline stays missing (FR-007a). For a write-only stream
`newline=""` is equivalent; `newline="\n"` is chosen so that one spelling of the text
configuration appears everywhere in the codebase and cannot drift.

Mode `"w"` — not `"a"` — is FR-043: it truncates an existing file so the previous content is
replaced in full rather than appended to.

No `line_buffering` argument: output files are block-buffered, which is what SC-019's throughput
budget wants. The existing `_text_stream` helper is not reused because it wraps an already-open
binary stream and selects buffering from `isatty()`; a plain `open` is both shorter and the
correct tool for a path.

---

## R-111: How is `wrote N files` counted, and in what order is it written?

**Decision**: `N = len(args.files)`, written to stdout through the existing `_write`/`_flush`
helpers after the last operand has been streamed and before the tally.

**Rationale**: FR-045 defines N as "the number of output files written, counting one per FILE
processed", and the line is only ever printed on a fully successful run — every operand processed,
no read failure, no output failure. On such a run the count of operands processed is exactly the
operand count, so no separate counter is needed. The spec's Assumptions confirm the duplicate
base-name reading: two operands sharing a base name write one file but report `2`.

Routing the line through the existing `_write`/`_flush` gives the spec's stdout-failure
behaviour for free — a failed write of the summary raises `OutputWriteError(is_stdout=True)`,
producing the existing diagnostic and exit 2 with no tally (spec edge case "Standard output
still matters"). It also puts the summary before the tally with the existing flush between them,
which is FR-046 and FR-024 unchanged.

The wording is a literal f-string with no pluralisation branch: `wrote 1 files` for one file
(FR-045, US2.7).

---

## R-112: How is a close failure on an output file reported without masking a read failure?

**Decision**: the output file is closed explicitly so that a close failure becomes an
`OutputWriteError` naming the path (FR-048 lists "closed"). If the streaming body already raised,
the close is still attempted but its own failure is suppressed with
`contextlib.suppress(OSError)`, leaving the original exception to propagate.

**Rationale**: `TextIOWrapper.close()` flushes, so it is a genuine write site and FR-048 names it.
But a read failure mid-stream leaves buffered output that the cleanup close will try to flush; if
that flush also fails, an unguarded cleanup close would replace the FR-050 diagnostic ("cannot
read FILE") with an FR-048 one ("cannot write output file"). FR-050 requires the unreadable FILE
to be the thing named, so the first failure must win.

This is a narrowly scoped, deliberate exception to Principle II's ban on suppressing exceptions,
and it is recorded in the plan's Complexity Tracking. Its scope is one statement, on a cleanup
path that runs only when the run has already failed and is already about to exit 2, and the
information suppressed is strictly less specific than the information reported.

**Alternatives considered**: a bare `with open(...)` block. Rejected: the implicit close raises a
plain `OSError` from the `with` statement's exit, which the enclosing read handler would catch
and misreport as a read failure — the exact confusion R-108 exists to prevent.

---

## R-113: Can the new tests exercise an unwritable directory in this environment?

**Decision**: express every FR-048 failure through filesystem *shape* rather than permissions,
and keep the permission-based test as an additional case guarded by
`pytest.mark.skipif(os.geteuid() == 0, …)`.

**Rationale**: the suite is expected to pass as run, and in a container running as root the mode
bits set by `chmod` are bypassed, so a `chmod 500` test would fail by *succeeding*. Shape-based
fixtures reproduce the same requirement for any user:

| Requirement | Fixture that works as any user |
|---|---|
| `DIR` exists but is not a directory (US4.5) | create a regular file at the `--out-dir` path → `FileExistsError` |
| `DIR` cannot be created (FR-048) | `--out-dir` pointing below a regular file → `NotADirectoryError` |
| output file cannot be created or written (FR-048) | create a *directory* named `clean/app.log` → `IsADirectoryError` on `open(..., "w")` |

The `chmod` case (US4.6) is kept as well, skipped under root, so that the requirement is covered
on a normal developer machine too.

**Verified by**: both `makedirs` probes in R-105; `os.geteuid()` is 0 in the current environment,
which is what prompted the question.

---

## R-114: How is "nothing else changed" (FR-052, FR-053, SC-012, SC-013) demonstrated?

**Decision**: the feature-001 test suite is the replay. It is run unchanged except for the
assertions on the tally line, and the complete list of edits made to it becomes the evidence for
SC-012.

**Rationale**: SC-012 asks for the list of differing input shapes to be "demonstrated rather than
asserted, by replaying the feature-001 acceptance scenarios and recording every difference
observed". Those scenarios already exist as executable tests, so the honest replay is to run them
and see which fail. The expected set of required edits is exactly the sites that spell out the
three-field tally line, and nothing else:

| File | Sites | Kind |
|---|---|---|
| `tests/test_cli.py` | 70, 128, 208, 233, 244, 265, 281, 289 | eight byte-exact assertions |
| `tests/test_cli.py` | 228 | one docstring quoting the FR-023 form |
| `tests/test_fidelity.py` | 109, 155 | two assertions |
| `tests/test_fidelity.py` | 169 | the `TALLY_LINE` regex |
| `tests/test_performance.py` | 106 | one assertion |

Each gains the `phones=N` field and nothing else. Any *other* feature-001 test that fails is a
regression, not a documented difference.

None of the feature-001 redaction fixtures contains a `+` outside an email local part, so no
assertion about redacted *output* is expected to change — which is SC-013 for that corpus. A
dedicated byte-identity test over a no-`+` corpus makes SC-013 measurable rather than incidental.

**Verified by**: `grep` over `tests/` for the tally form, which found the fourteen sites listed
above and no others.

---

## R-115: Does streaming to files keep the memory and speed budgets (SC-018, SC-019)?

**Decision**: no new mechanism. One line is resident at a time, one output file is open at a time,
and the only state that persists across operands is the four-key `Counter` and the operand list.

**Rationale**: SC-018 requires memory bounded by the longest line rather than by total input or
by operand count. Opening each output file as its operand is reached and closing it before the
next is opened keeps the number of open handles at one regardless of operand count; the spec's
Assumptions ("Output files are written as the input is read") rule out any buffer-then-write or
temp-file-and-rename scheme, which is also what makes FR-050's "earlier output files remain on
disk" true. SC-019's budget is the same 100,000 lines in under 30 s as SC-007, now measured across
all operands of one run, and the per-line work is unchanged — one regex scan, one write — so the
only new per-operand cost is an `open`/`close` pair and two `stat` calls, which do not accumulate
per line.

**Alternatives considered**: opening all output files up front so that an output failure is
discovered before any input is read. Rejected on two counts: it breaks SC-018 for large operand
counts, and it truncates every output file before the first is written, which contradicts
FR-054's guarantee that a run failing at step 2 or 3 has truncated nothing.
