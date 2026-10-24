# T-LOGIN-01 demo: unstructured vs. SDD

A practice comparison, **excluded from the study**. Both builds came from
subagents in Claude's own workspace, not from Claude Code with the study's hooks
and model, so the numbers show the method working, not study data.

## Setup

| | D001 unstructured | D002 SDD (Spec Kit 1.0.6) |
| --- | --- | --- |
| Task text | Identical 405-word description (stdlib login page, HS256 JWT, 30-minute session) | Same text, sent via `/speckit-specify` |
| Agents | 1 fresh agent | 5 fresh agents, one per phase: constitution, specify, plan, tasks, implement |
| Repository | Base only, no Spec Kit | Base + one Spec Kit setup commit |
| Questions answered | From the answer sheet, verbatim | Same |

The held-out suite (41 checks) was frozen before either agent ran, with tree
hash `556cc26c…66dd44`. It was encrypted while the agents worked and
re-verified before scoring.

## Results

| Measure | D001 unstructured | D002 SDD |
| --- | --- | --- |
| Stopping rule (task examples) | Met on 1st check, 0 follow-ups | Met on 1st check, 0 follow-ups |
| **Tier A**, stated behaviour | **22/22** | **22/22** |
| **Tier B**, intended behaviour | **1/4** | **2/4** |
| **Tier C**, security probes | **15/15** | **15/15** |
| Bandit | 1 Low (B105), false positive | 1 Low (B105), false positive |
| Confirmed security findings | 0 | 0 |
| Tests citing a requirement ID | 0 of 72 | 90 of 90 (all 32 FRs) |
| Product / test source lines | 612 / 549 | 518 / 1,458 |
| Questions the agent asked | 0 | 2 (in specify) |
| Human turns | 1 | 7 (5 phase prompts, 1 answer, 1 outage resume) |
| Agent working time | 23.5 min | about 160 min (+ up to 12 min unrecorded, see below) |
| Agent tokens | 118k | about 945k |
| Agent tool calls | 45 | 285 |
| Spec documents written | none | 27,891 words across 7 documents |
| Spec revisions after the plan phase | n/a | **0** (`tasks.md` changed only by ticking 56 checkboxes) |

**Tier B in detail:**

| Check | D001 | D002 | Why |
| --- | --- | --- | --- |
| I1 lockout: 5 failures, 15 min, same 401 | Fail | **Pass** | SDD asked. Unstructured guessed: 10 failures, 429 response |
| I2 logout revokes the copied token | Pass | Pass | SDD asked. Unstructured chose the same answer unprompted |
| I3 usernames case-insensitive | Fail | Fail | Neither asked; both made usernames case-sensitive |
| I4 `/login` redirects when logged in | Fail | Fail | Neither asked |

**SDD time by phase:**

| Phase | Time | Tokens |
| --- | --- | --- |
| constitution | 4.2 min | 92k |
| specify | 22.9 min | 189k |
| plan | 102.2 min | 166k |
| tasks | 1.8 min after the outage, up to 12 min before | 183k + unrecorded |
| implement | 28.6 min | 315k |

The plan phase alone took 4× the whole unstructured build, because the agent
ran its own experiments to settle the design. The four phases before implement took over
80% of SDD time; the pilot's figure was 74%.

## Reading it

- **On what was asked for, there's no difference.** Both builds pass every stated requirement and every security probe, including forged and `alg: none` tokens, cookie flags, salted hashing, enumeration, XSS, open redirect and oversized bodies. With "secure" in the prompt and a capable model, the unstructured build was already secure on everything probed.
- **SDD's only correctness gain came from asking.** It scored 2/4 on intended behaviour against 1/4, but the only extra point (I1) came from a question it asked and got answered. Both missed the two points neither agent asked about. That is weak evidence for the pilot's hypothesis that the benefit lives in the clarifying step, not in writing specs as such.
- **Traceability is where SDD clearly differs.** Every SDD test names the requirement it checks; the unstructured tests name none. SDD also wrote about 2.7× as much test code.
- **The price is large.** SDD took about 7× the agent time, 8× the tokens and 6× the human turns (excluding the outage resume), plus nearly 28,000 words of documents nobody read.
- **"Fix the spec, not the output" again did not happen.** No upstream artifact changed after creation, as in R001.

## Caveats

- **n = 1 per condition**, with a different harness and model from the study's. One run can't separate method from luck.
- **The SDD run was interrupted once** by an API session limit in the tasks phase. The same agent was resumed the next morning, and this is logged as a deviation. Its first turn has no usage record; timestamps cap it at about 12 minutes.
- **Clock time comes from agent usage records**, because subagents don't fire Claude Code hooks (the `active_seconds` warning in both runs).
- **The tests and reference implementation were written by me**, the same model family as the agents under test.

## Rubric correction found here

The pre-registration (section 7.2) accepted scrypt only at N ≥ 2¹⁷, r = 8,
p = 1, but OWASP also lists equivalent settings (2¹⁶/8/2, 2¹⁵/8/3, 2¹⁴/8/5,
2¹³/8/10). D001 uses 2¹⁴/8/5, which is acceptable. The rule now reads "meets
an OWASP Password Storage configuration"; the change was made before the
pre-registration was frozen.
