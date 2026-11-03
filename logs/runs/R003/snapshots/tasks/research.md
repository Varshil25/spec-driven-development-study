# Phase 0 Research: Shared Expense Settle-Up

**Feature**: `001-expense-splitter` | **Date**: 2026-11-03

## Status of unknowns

The specification's clarification session (2026-11-03) settled header strictness, name ordering,
file encoding, multi-error reporting, and empty participant elements. The planning input settled the
remaining three: **Python 3.11 or newer**, **standard library only**, **pytest for tests**.

**No `NEEDS CLARIFICATION` markers remain in the Technical Context.** What follows is therefore
design research — the decisions the specification leaves to the implementer, each with the
alternatives that were considered and rejected.

---

## D1. Money representation: integer cents

**Decision**: Represent every monetary value as a Python `int` number of cents, from the moment an
amount is parsed to the moment it is formatted for printing. Format for output with integer
arithmetic — `f"{cents // 100}.{cents % 100:02d}"` — not with float formatting.

**Rationale**: FR-014 and SC-002 require that printed payments sum to exactly the total imbalance.
Integers make that a property of the arithmetic rather than a property of a rounding policy: shares,
balances, and transfers are all exact, and the only division in the design (`total // n` with
remainder) has its remainder explicitly redistributed by FR-011. There is no step at which a
fractional cent can exist, so there is no step at which one can be lost.

**Alternatives considered**:

- **`float`** — rejected outright. `0.1 + 0.2 != 0.3`; summing a thousand amounts accumulates
  representation error, and SC-002 admits no error at all.
- **`decimal.Decimal`** — rejected, though it is stdlib and exact. It would still require an
  explicit quantization policy at every division, re-introducing the rounding question integers
  avoid. It is also a worse *validator* (see D2) and a heavier object to carry through the
  pipeline. Principle IV: integers are the design with fewer moving parts that still meets the
  spec.
- **`fractions.Fraction`** — rejected: exact but needless, since the domain is quantized to cents by
  FR-003 anyway.

## D2. Amount validation: explicit regular expression, not a numeric parser

**Decision**: Accept an amount field only if, after surrounding whitespace is stripped, it matches
`^\+?\d+(?:\.\d{1,2})?$`. Convert by `int(whole) * 100 + int(frac.ljust(2, "0"))` when `frac` is
present, else `int(whole) * 100`.

**Rationale**: FR-003 states the grammar positively and FR-004 enumerates what must be rejected:
non-numeric text, negatives, more than two decimal places, currency symbols, thousands separators,
exponent form, and `inf`/`nan`. One anchored pattern rejects all eight categories as a consequence
of the same rule, so there is no list of special cases to keep in step with FR-004. The conversion
is then pure integer arithmetic (D1).

**Alternatives considered**:

- **`Decimal(field)` plus post-checks** — rejected. `Decimal` happily accepts `1e3`, `Infinity`,
  `NaN`, `-5.00`, and `1.005`, so each FR-004 category would need its own follow-up check
  (`is_finite()`, sign test, exponent test). That is more code and more ways to be incomplete than
  the single pattern.
- **`float(field)` plus post-checks** — rejected for the same reason plus D1's precision problem.
- **Hand-written character loop** — rejected: the same semantics as the regex with more lines and
  more edge cases to test.

**Decision detail (whitespace)**: surrounding whitespace in the amount field is stripped before
matching, consistent with FR-006's trimming of payer names. A spreadsheet export writing `30.00 `
is the same ordinary artefact FR-006 already tolerates for names; interior whitespace (`3 0.00`)
still fails the pattern and is rejected.

## D3. Encoding: `encoding="utf-8-sig"`, strict errors

**Decision**: `open(path, newline="", encoding="utf-8-sig")`. Catch `UnicodeDecodeError` and convert
it to the FR-002a rejection naming the path. Do not pass `errors=`.

**Rationale**: `utf-8-sig` consumes a leading BOM if present and is a plain UTF-8 decoder otherwise,
which is exactly FR-002a — one codec name covers both acceptance scenario 1.7 (BOM and non-BOM
files produce identical output) and the strict-rejection requirement, because the default
`errors="strict"` raises rather than substituting `U+FFFD`. `newline=""` is what the `csv` module
documents as required so that quoted fields containing newlines are read correctly.

**Alternatives considered**:

- **`encoding="utf-8"` plus manual `﻿` stripping** — rejected: equivalent behaviour, extra
  code, and easy to get wrong when the BOM lands inside the first header field.
- **`errors="replace"`** — rejected: FR-002a explicitly forbids substituting replacement
  characters, and it is precisely the silent-wrong-answer failure Principle II prohibits.
- **Encoding detection / `chardet`-style guessing** — rejected: a third-party dependency
  (Principle I) and forbidden by FR-002a's "MUST NOT … guess another encoding".

## D4. CSV reading: `csv.reader` with the default dialect

**Decision**: Read with `csv.reader(fh)` (default comma dialect, double-quote quoting). Report row
positions with `reader.line_num`. Treat as blank — and skip — any row that `csv.reader` yields as
`[]` or as a single field that is empty after stripping. The first non-blank row is the header; it
must equal `["payer", "amount", "description"]` by exact list comparison, with no trimming or
case-folding.

**Rationale**: The default dialect is precisely what the spec assumes ("standard quoting available
for descriptions containing commas"). `line_num` tracks physical lines, so a message points at a
real line in the user's file even when a quoted description spans lines; for a multi-line record it
names the record's last line, which is the position the user's editor will show for that record's
end. Strict header comparison is the clarified answer: `Payer,Amount,Description`,
`amount,payer,description`, and `payer,amount,description,date` are each a single unambiguous
rejection with one message to verify.

**Alternatives considered**:

- **`csv.DictReader`** — rejected: it would map fields by name, which quietly tolerates reordering
  and extra columns — the opposite of FR-002's strict rule — and it hides the row length so FR-010's
  field-count check becomes awkward.
- **`str.split(",")`** — rejected: breaks quoted descriptions containing commas, which the spec
  requires to work.
- **Treating `,,` as a blank line** — rejected: it is a three-field row whose payer is empty, so it
  belongs in the data-row error path (reported as an unknown payer) rather than being silently
  dropped. Only a genuinely empty or whitespace-only line is skipped.
- **Deciding blankness before CSV parsing (raw line inspection)** — rejected: it would mis-handle a
  blank line inside a quoted field.

## D5. Ordering: Python's default `str` comparison

**Decision**: Order names with plain `sorted(...)` / `<` on `str`, and tie-break with the name as a
sort key component. Do not import `locale`, do not call `locale.strcoll`, `casefold`, or
`unicodedata.normalize`.

**Rationale**: FR-011a demands ascending Unicode code-point order with no locale collation, no case
folding, and no accent folding, identical on every machine. CPython's `str` comparison *is*
code-point lexicographic comparison and is unaffected by `LC_ALL`/`LC_COLLATE`, so the requirement
is met by using the language default and importing nothing — `Alice` < `Bob` < `alice`, and `José`
sorts by its code points like any other name. This is what makes SC-005's "byte-identical under
different locale settings" true by construction rather than by testing.

**Alternatives considered**:

- **`locale.strxfrm` / `functools.cmp_to_key(locale.strcoll)`** — rejected: explicitly forbidden by
  FR-011a and would make output depend on the environment.
- **`key=str.casefold`** — rejected: FR-006 treats `alice` and `Alice` as different people, and
  case-folding would make the leftover-cent tie-break ambiguous between them.

## D6. Share allocation: floor division plus ordered remainder

**Decision**: `base, remainder = divmod(total_cents, n)`. Every participant is charged `base`; the
first `remainder` participants in ascending code-point name order (D5) are charged one cent more.

**Rationale**: Directly implements FR-011 with shares that sum to exactly `total_cents` by
construction: `n * base + remainder == total_cents` is `divmod`'s own invariant, so no reconciliation
pass is needed. Choosing the extra-cent recipients by name order makes the choice deterministic and
explainable to a user ("the earliest names alphabetically absorb the odd cents"), which is what
acceptance scenario 3.1 pins down: 10.00 three ways gives Alice 334, Bob 333, Carol 333 cents, and
the printed payments sum to exactly 6.67.

**Alternatives considered**:

- **`round(total / n)` per participant** — rejected: float, and the rounded shares need not sum to
  the total, which is the precise failure SC-002 forbids.
- **Largest-remainder / Hamilton apportionment** — rejected as pointless here: with an equal split
  every participant's fractional remainder is identical, so the method degenerates to an arbitrary
  tie-break and FR-011a already specifies which one to use.
- **Randomized or insertion-order allocation** — rejected: violates FR-015/SC-005 determinism.

## D7. Settlement: greedy largest-debt against largest-credit, re-selected each step

**Decision**: Hold the non-zero balances in a dict. While any balance is negative, select the
debtor minimizing `(balance, name)` (most negative first, then ascending name) and the creditor
minimizing `(-balance, name)` (largest credit first, then ascending name); emit a payment of
`min(-debt, credit)`; apply it to both balances. Repeat. Print payments in generation order.

**Rationale**: This is FR-015 transcribed, including its tie-break. Each iteration drives at least
one participant to exactly zero (the final one drives two), so at most `n - 1` payments are emitted —
FR-013 and SC-003 hold structurally rather than by assertion. Because balances sum to zero (FR-012),
a negative balance guarantees a positive one exists, so the loop cannot stall; and every emitted
amount is `min` of two positive cent counts, hence at least one cent, so no `0.00` line can appear.
The amounts emitted sum to the total positive balance, giving FR-014 for free.

Re-selecting the extremes by scanning the dict each iteration is O(n²) overall. At the 50
participants of SC-006 that is a few thousand integer comparisons — far inside the two-second
budget — so a heap is not worth its weight.

**Alternatives considered**:

- **Two `heapq` priority queues** — rejected under Principle IV: O(n log n) buys nothing at this
  scale, and the name tie-break would need negated/wrapped keys that are easy to get subtly wrong
  and harder to read against FR-015's wording.
- **Pre-sorting both sides once and walking with two pointers** — rejected: it happens to produce
  the same payments for the greedy rule, but it no longer *reads* as "re-select the largest each
  time", so FR-015 compliance would have to be argued rather than seen.
- **Provably-minimal transfer count (subset-partition search)** — rejected: NP-hard, and the spec's
  Assumptions explicitly place it out of scope in favour of this greedy rule.

## D8. Error handling: one exception type, one place that prints

**Decision**: A single `SplitterError(Exception)` carrying a finished human-readable message.
Everything that validates raises it; only `cli.main` catches it, writes `splitter: error: <message>`
to stderr, and returns exit status 1. `argparse` keeps its own behaviour for malformed command
lines, which already prints usage to stderr and exits 2.

**Rationale**: FR-019 wants exactly one message on stderr and nothing on stdout; FR-020 wants
status 1 for validation failures and 2 for command-line misuse. One exception type and one handler
make "nothing is printed to stdout on failure" a structural property — payments are formatted and
written only after all validation has returned successfully — rather than something each error path
must remember. Using `argparse`'s native exit code for misuse means FR-020's status 2 needs no
custom code at all. Per Principle II there are only two `except` clauses in the whole design,
`OSError` and `UnicodeDecodeError`, each immediately re-raised as a `SplitterError`; neither
swallows anything.

**Alternatives considered**:

- **An exception subclass per failure category** — rejected: the CLI treats them identically, so the
  hierarchy would be unused generality (Principle IV).
- **Returning `(result, error)` tuples** — rejected: it makes ignoring an error the easy path,
  which is the silent-failure mode Principle II prohibits.
- **`sys.exit(message)` at the point of detection** — rejected: it makes the computation
  untestable without a subprocess, against Principle III.

## D9. Validation order: fail fast in a fixed, documented sequence

**Decision**: Validate in exactly this order and stop at the first failure — (1) argparse surface;
(2) the participant list (empty, empty element, duplicate); (3) opening and decoding the file;
(4) the header; (5) data rows by increasing line number. Within one data row: field count, then
payer, then amount.

**Rationale**: FR-010a names the first three levels ("command line first, then the header, then data
rows by increasing line number"); the participant list is a command-line value, so it belongs with
level 1, and it must be known before any payer can be checked anyway. Within a row the order is
left-to-right by column — payer is column 1, amount is column 2 — which is the rule a user can
predict from looking at their own file. Stopping at the first problem keeps error output
deterministic (SC-004: exactly one message, concerning the earliest problem) with no
error-collection machinery.

**Alternatives considered**:

- **Collect and rank all problems** — rejected: more machinery than the spec asks for, and
  FR-010a forbids listing further problems.
- **Amount before payer within a row** — rejected arbitrarily-tied; column order is the version
  that can be explained to a user without reference to the implementation.

## D10. Packaging and import path: `pytest.ini` with `pythonpath = src`

**Decision**: No build system and no install step. Commit a `pytest.ini` containing
`[pytest]` / `pythonpath = src`. Document manual runs as
`PYTHONPATH=src python -m splitter …` from the repository root.

**Rationale**: The spec's Given Constraints fix both the invocation (`python -m splitter …`) and the
location (`src/splitter`), which means something must put `src` on the import path. `pythonpath` is
a core `pytest` ini option — no plugin, no third-party dependency — so the constitution's "tests are
discoverable by `pytest` from the repository root with no configuration beyond what is committed"
holds with a two-line file.

**Alternatives considered**:

- **`pyproject.toml` + `pip install -e .`** — rejected: it introduces `setuptools` as a build
  dependency and an install step before the tool can run, against Principle I's spirit and the
  "installs and runs anywhere `python3` exists" rationale.
- **`sys.path` manipulation in `conftest.py`** — rejected: it works, but it is hand-rolled
  machinery where a committed one-line setting does the same job, and it does nothing for manual
  command-line runs.
- **Flattening the package to the repository root** — rejected: the spec requires `src/`.

## D11. Test strategy: in-process `main()` for breadth, subprocess for the contract

**Decision**: Most CLI tests call `cli.main(argv)` in process and assert on its return value plus
`capsys`-captured streams. A small number of end-to-end tests run
`[sys.executable, "-m", "splitter", …]` via `subprocess.run` with `PYTHONPATH` pointing at `src`, to
prove the documented invocation and exit codes work as published.

**Rationale**: Principle III requires every error path to assert both message content and exit
status; in-process calls make that fast and precise for the dozen-plus rejection cases, while the
subprocess tests are what actually verify FR-001's `python -m splitter` contract and FR-020's
status codes as a user would see them. `main(argv)` returning an `int` rather than calling
`sys.exit` is what makes the in-process half possible.

**Alternatives considered**:

- **Subprocess for every case** — rejected: a process launch per assertion, for no extra coverage
  on the cases that are not about process boundaries.
- **In-process only** — rejected: it would never execute `__main__.py` or confirm the published
  command line.

---

## Consolidated decisions

| # | Area | Decision |
|---|------|----------|
| D1 | Money | Integer cents throughout; integer-arithmetic formatting |
| D2 | Amount validation | Anchored regex `^\+?\d+(?:\.\d{1,2})?$`, whitespace stripped |
| D3 | Encoding | `utf-8-sig`, strict errors, `UnicodeDecodeError` → rejection |
| D4 | CSV | `csv.reader` default dialect, `line_num` for messages, strict header equality |
| D5 | Ordering | Default `str` comparison (code point); no `locale`, no case/accent folding |
| D6 | Shares | `divmod(total, n)`; first `remainder` names in order pay one cent more |
| D7 | Settlement | Greedy max-debt × max-credit, re-selected each step, O(n²) |
| D8 | Errors | One `SplitterError`; `cli.main` prints to stderr and returns 1; argparse gives 2 |
| D9 | Order of checks | CLI → participants → open/decode → header → rows; in-row: count, payer, amount |
| D10 | Import path | `pytest.ini` with `pythonpath = src`; `PYTHONPATH=src` for manual runs |
| D11 | Tests | In-process `main(argv)` for breadth; subprocess for the published contract |
