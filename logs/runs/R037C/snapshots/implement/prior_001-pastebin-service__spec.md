# Feature Specification: Pastebin Service

**Feature Branch**: `001-pastebin-service`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "Build a small HTTP service for sharing text snippets (\"pastes\"), using only Python's standard library (for example `http.server`). Run it as `python -m pastebin serve --port PORT --data DIR`. It listens on 127.0.0.1 at PORT, stores pastes under the directory DIR (creating it if needed) so that they survive a restart, and prints `listening on 127.0.0.1:PORT` to standard output once it is ready to accept requests. API: POST /pastes creates a paste (content required, max 65,536 UTF-8 bytes; optional expires_in of 1..2,592,000 seconds) returning 201 with id, delete_token and url; GET /pastes/<id> returns id, content, created_at, expires_at as ISO 8601 UTC; GET /pastes/<id>/raw returns the content as text/plain; charset=utf-8; DELETE /pastes/<id> with X-Delete-Token returns 204, or 403 for a missing or wrong token. An expired paste behaves as if it does not exist. Errors: 400 for invalid JSON, missing or non-string content, or invalid expires_in; 413 for oversized content; 404 for an unknown or expired paste or any other path, with 404 taking precedence over 403. Every error response has a JSON body of the form {\"error\": \"<message>\"}. Python 3.11+, standard library only, package `pastebin` under `src/`."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Share a text snippet and read it back (Priority: P1)

Someone has a block of text — a log excerpt, a configuration fragment, an error message — that they want to hand to another person or tool by reference instead of by copy-paste. They submit the text to the service, receive a short identifier and a link back, and anyone with that link can then retrieve the text, either as structured data (with its metadata) or as plain text suitable for piping into another command.

**Why this priority**: This is the entire point of the service. Without create-and-read there is no product; with just create-and-read the service is already independently useful.

**Independent Test**: Start the service, submit a snippet, and confirm the returned identifier retrieves the exact same text both in the structured form and in the plain-text form. Delivers the complete core value on its own.

**Acceptance Scenarios**:

1. **Given** a running service, **When** a snippet with content `hello` and no expiry is submitted, **Then** the response reports success-on-creation (201), supplies an identifier, a deletion token, and a link of the form `/pastes/<id>`.
2. **Given** a snippet that was just created, **When** it is fetched in structured form, **Then** the response (200) contains the identifier, the exact original content, the creation timestamp, and an expiry of `null`.
3. **Given** a snippet that was just created, **When** it is fetched in raw form, **Then** the response body is byte-for-byte the original content and the response declares plain UTF-8 text.
4. **Given** a snippet containing non-ASCII characters, emoji, embedded newlines, and quotation marks, **When** it is fetched in either form, **Then** the content round-trips unchanged.
5. **Given** a running service, **When** a snippet whose content is exactly at the maximum size (65,536 bytes when UTF-8 encoded) is submitted, **Then** it is accepted and retrievable in full.
6. **Given** a running service, **When** content one byte over the maximum is submitted, **Then** the request is rejected as too large (413) with a JSON error body and nothing is stored.
7. **Given** a running service, **When** a request body that is not valid JSON, or whose `content` is absent or not a string, is submitted, **Then** the request is rejected as a bad request (400) with a JSON error body and nothing is stored.
8. **Given** a running service, **When** an identifier that was never issued is fetched in either form, **Then** the response is not-found (404) with a JSON error body.
9. **Given** a running service, **When** any path outside the defined routes is requested, **Then** the response is not-found (404) with a JSON error body.

---

### User Story 2 - Revoke a shared snippet (Priority: P2)

The person who created a snippet realises it should no longer be readable — it was shared with the wrong audience, or it contained something they did not intend to publish. Using the deletion token they received at creation time, they remove it, and from that moment it is indistinguishable from a snippet that never existed. Nobody who only has the link can remove it.

**Why this priority**: Without revocation, anything posted is permanent, which makes the service risky to use for anything sensitive. It depends on Story 1 existing but is testable on top of it in isolation.

**Independent Test**: Create a snippet, delete it with the token returned at creation, and confirm it is subsequently unreadable; then confirm that deletion attempts without the correct token are refused.

**Acceptance Scenarios**:

1. **Given** a snippet and its deletion token, **When** a delete request presents the correct token, **Then** the response is success-with-no-content (204) and the snippet is no longer retrievable in any form (404).
2. **Given** an existing snippet, **When** a delete request presents no token, **Then** the response is forbidden (403) with a JSON error body and the snippet remains retrievable.
3. **Given** an existing snippet, **When** a delete request presents a token that does not match, **Then** the response is forbidden (403) with a JSON error body and the snippet remains retrievable.
4. **Given** an identifier that was never issued, **When** a delete request is made with any token or none at all, **Then** the response is not-found (404), never forbidden (403).
5. **Given** a snippet that was already deleted, **When** a delete request presents the original, once-valid token, **Then** the response is not-found (404).
6. **Given** two different snippets, **When** a delete request for the first presents the second one's deletion token, **Then** the response is forbidden (403) and the first snippet remains retrievable.

---

### User Story 3 - Let a snippet expire on its own (Priority: P3)

Someone pasting a short-lived secret or a transient log wants it to disappear without having to remember to delete it. They state a lifetime at creation time; the service reports when the snippet will expire, serves it normally until then, and afterwards behaves exactly as though the snippet had never existed.

**Why this priority**: Valuable for the "throwaway snippet" use case and a stated requirement, but the service is usable without it (snippets that never expire plus manual deletion). Independently testable once creation and reading exist.

**Independent Test**: Create a snippet with a short lifetime, confirm it reads normally and reports a correct expiry timestamp, then confirm that once that moment has passed it reads as not-found.

**Acceptance Scenarios**:

1. **Given** a running service, **When** a snippet is created with a lifetime of 3,600 seconds, **Then** creation succeeds and the structured form reports an expiry timestamp 3,600 seconds after the creation timestamp.
2. **Given** a snippet with a lifetime that has not yet elapsed, **When** it is fetched in either form, **Then** it is served normally (200).
3. **Given** a snippet whose expiry moment has passed, **When** it is fetched in either form, **Then** the response is not-found (404) with a JSON error body.
4. **Given** a snippet whose expiry moment has passed, **When** a delete request is made with the correct token, **Then** the response is not-found (404).
5. **Given** a running service, **When** a snippet is created with the minimum lifetime (1 second) or the maximum lifetime (2,592,000 seconds), **Then** creation succeeds.
6. **Given** a running service, **When** a lifetime of `0`, a negative number, a number above 2,592,000, a non-integer number, a string, `null`, or a boolean is supplied, **Then** the request is rejected as a bad request (400) with a JSON error body and nothing is stored.

---

### User Story 4 - Run and restart the service (Priority: P4)

An operator starts the service on a chosen port with a chosen storage directory, knows from the output when it is actually ready to take requests, and can stop and restart it — for an upgrade or a reboot — without losing the snippets that people have already shared.

**Why this priority**: Required for the service to be usable by anything other than a single in-memory test, but it adds no new user-facing capability by itself. Last because the API stories can be demonstrated before durability is proven.

**Independent Test**: Start the service with a storage directory that does not exist, observe the readiness line, create snippets, stop the service, start it again against the same directory, and confirm the snippets and their metadata are intact.

**Acceptance Scenarios**:

1. **Given** a chosen port and a storage directory path that does not yet exist, **When** the service is started, **Then** the directory is created, the service accepts requests on the loopback address at that port, and the line `listening on 127.0.0.1:<port>` appears on standard output.
2. **Given** the readiness line has been printed, **When** a request is sent immediately afterwards, **Then** it is served rather than refused.
3. **Given** snippets created against a storage directory, **When** the service is stopped and restarted against the same directory, **Then** every non-expired snippet is still retrievable with unchanged content, identifier, creation timestamp, and expiry timestamp, and its deletion token still works.
4. **Given** snippets created against a storage directory, **When** the service is restarted and a snippet whose lifetime elapsed while the service was stopped is fetched, **Then** the response is not-found (404).
5. **Given** a storage directory path that cannot be created or written, **When** the service is started, **Then** it reports a specific diagnostic on standard error and exits with a non-zero status rather than serving requests.
6. **Given** a port that is already in use, **When** the service is started, **Then** it reports a specific diagnostic on standard error and exits with a non-zero status.
7. **Given** two service instances started one after another against the same storage directory, **When** the first created snippets, **Then** the second never issues an identifier that collides with an existing snippet.

---

### Edge Cases

- **Empty content**: `{"content": ""}` is a string within the size limit, so it is accepted; the raw form returns an empty body.
- **Size measured in bytes, not characters**: content of 40,000 multi-byte characters may exceed the 65,536-byte limit even though it is far fewer than 65,536 characters; the limit is applied to the UTF-8 encoding.
- **Oversized request payload**: a request body far larger than the maximum content size is rejected as too large (413) without being buffered in full.
- **Both a size problem and a JSON problem**: a body that is both oversized and unparsable is rejected as too large (413), since the size is detectable before parsing.
- **Extra or unknown fields** in the creation body (for example `{"content": "x", "title": "y"}`) are ignored rather than rejected.
- **Non-object JSON body** (for example `"hello"`, `[1,2]`, `null`, `42`) is rejected as a bad request (400), because `content` cannot be present.
- **Missing request body** on creation is rejected as a bad request (400).
- **Unknown or expired snippet beats a token problem**: a delete request for a non-existent, deleted, or expired identifier returns not-found (404) even when the token is missing or wrong, so the response never reveals whether an identifier exists.
- **Identifier that looks like a path**: a fetch for an identifier containing path separators, `..`, encoded slashes, or an absolute path is not-found (404) and never reads anything outside the storage directory.
- **Trailing or doubled slashes and unknown sub-resources** (for example `/pastes/<id>/`, `/pastes//raw`, `/pastes/<id>/raw/extra`) are not-found (404); the only defined sub-resource is `raw`.
- **Undefined method on a defined path** (for example a `PUT` or `PATCH` to `/pastes/<id>`, or a `DELETE` to `/pastes`) is not-found (404), consistent with "any other path" being not-found.
- **Query strings** on any route are ignored for routing purposes (`/pastes/<id>?x=1` resolves to that snippet).
- **Expiry exactly at the boundary**: a snippet is readable strictly before its expiry moment and not-found at or after it.
- **Second creation of identical content** produces a distinct identifier and a distinct deletion token; snippets are never deduplicated or shared.
- **Deletion token is write-only**: it is returned only in the creation response and never appears in any read response.
- **Concurrent requests**: a read concurrent with a delete of the same snippet either serves the snippet in full or reports not-found, never partial or corrupt content.
- **Unexpected content in the storage directory** (a stray file, or a snippet record written by a future version) does not prevent the service from starting or from serving the snippets it can read.

## Requirements *(mandatory)*

### Functional Requirements

**Creating a snippet**

- **FR-001**: System MUST accept a snippet-creation request at `POST /pastes` whose JSON body carries a `content` string, and respond `201` with a JSON body containing `id`, `delete_token`, and `url`, where `url` is `/pastes/<id>`.
- **FR-002**: System MUST assign each snippet an identifier that is unique across all snippets the storage directory has ever held, is safe to place in a URL path without escaping, and is not guessable from other identifiers or from the creation order.
- **FR-003**: System MUST assign each snippet a deletion token that is unique to that snippet, unguessable, returned only in the creation response, and never exposed by any read route.
- **FR-004**: System MUST reject a creation request with `400` and a JSON error body when the body is not valid JSON, is not a JSON object, is absent, or has a `content` field that is missing or not a string.
- **FR-005**: System MUST reject a creation request with `413` and a JSON error body when `content` exceeds 65,536 bytes in its UTF-8 encoding, and MUST accept content of exactly 65,536 bytes.
- **FR-006**: System MUST treat `expires_in` as optional; when present it MUST be an integer from 1 to 2,592,000 inclusive, and any other value (including `0`, negative numbers, values above the maximum, non-integers, booleans, `null`, and strings) MUST be rejected with `400` and a JSON error body.
- **FR-007**: System MUST ignore fields in the creation body other than `content` and `expires_in`.
- **FR-008**: System MUST NOT store anything when a creation request is rejected.

**Reading a snippet**

- **FR-009**: System MUST serve `GET /pastes/<id>` for an existing, unexpired snippet with `200` and a JSON body containing `id`, `content`, `created_at`, and `expires_at`.
- **FR-010**: System MUST render `created_at` and `expires_at` as ISO 8601 timestamps in UTC with a trailing `Z` (for example `2026-10-23T20:15:00Z`), and MUST render `expires_at` as `null` for a snippet with no expiry.
- **FR-011**: System MUST serve `GET /pastes/<id>/raw` for an existing, unexpired snippet with `200`, the snippet's content as the entire response body, and the header `Content-Type: text/plain; charset=utf-8`.
- **FR-012**: System MUST return content byte-for-byte identical to what was submitted, for any valid UTF-8 text including non-ASCII characters, newlines, and control characters.

**Deleting a snippet**

- **FR-013**: System MUST delete an existing, unexpired snippet and respond `204` with no body when a `DELETE /pastes/<id>` request carries the header `X-Delete-Token` whose value matches that snippet's deletion token.
- **FR-014**: System MUST reject a delete request for an existing, unexpired snippet with `403` and a JSON error body when the `X-Delete-Token` header is absent, empty, or does not match that snippet's token, and MUST leave the snippet retrievable.
- **FR-015**: System MUST compare the supplied deletion token to the stored token in a way that does not reveal the stored token through response timing.
- **FR-016**: System MUST make a deleted snippet behave as never having existed: subsequent reads and deletes return `404`.

**Expiry**

- **FR-017**: System MUST set a snippet's expiry moment to its creation moment plus `expires_in` seconds when `expires_in` is supplied, and MUST give it no expiry otherwise.
- **FR-018**: System MUST treat a snippet as non-existent from its expiry moment onward: reads and deletes return `404`.
- **FR-019**: System MUST base expiry decisions on stored absolute timestamps, so that expiry is unaffected by restarts and by time spent not running.

**Errors and routing**

- **FR-020**: System MUST respond `404` with a JSON error body to any request whose path does not match `POST /pastes`, `GET /pastes/<id>`, `GET /pastes/<id>/raw`, or `DELETE /pastes/<id>`, including undefined methods on those paths.
- **FR-021**: System MUST return `404` rather than `403` when the identifier in a delete request is unknown, already deleted, or expired, regardless of the token supplied, so that responses do not disclose which identifiers exist.
- **FR-022**: System MUST give every error response (`400`, `403`, `404`, `413`) a JSON body of exactly the form `{"error": "<message>"}`, where the message names what was wrong specifically enough to act on.
- **FR-023**: System MUST resolve an identifier only against snippets it issued, and MUST never read or write a path outside the storage directory, whatever characters the requested identifier contains.
- **FR-024**: System MUST reject a request whose body exceeds the maximum accepted payload size with `413` and a JSON error body, without reading the whole body into memory.

**Running the service**

- **FR-025**: System MUST be startable as `python -m pastebin serve --port PORT --data DIR`, binding only the loopback address `127.0.0.1` at `PORT`.
- **FR-026**: System MUST create the storage directory, including missing parents, when it does not exist, and MUST use it as-is when it already holds snippets.
- **FR-027**: System MUST print exactly `listening on 127.0.0.1:<port>` to standard output once, after the listening socket is accepting connections, so that a request sent immediately after that line is served rather than refused.
- **FR-028**: System MUST persist each snippet's identifier, content, deletion token, creation moment, and expiry moment durably enough that a restart against the same storage directory restores all of them unchanged.
- **FR-029**: System MUST report a specific diagnostic on standard error and exit non-zero when startup cannot proceed — a missing, invalid, or out-of-range `--port` or `--data` argument, a storage directory that cannot be created or written, or a port already in use — rather than serving requests.
- **FR-030**: System MUST keep diagnostics on standard error and program output on standard output, never interleaving the two on one stream.
- **FR-031**: System MUST serve a request correctly while other requests are in flight, and MUST never serve partial, mixed, or corrupt snippet content as a result of a concurrent creation or deletion.
- **FR-032**: System MUST continue to start and to serve readable snippets when the storage directory contains an unreadable or unrecognised entry, and MUST report the skipped entry as a diagnostic on standard error.

### Key Entities

- **Paste (snippet)**: one submitted piece of text, identified by an opaque identifier. Attributes: identifier; content (text, at most 65,536 UTF-8 bytes); creation moment; expiry moment (absent for a snippet that never expires); deletion token (a secret issued once at creation). A paste has no owner, no title, and no relationship to any other paste. Its lifecycle is: created → readable → (deleted by token, or expired) → gone.
- **Storage directory**: the operator-chosen location that holds every paste the service has been asked to keep. It is the unit of persistence: the same directory given to a later run of the service yields the same set of pastes.
- **Deletion token**: the single credential in the system. It authorises deletion of exactly one paste, is shown only in that paste's creation response, and is the only thing distinguishing the paste's creator from any other reader.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person who has the service running can share a snippet and get back a working link in a single request, and the recipient can read the exact text with a single request — verified by a scripted create-then-read round trip that compares content byte-for-byte.
- **SC-002**: Every one of the functional requirements FR-001 through FR-032 is covered by at least one automated test that names the requirement, and the whole suite passes.
- **SC-003**: Each of the four error outcomes (bad request, forbidden, not found, too large) is produced by at least one test per distinct cause listed in the requirements, and every such response carries a JSON `error` message.
- **SC-004**: Snippets survive a stop-and-start cycle with 100% fidelity: in a test that creates 50 snippets (mixed expiring and non-expiring, including multi-byte content), restarts the service against the same directory, and re-reads them all, every content, identifier, creation timestamp, and expiry timestamp matches and every deletion token still works.
- **SC-005**: A snippet given a 1-second lifetime is readable before that second elapses and reports not-found afterwards, including across a restart that spans the expiry moment.
- **SC-006**: No identifier or deletion token issued across 10,000 creations repeats, and no deletion token appears in any read response.
- **SC-007**: A read of a maximum-size snippet (65,536 bytes) returns complete, unaltered content, and a snippet one byte larger is refused.
- **SC-008**: No request — including malformed, oversized, hostile-path, and unknown-route requests — causes the service to stop accepting further requests; a soak of the full malformed-request set leaves the service still serving a valid round trip.
- **SC-009**: Requests for identifiers containing path-traversal sequences never return content from outside the storage directory, verified by attempting to read a known file outside it and receiving not-found.
- **SC-010**: A fresh user can start the service and complete the three documented example commands (create, read raw, miss) with the exact outputs shown, with no setup beyond having a supported Python version.

## Assumptions

**Fixed by the request (not assumptions, recorded for traceability)**: Python 3.11 or newer, standard library only, code in a package named `pastebin` under `src/` so that `python -m pastebin` works with `src/` on `PYTHONPATH`, loopback-only binding, and the exact readiness line, routes, status codes, and limits above. These align with the project constitution's standard-library-only, fail-loudly, and testability principles.

Where the request left a detail open, the following defaults were chosen:

- **Identifier shape**: an opaque, randomly generated, URL-safe token (no sequential numbers, no content hashes). This avoids identifier enumeration and sidesteps collision handling at this scale.
- **Deletion token shape**: an independent, randomly generated secret of at least 128 bits of entropy, unrelated to the identifier so that knowing one does not yield the other.
- **Undefined methods**: a method that is not defined for an otherwise-known path returns `404` rather than `405`, following the request's rule that "any other path" is `404`. Chosen for a single uniform not-found behaviour; `405` would be equally defensible.
- **Unknown fields** in the creation body are ignored rather than rejected, so that clients can be extended without breaking against this service.
- **Non-object JSON bodies** (`"x"`, `[]`, `null`, numbers) are treated as `400` under the "missing `content`" rule.
- **Maximum accepted request payload**: a hard ceiling modestly above the 65,536-byte content limit (allowing for JSON framing and escaping), beyond which the request is refused with `413` before the body is read. Chosen so that a hostile client cannot force unbounded buffering; the exact ceiling is an implementation choice.
- **Timestamp precision**: whole seconds, UTC, rendered with a trailing `Z` as in the request's example. Sub-second precision is not exposed.
- **Expiry handling**: expiry is evaluated when a snippet is accessed; no background sweeper is required. Expired records may be removed lazily when encountered, which is why "expired" and "deleted" are indistinguishable from the outside.
- **Storage layout**: one record per paste within the storage directory, written so that a partially written record is never served as a valid paste. The specific file format and naming are implementation choices, not part of the contract.
- **No listing route**: there is deliberately no way to enumerate pastes. The only way to reach a paste is to know its identifier.
- **No authentication, rate limiting, quotas, or size accounting across pastes**: the service is loopback-only and single-operator, so the only credential is the per-paste deletion token.
- **No editing**: a paste is immutable once created; there is no update route.
- **No compression, content sniffing, or content-type negotiation**: content is treated as opaque UTF-8 text and always served as `text/plain; charset=utf-8` on the raw route.
- **Single process**: one service process owns a storage directory at a time. Two processes sharing one directory concurrently is out of scope; sequential runs against the same directory are supported and required.
- **Scale**: expected load is a handful of concurrent requests and thousands — not millions — of pastes. The design need not hold more than that.
