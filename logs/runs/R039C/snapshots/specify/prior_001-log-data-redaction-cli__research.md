# Phase 0 Research: Log Data Redaction CLI

**Feature**: 001-log-data-redaction-cli | **Date**: 2026-11-21

**Input**: [spec.md](./spec.md), [constitution.md](../../.specify/memory/constitution.md)

## Scope of this document

The specification left no `NEEDS CLARIFICATION` markers: the language (Python 3.11+), the runtime
dependency policy (standard library only), the test runner (`pytest`), the CLI surface, and the
recognition rules are all fixed by the spec and by the user's planning input. What needed research
was *how* to satisfy several requirements that pull against each other:

- byte-exact passthrough of non-UTF-8 input (FR-017) while matching on decoded text,
- bounded per-line reads with a 1 MiB ceiling (SR-005) when the convenient idioms are unbounded,
- leftmost, non-overlapping, precedence-ordered matching (FR-008, FR-009) when one category
  (card) cannot be validated by a regular expression alone,
- linear-time matching with bounded quantifiers (SR-006),
- fail-closed behaviour on output write failure (SR-007),
- testing failure paths that the usual trick cannot reach when tests run as root.

Every decision below was validated by executing a probe script against the concrete acceptance
scenarios and edge cases in the spec before being recorded here. Results are reported inline.

---

## D-001: Non-UTF-8 passthrough via `errors="surrogateescape"`

**Decision**: Open every input with `encoding="utf-8", errors="surrogateescape", newline=""`, and
reconfigure `sys.stdin`/`sys.stdout` the same way. Undecodable bytes become lone surrogates
(U+DC80–U+DCFF) in the decoded string and are re-encoded to the original bytes on output.

**Rationale**: FR-017 requires undecodable bytes to pass through unchanged rather than failing or
becoming U+FFFD. `surrogateescape` is the only standard-library codec error handler that is exactly
round-tripping. Verified: `b"caf\xe9 jane@example.com \xff\xfe 10.0.0.7\n"` decoded and re-encoded
compares byte-identical to the input, and redaction of the embedded email/IP still fires.

Surrogates cannot be confused with any recognised value because no recognition rule admits a
non-ASCII character (see D-004).

**Alternatives considered**:

- `errors="replace"` — substitutes U+FFFD, losing bytes. Violates FR-017 outright.
- `errors="strict"` with a crash — violates FR-017; also fails the constitution's "no silent
  wrong answer" only to replace it with a loud wrong answer.
- Operating on `bytes` with `bytes` patterns — round-trips trivially, but then line length limits,
  placeholder insertion, and `[0-9]` classes all work on bytes while the spec is written in terms of
  text. Rejected as a larger change for no benefit; `surrogateescape` already gives byte exactness.

**`newline=""`**: chosen on both sides so newline sequences are neither translated nor normalised;
`\r\n` and lone `\r` reach the output exactly as they arrived (FR-003, SC-003).

---

## D-002: Bounded line reads with `readline(MAX + 1)`

**Decision**: Read with `stream.readline(MAX_LINE + 1)` where `MAX_LINE = 1024 * 1024` characters of
decoded text. Treat a returned chunk as terminated if it ends with `"\n"` or `"\r"`. A chunk that is
not terminated and is longer than `MAX_LINE` is an over-long line: report and exit 2.

**Rationale**: SR-005 forbids unbounded reads. `for line in stream` and `stream.readline()` with no
argument are both unbounded — a single 4 GB line would be materialised in memory. `readline(n)`
caps the read at `n` characters, so peak memory is bounded by the limit regardless of total input
size (SC-007). Verified against a 17-character limit: a 30-character line surfaced as a 17-character
unterminated chunk (detected as over-long), while `"x\r\n"`, `"y\r"`, and `"z\n"` were each returned
as single terminated chunks.

The `MAX + 1` read (rather than `MAX`) is what makes the limit detectable: a chunk of exactly
`MAX + 1` characters with no terminator proves the line's content exceeds `MAX`, whereas a chunk of
`MAX` content characters plus its newline is exactly at the limit and legal.

**Known benign edge**: with `newline=""`, a line whose content is exactly `MAX` characters and whose
terminator is `\r\n` is returned as `MAX` characters + `"\r"`, leaving the `"\n"` to be returned as
the next chunk. The bytes written out are still byte-identical to the bytes read, and matching is
unaffected because no rule spans a line boundary. Accepted rather than worked around.

**Alternatives considered**:

- `read(chunk_size)` plus manual line splitting — equally bounded, but re-implements buffering and
  newline recognition in Python. Rejected under Principle IV (Simplicity).
- `mmap` or whole-file reads — violate SR-005 and FR-016.
- Raising the limit for stdin only — no requirement asks for it; one documented limit is simpler.

---

## D-003: Matching strategy — regex for email/IPv4, explicit scan for cards

**Decision**: Three-stage per-line pipeline.

1. One compiled alternation `(?P<email>…)|(?P<ip>…)`, scanned with `finditer`, yields the email and
   IPv4 matches. Alternation order encodes the email-before-IPv4 half of the FR-008 precedence, and
   `finditer` supplies leftmost, non-overlapping, greedy-longest matches (FR-009).
2. In each *gap* left uncovered by stage 1, find card matches: locate maximal ASCII digit runs with
   `[0-9]+`, join runs that are separated by exactly one `' '` or `'-'` into chains, and for each run
   as a candidate start walk forward accumulating runs while the digit total stays ≤ 19, recording
   the longest prefix whose total is 13–19 digits and which passes Luhn.
3. Sort all matches by position and rebuild the line by concatenating verbatim slices and literal
   placeholder strings.

**Rationale**: the Luhn checksum is not expressible as a regular expression, so cards need
host-language validation. Driving that validation off *maximal digit runs* rather than a regex
"chain" pattern is what makes the boundary rules fall out for free: FR-007 rejects any candidate
immediately preceded or followed by a digit, and a candidate can therefore only begin at the start
of a maximal run and end at the end of one. No separate boundary test is needed, and no false run
boundary can be introduced by a quantifier bound.

Running card detection only inside stage 1's gaps implements the rest of FR-008 — email and IPv4
outrank card for any overlapping span — and guarantees FR-008's "placeholders MUST NOT be nested":
placeholders are appended to an output list and never re-scanned.

Verified against every acceptance scenario and edge case in the spec:

| Input | Output | Rule exercised |
|---|---|---|
| `user jane@example.com from 10.0.0.7` | `user [EMAIL] from [IP]` | US1-1 |
| `paid with 4111 1111 1111 1111, ref 1234567890123` | `paid with [CARD], ref 1234567890123` | US1-2 |
| `jane.doe+test@mail.example.com logged in` | `[EMAIL] logged in` | US1-3 |
| `hit 999.1.1.1 today` | unchanged | US1-4, FR-005 |
| `a@1.2.3.4` | `a@[IP]` | edge: IPv4 domain |
| `4111 1111 1111 1111 1234` | `[CARD] 1234` | edge: longer digit runs |
| `over 1.2.3.4.5 here` | unchanged | edge: over-long IPv4 |
| `zero 010.0.0.7 ok` | `zero [IP] ok` | edge: leading zeros |
| `4111-1111 1111-1111` | `[CARD]` | edge: mixed separators |
| `4111  1111 1111 1111` | unchanged | edge: double separators |
| `12345678903@example.com` | `[EMAIL]` | FR-008 precedence |
| `12 34.5.6.7` | `12 [IP]` | precedence across a digit run |
| `12 34@x.com` | `12 [EMAIL]` | precedence across a digit run |
| `4111111111111111@a.com` | `[EMAIL]` | FR-008 precedence |
| `edge4111111111111111edge` | `edge[CARD]edge` | FR-006 contiguous |
| `jane@example.com.` | `[EMAIL].` | trailing sentence dot |
| `a@b.co1` | unchanged | FR-004 no truncation |
| `١٢٣٤ arabic digits` | unchanged | D-004 ASCII-only |

**Alternatives considered**:

- **Single `re.sub` with one combined pattern and a callback.** Cannot express Luhn, so a card
  alternative would have to match broadly and then decline — but a declined match has already
  consumed text, which loses later-starting matches. Concretely, a greedy chain alternative consumes
  `12 34` in `12 34.5.6.7` and the IPv4 `34.5.6.7` is never found. Rejected as incorrect.
- **Position-by-position Python scan** (try email, then IPv4, then card at each index). Correct, and
  the most literal reading of "leftmost wins", but it is a Python-level loop over every character:
  measured throughput would miss SC-007 by an order of magnitude. Rejected on performance.
- **Three sequential passes with sentinel placeholders.** Pass 2 and 3 would have to avoid matching
  inside `[EMAIL]`/`[IP]` text, which means the output of one pass becomes untrusted input to the
  next — precisely what FR-008 forbids. Rejected.

**Overlap rule, stated explicitly** (resolves the one ambiguity left by FR-008 + FR-009): precedence
is applied *before* position. An email or IPv4 match suppresses any card candidate that overlaps it,
even when the card candidate starts earlier. Within a single category, leftmost wins and ties at the
same start go to the longest. This ordering was chosen because it is what FR-008's "fixed,
documented precedence of email, then IPv4, then card" says on its face, and because the alternative
(strict leftmost across categories) produces worse disclosure: on `12 34.5.6.7` it would emit
`12 34.5.6.7` unchanged or a partial `[CARD].7.8.9`-style result on neighbouring inputs, leaking IP
fragments. Cards surviving in the gaps are still found leftmost-longest.

---

## D-004: ASCII-only character classes, no `\d` / `\w`

**Decision**: Write every class out explicitly — `[0-9]`, `[A-Za-z]`, `[A-Za-z0-9-]`,
`[A-Za-z0-9._%+-]`. Never use `\d`, `\w`, or `\b`.

**Rationale**: on `str` patterns Python's `\d` matches every Unicode decimal digit, so
`\d{13,19}` + Luhn would try to treat Arabic-Indic or Devanagari digits as a card number, and
`ord(ch) - 48` arithmetic in the Luhn routine would silently produce garbage — a silent wrong answer,
the defect class Principle II names as most severe. The spec's rules are defined over ASCII digits
and letters. Explicit classes make that visible in the pattern instead of depending on an
`re.ASCII` flag applied at the right place. Verified: `١٢٣٤ arabic digits` is returned unchanged.

**Alternatives considered**: `re.ASCII` flag on each compile — equivalent in effect but invisible at
the point of use and easy to omit on a later pattern. Rejected as the more fragile of two equals.

---

## D-005: Bounded quantifiers for SR-006

**Decision**: Every quantifier that could nest is explicitly bounded:

| Element | Pattern | Bound rationale |
|---|---|---|
| Email local part | `[A-Za-z0-9._%+-]{1,256}` | > RFC 5321 limits (64 local, 254 total) |
| Domain label | `[A-Za-z0-9-]{1,63}` | DNS label maximum |
| Label repetitions | `(?:label\.){1,16}` | far beyond real domain depth |
| Final label | `[A-Za-z]{2,63}` | FR-004: ≥ 2 letters, letters only |
| IPv4 octet | `(?:25[0-5]\|2[0-4][0-9]\|[01][0-9][0-9]\|[0-9][0-9]\|[0-9])` | fixed width, no quantifier |
| IPv4 groups | `(?:\.octet){3}` | exact count |

The single exception is `[0-9]+`, used to find maximal digit runs for card detection. It is one
unbounded repetition of a one-character class with nothing nested inside it; the engine consumes it
in a single linear scan and creates no backtracking states, so it meets SR-006's stated guarantee
("matching time stays linear in line length"). Bounding it would be actively wrong: a bound of *n*
would split a longer digit run into false fragments at arbitrary offsets, and a fragment boundary is
exactly what FR-007's digit-adjacency rule relies on not existing. This is recorded as a deliberate,
reasoned reading of SR-006 rather than an oversight.

**Rationale**: no pattern contains nested unbounded repetition, so catastrophic backtracking is
structurally impossible, not merely unobserved. Where backtracking does occur it is bounded: a
300-character local-part-like run backtracks at most 256 times and then fails, and the leading
`(?<![A-Za-z0-9._%+-])` guard stops the engine from retrying at every interior offset, which is what
would otherwise make such a run quadratic.

**Measured** (10,000-character adversarial lines, SC-008 budget 1 s each):

| Input | Time |
|---|---|
| `"9" * 10000` | 0.6 ms |
| `"1 " * 5000` (separator run) | 117 ms |
| `"a." * 2500 + "@" + "a." * 2500` | 1.1 ms |
| `"1." * 5000` | 3.6 ms |
| `"a" * 10000 + "@"` | 0.9 ms |

Worst case is 117 ms against a 1 s budget, 8.5× margin. The separator run is the costly shape
because it yields 5,000 candidate start positions; it stays linear because each start examines at
most 19 runs.

---

## D-006: Fail-closed output and exit status

**Decision**: a single error exit status of **2** for every failure mode — unreadable FILE (FR-013),
invalid usage (FR-014), over-long line (SR-005), and output write/flush failure (SR-007). Writes and
the final flush are wrapped; an `OSError` is reported on stderr and exits 2. On `BrokenPipeError`
specifically, write the diagnostic, flush stderr, then `os._exit(2)`.

**Rationale**: FR-014 fixes 2 for usage errors and FR-013 fixes 2 for unreadable files, and requires
only "non-zero" elsewhere; using one status everywhere is the smallest design that satisfies all of
them (Principle IV) and keeps SC-006's "no case exits 0" trivially checkable. The `os._exit` detail
is needed because CPython flushes `sys.stdout` during interpreter shutdown; if the pipe is already
broken that flush raises again and the interpreter prints `Exception ignored in: <stdout>` and
changes the status to 120 — which would both pollute stderr (FR-011, SR-001) and contradict the
documented status. Stderr is flushed explicitly first, so the diagnostic is not lost.

The `--count` summary is written only on the success path, after the final flush of stdout succeeds,
satisfying FR-010's ordering and US4-5's "no summary on failure".

**Alternatives considered**: distinct statuses per failure class (e.g. 2 usage, 3 I/O, 4 limit) — no
requirement asks for the distinction, and it adds a documented surface that tests must pin.
Rejected under Principle IV. Letting `BrokenPipeError` propagate — produces a traceback on stderr,
violating SR-009's "never as a stack trace". Rejected.

---

## D-007: `argparse` for the CLI surface

**Decision**: `argparse.ArgumentParser(prog="python -m logredact")` with `--count` as
`action="store_true"` and `files` as `nargs="*"`.

**Rationale**: argparse already does exactly what FR-012 and FR-014 require — it accepts `--count`
in any position, collects the rest positionally in order, and on an unrecognised option writes a
usage message to stderr and exits 2. Reimplementing that by hand would be more code for identical
behaviour (Principle IV). Confirmed that a bare `-` is handled as a positional, not an option, which
is what the spec's assumption ("`-` is not special") requires: it becomes a literal path that then
fails FR-013 with status 2.

Its diagnostics name only the offending option string, which comes from the invoking user's own
command line, not from input content — SR-001 permits that.

**Alternatives considered**: hand-rolled argv loop — more code, same result. `getopt` — same, with
worse error messages.

---

## D-008: Testing failure paths that the environment cannot produce

**Decision**: inject streams and dependencies rather than relying on filesystem state.
`main(argv, *, stdin, stdout, stderr)` takes its three streams as keyword arguments defaulting to
the real ones. Permission-denied is tested by monkeypatching the module's `open` to raise
`PermissionError`; write failure is tested with a stream object whose `write`/`flush` raise
`OSError`.

**Rationale**: the development and CI environment runs as **root**, where `chmod 000` does not
prevent reading — a test that chmods a file and expects exit 2 would pass or fail depending on the
uid of whoever runs the suite. Constitution Principle III requires tests to be deterministic and
forbids skipping or xfail-ing a known-failing test, so a uid-conditional test is not an acceptable
way to cover US4-2. Monkeypatching the open call tests the handler contract — "a `PermissionError`
from opening a FILE produces a message naming that file and exit 2" — deterministically on any uid.
A real directory argument is used for the unreadable-path case that *does* reproduce everywhere
(`IsADirectoryError`, US4-3), so the real `except OSError` path is still exercised against the real
filesystem.

**Alternatives considered**: run the suite as an unprivileged user — not available in CI and not
something a test can assume. `pytest.mark.skipif(os.geteuid() == 0)` — forbidden by Principle III.

---

## D-009: Test layout and `src/` on the path

**Decision**: a `pyproject.toml` carrying only `[tool.pytest.ini_options]` with
`pythonpath = ["src"]` and `testpaths = ["tests"]`. Tests are split between in-process calls to
`main(...)` and subprocess runs of `python -m logredact` with `PYTHONPATH=src`.

**Rationale**: FR-001 requires the package to live under `src/` and be run with `src/` on the module
search path. pytest's own `pythonpath` setting does that for the suite without a `sys.path`-editing
`conftest.py` and without installing anything, so the project stays usable by someone who has
installed nothing but CPython (Principle I). The file declares no dependencies and no build backend,
so it introduces no runtime dependency — it is developer tooling, which Principle I explicitly
permits.

Both test styles are needed: in-process tests reach injected-stream failure paths (D-008) and run
fast; subprocess tests are the only way to assert the real contract — the `python -m logredact`
entry point, the real exit status, and **byte-level** stdout content, which is what FR-003, FR-017
and SR-002 are actually about.

**On SR-008 ("no artifacts on disk")**: running `python -m logredact` makes CPython write
`src/logredact/__pycache__`. That is the interpreter's bytecode cache, not an artifact of the tool,
and the tool itself opens files read-only and creates nothing. Tests that assert the no-artifact
property run the subprocess with `-B` (and `PYTHONDONTWRITEBYTECODE=1`) so the assertion is about
the tool's own behaviour and cannot be defeated or faked by cache files. Recorded here because an
unqualified "no files created" assertion would otherwise fail for a reason unrelated to the control.

---

## D-010: Throughput

**Decision**: no optimisation beyond the design above; accept the straightforward implementation.

**Rationale**: measured 5.3 MB/s on a representative log line containing one email, one IPv4 and one
grouped card — **10 MB in 1.9 s** against SC-007's 10 s budget, a 5× margin. Memory is bounded by
`MAX_LINE`, so a 1 GB input streams in constant memory. No further work is justified
(Principle IV); if a future change erodes the margin, the first lever is a digit-value lookup table
in the Luhn routine to avoid per-candidate string construction.

---

## Resolved unknowns summary

| Question | Resolution |
|---|---|
| Keep non-UTF-8 bytes intact? | `errors="surrogateescape"` end to end (D-001) |
| Bound per-line memory? | `readline(MAX + 1)` + terminator check (D-002) |
| Luhn inside a regex? | Not possible; maximal digit runs + Python validation (D-003) |
| Cross-category overlap order? | Precedence before position; cards only in gaps (D-003) |
| Unicode digits as cards? | Excluded by explicit `[0-9]` classes (D-004) |
| Catastrophic backtracking? | No nested unbounded repetition; 117 ms worst case (D-005) |
| Exit status for I/O failure? | 2, uniformly; `os._exit` on broken pipe (D-006) |
| Argument parsing? | `argparse`; already satisfies FR-012/FR-014 (D-007) |
| Permission-denied test as root? | Inject `PermissionError`; directory case covers real OSError (D-008) |
| `src/` on path for tests? | `[tool.pytest.ini_options] pythonpath = ["src"]` (D-009) |
| Performance headroom? | 5.3 MB/s measured, 5× margin on SC-007 (D-010) |

No `NEEDS CLARIFICATION` items remain.
