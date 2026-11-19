# Implementation Plan: Password reset by one-time token

**Branch**: `002-password-reset` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-password-reset/spec.md`

## Summary

Two commands are added to the shipped `accounts` tool. `reset-token USERNAME [--ttl SECONDS]`
creates a one-time password-reset token for an existing account and prints it, alone, on one
line of standard output; `reset USERNAME` reads that token and then a new password from standard
input and, if the token is valid, replaces the password, clears any lockout, and prints
`password reset`. A token is single-use, expires after its lifetime (900 seconds by default,
1–86400 by `--ttl`), is replaced by a later `reset-token`, cancelled by a successful `passwd`,
and discarded with the account by `delete`. Refusals reuse the existing vocabulary: `invalid
token` / 1, `password too short` / 2 (with the token left usable), `no such account` / 3,
`store unusable: <cause>` / 5. Every existing command keeps its behaviour, with the single
deliberate exception of the usage line, which must now list seven commands and `--ttl`.

**Technical approach**: no new module and no new runtime dependency. The token is
`secrets.token_urlsafe(32)` — 256 bits, 43 printable ASCII characters — and the store records
only its unsalted SHA-256 fingerprint, compared with `hmac.compare_digest`, so a reader of the
store can neither recover a token nor construct one that `reset` will accept. Token state is
one optional `reset_token` object (`token_hash`, `issued_at`, `ttl_seconds`) inside the account
record, which keeps the store's format marker and top-level shape untouched and makes `delete`
discard the token automatically. Spending, replacing and cancelling a token are all the same
single operation — remove or overwrite that key, in the same atomic whole-file write that
changes the password. `hashing.py` gains three short token functions beside the password pair it
already has, `store.py` gains validation of the new object (malformed token state is a corrupt
store, never an ignored field), and `cli.py` gains `--ttl` in its hand-rolled scan, two handlers,
two messages and the new usage line. The `reset` path performs exactly one password derivation,
after the token is accepted; `reset-token` performs none.

## Technical Context

**Language/Version**: Python 3.11+ (verified on 3.13.17). No compiled extensions, no code
generation step. Unchanged from 001.

**Primary Dependencies**: none at runtime — standard library only (Principle I). The feature
adds exactly one module to the 001 inventory: `time` (for `time.time()`). The rest of the token
work uses modules already imported by the package: `secrets` (`token_urlsafe`), `hashlib`
(`sha256`), `hmac` (`compare_digest`). `--ttl` is parsed by the existing hand-rolled scanner,
not `argparse` ([research.md](./research.md) D-010, D-014).

**Storage**: the same single UTF-8 JSON file at `--store PATH`, same `"accounts-store-v1"`
marker, same whole-file atomic replace at mode `0o600`. One optional key is added inside the
account record: `reset_token` = `{token_hash, issued_at, ttl_seconds}`. No migration step.
Format contract: [contracts/store-file.md](./contracts/store-file.md).

**Testing**: `pytest` (dev-only, `requirements-dev.txt`, never imported by runtime code). Bare
`pytest` from the repository root; `pytest.ini` already supplies `pythonpath = src` and
`testpaths = tests`. Five new test files; the existing suite is edited in exactly two places,
both the usage-line literal (D-019). Expiry is tested with one real `--ttl 1` sleep plus
store-level `issued_at` rewriting, so no clock seam enters runtime code (D-015).

**Target Platform**: POSIX developer and server machines (Linux, macOS), one operator running
one invocation at a time. Unchanged from 001; `os.replace` and `0o600` remain the POSIX-mode
assumptions.

**Project Type**: single-project command-line tool — one source package, one test directory.

**Performance Goals**: each new command within 1 second for a store of up to 1,000 accounts;
full suite within 60 seconds (SC-018). Measured on this machine: one PBKDF2 derivation at
600,000 iterations = 213 ms; one SHA-256 of a 43-character token = **0.5 µs**. So
`reset-token` ≈ 30 ms (interpreter start plus file I/O, no derivation) and `reset` ≈ 245 ms
(exactly one derivation, performed only after the token is accepted).

**Constraints**: the token is disclosed only on the stdout of the `reset-token` invocation that
creates it, is unrecoverable from the store, and is never transmitted or written anywhere else
(FR-034b, FR-044, SC-014); token comparison is constant-time (FR-034b); every existing command
keeps its arguments, input lines, messages, streams, statuses and store effect, apart from the
usage line and the two token-state effects invisible to output (FR-040, FR-041); a failing
`reset` leaves the store untouched and the outstanding token armed (FR-036e, FR-036f); no
inter-process locking is introduced and overlapping invocations stay out of scope (FR-038b); no
network access, no ambient configuration, no write outside the given store path (constitution:
No hidden I/O).

**Scale/Scope**: 7 commands (5 frozen, 2 new); the same 6 exit statuses, of which the new
commands use 5 and never 4; 2 new messages on top of 11 reused; 1 new optional store field with
3 sub-fields; 14 functional requirements (FR-031…FR-044 with sub-requirements, 24 identifiers
in total) and 11 success criteria (SC-010…SC-020) to cover with tests. Still no concurrency, no
account listing, no rate limiting, no token revocation command, no expiry sweep.

**Unknowns**: none. The clarification session of 2026-11-11 resolved all five open items
(unlock on reset, `passwd` cancels a token, concurrency scope, the `--ttl` ceiling, and what
`reset-token` prints), each now written into a requirement, so no `NEEDS CLARIFICATION` marker
remains in the spec or in this plan.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0 (ratified 2026-11-11). Gates derived from its four principles and
from Development Workflow item 2, which requires this plan to state explicitly: the standard
library modules used (I), which inputs are validated and how each failure is signalled (II),
the requirement-to-test mapping (III), and a justification for any abstraction beyond the
minimum (IV).

### Gate I — Standard Library Only

| Check | Status |
|---|---|
| No third-party import in any runtime module | **PASS** — the feature adds one import, `time`; `secrets`, `hashlib` and `hmac` are already present ([research.md](./research.md) D-010) |
| No runtime dependency declaration added | **PASS** — no `pyproject.toml` dependency table is introduced; `pytest.ini` carries test configuration only |
| Dev/test dependencies declared separately and not importable from runtime code | **PASS** — `requirements-dev.txt` still reads `pytest` alone; no runtime module imports it |
| Test-tooling exemption respected (narrow: `pytest` + stdlib) | **PASS** — no clock-freezing, property-testing or coverage plugin is added; the expiry tests use the store file instead (D-015) |

### Gate II — Fail Loudly

Every new input, its validation, and the signal of each failure:

| Input | Validation | Signal |
|---|---|---|
| `--ttl SECONDS` | non-empty, every character in `0`–`9`, value 1…86400, at most one occurrence, only with `reset-token`; `--ttl=N` rejected | exact usage line → stderr, exit 2, store untouched (FR-033, FR-040) |
| `reset` stdin | both lines present before end of input | `missing password input` → stderr, exit 2 (FR-036) |
| username (both commands) | present in the store | `no such account` → stderr, exit 3 (FR-036a) |
| presented token | an outstanding `reset_token` exists, its fingerprint matches in constant time, and its lifetime has not elapsed | `invalid token` → stderr, exit 1, store unchanged (FR-036a, FR-036d, FR-036e) |
| new password | ≥ 12 characters | `password too short` → stderr, exit 2, token still usable (FR-036a, FR-036f) |
| `reset_token` in a loaded store | an object with `token_hash` (64 lowercase hex), `issued_at` (finite non-bool number), `ttl_seconds` (non-bool integer 1…86400) | `store unusable: <cause>` → stderr, exit 5 (FR-039) |

| Check | Status |
|---|---|
| No plausible-but-wrong value | **PASS** — malformed token state is a corrupt store, never read as "no token" (FR-039); a corrupt store is never read as empty (inherited FR-029) |
| No silent coercion of invalid input | **PASS** — `--ttl 86401` is refused, not clamped; `--ttl 1_0` and `--ttl ²` are usage errors, which is why the digit test is an explicit character check rather than `int()` or `str.isdigit()` (D-014 records that both of those one-liners coerce wrongly) |
| No default substituted for a malformed required field | **PASS** — a `reset_token` missing a field is corruption; only an *absent* `reset_token` key means "no token", and `"reset_token": null` is corruption too |
| No bare `except`/`pass` | **PASS** — the new code catches nothing new; store-level failures remain `StoreError` with a named cause |
| Errors on stderr; a success is never stderr-only | **PASS** — `invalid token` on stderr; `password reset` and the token itself on stdout, with stderr empty on success (FR-042) |
| Failures carry a non-zero status | **PASS** — 1, 2, 3, 5; status 4 is never produced by either new command (FR-043) |
| Error text names what was wrong | **PASS** — the two new messages are specific; `store unusable: ` keeps its assertable prefix plus the specific cause, and the `--ttl` usage error reuses the one usage line the spec's Assumptions require |

One deliberate exception to "name what was wrong", recorded because it looks like a Gate II
tension: `invalid token` is identical for a wrong, never-issued, spent, cancelled and expired
token. This is required by FR-036a/FR-042 and is the same discipline FR-014 already applies to
`invalid credentials` — distinguishing them would tell an attacker which of those five states a
token is in. The failure is still loud (stderr, exit 1); only the *discrimination* is withheld.

### Gate III — Every Requirement Is Testable

| Check | Status |
|---|---|
| Every FR maps to ≥ 1 pytest test, mapping explicit in the test name or a comment | **PASS** — table below; SC-016 makes outcome coverage itself a tested criterion |
| Every Gate II error path has a test asserting both message and failure signal | **PASS** — SC-016 requires exact assertions for statuses 0,1,2,3,5 and all seven message forms on their correct streams |
| No requirement testable only in principle | **PASS** — including FR-034b/SC-014 (byte search of the store plus replaying the stored fingerprint), FR-034a/SC-015 (1,000 tokens, distinctness and alphabet), FR-036d/SC-013 (expiry in both directions via D-015), FR-038b (sequential 100× single-use, SC-012) and SC-018 (wall clock and derivation count) |
| Feature not marked complete while any FR lacks a covering test | **PASS** — enforced as a task-level gate in Phase 2 |
| The shipped suite still passes | **PASS** — SC-010; the only edits are two usage-line literals (D-019) |

Requirement-to-test mapping (files created in Phase 2; this fixes the allocation):

| Test file | Requirements covered |
|---|---|
| `tests/test_reset_contract.py` | FR-031, FR-037, FR-040, FR-042, FR-043, FR-044 |
| `tests/test_reset_token.py` | FR-032, FR-033, FR-034, FR-034a, FR-034b |
| `tests/test_reset.py` | FR-035, FR-036, FR-036a, FR-036b, FR-036c, FR-036d, FR-036e, FR-036f |
| `tests/test_token_lifecycle.py` | FR-036g, FR-038, FR-038a, FR-038b, FR-041 |
| `tests/test_store_token_state.py` | FR-039 |
| `tests/test_reset_criteria.py` | SC-010…SC-020 (the criteria not already implied above: SC-012, SC-014, SC-015, SC-016, SC-018, SC-019, SC-020) |
| *(edited)* `tests/test_cli_contract.py`, `tests/test_success_criteria.py` | usage-line literal only — FR-040, SC-010 |

Fixtures: the existing `conftest.py` is reused as it stands (`run`, `run_subprocess`,
`store_path`, `read_store`, `write_store`, `low_iterations`). One addition is expected — a
helper that issues a token and returns it — and it is a test helper, not a runtime seam.

### Gate IV — Simplicity

| Check | Status |
|---|---|
| Smallest design that satisfies the spec | **PASS** — still 4 runtime modules and one exception class; ~40 lines of new runtime code; token state is a plain dict inside the existing record dict |
| No abstraction for anticipated future needs | **PASS** — no `tokens.py`, no token repository, no clock interface, no expiry sweep, no revoke/list command, no rate limiter (D-016, D-020) |
| No new configuration surface | **PASS** — `--ttl` is a documented argument, not configuration; nothing new reads an environment variable or a file beyond `--store` |
| Fewer modules / public functions / less state where two designs fit | **PASS** — "spent" is the *absence* of a key rather than a `used` flag; three functions added to `hashing.py` rather than a fourth module (D-012, D-013, D-016) |
| Every deviation justified against a specific requirement | **PASS** — the three judgement calls are below |

Deviations requiring justification, each tied to a requirement rather than to taste:

1. **SHA-256 rather than the project's PBKDF2 for the token fingerprint.** Treating the two
   secrets differently needs justification. It is forced by SC-018, which allows `reset-token`
   zero derivations and `reset` exactly one: PBKDF2 over the token would make that two and one.
   It is *safe* because FR-034a guarantees 256 bits of CSPRNG entropy, so there is no guessable
   distribution for a slow KDF to defend ([research.md](./research.md) D-012).
2. **An extra `ttl` parameter on all seven handlers, used by one.** FR-033 puts a value in
   `argv` that only `reset-token` needs. Every alternative routing (an options object, a
   partial, a closure, a per-command parser) is an abstraction introduced to avoid passing an
   integer; one uniform signature with one unused parameter is the smaller design (D-017).
3. **Validating token state in `store.py` instead of where it is used.** FR-039 makes
   malformed token state a corrupt store — `store unusable: <cause>` / 5 for *every* command,
   including the five that never read the token — so the check has to be at load, which is
   `store.py`'s existing job. Validating lazily in `reset` would let `login` succeed against a
   store FR-039 calls corrupt.

**Initial gate result: PASS.** No violations to justify, so Complexity Tracking stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-password-reset/
├── plan.md                    # This file (/speckit-plan output)
├── spec.md                    # Feature specification (clarified 2026-11-11)
├── research.md                # Phase 0 output — decisions D-010…D-020
├── data-model.md              # Phase 1 output — reset-token entity, rules T-1…T-10, A-7…A-9
├── quickstart.md              # Phase 1 output — seven runnable validation scenarios
├── contracts/                 # Phase 1 output (deltas on the 001 contracts)
│   ├── cli.md                 #   the two commands, --ttl grammar, new usage line, messages,
│   │                          #   statuses, token lifecycle, frozen behaviour of the five
│   └── store-file.md          #   the reset_token object, validation, corruption, compatibility
├── checklists/
│   └── requirements.md        # Pre-existing specification quality checklist
└── tasks.md                   # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

Existing files, with this feature's additions marked `+`. No file is created and none is
removed.

```text
src/
└── accounts/
    ├── __init__.py            # unchanged (package marker)
    ├── __main__.py            # unchanged (the only module touching sys.*)
    ├── cli.py                 # + USAGE updated to the FR-040 string
    │                          # + MSG_PASSWORD_RESET, MSG_INVALID_TOKEN
    │                          # + PASSWORD_LINES → INPUT_LINES, with reset-token: 0, reset: 2
    │                          # + _parse_args: --ttl located by scan, strict digits, 1..86400,
    │                          #   reset-token only; returns ttl alongside the existing three
    │                          # + handler signature gains `ttl`
    │                          # + _reset_token(), _reset() handlers, registered in _HANDLERS
    │                          # + _passwd: pops reset_token on success (FR-038a) — its only change
    ├── store.py               # + _validate_record: optional reset_token object validated
    │                          #   (three fields, types, ranges); malformed ⇒ StoreError ⇒ exit 5
    └── hashing.py             # + new_token()          -> secrets.token_urlsafe(32)
                               # + token_fingerprint()  -> sha256 hex of a token
                               # + verify_token()       -> hmac.compare_digest of fingerprints

tests/
├── conftest.py                # unchanged fixtures; one token-issuing helper may be added
├── test_cli_contract.py       # EDIT: usage literal only (lines 14–17)
├── test_success_criteria.py   # EDIT: usage literal only (lines 19–22)
├── test_register.py           # unchanged
├── test_login_lockout.py      # unchanged
├── test_unlock.py             # unchanged
├── test_passwd.py             # unchanged
├── test_delete.py             # unchanged
├── test_hashing.py            # unchanged
├── test_store_file.py         # unchanged (its two usage assertions use startswith)
├── test_reset_contract.py     # NEW: invocation surface, usage line, messages, statuses, check
│                              #      order, token disclosure
├── test_reset_token.py        # NEW: issuing, --ttl grammar, entropy/alphabet, no-stdin,
│                              #      replacement, nothing recoverable from the store
├── test_reset.py              # NEW: the happy path, check order, single use, expiry, the two
│                              #      failure modes that keep the token armed
├── test_token_lifecycle.py    # NEW: the five ways a token ends and the events that leave it
│                              #      armed; passwd/delete token effects; FR-041 frozen surface
├── test_store_token_state.py  # NEW: token-state validation, corruption, round-trip,
│                              #      pre-feature store compatibility
└── test_reset_criteria.py     # NEW: SC-010…SC-020

pytest.ini                     # unchanged
requirements-dev.txt           # unchanged (pytest)
```

**Structure Decision**: the 001 single-project, flat-package layout is kept exactly, and this
feature deliberately adds **no module and no directory**. The three axes of change the package
splits on — the command-line surface (`cli.py`), persistence and format validation
(`store.py`), cryptography (`hashing.py`) — each absorb the part of this feature that belongs
to them, and the token functions sit beside the password functions they mirror so that every
constant-time comparison in the project is in one file. A `tokens.py` would have held three
short functions needing exactly the imports `hashing.py` already has, splitting one axis in two
for no requirement ([research.md](./research.md) D-016). The test directory grows by five
files because Principle III wants the requirement-to-test mapping legible, not because the
source needs mirroring.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 against the artifacts actually produced.

| Gate | Result | Evidence from the design |
|---|---|---|
| I — Standard Library Only | **PASS** | The inventory in [research.md](./research.md) D-010 is complete and entirely stdlib — one new import, `time`; the file tree adds no runtime dependency declaration and no new dev dependency, and D-015 shows how the expiry requirement is tested without a clock-faking package |
| II — Fail Loudly | **PASS** | [contracts/cli.md](./contracts/cli.md) enumerates every outcome of both commands as an exact message on the right stream with a non-zero status; [contracts/store-file.md](./contracts/store-file.md) adds five corruption conditions for token state, all exit 5, none degrading to "no token"; the `--ttl` table in D-014 shows the two coercion traps (`int("1_0")`, `"²".isdigit()`) being rejected rather than silently accepted |
| III — Every Requirement Is Testable | **PASS** | The mapping table above assigns all 24 FR identifiers to named files; the CLI contract reproduces the message/status inventory (SC-016) and the token lifecycle (SC-020) as directly assertable tables; D-015 makes SC-013 testable in milliseconds and D-012's measurement shows the SC-018 budget is met with room |
| IV — Simplicity | **PASS** | The design ended with no new module, no new class, no clock seam, and "spent" represented as the absence of a key; the three judgement calls each carry a requirement-based justification; D-020 records the seven things deliberately left out, so each absence is a decision |

Five design consequences worth flagging to the user, since none is stated in the spec and each
should be asserted deliberately in Phase 2 rather than discovered:

1. **"Mark the token used" (FR-036b) is implemented as removing it.** No record of a spent
   token is kept. Every observable clause of FR-036b and FR-036c holds, and nothing in the spec
   asks for token history; if an audit trail is ever wanted, that is a new requirement, not a
   gap in this one (D-013).
2. **An expired token's record stays on disk until the account is next written.** Expiry needs
   no write, and the tool performs no sweep: "expired" and "absent" are indistinguishable to a
   user, which is all FR-036d requires. The alternative would make a read-only command write.
3. **A corrupt store outranks everything**, so `reset` against an unreadable store exits 5 even
   for a username that does not exist, and malformed token state makes *all seven* commands
   exit 5 — including `login`, which never reads a token. Both follow from FR-037 and FR-039
   read together, and are the same precedence the 001 plan flagged for `register`.
4. **`--ttl` is rejected, not ignored, on the other six commands** (FR-033), so
   `passwd alice --ttl 900` is a usage error. This is a *new* way for an existing command to
   fail, but it was already a usage error before this feature (an unknown flag), so FR-041 is
   untouched — the status and the stream are the same and only the usage text changed.
5. **The 43-character token length is a design choice, not a requirement.** FR-034a and SC-015
   set floors (128 bits, 22 characters); `token_urlsafe(32)` gives 256 bits and 43 characters.
   Tests should assert the floors, and the exact alphabet, rather than pinning 43 — so the
   margin can be raised later without a contract change (D-011).

**Post-design gate result: PASS.** No new violations; Complexity Tracking remains empty.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No violations. Both the initial and the post-design Constitution Checks pass. The three
judgement calls that could be read as added complexity — a second, faster transformation for the
token (SC-018, FR-034a), an unused `ttl` parameter on five handlers (FR-033), and token-state
validation at load rather than at use (FR-039) — are each justified above against the specific
requirement that forces them, and the alternatives are recorded with their rejection reasons in
[research.md](./research.md) D-012, D-017 and D-016.
