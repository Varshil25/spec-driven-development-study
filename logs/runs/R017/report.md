# Run report: R017

| Field | Value |
| --- | --- |
| Task | T-PASTE-01 |
| Condition | sdd_secure |
| Model | claude-opus-5 |
| Agent | claude-code |
| Computed at | 2026-11-16T08:18:45.968Z |

## Totals

| Measure | Value |
| --- | --- |
| Active time, all phases (s) | 2900.8 |
| Active time, reliable phases only (s) | 2900.8 |
| Wall-clock, run start to end (s) | 2945.6 |
| Phases completed | 5 |
| Human prompts (turns) | 5 |
| Prompt words | 633 |
| Agent outputs | 0 |
| Output words | 0 |
| Tool calls | 82 |
| Lines added | 12450 |
| Lines removed | 117 |
| Distinct files touched | 29 |
| Model messages | 112 |
| Input tokens, incl. cache reads and writes | 11850094 |
| Output tokens | 190959 |
| Events logged | 231 |

## Per phase

| Phase | Active (s) | Wall-clock (s) | Turns | Prompt words | Tool calls | Files | +Lines | -Lines | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| constitution | 87.2 | 93.0 | 1 | 246 | 8 | 1 | 323 | 35 | 5292 |
| specify | 300.3 | 311.8 | 1 | 359 | 11 | 2 | 978 | 0 | 15366 |
| plan | 548.8 | 554.7 | 1 | 26 | 8 | 6 | 3434 | 0 | 41414 |
| tasks | 323.2 | 329.0 | 1 | 1 | 11 | 1 | 592 | 2 | 25028 |
| implement | 1641.3 | 1645.4 | 1 | 1 | 44 | 21 | 7123 | 80 | 103859 |

## Artifact growth (words by phase)

| Artifact | constitution | specify | plan | tasks | implement |
| --- || --- | --- | --- | --- | --- |
| constitution | 1477 | 1477 | 1477 | 1477 | 1477 |
| spec | - | 4211 | 4211 | 4211 | 4211 |
| plan | - | - | 3563 | 3563 | 3721 |
| research | - | - | 4503 | 4503 | 4503 |
| data-model | - | - | 1699 | 1699 | 1699 |
| quickstart | - | - | 1335 | 1335 | 1335 |
| tasks | - | - | - | 5284 | 5240 |
