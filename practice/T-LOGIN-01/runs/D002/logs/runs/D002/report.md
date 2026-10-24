# Run report: D002

| Field | Value |
| --- | --- |
| Task | T-LOGIN-01 |
| Condition | sdd |
| Model | inherited-subagent |
| Agent | subagent |
| Computed at | 2026-10-24T14:23:21.246Z |

## Totals

| Measure | Value |
| --- | --- |
| Active time, all phases (s) | 0.0 |
| Active time, reliable phases only (s) | 0 |
| Wall-clock, run start to end (s) | 61498.2 |
| Phases completed | 5 |
| Human prompts (turns) | 7 |
| Prompt words | 559 |
| Agent outputs | 0 |
| Output words | 0 |
| Tool calls | 0 |
| Lines added | 5371 |
| Lines removed | 91 |
| Distinct files touched | 28 |
| Events logged | 82 |

## Per phase

| Phase | Active (s) | Wall-clock (s) | Turns | Prompt words | Tool calls | Files | +Lines | -Lines |
| --- | --- | --- | --- | --- | --- | --- | --- |
| constitution | None | 260.1 (unreliable) | 1 | 70 | 0 | 1 | 123 | 35 |
| specify | None | 1389.7 (unreliable) | 2 | 455 | 0 | 2 | 370 | 0 |
| plan | None | 6144.1 (unreliable) | 1 | 26 | 0 | 6 | 1175 | 0 |
| tasks | None | 50399.2 (unreliable) | 2 | 7 | 0 | 1 | 910 | 0 |
| implement | None | 1748.8 (unreliable) | 1 | 1 | 0 | 19 | 2793 | 56 |

## Timing warnings

- constitution: no real-time (hook) events in this phase; active_seconds unavailable and wall_clock_seconds unverified
- specify: no real-time (hook) events in this phase; active_seconds unavailable and wall_clock_seconds unverified
- plan: no real-time (hook) events in this phase; active_seconds unavailable and wall_clock_seconds unverified
- tasks: no real-time (hook) events in this phase; active_seconds unavailable and wall_clock_seconds unverified
- implement: no real-time (hook) events in this phase; active_seconds unavailable and wall_clock_seconds unverified

## Artifact growth (words by phase)

| Artifact | constitution | specify | plan | tasks | implement |
| --- || --- | --- | --- | --- | --- |
| constitution | 1134 | 1134 | 1134 | 1134 | 1134 |
| spec | - | 6857 | 6857 | 6857 | 6857 |
| plan | - | - | 3787 | 3787 | 3787 |
| research | - | - | 4150 | 4150 | 4150 |
| data-model | - | - | 1764 | 1764 | 1764 |
| quickstart | - | - | 978 | 978 | 978 |
| tasks | - | - | - | 9277 | 9221 |
