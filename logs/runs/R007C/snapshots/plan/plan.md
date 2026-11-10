# Implementation Plan: Burn After Reading and Password Protection

**Branch**: `002-burn-after-reading-password` | **Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-burn-after-reading-password/spec.md`

## Summary

Two optional publication fields on the existing service: `burn_after_reading`, which makes a
snippet's first successful read its last, and `password`, which makes every read present
`X-Paste-Password`. `GET /pastes/<id>` gains `burn_after_reading` and `protected` booleans.

The design adds no module and no dependency. The one-time claim is a single `os.unlink` plus a
directory `fsync` — POSIX `unlink` is already the exactly-once primitive FR-050 needs, and the
`fsync` before the first byte of the response is what FR-048 means by durable-before-send; the
existing `DELETE` path is folded into the same routine. The password is stored as a per-snippet
salted PBKDF2-HMAC-SHA256 derivation whose iteration count is **measured once at startup** so that
one verification costs ~50 ms on the serving host, which is the only way a band stated relative to
"the machine serving requests" (FR-073) can hold anywhere. `hashlib` releases the GIL, so
`ThreadingHTTPServer` already satisfies FR-074 with no pool or queue. The stored record gains two
keys, optional on read so that records written by the previous version remain valid (FR-067), and the
pre-read body ceiling grows from 394,240 to 395,776 bytes because the old one genuinely rejects a
submission this spec deems valid (FR-071).

Net change: roughly 120 lines across the two existing runtime modules, four new test modules, and no
edit to any feature 001 test.

## Technical Context

**Language/Version**: Python 3.11+ — unchanged, stated in `README.md` as the constitution requires.
No module may use a newer feature.

**Primary Dependencies**: None at runtime. Two standard-library modules are added to the set feature
001 uses: `hashlib` (`pbkdf2_hmac`) and `time` (`perf_counter`, for the one startup measurement).
`secrets` and `os` were already imported. `pytest` remains the only development dependency,
declared in `requirements-dev.txt` and never imported by runtime code.

**Storage**: Local filesystem, unchanged in layout — one JSON file per snippet at `<DIR>/<id>.json`,
still the sole source of truth. The record gains two keys, optional on read; removal gains a
directory `fsync`. See [contracts/storage.md](./contracts/storage.md).

**Testing**: `pytest`, on the two fixtures `tests/conftest.py` already provides. Every requirement
FR-045…FR-074 is named by at least one test; see the
[requirement to test map](./data-model.md#requirement-to-test-map). Feature 001's test modules are
run **unmodified** — that is the evidence for FR-068 and SC-018, so changing one of them would be a
failure of this feature, not a fix.

**Target Platform**: Linux/POSIX host, loopback only. Unchanged, and the claim protocol leans on the
same POSIX guarantees the publication protocol already does — `unlink` is atomic and fails with
`ENOENT` on an absent entry, and a directory `fsync` makes an entry removal durable
([research.md](./research.md) R-04).

**Project Type**: Single-package CLI-launched HTTP service (`src/pastebin`, run as
`python -m pastebin` with `src/` on the module search path). Unchanged.

**Performance Goals**:
- One password verification costs 10–200 ms on the serving host, targeted at 50 ms by a startup
  measurement (FR-073, SC-021).
- A verification delays no request about another snippet (FR-074). Measured on this two-core host:
  four concurrent 200,000-iteration derivations took 92.5 ms against 189.3 ms of serial work, so
  `hashlib` does release the GIL ([research.md](./research.md) R-03).
- A read of an **unprotected** snippet is unchanged — the header is not even inspected (FR-062).
- Startup still announces readiness well inside SC-007's two seconds: the calibration measurement
  costs roughly 15 ms.
- Feature 001's concurrency obligations (FR-042, FR-043, SC-010) continue to hold unchanged.

**Constraints**:
- `burn_after_reading` must be a JSON boolean; `password` a string of 1–128 **characters**. `null` is
  invalid for both — absence, not `null`, declines either option (FR-046, FR-055).
- Wire names are fixed by the spec: `burn_after_reading`, `password`, `protected`,
  `X-Paste-Password`. Status codes are fixed: 400 for an invalid option, 403 for a password failure,
  404 in precedence over 403, and 201/200/204 unchanged.
- A one-time snippet is consumed only by a read that passed every check and holds the text, and is
  claimed durably **before** the response is written (FR-048, FR-049).
- The password is never stored recoverably, never returned, never logged (FR-056, FR-057, SC-015).
- Verification is constant-time with respect to how much of a presented password is correct (FR-061).
- Pre-read body ceiling 394,240 → 395,776 bytes, still a fixed constant independent of any declared
  length (FR-071).
- Everything feature 001 specifies holds unchanged for a snippet published without either option,
  the widened ceiling excepted (FR-068).

**Scale/Scope**: Single operator, single host. 30 functional requirements (FR-045…FR-074), 3 user
stories, 11 success criteria (SC-011…SC-021). ~120 added lines of runtime code in the two existing
modules; 4 new test modules; 0 new runtime modules.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.0.0.

| Gate | Status (pre-Phase 0) | Status (post-Phase 1) | Evidence |
|------|----------------------|-----------------------|----------|
| **I. Standard Library Only** — no third-party import reachable from an entry point | PASS | PASS | The two added imports are `hashlib` and `time`, both standard library. `hashlib.pbkdf2_hmac` was chosen over `hashlib.scrypt` partly *because* it is unconditionally present rather than dependent on the interpreter's OpenSSL build ([research.md](./research.md) R-01), so "installs anywhere Python runs" holds without a fallback path. No password library, no `passlib`-style format, no third-party KDF. `pytest` remains confined to `tests/` and `requirements-dev.txt`. |
| **II. Fail Loudly** — clear diagnostic + explicit failure signal; no sentinels, no bare `except`, no guessing | PASS | PASS | Every new rejection is an explicit `{"error": ...}` body with a defined status: 400 for an invalid option, 403 for a password failure, 404 for a gone snippet, 500 for damaged storage ([contracts/http-api.md](./contracts/http-api.md)). No coercion anywhere — `"true"`, `1`, and `null` are 400s for `burn_after_reading`, and `""` is a 400 for `password`; a header value is never trimmed, case-folded, or normalised. Three exceptions are newly caught, each at the site that handles it and each translated into a clearer error, which is the one thing Principle II permits: `UnicodeDecodeError` on the header bytes → 403 ([research.md](./research.md) R-06), `FileNotFoundError` on the claim → 404, and any other `OSError` from the claim → `StoreCorrupt` → 500 with a stderr diagnostic (R-04). None is a swallow; each has an explicit outward failure. No bare `except:`, no `except Exception: pass`. The `store` functions still raise rather than return a sentinel a caller could mistake for a snippet — `burn_paste` returns a boolean that is *the* answer to "did I claim it", not a stand-in for a record. |
| **III. Every Requirement Is Testable** — each FR mapped to a named `pytest` test | PASS | PASS | All 30 FRs mapped in [data-model.md](./data-model.md#requirement-to-test-map), each test naming its identifier. The two requirements that look least testable are the reason R-02 and R-10 exist: FR-073's cost band is assertable *because* the iteration count is calibrated to the host rather than hard-coded, and FR-050's exactly-once is assertable with a `threading.Barrier` on the existing in-process fixture (the probe form produced one winner in 200 of 200 trials). FR-068 is tested by running feature 001's suite unmodified. Error behaviour required by Principle II has dedicated tests per status (`test_fr069_*`, `test_fr070_*`). |
| **IV. Simplicity** — smallest design, functions and plain data, no speculative extension points | PASS | PASS | No new module, no new class, no new entity — two keys on the existing `dict` record and two helper functions in `store`. The claim needs no lock file, index, tombstone, or in-memory set, because `unlink` already *is* exactly-once (R-04); the existing `DELETE` path is folded into the same routine, so the design removes a near-duplicate rather than adding one. No thread pool for verification, because `hashlib` releases the GIL and `ThreadingHTTPServer` is already there (R-03). The `password` sub-record has no `algorithm` field, because there is one algorithm. No `--password-cost` option, no pepper file, no rewrite-on-read migration. Two judgement calls are recorded rather than assumed obvious: the startup calibration (justified below) and nesting the derivation values under one key instead of three flat ones (R-08). |

**Result**: No violations. Complexity Tracking is empty.

**The one judgement call worth naming**: the startup calibration is ~20 lines that a hard-coded
iteration count would not need. It is not a speculative extension point or a configuration knob —
nothing can set it, and it has exactly one consumer — but it *is* code a simpler design would omit,
so Principle IV requires it be justified against a present requirement. FR-073 bounds a verification
at 10–200 ms "on the machine serving requests", and SC-021 makes that an asserted test. A fixed count
tuned to 50 ms here breaches the ceiling on a host four times slower and falls under the floor on one
five times faster, so the requirement would hold only on this machine and its test would be a
hardware lottery. Measuring makes it hold by construction. Full reasoning and the rejected
alternatives — fixed constant, CLI option, per-request recalibration — are in
[research.md](./research.md) R-02.

**Technology constraints check**: `json` for serialization, `pathlib` for paths, plain `stderr`
writes for diagnostics, `pytest` as the only development tool, `argparse` unchanged — all as the
constitution's Technology and Dependency Constraints section prescribes. The storage format is still
JSON, readable by the standard library alone, which is why a packed `algorithm$iterations$salt$hash`
string was rejected in favour of a nested object (R-08). `logging` is still deliberately unused:
FR-068 carries FR-044's prohibition on per-request output forward.

## Project Structure

### Documentation (this feature)

```text
specs/002-burn-after-reading-password/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── http-api.md      #   Delta on feature 001's HTTP contract: 2 fields, 1 header, 2 flags
│   └── storage.md       #   Delta on feature 001's storage contract: 2 keys, claim protocol
├── checklists/
│   └── requirements.md  # Existing spec-quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

There is no `contracts/cli.md` delta: the command line, the ready line, the exit statuses, and the
output discipline are untouched by this feature, so
[../001-pastebin-service/contracts/cli.md](../001-pastebin-service/contracts/cli.md) stands as
written.

### Source Code (repository root)

Changed and added files only; every other file in the repository is untouched.

```text
README.md                  # M  Document the two options, the header, the two flags, the new ceiling

src/
└── pastebin/
    ├── __init__.py        # -  unchanged
    ├── __main__.py        # -  unchanged (calibration happens in make_server, which it already calls)
    ├── server.py          # M  publish: validate the two new fields (absence, not null, declines)
    │                      #    read:    password gate, then claim, then respond — in that order
    │                      #    read:    report burn_after_reading and protected
    │                      #    helpers: _presented_password (get_all + latin-1 → utf-8)
    │                      #    make_server: calibrate and store password_iterations
    └── store.py           # M  MAX_BODY_BYTES recomputed; MIN/MAX_PASSWORD_CHARS added
                           #    create_paste: accept burn flag and password, derive and store
                           #    _validate_record: five required keys, two optional, strict types
                           #    hash_password / password_matches / calibrate_password_iterations
                           #    _unlink_durably (unlink + directory fsync), used by both removals
                           #    burn_paste: claim a one-time snippet, True if won
                           #    delete_paste: now routed through _unlink_durably

tests/
├── conftest.py            # -  unchanged — both fixtures, the raw-socket client, and the
│                          #    read_record/write_record helpers already cover what is needed
├── test_cli.py            # -  unchanged  ┐
├── test_publish.py        # -  unchanged  │
├── test_read.py           # -  unchanged  │  feature 001's suite runs unmodified; that it does
├── test_delete.py         # -  unchanged  │  is the evidence for FR-068 and SC-018, so editing
├── test_expiry.py         # -  unchanged  │  any of these would be a failure, not a fix
├── test_persistence.py    # -  unchanged  │
├── test_routing.py        # -  unchanged  │
├── test_errors.py         # -  unchanged  │
├── test_damaged_storage.py# -  unchanged  │
├── test_concurrency.py    # -  unchanged  ┘
├── test_burn.py           # A  FR-045..FR-053: publish, consume, exactly-once, restart, no-consume
├── test_password.py       # A  FR-054..FR-063, FR-072..FR-074: validation, verification, cost, 403s
├── test_flags.py          # A  FR-064..FR-066: the two report flags, raw endpoint unchanged
└── test_compatibility.py  # A  FR-067..FR-071: legacy records, 001 unchanged, error shape, ceiling
```

**Structure Decision**: the feature is absorbed into the two existing runtime modules along the
boundary feature 001 already drew — `store` owns the record, its encoding, and its durable removal;
`server` owns the HTTP surface, validation, and the order of checks. The password derivation goes in
`store`, not a new `passwords` module, because it is part of the record's encoding and is the thing
`store` must validate on read; a third module would be a layer with one caller, which Principle IV
forbids ("prefer one obvious module over several indirect ones"). The claim goes in `store` for the
same reason and sits beside `delete_paste`, which it shares its implementation with.

Tests follow feature 001's convention of one module per requirement group rather than the template's
`contract/integration/unit` split, for the same reason: nearly every test drives the real HTTP
surface. The four new modules map one-to-one onto the spec's four requirement headings, which is what
makes `pytest -k fr0NN` a useful coverage check.

## Complexity Tracking

> No Constitution Check violations. This table is intentionally empty.
>
> The startup calibration of the password iteration count is the only element of the design that a
> smaller implementation could omit. It is not a violation — it is forced by FR-073's
> machine-relative cost band, as the Constitution Check records and [research.md](./research.md) R-02
> argues in full — but it is the first thing to revisit if that requirement is ever amended to name a
> fixed cost parameter instead of a time band.
