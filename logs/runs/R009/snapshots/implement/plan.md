# Implementation Plan: Local Account Manager CLI

**Branch**: `001-accounts-cli` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-accounts-cli/spec.md`

## Summary

A command-line tool that manages local user accounts in a single JSON store file, invoked as
`python -m accounts --store PATH COMMAND USERNAME` with five commands (`register`, `login`,
`unlock`, `passwd`, `delete`). Passwords are never command-line arguments: each command reads
the lines it needs from standard input. Five consecutive failed logins lock an account until
`unlock` is run. Every outcome is reported as one exact message on the correct stream with one
of six documented exit statuses (0–5).

**Technical approach**: a four-module standard-library-only package under `src/accounts/` —
`__main__.py` (the only module touching `sys.*`), `cli.py` (argument parsing, input reading,
command dispatch, message/status mapping), `store.py` (load, validate, atomic owner-only
write), `hashing.py` (PBKDF2-HMAC-SHA256 derivation and constant-time verification). Account
records are plain validated dicts; there is no model or service layer. Passwords are protected
with PBKDF2-HMAC-SHA256 at 600,000 iterations over a 16-byte per-account salt, with each
record carrying its own derivation parameters so verification never depends on the current
default. `cli.main()` takes `argv` and the three streams as parameters and returns the exit
status, which lets the suite exercise the full command path in-process and stay inside the
60-second budget of SC-009 while the documented `python -m accounts` interface is still
asserted end to end through real subprocesses.

## Technical Context

**Language/Version**: Python 3.11+ (verified on 3.13.17). No compiled extensions, no code
generation step.

**Primary Dependencies**: None at runtime — standard library only (Principle I). Modules used:
`hashlib`, `hmac`, `secrets`, `base64`, `json`, `os`, `tempfile`, `pathlib`, `sys`, `io`.
Argument parsing is hand-rolled rather than using `argparse`, to produce the single exact usage
line FR-006 requires (see [research.md](./research.md) D-002).

**Storage**: a single UTF-8 JSON file at the operator-supplied `--store PATH`. Read whole,
rewritten whole and atomically (temp file in the same directory → flush → fsync → rename), mode
`0o600`. Format contract: [contracts/store-file.md](./contracts/store-file.md).

**Testing**: `pytest` (dev-only dependency, declared in `requirements-dev.txt`, never imported
by runtime code). Bare `pytest` from the repository root; `pytest.ini` provides
`pythonpath = src` and `testpaths = tests`.

**Target Platform**: POSIX developer and server machines (Linux, macOS) with a single operator
running one invocation at a time. `os.replace` and `0o600` are POSIX-mode assumptions.

**Project Type**: single-project command-line tool — one source package, one test directory.

**Performance Goals**: one command within 1 second for a store of up to 1,000 accounts; full
suite within 60 seconds (SC-009). Measured: one derivation = 213 ms, interpreter startup +
stdlib imports = ~30 ms, so `register`/`login`/`delete` ≈ 245 ms and `passwd` ≈ 460 ms.

**Constraints**: passwords never appear as arguments or in the store in recoverable form
(FR-003, FR-026, SC-005, SC-007); at most one derivation per command, two for `passwd`
(SC-009); every failing command leaves the store unchanged apart from the `login` failed-tally
increment (FR-028); exactly one assertable message per outcome (FR-027, SC-002); no network
access, no ambient configuration, no writes outside the given path (constitution: No hidden
I/O).

**Scale/Scope**: up to ~1,000 accounts in one store; 5 commands; 6 exit statuses; 11 pinned
messages; 30 functional requirements (FR-001–FR-030 with sub-requirements) and 9 success
criteria to cover with tests. No concurrency, no account listing, no password recovery, no lock
expiry.

**Unknowns**: none. The clarification session of 2026-11-11 resolved the four open items
(derivation function and cost, store format, error-text discipline, performance budget), so no
`NEEDS CLARIFICATION` marker remains.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0 (ratified 2026-11-11). Gates derived from its four principles and
the Development Workflow requirement that "the plan MUST state, explicitly: which standard
library modules it uses, which inputs are validated and how each failure is signalled, the
requirement-to-test mapping, and a justification for any abstraction beyond the minimum".

### Gate I — Standard Library Only

| Check | Status |
|---|---|
| No third-party import in any runtime module | **PASS** — modules listed under Technical Context are all stdlib ([research.md](./research.md) D-001) |
| No runtime dependency declaration (`install_requires`, `dependencies`, runtime `requirements.txt`) | **PASS** — no `pyproject.toml` dependency table is introduced; `pytest.ini` carries only test configuration |
| Dev/test dependencies declared separately and not importable from runtime code | **PASS** — `pytest` only, in `requirements-dev.txt`; no runtime module imports it |
| Test-tooling exemption respected (narrow: `pytest` + stdlib) | **PASS** — no other dev dependency; no coverage, factory or property-testing plugin |

### Gate II — Fail Loudly

Every input validated, and every failure's signal, named explicitly:

| Input | Validation | Signal |
|---|---|---|
| `argv` | `--store` present with a value; exactly two positionals; command word in the known set | exact usage line → stderr, exit 2 (FR-006) |
| store path | readable, writable, is a file (a missing file is the empty store, not an error) | `store unusable: <cause>` → stderr, exit 5 (FR-029) |
| store content | UTF-8; JSON object; `format == "accounts-store-v1"`; `accounts` an object; every record an object with all six fields at the right JSON type, valid base64 of the right length, `algorithm` recognized | `store unusable: <cause>` → stderr, exit 5 (FR-029a) |
| stdin lines | the exact count each command needs is available before EOF | `missing password input` → stderr, exit 2 (FR-005) |
| username (register) | 3–32 chars of `[A-Za-z0-9_]` | `invalid username` → stderr, exit 2 (FR-010) |
| password | ≥ 12 characters | `password too short` → stderr, exit 2 (FR-010, FR-021) |
| username existence | present / absent as the command requires | `username already exists` or `no such account` → stderr, exit 3 (FR-011, FR-018, FR-022, FR-025) |
| lock state | `locked` checked before the password on `login` | `account locked` → stderr, exit 4 (FR-016) |
| password correctness | constant-time compare of the derived key | `invalid credentials` → stderr, exit 1 (FR-013, FR-014, FR-020, FR-024) |

| Check | Status |
|---|---|
| No plausible-but-wrong value: a corrupt store is never read as an empty store | **PASS** — FR-029, S-5, enforced at load |
| No silent coercion, no default substituted for a malformed required field | **PASS** — every record field validated at load; wrong type is corruption |
| No bare `except: pass`; every caught exception becomes a named cause | **PASS** — `OSError`, `UnicodeDecodeError`, `json.JSONDecodeError` → `StoreError` with the cause in the message ([research.md](./research.md) D-006) |
| Errors on stderr; success messages never only on stderr | **PASS** — FR-027; successes write to stdout or nothing, and never to stderr |
| Failures carry a non-zero exit status | **PASS** — FR-030, statuses 1–5 |
| Error text names what was wrong | **PASS** — the fixed messages are specific; `store unusable: ` carries the specific cause after the assertable prefix, which is the compromise FR-029 spells out |

### Gate III — Every Requirement Is Testable

| Check | Status |
|---|---|
| Every FR maps to ≥ 1 pytest test, with the mapping explicit in the test name or a comment | **PASS** — mapping table below; SC-001 makes it a tested criterion |
| Every error path from Gate II has a test asserting both message content and failure signal | **PASS** — SC-002 requires equality assertions for all 11 messages and all 6 statuses |
| No requirement that cannot be expressed as an automated test | **PASS** — including SC-005 (byte search of the store), SC-007 (argument surface) and SC-009 (wall clock and derivation count) |
| Feature not marked complete while any FR lacks a covering test | **PASS** — enforced as a task-level gate in Phase 2 |

Requirement-to-test mapping (test files are created in Phase 2; this fixes the allocation):

| Test file | Requirements covered |
|---|---|
| `tests/test_cli_contract.py` | FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-030; SC-007 |
| `tests/test_register.py` | FR-007, FR-008, FR-009, FR-010, FR-011 |
| `tests/test_login_lockout.py` | FR-012, FR-013, FR-014, FR-015, FR-016; SC-006 |
| `tests/test_unlock.py` | FR-017, FR-018 |
| `tests/test_passwd.py` | FR-019, FR-020, FR-021, FR-022 |
| `tests/test_delete.py` | FR-023, FR-024, FR-025 |
| `tests/test_hashing.py` | FR-026, FR-026a, FR-026b, FR-026c |
| `tests/test_store_file.py` | FR-027, FR-028, FR-029, FR-029a, FR-029b, FR-029c |
| `tests/test_success_criteria.py` | SC-001…SC-009 (the criteria not already covered above: SC-002 message/status inventory, SC-003, SC-004, SC-005, SC-008, SC-009) |

### Gate IV — Simplicity

| Check | Status |
|---|---|
| Smallest design that satisfies the spec | **PASS** — 4 runtime modules, no classes except one `StoreError` exception, account records as plain dicts |
| No abstraction for anticipated future needs | **PASS** — no store backend interface, no command registry/plugin hook, no config layer, no logging |
| No configuration option beyond the documented arguments | **PASS** — `DEFAULT_ITERATIONS` is a module constant, not configuration; nothing reads env vars or config files |
| Fewer modules / public functions / less state where two designs both fit | **PASS** — the `models/` + `services/` + `cli/` + `lib/` layout the template offers by default is rejected; see Structure Decision |
| Every deviation justified against a specific requirement | **PASS** — the three judgement calls are recorded below |

Deviations requiring justification, each tied to a requirement rather than to taste:

1. **A separate `hashing.py` instead of folding derivation into `store.py`.** FR-026a/b/c are a
   cohesive, independently testable unit (algorithm, cost, salt source, constant-time compare)
   and the suite must patch `DEFAULT_ITERATIONS` at a single named location for the SC-009
   budget. Three functional modules is one more than the minimum of two, and this is the
   requirement that forces it.
2. **Hand-rolled argument parsing instead of `argparse`.** Justified by FR-006, which pins one
   exact usage string; matching it through `argparse` needs more code than writing the parser.
   The smaller design here is the one without the library ([research.md](./research.md) D-002).
3. **`cli.main(argv, stdin, stdout, stderr) -> int` rather than reading `sys.*` directly.**
   Justified by SC-009's 60-second suite budget: at 213 ms per derivation, a suite of
   full-cost subprocesses cannot meet it. Parameterised streams add no abstraction layer — no
   interface, no indirection — and `__main__.py` remains a three-line adapter.

**Initial gate result: PASS.** No violations to justify, so Complexity Tracking stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-accounts-cli/
├── plan.md                    # This file (/speckit-plan output)
├── spec.md                    # Feature specification (clarified 2026-11-11)
├── research.md                # Phase 0 output — decisions D-001…D-009
├── data-model.md              # Phase 1 output — entities, rules, state transitions
├── quickstart.md              # Phase 1 output — runnable validation scenarios
├── contracts/                 # Phase 1 output
│   ├── cli.md                 #   command-line contract: args, stdin, messages, statuses
│   └── store-file.md          #   on-disk store format and write protocol
├── checklists/
│   └── requirements.md        # Pre-existing specification quality checklist
└── tasks.md                   # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── accounts/
    ├── __init__.py            # package marker; no logic
    ├── __main__.py            # `python -m accounts`: the only module touching sys.*;
    │                          # wraps sys.stdin.buffer as UTF-8, calls sys.exit(cli.main(...))
    ├── cli.py                 # main(argv, stdin, stdout, stderr) -> int; argument parsing,
    │                          # stdin reading, the five command functions, messages, statuses
    ├── store.py               # load() / save(); format + record validation; StoreError;
    │                          # atomic same-directory replace at mode 0o600
    └── hashing.py             # DEFAULT_ITERATIONS, new_password_material(), verify()

tests/
├── conftest.py                # store-path fixture, in-process runner, subprocess runner,
│                              # low-iteration fixture for bulk tests
├── test_cli_contract.py       # invocation, stdin protocol, usage errors, status inventory
├── test_register.py
├── test_login_lockout.py
├── test_unlock.py
├── test_passwd.py
├── test_delete.py
├── test_hashing.py
├── test_store_file.py
└── test_success_criteria.py

pytest.ini                     # pythonpath = src ; testpaths = tests
requirements-dev.txt           # pytest  (dev-only; no runtime dependency file exists)
```

**Structure Decision**: single project, flat package. The template's default
`src/{models,services,cli,lib}/` split is rejected under Principle IV: there is one entity with
seven fields and five commands, so a `models/` package would hold a dict shape that `store.py`
already validates and a `services/` package would hold the five functions `cli.py` already has.
The chosen split is along the three genuine axes of change — the command-line surface
(`cli.py`), persistence (`store.py`), and cryptography (`hashing.py`) — each matching a distinct
cluster of requirements (FR-001…FR-025, FR-029*, FR-026*). `src/` as the package root is
required by the spec's environment assumption so that `python -m accounts` works with `src/` on
`PYTHONPATH`; `tests/` is separate per the constitution's Project Layout constraint, and
`pytest.ini` keeps a bare `pytest` working from the root with no environment setup.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 against the artifacts actually produced.

| Gate | Result | Evidence from the design |
|---|---|---|
| I — Standard Library Only | **PASS** | The module inventory in [research.md](./research.md) D-001 is complete and entirely stdlib; the file tree adds no runtime dependency declaration; `pytest` appears only in `requirements-dev.txt` and is imported only by `tests/` |
| II — Fail Loudly | **PASS** | [contracts/cli.md](./contracts/cli.md) enumerates every outcome as an exact message on stderr with a non-zero status; [contracts/store-file.md](./contracts/store-file.md) lists eleven corruption conditions, all exit 5, none degrading to an empty store; the check order in D-004 puts store usability ahead of input validation so a corrupt store can never be masked by an input error |
| III — Every Requirement Is Testable | **PASS** | Mapping table above assigns all 30 FRs to named test files; SC-002's full message-and-status inventory is reproduced as a table in the CLI contract so each row is directly assertable; the SC-009 budget is shown to be achievable in D-008, so no criterion is testable only in principle |
| IV — Simplicity | **PASS** | Design ended at 4 runtime modules and one exception class; no entity classes, no layers, no configuration surface; the three judgement calls each carry a requirement-based justification; D-009 records what was deliberately left out (timing equalization, locking, logging, models/services layers) so the absences are decisions |

One design consequence worth flagging to the user, since it is not stated in the spec: by
Gate II's check order, `register` with an invalid username against a *corrupt* store exits **5**,
not 2. The spec fixes precedence within a command but not between store usability and input
validation; D-004 chose store-first because reporting `invalid username` while the store is
unreadable would imply the store was fine. It is recorded as a decision so Phase 2 asserts it
deliberately rather than discovering it as an accident.

**Post-design gate result: PASS.** No new violations; Complexity Tracking remains empty.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

No violations. Both the initial and post-design Constitution Checks pass, and the three
judgement calls that could have been read as added complexity (a third functional module,
hand-rolled parsing, parameterised streams) are each justified above against the specific
requirement that forces them — FR-026a/b/c and SC-009, FR-006, and SC-009 respectively — rather
than left as unexplained design freedom.
