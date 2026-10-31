> **Archived as submitted.** This is the text of the Weeks 3–4 Plan and Report
> (Milestone 2, originally a Word document), kept unchanged as the record of
> that period. Two later corrections: the "325 lines of source code" in
> section 4 are physical lines; the pilot's product code is 168 non-blank,
> non-comment lines. And the advisor question in section 7 was settled in
> Week 7: the advisor of record is Yan Wang.

**Weeks 3–4 Plan and Report**

Evaluating and Extending Spec-Driven Development: GitHub Spec Kit and OpenOwls SD-KDP

| Student | Varshil Patel |
| --- | --- |
| Program | MS Computer Science, Temple University |
| Faculty Advisor | Alex Pang |
| Reporting Period | Weeks 3–4 of 16 — Part II: Pilot |
| Milestone | Milestone 2 — Pilot Run |
| Deliverables | Pilot project repository; logging protocol |

# 1. Purpose of This Period

Weeks 3–4 open Part II of the independent study. The goal is twofold: to learn GitHub Spec Kit's workflow firsthand by running its full command sequence on a small pilot feature, and to build and validate the logging infrastructure that will make controlled data collection possible in Weeks 5–7.

The pilot is deliberately not an experiment. Its purpose is to establish that the apparatus works — that prompts, edits, and outputs can be captured reliably enough that the numbers reported in Part III can be traced back to timestamped evidence. Every substantive finding below concerns the apparatus, not SDD's effectiveness.

# 2. Activities Completed

## 2.1 Pilot run of the full Spec Kit sequence

A fresh repository was initialised with Spec Kit 1.0.6, the Claude Code integration, and Spec Kit's bundled git extension. Instrumentation was installed before the first workflow command ran, so the pilot is captured from step zero.

The full sequence — constitution → specify → plan → tasks → implement — was then executed end to end on one small feature: a standard-library-only Python CLI that reads a CSV of shared group expenses and prints the minimal set of payments that settles every participant's balance. The feature was chosen to be completable in one sitting while still exercising the properties the Weeks 5–7 tasks require: exact-arithmetic edge cases, a defined error contract, and a testable acceptance surface.

The feature works. Fifty-eight tests pass, and the CLI's behaviour was verified independently of the agent's own report.

## 2.2 Logging instrumentation

A capture tool (sddlog) was written in standard-library Python. It records every run through three deliberately overlapping paths, so that no single misconfiguration can silently produce an empty or misleading dataset entry:

- Agent hooks — Claude Code SessionStart, UserPromptSubmit, PostToolUse, and Stop hooks capture prompt text, tool calls, per-edit line deltas, and session boundaries in real time. Primary source for prompts and turn counts.
- Git phase capture — at each phase boundary the working tree is committed and diffed, yielding exact line counts and full unified diffs. Authoritative source for edits.
- Transcript ingestion — an idempotent backfill from the agent's session log, deduplicated by content hash. A recovery path only, never primary.

Spec Kit artifacts are additionally hashed and snapshotted at every phase boundary, which makes specification drift measurable after the fact. Credential redaction runs inside the single write path, before anything reaches disk.

## 2.3 Validation and testing

- 57 automated tests covering redaction, event-log invariants, synthetic hook payloads, git edit capture, artifact snapshots, metrics derivation, phase-timing reliability, and the verification gate.
- Hook wiring was verified end to end against a real headless agent session rather than simulated — a prompt, a file edit, and both session boundaries were confirmed captured.
- The pilot feature's own 58 tests and its command-line behaviour were re-run independently rather than accepting the agent's summary.

# 3. Deliverables

| **Deliverable** | **Status** | **Location** |
| --- | --- | --- |
| Pilot project repository | Complete | sdd-pilot/ |
| Full Spec Kit sequence executed and captured | Complete | logs/runs/R001/ |
| Logging protocol (v1.0, ratified) | Complete | docs/LOGGING-PROTOCOL.md |
| Logging instrument with test suite | Complete | tools/sddlog/ |
| Pilot run report | Complete | docs/PILOT-REPORT.md |
| Matched task set for Weeks 5–7 | Not started | — |
| Unstructured-condition run of pilot task | Not started | — |

# 4. Measurements from the Pilot Run

Run R001, task T-SPLIT-01, condition SDD, model claude-opus-5, agent claude-code. All figures derive from the append-only event log and are recomputable.

| **Phase** | **Active time** | **Turns** | **Human words** | **Tool calls** | **Files** | **Lines added** |
| --- | --- | --- | --- | --- | --- | --- |
| constitution | 1m 13s | 1 | 92 | 7 | 1 | 227 |
| specify | 2m 00s | 1 | 135 | 4 | 2 | 316 |
| plan | 16m 11s | 1 | 49 | 5 | 5 | 834 |
| tasks | 2m 10s | 1 | 1 | 9 | 1 | 406 |
| implement | 7m 25s | 1 | 1 | 25 | 14 | 1,681 |
| Total | 29m 00s | 5 | 278 | 50 | 22 | 3,464 |

**Specification consumed 74% of active time.** The four pre-implementation phases took 21m 34s against 7m 25s for implementation. If SDD's benefit is real, this ratio is the price it must be measured against, and it is the single most important quantity for RQ3.

**The human wrote 278 words; the workflow produced 7,580.** Across the constitution, specification, plan, research notes, data model, quickstart, and task list, the generated specification set is roughly 27 times the human input that seeded it, and governs 325 lines of source code.

**The entire feature took five human prompts — one per phase.** Whatever the unstructured condition costs in Weeks 5–7, this is the SDD baseline it will be compared against, and it is very low.

# 5. Findings

## 5.1 Nothing upstream was ever revised

Because artifacts were hashed at every phase boundary, revision counts are directly measurable. The constitution, specification, plan, research notes, data model, and quickstart each recorded zero revisions after creation. Only the task list changed, and only to tick checkboxes.

The core SDD slogan — “fix the spec, not the output” — describes a feedback loop that did not occur even once in this run. Implementation raised no issue that flowed back into the specification. Two readings are possible and the pilot cannot distinguish them: either the specification was good enough that no revision was warranted, or the workflow applies no pressure to revise it and drift would go unnoticed. Either way, specification-revision count is now a measure worth collecting in Weeks 5–7, and the instrument already captures it.

## 5.2 Ambiguity is absorbed rather than surfaced

The specification stage resolved four genuine ambiguities in the task description — amount format, currency, participant identity, and the meaning of “minimal” — by writing an Assumptions section and proceeding. It raised no clarification markers and asked nothing. Spec Kit ships a separate clarify command for exactly this purpose, and it is optional.

This bears directly on RQ4. If a measured SDD benefit turns out to come from the clarify stage rather than from specification as such, that is a considerably more actionable finding than “SDD works”. The clarify stage should therefore be an explicitly manipulated factor in the Weeks 5–7 design rather than an optional extra.

## 5.3 The planning stage produces a document set, not a plan

The plan command generated five separate specification documents for a feature whose implementation is roughly 325 lines. The cost of SDD is not one extra prompt per stage; it is the generation, and in principle the human review, of a document set that grows faster than the code it governs. In this pilot the operator did not read all five before proceeding — which is almost certainly what a time-pressured developer would also do, and which means the measured cost here understates the cost of the methodology practised properly.

## 5.4 Three instrument defects were found by running the pilot

Each of the following would have silently corrupted the Weeks 5–7 dataset. None was caught by the test suite; all three surfaced only because the pilot produced real data that looked visibly wrong.

- The instrument measured itself. The first phase capture reported 200 changed lines where three were real — the logger's own event file, written inside the repository under observation, was counted as agent work. Both the log directory and the instrument's own source are now excluded at capture time and again when metrics are derived, the latter because the event log is append-only and must be filtered rather than rewritten.
- Phase timing depended on operator memory. The session was interrupted after an agent run finished but before the phase-end marker was issued, and that phase's marker-to-marker wall clock read roughly three days. Timing is now derived from the last real-time observation within a phase, and phases with excessive trailing idle are flagged automatically.
- The first fix for that was itself wrong. The new measure initially counted any event as activity, including the operator's own note written three days late, which made the stalled phase look continuously active and suppressed the warning. Only agent-hook events are genuine real-time observations; a phase containing none now reports no timing at all rather than a number that looks measured.

The generalisable lesson is that an instrument living inside the system it measures will measure itself, and a timing measure depending on a human remembering to press a button will eventually measure that human's memory. This is the argument for having run a pilot at all.

# 6. Protocol Deviations in Run R001

Both deviations are recorded as events in the run log and are reported here rather than quietly corrected. The run was not re-run to make it look clean.

- Late phase-end marker on the plan phase, as described above. That phase's wall-clock figure is invalid and excluded from analysis; its active-time figure is sound because it derives from agent-side timestamps.
- The repository was edited while a phase was open, violating the protocol's standing rule. This was addressed at the root by excluding the instrument's own source from measurement entirely.

The verification gate reports R001 as passing all six integrity checks, with the timing warning surfaced rather than suppressed.

# 7. Risks and Open Questions

- The pilot is n = 1: one task, one condition, one operator, one model. Nothing in it is a finding about SDD's effectiveness.
- No comparison condition has been run yet, so the 29-minute figure has nothing to be compared against.
- The stopping rule for the unstructured condition — when is a conversational run “done”? — is an operator judgement and must be pre-registered to avoid bias.
- The operator is also the researcher, and reviewed generated specifications only superficially, which likely understates the true human cost of SDD.
- Agent-internal behaviour (reasoning, retries, context management) is not observable through hooks and remains outside measurement.
- Advisor name discrepancy: the original proposal lists Yan Wang; this report follows the Week 1 report in listing Alex Pang. To be confirmed.

# 8. Plan for Weeks 5–7

Part II data collection begins on schedule. Before the first measured run:

- Select a small set of matched programming tasks of varying complexity, each with a held-out test suite written before either condition runs.
- Pre-register the defect-coding and traceability rubrics, and the stopping rule for the unstructured condition.
- Decide whether the clarify stage becomes an explicitly manipulated factor, per section 5.2.
- Run the pilot task a second time under the unstructured condition to confirm the comparison mechanics before committing to the full task set.

Thereafter, runs proceed in counterbalanced order, each passing the verification gate before entering the dataset.

# 9. Repository Contents

| **Path** | **Contents** |
| --- | --- |
| docs/LOGGING-PROTOCOL.md | The logging protocol: capture architecture, event schema, measures and their mapping to RQ1–RQ4, operator procedure, verification gate, limitations |
| docs/PILOT-REPORT.md | Full pilot report including all measurements and findings |
| tools/sddlog/ | The capture instrument and its 57-test suite |
| specs/001-expense-splitter/ | Spec Kit artifacts produced by the pilot run |
| .specify/memory/constitution.md | Project constitution produced by the constitution command |
| logs/runs/R001/ | Complete event log, unified diffs, per-phase artifact snapshots, derived metrics, and run report |
| src/splitter/, tests/ | The pilot feature implementation and its tests |
