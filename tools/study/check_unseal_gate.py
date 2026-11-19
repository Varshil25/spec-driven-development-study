#!/usr/bin/env python3
"""Read-only gate for unsealing/scoring after ALL registered Python study runs.

Does not decrypt archives, access private passphrases, run model sessions,
invoke held-out tests or modify frozen preregistration/scoring scripts.
"""
import argparse
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path
from preflight_part_iii import expected_runs
from run_remaining_part_iii import archived
from verify_archived_runs import run_archive
from score_run import tree_hash

KIT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "build": {
        "zip": "sealed-heldout-v1.zip",
        "sha": "9451954e1d4d4a914cad422b0477c838626ce9507bb9ac23966dbcc5a02c2198",
        "dir": "sealed/heldout",
        "tree": "a9b755596fa4d76f0658118373662f75c55dce3212a28a934cae2d1187425b9a",
    },
    "change": {
        "zip": "sealed-heldout-cr-v1.zip",
        "sha": "5ab5a4f021d36af294a2a75bc402babc2eef30bd6150069570c63fd78dc0bdd3",
        "dir": "sealed-cr/heldout",
        "tree": "4c345801d02d84af19814e842c4a877278390b061f4a3028e7c2ccf0b813d736",
    },
}

def hash_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def check(kit=KIT, check_verifier=True, check_packages=True):
    kit=Path(kit)
    build_rows,cells=expected_runs(kit/"schedule/schedule.csv")
    missing_archived=[r["effective_id"] for r in cells
                      if not archived(kit,{"run_id":r["effective_id"],
                                           "task_id":r["task_id"],"condition":r["condition"]})]
    bundles=[r["run_id"] for r in build_rows]+["R019"]
    missing_bundles=[name for name in bundles
                     if not (kit/"logs/bundles"/(name+".bundle")).is_file()]
    integrity=None
    if check_verifier:
        integrity=run_archive(kit,kit/"schedule/schedule.csv")
    zip_checks={}
    for label,spec in EXPECTED.items():
        archive=kit/spec["zip"]
        folder=kit/spec["dir"]
        zip_checks[label]={
            "zip_present":archive.is_file(),
            "zip_sha256_matches":hash_file(archive)==spec["sha"] if archive.is_file() else False,
            "tree_present":folder.is_dir(),
            "tree_sha256_matches":tree_hash(folder)==spec["tree"] if folder.is_dir() else False,
        }
    packages={}
    if check_packages:
        for name in ("pytest","bandit"):
            try:
                packages[name]=importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                packages[name]=None
    problems=[]
    if len(cells)!=48:
        problems.append("Frozen schedule does not have 48 effective Python cells")
    if missing_archived:
        problems.append("%d effective run archives missing/incomplete" % len(missing_archived))
    if missing_bundles:
        problems.append("%d required run bundles missing" % len(missing_bundles))
    if integrity is not None:
        if integrity["integrity_failures"] or integrity["integrity_passes"]!=48:
            problems.append("All 48 archived runs must pass frozen sddlog integrity")
    for label,d in zip_checks.items():
        if not d["zip_sha256_matches"] or not d["tree_sha256_matches"]:
            problems.append(label+" held-out plaintext ZIP/tree does not match preregistered SHA-256")
    if sys.version_info[:2]!=(3,13):
        problems.append("Python 3.13 scoring environment required")
    if check_packages:
        if packages.get("bandit")!="1.9.4":
            problems.append("Pre-registered Bandit 1.9.4 not available")
        if packages.get("pytest") is None:
            problems.append("pytest not installed in scorer Python environment")
    return {"ready_for_scoring":not problems,"scheduled_builds":len(build_rows),
            "expected_effective_runs":len(cells),"missing_run_ids":missing_archived,
            "missing_bundle_ids":missing_bundles,
            "log_integrity_passes":integrity["integrity_passes"] if integrity else None,
            "log_integrity_failures":integrity["integrity_failures"] if integrity else None,
            "unsealed_hash_checks":zip_checks,"scoring_packages":packages,
            "expected_scoring_outputs":72,
            "remaining_gates":problems,
            "warning":"This is a provenance/presence gate, not a correctness, security, traceability, or RQ1-RQ4 result."}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kit",type=Path,default=KIT)
    p.add_argument("--json-out",type=Path)
    p.add_argument("--strict",action="store_true",
                   help="Exit nonzero unless 48 runs, bundles, unsealed hashes, and tools are ready")
    args=p.parse_args(argv)
    report=check(args.kit)
    output=json.dumps(report,indent=2)+"\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(output,encoding="utf-8")
    print(output)
    return 2 if args.strict and not report["ready_for_scoring"] else 0

if __name__=="__main__":
    raise SystemExit(main())
