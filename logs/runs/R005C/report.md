# Run report: R005C

| Field | Value |
| --- | --- |
| Task | T-TARX-01-CR |
| Condition | sdd |
| Model | claude-opus-5 |
| Agent | claude-code |
| Computed at | 2026-11-05T04:11:18.905Z |

## Totals

| Measure | Value |
| --- | --- |
| Active time, all phases (s) | 2304.5 |
| Active time, reliable phases only (s) | 2304.5 |
| Wall-clock, run start to end (s) | 2339.0 |
| Phases completed | 4 |
| Human prompts (turns) | 4 |
| Prompt words | 312 |
| Agent outputs | 0 |
| Output words | 0 |
| Tool calls | 92 |
| Lines added | 7572 |
| Lines removed | 88 |
| Distinct files touched | 13 |
| Model messages | 102 |
| Input tokens, incl. cache reads and writes | 9187138 |
| Output tokens | 164519 |
| Events logged | 218 |

## Per phase

| Phase | Active (s) | Wall-clock (s) | Turns | Prompt words | Tool calls | Files | +Lines | -Lines | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| specify | 238.9 | 247.8 | 1 | 284 | 14 | 2 | 932 | 0 | 18014 |
| plan | 702.9 | 710.3 | 1 | 26 | 18 | 5 | 2906 | 0 | 52973 |
| tasks | 429.4 | 439.1 | 1 | 1 | 16 | 1 | 654 | 0 | 35478 |
| implement | 933.3 | 941.1 | 1 | 1 | 44 | 7 | 3080 | 88 | 58054 |

## Artifact growth (words by phase)

| Artifact | specify | plan | tasks | implement |
| --- || --- | --- | --- | --- |
| constitution | 1205 | 1205 | 1205 | 1205 |
| spec | 4353 | 4353 | 4353 | 4353 |
| prior:001-tar-archive-cli/spec | 3354 | 3354 | 3354 | 3354 |
| prior:001-tar-archive-cli/plan | 1679 | 1679 | 1679 | 1679 |
| prior:001-tar-archive-cli/tasks | 5508 | 5508 | 5508 | 5508 |
| prior:001-tar-archive-cli/research | 1853 | 1853 | 1853 | 1853 |
| prior:001-tar-archive-cli/data-model | 1152 | 1152 | 1152 | 1152 |
| prior:001-tar-archive-cli/quickstart | 841 | 841 | 841 | 841 |
| plan | - | 2689 | 2689 | 2689 |
| research | - | 4347 | 4347 | 4347 |
| data-model | - | 1952 | 1952 | 1952 |
| quickstart | - | 1622 | 1622 | 1614 |
| tasks | - | - | 5228 | 5182 |
