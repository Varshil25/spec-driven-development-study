# Part III — finish the registered software study

**Status at inspected revision:** `week8-runs@3a585ea9914d519a8ffdf1cc255f263aa6368cff` (2026-11-19 20:50 UTC) contains **35 of 48** effective Python study run archives. The latest completed run is **R036**. `R011C` was excluded; its replacement `R019C` is preserved and included in the valid 48-cell count. The original run log reports R036 passed integrity and its bundle exists.

## Remaining sequence

| Order | Run ID | Task | Condition | Clone |
|---:|---|---|---|---|
| 1 | R036C | T-REDACT-01-CR | unstructured | **Existing** R036 |
| 2 | R037 | T-PASTE-01 | sdd | New clone from frozen base-v1 |
| 3 | R037C | T-PASTE-01-CR | sdd | **Existing** R037 |
| 4 | R038 | T-BOOKMARKS-01 | sdd_secure | New clone from frozen base-v1 |
| 5 | R038C | T-BOOKMARKS-01-CR | sdd_secure | **Existing** R038 |
| 6 | R021 | T-REDACT-01 | sdd_clarify | New clone from frozen base-v1 |
| 7 | R021C | T-REDACT-01-CR | sdd_clarify | **Existing** R021 |
| 8 | R022 | T-REDACT-01 | sdd | New clone from frozen base-v1 |
| 9 | R022C | T-REDACT-01-CR | sdd | **Existing** R022 |
| 10 | R023 | T-REDACT-01 | unstructured | New clone from frozen base-v1 |
| 11 | R023C | T-REDACT-01-CR | unstructured | **Existing** R023 |
| 12 | R039 | T-REDACT-01 | sdd_secure | New clone from frozen base-v1 |
| 13 | R039C | T-REDACT-01-CR | sdd_secure | **Existing** R039 |

This sequence is taken from the frozen `schedule/schedule.csv`. R039C is the last study run. None of these 13 were counted as complete in the snapshot above.

## Launch only in the original Claude Code operator environment

The registered experiment uses `claude-opus-5`, Claude Code **2.1.317**, Spec Kit **1.0.6**, Python **3.13**, clean run-specific Claude config folders, and fixed prompt/answer/stop rules. Do not replace the model with ChatGPT or run in GitHub Actions; doing so would introduce an unregistered experimental condition.

In the original environment where `$KIT` is the current **`week8-runs` study checkout**, and `$HOME/sdd-study/runs/R036` contains the original completed clone:

```bash
# Set KIT to the path of the original, up-to-date study checkout.
export KIT="$HOME/CPT-Peng/sdd-pilot"

# First, read-only inspection:
python3 "$KIT/tools/study/run_remaining_part_iii.py" \
  --kit "$KIT"

# Only when all preconditions are satisfied and with a human operator present:
python3 "$KIT/tools/study/run_remaining_part_iii.py" \
  --kit "$KIT" --execute

# Optional: continue the remaining sequence, pausing for any operator
# classifications required by the frozen runner and STOPPING on any failure:
python3 "$KIT/tools/study/run_remaining_part_iii.py" \
  --kit "$KIT" --execute --all
```

This wrapper delegates to **unchanged** `tools/study/run_build.py`, never supplies synthetic answers, and never unseals tests. **With `--all`, it stops after each verified archive until the operator reviews the run log, commits/pushes the archived evidence, and types `NEXT`. Any integrity WARN or FAIL stops automatic progression.** It verifies the completed run with the frozen `sddlog` verifier before copying logs and refreshing the base run's Git bundle. Before starting it also checks the required tool versions, clean worktree, original completed build, and absence of an existing attempt. It is not a service or background runner: the original operator must remain present to classify questions and handle any interruption.

**Important:** The wrapper will refuse execution from a checkout that does not already contain the 35 valid archives through R036, or whose `logs/runs` folder is not the latest. The handoff path must be merged into that existing study checkout; do not replace or reset the study checkout to import it. The wrapper requires the same `--clean-env` conventions used for the preceding runs.

After each run, review the output, update `schedule/run-log.md` with the actual prompt/answer/cost notes, commit and push the new logs and bundle back to `week8-runs`. Do not change previous run statuses or invent observed metrics.

## Gates after R039C

1. Check all 48 effective archive triplets and their six `sddlog` integrity invariants. Keep the excluded `R011C` and replacement `R019C` audit trail.
2. Only **after** the last study run has completed and exclusion decisions are frozen, unseal both Python held-out suites using the **author's private passphrases**, which must never be pasted into a chat, committed to GitHub, or printed in CI.
3. Verify the decrypted archive SHA-256 and suite tree hashes against `sealed/README.md` and preregistration before scoring.
4. Score **24 builds, 24 change requests and 24 regressions**, retain 72 score JSONs, and run Bandit 1.9.4 plus manual security adjudication.
5. Complete traceability and constitution coding, repeat a seeded 30% sample at least five days later, compute weighted Cohen's κ, and reconcile model usage and interrupted-run timing.
6. Use the already created `recompute_idle_time.py` and `prepare_analysis_view.py` to create a provenance-logged copy of the **complete** dataset. The frozen `analyze.py` then produces the per-task comparisons and exact tests. **Do not generate or claim RQ1–RQ4 outcomes before these gates are satisfied.**

## Evidence already verified by GitHub Actions

The earlier 33-run audit passed all six integrity invariants on 33 available runs. A refreshed CI audit on this PR reads the current `week8-runs` branch to include R035C and R036; its generated queue JSON and six-check results are exported as workflow artifacts. **These checks never run Claude.**

## Blocker for assistant-only execution

The connected GitHub app can inspect/edit repositories and trigger CI via pull requests, but it does not expose the original Anthropic cloud workspace. The available container has neither `claude` nor `specify` executable nor the original run clones. Running a different model, supplying guessed operator answers, or bypassing pre-registered execution controls would invalidate the comparison. Thus the queue is prepared and tested but the remaining 13 controlled study sessions cannot be declared completed here.
