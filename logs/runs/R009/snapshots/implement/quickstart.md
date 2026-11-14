# Quickstart & Validation Guide: Local Account Manager CLI

**Feature**: `001-accounts-cli` | **Spec**: [spec.md](./spec.md) | **Contract**: [contracts/cli.md](./contracts/cli.md)

Runnable scenarios that prove the feature works end to end. Every command below is meant to be
pasted into a shell from the repository root. Exit statuses are read with `echo $?` immediately
after the command.

## Prerequisites

- Python **3.11 or newer** (`python3 --version`). Verified on 3.13.17.
- **pytest** for the suite (`pip install -r requirements-dev.txt`). The runtime itself needs
  nothing beyond the standard library (Principle I).
- No setup step beyond choosing a store path (SC-003).

```bash
export PYTHONPATH=src           # required for `python -m accounts` (FR-001)
STORE=$(mktemp -d)/accounts.json
```

---

## Scenario 1 — Register and log in (User Story 1, SC-003)

```bash
printf 'correct horse battery\n' | python -m accounts --store "$STORE" register alice
# → stdout: registered alice   exit 0   and "$STORE" now exists

printf 'correct horse battery\n' | python -m accounts --store "$STORE" login alice
# → stdout: ok                 exit 0

printf 'wrong horse battery\n'   | python -m accounts --store "$STORE" login alice
# → stderr: invalid credentials exit 1
```

Two commands take an operator from nothing to a verified password. The second `login` is a
separate process reading the store the first invocation wrote (FR-002).

Rejections:

```bash
printf 'short\n'                 | python -m accounts --store "$STORE" register bob
# → stderr: password too short   exit 2   (no account bob)
printf 'correct horse battery\n' | python -m accounts --store "$STORE" register bad-name
# → stderr: invalid username     exit 2
printf 'correct horse battery\n' | python -m accounts --store "$STORE" register alice
# → stderr: username already exists  exit 3
printf 'anything at all here\n'  | python -m accounts --store "$STORE" login nobody
# → stderr: invalid credentials  exit 1   (unknown account looks like a wrong password)
```

## Scenario 2 — Lockout and unlock (User Story 2, SC-006)

```bash
for i in 1 2 3 4 5; do
  printf 'definitely wrong pw\n' | python -m accounts --store "$STORE" login alice
  echo "attempt $i → $?"          # each prints invalid credentials, exit 1
done

printf 'correct horse battery\n' | python -m accounts --store "$STORE" login alice
# → stderr: account locked       exit 4   (the correct password no longer works)

python -m accounts --store "$STORE" unlock alice   # reads nothing on stdin
# → no output                    exit 0

printf 'correct horse battery\n' | python -m accounts --store "$STORE" login alice
# → stdout: ok                   exit 0
```

The fifth failing attempt itself reports `invalid credentials` / 1; the lock bites from the
next `login` (FR-015). `unlock` also resets the tally, so four fresh wrong attempts do not
re-lock the account (FR-017). See the transition table in
[data-model.md](./data-model.md#lock-and-failure-tally-state).

## Scenario 3 — Change the password (User Story 3)

```bash
printf 'correct horse battery\nnew passphrase here\n' \
  | python -m accounts --store "$STORE" passwd alice
# → no output                    exit 0   (current password first, then new)

printf 'new passphrase here\n'   | python -m accounts --store "$STORE" login alice
# → stdout: ok                   exit 0
printf 'correct horse battery\n' | python -m accounts --store "$STORE" login alice
# → stderr: invalid credentials  exit 1   (the old password is gone)

printf 'new passphrase here\nshort\n' | python -m accounts --store "$STORE" passwd alice
# → stderr: password too short   exit 2   (password unchanged)
printf 'not the password\nanother long one\n' | python -m accounts --store "$STORE" passwd alice
# → stderr: invalid credentials  exit 1   (checked before the length rule)
```

## Scenario 4 — Delete an account (User Story 4)

```bash
printf 'new passphrase here\n'   | python -m accounts --store "$STORE" delete alice
# → no output                    exit 0
printf 'new passphrase here\n'   | python -m accounts --store "$STORE" login alice
# → stderr: invalid credentials  exit 1   (behaves as a username that never existed)
printf 'a brand new password\n'  | python -m accounts --store "$STORE" register alice
# → stdout: registered alice     exit 0   (the name is free again)
```

## Scenario 5 — Passwords never reach the command line (SC-007)

```bash
python -m accounts --store "$STORE" login alice 'correct horse battery'
# → stderr: usage: python -m accounts --store PATH {register|login|unlock|passwd|delete} USERNAME
#   exit 2 — the extra argument is a usage error, never used as a password
python -m accounts --store "$STORE" login alice < /dev/null
# → stderr: missing password input   exit 2
python -m accounts login alice      # --store omitted
# → the same usage line             exit 2
```

Only the store path, command word and username are ever arguments (FR-006, SC-007).

## Scenario 6 — No password is recoverable from the store (SC-005)

```bash
grep -c 'correct horse battery' "$STORE" || echo "plaintext not found (expected)"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(json.dumps(d, indent=2))" "$STORE"
# → each record holds only: algorithm, iterations, salt, key, failed_logins, locked
ls -l "$STORE"   # → -rw------- (owner-only, FR-029c)
```

Register two accounts with the *same* password and compare their `salt` and `key`: both differ,
because the salt is drawn per account (FR-026, SC-005). Field meanings:
[contracts/store-file.md](./contracts/store-file.md).

## Scenario 7 — An unusable store fails loudly (FR-029)

```bash
printf 'not json at all\n' > "$STORE"
printf 'correct horse battery\n' | python -m accounts --store "$STORE" login alice
# → stderr: store unusable: <cause>   exit 5   (never silently treated as empty)

python -m accounts --store "$(mktemp -d)" unlock alice            # path is a directory
# → stderr: store unusable: <cause>   exit 5
python -m accounts --store /nonexistent/dir/store.json unlock alice
# → stderr: store unusable: <cause>   exit 5
```

A path that simply does not exist yet is **not** an error — it is the empty store (FR-002).

---

## Running the automated suite

```bash
pytest                      # from the repository root, no environment setup needed
pytest -q --durations=10    # confirm the SC-009 budget: suite under 60 s
```

`pytest.ini` sets `pythonpath = src` and `testpaths = tests`, so a bare `pytest` works from
the root (constitution: Project Layout). Expected: **zero failures, zero skips** (SC-001).

### What the suite must demonstrate

| Criterion | How it is validated |
|---|---|
| SC-001 | Every FR has ≥ 1 test naming it; the suite passes with zero failures |
| SC-002 | Every exit status 0–5 and every message string asserted for equality, on the correct stream |
| SC-003 | Scenario 1 above, as a test: fresh path → register → login, no setup step |
| SC-004 | 50 registrations across 50 independent invocations, then 50 successful logins |
| SC-005 | Raw store bytes searched for each known password; two same-password accounts compared |
| SC-006 | Every ordering of correct/wrong attempts containing five consecutive failures locks |
| SC-007 | Argument surface asserted; a password in argument position never authenticates |
| SC-008 | Each failure path: full store state compared before and after |
| SC-009 | Per-command wall clock under 1 s against a 1,000-account store; derivation count per command; suite under 60 s |

### Timing note

One PBKDF2 derivation at 600,000 iterations costs ~213 ms, so the suite's cost is dominated by
derivation count, not by test count. Bulk tests (SC-004, SC-009's 1,000-account store)
monkeypatch `accounts.hashing.DEFAULT_ITERATIONS` down for their duration — sound because every
record carries its own iteration count (FR-026b) — while the 600,000 default and the real
`python -m accounts` subprocess path are asserted separately at full cost. Rationale and
measurements: [research.md](./research.md) D-008.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `No module named accounts` | `PYTHONPATH=src` not set for the `python -m` form |
| `missing password input` when a password was typed | No trailing newline, or stdin was redirected from `/dev/null`; use `printf 'pw\n'` |
| `store unusable: ...` on a path you expected to work | Parent directory missing, path is a directory, permissions, or the file holds non-store content |
| `account locked` after testing wrong passwords | Five consecutive failures; run `unlock` |
