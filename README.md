# Spec-Driven Development Study

Research repository for the independent study *Evaluating and Extending
Spec-Driven Development: An Empirical Study of GitHub Spec Kit for Software
Engineering and OpenOwls SD-KDP for Knowledge-Base Production*.

Varshil Patel · MS Computer Science, Temple University

This repository holds the study's instrumentation, its design documents and
its collected data. It contains:

- **Milestone 2 (Weeks 3–4):** an instrumented pilot run of GitHub Spec Kit's
  full command sequence (R001), and the logging instrument `sddlog` with its
  protocol.
- **Milestone 3 (Weeks 5–9):** the design of the controlled study (5 tasks ×
  3 conditions = 15 runs), its pre-registration and runbook, `sddlog` 1.3,
  the task set, the scoring tools, and one practice comparison on a login task.
  This first design (15 runs) was widened in Week 7, below. See the
  [Weeks 5–9 report](docs/WEEKS-5-9-REPORT.md).
- **Week 7:** a Java/Quarkus extension (2 tasks × 3 conditions = 6 more runs,
  R024–R033), added before freezing and analysed separately from the Python
  runs, and the [week-by-week plan to the Dec 5 report](docs/WEEKLY-PLAN.md).
  See the [Java addendum](docs/PREREGISTRATION-JAVA.md). Then, still before
  freezing: a fourth approach, `sdd_secure` (security written into the
  constitution); a **change request** per Python task, run on each build's own
  code, so the study also covers existing projects (107 more sealed held-out
  cases); and a run tool that drives every run in Claude Code. The Python
  design is now 5 tasks × 4 approaches = 20 builds and 20 change requests,
  plus a required replication set (R021–R023, R039), 48 Python runs in all.
  The design was frozen on 4 November 2026 (PR #6).
- **Weeks 8–10:** the study runs, in four counterbalanced rounds. See
  [Status](#status) below and the [run log](schedule/run-log.md).

## Status

*Updated 14 November 2026.*

| Part | Done | Total | Where |
| --- | --- | --- | --- |
| Python mechanics runs (R002, R003) | 2 | 2 | [weeks/week-07](weeks/week-07/) |
| Python study runs, round 1 (R004–R008 + change requests) | 10 | 10 | [weeks/week-08](weeks/week-08/) |
| Python study runs, round 2 (R009–R013 + change requests) | 5 | 10 | [weeks/week-08](weeks/week-08/) |
| Python study runs, rounds 3–4 (R014–R018, R034–R038 + change requests) | 0 | 20 | [weeks/week-09](weeks/week-09/), [weeks/week-10](weeks/week-10/) |
| Replication (R021–R023, R039 + change requests) | 0 | 8 | [weeks/week-10](weeks/week-10/) |
| Java runs (R024–R025 mechanics, R026–R031 study) | — | — | dropped on 14 Nov for time; not run ([deviations log](docs/PREREGISTRATION.md#12-deviations-log)) |

Every finished run passed the stopping rule and the 6 integrity checks. Scoring
against the sealed held-out tests starts once the last run is finished.

**Start here:** [docs/STUDY-OVERVIEW.md](docs/STUDY-OVERVIEW.md) explains the
whole study in plain language, and [weeks/](weeks/) indexes the work week by
week, from Week 1 to Week 10.

Study runs (R002 onwards) land in `logs/runs/` alongside the pilot run, under
protocol 1.3.

**Sealed held-out tests.** The held-out test suites for the five study tasks
and for their change requests, with their reference implementations, are in
[sealed/](sealed/) as two encrypted archives, to be decrypted and published
once the last study run is finished.
Their SHA-256 hashes are recorded in section 11 of the
[pre-registration](docs/PREREGISTRATION.md), so anyone can check later that the
published suites are the ones frozen before any data existed.

## What is here

| Path | What it is |
| --- | --- |
| [docs/STUDY-OVERVIEW.md](docs/STUDY-OVERVIEW.md) | **Start here.** The study in plain language: the four approaches, new and existing projects, the hidden tests, what is measured |
| [weeks/](weeks/) | The work indexed week by week (Weeks 1–10), with the weekly reports |
| [docs/WEEKLY-PLAN.md](docs/WEEKLY-PLAN.md) | **Plan.** Weeks 7–12, from now to the Dec 5 report: who does what each week, gates, and what gets cut first if time runs short |
| [docs/PREREGISTRATION-JAVA.md](docs/PREREGISTRATION-JAVA.md) | **Deliverable.** Addendum for the Java/Quarkus extension: tasks, environment, prompts, measures, analysis, sealing record |
| [docs/WEEKS-5-9-REPORT.md](docs/WEEKS-5-9-REPORT.md) | **Deliverable.** Weeks 5–9 progress report: study design, validation, practice comparison, revised schedule |
| [docs/PREREGISTRATION.md](docs/PREREGISTRATION.md) | **Deliverable.** Design, conditions, fixed prompts, stopping rule, measures, rubrics, analysis plan, sealing record, deviations log |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Operator checklist for every study run |
| [docs/LOGGING-PROTOCOL.md](docs/LOGGING-PROTOCOL.md) | **Deliverable.** The logging protocol (version 1.1): capture architecture, event schema, measures, operator procedure, verification gate, limitations |
| [docs/PILOT-REPORT.md](docs/PILOT-REPORT.md) | **Deliverable.** What the pilot run showed, and what it changed about the study design |
| [tools/sddlog/sddlog.py](tools/sddlog/sddlog.py) | The instrument: run lifecycle, hook capture, git edit capture, transcript ingest, metrics, verification |
| [tools/sddlog/tests/](tools/sddlog/tests/) | 80 tests covering redaction, event invariants, hook payloads, edit capture, metrics, token usage, verification, the four study conditions, and the change-request stage |
| [tools/study/](tools/study/) | Study tools: the run tool (`run_build.py`, which drives each run in Claude Code), base-repository builders (Python and Java), the Quarkus skeleton, stopping-rule checker, scorer (with Java build and SpotBugs support), coding-sheet generator, schedule generator, and their tests |
| [tasks/](tasks/) | Task texts and stopping-rule examples: 5 Python study tasks, 2 Java/Quarkus study tasks (T-QNOTES-01, T-QIMPORT-01), the pilot task T-SPLIT-01, the Java mechanics task T-QCOUNT-01, and the practice task T-LOGIN-01 |
| [operator/answer-sheets/](operator/answer-sheets/) | Product-owner answers to each task's open points, and the rules for answering |
| [prompts/](prompts/) | The fixed constitution and plan prompts (Python and Java versions), and what is typed in each phase |
| [schedule/](schedule/) | Counterbalanced run order (seed 20261023) and the [run log](schedule/run-log.md): one row per run with its date, cost and outcome |
| [logs/runs/](logs/runs/) | Each run's event log, diffs, artifact snapshots, metrics and report (R001 pilot, R002 onwards study) |
| [logs/bundles/](logs/bundles/) | A git bundle of each run's full working repository, so every build can be checked out exactly as it finished |
| [coding/](coding/) | Requirement register for the Part III traceability and security coding |
| [sealed/](sealed/) | The sealed held-out suites (Python builds, Python change requests, and Java once sealed), encrypted until the last study run |
| [practice/T-LOGIN-01/](practice/T-LOGIN-01/) | Practice comparison, excluded from analysis: both builds, their scores, and the task's held-out tests |
| [specs/001-expense-splitter/](specs/001-expense-splitter/) | Spec Kit artifacts produced by the pilot run |
| [.specify/memory/constitution.md](.specify/memory/constitution.md) | Project constitution produced by `/speckit-constitution` in the pilot |
| [logs/runs/R001/](logs/runs/R001/) | The pilot run's complete event log, diffs, artifact snapshots, metrics, and report |
| [src/splitter/](src/splitter/) | The pilot feature's implementation |

## The pilot feature

A stdlib-only Python CLI that reads a CSV of shared group expenses and prints
the minimal set of payments that settles every participant's balance. It was
chosen to be small enough to run end to end in one sitting, while still having
the properties the Weeks 5–7 tasks need: exact-arithmetic edge cases, a
defined error contract, and a testable acceptance surface.

## Running the instrument

```bash
# verify the instrument before collecting any data
python3 -m pytest tools/sddlog/tests/ -q

# open a run, drive the workflow, close it
python3 tools/sddlog/sddlog.py run-start --run-id R002 --task T-SPLIT-01 --condition unstructured --model claude-opus-5
python3 tools/sddlog/sddlog.py phase implement --start
python3 tools/sddlog/sddlog.py phase implement --end
python3 tools/sddlog/sddlog.py run-end

# inspect
python3 tools/sddlog/sddlog.py verify
python3 tools/sddlog/sddlog.py report
python3 tools/sddlog/sddlog.py list
```

Hooks in [.claude/settings.json](.claude/settings.json) capture prompts, tool
calls, and edits automatically. They are inert unless a run is open, so normal
development in this repository is never logged.

Full command reference: [docs/LOGGING-PROTOCOL.md](docs/LOGGING-PROTOCOL.md). Step-by-step
procedure for study runs: [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Relationship to the Weeks 1–2 environment check

Before this repository existed, Spec Kit was installed against GitHub Copilot
and driven through a throwaway website feature to confirm the toolchain worked
end to end. That check was **not** instrumented, so it produced no
measurements, and its working directory was deleted once this repository
superseded it. It is mentioned here only to record that the Weeks 1–2
environment deliverable was met; nothing in the study's data depends on it.
