# Phase 0 Research: Burn After Reading and Password Protection

**Feature**: `002-burn-after-reading-password` | **Date**: 2026-11-10 | **Plan**: [plan.md](./plan.md)

## Unknowns extracted from Technical Context

The spec's Constraints section carries forward every constraint of feature 001 — Python 3.11+,
standard library only, the `pastebin` package under `src/`, the `python -m pastebin serve --port
PORT --data DIR` command form — and fixes the new wire names (`burn_after_reading`, `password`,
`protected`, `X-Paste-Password`) and status codes. The user input for this phase restates the same
three choices and fixes the test runner (`pytest`). No field of Technical Context is therefore
marked NEEDS CLARIFICATION, and the spec's own Clarifications session has already resolved the five
behavioural questions that were open (UTF-8 header bytes, the widened size bound, claim-before-send,
repeated headers, and a deliberately costly derivation).

What remained open were *how* questions — which standard-library mechanism satisfies each new
requirement, given an implementation that already exists and must not change.

| # | Question | Driving requirements |
|---|----------|----------------------|
| R-01 | Which standard-library derivation gives a salted, 10–200 ms, one-way password hash? | FR-056, FR-073, SC-021 |
| R-02 | How is the derivation's cost kept inside 10–200 ms *on the serving machine*? | FR-073, SC-021 |
| R-03 | Does a verification block concurrent requests for other snippets? | FR-074, FR-042, SC-021 |
| R-04 | How is a one-time snippet claimed atomically, durably, and exactly once? | FR-048, FR-050, FR-051 |
| R-05 | In what order are the checks on a read performed? | FR-049, FR-053, FR-060, FR-061 |
| R-06 | How are the bytes of `X-Paste-Password` recovered and decoded as UTF-8? | FR-058, FR-062 |
| R-07 | How is a repeated `X-Paste-Password` header detected without picking an occurrence? | FR-072 |
| R-08 | How does the stored record gain two fields without making old records damaged? | FR-047, FR-056, FR-067 |
| R-09 | What is the recomputed pre-read body ceiling? | FR-071 |
| R-10 | How are the new behaviours tested — exactly-once under contention, restart, cost band? | SC-012, SC-021, Principle III |

Every finding below was checked against the running interpreter (Python 3.13.17 on this host)
before being recorded; the measurements quoted are from that check.

---

## R-01 — Password derivation

**Decision**: `hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)`
with a fresh 16-byte salt from `secrets.token_bytes(16)` per snippet. Salt, iteration count, and the
32-byte derived key are stored hex-encoded in the snippet's record; verification re-derives with the
record's own salt and iteration count and compares with `secrets.compare_digest`.

**Rationale**: PBKDF2-HMAC-SHA256 is the one costly KDF the standard library offers
unconditionally — `hashlib.pbkdf2_hmac` is always present, OpenSSL-backed where available and with a
pure-Python fallback otherwise — so Principle I is satisfied with no portability caveat. It is
one-way, so FR-056's prohibition on storing a recoverable form holds. Its cost is a single linear
parameter, which is what makes R-02's calibration possible: measured here at 4.3 µs per 1,000
iterations (11.5 ms at 50,000; 46.6 ms at 200,000; 91.3 ms at 400,000), linear across the range.
Its memory cost is negligible, which matters for FR-074: ten concurrent verifications cost ten
hash states, not ten large scratch buffers. Storing the iteration count *in the record* rather than
as a global means a snippet written before a recalibration still verifies (FR-056 across restarts),
and is the same discipline the existing record already applies to `expires_at` — the value is
computed once at publication and never recomputed.

**Alternatives considered**:

- **`hashlib.scrypt`** — memory-hard, and therefore strictly better against custom hardware; measured
  here at 43.6 ms for `n=2**14, r=8, p=1`. Rejected on two grounds. It is conditional: `hashlib.scrypt`
  exists only when the interpreter was linked against an OpenSSL providing scrypt, and raises
  otherwise, so a service that must run "anywhere Python runs" (Principle I's rationale) would need a
  fallback path — two derivations where the spec requires one. And its cost parameter `n` moves in
  powers of two, so tuning into a 10–200 ms band is coarse where PBKDF2's is continuous. Its ~16 MB
  working set also multiplies by concurrency, which FR-074 makes a live concern.
- **`hashlib.blake2b` with a salt and a `person` value** — fast and always available, but *fast* is
  exactly what FR-073 forbids. A single salted BLAKE2b is a few microseconds, so a copy of the
  storage directory would yield a weak password immediately.
- **`secrets.compare_digest` against the password stored in clear** — forbidden outright by FR-056.
- **A per-service pepper outside the storage directory** — would strengthen the threat model FR-073
  names (a stolen copy of the directory), but requires a key file, its lifecycle, and a story for
  what happens when it is lost. No requirement asks for it; Principle IV rejects it.

## R-02 — Keeping the cost inside the required band

**Decision**: measure the host's PBKDF2 rate once, at server construction, and solve for the
iteration count that costs 50 ms:

```text
probe    = min of 3 timings of pbkdf2_hmac(..., PASSWORD_PROBE_ITERATIONS)
iterations = clamp(round(PASSWORD_PROBE_ITERATIONS * 0.05 / probe),
                   MIN_PASSWORD_ITERATIONS, MAX_PASSWORD_ITERATIONS)
```

The result is held on the server object (`httpd.password_iterations`) and passed to
`store.create_paste`; `store` itself stays free of module-level mutable state.

**Rationale**: FR-073 bounds one verification at 10–200 ms *"on the machine serving requests"*, and
SC-021 makes that an asserted test. A hard-coded iteration count cannot satisfy a machine-relative
bound: a count tuned to 50 ms here is 200 ms on a host four times slower and 10 ms on one five times
faster, so the two ends of plausible hardware already span the whole band and a test asserting it
would be hardware-dependent rather than a test of the service. Measuring instead makes the
requirement hold by construction, on whatever host the operator runs, and makes SC-021's test
deterministic. 50 ms is the geometric middle of the band, so a factor of five of measurement noise
or load in either direction still lands inside it. The cost is one measurement of roughly 15 ms at
startup — far inside SC-007's two-second readiness budget — and about twenty lines of code.

The two clamps are sanity rails, not tuning knobs. `MIN_PASSWORD_ITERATIONS` (20,000) stops a
pathologically slow or heavily loaded host from calibrating down to a cost that is cheap to attack;
it binds only on a host roughly ten times slower than this one, where a 50 ms target is unreachable
anyway. `MAX_PASSWORD_ITERATIONS` (5,000,000) stops a probe that measured as near-zero — clock
granularity, or a host so fast the probe is noise — from producing an absurd count. Neither is
reached on this host, where calibration selects roughly 215,000 iterations.

**Alternatives considered**:

- **A fixed constant, e.g. 600,000 iterations** (the current OWASP figure). Simpler by twenty lines,
  and rejected only because of the machine-relative band: 600,000 iterations is 137 ms here and over
  a second on modest hardware, breaching FR-073's ceiling, while on a fast host of a few years hence
  it drops under the floor. If FR-073 were ever amended to name a fixed cost parameter instead of a
  time band, this is the design to revert to.
- **An operator-supplied `--password-cost` option**. A configuration knob with one caller, which
  Principle IV prohibits, and it moves the obligation FR-073 places on the service onto the operator.
- **Recalibrating per request, or periodically**. Strictly worse: it spends the measurement cost
  repeatedly for a parameter that only affects *new* snippets, since verification must use the
  iteration count the record was written with.

**Known limit** (recorded as an assumption rather than solved): on a host where even
`MIN_PASSWORD_ITERATIONS` costs more than 200 ms, no salted costly derivation can satisfy both ends
of FR-073's band at once, and the floor wins — security over latency.

## R-03 — Verification and concurrency

**Decision**: no new mechanism. `ThreadingHTTPServer` already serves each connection on its own
thread (feature 001, R-01), and `hashlib.pbkdf2_hmac` releases the GIL for the duration of the
derivation, so a verification runs on its thread without stalling the interpreter.

**Rationale**: FR-074 forbids a verification from delaying a request about a different snippet, and
FR-042 already obliges the service to serve overlapping requests concurrently. Verified
experimentally on this two-core host: four threads each doing 200,000 iterations finished in 92.5 ms
against 189.3 ms of serial work (2.05× — full use of both cores), and two threads in 52.7 ms against
94.6 ms (1.80×). Had the GIL been held, the speedup would have been 1.0×. No thread pool, no
semaphore, and no work queue is therefore needed, and adding one would be an abstraction with no
requirement behind it (Principle IV).

The derivation is also reached only on a read of a snippet that is actually protected — FR-062 has
the header inspected for no other snippet — so an unprotected read costs exactly what it costs
today.

**Alternatives considered**: a bounded `concurrent.futures.ThreadPoolExecutor` for derivations, to
cap total CPU spent on verification. Rejected: it would *introduce* the queuing delay FR-074
prohibits, as the (n+1)-th verification would wait on the pool.

## R-04 — Claiming a one-time snippet

**Decision**: the claim is a single `os.unlink` of `<DIR>/<id>.json` followed by an `os.fsync` of a
descriptor opened on the storage directory. The caller whose `unlink` succeeds has claimed the
snippet and serves the text it already read into memory; a caller whose `unlink` raises
`FileNotFoundError` lost the race and reports 404. Both the one-time claim and the existing
`DELETE` path go through one `store` helper that unlinks and then fsyncs the directory.

**Rationale**: POSIX `unlink` removes a directory entry atomically and fails with `ENOENT` when the
entry is already gone, which is precisely the exactly-once primitive FR-050 asks for — no lock file,
no index, no tombstone. Verified here over 200 trials of sixteen threads racing to unlink the same
path: exactly one winner and fifteen `FileNotFoundError`s in every trial, with no other error. The
directory `fsync` is what makes the removal *durable* as FR-048 demands — a directory entry removal
is otherwise only in the page cache — and performing it before `send_response` is what satisfies
FR-048's ordering and FR-051's "a restart does not resurrect it", including for the claim whose
response never reached its caller. Because the text was read into memory before the claim, the
winner can serve a complete body (FR-050) and a loser has nothing to serve.

Routing the existing `DELETE` through the same helper is a reduction, not an addition: one durable
removal instead of two near-identical ones. It strengthens FR-031 and changes nothing a caller can
observe, so FR-068 holds (the directory fsync measured 12.3 ms on this host).

An `unlink` that fails for any reason *other* than `ENOENT` means storage is misbehaving; it is
translated to `StoreCorrupt` and reported through the existing damaged-storage path as a 500, which
leaves the snippet unconsumed exactly as FR-049 requires.

**Alternatives considered**:

- **Rename to a unique claim name, then unlink it.** Also exactly-once (`rename`'s source must
  exist), and it would let the winner re-read the text from the claimed file. Rejected as a strictly
  longer route to the same guarantee: the text is already in memory from the validation read, so the
  extra name and extra syscall buy nothing.
- **A `claimed: true` field rewritten into the record.** Needs a read-modify-write that is not atomic
  against a concurrent claim, so it would need a lock, and it leaves the consumed secret on disk —
  worse on every axis.
- **An in-memory set of consumed identifiers.** Lost on restart, which FR-051 forbids, and it would
  be the service's first piece of state outside the storage directory.
- **`O_EXCL` lock files per snippet.** Exactly-once, but leaves litter after an abrupt stop and needs
  a reclamation story no requirement asks for.

## R-05 — Order of checks on a read

**Decision**: `load and validate the record` → `404 if absent, 500 if damaged, 404 if expired` →
`403 if protected and the presented password does not match` → `take the text` →
`claim if one-time, 404 if the claim is lost` → `write the response`.

**Rationale**: this single ordering discharges every precedence rule the spec states. Loading first
makes 404 outrank 403 for an unknown, deleted, or already-consumed identifier (FR-060) and keeps the
endpoint from revealing an identifier a read would not have revealed — the same argument, and the
same order, that feature 001 already uses on `DELETE` (FR-026). Checking expiry before the password
gives FR-053 and User Story 2 scenario 6. Checking the password before the claim is what makes a
protected one-time snippet unburnable by someone who cannot read it (FR-049, SC-013). Claiming after
the text is in hand but before the first byte of the response is written is FR-048's explicit
ordering. Damaged storage is diagnosed by the load, before any claim, so a damaged one-time snippet
is not consumed (FR-049).

**Alternatives considered**: claiming before verifying the password would be cheaper by one failed
derivation and is rejected outright — it would let anyone who could guess a link destroy a snippet
they cannot read, which is the attack SC-013 exists to exclude. Writing the response and then
claiming is rejected by FR-048 and by the spec's own clarification: a snippet served twice cannot be
recalled, a snippet lost unread can be republished.

## R-06 — Recovering the password header's bytes

**Decision**: `self.headers.get_all("X-Paste-Password")[0].encode("latin-1").decode("utf-8")`;
a `UnicodeDecodeError` means the presented bytes match no password and the read is refused as 403.

**Rationale**: `http.client.parse_headers` decodes the whole header block as ISO-8859-1, so the `str`
`http.server` hands over holds one character per original byte. Re-encoding as `latin-1` is therefore
lossless and total — it cannot fail, because every character came from a latin-1 decode — and
recovers the bytes the caller actually sent, which is what FR-058 requires be interpreted as UTF-8.
Verified on the running server: the header bytes `70 c3 a4 73 73 77 c3 b6 72 64 2d c3 a9 e4 b8 ad`
arrive as a 16-character latin-1 string and round-trip to `pässwörd-é中`, so a non-ASCII password is
presentable and matchable. The bytes `ff fe` arrive likewise and raise `UnicodeDecodeError` on the
UTF-8 decode, which is caught and treated as a mismatch — a 403, never the 500 an uncaught decode
error would produce (FR-070).

Catching `UnicodeDecodeError` at exactly this site is a deliberate translation of an exception into a
clearer error, which is the one thing Principle II permits; it is not a swallow, because the outcome
is an explicit refusal.

The header is read only when the snippet is protected, which gives FR-062 for free: an unprotected
snippet is served whatever the header's value or bytes, including invalid UTF-8 and including a
repeated header, because nothing looks at it.

## R-07 — Detecting a repeated header

**Decision**: `self.headers.get_all("X-Paste-Password")` — `None` when the header is absent, a list
of every occurrence otherwise. A list of length other than one is treated as a password that does not
match.

**Rationale**: `self.headers` is an `email.message.Message`, whose `get()` silently returns the
*first* occurrence — which is exactly the behaviour FR-072 forbids, since a correct password smuggled
into a second copy of the header past whatever inspected the first must not open the snippet.
`get_all` is the standard-library way to see all occurrences without choosing one. Verified: a request
carrying `X-Paste-Password: wrong` then `X-Paste-Password: right` yields `get() == "wrong"` and
`get_all() == ["wrong", "right"]`, so only the `get_all` form can detect the repetition at all.
Collapsing "absent", "repeated", and "undecodable" into one refusal is not a loss of information to
the caller: FR-059 and FR-072 make all three the same 403 with the same message, and the spec's edge
cases note that the outcomes are indistinguishable by design.

An empty header value needs no special case: it is a one-element list holding `""`, a presented
password of zero characters, which cannot match any stored password because a stored password is at
least one character (FR-054). It is therefore refused rather than treated as absent, as the spec's
edge cases require, without a line of code saying so.

## R-08 — Extending the stored record

**Decision**: the record gains two keys, `burn_after_reading` (a boolean) and `password` (`null`, or
an object with exactly `iterations`, `salt`, and `hash`). Both are *written always* by this version
and *optional on read*: a record lacking them is valid and means not one-time and not protected.
Validation keeps its shape — five required keys, two optional, any other key still damaged — and the
new values are type-checked as strictly as the existing ones.

**Rationale**: FR-047 and FR-056 require both properties to be durable; FR-067 requires a record
written by the previous version, which names neither key, to read as neither one-time nor protected
rather than as damaged. Making the keys optional on read is exactly that rule, and nothing more
elaborate — no version field, no migration pass, no rewrite-on-read — is needed, because absence
already has an unambiguous meaning. Writing them unconditionally keeps one obvious shape for every
record this version creates, so the absent case is purely the legacy path rather than something the
service produces for itself.

Keeping "any other key is damaged" preserves feature 001's rule and its test, which uses the key name
`surprise` and so is unaffected by the two names now accepted (FR-068, SC-018).

Nesting the three derivation values under one `password` key, rather than adding three flat keys, is
what makes "protected" a single `is not None` test at every site that asks, and makes the invariant
"either all three are present or none is" structural rather than a check. A packed string in the
`algorithm$iterations$salt$hash` style familiar from `passlib` was rejected: it would need its own
parser and its own damaged-record diagnostics, where a nested object is validated by the same few
lines as the rest of the record. There is no `algorithm` field, because there is one algorithm;
adding a field to name it would be a speculative extension point (Principle IV).

## R-09 — The recomputed body ceiling

**Decision**: `MAX_BODY_BYTES = 6 * MAX_CONTENT_BYTES + 12 * MAX_PASSWORD_CHARS + 1_024` =
**395,776** bytes, up from 394,240.

**Rationale**: FR-071 is not a formality — the old ceiling genuinely rejects a submission this spec
deems valid. Measured: the worst-case valid body, with 65,536 bytes of content that JSON escapes
six-for-one, a 128-character password of astral characters that escapes to a twelve-byte surrogate
pair each, and `burn_after_reading`, serialises to 394,811 bytes, which exceeds the old 394,240 and
would be refused as too large. The recomputed bound leaves 965 bytes of headroom over that exact
worst case.

The two added terms are derived the same way feature 001's was. Content stays at six output bytes per
input byte (a C0 control byte becomes `\u0001`; a four-byte astral character becomes a twelve-byte
escaped surrogate pair, only three per input byte). A password is bounded in *characters*, not bytes,
so its worst case is twelve output bytes per character — the same escaped surrogate pair, now counted
per character rather than per byte. The 1,024-byte slack still covers the field names, whitespace, and
the unknown fields FR-015 requires be tolerated; the two new field names add 46 bytes to that
allowance, which it absorbs.

The bound remains a module constant, independent of anything the caller declares, so the memory
protection FR-040 exists for is unchanged (FR-071's final sentence). A submission whose *content*
exceeds 65,536 encoded bytes is still a 413, decided before or after the body is read as it is today.

## R-10 — Testing the new behaviours

**Decision**: four new test modules on the existing fixtures, with no new harness:

- **Exactly-once under contention** (SC-012, FR-050): N threads on the in-process `service` fixture
  released from a `threading.Barrier` onto the same unread one-time snippet; assert exactly one 200
  and N−1 404s, that the one 200 carries the whole text, and that the record file is gone. Repeated
  over many trials — the same shape as the R-04 probe, which produced one winner in 200 of 200 trials.
- **Across a restart** (FR-047, FR-051, FR-056, SC-012, SC-014): the `server_process` fixture
  publishes, is stopped, and a second process is started on the same directory — already how feature
  001 tests durability.
- **The cost band** (FR-073, SC-021): time one read of a protected snippet against one read of an
  unprotected one on the same host and assert the difference falls in 10–200 ms. Because R-02
  calibrates to the host, this is a genuine assertion rather than a hardware lottery. Salt uniqueness
  is read straight off disk: two snippets published with the same password must differ in both `salt`
  and `hash`.
- **Concurrency under verification** (FR-074, SC-021): overlap a read of a protected snippet with
  reads of a *different* unprotected snippet and assert the latter complete without waiting for the
  former — the measurement R-03 already validated.
- **Claim-before-send** (FR-048): assert the ordering by its consequence rather than by instrumenting
  the handler — a caller that reads the response headers and abandons the connection mid-body leaves
  the snippet gone, and the record file is absent the moment a successful read returns.
- **No password anywhere** (FR-057, FR-066, SC-015): publish with a distinctive password, then assert
  it appears in no response body, no response header, and neither captured stream of the
  `server_process` fixture.

**Rationale**: `conftest.py` already provides both server fixtures, raw-socket sends for framing the
`http.client` cannot express (needed for the repeated and invalid-UTF-8 headers), and
`read_record`/`write_record` helpers for inspecting and hand-writing stored records — which is how
the FR-067 legacy-record test writes a five-key record directly. Nothing new is required of the
harness, and runtime code gains no test-only hook (Principle IV).

The only new cost is time: a few dozen protected reads at the calibrated ~50 ms each. Tests that care
about neither the cost nor the band override `service.httpd.password_iterations` downward, which is
legitimate because the iteration count is server state the handler reads, not a constant it embeds.
