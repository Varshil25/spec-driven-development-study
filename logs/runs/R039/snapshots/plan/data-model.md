# Phase 1 Data Model: Log Data Redaction CLI

**Feature**: 001-log-data-redaction-cli | **Date**: 2026-11-21

Derived from **Key Entities** in [spec.md](./spec.md). This tool holds no persistent state and has
no storage layer; the "model" is the set of in-memory values that flow through one run. Per
Constitution Principle IV, each entity below is represented by the flattest structure that carries
its data — three of the five are plain `str`/`int` and get no type of their own.

---

## Entity overview

```text
Options ──── files: list[str], count: bool
   │
   └─> for each InputSource (stdin | one named file, in argument order)
            │
            └─> for each Line (bounded str, ≤ 1 MiB decoded)
                     │
                     ├─> RedactionRule × 3 (email, ipv4, card) ──> Match*
                     │
                     └─> (redacted str, Counts delta) ──> stdout
                                                 │
                     Counts (accumulated) ───────┴──> stderr, only if --count
```

---

## 1. Options

Parsed command line. Validated at the boundary before any input is touched
(Security Baseline, "Untrusted input").

| Field | Type | Constraint | Source |
|---|---|---|---|
| `files` | `list[str]` | 0..n; order significant; used verbatim as paths | positional argv (FR-002, FR-012) |
| `count` | `bool` | default `False` | `--count`, any position (FR-012) |

**Representation**: the `argparse.Namespace` returned by the parser. No wrapper class
(Principle IV).

**Validation rules**:

- An unrecognised option is rejected before any output: usage on stderr, exit 2 (FR-014, US4-6).
- `files` entries are *not* normalised, resolved, or containment-checked. SR-009 states these are
  paths from the invoking user's own command line with no base directory, and the tool never writes
  through them; resolving them would change which file is opened without adding a control.
- A `files` entry of `-` is a literal relative path, not a stdin alias (spec Assumptions).
- `count` affects only the summary. There is no option that disables or weakens any redaction
  category, by construction — no such flag exists (SR-003).

**State transitions**: none. `Options` is immutable after parsing.

---

## 2. InputSource

One source of lines, consumed in argument order.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | display name used **only** in diagnostics |
| `stream` | text stream | UTF-8, `errors="surrogateescape"`, `newline=""` |

**Representation**: not a class — a `(name, stream)` pair produced by a generator/context manager
that yields either stdin or each opened file in turn.

**Validation rules**:

- Files are opened read-only, mode `"r"`. No create, truncate, or append mode is ever used (SR-008).
- When `Options.files` is non-empty, stdin is never opened or read (FR-002, US2-5).
- When `Options.files` is empty, the single source is stdin, named `<stdin>`.
- A failure to open or read a file raises `OSError` (including `FileNotFoundError`,
  `PermissionError`, `IsADirectoryError`); it is caught, reported with the path, and exits 2
  (FR-013, US4-1/2/3).
- `name` is the only input-derived string permitted in any diagnostic (SR-001).

**Lifecycle**: opened lazily when reached, closed before the next source is opened. Sources after a
failing one are never opened — the run exits at the first unreadable file, keeping output already
written (spec Assumptions, "Failure timing"; US4-4).

---

## 3. Line

One unit of text read and emitted; the scope within which matches are found.

| Property | Type | Constraint |
|---|---|---|
| text | `str` | ≤ `MAX_LINE` = 1 048 576 characters of decoded content (SR-005) |

**Representation**: a plain `str`, including its terminator when one was present.

**Validation rules**:

- Content longer than `MAX_LINE` with no terminator is rejected: message naming the source, **not
  quoting the line**, exit 2 (SR-005, SR-001).
- Undecodable bytes are present as lone surrogates U+DC80–U+DCFF and re-encode to the original
  bytes (FR-017).
- A line is emitted with its terminator exactly as read; a final line without one gains none
  (FR-003, US1-6).
- Matches never span a line boundary (spec Assumptions, "Line-oriented scope").

**Invariant (SC-003)**: the output line differs from the input line only in that zero or more
`Match` spans are replaced by placeholder text. Every other character, including whitespace,
punctuation, and the terminator, is byte-identical.

---

## 4. RedactionRule

A category paired with its recognition criteria, placeholder, and precedence rank. Three instances
exist and no mechanism adds a fourth (Principle IV, SR-003).

| Rank | Category | Placeholder | Recognised by | Requirement |
|---|---|---|---|---|
| 1 | email | `[EMAIL]` | regex alternative | FR-004 |
| 2 | ipv4 | `[IP]` | regex alternative | FR-005 |
| 3 | card | `[CARD]` | digit-run scan + Luhn | FR-006, FR-007 |

**Representation**: module-level constants, not a class hierarchy — one compiled pattern holding the
email and IPv4 alternatives in rank order, one compiled `[0-9]+` pattern for digit runs, and three
placeholder string constants. The ranks are expressed structurally (alternation order; cards
searched only in gaps) rather than stored as data, because nothing reads a rank at runtime.

The exact recognition grammar for all three categories is specified in
[contracts/redaction-rules.md](./contracts/redaction-rules.md) and is not duplicated here.

**Validation rules**:

- All three rules are always active; no field, flag, or environment value can disable one (SR-003).
- Placeholders are inserted as literal strings, never as substitution templates, so `\1`, `\g<0>`,
  or `[EMAIL]` text appearing in the input cannot alter a replacement (SR-004).
- Inserted placeholder text is never re-scanned (FR-008).

---

## 5. Match

A span of a line recognised by exactly one rule.

| Field | Type | Constraint |
|---|---|---|
| `start` | `int` | 0 ≤ `start` < `end` ≤ `len(line)` |
| `end` | `int` | exclusive |
| `placeholder` | `str` | one of `[EMAIL]`, `[IP]`, `[CARD]` |

**Representation**: a `tuple[int, int, str]` in a list sorted by `start`. No dataclass
(Principle IV).

**Invariants**:

- **Non-overlapping** (FR-009): for consecutive matches, `previous.end <= next.start`.
- **Whole-value** (SR-002): the span covers the complete recognised value. No prefix or suffix of a
  recognised email, IPv4 address, or card number survives in the output.
- **Precedence** (FR-008): a span recognised by more than one rule yields exactly one match, chosen
  by rank. An email or IPv4 match suppresses any overlapping card candidate even when the card
  candidate starts earlier.
- **Leftmost-longest within a category** (FR-009): among same-category candidates at one start
  position, the longest valid one wins; candidates are taken left to right.

---

## 6. Counts

Three non-negative totals accumulated over all input.

| Field | Type | Initial | Semantics |
|---|---|---|---|
| `emails` | `int` | 0 | number of `[EMAIL]` **replacements** |
| `ips` | `int` | 0 | number of `[IP]` replacements |
| `cards` | `int` | 0 | number of `[CARD]` replacements |

**Representation**: three `int` locals, or one `dict[str, int]` keyed by category. Not a class.

**Validation rules**:

- A count is a replacement count, never a count of affected lines, files, or distinct values: the
  same email twice counts twice (FR-010, US3-3, spec Assumptions).
- Monotonically non-decreasing; incremented once per match as the output line is built.
- Rendered as exactly `emails=N ips=N cards=N` + `"\n"` — single spaces, no padding — written to
  stderr only, only with `--count`, only after stdout has been written **and flushed**
  (FR-010, US3-4).
- Never written on a failing run (FR-013, US4-5).
- Carries no input content, by construction — three integers (SR-001).

**State transitions**:

```text
zero ──(match replaced)──> incremented ... ──(stdout flushed OK, --count)──> rendered to stderr
                                        └────(any failure)──────────────────> discarded, exit 2
```

---

## Cross-entity invariants

| ID | Invariant | Requirement |
|---|---|---|
| INV-1 | Output bytes = input bytes with only `Match` spans replaced | FR-003, SC-003 |
| INV-2 | No input value appears in output except as a placeholder | SR-001, SR-002, SC-001 |
| INV-3 | Peak memory is bounded by `MAX_LINE`, independent of total input size | FR-016, SR-005, SC-007 |
| INV-4 | Nothing is created, written, or modified on disk | SR-008 |
| INV-5 | No subprocess, shell, `eval`, or deserialisation touches input | SR-004 |
| INV-6 | Exit status 0 ⟺ all input read and all output written and flushed | FR-014, SR-007, SC-006 |
| INV-7 | stderr is empty on a successful run without `--count` | FR-011 |
