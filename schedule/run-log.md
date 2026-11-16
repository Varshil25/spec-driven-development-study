# Run log

One line per run, filled in at step 4 of the runbook. Status is `ok`, `warn` (explained by a note) or `excluded` (give the reason and the replacement run ID). Each Python study build is followed, in the same clone, by its change request (the build's ID plus `C`), logged on its own line.

| Run | Date | Task | Condition | verify | Follow-ups | Cap reached? | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R002 | 2026-11-03 | T-SPLIT-01 | unstructured | OK | 0 | no | ok | mechanics check; operated by Claude; 1 LISTED, no questions; 7.9 min active, 1.86M tokens, about $2.49 (Claude Code's estimate) |
| R003 | 2026-11-03 | T-SPLIT-01 | sdd_clarify | OK | 0 | no | ok | mechanics check; operated by Claude; 1 question (clarify, NOPREF), 5 LISTED; the agent took the NOPREF reply as delegating all remaining clarify questions; 32.8 min active, 8.5M tokens, about $12.19 (Claude Code's estimate) |
| R024 | | T-QCOUNT-01 | unstructured | | | | | Java mechanics check |
| R025 | | T-QCOUNT-01 | sdd_clarify | | | | | Java mechanics check |
| R004 | 2026-11-04 | T-ACCOUNTS-01 | sdd_secure | OK | 0 | no | ok | operated by Claude; no questions, 5 LISTED; implement session interrupted when the operator's workspace restarted, resumed with the fixed message (1 RESUME; gap 2.8 min, inside active time); 65.7 min active, 17.2M tokens; Claude Code cost $10.00 excludes the interrupted call |
| R004C | 2026-11-04 | T-ACCOUNTS-01-CR | sdd_secure | OK | 0 | no | ok | change request on R004; operated by Claude; no questions, 3 LISTED; implement stopped at the account's 5-hour usage limit and was resumed with the fixed message after it reset (1 RESUME, about 43 min wait, inside active time); Claude Code cost $29.64 |
| R005 | 2026-11-04 | T-TARX-01 | sdd | OK | 0 | no | ok | operated by Claude; 1 question (implement, NOPREF), 5 LISTED; agent edited data-model.md during implement; Claude Code cost $22.03 |
| R005C | 2026-11-05 | T-TARX-01-CR | sdd | OK | 0 | no | ok | change request on R005; operated by Claude; no questions, 4 LISTED; Claude Code cost $12.94 |
| R006 | 2026-11-09 | T-REDACT-01 | sdd_secure | OK | 0 | no | ok | operated by Claude; 1 SAFETY (specify), 1 answer I1 (plan), 5 LISTED; plan session interrupted twice (usage limit 5 Nov, then workspace stops) and resumed 9 Nov with the fixed message: plan-phase and total active time include the idle gaps and are NOT usable; tokens and turns are; Claude Code cost $26.20 |
| R006C | 2026-11-09 | T-REDACT-01-CR | sdd_secure | OK | 0 | no | ok | change request on R006; operated by Claude; no questions, 4 LISTED; agent edited the original feature's plan.md; Claude Code cost $17.96 |
| R007 | 2026-11-09 | T-PASTE-01 | sdd_clarify | OK | 0 | no | ok | operated by Claude; 5 clarify questions, all NOPREF (none matched the sheet); implement stopped at the usage limit, then a container restart; resumed with the fixed message, so implement and total active time include the 3.4 h wait and are not usable; Claude Code cost $25.35 |
| R007C | 2026-11-10 | T-PASTE-01-CR | sdd_clarify | OK | 0 | no | ok | change request on R007; operated by Claude; 6 questions: clarify NOPREF x2 and SAFETY x3, implement NOPREF x1; correction: an earlier note of a slip in implement was wrong (the operator's keyword check had matched the run tool's own prompt line); for the same reason one clarify SAFETY reply (password-hashing question, no keyword in the agent's text) should have been NOPREF; implement stopped at the usage limit 9 Nov and was resumed 10 Nov with the fixed message, so implement and total active time include an 18.8 h wait and are not usable; Claude Code cost $42.41 |
| R008 | 2026-11-10 | T-BOOKMARKS-01 | unstructured | OK | 0 | no | ok | operated by Claude; no questions, 1 LISTED; Claude Code cost $0.67 |
| R008C | 2026-11-10 | T-BOOKMARKS-01-CR | unstructured | OK | 0 | no | ok | change request on R008; operated by Claude; no questions, 1 LISTED (ended with an offer about skipping bad rows, the point entry I2 covers; classified listed under the offer rule); Claude Code cost $1.22 |
| R026 | | T-QNOTES-01 | unstructured | | | | |  |
| R027 | | T-QIMPORT-01 | sdd_clarify | | | | |  |
| R009 | 2026-11-10 | T-ACCOUNTS-01 | sdd_clarify | OK | 0 | no | ok | operated by Claude; 4 clarify questions: SAFETY x2, NOPREF x2 (none matched the sheet); first session stopped at the usage limit before any work and was resumed after 4.2 h with the fixed message; constitution and total active time include that wait and are not usable; Claude Code cost $19.59 |
| R009C | 2026-11-11 | T-ACCOUNTS-01-CR | sdd_clarify | OK | 0 | no | ok | change request on R009; operated by Claude; 5 clarify questions: I1, I3 (first answer-sheet matches in the study), SAFETY x1, NOPREF x2; stopped at the usage limit twice (start of specify, start of implement) and resumed with the fixed message; specify, implement and total active time include the waits and are not usable; Claude Code cost $31.58 |
| R010 | 2026-11-12 | T-TARX-01 | sdd_secure | OK | 0 | no | ok | operated by Claude; no questions, 5 LISTED; implement stopped at the usage limit 11 Nov and was resumed 12 Nov with the fixed message; implement and total active time include the wait and are not usable; Claude Code cost $18.22 |
| R010C | 2026-11-12 | T-TARX-01-CR | sdd_secure | OK | 0 | no | ok | change request on R010; operated by Claude; no questions, 4 LISTED; implement stopped at the usage limit and was resumed with the fixed message; implement and total active time include the wait and are not usable; Claude Code cost $21.85 |
| R011 | 2026-11-13 | T-REDACT-01 | sdd_clarify | OK | 0 | no | ok | operated by Claude; 5 clarify questions: NOPREF x4, SAFETY x1 (none matched the sheet); plan stopped at the usage limit and was resumed with the fixed message; plan and total active time include the wait and are not usable; agent reports its email pattern is quadratic on long lines and scaled its own long-line test down; Claude Code cost $21.30 |
| R011C | 2026-11-14 | T-REDACT-01-CR | sdd_clarify | FAIL | 0 | no | excluded | change request on R011; operated by Claude; two copies of the run tool drove the same run from the end of clarify through plan (operator error), so verify reports a duplicated sequence number and doubled phase markers; kept in logs/runs/R011C, redone as R019C (section 9); Claude Code cost $27.67 |
| R019C | 2026-11-14 | T-REDACT-01-CR | sdd_clarify | OK | 0 | no | ok | rerun of R011C (spare ID), on R011's finished build from a fresh clone; operated by Claude; plan resumed after the usage limit (same session); Claude Code 2.1.325; Claude Code cost $24.74 |
| R012 | 2026-11-14 | T-PASTE-01 | unstructured | OK | 0 | no | ok | operated by Claude; Claude Code 2.1.317 (pinned); Claude Code cost $2.43 |
| R012C | 2026-11-14 | T-PASTE-01-CR | unstructured | OK | 0 | no | ok | change request on R012; operated by Claude; Claude Code 2.1.317 (pinned); the agent's own pkill matched the harness and ended its first call, and the resumed session then stopped at the usage limit; both resumed with the fixed message; cost excludes the calls that were cut off; Claude Code cost $2.61 |
| R013 | 2026-11-14 | T-BOOKMARKS-01 | sdd | OK | 0 | no | ok | operated by Claude; Claude Code 2.1.317 (pinned); Claude Code cost $9.91 |
| R013C | 2026-11-14 | T-BOOKMARKS-01-CR | sdd | OK | 0 | no | ok | change request on R013; operated by Claude; Claude Code 2.1.317 (pinned); Claude Code cost $10.44 |
| R028 | | T-QNOTES-01 | sdd_clarify | | | | |  |
| R029 | | T-QIMPORT-01 | sdd | | | | |  |
| R014 | 2026-11-14 | T-ACCOUNTS-01 | unstructured | OK | 0 | no | ok | operated by Claude; Claude Code 2.1.317 (pinned); Claude Code cost $1.15 |
| R014C | 2026-11-14 | T-ACCOUNTS-01-CR | unstructured | OK | 0 | no | ok | change request on R014; operated by Claude; Claude Code 2.1.317 (pinned); Claude Code cost $2.21 |
| R015 | 2026-11-14 | T-TARX-01 | unstructured | OK | 0 | no | ok | operated by Claude; Claude Code 2.1.317 (pinned); Claude Code cost $1.53 |
| R015C | 2026-11-14 | T-TARX-01-CR | unstructured | OK | 0 | no | ok | change request on R015; operated by Claude; Claude Code 2.1.317 (pinned); Claude Code cost $1.99 |
| R016 | 2026-11-16 | T-REDACT-01 | sdd | OK | 0 | no | ok | operated by Claude; Claude Code 2.1.317 (pinned); implement stopped at the usage limit and was resumed in the same session about 25 hours later; Claude Code cost $15.79 |
| R016C | 2026-11-16 | T-REDACT-01-CR | sdd | OK | 0 | no | ok | change request on R016; operated by Claude; Claude Code 2.1.317 (pinned); implement resumed after the usage limit; Claude Code cost $25.64 |
| R017 | 2026-11-16 | T-PASTE-01 | sdd_secure | OK | 0 | no | ok | operated by Claude; Claude Code 2.1.317 (pinned); Claude Code cost $14.94 |
| R017C | 2026-11-16 | T-PASTE-01-CR | sdd_secure | OK | 0 | no | ok | change request on R017; operated by Claude; Claude Code 2.1.317 (pinned); Claude Code cost $16.83 |
| R018 | 2026-11-16 | T-BOOKMARKS-01 | sdd_clarify | OK | 0 | no | ok | operated by Claude; Claude Code 2.1.317 (pinned); clarify resumed after the usage limit (same session); Claude Code cost $18.30 |
| R018C | | T-BOOKMARKS-01-CR | sdd_clarify | | | | | change request on R018 |
| R030 | | T-QNOTES-01 | sdd | | | | |  |
| R031 | | T-QIMPORT-01 | unstructured | | | | |  |
| R034 | | T-ACCOUNTS-01 | sdd | | | | |  |
| R034C | | T-ACCOUNTS-01-CR | sdd | | | | | change request on R034 |
| R035 | | T-TARX-01 | sdd_clarify | | | | |  |
| R035C | | T-TARX-01-CR | sdd_clarify | | | | | change request on R035 |
| R036 | | T-REDACT-01 | unstructured | | | | |  |
| R036C | | T-REDACT-01-CR | unstructured | | | | | change request on R036 |
| R037 | | T-PASTE-01 | sdd | | | | |  |
| R037C | | T-PASTE-01-CR | sdd | | | | | change request on R037 |
| R038 | | T-BOOKMARKS-01 | sdd_secure | | | | |  |
| R038C | | T-BOOKMARKS-01-CR | sdd_secure | | | | | change request on R038 |
| R021 | | T-REDACT-01 | sdd_clarify | | | | | replication |
| R021C | | T-REDACT-01-CR | sdd_clarify | | | | | change request on R021 |
| R022 | | T-REDACT-01 | sdd | | | | | replication |
| R022C | | T-REDACT-01-CR | sdd | | | | | change request on R022 |
| R023 | | T-REDACT-01 | unstructured | | | | | replication |
| R023C | | T-REDACT-01-CR | unstructured | | | | | change request on R023 |
| R039 | | T-REDACT-01 | sdd_secure | | | | | replication |
| R039C | | T-REDACT-01-CR | sdd_secure | | | | | change request on R039 |
