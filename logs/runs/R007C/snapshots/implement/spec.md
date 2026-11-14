# Feature Specification: Burn After Reading and Password Protection

**Feature Branch**: `002-burn-after-reading-password`

**Created**: 2026-11-10

**Status**: Draft

**Input**: User description: "This repository already contains `pastebin`, a small HTTP service for sharing text snippets ("pastes"). Read the existing code and any documentation in the repository before changing it. Add the two options below for creating a paste; everything the service does now must keep working exactly as it does. — **Burn after reading**: `"burn_after_reading": true` in the body of `POST /pastes` makes the paste one-time: the first successful read of it, by `GET /pastes/<id>` or `GET /pastes/<id>/raw`, returns it as usual and then deletes it, so every later request for it gets `404`. `burn_after_reading` is optional, defaults to `false`, and must be a boolean; any other value gets `400`. — **Password**: `"password": "..."` in the body of `POST /pastes` protects the paste. Reading it, by either `GET` endpoint, then requires the request header `X-Paste-Password` with that password; a missing or wrong password gets `403` (for an unknown or expired paste, `404` still takes precedence). `password` is optional and, if present, must be a string of 1 to 128 characters; anything else gets `400`. Deleting a protected paste still needs only its delete token. — `GET /pastes/<id>` also includes `"burn_after_reading"` and `"protected"` (each `true` or `false`) in its JSON. As before, every error response has a JSON body of the form `{"error": "<message>"}`."

## Context

This feature extends the service specified in [`../001-pastebin-service/spec.md`](../001-pastebin-service/spec.md), whose requirements are numbered FR-001…FR-044. Requirements below continue that sequence from **FR-045** so that every requirement identifier in the project stays unique and every test can name exactly one requirement (Constitution Principle III). Success criteria continue from **SC-011** for the same reason.

Nothing in the earlier specification is withdrawn. Every requirement, acceptance scenario, and success criterion of feature 001 continues to hold, and FR-068 below makes that an explicitly tested obligation rather than an assumption. One earlier requirement is widened rather than changed in kind: feature 001's pre-read bound on a submission's declared length (FR-040) is recomputed to admit the larger submissions this feature makes valid (FR-071), which can only turn a rejection into an acceptance, never the reverse.

## Clarifications

### Session 2026-11-10

- Q: When a reader sends a password containing non-English characters in the `X-Paste-Password` header, how should the service turn those header bytes back into password text for comparison? → A: Treat the header value as UTF-8 — decode the header bytes as UTF-8 and compare the resulting characters to the stored password; bytes that are not valid UTF-8 cannot match, so such a read is refused as forbidden (403).
- Q: Should the pre-read "too large" ceiling on a submission's declared length be raised to make room for the two new fields? → A: Yes — recompute the fixed ceiling so the largest valid submission (maximum text, longest password, the one-time flag, worst-case encoding) still fits; FR-040's behaviour is otherwise identical and only the constant grows.
- Q: For a one-time snippet, should the service take it out of circulation before it begins sending the response body, or only after the body has been fully sent? → A: Claim first — atomically take it out of circulation and make that durable before writing any of the response, so it can never be served twice; the accepted cost is that an abrupt stop mid-response may lose a snippet nobody received.
- Q: When a read request carries the `X-Paste-Password` header more than once, which value should the service treat as the presented password? → A: None of them — a repeated password header is treated as a presented password that does not match and the read is refused as forbidden (403), so no value can count that an inspector of the request would not have seen.
- Q: Should the stored form of a password be deliberately slow to compute, or is a fast salted one-way transformation sufficient? → A: Deliberately slow — a salted, costly one-way derivation with its own salt per snippet, bounded at 10–200 ms per verification, so that a copy of the storage directory does not cheaply yield even a weak password.

### Session 2026-11-10 (amendment raised during implementation)

- Q: FR-064 requires two new fields on the structured read response, but one feature 001 test asserts that response's field set is *closed*, and FR-068 forbids editing that test. Which requirement gives way? → A: Neither is dropped; FR-068 was incomplete and is amended. SC-018 already excepted "the two added report fields", so excepting them in FR-068 makes the two consistent. FR-064 stands as written and the two fields are added. The feature 001 test's closed-set assertion is stricter than feature 001's own FR-017, which requires only that the four fields be *returned*; it is relaxed to assert their presence, names, types, and values. That single relaxation is the only edit to a feature 001 test this feature permits — every other such file stays byte-identical, and the relaxed test still fails if any feature 001 field is removed, renamed, retyped, or given a wrong value.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Share something that disappears once it has been read (Priority: P1)

Someone needs to hand over a single secret — a freshly rotated credential, a recovery code, a one-off invite — to exactly one recipient. They publish it as a one-time snippet and send the link. The recipient opens the link, gets the text, and from that moment the link is dead: a second open, a refresh, a crawler that follows the link afterwards, and the author themselves all see only "not found". The author does not have to remember to withdraw it, and does not have to guess a lifetime short enough to be safe but long enough to be useful.

**Why this priority**: This is the larger of the two additions and the one with no workaround today. The nearest thing the current service offers is a short expiry, which either expires before the recipient reads it or leaves the secret readable afterwards — it cannot express "readable exactly once". Password protection, by contrast, has a partial substitute today: an unguessable link is already a weak secret.

**Independent Test**: Publish a snippet with the one-time option set, read it once through the structured endpoint and confirm the text and metadata come back normally, then read it again and confirm "not found". Repeat using the plain-text endpoint for the first read. Confirm a one-time snippet that has not yet been read is still readable, still deletable with its credential, and still subject to its expiry.

**Acceptance Scenarios**:

1. **Given** a running service, **When** a caller publishes a snippet with the one-time option set to true, **Then** the service reports successful creation and returns an identifier, a deletion credential, and a location exactly as it does for any other snippet.
2. **Given** a one-time snippet that has not been read, **When** a caller reads it through the structured endpoint, **Then** the full snippet is returned as usual, including its text, creation time, and expiry time.
3. **Given** a one-time snippet that has just been read once, **When** anyone requests it again through either the structured or the plain-text endpoint, **Then** the service reports that it was not found, forever after.
4. **Given** a one-time snippet that has not been read, **When** a caller reads it through the plain-text endpoint, **Then** the body is exactly the stored text, and the next request for it through either endpoint reports not found.
5. **Given** a running service, **When** a caller publishes a snippet with the one-time option absent, **Then** the snippet behaves exactly as snippets behave today — repeated reads all succeed.
6. **Given** a running service, **When** a caller publishes a snippet with the one-time option set to false, **Then** repeated reads all succeed.
7. **Given** a running service, **When** a caller publishes a snippet whose one-time option is a string, a number, null, a list, or an object, **Then** the service rejects the request as invalid input and creates nothing.
8. **Given** a one-time snippet that has not been read, **When** the holder of its deletion credential deletes it, **Then** the deletion is acknowledged with no content and the snippet is afterwards not found — the one-time option changes nothing about withdrawal.
9. **Given** a one-time snippet published before the service was stopped and restarted, **When** it is read after the restart, **Then** it is returned once and is not found thereafter — the one-time property survives a restart.
10. **Given** a one-time snippet, **When** several callers read it at the same moment, **Then** exactly one of them receives the snippet and every other receives not found; none receives a partial or corrupt body.

---

### User Story 2 - Share a snippet only the password holder can read (Priority: P2)

Someone wants to put text somewhere a colleague can fetch it, but the link alone travelling through a chat log, a ticket, or a shell history should not be enough to read it. When publishing they set a password, which they pass to the recipient out of band. Fetching the snippet then requires presenting that password; without it, or with the wrong one, the request is refused. The author keeps a separate, stronger credential for withdrawal, so sharing the reading password with a colleague does not let that colleague destroy the snippet, and losing the password does not cost the author the ability to clean up.

**Why this priority**: It closes a real gap — today a leaked link is a leaked snippet — but it is a refinement of a service that already works, and the unguessable identifier already provides some protection. It is also independent of User Story 1: either option is useful without the other.

**Independent Test**: Publish a snippet with a password; confirm reading it with the correct password through both endpoints succeeds, and that reading with no password header and with a wrong password is refused and leaves the snippet readable to someone who does have the password. Confirm the password is absent from every response. Confirm deletion of a protected snippet needs only the deletion credential. Separately, publish with an empty password, an over-long password, and non-string passwords, and confirm each is rejected.

**Acceptance Scenarios**:

1. **Given** a running service, **When** a caller publishes a snippet with a password, **Then** the service reports successful creation and returns an identifier, a deletion credential, and a location, and the password is not among the returned fields.
2. **Given** a protected snippet, **When** a caller reads it through either endpoint presenting the correct password in the designated header, **Then** the snippet is returned exactly as an unprotected snippet would be.
3. **Given** a protected snippet, **When** a caller reads it through either endpoint presenting no password header at all, **Then** the service refuses the request as forbidden and the snippet remains readable to a caller who presents the correct password.
4. **Given** a protected snippet, **When** a caller reads it through either endpoint presenting a wrong password, **Then** the service refuses the request as forbidden and the snippet remains readable to a caller who presents the correct password.
5. **Given** an identifier that was never issued, **When** a caller reads it with no password or a wrong password, **Then** the service reports not found rather than forbidden.
6. **Given** a protected snippet whose expiry moment has passed, **When** a caller reads it with the correct password, with a wrong password, or with none, **Then** the service reports not found in every case.
7. **Given** a protected snippet, **When** the holder of its deletion credential deletes it presenting only that credential and no password, **Then** the deletion succeeds.
8. **Given** a protected snippet, **When** someone requests deletion presenting the correct reading password but no deletion credential, **Then** the deletion is refused as forbidden and the snippet remains readable.
9. **Given** a snippet published without a password, **When** a caller reads it presenting a password header anyway, **Then** the snippet is returned normally — the header is ignored.
10. **Given** a running service, **When** a caller publishes a snippet whose password is an empty string, a string longer than 128 characters, a number, a boolean, null, a list, or an object, **Then** the service rejects the request as invalid input and creates nothing.
11. **Given** a running service, **When** a caller publishes a snippet whose password is exactly 1 character or exactly 128 characters long, **Then** the snippet is created successfully and that password is what reading it requires.
12. **Given** a protected snippet published before the service was stopped and restarted, **When** it is read after the restart, **Then** the same password is still required and still sufficient.
13. **Given** a snippet protected by a password containing non-ASCII characters, **When** a caller reads it presenting that password UTF-8 encoded in the designated header, **Then** the snippet is returned; and **When** a caller presents header bytes that are not valid UTF-8, **Then** the read is refused as forbidden rather than failing as an internal error.
14. **Given** a running service, **When** a caller publishes a snippet whose text is the largest the service accepts and which also carries a 128-character password and the one-time option, **Then** the snippet is created successfully rather than refused as too large, and that password is what reading it requires.
15. **Given** a protected snippet, **When** a caller reads it presenting the designated header twice — including a case where one of the two copies holds the correct password — **Then** the read is refused as forbidden and the snippet remains readable to a caller who presents the correct password exactly once.

---

### User Story 3 - See how a snippet is handled before relying on it (Priority: P3)

Someone holding a link — the author checking what they published, or a tool fetching on someone's behalf — needs to know what kind of snippet it is before acting. Reading it through the structured endpoint tells them whether this read was the only one the snippet will serve, and whether a password is required to read it, without revealing the password itself. A tool can therefore warn "this link will stop working after you load it" instead of discovering it afterwards.

**Why this priority**: It is a small, visible refinement that makes the first two stories usable by anything other than a human guessing. It depends on both of them existing, so it comes last.

**Independent Test**: Publish snippets in each of the four combinations of the two options, read each through the structured endpoint, and confirm both reported flags match what was requested in every case. Confirm the plain-text endpoint is unchanged and that no response anywhere carries the password or the deletion credential.

**Acceptance Scenarios**:

1. **Given** a snippet published with neither option, **When** it is read through the structured endpoint, **Then** the response reports that it is not one-time and not protected, alongside the identifier, text, creation time, and expiry time it reports today.
2. **Given** a snippet published with the one-time option only, **When** it is read through the structured endpoint, **Then** the response reports that it is one-time and not protected.
3. **Given** a snippet published with a password only, **When** it is read through the structured endpoint presenting the correct password, **Then** the response reports that it is not one-time and is protected.
4. **Given** a snippet published with both options, **When** it is read through the structured endpoint presenting the correct password, **Then** the response reports that it is both one-time and protected, and the next read of it reports not found.
5. **Given** any snippet, **When** it is read through either endpoint, **Then** the response carries neither the deletion credential nor the password nor any value derived from the password.
6. **Given** any snippet, **When** it is read through the plain-text endpoint, **Then** the body is the text alone, with no flags or metadata added — that endpoint's response is unchanged by this feature.

---

### Edge Cases

- **A refused read does not consume a one-time snippet**: a read of a one-time, protected snippet with a missing or wrong password is refused and the snippet is still unread — the correct password still retrieves it afterwards. The same holds for a read that reports not found and for a read that fails on damaged storage: only a read that has passed every check and obtained the text goes on to consume it.
- **An interrupted delivery still consumes**: the snippet is claimed, durably, before any of the response is written (FR-048), so a caller that abandons the connection mid-body, or a service stopped at that instant, leaves the snippet consumed and gone rather than readable again. This is deliberate: an unread secret that is lost can be republished, whereas a secret delivered to two recipients cannot be recalled, and removing that second possibility is the whole purpose of the option.
- **Overlapping reads of a one-time snippet**: when several reads of the same unread one-time snippet overlap, exactly one receives the text and the rest receive not found. No caller receives a truncated body, and the snippet is not served twice.
- **A one-time snippet that is never read**: it stays readable until it is read, deleted with its credential, or its expiry moment passes — the one-time option does not shorten its life, and the two mechanisms compose (whichever comes first wins).
- **A one-time snippet that expires before it is read**: it reports not found, exactly as an expired ordinary snippet does; it is not consumed and nothing distinguishes it from a snippet that never existed.
- **Both options on one snippet**: the password is checked first and the snippet is consumed only on the read that passes that check, so a snippet cannot be burned by someone who cannot read it.
- **Precedence among failures on a read**: not found outranks forbidden, so an unknown, deleted, or expired identifier reports not found whatever password is presented. Damaged storage still reports an internal error rather than not found or forbidden, and a damaged one-time snippet is not consumed.
- **Options explicitly given as null**: unlike the lifetime field, where null means "no expiry", `null` is not an accepted value for either new option — the one-time option must be a boolean and the password must be a string, so `null` for either is invalid input. An absent field is the way to say "not one-time" and "no password".
- **Values that merely look boolean or look like a password**: the strings `"true"` and `"false"`, the numbers `1` and `0`, and an empty string are each rejected for the one-time option; there is no coercion. An empty string is likewise rejected as a password — "protected by nothing" is not expressible.
- **Password length is counted in characters**: the 1-to-128 bound is on characters, not encoded bytes, so a 128-character password of multi-byte characters is valid. Passwords may contain any characters a string can carry, including spaces and non-ASCII characters, and are compared exactly, with no trimming, case folding, or normalisation.
- **Presenting a non-ASCII password**: the password header carries bytes, so its bytes are interpreted as UTF-8 to recover the characters being presented (FR-058) — a reader encodes the password as UTF-8 and a non-ASCII password is therefore presentable and matchable. Header bytes that are not valid UTF-8 match no password, so that read is refused as forbidden rather than failing as an internal error.
- **A password header on a snippet that has none**: ignored, and the read succeeds — consistent with the service's existing tolerance of input it does not need.
- **An empty or repeated password header**: an empty header value is treated as a presented password that does not match, so it is refused rather than treated as absent. The two outcomes are indistinguishable to the caller anyway, since both are forbidden. A header given more than once is likewise refused, and no one occurrence is picked out as the presented password (FR-072) — so a correct password smuggled into a second copy of the header, past whatever inspected the first, does not open the snippet. All three cases are forbidden, not invalid input: 400 stays reserved for an invalid value of one of the two new fields at publication.
- **The largest valid submission has grown**: two new fields mean a valid publication can legitimately occupy more space than before, so the pre-read size bound grows with it (FR-071) and a maximum-length text accompanied by a 128-character password is accepted rather than refused as too large. The bound's job is still only to stop the service reading unbounded input: a submission whose text exceeds the text limit is rejected as too large exactly as it is today, whether that is decided before or after the body is read.
- **Unknown extra fields still ignored**: adding two defined fields does not change the service's tolerance of fields it does not define; a submission carrying both the new options and unrecognised fields is still accepted.
- **Snippets stored by the previous version of the service**: a stored snippet written before this feature existed carries neither option and is read as neither one-time nor protected, so an upgrade does not make existing snippets unreadable or report them as damaged.
- **Several fields invalid at once**: a submission that is invalid in more than one way is rejected once, as invalid input, with a message naming one of the problems; which one is not specified.
- **The deletion credential is still the only thing deletion checks**: a password neither substitutes for the deletion credential nor is required in addition to it.

## Requirements *(mandatory)*

### Functional Requirements

Numbering continues the sequence established in feature 001 (FR-001…FR-044).

**Publishing a one-time snippet**

- **FR-045**: The service MUST accept an optional boolean field in a publication request marking the snippet as one-time (`burn_after_reading`). When the field is absent the snippet MUST be treated as not one-time.
- **FR-046**: The service MUST reject as invalid input a publication whose one-time field is present but is not a boolean — including a string (such as `"true"`), a number (such as `1` or `0`), null, a list, or an object — and MUST create nothing in that case.
- **FR-047**: The service MUST record whether a snippet is one-time durably alongside the snippet, such that a later instance of the service started against the same storage location enforces the same behaviour.

**Reading a one-time snippet**

- **FR-048**: On the first read of a one-time snippet that succeeds — through either the structured or the plain-text endpoint — the service MUST return the snippet exactly as it would return a snippet that is not one-time, so that every later request for that identifier reports not found. The service MUST take the snippet out of circulation, and MUST make that removal durable, *before* it begins writing the response; it MUST NOT defer removal until after the response has been sent.
- **FR-049**: The service MUST consume a one-time snippet only on a read it answers successfully. A read refused for a missing or wrong password, reported as not found, or failed on damaged storage MUST leave the snippet unconsumed and still readable by a caller who can read it. A read counts as answered successfully, for this purpose, once every check that could refuse it has passed and its text has been obtained from storage; a failure after that point — a caller that abandons the connection, or the service stopping mid-response — MUST NOT make the snippet readable again, because serving a snippet twice is a worse outcome than losing one unread.
- **FR-050**: When several successful reads of the same unread one-time snippet overlap, the service MUST serve the snippet to exactly one of them and report not found to the others, and MUST NOT return a partial or corrupt body to any of them.
- **FR-051**: The service MUST treat a one-time snippet that has been consumed as permanently gone, so that a restart does not resurrect it — including a snippet whose claim was recorded but whose response never reached its caller.
- **FR-052**: The one-time option MUST NOT change deletion: the holder of a snippet's deletion credential MUST still be able to withdraw an unread one-time snippet and receive the same no-content acknowledgement, and MUST still receive not found for one that has already been consumed.
- **FR-053**: The one-time option MUST NOT change expiry: a one-time snippet whose expiry moment has been reached or passed MUST be reported as not found without being consumed.

**Publishing a protected snippet**

- **FR-054**: The service MUST accept an optional password field in a publication request, which when present MUST be a string of 1 to 128 characters inclusive, counted in characters.
- **FR-055**: The service MUST reject as invalid input a publication whose password field is present but is not a string of 1 to 128 characters — including the empty string, a string of 129 or more characters, a number, a boolean, null, a list, or an object — and MUST create nothing in that case.
- **FR-056**: The service MUST record durably that a snippet is protected and MUST require the same password after a restart; it MUST NOT store, or write anywhere, a form of the password from which the password itself can be recovered.
- **FR-073**: The stored form of a password MUST be produced by a one-way derivation that is salted per snippet — no two snippets share a salt, even when their passwords are identical — and that is deliberately costly, so that guessing candidate passwords against a copy of the storage directory is expensive rather than cheap. One verification MUST cost at least 10 milliseconds and no more than 200 milliseconds on the machine serving requests.
- **FR-074**: The cost of verifying a password MUST NOT be borne by any request other than the one presenting it: a read of a protected snippet MUST NOT delay a concurrent request concerning a different snippet, so that feature 001's obligation to serve overlapping requests concurrently (FR-042) continues to hold.
- **FR-057**: The service MUST NOT return the password, or any value derived from it, in any response from any endpoint.

**Reading a protected snippet**

- **FR-058**: The service MUST require a request reading a protected snippet, through either the structured or the plain-text endpoint, to carry the designated password header (`X-Paste-Password`) whose value equals the snippet's password exactly, with no trimming, case folding, or normalisation. The header's bytes MUST be interpreted as UTF-8 to obtain the presented password's characters, so that a password containing non-ASCII characters can be presented and matched; header bytes that are not valid UTF-8 MUST NOT match any password.
- **FR-059**: The service MUST refuse a read of a protected snippet whose password header is absent or does not match, as a forbidden error, and MUST leave the snippet intact and readable by a caller presenting the correct password.
- **FR-072**: The service MUST treat a read request that carries the password header more than once as presenting a password that does not match, and MUST refuse it as a forbidden error without selecting any one of the occurrences. A correct password MUST be presented exactly once to be accepted.
- **FR-060**: When a read names a snippet that is unknown, deleted, expired, or already consumed, the service MUST report not found regardless of the password presented — "not found" takes precedence over "refused", as it already does for deletion.
- **FR-061**: The service MUST compare the presented password against the stored snippet in a way that does not reveal, through differences in timing, how much of the password was correct.
- **FR-062**: The service MUST ignore the password header on a read of a snippet that has no password, and answer the read successfully, whatever the header's value or bytes — including bytes that are not valid UTF-8. The header is inspected only for a snippet that is protected.
- **FR-063**: A password MUST NOT change deletion: withdrawal MUST continue to require only the snippet's deletion credential, MUST NOT additionally require the password, and MUST NOT accept the password in place of the deletion credential.

**Reporting how a snippet is handled**

- **FR-064**: A successful read through the structured endpoint MUST report, in addition to the fields it reports today, whether the snippet is one-time (`burn_after_reading`) and whether it is protected (`protected`), each as a boolean that is never absent and never null.
- **FR-065**: A successful read through the plain-text endpoint MUST remain exactly as specified in feature 001 — the stored text as the whole body, labelled as UTF-8 plain text — with no flags or metadata added.
- **FR-066**: A read MUST continue to disclose neither the deletion credential nor the password.

**Compatibility**

- **FR-067**: A snippet stored before this feature existed, whose stored form names neither option, MUST be read as neither one-time nor protected, and MUST NOT be reported as damaged storage.
- **FR-068**: Every behaviour specified in feature 001 MUST remain unchanged for a snippet published without either new option: the same success and error responses, status codes, field names, timestamp format, output discipline, concurrency behaviour, and persistence guarantees. Two exceptions are permitted, and only these two:
  - the widened pre-read size bound of FR-071, which only ever turns a previous rejection into an acceptance of a submission this specification deems valid, and never the reverse; and
  - the two report fields FR-064 adds to the structured read response, which SC-018 likewise excepts. No field of feature 001 is removed, renamed, retyped, or given a different value — the response gains two fields and changes nothing else. A feature 001 test that asserts the read response's field set is *closed* therefore MUST be relaxed to assert that feature 001's four fields are present with their specified names, types, and values, which is what feature 001's FR-017 requires; this is the only edit to a feature 001 test module that this feature permits, and any other edit remains a failure of this feature rather than a fix.
- **FR-069**: Every unsuccessful response introduced or affected by this feature MUST carry the same structured body as every other unsuccessful response — a single error field holding a human-readable message naming what was wrong.
- **FR-070**: Rejection of an invalid value for either new option MUST be reported as a client input error (400), and refusal of a read for a missing or wrong password MUST be reported as a forbidden error (403); no caller input described in this specification may provoke an unhandled failure or an internal error.
- **FR-071**: The service MUST accept a publication that combines the largest valid text with the longest valid password and the one-time field. The pre-read bound on a submission's declared length established in feature 001 (FR-040) MUST therefore be recomputed to cover the largest submission this specification deems valid, and such a submission MUST NOT be rejected as too large. The bound MUST remain a fixed quantity independent of any length the caller declares, so the memory protection FR-040 exists for is unchanged.

### Key Entities

- **Snippet** *(extended)*: the entity defined in feature 001 — identifier, text, creation time, expiry time, deletion credential — gains two properties. **One-time**: a yes/no property, fixed at publication, that makes the snippet's first successful read its last. **Password protection**: either absent, or a reading secret of 1 to 128 characters that every read must present; the secret is held in a form that cannot be read back, and is distinct from and independent of the deletion credential. A snippet is reachable until it is read once (if one-time), deleted, or expired, whichever comes first.
- **Reading password**: a shared secret, chosen by the author and distributed by them out of band, that authorises reading one snippet. It grants reading only, never withdrawal, and is never disclosed by the service once published.
- **Deletion credential** *(unchanged)*: the author's unpredictable, service-issued secret that authorises withdrawal of one snippet. It remains the only credential deletion consults.

## Success Criteria *(mandatory)*

### Measurable Outcomes

Numbering continues the sequence established in feature 001 (SC-001…SC-010), all of which continue to hold.

- **SC-011**: A person can publish a one-time snippet and read it back with a single command each, and a second identical read command reports not found — demonstrable with nothing beyond a standard command-line HTTP client and no setup step between the commands.
- **SC-012**: A one-time snippet is never served more than once across its whole life: in 100% of trials, including trials where reads overlap and trials that span a restart, at most one caller receives the text and every other request for that identifier — before or after, through either endpoint — receives not found. Absent an abrupt stop of the service mid-response, exactly one caller receives it.
- **SC-013**: In 100% of trials, a read refused for a missing or wrong password leaves a one-time snippet still readable to the holder of the correct password, so a snippet cannot be destroyed by someone who cannot read it.
- **SC-014**: A protected snippet is unreadable without its password in 100% of attempts through either reading route, and readable with it in 100% of attempts, before and after a restart of the service.
- **SC-015**: Nothing a caller can retrieve from the service, and nothing written to either output stream, contains a snippet's password or any value from which it can be recovered.
- **SC-016**: Someone who holds a snippet's reading password but not its deletion credential cannot withdraw the snippet; someone who holds its deletion credential but not its password can still withdraw it.
- **SC-017**: 100% of the invalid values enumerated for the two new options produce a client input error with an explanatory message and create nothing; none produces an unhandled failure, an internal error, or a snippet.
- **SC-018**: For a snippet published with neither new option, the service's observable behaviour is indistinguishable from the previous version's except for the two added report fields — the complete feature 001 test suite passes, unchanged but for the single relaxation FR-068 permits for those two fields, and snippets written by the previous version remain readable after an upgrade.
- **SC-019**: A caller reading any snippet through the structured endpoint can tell from that one response whether the snippet is one-time and whether it is protected, in 100% of cases and for all four combinations of the two options.
- **SC-020**: Every functional requirement above is exercised by at least one automated test that names its identifier, and the whole suite — the earlier requirements included — passes.
- **SC-021**: A copy of the storage directory does not cheaply yield a snippet's password: one verification of a candidate password costs at least 10 milliseconds, and two snippets sharing the same password have different stored forms, so a single precomputed table cannot attack both. A read of a protected snippet still completes within 200 milliseconds of the equivalent unprotected read, and reads of other snippets proceed concurrently throughout.

## Assumptions

- **Numbering continues rather than restarts**: requirement and criterion identifiers continue from feature 001 so that a test naming `FR-048` is unambiguous project-wide, as Constitution Principle III's discoverable mapping requires.
- **`null` is invalid for both new options**: the feature request says each option, when present, must be a boolean or a string of 1 to 128 characters and that "any other value" or "anything else" is rejected. `null` is therefore rejected for both, deliberately unlike the existing lifetime field, where `null` is an accepted way to say "no expiry". Absence, not `null`, is how a caller declines either option.
- **Exactly-once reading is the meaning of "one-time"**: the request says the first successful read deletes the snippet. Under overlapping reads the stricter reading — exactly one caller is served — is specified (FR-050), because the alternative would let two recipients both receive a secret intended for one, which is the whole risk the option exists to remove. For the same reason the guarantee is enforced as *at most* once where the two cannot both be had: the snippet is claimed durably before the response is written (FR-048), so an abrupt stop can lose an undelivered snippet but can never cause a second delivery.
- **Only a successful read consumes**: "first successful read" is read as "the first read the service answers with the snippet". Refusals and failures do not consume (FR-049). Without this, anyone who could guess a link could destroy a protected snippet they could not read.
- **The password is stored irreversibly and expensively**: FR-056 forbids storing a recoverable form of the password, and FR-073 adds that the derivation is salted per snippet and deliberately costly. A salted key-derivation facility from the standard library is assumed to be the mechanism; the specification does not dictate which, only that the stored snippet does not disclose the password, that one verification costs 10–200 ms, and that verification stays constant-time with respect to how much of a presented password is correct. The cost is specified rather than left open because a weak password is otherwise cheap to guess offline, and the password — unlike the snippet text, which a reader of the storage directory already has in the clear — is the one thing an author may well have reused elsewhere.
- **Password strength is the author's business**: the service enforces only the 1-to-128-character bound. It applies no complexity rule, no dictionary check, no rate limiting, and no lockout on repeated wrong passwords — consistent with the existing service's absence of rate limiting and its loopback-only scope. A caller on the host can therefore keep guessing passwords; the derivation cost of FR-073 slows each attempt but is not a substitute for rate limiting, so a weak password is accordingly weak.
- **Protection is confidentiality against link leakage, not against the host**: the service binds the loopback interface and stores snippets unencrypted in a directory the operator nominates. A password keeps a leaked link from being enough to read a snippet; it does not protect the text from anyone who can read the storage directory or the service's memory.
- **Report field names and the header name are fixed**: `burn_after_reading`, `password`, `protected`, and `X-Paste-Password` are given in the feature request and are not implementation choices, exactly as the existing field and header names were.
- **One rejection message per request**: when a submission is invalid in several ways the service rejects it once and need not report every problem; which problem is named is unspecified, and tests assert the status and a non-empty message rather than specific wording.
- **Storage format may gain fields**: the stored form of a snippet gains the information these options require. Snippets written by the previous version lack those fields and are read as neither one-time nor protected (FR-067); the previous version reading a snippet written by this one is not a supported direction and is not specified.
- **Out of scope**: changing or removing a password after publication, recovering a lost password, limiting a snippet to a fixed number of reads greater than one, notifying the author that a one-time snippet was read, per-snippet access logs or read counts, encrypting snippet text at rest, rate limiting or lockout on wrong passwords, and any requirement of a password for withdrawal or of a deletion credential for reading.

## Constraints *(imposed by the request)*

These were specified in the feature request and bound the implementation rather than the behaviour; they are recorded here so that planning treats them as fixed.

- The existing service's behaviour is preserved in full — this feature adds options and two report fields, and changes nothing else that a caller can observe, save for widening the pre-read size bound so that the larger submissions it makes valid are accepted (FR-071).
- The request body field names are `burn_after_reading` and `password`; the read-time header name is `X-Paste-Password`; the added report field names are `burn_after_reading` and `protected`.
- Status codes are as given: `400` for an invalid value of either option, `403` for a missing or wrong password on a read, `404` in precedence over `403` for an unknown or expired snippet, and the existing `201`/`200`/`204` successes unchanged.
- Every unsuccessful response keeps the body shape `{"error": "<message>"}`.
- The constraints of feature 001 continue to apply: Python 3.11 or newer, standard library only, the `pastebin` package under `src/`, and the command form `python -m pastebin serve --port PORT --data DIR`.
