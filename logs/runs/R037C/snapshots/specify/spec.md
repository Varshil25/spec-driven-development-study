# Feature Specification: Burn After Reading and Password Protection

**Feature Branch**: `002-burn-after-reading-password`

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "This repository already contains `pastebin`, a small HTTP service for sharing text snippets (\"pastes\"). Read the existing code and any documentation in the repository before changing it. Add the two options below for creating a paste; everything the service does now must keep working exactly as it does. — **Burn after reading.** `\"burn_after_reading\": true` in the body of `POST /pastes` makes the paste one-time: the first successful read of it, by `GET /pastes/<id>` or `GET /pastes/<id>/raw`, returns it as usual and then deletes it, so every later request for it gets `404`. `burn_after_reading` is optional, defaults to `false`, and must be a boolean; any other value gets `400`. — **Password.** `\"password\": \"...\"` in the body of `POST /pastes` protects the paste. Reading it, by either `GET` endpoint, then requires the request header `X-Paste-Password` with that password; a missing or wrong password gets `403` (for an unknown or expired paste, `404` still takes precedence). `password` is optional and, if present, must be a string of 1 to 128 characters; anything else gets `400`. Deleting a protected paste still needs only its delete token. — `GET /pastes/<id>` also includes `\"burn_after_reading\"` and `\"protected\"` (each `true` or `false`) in its JSON. As before, every error response has a JSON body of the form `{\"error\": \"<message>\"}`."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Share a snippet that destroys itself once read (Priority: P1)

Someone needs to hand over a one-time value — a recovery code, a temporary credential, a single-use link — and wants assurance that it cannot be read twice. They mark the snippet as one-time at creation. The recipient reads it once and gets the text exactly as they would for any snippet; every subsequent attempt by anyone, including the recipient, reports not-found. The creator can tell from the structured read that a snippet is one-time before handing out the link.

**Why this priority**: This is the headline capability of the feature and is valuable on its own without passwords. It also carries the only new behaviour that changes how reads work, so it is the slice that must be proven first.

**Independent Test**: Create a snippet with the one-time option, read it once through each read form (one snippet per form), confirm the content and metadata come back exactly as for an ordinary snippet, and confirm every later read of the same snippet is not-found.

**Acceptance Scenarios**:

1. **Given** a running service, **When** a snippet is created with the one-time option enabled, **Then** creation succeeds (201) with the same response fields as any other creation — identifier, deletion token, and link — and no extra fields.
2. **Given** a one-time snippet, **When** it is fetched in structured form, **Then** the response is served normally (200) with the exact content and metadata, and reports that it is one-time and not protected.
3. **Given** a one-time snippet that has just been fetched in structured form, **When** it is fetched again in either form, **Then** the response is not-found (404) with a JSON error body.
4. **Given** a one-time snippet, **When** it is fetched in raw form, **Then** the response body is byte-for-byte the content with plain-UTF-8 text declared, and every later fetch in either form is not-found (404).
5. **Given** a running service, **When** a snippet is created with the one-time option explicitly disabled, **Then** it behaves exactly like a snippet created without the option: it can be read any number of times.
6. **Given** a running service, **When** a snippet is created without mentioning the one-time option at all, **Then** the structured read reports that it is not one-time, and repeated reads all succeed.
7. **Given** a running service, **When** the one-time option is supplied as anything other than a true/false value — a string (including `"true"`), a number (including `1` and `0`), `null`, a list, or an object — **Then** the request is rejected as a bad request (400) with a JSON error body naming the field, and nothing is stored.
8. **Given** a one-time snippet and its deletion token, **When** it is deleted with the token before anyone reads it, **Then** the response is success-with-no-content (204) and every later read is not-found (404).
9. **Given** a one-time snippet that has already been read once, **When** a delete request presents its original deletion token, **Then** the response is not-found (404).
10. **Given** a one-time snippet whose expiry moment has passed, **When** it is fetched in either form, **Then** the response is not-found (404) — the expiry rule is unaffected by the one-time option.
11. **Given** a one-time snippet, **When** several reads of it arrive at the same time, **Then** exactly one of them is served the content and all the others are not-found (404); no read ever returns partial or corrupt content.
12. **Given** a one-time snippet created before the service was stopped, **When** the service is restarted against the same storage directory, **Then** the snippet is still one-time: the first read succeeds and later reads are not-found.

---

### User Story 2 - Put a password on a shared snippet (Priority: P2)

Someone wants to share a snippet over a channel where the link may be seen by people who should not read the content — a shared chat, a ticket, a build log. They set a password at creation and pass it to the intended reader out of band. Anyone fetching the snippet must present that password; without it, or with the wrong one, the read is refused. The creator still needs nothing but the deletion token to take the snippet down, and a link to a snippet that never existed or has expired still gives nothing away about whether a password would have helped.

**Why this priority**: A second, independent protection mechanism. It is valuable on its own and testable on its own, but the service is already useful with only the one-time option, so it comes second.

**Independent Test**: Create a snippet with a password, confirm that reads without the password and with a wrong password are refused while a read with the correct password succeeds in both read forms, and confirm deletion still works with only the deletion token.

**Acceptance Scenarios**:

1. **Given** a running service, **When** a snippet is created with a password, **Then** creation succeeds (201) with the same response fields as any other creation, and the password is not among them.
2. **Given** a protected snippet, **When** it is fetched in either form with the correct password in the `X-Paste-Password` header, **Then** it is served normally (200) with the exact content.
3. **Given** a protected snippet, **When** it is fetched in structured form with the correct password, **Then** the response reports that the snippet is protected, and the password does not appear anywhere in the response.
4. **Given** a protected snippet, **When** it is fetched in either form with no `X-Paste-Password` header, **Then** the response is forbidden (403) with a JSON error body and the snippet remains readable to someone with the password.
5. **Given** a protected snippet, **When** it is fetched in either form with an empty or wrong `X-Paste-Password` value, **Then** the response is forbidden (403) with a JSON error body and the snippet remains readable to someone with the password.
6. **Given** two protected snippets with different passwords, **When** one is fetched with the other's password, **Then** the response is forbidden (403).
7. **Given** an identifier that was never issued, or one whose snippet was deleted or has expired, **When** it is fetched in either form with any password or none, **Then** the response is not-found (404), never forbidden (403).
8. **Given** a protected snippet and its deletion token, **When** a delete request presents the deletion token and no password, **Then** the response is success-with-no-content (204) and the snippet is gone.
9. **Given** a protected snippet, **When** a delete request presents the correct password but no deletion token, **Then** the response is forbidden (403) and the snippet remains readable.
10. **Given** an unprotected snippet, **When** it is fetched in either form with an `X-Paste-Password` header, **Then** the header is ignored and the snippet is served normally (200).
11. **Given** a running service, **When** a password is supplied that is not text — a number, `true`, `null`, a list, or an object — or is text of zero characters or more than 128 characters, **Then** the request is rejected as a bad request (400) with a JSON error body naming the field, and nothing is stored.
12. **Given** a running service, **When** a password of exactly 1 character, or of exactly 128 characters, is supplied, **Then** creation succeeds and that exact password is the one required to read the snippet.
13. **Given** a password containing non-ASCII characters, spaces, or punctuation, **When** the snippet is read with that exact password, **Then** it is served normally (200), and reading with a visually similar but different password is forbidden (403).
14. **Given** a protected snippet created before the service was stopped, **When** the service is restarted against the same storage directory, **Then** the same password is still required and still works.

---

### User Story 3 - Keep every existing snippet and client working (Priority: P3)

People and scripts already use this service. Someone holding a link created before the new options existed must still be able to read that snippet; a tool that posts snippets without mentioning either new option must behave exactly as it did; and the structured read must stay parseable by anything that already reads its fields.

**Why this priority**: It adds no new capability, which is why it is last, but it is the condition the whole feature is accepted under: nothing the service does today may change.

**Independent Test**: Run the existing test suite unchanged, then start the service against a storage directory holding snippets created by the previous version and confirm every one of them reads back with unchanged content and metadata and still deletes with its original token.

**Acceptance Scenarios**:

1. **Given** a storage directory holding snippets created by the previous version of the service, **When** the new version is started against it, **Then** every one of those snippets is still readable in both forms with unchanged content, identifier, creation timestamp, and expiry, still deletes with its original token, and reports itself as neither one-time nor protected.
2. **Given** a creation request that mentions neither new option, **When** it is submitted, **Then** the outcome — status, response fields, and stored result — is identical to the previous version's.
3. **Given** a creation request that is already rejected by the existing rules — unparsable body, non-object body, missing or non-string content, oversized content, invalid lifetime — **When** it also carries an invalid value for one of the new options, **Then** the status code is the one the existing rules already produced (for example oversized content is still rejected as too large, 400 cases are still 400), so no existing rejection changes.
4. **Given** a snippet with no password and no one-time option, **When** it is read repeatedly in both forms, **Then** every read succeeds with identical content, as before.
5. **Given** any error response from any route, **When** its body is examined, **Then** it is a JSON object whose single `error` field names what was wrong.
6. **Given** a request to any path or method outside the four defined routes, **When** it is made, **Then** the response is not-found (404) with a JSON error body, as before — the new options add no routes.

---

### Edge Cases

- **Both options on one snippet**: a snippet may be both one-time and protected. A read with the correct password is served and destroys the snippet; a read with a missing or wrong password is refused (403) and leaves the snippet intact and still readable once.
- **A refused read never consumes a one-time snippet**: a read that answers 403 (wrong password) or 404 (bad identifier shape) leaves the snippet available for its one legitimate read.
- **An expired one-time snippet** is not-found and is never "consumed": there was no successful read to trigger destruction.
- **Explicit `false` and explicit absence are the same thing** for the one-time option; both mean the snippet can be read repeatedly.
- **`null` is a value, not an absence**: a one-time option of `null`, or a password of `null`, is a present-and-invalid value and is rejected (400), matching how the existing lifetime field already treats `null`.
- **Numbers are not booleans**: `1` and `0` for the one-time option are rejected (400).
- **Password length is counted in characters, not bytes**: a 128-character password of multi-byte characters is accepted even though its encoded size is larger.
- **An empty password string** (`""`) is rejected (400); a snippet cannot be protected by an empty password. A snippet with no password is unprotected, which is not the same thing.
- **Password is never echoed**: it appears in no response from any route, and the structured read exposes only whether a password exists.
- **Unknown fields are still ignored**: a creation body with extra fields beyond content, lifetime, and the two new options is still accepted.
- **More than one `X-Paste-Password` header** on a read of a protected snippet is ambiguous input and is refused (403) rather than guessing which value was meant.
- **`X-Paste-Password` on a route that does not read a snippet** (creation, deletion, an unknown route) has no effect whatsoever.
- **Raw reads gain no new fields**: the raw form's body is still the content and nothing else; the two new flags appear only in the structured form.
- **A client that disappears mid-response** may lose a one-time snippet it will never be able to re-read: destruction is triggered by the service serving the read, and delivery across the network is not confirmed. The guarantee is "at most one successful read", not "exactly one delivery".
- **Concurrent reads of the same one-time snippet** are resolved so that exactly one is served; the rest are not-found. A read concurrent with a delete of the same snippet still either serves it in full or reports not-found.
- **A storage record that is unreadable or of an unrecognised format** is still reported and skipped at startup and answers 404 on read, as before — including a record whose new fields are malformed.

## Requirements *(mandatory)*

Requirement identifiers continue the numbering of the existing specification (`FR-001`–`FR-032`,
`SC-001`–`SC-010`) so that every identifier in the repository stays unique and traceable.

### Functional Requirements

**Creating a snippet with the new options**

- **FR-033**: System MUST accept an optional `burn_after_reading` field in the `POST /pastes` body; when absent the snippet MUST behave as if `false` was supplied.
- **FR-034**: System MUST reject a creation request with `400` and a JSON error body when `burn_after_reading` is present and is not a JSON boolean — including a string (such as `"true"`), a number (including `1` and `0`), `null`, an array, and an object.
- **FR-035**: System MUST accept an optional `password` field in the `POST /pastes` body when it is a string of 1 to 128 characters inclusive, and MUST treat a snippet created with it as protected.
- **FR-036**: System MUST reject a creation request with `400` and a JSON error body when `password` is present and is not a string, or is a string shorter than 1 or longer than 128 characters, where length is counted in characters.
- **FR-037**: System MUST leave the creation response unchanged by either new option: `201` with a JSON body of exactly `id`, `delete_token`, and `url`, and neither the password nor the one-time flag included.
- **FR-038**: System MUST store nothing when a creation request is rejected for either new field.
- **FR-039**: System MUST leave every existing creation outcome unchanged: a request that mentions neither new field MUST produce exactly the status, body, and stored result it produces today, and a request that the existing rules already reject MUST still be rejected with that same status even when a new field is also invalid.

**Reading a protected snippet**

- **FR-040**: System MUST require the request header `X-Paste-Password`, carrying the snippet's password, on both `GET /pastes/<id>` and `GET /pastes/<id>/raw` for a protected snippet, and MUST serve the snippet normally when it matches.
- **FR-041**: System MUST respond `403` with a JSON error body to a read of an existing, unexpired protected snippet whose `X-Paste-Password` header is absent, empty, does not match, is supplied more than once, or carries another snippet's password, and MUST leave the snippet readable to a later request that supplies the correct password.
- **FR-042**: System MUST resolve existence and expiry before the password, so that `404` always takes precedence over `403`: an unknown, deleted, expired, or ill-shaped identifier MUST answer `404` on both read routes whatever password is supplied, so no response discloses which identifiers exist or which are protected.
- **FR-043**: System MUST compare the supplied password to the snippet's password in a way that does not reveal the stored value through response timing.
- **FR-044**: System MUST serve an unprotected snippet on both read routes without any password, and MUST ignore an `X-Paste-Password` header supplied for it.
- **FR-045**: System MUST NOT require a password to delete a snippet: `DELETE /pastes/<id>` MUST continue to be authorised by the `X-Delete-Token` header alone, and MUST continue to answer `403` when that token is missing or wrong even if a correct password is supplied.
- **FR-046**: System MUST NOT disclose a snippet's password in any response from any route, and MUST NOT retain it in a form from which the original password can be recovered.

**Reading a one-time snippet**

- **FR-047**: System MUST serve the first successful read of a snippet created with `burn_after_reading` set to `true` exactly as it would serve an ordinary snippet — the same status, headers, and body on whichever read route was used — and MUST then make that snippet behave as never having existed.
- **FR-048**: System MUST answer `404` with a JSON error body to every read and every delete of a one-time snippet after its one successful read, including a delete presenting the original deletion token.
- **FR-049**: System MUST serve at most one successful read of a one-time snippet even when reads of it are in flight at the same time; every other such read MUST answer `404`, and no read MUST return partial or corrupt content.
- **FR-050**: System MUST NOT consume or destroy a one-time snippet on a read that does not succeed — a `403` from a missing or wrong password, or a `404` from an ill-shaped identifier — leaving the snippet available for its one successful read.
- **FR-051**: System MUST leave a snippet that is not one-time readable an unlimited number of times on both read routes.
- **FR-052**: System MUST apply the one-time rule after existence and expiry: an expired one-time snippet answers `404` and is never treated as having been read.
- **FR-053**: System MUST allow a one-time snippet to be deleted by its deletion token before it is read, answering `204`, and MUST answer `403` for a missing or wrong token on a one-time snippet that has not yet been read.

**Reporting the new state**

- **FR-054**: System MUST include `burn_after_reading` and `protected` in the `GET /pastes/<id>` JSON body, each exactly `true` or `false`, alongside the existing `id`, `content`, `created_at`, and `expires_at` fields, which MUST keep their current names, formats, and meanings.
- **FR-055**: System MUST report `protected` as `true` exactly when a password was set at creation, and `burn_after_reading` as `true` exactly when the one-time option was enabled at creation.
- **FR-056**: System MUST leave the `GET /pastes/<id>/raw` response unchanged: the body is the content and nothing else, with `Content-Type: text/plain; charset=utf-8`.

**Persistence and continuity**

- **FR-057**: System MUST persist whether a snippet is one-time and whether it is protected, together with what is needed to check its password, durably enough that a restart against the same storage directory preserves both behaviours exactly.
- **FR-058**: System MUST keep reading snippets stored by the previous version of the service, serving them unchanged and reporting them as neither one-time nor protected.
- **FR-059**: System MUST give every error response introduced or affected by this feature — `400` for an invalid new field, `403` for a password failure, `404` for a consumed one-time snippet — a JSON body of exactly the form `{"error": "<message>"}` whose message names what was wrong specifically enough to act on.
- **FR-060**: System MUST continue to satisfy every requirement of the existing specification (`FR-001` through `FR-032`) unchanged, including the four defined routes and the `404` catch-all, the content size limit, lifetime handling, deletion-token rules, loopback-only binding, the readiness line, stream separation, concurrency safety, and tolerance of unreadable storage entries.

### Key Entities

- **Paste (snippet)**: gains two attributes. *One-time*: whether the snippet is destroyed by its first successful read (true/false, false by default). *Password*: an optional secret, 1 to 128 characters, that a read must present; its presence is observable as "protected", its value is not. The existing attributes — identifier, content, creation moment, expiry moment, deletion token — and the rule that a paste has no owner and no title are unchanged. The lifecycle gains one exit: created → readable → (deleted by token, or expired, **or consumed by its one read**) → gone.
- **Read password**: the second credential in the system, and the first that governs *reading*. It authorises reads of exactly one paste, is chosen by the creator rather than issued by the service, is never shown by the service, and is independent of that paste's deletion token — neither credential substitutes for the other.
- **Deletion token**: unchanged. It authorises deletion of exactly one paste and remains the only thing needed to delete it, whether or not that paste is protected or one-time.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-011**: A one-time snippet can be read exactly once: in a test that creates a one-time snippet and reads it twice through each read form, the first read returns the complete original content and the second returns not-found, 100% of the time.
- **SC-012**: Across 200 one-time snippets each read concurrently by 10 simultaneous requests, exactly one request per snippet receives the content and the other nine receive not-found — no snippet is served twice and none is lost without being served.
- **SC-013**: A protected snippet is unreadable without its password: in a test sweeping no header, an empty header, a wrong password, a duplicated header, and another snippet's password across both read forms, every attempt is forbidden (403) with a JSON `error` body, and a subsequent attempt with the correct password succeeds.
- **SC-014**: Not-found beats forbidden in every case: for an identifier that was never issued, one that was deleted, one that has expired, and one that is ill-shaped, all read attempts return 404 whatever password is supplied, so an observer cannot distinguish a protected snippet from a non-existent one.
- **SC-015**: Every new rejection cause is covered: each invalid shape of the one-time field (string, number, `null`, array, object) and of the password field (non-string, empty, 129 characters) produces 400 with a JSON `error` message naming the field, and the boundary values (1-character and 128-character passwords, `true` and `false` for the one-time field) are accepted.
- **SC-016**: Each of the requirements FR-033 through FR-060 is covered by at least one automated test that names the requirement, and the whole suite passes.
- **SC-017**: Nothing that worked before changes: the existing test suite passes unmodified against the new version, and a storage directory of 50 snippets written by the previous version (mixed expiring and non-expiring, including multi-byte content) reads back after upgrade with every content, identifier, creation timestamp, and expiry timestamp unchanged, every deletion token still working, and every snippet reported as neither one-time nor protected.
- **SC-018**: Both options survive a restart: a one-time snippet created before a stop-and-start is still consumed by exactly one read afterwards, and a protected snippet created before it still requires and accepts exactly the same password.
- **SC-019**: A refused read costs nothing: in a test that attempts a snippet that is both one-time and protected 20 times with the wrong password and then once with the right one, the 20 attempts are forbidden (403) and the final attempt returns the content.
- **SC-020**: No password is ever disclosed: across every route and every status code, no response body or header contains a password that was set at creation, verified by searching every response in the suite for the passwords it used.
- **SC-021**: The service stays available: a soak of the full set of malformed new-option requests, missing-password reads, and consumed-snippet reads leaves the service still serving a valid create-read round trip.

## Assumptions

**Fixed by the request (not assumptions, recorded for traceability)**: the field names `burn_after_reading` and `password` in the creation body; the header name `X-Paste-Password`; `400` for an invalid value of either field; `403` for a missing or wrong password with `404` taking precedence; the `burn_after_reading` and `protected` fields in the structured read; the 1-to-128-character password bound; deletion remaining token-only; and the requirement that everything the service already does keeps working exactly as it does.

Where the request left a detail open, the following defaults were chosen:

- **"Successful read" means a `200` response**: destruction of a one-time snippet is triggered by the service deciding to serve the snippet, after existence, expiry, and password have all been resolved. A `403` or `404` is not a successful read and consumes nothing.
- **At most once, not exactly once**: the guarantee is that no more than one read of a one-time snippet is served. A client that disconnects while the response is in flight may lose the content for good. Guaranteeing delivery would require acknowledgement the HTTP exchange does not provide.
- **Destruction is immediate and permanent**: the snippet is removed as part of serving its one read, not swept later, so the next request genuinely finds nothing. Expired snippets continue to be left in place as they are today.
- **The password is not kept in a recoverable form**: whatever is retained must be enough to check a supplied password and not enough to reconstruct the original, so that read access to the storage directory does not hand over the passwords people chose. This is a security default the request did not ask for; the specification constrains only the property (unrecoverable, and compared without leaking through timing), never how it is achieved.
- **Password comparison is exact**: no case folding, no whitespace trimming, no Unicode normalisation. The password that reads a snippet is byte-for-byte the string that created it, consistent with how the existing deletion token is compared.
- **Password length is measured in characters**, not encoded bytes, as "a string of 1 to 128 characters" states. The existing content limit remains measured in bytes; the two limits are deliberately different because the request words them differently.
- **An ambiguous `X-Paste-Password` (sent more than once) is refused** with `403` rather than resolved by picking one occurrence, following the project's rule against coercing questionable input. This is a defensible-either-way detail; the alternative would be to accept the first occurrence.
- **Validation order within the creation body**: the existing checks (body shape, `content`, size, `expires_in`) run first and keep their current precedence, so no existing rejection changes status. Among the new fields, order is unobservable because both produce `400`.
- **The two options are independent** and may be combined in any of the four ways; neither implies or forbids the other, and neither interacts with the lifetime option.
- **No new routes, headers, or response fields beyond those named**: no way to list, to re-arm a consumed snippet, to change or remove a password after creation, or to learn how many reads a snippet has left. A snippet remains immutable once created.
- **No rate limiting or lockout on wrong passwords**: the service is loopback-only and single-operator, so repeated password attempts are not throttled and are not logged as security events beyond the ordinary per-request log line.
- **`protected` is the only visibility into a password**, and it is readable by anyone who can read the snippet — which, for a protected snippet, means someone who already has the password. For an unprotected snippet it is always `false`.
- **Storage format changes are internal**: the on-disk record is not part of the contract, and the only external compatibility requirement is that records written by the previous version keep working (FR-058).
- **Scale is unchanged**: a handful of concurrent requests and thousands of snippets; the concurrency guarantee for one-time snippets must hold at that scale.
