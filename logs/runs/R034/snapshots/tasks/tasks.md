# Tasks: Local Account Manager

**Input**: Design documents from `/specs/001-local-account-manager/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli-contract.md](./contracts/cli-contract.md), [quickstart.md](./quickstart.md)

**Tests**: Test tasks ARE included and are mandatory here. Constitution Principle III
("Every Requirement Is Testable") and SC-001 both require every one of FR-001–FR-038 to map to
a `pytest` test that fails when the requirement is unmet. Within each phase, write the test
tasks first and confirm they fail before the implementation tasks of that phase.

**Organization**: Tasks are grouped by user story (US1–US4 from spec.md) so each story can be
implemented, tested, and delivered independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project, `src/` layout fixed by the spec's recorded implementation constraint
(plan.md → Structure Decision):

- Package: `src/accounts/` — `__init__.py`, `__main__.py`, `cli.py`, `commands.py`, `store.py`, `passwords.py`
- Tests: `tests/` (flat), importable via `[tool.pytest.ini_options] pythonpath = ["src"]`
- Project metadata: `pyproject.toml` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton and a runnable `pytest` with no environment setup

- [ ] T001 Create the source and test tree at the repository root: `src/accounts/` and `tests/`, with an empty `src/accounts/__init__.py` (no re-exports, per plan.md Structure Decision)
- [ ] T002 Create `pyproject.toml` at the repository root with `requires-python = ">=3.11"` stated exactly once in the whole repo, `dependencies = []` (Constitution Principle I and the empty-runtime-manifest constraint), `pytest` declared only under a development extra, and `[tool.pytest.ini_options] pythonpath = ["src"]` so a bare `pytest` from the root works
- [ ] T003 [P] Create `tests/conftest.py` with a `store_path` fixture returning `tmp_path / "store.json"` (a path that does not exist yet) and a `run_cli(argv, stdin_text="")` helper that calls `accounts.cli.main(argv, io.StringIO(stdin_text), io.StringIO(), io.StringIO())` and returns `(status, stdout_text, stderr_text)` — the in-process seam from research.md R-08
- [ ] T004 Verify the toolchain: `python3 --version` reports 3.11 or newer, and a bare `pytest` from the repository root exits cleanly collecting the (currently empty) `tests/` directory

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The three modules every user story depends on — the one-way password
transformation, the strict/atomic store file, and the process-facing CLI shell (argv, streams,
exit status, stdin reads). No command behaviour lives here.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for the foundational modules

- [ ] T005 [P] Create `tests/test_passwords.py` covering FR-036 and FR-037 (name the FR ids in test names or docstrings): `new_salt()` returns 16 distinct random bytes across calls; two accounts registered with an identical password hold different verifiers; `derive()` is deterministic for a given (password, salt); `verify()` is true for the right password and false for a wrong one; the password string never appears in the returned verifier bytes
- [ ] T006 [P] Create `tests/test_store.py` covering FR-002, FR-006, FR-007, FR-008, FR-034 and FR-038 (FR ids in test names or docstrings): a missing path loads as `{}` with **no file created**; a round-trip load/save preserves records; each of the seven load-time validation rules in data-model.md raises `StoreError` naming the path — top level not an object, `version` absent or `!= 1`, `accounts` absent or not an object, a record with a missing key, a record with an **unknown** key, `salt`/`verifier` not strict base64 or not decoding to **16 and 32 bytes** respectively, `failed_logins` not an int / negative / a `bool`, `locked` not a boolean; unreadable path (e.g. a directory, or mode `0000`) raises `StoreError`; a malformed store is **not** overwritten by a failed run; a newly created store file has mode `0600`; a missing parent directory raises `StoreError` on save
- [ ] T007 [P] Create `tests/test_cli_usage.py` covering FR-001, FR-003, FR-004, FR-005 and FR-035 (FR ids in test names or docstrings): missing `--store`, missing command, unknown command (`frobnicate`), missing username, and one extra positional argument each produce a usage diagnostic on **stderr** with status **2** and empty stdout (E13); no password is ever accepted as an argv element; every success path leaves stderr empty and every failure path leaves stdout empty; the `Result` invariants hold — `code == 0` implies `err == ""`, `code != 0` implies `out == "" and err != ""`, and `code` is only ever one of `0, 1, 2, 3, 4`; store-read failures surface as E10 `cannot read store file: PATH: REASON` and E11 `not a valid store file: PATH: REASON` with status 2

### Implementation of the foundational modules

- [ ] T008 [P] Implement `src/accounts/passwords.py` with module constants `ALGORITHM = "sha256"`, `ITERATIONS = 600_000`, `SALT_BYTES = 16`, `KEY_BYTES = 32` (constants, never options or stored fields — Principle IV), `new_salt()` using `secrets.token_bytes(16)`, `derive(password: str, salt: bytes) -> bytes` using `hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000, dklen=32)`, and `verify(password, salt, verifier) -> bool` using `hmac.compare_digest` (research.md R-02)
- [ ] T009 [P] Implement `src/accounts/store.py` with `StoreError(Exception)`; `load(path) -> dict[str, dict]` that returns `{}` for a missing path, parses UTF-8 JSON strictly, and enforces all seven validation rules from data-model.md (`version == 1`; `accounts` an object; every record carrying **exactly** the keys `salt`, `verifier`, `failed_logins`, `locked`; `salt`/`verifier` strict-base64 decoding to **16** and **32** bytes; `failed_logins` an `int` with `0 <= failed_logins` and **not a `bool`**; `locked` a `bool`), raising `StoreError` naming the path and the specific condition on any failure — and never defaulting, coercing, or treating a bad file as empty (Principle II, FR-007); and `save(path, accounts)` writing `{"version": 1, "accounts": accounts}` as `json.dump(..., indent=2, sort_keys=True)` plus one trailing newline via `tempfile.mkstemp(dir=<store parent>)` → `os.chmod(0o600)` → `flush` + `os.fsync` → `close` → `os.replace`, unlinking the temp file and raising `StoreError` on any failure (research.md R-05, FR-008, FR-038). Catch only `OSError`, `json.JSONDecodeError`, and `StoreError`; no bare `except`
- [ ] T010 Create `src/accounts/commands.py` with the frozen `Result` dataclass only — `code: int`, `out: str = ""`, `err: str = ""`, `save: bool = False` — documenting that `save` is stated by the command (not inferred from `code`) because a failed login must persist while every other non-zero outcome must not (FR-006). No command functions yet; those arrive with their stories
- [ ] T011 Implement `src/accounts/cli.py` as the sole stream writer and the only module that touches the process (depends on T008, T009, T010): `main(argv, stdin, stdout, stderr) -> int` building `argparse.ArgumentParser(prog="python -m accounts")` with a **required** `--store PATH` option and positionals `command` (`choices` = the five exact lower-case names `register`, `login`, `unlock`, `passwd`, `delete`) and `username`; catch `SystemExit` and return its code so usage errors are observable in-process as status 2 (research.md R-03); a `_read_password(stream) -> str | None` helper using a single `stream.readline()` that returns `None` on `""` (end of input) and otherwise strips **exactly one** trailing `"\n"` with `line[:-1] if line.endswith("\n") else line`, preserving leading/trailing spaces, `\r`, and non-ASCII characters (research.md R-06, FR-017); `store.load` wrapped so `StoreError` becomes E10/E11 text with status 2; dispatch on the command name to `commands.*`, writing `Result.out` to stdout and `Result.err` to stderr (never the reverse), calling `store.save` only when `Result.save` is true, mapping a `StoreError` from the save to E12 `cannot write store file: PATH: REASON` with status 2, and returning `Result.code`. A command name with no implementation yet must `raise AssertionError(f"unhandled command: {name}")` — an unreachable state, removed in T033 once all five exist
- [ ] T012 Create `src/accounts/__main__.py` containing only `sys.exit(cli.main(sys.argv[1:], sys.stdin, sys.stdout, sys.stderr))` under a `if __name__ == "__main__":` guard — no logic (plan.md Structure Decision)

**Checkpoint**: `pytest tests/test_passwords.py tests/test_store.py tests/test_cli_usage.py` passes; `PYTHONPATH=src python -m accounts --store /tmp/x login alice` reaches dispatch. User story work can begin.

---

## Phase 3: User Story 1 - Register an account and sign in (Priority: P1) 🎯 MVP

**Goal**: An operator can create a named account whose password is supplied only on standard
input, and later prove they hold that password, with the account persisting across processes.

**Independent Test**: Register `alice` into a fresh store path (expect `registered alice` on
stdout, status 0, store file created mode 0600); in a **separate process** log in with the same
password (expect `ok`, status 0) and with a different password (expect `invalid credentials` on
stderr, empty stdout, status 1).

### Tests for User Story 1 ⚠️ Write first, confirm they fail

- [ ] T013 [P] [US1] Create `tests/test_register.py` covering FR-009–FR-013 (FR ids in test names or docstrings): success writes exactly `registered alice\n` to stdout with status 0 and creates the store; username accepted only when it matches `\A[A-Za-z0-9_]{3,32}\Z` — boundary cases **3 and 32 characters valid, 2 and 33 rejected**, `bad-name` rejected, and a non-ASCII alphanumeric such as `éé1` or `١٢٣` rejected — each with E2 `username must be 3 to 32 characters of letters, digits, and underscores` and status 2; password accepted only at **12 characters or more** counted in **characters, not bytes** (12 valid, 11 rejected) with E1 `password must be at least 12 characters` and status 2; a duplicate username gives E3 `account already exists: alice`, status 3, and leaves the existing record byte-identical; end of input where the password was required gives E8 `no password on standard input`, status 2, and creates no account; and the two FR-013 precedences — invalid username **plus** short password → status 2 (E2), invalid username **plus** existing account → status 2 (E2), not 3
- [ ] T014 [P] [US1] Create `tests/test_login.py` covering FR-014–FR-018 (FR ids in test names or docstrings): correct password on an unlocked account writes exactly `ok\n` to stdout with status 0; a wrong password writes exactly `invalid credentials` to stderr with status 1 and empty stdout; an **unknown username** produces the identical message and status 1, revealing nothing about absence (FR-016), including a username whose format is invalid; comparison is exact and case-sensitive over the full password, with leading/trailing spaces and non-ASCII characters significant and only the single terminating newline removed (FR-017); extra stdin lines beyond the one needed are ignored; end of input gives E8 `no password on standard input` with status 2; a failed login's incremented `failed_logins` is persisted while a successful login resets it to 0 (FR-006, FR-021)
- [ ] T015 [P] [US1] Create `tests/test_end_to_end.py` running `[sys.executable, "-m", "accounts", ...]` through `subprocess.run` with `env["PYTHONPATH"] = "src"`: the **four worked examples** from contracts/cli-contract.md reproduced exactly — stdout text, stderr text, status, and nothing extra on either stream (SC-002); account data written by one invocation read by a later separate invocation (SC-005); no test password found anywhere in the store file's **bytes** and no password present in any element of the command line used (SC-006); and `stat` of a freshly created store reporting mode `600` (FR-038)

### Implementation for User Story 1

- [ ] T016 [US1] Add username and password validation plus `register` to `src/accounts/commands.py`: `_valid_username` as an explicit `re.fullmatch(r"[A-Za-z0-9_]{3,32}", username)` test (not `str.isalnum()`, which accepts non-ASCII letters and digits — data-model.md), `_valid_password` as `len(password) >= 12` over code points, and `register(accounts, username, password_or_none) -> Result` following R-07's order exactly: username format (E2) → password present (E8) → password length (E1) → already exists (E3) → insert `{"salt": …, "verifier": …, "failed_logins": 0, "locked": False}` with a fresh `passwords.new_salt()` and return `Result(0, out=f"registered {username}\n", save=True)`
- [ ] T017 [US1] Add `login` to `src/accounts/commands.py` following R-07's order for the unlocked paths: account absent → `Result(1, err="invalid credentials\n")` with **no save** → password present (E8, status 2, no save) → `passwords.verify`; on success set `failed_logins = 0` and return `Result(0, out="ok\n", save=True)`; on failure increment `failed_logins` by one and return `Result(1, err="invalid credentials\n", save=True)` so FR-006's "a failed login persists its count" holds. The lock gate and the lock-at-5 threshold are **deliberately out of scope here** — they arrive in T021/T022 with User Story 2
- [ ] T018 [US1] Wire `register` and `login` into the dispatch in `src/accounts/cli.py`: each reads **exactly one** stdin line via `_read_password` before being called, passing `None` through on end of input so `commands` owns the E8 diagnostic; no further reads

**Checkpoint**: `pytest tests/test_register.py tests/test_login.py tests/test_end_to_end.py` passes. US1 is a shippable MVP — register, login, persistence, and the four worked examples all hold.

---

## Phase 4: User Story 2 - Lock out password guessing, and recover (Priority: P2)

**Goal**: An account stops accepting logins after five consecutive failures, and an operator
with access to the store can clear that state.

**Independent Test**: Register an account, submit five wrong passwords (the fifth still reports
`invalid credentials` with status 1), then submit the **correct** password and confirm
`account locked` on stderr with status 4. Run `unlock`, then confirm the correct password logs
in again with status 0.

### Tests for User Story 2 ⚠️ Write first, confirm they fail

- [ ] T019 [P] [US2] Create `tests/test_lockout.py` covering FR-019–FR-025 (FR ids in test names or docstrings) and SC-004: four consecutive failures each give `invalid credentials`/status 1 and a fifth login with the **correct** password still succeeds with `ok`/status 0; five consecutive failures lock the account while the fifth attempt itself reports `invalid credentials` with status **1**, not 4; a login to a locked account writes exactly `account locked` to stderr with status **4** whether the password is correct or wrong, and never writes `ok` (E7, FR-020); a successful login resets `failed_logins` to zero so five further non-consecutive failures are needed (FR-021); `unlock` on a locked account exits 0 with **empty stdout**, clears `locked`, zeroes the count, and restores login; `unlock` on an account that is **not** locked also exits 0 and leaves it usable (FR-022); `unlock` reads **nothing** from standard input — passing a stdin stream that raises on read still succeeds; `unlock` for a missing account gives E4 `no such account: carol` with status 3 **before** any read (FR-034); and no command other than `unlock` clears a lock, no command other than `login` sets one (FR-023)
- [ ] T020 [P] [US2] Extend `tests/test_lockout.py`'s sibling coverage of FR-024 and FR-025 — a failed `passwd` and a failed `delete` leave `failed_logins` unchanged and never lock the account, and a **locked** account still accepts a `passwd` and a `delete` from a caller supplying the correct current password. Write these now as `xfail`-free tests that will pass once US3/US4 land, or keep them in this file and run them at the US3/US4 checkpoints — record the choice in the test module docstring

### Implementation for User Story 2

- [ ] T021 [US2] Extend `login` in `src/accounts/commands.py` with the lock gate and threshold, in R-07's order: account exists? → **locked? → `Result(4, err="account locked\n")` with no save** (before the password is even read, so a correct password can never produce `ok`) → password present → verify; on failure increment `failed_logins` and, when it **reaches 5**, set `locked = True` while still returning status 1 with `invalid credentials`; on success reset `failed_logins = 0` and leave `locked` untouched (only `unlock` clears it)
- [ ] T022 [US2] Add `unlock(accounts, username) -> Result` to `src/accounts/commands.py`: account absent → `Result(3, err=f"no such account: {username}\n")`; otherwise set `locked = False` and `failed_logins = 0` and return `Result(0, save=True)` with **empty stdout** — exiting 0 even when the account was not locked. It takes no password parameter at all
- [ ] T023 [US2] Wire `unlock` into the dispatch in `src/accounts/cli.py` so it is called with **zero** stdin reads and the existence check runs before any read (FR-034, contract "Standard-input protocol")

**Checkpoint**: `pytest tests/test_lockout.py` passes alongside all earlier suites. US1 and US2 both work independently.

---

## Phase 5: User Story 3 - Change a password (Priority: P3)

**Goal**: The holder of an account can replace its password by proving knowledge of the current
one, without destroying and recreating the account.

**Independent Test**: Register an account, run `passwd` supplying the current password then a
new one (status 0, no output), then confirm the new password logs in with `ok`/status 0 and the
old one fails with `invalid credentials`/status 1.

### Tests for User Story 3 ⚠️ Write first, confirm they fail

- [ ] T024 [P] [US3] Create `tests/test_passwd.py` covering FR-026–FR-029 (FR ids in test names or docstrings): success reads **two** lines (current, then new), exits 0 with empty stdout and empty stderr, and afterwards the new password verifies while the previous one does not (FR-029); a wrong current password writes exactly `invalid credentials` with status 1 and leaves the stored password working; a new password shorter than **12 characters** gives E1 `password must be at least 12 characters` with status 2 and leaves the stored password working; a missing account gives E4 `no such account: carol` with status 3 **before any stdin read**; end of input after the current password gives E9 `no new password on standard input` with status 2; the FR-028 ordering consequence — a **wrong current password plus a short new password exits 1 (E5), not 2**, so a status-2 reply can never confirm the current password was right; a new password identical to the current one is accepted; and a successful change regenerates the salt so the stored verifier changes, while `failed_logins` and `locked` are left untouched (FR-024, FR-025)

### Implementation for User Story 3

- [ ] T025 [US3] Add `passwd(accounts, username, current_or_none, new_or_none) -> Result` to `src/accounts/commands.py` in R-07's order — exists? (E4, status 3) → current present (E8) → new present (E9) → verify current (E5, status 1) → new length (E1, status 2) → replace — generating a **fresh** `passwords.new_salt()` and a new verifier on success and returning `Result(0, save=True)` with empty stdout. It must not read, set, or clear `locked`, and must not touch `failed_logins` (FR-023, FR-024, FR-025)
- [ ] T026 [US3] Wire `passwd` into the dispatch in `src/accounts/cli.py`: the existence check runs **before** any stdin read, then **two** `_read_password` calls in order (current, then new), with `None` passed through for each so `commands` owns the E8/E9 distinction

**Checkpoint**: `pytest tests/test_passwd.py` passes alongside all earlier suites. US1–US3 each work independently.

---

## Phase 6: User Story 4 - Delete an account (Priority: P4)

**Goal**: The holder of an account can remove it and all its state from the store by proving
knowledge of its password.

**Independent Test**: Register an account, delete it supplying the correct password (status 0),
and confirm a later login for that username fails with `invalid credentials`/status 1 and that
the username can be registered again. Separately confirm a delete with a wrong password leaves
the account intact.

### Tests for User Story 4 ⚠️ Write first, confirm they fail

- [ ] T027 [P] [US4] Create `tests/test_delete.py` covering FR-030–FR-033 (FR ids in test names or docstrings): success reads **one** line, exits 0 with empty stdout, and removes the record and all of its state; afterwards a login for that username fails per FR-016 with `invalid credentials`/status 1 and the username is **available for registration again** (FR-032); a wrong password writes exactly `invalid credentials` with status 1 and retains the account unchanged so it still logs in; a missing account gives E4 `no such account: carol` with status 3 **before any stdin read**; end of input gives E8 `no password on standard input` with status 2; deleting `alice` leaves `bob`'s verifier, salt, `failed_logins`, and `locked` byte-identical (FR-033); and a **locked** account is still deletable with the correct password (FR-025)

### Implementation for User Story 4

- [ ] T028 [US4] Add `delete(accounts, username, password_or_none) -> Result` to `src/accounts/commands.py` in R-07's order — exists? (E4, status 3) → password present (E8) → verify (E5, status 1) → `del accounts[username]` → `Result(0, save=True)` with empty stdout. It must not touch `failed_logins` or `locked` on any other account and must not count a failed attempt against the login counter (FR-024)
- [ ] T029 [US4] Wire `delete` into the dispatch in `src/accounts/cli.py`: existence check before any read, then **one** `_read_password` call

**Checkpoint**: All four user stories are independently functional; all five commands implemented.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The success criteria that span stories, plus the constitution's merge gates

- [ ] T030 [P] Extend `tests/test_end_to_end.py` for SC-005 across every mutating command: account data written by `passwd`, `unlock`, and `delete` in one process is observed by a later separate process, and the store file's mode stays `0600` after an atomic replace
- [ ] T031 [P] Add an SC-001 coverage check to `tests/` (e.g. `tests/test_requirement_coverage.py`): collect the `FR-0NN` identifiers referenced across `tests/` and assert all **38** of FR-001–FR-038 appear, so a requirement that loses its test fails the suite rather than decaying silently
- [ ] T032 [P] Add an SC-007 performance test: build a store of **1,000 accounts** (constructing records directly rather than running 1,000 registrations, so the test stays fast) and assert each of the five commands completes in **under 1 second**, against the budget of one ~145 ms PBKDF2 derivation plus JSON load and atomic rewrite
- [ ] T033 Remove the `raise AssertionError(f"unhandled command: {name}")` fallback from `src/accounts/cli.py` now that all five commands are dispatched, and confirm `cli.py` remains the only module in `src/accounts/` that reads argv, writes a stream, or returns an exit status (FR-004 gate)
- [ ] T034 Review `src/accounts/` against Constitution Principles I–IV: no third-party runtime import anywhere, `pyproject.toml` `dependencies` still empty, no bare `except:` or `except Exception: pass` (only `OSError`, `json.JSONDecodeError`, `StoreError` caught, each re-raised with the path), and no abstraction, option, or extension point that no requirement in spec.md needs
- [ ] T035 Run every command sequence in [quickstart.md](./quickstart.md) — Scenarios 1–4 and all the cross-cutting checks (secret absence from the store's bytes, mode `600`, distinct verifiers for identical passwords, loud store failures, missing-store behaviour, whitespace and non-ASCII passwords, ignored extra stdin lines, the five usage errors) — and confirm each produces exactly the stated stdout, stderr, and exit status
- [ ] T036 Run the full suite with a bare `pytest` from the repository root and confirm **0 failed, 0 skipped** (Constitution gate "Full suite green"); any skip must carry a written reason and a re-enable condition

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — starts immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational only
- **US2 (Phase 4)**: Depends on Foundational; T021 edits the `login` function created in T017, so US2 must follow US1 in practice (US2's lockout behaviour is defined on top of login)
- **US3 (Phase 5)**: Depends on Foundational only — `passwd` is a new function; its tests use `login` to confirm the change took effect, so running it after US1 is the convenient order
- **US4 (Phase 6)**: Depends on Foundational only — `delete` is a new function; its tests use `login`/`register` for confirmation
- **Polish (Phase 7)**: Depends on all four stories

### User Story Dependencies

- **US1 (P1)**: Independent. The MVP.
- **US2 (P2)**: Behaviourally layered on US1's `login` (the lock gate and threshold are added to that function). Independently *testable*: its test file drives only lockout and unlock behaviour.
- **US3 (P3)**: Independent of US2 — `passwd` never reads or writes `locked`. Uses `login` for verification in its tests.
- **US4 (P4)**: Independent of US2 and US3 — `delete` never reads or writes `locked`. Uses `register`/`login` for verification in its tests.

### Within Each User Story

- Tests are written and confirmed **failing** before the implementation tasks of that phase
- `passwords.py` and `store.py` (foundational) before any command function
- Command functions in `commands.py` before the `cli.py` wiring that dispatches to them
- Story complete and its checkpoint green before moving to the next priority

### File-contention notes (why some tasks are not [P])

- `src/accounts/commands.py` is touched by T010, T016, T017, T021, T022, T025, T028 — these must run sequentially
- `src/accounts/cli.py` is touched by T011, T018, T023, T026, T029, T033 — these must run sequentially
- `tests/test_end_to_end.py` is created in T015 and extended in T030 — T030 must follow T015
- `tests/test_lockout.py` is created in T019 and extended in T020

### Parallel Opportunities

- T003 runs alongside T001/T002 once the directories exist
- T005, T006, T007 (three test files) in parallel; T008 and T009 (two independent modules) in parallel
- T013, T014, T015 (three test files) in parallel
- T030, T031, T032 (three independent test files) in parallel
- Across stories: once Foundational is green, one developer can take US1+US2 (both centred on `login`) while another takes US3 and a third takes US4 — the three command functions are disjoint; only the `cli.py` wiring tasks need serializing

---

## Parallel Example: User Story 1

```bash
# Write all three US1 test files together, then confirm they fail:
Task: "Create tests/test_register.py covering FR-009–FR-013"
Task: "Create tests/test_login.py covering FR-014–FR-018"
Task: "Create tests/test_end_to_end.py covering SC-002, SC-005, SC-006"

pytest tests/test_register.py tests/test_login.py tests/test_end_to_end.py   # expect failures

# Then implement sequentially (all three touch commands.py / cli.py):
#   T016 register → T017 login → T018 cli wiring
```

## Parallel Example: Foundational

```bash
# Tests in parallel:
Task: "Create tests/test_passwords.py covering FR-036, FR-037"
Task: "Create tests/test_store.py covering FR-002, FR-006–FR-008, FR-034, FR-038"
Task: "Create tests/test_cli_usage.py covering FR-001, FR-003–FR-005, FR-035"

# Modules in parallel (disjoint files, no imports of each other):
Task: "Implement src/accounts/passwords.py"
Task: "Implement src/accounts/store.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run quickstart.md Scenario 1 and `pytest tests/test_register.py tests/test_login.py tests/test_end_to_end.py`
5. The tool now registers accounts, verifies passwords, and persists across processes — demonstrable value

### Incremental Delivery

1. Setup + Foundational → three modules, a dispatching CLI, and the usage/store/secret suites green
2. Add US1 → register + login → **MVP**, four worked examples reproduce
3. Add US2 → lockout + unlock → guessing is bounded and recoverable (SC-004)
4. Add US3 → passwd → credentials rotatable
5. Add US4 → delete → store hygiene
6. Polish → SC-001 coverage check, SC-005 cross-process checks, SC-007 performance, constitution gates

Each story adds value without breaking the previous ones; every phase ends with the full suite green.

### Parallel Team Strategy

1. Everyone on Setup + Foundational first — nothing else can start
2. Then: Developer A takes US1 then US2 (both own `login`); Developer B takes US3; Developer C takes US4
3. Serialize only the `cli.py` wiring tasks (T018, T023, T026, T029) and the `commands.py` additions; the test files and command bodies are disjoint

---

## Notes

- Tests are mandatory in this feature, not optional: Principle III and SC-001 require all 38 functional requirements to be covered by tests that fail when the requirement is unmet, and every FR id must be discoverable in a test name or docstring
- Error-path tests assert **both** the exact message and the exit status (Principle III)
- Only statuses `0, 1, 2, 3, 4` may ever be returned (FR-005); store-file failures use **2** (research.md R-04)
- The two verbatim messages `invalid credentials` and `account locked` are fixed by the spec and must match exactly; the E1–E12 texts are fixed by contracts/cli-contract.md and are asserted by tests
- No password may appear in `argv`, in the store file's bytes, or in any diagnostic (FR-003, FR-037, SC-006)
- `[P]` tasks touch different files and have no incomplete dependencies
- Commit after each task or logical group; stop at any checkpoint to validate a story independently
