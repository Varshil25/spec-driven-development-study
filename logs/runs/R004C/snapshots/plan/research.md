# Phase 0 Research: Password Reset by One-Time Token

**Feature**: `002-password-reset` | **Date**: 2026-11-05

Continues the numbering of
[feature 001 research](../001-user-accounts-cli/research.md) (R1 … R10), whose
decisions all remain in force. This file records only what feature 002 adds or
has to reconcile.

## Purpose

The specification carries no `NEEDS CLARIFICATION` marker, and the planning
input fixes the three things a plan would otherwise have to choose:

- **Language/runtime**: Python 3.11 or newer, standard library only (also A-013,
  Principle I).
- **Interface**: exactly as the specification states it — `reset-token` and
  `reset` under the existing `--store PATH COMMAND USERNAME` form, with
  `--ttl SECONDS` on `reset-token` only.
- **Testing**: `pytest`, a development-only dependency (Principle I).

So Phase 0 is not about resolving unknowns in the request. It is about the
decisions the specification deliberately leaves to the plan — how a token is
generated, what is recorded against an account, how an instant is represented,
and in what order the checks run — plus one reconciliation the existing code
forces (R18) and one budget that turns out to be tight (R20).

Host for every measurement below: CPython 3.13.17, Linux 6.18, x86-64 —
the same host as feature 001's R8.

---

## R11 — Token generation: source, entropy, alphabet, length

**Decision**: `secrets.token_urlsafe(16)` — 16 bytes from the OS CSPRNG,
rendered as 22 characters of the URL-safe base64 alphabet
(`A–Z a–z 0–9 - _`) with the padding stripped. Exposed as
`crypto.new_token()` with `crypto.TOKEN_BYTES = 16`.

**Rationale**:

- `secrets` is the stdlib's CSPRNG facade over `os.urandom`, which is what
  SR-014 names. `random` is excluded by the same requirement and the test suite
  asserts the package never imports it.
- 16 bytes is **exactly** the 128 bits SR-014 demands ("at least 128 bits"), and
  A-023 says the length "follows from the 128-bit entropy requirement" — so the
  spec itself points at the minimum rather than at a margin. The result is 22
  characters, short enough to read over the phone and paste into a shell, which
  is the hand-off A-014 describes.
- The alphabet satisfies A-023 and SR-011 by construction: every character is
  printable ASCII, none is whitespace, none is a quoting character, none is a
  control character, and none can begin a terminal escape sequence. Printing
  the token therefore cannot forge an extra line of output or move the cursor.
- Verified on the host: `len(secrets.token_urlsafe(16)) == 22`, the value
  base64url-decodes to exactly 16 bytes, and 10 000 tokens generated in one
  process were all distinct (0.013 s) — which is how SC-016 is checked without
  10 000 subprocess invocations.

**Alternatives considered**:

- `secrets.token_hex(16)` — 32 characters for the same 128 bits. Rejected:
  longer to transcribe for no gain.
- `secrets.token_urlsafe(32)` — 256 bits, 43 characters. Rejected: SR-014's
  bound is 128 bits and the extra 21 characters make the hand-off worse.
  Changing `TOKEN_BYTES` later is a one-constant change and no requirement
  depends on 16.
- A hand-rolled alphabet via `secrets.choice` over a custom character set.
  Rejected under Principle IV: the stdlib already has the exact function, and a
  hand-rolled loop is where an off-by-one in the entropy accounting lives.

---

## R12 — What is recorded against the account

**Decision**: one optional record key, `reset`, holding a nested object with
exactly eight keys — the same seven credential fields a password record carries
(`kdf`, `n`, `r`, `p`, `dklen`, `salt`, `hash`) plus `expires_ms`. The token
itself is never written. The digest is `scrypt` at the module's **current**
parameters over the token text, with a fresh 16-byte `secrets` salt per
issuance.

```json
"alice": {
  "kdf": "scrypt", "n": 131072, "r": 8, "p": 1, "dklen": 32,
  "salt": "…", "hash": "…", "failed_logins": 0,
  "reset": {
    "kdf": "scrypt", "n": 131072, "r": 8, "p": 1, "dklen": 32,
    "salt": "…", "hash": "…", "expires_ms": 1762300000000
  }
}
```

**Rationale**:

- SR-013 requires "a salted digest of the token produced by the same
  deliberately slow algorithm and current parameters already used for
  passwords, with a fresh salt per issued token". Mirroring the password field
  set is the literal reading of that, and it makes `crypto.verify(token,
  record["reset"])` work **unchanged** — `verify` already reads exactly
  `salt`, `n`, `r`, `p`, `dklen`, `hash` from the mapping it is handed and
  already compares with `hmac.compare_digest`. No new cryptographic code is
  written for this feature; `crypto` gains only `new_token`.
- One key makes the three lifecycle operations single expressions:
  issue is `record["reset"] = …` (which *replaces*, satisfying FR-029 and A-015
  structurally rather than by a check), consume is
  `record.pop("reset", None)`, and "has no outstanding token" is
  `"reset" not in record`.
- The field set is fixed and so is its serialised size — 174 bytes per record,
  measured — which is what FR-043 and SR-015 require: no account record can
  grow without limit. Worst case measured: 10 000 accounts each carrying reset
  material serialises to 3 440 027 bytes, comfortably inside the existing
  8 MiB store cap, so the A-011 limits continue to bound the file with no new
  limit needed.
- Optionality is what delivers FR-041: a record written before this feature has
  eight keys and no `reset`, which is a valid record under the extended rule.

**Alternatives considered**:

- **Eight flat keys** (`reset_kdf`, `reset_n`, … `reset_expires_ms`).
  Constitution Principle IV prefers a flat structure to a nested one, so this
  was the default. Rejected because `crypto.verify` would then need either a
  key-prefix parameter or a projection dict built at the call site — new code on
  the one path where SR-014's constant-time comparison lives — and because
  "replace the token" and "consume the token" become eight-key operations where
  forgetting one leaves half a token behind. The deviation is recorded in the
  plan's Complexity Tracking with this requirement as its justification.
- **Storing the token in plaintext** with only an expiry. Rejected outright:
  SR-013 and constitution rule 4 forbid it, and the store is exactly the file
  an attacker who can read the store already has.
- **A single unsalted SHA-256 of the token**, on the argument that 128 bits of
  entropy makes a dictionary attack pointless. Rejected: SR-013 names the slow
  algorithm and a fresh salt, and Principle IV explicitly does not permit
  simplifying away a Principle V control. The cost is one derivation, which
  R20 budgets.
- **A separate top-level `resets` object** in the document, keyed by username.
  Rejected: it duplicates the account key, admits a token for a username that
  does not exist, and makes `delete` responsible for cleaning up a second place
  (FR-042) instead of the token simply going with the record.

---

## R13 — Representing the expiry instant

**Decision**: `expires_ms` — an **integer** count of milliseconds since the Unix
epoch, computed at issuance as `int(time.time() * 1000) + ttl * 1000`, and
validated on load as an integer in `1 … 253402300799000`. A token is valid iff
`int(time.time() * 1000) <= expires_ms`, evaluated at the moment of the
attempt.

**Rationale**:

- **Why an integer, not a float.** SR-010 states the trap directly: "a malformed
  expiry MUST NOT be treated as 'not expired'". `json` accepts and emits
  `NaN`, and `NaN <= x` is `False` — a `NaN` expiry in a hand-edited store
  would read as *never expired*, which is the exact failure SR-010 names. An
  integer field with `type(v) is int` and a range check (the discipline
  store-format.md already uses, including its explicit rejection of `bool`)
  has no such value. Integers also keep the store byte-deterministic, which is
  what lets SC-021 be a byte comparison.
- **Why milliseconds, not whole seconds.** Whole seconds cannot satisfy the
  spec's own boundary cases together. SC-014 requires a token to be "accepted
  before its validity has elapsed and refused after it", and scenario 2.4
  requires a 1-second token to be refused once "more than 1 second has since
  elapsed". With second truncation a 1-second token issued at `t = 10.9` expires
  at `11`, so it is still accepted at `t = 11.5` — 0.6 s *after* its validity
  elapsed — and rounding the other way refuses it early, breaking scenario 1.5
  and "a token redeemed in the same second it was issued is valid".
  Millisecond resolution bounds the error at 1 ms, under which every boundary
  scenario in the spec holds as written.
- **Why the name carries the unit.** `expires` would invite a reader — or a
  later maintainer comparing against `time.time()` — to assume seconds and be
  wrong by a factor of 1 000, which is a silent wrong answer (Principle II).
- **Why absolute, from `time.time()`.** A-024 fixes this: an absolute instant
  recorded at issue, compared against the system clock at each attempt, with a
  clock the operator can move declared out of scope. `time.monotonic()` is
  unusable here because it is not comparable across processes, and the two
  operations are by design separate invocations.
- **Range bound.** `ttl ≤ 86 400` (A-016) means the arithmetic adds at most
  86 400 000, so an expiry computed from any accepted `ttl` is far inside the
  bound; the load-time upper bound of `253402300799000` (end of year 9999)
  exists to refuse a stored value that could only have been hand-written, and
  discharges SR-015's "no arithmetic on it can overflow or produce a value
  outside the store's accepted range". Python integers do not overflow, so the
  requirement is really about range *validation*, which is where this is done.

**Alternatives considered**:

- Integer **seconds** — simplest and matches the spec's unit, but fails the
  boundary scenarios above.
- A **float** POSIX timestamp — right resolution, but the `NaN`/`Infinity`
  hazard SR-010 calls out, plus a serialisation-determinism wrinkle.
- An **ISO-8601 string** — human-readable in the store, but needs
  `datetime.fromisoformat` parsing on the validation path (a new failure mode
  per load) and invites timezone ambiguity. Rejected under Principle IV.
- Storing **`issued_ms` + `ttl`** and deriving the expiry. Rejected: it stores
  two fields to answer one question and adds an arithmetic step on the
  authorisation path, where SR-016 wants the fewest.

---

## R14 — Ordering of checks for the two new operations

**Decision**: `reset` follows FR-033 literally; `reset-token` follows the
analogous order. Both are asserted by a dedicated precedence test.

`reset`:

| # | Check | Failure |
|---|---|---|
| 1 | username rules (FR-011) | 2 |
| 2 | read the token line, then the new-password line | 2 |
| 3 | acquire the directory lock, load and validate the store | 5 |
| 4 | the account exists | 3 |
| 5 | an outstanding token exists, is unexpired, and matches | 1 |
| 6 | the new password satisfies FR-012 | 2 |
| 7 | apply: new digest, token consumed, count zeroed, lock cleared, store written | 0 |

`reset-token`:

| # | Check | Failure |
|---|---|---|
| 1 | argument shape: `--ttl` present at most once, and only with `reset-token` | 2 |
| 2 | username rules (FR-011) | 2 |
| 3 | `--ttl` value: format then range (FR-022) | 2 |
| 4 | acquire the directory lock, load and validate the store | 5 |
| 5 | the account exists | 3 |
| 6 | issue: fresh token, fresh salt, digest, expiry, store written, token printed | 0 |

**Rationale**:

- Steps 1–2 of `reset` run **before** the store is touched, which is what makes
  an over-long token line a status-2 bad request (spec edge case "Over-long
  token line") rather than something compared against a record, and what makes
  "missing input against an unreadable store" report the missing input.
- Step 5 **before** step 6 is scenario 3.4 stated as an order: an expired token
  with an 11-character password answers `invalid token` (1), not a password
  error (2). The password line is *read* at step 2 but *judged* at step 6.
- Step 6 before step 7 is scenario 3.1 and FR-036: the refusal happens with the
  token still outstanding and its original expiry untouched, because nothing has
  been written yet.
- `reset-token` validates the username before the `--ttl` value so that the two
  new operations agree with the five existing ones on which status an invalid
  username produces first; the only shape checks ahead of it are the ones
  argparse necessarily performs on argv before any handler runs.
- There is **no lock check** in either table. FR-031, FR-039 and A-018 require
  the lock to restrict `login` only, exactly as FR-019 already has it for
  `passwd` and `delete`, so status 4 is unreachable from both new operations
  (FR-024).

**Alternatives considered**: validating the new password before the token
(status 2 ahead of status 1). Rejected — it contradicts scenario 3.4 and leaks
whether a token is outstanding, because the two statuses would then distinguish
"valid token, bad password" from "bad token, bad password".

---

## R15 — `--ttl` inside the existing argparse shape

**Decision**: add `--ttl` to the one existing parser as
`action="append"`, `default=None`, with **no** `type=` converter, so the raw
string reaches the handler. Keep `allow_abbrev=False` and `add_help=False`.
After parsing: more than one occurrence, or any occurrence with a command other
than `reset-token`, raises the usage error (status 2). The value is validated by
`validation.validate_ttl`.

**Rationale**:

- `allow_abbrev=False` is already set, so `--tt` and `--t` are errors with no
  extra code — FR-021's "MUST NOT be abbreviated".
- `action="append"` plus a length check is the pattern `--store` already uses
  for "given more than once is a shape error, not last-one-wins" — FR-021's
  "MUST NOT be given more than once". Reusing the existing pattern is cheaper
  than introducing a second one.
- **No `type=int`.** argparse would turn a bad value into its own message and
  its own exit path, and FR-022 requires a message that "names what was expected
  and what was received". Taking the raw string and validating it in
  `validation` keeps that message in the one place the project writes messages,
  and keeps the check order of R14 explicit rather than implicit in argparse.
- The "only with `reset-token`" rule is enforced after parsing rather than by a
  second parser or a subparser tree, because a subparser would restructure the
  argv handling of all seven commands — a change with blast radius across
  FR-040, for one option.
- `validate_ttl` accepts `re.fullmatch(r"[0-9]{1,5}", text)` and then
  `1 <= int(text) <= 86400`. The regex is checked **before** `int()`, which
  matters more than it looks: `int()` accepts Unicode decimal digits
  (`int("１２") == 12`), surrounding whitespace, and a leading `+`/`-`, none of
  which is "a whole number of seconds" written plainly. Bounding the match at
  five digits also bounds the conversion cost (SR-015) and makes
  `--ttl 100000` a format refusal while `--ttl 99999` is a range refusal —
  both status 2. The pattern is a bounded character class with no alternation
  or nesting, so its cost is linear (SR-015).
- `--ttl -5`: the parser declares no option that looks like a negative number,
  so argparse passes `-5` through as the option's value and `validate_ttl`
  refuses it. Asserted rather than assumed.

**Alternatives considered**: `argparse` subparsers per command (restructures
everything for one option); a positional optional `SECONDS` (the spec names the
option `--ttl`, and the planning input says follow the interface exactly);
`type=int` with a custom `ArgumentTypeError` (argparse reformats the text, so
the contract's message table stops being literally true).

---

## R16 — Reading the token line

**Decision**: factor the body of `cli.read_password_line` into
`cli.read_line(kind, missing_message)` and keep `read_password_line` as a
two-line wrapper that passes `kind="password"` and the **byte-identical**
message it emits today. `reset` calls `read_line("token", …)` then
`read_line("password", …)`.

**Rationale**:

- A-022 says the token line is read and bounded exactly as a password line is,
  so the mechanism is already written and already tested: one
  `sys.stdin.buffer.readline(MAX_LINE_BYTES + 1)`, which never asks for more
  than the cap and so refuses an over-long line without loading or truncating
  it (feature 001 R5, FR-014, SR-015).
- The messages must differ. "error: password line too long" on a refused *token*
  line would misreport which line was at fault — a Principle II problem, not a
  cosmetic one. Parameterising `kind` yields `error: token line too long: …`
  and `error: token line is not valid UTF-8 text` from the same code path.
- The missing-input message is passed in rather than derived because `reset`'s
  is not of the existing shape: it names both lines in order
  (`error: missing reset input: expected a token line then a new password line
  on stdin, received N line(s)`), which is what scenario 4.6 asks to be
  reported — the stream being empty and the stream ending after the token line
  are distinguished by `N`.
- Because `read_password_line` keeps its signature and emits the same bytes,
  no existing command's output changes (FR-040). This is the only edit this
  feature makes to code any of the five existing commands executes, and it is
  a pure extraction — the reason FR-040 is checkable by running the 001 suite
  unchanged (SC-019).

**Alternatives considered**: calling `read_password_line` from `reset` and
accepting "password" in a token message (rejected: misreports the fault);
duplicating the whole reader for tokens (Principle IV tolerates duplication,
but this is the second occurrence of a *security control* — the byte cap — and
two copies of a cap is how one of them later drifts).

---

## R17 — Making every refusal indistinguishable, including by stopwatch

**Decision**: every refused-token path spends **exactly one** scrypt derivation
before answering, and answers with the identical byte string `invalid token` and
status 1. Where there is nothing real to verify — no `reset` key at all, or an
expired one — the derivation is `crypto.dummy_verify(token)`, the function
feature 001 already uses on `login`'s unknown-account path.

**Rationale**:

- SR-018 and SC-018 require a wrong, used, replaced or expired token — and an
  account that never had one — to be externally identical in message, status
  and stdout. Those are satisfied by the fixed string and the single status.
- They do not mention timing, but without the dummy derivation the paths differ
  by ~0.4 s (R20), which tells a caller whether a reset is in progress for an
  account — precisely the state SR-018 says output must not reveal. Spending the
  derivation closes it using a mechanism already in the package, with no new
  code and no new concept. It is also the same decision 001 made for SC-004,
  so the two refusal families behave alike.
- "Already used" needs no special case: a consumed token's `reset` key is gone,
  so it takes the no-token path and is identical to it by construction rather
  than by matching two message strings.
- The account-does-not-exist path is **not** made uniform with these: A-021 and
  FR-024 put it at status 3 on purpose, and A-021 records that this is a
  deliberate departure from `login`'s enumeration resistance, scoped to callers
  who can already read the store.

**Alternatives considered**: returning early when there is no token (leaves the
timing oracle); distinct messages per refusal reason, which would be friendlier
to the operator and is what Principle II would otherwise favour — overruled
explicitly by SR-018 and FR-026, and noted here so the omission reads as
deliberate.

---

## R18 — Store compatibility in both directions

**Decision**: the record validator's field set becomes "exactly the eight
existing keys, **plus** an optional `reset`"; the `reset` object is then
validated against its own exact eight-key allow-list with the same per-field
type and range rules. `version` stays `1`. Nesting depth of a valid store
becomes 4.

**Rationale**:

- FR-041 requires an old store to load with every account simply having no
  token. Making `reset` optional is the whole mechanism; nothing migrates and
  nothing is rewritten on load.
- **`version` is deliberately not bumped.** The honest argument for bumping it
  is that the format changed. The argument against, which wins: `version` is
  defined by 001's store-format contract as the compatibility mechanism in
  the *forward* direction only — a store whose version the reader does not
  recognise is status 5, never best-effort. Bumping to `2` would therefore make
  every pre-existing store (`version: 1`) **unloadable**, which is a direct
  FR-041 violation. The change is additive and optional, so a version 1 store
  written by either generation of the tool is readable by this one.
- The cost is the asymmetry A-026 already records and accepts: the *previous*
  build validates against a closed eight-key set, so it reports a store
  carrying an outstanding token as malformed (status 5) rather than
  misreading it. Loud, not silent — which is the behaviour Principle II wants
  from a downgrade, and better than what a version bump would give (an equally
  loud failure, but for *every* store rather than only the ones with a token
  outstanding). Downgrading is out of scope by A-026.
- Validating the nested object against a closed field set, rather than
  skipping unknown keys inside it, is SR-010: an account record whose reset
  material fails validation is status 5 and is never repaired, guessed at or
  ignored. In particular a `reset` object missing `expires_ms`, or carrying a
  non-integer one, fails the load — it does not default to "not expired".

**Alternatives considered**: bump `version` to 2 (breaks FR-041, as above);
accept `reset` with a relaxed interior so old and new tools interoperate
(violates SR-010's allow-list rule and A-026's explicit non-goal); write reset
material to a sidecar file so the store format never changes (violates SR-017's
"no spool, no audit log, no sidecar" and loses atomicity across the two files).

---

## R19 — Single use under simultaneous redemption

**Decision**: no new mechanism. Both operations perform their entire
read–modify–write inside the existing `store.locked_store(path)` context, with
the token verification, the password replacement and the token consumption all
inside the same critical section.

**Rationale**:

- SR-016 requires the check and the change to be in one invocation and
  serialised against other invocations "so that no interleaving lets one token
  set two passwords and no concurrent issuance leaves two tokens outstanding
  for one account". The existing lock is an exclusive `fcntl.flock` on the
  store's *directory*, held across load → mutate → `os.replace` (001 R4), which
  is exactly that guarantee.
- Because the token is consumed by `record.pop("reset", None)` inside the same
  locked section that verified it, the second of two simultaneous redemptions
  loads a store with no `reset` key and takes the no-token path: one success,
  one `invalid token`, status 1 (FR-035, SC-023).
- Concurrent issuance is serialised by the same lock, and `record["reset"] = …`
  overwrites, so "at most one outstanding token" (FR-029, A-015) holds under
  interleaving without a check.
- Crash safety (SC-024) likewise needs nothing new: the token record is part of
  the one document replaced by `os.replace` after an `fsync`, so a kill at any
  point leaves the complete old or the complete new store (001 R3).

**Alternatives considered**: a per-account lock file (new file, violates SR-017
and adds a cleanup path); an optimistic compare-and-swap on the serialised
bytes (a second mechanism for a problem the existing lock already solves).

---

## R20 — Performance budget, and a flagged tightness

**Decision**: proceed at the unchanged scrypt work factor and accept that
`reset` sits at roughly 1.2× headroom against SC-022's absolute one-second
bound on this host. Test the absolute bound *and* a hardware-independent
assertion that the store-size component is negligible.

**Measured on the host** (CPython 3.13.17, Linux 6.18, x86-64):

| Component | Cost |
|---|---|
| One scrypt derivation at `n=2**17, r=8, p=1` | **0.399 s** |
| JSON parse, 1 000 accounts all carrying reset material (344 027 B) | 0.0025 s |
| Serialise, same document | 0.0036 s |
| Reset material, serialised, per record | 174 B (fixed) |
| 10 000 accounts all carrying reset material | 3 440 027 B (cap 8 388 608) |

Derived per-operation cost on a 1 000-account store:

| Operation | Derivations | Estimated total |
|---|---|---|
| `reset-token` (success) | 1 — digest the new token | ≈ 0.41 s |
| `reset` (success) | 2 — verify the token, digest the new password | ≈ 0.81 s |
| `reset` (refused token) | 1 — real or dummy (R17) | ≈ 0.41 s |
| `reset` (short new password) | 1 — the token verification only | ≈ 0.41 s |

**Rationale and the flag**: `reset` at ≈ 0.81 s against a 1 s bound is about
1.2× headroom, the same position feature 001 recorded for `passwd` (001 R8 and
its flagged note 3) and for the same reason — two deliberate derivations are
inherent to the operation. SR-013 names "the same deliberately slow algorithm
and current parameters already used for passwords", and Principle IV forbids
simplifying away a Principle V control, so buying margin by lowering the work
factor is not available to this plan: it would be an SR-013/SR-004 amendment,
not an implementation choice. The store-size component is ~6 ms — three orders
of magnitude below the KDF — so SC-022 is a statement about the host's CPU, not
about the design, and the suite asserts both the absolute bound (marked `slow`)
and the scaling claim. Carried forward to the plan's flagged notes.

**Alternatives considered**: a cheaper KDF for the token only, on the argument
that a 128-bit random token needs no stretching. Technically defensible and
rejected anyway: SR-013 states the requirement, the constitution marks
Principle V non-negotiable, and the plan is not the place to weaken it.
`/speckit-clarify` is.

---

## Resolved: no outstanding NEEDS CLARIFICATION

The specification contained none, and the planning input fixed the runtime,
the interface and the test framework. Three decisions above are judgement calls
the spec left open rather than unknowns in the request, and each is recorded
with the requirement that drove it: the millisecond integer expiry (R13), the
nested `reset` object (R12, carried into the plan's Complexity Tracking because
Principle IV prefers flat), and `version` staying at `1` (R18). The tight
`reset` budget (R20) is carried into the plan's flagged notes, not left here.
