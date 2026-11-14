# Phase 1 Data Model: Redact Personal Data From Log Files

**Feature**: `001-redact-log-pii` | **Date**: 2026-11-13

This tool is a streaming text filter with no persistence, so "data model" here means the few
in-memory structures that carry state through a run. There are four, and three of them are
immutable module-level constants. Per Principle IV, none is wrapped in a class that a plain
value would serve.

---

## Entity: Redaction type

A fixed, closed set of three. Not user-extensible (configurable placeholders and extra
identifier types are out of scope per the spec).

| Field | `email` | `ip` | `card` |
|-------|---------|------|--------|
| Group name (regex) | `email` | `ip` | `card` |
| Placeholder | `[EMAIL]` | `[IP]` | `[CARD]` |
| Counter key | `emails` | `ips` | `cards` |
| Precedence (FR-019) | 1 (first) | 2 | 3 (last) |
| Post-match validation | none (FR-007a) | every octet ≤ 255 (FR-010, FR-011) | 13–19 digits (FR-016) **and** Luhn passes (FR-014, FR-015) |

**Representation**: the alternation branch order in the single compiled pattern *is* the
precedence, and `match.lastgroup` *is* the type tag. No separate enum or registry table is
introduced — that would be an indirection layer with no requirement behind it.

**Validation rules** (from the spec, verified in `research.md` R-004):

- An **email** is `local@domain`, where `local` is one or more of `A-Za-z0-9._%+-`, and `domain`
  is either dot-separated labels of `A-Za-z0-9-` ending in a final label of ≥ 2 letters, or four
  dot-separated groups of 1–3 digits. Numeric domains are **not** range-checked (FR-007a).
  Trailing punctuation is never part of the match (FR-008).
- An **IPv4 address** is four 1–3 digit groups joined by single dots, each group 0–255 inclusive.
  Leading zeros are accepted (`010.0.0.7`). It is not recognised when adjacent to a digit, when
  preceded by digit-and-dot, or when followed by dot-and-digit (FR-012).
- A **card candidate** is a maximal run of digit groups joined by single spaces or single
  hyphens, not adjacent to another digit at either end (FR-017). Mixed separators are accepted.
  It is redacted only if, after stripping separators, it has 13–19 digits and passes Luhn;
  otherwise the whole candidate is emitted unchanged, never partially (FR-015, FR-016).

**No state transitions.** A type is a static description; it never changes during a run.

---

## Entity: Input source

An ordered sequence of inputs for one run, derived from the command line.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | The filename exactly as given on the command line — reused verbatim in the FR-025 diagnostic, never normalised or made absolute. |
| handle | text stream | UTF-8, `errors="surrogateescape"`, `newline="\n"` (R-002). |

**Rules**:

- Zero FILE arguments → exactly one source, standard input (FR-002).
- One or more FILE arguments → one source per argument, **in command-line order**, and standard
  input is not opened or read at all (FR-003). A filename repeated on the command line is a
  separate source each time and is read again (User Story 2, scenario 2).
- Sources are opened lazily, one at a time, and closed before the next is opened, so a failure on
  source *n* leaves sources *n+1…* unopened (FR-026).

**State transitions** (per source):

```
pending → open → exhausted        (normal: contributes all its lines, run continues)
pending → failed                  (open() raised OSError → diagnostic, exit 2, run stops)
open    → failed                  (read raised OSError mid-stream → diagnostic, exit 2, run stops)
open    → abandoned               (consumer closed stdout → quiet exit 0, no diagnostic)
```

`failed` and `abandoned` are terminal for the whole run, not just the source.

---

## Entity: Line

The unit of reading, matching, and writing.

| Field | Type | Notes |
|-------|------|-------|
| text | `str` | Includes its terminator when it had one; may contain lone surrogates standing for undecodable bytes (FR-005b). |

**Rules**:

- A line ends at `\n`; a bare `\r` is ordinary content inside a line (R-002).
- Each line is matched independently — **no match spans a line boundary**.
- The terminator is part of the string and is written back untouched, so a final line with no
  newline stays without one (FR-005). The patterns cannot match `\n` or `\r`, so a terminator is
  never consumed by a redaction.
- Every line read is written exactly once, in order (FR-004).

---

## Entity: Redaction counts

Three non-negative integers accumulated across every source in the run.

| Field | Type | Initial | Notes |
|-------|------|---------|-------|
| `emails` | `int` | `0` | |
| `ips` | `int` | `0` | |
| `cards` | `int` | `0` | |

**Rules**:

- A counter increments **once per replacement actually made** — not per distinct value, so the
  same address three times counts as three (FR-022).
- A candidate rejected by validation (out-of-range octet, wrong length, failed Luhn) increments
  nothing, because no replacement was made.
- Placeholder text present in the input is never matched, so it is never counted (FR-020).
- The counts are accumulated on every run; they are **reported** only when `--count` was given,
  and only when the run processed every input to the end — suppressed on the FR-026 failure path
  and on the FR-028 early-close path (FR-021).
- Reported as exactly `emails=N ips=N cards=N` on one line to stderr (see
  `contracts/cli-contract.md`).

**Representation**: a 3-field mutable counter object local to the run — a `dict` with the three
keys, or three locals threaded through. No global state (constitution: "no hidden state"), so two
runs in one process cannot contaminate each other.

---

## Run-level state

Everything that persists across the whole run, in full:

| Name | Type | Purpose |
|------|------|---------|
| `count` | `bool` | Whether `--count` was given (FR-001). |
| `files` | `list[str]` | FILE arguments in order; empty means read stdin (FR-002, FR-003). |
| counts | 3 × `int` | As above. |
| exit status | `int` | `0` or `2` only — never any other value (SC-006). |

Memory use is bounded by the longest single line, not by input size (SC-007); nothing else
accumulates.
