# Implementation Plan: Password Reset by One-Time Token

**Branch**: `002-password-reset` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-password-reset/spec.md`

## Summary

Two new operations on the existing tool — `reset-token` issues a short-lived,
single-use token for one account and prints it; `reset` redeems that token
together with a new password — while the five existing operations keep their
inputs, outputs, messages and exit statuses byte for byte.

Technical approach: **no new source module and no new mechanism.** The token is
`secrets.token_urlsafe(16)` (128 bits, 22 URL-safe characters). What is recorded
against the account is one optional record key, `reset`, holding a nested object
whose seven credential fields are deliberately the same names, types and ranges
as the account's own password fields, plus an integer `expires_ms` — so
`crypto.verify` and its `hmac.compare_digest` are reused unchanged and this
feature writes no new cryptographic code. Issuing assigns that key (which is
what makes "at most one outstanding token" structural rather than a check);
redeeming pops it inside the same `fcntl.flock` critical section that verified
it, which is what makes one token unable to set two passwords. `version` stays
at `1` and `reset` is optional, which is the whole of backward compatibility.
Every refused-token path answers the identical `invalid token`/status 1 after
spending exactly one scrypt derivation, so the refusals cannot be told apart by
message or by stopwatch. The only edit to code the five existing commands run is
a pure extraction of the stdin line reader so a token line can say "token" in
its diagnostics.

Full rationale and measurements: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.11+ (planning input, A-013). Development and
measurement host: CPython 3.13.17, Linux 6.18, x86-64.

**Primary Dependencies**: none at runtime — standard library only (Principle I,
A-013). Modules already used by the package: `argparse`, `base64`, `fcntl`,
`hashlib`, `hmac`, `json`, `os`, `pathlib`, `re`, `secrets`, `sys`. This feature
adds exactly one: **`time`** (for `time.time()`). Development only: `pytest`,
declared in `requirements-dev.txt` and never imported by shipped code.

**Storage**: the same single JSON file at the operator-supplied path, still
`version: 1`, extended by one optional per-record key. Format contract:
[contracts/store-format.md](./contracts/store-format.md).

**Testing**: `pytest`, driving the real executable in a subprocess with piped
streams so assertions are against the operator-visible contract. `pytest.ini`
already sets `pythonpath = src` and `testpaths = tests`; the 1 000-account,
concurrency, crash-loop and expiry-wait checks carry the existing `slow` marker.

**Target Platform**: POSIX (Linux, macOS), unchanged — `fcntl.flock` and
`os.replace` remain hard requirements.

**Project Type**: single-project CLI tool, extended from five to seven
operations. No network, no service, no UI, no role model (A-012, A-014).

**Performance Goals**: `reset-token` and `reset` each under 1 s on a
1 000-account store (SC-022). Measured components: one scrypt derivation
0.399 s; JSON parse of a 1 000-account store with reset material on every record
2.5 ms; serialise 3.6 ms. So `reset-token` ≈ 0.41 s and `reset` ≈ 0.81 s — about
1.2× headroom, flagged below. See
[research R20](./research.md#r20--performance-budget-and-a-flagged-tightness).

**Constraints**: unchanged limits — password 12–1 024 characters, input line
≤ 4 096 bytes, store ≤ 8 MiB, ≤ 10 000 accounts. Added: `--ttl` in `1 … 86400`
whole seconds (A-016); reset material of **fixed** 174-byte serialised size
(FR-043), so 10 000 accounts all carrying a token serialise to 3 440 027 bytes,
inside the existing cap. The issued token is the single value permitted to reach
an output stream (SR-018) and is written nowhere else.

**Scale/Scope**: single machine, single operator; 7 commands, 6 exit statuses
(status 4 unreachable from the two new ones). 24 functional, 9 security and 14
success-criteria requirements to cover, plus all 19 + 9 of feature 001 held
unchanged.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0.

| Gate | Pre-Phase 0 | Post-Phase 1 | Evidence |
|---|---|---|---|
| **I. Standard Library Only** — no third-party runtime import; bare `python3`, no install step; dev tools declared separately | PASS | **PASS** | Every mechanism Phase 0 chose is stdlib: `secrets.token_urlsafe`, `secrets.token_bytes`, `hashlib.scrypt`, `hmac.compare_digest`, `json`, `fcntl.flock`, `os.replace`, `argparse`, `re`, and the one addition `time.time`. `pytest` remains dev-only in `requirements-dev.txt`, never imported by `src/`. Run instruction unchanged: `PYTHONPATH=src python -m accounts`. |
| **II. Fail Loudly** — clear actionable message, non-zero exit, states expected/received/where, no broad suppression, no fallback or silent coercion | PASS | **PASS** | Every new failure has a row in [contracts/cli-contract.md](./contracts/cli-contract.md#failure-output) with its status. Malformed stored reset material is status 5 and is never repaired, defaulted or skipped — the SR-010 trap case, a malformed `expires_ms`, fails the load instead of reading as "not expired", which [research R13](./research.md#r13--representing-the-expiry-instant) is the reason the field is an integer. An over-long token line is refused, never truncated. The `--ttl` message names what was expected and what was received. **No new `except` clause of any kind is introduced**, so 001's single recorded suppression remains the only one. The one deliberate silence — `invalid token` carrying no detail — is not a Principle II violation but an explicit Principle V requirement (FR-026, SR-018); it is recorded in [Flagged notes](#flagged-notes-not-blocking) so the omission reads as chosen, not forgotten. |
| **III. Every Requirement Is Testable** — every FR and SR maps to a named automated test; error paths assert message *and* status | PASS | **PASS** | [Requirement-to-test mapping](#requirement-to-test-mapping) covers FR-020…043, SR-010…018 and SC-012…025 with no empty row. Tests assert status, stdout and stderr together. Security requirements are tested as negatives as well as positives. SC-019 is itself a test: the 001 suite runs unchanged apart from the two A-025 strings. |
| **IV. Simplicity** — smallest design, functions over classes, flat over nested, stdlib over hand-rolled, nothing for anticipated needs | PASS | **PASS** | **No new source module, no new class, no new mechanism.** The four existing modules gain functions; `crypto` gains exactly one (`new_token`) because `verify`, `dummy_verify`, `new_salt` and `hash_password` are reused as they stand. "At most one token" is structural (one key), not a check. Concurrency, atomicity, permissions, the stdin byte cap and the message sanitiser are all existing machinery reused. No audit trail, notification, rate limit or expiry sweep is built — A-027 says the request asks for none. **One** deviation, the nested `reset` object against the constitution's flat-over-nested preference, is recorded in [Complexity Tracking](#complexity-tracking) with the requirement that forces it. |
| **V. Secure by Default (NON-NEGOTIABLE)** — every applicable baseline rule named, mapped to an enforcing boundary with its stdlib mechanism, and tested | PASS | **PASS** | The spec walks all nine rules as SR-010…018 and justifies the non-applicable part (SR-012, path confinement, for SR-003's existing reason). [Security mapping](#security-requirement-mapping) gives the enforcing module, function, stdlib mechanism and test id for each. No rule is weakened: the token digest is held at the same OWASP-minimum work factor as a password even though that is what makes SC-022 tight, and timing parity on the refusal paths is *added* beyond what SR-018 literally demands. |

**Planning-stage obligation** (constitution, Security Requirements §Planning):
"map every security requirement to the module, function, or boundary that
enforces it, name the standard-library mechanism used, and record the
identifiers of the tests that will prove it" — discharged by the
[Security requirement mapping](#security-requirement-mapping).

**Gate result**: PASS before Phase 0 and PASS after Phase 1 design. One
justified complexity entry, no unjustified violation; nothing blocks
`/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/002-password-reset/
├── spec.md              # Feature specification (/speckit-specify output)
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 — R11…R20, decisions with measurements
├── data-model.md        # Phase 1 — the Reset token entity, extended Account and Store
├── quickstart.md        # Phase 1 — run and validation guide (V13…V25)
├── contracts/           # Phase 1 — both are deltas on feature 001's contracts
│   ├── cli-contract.md  #   the two new operations, statuses, messages, A-025 changes
│   └── store-format.md  #   the optional `reset` field, its validation, compatibility
├── checklists/
│   └── requirements.md  # existing
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

No file is added and no file is removed. The four existing modules are extended;
`__init__.py`, `__main__.py` and `errors.py` are untouched.

```text
src/
└── accounts/
    ├── __init__.py       # unchanged
    ├── __main__.py       # unchanged
    ├── errors.py         # unchanged
    ├── cli.py            # + COMMANDS/USAGE grow (A-025); + --ttl in parse_args;
    │                     #   + read_line extraction; + cmd_reset_token, cmd_reset
    ├── store.py          # + RESET_KEYS; validate_record accepts optional `reset`
    │                     #   and validates its interior
    ├── crypto.py         # + TOKEN_BYTES, new_token()  — verify/dummy_verify reused as-is
    └── validation.py     # + TTL_DEFAULT/MIN/MAX, EXPIRES_MS_MAX, validate_ttl()

tests/
├── conftest.py                    # + synthetic token literals, reset_material() builder,
│                                  #   issue_token() helper  (secrets hygiene: one place only)
├── test_cli_contract.py           # ~ the two A-025 strings; + seven commands accepted
├── test_reset_token.py            # NEW — US1 issuance, FR-021/022/028/029/031/032, US4
├── test_reset.py                  # NEW — US1 redemption, US3, FR-023/033/034/036/037
├── test_reset_invalid_token.py    # NEW — US2 all ten scenarios, SC-018
├── test_reset_security.py         # NEW — SR-010…018 negatives, leakage, entropy
├── test_compatibility.py          # NEW — US5, FR-040/041/042, SC-019, SC-020
├── test_store_format.py           # + `reset` field validation, malformed-expiry cases
├── test_concurrency.py            # + SC-023 simultaneous redemption (slow)
├── test_crash_safety.py           # + SC-024 kill during issue/redeem (slow)
├── test_performance.py            # + SC-022 at 1 000 accounts (slow)
├── test_example_sequence.py       # + SC-025 the new worked sequence
└── (test_register/login_lockout/passwd/delete/security.py — unchanged, and that is the point)

pytest.ini                         # unchanged
requirements-dev.txt               # unchanged — pytest only
```

**Structure Decision**: extend in place. The four boundaries feature 001
established are exactly the four this feature needs — request handling (`cli`),
persistence (`store`), cryptography (`crypto`), input rules (`validation`) — so
each new obligation lands in the module that already owns its kind of decision,
and the constitution's "map every security requirement to the boundary that
enforces it" rule is satisfied without a fifth boundary. A `reset.py` was
considered and rejected: it would have to reach into `store`'s record validation,
`crypto`'s parameters and `cli`'s check ordering, so it would add an import edge
and a boundary without owning a decision. Tests are added per user story, one
file per story, so each spec "Independent Test" stays a single runnable file —
and the five existing per-story test files staying untouched is itself the
evidence for FR-040.

## Security requirement mapping

Required by the constitution's Planning-stage obligation. Test ids are
`file::test` and are the names `/speckit-tasks` should carry forward.
SR-001 … SR-009 of feature 001 remain mapped by
[its plan](../001-user-accounts-cli/plan.md#security-requirement-mapping).

| SR | Enforcing module / function | Stdlib mechanism | Test id |
|---|---|---|---|
| **SR-010** all new input untrusted, allow-list, validate on the way in; stored reset material validated; malformed expiry is **not** "not expired" | `cli.parse_args` (`_command_name`), `validation.validate_username`, `validation.validate_ttl`, `cli.read_line`, `validation.check_settable_password`, `store.validate_record` → reset interior | `argparse choices=`, `re.fullmatch(r"[0-9]{1,5}")` **before** `int()`, explicit `type(v) is int` with range checks, closed `frozenset` field sets | `test_reset_token.py::test_fr022_ttl_allowlist`, `::test_sr010_int_does_not_accept_unicode_digits`, `test_reset_security.py::test_sr010_reset_field_allowlist`, `::test_sr010_malformed_expires_ms_is_status_5_not_unexpired`, `::test_sr010_invalid_reset_never_repaired_or_skipped` |
| **SR-011** no injection by concatenation; printed token cannot forge a line or a terminal control sequence | `store.serialise`/`store.load` (structured encoding only), `crypto.new_token` (alphabet), `validation.sanitize_for_message` | `json.dumps(ensure_ascii=True)` / `json.loads`; `secrets.token_urlsafe` alphabet is `[A-Za-z0-9_-]` only; no shell, query or markup anywhere in the feature | `test_reset_security.py::test_sr011_token_alphabet_is_safe_printable_ascii`, `::test_sr011_token_output_is_exactly_one_line`, `::test_sr011_control_chars_in_token_line_not_echoed` |
| **SR-012** path containment N/A (SR-003's recorded reason); temp-file discipline applies unchanged to both new writes | `store.atomic_write` — reused, not modified | `os.path.realpath` + `os.open(..., O_WRONLY\|O_CREAT\|O_EXCL, 0o600)` with `secrets.token_hex(8)` in the name; unlink on failure | `test_reset_security.py::test_sr012_no_temp_file_survives_a_failed_reset`, `::test_sr012_no_new_path_derived_from_input`, `test_reset_token.py::test_fr032_creates_no_file_when_store_absent` |
| **SR-013** token never stored or logged; salted slow digest at current parameters with a fresh salt per issuance; new password stored under SR-004 | `crypto.new_token` (generates, returns, does not persist), `cli._new_reset` (digest + salt + expiry), `cli._new_record` (reused for the new password) | `hashlib.scrypt(n=2**17, r=8, p=1, dklen=32, maxmem=192MiB)`, `secrets.token_bytes(16)` per issuance | `test_reset_security.py::test_sr013_token_absent_from_store_bytes`, `::test_sr013_fresh_salt_per_issuance`, `::test_sr013_token_digest_uses_current_parameters`, `::test_sr013_no_token_literal_in_repo_fixtures` |
| **SR-014** CSPRNG, ≥128 bits, constant-time comparison | `crypto.new_token`, `crypto.new_salt`, `crypto.verify` (reused) | `secrets.token_urlsafe(16)` → exactly 128 bits; `secrets.token_bytes`; `hmac.compare_digest` | `test_reset_security.py::test_sr014_token_entropy_is_at_least_128_bits`, `::test_sr014_ten_thousand_tokens_distinct`, `::test_sr014_package_never_imports_random`, `::test_sr014_token_compared_in_constant_time` |
| **SR-015** enforced maxima on every new input; expiry arithmetic bounded; fixed-size record; no super-linear matching | `cli.read_line` (4 096 B cap), `validation.validate_ttl` (5 digits then `1…86400`), `validation.EXPIRES_MS_MAX`, `store.validate_record` | `BufferedReader.readline(4097)`; bounded character class with no alternation or nesting; range check on `expires_ms` | `test_reset.py::test_sr015_overlong_token_line_refused_not_truncated`, `test_reset_token.py::test_sr015_ttl_bounded_at_five_digits`, `test_reset_security.py::test_sr015_reset_material_is_fixed_size`, `test_store_format.py::test_sr015_expires_ms_out_of_range_is_status_5` |
| **SR-016** authorisation at the point of operation; holds under concurrency; expiry and single use read from the store at the attempt | `cli.cmd_reset` (verify → change → consume, all in one invocation), `store.locked_store` (reused) | `fcntl.flock(dir_fd, LOCK_EX)` held across the whole read–modify–write; `record.pop("reset", None)` inside that section; `time.time()` read in the attempting invocation | `test_reset.py::test_sr016_expiry_read_at_attempt_not_cached`, `test_reset_invalid_token.py::test_fr037_current_password_not_accepted_as_token`, `test_concurrency.py::test_sc023_simultaneous_redemption_one_success`, `::test_sr016_concurrent_issuance_leaves_one_token` |
| **SR-017** least-privilege files, set at creation; nothing written anywhere else | `store.atomic_write` (reused, unmodified) | explicit `0o600` mode argument to `os.open`, preserved across `os.replace` | `test_reset_security.py::test_sr017_store_mode_600_after_issue_and_redeem`, `::test_sr017_no_sidecar_spool_or_log_created` |
| **SR-018** no sensitive data in output; the token is the single deliberate exception; all refusals identical; redaction before writing | `cli` message table, `validation.sanitize_for_message`, `cli._reset_is_valid` (one derivation on every refusal path), `errors.AccountsError` (carries pre-redacted text only) | fixed string `invalid token`; `crypto.dummy_verify` for timing parity; lengths and counts only in messages; no traceback reaches a stream | `test_reset_security.py::test_sr018_no_secret_material_in_either_stream`, `::test_sr018_token_only_on_reset_token_stdout_on_success`, `::test_sr018_all_refusal_paths_byte_identical`, `::test_sr018_refusal_timing_parity`, `::test_sr018_no_traceback_on_any_new_failure_path` |

## Requirement-to-test mapping

Principle III makes an unmapped requirement a blocker. No row is empty.
FR-001 … FR-019 and SR-001 … SR-009 remain mapped by
[feature 001's plan](../001-user-accounts-cli/plan.md#requirement-to-test-mapping)
and their tests are re-run unchanged (SC-019).

| Requirement | Test id |
|---|---|
| FR-020 seven operations, no other name, five unchanged | `test_cli_contract.py::test_fr020_seven_commands_accepted`, `test_compatibility.py::test_fr040_existing_five_unchanged` |
| FR-021 `--ttl` optional, default 900, only with `reset-token`, no abbreviation, not repeated | `test_reset_token.py::test_fr021_default_validity_is_900`, `::test_fr021_ttl_only_with_reset_token`, `::test_fr021_ttl_not_abbreviated`, `::test_fr021_ttl_not_repeated` |
| FR-022 validity accepted only in range, else 2 with expected/received and no token | `test_reset_token.py::test_fr022_ttl_allowlist`, `::test_fr022_invalid_ttl_issues_no_token` |
| FR-023 `reset-token` reads nothing; `reset` reads exactly two lines; extras ignored; short stream is 2 | `test_reset_token.py::test_fr023_succeeds_with_stdin_closed`, `test_reset.py::test_fr023_two_lines_in_order`, `::test_fr023_extra_lines_ignored`, `::test_fr023_missing_input_is_status_2` |
| FR-024 only the documented statuses; status 4 unreachable | `test_reset.py::test_fr024_every_status_reachable`, `test_reset_token.py::test_fr024_no_status_4_ever` |
| FR-025 success output exactly, stderr empty | `test_reset_token.py::test_fr025_token_is_the_only_stdout_line`, `test_reset.py::test_fr025_password_reset_on_stdout` |
| FR-026 one stderr line, empty stdout, `invalid token` detail-free | `test_reset_invalid_token.py::test_fr026_failure_streams`, `::test_fr026_invalid_token_is_exact_and_detail_free` |
| FR-027 failures leave the store byte-identical; no count or lock write | `test_reset_invalid_token.py::test_fr027_store_byte_identical_after_each_failure`, `::test_fr039_wrong_token_does_not_increment_count` |
| FR-028 generate, record, persist, print | `test_reset_token.py::test_fr028_issue_records_material_and_prints_token` |
| FR-029 at most one outstanding; issuing replaces | `test_reset_token.py::test_fr029_reissue_replaces`, `test_reset_invalid_token.py::test_fr029_replaced_token_refused` |
| FR-030 valid until elapsed, measured at each attempt | `test_reset.py::test_fr030_valid_before_expiry`, `test_reset_invalid_token.py::test_fr030_expired_token_refused` |
| FR-031 succeeds on a locked account, changing neither lock nor count | `test_reset_token.py::test_fr031_issue_on_locked_account_changes_nothing` |
| FR-032 `reset-token` does not create the store | `test_reset_token.py::test_fr032_creates_no_file_when_store_absent` |
| FR-033 exact order of checks | `test_reset.py::test_fr033_check_order_precedence` |
| FR-034 sets password, consumes token, zeroes count, clears lock, leaves others alone | `test_reset.py::test_fr034_reset_replaces_password_and_clears_lock`, `::test_fr034_other_accounts_byte_identical` |
| FR-035 usable at most once, including concurrently | `test_reset_invalid_token.py::test_fr035_second_use_refused`, `test_concurrency.py::test_sc023_simultaneous_redemption_one_success` |
| FR-036 short/long new password: status 2, password unchanged, token survives with original expiry | `test_reset.py::test_fr036_short_password_keeps_token`, `::test_fr036_long_password_keeps_token`, `::test_fr036_expiry_unchanged_after_refusal` |
| FR-037 no current password required or accepted | `test_reset.py::test_fr037_no_current_password_required`, `test_reset_invalid_token.py::test_fr037_current_password_not_accepted_as_token` |
| FR-038 `reset` does not create the store | `test_reset.py::test_fr038_creates_no_file_when_store_absent` |
| FR-039 refused token does not increment the count and is not restricted by a lockout | `test_reset_invalid_token.py::test_fr039_wrong_token_does_not_increment_count`, `test_reset.py::test_fr039_lockout_does_not_restrict_reset` |
| FR-040 five operations unchanged but for the A-025 strings | `test_compatibility.py::test_fr040_existing_five_unchanged`, `::test_a025_only_two_diagnostics_changed`, and the eleven unchanged 001 test files |
| FR-041 pre-feature store loads; every password still verifies | `test_compatibility.py::test_fr041_pre_feature_store_loads`, `::test_fr041_passwords_still_verify` |
| FR-042 `passwd` invalidates, `delete` removes, `login`/`unlock` leave alone | `test_compatibility.py::test_fr042_passwd_invalidates_token`, `::test_fr042_delete_removes_token`, `::test_fr042_login_and_unlock_leave_token` |
| FR-043 existing limits hold; reset material fixed and bounded | `test_reset.py::test_sr015_overlong_token_line_refused_not_truncated`, `test_reset_security.py::test_sr015_reset_material_is_fixed_size` |
| SR-010 … SR-018 | see [security mapping](#security-requirement-mapping) |
| SC-012 every extended outcome reachable and asserted | `test_reset.py::test_fr024_every_status_reachable` |
| SC-013 cross-invocation redemption; second attempt refused | `test_reset.py::test_sc013_issue_and_redeem_across_invocations`, `test_reset_invalid_token.py::test_fr035_second_use_refused` |
| SC-014 accepted before, refused after, default and explicit validity | `test_reset.py::test_sc014_validity_boundary_explicit`, `::test_sc014_validity_boundary_default` |
| SC-015 token appears nowhere but the one stdout line | `test_reset_security.py::test_sr013_token_absent_from_store_bytes`, `::test_sc015_token_in_no_temp_file_or_stderr` |
| SC-016 10 000 tokens distinct, ≥128 bits each | `test_reset_security.py::test_sr014_ten_thousand_tokens_distinct`, `::test_sr014_token_entropy_is_at_least_128_bits` |
| SC-017 refused password leaves the token usable | `test_reset.py::test_fr036_short_password_keeps_token` |
| SC-018 all refusals indistinguishable | `test_reset_security.py::test_sr018_all_refusal_paths_byte_identical`, `::test_sr018_refusal_timing_parity` |
| SC-019 the 001 suite passes against the extended tool | `test_compatibility.py::test_sc019_feature_001_suite_passes` plus the eleven unchanged files |
| SC-020 pre-feature store loads and verifies | `test_compatibility.py::test_fr041_pre_feature_store_loads` |
| SC-021 failures byte-identical; other accounts byte-identical after success | `test_reset_invalid_token.py::test_fr027_store_byte_identical_after_each_failure`, `test_reset.py::test_fr034_other_accounts_byte_identical` |
| SC-022 each operation under a second at 1 000 accounts | `test_performance.py::test_sc022_reset_operations_under_one_second`, `::test_sc022_store_scaling_component_negligible` |
| SC-023 simultaneous redemption: one success | `test_concurrency.py::test_sc023_simultaneous_redemption_one_success` |
| SC-024 kill mid-operation leaves a valid store | `test_crash_safety.py::test_sc024_sigkill_during_issue_and_redeem` |
| SC-025 documented sequence reproduced line for line | `test_example_sequence.py::test_sc025_reset_worked_sequence` |

## Check ordering

Fixed by FR-033 for `reset` and by the analogous reasoning for `reset-token`;
full tables in
[research R14](./research.md#r14--ordering-of-checks-for-the-two-new-operations),
asserted by `test_reset.py::test_fr033_check_order_precedence`. The three
non-obvious points:

- **The token is judged before the new password.** The password line is *read*
  before the store is opened (so a missing or over-long line is a status-2 bad
  request) but *validated* only after the token is accepted. An expired token
  with an 11-character password therefore answers `invalid token`/1, not 2
  (scenario 3.4). Reversing this would leak whether a token is outstanding,
  because the two statuses would distinguish "valid token, bad password" from
  "bad token, bad password".
- **Neither operation checks the lock at all**, exactly as `passwd` and `delete`
  already do not (FR-019), which is what makes status 4 unreachable from both
  (FR-024, FR-031, FR-039, A-018).
- **Nothing is written before the last step.** That is the single reason FR-027
  (failures change nothing), FR-036 (a refused password leaves the token with its
  original expiry) and FR-039 (no failure count on a refused token) all hold
  without individual safeguards.

## Flagged notes (not blocking)

Decided during planning so design and implementation can proceed. Each is a
candidate for `/speckit-clarify`; none changes the architecture.

1. **`reset` has only ~1.2× headroom against SC-022's absolute one-second
   bound.** Two deliberate scrypt derivations — verify the token, hash the new
   password — are inherent to the operation, and at the measured 0.399 s each
   that is ≈ 0.81 s on this host, with the store-size component ~6 ms. This is
   the same position feature 001 recorded for `passwd` and has the same single
   lever: the work factor. SR-013 names "the same deliberately slow algorithm and
   current parameters already used for passwords", and Principle IV forbids
   simplifying away a Principle V control, so lowering it is an SR-013/SR-004
   amendment rather than an implementation choice. The suite asserts both the
   absolute bound and the hardware-independent scaling claim. See
   [research R20](./research.md#r20--performance-budget-and-a-flagged-tightness).
2. **`invalid token` deliberately violates Principle II's "state what was
   expected and what was received".** FR-026 and SR-018 require one
   indistinguishable answer across wrong, used, replaced, expired and
   never-issued, so the operator gets no diagnostic help here. This is a
   requirement conflict the spec resolves in Principle V's favour, and the plan
   follows it; it is recorded so the missing detail reads as chosen. Timing
   parity was *added* beyond the literal requirement for the same reason
   ([research R17](./research.md#r17--making-every-refusal-indistinguishable-including-by-stopwatch)).
3. **`version` stays at `1`, so a store carrying a token is unreadable by the
   previous build.** Bumping it would make every pre-existing store unloadable
   and break FR-041 outright, so the asymmetry A-026 already anticipates is
   accepted: the old build reports such a store as malformed (status 5) — loud,
   never misread. If downgrading ever becomes a requirement, it needs a real
   migration path and a clarification, not a version number
   ([research R18](./research.md#r18--store-compatibility-in-both-directions)).
4. **`--ttl 0060` is accepted as 60.** `validate_ttl` allows `[0-9]{1,5}`, so a
   leading zero passes. Rejecting it would need a second pattern for no stated
   benefit; the behaviour is documented in the contract and pinned by a test so
   it is a decision rather than an accident.
5. **An expired `reset` field is never swept.** A-027 says the request asks for
   no expiry sweep, so an expired token simply stops being accepted and is
   overwritten by the next issuance or removed by the next successful `reset`,
   `passwd` or `delete` for that account. A store can therefore carry expired
   material indefinitely — harmless, fixed-size, and verified by SC-021's byte
   comparisons to change nothing.

**Non-applicability already justified in the spec**: SR-012's path-containment
rule does not apply, for SR-003's recorded reason — naming the store is the
operator's explicit purpose — and this feature introduces no new path derived
from input at all. The temporary-file half of the rule does apply and is
enforced by the unmodified `store.atomic_write`. Principle V requires this
statement rather than silence.

## Complexity Tracking

> Deviations toward added structure, each with the requirement that forces it
> (Principle IV). Feature 001's five entries remain in force and are not
> restated. This feature adds **one**.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| A **nested** `reset` object inside the account record, against the constitution's explicit "prefer … a flat data structure over a nested one" | SR-013 requires the token's verification material to be a salted digest from the same slow algorithm and *current parameters* as a password, which means carrying the same seven credential fields. Nesting them under one key is what lets `crypto.verify` — and with it the `hmac.compare_digest` that SR-014 mandates — be reused **with no change**, so this feature writes no new cryptographic code. It is also what makes FR-029/A-015 ("at most one outstanding token, issuing replaces") structural rather than a check that can be forgotten, and FR-035's consumption a single `pop` inside the locked section | Eight flat keys (`reset_kdf` … `reset_expires_ms`) was the Principle IV default. Rejected because `crypto.verify` would then need a key-prefix parameter or a caller-built projection dict — new code on the one path where constant-time comparison lives — and because "replace the token" and "consume the token" become eight-key operations where missing one leaves half a token behind, in a record whose field set is a closed allow-list. The nesting costs one level of depth (3 → 4) in a structure that is still non-recursive, still linear to parse, and still of fixed per-record size |

This entry *adds* no control and relaxes none; it is a shape decision taken to
let an existing Principle V control be reused rather than reimplemented. No
entry here weakens Principle V.
