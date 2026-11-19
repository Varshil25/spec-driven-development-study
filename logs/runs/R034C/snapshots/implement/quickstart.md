# Phase 1 Quickstart: validating Administrator-Issued Password Reset

**Feature**: `002-password-reset` | **Date**: 2026-11-16

How to prove this feature works end to end, by hand and by suite. Behaviour referenced here is
specified in [contracts/cli-contract.md](./contracts/cli-contract.md) and
[data-model.md](./data-model.md); this file does not restate it and contains no implementation
code.

## Prerequisites

- Python **3.11 or newer** (`pyproject.toml` → `requires-python`). No runtime dependency exists or
  may be added (Constitution Principle I).
- `pytest`, the only development dependency: `python -m pip install -e '.[dev]'`
- A shell at the repository root. `src/` must be on the import path — `pythonpath = ["src"]` is
  already configured for `pytest`; for manual runs use `PYTHONPATH=src`.

## Run the suite

```bash
pytest                       # bare invocation from the repository root; must be fully green
pytest -q tests/test_reset.py tests/test_reset_token.py
pytest -q -k "fr05 or fr04"  # the new requirement groups
```

Three gates the suite itself enforces:

| Gate | What asserts it | Criterion |
|---|---|---|
| Every new requirement is covered, in both directions | `tests/test_requirement_coverage.py` (extended to FR-001 – FR-062, see research.md R-17) | SC-009 |
| The existing suite still passes **unmodified** | `git diff --stat tests/` shows changes only to `test_requirement_coverage.py` and the six new files | SC-011 |
| Neither new command is slow at scale | `tests/test_reset_performance.py` | SC-016 |

Expected runtime: a little over the 001 baseline. `reset` performs two PBKDF2 derivations at
600,000 iterations (~0.15 s each), and one test sleeps ~1 s to exercise real-clock expiry through
the CLI (research.md R-18).

## Scenario 1 — the recovery journey (User Story 1, SC-012)

The whole feature in two commands: one run by the administrator, one by the user, with no hand
editing of the store and the administrator never seeing the new password.

```bash
export PYTHONPATH=src
STORE=$(mktemp -d)/store.json

printf 'correct horse battery\n' | python -m accounts --store "$STORE" register alice
TOKEN=$(python -m accounts --store "$STORE" reset-token alice)   # administrator
printf '%s\nmy brand new secret\n' "$TOKEN" | python -m accounts --store "$STORE" reset alice
```

**Expect**: `registered alice`, then a single 43-character token line, then `password reset` — each
on stdout with exit status 0 and nothing on stderr. That `TOKEN=$(...)` captures a usable token is
itself part of the contract: the line carries the token and nothing else.

Then confirm the password actually changed:

```bash
printf 'my brand new secret\n'   | python -m accounts --store "$STORE" login alice; echo "new -> $?"
printf 'correct horse battery\n' | python -m accounts --store "$STORE" login alice; echo "old -> $?"
```

**Expect**: `ok` with `new -> 0`; then `invalid credentials` on stderr with `old -> 1` (FR-050).

## Scenario 2 — a token cannot be reused, guessed, or outlived (User Story 2, SC-013)

Each case must produce byte-identical `invalid token` on stderr with status 1, and must leave the
stored password working. Run them against the store from Scenario 1.

```bash
# (a) already used — reuse the token from Scenario 1
printf '%s\nyet another secret\n' "$TOKEN" | python -m accounts --store "$STORE" reset alice; echo $?

# (b) wrong token
printf 'definitely-not-a-real-token\nyet another secret\n' \
  | python -m accounts --store "$STORE" reset alice; echo $?

# (c) no token ever issued
printf 'correct horse battery\n' | python -m accounts --store "$STORE" register bob
printf 'anything\nyet another secret\n' | python -m accounts --store "$STORE" reset bob; echo $?

# (d) superseded — the first of two tokens
FIRST=$(python -m accounts --store "$STORE" reset-token alice)
SECOND=$(python -m accounts --store "$STORE" reset-token alice)
printf '%s\nyet another secret\n' "$FIRST" | python -m accounts --store "$STORE" reset alice; echo $?

# (e) expired
SHORT=$(python -m accounts --store "$STORE" reset-token alice --ttl 1)
sleep 2
printf '%s\nyet another secret\n' "$SHORT" | python -m accounts --store "$STORE" reset alice; echo $?
```

**Expect**: `invalid token` and `1` five times, with stdout empty every time and no two responses
distinguishable. Then check that `$SECOND` — the surviving token from (d), superseded by the
`--ttl 1` issuance in (e) and therefore *also* dead — is rejected too, and that
`printf 'my brand new secret\n' | python -m accounts --store "$STORE" login alice` still prints
`ok`.

## Scenario 3 — a rejected password does not waste the token (User Story 3, SC-015)

```bash
TOKEN=$(python -m accounts --store "$STORE" reset-token alice)
printf '%s\nshort\n' "$TOKEN" | python -m accounts --store "$STORE" reset alice; echo $?
printf '%s\ntwelve chars ok\n' "$TOKEN" | python -m accounts --store "$STORE" reset alice; echo $?
```

**Expect**: `password must be at least 12 characters` on stderr with `2`, then `password reset` on
stdout with `0` — the same token, accepted on the retry. Also confirm the ordering rule: a *wrong*
token with a too-short password reports `invalid token` and `1`, never the length error
(FR-053).

## Scenario 4 — unknown accounts, and `--ttl` validation (User Story 4, FR-042, FR-043)

```bash
python -m accounts --store "$STORE" reset-token nobody; echo $?        # 3, names the account
printf 'tok\npassword here ok\n' | python -m accounts --store "$STORE" reset nobody; echo $?  # 3

for BAD in 0 -5 abc 10.0 1e3 1_000 +5; do
  python -m accounts --store "$STORE" reset-token alice --ttl "$BAD" >/dev/null; echo "$BAD -> $?"
done
python -m accounts --store "$STORE" --ttl 60 login alice; echo $?      # 2: --ttl out of scope
```

**Expect**: `3` for both unknown-account cases with a diagnostic naming `nobody` and nothing on
stdout; `2` for every `--ttl` value in the loop — including `1_000` and `+5`, which `int()` would
have silently coerced; and `2` for `--ttl` on `login`. Confirm no token was issued by any of these
and that the store file's modification time is unchanged.

## Scenario 5 — nothing that worked before has changed (User Story 5, SC-011)

```bash
pytest -q tests/test_cli_usage.py tests/test_register.py tests/test_login.py \
          tests/test_passwd.py tests/test_delete.py tests/test_lockout.py \
          tests/test_store.py tests/test_end_to_end.py tests/test_performance.py
git diff --stat tests/
python -m accounts --help | grep -c -- --ttl    # expect 0
```

**Expect**: all green with no edit to any of those files; `git diff --stat tests/` listing only
`test_requirement_coverage.py` plus the six new files; and `--ttl` absent from `--help`, which is
what keeps the FR-003 option-set assertion true (research.md R-13).

Then the compatibility check (FR-059) — a store written *before* this feature:

```bash
OLD=$(mktemp -d)/old.json
cat > "$OLD" <<'JSON'
{
  "version": 1,
  "accounts": {
    "carol": {
      "salt": "3Q2+7wAAAAAAAAAAAAAAAA==",
      "verifier": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
      "failed_logins": 0,
      "locked": false
    }
  }
}
JSON
python -m accounts --store "$OLD" unlock carol; echo $?                              # 0
printf 'anything\npassword here ok\n' | python -m accounts --store "$OLD" reset carol; echo $?  # 1
python -m accounts --store "$OLD" reset-token carol >/dev/null; echo $?              # 0
```

**Expect**: the file loads with no complaint, `carol` behaves as an account with no outstanding
token (`invalid token`, status 1), and issuing one works. Strictness must still hold — add a
`"reset_tokens": {}` key or an `"expires_at": NaN` and every command must exit 2 with a
`not a valid store file:` diagnostic naming the field, never a defaulted value.

## Scenario 6 — the token never touches the store or a diagnostic (FR-057, FR-058, SC-014)

```bash
FRESH=$(mktemp -d)/fresh.json
printf 'correct horse battery\n' | python -m accounts --store "$FRESH" register dave >/dev/null
TOKEN=$(python -m accounts --store "$FRESH" reset-token dave)
grep -c -- "$TOKEN" "$FRESH"                      # expect 0 matches (grep exits 1)
printf '%s\nshort\n' "$TOKEN" | python -m accounts --store "$FRESH" reset dave 2>&1 \
  | grep -c -- "$TOKEN"                           # expect 0 matches
```

**Expect**: no match in either place. The store holds only a salt, a PBKDF2 verifier, and an
`expires_at`, and the only line in the tool that ever carries a token is `reset-token`'s stdout.

## Done when

- [ ] `pytest` is fully green from the repository root, with no skipped test.
- [ ] Scenarios 1–6 all produce the expected statuses and exact text.
- [ ] `git diff --stat tests/` shows no edit to any existing behaviour test (SC-011).
- [ ] `git diff pyproject.toml` is empty — `dependencies` is still `[]` (Principle I).
- [ ] `tests/test_requirement_coverage.py` maps FR-001 – FR-062 with no gap in either
      direction (SC-009).
