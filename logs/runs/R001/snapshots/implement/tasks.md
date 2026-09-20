---
description: "Task list for Expense Splitter implementation"
---

# Tasks: Expense Splitter

**Input**: Design documents from `/specs/001-expense-splitter/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: INCLUDED. The project constitution (Principle IV — Every Requirement Is Testable) and plan.md/quickstart.md mandate a `pytest` suite where every functional requirement maps to at least one test. Test tasks are therefore first-class and precede implementation within each story (TDD).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single-project CLI layout (from plan.md). Runtime code in `src/splitter/`, tests in `tests/`, both at repository root. Running from source requires `src/` on the import path (`PYTHONPATH=src`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create source and test package layout: `src/splitter/` and `tests/` directories at repository root
- [X] T002 [P] Create `src/splitter/__init__.py` (package marker; may expose `__version__`)
- [X] T003 [P] Create `src/splitter/__main__.py` that enables `python -m splitter` by delegating to `cli.main()` (import guarded so it runs under `python -m splitter`)
- [X] T004 [P] Create `tests/__init__.py` (empty test package marker)
- [X] T005 [P] Create `pyproject.toml` at repository root with dev metadata and pytest config; declare NO runtime dependencies, `pytest` as a dev-only dependency (Constitution Principle I; plan.md)

**Checkpoint**: Package skeleton importable; `python -m splitter` resolves to a (still-empty) entry point.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Integer-cent money helpers required by parser, settlement, and CLI output. This is the shared money boundary every story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 [US-shared] Write failing tests in `tests/test_money.py` for cent parsing/formatting: `parse_to_cents("30.00") == 3000`, `parse_to_cents("0") == 0`, `parse_to_cents("12.50") == 1250`; rejects non-numeric (`"abc"`), negative (`"-5.00"`), and >2-decimal (`"12.505"`) values by raising; `format_cents(1500) == "15.00"` (two fractional digits, no locale symbol) — FR-009, FR-013, FR-018
- [X] T007 Implement `src/splitter/money.py`: `parse_to_cents(text)` using `decimal.Decimal` to parse exactly, rejecting non-numeric, negative, and values with more than two fractional digits, then converting to an integral `int` cents (verify `Decimal * 100` is integral); `format_cents(cents)` rendering a plain decimal with exactly two fractional digits at the output boundary only. Money is `int` cents throughout; no float ever holds money (research.md Decision 1; Constitution Principle II). Make T006 pass.

**Checkpoint**: Exact integer-cent parse/format available — all stories can now begin.

---

## Phase 3: User Story 1 - Settle up a shared trip (Priority: P1) 🎯 MVP

**Goal**: Turn a valid CSV of expenses plus a participant list into a deterministic, minimal list of debtor→creditor transfers that bring every participant to an equal share.

**Independent Test**: Provide a valid CSV (e.g. Alice 30.00, Bob 0) and participants `"Alice,Bob"`; confirm the tool prints exactly `Bob pays Alice 15.00`, exit 0. A multi-participant case's payments sum to the total owed by debtors and zero every balance.

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL)

- [X] T008 [P] [US1] Write failing settlement tests in `tests/test_settle.py`: net-balance computation (`net_cents = paid_cents - share_cents`), equal-share assignment for evenly divisible totals, minimal-transaction settlement (Alice paid 30.00 / Bob 0 → single `Bob→Alice 1500`), the already-settled case (all nets zero → empty payment list), and the SC-003 bound (payments ≤ non-zero-balance participants − 1) — FR-005, FR-006, FR-007, FR-010
- [X] T009 [P] [US1] Write failing happy-path parser tests in `tests/test_parser.py`: reading a valid CSV with header `payer,amount,description` produces one Expense per data row with `payer:str`, `amount_cents:int` (≥ 0), `description:str` (informational, never used in computation) — FR-002
- [X] T010 [P] [US1] Write failing end-to-end CLI tests in `tests/test_cli.py` (Scenarios 1 & 2 from quickstart.md): valid input → exit 0 and stdout `Bob pays Alice 15.00`; already-settled input → exit 0 and stdout stating no payments needed (e.g. `Already settled — no payments needed.`) — FR-010, contracts/cli.md

### Implementation for User Story 1

- [X] T011 [US1] Implement participant-list parsing and happy-path CSV reading in `src/splitter/parser.py`: split `--participants` on commas trimming surrounding whitespace; build ordered Participant list; read CSV via `csv` module with header `payer, amount, description`; construct Expense per row using `money.parse_to_cents` for `amount` (fields: `payer:str` matching a participant, `amount_cents:int ≥ 0`, `description:str` informational-only). Preserve supplied participant-list order for determinism (data-model.md; FR-002). Make T009 pass.
- [X] T012 [US1] Implement settlement core in `src/splitter/settle.py`: compute group total (sum of `amount_cents`), assign equal shares, compute each Participant's `net_cents = paid_cents - share_cents` (positive → creditor, negative → debtor, invariant: all nets sum to 0), and produce minimal payments via greedy largest-debtor/largest-creditor match transferring `min(|debt|, credit)`, breaking ties by supplied participant-list order (research.md Decisions 2 & 3; FR-005, FR-006, FR-007). Each Payment has `from_name` (debtor), `to_name` (creditor), `amount_cents > 0`. Make T008 pass.
- [X] T013 [US1] Implement CLI orchestration + success output in `src/splitter/cli.py`: `argparse` with positional `expenses.csv` and required `--participants` option; call parser then settle; write settlement to stdout formatting amounts via `money.format_cents` as `"<debtor> pays <creditor> <amount>"` one per line in deterministic order; when already settled, print the no-payments message; exit 0 (contracts/cli.md; FR-010, FR-017, FR-018). Make T010 pass.

**Checkpoint**: User Story 1 fully functional — `python -m splitter <valid.csv> --participants "..."` prints a correct minimal settlement. MVP deliverable.

---

## Phase 4: User Story 2 - Reject malformed input clearly (Priority: P1)

**Goal**: Every malformed-input variant produces a clear stderr message naming the problem, nothing on stdout, and a non-zero exit code.

**Independent Test**: Feed each malformed variant (missing file, unknown payer, bad/negative/over-precise amount, empty participant list, missing header/field, duplicate participants) and confirm stderr message + empty stdout + non-zero exit.

### Tests for User Story 2 ⚠️ (write first, ensure they FAIL)

- [X] T014 [P] [US2] Add failing validation tests in `tests/test_parser.py` covering the full error taxonomy (data-model.md): CSV file missing/unreadable (FR-011); missing/misnamed header or missing required column (FR-015, FR-002); row with blank `payer` or blank `amount` (FR-015); payer not in participant list, naming the payer (FR-012); amount non-numeric, negative, or >2 decimals, naming the amount (FR-013); empty participant list (FR-014); duplicate participant names after trimming, naming the duplicate (spec Edge Cases / Assumptions). Assert each raises the typed `ValidationError`.
- [X] T015 [P] [US2] Add failing end-to-end error tests in `tests/test_cli.py` (Scenario 4 from quickstart.md): for each malformed variant assert exit code is non-zero, stdout is empty (no partial/best-guess settlement — FR-016), and stderr contains a clear message naming the offending element (FR-011..FR-016, SC-004)

### Implementation for User Story 2

- [X] T016 [US2] Define typed `ValidationError(Exception)` in `src/splitter/parser.py` carrying a human-readable message per rejection class (research.md Decision 5)
- [X] T017 [US2] Add validation to `src/splitter/parser.py`: reject empty participant list (FR-014); reject duplicate participant names after trimming, naming the duplicate (Edge Cases); require header columns exactly `payer, amount, description` and reject missing/misnamed header or missing required column (FR-002, FR-015); reject rows with blank `payer` or blank `amount` (FR-015); reject a payer not in the participant list, naming the payer (FR-012); surface `money.parse_to_cents` rejections (non-numeric/negative/>2-decimal) naming the amount and row (FR-013). Raise `ValidationError` in every case. Make T014 pass.
- [X] T018 [US2] Add error handling to `src/splitter/cli.py`: catch file-open failure for the CSV path → `ValidationError`-style message (FR-011); catch `ValidationError`; write the message to stderr; write NOTHING to stdout; return a non-zero exit code (FR-016, Constitution Principle III). Make T015 pass.

**Checkpoint**: User Stories 1 AND 2 both work — valid input settles, every malformed input fails loudly with no stdout.

---

## Phase 5: User Story 3 - Trust that no money is lost or invented (Priority: P2)

**Goal**: For totals that do not divide evenly, leftover cents are distributed deterministically so shares sum exactly to the total and printed payments sum exactly to the total imbalance.

**Independent Test**: Run 10.00 across three participants; verify shares are `3.34 / 3.33 / 3.33` (sum exactly 10.00), printed payments sum to the exact total imbalance, and applying them zeroes every balance; per-person shares differ by at most one cent.

### Tests for User Story 3 ⚠️ (write first, ensure they FAIL)

- [X] T019 [P] [US3] Add failing conservation/remainder tests in `tests/test_settle.py`: for `total_cents=1000`, `n=3`, shares are `[334, 333, 333]` (`sum == total_cents`; any two differ by ≤ 1 cent); the first `r = total_cents % n` participants in supplied order get the `+1` cent; sum of all payment `amount_cents` equals the sum of positive `net_cents` (total imbalance) exactly; applying all payments brings every `net_cents` to 0 — FR-004, FR-008, FR-009, SC-001, SC-002
- [X] T020 [P] [US3] Add failing end-to-end uneven-split test in `tests/test_cli.py` (Scenario 3 from quickstart.md): Alice 10.00 across `"Alice,Bob,Carol"` → exit 0, printed payments sum exactly to the total imbalance and zero every balance

### Implementation for User Story 3

- [X] T021 [US3] Implement the deterministic largest-remainder share allocation in `src/splitter/settle.py`: `base = total_cents // n`, `r = total_cents % n`; every participant gets `share_cents = base`; the first `r` participants in supplied list order get `+1` cent so `sum(share_cents) == total_cents` exactly and any two shares differ by at most one cent (research.md Decision 2; data-model.md remainder rule; FR-004). Make T019 pass.
- [X] T022 [US3] Add conservation assertions/guards in `src/splitter/settle.py`: assert `sum(net_cents) == 0` and `sum(payment.amount_cents) == sum(positive net_cents)` so no cent is lost or invented at any step (FR-008, FR-009, Constitution Principle II). Ensure T020 passes end to end.

**Checkpoint**: All three user stories independently functional; uneven splits conserve every cent.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Determinism guarantee, documentation, and full validation across all stories

- [X] T023 [P] Add a determinism test in `tests/test_cli.py` (Scenario 5 from quickstart.md): two runs on identical input produce byte-identical stdout (FR-017, SC-005)
- [X] T024 [P] Verify performance/scope: a typical group (up to a few dozen expenses) settles in a single invocation with no interaction (SC-006) — add/confirm a representative multi-row case in `tests/test_settle.py`
- [X] T025 Run the full quickstart.md validation (Scenarios 1–5) manually with `PYTHONPATH=src` and confirm each expected result
- [X] T026 [P] Run `python -m pytest` from repository root and confirm all tests pass with every functional requirement covered (Constitution Principle IV)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (money helpers are used everywhere)
- **User Stories (Phase 3–5)**: All depend on Foundational (Phase 2)
  - US1 (P1) and US2 (P1) share `parser.py` and `cli.py`; US2 extends the files US1 creates, so run US1 → US2 sequentially (or coordinate edits if parallel)
  - US3 (P2) extends `settle.py` from US1; run after US1
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational. Creates `parser.py`, `settle.py`, `cli.py` happy paths. MVP.
- **US2 (P1)**: Depends on Foundational; extends `parser.py`/`cli.py` created in US1 with validation + error mapping. Independently testable via malformed inputs.
- **US3 (P2)**: Depends on Foundational; extends `settle.py` created in US1 with remainder allocation + conservation. Independently testable via an uneven-split case.

### Within Each User Story

- Tests are written FIRST and must FAIL before implementation (TDD)
- `money.py` (foundational) before `parser.py`/`settle.py`
- Models/parsing before settlement; settlement before CLI output
- Story complete and its checkpoint validated before moving to next priority

### Parallel Opportunities

- Setup: T002, T003, T004, T005 can run in parallel (different files) after T001
- Within a story, all test-authoring tasks marked [P] target different files and can run together (e.g. T008/T009/T010; T014/T015; T019/T020)
- Polish: T023, T024, T026 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Author all US1 tests together (they target different files and must fail first):
Task: "Settlement tests in tests/test_settle.py (T008)"
Task: "Happy-path parser tests in tests/test_parser.py (T009)"
Task: "End-to-end CLI tests in tests/test_cli.py (T010)"

# Then implement in dependency order (parser → settle → cli):
Task: "Implement parser.py happy path (T011)"
Task: "Implement settle.py core (T012)"
Task: "Implement cli.py success output (T013)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (money.py — CRITICAL, blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `python -m splitter <valid.csv> --participants "..."` prints a correct minimal settlement (quickstart Scenarios 1–2)
5. Demo the MVP

### Incremental Delivery

1. Setup + Foundational → money boundary ready
2. Add US1 → correct settlement for valid input → Demo (MVP!)
3. Add US2 → fails loudly on every malformed input → Demo
4. Add US3 → conserves every cent on uneven splits → Demo
5. Polish → determinism + full quickstart validation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to a specific user story for traceability; `[US-shared]` marks the foundational money tests used by all stories
- Money is `int` cents end to end; `decimal.Decimal` only parses the input string to exact cents; formatting to a decimal string happens only at the output boundary (Principle II, FR-018)
- Every error → clear stderr message + non-zero exit + no stdout settlement (Principle III, FR-016)
- Verify each story's tests fail before implementing
- Commit after each task or logical group
