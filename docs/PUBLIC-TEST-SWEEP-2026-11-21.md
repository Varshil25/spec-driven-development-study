# Public test sweep — 2026-11-21

**Workflow:** https://github.com/Varshil25/spec-driven-development-study/actions/runs/44930674082

**Tested commit:** `f98c6ba56716c1b193b3b6f3c9c5ef6cc20edfda` on `execution/part-iii-finish`.

| Suite | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Main expense-splitter application | 58 | 0 | 0 |
| Study logging, run builder and frozen analyzer | 143 | 0 | 0 |
| Part IV knowledge-base pipeline and baseline | 22 | 0 | 0 |
| Practice T-LOGIN-01 D001 internal | 133 | 0 | 0 |
| Practice T-LOGIN-01 D002 internal | 242 | 0 | 1 |
| Public practice held-out vs D001 | 38 | 3 | 0 |
| Public practice held-out vs D002 | 39 | 2 | 0 |
| **Total** | **675** | **5** | **1** |

Python 3.13.18, pytest 9.1.1, scikit-learn 1.7.2. All JUnit XML outputs are attached to the workflow as seven downloadable artifacts.

**Practice-suite failures:**
- D001: `test_i1_lockout_after_five_failures`, `test_i3_usernames_case_insensitive`, `test_i4_login_page_redirects_when_logged_in`.
- D002: `test_i3_usernames_case_insensitive`, `test_i4_login_page_redirects_when_logged_in`.
- D002 skipped an environment-specific Python 3.11 smoke test; this workflow uses pinned Python 3.13.

All five failures belong to the **public practice login project**, not the 48 controlled SDD Python runs. The earlier first sweep's practice held-out job failed due to a missing `SUT_REPO` variable. The corrected run above provides the actual D001/D002 comparisons.

**Local report evidence validator:** 8/8 tests passed, independently evaluating 266 report cells: 3 supported values and 263 pending.

**Research boundary:** The 27 separate Part III CI utility checks are a subset of the 143 tool tests counted above; do not double-count them. The KB CI's 22 are the same tests counted above. The latest `week8-runs` evidence snapshot has 46 of 48 effective archived runs; `R039` and `R039C` remain missing. The **sealed real study held-out tests were not decrypted or scored**, so this public sweep cannot fill the report's 263 unsupported cells. Do not present the public practice held-out results as study evidence.

The test sweep changes no frozen analysis code, no encrypted archive, and no original run log.
