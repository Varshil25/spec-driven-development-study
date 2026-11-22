# Phase 1 Data Model: Phone Redaction and Output Folder

**Feature**: `002-phone-redaction-out-dir` | **Date**: 2026-11-20 | **Plan**: [plan.md](./plan.md)

There is still no persistent store and no record type. The "entities" the spec names are the
in-memory values the run carries, and this document pins down each one's representation, its
validation rules, and where it is decided — so that the implementation phase has no
representation choices left to make.

Everything here extends
[`specs/001-logredact-cli/data-model.md`](../001-logredact-cli/data-model.md); only the four
entities the spec amends or adds are described. Entities that feature 001 defined and this
feature does not touch (the source stream, the line) are unchanged.

---

## 1. Redaction category

Four categories, up from three (spec Key Entities). The category set lives in `redact.py` as two
parallel dicts keyed by regex group name, both of which gain one entry.

| Group name | Placeholder | Tally key | Recognition rule |
|---|---|---|---|
| `email` | `[EMAIL]` | `emails` | FR-009 (unchanged) |
| `ip` | `[IP]` | `ips` | FR-013, FR-014 (unchanged) |
| `card` | `[CARD]` | `cards` | FR-016 – FR-019a (unchanged) |
| `phone` | `[PHONE]` | `phones` | **new** — FR-032, FR-033, FR-033a, FR-034 |

```python
PLACEHOLDERS = {"email": "[EMAIL]", "ip": "[IP]", "card": "[CARD]", "phone": "[PHONE]"}
TALLY_KEYS   = {"email": "emails", "ip": "ips", "card": "cards", "phone": "phones"}
```

**Representation rule**: a placeholder is *data appended to the output fragment list*, never text
substituted into the subject string. This is what makes FR-037 hold by construction: `[PHONE]`
never re-enters the string being scanned, so it cannot be re-examined, and a literal `[PHONE]`
already in the input is simply unmatched text that gets copied through and is never counted.

**Ordering rule**: the four categories have a total order, and it is expressed in exactly one
place — the written order of the alternatives in the compiled pattern:

```python
PATTERN = re.compile(
    rf"(?P<email>{_EMAIL})|(?P<ip>{_IPV4})|(?P<card>{_CARD})|(?P<phone>{_PHONE})"
)
```

`email` → `ip` → `card` → `phone` is FR-036. The dicts above are lookup tables and their
insertion order is not load-bearing; the pattern's order is. Reordering the alternatives changes
behaviour and nothing else will warn you (research R-102).

**Phone validation rules** (all enforced by the pattern, none by post-validation):

| Rule | Requirement | Where |
|---|---|---|
| Starts with a literal `+` | FR-033 | `\+` |
| 8 to 15 digits, no separators | FR-033 | `[0-9]{8,15}` |
| "Digit" means `0`–`9` only | FR-033a | the explicit class, never `\d` |
| Not followed by a further digit | FR-034 | `(?![0-9])`, which fails at every backtracked length |
| No constraint on what precedes the `+` | spec Assumptions | no lookbehind |

Unlike `card`, `phone` has **no post-validation step**. `_longest_valid_card` is reached only when
`match.lastgroup == "card"`; the phone branch takes `match.end()` like `email` and `ip` do.

---

## 2. Tally

`collections.Counter`, unchanged in type, with a fourth key.

| Property | Value |
|---|---|
| Type | `collections.Counter` with `str` keys and `int` values |
| Keys | `emails`, `ips`, `cards`, `phones` |
| Lifetime | One per run, accumulated across every source read, including across operands |
| Seeding | **Never pre-seeded.** Reading an absent key yields `0`, which is FR-039's "report `0` when no phone number was replaced" |
| Per-line form | `redact_line` returns a fresh `Counter` for its own line; the run total is `total.update(line_counts)` |

**Rendered form** (FR-038) — the key order is fixed by the requirement, so the four keys are
named explicitly in the f-string rather than iterated:

```text
emails=N ips=N cards=N phones=N\n
```

**Write-time rule**: written to stderr only with `--count`, only after stdout has been flushed
successfully, and — on an `--out-dir` run — only after the summary line (FR-046, FR-024). Never
written on a failing run, whatever the failure (FR-029, FR-048, FR-050).

---

## 3. Output destination

The one genuinely new value in the run. Derived entirely from the parsed arguments before any
I/O happens.

| Field | Type | Source | Meaning |
|---|---|---|---|
| `out_dir` | `str \| None` | `args.out_dir` | `None` means stdout, the default and unchanged path (FR-052). A string names the directory from FR-040. |
| `files` | `list[str]` | `args.files` | Operands in command-line order, each kept **exactly as spelled** — never resolved, never made absolute, because FR-028's and FR-049's diagnostics must use that spelling. |

**Derived per operand**:

```python
out_path = os.path.join(out_dir, os.path.basename(file))
```

| Rule | Requirement |
|---|---|
| `os.path.basename` discards every leading directory: `logs/2026/app.log` → `app.log` | FR-041, US2.3 |
| A FILE literally named `-` has base name `-`; it is not standard input | spec edge case |
| Two operands with the same base name derive the same `out_path`; the later write replaces the earlier | FR-043, US2.10 |
| `out_path` is opened with mode `"w"`, which truncates | FR-043, US2.5 |
| Text settings are `encoding="utf-8", errors="surrogateescape", newline="\n"` — identical to stdout's, which is what makes the bytes identical | FR-044, research R-110 |

**Validity rules, in the order FR-054 fixes**:

| # | Rule | Failure | Requirement |
|---|---|---|---|
| 1 | `out_dir is not None` ⇒ `files` is non-empty | diagnostic naming the conflict, no `DIR` created, stdin untouched, exit 2 | FR-047, US4.4 |
| 2 | `DIR` exists as a directory or can be created with its parents | diagnostic naming `DIR`, exit 2 | FR-042, FR-048, US4.5, US4.6 |
| 3 | For every operand, `out_path` is not the same file as the operand | diagnostic naming that file, operand untouched, exit 2 | FR-049, FR-049a, US4.7 – US4.7c |

Rules 1–3 all complete before the first output file is opened, so a run that fails any of them
has truncated nothing (FR-054). Rule 3 is re-evaluated for each operand immediately before its
output file is opened, which catches the case where an earlier operand *created* the colliding
file (research R-107).

**File identity** is the value rule 3 compares:

| Property | Value |
|---|---|
| Representation | `tuple[int, int]` — `(st_dev, st_ino)` — or `None` |
| Produced by | `os.stat`, which follows symlinks |
| `None` means | the path names no existing file; it therefore cannot collide (FR-049a, final sentence) |
| Collision test | `a is not None and a == b` |
| Catches | differently spelled paths (US4.7a), symlinked output paths (US4.7b), hard links (FR-049a) |

---

## 4. Run summary

| Property | Value |
|---|---|
| Value | `len(files)` — one per FILE operand processed (FR-045, research R-111) |
| Rendered form | `wrote N files\n`, literal, never pluralised for N = 1 (US2.7) |
| Destination | Standard output, through the same `_write`/`_flush` helpers as redacted output |
| Written when | Only on a fully successful `--out-dir` run; never without `--out-dir`, never on a run that exits 2 (FR-045, FR-047 – FR-050, SC-017) |
| Ordering | After the last operand is streamed, before the tally; stdout is flushed between the two (FR-046) |

On a successful `--out-dir` run this line is the **only** thing on stdout (FR-045, US2.2).

---

## 5. Output failure

One exception type carries every output-side failure, extending the existing `OutputWriteError`
(research R-108).

| Field | Type | Meaning |
|---|---|---|
| `message` | `str` | The diagnostic body, already naming the destination |
| `is_stdout` | `bool` | Whether file descriptor 1 must be pointed at the null device before exit |

| Raised by | `message` | `is_stdout` | Requirement |
|---|---|---|---|
| stdout write / flush | `failed writing to standard output` | `True` | FR-031a, **text unchanged** so FR-052 holds |
| output-file open | `cannot write output file '<out_path>': <os message>` | `False` | FR-048 |
| output-file write | same | `False` | FR-048 |
| output-file close | same | `False` | FR-048 |
| `DIR` create / use | `cannot use output directory '<out_dir>': <os message>` | `False` | FR-042, FR-048 |

**Invariant**: `OutputWriteError` does **not** inherit from `OSError`. Both directions of I/O now
happen inside the per-source loop that catches `OSError` to report an unreadable FILE; keeping the
output side off that channel is what stops an output failure from being reported as "cannot read
FILE" (FR-048 vs FR-050).

---

## 6. Run state and its transitions

The run is a short sequence of states, and the table is the specification of FR-054's ordering.
No state is ever revisited.

| # | State | Side effects permitted | On failure |
|---|---|---|---|
| 1 | Parse arguments | none | usage to stderr, exit 2 (FR-030, FR-040) |
| 2 | Help requested? | none | n/a — usage to stdout, exit 0 (FR-051) |
| 3 | `--out-dir` without operands? | none | diagnostic, exit 2 (FR-047) |
| 4 | Wrap stdout | none | — |
| 5 | Create and confirm `DIR` | `DIR` and its parents created | diagnostic naming `DIR`, exit 2 (FR-048) |
| 6 | Sweep every operand for a collision | none | diagnostic naming the file, exit 2 (FR-049) |
| 7 | For each operand: open input, re-check collision, open output, stream, close | output files created and written | read failure → FR-050; output failure → FR-048; either way stop, exit 2 |
| 8 | Write summary, flush stdout | summary on stdout | stdout failure → FR-031a, exit 2 |
| 9 | Write tally if `--count` | tally on stderr | — |

States 5 and 6 run **before** any input source is opened, which is why US4.1 sees a created but
empty `DIR` and a read diagnostic. States 1–4 touch nothing, which is why FR-051 and FR-047 leave
the filesystem as it was. State 7 is the only state that can leave a partial result, and the spec
accepts that explicitly: nothing already written is deleted or rolled back.

Without `--out-dir`, states 3, 5, 6 and 8 are skipped and state 7 writes to stdout through the
existing code path — which is the whole of FR-052.
