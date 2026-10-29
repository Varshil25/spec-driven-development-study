# Logging Protocol

**Study**: Evaluating and Extending Spec-Driven Development (Parts II–III)
**Protocol version**: 1.2
**Status**: 1.0 ratified at Milestone 2; 1.2 governs data collection from Week 7
**Instrument**: `tools/sddlog/sddlog.py` (stdlib-only Python, 73 automated tests)

---

## 1. Purpose and scope

This protocol governs how prompts, edits, and outputs are recorded for every
task run in the software strand of the study. It exists so that the three
conditions (unstructured prompting, SDD, and SDD with clarification) are
measured by an identical instrument, and so that any number reported in
Part III can be traced back to a timestamped, tamper-evident event in a
specific run log.

It covers data **capture** only. Defect coding, static analysis, and
traceability coding are downstream activities performed on the artifacts this
protocol collects. They are defined in `PREREGISTRATION.md`, section 7.

## 2. Unit of analysis: the run

A **run** is one execution of one task, under one condition, by one operator,
with one agent and model. Runs are the rows of the eventual dataset.

| Field | Meaning | Example |
| --- | --- | --- |
| `run_id` | Identifier assigned by the schedule and passed with `--run-id` | `R004` |
| `task_id` | Stable identifier for the programming task | `T-ACCOUNTS-01` |
| `condition` | `unstructured`, `sdd` or `sdd_clarify`: the manipulated variable | `sdd` |
| `model` | Underlying LLM, held constant across the study | `claude-opus-5` |
| `agent` | Agent harness | `claude-code` |
| `operator` | Person driving the session | `varshil` |
| `start_commit` | Repository state the run began from | `83bc4eb` |

Every run starts in its own fresh clone of one **base repository** (tag
`base-v1`; see `RUNBOOK.md`), which holds only the instrument and its hooks.
The two SDD conditions add exactly one setup commit (Spec Kit scaffolding)
before `run-start`. That commit is the manipulated variable, and the
unstructured condition never sees Spec Kit. Because each run lives in its own
clone, run IDs are assigned in advance by `schedule/schedule.csv` rather than
counted from the local `logs/` directory. All runs use the same model and
agent. Condition order is counterbalanced across tasks (`PREREGISTRATION.md`,
section 3).

## 3. Capture architecture

Three independent paths record the run. They overlap deliberately: no single
misconfiguration can silently produce an empty or misleading dataset entry.

| # | Path | Mechanism | Captures | Authority |
| --- | --- | --- | --- | --- |
| 1 | Agent hooks | Claude Code `SessionStart` / `UserPromptSubmit` / `PostToolUse` / `Stop` → `sddlog hook` | Prompt text, tool calls, per-edit line deltas, session boundaries | Primary for **prompts** and **turns** |
| 2 | Git phase capture | `sddlog phase … --end` → `git add -A` + commit + `git diff --numstat` | Files changed, lines added/removed, full unified diffs | **Authoritative** for edits |
| 3 | Transcript read | Every `Stop` hook reads the session JSONL named in its payload (`transcript_path`), plus `<session>/subagents/*.jsonl`; `sddlog ingest-transcript` does the same after the fact | Token usage per model message; prompts and full agent outputs (ingest) | **Only source of token counts**; backfill / recovery for text |

**Why three.** Path 1 is real-time but depends on hook configuration and only
sees line deltas the tool call itself reports. Path 2 cannot see individual
turns but is exact about what changed on disk. Path 3 is the richest record of
agent *output* text but is written in a format controlled by the agent host,
so it is treated as secondary evidence. Path 3 deduplicates against paths 1–2
by SHA-256 of the message text, so backfilling never double-counts a turn.
Token usage is deduplicated by API message id: Claude Code writes one line per
content block, so the same message repeats in the transcript, and a resumed
session can repeat earlier messages. Each message is credited to the phase whose
window contains its timestamp.

## 4. Storage layout

```
logs/
├── ACTIVE_RUN              # run_id of the open run; hooks no-op when absent
├── index.json              # regenerated summary of every run
└── runs/
    └── R004/
        ├── manifest.json   # run metadata (section 2)
        ├── events.jsonl    # append-only event log — the primary record
        ├── diffs/          # unified diff per capture point
        │   └── 015-phase-specify.diff
        ├── snapshots/      # Spec Kit artifacts frozen per phase
        │   ├── constitution/constitution.md
        │   ├── specify/{constitution,spec}.md
        │   └── plan/{constitution,spec,plan,research,data-model}.md
        ├── metrics.json    # derived, always recomputable from events.jsonl
        └── report.md       # human-readable rendering of metrics.json
```

`events.jsonl` is the single source of truth. `metrics.json` and `report.md`
are derived and may be regenerated at any time with `sddlog metrics` /
`sddlog report`; they are never edited by hand.

Each run's `logs/runs/<RUN>/` directory is written inside that run's clone and
copied into the study repository's `logs/runs/` when the run closes. The clone
itself is kept, and archived as a git bundle, because Part III scores it.

## 5. Event schema

Every line of `events.jsonl` is one JSON object with this envelope:

| Field | Type | Notes |
| --- | --- | --- |
| `schema_version` | string | `1.0.0`; bump on any breaking payload change |
| `event_id` | UUID4 | Unique per event |
| `run_id` | string | Owning run |
| `seq` | integer | Dense, 1-based, monotonic — gaps indicate tampering |
| `ts` | ISO-8601 UTC | Millisecond precision, `Z`-suffixed |
| `type` | enum | See below |
| `actor` | enum | `human`, `agent`, or `system` |
| `phase` | string or null | Spec Kit phase open at the time; `null` between phases |
| `condition` | enum | Denormalised from the manifest so events are self-describing |
| `task_id` | string | Denormalised from the manifest |
| `session_id` | string or null | Agent session, when the host supplies one |
| `payload` | object | Type-specific, below |
| `redactions` | array | Present only when a redaction rule fired |

`condition` and `task_id` are denormalised onto every event on purpose: a
single event line, pulled out of context, still identifies which cell of the
design it belongs to. Adding the `sdd_clarify` value in 1.1 is not a breaking
payload change, so `schema_version` stays `1.0.0`.

### Event types

| `type` | Emitted by | Key payload fields |
| --- | --- | --- |
| `run_start` / `run_end` | `run-start` / `run-end` | `task_id`, `condition`, `model`; `status` |
| `phase_start` / `phase_end` | `phase … --start/--end` | `phase` |
| `prompt` | Hook, transcript, or `log-prompt` | `text`, `chars`, `words`, `sha256`, `source` |
| `token_usage` | `Stop` hook or `ingest-transcript` (1.2) | the four token fields, `messages`, `subagent_messages`, `models`, `message_ids`, `source: transcript_usage` |
| `agent_output` | Transcript or `log-output` | `text`, `chars`, `words`, `sha256`, `model` |
| `file_edit` | Hook (per edit) or git capture (per phase) | `path`, `lines_added`, `lines_removed`, `capture_label`, `base_commit`, `head_commit`, `diff_file` |
| `tool_call` | Hook | `tool`, `args_summary`, `ok` |
| `artifact_snapshot` | `snapshot` / phase close | `artifact`, `sha256`, `words`, `lines`, `snapshot_path` |
| `note` | `note` | `text`: operator observations, answers given (`ANSWER …`), caps, protocol deviations |

Both hook-derived and git-derived `file_edit` events appear in a normal run.
They are distinguished by `payload.source` (`hook`) versus the presence of
`payload.capture_label`. **Analysis uses git-derived events for line counts**;
hook-derived events are used for within-phase edit sequencing.

## 6. Measures and their mapping to research questions

| Measure | Definition | Source | RQ |
| --- | --- | --- | --- |
| `active_seconds` | Phase open → last **real-time (hook)** observation in that phase; `null` if the phase contains no hook events | Event timestamps | RQ3 |
| `wall_clock_seconds` | Marker to marker; flagged unreliable if trailing idle > 300 s | Event timestamps | RQ3 |
| `turns` | Count of human prompts within a phase | Hook | RQ3 |
| `prompt_words` | Total words the human supplied | Hook | RQ3 (specification burden) |
| `lines_added` / `lines_removed` | Git numstat between capture points | Git | RQ1, RQ3 |
| `distinct_files_touched` | Unique paths across all `file_edit` events | Git | RQ3 |
| `tool_calls` | Non-edit tool invocations | Hook | RQ3 |
| Artifact words per phase | `artifact_snapshot.words` by phase | Snapshots | RQ4 |
| Artifact hash drift | Change in `artifact_snapshot.sha256` across phases | Snapshots | RQ4 (is the spec revised after planning?) |
| Questions and answers | `note` events beginning `ANSWER` | Operator notes | RQ4 (clarify) |

**Deliberately out of scope for this instrument**: functional pass rate,
security-defect counts, and requirement traceability. Those require the
held-out test suites, a SAST run, and manual coding respectively. They are
computed in Part III over the artifacts and repositories collected here
(`PREREGISTRATION.md`, section 7), and joined to this dataset on `run_id`.

**The instrument is excluded from measurement.** Everything under `logs/` and
`tools/sddlog/` is filtered out twice: by git pathspec at capture time, and
again by path prefix when metrics are derived. The second filter exists
because `events.jsonl` is append-only — events written before a path was
excluded must be ignored at derivation time rather than edited out of history.

**Only hook events establish timing.** Git captures, artifact snapshots,
manual notes, and transcript backfill all carry a timestamp describing when
the *instrument* ran, not when the work happened. Using any of them to bound a
phase would mask the operator-idle gaps `active_seconds` exists to detect.

## 7. Operator procedure

`RUNBOOK.md` is the step-by-step checklist; this section states the rules it
implements.

### 7.1 Before any run

1. The run's clone is fresh from the base repository, on the starting commit (plus the Spec Kit setup commit for SDD conditions), with a clean working tree.
2. `python3 -m pytest tools/sddlog/tests/ -q` passes (73 tests).
3. `.claude/settings.json` hooks present.

### 7.2 SDD conditions (`sdd`, `sdd_clarify`)

Each phase runs in a fresh agent session, using the fixed prompt for that
phase (`prompts/README.md`):

```bash
python3 tools/sddlog/sddlog.py run-start --run-id R004 \
  --task T-ACCOUNTS-01 --condition sdd --model claude-opus-5 --agent claude-code

for phase in constitution specify plan tasks implement; do   # sdd_clarify: add clarify after specify
  python3 tools/sddlog/sddlog.py phase $phase --start
  #   ... run the phase's fixed prompt in a fresh agent session ...
  python3 tools/sddlog/sddlog.py phase $phase --end     # snapshot + git capture
done

python3 tools/sddlog/sddlog.py run-end --status completed
python3 tools/sddlog/sddlog.py verify --run-id R004
```

In `sdd_clarify` runs, every question the agent asks is answered from the
task's answer sheet and logged with `sddlog note --text "ANSWER <entry>: …"`.

### 7.3 Unstructured condition

The task text is given as a single prompt with no imposed structure. All work
is logged inside one phase marker so that the conditions remain comparable on
totals:

```bash
python3 tools/sddlog/sddlog.py run-start --run-id R006 \
  --task T-REDACT-01 --condition unstructured --model claude-opus-5
python3 tools/sddlog/sddlog.py phase implement --start
#   ... the task text, then follow-ups until the stopping rule is met (7.4) ...
python3 tools/sddlog/sddlog.py phase implement --end
python3 tools/sddlog/sddlog.py run-end --status completed
```

### 7.4 Stopping rule (all conditions)

A run is done when `tools/study/check_examples.py` reports that every example
in the task text behaves as shown. Until then, the follow-up message the
checker prints is pasted verbatim, up to 5 follow-ups or 90 minutes after
`implement` opened (`PREREGISTRATION.md`, section 6.3). This replaces the
operator's judgement of "done", which 1.0 left open.

### 7.5 Standing rules

- **Close a phase marker as soon as the agent finishes.** A late marker corrupts `wall_clock_seconds`. The tool will flag it, but that measurement is lost; prefer `active_seconds` in analysis.
- **Never edit repository files while a phase is open.** Operator work (tooling fixes, notes, environment changes) goes *between* phases and is recorded with `capture-edits --label <what>`, which attributes it to no phase. Running `check_examples.py` is allowed: it works in a temporary directory and writes nothing to the repository.
- **Record deviations as they happen** with `sddlog note`. A documented deviation is recoverable; an undocumented one invalidates the run.
- **Do not hand-edit `events.jsonl`.** `verify` detects sequence gaps.

## 8. Verification gate

A run enters the dataset only after `sddlog verify` reports no failures.

**Failures** (block the run): empty event log; missing manifest fields; invalid
`condition`; sequence gap; unparseable or backwards timestamp; unknown event
type; `phase_end` not matching an open `phase_start`.

**Warnings** (require an explanatory `note`, do not block):

- phases left open;
- completed phases that do not match the run's condition: a required phase missing, a phase outside the condition (for example `clarify` in an `sdd` run, or `specify` in an `unstructured` run), or required phases completed out of order;
- no prompts captured;
- no file edits captured;
- a phase whose timing was flagged unreliable.

## 9. Redaction and data handling

Redaction runs inside the single `append()` path, before anything is written,
so no caller can bypass it. It is applied to prompt text, agent output text,
tool argument summaries, unified diffs, and artifact snapshots.

Rules cover GitHub PATs, OpenAI and Anthropic keys, AWS access key IDs, Slack
tokens, private-key headers, bearer tokens, and generic
`password`/`secret`/`token`/`api_key` assignments. Each substitution is
replaced with `[REDACTED:<rule>]` and the firing rule name is recorded on the
event, so redaction is auditable rather than invisible.

Ordinary source code and prose are **not** redacted — they are the object of
study. Logs are committed to the study repository and contain no participant
data beyond the single operator's own prompts.

## 10. Known limitations

1. **Hook line deltas are approximations.** They are computed from the tool call's own strings, not from disk. Git capture is authoritative; the two will disagree and that is expected.
2. **Wall-clock timing depends on operator discipline.** Mitigated, not eliminated, by `active_seconds` and idle flagging.
3. **Agent-internal behaviour is mostly invisible.** Retries and context management are not observable through hooks. Token counts are read from the transcript's per-message usage records (path 3), so they depend on the host's transcript format; `verify` warns when an agent phase has no token usage.
4. **The transcript format is host-controlled.** A Claude Code update could change it; ingestion is therefore a recovery path, never the primary one. Backfilled events are also stamped with the *ingest* time, not the original turn time (the original is preserved in `payload.transcript_ts`), which is why they are excluded from timing.
5. **Single operator, single agent.** Within-subject design; no inter-rater reliability is available for the capture step itself.
6. **`turns` counts human prompts only.** A long autonomous agent run counts as one turn regardless of internal work, which understates agent effort and is the intended reading for RQ3 (human cost).
7. **Files the agent's own code creates are measured.** Databases or data directories the agent creates while testing its code are committed at capture points and appear in `distinct_files_touched`. This applies equally to every condition; code size for analysis is taken from Python source only (`score_run.py`).

## 11. Command reference

| Command | Purpose |
| --- | --- |
| `run-start --run-id --task --condition --model` | Open a run, write manifest, set `ACTIVE_RUN` |
| `run-end [--status]` | Close run, write `metrics.json` and `report.md` |
| `phase <name> --start \| --end` | Phase boundary; `--end` snapshots artifacts and captures edits |
| `log-prompt` / `log-output` | Manual capture (`--text`, `--file`, `--stdin`) |
| `note --text` | Operator observation, answer given, or protocol deviation |
| `capture-edits --label` | Git capture outside a phase |
| `snapshot --phase` | Artifact snapshot without closing a phase |
| `hook --event <name>` | Hook entrypoint; reads JSON on stdin, always exits 0 |
| `ingest-transcript --path [--since]` | Idempotent backfill from agent transcript |
| `metrics` / `report` / `verify` / `list` | Derive, render, check, enumerate |

Valid conditions: `unstructured`, `sdd`, `sdd_clarify`. Valid phases:
`constitution`, `specify`, `clarify`, `plan`, `tasks`, `analyze`, `implement`.

## 12. Changelog

**1.2 (Week 7)**: before the pre-registration is frozen and before any study run.

- Token usage: every `Stop` hook reads per-message usage (`input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`) from the session transcript and its subagent transcripts, and records new messages in a `token_usage` event. Messages are deduplicated by message id and credited to the phase that contains their timestamp. `metrics.json` reports tokens per phase and in totals (`input_tokens_all`, `output_tokens`, `model_messages`); `verify` warns when an agent phase has none.
- The `PostToolUse` hook now also matches `Agent` and `Skill`, so subagent launches and skill invocations appear in the tool-call log (`Task` stays for older Claude Code versions).
- Six new tests (73 in total).

**1.1 (Weeks 5–7)**: prepared for the controlled study, before any study run.

- Added the `sdd_clarify` condition, so the clarify stage is a manipulated factor rather than an optional extra (Pilot Report section 3.2).
- The verification gate now checks each run's completed phases against its condition: required phases present, no phases outside the condition, and required phases in workflow order.
- Every run starts from a shared base repository with no Spec Kit; SDD conditions add Spec Kit in one setup commit. Spec Kit's commands are model-invocable skills, so their presence would contaminate the unstructured condition.
- Run IDs are pre-assigned by the schedule (`--run-id`, already supported in 1.0), since each run lives in its own clone.
- "Done" is now defined by a pre-registered stopping rule (section 7.4) instead of operator judgement.
- Ten new tests (67 in total).

**1.0 (Milestone 2)** — Initial ratification. Two changes were made in
response to the R001 pilot rather than designed up front:

- Added `active_seconds`, `trailing_idle_seconds`, and `timing_reliable` after
  an operator interruption inflated one phase's marker-to-marker wall clock by
  roughly three days. Marker-derived wall clock alone was not a safe measure.
- Excluded `logs/` and `tools/sddlog/` from all measurement, at both capture
  and derivation time, after the instrument was observed recording its own
  event file as agent work (a phase reported 200 changed lines where 3 were
  real), and after operator maintenance of the instrument during an open phase
  would otherwise have been attributed to the agent.
- Restricted `active_seconds` to hook-sourced events. The first version of the
  fix above counted *any* event in the phase as activity, including the
  operator note written three days late — which made the stalled phase look
  continuously active and suppressed the very warning it was added to raise.
  A phase with no hook events now reports `null` rather than a number that
  looks measured.
