# Batch process
**Audience: DevOps / Engineer**

Four stages: collect (reviewed text -> kdb/raw + hash manifest), distill (changed raw sources -> wiki/articles), index (wiki -> .index/index.json), backup (snapshot kdb and wiki -> backups). `src/run_batch.py` orchestrates and logs to `.state/runs/`, appending a row to `progress.md`. Continue on individual source errors; backup runs even if any stage fails. Preserve 14 snapshots by default. No scheduler is installed automatically: after a successful manual trial, configure cron or equivalent to run nightly, monitor logs and verify restoration. `--force` reprocesses all.
