# Domain Knowledge

> **OpenOwls SD-KDP** — Read by the distillation agent before every run.
> The terms, distinctions and facts the agent must get right, so every article uses them the same way.

---

## Glossary

| Term | Meaning in this knowledge base |
| --- | --- |
| Spec-driven development (SDD) | Writing a structured specification (requirements, then a technical plan, then tasks) *before* an AI agent writes code, and treating the specification as the source the code is generated from. |
| Vibe coding | Building software with an LLM **without reviewing the code it writes** (Willison's narrow definition, S14). Reviewed, tested AI-assisted code is *not* vibe coding. Use the term only in this sense. |
| Conversational / unstructured prompting | Asking an agent for the feature directly, in chat, without a written specification. The usual comparison condition for SDD. |
| Spec Kit | GitHub's open-source SDD toolkit (MIT), released September 2025. Command sequence: constitution → specify → (clarify) → plan → tasks → implement. |
| Constitution | Spec Kit's project-wide principles file, read before every phase. Security rules can be written into it (S06). |
| Kiro | AWS's agentic IDE. A spec is `requirements.md` (or `bugfix.md`), `design.md` and `tasks.md` (S11). |
| Tessl | A company with its own SDD framework; Böckeler compares it with Kiro and Spec Kit as the tool that goes furthest towards specs as the maintained source (S12). Check S12 before stating more. |
| Spec-first / spec-anchored / spec-as-source | Böckeler's three levels (S12): a spec written before the code; a spec kept and evolved with the code; a spec that *is* the source, with code generated from it. Use these labels when comparing tools. |
| Brownfield / change request | Changing an existing codebase, as opposed to building a new one (greenfield). |
| Traceability | Being able to follow a requirement to the code and tests that implement it, and back. |
| CWE | MITRE's Common Weakness Enumeration; "CWE Top 25" is the list of most dangerous weaknesses. |
| Determinism (of output) | How similar the code is across independent runs on the same input (S04 measures it by lexical similarity). |

## Evidence classes (used in every article)

| Class | Use when | Example phrasing |
| --- | --- | --- |
| **measured** | A study with a stated design and sample reports the number | "In an RCT with 16 developers, AI access increased completion time by 19% [S03]." |
| **reported case** | One project or organisation, method described | "One banking case study reports 73% fewer security defects [S06]; it has not been replicated." |
| **claimed** | Stated without method | "The announcement says … [S09]; no measurement is given." |
| **observed** | A named practitioner's hands-on experience | "Böckeler found the generated specs long and repetitive to review [S12]." |
| **documented** | What a tool's own documentation says it does | "Kiro produces three spec files [S11]." |
| **argued** | A position paper's reasoning | "Alenezi argues that … [S07]." |

## Facts the agent must not get wrong

- Spec Kit was announced by GitHub on 2 September 2025 [S09]; its methodology document is
  `spec-driven.md` in `github/spec-kit` [S08].
- Thoughtworks placed SDD in **Assess**, not Trial or Adopt, in November 2025 [S13].
- The METR study (S03) is about AI tools in general (Cursor with Claude 3.5/3.7 Sonnet), **not**
  about SDD. Use it only for the gap between perceived and measured speed.
- S01 and S02 are about Copilot/Codex-era assistants, **not** SDD. They set the security baseline.
- S05 is a study *design*: it has **no results**. Never cite a result from it.
- S06's 73% is **one case study by one author**; S07 itself notes it is unreplicated.
- S07 collects **no new data**.

## Boundaries of the domain

In scope: SDD for AI coding agents (2025–2026), its tools, and the evidence about AI-generated code
quality, security and productivity that bears on it. Out of scope: classical formal specification
and model-driven engineering, except as one-line background; general LLM benchmarks.
