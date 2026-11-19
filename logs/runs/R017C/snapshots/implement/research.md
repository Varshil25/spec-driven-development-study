# Phase 0 Research: Burn-After-Reading and Password-Protected Pastes

**Feature**: `002-burn-and-password-pastes` | **Date**: 2026-11-16 | **Plan**: [plan.md](./plan.md)

Decision numbering continues the sequence established by `001-pastebin-service`, whose decisions
R-01 … R-15 ([research.md](../001-pastebin-service/research.md)) remain in force unchanged. This
feature adds R-16 … R-26. Where a decision here refines one of R-01 … R-15, the refinement is
stated explicitly and the original decision is **not** reversed.

The Technical Context of [plan.md](./plan.md) raised no `NEEDS CLARIFICATION` items that survive
this phase; the "Resolved unknowns summary" at the end lists each one and where it was settled.

---

## R-16: Password hashing algorithm and parameters (SR-013, SR-018)

**Decision**: `hashlib.pbkdf2_hmac("sha256", password_utf8, salt, 600_000, dklen=32)` with a
16-byte salt drawn from `secrets.token_bytes(16)`, stored per paste. The constants live in
`models.py` as `PBKDF2_ALGORITHM = "pbkdf2_sha256"`, `PBKDF2_ITERATIONS = 600_000`,
`PBKDF2_SALT_BYTES = 16`, `PBKDF2_DKLEN = 32`.

**Rationale**:

- It is standard library (Principle I) and is named explicitly in the constitution's Security
  Baseline credential-storage item, so no amendment and no exception is required.
- 600 000 iterations of PBKDF2-HMAC-SHA-256 is the OWASP Password Storage Cheat Sheet's current
  recommendation for that algorithm, which is what SR-013's "current parameters" points at.
- Its memory use is O(1) — a few hundred bytes — so the per-request memory envelope the existing
  SR-005 / FR-029 controls establish (~66 KB) is unchanged by this feature. That matters here
  more than usual: the server is `ThreadingHTTPServer` with one thread per connection and the
  spec's Assumptions explicitly decline to rate-limit password attempts, so anything whose cost
  scales with concurrency is a self-inflicted denial of service.
- `hashlib.pbkdf2_hmac` dispatches to OpenSSL, so the 600 000 iterations cost roughly 0.2 s of C
  time per verification rather than Python-loop time.

**Alternatives considered**:

| Alternative | Rejected because |
|---|---|
| `hashlib.scrypt`, OWASP minimum `n=2**17, r=8, p=1` | Memory-hard by design: ~128 MiB **per concurrent verification**. With one thread per connection, no request cap, and no password-attempt throttling (spec Assumption "No rate limiting on password attempts"), a handful of simultaneous reads of one protected paste would allocate gigabytes. That directly contradicts SR-018's "the work any single submission or read can provoke stays bounded" and the Baseline's resource-limits item |
| `hashlib.scrypt` with reduced `n` (e.g. `2**14`, 16 MiB) | Keeps the memory problem in a smaller form while silently dropping below the published minimum parameters for the algorithm. "Current parameters" (SR-013) is not a value we get to lower to make the implementation comfortable; choosing a different algorithm at its own recommended strength is the honest move |
| `hashlib.blake2b(key=…)` / HMAC of the password | Fast by design. A keyed hash is not a *deliberately slow, purpose-built password hashing algorithm*; SR-013 rejects it in so many words |
| A single unsalted SHA-256 | Violates SR-013 twice (no salt, not slow) |
| Argon2 (`argon2-cffi`) | Third-party. Principle I forbids it at runtime, and no standard-library gap justifies an amendment when PBKDF2 at current parameters is available |
| Deriving an encryption key from the password and encrypting the content | Far larger design (key management, AEAD choice, re-encryption semantics) for a requirement — "reading requires the header" — that an authorization check satisfies. Principle IV: the smallest design that satisfies the specification wins. Also note the spec does **not** ask for content confidentiality against someone holding the data directory |

**Interaction with SR-018 (bounded work)**: exactly one KDF invocation can be provoked per
request, and only after the request has resolved to a live, protected paste. Validation of the
`password` field's shape (type, 1 … 128 characters) happens before any hashing on the create path
(FR-033, FR-036), so an oversized or wrong-typed value never reaches the KDF.

---

## R-17: Stored verifier representation and forward/backward compatibility (FR-051, FR-052, SR-020)

**Decision**: two optional keys are added to the record file. `RECORD_FIELDS` — the set of keys a
record must carry to be recognisable at all — is **not** extended.

```json
{
  "id": "…", "content": "…", "created_at": "…", "expires_at": null, "delete_token": "…",
  "burn_after_reading": false,
  "password": {
    "algorithm": "pbkdf2_sha256",
    "iterations": 600000,
    "salt": "9f1c…",      // 32 hex characters (16 bytes)
    "hash": "4b7e…"       // 64 hex characters (32 bytes)
  }
}
```

`"password"` is JSON `null` (or absent) for an unprotected paste. Both keys absent is exactly the
shape every pre-feature record already has, which is what makes FR-051 and SC-019 hold with no
migration, no rewrite, and no startup scan (spec Assumption "Existing records need no migration").

**Interpretation rules, applied in `store._load` so that every caller inherits them**:

| Stored shape | Interpretation | Requirement |
|---|---|---|
| `burn_after_reading` absent | `False` | FR-051 |
| `burn_after_reading` present, `type(...) is bool` | that value | FR-052 |
| `burn_after_reading` present, anything else | **record is unusable → paste does not exist (404)** | SR-020, Edge Case "Stored record whose new data is unusable" |
| `password` absent or `null` | unprotected | FR-051 |
| `password` a dict with exactly the four keys, `algorithm == "pbkdf2_sha256"`, `iterations` an `int` in `[1, 10_000_000]`, `salt` 32 hex chars, `hash` 64 hex chars | protected, verify against it | FR-052 |
| `password` anything else | **record is unusable → paste does not exist (404)** | SR-020 |

**Rationale**: the two failure directions are not symmetric and the spec is explicit about which
way each one falls. A *missing* option means "off", because that is what every legacy record
looks like and treating it as corrupt would destroy pastes the operator still owns (FR-051). A
*malformed* option means "gone", because the alternatives are to serve a protected paste without
checking a password or to serve a one-time paste twice — both are SR-017 violations. Treating it
as absent-therefore-unprotected would be exactly the fail-open behaviour SR-020 forbids.

The `iterations` bound is not decoration: without it, a record whose `iterations` reads
`10**12` — whether through corruption or because someone with write access to the data directory
put it there — would wedge a request thread in the KDF for hours. SR-018 requires the work a
single read can provoke to be bounded by something other than the contents of a file.

**`type(...) is bool`, not `isinstance`**: this is R-10's rule applied to the new field. Because
`bool` subclasses `int`, an `isinstance(x, int)` guard elsewhere would accept `True`; symmetrically
an `isinstance(x, bool)` guard here is adequate, but `type(...) is bool` is used for consistency
with the existing validator and to reject `bool` subclasses.

**Alternatives considered**:

| Alternative | Rejected because |
|---|---|
| Flat keys `password_salt` / `password_hash` / `password_iterations` | Three keys that are only ever meaningful together, each independently absent-able, multiplying the partial-shape cases `_load` has to reason about. One nested object has one validity question |
| A PHC-style single string (`$pbkdf2-sha256$600000$salt$hash`) | Requires writing and testing a parser for a format the service neither receives nor emits, to store a value only this code reads. Principle IV |
| Adding the new keys to `RECORD_FIELDS` and migrating old records on startup | A startup scan that rewrites every record is explicitly out of scope (spec Assumption "Existing records need no migration"), and a rewrite pass is the one operation that can damage pastes that were previously fine |
| Storing a `protected` boolean alongside the verifier | Redundant state that can disagree with itself. `protected` is derived: `record["password"] is not None` |

---

## R-18: Verification and constant-time comparison (SR-014, SR-019)

**Decision**: `models.verify_password(verifier, supplied) -> bool` re-derives the key with the
stored salt and iteration count, then compares the two 32-byte digests with
`hmac.compare_digest`. The comparison operands are the **derived digests**, never the passwords.
A missing `X-Paste-Password` header short-circuits to `403` without invoking the KDF.

**Rationale**:

- `hmac.compare_digest` on fixed-length digests is the Baseline's "Randomness and comparison"
  control and mirrors R-05's handling of `delete_token`. Comparing derived digests rather than
  raw passwords also removes the length-leak that comparing variable-length inputs would carry.
- Short-circuiting on an *absent* header is not a comparison and therefore not a timing side
  channel over any stored value: it is decided entirely by the request. The alternative — hashing
  the empty string so that the no-header path costs the same as the wrong-password path — would
  let an unauthenticated caller provoke a 0.2 s KDF run per request with no header at all, which
  is the SR-018 bound traded away for a distinction that reveals nothing. An **empty** header
  value (`X-Paste-Password:`) is treated identically to an absent one; because a stored password
  is at least 1 character (FR-032), the empty string can never be a correct password, so no access
  decision changes (Edge Case "Empty password header on a protected snippet").
- The refusal message is a fixed constant (`"invalid paste password"`). It never echoes the
  supplied value, never reports whether a password was supplied at all, and never mentions the
  stored verifier, its salt, or its parameters (SR-019).

**Enforcement**: `tests/test_password.py` carries a source-level scan, modelled on the existing
`test_SR_002_implementation_uses_hmac_compare_digest`, asserting that no line in `src/pastebin/`
compares anything matching `password`/`hash`/`digest` with `==` or `!=`, and that
`hmac.compare_digest(` appears in the verification path.

---

## R-19: Reading the `X-Paste-Password` header (FR-034, FR-040, Edge Cases)

**Decision**: read the header with `self.headers.get("X-Paste-Password")` — the first value if it
appears more than once — then recover the author's text with
`value.encode("latin-1").decode("utf-8")`. A value that fails either step is treated as a wrong
password (`403`), never as an error and never as a match.

**Rationale**:

- Python's `email.parser`, which `http.server` uses for headers, decodes header bytes as
  ISO-8859-1 (RFC 7230's legacy rule). Re-encoding to `latin-1` recovers the exact bytes the
  client sent; decoding those as UTF-8 yields the author's text. Without this round trip a
  non-ASCII password would never match what was stored, breaking FR-034 and the Edge Case
  "Password with unusual characters".
- `UnicodeEncodeError` (a value the stdlib produced outside latin-1 — not reachable through the
  standard parser, guarded anyway) and `UnicodeDecodeError` (bytes that are not valid UTF-8) both
  mean the caller did not send the stored password, since the stored password came from a UTF-8
  JSON body and is UTF-8 by construction. `403` is the correct answer and keeps the handler off
  the `500` path (Principle II: the failure is answered, not swallowed).
- Duplicate headers: taking the first value is deterministic and satisfies the Edge Case in its
  binding form — access is granted only when the value acted upon *is* the stored password. There
  is no shape of duplicate headers that grants access to a caller who does not hold the password.
  Note that this differs from the `X-Delete-Token` handling only in the UTF-8 step: the delete
  token is ASCII by construction (R-05), a password is not.

**Alternatives considered**: rejecting a request that carries the header twice with `400`
(introduces a status the spec never mentions on a read path, and the spec's Edge Case asks only
that access not be granted); joining duplicate values with commas (the stdlib `get_all` behaviour
would manufacture a value no client sent); treating a non-UTF-8 header as `400` (leaks that the
paste exists and is protected to a caller who sent garbage — `403` already does that, but `400`
would do it on a *different* axis and for no gain).

---

## R-20: Atomic single-read destruction (SR-016, FR-044, FR-047, FR-048)

**Decision**: the claim is the `os.unlink`. A read of a one-time paste runs:

```text
record = store.read_record(id)          # load + liveness; None → 404
                                        # password verified here if protected (R-21)
claimed = store.consume_record(id)      # under the store's existing lock: os.unlink
if not claimed: → 404                   # someone else won the race, or it expired away
serve record["content"]                 # only now is any byte of content written
```

`consume_record` returns `True` when its `os.unlink` removed the entry, `False` on
`FileNotFoundError`, and lets any other `OSError` propagate (which the handler converts to a
generic `500` with no content — SR-020).

**Rationale**:

- POSIX `unlink` is atomic with respect to the directory entry: of N concurrent `unlink` calls
  naming the same path, **exactly one** returns success and the rest fail with `ENOENT`. That
  makes "did I win?" a single syscall answer, with no compare-and-swap to emulate and no window
  between the check and the removal. SR-016 is satisfied by the primitive, not by a convention.
- Content is read *before* the claim but written to the socket only *after* it, which is exactly
  the spec's Assumption "Destruction happens before the text is handed over": the text is handed
  over only once removal has succeeded, and a removal failure yields an error rather than a second
  disclosure. Reading the bytes early is safe because records are immutable after creation — there
  is no update operation — so the bytes read and the bytes claimed are necessarily the same.
- The call is made under the store's **existing** `threading.Lock`, the same one `delete_record`
  holds. No second lock and no per-identifier lock registry is introduced (R-09's rejection of
  that stands). The lock is not what makes the claim atomic — `unlink` is — but holding it keeps
  a concurrent revocation from interleaving between the liveness check and the claim, so the two
  destructive paths have one serialization point rather than two that must be reasoned about
  together.
- FR-048 (durability of destruction across a restart) needs nothing further. The service is
  stopped and started again on the same machine against the same directory; the unlinked entry is
  gone from the filesystem's view the instant the call returns, regardless of whether the
  directory metadata has reached the platter. `fsync` on the directory is **not** performed: no
  stated requirement concerns machine-level crash consistency, and adding it would slow every
  burn read for a guarantee the spec does not ask for (Principle IV). This is the same line 001
  drew in R-03, where the record file is `fsync`ed because FR-023 asks for durability of
  *creation* across a restart.

**Alternatives considered**:

| Alternative | Rejected because |
|---|---|
| Rename-to-claim (`os.replace(path, tmp)`, read the renamed file, then unlink) | `os.replace` onto a fresh unique name succeeds for *both* racers if each picks its own target name, so it does not decide a winner. A shared target name would decide one, but that is `unlink`'s job done with two syscalls and a leftover file to clean up on every failure path |
| `O_TMPFILE` / open-then-unlink and serve from the descriptor | Same winner-selection problem, plus a descriptor held across the response write |
| A "consumed" flag written into the record | Turns a removal into a read-modify-write, needs the atomic-replace dance for every burn read, leaves the content on disk after consumption (contradicting the spec's Assumption "Destruction means removal"), and leaves a record that must then be distinguished from a live one on every subsequent read |
| An in-memory set of consumed ids | Not durable across restart (FR-048), and wrong the moment the record is also removable by revocation |
| Holding the lock across the socket write | A slow client would serialize every other request behind it. The claim is already decided before the first byte is written, so the lock has nothing left to protect |

---

## R-21: Ordering of checks on a read (FR-043, FR-046, SR-015, SR-017)

**Decision**: every read — structured or raw — evaluates in exactly this order:

```text
1. identifier allowlist + path containment        → 404   (unchanged, SR-003)
2. record exists, parses, and is usable           → 404   (R-17; includes malformed new fields)
3. record is live (not expired)                   → 404   (unchanged, FR-017)
4. if protected: X-Paste-Password verifies        → 403   (FR-040, SR-015)
5. if one-time: claim succeeds                    → 404   (R-20; lost race / vanished)
6. serve
```

**Rationale**:

- Steps 1-3 before step 4 is FR-043 verbatim: non-existence outranks refusal, so a `403` is only
  ever returned for an identifier that really resolves to a live paste, and an unknown or expired
  identifier is indistinguishable from a protected one to a caller without the password. This is
  the same precedence R-09 already established for `delete_record` (`404` before `403`), applied
  to the read paths — the service now has one rule, not two.
- Step 4 before step 5 is the composition the spec calls "the only safe order" (User Story 3): a
  caller who cannot prove they hold the password never consumes the single read, so a stranger
  with the link cannot destroy a paste they were never entitled to see (FR-046).
- The password is re-verified against the stored record on **every** read, in **both** read forms.
  Nothing is cached, no cookie or session exists, and no client-supplied claim other than the
  password itself is consulted (SR-015). This falls out of the design rather than needing
  enforcement: there is no state between requests anywhere in the service.
- Step 6 writes the first byte of content. Nothing before it discloses any part of the text, the
  length of the text, or anything derived from it (FR-041).

**Paths that are not reads**, and therefore never reach steps 4-6: `DELETE` (token only, FR-050 —
a password header has no effect and is not read on that path), and every unrouted request, which
is `404` from the route table before any record is loaded (FR-046, SR-017). `HEAD` remains `404`
by the same route table and so cannot consume a one-time paste either.

---

## R-22: Validation order and precedence for the new creation fields (FR-031, FR-033, FR-036)

**Decision**: `models.validate_create_payload` gains two rules, inserted **after** the
`expires_in` rules and **before** the content-size rule, and returns a 4-tuple
`(content, expires_in, burn_after_reading, password)`.

| # | Rule | Violation | Requirement |
|---|---|---|---|
| … | *(rules 1-10 unchanged)* | | |
| 11 | if `burn_after_reading` present: `type(...) is bool` | `400` | FR-031 |
| 12 | if `password` present: `type(...) is str` | `400` | FR-033 |
| 13 | if `password` present: `1 <= len(password) <= 128` **characters** | `400` | FR-033 |
| 14 | `len(content.encode("utf-8")) <= 65_536` *(was rule 11)* | `413` | FR-007, FR-027, FR-036 |

**Rationale**:

- The size rule moving to last is FR-036 exactly: a submission carrying an invalid new field is
  reported as malformed (`400`), not as too large (`413`), while an otherwise-valid oversized
  submission still gets `413` (FR-027 preserved). This costs nothing — the rule was already last
  among the body rules, and the new rules are simply inserted ahead of it.
- `len()` on a `str` counts **characters**, which is the bound FR-033 specifies ("however many
  bytes it encodes to"). This is deliberately the opposite measure from `content`, which is bounded
  in encoded bytes (FR-007). The two are different for a reason and the tests assert both.
- `type(...) is str` and `type(...) is bool` rather than `isinstance`, per R-10: `isinstance(x,
  int)` would accept `True`, and `isinstance` generally would accept subclasses the JSON parser
  never produces but a future caller of the function might.
- An explicit `null` for either field is rejected, not treated as absence — the same rule the
  existing `expires_in` already applies (Edge Case "Marking is null").
- Which of two simultaneously-invalid new fields is reported is deliberately unspecified by the
  spec; the implementation reports `burn_after_reading` first by virtue of rule order, and the
  tests assert only that the status is `400` and nothing was created.

**Return shape**: a 4-tuple rather than a dataclass or dict. R-10 already rejected a wrapper
object for the 2-tuple; a fourth element does not change that calculus, and there is exactly one
caller.

**Note on the declared-body cap**: `MAX_BODY_BYTES` (66 560) is **unchanged**. A 128-character
password encodes to at most 512 bytes and the two new keys add roughly 50 more, well inside the
1 024-byte envelope slack, so no submission that was accepted before is refused now. Raising the
cap would itself be a change to existing behaviour, which FR-053 forbids.

---

## R-23: Where the new flags appear (FR-035, FR-037, FR-039)

**Decision**: `burn_after_reading` and `protected` are added to the `GET /pastes/<id>` JSON body
and **nowhere else**. The `201` creation body stays exactly `{id, delete_token, url}`; the
`/raw` body stays exactly the content bytes; no response header carries either flag on any route.

**Rationale**: FR-035, FR-037, and FR-039 say so individually, and the spec's Assumption "Flags
appear only in the structured read" says so collectively. The temptation to echo the flags in the
`201` ("so the client can confirm what it created") is exactly the speculative capability
Principle IV rejects, and it would break the three existing tests that assert the `201` body has
precisely three keys — tests SC-020 forbids weakening.

`protected` is computed as `record["password"] is not None`. It reports only *whether* a password
is required; no response, header, or process output ever contains the password, the stored hash,
the salt, or the iteration count (FR-038, SR-019).

Consequence for the existing suite: exactly three assertions change, each the "the structured
read has exactly these keys" set in `test_read.py`, `test_create.py`, and `test_persistence.py`.
SC-020 permits precisely this and nothing more; no test is deleted, weakened, skipped, or xfailed.

---

## R-24: Module placement of the new logic (Principle IV)

**Decision**: no new module. The four existing runtime modules absorb the feature along the seams
they already have:

| Module | Addition |
|---|---|
| `models.py` | password/burn constants and messages; `hash_password()`, `verify_password()`; the two new validation rules; `read_flags()`-style interpretation helpers for stored records |
| `store.py` | new-field interpretation inside `_load` (R-17); `consume_record()` (R-20) |
| `server.py` | header decoding (R-19); the read-path ordering (R-21); the two flags in the structured read (R-23) |
| `cli.py` | none — no new flag, no new option (spec Constraints) |

**Rationale**: a `passwords.py` or `auth.py` would be a module per concept rather than per seam,
and the concept is roughly forty lines. The pure, filesystem-free, socket-free character of
`models.py` is preserved — `hash_password` and `verify_password` touch nothing but their
arguments and `secrets`/`hashlib`, which keeps them directly unit-testable.

---

## R-25: Work and exposure bounds for the password path (SR-018, spec Assumptions)

**Decision**: accept, and state, that each read of a protected paste costs one PBKDF2 run
(~0.2 s of C time, O(1) memory), that attempts are neither throttled nor counted, and that the
only guess-resistance is the author's choice of password.

**Rationale**: the spec's Assumptions "No rate limiting on password attempts" and "Password
strength is the author's choice" settle this at the requirements level, and the service has no log
channel in which to record an attempt (FR-003). What SR-018 does require — that the work a single
request can provoke is bounded — holds: validation precedes hashing on create, a read performs at
most one KDF invocation and only after the paste has resolved live and protected, the iteration
count is bounded even if the stored record claims otherwise (R-17), and an absent header costs no
KDF at all (R-18). Nothing in the feature lets a caller provoke unbounded or caller-chosen work.

**Not adopted**: an attempt counter or lockout (stateful, needs durable per-paste state the spec
does not define, and a lockout is a denial-of-service lever against the author); a delay on
failure (adds latency without reducing offline guessing, and the 0.2 s KDF already dominates).

---

## R-26: Test strategy extension (Principle III, SC-020, SC-021)

**Decision**:

- Three new test modules — `tests/test_burn.py`, `tests/test_password.py`,
  `tests/test_compat.py` — following the existing one-file-per-requirement-cluster convention.
- `tests/test_requirement_coverage.py` extends its ranges to `FR-001 … FR-054` and
  `SR-001 … SR-020`. Because its `ID_RE` already matches three-digit ids and both new ranges are
  three digits, only the two `range()` bounds change. This keeps SC-021 an enforced gate rather
  than a claim: a new requirement with no test referencing it by id fails the suite.
- `tests/conftest.py` gains helpers only: a `password` keyword passthrough on `Service.create`
  (it already forwards `**extra` into the payload, so this needs nothing), and `get`/`request`
  wrappers that attach `X-Paste-Password`. The suite-wide `scan_response` gate is extended to
  assert that no response ever contains a password the suite has used, nor a stored salt or hash
  read back off disk (SC-017) — the same mechanism that already makes the `delete_token` guarantee
  suite-wide rather than per-test.
- Concurrency (FR-047, SR-016, SC-015) is tested as R-09's revocation test already is: N threads
  issuing the same read against one burn paste, asserting exactly one `200` with complete content
  and `N-1` `404`s, with no `403` and no `500`.
- Legacy-record compatibility (FR-051, SC-019) is tested by writing a record file by hand that
  carries only the five original keys, then reading it back — this is the "build that predates the
  feature" of the spec's Independent Test, expressed without needing the old build.

**Rationale**: every mechanism here already exists in the 001 suite; this decision is mostly a
statement that the feature does not get its own testing style. The one genuinely new piece is
extending `scan_response` to passwords, and it belongs there for the same reason the token scan
does: a guarantee asserted once per test is a guarantee only for the tests that remember to
assert it.

**Note on test runtime**: at ~0.2 s per verification, a suite with on the order of 50 protected
reads spends ~10 s in the KDF. That is accepted rather than designed around — lowering the
iteration count for tests would mean the tested configuration is not the shipped one, which is
exactly the kind of "secure in a configuration nobody runs" Principle V rejects.

---

## Resolved unknowns summary

| Unknown raised in Technical Context | Resolution | Decision |
|---|---|---|
| Which standard-library password hash, at which parameters | PBKDF2-HMAC-SHA-256, 600 000 iterations, 16-byte salt, 32-byte output | R-16 |
| How the verifier is stored without breaking existing records | Nested optional `password` object; absent ⇒ unprotected; malformed ⇒ paste does not exist | R-17 |
| How "constant-time" is achieved when inputs vary in length | Compare the derived 32-byte digests with `hmac.compare_digest` | R-18 |
| How a non-ASCII password survives an HTTP header | `latin-1` re-encode then UTF-8 decode; failure ⇒ `403` | R-19 |
| What makes single-read destruction atomic | `os.unlink` as the claim; content served only after it succeeds | R-20 |
| Where `403` sits relative to `404` and to consumption | 404 → 403 → claim → serve | R-21 |
| How FR-036's `400`-before-`413` precedence is achieved | New rules inserted before the size rule in the existing ordered validator | R-22 |
| Whether the new flags appear anywhere but the structured read | No | R-23 |
| Whether a new module is warranted | No | R-24 |
| Whether attempt throttling is in scope | No — settled by the spec's Assumptions | R-25 |
| How the coverage gate extends to the new ids | Two `range()` bounds in the existing gate | R-26 |

No `NEEDS CLARIFICATION` item remains open.
