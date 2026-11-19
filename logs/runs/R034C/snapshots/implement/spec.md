# Feature Specification: Administrator-Issued Password Reset

**Feature Branch**: `002-password-reset`

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "This repository already contains `accounts`, a command-line tool that manages local user accounts with passwords in a single store file. Read the existing code and any documentation in the repository before changing it. Add password reset as described below; every existing command must keep working exactly as it does now. `python -m accounts --store PATH reset-token USERNAME [--ttl SECONDS]` creates a one-time password-reset token for the account and prints it on a line of its own to standard output; an administrator passes it on to the user. The token is valid for SECONDS seconds, 900 (15 minutes) by default. `python -m accounts --store PATH reset USERNAME` reads the token and then the new password from standard input, one per line. If the token is valid, it sets the new password and prints `password reset`. A token can be used only once. A wrong, already used or expired token prints `invalid token` to standard error and exits with status 1. A new password shorter than 12 characters is rejected with exit status 2, and the token can still be used afterwards. For both commands, a username that does not exist fails with exit status 3. Successful commands exit with status 0."

## Context

This feature extends the existing `accounts` tool (feature `001-local-account-manager`, requirements FR-001 – FR-038). It adds two commands and changes nothing else. Requirement identifiers continue the existing sequence from **FR-039** and success criteria from **SC-009** so that every identifier remains unique across the repository.

Today a user who has forgotten their password cannot recover it: the only way to change a password is `passwd`, which demands the current password, so an administrator must either delete and re-register the account (losing it) or learn the user's new password themselves. This feature closes that gap without ever putting a password in an administrator's hands.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recover access to a forgotten password (Priority: P1)

A user tells the administrator they cannot sign in because they have forgotten their password. The administrator issues a reset token for that user's account and passes the token to the user over whatever channel they already use. The user runs the reset command, supplies the token followed by a password of their own choosing, and is told the password was reset. They can sign in immediately with the new password; the administrator never learns it.

**Why this priority**: This is the whole point of the feature. Without it there is no recovery path at all, and the two commands together are the smallest unit that delivers one.

**Independent Test**: Register an account, issue a token for it, feed that token and a new password to the reset command, confirm `password reset` on standard output with exit status 0, then confirm a login with the new password succeeds and a login with the old password fails.

**Acceptance Scenarios**:

1. **Given** a store containing account `alice`, **When** the administrator issues a reset token for `alice`, **Then** a single line containing only the token is written to standard output, nothing is written to standard error, and the exit status is 0.
2. **Given** a token just issued for `alice`, **When** the reset command is given that token and then a 20-character new password, **Then** `password reset` is written to standard output and the exit status is 0.
3. **Given** a password reset that has just succeeded, **When** a login is attempted with the new password, **Then** it succeeds; **When** a login is attempted with the password from before the reset, **Then** it is rejected as an invalid credential.
4. **Given** a store containing account `alice`, **When** a token is issued twice in a row, **Then** the two tokens differ.

---

### User Story 2 - A token cannot be reused, guessed, or outlived (Priority: P1)

Whoever gets hold of a token can set the account's password, so the token must stop working the moment it has done its single job, and must stop working on its own even if it was never used. A user who mistypes the token, replays a token that already worked, or comes back to it an hour later is told the token is invalid — and nothing about the account changes.

**Why this priority**: A reset path that leaves long-lived or replayable tokens lying around is worse than having no reset path, because it silently weakens every account in the store. The single-use and expiry rules are part of the feature, not a hardening pass to follow it.

**Independent Test**: Exercise each rejection case — wrong token, already-used token, expired token, and an account with no outstanding token — and confirm each one writes exactly `invalid token` to standard error, exits 1, and leaves the stored password working as before.

**Acceptance Scenarios**:

1. **Given** an outstanding token for `alice`, **When** the reset command is given a different string as the token, **Then** `invalid token` is written to standard error, the exit status is 1, and `alice`'s password is unchanged.
2. **Given** a token that has already been used for a successful reset, **When** it is presented a second time with another new password, **Then** `invalid token` is written to standard error, the exit status is 1, and the password set by the first reset still works.
3. **Given** a token issued with a validity window of 1 second, **When** the reset command presents it after that window has elapsed, **Then** `invalid token` is written to standard error and the exit status is 1.
4. **Given** account `alice` with no token ever issued, **When** the reset command presents any token, **Then** `invalid token` is written to standard error and the exit status is 1.
5. **Given** an outstanding token for `alice`, **When** a second token is issued for `alice`, **Then** the first token is rejected with `invalid token` and exit status 1 while the second succeeds.

---

### User Story 3 - A rejected new password does not waste the token (Priority: P2)

The user pastes the token correctly but picks a new password that is too short. They are told the password is too short and nothing has changed — and because the mistake was theirs alone and the token was never spent, they can simply run the command again with the same token and a longer password.

**Why this priority**: Without this, a typo in the password field forces the user back to the administrator for a fresh token, which turns a self-service recovery into a two-person round trip. It is a usability rule, so it ranks below the core flow and the security rules, but it is explicitly required behaviour.

**Independent Test**: Issue a token, run the reset command with that token and an 11-character password, confirm exit status 2 with a diagnostic on standard error, then run it again with the same token and a 12-character password and confirm the reset succeeds.

**Acceptance Scenarios**:

1. **Given** an outstanding token for `alice`, **When** the reset command is given that token and an 11-character new password, **Then** a diagnostic is written to standard error, the exit status is 2, and `alice`'s password is unchanged.
2. **Given** the situation above, **When** the reset command is run again with the same token and a 12-character new password, **Then** the reset succeeds with exit status 0.
3. **Given** an outstanding token for `alice`, **When** the reset command is given a *wrong* token and a too-short password, **Then** the outcome is `invalid token` with exit status 1 — the token is judged before the password length.

---

### User Story 4 - A reset command naming an unknown account says so (Priority: P2)

An administrator mistypes a username. Both new commands report that there is no such account and exit 3, the same way `unlock`, `passwd`, and `delete` already do, so the mistake is obvious rather than looking like a token problem.

**Why this priority**: It is a small, explicitly required behaviour, but it is the difference between an administrator fixing a typo in seconds and chasing a token that was never issued.

**Independent Test**: Run both new commands against a username absent from the store and confirm each writes a diagnostic to standard error and exits 3, with no token printed and the store untouched.

**Acceptance Scenarios**:

1. **Given** a store with no account `nobody`, **When** a token is requested for `nobody`, **Then** a diagnostic naming the account is written to standard error, nothing is written to standard output, and the exit status is 3.
2. **Given** a store with no account `nobody`, **When** the reset command is run for `nobody`, **Then** a diagnostic is written to standard error and the exit status is 3, without reading the token or the password from standard input.

---

### User Story 5 - Everything that worked before still works (Priority: P1)

An administrator who has scripted `register`, `login`, `unlock`, `passwd`, and `delete` upgrades to the version with password reset. Every one of those scripts behaves identically: the same arguments, the same lines read from standard input, the same output text, the same exit statuses. Store files written before the upgrade are still read without complaint.

**Why this priority**: The feature description makes this a hard condition on the change, and the five existing commands are the tool's entire current value. A regression here is worse than shipping no reset at all.

**Independent Test**: Run the existing automated test suite for FR-001 – FR-038 unchanged, and additionally load a store file written by the pre-feature version and confirm every existing command still operates on it.

**Acceptance Scenarios**:

1. **Given** the existing test suite for FR-001 – FR-038, **When** it is run against the tool with password reset added, **Then** every test passes without modification.
2. **Given** a store file produced by the version of the tool before this feature, **When** any existing command is run against it, **Then** it behaves exactly as it did before, with no complaint about the file's contents.
3. **Given** the new `--ttl` option, **When** it is supplied to any command other than the token-issuing command, **Then** it is a usage error with exit status 2, exactly as an unrecognized option is today.

---

### Edge Cases

- **A token for a locked account**: Lockout blocks login only. A token can be issued for a locked account and a reset can succeed on it, matching the existing rule that a locked account still accepts a password change (FR-025). A successful reset does **not** clear the lock — only `unlock` does (FR-023) — so the user must still be unlocked before they can log in with the new password.
- **An invalid token is not a failed login**: Rejected tokens never increment the failed-login count and can never lock an account, matching the existing treatment of failed password changes and deletes (FR-024).
- **Standard input ends early**: If the reset command reaches end of input before reading the token line, or before reading the new-password line, it reports the missing line and exits 2 rather than treating it as an empty string — the same rule the existing commands follow (FR-018). This check precedes any judgement of the token, so a wrong token with a missing password line reports the missing password, not `invalid token`.
- **An empty token line**: An empty line is a token value like any other; it does not match any issued token, so it is rejected as `invalid token` with exit status 1.
- **A validity window of zero or a negative number of seconds**: Rejected as a usage error with exit status 2, rather than issuing a token that is dead on arrival.
- **A non-numeric or absurdly large validity window**: A non-numeric value is a usage error, exit status 2. Any positive integer is accepted; a window longer than the operator will ever wait is their choice to make.
- **Two tokens outstanding at once**: Not possible. An account has at most one outstanding token; issuing a new one supersedes the old, which is then rejected like any other wrong token.
- **The account is deleted while a token is outstanding**: Deleting the account removes its token along with the rest of its state, so a later reset for that username exits 3 (no such account).
- **The password is changed with `passwd` while a token is outstanding**: The token remains usable until it expires or is used, because existing commands must behave exactly as they do today.
- **A reset that cannot be saved**: If the store cannot be written, the reset fails with a diagnostic and a non-zero status and the previous contents survive intact, exactly as for every other store write (FR-007, FR-008).
- **Clock movement**: Expiry is judged against the system clock at the moment the reset is attempted. If the clock is moved backwards or forwards between issuing and use, the token's apparent lifetime moves with it.

## Requirements *(mandatory)*

### Functional Requirements

**Issuing a token**

- **FR-039**: The tool MUST accept a token-issuing command invoked as `python -m accounts --store PATH reset-token USERNAME [--ttl SECONDS]`. For an existing account it MUST write exactly one line to standard output containing the token and nothing else, write nothing to standard error, and exit 0.
- **FR-040**: Each issued token MUST be generated from a cryptographically suitable source of randomness with at least 128 bits of entropy, MUST consist only of characters that survive being copied and pasted as one line (no whitespace, no line break, no shell-quoting hazard), and MUST differ from every previously issued token, including one issued for the same account in the same second.
- **FR-041**: A token MUST be valid from the moment it is issued until `SECONDS` seconds have elapsed, and MUST NOT be valid thereafter. When `--ttl` is omitted, `SECONDS` MUST be 900.
- **FR-042**: `--ttl` MUST be accepted only as a positive whole number of seconds. A value that is not a whole number, or is zero or negative, MUST produce a usage diagnostic on standard error, exit 2, and leave the store unchanged with no token issued.
- **FR-043**: `--ttl` MUST be rejected with a usage diagnostic on standard error and exit status 2 when supplied with any command other than the token-issuing command, so that no existing command's accepted argument forms change.
- **FR-044**: An account MUST have at most one outstanding token. Issuing a token MUST supersede any token previously issued for that account, and the superseded token MUST thereafter be treated exactly like a token that was never issued.
- **FR-045**: The token-issuing command for a username not present in the store MUST write a diagnostic naming the account to standard error, write nothing to standard output, exit 3, and leave the store unchanged.
- **FR-046**: Issuing a token MUST NOT change the account's stored password, failed-login count, or lock state, and MUST be durable at the moment the command exits 0.
- **FR-047**: Issuing a token MUST succeed for a locked account, with the same output and status as for an unlocked one.

**Using a token**

- **FR-048**: The tool MUST accept a reset command invoked as `python -m accounts --store PATH reset USERNAME`, which MUST read the token from the first line of standard input and the new password from the second, and MUST NOT accept either value as a command-line argument.
- **FR-049**: A reset presenting an outstanding, unexpired token together with a new password satisfying the existing 12-character minimum (FR-011) MUST replace the account's stored password, write `password reset` to standard output, exit 0, and be durable at that moment.
- **FR-050**: After a successful reset, a login with the new password MUST succeed and a login with the password in force before the reset MUST be rejected as an invalid credential.
- **FR-051**: A token MUST be usable at most once: after a reset succeeds with it, presenting the same token again MUST be rejected under FR-052 and MUST leave the password set by the successful reset in force.
- **FR-052**: A presented token that does not match the account's outstanding token, or that has been superseded, already used, or has expired, or where the account has no outstanding token at all, MUST write exactly `invalid token` to standard error, exit 1, and leave the account's stored password, failed-login count, and lock state unchanged. The message and status MUST be identical in all of these cases, so the response does not reveal which of them applied.
- **FR-053**: A reset whose new password is shorter than 12 characters MUST write a diagnostic to standard error, exit 2, and leave the stored password unchanged; the presented token MUST remain outstanding and MUST still be usable for a later reset within its validity window. This length check MUST be evaluated only after the token has been accepted, so a wrong token with a too-short password reports `invalid token` and exit 1.
- **FR-054**: The reset command for a username not present in the store MUST write a diagnostic naming the account to standard error and exit 3, and the existence check MUST precede reading any line from standard input — matching the existing rule for `unlock`, `passwd`, and `delete` (FR-034).
- **FR-055**: A reset command that reaches end of input before reading the token line, or before reading the new-password line, MUST write a diagnostic to standard error and exit 2, MUST NOT treat the missing line as an empty value, and MUST leave the store unchanged. This check MUST precede judging the token.
- **FR-056**: The reset command MUST NOT read or modify the account's failed-login count or lock state: a reset MUST succeed on a locked account, a successful reset MUST NOT clear a lock, and a rejected token MUST NOT count as a failed login.

**Secret handling and store compatibility**

- **FR-057**: The store MUST NOT contain an outstanding token in any form from which the token itself can be read back; validation MUST rely on a one-way transformation of the token with a per-token random salt, in the same manner already required of passwords (FR-036).
- **FR-058**: No token MUST appear in any diagnostic or in any command's output other than the single standard-output line the token-issuing command exists to produce (extending FR-037).
- **FR-059**: A store file written before this feature MUST continue to load without complaint, and an account in it MUST behave as an account with no outstanding token. Store validation MUST continue to reject contents it does not recognize rather than defaulting or ignoring them (FR-007).

**Preserved behaviour**

- **FR-060**: The `register`, `login`, `unlock`, `passwd`, and `delete` commands MUST keep their existing invocation form, standard-input protocol, output text, exit statuses, and effects on the store, with no observable change of any kind.
- **FR-061**: The two new commands MUST use only exit statuses already defined by FR-005 — 0 for success, 1 for a rejected token, 2 for invalid input or usage, 3 for an account that does not exist — and MUST NOT introduce a new status or use status 4.
- **FR-062**: Both new commands MUST obey the existing stream discipline: results on standard output, diagnostics on standard error, never the other way round, with every message a single line (FR-004).

### Key Entities *(include if data involved)*

- **Reset token**: A single-use secret belonging to one account, created by the token-issuing command and surrendered by the user when choosing a new password. Attributes: the secret value itself (shown once, on standard output, and never recoverable from the store); the account it belongs to; the moment after which it is no longer valid. An account has either one outstanding token or none; it ceases to be outstanding when it is used, superseded by a newer token, or expires.
- **Account** *(existing, extended)*: Gains an optional outstanding reset token alongside its existing password verifier, failed-login count, and lock state. An account with no outstanding token is the normal case, including every account in a store written before this feature.
- **Validity window**: The number of seconds a token remains usable after it is issued, chosen per issuance and defaulting to 900.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-009**: Every functional requirement FR-039 – FR-062 is covered by at least one automated test that fails if the requirement is unmet — 24 of 24 mapped, with no requirement verified by manual inspection alone.
- **SC-010**: All four worked examples in the feature description reproduce exactly: the stated standard-output text, the stated standard-error text, and the stated exit status, with no extra output on either stream.
- **SC-011**: The complete existing test suite for FR-001 – FR-038 passes unmodified, and the full suite is green with the feature added.
- **SC-012**: A user who has forgotten their password regains access in exactly two commands — one run by the administrator, one by the user — with no editing of the store file by hand and without the administrator ever seeing the new password.
- **SC-013**: A token is accepted at most once and never outside its validity window, across 100% of tested cases: reuse, supersession, expiry, an unknown token, and an account with no token are each rejected with `invalid token` and exit status 1 on every run.
- **SC-014**: No token issued during testing can be found anywhere in the store file's bytes, and no token appears in any command line the tool is invoked with.
- **SC-015**: A new password rejected for being too short leaves the token usable: the immediately following attempt with the same token and an acceptable password succeeds, on every run.
- **SC-016**: Each new command completes in under 1 second on a store holding 1,000 accounts, so the reset flow feels as immediate as the existing commands (matching SC-007).
- **SC-017**: Every failure path of the two new commands produces a diagnostic on standard error naming the specific rule or condition that failed; no failure exits non-zero in silence.

## Assumptions

- **One outstanding token per account, newest wins.** The feature description says "a one-time password-reset token" without saying what happens when a second is issued before the first is used. Keeping a single slot per account is the simplest reading, matches how reset links behave in common practice, and means a re-issue after a lost token also revokes the lost one. The alternative — several valid tokens at once — adds state with no requirement asking for it.
- **The validity window must be positive.** The description gives a default of 900 seconds but no bounds. A zero or negative window would issue a token that can never be used, which is a mistake worth reporting rather than honouring, so it is treated as a usage error.
- **`invalid token` is deliberately uninformative.** The description groups wrong, used, and expired tokens behind one message and status, so the implementation must not distinguish them; this also keeps the response from confirming that a guessed token was once real.
- **Reset follows `passwd`, not `login`, on lockout.** The description is silent on locked accounts. The existing requirements already settle it: FR-025 lets a locked account's password be changed and FR-023 reserves lock clearing to `unlock`, so reset works on a locked account and does not unlock it.
- **Existing commands do not touch tokens.** A password change via `passwd` leaves an outstanding token alone, because the feature description requires existing commands to behave exactly as they do now. Deleting an account removes its token only because the account's whole record goes.
- **Tokens are stored irreversibly, like passwords.** A token is a credential that can set a password, so the reasoning behind FR-036 applies to it unchanged; a store file readable by an attacker must not hand them a usable reset.
- **Expiry uses the local system clock.** The tool is a single-process local utility with no network and no trusted time source, so the system clock is the only clock available.
- **The token is passed on out of band.** The tool prints the token and stops; delivering it to the user — chat, phone, in person — is the administrator's job and outside this feature's scope.
- **Requirement numbering continues the existing sequence.** New requirements start at FR-039 and new success criteria at SC-009 so that identifiers remain unique repository-wide and the existing requirement-to-test coverage check stays meaningful.

## Out of Scope

- Any change to how passwords are validated, stored, or verified beyond reusing the existing rules.
- Email, SMS, or any other delivery of the token to the user.
- Rate limiting or lockout of repeated invalid-token attempts; an invalid token is explicitly not a failed login (FR-056).
- Listing, revoking, or inspecting outstanding tokens as a separate command; re-issuing supersedes, and expiry handles the rest.
- An audit log or history of resets.
- Administrator authentication: anyone who can run the tool against the store file is already able to delete and re-register accounts, so the tool does not attempt to gate who may issue a token.
