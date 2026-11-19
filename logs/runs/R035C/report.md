# Run report: R035C

| Field | Value |
| --- | --- |
| Task | T-TARX-01-CR |
| Condition | sdd_clarify |
| Model | claude-opus-5 |
| Agent | claude-code |
| Computed at | 2026-11-19T20:41:33.875Z |

## Totals

| Measure | Value |
| --- | --- |
| Active time, all phases (s) | 3220.8 |
| Active time, reliable phases only (s) | 3220.8 |
| Wall-clock, run start to end (s) | 3258.5 |
| Phases completed | 5 |
| Human prompts (turns) | 10 |
| Prompt words | 384 |
| Agent outputs | 0 |
| Output words | 0 |
| Tool calls | 114 |
| Lines added | 10287 |
| Lines removed | 187 |
| Distinct files touched | 16 |
| Model messages | 155 |
| Input tokens, incl. cache reads and writes | 16393949 |
| Output tokens | 231964 |
| Events logged | 329 |

## Per phase

| Phase | Active (s) | Wall-clock (s) | Turns | Prompt words | Tool calls | Files | +Lines | -Lines | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| specify | 275.4 | 282.8 | 1 | 284 | 14 | 2 | 943 | 1 | 20084 |
| clarify | 501.9 | 508.0 | 6 | 72 | 15 | 1 | 260 | 80 | 33031 |
| plan | 676.4 | 682.2 | 1 | 26 | 19 | 5 | 2539 | 11 | 51703 |
| tasks | 354.9 | 359.6 | 1 | 1 | 14 | 1 | 728 | 0 | 29148 |
| implement | 1412.2 | 1418.7 | 1 | 1 | 52 | 9 | 5817 | 95 | 97998 |

## Artifact growth (words by phase)

| Artifact | specify | clarify | plan | tasks | implement |
| --- || --- | --- | --- | --- | --- |
| constitution | 1084 | 1084 | 1084 | 1084 | 1084 |
| spec | 4622 | 6125 | 6125 | 6125 | 6125 |
| prior:001-tarx-cli/spec | 4399 | 4399 | 4399 | 4399 | 4399 |
| prior:001-tarx-cli/plan | 1300 | 1300 | 1300 | 1300 | 1300 |
| prior:001-tarx-cli/tasks | 5737 | 5737 | 5737 | 5737 | 5737 |
| prior:001-tarx-cli/research | 2034 | 2034 | 2034 | 2034 | 2034 |
| prior:001-tarx-cli/data-model | 1572 | 1572 | 1572 | 1572 | 1572 |
| prior:001-tarx-cli/quickstart | 907 | 907 | 907 | 907 | 907 |
| plan | - | - | 1644 | 1644 | 1644 |
| research | - | - | 2999 | 2999 | 2999 |
| data-model | - | - | 1983 | 1983 | 1983 |
| quickstart | - | - | 1599 | 1599 | 1599 |
| tasks | - | - | - | 5929 | 5876 |
