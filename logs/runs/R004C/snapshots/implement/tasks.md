---

description: "Task list for feature 002-password-reset"
---

# Tasks: Password Reset by One-Time Token

**Input**: Design documents from `/specs/002-password-reset/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/cli-contract.md](./contracts/cli-contract.md),
[contracts/store-format.md](./contracts/store-format.md),
[quickstart.md](./quickstart.md), `.specify/memory/constitution.md` v1.0.0

**Tests**: Test tasks are included and are **not** optional for this feature.
Constitution Principle III ("Every Requirement Is Testable") makes an unmapped
requirement a blocker, and the spec states its own Independent Tests per story.
Test ids below are taken verbatim from plan.md's
[Requirement-to-test mapping](./plan.md#requirement-to-test-mapping) and
[Security requirement mapping](./plan.md#security-requirement-mapping) — do not
rename them.

**Organization**: Tasks are grouped by user story so each story can be
implemented, tested and demonstrated on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 … US5)
- Exact file paths are given in every task

## Path Conventions

Single project, already in place from feature 001. **No file is added to `src/`
and none is removed** (plan.md §Project Structure):

- Source: `src/accounts/{cli,store,crypto,validation}.py` — extended in place
- Untouched source: `src/accounts/{__init__,__main__,errors}.py`
- Tests: `tests/` at repository root; `pytest.ini` already sets
  `pythonpath = src` and `testpaths = tests`
- Run the tool as `PYTHONPATH=src python -m accounts` (stdlib only, no install)

**Reference constants** (quote these verbatim in code and tests — they are the
contract, not defaults): token = `secrets.token_urlsafe(16)` → exactly 128 bits,
22 characters, alphabet `[A-Za-z0-9_-]`; `--ttl` format `[0-9]{1,5}` then range
`1 … 86400`, default `900`; `expires_ms` integer `1 … 253402300799000`;
password 12–1 024 characters; input line ≤ 4 096 bytes; store ≤ 8 MiB;
≤ 10 000 accounts; serialised `reset` object = 174 bytes; scrypt
`n=2**17, r=8, p=1, dklen=32, maxmem=192 MiB`; salt = 16 bytes.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the untouched-baseline evidence that FR-040 / SC-019 are
measured against. There is no project to initialise — feature 001 ships the
package, `pytest.ini` and `requirements-dev.txt`.

- [X] T001 Run the full existing suite in `tests/` from the repository root (`python -m pytest -m "not slow"` then `python -m pytest`) and record the passing baseline in the task notes; this is the "before" half of SC-019 and must be green before any edit
- [X] T002 [P] Confirm the dependency position is unchanged: `requirements-dev.txt` lists `pytest` only, `pytest.ini` needs no edit, and the single new import this feature is permitted to add anywhere under `src/accounts/` is `time` (plan.md §Technical Context, Principle I)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared mechanisms every user story needs — token generation,
`--ttl` validation, stored-reset validation, the stdin line reader, the
seven-command argument surface, and the test helpers that keep token literals
out of the repository.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Add `TOKEN_BYTES = 16` and `new_token()` returning `secrets.token_urlsafe(TOKEN_BYTES)` to `src/accounts/crypto.py` — exactly 128 bits of entropy, 22 characters, alphabet `A–Z a–z 0–9 - _`, no padding; the function generates and returns only and MUST NOT persist, log or echo the value (SR-013, SR-014, A-023). Do **not** modify `verify`, `dummy_verify`, `new_salt` or `hash_password`: they are reused as they stand
- [X] T004 [P] Add to `src/accounts/validation.py`: `TTL_DEFAULT = 900`, `TTL_MIN = 1`, `TTL_MAX = 86400`, `EXPIRES_MS_MAX = 253402300799000`, a module-level `TTL_PATTERN = re.compile(r"[0-9]{1,5}")`, and `validate_ttl(text)` which applies `re.fullmatch` **before** `int()` and then checks `TTL_MIN <= value <= TTL_MAX`, raising `AccountsError(2, "error: invalid ttl: expected a whole number of seconds from 1 to 86400, received '%s'" % sanitize_for_message(text))` otherwise. The regex-before-`int()` order is mandatory: `int()` accepts Unicode digits, surrounding whitespace and a leading sign (SR-010, FR-022, research R15). `--ttl 0060` is accepted as 60 by design (plan.md flagged note 4)
- [X] T005 [P] Extend record validation in `src/accounts/store.py`: add `RESET_KEYS = frozenset(("kdf", "n", "r", "p", "dklen", "salt", "hash", "expires_ms"))`, make `validate_record` accept exactly two field sets — `RECORD_KEYS` or `RECORD_KEYS | {"reset"}` — and validate the `reset` interior against the store-format table: `kdf` exactly `"scrypt"`; `n` a power of two in `2 … 1048576`; `r` in `1 … 32`; `p` in `1 … 16`; `dklen` in `16 … 64`; `salt` padded standard-alphabet base64 decoding to exactly 16 bytes; `hash` base64 decoding to exactly `dklen` bytes; `expires_ms` an integer in `1 … 253402300799000` checked with the existing `_in_range` so `True`/`False` are refused; and the `n * r` `maxmem` cross-field rule via `crypto.fits_maxmem`. One invalid `reset` object returns a reason and so fails the **whole** load with status 5 — never repaired, defaulted, skipped or partially loaded, and a malformed `expires_ms` is **never** read as "not expired" (SR-010, contracts/store-format.md §Validation discipline)
- [X] T006 Extract the stdin reader in `src/accounts/cli.py` into `read_line(kind, missing_message)` and keep `read_password_line(expected, received)` as a thin wrapper passing `kind="password"` and its present, **byte-identical** missing-password message. The byte cap stays `sys.stdin.buffer.readline(validation.MAX_LINE_BYTES + 1)` so an over-long line is refused, never truncated; `kind` parameterises `error: {kind} line too long: expected at most 4096 bytes before the line terminator` and `error: {kind} line is not valid UTF-8 text`. This is a **pure extraction** — the only edit this feature makes to code the five existing commands execute (research R16, FR-040)
- [X] T007 Update the command surface in `src/accounts/cli.py`: `COMMANDS = ("register", "login", "unlock", "passwd", "delete", "reset-token", "reset")`, `USAGE = "usage: python -m accounts --store PATH {register|login|unlock|passwd|delete|reset-token|reset} USERNAME [--ttl SECONDS]"`, and `STDIN_LINES` gains `"reset-token": 0` and `"reset": 2`. These are the only two existing strings this feature may change (A-025, FR-040); the unknown-command message is generated from `COMMANDS` and follows automatically
- [X] T008 Add `--ttl` to the single parser in `src/accounts/cli.py` `parse_args`: `parser.add_argument("--ttl", action="append", default=None)` with **no** `type=` converter so the raw string reaches validation, keeping `allow_abbrev=False` and `add_help=False` (so `--tt` stays an error). After parsing, raise `AccountsError(2, USAGE)` if `--ttl` was given more than once or given with any command other than `reset-token`, then collapse it to `args.ttl = args.ttl[0]` or `None` (FR-021, research R15)
- [X] T009 [P] Add feature-002 test helpers to `tests/conftest.py`: synthetic token literals (`SYNTHETIC_TOKEN`, a wrong-token literal, and a 4 097-byte over-long token line), a `reset_material(**overrides)` builder returning the eight-key `reset` dict from synthetic base64 salt/hash plus an `expires_ms`, and an `issue_token(store_path, username, ttl=None)` helper that runs the real `reset-token` and returns the token read from stdout. Every real token value is read at runtime through this one helper — no issued token appears as a literal anywhere in the repository (SR-013, SC-015)
- [X] T010 Update `tests/test_cli_contract.py` for the two A-025 strings only (the usage line and the unknown-command enumeration) and add `test_fr020_seven_commands_accepted` asserting all seven names are accepted and that no eighth name is; change **no other assertion** in this file (SC-019, FR-020)

**Checkpoint**: Foundation ready — `python -m pytest -m "not slow"` is green again with the two updated contract strings, and user story work can begin.

---

## Phase 3: User Story 1 - Recover an account with an issued token (Priority: P1) 🎯 MVP

**Goal**: An administrator issues a one-time token with `reset-token` and reads
it off stdout; a later, separate invocation redeems it with `reset` and a new
password. The new password works from then on; the old one does not.

**Independent Test**: Register an account into a fresh store, issue a token,
then in a separate invocation redeem it with a new password, confirming the
printed output and exit status of each step plus that the new password verifies
(`ok`, 0) and the old one does not (`invalid credentials`, 1). Needs nothing
from the other stories. Automated as `tests/test_reset_token.py` and
`tests/test_reset.py`.

### Implementation for User Story 1

- [X] T011 [US1] Add `import time` and `_new_reset(token, ttl)` to `src/accounts/cli.py`, returning the eight-key reset dict: `kdf`/`n`/`r`/`p`/`dklen` from the module's **current** `crypto` parameters (`crypto.KDF_NAME`, `crypto.N`, `crypto.R`, `crypto.P`, `crypto.DKLEN`), `salt` = `crypto.b64encode(crypto.new_salt())` generated **fresh per issuance** and never the account's password salt, `hash` = `crypto.b64encode(crypto.hash_password(token, salt, ...))`, and `expires_ms = int(time.time() * 1000) + ttl * 1000` (SR-013, FR-028, data-model.md §The `reset` field)
- [X] T012 [US1] Implement `cmd_reset_token(args)` in `src/accounts/cli.py` in exactly this check order: `validation.validate_username` (2) → `validation.validate_ttl(args.ttl)` or `TTL_DEFAULT` when absent (2) → `store.locked_store` + `store.load` (5) → account exists else `_no_such_account` (3) → `record["reset"] = _new_reset(token, ttl)` (plain assignment, which is what makes "at most one outstanding token" structural and replaces any previous one) → `_save` → write the token plus one `\n` to stdout → return 0. It MUST read **nothing** from stdin and succeed with the stream closed (FR-021 … FR-025, FR-028, FR-029, research R14)
- [X] T013 [US1] Add `_reset_is_valid(token, record, now_ms)` to `src/accounts/cli.py`: when `"reset"` is absent **or** `record["reset"]["expires_ms"] < now_ms`, spend `crypto.dummy_verify(token)` and return `False`; otherwise return `crypto.verify(token, record["reset"])`, which reuses feature 001's `hmac.compare_digest` path unchanged. `now_ms = int(time.time() * 1000)` is read in the attempting invocation and never carried over (FR-030, SR-014, SR-016, research R17)
- [X] T014 [US1] Implement `cmd_reset(args)` in `src/accounts/cli.py` in exactly this check order: `validate_username` (2) → `read_line("token", "error: missing reset input: expected a token line then a new password line on stdin, received 0 line(s)")` then the password line with `received 1 line(s)` (2) → `locked_store` + `load` (5) → account exists (3) → `_reset_is_valid` else `AccountsError(1, "invalid token")` (1) → `validation.check_settable_password` (2) → replace the record with `_new_record(new_password)`, which in one assignment installs fresh password material at current parameters, returns `failed_logins` to `0` and leaves no `reset` key (equivalently the `record.pop("reset", None)` formulation in plan.md), all inside the same locked section that verified the token → `_save` → write `password reset\n` to stdout → return 0. The token is compared exactly as supplied: no whitespace trimming, no case folding (FR-033, FR-034, FR-035, FR-037, A-022)
- [X] T015 [US1] Wire both handlers into `HANDLERS` in `src/accounts/cli.py` as `"reset-token": cmd_reset_token` and `"reset": cmd_reset`, leaving `main` untouched so `AccountsError` remains the single path from a failure to the operator

### Tests for User Story 1

- [X] T016 [P] [US1] Create `tests/test_reset_token.py` with the issuance happy-path tests: `test_fr028_issue_records_material_and_prints_token`, `test_fr025_token_is_the_only_stdout_line` (22 characters, one `\n`, stderr empty, status 0), `test_fr021_default_validity_is_900`, `test_fr023_succeeds_with_stdin_closed`, `test_fr029_reissue_replaces`, `test_fr031_issue_on_locked_account_changes_nothing` (scenario 1.7: `failed_logins` and lock state unchanged), and `test_fr024_no_status_4_ever`
- [X] T017 [P] [US1] Create `tests/test_reset.py` with the redemption happy-path tests: `test_sc013_issue_and_redeem_across_invocations`, `test_fr025_password_reset_on_stdout`, `test_fr023_two_lines_in_order`, `test_fr023_extra_lines_ignored`, `test_fr034_reset_replaces_password_and_clears_lock` (new password gives `ok`/0, old password gives `invalid credentials`/1, `failed_logins` is 0 and a previously locked account logs in immediately — scenarios 1.3, 1.4, 1.7), `test_fr034_other_accounts_byte_identical` (SC-021), `test_fr037_no_current_password_required`, `test_fr030_valid_before_expiry`, `test_sc014_validity_boundary_explicit` and `test_sc014_validity_boundary_default` (scenario 1.5: `--ttl 5` redeemed immediately succeeds), plus scenario 1.8 — two tokens for two accounts each work only against their own account
- [X] T018 [P] [US1] Create `tests/test_reset_security.py` with the issuance-side security tests: `test_sr013_token_absent_from_store_bytes`, `test_sr013_fresh_salt_per_issuance` (never the account's password salt, never reused across issuances), `test_sr013_token_digest_uses_current_parameters` (`n=131072, r=8, p=1, dklen=32`), `test_sr013_no_token_literal_in_repo_fixtures`, `test_sc015_token_in_no_temp_file_or_stderr`, `test_sr014_token_entropy_is_at_least_128_bits`, `test_sr014_ten_thousand_tokens_distinct` (SC-016; mark `slow`), `test_sr014_package_never_imports_random`, `test_sr014_token_compared_in_constant_time`, `test_sr011_token_alphabet_is_safe_printable_ascii`, `test_sr011_token_output_is_exactly_one_line`, `test_sr017_store_mode_600_after_issue_and_redeem`, `test_sr017_no_sidecar_spool_or_log_created`, `test_sr012_no_new_path_derived_from_input`

**Checkpoint**: User Story 1 is fully functional and testable on its own — the MVP recovery path works end to end.

---

## Phase 4: User Story 5 - The existing five commands are untouched (Priority: P1)

**Goal**: Everything feature 001 specifies about `register`, `login`, `unlock`,
`passwd` and `delete` still holds byte for byte and status for status, and
stores written before this feature still load and still verify.

**Independent Test**: Run feature 001's complete suite unchanged apart from the
two A-025 diagnostic strings and confirm it passes; load a pre-feature store and
confirm every account still verifies its password. Automated as
`tests/test_compatibility.py` plus the eleven unchanged 001 test files.

### Implementation for User Story 5

- [X] T019 [US5] Record in `src/accounts/cli.py` — as comments on `cmd_passwd`, `cmd_delete`, `cmd_login` and `cmd_unlock`, with **no behavioural change** — why FR-042 already holds: `cmd_passwd` assigns a whole fresh record via `_new_record`, so a successful change drops any `reset` key; `cmd_delete` removes the record and its token together; `cmd_login` and `cmd_unlock` mutate `failed_logins` in place, so an outstanding token survives them untouched. Any edit here beyond comments is a FR-040 regression

### Tests for User Story 5

- [X] T020 [P] [US5] Create `tests/test_compatibility.py` with `test_fr040_existing_five_unchanged`, `test_a025_only_two_diagnostics_changed`, `test_fr041_pre_feature_store_loads` and `test_fr041_passwords_still_verify` (a store built from `conftest.synthetic_record()` with **no** `reset` key, i.e. byte-identical to pre-feature output — SC-020), `test_fr042_passwd_invalidates_token`, `test_fr042_delete_removes_token` (and re-registering the username does not inherit it — scenario 5.5), `test_fr042_login_and_unlock_leave_token` (scenario 5.4), and `test_sc019_feature_001_suite_passes`
- [X] T021 [P] [US5] Verify with `git diff --stat` that the eleven feature-001 test files (`tests/test_register.py`, `test_login_lockout.py`, `test_passwd.py`, `test_delete.py`, `test_security.py`, `test_store_format.py`, `test_concurrency.py`, `test_crash_safety.py`, `test_performance.py`, `test_example_sequence.py` and `tests/conftest.py`) carry **only additions** — no modified or deleted 001 assertion — and that `tests/test_cli_contract.py` differs by exactly the two A-025 strings plus the added FR-020 test (SC-019)

**Checkpoint**: Stories 1 and 5 both hold — the recovery path works and nothing existing regressed.

---

## Phase 5: User Story 2 - A token that should not work does not work (Priority: P2)

**Goal**: Every token that is not the current, unused, unexpired token for that
account is refused with one indistinguishable answer, and the refusal changes
nothing.

**Independent Test**: Register an account, then attempt a reset with a token
that was never issued, one already redeemed, one whose validity elapsed, and one
a newer issuance replaced — each prints `invalid token`, exits 1, and leaves the
stored password working. Automated as `tests/test_reset_invalid_token.py`.

### Implementation for User Story 2

- [X] T022 [US2] Audit `cli._reset_is_valid` and `cli.cmd_reset` in `src/accounts/cli.py` so that **every** refused-token path spends exactly one scrypt derivation before answering and there is no early `return` ahead of it — no `reset` key, an expired `reset`, a replaced token and a wrong token must all cost one derivation and emit the byte-identical `invalid token` with status 1 and empty stdout. A consumed token needs no special case: its key is gone, so it takes the no-token path by construction (SR-018, SC-018, research R17)

### Tests for User Story 2

- [X] T023 [P] [US2] Create `tests/test_reset_invalid_token.py` covering all ten acceptance scenarios: `test_fr026_failure_streams` (one stderr line, empty stdout), `test_fr026_invalid_token_is_exact_and_detail_free`, never-issued, wrong value (issued token still usable afterwards), `test_fr035_second_use_refused`, `test_fr030_expired_token_refused` (`--ttl 1`, sleep past it), `test_fr029_replaced_token_refused` (and the second token still works), token dead after a successful `passwd` (scenario 2.6), empty token line, `test_fr039_wrong_token_does_not_increment_count`, a token issued for `bob` refused for `alice`, `test_fr037_current_password_not_accepted_as_token`, and `test_fr027_store_byte_identical_after_each_failure` (SC-021)
- [X] T024 [P] [US2] Add the refusal-indistinguishability tests to `tests/test_reset_security.py`: `test_sr018_all_refusal_paths_byte_identical` across all five refusal families, `test_sr018_refusal_timing_parity`, `test_sr018_no_secret_material_in_either_stream`, `test_sr018_token_only_on_reset_token_stdout_on_success`, `test_sr018_no_traceback_on_any_new_failure_path`, and `test_sr011_control_chars_in_token_line_not_echoed`
- [X] T025 [P] [US2] Add to `tests/test_concurrency.py` (existing `slow` marker): `test_sc023_simultaneous_redemption_one_success` — two simultaneous `reset` invocations with one valid token yield exactly one `password reset`/0 and one `invalid token`/1, and the stored password is afterwards the one set by the single success — and `test_sr016_concurrent_issuance_leaves_one_token`

**Checkpoint**: Stories 1, 2 and 5 all work independently — the recovery path is safe to operate.

---

## Phase 6: User Story 3 - A refused new password does not burn the token (Priority: P3)

**Goal**: A valid token redeemed with a password that fails the length rules is
refused as a bad request (status 2) with the token left outstanding and its
original expiry unchanged, so the holder can simply retry.

**Independent Test**: Register an account, issue one token, attempt a reset with
an 11-character new password and confirm status 2 with the stored password
unchanged, then retry the same token with a 12-character password and confirm it
succeeds. Automated as the FR-036 tests in `tests/test_reset.py`.

### Implementation for User Story 3

- [X] T026 [US3] Confirm in `src/accounts/cli.py` `cmd_reset` that the password line is *read* at step 2 but *judged* only after the token is accepted, and that **nothing** is written before the final step — so an expired token with an 11-character password answers `invalid token`/1 rather than a password error (scenario 3.4), and a refused password leaves the `reset` field and its `expires_ms` untouched because no write has happened (FR-033, FR-036, research R14)

### Tests for User Story 3

- [X] T027 [US3] Add to `tests/test_reset.py` (same file as T017, so run after it): `test_fr036_short_password_keeps_token` (11 characters → `error: new password too short: expected at least 12 characters, received 11`, status 2, stored password unchanged, then the same token with a 12-character password succeeds — SC-017), `test_fr036_long_password_keeps_token` (over 1 024 characters), `test_fr036_expiry_unchanged_after_refusal` (the `reset` object compared byte for byte before and after), `test_fr033_check_order_precedence` (including scenario 3.4), and the exactly-12-character success of scenario 3.5

**Checkpoint**: A mistyped password no longer costs a round trip to the administrator.

---

## Phase 7: User Story 4 - Bad requests are refused without touching the store (Priority: P3)

**Goal**: A request naming an unregistered account, or malformed in its
arguments or input, is refused with the documented status and leaves the store
exactly as it was — including not creating it.

**Independent Test**: Against a store path that does not exist, and against a
store holding only `alice`, run both new operations for an unregistered username
and confirm status 3, a message naming the missing account, and that no file is
created or altered. Automated across `tests/test_reset_token.py`,
`tests/test_reset.py` and `tests/test_store_format.py`.

### Implementation for User Story 4

- [X] T028 [US4] Confirm in `src/accounts/cli.py` that neither `cmd_reset_token` nor `cmd_reset` creates the store: a missing path loads as an empty in-memory store, both then raise `_no_such_account` (status 3), and nothing is written — not the store, not a temporary file, not a lock file. Unlike `cmd_login`, neither handler ever writes a failure count on any failure path (FR-027, FR-032, FR-038, FR-039)

### Tests for User Story 4

- [X] T029 [P] [US4] Add the bad-request tests to `tests/test_reset_token.py`: `test_fr022_ttl_allowlist` (reject `-5`, `+60`, `0`, `1.5`, `6e1`, `100000`, `99999`, the empty string, surrounding whitespace and `１２`, each status 2 with `error: invalid ttl: expected a whole number of seconds from 1 to 86400, received 'VALUE'`), `test_fr022_invalid_ttl_issues_no_token`, `test_sr010_int_does_not_accept_unicode_digits`, `test_sr015_ttl_bounded_at_five_digits`, `test_fr021_ttl_only_with_reset_token`, `test_fr021_ttl_not_abbreviated`, `test_fr021_ttl_not_repeated` (all three → the usage line, status 2), `test_fr032_creates_no_file_when_store_absent`, invalid usernames (2 characters, 33 characters, a character outside `[A-Za-z0-9_]`) → status 2, and an unregistered username → `error: no such account 'USERNAME'`, status 3
- [X] T030 [P] [US4] Add the bad-request tests to `tests/test_reset.py`: `test_fr023_missing_input_is_status_2` (empty stream → `received 0 line(s)`; closed after the token line → `received 1 line(s)`), `test_sr015_overlong_token_line_refused_not_truncated` (4 097 bytes → `error: token line too long: expected at most 4096 bytes before the line terminator`, decided before the store is opened and never compared), a non-UTF-8 token line → `error: token line is not valid UTF-8 text`, `test_fr038_creates_no_file_when_store_absent`, an unreadable or malformed store → status 5 changing nothing, `test_fr024_every_status_reachable` (SC-012) and `test_fr039_lockout_does_not_restrict_reset`
- [X] T031 [P] [US4] Add the stored-material cases to `tests/test_store_format.py`: `reset` present but not an object; `reset` missing any of its eight keys or carrying a ninth; `expires_ms` absent, a string, a float, `true`, `NaN`, negative, zero or above `253402300799000` (`test_sr015_expires_ms_out_of_range_is_status_5`); `reset.salt`/`reset.hash` of wrong decoded length or outside the base64 alphabet; `reset.kdf` anything but `"scrypt"`; any scrypt parameter out of range or failing the `maxmem` rule — every case status 5, with the record never loaded without its `reset`
- [X] T032 [P] [US4] Add to `tests/test_reset_security.py`: `test_sr010_reset_field_allowlist`, `test_sr010_malformed_expires_ms_is_status_5_not_unexpired` (the trap case: a `NaN`/missing expiry must not read as "not expired"), `test_sr010_invalid_reset_never_repaired_or_skipped`, `test_sr015_reset_material_is_fixed_size` (serialised `reset` is exactly 174 bytes regardless of token, username or issuance count), and `test_sr012_no_temp_file_survives_a_failed_reset`

**Checkpoint**: All five user stories are independently functional; the extended status contract is complete.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: The cross-story success criteria, documentation accuracy, and the
full-suite and traceability gates.

- [X] T033 [P] Add to `tests/test_performance.py` (existing `slow` marker): `test_sc022_reset_operations_under_one_second` (both operations on a 1 000-account store, each under 1 s) and `test_sc022_store_scaling_component_negligible` (the hardware-independent claim that the store-size component is ~ms against the ~0.4 s per derivation). Note plan.md flagged note 1: `reset` has only ~1.2× headroom — if the absolute bound fails on the host, report it rather than lowering the scrypt work factor, which would be an SR-013/SR-004 amendment
- [X] T034 [P] Add `test_sc024_sigkill_during_issue_and_redeem` to `tests/test_crash_safety.py` (`slow`): killing the tool at points during issuance and redemption leaves a store that still parses and still verifies every account it held before — never a mixture
- [X] T035 [P] Add `test_sc025_reset_worked_sequence` to `tests/test_example_sequence.py`, reproducing the worked sequence of [contracts/cli-contract.md](./contracts/cli-contract.md#worked-example-sequence) line for line and status for status, with every token captured at runtime via `conftest.issue_token` and never written as a literal
- [X] T036 [P] Update the stale docstrings in `src/accounts/cli.py` (the module header's "the five commands" and `COMMANDS`/`STDIN_LINES` comments) and any "five operations" wording in `src/accounts/store.py`, `crypto.py` and `validation.py` docstrings, so the code's own documentation names seven operations and the optional `reset` field
- [X] T037 Walk the validation scenarios V13–V25 of [quickstart.md](./quickstart.md#validation-scenarios) by hand against a scratch store and confirm each matches its documented output and exit status
- [X] T038 Run the complete suite in `tests/` including slow checks (`python -m pytest`) from the repository root and confirm it is green, including the feature-001 files unchanged from T001's baseline (SC-019)
- [X] T039 Audit every row of plan.md's [Requirement-to-test mapping](./plan.md#requirement-to-test-mapping) and [Security requirement mapping](./plan.md#security-requirement-mapping) against the tests that now exist, confirming no row is empty and no test id was renamed — FR-020 … FR-043, SR-010 … SR-018, SC-012 … SC-025 (Principle III)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — T001 establishes the baseline every FR-040/SC-019 claim is measured against and should genuinely run first
- **Foundational (Phase 2)**: depends on Setup — **blocks all five user stories**
- **User Stories (Phases 3–7)**: all depend on Phase 2. Phase 3 (US1) additionally gates Phases 5–7 in practice, because US2, US3 and US4 all exercise the two handlers US1 implements. US5 (Phase 4) depends only on Phase 2
- **Polish (Phase 8)**: depends on Phases 3–7

### User Story Dependencies

- **US1 (P1)**: after Phase 2. No dependency on another story — the MVP
- **US5 (P1)**: after Phase 2. Independent of US1 by design; its whole claim is that nothing the other stories add is observable in the existing five commands. Can be worked in parallel with US1
- **US2 (P2)**: after Phase 2; needs US1's `cmd_reset` to have something to refuse
- **US3 (P3)**: after Phase 2; needs US1's `cmd_reset`
- **US4 (P3)**: after Phase 2; needs US1's two handlers for their failure paths

### Within Each User Story

- Models/validators before services before handlers; handlers before the tests that drive them
- Tasks touching the same file are never marked [P] — in particular `src/accounts/cli.py` (T006 → T007 → T008 → T011 → T012 → T013 → T014 → T015) and `tests/test_reset.py` (T017 → T027 → T030), `tests/test_reset_token.py` (T016 → T029), `tests/test_reset_security.py` (T018 → T024 → T032)
- Nothing is written to the store before the last step of either handler — this single property is what delivers FR-027, FR-036 and FR-039 without individual safeguards

### Parallel Opportunities

- Phase 1: T002 alongside T001
- Phase 2: T003, T004, T005 and T009 are four different files and can all run together; T006 → T007 → T008 are the same file and must be sequential; T010 depends on T007
- Phase 3: T016, T017, T018 in parallel once T015 lands
- Phase 4: T020 and T021 in parallel, and the whole phase in parallel with Phase 3
- Phase 5: T023, T024, T025 in parallel
- Phase 7: T029, T030, T031, T032 in parallel
- Phase 8: T033, T034, T035, T036 in parallel; T037 → T038 → T039 sequential

---

## Parallel Example: Phase 2 Foundational

```bash
# Four different files, no shared edits:
Task: "Add TOKEN_BYTES and new_token() to src/accounts/crypto.py"
Task: "Add TTL constants and validate_ttl() to src/accounts/validation.py"
Task: "Add RESET_KEYS and reset-interior validation to src/accounts/store.py"
Task: "Add reset test helpers to tests/conftest.py"
```

## Parallel Example: User Story 1 tests

```bash
# After T015 wires the handlers:
Task: "Create tests/test_reset_token.py issuance happy-path tests"
Task: "Create tests/test_reset.py redemption happy-path tests"
Task: "Create tests/test_reset_security.py issuance-side security tests"
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 5)

1. Phase 1: Setup — the green baseline
2. Phase 2: Foundational (**blocks everything**)
3. Phase 3: User Story 1 — issue and redeem
4. Phase 4: User Story 5 — prove nothing regressed
5. **STOP and VALIDATE**: quickstart V13, V14 and V15; the full 001 suite
6. Demo if ready

Both P1 stories belong in the MVP: a working recovery path that regresses the
existing tool is not a shippable outcome (spec, US5 rationale).

### Incremental Delivery

1. Setup + Foundational → the seven-command surface exists, suite green
2. + US1 → recovery works (MVP, with US5 as its guard rail)
3. + US2 → recovery is safe to operate: every bad token refused identically
4. + US3 → a mistyped password no longer burns the token
5. + US4 → the extended status contract is complete
6. + Polish → SC-022, SC-024, SC-025 and the Principle III traceability gate

### Parallel Team Strategy

1. Everyone on Phase 1 + Phase 2 (four files, four hands)
2. Then: Developer A on US1 (Phase 3), Developer B on US5 (Phase 4) —
   genuinely independent
3. Once US1's handlers land: Developer B picks up US2, Developer C US3 and US4
4. Phase 8 once Phases 3–7 are done

---

## Notes

- [P] = different files, no dependencies. Every [P] group above was checked for
  file overlap
- Test ids come from plan.md and are themselves the contract — do not rename
  them; an empty row in the mapping is a Principle III blocker
- **Secrets hygiene**: no issued token value ever becomes a literal in the
  repository. Tests capture tokens at runtime through `conftest.issue_token`,
  and all fixture salts and digests are synthetic (SR-013, SC-015)
- **No new `except` clause** may be introduced anywhere in `src/accounts/` —
  feature 001's single recorded suppression must remain the only one
  (Principle II, plan.md Constitution Check)
- `version` stays exactly `1` and `reset` stays optional: that is the whole of
  backward compatibility (FR-041)
- `invalid token` is deliberately detail-free, and status 4 is deliberately
  unreachable from both new operations — both are requirements, not oversights
- Commit after each task or logical group; stop at any checkpoint to validate a
  story on its own
