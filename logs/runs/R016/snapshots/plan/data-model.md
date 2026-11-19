# Phase 1 Data Model: Log Redaction CLI

**Branch**: `001-logredact-cli` | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

This tool holds no persistent state and defines no classes. "Entities" here are the three concepts
the spec names, expressed as the smallest Python values that carry them. Recognition grammar lives in
[contracts/redaction-rules.md](./contracts/redaction-rules.md); this document covers shape,
validation, and lifetime.

## Entity 1 — Input source

An ordered sequence of text lines, originating either from a named file operand or from standard
input.

| Aspect | Value |
|--------|-------|
| Representation | An open text file object (`io.TextIOWrapper`) |
| Fields | `name` (the operand as the user typed it, or `"<stdin>"` for standard input) |
| Open mode | `encoding="utf-8"`, `errors="surrogateescape"`, `newline=""` |
| Unit of consumption | One line **including its terminator**, as yielded by iterating the file |
| Lifetime | Opened, fully consumed, closed; never held open alongside another source |

**Relationships**: a run consumes 0..N file sources in command-line order, or exactly one standard-input
source when N = 0 (FR-002, FR-003). Sources are never deduplicated — the same name given twice is two
sources read twice (US2 scenario 3).

**Validation rules**:

- A source that cannot be opened or read (missing, permission denied, is a directory) terminates the
  run: diagnostic naming the file *and* the reason on stderr, exit 2 (FR-021). Validation is
  per-source at open time, not pre-flight across all operands — earlier sources have already been
  written to stdout when a later one fails (stated assumption; US4 scenario 4).
- No validation is applied to line *content*: undecodable bytes become lone surrogates and pass
  through (FR-007), and no line length limit exists.

**State transitions**: `unopened → open → exhausted → closed`, or `unopened → failed` (terminal,
exit 2). There is no `reopened` state and no seeking.

## Entity 2 — Redaction category

One of exactly three fixed categories. Not configurable and not extensible (Principle IV): the spec
fixes both the set and each placeholder.

| Category | Placeholder | Tally key | Requirements |
|----------|-------------|-----------|--------------|
| Email address | `[EMAIL]` | `emails` | FR-008, FR-009 |
| IPv4 address | `[IP]` | `ips` | FR-010, FR-011 |
| Payment card number | `[CARD]` | `cards` | FR-012, FR-013 |

**Representation**: the named groups `email`, `ip`, `card` of one module-level compiled pattern, in
that order. The alternation order *is* the precedence rule — email, then IPv4, then card (FR-015) —
so the order is load-bearing and must not be rearranged.

**Validation rules**:

- Email and IPv4 candidates are fully decided by the pattern.
- A card candidate is additionally validated in code: separators stripped, digit count must be 13–19
  inclusive, and the digits must pass Luhn (FR-013). A candidate failing either check is **not** a
  replacement, and the text it covered is re-examined from one character in (research R2).

**Relationships**: each category maps to exactly one placeholder and exactly one tally key; a single
replacement belongs to exactly one category, so categories never overlap in the output (FR-015).

## Entity 3 — Replacement tally

Three independent non-negative counters accumulated across the whole run.

| Aspect | Value |
|--------|-------|
| Representation | Three `int` counters (`emails`, `ips`, `cards`) |
| Initial value | `0, 0, 0` |
| Increment unit | One per *replacement performed*, not per distinct value (stated assumption; US3 scenario 3) |
| Scope | The entire run, summed across all sources (US3 scenario 4) |
| Reported as | `emails=N ips=N cards=N` on stderr, exactly once, only with `--count` (FR-017) |

**Validation rules / invariants**:

- For any run that completes, each counter equals the number of occurrences of that category's
  placeholder *added by the tool* in the output (SC-006).
- A rejected card candidate increments nothing.
- A value redacted as an email never increments `ips`, even when its domain is an IPv4 address
  (Edge Cases; research R4).

**State transitions**: `zeroed → accumulating → reported` with `--count`, or
`zeroed → accumulating → discarded` without it (FR-019) or when the run exits 2 (FR-022) — including
the closed-stdout case (research R7). Reporting happens only after stdout has been flushed (FR-018).

## Derived function signatures

Stated here because they fix the boundary between the two source modules; bodies belong to
implementation.

```python
# src/logredact/redact.py
def luhn(digits: str) -> bool: ...
def redact_line(line: str) -> tuple[str, tuple[int, int, int]]: ...
    # returns (redacted_line, (emails, ips, cards)) — pure, no I/O, terminator-preserving

# src/logredact/cli.py
def main(argv: list[str] | None = None) -> int: ...
    # returns the process exit status; writes to sys.stdout / sys.stderr
```

`redact_line` is total: every `str` input returns a `str` output of the same line count, and input
containing no candidate returns an object equal to its input (FR-007, FR-016).
