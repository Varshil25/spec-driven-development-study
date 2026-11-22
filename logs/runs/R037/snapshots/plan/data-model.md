# Phase 1 Data Model: Pastebin Service

**Feature**: `001-pastebin-service` | **Date**: 2026-11-20

Derived from the spec's Key Entities and FR-001…FR-032. Decisions referenced as `R-00n` come
from [research.md](./research.md).

---

## 1. Entity: Paste

One submitted piece of text. No owner, no title, no relationship to any other paste.

### In-memory representation

A frozen `dataclass` (`pastebin.storage.Paste`) — plain data, no behaviour beyond construction
(Constitution IV).

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `str` | yes | Opaque URL-safe identifier, 22 chars from `[A-Za-z0-9_-]` (R-004) |
| `content` | `str` | yes | The snippet text; ≤ 65,536 bytes when UTF-8 encoded |
| `created_at` | `int` | yes | Creation moment, epoch seconds UTC, whole seconds (R-009) |
| `expires_at` | `int \| None` | yes | Expiry moment, epoch seconds UTC; `None` = never expires |
| `delete_token` | `str` | yes | 43-char URL-safe secret, 256 bits (R-004). Write-only field |

### Validation rules

| Rule | Constraint | Violation → | Requirement |
|---|---|---|---|
| V-1 | request body parses as JSON | `400` | FR-004 |
| V-2 | parsed body is a JSON object (`dict`) | `400` | FR-004 |
| V-3 | `content` key present | `400` | FR-004 |
| V-4 | `content` is a `str` (not `int`, `bool`, `None`, `list`, `dict`) | `400` | FR-004 |
| V-5 | `len(content.encode("utf-8")) <= 65536` (inclusive) | `413` | FR-005 |
| V-6 | `expires_in`, if present, is an `int` and not a `bool` | `400` | FR-006 |
| V-7 | `expires_in`, if present, satisfies `1 <= expires_in <= 2_592_000` | `400` | FR-006 |
| V-8 | keys other than `content` / `expires_in` are ignored, not rejected | — | FR-007 |
| V-9 | request `Content-Length` ≤ 1,048,576 (checked before reading) | `413` | FR-024 |
| V-10 | path-supplied id matches `^[A-Za-z0-9_-]{1,64}$` before any I/O | `404` | FR-023 |

Notes:
- V-4 accepts `""` — an empty string is a valid, storable paste (spec edge case); the raw route
  then returns an empty body.
- V-5 is measured on the UTF-8 encoding, not on character count (spec edge case).
- V-6 rejects `3600.0` as well as `"3600"`, `true`, and `null`: JSON `null` for `expires_in`
  means "present and invalid", not "absent".
- V-9 fires before parsing, which is why a body that is both oversized and unparsable yields
  `413` rather than `400` (spec edge case).
- V-10 is an allow-list, not a sanitisation: a non-matching id is refused, never rewritten
  (R-007).
- When any rule fails, nothing is written to the storage directory (FR-008).

### Derived values

| Value | Derivation | Requirement |
|---|---|---|
| `expires_at` | `created_at + expires_in` when `expires_in` given, else `None` | FR-017 |
| `url` (creation response only) | `"/pastes/" + id` | FR-001 |
| `created_at` / `expires_at` on the wire | `strftime("%Y-%m-%dT%H:%M:%SZ")` in UTC; `expires_at` is JSON `null` when there is no expiry | FR-010 |

### Lifecycle

```text
                    ┌──────────────── DELETE with matching token (204) ───────┐
                    │                                                         ▼
(none) ──POST /pastes (201)──▶ READABLE ──now >= expires_at (no action)──▶ GONE
                                 │  ▲                                        ▲
                                 │  └── GET / GET raw (200) ──┘              │
                                 └── DELETE without / wrong token (403) ─────┘
                                     (stays READABLE)
```

| Transition | Trigger | Observable result | Requirement |
|---|---|---|---|
| → READABLE | `POST /pastes` passes V-1…V-9 | `201` + `id`, `delete_token`, `url` | FR-001 |
| READABLE → READABLE | `GET /pastes/<id>` | `200` + JSON record | FR-009 |
| READABLE → READABLE | `GET /pastes/<id>/raw` | `200` + content as `text/plain; charset=utf-8` | FR-011 |
| READABLE → READABLE | `DELETE` with absent/empty/wrong token | `403`, paste still readable | FR-014 |
| READABLE → GONE | `DELETE` with matching token | `204`, no body | FR-013 |
| READABLE → GONE | wall clock reaches `expires_at` | no response; next access `404` | FR-018 |
| GONE → GONE | any read or delete | `404`, regardless of token | FR-016, FR-021 |

**GONE is terminal and indistinguishable from never-existed.** Deleted, expired, and
never-issued identifiers all answer `404`, so no response discloses which identifiers exist
(FR-021). Expiry is evaluated at access time — there is no background sweeper (spec
assumption); an expired record encountered on disk may be removed lazily.

**Boundary**: a paste is readable strictly before `expires_at` and gone at or after it —
`now >= expires_at` means gone (R-009, spec edge case).

---

## 2. Entity: Storage directory

The operator-chosen path passed as `--data DIR`. It is the unit of persistence: the same
directory given to a later run yields the same set of pastes (FR-028).

### Layout

```text
<DIR>/
├── <id>.json        # one record per paste (R-006)
├── <id>.json
└── .tmp-<random>    # transient; exists only mid-write, renamed away atomically
```

### Record format (internal — NOT part of the external contract)

```json
{
  "version": 1,
  "id": "A1b2C3d4E5f6G7h8I9j0K_",
  "content": "hello",
  "created_at": 1763596800,
  "expires_at": null,
  "delete_token": "xZ...43 chars..."
}
```

| Field | Type | Notes |
|---|---|---|
| `version` | `int` | Format marker. A record whose `version` is unrecognised is skipped and reported (FR-032) |
| `id` | `str` | Must equal the filename stem; a mismatch makes the record unreadable → skipped |
| `content` | `str` | Verbatim submitted text (FR-012) |
| `created_at` | `int` | Epoch seconds UTC |
| `expires_at` | `int \| null` | Epoch seconds UTC, or `null` |
| `delete_token` | `str` | Never serialised into any response (FR-003) |

The file format, filenames, and the `version` field are implementation details the spec
explicitly leaves open; only the HTTP surface in [contracts/http-api.md](./contracts/http-api.md)
is contractual.

### Invariants

| Invariant | How it is enforced | Requirement |
|---|---|---|
| S-1 | No path outside `DIR` is ever opened: ids are allow-listed (V-10) and paths are composed as `join(DIR, id + ".json")` | FR-023 |
| S-2 | A partially written record is never readable: write temp file → `fsync` → `os.replace` | FR-028 |
| S-3 | An id is never reused: the final name is reserved with `os.open(O_CREAT \| O_EXCL)`; on collision a new id is drawn | FR-002, Story 4 §7 |
| S-4 | A read racing a delete sees the whole record or nothing (`FileNotFoundError` → `404`) | FR-031 |
| S-5 | Expiry survives restarts and downtime: `expires_at` is an absolute stored timestamp | FR-019 |
| S-6 | An unreadable or unrecognised entry never blocks startup or other reads; it is reported on stderr and skipped | FR-032 |
| S-7 | `DIR` is created with missing parents when absent, and used as-is when it already holds records | FR-026 |
| S-8 | No index, cache, or hidden state file: the directory contents are the whole truth | Constitution (no hidden state) |

### Failure modes at startup

| Condition | Behaviour | Requirement |
|---|---|---|
| `DIR` absent | created, including parents | FR-026 |
| `DIR` cannot be created or written | specific stderr diagnostic, exit `2`, no readiness line | FR-029 |
| `DIR` contains a stray/corrupt/future-version entry | reported on stderr, startup continues | FR-032 |

---

## 3. Entity: Deletion token

The single credential in the system. Authorises deletion of exactly one paste.

| Property | Value | Requirement |
|---|---|---|
| Entropy | 256 bits (`secrets.token_urlsafe(32)`) | FR-003 |
| Relationship to `id` | independent draw; neither yields the other | FR-003 |
| Exposure | returned **only** in the `201` creation body | FR-003 |
| Transport | `X-Delete-Token` request header on `DELETE` | FR-013 |
| Comparison | `secrets.compare_digest`, after the existence/expiry check | FR-015, FR-021 |
| Scope | one paste; another paste's token never authorises this one | Story 2 §6 |
| Recovery | none — a lost token means the paste can only expire | spec assumption |

Absent, empty, and non-matching tokens are all `403` **for an existing unexpired paste**, and
all `404` when the paste is unknown, deleted, or expired (FR-021).

---

## 4. Non-entities (explicitly out of scope)

Recorded so the implementation does not invent them: no user/account, no paste listing or
index, no title or metadata beyond the fields above, no edit/update route, no quotas or rate
limits, no deduplication of identical content, no content-type negotiation, no compression.
