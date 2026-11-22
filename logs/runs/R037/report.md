# Run report: R037

| Field | Value |
| --- | --- |
| Task | T-PASTE-01 |
| Condition | sdd |
| Model | claude-opus-5 |
| Agent | claude-code |
| Computed at | 2026-11-20T01:21:06.711Z |

## Totals

| Measure | Value |
| --- | --- |
| Active time, all phases (s) | 4047.7 |
| Active time, reliable phases only (s) | 4047.7 |
| Wall-clock, run start to end (s) | 4078.4 |
| Phases completed | 5 |
| Human prompts (turns) | 11 |
| Prompt words | 565 |
| Agent outputs | 0 |
| Output words | 0 |
| Tool calls | 131 |
| Lines added | 10068 |
| Lines removed | 199 |
| Distinct files touched | 25 |
| Model messages | 180 |
| Input tokens, incl. cache reads and writes | 27992743 |
| Output tokens | 217212 |
| Events logged | 292 |

## Per phase

| Phase | Active (s) | Wall-clock (s) | Turns | Prompt words | Tool calls | Files | +Lines | -Lines | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| constitution | 86.6 | 91.9 | 1 | 70 | 8 | 1 | 283 | 35 | 4806 |
| specify | 198.3 | 205.5 | 1 | 359 | 11 | 2 | 506 | 0 | 13915 |
| plan | 381.2 | 385.9 | 1 | 26 | 8 | 6 | 2420 | 0 | 29778 |
| tasks | 365.7 | 369.6 | 1 | 1 | 11 | 1 | 594 | 0 | 30422 |
| implement | 3015.9 | 3019.0 | 7 | 109 | 93 | 19 | 6265 | 164 | 138291 |

## Artifact growth (words by phase)

| Artifact | constitution | specify | plan | tasks | implement |
| --- || --- | --- | --- | --- | --- |
| constitution | 1155 | 1155 | 1155 | 1155 | 1155 |
| spec | - | 4069 | 4069 | 4069 | 4069 |
| plan | - | - | 1613 | 1613 | 1613 |
| research | - | - | 2763 | 2763 | 2763 |
| data-model | - | - | 1390 | 1390 | 1443 |
| quickstart | - | - | 1296 | 1296 | 1296 |
| tasks | - | - | - | 5173 | 5109 |
