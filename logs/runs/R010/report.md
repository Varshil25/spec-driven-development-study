# Run report: R010

| Field | Value |
| --- | --- |
| Task | T-TARX-01 |
| Condition | sdd_secure |
| Model | claude-opus-5 |
| Agent | claude-code |
| Computed at | 2026-11-12T21:13:26.748Z |

## Totals

| Measure | Value |
| --- | --- |
| Active time, all phases (s) | 73408.9 |
| Active time, reliable phases only (s) | 73408.9 |
| Wall-clock, run start to end (s) | 73457.2 |
| Phases completed | 5 |
| Human prompts (turns) | 6 |
| Prompt words | 541 |
| Agent outputs | 0 |
| Output words | 0 |
| Tool calls | 79 |
| Lines added | 10146 |
| Lines removed | 189 |
| Distinct files touched | 28 |
| Model messages | 114 |
| Input tokens, incl. cache reads and writes | 13896623 |
| Output tokens | 207905 |
| Events logged | 247 |

## Per phase

| Phase | Active (s) | Wall-clock (s) | Turns | Prompt words | Tool calls | Files | +Lines | -Lines | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| constitution | 106.3 | 111.3 | 1 | 246 | 8 | 1 | 375 | 35 | 6269 |
| specify | 274.1 | 282.3 | 1 | 261 | 10 | 3 | 417 | 0 | 18747 |
| plan | 459.9 | 468.7 | 1 | 26 | 9 | 5 | 2334 | 0 | 35794 |
| tasks | 291.5 | 297.8 | 1 | 1 | 11 | 1 | 613 | 1 | 23412 |
| implement | 72277.1 | 72288.5 | 2 | 7 | 41 | 19 | 6407 | 153 | 123683 |

## Artifact growth (words by phase)

| Artifact | constitution | specify | plan | tasks | implement |
| --- || --- | --- | --- | --- | --- |
| constitution | 1622 | 1622 | 1622 | 1622 | 1622 |
| spec | - | 3789 | 3789 | 3789 | 3789 |
| plan | - | - | 2140 | 2140 | 2140 |
| research | - | - | 3112 | 3112 | 3112 |
| data-model | - | - | 1581 | 1581 | 1581 |
| quickstart | - | - | 1050 | 1050 | 1050 |
| tasks | - | - | - | 5233 | 5189 |
