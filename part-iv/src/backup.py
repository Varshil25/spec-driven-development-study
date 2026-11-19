"""Timestamped snapshots; run regardless of earlier pipeline failures."""
import shutil
from datetime import datetime, timezone
from paths import KDB, WIKI, BACKUPS

def backup(keep=14):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = BACKUPS / stamp
    dest.mkdir()
    for src in (KDB, WIKI):
        if src.exists():
            shutil.copytree(src, dest / src.name, ignore=shutil.ignore_patterns(".gitkeep"))
    snapshots = sorted(p for p in BACKUPS.iterdir() if p.is_dir())
    for stale in snapshots[:-keep]:
        shutil.rmtree(stale)
    return {"snapshot": stamp}
