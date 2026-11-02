> **Archived as submitted.** This is the text of the Week 1 Plan and Report
> (originally a Word document). It is kept unchanged as the record of that week.

**Week 1 Plan and Report**

*Evaluating and Extending Spec-Driven Development: GitHub Spec Kit and OpenOwls SD-KDP*

| **Student** | Varshil Patel |
| --- | --- |
| **Program** | MS Computer Science, Temple University |
| **Faculty Advisor** | Alex Pang |
| **Reporting Period** | Week 1 of 16 — Part I: Foundations |

# 1. Purpose of This Week

Week 1 opens Part I (Foundations) of the independent study on Spec-Driven Development (SDD). The goal for this week is to begin the literature review and stand up a working Spec Kit environment, so that Part II (pilot and data collection) can start on schedule in Week 3. This report documents the planned activities, the concrete deliverables for the week, and how progress will be verified.

# 2. Planned Activities

**2.1 Literature Review (software SDD strand)**

- Read foundational security/correctness papers: Pearce et al. (2022/2023) on GitHub Copilot vulnerabilities; Perry et al. (2023) on AI-assisted code security.
- Read Spec Kit methodology sources: GitHub's Spec Kit blog post and documentation.
- Read the closest methodological analogue: Rosa et al. (2026), the SANER Stage 1 registered report on specification-first vs. test-first LLM code generation.
- Skim the two supporting preprints (Alenezi 2026 on AI-native SE frameworks; Marri 2026 on “constitutional” SDD) and the traceability paper (Panda 2026).
- Begin an annotated bibliography document: one paragraph per source covering claim, method, and relevance to RQ1–RQ4.

**2.2 Literature Review (knowledge-base strand, light pass)**

- Skim the OpenOwls SD-KDP guide to understand the six-step workflow and the seven specification files.
- Skim the OpenKB repository README to understand its automated, lighter-weight compilation approach.
- Add short annotated-bibliography entries for both, to avoid a cold start before Part IV in Week 12.

**2.3 Environment Setup**

- Install the Spec Kit CLI (specify).
- Configure at least one coding-agent integration (Claude Code and/or GitHub Copilot).
- Run a smoke test: execute the full command sequence — constitution → specify → plan → tasks → implement — on a trivial toy feature to confirm the pipeline works end-to-end before pilot work begins in Week 3.
- Sketch a logging/instrumentation scaffold (folder structure and format) for capturing prompts, specs, plans, task lists, diffs, and outputs, to be used starting in Part II.

**2.4 Administrative**

- Confirm study scope and Part IV time allocation (≈25%) with faculty advisor Alex Pang.
- Confirm access/accounts needed for chosen coding-agent integration(s).

# 3. Deliverables for Week 1

| **Deliverable** | **Status** |
| --- | --- |
| Annotated bibliography (in progress, 6–8 sources) | In progress |
| Working Spec Kit installation with 1+ agent integration | In progress |
| Successful smoke-test run of the full Spec Kit command sequence | Planned |
| Draft logging/instrumentation scaffold | Planned |

# 4. Risks / Open Questions

- Agent integration setup (API access, authentication) may take longer than expected — flagged as the main schedule risk for this week.
- Final confirmation of Part IV's knowledge-domain scope (Spec Kit/SDD literature itself, or an alternative domain) is still pending advisor approval.

# 5. Plan for Week 2

Complete the annotated bibliography, finish verifying the Spec Kit environment across all intended agent integrations, and finalize the logging protocol so that Part II's pilot run can begin in Week 3 as scheduled.

# 6. Sources Consulted (Spec Kit)

**Primary**

- GitHub, Inc. (2025). Spec-driven development with AI: Get started with a new open source toolkit. The GitHub Blog. https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/
- GitHub, Inc. (2026). spec-kit [Source code repository]. https://github.com/github/spec-kit

**Supporting**

- Lam, J. What's The Deal With GitHub Spec Kit. https://den.dev/blog/github-spec-kit/
- LogRocket Blog. Exploring spec-driven development with the new GitHub Spec Kit. https://blog.logrocket.com/github-spec-kit/
