# Run report: R001

| Field | Value |
| --- | --- |
| Task | T-SPLIT-01 |
| Condition | sdd |
| Model | claude-opus-5 |
| Agent | claude-code |
| Computed at | 2026-09-20T18:08:18.157Z |

## Totals

| Measure | Value |
| --- | --- |
| Active time, all phases (s) | 1739.5 |
| Active time, reliable phases only (s) | 768.7 |
| Wall-clock, run start to end (s) | 252472.9 |
| Phases completed | 5 |
| Human prompts (turns) | 5 |
| Prompt words | 278 |
| Agent outputs | 0 |
| Output words | 0 |
| Tool calls | 50 |
| Lines added | 3464 |
| Lines removed | 66 |
| Distinct files touched | 22 |
| Events logged | 159 |

## Per phase

| Phase | Active (s) | Wall-clock (s) | Turns | Prompt words | Tool calls | Files | +Lines | -Lines |
| --- | --- | --- | --- | --- | --- | --- | --- |
| constitution | 73.3 | 79.1 | 1 | 92 | 7 | 1 | 227 | 35 |
| specify | 120.4 | 125.8 | 1 | 135 | 4 | 2 | 316 | 0 |
| plan | 970.8 | 251512.1 (unreliable) | 1 | 49 | 5 | 5 | 834 | 0 |
| tasks | 129.8 | 130.2 | 1 | 1 | 9 | 1 | 406 | 0 |
| implement | 445.2 | 453.3 | 1 | 1 | 25 | 14 | 1681 | 31 |

## Timing warnings

- plan: phase_end marker issued 250541s after last observed activity; wall_clock_seconds is unreliable, use active_seconds

## Artifact growth (words by phase)

| Artifact | constitution | specify | plan | tasks | implement |
| --- || --- | --- | --- | --- | --- |
| constitution | 833 | 833 | 833 | 833 | 833 |
| spec | - | 1865 | 1865 | 1865 | 1865 |
| plan | - | - | 766 | 766 | 766 |
| research | - | - | 715 | 715 | 715 |
| data-model | - | - | 643 | 643 | 643 |
| quickstart | - | - | 503 | 503 | 503 |
| tasks | - | - | - | 2255 | 2229 |
