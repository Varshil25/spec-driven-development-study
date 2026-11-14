# Phase 1 Data Model: Phone Number Redaction and Output Folder

**Feature**: `002-phone-redaction-out-dir` | **Date**: 2026-11-14

This tool holds no persistent state and has no database. The "data model" is the small set of
values that exist for the duration of one run, and the amendments this feature makes to them.
It extends [`../001-redact-log-pii/data-model.md`](../001-redact-log-pii/data-model.md); only
the deltas are described here.

---

## Redaction type (amended: three → four)

A redaction type is still not an object. It is an ordered alternative inside one compiled
pattern, tagged by its group name, with a validator branch keyed on that tag. Adding a fourth
type adds a fourth alternative and a fourth branch — no enum, no registry, no class
(Constitution Principle IV).

| Type | Group | Recognition | Validation | Placeholder | Counter |
|------|-------|-------------|------------|-------------|---------|
| Email address | `email` | unchanged from 001 | none | `[EMAIL]` | `emails` |
| IPv4 address | `ip` | unchanged from 001 | every octet ≤ 255 | `[IP]` | `ips` |
| Payment card | `card` | unchanged from 001 | **new**: not a `+`-prefixed unbroken digit run (FR-003a); then 13–19 digits and Luhn | `[CARD]` | `cards` |
| **Phone number** | `phone` | **new**: `\+\d{8,15}(?!\d)` | none — the pattern is the whole rule | `[PHONE]` | `phones` |

**Order is the contract.** The alternatives are written `email | ip | card | phone`, and that
written order *is* FR-005's same-position precedence. Position in the line still beats order in
the pattern: a phone candidate starting one character earlier than a card candidate wins on
position alone (`+4111111111119` → `[PHONE]`).

**Validation rules**

- A candidate that fails validation is returned **whole and unchanged** and increments nothing.
  This is the pre-existing contract; FR-003 and FR-003a are both expressed through it, which is
  why "no partial redaction" needs no separate mechanism.
- FR-003 (fewer than 8 or more than 15 digits) is enforced by the pattern, not the validator:
  `{8,15}` with the trailing `(?!\d)` means an over-long run produces **no match at all**
  rather than a match that must be rejected.
- FR-003a is enforced by the validator, because it depends on the character *before* the match
  and on whether the candidate contains separators — see research.md R-002.

**State transitions**: none. Each candidate is decided independently in one left-to-right pass,
and a placeholder the tool inserts is never revisited (FR-006).

---

## Redaction counts (amended: three keys → four)

A plain `dict` with four `int` keys, created fresh per call and per run.

```python
{"emails": 0, "ips": 0, "cards": 0, "phones": 0}
```

| Property | Value |
|----------|-------|
| Keys | `emails`, `ips`, `cards`, `phones` — in this order, always all four |
| Meaning | replacements **actually made**, not candidates seen (FR-008) |
| Scope | per-line counts are returned by the matcher; run totals accumulate across every input |
| Lifetime | run-local; never module-level, so two runs in one process cannot contaminate each other |
| Reported | only on a complete run, only with `--count`, only to stderr (FR-007) |

Invariant (SC-003): each total equals the number of placeholders of that type present in the
output. `phones` is appended in **final position** so the three existing keys keep their
positions and meanings.

---

## Output destination (new)

A run has exactly one destination, chosen once from the command line and never mixed.

| Destination | Selected by | Receives redacted lines | Receives `wrote N files` |
|-------------|-------------|-------------------------|--------------------------|
| Standard output | no `--out-dir` (the default) | one combined stream, all inputs in order | never (FR-021) |
| Output folder | `--out-dir DIR` | one file per FILE argument | stdout, once, at the end (FR-014) |

**Fields**

- `path` — the directory path **exactly as written on the command line**, never normalised, so
  the FR-016 diagnostic names what the user typed.
- Existence is not a field: `os.makedirs(path, exist_ok=True)` makes "create with missing
  parents" and "use an existing one as it is" the same operation (FR-011).

**Validity**: the destination is created, or confirmed usable, **before the first FILE is read**
(FR-015). With the folder destination selected, at least one FILE is required — standard input
has no name to derive an output file from (FR-019).

**The destination folder is not inventory.** Files already in DIR that this run does not write
are left untouched; the tool knows only about the files it writes.

---

## Output file (new)

One per **FILE argument**, not per distinct path.

| Field | Value |
|-------|-------|
| Name | `os.path.basename(FILE)` — the file's own name, directories discarded (FR-010) |
| Location | directly inside DIR; input directory structure is never reproduced |
| Contents | byte-for-byte what stdout would have received for that FILE (FR-013) |
| Mode | `"w"` — an existing file of that name is replaced, never appended to (FR-012) |
| Encoding | UTF-8, `errors="surrogateescape"`, `newline=""` — identical to stdout's settings |

**Lifecycle** — the ordering here *is* FR-017a:

```text
input opens successfully  →  output file is created  →  lines are written  →  close succeeds
        │                            │                        │                    │
        │ fails                      │ fails                  │ fails              │ fails
        ▼                            ▼                        ▼                    ▼
  no file of that name        diagnostic names         partly-written file is removed,
  is left in DIR              the output path          then the diagnostic is written
  (FR-018)                    (FR-017)                 (FR-017a)
```

**Invariants**

- *Only complete files remain.* At every exit, DIR holds no stray empty file for an input that
  was never read and no truncated file for one whose write was cut short (FR-017a).
- *Earlier files survive.* An output file completed for an earlier FILE is left in place when a
  later FILE fails — **except** when the later FILE writes to that same path (two FILEs sharing
  a name). That path follows the later write's outcome, which falls out of `"w"` mode plus
  removal-on-failure with no extra rule.
- *Never its own input.* If an output path would be the same file on disk as any FILE on the
  command line, the run fails in pre-flight, having read nothing and written nothing (FR-020).

**Counting**: `N` in `wrote N files` is the number of FILE arguments processed. Two inputs
sharing a file name write the destination twice and report `wrote 2 files`; the same input named
twice counts twice. The number is therefore a function of the command line alone (FR-014).

---

## What did not change

Input sources and their order, the per-line streaming discipline (nothing accumulated, memory
flat with respect to input size), the input encoding contract, the `{0, 2}` exit-status set, and
the quiet exit when the output consumer closes early — all exactly as 001 defines them
(FR-023).
