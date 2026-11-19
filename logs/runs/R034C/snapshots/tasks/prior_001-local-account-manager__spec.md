# Feature Specification: Local Account Manager

**Feature Branch**: `001-local-account-manager`

**Created**: 2026-11-16

**Status**: Draft

**Input**: User description: "Build a command-line tool that manages local user accounts with passwords, kept in a single store file. Run it as `python -m accounts --store PATH COMMAND USERNAME`. The store is the file at PATH; it is created on first use and persists between runs. Passwords are never passed as command-line arguments: each command reads the passwords it needs from standard input, one per line. Commands: register, login (with lockout after 5 failed attempts), unlock, passwd, delete. Exit statuses: 0 success, 1 invalid credentials, 2 invalid input, 3 account-existence conflict, 4 account locked."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register an account and sign in (Priority: P1)

An operator of a single machine needs to create a named local account protected by a password, and later prove they hold that password. They invoke the tool with a store file path, a command, and a username; the password itself is typed (or piped) on standard input so it never appears in the command line, shell history, or process list. The account survives between invocations because it is kept in the store file.

**Why this priority**: Without account creation, credential verification, and persistence there is no product. This story alone is a usable MVP: an operator can create an account and check a password against it.

**Independent Test**: Register a new account into a fresh store path, then run a login with the same password (expect success output and exit status 0) and a login with a different password (expect the credential-failure message on standard error and exit status 1). Re-run the login in a separate process to confirm the account persisted.

**Acceptance Scenarios**:

1. **Given** a store path that does not yet exist, **When** the operator registers `alice` supplying the password `correct horse battery` on standard input, **Then** the store file is created, `registered alice` is written to standard output, and the exit status is 0.
2. **Given** `alice` is registered with `correct horse battery`, **When** a later, separate invocation logs in as `alice` with `correct horse battery`, **Then** `ok` is written to standard output and the exit status is 0.
3. **Given** `alice` is registered, **When** a login supplies `wrong password!!`, **Then** `invalid credentials` is written to standard error, nothing is written to standard output, and the exit status is 1.
4. **Given** a store containing accounts, **When** the operator registers `bob` with the password `short`, **Then** a diagnostic naming the password-length rule is written to standard error, no account is created, and the exit status is 2.
5. **Given** a store containing `alice`, **When** the operator registers `alice` again with any valid password, **Then** a diagnostic is written to standard error, the existing account and its password are unchanged, and the exit status is 3.
6. **Given** any store, **When** the operator registers the username `ab` (too short) or `bad-name` (contains a character outside letters, digits, and underscore), **Then** a diagnostic naming the username rule is written to standard error, no account is created, and the exit status is 2.

---

### User Story 2 - Lock out password guessing, and recover from a lockout (Priority: P2)

Because the store sits on a machine where anyone with shell access can run the tool repeatedly, an account stops accepting logins after a run of failed attempts. An administrator who controls the store can clear that state so the legitimate holder regains access.

**Why this priority**: Credential verification without an attempt limit lets an attacker grind through guesses; the limit is the second-most valuable behaviour after verification itself. Unlock ships with it because a lockout with no recovery path is a self-inflicted denial of service.

**Independent Test**: Register an account, submit five wrong passwords, then submit the correct password and confirm the lock message and exit status 4. Run unlock, then confirm the correct password logs in again with exit status 0.

**Acceptance Scenarios**:

1. **Given** a freshly registered `alice`, **When** four logins in a row supply a wrong password, **Then** each writes `invalid credentials` to standard error with exit status 1, and a fifth login with the correct password still succeeds with `ok` and exit status 0.
2. **Given** a freshly registered `alice`, **When** five logins in a row supply a wrong password, **Then** the fifth writes `invalid credentials` with exit status 1 and the account becomes locked.
3. **Given** `alice` is locked, **When** a login supplies the *correct* password, **Then** `account locked` is written to standard error and the exit status is 4.
4. **Given** `alice` is locked, **When** a login supplies a wrong password, **Then** `account locked` is written to standard error and the exit status is 4.
5. **Given** `alice` is locked, **When** the operator runs unlock for `alice`, **Then** the exit status is 0 and a subsequent login with the correct password prints `ok` with exit status 0.
6. **Given** `alice` has three recorded failed attempts and is not locked, **When** a login with the correct password succeeds, **Then** the recorded failure count returns to zero, so that five further *non-consecutive* failures are required to lock the account.
7. **Given** a store with no account named `carol`, **When** the operator runs unlock for `carol`, **Then** a diagnostic is written to standard error and the exit status is 3.

---

### User Story 3 - Change a password (Priority: P3)

The holder of an account can replace its password by proving knowledge of the current one, so a password suspected of exposure can be rotated without destroying and recreating the account.

**Why this priority**: Rotation is expected of any credential store, but an account remains usable without it.

**Independent Test**: Register an account, change its password supplying the current password then a new one, then confirm the new password logs in and the old one does not.

**Acceptance Scenarios**:

1. **Given** `alice` registered with `correct horse battery`, **When** the operator runs the password change supplying `correct horse battery` then `new longer secret`, **Then** the exit status is 0, a login with `new longer secret` prints `ok`, and a login with `correct horse battery` fails with exit status 1.
2. **Given** `alice` registered with `correct horse battery`, **When** the password change supplies a wrong current password, **Then** `invalid credentials` is written to standard error, the exit status is 1, and the original password still logs in.
3. **Given** `alice` registered with a valid password, **When** the password change supplies the correct current password and a new password of fewer than 12 characters, **Then** a diagnostic naming the length rule is written to standard error, the exit status is 2, and the original password still logs in.
4. **Given** a store with no account named `carol`, **When** the operator runs the password change for `carol`, **Then** a diagnostic is written to standard error and the exit status is 3.

---

### User Story 4 - Delete an account (Priority: P4)

The holder of an account can remove it from the store by proving knowledge of its password, so a store does not accumulate accounts that are no longer wanted.

**Why this priority**: Useful hygiene, and the smallest slice of value; everything else works without it.

**Independent Test**: Register an account, delete it supplying the correct password, and confirm a later login for that username fails. Separately confirm a delete with a wrong password leaves the account intact.

**Acceptance Scenarios**:

1. **Given** `alice` registered with `correct horse battery`, **When** the operator deletes `alice` supplying `correct horse battery`, **Then** the exit status is 0 and a later login as `alice` with that password fails with `invalid credentials` and exit status 1.
2. **Given** `alice` registered, **When** the operator deletes `alice` supplying a wrong password, **Then** `invalid credentials` is written to standard error, the exit status is 1, and `alice` can still log in with the correct password.
3. **Given** a store with no account named `carol`, **When** the operator deletes `carol`, **Then** a diagnostic is written to standard error and the exit status is 3.
4. **Given** a store containing `alice` and `bob`, **When** `alice` is deleted, **Then** `bob` and `bob`'s password and failure state are unaffected.

---

### Edge Cases

- **Unknown username on login**: A login for a username that is not in the store reports `invalid credentials` with exit status 1 — the same message and status as a wrong password — so the tool does not reveal which usernames exist. (Unlock, password change, and delete do distinguish the case, with exit status 3, because the user description requires it.)
- **No password on standard input**: A command that needs a password but reaches end of input without reading a line fails with a diagnostic and exit status 2, rather than treating the absent password as empty.
- **Only one password supplied to the password change**: The change needs two lines (current, then new); reaching end of input after the first fails with a diagnostic and exit status 2, and the account is unchanged.
- **Password containing spaces or non-ASCII characters**: Accepted and compared exactly; only the single terminating newline is stripped, so leading and trailing spaces are part of the password. Length is counted in characters, not bytes.
- **Extra lines on standard input**: Lines beyond those a command needs are ignored, so piping a file with a trailing blank line works.
- **Boundary lengths**: A username of exactly 3 and of exactly 32 characters is valid; 2 and 33 are rejected. A password of exactly 12 characters is valid; 11 is rejected.
- **Invalid-format username on a command other than register**: Treated as a username that does not exist — exit status 1 for login, exit status 3 for unlock, password change, and delete — rather than as a usage error.
- **Lockout and the non-login commands**: Being locked blocks login only. An operator who knows the password can still change it or delete the account while locked; a successful password change does not itself clear the lock (only unlock does).
- **Failed password change or delete attempts**: These do not count toward the five failed *logins*, so they cannot lock an account.
- **Missing store file or empty store**: A store path that does not exist behaves as a store with no accounts — register creates it; login reports `invalid credentials` (status 1); unlock, change, and delete report status 3. The file is created only when an account is actually written.
- **Unreadable or malformed store file**: A store path that exists but cannot be read, or whose contents are not recognizable as a store, fails with a diagnostic naming the file and a non-zero exit status, rather than being silently replaced or treated as empty.
- **Unusable store path**: A store path in a directory that does not exist, or that is not writable, fails with a diagnostic and a non-zero exit status.
- **Usage errors**: A missing store option, a missing or unknown command, a missing username, or extra positional arguments produce a usage diagnostic on standard error and exit status 2.
- **Interrupted write**: A failure partway through saving the store leaves the previous contents intact rather than a truncated store.

## Requirements *(mandatory)*

### Functional Requirements

**Invocation and the store**

- **FR-001**: The tool MUST be invoked as a single command taking a store-path option, a command name, and a username, and MUST act only on the store file at the given path.
- **FR-002**: The store MUST be created on first successful account creation if it does not exist, and MUST persist all accounts, their password verifiers, their failed-login counts, and their lock states between invocations.
- **FR-003**: The tool MUST NOT accept any password as a command-line argument. Each command MUST read the passwords it needs from standard input, one per line, in the order documented for that command (for the password change: current password first, then new password).
- **FR-004**: The tool MUST write command results to standard output and all diagnostics to standard error, and MUST NOT write diagnostics to standard output or results to standard error.
- **FR-005**: The tool MUST exit 0 on success and MUST use exactly these non-zero statuses: 1 for a rejected credential, 2 for invalid input or usage, 3 for an account that already exists or does not exist, 4 for a locked account.
- **FR-006**: A successful command's effect on the store MUST be durable at the moment the tool exits with status 0; a command that exits non-zero MUST leave the store's account data unchanged, except that a failed login MUST persist its incremented failure count and any resulting lock.
- **FR-007**: A store file that exists but cannot be read or is not recognizable as a store MUST produce a diagnostic naming the file and a non-zero exit status; the tool MUST NOT overwrite it, treat it as empty, or continue.
- **FR-008**: Saving the store MUST either fully apply the change or leave the prior contents intact.

**Account creation**

- **FR-009**: Registration MUST create the named account with the supplied password, write `registered USERNAME` to standard output, and exit 0.
- **FR-010**: A username MUST be accepted only if it is 3 to 32 characters long and consists solely of letters, digits, and underscores; a username failing this rule MUST be rejected at registration with a diagnostic and exit status 2.
- **FR-011**: A password MUST be accepted only if it is at least 12 characters long; a shorter password MUST be rejected with a diagnostic and exit status 2.
- **FR-012**: Registering a username already present in the store MUST be rejected with a diagnostic and exit status 3, and MUST NOT modify the existing account.
- **FR-013**: When both the username and the password are invalid, the command MUST still exit 2; when the username is invalid and the account also already exists, the command MUST exit 2 (input validation precedes existence checks).

**Credential verification**

- **FR-014**: A login supplying the account's current password for an unlocked account MUST write `ok` to standard output and exit 0.
- **FR-015**: A login supplying any other password for an unlocked, existing account MUST write exactly `invalid credentials` to standard error and exit 1.
- **FR-016**: A login for a username not present in the store MUST write exactly `invalid credentials` to standard error and exit 1, and MUST NOT reveal that the account is absent.
- **FR-017**: Password comparison MUST be exact and case-sensitive over the full password, including spaces and non-ASCII characters; only the terminating newline of the input line MUST be excluded.
- **FR-018**: A command that requires a password but reaches end of input before reading it MUST write a diagnostic and exit 2, and MUST NOT treat the missing password as an empty password.

**Lockout and unlock**

- **FR-019**: Each failed login MUST increase the account's recorded failed-login count by one; once that count reaches 5, the account MUST be locked.
- **FR-020**: A login to a locked account MUST write exactly `account locked` to standard error and exit 4, whether or not the password supplied is correct, and MUST NOT write `ok`.
- **FR-021**: A successful login MUST reset the account's failed-login count to zero.
- **FR-022**: Unlock MUST clear the lock and reset the failed-login count to zero for an existing account and exit 0; it MUST NOT read a password, and running it on an account that is not locked MUST also exit 0 and leave the account usable.
- **FR-023**: Only unlock may clear a lock; no other command may clear it, and no command other than login may set it.
- **FR-024**: A failed password-change or delete attempt MUST NOT change the failed-login count and MUST NOT lock the account.
- **FR-025**: A locked account MUST still accept a password change and a delete from a caller supplying the correct current password.

**Password change**

- **FR-026**: The password change MUST read the current password and then the new password, replace the stored password only if the current password is correct and the new password satisfies FR-011, and exit 0.
- **FR-027**: A password change supplying an incorrect current password MUST write exactly `invalid credentials` to standard error, exit 1, and leave the stored password unchanged.
- **FR-028**: A password change whose new password is shorter than 12 characters MUST write a diagnostic, exit 2, and leave the stored password unchanged; this check MUST be reported only after the current password has been accepted, so that it never reveals whether the current password was right.
- **FR-029**: After a successful password change, the new password MUST verify on login and the previous password MUST NOT.

**Deletion**

- **FR-030**: Delete MUST read the current password and, if it is correct, remove the account and all of its state from the store and exit 0.
- **FR-031**: A delete supplying an incorrect password MUST write exactly `invalid credentials` to standard error, exit 1, and retain the account unchanged.
- **FR-032**: After a successful delete, a login for that username MUST fail per FR-016, and the username MUST be available for registration again.
- **FR-033**: Removing one account MUST NOT alter any other account's password, failed-login count, or lock state.

**Existence checks and usage**

- **FR-034**: Unlock, password change, and delete for a username not present in the store MUST write a diagnostic and exit 3; for these commands the existence check MUST precede reading any password from standard input.
- **FR-035**: A missing store option, a missing command, an unknown command, a missing username, or unexpected extra arguments MUST produce a usage diagnostic on standard error and exit 2.

**Secret handling**

- **FR-036**: The store MUST NOT contain any account's password in a form from which the password can be read back; verification MUST rely on a one-way transformation of the password with a distinct, per-account random salt, so that two accounts with the same password have different stored verifiers.
- **FR-037**: Diagnostics and results MUST NOT include any password or stored verifier.
- **FR-038**: A newly created store file MUST be readable and writable only by its owner.

### Key Entities *(include if data involved)*

- **Store**: The single file at the operator-supplied path holding every account. Created on first account creation, read at the start of each command, rewritten when a command changes it. It is the only persistent state the tool keeps.
- **Account**: One named local identity in the store. Attributes: the username (unique within the store, 3–32 characters of letters, digits, and underscores); a password verifier plus the per-account salt it was derived with; the count of consecutive failed logins since the last success or unlock; and whether the account is locked.
- **Password**: A caller-supplied secret of at least 12 characters, received only on standard input, never stored or printed, and compared only against an account's verifier.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every functional requirement above is covered by at least one automated test that fails if the requirement is unmet — 38 of 38 requirements mapped, with no requirement verified by manual inspection alone.
- **SC-002**: All four worked examples in the feature description reproduce exactly: the stated standard-output text, the stated standard-error text, and the stated exit status, with no extra output on either stream.
- **SC-003**: A wrong password never produces exit status 0 and never produces the success output, across 100% of tested cases, including locked accounts, absent accounts, and accounts whose password was just changed.
- **SC-004**: Five consecutive wrong passwords lock an account and the sixth attempt with the correct password reports the lock with exit status 4; four wrong passwords followed by the correct one succeeds. Both sequences pass on every run.
- **SC-005**: Account data written by one invocation is readable by a later, separate invocation in 100% of tested cases, including after a password change, an unlock, and a delete.
- **SC-006**: No password supplied in testing can be found anywhere in the store file's bytes, and no password appears in any command line the tool is invoked with.
- **SC-007**: Each command completes in under 1 second on a store holding 1,000 accounts, so interactive use never feels delayed.
- **SC-008**: Every failure path produces a diagnostic on standard error that names the specific rule or condition that failed; no failure exits non-zero in silence.

## Assumptions

Each assumption below is a reasonable default chosen where the feature description was silent; all are observable and testable as written into the requirements above.

- **Unknown username on login is reported as a credential failure (exit 1), not as a missing account (exit 3)**. The description fixes exit status 3 for unlock, password change, and delete only, and deliberately omits login; reporting `invalid credentials` avoids turning login into a username-enumeration oracle.
- **A successful login resets the failed-login count**, so lockout follows 5 *consecutive* failures. The alternative — a lifetime counter — would eventually lock every long-lived account.
- **The fifth consecutive failure reports `invalid credentials` with exit status 1** and locks the account; the lock is reported from the next login onward. The description defines the lock as a state entered "after 5 failed login attempts".
- **The lock gates login only.** A caller with the correct password may still change the password or delete a locked account, and a password change does not clear the lock. The description attaches the lock behaviour solely to logging in, and unlock is named as the operation that clears it.
- **Failed password-change and delete attempts do not count as failed logins**, so they cannot lock an account; the count is specified in terms of failed *logins*.
- **Unlock reads nothing from standard input** and requires no password — it is an administrative operation available to whoever can run the tool against the store, which is also whoever could edit the store file directly.
- **A username whose format is invalid is simply a username that does not exist** for commands other than register, so no second class of validation error appears on login, unlock, change, or delete.
- **Passwords are read as single lines**, with the terminating newline removed and all other characters preserved, and length is measured in characters; extra input lines are ignored.
- **Password strength beyond the 12-character minimum is not enforced** — no character-class, dictionary, or reuse rules — and a new password identical to the current one is accepted. Only the stated minimum was specified.
- **The store's on-disk format is unspecified by this document** beyond FR-036's secret-handling constraint; it is a planning decision, and the store is not treated as a public interface to be read by other tools.
- **Single-process use is assumed.** Concurrent invocations against the same store are out of scope; no locking or merge behaviour is specified, and a last-writer-wins outcome under concurrency is not a defect against this spec.
- **There is no account listing, no account enumeration, no password reset without the current password, no password expiry, no time-based lockout release, and no audit log.** None were requested, and each would need its own requirements.
- **Protection is against guessing through this tool, not against an attacker holding the store file.** A party who can read or write the store can delete or replace accounts; the file's owner-only permissions and the one-way verifiers limit casual exposure, not a determined local attacker with filesystem access.
- **Implementation constraints recorded for planning, not restated as behavioural requirements**: the user description requires Python 3.11 or newer, the standard library only, and a package named `accounts` under `src/` runnable as `python -m accounts` with `src/` on `PYTHONPATH`. These belong to `plan.md`'s technical context; they are noted here only so planning does not lose them.
