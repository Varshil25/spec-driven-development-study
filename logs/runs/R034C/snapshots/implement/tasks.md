# Tasks: Administrator-Issued Password Reset

**Input**: Design documents from `/specs/002-password-reset/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-contract.md, quickstart.md

**Tests**: Test tasks ARE included and are mandatory. Constitution Principle III requires every
functional requirement to map to a `pytest` test that fails when the requirement is unmet, and
SC-009 counts the mapping (24 of 24, both directions).

**Organization**: Tasks are grouped by user story. Phases run in spec priority order — the three
P1 stories (US1, US2, US5) before the two P2 stories (US3, US4).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 – US5)
- Exact file paths are given in every task

## Path Conventions

Single project, as feature 001 established it: `src/accounts/` and a flat `tests/` at the
repository root. **No module is added and no file is deleted.** Four source files are modified
(`cli.py`, `commands.py`, `passwords.py`, `store.py`), six test files are new, and exactly one
existing test file is modified (`tests/test_requirement_coverage.py`, sanctioned by research.md
R-17). `pyproject.toml` is not touched.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the green baseline this feature must not break, and confirm the
performance budget on the machine the work is done on.

- [X] T001 Run `pytest` from the repository root and confirm the full existing suite is green with no skipped test; record the commit (`git rev-parse HEAD`) as the SC-011 baseline, and confirm `pyproject.toml` still has `dependencies = []` and `requires-python = ">=3.11"` (Constitution Principle I, SC-011)
- [X] T002 [P] Measure the cost of one PBKDF2 derivation at the project's parameters (`hashlib.pbkdf2_hmac("sha256", b"x", b"y"*16, 600_000, dklen=32)`) on this machine with a throwaway timing run, and record the figure; plan.md budgets 0.150 s per derivation, so `reset-token` ≈ 1 derivation and `reset` ≈ 2 against SC-016's 1-second limit. If the measurement exceeds ~0.33 s per derivation, note it against the SC-016 thresholds used in T033 (research.md R-10, SC-016)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The token primitive, the store schema that can hold a token, the shared diagnostics,
and the coverage ledger. No user story can be implemented or tested until these are done.

**⚠️ CRITICAL**: T006 is blocking for a non-obvious reason — `tests/test_requirement_coverage.py`
currently asserts that no test under `tests/` mentions any identifier outside FR-001 – FR-038.
The moment the first new test cites `FR-039`, that existing assertion fails. The ledger must be
extended **before** any new test file is written, or the suite goes red for bookkeeping reasons
rather than behaviour.

- [X] T003 [P] Add `new_token() -> str` to `src/accounts/passwords.py` returning `secrets.token_urlsafe(32)` — "32 CSPRNG bytes", "256 bits (floor is 128)", rendered as "43 characters matching `\A[A-Za-z0-9_-]{43}\Z`" — and widen the module docstring from "One-way password transformation" to cover token generation as well, citing FR-040 and research.md R-09. No new import beyond the `secrets` already present (FR-040)
- [X] T004 [P] Extend `src/accounts/store.py` for the optional `reset_token` record key (data-model.md rules 4 amended and 8–11; FR-057, FR-059):
  - keep `VERSION = 1` unchanged — a pre-feature file stamped `1` must still load
  - add `RESET_TOKEN_KEYS = frozenset({"salt", "verifier", "expires_at"})`
  - in `_validate_record`, require "exactly the keys `salt`, `verifier`, `failed_logins`, `locked`, and **optionally** `reset_token`" — compute `unknown` against `RECORD_KEYS | {"reset_token"}` while leaving the required-key (`missing`) check against `RECORD_KEYS` unchanged, so an account with no token still validates and a misspelled `reset_tokens` is still `unknown key: reset_tokens`
  - add `_validate_reset_token(where, value)` applying rule 8 ("a JSON object carrying exactly the keys `salt`, `verifier`, `expires_at` — no missing key, no unknown key"; `null` is not an object and is rejected here), rule 9 (`salt` and `verifier` are "strings that decode as strict base64 to exactly 16 and 32 bytes respectively" — reuse `_validate_base64` with `SALT_BYTES` and `VERIFIER_BYTES`, adding no new helper), and rule 10 (`expires_at` "is an `int` or `float`, is not a `bool`, and is **finite**" — `math.isfinite` is required because `json.loads` accepts the literals `NaN`, `Infinity`, and `-Infinity`)
  - rule 11 diagnostics name the account, the `reset_token` field, and the condition and disclose no stored value, e.g. `account 'alice': reset_token: expires_at is not a finite number`
  - add `import math`; every failure is `StoreError`, raised by explicit test rather than by catching a decoder (Principle II)
- [X] T005 [P] Add the two new diagnostics constants to `src/accounts/commands.py` beside the existing E-constants: `E14_NO_TOKEN = "no token on standard input\n"` and `E15_INVALID_TOKEN = "invalid token\n"`. `invalid token` is fixed verbatim by FR-052 and MUST match exactly. Do not add constants for E1, E4, or E9 — the new commands reuse `E1_SHORT_PASSWORD`, `E9_NO_NEW_PASSWORD`, and the existing inline `f"no such account: {username}\n"` text unchanged (contracts/cli-contract.md E1/E4/E9/E14/E15)
- [X] T006 Extend `tests/test_requirement_coverage.py` to span both features per research.md R-17: read `specs/001-local-account-manager/spec.md` **and** `specs/002-password-reset/spec.md`, assert the union of defined identifiers is exactly FR-001 – FR-062, that every one is referenced by some test under `tests/`, and that no test cites an identifier no spec defines. Preserve the three existing assertions for FR-001 – FR-038 rather than loosening them (raise `LAST_REQUIREMENT` to 62 only in the union checks). This is the only existing test file that may change (SC-009, SC-011, R-17)

**Checkpoint**: `pytest` is still green (the ledger now tolerates FR-039+ citations, and no behaviour has changed). User story work can begin.

---

## Phase 3: User Story 1 - Recover access to a forgotten password (Priority: P1) 🎯 MVP

**Goal**: The two-command recovery journey works: an administrator issues a token, the user
redeems it with a password of their own choosing, and the administrator never learns it.

**Independent Test**: Register an account, issue a token for it, feed that token and a new
password to the reset command, confirm `password reset` on stdout with status 0, then confirm a
login with the new password succeeds (0) and a login with the old password is rejected (1).

### Implementation for User Story 1

- [X] T007 [US1] Add the `--ttl` value validator `_ttl(value: str) -> int` to `src/accounts/cli.py`: accept only "a string of ASCII decimal digits" matching `\A[0-9]+\Z` that converts to `>= 1`, otherwise raise `argparse.ArgumentTypeError`. Do **not** use `type=int`, which silently coerces `1_000` → 1000, `+5` → 5, `" 10 "` → 10, and `"١٢٣"` → 123 (Principle II, research.md R-14, E17)
- [X] T008 [US1] Wire the new surface into `src/accounts/cli.py`'s parser: extend `COMMANDS` to `("register", "login", "unlock", "passwd", "delete", "reset-token", "reset")` (exact, lower-case, `reset-token` hyphenated), and register `parser.add_argument("--ttl", type=_ttl, default=None, metavar="SECONDS", help=argparse.SUPPRESS)`. `help=argparse.SUPPRESS` is required, not cosmetic: `tests/test_cli_usage.py` asserts the `--`-prefixed tokens in `--help` output are exactly `{"--store", "--help"}` and FR-060/SC-011 require that test to pass unmodified (FR-039, FR-042, research.md R-13)
- [X] T009 [US1] Inject the clock and dispatch the two new commands in `src/accounts/cli.py`: `import time`, pass `now=time.time()` and `ttl=args.ttl` from `main` into `_dispatch`, and add two branches to `_dispatch` — `reset-token` reads **zero** stdin lines and calls `commands.reset_token(accounts, username, ttl, now)` with `ttl` defaulting to 900 when `args.ttl is None`; `reset` follows the existing `passwd` pre-pass shape, returning `commands.reset(accounts, username, None, None, now)` when `username not in accounts` and otherwise reading the token line then the new-password line with `_read_password` (one `readline` each, exactly one trailing `"\n"` removed, `None` at end of input) before calling `commands.reset(accounts, username, token, new, now)`. Update `_dispatch`'s docstring, which currently says "exactly the five commands below" (FR-041, FR-048, FR-054, research.md R-15)
- [X] T010 [US1] Implement `reset_token(accounts, username, ttl, now) -> Result` in `src/accounts/commands.py`: look the record up; on success set `record["reset_token"] = {"salt": store.encode(salt), "verifier": store.encode(passwords.derive(token, salt)), "expires_at": now + ttl}` with a fresh `passwords.new_salt()` and `token=[REDACTED:assigned_secret]()`, **replacing any previous value** (at most one outstanding token per account), and return `Result(0, out=f"{token}\n", save=True)` — one line, the token and nothing else, no label, no prefix, no trailing space. Do not read or write `salt`, `verifier`, `failed_logins`, or `locked`, so issuing succeeds on a locked account with identical output and status (FR-039, FR-041, FR-044, FR-046, FR-047)
- [X] T011 [US1] Implement the success path of `reset(accounts, username, token, new, now) -> Result` in `src/accounts/commands.py`, in the contract's check order — exists? → token line present (E14) → new-password line present (E9) → token valid? → new length (E1) → act. On success replace `record["salt"]` / `record["verifier"]` with `_credential(new)` (a fresh salt, so the verifier differs even for an unchanged password), `del record["reset_token"]`, and return `Result(0, out="password reset\n", save=True)`. `password reset` is fixed verbatim by the feature description. Validate the token with `passwords.verify(token, store.decode(rt["salt"]), store.decode(rt["verifier"]))` so `hmac.compare_digest` prevents a prefix match leaking through timing, and treat it as valid only while `now < rt["expires_at"]`. Leave `failed_logins` and `locked` untouched, so a successful reset does not clear a lock (FR-048, FR-049, FR-051, FR-056)

### Tests for User Story 1

- [X] T012 [P] [US1] Create `tests/test_reset_token.py` covering FR-039, FR-040, FR-041, FR-046, FR-047 via the `run_cli`, `store_path`, and `read_store` fixtures (used unchanged): exactly one line on stdout matching `\A[A-Za-z0-9_-]{43}\n\Z` with empty stderr and status 0; 50 tokens issued in a tight loop — including twice for the same account in the same second — are all distinct and all match the alphabet; `expires_at` equals `now + 900` when `--ttl` is omitted and `now + SECONDS` when it is given (assert at the `commands.reset_token` level with an explicit `now`); the stored `reset_token` carries exactly `salt`, `verifier`, `expires_at` with the salt 16 bytes and the verifier 32 bytes once base64-decoded; `salt`, `verifier`, `failed_logins`, and `locked` are byte-identical before and after issuance; and issuing for a locked account gives the same output and status as for an unlocked one
- [X] T013 [P] [US1] Create `tests/test_reset.py` covering FR-048, FR-049, FR-050: the stdin protocol reads the token from the first line and the new password from the second and neither is ever a command-line argument; a valid token plus a 20-character password yields `password reset\n` on stdout, empty stderr, status 0; the `reset_token` key is gone from the record afterwards; a subsequent `login` with the new password exits 0 and with the pre-reset password exits 1 with `invalid credentials`
- [X] T014 [P] [US1] Create `tests/test_reset_end_to_end.py` covering SC-010 worked examples 1 and 2 and the SC-012 journey: drive real `python -m accounts` subprocesses with `PYTHONPATH=src` against a `tmp_path` store, asserting the exact stdout text, exact stderr text, and exact status of each step, and that `TOKEN=$(... reset-token alice)`-style capture yields a usable token. Include the note from contracts/cli-contract.md that these four examples are drawn from the spec's fully specified stdout/stderr/status triples, since the recorded feature description contains none
- [X] T015 [US1] Append `--ttl` value-validation cases to `tests/test_reset_token.py` for FR-042: each of `0`, `-5`, `abc`, `10.0`, `1e3`, `1_000`, `+5`, `" 10 "`, `١٢٣`, and an empty value exits 2 with a usage diagnostic on stderr, writes nothing to stdout, issues no token, and leaves the store file untouched (assert the file does not exist, or its bytes are unchanged) — `1_000` and `+5` in particular must not be coerced (research.md R-14)

**Checkpoint**: User Story 1 is fully functional and independently testable — the MVP recovery journey works end to end.

---

## Phase 4: User Story 2 - A token cannot be reused, guessed, or outlived (Priority: P1)

**Goal**: All five ways a token can fail — wrong, superseded, already used, expired, never issued
— produce byte-identical `invalid token` with status 1, change nothing, and write nothing. A
token in the store cannot be read back out of it.

**Independent Test**: Exercise each rejection case and confirm each writes exactly
`invalid token` to stderr, exits 1, leaves the stored password working, and leaves
`failed_logins` and `locked` untouched; then confirm an issued token's 43 characters appear
nowhere in the store file's bytes.

### Implementation for User Story 2

- [X] T016 [US2] Complete the rejection path of `reset` in `src/accounts/commands.py`: return `Result(1, err=E15_INVALID_TOKEN, save=False)` when `"reset_token" not in record` (never issued, already used, or removed with a successful reset), when `passwords.verify` fails (wrong or superseded — a superseded token fails because `reset_token` was overwritten in T010), or when `not now < rt["expires_at"]` (expired; strict `<`, so the token is invalid *at* and after the instant the window elapses). The message and status MUST be identical in all five cases so the response cannot reveal which applied. Write nothing: `save=False` on every one of these paths, do not sweep the expired `reset_token` record, and never read or increment `failed_logins` or touch `locked` — a rejected token is not a failed login (FR-041, FR-051, FR-052, FR-056, research.md R-16)

### Tests for User Story 2

- [X] T017 [US2] Append the five rejection cases to `tests/test_reset.py` for FR-051, FR-052, FR-056: wrong token, already-used token, superseded token, expired token, and an account with no token ever issued each yield byte-identical `("invalid token\n", 1)` with empty stdout; the stored `salt`/`verifier` are unchanged and the pre-existing password still logs in; `failed_logins` and `locked` are unchanged; and six consecutive wrong tokens do not lock the account (the lock threshold is 5)
- [X] T018 [P] [US2] Create `tests/test_reset_secrets.py` covering FR-057, FR-058, SC-014: issue a token, then assert its 43 characters appear nowhere in the store file's raw bytes; assert the record's `reset_token` holds only `salt`, `verifier`, `expires_at`; and assert the token appears in no diagnostic and on no stream of any other command — drive the success, `invalid token`, short-password, and unknown-account paths and grep both captured streams for the token value
- [X] T019 [P] [US2] Append supersession coverage to `tests/test_reset_token.py` for FR-044: issuing a second token for an account replaces the first (the stored `salt`, `verifier`, and `expires_at` all change), and the first token is thereafter "treated exactly like a token that was never issued" — rejected with `invalid token` and status 1 — while the second succeeds
- [X] T020 [US2] Append expiry-boundary coverage to `tests/test_reset.py` for FR-041 and FR-052, calling `commands.reset` directly with an explicit `now` (the injected clock, plan.md Complexity Tracking): valid at `now = expires_at - 0.001`, **invalid at exactly `now = expires_at`**, and invalid after it — asserting the boundary rather than sleeping through a window
- [X] T021 [US2] Append to `tests/test_reset_end_to_end.py`: SC-010 worked example 3 (the same token a second time → `invalid token` on stderr, stdout empty, status 1, password unchanged), and SC-013 — all five rejection cases through the real CLI returning indistinguishable output, including one `--ttl 1` token with a real ~1 s sleep so the wiring from `cli` to the actual clock is asserted and not just a stub (research.md R-18)

**Checkpoint**: User Stories 1 and 2 both work independently. The reset path is now safe to ship.

---

## Phase 5: User Story 5 - Everything that worked before still works (Priority: P1)

**Goal**: The five existing commands show no observable change of any kind, `--ttl` is rejected
everywhere except `reset-token`, and a store file written before this feature loads without
complaint while strict validation stays strict.

**Independent Test**: Run the existing suite for FR-001 – FR-038 unmodified and confirm it is
green; load a pre-feature store file and confirm every existing command still operates on it;
confirm `--ttl` on any other command is a usage error with status 2.

### Implementation for User Story 5

- [X] T022 [US5] Add the `--ttl` scope check to `src/accounts/cli.py` immediately after `parse_args`, inside the existing `contextlib.redirect_stdout/redirect_stderr` block so the output lands on the injected streams: `if args.ttl is not None and args.command != "reset-token": parser.error("--ttl is only valid with the reset-token command")`. `parser.error` prints the usage message and the error line to stderr and exits 2, which is byte-for-byte the shape of the existing E13 usage failure, so no bespoke path is introduced (FR-043, E16, research.md R-13)

### Tests for User Story 5

- [X] T023 [P] [US5] Create `tests/test_preserved_behaviour.py` covering FR-043, FR-060, FR-061, FR-062, SC-011: for each of `register`, `login`, `unlock`, `passwd`, `delete`, and `reset`, `--ttl 60` exits 2 with a usage message on stderr and an empty stdout and leaves the store untouched; `python -m accounts --help` still yields exactly `{"--store", "--help"}` under the extraction `tests/test_cli_usage.py` uses, so `--ttl` is absent from help; `--store` is still accepted after the command name (`["login", "alice", "--store", PATH]`); the usage `choices` list now contains all seven command names; every status returned by the two new commands across all their paths is in `{0, 1, 2, 3}` and never 4; and on every new-command success path stderr is empty while on every failure path stdout is empty, with each message a single `"\n"`-terminated line
- [X] T024 [P] [US5] Create `tests/test_store_compatibility.py` covering FR-059: a hand-written `version: 1` store whose account records have no `reset_token` key loads with no complaint, behaves as "no outstanding token" (`reset` → `invalid token`, status 1), and accepts a freshly issued token; and strictness is preserved, not relaxed — each of `"reset_token": null`, a `reset_token` missing `expires_at`, a `reset_token` with an extra key, a `reset_token.salt` that is not base64 of 16 bytes, a `reset_token.verifier` that is not base64 of 32 bytes, `"expires_at": NaN`, `"expires_at": Infinity`, `"expires_at": true`, `"expires_at": "soon"`, and a misspelled `"reset_tokens": {}` makes **every** command exit 2 with a `not a valid store file:` diagnostic naming the account, the field, and the condition, and never a defaulted or ignored value
- [X] T025 [US5] Verify the preservation claim directly: run `pytest -q` over the nine untouched behaviour files (`tests/test_cli_usage.py`, `test_register.py`, `test_login.py`, `test_passwd.py`, `test_delete.py`, `test_lockout.py`, `test_store.py`, `test_passwords.py`, `test_end_to_end.py`, `test_performance.py`) and confirm all green, then confirm `git diff --stat tests/` lists only `test_requirement_coverage.py` plus the new files (SC-011)

**Checkpoint**: All three P1 stories are complete. The feature is shippable; the two P2 stories below are required behaviour but refine failure handling.

---

## Phase 6: User Story 3 - A rejected new password does not waste the token (Priority: P2)

**Goal**: A too-short new password is reported, nothing changes, and the token survives for an
immediate retry.

**Independent Test**: Issue a token, run `reset` with it and an 11-character password, confirm
status 2 with a diagnostic on stderr, then run it again with the **same** token and a
12-character password and confirm the reset succeeds.

### Implementation for User Story 3

- [X] T026 [US3] In `src/accounts/commands.py`, confirm and pin the length check's position in `reset`: it is evaluated **only after** the token has been accepted, and returns `Result(2, err=E1_SHORT_PASSWORD)` with `save=False` and no mutation of `record` — so the `reset_token` entry stays outstanding and usable within its window, and a wrong token with a too-short password reports `invalid token` and status 1 rather than the length error. This mirrors `passwd`'s verify-before-length (FR-028). The reused message is verbatim `password must be at least 12 characters` and the minimum is "at least 12 characters", counted in code points via the existing `_valid_password` (FR-053)

### Tests for User Story 3

- [X] T027 [P] [US3] Append to `tests/test_reset.py` for FR-053: a valid token with an 11-character password exits 2 with `password must be at least 12 characters` on stderr, empty stdout, the stored `salt`/`verifier` unchanged, and the `reset_token` entry byte-identical in the store (including `expires_at`); the immediately following attempt with the **same** token and a 12-character password exits 0 with `password reset`; a 12-character password is accepted and an 11-character one is not (the boundary); and a *wrong* token with a too-short password yields `invalid token` with status 1, never status 2
- [X] T028 [P] [US3] Append to `tests/test_reset_end_to_end.py`: SC-010 worked example 4 and SC-015 through the real CLI — `--ttl 60` token, a `short` password rejected with status 2, then the same token with `long enough secret` accepted with `password reset` and status 0

**Checkpoint**: A user who mistypes their new password can retry without going back to the administrator.

---

## Phase 7: User Story 4 - A reset command naming an unknown account says so (Priority: P2)

**Goal**: Both new commands report a missing account and exit 3 the way `unlock`, `passwd`, and
`delete` already do — and a `reset` that runs out of input says which line is missing rather than
treating it as empty.

**Independent Test**: Run both new commands against a username absent from the store and confirm
each writes a diagnostic naming the account to stderr and exits 3, with nothing on stdout and the
store untouched — and that `reset` does so without consuming a single line of standard input.

> Scope note: the end-of-input rules (FR-055) are grouped here rather than given a phase of their
> own. They are the spec's "Standard input ends early" edge case, not a user story, and they share
> this story's shape — a reset that cannot proceed names the specific missing thing instead of
> guessing — and the same `cli._dispatch` pre-pass.

### Implementation for User Story 4

- [X] T029 [US4] In `src/accounts/commands.py`, confirm `reset_token`'s existence check returns `Result(3, err=f"no such account: {username}\n")` — reusing E4's existing text verbatim — with empty stdout, `save=False`, and no token issued, before any token is generated (FR-045)
- [X] T030 [US4] Pin the pre-read checks for `reset` across `src/accounts/cli.py` and `src/accounts/commands.py`: the existence check precedes reading any line (the `_dispatch` pre-pass from T009 passes `None` for both lines when `username not in accounts`, so `commands.reset` returns E4 and status 3 without a single `readline` — structural, not guarded); then `token is None` returns `Result(2, err=E14_NO_TOKEN)` and `new is None` returns `Result(2, err=E9_NO_NEW_PASSWORD)`, both with `save=False`. Both end-of-input checks precede judging the token, so a wrong token with a missing password line reports the missing password (status 2), not `invalid token`. End of input is never an empty value; a present-but-empty token line *is* a value and simply matches nothing → `invalid token`, status 1 (FR-054, FR-055, research.md R-15)

### Tests for User Story 4

- [X] T031 [P] [US4] Append to `tests/test_reset_token.py` for FR-045: `reset-token nobody` against a store with no such account writes a diagnostic naming `nobody` to stderr, writes nothing to stdout, exits 3, and leaves the store file unchanged (no token issued, no write)
- [X] T032 [P] [US4] Append to `tests/test_reset.py` for FR-054 and FR-055: `reset nobody` exits 3 with a diagnostic naming `nobody` **and consumes no input** — pass a non-empty `io.StringIO` and assert `tell() == 0` / that its full contents remain readable; empty stdin for an existing account gives `no token on standard input` with status 2; a token line with no following password line gives `no new password on standard input` with status 2; a *wrong* token with a missing password line gives status 2 (the missing line), not status 1; a present-but-empty token line gives `invalid token` with status 1; and the store is unwritten in every one of these cases

**Checkpoint**: All five user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T033 Create `tests/test_reset_performance.py` covering SC-016: build a store holding 1,000 accounts and assert `reset-token` and `reset` each complete in under 1 second, following the shape of the existing `tests/test_performance.py`. Use the T002 measurement to sanity-check the margin (budget ≈ 0.15 s and ≈ 0.30 s of PBKDF2 respectively, plus a JSON load and atomic rewrite of a ~200 KB file)
- [X] T034 [P] Audit SC-017 across both new commands: every failure path (E1, E4, E9, E10–E12, E14, E15, E16, E17) writes a one-line diagnostic to stderr naming the specific rule or condition that failed, and no failure exits non-zero in silence. Add any missing assertion to the owning test file
- [X] T035 [P] Review the docstrings and comments added to `src/accounts/cli.py`, `commands.py`, `passwords.py`, and `store.py` so each new rule cites the requirement that forces it, matching the existing house style; in particular correct `_dispatch`'s "exactly the five commands" docstring and note why the clock is a parameter (plan.md Complexity Tracking) and why `--ttl` is suppressed (research.md R-13)
- [X] T036 Walk quickstart.md scenarios 1–6 by hand from the repository root and confirm each produces the stated statuses and exact text, including scenario 5's pre-feature store file and scenario 6's two `grep -c` checks returning no match
- [X] T037 Run the full `pytest` from the repository root and confirm it is green with no skipped test; confirm `git diff pyproject.toml` is empty (`dependencies` still `[]`, Principle I) and that `git diff --stat tests/` lists only `test_requirement_coverage.py` plus the six new files (SC-011, quickstart.md "Done when")
- [X] T038 Confirm SC-009 bookkeeping: `tests/test_requirement_coverage.py` passes and maps FR-001 – FR-062 with no gap in either direction, so all 24 new requirements (FR-039 – FR-062) are cited by at least one test and no test cites an identifier no spec defines

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**. T006 in particular must land before any new test file, or the existing coverage ledger fails on the first `FR-039` citation
- **User Stories (Phases 3–7)**: All depend on Foundational. Phase order follows spec priority: US1 (P1) → US2 (P1) → US5 (P1) → US3 (P2) → US4 (P2)
- **Polish (Phase 8)**: Depends on all five stories being complete

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational. Delivers the MVP
- **US2 (P1)**: Depends on Foundational; its implementation task T016 extends the `reset` function T011 creates, so in practice US1 lands first. Its tests are independently meaningful
- **US5 (P1)**: Depends on Foundational for the store schema (T004). T022 (`--ttl` scope) depends on T008 registering the option. Otherwise independent of US1–US4 — it asserts what did *not* change
- **US3 (P2)**: Depends on Foundational; T026 pins an ordering inside the `reset` function, so after US1
- **US4 (P2)**: Depends on Foundational; T030 pins the pre-pass `cli._dispatch` gains in T009, so after US1

### Within Each User Story

- Source changes before the tests that assert them (this project writes behaviour and its tests in the same change set, per the constitution's workflow gate 2, rather than strict red-first TDD)
- `passwords` → `store` → `commands` → `cli` is the import direction; follow it when a task touches more than one layer
- Tasks touching the same file are never marked [P] and must run in listed order

### Parallel Opportunities

- T001 and T002 (Setup) are independent
- T003, T004, T005 (Foundational) touch three different source files and can run together; T006 touches a fourth file and can run alongside them
- Within US1: T012, T013, T014 create three different new test files — fully parallel. T015 appends to T012's file, so it follows T012
- Within US2: T018 and T019 are parallel with T017; T020 follows T017 (same file); T021 follows T014 (same file)
- Within US5: T023 and T024 create two different new files — parallel. T025 is a verification gate and runs after both
- Within US3: T027 and T028 touch different files — parallel
- Within US4: T031 and T032 touch different files — parallel
- With multiple developers, US5 can be built entirely in parallel with US1/US2 once T004 and T008 exist, because it adds no behaviour to the new commands
- T034 and T035 in Polish are parallel; T036, T037, T038 are sequential gates

---

## Parallel Example: User Story 1

```bash
# After T007 - T011 (the source changes), launch the three new test files together:
Task: "Create tests/test_reset_token.py covering FR-039, FR-040, FR-041, FR-046, FR-047"
Task: "Create tests/test_reset.py covering FR-048, FR-049, FR-050"
Task: "Create tests/test_reset_end_to_end.py covering SC-010 examples 1-2 and SC-012"
```

## Parallel Example: Foundational Phase

```bash
# Four files, four independent changes:
Task: "Add new_token() to src/accounts/passwords.py"
Task: "Extend src/accounts/store.py with the optional reset_token key and rules 8-11"
Task: "Add E14/E15 diagnostics constants to src/accounts/commands.py"
Task: "Extend tests/test_requirement_coverage.py to FR-001 - FR-062"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup — baseline green, budget measured
2. Complete Phase 2: Foundational — **CRITICAL**, and T006 before any new test
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: register → `reset-token` → `reset` → `login` with the new password, old password rejected
5. The recovery path exists at this point, but **do not ship yet**: US2's single-use and expiry rules are part of the feature, not a hardening pass (spec, US2 "Why this priority"). A reset path with replayable tokens is worse than none

### Incremental Delivery

1. Setup + Foundational → the store can hold a token and the ledger spans both features
2. Add US1 → the two-command journey works → validate
3. Add US2 → tokens are single-use, unguessable, and expire → **first shippable point**
4. Add US5 → the five existing commands are proven unchanged and old stores still load
5. Add US3 → a mistyped password no longer wastes a token
6. Add US4 → unknown accounts and truncated input are named precisely
7. Polish → performance, quickstart walkthrough, full-suite and SC-009/SC-011 gates

### Parallel Team Strategy

1. Everyone completes Setup + Foundational together (T006 first)
2. Then:
   - Developer A: US1 → US2 (both extend `commands.reset`, so one owner)
   - Developer B: US5 (additive tests plus one `if` in `cli.py`; needs T004 and T008)
   - Developer C: US3 → US4 after A's T011 lands
3. Polish is shared, with T036–T038 run once at the end

---

## Notes

- [P] = different files, no dependencies. `commands.py` and `cli.py` are each touched by several
  stories, so tasks naming them are deliberately sequential
- Every new rule is cited by requirement identifier in the test that asserts it — that citation is
  what `tests/test_requirement_coverage.py` checks, and Principle III requires
- `invalid token` and `password reset` are fixed verbatim by the spec; `password must be at least
  12 characters`, `no such account: USERNAME`, and `no new password on standard input` are reused
  from 001 unchanged
- No store write on any failure path of either new command, and expired token records are never
  swept (research.md R-16)
- `pyproject.toml` must stay untouched: no runtime dependency may be added (Principle I)
- Commit after each task or logical group; stop at any checkpoint to validate a story on its own
