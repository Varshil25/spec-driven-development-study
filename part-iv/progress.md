# Progress

## Latest batch run

None yet.

## Log

| Date | What | Who |
| --- | --- | --- |
| 2026-11-14 | Oracle, seven `ai_specs/` files and corpus list (17 trusted, 3 rejected) drafted; every URL, date and licence in `corpus/sources.csv` checked against the source page, except where left blank | Claude |

| 2026-11-14 | Pipeline scripts: `collect.py`, `distill.py`, `voice_check.py`, `synthesize.py`, `index.py`, `query.py`, `batch.sh`; 18 offline tests pass. S08 collected over HTTP; a second run found it unchanged (incremental check, collect step) | Claude |

| 2026-11-14 | Author approved the Oracle as drafted; chose the subscription (`claude` backend) for distillation, after the last study run; will allow all domains for collection | Author |

## Next

1. Collect S01–S17 once the workspace may reach all domains.
2. One-source trial (S12 or S03): run, read, fix the spec, re-run, until the article passes the voice check and reads in the Oracle's voice.
3. Full corpus (after the last study run); incremental check (batch-process.md); OpenKB on the same corpus and model; both asked Q1–Q8. OpenKB cannot use a Claude subscription (it needs an API key, or an OAuth provider such as GitHub Copilot), so how OpenKB is built is still open.
