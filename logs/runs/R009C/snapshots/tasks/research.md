# Phase 0 Research: Password reset by one-time token

**Feature**: `002-password-reset` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

## Scope of this document

The specification carries no `NEEDS CLARIFICATION` marker. Its clarification session of
2026-11-11 settled the five open questions (unlock-on-reset, `passwd` cancels a token,
concurrency scope, the `--ttl` ceiling, and what `reset-token` prints), and every one is
written into a requirement — FR-036b, FR-038a, FR-038b, FR-033, FR-032 respectively. The
Technical Context in [plan.md](./plan.md) therefore has no unknowns.

What Phase 0 has to settle is the second and third category of research task: best practice
for the standard library modules this feature newly depends on, and the design decisions the
specification deliberately leaves open — above all *how* a token is recorded so that FR-034b
("not recoverable from the store") and SC-014 hold, and *where* the new code goes without
adding a module (Principle IV).

Decision numbering continues the shipped feature's sequence, which ended at D-009 in
[`../001-accounts-cli/research.md`](../001-accounts-cli/research.md), so that every decision
identifier in the project stays unique. Measurements were taken on this development machine
(Python 3.13.17, pytest 9.1.1), the same machine the 001 numbers came from.

---

## D-010: Standard library modules — one addition

**Decision**: the feature adds exactly one module to the runtime inventory of D-001: `time`,
for `time.time()`. The three modules the token work needs beyond that — `secrets`, `hashlib`,
`hmac` — are already imported by `hashing.py`. No third-party import, no runtime dependency
declaration, no new dev dependency.

| Module | Used for | Requirement |
|---|---|---|
| `secrets` | `secrets.token_urlsafe(32)` — the token itself, from a CSPRNG | FR-034a |
| `hashlib` | `sha256` of the presented token for the stored fingerprint | FR-034b |
| `hmac` | `hmac.compare_digest` — constant-time fingerprint comparison | FR-034b |
| `time` | `time.time()` — the issue moment and the expiry judgement | FR-036d |

**Rationale**: Principle I. Every one of these is stdlib, and three of the four are already in
the package, so the dependency surface of the feature is a single new import.

**Alternatives considered**:

- `datetime.datetime.now(timezone.utc)` with ISO-8601 strings in the store — more readable on
  disk, but it costs a parse on every load, a format to validate, and a timezone question that
  epoch seconds do not have. Rejected under Principle IV; `time.time()` is one call and one
  JSON number.
- `time.monotonic()` for expiry — monotonic time is not comparable across processes (its zero
  point is arbitrary per boot), and FR-036d names the system clock explicitly. Rejected as
  incorrect, not merely different.
- `uuid.uuid4()` as the token — 122 bits of entropy, under the 128-bit floor of FR-034a, and
  uuid4 is not documented as drawn from a CSPRNG on every platform. Rejected.

---

## D-011: Token value — `secrets.token_urlsafe(32)`

**Decision**: each token is `secrets.token_urlsafe(32)`: 32 random bytes from the OS CSPRNG,
encoded URL-safe base64 without padding, giving a 43-character string drawn from
`[A-Za-z0-9_-]`.

**Rationale**: it satisfies all three clauses of FR-034a and both clauses of SC-015 directly
and measurably.

| FR-034a / SC-015 clause | How `token_urlsafe(32)` meets it |
|---|---|
| cryptographically secure source | `secrets` is the stdlib's CSPRNG-backed module; `token_urlsafe` wraps `token_bytes` |
| ≥ 128 bits of entropy | 32 bytes = **256 bits**, double the floor |
| printable ASCII, no whitespace, exactly one line | the alphabet is `A–Z a–z 0–9 - _`; no `+`, no `/`, no `=`, no space, no newline |
| ≥ 22 characters (SC-015) | **43** characters |
| differs from every other token issued | 256 bits: the chance of a repeat across every token this tool will ever issue is not physically reachable |

The "differs from every other token" clause of FR-034a is met by entropy, not by a uniqueness
register: keeping a list of previously issued tokens would mean storing them (against FR-034b)
or their fingerprints forever (unbounded state for no behavioural gain), so the requirement is
read as the probabilistic guarantee the entropy floor exists to provide.

**Alternatives considered**:

- `secrets.token_hex(16)` — 128 bits exactly, 32 hex characters. Meets the floor with no
  margin and is longer per bit. Rejected in favour of the larger margin at a similar length.
- `secrets.token_urlsafe(16)` — 128 bits, 22 characters. Exactly on both floors, which leaves
  SC-015's "at least 22 characters" assertion with no slack. Rejected: no reason to sit on the
  boundary.
- `secrets.token_bytes` + `base64.b64encode` — standard base64 contains `+`, `/` and `=`.
  All printable and whitespace-free, so it would pass, but `-`/`_` survive copy-paste through
  shells and URLs with less quoting risk for the administrator who has to pass the token on.

---

## D-012: Stored form — unsalted SHA-256, compared in constant time

**Decision**: the store records `sha256(token.encode("utf-8")).hexdigest()` — 64 lowercase hex
characters — and never the token. `reset` validates by hashing the presented line the same way
and comparing the two hex strings with `hmac.compare_digest`. No salt, no iteration count, no
password-style KDF.

**Rationale**: three requirements pull on this choice and this is the design that satisfies all
three.

1. **FR-034b / SC-014 (not recoverable)**: SHA-256 is a one-way transformation; the stored
   value is a 32-byte digest of a 256-bit random string. There is no dictionary to try, so
   nothing can be inverted and nothing read from the store can be replayed — feeding the
   recorded hex back to `reset` as the token simply hashes it again and fails to match, which
   is the second half of SC-014 asserted directly.
2. **FR-034b (constant-time)**: `hmac.compare_digest` is the stdlib's documented constant-time
   comparison, already used for password keys (FR-026c), so the token path reuses the mechanism
   the project already trusts rather than introducing a second one.
3. **SC-018 (`reset-token` performs no password derivation; `reset` performs exactly one)**: a
   SHA-256 of 43 bytes costs **0.5 µs** measured here, against **213 ms** for one PBKDF2
   derivation at 600,000 iterations. Fingerprinting is therefore free on both commands, and
   the one derivation `reset` performs is the one that writes the new password — after the
   token has been accepted, as SC-018 requires.

A salt and a slow KDF are what protect a *low-entropy* secret from offline guessing. A 256-bit
random token has no guessable distribution to attack, so stretching it would buy nothing and
would spend the derivation budget SC-018 pins. This is the standard treatment of
high-entropy bearer tokens, and the reasoning is recorded here because the project's other
secret (the password) is deliberately handled the opposite way.

**Alternatives considered**:

- **PBKDF2 at 600,000 iterations over the token**, reusing `hashing.new_password_material`.
  Rejected: it would make `reset` perform two derivations and `reset-token` one, contradicting
  SC-018 twice, in exchange for protection against an attack (guessing a 256-bit value) that
  is not available to anyone.
- **HMAC-SHA256 under a key** — there is nowhere to keep a key that is not the store file
  itself, so it reduces to the same thing with a second secret to manage. Rejected under
  Principle IV.
- **Storing the token in plaintext** — fails FR-034b and SC-014 outright.
- **Comparing with `==`** — fails FR-034b's constant-time clause. Against a digest of a
  high-entropy value the timing leak is not practically exploitable, but the requirement is
  explicit and `compare_digest` costs nothing.

---

## D-013: Token state lives inside the account record as one optional key

**Decision**: an account record gains one optional key, `reset_token`, holding a JSON object
with exactly three fields:

```json
"reset_token": {
  "token_hash": "9f2c…  (64 lowercase hex)",
  "issued_at": 1794427356.867,
  "ttl_seconds": 900
}
```

The key's **presence** is what "a token is outstanding" means. An account that has never had a
token issued does not carry the key at all, so a freshly registered record is byte-for-byte
what it is today (FR-039). The four ways a token ends are therefore all the same single
operation — remove the key — except expiry, which needs no write at all:

| Route | Implementation |
|---|---|
| spent by a successful `reset` (FR-036b, FR-036c) | `record.pop("reset_token")` as part of the same write that sets the new password |
| replaced by a later `reset-token` (FR-032) | assignment overwrites the key |
| cancelled by a successful `passwd` (FR-038a) | `record.pop("reset_token", None)` in the same write |
| discarded with the account by `delete` (FR-036g) | automatic — the record is removed, and nothing else holds token state |
| expired (FR-036d) | no write; judged on read from `issued_at + ttl_seconds` |

**Rationale**: the spec's own Assumptions already choose "token state lives with the account
record", and FR-036g is the requirement that forces it: if token state sat in a top-level
table keyed by username, `delete` would need a second removal and a username registered again
could inherit a stale entry — exactly the bug acceptance scenario 4.3 tests for. Nesting it in
the record makes that class of bug unreachable rather than merely tested, and keeps the store's
top-level shape and format marker untouched (FR-039).

**"Mark the token used" (FR-036b) is implemented as removal.** A `"used": true` flag would be
a second way to represent "no usable token", and every read would have to check both. Removal
satisfies the requirement's observable clause — "so that no later invocation will accept it
again" — exactly, with less state (Principle IV). Nothing in the spec asks for the history of
a spent token, and keeping a spent fingerprint would be data retained for no requirement.

**`issued_at` + `ttl_seconds`, not a precomputed `expires_at`.** The Key Entities section
describes a token that "carries the moment it was issued and the lifetime chosen for it, from
which its expiry follows", so the store mirrors that: the two facts chosen at issue time are
recorded, and the derived one is computed. It also keeps the stored `ttl_seconds` assertable
against what `--ttl` was given, which an `expires_at` would blur with the clock.

**Alternatives considered**:

- A top-level `"reset_tokens"` table keyed by username — rejected as above (FR-036g), and it
  would change the store's top-level shape that FR-039 freezes.
- A `used` / `spent` flag with retention — rejected under Principle IV, as above.
- Storing `expires_at` only — rejected as above; it also makes an `issued_at`-based assertion
  impossible without inverting the arithmetic in the test.
- A list of outstanding tokens per account — explicitly ruled out by FR-032 ("exactly one
  valid token per account") and by the spec's Assumptions.

---

## D-014: `--ttl` parsing — located by scan, accepted only as strict decimal digits

**Decision**: `--ttl` joins `--store` in the hand-rolled scan of D-002. It may appear anywhere
relative to the positionals; only the space-separated `--ttl SECONDS` form is accepted; a
second `--ttl`, a missing value, a value that is not a non-empty string of ASCII decimal digits
`0`–`9`, or a value outside 1–86400 inclusive, is a usage error — the single usage line of
FR-040 on stderr, exit 2, no store file created or modified. `--ttl` supplied with any command
other than `reset-token` is likewise a usage error. Absent, the lifetime is 900 seconds.

**Rationale**: FR-033 requires all of that, and the usage-error answer is the spec's own
Assumption ("a malformed `--ttl` is a usage error, not a new message"), so no message joins the
inventory. Validating during parsing — before the store is loaded — is what makes "no store
file created or modified" true for free, and matches the global check order of FR-037.

**The digit test cannot be `int()` or `str.isdigit()`.** Both were measured on this machine:

| Candidate value | `int(v)` | `v.isdigit()` | Required outcome | Verdict |
|---|---|---|---|---|
| `"1_0"` | `10` — underscores are accepted in numeric literals *and* in `int()` | `False` | usage error | `int()` alone is **wrong** |
| `"²"` (superscript two) | `ValueError` | **`True`** | usage error | `isdigit()` alone is **wrong** |
| `"١٢"` (Arabic-Indic) | `12` | `True` | usage error | both are **wrong** |
| `" 5"`, `"+5"`, `"5.0"`, `"0x10"`, `""` | error or wrong value | `False` | usage error | — |

So the test is explicit: non-empty, and every character in `"0123456789"`, then `int()`, then
the 1–86400 range check. This is the kind of silent coercion Principle II forbids, and the
table is recorded because two plausible one-liners both get it wrong.

**`--ttl 86401` and `--ttl 99999999999999999999` are refused, not clamped** (FR-033, and the
spec's Assumption on the ceiling): an administrator is never left believing a lifetime they did
not get. `--ttl 1` and `--ttl 86400` are both accepted, so the tests pin both edges.

**Alternatives considered**:

- `argparse` with `type=int` — rejected for the same reason as D-002, and `type=int` would
  accept `1_0` and print its own error text.
- Clamping an over-large value to 86400 — rejected: silent coercion (Principle II).
- A distinct message such as `invalid ttl` — rejected by the spec's Assumption; it would
  enlarge the pinned message inventory for no new information.

---

## D-015: Expiry judged against `time.time()`, boundary exclusive, no clock seam in runtime code

**Decision**: `reset-token` records `issued_at = time.time()` (a float, epoch seconds).
`reset` refuses the token when `time.time() >= issued_at + ttl_seconds`. No clock abstraction,
no injectable now-function, and no attempt to detect or compensate for the clock moving.

**Rationale**: FR-036d names the system clock at the moment of use; the spec's Assumptions make
the boundary exclusive ("a token presented at exactly *t + s* is expired") and rule out clock
handling and any network time source (Principle I, no hidden I/O). A float keeps sub-second
precision, which matters for the `--ttl 1` case: truncating to whole seconds would make a
one-second token expire up to a second early or late depending on where in the second it was
issued.

**How this is tested without sleeping for 900 seconds** — this is the one testability question
the feature raises, and it is answered without adding a seam to runtime code:

1. **Real elapsed time, once**: `--ttl 1`, sleep ~1.1 s, assert `invalid token` / 1. This is
   the end-to-end truth and costs about a second of the 60-second suite budget (SC-018).
2. **The 900-second default and the within-lifetime direction**: the test rewrites
   `issued_at` in the store file to a chosen point in the past and runs `reset`. The store file
   is a documented contract ([contracts/store-file.md](./contracts/store-file.md)), the suite
   already writes raw store documents for the corruption tests via the `write_store` fixture,
   and a store whose `issued_at` is older than the tool has been running is indistinguishable
   from one written by an earlier invocation. This covers SC-013 in both directions — accepted
   at `ttl - 1` elapsed, refused at `ttl` elapsed and beyond — in milliseconds.

**Alternatives considered**:

- A `_now()` indirection in runtime code for tests to monkeypatch — rejected under Principle
  IV: an extension point introduced for the test suite, when rewriting the recorded
  `issued_at` exercises the real code path with no production indirection at all.
- `monkeypatch.setattr(time, "time", ...)` globally in the in-process runner — works, but
  patches a stdlib module for the duration of a test that also does file I/O and derivation,
  which is a broader blast radius than editing one number in a fixture file.
- Freezing or faking the clock with a library — a third-party dependency; forbidden by
  Principle I's dev-dependency clause (the exemption is `pytest` and the stdlib only).

---

## D-016: No new module — the feature lands in the three that exist

**Decision**: no fourth functional module. The ~40 lines of new runtime code are placed along
the axes the shipped package already splits on:

| Code | Module | Why this module |
|---|---|---|
| `new_token()`, `token_fingerprint(token)`, `verify_token(stored, presented)` | `hashing.py` | it *is* the cryptography module: `secrets`, `hashlib`, `hmac` and `compare_digest` are already there, and the token functions are the same kind of thing as `new_password_material` / `verify` |
| validation of the `reset_token` object on load | `store.py` | it is the format-validation module; FR-039 makes malformed token state a corrupt store, which is `store.py`'s existing job |
| `--ttl` parsing, the two handlers, the two new messages, the new usage line, the `passwd` cancellation | `cli.py` | argument surface, dispatch, messages and statuses are all `cli.py`'s existing job |

**Rationale**: Principle IV requires the smallest design, and the 001 plan's Structure Decision
already rejected a layered layout for this project. A `tokens.py` would hold three short
functions that need exactly the imports `hashing.py` already has, and would split the
"cryptography" axis in two for no requirement. Naming mirrors the existing pair deliberately —
`verify_token` sits beside `verify`, so the constant-time comparison is in one module and one
reviewer's field of view.

**Alternatives considered**:

- `src/accounts/tokens.py` — rejected as above. It is the choice to revisit if token state ever
  grows a second shape; nothing in this spec asks for one.
- Folding the token functions into `cli.py` — rejected the other way: it would put a CSPRNG
  draw and a digest comparison in the module that is about messages and statuses, and leave the
  constant-time compare outside the module whose whole purpose is that discipline.

---

## D-017: The handler signature gains `ttl`; `PASSWORD_LINES` becomes `INPUT_LINES`

**Decision**: the uniform handler signature becomes
`handler(data, store_path, username, inputs, ttl, stdout, stderr) -> int`. Every handler takes
`ttl`; only `_reset_token` reads it. The input-count table `PASSWORD_LINES` is renamed
`INPUT_LINES` and gains two rows:

| Command | Lines read |
|---|---|
| `reset-token` | 0 (FR-034) |
| `reset` | 2 — the token, then the new password (FR-035) |

**Rationale**: one uniform signature with one unused parameter in five handlers is smaller than
any alternative that routes the value only to the handler that wants it — a per-command options
object, a partial application, or a closure are all an abstraction introduced to avoid passing
an integer. The rename is because `reset`'s first line is a token, not a password, so the old
name would be actively misleading at the one place a reader checks the input protocol; it is a
module-private name, referenced by no test (verified), so FR-041 and SC-010 are untouched.

**Note on `_read_passwords`**: the function is unchanged and keeps its no-strip,
line-break-only behaviour, which is exactly what FR-035 requires for both of `reset`'s lines —
so a token with surrounding spaces is not the issued token (`invalid token` / 1), and an empty
token line is a 0-length token rather than missing input. The existing reader already gives the
new command the right semantics with no edit at all.

---

## D-018: Check order, and where the single derivation happens

**Decision**: the two commands plug into the existing global order with no change to the
pipeline: argument parsing (2) → store load (5) → read the command's input lines (2) → the
command's own checks. Within `reset`: account exists (3) → token valid (1) → password length
(2) → success (0).

**Rationale**: FR-037 states the global order and FR-036a the local one, and the pipeline in
`cli.main` already imposes the global order on every command, so `reset` inherits it by being
a handler. Three consequences worth recording because tests must assert them deliberately:

- **A wrong token *and* a too-short password exits 1**, not 2 — the token is judged first
  (FR-036a, acceptance scenario 3.3).
- **Missing input beats a non-existent account**: `reset nobody` with empty stdin is
  `missing password input` / 2, not `no such account` / 3, because input reading precedes
  dispatch (FR-036, and the spec's edge case says so explicitly).
- **A corrupt store beats everything**, so `reset` against an unreadable store is 5 even when
  the username does not exist (FR-037: "MUST NOT be treated as an empty store"). This is the
  same precedence the 001 plan flagged for `register`.

**Derivation budget (SC-018)**: `reset-token` calls nothing in the derivation path — it draws
32 random bytes and takes one SHA-256. `reset` calls
`hashing.new_password_material` exactly once, after the token has been accepted and the length
check has passed, so a refused token and a short password both cost zero derivations. Measured
from the 001 figures: `reset-token` ≈ 30 ms (interpreter start plus file I/O), `reset` ≈ 245 ms
(one 213 ms derivation), both inside the 1-second per-command budget. No command performs a
derivation per account, so neither grows with store size beyond reading and rewriting the file.

---

## D-019: Impact on the shipped suite — two string literals

**Decision**: the only edit to existing tests is the usage-line literal, in the two places that
pin it in full:

| File | Line | Change |
|---|---|---|
| `tests/test_cli_contract.py` | 14–17 | the `USAGE` constant → the FR-040 string |
| `tests/test_success_criteria.py` | 19–22 | the `USAGE` constant → the FR-040 string |

Two further assertions use `err.startswith("usage: python -m accounts")`
(`tests/test_store_file.py` lines 513 and 742) and need no change. No other existing assertion
is touched, weakened or deleted (SC-010). The `COMMANDS` list in `test_cli_contract.py` stays
at the five existing commands: it drives the unchanged-behaviour tests, and the two new
commands get their own coverage in new files rather than being folded into assertions written
about the old ones.

**Rationale**: FR-040 is declared the single visible change to any existing command, and
FR-041 freezes everything else, so the size of this table is itself the evidence for both. If
implementation turns out to require a third edit to an existing test, that is a signal the
change has leaked past FR-041 and must be re-examined rather than accommodated.

---

## D-020: Deliberately out of scope

Recorded so each absence is a decision rather than an oversight, and so a reviewer can check
them against Principle IV.

| Not built | Why |
|---|---|
| Rate limiting or an attempt counter on wrong tokens | 256-bit entropy makes guessing infeasible (FR-034a), FR-036e requires a refusal to leave the token armed, and a counter would hand an attacker a way to deny a legitimate reset — the spec's Assumptions say so |
| A lock file or any inter-process locking | FR-038b keeps 001's concurrency scope; locking would add platform-specific machinery to the write path FR-041 freezes, to serve a case the project excludes |
| Printing the expiry time on `reset-token` | FR-032 as clarified: the token alone on one line, nothing else on either stream, so the output stays usable from a script |
| A `revoke-token` or `list-tokens` command | No requirement asks for one; `passwd` and a replacement `reset-token` already end a token, and FR-031 fixes the command set at seven |
| Clock-skew detection, NTP, or a monotonic cross-check | Ruled out by the spec's Assumptions and by Principle I / no hidden I/O |
| A store format bump or a migration step | Forbidden by FR-039; the new key is optional, so v1 stores load unchanged |
| Token state for anything but passwords (e-mail, delivery, audit log) | No requirement; FR-044 confines the token to the `reset-token` invocation's stdout and the store path |

---

## Summary of new decisions

| ID | Decision |
|---|---|
| D-010 | One new stdlib import: `time`. `secrets`, `hashlib`, `hmac` already present |
| D-011 | Token is `secrets.token_urlsafe(32)` — 256 bits, 43 printable ASCII characters |
| D-012 | Stored as unsalted SHA-256 hex, compared with `hmac.compare_digest`; no KDF on the token |
| D-013 | Optional `reset_token` object inside the account record; presence means outstanding; spending is removal |
| D-014 | `--ttl` located by scan, strict decimal digits only, 1–86400, otherwise the usage line and exit 2 |
| D-015 | `time.time()`, exclusive boundary, no clock seam; expiry tested by one real sleep plus a rewritten `issued_at` |
| D-016 | No new module: `hashing.py` for token crypto, `store.py` for validation, `cli.py` for the surface |
| D-017 | Handler signature gains `ttl`; `PASSWORD_LINES` renamed `INPUT_LINES` with two new rows |
| D-018 | Existing global check order inherited; one derivation in `reset`, none in `reset-token` |
| D-019 | Two usage-line literals in the shipped suite change; nothing else |
| D-020 | Rate limiting, locking, expiry output, revoke/list commands, clock handling, format bump: out |
