# Implementation Plan: Local Account Manager

**Branch**: `001-local-account-manager` | **Date**: 2026-11-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-local-account-manager/spec.md`

## Summary

A single-process command-line tool, `python -m accounts --store PATH COMMAND USERNAME`, that
manages local accounts (`register`, `login`, `unlock`, `passwd`, `delete`) in one JSON store
file. Passwords arrive only on standard input, one line per password, and are stored only as
PBKDF2-HMAC-SHA256 verifiers with a per-account random salt. Results go to stdout, diagnostics
to stderr, and the process exits 0/1/2/3/4 per FR-005.

Technical approach: a thin `__main__` entry point over a `cli` module that parses arguments
with `argparse`, reads the passwords a command needs from a stream, and dispatches to one of
five command functions. Each command function takes the in-memory store and returns a
`Result(code, out, err)`; `cli` prints and exits. Store load/save is a separate module that
reads JSON strictly (malformed → diagnostic, never silently treated as empty) and writes via
`tempfile` + `os.replace` so a partial write cannot truncate the store. Everything is Python
3.11+ standard library; `pytest` is the only development dependency.

## Technical Context

**Language/Version**: Python 3.11+ (declared once in `pyproject.toml` as
`requires-python = ">=3.11"`; local interpreter is 3.13.17)

**Primary Dependencies**: None at runtime — standard library only (`argparse`, `json`,
`hashlib`, `hmac`, `secrets`, `base64`, `os`, `sys`, `tempfile`, `pathlib`, `dataclasses`).
`pytest` is a development-only dependency.

**Storage**: One JSON file at the operator-supplied `--store PATH`; created with mode `0600` on
first successful account write; replaced atomically on every change. Schema in
[data-model.md](./data-model.md).

**Testing**: `pytest`, runnable as a bare `pytest` from the repository root. `src/` is put on
the import path by `[tool.pytest.ini_options] pythonpath = ["src"]` so no environment setup is
needed. In-process tests call `cli.main(argv, stdin, stdout, stderr) -> int`; a smaller set of
end-to-end tests invoke `python -m accounts` as a subprocess with `PYTHONPATH=src`.

**Target Platform**: Any POSIX host with CPython 3.11+ (developed and verified on Linux).

**Project Type**: Single-project CLI tool with one importable package (`accounts`).

**Performance Goals**: Every command completes in well under 1 second on a store of 1,000
accounts (SC-007). Budget: one PBKDF2 derivation at 600,000 iterations ≈ 145 ms measured on
this host, plus JSON load and atomic rewrite of a ~200 KB store (single-digit ms).

**Constraints**: No password may appear in `argv`, in the store file's bytes, or in any
diagnostic (FR-003, FR-037, SC-006). A non-zero exit must leave account data unchanged, except
that a failed login persists its incremented failure count and any resulting lock (FR-006).
Only the four non-zero statuses 1–4 may be used (FR-005). Owner-only permissions on a
newly created store (FR-038).

**Scale/Scope**: 5 commands, 38 functional requirements, 1,000-account stores, single-process
use only (no concurrency, locking, or merge behaviour — per the spec's assumption).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Gates derived from `.specify/memory/constitution.md` v1.0.0.

| Gate | Source | Pre-Phase 0 | Post-Phase 1 | Evidence |
|------|--------|-------------|--------------|----------|
| No third-party runtime import | I. Standard Library Only | PASS | PASS | Runtime module list in Technical Context is stdlib-only; `pyproject.toml` `dependencies = []`; `pytest` declared separately under a dev extra |
| Minimum Python version stated once, in project metadata | Additional Constraints | PASS | PASS | `requires-python = ">=3.11"` in `pyproject.toml`; no other file restates it |
| Every failure mode has a specific diagnostic + non-zero exit | II. Fail Loudly | PASS | PASS | Every row of the error table in [contracts/cli-contract.md](./contracts/cli-contract.md) names the rule that failed and a non-zero status; SC-008 asserts no silent failure |
| No silent coercion of invalid input | II. Fail Loudly | PASS | PASS | Missing stdin line is an error, never an empty password (FR-018); a malformed store is an error, never an empty store (FR-007) — both decided in [research.md](./research.md) |
| No bare `except:` / `except Exception: pass` | II. Fail Loudly | PASS | PASS | Only `OSError`, `json.JSONDecodeError`, and the module's own `StoreError` are caught, each re-raised as a `StoreError` carrying the file path |
| Diagnostics to stderr, results to stdout, not interleaved | Additional Constraints | PASS | PASS | Command functions return `Result(code, out, err)` with separate fields; `cli` is the only writer and writes each field to its own stream |
| Every functional requirement maps to a failing-without-the-change pytest test | III. Every Requirement Is Testable | PASS | PASS | FR → test-module mapping table below; FR ids appear in test names/docstrings |
| Error paths tested for both message and exit status | III. Every Requirement Is Testable | PASS | PASS | Contract table gives exact stderr text and status for each path; tests assert both |
| Smallest design; no abstraction for a single caller | IV. Simplicity | PASS | PASS | 5 modules, each a distinct responsibility (see Structure Decision); no base classes, no registry, no plugin seam |
| No configuration option or extension point without a requirement | IV. Simplicity | PASS | PASS | Hash algorithm and iteration count are module constants, not options or stored fields; the store record carries only the four fields the requirements need |
| Runtime dependency manifest empty | Additional Constraints | PASS | PASS | `dependencies = []` |

**Result**: all gates PASS. No entries in Complexity Tracking.

### Requirement → test mapping

| Requirements | Test module |
|---|---|
| FR-001, FR-003, FR-004, FR-005, FR-035 | `tests/test_cli_usage.py` |
| FR-009 – FR-013, FR-010 boundary lengths | `tests/test_register.py` |
| FR-014 – FR-018 | `tests/test_login.py` |
| FR-019 – FR-025 | `tests/test_lockout.py` |
| FR-026 – FR-029 | `tests/test_passwd.py` |
| FR-030 – FR-033 | `tests/test_delete.py` |
| FR-002, FR-006 – FR-008, FR-034, FR-038 | `tests/test_store.py` |
| FR-036, FR-037 | `tests/test_passwords.py` |
| SC-002, SC-005, SC-006 (real process, real files) | `tests/test_end_to_end.py` |

## Project Structure

### Documentation (this feature)

```text
specs/001-local-account-manager/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── cli-contract.md  # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md  # Existing spec-quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml           # requires-python = ">=3.11"; dependencies = []; pytest pythonpath = ["src"]

src/
└── accounts/
    ├── __init__.py      # Empty marker; no re-exports
    ├── __main__.py      # python -m accounts entry: sys.exit(cli.main(sys.argv[1:], sys.stdin, sys.stdout, sys.stderr))
    ├── cli.py           # argparse parsing, stdin password reads, dispatch, stream writing, exit status
    ├── commands.py      # register/login/unlock/passwd/delete; username and password rules; lockout logic
    ├── store.py         # strict JSON load, atomic 0600 save, StoreError
    └── passwords.py     # per-account salt generation, PBKDF2 verifier derivation, constant-time verify

tests/
├── conftest.py          # tmp store path fixture; helper to run cli.main in-process
├── test_cli_usage.py
├── test_register.py
├── test_login.py
├── test_lockout.py
├── test_passwd.py
├── test_delete.py
├── test_store.py
├── test_passwords.py
└── test_end_to_end.py
```

**Structure Decision**: Single project, one package at `src/accounts/`, flat test directory.
The spec's recorded implementation constraint fixes `src/accounts` runnable as
`python -m accounts` with `src/` on `PYTHONPATH`, so the `src/` layout is given rather than
chosen. Within the package, five modules are the fewest that keep each requirement group in
one place and independently testable:

- `__main__.py` exists only because `python -m accounts` requires it; it holds no logic.
- `cli.py` owns everything that touches the process — `argv`, the three streams, the exit
  status. Keeping it the sole stream writer is what makes the "diagnostics never on stdout"
  gate checkable in one file.
- `commands.py` owns the five operations and their rules. It returns values instead of
  printing, so each requirement is testable without capturing streams.
- `store.py` owns the file: strict parsing and the atomic, owner-only write. Separating it is
  what allows FR-007 and FR-008 to be tested by handing it a corrupt or read-only file.
- `passwords.py` owns the one-way transformation. FR-036 ("two accounts with the same password
  have different verifiers") is a property of this module alone and is tested as such.

The template's unused layout options (web application, mobile + API) do not apply: there is no
frontend, no service, and no second deployable. No `models/`, `services/`, `lib/` subpackages
are created — with five modules they would be empty directories, which Principle IV forbids.

## Complexity Tracking

No Constitution Check violations. Nothing to justify.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)* | — | — |
