# Phase 1 Quickstart: Validating Local Account Manager

**Feature**: `001-local-account-manager` | **Date**: 2026-11-16

How to run the tool and prove the feature works end to end. Scenario text and exit statuses
come from [contracts/cli-contract.md](./contracts/cli-contract.md); the store's internals are
described in [data-model.md](./data-model.md). This is a run-and-verify guide — no
implementation code here.

## Prerequisites

- CPython **3.11 or newer** (`python3 --version`)
- `pytest` (the only development dependency; no runtime dependencies exist)
- A POSIX shell, run from the repository root

```bash
python3 --version          # expect 3.11+
python3 -m pytest --version
```

The commands below are written as `python -m accounts`, the invocation form the spec fixes;
make sure `python` resolves to that 3.11+ interpreter (`python --version`), or substitute
`python3` throughout.

## Setup

Nothing to install or build. The package is run from the source tree with `src/` on the import
path:

```bash
export PYTHONPATH=src
STORE=$(mktemp -d)/store.json       # a fresh path; the file does not exist yet
```

For the test suite, `src/` is placed on the path by `pyproject.toml`
(`[tool.pytest.ini_options] pythonpath = ["src"]`), so a bare `pytest` works with no
environment setup.

## Run the test suite

```bash
pytest                              # expect: all tests pass, 0 failed, 0 skipped
pytest -q tests/test_lockout.py     # one story in isolation
```

Every functional requirement `FR-001`–`FR-038` is named in a test name or docstring, so the
coverage claim in SC-001 is checkable:

```bash
pytest --collect-only -q | grep -c fr_      # expect at least 38 requirement-named tests
grep -rho 'FR-0[0-9][0-9]' tests/ | sort -u | wc -l   # expect 38
```

---

## Scenario 1 — Register and sign in (User Story 1, P1)

```bash
printf 'correct horse battery\n' | python -m accounts --store "$STORE" register alice
# stdout: registered alice        status: 0

printf 'correct horse battery\n' | python -m accounts --store "$STORE" login alice
# stdout: ok                      status: 0   (a separate process — proves persistence)

printf 'wrong password!!\n' | python -m accounts --store "$STORE" login alice
# stderr: invalid credentials     status: 1   stdout empty
```

Check the status explicitly after each command with `echo $?`, and confirm the stream split:

```bash
printf 'wrong password!!\n' | python -m accounts --store "$STORE" login alice 2>/dev/null
# expect no output at all — the diagnostic is on stderr, never stdout
```

Input rejections, each exiting 2 or 3 with a diagnostic naming the rule:

```bash
printf 'short\n'          | python -m accounts --store "$STORE" register bob     # status 2, length rule
printf 'a valid password\n' | python -m accounts --store "$STORE" register ab     # status 2, username rule
printf 'a valid password\n' | python -m accounts --store "$STORE" register bad-name # status 2, username rule
printf 'a valid password\n' | python -m accounts --store "$STORE" register alice  # status 3, already exists
printf '' | python -m accounts --store "$STORE" register carol                    # status 2, no password on stdin
```

Boundary cases worth running by hand: usernames of exactly 3 and 32 characters are accepted,
2 and 33 rejected; a 12-character password is accepted, 11 rejected.

## Scenario 2 — Lockout and recovery (User Story 2, P2)

Four failures then a success — the account must **not** be locked:

```bash
for i in 1 2 3 4; do printf 'nope nope nope\n' | python -m accounts --store "$STORE" login alice; done
# each: stderr invalid credentials, status 1
printf 'correct horse battery\n' | python -m accounts --store "$STORE" login alice
# stdout: ok    status: 0   — and the failure count is now back to zero
```

Five failures — the fifth still reports credentials, and the account locks:

```bash
for i in 1 2 3 4 5; do printf 'nope nope nope\n' | python -m accounts --store "$STORE" login alice; done
# fifth: stderr invalid credentials, status 1   (not "account locked")

printf 'correct horse battery\n' | python -m accounts --store "$STORE" login alice
# stderr: account locked    status: 4   — correct password is refused

printf 'nope nope nope\n' | python -m accounts --store "$STORE" login alice
# stderr: account locked    status: 4   — wrong password, same answer
```

Recover, then confirm access is restored:

```bash
python -m accounts --store "$STORE" unlock alice            # status 0, no stdin read, no output
printf 'correct horse battery\n' | python -m accounts --store "$STORE" login alice
# stdout: ok    status: 0
python -m accounts --store "$STORE" unlock carol            # status 3, no such account
```

## Scenario 3 — Change a password (User Story 3, P3)

```bash
printf 'correct horse battery\nnew longer secret\n' | python -m accounts --store "$STORE" passwd alice
# status 0, no output
printf 'new longer secret\n'     | python -m accounts --store "$STORE" login alice   # ok, status 0
printf 'correct horse battery\n' | python -m accounts --store "$STORE" login alice   # invalid credentials, status 1
```

Rejections, each leaving the stored password untouched:

```bash
printf 'wrong one here\nanother long secret\n' | python -m accounts --store "$STORE" passwd alice  # status 1
printf 'new longer secret\nshort\n'            | python -m accounts --store "$STORE" passwd alice  # status 2, length rule
printf 'new longer secret\n'                   | python -m accounts --store "$STORE" passwd alice  # status 2, no new password on stdin
printf 'whatever long enough\nalso long enough\n' | python -m accounts --store "$STORE" passwd carol # status 3, before reading stdin
```

The combination that matters: a **wrong current password plus a short new password must exit 1**,
not 2 — the length complaint must never confirm that the current password was right.

```bash
printf 'wrong one here\nshort\n' | python -m accounts --store "$STORE" passwd alice   # expect status 1
```

## Scenario 4 — Delete an account (User Story 4, P4)

```bash
printf 'a second password\n' | python -m accounts --store "$STORE" register bob       # status 0
printf 'nope nope nope\n'    | python -m accounts --store "$STORE" delete alice       # status 1, alice survives
printf 'new longer secret\n' | python -m accounts --store "$STORE" delete alice       # status 0
printf 'new longer secret\n' | python -m accounts --store "$STORE" login alice        # invalid credentials, status 1
printf 'a second password\n' | python -m accounts --store "$STORE" login bob          # ok, status 0 — bob unaffected
printf 'whatever long enough\n' | python -m accounts --store "$STORE" delete carol    # status 3
```

The username is free again afterwards:

```bash
printf 'a brand new secret\n' | python -m accounts --store "$STORE" register alice    # registered alice, status 0
```

---

## Cross-cutting checks

### Secrets never leak (FR-036, FR-037, SC-006)

```bash
grep -c 'correct horse battery' "$STORE"   # expect 0 matches (grep exits 1)
cat "$STORE"                               # only base64 salt/verifier, counts, and flags
stat -c '%a' "$STORE"                      # expect 600
```

Two accounts with the same password must hold different verifiers:

```bash
S2=$(mktemp -d)/store.json
printf 'identical password\n' | python -m accounts --store "$S2" register user_one
printf 'identical password\n' | python -m accounts --store "$S2" register user_two
python3 -c "import json,sys; a=json.load(open(sys.argv[1]))['accounts']; \
print(a['user_one']['verifier'] != a['user_two']['verifier'])" "$S2"   # expect True
```

### Store failures are loud (FR-007, FR-008)

```bash
BAD=$(mktemp -d)/bad.json
printf 'this is not a store\n' > "$BAD"
python -m accounts --store "$BAD" login alice
# stderr names the file and the problem; status non-zero (2); the file is NOT overwritten
cat "$BAD"                                  # unchanged

printf 'a valid password\n' | python -m accounts --store /nonexistent-dir/store.json register alice
# stderr names the path; status 2
```

### Missing store behaves as an empty store

```bash
FRESH=$(mktemp -d)/none.json
printf 'a valid password\n' | python -m accounts --store "$FRESH" login alice   # status 1
python -m accounts --store "$FRESH" unlock alice                                # status 3
test -e "$FRESH" || echo "no file created"                                      # expect: no file created
```

### Passwords with spaces and non-ASCII characters (FR-017)

```bash
WS=$(mktemp -d)/ws.json
printf '  leading and trailing  \n' | python -m accounts --store "$WS" register spacey
printf '  leading and trailing  \n' | python -m accounts --store "$WS" login spacey   # ok, status 0
printf 'leading and trailing\n'     | python -m accounts --store "$WS" login spacey   # status 1 — spaces matter
printf 'pässwörd-с-юникодом\n'      | python -m accounts --store "$WS" register unico # status 0 (19 characters, 29 bytes)
```

### Extra stdin lines are ignored

```bash
printf 'a valid password\nextra line\n\n' | python -m accounts --store "$WS" register extras   # status 0
```

### Usage errors (FR-035)

```bash
python -m accounts login alice                             # status 2, missing --store
python -m accounts --store "$STORE"                        # status 2, missing command
python -m accounts --store "$STORE" frobnicate alice       # status 2, unknown command
python -m accounts --store "$STORE" login                  # status 2, missing username
python -m accounts --store "$STORE" login alice extra      # status 2, extra argument
```

### Performance (SC-007)

```bash
BIG=$(mktemp -d)/big.json
for i in $(seq 1 1000); do printf 'bulk password %d\n' "$i" | \
  python -m accounts --store "$BIG" register "user_$i" >/dev/null; done
time (printf 'bulk password 500\n' | python -m accounts --store "$BIG" login user_500)
# expect well under 1s (budget: ~145 ms PBKDF2 + a few ms of JSON load and atomic rewrite)
```

## Cleanup

```bash
rm -f "$STORE" "$S2" "$BAD" "$FRESH" "$WS" "$BIG"
unset PYTHONPATH
```

## Done when

- `pytest` passes in full, with no skipped tests.
- All four scenarios above produce exactly the stated stdout, stderr, and exit statuses.
- The cross-cutting checks all hold: no password in the store's bytes, mode `600`, distinct
  verifiers for identical passwords, loud failures on a bad store, and exit 2 on every usage
  error.
