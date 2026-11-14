# Batch Process

> **OpenOwls SD-KDP** — Read by whoever schedules or debugs the pipeline.
> The unattended run: what runs, when, in what order, and what happens when a step fails.

---

## Job inventory

| Step | Script | Does | Skips when |
| --- | --- | --- | --- |
| 1. Collect | `scripts/collect.py` | Fetch or import every trusted source; extract text; record hashes in `state/manifest.json` | Source text hash unchanged |
| 2. Distill | `scripts/distill.py` | One article per new or changed source, then the voice check | Article's `source_sha256` and `spec_sha256` both match |
| 3. Synthesize | `scripts/synthesize.py` | Question pages, FAQ, index from the articles | No article changed since the last synthesis |
| 4. Index | `scripts/index.py` | TF-IDF vector index over `wiki/` for `scripts/query.py` | No wiki page changed |
| 5. Backup | `scripts/batch.sh` | `git commit` of `wiki/` and `corpus/` with the run ID; dated tarball of `wiki/` and `state/` in `backups/` (keep the last 7) | Nothing changed |

`scripts/batch.sh` runs the five steps in order and stops at the first step that exits with
status 2 (a hard failure). Status 1 (some sources failed, others fine) continues.

## Schedule

Nightly at 02:30 local time, from cron on the machine that holds the repository:

```
30 2 * * * cd /path/to/spec-driven-development-study/part-iv && scripts/batch.sh >> state/batch.log 2>&1
```

Changing a spec file in `ai_specs/` changes `spec_sha256`, so the next nightly run re-distils every
article under the new spec. That is intended: the spec is the source.

## The incremental check (SD-KDP step 5, verified once and reported)

1. Run `batch.sh` on the full corpus. Record per-step counts.
2. Run it again with nothing changed. **Expected: 0 sources collected as changed, 0 distilled.**
3. Change one source (re-import S08 with a one-line edit). **Expected: 1 collected as changed,
   1 distilled, its question pages re-synthesized.**
4. Change one line in `distillation-techniques.md`. **Expected: all articles re-distilled.**

The counts from each run are logged in `state/batch.log` and copied into the report.

## LLM access and cost

`scripts/llm.py` is the only place a model is called. Two backends:

- `claude` (default): the Claude Code CLI in headless mode (`claude -p`), using the author's
  subscription. Note: this shares the five-hour usage limit with the Part III study runs, so the
  first full distillation is scheduled for after the last study run, or run on an API key.
- `anthropic`: the Anthropic API with `ANTHROPIC_API_KEY` from `.env` (git-ignored).

**Decision (author, 14 Nov 2026):** the `claude` backend on the author's subscription. The first
full distillation runs after the last Part III study run, so it does not take usage the runs need;
the one-source trial (a few calls) may run earlier.

The model ID is set once in `llm.py` and written into every article. **The OpenKB comparison uses
the same model** (OpenKB reads `LLM_API_KEY` and a `provider/model` string, e.g.
`anthropic/<model>`), so both knowledge bases differ in method, not in model.

## Failure handling

| Failure | Action |
| --- | --- |
| A fetch fails | Logged; other sources continue; exit 1 |
| An article fails the voice check twice | Not written; logged with the drifting sentences; exit 1 |
| The LLM is unavailable or over its limit | Stop the run (exit 2); the next nightly run resumes from the hashes |
| `git commit` fails | Exit 2; the tarball is still written |

## Latest run status

Recorded by `batch.sh` at the top of `progress.md` after each run: date, run ID, counts per step,
exit status.
