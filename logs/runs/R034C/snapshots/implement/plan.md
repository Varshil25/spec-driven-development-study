# Implementation Plan: Administrator-Issued Password Reset

**Branch**: `002-password-reset` | **Date**: 2026-11-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-password-reset/spec.md`

## Summary

Add two commands to the existing `accounts` CLI — `reset-token USERNAME [--ttl SECONDS]`, which
prints a one-time reset token, and `reset USERNAME`, which consumes that token plus a new
password from standard input — while leaving the five existing commands observably unchanged
(FR-060).

Technical approach: no new source module and no new runtime dependency. A token is
`secrets.token_urlsafe(32)` (256 bits, single-line-safe alphabet). It is stored only as a
PBKDF2-HMAC-SHA256 verifier under a fresh per-token salt — the same transformation already
applied to passwords — alongside an absolute `expires_at` epoch timestamp, in a new **optional**
`reset_token` key on the account record. The store `version` stays `1`, so a file written before
this feature loads unchanged and reads as "no outstanding token" (FR-059). `--ttl` joins the
existing flat `argparse` parser as a suppressed option scoped to `reset-token` by an explicit
check, which is the only arrangement that adds the option without changing any existing
command's accepted argument forms or `--help` output (research.md R-13).

## Technical Context

**Language/Version**: Python 3.11+ (`requires-python = ">=3.11"` in `pyproject.toml`, the single
place the minimum is stated; developed and measured against CPython 3.13.17)

**Primary Dependencies**: None. Standard library only (Constitution Principle I). This feature
adds `secrets.token_urlsafe`, `time.time`, and `math.isfinite` to the modules already in use
(`argparse`, `json`, `hashlib`, `hmac`, `base64`, `re`, `tempfile`, `os`, `pathlib`,
`dataclasses`, `contextlib`). `pytest` remains the only development dependency.

**Storage**: The same single JSON store file at `--store PATH`, format `version: 1` unchanged.
Each account record gains one optional key, `reset_token`, holding `{salt, verifier,
expires_at}`. Absence of the key is the normal case and the only representation of "no
outstanding token" (data-model.md).

**Testing**: `pytest`, run bare from the repository root (`pythonpath = ["src"]` is already
configured). New tests drive the in-process seam `cli.main(argv, stdin, stdout, stderr) -> int`
with `io.StringIO` streams, reusing the existing `run_cli`, `store_path`, and `read_store`
fixtures in `tests/conftest.py` unchanged.

**Target Platform**: POSIX-like local shell (Linux). Single process, no network. Atomicity of
saves relies on `os.replace` within one filesystem, as already established (001 research.md R-05).

**Project Type**: Single-project command-line tool.

**Performance Goals**: Each new command completes in under 1 second on a 1,000-account store
(SC-016, matching SC-007). Measured budget: one PBKDF2 derivation at 600,000 iterations costs
**0.150 s** on the development machine, so `reset-token` spends ~0.15 s (one derivation for the
token verifier) and `reset` ~0.30 s (verify the token, then derive the new password verifier),
plus a JSON load and atomic rewrite of a ~200 KB file. Roughly 3× margin against the budget.

**Constraints**:

- The five existing commands must show no observable change: same arguments, same stdin
  protocol, same output text, same exit statuses, same store effects (FR-060).
- No new exit status; only 0, 1, 2, 3 are used by the new commands, and never 4 (FR-061).
- No token may be recoverable from the store's bytes, and no token may appear in any diagnostic
  (FR-057, FR-058, SC-014).
- Pre-feature store files must load without complaint; unrecognized store contents must still be
  rejected rather than defaulted (FR-059).
- Results on stdout, diagnostics on stderr, one line each (FR-062).

**Scale/Scope**: ~1,000 accounts per store; 7 commands after this change; 24 new functional
requirements (FR-039 – FR-062) and 9 new success criteria (SC-009 – SC-017). Four source files
touched, no file added; six test files added, one existing test file extended (research.md R-17).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v1.0.0.

| Gate | Verdict | Evidence |
|---|---|---|
| **I. Standard Library Only** — no third-party runtime import; `dependencies` stays empty | **PASS** | Token generation is `secrets.token_urlsafe`, hashing is `hashlib.pbkdf2_hmac`, comparison is `hmac.compare_digest`, the clock is `time.time`, number validation is `math.isfinite`. `pyproject.toml`'s `dependencies = []` is untouched; `pytest` stays under `optional-dependencies.dev`. |
| **II. Fail Loudly** — every invalid input and unmet precondition produces a specific diagnostic and a non-zero status; no defaulting, no coercion, no bare `except` | **PASS** | Every new failure path has a named message and status: E14 missing token line (2), E15 `invalid token` (1), E16 `--ttl` out of scope (2), E17 `--ttl` not a positive whole number (2), plus the reused E1/E4/E9. A `reset_token` that is malformed, carries an unknown key, or has a non-finite `expires_at` raises `StoreError` rather than being ignored or treated as "no token" (data-model.md rules 8–11). `--ttl` is validated by a strict decimal-digit test instead of `int()`, which would silently coerce `1_000`, `+5`, `" 10 "`, and `"١٢٣"` (research.md R-14). No new `except` clause is introduced. |
| **III. Every Requirement Is Testable** — each FR maps to a discoverable `pytest` test; error paths tested for message *and* status | **PASS** | FR-039 – FR-062 each map to at least one named test (table below). `tests/test_requirement_coverage.py` is extended to assert the mapping in both directions across the union FR-001 – FR-062, so a lost mapping fails the suite (research.md R-17). Every error path is asserted on exact stderr text and exact status. |
| **IV. Simplicity** — smallest design; no abstraction for a single caller; no unneeded option or seam | **PASS** (one justified item, see Complexity Tracking) | No new module, no new class, no new `Result` field. The token reuses `passwords.derive`/`verify` rather than introducing a second one-way transformation. The store gains one optional key, not a version bump with two accepted versions. `--ttl` is scoped by one `if`, not by restructuring the parser into subparsers. The single added parameter — an injected `now: float` — is justified below. |

Gate result: **no unjustified violation. Proceed to Phase 0.**

### Requirement → test mapping

| Requirement | Test file | Focus |
|---|---|---|
| FR-039, FR-040, FR-041, FR-046, FR-047 | `tests/test_reset_token.py` | Issuing: one-line stdout, entropy/alphabet/uniqueness, validity window, no change to password/count/lock, locked accounts |
| FR-042, FR-043 | `tests/test_reset_token.py`, `tests/test_preserved_behaviour.py` | `--ttl` value validation; `--ttl` rejected on every other command |
| FR-044, FR-045 | `tests/test_reset_token.py` | Supersession; unknown account exits 3 with nothing on stdout |
| FR-048 – FR-051, FR-053 | `tests/test_reset.py` | Stdin protocol, success path, old password stops working, single use, short password keeps the token |
| FR-052 | `tests/test_reset.py` | All five rejection cases produce byte-identical `invalid token` + status 1 |
| FR-054, FR-055, FR-056 | `tests/test_reset.py` | Existence check before any read; end-of-input diagnostics; lock and counter untouched |
| FR-057, FR-058 | `tests/test_reset_secrets.py` | Token absent from store bytes; token absent from every stream but the one stdout line |
| FR-059 | `tests/test_store_compatibility.py` | Pre-feature store loads and behaves as "no token"; malformed `reset_token` still rejected |
| FR-060, FR-061, FR-062 | `tests/test_preserved_behaviour.py` | Existing commands byte-identical; statuses confined to 0–3; stream discipline |
| SC-009 | `tests/test_requirement_coverage.py` | 24 of 24 new requirements mapped, checked both directions |
| SC-010, SC-012 | `tests/test_reset_end_to_end.py` | The four worked examples; the two-command recovery journey |
| SC-016 | `tests/test_reset_performance.py` | Both new commands under 1 s on 1,000 accounts |

## Project Structure

### Documentation (this feature)

```text
specs/002-password-reset/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── cli-contract.md  # Phase 1 output — delta over the 001 contract
├── checklists/
│   └── requirements.md  # Existing (/speckit-checklist output)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/accounts/
├── __init__.py          # unchanged
├── __main__.py          # unchanged
├── cli.py               # MODIFIED: two command names, the --ttl option and its scope check,
│                        #   the reset stdin pre-pass, the injected clock
├── commands.py          # MODIFIED: reset_token() and reset(), the new diagnostics
├── passwords.py         # MODIFIED: new_token(); docstring widened to cover token generation
└── store.py             # MODIFIED: optional reset_token key and its validation rules

tests/
├── conftest.py                     # unchanged (run_cli / store_path / read_store reused)
├── test_cli_usage.py               # unchanged
├── test_delete.py                  # unchanged
├── test_end_to_end.py              # unchanged
├── test_lockout.py                 # unchanged
├── test_login.py                   # unchanged
├── test_passwd.py                  # unchanged
├── test_passwords.py               # unchanged
├── test_performance.py             # unchanged
├── test_register.py                # unchanged
├── test_store.py                   # unchanged
├── test_requirement_coverage.py    # MODIFIED: ledger spans FR-001 - FR-062 (research.md R-17)
├── test_reset_token.py             # NEW: FR-039 - FR-047
├── test_reset.py                   # NEW: FR-048 - FR-056
├── test_reset_secrets.py           # NEW: FR-057, FR-058, SC-014
├── test_store_compatibility.py     # NEW: FR-059
├── test_preserved_behaviour.py     # NEW: FR-060 - FR-062, SC-011
├── test_reset_end_to_end.py        # NEW: SC-010, SC-012, SC-013, SC-015
└── test_reset_performance.py       # NEW: SC-016

pyproject.toml           # unchanged (dependencies stays empty, requires-python stays >=3.11)
```

**Structure Decision**: The existing single-project layout is kept exactly as feature 001
established it — `src/accounts/` with four modules and a flat `tests/` directory. No module is
added. The two new commands are operations on the same store with the same shape as the five
existing ones, so they belong in `commands.py` beside them; token generation joins `passwords.py`
so that every use of `secrets` and `hashlib` stays in one auditable module. Creating a
`tokens.py` for one `token_urlsafe` call and one record-building helper would be an abstraction
with a single caller (Principle IV). Test files are split by requirement group rather than added
to existing files, so that "the existing suite passes unmodified" (SC-011) is verifiable by
`git diff --stat tests/` rather than by reading diffs.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| An injected clock: `commands.reset_token(..., now)` and `commands.reset(..., now)` take the current time as a parameter instead of calling `time.time()` themselves | FR-041 makes expiry observable behaviour and Principle III requires it to be covered by a test that fails when the rule is unmet. A parameter makes the boundary (`now < expires_at`, and the instant of equality) assertable exactly and instantly. The precedent is already in the codebase: `cli.main` takes its three streams as parameters for the same reason (001 research.md R-08). It is not a user-facing option — `cli` is the only caller and always passes `time.time()`. | Calling `time.time()` inside the commands forces expiry tests to `sleep` through real `--ttl` windows. That buys a slower suite and can only test "well after expiry", never the boundary or the instant before it, so FR-041's "and MUST NOT be valid thereafter" would rest on a 1-second sleep rather than an exact assertion. |
| `--ttl` is registered with `help=argparse.SUPPRESS`, so it does not appear in `python -m accounts --help` | `tests/test_fr003_the_parser_exposes_only_the_store_option` asserts that the set of `--`-prefixed tokens anywhere in `--help` output is exactly `{--store, --help}`. FR-060 and SC-011 require that test to pass **unmodified**. Suppression is the only way to add the option FR-039 mandates while keeping that assertion true, and it costs no behaviour: `--ttl` works exactly as specified, and is documented in `contracts/cli-contract.md`. | (a) Registering `--ttl` with visible help text breaks that FR-003 test, which is a direct SC-011 violation. (b) `argparse` subparsers would scope `--ttl` structurally and keep top-level help clean, but they change *more* observable surface for the five existing commands — the usage text they print on a usage error becomes the subparser's, and `--store` would no longer be accepted after the command name (`python -m accounts login alice --store S` works today) — which FR-060 forbids. See research.md R-13 for the full comparison. |

**Flagged for the project owner** (not a blocker, no code depends on the answer): the suppressed
option is a consequence of FR-003's test asserting *no other option exists* rather than its actual
requirement, that *no option accepts a password*. If visible help for `--ttl` is preferred over
SC-011's letter, the sanctioned change is the one assertion on line 112 of
`tests/test_cli_usage.py` (`{"--store", "--help"}` → `{"--store", "--help", "--ttl"}`) and
dropping `SUPPRESS`. This plan takes the spec at its word and does not modify that file.

## Post-Design Constitution Re-Check

Re-evaluated after data-model.md, contracts/cli-contract.md, and quickstart.md were written.

| Gate | Verdict | What the design added, and why it still holds |
|---|---|---|
| I. Standard Library Only | **PASS** | The design introduced no dependency. `math.isfinite` (store validation) and `time.time` (the clock) are the only additional stdlib names beyond Phase 0. |
| II. Fail Loudly | **PASS** | Phase 1 added four failure modes to the contract (E14–E17) and four load-time validation rules (8–11), each with a specific message. Two "fail closed, silently" traps were found and closed explicitly: `expires_at: NaN` (which JSON accepts and which would make every comparison false) and `reset_token: null` (which would read as "no token"). Both raise `StoreError` naming the field. |
| III. Every Requirement Is Testable | **PASS** | The mapping table above covers FR-039 – FR-062 with no gap, and the ledger test enforces it in both directions. Each contract row (E14–E17, both success rows) names the status and the exact stderr/stdout text an assertion can use. |
| IV. Simplicity | **PASS** | Phase 1 removed candidates rather than adding them: no `version: 2`, no second accepted store version, no `issued_at` field beside `expires_at`, no token-registry for uniqueness, no cleanup write on the expired-token path, no new `Result` field, no new module. The two justified items above are unchanged in number and scope. |

Design is consistent with the spec and the constitution. Ready for `/speckit-tasks`.
