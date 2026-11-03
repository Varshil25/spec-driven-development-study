# Tasks: Shared Expense Settle-Up

**Input**: Design documents from `/specs/001-expense-splitter/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, contracts/python-api.md, quickstart.md

**Tests**: Test tasks **are** included and are **mandatory** here — not because of a default, but
because Constitution v1.0.0 Principle III ("Every Requirement Is Testable") requires every
functional requirement to map to at least one automated `pytest` test that names the requirement,
and requires each error path to have its own test asserting both message content and exit status.
plan.md carries the requirement → test-file traceability table that these tasks expand.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and
demonstrated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are given in every task

## Path Conventions

Single project, repository root `/root/sdd-study/runs/R003`:

- Source: `src/splitter/`
- Tests: `tests/` (flat, named by subject — no `contract/`, `integration/`, `unit/` split)
- Config: `pytest.ini` at the repository root

## Non-negotiable invariants for every implementation task

These come from the constitution, research.md, and the contracts. Any task that writes code under
`src/` must hold them:

- **Integer cents only.** Never `float`, never `decimal.Decimal`, never `fractions.Fraction` in any
  monetary path, including output formatting (research D1).
- **Standard library only at runtime.** Permitted runtime imports across the whole package:
  `argparse`, `csv`, `dataclasses`, `re`, `sys`. Nothing else. `pytest` is test-only
  (Constitution I).
- **No `locale`, no `casefold`, no `unicodedata.normalize`.** All name ordering is plain `str`
  comparison / `sorted()`, which is ascending Unicode code-point order (FR-011a, research D5).
- **Exactly two `except` clauses in the whole package**: `OSError` and `UnicodeDecodeError`, each
  immediately converted to a `SplitterError`. No bare `except:`, no `except Exception: pass`
  (Constitution II, research D8).
- **Nothing is written to disk.** One read-only `open()`; no temp files, caches, or config files
  (FR-021, SC-008).
- **No speculative generality.** No extra options, no config surface, no abstraction layers,
  no second way to do anything (Constitution IV).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the layout and the single configuration file the suite needs

- [ ] T001 Create the directory skeleton at the repository root: `src/splitter/` and `tests/` (no files yet beyond what T002–T003 add)
- [ ] T002 [P] Create `pytest.ini` at the repository root containing exactly a `[pytest]` section with `pythonpath = src` — a core pytest ini option, no plugins (research D10); this is what lets `pytest` with no arguments import `splitter` from the repository root with no install step
- [ ] T003 [P] Create `src/splitter/__init__.py` as an empty package marker — no logic, no imports, no `__all__` (plan.md Project Structure)

**Checkpoint**: `pytest` runs from the repository root and collects zero tests without error.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The exception type, the two data carriers, and the test fixture that every user story
builds on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Create `src/splitter/errors.py` defining `class SplitterError(Exception)` with the docstring `"""An input or validation failure whose message is ready to show the user."""` — the single exception type for every exit-1 rejection, carrying a finished message with **no** `splitter: error: ` prefix (`cli.main` adds that). No subclasses, no extra attributes, no error codes (contracts/python-api.md `splitter.errors`, research D8)
- [ ] T005 [P] Create `src/splitter/expenses.py` with the module-level constant `HEADER: tuple[str, str, str] = ("payer", "amount", "description")` and a frozen dataclass `Expense` with exactly these fields: `payer: str` (trimmed; a known participant), `amount_cents: int` (constraint: `>= 0`), `line: int` (1-based physical line in the file, used only for error messages). Declare with `@dataclass(frozen=True)`. The description column is deliberately **not** a field — FR-018 makes it computationally inert, so it is read only to satisfy the three-field count check and then discarded (data-model.md Expense)
- [ ] T006 [P] Create `src/splitter/settle.py` with a frozen dataclass `Payment` with exactly these fields: `payer: str` (had a negative balance), `payee: str` (had a positive balance), `amount_cents: int` (constraint: `>= 1`, so a `0.00` line can never be printed). Declare with `@dataclass(frozen=True)` (data-model.md Payment, FR-013)
- [ ] T007 [P] Create `tests/conftest.py` with two fixtures and nothing else: (a) a `write_csv` fixture built on pytest's `tmp_path` that writes given text to a temp file with a caller-chosen encoding (default `utf-8`) and returns its path as `str`, so tests can write raw bytes for the BOM and invalid-UTF-8 cases; (b) a `run_subprocess` helper that invokes `[sys.executable, "-m", "splitter", *args]` via `subprocess.run(..., capture_output=True, text=True)` with `PYTHONPATH` set to the repository-root `src` directory, returning the `CompletedProcess` (research D11, plan.md tests/conftest.py)

**Checkpoint**: Foundation ready — `from splitter.errors import SplitterError`, `from splitter.expenses import Expense, HEADER`, and `from splitter.settle import Payment` all import cleanly under `pytest`.

---

## Phase 3: User Story 1 - Settle up after a shared trip (Priority: P1) 🎯 MVP

**Goal**: A valid expenses CSV plus a participant list produces the correct, deterministic
`PAYER pays PAYEE AMOUNT` lines on stdout and exit status 0 — the whole purpose of the feature.

**Independent Test**: Write a CSV with a header row and the single row `Alice,30.00,Hotel`, run
`PYTHONPATH=src python -m splitter FILE --participants "Alice,Bob"`, and confirm stdout is exactly
`Bob pays Alice 15.00` and the exit status is 0. Then confirm the already-settled case prints
nothing and still exits 0. Requires nothing from US2 or US3.

**Scope note**: This phase implements the **happy path** of every function. It raises
`SplitterError` only where validation is structurally unavoidable (a payer must be looked up, an
amount must be parsed); the exact message catalogue, the stderr/exit-1 discipline, and the
fail-fast ordering are US2's phase. US1 is demonstrable with valid input alone.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST and confirm they FAIL before implementing T012–T020.** Every test
> name or its comment must cite the requirement id it covers (Constitution III).

- [ ] T008 [P] [US1] Create `tests/test_settle.py` covering the pure settlement functions: FR-011/FR-011a share allocation (`divmod(total_cents, n)`; the first `remainder` participants in ascending code-point name order are charged one cent more — assert `sum(shares.values()) == total_cents` exactly, and assert the specific allocation for `total_cents=1000, participants=["Alice","Bob","Carol"]` is `{"Alice": 334, "Bob": 333, "Carol": 333}`); FR-012 balances (`paid - share`, participants absent from every row included with `paid == 0`, `sum(balances.values()) == 0` exactly); FR-013/FR-014/FR-015 settlement (greedy largest-debt against largest-credit re-selected each step, ties in ascending name order, `len(payments) <= len(balances) - 1`, every `amount_cents >= 1`, printed total equals the sum of positive balances, identical input gives identical output). Include the worked example from data-model.md: balances `{"Alice": 666, "Bob": -333, "Carol": -333}` → `[Payment("Bob","Alice",333), Payment("Carol","Alice",333)]` in that order
- [ ] T009 [P] [US1] Create `tests/test_expenses.py` covering valid parsing: FR-003 accepted amount forms `30`, `30.5`, `30.00`, `0`, `0.00`, `+30` and their exact cent values (3000, 3050, 3000, 0, 0, 3000), plus surrounding whitespace stripped (`" 30.00 "` → 3000, research D2); FR-005 an amount of exactly zero is accepted and contributes nothing; FR-002 the header must equal `("payer","amount","description")` by exact comparison and a conforming file parses; FR-002a a file beginning with a UTF-8 byte-order mark parses identically to one without; blank and whitespace-only rows are skipped wherever they appear, including before the header, while a row of `,,` is **not** blank (it is a three-field row with an empty payer); FR-006 a payer is matched exactly after trimming and case-sensitively (` Alice ` is `Alice`); FR-010 `Expense.line` is the 1-based physical line number; a quoted description containing a comma still parses as three fields
- [ ] T010 [P] [US1] Create `tests/test_cli_output.py` covering the end-to-end happy path: SC-001/FR-016 the reference case prints exactly `Bob pays Alice 15.00\n`; FR-016 the amount always has exactly two decimal places with no currency symbol, thousands separator, or sign, and every line ends with `\n` including the last; FR-017 when every net balance is already zero — including a file with a header and no data rows — stdout is empty and the status is 0; acceptance 1.4 a participant in no expense row is still charged a share and appears as a payer; acceptance 1.6 a row with amount `0.00` gives the same result as if the row were absent; acceptance 1.5/FR-018 two files differing only in description text print identical output; acceptance 1.7 BOM and non-BOM files print identical output; the group-of-one edge case prints nothing; FR-021/SC-008 the expenses file's bytes are identical before and after a run and no other file is created or deleted in `tmp_path`
- [ ] T011 [P] [US1] Create `tests/test_cli_invocation.py` covering the accepted command-line shape only (exit-2 misuse is T023): FR-001 one positional path plus required `--participants`, asserting `cli.main([path, "--participants", "Alice,Bob"]) == 0` in process; and one subprocess test via the `run_subprocess` fixture proving the published invocation `python -m splitter EXPENSES.csv --participants NAMES` works with `returncode == 0` and the expected stdout (research D11, contracts/cli.md Invocation)

### Implementation for User Story 1

- [ ] T012 [P] [US1] Implement `parse_amount(value: str, *, path: str, line: int) -> int` in `src/splitter/expenses.py`: strip surrounding whitespace, match the anchored pattern `^\+?\d+(?:\.\d{1,2})?$` compiled once at module level, and convert by pure integer arithmetic — `int(whole) * 100 + int(frac.ljust(2, "0"))` when a fractional part is present, else `int(whole) * 100`. Raise `SplitterError` on no match (message text is pinned in T027). No `float`, no `Decimal` (research D2, FR-003, FR-004)
- [ ] T013 [US1] Implement `read_expenses(path: str, participants: Sequence[str]) -> list[Expense]` in `src/splitter/expenses.py` (depends on T012): open with `open(path, newline="", encoding="utf-8-sig")` — `newline=""` is required by the `csv` module, `utf-8-sig` consumes a leading BOM and is otherwise a strict UTF-8 decoder (research D3, D4). Read with `csv.reader(fh)` using the default comma dialect and double-quote quoting. Skip as blank any row the reader yields as `[]` or as a single field that is empty after stripping, wherever it appears including before the header. Require the first non-blank row to equal `list(HEADER)` by exact list comparison — no trimming, no case-folding. For each subsequent non-blank row, validate in this fixed order: (1) field count is exactly 3, (2) `row[0].strip()` is one of `participants`, (3) `parse_amount(row[1], ...)`. Discard `row[2]`. Record `reader.line_num` as `Expense.line` (for a multi-line quoted record this is the record's last physical line). Return expenses in file order, stopping at the first problem (FR-002, FR-002a, FR-006, FR-009, FR-010, FR-010a)
- [ ] T014 [P] [US1] Implement `compute_shares(participants: Sequence[str], total_cents: int) -> dict[str, int]` in `src/splitter/settle.py`: `base, remainder = divmod(total_cents, len(participants))`; charge `base + 1` to the first `remainder` names in `sorted(participants)` (plain `str` comparison = ascending code-point order) and `base` to the rest. Postcondition: `sum(result.values()) == total_cents` exactly, which is `divmod`'s own invariant — no reconciliation pass (FR-011, FR-011a, research D6)
- [ ] T015 [US1] Implement `compute_balances(participants: Sequence[str], expenses: Sequence[Expense]) -> dict[str, int]` in `src/splitter/settle.py` (same file as T014, so sequential): sum each participant's `amount_cents` across `expenses` (0 for a participant appearing in no row), call `compute_shares` with the total, and return `paid[name] - share[name]` for every participant. Postcondition: `sum(result.values()) == 0` exactly (FR-012)
- [ ] T016 [US1] Implement `settle(balances: Mapping[str, int]) -> list[Payment]` in `src/splitter/settle.py` (same file as T014–T015): copy the non-zero balances into a dict; while any balance is negative, pick the debtor minimising `(remaining[name], name)` and the creditor minimising `(-remaining[name], name)`, emit `Payment(debtor, creditor, min(-remaining[debtor], remaining[creditor]))`, and apply the amount to both balances. Return payments in generation order — that order is part of the output contract. Pure function: no I/O, no exceptions raised, no global state. Use the plain O(n²) re-scan, **not** `heapq` and **not** a pre-sorted two-pointer walk, so the code reads as FR-015's wording (FR-013, FR-014, FR-015, research D7)
- [ ] T017 [P] [US1] Implement `parse_participants(raw: str) -> list[str]` in `src/splitter/cli.py`: `raw.split(",")`, strip each element, return the names in command-line order (not sorted — sorting happens only where ordering matters). Happy path only; the three rejections are T024 (FR-006, contracts/python-api.md)
- [ ] T018 [US1] Implement `format_payment(payment: Payment) -> str` in `src/splitter/cli.py` (same file as T017): render `f"{payment.payer} pays {payment.payee} {cents // 100}.{cents % 100:02d}"` — single spaces, the literal word `pays`, exactly two decimal places by integer arithmetic, never float formatting (FR-016, research D1)
- [ ] T019 [US1] Implement `main(argv: Sequence[str] | None = None) -> int` in `src/splitter/cli.py` (same file as T017–T018): build an `argparse.ArgumentParser(prog="splitter")` with one positional path argument and a required `--participants` option, parse `argv` (defaulting to `sys.argv[1:]`), then run the pipeline `parse_participants → read_expenses → compute_balances → settle`, print `format_payment(p)` for each payment to stdout, and return 0. Formatting and writing happen **only after** the whole pipeline has succeeded, so stdout is structurally untouched on failure. Return an `int` rather than calling `sys.exit`, which is what lets the CLI be tested in process (FR-001, FR-016, FR-017, FR-019, research D8, D11)
- [ ] T020 [US1] Create `src/splitter/__main__.py` containing only the import of `main` from `splitter.cli` and `raise SystemExit(main())` — nothing else; this module exists so `python -m splitter` works as the spec's Given Constraints require (contracts/python-api.md `splitter.__main__`)
- [ ] T021 [US1] Run `pytest tests/test_settle.py tests/test_expenses.py tests/test_cli_output.py tests/test_cli_invocation.py` from the repository root and confirm all US1 tests now pass; then run the quickstart.md V1, V2, V3, V5, V6 checks by hand and confirm each matches its stated expectation

**Checkpoint**: User Story 1 is fully functional and testable independently — the MVP. A group with a
valid CSV can settle up.

---

## Phase 4: User Story 2 - Be told clearly when the input is wrong (Priority: P2)

**Goal**: Every malformed input produces exactly one message on stderr that names the problem (and,
where it lies in the file, the line number and offending value), writes nothing to stdout, and exits
non-zero — 1 for input/validation failures, 2 for command-line misuse.

**Independent Test**: Run the tool once per malformed-input case from quickstart.md V8 and confirm
for each that stderr carries the exact message from the contracts/cli.md catalogue, stdout is empty,
and the exit status is 1 (or 2 for the three command-line cases). Then run a file with two malformed
rows and confirm only the earlier row is reported.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST and confirm they FAIL before implementing T024–T029.** Per
> Constitution III each error path gets its own test asserting **both** message content and exit
> status.

- [ ] T022 [P] [US2] Create `tests/test_cli_errors.py` with one test per row of the contracts/cli.md exit-1 message catalogue, each asserting the exact message on stderr (prefixed `splitter: error: `), **empty stdout**, and exit status 1. The ten messages, verbatim: `--participants requires at least one participant name` (FR-007); `--participants contains an empty participant name` (FR-007, for both `Alice,,Bob` and `Alice,Bob,`); `--participants contains duplicate participant name '{name}'` (FR-008); `cannot read expenses file '{path}': {reason}` (FR-009); `cannot decode expenses file '{path}' as UTF-8` (FR-002a); `{path}: missing header row; expected 'payer,amount,description'` (FR-002, FR-010, for an empty or all-blank file); `{path}:{line}: header must be exactly 'payer,amount,description'; found '{found}'` where `{found}` is the header row's fields re-joined with commas (FR-002, FR-010 — cover `Payer,Amount,Description`, `amount,payer,description`, and `payer,amount,description,date`); `{path}:{line}: expected 3 fields, found {count}` (FR-010); `{path}:{line}: unknown payer '{payer}'; not in the participant list` (FR-006); `{path}:{line}: invalid amount '{value}'; expected a non-negative number with at most two decimal places` (FR-003, FR-004 — cover `abc`, the empty string, `-5.00`, `1.005`, `$5`, `1,200.00`, `1e3`, `inf`, `nan`, `3 0.00`). Also assert FR-010a/acceptance 2.8: a file with a bad amount on line 3 and an unknown payer on line 5 reports only line 3; a bad header hides every row problem; a duplicate participant is reported without the file being opened at all (point the path at a non-existent file to prove it); and SC-004's count — 11 of 11 named malformed cases produce a non-empty stderr message, empty stdout, and non-zero status
- [ ] T023 [US2] Extend `tests/test_cli_invocation.py` (created in T011, so sequential with it) with the FR-020 exit-2 cases, run via the `run_subprocess` fixture because `argparse` exits the process itself: missing positional path, missing `--participants`, an unrecognised option (`--verbose`), and an extra positional argument. Assert `returncode == 2`, that stderr contains `splitter:` and argparse's usage line, and that stdout is empty (contracts/cli.md exit table)

### Implementation for User Story 2

- [ ] T024 [P] [US2] Add the three participant-list rejections to `parse_participants` in `src/splitter/cli.py`, checked in exactly this order (research D9): no names at all after splitting and trimming → `SplitterError("--participants requires at least one participant name")`; any element empty or whitespace-only after trimming → `SplitterError("--participants contains an empty participant name")` (never silently skipped, because the group size determines every share); the same trimmed name more than once → `SplitterError(f"--participants contains duplicate participant name '{name}'")` (FR-007, FR-008)
- [ ] T025 [P] [US2] Add the two file-level rejections to `read_expenses` in `src/splitter/expenses.py`: wrap the `open`/read in a narrow `except OSError as exc` raising `SplitterError(f"cannot read expenses file '{path}': {exc.strerror}")` (FR-009), and a narrow `except UnicodeDecodeError` raising `SplitterError(f"cannot decode expenses file '{path}' as UTF-8")` (FR-002a). These are the only two `except` clauses permitted in the package; neither swallows anything, and `errors=` is never passed to `open` so replacement characters are never substituted
- [ ] T026 [US2] Add the two header rejections to `read_expenses` in `src/splitter/expenses.py` (same file as T025): no non-blank row at all → `SplitterError(f"{path}: missing header row; expected 'payer,amount,description'")`; first non-blank row != `list(HEADER)` → `SplitterError(f"{path}:{line}: header must be exactly 'payer,amount,description'; found '{\",\".join(row)}'")` (FR-002, FR-010)
- [ ] T027 [US2] Add the three data-row rejections to `src/splitter/expenses.py` (same file as T025–T026), raised in column order within each row: field count != 3 → `SplitterError(f"{path}:{line}: expected 3 fields, found {len(row)}")`; payer not in `participants` → `SplitterError(f"{path}:{line}: unknown payer '{payer}'; not in the participant list")`; and in `parse_amount`, no regex match → `SplitterError(f"{path}:{line}: invalid amount '{value}'; expected a non-negative number with at most two decimal places")`. Rows are processed by increasing line number and the first failure stops the read (FR-003, FR-004, FR-006, FR-010, FR-010a, research D9)
- [ ] T028 [US2] Add the single error handler to `main` in `src/splitter/cli.py`: wrap the pipeline in `try` / `except SplitterError as exc`, write `f"splitter: error: {exc}"` as one line to `sys.stderr`, and `return 1`. This is the **only** place that catches `SplitterError` and the only place that prints a diagnostic. Because payment formatting runs only after the pipeline returns successfully, stdout stays empty on every failure path (FR-019, FR-020, research D8)
- [ ] T029 [US2] Confirm the argparse configuration in `src/splitter/cli.py` yields exit 2 for command-line misuse with no custom code: `prog="splitter"` so messages read `splitter: error: …`, the path positional required (`nargs` left at its default so an extra positional is also an error), and `--participants` declared `required=True`. Do not add `exit_on_error=False`, a custom `error()` override, or any try/except around `parse_args` — argparse's native behaviour *is* FR-020's status 2 (contracts/cli.md, research D8)
- [ ] T030 [US2] Run `pytest` from the repository root (whole suite) and confirm every US1 and US2 test passes; then run every command in quickstart.md V8 and V9 and confirm each prints the catalogued message, leaves stdout empty, and exits with the documented status

**Checkpoint**: User Stories 1 AND 2 both work independently — valid input settles, and every
invalid input fails loudly with one precise message.

---

## Phase 5: User Story 3 - Trust the cent-level arithmetic on an awkward split (Priority: P3)

**Goal**: Demonstrate, over inputs whose totals deliberately do not divide evenly, that the printed
payments account for every cent — none dropped, none invented — and that repeated runs are
byte-identical.

**Independent Test**: Run the tool on a 10.00 total split three ways and on a range of
non-divisible totals and group sizes; confirm the printed amounts sum to exactly the total imbalance
and that applying them zeroes every balance to the cent. Then run the same input twice and compare
the output byte for byte.

**Scope note**: The arithmetic itself is already implemented in US1 (integer cents throughout, by
construction). This phase is the *guarantee*: the invariant tests that prove it, plus correcting the
one arithmetic slip the design review found in the spec.

### Tests for User Story 3 ⚠️

- [ ] T031 [P] [US3] Extend `tests/test_settle.py` (created in T008, so sequential with it) with the conservation invariants as parametrised sweeps over many inputs — at minimum every combination of `total_cents` in `{0, 1, 2, 99, 100, 101, 999, 1000, 1001, 123457}` and participant counts 1 through 7: SC-002 `sum(shares.values()) == total_cents` exactly and `sum(balances.values()) == 0` exactly in 100% of cases; SC-002 applying every returned `Payment` to a copy of the balance map leaves every entry at exactly 0; SC-003 `len(payments) <= len(participants) - 1` and `all(p.amount_cents >= 1 for p in payments)`; FR-014 `sum(p.amount_cents for p in payments) == sum(b for b in balances.values() if b > 0)`. Also assert the loop-termination property for a group of one (balance 0 → no payments) and for a zero total
- [ ] T032 [P] [US3] Extend `tests/test_cli_output.py` (created in T010, so sequential with it) with the end-to-end awkward-split cases: acceptance 3.1 — a file whose only expense is `Alice,10.00,Taxi` with participants `Alice,Bob,Carol` prints exactly `Bob pays Alice 3.33` and `Carol pays Alice 3.33`, whose amounts sum to **6.66** (see T033: under FR-011 the leftover cent is charged to `Alice`, first in name order, raising her share to 334 and lowering her credit to 666 cents); acceptance 3.3/SC-005 the same input run twice produces byte-identical stdout, line for line; and SC-005's locale clause — run the subprocess twice with `LC_ALL=C` and `LC_ALL=en_US.UTF-8` in the environment and assert byte-identical stdout, which holds by construction because nothing imports `locale`

### Implementation for User Story 3

- [ ] T033 [US3] Correct the arithmetic slip in acceptance scenario 3.1 of `specs/001-expense-splitter/spec.md` (around line 128): change "the printed amounts sum to exactly 6.67" to "6.66", because FR-011/FR-011a charge the leftover cent to `Alice` (first in ascending code-point name order), giving shares Alice 334 / Bob 333 / Carol 333 and payments of 333 + 333 = 666 cents. FR-011/FR-011a are normative and self-consistent; `6.67` would require charging the odd cent to a debtor instead. No cent is lost either way — SC-002 holds under FR-011. This is the spec fix the discrepancy note at the end of `data-model.md` asks `/speckit-tasks` to schedule
- [ ] T034 [P] [US3] Correct the same slip in `specs/001-expense-splitter/research.md` D6 (around line 147): "the printed payments sum to exactly 6.67" → "6.66", keeping the surrounding share figures (Alice 334, Bob 333, Carol 333) which are already correct. Then remove the now-resolved "Discrepancy to resolve before implementation" block at the end of `specs/001-expense-splitter/data-model.md` (lines 221–231) and the corresponding note in `specs/001-expense-splitter/quickstart.md` V4 (lines 112–115), replacing each with a one-line statement that the total is 6.66 per FR-011
- [ ] T035 [US3] Audit every file under `src/splitter/` for monetary-precision violations: `grep -rnE "float|Decimal|Fraction|round\(|%\.2f|:\.2f" src/` must return no hit in any monetary path, confirming amounts are formatted by integer arithmetic only (research D1). Also confirm `grep -rn "import" src/` shows only `argparse`, `csv`, `dataclasses`, `re`, `sys`, and intra-package imports
- [ ] T036 [US3] Run `pytest` from the repository root and confirm the whole suite passes; then run quickstart.md V4, V7, and V10 and confirm the awkward-split total, the cross-locale byte-identity, and the no-mutation guarantee

**Checkpoint**: All three user stories are independently functional. The settlement is safe to act on
without a manual re-check.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: The performance ceiling, the traceability gate, and the final constitution check

- [ ] T037 [P] Create `tests/test_performance.py` covering SC-006: generate a file of 1,000 expense rows across 50 participants into `tmp_path` (participant names `P00`…`P49`, amounts in cents so no float is involved), time one in-process `cli.main([...])` call with `time.perf_counter`, and assert it completes in under 2.0 seconds and prints at most 49 payment lines. Keep the generation deterministic (seed any `random` use, or cycle the payers) so the test cannot flake on content
- [ ] T038 [P] Add `__pycache__/` and `.pytest_cache/` to the repository-root `.gitignore` if not already present, so `git status` is clean after a run as quickstart.md's "Done when" requires
- [ ] T039 Traceability audit against plan.md's requirement table: confirm every requirement FR-001 through FR-021 and every criterion SC-001 through SC-008 is named in at least one test name or test comment, and that each of the ten exit-1 error paths has its own test asserting both message content and exit status (Constitution III). Record any gap as a new test rather than a note
- [ ] T040 Run the full `pytest` suite from the repository root with no arguments and confirm it passes and collects every test file — proving `pytest.ini`'s `pythonpath = src` is sufficient with no install step and no plugin (Constitution "tests are discoverable by pytest from the repository root")
- [ ] T041 Walk quickstart.md's "Done when" checklist end to end: `pytest` passes with no arguments; V1–V11 each produce the stated expectation; no third-party module is imported by anything under `src/`; and `git status` is clean after a run (the tool created and changed nothing)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on US2 or US3
- **User Story 2 (Phase 4)**: Depends on Foundational. Its *tests* are independent, but its
  implementation tasks modify functions US1 creates (`parse_participants`, `read_expenses`,
  `main`), so in practice run it after US1 — see the note below
- **User Story 3 (Phase 5)**: Depends on Foundational and on US1's `settle.py` and `cli.py`
  implementations existing. Independent of US2
- **Polish (Phase 6)**: Depends on all three stories being complete

### User Story Dependencies

- **US1 (P1)**: Self-contained. Delivers the MVP on its own
- **US2 (P2)**: Shares three source files with US1 (`cli.py`, `expenses.py`). This is the one place
  the stories are not file-disjoint: US1 writes the happy path of those functions and US2 adds the
  rejection branches to the same bodies. US2 is still *testable* independently (its tests assert
  only failure behaviour) but should not be implemented concurrently with US1 by a second person in
  the same files
- **US3 (P3)**: Adds tests to `test_settle.py` and `test_cli_output.py` (US1's files) and edits spec
  documents. No source change — the arithmetic it guarantees is already US1's

### Within Each User Story

- Tests are written and MUST FAIL before the implementation tasks of that story
- Dataclasses and constants (Phase 2) before the functions that use them
- `parse_amount` before `read_expenses`; `compute_shares` before `compute_balances` before `settle`;
  all of those before `cli.main`; `cli.main` before `__main__.py`
- Story complete and its checkpoint verified before moving to the next priority

### Parallel Opportunities

- T002 and T003 run in parallel (both after T001)
- T005, T006, T007 run in parallel (different files; all after T004)
- T008, T009, T010, T011 — all four US1 test files — run in parallel
- T012 (`expenses.py`), T014 (`settle.py`), T017 (`cli.py`) run in parallel: three different files,
  no dependency between them
- T024 (`cli.py`) and T025 (`expenses.py`) run in parallel
- T031 (`test_settle.py`) and T032 (`test_cli_output.py`) run in parallel
- T033/T034 (spec documents) run in parallel with any source or test work
- T037 and T038 run in parallel
- **Not parallel**: T014/T015/T016 (all `settle.py`), T017/T018/T019 (all `cli.py`),
  T025/T026/T027 (all `expenses.py`), T011/T023 (both `test_cli_invocation.py`),
  T008/T031 (both `test_settle.py`), T010/T032 (both `test_cli_output.py`)

---

## Parallel Example: User Story 1

```bash
# Launch all four US1 test files together (they must fail before implementation):
Task: "Create tests/test_settle.py — share, balance, and settlement assertions (T008)"
Task: "Create tests/test_expenses.py — header, BOM, blank rows, amount grammar (T009)"
Task: "Create tests/test_cli_output.py — reference case, silence, determinism, read-only (T010)"
Task: "Create tests/test_cli_invocation.py — accepted invocation, in-process and subprocess (T011)"

# Then launch the three first-in-file implementations together:
Task: "Implement parse_amount in src/splitter/expenses.py (T012)"
Task: "Implement compute_shares in src/splitter/settle.py (T014)"
Task: "Implement parse_participants in src/splitter/cli.py (T017)"
```

## Parallel Example: User Story 2

```bash
Task: "Add the three participant-list rejections to src/splitter/cli.py (T024)"
Task: "Add OSError and UnicodeDecodeError rejections to src/splitter/expenses.py (T025)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup — three files, no logic
2. Complete Phase 2: Foundational — `SplitterError`, `Expense`, `Payment`, `conftest.py`
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `pytest` passes; quickstart V1, V2, V3, V5, V6 match their expectations
5. The tool now settles up correctly for valid input — demonstrable value

### Incremental Delivery

1. Setup + Foundational → the package imports and `pytest` collects
2. Add US1 → valid CSVs settle correctly → **MVP, demo-able**
3. Add US2 → every malformed input fails loudly with one precise message and the right exit status
4. Add US3 → the cent-conservation guarantee is proven over a sweep of awkward splits, and the
   spec's arithmetic slip is corrected
5. Polish → performance ceiling, traceability audit, full quickstart walkthrough

Each story adds value without breaking the previous ones: US2 only adds branches that US1's valid
inputs never reach, and US3 adds no source change at all.

### Parallel Team Strategy

With more than one developer, the file overlap between US1 and US2 matters more than the story
independence:

1. Everyone completes Setup + Foundational together
2. Then split by **file**, not by story: Developer A takes `expenses.py` and `test_expenses.py`
   (T012, T013, then T025–T027); Developer B takes `settle.py` and `test_settle.py` (T014–T016,
   then T031); Developer C takes `cli.py`, `__main__.py`, and the CLI test files (T017–T020, then
   T024, T028, T029)
3. T033/T034 (spec corrections) and T037/T038 (polish) can be picked up by anyone at any point

---

## Notes

- [P] tasks touch different files and have no dependency on an incomplete task
- Every task names its exact file path; every implementation task names the requirement ids it
  satisfies so the Constitution III mapping is explicit in the code and tests
- Verify tests fail before implementing — a test that passes against missing code is testing nothing
- Commit after each task or logical group
- Stop at any checkpoint to validate that story independently
- The "Non-negotiable invariants" block at the top of this file applies to every source task; a
  violation there is a merge-gate failure, not a style preference
