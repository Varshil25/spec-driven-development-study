# Phase 0 Research: Phone Redaction and `--out-dir`

**Feature**: `002-redact-phones-out-dir` | **Date**: 2026-11-14

Decision IDs continue feature 001's series (R-001 … R-009 live in
[`../001-redact-log-pii/research.md`](../001-redact-log-pii/research.md)).

Every decision below was **verified by execution** on Python 3.13.17 before being written down:
a prototype carrying the full design was built and run against every acceptance scenario and edge
case in [spec.md](./spec.md), and against the existing test suite. Where a decision had a credible
alternative, the alternative was built and run too, and the transcript is quoted.

No NEEDS CLARIFICATION remains. The spec's four clarifications settled the open recognition
questions; the user's instruction settled language, dependencies, interface, and test framework.

---

## R-010 — The phone pattern

**Decision**: `_PHONE = r"\+[0-9]{8,15}(?![0-9])"`, added as a fourth named branch to the existing
compiled alternation.

Three details carry three requirements, and none is decorative:

| Detail | Requirement |
|--------|-------------|
| `[0-9]`, **not** `\d` | FR-031 — "digit" means ASCII `0`-`9` only. In Python, `\d` on a `str` pattern matches every Unicode decimal digit |
| `(?![0-9])` | FR-032 — a run followed by another digit is rejected whole, never truncated to its first 15 |
| no lookbehind of any kind | FR-031a — there is no left-hand guard; whatever precedes the `+`, the candidate matches |

**Rationale**: `{8,15}` plus a trailing negative lookahead is the only shape that rejects a
16-digit run *entirely* rather than matching its first 15. Verified:

```text
'x +1234567 y'            -> 'x +1234567 y'              (7 digits: below the minimum)
'+12345678'               -> '[PHONE]'                   (8 digits: the minimum)
'+455673758689985'        -> '[PHONE]'                   (15 digits: the maximum)
'x +1234567890123456 y'   -> 'x +1234567890123456 y'     (16 digits: rejected whole, not truncated)
'+14155552671.'           -> '[PHONE].'                  (FR-034: punctuation not consumed)
'(+14155552671)'          -> '([PHONE])'
'bare + here'             -> 'bare + here'               (FR-033)
'build v2+12345678 ok'    -> 'build v2[PHONE] ok'        (FR-031a)
'x=99+12345678'           -> 'x=99[PHONE]'               (FR-031a)
'+14155552671+442071838750' -> '[PHONE][PHONE]'          (adjacent candidates)
'+١٤١٥٥٥٥٢٦٧١'            -> '+١٤١٥٥٥٥٢٦٧١'              (FR-031: non-ASCII digits)
'+1415555٢٦٧١'            -> '+1415555٢٦٧١'              (7 ASCII digits, and FR-032 does not fire)
```

The mixed-script case is the subtle one and it works for the stated reason: the ASCII run is cut
short by a non-ASCII character, so `{8,15}` fails on length rather than `(?![0-9])` firing — which
is exactly the reading the spec's edge-case list demands.

**Alternatives considered**:

- `\+\d{8,15}(?!\d)` — matches Arabic-Indic and fullwidth digits, contradicting FR-031 directly.
- `\+[0-9]{8,15}\b` — `\b` is wrong at a word boundary that is also a digit boundary; verified to
  accept `+123456789` inside `+1234567890123456`, truncating a rejected run.
- Bounding the run in the validator instead of the pattern (the approach the card rule uses):
  needless here, because a phone candidate has no separators, so its digit count is known from the
  match. The card rule needs a validator only because separators must be stripped first.

---

## R-011 — Branch placement is the precedence rule

**Decision**: append the phone branch **last**:
`(?P<email>…)|(?P<ip>…)|(?P<card>…)|(?P<phone>…)`.

**Rationale**: feature 001 made `re.sub` over a single alternation carry FR-018 (leftmost wins)
and FR-019 (branch order breaks a tie at the same start) by construction. FR-036 extends that
order to `email → ip → card → phone`, so appending the branch *is* the implementation — no
comparison code, no priority field. Verified:

```text
'+12345678@example.com'  -> '[EMAIL]'        counted as an email, not '[PHONE]@example.com'
'jane+orders@example.com'-> '[EMAIL]'
'a@b.io +442071838750'   -> '[EMAIL] [PHONE]'
'+14155552671 10.0.0.7'  -> '[PHONE] [IP]'
```

In practice only the email branch can begin at the same offset as a phone candidate, because `+`
is in the email local-part class while IPv4 and card candidates both begin with a digit — so
"phone last" and "phone third" are indistinguishable in output. Last is still the right choice: it
is what FR-036 says, and it leaves the inherited three-way order untouched.

FR-035 needs no code at all. `re.sub` resumes scanning after the replaced span, so the digits
inside a `[PHONE]` are never re-examined by the card or IPv4 branch and cannot be double-counted
(the inherited FR-020 mechanism, already tested).

---

## R-012 — FR-032a belongs in the card validator, not in a lookbehind

**Decision**: leave `_CARD` exactly as it is and add one guard to the card arm of `_replacement`:

```python
if match.start() > 0 and match.string[match.start() - 1] == "+":
    return text        # FR-032a — a '+'-prefixed run is telephone-shaped, never a card
```

**This decision was changed by its experiment.** The obvious implementation — add `(?<!\+)` to the
card pattern — was built and run side by side with the validator version:

```text
input                    today        (?<!\+) lookbehind   validator guard
'+4111111111111111'      '+[CARD]'    '+4111111111111111'  '+4111111111111111'
'+4111 1111 1111 1111'   '+[CARD]'    unchanged            unchanged
'+1 4111111111111111'    unchanged    '+1 [CARD]'   ←NEW   unchanged
'+1-4111111111111111'    unchanged    '+1-[CARD]'   ←NEW   unchanged
```

The lookbehind **creates card matches that today's tool does not produce**: blocking the candidate
at the first digit lets the scanner restart inside the run and find a shorter, Luhn-valid tail.
FR-054 states the two deliberate output changes are "exactly the phone replacements of FR-030 and
the card **suppression** of FR-032a" — a suppression, never an addition — so the lookbehind variant
is out. The validator guard rejects the whole maximal candidate and `re.sub` then resumes *after*
it, so nothing inside is re-scanned, matching FR-016's inherited "never partially redact a
candidate" treatment.

It is also the cheaper change: the card arm already has two `return text` paths for a rejected
candidate, so this is a third one, and the compiled pattern is untouched.

**Alternatives considered**: a fifth alternation branch that swallows `\+[0-9]+` and returns it
unchanged — would need to run after the phone branch, which the engine's first-match-wins order
makes impossible without duplicating the `{8,15}` logic in two places.

---

## R-013 — The inherited `\d` stays Unicode-wide (a documented non-change)

**Decision**: do **not** narrow `\d` to `[0-9]` in `_IP` or `_CARD`.

**Finding**: FR-031 asserts that non-ASCII decimal digits are left unchanged "exactly as the
existing IPv4 and payment-card rules are read". That assertion is false. `\d` matches every
Unicode decimal digit, and `int()` accepts them, so the inherited card rule redacts a
13-to-19-digit Arabic-Indic run that passes Luhn, today, before this feature.

**Rationale for leaving it**: such an input contains no international-format phone number and no
`+`-prefixed digit run, so FR-054 requires its output to be **byte-identical** to the existing
tool's. Fixing the inherited patterns here would violate FR-054 and would smuggle a third
behavioural change into a feature whose spec names exactly two. The new phone rule uses `[0-9]`
and is correct in isolation.

Recorded as spec defect D-2 in [plan.md](./plan.md). It deserves its own decision — a one-line
spec amendment plus a one-character pattern change — not a silent correction inside this feature.

---

## R-014 — `--out-dir` as an argparse option, and the no-FILE usage error

**Decision**: `parser.add_argument("--out-dir", dest="out_dir", metavar="DIR")`, still parsed with
`parse_intermixed_args`. For FR-051, `parser.error("--out-dir requires at least one FILE")`.

**Rationale**: the inherited `parse_intermixed_args` (R-001) already allows flags between
filenames, and it extends to an option-with-value for free. Verified:

```text
['--out-dir','clean','a.log','b.log']        -> out_dir='clean'  files=['a.log','b.log']
['a.log','--out-dir','clean','--count','b.log'] -> out_dir='clean'  files=['a.log','b.log']  count=True
['a.log','b.log','--count','--out-dir','d']  -> out_dir='d'      files=['a.log','b.log']  count=True
usage: python -m logredact [-h] [--count] [--out-dir DIR] [files ...]
```

The usage line updates itself, so FR-040's grammar change needs no hand-written `usage=` string.

`parser.error` is the right instrument for FR-051 because it *is* the FR-029 path: argparse writes
the usage line plus a message naming the problem to stderr and raises `SystemExit(2)`, which
`__main__.py`'s `raise SystemExit(main())` propagates unchanged. Verified against the real
requirement — stdout empty, DIR not created, stdin not read:

```text
$ python -m logredact --out-dir clean          (with '+12345678' on stdin)
rc=2  stdout=b''
stderr=b'usage: python -m logredact [-h] [--count] [--out-dir DIR] [files ...]\n'
       b'python -m logredact: error: --out-dir requires at least one FILE\n'
clean/ created: False
```

The check runs **before** `_configure_streams` and before `makedirs`, which is what keeps stdin
unread and DIR uncreated.

**Alternatives considered**: a hand-rolled `if` writing its own message and returning 2 — would
duplicate argparse's usage-line formatting and risk drifting from the FR-029 wording; a mutually
exclusive group — argparse cannot express "requires a positional".

---

## R-015 — Create DIR before opening any input

**Decision**: `os.makedirs(args.out_dir, exist_ok=True)` as the first thing the `--out-dir` branch
does, wrapped in `except OSError` → diagnostic naming DIR → return 2.

**Rationale**: FR-045 requires it, and FR-049 requires the diagnostic to precede any reading.
`exist_ok=True` gives FR-042 in one argument: a missing DIR and every missing parent are created, an
existing DIR is used as it is, nothing is emptied. Verified, including the failure modes the spec
names:

```text
makedirs('deep/a/b', exist_ok=True)      -> created, parents and all
makedirs(<a regular file>, exist_ok=True)-> FileExistsError   strerror='File exists'
makedirs(<file>/'sub', exist_ok=True)    -> NotADirectoryError strerror='Not a directory'
```

`OSError.strerror` supplies "what went wrong" for all of them, so the inherited `_report` helper —
`python -m logredact: <path>: <reason>` — carries FR-049 with no new formatting:

```text
$ python -m logredact --out-dir blocker in.log      # 'blocker' is a regular file
rc=2  stdout=b''  stderr=b'python -m logredact: blocker: File exists\n'
$ python -m logredact --out-dir blocker/sub in.log
rc=2  stdout=b''  stderr=b'python -m logredact: blocker/sub: Not a directory\n'
```

`exist_ok=True` is also why a pre-existing DIR is not a race: two concurrent runs both succeed.

---

## R-016 — Output names come from `os.path.basename`

**Decision**: `out_path = os.path.join(args.out_dir, os.path.basename(name))`.

**Rationale**: FR-041 says "the final path component of that FILE as given on the command line".
That is `os.path.basename` by definition. Verified:

```text
'var/logs/app.log' -> 'app.log'      './a.log' -> 'a.log'       '/abs/x.log' -> 'x.log'
'a/b/../c.log'     -> 'c.log'        '..'      -> '..'          'dir/'       -> ''
```

The last two are degenerate — `basename('dir/')` is the empty string, and `'..'` names the parent
directory — but neither is reachable: both are directories, so the input open fails first under
R-017 and the user gets a diagnostic naming what they typed rather than a confusing one naming DIR.
Verified end to end; no special-casing is needed, which is the point of recording it.

Name collisions need no code either: FR-043's `"w"` mode applies at every write, so a later FILE
with the same basename replaces the earlier one's output, and `written` counts both
(spec Assumptions, "N counts FILE arguments processed"). Verified:
`--out-dir out a/x.log b/x.log` → `wrote 2 files`, `out/x.log` holding only `b/x.log`'s output.

---

## R-017 — Open the input before the sink

**Decision**: for each FILE, open the input first; only then open the sink. The spec is ambiguous
here, so the reasoning matters.

**The ambiguity**: FR-048 says that when a FILE cannot be read, "the incomplete output file for the
failing FILE MUST be removed as FR-050a requires", which presupposes a sink was already opened —
i.e. sink-first. But FR-050a scopes itself to a failure "after an output file has been opened but
before that file has been completely written", and User Story 4 scenario 9 scopes its
previous-contents-are-gone rule to a run that "fails **partway through writing** it". Both
orderings satisfy the letter of every acceptance scenario.

**Rationale for input-first**: the orderings differ in exactly one case — a FILE that cannot be
opened at all, the single most common failure (a typo). Verified, with a pre-existing
`out/missing.log` in place:

```text
$ python -m logredact --out-dir out missing.log
rc=2  stdout=b''  stderr=b'python -m logredact: missing.log: No such file or directory\n'
out/ contains: ['missing.log']        content: b'PRE-EXISTING\n'   ← intact
```

Sink-first would have created, truncated, and then deleted that file, destroying unrelated data
because of a typo. Input-first preserves it. The spec invokes "the safe direction when in doubt" as
its own tie-breaker twice (FR-031a, FR-036), and the purpose FR-050a states for the deletion — "so
the output folder is left holding only complete files" — is fully met either way.

The non-destructive reading costs nothing in the cases the spec does specify, because a read
failure *after* the sink opened still deletes the sink. Verified with `/proc/self/mem`, which opens
cleanly and fails on read, and with a pre-existing file of its output name:

```text
$ python -m logredact --out-dir out first.log /proc/self/mem --count
rc=2  stdout=b''  stderr=b'python -m logredact: /proc/self/mem: Input/output error\n'
out/ contains: ['first.log']          first.log: b'[PHONE]\n'   ← earlier file complete
out/mem: absent                       ← sink deleted; its pre-existing content is gone (FR-050a)
```

So FR-048's removal clause is honoured wherever there is something to remove, SC-013a's "no
truncated file in the folder" holds, and a mistyped filename is no longer destructive.

**Consequence, recorded deliberately**: whether a pre-existing `DIR/basename(FILE)` survives a
failed run depends on *when* the input failed — it survives an open failure, it is gone on a
mid-read failure. That jaggedness is the price of the non-destructive choice. The uniform
alternative (sink-first: the name is always absent afterwards) is a one-line change if the product
decision goes the other way.

---

## R-018 — Telling an input failure from an output failure

**Decision**: a two-attribute exception, `_OutputError(path, error)`, raised by the three sink
operations (`open`, `write`, `close`) and nothing else. The per-FILE handler is then unambiguous:

```python
except _OutputError as failure:   # FR-050 — name the output path
    _report(failure.path, failure.error); return EXIT_FAILURE
except OSError as error:          # FR-048 — name the FILE as given
    _report(name, error); return EXIT_FAILURE
```

`_OutputError` inherits `Exception`, **not** `OSError`, so the second clause cannot swallow it.

**Rationale**: FR-048 and FR-050 require different paths in the diagnostic, and once both files are
open an `OSError` from the streaming loop could come from either side. `OSError.filename` does not
disambiguate — it is set by `open()`, not by reads or writes on an established handle (verified:
unset in both cases). Without the wrapper the tool names the wrong path, which Principle II
forbids. Verified on both sides:

```text
write failure (out/in.log is a symlink to /dev/full):
  rc=2  stderr=b'python -m logredact: out/in.log: No space left on device\n'   ← output path
output path exists as a directory:
  rc=2  stderr=b'python -m logredact: out/in.log: Is a directory\n'            ← output path
read failure mid-stream (/proc/self/mem):
  rc=2  stderr=b'python -m logredact: /proc/self/mem: Input/output error\n'    ← input name
```

The wrapper is applied to each line through a small closure returned by `_sink_writer`. CPython
3.11+ has zero-cost exception handling, so the `try` costs nothing when nothing raises; the extra
call is the only overhead, and it is unmeasurable at this scale (R-021).

**Alternatives considered**: one `except OSError` naming the input — verified to misattribute the
`/dev/full` failure above; a boolean flag set around each write — same line count, and it cannot
cover the sink's `close()`; comparing `error.filename` — unset, as measured.

---

## R-019 — Discarding the half-written file

**Decision**:

```python
def _discard(sink, path):
    try:
        sink.close()
    except OSError:
        pass                      # the file is being deleted; the real diagnostic is already queued
    try:
        os.remove(path)
    except OSError as error:
        _report(path, error)      # FR-050a — a failed deletion is reported too
```

called from a cleanup-and-re-raise wrapped around the streaming loop, so it fires on a read
failure (FR-048), an output failure (FR-050), and nothing else.

**Rationale**: FR-050a requires the incomplete file gone and the original diagnostic intact. The
handle must be closed before `os.remove` for the deletion to be portable; a flush failure at that
close is, on the common `ENOSPC` path, the very error already being reported, so re-raising it
would both skip the deletion — leaving exactly the truncated file the requirement exists to
prevent — and replace the primary diagnostic with a duplicate. The `pass` is narrow, on a file whose
contents are being destroyed by design, and is logged as a justified deviation in plan.md's
Complexity Tracking rather than hidden.

A failed `os.remove` is reported as a *second* stderr line and the status stays 2, which is
FR-050a's last sentence and the spec's "the tool does not retry or fall silent".

**Alternatives considered**: write to a temporary name and `os.replace` on success — rejected by
the spec itself (Assumptions: it would leave stray temporary files in DIR on a hard kill, and it
adds names no requirement asks for); buffer the file and write it only on success — contradicts
FR-044's streaming contract and SC-017's memory bound; keep a copy of the previous contents to roll
back — the spec explicitly refuses this ("the run MUST NOT attempt to restore its previous
contents").

---

## R-020 — The sink's text contract

**Decision**: `open(path, "w", encoding="utf-8", errors="surrogateescape", newline="")` — the same
four arguments as the inherited `sys.stdout.reconfigure`.

**Rationale**: FR-044 requires each output file to carry exactly the text contract standard output
carries. Reusing the arguments verbatim is the only way to guarantee that rather than approximate
it: `"w"` gives FR-043's replacement, `utf-8` gives FR-005a, `surrogateescape` gives FR-005b's byte
round-trip, `newline=""` disables all line-ending translation so CRLF and a missing final newline
survive (FR-005). Verified end to end on an undecodable byte:

```text
in:  b'bad \xff byte +14155552671\n'
out: b'bad \xff byte [PHONE]\n'        byte-identical outside the match
```

The quickstart checks the stronger property the spec actually cares about: the output file's bytes
equal the bytes the same FILE produces on standard output.

---

## R-021 — Four counters, one source of key names, measured cost

**Decision**: `new_counts()` gains `"phones": 0` and becomes the single place the key names are
written. `cli.main` initialises `totals = new_counts()` instead of repeating the literal, and
`_redact_stream` accumulates with `for key, value in counts.items(): totals[key] += value` instead
of three hand-written lines. The summary becomes
`"emails={emails} ips={ips} cards={cards} phones={phones}\n"`.

**Rationale**: the key list appeared in three places before this feature (the factory, `main`'s
literal, and the accumulation lines); adding a fourth type to three places invites exactly the
drift FR-037's "always all four, always in this order" forbids. Collapsing to one is fewer moving
parts, not more (Principle IV).

**Measured cost** — the dict loop and the sink closure together, 1M lines / 88 MB:

| Run | Time |
|-----|------|
| current tool → `/dev/null` | 8.6 s |
| prototype → `/dev/null` | 8.5 s |
| prototype → `--out-dir`, with `--count` | 8.7 s |

Unchanged in character, far inside SC-017's 60 s, and memory stays bounded by the longest line
because nothing is accumulated (the inherited R-008 property).

**Measured impact on the existing suite** (SC-015). The prototype was run against the current
`tests/` unchanged:

```text
25 failed, 128 passed, 1 skipped
```

and all 25 are the summary shape, by category:

| Count | Assertion |
|-------|-----------|
| 15 | `c == {"emails": …, "ips": …, "cards": …}` — a 3-key dict literal in `tests/unit/` |
| 10 | `stderr == b"emails=N ips=N cards=N\n"` — the 3-key summary line in `tests/cli/` |

**Zero** failures on redacted stdout content. No test asserts that a `+`-prefixed run is redacted
as a card, so SC-015's second allowance turns out to be unused. The four-key update to those 25
assertions is therefore the complete, bounded cost of this feature to the existing suite.

---

## Verification transcript: the spec's scenarios

Every acceptance scenario and every edge case listed in spec.md was run against the prototype. All
produced the specified result. The ones that pin down a judgement call:

| Spec reference | Input / command | Result |
|----------------|-----------------|--------|
| US1-1 … US1-9 | the nine phone scenarios | all as specified, incl. `+4111111111111111` unchanged |
| US2-1 | `--count` on `a@b.io +442071838750` | stdout `[EMAIL] [PHONE]`, stderr `emails=1 ips=0 cards=0 phones=1` |
| US2-2 | `--count` on inert input | `emails=0 ips=0 cards=0 phones=0` |
| US3-1 | `--out-dir clean app.log web.log` | `clean/` created, both files correct, stdout `wrote 2 files`, rc 0 |
| US3-2 | `--out-dir clean var/logs/app.log` | `clean/app.log` |
| US3-3 | `--out-dir a/b/c …` | all parents created |
| US3-4/5 | pre-existing `out/app.log` (26 B) + `out/unrelated.txt` | replaced with 9 B; unrelated file untouched |
| US3-6 | `--out-dir out --count app.log` | `wrote 1 files` on stdout, four-key summary on stderr |
| US3-8 | empty input file | 0-byte output file, counts towards N |
| US4-1 | missing FILE, pre-existing output name | names the FILE, rc 2, no confirmation, no summary, pre-existing file intact (R-017) |
| US4-2 | `good.log nope.log later.log --count` | `out/` holds only a complete `good.log`; `later.log` never opened; rc 2 |
| US4-3 | DIR's parent is a regular file | names DIR with `Not a directory`, no input read, rc 2 |
| US4-4 | output path is a directory | names the output path with `Is a directory`, rc 2 |
| US4-5 | `--out-dir clean` with no FILE | usage diagnostic, stdout empty, `clean/` not created, rc 2 |
| US4-7 | `--redact-all` | unchanged from today: usage naming the flag, rc 2 |
| US4-8/9 | read fails after the sink opened | sink deleted, earlier file complete, rc 2 |
| Edge: early close | `--out-dir` with stdout closed before `wrote N files` | silent, rc 0 — the inherited FR-028 path still holds |
| Edge: early close | `big.log \| head -5` (no `--out-dir`) | first 5 lines, stderr empty, rc 0 |
