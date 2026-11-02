# Week 7 · Extensions, run tool, and the freeze

**Focus:** settle every open design decision, then freeze the pre-registration before any study run.

| Deliverable | Where |
| --- | --- |
| Week-by-week plan to the 5 December deadline | [docs/WEEKLY-PLAN.md](../../docs/WEEKLY-PLAN.md) |
| Java/Quarkus extension: 2 projects, separately registered | [docs/PREREGISTRATION-JAVA.md](../../docs/PREREGISTRATION-JAVA.md) |
| Pre-registration decisions: time measure, research questions and hypotheses, question rule, resume message, κ check | [docs/PREREGISTRATION.md](../../docs/PREREGISTRATION.md) |
| **Fourth approach, `sdd_secure`**: spec-driven with security written into the constitution | [prompts/constitution-secure.txt](../../prompts/constitution-secure.txt) |
| **Existing-project stage**: one change request per project, run on each build's own code | [tasks/*-CR/](../../tasks/), [operator/answer-sheets/*-CR.md](../../operator/answer-sheets/) |
| Hidden tests for the change requests (107 cases): reviewed, validated against reference, naive and independent implementations, then sealed and encrypted | [sealed/](../../sealed/), [pre-registration Appendix C](../../docs/PREREGISTRATION.md) |
| `sddlog` 1.3: token counts, the new condition, the change stage | [tools/sddlog/](../../tools/sddlog/) |
| Run tool: drives each build in Claude Code, you only judge the agent's messages | [tools/study/run_build.py](../../tools/study/run_build.py) |
| Plain-language overview of the whole study | [docs/STUDY-OVERVIEW.md](../../docs/STUDY-OVERVIEW.md) |

**Still to do this week (you):** build both base repositories, run the mechanics checks (R002, R003, R024, R025), fill in section 11 of the pre-registration, commit the freeze, and email the hashes to your advisor.

| Run | Project | Approach | Purpose | Status |
| --- | --- | --- | --- | --- |
| R002 | T-SPLIT-01 | unstructured | mechanics | to do |
| R003 | T-SPLIT-01 | sdd_clarify | mechanics | to do |
| R024 | T-QCOUNT-01 | unstructured | mechanics-java | to do |
| R025 | T-QCOUNT-01 | sdd_clarify | mechanics-java | to do |
