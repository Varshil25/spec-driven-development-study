# Phase 0 Research: Local Account Manager

**Feature**: `001-local-account-manager` | **Date**: 2026-11-16

The Technical Context in [plan.md](./plan.md) contains no `NEEDS CLARIFICATION` markers: the
user input fixed the language (Python 3.11+), the dependency policy (standard library only),
the test framework (pytest), and the interface (taken exactly from the spec). The open
questions were therefore not *unknowns in the spec* but *choices the spec deliberately left to
planning* — chiefly the store format, the one-way password transformation, how usage errors
reach exit status 2, and which of the four permitted statuses a store-file failure uses.

Each decision below is recorded as Decision / Rationale / Alternatives considered.

---

## R-01: Store file format — JSON via `json`

**Decision**: A single UTF-8 JSON object, written with `json.dump(..., indent=2, sort_keys=True)`
and a trailing newline. Top level: `{"version": 1, "accounts": {<username>: <record>}}`. Schema
in [data-model.md](./data-model.md).

**Rationale**: `json` is stdlib (Principle I), the format is self-delimiting so a truncated or
hand-edited file reliably fails to parse (which FR-007 needs), and a username-keyed object
makes lookup, insert, and delete one dict operation each — no index to maintain and no
ordering to preserve. Sorted keys and an indent make the file diffable and make SC-006's "no
password appears in the store's bytes" check readable by eye as well as by test. `version` is
not speculative generality: a strict `version == 1` check is one of the ways a foreign file is
rejected under FR-007.

**Alternatives considered**:
- **`sqlite3`**: stdlib and transactional, so FR-008 would come free. Rejected under Principle
  IV — it adds schema DDL, a connection lifecycle, and migration thinking for a store the spec
  says is read whole and rewritten whole, and a binary file makes the SC-006 byte check harder
  to inspect.
- **`configparser` / INI**: no clean representation for the boolean and integer fields, and
  values containing `%` or `=` need escaping rules the project would have to own.
- **`csv` or one record per line**: lookup becomes a scan, and a half-written final line parses
  as a valid shorter store — exactly the silent-truncation outcome FR-008 forbids.
- **`pickle` / `shelve`**: loading an attacker-supplied store would execute arbitrary code; the
  store is explicitly a file anyone with shell access can edit.

---

## R-02: Password verifier — PBKDF2-HMAC-SHA256, 600,000 iterations, 16-byte salt, 32-byte key

**Decision**: `hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000, dklen=32)`
with `salt = secrets.token_bytes(16)` generated per account at registration and regenerated on
every password change. Salt and verifier are stored base64-encoded (`base64.b64encode`).
Algorithm name, iteration count, salt length, and key length are module constants in
`passwords.py`.

**Rationale**: PBKDF2 is the one password-based KDF that stdlib `hashlib` always provides,
independent of how the local OpenSSL was built. 600,000 iterations is the current OWASP figure
for PBKDF2-HMAC-SHA256 and measures ≈145 ms on this host — a comfortable fraction of SC-007's
1-second budget, since every command performs at most one derivation. A fresh 16-byte random
salt per account satisfies FR-036's requirement that two accounts sharing a password hold
different verifiers. Verification compares with `hmac.compare_digest`, so a wrong password
cannot be narrowed byte-by-byte through timing.

**Alternatives considered**:
- **`hashlib.scrypt`** (measured ≈47 ms at `n=2**14, r=8, p=1`): memory-hard and the stronger
  primitive, and available here. Rejected because it is present only when Python is linked
  against an OpenSSL built with scrypt support, so it can raise at import-or-call time on an
  otherwise valid 3.11+ interpreter — a portability failure the spec's "runs anywhere Python
  does" posture does not accept. Noted as the preferred upgrade if a future requirement adds a
  hard memory-hardness demand.
- **Plain `hashlib.sha256(salt + password)`**: fast enough, but a single hash makes offline
  guessing against a stolen store trivial; FR-036 asks for a one-way transformation whose point
  is to resist exactly that.
- **Storing `iterations` and `algorithm` per record** to allow rehashing later: rejected under
  Principle IV — no requirement asks for algorithm migration, and the fields would be written,
  read, and validated while never varying. Consequence accepted and recorded: changing the
  constants invalidates existing stores, and no requirement calls for migrating them.
- **`crypt` module**: deprecated in 3.11 and removed in 3.13, and platform-dependent.

---

## R-03: Argument parsing — `argparse`, with usage failures mapped to exit 2

**Decision**: One `argparse.ArgumentParser(prog="python -m accounts")` with a required
`--store PATH` option and two positionals, `command` (constrained by `choices` to the five
names) and `username`. Parse failures are left to argparse, which prints usage to stderr and
exits 2.

**Rationale**: argparse's own failure behaviour is already exactly FR-035 — usage diagnostic on
stderr, exit status 2 — for a missing `--store`, a missing or unknown command, a missing
username, and extra positional arguments. Using it means that requirement is satisfied by the
stdlib rather than by hand-written checks that would need their own tests for each
permutation. `choices` turns "unknown command" into the same path as the other usage errors.

**Alternatives considered**:
- **Manual `sys.argv` parsing**: more code, five more branches, and the exit-2 contract
  re-implemented by hand; Principle IV picks the smaller design.
- **`argparse` subparsers per command**: natural-looking, but the commands share one argument
  shape (store + username) and differ only in how many stdin lines they read, so subparsers
  would add five parser objects for no behavioural difference.
- **`optparse` / `getopt`**: `optparse` is deprecated; `getopt` does not produce usage messages
  or the exit-2 behaviour on its own.

Because argparse calls `SystemExit`, `cli.main` catches `SystemExit` and returns its code, so
the in-process test harness observes a status instead of terminating the test run.

---

## R-04: Store-file failures use exit status 2

**Decision**: An unreadable store, a store whose bytes are not a valid store, a store path
whose parent directory does not exist, and a store path that cannot be written all produce a
diagnostic on stderr that names the path and the specific condition, and exit **2**.

**Rationale**: FR-007 and the "unusable store path" edge case require a diagnostic and a
non-zero status but do not name which one, while FR-005 restricts the tool to exactly 1, 2, 3,
and 4 with fixed meanings. Statuses 1, 3, and 4 are reserved for credential, existence, and
lock outcomes, none of which describe a bad file. Status 2 is defined as "invalid input or
usage", and the store path and its contents are input. So 2 is the only choice consistent with
both requirements.

**Alternatives considered**:
- **A fifth status such as 5 or 74 (`EX_IOERR`)**: more informative, and directly contradicts
  FR-005's "exactly these non-zero statuses".
- **Letting the traceback propagate** (exit 1 from an uncaught exception): collides with the
  credential-failure meaning of 1 and prints a traceback instead of a diagnostic naming the
  file.

---

## R-05: Atomic save — `tempfile.mkstemp` in the store's directory, `chmod 0600`, `os.replace`

**Decision**: Write to a temporary file created by `tempfile.mkstemp(dir=<store parent>)`,
`os.chmod` it to `0o600`, `flush` + `os.fsync` it, close it, then `os.replace(tmp, store)`. On
any failure, unlink the temporary file and raise `StoreError`.

**Rationale**: `os.replace` is atomic within a filesystem, so the "interrupted write" edge case
and FR-008 hold: a reader sees either the previous store or the complete new one, never a
truncated one. Creating the temporary file in the *store's own directory* keeps the rename
within one filesystem — a temp file under `/tmp` would make `os.replace` a cross-device copy
and lose atomicity. `mkstemp` creates with mode `0600` already; the explicit `chmod` makes
FR-038 true of the file the operator ends up with regardless of umask, and `fsync` before
rename is what makes FR-006's "durable at the moment the tool exits 0" more than a claim about
the page cache.

**Alternatives considered**:
- **Write the store path in place (`open(path, "w")`)**: simplest, and it is precisely the
  truncation failure the spec calls out.
- **Copy to `path.bak` first, then write in place**: leaves a second file containing verifiers,
  and recovery becomes a manual step rather than an atomic one.
- **`fsync` the parent directory too**: guards the rename itself against power loss. Not
  adopted — no requirement reaches past process exit to machine crash, and it adds a platform
  caveat (directory `fsync` is not portable to every target).

---

## R-06: Reading passwords from standard input

**Decision**: `cli` reads each password it needs with a single `stream.readline()`. An empty
string means end of input: diagnostic + exit 2 (FR-018), never an empty password. Otherwise
exactly one trailing `"\n"` is removed, with `line[:-1] if line.endswith("\n") else line`, and
every other character — leading and trailing spaces, `\r`, non-ASCII — is kept. Lines beyond
what a command needs are never read, so extra input is ignored. Length rules count
`len(password)`, i.e. Unicode code points, not bytes.

**Rationale**: This is the literal reading of FR-017 ("only the terminating newline ... MUST be
excluded") and of the "password containing spaces or non-ASCII characters" and "extra lines on
standard input" edge cases. `readline` is the only stdlib read that distinguishes "a blank
line was supplied" (`"\n"`, which then fails the 12-character rule with status 2) from "input
ended" (`""`, status 2 with a different diagnostic) — a distinction `read().splitlines()`
destroys. Using `len()` on a `str` counts characters, which is what the spec asks for; encoding
to UTF-8 happens only inside `passwords.py`, after validation.

**Alternatives considered**:
- **`input()`**: raises `EOFError` instead of returning a sentinel, and strips the newline
  without telling the caller whether one was present. It also reads from the real `sys.stdin`
  rather than an injected stream, which would force every test to be a subprocess.
- **`getpass.getpass()`**: prompts on a TTY and would break piping, which is the documented
  invocation style.
- **`line.rstrip("\n")` or `.strip()`**: `rstrip` removes *every* trailing newline and `strip`
  removes the spaces the spec says are part of the password.

Read order per command, as fixed by FR-003 and FR-034: `register` reads one line; `login` one;
`passwd` two (current, then new); `delete` one; `unlock` reads nothing. For `unlock`, `passwd`,
and `delete`, the account-existence check runs *before* any read, so a command for a missing
account exits 3 without consuming input.

---

## R-07: Check ordering within each command

**Decision**: A fixed order per command, chosen so the required precedences in FR-013, FR-028,
and FR-034 fall out of it rather than being special-cased.

- `register`: username format → password present → password length → account already exists.
- `login`: account exists? (no → `invalid credentials`, 1) → locked? (yes → `account locked`,
  4) → password present → verify → on success reset count; on failure increment, lock at 5,
  **save**, exit 1.
- `unlock`: account exists? (no → 3) → clear lock and zero the count → 0.
- `passwd`: account exists? (no → 3) → current password present → new password present →
  verify current (wrong → 1) → new password length (short → 2) → replace verifier and salt → 0.
- `delete`: account exists? (no → 3) → password present → verify (wrong → 1) → remove → 0.

**Rationale**: FR-013 requires input validation to precede existence checks at registration, so
username and password rules come first there. FR-028 requires the new-password length error to
be reported only *after* the current password is accepted, so that a status-2 response cannot
be used to learn that the current password was right — hence verify-then-length in `passwd`,
which is the reverse of `register`'s order. FR-034 requires the existence check to precede
reading any password for `unlock`, `passwd`, and `delete`. FR-016 puts the unknown-account
case on login behind the same message and status as a wrong password. FR-020 places the lock
check before password verification so a correct password cannot produce `ok` on a locked
account, and FR-024 keeps the failure counter out of `passwd` and `delete` entirely.

**Alternatives considered**: one shared "resolve account then check password" helper used by all
five commands. Rejected — the orders genuinely differ (login hides absence, the others report
it; register validates before lookup, passwd verifies before validating), so the helper would
need flags for each difference and would make the FR-013/FR-028/FR-034 precedences harder to
read than the five explicit sequences.

---

## R-08: Testing approach — in-process `main()` plus a thin subprocess layer

**Decision**: `cli.main(argv: list[str], stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int`
is the seam. Most tests call it directly with `io.StringIO` streams and a `tmp_path` store, and
assert on the returned status and the two captured strings. `tests/test_end_to_end.py` runs
`[sys.executable, "-m", "accounts", ...]` with `env["PYTHONPATH"] = "src"` via
`subprocess.run`, covering the four worked examples (SC-002), cross-invocation persistence
(SC-005), and the store-bytes and command-line secret checks (SC-006).

**Rationale**: Principle III wants every requirement covered, and a 38-requirement matrix run
in-process costs milliseconds per case instead of an interpreter start, which keeps the full
suite fast enough that "full suite green" stays a habit. Injecting the streams rather than
monkeypatching `sys.stdout` is also what makes the "diagnostics never on stdout" gate directly
assertable. The subprocess tests exist because some criteria are claims about the *process* —
its real exit status, that nothing extra reaches the real streams, and that no password appears
in `argv` — which an in-process call cannot honestly verify.

**Alternatives considered**:
- **Subprocess for everything**: the most faithful, and ~600 ms × every case; the lockout
  sequences alone would dominate the suite.
- **`capsys` with a module-level `main()` reading `sys.stdin`**: works, but couples every test
  to pytest's capture and hides the stream-separation property behind fixture behaviour.
- **`unittest`**: the constitution names `pytest`.

---

## Resolved unknowns

| Question | Resolution |
|---|---|
| On-disk store format | R-01: JSON object, version-stamped, username-keyed |
| One-way password transformation and salting | R-02: PBKDF2-HMAC-SHA256, 600k iterations, 16-byte per-account salt |
| How usage errors produce exit 2 | R-03: argparse's native stderr-usage + status 2, `SystemExit` captured in `main` |
| Which status a bad store file uses | R-04: 2, the only one consistent with FR-005 and FR-007 |
| How FR-008 ("fully apply or leave intact") is achieved | R-05: same-directory temp file, chmod 0600, fsync, `os.replace` |
| Exact stdin semantics (EOF vs blank, newline handling, extra lines) | R-06: `readline`, single trailing `\n` removed, EOF is an error |
| Required precedence among validation, existence, lock, and verify | R-07: five explicit per-command orders |
| Test strategy satisfying Principle III without a slow suite | R-08: in-process `main()` seam plus subprocess end-to-end tests |

No `NEEDS CLARIFICATION` markers remain.
