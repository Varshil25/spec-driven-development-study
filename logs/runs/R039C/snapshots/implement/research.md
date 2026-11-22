# Phase 0 Research: Phone Redaction and Output Folder

**Feature**: 002-phone-redaction-out-dir | **Date**: 2026-11-21 | **Spec**: [spec.md](./spec.md)

The specification fixes *what*; this document resolves *how*. Decisions continue feature 001's
series (`D-001` – `D-010`) in a new `D-1nn` block so the two can be cited unambiguously. Every
decision below was **executed as a probe against the spec's acceptance scenarios before being
written down**; measured results are quoted inline.

**Unknowns on entry**: none of the `NEEDS CLARIFICATION` kind. The spec fixes the interface, the
recognition rule, the precedence rank, and every failure status; the user's planning input fixes
language (Python 3.11+), dependency policy (standard library only), and test runner (`pytest`).
What remained were twelve open *how* questions, resolved below.

**Probe environment**: CPython 3.13.17 on Linux, `umask 0022`. No feature newer than 3.11 is used.

---

## D-101 — Phone recognition pattern

**Decision**: one compiled pattern, with the placeholder beside the existing three in `redact.py`:

```python
PHONE_PLACEHOLDER = "[PHONE]"
_PHONE = r"\+[0-9]{8,15}(?![0-9])"
```

- `\+` is a literal plus and the **only** anchor. There is no leading condition, so the character
  before the `+` is never examined (spec Assumptions, FR-001).
- `[0-9]` is written out explicitly. The `\d` shorthand also matches non-ASCII decimal digits on a
  `str` pattern, which FR-002 forbids and which 001 D-004 already rejected for the Luhn check.
- `{8,15}` is a **bounded** quantifier with no nested repetition, which is SR-004 stated as code.
- `(?![0-9])` is FR-001's "the final digit of the match is not immediately followed by another
  ASCII digit", and is what makes a 16-digit run reject rather than yield a 15-digit partial.

**Verified**: all 22 phone-related acceptance scenarios and edge cases in the spec produce the
specified output, including `+1234567` → unchanged, `+1234567890123456` → unchanged,
`++14155552671` → `+[PHONE]`, `100+14155552671` → `100[PHONE]`, `+ 14155552671` → unchanged,
`+١٢٣٤٥٦٧٨` (Arabic-Indic digits) → unchanged, and both bounds (8 and 15 digits) → `[PHONE]`.

**Alternatives considered**

| Alternative | Rejected because |
|---|---|
| `\+\d{8,15}\b` | `\d` admits non-ASCII digits (FR-002); `\b` is the wrong test — it is satisfied between a digit and `_`, and `\B` would wrongly reject at line end. An explicit `(?![0-9])` says what FR-001 says. |
| `\+[0-9]{8,15}` with no lookahead | Yields `[PHONE]` plus the remaining digits for a 16+ digit run — a partial disclosure, forbidden by SR-002 and FR-002. |
| Lazy `{8,15}?` | Would match the *shortest* qualifying run, contradicting FR-001's longest rule and leaving trailing digits in the output. |
| Match `+` then count digits in Python | More code than the regex it replaces, with no gain; the bounded quantifier already guarantees the complexity property. |

## D-102 — Phone is a fourth stage over the gaps left by ranks 1–3

**Decision**: do **not** add a phone alternative to the existing `EMAIL_OR_IP` alternation. Add a
third matching stage to `redact_line` that runs `_PHONE.finditer` over the sub-slices of the line
left uncovered by the email, IPv4, **and card** matches already collected.

**Rationale**: FR-003 puts phone at rank 4, *after* card. Card is not expressible as a regex — the
Luhn checksum is computed in Python (001 D-003) — so an alternation can never encode
"card beats phone". The existing engine already restricts card detection to the gaps stage 1 left
over; phone simply repeats that move one rank lower. Reusing the mechanism rather than inventing
one is also what keeps FR-005 true: stages 1 and 2 are untouched, so every span the tool redacts
today is still claimed by the same rule, with the same placeholder, at the same position.

This makes `+4222222222222` — 13 digits that pass Luhn, and therefore `+[CARD]` today — stay
`+[CARD]`: the card claims the digits and the leftover gap is the single character `"+"`, in which
no phone can match. **Verified** by probe, together with `4111111111111111+14155552671` →
`[CARD][PHONE]` and the whole 001 corpus unchanged.

**Slice-boundary soundness** (the one subtlety): `(?![0-9])` is evaluated against the end of a
*slice*, not of the line, so a slice that ended mid-digit-run would make the lookahead lie. It
cannot happen. A slice ends where a rank 1–3 match begins, and no rank 1–3 match can begin with a
digit that is immediately preceded by a digit: email carries `(?<![A-Za-z0-9._%+-])`, IPv4 carries
`(?<![0-9.])`, and a card span can only begin at the start of a **maximal** digit run. A phone
match can likewise never be cut at its left edge, because it must begin at a `+`.

**Alternatives considered**

| Alternative | Rejected because |
|---|---|
| Add `(?P<phone>...)` to `EMAIL_OR_IP` | Puts phone at rank 3, above card, reclassifying `+4222222222222` from `[CARD]` to `+[PHONE]`. That breaks FR-003 and FR-005 outright. |
| Run phone first and let card re-claim | Requires un-substituting a placeholder, which FR-003 forbids ("placeholders MUST NOT be nested or doubly substituted"). |
| One generic rule table driving N stages | A registry abstraction with four fixed entries and one caller — speculative generality, forbidden by Principle IV. |

## D-103 — Rejecting 16-or-more-digit runs is bounded work

**Decision**: rely on greedy matching plus the lookahead; add no guard.

At a `+` followed by *k* ≥ 16 digits the engine tries 15 digits, fails the lookahead, backtracks to
14, and so on to 8 — **at most 8 attempts, each O(1)**, then `finditer` advances. The bound comes
from the quantifier's own range, not from the input, so matching stays linear in line length.

**Measured** (10 000-character adversarial lines, SC-010 budget 1 s, through the complete
four-rank `redact_line`, not the pattern alone):

| Line | Time | Margin |
|---|---|---|
| 10 000 `+` characters | 1.53 ms | 650× |
| 10 000 digits | 0.67 ms | 1500× |
| `+1` repeated 5 000× | 6.78 ms | 147× |
| `+` + 15 digits, repeated | 3.39 ms | 295× |
| `+` + 16 digits, repeated (worst backtracking case) | 3.10 ms | 322× |
| `@.` repeated (001's worst case) | 1.46 ms | 685× |

## D-104 — Counts carry a fourth key

**Decision**: `redact_line` returns `counts` keyed `"emails"`, `"ips"`, `"cards"`, `"phones"`;
`cli.main` seeds the same four keys and `_consume` accumulates the fourth alongside the others. The
summary becomes one format string:

```python
"emails={emails} ips={ips} cards={cards} phones={phones}\n".format(**counts)
```

A plain `dict` of four `int`s remains the right shape (Principle IV); nothing about the fourth
category calls for a type. Field order is `emails ips cards phones`, appended not inserted, so a
script reading the first three fields positionally keeps working (spec Assumptions).

## D-105 — `_partition` must learn which options take a value

**Decision**: extend `_partition` with a one-entry table of value-taking options and a
`expect_value` flag, so the token after `--out-dir` is grouped with the options rather than with the
FILE paths.

**This is a correctness fix, not a refactor.** `_partition`'s current docstring states "No option in
this tool takes a value … so no token can be the value of a preceding option". `--out-dir` breaks
that premise: without the change, `--out-dir clean app.log` regroups to
`["--out-dir", "--", "clean", "app.log"]` and argparse would fail on a missing value while silently
treating `clean` as an input path — a wrong answer, which Principle II calls the most severe defect
class here.

Handled forms, all **verified** by probe:

| Argument list | Regrouped as |
|---|---|
| `--out-dir clean app.log web.log` | `--out-dir clean -- app.log web.log` |
| `app.log --out-dir clean web.log` | `--out-dir clean -- app.log web.log` (FR-006, any position) |
| `--out-dir=clean app.log` | `--out-dir=clean -- app.log` (FR-006, `=` form) |
| `app.log --out-dir` | `--out-dir -- app.log` → argparse usage error, exit 2 |
| `--out-dir --count a.log` | `--out-dir --count -- a.log` (the value is taken literally) |
| `--count --out-dir clean -` | `--count --out-dir clean -- -` (a FILE of `-` stays a literal path) |

A token is treated as value-taking when it contains no `=` and is a prefix of `--out-dir` at least
three characters long. That keeps argparse's option abbreviation working for **both** options, which
FR-005 requires: `--c` resolves to `--count` today, and the two option names share no prefix beyond
`--`, so `--c…` and `--o…` stay unambiguous. Setting `allow_abbrev=False` instead would have been
simpler to write but would have changed existing behaviour (`--cou` goes from exit 0 to exit 2),
which FR-005 forbids.

## D-106 — `--out-dir` absent, empty, and repeated

**Decision**: `parser.add_argument("--out-dir", metavar="DIR", default=None)` (dest `out_dir`).

- **Absent** is `None`, **empty** is `""` — distinguishable, which matters because the two take
  different paths: absent means "stream to stdout exactly as today" (FR-017), empty means "reject"
  (SC-008). A `default=""` would have conflated them.
- **Repeated**: argparse's store action keeps the last occurrence, which is FR-006 with no code
  (verified: `--out-dir x --out-dir y` → `out_dir="y"`).
- **Missing value**: argparse emits `error: argument --out-dir: expected one argument` with usage,
  and exits 2 (verified) — FR-006 and US4-4 with no code.

## D-107 — Argument-level failures go through `parser.error`, filesystem failures do not

**Decision**: the two argument-level rejections — `--out-dir` with no FILE (FR-012) and an empty DIR
value (SR-012) — are raised with `parser.error(...)`, inside the same block that already swaps
`sys.stderr` for the injected stream around `parse_args`. `parser.error` writes usage plus the
message to stderr and raises `SystemExit(2)`, which `main`'s existing `_exit_code` already
translates.

This gives US4-3 and US4-4 the "usage diagnostic" the spec asks for, places validation **at the
boundary before the value reaches any write logic** (SR-012, Security Baseline "Untrusted input"),
and guarantees FR-012's "standard input not read, no directory or file created" structurally —
the check runs before any source is opened and before DIR is touched.

Filesystem failures (cannot create DIR, cannot open or write an output file) are *not* usage errors
and print no usage text; they use the same one-line `python -m logredact: …` shape as 001's
diagnostics.

## D-108 — Creating DIR: an explicit loop, because `makedirs(mode=…)` does not do what SC-007 needs

**Decision**: walk up from DIR collecting the components that do not exist, then create them
top-down with `os.mkdir(target, 0o700)` followed by `os.chmod(target, 0o700)`. Directories that
already exist are left exactly as they are.

**Rationale**: `os.makedirs(path, mode=0o700)` applies the mode to the **leaf only**. Measured on
`mk/a/b/c` with `umask 0022`:

```text
mk       0755      <- intermediate, mode ignored
mk/a     0755      <- intermediate, mode ignored
mk/a/b   0755      <- intermediate, mode ignored
mk/a/b/c 0700      <- leaf
```

SC-007 requires owner-only permissions on **every** directory the tool creates, and US2-3 requires
`reports/2026/clean` to be created three levels deep, so `makedirs` cannot be used as-is. The
explicit `chmod` after `mkdir` also removes the `umask` from the picture: `mkdir`'s mode argument is
masked by it, so a permissive `umask` would otherwise widen what the tool creates.

Only components the tool creates are chmod'ed. An existing DIR keeps its own mode — the tool was not
asked to re-permission the user's directories, and narrowing one would be a side effect SR-008 does
not sanction (verified: an existing `0755` directory stays `0755`, and re-running is a no-op).

Failure cases, **verified**: DIR exists as a regular file → `FileExistsError` naming the path;
a path component is a regular file → `NotADirectoryError`; DIR is a symlink to a directory → used
as-is, nothing created (the spec treats the DIR value itself as the user's own, Assumptions).

**Alternatives considered**: `os.makedirs(..., exist_ok=True)` then a second pass to chmod the tree —
needs the same "which did I create?" bookkeeping, plus a tree walk; `umask` manipulation around
`makedirs` — process-global, not thread-safe, and leaves the intermediate modes still wrong.

## D-109 — Opening an output file: the ordered sequence that cannot truncate the wrong file

**Decision**: open through `os.open` with explicit flags, run every check **on the file descriptor**,
and truncate **last**:

```python
_OUT_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
fd = os.open(path, _OUT_FLAGS, 0o600)      # no O_TRUNC
st = os.fstat(fd)                          # SR-006: must be a regular file
if not stat.S_ISREG(st.st_mode): fail
if os.path.samestat(st, os.fstat(in_fd)): fail   # SR-008: never the input file
os.fchmod(fd, 0o600)                       # SC-007, also for a pre-existing file
os.ftruncate(fd, 0)                        # FR-009: full replacement, last of all
stream = open(fd, "w", encoding="utf-8", errors="surrogateescape", newline="")
```

Each element earns its place:

| Element | Requirement it discharges | Measured behaviour |
|---|---|---|
| `O_NOFOLLOW` | SR-006, SR-005 — a planted symlink must not become a write outside DIR | symlink at the output path → `OSError` ELOOP; the link target was **not** created |
| `O_NONBLOCK` | Principle II — a FIFO at the output path must fail, not hang | FIFO → `OSError` ENXIO immediately; no effect on a regular file |
| `fstat` + `S_ISREG` | SR-006 — directory, device, socket, FIFO | directory → `IsADirectoryError` EISDIR; checked on the fd, so there is no time-of-check gap |
| `samestat` vs the input fd | SR-008 — `--out-dir .` must not truncate the file being read | detected as the same file **with the input still intact**, because no `O_TRUNC` was requested |
| `fchmod(0o600)` | SC-007 — "every output file has owner-only permissions after the run" | a pre-existing `0666` file ends the run at `0600`; narrowing only, never widening |
| `ftruncate` last | FR-009 — no remnant of longer previous content | a 50-byte file overwritten with 2 bytes contains exactly those 2 bytes |

**Why not `open(path, "w")`**: it implies `O_TRUNC`, so it destroys the file *before* any check can
run — exactly the input-truncation the spec forbids — and it follows symlinks, cannot set the
creation mode, and would hang on a FIFO.

**Why no temp-file-and-rename**: the spec does not require atomic replacement, and the Assumptions
record the opposite — a failed write may leave a partial file, signalled by exit 2 and the absent
`wrote N files` line. SR-007 also forbids a temporary file at a predictable path, so the simplest
design that satisfies the spec is the direct write (Principle IV).

## D-110 — Diagnostics for a non-regular output path

**Decision**: `os.lstat` the output path first *for the message*, and keep `O_NOFOLLOW` as the
authoritative guard. ELOOP from the open is reported with the same wording as the pre-check.

**Rationale**: the kernel's `strerror` for `O_NOFOLLOW` is "Too many levels of symbolic links",
which misdescribes a single symlink and fails Principle II's "says what was rejected and why, in
terms the caller can act on". The pre-check produces `cannot write DIR/app.log: not a regular file`.
The pre-check is advisory only — it is the open flag and the `fstat` on the descriptor that enforce
the rule, so the window between the two cannot be exploited into a write.

## D-111 — Output path containment

**Decision**, in this order, before any output file is opened:

1. `name = os.path.basename(file)` — the spec's "final path component of FILE only" (SR-005). This
   alone discards directory components, `..` segments, and an absolute root. **Verified**:
   `logs/2026/app.log`, `../../etc/passwd`, and `/etc/passwd` map to `DIR/app.log`, `DIR/passwd`,
   and `DIR/passwd`.
2. Reject `name` in `("", ".", "..")` with a diagnostic and exit 2 (SR-005). **Verified**: `a/`, `.`,
   `..`, `sub/..`, and `""` all land in this set.
3. `path = os.path.join(dir_value, name)`, then require
   `Path(path).resolve().parent == Path(dir_value).resolve()` — the spec's "resolved and verified to
   be a direct child of the resolved DIR". **Verified**: this independently rejects a symlink
   planted at `DIR/app.log` (its resolved parent is the link's target directory, not DIR), so the
   containment rule and `O_NOFOLLOW` catch the same attack by two different mechanisms.

DIR itself is used as given, not resolved for the write (spec Assumptions); resolution is applied to
the *path within* DIR, which is where a FILE value could otherwise escape.

## D-112 — Destination, ordering, and the tally

**Decision**: `_consume(name, stream, out, err, counts)` is unchanged — it already writes to
whichever `out` it is handed. `main` grows one branch: with `--out-dir`, the per-FILE output stream
is opened just after that FILE's input stream and closed before the next FILE is reached; without
it, `out` stays stdout. No destination class, no writer abstraction (Principle IV).

Consequences, each a stated requirement:

- **At most one output file open at a time** (SR-011), closed in a `finally` that is inside the
  existing per-source `finally` for the input stream.
- **DIR is created once**, after argument validation and before the first FILE is opened (FR-008),
  so FR-012's "no directory created" holds and US4-1's "earlier output files survive a later
  unreadable FILE" holds.
- **`wrote N files`** is written to stdout only after the last output file has been closed
  successfully, with `N = len(files)` (FR-011 counts FILE arguments, so a repeated FILE and two
  FILEs sharing a final component each count). Singular for `N == 1`:
  `f"wrote {n} file{'' if n == 1 else 's'}\n"`.
- **Ordering**: every output file closed → `wrote N files` to stdout → stdout flushed → `--count`
  summary to stderr (FR-016). Every failure path returns before the tally, so neither line appears
  on a failing run (FR-014, FR-015, US4-8).
- **Flush and close are part of success**: the per-file `close()` is wrapped and a failure in it is
  reported and returns 2 (SR-009), because a buffered tail lost at close would otherwise be a
  silently truncated redaction.
- Output files use the identical encoding triple as stdout — `utf-8` / `surrogateescape` /
  `newline=""` — which is FR-013 with no new policy to state (001 D-001).

## D-113 — Target platform for `--out-dir`: POSIX

**Decision**: implement the output path with POSIX primitives (`os.O_NOFOLLOW`, `os.O_NONBLOCK`,
`os.fchmod`) and state the supported platform as POSIX — Linux and macOS — rather than adding
capability fallbacks.

**Rationale**: `O_NOFOLLOW` and `fchmod` are Unix-only in the standard library. A `getattr(os,
"O_NOFOLLOW", 0)` fallback would silently *weaken* a security control on the platform where it is
absent, which SR-006 forbids and which is worse than not running; and a second, non-atomic code path
for a platform the spec never mentions is speculative generality (Principle IV). FR-018 constrains
the interpreter (3.11+) and the dependency policy (stdlib), not the operating system.

**Consequence, recorded honestly**: on Windows, `--out-dir` would fail at import-time attribute
access rather than run with a weaker guarantee. Everything feature 001 does — the default
stdout-streaming mode, all four redaction categories, `--count` — remains platform-independent.
Revisiting this is an amendment-sized decision, not a quiet fallback.

## D-114 — Test strategy for the new surface

**Decision**: keep 001's two styles (`run_cli` subprocess for the real entry point and byte-level
assertions, `call_main` with injected streams for paths the environment cannot produce) and add
three fixtures' worth of filesystem helpers to `tests/conftest.py`:

- a sample phone constant alongside `SAMPLE_EMAIL` / `SAMPLE_IP` / `SAMPLE_CARD`, so the existing
  SC-012 gate — "no prepared sample value appears in any captured output" — extends to phones and,
  newly, to **every file under every output folder a test creates** (SR-010);
- an `out_dir` tmp-path fixture plus a permission reader, for SC-007's mode assertions;
- the unwritable-destination case produced with `os.chmod(parent, 0o500)` where the test is not
  running as root, and otherwise by injecting the failure through `call_main` with a patched
  `os.open` — the same technique 001 D-008 used for the stdout write-failure path, so no test needs
  `skipif` or `xfail` (Principle III forbids both).

Each failure path asserts **both** the exit status and the message content, and additionally that
no `wrote N files` line and no summary were produced.

---

## Summary of resolved unknowns

| # | Question | Resolution |
|---|---|---|
| D-101 | Phone pattern | `\+[0-9]{8,15}(?![0-9])`, explicit ASCII class, bounded quantifier |
| D-102 | How to rank phone below card | fourth stage over the gaps left by ranks 1–3 |
| D-103 | Cost of rejecting 16+ digits | ≤ 8 bounded attempts per `+`; worst line 6.78 ms of a 1 s budget |
| D-104 | Counts and summary shape | fourth dict key, `phones` appended to the field order |
| D-105 | `--out-dir` in any position | `_partition` learns value-taking options; abbreviation preserved |
| D-106 | Absent vs empty vs repeated DIR | `default=None`; last occurrence wins; missing value is argparse's exit 2 |
| D-107 | Where argument validation lives | `parser.error` at the boundary, before stdin or the filesystem is touched |
| D-108 | Creating DIR with owner-only modes | explicit per-component `mkdir(0o700)` + `chmod`; `makedirs(mode=)` applies to the leaf only |
| D-109 | Opening an output file safely | `O_WRONLY\|O_CREAT\|O_NOFOLLOW\|O_NONBLOCK`, checks on the fd, `ftruncate` last |
| D-110 | Diagnostic for a link or non-regular path | `lstat` for wording, `O_NOFOLLOW` for enforcement |
| D-111 | Containment | basename, reject `""`/`.`/`..`, require a resolved direct child of resolved DIR |
| D-112 | Destination plumbing and tally ordering | one branch in `main`; one file open at a time; tally after the last close |
| D-113 | Platform | POSIX, stated rather than faked with fallbacks |
| D-114 | Testing the filesystem surface | 001's two styles plus output-folder fixtures; no skips, no xfails |

**No `NEEDS CLARIFICATION` markers remain.**
