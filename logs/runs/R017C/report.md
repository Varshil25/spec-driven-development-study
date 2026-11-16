# Run report: R017C

| Field | Value |
| --- | --- |
| Task | T-PASTE-01-CR |
| Condition | sdd_secure |
| Model | claude-opus-5 |
| Agent | claude-code |
| Computed at | 2026-11-16T09:07:21.957Z |

## Totals

| Measure | Value |
| --- | --- |
| Active time, all phases (s) | 2872.3 |
| Active time, reliable phases only (s) | 2872.3 |
| Wall-clock, run start to end (s) | 2909.6 |
| Phases completed | 4 |
| Human prompts (turns) | 7 |
| Prompt words | 337 |
| Agent outputs | 0 |
| Output words | 0 |
| Tool calls | 112 |
| Lines added | 9168 |
| Lines removed | 148 |
| Distinct files touched | 20 |
| Model messages | 137 |
| Input tokens, incl. cache reads and writes | 15027480 |
| Output tokens | 172074 |
| Events logged | 263 |

## Per phase

| Phase | Active (s) | Wall-clock (s) | Turns | Prompt words | Tool calls | Files | +Lines | -Lines | Output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| specify | 275.3 | 281.9 | 1 | 262 | 17 | 2 | 1048 | 0 | 18904 |
| plan | 665.6 | 671.0 | 1 | 26 | 19 | 5 | 3068 | 0 | 48808 |
| tasks | 347.8 | 355.9 | 1 | 1 | 18 | 1 | 608 | 0 | 25343 |
| implement | 1583.6 | 1588.7 | 4 | 48 | 58 | 14 | 4444 | 148 | 79019 |

## Artifact growth (words by phase)

| Artifact | specify | plan | tasks | implement |
| --- || --- | --- | --- | --- |
| constitution | 1477 | 1477 | 1477 | 1477 |
| spec | 5185 | 5185 | 5185 | 5185 |
| prior:001-pastebin-service/spec | 4211 | 4211 | 4211 | 4211 |
| prior:001-pastebin-service/plan | 3721 | 3721 | 3721 | 3721 |
| prior:001-pastebin-service/tasks | 5240 | 5240 | 5240 | 5240 |
| prior:001-pastebin-service/research | 4503 | 4503 | 4503 | 4503 |
| prior:001-pastebin-service/data-model | 1699 | 1699 | 1699 | 1699 |
| prior:001-pastebin-service/quickstart | 1335 | 1335 | 1335 | 1335 |
| plan | - | 4834 | 4834 | 4834 |
| research | - | 4450 | 4450 | 4450 |
| data-model | - | 2785 | 2785 | 2785 |
| quickstart | - | 1437 | 1437 | 1519 |
| tasks | - | - | 5389 | 5332 |
