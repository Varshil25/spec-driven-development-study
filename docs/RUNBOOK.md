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

Keep `sealed-heldout-v1.zip` **closed** until all study runs are finished.

---

## 0. One-time setup (before R002)

1. **Set `KIT=$PILOT`.** The study materials are in the study repository. Runs happen in separate clones of `$BASE` outside it, so an agent never sees the answer sheets. Keep `sealed-heldout-v1.zip` outside every repository.
2. **Confirm the instrument** (`sddlog` 1.1 is already in the repository):
   ```bash
   cd $PILOT
   python3 -m pytest tools/sddlog/tests -q          # expect: 67 passed
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

## 1. Start a run (every condition)

Take the next row of `schedule/schedule.csv`:

```bash
RUN=R004 TASK=T-ACCOUNTS-01 COND=sdd        # from the schedule
git clone -q $BASE ~/sdd-study/runs/$RUN
cd ~/sdd-study/runs/$RUN
git checkout -q -b run/$RUN base-v1
```

**`sdd` and `sdd_clarify` only:** add Spec Kit as one setup commit:
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

## 2a. `sdd` and `sdd_clarify`

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

Add a line to `schedule/run-log.md` in `$PILOT`. **Keep the run directory**: Part III scores it.

---

## 5. When something goes wrong (pre-registered handling)

| Situation | Action |
| --- | --- |
| `verify` reports **FAIL** | The run is invalid. Keep its logs, mark it `excluded` in the run log, and redo it from a fresh clone with the next spare ID (R019, then R020). |
| `verify` reports **WARN** | Write a `note` explaining it. The run stays in the dataset. |
| Agent or API outage, crash, or an interruption of more than 10 minutes mid-phase | Write a `note`. If the phase can carry on in a new session, carry on. Otherwise `run-end --status aborted` and redo with a spare ID. |
| Wrong text pasted, typo in a fixed prompt | Write a `note` at once. If the agent already acted on it, abort and redo with a spare ID. |
| A phase marker was closed late | Already handled by `active_seconds`. Write a `note` as in R001. |

Every one of these also goes into the deviations log, section 12 of `PREREGISTRATION.md`.

---

## 6. After the last study run: start of Part III

1. **Unseal.** Unzip `sealed-heldout-v1.zip` next to the kit and check it is the frozen version:
   ```bash
   python3 $KIT/tools/study/score_run.py --hash-only --heldout sealed/heldout   # must equal section 11
   ```
2. **Score** every run with the pre-registered interpreter (install `pytest` and `bandit==1.9.4` for it first):
   ```bash
   python3.13 $KIT/tools/study/score_run.py --task $TASK --repo ~/sdd-study/runs/$RUN \
       --run-id $RUN --heldout sealed/heldout --sast --out $PILOT/scores/$RUN.json
   ```
3. **Coding sheets** for the manual coding (pre-registration section 7):
   ```bash
   python3 $KIT/tools/study/make_coding_sheets.py $RUN --score $PILOT/scores/$RUN.json
   ```
