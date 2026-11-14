# Run report: R010C

| Field | Value |
| --- | --- |
| Task | T-TARX-01-CR |
| Condition | sdd_secure |
| Model | claude-opus-5 |
| Agent | claude-code |
| Computed at | 2026-11-13T03:51:54.479Z |

## Totals

| Measure | Value |
| --- | --- |
| Active time, all phases (s) | 23849.9 |
| Active time, reliable phases only (s) | 23849.9 |
| Wall-clock, run start to end (s) | 23897.4 |
| Phases completed | 4 |
| Human prompts (turns) | 5 |
| Prompt words | 318 |
| Agent outputs | 0 |
| Output words | 0 |
| Tool calls | 112 |
| Lines added | 9691 |
| Lines removed | 111 |
| Distinct files touched | 22 |
| Model messages | 137 |
| Input tokens, incl. cache reads and writes | 20205073 |
| Output tokens | 201442 |
| Events logged | 269 |

## Per phase

| Phase | Active (s) | Wall-clock (s) | Turns | Prompt words | Tool calls | Files | +Lines | -Lines | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| specify | 345.8 | 353.8 | 1 | 284 | 14 | 2 | 480 | 0 | 23955 |
| plan | 628.1 | 635.6 | 1 | 26 | 22 | 5 | 2640 | 2 | 46879 |
| tasks | 269.1 | 278.5 | 1 | 1 | 13 | 1 | 550 | 0 | 21264 |
| implement | 22606.9 | 22619.1 | 2 | 7 | 63 | 15 | 6021 | 109 | 109344 |

## Artifact growth (words by phase)

| Artifact | specify | plan | tasks | implement |
| --- || --- | --- | --- | --- |
| constitution | 1622 | 1622 | 1622 | 1622 |
| spec | 4589 | 4589 | 4589 | 4589 |
| prior:001-tarx-cli/spec | 3789 | 3789 | 3789 | 3789 |
| prior:001-tarx-cli/plan | 2140 | 2140 | 2140 | 2140 |
| prior:001-tarx-cli/tasks | 5189 | 5189 | 5189 | 5189 |
| prior:001-tarx-cli/research | 3112 | 3112 | 3112 | 3112 |
| prior:001-tarx-cli/data-model | 1581 | 1581 | 1581 | 1581 |
| prior:001-tarx-cli/quickstart | 1050 | 1050 | 1050 | 1050 |
| plan | - | 2976 | 2976 | 2976 |
| research | - | 3535 | 3535 | 3535 |
| data-model | - | 1612 | 1612 | 1612 |
| quickstart | - | 1057 | 1057 | 1057 |
| tasks | - | - | 5776 | 5735 |
