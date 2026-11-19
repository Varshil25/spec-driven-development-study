# Supplemental Part III inventory: week8-runs branch — 2026-11-19

**Inspected:** `week8-runs` at commit `af12dfdd1ed1b44ef19f50918166e6d84c1834c0` (last commit 2026-11-19 19:47:26 UTC). Source: GitHub's recursive tree, schedule and selected run manifests/metrics; no sealed suite was decrypted.

This **corrects the apparent evidence-access gap on main**. The study-run archives do exist on a separate branch, so claims that they are unavailable across the whole repository are incorrect. The earlier audit for `main` remains accurate *for main only*.

| Measure | Verified on week8-runs |
|---|---:|
| Scheduled Python study cells (includes replication and CR) | 48 |
| Effective study cells with manifest, metrics.json, and events.jsonl files | **33** |
| Effective cells without those archived files | **15** |
| Extra excluded archive | **R011C** (retained, not scored; replacement R019C present) |
| Non-study archives | R001 (pilot), R002 and R003 (mechanics) |
| All visible run directories including excluded and non-study | 37 |
| Study score JSON files on this branch | 0 |
| Decrypted Python held-out suites on this branch | none |

**Available effective cells:** R004, R004C, R005, R005C, R006, R006C, R007, R007C, R008, R008C, R009, R009C, R010, R010C, R011, R019C, R012, R012C, R013, R013C, R014, R014C, R015, R015C, R016, R016C, R017, R017C, R018, R018C, R034, R034C, R035.

**Not yet archived:** R035C, R036, R036C, R037, R037C, R038, R038C, R021, R021C, R022, R022C, R023, R023C, R039, R039C.

The R035 manifest reports `status: completed`, with `ended_at=2026-11-19T19:47:00.153Z`. Its run-log entry records a weekly usage-limit interruption; **the raw `totals.active_seconds` in its metrics includes that multi-day delay and is not a valid adjusted active-time observation**. The report already specifies a correction for idle gaps above ten minutes. It must be applied consistently with the preregistered method rather than treating raw time as actual labor.

### What was and was not verified

- **File-level evidence:** path presence was verified for all 33 effective cells' manifests, event logs and metrics. Selected manifest fields and metrics were inspected, including R019C and R035.
- **Independent integrity verification:** not run. Presence alone does not mean all six run-integrity checks pass; the run log states 'OK' for archived effective cells but these verdicts must be regenerated from the event data.
- **Correctness/security scoring:** not run because held-out suites remain sealed and study collection is incomplete.
- **Coding and inference:** no traceability sheets, manually confirmed security findings, Cohen's κ, or frozen `analyze.py` outputs were verified on this branch.

### Next read-only check against a local checkout of week8-runs

```bash
git worktree add /tmp/sdd-week8-runs week8-runs
python3 tools/study/preflight_part_iii.py \
  --runs-root /tmp/sdd-week8-runs/logs \
  --scores scores --coding coding/runs \
  --json-out part-iii/audits/local-preflight.json
```

Do not merge run artifacts or unseal test archives while runs remain in progress. The latest source snapshot remains incomplete as of 19 November 2026.
