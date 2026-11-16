# Phase 1 Data Model: Burn-After-Reading and Password-Protected Pastes

**Feature**: `002-burn-and-password-pastes` | **Date**: 2026-11-16 | **Plan**: [plan.md](./plan.md)

This document is a **delta** on [the 001 data model](../001-pastebin-service/data-model.md), which
remains in force in full. Everything not restated here is unchanged. Decisions referenced as
`R-nn` are in [research.md](./research.md) (R-16 …) or in
[001/research.md](../001-pastebin-service/research.md) (R-01 … R-15).

---

## Entity: Paste *(extended)*

Still a single immutable shared snippet. Two attributes are added; both default to "off" and
neither changes the meaning of any existing attribute.

### Fields

New rows in **bold**; existing rows are repeated only for context.

| Field | Type | Stored | Returned by `GET /pastes/<id>` | Notes |
|---|---|---|---|---|
| `id` | `str` | yes | yes | unchanged |
| `content` | `str` | yes | yes | unchanged |
| `created_at` | `str` | yes | yes | unchanged |
| `expires_at` | `str \| null` | yes | yes | unchanged |
| `delete_token` | `str` | yes | **never** | unchanged — still the only stored-but-never-returned field prior to this feature |
| **`burn_after_reading`** | **`bool`** | **yes (optional key)** | **yes** | **absent ⇒ `false` (FR-051). The paste ceases to exist upon its first successful read** |
| **`password`** | **`object \| null`** | **yes (optional key)** | **never — derived `protected` is returned instead** | **A non-recoverable salted verifier (R-16, R-17). Absent or `null` ⇒ unprotected** |
| **`protected`** | **`bool`** | **no — derived** | **yes** | **`record["password"] is not None` (FR-037, FR-038)** |

`password` joins `delete_token` as a field that is stored and never returned. Unlike
`delete_token`, it is never returned **at all** — not even once, not by the `201` that creates the
paste (FR-035). What callers see is the derived boolean `protected`.

### Password verifier sub-object

```json
"password": {
  "algorithm":  "pbkdf2_sha256",
  "iterations": 600000,
  "salt":       "<32 lowercase hex characters — 16 random bytes>",
  "hash":       "<64 lowercase hex characters — 32-byte derived key>"
}
```

| Property | Value | Requirement |
|---|---|---|
| Algorithm | `hashlib.pbkdf2_hmac("sha256", …)` | SR-013, R-16 |
| Iterations | 600 000 (OWASP current recommendation) | SR-013 |
| Salt | 16 bytes from `secrets.token_bytes`, **per paste**, never reused | SR-013 |
| Derived key length | 32 bytes | SR-013 |
| Comparison | `hmac.compare_digest` over the two 32-byte digests | SR-014, R-18 |
| Plaintext | never written to disk, to a response, or to process output | SR-013, SR-019 |

### Creation validation rules *(replaces the 001 table)*

Applied in this order on `POST /pastes`; each row is the first failure that applies. Rules 1-10
are unchanged from 001. Rules 11-13 are new; rule 14 is 001's rule 11, **moved to last** (R-22).

| # | Rule | Violation response | Requirement |
|---|---|---|---|
| 1 | `Content-Length` present, non-negative, no `Transfer-Encoding` | `400` | SR-005 |
| 2 | `Content-Length` ≤ 66 560 | `413` *(body not read)* | FR-029, SR-005 |
| 3 | Body delivers exactly `Content-Length` bytes | `400` | SR-005 |
| 4 | Body decodes as UTF-8 | `400` | FR-026 |
| 5 | Body parses as JSON | `400` | FR-026 |
| 6 | Parsed value is a JSON object | `400` | FR-026 |
| 7 | `content` key present | `400` | FR-006 |
| 8 | `type(content) is str` | `400` | FR-006 |
| 9 | If `expires_in` present: `type(...) is int` | `400` | FR-008 |
| 10 | If `expires_in` present: `1 … 2 592 000` | `400` | FR-008 |
| **11** | **If `burn_after_reading` present: `type(...) is bool`** | **`400`** | **FR-031** |
| **12** | **If `password` present: `type(...) is str`** | **`400`** | **FR-033** |
| **13** | **If `password` present: `1 ≤ len(password) ≤ 128` characters** | **`400`** | **FR-033** |
| 14 | `len(content.encode("utf-8")) ≤ 65 536` | `413` | FR-007, FR-027, **FR-036** |

Rule 14's position is load-bearing: it is what makes an invalid new field report `400` rather than
`413`, while an otherwise-valid oversized submission still reports `413` (FR-036 vs FR-027).

Keys other than `content`, `expires_in`, `burn_after_reading`, and `password` are still not
inspected and never cause rejection (FR-009, spec Assumption "Unknown fields are still ignored").

**Boundary values** (new rows only; the 001 table still applies):

| Input | Outcome | Source |
|---|---|---|
| `burn_after_reading` absent | accepted ⇒ `false` | FR-030 |
| `burn_after_reading` = `false` | accepted; identical behaviour to absence | Edge Case "Marking explicitly false" |
| `burn_after_reading` = `true` | accepted; one-time | FR-030 |
| `burn_after_reading` = `"true"`, `"false"`, `0`, `1`, `null`, `[]`, `{}` | `400` | FR-031 |
| `password` absent | accepted ⇒ unprotected | FR-032 |
| `password` = `"x"` (1 character) | accepted — smallest | FR-032 |
| `password` = 128 characters | accepted — largest | FR-033 |
| `password` = 128 **multi-byte** characters (e.g. 512 UTF-8 bytes) | accepted — the bound is characters | FR-033 |
| `password` = 129 characters | `400` | FR-033 |
| `password` = `""` | `400` | Edge Case "Password is the empty string" |
| `password` = `null`, `5`, `true`, `[]`, `{}` | `400` | FR-033 |
| `password` containing spaces, punctuation, emoji, non-ASCII | accepted; identical value grants access | FR-034 |
| Both new fields invalid | `400`, exactly one message, nothing created | Edge Case "Both new fields invalid" |
| Invalid new field **and** oversized content | `400` (not `413`) | FR-036 |
| Valid new fields **and** oversized content | `413` | FR-027 |

### Derived values

- `burn_after_reading` is stored as given (or `false`); nothing is derived from it.
- `password` verifier = `{algorithm, iterations, salt: hex(secrets.token_bytes(16)), hash:
  hex(pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000, dklen=32))}`. The salt is
  drawn per paste and never reused, so two pastes created with the same password have unrelated
  stored hashes (SR-013).
- `protected` = `record["password"] is not None`, computed per response, never stored (R-17).

### Lifecycle / state transitions *(extends the 001 diagram)*

```text
                   POST /pastes (valid)
                           │
                           ▼
                  ┌─────────────────┐
                  │      LIVE       │  readable (password if protected), revocable
                  └────────┬────────┘
                           │
        ┌──────────────────┼───────────────────────┬──────────────────────┐
        │                  │                       │                      │
 now > expires_at   DELETE with correct   ***first successful read***     │
 (no action taken)   delete_token          ***of a one-time paste***      │
        │                  │                (FR-044, R-20)                │
        │                  ▼                       │                      │
        │          ┌─────────────────┐             │                      │
        │          │     REMOVED     │◄────────────┘                      │
        │          │ record unlinked │                                    │
        │          └────────┬────────┘                                    │
        ▼                   │                                             │
┌─────────────────┐         │                                             │
│     EXPIRED     │─────────┤                                             │
└────────┬────────┘         │        refused read (403) / failed revoke ──┘
         │                  │        (403) / unrouted request (404)
         │                  │        ⇒ **no transition**, paste stays LIVE
         ▼                  ▼        (FR-046)
   Indistinguishable from NEVER EXISTED:
   GET /pastes/<id>      → 404   (whatever password is supplied, FR-043)
   GET /pastes/<id>/raw  → 404
   DELETE /pastes/<id>   → 404   (whatever token is supplied, FR-021/FR-045)
```

Key consequences:

- **CONSUMED is not a state.** A one-time paste that has been read is `REMOVED` — the same
  terminal state revocation produces, reached by a different door. From every caller's point of
  view a consumed paste is indistinguishable from a revoked one and from one that never existed
  (spec Assumption "Destruction means removal", FR-045).
- **Only a *successful* read transitions.** A read refused for a missing or wrong password, a
  request for an identifier that does not resolve, an unsupported method or address, and a refused
  revocation all leave `LIVE` untouched (FR-046, SC-014).
- **Expiry is still independent.** An unread one-time paste past its expiry instant is
  non-existent; the liveness predicate is evaluated before anything else and is unchanged
  (FR-049).
- **Protection does not create a state.** `protected` is a property of the record, not a phase of
  its life; it never changes, because pastes are immutable and there is no add/change/remove
  password operation (spec Assumption "No password change, no password recovery").

**Liveness predicate** — unchanged from 001, and deliberately so: it is evaluated before any
password check, which is what gives FR-043 its precedence.

```text
live  ⟺  record exists on disk
      ∧  record parses as a valid paste        ← now also: new fields are well-shaped (R-17)
      ∧  (expires_at is null ∨ now <= expires_at)
```

### Authorization rules *(replaces the 001 table)*

| Operation | Credential required | Consumes a one-time paste? |
|---|---|---|
| `GET /pastes/<id>` | possession of `id`; **plus `X-Paste-Password` if protected** | **yes, on success** |
| `GET /pastes/<id>/raw` | possession of `id`; **plus `X-Paste-Password` if protected** | **yes, on success** |
| `DELETE /pastes/<id>` | possession of `id` **and** `X-Delete-Token` — **never the password** | no (FR-046, FR-050) |

**Evaluation order on a read** (R-21), load-bearing in both of its steps:

```text
404  identifier invalid / record absent / record unusable / expired
403  protected and X-Paste-Password missing, undecodable, or not equal to the stored password
404  one-time and the claim (os.unlink) did not succeed — another reader won the race
200  serve
```

1. `404` **before** `403` (FR-043): a refusal is only ever returned for an identifier that really
   resolves to a live paste, so the `403`/`404` distinction never tells a caller that an invented
   identifier is real. This is the same precedence `delete_record` already applies.
2. `403` **before** the claim (FR-046, User Story 3): a reader who cannot prove they hold the
   password never consumes the single read, so a stranger with the link cannot destroy a paste
   they were never entitled to see.

The password is verified server-side against the stored record on **every** read, in **both** read
forms, using `hmac.compare_digest` over derived digests. It is never cached, never carried in a
cookie or session, and no client-supplied claim other than the password itself is consulted
(SR-015). The service holds no cross-request state of any kind, so this is structural rather than
enforced.

A password header on an **unprotected** paste is never read and has no effect (FR-042). A password
header on a **revocation** is never read and has no effect (FR-050).

---

## Entity: Paste store *(extended)*

### Physical layout

Unchanged — `<data_dir>/<id>.json` at `0600` inside a `0700` directory, written via `O_EXCL` temp
file + `fsync` + `os.replace`. No new file, no index, no sidecar, no startup scan.

### Record file format

Two optional keys are added. A record carrying neither is exactly a pre-feature record, which is
what makes FR-051 and SC-019 hold with no migration (R-17).

```json
{
  "id": "QnJ3c2VyLVNhZmUtSWQ",
  "content": "hello",
  "created_at": "2026-11-16T09:41:07Z",
  "expires_at": "2026-11-16T10:41:07Z",
  "delete_token": "9rYQ0s3Xz2mKpLv8wTnB4jHcFdEaGuRi7NsOyPqZlMk",
  "burn_after_reading": true,
  "password": {
    "algorithm": "pbkdf2_sha256",
    "iterations": 600000,
    "salt": "3f9a1c7d5e2b48a06d1f8c3b9e04a7d2",
    "hash": "7c1d…"
  }
}
```

`RECORD_FIELDS` — the keys a record must carry to be recognisable at all — stays
`("id", "content", "created_at", "expires_at", "delete_token")`. The new keys are **optional**,
which is precisely why legacy records remain valid.

### Stored-record interpretation rules

Applied in `store._load`, so every caller (read, raw read, revoke) inherits them identically.

| Stored shape | Interpretation | Requirement |
|---|---|---|
| `burn_after_reading` absent | `false` | FR-051 |
| `burn_after_reading` is `true` / `false` (`type(...) is bool`) | that value | FR-052 |
| `burn_after_reading` is anything else | **record unusable ⇒ paste does not exist (`404`)** | SR-020 |
| `password` absent or `null` | unprotected | FR-051 |
| `password` is an object with exactly `{algorithm, iterations, salt, hash}`, `algorithm == "pbkdf2_sha256"`, `type(iterations) is int` within `[1, 10 000 000]`, `salt` 32 hex chars, `hash` 64 hex chars | protected; verify against it | FR-052 |
| `password` is anything else | **record unusable ⇒ paste does not exist (`404`)** | SR-020 |

**The two directions are deliberately asymmetric.** *Absent* means off, because that is what every
legacy record looks like and treating it as corrupt would destroy pastes the operator still owns.
*Malformed* means gone, because the only alternatives are serving a protected paste without
checking a password or serving a one-time paste twice — both SR-017 violations. This is the
existing FR-024 rule ("a record that does not parse is a paste that does not exist") extended to
the new fields, not a new policy.

The `iterations` upper bound is a control, not a formality: a record claiming `10**12` iterations
would otherwise wedge a request thread for hours, which SR-018 forbids.

### Operations *(delta)*

| Operation | Implementation | Guarantees |
|---|---|---|
| `write_record(record)` | unchanged, now carrying the two extra keys when set | unchanged (SR-007, SR-008, FR-023) |
| `read_record(id)` | unchanged, plus the interpretation rules above in `_load` | malformed new fields ⇒ absent (SR-020) |
| **`consume_record(id) -> bool`** | **under the existing store lock: `os.unlink(path)`. `True` if it removed the entry, `False` on `FileNotFoundError`; any other `OSError` propagates** | **the claim is atomic — of N concurrent callers exactly one gets `True` (SR-016, R-20)** |
| `delete_record(id, token)` | unchanged — token only, never the password | FR-050 |

### Concurrency model *(delta)*

- `os.unlink` is atomic with respect to the directory entry: of N concurrent calls naming the same
  path, exactly one succeeds and the rest raise `ENOENT`. That single syscall is the one-time
  paste's claim; nothing else is needed to decide a winner (SR-016, FR-047).
- Content is read **before** the claim and written to the socket **only after** it. Records are
  immutable, so the bytes read are the bytes claimed. A caller that loses the race has already
  read the content into memory and discards it without writing a byte — no partial or truncated
  text ever reaches a socket (FR-047, SC-015).
- The claim is taken under the store's **existing** `threading.Lock`, the same one `delete_record`
  holds, so the two destructive paths have one serialization point. No second lock and no
  per-identifier lock registry is introduced (R-09's rejection stands).
- A concurrent read **and** revocation of the same one-time paste: each ends in an `unlink`, one
  wins, the loser reports `404`; the paste is gone either way and the content is returned at most
  once (Edge Case "Simultaneous read and revocation").
- Non-burn reads continue to take **no** lock (R-09) — their behaviour is byte-for-byte unchanged,
  which is what FR-053 requires.

### Durability

- Creation durability is unchanged (`fsync` before `os.replace`, R-03) and now covers the two new
  keys, so a one-time paste is still one-time and a protected paste still requires the same
  password after a restart (FR-052, SC-018).
- Destruction durability (FR-048) needs nothing new: the unlinked directory entry is gone from the
  filesystem's view the moment the call returns, so a restarted service against the same directory
  finds nothing. No `fsync` of the directory is performed — no stated requirement concerns
  machine-level crash consistency, and R-20 records that choice.

---

## Field-to-requirement traceability *(new rows only)*

| Field / rule | Requirements |
|---|---|
| `burn_after_reading` accepted, optional, defaults false | FR-030 |
| `burn_after_reading` type rejection | FR-031 |
| `password` accepted, optional, 1-128 characters | FR-032 |
| `password` type and length rejection, measured in characters | FR-033 |
| `password` character set; identical value grants access | FR-034 |
| `201` body shape unchanged, no echo of either option | FR-035 |
| New fields validated before the size rule | FR-036 |
| `burn_after_reading` + `protected` in the structured read | FR-037 |
| `protected` reports only *whether*; no derived value disclosed | FR-038, SR-019 |
| `/raw` body and headers unchanged | FR-039 |
| `403` on a protected read without the correct header | FR-040, SR-015 |
| Refused read discloses nothing and leaves the paste readable | FR-041, SC-012 |
| Password header ignored on an unprotected paste | FR-042 |
| `404` before `403` for unknown/expired/revoked/consumed | FR-043, SC-016 |
| First successful read returns then destroys | FR-044, SC-011 |
| Every later request `404` | FR-045 |
| No unsuccessful request consumes | FR-046, SC-014 |
| Concurrent reads: at most one success, no truncation | FR-047, SR-016, SC-015 |
| Destruction durable across restart | FR-048, SC-018 |
| Expiry independent of consumption | FR-049 |
| Revocation needs the token alone | FR-050 |
| Legacy record ⇒ not one-time, not protected | FR-051, SC-019 |
| Both options survive restart | FR-052, SC-018 |
| All 001 behaviour unchanged apart from the two flags | FR-053, SC-020 |
| Error bodies keep the `{"error": …}` shape | FR-054 |
| Salted slow hash, per-paste salt, never plaintext | SR-013, SC-017 |
| Constant-time verification over derived digests | SR-014 |
| Server-side check on every read, both forms, uncached | SR-015 |
| Atomic claim-and-destroy | SR-016 |
| No route, method, or encoding bypasses either protection | SR-017 |
| Allowlist validation before storage/hashing; bounded work | SR-018 |
| No password, hash, salt, or parameter in any output | SR-019, SC-017 |
| Fail closed when protection state is undeterminable | SR-020 |
