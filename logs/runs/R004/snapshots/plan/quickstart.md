# Quickstart & Validation Guide

**Feature**: `001-user-accounts-cli` | **Date**: 2026-11-04

How to run the tool and how to prove it satisfies the spec. This is a
validation guide — the behaviour it checks is defined in
[contracts/cli-contract.md](./contracts/cli-contract.md) and
[contracts/store-format.md](./contracts/store-format.md), and the
implementation steps belong in `tasks.md`.

## Prerequisites

- Python **3.11 or newer** (`python3 -VV`). Verified on 3.13.17.
- No runtime install step and no third-party runtime package (Principle I).
- For the test suite only: `pytest` (`pip install -r requirements-dev.txt`).
- A POSIX filesystem. `fcntl.flock` and `os.replace` are both required; the
  tool targets Linux and macOS.

## Running it

```bash
export PYTHONPATH=src           # no install step; src/ on the path is all it needs
python -m accounts --store ./demo.store register alice
```

Every command reads the passwords it needs from stdin, one per line, and never
from an argument. The minimum password length is 12 characters.

```bash
# register, then verify
printf 'correct-horse-battery\n' | python -m accounts --store ./demo.store register alice
printf 'correct-horse-battery\n' | python -m accounts --store ./demo.store login alice   # -> "ok", exit 0

# change a password: current first, then new
printf 'correct-horse-battery\nnew-password-here\n' \
  | python -m accounts --store ./demo.store passwd alice

# unlock takes no password at all
python -m accounts --store ./demo.store unlock alice < /dev/null

# remove an account
printf 'new-password-here\n' | python -m accounts --store ./demo.store delete alice
```

Branch on the exit status, not on the output:

```bash
printf "$CANDIDATE\n" | python -m accounts --store ./demo.store login "$USER_NAME"
case $? in
  0) echo "authenticated" ;;
  1) echo "rejected" ;;
  4) echo "locked - run unlock" ;;
  *) echo "request or store problem" ;;
esac
```

## Running the test suite

```bash
pip install -r requirements-dev.txt
pytest                      # pytest.ini sets pythonpath=src and testpaths=tests
pytest -m "not slow"        # skips the 1000-account performance and crash-loop tests
```

The suite drives the real executable in a subprocess with piped streams, so it
asserts the contract an operator actually gets — exit status, stdout and stderr
— rather than internal function returns. Every test names the FR/SR/SC
identifier it covers in its own name or docstring (Principle III).

## Validation scenarios

Each scenario below is an end-to-end check that a requirement holds. All are
automated in the suite; the manual commands are given so a reviewer can
reproduce any of them by hand.

### V1 — Register and verify across invocations (US1, FR-008, SC-002)

```bash
rm -f ./v1.store
printf 'correct-horse-battery\n' | python -m accounts --store ./v1.store register alice; echo "exit=$?"
printf 'correct-horse-battery\n' | python -m accounts --store ./v1.store login alice;    echo "exit=$?"
printf 'wrong-password-here\n'   | python -m accounts --store ./v1.store login alice;    echo "exit=$?"
```

**Expect**: `registered alice` / exit 0 and the file now exists; `ok` / exit 0;
`invalid credentials` on stderr / exit 1.

### V2 — Unknown account is indistinguishable from a wrong password (SC-004, SR-009, A-001)

```bash
printf 'any-password-here-ok\n' | python -m accounts --store ./v1.store login nobody_here
```

**Expect**: byte-identical stderr (`invalid credentials`), identical exit
status 1 and identical empty stdout to V1's wrong-password case. The automated
version also compares wall-clock times and asserts they are within the same
order of magnitude, since the unknown-account path performs a discarded
derivation for exactly this reason.

### V3 — Lockout and recovery (US2, FR-015 … FR-018, SC-003)

```bash
for i in 1 2 3 4; do printf 'wrong-password-here\n' \
  | python -m accounts --store ./v1.store login alice; echo "exit=$?"; done
printf 'correct-horse-battery\n' | python -m accounts --store ./v1.store login alice   # still works, resets count
for i in 1 2 3 4 5; do printf 'wrong-password-here\n' \
  | python -m accounts --store ./v1.store login alice; echo "exit=$?"; done            # 5th locks
printf 'correct-horse-battery\n' | python -m accounts --store ./v1.store login alice   # refused
python -m accounts --store ./v1.store unlock alice < /dev/null; echo "exit=$?"
printf 'correct-horse-battery\n' | python -m accounts --store ./v1.store login alice   # works again
```

**Expect**: four × exit 1 then `ok`/0 (success resets the count); five × exit 1
with the fifth still reported as exit 1, not 4; then `account locked` / exit 4
*for the correct password*; `unlock` silent / exit 0; finally `ok` / 0.

### V4 — Validation and conflict statuses (FR-003, FR-011, FR-012)

```bash
printf 'correct-horse-battery\n' | python -m accounts --store ./v1.store register ab          # 2: username too short
printf 'correct-horse-battery\n' | python -m accounts --store ./v1.store register 'bad name'  # 2: bad character
printf 'short\n'                 | python -m accounts --store ./v1.store register bob         # 2: password too short
printf 'correct-horse-battery\n' | python -m accounts --store ./v1.store register alice       # 3: exists
python -m accounts --store ./v1.store unlock nobody_here < /dev/null                          # 3: unknown
python -m accounts --store ./v1.store frobnicate alice < /dev/null                            # 2: unknown command
python -m accounts --store ./v1.store login alice < /dev/null                                 # 2: missing input
```

**Expect**: the exit statuses in the comments, each with its message on stderr
and nothing on stdout, and no account created or altered by any of them.

### V5 — No secret ever leaves memory (SR-004, SR-009, SC-005, SC-006)

```bash
PW='correct-horse-battery'
printf '%s\n' "$PW" | python -m accounts --store ./v5.store register carol
grep -c -- "$PW" ./v5.store || echo "0 occurrences - good"
ls -a .                                   # no leftover .tmp file
printf '%s\n' "$PW" | python -m accounts --store ./v5.store register dave_x
python -c "import json;a=json.load(open('./v5.store'))['accounts'];print(a['carol']['hash']!=a['dave_x']['hash'], a['carol']['salt']!=a['dave_x']['salt'])"
```

**Expect**: zero occurrences of the password in the store, in stdout and in
stderr; no temporary file left behind; and `True True` — two accounts with the
*same* password have different salts and different digests (SC-006).

### V6 — Owner-only permissions (SR-008, SC-010)

```bash
stat -c '%a' ./v5.store        # macOS: stat -f '%Lp'
```

**Expect**: `600`. The automated test also asserts the mode immediately after a
`passwd`, since the file is replaced by a rename and must not inherit a wider
mode from the temporary file.

### V7 — Malformed store fails loudly and changes nothing (SR-001, Principle II)

```bash
cp ./v5.store ./v7.store
printf '{"version":1,"accounts":{"carol":{"kdf":"argon2"}}}' > ./v7.bad
cp ./v7.bad ./v7.copy
printf 'correct-horse-battery\n' | python -m accounts --store ./v7.bad login carol; echo "exit=$?"
cmp ./v7.bad ./v7.copy && echo "unchanged - good"
printf 'not json at all' > ./v7.trunc
printf 'correct-horse-battery\n' | python -m accounts --store ./v7.trunc register carol; echo "exit=$?"
```

**Expect**: exit 5 with a structural reason on stderr in both cases, the
malformed file byte-identical afterwards, and no account created. The tool never
starts from an empty store and never partially overwrites the existing one.

### V8 — Atomic write survives a kill (FR-009, SC-009)

Automated as a loop that starts a `passwd` and sends `SIGKILL` after a random
sub-millisecond delay, repeatedly; after each kill the store is loaded and every
account that existed beforehand is verified again.

**Expect**: in every trial the store still parses and still verifies every
account it held before — it is either fully in its old state or fully in its new
one, never a mixture and never empty.

### V9 — Concurrent invocations cannot dodge the lockout (SR-007)

Automated: register an account, then launch 20 concurrent `login` attempts with
the *wrong* password against the same store, wait for all of them, then try the
**correct** password.

**Expect**: the correct password is refused with `account locked` / exit 4 — no
failure-count increment was lost to an interleaving. The stored count is 5, not
some smaller number.

### V10 — Scale and timing (FR-010, SC-007)

```bash
pytest -m slow -k performance
```

**Expect**: a store built with 1 000 accounts; every command completes in under
one second; and the store-scaling component is negligible — the same command
against a 1-account store and a 1 000-account store differ by under 100 ms.
Note the `passwd` headroom caveat in
[research R8](./research.md#r8--performance-budget-against-sc-007).

### V11 — Unusual password content round-trips (spec edge cases, A-009)

```bash
printf 'pâss wörd — ünïcode ✓\n' | python -m accounts --store ./v11.store register eve_x
printf 'pâss wörd — ünïcode ✓\n' | python -m accounts --store ./v11.store login eve_x
printf 'pâss wörd — ünïcode ✓'   | python -m accounts --store ./v11.store login eve_x   # no trailing newline
```

**Expect**: `registered eve_x`/0, then `ok`/0 twice — spaces, punctuation and
non-ASCII characters are all accepted and verify byte-for-byte, and a missing
final terminator makes no difference.

### V12 — Case-sensitive usernames (FR-011)

```bash
printf 'correct-horse-battery\n' | python -m accounts --store ./v12.store register alice
printf 'different-password-x\n'  | python -m accounts --store ./v12.store register Alice
printf 'different-password-x\n'  | python -m accounts --store ./v12.store login Alice
```

**Expect**: both registrations succeed (exit 0) — `Alice` and `alice` are two
distinct accounts — and each verifies only its own password.

## Requirement coverage

Every FR, SR and SC identifier maps to at least one automated test; the mapping
table lives in [plan.md](./plan.md#requirement-to-test-mapping) and
Principle III makes an unmapped requirement a blocker, not a gap.

## Cleanup

```bash
rm -f ./demo.store ./v1.store ./v5.store ./v7.* ./v11.store ./v12.store
```
