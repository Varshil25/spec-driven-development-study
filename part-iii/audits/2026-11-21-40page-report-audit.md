# PDF results verification snapshot (2026-11-21)

Source report: uploaded `final-report (1).pdf`, dated 20 Nov 2026, 40 pages. The PDF contains 266 literal `[EMPTY]` placeholders, 25 `[TO FILL:...]` directives and four validation-not-completed notices. Earlier interim PDF fills only three Table 11 active-time deltas.

Inspected immutable evidence snapshot: [week8-runs@c668278](https://github.com/Varshil25/spec-driven-development-study/tree/c668278a97ff3c039ca037269339799352679a00). **46 of 48** effective Python study run folders have `manifest.json`, `events.jsonl` and `metrics.json`; only **R039** and **R039C** remain missing. Original **R011C** remains excluded, replaced by **R019C**. No 72 expected scoring JSONs, unsealed Python suites, or completed human coding results are present in this branch.

## PDF placeholder ownership

| Output | Placeholders | Required work |
|---|---:|---|
| Table 7 | 100 | 20 scored build repositories; 20 manually reviewed security sheets |
| Table 8 | 80 | 20 scored change requests + 20 regressions; 20 reviewed change-request security sheets |
| Table 9 | 60 | 20 completed traceability coding sheets |
| Table 11 | 12 | 8 hidden-score deltas + 4 time deltas; 3 time deltas computed from log hooks, R039 delta pending |
| Table 12 | 9 | Results-level scientific validation checks |
| Table 13 | 2 | SD-KDP/OpenKB actual observed outcomes |
| Appendix A | 3 | Real unseal date, hash checks and audit location |
| **Total** | **266** | Score, human-code, compare, audit |

25 narrative `[TO FILL]` directives and four validation notices are **in addition** to the 266 cells.

## Table 10 discrepancy audit

The PDF already prints 20 build-time values. A preliminary event-based recomputation following the stated rule (drop complete inter-hook idle intervals **over** 600s) gave different rounded active times for ten archived run IDs:

| Run | PDF (min) | Hook-derived candidate (min) | Difference PDF − candidate |
|---|---:|---:|---:|
| R006 | 63.0 | 62.4 | +0.6 |
| R007 | 56.4 | 55.8 | +0.6 |
| R009 | 42.0 | 41.2 | +0.8 |
| R010 | 44.4 | 43.6 | +0.8 |
| R011 | 50.4 | 49.6 | +0.8 |
| R016 | 40.7 | 40.1 | +0.6 |
| R018 | 36.5 | 35.8 | +0.7 |
| R035 | 43.7 | 42.9 | +0.8 |
| R037 | 67.9 | 67.5 | +0.4 |
| R038 | 37.7 | 37.1 | +0.6 |

These are **candidate reconciliations**, not authority to silently overwrite the report: inspect the frozen active-time definition, all versioned phase marker/hook events and the existing report calculations before editing. R037 is especially straightforward because its archived raw `metrics.json` also says ~67.5 min and there were no >600s gaps. Human-turn fields matched all 20 printed build rows; token fields were consistent to approximate report precision.

## Other scientific issues to resolve

1. **Report §5.8** currently states the full six-step KB workflow and OpenKB comparison in past tense, yet §8 has no full-corpus run or OpenKB results. Change claims to implementation/design unless direct run artifacts are found.
2. **OpenOwls format mismatch:** the author-supplied *Learning From Your Oracle* guide uses `ai_specs/domain_knowledge.md` with underscores; current `part-iv/CLAUDE.md` and its active `scripts/` pipeline refer to hyphenated names. Both file sets exist. Choose/document one canonical OpenOwls implementation before declaring conformance.
3. **Abstract and §13** refer to final scoring/all-run availability as accomplished, but 2 runs and 72 scores are still missing as of this snapshot. Update tense until final validation.
4. **Table 10** cannot be called validated until the discrepancy is explained; do not compute final RQ3 P4 verdicts on inconsistent inputs.
5. **Appendix [16]** lacks the exact OpenOwls guide bibliographic entry. The author's pasted guide has the title `Learning From Your Oracle`. Confirm publisher, canonical guide URL and access date rather than invent a deep link.
6. **R011C → R019C**: the unchanged preregistered analyzer assumes nominal `R011C` filenames; use a provenance-logged derived view to map the valid replacement without changing raw evidence.
7. **Manual coding** is required to interpret failures: Bandit and failing security probes are candidates, not automatically confirmed CWE defects.
8. **RQ5 and discussion/conclusion** must remain qualified until actual KB corpus, voice checks, eight QAs and fair/explicitly-blocked OpenKB comparison are documented.

## Ordered completion gates

1. Run R039 then R039C in the original frozen Claude Code operator environment. Archive run logs, final code git bundles, and inspect manual decisions.
2. Independently verify **all 48** effective logs with the unchanged `sddlog` six-check validator. Preserve excluded R011C.
3. **After** R039C and exclusion freeze, locally decrypt both held-out Python suites using author-held private passphrases and check pre-registered ZIP and tree SHA-256. Never use chat/CI to handle passphrases.
4. Run `score_run.py` on **24 build-closing commits, 24 change-closing commits, and 24 original-suite regressions**, producing 72 machine-readable score files with complete tests/SAST outputs.
5. Generate 48 each of security/traceability/principles sheets, human-adjudicate all 40 original-task security sheets, code main-condition traceability/constitution, then repeat 30% traceability scores ≥5 days later and calculate the registered weighted Cohen's kappa.
6. Reconcile Table 10 and all interrupted durations; map R019C as a derived nominal R011C and run unchanged `tools/study/analyze.py`, checking outputs under frozen thresholds.
7. Run one-source SD-KDP trial and full 17-source corpus, verify Oracle voice, eight question pages, incremental hashes and index; compare to OpenKB using a comparable corpus/model or explicitly document a blocked evaluation.
8. Populate the 266-cell mapping with provenance to each score, coded sheet or audit, fill the other 25 narrative directives, remove the four warnings **only after** completing each affected validation, recompile LaTeX and visually verify all 40 pages.

**Status:** no fabricated results and no encryption changes. The 46 archived logs' file presence is verified; the latest CI run on this draft PR is expected to rerun the frozen verifier against this updated snapshot (record that run separately after it finishes).

## Independently executed checks completed 2026-11-21

- **Part III read-only CI**: [run 44928326363](https://github.com/Varshil25/spec-driven-development-study/actions/runs/44928326363) completed successfully: **46/46 archived effective logs passed all six frozen sddlog invariants**, 27 synthetic fixture utility tests passed, **two runs (R039, R039C) remain missing**, scoring gate correctly **closed**.
- **Part IV offline CI**: [run 44928583255](https://github.com/Varshil25/spec-driven-development-study/actions/runs/44928583255) completed successfully after installing the missing test dependency `scikit-learn==1.7.2`. **18/18 active-pipeline tests and 4/4 separate extractive-baseline tests passed**, corpus list contains **17 trusted + 3 rejected entries**. The earlier attempt [run 44928427622](https://github.com/Varshil25/spec-driven-development-study/actions/runs/44928427622) had one `ModuleNotFoundError: sklearn` and 17 other tests passing, establishing a dependency declaration gap rather than proven algorithmic failure.
- **Release caution**: These pass results establish offline code functionality and log structure only. They cannot validate paper quality, all 17-source collection, LLM Oracle voice, actual OpenKB comparison, hidden-test security or requirement traceability.
- **Layout QA**: PDF page 35 Table 14 text overflow was reproduced visually and by page-span coordinates (rightmost span ends at x=613.2pt on a 612.0pt-wide page). Re-typesetting required.
