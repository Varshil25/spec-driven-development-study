# Phase 1 Data Model: Phone Redaction and Output Folder

**Branch**: `002-phone-redaction-out-dir` | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

This document is a **delta** on [feature 001's data model](../001-logredact-cli/data-model.md).
Entities not mentioned here are unchanged. The tool still holds no persistent state and defines no
classes; "entities" are the concepts the spec names, expressed as the smallest Python values that
carry them. Recognition grammar lives in
[contracts/redaction-rules.md](./contracts/redaction-rules.md); the command surface lives in
[contracts/cli.md](./contracts/cli.md).

Two entities are amended and two are new.

## Entity 1 — Input source *(unchanged)*

Exactly as feature 001: an open text file object per `FILE` operand or standard input, opened
`encoding="utf-8"`, `errors="surrogateescape"`, `newline=""`, consumed one line *including its
terminator*, closed before the next source opens, never deduplicated.

One clarification this feature adds: a source is opened **before** its output file (Entity 4), so the
state transition `unopened → failed` leaves no output file in existence for that operand (FR-016,
research R7). With `--out-dir`, the zero-source case cannot arise: zero operands is rejected before
any source is opened (FR-018), so standard input is never a source in that mode.

## Entity 2 — Redaction category *(amended: three become four)*

One of exactly **four** fixed categories. Still not configurable and not extensible (Principle IV):
the spec fixes both the set and each placeholder.

| Category | Placeholder | Tally key | Summary field | Requirements |
|----------|-------------|-----------|---------------|--------------|
| Email address | `[EMAIL]` | `emails` | 1st | 001 FR-008, FR-009 |
| IPv4 address | `[IP]` | `ips` | 2nd | 001 FR-010, FR-011 |
| Payment card number | `[CARD]` | `cards` | 3rd | 001 FR-012, FR-013 |
| **International phone number** | **`[PHONE]`** | **`phones`** | **4th** | **FR-001, FR-002, FR-003** |

**Representation**: the named groups `email`, `ip`, `card`, `phone` of one module-level compiled
pattern, **in that order**:

```python
COMBINED = re.compile(f"(?P<email>{EMAIL})|(?P<ip>{IP})|(?P<card>{CARD})|(?P<phone>{PHONE})")
```

The alternation order *is* the precedence rule (FR-004). `email` before `phone` is **load-bearing**:
both can begin at the same `+`, and email must win (research R2). `phone`'s position relative to `ip`
and `card` is behaviourally inert — a phone candidate begins at `+`, those two begin at a digit, so
they never start at the same offset — and `phone` is appended last to leave 001's documented
email→IPv4→card order literally intact.

**Validation rules**:

- Email, IPv4 and phone candidates are decided entirely by the pattern. A phone candidate therefore
  has no rejection path: the 8–15 length rule lives in the quantifier and the "no further digit"
  rule in the trailing `(?!\d)` guard (FR-002, FR-003).
- A card candidate is still additionally validated in code (separators stripped, 13–19 digits, Luhn),
  and a rejected candidate is still not a replacement: the scan restarts one character into it. This
  rule is untouched, and `CARD`'s `(?<!\d)` lookbehind still blocks every interior digit offset, so
  no fragment of an over-long `+`-prefixed run can be redacted (research R2).

**Relationships**: each category maps to exactly one placeholder and exactly one tally key; a single
replacement belongs to exactly one category, so categories never overlap in the output. Three
cross-category outcomes are fixed by leftmost-match and are part of the contract:

| Input | Outcome | Category credited |
|-------|---------|-------------------|
| `+14155552671@example.com` | `[EMAIL]` | email — equal start offset, email listed first |
| `+378282246310005` | `[PHONE]` | phone — starts one character earlier than the card candidate |
| `+4111111111111111` | `+[CARD]` | card — 16 digits, so no phone candidate exists |

## Entity 3 — Replacement tally *(amended: three counters become four)*

| Aspect | Value |
|--------|-------|
| Representation | Four `int` counters, carried as `tuple[int, int, int, int]` ordered `(emails, ips, cards, phones)` |
| Initial value | `0, 0, 0, 0` |
| Increment unit | One per *replacement performed*, not per distinct value (US3 scenario 3) |
| Scope | The entire run, summed across all sources (US3 scenario 4) |
| Reported as | `emails=N ips=N cards=N phones=N` on stderr, exactly once, only with `--count` (FR-006) |

**Validation rules / invariants**:

- For any run that completes, each counter equals the number of occurrences of that category's
  placeholder *added by the tool* in the output — in `--out-dir` mode, across all output files
  (SC-007).
- A rejected card candidate increments nothing. A `+`-prefixed digit run outside 8–15 digits
  increments nothing (FR-003).
- A value redacted as an email never increments `ips` or `phones`, even when it begins with `+`
  (Edge Cases; research R2).
- `phones` is **appended**, not inserted: the first three fields keep their names, order and meaning,
  so a consumer parsing them positionally keeps working (FR-006).

**State transitions**: `zeroed → accumulating → reported` with `--count`, or
`zeroed → accumulating → discarded` without it or when the run exits 2 (FR-007) — including a failure
to create the output directory or write an output file. Reporting still happens only after all
redacted output has been written and stdout flushed, which in `--out-dir` mode means after the last
output file is closed *and* after the `wrote N files` line (FR-012, research R10).

## Entity 4 — Output destination *(new)*

Where the redacted stream goes. Exactly one of two modes for the whole run, fixed at parse time by
whether `--out-dir` was given.

| Aspect | Standard-output mode (default) | Output-folder mode (`--out-dir DIR`) |
|--------|-------------------------------|--------------------------------------|
| Representation | `sys.stdout`, reconfigured with the shared stream settings | One `io.TextIOWrapper` per operand, opened mode `"w"` with the *same* stream settings |
| Target | A single stream carrying every source concatenated | `os.path.join(DIR, os.path.basename(operand))` — one file per operand (FR-009) |
| Lifetime | Open for the whole run | Opened after its input opens successfully, closed before the next input opens; never two at once |
| Pre-condition | None | `DIR` created once up front via `os.makedirs(DIR, exist_ok=True)`; at least one `FILE` operand (FR-018) |
| Existing file at the target | N/A | Truncated — none of its previous content survives (FR-011) |
| On stdout | Redacted log text (001 FR-006) | Only the `wrote N files` line (FR-013) |

**Field**: `path` — the joined output path, used verbatim in any FR-017 diagnostic so the user sees
the path that failed.

**Validation rules**:

- `--out-dir` with zero operands is rejected before any directory is created or any stream touched:
  diagnostic on stderr, exit 2 (FR-018, research R8).
- `DIR` that cannot be created — including a path that already exists as a regular file — is a
  failure naming `DIR` and the reason, exit 2 (FR-017). `exist_ok=True` suppresses the collision only
  when the existing path is a directory, so "exists but is not a folder" fails by construction.
- An output file that cannot be opened, written or closed — for example its name collides with an
  existing subdirectory, or `DIR` is not writable — is a failure naming the **output path** and the
  reason, exit 2 (FR-017). An input failure names the **input path** instead (FR-015); attribution is
  by the operation that raised, never inferred (research R7).
- Operands are never written to: the only mode an operand is ever opened in is read (FR-020). The
  degenerate basenames (`""` from `logs/`, `"."` from `.`) are unreachable as successful writes
  because such an operand fails its own input `open()` first (research R5).

**State transitions** (per operand, output-folder mode):
`input opened → output opened → streaming → output closed → counted`, or
`input open failed` (terminal, exit 2, **no output file for this operand**), or
`output open/write/close failed` (terminal, exit 2). Outputs completed for earlier operands are
retained in every failure case (FR-016).

**Relationships**: N operands map to N writes but to at most N *files* — two operands sharing a
basename both write the same path, the second replacing the first, and both are counted (Entity 5).

## Entity 5 — Output file count *(new)*

| Aspect | Value |
|--------|-------|
| Representation | One `int` |
| Initial value | `0` |
| Increment unit | One per `FILE` operand whose output file was written and closed successfully — *not* per distinct output file name (stated assumption) |
| Scope | The run |
| Reported as | `wrote N files` on **stdout**, exactly once, only in output-folder mode, only on a fully successful run (FR-012) |

**Validation rules / invariants**:

- On a successful run, `N` equals the number of `FILE` operands given (SC-008).
- The word is literally `files` for every `N`, including `wrote 1 files` — not pluralised
  (Edge Cases).
- The line is written only after every output file has been closed, and the `--count` summary only
  after that line has been flushed (FR-012, research R10).
- A run that exits 2 produces no `wrote N files` line at all, even though some output files exist
  (FR-015, FR-016).
- In standard-output mode the counter is never reported; no such line is produced (US2 scenario 9).

## Derived function signatures

The boundary between the two source modules, amended. Bodies belong to implementation.

```python
# src/logredact/redact.py
def luhn(digits: str) -> bool: ...                       # unchanged
def redact_line(line: str) -> tuple[str, tuple[int, int, int, int]]: ...
    # AMENDED: returns (redacted_line, (emails, ips, cards, phones))
    # still pure, no I/O, terminator-preserving

# src/logredact/cli.py
def main(argv: list[str] | None = None) -> int: ...       # unchanged signature
    # returns the process exit status; writes to sys.stdout / sys.stderr
```

`redact_line` remains total: every `str` input returns a `str` output of the same line count, and
input containing no candidate returns an object equal to its input. The only change is the arity of
the tally — a 4-tuple ordered as the summary's fields. The ~20 unit assertions in the existing suite
that compare against 3-tuples gain a fourth element; no asserted behaviour changes (research R3).
