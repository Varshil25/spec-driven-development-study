#!/usr/bin/env python3
"""Prepare a provenance-logged analysis VIEW without editing the frozen data.

Expects all Python study runs, all 72 scores, all 144 coding sheets, and a
verified idle-gap audit CSV from recompute_idle_time.py. Stops if incomplete.
R011C remains excluded; R019C substitutes for it in the frozen analyzer's
expected filenames *only in this separate derived view*.
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from preflight_part_iii import expected_runs

KIT = Path(__file__).resolve().parents[2]
KINDS = ("traceability", "security", "principles")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(schedule, run_root, score_root, coding_root, time_csv, out):
    builds, items = expected_runs(schedule)
    with Path(time_csv).open(newline="", encoding="utf-8") as f:
        audit_rows = list(csv.DictReader(f))
    audit = {row["run_id"]: row for row in audit_rows}
    if len(audit) != len(audit_rows):
        raise ValueError("Duplicate run IDs in time-audit CSV")
    required = []
    for item in items:
        original, effective = item["nominal_id"], item["effective_id"]
        required.extend([(effective, run_root / effective / "metrics.json", "metrics"),
                         (effective, run_root / effective / "events.jsonl", "events"),
                         (effective, score_root / (effective + ".json"), "score")])
        if item["change_request"]:
            required.append((effective, score_root / (effective + "-regression.json"), "regression"))
        for kind in KINDS:
            required.append((effective, coding_root / f"{effective}-{kind}.csv", kind))
    missing = [f"{rid} {kind}: {path}" for rid, path, kind in required if not path.is_file()]
    missing.extend(f"{r['effective_id']}: corrected-time entry missing" for r in items
                   if r["effective_id"] not in audit)
    if missing:
        raise ValueError(f"Analysis view not ready ({len(missing)} missing inputs):\n" +
                         "\n".join(missing[:25]))
    for item in items:
        rid = item["effective_id"]
        r = audit[rid]
        if r["check"] not in ("matches_raw", "gap_adjusted"):
            raise ValueError(f"Idle-gap audit for {rid} is not accepted: {r['check']}")
        if sha(run_root / rid / "metrics.json") != r["metrics_sha256"] or \
           sha(run_root / rid / "events.jsonl") != r["events_sha256"]:
            raise ValueError(f"Idle-gap audit hashes stale for {rid}")
        metrics = json.loads((run_root / rid / "metrics.json").read_text())
        if metrics.get("run_id") != rid or abs(float(r["raw_active_seconds"]) - metrics["totals"]["active_seconds"]) > 1:
            raise ValueError(f"Metrics mismatch for {rid}")
        corrected = float(r["corrected_active_seconds"])
        if not (0 <= corrected <= metrics["totals"]["active_seconds"] + 1):
            raise ValueError(f"Invalid adjusted time for {rid}")
    out = Path(out)
    if out.exists():
        raise FileExistsError(f"Analysis view exists, refusing overwrite: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="part-iii-view-", dir=out.parent))
    records = []
    try:
        for item in items:
            nominal, actual = item["nominal_id"], item["effective_id"]
            src = run_root / actual / "metrics.json"
            m = json.loads(src.read_text())
            original_time = m["totals"]["active_seconds"]
            m["totals"]["active_seconds"] = float(audit[actual]["corrected_active_seconds"])
            out_metrics = temp / "runs" / nominal / "metrics.json"
            out_metrics.parent.mkdir(parents=True, exist_ok=True)
            out_metrics.write_text(json.dumps(m, indent=2) + "\n")
            files = [(score_root / (actual + ".json"), temp / "scores" / (nominal + ".json"))]
            if item["change_request"]:
                files.append((score_root / (actual + "-regression.json"),
                              temp / "scores" / (nominal + "-regression.json")))
            for kind in KINDS:
                files.append((coding_root / f"{actual}-{kind}.csv",
                              temp / "coding" / f"{nominal}-{kind}.csv"))
            for input_path, output_path in files:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(input_path, output_path)
            records.append({"analysis_id": nominal, "source_id": actual,
                            "raw_active_seconds": original_time,
                            "adjusted_active_seconds": m["totals"]["active_seconds"],
                            "metrics_source_sha256": sha(src),
                            "events_source_sha256": sha(run_root / actual / "events.jsonl"),
                            "score_source_sha256": sha(score_root / (actual + ".json"))})
        (temp / "provenance.json").write_text(json.dumps({"purpose": "derived view for frozen analyzer",
             "originals_modified": False, "replacement": {"R011C": "R019C"},
             "time_rule": "exclude complete >600-second gaps between phase start/hook activity",
             "records": records}, indent=2) + "\n")
        os.rename(temp, out)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return len(items)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schedule", type=Path, default=KIT / "schedule/schedule.csv")
    p.add_argument("--runs-root", type=Path, required=True, help="directory containing <run>/metrics.json and events.jsonl")
    p.add_argument("--scores", type=Path, required=True)
    p.add_argument("--coding", type=Path, required=True)
    p.add_argument("--time-csv", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    count = prepare(a.schedule, a.runs_root, a.scores, a.coding, a.time_csv, a.out)
    print(f"Prepared view for {count} study-run cells at {a.out}; originals untouched.")


if __name__ == "__main__":
    main()
