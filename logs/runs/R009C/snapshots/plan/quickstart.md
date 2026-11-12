# Quickstart & Validation Guide: Password reset by one-time token

**Feature**: `002-password-reset` | **Spec**: [spec.md](./spec.md) | **Contract**: [contracts/cli.md](./contracts/cli.md)

Runnable scenarios that prove the feature works end to end. Paste each block into a shell from
the repository root; read exit statuses with `echo $?` immediately after a command. The 001
guide ([`../001-accounts-cli/quickstart.md`](../001-accounts-cli/quickstart.md)) still covers
the five existing commands.

## Prerequisites

- Python **3.11 or newer** (`python3 --version`). Verified on 3.13.17.
- **pytest** for the suite (`pip install -r requirements-dev.txt`). The runtime needs nothing
  beyond the standard library (Principle I).
- No setup step and no migration: an existing store file works as it is (FR-039).

```bash
export PYTHONPATH=src           # required for `python -m accounts` (FR-001)
STORE=$(mktemp -d)/accounts.json
printf 'correct horse battery\n' | python -m accounts --store "$STORE" register alice
```

---

## Scenario 1 — Issue a token and reset the password (User Story 1, SC-011)

```bash
TOKEN=$(python -m accounts --store "$STORE" reset-token alice)
echo "$?"                        # 0 — and nothing was written to stderr
echo "$TOKEN"                    # one line, 43 characters of [A-Za-z0-9_-]

printf '%s\nbrand new passphrase\n' "$TOKEN" |
  python -m accounts --store "$STORE" reset alice
# → stdout: password reset       exit 0

printf 'brand new passphrase\n'  | python -m accounts --store "$STORE" login alice
# → stdout: ok                   exit 0
printf 'correct horse battery\n' | python -m accounts --store "$STORE" login alice
# → stderr: invalid credentials  exit 1   (the old password is gone)
```

Three commands take a user from a forgotten password back to a working login, with no setup
step (SC-011). The `$(...)` capture working is itself the point of FR-032's "the token and
nothing else, on a line of its own": no label to strip, no line to select.

Two tokens are never the same (FR-034a):

```bash
A=$(python -m accounts --store "$STORE" reset-token alice)
B=$(python -m accounts --store "$STORE" reset-token alice)
[ "$A" != "$B" ] && echo "distinct, as required"
```

…and only the newer one works — issuing replaced the first (FR-032):

```bash
printf '%s\nanother good passphrase\n' "$A" |
  python -m accounts --store "$STORE" reset alice
# → stderr: invalid token        exit 1   (A was replaced by B)
printf '%s\nanother good passphrase\n' "$B" |
  python -m accounts --store "$STORE" reset alice
# → stdout: password reset       exit 0
```

## Scenario 2 — A reset recovers a locked-out account (User Story 1, FR-036b, SC-011)

```bash
for i in 1 2 3 4 5; do
  printf 'wrong one\n' | python -m accounts --store "$STORE" login alice
done                             # five refusals; the account is now locked

printf 'another good passphrase\n' | python -m accounts --store "$STORE" login alice
# → stderr: account locked       exit 4

T=$(python -m accounts --store "$STORE" reset-token alice)
printf 'another good passphrase\n' | python -m accounts --store "$STORE" login alice
# → stderr: account locked       exit 4   — issuing a token alone does NOT unlock (FR-032)

printf '%s\nrecovered passphrase\n' "$T" | python -m accounts --store "$STORE" reset alice
# → stdout: password reset       exit 0

printf 'recovered passphrase\n'   | python -m accounts --store "$STORE" login alice
# → stdout: ok                   exit 0   — no `unlock` was run (FR-036b)
```

## Scenario 3 — Wrong, spent and expired tokens are refused (User Story 2, SC-012, SC-013)

```bash
T=$(python -m accounts --store "$STORE" reset-token alice)

printf 'not-the-token\nperfectly fine passphrase\n' |
  python -m accounts --store "$STORE" reset alice
# → stderr: invalid token        exit 1

printf '%s\nperfectly fine passphrase\n' "$T" |
  python -m accounts --store "$STORE" reset alice
# → stdout: password reset       exit 0
printf '%s\nyet another passphrase\n' "$T" |
  python -m accounts --store "$STORE" reset alice
# → stderr: invalid token        exit 1   — single use (FR-036c)

printf 'perfectly fine passphrase\n' | python -m accounts --store "$STORE" login alice
# → stdout: ok                   exit 0   — the first reset's password still stands
```

Expiry, with real elapsed time (FR-036d):

```bash
SHORT=$(python -m accounts --store "$STORE" reset-token alice --ttl 1)
sleep 2
printf '%s\nexpired attempt passphrase\n' "$SHORT" |
  python -m accounts --store "$STORE" reset alice
# → stderr: invalid token        exit 1
```

A `passwd` cancels an outstanding token (FR-038a):

```bash
T=$(python -m accounts --store "$STORE" reset-token alice)
printf 'perfectly fine passphrase\nchanged it myself ok\n' |
  python -m accounts --store "$STORE" passwd alice      # exit 0, no output
printf '%s\nreset after passwd now\n' "$T" |
  python -m accounts --store "$STORE" reset alice
# → stderr: invalid token        exit 1
```

## Scenario 4 — A too-short password leaves the token usable (User Story 3, SC-017)

```bash
T=$(python -m accounts --store "$STORE" reset-token alice)

printf '%s\nshortpass11\n' "$T" | python -m accounts --store "$STORE" reset alice
# → stderr: password too short   exit 2   (11 characters)

printf '%s\ntwelvechars!\n' "$T" | python -m accounts --store "$STORE" reset alice
# → stdout: password reset       exit 0   — same token, accepted (FR-036f)
```

The token is judged before the password's length (FR-036a):

```bash
T=$(python -m accounts --store "$STORE" reset-token alice)
printf 'wrong-token\nshort\n' | python -m accounts --store "$STORE" reset alice
# → stderr: invalid token        exit 1   (not `password too short` / 2)
```

## Scenario 5 — Unknown accounts, bad `--ttl`, missing input (User Story 4, FR-033, FR-036)

```bash
python -m accounts --store "$STORE" reset-token nobody
# → stderr: no such account      exit 3   (nothing on stdout)
printf 'tok\ngood long passphrase\n' | python -m accounts --store "$STORE" reset nobody
# → stderr: no such account      exit 3

python -m accounts --store "$STORE" reset-token alice --ttl 0
python -m accounts --store "$STORE" reset-token alice --ttl abc
python -m accounts --store "$STORE" reset-token alice --ttl 86401
python -m accounts --store "$STORE" reset-token alice --ttl
python -m accounts --store "$STORE" passwd alice --ttl 900
# → each: the usage line on stderr, exit 2, store untouched (FR-033, FR-040)

python -m accounts --store "$STORE" reset-token alice --ttl 1       # accepted
python -m accounts --store "$STORE" reset-token alice --ttl 86400   # accepted

printf '' | python -m accounts --store "$STORE" reset alice
# → stderr: missing password input  exit 2
printf 'only-the-token-line\n' | python -m accounts --store "$STORE" reset alice
# → stderr: missing password input  exit 2
```

The usage line, in full (FR-040):

```text
usage: python -m accounts --store PATH {register|login|unlock|passwd|delete|reset-token|reset} USERNAME [--ttl SECONDS]
```

## Scenario 6 — The token is not in the store (FR-034b, SC-014)

```bash
T=$(python -m accounts --store "$STORE" reset-token alice)

grep -c -- "$T" "$STORE" || echo "token not present in plaintext — as required"
python - "$STORE" "$T" <<'PY'
import base64, hashlib, json, sys
store, token=[REDACTED:assigned_secret][1], sys.argv[2]
raw = open(store, "rb").read()
for form in (token.encode(), token.encode().hex().encode(),
             base64.b64encode(token.encode())):
    assert form not in raw, "token recoverable from the store!"
record = json.loads(raw)["accounts"]["alice"]["reset_token"]
assert record["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
print("stored only as a SHA-256 fingerprint:", record["token_hash"][:16] + "...")
print("ttl_seconds:", record["ttl_seconds"], " issued_at:", record["issued_at"])
PY
```

Feeding the stored fingerprint back as the token is refused — it is not the token (SC-014):

```bash
HASH=$(python -c 'import json,sys;print(json.load(open(sys.argv[1]))["accounts"]["alice"]["reset_token"]["token_hash"])' "$STORE")
printf '%s\nhash as token now\n' "$HASH" | python -m accounts --store "$STORE" reset alice
# → stderr: invalid token        exit 1
```

## Scenario 7 — Compatibility with a pre-feature store (FR-039, SC-019)

```bash
OLD=$(mktemp -d)/old.json
cat > "$OLD" <<'JSON'
{"format": "accounts-store-v1", "accounts": {"carol": {
  "algorithm": "pbkdf2_hmac_sha256", "iterations": 600000,
  "salt": "3Q2+7wAAAAAAAAAAAAAAAA==",
  "key": "f6bX4m3kZ0F0bkYyR2hXb1lkV2hUZ0kyZ0kyZ0kyZ0k=",
  "failed_logins": 0, "locked": false}}}
JSON

python -m accounts --store "$OLD" unlock carol      # exit 0 — loads unchanged, no migration
printf 'tok\ngood long passphrase\n' | python -m accounts --store "$OLD" reset carol
# → stderr: invalid token        exit 1   — an account with no token state
python -m accounts --store "$OLD" reset-token carol >/dev/null   # exit 0
python -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["format"])' "$OLD"
# → accounts-store-v1            — the marker never changed
```

Malformed token state is a corrupt store, not an absent token (FR-039):

```bash
BAD=$(mktemp -d)/bad.json
python - "$BAD" <<'PY'
import json, sys
json.dump({"format": "accounts-store-v1", "accounts": {"dave": {
    "algorithm": "pbkdf2_hmac_sha256", "iterations": 600000,
    "salt": "3Q2+7wAAAAAAAAAAAAAAAA==",
    "key": "f6bX4m3kZ0F0bkYyR2hXb1lkV2hUZ0kyZ0kyZ0kyZ0k=",
    "failed_logins": 0, "locked": False,
    "reset_token": {"token_hash": "nope", "ttl_seconds": 900}}}}, open(sys.argv[1], "w"))
PY
python -m accounts --store "$BAD" reset-token dave
# → stderr: store unusable: <cause>   exit 5
```

---

## Running the automated suite

```bash
pip install -r requirements-dev.txt
pytest                                    # bare invocation from the repository root
pytest tests/test_reset_token.py tests/test_reset.py tests/test_reset_criteria.py
pytest -k "FR_036 or FR_038"              # requirement identifiers are in the test names
```

Expected: **zero failures**, whole suite within 60 seconds (SC-018). The shipped tests for the
five existing commands pass with the two usage-line literals updated and nothing else changed
(SC-010, [research.md](./research.md) D-019).

### Expiry in the suite, without waiting (research.md D-015)

One test uses `--ttl 1` and a real ~1.1 s sleep. The rest — including the 900-second default
of SC-013 — rewrite `issued_at` in the store file to a chosen point in the past with the
existing `write_store` fixture and then run `reset`: a store whose token was issued an hour ago
is indistinguishable from one an earlier invocation wrote. No clock seam exists in runtime code
to patch, deliberately.

### What to check before calling the feature done

| Gate | How |
|---|---|
| Every FR has a covering test naming it | grep the suite for each of FR-031…FR-044 (Principle III, SC-016) |
| Every message and status asserted exactly | `password reset`, `invalid token`, `no such account`, `password too short`, `missing password input`, the usage line, `store unusable: ` (SC-016) |
| The shipped suite still passes | `pytest tests/test_cli_contract.py tests/test_register.py tests/test_login_lockout.py tests/test_unlock.py tests/test_passwd.py tests/test_delete.py tests/test_hashing.py tests/test_store_file.py` (SC-010) |
| No new runtime dependency | no import outside the stdlib in `src/accounts/`; `requirements-dev.txt` still reads `pytest` alone (Principle I) |
| Suite inside budget | `time pytest` under 60 s (SC-018) |
