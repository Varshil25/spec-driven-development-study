---

description: "Task list for implementing burn-after-reading and password protection"
---

# Tasks: Burn After Reading and Password Protection

**Input**: Design documents from `/specs/002-burn-after-reading-password/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/http-api.md](./contracts/http-api.md), [quickstart.md](./quickstart.md)

**Tests**: Test tasks are **included and mandatory**. Constitution v1.0.0 Principle III
(NON-NEGOTIABLE) requires every functional requirement to map to at least one automated `pytest`
test whose name carries the requirement id, and SC-016 restates it. The traceability table in
[quickstart.md](./quickstart.md) is the contract these test tasks must satisfy.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and
delivered independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Every description carries the exact file path it touches

## Path Conventions

Single-package project, paths relative to the repository root `/root/sdd-study/runs/R037`:

- Runtime: `src/pastebin/` — only `storage.py` and `server.py` change; `cli.py`, `__main__.py`,
  `__init__.py` are untouched
- Tests: `tests/` — `conftest.py` gains additive helpers; `tests/test_burn.py`,
  `tests/test_password.py`, `tests/test_compat.py` are new; **no pre-existing test module is
  edited** (SC-017)

**Critical ordering rule that pervades these tasks** (contracts/http-api.md "Ordering rule"):
both read routes resolve a request as `1. id/existence/expiry → 404`, `2. password → 403`,
`3. one-time claim → 404 if lost`, `4. serve 200`. Tasks are sequenced so that step 3 is built in
US1, step 2 is inserted *before* it in US2, and step 1 is the already-existing behaviour.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Record the baseline the whole feature is measured against. No scaffolding is needed —
the project, its layout, and its tooling already exist and no dependency is added (Constitution I).

- [ ] T001 Record the pre-change baseline by running `python3 -m pytest` from the repository root and saving the pass count; this is the "existing suite passes unmodified" reference for SC-017/FR-060 and must stay green after every later task (covers `tests/test_create.py`, `tests/test_read.py`, `tests/test_delete.py`, `tests/test_expiry.py`, `tests/test_routing.py`, `tests/test_storage.py`, `tests/test_cli.py`)
- [ ] T002 Create the three new test modules `tests/test_burn.py`, `tests/test_password.py`, and `tests/test_compat.py`, each with a module docstring naming the requirements it owns per the traceability table in `specs/002-burn-after-reading-password/quickstart.md` (test_burn: FR-033/034, FR-047…FR-053, SC-011, SC-012; test_password: FR-035/036, FR-040…FR-046, SC-013, SC-014, SC-019, SC-020; test_compat: FR-037/038/039, FR-054…FR-059, SC-015, SC-017, SC-018, SC-021)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The storage layer and the test helpers both user stories stand on. The record format,
the `Paste` fields, the password hashing primitives, and the atomic claim are shared by US1 and US2,
so they are built once here.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 Add `import hashlib` and the new module constants to `src/pastebin/storage.py` next to the existing `RECORD_VERSION` / `CONTENT_MAX_BYTES` block: `PASSWORD_SALT_BYTES = 16` (per R-016: "a per-paste 16-byte random salt"), `PBKDF2_ITERATIONS = 200_000`, `PBKDF2_HASH = "sha256"`, `PASSWORD_MIN_CHARS = 1` and `PASSWORD_MAX_CHARS = 128` (V-13: `1 <= len(password) <= 128`, **counted in characters**, boundaries inclusive — 1 and 128 pass, 0 and 129 fail). Keep `RECORD_VERSION = 1` unchanged (R-017) and add a comment saying why bumping it would break FR-058
- [ ] T004 Extend the frozen `Paste` dataclass in `src/pastebin/storage.py` with three fields, each defaulted so every existing positional construction keeps working: `burn_after_reading: bool = False` ("whether the first successful read destroys the paste; `False` for a paste created without the option and for every record written by the previous version"), `password_salt: "str | None" = None` ("hex-encoded 16 random bytes, or `None` when the paste is unprotected" — 32 hex chars), `password_hash: "str | None" = None` ("hex-encoded PBKDF2-HMAC-SHA256 derivation … or `None` when unprotected" — 64 hex chars). Docstring must state that the plaintext password is never a field of `Paste` (FR-046, S-11)
- [ ] T005 Add `hash_password(password)` to `src/pastebin/storage.py` returning `(salt_hex, hash_hex)` from `secrets.token_bytes(PASSWORD_SALT_BYTES)` and `hashlib.pbkdf2_hmac(PBKDF2_HASH, password.encode("utf-8"), salt, PBKDF2_ITERATIONS)`, both `.hex()`-encoded (R-016)
- [ ] T006 Add `password_matches(paste, supplied)` to `src/pastebin/storage.py`, mirroring the existing `token_matches` idiom: coerce a non-`str` `supplied` to `""`, derive with the paste's `password_salt`, and compare the derived hex to `paste.password_hash` with `secrets.compare_digest` so nothing leaks through response timing (FR-043, V-16). Comparison is exact — no case folding, trimming, or Unicode normalisation (spec assumption)
- [ ] T007 Extend `create_paste` in `src/pastebin/storage.py` to `create_paste(data_dir, content, expires_in=None, burn_after_reading=False, password=None)`: derive salt/hash via `hash_password` when `password is not None` (else both `None`), build the `Paste` with the three new fields, and write `burn_after_reading`, `password_salt`, and `password_hash` **unconditionally** into the record alongside the existing keys, keeping `"version": RECORD_VERSION` at `1` (R-017, FR-057)
- [ ] T008 Extend `_read_paste` in `src/pastebin/storage.py` to validate the three new keys as **optional on read**: absent `burn_after_reading` → `False`, present-but-not-a-`bool` → `_BadRecord`; absent or `null` `password_salt`/`password_hash` → `None`, present-but-not-a-hex-`str` → `_BadRecord`; and enforce invariant S-10 — both password fields `null` or both well-formed, one without the other is `_BadRecord`. A malformed new key is reported on stderr and the record skipped, never coerced to a default (Constitution II, FR-058, data-model §3)
- [ ] T009 Add `consume_paste(data_dir, paste_id)` to `src/pastebin/storage.py`: `os.unlink(record_path(data_dir, paste_id))` returning `True`, `FileNotFoundError` returning `False`, every other `OSError` propagating. Docstring must record that POSIX guarantees exactly one concurrent caller wins, that this is the whole mutual-exclusion mechanism (no lock, no index, no tombstone — invariants S-8, S-9), and that it must be called only after the content is already in memory (S-12) and only after the password check (FR-050)
- [ ] T010 [P] Extend the `ServiceClient` helpers in `tests/conftest.py` additively: `read(paste_id, password=None)` and `read_raw(paste_id, password=None)` sending `X-Paste-Password` only when `password is not None`, plus a way to send the header more than once and to send it empty (FR-041 cases); keep every existing call signature working so no pre-existing test changes behaviour (SC-017)
- [ ] T011 Add a `write_legacy_record(data_dir, paste_id, content, created_at, expires_at, delete_token)` helper to `tests/conftest.py` that writes the exact previous-version record shape — `version`, `id`, `content`, `created_at`, `expires_at`, `delete_token` and **none** of the three new keys — directly into a data directory, as pinned in `specs/002-burn-after-reading-password/data-model.md` §3 (needed by FR-058/SC-017)

**Checkpoint**: `python3 -m pytest` is still green (storage changes are additive and defaulted), the
record format accepts old and new records, and both user stories can now proceed in parallel.

---

## Phase 3: User Story 1 - Share a snippet that destroys itself once read (Priority: P1) 🎯 MVP

**Goal**: `"burn_after_reading": true` at creation makes a paste one-time — the first successful
read on either read route serves it exactly as an ordinary paste and destroys it, so every later
read or delete is `404`. The structured read reports the flag.

**Independent Test**: Create a paste with `burn_after_reading: true`, read it once through
`GET /pastes/<id>` and (on a second paste) once through `GET /pastes/<id>/raw`, confirm content and
metadata are identical to an ordinary paste, and confirm every later read of either form is `404`
with a JSON `error` body. Needs nothing from US2.

### Tests for User Story 1

> Write these first and confirm they FAIL before the implementation tasks below.

- [ ] T012 [US1] In `tests/test_burn.py`, add creation-option tests: `burn_after_reading` absent behaves exactly as `false` and explicit `false` is indistinguishable from absent (FR-033), and each invalid shape — a string including `"true"`/`"false"`, a number including `1`/`0`/`1.0`, `null`, an array, an object — is `400` with a JSON `{"error": ...}` body naming the field, with nothing written to the data directory (FR-034, V-11, SC-015)
- [ ] T013 [US1] In `tests/test_burn.py`, add the single-read tests: the first read on `GET /pastes/<id>` returns `200` with the exact content and metadata, and the first read on `GET /pastes/<id>/raw` returns the content byte-for-byte with `Content-Type: text/plain; charset=utf-8` and no extra fields (FR-047, FR-056); after one read of either route, both read routes **and** a delete presenting the original token answer `404` (FR-048); a paste consumed on the raw route is `404` on the JSON route and vice versa; a non-burn paste reads repeatedly on both routes (FR-051); and the read-twice-per-route sweep of SC-011
- [ ] T014 [US1] In `tests/test_burn.py`, add the non-consumption and precedence tests: an ill-shaped identifier `404` and (for a paste that is both one-time and protected, after US2 lands) a wrong-password `403` leave the one read available (FR-050); the SC-019 sweep of 20 wrong-password attempts followed by one correct read then a `404`; an expired one-time paste answers `404` on both routes and is never treated as having been read (FR-052); delete-before-read with the correct token answers `204` and every later read is `404`, while a missing or wrong token on an unread one-time paste answers `403` and leaves it readable (FR-053)
- [ ] T015 [US1] In `tests/test_burn.py`, add the concurrency test for FR-049/SC-012 using `concurrent.futures.ThreadPoolExecutor` against the `service` fixture: 200 one-time pastes × 10 simultaneous reads each, asserting exactly one `200` and nine `404` per paste, that the single served body is the complete original content (no partial or corrupt content), and that no paste is lost without being served
- [ ] T016 [US1] In `tests/test_burn.py`, add the restart-durability test for Story 1 scenario 12 using the `in_process_factory` fixture over one data directory (plus one end-to-end `launch` stop-and-start): a one-time paste created before the restart is still consumed by exactly one read afterwards (FR-057, part of SC-018)

### Implementation for User Story 1

- [ ] T017 [US1] In `src/pastebin/server.py`, add `_parse_burn_after_reading(parsed)` and call it from `_parse_create` **after** the existing V-1…V-7 checks so no existing rejection's status changes (V-14, FR-039, R-019): absent → `False`; otherwise the check is `isinstance(value, bool)` — because `isinstance(True, int)` is `True` in Python, numbers must never pass it (FR-034, spec edge case "numbers are not booleans") — and a failure raises `_Rejected(400, 'field "burn_after_reading" must be a boolean, got <json type>')` using the existing `_json_type` helper (FR-059)
- [ ] T018 [US1] In `src/pastebin/server.py`, thread the parsed flag through `_parse_create`'s return value and `_create` into `storage.create_paste(..., burn_after_reading=...)`, leaving the `201` body exactly `id`, `delete_token`, `url` with no new field and no echo of either option (FR-037)
- [ ] T019 [US1] In `src/pastebin/server.py` `_read_json`, add `"burn_after_reading": paste.burn_after_reading` and `"protected": paste.password_hash is not None` to the `200` body, each exactly `true` or `false` — never absent, never `null` — alongside the unchanged `id`, `content`, `created_at`, `expires_at`, and still no `delete_token` (FR-054, FR-055, FR-003). `_read_raw` gains nothing (FR-056)
- [ ] T020 [US1] In `src/pastebin/server.py`, add a single `_load_for_read(paste_id)` helper used by **both** `_read_json` and `_read_raw`: load via the existing `_load` (`404` on allow-list/existence/expiry), then — for a paste with `burn_after_reading` true — claim it with `storage.consume_paste`, answering `404` ("paste not found") when the claim is lost, and return the in-memory `Paste` for serving. The claim must run after the content is in memory and before any byte of the response is written (R-015, FR-047, FR-049, S-12), and the helper must leave an explicit gap for the US2 password gate immediately before the claim (FR-050)
- [ ] T021 [US1] Run `python3 -m pytest tests/test_burn.py` and `python3 -m pytest` from the repository root; both must be green, confirming US1 works and no pre-existing test changed (FR-060)

**Checkpoint**: One-time pastes are fully functional and independently testable. This is the MVP.

---

## Phase 4: User Story 2 - Put a password on a shared snippet (Priority: P2)

**Goal**: `"password": "..."` at creation protects a paste; reads of it on either route require a
matching `X-Paste-Password` header and are `403` without one. `404` still beats `403`, deletion
stays token-only, and the password is never stored recoverably nor disclosed anywhere.

**Independent Test**: Create a paste with a password, confirm reads with no header, an empty
header, a wrong password, a duplicated header, and another paste's password are all `403` while a
read with the correct password succeeds on both routes, and confirm the paste still deletes with its
deletion token alone. Needs nothing from US1.

### Tests for User Story 2

> Write these first and confirm they FAIL before the implementation tasks below.

- [ ] T022 [US2] In `tests/test_password.py`, add creation-validation tests: a 1-character password and a 128-character password (including one of 128 **multi-byte** characters, whose UTF-8 encoding is longer) are accepted and the paste reports `"protected": true` (FR-035, V-13 boundaries inclusive); and each rejection — a non-string (number, boolean, `null`, array, object), `""` (zero characters), and 129 characters — is `400` with a JSON `error` body naming the field, with nothing written to the data directory (FR-036, FR-038, SC-015)
- [ ] T023 [US2] In `tests/test_password.py`, add the gate sweep for SC-013 across **both** read routes: the correct header serves `200` with the exact content and, on the JSON route, `"protected": true` (FR-040); an absent header, an empty header value, a wrong password, another paste's password, and the header supplied **more than once** each answer `403` with a JSON `error` body and leave the paste readable to a later correct attempt (FR-041, V-15, V-16, R-018); and an unprotected paste serves `200` on both routes with a stray `X-Paste-Password` header, which is ignored (FR-044, V-17)
- [ ] T024 [US2] In `tests/test_password.py`, add the `404`-beats-`403` sweep for FR-042/SC-014: a never-issued identifier, a deleted paste, an expired protected paste, and an ill-shaped identifier (e.g. `../../etc/passwd`) each answer `404` on both read routes with any password or none — never `403` — so no response discloses which identifiers exist or which are protected
- [ ] T025 [US2] In `tests/test_password.py`, add the storage-and-disclosure tests: the on-disk record contains `password_salt` and `password_hash` but neither the plaintext password nor anything reversible to it (FR-046, S-11); two pastes created with the *same* password have different stored salts and hashes (R-016); verification derives and compares via `secrets.compare_digest` over derived values (FR-043); a visually similar but different password is `403` while the exact password with non-ASCII characters, spaces, and punctuation is `200` (Story 2 scenario 13); and the SC-020 sweep that searches every response collected in this module — body and headers, at every status — for the literal passwords used
- [ ] T026 [US2] In `tests/test_password.py`, add the credential-independence and durability tests: `DELETE` with the correct `X-Delete-Token` and **no** password answers `204` even for a protected and/or one-time paste, while `DELETE` with a correct `X-Paste-Password` and a missing or wrong token answers `403` and leaves the paste readable (FR-045); `X-Paste-Password` is inert on `POST /pastes`, on `DELETE`, and on an undefined route (spec edge case); and a protected paste created before a restart over the same data directory still requires and accepts exactly the same password (FR-057, Story 2 scenario 14, part of SC-018)

### Implementation for User Story 2

- [ ] T027 [US2] In `src/pastebin/server.py`, add `_parse_password(parsed)` and call it from `_parse_create` **after** `_parse_burn_after_reading` (V-14, R-019): absent → `None`; `isinstance(value, str)` fails → `_Rejected(400, 'field "password" must be a string, got <json type>')` (V-12); `len(value)` outside `storage.PASSWORD_MIN_CHARS … storage.PASSWORD_MAX_CHARS` inclusive → `_Rejected(400, …)` naming the field and the bound (V-13). Measure with `len(str)` — **characters, not encoded bytes** — and add a comment saying this differs from `content`'s byte limit on purpose, because the inconsistency otherwise looks like a bug (FR-036, R-019)
- [ ] T028 [US2] In `src/pastebin/server.py`, thread the parsed password through `_parse_create` and `_create` into `storage.create_paste(..., password=...)`, keeping the `201` body exactly `id`, `delete_token`, `url` with the password **not** echoed (FR-037, FR-046), and keeping the plaintext a local variable that is never logged (S-11)
- [ ] T029 [US2] In `src/pastebin/server.py`, add `_password_ok(paste)` and insert it into `_load_for_read` **between** the load step and the claim step (contracts/http-api.md ordering rule): for an unprotected paste the header is never examined at all (FR-044, V-17); for a protected paste read occurrences with `self.headers.get_all("X-Paste-Password")` — zero → `403` "X-Paste-Password is required to read this paste", more than one → `403` "X-Paste-Password was supplied more than once", exactly one → `storage.password_matches`, `403` on mismatch (R-018, FR-041, FR-059). An empty value is one occurrence that fails the ordinary comparison, with no special case. Returning `403` must happen **before** `storage.consume_paste` is ever called, so a refused read consumes nothing (FR-050, SC-019)
- [ ] T030 [US2] Run `python3 -m pytest tests/test_password.py tests/test_burn.py` and `python3 -m pytest` from the repository root; all green, including T014's combined one-time-and-protected non-consumption assertions, which only become meaningful now

**Checkpoint**: User Stories 1 and 2 both work, independently and in combination (all four option
combinations).

---

## Phase 5: User Story 3 - Keep every existing snippet and client working (Priority: P3)

**Goal**: Nothing the service already does changes. Records written by the previous version keep
working, existing rejections keep their status codes, and the structured read keeps its existing
fields unchanged.

**Independent Test**: Run the pre-existing test suite unmodified, then start the service against a
data directory of records written by the previous version and confirm each reads back with unchanged
content, identifier, creation timestamp, and expiry, still deletes with its original token, and
reports itself as neither one-time nor protected.

- [ ] T031 [US3] In `tests/test_compat.py`, assert the creation response is unchanged for **all four** option combinations (neither option, one-time only, password only, both): `201` with a JSON body of exactly the keys `id`, `delete_token`, `url` — no extra field, no password, no flag (FR-037) — and that a request mentioning neither new field produces exactly the status, body shape, and stored record the previous version produced (FR-039)
- [ ] T032 [US3] In `tests/test_compat.py`, assert existing-rejection precedence (FR-039, Story 3 scenario 3, R-019): a body with oversized `content` **and** an invalid `burn_after_reading` still answers `413`, not `400`; an unparsable body, a non-object body, a missing or non-string `content`, and an invalid `expires_in` keep their existing statuses and messages even when a new field is also invalid; and the data directory gains **no file** from any rejected creation (FR-038)
- [ ] T033 [US3] In `tests/test_compat.py`, assert the read-body contract: the `GET /pastes/<id>` `200` body is exactly the six keys `id`, `content`, `created_at`, `expires_at`, `burn_after_reading`, `protected`, with the four pre-existing ones keeping their names, formats (`created_at` as `YYYY-MM-DDTHH:MM:SSZ`, `expires_at` that or `null`), and meanings and no `delete_token` (FR-054); the two booleans match what was set at creation across all four combinations and are never absent or `null` (FR-055); and the `GET /pastes/<id>/raw` body is the content and nothing else with `Content-Type: text/plain; charset=utf-8` (FR-056)
- [ ] T034 [US3] In `tests/test_compat.py`, add the legacy-record test for FR-058/SC-017 using `write_legacy_record` from `tests/conftest.py`: 50 records written in the previous version's shape (mixed expiring and non-expiring, including multi-byte content), then assert no "skipping unreadable record" line on stderr for any of them, that each reads back in both forms with unchanged `content`, `id`, `created_at`, and `expires_at`, that each original delete token still answers `204`, and that each reports `"burn_after_reading": false, "protected": false`
- [ ] T035 [US3] In `tests/test_compat.py`, add the restart-durability test for FR-057/SC-018 covering both options together over one data directory (`in_process_factory`, plus an end-to-end `launch` stop-and-start): after the restart the one-time paste is still consumed by exactly one read and the protected paste still requires and accepts exactly the same password
- [ ] T036 [US3] In `tests/test_compat.py`, add the malformed-new-key tests (spec edge case, data-model §3, S-10): a version-1 record on disk whose `burn_after_reading` is not a boolean, whose `password_salt` is not a hex string, or which has one password field without the other, is reported on stderr and skipped by `scan_directory` at startup and answers `404` on both read routes — never coerced to a default, because silently serving a one-time paste repeatedly is the highest-severity defect under Constitution II
- [ ] T037 [US3] In `tests/test_compat.py`, add the error-shape and availability tests: every new `400`, `403`, and `404` response body is exactly `{"error": "<message>"}` with `Content-Type: application/json` and a message naming what was wrong (FR-059); any path or method outside the four defined routes is still `404` with that body — the new options add no route (FR-060); and the SC-021 soak replays the full set of malformed new-option bodies, refused reads, and consumed-paste reads in bulk and then completes an ordinary create-read round trip, with no traceback and no `500` on stderr
- [ ] T038 [US3] Run `python3 -m pytest` from the repository root and confirm every pre-existing test file is byte-for-byte unmodified (`git diff --stat -- tests/` shows changes only to `tests/conftest.py` and the three new modules), satisfying FR-060 and SC-017

**Checkpoint**: All three user stories are independently functional and the compatibility guarantee
is proven.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T039 Review and tidy the new docstrings and comments in `src/pastebin/storage.py` and `src/pastebin/server.py`: the character-vs-byte limit difference (R-019), why `RECORD_VERSION` stays `1` (R-017), why the claim is an `unlink` and where it must sit relative to the password check (R-015, FR-050), and the POSIX platform note from R-015
- [ ] T040 [P] Update `tests/README.md` to list `tests/test_burn.py`, `tests/test_password.py`, and `tests/test_compat.py` with the requirement ranges each owns, matching the traceability table in `specs/002-burn-after-reading-password/quickstart.md`
- [ ] T041 Verify the Constitution v1.0.0 quality gates on the diff: `pyproject.toml` `dependencies = []` is unchanged and `hashlib` is the only new runtime import (I); no new bare `except:` or `except Exception: pass` and every new rejection names the field or cause (II); no new structure needing a Principle IV justification (IV); stdout still carries only the readiness line (Additional Constraints)
- [ ] T042 Verify requirement coverage for SC-016: run `python3 -m pytest --collect-only -q` from the repository root and confirm each of FR-033 through FR-060 appears in at least one collected test name, and that the whole suite passes
- [ ] T043 Run the manual validation scenarios V8–V17 in `specs/002-burn-after-reading-password/quickstart.md` against a live `python3 -m pastebin serve` and confirm each expected outcome, including V14's `400` row and the `413`-not-`400` precedence check
- [ ] T044 Confirm the performance shape stated in `plan.md`: a read of a protected paste costs roughly one PBKDF2 derivation (~40 ms) and reads of **unprotected** pastes are unaffected, so no existing path got slower
- [ ] T045 Final gate: `python3 -m pytest` green from the repository root, `git diff` limited to `src/pastebin/storage.py`, `src/pastebin/server.py`, `tests/conftest.py`, and the three new test modules, and every item in this file checked off

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on Setup — **blocks both user stories**
- **US1 (Phase 3)** and **US2 (Phase 4)**: both depend only on Phase 2 and can proceed in parallel
- **US3 (Phase 5)**: its tests span both options, so it is cheapest after US1 and US2 land; T031–T033 and T034/T036 can in fact run as soon as Phase 2 is done
- **Polish (Phase 6)**: depends on every story being complete

### User Story Dependencies

- **US1 (P1)**: independent. Needs T003–T011 only
- **US2 (P2)**: independent. Needs T003–T011 only. Does **not** need US1 — but note T029 inserts the password gate into the `_load_for_read` helper T020 creates, so if US2 ships first, T029 instead inserts the gate directly into `_read_json`/`_read_raw` and T020 then wraps both steps
- **US3 (P3)**: adds no capability. T034 and T036 depend only on Phase 2; T031–T033, T035, and T037 assert behaviour from both stories

### Within Each User Story

- Tests are written first and must fail before the implementation tasks
- Storage before server; validation before wiring; the read gate before the claim
- Each story ends with a full-suite run, so a regression in the pre-existing suite is caught at the story boundary rather than at the end

### Critical sequencing not to get wrong

- T017/T027 append to `_parse_create` **after** the existing checks — reversing this turns an existing `413` into a `400` and breaks FR-039 (quickstart troubleshooting row)
- T029 runs **before** T020's claim — reversing this lets a wrong password destroy a one-time paste and breaks FR-050/SC-019
- T020's claim runs **after** the content is in memory and **before** the response is written — serving first loses the race and breaks FR-049

### Parallel Opportunities

- T003–T009 all touch `src/pastebin/storage.py` and so are sequential; T010/T011 touch `tests/conftest.py` and can run in parallel with them
- Within a story, test tasks share one file and so are sequential; the test file and the implementation files are different files, so a second person can write T017–T020 while T012–T016 are being written, as long as the tests land first
- US1 (`tests/test_burn.py` + server read path) and US2 (`tests/test_password.py` + server validation) are the main parallel axis
- T040 is the only [P] task in Polish

---

## Parallel Example: after Phase 2

```bash
# Two developers, no file conflicts:
Developer A: T012–T016 (tests/test_burn.py)    then T017–T020 (src/pastebin/server.py, read path)
Developer B: T022–T026 (tests/test_password.py) then T027–T029 (src/pastebin/server.py, validation + gate)
# One merge point: both touch src/pastebin/server.py — agree that _load_for_read (T020) lands first.

# Inside Phase 2, these two can go at once:
Task: "Add hashlib, KDF constants, Paste fields, hashing, create, read-validate, consume in src/pastebin/storage.py"  # T003–T009
Task: "Add password-aware read helpers and write_legacy_record in tests/conftest.py"                                  # T010–T011
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (T001–T002)
2. Phase 2: Foundational (T003–T011) — **blocks everything**
3. Phase 3: User Story 1 (T012–T021)
4. **STOP and VALIDATE**: quickstart V8 and V9, plus `python3 -m pytest`
5. One-time pastes are shippable on their own; `protected` is already in the read body and is always
   `false` until US2 lands

### Incremental Delivery

1. Setup + Foundational → storage layer ready, old records still load
2. + US1 → one-time pastes work (MVP, quickstart V8, V9)
3. + US2 → password protection works, including the combined case (quickstart V10–V13)
4. + US3 → compatibility proven (quickstart V14–V17)
5. + Polish → gates verified

### Parallel Team Strategy

1. Everyone on Phase 2 (it is small and blocking)
2. Then A on US1, B on US2, coordinating only on `src/pastebin/server.py`
3. US3 afterwards, by whoever finishes first, since it only writes tests

---

## Notes

- Tests are mandatory here (Constitution III), and every test name must carry its requirement id —
  e.g. `test_fr_047_first_read_serves_and_destroys` — so SC-016's coverage check is mechanical
- No pre-existing test module may be edited; `tests/conftest.py` changes must be purely additive
  (SC-017)
- No new runtime dependency, no new module, no new route, no new config knob (Constitution I and IV;
  plan.md Constitution Check)
- Commit after each task or logical group; stop at any checkpoint to validate a story on its own
