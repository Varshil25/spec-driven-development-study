# Phase 1 Data Model: Log Redaction CLI

**Branch**: `001-logredact-cli` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

This feature has no persistent storage and no serialised data. The "data model" is the small set
of in-memory structures the stream passes through. They are kept as plain standard-library types
on purpose: Principle IV prefers a plain data structure to a custom abstraction, and nothing in
the spec requires more.

## Entities

### Input source

A place lines are read from, plus the name used when reporting a problem with it.

| Field | Type | Notes |
|---|---|---|
| `display_name` | `str` | The operand exactly as given on the command line, or `standard input`. Used only in diagnostics (FR-012, FR-018). Never normalised, resolved, or rewritten (SR-008). |
| `stream` | text stream | `TextIOWrapper` opened `encoding="utf-8", errors="surrogateescape", newline=""` (R3). Read-only (`"r"`), opened exactly as supplied (SR-008). |

**Representation**: not a class. The ordered operand list is the `list[str]` argparse produces; the
stream is a context-managed `open()` result, or `sys.stdin` reconfigured identically. The
`display_name` is the operand string itself.

**Validation rules**
- Zero operands → read standard input (FR-002); one or more → read each in operand order and never
  read standard input (FR-003).
- Operand order is honoured, never sorted or de-duplicated; a repeated operand is read again
  (Story 2 scenarios 2 and 4).
- A failure to open or read → diagnostic naming `display_name`, this source is skipped, remaining
  sources are still processed, and the run exits 2 at the end (FR-012, R10).
- Opened read-only; no operand is written, truncated, or created (FR-017, SR-007).

**State transitions**: `pending → open → exhausted` (next source, or end of run), or
`pending → failed → ` *next source* (R10). A `failed` source contributes one diagnostic and sets a
run-level failure flag that fixes the final status at 2; it does not end the run.

**Run-level state**: a single boolean "a source failed" flag plus the ordered source list. The flag
is the only state that outlives a source, and it exists because the status is decided at the end of
the run rather than at the failure (R10). An over-length line is the one failure that ends the run
immediately, so it does not use the flag (FR-018).

---

### Line

The unit of reading, redaction, and writing. Lines are processed independently of one another,
which is what lets peak memory be bounded by one line rather than by input size (FR-016).

| Field | Type | Notes |
|---|---|---|
| `text` | `str` | Content including its original terminator, or no terminator on a final unterminated line. May contain lone surrogates standing for undecodable bytes (A-4). |

**Representation**: the `str` returned by `stream.readline(MAX_LINE_CHARS + 1)`.

**Validation rules**
- `len(text) <= MAX_LINE_CHARS` (1,048,576, terminator included) — the cap is inclusive, so a line
  of exactly 1 MiB is accepted (SR-005, Story 4 scenario 7).
- `len(text) == MAX_LINE_CHARS + 1` → over-length: stop the run, diagnostic naming the source,
  exit 2, nothing of that line on stdout, no summary (FR-018, Story 4 scenarios 6 and 8).
- Terminators are never translated, added, or removed (FR-009, R3).

**State transitions**: `read → redacted → written`, or `read → rejected` (over-length; the run
ends and the line is never redacted or written).

---

### Redaction kind

One of the three fixed categories. There are exactly three, they are not configurable, and no
mechanism exists to add a fourth (A-8, A-9, Principle IV).

| Kind | Placeholder | Precedence | Tally key | Recognition |
|---|---|---|---|---|
| email | `[EMAIL]` | 1 (highest) | `emails` | FR-004, as refined by R5 (boundary guard) and R6 (domain needs at least one dot) |
| IPv4 address | `[IP]` | 2 | `ips` | FR-005 plus the FR-013 flanking guard |
| card number | `[CARD]` | 3 | `cards` | FR-006, FR-007, FR-013, as refined by R8 |

**Representation**: the three named groups of one compiled pattern, written in precedence order;
the alternation order *is* the precedence (R4). No enum, no registry, no table of rule objects —
there is nothing for such an abstraction to vary over.

See [contracts/redaction-rules.md](./contracts/redaction-rules.md) for the exact patterns and the
candidate-selection algorithm.

---

### Match

A region of one line claimed by exactly one kind, replaced in full by that kind's placeholder.

| Field | Type | Notes |
|---|---|---|
| kind | named group | `match.lastgroup` is `email`, `ip`, or `card`. |
| span | `(int, int)` | Supplied by `re`; matches within a line never overlap. |

**Validation rules**
- Replaced in full — no digits, characters, or length information from the original survive
  (SR-006). The placeholder is a fixed literal, so the original length is not even recoverable
  from the output length.
- Counted exactly once, per replacement rather than per distinct value (A-1, FR-014).
- Never re-scanned: the text of a placeholder cannot produce a further match, because `re.sub`
  builds the result from non-overlapping matches of the input (FR-014, R4).
- A `card` match region is the maximal digit/separator run; the replacer may redact several
  candidates inside it and leave the rest of the run untouched, counting one per redaction (R8).
  Every character of the run that is not part of a redacted candidate is reproduced unchanged
  (FR-008).

**Representation**: `re.Match` objects consumed inside the replacement callback and discarded. No
match list is accumulated, so memory stays bounded by the line (FR-016).

---

### Run tally

Three counters accumulated across the whole run and reported only with `--count`.

| Field | Type | Notes |
|---|---|---|
| `emails` | `int >= 0` | Replacements made, all sources (FR-010, Story 3 scenario 3) |
| `ips` | `int >= 0` | " |
| `cards` | `int >= 0` | " |

**Representation**: one mutable `dict[str, int]` (or three ints threaded through) initialised to
zero and incremented in the replacement callback.

**Validation rules**
- Reported only when `--count` is given; otherwise a successful run writes nothing to stderr
  (FR-011).
- Written to standard error, never standard output, after stdout has been written and flushed
  (FR-010, A-3, Story 3 scenario 5).
- Exactly the format `emails=N ips=N cards=N` plus a newline, with no sample values, line numbers,
  or any other content derived from the data (SR-004).
- Not written at all on a run that exits non-zero (FR-018 for the over-length case, generalised to
  every failure by R10).

**State transitions**: `zeroed → accumulating → reported` (with `--count`, status 0), or
`zeroed → accumulating → discarded` (no `--count`, or any non-zero exit).

---

## Module-level constants

| Name | Value | Source |
|---|---|---|
| `MAX_LINE_CHARS` | `1 << 20` | SR-005 — 1,048,576 characters including the terminator, inclusive |
| `MIN_CARD_DIGITS` | `13` | FR-006 |
| `MAX_CARD_DIGITS` | `19` | FR-006 |
| `EMAIL_PLACEHOLDER` / `IP_PLACEHOLDER` / `CARD_PLACEHOLDER` | `[EMAIL]` / `[IP]` / `[CARD]` | FR-004, FR-005, FR-006 |
| `EXIT_OK` / `EXIT_ERROR` | `0` / `2` | FR-015, FR-012, FR-018, A-5 |

These are constants rather than configuration: A-9 fixes them, and no option, environment
variable, or file may change them.

## What this model deliberately does not contain

Recorded so a reviewer can see the omissions are decisions, not oversights (Principle IV):

- **No match/rule class hierarchy** — three kinds, one pattern, no variation to abstract over.
- **No accumulated list of lines or matches** — would break FR-016 and SC-006.
- **No configuration object** — A-9 leaves nothing to configure.
- **No per-file tally** — FR-010 and Story 3 scenario 3 require run totals only.
- **No collected list of failed sources** — each failure is reported as it happens and only a
  boolean survives; accumulating the names would serve no requirement, since there is no end-of-run
  summary of failures (FR-012 asks for a message per file, A-5 for one status).
- **No normalised or resolved paths** — SR-008 forbids path construction; the operand string is
  used as given, for both `open()` and diagnostics.
