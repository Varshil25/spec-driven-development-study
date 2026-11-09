# Phase 1 Data Model: Phone Redaction and Output Folder

**Branch**: `002-phone-redaction-out-dir` | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

This feature still has no persistent storage and no serialised data; the "data model" remains the
small set of in-memory structures the stream passes through, as plain standard-library types
(Principle IV).

This document is an **amendment** to
[001's data-model.md](../001-logredact-cli/data-model.md). Only what changes is described. Entities
not named here — **Input source**, **Line**, **Match** — are unchanged, including their fields,
validation rules and state transitions.

## Amended entities

### Redaction kind

A fourth kind is added. The entity is still not a class, not an enum and not a table: a kind is a
named group in one compiled pattern plus a branch in the replacer (R16).

| Kind | Recognition | Placeholder | Rank |
|---|---|---|---|
| email | `_EMAIL` (unchanged) | `[EMAIL]` | 1 |
| IPv4 address | `_IPV4` (unchanged) | `[IP]` | 2 |
| **phone number** | **`_PHONE` = `\+[0-9]{8,15}(?![0-9])`** | **`[PHONE]`** | **3** |
| card number | `_CARD_RUN` + candidate scan (unchanged) | `[CARD]` | 4 |

**Representation**: `PATTERN` gains a third named alternative, written between `ip` and `card` so
the source order is FR-021's order:

```python
PATTERN = re.compile(
    "(?P<email>" + _EMAIL + ")|(?P<ip>" + _IPV4 + ")|"
    "(?P<phone>" + _PHONE + ")|(?P<card>" + _CARD_RUN + ")"
)
```

`PHONE_PLACEHOLDER = "[PHONE]"` joins the module-level constants beside the existing three. The
digit bounds `8` and `15` are inline in the pattern, like the `_OCTET` ranges and unlike
`MIN_CARD_DIGITS`/`MAX_CARD_DIGITS`, which exist only because the candidate scan reads them at
runtime. Nothing here is configurable: A-23 leaves nothing to configure, so no option, environment
variable or file can change any value above (SR-016).

**Validation rules**
- A phone number is a literal `+` followed by 8 to 15 decimal digits, bounds inclusive, with no
  separator inside the run; the `+` is part of the match and is replaced with it (FR-019).
- A candidate must not be followed by a decimal digit, so a `+` with 16 or more digits contains no
  phone number and no leading part of it is replaced (FR-020).
- Precedence is email, IPv4, phone, card; an overlapping region is redacted once and counted once
  under the winning kind, and a placeholder is never re-scanned (FR-021). Delivered by `re.sub`'s
  leftmost-match rule plus the written alternation order — see [R16](./research.md) for which
  relation each of the two mechanisms actually decides.
- Nothing constrains what precedes the `+` (A-14), so `99+14155552671` → `99[PHONE]`.

**State transitions**: none. Recognition is stateless, as before.

### Run tally

Four non-negative integers instead of three.

| Field | Type | Notes |
|---|---|---|
| `emails` | `int` | unchanged |
| `ips` | `int` | unchanged |
| `cards` | `int` | unchanged |
| **`phones`** | `int` | one increment per phone replacement (FR-022) |

**Representation**: still one mutable `dict[str, int]`, created once per run in `_run` and threaded
into `redact_line`, incremented by the replacer. Field order in the dict is irrelevant; the
reported order is fixed by the format string.

**Validation rules**
- Accumulated across every source in the run; never per file (FR-022, A-24).
- Reported as `emails=N ips=N cards=N phones=N` — the new field is **appended**, not inserted in
  precedence order, so a caller parsing the first three fields is affected as little as possible
  (A-15). Note that the report order therefore deliberately differs from the precedence order.
- Written only when `--count` is given **and** the run exits 0 (unchanged from FR-010).
- Contains nothing but the four integers: no sample value, line number or file name (SR-014).

## New entities

### Output destination

Where redacted lines go for one source. Introduced because there are now two possibilities, and the
line loop must be told which.

| Field | Type | Notes |
|---|---|---|
| `handle` | text stream | `sys.stdout` (default, unchanged) or a `TextIOWrapper` over a file in DIR |

**Representation**: not a class and not a flag inspected inside the line loop. `_redact_stream`
already takes its destination as its `out` parameter; the operand loop passes either `sys.stdout`
or the per-operand output handle. That parameter *is* the entity, which is why the feature adds no
abstraction for it (Principle IV).

**Validation rules**
- With `--out-dir`, no redacted line may reach standard output; standard output carries only the
  `wrote N files` line (FR-024, FR-027).
- Without `--out-dir`, the destination is standard output for every source, exactly as today
  (FR-035).
- Both destinations use the same `STREAM_SETTINGS`
  (`encoding="utf-8", errors="surrogateescape", newline=""`), so the byte-for-byte and line
  terminator guarantees of FR-009 and A-4 hold identically for a file in DIR ([R20](./research.md)).
- Written as the input is read, one line at a time, with one output handle open at a time, so peak
  memory stays bounded by one line however many operands there are (FR-034).

**State transitions**: `absent → open → closed` per operand. `closed` is what makes the operand
countable: a flush or close failure moves it to `failed` instead (FR-030, [R22](./research.md)).

### Output folder

The directory named by `--out-dir`, and the only place besides standard output that redacted data is
written (SR-013).

| Field | Type | Notes |
|---|---|---|
| `path` | `str` or `None` | The option's value exactly as given on the command line; `None` when the option is absent. Used verbatim in diagnostics (FR-029, SR-017). |

**Representation**: the string argparse produced. Not resolved, not normalised, not made absolute —
the same discipline SR-008 already applies to operands.

**Validation rules**
- Supplied at most once; a second occurrence is a usage error ([R18](./research.md), FR-023).
- Requires at least one FILE operand; otherwise a usage error with nothing read, nothing written and
  DIR not created (FR-031, A-16).
- Created if absent, together with every missing parent, each directory owner-accessible only
  (`0o700` at creation, never relaxed afterwards) (FR-025, SR-011, [R19](./research.md)).
- Used as it is if it already exists as a directory; no file in it is removed or altered unless an
  operand names it (FR-025).
- If it cannot be created, or exists and is not a directory, the run reports it naming DIR, reads no
  operand, writes nothing to standard output, and exits 2 (FR-029).

**State transitions**: `named → ready` (existing or created) or `named → rejected` (FR-029, ends the
run before any operand is read).

### Output file

One file per FILE operand inside DIR.

| Field | Type | Notes |
|---|---|---|
| `path` | `str` | `os.path.join(DIR, os.path.basename(operand))` — DIR plus the operand's final path component and nothing else (FR-024, SR-010) |
| `handle` | text stream | `open(fd, "w", **STREAM_SETTINGS)` over a descriptor from `os.open(path, O_WRONLY\|O_CREAT\|O_TRUNC\|O_NOFOLLOW, 0o600)` |

**Validation rules**
- The name is the operand's final path component only; no other part of any operand, and no input
  data, contributes to the path (FR-024, SR-010, [R26](./research.md)).
- An existing file of that name is replaced in full, with no remnant of its previous content
  (FR-026, delivered by `O_TRUNC`).
- A file the tool creates is owner-read/write only (`0o600` at creation); a file that already exists
  keeps the permissions its owner chose and is neither widened nor narrowed (SR-011,
  [R20](./research.md)).
- A symbolic link at the output path is refused rather than followed, including a dangling one
  (SR-010, delivered by `O_NOFOLLOW`).
- If the path names the same file as the operand being read — by path, hard link or symlink — the
  write is refused before any truncation could occur, the operand is left unmodified, the failure is
  reported, and the remaining operands are still processed (FR-036, SR-012, FR-017,
  [R21](./research.md)).
- Any failure to open, write, flush or close is reported naming the output path; the remaining
  operands are still processed and the run exits 2 (FR-030).

**State transitions**: `path computed → refused` (collision with the operand, or open failure), or
`path computed → open → written → closed`. Only `closed` after a complete read increments the write
tally.

### Write tally

| Field | Type | Notes |
|---|---|---|
| `written` | `int` | Number of operand outputs written in full during the run |

**Representation**: one `int` local to `_run`, beside the existing `failed` flag. Not a list of
paths, not a set: A-18 defines N as operand outputs written, not distinct files remaining, so two
operands sharing a final path component report `2`.

**Validation rules**
- Incremented when an operand's input reached end-of-file with no read error **and** its output
  handle closed with no error ([R22](./research.md)).
- Reported as `wrote N files` on standard output, once, when every operand has been processed —
  including a run where some operand failed (A-17, FR-027, FR-028). Not pluralised: one file reports
  `wrote 1 files`.
- Not reported when the run stopped before processing every operand: an over-length line (FR-033), a
  rejected argument (SR-016), a DIR that could not be created (FR-029), or `--out-dir` with no
  operand (FR-031).
- Contains only the fixed literals and the decimal count — no file name, no sample value (SR-014).

## Run-level state, complete

Everything that outlives a single source, in one place:

| State | Type | Lifetime | Why it exists |
|---|---|---|---|
| tally | `dict[str, int]`, 4 keys | whole run | FR-022 totals are per run (A-24) |
| `failed` | `bool` | whole run | status decided at the end of the run ([R10](../001-logredact-cli/research.md), A-5) |
| `written` | `int` | whole run | FR-027's N |
| output folder path | `str` or `None` | whole run | FR-023; `None` means stdout |

No other state is added. There is no per-file record, no list of written paths, and no summary
object: each of the four items above is read by exactly one line of reporting code at the end of the
run.
