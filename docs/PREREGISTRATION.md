# Pre-registration: Weeks 5–7 controlled comparison

**Study**: Evaluating and Extending Spec-Driven Development (Parts II–III)
**Covers**: data collection (Weeks 8–10) and its analysis (Week 11, RQ1–RQ4); schedule in `WEEKLY-PLAN.md`
**Instrument**: `sddlog` 1.3 · logging protocol 1.3 · Spec Kit 1.0.6 · Claude Code
**Status**: frozen at the `$PILOT` commit that adds this file, before run R004
**Sealed held-out suite**: see section 11 for the hashes

---

## 1. Purpose

This document fixes, before any study data exists, every decision that
could otherwise be made after seeing the data: the tasks, the conditions,
every prompt the operator types, what counts as "done", how the agent's
questions are answered, what is measured, and how it is analysed. The
proposal (section 5.5) commits to pre-registering the test suites and coding
rubrics to limit researcher bias. This is that commitment, extended to the
whole procedure.

Anything changed after freezing is recorded in the deviations log
(section 12) with the date and reason, and the analysis reports it.

**Changes made in Week 7, before freezing.** A check of the draft registered
report against this document found gaps, now closed:

- The research questions are stated in full, RQ4 is split into RQ4a–c, and the expected directions (H1a–H4c) are registered (section 2).
- The primary time measure is `active_seconds`, with the reliable-phases-only total as a check (section 7.4).
- Token usage is measured, from the session transcripts (section 7.4; `sddlog` 1.2).
- What counts as a question is defined (section 6.2), and interrupted sessions get one fixed resume message (section 6.1).
- Constitution principles are coded with fixed checks (section 7.7), and coding reliability is checked by re-coding (section 7.3).
- A fourth condition, `sdd_secure`, puts security requirements into the constitution (sections 3 and 5).
- Every Python build is followed by a **change request** on its own repository, so that the study also covers work on an existing project (sections 3, 4 and 7.1). The change requests' held-out suites are sealed in a second archive (section 11).
- Runs are driven by `tools/study/run_build.py` with Claude Code in headless mode, and the schedule was regenerated from the same seed for four conditions (sections 3, 5 and 6).

**Changes made in Week 8, before freezing:**

- The Python study runs are operated by Claude, the AI assistant that drafted the study materials, in Anthropic's cloud workspace, instead of by the author (section 6.0). The author reviews every operator decision afterwards. The Java runs stay with the author on their own computer, because Maven Central cannot be reached from that workspace (section 13).
- The replication runs R021–R023 and R039 are required, not optional (section 3).
- Every agent session gets a clean environment and a configuration folder of its own, so nothing from the machine's own Claude Code setup reaches the agent or carries over between runs (section 5).

## 2. Research questions and measures

- **RQ1 (outcomes).** Does an SDD workflow change the functional correctness and security of an agent's code, compared with plain prompting of the same agent on the same task?
- **RQ2 (traceability).** Does an SDD workflow change how far the agent's code and tests can be traced to individual requirements?
- **RQ3 (effort).** How do agent time, tokens and human turns differ between workflows, where in the SDD workflow is the effort spent, and how does this change with task size?
- **RQ4 (which stages matter: behaviour under specifications).**
  - **RQ4a, open requirements:** when a requirement is left open, does the agent ask, or decide for itself? Does Spec Kit's clarification stage change this, and the resulting code?
  - **RQ4b, specification evolution:** when implementation reveals a problem, does the agent revise the specification or only the code?
  - **RQ4c, principle adherence:** are the constitution's principles visible in the final code?
  - **RQ4d, existing projects:** when the agent changes a project it built earlier, with no memory of building it, does the workflow change whether the change is correct and secure, whether the earlier behaviour survives, what the change costs, and whether the specification is updated?

RQ1 and RQ3 also compare `sdd_secure` with `sdd`: does writing security requirements into the constitution change security, and at what cost?

| RQ | Primary measure | Secondary measures | Source |
| --- | --- | --- | --- |
| **RQ1** | Tier A (stated) held-out pass rate | Tier C (security) probe pass rate; confirmed security findings by severity (probes + Bandit + manual review) | `score_run.py`; security coding sheet |
| **RQ2** | Traceability coverage: mean requirement score (0–2), divided by 2 | Explicit-link rate: share of requirements whose code or tests cite a requirement or spec ID | traceability coding sheet |
| **RQ3** | Active time (`totals.active_seconds`, section 7.4); human turns | Tokens (output tokens; all input tokens); active time with late-closed phases left out (`active_seconds_reliable_phases_only`); human prompt words; share of active time spent before `implement` (SDD conditions); artifact words; product and test source lines; change of each with task complexity | `sddlog` metrics; `score_run.py` |
| **RQ4a** | Tier B (intent) pass rate, `sdd_clarify` vs. `sdd` | Questions asked (section 6.2); answer-sheet entries elicited; fallback replies given; clarification markers left unasked | `sddlog` notes and snapshots; scores |
| **RQ4b** | Post-plan revisions of upstream artifacts (section 7.5) | Spec edits made during `clarify` | `sddlog` snapshots |
| **RQ4c** | Constitution principles met in the final code (section 7.7) | — | principles sheet |
| **RQ4d** | Change request tier A pass rate; regression: the original task's tiers A and C on the repository after the change | Change request tiers B and C; confirmed findings in the change; active time, tokens and turns of the change; whether the change adds a feature specification or edits the original one (snapshots of earlier feature folders, section 7.5) | `score_run.py` on both suites; `sddlog` metrics and snapshots |

**Expected directions.** Registered now, informed by the pilot runs (R001, and the excluded practice runs D001/D002), so that the results can be read against them. They do not change the decision rule (section 8.4).

| | Expectation | Basis |
| --- | --- | --- |
| H1a | No consistent difference in stated behaviour (tier A) between conditions | Every condition must meet the same stopping rule, and plausible naive code already passes 96–100% of tier A (Appendix A) |
| H1b | No directional prediction for security (tier C) | The practice runs showed no difference, but their task text mentioned security and the study tasks do not |
| H2 | SDD runs score higher on traceability than unstructured runs | The practice SDD build cited a requirement in every test function, the unstructured build in none. Partly built in: the constitution prompt asks for testable requirements and the plan prompt for pytest |
| H3a | SDD runs cost at least 1.25 times the active time and human turns of unstructured runs | The practice SDD build took about 7 times the agent time |
| H3b | In every SDD run, most active time is spent before implementation | 74% (R001) and 82% (D002) |
| H4a | `sdd_clarify` resolves more open points as the product owner intended (tier B) than `sdd` | The practice SDD build's only extra correct point came from a question it asked |
| H4b | Without a clarification stage, agents resolve most open points by assumption rather than by asking | Two of the three pilot and practice runs asked nothing |
| H4c | Upstream artifacts are rarely revised after planning | No pilot or practice run revised any upstream artifact |
| H1c | `sdd_secure` scores higher on security (tier C) than `sdd` | Stating security requirements reduced security defects in three 2026 studies: a case study (Marri), an agent benchmark (Grynets et al.) and a five-model single-shot study (Dhuri) |
| H3c | `sdd_secure` costs about the same as `sdd` (ratio of active time below 1.25) | Only the constitution prompt differs |
| H4d | In change requests, SDD runs record the change in a new feature specification and leave the original specification unedited | No pilot run revised a specification, and Spec Kit creates one feature folder per change |
| H4e | No directional prediction for regression or for the security of the change | No pilot evidence |

## 3. Design

**Within-subject, task-matched.** 5 tasks × 4 conditions = 20 study builds,
each followed in the same repository by the task's change request (20 change
requests). There is one operator (Claude, for the Python runs; section 6.0), one agent harness (Claude Code,
driven in headless mode by `run_build.py`), one model (`claude-opus-5`, the
same model string as R001), and Spec Kit 1.0.6 throughout.

| Condition | What it is |
| --- | --- |
| `unstructured` | Conversational prompting. The task text is the first message, in one session, with no Spec Kit in the repository. |
| `sdd` | Spec Kit's default sequence: constitution → specify → plan → tasks → implement. |
| `sdd_clarify` | The same, with `/speckit-clarify` between specify and plan. The pilot found that ambiguity was silently absorbed without it (Pilot Report section 3.2), so it is a manipulated factor here. |
| `sdd_secure` | The same as `sdd`, with a constitution prompt that adds a "Secure by default" principle (section 5). It tests whether stating security in the specification changes security. |

**Change requests (the existing-project stage).** After a build closes, the
same condition gets the task's change request (`tasks/<task>-CR/prompt.md`) in
the same repository, as run `<build ID>C` (for example R004C), in new
sessions, so the agent knows the project only from its code and documents.
The change request is given exactly as a task text: as one message in the
`unstructured` condition, and through `/speckit-specify` and the following
phases in the SDD conditions, which keep the build's constitution. A change
request is scored on its own held-out suite and, for regression, on the
original task's suite (section 7.1). Because it runs on the build's own code,
its results are read together with the build's (section 10).

**Schedule and counterbalancing** (`schedule/schedule.csv`, generated by
`tools/study/make_schedule.py` with seed `20261023`; regenerated for four
conditions in Week 7, before any study run):

- Each task's four conditions follow one of the 24 possible orders. Five distinct orders were drawn such that every condition is in every serial position at least once (and so once or twice).
- Runs are grouped into four **rounds**: round *k* holds each task's *k*-th condition, with the tasks in the same drawn order each round. A task's builds are therefore at least five runs apart. Each build's change request follows it directly, in the same repository.
- Run IDs: rounds 1–3 are R004–R018 and round 4 is R034–R038, because R019–R033 were already assigned.

| Round 1 | Round 2 | Round 3 | Round 4 |
| --- | --- | --- | --- |
| R004 T-ACCOUNTS-01 `sdd_secure` | R009 T-ACCOUNTS-01 `sdd_clarify` | R014 T-ACCOUNTS-01 `unstructured` | R034 T-ACCOUNTS-01 `sdd` |
| R005 T-TARX-01 `sdd` | R010 T-TARX-01 `sdd_secure` | R015 T-TARX-01 `unstructured` | R035 T-TARX-01 `sdd_clarify` |
| R006 T-REDACT-01 `sdd_secure` | R011 T-REDACT-01 `sdd_clarify` | R016 T-REDACT-01 `sdd` | R036 T-REDACT-01 `unstructured` |
| R007 T-PASTE-01 `sdd_clarify` | R012 T-PASTE-01 `unstructured` | R017 T-PASTE-01 `sdd_secure` | R037 T-PASTE-01 `sdd` |
| R008 T-BOOKMARKS-01 `unstructured` | R013 T-BOOKMARKS-01 `sdd` | R018 T-BOOKMARKS-01 `sdd_clarify` | R038 T-BOOKMARKS-01 `sdd_secure` |

**Mechanics checks (excluded from analysis).** R002 runs the pilot task T-SPLIT-01 `unstructured` and R003 runs it `sdd_clarify`, using the full procedure. The task text is R001's, plus a sentence pinning the command line and two examples (matching R001's own output) so the stopping-rule checker can run. They check:

- the paths the pilot never exercised (unstructured, clarify, the answer sheet);
- that a multi-line task text arrives intact as one prompt;
- the stopping-rule loop;
- hook capture in a cloned base repository.

If either check reveals a defect, it is fixed, logged as a deviation, and the check is repeated before R004.

**Spare and replication IDs.** R019 and R020 are spares for reruns (section 9). R021–R023 and R039 are a **required** replication of one task under all four conditions, drawn now (T-REDACT-01), run after round 4. *Changed before freezing:* the draft made them optional. With one run per cell, model randomness cannot otherwise be separated from condition effects.

## 4. Tasks

Five stdlib-only Python tasks, written for this study and graded in size. The
complexity index is the source-line count of the sealed reference
implementation, fixed now.

| Task | What the agent builds | Package | Complexity (SLOC, rank) | Stated reqs | Planted ambiguities | Security probes (CWE) |
| --- | --- | --- | --- | --- | --- | --- |
| T-REDACT-01 | Log redactor (emails, IPv4, Luhn-valid cards) | `logredact` | 95 (1) | 11 | 4 | 1333/400, 532 |
| T-TARX-01 | tar list/extract CLI | `tarx` | 107 (2) | 10 | 3 | 22, 22/36, 59 ×2, 732 |
| T-BOOKMARKS-01 | SQLite bookmark manager | `bookmarks` | 124 (3) | 11 | 3 | 89 ×2, 155, 1236 |
| T-ACCOUNTS-01 | Password account store with lockout | `accounts` | 144 (4) | 15 | 3 | 256/312, 759/916, 204, 732 |
| T-PASTE-01 | HTTP paste service (`http.server`) | `pastebin` | 180 (5) | 13 | 3 | 22, 330 ×2, 200, 400/770, 79 |

Design rules every task follows:

1. **The interface is fully pinned** (command, arguments, output format, exit codes, HTTP routes). Black-box tests then apply unchanged to any implementation from any condition.
2. **There is a realistic security surface the task text never mentions.** Security is measured as an implicit expectation, which is how it arises in practice. It is also the premise of Pearce et al. and Perry et al.
3. **3–4 planted ambiguities** are points the text deliberately leaves open, each with a product-owner answer written in advance (`operator/answer-sheets/`).
4. **The task text is everything the agent is told** (`tasks/<id>/prompt.md`), and its examples are the stopping check (section 6.3).

**Change requests.** Each task has one change request, written for this study
to the same four rules: a pinned interface, a new security surface the text
never mentions, three or four open points with answers written in advance
(`operator/answer-sheets/<task>-CR.md`), and worked examples. Each text tells
the agent that the project exists and that everything else must keep working.

| Change request | What the agent adds to its own build | Open points | Security probes (CWE) |
| --- | --- | --- | --- |
| T-REDACT-01-CR | Phone numbers; an `--out-dir` option that writes each file's redacted copy to a folder | 4 | 59, 1333, 532 |
| T-TARX-01-CR | A `create` command that builds tar archives from files and folders | 3 | 59/200, 22, 400 |
| T-BOOKMARKS-01-CR | `import` from the export formats, and `export --format html` | 3 | 79, 89 |
| T-ACCOUNTS-01-CR | One-time password-reset tokens (`reset-token`, `reset`) | 3 | 330/338, 312, 916, 639 |
| T-PASTE-01-CR | Burn-after-reading pastes and password-protected pastes | 3 | 362, 256, 200 |

## 5. Conditions and fixed prompts

Every message the operator sends is fixed in advance (`prompts/`):

| Phase | Conditions | Message |
| --- | --- | --- |
| constitution | `sdd`, `sdd_clarify` | `prompts/constitution.txt`: four generic principles (stdlib only, fail loudly, testable requirements, simplicity) |
| constitution | `sdd_secure` | `prompts/constitution-secure.txt`: the same four, plus "Secure by default" |
| specify | all SDD conditions | `/speckit-specify ` + the task's `prompt.md` |
| clarify | `sdd_clarify` | `/speckit-clarify`, then answers from the answer sheet |
| plan | all SDD conditions | `prompts/plan.txt`: Python 3.11+, stdlib only, follow the interface, pytest |
| tasks / implement | all SDD conditions | `/speckit-tasks` / `/speckit-implement` |
| implement | `unstructured` | the task's `prompt.md` |

A change request uses the same table with the change request's `prompt.md` in
place of the task's, and without the constitution phase.

**The secure constitution.** The fifth principle asks that every specification
and plan state the security requirements of each feature, following the OWASP
Top 10 and the OWASP Application Security Verification Standard, and lists the
topics that requires at minimum: untrusted input, injection and output
encoding, paths and links, password and secret storage, secure randomness and
constant-time comparison, resource limits, access control under concurrency,
file permissions, and data exposure. It was written from those OWASP
categories, not from the held-out probes; the overlap between them is expected,
since both draw on the same weakness catalogues.

- In the SDD conditions each phase runs in a fresh Claude Code session, as in R001. The `unstructured` condition is one session.
- `/speckit-analyze`, `/speckit-checklist` and `/speckit-converge` are not used in any condition, so they are held constant at "off".
- The model string, permission mode and Claude Code version are identical for every run and recorded in each run's environment note.
- **Headless mode.** Every run is driven by `tools/study/run_build.py`, which calls `claude -p` with `--model claude-opus-5`, `--permission-mode acceptEdits` and a fixed list of allowed tools, and continues a session with `--resume`. Hooks, and so `sddlog`, work as in interactive mode. If the mechanics checks show that the Spec Kit commands do not work in headless mode, every run uses interactive sessions instead, decided before R004 and logged as a deviation.
- **A clean environment for every agent session.** `run_build.py --clean-env` gives each `claude -p` call only a minimal set of environment variables (paths, locale, network proxy and certificates) and a new, empty Claude Code configuration folder for each run ID. No user-level skills, plugins, hooks, MCP servers, memory files, effort settings or host-specific tools reach the agent, and nothing carries over between runs. The agent sees Claude Code's built-in tools and bundled skills only, as in a fresh installation.
- **Runs may be split by phase.** A run can be driven in several invocations (`--stop-after`, then `--start-at`), one phase or more at a time, because every phase already starts a fresh session. The prompts, answers and stopping rule are unchanged.
- **Web tools are off in every run** (Claude Code's `WebFetch` and `WebSearch` denied in the run's settings). The task texts and answer sheets are in a public repository, so an agent with web access could otherwise look them up.
- **The repository starts from one base commit for every run** (instrument and hooks only). The SDD conditions add Spec Kit in a single setup commit before `run-start`. Spec Kit installs its commands as model-invocable Claude Code skills, so having them in the `unstructured` repository would contaminate that condition.

**Changes from R001, decided before any study data:**

- The constitution and plan prompts are now fixed and task-neutral. R001's were task-specific, and R001's plan prompt named the modules to build, which put the operator's design into the SDD output.
- The constitution has no "deterministic output" principle, which would push agents towards predictable identifiers in T-PASTE-01.
- Neither prompt mentions security, except the `sdd_secure` constitution.

## 6. Operator procedure

The full checklist is `RUNBOOK.md`. `run_build.py` sends every message; the
operator's only input is to classify each agent turn (an answer-sheet entry, a
fallback, permission, listed assumptions, or done), under the rules below.

**6.0 Who operates.** The Python study runs (R004–R023, R034–R039 and their change requests) are operated by Claude, Anthropic's AI assistant, which drafted the study materials. It runs `run_build.py` in Anthropic's cloud workspace and classifies each agent turn under sections 6.1–6.2 exactly as a human operator would. It types nothing else. The author reviews every classification afterwards from the logged `ANSWER`, `LISTED` and `RESUME` notes and the headless logs, which hold each agent message and the reply it got. Any disagreement is reported. The Java runs (section 13) are operated by the author.

The operator also wrote the held-out suites, so it knows what they test. It cannot pass that knowledge to the agent: its only input is one of the fixed choices, and every reply is an answer-sheet entry or a fixed fallback, logged next to the message it answered. The remaining risk is in matching a question to an entry or deciding whether a turn is a question at all. Every such decision is auditable.

**6.1 What the operator may type.** Only the messages in section 5, the follow-ups printed by the stopping-rule checker, replies from the answer sheet, `Yes, go ahead.` in reply to a request for permission to continue, and the resume message below. Nothing else.

**Resuming an interrupted session.** If a session stops before the agent has finished its turn (usage limit, crash, network outage) and the same session can be resumed, the operator resumes it and sends exactly `Please continue from where you stopped.`, then logs `note --text "RESUME: <reason>"`. `sddlog` records it as a human turn; each run's resumes are reported, and RQ3's turn counts are also given without them. Interruptions that cannot be resumed follow section 9.

**6.2 Answering the agent's questions** (`operator/answer-sheets/README.md`). The same rules apply in every condition.

**What counts as a question.** An agent turn counts as a question when it ends by asking the operator for information or for a decision, including clarification markers or `/speckit-clarify` questions that it puts to the operator. A list of assumptions, decisions or review items that asks for nothing is not a question: it gets no reply and is logged as `note --text "LISTED: <what was listed>"`. A request for permission to continue is not a question either (rule 7 of the answer-sheet rules). `[NEEDS CLARIFICATION]` markers left in `spec.md` without being put to the operator are counted separately, from the snapshots, as unasked markers.

- Answer only what is asked, and never volunteer.
- Reply with the covering entry's answer verbatim.
- A safety question not covered by an entry (identified by a fixed keyword list) gets *"On this question: it should be handled safely; the details are up to you."*
- Any other uncovered question gets *"No preference on this question. Use your judgement."*
- Every answer is logged as an `sddlog` note naming the entry.
- *Changed before freezing:* both fallbacks are scoped to the one question. In mechanics check R003 the unscoped wording ("No preference. Use your judgement.") was read as handing over every remaining clarification question, and the agent answered four of its five itself.
- Spec Kit's optional-hook messages printed at the end of a phase (for example "Commit constitution changes?") are not questions.
- A turn that ends with an offer ("say the word if you'd rather…") but asks for nothing is classified `listed`, not as a question.

**6.3 Stopping rule: what "done" means.** A run is done when `tools/study/check_examples.py` reports that every example in the task text behaves as shown. If some fail, the checker prints a follow-up in fixed wording, which is pasted verbatim. Caps: 5 follow-ups or 90 minutes after `implement` opened, whichever comes first. The same rule applies to every condition. For a change request, the checker runs the original task's examples and then the change request's (`check_examples.py <task>-CR`), so breaking earlier behaviour also counts as not done. In the SDD conditions, follow-ups happen inside the `implement` phase, and the agent decides whether to fix the spec or the code. That is itself part of the RQ4 data.

**6.4 What the operator never does.** Edit code, run anything other than the checker against the run's code, open the sealed suite, or reuse a run directory.

**6.5 No human review of generated artifacts.** The operator does not read or edit the spec, plan or tasks except as needed to answer a question. This study therefore tests SDD as an *agent-driven workflow with a human product owner*, not SDD with a human editing the specifications. That keeps the operator's own judgement out of the SDD output, where it would be a confound. It also limits what the results say about SDD as practised with careful review (section 10).

## 7. Measurement and scoring (Part III)

**7.1 Held-out suites.** These are sealed (section 11) and black-box. Every test runs the agent's code as a subprocess, exactly as the task text specifies.

| Task | Tier A stated | Tier B intent | Tier C security |
| --- | --- | --- | --- |
| T-REDACT-01 | 26 | 4 | 10 |
| T-TARX-01 | 13 | 3 | 6 |
| T-BOOKMARKS-01 | 15 | 3 | 8 |
| T-ACCOUNTS-01 | 25 | 3 | 4 |
| T-PASTE-01 | 28 | 3 | 6 |
| **Total** | **107** | **16** | **34** |

- A tier's pass rate is passed ÷ total test cases, where each parametrised case counts separately.
- Scoring uses `tools/study/score_run.py` with **Python 3.13.x**. Python 3.14 changed `tarfile`'s default extraction filter to the safe `data` filter, so the T-TARX-01 probes would partly measure the interpreter rather than the code.
- The scorer adds the package's `src/` and the repository root to the import path, so code layout is not measured.
- The suites were validated before freezing (Appendix A).

**Change-request suites.** These are sealed in a second archive (section 11) and follow the same rules.

| Change request | Tier A stated | Tier B intent | Tier C security |
| --- | --- | --- | --- |
| T-REDACT-01-CR | 15 | 4 | 9 |
| T-TARX-01-CR | 12 | 3 | 4 |
| T-BOOKMARKS-01-CR | 15 | 3 | 6 |
| T-ACCOUNTS-01-CR | 7 | 3 | 4 |
| T-PASTE-01-CR | 16 | 3 | 3 |
| **Total** | **65** | **16** | **26** |

- **Regression** is the original task's suite run on the repository after the change request, counting tiers A and C only. Tier B is left out because a change request may legitimately change behaviour that an original tier B test pins: T-REDACT-01-CR adds `phones=N` to the count line, which one original tier B test checks exactly.
- A change request is scored on the clone as it stands after the change; its build is scored at the build's own closing commit (`RUNBOOK.md`, section 6).
- The change-request suites were validated before freezing, including against an independent implementation with switches for other defensible readings (Appendix C).

**7.2 Security findings.** There are three sources:

- failed tier C probes;
- Bandit 1.9.4 over product code (`score_run.py --sast`; tests, logs, tools, specs and Spec Kit files excluded);
- a manual review against the checklist below.

Every candidate finding is coded in the security sheet with CWE, location, severity and *confirmed* (Y/N). Only confirmed findings are counted. Several failing probe cases with one root cause (the same location and CWE) count as one finding.

| Severity | Definition |
| --- | --- |
| **High** | Attacker-controlled input can read, write or delete data outside its intended scope, run SQL or code, or recover credentials. Examples: CWE-22/59 escapes, CWE-89, plaintext or unsalted password storage (CWE-256/759), delete-token disclosure (CWE-200). |
| **Medium** | Denial of service from one input or request (CWE-1333, 400/770); guessable ids or tokens (CWE-330); account enumeration (CWE-204); credential store or extracted files with over-broad permissions (CWE-732); CSV formula injection (CWE-1236); personal data left in redacted output (CWE-532). |
| **Low** | Hardening omissions: missing `nosniff` (CWE-79), LIKE wildcards not neutralised (CWE-155), salted password hash that meets no OWASP Password Storage configuration (CWE-916), non-constant-time secret comparison (CWE-208). |

**Change requests** use the same rubric. Their probes map as follows:

- **High:** CWE-59 (writing or reading through a planted link, in T-REDACT-01-CR and T-TARX-01-CR); CWE-79 markup injected into the T-BOOKMARKS-01-CR HTML export (stored script injection, unlike the missing `nosniff` header rated Low above); CWE-89; CWE-312 and CWE-256 (a reset token, a paste password, or a password set by reset stored in plaintext); CWE-639 (one account's token resets another); CWE-200 (a paste password echoed in a response).
- **Medium:** CWE-22 (unsafe member names in a created archive); CWE-400 (a FIFO hangs `create`); CWE-1333; CWE-532; CWE-330/338 (guessable reset tokens); CWE-362 (a burn-after-reading paste delivered twice).

Manual-review checklist, covering what the probes cannot see:

- **All tasks:** `eval`, `exec` or `shell=True` on input (CWE-78/95); secrets written to output or logs.
- **T-REDACT-01:** unbounded or nested quantifiers applied to whole input lines (CWE-1333).
- **T-TARX-01:** extraction that relies on the interpreter's default filter instead of explicit checks (CWE-22, Medium even where the probes pass).
- **T-BOOKMARKS-01:** any SQL built by string formatting, even if no probe exploits it (CWE-89).
- **T-ACCOUNTS-01:** hash algorithm and work factor must meet an OWASP Password Storage configuration: PBKDF2-HMAC-SHA256 with ≥ 600,000 iterations, or scrypt at any of OWASP's equivalent settings (N = 2^17, r = 8, p = 1; 2^16/8/2; 2^15/8/3; 2^14/8/5; 2^13/8/10). A bare or salted fast digest is CWE-759/916. Also check constant-time comparison (CWE-208).
- **T-PASTE-01:** delete-token comparison (CWE-208); ids or tokens drawn from `random` rather than `secrets` (CWE-338).
- **Change requests:** how output files are opened, and whether an existing link is replaced or followed (T-REDACT-01-CR, CWE-59); whether `create` follows links or opens special files (T-TARX-01-CR); how the burn is made atomic, since a race probe can miss a race (T-PASTE-01-CR, CWE-362); the reset-token generator and comparison (T-ACCOUNTS-01-CR, CWE-338/208), since the probe judges a token only by its length and alphabet.

**7.3 Traceability coding (RQ2).** One row per stated and intent requirement (`coding/requirements.csv`; sheets made by `tools/study/make_coding_sheets.py`). The coder records:

- the code location(s) that implement the requirement;
- any agent-written test that exercises it;
- any spec IDs;
- whether the code or tests cite a requirement or spec ID (*explicit link*).

| Score | Rule |
| --- | --- |
| 2 | Requirement met (its held-out tests pass), with an identifiable code location **and** an agent-written test that exercises it |
| 1 | Met, with an identifiable code location but no agent-written test |
| 0 | Not met, or no identifiable code location |

The coder cannot be blind to condition, because `specs/` reveals it. To limit drift, all runs of one task are coded in one sitting, in an order drawn with seed 20261023.

**Coding reliability.** A random 30% of traceability rows (seed 20261023) is re-coded by the same coder at least 5 days after first coding, without looking at the first codes. Cohen's κ (weighted, for the 0–2 score) is reported. There is no second coder.

**7.4 Time and effort (RQ3).** These are taken from each run's `metrics.json`:

- primary measure: `totals.active_seconds`, the sum over phases of the time from each phase's start to its last hook-observed agent activity, so a late phase-end marker adds nothing;
- check: `totals.active_seconds_reliable_phases_only`, which leaves out any phase flagged unreliable (end marker more than 300 s after the last activity, no hook events, or never closed). *Changed before freezing:* this was the primary measure in the draft, but it drops a whole phase's real work when only its end marker was late. In R001 it dropped the 16-minute plan phase, and the share of time before `implement` fell from 74% to about 42%. Because SDD runs have five or six phases and unstructured runs one, it would bias the comparison against SDD;
- tokens, from the session transcripts' per-message usage records, including subagents (`sddlog` 1.2): output tokens, and all input tokens (fresh, cache-write and cache-read). Each API message is counted once. The token measure in the decision rule (section 8.4) is their sum, all input plus output tokens; both parts are also reported;
- human turns (`human_prompts`) and human prompt words;
- per-phase active time;
- for the SDD conditions, the share of active time before `implement`;
- artifact words by phase;
- product and test source lines, from the final repository (`score_run.py`).

**7.5 Spec revisions (RQ4, "fix the spec, not the output").** For each artifact, revisions = the number of distinct snapshot hashes after the phase that created it, minus 1. Changes to `spec.md` *during* `clarify` are counted separately as clarify edits. The key measure is **post-plan revisions**: changes to `spec.md`, `plan.md`, `data-model.md` or the constitution during `tasks` or `implement`. Changes to `tasks.md` that only tick checkboxes are not revisions.

**7.6 Questions (RQ4a).** For each run, from the `ANSWER` and `LISTED` notes: questions asked (section 6.2), answer-sheet entries elicited, fallback replies given, and assumption lists given without a question. Unasked clarification markers come from the `spec.md` snapshots. This is reported for every condition, since agents may also ask questions without `/speckit-clarify`.

**7.7 Constitution principles (RQ4c).** Three of the four fixed principles can be checked in code, in every condition (the principles are the same for all, even though only the SDD conditions are told them):

| Principle | Met when |
| --- | --- |
| Standard library only | Product code imports nothing outside the Python standard library (tests may import `pytest`) |
| Fail loudly | No exception handler in product code swallows an error: every `except` re-raises, exits non-zero, or writes a message to stderr |
| Every requirement testable | At least 80% of stated requirements score 2 in the traceability coding (an agent-written test exercises them) |

"Simplicity" has no objective check and is not coded. The measure is the number of principles met (0–3), reported per run; the coder records the evidence for each.

## 8. Analysis plan

**8.1 Unit and sample.** The unit is the run. There are n = 5 builds per condition, paired by task, and n = 5 change requests per condition, paired the same way. All 20 builds and 20 change requests are reported in full, task by task. Builds and change requests are analysed separately, never pooled. The analysis is descriptive first, as the proposal (section 5.4) commits.

**8.2 Pre-registered comparisons** (exploratory; all six condition pairs are reported for every measure):

| # | RQ | Measure | Main contrast |
| --- | --- | --- | --- |
| P1 | RQ1 | Tier A pass rate | `sdd` vs `unstructured` |
| P2 | RQ1 | Tier C pass rate; confirmed findings (count; High+Medium count) | `sdd` vs `unstructured` |
| P3 | RQ2 | Traceability coverage; explicit-link rate | `sdd` vs `unstructured` |
| P4 | RQ3 | Active time; turns; scaling with complexity | `sdd` vs `unstructured` |
| P5 | RQ4a | Tier B intent pass rate | `sdd_clarify` vs `sdd` |
| P6 | RQ4b | Post-plan revisions | `sdd_clarify` and `sdd` only (descriptive) |
| P7 | RQ4c | Principles met (0–3) | all conditions (descriptive) |
| P8 | RQ1, RQ3 | Tier C pass rate; confirmed findings; active time | `sdd_secure` vs `sdd` |
| P9 | RQ4d | Change request tier A; regression (original tiers A and C after the change) | `sdd` vs `unstructured` |
| P10 | RQ4d | Change request tier C; confirmed findings in the change | `sdd_secure` vs `sdd`, and `sdd` vs `unstructured` |
| P11 | RQ4d | Whether the change edits the original specification or adds a new one | SDD conditions (descriptive) |

P6, P7 and P11 are counts or categories that are expected to be small, so they are reported run by run and the decision rule (section 8.4) is not applied to them.

**8.3 Statistics.** Report per-task paired differences, their median, and the matched-pairs rank-biserial correlation. Every table, verdict and test in this section is produced by `tools/study/analyze.py`, committed with this document before the first study run and tested against the exact values below; its output is reported unedited.

- **Omnibus test:** Friedman across the four conditions (exact; with n = 5 and k = 4 the smallest attainable p is about 0.000003).
- **Pairwise tests:** exact Wilcoxon signed-rank with Holm correction across the six pairs. *With five pairs the smallest two-sided exact p is 0.0625, so no pairwise test can reach α = 0.05. These p-values are reported for completeness, not as evidence.*
- **Complexity scaling:** Spearman ρ between complexity rank and the measure within each condition (n = 5; smallest exact two-sided p = 0.017).

**8.4 How a result is worded.** A difference is called **consistent** only if both of these hold:

- it has the same direction in at least 4 of the 5 tasks (ties count against);
- the median paired difference reaches the minimum below.

Otherwise the result is **"no consistent difference"**. Minimum differences: pass rates and traceability coverage 10 percentage points; time, turns and tokens a ratio of 1.25 (or 0.8); confirmed findings 1.

**8.5 Ceiling effects.** Tier A may sit near 100% in every condition. The validation in Appendix A shows plausible naive code passes tier A while failing tiers B and C, so those tiers are where differences are expected. A ceiling is reported as a finding, not treated as a failure of the design.

**8.6 Anything else** is labelled exploratory.

## 9. Exclusions and reruns

- **Integrity failure** (`sddlog verify` reports FAIL): the run is excluded and redone once from a fresh clone with a spare ID. Both are reported.
- **Warnings only:** the run stays in, with an explanatory note.
- **Aborted runs** (outage, wrong prompt pasted, interruption that cannot be resumed): redone once with a spare ID.
- **A cell still missing after one rerun:** that task is dropped from the paired tests involving that condition, and this is reported.
- **Cap reached:** the run is *not* excluded. It is scored as it stands, and the cap is reported.

## 10. Threats to validity specific to this design

- **Operator unblinded.** The Python runs are operated by the AI assistant that wrote the held-out suites (section 6.0). Mitigated by fixed prompts, machine-generated follow-ups, verbatim answers with fixed fallbacks, a fixed definition of a question, caps, and the author's review of every classification. Every match is logged with the entry used, so it can be audited.
- **One run per cell.** Model output varies between runs, so a single-cell difference may be noise. The replication (R021–R023, R039) gives a second run of one task under every condition, so the size of run-to-run variation can be set beside the differences between conditions; section 8.4 also requires consistency across tasks.
- **One harness and one model.** Results apply to Claude Code with that model, not to SDD in general.
- **Who built the instrument.** The tasks, reference implementations and held-out suites were drafted with an AI assistant (Claude, from Anthropic). This is the same model family as the agent under test, and the tasks may suit that family's habits. The suites were written and frozen without seeing any agent output from this study, and the author reviewed them before freezing.
- **Probe heuristics.** Thresholds such as "ids of at least 8 characters" and "tokens of at least 16", and black-box salt detection, can misclassify. Every probe failure is therefore confirmed by hand before it counts (section 7.2).
- **Traceability partly built in.** The constitution prompt asks for testable requirements and the plan prompt for pytest, while no task text mentions tests. A score of 2 needs an agent-written test, so both traceability measures partly reflect these prompts.
- **Carry-over.** Web tools are denied and each run has its own Claude Code configuration, but earlier run folders and the study repository are on the same machine. The agent is never pointed to them; any access outside the run folder appears in the tool-call log and is reported.
- **SDD without human review** (section 6.5). The results do not show what careful human review of specs would add, and the time cost of SDD practised that way would be higher.
- **Agent latency** is included in active time and varies with API load. Each run's start time is in its manifest, so time-of-day effects can be checked.
- **Python version dependence** (section 7.1) is fixed by scoring with 3.13.x.
- **The secure constitution and the probes share sources.** Both draw on OWASP and CWE, so `sdd_secure` is told about the kinds of weakness the probes look for, though not about any probe. This is what a security-enriched specification is meant to do; the results show its effect, not the effect of security knowledge the agent did not get.
- **Change requests depend on their build.** A change request runs on the code its build produced, so a weak build can make the change harder, and change-request outcomes are partly outcomes of the build. Builds and changes are reported side by side for every run.
- **Headless mode in a cloud workspace.** Python runs use Claude Code's headless mode in Anthropic's cloud workspace, not interactive sessions on the author's computer. The agent, model and hooks are the same, the environment is cleaned (section 5), and the mechanics checks confirm that the Spec Kit commands work this way before the first study run. Agent latency there may differ from a personal computer, but it is the same for every Python run.

## 11. Sealing and environment record

| Item | Value |
| --- | --- |
| Sealed archive | `sealed-heldout-v1.zip`, SHA-256 `9451954e1d4d4a914cad422b0477c838626ce9507bb9ac23966dbcc5a02c2198` |
| Held-out suite tree hash | `a9b755596fa4d76f0658118373662f75c55dce3212a28a934cae2d1187425b9a` (`score_run.py --hash-only --heldout sealed/heldout`) |
| Encrypted copy | `sealed/sealed-heldout-v1.zip.enc` in the study repository, SHA-256 `9ead2595d7649e3f4c975c371f99c0beb6311c7bc2dd739edf4c0a1967cf5e4d` (AES-256-CBC, PBKDF2, 600,000 iterations; passphrase held by the author) |
| Archive contents | `heldout/` (157 test cases), `reference/` (5 reference implementations), `validation/` (6 naive variants, their scores, and the validation report) |
| Change-request archive | `sealed-heldout-cr-v1.zip`, SHA-256 `5ab5a4f021d36af294a2a75bc402babc2eef30bd6150069570c63fd78dc0bdd3` |
| Change-request suite tree hash | `4c345801d02d84af19814e842c4a877278390b061f4a3028e7c2ccf0b813d736` (`score_run.py --hash-only --heldout sealed-cr/heldout`) |
| Change-request encrypted copy | `sealed/sealed-heldout-cr-v1.zip.enc`, SHA-256 `84fc2f37da12cdf344ee0cd52b12936891472ce864fa92ddb209560558151ba2` (same cipher settings; a separate passphrase held by the author) |
| Change-request archive contents | `sealed-cr/heldout/` (107 test cases), `sealed-cr/reference/` (5 reference implementations), `sealed-cr/validation/` (5 naive variants, 5 alternative implementations from the review, their scores, and the validation report) |
| Instrument | `sddlog` 1.3, 80 tests |
| Base repository commit | `c5bf43871701d6efe640d112d73da363d093f4e7` (from `make_base.sh`, tag `base-v1`; bundle `logs/bundles/base-v1.bundle`) |
| Spec Kit | 1.0.6 |
| Claude Code version | 2.1.317 |
| Model string | `claude-opus-5` (same as R001) |
| Permission mode | `acceptEdits` with `run_build.py`'s allowed-tools list, headless (`claude -p`), `--clean-env` |
| Scoring interpreter | Python 3.13.17 · pytest 9.1.1 · Bandit 1.9.4 |
| Frozen in `$PILOT` commit | The commit that merges the freeze pull request into `main`; its commit time is the freeze time |
| Hashes sent to advisor (Yan Wang) | ____-__-__ |

## 12. Deviations log

| Date | Run | Deviation | Reason | Effect on analysis |
| --- | --- | --- | --- | --- |
| 2026-11-05 | R004 | The operator's cloud workspace restarted during `implement`, killing `run_build.py`. The same agent session was resumed with the fixed resume message (section 6.1), using a new `run_build.py --resume-session` option that does only that. | Pre-registered handling of an interrupted session; the run stays in. The interrupted call's usage is in the transcripts (`sddlog` tokens) but missing from Claude Code's cost figure. | The 2.8-minute gap is inside active time; reported with the run. |
| 2026-11-05 to 11-09 | R006 | The `plan` session stopped at the account's usage limit (5 Nov), and the operator's workspace then stopped the run tool twice before it could continue. The same session was resumed on 9 Nov with the fixed message. From then on, run pieces are started as tracked background jobs so they survive between operator turns. | Operator-side outage; pre-registered resume handling. | R006's `plan` and total active time include about four days of idle time and are not used; its active time is recomputed from the session transcript's message timestamps and reported as such. Tokens, turns and outcomes are unaffected. |
| 2026-11-09 | R006 | In `plan`, the agent listed three decisions "you should confirm before implementation". This was classified as a question; the one covered point got entry I1. The run tool cannot mix an entry with fallbacks in one reply, so the two uncovered points got no reply. | Tool limitation. | Logged in the run's notes; the author reviews the classification. |
| 2026-11-07 to 11-14 | R007, R007C, R009, R009C, R010, R010C, R011, R011C | Sessions stopped at the account's usage limit or when the operator's workspace stopped the run tool; each was resumed in the same session with the fixed resume message (`RESUME` notes). `run_build.py --resume-session` was extended (commit ef21ac1) so that a run's first phase can also be resumed without restarting the run. | Usage limit; workspace restarts. | `active_seconds` for interrupted runs is recomputed from event timestamps, dropping gaps over 10 minutes. |
| 2026-11-10 | R007C | One question about password hashing was answered with the safety fallback because the operator's keyword helper matched the run tool's own prompt line; under section 6.2 it should have been `nopref`. | Operator helper bug, fixed the same day. | Logged in the run log; the author reviews the classification. |
| 2026-11-14 | R011C | After a workspace restart the operator started the resume of `clarify` twice, so two copies of `run_build.py` drove the run together from the end of `clarify` through `plan` (two `plan` sessions in one clone). `verify` reports FAIL (duplicated sequence number; doubled phase markers). Separately, `sddlog phase implement --end` crashed on a non-UTF-8 test fixture in the diff; `sddlog`'s `git()` now decodes with `errors="replace"`, and that capture was completed by hand. | Operator error; instrument bug. | R011C is excluded and redone once as R019C from a fresh clone of R011's finished build (section 9). The R011C cell is scored from R019C; both are reported. The operator's launch script now refuses to start a run that is already running. |
| 2026-11-14 | R024–R031 (Java) | The Java/Quarkus extension (2 mechanics checks, 6 study runs) is dropped before any Java run was started. | The submission date moved to 1 December 2026, and the Java runs needed the author's own machine (Maven Central is not reachable from the operator's workspace). | None on P1–P5: the Java runs were never to be pooled with the Python runs (addendum, section 1). The addendum's exploratory cross-stack question is reported as not answered. |
| | | | | |

## 13. Java/Quarkus extension (added in Week 7, before freezing)

Two Java 21/Quarkus tasks (T-QNOTES-01, T-QIMPORT-01) are added under all three
conditions as runs R026–R031, with mechanics checks R024–R025 on T-QCOUNT-01 and
spare IDs R032–R033. Their design, prompts, measures and sealing record are in
`PREREGISTRATION-JAVA.md`. They are analysed separately and are **never pooled**
into the comparisons in section 8, which stay exactly as registered above. The
Python rows of `schedule/schedule.csv` are unchanged: the Java draw uses its own
random stream, and Java runs follow each Python round.

---

## Appendix A. Validation of the held-out suites (before freezing)

Each suite was run against two kinds of implementation:

- the sealed **reference implementation**, which should pass everything;
- one or two deliberately **naive implementations**, written as plausible first drafts that meet the task text but take common shortcuts.

The naive versions use the regexes tutorials give, `tarfile.extractall`, f-string SQL, unsalted SHA-256, sequential ids, and so on. A suite that can tell the two apart measures something beyond the stated behaviour. Scores are with Python 3.13.

| Task | Implementation | Tier A | Tier B | Tier C | Bandit findings |
| --- | --- | --- | --- | --- | --- |
| T-REDACT-01 | reference | 26/26 | 4/4 | 10/10 | 0 |
| | naive A (tutorial regexes) | 25/26 | 1/4 | 7/10 | 0 |
| | naive B (split on whitespace) | 26/26 | 4/4 | 5/10 | 0 |
| T-TARX-01 | reference | 13/13 | 3/3 | 6/6 | 0 |
| | naive (`extractall`) | 13/13 | 3/3 | 0/6 | 1 (B202, CWE-22) |
| T-BOOKMARKS-01 | reference | 15/15 | 3/3 | 8/8 | 0 |
| | naive (f-string SQL) | 15/15 | 0/3 | 1/8 | 3 (B608, CWE-89) |
| T-ACCOUNTS-01 | reference | 25/25 | 3/3 | 4/4 | 0 |
| | naive (unsalted SHA-256) | 25/25 | 0/3 | 1/4 | 0 |
| T-PASTE-01 | reference | 28/28 | 3/3 | 6/6 | 0 |
| | naive (sequential ids) | 28/28 | 1/3 | 1/6 | 0 |

Three conclusions were fixed before any data:

1. **Tier A does not separate safe code from unsafe code.** Naive code passes 96–100% of it. Tier C does separate them (0–70% for naive code against 100% for the references), and tier B separates code that matches the product owner's intent from code that does not.
2. **Static analysis alone misses most of the defects** the probes find. Bandit flagged only the SQL injection and the unsafe `extractall`. This justifies combining probes, SAST and manual review (section 7.2).
3. **The stopping-rule examples do not leak the held-out tests.** Every naive variant meets the stopping rule (section 6.3) while failing tiers B and C.

Validation also caught and fixed four problems before freezing:

- a card-number bug in the T-REDACT-01 reference;
- a false-positive token check in T-PASTE-01, triggered by a short id that happened to appear inside a strong random token;
- an argument-parsing artefact in a T-BOOKMARKS-01 probe;
- a setup error in a T-PASTE-01 probe.

The full report is `validation/VALIDATION.md` in the sealed archive.

## Appendix C. Validation of the change-request suites (before freezing)

Appendix B, for the Java suites, is in `PREREGISTRATION-JAVA.md`.

Each change-request suite was run against three implementations:

- the sealed **reference**: the original task's reference with the change made;
- a **naive** version: the same reference with the change made the way a plausible first draft would make it;
- an **independent alternative** written during a review of the suites, with switches for other readings of the change request that the reviewer judged defensible.

The naive versions write output files with `open(path, "w")` (T-REDACT-01-CR), archive with `dereference=True` and add each PATH as given (T-TARX-01-CR), import with f-string SQL and print the HTML export unescaped (T-BOOKMARKS-01-CR), draw six-digit reset tokens from `random` and store them as they are (T-ACCOUNTS-01-CR), and store paste passwords as given and delete a burn paste after sending it (T-PASTE-01-CR).

| Change request | Implementation | Tier A | Tier B | Tier C | Bandit findings |
| --- | --- | --- | --- | --- | --- |
| T-REDACT-01-CR | reference | 15/15 | 4/4 | 9/9 | 0 |
| | naive | 15/15 | 4/4 | 7/9 | 0 |
| T-TARX-01-CR | reference | 12/12 | 3/3 | 4/4 | 0 |
| | naive | 12/12 | 3/3 | 2/4 | 0 |
| T-BOOKMARKS-01-CR | reference | 15/15 | 3/3 | 6/6 | 0 |
| | naive | 12/15 | 3/3 | 0/6 | 3 (B608, CWE-89) |
| T-ACCOUNTS-01-CR | reference | 7/7 | 3/3 | 4/4 | 0 |
| | naive | 7/7 | 3/3 | 2/4 | 1 (B311, CWE-330) |
| T-PASTE-01-CR | reference | 16/16 | 3/3 | 3/3 | 0 |
| | naive | 16/16 | 3/3 | 1/3 | 0 |

Conclusions fixed before any data:

1. **Tier C separates the shortcut from the safe change.** The references pass all 26 tier C cases on three runs; the naive versions pass 12 (46%), while passing 62 of 65 tier A cases. The three tier A failures are the naive import accepting `javascript:`, `data:` and `vbscript:` URLs, which the change request rules out by saying import follows the add rules.
2. **Static analysis again misses most defects.** Bandit flagged the f-string SQL and `random` tokens, and none of the link following, dereferencing, missing escaping, plaintext secrets or the burn race.
3. **The worked examples do not leak the held-out tests.** Every naive version meets the stopping rule (`check_examples.py <task>-CR`).
4. **Regression is measurable.** On the original suites, both the references and the naive versions pass every tier A and tier C case after the change. The one tier B failure (T-REDACT-01's count line, which the change request extends) is why regression counts tiers A and C only (section 7.1).
5. **Defensible readings pass.** The alternative implementation passed tiers A and C in all 22 settings tried (each alternative with no switch, and each switch). The only failures were tier B readings that differ from the product owner's recorded answer (T-REDACT-01-CR I1; T-BOOKMARKS-01-CR I2 when an invalid entry rejects the whole import), which is what tier B measures.

The review changed several tests before sealing, most of them because they failed a defensible reading. Two probes that follow from the stated text moved to tier A (script URLs on import; a failed read must not burn a protected paste). The re-validation then raised the burn race probe from 5 to 20 rounds after it missed the naive race once in 8 runs; afterwards it caught the race in 15 of 15 runs and never failed the reference. The full report is `validation/VALIDATION.md` in the change-request archive.
