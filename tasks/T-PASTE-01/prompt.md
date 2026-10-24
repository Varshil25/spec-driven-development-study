Build a small HTTP service for sharing text snippets ("pastes"), using only Python's standard library (for example `http.server`).

Run it as `python -m pastebin serve --port PORT --data DIR`. It listens on 127.0.0.1 at PORT, stores pastes under the directory DIR (creating it if needed) so that they survive a restart, and prints `listening on 127.0.0.1:PORT` to standard output once it is ready to accept requests.

API (request and response bodies are JSON unless stated otherwise):

- `POST /pastes` with a body such as `{"content": "hello", "expires_in": 3600}` creates a paste. `content` is a required string of at most 65,536 bytes when UTF-8 encoded. `expires_in` is optional and, if present, must be an integer number of seconds from 1 to 2,592,000 (30 days). The response is `201` with `{"id": ..., "delete_token": ..., "url": "/pastes/<id>"}`.
- `GET /pastes/<id>` responds `200` with `{"id": ..., "content": ..., "created_at": ..., "expires_at": ...}`. Timestamps are ISO 8601 in UTC, such as `2026-10-23T20:15:00Z`; `expires_at` is `null` for a paste that never expires.
- `GET /pastes/<id>/raw` responds `200` with the paste's content as the response body and the header `Content-Type: text/plain; charset=utf-8`.
- `DELETE /pastes/<id>` with the header `X-Delete-Token: <delete_token>` deletes the paste and responds `204`. A missing or wrong token gets `403`.
- An expired paste behaves as if it does not exist.

Errors: a body that is not valid JSON, a missing or non-string `content`, or an invalid `expires_in` gets `400`; content over the size limit gets `413`; an unknown or expired paste, or any other path, gets `404` (for an unknown or expired paste, `404` takes precedence over `403`). Every error response has a JSON body of the form `{"error": "<message>"}`.

Use Python 3.11 or newer and the standard library only. Put the code in a package named `pastebin` under `src/`, so that it runs with `python -m pastebin` when `src/` is on `PYTHONPATH`.

Examples, with the server started as `python -m pastebin serve --port 8765 --data ./pastes`:

```
$ curl -s -X POST 127.0.0.1:8765/pastes -d '{"content": "hello"}'
{"id": "...", "delete_token": "...", "url": "/pastes/..."}        <- status 201
$ curl -s 127.0.0.1:8765/pastes/<id>/raw
hello
$ curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8765/pastes/does-not-exist
404
```
