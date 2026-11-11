# Feature Specification: Local Account Manager CLI

**Feature Branch**: `001-accounts-cli`

**Created**: 2026-11-11

**Status**: Draft

**Input**: User description: "Build a command-line tool that manages local user accounts with passwords, kept in a single store file. Run it as `python -m accounts --store PATH COMMAND USERNAME`. The store is the file at PATH; it is created on first use and persists between runs. Passwords are never passed as command-line arguments: each command reads the passwords it needs from standard input, one per line. Commands: `register` (creates an account; username 3–32 chars of letters, digits and underscores; password at least 12 characters; invalid username or short password → exit 2; existing username → exit 3; prints `registered USERNAME`), `login` (prints `ok` on success; `invalid credentials` on stderr with exit 1 otherwise; after 5 failed attempts the account is locked and login prints `account locked` on stderr with exit 4 even for a correct password), `unlock` (unlocks the account and resets its failed-login count), `passwd` (reads current then new password; wrong current password → `invalid credentials` on stderr, exit 1; new password under 12 characters → exit 2), `delete` (reads the current password and deletes the account; wrong password → `invalid credentials` on stderr, exit 1). For `unlock`, `passwd` and `delete` a username that does not exist fails with exit status 3. Successful commands exit with status 0. Use Python 3.11 or newer and the standard library only, in a package named `accounts` under `src/`, runnable with `python -m accounts` when `src/` is on `PYTHONPATH`."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register an account and sign in with it (Priority: P1)

An operator working on a single machine needs to create a named account protected by a password, and later prove they know that password. They run the tool with a store file path, type the password on standard input (never on the command line, so it is not captured in shell history or process listings), and get a clear success message. On a later run — a separate invocation of the tool — they present the same password and the tool confirms it is correct. Presenting a wrong password yields a clear failure that a calling script can detect.

**Why this priority**: This is the irreducible core of the feature. Without creating an account and verifying a password, nothing else in the tool has meaning. Delivered alone, it is already useful: a script can gate an action on a correct password.

**Independent Test**: Run the register command against a fresh store path, then run the login command in a separate invocation with the same password and with a different password. Verify the success message, the failure message and stream, the exit statuses, and that the store file exists and is reused rather than recreated.

**Acceptance Scenarios**:

1. **Given** no store file exists at the chosen path, **When** the operator registers the username `alice` supplying a 21-character password, **Then** the tool prints `registered alice` on standard output, exits with status 0, and the store file now exists at that path.
2. **Given** `alice` was registered in an earlier invocation, **When** the operator logs in as `alice` with the same password, **Then** the tool prints `ok` on standard output and exits with status 0.
3. **Given** `alice` exists, **When** the operator logs in as `alice` with a different password, **Then** the tool prints `invalid credentials` on standard error and exits with status 1.
4. **Given** `alice` exists, **When** the operator registers `alice` again, **Then** the tool reports the conflict on standard error and exits with status 3, leaving the existing account and its password unchanged.
5. **Given** a fresh store, **When** the operator registers `bob` supplying the 5-character password `short`, **Then** the tool reports the rejection on standard error, exits with status 2, and no account named `bob` exists afterwards.
6. **Given** a fresh store, **When** the operator registers the username `ab` (too short) or `bad-name` (contains a character outside letters, digits and underscores) with a valid password, **Then** the tool reports the rejection on standard error, exits with status 2, and no such account exists afterwards.
7. **Given** a store containing several accounts, **When** the operator logs in as a username that was never registered, **Then** the tool prints `invalid credentials` on standard error and exits with status 1, giving no indication that the distinction between a wrong password and an unknown account exists.

---

### User Story 2 - Repeated wrong passwords lock the account until an operator unlocks it (Priority: P2)

Someone guessing passwords against the store must be stopped after a small number of tries. After five consecutive rejected login attempts, the account stops accepting logins altogether — a correct password no longer works — and says so distinctly, so a caller can tell "you got the password wrong" apart from "this account is closed to logins". An operator with access to the store clears the condition with a single command, after which the account behaves normally again and the tally of failures starts over.

**Why this priority**: Password verification without a limit on guesses is weak protection, so this is the first thing to add once Story 1 works. It is second because the tool is still useful without it.

**Independent Test**: Register an account, submit five wrong passwords in five separate invocations, then attempt a login with the correct password and observe the lock message and status; run the unlock command and confirm the correct password works again and that the failure tally restarted (five further wrong attempts are needed to lock it a second time).

**Acceptance Scenarios**:

1. **Given** a registered account with no prior failed logins, **When** four wrong-password logins are attempted, **Then** each prints `invalid credentials` on standard error with exit status 1, and a subsequent login with the correct password prints `ok` and exits 0.
2. **Given** a registered account with four recorded failed logins, **When** a fifth wrong-password login is attempted, **Then** that attempt prints `invalid credentials` on standard error and exits with status 1, and the account is locked from that point on.
3. **Given** a locked account, **When** a login is attempted with the correct password, **Then** the tool prints `account locked` on standard error and exits with status 4, and does not print `ok`.
4. **Given** a locked account, **When** a login is attempted with a wrong password, **Then** the tool prints `account locked` on standard error and exits with status 4.
5. **Given** a locked account, **When** the operator unlocks it, **Then** the tool exits with status 0, and a subsequent login with the correct password prints `ok` and exits 0.
6. **Given** an account that was just unlocked, **When** four wrong-password logins are attempted, **Then** the account is still not locked and the correct password still succeeds — showing the failure tally was reset by the unlock.
7. **Given** an account that is not locked and has some recorded failures, **When** the operator unlocks it, **Then** the tool exits with status 0 and the failure tally is cleared.
8. **Given** a store that has no account named `carol`, **When** the operator unlocks `carol`, **Then** the tool reports the unknown account on standard error and exits with status 3.
9. **Given** a registered account with three recorded failed logins, **When** a login succeeds with the correct password, **Then** the failure tally returns to zero, so five further consecutive wrong attempts are required to lock the account.

---

### User Story 3 - Change an account's password (Priority: P3)

The holder of an account needs to replace its password, proving they know the current one first. Both passwords are supplied on standard input in order — current, then new — so neither appears on the command line. Once changed, the old password no longer works and the new one does. A new password that is too weak to meet the length rule is refused, and the account keeps its existing password.

**Why this priority**: Rotation matters for any credential that lives on past its creation, but accounts are usable without it, so it follows the lockout protection.

**Independent Test**: Register an account, change its password with the correct current password, then confirm in separate invocations that logging in with the old password fails and with the new one succeeds; also attempt a change with a wrong current password and with a too-short new password and confirm the account's password is untouched in both cases.

**Acceptance Scenarios**:

1. **Given** a registered account, **When** the operator changes the password supplying the correct current password and a 12-or-more-character new password, **Then** the tool exits with status 0, a login with the new password prints `ok`, and a login with the old password prints `invalid credentials` with exit status 1.
2. **Given** a registered account, **When** the operator attempts a change supplying a wrong current password, **Then** the tool prints `invalid credentials` on standard error, exits with status 1, and the original password still works.
3. **Given** a registered account, **When** the operator attempts a change supplying the correct current password and an 11-character new password, **Then** the tool reports the rejection on standard error, exits with status 2, and the original password still works.
4. **Given** a store with no account named `dave`, **When** the operator attempts to change `dave`'s password, **Then** the tool reports the unknown account on standard error and exits with status 3.

---

### User Story 4 - Delete an account (Priority: P4)

The holder of an account needs to remove it from the store, proving they know its password first. After deletion the username is free to register again, and logging in as the deleted account behaves exactly as it would for a username that never existed.

**Why this priority**: Cleanup is the least urgent of the four journeys — the store is usable, and the earlier stories are demonstrable, without it.

**Independent Test**: Register an account, delete it with the correct password, then confirm a login attempt fails as for an unknown account and that the same username can be registered afresh; also attempt a deletion with a wrong password and confirm the account survives and still accepts its password.

**Acceptance Scenarios**:

1. **Given** a registered account, **When** the operator deletes it supplying the correct password, **Then** the tool exits with status 0 and a later login as that username prints `invalid credentials` on standard error with exit status 1.
2. **Given** a registered account, **When** the operator attempts a deletion supplying a wrong password, **Then** the tool prints `invalid credentials` on standard error, exits with status 1, and the account still accepts its correct password.
3. **Given** an account was deleted, **When** the operator registers the same username again with a new valid password, **Then** the tool prints `registered USERNAME` with exit status 0 and the new password works for login.
4. **Given** a store with no account named `erin`, **When** the operator attempts to delete `erin`, **Then** the tool reports the unknown account on standard error and exits with status 3.
5. **Given** a store containing two accounts, **When** one is deleted, **Then** the other account is unaffected and still accepts its password.

---

### Edge Cases

- **Store absent on first use**: a command is run against a path where no file exists. `register` creates the store; commands that need an existing account (`login`, `unlock`, `passwd`, `delete`) treat the store as empty and apply the unknown-account rules (status 1 for `login`, status 3 for the others).
- **Store path not usable**: the path names a directory, sits in a missing parent directory, or cannot be read or written because of permissions. The tool reports the problem on standard error and exits non-zero without claiming success.
- **Store content unreadable**: the file exists but its content is not a valid store (truncated or corrupted). The tool reports this distinctly on standard error and exits non-zero rather than silently treating the store as empty and losing accounts.
- **Missing password input**: standard input is empty or ends before all the lines a command needs (notably `passwd`, which needs two). The tool reports the missing input on standard error and exits with status 2; the store is not modified.
- **Password boundary lengths**: exactly 12 characters is accepted; exactly 11 is rejected. Username boundaries: 3 and 32 characters accepted, 2 and 33 rejected.
- **Passwords with spaces or unusual characters**: a password may contain spaces and any characters other than a line break (the example `correct horse battery` contains spaces); only the line break terminates it. An empty line is a password of length 0 and is therefore rejected on the length rule.
- **Extra input after the needed lines**: additional lines on standard input beyond what a command needs are ignored, not treated as an error.
- **Username case**: `Alice` and `alice` are different accounts.
- **Two rules broken at once**: `register` with both an invalid username and a short password exits 2; `register` of an existing username with a short password exits 2 (the format rules are applied before the existence check).
- **Locked account, non-login commands**: the lock gates `login` only. `passwd` and `delete` on a locked account behave normally when the correct password is given; a successful `passwd` does not by itself unlock the account.
- **Wrong password on `passwd` or `delete`**: counts as a failure of that command only — it does not advance the failed-login tally and so cannot lock the account.
- **`unlock` needs no password**: it reads nothing from standard input and succeeds whether or not the account is currently locked.
- **No account is identified**: the command word is missing, unknown, or given without a username, or `--store` is omitted. The tool reports usage on standard error and exits with status 2.

## Requirements *(mandatory)*

### Functional Requirements

**Invocation and input handling**

- **FR-001**: The tool MUST be invocable as `python -m accounts --store PATH COMMAND USERNAME`, where `COMMAND` is one of `register`, `login`, `unlock`, `passwd`, `delete`, and MUST act on the single store file identified by `PATH`.
- **FR-002**: The tool MUST create the store file on first use and MUST read back the accounts it recorded in earlier, separate invocations against the same path.
- **FR-003**: The tool MUST NOT accept a password as a command-line argument; it MUST read each password it needs from standard input as one line, terminated by a line break or end of input, taking the line content excluding the line break as the password.
- **FR-004**: The tool MUST read exactly the passwords each command needs, in this order: `register` one (new password), `login` one (password), `passwd` two (current password, then new password), `delete` one (current password), `unlock` none. Input beyond those lines MUST be ignored.
- **FR-005**: When standard input ends before a command's required password lines are available, the tool MUST report the missing input on standard error, exit with status 2, and leave the store unchanged.
- **FR-006**: When the command word is missing or unrecognized, the username is missing, or `--store` is missing, the tool MUST report usage on standard error and exit with status 2, and MUST NOT create or modify a store file.

**Validation rules**

- **FR-007**: A username MUST be accepted for registration only when it is 3 to 32 characters long inclusive and consists solely of letters (`A`–`Z`, `a`–`z`), digits (`0`–`9`) and underscores; usernames MUST be treated as case-sensitive and MUST be compared exactly.
- **FR-008**: A password MUST be accepted only when it is at least 12 characters long; there MUST be no maximum length and no character-class restriction.

**`register`**

- **FR-009**: `register USERNAME` MUST, on success, create the account with the supplied password, print exactly `registered USERNAME` on standard output, and exit with status 0.
- **FR-010**: `register` MUST reject an invalid username (FR-007) or a too-short password (FR-008) with a message on standard error and exit status 2, creating no account; the username and password rules MUST be applied before the duplicate check, so a request that breaks both exits 2.
- **FR-011**: `register` MUST reject a username that already exists in the store with a message on standard error and exit status 3, leaving the existing account's password, failure tally and lock state unchanged.

**`login`**

- **FR-012**: `login USERNAME` MUST, when the account exists, is not locked, and the supplied password is correct, print exactly `ok` on standard output, exit with status 0, and reset the account's failed-login tally to zero.
- **FR-013**: `login USERNAME` MUST, when the account exists, is not locked, and the supplied password is incorrect, print exactly `invalid credentials` on standard error, exit with status 1, and increase the account's failed-login tally by one.
- **FR-014**: `login USERNAME` MUST, when no such account exists, print exactly `invalid credentials` on standard error and exit with status 1, producing output and status indistinguishable from an existing account with a wrong password.
- **FR-015**: An account MUST become locked once its failed-login tally reaches 5, and MUST remain locked until unlocked; the fifth consecutive failing attempt itself MUST still be reported as `invalid credentials` with exit status 1 (FR-013).
- **FR-016**: `login USERNAME` on a locked account MUST print exactly `account locked` on standard error and exit with status 4, whether the supplied password is correct or incorrect, MUST NOT print `ok`, and MUST NOT change the account's stored password, failure tally or lock state.

**`unlock`**

- **FR-017**: `unlock USERNAME` MUST clear the account's locked state and reset its failed-login tally to zero, exiting with status 0; it MUST succeed whether or not the account was locked and MUST require no password input.
- **FR-018**: `unlock USERNAME` MUST, when no such account exists, report the unknown account on standard error and exit with status 3.

**`passwd`**

- **FR-019**: `passwd USERNAME` MUST, on success, replace the account's password with the new password, exit with status 0, and leave the account's lock state and failure tally unchanged; afterwards the new password MUST be accepted for login and the previous password MUST be rejected.
- **FR-020**: `passwd USERNAME` MUST, when the supplied current password is incorrect, print exactly `invalid credentials` on standard error, exit with status 1, leave the stored password unchanged, and MUST NOT advance the failed-login tally.
- **FR-021**: `passwd USERNAME` MUST, when the new password is shorter than 12 characters, report the rejection on standard error, exit with status 2, and leave the stored password unchanged; the current password MUST be verified before the new password is validated, so a request with both a wrong current password and a too-short new password exits 1.
- **FR-022**: `passwd USERNAME` MUST, when no such account exists, report the unknown account on standard error and exit with status 3, without consuming the outcome of any password check.

**`delete`**

- **FR-023**: `delete USERNAME` MUST, on success, remove the account from the store and exit with status 0, leaving every other account in the store unchanged; afterwards the username MUST be available for registration again and MUST behave as an unknown account (FR-014, FR-018, FR-022).
- **FR-024**: `delete USERNAME` MUST, when the supplied password is incorrect, print exactly `invalid credentials` on standard error, exit with status 1, retain the account unchanged, and MUST NOT advance the failed-login tally.
- **FR-025**: `delete USERNAME` MUST, when no such account exists, report the unknown account on standard error and exit with status 3.

**Store integrity and output discipline**

- **FR-026**: The store MUST NOT contain any account's password in a form from which the password can be read back; verification MUST work by comparing a one-way transformation of the supplied password, with a distinct per-account random salt so that two accounts sharing a password do not share stored material.
- **FR-027**: Every failing command MUST write its message to standard error and MUST NOT write the message to standard output; successful commands MUST write nothing to standard error.
- **FR-028**: A command that fails for any reason MUST leave the store's accounts, passwords, failure tallies and lock states exactly as they were, except for the failed-login tally changes required by FR-013 and FR-015.
- **FR-029**: When the store file cannot be read or written, or its content is not a valid store, the tool MUST report the specific problem on standard error and exit with status 5, and MUST NOT treat an unreadable or corrupt store as an empty store.
- **FR-030**: Every successful command MUST exit with status 0, and the exit statuses MUST be used with exactly these meanings: 0 success, 1 invalid credentials, 2 invalid input (username, password length, usage or missing input), 3 account conflict (already exists, or does not exist), 4 account locked, 5 store unusable.

### Key Entities

- **Store**: the single file at the given path holding all accounts; created on first use, rewritten in place as accounts change, and readable by later invocations. Holds no information other than the account records. Readable and writable only by the user who created it.
- **Account**: one named local user. Attributes: the username (unique within the store, case-sensitive, 3–32 characters of letters, digits and underscores); the non-recoverable verification material for the current password together with its per-account salt; the count of consecutive failed login attempts since the last successful login or unlock; and whether the account is locked against logins.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the 30 functional requirements is covered by at least one automated test that names the requirement it verifies, and the full suite passes with zero failures.
- **SC-002**: Every documented exit status (0, 1, 2, 3, 4, 5) is produced and asserted by at least one automated test, and every documented message (`registered USERNAME`, `ok`, `invalid credentials`, `account locked`) is asserted exactly, on the stream where it belongs.
- **SC-003**: An operator who has never used the tool can create an account and verify its password in two commands, with no setup step beyond choosing a store path.
- **SC-004**: Accounts written by one invocation are readable by every later invocation against the same path: a sequence of 50 registrations across 50 separate runs ends with all 50 accounts able to log in successfully.
- **SC-005**: No password supplied to the tool can be found in the store file: after registering accounts with known passwords, a search of the store's bytes for any of those passwords finds no match, and two accounts registered with the same password have different stored material.
- **SC-006**: Five consecutive wrong passwords always lock an account, and after a lock no password — correct or not — produces a successful login until `unlock` is run; this holds for every ordering of correct and wrong attempts that includes five consecutive failures.
- **SC-007**: No password is ever accepted as or visible in a command-line argument: the tool's accepted arguments are the store path, command word and username only, and a password placed where an argument is expected is never used as a password.
- **SC-008**: Every failed command leaves the store in the state it had before the command, apart from the failed-login tally, verified by comparing the behaviour of all accounts before and after each failure path.

## Assumptions

The feature description left the following unstated; these are the reasonable defaults adopted, and each is reflected in the requirements above.

- **Unknown username on `login` reports invalid credentials (status 1), not status 3.** The description assigns status 3 to a missing account for `unlock`, `passwd` and `delete` only, and deliberately omits `login`; treating an unknown account as a credential failure also avoids revealing which usernames exist. (FR-014)
- **A successful login resets the failed-login tally.** The five failures that lock an account are therefore five *consecutive* failures. (FR-012, FR-015)
- **The fifth failing attempt reports `invalid credentials`, not `account locked`.** The account is locked from the next login onward. (FR-015)
- **A login attempt on a locked account changes nothing.** The lock is checked before the password, so no further failures are recorded and the lock does not deepen. (FR-016)
- **The lock gates `login` only.** `passwd` and `delete` work on a locked account when the correct password is given, and neither advances or resets the failed-login tally. A successful `passwd` does not unlock the account; only `unlock` does. (FR-019, FR-020, FR-024)
- **`unlock` requires no password and is idempotent.** The description lists the passwords each command reads and names none for `unlock`; unlocking an already-unlocked account succeeds and clears its tally. (FR-017)
- **The username format rules are a registration-time constraint.** Other commands do not reject a malformed username as invalid input; a name that could never have been registered simply does not exist, so the unknown-account rules apply. (FR-007)
- **Rule precedence within a command is fixed** so each outcome is unambiguous: `register` applies format rules (2) before the duplicate check (3); `passwd` applies the existence check (3), then the current-password check (1), then the new-password length check (2); `login` applies the existence check (1), then the lock check (4), then the password check (1). (FR-010, FR-021, FR-022)
- **Store unusable is a distinct exit status 5.** Statuses 0–4 are assigned by the description to specific account outcomes, so a path, permission or corruption problem — which is neither a credential nor an account-state outcome — needs its own non-zero status rather than being folded into one of them. (FR-029)
- **Lengths are counted in characters, not bytes.** A 12-character password of non-ASCII characters is accepted even though it occupies more than 12 bytes. (FR-008)
- **Passwords may contain anything except a line break**, including spaces and leading or trailing whitespace, which is preserved rather than trimmed. The line break itself is not part of the password. (FR-003)
- **Single operator, one invocation at a time.** Concurrent invocations against the same store are out of scope; the store is written so that an ordinary completed write leaves it readable, but no locking between simultaneous processes is provided.
- **No account listing, no password recovery, no lock expiry.** There is no command to enumerate accounts, no way to recover a forgotten password, and a lock never times out — an account stays locked until `unlock` is run. These are outside the described command set.
- **Store file permissions are owner-only** (readable and writable by the creating user alone), because the file holds credential verification material.
- **Environment**: Python 3.11 or newer, standard library only, with the `accounts` package under `src/` so that `python -m accounts` runs it when `src/` is on `PYTHONPATH`. This is the only stated implementation constraint and is carried here because it is part of how the tool is invoked.
