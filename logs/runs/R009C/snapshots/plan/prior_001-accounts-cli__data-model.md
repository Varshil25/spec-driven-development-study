# Phase 1 Data Model: Local Account Manager CLI

**Feature**: `001-accounts-cli` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

The exact on-disk encoding is specified in [contracts/store-file.md](./contracts/store-file.md);
this document describes the entities, their fields, the validation rules that govern them, and
the state transitions. Where the two overlap, the contract is canonical for encoding and this
document is canonical for meaning.

---

## Entity: Store

The single file at the path given by `--store`. Holds every account and nothing else.

| Field | Type | Meaning | Requirement |
|---|---|---|---|
| `format` | string, exactly `"accounts-store-v1"` | Format marker. Its absence or any other value makes the store corrupt. | FR-029a |
| `accounts` | object, username → Account | The account records, keyed by username. | FR-029a |

**Representation in code**: a plain `dict` with those two keys, loaded by `store.load(path)`
and written by `store.save(path, data)`. No class wrapper — see Principle IV.

**Rules**

- **S-1** A path that does not exist loads as `{"format": "accounts-store-v1", "accounts": {}}`,
  the empty store. (FR-002, edge case "store absent on first use")
- **S-2** The store file is created on the first successful write, not on load. A command that
  fails never creates it. (FR-006, FR-028)
- **S-3** Every write replaces the whole document atomically: temp file in the same directory
  → flush → fsync → `os.replace`. (FR-029b)
- **S-4** The file's mode is `0o600` at creation and after every rewrite; a rewrite never
  widens it. (FR-029c)
- **S-5** Any of the following makes the store corrupt — reported as
  `store unusable: <cause>` with exit 5, never silently treated as empty: not valid UTF-8;
  not valid JSON; top level not an object; `format` missing or unrecognized; `accounts`
  missing or not an object; any record not an object; any record missing a required field or
  holding a wrong JSON type for one. (FR-029, FR-029a)
- **S-6** No field beyond `format` and `accounts` is written. Unknown extra keys found on load
  are not an error (they are ignored and dropped on the next rewrite); a *missing* required
  key is. (FR-029a; Key Entities: "Holds no information other than the format marker and the
  account records")

**Key ordering and whitespace** are not part of the contract; tests must compare parsed JSON,
not bytes — except SC-005, which deliberately searches the raw bytes for plaintext passwords.

---

## Entity: Account

One named local user. Stored as the value under its username key in `accounts`; the username
is therefore the key and is not repeated inside the record.

| Field | Type | Meaning | Requirement |
|---|---|---|---|
| *(key)* `username` | string | Unique within the store, case-sensitive, 3–32 chars of `[A-Za-z0-9_]`. | FR-007 |
| `algorithm` | string, exactly `"pbkdf2_hmac_sha256"` | Derivation function used for this record. Any other value ⇒ corrupt store. | FR-026b |
| `iterations` | integer ≥ 1 | Iteration count used for *this* record. New records: 600,000. | FR-026a, FR-026b |
| `salt` | string, base64 of 16 bytes | Per-account salt from a CSPRNG. | FR-026a |
| `key` | string, base64 of 32 bytes | Derived key. The only password-derived material stored. | FR-026a |
| `failed_logins` | integer ≥ 0 | Consecutive failed logins since the last success or unlock. | FR-013, FR-015 |
| `locked` | boolean | Whether the account is closed to `login`. | FR-016, FR-017 |

All seven fields are required in every record; a record missing any of them is a corrupt
store (S-5).

**Rules**

- **A-1 Username format** — accepted at registration only when `3 <= len(username) <= 32` and
  every character is an ASCII letter, digit or underscore. Length is counted in characters.
  Boundaries: 3 and 32 accepted, 2 and 33 rejected. (FR-007)
- **A-2 Username comparison** — exact and case-sensitive; `Alice` and `alice` are distinct
  accounts. (FR-007)
- **A-3 Username format is a registration-time rule only.** `login`, `unlock`, `passwd` and
  `delete` never report `invalid username`: a name that could not have been registered simply
  does not exist, so the unknown-account rules apply. (Spec assumption on FR-007)
- **A-4 Password length** — accepted only when at least 12 characters. No maximum, no
  character-class rule. Counted in characters, not bytes, so a 12-character non-ASCII password
  is accepted. Boundaries: 12 accepted, 11 rejected. The empty string is length 0 and is
  rejected here (it is a *password*, not missing input). (FR-008)
- **A-5 Password content** — anything except a line break, including spaces and leading or
  trailing whitespace, which is preserved and never trimmed. (FR-003)
- **A-6 No recoverable password** — the record holds only `algorithm`, `iterations`, `salt` and
  `key`. The password itself, and any reversible encoding of it, is never written. Two accounts
  registered with the same password have different `salt` and therefore different `key`.
  (FR-026, SC-005)
- **A-7 Verification uses the record's own parameters** — derive with this record's
  `algorithm`, `iterations` and `salt`, then compare against its `key` with
  `hmac.compare_digest`. The module default is used only when creating new material.
  (FR-026b, FR-026c)
- **A-8 Derivation cost per command** — at most one derivation per command, except `passwd`
  which performs two (verify current, derive new). `unlock` performs none. (SC-009)

---

## Lock and failure-tally state

`failed_logins` and `locked` together form the only mutable state an account has beyond its
password material. The threshold is 5 (FR-015).

### Transitions

| From | Event | To | Output | Exit |
|---|---|---|---|---|
| unlocked, tally *n* < 4 | `login`, correct password | unlocked, tally 0 | `ok` (stdout) | 0 |
| unlocked, tally *n* ≤ 3 | `login`, wrong password | unlocked, tally *n*+1 | `invalid credentials` (stderr) | 1 |
| unlocked, tally 4 | `login`, wrong password | **locked**, tally 5 | `invalid credentials` (stderr) | 1 |
| locked | `login`, correct password | locked, unchanged | `account locked` (stderr) | 4 |
| locked | `login`, wrong password | locked, unchanged | `account locked` (stderr) | 4 |
| any | `unlock` | unlocked, tally 0 | *(nothing)* | 0 |
| any | `passwd`, success | unchanged | *(nothing)* | 0 |
| any | `passwd`/`delete`, wrong password | unchanged | `invalid credentials` (stderr) | 1 |

### Invariants

- **L-1** The fifth consecutive failure is itself reported as `invalid credentials` / 1, not
  as `account locked`. The lock takes effect from the *next* `login`. (FR-015)
- **L-2** A successful `login` resets the tally to 0, so the five failures that lock an account
  are five *consecutive* failures. (FR-012)
- **L-3** On a locked account, `login` changes nothing at all — not the tally, not the lock,
  not the password. The lock is checked before the password, so the tally never exceeds 5 by
  way of further login attempts. (FR-016)
- **L-4** `unlock` clears both `locked` and the tally, requires no password input, and succeeds
  whether or not the account was locked. (FR-017)
- **L-5** The lock gates `login` only. `passwd` and `delete` behave normally on a locked
  account when the correct password is given, and a successful `passwd` does not unlock it.
  (Spec edge case; FR-019)
- **L-6** A wrong password given to `passwd` or `delete` is a failure of that command only: it
  never advances `failed_logins` and so can never lock an account. (FR-020, FR-024)
- **L-7** The tally increment of the wrong-password `login` path is the **only** store write
  performed by a failing command. Every other failure leaves the store byte-for-byte
  equivalent. (FR-028)
- **L-8** A newly registered account starts at `failed_logins: 0`, `locked: false`. (FR-009)
- **L-9** `delete` followed by `register` of the same username produces a fresh account with a
  new salt, a zero tally and no lock; no state survives the deletion. (FR-023)

---

## Command effects on the store

| Command | Reads | Writes on success | Writes on failure |
|---|---|---|---|
| `register` | store | adds one record | never |
| `login` | store | tally → 0 (only if it was non-zero) | tally +1, and `locked` → true at 5 (wrong-password path only) |
| `unlock` | store | `locked` → false, tally → 0 | never |
| `passwd` | store | replaces `algorithm`, `iterations`, `salt`, `key`; leaves tally and `locked` alone | never |
| `delete` | store | removes the record; every other record untouched | never |

A successful command that would change nothing (e.g. `login` with a tally already at 0,
`unlock` on an unlocked account with a zero tally) may skip the write; the observable
behaviour is identical either way and tests must not depend on the file's mtime.
