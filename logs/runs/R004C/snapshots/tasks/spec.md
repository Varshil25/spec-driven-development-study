# Feature Specification: Password Reset by One-Time Token

**Feature Branch**: `002-password-reset`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "This repository already contains `accounts`, a command-line tool that manages local user accounts with passwords in a single store file. Read the existing code and any documentation in the repository before changing it. Add password reset as described below; every existing command must keep working exactly as it does now. `python -m accounts --store PATH reset-token USERNAME [--ttl SECONDS]` creates a one-time password-reset token for the account and prints it on a line of its own to standard output; an administrator passes it on to the user. The token is valid for SECONDS seconds, 900 (15 minutes) by default. `python -m accounts --store PATH reset USERNAME` reads the token and then the new password from standard input, one per line. If the token is valid, it sets the new password and prints `password reset`. A token can be used only once. A wrong, already used or expired token prints `invalid token` to standard error and exits with status 1. A new password shorter than 12 characters is rejected with exit status 2, and the token can still be used afterwards. For both commands, a username that does not exist fails with exit status 3. Successful commands exit with status 0."

## Overview

The existing tool (feature `001-user-accounts-cli`) offers no way back into an
account whose password has been forgotten: `passwd` demands the current
password, and `unlock` only clears a lockout. The only remedy today is to
delete the account — which also needs the password — or to hand-edit the store.

This feature adds the missing recovery path and splits it across two people.
The administrator, who can read and write the store file, issues a short-lived
one-time token for one account and passes it to the account holder out of band.
The account holder redeems that token together with a new password, and nobody
has to learn or reveal the old one.

The two new operations join the existing five without disturbing them: the five
existing commands keep their inputs, their success output, their failure
messages and their exit statuses exactly as feature 001 specifies, and a store
written by the current version keeps loading.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recover an account with an issued token (Priority: P1)

An administrator issues a one-time reset token for an account and reads it off
standard output. The account holder, in a later invocation, supplies that token
and a new password and is told the reset succeeded. The new password works from
then on and the old one does not.

**Why this priority**: This is the whole point of the feature. Without the
happy path there is no recovery route, and the other stories only describe ways
the happy path is denied.

**Independent Test**: Register an account into a fresh store, issue a token,
then in a separate invocation redeem that token with a new password, and
confirm the printed output and exit status of each step plus that the new
password verifies and the old one does not. Nothing from the other stories is
needed.

**Acceptance Scenarios**:

1. **Given** `alice` is registered, **When** the administrator issues a reset
   token for `alice`, **Then** the exit status is 0, standard output holds
   exactly one line containing the token and nothing else, and the error stream
   is empty.
2. **Given** a reset token has just been issued for `alice`, **When** the holder
   supplies that token followed by a 21-character new password in a later
   invocation, **Then** `password reset` is written to standard output and the
   exit status is 0.
3. **Given** `alice`'s password was reset in scenario 2, **When** her new
   password is checked, **Then** the output is `ok` and the exit status is 0.
4. **Given** `alice`'s password was reset in scenario 2, **When** her *original*
   password is checked, **Then** `invalid credentials` is written to the error
   stream and the exit status is 1.
5. **Given** `alice` is registered, **When** the administrator issues a token
   with an explicit validity of 5 seconds and the holder redeems it
   immediately, **Then** the reset succeeds with exit status 0.
6. **Given** `alice` is registered, **When** the administrator issues a token
   with the standard input stream closed, **Then** the token is still printed
   and the exit status is 0 — issuing a token reads no input.
7. **Given** `alice` is locked out after five failed password checks, **When**
   the administrator issues a token and the holder redeems it with a new
   password, **Then** the reset succeeds, the lock is cleared, and the new
   password is accepted immediately afterwards.
8. **Given** two reset tokens were issued for two different accounts, **When**
   each is redeemed against its own account, **Then** both succeed and neither
   token works against the other account.

---

### User Story 2 - A token that should not work does not work (Priority: P2)

Every token that is not the current, unused, unexpired token for that account is
refused with one indistinguishable answer, and the refusal changes nothing.

**Why this priority**: A recovery path that accepted a stale, guessed or reused
token would be a way into every account on the machine. This story is what makes
story 1 safe to operate.

**Independent Test**: Register an account, then attempt a reset with a token
that was never issued, with a token that was already redeemed, with a token
whose validity has elapsed, and with a token that a newer issuance replaced —
and confirm each attempt prints `invalid token`, exits 1, and leaves the stored
password working.

**Acceptance Scenarios**:

1. **Given** `alice` is registered and no token was ever issued for her,
   **When** a reset is attempted with any token value, **Then** `invalid token`
   is written to the error stream, the exit status is 1, standard output is
   empty, and her existing password still verifies.
2. **Given** a token was issued for `alice`, **When** a reset is attempted with
   a different token value, **Then** `invalid token` is written to the error
   stream, the exit status is 1, and the issued token is still usable
   afterwards.
3. **Given** a token for `alice` was redeemed successfully, **When** the same
   token is supplied again with another new password, **Then** `invalid token`
   is written to the error stream, the exit status is 1, and the password set by
   the first redemption still verifies.
4. **Given** a token for `alice` was issued with a validity of 1 second and
   more than 1 second has since elapsed, **When** that token is supplied,
   **Then** `invalid token` is written to the error stream and the exit status
   is 1.
5. **Given** a token for `alice` was issued and then a second token was issued
   for `alice`, **When** the first token is supplied, **Then** `invalid token`
   is written to the error stream and the exit status is 1, and the second
   token still works.
6. **Given** a token for `alice` was issued, **When** `alice` changes her
   password with the existing password-change operation, **Then** that token is
   afterwards refused with `invalid token` and exit status 1.
7. **Given** a token for `alice` was issued, **When** an empty token line is
   supplied, **Then** `invalid token` is written to the error stream and the
   exit status is 1.
8. **Given** a token for `alice` was issued, **When** a reset is attempted with
   a wrong token, **Then** the stored failure count for `alice` is unchanged, so
   token guesses can neither lock the account nor be slowed by the lockout.
9. **Given** a token for `bob` was issued, **When** that token is supplied for
   `alice`, who also has an outstanding token, **Then** `invalid token` is
   written to the error stream and the exit status is 1.
10. **Given** `alice` is registered and has an outstanding token, **When** her
    *current password* is supplied on the token line, **Then** `invalid token`
    is written to the error stream and the exit status is 1 — the current
    password is never accepted in place of a token.

---

### User Story 3 - A refused new password does not burn the token (Priority: P3)

When the holder redeems a valid token but the new password does not meet the
minimum length, the attempt is refused as a bad request and the token survives,
so the holder can simply try again with a longer password.

**Why this priority**: Without this the common user mistake — typing a short
password — would force a new round trip to the administrator for every attempt,
which is the difference between a usable recovery path and an irritating one.

**Independent Test**: Register an account, issue one token, attempt a reset with
an 11-character new password and confirm the exit status is 2 and the stored
password is unchanged, then attempt the same token again with a conforming
password and confirm it succeeds.

**Acceptance Scenarios**:

1. **Given** a valid outstanding token for `alice`, **When** that token is
   supplied with an 11-character new password, **Then** an explanatory message
   is written to the error stream, the exit status is 2, standard output is
   empty, and her existing password still verifies.
2. **Given** the refusal in scenario 1, **When** the same token is supplied
   again with a 12-character new password, **Then** `password reset` is written
   to standard output and the exit status is 0.
3. **Given** a valid outstanding token for `alice`, **When** that token is
   supplied with a new password longer than the accepted maximum, **Then** an
   explanatory message is written to the error stream, the exit status is 2, and
   the token is still usable afterwards.
4. **Given** an outstanding token for `alice` that has expired, **When** it is
   supplied with an 11-character new password, **Then** the answer is
   `invalid token` with exit status 1 — the token is judged before the new
   password is examined.
5. **Given** a valid outstanding token for `alice`, **When** that token is
   supplied with a new password of exactly 12 characters, **Then** the reset
   succeeds with exit status 0.

---

### User Story 4 - Bad requests are refused without touching the store (Priority: P3)

A request that names an account nobody registered, or that is malformed in its
arguments or its input, is refused with the documented status and leaves the
store exactly as it was — including not creating it.

**Why this priority**: Completes the exit-status contract for the two new
operations and keeps the "a failing command changes nothing" guarantee of
feature 001 true for them as well.

**Independent Test**: Against a store path that does not exist, and against a
store holding only `alice`, run both new operations for a username nobody
registered and confirm the exit status is 3, the message names the missing
account, and no file is created or altered.

**Acceptance Scenarios**:

1. **Given** a store in which no such username exists, **When** a reset token is
   requested for that username, **Then** an explanatory message is written to
   the error stream and the exit status is 3.
2. **Given** a store in which no such username exists, **When** a reset is
   attempted for that username, **Then** an explanatory message is written to
   the error stream and the exit status is 3.
3. **Given** a store path that does not exist, **When** either new operation is
   run, **Then** the exit status is 3 and no file whatsoever is created at or
   beside that path.
4. **Given** any store, **When** either new operation is given a username that
   is 2 characters long, 33 characters long, or contains a character outside
   letters, digits and underscore, **Then** an explanatory message is written to
   the error stream and the exit status is 2.
5. **Given** any store, **When** a reset token is requested with a validity that
   is not a positive integer within the accepted range, **Then** an explanatory
   message is written to the error stream, the exit status is 2, and no token is
   issued.
6. **Given** `alice` is registered, **When** a reset is attempted with the input
   stream empty, or closed after the token line only, **Then** the missing input
   is reported on the error stream and the exit status is 2, changing nothing.
7. **Given** any store, **When** the validity option is given to an operation
   other than the token-issuing one, or the token-issuing operation is given a
   second validity option, **Then** usage is reported on the error stream and
   the exit status is 2.
8. **Given** a store that cannot be read or parsed, **When** either new
   operation is run, **Then** the problem is reported on the error stream and
   the exit status is 5, with no account created, deleted or altered.

---

### User Story 5 - The existing five commands are untouched (Priority: P1)

Everything feature 001 specifies about `register`, `login`, `unlock`, `passwd`
and `delete` keeps holding, byte for byte and status for status.

**Why this priority**: The request states it as a hard condition, and it is the
only part of this feature that can break software and scripts that already
depend on the tool. It shares P1 with story 1 because a working recovery path
that regresses the existing tool is not a shippable outcome.

**Independent Test**: Run the complete existing automated suite for feature 001
unchanged, apart from the two diagnostic strings that necessarily grow to list
the new operations (A-025), and confirm it passes.

**Acceptance Scenarios**:

1. **Given** the feature-001 test suite, **When** it is run against the extended
   tool, **Then** every check passes, with no change to any assertion other than
   the two diagnostic strings of A-025.
2. **Given** a store file written by the current version of the tool before this
   feature, **When** any operation reads it, **Then** it loads without error and
   every account in it still verifies its password.
3. **Given** an account with no outstanding token, **When** it is registered,
   checked, unlocked, changed or deleted, **Then** the store content, the output
   and the exit status are indistinguishable from the tool before this feature.
4. **Given** an account with an outstanding token, **When** its password is
   checked correctly, or it is unlocked, **Then** the outcome is exactly as
   feature 001 specifies and the token is left alone.
5. **Given** an account with an outstanding token, **When** the account is
   deleted, **Then** the deletion succeeds as feature 001 specifies and the
   token is gone with the account, so re-registering the same username does not
   inherit it.

---

### Edge Cases

- **No token was ever issued.** A reset attempt against an account that has no
  outstanding token is refused exactly like a wrong token (`invalid token`,
  exit 1), so output cannot be used to learn whether a reset is in progress.
- **Empty or whitespace token line.** A present but empty token line, or one
  holding only spaces, is a wrong token: `invalid token`, exit 1.
- **Token with unusual content.** A token line containing non-ASCII characters,
  punctuation or control characters is compared as supplied and refused; nothing
  from it is echoed to either stream.
- **Over-long token line.** A token line longer than the accepted input-line
  maximum is refused as a bad request (exit 2) rather than truncated and
  compared.
- **Missing input lines.** The stream is empty, or ends after the token line:
  the missing input is reported and the exit status is 2, changing nothing.
- **Extra input lines.** Input beyond the two lines a reset needs is ignored and
  is not an error. The token-issuing operation reads no lines at all and must
  work with the stream closed.
- **Validity boundary.** A token redeemed in the same second it was issued is
  valid; a token whose validity has fully elapsed is not. The boundary is
  checked at the moment of the attempt, never cached from an earlier run.
- **Validity out of range.** A validity that is zero, negative, not an integer,
  or above the accepted maximum is a bad request (exit 2); no token is issued
  and the store is not written.
- **Reissuing.** Requesting a second token for the same account replaces the
  first, which stops working at once. There is never more than one outstanding
  token per account.
- **Token for the wrong account.** A token issued for one account never works
  for another, even when both have outstanding tokens.
- **Locked account.** Issuing and redeeming a token both work on a locked
  account — this is the recovery path — and a successful reset clears the lock
  and the failure count.
- **Password change or deletion while a token is outstanding.** A successful
  password change invalidates the outstanding token; a successful deletion
  removes the account and its token together.
- **Simultaneous redemption.** Two resets run at the same moment with the same
  valid token: exactly one succeeds and the other reports `invalid token` with
  exit status 1. One token can never set two passwords.
- **First use of a store.** Neither new operation creates the store: against a
  store path that does not exist both report "no such account" with exit
  status 3 and leave no file behind, not even a temporary one.
- **Unreadable, malformed or truncated store.** Reported on the error stream
  with exit status 5, changing nothing — as for every other operation.
- **Store written before this feature.** Loads unchanged, with every account
  simply having no outstanding token.
- **Interrupted write.** Issuing or redeeming a token is interrupted midway: the
  store afterwards holds either the complete previous content or the complete new
  content, never a mixture.
- **Unknown operation, missing username, extra arguments.** Usage is reported on
  the error stream with exit status 2, and the usage text lists the two new
  operations alongside the five existing ones.
- **Username that differs only in case.** `Alice` and `alice` remain two
  distinct accounts, each with its own token.

## Requirements *(mandatory)*

Identifiers continue the sequence of feature `001-user-accounts-cli` so that no
identifier in this repository names two different requirements. Every
requirement of feature 001 (FR-001 … FR-019, SR-001 … SR-009) remains in force
unchanged; the requirements below add to them.

### Invocation and exit-status contract

- **FR-020**: The tool MUST support two further operations in the existing
  invocation form `--store PATH COMMAND USERNAME` — `reset-token` and `reset` —
  bringing the accepted set to exactly seven operations. No other operation name
  MUST be accepted, and the behaviour of the five existing operations MUST NOT
  change in any observable way (FR-040).
- **FR-021**: `reset-token` MUST accept one optional argument naming the
  validity of the token it issues, in whole seconds. When it is absent the
  validity MUST be 900 seconds. The option MUST be accepted only with
  `reset-token`, MUST NOT be abbreviated, and MUST NOT be given more than once;
  any of those MUST be refused as a usage error under status 2.
- **FR-022**: The supplied validity MUST be accepted only when it is a whole
  number of seconds within the range of A-016; anything else MUST be refused
  under status 2 with a message naming what was expected and what was received,
  and no token MUST be issued.
- **FR-023**: `reset-token` MUST read nothing from the standard input stream and
  MUST succeed with the stream closed. `reset` MUST read exactly two lines from
  the standard input stream — the token, then the new password, in that order —
  under the same line rules as every existing password line (FR-002, FR-014,
  A-009, A-022). Lines beyond the second MUST NOT be read and MUST NOT be an
  error. If the stream ends before those two lines, the operation MUST report
  the missing input under status 2 and change nothing.
- **FR-024**: Every invocation of the two new operations MUST exit with one of
  the statuses of FR-003 and no other. The conditions of that table are extended
  as follows, with no status redefined and no condition removed:

  | Status | Additional condition for `reset-token` / `reset` |
  |--------|--------------------------------------------------|
  | 0 | The token was issued, or the password was reset |
  | 1 | The supplied token is wrong, already used, replaced or expired |
  | 2 | Bad usage, invalid username, invalid validity, missing input, or a new password too short or too long |
  | 3 | The named account does not exist |
  | 5 | The store could not be read, parsed or written |

  Status 4 MUST NOT be produced by either new operation: a lockout does not
  restrict them (A-018, FR-031, FR-039).
- **FR-025**: On success `reset-token` MUST write the token and nothing else to
  the standard output stream, as a single line terminated by one newline, and
  MUST write nothing to the error stream. On success `reset` MUST write exactly
  `password reset` followed by one newline to the standard output stream and
  nothing to the error stream.
- **FR-026**: On failure both operations MUST write exactly one line to the
  error stream and nothing to the standard output stream. A refused token MUST
  produce exactly `invalid token`, with no further detail and no indication of
  which way it was refused. Every other failure MUST name what was expected and
  what was received, within the disclosure limits of SR-018.
- **FR-027**: Every failing invocation of either new operation MUST leave the
  store exactly as it was, byte for byte. Neither operation MUST ever record a
  failed-login count or alter lock state on a failure.

### Issuing a token

- **FR-028**: `reset-token` MUST, for an account that exists, generate an
  unguessable one-time token, record what is needed to verify and expire it
  against that account, persist that record, and print the token.
- **FR-029**: An account MUST have at most one outstanding token. Issuing a
  token MUST replace any token previously issued for that account, which MUST
  stop being accepted from that moment.
- **FR-030**: The token MUST be valid from the moment it is issued until its
  validity has elapsed, measured against the system clock at the moment of each
  attempt and never against a value carried over from an earlier invocation.
- **FR-031**: `reset-token` MUST succeed on a locked account and MUST NOT change
  its lock state or failure count, since the lock restricts `login` only
  (FR-019, A-018).
- **FR-032**: `reset-token` MUST NOT create the store. Against a store path that
  does not exist it MUST report that the account does not exist under status 3
  and leave no file behind.

### Redeeming a token

- **FR-033**: `reset` MUST apply its checks in exactly this order, so that each
  outcome in FR-024 is produced for one reason only: the username rules
  (status 2); the two input lines (status 2); the store loads (status 5); the
  account exists (status 3); the token is current, unused and unexpired
  (status 1); the new password rules (status 2); then the change is made.
- **FR-034**: When the token is accepted, `reset` MUST replace the account's
  stored password with the new one, MUST consume the token so that no later
  attempt with it is accepted, MUST reset the account's failed-login count to
  zero and clear its lock, and MUST leave every other account untouched. The old
  password MUST stop verifying.
- **FR-035**: A token MUST be usable at most once in total: once a reset has
  succeeded with it, every later attempt with the same token MUST be refused
  under status 1, including when two invocations redeem it at the same moment
  (SR-016).
- **FR-036**: When the token is accepted but the new password fails the rules of
  FR-012, `reset` MUST refuse the request under status 2, MUST leave the stored
  password unchanged, and MUST leave the token outstanding and still usable with
  its original validity unchanged.
- **FR-037**: `reset` MUST NOT require the account's current password and MUST
  NOT accept the current password in place of a token.
- **FR-038**: `reset` MUST NOT create the store. Against a store path that does
  not exist it MUST report that the account does not exist under status 3 and
  leave no file behind.
- **FR-039**: A refused token MUST NOT increment the account's failed-login
  count and MUST NOT be restricted by a lockout, which is defined over `login`
  attempts only (A-005, A-020).

### Compatibility with the existing tool

- **FR-040**: The five existing operations MUST keep their accepted arguments,
  their input protocol, their success output, their failure messages and their
  exit statuses exactly as feature 001 specifies, with the single exception of
  the two diagnostics that necessarily list the accepted operation names
  (A-025).
- **FR-041**: A store file written by the tool as it stands before this feature
  MUST load without error, with every account in it simply having no
  outstanding token, and every such account MUST still verify its password.
- **FR-042**: A successful `passwd` MUST invalidate any outstanding token for
  that account. A successful `delete` MUST remove the account's token with the
  account. `login` and `unlock` MUST leave an outstanding token untouched.
- **FR-043**: The limits of FR-014 and A-011 MUST continue to hold for the two
  new operations: the token line is an input line and is bounded as one, the new
  password is bounded as a password, and the token material recorded against an
  account MUST be of fixed, bounded size so that no account record can grow
  without limit.

### Security requirements

Derived, as the constitution requires, by walking all nine baseline rules of
Principle V for this feature. Each is a functional requirement and carries the
same obligation to be tested, including with the rejected input. Identifiers
continue after SR-009 of feature 001; those nine remain in force.

- **SR-010** *(rule 1 — all input untrusted)*: Every new input MUST be validated
  against an allow-list before use: the two new operation names against the
  accepted set; the validity argument against FR-022 before it is used in any
  arithmetic; the token line against A-022 and the input-line limit; the new
  password line against FR-012 and FR-014; and the token material read back from
  a store record against its expected structure, field set, format and range.
  An account record whose reset material fails validation MUST be reported under
  status 5, never repaired, guessed at, ignored or skipped — and in particular a
  malformed expiry MUST NOT be treated as "not expired".
- **SR-011** *(rule 2 — no injection by concatenation)*: Token material and
  expiry MUST be written to and read from the store only through the existing
  structured encoding, so that no token value can create, merge or truncate a
  record. The token printed to the standard output stream MUST consist only of
  characters that cannot act as a terminal control sequence or a line
  terminator, so that printing it cannot forge an additional line of output. No
  input MUST be used to build a shell command, a query or markup; this feature
  issues none.
- **SR-012** *(rule 3 — path containment)*: Confinement of the store path to a
  base directory does NOT apply, for the reason already recorded in SR-003 —
  naming the store is the operator's explicit purpose. This feature introduces
  no new path from input: it reads and writes only the store named on the
  command line, through the existing temporary-file discipline of SR-003, which
  MUST continue to apply unchanged to writes made by both new operations.
- **SR-013** *(rule 4 — credential and token storage)*: The token MUST NOT be
  written to the store, to any file, or to any stream other than the single line
  of standard output that is the deliberate purpose of `reset-token`. What is
  recorded against the account MUST be a salted digest of the token produced by
  the same deliberately slow algorithm and current parameters already used for
  passwords, with a fresh salt per issued token, and MUST be sufficient to
  verify a presented token and no more. No token MUST appear in the repository,
  including in tests and fixtures, which MUST use synthetic values. The new
  password MUST be stored under SR-004 exactly as every other password is.
- **SR-014** *(rule 5 — randomness and comparison)*: The token MUST be generated
  by a cryptographically secure source, never a general-purpose pseudo-random
  one, and MUST carry at least 128 bits of entropy so that it cannot be guessed
  within its validity. Its salt MUST likewise come from a cryptographically
  secure source. A presented token MUST be compared against the stored material
  in constant time.
- **SR-015** *(rule 6 — resource limits)*: Every new input MUST have an enforced
  maximum: the token line and the new-password line under the existing line and
  password limits, and the validity under FR-022's range, which MUST bound the
  recorded expiry so that no arithmetic on it can overflow or produce a value
  outside the store's accepted range. The reset material recorded per account
  MUST be of fixed size (FR-043), so the store size and account limits of
  A-011 continue to bound the file. No new pattern matching whose cost can grow
  faster than linearly with input length MUST be introduced.
- **SR-016** *(rule 7 — authorisation at the point of operation)*: The right to
  reset a password MUST be established by verifying the presented token, and its
  unexpired and unused state, within the same invocation that performs the
  change; no earlier result, cached state or input-supplied field may stand in
  for it. Expiry and single use MUST be read from the store at the moment of the
  attempt. The read, modify and write of the store MUST be serialised against
  other invocations under the existing discipline of SR-007, so that no
  interleaving lets one token set two passwords and no concurrent issuance
  leaves two tokens outstanding for one account. The authority to issue a token
  is, by design, the ability to write the store file, which the owner-only
  permissions of SR-008 are what limit (A-014).
- **SR-017** *(rule 8 — least-privilege files)*: The store and the temporary
  file used to replace it MUST continue to be created readable and writable by
  their owner only, with the permissions set at creation. This feature MUST NOT
  write the token, or anything else, to any other file — no spool, no audit log,
  no sidecar.
- **SR-018** *(rule 9 — no sensitive data in output)*: No password, salt, digest,
  hashing parameter, stored token material, expiry instant, store content,
  internal path other than the operator's own argument, or stack trace MUST
  appear in either output stream. The issued token is the single deliberate
  exception and MUST be written only by `reset-token`, only on success, and only
  to the standard output stream. A refused token MUST produce the identical
  message and status whether it was wrong, already used, replaced, or expired,
  and whether or not any token was ever issued for the account, so output cannot
  be used to learn the state of a reset. Redaction MUST happen before anything
  is written.

### Key Entities

- **Reset token**: a one-time, short-lived authorisation to replace one
  account's password without knowing the current one. It exists in exactly two
  places: as a value printed once to the administrator, and as verification
  material plus an expiry instant recorded against the account (never the token
  itself). At most one is outstanding per account; it ceases to exist when it is
  redeemed, when it expires, when another is issued for the same account, when
  that account's password is changed, or when the account is deleted.
- **Account** *(extended)*: unchanged in identity and in its password
  verification material and failed-login count, and now additionally carrying at
  most one outstanding reset token's verification material and expiry. An account
  with none behaves exactly as an account did before this feature.
- **Store** *(extended)*: unchanged as the single file at the operator-supplied
  path holding the whole set of accounts. It now also carries outstanding reset
  tokens' verification material, and MUST keep loading files written before this
  feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-012**: Every outcome in the extended status table of FR-024 is reachable,
  and for each one an automated check confirms the exit status, the standard
  output and the error output match this specification — 100% of the functional
  and security requirements of this feature map to at least one passing
  automated check.
- **SC-013**: A token issued in one invocation is redeemed successfully in a
  later, separate invocation 100% of the time, with no setup step between them;
  and a second attempt with that same token is refused 100% of the time.
- **SC-014**: A token is accepted before its validity has elapsed and refused
  after it, in 100% of trials, for both the default validity and an explicitly
  supplied one.
- **SC-015**: An issued token appears nowhere except the one line of standard
  output that printed it — searching the store file, any temporary file left
  behind, and the error stream for the token value after every operation yields
  zero occurrences.
- **SC-016**: Tokens are unguessable: across 10 000 issued tokens no two are
  equal, and each carries at least 128 bits of entropy.
- **SC-017**: A new password refused for its length leaves the token usable: the
  immediately following attempt with the same token and a conforming password
  succeeds, in 100% of trials.
- **SC-018**: A wrong token, an already-redeemed token, a replaced token and an
  expired token are indistinguishable from the outside: identical message,
  identical exit status, identical empty standard output, in 100% of cases — as
  is a token presented for an account that never had one.
- **SC-019**: The complete automated suite of feature 001 passes against the
  extended tool, with no change to any assertion other than the two diagnostic
  strings of A-025.
- **SC-020**: A store file written by the tool before this feature loads without
  error and every account in it still verifies its password, in 100% of trials.
- **SC-021**: Every failing invocation of either new operation leaves the store
  byte-identical, verified by comparing the file before and after each failure
  case; and every account other than the one being reset is byte-identical after
  a successful reset.
- **SC-022**: Issuing and redeeming a token each finish in under one second on a
  store holding 1 000 accounts.
- **SC-023**: Two simultaneous redemptions of one valid token result in exactly
  one success and one refusal, in 100% of trials, and the account's password is
  afterwards the one set by the single success.
- **SC-024**: Killing the tool at any point while a token is being issued or
  redeemed leaves a store that still parses and still verifies every account it
  held before, in 100% of trials.
- **SC-025**: Running the documented example sequence of the feature request
  reproduces its output and exit statuses exactly, line for line.

## Assumptions

Reasonable defaults chosen where the feature request did not say. Each is
testable as written and can be revisited in clarification. Assumptions A-001 …
A-013 of feature 001 remain in force; in particular A-012 (single machine,
single operator) and A-013 (standard library only, `python -m accounts` with
`src/` on `PYTHONPATH`) continue to bound this feature.

- **A-014 — "Administrator" means whoever can write the store file.** The
  request says an administrator passes the token on, but the tool has no notion
  of a role (A-012) and this feature does not add one. The authority to issue a
  token is therefore exactly the authority to write the store, the same
  authority `unlock` already requires (A-006), limited by the file's owner-only
  permissions. Issuing a token requires no password.
- **A-015 — At most one outstanding token per account, and issuing replaces.**
  The request describes "a one-time password-reset token for the account", in the
  singular. Keeping one slot per account makes "already used" well defined,
  bounds the record size (FR-043), and makes reissuing the natural remedy when a
  token goes astray. The replaced token stops working immediately.
- **A-016 — Validity bounds: a whole number of seconds from 1 to 86 400.** The
  request gives a default of 900 and no range. A lower bound of 1 second follows
  from "valid for SECONDS seconds" being meaningless at zero or below, and an
  upper bound of 86 400 (one day) satisfies SR-015 while leaving every practical
  hand-off comfortable. Both bounds are adjustable without changing any other
  requirement.
- **A-017 — "No token was ever issued" is answered like a wrong token.** The
  request enumerates wrong, used and expired. An account with no outstanding
  token is treated as the same single case — `invalid token`, status 1 — because
  any other answer would reveal whether a reset is in progress (SR-018).
- **A-018 — A reset needs no password and ignores the lock, and clears it.**
  The request asks for exactly a token and a new password, so the current
  password is neither required nor accepted in its place. By analogy with
  FR-019, under which the lock restricts `login` only, both new operations work
  on a locked account; and as with a successful `passwd`, a successful `reset`
  resets the failure count and clears the lock, making the reset a complete
  recovery path.
- **A-019 — A successful password change invalidates an outstanding token.**
  The request does not say what a password change does to a token in flight.
  Invalidating it is the standard practice and the safer default: it closes the
  window in which an old, possibly leaked, token could undo a deliberate change.
  A successful deletion removes the account and its token together. A successful
  or failed `login`, and an `unlock`, leave the token alone. None of this alters
  the output or exit status of any existing operation (FR-040).
- **A-020 — Token guesses do not count toward the lockout.** The failed-login
  count is defined over `login` attempts (A-005), and a token carrying at least
  128 bits of entropy (SR-014) cannot be guessed within its validity, so no
  separate attempt limit is introduced. The consequence — a wrong token neither
  locks the account nor is slowed down — is stated so it can be tested.
- **A-021 — Status 3 for an unknown username is the request's explicit
  choice.** It means these two operations do reveal whether a username exists,
  exactly as `unlock`, `passwd` and `delete` already do. This is a deliberate
  departure from the enumeration-resistance of `login` (A-001, SR-009), stated
  by the request for both new commands, and it is scoped to callers who can
  already read the store file (A-014).
- **A-022 — A token is one line of text, excluding its terminator.** The token
  line is read and bounded exactly as a password line is (A-009, FR-014): the
  terminator is stripped and is not part of the token, a final line without a
  terminator is valid, the line must be valid UTF-8, and a line over the
  input-line limit is refused rather than truncated. The token is compared
  exactly, with no trimming of surrounding whitespace, so a line that does not
  match byte for byte is a wrong token.
- **A-023 — The issued token is printable, non-whitespace ASCII.** It is printed
  for a person to copy and paste, so it uses an alphabet safe to show in a
  terminal and safe to pass through a shell: letters, digits and the URL-safe
  punctuation, with no whitespace, no quoting characters and no control
  characters (SR-011). Its length follows from the 128-bit entropy requirement.
- **A-024 — Expiry is an absolute instant recorded at issue, read from the
  system clock.** The tool trusts the machine's clock, consistent with the
  single-machine scope of A-012: it records when the token stops being valid and
  compares that against the clock at each attempt. A clock moved backwards
  extends a token's life and a clock moved forwards shortens it; defending
  against an operator who can change the clock of the machine whose store file
  they can already write is out of scope.
- **A-025 — Two existing diagnostics necessarily grow, and nothing else
  changes.** The usage line and the unknown-operation message both enumerate the
  accepted operation names, so both must now list `reset-token` and `reset`
  alongside the five existing names, or they would misreport the interface. This
  is the only permitted change to any existing message, and it affects only
  text already emitted on an argument-shape failure — no existing operation's
  accepted input, success output, failure message or exit status changes
  (FR-040). The two automated assertions that pin those strings are updated to
  the new text; every other assertion of feature 001 stays as written (SC-019).
- **A-026 — Stores written by this feature are not guaranteed readable by the
  earlier version.** Backward compatibility is required and specified (FR-041):
  old stores load. The reverse — a store carrying an outstanding token being
  read by the tool as it stands today — is out of scope, because that tool
  validates an account record against a fixed field set and has no notion of
  reset material. Downgrading is not a supported operation.
- **A-027 — No audit trail, notification or rate limit.** The request asks for
  issuance and redemption only. There is no record of who issued a token or
  when, no message sent to the account holder (the request has the administrator
  hand it over out of band), no limit on how many tokens may be issued, and no
  expiry sweep: an expired token is simply refused and is overwritten by the
  next issuance for that account.
