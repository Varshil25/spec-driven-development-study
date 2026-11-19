# Quickstart & Validation Guide: Burn After Reading and Password Protection

**Feature**: `002-burn-after-reading-password` | **Plan**: [plan.md](./plan.md)

How to prove the two new options work end to end, and that everything feature 001 did still does.
Interface details live in [contracts/http-api.md](./contracts/http-api.md) and
[contracts/storage.md](./contracts/storage.md); field semantics and the requirement→test map in
[data-model.md](./data-model.md). Running the service itself is unchanged — see
[../001-pastebin-service/quickstart.md](../001-pastebin-service/quickstart.md).

## Prerequisites

- Python 3.11 or newer (`python3 --version`)
- `curl` for the manual scenarios
- `pytest` for the automated suite: `python3 -m pip install -r requirements-dev.txt`

Unchanged from feature 001: no runtime dependencies, nothing to build, nothing to install for the
service itself.

## Run it

```bash
PYTHONPATH=src python3 -m pastebin serve --port 8765 --data ./pastes
```

Expected: the same single line `listening on 127.0.0.1:8765`, and nothing further however much
traffic follows. Startup now also measures the host's password-derivation rate once — a few tens of
milliseconds, invisible against the two-second readiness budget, and printed nowhere.

```bash
export B=127.0.0.1:8765
```

## Automated suite

```bash
python3 -m pytest                 # whole suite: feature 001's modules and this feature's
python3 -m pytest -k fr050        # one requirement
python3 -m pytest tests/test_burn.py tests/test_password.py tests/test_flags.py tests/test_compatibility.py
```

Expected: everything passes, **including feature 001's test modules unmodified** — that is SC-018
and FR-068, and the unchanged files are themselves the evidence. Every requirement FR-045…FR-074 is
named by at least one test; see the
[requirement to test map](./data-model.md#requirement-to-test-map).

The password tests are the slowest in the suite by design: each protected read pays the ~50 ms
derivation FR-073 requires.

---

## Scenario 1 — a snippet that disappears once it has been read (User Story 1)

```bash
ID=$(curl -s -X POST $B/pastes -d '{"content": "one-time secret", "burn_after_reading": true}' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -s $B/pastes/$ID            # first read
curl -s -o /dev/null -w '%{http_code}\n' $B/pastes/$ID        # second read
curl -s -o /dev/null -w '%{http_code}\n' $B/pastes/$ID/raw    # and the other endpoint
```

Expected: the first read returns the full JSON with `"content": "one-time secret"`,
`"burn_after_reading": true`, `"protected": false`, and the usual timestamps. Both later reads print
`404`. `ls ./pastes/$ID.json` reports no such file — the record is gone, not flagged.

Repeat with `$B/pastes/$ID/raw` as the *first* read: the body is exactly `one-time secret` with no
added newline, and the structured endpoint then returns `404` (FR-048).

## Scenario 2 — the one-time property survives a restart

```bash
ID=$(curl -s -X POST $B/pastes -d '{"content": "survives", "burn_after_reading": true}' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
# Ctrl-C the service, then start it again on the same --data directory
curl -s $B/pastes/$ID                                          # returns it, once
curl -s -o /dev/null -w '%{http_code}\n' $B/pastes/$ID         # 404
```

Expected: an unread one-time snippet is still one-time after a restart, and a consumed one stays
gone across a further restart (FR-047, FR-051).

## Scenario 3 — exactly one of many overlapping readers is served (SC-012)

```bash
ID=$(curl -s -X POST $B/pastes -d '{"content": "only once", "burn_after_reading": true}' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

for i in $(seq 1 16); do curl -s -o /dev/null -w '%{http_code}\n' $B/pastes/$ID & done | sort | uniq -c
```

Expected: exactly one `200` and fifteen `404`s. Never two `200`s, and never a truncated body
(FR-050). The automated version of this, released from a `threading.Barrier` over many trials, is
`test_fr050_concurrent_reads_serve_exactly_one`.

## Scenario 4 — a snippet only the password holder can read (User Story 2)

```bash
ID=$(curl -s -X POST $B/pastes -d '{"content": "confidential", "password": "correct horse"}' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -s -o /dev/null -w '%{http_code}\n' $B/pastes/$ID                                   # no header
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Paste-Password: wrong' $B/pastes/$ID       # wrong
curl -s -H 'X-Paste-Password: correct horse' $B/pastes/$ID                               # right
curl -s -H 'X-Paste-Password: correct horse' $B/pastes/$ID/raw                            # and raw
```

Expected: `403` with `{"error": "missing or invalid X-Paste-Password"}` for the first two; the full
snippet for the third, reporting `"protected": true`; the bare text for the fourth. Crucially, the
two refusals leave the snippet readable — the third command still works after them (FR-059, SC-013).

Combine the options and confirm a refusal does not burn:

```bash
ID=$(curl -s -X POST $B/pastes -d '{"content": "both", "burn_after_reading": true, "password": "pw"}' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Paste-Password: nope' $B/pastes/$ID   # 403
curl -s -H 'X-Paste-Password: pw' $B/pastes/$ID                                      # still there
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Paste-Password: pw' $B/pastes/$ID     # now 404
```

## Scenario 5 — the password is never disclosed, and never stored (SC-015, FR-056)

```bash
ID=$(curl -s -X POST $B/pastes -d '{"content": "x", "password": "Tr0ub4dor&3-UNIQUE"}' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -s -D - -H 'X-Paste-Password=[REDACTED:assigned_secret]&3-UNIQUE' $B/pastes/$ID | grep -c UNIQUE   # 0
grep -rc 'UNIQUE' ./pastes/ || echo "absent from storage"
python3 -m json.tool ./pastes/$ID.json
```

Expected: `0` matches in the response (headers and body), no match anywhere in the storage directory,
and a record whose `password` holds only `iterations`, `salt`, and `hash`. Nothing appears on the
service's standard output or standard error either.

Two snippets with the **same** password must have different stored forms (FR-073, SC-021):

```bash
for i in 1 2; do curl -s -X POST $B/pastes -d '{"content": "a", "password": "same"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])'; done \
  | while read id; do python3 -c "import json;r=json.load(open('./pastes/$id.json'));print(r['password']['salt'], r['password']['hash'][:16])"; done
```

Expected: two different salts and two different hashes.

## Scenario 6 — the password costs 10–200 ms to verify (FR-073, SC-021)

```bash
ID=$(curl -s -X POST $B/pastes -d '{"content": "timed", "password": "pw"}' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
PLAIN=$(curl -s -X POST $B/pastes -d '{"content": "timed"}' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -s -o /dev/null -w 'protected   %{time_total}s\n' -H 'X-Paste-Password: pw' $B/pastes/$ID
curl -s -o /dev/null -w 'unprotected %{time_total}s\n' $B/pastes/$PLAIN
```

Expected: the protected read takes between 10 ms and 200 ms longer than the unprotected one — the
derivation cost, calibrated to the host at startup ([research.md](./research.md) R-02). An
unprotected read is as fast as it was before this feature.

And it must not block anything else (FR-074):

```bash
( for i in $(seq 1 4); do curl -s -o /dev/null -H 'X-Paste-Password: pw' $B/pastes/$ID & done
  time curl -s -o /dev/null $B/pastes/$PLAIN; wait )
```

Expected: the unprotected read completes in single-digit milliseconds, without waiting for the four
protected reads.

## Scenario 7 — a non-ASCII password, and bytes that are not UTF-8 (FR-058)

```bash
ID=$(curl -s -X POST $B/pastes -d "$(python3 -c 'import json; print(json.dumps({"content":"ünicode","password":"pässwörd-é中"}))')" \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -s -H "$(printf 'X-Paste-Password: p\xc3\xa4ssw\xc3\xb6rd-\xc3\xa9\xe4\xb8\xad')" $B/pastes/$ID
curl -s -o /dev/null -w '%{http_code}\n' -H "$(printf 'X-Paste-Password: \xff\xfe')" $B/pastes/$ID
```

Expected: the UTF-8 encoded password reads the snippet; the invalid bytes give `403`, **not** `500`
(FR-070).

## Scenario 8 — deletion still needs only the delete token (FR-063, SC-016)

```bash
OUT=$(curl -s -X POST $B/pastes -d '{"content": "withdraw me", "password": "readpw"}')
ID=$(echo "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
TOK=$(echo "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["delete_token"])')

curl -s -o /dev/null -w '%{http_code}\n' -X DELETE -H "X-Paste-Password: readpw" $B/pastes/$ID  # 403
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE -H "X-Delete-Token: $TOK" $B/pastes/$ID      # 204
```

Expected: the reading password does not authorise withdrawal (`403`), and the delete token alone
does, with no password presented (`204`).

## Scenario 9 — the two report flags, all four combinations (User Story 3, SC-019)

```bash
for body in '{"content":"a"}' \
            '{"content":"a","burn_after_reading":true}' \
            '{"content":"a","password":"pw"}' \
            '{"content":"a","burn_after_reading":true,"password":"pw"}'; do
  ID=$(curl -s -X POST $B/pastes -d "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
  curl -s -H 'X-Paste-Password: pw' $B/pastes/$ID \
    | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r["burn_after_reading"], r["protected"])'
done
```

Expected: `False False`, `True False`, `False True`, `True True` — both flags always present, always
booleans, never `null`. The password header on the two unprotected snippets is ignored (FR-062).

## Scenario 10 — invalid values are rejected and create nothing (SC-017)

```bash
for body in '{"content":"a","burn_after_reading":"true"}' '{"content":"a","burn_after_reading":1}' \
            '{"content":"a","burn_after_reading":null}'  '{"content":"a","password":""}' \
            '{"content":"a","password":null}'            '{"content":"a","password":123}' \
            "{\"content\":\"a\",\"password\":\"$(python3 -c 'print("x"*129)')\"}"; do
  curl -s -o /dev/null -w "%{http_code}  $body\n" -X POST $B/pastes -d "$body"
done
ls ./pastes | wc -l   # unchanged by the loop
```

Expected: `400` on every line, each with an explanatory `{"error": ...}` body, and no new record in
the storage directory. Note `null` is a `400` for both options, unlike `expires_in`, where it means
"no expiry".

## Scenario 11 — compatibility (FR-067, FR-068, FR-071)

A record written by the previous version — five keys, neither new one — must still read:

```bash
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("./pastes/LegacyRecordExample.json")
p.write_text(json.dumps({"id": "LegacyRecordExample", "content": "written before 002",
                         "created_at": "2026-10-23T20:15:00Z", "expires_at": None,
                         "delete_token": "legacy-token"}))
PY
curl -s $B/pastes/LegacyRecordExample
```

Expected: `200` with `"burn_after_reading": false, "protected": false` — not a `500`, and no
damaged-storage diagnostic on standard error.

The largest valid submission must now be accepted (FR-071):

```bash
python3 -c 'import json; print(json.dumps({"content": "\u0001"*65536, "password": "p"*128, "burn_after_reading": True}))' \
  > /tmp/max.json
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/pastes --data-binary @/tmp/max.json   # 201
python3 -c 'import json; print(json.dumps({"content": "a"*65537}))' > /tmp/over.json
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/pastes --data-binary @/tmp/over.json  # 413
```

Expected: `201` for the maximum valid submission that the old ceiling would have refused as too
large, and `413` still for content over 65,536 bytes.

## What "done" looks like

- `python3 -m pytest` passes, with feature 001's test modules **unmodified** (FR-068, SC-018).
- Every requirement FR-045…FR-074 is named by a passing test
  ([map](./data-model.md#requirement-to-test-map)) (SC-020).
- Scenarios 1–11 above behave as stated against a freshly started service.
- `grep -rn 'import ' src/pastebin/` names only standard-library modules (Principle I).
- The service still prints exactly one line to standard output and nothing per request (FR-068).
