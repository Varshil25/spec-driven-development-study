# Phase 0 Research: Local Account Manager CLI

**Feature**: `001-accounts-cli` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

## Scope of this document

The specification has already been clarified (session 2026-11-11) and carries no
`NEEDS CLARIFICATION` markers: the password transformation (FR-026a), the store format
(FR-029a/b/c), the exact message strings (FR-027, SC-002) and the performance budget
(SC-009) are all pinned. The Technical Context in [plan.md](./plan.md) therefore has no
unknowns.

What remains for Phase 0 is the second and third category of research task: best practices
for the chosen standard library modules, and the design decisions the specification
deliberately leaves to the implementation. Each decision below is recorded with its
rationale and the alternatives rejected. Measurements were taken on this development
machine (Python 3.13.17, pytest 9.1.1).

---

## D-001: Standard library modules used

**Decision**: runtime code imports only `argparse`-free hand-rolled parsing plus `hashlib`,
`hmac`, `json`, `os`, `secrets`, `sys`, `tempfile`, and `pathlib`. No third-party imports,
no runtime dependency declaration.

| Module | Used for | Requirement |
|---|---|---|
| `hashlib` | `pbkdf2_hmac('sha256', ...)` key derivation | FR-026a |
| `hmac` | `hmac.compare_digest` constant-time key comparison | FR-026c |
| `secrets` | `secrets.token_bytes(16)` per-account salt from a CSPRNG | FR-026a |
| `json` | store serialization and parsing | FR-029a |
| `os` | `os.replace`, `os.fsync`, `os.open`/`O_CREAT|O_EXCL`, `os.chmod`, `os.close` | FR-029b, FR-029c |
| `tempfile` | `mkstemp(dir=...)` for the same-directory temporary file | FR-029b |
| `pathlib` | store path handling | FR-001 |
| `sys` | argv, stdin, stdout, stderr, exit status | FR-001, FR-027, FR-030 |
| `base64` | text encoding of salt and derived key inside JSON | FR-029a |

**Rationale**: Principle I (Standard Library Only). `hashlib.pbkdf2_hmac` is implemented in
OpenSSL and is the fastest stdlib route to PBKDF2; `hmac.compare_digest` is the stdlib's
documented constant-time comparison.

**Alternatives considered**:

- `hashlib.scrypt` / Argon2 — stronger memory-hard functions, but FR-026a names
  PBKDF2-HMAC-SHA256 at 600,000 iterations. Rejected: the specification is binding.
- `random` for salts — not cryptographically secure. Rejected on FR-026a ("cryptographically
  secure random source").
- `binascii.hexlify` instead of `base64` — equivalent; `base64` chosen for a shorter file.
  Either satisfies "binary material recorded in a text encoding" (FR-029a).

---

## D-002: Argument parsing — hand-rolled, not `argparse`

**Decision**: parse `sys.argv[1:]` by hand. Scan for the `--store` flag, take the following
element as the path, and require the remaining elements to be exactly two positionals
(`COMMAND`, `USERNAME`) with `COMMAND` in the known set. Anything else — missing `--store`,
`--store` with no value, a missing or unknown command word, a missing username, extra
positionals, or an unrecognized flag — produces the single exact usage line of FR-006 on
stderr with exit status 2, and no store file is created or touched.

**Rationale**: FR-006 requires *exactly* one string:
`usage: python -m accounts --store PATH {register|login|unlock|passwd|delete} USERNAME`.
`argparse` writes its own multi-line usage and error text, exits 2 via `SystemExit`, and
pinning its output to that one line means overriding `error()`, suppressing `prog`, and
disabling `-h`. The hand-rolled parser is about fifteen lines, gives exact control of the
message and stream, and keeps `-h`/`--help` from becoming an undocumented fourth way to
exit non-zero. Principle IV favours the smaller design, and here the "library" option is the
larger one.

**Alternatives considered**:

- `argparse` with a custom `error()` and `add_help=False` — rejected as above: more code and
  more surface to get FR-006 exactly right.
- `getopt` — thin, but still needs the same positional validation afterwards, so it saves
  nothing.

**Sub-decisions** (not fixed by the spec, documented so tests can assert them):

- `--store PATH` is accepted in any position relative to the positionals (`--store p login
  alice` and `login alice --store p` both work). The scan is position-independent, which is
  less code than enforcing an order.
- `--store=PATH` is **not** accepted; it is a usage error. FR-001 documents the space form
  only, and Principle IV says not to add the alternative spelling without a requirement.
- A password placed where an argument is expected is never read as a password (SC-007):
  arguments are only ever the store path, command word and username, and a third positional
  is a usage error.

---

## D-003: Reading passwords from standard input

**Decision**: read exactly the number of lines the command needs (FR-004) with one
`readline()` per password, in order. A returned empty string (`''`) means end of input
before the line was available → `missing password input` on stderr, exit 2 (FR-005). A
returned line is the password with a single trailing `\n` removed, if present; nothing else
is stripped. `unlock` reads nothing at all. Input after the needed lines is never read, so
it is ignored (FR-004).

**Rationale**: `readline()` is the exact primitive FR-003 describes ("one line, terminated
by a line break or end of input"). Distinguishing `''` (EOF) from `'\n'` (an empty password,
length 0, rejected by the FR-008 length rule) is what makes the edge case in the spec —
"an empty line is a password of length 0 and is therefore rejected on the length rule" —
fall out of the implementation rather than needing a special case.

- `line[:-1] if line.endswith('\n') else line` rather than `rstrip()` or `strip()`:
  passwords may contain and must preserve leading and trailing whitespace, and a password
  may contain spaces (`correct horse battery`).
- Standard input is decoded as UTF-8 explicitly (wrapping `sys.stdin.buffer` in
  `io.TextIOWrapper(encoding='utf-8', newline=None)` in `__main__.py`). This makes the
  "lengths are counted in characters, not bytes" assumption behave the same regardless of
  the ambient locale, and `newline=None` (universal newlines) means a `\r\n` line ending
  arrives as `\n`. One line of code, tied to a stated assumption.
- Passwords are encoded back to UTF-8 bytes immediately before derivation (FR-026a).

**Alternatives considered**:

- `sys.stdin.read().split('\n')` — reads the ignored extra input too, and loses the
  EOF-versus-empty-line distinction that FR-005 depends on. Rejected.
- `getpass.getpass()` — prompts from a TTY, which contradicts FR-003's "reads from standard
  input" and breaks non-interactive use. Rejected.

---

## D-004: Order of checks within a command

**Decision**: every command applies its checks in this fixed order:

1. Argument parsing → usage error, exit 2 (FR-006). No store access.
2. Store load → `store unusable: <cause>`, exit 5 (FR-029). A missing file is *not* an
   error here: it loads as an empty store (FR-002, edge case "store absent on first use").
3. Required password lines → `missing password input`, exit 2 (FR-005).
4. Per-command rules, in the precedence the spec fixes:
   - `register`: username format (2) → password length (2) → already exists (3).
     (FR-010: format before existence; username before password.)
   - `login`: account exists (else `invalid credentials`, 1) → locked (4) → password (1).
   - `unlock`: account exists (else `no such account`, 3) → succeed (0).
   - `passwd`: account exists (3) → current password (1) → new password length (2).
     (FR-021/FR-022.)
   - `delete`: account exists (3) → password (1).
5. Store write only on success (FR-028), or on the FR-013 tally increment, which is the one
   documented write on a failing path.

**Rationale**: steps 1–3 are ordered by what the tool can still honestly say. Usage errors
come first because without a command there is nothing to do and FR-006 forbids touching the
store. Store load comes before input validation because an unusable store means the command
cannot be carried out at all — reporting `invalid username` while the store is corrupt would
imply the store was fine and would contradict FR-029's "MUST NOT treat an unreadable or
corrupt store as an empty store". Step 4's internal order is quoted verbatim from the spec's
precedence assumption, not chosen here.

**Consequence worth pinning in tests**: `register` with an invalid username against a
*corrupt* store exits 5, not 2. The spec does not state this combination; it follows from the
ordering above and is recorded as a decision so the test suite asserts it deliberately.

**Alternatives considered**:

- Validate pure inputs (username, password length) before touching the filesystem — cheaper
  and arguably friendlier, but it lets a run report an input error while hiding a corrupt
  store, which Principle II (Fail Loudly) and FR-029 argue against. Rejected.

---

## D-005: Atomic, owner-only store writes

**Decision**: `save` writes the whole JSON document to a temporary file created by
`tempfile.mkstemp(dir=<store's directory>)`, `chmod`s it to `0o600`, writes, `flush()`es,
`os.fsync()`s the file descriptor, closes it, then `os.replace(tmp, path)`. On any exception
the temporary file is removed. The final `chmod` to `0o600` happens on the temporary file
*before* the rename, so the store is never momentarily world-readable and a rewrite cannot
widen permissions (FR-029c).

**Rationale**: FR-029b names this sequence. Same-directory temp file is required because
`os.replace` is only atomic within a filesystem. `mkstemp` already creates the file with
mode `0o600`, so the explicit `chmod` is belt-and-braces for the case where the file already
exists with wider permissions — note that `os.replace` preserves the *source* inode's mode,
so the mode of the temp file is the mode the store ends up with. This is what makes "a
rewrite MUST NOT widen them" true without reading the old file's mode.

**Rejected**: `pathlib.Path.write_text()` directly onto the store (not atomic; an interrupted
run truncates the store — exactly what FR-029b forbids); `fcntl` advisory locking (the spec's
assumption section puts concurrency out of scope, so Principle IV excludes it).

**Also noted**: `os.fsync` on the containing directory after the rename would make the rename
itself durable across a power loss. FR-029b requires only that an interrupted run leave one
intact version, which `os.replace` guarantees at the filesystem level. Not implemented;
recorded here so the omission is a decision rather than an oversight.

---

## D-006: Store validation on load

**Decision**: `load` raises a single `StoreError` carrying a human-readable cause for every
condition FR-029/FR-029a name, and `cli` renders it as `store unusable: {cause}` on stderr
with exit 5. A file that does not exist yields an empty store. Validated on load:

- the path exists but is a directory, or the parent directory is missing, or the file cannot
  be read or written (`OSError` → cause from `e.strerror`);
- the bytes are not valid UTF-8, or do not parse as JSON (`UnicodeDecodeError`,
  `json.JSONDecodeError`);
- the top level is not a JSON object, or the format marker is absent or unrecognized;
- `accounts` is not an object, or any record is not an object, or any record is missing a
  required field, or a field has the wrong JSON type.

**Rationale**: Principle II requires the message to name what was wrong, while FR-029 and
SC-002 require the fixed prefix `store unusable: ` to be assertable. A prefix plus a free-form
cause satisfies both, which is exactly the compromise FR-029 spells out. Validating *every*
required field at load time (rather than at first use) means a corrupt record can never be
silently treated as a default-valued account, which FR-029's "MUST NOT ... treat as an empty
store" is the general form of.

**Writability**: the store's directory is probed only implicitly — a write that fails raises
`OSError`, which becomes the same exit 5. No separate pre-flight access check (`os.access`
is advisory and racy, and would be a second code path for the same outcome).

---

## D-007: Per-account derivation parameters

**Decision**: each account record stores `algorithm` (`"pbkdf2_hmac_sha256"`), `iterations`,
`salt` (base64) and `key` (base64). Verification reads those four values from the record and
derives with them; it never consults the module default. New material (register, passwd)
is derived with the module constant `DEFAULT_ITERATIONS = 600_000`. An unrecognized
`algorithm` value on load is a corrupt store (exit 5), not a failed login.

**Rationale**: FR-026b verbatim — "verification MUST derive using the values recorded for
that account rather than the current defaults, so that a later change of cost parameters
cannot silently turn a correct password into a rejected one". Treating an unknown algorithm
as corruption rather than as a credential failure follows Principle II: a store this tool
cannot interpret must fail loudly, not look like a wrong password.

---

## D-008: Keeping the suite inside the SC-009 budget

**Measured on this machine**: one PBKDF2-HMAC-SHA256 derivation at 600,000 iterations and a
32-byte key costs **213 ms**. A `python -m accounts` subprocess costs **~30 ms** of
interpreter startup and stdlib imports on top of that.

**Per-command budget (SC-009, 1 second)**: `register`, `login`, `delete` perform one
derivation (~245 ms end to end); `passwd` performs two (~460 ms). Both are comfortably inside
one second, and neither grows with the number of accounts beyond reading and rewriting the
file. Headroom is roughly 2× for `passwd`, so the budget holds on hardware meaningfully
slower than this machine.

**Suite budget (SC-009, 60 seconds)** — this is the real constraint. At 213 ms each, 60
seconds buys only ~280 derivations, and a suite that covers every requirement and success
criterion with full-cost subprocess runs would exceed that (SC-004 alone — 50 registrations
plus 50 logins — is ~24 s). Decision, in three parts:

1. **Tests drive an in-process entry point by default.** `accounts.cli.main(argv, stdin,
   stdout, stderr) -> int` takes its streams and argv as parameters and returns the exit
   status; `__main__.py` is the only place that touches `sys.*` and calls `sys.exit`. Each
   `main()` call re-reads the store from disk and shares no in-memory state with the
   previous one, so a sequence of calls is a faithful stand-in for a sequence of runs — and
   it is fast, debuggable, and gives tests the captured streams directly.
2. **A small set of tests uses real subprocesses.** `python -m accounts` with `src` on
   `PYTHONPATH` is asserted end to end (FR-001), including one genuine
   register-then-login-in-a-second-process persistence check (FR-002). Kept to a handful of
   invocations, ~0.25 s each.
3. **Bulk and persistence tests lower the iteration count.** Tests that need many accounts —
   SC-004's 50 runs, SC-009's 1,000-account store — monkeypatch
   `accounts.hashing.DEFAULT_ITERATIONS` to a small value for the duration of the test. This
   is sound precisely because of FR-026b: each record carries its own iteration count, so a
   store written at low cost still verifies correctly, and the test exercises the same code
   path. The 600,000 default itself is asserted separately as a one-line constant check plus
   one end-to-end registration that reads the recorded `iterations` back out of the store.

`DEFAULT_ITERATIONS` is a module constant, **not** configuration: nothing reads an
environment variable or a config file, so the constitution's "no hidden I/O / no ambient
configuration" constraint holds and SC-007's argument surface is unchanged. Only the
in-process tests can patch it, which is the point.

**Alternatives considered**:

- Run everything through subprocesses at full cost and accept a slow suite — rejected: it
  breaks SC-009's 60-second criterion, which is itself a tested requirement.
- Expose an `--iterations` flag or an `ACCOUNTS_ITERATIONS` environment variable — rejected:
  it widens the documented argument surface (FR-001, SC-007) and adds ambient configuration
  the constitution forbids.
- Fake the derivation in tests with a monkeypatched hash function — rejected: it would stop
  testing the real FR-026a code path.

---

## D-009: What was deliberately *not* built

Recorded so that each absence is a decision traceable to Principle IV, not an omission.

- **No timing equalization for unknown accounts.** FR-014 requires an unknown account to be
  indistinguishable from a wrong password in *output and exit status*; it does not mention
  duration, and FR-026c's constant-time requirement is about the key comparison only. A dummy
  derivation for unknown users would add code for an unrequired property.
- **No account listing, password recovery, or lock expiry** — explicitly out of scope per the
  spec's assumptions.
- **No inter-process locking** — concurrency is out of scope per the spec's assumptions; the
  atomic replace of D-005 is all FR-029b asks for.
- **No `models/` or `services/` layer.** Account records are plain dicts validated at load.
  See the Structure Decision in [plan.md](./plan.md).
- **No logging.** Nothing in the spec requires it, and FR-027 constrains both streams
  strictly: a stray log line on stdout or stderr would violate it.

---

## Outcome

No `NEEDS CLARIFICATION` items remain. All decisions above are reflected in
[plan.md](./plan.md), [data-model.md](./data-model.md),
[contracts/cli.md](./contracts/cli.md), [contracts/store-file.md](./contracts/store-file.md)
and [quickstart.md](./quickstart.md).
