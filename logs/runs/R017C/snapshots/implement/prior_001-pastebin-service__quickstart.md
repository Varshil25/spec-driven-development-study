# Quickstart & Validation Guide: Pastebin Service

**Feature**: `001-pastebin-service` | **Date**: 2026-11-16 | **Plan**: [plan.md](./plan.md)

Runnable scenarios that prove the feature works end to end. Interface details live in
[contracts/http-api.md](./contracts/http-api.md) and [contracts/cli.md](./contracts/cli.md);
entity and storage details in [data-model.md](./data-model.md). This guide does not restate them.

---

## Prerequisites

- Python **3.11 or newer** (`python3 --version`). No runtime dependencies — standard library only.
- `pytest` for the automated suite (test-only dependency).
- A POSIX host (the storage layer relies on `os.replace` atomicity and POSIX permission bits).
- `curl` for the manual walkthrough (not required by the test suite).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pytest
```

---

## Start the service

```bash
PYTHONPATH=src python -m pastebin serve --port 8080 --data ./pastes-data
```

**Expected**: the directory `./pastes-data` is created if absent, and stdout carries exactly one
line:

```text
listening on 127.0.0.1:8080
```

Leave this running in one terminal; run the scenarios below in another. Use `--port 0` to let the
kernel pick a free port — the line reports the port actually bound.

---

## Scenario 1 — Share a snippet (User Story 1, P1)

Covers FR-005, FR-010, FR-012, FR-013, FR-014, FR-016.

```bash
# Create
curl -s -X POST http://127.0.0.1:8080/pastes \
  -H 'Content-Type: application/json' \
  -d '{"content": "hello"}'
```

**Expected** `201` with `{"id": "...", "delete_token": "...", "url": "/pastes/<id>"}` — a
22-character id and a 43-character token.

```bash
ID=<paste the id>

# Read as structured data
curl -s http://127.0.0.1:8080/pastes/$ID

# Read as plain text
curl -s http://127.0.0.1:8080/pastes/$ID/raw
```

**Expected**: the first returns `200` with `id`, `content`, `created_at`, and `expires_at`
(`null` here) — and **no `delete_token`**. The second returns `200`, the body is exactly `hello`
with no trailing newline, and `Content-Type: text/plain; charset=utf-8`.

**Unicode round-trip** (FR-016):

```bash
curl -s -X POST http://127.0.0.1:8080/pastes \
  -d '{"content": "héllo 🌍\n\"quoted\"\ttabbed"}'
curl -s http://127.0.0.1:8080/pastes/<id>/raw | xxd | head
```

**Expected**: the raw bytes are byte-identical to the submitted text — emoji, newline, quotes, and
tab all preserved.

**Unknown id** (FR-028): `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/pastes/AAAAAAAAAAAAAAAAAAAAAA` → `404`.

---

## Scenario 2 — Expiry (User Story 2, P2)

Covers FR-008, FR-015, FR-017, FR-018.

```bash
# One-second lifetime
curl -s -X POST http://127.0.0.1:8080/pastes -d '{"content": "temporary", "expires_in": 1}'
ID=<id>

curl -s -o /dev/null -w 'before: %{http_code}\n' http://127.0.0.1:8080/pastes/$ID
sleep 2
curl -s -o /dev/null -w 'after:  %{http_code}\n' http://127.0.0.1:8080/pastes/$ID
```

**Expected**: `before: 200`, `after: 404`. After expiry, `/raw` and `DELETE` also return `404`.

**Rejected lifetimes** (FR-008) — each must return `400` and create nothing:

```bash
for v in 0 -1 2592001 3600.0 true '"3600"'; do
  curl -s -o /dev/null -w "$v -> %{http_code}\n" -X POST \
    http://127.0.0.1:8080/pastes -d "{\"content\": \"x\", \"expires_in\": $v}"
done
```

**Expected**: `400` for every one. Note `true` in particular — a boolean must not be accepted as
a 1-second lifetime.

**Accepted boundaries**: `expires_in: 1` and `expires_in: 2592000` both return `201`, and
`expires_at` reads back as exactly that many seconds after `created_at`.

---

## Scenario 3 — Revocation (User Story 3, P3)

Covers FR-019, FR-020, FR-021, FR-022, SR-002, SR-006.

```bash
curl -s -X POST http://127.0.0.1:8080/pastes -d '{"content": "secret"}'
ID=<id>; TOKEN=<delete_token>

# Wrong token → 403, paste survives
curl -s -o /dev/null -w 'wrong token: %{http_code}\n' -X DELETE \
  -H "X-Delete-Token: wrong" http://127.0.0.1:8080/pastes/$ID
curl -s -o /dev/null -w 'still readable: %{http_code}\n' http://127.0.0.1:8080/pastes/$ID

# No token → 403
curl -s -o /dev/null -w 'no token: %{http_code}\n' -X DELETE http://127.0.0.1:8080/pastes/$ID

# Correct token → 204, then gone
curl -s -o /dev/null -w 'revoke: %{http_code}\n' -X DELETE \
  -H "X-Delete-Token: $TOKEN" http://127.0.0.1:8080/pastes/$ID
curl -s -o /dev/null -w 'after revoke: %{http_code}\n' http://127.0.0.1:8080/pastes/$ID

# Repeat revocation with the same correct token → 404, not 403
curl -s -o /dev/null -w 'repeat: %{http_code}\n' -X DELETE \
  -H "X-Delete-Token: $TOKEN" http://127.0.0.1:8080/pastes/$ID
```

**Expected**: `403`, `200`, `403`, `204`, `404`, `404`.

**404 before 403** (FR-021) — an unknown id with a wrong token must report non-existence, not a
permission failure:

```bash
curl -s -X DELETE -H 'X-Delete-Token: wrong' \
  http://127.0.0.1:8080/pastes/AAAAAAAAAAAAAAAAAAAAAA
```

**Expected**: `404` with `{"error": "not found"}`.

---

## Scenario 4 — Durability across restart (User Story 4, P4)

Covers FR-002, FR-003, FR-023, SC-005.

```bash
# With the service running, create two pastes
curl -s -X POST http://127.0.0.1:8080/pastes -d '{"content": "persistent"}'
curl -s -X POST http://127.0.0.1:8080/pastes -d '{"content": "short", "expires_in": 2}'
```

Record both ids and the first token, then stop the service (Ctrl-C), wait 3 seconds, and restart
it against the **same** `--data` directory.

**Expected after restart**:
- The readiness line appears again on stdout.
- The first paste reads back with identical `content`, `created_at`, and `expires_at`.
- Its original `delete_token` still revokes it (`204`).
- The second paste, which expired while the service was stopped, returns `404` (FR-018).

**Fresh directory** (FR-002): start with `--data ./brand-new/nested/dir` — the service creates it,
parents included, and reports readiness.

**Startup failures** (FR-004) — each must print to stderr, exit non-zero, and print **no**
readiness line:

```bash
# Port already in use (with the service already running on 8080)
PYTHONPATH=src python -m pastebin serve --port 8080 --data ./pastes-data; echo "exit=$?"

# Unwritable data directory
mkdir -p /tmp/ro && chmod 500 /tmp/ro
PYTHONPATH=src python -m pastebin serve --port 8081 --data /tmp/ro/sub; echo "exit=$?"
```

---

## Scenario 5 — Security probes

Covers SR-003, SR-005, SR-008, SR-009, SR-012, SC-007, SC-009, SC-010.

**Path traversal** (SR-003, SC-010) — each must return `404` and touch nothing outside the data
directory:

```bash
for p in '../../etc/passwd' '..%2F..%2Fetc%2Fpasswd' '%2Fetc%2Fpasswd' '/etc/passwd' 'a/../b'; do
  curl -s -o /dev/null -w "$p -> %{http_code}\n" "http://127.0.0.1:8080/pastes/$p"
done
```

**Oversized submission** (FR-007, FR-027, FR-029, SR-005):

```bash
# Exactly 65536 bytes of content → 201
python3 -c 'import json;print(json.dumps({"content":"a"*65536}))' > /tmp/ok.json
curl -s -o /dev/null -w 'at limit: %{http_code}\n' -X POST \
  http://127.0.0.1:8080/pastes --data-binary @/tmp/ok.json

# 65537 bytes → 413
python3 -c 'import json;print(json.dumps({"content":"a"*65537}))' > /tmp/big.json
curl -s -o /dev/null -w 'over limit: %{http_code}\n' -X POST \
  http://127.0.0.1:8080/pastes --data-binary @/tmp/big.json

# 50 MB → 413, and the server's memory must not grow
python3 -c 'import json;print(json.dumps({"content":"a"*50_000_000}))' > /tmp/huge.json
curl -s -o /dev/null -w 'huge: %{http_code}\n' -X POST \
  http://127.0.0.1:8080/pastes --data-binary @/tmp/huge.json
```

**Expected**: `201`, `413`, `413`. Watch the server process's RSS during the third — it must stay
flat (SC-007).

**File permissions** (SR-008):

```bash
ls -ld ./pastes-data && ls -l ./pastes-data | head -3
```

**Expected**: the directory is `drwx------` (0700) and every record file is `-rw-------` (0600).

**No leakage** (SR-009, SC-009):

```bash
# No delete_token in any read
curl -s http://127.0.0.1:8080/pastes/$ID | grep -c delete_token   # → 0

# No path or Python version in headers or error bodies
curl -si http://127.0.0.1:8080/nope | grep -iE 'server:|python|/home|/tmp'
```

**Expected**: no `delete_token` in reads; the `Server` header is `pastebin` with no Python
version; no filesystem path appears anywhere.

**Content is inert** (SR-012):

```bash
curl -s -X POST http://127.0.0.1:8080/pastes -d '{"content": "<script>alert(1)</script>"}'
curl -si http://127.0.0.1:8080/pastes/<id>/raw | head -5
```

**Expected**: `Content-Type: text/plain; charset=utf-8` and `X-Content-Type-Options: nosniff` —
never `text/html`.

**Corrupt record tolerated** (FR-024):

```bash
echo 'not json at all' > ./pastes-data/AAAAAAAAAAAAAAAAAAAAAA.json
curl -s -o /dev/null -w 'corrupt: %{http_code}\n' \
  http://127.0.0.1:8080/pastes/AAAAAAAAAAAAAAAAAAAAAA
```

**Expected**: `404`, the service keeps running, and other pastes remain readable.

---

## Run the automated suite

```bash
PYTHONPATH=src pytest -q
```

**Expected**: all tests pass, none skipped, none `xfail` (Constitution: Development Workflow &
Quality Gates).

### Requirement coverage check

```bash
PYTHONPATH=src pytest -q tests/test_requirement_coverage.py
```

**Expected**: passes, confirming every requirement FR-001 … FR-029 and SR-001 … SR-012 is
referenced by at least one test name or docstring (SC-008, Constitution Principle III). This test
fails if a requirement id goes unreferenced, which is what makes the mapping an enforced gate
rather than a convention.

---

## Definition of done

- [ ] All five scenarios above behave as described against a freshly started service.
- [ ] `PYTHONPATH=src pytest -q` passes with zero failures, skips, or xfails.
- [ ] `tests/test_requirement_coverage.py` passes — every FR and SR maps to a test.
- [ ] Record files are `0600` and the data directory is `0700`.
- [ ] No response, header, or log line discloses a `delete_token`, a filesystem path, or a
      traceback.
- [ ] `pip list` inside a clean environment shows no runtime dependency beyond `pytest`.
