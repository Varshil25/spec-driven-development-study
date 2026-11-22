# Phase 1 Data Model: Log Redaction Tool (`logredact`)

**Feature**: `001-logredact-cli` | **Date**: 2026-11-20 | **Plan**: [plan.md](./plan.md)

Nothing here is persisted: the tool is a stream filter and holds no state between lines beyond
three integers. The four entities from the specification map onto plain Python values rather than
classes, as Principle IV requires. "Representation" below is what the implementation actually
uses; no entity gets a type of its own unless the table says so.

---

## 1. Input source

A named file or standard input, supplying a sequence of text lines. Sources are consumed in
command-line order.

| Field | Representation | Notes |
|-------|----------------|-------|
| Display name | `str` | The path **exactly as given on the command line** (FR-028 requires the diagnostic to use that spelling, not a resolved or absolute path). For standard input there is no operand, and no diagnostic names it. |
| Line stream | iterator of `str` | A text stream opened with `encoding="utf-8"`, `errors="surrogateescape"`, `newline="\n"`. Each item is one line *including* its trailing `\n` when present (R-001, R-002). |

**Collection**: `list[str]` from `argparse` (`files`, `nargs="*"`). Empty list means "read
standard input" (FR-002). A list entry of `-` is an ordinary relative path (spec Assumptions).

**Lifecycle / validation rules**:

- Opened lazily, immediately before its first line is read, and closed before the next source is
  opened. A source is never opened on a help run (FR-030a).
- `OSError` on open or on read → diagnostic naming the display name, stop reading further
  sources, no tally, exit 2 (FR-028, FR-029).
- There is no decode failure state: `surrogateescape` cannot raise (R-001). "Unreadable" means
  open or read failed, never that the contents failed to decode.
- Sources are read-only; the tool never writes to a named path (spec Assumptions).

**State transitions**: `pending → open → exhausted` (normal) or `pending → failed` /
`open → failed` (FR-028). A `failed` source terminates the whole run; later `pending` sources are
never opened.

---

## 2. Redaction category

One of three recognition rules, each with a fixed placeholder. The set is closed: there is no
registration mechanism and no flag to enable or disable a category (spec Assumptions).

| Category | Named regex group | Placeholder | Tally key | Precedence at equal start |
|----------|-------------------|-------------|-----------|---------------------------|
| Email | `email` | `[EMAIL]` | `emails` | 1st |
| IPv4 | `ip` | `[IP]` | `ips` | 2nd |
| Card | `card` | `[CARD]` | `cards` | 3rd |

**Representation**: the three alternatives of one compiled pattern, plus a module-level
`dict[str, str]` mapping group name → placeholder. Precedence is encoded as the order of the
alternatives (R-003), not as a sortable attribute — Python's `re` tries alternatives left to
right at the leftmost matching position, which is FR-021.

**Validation rules** (full grammar in [contracts/redaction-patterns.md](./contracts/redaction-patterns.md)):

- Email: FR-009, as amended by research item R-000 to admit an IPv4-literal domain.
- IPv4: four octets of value 0–255, leading zeros permitted, not flanked by a digit or a dot
  (FR-012–FR-014).
- Card: 13–19 digits with optional single `space` or `-` separators, digit at each end, no
  adjacent separators, not flanked by a digit, and Luhn-valid (FR-016–FR-019a). The card category
  is the only one whose match can be **rejected after matching**, which is why the scan keeps two
  cursors (see Match below).

**Placeholders are data, not patterns**: placeholder text is appended to the output fragment list
and is never part of the subject string, so it cannot be rescanned; literal `[EMAIL]`, `[IP]`, or
`[CARD]` present in the input matches no category and passes through uncounted (FR-022).

---

## 3. Match

A span of characters on one line claimed by exactly one category, replaced by that category's
placeholder and counted once.

| Field | Representation | Notes |
|-------|----------------|-------|
| Start offset | `int` | `match.start()`, an index into the current line. |
| End offset | `int` | `match.end()` for email and IPv4. For a card it is the end of the **longest Luhn-valid** candidate at the start offset, which may be shorter than `match.end()` (FR-019). |
| Category | `str` | `match.lastgroup` — reliable because every inner group in the pattern is non-capturing. |

Matches are not materialised into a list. A match is consumed the moment it is found: the text
between the previous match and this one is appended to the fragment list, then the placeholder.
The line's result is `"".join(fragments)`.

**Invariants**:

- Spans never overlap and never nest; each character of a line belongs to at most one match
  (FR-020). Guaranteed by the copy cursor only ever moving forward to a match's end offset.
- A match never spans a line boundary, since the subject is a single line (spec Assumptions). It
  may span a bare `\r`, which is an ordinary character (FR-007) — in practice no pattern admits
  `\r`, so a `\r` breaks a candidate exactly as any other non-matching character does.
- A match never begins or ends on a space or hyphen: the card pattern requires a digit at each
  end, and the other two cannot match a separator at either edge.

**The two cursors** (the one piece of mutable state inside a line, required by FR-019a):

| Cursor | Meaning | Advance rule |
|--------|---------|--------------|
| `copy_from` | Start of input text not yet copied to the output | Set to the match's end offset only when a match is **accepted** |
| `search_from` | Where the next `search()` begins | Set to the match's end offset on acceptance; set to `match.start() + 1` when a card candidate is **rejected** by Luhn |

Because `search_from` strictly increases on every iteration, the loop terminates. Because
`copy_from` does not move on rejection, the rejected text is still copied verbatim later, and
scanning continues past it — so a failing candidate cannot hide a valid one further along the
line (FR-019a).

---

## 4. Tally

Three non-negative totals, one per category, accumulated over all input and reported only on
request.

| Field | Representation | Notes |
|-------|----------------|-------|
| `emails` / `ips` / `cards` | `int` ≥ 0 | Counts **replacements**, not distinct values: three addresses on one line contribute 3 (FR-026). |

**Representation**: `collections.Counter`. `redact_line` returns a per-line `Counter`; the caller
accumulates with `total.update(line_counts)`. Reading a never-incremented key yields `0`, which
is what FR-026 requires for an absent category.

**Validation rules**:

- Rendered as exactly `emails=N ips=N cards=N` plus a newline, to stderr (FR-023). The key order
  is fixed and is not the Counter's insertion order — the format string names the three keys
  explicitly.
- Written **only** after stdout has been fully written and flushed (FR-024).
- Written only when `--count` was passed, and never on a failed run: not on an unreadable source
  (FR-029), not on a failed write (FR-031a), not on a usage error (FR-030), and not on a help
  request (FR-030a).
- Without `--count`, a successful run writes nothing at all to stderr (FR-025).
- Equals the number of placeholders of that category present in the output, which is how SC-008
  is checked.

---

## Derived: run outcome

Not an entity in the specification, but the value `cli.main()` returns and the only thing the
caller observes besides the two streams. Enumerated here because exit status is load-bearing for
SC-009.

| Outcome | Exit status | stdout | stderr |
|---------|-------------|--------|--------|
| All sources read, all output written | 0 | Redacted stream | Tally if `--count`, else empty |
| Help requested | 0 | Usage text only | Empty |
| Source could not be opened or read | 2 | Redacted output of earlier sources | Diagnostic naming that path |
| Invalid usage | 2 | Empty | argparse usage + error |
| Write to stdout failed | 2 | Whatever reached the destination | One concise diagnostic, no traceback |

Status 1 is never produced (spec Assumptions). A truncated output stream can never exit 0
(FR-031a).
