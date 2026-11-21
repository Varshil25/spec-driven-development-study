# Phase 1 Data Model: Log Redaction CLI

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**:
[research.md](./research.md)

This tool has no persistent state, no storage, and no schema. "Data model" here means the four
entities the spec names, the form each takes in code, and the validation rules attached to them.
Pattern derivations and the reasoning behind them live in [research.md](./research.md) and are
referenced, not repeated.

## Entity map

| Spec entity | Code form | Module |
|---|---|---|
| Input source | `str` path, or the stdin text stream | `__main__.py` |
| Log line | `str`, terminator included | `redact.py` |
| Redaction rule | Compiled `re.Pattern` + placeholder constant | `redact.py` |
| Redaction tally | `Counts` frozen dataclass (3 × `int`) | `redact.py` |

No other type is introduced. There is no rule base class, no registry, and no configuration
object (Principle IV).

---

## 1. Input source

An ordered sequence of places to read text from, derived from the command line.

**Fields**

| Field | Type | Notes |
|---|---|---|
| `path` | `str` | A FILE argument, verbatim as given. Used in diagnostics (FR-022). A bare `-` is an ordinary path, not a stdin convention (spec Assumptions). |
| (stdin) | text stream | Used only when the FILE list is empty (FR-002). Has no path; it is never named in a diagnostic because it is never reported as unreadable. |

**Rules**

- **R1.1** Ordering is argument order and is significant: output concatenates sources in that
  order (FR-003, FR-004). Duplicates are independent sources — the same path twice is read twice.
- **R1.2** A non-empty FILE list suppresses stdin entirely; stdin is not opened or read (FR-003).
- **R1.3** Each source opens as `encoding="utf-8", newline="", errors="strict"` (research D-008).
- **R1.4** A source that cannot be opened or decoded is a **read failure** — missing path,
  permission denied, directory, or undecodable bytes (FR-022). Detection is by exception
  (`OSError`, `UnicodeDecodeError`), never by a pre-flight check (research D-009).

**State transitions** — the only state machine in the feature, held in `__main__.py`:

```text
            ┌──────────── next source ────────────┐
            ▼                                     │
  [parsing] ──ok──> [streaming source] ──exhausted┘──all done──> [tally?] ──> exit 0
      │                      │                                      │
      │ bad option           │ read failure                         └─ --count: one line to stderr
      ▼                      ▼                                         else:    stderr stays empty
  usage → stderr      "logredact: path: reason" → stderr
  exit 2 (FR-024)     exit 2, remaining sources unread,
  nothing read        no tally printed (FR-023)
```

Once the failure state is entered it is terminal: no further source is opened (FR-023), and
output already written to stdout stays written (spec Assumptions — it is already-sanitised data).

## 2. Log line

The unit of redaction.

**Fields**

| Field | Type | Notes |
|---|---|---|
| text | `str` | One line including its terminator (`\n`, `\r\n`, `\r`, or none at end of input). |

**Rules**

- **R2.1** A line carries no structure the tool interprets — no timestamp, level, or field
  parsing (spec: "Carries no structure the tool depends on").
- **R2.2** Redaction never crosses a line boundary: a sensitive value split by a line ending is
  not recognised (spec Edge Cases).
- **R2.3** Lines are neither added, dropped, reordered, merged, nor split (FR-005). Exactly one
  output line per input line.
- **R2.4** Apart from the three replacements, a line is reproduced byte-identically — whitespace,
  blank lines, and the presence or absence of a trailing terminator all preserved (FR-006). The
  terminator stays attached to the line and is never rewritten (research D-008).
- **R2.5** Lines are processed and emitted one at a time; only one is resident in memory, so a
  1 MB line works and a 1 GB file does not grow memory (SC-006).

## 3. Redaction rule

A named category of sensitive value with its recognition criteria and fixed placeholder. Three
instances exist; they are module-level constants, not objects.

| Rule | Placeholder | Recognition | Validation beyond the pattern | Requirements |
|---|---|---|---|---|
| `email` | `[EMAIL]` | `[A-Za-z0-9._%+\-]+@(?:[A-Za-z0-9\-]+\.)+[A-Za-z]{2,}` | none | FR-007…FR-009 |
| `ipv4` | `[IP]` | range-checked octet quad with boundary guards (research D-002) | none — 0-255 is enforced inside the pattern | FR-010…FR-013 |
| `card` | `[CARD]` | `(?<!\d)(?:\d[ \-]?){12,18}\d(?!\d)` | `luhn(digits)` must hold, where `digits` is the match with spaces and hyphens stripped | FR-014…FR-016 |

**Rules**

- **R3.1** Placeholders are fixed literals, not configurable (FR-007/010/014, spec Assumptions).
- **R3.2** A card match is replaced **including its internal separators** by the single literal
  `[CARD]` (FR-014) — `4111 1111 1111 1111` becomes one placeholder, not four.
- **R3.3** Group separators may be single spaces or single hyphens and may be mixed within one
  number; group sizes are not validated against card-brand formats (FR-015, spec Assumptions).
- **R3.4** No issuer-prefix or BIN validation — any Luhn-valid 13-19 digit run qualifies
  (spec Assumptions). Over-redaction of Luhn-passing identifiers is accepted.
- **R3.5** Each pattern is compiled once at import, not per line (SC-006).

### Luhn validation (`luhn(digits: str) -> bool`)

Precondition: `digits` contains only `0-9`. Walking right to left, every second digit is doubled
and reduced by 9 when it exceeds 9; the number is valid when the sum is divisible by 10
(research D-006). Length is **not** checked here — the 13-19 digit bound is the pattern's job
(R3.6).

- **R3.6** Fewer than 13 or more than 19 digits is never a card, whatever Luhn says (FR-016,
  spec Edge Cases).

### Overlap and precedence

- **R3.7** Each character is redacted at most once (FR-017).
- **R3.8** Email and IPv4 are resolved in a single leftmost-first alternation, so the leftmost
  match wins and email beats IPv4 at an equal start position (FR-017, research D-004).
- **R3.9** Placeholders are never re-examined; the output of one rule cannot be altered by
  another (FR-018). Guaranteed structurally — `re.sub` does not rescan replacements, and no
  placeholder contains an `@`, a dot, or a digit.
- **R3.10** Cards are resolved in a second pass over the email/IPv4-redacted text. Where a card
  candidate overlaps an IPv4 address, this redacts both rather than letting the card consume part
  of the address; see research D-004 for the full argument and the one divergence from a literal
  single-pass reading of FR-017.
- **R3.11** A candidate that fails Luhn is left unchanged and the scan resumes one character
  later, not past the candidate (FR-016, research D-005).

## 4. Redaction tally

Three running totals over all inputs of a single run.

```python
@dataclass(frozen=True, slots=True)
class Counts:
    emails: int = 0
    ips: int = 0
    cards: int = 0
```

**Rules**

- **R4.1** One tally per run, covering every source combined — not one per file (FR-020).
- **R4.2** Each total counts **replacement occurrences**, not distinct values: the same address
  three times counts 3 (FR-020, spec Assumptions).
- **R4.3** Absent values give `0`, never a blank or omitted field (FR-020).
- **R4.4** Rendered only with `--count`, as exactly one line `emails=N ips=N cards=N` on stderr,
  after all stdout output (FR-019). Without `--count`, stderr stays empty on a successful run
  (FR-021).
- **R4.5** Suppressed entirely on the exit-2 read-failure path, so a printed tally always
  describes a complete run (FR-023, spec Assumptions).
- **R4.6** Totals accumulate as lines stream; the tally is not computed by a second pass over the
  data.

## Engine interface

The two functions the CLI layer calls, and the boundary where validation happens (Constitution
"Validation boundary" — input is validated where it enters the system, so `redact_text` may
assume a decoded `str`):

```python
def luhn(digits: str) -> bool: ...

def redact_text(text: str) -> tuple[str, Counts]: ...
```

`redact_text` takes one line (it does not require one, but R2.2 means callers pass lines) and
returns the redacted text plus the counts for *that* text. The CLI sums the per-line `Counts`
into the run tally. This keeps the engine free of I/O, which is what makes FR-005 through FR-018
unit-testable without a subprocess (Principle III; see the FR→test map in
[quickstart.md](./quickstart.md)).
