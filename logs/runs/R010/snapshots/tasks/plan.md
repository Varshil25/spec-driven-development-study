# Implementation Plan: Tar Archive Listing and Extraction Tool

**Branch**: `001-tarx-cli` | **Date**: 2026-11-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-tarx-cli/spec.md`

## Summary

A zero-dependency command-line tool, run as `python -m tarx`, with two commands: `list
ARCHIVE` prints every member name in archive order, and `extract ARCHIVE DEST [--overwrite]`
writes the archive's regular files and directories beneath `DEST` and prints
`extracted N files`. Both plain and gzip-compressed tar archives are supported, with the
format decided from the archive's content rather than its filename.

The technical approach treats the archive as wholly untrusted and is built around one
decision: **validate every member, then write**. A single `tarfile.TarFile` is iterated
*lazily* to enforce resource bounds, and each member's name, kind, declared size, destination
mapping, symlink exposure, uniqueness, and destination state are checked before anything is
written — so a rejected archive leaves the destination contents byte-for-byte unchanged. The
write phase never calls `TarFile.extract`/`extractall`; it opens each file itself with
`os.open(..., O_CREAT | O_EXCL-or-O_TRUNC | O_NOFOLLOW, 0o600)` and streams contents in 64 KiB
chunks. That one choice simultaneously delivers narrowest-permissions-at-creation, refusal to
follow symlinks, bounded memory for arbitrarily large members, and the guarantee that archive
permission/ownership/timestamp metadata is never applied.

Failure handling funnels through one exception hierarchy and one handler, so the promise that
only exit statuses 0, 2, and 3 are producible — and that 3 means *solely* an overwrite
conflict — is verifiable by reading a single function.

## Technical Context

**Language/Version**: Python 3.11+ (no syntax or API newer than 3.11; verified against
CPython 3.13.17 in this environment)

**Primary Dependencies**: None. Standard library only (MC-001, constitution Principle I).
Runtime modules used: `argparse`, `tarfile`, `gzip`, `zlib`, `os`, `os.path`, `pathlib`,
`shutil` (chunked copy only), `stat`, `errno`, `sys`, `unicodedata`, `dataclasses`, `re`

**Storage**: N/A — no database and no persisted state. The filesystem is the output medium;
the only state is the destination tree the tool writes.

**Testing**: `pytest` (development-only dependency, never imported by runtime code),
configured via `pytest.ini` with `pythonpath = src`

**Target Platform**: POSIX-like filesystems, non-privileged user, local paths, no network
(spec Assumptions). Windows-specific absolute path forms (drive letters, UNC prefixes) are
still rejected defensively per SR-001.

**Project Type**: Single-project CLI tool — a `tarx` package under `src/`, run as
`python -m tarx` with `src/` on `PYTHONPATH`, no install step (MC-002)

**Performance Goals**: A 1,000-member, 50 MB archive lists or extracts in under 5 s on a
typical developer machine (SC-007). Streaming throughput is bounded by `gzip` decompression
and disk, both of which this design leaves unobstructed.

**Constraints**: Bounded memory regardless of member size — no member's contents are ever
held whole in memory (SC-007), achieved by 64 KiB chunked copies. Peak memory is dominated by
at most 10,000 `TarInfo` objects plus plan entries. Resource bounds are fixed constants:
10,000 members, 1 GiB total uncompressed, 1 GiB per member (SR-005). Offline-capable; no
configuration file.

**Scale/Scope**: 7 runtime modules, roughly 450–550 lines of runtime code; 19 functional
requirements and 10 security requirements, each with at least one automated test.

**No `NEEDS CLARIFICATION` items remain.** Every technical choice above is fixed by the
specification, the requester's input, or a Phase 0 decision recorded in
[research.md](./research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0. The Development Workflow section requires a plan to state, per
principle, how it complies.

### Initial check (before Phase 0) — **PASS**

| Principle | Compliance |
|---|---|
| **I. Standard Library Only** | Zero runtime dependencies by design; `tarfile` + `gzip` cover the whole problem. `pytest` is dev-only and is not importable from any runtime path. |
| **II. Fail Loudly** | Every failure exits non-zero with an actionable stderr message (FR-013, FR-015 – FR-017). The spec explicitly forbids silently skipping unsupported members (SR-002, SR-003). |
| **III. Every Requirement Is Testable** | All 19 FR and 10 SR identifiers are mechanically checkable; SC-008 already requires each to appear in a test name or docstring. |
| **IV. Simplicity** | A two-command CLI over `tarfile` with no abstraction layers, no configuration, no concurrency, no caching. |
| **V. Secure by Default** | The spec carries a dedicated Security Requirements section (SR-001 – SR-010) derived from OWASP Top 10 and ASVS file-handling requirements, so the feature is eligible to proceed to planning. |

### Post-design re-check (after Phase 1) — **PASS**

**I. Standard Library Only.** Dependencies considered and replaced with std-lib facilities:

| Considered | Replaced by |
|---|---|
| `click` / `typer` for the CLI | `argparse` with subparsers — already produces FR-001's exact behaviour (usage to stderr, exit 2) |
| a safe-extraction helper library | our own validate-then-write pass over `tarfile`, which is *stricter* than `tarfile`'s own `data` filter (R-003) |
| `pytest-cov` for coverage | requirement-identifier traceability via `test_traceability.py`, which is what Principle III actually asks for |

No runtime module imports anything outside the standard library. `pytest.ini` (not
`pyproject.toml`) holds the test configuration, so the project ships no package metadata and
cannot be mistaken for something requiring installation (MC-002).

**II. Fail Loudly.** Invalid input fails as follows: usage errors via `argparse` → stderr +
exit 2; archive and member problems via `TarxError` → one-line stderr message naming the
archive path, member name, or destination path, + exit 2; overwrite conflicts via
`OverwriteConflict` → exit 3. There is no bare `except`; the broadest catch is
`except OSError`, which still produces a message and a non-zero status. No failure is
degraded into a default or partial result — the one case where a partial result is possible
(SR-005 actual-byte abort) still exits non-zero *and* states in its message that the
destination may hold a partial extraction. Messages comply with Principle V's output
restriction: paths and reasons only (SR-008).

**III. Every Requirement Is Testable.** Requirement-to-test mapping:

| Test module | Requirement identifiers covered |
|---|---|
| `tests/test_cli_contract.py` | FR-001, FR-015, FR-016, FR-017, SR-010 |
| `tests/test_list.py` | FR-002, FR-003, FR-008, FR-018 |
| `tests/test_extract.py` | FR-004, FR-005, FR-006, FR-007, FR-008, FR-013, FR-014, FR-018, FR-019 |
| `tests/test_overwrite.py` | FR-009, FR-010, FR-011, FR-012 |
| `tests/test_security.py` | SR-001, SR-002, SR-003, SR-004, SR-006, SR-007, SR-008, SR-009 |
| `tests/test_limits.py` | SR-005 |
| `tests/test_performance.py` | SC-007 |
| `tests/test_traceability.py` | SC-008 — fails if any FR-xxx/SR-xxx in `spec.md` is unreferenced |

Every test function carries its requirement identifiers in its name or docstring, and
`test_traceability.py` makes the mapping a gate rather than a convention. Tests for a
requirement ship in the same change as the code implementing it.

**IV. Simplicity.** Complexity explicitly declined:

| Declined | Why not needed now |
|---|---|
| Configurable resource limits | SR-005 fixes the three bounds as constants; the spec records configurability as a possible later change |
| Pluggable compression backends | Only tar and gzip are in scope; `mode="r:*"` was rejected precisely because it would silently widen support (R-002) |
| An abstraction over the filesystem for testing | `pytest`'s `tmp_path` exercises the real filesystem, which is where the symlink and permission behaviour under test actually lives |
| Transactional extraction (temp dir + atomic rename) | FR-014's validate-before-write already delivers the "destination unchanged on failure" guarantee that a transaction would buy |
| Concurrency / parallel member writes | SC-007's 5 s budget is met by straightforward streaming |
| `openat`-based race-free directory descent | Rejected in R-007: the threat model is a hostile archive, not a hostile concurrent local process, and `O_NOFOLLOW` + `O_EXCL` already prevent the symlink write |

The 7-module split is not layering — each module is one cohesive responsibility with no
indirection between them, and no module exists to anticipate a future need.

**V. Secure by Default.** Security Baseline, control by control:

| Baseline control | How this design satisfies it |
|---|---|
| **Untrusted input** | Archive names, kinds, and declared sizes are all validated against an allowed shape before use (SR-001 – SR-003, SR-005); command-line arguments validated before use (SR-010). Rejected, never repaired. |
| **No string-built interfaces** | No subprocess, no shell, no SQL, no markup anywhere in the tool. Paths are resolved against `DEST` as the allowed base, containment is confirmed lexically, and symlinks out of the base are refused (SR-001, SR-004). Output destined for a terminal is encoded for that context (SR-007). |
| **Credentials and secrets** | N/A — the tool handles no credentials, reads no environment secrets, and persists no state. |
| **Randomness and comparison** | N/A — no identifiers, tokens, nonces, or secret comparisons. |
| **Resource limits** | SR-005: 10,000 members, 1 GiB total, 1 GiB per member, enforced on declared sizes before writing *and* on actual bytes during writing. Lazy iteration is what makes the member cap enforceable. Exceeding a bound is an error, never truncation. |
| **Access control** | No multi-user model, so no authorisation decisions exist. The closest analogue — the destination boundary — is checked at the point each path is used, not only where it is requested, and `O_NOFOLLOW`/`O_EXCL` keep the check valid at write time. |
| **File permissions** | SR-006: `0o600` for files and `0o700` for directories, passed to `os.open`/`os.mkdir` as the mode argument so they are set **at creation**. Archive modes are never read; setuid/setgid/sticky can never be set. |
| **Output hygiene** | SR-008: messages contain only paths and reasons. No member contents, no environment values, no tracebacks — including the verified `EOFError` from a corrupt gzip stream, which is caught explicitly (R-010). |

**No exceptions to the Security Baseline are taken.** Two consequences of security decisions
are recorded for reviewers rather than being exceptions: an escaped member name on output is
a display form and not always a shell-pasteable path (SR-007, R-008), and a broken pipe exits
2 rather than the conventional 141 because FR-015 forbids any other status (R-011).

**Result: PASS.** No violations, so Complexity Tracking below stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-tarx-cli/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — R-001 … R-016 decisions
├── data-model.md        # Phase 1 output — in-memory entities and validation rules
├── quickstart.md        # Phase 1 output — run + validation guide
├── contracts/
│   └── cli.md           # Phase 1 output — authoritative CLI contract
├── checklists/
│   └── requirements.md  # Pre-existing spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pytest.ini                      # dev-only: pythonpath = src  (no package metadata, no install)

src/
└── tarx/
    ├── __init__.py             # package marker; no runtime logic
    ├── __main__.py             # `python -m tarx` entry: raise SystemExit(cli.main())
    ├── cli.py                  # argparse definition, dispatch, stdout writing,
    │                           #   the single TarxError→exit-status handler
    ├── errors.py               # TarxError (exit 2), OverwriteConflict (exit 3)
    ├── archive.py              # magic-byte format sniffing, TarFile opening,
    │                           #   lazy bounded member iteration, limit constants
    ├── paths.py                # member-name validation, destination mapping,
    │                           #   symlink-component refusal, escape_name for display
    └── extract.py              # Pass 1 plan building + Pass 2 chunked writing

tests/
├── conftest.py                 # tmp_path-based archive-builder fixtures
├── helpers.py                  # in-process tarfile/TarInfo construction, incl. hostile members
├── test_cli_contract.py        # FR-001, FR-015, FR-016, FR-017, SR-010
├── test_list.py                # FR-002, FR-003, FR-008, FR-018
├── test_extract.py             # FR-004 – FR-008, FR-013, FR-014, FR-018, FR-019
├── test_overwrite.py           # FR-009 – FR-012
├── test_security.py            # SR-001 – SR-004, SR-006 – SR-009 (adversarial corpus)
├── test_limits.py              # SR-005
├── test_performance.py         # SC-007
└── test_traceability.py        # SC-008 — every FR/SR identifier is referenced by a test
```

**Structure Decision**: Single-project layout. `src/tarx/` holds the package, which MC-002
requires to be importable from `src/` and runnable as `python -m tarx` with no install step;
`tests/` sits beside it at the repository root and finds the package through
`pytest.ini`'s `pythonpath = src`. There is no `models/`, `services/`, or `lib/` subdivision —
the tool has no persistence layer and no service boundary, so the template's layered
directories would be empty ceremony (Principle IV). The 7 modules divide by responsibility,
not by layer:

- `errors.py` is the only place exit statuses are defined, and `cli.py` the only place one is
  chosen, which is what makes FR-015 auditable;
- `paths.py` holds every decision about a member *name* — validating it, mapping it to a
  destination, and rendering it safely for display — so SR-001, SR-004, and SR-007 are
  reviewable in one file;
- `archive.py` owns format detection and the resource bounds, the two things that must happen
  before any member is trusted;
- `extract.py` holds the validate-then-write sequence, with the boundary between the two
  passes visible in one function, which is where FR-014 and SC-006 are enforced.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. The Constitution Check passes both before Phase 0 and after Phase 1 design,
with no Security Baseline exceptions taken. Complexity declined rather than added is listed
under Principle IV above.
