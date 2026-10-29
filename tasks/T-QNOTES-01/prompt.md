Build a small HTTP service where users keep private notes, using Java 21 and the Quarkus project skeleton that is already in this repository.

It is built with `./mvnw package` and started as

```
java -Dquarkus.http.host=127.0.0.1 -Dquarkus.http.port=PORT -Dnotes.data-dir=DIR -jar target/quarkus-app/quarkus-run.jar
```

It listens on 127.0.0.1 at PORT and stores all its data under the directory DIR (creating it if needed), so that users and notes survive a restart. When `notes.data-dir` is not given, DIR is `./data`.

API (request and response bodies are JSON):

Users:

- `POST /users` with a body such as `{"name": "alice"}` registers a user and responds `201` with `{"name": "alice", "api_key": "..."}`. `name` is a required string of 3 to 32 characters, each a lowercase letter, a digit, `-` or `_`. A name that is already registered gets `409`.
- Every request to `/notes` must carry the header `X-Api-Key` with a key returned by `POST /users`. A missing or unknown key gets `401`.

Notes. Each note belongs to the user who created it.

- `POST /notes` with a body such as `{"title": "Groceries", "body": "milk, eggs", "tags": ["home"]}` creates a note and responds `201` with the note. `title` is a required string of 1 to 200 characters. `body` is an optional string of at most 10,000 characters (default `""`). `tags` is an optional list of at most 10 strings (default `[]`), each of 1 to 30 characters, each character a lowercase letter, a digit or `-`.
- A note is returned as `{"id": ..., "title": ..., "body": ..., "tags": [...], "created_at": ..., "updated_at": ...}`. Timestamps are ISO 8601 in UTC with whole seconds, such as `2026-10-23T20:15:00Z`. A new note's `updated_at` equals its `created_at`.
- `GET /notes/{id}` responds `200` with the note.
- `PUT /notes/{id}` with the same kind of body as `POST /notes` replaces the note's title, body and tags (a field left out takes its default), sets `updated_at` to the current time, and responds `200` with the note.
- `DELETE /notes/{id}` deletes the note and responds `204`.
- `GET /notes` responds `200` with `{"notes": [...]}`, listing the caller's notes. Optional query parameters:
  - `q`: only notes whose title or body contains this text;
  - `tag`: only notes that have this tag;
  - `sort`: `created_at` (the default), `updated_at` or `title`;
  - `order`: `asc` (the default) or `desc`;
  - `limit`: an integer from 1 to 100 (default 20), the most notes to return;
  - `offset`: an integer of 0 or more (default 0), the number of notes to skip first.

  Notes with equal sort values are listed in the order they were created.

Errors: a body that is not valid JSON, a missing or invalid field, or an invalid query parameter gets `400`; an unknown note gets `404`, as does any other path. Every error response has a JSON body of the form `{"error": "<message>"}`.

Use Java 21, the Quarkus version in the skeleton's `pom.xml` (3.40.1.1), and only the libraries already declared there. Do not change the build or start commands above.

Examples, with the service started on port 8765 (`<KEY>` is the `api_key` from the first response):

```
$ curl -s -X POST 127.0.0.1:8765/users -H 'Content-Type: application/json' -d '{"name": "alice"}'
{"name": "alice", "api_key": "..."}                                      <- status 201
$ curl -s -X POST 127.0.0.1:8765/notes -H 'X-Api-Key: <KEY>' -H 'Content-Type: application/json' -d '{"title": "Groceries", "tags": ["home"]}'
{"id": ..., "title": "Groceries", "body": "", "tags": ["home"], "created_at": "...", "updated_at": "..."}    <- status 201
$ curl -s '127.0.0.1:8765/notes?tag=home' -H 'X-Api-Key: <KEY>'
{"notes": [{"id": ..., "title": "Groceries", ...}]}                      <- status 200
$ curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8765/notes
401
```
