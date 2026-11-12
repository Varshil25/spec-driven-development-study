---

description: "Task list for 002-password-reset"
---

# Tasks: Password reset by one-time token

**Input**: Design documents from `/specs/002-password-reset/`

**Prerequisites**: plan.md, spec.md, research.md (D-010…D-020), data-model.md (T-1…T-10, A-7…A-9), contracts/cli.md, contracts/store-file.md, quickstart.md, `.specify/memory/constitution.md` v1.0.0

**Tests**: **MANDATORY, not optional.** Constitution Principle III requires every functional
requirement to map to at least one automated `pytest` test with the mapping explicit in the test
name or a comment, and forbids marking the feature complete while any FR lacks a covering test.
Every error path required by Principle II needs a test asserting both the message and the failure
signal. Test tasks below therefore carry the same weight as implementation tasks.

**Organization**: Tasks are grouped by user story (US1–US4 = spec priorities P1–P4) so each story
can be implemented, tested and delivered independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task belongs to (US1…US4); Setup, Foundational and Polish tasks carry no story label
- Exact file paths are given in every task

## Path Conventions

Single project, flat package, as shipped by 001 and frozen by plan.md's Structure Decision:
`src/accounts/` and `tests/` at the repository root. **This feature adds no module and no
directory** — only three existing source files change, five test files are created, and two
existing test files have one string literal updated each (research.md D-016, D-019).

## Constants fixed by the design (use these verbatim)

| Thing | Value | Source |
|---|---|---|
| Usage line | `usage: python -m accounts --store PATH {register\|login\|unlock\|passwd\|delete\|reset-token\|reset} USERNAME [--ttl SECONDS]` | FR-040 |
| New messages | `password reset` (stdout, 0), `invalid token` (stderr, 1) | FR-042 |
| Default TTL | `900` seconds | FR-033 |
| TTL range | `1` … `86400` inclusive | FR-033 |
| Token value | `secrets.token_urlsafe(32)` — 256 bits, 43 chars of `[A-Za-z0-9_-]` | D-011 |
| Stored form | `hashlib.sha256(token.encode("utf-8")).hexdigest()` — 64 lowercase hex | D-012 |
| Comparison | `hmac.compare_digest` — constant-time | FR-034b |
| Expiry | valid while `time.time() < issued_at + ttl_seconds`; boundary **exclusive** | T-5, D-015 |
| Min password length | `12` (existing `MIN_PASSWORD_LENGTH`) | FR-008 |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: establish the SC-010 baseline and the one shared test helper the new suites need

- [ ] T001 Run `pytest` from the repository root and record the baseline: zero failures across the 10 existing files in `tests/` (`test_cli_contract.py`, `test_delete.py`, `test_hashing.py`, `test_login_lockout.py`, `test_passwd.py`, `test_register.py`, `test_store_file.py`, `test_success_criteria.py`, `test_unlock.py`, `conftest.py`). This pass count is the SC-010 reference that must still hold at T033; no files are changed by this task.
- [ ] T002 Add an `issued_token` fixture to `tests/conftest.py` beside the existing `run` / `run_subprocess` / `store_path` / `read_store` / `write_store` / `low_iterations` fixtures: `issued_token(run, store_path, username, ttl=None)` invokes `reset-token` (with `--ttl` appended only when `ttl` is not `None`), asserts status 0 and empty stderr, and returns the single stdout line with its trailing newline removed. It is a test helper only — no runtime seam is introduced (plan.md Gate III "Fixtures", D-015).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: token cryptography, store-format validation and the CLI plumbing (`--ttl`, the usage line, the message constants, the input-line table, the handler signature). No user story can be implemented until these are in place.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 [P] Add three token functions to `src/accounts/hashing.py`, beside the existing `new_password_material` / `verify` pair so every constant-time comparison in the project stays in one file (D-016): `new_token() -> str` returning `secrets.token_urlsafe(32)` (32 CSPRNG bytes → 43 characters of `[A-Za-z0-9_-]`, 256 bits of entropy, no whitespace so it occupies exactly one line — FR-034a, D-011); `token_fingerprint(token: str) -> str` returning `hashlib.sha256(token.encode("utf-8")).hexdigest()` (64 lowercase hex characters — FR-034b, D-012); `verify_token(stored_hash: str, presented: str) -> bool` returning `hmac.compare_digest(token_fingerprint(presented), stored_hash)` (constant-time — FR-034b, T-4). `secrets`, `hashlib` and `hmac` are already imported; add no new import here. Deliberately **no** PBKDF2 over the token: `reset-token` must perform zero derivations (SC-018, D-012).
- [ ] T004 [P] Extend `_validate_record` in `src/accounts/store.py` with optional `reset_token` validation, raising `StoreError` with the specific cause named in the existing `f"account {username!r}: …"` style. The key is **optional**; its absence is the normal state of an account (A-7). When present, each of these is a corrupt store — never silently ignored and never read as "no token" (FR-039, T-10): `reset_token` "is not a JSON object — including `null`, a string, a number, a boolean, or an array"; `reset_token` "is missing `token_hash`, `issued_at` or `ttl_seconds`"; `token_hash` "is not a string; or is not exactly 64 characters; or contains a character outside `0`–`9`/`a`–`f` (including uppercase hex)"; `issued_at` "is not a number; is a boolean; or is not finite (`NaN`, `Infinity`, `-Infinity` — which `json.loads` accepts by default and this tool must therefore reject)"; `ttl_seconds` "is not an integer; is a boolean; is a float (including `900.0`); or is outside 1…86400". Reject `bool` explicitly wherever a number is required (`bool` subclasses `int`), reusing the existing `_validate_int` discipline. Unknown **extra** keys inside the `reset_token` object "are not an error and are preserved on rewrite"; a *missing* required key is corruption (S-6 precedent). Add `math` (or an `x != x` / `abs(x) != inf` check) only if needed for the finiteness test — no non-stdlib import.
- [ ] T005 Replace the `USAGE` constant in `src/accounts/cli.py` (lines 17–20) with exactly `usage: python -m accounts --store PATH {register|login|unlock|passwd|delete|reset-token|reset} USERNAME [--ttl SECONDS]`. This is the one and only change visible in any existing command's output (FR-040, FR-041).
- [ ] T006 [P] Update the `USAGE` literal in `tests/test_cli_contract.py` (lines 14–17) to the FR-040 string, keeping the trailing `\n` the equality assertions rely on. Leave `COMMANDS` (line 19) at the five existing commands and change no other assertion — the new commands get their own files (SC-010, D-019).
- [ ] T007 [P] Update the `USAGE` literal in `tests/test_success_criteria.py` (lines 19–22) to the FR-040 string with its trailing `\n`. These two literals are the **only** permitted edits to the shipped suite; a third edit means the change has leaked past FR-041 and must be re-examined, not accommodated (SC-010, D-019).
- [ ] T008 Add the two new message constants to the message block of `src/accounts/cli.py` (after `MSG_MISSING_PASSWORD_INPUT`): `MSG_PASSWORD_RESET = "password reset"` and `MSG_INVALID_TOKEN = "invalid token"`. No other message joins the inventory — `no such account`, `password too short`, `missing password input` and `STORE_UNUSABLE_PREFIX` are reused verbatim (FR-042).
- [ ] T009 Rename `PASSWORD_LINES` to `INPUT_LINES` in `src/accounts/cli.py` and add two rows, `"reset-token": 0` (FR-034 — reads nothing at all) and `"reset": 2` (FR-035 — the token, then the new password). Update both existing references: the count lookup in `main` (line 73) and the command-membership test in `_parse_args` (line 115), which is what admits the two new command words (FR-031). The name is module-private and referenced by no test, so FR-041 and SC-010 are untouched (D-017).
- [ ] T010 Extend `_parse_args` in `src/accounts/cli.py` to locate `--ttl` by scan exactly as `--store` already is, and add the constants `TTL_DEFAULT = 900`, `TTL_MIN = 1`, `TTL_MAX = 86400` near `MIN_PASSWORD_LENGTH`. Accept only the space-separated `--ttl SECONDS` form; return `None` (the usage error) for: a second `--ttl`, `--ttl` with no following value, `--ttl=900`, a value that is not a non-empty string with **every character in `"0123456789"`**, a value outside 1…86400 after `int()`, and `--ttl` supplied with any command other than `reset-token`. The digit test must be the explicit character check — **not** `int()` alone (which accepts `"1_0"` as 10) and **not** `str.isdigit()` (which accepts `"²"` and `"١٢"`) — per the measured table in D-014, Principle II. `--ttl 86401` and `--ttl 99999999999999999999` are refused, **not clamped**; `--ttl 1` and `--ttl 86400` are both accepted. Absent, the lifetime is `TTL_DEFAULT`. Validation happens during parsing, before the store is loaded, which is what makes "no store file created or modified" true for free (FR-033, FR-037, FR-040).
- [ ] T011 Thread `ttl` through dispatch in `src/accounts/cli.py`: `_parse_args` now returns `(store_path, command, username, ttl)`; `main` unpacks the fourth value and the uniform handler signature becomes `handler(data, store_path, username, inputs, ttl, stdout, stderr) -> int`. Add the `ttl` parameter to all five existing handlers (`_register`, `_login`, `_unlock`, `_passwd`, `_delete`), which ignore it, and update the call site at line 82. One uniform signature with one unused parameter is deliberately chosen over an options object, a partial or a closure (D-017, Gate IV deviation 2). Rename the `passwords` parameter to `inputs` only where it is now a token-plus-password pair; `_read_passwords` itself is unchanged and keeps its no-strip, line-break-only behaviour, which is exactly what FR-035 requires (D-017).
- [ ] T012 Create `tests/test_store_token_state.py` covering FR-039 and the store half of SC-019, naming the requirement in each test name or docstring (Principle III): one test per corruption row of T004 asserting `store unusable: ` as a **prefix** on stderr with exit 5 — `"reset_token": null`, a string, a number, a boolean, an array; each of the three fields missing in turn; `token_hash` as `5`, 63 characters, 65 characters, uppercase hex, non-hex letters; `issued_at` as `"now"`, `true`, `NaN`, `Infinity`, `-Infinity`; `ttl_seconds` as `0`, `-5`, `1.5`, `900.0`, `true`, `86401`, `"900"`. Assert malformed token state is exit 5 for **all seven** commands including `login`, which never reads a token (FR-039, plan.md consequence 3). Assert a well-formed `reset_token` round-trips through `store.load` → `store.save` unchanged, that unknown extra keys inside the object are preserved on rewrite, and that a pre-feature store document (no `reset_token` anywhere, marker `accounts-store-v1`) loads and is used by all seven commands with no migration and no marker change (A-7, SC-019). Use the existing `write_store` / `read_store` fixtures.

**Checkpoint**: `pytest` is green again (T001's baseline plus `test_store_token_state.py`), the seven command words parse, `--ttl` is validated, and token crypto exists. User story implementation can now begin.

---

## Phase 3: User Story 1 - An administrator issues a reset token and the user resets their password (Priority: P1) 🎯 MVP

**Goal**: `reset-token USERNAME [--ttl SECONDS]` prints a fresh single-use token on a line of its own and records only its fingerprint; `reset USERNAME` reads that token and a new password and, on acceptance, replaces the password, clears the lock and the tally, spends the token, and prints `password reset`.

**Independent Test**: register `alice`; run `reset-token alice` and capture the single stdout line; feed that line plus a ≥12-character password to `reset alice` and assert `password reset` / 0; `login alice` with the new password prints `ok` / 0 and with the old password prints `invalid credentials` / 1. Repeat with `alice` locked by five failed logins and assert the same three commands succeed with no `unlock` (SC-011).

**Note on scope**: `_reset`'s full check chain (existence → token → length → success) is implemented
here because FR-036a fixes that order and the happy path cannot be reached without it. US2 and US3
add the assertions for each refusal branch plus the one piece of new code each still needs.

### Tests for User Story 1

> Write these first and confirm they fail before implementing T018–T019.

- [ ] T013 [P] [US1] Create `tests/test_reset_token.py` with the issuing tests (FR-032, FR-034, named in each test): `reset-token alice` on an existing account exits 0, writes **exactly one line** to stdout and **nothing** to stderr; the account record gains a `reset_token` whose `token_hash` equals `hashlib.sha256(printed_token.encode("utf-8")).hexdigest()`, whose `issued_at` is within a second of `time.time()`, and whose `ttl_seconds` is `900` by default; `algorithm`, `iterations`, `salt`, `key`, `failed_logins` and `locked` are **byte-for-byte unchanged** (FR-032, FR-038); the command reads nothing from standard input, asserted by passing a non-empty stdin and seeing it untouched (FR-034); it succeeds on a locked account and does **not** unlock it, so a following `login` with the correct password still prints `account locked` / 4 (acceptance 1.7, FR-032); two invocations print different tokens and the second **replaces** the first in the record (FR-032, T-6); `--ttl 1` and `--ttl 86400` are accepted and the given value is what lands in `ttl_seconds` (FR-033). Use the `run`, `store_path`, `read_store` and `issued_token` fixtures.
- [ ] T014 [US1] Extend `tests/test_reset_token.py` with the `--ttl` grammar table from contracts/cli.md (FR-033, FR-040, D-014), each asserting the exact FR-040 usage line on stderr, exit 2, empty stdout and **no store file created or modified**: `--ttl` with no value, `--ttl=900`, `--ttl abc`, `--ttl ""`, `--ttl " 5"`, `--ttl +5`, `--ttl 1_0`, `--ttl 1.5`, `--ttl 0x10`, `--ttl ²`, `--ttl ١٢`, `--ttl 0`, `--ttl -5`, `--ttl 86401`, `--ttl 99999999999999999999`, `--ttl` given twice, and `--ttl 900` supplied to each of `register`, `login`, `unlock`, `passwd`, `delete` and `reset`. Also assert `--ttl` is accepted before the positionals and between them (located by scan, like `--store`).
- [ ] T015 [US1] Extend `tests/test_reset_token.py` with the entropy and unrecoverability tests (FR-034a, FR-034b, SC-014, SC-015): 1,000 tokens issued in succession are all distinct, each is **at least 22 characters**, every character is in `[A-Za-z0-9_-]`, and none contains whitespace (SC-015) — assert the floors and the alphabet, **not** the 43-character length, so the margin can be raised later without a contract change (plan.md consequence 5, D-011); after issuing tokens for accounts whose tokens are known, a search of the store file's **bytes** finds none of them in plain, hexadecimal or base64 form (SC-014); feeding the recorded `token_hash` to `reset` as the token yields `invalid token` / 1 — it is not the token (SC-014, T-3).
- [ ] T016 [P] [US1] Create `tests/test_reset.py` with the happy path (FR-035, FR-036b, named in each test): `reset alice` given a valid token and a ≥12-character password prints exactly `password reset\n` on stdout, nothing on stderr, and exits 0; the record's `algorithm`, `iterations`, `salt` and `key` are replaced with fresh material (new `salt`, `iterations == hashing.DEFAULT_ITERATIONS`), `failed_logins` is `0`, `locked` is `false`, and `reset_token` is **removed**; a following `login` with the new password prints `ok` / 0 and with the previous password prints `invalid credentials` / 1; the same holds when `alice` was locked by five failed logins, with **no `unlock` run** (acceptance 1.6, SC-011); input beyond the two lines is ignored, not an error (FR-035); a token line with leading or trailing spaces is taken verbatim and is therefore not the issued token → `invalid token` / 1 (FR-035).
- [ ] T017 [P] [US1] Create `tests/test_reset_contract.py` covering the invocation surface (FR-031, FR-037, FR-040, FR-042, FR-043, FR-044): all seven command words are accepted by the parser and `reset-token` / `reset` are dispatched (FR-031); the global check order holds for both new commands — a corrupt or unreadable store gives `store unusable: ` prefix / 5 **even when the username does not exist**, so a corrupt store is never treated as empty (FR-037, plan.md consequence 3); on success both commands write **nothing** to stderr and on failure both write to stderr **only** with nothing on stdout (FR-042); status **4 is never produced** by either new command, asserted on a locked account for every outcome of both (FR-043); the token appears on the stdout of the `reset-token` invocation that creates it and nowhere else — not in any other command's output and not in any error message, including `invalid token` (FR-044); the exact FR-040 usage line is asserted in full for a malformed invocation of each new command (a third positional, an unknown flag).

### Implementation for User Story 1

- [ ] T018 [US1] Add `import time` to `src/accounts/cli.py` (the feature's one new stdlib import — D-010) and implement `_reset_token(data, store_path, username, inputs, ttl, stdout, stderr)`: look the account up in `data["accounts"]`; `None` → `_fail(stderr, MSG_NO_SUCH_ACCOUNT, EXIT_ACCOUNT_CONFLICT)` with nothing on stdout and **no store write at all**; otherwise draw `token=[REDACTED:assigned_secret]()`, assign `record["reset_token"] = {"token_hash": hashing.token_fingerprint(token), "issued_at": time.time(), "ttl_seconds": ttl}` (plain assignment, which overwrites any outstanding token — T-6), `store.save(store_path, data)`, `print(token, file=stdout)`, return `EXIT_SUCCESS`. Touch nothing else in the record — no password material, no `failed_logins`, no `locked` (FR-032, FR-038). Perform **no** password derivation (SC-018). Register `"reset-token": _reset_token` in `_HANDLERS`.
- [ ] T019 [US1] Implement `_reset(data, store_path, username, inputs, ttl, stdout, stderr)` in `src/accounts/cli.py` with a module-private helper `_token_valid(record, presented) -> bool` (no new class, no new module — D-016). `_token_valid`: return `False` unless `record` has a `reset_token`; then `hashing.verify_token(record["reset_token"]["token_hash"], presented)`; then `time.time() < record["reset_token"]["issued_at"] + record["reset_token"]["ttl_seconds"]` — boundary **exclusive**, so at exactly `issued_at + ttl_seconds` the token is expired (T-5, D-015); all three must hold. `_reset` unpacks `token, new = inputs` and applies FR-036a's order, the first failure deciding the outcome: unknown account → `MSG_NO_SUCH_ACCOUNT` / `EXIT_ACCOUNT_CONFLICT` (3); `not _token_valid(...)` → `MSG_INVALID_TOKEN` / `EXIT_INVALID_CREDENTIALS` (1), identical for a wrong, never-issued, spent, cancelled or expired token (FR-036a, FR-042); `len(new) < MIN_PASSWORD_LENGTH` → `MSG_PASSWORD_TOO_SHORT` / `EXIT_INVALID_INPUT` (2); otherwise `record.update(hashing.new_password_material(new))`, `record["failed_logins"] = 0`, `record["locked"] = False`, `record.pop("reset_token", None)`, one `store.save`, `print(MSG_PASSWORD_RESET, file=stdout)`, return `EXIT_SUCCESS`. Spending the token is its **removal** — no `used` flag and no spent-token history (FR-036b, T-1, T-7, D-013). Exactly **one** derivation, performed only after the token has been accepted and the length check has passed (SC-018, D-018). Every failing branch returns before any `store.save`. Register `"reset": _reset` in `_HANDLERS`.

**Checkpoint**: User Story 1 is fully functional and independently testable — a forgotten password is recovered in three commands, locked or not. This is the MVP; stop and validate here.

---

## Phase 4: User Story 2 - A token that is wrong, already used, expired or cancelled is refused (Priority: P2)

**Goal**: every way a token can be bad — wrong, never issued, already spent, replaced, expired, or cancelled by a successful `passwd` — yields `invalid token` / 1 with the store untouched and the password in force unchanged.

**Independent Test**: for each bad-token case run `reset` and assert `invalid token` / 1, then assert the password in force at the time still logs in; and assert the five-route lifecycle table of SC-020 row by row.

### Tests for User Story 2

- [ ] T020 [P] [US2] Extend `tests/test_reset.py` with the refusal tests (FR-036a, FR-036c, FR-036e): a different string as the token → `invalid token` / 1 with the stored password unchanged (acceptance 2.1); a token already used successfully, presented again with another valid password → `invalid token` / 1 and the password set by the first reset still logs in (acceptance 2.2, FR-036c); any token string on an account that has never had one issued → `invalid token` / 1 (acceptance 2.4); an **empty** token line → `invalid token` / 1, **not** `missing password input` (edge case, FR-035); a wrong token **together with** a too-short new password → exit **1**, not 2, because the token is judged before the password's length (acceptance 3.3, FR-036a, D-018); after a refused attempt the correct outstanding token still succeeds, and the refused attempt changed neither the stored password, nor `failed_logins`, nor `locked`, nor `reset_token` (acceptance 2.5, FR-036e).
- [ ] T021 [US2] Extend `tests/test_reset.py` with expiry in both directions (FR-036d, SC-013, D-015): one test with real elapsed time — `reset-token alice --ttl 1`, sleep ~1.1 s, then `reset` → `invalid token` / 1 (acceptance 2.3); and clock-free tests that rewrite `issued_at` in the store file with the `write_store` fixture to assert a token is **accepted** at `ttl - 1` seconds elapsed and **refused** at `ttl` seconds and beyond, for both an explicit short `--ttl` and the 900-second default, pinning the **exclusive** boundary (at exactly `issued_at + ttl_seconds` the token is expired). Add no clock seam to runtime code — the rewrite exercises the real code path (D-015).
- [ ] T022 [P] [US2] Create `tests/test_token_lifecycle.py` asserting every row of the lifecycle table in contracts/cli.md (FR-036g, FR-038, FR-038a, FR-038b, FR-041, SC-020), each row as "after X, `reset` with the token issued earlier yields …". **Refused** (`invalid token` / 1): nothing further but a successful `reset` with it (FR-036c); a later `reset-token` for the same account (FR-032); a successful `passwd` (FR-038a); a `delete`, including when the username is registered again afterwards (FR-036g, acceptance 4.3); its lifetime elapsed (FR-036d). **Still succeeds** (0): a `reset` refused with `invalid token` (FR-036e); a `reset` refused with `password too short` (FR-036f); a **failed** `passwd` (wrong current password, and short new password) (FR-038a); a **failed** `delete` (wrong password) (FR-038); a `register`, a `login` — success, failure, and a failure that locks the account — or an `unlock` (FR-038). Also assert: a wrong token presented many times never locks the account nor advances `failed_logins` (FR-038); SC-012's single-use sweep — 100 issued tokens, 100 first uses succeed and 100 second uses are refused with `invalid token` / 1, each invocation run to completion before the next begins (FR-038b), using the `low_iterations` fixture to keep inside the suite budget; and FR-041's frozen surface for `passwd` and `delete` — arguments, input lines, messages, streams, statuses and effect on the password, tally and lock state all unchanged, with the token effect the only addition.
- [ ] T023 [US2] Implement the `passwd` cancellation in `_passwd` in `src/accounts/cli.py`: after the current-password and length checks pass, add `record.pop("reset_token", None)` in the **same** write that replaces the derivation material (`record.update(hashing.new_password_material(new))` → single `store.save`), so the token is never committed separately from the password change (FR-038a, A-9, D-013). A `passwd` that fails for any reason must return before this and leave the token exactly as it was. This is `_passwd`'s **only** change: `locked` and `failed_logins` are still left untouched (FR-019, A-5), and its arguments, input lines, messages, streams and statuses are unchanged (FR-038a, FR-041). `register`, `login` and `unlock` need **no** change — they must not touch token state (FR-038); `delete` needs none either, since removing the record removes the token automatically (FR-036g, A-8).

**Checkpoint**: User Stories 1 and 2 both work independently — the happy path is safe to ship because every stale, wrong or cancelled token is refused.

---

## Phase 5: User Story 3 - A too-short new password is rejected but the token survives (Priority: P3)

**Goal**: a new password under 12 characters is rejected with `password too short` / 2 and the outstanding token remains usable, so the user retries instead of returning to the administrator.

**Independent Test**: issue a token, run `reset` with an 11-character password and assert `password too short` / 2 with the store unchanged, then run `reset` again with the **same** token and a 12-character password and assert `password reset` / 0.

### Tests for User Story 3

- [ ] T024 [US3] Extend `tests/test_reset.py` with the too-short-password tests (FR-036f, SC-017): a valid token with an 11-character new password prints exactly `password too short` on stderr, exits 2, writes nothing to stdout, and leaves the store **unchanged** — same password material, same `failed_logins`, same `locked`, and `reset_token` still present with the same `token_hash`, `issued_at` and `ttl_seconds` (acceptance 3.1); presenting the **same** token again with a 12-character password then yields `password reset` / 0 (acceptance 3.2, FR-036f); an **empty** new-password line with a valid token is a password of length 0 → `password too short` / 2 with the token still usable, not `missing password input` (edge case); and SC-017 for **every ordering** — a refused token then a successful reset, a too-short password then a successful reset, and each pair in the opposite order — the correct token still works in all of them.
- [ ] T025 [US3] Audit and, if needed, correct the length guard in `_reset` in `src/accounts/cli.py` so a rejected password costs nothing: the `len(new) < MIN_PASSWORD_LENGTH` branch must return **before** `hashing.new_password_material` is called and **before** any `store.save`, so the rejection performs **zero** derivations and leaves the outstanding token armed by not writing at all (FR-036f, SC-018, contracts/store-file.md "reset failure → none, no write at all"). Add a test-visible assertion of the derivation count to `tests/test_reset.py` if it is not already covered by T024 — e.g. monkeypatch `hashing.new_password_material` to raise and confirm the too-short path still exits 2.

**Checkpoint**: User Stories 1, 2 and 3 all work independently — a common slip is a retry, not a second trip to an administrator.

---

## Phase 6: User Story 4 - A reset for an account that does not exist fails plainly (Priority: P4)

**Goal**: both new commands report `no such account` / 3 for a username absent from the store, consistently with `unlock`, `passwd` and `delete`, and a token never outlives the account it belongs to.

**Independent Test**: run `reset-token nobody` and `reset nobody` against a store without that account and assert `no such account` / 3 in both cases, with nothing on stdout and no store file created.

### Tests for User Story 4

- [ ] T026 [P] [US4] Extend `tests/test_reset_token.py` with the unknown-account tests (FR-032, FR-042, FR-043): `reset-token nobody` prints exactly `no such account` on stderr, exits 3, prints **nothing** on stdout — no token is leaked for a non-existent account — and creates or modifies **no** store file (acceptance 4.1); the same against a non-existent store path, which is the empty store, also gives `no such account` / 3 and creates no file (edge case, FR-002).
- [ ] T027 [P] [US4] Extend `tests/test_reset.py` with `reset`'s unknown-account and missing-input tests (FR-036, FR-036a, FR-037): `reset nobody` given a token line and a password line prints `no such account` on stderr and exits 3 with the store unchanged (acceptance 4.2); the same against a non-existent store path gives 3 and creates no file; **missing input beats a non-existent account** — `reset nobody` with completely empty stdin, and with only the token line, both give exactly `missing password input` / 2 with the store untouched, because input reading precedes dispatch (FR-036, FR-037, D-018); and **a corrupt store beats both** — `reset nobody` against a corrupt store gives `store unusable: ` / 5 (FR-037, plan.md consequence 3).
- [ ] T028 [P] [US4] Extend `tests/test_token_lifecycle.py` with the account-lifetime test (FR-036g, A-8): issue a token for `alice`, `delete alice`, `register alice` again with a different password, then `reset alice` with the old token → `invalid token` / 1, and assert the re-registered record carries **no** `reset_token` key at all, behaving exactly as an account that has never had a token issued (acceptance 4.3).
- [ ] T029 [US4] Audit both new handlers in `src/accounts/cli.py` and complete the unknown-account branch if anything is missing: `_reset_token` and `_reset` must each look the account up and return `MSG_NO_SUCH_ACCOUNT` / `EXIT_ACCOUNT_CONFLICT` **before** drawing a token, before any derivation and before any `store.save`, so an unknown account leaves no file behind (FR-032, FR-036a). Confirm `_delete` needs **no** change for FR-036g — token state is held nowhere but the account record, so `del data["accounts"][username]` already discards it (A-8, D-013) — and record that confirmation in the handler's docstring.

**Checkpoint**: all four user stories are independently functional; every outcome of both new commands is reachable and asserted.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: the success-criteria suite, the Principle III audit, the constitution gates and the documentation the plan commits to

- [ ] T030 [P] Create `tests/test_reset_criteria.py` for the success criteria not already implied by the story phases (SC-010…SC-020), each named in its test: **SC-011** — a forgotten password is recovered in three commands with no setup step, and identically for an account locked by five failed logins with no `unlock` among them, while a locked account whose token is merely outstanding still reports `account locked` / 4; **SC-016** — every outcome of the two new commands asserted exactly: statuses 0, 1, 2, 3 and 5, and the messages `password reset`, `invalid token`, `no such account`, `password too short`, `missing password input`, the full FR-040 usage line and the `store unusable: ` prefix, each on the stream where it belongs; **SC-018** — each new command completes within 1 second against a store of 1,000 accounts (use `low_iterations`), `reset-token` performs **zero** password derivations and `reset` performs **exactly one** and only after the token was accepted, asserted by counting calls to `hashing.derive` or `hashing.new_password_material` via monkeypatch; **SC-019** — a store holding token state is read and rewritten by all seven commands with the token state of untouched accounts preserved; **SC-020** — the four non-expiry routes to a token's end, cross-checked against `tests/test_token_lifecycle.py`. Where a criterion is already fully asserted elsewhere (SC-012, SC-013, SC-014, SC-015), reference the covering test by name in a comment rather than duplicating it.
- [ ] T031 [P] Update the module docstrings to name this feature's contracts: `src/accounts/cli.py` (add `specs/002-password-reset/contracts/cli.md` beside the 001 reference, and note `--ttl` and the two new handlers), `src/accounts/store.py` (add `specs/002-password-reset/contracts/store-file.md` and the optional `reset_token` object), `src/accounts/hashing.py` (note that the token functions use SHA-256 deliberately, not PBKDF2, per SC-018 and D-012, with the entropy argument from FR-034a). No `README` exists and none is added.
- [ ] T032 Run the Principle III audit: grep `tests/` for each of the 24 requirement identifiers FR-031, FR-032, FR-033, FR-034, FR-034a, FR-034b, FR-035, FR-036, FR-036a, FR-036b, FR-036c, FR-036d, FR-036e, FR-036f, FR-036g, FR-037, FR-038, FR-038a, FR-038b, FR-039, FR-040, FR-041, FR-042, FR-043, FR-044 and for SC-010…SC-020, and confirm each is named by at least one test name or comment. Any identifier with no hit is a feature-incomplete gate under Principle III and must be covered before T033 closes.
- [ ] T033 Run `pytest` from the repository root: zero failures, zero unexplained skips (Development Workflow gate 3), and `time pytest` under 60 seconds (SC-018). Confirm the shipped suite still passes with the two usage-line literals as its **only** edits — `pytest tests/test_cli_contract.py tests/test_register.py tests/test_login_lockout.py tests/test_unlock.py tests/test_passwd.py tests/test_delete.py tests/test_hashing.py tests/test_store_file.py` (SC-010, D-019) — and that `tests/test_store_file.py` lines 513 and 742 still pass unchanged on their `startswith("usage: python -m accounts")` assertions.
- [ ] T034 Walk every scenario in `specs/002-password-reset/quickstart.md` in a shell from the repository root (scenarios 1–7: issue and reset, locked-account recovery, wrong/spent/expired/cancelled tokens, the too-short password, unknown accounts and bad `--ttl`, the token absent from the store bytes, and pre-feature store compatibility) and confirm each documented status and message appears exactly as written, including the `$(...)` capture of `reset-token`'s output working with no line to select.
- [ ] T035 Run the final constitution gate audit and record the result: **I** — no non-stdlib import anywhere in `src/accounts/` (the only addition is `time`), `requirements-dev.txt` still reads `pytest` alone, no runtime dependency declaration added; **II** — every new error path has a test asserting both message and non-zero status, nothing is clamped or coerced, no bare `except`/`pass` added; **III** — T032 clean; **IV** — no new module, no new class, no clock seam, no `used` flag, and the three justified judgement calls (SHA-256 for the token fingerprint, the unused `ttl` parameter on five handlers, token validation in `store.py`) are the only deviations, each already tied to FR/SC in plan.md's Gate IV.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Setup — **blocks all four user stories**
- **User Stories (Phases 3–6)**: all depend on Phase 2; then either in priority order (P1 → P2 → P3 → P4) or in parallel across people, with the same-file caveat below
- **Polish (Phase 7)**: depends on every story phase that is being shipped

### User Story Dependencies

- **US1 (P1)**: depends only on Foundational. Delivers the whole capability; it is the MVP.
- **US2 (P2)**: depends only on Foundational for its one code change (T023, `_passwd`). Its tests need `_reset` from T019, so in practice run it after US1 — or stub nothing and simply accept that its test file is written first and fails until T019 lands.
- **US3 (P3)**: tests need `_reset` (T019); its own code change is the guard audit T025. Independent of US2.
- **US4 (P4)**: tests need both handlers (T018, T019); its code task T029 is an audit. Independent of US2 and US3.

### Same-file serialization (why some tasks lack [P])

| File | Tasks that touch it, in order |
|---|---|
| `src/accounts/cli.py` | T005, T008, T009, T010, T011, T018, T019, T023, T025, T029, T031 |
| `tests/test_reset_token.py` | T013, T014, T015, T026 |
| `tests/test_reset.py` | T016, T020, T021, T024, T027 |
| `tests/test_token_lifecycle.py` | T022, T028 |
| `src/accounts/hashing.py` | T003, T031 |
| `src/accounts/store.py` | T004, T031 |

Tasks sharing a row must not run concurrently; tasks in different rows may.

### Within Each User Story

- Tests are written first and must **fail** before the implementation tasks of that phase
- Foundational plumbing before handlers; handlers before cross-command lifecycle assertions
- A story is complete and validated before moving to the next priority

### Parallel Opportunities

- **Phase 2**: T003 (`hashing.py`) and T004 (`store.py`) in parallel; then T005, then T006 and T007 in parallel; T008–T011 are serialized by `cli.py`
- **Phase 3**: T013, T016 and T017 in parallel (three different new test files); T014 and T015 follow T013 in the same file
- **Phase 4**: T020 and T022 in parallel; T021 follows T020
- **Phase 6**: T026, T027 and T028 in parallel (three different files)
- **Phase 7**: T030 and T031 in parallel; T032–T035 are audits run in sequence at the end
- Across people after Phase 2: one developer on US1, one on US2's `_passwd` change and lifecycle file, with `cli.py` edits coordinated per the table above

---

## Parallel Example: User Story 1

```bash
# Launch the three new test files for User Story 1 together:
Task: "Create tests/test_reset_token.py with the issuing tests (T013)"
Task: "Create tests/test_reset.py with the happy path (T016)"
Task: "Create tests/test_reset_contract.py with the invocation surface (T017)"

# Then, serialized by cli.py:
Task: "Implement _reset_token handler (T018)"
Task: "Implement _token_valid and _reset handler (T019)"
```

## Parallel Example: Phase 2 Foundational

```bash
# Different source files, no shared state:
Task: "Add new_token/token_fingerprint/verify_token to src/accounts/hashing.py (T003)"
Task: "Add reset_token validation to src/accounts/store.py (T004)"

# After T005 updates the USAGE constant, the two literal edits are independent:
Task: "Update USAGE literal in tests/test_cli_contract.py (T006)"
Task: "Update USAGE literal in tests/test_success_criteria.py (T007)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (T001–T002)
2. Phase 2: Foundational (T003–T012) — **blocks everything**; the suite must be green at its checkpoint
3. Phase 3: User Story 1 (T013–T019)
4. **STOP and VALIDATE**: register, `reset-token`, `reset`, `login` — on an unlocked and on a locked account. Quickstart scenarios 1 and 2 pass.
5. This is a complete, useful capability: an account with a forgotten password can be recovered.

### Incremental Delivery

1. Setup + Foundational → the seven command words parse, `--ttl` is validated, token crypto and store validation exist
2. + US1 → **MVP**: issue a token, reset the password, log in (quickstart 1–2)
3. + US2 → every stale, wrong, expired or cancelled token refused; `passwd` cancels (quickstart 3)
4. + US3 → a too-short password is a retry, not a round trip (quickstart 4)
5. + US4 → unknown accounts and dead tokens fail plainly (quickstart 5)
6. + Polish → the criteria suite, the Principle III audit, the four constitution gates (quickstart 6–7)

Each step adds value and breaks nothing before it: the shipped five commands keep their behaviour throughout, with the usage line of FR-040 the single visible change.

### Parallel Team Strategy

1. Everyone on Setup + Foundational together (T003/T004 split cleanly; `cli.py` tasks T005–T011 go to one person)
2. Once Foundational is done:
   - Developer A: US1 (T013–T019) — owns `cli.py` while the handlers land
   - Developer B: US2's test file T022 and, after T019, T023
   - Developer C: US4's test files T026–T028, then Polish T030
3. Reconverge on T032–T035, which must be run against the whole suite

---

## Notes

- `[P]` = different files, no dependency on an incomplete task; see the same-file table before parallelizing
- `[Story]` maps a task to one user story for traceability; Setup, Foundational and Polish tasks carry no label
- **Every test must name the requirement it covers** in its name or a comment — Principle III makes this the condition for calling the feature complete, and T032 audits it
- Message strings are asserted for **equality**, never containment, except `store unusable: `, which is asserted as a **prefix** plus the specific cause
- Compare **parsed JSON**, not bytes, when inspecting the store — with two exceptions where the bytes are the point: SC-005 (no plaintext password) and SC-014 (no token in any form)
- A third edit to a shipped test file is a signal that the change has leaked past FR-041; re-examine rather than accommodate (D-019)
- Commit after each task or logical group; stop at any checkpoint to validate a story independently
