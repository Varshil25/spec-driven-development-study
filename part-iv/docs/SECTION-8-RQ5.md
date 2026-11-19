# Section 8.1 and RQ5 — evidence-controlled draft
**Status: preliminary; updated 2026-11-19.** This document is a report-ready account of what is documented and what remains to be demonstrated. Do not interpret a proposed pipeline or an unexecuted test as an empirical result.

## 8.1 OpenOwls SD-KDP Implementation

Part IV investigates whether specification-driven methods can govern the production of a queryable knowledge base about spec-driven development (SDD), rather than executable software. The chosen Oracle is an *evidence-first software engineer*: a reviewer who regards claims about SDD as hypotheses requiring appropriately scoped support. Its evidence taxonomy distinguishes measured, reported case, observed, documented, claimed, and argued material. The Oracle rejects sponsored advocacy represented as independent evidence, unattributed copies, and unverifiable AI-hosted commentary. Its eight acceptance questions cover SDD definitions and tooling, functional correctness, security, cost, existing-codebase changes, traceability, practitioner criticisms, and remaining uncertainties.

The supplied final-report draft records the original study's planned 17-source corpus (seven papers, four sets of documentation or announcements, and six practitioner analyses), seven governing specifications, and an initial offline test record of 18 passing tests. It also reports an S08 collection check in which a second collection of the Spec Kit methodology source detected no change and forwarded no content to distillation. **Those historical statements are attributed to the report draft, not independently reproduced in this new repository branch.** The full source inventory and source files are not yet present in the new branch, and its initial tests have not yet been run in a recorded environment.

Following the provided OpenOwls *Learning From Your Oracle* guide, the new `part-iv/` branch contains `CLAUDE.md`, `progress.md`, and seven underscore-named specifications: `overview.md`, `domain_knowledge.md`, `oracle.md`, `collection_techniques.md`, `distillation_techniques.md`, `output_format.md`, and `batch_process.md`. The four-stage implementation is organized as collect → distill → index → backup. The collector accepts manually reviewed UTF-8 local files listed in `sources.json`, records SHA-256 hashes, and avoids recopies when content is unchanged. The distiller currently writes *extractive, attributed baseline snippets*, not model-generated or Oracle-voice-validated articles. The local index currently uses token frequencies rather than a semantic vector embedding store. Backups snapshot `kdb/` and `wiki/` and retain 14 copies by default. The orchestrator attempts backup even when earlier stages report failure and records run outcomes.

This implementation is a reproducible scaffold, not yet a validated full-corpus result. The absence of sources in the branch's initial manifest means that a successful empty-corpus run would demonstrate only basic orchestration. The 17-source collection, actual article quality, one-source voice review, two-stage incremental distillation check, overnight schedule, and eight-question retrieval evaluation must be measured before claiming successful knowledge-base production.

## 8.2 Structural comparison against OpenKB

| Dimension | OpenOwls SD-KDP | OpenKB | Current evidence |
|---|---|---|---|
| Governing artifact | Seven explicit, version-controlled Markdown specs and Oracle | Lighter configuration and automated compilation (as described in study report) | Structural design, not effectiveness |
| Stance | Declared trusted/rejected sources and evidence-first Oracle | Broader cross-referenced synthesis | Design-level distinction |
| Workflow | Scheduled collect → distill → index → backup | Incremental init/add/query/chat workflow (report description) | No matched run |
| Retrieval | Target: searchable distilled wiki; current scaffold: token-frequency index | Report describes PageIndex vectorless reasoning retrieval | Not a quality comparison |
| Provenance | Source ID, URL, content hash, evidence class in article front matter | Requires output inspection on same corpus | No scored coverage |
| Observed result | Historical report: 18 offline tests, S08 unchanged collection; new scaffold: unexecuted | No OpenKB result recorded | **Comparison pending** |

The two approaches cannot be ranked empirically from their stated architectures alone. A fair test requires the same frozen corpus, comparable model settings, identical eight Oracle questions, version and cost logs, and a blinded citation-quality review where feasible. OpenKB's API/OAuth requirements may prevent a matched run using a Claude subscription alone; such a limitation must be disclosed rather than converted into a negative result.

### RQ5a — specification overhead versus traceability

The OpenOwls workflow requires seven human-authored specifications, creating a real *structural* setup obligation. Those files explicitly record the Oracle's exclusions, evidence taxonomy, collection rules, output schema and operating policy. This makes intended provenance requirements inspectable and reviewable in version control. **No measured authoring time, source-to-answer citation rate, or comparative consistency score is yet available.** The supported finding is that the governance burden and controls are explicit, not that they are faster or more accurate than OpenKB.

### RQ5b — effect of declaring an Oracle

The evidence-first Oracle is designed to distinguish tool descriptions from evidence of engineering outcomes and to label claims by evidentiary status. This is a testable editorial constraint rather than an established quality improvement. The new scaffold does not yet perform an LLM voice check. Consequently **it has not demonstrated that an Oracle produces more defensible answers than OpenKB**. A comparison should score unsupported assertions, evidence-class accuracy, attribution, contradiction handling, and Oracle consistency on identical questions.

### RQ5c — transfer of SDD principles beyond code

The architecture transfers three SDD principles to knowledge artifacts: explicit specifications precede production; artifacts have a prescribed format and acceptance criteria; and changes can be processed incrementally. The report's historical S08 unchanged-collection observation supports a narrow instance of incremental collection, but it does not establish full-corpus incremental distillation or question-answer quality. The present scaffold shows a concrete *implementation path* for knowledge-first SDD; generalizability and effectiveness remain unverified.

### Provisional answer to RQ5

**Yes at the level of design and prototype implementation:** the spec-first paradigm can be expressed as an Oracle-governed pipeline for producing a queryable knowledge artifact. **Not yet established at the level of validated comparative results:** the evidence does not currently show that it yields more accurate, more consistent, or more defensible answers than OpenKB, or that its up-front authoring overhead pays for itself.

## Completion criteria / data collection

1. Record the 17-source frozen inventory, verified URLs, license, evidence class and exclusions.
2. Run a single approved source; inspect article structure, citation spans and actual voice-review result.
3. Run the full corpus and record ingestion success/failure, accepted articles and question coverage.
4. Repeat without changes: record number re-distilled (target 0); modify exactly one approved source and rerun (target 1).
5. Run or explicitly document the blocker to OpenKB with the same corpus.
6. Score the eight questions using `EVALUATION-RUBRIC.md`, log setup time, model/cost, and link run artifacts.
7. Replace provisional text with actual observed results, without extrapolating beyond the sample.

**Primary bases:** user's `final-report.pdf` (Sections 3.3, 5.8 and 8) and uploaded OpenOwls *Learning From Your Oracle* guide (Sections 1–7); branch source files linked from PR #8. This document does not claim independent verification of the original report's 18 tests.
