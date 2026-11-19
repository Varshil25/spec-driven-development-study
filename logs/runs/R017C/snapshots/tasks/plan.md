# Implementation Plan: Burn-After-Reading and Password-Protected Pastes

**Branch**: `002-burn-and-password-pastes` | **Date**: 2026-11-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-burn-and-password-pastes/spec.md`

## Summary

Two optional creation fields are added to the existing pastebin service. `burn_after_reading:
true` makes a paste one-time — the first successful read of either form returns it and destroys
it, so every later request is `404`. `password: "…"` protects a paste — reading it, in either
form, then requires the `X-Paste-Password` header, and a missing or wrong password is `403`
(`404` still takes precedence for a paste that does not exist). `GET /pastes/<id>` gains
`burn_after_reading` and `protected` booleans. Everything else the service does today is
unchanged (FR-053).

**Technical approach**: no new route, no new module, no new dependency. `models.py` gains the two
validation rules (inserted before the content-size rule, so an invalid new field is `400` rather
than `413`) and a PBKDF2-HMAC-SHA-256 verifier at OWASP's current parameters, compared with
`hmac.compare_digest` over derived digests. `store.py` gains the interpretation of two optional
record keys — absent means "off" so that pre-feature records keep working, malformed means "this
paste does not exist" so that the service fails closed — and one new operation, `consume_record`,
whose `os.unlink` *is* the atomic claim on a one-time paste. `server.py` gains header decoding and
one evaluation order on both read paths: `404` (unknown / expired / unusable) → `403` (wrong
password) → claim → serve. Content is read before the claim and written to the socket only after
it succeeds. Every decision is recorded in [research.md](./research.md) as R-16 … R-26; the
extended entity and storage rules in [data-model.md](./data-model.md); the wire delta in
[contracts/http-api.md](./contracts/http-api.md); runnable validation in
[quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.11+ (developed against 3.13), per the user input and the spec's
Constraints. Unchanged from 001; `datetime.UTC` independently requires the 3.11 floor.

**Primary Dependencies**: None at runtime — standard library only (Constitution Principle I, spec
Constraints, user input). This feature adds exactly one module to 001's list of thirteen:
`hashlib` (for `pbkdf2_hmac`). `hmac` and `secrets` were already in use. `pytest` remains a
test-only dependency under the Principle I exemption, and is the test framework per the user
input.

**Storage**: Filesystem, unchanged. The same one-UTF-8-JSON-record-per-paste layout at
`<data_dir>/<id>.json`, mode `0600` inside a `0700` directory, written via `O_EXCL` temp file +
`fsync` + `os.replace`. Two **optional** keys are added to the record: `burn_after_reading`
(boolean) and `password` (a `{algorithm, iterations, salt, hash}` object, or `null`). No new file,
no index, no sidecar, no migration, no startup scan (R-17).

**Testing**: `pytest`, driving a real server on an ephemeral port over real HTTP with stdlib
clients, exactly as the 001 suite does. Three new modules (`test_burn.py`, `test_password.py`,
`test_compat.py`), the existing `test_requirement_coverage.py` gate extended to `FR-001 … FR-054`
and `SR-001 … SR-020`, and the suite-wide response scanner extended to passwords and verifier
material (R-26).

**Target Platform**: POSIX (Linux, macOS). This feature additionally relies on POSIX `unlink`
atomicity — of N concurrent `unlink` calls on one path, exactly one succeeds (R-20).

**Project Type**: Single-package CLI-launched HTTP service. Unchanged.

**Performance Goals**: None specified. One new cost is accepted and stated: a read of a protected
paste runs one PBKDF2 derivation, roughly 0.2 s of OpenSSL time, with O(1) memory. Memory per
request stays inside the existing ~66 KB envelope — the reason PBKDF2 was chosen over scrypt
(R-16).

**Constraints**: inherited from 001 and unchanged — `content` ≤ 65 536 encoded bytes, `expires_in`
∈ [1, 2 592 000], declared body ≤ 66 560 bytes, loopback-only binding, whole-second UTC
timestamps. New: `password` is 1 … 128 **characters** (not bytes — deliberately the opposite
measure from `content`); the caller-facing surface stays the same four addresses with no route,
method, or command-line option added; the reader's password travels in `X-Paste-Password` and the
revocation secret in `X-Delete-Token`.

**Scale/Scope**: unchanged — thousands of pastes, single operator, no listing, no enumeration, no
editing, no password change and no password recovery (spec Assumptions).

**Unknowns**: none. Every `NEEDS CLARIFICATION` raised while drafting this section was resolved in
Phase 0 — see the "Resolved unknowns summary" table in [research.md](./research.md). The
substantive ones were: which standard-library password hash at which parameters (R-16), how a
verifier is stored without breaking pre-feature records (R-17), what makes single-read destruction
atomic (R-20), and how a non-ASCII password survives an HTTP header (R-19).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Assessed against constitution **v1.0.0** (ratified 2026-11-16).

### Initial check (pre-Phase 0) — PASS

| Principle | Assessment | Verdict |
|---|---|---|
| **I. Standard Library Only** | The spec's Constraints and the user input both mandate stdlib-only, and state explicitly that the password hashing SR-013 requires must come from the standard library. `hashlib.pbkdf2_hmac` and `hashlib.scrypt` are both available and both named in the Security Baseline, so no gap exists and no exception is requested. | PASS |
| **II. Fail Loudly** | Every new rejection is an explicit status with a message naming what was rejected (FR-031, FR-033, FR-040, FR-054). Nothing is coerced: a non-boolean marking is not read as truthiness, an explicit `null` is not read as absence, a stored record whose new fields are unusable is not read as "unprotected". SR-020 requires failing closed when protection state cannot be determined. | PASS |
| **III. Every Requirement Is Testable** | All 25 new FRs and 8 new SRs are observable over HTTP or on disk. SC-021 already requires each to map to a test referencing it by id, and the 001 suite already contains the gate that enforces it. | PASS |
| **IV. Simplicity** | The feature is additive to an existing design: no new route, no new entity, no new module, no new configuration. The one genuinely new mechanism — an atomic claim on a one-time paste — is forced by SR-016 and FR-047, not speculative. | PASS |
| **V. Secure by Default (NON-NEGOTIABLE)** | The spec carries SR-013 … SR-020, derived from OWASP Top 10 / ASVS, each testable with negative tests. Both options are off by default and neither weakens any existing control; the protections need no operator configuration to be in force. | PASS |

**Security Baseline coverage** — note that two items change status relative to 001, because this
feature newly touches surfaces 001 explicitly did not:

| Baseline item | Status | Where |
|---|---|---|
| Untrusted input, allowlist-based, validated before any sink | Controlled | SR-018; R-22 (exact-type rules before the value reaches storage or the KDF), R-17 (stored records re-validated on load, not trusted) |
| No string-built sinks | Controlled, unchanged | Paths still built only from an allowlist-validated 22-char id; JSON still emitted via `json.dumps`. The password is never interpolated into a path, a query, or any structured output |
| Path containment | Controlled, unchanged | SR-003; R-07. `consume_record` resolves its path through the same `_record_path` guard |
| **Credential storage (slow salted hashes)** | **Now applicable — Controlled** *(was "not applicable, by deliberate narrowing" in 001)* | SR-013; R-16 (PBKDF2-HMAC-SHA-256, 600 000 iterations, 16-byte per-paste salt from `secrets`, 32-byte output), R-17 (storage shape). Plaintext never reaches disk, a response, or process output |
| Randomness and constant-time comparison | Controlled, extended | SR-014; R-18 — `hmac.compare_digest` over the two derived digests, never `==`, and never over raw passwords |
| Resource limits | Controlled, extended | SR-018; R-16 (O(1)-memory KDF chosen so the per-request envelope is unchanged), R-17 (`iterations` bounded even if a stored record claims otherwise), R-18 (an absent header costs no KDF run) |
| **Access control on every operation, server-side, atomic under concurrency** | **Controlled, materially extended** | SR-015 (verified against the stored record on every read, both forms, nothing cached — structural, since the service holds no cross-request state); SR-016 + R-20 (the `unlink` *is* the check-and-use pair, made atomic by the syscall rather than by convention) |
| File permissions | Controlled, unchanged | SR-008; R-03. The verifier is written into the same `0600` record by the same `os.open(..., 0o600)` path, with no permissive window |
| Output redaction | Controlled, extended | SR-019; R-18 (fixed refusal message, no echo of the supplied value, nothing about the stored one), R-23 (`protected` reports only *whether*) |

**Development Workflow gates**: the spec states functional and security requirements together
(satisfied); this plan shows per-requirement verification and the applicable Baseline items (see
*Requirement Verification Map*); tests ship with the implementation; the full suite must pass with
no skips or xfails, and SC-020 additionally forbids weakening any 001 test.

**Result**: no violations. Complexity Tracking records three retained non-trivial elements.

### Post-design re-check (after Phase 1) — PASS

Re-assessed against the artifacts actually produced (`research.md`, `data-model.md`,
`contracts/http-api.md`, `quickstart.md`).

| Principle | Post-design assessment | Verdict |
|---|---|---|
| **I. Standard Library Only** | The dependency list closed at fourteen stdlib modules — 001's thirteen plus `hashlib`. Phase 0 explicitly rejected `argon2-cffi` as third-party (R-16). No runtime dependency is added to packaging metadata, and no amendment is needed. | PASS |
| **II. Fail Loudly** | Every new rule in the data-model validation table maps to a specific status and message; none produces a default, a coercion, or a silent pass. Three places could have failed silently and deliberately do not: a malformed stored option is `404` rather than "assume off" (R-17, SR-020); an undecodable password header is `403` rather than "compare the mangled value" (R-19); a claim that fails for a reason other than the record already being gone propagates to a loud generic `500` rather than serving the content anyway (R-20, SR-020). No bare `except:` and no `except Exception: pass` appears in the design, and the existing suite enforces that by source scan. | PASS |
| **III. Every Requirement Is Testable** | R-26 extends the existing enforced gate to `FR-001 … FR-054` and `SR-001 … SR-020` by changing two `range()` bounds — the gate's regex already matches the new ids. The Requirement Verification Map below names the approach for all 25 FRs, 8 SRs, and 11 SCs. Two security properties get source-level assertions in addition to behavioural ones (no `==` on password material; `hmac.compare_digest` present), mirroring the SR-002 test that already exists. | PASS |
| **IV. Simplicity** | The design settled on: zero new modules, zero new routes, zero new CLI options, zero new locks, zero new files on disk, and one new store method. Six alternatives were rejected *specifically* for adding moving parts — scrypt's memory amplification (R-16), flat verifier keys and a PHC-style parser (R-17), rename-to-claim and a "consumed" flag (R-20), an attempt counter (R-25), a `passwords.py` module (R-24). The single new concurrency mechanism is a syscall, not machinery. | PASS |
| **V. Secure by Default (NON-NEGOTIABLE)** | All eight new SRs have a concrete mechanism and at least one negative test. Nothing requires operator action: both options are per-paste and off by default, the hashing parameters are constants with no knob, and the checks cannot be disabled. Three design choices exist *only* for security with no functional driver — the `iterations` upper bound on load (R-17), the 404-before-403 ordering that costs an extra branch to avoid an existence oracle (R-21), and the password-before-claim ordering that makes a one-time paste harder to destroy (R-21). | PASS |

**Design decisions that strengthened compliance during Phase 1**, each closing a hole the naive
implementation would have had:

1. **Malformed stored option ⇒ the paste does not exist** (R-17). The obvious reading of "absent
   means false" extends to "unparseable means false", which would serve a protected paste with no
   password check the moment a verifier was damaged. The asymmetry — absent means off, malformed
   means gone — is what SR-020 actually requires.
2. **An upper bound on the stored `iterations`** (R-17). Without it, the work a single read can
   provoke is set by a file rather than by the code, which is the SR-018 bound given away.
3. **`unlink` as the claim, content written only afterwards** (R-20). "Read, send, then delete" is
   the natural shape and it hands the content to every racing reader before the first delete
   lands. Deciding the winner with the syscall means no lock protocol has to be got right.
4. **Password check before the claim** (R-21). The reverse order would let anyone holding a link
   destroy a paste they cannot read — the spec calls the chosen order "the only safe order".
5. **`404` before `403` on reads** (R-21). Extends the precedence `delete_record` already applies
   so the service has one rule rather than two, and so a refusal never confirms an identifier is
   real (SC-016).
6. **Comparing derived digests, not passwords** (R-18). `compare_digest` over variable-length
   inputs leaks length; over two 32-byte digests it leaks nothing.
7. **Re-encoding the header latin-1 → UTF-8** (R-19). Without it, every non-ASCII password would
   silently fail to match what was stored — a correctness bug that would look like a security
   feature.

**Result**: no violations introduced by the design. Complexity Tracking below records the retained
non-trivial elements with their forcing requirements.

## Project Structure

### Documentation (this feature)

```text
specs/002-burn-and-password-pastes/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — decisions R-16 … R-26 with alternatives
├── data-model.md        # Phase 1 output — Paste and Paste store, as a delta on 001
├── quickstart.md        # Phase 1 output — 8 runnable validation scenarios
├── contracts/           # Phase 1 output
│   └── http-api.md      #   caller-facing HTTP delta (no new route; cli.md is unchanged)
├── checklists/
│   └── requirements.md  # Spec quality checklist (already complete)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

`contracts/cli.md` is **not** re-issued: this feature adds no command-line option, no flag, and no
change to startup, shutdown, or exit codes. [001's cli contract](../001-pastebin-service/contracts/cli.md)
continues to hold verbatim.

### Source Code (repository root)

Changed files are marked; no file is added to `src/`.

```text
src/
└── pastebin/
    ├── __init__.py          # unchanged
    ├── __main__.py          # unchanged
    ├── cli.py               # unchanged — no new option (spec Constraints)
    ├── server.py            # CHANGED: X-Paste-Password decoding; read-path ordering;
    │                        #          the two flags in the structured read
    ├── store.py             # CHANGED: new-key interpretation in _load; consume_record()
    └── models.py            # CHANGED: password/burn constants + messages; hash_password();
                             #          verify_password(); validation rules 11-13; rule 14 last

tests/
├── conftest.py              # CHANGED: password-header helpers; response scanner extended
│                            #          to passwords, salts, and stored hashes (SC-017)
├── test_create.py           # CHANGED: one key-set assertion (SC-020)
├── test_read.py             # CHANGED: one key-set assertion (SC-020)
├── test_persistence.py      # CHANGED: one key-set assertion (SC-020)
├── test_expiry.py           # unchanged
├── test_revoke.py           # unchanged
├── test_startup.py          # unchanged
├── test_routing.py          # unchanged
├── test_security.py         # unchanged
├── test_burn.py             # NEW: FR-030, FR-031, FR-044 … FR-049, SR-016, SR-017
├── test_password.py         # NEW: FR-032 … FR-035, FR-038, FR-040 … FR-043, FR-050,
│                            #      SR-013 … SR-015, SR-018, SR-019
├── test_compat.py           # NEW: FR-036, FR-037, FR-039, FR-051 … FR-054, SC-019, SC-020
└── test_requirement_coverage.py  # CHANGED: ranges extended to FR-054 / SR-020 (SC-021)

pyproject.toml               # unchanged — still ZERO runtime dependencies
```

**Structure Decision**: the 001 structure is kept exactly. The four runtime modules already split
along the only seams this feature touches — record shape and validation (`models`), durability
(`store`), HTTP (`server`) — so the feature lands as additions inside existing seams rather than
as new structure. A dedicated `passwords.py` or `auth.py` was rejected in R-24: roughly forty
lines of hashing and verification belong with the rest of the pure record logic in `models.py`,
which stays free of filesystem and socket access and therefore directly unit-testable. Tests
follow the existing one-file-per-requirement-cluster convention so a reviewer can still find a
requirement's test from the filename (Principle III's "discoverable" mapping).

## Requirement Verification Map

Constitution Development Workflow: *"Plans MUST show, per requirement, how it will be verified and
which Security Baseline items apply."* `R-nn` references are decisions in
[research.md](./research.md) (R-16 …) or in [001/research.md](../001-pastebin-service/research.md)
(R-01 … R-15). Every requirement of 001 remains in force and is verified by its existing tests,
which this feature does not modify except for the three key-set assertions SC-020 permits.

### Functional requirements

| Req | Verification approach | Test file | Design ref |
|---|---|---|---|
| FR-030 | Create with `true`, with `false`, and with the field absent; assert `201` in all three and that the absent and `false` cases read repeatedly while the `true` case does not | test_burn | R-22 |
| FR-031 | Table test over `"true"`, `"false"`, `0`, `1`, `-1`, `null`, `[]`, `{}`, `1.0`; assert `400` and a directory snapshot unchanged (nothing created) | test_burn | R-22 |
| FR-032 | Create with a 1-character and a 128-character password; assert `201`, and that reading each requires that password | test_password | R-22 |
| FR-033 | Table test over `""`, 129 chars, `null`, `5`, `true`, `[]`, `{}` → `400`; plus 128 **multi-byte** characters (512 UTF-8 bytes) → `201`, which is what proves the bound is counted in characters | test_password | R-22 |
| FR-034 | Round-trip passwords containing spaces, punctuation, emoji, combining marks, and non-ASCII; assert the identical value read back grants `200` in both read forms | test_password | R-19 |
| FR-035 | Assert the `201` body is exactly `{id, delete_token, url}` for every combination of the two options, and that the password does not appear anywhere in the response bytes | test_password, test_compat | R-23 |
| FR-036 | Submit an invalid new field together with 70 000 bytes of content; assert `400`, not `413`. Control: the same body with valid new fields → `413` | test_compat | R-22 |
| FR-037 | Assert both flags are present on every successful structured read, including a paste using neither option, and that `delete_token` is still absent | test_compat | R-23 |
| FR-038 | Assert `protected` is a bare boolean; scan the whole response (body + headers) for the password, the stored salt, the stored hash, and the string `pbkdf2` | test_password | R-23 |
| FR-039 | Assert the `/raw` body is byte-equal to the content for a protected one-time paste, and that no response header on that route carries either flag | test_compat | R-23 |
| FR-040 | For both read forms: no header, empty header, wrong case, trailing whitespace, truncated, and over-long values → `403`; correct value → `200` | test_password | R-18, R-19 |
| FR-041 | After each `403`, assert the body is exactly `{"error": "invalid paste password"}`, contains no substring of the content, and that a subsequent correct-password read still returns the full content | test_password | R-18 |
| FR-042 | Read an unprotected paste with a password header present (correct-looking and garbage); assert `200`, `protected: false`, and identical bytes to a read with no header | test_password | R-21 |
| FR-043 | Table over an unknown id, an expired paste, a revoked paste, and a consumed one-time paste × {no header, wrong password, correct password} → `404` in all twelve, never `403` | test_password, test_burn | R-21 |
| FR-044 | Read a one-time paste structured and (in a second case) raw; assert the response is byte-identical to the same read of an equivalent ordinary paste, then assert the record file is gone from the data directory | test_burn | R-20 |
| FR-045 | After the consuming read, assert `404` from the structured read, the raw read, and a `DELETE` with the correct token | test_burn | R-20 |
| FR-046 | Against one one-time paste: wrong-password read, missing-password read, unknown sub-resource, trailing slash, `PUT`/`PATCH`/`HEAD`, and a `DELETE` with a wrong token — then assert the paste still returns its content on its first successful read | test_burn | R-21 |
| FR-047 | N threads issuing the same read against one one-time paste; assert exactly one `200` with complete content, `N-1` `404`s, no `403`, no `500`, and no truncated body. Run for both read forms and for a mixed read/revocation race | test_burn | R-20 |
| FR-048 | Consume a one-time paste, restart the service against the same data directory, assert `404` from both read forms and from `DELETE` | test_compat | R-20 |
| FR-049 | A one-time paste with `expires_in: 1`, never read, past its expiry → `404`; and an unexpired one-time paste consumed normally | test_burn | R-08 |
| FR-050 | Revoke a protected paste with the token and **no** password header → `204`; with a correct password but a wrong token → `403`; with the password in place of the token → `403`. Assert the password never substitutes for and is never required alongside the token | test_password | R-21 |
| FR-051 | Hand-write a record carrying only the five original keys; assert it reads back with identical content and timestamps, needs no password, and reports both flags `false` | test_compat | R-17 |
| FR-052 | Create a one-time paste and a protected paste, restart, assert the first is still one-time, the second still requires the same password, and both original tokens still revoke | test_compat | R-17 |
| FR-053 | Create and read using neither field; assert status, headers, and body shape are byte-identical to the 001 expectations, apart from the two added flags. Backed by the unchanged 001 suite passing in full | test_compat | R-23 |
| FR-054 | Assert every error this feature can produce (`400` × 2 messages, `403`, `404`, `500`) parses as JSON with exactly the key `error` mapping to a non-empty, non-echoing message | test_password, test_burn | R-11 |

### Security requirements

| Req | Verification approach (incl. negative test) | Baseline item | Design ref |
|---|---|---|---|
| SR-013 | Read the record file off disk: assert the password plaintext appears nowhere under the data directory; assert `password.algorithm == "pbkdf2_sha256"`, `iterations == 600000`, `salt` is 32 hex chars and `hash` 64 hex chars. **Negative/discriminating**: two pastes created with the *same* password have different `salt` **and** different `hash`, which is what proves the salt is per-paste and random. Assert no reversible encoding (the hash is not a hex/base64 encoding of the password) | Credential storage | R-16, R-17 |
| SR-014 | Source scan: `hmac.compare_digest(` appears in the verification path, and no line in `src/pastebin/` compares anything matching `password`/`hash`/`digest` with `==` or `!=` (mirrors the existing SR-002 scan). Behavioural: a password differing only in its last character, and one that is a correct prefix of the stored password, are both rejected | Randomness/comparison | R-18 |
| SR-015 | Assert the check runs on **every** read: two successive correct reads both require the header, and a correct read followed by a header-less read of the same paste is `403`. Assert no cookie, `Set-Cookie`, session, `Authorization`, or other client-supplied claim influences the outcome, and that a correct read of paste A does not grant access to paste B | Access control | R-21 |
| SR-016 | The FR-047 concurrency test, plus a monkeypatched `consume_record` that fails *after* the liveness check: assert `500`, no content, and no second disclosure. Assert no concurrent read observes a partially written or partially removed record | Access control (atomicity) | R-20 |
| SR-017 | Table test: for a protected paste and for a consumed one-time paste, attempt `HEAD`, `PUT`, `PATCH`, `OPTIONS`, `/pastes/<id>/raw/`, `/pastes/<id>/anything`, a percent-encoded id (`%51nJ…`), a double-encoded id, a trailing-slash form, and `DELETE` — assert none returns content and none is `200` | Access control | R-07, R-12, R-21 |
| SR-018 | Assert an invalid-shape `password` is rejected before any hashing (patch `hash_password` to raise and assert the `400` still arrives); assert a stored record claiming `iterations: 10**12` is treated as unusable (`404`) rather than executed, with the response arriving promptly; assert a read with no password header performs no KDF run | Resource limits / untrusted input | R-16, R-17, R-18 |
| SR-019 | Extend the suite-wide `scan_response` so **every** response in the suite is checked for any password the suite has used, for any stored `salt` or `hash`, and for the strings `pbkdf2`/`iterations` — the same mechanism that already makes the `delete_token` guarantee suite-wide. Plus: assert the `403` message is a fixed constant that does not vary with the supplied value and does not reveal whether a password was supplied | Output redaction | R-18, R-23 |
| SR-020 | Plant records with a non-boolean `burn_after_reading`, a `password` that is a string, a list, an object with missing keys, a bad `algorithm`, a non-hex `salt`, and an out-of-range `iterations`; assert each reads `404` — never `200`, never served unprotected, never served twice. Plus the monkeypatched-`consume_record` failure from SR-016 asserting a generic `500` with no content and no diagnostics | Output redaction / fail closed | R-17, R-20 |

### Success criteria

| Criterion | Verification |
|---|---|
| SC-011 | FR-044/FR-045 tests, run in both orders (structured-then-raw and raw-then-structured) |
| SC-012 | FR-040/FR-041 tests, both read forms, asserting the paste survives every refusal |
| SC-013 | FR-034 round-trip including non-ASCII, in both read forms, asserting byte equality |
| SC-014 | FR-046 test — the full sequence of refused and unrouted requests, then one successful read |
| SC-015 | FR-047 concurrency test — exactly one `200`, no truncation, no status other than `200`/`404` |
| SC-016 | FR-043 twelve-case table — no input produces `403` for an identifier that does not resolve |
| SC-017 | SR-019 suite-wide scanner, plus the on-disk assertions from SR-013 |
| SC-018 | FR-048 and FR-052 restart tests |
| SC-019 | FR-051 legacy-record test |
| SC-020 | The 001 suite runs unchanged except for three key-set assertions; enforced by review of `git diff tests/` and by the whole suite passing with zero skips and zero xfails |
| SC-021 | `tests/test_requirement_coverage.py` with its ranges extended to `FR-001 … FR-054` and `SR-001 … SR-020` — fails and names the ids if any is unreferenced, or if a test references an id that is not a requirement |

## Complexity Tracking

> Principle IV requires any complexity that survives review to be justified against the
> requirement that forces it. 001's five entries still stand. Three new elements qualify; none is
> a constitution *violation*, but each is recorded because a simpler design exists and was
> rejected for a stated reason.

| Element | Why needed | Simpler alternative rejected because |
|---|---|---|
| A password verifier sub-object with algorithm and parameters recorded alongside the hash | SR-013 requires a salted hash from a deliberately slow algorithm at current parameters, and SR-018 requires the work a read can provoke to be bounded. Storing the parameters is what lets verification be checked against the record rather than assumed, and what lets an out-of-range `iterations` be rejected as unusable | Storing the raw digest alone was rejected: verification would then have to assume the parameters, so the day they change, every existing paste silently fails to verify with no way to tell that from a wrong password. Three flat keys were rejected in R-17 as three independently-absent values for one indivisible fact |
| `consume_record()` — a second destructive path through the store, taking the same lock as `delete_record()` | FR-044 and SR-016: the availability check and the destruction of a one-time paste must be atomic with respect to concurrent requests, and the content must not be returned to two callers | Reusing `delete_record` was rejected: it requires and compares a `delete_token`, which a reader does not have, so the reader would have to be handed the paste's own secret — exactly the disclosure FR-013 forbids. Deleting after sending the response was rejected because it hands the content to every racing reader before the first removal lands. A "consumed" flag was rejected in R-20: it leaves the content on disk, contradicting the spec's "destruction means removal" |
| ~0.2 s of PBKDF2 per read of a protected paste | SR-013's "deliberately slow" is the point of the control, not a side effect. The cost exists so that a stolen data directory does not yield the passwords | A fast hash was rejected as an SR-013 violation in plain terms. A cached verification result was rejected under SR-015 ("MUST NOT be cached across requests"). A lower iteration count was rejected as going below the published current parameters. scrypt at its own current parameters was rejected in R-16 for a different reason entirely — ~128 MiB per concurrent verification, with one thread per connection and no attempt throttling, is a self-inflicted denial of service and an SR-018 violation |

**Not complexity, recorded to pre-empt the question**:

- **The asymmetric treatment of stored options** (absent ⇒ off, malformed ⇒ the paste does not
  exist) looks like a special case but is the existing FR-024 rule applied to new fields, and the
  only alternative is fail-open, which SR-020 forbids outright.
- **No new lock.** One-time reads take the store's existing lock; the atomicity itself comes from
  `unlink`, not from the lock. R-09's rejection of a per-identifier lock registry stands.
- **No migration, no startup scan, no index.** Pre-feature records are valid records; nothing on
  disk is rewritten, and the directory is still never enumerated.
