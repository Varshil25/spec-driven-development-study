# Phase 0 Research: Redact Personal Data From Log Files

**Feature**: `001-redact-log-pii` | **Date**: 2026-11-13

All findings below were verified empirically on CPython 3.13 before being recorded. Each
decision names the requirement it serves. No NEEDS CLARIFICATION items remain.

---

## R-001: Argument parsing — `--count` in any position (FR-001, FR-029)

**Decision**: Use `argparse` with `parser.parse_intermixed_args()` (not `parse_args()`), a
`--count` store-true flag, and a `files` positional with `nargs="*"`.

**Rationale**: FR-001 requires the flag and FILE arguments in any order. Verified:
`parse_args(["a.log", "--count", "b.log"])` **fails** with `error: unrecognized arguments:
b.log` and exit 2 — argparse consumes positionals in contiguous groups, so a flag between two
filenames breaks it. `parse_intermixed_args` (stdlib, 3.7+) handles the same input correctly,
returning `files=['a.log', 'b.log'], count=True` with order preserved.

It also satisfies FR-029 for free: an unrecognised flag yields `usage: python -m logredact
[--count] [FILE ...]` plus `logredact: error: unrecognized arguments: --redact-all` on stderr
and `SystemExit(2)` — a usage diagnostic that names the offending argument, with exit status 2,
and no input read. Both verified.

**Alternatives considered**:
- `parse_args()` — rejected: fails FR-001, verified above.
- `parse_known_args()` then sorting extras into files/flags — rejected: silently accepts an
  unknown flag unless re-checked by hand, and loses the command-line order of filenames.
- A hand-written argv loop — rejected under Principle IV: argparse already delivers the usage
  text, the offending-argument diagnostic, and exit status 2 that FR-029 demands.

**Note**: `prog` is set to `python -m logredact` so the diagnostic matches the documented
invocation rather than `__main__.py`.

---

## R-002: Encoding and byte-exact round-trip (FR-005, FR-005a, FR-005b)

**Decision**: Open every input with `encoding="utf-8", errors="surrogateescape",
newline="\n"`; reconfigure `sys.stdin` the same way and `sys.stdout` with
`encoding="utf-8", errors="surrogateescape", newline=""`.

**Rationale**:
- `errors="surrogateescape"` maps each undecodable byte to a lone surrogate (`\udce9`) on read
  and restores the identical byte on write — FR-005b's round-trip without aborting or
  substituting `U+FFFD`. Verified: `b"caf\xe9 line\r\nsecond\rinner\nno-eol"` read and
  rewritten produced byte-identical output.
- Naming the encoding explicitly (rather than relying on the default) makes output independent
  of `LANG`/`LC_ALL`/`PYTHONIOENCODING`, satisfying FR-005a and the constitution's "no hidden
  state" constraint.
- Surrogates never match the redaction patterns (which are ASCII-only), so undecodable bytes
  pass through untouched.

**Newline handling**: `newline="\n"` on read disables all translation and splits lines only at
`\n`, so a `\r\n` line is read as `"text\r\n"` and a bare `\r` stays inside the line. Verified
above. On write, `newline=""` likewise disables translation. Together these satisfy FR-005
(byte-for-byte, including a missing final newline) and the CRLF edge case.

**Alternatives considered**:
- `newline=""` on read — rejected: it also splits on a bare `\r`, so a progress-bar-style log
  line would be cut in two. Byte output is identical either way, but `\n`-only splitting is the
  simpler, more predictable unit of work.
- Binary I/O with `bytes` patterns — rejected: viable but forces every pattern, placeholder and
  test fixture into `bytes`; `surrogateescape` gives the same guarantee in `str`.
- `errors="replace"` / `"ignore"` — rejected: both violate FR-005b outright.

---

## R-003: Single-pass match resolution (FR-018, FR-019, FR-020)

**Decision**: One precompiled alternation `EMAIL | IP | CARD` with named groups, applied with
`pattern.sub(callback, line)`. The callback dispatches on `match.lastgroup`, validates, and
returns either the placeholder (incrementing that type's counter) or the matched text unchanged.

**Rationale**: `re.sub` already implements exactly FR-018 — it scans left to right, takes the
match starting earliest, and resumes after the replaced span, so replacements are never
rescanned. Python's alternation is ordered: at a position where more than one branch could
match, the first listed branch wins, which gives FR-019's email → IP → card precedence by
construction rather than by extra code. FR-020 follows for free: the inserted placeholders are
output text that the single pass never revisits, and they contain no `@` and no digits, so they
could not match anyway.

**Validation-after-match**: range checks (IP) and length+Luhn checks (card) cannot be expressed
in the pattern, so the callback performs them and returns `match.group(0)` unchanged on failure
(FR-011, FR-015, FR-016). Verified that a rejected candidate can never hide a valid shorter
match of another type: a dotted quad contains no `@` and too few digits to be a card, and the
digit-boundary guards (R-004) mean no card can begin inside a rejected digit run.

**Alternatives considered**:
- Three sequential `sub()` passes, one per type — rejected: it breaks FR-018 and FR-019
  (a later pass would see text the earlier one left behind, e.g. `user@1.2.3.4` would become
  `user@[IP]`, contradicting FR-007a) and would risk matching inside placeholders.
- A hand-rolled scanner with explicit position tracking — rejected under Principle IV; `re.sub`
  provides the same semantics.

---

## R-004: Pattern shapes and boundary guards (FR-007 … FR-017)

**Decision**:

| Type  | Pattern |
|-------|---------|
| email | `[A-Za-z0-9._%+-]+@(?:(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\|\d{1,3}(?:\.\d{1,3}){3})` |
| ip    | `(?<!\d)(?<!\d\.)\d{1,3}(?:\.\d{1,3}){3}(?!\d)(?!\.\d)` |
| card  | `(?<!\d)\d++(?:[ -]\d++)*+` |

**Rationale**:
- **Email** (FR-007): the domain alternation tries dotted labels first and falls back to the
  dotted-number form, so `user@1.2.3.4` and `user@999.1.1.1` both match whole and are counted as
  emails (FR-007a) with no range check. Because the pattern stops at the last TLD letter,
  trailing punctuation is never consumed (FR-008) — verified on `jane.doe+test@mail.example.com,`
  → `[EMAIL],`.
- **IP** (FR-010–FR-012): the four lookarounds are a direct transcription of FR-012 — not
  preceded by a digit, not preceded by digit-and-dot, not followed by a digit, not followed by
  dot-and-digit. Verified: `1.2.3.4.5` is left entirely alone (every candidate start position is
  blocked), while `from 10.0.0.7.` redacts and keeps the full stop.
- **Card** (FR-014–FR-017): `(?<!\d)` plus the trailing non-digit implied by the possessive
  quantifier implement FR-017's "no card inside a longer digit run". **Possessive quantifiers**
  (`++`, `*+`, new in Python 3.11) make the candidate maximal and non-backtrackable, which is
  what makes the doubled-separator edge case work: verified `4111  1111 1111 1111` splits into
  `4111` and `1111 1111 1111`, neither long enough, so nothing is redacted. They also rule out
  catastrophic backtracking on long digit runs.

The card pattern deliberately carries no `{13,19}` bound: the length test belongs in the
validator, because the digit count of a grouped candidate is only known after the separators are
stripped (FR-016). Verified that a 20-digit run matches as a candidate and is then rejected
whole, never partially redacted.

**Verification**: the full design was run against every acceptance scenario and edge case in the
spec. All produced the specified output, including `999.1.1.1`/`256.1.1.1` untouched beside
`0.0.0.0`/`255.255.255.255` redacted, `010.0.0.7` redacted (leading zeros assumption),
`4111-1111 1111-1111` redacted (mixed separators), `x4111111111111111y` → `x[CARD]y`,
`ts 2026-11-13 10:00:00` untouched, and `[EMAIL] [IP] [CARD]` passing through uncounted.

**Known consequence of the maximal-candidate rule** (follows from FR-014 + FR-015, flagged, not
a deviation): a card written next to another number joined by a single separator forms one
larger candidate. `code 7-4111 1111 1111 1111` is one 17-digit candidate that fails Luhn, so the
card is **not** redacted. The spec's doubled-separator edge case fixes this maximal-run reading,
and searching sub-runs instead would contradict it. The converse case over-redacts harmlessly:
`id 42 4111 1111 1111 1111` is an 18-digit candidate that happens to pass Luhn and is replaced
whole, which is the spec's stated safe direction.

---

## R-005: Luhn checksum (FR-014, FR-015)

**Decision**: A small pure function over the separator-stripped digit string: double every
second digit from the right, subtract 9 from any result above 9, sum, accept when the total is
divisible by 10. Applied only after the 13–19 length test passes.

**Rationale**: Six lines of stdlib arithmetic (Principle I), pure and directly unit-testable
(Principle III). Verified `4111 1111 1111 1111` accepted and `1234567890123` rejected.

**Alternatives considered**: a lookup-table variant — rejected as a micro-optimisation with no
requirement behind it (Principle IV).

---

## R-006: Early output close (FR-028)

**Decision**: Wrap the whole write path in `except BrokenPipeError`; on catch, redirect fd 1 to
`os.devnull` via `os.dup2`, then exit 0 without writing anything to stderr.

**Rationale**: Verified that an unhandled broken pipe prints a `BrokenPipeError` traceback and
exits **1** — violating FR-028 on both counts. Catching it alone is not enough: the interpreter
flushes `sys.stdout` during shutdown and would emit a second `Exception ignored in:` line to
stderr. Redirecting the file descriptor to `/dev/null` first makes that final flush succeed
silently. Verified end to end under `| head -3`: three lines out, **0 bytes on stderr**, exit
status 0, and no `--count` summary.

**Alternatives considered**:
- `signal.signal(SIGPIPE, SIG_DFL)` — rejected: it kills the process with SIGPIPE, so the shell
  reports status 141, not the 0 that FR-028 requires. It is also POSIX-only.
- Catching `BrokenPipeError` without the `dup2` — rejected: verified to leak shutdown noise to
  stderr, breaking FR-028's "nothing on standard error".

This is the one narrow exception handler justified against Principle II: an early-closing
consumer is a normal end of work, not input the tool failed to validate, per the spec's own
assumption. It catches exactly `BrokenPipeError` and exits deliberately — it does not swallow
other errors.

---

## R-007: Input failure handling (FR-025, FR-026, FR-027)

**Decision**: Catch `OSError` around both `open()` and the read loop for named files. On catch,
write `python -m logredact: <name>: <reason>` to stderr using the filename exactly as given on
the command line, stop processing further inputs, suppress the `--count` summary, and exit 2.

**Rationale**: `OSError` is the single narrow base class covering every cause FR-025 enumerates —
`FileNotFoundError`, `PermissionError`, `IsADirectoryError` (verified: `open()` on a directory
raises it on Linux), and mid-read `IOError`. Catching it is specific, not a bare `except`, and it
re-reports rather than swallows (Principle II). `UnicodeDecodeError` cannot occur because of
R-002. Output already written for earlier files stays on stdout untouched (FR-027), because the
tool streams and never rewinds.

**Ordering**: stdout is flushed before the `--count` summary is written to stderr, so FR-021's
"after all redacted output" holds even when both streams are redirected to the same file.

**Alternatives considered**:
- Pre-checking with `os.path.isfile()`/`os.access()` — rejected: a TOCTOU race and a second code
  path for the same failure; `open()` already reports the precise reason.
- Collecting errors and continuing to later files — rejected: contradicts FR-026 and the spec's
  fail-fast assumption.

---

## R-008: Streaming and performance (SC-007)

**Decision**: Iterate the file object line by line (`for line in stream:`) and write each
redacted line immediately. No input is accumulated; only the three integer counters persist
across lines.

**Rationale**: Line iteration on a `TextIOWrapper` is buffered and lazy, so memory stays flat
regardless of input size — SC-007's "memory use that does not grow with input size". A single
precompiled pattern with possessive quantifiers runs one linear scan per line; one million
typical log lines are well inside the 60-second budget.

**Alternatives considered**: `readlines()` or `sys.stdin.read()` — rejected: buffers the whole
input, directly violating SC-007. Block-wise reads with manual line splitting — rejected:
reimplements buffered line iteration for no measured gain (Principle IV).

---

## R-009: Test layout and import path (Constitution: pytest, bare invocation)

**Decision**: Tests in `tests/` at the repository root; a root `pytest.ini` containing
`pythonpath = src` so `import logredact` resolves under a bare `pytest`. CLI-level tests invoke
`[sys.executable, "-m", "logredact"]` via `subprocess.run` with `PYTHONPATH=src`.

**Rationale**: The constitution requires `pytest` runnable bare from the repository root, while
the spec fixes the package at `src/logredact`. The `pythonpath` ini option (pytest 7.0+) bridges
the two with one line and no packaging. `pytest` stays a test-time dependency only, imported by
nothing under `src/` (Principle I). Subprocess invocation is the only way to assert the real
contract — exit status, stream separation, and the broken-pipe path — rather than a simulation of
it.

**Alternatives considered**:
- A root `conftest.py` that mutates `sys.path` — rejected: imperative where one declarative line
  does the job.
- `pip install -e .` with a `pyproject.toml` — rejected: the spec defines the tool as runnable
  from `src/` on `PYTHONPATH` with no install step, and the constitution forbids a required
  `pip install`.
- Calling `main()` in-process for every test — rejected as the sole approach: it cannot observe a
  real exit status or a real broken pipe. Used only where unit-level access is clearer.
