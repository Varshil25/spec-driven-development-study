# Part III CI execution evidence — November 19, 2026

## Executed verification
GitHub Actions workflow: [Part III evidence-only audit, run 44605961542](https://github.com/Varshil25/spec-driven-development-study/actions/runs/44605961542).
Source: the workflow job's actual execution log (`inspect`, job 135849580716). Overall result: **success**.

**Unit tests performed by CI:** 4 tests of preflight completeness + 5 tests of per-hook idle-gap correction + 3 tests of derived analysis-input preparation = **12 passed**. These tests exercise synthetic inputs and integrity safeguards; they do not verify scientific findings or the original frozen study tool suite.

**Read-only corpus preflight performed by CI:** 24 scheduled Python builds, 48 effective build/change cells, 33 archived metrics/event-log/manifest triplets and 15 absent. Missing outputs: 72 held-out score JSON files, 48 traceability coding sheets, 48 security sheets, and 48 principles sheets. Both decrypted held-out directories absent. Status: `incomplete`.

**Actual archived timing audit executed by CI:** `total_expected=48`, `computed=33`, `adjusted=16`, `review=[]`, `errors=[]`, `missing=15`. "Adjusted" means 16 runs contained one or more gaps over 600 seconds between hook-observed activity events. "review=[]" means the script detected no internal arithmetic inconsistency against the raw logged metric under its configured checks; it does **not** validate the gap rule against the pre-registered analysis protocol or a human interruption audit.

The generated audit results, original file SHA-256 hashes and the exact checked-out `week8-runs` revision were uploaded as a run artifact named `part-iii-read-only-audit` with a 30-day retention.

## Guardrails
- **No original logs changed.** CI checked out `week8-runs` read-only.
- **No sealed suite decrypted or executed.** No raw correctness/security results or statistical significance claims were produced.
- **Timing results are provisional** until review of the protocol's idle-gap correction, phase boundaries and explicit interruption notes.
- **R011C is excluded** and the effective replacement R019C is used in the presence audit. The original R011C audit trail remains intact.
- The frozen `tools/study/analyze.py` is unchanged. The new `prepare_analysis_view.py` explicitly stages corrected data and replacement naming in a derivative directory only when all inputs are present and hashed.

## Frozen sddlog integrity verification — subsequent CI run

[Part III evidence-only audit, run 44606610182](https://github.com/Varshil25/spec-driven-development-study/actions/runs/44606610182), job `inspect`, completed **successfully** on 2026-11-19. The new read-only `tools/study/verify_archived_runs.py` imported the **unchanged `tools/sddlog/sddlog.py` `verify_run`** function and checked all available effective run manifests and events.

| Check | CI output |
|---|---:|
| Effective scheduled cells | 48 |
| Present runs scanned | 33 |
| Runs passing all six log-integrity invariants | **33** |
| Runs failing integrity | **0** |
| Warning runs | **0** |
| Not archived | 15 |

The excluded `R011C` separately produced the **three expected** problems: duplicated sequence at position 234 (saw 233), mismatched clarify/plan phase boundary, and a phase end without a start at event 265. Its report also contains two timing warnings. `R011C` remains excluded, while replacement `R019C` is included in the 33 passes.

This evidence validates the **log-format and phase-integrity checks only**. Held-out scoring, confirmed security defects, traceability coding, costs and RQ1–RQ4 inferential results remain pending.
