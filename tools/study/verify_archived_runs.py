#!/usr/bin/env python3
"""Re-check integrity of archived Part III logs using the frozen sddlog verifier.

Only reads an archive checkout. Missing runs are not classified as failed runs.
The excluded R011C is inspected separately and never included in valid counts.
"""
import argparse
import json
import sys
from pathlib import Path
from preflight_part_iii import expected_runs

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools/sddlog"))
from sddlog import Store, verify_run


def run_archive(archive_repo, schedule):
    _, expected = expected_runs(schedule)
    store = Store(archive_repo)
    results, missing = [], []
    for item in expected:
        rid = item["effective_id"]
        root = Path(archive_repo) / "logs" / "runs" / rid
        if not (root / "events.jsonl").exists() or not (root / "manifest.json").exists():
            missing.append(rid)
            continue
        try:
            problems, warnings = verify_run(store, rid)
        except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
            problems, warnings = ["Verifier exception: " + str(exc)], []
        results.append({"run_id": rid, "condition": item["condition"],
                        "problems": problems, "warnings": warnings,
                        "verified_six_checks": not bool(problems)})
    excluded = Path(archive_repo) / "logs/runs/R011C"
    rejected = None
    if (excluded / "events.jsonl").exists():
        try:
            problems, warnings = verify_run(store, "R011C")
        except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
            problems, warnings = ["Verifier exception: " + str(exc)], []
        rejected = {"run_id": "R011C", "excluded_from_scoring": True,
                    "problems": problems, "warnings": warnings}
    return {"effective_scheduled": len(expected), "scanned": len(results),
            "integrity_passes": sum(x["verified_six_checks"] for x in results),
            "integrity_failures": [x for x in results if not x["verified_six_checks"]],
            "warning_runs": sum(bool(x["warnings"]) for x in results),
            "not_archived": missing, "excluded_audit": rejected,
            "details": results,
            "caveat": "sddlog integrity does not validate hidden-test scores, coding, software correctness, or full dataset completeness"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive-repo", type=Path, required=True)
    ap.add_argument("--schedule", type=Path, default=KIT / "schedule/schedule.csv")
    ap.add_argument("--json-out", type=Path)
    a = ap.parse_args(argv)
    report = run_archive(a.archive_repo, a.schedule)
    print(json.dumps({k: v for k, v in report.items() if k != "details"}, indent=2))
    if a.json_out:
        a.json_out.parent.mkdir(parents=True, exist_ok=True)
        a.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 1 if report["integrity_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
