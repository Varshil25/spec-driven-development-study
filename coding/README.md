# Coding materials (Part III)

| File | What it is |
| --- | --- |
| `requirements.csv` | Every requirement of every task, each with the held-out tests that check it. Python tasks: 60 stated, 16 intent and 21 security rows. Java tasks (added in Week 7): 42 stated, 8 intent and 14 security rows. IDs (S1, I2, C3, ...) match the test names. |
| `runs/` | Created by `tools/study/make_coding_sheets.py`: one traceability sheet, one security sheet and one constitution-principles sheet per scored run. |

The coding rules (traceability scores 0/1/2, the explicit-link flag, the
security severity rubric, the manual-review checklist and the principle checks) are in
`docs/PREREGISTRATION.md`, section 7. Code every run of one task in a single
sitting, in the order drawn with seed 20261023. Re-code a random 30% of
traceability rows at least 5 days later, without the first codes, for Cohen's κ
(section 7.3).
