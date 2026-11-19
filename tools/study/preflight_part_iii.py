#!/usr/bin/env python3
"""Read-only Part III evidence preflight. Never unseals suites or changes frozen files.

Usage: python tools/study/preflight_part_iii.py [--runs-root DIR] [--scores DIR]
       [--coding DIR] [--json-out FILE] [--strict]

Missing evidence is not a failed experiment; it is reported as missing.
"""
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
EXCLUDED_TASK_PREFIX = "T-Q"  # Java extension dropped before runs, per report.
PURPOSES = {"study", "replication"}
# Per report: corrupted R011C was excluded, and R019C re-ran the cell.
REPLACEMENTS = {"R011C": "R019C"}
CODING_KINDS = ("traceability", "security", "principles")
RUN_ARTIFACTS = ("metrics.json", "manifest.json", "events.jsonl")


def expected_runs(schedule_file):
    with Path(schedule_file).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    builds = [row for row in rows
              if row.get("purpose") in PURPOSES
              and not row.get("task_id", "").startswith(EXCLUDED_TASK_PREFIX)]
    if len({r["run_id"] for r in builds}) != len(builds):
        raise ValueError("Schedule has duplicate build run IDs")
    expected = []
    for row in builds:
        for change in (False, True):
            nominal = row["run_id"] + ("C" if change else "")
            expected.append({"nominal_id": nominal,
                             "effective_id": REPLACEMENTS.get(nominal, nominal),
                             "task_id": row["task_id"] + ("-CR" if change else ""),
                             "condition": row["condition"],
                             "purpose": row["purpose"],
                             "change_request": change})
    return builds, expected


def run_artifact(root, run_id, filename):
    """Support a central logs directory and individual self-contained clones."""
    candidates = [root / "runs" / run_id / filename,
                  root / "logs" / "runs" / run_id / filename,
                  root / run_id / "logs" / "runs" / run_id / filename,
                  root / run_id / filename]
    return next((str(p) for p in candidates if p.is_file()), None)


def build_report(schedule_file, runs_root, scores_dir, coding_dir, heldout_root):
    builds, expected = expected_runs(schedule_file)
    missing = Counter()
    cases = []
    for run in expected:
        rid = run["effective_id"]
        events = {f: run_artifact(runs_root, rid, f) for f in RUN_ARTIFACTS}
        score_names = [rid + ".json"]
        if run["change_request"]:
            score_names.append(rid + "-regression.json")
        scores = {name: str(scores_dir / name) if (scores_dir / name).is_file() else None
                  for name in score_names}
        coding = {kind: str(coding_dir / f"{rid}-{kind}.csv")
                  if (coding_dir / f"{rid}-{kind}.csv").is_file() else None
                  for kind in CODING_KINDS}
        for key, location in events.items():
            if location is None:
                missing["run_" + key] += 1
        for key, location in scores.items():
            if location is None:
                missing["score_file"] += 1
        for key, location in coding.items():
            if location is None:
                missing["coding_" + key] += 1
        cases.append({**run, "run_artifacts": events, "score_files": scores,
                      "coding_sheets": coding})
    suites = {"build": (heldout_root / "sealed" / "heldout").is_dir(),
              "change_request": (heldout_root / "sealed-cr" / "heldout").is_dir()}
    # Preflight deliberately does not decrypt or assert that suites match frozen hashes.
    ready = not missing and all(suites.values())
    return {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "files_present_unverified_hashes" if ready else "incomplete",
            "scheduled_python_builds": len(builds),
            "expected_python_study_runs": len(expected),
            "expected_score_files": len(builds) * 3,
            "expected_coding_sheets": len(expected) * len(CODING_KINDS),
            "replacement_policy": REPLACEMENTS,
            "excluded_java_extension": True,
            "unsealed_suite_directories_present": suites,
            "missing_counts": dict(sorted(missing.items())), "runs": cases,
            "warnings": ["File presence is not experimental validation: verify archive integrity, sealed-suite tree hashes, scorer outputs, manual coding and exclusions before reporting results.",
                         "R011C is excluded; its effective change-request ID is R019C.",
                         "This preflight never executes study runs or decrypts held-out suites."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path, default=KIT / "schedule/schedule.csv")
    parser.add_argument("--runs-root", type=Path, default=KIT / "logs")
    parser.add_argument("--scores", type=Path, default=KIT / "scores")
    parser.add_argument("--coding", type=Path, default=KIT / "coding/runs")
    parser.add_argument("--heldout-root", type=Path, default=KIT)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--strict", action="store_true", help="return 2 when required evidence is missing")
    args = parser.parse_args(argv)
    report = build_report(args.schedule, args.runs_root, args.scores, args.coding, args.heldout_root)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload, encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "runs"}, indent=2))
    return 2 if args.strict and report["status"] != "files_present_unverified_hashes" else 0


if __name__ == "__main__":
    raise SystemExit(main())
