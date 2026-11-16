---

description: "Task list for 002-burn-and-password-pastes"
---

# Tasks: Burn-After-Reading and Password-Protected Pastes

**Input**: Design documents from `/specs/002-burn-and-password-pastes/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/http-api.md](./contracts/http-api.md),
[quickstart.md](./quickstart.md)

**Tests**: **REQUIRED and included.** Constitution Principle III and Principle V make every
functional and security requirement a testable one with at least one automated `pytest` test, and
SC-021 turns that into an enforced gate. Tests are therefore written **before** the implementation
in each story phase.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths are given in every task

## Path Conventions

Single project, as established by `001-pastebin-service` and kept unchanged by this feature
(plan.md "Project Structure"): runtime code in `src/pastebin/`, tests in `tests/`, both at the
repository root. **No file is added to `src/`.** Three files are added to `tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the green baseline this feature must not break, and land the constants
every later task refers to.

- [ ] T001 Confirm the pre-feature baseline is green: from the repository root run `PYTHONPATH=src python3 -m pytest -q` and record the passing test count and zero skips/xfails in the task notes — this is the SC-020 reference point that every later run is compared against
- [ ] T002 Add the feature's constants and error messages to `src/pastebin/models.py` beside the existing limits and `MSG_*` block: `PASSWORD_MIN_CHARS = 1`, `PASSWORD_MAX_CHARS = 128`, `PBKDF2_ALGORITHM = "pbkdf2_sha256"`, `PBKDF2_ITERATIONS = 600_000`, `PBKDF2_SALT_BYTES = 16`, `PBKDF2_DKLEN = 32`, `PBKDF2_MAX_ITERATIONS = 10_000_000` (the stored-`iterations` upper bound, R-17/SR-018), `MSG_BURN_TYPE = "burn_after_reading must be true or false"`, `MSG_PASSWORD = "password must be a string of 1 to 128 characters"`, `MSG_BAD_PASSWORD = "invalid paste password"`. `MAX_BODY_BYTES` stays `66560` — unchanged (R-22)

**Checkpoint**: Constants exist; nothing observable has changed; the suite is still green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The record shape, the validator, the store primitives, the header decoder, and the
test harness that every user story below builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 Extend `validate_create_payload` in `src/pastebin/models.py` to return the 4-tuple `(content, expires_in, burn_after_reading, password)` and add validation rules 11-13 **after** the `expires_in` rules and **before** the content-size rule (R-22, data-model.md "Creation validation rules"): rule 11 — if `burn_after_reading` is present, `type(...) is bool` else `ValidationError(400, MSG_BURN_TYPE)`; rule 12 — if `password` is present, `type(...) is str` else `ValidationError(400, MSG_PASSWORD)`; rule 13 — if `password` is present, `1 <= len(password) <= 128` **characters** (`len()` on the `str`, never on its UTF-8 encoding) else `ValidationError(400, MSG_PASSWORD)`. Move the existing `len(content.encode("utf-8")) > MAX_CONTENT_BYTES → 413` rule to **last** so an invalid new field is `400` rather than `413` (FR-031, FR-033, FR-036). An explicit `null` for either field is rejected, never treated as absence. Keys other than `content`, `expires_in`, `burn_after_reading`, and `password` stay uninspected (FR-009)
- [ ] T004 Implement `hash_password(password: str) -> dict` in `src/pastebin/models.py` (add `import hashlib`): draw a salt with `secrets.token_bytes(PBKDF2_SALT_BYTES)`, derive with `hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=PBKDF2_DKLEN)`, and return exactly `{"algorithm": PBKDF2_ALGORITHM, "iterations": PBKDF2_ITERATIONS, "salt": salt.hex(), "hash": derived.hex()}` — 32 lowercase hex characters of salt, 64 of hash. The plaintext is never retained, logged, or returned (SR-013, R-16)
- [ ] T005 Implement `verify_password(verifier: dict, supplied: str) -> bool` in `src/pastebin/models.py`: re-derive with the verifier's stored `salt` (decoded via `bytes.fromhex`) and stored `iterations`, then compare the two 32-byte **derived digests** with `hmac.compare_digest` — never the raw passwords, never `==`/`!=` (add `import hmac`). Returns a bare `bool` (SR-014, R-18)
- [ ] T006 Implement the stored-record interpretation helpers in `src/pastebin/models.py` — a module-level sentinel `RECORD_UNUSABLE`, plus `stored_burn_flag(record)` and `stored_password_verifier(record)` — applying the data-model.md "Stored-record interpretation rules" verbatim: `burn_after_reading` absent ⇒ `False`; present and `type(...) is bool` ⇒ that value; anything else ⇒ `RECORD_UNUSABLE`. `password` absent or `None` ⇒ `None` (unprotected); a `dict` whose key set is **exactly** `{"algorithm", "iterations", "salt", "hash"}` with `algorithm == PBKDF2_ALGORITHM`, `type(iterations) is int` within `[1, PBKDF2_MAX_ITERATIONS]`, `salt` 32 lowercase hex characters and `hash` 64 lowercase hex characters ⇒ that verifier; anything else ⇒ `RECORD_UNUSABLE`. Use `type(...) is bool` / `type(...) is int`, never `isinstance` (R-10, R-17, FR-051, FR-052, SR-018, SR-020)
- [ ] T007 Apply those rules inside `PasteStore._load` in `src/pastebin/store.py`, after the existing `RECORD_FIELDS` check: if either helper returns `RECORD_UNUSABLE`, return `None` so the paste reports `404` exactly as any unparseable record already does. `RECORD_FIELDS` is **not** extended — the two keys stay optional, which is what keeps pre-feature records valid with no migration and no startup scan (FR-051, SR-020, R-17)
- [ ] T008 Add `consume_record(self, paste_id: str) -> bool` to `PasteStore` in `src/pastebin/store.py`: under the **existing** `self._lock` (the same one `delete_record` holds — no new lock, no per-identifier registry), resolve the path through `self._record_path`, return `False` if it is `None`, then `os.unlink(path)` returning `True`; return `False` on `FileNotFoundError`; let every other `OSError` propagate. The `unlink` **is** the atomic claim — of N concurrent callers exactly one gets `True` (FR-044, FR-047, SR-016, R-20)
- [ ] T009 Add `_paste_password(self) -> str | None` to `PastebinHandler` in `src/pastebin/server.py`: read `self.headers.get("X-Paste-Password")` (the first value when the header repeats), return `None` when absent or empty, otherwise recover the author's text with `value.encode("latin-1").decode("utf-8")`, returning `None` on `UnicodeEncodeError` or `UnicodeDecodeError` so an undecodable value is treated as a wrong password and never as a `500` (FR-034, FR-040, R-19)
- [ ] T010 Persist the two new keys in `PastebinHandler._handle_create` in `src/pastebin/server.py`: unpack the 4-tuple from `models.validate_create_payload`, add `"burn_after_reading": burn_after_reading or False` and `"password": models.hash_password(password) if password is not None else None` to the record dict passed to `write_record`. The `201` body stays **exactly** `{id, delete_token, url}` — no flag, no echo of the password (FR-030, FR-032, FR-035, SR-013)
- [ ] T011 Add password-aware request helpers to `tests/conftest.py`: a `password: str | None = None` keyword on `Service.request` and `Service.get` that attaches `X-Paste-Password` when given, and a `record_file(paste_id) -> dict` helper that reads and parses `<data_dir>/<id>.json` straight off disk so tests can assert on the stored verifier. `Service.create` already forwards `**extra` into the payload, so `password=` and `burn_after_reading=` need nothing further (R-26)
- [ ] T012 Extend `scan_response` in `tests/conftest.py` so the leakage guarantee is suite-wide (SR-019, SC-017): maintain a module-level `USED_PASSWORDS: set[str]` that tests register passwords in, and assert no response's headers or body ever contains any registered password, any stored `salt` or `hash` value read back off disk, or the strings `pbkdf2` / `iterations` — the same mechanism that already makes the `delete_token` guarantee suite-wide
- [ ] T013 Extend the coverage gate in `tests/test_requirement_coverage.py`: change `REQUIRED_IDS` to `[f"FR-{n:03d}" for n in range(1, 55)] + [f"SR-{n:03d}" for n in range(1, 21)]` and update the three docstrings to name `FR-001 … FR-054` and `SR-001 … SR-012` → `SR-020`. `ID_RE` already matches three-digit ids, so only the two `range()` bounds change (SC-021, R-26). **Expected transient state**: from here until Phase 6 completes, `test_SC_008_every_requirement_id_is_referenced_by_a_test` fails and names the ids still without tests — that is the gate working. Use `python3 -m pytest -q --deselect tests/test_requirement_coverage.py` at the intermediate checkpoints below, and the full command from Phase 7 onward

**Checkpoint**: Foundation ready. Validation, hashing, verification, record interpretation, the
atomic claim, the header decoder, and the test harness all exist. Creation already stores both
options; no read path has changed yet.

---

## Phase 3: User Story 1 - Share a snippet that destroys itself once read (Priority: P1) 🎯 MVP

**Goal**: `"burn_after_reading": true` makes a paste one-time — the first successful read of either
form returns it exactly as an ordinary paste and then destroys it; every later request is `404`.

**Independent Test**: Create a paste marked burn-after-reading, read it once and confirm the text
is returned exactly as for an ordinary paste, then read it again and confirm `404`. Repeat with
`/raw` for the single read. Fully testable with no password involved.

### Tests for User Story 1 ⚠️

> **Write these FIRST and confirm they FAIL before implementing T023-T025.** All live in
> `tests/test_burn.py`, so they are sequential with one another; they are parallel with the
> User Story 2 test tasks, which live in a different file.

- [ ] T014 [US1] Create `tests/test_burn.py` with the module docstring naming its requirement cluster, and the FR-030 tests: create with `true`, with `false`, and with the field absent — assert `201` for all three, that the `false` and absent cases read repeatedly and report `"burn_after_reading": false`, and that the `true` case reports `true` on its single read
- [ ] T015 [US1] Add the FR-031 table test to `tests/test_burn.py` over `"true"`, `"false"`, `0`, `1`, `-1`, `null`, `[]`, `{}`, `1.0` — assert `400` for each, the body is `{"error": "burn_after_reading must be true or false"}`, and a before/after `os.listdir` snapshot of the data directory is unchanged (nothing created)
- [ ] T016 [US1] Add the FR-044 / FR-045 tests to `tests/test_burn.py` (SC-011): a one-time paste read structured-first is byte-identical to the same read of an equivalent ordinary paste apart from the two flags, then the record file is gone from the data directory and the structured read, the raw read, and a `DELETE` with the **correct** token are all `404`; repeat with the raw read first, asserting the `/raw` body is byte-for-byte the content with no trailing newline
- [ ] T017 [US1] Add the FR-046 test to `tests/test_burn.py` (SC-014): against one one-time paste issue a `DELETE` with a wrong token (`403`), a `DELETE` with no token (`403`), `GET /pastes/<id>/other` (`404`), `GET /pastes/<id>/` (`404`), `GET /pastes/<id>/raw/` (`404`), and `PUT` / `PATCH` / `HEAD` on `/pastes/<id>` (`404`) — then assert the paste **still** returns its full content on its first successful read
- [ ] T018 [US1] Add the FR-049 test to `tests/test_burn.py`: a one-time paste created with `expires_in: 1`, never read, is `404` in both read forms once its expiry instant has passed; the control — an unexpired one-time paste — is consumed normally
- [ ] T019 [US1] Add the FR-047 / SR-016 concurrency tests to `tests/test_burn.py` (SC-015), modelled on the existing concurrent-revocation test: N (≥ 20) threads issuing the same read against one one-time paste — assert exactly one `200` carrying the complete, untruncated content, `N-1` `404`s, no `403` and no `500`; run it for the structured form, for the raw form, and for a mixed read/revocation race where the paste is gone afterwards either way and the content is returned at most once
- [ ] T020 [US1] Add the SR-017 bypass table to `tests/test_burn.py`: after a one-time paste has been consumed, assert `HEAD`, `PUT`, `PATCH`, `OPTIONS`, `DELETE` with the correct token, `/pastes/<id>/raw/`, `/pastes/<id>/anything`, a percent-encoded id, and a double-encoded id all return no content and none is `200`
- [ ] T021 [US1] Add the SR-020 fail-closed test to `tests/test_burn.py`: monkeypatch `server.store.consume_record` (reachable via the `Service.store` property) to raise `OSError` *after* the liveness check — assert the response is `500` with exactly `{"error": "internal error"}`, carries no content and no diagnostics, and that no second disclosure of the content ever occurs
- [ ] T022 [US1] Add the FR-054 error-body test to `tests/test_burn.py`: every error this story can produce (`400`, `404`, `500`) parses as JSON whose key set is exactly `{"error"}` mapping to a non-empty, non-echoing message

### Implementation for User Story 1

- [ ] T023 [US1] Rework `PastebinHandler._handle_read` in `src/pastebin/server.py` to the documented evaluation order (contracts/http-api.md "Read evaluation order", R-21): `read_record` → `404`; then, if `models.stored_burn_flag(record)` is true, `self._store.consume_record(paste_id)` → `404` when it returns `False` (another reader won the race, or it vanished); only then write the body. The body gains `"burn_after_reading"` (from the record) and `"protected"` (`record.get("password") is not None`), for a six-key response — `delete_token` is still absent (FR-037, FR-038, FR-044, FR-045, FR-047). An `OSError` out of `consume_record` propagates to the existing generic `500` path, never to a served body (SR-020)
- [ ] T024 [US1] Apply the same claim-before-serve order to `PastebinHandler._handle_raw` in `src/pastebin/server.py`: the content is read into memory **before** the claim and written to the socket **only after** it succeeds, so a losing racer discards its copy without writing a byte. The success response is otherwise completely unchanged — `200`, `text/plain; charset=utf-8`, `X-Content-Type-Options: nosniff`, body byte-for-byte the content, and **no** response header carrying either flag (FR-039, FR-044, FR-047, SR-016)
- [ ] T025 [US1] Update the three structured-read key-set assertions that SC-020 permits and no others — `tests/test_read.py:33`, `tests/test_create.py:101`, and `tests/test_persistence.py:33` — from `{"id", "content", "created_at", "expires_at"}` to `{"id", "content", "created_at", "expires_at", "burn_after_reading", "protected"}`. No test is deleted, weakened, skipped, or marked `xfail`

**Checkpoint**: User Story 1 is fully functional and independently testable. Run
`PYTHONPATH=src python3 -m pytest -q --deselect tests/test_requirement_coverage.py` — the whole
001 suite plus `tests/test_burn.py` must be green. Quickstart Scenarios 1, 2, and 6 now pass.

---

## Phase 4: User Story 2 - Protect a snippet with a password (Priority: P2)

**Goal**: `"password": "…"` protects a paste — reading it in either form requires the
`X-Paste-Password` header holding exactly that password; a missing or wrong password is `403`.
Revocation still needs only the delete token.

**Independent Test**: Create a paste with a password; confirm reading it without a password and
with a wrong password are both refused while the paste stays readable; confirm the correct password
returns the exact text in both read forms; confirm revocation works with the token alone. Fully
testable with no burn-after-reading paste involved.

### Tests for User Story 2 ⚠️

> **Write these FIRST and confirm they FAIL before implementing T037-T038.** All live in
> `tests/test_password.py`, so they are sequential with one another; they are parallel with the
> User Story 1 test tasks in `tests/test_burn.py`.

- [ ] T026 [US2] Create `tests/test_password.py` with the module docstring naming its requirement cluster, and the FR-032 tests: create with a 1-character password and with a 128-character password — assert `201` for both and that reading each requires exactly that password
- [ ] T027 [US2] Add the FR-033 table test to `tests/test_password.py` over `""`, 129 characters, `null`, `5`, `true`, `[]`, `{}` — assert `400` with `{"error": "password must be a string of 1 to 128 characters"}` and nothing created; then the discriminating case: **128 multi-byte characters** (e.g. 128 × `"🔑"`, 512 UTF-8 bytes) is `201`, which is what proves the bound is counted in characters and not in encoded bytes
- [ ] T028 [US2] Add the FR-034 round-trip test to `tests/test_password.py` (SC-013): passwords containing spaces, punctuation, emoji, combining marks, and non-ASCII letters each grant `200` when the identical value is supplied, in **both** read forms, with the returned content byte-equal to what was submitted
- [ ] T029 [US2] Add the FR-040 refusal table to `tests/test_password.py`: for both read forms, a missing header, an empty header value, a wrong-case value, a value with trailing whitespace, a truncated value, a correct-prefix value, and an over-long value are each `403`; the correct value is `200`
- [ ] T030 [US2] Add the FR-041 test to `tests/test_password.py` (SC-012): after each `403`, the body is exactly `{"error": "invalid paste password"}`, contains no substring of the content, and the paste still returns its full content to a subsequent correct-password read in either form
- [ ] T031 [US2] Add the FR-042 test to `tests/test_password.py`: reading an **unprotected** paste with a password header present — both a plausible value and garbage — returns `200` with `"protected": false` and bytes identical to a read with no header at all
- [ ] T032 [US2] Add the FR-050 test to `tests/test_password.py`: revoking a protected paste with the correct token and **no** password header is `204`, and later reads are `404`; a correct password with a wrong token is `403`; the password supplied in place of the token is `403`. The password never substitutes for the token and is never required alongside it
- [ ] T033 [US2] Add the FR-035 / FR-038 / SR-013 storage tests to `tests/test_password.py` (SC-017): the `201` body is exactly `{id, delete_token, url}` for every combination of the two options and contains no trace of the password; reading the record file off disk via the `record_file` helper asserts `password.algorithm == "pbkdf2_sha256"`, `iterations == 600000`, `salt` is 32 hex characters, `hash` is 64 hex characters, and the plaintext appears nowhere under the data directory; `protected` in the structured read is a bare boolean. **Discriminating case**: two pastes created with the *same* password have different `salt` **and** different `hash`, and the hash is not any hex or base64 encoding of the password
- [ ] T034 [US2] Add the SR-014 tests to `tests/test_password.py`, modelled on the existing `test_SR_002_implementation_uses_hmac_compare_digest` source scan: assert `hmac.compare_digest(` appears in the verification path of `src/pastebin/models.py`, and that no line under `src/pastebin/` compares an expression matching `password` / `hash` / `digest` with `==` or `!=`. Behavioural companion: a password differing only in its final character, and a password that is a correct prefix of the stored one, are both `403`
- [ ] T035 [US2] Add the SR-015 tests to `tests/test_password.py`: two successive correct reads of the same paste each require the header, and a correct read followed by a header-less read of that same paste is `403` — nothing is cached; no `Set-Cookie` is ever sent and no cookie, session, or `Authorization` header changes any outcome; a correct read of paste A grants no access to paste B
- [ ] T036 [US2] Add the SR-018 / SR-019 tests to `tests/test_password.py`: monkeypatch `models.hash_password` to raise and assert an invalid-shape `password` still returns `400`, proving validation precedes hashing; a read with **no** password header performs no KDF run (monkeypatch `models.verify_password` to raise and assert the `403` still arrives); the `403` message is a fixed constant that does not vary with the supplied value and does not reveal whether a password was supplied; and no response contains the password, the stored salt or hash, or the strings `pbkdf2` / `iterations`

### Implementation for User Story 2

- [ ] T037 [US2] Add the password gate to `PastebinHandler._handle_read` in `src/pastebin/server.py`, **after** the `404` checks and **before** the burn claim: if `record.get("password") is not None`, read the supplied value with `self._paste_password()` and respond `403` with `models.MSG_BAD_PASSWORD` when it is `None` (absent, empty, or undecodable — no KDF run) or when `models.verify_password(verifier, supplied)` is false. Nothing before the `200` discloses any part of the content or its length (FR-040, FR-041, SR-015, SR-019)
- [ ] T038 [US2] Add the identical gate, in the identical position, to `PastebinHandler._handle_raw` in `src/pastebin/server.py` — the check runs server-side on **every** read in **both** forms, with the failure body staying JSON (`{"error": …}`) even though the success body is plain text (FR-040, SR-015)

**Checkpoint**: User Stories 1 AND 2 both work independently. Run
`PYTHONPATH=src python3 -m pytest -q --deselect tests/test_requirement_coverage.py` — green.
Quickstart Scenarios 3, 5, and 8 now pass.

---

## Phase 5: User Story 3 - Combine the two, and keep non-existence private (Priority: P3)

**Goal**: The two protections compose in the only safe order — a reader who cannot prove they hold
the password never consumes the single read — and an unknown, expired, revoked, or already-consumed
identifier is `404` whatever password is supplied, never `403`.

**Independent Test**: Create a paste that is both one-time and protected; confirm a wrong-password
read is refused and the paste survives, then a correct-password read returns it and destroys it.
Separately confirm an identifier that was never issued, and an expired one, are `404` rather than
`403`, whatever password is supplied.

### Tests for User Story 3 ⚠️

- [ ] T039 [P] [US3] Add the FR-043 twelve-case table to `tests/test_password.py` (SC-016): {an identifier that was never issued, an expired protected paste, a revoked protected paste, a consumed one-time protected paste} × {no header, wrong password, correct password} — assert `404` in all twelve and `403` in none, so no response lets a caller tell a real identifier from an invented one
- [ ] T040 [P] [US3] Add the combined-paste tests to `tests/test_burn.py`: a paste created with **both** options returns `403` for a no-password read and for a wrong-password read and is **still readable** afterwards by a holder of the password; the correct-password read then returns the content with both flags `true` in the structured form; and every later request in either form — including one supplying the correct password — is `404`. Run the sequence once with the structured read as the consuming one and once with the raw read
- [ ] T041 [P] [US3] Add the combined SR-015 / SR-017 table to `tests/test_password.py`: for a paste that is both one-time and protected, assert that `HEAD`, `PUT`, `PATCH`, `OPTIONS`, `DELETE`, `/pastes/<id>/raw/`, `/pastes/<id>/anything`, a percent-encoded id, and a double-encoded id return no content, are never `200`, and — critically — never consume it; the paste still reads once afterwards with its password

### Implementation for User Story 3

- [ ] T042 [US3] Factor the shared prelude of `_handle_read` and `_handle_raw` in `src/pastebin/server.py` into one helper — `_resolve_read(self, paste_id) -> dict | None` — that performs steps 1-5 of the normative order in exactly one place (`404` unknown/unusable/expired → `403` password → claim → `404` on a lost claim), sending the error response itself and returning `None` when it did. Both handlers then call it and differ only in how they render the record. The order is defined once, so the two routes cannot drift (R-21, FR-043, FR-046, SR-015, SR-017)

**Checkpoint**: All three behavioural stories work and compose. Run
`PYTHONPATH=src python3 -m pytest -q --deselect tests/test_requirement_coverage.py` — green.
Quickstart Scenario 4 now passes.

---

## Phase 6: User Story 4 - Existing snippets and existing clients keep working (Priority: P4)

**Goal**: Records written before this feature read back identically and report both flags `false`;
both options survive a restart; a client using neither new field sees no change beyond the two
added flags.

**Independent Test**: Hand-write record files carrying only the five original keys, restart against
the same data directory, and confirm every one reads back with identical text and timestamps,
reports both flags `false`, and is still revocable with its original token.

### Tests for User Story 4 ⚠️

> All live in `tests/test_compat.py`, so they are sequential with one another.

- [ ] T043 [US4] Create `tests/test_compat.py` with the module docstring naming its requirement cluster, and the FR-037 tests: `burn_after_reading` and `protected` are present on **every** successful structured read — including a paste created with neither option, where both are `false` — both are bare booleans, and `delete_token` is still absent from the body and from every response header
- [ ] T044 [US4] Add the FR-039 tests to `tests/test_compat.py`: for a paste that is both protected and one-time, the `/raw` success body is byte-equal to the submitted content with nothing added, and no response header on that route carries either flag; the header set is identical to the 001 expectation (`Content-Type: text/plain; charset=utf-8`, `X-Content-Type-Options: nosniff`)
- [ ] T045 [US4] Add the FR-036 precedence tests to `tests/test_compat.py`: a submission carrying an invalid new field **and** 70 000 bytes of content is `400`, not `413`; the control — the same body with valid new fields — is `413`; and a declared `Content-Length` over 66 560 is still `413` with the body unread
- [ ] T046 [US4] Add the FR-051 legacy-record test to `tests/test_compat.py` (SC-019): hand-write a record file carrying only `id`, `content`, `created_at`, `expires_at`, and `delete_token` (mode `0600`, a valid 22-character id), then assert it reads back with identical content, `created_at`, and `expires_at`, requires no password, reports both flags `false`, serves its `/raw` form, and is still revocable with its original token
- [ ] T047 [US4] Add the FR-052 restart test to `tests/test_compat.py` (SC-018): create a one-time paste and a protected paste, call `Service.restart()`, then assert the first is still one-time (reads once, then `404`), the second still requires the same password (`403` without it, `200` with it), and both original delete tokens still revoke
- [ ] T048 [US4] Add the FR-048 durability test to `tests/test_compat.py` (SC-018): consume a one-time paste, `Service.restart()`, then assert `404` from the structured read, the raw read, and a `DELETE` with the correct token
- [ ] T049 [US4] Add the FR-053 test to `tests/test_compat.py`: a create-and-read cycle using neither new field and no password header produces statuses, headers, and body shapes identical to the 001 expectations — the only difference anywhere is the two added flags in the structured read. Back it with an explicit assertion that the `201` key set, the `/raw` header set, the `204` revocation, and every error message are unchanged
- [ ] T050 [US4] Add the SR-020 planted-record table to `tests/test_compat.py`: write records by hand whose `burn_after_reading` is `"true"` / `0` / `null` / `[]`, and whose `password` is a string, a list, an object missing a key, an object with an extra key, an object with `algorithm: "md5"`, a non-hex `salt`, a short `hash`, and `iterations: 10**12` — assert each is `404` from both read forms (never `200`, never served unprotected, never served twice), and that the `iterations: 10**12` case responds promptly rather than executing the KDF

**Checkpoint**: All four user stories are independently functional. The whole suite — including
`tests/test_requirement_coverage.py` with its extended ranges — must now be green.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T051 [P] Update `README.md`: add `burn_after_reading` and `password` to the `POST /pastes` field description, add `X-Paste-Password` to the Routes table rows for both `GET` endpoints, update the structured-read key list on line 47 to the six fields, add `403` to the status column for the `GET` rows, and extend the storage-and-security notes with the PBKDF2 verifier and the single-read destruction. The README must not document a password-change or recovery operation — neither exists
- [ ] T052 Run the full suite from the repository root: `PYTHONPATH=src python3 -m pytest -q` — it MUST pass with **zero** failures, zero skips, and zero `xfail`s (Constitution, Development Workflow). Compare the passing count against the T001 baseline and account for every added test
- [ ] T053 Confirm the SC-021 gate is green on its own: `PYTHONPATH=src python3 -m pytest -q tests/test_requirement_coverage.py` — every `FR-001 … FR-054` and `SR-001 … SR-020` is referenced by at least one test by id, and no test references an id that is not a requirement
- [ ] T054 Run all 8 scenarios in [quickstart.md](./quickstart.md) manually against a real server started with `PYTHONPATH=src python3 -m pastebin serve --port 8080 --data "$DATA"`, and confirm each behaves exactly as stated — including Scenario 8's `grep -ril 'hunter2' "$DATA"` printing nothing
- [ ] T055 SC-020 review: run `git diff tests/` and confirm the **only** changes to the 001 suite are the three key-set assertions from T025 plus the additive helpers in `tests/conftest.py` and the two `range()` bounds in `tests/test_requirement_coverage.py`. No existing test is deleted, weakened, skipped, or marked expected-to-fail
- [ ] T056 [P] Principle I check: confirm `pyproject.toml` still declares **zero** runtime dependencies, and that the only module added to the runtime import set across `src/pastebin/` is `hashlib` (`hmac` and `secrets` were already in use)
- [ ] T057 Principle II / IV review of `src/pastebin/`: confirm no bare `except:` and no `except Exception: pass` was introduced, that every new rejection names what was rejected without echoing it, and that the feature added zero new modules, routes, CLI options, locks, and on-disk files — as Complexity Tracking in [plan.md](./plan.md) records

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Setup — **BLOCKS all four user stories**
- **User Story 1 (Phase 3)**: depends on Foundational only
- **User Story 2 (Phase 4)**: depends on Foundational only — independent of US1
- **User Story 3 (Phase 5)**: depends on US1 **and** US2 — it is a composition story with no value until both exist (spec: "Why this priority")
- **User Story 4 (Phase 6)**: depends on Foundational; its FR-037/FR-039 tests additionally need US1's T023/T024, and FR-052 needs US2's gate. Run it last
- **Polish (Phase 7)**: depends on all four stories

### User Story Dependencies

- **US1 (P1)**: no dependency on any other story. Ships as the MVP on its own
- **US2 (P2)**: no dependency on US1. The two stories touch the same two handler methods, so if they are worked in parallel, T037/T038 merge into T023/T024's result
- **US3 (P3)**: requires US1 + US2
- **US4 (P4)**: requires US1 (for the flags) and US2 (for the restart assertions)

### Within Each User Story

- Tests are written and MUST FAIL before the implementation tasks in the same phase
- Store primitives before server handlers; server handlers before the cross-cutting refactor
- A story is complete — and its checkpoint run green — before the next priority begins

### Parallel Opportunities

- **T003-T010 are strictly sequential**: T004→T005 (verify needs the hash shape), T006→T007 (the store applies the model's rules), T003/T004/T005/T006 all edit `src/pastebin/models.py`, T007/T008 both edit `src/pastebin/store.py`, T009/T010 both edit `src/pastebin/server.py`
- **T011-T013 can run in parallel with T003-T010** (different files: `tests/conftest.py`, `tests/test_requirement_coverage.py`) — though T011/T012 are sequential with each other
- **The US1 and US2 test blocks are fully parallel with each other**: T014-T022 only touch `tests/test_burn.py`, T026-T036 only touch `tests/test_password.py`
- **T039, T040, T041 are parallel** — the first and third are in `tests/test_password.py`, the second in `tests/test_burn.py`. (T039 and T041 are sequential with each other.)
- **T051 and T056 are parallel** with the verification tasks — they touch `README.md` and `pyproject.toml`, which no test task reads
- Within any one test module, tasks are sequential: they append to the same file

---

## Parallel Example: User Stories 1 and 2

```bash
# Once Phase 2 is complete, two developers can work the P1 and P2 test suites at once:
Developer A: T014 … T022  →  tests/test_burn.py       (burn-after-reading)
Developer B: T026 … T036  →  tests/test_password.py   (password protection)

# And within Phase 5, three test tasks run together:
Task: "FR-043 twelve-case table in tests/test_password.py"      (T039)
Task: "Combined burn+password sequence in tests/test_burn.py"   (T040)
Task: "Combined SR-015/SR-017 table in tests/test_password.py"  (T041)   # after T039
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T013) — **CRITICAL, blocks everything**
3. Complete Phase 3: User Story 1 (T014-T025)
4. **STOP and VALIDATE**: `PYTHONPATH=src python3 -m pytest -q --deselect tests/test_requirement_coverage.py`, plus quickstart Scenarios 1, 2, and 6
5. At this point burn-after-reading ships and every 001 behaviour is intact. Password support is accepted at creation and stored, but no read requires it yet — so **do not deploy this increment as if `password` worked**; it is an MVP checkpoint, not a release boundary

### Incremental Delivery

1. Setup + Foundational → foundation ready, nothing observable changed
2. + US1 → one-time pastes work end to end (MVP checkpoint)
3. + US2 → password protection works end to end; both options usable independently
4. + US3 → the two compose safely and non-existence stays private — **the first releasable point**, because FR-043's precedence and FR-046's "a refused read never consumes" are security properties, not polish
5. + US4 → compatibility and durability proven; the SC-021 gate goes green
6. + Polish → full suite, quickstart, and the SC-020 diff review

### Parallel Team Strategy

1. One developer completes Setup + Foundational alone — every later task depends on it and it is almost entirely one file at a time
2. Then: Developer A takes US1, Developer B takes US2. Their test files are disjoint; they coordinate on `src/pastebin/server.py`, where T023/T024 and T037/T038 touch the same two methods
3. US3 and US4 are picked up by whoever finishes first, once both US1 and US2 have landed

---

## Notes

- `[P]` means different files and no dependency on an incomplete task
- Tests are **not** optional here: Principle III, Principle V, and the enforced SC-021 gate make a
  requirement with no test an unimplemented requirement
- The test suite spends roughly ten seconds inside PBKDF2 at the shipped 600 000 iterations. The
  iteration count is **not** lowered for tests — the configuration under test is the one that ships
  (R-16, R-26)
- Commit after each task or logical group; the full suite must pass before any merge
- Nothing in this feature adds a module, a route, a CLI option, a lock, or a file on disk
