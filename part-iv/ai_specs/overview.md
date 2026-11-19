# Overview

> **OpenOwls SD-KDP** — Read by the advisor, the author and the agent.
> What this knowledge base is, why it exists, who it is for, and how it is built.
> **Status:** drafted by Claude and approved by the author, 14 Nov 2026.

---

## Project name

SDD Evidence Base — Part IV of *Evaluating and Extending Spec-Driven Development*.

## One-line description

A source-attributed wiki that answers an engineer's practical questions about spec-driven
development (SDD) from the research and practitioner literature, distilled in one declared voice:
the evidence-first software engineer (see `oracle.md`).

## Problem statement

Writing on SDD grew quickly after GitHub released Spec Kit in September 2025. It is scattered across
preprints, tool documentation, vendor blogs and practitioner essays, and much of it repeats the same
few claims without saying where they come from. An engineer deciding whether to adopt SDD cannot
easily tell what has been *measured*, what has been *observed* by practitioners, and what is only
*claimed*. This knowledge base sorts the literature along exactly that line.

## Goals

- **Answer the eight key questions** in `oracle.md` from distilled articles, every claim tagged with
  its source and its evidence class.
- **One article per trusted source**, in a fixed format (`output-format.md`), produced by an
  unattended pipeline from the specifications in this folder.
- **Reproducible and incremental:** re-running the pipeline on unchanged sources changes nothing;
  changing one source re-distils only that source (hash-based).
- **A fair structural comparison** with OpenKB built on the same corpus (report, Part IV).

## Non-goals

- Not a neutral survey. The Oracle's perspective is the product (SD-KDP's premise).
- Not a full systematic review: the corpus is bounded (15–20 sources), chosen for the key questions.
- No redistribution of third-party full texts. `raw/` is local and git-ignored; the wiki holds
  original summaries with short attributed quotes only.

## Audience

- The author and advisor (as the acceptance test of Part IV).
- An engineer deciding about SDD adoption (the Oracle's reader).

## Architecture at a glance

```
corpus/sources.csv ──collect.py──> raw/<id>.txt + state/manifest.json (sha256 per source)
                                        │ (only new or changed hashes)
                                        ▼
ai_specs/*.md ─────────────distill.py──> wiki/sources/<id>.md ──voice check──┐
                                        │                                    │ fail -> fix the SPEC, re-run
                                        ▼                                    │
                              synthesize.py ──> wiki/questions/Q1..Q8.md, wiki/faq.md, wiki/index.md
                                        │
                                        ▼
                              index.py ──> state/index (TF-IDF vectors) ; query.py answers questions
                                        │
                                        ▼
                              backup: git commit of wiki/ + dated tarball in backups/
```

## Technology

Python 3.13 standard library plus `scikit-learn` (index). The LLM is called through a single
function in `scripts/llm.py`, so the model is set in one place and recorded in every article's
front matter. Model choice and API access: see `batch-process.md`.

## Stakeholders

| Role | Who |
| --- | --- |
| Author, Oracle owner | Varshil Patel |
| Advisor | Alex Pang |
| Drafting and pipeline code | Claude (disclosed in the report) |
