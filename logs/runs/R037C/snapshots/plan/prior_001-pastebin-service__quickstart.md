# Quickstart & Validation Guide: Pastebin Service

**Feature**: `001-pastebin-service` | **Date**: 2026-11-20

How to run the service and prove it works end to end. Interface details live in
[contracts/http-api.md](./contracts/http-api.md) and [contracts/cli.md](./contracts/cli.md);
field semantics live in [data-model.md](./data-model.md). This file is a run/validation guide,
not an implementation guide.

---

## Prerequisites

- Python **3.11 or newer** (`python3 --version`)
- No installation step and no network access: the runtime uses only the standard library
- `pytest` for the test suite (`python3 -m pip install pytest`) — development only, never
  imported by runtime code
- `curl` for the manual scenarios below (optional)

---

## Run the service

```bash
cd /root/sdd-study/runs/R037
PYTHONPATH=src python3 -m pastebin serve --port 8080 --data /tmp/pastes
```

Expected on **stdout**, once, immediately before requests are accepted:

```text
listening on 127.0.0.1:8080
```

`/tmp/pastes` is created if it does not exist. Diagnostics (including per-request logs) go to
**stderr** only. Stop with `Ctrl-C`.

---

## Run the test suite

```bash
cd /root/sdd-study/runs/R037
python3 -m pytest            # pythonpath=src is set in pyproject.toml
python3 -m pytest -v         # per-test requirement ids in the names
python3 -m pytest -k FR_013  # everything covering one requirement
```

Expected: all tests pass. The suite is the primary acceptance evidence — every requirement
FR-001…FR-032 is named by at least one test, and `tests/README.md` carries the
requirement → test traceability table (SC-002, Constitution III).

---

## Validation scenarios

Each scenario is independently runnable and maps to a user story in
[spec.md](./spec.md). Start the service as above before running them.

### V1 — Share a snippet and read it back (Story 1, SC-001)

```bash
BASE=http://127.0.0.1:8080

# create
curl -s -X POST $BASE/pastes -d '{"content": "hello"}'
# → 201 {"id": "...", "delete_token": "...", "url": "/pastes/<id>"}

ID=$(curl -s -X POST $BASE/pastes -d '{"content": "hello"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

# read as JSON
curl -s $BASE/pastes/$ID
# → 200 {"id": "<id>", "content": "hello", "created_at": "...Z", "expires_at": null}

# read as plain text
curl -si $BASE/pastes/$ID/raw | head -3
# → 200, Content-Type: text/plain; charset=utf-8, body exactly: hello
```

**Pass criteria**: `201` then `200` twice; `content` identical to what was sent; `expires_at` is
`null`; no `delete_token` in either read response; raw body has no added trailing newline.

### V2 — Round-trip fidelity, including the size boundary (Story 1, SC-007)

```bash
# non-ASCII, emoji, newlines, quotes
python3 - <<'EOF'
import json, urllib.request
text = 'héllo 🌍\nline "two"\ttab\x07bell'
req = urllib.request.Request('http://127.0.0.1:8080/pastes',
                             data=json.dumps({'content': text}).encode(),
                             method='POST')
pid = json.load(urllib.request.urlopen(req))['id']
raw = urllib.request.urlopen(f'http://127.0.0.1:8080/pastes/{pid}/raw').read().decode()
assert raw == text, (raw, text)
print('round-trip OK')
EOF

# exactly at the limit → accepted; one byte over → 413
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/pastes \
  -d "$(python3 -c 'import json; print(json.dumps({"content": "a"*65536}))')"   # → 201
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/pastes \
  -d "$(python3 -c 'import json; print(json.dumps({"content": "a"*65537}))')"   # → 413
```

**Pass criteria**: `round-trip OK`; `201` at 65,536 bytes; `413` with a JSON `error` body at
65,537; nothing stored for the rejected request.

### V3 — Revoke a snippet (Story 2)

```bash
OUT=$(curl -s -X POST $BASE/pastes -d '{"content": "secret"}')
ID=$(echo "$OUT"  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
TOK=$(echo "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["delete_token"])')

curl -s -o /dev/null -w 'no token: %{http_code}\n'    -X DELETE $BASE/pastes/$ID            # → 403
curl -s -o /dev/null -w 'wrong token: %{http_code}\n' -X DELETE $BASE/pastes/$ID -H 'X-Delete-Token: nope'  # → 403
curl -s -o /dev/null -w 'still there: %{http_code}\n'            $BASE/pastes/$ID           # → 200
curl -s -o /dev/null -w 'deleted: %{http_code}\n'     -X DELETE $BASE/pastes/$ID -H "X-Delete-Token: $TOK"  # → 204
curl -s -o /dev/null -w 'gone: %{http_code}\n'                   $BASE/pastes/$ID           # → 404
curl -s -o /dev/null -w 'redelete: %{http_code}\n'    -X DELETE $BASE/pastes/$ID -H "X-Delete-Token: $TOK"  # → 404
curl -s -o /dev/null -w 'unknown: %{http_code}\n'     -X DELETE $BASE/pastes/zzzz -H 'X-Delete-Token: x'    # → 404
```

**Pass criteria**: `403, 403, 200, 204, 404, 404, 404` in that order — note that a re-delete and
an unknown id give `404`, never `403` (FR-021).

### V4 — Expiry (Story 3, SC-005)

```bash
ID=$(curl -s -X POST $BASE/pastes -d '{"content": "transient", "expires_in": 1}' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
curl -s -o /dev/null -w 'before: %{http_code}\n' $BASE/pastes/$ID   # → 200
sleep 2
curl -s -o /dev/null -w 'after: %{http_code}\n'  $BASE/pastes/$ID   # → 404

# expiry timestamp arithmetic
curl -s -X POST $BASE/pastes -d '{"content": "x", "expires_in": 3600}' > /dev/null
# then read the paste: expires_at must be exactly created_at + 3600 seconds

# invalid lifetimes → 400
for v in 0 -1 2592001 1.5 '"60"' null true; do
  printf '%-10s ' "$v"
  curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/pastes -d "{\"content\":\"x\",\"expires_in\":$v}"
done
```

**Pass criteria**: `200` before, `404` after; `expires_at` exactly 3,600 s after `created_at`;
`400` for every value in the loop; `1` and `2592000` both accepted.

### V5 — Restart durability (Story 4, SC-004)

```bash
DIR=$(mktemp -d)
PYTHONPATH=src python3 -m pastebin serve --port 8080 --data "$DIR" &
SRV=$!
# create a mix of expiring and non-expiring pastes, recording id/content/token for each
kill $SRV; wait $SRV 2>/dev/null

PYTHONPATH=src python3 -m pastebin serve --port 8080 --data "$DIR" &
# re-read every recorded id
```

**Pass criteria**: after the restart, every non-expired paste returns the same `id`, `content`,
`created_at`, and `expires_at`, and each recorded delete token still works; a paste whose
lifetime elapsed while the service was stopped returns `404`.

### V6 — Startup failures (Story 4, FR-029)

```bash
PYTHONPATH=src python3 -m pastebin serve --port 99999 --data /tmp/p; echo "exit=$?"   # diagnostic on stderr, exit 2
PYTHONPATH=src python3 -m pastebin serve --port abc   --data /tmp/p; echo "exit=$?"   # exit 2
PYTHONPATH=src python3 -m pastebin serve --port 8080;                echo "exit=$?"   # missing --data, exit 2
PYTHONPATH=src python3 -m pastebin serve --port 8080 --data /etc/passwd/sub; echo "exit=$?"  # undeployable dir, exit 2

# port already in use: start one instance, then a second on the same port → exit 2
```

**Pass criteria**: each prints a specific message naming the offending argument or condition on
**stderr**, writes nothing to stdout (no readiness line), and exits `2`.

### V7 — Hostile input does not take the service down (SC-008, SC-009)

```bash
curl -s -o /dev/null -w '%{http_code}\n' $BASE/                              # → 404
curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes                        # → 404
curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/../../../etc/passwd    # → 404
curl -s -o /dev/null -w '%{http_code}\n' $BASE/pastes/%2e%2e%2fetc%2fpasswd  # → 404
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/pastes//raw"                 # → 404
curl -s -o /dev/null -w '%{http_code}\n' -X PUT $BASE/pastes/abc             # → 404
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/pastes -d 'not json'  # → 400
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/pastes -d '[1,2]'     # → 400
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/pastes                # → 400
head -c 2000000 /dev/zero | tr '\0' 'a' > /tmp/big
curl -s -o /dev/null -w '%{http_code}\n' -X POST $BASE/pastes --data-binary @/tmp/big  # → 413

# the service must still work afterwards
curl -s -X POST $BASE/pastes -d '{"content": "still alive"}'                 # → 201
```

**Pass criteria**: the status codes above, every error body of the form `{"error": "..."}`, the
traversal attempts never returning file contents, and the final `201` proving the service is
still serving.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `No module named pastebin` | `PYTHONPATH=src` not set (or run from the wrong directory) |
| readiness line never appears, exit `2` | port in use or `--data` not writable — read stderr |
| first request after startup is refused | the readiness line is being printed before the socket listens (R-002 violated) |
| `expires_at` has `+00:00` instead of `Z` | timestamp rendered with `isoformat()` instead of the required format (FR-010) |
| maximum-size paste returns `413` | payload ceiling set too close to 65,536 bytes (R-003) |
| `403` where `404` is expected | token checked before existence/expiry (FR-021) |
