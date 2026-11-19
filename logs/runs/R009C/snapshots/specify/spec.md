# Feature Specification: Password reset by one-time token

**Feature Branch**: `002-password-reset`

**Created**: 2026-11-11

**Status**: Draft

**Input**: User description: "This repository already contains `accounts`, a command-line tool that manages local user accounts with passwords in a single store file. Read the existing code and any documentation in the repository before changing it. Add password reset as described below; every existing command must keep working exactly as it does now. `python -m accounts --store PATH reset-token USERNAME [--ttl SECONDS]` creates a one-time password-reset token for the account and prints it on a line of its own to standard output; an administrator passes it on to the user. The token is valid for SECONDS seconds, 900 (15 minutes) by default. `python -m accounts --store PATH reset USERNAME` reads the token and then the new password from standard input, one per line. If the token is valid, it sets the new password and prints `password reset`. A token can be used only once. A wrong, already used or expired token prints `invalid token` to standard error and exits with status 1. A new password shorter than 12 characters is rejected with exit status 2, and the token can still be used afterwards. For both commands, a username that does not exist fails with exit status 3. Successful commands exit with status 0."

## Context: what already exists

This feature extends the shipped `001-accounts-cli` feature rather than standing alone. The
existing tool offers five commands — `register`, `login`, `unlock`, `passwd`, `delete` — against a
single store file, with a fixed exit-status vocabulary (0 success, 1 invalid credentials, 2 invalid
input, 3 account conflict, 4 account locked, 5 store unusable) and a documented message inventory.
See [`../001-accounts-cli/spec.md`](../001-accounts-cli/spec.md) and its contracts.

Requirement and criterion identifiers here continue that spec's numbering (FR-031 onward, SC-010
onward) so that every identifier in the project remains unique and a test can name exactly one
requirement, as Principle III requires.

Two new commands are added. Nothing about the five existing commands changes, with one single
deliberate exception that cannot be avoided: the usage line printed for a malformed invocation must
list the commands that actually exist, so its text grows (FR-040).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An administrator issues a reset token and the user resets their password (Priority: P1)

A user has forgotten their password. An administrator runs `reset-token` for that account and gets
back a single line — the token — which they pass on to the user out of band. The user runs `reset`,
types the token and then their new password, and sees `password reset`. The new password now logs
them in; the old one no longer does.

**Why this priority**: this is the whole feature. Without it there is no way to recover an account
whose password is forgotten, because `passwd` requires the current password. Delivered alone, it is
a complete and useful capability.

**Independent Test**: register an account, run `reset-token`, feed the printed token and a new
password to `reset`, then log in with the new password and fail to log in with the old one.

**Acceptance Scenarios**:

1. **Given** an account `alice` exists, **When** `reset-token alice` is run, **Then** a token is
   printed on a line of its own on standard output, nothing is written to standard error, and the
   exit status is 0.
2. **Given** a token was just issued for `alice`, **When** `reset alice` is given that token and a
   new password of at least 12 characters, **Then** `password reset` is printed on standard output
   and the exit status is 0.
3. **Given** a password was reset, **When** `login alice` is given the new password, **Then** `ok`
   is printed and the exit status is 0.
4. **Given** a password was reset, **When** `login alice` is given the password from before the
   reset, **Then** `invalid credentials` is printed on standard error and the exit status is 1.
5. **Given** an account `alice` exists, **When** `reset-token alice` is run twice, **Then** the two
   printed tokens differ.

---

### User Story 2 - A token that is wrong, already used or expired is refused (Priority: P2)

Someone presents a token that is not the one issued, or one that has already been spent, or one
whose validity window has passed. The attempt is refused, nothing is changed, and the account keeps
the password it had.

**Why this priority**: a reset path that accepts a stale or guessed token is a way into every
account on the machine, so the refusals are what make Story 1 safe to ship. It is tested
independently of the happy path's success message.

**Independent Test**: for each of the three bad-token cases, run `reset` and assert
`invalid token` / 1, then assert the old password still logs in.

**Acceptance Scenarios**:

1. **Given** a token was issued for `alice`, **When** `reset alice` is given a different string as
   the token, **Then** `invalid token` is printed on standard error, the exit status is 1, and the
   stored password is unchanged.
2. **Given** a token was issued and already used successfully, **When** `reset alice` is given that
   same token again with another valid new password, **Then** `invalid token` / 1 results and the
   password set by the first reset still logs in.
3. **Given** a token was issued with `--ttl 1` and more than one second has passed, **When**
   `reset alice` is given that token, **Then** `invalid token` / 1 results.
4. **Given** no token has ever been issued for `alice`, **When** `reset alice` is given any token
   string, **Then** `invalid token` / 1 results.
5. **Given** a wrong token was just refused for `alice`, **When** `reset alice` is given the
   correct outstanding token, **Then** the reset succeeds — a failed attempt does not spend or
   disarm the outstanding token.

---

### User Story 3 - A too-short new password is rejected but the token survives (Priority: P3)

The user mistypes a new password that is too short. The attempt is rejected, and the user can try
again with the same token rather than going back to the administrator for a new one.

**Why this priority**: it turns a common slip into a retry instead of a second round trip to an
administrator. It is the one case where a rejected `reset` leaves the token usable, so it needs its
own assertions.

**Independent Test**: issue a token, run `reset` with a password of 11 characters, assert exit
status 2, then run `reset` again with the same token and a valid password and assert success.

**Acceptance Scenarios**:

1. **Given** a token was issued for `alice`, **When** `reset alice` is given that token and a
   new password of 11 characters, **Then** `password too short` is printed on standard error, the
   exit status is 2, and the stored password is unchanged.
2. **Given** that rejection just happened, **When** `reset alice` is given the same token and a
   password of 12 characters, **Then** `password reset` / 0 results.
3. **Given** a token was issued for `alice`, **When** `reset alice` is given a wrong token *and* a
   too-short new password, **Then** `invalid token` / 1 results — the token is judged before the
   password's length.

---

### User Story 4 - A reset for an account that does not exist fails plainly (Priority: P4)

An administrator mistypes a username, or asks to reset an account that was deleted. Both new
commands say so and fail.

**Why this priority**: required for completeness and for consistency with `unlock`, `passwd` and
`delete`, which already report an unknown account this way. Lowest priority because it adds no new
capability.

**Independent Test**: run both new commands against a username absent from the store and assert
`no such account` / 3.

**Acceptance Scenarios**:

1. **Given** no account `nobody` exists, **When** `reset-token nobody` is run, **Then**
   `no such account` is printed on standard error, the exit status is 3, and no token is printed on
   standard output.
2. **Given** no account `nobody` exists, **When** `reset nobody` is given a token line and a
   password line, **Then** `no such account` / 3 results.
3. **Given** `alice` had a token issued and was then deleted and registered again, **When**
   `reset alice` is given that token, **Then** `invalid token` / 1 results — a token does not
   survive the account it belongs to.

---

### Edge Cases

- **`--ttl` with a value that is not a positive whole number of seconds** (`--ttl abc`, `--ttl 0`,
  `--ttl -5`, `--ttl 1.5`, `--ttl` with nothing after it): usage line on standard error, exit 2,
  store untouched (FR-033).
- **`--ttl` given to a command other than `reset-token`**: usage line, exit 2 (FR-033).
- **Standard input ends before `reset` has both its lines** (no input at all, or only the token
  line): `missing password input` on standard error, exit 2, store untouched — the existing
  end-of-input rule, applied before the account is looked up (FR-036).
- **An empty token line**: a token of length 0 is simply not the issued token → `invalid token` / 1,
  not missing input.
- **An empty new-password line, with a valid token**: a password of length 0 is too short →
  `password too short` / 2, token still usable.
- **Input beyond `reset`'s two lines**: ignored, not an error (FR-035).
- **A token string containing leading or trailing spaces**: the line is taken verbatim, with only
  the line break removed, exactly as passwords are; a token surrounded by spaces is therefore not
  the issued token → `invalid token` / 1 (FR-035).
- **A locked account**: `reset-token` and `reset` both work on it and neither changes the lock or
  the failed-login tally, so `login` still reports `account locked` / 4 afterwards until `unlock`
  is run (FR-032, FR-038). See Assumptions.
- **A second `reset-token` while a token is outstanding**: the newer token is the only valid one;
  the earlier token becomes invalid immediately (FR-032).
- **A wrong token presented many times**: refused every time, and never locks the account or
  advances the failed-login tally (FR-038).
- **A store file written before this feature existed**: loads and works unchanged, with no
  migration step and no change of format marker (FR-039).
- **A store file holding reset-token state**: every existing command reads and rewrites it without
  error, and preserves the token state of accounts it does not touch (FR-039).
- **`passwd` run while a token is outstanding**: the token stays outstanding and usable, because
  `passwd` must keep behaving exactly as it does now (FR-038). See Assumptions.
- **The store is missing, unreadable or corrupt**: `store unusable: <cause>` on standard error,
  exit 5, for both new commands, as for every existing command (FR-037).
- **A non-existent store path**: it is the empty store, so both new commands report
  `no such account` / 3.
- **The system clock moves backwards between issuing and using a token**: validity is judged
  against the system clock at the moment of use; no attempt is made to detect clock changes. See
  Assumptions.

## Requirements *(mandatory)*

### Functional Requirements

#### Invocation

- **FR-031**: The tool MUST accept two further command words, so that `COMMAND` is one of
  `register`, `login`, `unlock`, `passwd`, `delete`, `reset-token`, `reset`, each acting on the
  single store file identified by `--store PATH` exactly as the existing commands do.

#### `reset-token USERNAME [--ttl SECONDS]`

- **FR-032**: `reset-token USERNAME` MUST, when the account exists, create a password-reset token
  for that account, print the token and nothing else on a line of its own on standard output, write
  nothing to standard error, record the token in the store so that a later, separate invocation can
  honour it, and exit with status 0. It MUST succeed whether or not the account is locked. It MUST
  NOT change the account's stored password, failed-login tally or lock state. When a token is
  already outstanding for that account, the newly issued token MUST replace it, leaving exactly one
  valid token per account and making the replaced token invalid from that moment on.
- **FR-033**: `reset-token` MUST accept an optional `--ttl SECONDS` argument giving the token's
  lifetime in seconds, and MUST use 900 seconds when it is not given. `SECONDS` MUST be accepted
  only as a whole number of at least 1; a missing, non-numeric, zero, negative or fractional value,
  and `--ttl` supplied to any command other than `reset-token`, MUST each be treated as a malformed
  invocation under FR-040 — the usage line on standard error, exit status 2, and no store file
  created or modified.
- **FR-034**: `reset-token` MUST read nothing from standard input.
- **FR-034a**: Each issued token MUST be drawn from a cryptographically secure random source with
  at least 128 bits of entropy, MUST consist of printable ASCII characters with no whitespace so
  that it occupies exactly one line, and MUST differ from every other token the tool issues.
- **FR-034b**: The store MUST NOT contain any outstanding token in a form from which the token can
  be read back; a party who can read the store file MUST NOT be able to recover a token from it or
  to construct a value that `reset` will accept. Validation MUST work by comparing a one-way
  transformation of the presented token, and the comparison MUST be constant-time.

#### `reset USERNAME`

- **FR-035**: `reset USERNAME` MUST read exactly two lines from standard input, in order: the
  token, then the new password. Each line is its content up to and excluding the line break, with
  nothing stripped, so leading and trailing whitespace is significant in both. Input beyond those
  two lines MUST be ignored.
- **FR-036**: `reset USERNAME` MUST, when standard input ends before both lines are available,
  print exactly `missing password input` on standard error, exit with status 2, and leave the store
  unchanged.
- **FR-036a**: `reset USERNAME` MUST apply its checks in this order, the first failure deciding the
  outcome: the account does not exist → `no such account` on standard error, status 3; the
  presented token is not the account's outstanding token, or that token has already been used, or
  its lifetime has elapsed → `invalid token` on standard error, status 1; the new password is
  shorter than 12 characters → `password too short` on standard error, status 2.
- **FR-036b**: `reset USERNAME` MUST, on success, replace the account's password with the new
  password using freshly drawn derivation material, mark the token used so that no later invocation
  will accept it again, print exactly `password reset` on standard output, and exit with status 0.
  Afterwards the new password MUST be accepted for login and the previous password MUST be
  rejected.
- **FR-036c**: A token MUST be honoured at most once: after a successful `reset`, presenting the
  same token again MUST yield `invalid token` / 1 and MUST leave the password set by that successful
  reset in place.
- **FR-036d**: A token MUST be honoured only while its lifetime has not elapsed, measured from the
  moment it was issued against the system clock at the moment it is presented. Once `SECONDS`
  seconds have elapsed it MUST yield `invalid token` / 1.
- **FR-036e**: A `reset` that fails with `invalid token` (status 1) MUST leave the account's
  outstanding token exactly as it was, so a subsequent attempt with the correct token still
  succeeds, and MUST NOT change the stored password, the failed-login tally or the lock state.
- **FR-036f**: A `reset` that fails with `password too short` (status 2) MUST leave the account's
  outstanding token valid and usable, so that presenting the same token again with an acceptable
  password succeeds.
- **FR-036g**: Deleting an account MUST remove any outstanding token along with it, so that a token
  issued before a `delete` is never honoured — including for an account registered again under the
  same username, which MUST behave as an account that has never had a token issued.

#### Shared behaviour

- **FR-037**: Both new commands MUST follow the tool's existing global check order: argument
  parsing (status 2) → loading the store (status 5) → reading the command's required input lines
  (status 2) → the command's own checks. An unreadable or corrupt store MUST therefore produce
  `store unusable: <cause>` / 5 for both commands, and MUST NOT be treated as an empty store.
- **FR-038**: Neither new command MUST change an account's failed-login tally or lock state under
  any outcome, and no `reset-token` or `reset` MUST ever lock an account. A `reset` that fails for
  any reason MUST leave the store exactly as it was, except that FR-036e and FR-036f require the
  outstanding token to be preserved rather than spent. Every other command MUST keep its current
  effect on token state, which is none, except `delete` as required by FR-036g: in particular a
  successful `passwd` MUST leave an outstanding token outstanding.
- **FR-039**: Recording token state MUST NOT change the store's format marker and MUST NOT require
  a migration step: a store file written before this feature MUST load and behave exactly as it
  does now, and a store file holding token state MUST be read and rewritten without error by every
  command, preserving the token state of accounts the command does not alter. Token state that is
  present but malformed MUST be treated as a corrupt store under FR-029 (`store unusable: <cause>`
  / 5), never silently ignored.
- **FR-040**: The usage line printed for a malformed invocation MUST list the commands that exist
  and the optional argument, becoming exactly
  `usage: python -m accounts --store PATH {register|login|unlock|passwd|delete|reset-token|reset} USERNAME [--ttl SECONDS]`
  on standard error with exit status 2 and no store file created or modified. This is the only
  change to the output of any existing command.
- **FR-041**: Apart from the usage line of FR-040, every existing command MUST keep its current
  behaviour unchanged: the same accepted arguments, the same input lines read, the same messages on
  the same streams, the same exit statuses, and the same effect on the store. The existing
  automated suite MUST continue to pass, with changes limited to the literal usage string the
  assertions compare against.
- **FR-042**: The new messages MUST be exactly `password reset` on standard output for a successful
  `reset`, and `invalid token` on standard error for a refused token; `no such account`,
  `password too short`, `missing password input` and the `store unusable: ` prefix MUST be reused
  verbatim from the existing inventory rather than reworded. Both new commands MUST write their
  failure messages to standard error only and MUST write nothing to standard error on success.
- **FR-043**: The exit statuses of both new commands MUST stay inside the existing vocabulary with
  its existing meanings: 0 success, 1 a refused token (invalid credentials), 2 invalid input (a
  too-short new password, a malformed invocation, or missing input), 3 the account does not exist,
  5 the store is unusable. Status 4 MUST NOT be produced by either new command.
- **FR-044**: The token MUST be disclosed only on the standard output of the `reset-token`
  invocation that creates it. It MUST NOT be printed by any other command, MUST NOT appear in any
  error message, and MUST NOT be recoverable from the store afterwards (FR-034b); the tool MUST NOT
  transmit it anywhere or write it to any path other than the store file given by `--store`.

### Key Entities

- **Password-reset token**: a secret, single-use credential belonging to one account, standing in
  for that account's password for one `reset`. It is created by `reset-token`, disclosed once on
  standard output, and carries the moment it was issued and the lifetime chosen for it, from which
  its expiry follows. It is consumed by a successful `reset`, replaced by a later `reset-token` for
  the same account, and discarded with the account on `delete`. At most one is outstanding per
  account. It is recorded in the store only in a form from which the token itself cannot be read.
- **Account** (existing): gains optional reset-token state. Its password material, failed-login
  tally and lock state keep their current meanings and are untouched by this feature except for the
  password replacement a successful `reset` performs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-010**: Every existing automated test for the five existing commands passes unchanged, except
  the assertions that compare against the literal usage string, which are updated to the single new
  line of FR-040; no other existing assertion is weakened, deleted or rewritten.
- **SC-011**: A user who has forgotten their password regains access in three commands and with no
  setup step: one `reset-token` by an administrator, one `reset` by the user, one successful
  `login`.
- **SC-012**: A token is accepted at most once: across 100 issued tokens, 100 first uses succeed and
  100 second uses are refused with `invalid token` and status 1.
- **SC-013**: Expiry is honoured in both directions: a token presented within its lifetime is
  accepted, and the same token presented after its lifetime has elapsed is refused — asserted for
  the explicit short lifetime and for the 900-second default.
- **SC-014**: A token cannot be recovered from the store: after issuing tokens for accounts with
  known tokens, a search of the store file's bytes finds none of those tokens in any plain, base64
  or hexadecimal form, and feeding the store's recorded token material to `reset` as the token is
  refused.
- **SC-015**: Tokens are unpredictable: 1,000 tokens issued in succession are all distinct, and each
  is at least 22 characters of non-whitespace printable ASCII on one line, consistent with at least
  128 bits of entropy.
- **SC-016**: Every outcome of the two new commands is asserted exactly by at least one automated
  test: statuses 0, 1, 2, 3 and 5, and the messages `password reset`, `invalid token`,
  `no such account`, `password too short`, `missing password input`, the new usage line and the
  `store unusable: ` prefix, each on the stream where it belongs.
- **SC-017**: A failed `reset` costs the user nothing but the attempt: after a refused token the
  correct token still works, and after a too-short password the same token still works — verified
  for every ordering of one failure of each kind followed by a successful reset.
- **SC-018**: The new commands meet the existing performance contract: each completes within 1
  second for a store of up to 1,000 accounts, and the full automated suite still completes within 60
  seconds. `reset-token` performs no password derivation; `reset` performs exactly one, and only
  after the token has been accepted.
- **SC-019**: Store compatibility holds in both directions: a store file produced by the tool before
  this feature is loaded and used by all seven commands without error or migration, and a store file
  holding token state is read and rewritten by all seven commands with the token state of untouched
  accounts preserved byte-for-byte in meaning.

## Assumptions

Reasonable defaults chosen where the feature description did not say. Each is testable as written,
and each is a candidate to revisit in `/speckit-clarify`.

- **A reset does not unlock the account.** A successful `reset` replaces the password and leaves the
  lock state and failed-login tally alone, exactly as `passwd` does (FR-019). An account locked by
  five failures therefore still reports `account locked` / 4 after a reset until `unlock` is run.
  This follows the existing precedent and keeps lock management in the one command that owns it;
  the alternative — a reset that also unlocks — is the most plausible competing reading, since a
  forgotten password is a common route to a lockout. **This is the assumption most worth
  confirming.**
- **Issuing a token invalidates the previous one.** At most one token is outstanding per account
  (FR-032). Keeping a set of simultaneously valid tokens would add state the description does not
  ask for and widen the window in which any token works.
- **A wrong token does not disarm the outstanding token and is not rate-limited.** With at least 128
  bits of entropy (FR-034a), guessing is not a feasible attack, so no attempt counter, cooldown or
  lockout is introduced (FR-036e). This also keeps wrong-token attempts from becoming a way to deny
  a legitimate user their reset.
- **A malformed `--ttl` is a usage error, not a new message.** It is a fault in the shape of the
  invocation, which the tool already answers with the usage line and status 2 (FR-033); adding a
  distinct message for it would enlarge the documented inventory for no new information.
- **`--ttl` is located by scan, like `--store`.** It may appear before or after the positional
  arguments, and only the space-separated form `--ttl SECONDS` is accepted — `--ttl=SECONDS` is a
  usage error, matching how `--store` already behaves.
- **A too-short new password reuses `password too short`.** The description fixes status 2 but not
  the wording; reusing the existing message keeps one wording for one condition (FR-042).
- **Missing input for `reset` reuses `missing password input`.** The first of the two lines is a
  token rather than a password, but the condition is the existing one — input ended before a
  required line — and the existing message is reused rather than split in two (FR-036).
- **Expiry is judged against the system clock, with no clock-skew handling.** A token issued at time
  *t* with lifetime *s* is refused once the clock reads *t + s* or later. The tool neither detects
  nor compensates for the clock being changed between issuing and use; no network time source is
  consulted, as Principle I and the no-hidden-I/O constraint forbid it.
- **The lifetime boundary is exclusive.** A token presented at exactly *t + s* is expired.
- **The token is text on standard output and nothing more.** The tool prints it; passing it to the
  user is the administrator's job, done outside the tool. No mail, no file, no clipboard — the tool
  performs no I/O beyond the store path it is given (FR-044).
- **An outstanding token survives a `passwd`.** Security practice would often retire a reset token
  when the password changes by another route, but doing so would change what a successful `passwd`
  writes to the store, and the instruction that every existing command keep working exactly as it
  does now takes precedence (FR-038). The window is bounded by the token's lifetime.
- **Token state lives with the account record.** It is recorded inside the store as part of the
  account it belongs to, so that `delete` discards it with the account (FR-036g) and no change to
  the store's top-level shape or format marker is needed (FR-039). An account that has never had a
  token issued carries no token state at all, so a freshly registered account's record is exactly
  what it is today.
- **Usernames, password length and derivation rules are unchanged.** The 12-character minimum of
  FR-008 applies to the new password a `reset` sets, and the new material uses the same algorithm
  and current default cost as `register` and `passwd` (FR-026a).
- **The runtime stays standard-library-only** (Principle I), Python 3.11 or newer, with `src/` on
  `PYTHONPATH` for `python -m accounts` to resolve, exactly as the existing feature assumes.
