# Phase 1 Data Model: Administrator-Issued Password Reset

**Feature**: `002-password-reset` | **Date**: 2026-11-16

This file is a **delta** over [001's data model](../001-local-account-manager/data-model.md),
which remains authoritative for Store, Account, Password, and `Result`. Nothing there is
redefined; one entity is added and one existing entity gains one optional attribute. Format
decisions come from [research.md](./research.md) R-09 – R-12.

As in 001, the store is an internal decision, not a public interface — the CLI
([contracts/cli-contract.md](./contracts/cli-contract.md)) is the only external contract.

---

## Reset token *(new)*

A single-use secret belonging to one account, printed once by `reset-token` and surrendered to
`reset`. The token **value** exists only in transit: in the issuing process's memory, on one line
of stdout, and on one line of the using process's stdin. What persists is a verifier from which
the value cannot be recovered (FR-057).

### On-disk representation

Nested inside the owning account's record, under the optional key `reset_token`:

```json
{
  "version": 1,
  "accounts": {
    "alice": {
      "salt": "3Q2+7wAAAAAAAAAAAAAAAA==",
      "verifier": "n0Zq...32-bytes-base64...=",
      "failed_logins": 0,
      "locked": false,
      "reset_token": {
        "salt": "RkZGRkZGRkZGRkZGRkZGRg==",
        "verifier": "QkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkI=",
        "expires_at": 1763336400.1234567
      }
    },
    "bob": {
      "salt": "3Q2+7wAAAAAAAAAAAAAAAA==",
      "verifier": "n0Zq...32-bytes-base64...=",
      "failed_logins": 0,
      "locked": false
    }
  }
}
```

`alice` has an outstanding token; `bob` has none. **Absence of the key is the only way to say "no
outstanding token"** — `"reset_token": null` is rejected at load, not interpreted (R-11).

### Fields

| Field | Type | Meaning |
|---|---|---|
| `salt` | string, strict base64 of exactly 16 bytes | `secrets.token_bytes(16)`, fresh at every issuance. Per-token, never shared with the account's password salt (R-10). |
| `verifier` | string, strict base64 of exactly 32 bytes | `hashlib.pbkdf2_hmac("sha256", token.encode("utf-8"), salt, 600_000, dklen=32)`. The same transformation, parameters, and field widths as a password verifier, so the existing validation helper covers it unchanged. |
| `expires_at` | number (`int` or `float`, never `bool`), finite | Unix epoch seconds, computed at issuance as `time.time() + ttl`. The token is valid while `now < expires_at` (R-12). |

The TTL is **not** stored. Once `expires_at` is fixed, the window it came from is of no further
use to any requirement (R-12).

### The token value itself *(never at rest)*

| Property | Value | Requirement |
|---|---|---|
| Source | `secrets.token_urlsafe(32)` — 32 CSPRNG bytes | FR-040 |
| Entropy | 256 bits (floor is 128) | FR-040 |
| Rendered form | 43 characters matching `\A[A-Za-z0-9_-]{43}\Z` — no whitespace, no newline, no quote, no shell metacharacter | FR-040 |
| Uniqueness | Probabilistic: repeat probability below 2⁻¹²⁸. No registry exists, and none can, because FR-057 forbids keeping tokens in recoverable form | FR-040 |
| Where it may appear | Exactly one line on `reset-token`'s stdout, and one line read from `reset`'s stdin | FR-048, FR-058 |
| Where it must never appear | The store's bytes, any diagnostic, any other command's output, `argv` | FR-048, FR-057, FR-058, SC-014 |

### Validation rules (load-time; any failure is `StoreError`)

Continuing 001's numbering, where rules 1–7 are unchanged. Rule 4 is amended in one word.

4. *(amended)* Every value in `accounts` is an object carrying exactly the keys `salt`,
   `verifier`, `failed_logins`, `locked`, and **optionally** `reset_token` — no missing required
   key, no unknown key.
8. If `reset_token` is present, it is a JSON object carrying exactly the keys `salt`, `verifier`,
   `expires_at` — no missing key, no unknown key. `null` is not an object and is rejected here.
9. `reset_token.salt` and `reset_token.verifier` are strings that decode as strict base64 to
   exactly 16 and 32 bytes respectively (the same check as rule 5).
10. `reset_token.expires_at` is an `int` or `float`, is not a `bool`, and is **finite** —
    `math.isfinite` is required, because `json.loads` accepts the literals `NaN`, `Infinity`, and
    `-Infinity`.
11. The diagnostic for any of rules 8–10 names the account, the `reset_token` field, and the
    condition — e.g. `account 'alice': reset_token: expires_at is not a finite number` — without
    disclosing any stored value.

Rule 10's finiteness check exists because the alternative fails *silently*: `now < NaN` is
`False` for every `now`, so `expires_at: NaN` would be a token that is permanently invalid while
looking ordinary, and `Infinity` one that never expires. Both are the plausible-wrong-answer
class Principle II treats as the most severe defect, so both are loud (R-12).

Rule 8's exact-key requirement is 001's rule 4 reasoning applied one level down: a silently
ignored extra key inside `reset_token` is how a hand-edited store would appear to work while
meaning something else.

### Lifecycle

| Situation | Effect on `reset_token` | Requirement |
|---|---|---|
| Account registered | Key absent | FR-059 (same shape as a pre-feature record) |
| Store written before this feature | Key absent → reads as no outstanding token, no migration, no rewrite | FR-059 |
| `reset-token` succeeds | Key set to a fresh `{salt, verifier, expires_at}`, replacing any previous value; store saved | FR-039, FR-044, FR-046 |
| `reset-token` succeeds on a **locked** account | Same as above; `locked` and `failed_logins` untouched | FR-047 |
| `reset` succeeds | Key **removed**; `salt`/`verifier` replaced with the new password's; store saved | FR-049, FR-051 |
| `reset` rejected (`invalid token`) | Unchanged; **store not written at all** | FR-052, R-16 |
| `reset` rejected (new password too short) | Unchanged and still usable; store not written | FR-053 |
| Window elapses | Unchanged on disk; treated as no token by every validation. Expired records are never swept | FR-041, R-16 |
| `passwd` changes the password | Unchanged and still usable — existing commands must behave exactly as today | FR-060, spec edge case |
| `unlock`, `login`, `register` run | Unchanged — no existing command reads or writes the key | FR-060 |
| Account deleted | Removed with the whole record; a later `reset` for that username exits 3 | FR-054, spec edge case |

### State transitions

```text
                          ┌──────────────────────────────┐
                          │          NO TOKEN            │ ← register; pre-feature record;
                          │   (reset_token key absent)   │   after a successful reset;
                          └──────────────────────────────┘   after the account is deleted
                             │                      ▲
            reset-token      │                      │  reset succeeds
       → salt, verifier,     │                      │  (token consumed, key removed)
         expires_at = now+ttl│                      │
                             ▼                      │
                          ┌──────────────────────────────┐
                 ┌───────▶│         OUTSTANDING          │────────┐
                 │        │     now < expires_at         │        │
    reset-token  │        └──────────────────────────────┘        │  now reaches expires_at
    again        │           │                                    │
    (supersedes: │           │  reset with a wrong token  → 1     ▼
     old value   │           │  reset with a short password → 2  ┌──────────────────────────┐
     overwritten)│           │  (both leave this state)          │        EXPIRED           │
                 └───────────┘                                   │   now >= expires_at      │
                                                                 │  record still on disk,   │
                                                                 │  treated as NO TOKEN     │
                                                                 └──────────────────────────┘
```

Five states collapse to one observable answer. A `reset` attempt is rejected with exactly
`invalid token` and status 1 when the presented token does not match, has been superseded, has
already been used, has expired, or never existed — the message and status are identical in all
five cases, so the response cannot reveal which applied (FR-052, SC-013).

Three transitions worth stating explicitly because they are easy to get backwards:

- **A too-short new password does not spend the token.** The account stays OUTSTANDING and the
  very next attempt with the same token and a 12-character password succeeds (FR-053, SC-015).
  This is the one `reset` failure where the token survives.
- **A successful reset does not clear a lock.** `reset` neither reads nor writes `locked` or
  `failed_logins`, so a locked account can be reset and stays locked until `unlock` (FR-056,
  and FR-023/FR-025 before it).
- **A rejected token is not a failed login.** `failed_logins` is never incremented by `reset`, so
  no number of wrong tokens can lock an account (FR-056, spec edge case).

---

## Account *(existing, extended)*

One attribute is added to [001's Account](../001-local-account-manager/data-model.md#account).
Everything else — username rules, password verifier, salt, failed-login count, lock state — is
unchanged, including the state machine governing lockout.

| Attribute | Stored as | Rules |
|---|---|---|
| Outstanding reset token | `reset_token`, optional object | Zero or one per account. Set by `reset-token` (superseding any previous), removed by a successful `reset`, and removed with the account by `delete`. Not read or written by `register`, `login`, `unlock`, or `passwd` (FR-044, FR-051, FR-060). |

### In-memory representation

Unchanged: a plain `dict[str, dict]` from `json.load`, with `reset_token` simply another key in
the record dict. No wrapper class and no dataclass for the token — the only operations needed are
"is the key there", "read three fields", "replace it", and "delete it", which `dict` provides, so
a class would be an abstraction with a single caller (Principle IV, and the same reasoning 001
applied to the Store).

---

## Validity window *(new, in-memory only)*

The number of seconds a token remains usable after issuance.

| Property | Value | Requirement |
|---|---|---|
| Source | `--ttl SECONDS`, or 900 when omitted | FR-041 |
| Accepted form | A string of ASCII decimal digits (`\A[0-9]+\Z`) converting to `>= 1`. Not `int()`, which would coerce `1_000`, `+5`, `" 10 "`, and `"١٢٣"` (R-14) | FR-042 |
| Upper bound | None. Any positive integer is the operator's choice | FR-042, spec edge case |
| Scope | `reset-token` only. Supplied to any other command it is a usage error, exit 2 | FR-043 |
| Lifetime | Consumed at issuance to compute `expires_at`; never stored | R-12 |

---

## `Result` *(existing, unchanged)*

The two new commands return the same frozen dataclass, with no new field and no new status:

- `reset-token` success → `Result(0, out=f"{token}\n", save=True)`
- `reset` success → `Result(0, out="password reset\n", save=True)`
- every new failure → `Result(1|2|3, err="<one line>\n", save=False)`

Both existing invariants continue to hold, and the new commands strengthen one of them: `save is
True` only on the two success paths above, so the set of outcomes that write the store grows by
exactly two and the failed-`login` exception (FR-006) remains the only non-zero outcome in the
whole tool that persists (R-16). `code` stays within 0–3 for both new commands, and neither ever
returns 4 (FR-061).
