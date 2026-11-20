# Phase 0 Research: Burn After Reading and Password Protection

**Feature**: `002-burn-after-reading-password` | **Date**: 2026-11-20

Continues the identifier numbering of [001's research](../001-pastebin-service/research.md)
(`R-001`…`R-014`), so every decision identifier in the repository stays unique.

The Technical Context in [plan.md](./plan.md) carries **no NEEDS CLARIFICATION markers**: the
language, dependency rule, storage shape, and test runner were all fixed by the constitution, by
feature 001, and by the user input for this command ("Python 3.11 or newer, standard library only,
the interface in the specification exactly, pytest for tests"). The open questions were therefore
not *what* to use but *how* to meet three requirements the existing code has no primitive for:
at-most-once reads under concurrency (FR-049), unrecoverable password storage (FR-046), and
extending the record format without breaking records the previous version wrote (FR-058).

---

## R-015: At-most-once consumption of a one-time paste

**Decision**: claim the paste by removing its record — `os.unlink(record_path(...))` — **after** the
record has been read fully into memory and **before** the response is written. The caller that
raises `FileNotFoundError` lost the race and answers `404`. Exposed as
`storage.consume_paste(data_dir, paste_id) -> bool`.

Read order inside a read route is therefore: load (404) → password (403) → *claim* (404 if lost) →
serve 200 from the in-memory copy.

**Rationale**:

- POSIX guarantees that for concurrent `unlink` calls on the same directory entry exactly one
  succeeds and the rest fail with `ENOENT`. That is the whole mutual-exclusion mechanism — one
  syscall, no lock file, no index, no "consumed" flag to write and fsync. FR-049 ("at most one
  successful read even when reads are in flight at the same time") falls out of the kernel's
  directory-entry semantics rather than out of code this project has to get right.
- It preserves invariant S-8 from feature 001: the directory contents are the whole truth, with no
  hidden state. A `consumed: true` flag written back into the record would have needed a
  read-modify-write with no atomicity (two readers could both see `false`), so it would have needed
  a lock, which 001 deliberately does not have (R-008).
- Reading the content into memory *before* the claim is what satisfies "no read ever returns partial
  or corrupt content" (FR-049, SC-012): the bytes being served no longer depend on the file
  existing. It also composes with 001's invariant S-4 (a read racing a delete sees the whole record
  or nothing).
- The claim sits *after* the password check, which is exactly FR-050: a `403` never reaches the
  unlink, so a wrong password costs the paste nothing (SC-019).
- "Destruction is immediate and permanent" (spec assumption): the next request genuinely finds no
  file, so FR-048's `404` — including for a delete presenting the original token — needs no extra
  code at all.

**Consequence accepted**: a client that disconnects after the claim but before the body lands loses
the content for good. The specification explicitly chooses this ("at most once, not exactly once";
edge case "a client that disappears mid-response"), so no attempt is made to confirm delivery.

**Alternatives considered**:

| Alternative | Rejected because |
|---|---|
| Rename the record to a unique `.consumed-<rand>` name, serve, then unlink | Same race-winner semantics as plain `unlink` but two syscalls, a second temp-file lifecycle to clean up on crash, and a window where the directory holds an entry that `scan_directory` would report as unrecognised. No requirement buys anything with it. |
| `consumed: true` written back into the record | Not atomic without a lock; leaves a tombstone that must then be hidden from reads *and* from `scan_directory`; contradicts "destruction is immediate and permanent". |
| A `threading.Lock` per paste id (or one global lock) in the server process | Only guards one process. 001's model is explicitly multi-process-safe through the filesystem (R-008), and a restart against the same directory must behave identically (FR-057). Also pure added state for no gain, against Principle IV. |
| `fcntl.flock` on the record | Advisory, filesystem-dependent, and still needs the unlink afterwards. Strictly more machinery than the unlink it would be protecting. |
| Serve first, then unlink | Loses the race: two concurrent reads could both serve before either unlinks, violating FR-049 outright. |

**Platform note**: the guarantee is POSIX `unlink`. The service is loopback-only Linux/POSIX
(feature 001, FR-025); on Windows `os.unlink` of an open file behaves differently, which is recorded
here as a known platform constraint rather than handled, because no requirement targets Windows.

---

## R-016: Storing and checking the password

**Decision**: store a per-paste 16-byte random salt and
`hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)`, both hex-encoded, in the
record as `password_salt` and `password_hash`. Verify by deriving from the supplied password with
the same salt and comparing with `secrets.compare_digest`. KDF parameters live as module constants
in `storage.py`, not in the record.

**Rationale**:

- FR-046 requires that the password is not retained "in a form from which the original password can
  be recovered", and the spec assumption spells out the threat: read access to the storage directory
  must not hand over the passwords people chose. A salted, deliberately slow derivation is the
  standard answer, and `hashlib.pbkdf2_hmac` is in the standard library on every CPython build
  (Constitution I, and the "installs anywhere Python is present" rationale behind it).
- Per-paste salt means two pastes sharing a password have unrelated stored values, so the directory
  does not even reveal which pastes share a password.
- `secrets.compare_digest` on the derived values satisfies FR-043 (no timing disclosure) and matches
  how the existing `token_matches` already compares deletion tokens (R-005) — one comparison idiom
  in the codebase, not two.
- 200,000 iterations measured at ~40 ms on the development machine. That is paid only on reads of a
  *protected* paste, on a loopback single-operator service with no rate limiting (spec assumption),
  and it is the cost that makes an exposed storage directory useless. Unprotected reads are
  untouched.
- Comparison is exact, with no case folding, trimming, or Unicode normalisation (spec assumption):
  the password is encoded UTF-8 and fed to the KDF as-is, so a visually similar password fails
  (Story 2 scenario 13).

**Alternatives considered**:

| Alternative | Rejected because |
|---|---|
| `hashlib.scrypt` (n=2¹⁴, r=8, p=1) | Measured at the same ~40 ms and is memory-hard, so cryptographically the better choice — but it exists only when CPython was linked against OpenSSL ≥1.1, which makes the zero-dependency promise conditional on a build flag, and it costs ~16 MB per concurrent check (160 MB at SC-012's ten-way concurrency). PBKDF2 is unconditionally present and has no memory amplification. Revisit only if the threat model changes. |
| Plain `hashlib.sha256(salt + password)` | Fast enough to brute-force the short, human-chosen passwords this field invites. Fails the *spirit* of FR-046 even though it is technically irreversible. |
| Store the password as-is and compare with `compare_digest` | Satisfies FR-043 but flatly violates FR-046. |
| Record the KDF name/iterations per record (`"kdf": "pbkdf2_sha256", "iterations": 200000`) | A speculative extension point with one implementation, which Principle IV forbids. **Consequence written down deliberately**: changing the iteration count later invalidates existing protected pastes, so such a change must bump `RECORD_VERSION` (and old protected pastes would then be reported and skipped). That is the accepted price of the simpler record. |
| Encrypt the content with a key derived from the password | Far beyond the requirement. The spec asks for a read gate, not confidentiality against someone holding the storage directory, and it also requires `protected` to be reportable and the content to be servable — which key-wrapping would complicate for no stated benefit. |

---

## R-017: Extending the record format without breaking old records

**Decision**: keep `RECORD_VERSION = 1`. Add three keys that are **optional on read** and **always
written on create**: `burn_after_reading` (bool), `password_salt` (hex string or `null`),
`password_hash` (hex string or `null`). A record missing all three loads as "not one-time, not
protected". A record in which any of them is *present but malformed* raises `_BadRecord` and is
reported and skipped, as any other corruption already is.

**Rationale**:

- FR-058 requires records written by the previous version to keep working. The existing reader
  rejects any `version` other than `1` outright (`_read_paste` → `_BadRecord` → reported and
  skipped), so bumping to `2` would make every pre-existing paste disappear with a skip message —
  the precise failure FR-058 and SC-017 forbid. Absent-means-default on a version-1 record is the
  only change that is compatible in the direction that matters.
- The on-disk record is explicitly internal and not part of the contract (001 data-model; spec
  assumption "storage format changes are internal"), so no external consumer is entitled to notice.
- Writing the new keys unconditionally on create keeps new records self-describing and keeps the
  write path free of conditionals.
- Validating the new keys when present preserves Constitution II: a malformed `burn_after_reading`
  on disk is never coerced to `false`, because silently serving a paste that was meant to be
  one-time repeatedly is exactly the "silent wrong answer" the constitution calls the highest
  severity defect. It is reported and the record is skipped (spec edge case: "a record whose new
  fields are malformed" is still reported and skipped and answers `404`).

**Consequence accepted**: records written by *this* version are not readable by the previous
version (it would reject the unknown keys only if it validated them — in fact it ignores unknown
keys, so it would read them as ordinary unprotected, non-burning pastes). Backward compatibility is
one-directional, which is all FR-058 asks for.

**Alternatives considered**: `RECORD_VERSION = 2` with a read-time accept-list of `{1, 2}` (adds a
branch and a second format to keep alive forever, for no behavioural gain over optional keys); a
one-shot migration pass at startup (mutates the operator's data on upgrade, needs its own
failure-handling story, and violates "expired records are left in place" conservatism); a sidecar
file per paste for the new fields (two files to keep atomic, breaks S-8).

---

## R-018: Reading the `X-Paste-Password` header, including duplicates

**Decision**: read the header with `self.headers.get_all("X-Paste-Password")`. For a protected
paste: zero occurrences → `403` ("required"), more than one → `403` ("supplied more than once"),
exactly one → derive and compare. For an unprotected paste the header is never looked at.

**Rationale**:

- `self.headers` is an `email.message.Message`; `get()` silently returns only the *first* of several
  occurrences, which is precisely the coercion of ambiguous input Constitution II forbids and which
  FR-041 settles by requiring `403`. `get_all` is the only API that makes the ambiguity visible.
- The three cases get distinct diagnostics (FR-059: the message must name what was wrong
  specifically enough to act on). Distinguishing them discloses nothing beyond what the `403` status
  already discloses, since FR-042 guarantees a non-existent paste never reaches this code at all.
- An empty value (`X-Paste-Password:` with nothing after it) is one occurrence of the empty string:
  it goes through the ordinary derive-and-compare and fails, because no paste can have an empty
  password (V-12). No special case (FR-041).
- Not looking at the header for an unprotected paste is FR-044 ("MUST ignore") stated directly, and
  keeps the header inert on create, delete, and unknown routes (spec edge case) with no code at all.

**Alternatives considered**: `self.headers.get()` (picks the first occurrence — the behaviour FR-041
rejects); joining multiple values with a comma, which `email.message` does for some headers
(invents a password nobody sent); `400` for the duplicate case (the spec assigns it `403`, and the
request fixes `403` for password failures).

---

## R-019: Where the new validation sits in the creation path

**Decision**: validate the new fields in `_parse_create`, **after** the existing V-1…V-7 checks,
in the order `burn_after_reading` then `password`. Both produce `_Rejected(400, …)` and are raised
before `storage.create_paste` is called.

**Rationale**:

- FR-039 and Story 3 scenario 3 require that a request the existing rules already reject keeps its
  existing status even when a new field is also invalid. Appending the new checks after the old ones
  guarantees that mechanically: oversized content still yields `413`, a non-string `content` still
  yields `400` naming `content`, and no reordering of the existing precedence is possible.
- FR-038 ("store nothing when rejected") is already structural in the existing code — all validation
  completes before storage is touched — and appending to the same function preserves it.
- The relative order of the two new checks is unobservable (both are `400`), as the spec notes, so
  it is fixed arbitrarily to field order in the request description for readability.
- `password` length is measured with `len(str)` — characters, not encoded bytes (FR-036, spec
  assumption) — deliberately unlike `content`'s byte limit, which stays byte-measured. The two
  limits are different on purpose and the code comments will say so, because the inconsistency looks
  like a bug otherwise.
- `isinstance(value, bool)` must be checked *before* `isinstance(value, int)` nowhere new here, but
  the mirror-image trap applies to `burn_after_reading`: `isinstance(True, int)` is `True` in
  Python, so the boolean check is `isinstance(value, bool)` and `1`/`0` are rejected as numbers
  (FR-034, spec edge case "numbers are not booleans"). For `password`, `isinstance(value, str)` is
  exact — no bool subclass trap — matching how `content` is already checked.

**Alternatives considered**: validating the new fields first (would let an invalid
`burn_after_reading` turn an existing `413` into a `400`, breaking FR-039); collecting all field
errors and reporting them together (changes the response shape for existing rejections, which
FR-059 pins to a single `error` string).

---

## R-020: Test strategy for the new behaviour

**Decision**: three new modules — `tests/test_burn.py`, `tests/test_password.py`,
`tests/test_compat.py` — reusing the existing `service`, `in_process_factory`, and `launch`
fixtures. `conftest.py` gains an optional `password` argument on its `read`/`read_raw` helpers and a
helper that writes a *legacy* record (version 1 without the new keys) directly into a data
directory. Concurrency (SC-012) is exercised with `concurrent.futures.ThreadPoolExecutor` against
the in-process server; restart durability (SC-018) with `in_process_factory` over one directory,
plus one end-to-end `launch` stop-and-start.

**Rationale**:

- Constitution III requires one named `pytest` test per requirement with a discoverable mapping;
  the existing suite already names tests after FR ids, so the new modules follow it and
  [quickstart.md](./quickstart.md) carries the traceability table.
- Splitting by concern rather than growing `test_read.py` keeps SC-017's claim — "the existing test
  suite passes unmodified" — literally verifiable: no existing test file is edited.
- The legacy-record writer is the only honest way to test FR-058/SC-017. Creating records through
  the *previous* version of the code is not available in-tree, so the test writes the exact v1
  record shape 001 documented, which is pinned in [data-model.md](./data-model.md).
- SC-020 (no password is ever disclosed) is tested as a sweep: every response collected in the
  password module is searched for the literal passwords used.

**Alternatives considered**: a subprocess-only suite (far slower, and the in-process fixture already
covers request/response requirements per 001's R-014); mocking the KDF to speed tests up (would stop
testing the thing FR-046 is about, and 40 ms × the suite's protected reads is acceptable).

---

## Resolved constraint summary

| Question | Resolution | Requirements |
|---|---|---|
| How is "at most one successful read" enforced? | `os.unlink` as the claim, after reading content into memory, after the password check, before the response | FR-047, FR-049, FR-050, SC-012 |
| What is stored for a password? | 16-byte random salt + PBKDF2-HMAC-SHA256, 200k iterations, hex; compared with `compare_digest` | FR-043, FR-046, SC-020 |
| How do old records keep working? | `version` stays `1`; new keys optional on read, always written on create | FR-057, FR-058, SC-017 |
| Duplicate `X-Paste-Password`? | `get_all`, length ≠ 1 → `403`, never resolved by guessing | FR-041, SC-013 |
| Does a new invalid field change an existing rejection? | No: new checks run after V-1…V-7 | FR-039 |
| Any new runtime dependency? | No. `hashlib` is the only new import | Constitution I |
