# Implementation Plan: Local User Account Manager (CLI)

**Branch**: `001-user-accounts-cli` | **Date**: 2026-11-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-user-accounts-cli/spec.md`

## Summary

A single-invocation CLI that keeps named local accounts with passwords in one
JSON file, invoked as `python -m accounts --store PATH COMMAND USERNAME`, with
passwords read only from stdin and every outcome reported as one of six
documented exit statuses.

Technical approach: a flat, six-module package under `src/accounts/` with no
classes beyond one error type. Passwords are stored as `hashlib.scrypt`
digests at the OWASP-minimum work factor with a per-account 16-byte
`secrets` salt and the parameters recorded per record; digests are compared
with `hmac.compare_digest`. The store is one JSON document validated
field-by-field against an allow-list on every load, size-capped before parsing,
and replaced atomically by writing a `0o600` temporary file in the store's own
directory and `os.replace`-ing it over the target. Every command holds an
exclusive `fcntl.flock` on the store's *directory* — not the file, which may
not exist yet and whose inode the rename swaps — for the whole
read–modify–write, which is what stops concurrent failed logins from losing a
failure-count increment. Lock state is derived from the failure count rather
than stored alongside it.

Full rationale and measurements: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.11+ (A-013, confirmed by the planning input).
Development and measurement host: CPython 3.13.17, Linux 6.18, x86-64.

**Primary Dependencies**: none at runtime — standard library only (A-013,
Principle I). Modules used: `argparse`, `base64`, `fcntl`, `hashlib`, `hmac`,
`json`, `os`, `re`, `secrets`, `sys`. Development only: `pytest`, declared in
`requirements-dev.txt` and never imported by shipped code.

**Storage**: one JSON file at the operator-supplied path, created on first
`register`, replaced atomically thereafter. Format contract:
[contracts/store-format.md](./contracts/store-format.md).

**Testing**: `pytest`, driving the real executable in a subprocess with piped
stdin/stdout/stderr so the assertions are against the operator-visible
contract. `pytest.ini` sets `pythonpath = src` and `testpaths = tests`; the
1 000-account and crash-loop tests carry a `slow` marker.

**Target Platform**: POSIX (Linux, macOS). `fcntl.flock` and `os.replace` are
both hard requirements; there is no Windows support in scope.

**Project Type**: single-project CLI tool. No network, no service, no UI
(A-012).

**Performance Goals**: every command under 1 s on a 1 000-account store
(FR-010, SC-007). Measured: store load+save for 1 000 accounts is 3.0 ms
combined, so the budget is dominated by the deliberate KDF cost of 0.369 s per
derivation — `passwd` performs two. See
[research R8](./research.md#r8--performance-budget-against-sc-007) and the
flagged note below.

**Constraints**: password 12–1 024 characters; input line ≤ 4 096 bytes; store
file ≤ 8 MiB; ≤ 10 000 accounts (A-011). scrypt `maxmem` 192 MiB bounds
per-invocation memory. No password in any argument, output stream, temporary
file, or repository file including fixtures.

**Scale/Scope**: single machine, single operator, 5 commands, 6 exit statuses,
~1 000 accounts typical and 10 000 maximum. 19 functional, 9 security and 11
success-criteria requirements to cover.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0.

| Gate | Pre-Phase 0 | Post-Phase 1 | Evidence |
|---|---|---|---|
| **I. Standard Library Only** — no third-party runtime import; runs on a bare `python3` with no install step; dev tools declared separately | PASS | **PASS** | Every mechanism chosen in Phase 0 is stdlib: `hashlib.scrypt`, `secrets`, `hmac.compare_digest`, `json`, `fcntl.flock`, `os.replace`, `argparse`. `pytest` is dev-only, declared in `requirements-dev.txt`, never imported by `src/`. Run instruction is `PYTHONPATH=src python -m accounts` — no install. |
| **II. Fail Loudly** — clear actionable message, non-zero exit, states expected/received/where, no broad suppression, no fallback or silent coercion | PASS | **PASS** | Six-status contract with a message table in [contracts/cli-contract.md](./contracts/cli-contract.md); every non-zero status writes one stderr line naming what was expected and what was received. A malformed store is status 5, never repaired, skipped or treated as empty ([store-format.md](./contracts/store-format.md#validation-discipline)). An over-long password is refused, never truncated. `except` clauses are narrow (`OSError`, `JSONDecodeError`, `UnicodeDecodeError`, `RecursionError`) and each one maps to a status rather than to a default. One deliberate exception-suppression is recorded in Complexity Tracking. |
| **III. Every Requirement Is Testable** — every FR and SR maps to a named automated test; error paths assert message *and* status | PASS | **PASS** | [Requirement-to-test mapping](#requirement-to-test-mapping) below covers FR-001…019, SR-001…009 and SC-001…011 with no unmapped row. Tests assert exit status, stdout and stderr together. Security requirements are tested as negatives (rejected input) as well as positives. |
| **IV. Simplicity** — smallest design, functions over classes, flat over nested, stdlib over hand-rolled, nothing for anticipated needs | PASS | **PASS** | Six modules, five with code, no classes except one exception type. Store and account are plain `dict`s, not models. Lock state is *derived* rather than stored, removing a field and a whole malformed-store case ([research R7](./research.md#r7--lock-state-is-derived-not-stored)). `argparse` chosen over hand-rolled parsing per the stdlib preference ([research R10](./research.md#r10--argument-parsing)). No config system, no plugin layer, no abstraction over the KDF, no "future" fields. Three justified deviations are recorded in Complexity Tracking. |
| **V. Secure by Default (NON-NEGOTIABLE)** — every applicable baseline rule named, mapped to an enforcing boundary with its stdlib mechanism, and tested | PASS | **PASS** | The spec enumerates all nine rules as SR-001…009 and justifies the one non-applicable part (SR-003, path confinement). [Security mapping](#security-requirement-mapping) gives the enforcing module, function, stdlib mechanism and test id for each. No rule is weakened: the KDF is held at the OWASP minimum work factor even where that costs performance headroom. |

**Planning-stage obligation** (constitution, Security Requirements §Planning):
"map every security requirement to the module, function, or boundary that
enforces it, name the standard-library mechanism used, and record the
identifiers of the tests that will prove it" — discharged by the
[Security requirement mapping](#security-requirement-mapping) table.

**Gate result**: PASS before Phase 0 and PASS after Phase 1 design. No
unjustified violation; nothing blocks `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/001-user-accounts-cli/
├── spec.md              # Feature specification (/speckit-specify output)
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output — mechanism decisions with measurements
├── data-model.md        # Phase 1 output — entities, fields, state transitions
├── quickstart.md        # Phase 1 output — run and validation guide (V1…V12)
├── contracts/           # Phase 1 output
│   ├── cli-contract.md  #   invocation, stdin protocol, exit statuses, messages
│   └── store-format.md  #   on-disk format, validation and write discipline
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/
└── accounts/
    ├── __init__.py       # package marker and version string; no logic
    ├── __main__.py       # `python -m accounts` entry: sys.exit(cli.main(sys.argv[1:]))
    ├── cli.py            # argv parsing, stdin reading, the five commands, exit statuses, messages
    ├── store.py          # directory lock, load+validate, atomic 0o600 write, size/count limits
    ├── crypto.py         # scrypt parameters, salt generation, hash, constant-time verify, dummy verify
    ├── validation.py     # username and password rules, the four A-011 limits
    └── errors.py         # AccountsError(status, message) — the only class in the package

tests/
├── conftest.py              # tmp store path, subprocess runner, store-builder fixtures
├── test_cli_contract.py     # FR-001…005: usage, unknown command, arg shape, stream discipline
├── test_register.py         # US1 scenarios 1, 5, 6, 7
├── test_login_lockout.py    # US1 scenarios 2-4, all of US2
├── test_passwd.py           # US3 scenarios
├── test_delete.py           # US4 scenarios
├── test_store_format.py     # FR-007…009, store validation, limits, permissions, atomicity
├── test_security.py         # SR-001…009 negatives, leakage, enumeration parity
├── test_concurrency.py      # SR-007 interleaving (slow)
├── test_crash_safety.py     # SC-009 SIGKILL loop (slow)
├── test_performance.py      # FR-010, SC-007 at 1 000 accounts (slow)
└── test_example_sequence.py # SC-011 worked sequence, line for line

pytest.ini                   # pythonpath = src, testpaths = tests, slow marker
requirements-dev.txt          # pytest — development dependency only (Principle I)
```

**Structure Decision**: single project, flat package. A-013 fixes the package
name, its location under `src/`, and `python -m accounts` as the entry point,
so `src/accounts/` with `__main__.py` is given rather than chosen. Principle IV
prefers a module to a package, but the mandated `python -m accounts` form
requires a package; within it the layout is as flat as the security mapping
allows — the split into `cli` / `store` / `crypto` / `validation` exists because
the constitution's planning stage requires each security requirement to name
*the boundary that enforces it*, and these are those four boundaries (request
handling, persistence, cryptography, input rules). No `models/`, `services/` or
`lib/` layering: there is nothing to put in them. Tests are split by user story
and by cross-cutting concern so each story's "Independent Test" from the spec
is a single runnable file.

## Security requirement mapping

Required by the constitution's Planning-stage obligation. Test ids are
`file::test` and are the names `/speckit-tasks` should carry forward.

| SR | Enforcing module / function | Stdlib mechanism | Test id |
|---|---|---|---|
| **SR-001** all input untrusted, allow-list, validate on the way in | `cli.parse_args` (command), `validation.validate_username`, `validation.check_settable_password`, `store.load` → `store._validate_record` | `argparse` `choices=`, `re.fullmatch` on `[A-Za-z0-9_]{3,32}`, explicit `type(v) is int` field checks | `test_cli_contract.py::test_sr001_unknown_command_rejected`, `test_security.py::test_sr001_record_field_allowlist`, `::test_sr001_unknown_record_field_is_status_5`, `::test_sr001_invalid_record_never_skipped_or_repaired` |
| **SR-002** no injection by concatenation | `store.dump` / `store.load` (structured encoding only), `cli.sanitize_for_message` | `json.dumps(ensure_ascii=True)` / `json.loads`; no shell, no query, no markup anywhere in the feature | `test_security.py::test_sr002_delimiter_in_username_cannot_split_record`, `::test_sr002_control_chars_not_echoed_raw_to_stderr` |
| **SR-003** path containment N/A; temp-file discipline applies | `store.atomic_write` | `os.path.realpath` + `os.open(..., O_WRONLY\|O_CREAT\|O_EXCL, 0o600)` with `secrets.token_hex(8)` in the name; `os.unlink` on failure | `test_store_format.py::test_sr003_temp_file_in_store_directory_only`, `test_security.py::test_sr003_no_temp_file_survives_failure`, `::test_sr003_temp_name_unpredictable_and_exclusive` |
| **SR-004** credential storage | `crypto.hash_password`, `crypto.verify`; no password crosses into `store` or `cli` output | `hashlib.scrypt(n=2**17, r=8, p=1, dklen=32, maxmem=192MiB)`, `secrets.token_bytes(16)` per account | `test_security.py::test_sr004_password_absent_from_store_bytes`, `::test_sr004_params_recorded_per_record`, `::test_sr004_no_plaintext_in_repo_fixtures` |
| **SR-005** CSPRNG and constant-time comparison | `crypto.new_salt`, `crypto.verify` | `secrets.token_bytes`, `hmac.compare_digest` | `test_security.py::test_sr005_salts_unique_across_accounts`, `::test_sr005_verify_uses_constant_time_compare` |
| **SR-006** resource limits, bounded parsing | `cli.read_password_line` (4 096 B), `validation` limits, `store.load` (8 MiB pre-parse via `fstat`, 10 000 accounts), `crypto` (`maxmem`) | `BufferedReader.readline(4097)`, `os.fstat(fd).st_size`, caught `RecursionError`, no regex in the parse path | `test_security.py::test_sr006_overlong_line_refused_not_truncated`, `::test_sr006_oversize_store_refused_before_parsing`, `::test_sr006_deeply_nested_store_is_status_5`, `test_store_format.py::test_sr006_account_count_cap` |
| **SR-007** authorisation at the point of operation; holds under concurrency | `cli.cmd_passwd` / `cmd_delete` / `cmd_login` (verify inside the same invocation), `store.locked_store` context manager | `fcntl.flock(dir_fd, LOCK_EX)` held across the whole read–modify–write | `test_passwd.py::test_sr007_wrong_current_password_blocks_change`, `test_concurrency.py::test_sr007_concurrent_failures_cannot_exceed_five`, `::test_sr007_concurrent_registers_do_not_lose_an_account` |
| **SR-008** least-privilege files, set at creation | `store.atomic_write` | explicit `0o600` mode argument to `os.open`, preserved across `os.replace` | `test_store_format.py::test_sr008_store_mode_600_on_create`, `::test_sr008_store_mode_600_after_passwd_replace` |
| **SR-009** no sensitive data in output | `cli` message table + `cli.sanitize_for_message`; `errors.AccountsError` carries only pre-redacted text | fixed strings for `invalid credentials` / `account locked`; lengths and counts only; no traceback reaches a stream | `test_security.py::test_sr009_no_secret_material_in_either_stream`, `::test_sr009_unknown_and_wrong_password_identical_output`, `::test_sr009_no_traceback_on_any_failure_path`, `::test_sr009_store_path_is_the_only_path_echoed` |

## Requirement-to-test mapping

Principle III makes an unmapped requirement a blocker. No row is empty.

| Requirement | Test id |
|---|---|
| FR-001 invocation form, five commands | `test_cli_contract.py::test_fr001_invocation_form`, `::test_fr001_five_commands_accepted` |
| FR-002 no password in argv; stdin one per line | `test_cli_contract.py::test_fr002_stdin_protocol_per_command`, `test_security.py::test_fr002_no_password_accepted_as_argument` |
| FR-003 exactly six statuses | `test_cli_contract.py::test_fr003_every_status_reachable`, `::test_fr003_no_other_status_observed` |
| FR-004 success output and silent stderr | `test_cli_contract.py::test_fr004_success_output_per_command` |
| FR-005 failure message to stderr, empty stdout, exact fixed strings | `test_cli_contract.py::test_fr005_failure_streams`, `::test_fr005_exact_fixed_messages` |
| FR-006 failing operation changes nothing | `test_store_format.py::test_fr006_store_byte_identical_after_each_failure` |
| FR-007 single file, created only by `register` | `test_store_format.py::test_fr007_register_creates_store`, `::test_fr007_other_commands_create_nothing` |
| FR-008 readable by later invocations | `test_store_format.py::test_fr008_round_trip_across_invocations` |
| FR-009 all-at-once visibility | `test_crash_safety.py::test_fr009_store_old_or_new_never_mixed` |
| FR-010 1 000 accounts under a second | `test_performance.py::test_fr010_thousand_account_store` |
| FR-011 username rules, case-sensitive | `test_register.py::test_fr011_username_length_and_charset`, `::test_fr011_case_sensitive_distinct_accounts` |
| FR-012 password length when set | `test_register.py::test_fr012_password_min_length`, `test_passwd.py::test_fr012_new_password_min_length` |
| FR-013 verify current password first | `test_login_lockout.py::test_fr013_login_verifies`, `test_passwd.py::test_fr013_verify_before_change`, `test_delete.py::test_fr013_verify_before_removal` |
| FR-014 four enforced maxima | `test_security.py::test_sr006_overlong_line_refused_not_truncated`, `test_register.py::test_fr014_password_max_length`, `test_store_format.py::test_sr006_account_count_cap`, `test_security.py::test_sr006_oversize_store_refused_before_parsing` |
| FR-015 count increments and resets | `test_login_lockout.py::test_fr015_failure_increments`, `::test_fr015_success_resets` |
| FR-016 lock at five; fifth still status 1 | `test_login_lockout.py::test_fr016_fifth_failure_is_status_1`, `::test_fr016_sixth_attempt_is_locked` |
| FR-017 locked login reports 4 regardless of password | `test_login_lockout.py::test_fr017_correct_password_refused_when_locked`, `::test_fr017_lock_reported_before_password_considered` |
| FR-018 `unlock` clears, needs no password, idempotent | `test_login_lockout.py::test_fr018_unlock_restores_access`, `::test_fr018_unlock_on_unlocked_account_succeeds`, `::test_fr018_unlock_reads_no_stdin` |
| FR-019 `passwd`/`delete` work when locked; `passwd` resets | `test_passwd.py::test_fr019_passwd_works_on_locked_account`, `::test_fr019_passwd_resets_failure_count`, `test_delete.py::test_fr019_delete_works_on_locked_account` |
| SR-001 … SR-009 | see [security mapping](#security-requirement-mapping) |
| SC-001 every status reachable and asserted | `test_cli_contract.py::test_fr003_every_status_reachable` |
| SC-002 cross-invocation persistence | `test_store_format.py::test_fr008_round_trip_across_invocations` |
| SC-003 no success after five failures until unlock | `test_login_lockout.py::test_sc003_no_guess_succeeds_while_locked` |
| SC-004 wrong password and unknown account indistinguishable | `test_security.py::test_sr009_unknown_and_wrong_password_identical_output`, `::test_sc004_timing_parity_for_unknown_account` |
| SC-005 password nowhere on disk or in output | `test_security.py::test_sr004_password_absent_from_store_bytes`, `::test_sc005_no_password_in_any_temp_file` |
| SC-006 same password, different stored material | `test_security.py::test_sc006_same_password_different_digests` |
| SC-007 under a second; rejection timing independent of the wrong part | `test_performance.py::test_sc007_each_command_under_one_second`, `::test_sc007_store_scaling_component_negligible`, `test_security.py::test_sc007_rejection_timing_independent_of_mismatch_position` |
| SC-008 failures leave the store as it was | `test_store_format.py::test_fr006_store_byte_identical_after_each_failure`, `::test_sc008_only_exception_is_login_failure_count` |
| SC-009 kill mid-write leaves a valid store | `test_crash_safety.py::test_sc009_sigkill_loop_store_always_valid` |
| SC-010 owner-only store | `test_store_format.py::test_sr008_store_mode_600_on_create` |
| SC-011 documented sequence reproduced line for line | `test_example_sequence.py::test_sc011_worked_sequence` |

## Check ordering

The spec pins several orderings and implies others; getting them wrong silently
changes which status an operator sees. The resolved order is specified in
[research R6](./research.md#r6--ordering-of-checks-resolving-requirement-interactions)
and asserted by `test_cli_contract.py::test_r6_check_order_precedence`. The two
non-obvious points:

- **`login` checks the lock before the password** (FR-017, scenario 2.4), so a
  locked account's failure count never grows past 5.
- **`passwd` authenticates before validating the new password** (scenario 3.2:
  a wrong current password with "any new password" is status 1), whereas
  `register` validates the password before reading the store (scenario 1.6).
  This asymmetry is the spec's, not an implementation accident.

## Spec gaps flagged (not blocking)

Three items were decided during planning so that design and implementation can
proceed; each is a candidate for `/speckit-clarify` and none changes the
architecture.

1. **`register` into a full store has no status in FR-003.** A-011 caps a store
   at 10 000 accounts but the status table has no row for "cannot accept another
   account". Decided: **status 5**, because statuses 1–4 are each defined for a
   specific account-level outcome while this is a store-level refusal to write,
   and SR-006 frames the account cap as a store limit beside the file-size cap.
2. **SC-011 refers to an example sequence the recorded feature request does not
   contain.** The spec's Input field has no worked example with outputs, so
   there is nothing to reproduce "line for line". A worked sequence is supplied
   in [contracts/cli-contract.md](./contracts/cli-contract.md#worked-example-sequence)
   and `test_example_sequence.py` asserts it; if the operator has a specific
   sequence in mind, substituting it is a one-file change.
3. **`passwd` has only ~1.3× headroom against SC-007's absolute 1 s bound**,
   because two deliberate scrypt derivations (0.369 s each here) are inherent to
   it. Keeping the OWASP-minimum work factor was chosen over buying margin by
   weakening a NON-NEGOTIABLE principle; the hardware-independent
   store-scaling assertion is tested alongside the absolute one. If the absolute
   bound is binding on the target hardware, the lever is the work factor and
   that is an SR-004 decision, not an implementation detail. See
   [research R1](./research.md#r1--password-hashing-algorithm-and-parameters)
   and [R8](./research.md#r8--performance-budget-against-sc-007).

**Non-applicability already justified in the spec**: SR-003's path-containment
rule does not apply, because naming the store file is the operator's explicit
purpose in invoking the tool. The temp-file half of that rule does apply and is
enforced. Constitution Principle V requires exactly this explicit statement
rather than silence.

## Complexity Tracking

> Deviations toward added structure, each with the requirement that forces it
> (Principle IV).

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| A **package** (`src/accounts/` with `__main__.py`) rather than a single module | A-013 mandates `python -m accounts` with the package under `src/`; `-m` on a plain module cannot provide the stated invocation form | A single `accounts.py` would be the Principle IV default, but it cannot satisfy the stated invocation constraint |
| **Six modules** inside the package rather than one | The constitution's Planning-stage rule requires every security requirement to be mapped to "the module, function, or boundary that enforces it"; `cli` / `store` / `crypto` / `validation` *are* those four boundaries, and `errors` exists only to let all four raise one status-carrying error without an import cycle | One 600-line module would blur the four security boundaries the mapping has to name, and the mapping is a hard gate, not a preference. Merging `errors` into any other module creates a cycle (`store` and `cli` both raise and both import `validation`) |
| **One class** (`errors.AccountsError`) in a package that otherwise uses only functions and dicts | Principle II requires every failure to carry both a message and an exit status to the single place that writes them; an exception with two attributes is the stdlib-idiomatic carrier | Returning `(status, message)` tuples through every call site would thread error plumbing through `store` and `crypto` and invite a silently dropped status — exactly the silent-wrong-answer class Principle II calls most severe |
| A **discarded scrypt derivation** on `login` against an unknown username | SC-004 and SR-009 require a wrong password and an unknown account to be indistinguishable; without it the two differ by ~0.37 s, which enumerates accounts by stopwatch | Returning early is simpler and faster but leaves a timing oracle that defeats the requirement the fixed message exists to satisfy |
| **Catching `RecursionError`** during store parsing — an exception class normally left to propagate | SR-006 requires bounded parsing; `json`'s C scanner signals pathological nesting this way and the alternative is a traceback on stderr, which SR-009 forbids | Letting it propagate prints a traceback and exits with an undocumented status, violating FR-003 and SR-009 together. The catch is narrow (one call site), maps to status 5, and `test_security.py::test_sr006_deeply_nested_store_is_status_5` asserts the surviving behaviour, as Principle II requires |

No entry here is a weakening of Principle V; the two security-related entries
*add* a control rather than relax one.
