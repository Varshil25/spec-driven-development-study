# Phase 1 Data Model: Phone Redaction and `--out-dir`

**Feature**: `002-redact-phones-out-dir` | **Date**: 2026-11-14

This document records what this feature **adds to or changes in** the model of feature 001
([`../001-redact-log-pii/data-model.md`](../001-redact-log-pii/data-model.md)). The entities it
does not mention — input source, line — are unchanged, including their state transitions.

As in 001, "entity" means a concept the design has to keep straight, not a class. Nothing here
becomes a new type: a redaction type is still a regex group name, counts are still one `dict`, and
the output destination is still a single optional string plus a `write` parameter.

---

## Entity: Redaction type — **changed** (a fourth member)

| Field | `email` | `ip` | `card` | `phone` *(new)* |
|-------|---------|------|--------|-----------------|
| Group name (regex) | `email` | `ip` | `card` | `phone` |
| Placeholder | `[EMAIL]` | `[IP]` | `[CARD]` | `[PHONE]` (FR-030) |
| Counter key | `emails` | `ips` | `cards` | `phones` (FR-037) |
| Precedence (FR-036) | 1 (first) | 2 | 3 | 4 (last) |
| Candidate shape | local part `@` domain | dotted quad | digit run, optional ` `/`-` separators | `+` then 8–15 ASCII digits (FR-031) |
| Left-hand guard | none | not preceded by a digit or digit-dot (FR-012) | not preceded by a digit (FR-017) — **and now not preceded by `+`** (FR-032a) | **none, deliberately** (FR-031a) |
| Right-hand guard | none | not followed by a digit or dot-digit (FR-012) | not followed by a digit | not followed by an ASCII digit (FR-032) |
| Post-match validation | none (FR-007a) | every octet ≤ 255 (FR-010, FR-011) | 13–19 digits **and** Luhn passes, **and** the character before the candidate is not `+` (FR-032a) | none — the pattern alone decides (R-010) |

**Validation rules**

- "Digit" in the phone rule means ASCII `0`–`9` and nothing else (FR-031). Other scripts' decimal
  digits neither extend a run nor trigger the FR-032 rejection.
- A failed candidate of any type is returned **whole and unchanged** and increments nothing. The
  phone rule has no post-match validation, so its only rejection happens in the pattern, which
  means a rejected phone candidate never becomes a partial redaction (FR-032).
- The `+` guard on the card type is a **narrowing** of the inherited rule: strictly fewer card
  matches than before, never more (FR-032a, FR-054; verified in research.md R-012).

**Precedence** is realised entirely by the order of the branches in the one compiled alternation,
so this table's "Precedence" row is the implementation, not a description of it. Only `email` and
`phone` can begin at the same offset, because `+` is in the email local-part class while `ip` and
`card` candidates begin with a digit; at that offset email wins (FR-036).

---

## Entity: Redaction counts — **changed** (a fourth counter)

| Field | Type | Initial | Notes |
|-------|------|---------|-------|
| `emails` | `int` | `0` | |
| `ips` | `int` | `0` | |
| `cards` | `int` | `0` | |
| `phones` | `int` | `0` | **New** (FR-038). |

**Rules**

- One `dict` with exactly these four keys, in this order, produced by `new_counts()` — the single
  place the key names are written (R-021). The run's totals and the summary's field order both
  derive from it.
- A counter is incremented **only** when a replacement is actually made. A rejected candidate, and
  placeholder text that was already present in the input, increment nothing (FR-038, inherited
  FR-020).
- Counts are run-local, never module state: two runs in one process cannot contaminate each other.
- Totals accumulate across every input read in the run, whichever destination the output went to,
  and are reported once (FR-037, FR-052).
- Reported only when `--count` was given, and suppressed entirely on every failure path (FR-039).

---

## Entity: Output destination — **new**

Exactly one destination is in effect for a whole run; it is chosen once, from the command line,
before any input is opened.

| Field | Type | Notes |
|-------|------|-------|
| `out_dir` | `str \| None` | The `--out-dir` value exactly as given; `None` means standard output (FR-040). |
| `write` | callable | `sys.stdout.write` for the default destination; a per-output-file writer otherwise. The only thing that differs between destinations. |

**States**

```text
standard output  — out_dir is None. Every FILE's lines go to one combined stream, as today.
                   No confirmation line is ever printed (FR-047).
output folder    — out_dir is set and at least one FILE was named. One output file per FILE
                   argument; nothing but the confirmation line reaches standard output.
invalid          — out_dir is set and no FILE was named: invalid usage, exit 2 (FR-051).
```

**Validation rules**

- `out_dir` set with an empty FILE list is rejected before anything else happens: standard input is
  not read, DIR is not created, standard output stays empty, exit status 2 (FR-051).
- DIR is created, with every missing parent, before the first FILE is opened (FR-042, FR-045). An
  existing DIR is used as it is — never emptied, and files in it this run does not write are
  untouched.
- DIR that cannot be created is a terminal failure: diagnostic naming DIR, no input read, exit 2
  (FR-049).

---

## Entity: Output file — **new**

| Field | Type | Notes |
|-------|------|-------|
| `path` | `str` | `os.path.join(out_dir, os.path.basename(FILE))` — the FILE's final path component only, its directories dropped (FR-041). |
| handle | text stream | `"w"`, UTF-8, `errors="surrogateescape"`, `newline=""` — the same contract as standard output (FR-044, R-020). |
| state | see below | |

**State transitions** (one output file per FILE argument, in command-line order)

```text
pending ──open(w)──► open ──all lines written, closed──► complete
   │                   │
   │                   ├── input read failed      ──► discarded  (FR-048 + FR-050a)
   │                   └── write or close failed  ──► discarded  (FR-050 + FR-050a)
   │
   └── the FILE could not be opened at all ──► never created (R-017)
```

- `open` → `complete` is the only transition that increments the write counter.
- `discarded` means: the handle is closed and the file is removed, so DIR holds no file under a
  legitimate name that is not a complete redaction of its input (FR-050a, SC-013a). A file of that
  name that existed before the run is gone with it and is **not** restored — `"w"` replaced it the
  moment the run opened it.
- A failed removal does not change the state: it is reported as a second diagnostic and the exit
  status stays 2.
- `never created` is the non-destructive case recorded in research.md R-017: a FILE that cannot be
  opened at all leaves any pre-existing file of its output name untouched.

**Collisions.** Two FILE arguments with the same basename resolve to the same `path`. The second
`open(…, "w")` replaces the first one's contents; both transitions to `complete` count. So the
write counter can exceed the number of files on disk, by design (spec Assumptions).

---

## Entity: Write confirmation — **new**

| Field | Type | Notes |
|-------|------|-------|
| N | `int` | The number of output files that reached `complete`, i.e. one per FILE argument processed (FR-046). |
| text | `str` | Exactly `wrote N files\n`, including `wrote 1 files` for a single file — the literal form the request specifies, never pluralised. |

**Rules**

- Written to **standard output**, once, after every FILE has been processed, and it is the only
  thing an `--out-dir` run writes to standard output (FR-046, FR-047).
- Never written on a run without `--out-dir`, and never on a run that failed (FR-047).
- Precedes the `--count` summary, which goes to standard error after standard output is flushed
  (FR-052).

---

## Run-level state

| Name | Type | Purpose |
|------|------|---------|
| `count` | `bool` | Whether `--count` was given (FR-001). |
| `out_dir` | `str \| None` | The destination (FR-040). **New.** |
| `files` | `list[str]` | FILE arguments in order; empty means read stdin — unless `out_dir` is set, which makes it invalid usage (FR-002, FR-003, FR-051). |
| counts | 4 × `int` | As above. **Was 3.** |
| `written` | `int` | Output files completed so far; becomes N in the confirmation line. **New.** |
| exit status | `int` | `0` or `2` only — never any other value (FR-053, SC-014). |

**Invariants**

- `written` only ever increments, once per FILE argument, after that FILE's output file is closed
  successfully. It is read only to format the confirmation line, so a failed run's partial value is
  never observable.
- At most one output file is open at any moment: FILE *k+1*'s sink is opened only after FILE *k*'s
  was closed or discarded. Nothing is buffered beyond one line, so memory does not grow with input
  size in either destination (SC-017).
- The run is fail-fast. The first unreadable input or unwritable output stops everything: no later
  FILE is opened, no confirmation line, no summary, exit 2 (FR-048, FR-050).
