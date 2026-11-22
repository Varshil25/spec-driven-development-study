# Phase 1 Data Model: Phone Redaction and Output Folder

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**:
[research.md](./research.md)

This is a **delta** against [specs/001-logredact-cli/data-model.md](../001-logredact-cli/data-model.md),
whose rules are referenced as `001/R1.1`, `001/R3.7`, and so on. Rules introduced here are
numbered in the same scheme continuing from the entity they belong to. Any `001/` rule not
mentioned below is unchanged — that is FR-027.

The tool still has no persistent state, no storage, and no schema. "Data model" means the entities
the spec names, their form in code, and the rules attached to them.

## Entity map

| Spec entity | Code form | Module | Change |
|---|---|---|---|
| Input source | `str` path, or the stdin text stream | `__main__.py` | unchanged (`001/§1`) |
| Log line | `str`, terminator included | `redact.py` | unchanged (`001/§2`) |
| Redaction rule | Compiled `re.Pattern` + placeholder constant | `redact.py` | **extended**: a fourth rule |
| Redaction tally | `Counts` frozen dataclass | `redact.py` | **extended**: 4 × `int`, plus `__add__` |
| Output destination | the stdout wrapper, or one output file per FILE | `__main__.py` | **new** |
| Output folder | `str` path, created on demand | `__main__.py` | **new** |

Still no rule base class, no registry, no configuration object, and no new module (Principle IV).
The two new entities are a `str` and a file handle, not types.

---

## 1. Input source — unchanged

`001/R1.1`…`001/R1.4` hold exactly. In particular `001/R1.1` (duplicate paths are independent
sources, read twice) and `001/R1.3` (opened `encoding="utf-8", newline="", errors="strict"`) are
load-bearing for this feature's new rules R6.3 and R5.4 respectively.

One clarification, not a change: with `--out-dir`, an empty FILE list is rejected before any
source is opened (R6.6), so the stdin branch of `001/R1.2` is unreachable in that mode.

## 2. Log line — unchanged

`001/R2.1`…`001/R2.5` hold exactly, for both output destinations. `001/R2.4` (byte-identical
reproduction apart from replacements) and `001/R2.5` (one line resident at a time) are what R5.4
and R5.5 below inherit rather than restate.

- **R2.6** A phone number split across a line ending is not recognised, by `001/R2.2`. No new
  rule is needed; this is recorded only because the spec lists it as an edge case.

## 3. Redaction rule — a fourth member

Four instances now exist, still module-level constants rather than objects.

| Rule | Placeholder | Recognition | Validation beyond the pattern | Requirements |
|---|---|---|---|---|
| `email` | `[EMAIL]` | `[A-Za-z0-9._%+\-]+@(?:[A-Za-z0-9\-]+\.)+[A-Za-z]{2,}` with a leading class lookbehind | none | `001/FR-007`…`001/FR-009` |
| `ipv4` | `[IP]` | range-checked octet quad with mirrored boundary guards | none | `001/FR-010`…`001/FR-013` |
| **`phone`** | **`[PHONE]`** | **`\+\d{8,15}(?!\d)`** | **none** | **FR-001…FR-005** |
| `card` | `[CARD]` | `(?<!\d)(?:\d[ \-]?){12,18}\d(?!\d)` | `luhn(digits)` must hold | `001/FR-014`…`001/FR-016` |

`001/R3.1`…`001/R3.6` and `001/R3.9`…`001/R3.11` are unchanged. New and amended rules:

- **R3.1a** `[PHONE]` is a fixed literal, not configurable, like the other three (FR-001,
  Principle IV).
- **R3.12** A phone number is a `+` immediately followed by 8 to 15 decimal digits, with nothing
  between the `+` and the digits and nothing between the digits (FR-002).
- **R3.13** The `+` is **part of the match** and is consumed by the replacement, so no `+` remains
  beside the placeholder (FR-003).
- **R3.14** A candidate immediately followed by a further decimal digit does not match. A `+`
  followed by 16 or more digits is therefore left entirely alone by this rule — never partially
  replaced (FR-004). See research [D-101](./research.md#d-101-phone-recognition--d815d-no-lookbehind)
  for why backtracking cannot produce a shorter match.
- **R3.15** Nothing is required or forbidden before the `+`: the preceding character places no
  constraint on the match (FR-005). `100+14155552671` → `100[PHONE]`; in `++14155552671` the match
  starts at the second `+`, giving `+[PHONE]`.
- **R3.16** A `+` followed by fewer than 8 digits is not a phone number and is left unchanged
  (FR-005).

### Overlap and precedence — amended

`001/R3.7` (each character redacted at most once) and `001/R3.9` (placeholders are never
re-examined) hold unchanged, now over four rules (FR-006).

- **R3.8a** Email, IPv4, and phone are resolved in a **single leftmost-first alternation**, written
  in that branch order. The leftmost match wins; at an equal start position the earlier branch
  wins, giving the email → IPv4 → phone precedence of FR-006 with no arbitration code
  (research [D-102](./research.md#d-102-precedence--phone-becomes-a-third-branch-of-the-existing-pass-a-alternation)).
- **R3.10a** Cards are still resolved in a second pass over the output of the first. Phone
  therefore precedes card in FR-006's ordering as a consequence of pass order: a phone match is
  invisible to the card pass. Conversely a candidate the phone rule declines under R3.14 is
  visible to the card pass, so `+4111111111111111` → `+[CARD]`.
- **R3.17** Phone and card can never *start* at the same position — card begins with a digit,
  phone with `+` — so FR-006's phone-before-card clause is observable only as overlap, resolved by
  R3.10a.
- **R3.18** The observable consequence of email beating phone at an equal start is that
  `+12345678@b.io` is redacted once, to `[EMAIL]`: the whole address goes, and the domain is not
  left exposed as `[PHONE]@b.io` would leave it (FR-006, spec Assumptions).

## 4. Redaction tally — four totals

```python
@dataclass(frozen=True, slots=True)
class Counts:
    emails: int = 0
    ips: int = 0
    cards: int = 0
    phones: int = 0

    def __add__(self, other: "Counts") -> "Counts":
        """Field-wise sum. Used per line and per file; no __radd__, so an
        accumulation starts from an explicit Counts()."""
```

`001/R4.1`…`001/R4.3`, `001/R4.5`, and `001/R4.6` hold unchanged, now over four fields. Amended
and new:

- **R4.4a** Rendered only with `--count`, as exactly one line
  **`emails=N ips=N cards=N phones=N`** on stderr, after all stdout output — the four figures in
  that order (FR-008, FR-010). This **supersedes** `001/R4.4`'s three-figure form; it is the one
  deliberately breaking change to existing behaviour. Without `--count`, stderr stays empty on a
  successful run.
- **R4.7** `phones` counts phone replacement occurrences across all inputs of the run, repeated
  values once per occurrence, `0` when none (FR-009). `emails`, `ips`, and `cards` keep their
  existing meanings (FR-009).
- **R4.8** `phones` is appended **last** and defaults to `0`, so existing keyword construction
  such as `Counts(emails=2, ips=1, cards=2)` stays valid *and* keeps asserting the same fact
  (SC-005).
- **R4.9** With `--out-dir`, the tally is written after the `wrote N files` line, preserving
  "after all standard output" (FR-019).
- **R4.5a** Suppressed on **every** exit-2 path, not only the read-failure one: unrecognised
  option, missing `--out-dir` value, `--out-dir` with no FILE, uncreatable folder, unwritable
  output file, unreadable FILE (FR-026). A printed tally therefore always describes a complete run.

## 5. Output destination — new

Where a run's redacted lines go. Exactly one of two modes, chosen by the presence of `--out-dir`.

**Fields**

| Field | Type | Notes |
|---|---|---|
| mode | implicit | `out_dir is None` → stdout mode; otherwise folder mode |
| stdout wrapper | `io.TextIOWrapper` over `sys.stdout.buffer` | `encoding="utf-8", newline="", errors="strict"` (`001/D-008`). Created in both modes: folder mode still needs it for the `wrote N files` line. |
| output file | text file handle | One per FILE argument, opened `"w", encoding="utf-8", newline="", errors="strict"`, closed before the next FILE opens |
| `out_path` | `str` | `os.path.join(out_dir, os.path.basename(path))` |

**Rules**

- **R5.1** Without `--out-dir`, output is exactly as it is today: redacted lines to stdout, no
  `wrote N files` line, and no file created anywhere (FR-022). This is the default and it is
  unchanged.
- **R5.2** With `--out-dir DIR` and one or more FILE arguments, each FILE's redacted lines go to a
  file in DIR and **no** redacted line goes to stdout (FR-013).
- **R5.3** An output file's name is the final path component of its FILE argument —
  `os.path.basename` — so `logs/2026/app.log` → `DIR/app.log`. The input's directories are not
  reproduced inside DIR (FR-014).
- **R5.4** An output file is opened with **the same three keyword arguments as the stdout
  wrapper**. This identity *is* FR-015: same encoding, newline translation disabled, so content is
  byte-identical to what stdout would have received and line order, CRLF terminators, and a
  missing final newline all round-trip exactly (`001/R2.4`, `001/FR-004`…`001/FR-006`). Divergence
  here is the single way to break line fidelity silently.
- **R5.5** Lines stream to the output file as they are read, one resident at a time
  (`001/R2.5`), so a 1 MB line works and a 1 GB file does not grow memory (SC-007).
- **R5.6** Mode `"w"` truncates on open, so an existing file of that name in DIR has its content
  replaced entirely with no leftover trailing bytes (FR-017).
- **R5.7** Writes are **not** atomic: no temporary file, no rename. A run that fails part-way may
  leave a partially written output file; the non-zero exit status is the signal (spec
  Assumptions).
- **R5.8** Exactly one output file is open at a time, and it is closed before the next FILE is
  opened.
- **R5.9** In folder mode the **only** thing written to stdout is the single `wrote N files` line
  (FR-013, FR-018) — no per-file progress. Because no redacted data reaches stdout, a closed
  stdout cannot truncate redacted output; the existing `SIGPIPE` disposition (`001/D-010`) still
  applies to that one line, so the process terminates with status 141 and no traceback.

### `wrote N files`

- **R5.10** After every FILE has been processed successfully, exactly one line `wrote N files` is
  written to stdout and the run exits 0 (FR-018).
- **R5.11** N is **one per FILE argument processed**, incremented as each output file closes
  successfully. Two arguments sharing a final path component still give `wrote 2 files`; the same
  path twice still gives `wrote 2 files` (spec Assumptions).
- **R5.12** The noun is fixed: `wrote 1 files` for a single FILE. No pluralisation branch (spec
  Assumptions).
- **R5.13** The line is written only on the success path, after the loop completes, so no exit-2
  path can reach it (FR-026).

## 6. Output folder — new

A directory path given on the command line, created on demand, holding a run's output files.

**Fields**

| Field | Type | Notes |
|---|---|---|
| `out_dir` | `str \| None` | `None` means stdout mode. Otherwise the token that followed `--out-dir`, **verbatim** |

**Rules**

- **R6.1** The value is the immediately following command-line token, taken literally whatever its
  shape — it is never inspected for an option-like form. In `--out-dir --count`, the folder is
  named `--count` (FR-011, spec Edge Cases).
- **R6.2** `--out-dir` is accepted in any position relative to FILE arguments and `--count`
  (FR-011), and when given more than once the last value wins (FR-021).
- **R6.3** `--out-dir` as the final token, with nothing after it, is a usage error: usage message
  to stderr, nothing read, nothing on stdout, exit 2 (FR-012).
- **R6.4** `--out-dir=DIR` is **not** recognised. It falls through to the existing
  unrecognised-option path and exits 2 (`001/FR-024`, spec Assumptions).
- **R6.5** DIR is created, with any missing parent directories, before the first FILE is opened.
  An existing DIR is used as it is, and unrelated files in it are left alone (FR-016, spec
  Assumptions).
- **R6.6** `--out-dir` with no FILE argument is an error: a message stating that `--out-dir`
  requires at least one FILE, stdin **not** read, nothing on stdout, exit 2 (FR-020). Checked
  before DIR is created, so this invocation has no filesystem effect at all.
- **R6.7** A DIR that cannot be created or used as a directory — an existing regular file at that
  path, a regular file as a parent component, no permission, or the empty string — is reported by
  naming the path **as given** with the reason, no `wrote N files` line, exit 2 (FR-024).
  Detection is by exception, never a pre-flight `isdir`/`access` check (`001/D-009`).
- **R6.8** Pointing DIR at an input file's own directory makes the output file the input file.
  This is **not guarded against**: the input is overwritten while being read and the result is not
  well defined. A known hazard, specified as such (spec Assumptions, "Self-overwrite is not
  guarded"). It revises `001`'s assumption that the tool never modifies an input file.

## 7. Diagnostics and exit status

Every diagnostic keeps the existing one-line shape `logredact: {subject}: {reason}`
(`001/C-3`), so one format covers old and new failures.

| Failure | Subject named | Reason | Status | Requirement |
|---|---|---|---|---|
| Unrecognised option | the token | usage line + `unrecognized option: {token}` | 2 | `001/FR-024` |
| `--out-dir` with no value | — | usage line + `--out-dir requires a directory` | 2 | FR-012 |
| `--out-dir` with no FILE | — | `--out-dir requires at least one FILE` | 2 | FR-020 |
| DIR uncreatable | `out_dir`, as given | OS `strerror` | 2 | FR-024 |
| FILE unreadable or undecodable | the FILE path | OS `strerror`, or the decoder's message | 2 | FR-023 |
| Output file unwritable | `out_path` | OS `strerror` | 2 | FR-025 |

**Rules**

- **R7.1** The usage line is emitted for **malformed command lines only** (unrecognised option,
  missing `--out-dir` value) — not for the semantic failures below it, which are reported by their
  diagnostic alone.
- **R7.2** The usage text itself is **unchanged** and does not mention `--out-dir`
  (research [D-105](./research.md#d-105-the-usage-string-stays-byte-identical): FR-027 and SC-005
  require the existing usage-line test to pass unchanged).
- **R7.3** Input and output failures must be distinguishable, so the input is opened first and the
  output's error handling nests inside it. During the copy loop, `UnicodeDecodeError` is
  attributed to the input and `OSError` to the output
  (research [D-109](./research.md#d-109-attributing-a-failure-to-the-input-path-or-the-output-path)).
- **R7.4** Because the input is opened first, a FILE that cannot be read leaves **no** stray empty
  output file named after it.
- **R7.5** Processing stops at the first failure of any kind; no later FILE is opened
  (`001/FR-023`). Output files already written are **not** retracted, consistent with the existing
  rule that already-written stdout is not retracted (spec Assumptions).
- **R7.6** Exceptions are caught only to add path context and translate to an exit status. No bare
  `except`, no `except Exception: pass` (Principle II).

## 8. State transitions

The one state machine in the feature, held in `__main__.py`. The `parse → validate → create →
stream` ordering is research [D-106](./research.md#d-106-order-of-operations--validate-fully-then-create-the-folder-then-read).

```text
  [parsing]
      │  bad option, or --out-dir with no value
      │      → usage + diagnostic to stderr, exit 2, nothing read       (001/FR-024, FR-012)
      ▼
  [validating]
      │  --out-dir with no FILE
      │      → diagnostic to stderr, exit 2, stdin not read             (FR-020)
      ▼
  [creating DIR]  ── only in folder mode ──
      │  uncreatable
      │      → "logredact: {out_dir}: {reason}", exit 2                 (FR-024)
      ▼
            ┌──────────────── next FILE ────────────────┐
            ▼                                           │
  [streaming source] ──────────── exhausted ────────────┘
      │         │                        │
      │         │ read failure           │ output open/write failure
      │         ▼                        ▼
      │  "logredact: {path}: …"   "logredact: {out_path}: …"
      │   exit 2 (FR-023)          exit 2 (FR-025)
      │   remaining FILEs unread, no `wrote N files`, no tally (FR-026)
      │
      └── all FILEs done
             │
             ├─ folder mode: "wrote N files" → stdout                   (FR-018)
             │
             └─ then --count: one tally line → stderr                   (FR-008, FR-019)
                  else:       stderr stays empty                        (FR-010)
                                    ▼
                                 exit 0
```

Every failure state is terminal. No transition out of one reaches the `wrote N files` line or the
tally line (FR-026), which is what makes each of those lines a guarantee that the run completed.

## Engine interface

Unchanged in shape; only `Counts` widens. `redact_text` still performs no I/O and still assumes a
decoded `str`, because decoding happens where input enters the system (Constitution "Validation
boundary").

```python
def luhn(digits: str) -> bool: ...                          # unchanged

def redact_text(text: str) -> tuple[str, Counts]: ...       # Counts now has 4 fields
```

The CLI layer's internal helper changes signature to carry the fourth figure:

```python
def _copy_redacted(source, destination) -> Counts: ...      # was -> tuple[int, int, int]
```

It is private, imported by no test (tests use `redact_text`/`Counts` or a real subprocess), so the
change is contained.

## Requirement coverage map

Where each functional requirement is pinned down. The requirement → **test** map is in
[quickstart.md](./quickstart.md).

| Requirement | Rules |
|---|---|
| FR-001 | R3.1a, §3 table |
| FR-002 | R3.12 |
| FR-003 | R3.13 |
| FR-004 | R3.14 |
| FR-005 | R3.15, R3.16 |
| FR-006 | R3.8a, R3.10a, R3.17, R3.18, `001/R3.7`, `001/R3.9` |
| FR-007 | §3 table, R5.2, R5.4 |
| FR-008 | R4.4a |
| FR-009 | R4.7 |
| FR-010 | R4.4a |
| FR-011 | R6.1, R6.2 |
| FR-012 | R6.3, R7.1 |
| FR-013 | R5.2, R5.9 |
| FR-014 | R5.3 |
| FR-015 | R5.4, R5.5 |
| FR-016 | R6.5 |
| FR-017 | R5.6 |
| FR-018 | R5.10, R5.11, R5.12 |
| FR-019 | R4.9, R5.10 |
| FR-020 | R6.6 |
| FR-021 | R6.2 |
| FR-022 | R5.1 |
| FR-023 | R7.5, §7 table |
| FR-024 | R6.7 |
| FR-025 | R7.3, §7 table |
| FR-026 | R4.5a, R5.13, §8 |
| FR-027 | §1, §2 (unchanged), R5.1, R6.4, R7.2, R4.8 |
