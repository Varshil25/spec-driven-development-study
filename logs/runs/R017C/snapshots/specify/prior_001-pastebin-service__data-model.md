# Phase 1 Data Model: Pastebin Service

**Feature**: `001-pastebin-service` | **Date**: 2026-11-16 | **Plan**: [plan.md](./plan.md)

Entities are drawn from the spec's **Key Entities** section. Decisions referenced as `R-nn` are
recorded in [research.md](./research.md).

---

## Entity: Paste

A single shared snippet. Immutable once created — there is no update operation (spec Assumption
"Editing is out of scope"). It exists from creation until it expires or is revoked, after which it
is indistinguishable from a paste that never existed (FR-017, FR-022).

### Fields

| Field | Type | Stored | Returned by `GET /pastes/<id>` | Notes |
|---|---|---|---|---|
| `id` | `str` | yes | yes | 22 chars, `[A-Za-z0-9_-]`, 128 bits CSPRNG entropy (R-04) |
| `content` | `str` | yes | yes | UTF-8 text, ≤ 65 536 **encoded bytes**; empty string is valid |
| `created_at` | `str` | yes | yes | ISO 8601 UTC, second precision, `Z` suffix |
| `expires_at` | `str \| null` | yes | yes | Same format, or `null` for "never" |
| `delete_token` | `str` | yes | **never** | 43 chars, 256 bits CSPRNG entropy (R-04) |

`delete_token` is the only field that is stored but never returned by any read (FR-013, SR-009).
It is disclosed exactly once, in the `201` response to the creating request.

### Validation rules

Applied in this order on `POST /pastes` (R-10). Each row is the first failure that applies.

| # | Rule | Violation response | Requirement |
|---|---|---|---|
| 1 | `Content-Length` header present, a non-negative integer, and `Transfer-Encoding: chunked` absent | `400` | SR-005 |
| 2 | `Content-Length` ≤ 66 560 (65 536 + 1 024 envelope slack) | `413` *(body not read)* | FR-029, SR-005 |
| 3 | Body delivers exactly `Content-Length` bytes | `400` | SR-005 |
| 4 | Body decodes as UTF-8 | `400` | FR-026 |
| 5 | Body parses as JSON | `400` | FR-026 |
| 6 | Parsed value is a JSON object (not list, number, string, `null`, bool) | `400` | FR-026 |
| 7 | `content` key is present | `400` | FR-006, FR-026 |
| 8 | `type(content) is str` — **not** `isinstance` | `400` | FR-006, FR-026 |
| 9 | If `expires_in` present: `type(expires_in) is int` (rejects `bool`, `float`, `str`) | `400` | FR-008 |
| 10 | If `expires_in` present: `1 <= expires_in <= 2_592_000` | `400` | FR-008 |
| 11 | `len(content.encode("utf-8")) <= 65_536` | `413` | FR-007, FR-027 |

Keys other than `content` and `expires_in` are not inspected and never cause rejection (FR-009).

**Boundary values** (from spec Edge Cases):

| Input | Outcome |
|---|---|
| `content` = `""` | accepted — stored and returned as empty (not treated as missing) |
| `content` encoding to exactly 65 536 bytes | accepted |
| `content` encoding to 65 537 bytes | `413` |
| `expires_in` = `1` | accepted (smallest) |
| `expires_in` = `2592000` | accepted (largest, 30 days) |
| `expires_in` = `0`, `-1`, `2592001` | `400` |
| `expires_in` = `3600.0`, `"3600"`, `true`, `false`, `null` | `400` |
| `expires_in` absent | accepted — `expires_at` is `null` (never expires) |

### Derived values

- `created_at` = `datetime.now(UTC).replace(microsecond=0)`, captured once per creation (R-08).
- `expires_at` = `created_at + timedelta(seconds=expires_in)` when `expires_in` was supplied,
  otherwise `None`. Truncating microseconds *before* adding means the stored and reported instants
  are identical, with no rounding gap (R-08).
- `id` and `delete_token` are drawn independently from `secrets` per paste; neither derives from
  `content`, `created_at`, a counter, or any other input (SR-001).

### Lifecycle / state transitions

```text
                   POST /pastes (valid)
                           │
                           ▼
                  ┌─────────────────┐
                  │      LIVE       │  readable, revocable
                  └────────┬────────┘
                           │
          ┌────────────────┴────────────────┐
          │                                 │
   now > expires_at                 DELETE with correct
   (no action taken;                 delete_token
    record may remain                       │
    on disk)                                ▼
          │                        ┌─────────────────┐
          │                        │     REMOVED     │  record unlinked
          │                        └────────┬────────┘
          ▼                                 │
  ┌─────────────────┐                       │
  │     EXPIRED     │───────────────────────┘
  └────────┬────────┘
           │
           ▼
   Indistinguishable from NEVER EXISTED:
   GET /pastes/<id>      → 404
   GET /pastes/<id>/raw  → 404
   DELETE /pastes/<id>   → 404  (regardless of token, FR-021)
```

**Liveness predicate**, evaluated fresh on every request against the current clock (R-08):

```text
live  ⟺  record exists on disk
      ∧  record parses as a valid paste
      ∧  (expires_at is null ∨ now <= expires_at)      ← inclusive
```

Key consequences:
- `EXPIRED` is a *computed* state, not a stored one. No transition is written to disk; an expired
  record is permitted to linger (spec Assumption "Expired records may remain on disk") and simply
  stops passing the predicate. This is what makes FR-018's restart clause automatic.
- A paste is readable up **to and including** its expiry instant (`<=`), and not after
  (Edge Case "Expiry exactly now").
- `REMOVED` is terminal and irreversible — the record file is gone, and because ids are 128-bit
  random the identifier is never reissued (FR-022).
- There is no `EDITED` transition: `content`, `expires_at`, and `delete_token` never change after
  creation.

### Authorization rules

| Operation | Credential required |
|---|---|
| `GET /pastes/<id>` | possession of `id` |
| `GET /pastes/<id>/raw` | possession of `id` |
| `DELETE /pastes/<id>` | possession of `id` **and** `delete_token` |

`delete_token` is verified server-side against the stored record on **every** revocation request,
using `hmac.compare_digest` (SR-002, SR-006). No client-supplied claim other than the token itself
is consulted. The check and the removal happen inside one lock (SR-007, R-09).

**Ordering is load-bearing** (FR-021, Edge Case "Both wrong"): existence and liveness are
evaluated *before* the token is compared, so a revocation against an unknown or expired paste
returns `404` even when the token is wrong or missing — non-existence is reported in preference
to a permission failure, and the `403`/`404` distinction never reveals whether an id exists.

---

## Entity: Paste store

The durable collection of pastes under the operator-chosen data directory. Single source of truth
across restarts (FR-023); keyed by paste identifier.

### Physical layout

```text
<data_dir>/                       mode 0700, created with parents if absent (FR-002, SR-008)
├── <id>.json                     mode 0600, one record per paste
├── <id>.json
└── .<id>.json.<random>.tmp       transient; renamed over the target via os.replace
```

### Record file format

UTF-8 JSON object, written in full by a single atomic replace:

```json
{
  "id": "QnJ3c2VyLVNhZmUtSWQ",
  "content": "hello",
  "created_at": "2026-11-16T09:41:07Z",
  "expires_at": "2026-11-16T10:41:07Z",
  "delete_token": "9rYQ0s3Xz2mKpLv8wTnB4jHcFdEaGuRi7NsOyPqZlMk"
}
```

`expires_at` is JSON `null` for a paste that never expires. The on-disk timestamp strings are the
**same strings** returned on the wire — nothing is re-derived on read, so FR-023's "identical
creation time and expiry time after restart" holds by construction (R-08).

### Operations

| Operation | Implementation | Guarantees |
|---|---|---|
| `create(content, expires_in)` | generate `id`/`token`; `os.open(tmp, O_WRONLY\|O_CREAT\|O_EXCL, 0o600)` in the same directory; write; `fsync`; `os.replace(tmp, final)`. On name collision, regenerate the id and retry (bounded) | mode set at creation with no permissive window (SR-008); readers see all-or-nothing (SR-007); `O_EXCL` enforces id uniqueness (FR-011) |
| `read(id)` | validate id against the allowlist, resolve and containment-check the path, open, parse, check liveness | never reads outside the data directory (SR-003); corrupt/unparsable → treated as absent (FR-024) |
| `delete(id, token)` | under one `threading.Lock`: read → liveness check → `hmac.compare_digest` → `os.unlink` | check and removal atomic w.r.t. concurrent requests (SR-007, R-09) |

### Integrity and containment rules

- **Identifier validation precedes path construction.** The id segment must match
  `[A-Za-z0-9_-]{22}` before it is joined to the data directory; anything else is `404` and never
  reaches the filesystem (SR-003, SR-004).
- **Resolved-path containment.** After joining, `os.path.realpath(candidate)` must lie inside
  `os.path.realpath(data_dir)`; this catches a validly-named record file that is a symlink out of
  the directory. On a legitimate request this check can never fire — it is defence in depth
  (SR-003, R-07).
- **Corrupt records are absent, not fatal.** A record that is unreadable, is not valid UTF-8, is
  not valid JSON, is not a JSON object, or lacks any required field is treated as a paste that
  does not exist. It never prevents startup and never affects any other paste (FR-024).
- **Foreign files are ignored.** The store is only ever read by exact key lookup; it never
  enumerates the directory, so unrelated files are structurally invisible (spec Edge Case
  "Foreign files in the data directory", Assumption "Listing is out of scope").
- **No index, no listing, no enumeration.** There is no operation that lists, searches, or counts
  pastes; the only route to a paste is its identifier.
- **No startup scan.** The directory is created/permission-checked at startup and otherwise not
  traversed — expiry is evaluated per request (R-08), so an expired-while-stopped paste is
  non-existent on the next request without any sweep (FR-018).

### Concurrency model

- One process, one `ThreadingHTTPServer`, one thread per request (R-01).
- **Writes** are atomic via `os.replace`; a reader observes the complete file or no file.
- **Deletes** are a single `os.unlink`; a reader that already opened the file keeps reading it via
  its descriptor, so a read running concurrently with a revocation returns either the complete
  paste or `404` — never truncated or partial text (Edge Case "Concurrent reads during
  revocation").
- **Reads take no lock.** There is no partial-read window to protect, so locking reads would only
  cost throughput (R-09).
- Two simultaneous correct revocations: exactly one `unlink` succeeds; the loser's
  `FileNotFoundError` maps to `404` (Edge Case "Concurrent revocation").

---

## Field-to-requirement traceability

| Field / rule | Requirements |
|---|---|
| `id` generation, uniqueness, URL-safety | FR-011, SR-001 |
| `content` presence, type, empty-string validity | FR-005, FR-006, FR-026 |
| `content` size limit (encoded bytes) | FR-007, FR-027, FR-029, SR-005 |
| `content` exact round-trip | FR-016, SC-001 |
| `expires_in` type and range | FR-008, FR-026 |
| Unknown fields ignored | FR-009 |
| `created_at` / `expires_at` format | FR-015 |
| `expires_at` null for "never" | FR-008, FR-015 |
| `delete_token` generation | SR-001 |
| `delete_token` never returned on read | FR-013, SR-009 |
| `delete_token` constant-time comparison | SR-002, SR-006 |
| Liveness predicate (inclusive bound) | FR-017, FR-018 |
| 404-before-403 ordering | FR-021 |
| Atomic check-and-remove | SR-007 |
| Record/directory permissions | SR-008 |
| Path allowlist + resolved containment | SR-003, SR-004 |
| Corrupt record tolerated as absent | FR-024 |
| Durability across restart | FR-023, SC-005 |
