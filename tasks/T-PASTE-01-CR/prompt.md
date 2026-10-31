This repository already contains `pastebin`, a small HTTP service for sharing text snippets ("pastes"). Read the existing code and any documentation in the repository before changing it. Add the two options below for creating a paste; everything the service does now must keep working exactly as it does.

- **Burn after reading.** `"burn_after_reading": true` in the body of `POST /pastes` makes the paste one-time: the first successful read of it, by `GET /pastes/<id>` or `GET /pastes/<id>/raw`, returns it as usual and then deletes it, so every later request for it gets `404`. `burn_after_reading` is optional, defaults to `false`, and must be a boolean; any other value gets `400`.
- **Password.** `"password": "..."` in the body of `POST /pastes` protects the paste. Reading it, by either `GET` endpoint, then requires the request header `X-Paste-Password` with that password; a missing or wrong password gets `403` (for an unknown or expired paste, `404` still takes precedence). `password` is optional and, if present, must be a string of 1 to 128 characters; anything else gets `400`. Deleting a protected paste still needs only its delete token.
- `GET /pastes/<id>` also includes `"burn_after_reading"` and `"protected"` (each `true` or `false`) in its JSON.

As before, every error response has a JSON body of the form `{"error": "<message>"}`.

Examples, with the server started as `python -m pastebin serve --port 8765 --data ./pastes`:

```
$ curl -s -X POST 127.0.0.1:8765/pastes -d '{"content": "hello", "burn_after_reading": true}'
{"id": "...", "delete_token": "...", "url": "/pastes/..."}        <- status 201
$ curl -s 127.0.0.1:8765/pastes/<id>/raw
hello
$ curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8765/pastes/<id>/raw
404
```
