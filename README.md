# SDD Pilot — Milestone 2

Pilot project repository and logging infrastructure for the independent study
*Evaluating and Extending Spec-Driven Development: An Empirical Study of
GitHub Spec Kit*.

This repository is **both** the Milestone 2 deliverables:

1. a complete, instrumented run of GitHub Spec Kit's full command sequence on
   a small pilot feature, and
2. the logging instrument (`sddlog`) and written protocol that will govern
   data collection for the controlled study in Weeks 5–7.

## What is here

| Path | What it is |
| --- | --- |
| [docs/LOGGING-PROTOCOL.md](docs/LOGGING-PROTOCOL.md) | **Deliverable.** The logging protocol: capture architecture, event schema, measures, operator procedure, verification gate, limitations |
| [docs/PILOT-REPORT.md](docs/PILOT-REPORT.md) | **Deliverable.** What the pilot run showed, and what it changed about the study design |
| [tools/sddlog/sddlog.py](tools/sddlog/sddlog.py) | The instrument: run lifecycle, hook capture, git edit capture, transcript ingest, metrics, verification |
| [tools/sddlog/tests/](tools/sddlog/tests/) | 50 tests covering redaction, event invariants, hook payloads, edit capture, metrics, and verification |
| [specs/001-expense-splitter/](specs/001-expense-splitter/) | Spec Kit artifacts produced by the pilot run |
| [.specify/memory/constitution.md](.specify/memory/constitution.md) | Project constitution produced by `/speckit-constitution` |
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
python3 tools/sddlog/sddlog.py run-start --task T-SPLIT-01 --condition sdd --model claude-opus-5
python3 tools/sddlog/sddlog.py phase specify --start
python3 tools/sddlog/sddlog.py phase specify --end
python3 tools/sddlog/sddlog.py run-end

# inspect
python3 tools/sddlog/sddlog.py verify
python3 tools/sddlog/sddlog.py report
python3 tools/sddlog/sddlog.py list
```

Hooks in [.claude/settings.json](.claude/settings.json) capture prompts, tool
calls, and edits automatically. They are inert unless a run is open, so normal
development in this repository is never logged.

Full command reference and operator procedure: [docs/LOGGING-PROTOCOL.md](docs/LOGGING-PROTOCOL.md).

## Relationship to the Weeks 1–2 environment check

Before this repository existed, Spec Kit was installed against GitHub Copilot
and driven through a throwaway website feature to confirm the toolchain worked
end to end. That check was **not** instrumented, so it produced no
measurements, and its working directory was deleted once this repository
superseded it. It is mentioned here only to record that the Weeks 1–2
environment deliverable was met; nothing in the study's data depends on it.
