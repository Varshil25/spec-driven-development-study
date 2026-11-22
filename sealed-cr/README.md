# Sealed held-out suite for the change requests, v1

**Do not open before all study runs (R002–R018 and R034–R038, and R021–R023
and R039 if run) are finished.** The hashes in section 11 of
`PREREGISTRATION.md` identify this exact version. Check them before scoring:

```bash
python3 <kit>/tools/study/score_run.py --hash-only --heldout sealed-cr/heldout
```

| Path | What it is |
| --- | --- |
| `heldout/` | Black-box pytest suites for the five change requests (`T-<task>-01-CR/`), three tiers each: `test_stated.py` (tier A), `test_intent.py` (tier B), `test_security.py` (tier C), plus shared harness files and helper modules. 107 test cases |
| `reference/` | Reference implementation of each change request: the original task's reference with the change made. It passes every test |
| `validation/naive/` | Naive implementations: the reference with the change made the way a plausible first draft would make it |
| `validation/alternatives/` | Independent implementations from the review, with switches for other defensible readings (`validation/VALIDATION.md`, section 3) |
| `validation/scores/` | `score_run.py` output for every reference and naive implementation, on this suite (with Bandit) and on the build suite (regression) |
| `validation/VALIDATION.md` | What was checked before freezing, what it showed, and what was fixed |

Score a change request (Part III). The run's repository is the build's
repository after the change request has closed:

```bash
python3.13 <kit>/tools/study/score_run.py --task T-TARX-01-CR --repo <run dir> \
    --run-id R005C --heldout sealed-cr/heldout --sast --out scores/R005C.json
python3.13 <kit>/tools/study/score_run.py --task T-TARX-01 --repo <run dir> \
    --run-id R005C-regression --heldout sealed/heldout --out scores/R005C-regression.json
```

Regression is the second command's tiers A and C only (`VALIDATION.md`,
section 2.2).
