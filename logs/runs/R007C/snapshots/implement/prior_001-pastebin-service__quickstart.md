# Quickstart & Validation Guide: Pastebin Service

**Feature**: `001-pastebin-service` | **Plan**: [plan.md](./plan.md)

How to run the service and prove the feature works end to end. Interface details live in
[contracts/http-api.md](./contracts/http-api.md), [contracts/cli.md](./contracts/cli.md), and
[contracts/storage.md](./contracts/storage.md); field semantics in
[data-model.md](./data-model.md).

## Prerequisites

- Python 3.11 or newer (`python3 --version`)
- `curl` for the manual scenarios
- `pytest` for the automated suite: `python3 -m pip install -r requirements-dev.txt`

No runtime dependencies. Nothing to build or install for the service itself.

## Run it

```bash
PYTHONPATH=src python3 -m pastebin serve --port 8765 --data ./pastes
```

Expected: the line `listening on 127.0.0.1:8765` on standard output, a `./pastes` directory created
if absent, and nothing further printed no matter how much traffic follows.

## Automated suite

```bash
python3 -m pytest            # pytest.ini puts src/ on the path; no PYTHONPATH needed
python3 -m pytest -q         # terse
python3 -m pytest -k fr040   # one requirement
```

Expected: all tests pass. Every functional requirement FR-001…FR-044 is named by at least one test —
see the [requirement to test map](./data-model.md#requirement-to-test-map). `pytest -k fr0NN`
is the quickest way to check a single requirement's coverage.

## Manual validation scenarios

Each scenario below maps to a user story's Independent Test in [spec.md](./spec.md). Start the
service as above first; `$ID` and `$TOKEN` refer to values from the publish response.

### 1. Publish, read, read raw — User Story 1 (SC-001, SC-002)

```bash
curl -s -X POST 127.0.0.1:8765/pastes -d '{"content": "hello"}'
curl -s 127.0.0.1:8765/pastes/$ID
curl -si 127.0.0.1:8765/pastes/$ID/raw
curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8765/pastes/does-not-exist
```

Expected: `201` with `id`, `delete_token`, and `url: /pastes/<id>`; then a JSON body carrying the
same `id`, `"content": "hello"`, a `created_at` timestamp ending in `Z`, and `"expires_at": null`;
then a response whose body is exactly `hello` with no trailing newline and header
`Content-Type: text/plain; charset=utf-8`; then `404`.

Fidelity check across the supported range:

```bash
printf '{"content": "a\\nb ☃ 🎉"}' | curl -s -X POST 127.0.0.1:8765/pastes -d @-
curl -s -X POST 127.0.0.1:8765/pastes -d '{"content": ""}'
curl -s 127.0.0.1:8765/pastes/$ID/raw | cmp - expected.txt
```

Expected: both publish; the raw body of the first is byte-for-byte what was submitted (newline,
non-ASCII, and emoji intact); the empty snippet's raw body is empty with `Content-Length: 0`.

### 2. Lifetimes — User Story 2 (SC-005)

```bash
curl -s -X POST 127.0.0.1:8765/pastes -d '{"content": "temp", "expires_in": 3600}'
curl -s -X POST 127.0.0.1:8765/pastes -d '{"content": "brief", "expires_in": 1}'
sleep 2
curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8765/pastes/$BRIEF_ID
curl -s -X POST 127.0.0.1:8765/pastes -d '{"content": "x", "expires_in": 0}'
curl -s -X POST 127.0.0.1:8765/pastes -d '{"content": "x", "expires_in": "3600"}'
curl -s -X POST 127.0.0.1:8765/pastes -d '{"content": "x", "expires_in": 2592001}'
```

Expected: the first publishes with `expires_at` exactly one hour after its `created_at`; the
short-lived one reads back normally and then `404`s on `GET`, `GET /raw`, **and** `DELETE` with the
correct token; each of the last three is `400` with an `error` message and creates nothing.

### 3. Withdrawal — User Story 3 (SC-006)

```bash
curl -si -X DELETE 127.0.0.1:8765/pastes/$ID -H "X-Delete-Token: $TOKEN"
curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8765/pastes/$ID
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE 127.0.0.1:8765/pastes/$OTHER_ID
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE 127.0.0.1:8765/pastes/$OTHER_ID -H "X-Delete-Token: wrong"
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE 127.0.0.1:8765/pastes/nope -H "X-Delete-Token: wrong"
```

Expected: `204` with an empty body, then `404`; `403` twice with `$OTHER_ID` still readable
afterwards; `404` (not `403`) for the unknown id — a deletion attempt reveals nothing a read would
not have.

### 4. Survives a restart — User Story 4 (SC-004)

```bash
# publish two snippets, one with expires_in, then stop the service with Ctrl-C and restart it
PYTHONPATH=src python3 -m pastebin serve --port 8765 --data ./pastes
curl -s 127.0.0.1:8765/pastes/$ID
curl -si -X DELETE 127.0.0.1:8765/pastes/$ID -H "X-Delete-Token: $TOKEN"
```

Expected: both snippets read back with unchanged `id`, `content`, `created_at`, and `expires_at` —
the restart neither extends nor shortens the expiry — and the original delete token still works. A
snippet whose expiry passed while the service was stopped `404`s.

### 5. Error surface (SC-003, SC-009)

```bash
curl -s -X POST 127.0.0.1:8765/pastes -d 'not json'
curl -s -X POST 127.0.0.1:8765/pastes -d '[1,2,3]'
curl -s -X POST 127.0.0.1:8765/pastes -d '{"expires_in": 60}'
curl -s -X POST 127.0.0.1:8765/pastes -d '{"content": 42}'
curl -s -X POST 127.0.0.1:8765/pastes -H 'Content-Type: text/plain' -d '{"content": "ok"}'
curl -s -X POST 127.0.0.1:8765/pastes -d "{\"content\": \"$(python3 -c 'print("x"*65537)')\"}"
curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8765/
curl -s -o /dev/null -w '%{http_code}\n' -X PUT 127.0.0.1:8765/pastes/$ID
```

Expected: `400`, `400`, `400`, `400` each with an explanatory `error` field; `201` for the
mislabelled content type (the declared type is ignored); `413` for the oversize content; `404` for
the root path and for the unsupported method. Throughout all of this the service's terminal shows no
additional output — the ready line remains the only line on standard output and standard error stays
empty.

Oversize declared body (FR-040), which `curl` cannot express — send a header claiming a huge body:

```bash
printf 'POST /pastes HTTP/1.0\r\nContent-Length: 999999999\r\n\r\n' | nc 127.0.0.1 8765
```

Expected: an immediate `413` with an `error` body, without the service waiting for or reading a
gigabyte.

### 6. Startup failures (FR-005, FR-006)

```bash
PYTHONPATH=src python3 -m pastebin serve --data ./pastes            ; echo "exit=$?"
PYTHONPATH=src python3 -m pastebin serve --port abc --data ./pastes ; echo "exit=$?"
PYTHONPATH=src python3 -m pastebin serve --port 8765 --data ./pastes ; echo "exit=$?"   # while one is already running
PYTHONPATH=src python3 -m pastebin serve --port 8766 --data /proc/nope ; echo "exit=$?"
```

Expected: exit `2` for the two argument errors with an `argparse` message naming the argument; exit
`1` for the port conflict and for the unusable storage directory, each with one explanatory line on
standard error; in all four cases no `listening on …` line is printed.

### 7. Concurrency and partial-read safety (SC-010, FR-042, FR-043)

```bash
# ten overlapping publishes, reads, and deletes
seq 1 10 | xargs -P 10 -I{} curl -s -X POST 127.0.0.1:8765/pastes -d '{"content": "{}"}'
# a caller that connects and goes quiet must not block anyone
(exec 3<>/dev/tcp/127.0.0.1/8765; printf 'POST /pastes HTTP/1.0\r\nContent-Length: 50\r\n\r\n' >&3; sleep 30) &
curl -s -o /dev/null -w 'served in %{time_total}s\n' 127.0.0.1:8765/pastes/$ID
```

Expected: ten distinct ids, each reading back its own content; the read served in well under a
second while the quiet connection is still open; no response is ever truncated or corrupt. The
automated equivalents are in `tests/test_concurrency.py`.

## Done when

- `python3 -m pytest` passes with every FR-001…FR-044 test green.
- Scenarios 1–7 behave as described above.
- Across a whole session, standard output holds exactly one line and standard error only the
  failures named in [contracts/cli.md](./contracts/cli.md).
