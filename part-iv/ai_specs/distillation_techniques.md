# Distillation techniques
**Audience: Engineer + distill.py**

Production goal: source-faithful, Oracle-voiced, citation-bearing article per changed source; model review against Oracle and deterministic quality checks; no outside facts or invented examples. On repeated failure, revise the spec rather than editing wiki output.

**Baseline implementation (not production-complete):** deterministic extractive snippets, source tags and evidence classes, limited to 3 source sentences per document. It cannot assert Oracle voice compliance or synthesize across documents. Only changed source hashes are redistilled, unless `--force` or a governing-spec hash changes. Preserve original text separately, do not copy long passages into distributable wiki without rights review. Model provider, voice reviewer, synthesis, quote licensing and cost controls remain TODOs.
