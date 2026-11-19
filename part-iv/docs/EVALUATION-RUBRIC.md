# RQ5 matched-corpus evaluation protocol

## Freeze before comparison
Record corpus manifest commit/hash, source license and date, model/provider/version, tool versions, prompts/configuration, machine environment, start/end timestamps, input/output token counts where available, API costs, and failed ingestions. Do not change sources or scoring criteria after seeing results.

## Questions
Use the eight numbered acceptance questions in `ai_specs/oracle.md` verbatim. Save raw answers and retrieval traces for both SD-KDP and OpenKB; reviewers should not know which system generated which answer where practical.

## Scoring per answer
Score each item 0, 1, or 2:
- **Question coverage:** 0 absent; 1 partial; 2 directly addresses all parts.
- **Citation support:** 0 no verifiable citation or unsupported; 1 some claims supported; 2 all material factual claims trace to verified sources.
- **Evidence classification:** 0 absent/incorrect; 1 mixed; 2 appropriately distinguishes measured, case, observed, documented, claimed and argued.
- **Uncertainty and causal scope:** 0 overstates evidence; 1 partly qualified; 2 matches evidence and states limitations.
- **Contradictions:** 0 suppresses relevant contrary evidence; 1 mentions without context; 2 fairly and accurately characterizes disagreements.
- **Oracle adherence:** 0 unlabelled generic or promotional claims; 1 inconsistent; 2 clear evidence-first lens labelled as perspective.

Total per question: 0–12; maximum per system across eight questions: 96. Record citations and rationale for every score. Do not claim a significant difference from eight non-independent questions without an appropriate analysis plan.

## Observation table
| Question | System | Coverage | Citations | Evidence class | Uncertainty | Contradictions | Oracle | Total | Notes / trace |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Q1 | SD-KDP | | | | | | | | |
| Q1 | OpenKB | | | | | | | | |
| Q2–Q8 | Both | | | | | | | | |

## Incremental and effort record
| Experiment | Expected check | Observed | Run-log path |
|---|---|---|---|
| One-source first run | 1 accepted source/article | Pending | |
| Unchanged rerun | 0 redistilled | Pending | |
| One source modified | 1 redistilled | Pending | |
| Full corpus | Record accepted/failed counts | Pending | |
| OpenKB matched run | Record outputs and errors | Pending | |

Track setup minutes for specs and OpenKB separately; record all manual corrections and retries. Distinguish model-access limitations from software defects.
