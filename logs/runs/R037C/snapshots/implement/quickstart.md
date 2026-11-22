# Quickstart & Validation Guide: Burn After Reading and Password Protection

**Feature**: `002-burn-after-reading-password` | **Date**: 2026-11-20

How to prove the two new options work end to end, and the requirement-to-test map Constitution III
requires. Interface details live in [contracts/http-api.md](./contracts/http-api.md); field
semantics and the on-disk record shape live in [data-model.md](./data-model.md); design decisions
live in [research.md](./research.md). This file is a run/validation guide, not an implementation
guide.

Running the service itself is unchanged — see
[001's quickstart](../001-pastebin-service/quickstart.md) for startup, the readiness line, and the
CLI. Scenarios V1…V7 there must all still pass untouched (FR-060, SC-017).

---

## Prerequisites

- Python **3.11 or newer** (`python3 --version`)
- No installation step, no network access: the runtime uses only the standard library
- `pytest` for the suite (`python3 -m pip install pytest`) — development only
- `curl` and `jq` for the manual scenarios below (optional)

---

## Run the service and the suite

```bash
cd /root/sdd-study/runs/R037
PYTHONPATH=src python3 -m pastebin serve --port 8080 --data /tmp/pastes &
# stdout, once: listening on 127.0.0.1:8080

# whole suite — must be green, including every pre-existing test, unmodified (SC-017)
python3 -m pytest

# just this feature
python3 -m pytest tests/test_burn.py tests/test_password.py tests/test_compat.py

# requirement coverage spot-check: every FR id below must appear in a test name
python3 -m pytest --collect-only -q | grep -c fr_0
```

---

## Validation scenarios

Continuing 001's numbering (V1…V7). `$P` is `http://127.0.0.1:8080`.

### V8 — A one-time snippet is readable exactly once (Story 1, SC-011)

```bash
# create, one-time
ID=$(curl -sS -X POST $P/pastes -d '{"content":"recovery-code-8842","burn_after_reading":true}' | jq -r .id)

# first read → 200, content intact, burn_after_reading true, protected false
curl -sS -i $P/pastes/$ID
# second read → 404 {"error": "..."}
curl -sS -i $P/pastes/$ID
# raw read → also 404
curl -sS -i $P/pastes/$ID/raw
```

Repeat with the raw route first: the raw body must be byte-for-byte the content with
`Content-Type: text/plain; charset=utf-8` and no new fields, and the JSON route must then answer
`404`. Expected: exactly one `200` per snippet, every later read `404`.

With `"burn_after_reading": false`, or with the field absent, every read must succeed indefinitely
and the JSON read must report `"burn_after_reading": false`.

### V9 — Exactly one of many simultaneous reads wins (Story 1 §11, SC-012)

```bash
ID=$(curl -sS -X POST $P/pastes -d '{"content":"only-once","burn_after_reading":true}' | jq -r .id)
for i in $(seq 10); do curl -sS -o /dev/null -w "%{http_code}\n" $P/pastes/$ID & done; wait
```

Expected: exactly one `200` and nine `404`. The automated version of this runs 200 snippets × 10
threads and asserts the one-to-nine split for every snippet, and that the single served body is
complete.

### V10 — A password gates both read routes (Story 2, SC-013)

```bash
ID=$(curl -sS -X POST $P/pastes -d '{"content":"secret","password":"hunter2"}' | jq -r .id)

curl -sS -i $P/pastes/$ID                                      # 403 — no header
curl -sS -i -H 'X-Paste-Password;'        $P/pastes/$ID         # 403 — empty header
curl -sS -i -H 'X-Paste-Password: wrong'  $P/pastes/$ID         # 403 — wrong
curl -sS -i -H 'X-Paste-Password: hunter2' -H 'X-Paste-Password: hunter2' $P/pastes/$ID  # 403 — duplicated
curl -sS -i -H 'X-Paste-Password: hunter2' $P/pastes/$ID        # 200, "protected": true
curl -sS -i -H 'X-Paste-Password: hunter2' $P/pastes/$ID/raw    # 200, body exactly: secret
```

Expected: every refusal is `403` with a JSON `error` body, the snippet stays readable afterwards,
and no response anywhere contains `hunter2`. An unprotected snippet must serve `200` even when an
`X-Paste-Password` header is sent.

### V11 — Not-found beats forbidden (Story 2 §7, SC-014)

```bash
curl -sS -i -H 'X-Paste-Password=[REDACTED:assigned_secret] $P/pastes/neverissuedxxxxxxxxx   # 404
curl -sS -i -H 'X-Paste-Password=[REDACTED:assigned_secret] $P/pastes/../../etc/passwd       # 404
# delete a protected paste, then read it with the correct password            → 404
# let a protected paste expire, then read it with the correct password        → 404
```

Expected: `404` in every case, never `403` — an observer cannot tell a protected snippet from one
that does not exist.

### V12 — A refused read costs nothing (edge cases, SC-019)

```bash
ID=$(curl -sS -X POST $P/pastes -d '{"content":"both","burn_after_reading":true,"password":"pw"}' | jq -r .id)
for i in $(seq 20); do curl -sS -o /dev/null -w "%{http_code} " -H 'X-Paste-Password: nope' $P/pastes/$ID; done
curl -sS -H 'X-Paste-Password: pw' $P/pastes/$ID    # 200 with the content
curl -sS -i -H 'X-Paste-Password: pw' $P/pastes/$ID # 404 — now consumed
```

Expected: twenty `403`s, then one `200`, then `404`.

### V13 — Deletion is still token-only (Story 2 §8–9, FR-045)

```bash
R=$(curl -sS -X POST $P/pastes -d '{"content":"x","password":"pw","burn_after_reading":true}')
ID=$(echo $R | jq -r .id); TOK=$(echo $R | jq -r .delete_token)

curl -sS -i -X DELETE -H 'X-Paste-Password: pw' $P/pastes/$ID   # 403 — password is not authorisation
curl -sS -i -X DELETE -H "X-Delete-Token: $TOK" $P/pastes/$ID   # 204 — no password needed
curl -sS -i $P/pastes/$ID                                        # 404
```

Also: read a one-time snippet once, then `DELETE` it with its original token → `404` (FR-048).

### V14 — Invalid new fields are rejected and store nothing (SC-015)

```bash
for BODY in '{"content":"x","burn_after_reading":"true"}' '{"content":"x","burn_after_reading":1}' \
            '{"content":"x","burn_after_reading":null}'   '{"content":"x","burn_after_reading":[]}' \
            '{"content":"x","password":5}'                '{"content":"x","password":""}' \
            "{\"content\":\"x\",\"password\":\"$(python3 -c 'print("a"*129)')\"}" ; do
  curl -sS -o /dev/null -w "%{http_code} " -X POST $P/pastes -d "$BODY"
done   # expect: 400 400 400 400 400 400 400
```

Then the accepted boundaries: a 1-character password, a 128-character password (including
multi-byte characters), and `true`/`false` for the flag → `201`, and the exact password works.
Finally the precedence check (FR-039): a body with oversized `content` **and** an invalid
`burn_after_reading` must still answer `413`, not `400`, and the storage directory must gain no
file from any rejected request.

### V15 — Old snippets keep working after upgrade (Story 3, SC-017)

```bash
# with the service stopped, point it at a directory of records written by the previous version
PYTHONPATH=src python3 -m pastebin serve --port 8080 --data /tmp/legacy-pastes
```

Expected: no skip messages on stderr for those records; every one reads back in both forms with
unchanged `content`, `id`, `created_at`, and `expires_at`; every original delete token still works;
and every one reports `"burn_after_reading": false, "protected": false`. The automated version
writes 50 such records (mixed expiring and non-expiring, including multi-byte content) and asserts
all of that.

### V16 — Both options survive a restart (Story 1 §12, Story 2 §14, SC-018)

```bash
# create one one-time snippet and one protected snippet, then stop the service (Ctrl-C) and
# start it again against the same --data directory
```

Expected after the restart: the one-time snippet is still consumed by exactly one read, and the
protected snippet still requires and accepts exactly the same password.

### V17 — The service stays up under the new bad input (SC-021)

Replay V14's malformed bodies, V10's refused reads, and V8's consumed-snippet reads in bulk, then
run an ordinary create-read round trip. Expected: the round trip succeeds, and stderr shows no
traceback and no `500`.

---

## Requirement traceability (Constitution III)

Every requirement maps to at least one automated test whose name carries the requirement id, as the
existing suite already does (e.g. `test_fr_047_first_read_serves_and_destroys`).

| Requirement | Test module | What the test asserts |
|---|---|---|
| FR-033 | `test_burn.py` | absent `burn_after_reading` behaves as `false`; explicit `false` is identical |
| FR-034 | `test_burn.py` | string / number / `null` / array / object each → `400` naming the field |
| FR-035 | `test_password.py` | 1- and 128-character passwords accepted; the paste reports `protected: true` |
| FR-036 | `test_password.py` | non-string, `""`, and 129 characters each → `400`; length counted in characters, not bytes |
| FR-037 | `test_compat.py` | `201` body is exactly `id`, `delete_token`, `url` for all four option combinations |
| FR-038 | `test_compat.py` | the data directory gains no file from any rejected creation |
| FR-039 | `test_compat.py` | oversized content + invalid new field → `413`; a body with neither new field matches the old outcome byte for byte |
| FR-040 | `test_password.py` | correct header serves `200` on both read routes |
| FR-041 | `test_password.py` | absent / empty / wrong / duplicated / foreign password → `403`, and the paste stays readable |
| FR-042 | `test_password.py` | never-issued, deleted, expired, and ill-shaped ids → `404` with any password |
| FR-043 | `test_password.py` | verification goes through `secrets.compare_digest` over derived values; the stored value is not the password |
| FR-044 | `test_password.py` | unprotected paste serves `200` with a stray `X-Paste-Password` header |
| FR-045 | `test_password.py` | delete with token and no password → `204`; delete with password and no token → `403` |
| FR-046 | `test_password.py` | no response from any route contains the password; the record on disk contains neither it nor anything reversible to it |
| FR-047 | `test_burn.py` | first read on each route serves the ordinary status, headers, and body |
| FR-048 | `test_burn.py` | after one read, both read routes and a delete with the original token → `404` |
| FR-049 | `test_burn.py` | 200 pastes × 10 concurrent reads: exactly one `200` each, bodies complete |
| FR-050 | `test_burn.py` | wrong-password `403` and ill-shaped-id `404` leave the one read available |
| FR-051 | `test_burn.py` | a non-burn paste serves repeatedly on both routes |
| FR-052 | `test_burn.py` | an expired one-time paste → `404`, and is not consumed |
| FR-053 | `test_burn.py` | delete-before-read → `204`; missing/wrong token on an unread burn paste → `403` |
| FR-054 | `test_compat.py` | JSON read body is exactly the six fields, with the four old ones unchanged |
| FR-055 | `test_compat.py` | the two booleans match what was set at creation, across all four combinations |
| FR-056 | `test_compat.py` | raw body is the content and nothing else, with the unchanged content type |
| FR-057 | `test_compat.py` | restart over the same directory preserves both behaviours |
| FR-058 | `test_compat.py` | 50 legacy records read back unchanged and report both flags `false` |
| FR-059 | all three | every new `400`, `403`, and `404` body is exactly `{"error": "<message>"}` and names the cause |
| FR-060 | pre-existing suite | `python3 -m pytest` passes with every 001 test file unmodified |

| Success criterion | Covered by |
|---|---|
| SC-011 | `test_burn.py` read-twice-per-route test (V8) |
| SC-012 | `test_burn.py` concurrency test (V9) |
| SC-013 | `test_password.py` refusal sweep (V10) |
| SC-014 | `test_password.py` 404-beats-403 sweep (V11) |
| SC-015 | `test_compat.py` rejection and boundary tables (V14) |
| SC-016 | the traceability table above, plus a green suite |
| SC-017 | unmodified 001 suite + `test_compat.py` legacy-record test (V15) |
| SC-018 | `test_compat.py` restart tests (V16) |
| SC-019 | `test_burn.py` 20-wrong-then-right test (V12) |
| SC-020 | `test_password.py` whole-suite password search (V10) |
| SC-021 | `test_compat.py` soak test (V17) |

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| A legacy record is reported as "skipping unreadable record" at startup | `RECORD_VERSION` was bumped, or the new keys were made required on read. They must be optional (R-017, FR-058). |
| Both of two concurrent reads of a one-time paste get `200` | The claim is happening after the response is written, or it is not the `unlink` claim. The order is: read into memory → password → claim → serve (R-015). |
| A wrong-password attempt destroys a one-time paste | The claim is running before the password check. `403` must return before step 3 (FR-050). |
| A read of a protected paste answers `403` for a non-existent id | Existence and expiry must be resolved first; `404` always wins (FR-042). |
| Reads of protected pastes feel slow (~40 ms) | Expected: that is the PBKDF2 cost, and it is deliberate (R-016). Unprotected reads must be unaffected. |
| An existing `413` turned into a `400` | New-field validation is running before the existing checks (R-019, FR-039). |
