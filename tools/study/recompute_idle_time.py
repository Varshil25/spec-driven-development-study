#!/usr/bin/env python3
"""Independent, read-only 10-minute idle-gap correction for Part III active time.

Preserves original metrics and event logs. Missing runs remain missing; this is
not a replacement for sddlog integrity verification or the frozen analysis.
"""
import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
MAX_IDLE_SECONDS = 600
REPLACEMENTS = {"R011C": "R019C"}
FIELDS = ("run_id", "raw_active_seconds", "corrected_active_seconds",
          "removed_idle_seconds", "idle_gaps_over_600s", "largest_idle_gap_seconds",
          "check", "events_sha256", "metrics_sha256")


def iso(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def correct(events, metrics):
    """Add only phase start→hook and hook→hook intervals of at most 600s."""
    starts, hooks, duplicates = {}, {}, set()
    for ev in events:
        phase, kind = ev.get("phase"), ev.get("type")
        if kind == "phase_start":
            if phase in starts:
                duplicates.add(phase)
            starts[phase] = iso(ev["ts"])
            hooks.setdefault(phase, [])
        elif phase in starts and (ev.get("payload") or {}).get("source") == "hook":
            hooks[phase].append(iso(ev["ts"]))
    if duplicates:
        raise ValueError("duplicate phase_start markers: " + repr(sorted(duplicates)))
    if not starts or any(not hooks[p] for p in starts):
        raise ValueError("a phase has no hook activity")
    total, dropped = 0.0, []
    for phase, start in starts.items():
        previous = start
        for ts in hooks[phase]:
            gap = (ts - previous).total_seconds()
            if gap < 0:
                raise ValueError("nonmonotonic hook timestamps: " + phase)
            if gap > MAX_IDLE_SECONDS:
                dropped.append((phase, gap))
            else:
                total += gap
            previous = ts
    raw = float(metrics["totals"]["active_seconds"])
    corrected = round(total, 1)
    removed = round(sum(x[1] for x in dropped), 1)
    # The unadjusted metric is rounded phase by phase; tolerate 1s rounding.
    check = "matches_raw" if not dropped and abs(raw - corrected) <= 1.0 else (
        "gap_adjusted" if dropped and abs(raw - corrected - removed) <= max(2.0, .01 * raw) else "REVIEW")
    return {"raw_active_seconds": round(raw, 1),
            "corrected_active_seconds": corrected,
            "removed_idle_seconds": removed,
            "idle_gaps_over_600s": len(dropped),
            "largest_idle_gap_seconds": round(max((x[1] for x in dropped), default=0.0), 1),
            "check": check}


def read_one(logs_root, rid):
    folder = Path(logs_root) / rid
    ep, mp = folder / "events.jsonl", folder / "metrics.json"
    if not ep.is_file() or not mp.is_file():
        return None
    eb, mb = ep.read_bytes(), mp.read_bytes()
    events = [json.loads(line) for line in eb.decode("utf-8").splitlines() if line.strip()]
    metrics = json.loads(mb)
    if metrics.get("run_id") != rid or any(e.get("run_id") != rid for e in events):
        raise ValueError("run-id mismatch: " + rid)
    return {"run_id": rid, **correct(events, metrics),
            "events_sha256": hashlib.sha256(eb).hexdigest(),
            "metrics_sha256": hashlib.sha256(mb).hexdigest()}


def run_ids(schedule):
    with Path(schedule).open(encoding="utf-8", newline="") as f:
        lines = list(csv.DictReader(f))
    return [REPLACEMENTS.get(r["run_id"] + c, r["run_id"] + c)
            for r in lines if r.get("purpose") in ("study", "replication")
            and not r.get("task_id", "").startswith("T-Q")
            for c in ("", "C")]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=KIT / "logs/runs")
    parser.add_argument("--schedule", type=Path, default=KIT / "schedule/schedule.csv")
    parser.add_argument("--csv-out", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    ids = run_ids(args.schedule)
    records, missing, errors = [], [], []
    for rid in ids:
        try:
            result = read_one(args.runs_root, rid)
            if result:
                records.append(result)
            else:
                missing.append(rid)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{rid}: {exc}")
    if args.csv_out:
        args.csv_out.parent.mkdir(parents=True, exist_ok=True)
        with args.csv_out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, FIELDS)
            writer.writeheader()
            writer.writerows(records)
    print(json.dumps({"total_expected": len(ids), "computed": len(records),
                      "adjusted": sum(r["idle_gaps_over_600s"] > 0 for r in records),
                      "review": [r["run_id"] for r in records if r["check"] == "REVIEW"],
                      "missing": missing, "errors": errors}, indent=2))
    return 2 if errors or any(r["check"] == "REVIEW" for r in records) or (args.require_complete and missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
