# Runbook: Weeks 5–7 data collection

Step-by-step operator procedure for every run in `schedule/schedule.csv`. The
rules behind each step are in `PREREGISTRATION.md`; this file is the
checklist to follow with the terminal open. Paths below assume:

| Name | Path (example) | What it is |
| --- | --- | --- |
| `$PILOT` | `~/CPT-Peng/sdd-pilot` | the study repository: dataset, documents and study tools |
| `$KIT` | same as `$PILOT` | the study materials now live in the study repository |
| `$BASE` | `~/sdd-study/base` | base repository built in step 0.5 |
| run dirs | `~/sdd-study/runs/R0NN` | one fresh clone per run |

The sealed suite is in the repository only as `sealed/sealed-heldout-v1.zip.enc`. Keep it **encrypted**, and keep any decrypted copy closed, until all study runs are finished.

---

## 0. One-time setup (before R002)

1. **Set `KIT=$PILOT`.** The study materials are in the study repository. Runs happen in separate clones of `$BASE` outside it, so an agent never sees the answer sheets. Keep `sealed-heldout-v1.zip` outside every repository.
2. **Confirm the instrument** (`sddlog` 1.3 is already in the repository):
   ```bash
   cd $PILOT
   python3 -m pytest tools/sddlog/tests -q          # expect: 80 passed
   ```
3. **Freeze the pre-registration.** Fill in the blanks in section 11 of `docs/PREREGISTRATION.md` (versions, base commit). Then commit on `main`. The commit time is the pre-registration date:
   ```bash
   git add -A && git commit -m "Pre-register Weeks 5-7 study (protocol 1.1)"
   ```
   Email the two hashes in section 11 to your advisor before R004. That gives an outside timestamp that the held-out tests existed before any data.
4. **Pin the tools** and note the versions in section 11:
   - Spec Kit: `specify --version` must print `1.0.6`, the version used for R001.
   - Claude Code: `claude --version`. Do not update it until the last study run.
   - Model: the same model string as R001 (`claude-opus-5` in R001's manifest).
   - Scoring interpreter: Python 3.13.x, used only in Part III (see section 7.1 of the pre-registration).
5. **Build the base repository** (instrument + hooks, no Spec Kit, web tools denied):
   ```bash
   bash $KIT/tools/study/make_base.sh $PILOT $KIT $BASE
   ```
   Record the printed commit hash in section 11. Its `.claude/settings.json` must list `WebFetch` and `WebSearch` under `permissions.deny`.
6. **Claude Code settings for the whole study.** Use the same permission mode as R001 for every run. Remove anything that would differ between runs or carry over between them: move `~/.claude/CLAUDE.md` aside if you have one, and add no MCP servers, plugins or user skills. Each run happens in a new directory, so project memory starts empty.

---

## The usual way: the run tool

Every study run is driven by `tools/study/run_build.py` (pre-registration
section 5). It sends every fixed prompt to Claude Code in headless mode, runs
the stopping-rule check and the follow-ups, writes all the `sddlog` markers and
notes, and commits the clone at the end. Your only job is to read each agent
turn it shows you and type what it is:

| You type | When the agent's turn... | The tool sends |
| --- | --- | --- |
| `I2` (or `I1,I3`; `orig:I2` for the original task's sheet in a change request) | asks something an answer-sheet entry covers | that entry's reply, verbatim |
| `safety` | asks an uncovered safety question | the safety fallback |
| `nopref` | asks any other uncovered question | the no-preference fallback |
| `permit` | asks for permission to continue | `Yes, go ahead.` |
| `listed` | lists assumptions or review items but asks nothing | nothing (logs a `LISTED` note) |
| `done` | says it has finished | nothing; in `implement` it runs the checker |

```bash
RUN=R004                                     # the next row of schedule/schedule.csv
git clone -q $BASE ~/sdd-study/runs/$RUN
cd ~/sdd-study/runs/$RUN
git checkout -q -b run/$RUN base-v1
python3 $KIT/tools/study/run_build.py $RUN   # adds Spec Kit itself for SDD conditions
python3 $KIT/tools/study/run_build.py ${RUN}C   # then the change request, same clone
```

Then archive each (step 4). If the session stops with an error (a usage limit,
say), the tool asks whether to resume it with the fixed resume message.

### Python runs in the cloud workspace (from Week 8)

The Python runs are operated by Claude in Anthropic's cloud workspace
(pre-registration section 6.0). Two options keep them clean and within that
workspace's limits:

- `--clean-env DIR` gives every `claude -p` call a minimal environment and a new
  Claude Code configuration folder `DIR/<run id>`, so no user skills, plugins,
  hooks, MCP servers or host tools reach the agent.
- `--stop-after PHASE` leaves a run open after a phase, and `--start-at PHASE`
  continues it, so a long SDD run can be driven in pieces of at most two hours.
  Every phase is a fresh session anyway, so nothing else changes.

```bash
python3 $KIT/tools/study/run_build.py R005 --clean-env ~/sdd-study/claude-configs --stop-after plan
python3 $KIT/tools/study/run_build.py R005 --clean-env ~/sdd-study/claude-configs --start-at tasks
```

The operator's choices are read from standard input as usual, so they can be
fed one line at a time; each choice and the agent message it answered are kept
in the run's notes and `headless/` logs for the author's review. The
manual steps below do the same thing by hand; use them only if the
mechanics checks show that headless mode cannot run the Spec Kit commands.

## 1. Start a run (every condition)

Take the next row of `schedule/schedule.csv`:

```bash
RUN=R004 TASK=T-ACCOUNTS-01 COND=sdd        # from the schedule
git clone -q $BASE ~/sdd-study/runs/$RUN
cd ~/sdd-study/runs/$RUN
git checkout -q -b run/$RUN base-v1
```

**`sdd`, `sdd_clarify` and `sdd_secure` only:** add Spec Kit as one setup commit:
```bash
specify init --here --force --integration claude --extension git --non-interactive --script sh
git add -A && git commit -qm "condition setup: Spec Kit 1.0.6"
```

**`unstructured` only:** confirm Spec Kit is absent. `ls .claude` must show only `settings.json`, and `.specify/` must not exist.

**Every condition:**
```bash
L="python3 tools/sddlog/sddlog.py"
$L run-start --run-id $RUN --task $TASK --condition $COND --model claude-opus-5
$L note --text "env: claude $(claude --version) | $(specify --version 2>/dev/null || echo 'no spec kit') | $(python3 --version) | permission mode: <same as R001>"
```

Open `$KIT/operator/answer-sheets/$TASK.md` in a second window. Keep a second terminal in the run directory for the checks in step 3.

---

## 2a. `sdd`, `sdd_clarify` and `sdd_secure`

(`sdd_secure` sends `prompts/constitution-secure.txt` in the constitution phase; everything else is as for `sdd`.)

Run each phase in a **fresh** Claude Code session, as in R001:

```bash
$L phase constitution --start
claude --model claude-opus-5
#   send prompts/constitution.txt exactly; wait for the agent to finish; /exit
$L phase constitution --end
```

| Phase | Message to send (see `prompts/README.md`) |
| --- | --- |
| `constitution` | `prompts/constitution.txt` |
| `specify` | `/speckit-specify ` followed by `tasks/$TASK/prompt.md`, pasted as **one** message |
| `clarify` (`sdd_clarify` only) | `/speckit-clarify`, then answer each question from the answer sheet |
| `plan` | `prompts/plan.txt` |
| `tasks` | `/speckit-tasks` |
| `implement` | `/speckit-implement`, then the stopping-rule loop (step 3) **in the same session, with the phase still open** |

- Close each phase marker as soon as the agent finishes, before doing anything else (protocol section 7.4).
- Do not open, read or edit the generated artifacts unless you need to in order to answer a question. The pre-registration explains why (section 6.5).

## 2b. `unstructured`

```bash
$L phase implement --start
claude --model claude-opus-5
#   send tasks/$TASK/prompt.md as one message, then the stopping-rule loop (step 3)
```

---

## 3. Stopping-rule loop (every condition, inside the `implement` phase)

Each time the agent's turn ends:

1. **It asked a question?** Answer from the answer sheet, verbatim (`operator/answer-sheets/README.md`), and log it:
   `$L note --text "ANSWER I2: <question, shortened>"`
2. **It asked permission to continue** ("Shall I proceed?", "Want me to implement it?")? Send exactly `Yes, go ahead.`
   **It listed assumptions or review items but asked nothing?** Send nothing; log `$L note --text "LISTED: <shortened>"` and treat the turn as finished (item 3).
3. **Otherwise, it says it is done.** In the second terminal:
   ```bash
   python3 $KIT/tools/study/check_examples.py $TASK --repo .
   ```
   - **All examples pass:** the run is done. Go to step 4.
   - **Some fail:** paste the printed follow-up message **verbatim**, then repeat this loop.
4. **Caps:** stop after **5** follow-up messages from the checker, or **90 minutes** after the `implement` phase opened, whichever comes first. Then:
   `$L note --text "CAP REACHED: <which cap>; examples still failing: <list>"`

Never type anything else. Never fix code yourself. Never run or open the held-out tests.

---

## 4. Close and archive the run

```bash
$L phase implement --end
$L run-end --status completed
$L verify --run-id $RUN                       # must print OK; explain any WARN with a note
git add -A && git -c user.name=operator -c user.email=operator@localhost commit -qm "run $RUN closed"
mkdir -p ~/sdd-study/bundles && git bundle create ~/sdd-study/bundles/$RUN.bundle --all
cp -r logs/runs/$RUN $PILOT/logs/runs/
```

Add a line to `schedule/run-log.md` in `$PILOT`. **Keep the run directory**: Part III scores it. In the cloud workspace, whose folders do not last, also copy the bundle into the repository (`cp ~/sdd-study/bundles/$RUN.bundle $PILOT/logs/bundles/`): Part III then scores a clone of the bundle.

---

## 5. When something goes wrong (pre-registered handling)

| Situation | Action |
| --- | --- |
| `verify` reports **FAIL** | The run is invalid. Keep its logs, mark it `excluded` in the run log, and redo it from a fresh clone with the next spare ID (R019, then R020). |
| `verify` reports **WARN** | Write a `note` explaining it. The run stays in the dataset. |
| Agent or API outage, usage limit, crash, or an interruption of more than 10 minutes mid-phase | Write a `note`. If the same session can be resumed, resume it and send exactly `Please continue from where you stopped.`, then `$L note --text "RESUME: <reason>"`. If the phase can carry on in a new session, carry on. Otherwise `run-end --status aborted` and redo with a spare ID. |
| Wrong text pasted, typo in a fixed prompt | Write a `note` at once. If the agent already acted on it, abort and redo with a spare ID. |
| A phase marker was closed late | Already handled by `active_seconds`. Write a `note` as in R001. |

Every one of these also goes into the deviations log, section 12 of `PREREGISTRATION.md`.

---

## 5b. Change requests (`<build ID>C`)

A change request runs in the build's clone, right after the build is archived,
under the same condition, as run `${RUN}C` (for example R004C):

- `sddlog run-start` gets `--stage change` and the task `<task>-CR`.
- SDD conditions start at `specify`, with `/speckit-specify ` followed by `tasks/<task>-CR/prompt.md`; the constitution phase is skipped, because the build's constitution stays in place.
- `unstructured` sends `tasks/<task>-CR/prompt.md` as one message in a new session.
- The stopping rule is `check_examples.py <task>-CR`, which runs the original task's examples and then the change request's.
- Answer from `operator/answer-sheets/<task>-CR.md`; the original task's sheet still applies to behaviour the change request does not touch.

`run_build.py ${RUN}C` does all of this.

## 6. After the last study run: start of Part III

1. **Unseal both archives.** Decrypt them, unzip them next to the kit and check they are the frozen versions (full steps in `sealed/README.md`):
   ```bash
   openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -in sealed/sealed-heldout-v1.zip.enc -out sealed-heldout-v1.zip
   openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -in sealed/sealed-heldout-cr-v1.zip.enc -out sealed-heldout-cr-v1.zip
   sha256sum sealed-heldout-v1.zip sealed-heldout-cr-v1.zip                       # must equal section 11
   unzip -n sealed-heldout-v1.zip && unzip -n sealed-heldout-cr-v1.zip             # -n keeps sealed/README.md
   python3 $KIT/tools/study/score_run.py --hash-only --heldout sealed/heldout      # must equal section 11
   python3 $KIT/tools/study/score_run.py --hash-only --heldout sealed-cr/heldout   # must equal section 11
   ```
2. **Score every build at the commit that closed it.** The clone now holds the code after its change request, so the build is scored from its own closing commit (`run R004 closed`), checked out separately. Use the pre-registered interpreter (install `pytest` and `bandit==1.9.4` for it first):
   ```bash
   cd ~/sdd-study/runs/$RUN
   BUILD=$(git log --format=%H --grep "^run $RUN closed$" -1)
   git worktree add -f ~/sdd-study/scoring/$RUN $BUILD
   python3.13 $KIT/tools/study/score_run.py --task $TASK --repo ~/sdd-study/scoring/$RUN \
       --run-id $RUN --heldout sealed/heldout --sast --out $PILOT/scores/$RUN.json
   ```
3. **Score every change request twice**, on the clone as it stands: on its own suite, and on the original task's suite for regression:
   ```bash
   python3.13 $KIT/tools/study/score_run.py --task $TASK-CR --repo ~/sdd-study/runs/$RUN \
       --run-id ${RUN}C --heldout sealed-cr/heldout --sast --out $PILOT/scores/${RUN}C.json
   python3.13 $KIT/tools/study/score_run.py --task $TASK --repo ~/sdd-study/runs/$RUN \
       --run-id ${RUN}C-regression --heldout sealed/heldout --out $PILOT/scores/${RUN}C-regression.json
   ```
4. **Coding sheets** for the manual coding (pre-registration section 7):
   ```bash
   python3 $KIT/tools/study/make_coding_sheets.py $RUN --score $PILOT/scores/$RUN.json
   python3 $KIT/tools/study/make_coding_sheets.py ${RUN}C --score $PILOT/scores/${RUN}C.json
   ```

---

## 7. Java/Quarkus runs (R024–R033)

Everything above applies, with these differences. The design is in
`PREREGISTRATION-JAVA.md`.

**7.0 One-time setup (before R024).**

1. Install a Java 21 JDK and check `java -version`. Record the full version in
   section 9 of `PREREGISTRATION-JAVA.md`, and keep it for every Java run and for scoring.
2. Build the Java base next to the Python one:
   ```bash
   bash $KIT/tools/study/make_base_java.sh $PILOT $KIT ~/sdd-study/base-java
   (cd ~/sdd-study/base-java && ./mvnw -q -B -DskipTests package && ls target/quarkus-app/quarkus-run.jar)
   (cd ~/sdd-study/base-java && git clean -qfdx)    # remove the test build output again
   ```
   Record the printed `base-java-v1` commit in section 9 of `PREREGISTRATION-JAVA.md`.
   The first build downloads Maven and Quarkus into `~/.m2`; later builds reuse that cache.
3. Fetch the static-analysis jars used in scoring: `bash $KIT/tools/study/java-sast/fetch.sh`.

**7.1 Start a run.** As in step 1, but clone the Java base and check out its tag:
```bash
RUN=R026 TASK=T-QNOTES-01 COND=unstructured     # from the schedule
git clone -q ~/sdd-study/base-java ~/sdd-study/runs/$RUN
cd ~/sdd-study/runs/$RUN
git checkout -q -b run/$RUN base-java-v1
```
The Spec Kit setup commit (SDD conditions) and `run-start` are exactly as in step 1.
Add the JDK to the environment note:
`$L note --text "env: claude $(claude --version) | $(specify --version 2>/dev/null || echo 'no spec kit') | $(java -version 2>&1 | head -1) | permission mode: <same as R001>"`

**7.2 Prompts.** In the SDD conditions, send `prompts/constitution-java.txt` and
`prompts/plan-java.txt` instead of the Python versions. Every other message is
as in steps 2a, 2b and 3 (the task's `prompt.md`, `/speckit-*` commands, checker
follow-ups, answer-sheet replies, `Yes, go ahead.`).

**7.3 Stopping rule.** Run the checker exactly as before:
```bash
python3 $KIT/tools/study/check_examples.py $TASK --repo .
```
For a Quarkus task it first builds the repository (`./mvnw -q -B -DskipTests clean package`,
up to a few minutes) and then starts the service on a free port. A failed build
prints a follow-up starting "the build failed"; paste it verbatim like any other.
The caps (5 follow-ups, 90 minutes) are unchanged.

**7.4 Close and archive.** As in step 4. `target/` is git-ignored, so it is not
in the bundle; Part III rebuilds every run from its committed sources.

**7.5 Scoring (Part III).** Unseal `sealed-heldout-java-v1.zip.enc` the same way
as the Python archive (`sealed/README.md`), then:
```bash
python3.13 $KIT/tools/study/score_run.py --task $TASK --repo ~/sdd-study/runs/$RUN \
    --run-id $RUN --heldout sealed/heldout-java --sast --out $PILOT/scores/$RUN.json
python3 $KIT/tools/study/make_coding_sheets.py $RUN --score $PILOT/scores/$RUN.json
```
The scorer runs `./mvnw -q -B -DskipTests clean package` once, then the three
tiers, then SpotBugs + FindSecBugs over `target/classes`.
