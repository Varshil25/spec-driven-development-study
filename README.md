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
  3 conditions = 15 runs), its pre-registration and runbook, `sddlog` 1.1,
  the task set, the scoring tools, and one practice comparison on a login task.
  The 15 study runs have not been carried out yet. See the
  [Weeks 5–9 report](docs/WEEKS-5-9-REPORT.md).

Study runs (R002 onwards) land in `logs/runs/` alongside the pilot run, under
protocol 1.1.

**Sealed held-out tests.** The held-out test suites for the five study tasks,
with their reference implementations, are kept out of this repository until
the last study run is finished. Their SHA-256 hashes are recorded in section 11
of the [pre-registration](docs/PREREGISTRATION.md), so anyone can check later
that the published suites are the ones frozen before any data existed.

## What is here

| Path | What it is |
| --- | --- |
| [docs/WEEKS-5-9-REPORT.md](docs/WEEKS-5-9-REPORT.md) | **Deliverable.** Weeks 5–9 progress report: study design, validation, practice comparison, revised schedule |
| [docs/PREREGISTRATION.md](docs/PREREGISTRATION.md) | **Deliverable.** Design, conditions, fixed prompts, stopping rule, measures, rubrics, analysis plan, sealing record, deviations log |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Operator checklist for every study run |
| [docs/LOGGING-PROTOCOL.md](docs/LOGGING-PROTOCOL.md) | **Deliverable.** The logging protocol (version 1.1): capture architecture, event schema, measures, operator procedure, verification gate, limitations |
| [docs/PILOT-REPORT.md](docs/PILOT-REPORT.md) | **Deliverable.** What the pilot run showed, and what it changed about the study design |
| [tools/sddlog/sddlog.py](tools/sddlog/sddlog.py) | The instrument: run lifecycle, hook capture, git edit capture, transcript ingest, metrics, verification |
| [tools/sddlog/tests/](tools/sddlog/tests/) | 67 tests covering redaction, event invariants, hook payloads, edit capture, metrics, verification, and the three study conditions |
| [tools/study/](tools/study/) | Study tools: base-repository builder, stopping-rule checker, scorer, coding-sheet generator, schedule generator |
| [tasks/](tasks/) | Task texts and stopping-rule examples: 5 study tasks, the pilot task T-SPLIT-01, and the practice task T-LOGIN-01 |
| [operator/answer-sheets/](operator/answer-sheets/) | Product-owner answers to each task's open points, and the rules for answering |
| [prompts/](prompts/) | The fixed constitution and plan prompts, and what is typed in each phase |
| [schedule/](schedule/) | Counterbalanced run order (seed 20261023) and the run log |
| [coding/](coding/) | Requirement register for the Part III traceability and security coding |
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
