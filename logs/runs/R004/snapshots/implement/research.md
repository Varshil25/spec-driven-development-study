# Phase 0 Research: Local User Account Manager (CLI)

**Feature**: `001-user-accounts-cli` | **Date**: 2026-11-04

**Input**: [spec.md](./spec.md), [constitution](../../.specify/memory/constitution.md)

## Purpose

The spec records its environment constraints as given (A-013: Python 3.11+,
standard library only, package `accounts` under `src/`), and the user input for
this planning run confirms them and adds `pytest` for tests. No
`NEEDS CLARIFICATION` marker therefore survives into the Technical Context on
the *environment* axis. What remained open were the **mechanism** choices the
spec deliberately left to planning: which password hash, which store encoding,
how atomicity and serialisation are achieved, and how a handful of
requirement interactions order themselves. Each is resolved below against the
machine this will run on.

All measurements below were taken on the development host (Python 3.13.17,
Linux 6.18, x86-64) and are reproducible with the commands in
[quickstart.md](./quickstart.md).

---

## R1 — Password hashing algorithm and parameters

**Decision**: `hashlib.scrypt` with `n=2**17, r=8, p=1, dklen=32,
maxmem=192*1024*1024`, a fresh 16-byte salt per account from
`secrets.token_bytes(16)`. The algorithm name and all four parameters are
stored alongside each account record.

**Rationale**:

- SR-004 requires "a deliberately slow password-hashing algorithm at current
  parameters". The standard library offers exactly two candidates:
  `hashlib.scrypt` (memory-hard) and `hashlib.pbkdf2_hmac` (iterated only).
  Constitution Principle V rule 4 prefers "memory-hard **or** iterated"; scrypt
  is the stronger of the two available and is present in this build
  (`hashlib.scrypt` resolves, OpenSSL-backed).
- `n=2**17, r=8, p=1` is the OWASP Password Storage minimum work factor for
  scrypt. Measured cost: **0.369 s** per derivation, 128 MiB working set.
- `maxmem` must be set explicitly: OpenSSL's default cap (32 MiB) rejects
  `n=2**17, r=8`. 192 MiB gives headroom over the 128 MiB working set and is
  itself the enforced memory bound SR-006 asks for on this operation.
- Storing the parameters per record (rather than as a global constant) is what
  makes a future parameter increase a non-migration: old accounts keep
  verifying under their recorded parameters, new and changed passwords get the
  new ones. SR-004 requires this recording anyway.

**Alternatives considered**:

| Option | Measured | Rejected because |
|---|---|---|
| `pbkdf2_hmac('sha256', …, 600_000)` | 0.144 s | Not memory-hard; far cheaper to attack on GPU/ASIC per unit of defender cost. Only worth it if scrypt were unavailable. |
| scrypt `n=2**16, r=8, p=2` | 0.347 s | Equivalent work to the chosen set at half the memory (64 MiB). A legitimate OWASP-listed alternative; chosen set preferred because higher `n` (not higher `p`) is where scrypt's memory hardness comes from. |
| scrypt `n=2**16, r=8, p=1` | 0.169 s | Half the OWASP minimum work factor. Would have bought performance margin (see R8) by weakening a NON-NEGOTIABLE principle — rejected. |
| scrypt `n=2**14, r=8, p=1` | 0.028 s | Eighth of the minimum work factor. Rejected outright. |

**Also decided**: verification compares the derived digest to the stored digest
with `hmac.compare_digest` (SR-005, constant-time). `login` against a username
that does not exist performs one derivation against a fixed synthetic dummy
salt and discards the result, so that the unknown-account and wrong-password
paths cost the same wall-clock time (SC-004 requires identical message and
status; equal timing closes the side channel that would otherwise still
enumerate accounts). The dummy input is a module constant, not a password.

---

## R2 — Store encoding

**Decision**: a single JSON object, UTF-8, written with
`json.dumps(…, ensure_ascii=True, sort_keys=True, separators=(",", ":"))`,
shaped `{"version": 1, "accounts": {<username>: <flat record>}}`. Parsed with
`json.loads`. See [contracts/store-format.md](./contracts/store-format.md).

**Rationale**:

- SR-002 requires a structured encoding in which no username or credential
  material can create, merge or truncate a record by containing a delimiter,
  newline or control character. JSON string escaping gives this for free;
  `ensure_ascii=True` additionally guarantees the file holds no raw control
  characters or non-ASCII bytes at all, so the file is safe to inspect in a
  terminal.
- Usernames are restricted to `[A-Za-z0-9_]` by FR-011 anyway, so they are
  already safe as JSON object keys — and a dict keyed by username enforces
  "at most one account per username" structurally rather than by a check.
- `sort_keys=True` makes the file byte-for-byte deterministic for a given
  account set, which is what lets the SC-008 "store unchanged after failure"
  test be a plain byte comparison instead of a semantic diff.
- Measured: 1 000 accounts serialise to **179 KiB**; `json.loads` 1.3 ms,
  `json.dumps` 1.7 ms. 10 000 accounts project to ~1.75 MiB, comfortably under
  the 8 MiB ceiling of A-011 — the two limits are mutually consistent.
- Bounded parsing (SR-006): the file size is checked against the 8 MiB limit
  from the open file descriptor *before* the bytes are parsed, and deeply
  nested input raises a catchable `RecursionError` from the C scanner
  (confirmed: 200 000-deep array → `RecursionError`), which is reported as
  status 5. No regular expressions are used in parsing, so there is no
  backtracking cost to bound.

**Alternatives considered**: a line-oriented `username:salt:hash:count` format
(rejected — delimiter injection is exactly what SR-002 forbids, and escaping it
by hand reimplements JSON badly); `sqlite3` (rejected — Principle IV, a
relational engine for one flat dict, and FR-009's atomicity is already solved
more simply by `os.replace`; also leaves `-wal`/`-journal` sidecar files, which
conflicts with FR-007's "the store MUST be the single file at the given path");
`configparser` (rejected — no nesting, weak escaping, and interpolation is an
injection surface); `pickle` (rejected outright — arbitrary code execution on a
malformed store).

---

## R3 — Atomic replacement (FR-009, SC-009)

**Decision**: write to a fresh temporary file in the store's own directory,
`fsync` it, close it, `os.replace()` it over the store path, then `fsync` the
containing directory. The temporary file is created with
`os.open(path, O_WRONLY|O_CREAT|O_EXCL, 0o600)` and a name of
`.<storename>.<16-hex>.tmp` where the hex comes from `secrets.token_hex(8)`. On
any failure the temporary file is unlinked.

**Rationale**:

- `os.replace` is `rename(2)`, which is atomic within a filesystem: a reader
  sees either the whole old file or the whole new one, never a mixture, and
  never an empty file. The directory `fsync` is what makes the rename itself
  durable after a power loss, not merely after a process kill.
- Same-directory placement is required twice over: `rename` cannot cross
  filesystems, and SR-003 explicitly mandates it.
- `O_EXCL` plus an unpredictable name satisfies SR-003's "no overwriting of an
  existing file, unpredictable name"; the explicit `0o600` mode argument
  satisfies SR-008's "set at creation rather than applied afterwards", and the
  mode survives the rename, so the store inherits owner-only permissions
  (SC-010).
- `tempfile.NamedTemporaryFile` was considered and rejected: it creates with
  mode `0o600` correctly but its `delete` semantics and name handling fight the
  rename pattern, and `tempfile.mkstemp` in the target directory is the same
  call as above with less control over the name prefix. `os.open` directly is
  the smaller, clearer thing (Principle IV).

**Consequence recorded**: if the store path is a symbolic link, the directory
used for the temporary file and the rename target are derived from
`os.path.realpath()`, so the operator's symlink keeps pointing at a real file
instead of being replaced by one. SR-003 states containment does not apply
here, so following the operator's own deliberate symlink honours their intent.

---

## R4 — Serialising concurrent invocations (SR-007, edge case "simultaneous invocations")

**Decision**: hold an exclusive `fcntl.flock(LOCK_EX)` on a file descriptor for
the **directory containing the store** for the whole read–modify–write of every
command, including read-mostly ones.

**Rationale**:

- The obvious candidate — locking the store file itself — is wrong twice.
  First, `register` on a store that does not exist yet has no file to lock, so
  two concurrent first-registrations would race. Second, `os.replace` swaps the
  inode: a lock held on the old inode protects nothing once the new file is in
  place, so each invocation would be locking a different object.
- The directory is the thing that both the store and its temporary file live
  in, exists for the whole operation, and has a stable inode. Locking it closes
  both races. Confirmed working on this platform:
  `os.open(dir, O_RDONLY)` + `flock(LOCK_EX)` succeeds.
- Locking the directory also means it creates **no files**, which FR-007
  requires: a `login` against a non-existent store must not bring a store — or
  a `.lock` sidecar — into existence.
- Taking the lock exclusively even for `login` is deliberate: every command can
  write (a failed `login` increments the failure count, a successful one resets
  it), so a shared/exclusive distinction would buy nothing and cost a
  lock-upgrade race. A-012 caps the required throughput at "correct", not
  "fast".
- The lock is advisory and effective only between cooperating invocations of
  this tool, which is precisely SR-007's stated scope ("serialised against
  other invocations").

**Alternatives considered**: a `PATH.lock` sidecar file (rejected — creates a
file for non-`register` commands, against FR-007); `O_EXCL` lock-file spinning
(rejected — needs stale-lock recovery, which is a new failure mode and more
code); no locking (rejected — SR-007 names the lost-failure-count-increment
attack explicitly).

**Cost accepted**: invocations against *different* stores in the same directory
serialise against each other unnecessarily. Acceptable under A-012.

---

## R5 — Reading passwords from stdin under a byte cap (FR-002, FR-014, SR-006, A-009, A-010)

**Decision**: read each password line from `sys.stdin.buffer` with
`readline(MAX_LINE_BYTES + 1)`, i.e. `readline(4097)`. Classify:

| Return | Meaning |
|---|---|
| `b""` | input ended → missing password input, status 2 (A-010) |
| length 4097 | line exceeds the 4 096-byte limit → status 2, nothing read further |
| otherwise | strip one trailing `\n`, then one preceding `\r`; decode UTF-8 |

**Rationale**: the size argument is what makes the read bounded — the limit is
enforced by never asking for more than 4 097 bytes, not by measuring after the
fact, so an attacker-supplied 1 GiB line cannot be loaded (SR-006). A return of
exactly 4 097 bytes is unambiguous proof of overflow; any shorter return is
within limit whether or not it ended in a newline (a final line at EOF without
a terminator is valid). A present-but-empty line is `b"\n"` → a password of
length 0, which is the spec's intended distinction from *missing* input.

**Decided consequences**:

- A line that is not valid UTF-8 is a malformed *request*, status 2, on every
  command — not a wrong password. A-009 defines a password as UTF-8 text, so
  undecodable bytes are not a candidate password at all. Recorded as a decision
  because the spec does not name this case.
- Length for FR-012/A-011 purposes is counted in **characters after decoding**
  (A-009: "length is counted in characters"), while the 4 096-byte line cap is
  counted in **bytes**. Both limits are therefore enforced, in that order.
- Extra input lines are never read, which is both how they are "ignored" (spec
  edge case) and why a 10 GiB stdin costs nothing.
- `unlock` reads **zero** lines (A-006), so it must work with stdin closed.

---

## R6 — Ordering of checks (resolving requirement interactions)

The spec pins several orderings and leaves a few implied. Resolved order, which
the contract tests assert directly:

1. **Argument shape** → status 2. Usage, unknown command, missing/extra
   arguments, missing `--store`.
2. **Username format** (FR-011) → status 2. Before the store is touched at all,
   so an invalid username can never create a store file.
3. **Password input** (R5) → status 2. Missing line, over-long line, bad UTF-8.
4. **`register` only — new password length** (FR-012) → status 2, before the
   store is read. `register` has nothing to authenticate against, so length is
   pure request validation and belongs "on the way in" (SR-001). Scenario 1.6
   confirms it on a fresh store.
5. **Store load** (FR-007, SR-001, SR-006) → status 5 on unreadable, over-size,
   over-count, unparseable or structurally invalid content. A missing store is
   *not* an error here: it loads as empty and is not created.
6. **Account existence**: `register` → 3 if present; `unlock`/`passwd`/`delete`
   → 3 if absent; `login` → status 1 `invalid credentials` if absent (A-001),
   after the dummy derivation of R1.
7. **Lock state** (FR-017) — `login` only → status 4, *before* the password is
   considered (scenario 2.4 is explicit). `passwd` and `delete` skip this step
   entirely (FR-019).
8. **Current-password verification** (FR-013) → status 1.
9. **`passwd` only — new password length** → status 2, *after* step 8. Scenario
   3.2 says a wrong current password with "any new password" yields status 1,
   so authentication precedes new-password validation here. This is the one
   place where FR-013's "before doing anything else that the operation implies"
   outranks SR-001's validate-early rule, and the spec's own scenario is what
   decides it.
10. **Apply and save** → status 0.

**Noted asymmetry, deliberate**: new-password length is validated before the
store is read for `register` (step 4) and after authentication for `passwd`
(step 9). Both placements come from the spec's own acceptance scenarios.

---

## R7 — Lock state is derived, not stored

**Decision**: each account record stores `failed_logins` (an integer) and
**no** separate locked flag. Locked is computed as
`failed_logins >= 5`.

**Rationale**: FR-016 locks the account "as soon as its count of consecutive
failed login attempts reaches 5" and FR-018 has `unlock` clear the lock *and*
reset the count to zero, so the two can never legitimately disagree — the flag
would be pure redundancy. Storing both invents a new malformed-store case (a
record claiming `locked: true` with `failed_logins: 0` — which would then have
to be rejected under status 5) for no behavioural gain. Principle IV calls for
the flat, non-redundant structure. The Key Entities line "whether it is locked"
is satisfied by a derived attribute; no requirement distinguishes a locked
account whose count is not exactly 5.

**Alternative considered**: store `locked: bool` as well, for forensic clarity
about *why* an account is locked. Rejected — the count already says that, and
the redundancy has to be validated and kept consistent forever.

---

## R8 — Performance budget against SC-007

**Measured**: store load+save for 1 000 accounts is **3.0 ms** combined
(1.3 ms parse, 1.7 ms serialise). One scrypt derivation at the chosen
parameters is **0.369 s**. Interpreter start for `python -m accounts` is
~30 ms. Derivations per command: `unlock` 0, `login` 1, `register` 1,
`delete` 1, `passwd` 2 (verify current, derive new).

| Command | Projected wall clock, 1 000-account store |
|---|---|
| `unlock` | ~0.04 s |
| `login`, `register`, `delete` | ~0.40 s |
| `passwd` | ~0.77 s |

**Decision**: keep the OWASP-minimum parameters, and test SC-007 two ways:

- an **absolute** assertion, every command under 1 s on a 1 000-account store;
- a **hardware-independent** assertion that the store-scaling component is
  negligible — the same command against a 1-account store and a
  1 000-account store differ by less than 100 ms.

**Flagged for the user (clarification candidate, not a blocker)**: `passwd`
leaves only ~1.3× headroom on the absolute bound, because two deliberate
derivations are inherent to it. On hardware materially slower than this host
the absolute assertion for `passwd` alone could fail. The cost is deliberate
security work, not inefficiency, and SC-007's wording ("on a store holding
1 000 accounts") reads as a statement about *store scale*, which the second
assertion measures directly. If the absolute 1 s bound on `passwd` is the
binding requirement on the target hardware, the lever is the work factor
(R1's `n=2**16, r=8, p=1` alternative halves it), and that is a spec decision
about SR-004, not an implementation detail. Proceeding with the strong
parameters until told otherwise.

---

## R9 — Error message construction (FR-005, SR-002, SR-009)

**Decision**: every failure writes exactly one line to stderr and nothing to
stdout. Two messages are fixed strings mandated by FR-005 — `invalid
credentials` and `account locked` — and carry no detail at all. Every other
message states what was expected and what was received, where "what was
received" is a **length, a count or a sanitised username**, never a password, a
salt, a digest, a parameter or any store content.

Usernames echoed back into a message pass through a sanitiser that renders
anything outside printable ASCII as `\xNN` and truncates at 64 characters
(SR-002: no unescaped control characters from input in output; SR-009: no
terminal-injection surface). The store path may be echoed verbatim — SR-009
exempts "the operator's own argument" explicitly.

Full message table: [contracts/cli-contract.md](./contracts/cli-contract.md).

---

## R10 — Argument parsing

**Decision**: `argparse.ArgumentParser(add_help=False, allow_abbrev=False)`
with `--store` as a required option, `command` as a positional with
`choices=("register", "login", "unlock", "passwd", "delete")`, and `username`
as a positional. `ArgumentParser.error` is overridden to raise the project's
own error carrying status 2 instead of calling `sys.exit` itself.

**Rationale**: Principle IV prefers the standard library's existing solution to
a hand-rolled one, and `choices` *is* SR-001's allow-list for the command name.
`allow_abbrev=False` stops `--sto` from being accepted as `--store`, keeping the
accepted surface exactly what FR-001 specifies. `add_help=False` is deliberate:
FR-003 admits only six exit statuses for their stated conditions and the spec
defines no help operation, so no path may exit 0 without having performed an
operation. Overriding `error()` keeps every exit status flowing through one
place in `cli.py` rather than letting argparse exit on its own terms.

**Alternative considered**: hand-rolled `sys.argv` walking (~20 lines).
Rejected under Principle IV's preference for the stdlib solution, though it was
close — argparse's defaults needed three suppressions to behave.

---

## Resolved: no outstanding NEEDS CLARIFICATION

Every unknown that entered Phase 0 is decided above. Two items are recorded as
decisions the user may want to revisit, and neither blocks design or
implementation:

1. **R8** — `passwd`'s headroom against SC-007's absolute 1 s bound.
2. **Register into a full store** — A-011 caps a store at 10 000 accounts but
   FR-003's status table has no row for "the store cannot accept another
   account". Decided: status **5**, on the grounds that statuses 1–4 are each
   defined for a specific account-level outcome while this is a store-level
   refusal to write, and SR-006 frames the account cap as a store limit
   alongside the file-size cap. Recorded in the contract.
