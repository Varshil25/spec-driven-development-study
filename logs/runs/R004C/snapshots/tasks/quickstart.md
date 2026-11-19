# Quickstart & Validation Guide: Password Reset by One-Time Token

**Feature**: `002-password-reset` | **Date**: 2026-11-05

How to run the extended tool and how to prove this feature works end to end.
Continues the numbering of
[feature 001's guide](../001-user-accounts-cli/quickstart.md) (V1 … V12), whose
scenarios all still apply and are re-run unchanged as **V13**.

Interface details are in
[contracts/cli-contract.md](./contracts/cli-contract.md); field rules in
[contracts/store-format.md](./contracts/store-format.md); entity rules in
[data-model.md](./data-model.md). Nothing is duplicated here.

## Prerequisites

- **Python 3.11 or newer** (A-013, planning input). No install step, no runtime
  dependency — standard library only (Principle I).
- **POSIX** host: `fcntl.flock` and `os.replace` are hard requirements.
- `pytest` for the suite only — a development dependency, declared in
  `requirements-dev.txt` and never imported by `src/` (Principle I).

```bash
cd <repo root>
python3 --version                 # expect 3.11 or newer
python3 -m pip install -r requirements-dev.txt   # pytest, for tests only
```

## Running the tool

`src/` goes on `PYTHONPATH`; there is nothing to install (A-013).

```bash
export PYTHONPATH=src
export STORE=./demo.store
```

### Issue a token (administrator)

```bash
python -m accounts --store "$STORE" reset-token alice < /dev/null
python -m accounts --store "$STORE" reset-token alice --ttl 60 < /dev/null
```

Prints the token on a line of its own and nothing else; exit 0. Reads no input,
so it works with stdin closed. Default validity is 900 seconds.

### Redeem it (account holder)

```bash
printf '%s\n%s\n' "$TOKEN" "$NEW_PASSWORD" \
  | python -m accounts --store "$STORE" reset alice
```

Prints `password reset`; exit 0. Reads exactly two lines — token, then new
password.

### Capture a token for scripted use

```bash
TOKEN=$(python -m accounts --store "$STORE" reset-token alice < /dev/null)
```

Safe because the token is the only thing on stdout on success, and its alphabet
contains no whitespace, quoting or control characters (A-023, SR-011).

## Running the suite

```bash
python3 -m pytest                      # everything except the slow markers is fast
python3 -m pytest -m "not slow"        # skip the 1 000-account, concurrency, crash and expiry waits
python3 -m pytest tests/test_reset.py tests/test_reset_token.py -v
python3 -m pytest tests/test_compatibility.py -v   # proves feature 001 is untouched
```

`pytest.ini` already sets `pythonpath = src` and `testpaths = tests`. The suite
drives the real executable in a subprocess with piped streams, so it asserts the
operator-visible contract rather than internal function returns.

**Every password and token literal the suite uses is synthetic** and defined
only in `tests/conftest.py` (constitution, secrets hygiene). Real tokens are
captured from stdout at runtime and never committed.

---

## Validation scenarios

Each is runnable, states its expected outcome, and names the requirements and
the test file that automates it. V13–V23 are new; V1–V12 are feature 001's and
are re-run unchanged.

### V13 — Feature 001 still passes, unchanged (US5, FR-040, SC-019)

**The gate for this whole feature.** Run the complete existing suite against the
extended tool.

```bash
python3 -m pytest tests/test_cli_contract.py tests/test_register.py \
  tests/test_login_lockout.py tests/test_passwd.py tests/test_delete.py \
  tests/test_store_format.py tests/test_security.py tests/test_concurrency.py \
  tests/test_crash_safety.py tests/test_performance.py tests/test_example_sequence.py
```

**Expected**: all pass. The **only** permitted edit to any of those files is the
two diagnostic strings of A-025 in `tests/test_cli_contract.py` (the usage line
and the unknown-command message, both of which enumerate the operation names).
Any other changed assertion means the feature regressed the tool, not that the
test was wrong.

**Automated by**: the files above, plus
`tests/test_compatibility.py::test_a025_only_two_diagnostics_changed`.

### V14 — Issue and redeem across two invocations (US1, FR-028, SC-013)

```bash
rm -f "$STORE"
printf 'quarry-lantern-glide\n' | python -m accounts --store "$STORE" register alice
TOKEN=$(python -m accounts --store "$STORE" reset-token alice < /dev/null); echo "exit=$?"
printf '%s\ncobalt-meadow-stencil\n' "$TOKEN" | python -m accounts --store "$STORE" reset alice
printf 'cobalt-meadow-stencil\n' | python -m accounts --store "$STORE" login alice
printf 'quarry-lantern-glide\n'   | python -m accounts --store "$STORE" login alice
```

**Expected**: the token line then `exit=0`; `password reset` and 0; `ok` and 0;
then `invalid credentials` and 1 — the old password is dead. No setup step
between issuing and redeeming.

**Automated by**: `tests/test_reset.py`.

### V15 — The token works only once (US2, FR-035, SC-013)

Repeat the redemption from V14 with the same `$TOKEN` and a different password.

**Expected**: `invalid token` on stderr, exit 1, empty stdout, and the password
set by the first redemption still verifies.

**Automated by**: `tests/test_reset_invalid_token.py`.

### V16 — Every refusal is indistinguishable (US2, SR-018, SC-018)

Compare the five refusal paths: never issued; already redeemed; replaced by a
later issuance; expired; and an account that never had a token. Also try an
empty token line, a token issued for another account, and the account's own
current password on the token line.

**Expected**: all eight produce byte-identical stderr (`invalid token`),
identical exit status 1, identical empty stdout, and comparable wall-clock time.
`stat` the store before and after each: byte-identical, and `failed_logins` is
unchanged — a wrong token can neither lock the account nor be slowed by a
lockout (FR-039, A-020).

**Automated by**: `tests/test_reset_invalid_token.py`,
`tests/test_reset_security.py`.

### V17 — Validity is honoured at both ends (FR-030, SC-014)

```bash
T1=$(python -m accounts --store "$STORE" reset-token alice --ttl 5 < /dev/null)
printf '%s\nharbor-mellow-quartz\n' "$T1" | python -m accounts --store "$STORE" reset alice
T2=$(python -m accounts --store "$STORE" reset-token alice --ttl 1 < /dev/null)
sleep 2
printf '%s\nthistle-amber-driftx\n' "$T2" | python -m accounts --store "$STORE" reset alice
```

**Expected**: the immediate redemption succeeds (`password reset`, 0); the
expired one is refused (`invalid token`, 1). Expiry is read from the clock at the
moment of the attempt, never cached from the issuing run.

**Automated by**: `tests/test_reset.py` (marked `slow` where it waits).

### V18 — A refused new password does not burn the token (US3, FR-036, SC-017)

```bash
T=$(python -m accounts --store "$STORE" reset-token alice < /dev/null)
printf '%s\nelevenchars\n' "$T"  | python -m accounts --store "$STORE" reset alice   # 11 chars
printf '%s\ntwelvecharss\n' "$T" | python -m accounts --store "$STORE" reset alice   # 12 chars
```

**Expected**: first → `error: new password too short: expected at least 12
characters, received 11` on stderr, exit **2**, empty stdout, stored password
unchanged, token still outstanding **with its original expiry**. Second →
`password reset`, exit 0. Also check the over-long case (status 2, token
survives) and that an **expired** token with an 11-character password answers
`invalid token`/1 rather than 2 — the token is judged before the password
(scenario 3.4).

**Automated by**: `tests/test_reset.py`.

### V19 — Reissuing replaces; tokens do not cross accounts (FR-029, A-015)

Issue twice for `alice` and confirm the first value is dead and the second
works. Issue for `alice` and `bob`, then present each token against the other
account.

**Expected**: the replaced token and the wrong-account token both give
`invalid token`/1; each correct pairing succeeds. At most one token is ever
outstanding per account. `Alice` and `alice` are two accounts with independent
tokens.

**Automated by**: `tests/test_reset_token.py`,
`tests/test_reset_invalid_token.py`.

### V20 — Locked accounts: the recovery path works and clears the lock (FR-031, FR-034, A-018)

Drive `alice` to five failed logins, then issue and redeem a token.

**Expected**: both operations succeed on the locked account (**never** status
4), the reset clears the lock and zeroes `failed_logins`, and the new password is
accepted immediately afterwards. `reset-token` alone leaves the lock state and
count exactly as they were.

**Automated by**: `tests/test_reset.py`, `tests/test_reset_token.py`.

### V21 — Bad requests change nothing, and never create the store (US4, FR-027, FR-032, FR-038)

```bash
python -m accounts --store ./does-not-exist reset-token alice < /dev/null ; echo "exit=$?"
ls ./does-not-exist* 2>&1
python -m accounts --store "$STORE" reset-token ab < /dev/null               ; echo "exit=$?"
python -m accounts --store "$STORE" reset-token alice --ttl 0 < /dev/null    ; echo "exit=$?"
python -m accounts --store "$STORE" reset-token alice --ttl abc < /dev/null  ; echo "exit=$?"
python -m accounts --store "$STORE" reset-token alice --ttl 100000 < /dev/null; echo "exit=$?"
python -m accounts --store "$STORE" reset-token alice --ttl 60 --ttl 60 < /dev/null; echo "exit=$?"
python -m accounts --store "$STORE" login alice --ttl 60 < /dev/null         ; echo "exit=$?"
python -m accounts --store "$STORE" reset alice < /dev/null                  ; echo "exit=$?"
```

**Expected**, in order: 3 with `error: no such account 'alice'` and **no file
created**; 2 (invalid username); 2, 2, 2 (invalid ttl, message naming expected
and received); 2 with the usage line (`--ttl` twice); 2 with the usage line
(`--ttl` on another command); 2 with `error: missing reset input: expected a
token line then a new password line on stdin, received 0 line(s)`. Also check
the stream closing after the token line only → 2, `received 1 line(s)`. Every
case leaves the store byte-identical and issues no token.

**Automated by**: `tests/test_reset_token.py`, `tests/test_reset.py`.

### V22 — The token leaks nowhere (SR-013, SR-017, SR-018, SC-015, SC-016)

After every operation, search the store file, any file left beside it, and both
streams for the issued token value.

**Expected**: zero occurrences anywhere except the one stdout line that printed
it. The store holds only a salted scrypt digest and an expiry. No sidecar, spool
or log file exists. No password, salt, digest, parameter, expiry instant or
stack trace appears on either stream.

Also: 10 000 tokens generated in-process are all distinct, each decodes to
exactly 16 bytes (128 bits), and the package never imports `random`.

**Automated by**: `tests/test_reset_security.py`.

### V23 — Malformed reset material is loud (SR-010)

Hand-write stores (synthetic material only) in which `reset` is not an object,
is missing `expires_ms`, has `expires_ms` as a string / float / `true` /
negative / above the cap, has a ninth key, or has a bad salt length.

**Expected**: every one is `error: store 'PATH' is malformed: <structural
reason>` with exit **5**, for both new operations and for the existing five. In
particular a malformed `expires_ms` is **not** treated as "not expired" — the
load fails rather than the token being accepted. No account is created, deleted
or altered.

**Automated by**: `tests/test_store_format.py`,
`tests/test_reset_security.py`.

### V24 — Concurrency, crash safety and performance (SC-022, SC-023, SC-024)

```bash
python3 -m pytest -m slow -v
```

**Expected**:

- two simultaneous redemptions of one valid token → exactly one `password
  reset`/0 and one `invalid token`/1, and the password afterwards is the one set
  by the single success;
- `SIGKILL` during issuance or redemption → the store still parses and every
  account it held before still verifies;
- `reset-token` and `reset` each finish in under one second on a 1 000-account
  store.

**Note on the last one**: `reset` performs two deliberate scrypt derivations
(verify the token, hash the new password) at ≈ 0.40 s each on the development
host, so it lands at ≈ 0.81 s — about 1.2× headroom against the one-second
bound, the same position `passwd` is in. The store-size component is ~6 ms, so
this is a statement about host CPU, not about the design. See
[research R20](./research.md#r20--performance-budget-and-a-flagged-tightness)
and the plan's flagged notes.

**Automated by**: `tests/test_concurrency.py`, `tests/test_crash_safety.py`,
`tests/test_performance.py`.

### V25 — The documented sequence reproduces exactly (SC-025)

```bash
python3 -m pytest tests/test_example_sequence.py -v
```

**Expected**: the sequence in
[contracts/cli-contract.md](./contracts/cli-contract.md#worked-example-sequence)
reproduces line for line and status for status, with the token captured at
runtime rather than hard-coded.

---

## Definition of done for this feature

From the constitution's Development Workflow, checked against this feature:

- [ ] Every FR-020 … FR-043 and SR-010 … SR-018 maps to a passing `pytest`
      test — see the plan's
      [requirement-to-test mapping](./plan.md#requirement-to-test-mapping).
- [ ] Error paths assert the **message and the exit status** together, not just
      the status.
- [ ] Security requirements are tested as **negatives** too: the wrong, used,
      replaced, expired and never-issued token; the out-of-range `--ttl`; the
      over-long and non-UTF-8 token line; the malformed stored reset material;
      the token-leakage searches.
- [ ] The full suite passes, including V13 — feature 001 unchanged apart from
      the two A-025 strings.
- [ ] No third-party runtime import added; `pytest` stays development-only.
- [ ] No placeholder, stub or `TODO` in the delivered path.
