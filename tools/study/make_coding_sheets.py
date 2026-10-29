#!/usr/bin/env python3
"""Create the Part III coding sheets for one scored run.

Writes two CSV files, pre-filled from the schedule, the requirements register
and the run's score file, ready for manual coding:

  coding/runs/<RUN>-traceability.csv   one row per stated and intent requirement
  coding/runs/<RUN>-security.csv       one row per failed security probe and
                                       per SAST finding (Bandit for Python
                                       tasks, SpotBugs + FindSecBugs for the
                                       Java tasks); manual-review rows are
                                       added by hand

Usage: python3 tools/study/make_coding_sheets.py R004 --score scores/R004.json
The coding rules are in docs/PREREGISTRATION.md, section 7.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]

TRACE_FIELDS = ["run_id", "task_id", "condition", "req_id", "tier", "requirement",
                "heldout_passed", "code_locations", "agent_tests", "spec_ids",
                "explicit_link", "score", "notes"]
SEC_FIELDS = ["run_id", "task_id", "condition", "finding_id", "source", "cwe", "location",
              "severity", "confirmed", "notes"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_id")
    parser.add_argument("--score", required=True, help="score JSON written by score_run.py")
    parser.add_argument("--out-dir", default=str(KIT / "coding" / "runs"))
    args = parser.parse_args(argv)

    schedule = {r["run_id"]: r for r in csv.DictReader(open(KIT / "schedule" / "schedule.csv"))}
    if args.run_id not in schedule:
        parser.error("%s is not in schedule/schedule.csv" % args.run_id)
    run = schedule[args.run_id]
    score = json.loads(Path(args.score).read_text())
    if score.get("task_id") != run["task_id"]:
        parser.error("score file is for %s, schedule says %s" % (score.get("task_id"), run["task_id"]))

    outcome = {}
    for tier in score["tiers"].values():
        for test in tier["tests"]:
            base = test["test"].split("[")[0]
            outcome.setdefault(base, []).append(test["outcome"] == "passed")

    requirements = [r for r in csv.DictReader(open(KIT / "coding" / "requirements.csv"))
                    if r["task_id"] == run["task_id"]]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    trace_path = out_dir / ("%s-traceability.csv" % args.run_id)
    with open(trace_path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACE_FIELDS, lineterminator="\n")
        writer.writeheader()
        for req in requirements:
            if req["tier"] == "security":
                continue
            results = [ok for name in req["heldout_tests"].split() for ok in outcome.get(name, [])]
            writer.writerow({"run_id": args.run_id, "task_id": run["task_id"],
                             "condition": run["condition"], "req_id": req["req_id"],
                             "tier": req["tier"], "requirement": req["requirement"],
                             "heldout_passed": "%d/%d" % (sum(results), len(results))})

    sec_path = out_dir / ("%s-security.csv" % args.run_id)
    cwe_of = {r["req_id"]: (re.search(r"CWE-[\d/]+", r["requirement"]) or [""])[0]
              for r in requirements if r["tier"] == "security"}
    with open(sec_path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SEC_FIELDS, lineterminator="\n")
        writer.writeheader()
        number = 0
        for test in score["tiers"]["security"]["tests"]:
            if test["outcome"] == "passed":
                continue
            number += 1
            req = re.match(r"test_c(\d+)_", test["test"])
            req_id = "C%s" % req.group(1) if req else "?"
            writer.writerow({"run_id": args.run_id, "task_id": run["task_id"],
                             "condition": run["condition"], "finding_id": "F%02d" % number,
                             "source": "probe:%s" % test["test"], "cwe": cwe_of.get(req_id, ""),
                             "notes": test["message"][:200]})
        sast = score.get("sast") or {}
        tool = "spotbugs" if str(sast.get("tool", "")).startswith("spotbugs") else "bandit"
        for finding in sast.get("findings", []):
            number += 1
            writer.writerow({"run_id": args.run_id, "task_id": run["task_id"],
                             "condition": run["condition"], "finding_id": "F%02d" % number,
                             "source": "%s:%s" % (tool, finding["test_id"]), "cwe": finding["cwe"] or "",
                             "location": "%s:%s" % (finding["file"], finding["line"]),
                             "notes": "%s severity %s: %s" % (tool, finding["severity"], finding["message"])})
    print("wrote %s\nwrote %s" % (trace_path, sec_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
