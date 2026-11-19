# CLAUDE.md

> This knowledge base follows the **OpenOwls SD-KDP** (Spec-Driven Knowledge Distillation Process).
> Read the files below in order before doing any work.

## Session startup — read these first

1. `progress.md` — what is done, what is next, the latest batch run
2. `ai_specs/overview.md` — what this knowledge base is and how it is built
3. `ai_specs/oracle.md` — **whose view this is**: perspective, voice, trusted and rejected sources, key questions
4. `ai_specs/domain-knowledge.md` — terms, evidence classes, facts not to get wrong
5. `ai_specs/collection-techniques.md` — how sources come in
6. `ai_specs/distillation-techniques.md` — how a source becomes an article, and the voice check
7. `ai_specs/output-format.md` — the exact shape of every wiki page
8. `ai_specs/batch-process.md` — the unattended run, schedule and failure handling

## General instructions

- The Oracle's perspective is the product. Do not neutralise it.
- One article per source, from that source only. Synthesis happens on question pages.
- When an article is wrong, **change the spec, not the article**, and log the change in `progress.md`.
- Never commit anything under `raw/` (third-party full texts).
- Never edit or delete a file in `ai_specs/` without the author's approval.
