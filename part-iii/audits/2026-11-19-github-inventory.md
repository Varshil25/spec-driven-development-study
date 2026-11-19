# Part III GitHub inventory audit — 2026-11-19

Repository: Varshil25/spec-driven-development-study

**Inspected revision:** main commit `99e23e4abc016d125cbcb718073b96bbb269b7c1`, tree `ee6f7ddc4e63c6f9a937f8c3c5f483fa9163ae40`.
Evidence: GitHub API recursive tree and UTF-8 contents of `schedule/schedule.csv`, `schedule/run-log.md`, `coding/requirements.csv`, `logs/index.json`, `sealed/README.md`, and the user-supplied report PDF.

| Check | Observed |
|---|---|
| Python study/replication build rows in schedule | 24 |
| Expected build and change-request cells | 48 |
| Expected score JSONs when fully scored | 72 |
| Registered requirements (rows) | 245 |
| Study-run metrics files in committed Git tree | 0 of 48 |
| Study-run score JSONs in committed Git tree | 0 |
| Visible log directories in Git tree | R001, R002, R003 (pilot/mechanics only) |
| Encrypted Python held-out archives | Two: builds and change requests |
| Decrypted held-out suites in Git tree | None |
| Frozen scoring and analysis scripts | Present |
| Run-log study rows | Present as planned rows, many blank; not evidence of completed runs |

**Report-versus-repository gap:** the report describes 16 closed Python runs as of 2026-11-14, a corrupted excluded R011C and replacement R019C. The GitHub tree does not expose the corresponding archives or scoring artifacts. This is an **evidence-location gap**, not proof that those runs did not happen.

**Test status:** 4 synthetic-fixture unit tests of the new preflight script passed in the assistant's working container on 2026-11-19. The existing project's full test suite and frozen analysis were **not run** in that container because the repository and external experiment runs were not locally available.

**Required before empirical Part III verdicts:** obtain the run clones, verify completion/integrity, unseal the held-out suites after the registered gate, score, adjudicate, recode, and run the frozen analyzer. No RQ1–RQ4 condition verdict, security prevalence, Cohen's κ or p-value is supported by this inventory alone.
