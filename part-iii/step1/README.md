# Step 1 — R035C operator handoff

**Verified snapshot:** `week8-runs` commit `af12dfdd1ed1b44ef19f50918166e6d84c1834c0` has a completed R035 manifest, `logs/bundles/R035.bundle`, and no archived R035C. R035 passed all six frozen log-integrity checks.

R035C is the T-TARX-01 change request in the `sdd_clarify` condition. It **must** run in the original R035 clone, with `claude-opus-5`, Claude Code 2.1.317, Spec Kit 1.0.6, frozen answer sheets and the registered `--clean-env` setting. Do not run this experiment via GitHub Actions or ChatGPT as a replacement for the original Claude Code environment.

## Start in the original operator terminal

Make sure `$KIT` is the actual study-kit path, not a fresh checkout:

```bash
export KIT="$HOME/CPT-Peng/sdd-pilot"
python3 "$KIT/tools/study/start_r035c.py" --kit "$KIT" \
  --run-dir "$HOME/sdd-study/runs/R035" \
  --clean-env "$HOME/sdd-study/claude-configs"
```

The initial command only checks readiness. If it reports `ready`, run it again with `--execute` to launch the frozen runner. **If this new convenience script is not yet in your checkout**, you can launch the original unmodified runner directly:

```bash
cd "$HOME/sdd-study/runs/R035"
python3 "$KIT/tools/study/run_build.py" R035C \
  --kit "$KIT" --clean-env "$HOME/sdd-study/claude-configs"
```

The original operator must classify any questions using the frozen rules in `docs/RUNBOOK.md` and the answer sheets; no new model-generated answers. Keep the original clone and logs.

If the original R035 clone is missing, **do not start R035C on an empty clone**. Restore from the recorded R035 bundle only after checking the closure commit and all required state. A bundle does not preserve untracked state or agent session configuration; document any restoration in the study deviations log.

## After the run

Verify logs with the frozen `sddlog verify`, create the completed-run Git bundle, copy `logs/runs/R035C` and the bundle to the study repository, and update `schedule/run-log.md` according to RUNBOOK section 4. The next build is **R036**, in a fresh `base-v1` clone.

**Assistant access limitation:** This session has no Claude CLI, Spec Kit CLI or original `~/sdd-study/runs/R035` clone. Therefore it cannot execute R035C here, and no run result is being claimed. The new script is a preflight and operator handoff, not a completed experiment.
