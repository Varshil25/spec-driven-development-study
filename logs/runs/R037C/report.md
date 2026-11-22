# Run report: R037C

| Field | Value |
| --- | --- |
| Task | T-PASTE-01-CR |
| Condition | sdd |
| Model | claude-opus-5 |
| Agent | claude-code |
| Computed at | 2026-11-20T02:29:58.109Z |

## Totals

| Measure | Value |
| --- | --- |
| Active time, all phases (s) | 4088.6 |
| Active time, reliable phases only (s) | 4088.6 |
| Wall-clock, run start to end (s) | 4120.1 |
| Phases completed | 4 |
| Human prompts (turns) | 5 |
| Prompt words | 307 |
| Agent outputs | 0 |
| Output words | 0 |
| Tool calls | 101 |
| Lines added | 8027 |
| Lines removed | 126 |
| Distinct files touched | 17 |
| Model messages | 121 |
| Input tokens, incl. cache reads and writes | 14873980 |
| Output tokens | 168306 |
| Events logged | 253 |

## Per phase

| Phase | Active (s) | Wall-clock (s) | Turns | Prompt words | Tool calls | Files | +Lines | -Lines | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| specify | 266.3 | 273.2 | 1 | 262 | 13 | 2 | 518 | 2 | 17935 |
| plan | 429.1 | 436.0 | 1 | 26 | 17 | 5 | 2102 | 2 | 31613 |
| tasks | 269.3 | 273.7 | 1 | 1 | 14 | 1 | 533 | 1 | 19756 |
| implement | 3123.9 | 3129.9 | 2 | 18 | 57 | 10 | 4874 | 121 | 99002 |

## Artifact growth (words by phase)

| Artifact | specify | plan | tasks | implement |
| --- || --- | --- | --- | --- |
| constitution | 1155 | 1155 | 1155 | 1155 |
| spec | 4789 | 4789 | 4789 | 4789 |
| prior:001-pastebin-service/spec | 4069 | 4069 | 4069 | 4069 |
| prior:001-pastebin-service/plan | 1613 | 1613 | 1613 | 1613 |
| prior:001-pastebin-service/tasks | 5109 | 5109 | 5109 | 5109 |
| prior:001-pastebin-service/research | 2763 | 2763 | 2763 | 2763 |
| prior:001-pastebin-service/data-model | 1443 | 1443 | 1443 | 1443 |
| prior:001-pastebin-service/quickstart | 1296 | 1296 | 1296 | 1296 |
| plan | - | 1125 | 1125 | 1125 |
| research | - | 2609 | 2609 | 2609 |
| data-model | - | 1679 | 1679 | 1679 |
| quickstart | - | 1964 | 1964 | 1964 |
| tasks | - | - | 4394 | 4852 |
