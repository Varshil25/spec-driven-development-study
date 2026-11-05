# Phase 1 Data Model: Local User Account Manager (CLI)

**Feature**: `001-user-accounts-cli` | **Date**: 2026-11-04

Derived from [spec.md](./spec.md) "Key Entities" and the FR/SR requirements.
The on-disk encoding of these entities is the cross-invocation contract and is
specified separately in [contracts/store-format.md](./contracts/store-format.md).

---

## Entity: Store

The whole set of accounts, held in the single file at the operator-supplied
path (FR-007). In memory it is a plain `dict`; there is no store class
(Principle IV).

| Field | Type | Rules |
|---|---|---|
| `version` | `int` | MUST equal `1`. Any other value → status 5. Present so a future format change is detectable rather than silently misread (Principle II). |
| `accounts` | `dict[str, Account]` | Keys are usernames and MUST each satisfy the username rules below. At most one entry per username — enforced structurally by the mapping, not by a check. At most 10 000 entries (A-011, SR-006). |

**Constraints**

- **Existence**: created only by `register` (FR-007). A missing file loads as
  `{"version": 1, "accounts": {}}` *in memory* and is not written to disk by
  `login`, `unlock`, `passwd` or `delete`.
- **Size**: the file MUST be at most 8 MiB (8 388 608 bytes), checked from the
  open file descriptor before any parsing (A-011, SR-006). Over-size → status 5.
- **Count**: a loaded store with more than 10 000 accounts → status 5. A
  `register` that would exceed 10 000 → status 5 (see
  [research R10 note](./research.md#resolved-no-outstanding-needs-clarification)).
- **Permissions**: owner read/write only, `0o600`, set at creation (SR-008,
  SC-010).
- **Atomicity**: replaced as a whole; after any interruption the file holds
  either the complete old content or the complete new content (FR-009, SC-009).
- **Validation on load**: every record is validated against the structure,
  field set and field formats below before any of it is used. A single invalid
  record fails the whole load under status 5 — never repaired, guessed at or
  skipped (SR-001).

---

## Entity: Account

One named local identity. In memory a plain `dict`; the username is not a field
of the record, it is the key that locates it.

| Field | Type | Rules |
|---|---|---|
| *(key)* `username` | `str` | 3–32 characters, each of `A–Z a–z 0–9 _`. Compared exactly, case-sensitively, so `Alice` and `alice` are two accounts (FR-011). Violation on input → status 2; violation in a stored key → status 5. |
| `kdf` | `str` | MUST be exactly `"scrypt"`. Any other value → status 5 (SR-001: allow-list, no guessing). |
| `n` | `int` | scrypt cost. MUST be a power of two, `2 <= n <= 2**20`. |
| `r` | `int` | scrypt block size. MUST be `1 <= r <= 32`. |
| `p` | `int` | scrypt parallelism. MUST be `1 <= p <= 16`. |
| `dklen` | `int` | derived key length in bytes. MUST be `16 <= dklen <= 64`. |
| `salt` | `str` | base64 (standard alphabet, padded) of exactly 16 random bytes from `secrets.token_bytes` (SR-005). Fresh per account, and re-generated on every password change. |
| `hash` | `str` | base64 of exactly `dklen` bytes: `scrypt(password, salt, n, r, p, dklen)`. The password itself is never stored in any form (SR-004). |
| `failed_logins` | `int` | Consecutive failed `login` attempts, `0 <= failed_logins <= 5`. A value outside that range → status 5. |

**Derived attribute**

| Name | Definition |
|---|---|
| `locked` | `failed_logins >= 5`. Not stored — see [research R7](./research.md#r7--lock-state-is-derived-not-stored). |

**Constraints**

- `n`, `r`, `p`, `dklen` are recorded per account so a future parameter
  increase does not invalidate existing accounts (SR-004). New and changed
  passwords are written with the current module defaults
  (`n=2**17, r=8, p=1, dklen=32`); verification always uses the values in the
  record.
- `n * r * 128` for a stored record MUST NOT exceed the `maxmem` the tool
  passes to `scrypt` (192 MiB); a record demanding more → status 5 rather than
  an unbounded allocation (SR-006).
- Two accounts given the same password have different salts and therefore
  different `hash` values (SC-006) — guaranteed by generating the salt per
  account rather than per store.
- Unknown extra fields in a record → status 5. The field set is an allow-list,
  not a minimum (SR-001).

---

## Entity: Credential attempt

One password supplied on stdin for one invocation. Never persisted, never
echoed, never written to a temporary file (SR-004, SR-009, SC-005). It exists
only as a local `str` for the duration of one derivation.

| Property | Rule |
|---|---|
| Source | One line of `sys.stdin.buffer`, in the order the command documents (FR-002). Never a command-line argument (FR-002). |
| Line size | At most 4 096 bytes including the terminator that is then stripped; longer → status 2, refused rather than truncated (FR-014, SR-006). |
| Encoding | UTF-8. Undecodable bytes → status 2 (A-009, [research R5](./research.md#r5--reading-passwords-from-stdin-under-a-byte-cap-fr-002-fr-014-sr-006-a-009-a-010)). |
| Terminator | One trailing `\n`, then one preceding `\r`, stripped and not part of the password (A-009). |
| Length when **being set** (`register`, new password of `passwd`) | 12–1 024 characters, counted after decoding. Outside that → status 2 (FR-012, A-011). |
| Length when **being verified** (`login`, `delete`, current password of `passwd`) | Not range-checked; any decodable in-limit line is simply compared, and a mismatch — including from an over-long or empty password — is status 1 (spec edge cases). |
| Absence | Stream ends before the required line → status 2, nothing changed (A-010). |
| Surplus | Lines beyond what the command needs are never read, so they are ignored without cost (spec edge case). |

---

## State transitions

`failed_logins` is the only mutable account state; the password material is
replaced wholesale by `passwd`.

```text
                       register (12–1024 char password)
                                   │
                                   ▼
                         ┌───────────────────┐
         login OK ──────▶│  failed_logins=0  │◀────── unlock, passwd OK
         (reset)         │     (unlocked)    │        (reset + relock clear)
                         └───────────────────┘
                                   │ login fails
                                   ▼
                      ┌─────────────────────────┐
                      │  failed_logins = 1..4   │  login still possible;
                      │       (unlocked)        │  each failure → status 1
                      └─────────────────────────┘
                                   │ 5th consecutive failure
                                   │ (that attempt still reports status 1)
                                   ▼
                      ┌─────────────────────────┐
                      │   failed_logins = 5     │  login → status 4 always,
                      │        (LOCKED)         │  correct password included
                      └─────────────────────────┘
                                   │ unlock (no password) or passwd (correct current)
                                   ▼
                            failed_logins = 0

   delete (correct password, locked or not) ──▶ record removed entirely
```

**Transition rules**

| Trigger | Precondition | Effect on `failed_logins` | Status |
|---|---|---|---|
| `register` | username absent, password 12–1 024 chars | set to `0` | 0 |
| `register` | username present | unchanged | 3 |
| `login` | locked (`>= 5`) | **unchanged** — the lock is reported before the password is considered, so a locked account's count does not grow (FR-017, scenario 2.4) | 4 |
| `login` | unlocked, password matches | reset to `0` (FR-015, A-002) | 0 |
| `login` | unlocked, password mismatches | `+1`, capped by the lock taking effect at 5 (FR-015, FR-016) | 1 |
| `login` | username absent | no record to change; dummy derivation performed for timing parity | 1 |
| `unlock` | username present | reset to `0`, lock cleared, succeeds whether locked or not (FR-018, A-007) | 0 |
| `unlock` | username absent | no change | 3 |
| `passwd` | username present, current password matches, new password 12–1 024 chars | reset to `0`, lock cleared (FR-019) — a password change is also a recovery path; new salt generated | 0 |
| `passwd` | current password mismatches | **unchanged** — `passwd` failures do not count toward the login lock (A-005) | 1 |
| `passwd` | current matches, new password out of range | unchanged, stored password unchanged | 2 |
| `passwd` | username absent | no change | 3 |
| `delete` | username present, password matches (locked or not, FR-019) | record removed | 0 |
| `delete` | password mismatches | unchanged (A-005: no increment) | 1 |
| `delete` | username absent | no change | 3 |

**Invariant**: every transition that ends in a non-zero status leaves the
stored account set and every stored password exactly as it was, with the single
exception of the `login` failure-count increment (FR-006, SC-008). That
exception is also the only case in which a failing command writes the store at
all.
