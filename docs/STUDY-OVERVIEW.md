# Study overview

A plain-language summary of what this study compares, how, and what it will
produce. The binding details are in [PREREGISTRATION.md](PREREGISTRATION.md);
the operator steps are in [RUNBOOK.md](RUNBOOK.md).

## The question

When a coding agent builds software, does writing a specification first
(spec-driven development, SDD) change what it builds and how it behaves,
compared with simply describing the feature in a prompt ("vibe coding")?
In particular:

- Is the code more **correct**, and more **secure**?
- What does it **cost**, in agent time, tokens and human turns?
- Does it help when the agent changes an **existing** project, not only when
  it starts a new one?
- Does it matter whether **security is written into the specification**?

## The four approaches compared

All four use the same agent (Claude Code), the same model (`claude-opus-5`),
the same projects and the same rules for answering the agent.

| Approach | What the agent gets | What it represents |
| --- | --- | --- |
| `unstructured` | The project description as one prompt | Vibe coding |
| `sdd` | GitHub Spec Kit's sequence: constitution, specification, plan, task list, implementation | Spec-driven development as shipped |
| `sdd_clarify` | The same, plus Spec Kit's clarification step, where the agent asks questions before planning | SDD that resolves ambiguity |
| `sdd_secure` | The same as `sdd`, with security requirements written into the constitution (from the OWASP Top 10 and ASVS) | SDD with security defined in the spec |

No approach is told to be secure except `sdd_secure`. Security is measured as
the implicit expectation it usually is in practice.

## New projects and existing projects

Each of the five projects is built twice over:

1. **New project (build).** The agent starts from an empty repository and
   builds the project from its description.
2. **Existing project (change request).** In the same repository, the same
   approach then gets a change request that adds a feature to the code it just
   built. The agent has no memory of the build: it must read the existing code
   (and, in SDD, the existing specification) to make the change. Each change
   request also opens a new, unstated security risk.

The five projects, from smallest to largest:

| Project | Build | Change request |
| --- | --- | --- |
| T-REDACT-01 | Removes emails, IP addresses and card numbers from log files | Phone numbers, and writing results to an output folder |
| T-TARX-01 | Lists and extracts tar archives | Creates archives |
| T-BOOKMARKS-01 | Bookmark manager on SQLite, with search and export | Import from a file, and an HTML export |
| T-ACCOUNTS-01 | Password account store with lockout | Password-reset tokens |
| T-PASTE-01 | HTTP service for sharing text snippets | One-time ("burn after reading") and password-protected pastes |

## How each run is judged

Every build and change request is scored against **hidden tests** that the
agent never sees. They were written and checked before any study run, then
encrypted (`sealed/`), with their fingerprints recorded, so nobody can tune
them to the results.

| Tier | What it checks | Example |
| --- | --- | --- |
| A, stated | What the description asks for | Card numbers become `[CARD]` |
| B, intent | Points the description leaves open, answered by the product owner only if the agent asks | Does one unreadable file stop the whole run? |
| C, security | Implicit security expectations, each mapped to a CWE weakness | A crafted archive must not write outside the target folder (CWE-22) |

There are 157 hidden tests for the builds and 107 for the change requests.
After a change request, the build's own stated and security tests are run
again to catch anything the change broke (regression).

Security is also checked with the Bandit static analyser and a manual review
against a fixed checklist; only findings confirmed by hand are counted.

## What is measured

| Measure | How |
| --- | --- |
| Correctness | Tier A and tier B pass rates |
| Security | Tier C pass rate; confirmed security findings by severity |
| Traceability | Whether each requirement can be traced to code and to a test |
| Time | Agent working time per phase, from the logging hooks |
| Tokens and cost | Tokens per model message from the session transcripts; Claude Code's own cost figures as a cross-check |
| Human effort | Number of operator messages |
| Behaviour | Questions asked, assumptions made, whether specifications are ever revised |

## How a run is done

The operator runs `tools/study/run_build.py <run ID>` in a fresh copy of the
base repository. The tool sends every fixed prompt to Claude Code, runs the
stopping-rule check, and logs everything. The operator's only job is to say,
after each agent turn, whether the agent asked a question (and which answer
from the answer sheet applies), asked for permission, listed assumptions, or
finished. The operator never types into the agent.

Every run is recorded by `sddlog` (prompts, tool calls, edits, time, tokens,
and a snapshot of every specification document after each phase).

## Scale and schedule

- 20 builds (5 projects × 4 approaches) and 20 change requests, in four
  counterbalanced rounds, plus 6 Java builds in a separately registered
  extension.
- Study runs: Weeks 8–10. Scoring and coding: Week 11. Writing: Week 12.
  Report due 5 December 2026.

## What exists already, and what does not

**Already done:** the design, the projects, the hidden tests and their
validation, the logging instrument, the run tool, the pilot run (R001), and a
practice comparison on a login page (excluded from the data).

**Not yet done:** the study runs themselves. No result in this repository is a
study finding until those runs are complete.
