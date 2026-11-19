# Output Format

> **OpenOwls SD-KDP** — Read by the distillation agent and by `voice_check.py`.
> The exact shape of every page in `wiki/`.

---

## Layout

```
wiki/
├── index.md              # one line per source article and per question page
├── faq.md                # short answers to the key questions, each linking to its question page
├── questions/Q1.md … Q8.md
└── sources/S01.md … S17.md
```

Plain Markdown, UTF-8, links relative (`../sources/S03.md`) so the wiki reads on GitHub and in any
Markdown viewer.

## Source article (`wiki/sources/<id>.md`)

```markdown
---
id: S03
title: <title as found at collection>
authors: <authors or publisher>
date: <YYYY-MM-DD or empty>
url: <url>
licence: <from sources.csv>
tier: T1
evidence_type: randomized controlled trial
questions: [Q4, Q8]
source_sha256: <hash of raw/<id>.txt at distillation>
spec_sha256: <hash of the four ai_specs files read>
model: <model id from llm.py>
distilled_at: <UTC timestamp>
---

# <Short title> [S03]

**In one sentence:** <what the source did and found, with its scope>.

## What it is
<design, sample or scope, date, who wrote it and any interest they have — 2 to 4 sentences>

## What it shows
- **measured** / **reported case** / **observed** / **documented**: <statement with numbers and scope> [S03]

## What it claims (without measurement)
- **claimed** / **argued**: <statement> [S03]
(or "Nothing beyond what it shows.")

## Method and limits
<the authors' stated limitations, then any the Oracle adds, labelled "Oracle's note:">

## Bearing on the key questions
- **Q4:** <one sentence on what this source contributes to the question>

## Quotes
> "<at most 25 words>" [S03]
```

## Question page (`wiki/questions/Q<n>.md`)

```markdown
---
question: Q4
sources: [S03, S12, S15]
synthesized_at: <UTC>
model: <model id>
---

# Q4. <question text from oracle.md>

**Short answer:** <2–3 sentences, the Oracle's bottom line, with tags>

## What has been measured
## What practitioners observe
## What is claimed but not measured
## Where the sources disagree
## What is still unknown
```

Every section may say "Nothing in the corpus." It must not be left out.

## FAQ (`wiki/faq.md`)

One entry per key question: the question as a heading, the short answer from its question page,
and a link to it. Nothing that is not on a question page.

## Index (`wiki/index.md`)

A table of source articles (ID, title, tier, evidence type, questions) and a list of question pages.
Generated, never written by hand.
