# Phase 1 Data Model: Password Reset by One-Time Token

**Feature**: `002-password-reset` | **Date**: 2026-11-05

Derived from [spec.md](./spec.md) "Key Entities" and FR-020 … FR-043 /
SR-010 … SR-018. Extends
[feature 001's data model](../001-user-accounts-cli/data-model.md), which
remains in force for everything not restated here. The on-disk encoding is the
cross-invocation contract and is specified in
[contracts/store-format.md](./contracts/store-format.md).

This feature adds **one** optional field to one existing entity and introduces
**one** new entity that lives inside it. Nothing else in the model changes.

---

## Entity: Reset token (new)

A one-time, short-lived authorisation to replace one account's password without
knowing the current one. The spec's Key Entities section is precise about its
split existence, and the model follows it:

| Where | What | Lifetime |
|---|---|---|
| Standard output of one `reset-token` invocation | the token **value** (22 characters) | printed once; the tool never holds or sees it again |
| The account's `reset` field in the store | **verification material** + an expiry instant — never the value | until redeemed, expired, replaced, the password changes, or the account is deleted |

In memory it is a plain `dict` nested inside the account record. There is no
token class and no token module (Principle IV).

### The token value

| Property | Rule |
|---|---|
| Source | `secrets.token_urlsafe(16)` — the OS CSPRNG via `secrets` (SR-014) |
| Entropy | exactly 128 bits; `crypto.TOKEN_BYTES = 16` |
| Rendering | 22 characters, alphabet `A–Z a–z 0–9 - _`, no padding (A-023) |
| Printability | every character printable ASCII; no whitespace, no quoting character, no control character, nothing that can start a terminal escape (SR-011) |
| Stored? | **never** — not in the store, not in a temporary file, not in any other stream (SR-013, SC-015) |
| Compared | `hmac.compare_digest` over derived digests, constant time (SR-014) |
| Compared how exactly | byte for byte after terminator stripping; **no** whitespace trimming, **no** case folding (A-022) |

### The `reset` field (verification material)

Exactly these eight keys, no more and no fewer — an allow-list, not a minimum
(SR-010):

| Key | Type | Rules |
|---|---|---|
| `kdf` | `str` | MUST be exactly `"scrypt"` |
| `n` | `int` | power of two, `2 … 1048576` |
| `r` | `int` | `1 … 32` |
| `p` | `int` | `1 … 16` |
| `dklen` | `int` | `16 … 64` |
| `salt` | `str` | base64 (standard alphabet, padded) of exactly 16 bytes from `secrets.token_bytes`. **Fresh per issued token** (SR-013) — never the account's password salt and never reused across issuances |
| `hash` | `str` | base64 of exactly `dklen` bytes: `scrypt(token, salt, n, r, p, dklen)` at the module's *current* parameters (SR-013) |
| `expires_ms` | `int` | absolute instant, milliseconds since the Unix epoch, `1 … 253402300799000`. See [research R13](./research.md#r13--representing-the-expiry-instant) for why integer milliseconds |

The first seven keys are deliberately the same names, types and ranges as the
account's own password fields, which is what lets `crypto.verify(token,
record["reset"])` be reused with no change
([research R12](./research.md#r12--what-is-recorded-against-the-account)).

**Constraints**

- **At most one per account.** Enforced *structurally* — one key per record, so
  issuing assigns and thereby replaces (FR-029, A-015). There is no check to
  forget and no list to grow.
- **Fixed size.** The serialised field is 174 bytes, independent of the token,
  the username and the number of issuances (FR-043, SR-015). No account record
  can grow without limit, so the existing 8 MiB / 10 000-account caps continue
  to bound the file — measured worst case 3 440 027 bytes
  ([research R20](./research.md#r20--performance-budget-and-a-flagged-tightness)).
- **Validated on load, every load.** Against the table above, before any of it
  is used (SR-010). One invalid `reset` object fails the **whole** load with
  status 5. It is never repaired, never defaulted, never dropped — and in
  particular a missing or non-integer `expires_ms` is **not** treated as "not
  expired".
- **Optional.** A record with no `reset` key is valid and means "no outstanding
  token" (FR-041). A record written before this feature is exactly that.
- **Never partially present.** Either all eight keys or no `reset` key at all;
  a subset is malformed (status 5).

### Derived attribute

`is_current(record, now_ms)` — not stored, computed at the moment of each
attempt (FR-030, SR-016):

```text
"reset" in record  and  record["reset"]["expires_ms"] >= now_ms
```

where `now_ms = int(time.time() * 1000)` read **in the invocation making the
attempt**, never carried over (FR-030). "Unused" needs no term: a redeemed
token's `reset` key is gone, so a used token fails the first clause.

### State transitions

A token has no stored state field; its state is its presence plus its expiry.

```text
            reset-token (account exists)
   absent ─────────────────────────────────▶ outstanding
      ▲                                        │   │
      │                                        │   │ expires_ms < now_ms
      │  reset   (token matches, password ok)   │   ▼
      ├────────────────────────────────────────┤ expired ──┐
      │  passwd  (success, FR-042)             │           │ refused, status 1
      ├────────────────────────────────────────┤◀──────────┘
      │  delete  (success — record and token go together)
      ├────────────────────────────────────────┤
      │  reset-token again (replaces, A-015)   │
      └────────────────────────────────────────┘
```

| From | Event | To | Observable |
|---|---|---|---|
| absent | `reset-token`, account exists | outstanding | token on stdout, status 0 |
| outstanding | `reset-token` again | outstanding (**new** material; old value dead at once) | token on stdout, status 0 |
| outstanding | `reset` with the matching value, new password valid | absent | `password reset`, status 0 |
| outstanding | `reset` with the matching value, new password refused | **outstanding, expiry unchanged** | status 2, token still usable (FR-036) |
| outstanding | `reset` with any other value | outstanding, unchanged | `invalid token`, status 1 |
| outstanding | clock passes `expires_ms` | expired | — (no write; expiry is not swept, A-027) |
| expired / absent | `reset` with any value | unchanged | `invalid token`, status 1 |
| outstanding | successful `passwd` | absent (FR-042) | `passwd`'s own output, unchanged |
| outstanding | successful `delete` | absent with the record (FR-042) | `delete`'s own output, unchanged |
| outstanding | `login` (success or failure), `unlock` | **outstanding, untouched** (FR-042) | that command's own output, unchanged |
| expired | anything | expired until overwritten or the record goes | an expired field is never cleaned up on its own (A-027) |

Transitions that write the store do so **only** on success, inside the lock,
atomically (FR-027, SR-016). No transition is triggered by a failed operation
of any kind.

---

## Entity: Account (extended)

Unchanged in identity, in its password material, and in `failed_logins`. One
field is added:

| Field | Type | Rules |
|---|---|---|
| *(key)* `username` | `str` | unchanged — 3–32 of `[A-Za-z0-9_]`, case-sensitive (FR-011). `Alice` and `alice` remain two accounts, each with its own independent token |
| `kdf`, `n`, `r`, `p`, `dklen`, `salt`, `hash` | — | unchanged (SR-004) |
| `failed_logins` | `int` | unchanged, `0 … 5`. **Never written by either new operation** — not on success, not on a refused token (FR-027, FR-039, A-020) |
| `reset` | `dict` \| *absent* | **new, optional.** The Reset token entity above. Absent means no outstanding token |

**Constraints added by this feature**

- **Lock state is still derived** from `failed_logins` (001 R7) and is still
  defined over `login` only. Neither new operation reads it to decide whether to
  proceed (FR-031, FR-039, A-018), so status 4 is unreachable from both
  (FR-024).
- **A successful `reset` sets three things together**: fresh password material
  at the module's current parameters, `failed_logins = 0`, and `reset` removed
  (FR-034, A-018). The old password stops verifying because the material is
  replaced wholesale, not amended.
- **Every other account is untouched** by a successful reset, byte for byte
  (FR-034, SC-021).
- A record carrying `reset` is still a valid record for every existing
  operation; none of the five reads the field, and `login`/`unlock` mutate
  `failed_logins` in place so the field survives them (FR-042, scenario 5.4).

---

## Entity: Store (extended)

Unchanged as the single JSON file at the operator-supplied path.

| Field | Type | Rules |
|---|---|---|
| `version` | `int` | **still exactly `1`.** Deliberately not bumped — see [research R18](./research.md#r18--store-compatibility-in-both-directions): bumping would make every pre-existing store unloadable and break FR-041 |
| `accounts` | `dict[str, Account]` | unchanged: 0–10 000 members, each key a valid username |

**Constraints added or restated**

- **Maximum nesting depth becomes 4** (`document` → `accounts` → `record` →
  `reset`), up from 3. Still non-recursive, so parse cost stays linear in file
  size and no regular expression is involved in parsing (SR-015).
- **Backward compatibility (FR-041)**: a store written before this feature
  loads unchanged; every account in it simply has no `reset` key and every
  password in it still verifies. Nothing is migrated or rewritten on load.
- **Forward compatibility is not offered (A-026)**: the previous build
  validates records against a closed eight-key set, so it reports a store
  carrying an outstanding token as malformed (status 5). Loud, not silent;
  downgrading is out of scope.
- **Neither new operation creates the store** (FR-032, FR-038). A missing file
  still loads as an empty in-memory store, so both operations reach "no such
  account" (status 3) and write nothing — not the store, not a temporary file,
  not a lock file.
- **Size and count caps unchanged** (8 MiB, 10 000 accounts). They still bound
  the file because the new field is of fixed size (FR-043).
- **Permissions, atomicity and locking unchanged**: `0o600` set at creation,
  whole-file replacement via `os.replace`, exclusive `flock` on the store's
  directory held across the entire read–modify–write (SR-012, SR-016, SR-017).

---

## Value object: Validity (`--ttl`)

Not persisted — it exists only between argv and the computation of
`expires_ms`.

| Property | Rule |
|---|---|
| Source | `--ttl SECONDS` on `reset-token` only (FR-021) |
| Default when absent | `900` seconds (FR-021) |
| Accepted form | `[0-9]{1,5}`, then `1 … 86400` (FR-022, A-016) |
| Rejected | anything else — including `-5`, `+60`, `0`, `1.5`, `6e1`, `100000`, `99999`, the empty string, surrounding whitespace, and non-ASCII digits such as `１２`. Status 2, no token issued, store not written |
| Why the regex precedes `int()` | `int()` accepts Unicode digits, whitespace and a sign; the allow-list is the format, not just the range (SR-010). The five-digit cap also bounds conversion cost (SR-015) |
| Consumed by | `expires_ms = int(time.time() * 1000) + ttl * 1000` |

---

## Requirement traceability for this model

| Requirement | Where it lands in the model |
|---|---|
| FR-028 record what verifies and expires a token | the `reset` field's eight keys |
| FR-029 / A-015 at most one, issuing replaces | one key per record — structural |
| FR-030 expiry measured at each attempt | `is_current`, derived not stored |
| FR-034 reset sets password, clears count and lock, consumes token | Account constraints |
| FR-035 at most one use in total | the key is removed inside the same locked section that verified it |
| FR-036 refused password leaves the token and its expiry alone | state table, "outstanding → outstanding" row |
| FR-041 old stores load | `reset` optional; `version` stays 1 |
| FR-042 `passwd`/`delete` clear it, `login`/`unlock` do not | Account constraints, state table |
| FR-043 fixed, bounded size | 174 B per record, measured |
| SR-010 stored material validated, malformed expiry not "not expired" | `reset` validated on every load against the closed table; `expires_ms` is a range-checked `int` |
| SR-013 salted slow digest, fresh salt, token never written | the `reset` field holds no token value; `salt` fresh per issuance |
| SR-014 CSPRNG, ≥128 bits, constant-time compare | token value properties |
| SR-015 bounded sizes and arithmetic | fixed field size; `ttl` range bounds `expires_ms` |
