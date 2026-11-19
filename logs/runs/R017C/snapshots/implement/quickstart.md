# Quickstart: Burn-After-Reading and Password-Protected Pastes

**Feature**: `002-burn-and-password-pastes` | **Date**: 2026-11-16 | **Plan**: [plan.md](./plan.md)

Runnable scenarios that prove this feature works end to end. Field shapes are in
[data-model.md](./data-model.md); the wire contract is in
[contracts/http-api.md](./contracts/http-api.md); the pre-existing behaviour these scenarios must
not disturb is in [001/quickstart.md](../001-pastebin-service/quickstart.md).

---

## Prerequisites

- Python 3.11 or newer (`python3 --version`)
- `pytest` for the automated suite (`python3 -m pip install pytest`) — the **only** dependency,
  and a development-only one (Constitution Principle I)
- `curl` and `jq` for the manual scenarios
- No network access and no service account: everything binds `127.0.0.1` only

## Setup

```bash
cd <repo root>
export PYTHONPATH=src
DATA=$(mktemp -d)
python3 -m pastebin serve --port 8080 --data "$DATA" &
# prints exactly: listening on 127.0.0.1:8080
BASE=http://127.0.0.1:8080
```

Tear down with `kill %1 && rm -rf "$DATA"` when finished.

---

## Scenario 1 — Burn after reading (User Story 1, FR-030, FR-044, FR-045)

```bash
ID=$(curl -s -X POST $BASE/pastes \
      -d '{"content":"recovery code 4821","burn_after_reading":true}' | jq -r .id)

curl -s -i $BASE/pastes/$ID      # first read
curl -s -i $BASE/pastes/$ID      # second read
curl -s -i $BASE/pastes/$ID/raw  # and the other form
```

**Expected**: the first read is `200` with `"content": "recovery code 4821"`,
`"burn_after_reading": true`, `"protected": false`, and the usual `id` / `created_at` /
`expires_at`. The second read and the raw read are both `404` with `{"error":"not found"}`.

Repeat with the raw form first (`/raw` before the structured read) — the raw body must be
byte-for-byte the content with no trailing newline, and every later request in either form must be
`404` (FR-044).

**Control**: a paste created without the field reads any number of times and reports
`"burn_after_reading": false` (FR-030, FR-053).

## Scenario 2 — A refused request never consumes (FR-046, SC-014)

```bash
ID=$(curl -s -X POST $BASE/pastes -d '{"content":"still here","burn_after_reading":true}' | jq -r .id)

curl -s -o /dev/null -w '%{http_code}\n' -X DELETE $BASE/pastes/$ID -H 'X-Delete-Token: wrong'
curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/$ID/other
curl -s -o /dev/null -w '%{http_code}\n' -X PUT $BASE/pastes/$ID
curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/$ID/      # trailing slash

curl -s $BASE/pastes/$ID | jq -r .content                       # must still work, once
```

**Expected**: `403`, `404`, `404`, `404`, then `still here`. The failed revocation and the three
unrouted requests left the paste intact; only the last line consumed it.

## Scenario 3 — Password protection (User Story 2, FR-032, FR-040, FR-041)

```bash
ID=$(curl -s -X POST $BASE/pastes -d '{"content":"shared secret","password":"hunter2"}' | jq -r .id)

curl -s -i $BASE/pastes/$ID                                  # no header
curl -s -i $BASE/pastes/$ID -H 'X-Paste-Password: Hunter2'   # wrong case
curl -s -i $BASE/pastes/$ID -H 'X-Paste-Password: hunter2 '  # trailing space
curl -s -i $BASE/pastes/$ID -H 'X-Paste-Password: hunter2'   # correct
curl -s    $BASE/pastes/$ID/raw -H 'X-Paste-Password: hunter2'
```

**Expected**: the first three are `403` with `{"error":"invalid paste password"}` and disclose no
part of the content; the fourth is `200` with `"protected": true` and
`"burn_after_reading": false`; the fifth is the exact content as plain text. The paste is still
readable after each refusal (FR-041, SC-012).

**Non-ASCII** (FR-034): create with `{"content":"x","password":"pässwörd🔑"}` and read with
`-H 'X-Paste-Password: pässwörd🔑'` → `200`. `curl` sends the header bytes as UTF-8, which is what
the service decodes.

**Revocation needs only the token** (FR-050): `curl -X DELETE $BASE/pastes/$ID -H
"X-Delete-Token: $TOKEN"` with no password header → `204`, then every read is `404`.

**Unprotected paste, password header sent anyway** (FR-042): `200`, `"protected": false`, header
ignored.

## Scenario 4 — The two combined, and non-existence stays private (User Story 3)

```bash
ID=$(curl -s -X POST $BASE/pastes \
      -d '{"content":"one shot","burn_after_reading":true,"password":"pw"}' | jq -r .id)

curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/$ID                          # 403
curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/$ID -H 'X-Paste-Password: x' # 403
curl -s $BASE/pastes/$ID -H 'X-Paste-Password: pw' | jq '{burn_after_reading,protected}'
curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/$ID -H 'X-Paste-Password: pw' # 404

curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/AAAAAAAAAAAAAAAAAAAAAA -H 'X-Paste-Password: pw'
```

**Expected**: `403`, `403` (the wrong-password reads did **not** consume it), then a `200`
reporting both flags `true`, then `404` even with the correct password. The invented identifier is
`404`, never `403` — a refusal never confirms that an identifier is real (FR-043, SC-016).

## Scenario 5 — Validation (FR-031, FR-033, FR-036)

```bash
for v in '"true"' 0 1 null '[]' '{}'; do
  curl -s -o /dev/null -w "burn=$v %{http_code}\n" -X POST $BASE/pastes \
    -d "{\"content\":\"x\",\"burn_after_reading\":$v}"
done
for v in '""' null 5 true '[]' '{}'; do
  curl -s -o /dev/null -w "pw=$v %{http_code}\n" -X POST $BASE/pastes \
    -d "{\"content\":\"x\",\"password\":$v}"
done
python3 - <<'PY'
import json, urllib.request
for n, expect in ((128, 201), (129, 400)):
    body = json.dumps({"content": "x", "password": "a" * n}).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/pastes", body)
    try:
        print(n, urllib.request.urlopen(req).status, "expected", expect)
    except urllib.error.HTTPError as e:
        print(n, e.code, "expected", expect)
    # and 128 multi-byte characters must also be accepted (FR-033)
PY
```

**Expected**: every listed `burn_after_reading` and `password` value is `400` and creates nothing;
128 characters is `201`; 129 is `400`; 128 **multi-byte** characters is `201` (the bound is
characters, not encoded bytes).

**Precedence** (FR-036): a submission with `"burn_after_reading": "yes"` **and** 66 000 bytes of
content is `400`, not `413`. The same submission with valid new fields is `413`.

The size must sit between the two caps — over the 65 536-byte **content** limit but under the
66 560-byte **declared `Content-Length`** limit — or the framing guard answers first. A body
carrying 70 000 bytes of content declares ~70 030 bytes, so it is refused `413` **unread** by the
framing rule (contracts/http-api.md, third precedence row) before any field is validated. That is
the pre-existing FR-029 behaviour and is unchanged by this feature; FR-036 governs only
submissions whose body is actually read.

## Scenario 6 — Concurrency (FR-047, SR-016, SC-015)

```bash
ID=$(curl -s -X POST $BASE/pastes -d '{"content":"exactly once","burn_after_reading":true}' | jq -r .id)
seq 20 | xargs -P 20 -I{} curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/$ID | sort | uniq -c
```

**Expected**: exactly `1` × `200` and `19` × `404`. No `403`, no `500`, and no truncated body.

## Scenario 7 — Restart and legacy records (User Story 4, FR-048, FR-051, FR-052)

```bash
# a record written before this feature existed: the five original keys only
python3 - <<PY
import json, os, time
d = os.environ["DATA"]
pid = "LegacyPasteIdAAAAAAAAA"  # 22 chars from [A-Za-z0-9_-]
rec = {"id": pid, "content": "from the old build", "created_at": "2026-01-01T00:00:00Z",
       "expires_at": None, "delete_token": "legacy-token"}
fd = os.open(os.path.join(d, pid + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
os.write(fd, json.dumps(rec).encode()); os.close(fd)
PY

BURN=$(curl -s -X POST $BASE/pastes -d '{"content":"survives","burn_after_reading":true}' | jq -r .id)
PROT=$(curl -s -X POST $BASE/pastes -d '{"content":"guarded","password":"pw"}' | jq -r .id)
GONE=$(curl -s -X POST $BASE/pastes -d '{"content":"consumed","burn_after_reading":true}' | jq -r .id)
curl -s -o /dev/null $BASE/pastes/$GONE   # consume it

kill %1; sleep 1
python3 -m pastebin serve --port 8080 --data "$DATA" &

curl -s $BASE/pastes/LegacyPasteIdAAAAAAAAA | jq '{content,created_at,burn_after_reading,protected}'
curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/$PROT                            # 403
curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/$PROT -H 'X-Paste-Password: pw'  # 200
curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/$BURN                            # 200, once
curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/$BURN                            # 404
curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/$GONE                            # 404
```

**Expected**: the legacy record reads back with identical content and `created_at`, needs no
password, and reports both flags `false` (FR-051, SC-019). The one-time paste is still one-time,
the protected paste still requires the same password, and the consumed paste is still gone
(FR-048, FR-052, SC-018).

## Scenario 8 — Nothing leaks (SR-013, SR-019, SC-017)

```bash
grep -ril 'hunter2' "$DATA"            # must print nothing — plaintext is never stored
cat "$DATA"/*.json | jq '.password'    # algorithm/iterations/salt/hash only, no plaintext
curl -s -D- $BASE/pastes/$ID -H 'X-Paste-Password: wrong' | grep -i 'hunter2\|salt\|pbkdf2\|hash'
```

**Expected**: no match anywhere. The stored verifier is a salted PBKDF2 hash; no response body,
header, or process output contains the password, the hash, the salt, or the hashing parameters.
Two pastes created with the **same** password have different stored `salt` and `hash` values.

---

## Automated suite

```bash
cd <repo root>
python3 -m pytest -q          # the whole suite: 001 + 002, zero failures, skips, or xfails
python3 -m pytest -q tests/test_burn.py tests/test_password.py tests/test_compat.py
python3 -m pytest -q tests/test_requirement_coverage.py   # the SC-021 gate
```

**Expected**: everything passes. `test_requirement_coverage.py` fails loudly and names the ids if
any requirement in `FR-001 … FR-054` or `SR-001 … SR-020` is referenced by no test, and if any
test references an id that is not a requirement.

The suite spends roughly ten seconds inside PBKDF2 — ~0.2 s per protected read, at the shipped
600 000 iterations. The iteration count is **not** lowered for tests: the configuration under
test is the configuration that ships (R-16, R-26).

---

## Acceptance gate for this feature

| Check | Where |
|---|---|
| All 8 scenarios above behave as stated | manual |
| `pytest` passes with zero failures, skips, and xfails | Constitution, Development Workflow |
| Every `FR-030 … FR-054` and `SR-013 … SR-020` referenced by a test id | `test_requirement_coverage.py` (SC-021) |
| The 001 suite passes with only the three key-set assertions updated for the two new flags | `git diff` on `tests/` (SC-020) |
| No third-party runtime import added | `pyproject.toml` has no runtime dependency (Principle I) |
