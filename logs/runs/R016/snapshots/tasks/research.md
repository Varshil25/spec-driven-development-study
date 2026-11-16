# Phase 0 Research: Log Redaction CLI

**Branch**: `001-logredact-cli` | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

Purpose: resolve every technical unknown and every internal contradiction in the specification
before design. Each section states a Decision, a Rationale, and the Alternatives considered.

## Summary of unresolved items entering Phase 0

| # | Item | Status |
|---|------|--------|
| R1 | Minimum Python version (constitution `TODO(PYTHON_VERSION)`) | Resolved |
| R2 | Single-pass precedence scan with a *rejectable* candidate (Luhn) | Resolved |
| R3 | IPv4 boundary rule — spec text conflicts with itself (`v1.2.3.4`) | Resolved (spec correction recommended) |
| R4 | Email domain rule — spec text conflicts with itself (`user@1.2.3.4`) | Resolved (spec correction recommended) |
| R5 | Byte-for-byte line fidelity (`\r`, no trailing newline, non-UTF-8) | Resolved |
| R6 | `--count` accepted in any position | Resolved |
| R7 | Closed standard output (broken pipe) behaviour and exit status | Resolved |
| R8 | `pytest` import of a package under `src/` with no custom configuration | Resolved |
| R9 | Performance: 100k lines < 10 s, memory flat | Resolved |

---

## R1. Minimum Python version

**Decision**: Python 3.11 or newer (CPython). Recommend amending the constitution to replace
`TODO(PYTHON_VERSION)` with "3.11".

**Rationale**: The feature description, the spec Assumptions section, and the user input for this
planning step all state 3.11+. The constitution requires the version to be pinned *before the first
implementation task*, so this must be recorded now. Nothing in the design needs a feature newer than
3.11 (`re`, `argparse`, `TextIOWrapper.reconfigure` are all much older); 3.11 is therefore a floor,
not a requirement.

**Alternatives considered**: 3.9/3.10 (rejected — contradicts the stated constraint, buys nothing);
3.12+ (rejected — narrows the supported range with no benefit).

**Note**: the environment used for development reports CPython 3.13.17, which satisfies the floor.

## R2. Single-pass left-to-right precedence scan with a rejectable candidate

**Problem**: FR-015 requires one left-to-right scan preferring email, then IPv4, then card, with text
consumed by a replacement never reconsidered. Email and IPv4 are decidable by regular expression
alone, but a card candidate must additionally pass the Luhn checksum (FR-013), which `re` cannot
express. A rejected candidate is *not* a replacement, so FR-015 does **not** permit its text to be
skipped.

**Why the obvious implementations are wrong**:

- `re.sub(COMBINED, callback, line)` returning `match.group(0)` unchanged when Luhn fails **loses
  redactions**. On input `123 1.2.3.4`, the card pattern matches the maximal group-run `123 1`
  (digits joined by a single space), fails the length check, and `re.sub` resumes *after* that
  match — so the `1` that begins `1.2.3.4` has been eaten and the IPv4 address is never seen.
  Output would be `123 1.2.3.4`, violating FR-010/FR-014.
- Position-by-position `pattern.match(line, i)` for three patterns is correct but does the scanning
  in Python rather than in the regex engine; at ~8 M characters for a 100k-line log that is roughly
  24 M `match()` calls, which risks the SC-008 budget.

**Decision**: one compiled combined pattern with ordered alternation
(`(?P<email>…)|(?P<ip>…)|(?P<card>…)`) driven by an explicit `search(line, pos)` loop:

1. `m = COMBINED.search(line, pos)`; if no match, emit `line[pos:]` and stop.
2. If the matched group is `email` or `ip`, emit `line[pos:m.start()]` + placeholder, set
   `pos = m.end()`, increment that category's count.
3. If the matched group is `card`, strip separators and validate (13–19 digits **and** Luhn). On
   success, behave as in step 2. **On failure, emit `line[pos:m.start() + 1]` and set
   `pos = m.start() + 1`** — i.e. restart the scan one character into the rejected candidate rather
   than past it.

**Rationale**:

- Restarting at `start + 1` is exactly "the rejected text was not consumed by a replacement, so it
  is still considered"; `123 1.2.3.4` then yields `123 [IP]` as FR-010 requires.
- Advancing by at least one character on every iteration guarantees termination.
- The regex engine still performs all scanning, so the common case (no rejection) is a single pass
  in C. Rejections are rare and locally bounded.
- Alternation order gives FR-015's precedence for free: Python `re` prefers the leftmost match, and
  among alternatives starting at the same offset it prefers the first one listed.
- Re-scanning inside a rejected *card* candidate cannot resurrect a fragment that the spec forbids,
  because the card pattern's `(?<!\d)` lookbehind blocks every interior digit position (see R3), and
  a card candidate contains only digits, single spaces, and single hyphens — so it can never hide an
  email (needs `@`) or an IPv4 address (needs `.`).

**Alternatives considered**: three separate sequential `re.sub` passes (rejected — cannot express
FR-015 precedence; an IPv4 pass would partly redact an address inside an email); regex module with
recursion/conditionals (rejected — third-party, violates Principle I).

### Luhn check

**Decision**: iterate the digit string right-to-left, double every second digit, subtract 9 when the
doubled value exceeds 9, and require the total to be ≡ 0 (mod 10). Pure integer arithmetic over the
digit characters, no table.

**Rationale**: smallest correct implementation (Principle IV), no allocation beyond the digit string.
Verified against the spec's own examples: `4111111111111111` passes, `1234567890123` fails.

### Maximal-run-then-validate for cards

**Decision**: the card pattern matches a *maximal* run `(?<!\d)\d+(?:[ -]\d+)*(?!\d)`; the digit
count is then checked in code against 13–19.

**Rationale**: this is the only reading consistent with the spec's edge cases. "12 digits or fewer,
and 20 digits or more, are never redacted as a card, even if some 13-to-19-digit window inside them
would pass Luhn" requires the *run as a whole* to be judged, which a counting regex would not do.
A single `[ -]` character class gives "a doubled separator ends the number" automatically (the
character after a separator must be a digit), and allows mixed separators
(`4111-1111 1111-1111` is one card) as the Assumptions section requires. Group sizes are
deliberately unconstrained.

## R3. IPv4 boundary rule — internal spec conflict

**Conflict**: the Edge Cases section states that `v1.2.3.4` is **not** an IPv4 address, but the
Assumptions section defines the boundary as "not immediately adjacent to a character that would
extend it — a digit or a dot for an IPv4 address". Under the digit-or-dot rule, `v1.2.3.4`
*would* be redacted to `v[IP]`, contradicting the edge case.

**Decision**: use the strictest rule that satisfies **both** statements — reject a candidate that is
immediately preceded or followed by a word character or a dot:

```python
IP = r"(?<![\w.])(?:25[0-5]|2[0-4]\d|[01]\d\d|\d\d|\d)(?:\.(?:25[0-5]|2[0-4]\d|[01]\d\d|\d\d|\d)){3}(?![\w.])"
```

**Rationale**:

- `\w` is a superset of "digit", so every case the Assumptions rule covers is still covered, and the
  explicitly enumerated edge case (`v1.2.3.4`) is also honoured. One rule, no special cases.
- The lookbehind is what makes `999.1.1.1` safe: without it the engine would happily match the
  fragment `99.1.1.1` starting at offset 1. With it, every interior offset is blocked, so the run is
  reproduced whole as the Edge Cases section demands. The same mechanism protects `256.0.0.1`,
  `1.2.3`, `1.2.3.4.5` and `1.2.3.45678`.
- The component alternation is ordered longest-first and accepts 1–3 digits with value 0–255,
  including leading zeros (`010.0.0.1` is an address, per the Assumptions section). `256` matches no
  alternative as a whole component, and partial matches (`25`) fail because the next character must
  be `.`.
- Verified by hand against every IPv4 example in the spec; no fragment of any invalid run is matched.

**Consequence to accept knowingly**: a trailing dot ends the token, so `connect to 1.2.3.4.` leaves
the address unredacted. This follows directly from the spec's own "not butted up against another
digit or dot" rule and from `1.2.3.4.5` being required to stay unchanged; the two cannot be
separated by a line-local rule. Flagged for the spec owner below.

**Alternatives considered**: `(?<![\d.])`/`(?![\d.])` (rejected — fails the `v1.2.3.4` edge case);
`\b` word boundaries (rejected — `\b` does not treat `.` as extending the token, so
`1.2.3.4.5` would be partly redacted); `ipaddress.IPv4Address` for validation (rejected — needs
candidate extraction first, and `ipaddress` accepts forms the spec excludes).

## R4. Email domain rule — internal spec conflict

**Conflict**: FR-009 defines the domain as "one or more domain labels … ending in a final label of
at least two letters". By that rule `user@1.2.3.4` is **not** an email address (final label `4`),
and the scan would instead produce `user@[IP]`. But the Edge Cases section states "in
`user@1.2.3.4`, the whole value is recognised as one email address and becomes `[EMAIL]`; the
embedded address is not separately redacted and is not counted as an IP", and the Assumptions section
repeats it as the reason the precedence order was chosen.

**Decision**: implement the behaviour stated twice (`user@1.2.3.4` → `[EMAIL]`, counted as one
email) by treating the email domain as *either* ordinary labels ending in a ≥2-letter label *or* a
bare IPv4 address:

```python
EMAIL = r"[A-Za-z0-9._%+-]+@(?:" + IPV4_BODY + r"|(?:[A-Za-z0-9-]+\.)*[A-Za-z]{2,})"
```

**Rationale**:

- Two of the spec's three statements about this value agree on `[EMAIL]`, and it is the only outcome
  consistent with the stated *reason* for the precedence order in FR-015.
- It is also the safer behaviour for a privacy tool: `user@[IP]` publishes the local part `user`,
  while `[EMAIL]` leaks nothing. Under-redaction is the failure mode this feature exists to prevent.
- FR-009's positive examples are unaffected: `a@b.io` and `jane.doe+test@mail.example.com` both
  still match through the ordinary-labels branch.
- No boundary guard is placed on the local part: the spec states none, and leftmost scanning with a
  greedy local part means any adjacent local-part characters are absorbed into the redaction, which
  errs toward removing more rather than less.

**Spec correction recommended (non-blocking)**: FR-009 should be amended to add "or a valid IPv4
address" as an accepted domain form. Per the constitution ("Specifications … are subordinate to this
constitution; where they conflict, this document wins and the artifact MUST be corrected"), the
spec's own internal conflict should be settled in `spec.md` rather than only here. Design and tasks
proceed on the decision above; if the spec owner prefers FR-009 as written, only the email pattern's
first branch and two tests change.

**Alternatives considered**: follow FR-009 literally and produce `user@[IP]` (rejected — contradicts
two other sections, and under-redacts); special-case the single literal `user@1.2.3.4` (rejected —
not a rule, and Principle IV forbids it).

## R5. Byte-for-byte line fidelity

**Decision**: open every input with `encoding="utf-8", errors="surrogateescape", newline=""`, and
reconfigure `sys.stdin`/`sys.stdout` the same way. Iterate the file object (which yields each line
*with* its terminator) and write each redacted line with `write()`, never `print()`.

**Rationale**:

- `newline=""` disables universal-newline translation, so `\r\n` and a lone `\r` survive into the
  string and back out unchanged (FR-007, "carriage returns" edge case). The default
  `newline=None` would rewrite `\r\n` to `\n` and break byte fidelity.
- Iterating the file keeps the line terminator attached, so a final line with no trailing newline is
  written back with none — no newline is invented (FR-007). `print()` would append one.
- `errors="surrogateescape"` maps undecodable bytes to lone surrogates on input and back to the
  original bytes on output, so a non-UTF-8 line passes through unaltered instead of crashing or being
  replaced. None of the three patterns can match a surrogate, so such bytes are never redacted.
- Redaction operates on one line at a time, so memory is independent of input length (SC-008) and a
  value split across a line ending is not redacted (stated assumption).
- Blank, whitespace-only, and very long lines need no special handling under this scheme; everything
  outside a match is copied by slicing.

**Alternatives considered**: binary mode with `bytes` patterns (rejected — the spec defines the email
character classes in text terms, and `surrogateescape` already gives byte fidelity at lower
complexity); reading whole files into memory (rejected — violates SC-008's flat-memory requirement).

## R6. `--count` in any position

**Decision**: `argparse` with `--count` as `store_true` and `files` as `nargs="*"`, parsed with
`parser.parse_intermixed_args()`. Set `prog="logredact"` explicitly.

**Rationale**: with a `nargs="*"` positional, plain `parse_args()` rejects
`a.log --count b.log` as "unrecognized arguments", which FR-004 forbids;
`parse_intermixed_args()` (3.7+) exists for exactly this shape and handles the flag before, among,
or after the operands. `argparse` also gives FR-005 for free: an unknown option produces a usage
diagnostic on stderr and exits 2, without being mistaken for a file name. `prog` must be set because
under `python -m logredact` argparse would otherwise name the program `__main__.py`.

**Alternatives considered**: hand-rolled `sys.argv` loop (rejected — reimplements diagnostics and
exit codes argparse already provides, more code for less behaviour); `getopt` (rejected — no usage
message, no exit-2 convention).

## R7. Closed standard output (broken pipe)

**Decision**: catch `BrokenPipeError` around the whole run; on it, redirect `fd 1` to `os.devnull`
with `os.dup2` to silence the interpreter's shutdown flush, write
`logredact: cannot write to standard output: Broken pipe` to stderr (ignoring failure if stderr is
also gone), emit **no** `--count` summary, and exit with status **2**.

**Rationale**: the spec requires stopping "without a traceback" but does not name a status. Status 2
is the only choice consistent with SC-007 ("every run that cannot produce the complete redacted
output … exits with status 2 and explains itself on standard error") and with Principle II, which
forbids swallowing a failure silently. Suppressing the summary follows FR-018/FR-022 — not all
output was written. The `dup2` step is required because without it CPython prints
`Exception ignored in: <_io.TextIOWrapper name='<stdout>'>` during interpreter shutdown, which is a
traceback-shaped message on stderr.

**Alternatives considered**: exit 0 (rejected — reports success for an incomplete redaction, the
exact failure mode Principle II bans); exit 141 / re-raise `SIGPIPE` (rejected — SC-007 specifies 2
for incomplete output, and restoring default SIGPIPE handling is platform-specific); silent exit
(rejected — Principle II requires a diagnostic).

## R8. Making `logredact` importable by plain `pytest`

**Decision**: a single `tests/conftest.py` that prepends the repository's `src/` to `sys.path`, plus
a `run_cli` helper fixture there that invokes
`[sys.executable, "-m", "logredact", …]` with `PYTHONPATH=<repo>/src` via `subprocess.run`.

**Rationale**: the constitution requires plain `pytest` from the repository root to work "with no
custom configuration required", which rules out `pytest.ini`/`pyproject.toml` `pythonpath` entries
and a `PYTHONPATH=src pytest` invocation. `conftest.py` is test code, not configuration, and pytest
imports it before any test module, so unit tests can `from logredact.redact import …` directly. The
subprocess helper is what proves FR-001 (`python -m logredact`) and the exit statuses for real,
rather than by calling `main()` in-process.

**Alternatives considered**: packaging metadata + editable install (rejected — Principle I bans an
install step beyond obtaining the source); `sys.path` hacks inside each test file (rejected —
duplication); testing only in-process (rejected — cannot verify FR-001 or exit codes).

## R9. Performance

**Decision**: one module-level compiled combined pattern, line-at-a-time streaming, output written
through the buffered text layer with no explicit per-line flush.

**Rationale**: scanning stays in the C regex engine (R2), so per-line cost is a single pass plus one
Python-level iteration per match. Measured on the design prototype (CPython 3.13, this environment):
100,000 copies of a dense 120-character log line carrying four replacements and two rejected
candidates redact in **1.36 s**, against the 10 s SC-008 budget — and a realistic log line carries
far fewer matches. Memory is bounded by the longest single line, satisfying SC-008's flat-memory
requirement. A
deliberate per-line flush would dominate runtime and is not needed — the only ordering requirement is
FR-018, satisfied by flushing stdout once before writing the summary.

**Alternatives considered**: `re.sub` with a callback (rejected on correctness in R2, not
performance); per-line flush (rejected — large constant cost, no requirement); multiprocessing
(rejected — Principle IV, and output order must be preserved).

---

## Items for the spec owner (do not block Phase 1)

1. **FR-009 vs the `user@1.2.3.4` edge case** (R4) — recommend amending FR-009 to accept a bare IPv4
   address as a domain form. Implemented as `[EMAIL]`.
2. **IPv4 boundary wording** (R3) — the Assumptions section says "digit or a dot" while Edge Cases
   requires `v1.2.3.4` to be excluded; recommend restating the rule as "not adjacent to a word
   character or a dot". Implemented as the stricter rule, which satisfies both.
3. **Constitution `TODO(PYTHON_VERSION)`** (R1) — pin to 3.11 before implementation begins.
4. **Exit status for a closed stdout** (R7) — the spec is silent; implemented as 2 with a
   diagnostic, by analogy with SC-007.
