# Distillation Techniques

> **OpenOwls SD-KDP** — Read by the distillation agent before every run.
> How a source becomes an article in the Oracle's voice, and how drift from that voice is caught.

---

## Inputs to every distillation call

1. `ai_specs/oracle.md` (perspective, voice, tiers, key questions)
2. `ai_specs/domain-knowledge.md` (terms, evidence classes, facts not to get wrong)
3. `ai_specs/output-format.md` (the article template)
4. The source's row from `corpus/sources.csv` (tier, evidence type, why it is in)
5. The source's extracted text from `raw/<id>.txt`

Nothing else. In particular, no other source's text: one article describes one source. Cross-source
synthesis happens later, in `synthesize.py`, from the articles.

## Steps per source

1. **Read for what the source actually did.** Identify its design (RCT, case study, hands-on trial,
   documentation, opinion), its sample or scope, and what it measured.
2. **Separate the layers.** Sort every candidate statement into: documented behaviour, measured
   result, reported case, practitioner observation, claim without method, argument. A statement that
   cannot be placed is left out.
3. **Map to the key questions.** Tag each statement with the key questions (Q1–Q8) it bears on. A
   source may bear on none; then the article says so and stays short.
4. **Write the article** in the template from `output-format.md`, in the Oracle's voice.
5. **Voice check** (below). If it fails, the article is not written to `wiki/`; the failure is
   logged.

## Rules

- **Numbers keep their context.** Never write "40% of AI code is vulnerable"; write "about 40% of
  1,689 Copilot-completed programs across 89 CWE scenarios were vulnerable [S01]".
- **Scope is preserved.** A result about Copilot is not a result about SDD; a result about one
  banking service is not a result about software.
- **Authors' own limitations are reported** where the source states them.
- **No inference beyond the source.** "This suggests SDD would…" is not allowed in a source
  article. Implications belong in the question pages, labelled as the Oracle's reading.
- **Quotes:** at most two, each 25 words or fewer, in quotation marks, with the source tag.

## Voice check (catches drift to generic, hedged consensus)

Run on every article before it is saved. Two parts.

**Deterministic checks (`voice_check.py`, no LLM):**

| Check | Fails when |
| --- | --- |
| Source tags | A sentence in *What it shows* or *What it claims* has no `[Sxx]` tag |
| Evidence classes | A statement of effect lacks one of the bold class labels |
| Hype vocabulary | Any of: revolutionary, game-changer, game-changing, 10x, paradigm shift, unlock, supercharge, seamless, cutting-edge |
| Hedge density | More than 1 hedge word (may, might, could, potentially, arguably, perhaps, somewhat) per 60 words |
| Quote limits | More than two quotes, or a quote over 25 words |
| Template | A required section from `output-format.md` is missing |

**LLM review (one short call):** the article and `oracle.md` are given to the model with the
question: *"Would the evidence-first software engineer sign this article as written? Answer PASS, or
FAIL with the sentences that drift (vendor framing, unearned certainty, needless hedging, a claim
moved to a stronger evidence class)."*

## When an article fails

Per SD-KDP: **fix the specification, not the article.** Find which rule in these files the article
broke or which rule was missing, change the spec, and re-run. Each such change is one line in
`progress.md` ("spec change: …, because article Sxx …"). Hand-editing an article in `wiki/` is not
allowed; the next run would overwrite it anyway.
