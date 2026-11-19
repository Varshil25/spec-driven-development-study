# Part III report evidence ledger (RQ1–RQ4)

**Do not replace missing values with estimates.** Populate only after the prerequisite evidence has been examined and frozen analysis executed. Each row must link a reproducible artifact, script version, and run IDs.

| Report section | Data required | Analysis/report source | Status |
|---|---|---|---|
| 6.1 RQ1, correctness | All 24 build tier A and C scores; 24 CR tier A/C scores; 24 regressions | score JSONs, results.json, tested source bundles | Missing in public repo |
| 6.1 Security | Probe outcomes, Bandit, manually confirmed CWE/severity and dedup notes | security sheets, SAST logs | Missing in public repo |
| 6.2 RQ2, traceability | 245 register rows mapped into per-run coding; 30% recoding ≥5 days later; Cohen's κ | traceability sheets and recoding log | Missing in public repo |
| 6.3 RQ3, effort | Active time, human turns, input/output tokens, phase time, version drift, costs, interruptions | sddlog metrics and reconciled run logs | Missing in public repo |
| 6.4 RQ4 components | Tier B scores, clarification choices, post-plan revisions, constitution principles, CR spec edits | scored runs, snapshots, principle sheets | Missing in public repo |
| 6.5 Output determinism | Replicated REDACT runs R036/R023, R016/R022, R011/R021, R006/R039 | results.json and replication analysis | Missing in public repo |
| 7.1–7.5 validation | Held-out hashes, audit, scoring version, adjudication, coder reliability, reconciliation | sealed/README.md, prereg, audit logs | Pending |
| 9–12 discussion/conclusion | Results with deviations, limits and comparisons | validated Sections 6–7 | Pending |

**Special exclusions and deviations:** R011C excluded; use separately archived R019C replacement for that change-request cell; retain both audit trails. Java/Quarkus extension cancelled before execution, so exclude it from Python study denominators. Account interruptions and Claude Code version drift must be disclosed and analyzed as described in the final-report draft.

## Notes template per analysis result

- Measure / hypothesis:
- Conditions compared:
- Tasks included / exclusions:
- Raw run IDs and scoring file SHA-256:
- Exact analysis script commit:
- Direction, magnitude, consistency threshold:
- Statistical output (when applicable):
- Security/traceability adjudication:
- Research limitation:
- Report table/paragraph updated:
