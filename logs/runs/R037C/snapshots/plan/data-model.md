# Phase 1 Data Model: Burn After Reading and Password Protection

**Feature**: `002-burn-after-reading-password` | **Date**: 2026-11-20

A **delta** against [001's data model](../001-pastebin-service/data-model.md). Everything there
still holds; only the additions and the one changed lifecycle are restated here. Validation-rule
identifiers continue from `V-10`, storage invariants from `S-8`.

---

## 1. Entity: Paste — two new attributes

### In-memory representation

`storage.Paste` stays a frozen dataclass of plain data (Constitution IV). Existing fields — `id`,
`content`, `created_at`, `expires_at`, `delete_token` — keep their names, types, and meanings.
Three fields are added:

| Field | Type | Meaning |
|---|---|---|
| `burn_after_reading` | `bool` | Whether the first successful read destroys the paste. `False` for a paste created without the option and for every record written by the previous version. |
| `password_salt` | `str \| None` | Hex-encoded 16 random bytes, or `None` when the paste is unprotected. |
| `password_hash` | `str \| None` | Hex-encoded PBKDF2-HMAC-SHA256 derivation of the password with `password_salt`, or `None` when unprotected. |

The two password fields are always both set or both `None`; a record with one of them is malformed
(S-10). The plaintext password is **never** a field of `Paste` — it exists only as a local variable
during creation and during one verification (FR-046).

### Derived values

| Derived | From | Where it surfaces |
|---|---|---|
| `protected` | `password_hash is not None` | `GET /pastes/<id>` body (FR-054, FR-055); the decision to require the header (FR-040) |
| `burn_after_reading` | stored directly | `GET /pastes/<id>` body (FR-054, FR-055); the decision to claim on read (FR-047) |

`protected` is the *only* visibility into a password (spec assumption). Nothing derives the password
itself; nothing can.

### Validation rules — creation body (continuing V-1…V-10)

| ID | Rule | Failure | Requirement |
|---|---|---|---|
| V-11 | `burn_after_reading`, if present, is a `bool` — a real JSON boolean | `400` | FR-034 |
| V-12 | `password`, if present, is a `str` | `400` | FR-036 |
| V-13 | `password`, if present, satisfies `1 <= len(password) <= 128`, **counted in characters** | `400` | FR-036 |
| V-14 | V-11…V-13 are evaluated **after** V-1…V-7, so no existing rejection's status changes | — | FR-039 |

Notes:

- V-11 rejects `"true"`, `"false"`, `1`, `0`, `1.0`, `null`, `[]`, and `{}`. In Python
  `isinstance(True, int)` is `True`, so the check is `isinstance(value, bool)` and numbers never
  pass it (spec edge case "numbers are not booleans").
- Absent `burn_after_reading` and explicit `false` are indistinguishable from this point on
  (FR-033, spec edge case). JSON `null` is *present and invalid*, matching how `expires_in` already
  treats `null` (V-6).
- V-13 is measured in characters (`len(str)`), deliberately unlike V-5's byte measurement of
  `content`: a 128-character password of multi-byte characters is accepted even though its UTF-8
  encoding is longer (FR-036, spec edge case). The boundaries are inclusive — 1 and 128 both pass,
  0 (`""`) and 129 both fail.
- V-8 is unchanged and still applies: keys other than `content`, `expires_in`,
  `burn_after_reading`, and `password` are ignored, not rejected (FR-007, spec edge case).
- Nothing is written to storage on any of these failures, because all validation completes before
  `storage.create_paste` is called (FR-038).

### Validation rules — read request

| ID | Rule | Failure | Requirement |
|---|---|---|---|
| V-15 | For a protected paste, exactly one `X-Paste-Password` header occurrence is present | `403` | FR-041 |
| V-16 | For a protected paste, the supplied value derives to the stored `password_hash` under `password_salt`, compared with `secrets.compare_digest` | `403` | FR-040, FR-041, FR-043 |
| V-17 | For an unprotected paste, `X-Paste-Password` is not examined at all | — | FR-044 |

V-15 and V-16 apply to both `GET /pastes/<id>` and `GET /pastes/<id>/raw`, and to neither `POST`
nor `DELETE` (FR-045, spec edge case "`X-Paste-Password` on a route that does not read a snippet").

### Lifecycle — one new exit

```text
                   POST /pastes (V-1…V-13)
                            │ 201
                            ▼
                      ┌──────────┐
                      │ READABLE │◄──── reads that fail (403 wrong/missing password,
                      └────┬─────┘      404 ill-shaped id) leave this state untouched
          ┌────────────────┼────────────────┐
          │                │                │
   DELETE + token   expires_at reached   first successful read
          │                │              of a burn paste
          ▼                ▼                ▼
       ┌──────────────────────────────────────┐
       │                GONE                   │  every later read → 404
       └──────────────────────────────────────┘  every later delete → 404 (consumed)
```

| Transition | Trigger | Response | Requirement |
|---|---|---|---|
| READABLE → GONE (consumed) | a read of a `burn_after_reading` paste that gets past existence, expiry, and password, and wins the claim | the read itself answers `200` with the full content | FR-047 |
| READABLE (unchanged) | a read that answers `403` or `404` | `403` / `404`; the paste keeps its one read | FR-050, SC-019 |
| GONE → GONE | any read or delete after consumption | `404`, including a delete with the original token | FR-048 |
| READABLE → GONE (deleted) | `DELETE` with the token, before any read, on a burn paste | `204` | FR-053 |

Ordering inside a read route is **contractual** and extends 001's `404`-before-`403` rule with a
third step:

```text
1. id allow-list, existence, expiry   → 404   (FR-042, FR-052)
2. password                            → 403   (FR-041)
3. claim (burn pastes only)            → 404 if the claim is lost (FR-049)
4. serve 200 from the in-memory copy
```

Step 1 before step 2 is what keeps a protected paste indistinguishable from a non-existent one
(FR-042, SC-014). Step 2 before step 3 is what makes a refused read free (FR-050). Step 3 before
step 4 is what makes two simultaneous reads resolve to one `200` and one `404` (FR-049).

---

## 2. Entity: Read password

The second credential in the system, and the first that governs reading.

| Property | Value |
|---|---|
| Chosen by | the creator, in the creation body — not issued by the service |
| Length | 1…128 characters inclusive (V-13) |
| Scope | exactly one paste |
| Presented as | request header `X-Paste-Password`, on both read routes only |
| Stored as | per-paste random salt + PBKDF2-HMAC-SHA256 derivation; the plaintext is never stored (FR-046) |
| Compared | exactly — no case folding, trimming, or Unicode normalisation — and in constant time (FR-043) |
| Disclosed | never, in no response body or header, at any status (FR-046, SC-020) |
| Observable as | the boolean `protected` in the JSON read body, readable only by someone who already passed the password gate |
| Relationship to the deletion token | fully independent: neither substitutes for the other (FR-045) |
| Changeable | no. A paste is immutable once created; there is no route to set, change, or clear a password (spec assumption) |

**Not** rate-limited and **not** locked out after repeated failures: the service is loopback-only and
single-operator (spec assumption). Wrong attempts appear only in the ordinary per-request stderr log
line, which never contains a body or this header's value.

---

## 3. Entity: Storage directory — record format, extended

### Record format (internal — NOT part of the external contract)

`version` **stays `1`** (R-017). Three keys are added; all three are written on every create and all
three are optional on read.

```json
{
  "version": 1,
  "id": "V1StGXR8_Z5jdHi6B-myT",
  "content": "hello",
  "created_at": 1763596800,
  "expires_at": null,
  "delete_token": "…43 chars…",
  "burn_after_reading": false,
  "password_salt": null,
  "password_hash": null
}
```

| Key | Type on disk | Absent means | Present-but-malformed |
|---|---|---|---|
| `burn_after_reading` | `true` / `false` | `false` | `_BadRecord` → reported on stderr, record skipped, reads answer `404` |
| `password_salt` | hex string (32 chars) or `null` | `null` (unprotected) | `_BadRecord` |
| `password_hash` | hex string (64 chars) or `null` | `null` (unprotected) | `_BadRecord` |

A record written by the **previous version** has none of the three keys and therefore loads as a
readable, repeatedly-readable, unprotected paste with its content, id, `created_at`, `expires_at`,
and `delete_token` unchanged (FR-058, SC-017).

A malformed new key is reported and skipped rather than defaulted, because silently serving a paste
that was created as one-time an unlimited number of times is the "silent wrong answer" Constitution
II calls the highest-severity defect — and because 001's FR-032 already established report-and-skip
as the behaviour for any unusable record (spec edge case).

### Invariants (continuing S-1…S-8)

| ID | Invariant | Requirement |
|---|---|---|
| S-9 | Consumption of a one-time paste is a single `os.unlink` of its record: exactly one concurrent caller succeeds, the rest get `FileNotFoundError` → `404`. No lock, no index, no tombstone — S-8 ("the directory contents are the whole truth") still holds. | FR-049, SC-012 |
| S-10 | The two password fields are consistent: both `null` (unprotected) or both well-formed hex strings (protected). One without the other is `_BadRecord`. | FR-046, FR-057 |
| S-11 | The plaintext password never reaches the filesystem, a log line, or a response — only the salt and the derivation are persisted, and neither is ever serialised into a response. | FR-046, SC-020 |
| S-12 | Content is fully in memory before the claim in S-9 is attempted, so a served read never depends on the file still existing: no read returns partial or corrupt content. | FR-049 |
| S-1…S-8 | unchanged | — |

### Failure modes at startup

Unchanged from 001: `scan_directory` reports and skips every unusable entry and never blocks
startup (FR-032, S-6). It now also reports a version-1 record whose new keys are malformed, because
it validates records through the same `_read_paste` the read path uses — one reader, one notion of
"usable record" (spec edge case, FR-058).

---

## 4. Non-entities (still explicitly out of scope)

Everything 001 excluded, plus:

- **No read counter and no "reads remaining"**: a paste is one-time or unlimited, nothing in
  between, and nothing reports how many reads are left (spec assumption).
- **No re-arming** a consumed paste and **no un-burning**.
- **No password change, removal, or rotation** route, and no way to learn a password.
- **No per-password rate limit, lockout, or audit record** beyond the ordinary request log line.
- **No new route, header, or response field** beyond `burn_after_reading`, `protected`, and
  `X-Paste-Password`.
