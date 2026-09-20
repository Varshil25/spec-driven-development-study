# Pilot Run Report — Milestone 2

**Study**: Evaluating and Extending Spec-Driven Development
**Milestone**: 2 (Weeks 3–4), Part II — Pilot
**Run**: `R001` · task `T-SPLIT-01` · condition `sdd` · model `claude-opus-5` · agent `claude-code`
**Raw data**: [`logs/runs/R001/`](../logs/runs/R001/)

---

## 1. What was done

GitHub Spec Kit's full command sequence — `/speckit-constitution` →
`/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`
— was executed end to end on one small feature, with every prompt, edit, and
output captured by purpose-built instrumentation installed *before* the first
command ran.

The pilot feature is a stdlib-only Python CLI that reads a CSV of shared group
expenses and prints the minimal set of payments that settles every
participant's balance. It was chosen to be completable in one sitting while
still exercising the properties the Weeks 5–7 tasks need: exact-arithmetic
edge cases (integer cents, remainder distribution), a defined error contract,
and a testable acceptance surface.

**Outcome**: the feature works. 58 tests pass, and the CLI was verified
independently of the agent's own report — `Bob pays Alice 15.00` for a
two-person, one-expense case; correct 3.34/3.33/3.33 remainder handling for
10.00 across three people.

## 2. Measurements

All figures are derived from [`logs/runs/R001/metrics.json`](../logs/runs/R001/metrics.json),
which is recomputable at any time from the append-only event log.

| Phase | Active time | Human turns | Human words | Tool calls | Files | Lines added |
| --- | --- | --- | --- | --- | --- | --- |
| constitution | 1m 13s | 1 | 92 | 7 | 1 | 227 |
| specify | 2m 00s | 1 | 135 | 4 | 2 | 316 |
| plan | 16m 11s | 1 | 49 | 5 | 5 | 834 |
| tasks | 2m 10s | 1 | 1 | 9 | 1 | 406 |
| implement | 7m 25s | 1 | 1 | 25 | 14 | 1,681 |
| **Total** | **29m 00s** | **5** | **278** | **50** | **22** | **3,464** |

Three results stand out.

**Specification consumed 74% of active time.** The four pre-implementation
phases took 21m 34s against 7m 25s for implementation. If SDD's benefit is
real, this is the price it is measured against — and the ratio is the single
most important quantity for RQ3.

**The human wrote 278 words; the workflow produced 7,580.** Across the
constitution (833 words), spec (1,865), plan (766), research (715), data-model
(643), quickstart (503), and task list (2,255), the specification set is
roughly 27× the human input that seeded it, and governs 325 lines of source.

**Five turns, one per phase.** The entire feature was produced in five human
prompts. Whatever the unstructured condition costs in Weeks 5–7, this is the
SDD baseline it is compared against, and it is very low.

## 3. Qualitative observations

### 3.1 The workflow is five commands, but seven artifacts

`/speckit-plan` did not produce "a plan". It produced `plan.md`,
`research.md`, `data-model.md`, `contracts/cli.md`, and `quickstart.md`. For a
task whose implementation is ~325 lines of Python, the planning stage alone
generated five specification documents.

The cost of SDD is not one extra prompt per stage; it is the generation, and
in principle the human review, of a document set that grows faster than the
code it governs. Whether that review actually happens is the honest question
the controlled study has to confront: in this pilot the operator did **not**
read all five plan artifacts before proceeding to `/speckit-tasks`, which is
almost certainly what a time-pressured developer would also do.

### 3.2 Ambiguity is absorbed, not surfaced

The specification stage resolved four genuine ambiguities in the task
description — amount format, currency, participant identity, and what
"minimal" means for a settlement — by writing an **Assumptions** section and
proceeding. It emitted no `[NEEDS CLARIFICATION]` markers and asked nothing.

Spec Kit ships `/speckit-clarify` for exactly this, and it is optional. The
default path therefore converts ambiguity into silently-recorded assumptions
rather than into questions. This bears directly on RQ4: if a measured SDD
benefit comes from the `clarify` stage rather than from specification as such,
that is a far more actionable finding than "SDD works".

### 3.3 Nothing upstream was ever revised

This is the clearest finding of the pilot, and it was only visible because
artifacts were hashed at every phase boundary:

| Artifact | Revisions after creation |
| --- | --- |
| constitution.md | 0 |
| spec.md | 0 |
| plan.md | 0 |
| research.md | 0 |
| data-model.md | 0 |
| quickstart.md | 0 |
| tasks.md | 1 (checkbox ticks only) |

Every upstream artifact was written once and never touched again. The core SDD
slogan — *fix the spec, not the output* — describes a feedback loop that **did
not occur even once** in this run. Implementation raised no issue that flowed
back into the specification.

Two readings are possible, and the pilot cannot distinguish them: either the
specification was good enough that no revision was warranted, or the workflow
provides no pressure to revise it and drift would go unnoticed. Either way,
"spec revision count" is now a measure worth collecting in Weeks 5–7, and the
instrument already captures it.

### 3.4 The constitution is consulted, and it is also self-graded

The plan artifacts contain an explicit "Constitution Check" with initial and
post-design PASS. That is real traceability. But the check is performed by the
same agent that wrote the design, against principles that same agent drafted
from a one-paragraph prompt, with nothing external validating it.

For RQ4 the useful measurement is therefore not "was the constitution
checked" (it always will be) but whether its principles had a detectable
effect on the code — e.g. whether the integer-cents principle actually
eliminated float arithmetic. Here it did: runtime imports are limited to
`argparse`, `csv`, `sys`, `decimal`, and cents are integers throughout. That
is statically checkable and should be added to the Week 8–9 coding scheme.

### 3.5 Task decomposition flagged its own limits

`/speckit-tasks` produced 26 tasks (later 28) and then volunteered that the
three user stories were *not* independently parallelizable because the modules
they touch overlap — useful honesty, and a sign that the "independently
testable user story" framing in the spec template is aspirational rather than
structural.

### 3.6 Artifact hygiene

`/speckit-constitution` wrote a Sync Impact Report as an HTML comment at the
top of `constitution.md`, told the operator it was "scratch material expected
to be removed before committing", and left it in the file.

## 4. What the pilot changed about the instrument

Three defects were found by *running* the logger, not by testing it. Each
would have silently corrupted the Weeks 5–7 dataset.

**The instrument measured itself.** The first phase capture reported 200
changed lines where three were real: the logger's own `events.jsonl`, written
inside the repository under observation, was counted as agent work. Fixed by
excluding `logs/` — and later `tools/sddlog/` — at both capture time (git
pathspec) and derivation time (metrics filter). The derivation-time filter is
the important half: the event log is append-only, so events written before a
path was excluded must be *filtered*, never rewritten.

**Phase timing depended on operator memory.** The session was interrupted
after the plan phase's agent run finished and before the phase-end marker was
issued. Marker-to-marker wall clock for that phase read 251,512 seconds —
roughly three days. Fixed by deriving `active_seconds` from the last real-time
observation and flagging phases whose trailing idle exceeds five minutes. The
flag is still visible in `R001`'s verification output, deliberately: the run
is reported with its defect documented rather than re-run to look clean.

**The first fix for that was itself wrong.** `active_seconds` initially
counted *any* event in the phase as activity — including the operator's own
note, written three days late, which made the stalled phase look continuously
active and suppressed the warning. Only hook events are real-time
observations; git captures, snapshots, notes, and transcript backfill all
timestamp when the *instrument* ran. The rule is now "only hook events bound a
phase", and a phase with no hook events reports `null` rather than a number
that looks measured.

The generalisable lesson: **an instrument that lives inside the system it
measures will measure itself, and a timing measure that depends on a human
remembering to press a button will eventually measure the human's memory.**
Both were caught only because the pilot produced real data that looked
visibly absurd. Neither would have been caught by the test suite alone — which
is the argument for having run a pilot at all.

## 5. Protocol deviations in R001

Both are recorded as `note` events in the run log and are reproduced here
rather than quietly corrected.

1. **Late phase-end marker (plan phase).** Operator session interrupted; the
   marker was issued ~3 days after the agent finished. `wall_clock_seconds`
   for that phase is invalid and excluded from analysis; `active_seconds`
   (970.8 s) is sound because it derives from agent-side timestamps.
2. **Repository edited during an open phase.** The operator modified
   instrument code while the implement phase was open, violating the standing
   rule. Addressed at the root rather than worked around, by excluding
   `tools/sddlog/` from measurement entirely.

`sddlog verify` reports R001 as passing all six integrity checks, with the
timing warning surfaced.

## 6. Readiness for Weeks 5–7

**Ready**: the instrument (57 tests), the protocol, the verification gate, the
repository layout, and a validated end-to-end workflow including hook capture
against a real agent session.

**Still needed before data collection**:

1. **A matched task set.** R001 establishes the harness with one task. Weeks
   5–7 need a small set of tasks of varying complexity, each with a held-out
   test suite written *before* either condition runs.
2. **A specified unstructured condition.** Section 7.3 of the protocol defines
   the mechanics, but the stopping rule — when is a conversational run "done"?
   — is an operator judgement that must be pre-registered to avoid bias.
3. **Pre-registered defect and traceability rubrics**, per the proposal's
   researcher-bias mitigation.
4. **A decision on `/speckit-clarify`.** Section 3.2 argues it should be an
   explicitly manipulated factor rather than an optional extra.
5. **A second run of this pilot task under the unstructured condition**, to
   confirm the comparison mechanics work before committing to the full set.

## 7. Honest limitations of this pilot

- **n = 1.** One task, one condition, one operator, one model. Nothing here is
  a finding about SDD's effectiveness; it is a finding about whether the
  *apparatus* works. Only §3.3 (zero upstream revisions) is even a candidate
  for a substantive result, and it needs the controlled study to mean anything.
- **No comparison condition was run.** The 29-minute figure has nothing to be
  compared against yet.
- **The operator is also the researcher**, and reviewed the generated
  specifications only superficially — which likely *understates* the true human
  cost of SDD as a methodology practised properly.
- **Wall-clock timing for one phase is unrecoverable**, as documented above.
