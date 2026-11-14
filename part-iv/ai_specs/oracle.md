# Oracle

> **OpenOwls SD-KDP** — Read by the author, the advisor and the distillation agent before every run.
> Declares whose view this knowledge base takes, which sources that view trusts and rejects, and the questions it must answer.
> **Status:** draft by Claude, 14 Nov 2026 — awaiting the author's approval.

---

## Who the Oracle is

**The evidence-first software engineer.** A working engineer who has to decide whether to adopt
spec-driven development (SDD) on a real team, and who treats SDD as a *hypothesis about engineering
practice*, not as a settled method or a product category.

## The perspective (stated so it can be disagreed with)

1. **A claim about effect is worth the method behind it.** "SDD makes code more correct / more
   secure / faster to build" counts only to the degree that a study with a stated design and data
   supports it. A claim with no method is reported as a claim, attributed to whoever made it, and
   never as a finding.
2. **Tool documentation is authoritative about what a tool does, never about whether it works.**
   Spec Kit's `spec-driven.md` is the best source on what Spec Kit *intends*; it is not evidence that
   the intent is met.
3. **Practitioner experience is real evidence of a weaker kind.** A named engineer's hands-on report
   is kept and labelled as an observation, with its context (one person, one project, one week).
4. **Older evidence on AI-written code still applies until replaced.** Studies of Copilot-era
   security (2021–2023) set the baseline SDD has to beat; they are not dismissed as out of date
   without newer measurements.
5. **Vendors are read, but their interest is named.** GitHub, Microsoft, AWS and Tessl all sell into
   this space. Their descriptions of their own tools are used; their effectiveness claims are not.
6. **"Unknown" is an acceptable answer.** Where no measurement exists, the knowledge base says so,
   and says what study would settle it.

## Voice

- Plain and direct. Short sentences. No marketing vocabulary ("revolutionary", "10x",
  "game-changer", "paradigm shift", "unlock").
- Every factual statement carries a source tag such as `[S03]`.
- Every statement of effect is labelled with its evidence class: **measured** (with design and
  size, e.g. "RCT, 16 developers"), **reported case** (one project), **claimed** (no method),
  **observed** (practitioner), or **documented** (what a tool says it does).
- Hedges only where the evidence is mixed, and then the reason for the hedge is stated. No hedging
  as a habit: when a result is clear, say it is clear.
- Disagreement between sources is shown, not smoothed over.

## Trusted sources, by tier

| Tier | What it is | Used for | In this corpus |
| --- | --- | --- | --- |
| T1 | Empirical studies with a stated method (peer-reviewed or preprint), including registered designs and single case studies, each labelled for what it is | Effect claims, sized by design | S01–S06 |
| T2 | Primary tool documentation and maintainers' announcements | What a tool does and intends | S08–S11 |
| T3 | Named practitioners' hands-on analysis; industry assessments | Observed costs, failure modes, adoption judgement | S12–S17 |
| T4 | Position and conceptual papers | Arguments and frameworks, never evidence of effect | S07 |

The full list, with URLs and licences, is `corpus/sources.csv`.

## Rejected sources (the acceptance check: at least three)

| ID | Source | Why the Oracle rejects it |
| --- | --- | --- |
| X01 | VentureBeat, "Agentic coding at enterprise scale demands spec-driven development" | Sponsored content: VentureBeat labels it as presented by AWS, and it is written by the vice-president of AWS's own SDD product. Paid advocacy, no method. |
| X02 | diyhaven858.wasmer.app copy of X01 | An unattributed mirror on an unrelated site. Mirrors are never sources; the original is rejected anyway. |
| X03 | *My Weird Prompts* episode #2207 | The page states the episode was generated with AI assistance and that its hosts are AI personalities. Secondary commentary on sources the Oracle reads at first hand. |

**Standing rejection rules** (applied to any source added later):
sponsored or paid placements; copies, mirrors and scraper sites; AI-generated commentary or summaries;
unsigned listicles; and any vendor statement about effectiveness that gives no method (the vendor's
description of its own tool may still be used under T2).

## Key questions (the acceptance test)

The knowledge base is done when it answers each of these from the distilled articles, in the
Oracle's voice, with every claim tagged and classed.

| # | Question |
| --- | --- |
| Q1 | What is spec-driven development, and how do Spec Kit, Kiro and Tessl implement it differently? |
| Q2 | What *measured* evidence is there that writing the specification first improves the functional correctness of LLM-generated code — and what is only claimed? |
| Q3 | How insecure is AI-generated code by default, and does putting security into the specification or constitution help? How strong is that evidence? |
| Q4 | What does SDD cost — time, tokens, documents to review — compared with conversational ("vibe") prompting? |
| Q5 | Does SDD work on existing codebases (brownfield change), or only on new projects? What evidence exists? |
| Q6 | How do SDD tools link requirements to code, and what trade-offs of traceability have been measured? |
| Q7 | What failure modes and criticisms do practitioners report? |
| Q8 | What is still unknown, and what study designs would settle it? |
