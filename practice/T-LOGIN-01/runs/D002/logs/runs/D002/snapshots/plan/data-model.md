# Data Model: Secure Login Web Application

**Feature**: `001-secure-login-app` | **Date**: 2026-10-23 | **Plan**: [plan.md](plan.md) | **Research**: [research.md](research.md)

The application has one persistent store, the accounts file. Everything else lives in memory and lasts only for one run of `serve`.

## Constants

These values are fixed in code (`src/loginapp/accounts.py`, `src/loginapp/server.py`, `src/loginapp/tokens.py`). Tests check them exactly.

| Name | Value | Requirement |
|------|-------|-------------|
| Username pattern | `^[A-Za-z0-9_]{3,32}$` (ASCII only, whole string) | FR-002 |
| Minimum password length | 12 characters | FR-003 |
| Hash function | `scrypt` (`hashlib.scrypt`) | FR-005 |
| scrypt `n` | 131072 (2^17) | FR-005 |
| scrypt `r` | 8 | FR-005 |
| scrypt `p` | 1 | FR-005 |
| Derived key length | 32 bytes | FR-005 |
| Salt length | 16 bytes, from `secrets.token_bytes` | FR-005 |
| scrypt `maxmem` | 268435456 (256 MiB) (a limit, not stored) | FR-005 |
| Hashes running at once | at most 4 (process-wide semaphore) | FR-030, FR-031 |
| Session lifetime | 1800 seconds | FR-024, FR-025, FR-026 |
| Failures that lock a username | 5 in a row | FR-030 |
| Lock duration | 900 seconds | FR-030 |
| Largest sign-in body | 65536 bytes | FR-015 |
| Listen address | `127.0.0.1` | FR-008 |

## Account

One person who can sign in. Stored in the accounts file under its username.

| Field | Type | Rule |
|-------|------|------|
| username (the key in `accounts`) | string | Matches the username pattern. Unique and case-sensitive: `Alice` and `alice` are different accounts. |
| `algorithm` | string | Exactly `"scrypt"` |
| `n` | integer | Exactly `131072` |
| `r` | integer | Exactly `8` |
| `p` | integer | Exactly `1` |
| `salt` | string | Exactly 32 lowercase hex characters (16 bytes). Random for each account. |
| `hash` | string | Exactly 64 lowercase hex characters (32 bytes): `scrypt(password.encode("utf-8"), salt, n, r, p, dklen=32)` |

- No other fields are allowed. The password itself is never stored (FR-005).
- `verify(password, record)` recomputes the hash with the record's salt and settings, then compares the result with `hmac.compare_digest`.
- The password is hashed exactly as typed, as its UTF-8 bytes, with no Unicode normalisation.
- Two accounts with the same password get different hashes, because their salts differ.

## Accounts file

The single file named by `--users`. Only `adduser` writes it, and `serve` only reads it.

```json
{
  "accounts": {
    "alice": {
      "algorithm": "scrypt",
      "hash": "9f2c…64 hex chars…",
      "n": 131072,
      "p": 1,
      "r": 8,
      "salt": "4b1e…32 hex chars…"
    }
  }
}
```

### Validity rules

A file breaking any of these rules is "not a valid accounts file" (FR-007, FR-010, FR-011):

1. It is UTF-8 text that parses as JSON. An empty file is invalid.
2. No JSON object anywhere in it has a duplicate key.
3. The top level is an object with exactly one key, `accounts`, whose value is an object. It may be empty.
4. Every key of `accounts` matches the username pattern.
5. Every value is an object with exactly the fields in the Account table, each meeting its rule.
   - The integers must be real JSON integers. `true` and `131072.0` are invalid.

Error messages name the file and the rule that failed (for example `account 'bob': field 'salt' must be 32 lowercase hex characters`). They never include a field's value (FR-029).

### Lifecycle

```text
(absent) --adduser ok--> present, mode 0600, 1 account
present  --adduser ok--> present, mode 0600, accounts + 1    (old accounts unchanged)
present  --adduser fails (any status)--> unchanged (bytes and mode)
```

- **Reading** opens the file and validates it.
  - In `adduser`, a missing file counts as an empty `accounts` object. Any other `OSError` is "cannot be read" (exit 1).
  - In `serve`, a missing file is an error.
    - At startup it means exit 1 (FR-010).
    - During a well-formed sign-in it means a 500 response (FR-011).
- **Writing** (`adduser` only) goes through a temporary file:
  1. Serialise with `json.dumps(obj, indent=2, sort_keys=True) + "\n"`.
  2. Create a temporary file with `tempfile.mkstemp(dir=<FILE's folder>, prefix="." + <FILE's name> + ".", suffix=".tmp")`. It gets mode `0600` from the start.
  3. Write, flush and `os.fsync`, then `os.replace(temp, FILE)`.
  4. On any error, remove the temporary file and exit 1 naming FILE.

  A reader therefore sees either the complete old file or the complete new one (FR-006, FR-011).

## Session token

A JWT in compact form (RFC 7519), carried in the `session` cookie.

```text
base64url(header) "." base64url(payload) "." base64url(signature)     (no "=" padding)

header    = {"alg":"HS256","typ":"JWT"}                       (these exact bytes)
payload   = {"sub":USERNAME,"iat":IAT,"exp":IAT+1800}        (json.dumps, separators=(",", ":"))
signature = HMAC-SHA256(key = LOGINAPP_SECRET.encode("utf-8"),
                        msg = ASCII(segment1 + "." + segment2))
```

| Claim | Type | Value |
|-------|------|-------|
| `sub` | string | The username that signed in |
| `iat` | integer | `int(clock())` at issue: whole seconds since the Unix epoch, rounded down |
| `exp` | integer | `iat + 1800` |

### Acceptance (FR-023)

`tokens.decode(token, secret, now)` returns the claims or raises `InvalidToken`. Each step must pass before the next one runs:

1. The token is ASCII with exactly two `.` characters, which gives three segments.
2. Every segment is non-empty, uses only `A–Z a–z 0–9 - _`, and is **canonical**: decoding it and encoding it again (without padding) gives the same text. This refuses added `=` padding and altered unused final bits (FR-020).
3. The header decodes to a JSON object with no duplicate keys, and its `alg` is the string `"HS256"`. Other header fields are allowed.
4. `hmac.compare_digest(signature, HMAC-SHA256(secret, segment1 + "." + segment2))` is true.
5. The payload is a JSON object with no duplicate keys. `sub` is a `str`; `iat` and `exp` are `int` and not `bool`.
6. `now < exp`. There is no clock tolerance, so at `now == exp` the token is refused.

The server then adds the checks that need state, with the token's exact string as the key:

7. The token is in this run's **issued-token registry** (FR-027).
8. The token is not in the **signed-out map** (FR-020).

## Issued-token registry (in memory)

`issued: dict[str, int]`, mapping a token string to its `exp`. It is owned by the running `LoginServer` and guarded by the server's state lock.

- **Added**: when a sign-in succeeds, before the 303 response is written.
- **Removed**:
  - when the token is signed out (it moves to the signed-out map);
  - when it has expired, by a sweep at each sign-in and sign-out that removes every entry with `exp <= now`.
- **Lost** when the server stops. A new run starts empty, so it refuses every token from an earlier run (FR-027).

## Signed-out map (in memory)

`signed_out: dict[str, int]`, mapping a token string to its `exp`. Same owner and lock.

- **Added**: by `POST /logout` when the presented token is valid at that moment, in the same critical section that removes it from `issued`, before the response is written (FR-020).
- **Removed**: by the same expiry sweep, and when the server stops.
- Its only other job is to stop a new sign-in from producing a byte-identical token while the old one is still unexpired (see [Issuing a token](#issuing-a-token)).

## Issuing a token

The server records `run_start = int(clock())` immediately after it binds the port, before it prints `listening on`. After a password has been verified, it issues a token like this:

```text
loop:
    with state lock:
        iat = int(clock())
        token = encode(sub, iat, secret)
        if iat > run_start and token not in signed_out:
            issued[token] = iat + 1800
            return token
    sleep(iat + 1 - clock())        # outside the lock; at most 1 second
```

- An earlier run on the same port stopped issuing tokens before this run could bind the port. Its tokens therefore all have `iat <= run_start`. Because of the `iat > run_start` rule, this run can never re-issue an earlier run's bytes (FR-027). This covers an earlier run's signed-out tokens too (FR-020). Two servers running at the same time on different ports are not a restart, and this rule does not cover them.
- The `signed_out` rule stops a same-second sign-in from re-issuing a token that was just signed out (FR-020).
- The wait adds at most 1 s, so a sign-in still finishes in under 2 s (SC-002).
- If the same user signs in twice in the same second without signing out, both get the same token. This is accepted (spec Edge Cases).

## Session lifecycle

```text
           sign-in ok
(none) ─────────────────▶ ACTIVE ──── now >= exp ─────────▶ EXPIRED   (refused, swept)
                            │
                            ├── POST /logout ──────────────▶ SIGNED-OUT (refused until exp)
                            │
                            └── server stops ──────────────▶ ENDED     (refused by every later run)
```

- Only ACTIVE tokens open the dashboard.
- `GET /dashboard` never changes a token's state and never sets a cookie (FR-026).
- A lock on the username does not affect ACTIVE tokens (FR-030).

## Sign-in lock state (in memory)

These maps are owned by the running `LoginServer` and guarded by the same state lock:

- `failures: dict[str, int]`: username → failed attempts in a row. A missing key means 0.
- `locked_at: dict[str, float]`: username → `clock()` at the fifth failure.

Keys are added only for usernames that exist in the accounts file at the time of the attempt. A restart clears both maps.

### Transitions for a well-formed attempt

These run under the state lock, after hashing, with the attempt time `t = clock()`. The username exists in the file.

```text
                 wrong password (count < 4): count += 1
               ┌──────────────┐
               ▼              │
   UNLOCKED(count) ───────────┘
      │    │
      │    └─ correct password ──▶ UNLOCKED(0) + token issued
      │
      └─ wrong password (count == 4) ──▶ LOCKED(locked_at = t), count = 0

   LOCKED(s):
      t - s <  900 ─▶ refused (standard 401); nothing counted; s unchanged
      t - s >= 900 ─▶ lock cleared, count = 0, attempt handled as UNLOCKED(0)
```

- An attempt for a username that has no account is refused and changes no state.
- A malformed submission (FR-015) changes no state and does not read the file.
- One critical section covers the lock check, the comparison of the password result and the update. As a result, 10 simultaneous wrong attempts give exactly 5 counted failures and a lock, and the other 5 find the lock in place (FR-030).

## Server secret

- `LOGINAPP_SECRET`, read once by `serve` at startup. It must be non-empty and encodable as UTF-8.
- It is held in memory only, passed to `tokens.encode` and `tokens.decode` as `secret.encode("utf-8")`, and never printed (FR-029).
