# Phase 1 Data Model: Password reset by one-time token

**Feature**: `002-password-reset` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

This document is canonical for the **meaning** of the new state; the on-disk encoding is fixed
by [contracts/store-file.md](./contracts/store-file.md). It extends
[`../001-accounts-cli/data-model.md`](../001-accounts-cli/data-model.md) rather than replacing
it: the Store entity and all seven existing Account fields keep their current definitions and
rules (S-1…S-6, A-1…A-6), and are not restated here.

Rule identifiers continue the shipped feature's series — the token rules are **T-1…T-10** and
the new account rules are **A-7…A-9** — so no identifier is reused.

---

## Entity: Reset token

A secret, single-use credential belonging to exactly one account, standing in for that
account's password for exactly one `reset`. At most one is outstanding per account (FR-032).

**Representation in code**: a plain `dict` under the account record's optional `reset_token`
key, written and read by `cli.py` and validated by `store.py`. No class wrapper, no
module of its own — see [research.md](./research.md) D-013, D-016.

| Field | Type | Meaning | Requirement |
|---|---|---|---|
| `token_hash` | string, 64 lowercase hex characters | `sha256(token_utf8).hexdigest()` — the only recorded trace of the token. The token itself is never stored. | FR-034b |
| `issued_at` | number (epoch seconds, float) | `time.time()` at the moment `reset-token` created it. | FR-036d |
| `ttl_seconds` | integer, 1 … 86400 | The lifetime chosen for it: `--ttl SECONDS`, or 900. | FR-033 |

All three fields are required **when the key is present**. The key itself is optional; its
absence is the normal state of an account (A-7).

### Rules

- **T-1 Presence is the state.** `reset_token` present ⇔ a token is outstanding for that
  account. There is no `used`, `spent` or `revoked` flag: a token that has ended is a key that
  is gone. (FR-036b, D-013)
- **T-2 The token is unguessable and single-line.** 256 bits from a CSPRNG, rendered as 43
  characters of `[A-Za-z0-9_-]` — printable ASCII, no whitespace, so it occupies exactly one
  line. Two tokens are never equal. (FR-034a, SC-015)
- **T-3 The token is unrecoverable from the store.** Only `token_hash` is written. No party
  who can read the store can recover the token or construct a value `reset` will accept:
  presenting the recorded hex as the token hashes it again and does not match. (FR-034b,
  SC-014)
- **T-4 Validation is a constant-time comparison** of `sha256(presented)` against
  `token_hash`, via `hmac.compare_digest`. (FR-034b)
- **T-5 Expiry.** The token is valid while `now < issued_at + ttl_seconds`, measured by
  `time.time()` at the moment it is presented. The boundary is **exclusive**: at exactly
  `issued_at + ttl_seconds` it is expired. No clock-change detection. (FR-036d, D-015)
- **T-6 At most one per account.** Issuing while one is outstanding overwrites it; the replaced
  token is invalid from that moment. (FR-032)
- **T-7 Single use.** A successful `reset` removes the key in the same write that sets the new
  password, so no later non-overlapping invocation can accept it again. (FR-036b, FR-036c)
- **T-8 Five ways it ends, and no others**: a successful `reset` spends it (T-7); a later
  `reset-token` replaces it (T-6); a successful `passwd` cancels it (A-9); a `delete` discards
  it with the account (A-8); its lifetime elapses (T-5). `register`, `login`, `unlock`, a
  failed `passwd` and a failed `delete` leave it exactly as it is. (FR-038, FR-038a, SC-020)
- **T-9 A failed `reset` never ends it.** `invalid token` / 1 leaves the outstanding token
  untouched and still usable (FR-036e); `password too short` / 2 leaves it outstanding and
  usable (FR-036f). Neither changes the password, the tally or the lock state.
- **T-10 Malformed token state is a corrupt store.** `reset_token` present but not an object,
  missing a field, holding a wrong type, or holding a value outside its constraint, makes the
  store unusable: `store unusable: <cause>` / 5, for every command. It is never silently
  ignored and never treated as "no token". (FR-039, Principle II)

### State transitions

```text
                      reset-token (account exists)
   ┌──────────────┐  ───────────────────────────────▶  ┌──────────────────────┐
   │  no token    │                                    │  outstanding         │
   │ (key absent) │  ◀───────────────────────────────   │  (key present)      │
   └──────────────┘   successful reset   (T-7)         └──────────────────────┘
          ▲            successful passwd (A-9)             │   │         ▲
          │            delete           (A-8)             │   │         │
          │                                               │   │         │ reset-token
          └───────────────────────────────────────────────┘   │         │ again (T-6,
            lifetime elapses (T-5, no write — the key          │         │ replaces)
            stays on disk but is honoured by nothing)          └─────────┘

   Self-loops that change nothing (T-9): reset with a wrong/expired token → 1;
   reset with a too-short password → 2; register, login, unlock, failed passwd,
   failed delete.
```

Two properties of this diagram are themselves requirements and are each asserted:

- **Expiry needs no write.** An expired token may remain on disk until the account is next
  written; it is honoured by nothing, so "expired" and "absent" are indistinguishable to a
  user (T-5, FR-036d). The tool does not sweep expired tokens — no requirement asks for it, and
  a sweep would make an otherwise read-only command write (Principle IV).
- **No transition out of "outstanding" is reachable by `login`.** Repeated wrong tokens and
  repeated failed logins cannot consume, disarm or lock anything on the token path
  (FR-036e, FR-038).

---

## Entity: Account (extended)

The seven existing fields and their rules A-1…A-6 are unchanged
([`../001-accounts-cli/data-model.md`](../001-accounts-cli/data-model.md)). One optional field
is added.

| Field | Type | Required | Meaning | Requirement |
|---|---|---|---|---|
| `reset_token` | object (see above) | **no** | The account's outstanding reset token, if any. | FR-032, FR-039 |

### New rules

- **A-7 Optional by construction.** An account that has never had a token issued carries no
  `reset_token` key, so a record written by `register` is exactly what it is today, and a store
  file written before this feature loads and behaves unchanged with no migration. (FR-039,
  SC-019)
- **A-8 `delete` discards the token with the account.** Token state is held nowhere else, so
  removing the record removes the token. A username registered again afterwards behaves as an
  account that has never had a token issued. (FR-036g)
- **A-9 A successful `passwd` cancels the token.** It removes `reset_token` in the same write
  that replaces the derivation material. A failed `passwd` changes nothing. This is `passwd`'s
  only new effect: its arguments, input lines, messages, streams, statuses, and its effect on
  the password, `failed_logins` and `locked` are all exactly as they are today. (FR-038a,
  FR-041)

### What a successful `reset` writes

One write, all of it or none of it (the inherited atomic replace, FR-029b):

| Field | After a successful `reset` | Requirement |
|---|---|---|
| `algorithm`, `iterations`, `salt`, `key` | replaced with fresh material for the new password — new salt, current `DEFAULT_ITERATIONS` | FR-036b |
| `failed_logins` | `0` | FR-036b |
| `locked` | `false` | FR-036b |
| `reset_token` | removed | FR-036b, T-7 |

This is the only command that clears a lock other than `unlock`, and the departure from
`passwd` (which leaves lock state alone, A-5/FR-019) is deliberate: the lockout guards a
password the reset has just replaced, and the token it required is itself the administrator's
authorisation. (Spec Clarifications, session 2026-11-11)

### What `reset-token` writes

| Field | After a successful `reset-token` | Requirement |
|---|---|---|
| `reset_token` | set (replacing any previous value) | FR-032 |
| everything else | **unchanged** — password material, `failed_logins` and `locked` are not touched, so a locked account stays locked and `login` still reports `account locked` / 4 | FR-032, FR-038 |

---

## Validation rules, consolidated

New or newly-relevant input validation. Existing rules (username format, 12-character
password minimum) are unchanged and apply to `reset`'s new password as they do to `passwd`'s.

| Input | Rule | Failure |
|---|---|---|
| `--ttl SECONDS` | non-empty string of ASCII digits `0`–`9`; integer value 1 ≤ n ≤ 86400; at most one occurrence; only with `reset-token` | usage line → stderr, exit 2, store untouched (FR-033, FR-040) |
| `reset` stdin | exactly two lines available before end of input | `missing password input` → stderr, exit 2 (FR-036) |
| token line | content up to the line break, nothing stripped; matched against `token_hash` for an unexpired outstanding token | `invalid token` → stderr, exit 1 (FR-035, FR-036a) |
| new-password line | ≥ 12 characters | `password too short` → stderr, exit 2, token still usable (FR-036a, FR-036f) |
| username | present in the store | `no such account` → stderr, exit 3 (FR-036a) |
| `reset_token` on load | object with all three fields at the right type and within constraints | `store unusable: <cause>` → stderr, exit 5 (FR-039, T-10) |

### Field-level store validation (what makes token state malformed)

Enforced in `store.py` at load, before any command runs. Each row is a corrupt store:

| Condition | Example |
|---|---|
| `reset_token` is not a JSON object | `"reset_token": null`, `"reset_token": "abc"`, `"reset_token": []` |
| a required field is missing | `{"token_hash": "…", "issued_at": 1.0}` |
| `token_hash` is not a string, or not exactly 64 lowercase hex characters | `"token_hash": 5`, `"ABC…"`, `"zz…"`, a 63-character value |
| `issued_at` is not a number, or is a boolean, or is not finite | `"issued_at": "now"`, `true`, `NaN`, `Infinity` |
| `ttl_seconds` is not an integer, or is a boolean, or is outside 1…86400 | `0`, `-5`, `1.5`, `true`, `86401` |

As with account records, a boolean must be rejected where a number is required: `bool` is a
subclass of `int` in Python. Unknown **extra** keys inside the `reset_token` object are not an
error and are preserved on rewrite, which is how account records already treat extras; a
*missing* required key is corruption. (FR-039, and the 001 precedent S-6)
