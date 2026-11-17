# Phase 0 Research: Administrator-Issued Password Reset

**Feature**: `002-password-reset` | **Date**: 2026-11-16

Decisions continue the numbering of feature 001's research (R-01 – R-08), so a reference like
"R-10" is unambiguous repository-wide. R-01 – R-08 still stand unchanged; this file records only
what the password-reset feature adds or constrains.

The spec left no `NEEDS CLARIFICATION` marker: its **Assumptions** section already settles one
outstanding token per account, the positive validity window, the deliberately uninformative
`invalid token`, locked-account behaviour, and irreversible token storage. What remained were
implementation choices, and one genuine conflict between FR-039 and an existing test, which R-13
resolves.

---

## R-09: Token generation — `secrets.token_urlsafe(32)`

**Decision**: A token is `secrets.token_urlsafe(32)`: 32 random bytes from the OS CSPRNG,
rendered as 43 characters of URL-safe base64 without padding, drawn from `[A-Za-z0-9_-]`.

**Rationale**: FR-040 asks for three properties at once and this satisfies all three with one
stdlib call. *Cryptographically suitable, ≥128 bits*: `secrets` is the stdlib's CSPRNG-backed
module and 32 bytes is 256 bits, double the floor. *Survives copy-paste as one line*: the
alphabet contains no whitespace, no newline, no quote, no backslash, no shell metacharacter, and
no character that a terminal, chat client, or spreadsheet will transform — the administrator
passes the token on out of band (spec Assumptions), so paste-safety is a functional property,
not a nicety. *Differs from every previously issued token*: with 256 bits of entropy, a repeat
has probability below 2⁻¹²⁸ even across astronomically many issuances, which is what "MUST
differ" can mean for a value the store deliberately cannot recall (FR-057 forbids keeping tokens
in recoverable form, so a uniqueness registry is not available even in principle). The testable
form of FR-040 is therefore: many tokens issued in a tight loop, including twice for the same
account in the same second, are all distinct and all match `\A[A-Za-z0-9_-]{43}\Z`.

A leading `-` is possible (the alphabet includes it) and harmless: FR-048 forbids the token from
ever being a command-line argument, so it is never in a position where a parser could read it as
an option.

**Alternatives considered**:

- `secrets.token_hex(16)` — 128 bits, 32 hex characters, alphabet `[0-9a-f]`. Equally safe and
  marginally friendlier to read aloud, but at the FR-040 floor rather than comfortably above it,
  and longer per bit. Rejected for having no advantage in a value that is pasted, not retyped.
- `secrets.token_bytes(32)` with our own base64 — `base64.urlsafe_b64encode` plus stripping `=`
  reimplements `token_urlsafe` exactly. Rejected as code for no gain.
- `uuid.uuid4()` — 122 bits of entropy, and the hyphenated form invites truncation at a
  delimiter. Rejected: below the stated floor and shaped for identifiers, not secrets.
- A human-friendly grouped format (`xxxx-xxxx-xxxx`) — would need a separate alphabet decision,
  a grouping decision, and normalization on input (is `XXXXXXXXXXXX` the same token?). No
  requirement asks for readability, and normalization is exactly the input-coercion Principle II
  prohibits. Rejected.

---

## R-10: Token at rest — PBKDF2-HMAC-SHA256 verifier with a fresh per-token salt

**Decision**: Reuse `passwords.new_salt()`, `passwords.derive()`, and `passwords.verify()`
unchanged. Issuing a token stores `{salt: <16 random bytes>, verifier: <PBKDF2 of the token
under that salt, 32 bytes>, expires_at: ...}`. Validation re-derives from the presented token
and compares with `hmac.compare_digest`. The token itself is never written anywhere.

**Rationale**: FR-057 states the requirement in exactly these terms — "a one-way transformation
of the token with a per-token random salt, in the same manner already required of passwords
(FR-036)" — so reusing the existing functions is the literal reading *and* the simplest design:
zero new crypto code, zero new store-format parameters, and the record's `salt`/`verifier`
fields are 16 and 32 bytes just like an account's, so `store._validate_base64` validates them
with no new helper (Principle IV). `hmac.compare_digest` keeps token validation from leaking a
prefix match through timing, which matters more for a token than for a password because a token
is pasted by whoever holds it. Cost is acceptable: one derivation measures **0.150 s** on the
development machine, so `reset-token` spends one and `reset` spends two (token verify, then the
new password's verifier) — about 0.30 s against SC-016's 1-second budget.

A fresh salt per token also means two tokens issued for two accounts, or successively for one
account, have unrelated verifiers even in the vanishingly unlikely event the tokens collide.

**Alternatives considered**:

- Single-pass salted SHA-256 for tokens, keeping PBKDF2 for passwords. Defensible on the merits:
  a 256-bit random token has no guessable structure, so key stretching — whose entire purpose is
  to slow brute force against low-entropy human secrets — buys nothing, and this would halve
  `reset`'s cost. Rejected because it adds a *second* one-way transformation to a four-module
  codebase and its own parameters to the store format, in exchange for 0.15 s the budget already
  affords by 3×; FR-057's "in the same manner" points the other way. Recorded here as the first
  thing to change if SC-016 ever turns out tight on slower hardware.
- Storing the token in plaintext, or reversibly encrypted. Rejected outright by FR-057 and
  SC-014: a store file readable by an attacker must not hand them a usable password reset, and an
  encryption key would have to live beside the store to be usable.
- A single store-wide token salt. Rejected: FR-057 says per-token, and a shared salt lets one
  precomputation attack every token at once.
- Reusing the account's password salt for its token. Rejected: it couples two independent
  secrets' storage, and regenerating the salt on a successful `passwd` would silently invalidate
  an outstanding token, which the spec's edge case explicitly forbids ("the token remains usable").

---

## R-11: Store schema — an optional `reset_token` key, `version` stays `1`

**Decision**: The store format stamp remains `version: 1`. An account record keeps its four
required keys (`salt`, `verifier`, `failed_logins`, `locked`) and gains exactly one **optional**
key, `reset_token`. Absence of the key is the only representation of "no outstanding token";
`reset_token: null` is rejected, not interpreted.

**Rationale**: FR-059 requires a store file written before this feature to load "without
complaint" and to read as an account with no outstanding token. Those files say `version: 1`, so
the stamp must keep accepting `1`. Making the new key optional satisfies FR-059 directly: the old
file validates under the unchanged required-key set, and `reset_token not in record` means no
token with no migration step, no rewrite on load, and no upgrade path to test. The strict
unknown-key rejection from 001 (rule 4) is preserved by moving `reset_token` from "unknown" to
"known optional" — so a hand-edited store with a misspelled `reset_tokens` still fails loudly.

Rejecting `null` matters: two spellings of the same state ("key absent" and "key null") is a
distinction the code would have to keep straight forever, and accepting `null` would be a
default applied to input the format does not define — prohibited by Principle II. One
representation, enforced at load.

**Alternatives considered**:

- Bump to `version: 2`. Rejected: old files stamped `1` would then fail validation, breaking
  FR-059. Accepting both `1` and `2` would mean two formats, two validation paths, and a
  migration decision on save, all to record information the optional key already carries.
- A separate top-level `tokens` object keyed by username, beside `accounts`. Rejected: it adds a
  second place where an account's state lives, so `delete` would need to clean up two structures
  (the spec requires deleting an account to take its token with it) and a token could outlive its
  account as orphaned state. Nesting the token in the record makes that correct by construction.
- A sidecar token file next to the store. Rejected: the tool's defining property is a *single*
  store file, and two files cannot be replaced atomically together.

---

## R-12: Expiry — one absolute `expires_at`, valid while `now < expires_at`

**Decision**: Store a single field, `expires_at`, as a float of Unix epoch seconds computed at
issuance as `time.time() + ttl`. A token is valid when `now < expires_at` and invalid at and
after that instant. `expires_at` is validated at load as a finite `int` or `float` (never a
`bool`, never `NaN` or `±Infinity`).

**Rationale**: One field, one comparison, no arithmetic at validation time — the smallest thing
that expresses FR-041. The boundary follows the requirement's words: a token is valid "until
`SECONDS` seconds have elapsed, and MUST NOT be valid thereafter", so at exactly the moment the
window has elapsed it has elapsed, and the strict `<` is the faithful reading. A float preserves
the sub-second instant of issuance, so a 1-second window is exactly one second rather than
rounded into a different window than the operator asked for.

The finiteness check is the Fail Loudly principle catching a real trap: `json.loads` accepts the
literals `NaN`, `Infinity`, and `-Infinity` by default, and `now < NaN` is `False` for every
`now` — so a hand-edited or corrupted `expires_at: NaN` would produce a token that is silently
permanently invalid, and `Infinity` one that never expires, each looking like ordinary behaviour.
Both are now a `StoreError` naming the field. The system clock is the only clock available (spec
Assumptions; a single-process local tool with no network and no trusted time source), and the
spec's "Clock movement" edge case accepts its semantics explicitly.

**Alternatives considered**:

- `issued_at` + `ttl` as two fields, computing expiry at validation. Rejected: two fields and an
  addition to express one instant, and it tempts a future reader to "re-interpret" an old token's
  window. The TTL is not needed after issuance — nothing in the spec reports it back.
- Integer `expires_at` (whole seconds). Rejected: rounding makes a short window silently shorter
  or longer than requested, which an expiry-boundary test would then have to tolerate.
- `time.monotonic`. Rejected: not comparable across processes, which is the only comparison that
  matters here — the token is issued by one process and used by another.
- `datetime.now(timezone.utc).isoformat()` strings. Rejected: a parse step on every load, and
  string comparison that is only ordered by accident of format. A float needs neither.

---

## R-13: `--ttl` in the parser — flat parser, `help=argparse.SUPPRESS`, explicit scope check

**Decision**: Keep the existing single flat `argparse` parser. Add `reset-token` and `reset` to
the `command` positional's `choices`. Register `--ttl` on that same parser with
`help=argparse.SUPPRESS` and a strict `type` (R-14), then, immediately after `parse_args` and
inside the existing redirect block, reject it when the command is not `reset-token`:

```python
if args.ttl is not None and args.command != "reset-token":
    parser.error("--ttl is only valid with the reset-token command")
```

`parser.error` prints the usage message and the error line to the (redirected) stderr and exits
2, which is byte-for-byte the shape of every other usage failure (E13), so FR-043 lands on the
established path rather than a bespoke one.

**Rationale**: This was the one real conflict in the feature, and it is a conflict between two
requirements of the spec itself, not a free choice.

`tests/test_cli_usage.py` contains, for FR-003, this assertion:

```python
options = {token.split("=")[0].rstrip(",") for token in out.split() if token.startswith("--")}
assert options == {"--store", "--help"}
```

It scans the *whole* `--help` output and demands the set of `--`-prefixed tokens be exactly those
two. FR-060 and SC-011 require that test to pass **unmodified**. FR-039 requires `--ttl` to
exist. `help=argparse.SUPPRESS` is what reconciles them: a suppressed action appears in neither
the usage line nor the options list — verified empirically against CPython 3.13, where the
extraction above still yields exactly `{'--store', '--help'}` — while `--ttl` parses and behaves
exactly as specified. The option is documented in `contracts/cli-contract.md` and in the spec.

Keeping the parser flat also preserves two things the five existing commands have today and
FR-060 protects. First, `--store` is accepted anywhere on the line, so
`python -m accounts login alice --store ./s.json` keeps working. Second, a usage error for an
existing command still prints the same top-level usage message. The only unavoidable change to
that message is the `choices` list growing by two names — which is what adding commands *is*, and
which no test asserts.

**Alternatives considered**:

- **`argparse` subparsers** — the textbook way to scope an option to one subcommand, and it would
  satisfy FR-043 with no code at all while keeping top-level help clean. Rejected because it
  changes more observable surface than it saves: every existing command's usage error would print
  its subparser's usage line (`usage: python -m accounts login [-h] username`) instead of today's
  top-level one, and `--store` would stop being accepted after the command name. Both are
  observable changes to existing commands, which FR-060 forbids "of any kind". Restoring the
  `--store` position would need a per-subparser `--store` with `default=argparse.SUPPRESS` plus a
  manual required-check — more argparse subtlety than the one `if` above, for a worse outcome.
- **Visible `--ttl` help, and edit the FR-003 test.** The cleanest-looking option and arguably
  what the project owner will eventually want, since FR-003's actual requirement is that no
  option accepts a *password* and the test over-constrains it to "no option exists". Rejected
  here because SC-011 is explicit and a plan should not quietly relax a success criterion; the
  one-line alternative is flagged in plan.md's Complexity Tracking for the owner to decide.
- **A separate parser for the two new commands**, dispatched by pre-scanning `argv` for the
  command token. Rejected: hand-rolled argv scanning ahead of the parser is exactly the fragile
  code `argparse` exists to remove, and it would duplicate `--store` handling.
- **An environment variable instead of an option.** Rejected: FR-039 fixes the invocation form,
  and an invisible input channel is worse for an operator than a suppressed flag.

---

## R-14: `--ttl` value validation — strict decimal digits, then `>= 1`

**Decision**: A custom `type` callable for `--ttl` that accepts only a string of ASCII decimal
digits matching `\A[0-9]+\Z` and converting to `>= 1`, raising `argparse.ArgumentTypeError`
otherwise. Argparse turns that into a usage diagnostic on stderr with exit 2 (E17), satisfying
FR-042 through the existing usage path.

**Rationale**: FR-042 says `--ttl` is "accepted only as a positive whole number of seconds" and
that anything else is a usage error that issues no token and leaves the store unchanged. Plain
`type=int` is too permissive to express that: `int()` accepts `"1_000"` → 1000, `"+5"` → 5,
`" 10 "` → 10, and `"١٢٣"` → 123. Each of those is `int()` coercing input into something the
operator did not write, which Principle II prohibits ("defaulting, coercing, or truncating
invalid input in order to continue is prohibited") — and a `--ttl 1_000` silently meaning 1000
seconds is precisely the plausible-wrong-answer class the constitution calls most severe. The
strict character-set test is also the established house style: `commands._USERNAME` rejects
`str.isalnum()`'s non-ASCII breadth for the same reason (001 data-model.md).

Rejecting zero and negatives follows the spec's assumption that a window which can never be used
is a mistake worth reporting, not an instruction to honour. There is no upper bound: the spec
says any positive integer is accepted and a window longer than the operator will ever wait is
their choice.

Checking the value inside the `type` callable rather than after parsing keeps all four rejection
reasons (non-numeric, zero, negative, malformed) on one path with one message shape, and means an
invalid `--ttl` fails before any store is read — "no token issued, store unchanged" is then true
by construction rather than by a later guard.

**Alternatives considered**:

- `type=int` plus a separate `if args.ttl < 1` check. Rejected: accepts the coerced forms above,
  and splits one requirement across two places.
- `type=int, choices=range(1, ...)`. Rejected: needs an arbitrary upper bound the spec declines
  to set, and argparse would print the whole range in its error.
- Silently clamping a zero or negative window to 1 second, or to the 900-second default.
  Rejected: that is the prohibited defaulting, and it would issue a token under a window the
  operator never asked for.

---

## R-15: Check order for the two new commands

**Decision**:

```text
reset-token : --ttl valid (E17) → --ttl in scope (E16) → store loads → exists? (E4)
              → issue, supersede any previous token, save
reset       : store loads → exists? (E4) → token line present (E14)
              → new-password line present (E9) → token valid? (E15) → new length (E1)
              → replace password, clear token, save
```

**Rationale**: Every step's position is pinned by a requirement, and the order is observable
because it decides which of two simultaneous problems gets reported.

- Existence before any read is FR-054, matching FR-034's existing rule for `unlock`, `passwd`,
  and `delete`. As in 001, this is implemented as a short pre-pass in `cli._dispatch`: for a
  missing account, `commands.reset` is called with `None` for both lines and returns E4 without a
  single `readline`, so "exits 3 without consuming input" is structural.
- Both end-of-input checks before judging the token is FR-055, and the spec is explicit about the
  consequence: a wrong token with a missing password line reports the missing password, not
  `invalid token`. End of input is never an empty value (FR-055, and FR-018 before it) — an
  *empty but present* line is a token value like any other, and simply fails to match (spec edge
  case), which is why the distinction between `""` and `None` is load-bearing here exactly as it
  is for passwords (001 R-06).
- Token before password length is FR-053, mirroring `passwd`'s verify-before-length (FR-028): the
  status-2 length complaint must never be reachable with a token that was not accepted, or the
  reply would confirm a guessed token was real.
- Length failure leaves the token outstanding, so that path returns `save=False` and mutates
  nothing — the token stays usable for the immediate retry US3 requires.
- For `reset-token`, `--ttl` validation precedes the store read because FR-042 requires a bad
  window to leave the store untouched with no token issued; failing in the parser makes that
  unconditional.

**Alternatives considered**: reading both stdin lines before the existence check, which would
simplify `_dispatch` into a single uniform path for all seven commands. Rejected: it breaks
FR-054 observably — a mistyped username would consume the administrator's input before reporting
the typo. The pre-pass already exists for three commands; `reset` joins the pattern.

---

## R-16: No store write on any token-rejection path; expired tokens are not swept

**Decision**: A rejected token (wrong, superseded, already used, expired, or none outstanding)
returns `Result(1, err="invalid token\n", save=False)`. Nothing is written, and an expired
`reset_token` record stays in the store until it is superseded by a new token or removed with the
account.

**Rationale**: FR-052 requires the account's stored password, failed-login count, and lock state
to be unchanged, and the 001 contract's store-side-effects table makes "no write on any failure
except a failed login" an established property (FR-006 is the single documented exception, and a
rejected token is explicitly *not* a failed login under FR-056). Sweeping expired tokens would
mean a store write on a status-1 path, which would be a new exception to that rule, would make an
invalid-token attempt against a read-only store fail with a *write* error instead of
`invalid token`, and would let an observer distinguish "expired" from "wrong" by watching the
file's mtime — undercutting FR-052's requirement that the five rejection cases be
indistinguishable.

The residue is bounded and harmless: at most one token record per account, holding only a salt, a
verifier, and a timestamp, from which the token cannot be recovered (FR-057). No requirement asks
for cleanup, so adding it would be unspecified work (Principle IV).

**Alternatives considered**:

- Clear the expired token on the attempt that notices it. Rejected for the three reasons above.
- Clear expired tokens opportunistically during any command's save. Rejected: it makes every
  command a mutator of other accounts' token state, which FR-060 forbids for the five existing
  commands.

---

## R-17: Extending the requirement-coverage ledger — the one existing test file that changes

**Decision**: `tests/test_requirement_coverage.py` is extended to span both features: it reads
`specs/001-local-account-manager/spec.md` and `specs/002-password-reset/spec.md`, and asserts the
union of defined identifiers is exactly `FR-001` – `FR-062`, that every one of them is referenced
by some test, and that no test references an identifier no spec defines. Its three existing
assertions for FR-001 – FR-038 are preserved, not loosened. Every other existing test file is
untouched.

**Rationale**: This file is not a behaviour test of the tool; it is the SC-001 bookkeeping ledger,
and it is hard-coded to 38 requirements in both directions. Its second assertion — "no test
references a requirement the spec does not define" — scans `tests/` for `FR-0\d\d` and fails on
any mention of `FR-039`+. So the moment the new tests cite their requirements, as Principle III
requires them to, this file must change. There is no arrangement that avoids it: suppressing the
citations would break the discoverable mapping the constitution demands.

The spec sanctions this directly. Its final assumption reads: "Requirement numbering continues
the existing sequence ... so that identifiers remain unique repository-wide and **the existing
requirement-to-test coverage check stays meaningful**." Extending the ledger is what keeping it
meaningful means. SC-011's "the complete existing test suite for FR-001 – FR-038 passes
unmodified" is satisfied in substance: the ledger still requires all 38 to be mapped, and not one
assertion about the tool's behaviour is edited. This is called out in plan.md's structure table so
the exception is visible rather than buried in a diff.

**Alternatives considered**:

- A second file, `test_requirement_coverage_002.py`, leaving the first alone. Rejected: it does
  not work. The *existing* file's reverse check still fails on the new tests' `FR-039`+ citations.
- Keeping FR citations out of the new tests' text (e.g. citing "US1 scenario 2" instead).
  Rejected: Principle III requires the requirement-to-test mapping to be discoverable by
  identifier, and SC-009 counts 24 of 24 mapped requirements.
- Widening the regex to make 001's ledger ignore FR-039+ — still an edit to the same file, with a
  weaker result.

---

## R-18: Test strategy for the new commands

**Decision**: Reuse the in-process seam and the three existing fixtures (`run_cli`, `store_path`,
`read_store`) from `tests/conftest.py` with no change. Six new test files, split by requirement
group (see plan.md). Expiry is tested by passing an explicit `now` to the command functions
(Complexity Tracking) rather than by sleeping; the CLI-level expiry path is covered once with a
`--ttl 1` token and a short real sleep, so the wiring from `cli` to the clock is also asserted.
SC-014 is tested by issuing a token and asserting its 43 characters appear nowhere in the store
file's bytes; SC-013 by running all five rejection cases and asserting byte-identical
`("invalid token\n", 1)` from each.

**Rationale**: 001 R-08 established the in-process seam for exactly this reason — a requirement
matrix this size would cost minutes of interpreter startup as subprocesses and microseconds in
process. The fixtures already return `(status, stdout, stderr)`, which is the triple every new
requirement is stated in. The one real sleep is the price of asserting that `cli` passes the
actual clock and not a stub; one second in the whole suite is acceptable, and the exhaustive
boundary cases stay instant at the `commands` level.

**Alternatives considered**: subprocess-driving every new case for maximum fidelity. Rejected on
the same grounds as 001 — kept only for the end-to-end worked examples, where the point *is* the
real `python -m accounts` invocation.

---

## Resolved unknowns

| From Technical Context | Resolution |
|---|---|
| Token format and entropy source | R-09: `secrets.token_urlsafe(32)`, 256 bits, `[A-Za-z0-9_-]{43}` |
| How a token is stored irreversibly | R-10: existing PBKDF2-HMAC-SHA256 at 600,000 iterations with a fresh 16-byte per-token salt |
| How the store stays backward compatible | R-11: `version` stays `1`; one optional `reset_token` record key; `null` rejected |
| How expiry is represented and judged | R-12: float `expires_at` epoch seconds, valid while `now < expires_at`, finiteness validated |
| How `--ttl` is scoped to one command without changing the others | R-13: flat parser, `help=argparse.SUPPRESS`, one explicit `parser.error` check |
| How `--ttl` values are validated | R-14: strict `\A[0-9]+\Z` and `>= 1` inside the argparse `type` |
| Observable check order for both commands | R-15: pinned step by step to FR-042, FR-053, FR-054, FR-055 |
| Whether rejection paths write the store | R-16: never; expired tokens are not swept |
| Whether any existing test must change | R-17: one file, the SC-001 coverage ledger, extended to FR-001 – FR-062 |
| Performance against SC-016 | 0.150 s per derivation measured: `reset-token` ≈ 0.15 s, `reset` ≈ 0.30 s, ~3× margin |
