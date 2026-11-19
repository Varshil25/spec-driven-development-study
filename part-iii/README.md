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


## Verified CI execution and derived analysis inputs

GitHub Actions [read-only audit](https://github.com/Varshil25/spec-driven-development-study/actions/runs/44605961542) completed successfully on 19 November 2026: **12 synthetic-fixture utility tests passed**; **33 of 48** effective archived study cells found; **16 archived runs** had at least one hook-observed idle gap longer than 600 seconds; no arithmetic inconsistency was flagged by the correction script. Full results and limitations are documented in [CI execution evidence](audits/2026-11-19-ci-execution-evidence.md). A [preliminary per-run CSV](audits/2026-11-19-preliminary-idle-gap-candidates.csv) is available for review, **not** as final RQ3 data.

Run the actual timing audit from a local checkout containing the `week8-runs` evidence:

```bash
python3 tools/study/recompute_idle_time.py \
  --runs-root /tmp/sdd-week8-runs/logs/runs \
  --csv-out /tmp/part-iii-idle-verified.csv
```

Once all 48 runs, 72 scores and human coding sheets are complete, build a separate audit-traceable input directory for the **unchanged frozen analyzer**:

```bash
python3 tools/study/prepare_analysis_view.py \
  --runs-root /tmp/sdd-week8-runs/logs/runs \
  --scores /path/to/scores \
  --coding /path/to/coding/runs \
  --time-csv /tmp/part-iii-idle-verified.csv \
  --out /tmp/part-iii-analysis-view
python3 tools/study/analyze.py \
  --scores /tmp/part-iii-analysis-view/scores \
  --runs /tmp/part-iii-analysis-view/runs \
  --coding /tmp/part-iii-analysis-view/coding \
  --out /tmp/part-iii-results
```

The preparation script refuses incomplete or stale data, saves provenance hashes, maps excluded `R011C` to replacement `R019C` within derived filenames only, and never rewrites source evidence. **Review the correction against the original interruption notes and preregistration before using it for inferential analysis.**

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
