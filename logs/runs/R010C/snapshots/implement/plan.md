# Implementation Plan: Create Tar Archives (`create` command)

**Branch**: `002-create-archive-command` | **Date**: 2026-11-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-create-archive-command/spec.md`

## Summary

A third command on the existing zero-dependency `tarx` tool:
`python -m tarx create ARCHIVE PATH... [--overwrite]` packages the named files and directories
into one tar archive — gzip-compressed when `ARCHIVE` ends in `.tar.gz` or `.tgz`, plain
otherwise — and prints `created ARCHIVE with N files`. `list` and `extract` are not changed in
any observable way; `create` is additive, and the whole 001 test suite must keep passing
unmodified.

The technical approach mirrors `extract`'s **validate, then write**, with one addition that the
spec's all-or-nothing promise forces: **write somewhere else, then rename**. Pass 1 walks every
`PATH` with an explicit stack and `os.scandir(follow_symlinks=False)`, refusing anything that is
not a regular file or a directory, refusing absolute/`..`/duplicate/nested paths, enforcing the
same resource bounds `list` and `extract` already apply, and producing the complete, ordered
member list without writing anything. Pass 2 streams that list into a `mkstemp` temporary file
in the archive's own directory — opened `0o600` at creation — and `os.rename`s it onto `ARCHIVE`
as the final act. Any failure, at any point including mid-stream, unlinks the temporary file, so
nothing partial ever appears at `ARCHIVE` and a pre-existing archive is byte-for-byte unchanged.

Two further choices carry most of the security requirements. Every `TarInfo` is built field by
field rather than through `TarFile.add()`/`gettarinfo()`, so the local account's uid, gid, user
name, group name, permissions, and timestamps are never even read into a header — making SR-108
structural rather than remembered, and taking traversal order (FR-106) and symlink policy
(SR-102, SR-103) out of `tarfile`'s hands. And every member name the producer computes is passed
through `paths.validate_member_name` — the very function `extract` uses to decide what it will
accept — so FR-109's round-trip promise is an executed check rather than an argument.

## Technical Context

**Language/Version**: Python 3.11+ (no syntax or API newer than 3.11; verified against CPython
3.13.17 in this environment, as for 001)

**Primary Dependencies**: None. Standard library only (MC-101, constitution Principle I).
Runtime modules added by this feature: `tempfile` (for `mkstemp` only). Already in use and
reused here: `argparse`, `tarfile`, `gzip`, `os`, `os.path`, `pathlib`, `stat`, `errno`, `sys`,
`dataclasses`, `re`, `unicodedata`, `zlib`

**Storage**: N/A — no database and no persisted state. The filesystem is the output medium; the
only state is the single archive file the command writes.

**Testing**: `pytest` (development-only dependency, never imported by runtime code), configured
by the existing `pytest.ini` with `pythonpath = src`. Five new test modules plus additions to
`tests/helpers.py`, `tests/conftest.py`, and `tests/test_performance.py`.

**Target Platform**: POSIX-like filesystems, non-privileged user, local paths, no network (spec
Assumptions). Windows-specific absolute path forms (drive letters, UNC prefixes) are rejected
defensively per SR-101. `os.rename` atomicity within one filesystem is relied upon, which is why
the temporary file is created in `ARCHIVE`'s own directory.

**Project Type**: Single-project CLI tool — the existing `tarx` package under `src/`, run as
`python -m tarx` with `src/` on `PYTHONPATH`, no install step (MC-101)

**Performance Goals**: a 1,000-file, 50 MB tree is archived in under 5 s on a typical developer
machine (SC-108). Throughput is bounded by `gzip` compression and disk, neither of which this
design obstructs.

**Constraints**: bounded memory regardless of individual file size — no file's contents are ever
held whole in memory (SR-106), achieved by 64 KiB chunked reads through
`archive.COPY_CHUNK_BYTES`. Peak memory is dominated by at most 10,000 `PlannedMember` records.
Resource bounds are the existing fixed constants, imported not redefined: 10,000 members, 1 GiB
total, 1 GiB per member (SR-105). Traversal is iterative so that a very deep tree cannot raise
`RecursionError`, which would reach stderr as a traceback and breach SR-111. Offline-capable; no
configuration file.

**Scale/Scope**: 1 new runtime module (`create.py`, ≈200–250 lines) plus small additions to
three existing ones; 22 functional and 12 security requirements, each with at least one
automated test.

**No `NEEDS CLARIFICATION` items remain.** Every technical choice above is fixed by the
specification, by the requester's input (Python 3.11+, standard library only, the
specification's interface exactly, `pytest` for tests), or by a Phase 0 decision recorded in
[research.md](./research.md) (R-101 … R-118).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version 1.0.0. The Development Workflow section requires a plan to state, per
principle, how it complies.

### Initial check (before Phase 0) — **PASS**

| Principle | Compliance |
|---|---|
| **I. Standard Library Only** | `tarfile` + `gzip` + `os` cover the whole problem; the one new import is `tempfile`, also standard library. `pytest` stays dev-only and is not importable from any runtime path. |
| **II. Fail Loudly** | Every failure exits non-zero with an actionable stderr message (FR-112, FR-113, FR-121). The spec explicitly forbids silently skipping an unsupported entry (SR-102) or producing a truncated archive (SR-105). |
| **III. Every Requirement Is Testable** | All 22 FR-1xx and 12 SR-1xx identifiers are mechanically checkable; SC-110 already requires each to appear in a test name or docstring, and `tests/test_traceability.py` enforces it. |
| **IV. Simplicity** | One new module on an existing 7-module CLI. No abstraction layer, no configuration, no concurrency, no caching, no new exception class, no new constant. |
| **V. Secure by Default** | The spec carries a dedicated Security Requirements section (SR-101 – SR-112) derived from OWASP Top 10 (A01, A03, A04, A05) and ASVS V5/V12, so the feature is eligible to proceed to planning. |

### Post-design re-check (after Phase 1) — **PASS**

**I. Standard Library Only.** Dependencies considered and replaced with std-lib facilities:

| Considered | Replaced by |
|---|---|
| `shutil.make_archive` | hand-driven `tarfile.addfile` — `make_archive` offers no control over member order, metadata normalisation, symlink refusal, or self-exclusion (research R-101) |
| `TarFile.add(recursive=True)` | our own iterative traversal — `add()` copies on-disk uid/gid/mode/mtime into the header, which SR-108 forbids |
| a reproducible-tarball helper library | `format=PAX_FORMAT` with fixed header fields and `GzipFile(mtime=0)` (R-102, R-103) |
| `tempfile.NamedTemporaryFile` | `tempfile.mkstemp`, which gives the raw descriptor needed to wrap the gzip layer and to control the unlink ourselves (R-104) |

No runtime module imports anything outside the standard library. `pytest.ini` remains the only
test configuration, so the project still ships no package metadata and needs no install
(MC-101).

**II. Fail Loudly.** Invalid input fails as follows: usage errors via `argparse` → stderr +
exit 2; a rejected `PATH`, member, archive path, or bound via `TarxError` → one-line stderr
message naming the path or member at issue + exit 2; a pre-existing archive without
`--overwrite` via `OverwriteConflict` → exit 3. Nothing is skipped: a symlink or special file
inside a tree fails the whole command rather than being omitted (SR-102), and an exceeded bound
is an error rather than a truncated archive (SR-105). There is no bare `except`; the broadest
catch is `except OSError`, which still produces a message and a non-zero status. The one case
where a non-zero status accompanies a complete archive — stdout closed before the success line —
is reported as a failure (status 2) with no crash report, reusing 001's
`_silence_stdout_at_shutdown` (R-115). No failure is degraded into a partial result, and unlike
`extract` there is no documented partial-output exception at all.

**III. Every Requirement Is Testable.** Requirement-to-test mapping:

| Test module | Requirement identifiers covered |
|---|---|
| `tests/test_create.py` | FR-101, FR-102, FR-103, FR-104, FR-105, FR-106, FR-108, FR-110, FR-111, FR-112, FR-113, SR-112 |
| `tests/test_create_roundtrip.py` | FR-107, FR-109 (and SC-101 – SC-103, SC-107, SC-109) |
| `tests/test_create_overwrite.py` | FR-114, FR-115, FR-116, FR-121 |
| `tests/test_create_failures.py` | FR-117, FR-118, FR-119, FR-120, FR-122 (and SC-104, SC-106) |
| `tests/test_create_security.py` | SR-101 – SR-104, SR-106 – SR-111 (adversarial corpus, SC-105) |
| `tests/test_create_limits.py` | SR-105 |
| `tests/test_performance.py` (extended) | SC-108 |
| `tests/test_traceability.py` (unchanged) | SC-110 — fails if any FR-1xx/SR-1xx is unreferenced |

Every test function will carry its requirement identifiers in its name or docstring, and
`test_traceability.py` already makes the mapping a gate rather than a convention — it scans all
`specs/*/spec.md`, so it is **currently failing** for this spec's uncovered identifiers
(verified: `144 passed, 1 failed`). That failure is the gate working as designed and is cleared
by this feature's tests, not by changing the gate (R-118). Tests for a requirement ship in the
same change as the code implementing it.

MC-102 is covered by SC-109: the 144 inherited tests must pass **unmodified**. No existing test
file is edited except by addition (new fixtures, new helpers, one new performance case).

**IV. Simplicity.** Complexity explicitly declined:

| Declined | Why not needed now |
|---|---|
| A new exception class for create-side failures | `TarxError` and `OverwriteConflict` already carry exactly the two statuses FR-121 permits; a third class would create a third status to misuse |
| New resource-limit constants | SR-105 fixes the bounds as *the same* ones the existing commands enforce, so they are imported from `tarx.archive`, not redefined (R-111) |
| A `sources.py` module for `PATH` validation | One function added beside the existing name validators in `paths.py`, where 001's Structure Decision already puts "every decision about a member name" (R-113) |
| A generalised `validate_path(kind=...)` shared by members and sources | A parameter that selects only message wording is the configurability the constitution asks us not to add, and it would touch code the 001 suite depends on (R-113) |
| An `--exclude`/`--strip-components`/`--compression-level` option | Out of scope by the spec's own Scope boundaries; `--overwrite` is the only option |
| Parallel or threaded file reading | SC-108's 5 s budget is met by straightforward streaming |
| Appending to or updating an existing archive | Out of scope; `create` only ever writes a whole archive |
| An `openat`-based race-free descent | Rejected in 001 (R-007) on threat-model grounds; `O_NOFOLLOW` on each file open plus `lstat`-only kind checks already prevent following a link (R-110) |
| Transactional journalling or `fsync` barriers | FR-119 asks that no partial archive be *visible*; `mkstemp` + `rename` delivers that. Durability across a power loss is not a stated requirement |

The new module is one cohesive responsibility — the create-side validate-then-write sequence —
with no indirection, mirroring `extract.py`'s shape so that a reader who knows one knows the
other.

**V. Secure by Default.** Security Baseline, control by control:

| Baseline control | How this design satisfies it |
|---|---|
| **Untrusted input** | Command-line arguments are validated before use — non-empty, exactly one `ARCHIVE`, at least one `PATH`, `--overwrite` the only option (SR-112). Every `PATH` is validated against an allowed shape (relative, no `..`, no drive/UNC prefix, non-empty after normalisation) and **rejected**, never repaired (SR-101). Every filesystem entry is checked against an allowed kind — regular file or directory only (SR-102). |
| **No string-built interfaces** | No subprocess, no shell, no SQL, no markup anywhere in the tool. `PATH`s are used as paths directly, resolved against the current directory as the allowed base, with containment confirmed lexically and symlinks never followed out of it (SR-101, SR-103). Output destined for a terminal is encoded for that context by the existing `escape_name` (SR-110). |
| **Credentials and secrets** | N/A — the tool handles no credentials, reads no environment secrets, and persists no state. SR-108 and SR-111 cover the adjacent concern, disclosure of the local account and of file contents through output. |
| **Randomness and comparison** | No tokens, nonces, or secret comparisons exist. The one random value is the temporary filename, generated by `tempfile.mkstemp`, which uses a strong source and `O_EXCL` (R-104). |
| **Resource limits** | SR-105: 10,000 members, 1 GiB total, 1 GiB per member — the existing constants, enforced on stat sizes while the member set is built *and* on bytes actually read while writing. Exceeding a bound is an error, never truncation; because writing goes to a temporary file, an exceeded bound mid-write still leaves no archive (R-111). |
| **Access control** | No multi-user model, so no authorisation decisions exist. The closest analogue — the "inside the current directory" boundary — is checked at the point each path is used, and `O_NOFOLLOW` on every file open keeps the enumeration-time kind check valid at read time (R-110). |
| **File permissions** | SR-107: the archive and its temporary predecessor are created `0o600` by `mkstemp`'s own mode, set **at creation**; no `chmod` is ever issued and setuid/setgid/sticky can never be set. Recorded member modes are the fixed `0o644`/`0o755` of SR-108, never the on-disk mode. |
| **Output hygiene** | SR-110 and SR-111: messages contain only paths and reasons, escaped for the terminal. No file contents, no environment values, no tracebacks — including the `RecursionError` a deep tree would otherwise raise, which the iterative traversal makes impossible (R-106), and the bare `OSError` `tarfile` would raise on a shrinking file, which the explicit size check replaces with a named message (R-110). |

**No exceptions to the Security Baseline are taken.** Three consequences of security decisions
are recorded for reviewers rather than being exceptions:

1. A directory containing any symbolic link cannot be archived at all (SR-102) — the mirror of
   the restriction `extract` already imposes, and the spec's own stated Assumption.
2. `create photos/out.tar photos` silently omits `out.tar` from its own archive when a rerun with
   `--overwrite` finds it, because SR-109 requires the omission; naming `ARCHIVE` *directly* as a
   `PATH` is refused instead, so Principle II's "never silently skip what the user named" still
   holds for everything the user actually typed (R-109).
3. The archive-exists check before the rename narrows but does not eliminate a
   concurrent-creation race, consistent with 001's threat model of a hostile *archive* rather
   than a hostile concurrent local process (R-105).

**Result: PASS.** No violations, so Complexity Tracking below stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-create-archive-command/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — R-101 … R-118 decisions
├── data-model.md        # Phase 1 output — in-memory entities and validation rules
├── quickstart.md        # Phase 1 output — run + validation guide
├── contracts/
│   └── create-cli.md    # Phase 1 output — the `create` CLI contract, extending 001's
├── checklists/
│   └── requirements.md  # Pre-existing spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
pytest.ini                      # unchanged: pythonpath = src  (no package metadata, no install)

src/
└── tarx/
    ├── __init__.py             # unchanged
    ├── __main__.py             # unchanged — `raise SystemExit(cli.main())`
    ├── cli.py                  # MODIFIED: `create` subparser, run_create, dispatch branch,
    │                           #   empty-string checks for ARCHIVE and every PATH
    ├── errors.py               # MODIFIED (docstring only): OverwriteConflict now names its
    │                           #   second raise site; the two exit statuses are unchanged
    ├── archive.py              # unchanged — MAX_* and COPY_CHUNK_BYTES are imported by create.py
    ├── paths.py                # MODIFIED: + validate_source_path() beside the existing
    │                           #   validate_member_name(), reusing _components/_DRIVE_PREFIX
    ├── extract.py              # unchanged
    └── create.py               # NEW: Pass 1 enumeration/validation + Pass 2 temp-file writing
                                #   + rename, with the boundary visible in create_archive()

tests/
├── conftest.py                 # MODIFIED (additions only): source-tree fixtures
├── helpers.py                  # MODIFIED (additions only): on-disk tree builders, incl.
│                               #   hostile trees (symlink, FIFO, deep, oversized)
├── test_cli_contract.py        # unchanged (001)
├── test_list.py                # unchanged (001)
├── test_extract.py             # unchanged (001)
├── test_overwrite.py           # unchanged (001)
├── test_security.py            # unchanged (001)
├── test_limits.py              # unchanged (001)
├── test_traceability.py        # unchanged (001) — already gates this spec's identifiers
├── test_performance.py         # MODIFIED (addition only): SC-108 create benchmark
├── test_create.py              # NEW: command surface, naming, ordering, reporting
├── test_create_roundtrip.py    # NEW: create → list → extract acceptance corpus
├── test_create_overwrite.py    # NEW: exit 3 vs exit 2 at the archive path
├── test_create_failures.py     # NEW: all-or-nothing, missing/changing inputs
├── test_create_security.py     # NEW: SR-1xx adversarial corpus
└── test_create_limits.py       # NEW: SR-105 bounds on the create side
```

**Structure Decision**: the single-project layout established by 001 is kept; this feature adds
one module and touches three. `create.py` sits beside `extract.py` because it is the same shape
in the other direction — a validation pass that writes nothing, then a write pass — and keeping
them as siblings rather than merging them means neither file has to branch on direction, and the
001 module keeps its line-for-line behaviour (FR-101).

The division of responsibility follows the one 001 already chose, which is why no file moves:

- `errors.py` stays the only place an exit status is *defined* and `cli.py` the only place one is
  *chosen*, so FR-121's "no other exit status" remains checkable by reading one function;
- `paths.py` keeps every decision about a *name* — now including `PATH` validation (SR-101)
  alongside member-name validation (001 SR-001) and display escaping (SR-110) — so the three can
  be reviewed together;
- `archive.py` keeps the resource bounds, which `create.py` imports rather than redefines, so
  SR-105's "the same bounds as the existing commands" cannot drift;
- `create.py` holds the enumerate-then-write sequence with the boundary visible in
  `create_archive()`, which is where FR-118, FR-119, and SC-106 are enforced.

Public shape of the new module (the interface the tasks phase will implement against):

```python
# src/tarx/create.py
MEMBER_FILE_MODE = 0o644        # SR-108
MEMBER_DIR_MODE  = 0o755        # SR-108

@dataclass
class PlannedMember: ...        # name, kind, path, size, origin   (data-model.md §2)

def plan_members(given_paths, archive_path) -> CreationPlan: ...
    # Pass 1: validate, traverse, order, bound, de-duplicate. Writes nothing.

def write_archive(plan, target) -> None: ...
    # Pass 2: mkstemp → (gzip) → tarfile → stream → rename. Unlinks the temp on any failure.

def create_archive(archive, given_paths, overwrite: bool = False) -> int: ...
    # Classify the target, plan, then write; returns N (regular files added).
```

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. The Constitution Check passes both before Phase 0 and after Phase 1 design, with
no Security Baseline exceptions taken. Complexity declined rather than added is listed under
Principle IV above; the three consequences recorded under Principle V are properties of the
specification, not exceptions to it.
