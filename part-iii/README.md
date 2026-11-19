# Part III — software SDD study analysis and validation

**Status: partially archived study-run evidence is available on the separate `week8-runs` branch; full collection and sealed-suite access remain incomplete. This does not indicate failed experiments.**

This directory adds an *analysis preflight*, without editing the frozen pre-registration, frozen analysis program, encrypted suites or existing run logs.

## Verified from the repository inventory (2026-11-19)

- Python study schedule: **24 builds** (20 task×condition cells and 4 replicated builds) plus **24 change requests** = **48 expected run artifacts**.
- Expected post-unseal scoring files: **72** (one score per build, one change-request score and one regression score per change request).
- Expected initial coding sheets: **144** (traceability, security, principles per effective run). Human adjudication and a five-day later re-coding remain separate requirements.
- **245 requirement register rows** were present in `coding/requirements.csv`.
- Only the pilot/mechanics log directories **R001**, **R002**, and **R003** were visible at `logs/runs/` in the remote repository at audit time. None is a scored Python study run.
- No `scores/Rxxx*.json` for the Python study and no `coding/runs/` study sheets were present in the reviewed Git tree.
- Python held-out build and change-request suites remain encrypted in the repository. This preflight never decrypts them.
- The report (dated as of 14 November for its partial run count) *states* that 16 runs had closed, one of which (R011C) was excluded; those newer run archives have **not** been independently inspected in this GitHub snapshot.
- Java extension was dropped before any Java study runs; it is excluded from the 48-run denominator.

## Additional archive discovery\n\nThe \`week8-runs\` branch contains **33 of the 48 effective Python study cells** with log, manifest and metrics files, plus the excluded R011C audit trail. The remaining 15 effective cells have no archived files in the inspected branch snapshot. Details: [supplemental week8-runs audit](audits/2026-11-19-week8-runs-inventory.md). The main-branch inventory below does **not** represent all branches.\n\n## Run now (read-only)

From the repository root:

```bash
python3 -m unittest discover -s tools/study/tests -p test_part_iii_preflight.py -v
python3 tools/study/preflight_part_iii.py --json-out part-iii/audits/local-preflight.json
```

If the run clones still live outside the repository (as in the runbook), supply their directory:

```bash
python3 tools/study/preflight_part_iii.py \
  --runs-root "$HOME/sdd-study/runs" \
  --scores scores \
  --coding coding/runs \
  --json-out part-iii/audits/local-preflight.json --strict
```

A nonzero `--strict` status means **evidence missing**, not a poor research outcome. A status of `files_present_unverified_hashes` means required file *paths* exist; it is **not** a passing validation verdict.

## Gate sequence

1. **Complete data collection first.** Archive R004–R039C including run-specific logs and final code bundles; preserve the excluded R011C and its replacement R019C. Check the run log and verify each run's event-log integrity.
2. **Unseal only after R039C is finished and exclusion decisions are frozen.** Follow `sealed/README.md` with the author's private passphrase. Compare archive SHA-256 and the frozen suite tree hashes against `docs/PREREGISTRATION.md`. Do not publish any passphrase.
3. **Score every build, change, and original-suite regression.** Use the existing frozen `tools/study/score_run.py` (do not change scoring behavior after viewing results); retain machine-readable per-test outcomes, SAST output, and run IDs.
4. **Generate human coding sheets** using `tools/study/make_coding_sheets.py`. Confirm security findings manually with CWE/severity, and code traceability evidence and principles. Recode 30% after at least five days and compute Cohen's κ.
5. **Reconcile effort metrics** against transcript/hook logs, interrupted-run idle-gap corrections, exclusion notes, and recorded Claude Code versions.
6. **Apply the frozen analysis script** `tools/study/analyze.py` only after complete scoring and coding data; report consistency rules, exact tests, effect sizes, complexity correlations and replication variation as preregistered.
7. **Update report Sections 6, 7 and 9–12** only with independently checked outcomes and exact artifact references. Leave all placeholders empty where verification is incomplete.

## Reproducibility and ethics

The public repository does not substitute for missing external cloud-workspace run clones. Keep sealed suites sealed until the freeze condition is met, do not modify frozen instruments to force a desired result, and do not write synthetic or estimated data into the final research tables. The study's own docs and runbook are the authority for scoring, adjudication and statistical analysis.
