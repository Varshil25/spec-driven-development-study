# Phase 0 Research: Log Redaction CLI

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-11-21

## Status of unknowns

The Technical Context in [plan.md](./plan.md) contains **no NEEDS CLARIFICATION markers**. The
requester supplied the language, dependency policy, layout, and test framework; the spec's
Assumptions section had already resolved the behavioural ambiguities. Phase 0 therefore did not
need to resolve open questions about *what* to build.

What it did instead was verify that the stated interface is actually achievable with the
standard library, because three of the spec's requirements are the kind that look trivial and
are not:

- FR-001 ("`--count` accepted in any position") — **`argparse` cannot do this** (D-007).
- FR-017 (leftmost-wins precedence across three overlapping rule families) — resolvable, but
  only after deciding how cards interact with the other two rules (D-004).
- FR-006 ("exactly as read, including … the presence or absence of a trailing line ending") —
  requires opting out of universal-newline translation (D-008).

Every decision below was checked by running code, not by recall. The probe suite covered 36
input/output pairs drawn from the spec's acceptance scenarios and edge-case list; all 36 produced
the specified output. Three additional probes covered argument parsing, I/O fidelity, and
throughput.

---

## D-001: Email recognition — one regex, anchored on the final label

**Decision**: `[A-Za-z0-9._%+\-]+@(?:[A-Za-z0-9\-]+\.)+[A-Za-z]{2,}`

**Rationale**: Transcribes FR-008 literally. The `(?:label\.)+` repetition requires at least one
dot, which is what makes FR-009 reject `jane@localhost`; `[A-Za-z]{2,}` is the "final label of at
least two letters" clause, which rejects `x@y.c`. No `\b` is needed — the character classes are
their own boundaries.

**Verified**: `jane.doe+test@mail.example.com` → `[EMAIL]`; `jane@localhost`, `bare @ sign`,
`x@y.c` → unchanged; `12345678901234-user@x.com` → `[EMAIL]` (digits and hyphens are legal local
part characters, so this is one email, not a card followed by text).

**Alternatives considered**: RFC 5322-conformant matching (rejected — vastly larger, and FR-008
defines a narrower grammar that the tests will assert); `email.utils.parseaddr` from the stdlib
(rejected — it parses a header field, does not *find* addresses inside arbitrary text, and
accepts things FR-009 requires rejecting).

## D-002: IPv4 recognition — range-checked in the pattern, with mirrored boundary guards

**Decision**:

```python
OCTET = r"(?:25[0-5]|2[0-4]\d|[01]?\d?\d)"
IPV4  = rf"(?<!\d)(?<!\d\.){OCTET}(?:\.{OCTET}){{3}}(?!\d)(?!\.\d)"
```

**Rationale**: The alternation enforces 0-255 (FR-011) without a Python-side check, so no
candidate needs a callback. The two lookaheads are FR-013 verbatim: not followed by a digit, and
not followed by `.`+digit — the pair that makes `192.168.0.10.` redact while `1.2.3.4.5` does
not.

The `(?<!\d\.)` lookbehind is **derived, not stated in FR-013**, and it is required for
correctness. FR-013's forward guard alone leaves `1.2.3.4.5` partially matched: the candidate at
offset 0 is correctly rejected, but the scan then reaches offset 2, where `2.3.4.5` is preceded
by `.` (not a digit) and followed by end-of-string — so it would match, producing `1.[IP]` and
contradicting the spec's own edge case ("`1.2.3.4.5` is left unchanged"). Mirroring the forward
`(?!\.\d)` guard backwards resolves the spec's internal tension in favour of the explicitly
stated outcome.

**Verified**: `10.0.0.7`, `0.0.0.0`, `255.255.255.255` → `[IP]`; `999.1.1.1`, `256.1.1.1`,
`1.2.3`, `1.2.3.4.5`, `v1.2.3` → unchanged; `connect to 192.168.0.10.` → `connect to [IP].`;
`user@1.2.3.4` → `user@[IP]`.

**Alternatives considered**: `\d{1,3}` parts plus a Python range check in the callback (rejected —
moves work out of the compiled pattern for no behavioural gain and adds a branch per candidate);
`ipaddress.IPv4Address` validation (rejected — it validates a complete string, so it still needs
a finder regex, and it accepts forms FR-011 excludes).

### Derived sub-decision: leading zeros are accepted

`[01]?\d?\d` matches `01`, `007`, and `000`, so `007.0.0.1` and `01.2.3.4` redact to `[IP]`.
FR-011 says each part is "a decimal number in the range 0 to 255" and is silent on zero padding;
`007` reads as 7, which is in range. The tie-break is the spec's stated bias — over-redaction is
the safe direction for a privacy tool — so padded quads are redacted rather than leaked.
Four-digit parts are still rejected (`0255.1.1.1` is unchanged) because the digit-boundary guards
apply. Flag for `/speckit-clarify` if canonical-form-only matching is wanted.

## D-003: Card recognition — bounded-window regex plus a Python Luhn check

**Decision**: candidate pattern `(?<!\d)(?:\d[ \-]?){12,18}\d(?!\d)`, then validate with an
8-line `luhn()` over the separator-stripped digits.

**Rationale**: A checksum is not expressible as a regular expression, so the split is forced:
regex finds *shaped* candidates, Python decides. The unit `(?:\d[ \-]?)` makes the digit count —
not the character count — the thing being bounded, giving exactly 13 to 19 digits (FR-015/FR-016)
however the groups are separated. Because every unit's separator *follows* a digit, double
separators, leading separators, and trailing separators are all structurally impossible, which is
what makes `4111  1111 1111 1111` (double space) fail as required. The `{12,18}` cap is load
bearing in a non-obvious way: an uncapped "maximal run" pattern would consume short digit runs,
and a run ending adjacent to an address (`1234 10.0.0.7`) would swallow the first octet and hide
an IPv4 address from the scan. The cap plus the `(?!\d)` lookahead guarantees a match always ends
on a group boundary.

**Verified**: `4111 1111 1111 1111`, `4111-1111-1111-1111`, `4111-1111 1111-1111` (mixed
separators, per the spec's Assumptions), and bare `4111111111111111` → `[CARD]`;
`1234567890123` (Luhn-invalid 13 digits), `123456789012` (12 digits), `11111111111111111111`
(20 digits), `4111  1111 1111 1111` (double space), `4111,1111,1111,1111` (comma),
`2026-11-20 10:00:00` → unchanged; `x4111111111111111` → `x[CARD]`.

**Alternatives considered**: brand/BIN prefix validation (rejected — the spec's Assumptions
explicitly exclude it); `{13,19}` on a character count (rejected — wrong unit; it miscounts any
separated number).

## D-004: Overlap resolution — email+IPv4 in one alternation pass, cards in a second pass

**Decision**: Pass A is `re.sub` over `(?P<email>…)|(?P<ip>…)`. Pass B scans pass A's output for
card candidates. Counts accumulate across both.

**Rationale**: Python's alternation is leftmost-first — it takes the earliest start position, and
among alternatives at that position it prefers the earlier branch — which *is* FR-017 ("the match
starting at the leftmost position MUST win; where candidates start at the same position, email
MUST take precedence over IPv4"). Writing email before IPv4 in the pattern is the whole
implementation of that clause. `re.sub` never rescans replacement text, which is FR-018 for free.
Cards cannot join that alternation, because a Luhn-failing branch cannot "give the match back" to
a later alternative in a single `re.sub`.

Running cards second is safe in the ordinary case and strictly safer in the overlapping case.
Placeholders contain no digits, dots, or `@`, so pass B cannot match inside pass A's output
(FR-018 holds), and card text (digits, single spaces, single hyphens) contains no `@` or `.`, so
pass B never has an email or IPv4 hidden inside a candidate.

**The one divergence from a literal single-pass reading of FR-017**, recorded here because the
Constitution's Workflow Gate 2 requires design choices to be visible in the plan: when a card
candidate *overlaps* an IPv4 address — possible only when a 13-19 digit run is joined to an
address by a single space, as in `4111111111111111 10.0.0.7` — strict leftmost-wins would let the
card candidate (starting further left) consume the address's first octet and emit
`[CARD].0.0.7`, leaving `.0.0.7` in the output. Worse, if that merged 18-digit window fails Luhn,
the single-pass scan consumes it, leaves it unchanged, and resumes *past* the address — leaking
the whole IPv4 address. IPv4-before-cards produces `card [CARD] [IP]` (**verified**) in the first
case and `1111111111111 [IP]` in the second. It redacts a superset of what strict leftmost-wins
redacts and never a subset, which is the direction SC-002 ("the leak rate is 0%") demands.

**Alternatives considered**: a single three-branch alternation whose callback returns
`match.group(0)` unchanged on Luhn failure (rejected — the leak just described, demonstrated by
probe on `card 4111111111111111 10.0.0.7`); a maximal-run card pattern with a recursive callback
that re-scans leftover text for addresses (rejected — restores correctness at the cost of
re-entrant scanning, which Principle IV rules out when a two-line pass ordering achieves the same
result).

## D-005: A Luhn-failing window is left unchanged, and the scan restarts one character later

**Decision**: Pass B is a `while` loop over `CARD.search(text, pos)` rather than `re.sub`:

```python
if luhn(digits):   emit "[CARD]";  pos = m.end()
else:              emit one char;  pos = m.start() + 1
```

**Rationale**: FR-016 requires a Luhn-failing candidate to be left unchanged. `re.sub` would also
*consume* it, skipping any valid card nested behind it: in `123 4111111111111111` the leftmost
window is all 19 digits, which fails Luhn, and consuming it would hide the valid 16-digit card
that follows the space. Advancing by one character instead lets the scan re-enter at the next
legal start — the `(?<!\d)` lookbehind still works when `search` is given a `pos`, because `pos`
is not a slice and lookbehind can see behind it. **Verified**: `123 4111111111111111` →
`123 [CARD]`.

**Residual limitation, accepted and stated precisely**: if the longest window at a start position
fails Luhn but a *shorter* window at the **same** start would pass, the shorter one is not tried.
Concretely: a digit run of 3+ separated groups totalling more than 19 digits, where a valid card
occupies the leading groups and the trailing digits begin at a position preceded by a digit. This
is the same class of false negative the spec already accepts in its edge-case list ("a 20+ digit
run … is left unchanged, even if some substring of it would pass the Luhn check") and follows
directly from FR-016's wording.

**Alternatives considered**: exhaustive sub-window search (longest-first at each group start,
retrying all shorter windows). Rejected: it contradicts FR-016's plain reading, costs an inner
loop over up to 7 windows per candidate, and increases over-redaction of long correlation ids —
and the spec already treats this exact trade as settled. `/speckit-clarify` can reverse it; doing
so changes only `redact_text`'s inner loop.

## D-006: Luhn implementation

**Decision**: double every second digit from the right, subtract 9 when the doubled value exceeds
9, sum, accept when the total is divisible by 10.

**Verified**: `4111111111111111` → valid; `1234567890123` → invalid (the spec's two worked
examples).

**Alternatives considered**: a lookup table for doubled digits (rejected — a micro-optimisation
invisible against regex cost; the probe already runs 7x inside the SC-006 budget).

## D-007: Argument parsing — hand-written, because `argparse` cannot satisfy FR-001

**Decision**: a ~15-line scan of `sys.argv[1:]`: exactly `--count` sets the flag; any other token
beginning with `-` and longer than one character is an unrecognised option (usage to stderr, exit
2); every remaining token, including a bare `-`, is a FILE path in order.

**Rationale**: this is the one place where the obvious stdlib answer is wrong, and it was caught
by probing rather than assumed. FR-001 requires `--count` "in any position relative to file
arguments". `argparse` with `positional nargs="*"` **fails** on an interspersed flag — a
documented consequence of how it splits argument groups:

| `argv` | `argparse` result |
|---|---|
| `['--count', 'a.log', 'b.log']` | `count=True files=['a.log','b.log']` ✓ |
| `['a.log', '--count']` | `count=True files=['a.log']` ✓ |
| **`['a.log', '--count', 'b.log']`** | **`error: unrecognized arguments: b.log`, exit 2** ✗ |

Any `argparse`-based fix (pre-filtering `--count` out of `argv`, or `parse_known_args`, which
would silently accept unknown options and violate FR-024) requires hand-writing part of the
parse anyway, so hand-writing all 15 lines is both smaller and the only version that meets
FR-001. Exit status 2 is kept for the usage error — it matches `argparse`'s own convention and
satisfies FR-024's "non-zero". It coincides with the unreadable-file status, which FR-023/FR-024
permit, and the two cases are distinguished by their messages.

**Derived sub-decision**: `-h`/`--help` is **not** implemented; like any other unrecognised
option it yields the usage message and exit 2. No requirement asks for a help flag, and Principle
IV prohibits unrequested surface. The usage string exists regardless, since FR-024 requires it.
Flag for `/speckit-clarify` if a help flag is wanted.

## D-008: Stream I/O — explicit UTF-8, `newline=""`, strict decoding

**Decision**: open files as `open(path, "r", encoding="utf-8", newline="", errors="strict")`;
wrap `sys.stdin.buffer` and `sys.stdout.buffer` in `io.TextIOWrapper` with the same settings.

**Rationale**: FR-006 requires a line to come out "exactly as read, including … the presence or
absence of a trailing line ending". Default universal-newline mode rewrites `\r\n` to `\n`,
breaking that; `newline=""` keeps each terminator attached to its line while still splitting on
all three conventions. **Verified**: `'a@b.io line1\r\nno newline at end 1.2.3.4'` reads back as
`['a@b.io line1\r\n', 'no newline at end 1.2.3.4']` — CRLF intact, no newline invented for the
final line. Forcing `encoding="utf-8"` on *output* as well matters because an inherited `C`
locale would otherwise pick ASCII and crash on non-ASCII passthrough text; re-encoding
UTF-8-decoded text as UTF-8 cannot fail. `errors="strict"` is what turns undecodable bytes into
the exit-2 path the spec's Assumptions require, rather than `U+FFFD`-mangled output.

**Alternatives considered**: byte-level processing with `bytes` patterns (rejected — the spec's
Assumptions fix UTF-8 text semantics, and byte mode would redefine "line" and "letter");
`errors="replace"` (rejected — explicitly contrary to the "decode failures are read failures"
assumption and to Principle II).

## D-009: Read-failure detection — catch `OSError` and `UnicodeDecodeError` per file

**Decision**: wrap each file's open-and-stream in `except (OSError, UnicodeDecodeError) as exc`,
report `logredact: {path}: {reason}`, stop, exit 2.

**Rationale**: one `OSError` base covers every variant FR-022 lists with the *reason already
filled in by the OS*, so the diagnostic names both the path and what went wrong, as Principle II
demands. **Verified**: a missing path raises `FileNotFoundError` with `strerror='No such file or
directory'`; a directory raises `IsADirectoryError` ('Is a directory'); permission denial raises
`PermissionError`; undecodable bytes raise `UnicodeDecodeError` ('invalid start byte'). Note that
`UnicodeDecodeError` surfaces *during* iteration, after earlier lines of that file have already
been written — consistent with the spec's "output already written is left in place" assumption.

**Alternatives considered**: pre-flighting every path with `os.access`/`Path.is_file` before
reading (rejected — a TOCTOU race and a second code path for the same failure, where the
exception already carries a better message).

## D-010: Broken pipe — restore the default `SIGPIPE` disposition

**Decision**: at startup, `signal.signal(signal.SIGPIPE, signal.SIG_DFL)` where the signal
exists, plus a `BrokenPipeError` guard around the final flush.

**Rationale**: the spec's last edge case requires that a closed stdout ("for example by a pipe to
`head`") terminate the tool "without an unhandled crash report". Python installs a `SIGPIPE`
handler that converts the signal into an exception, so the default behaviour is a traceback.
**Verified** by probe: without the change, `… | head -2` prints a 194-byte
`BrokenPipeError` traceback to stderr and exits 1; with it, stderr is empty and the exit status
is 141 (128+13), exactly how `cat` behaves in the same pipeline. The explicit
`BrokenPipeError` catch covers interpreter shutdown flushes and platforms without `SIGPIPE`;
catching one specific anticipated exception type is permitted by Principle II.

**Alternatives considered**: catching `BrokenPipeError` alone and exiting 0 or 1 (rejected —
reports success or an ambiguous failure for a truncated privacy-sensitive stream, and still risks
a shutdown-time traceback unless stdout is redirected to `os.devnull` first).

---

## Throughput measurement (SC-006)

| Input | Result |
|---|---|
| 100,000 lines / 10.3 MB, every line carrying an email, an IPv4 address, and a grouped card | **1.40 s**, 300,000 replacements, memory flat (one line resident) |

Against the 10-second budget in SC-006 this leaves roughly a 7x margin, measured with both regex
passes and the Luhn check active on every line. Because the loop holds exactly one line at a
time, the 1 GB case in SC-006 is bounded by the longest line rather than by file size. No
optimisation work is warranted; the simple implementation is already comfortably inside budget.

## Consolidated decision summary

| ID | Decision | Drives |
|----|----------|--------|
| D-001 | Single email regex anchored on a ≥2-letter final label | FR-007, FR-008, FR-009 |
| D-002 | Range-checked octet alternation; forward *and* mirrored backward boundary guards | FR-010…FR-013 |
| D-003 | Digit-counted window regex `(?:\d[ \-]?){12,18}\d` + Luhn | FR-014, FR-015, FR-016 |
| D-004 | Email+IPv4 in one leftmost-first alternation; cards in a second pass | FR-017, FR-018 |
| D-005 | Luhn failure leaves text unchanged; scan restarts at start+1 | FR-016 |
| D-006 | Textbook Luhn, 8 lines, no table | FR-015 |
| D-007 | Hand-written parser (`argparse` fails FR-001); no `--help` | FR-001, FR-024 |
| D-008 | Explicit UTF-8, `newline=""`, strict errors on both streams | FR-005, FR-006 |
| D-009 | `OSError`/`UnicodeDecodeError` per file → named diagnostic, exit 2 | FR-022, FR-023 |
| D-010 | `SIGPIPE` → `SIG_DFL` + `BrokenPipeError` guard | Closed-output edge case |
