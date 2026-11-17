# Phase 1 Data Model: Local Account Manager

**Feature**: `001-local-account-manager` | **Date**: 2026-11-16

Three entities from the spec — **Store**, **Account**, **Password** — plus the one in-memory
value type the modules pass around, `Result`. Format decisions come from
[research.md](./research.md) R-01 and R-02; the spec's assumption that "the store's on-disk
format is unspecified by this document" means this file, not `spec.md`, is where the format is
fixed, and the store is not a public interface.

---

## Store

The single file at `--store PATH`. Read whole at the start of every command, rewritten whole
(atomically) when a command changes it. The only persistent state the tool keeps.

### On-disk representation

UTF-8 JSON object, `indent=2`, `sort_keys=True`, one trailing newline.

```json
{
  "version": 1,
  "accounts": {
    "alice": {
      "salt": "3Q2+7wAAAAAAAAAAAAAAAA==",
      "verifier": "n0Zq...32-bytes-base64...=",
      "failed_logins": 0,
      "locked": false
    }
  }
}
```

### Fields

| Field | Type | Meaning |
|---|---|---|
| `version` | integer, exactly `1` | Format stamp. Any other value makes the file "not recognizable as a store" (FR-007). |
| `accounts` | object, username → Account record | May be empty (`{}`). Keys are the usernames; a username appears at most once, so uniqueness is a property of the format rather than a rule to enforce. |

### In-memory representation

A plain `dict[str, dict]` mapping username → record, as returned by `json.load`. No wrapper
class: the only operations needed are membership test, lookup, insert, and delete, which `dict`
provides, so a `Store` class would be an abstraction with a single caller (Principle IV).

### Lifecycle

| Situation | Behaviour | Requirement |
|---|---|---|
| Path does not exist | Treated as a store with no accounts. `register` will create it; `login` → status 1; `unlock`/`passwd`/`delete` → status 3. No file is created. | FR-002, "missing store file" edge case |
| Path exists, parses, validates | Loaded. | FR-002 |
| Path exists but cannot be read (permissions, is a directory) | `StoreError` naming the path → diagnostic + exit 2. Not overwritten, not treated as empty. | FR-007, R-04 |
| Path exists, bytes are not valid JSON | Same as above, diagnostic names the path and that it is not valid JSON. | FR-007 |
| Path exists, valid JSON but fails validation below | Same as above, diagnostic names the path and the structural problem. | FR-007 |
| A command changes the store | Temp file in the store's directory → `chmod 0o600` → `fsync` → `os.replace`. Either fully applied or prior contents intact. | FR-006, FR-008, FR-038, R-05 |
| Parent directory missing or not writable | `StoreError` naming the path → diagnostic + exit 2, before any account change is visible. | "unusable store path" edge case |

### Validation rules (load-time; any failure is `StoreError`)

1. Top-level value is a JSON object.
2. `version` is present and equals `1`.
3. `accounts` is present and is an object.
4. Every value in `accounts` is an object carrying exactly the keys `salt`, `verifier`,
   `failed_logins`, `locked` — no missing keys, no unknown keys.
5. `salt` and `verifier` are strings that decode as base64 (strict), to 16 and 32 bytes
   respectively.
6. `failed_logins` is an integer with `0 <= failed_logins`, and is not a `bool`.
7. `locked` is a boolean.

Rule 4's "no unknown keys" and rule 6's `bool` exclusion are deliberate strictness: JSON's
`true` is a valid Python `int`, and a silently ignored extra key is how a hand-edited store
would appear to work while meaning something else. Both are the Fail Loudly principle applied
to parsing — the alternative is defaulting around bad input, which the constitution prohibits.

Validation does *not* check the username keys against the 3–32-character format rule. Per the
spec's assumption, a badly formatted username is simply a username that does not exist for
every command except `register`, and `register` rejects it before lookup; a store containing
one is unusual but not malformed.

---

## Account

One named local identity. Stored as the record described above.

| Attribute | Stored as | Rules |
|---|---|---|
| Username | The key in `accounts` | 3–32 characters, each in `[A-Za-z0-9_]`. Enforced at `register` only (FR-010, FR-013). Boundaries: 3 and 32 valid; 2 and 33 rejected. |
| Password verifier | `verifier`, base64 of 32 bytes | PBKDF2-HMAC-SHA256 of the UTF-8 password with `salt`, 600,000 iterations. Never reversible, never printed (FR-036, FR-037). |
| Salt | `salt`, base64 of 16 bytes | `secrets.token_bytes(16)`, fresh at `register` and regenerated at every successful `passwd`. Distinct per account, so equal passwords yield different verifiers (FR-036). |
| Failed-login count | `failed_logins`, integer ≥ 0 | Consecutive failed logins since the last success or `unlock`. Incremented only by a failed `login`; zeroed by a successful `login` and by `unlock`. Untouched by `passwd` and `delete` (FR-019, FR-021, FR-022, FR-024). |
| Locked | `locked`, boolean | Set only when `failed_logins` reaches 5 during a failed `login`; cleared only by `unlock` (FR-019, FR-023). |

### Username validation

`len(username)` in `3..32` **and** `username.isascii() and all(c.isalnum() or c == "_" ...)` —
expressed as an explicit character-set test rather than `str.isalnum()` alone, because
`isalnum()` is true for non-ASCII letters and digits (`"éé1"`, `"١٢٣"`), which the rule
"letters, digits, and underscore" in a local-account context does not intend. A regular
expression `\A[A-Za-z0-9_]{3,32}\Z` is the equivalent form and is what the implementation uses.

### Password validation

`len(password) >= 12`, counted in characters (code points), not bytes. No character-class,
dictionary, or reuse rule; a new password equal to the current one is accepted (spec
assumption). Applied at `register` and at the new password of `passwd` (FR-011, FR-028).

### State transitions

```text
                      register (valid username+password, not present)
                                      │
                                      ▼
                        ┌──────── UNLOCKED ────────┐
                        │   failed_logins = 0      │
                        └──────────────────────────┘
                          │        ▲            │
   failed login           │        │            │  successful login
   (count < 5 after ++)   │        │            │  → count = 0
   → count++, status 1 ───┘        │            └──────────────┐
                                   │                           │
                          unlock   │                           ▼
                        → locked=false,              (stays UNLOCKED)
                          count = 0
                                   │
   5th consecutive failed login    │
   → count = 5, locked = true,     │
     status 1 (the 5th attempt     │
     still reports credentials)    │
                        │          │
                        ▼          │
                 ┌──────────────────────┐
                 │       LOCKED         │
                 │  login → status 4    │  ← correct or wrong password alike
                 │  passwd → allowed    │  (with correct current password)
                 │  delete → allowed    │  (with correct password)
                 │  unlock → UNLOCKED   │
                 └──────────────────────┘
                        │
                        │  delete (correct password), from either state
                        ▼
                    (record removed; username available to register again)
```

Two transitions worth stating explicitly because they are easy to get backwards:

- The fifth consecutive failure **reports `invalid credentials` with status 1** and locks the
  account; status 4 appears from the *next* login onward (spec assumption, SC-004).
- A successful `passwd` on a locked account **does not clear the lock** — only `unlock` does
  (FR-023, FR-025).

---

## Password

A caller-supplied secret, never an entity at rest. Arrives only as a line on standard input,
is held as a `str` for the lifetime of one command, is encoded to UTF-8 only inside
`passwords.py`, and is never stored, logged, echoed, or included in a diagnostic (FR-003,
FR-037, SC-006). It does not appear in the store's bytes in any readable form, and never in
`argv`.

---

## Result *(in-memory only)*

The value every command function in `commands.py` returns, so that no module except `cli.py`
touches a stream.

```python
@dataclass(frozen=True)
class Result:
    code: int         # 0, 1, 2, 3, or 4 — the process exit status
    out: str = ""     # written verbatim to stdout (empty on every failure path)
    err: str = ""     # written verbatim to stderr (empty on every success path)
    save: bool = False  # cli must persist the mutated store before exiting
```

Invariants, asserted in tests:

- `code == 0` implies `err == ""`; `code != 0` implies `out == ""` and `err != ""`. That pair
  is FR-004 and SC-008 expressed as a property of one type, which is why `Result` is a
  dataclass rather than a bare tuple.
- `save is True` only for the five successful commands and for a failed `login`.

`save` is a field rather than something `cli` infers from `code`, because FR-006 makes "exit
non-zero but still persist" a real case: a failed login must write its incremented
`failed_logins` and any resulting lock, while every other non-zero outcome must leave the file
untouched. No status code can express that distinction, so the command function states it.
