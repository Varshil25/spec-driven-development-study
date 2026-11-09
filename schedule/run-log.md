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
| R007 | | T-PASTE-01 | sdd_clarify | | | | |  |
| R007C | | T-PASTE-01-CR | sdd_clarify | | | | | change request on R007 |
| R008 | | T-BOOKMARKS-01 | unstructured | | | | |  |
| R008C | | T-BOOKMARKS-01-CR | unstructured | | | | | change request on R008 |
| R026 | | T-QNOTES-01 | unstructured | | | | |  |
| R027 | | T-QIMPORT-01 | sdd_clarify | | | | |  |
| R009 | | T-ACCOUNTS-01 | sdd_clarify | | | | |  |
| R009C | | T-ACCOUNTS-01-CR | sdd_clarify | | | | | change request on R009 |
| R010 | | T-TARX-01 | sdd_secure | | | | |  |
| R010C | | T-TARX-01-CR | sdd_secure | | | | | change request on R010 |
| R011 | | T-REDACT-01 | sdd_clarify | | | | |  |
| R011C | | T-REDACT-01-CR | sdd_clarify | | | | | change request on R011 |
| R012 | | T-PASTE-01 | unstructured | | | | |  |
| R012C | | T-PASTE-01-CR | unstructured | | | | | change request on R012 |
| R013 | | T-BOOKMARKS-01 | sdd | | | | |  |
| R013C | | T-BOOKMARKS-01-CR | sdd | | | | | change request on R013 |
| R028 | | T-QNOTES-01 | sdd_clarify | | | | |  |
| R029 | | T-QIMPORT-01 | sdd | | | | |  |
| R014 | | T-ACCOUNTS-01 | unstructured | | | | |  |
| R014C | | T-ACCOUNTS-01-CR | unstructured | | | | | change request on R014 |
| R015 | | T-TARX-01 | unstructured | | | | |  |
| R015C | | T-TARX-01-CR | unstructured | | | | | change request on R015 |
| R016 | | T-REDACT-01 | sdd | | | | |  |
| R016C | | T-REDACT-01-CR | sdd | | | | | change request on R016 |
| R017 | | T-PASTE-01 | sdd_secure | | | | |  |
| R017C | | T-PASTE-01-CR | sdd_secure | | | | | change request on R017 |
| R018 | | T-BOOKMARKS-01 | sdd_clarify | | | | |  |
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
