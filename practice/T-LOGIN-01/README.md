# Practice comparison: T-LOGIN-01

One unstructured build (D001) and one SDD build (D002) of the same login task,
run to test the study procedure end to end. **Excluded from the study's data.**
Results and caveats are in [COMPARISON.md](COMPARISON.md) and in section 4 of
the [Weeks 5–9 report](../../docs/WEEKS-5-9-REPORT.md).

| Path | What it is |
| --- | --- |
| [COMPARISON.md](COMPARISON.md) | Setup, results, phase timings and caveats |
| [runs/D001/](runs/D001/) | The unstructured build as committed at the end of the run: code, the agent's tests, and the `sddlog` event log |
| [runs/D002/](runs/D002/) | The SDD build: code, tests, the Spec Kit documents in `specs/` and `.specify/memory/constitution.md`, and the event log |
| [bundles/](bundles/) | Both run repositories with their full git history, including Spec Kit's scaffolding (`git clone bundles/D002.bundle D002`) |
| [scores/](scores/) | `score_run.py` output for both builds, with Bandit |
| [heldout/](heldout/) | The 41-check held-out suite (stated, intent and security tiers). It was frozen before either agent ran; [FREEZE.txt](FREEZE.txt) records its tree hash |
| [reference/](reference/), [validation/](validation/) | The reference implementation and a naive variant, with their scores |

The task text, examples and answer sheet are in
[tasks/T-LOGIN-01/](../../tasks/T-LOGIN-01/) and
[operator/answer-sheets/T-LOGIN-01.md](../../operator/answer-sheets/T-LOGIN-01.md).
Unlike the five study tasks, this task's tests are public, so it cannot be
reused as a study task.

Rescore a build (needs pytest; Bandit for `--sast`):

```bash
python3 tools/study/score_run.py --task T-LOGIN-01 \
    --repo practice/T-LOGIN-01/runs/D002 \
    --heldout practice/T-LOGIN-01/heldout --sast
```
