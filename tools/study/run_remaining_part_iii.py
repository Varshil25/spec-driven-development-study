#!/usr/bin/env python3
"""Continue the registered Part III run schedule in the ORIGINAL Claude Code workspace.

Read-only by default. With --execute, launch only the first unarchived cell.
With --execute --all, continue sequentially with a human operator present.
NEVER decrypt sealed tests, synthesize responses or alter the frozen runner.
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
STUDY_PURPOSES = ("study", "replication")
REPLACEMENT = {"R011C": "R019C"}
EXPECTED_CLAUDE = "2.1.317"
EXPECTED_SPECIFY = "1.0.6"

def plan(schedule):
    with Path(schedule).open(newline="", encoding="utf-8") as stream:
        rows=list(csv.DictReader(stream))
    result=[]
    for row in rows:
        if row.get("purpose") not in STUDY_PURPOSES or row["task_id"].startswith("T-Q"):
            continue
        for change in (False,True):
            nominal=row["run_id"]+("C" if change else "")
            result.append({"run_id":REPLACEMENT.get(nominal,nominal),
                           "nominal_id":nominal, "build_id":row["run_id"],
                           "task_id":row["task_id"]+("-CR" if change else ""),
                           "condition":row["condition"],"change":change})
    return result

def archived(evidence_root, cell):
    root=Path(evidence_root)/"logs"/"runs"/cell["run_id"]
    required=[root/x for x in ("manifest.json","events.jsonl","metrics.json")]
    if not all(x.is_file() for x in required):
        return False
    try:
        data=json.loads(required[0].read_text(encoding="utf-8"))
    except (OSError,ValueError):
        return False
    return (data.get("status")=="completed" and data.get("run_id")==cell["run_id"]
            and data.get("task_id")==cell["task_id"] and data.get("condition")==cell["condition"])

def overview(schedule,evidence_root):
    cells=plan(schedule)
    completed=[cell for cell in cells if archived(evidence_root,cell)]
    incomplete=[cell for cell in cells if not archived(evidence_root,cell)]
    # Explicitly protect the frozen schedule's sequence.
    first=incomplete[0] if incomplete else None
    return {"expected":len(cells),"archived":len(completed),"remaining":len(incomplete),
            "remaining_ids":[r["run_id"] for r in incomplete],"next":first}

def checked_version(name, expected):
    exe=shutil.which(name)
    if not exe:
        raise RuntimeError("Required registered executable missing: "+name)
    proc=subprocess.run([exe,"--version"],capture_output=True,text=True,timeout=20)
    got=(proc.stdout or proc.stderr).strip()
    if proc.returncode!=0 or expected not in got:
        raise RuntimeError("%s version mismatch: expected %s, got %s" % (name,expected,got))
    return got

def cmd(args, *, cwd=None):
    subprocess.run(args,cwd=cwd,check=True)

def check_original_environment(kit):
    if sys.version_info[:2]!=(3,13):
        raise RuntimeError("Pinned study Python interpreter is 3.13")
    checked_version("claude",EXPECTED_CLAUDE)
    checked_version("specify",EXPECTED_SPECIFY)
    if not (kit/"tools/study/run_build.py").is_file():
        raise RuntimeError("Original frozen run_build.py not found")
    if not (kit/"tools/sddlog/sddlog.py").is_file():
        raise RuntimeError("Frozen sddlog.py not found")

def clone_for(cell, runs_root, base_repo):
    build=cell["build_id"]
    target=Path(runs_root)/build
    if cell["change"]:
        if not target.is_dir():
            raise RuntimeError("Change request must use the completed %s clone; not found: %s" %
                               (build,target))
        manifest=target/"logs"/"runs"/build/"manifest.json"
        if not manifest.is_file():
            raise RuntimeError("Original build manifest missing from change-request clone")
        data=json.loads(manifest.read_text())
        if data.get("status")!="completed" or data.get("run_id")!=build:
            raise RuntimeError("Change request would start from an incomplete build")
        if (target/"logs"/"runs"/cell["run_id"]).exists():
            raise RuntimeError("Run already started in this clone; inspect/resume it manually")
        if (target/"logs"/"ACTIVE_RUN").exists():
            raise RuntimeError("Existing active run must be resolved manually")
    else:
        if target.exists():
            raise RuntimeError("Fresh-build target already exists; inspect manually: "+str(target))
        if not Path(base_repo).is_dir():
            raise RuntimeError("Pinned base clone unavailable: "+str(base_repo))
        # Verify the registered base-v1 tag exists before creating a new run.
        cmd(["git","-C",str(base_repo),"rev-parse","--verify","refs/tags/base-v1"])
        target.parent.mkdir(parents=True,exist_ok=True)
        cmd(["git","clone","-q",str(base_repo),str(target)])
        cmd(["git","-C",str(target),"checkout","-q","-b","run/"+build,"base-v1"])
    if not (target/"tools/sddlog/sddlog.py").is_file():
        raise RuntimeError("Clone lacks frozen instrument")
    if cell["condition"]=="unstructured" and not cell["change"] and (target/".specify").exists():
        raise RuntimeError("Unstructured clone unexpectedly includes Spec Kit")
    if cell["change"] and cell["condition"]!="unstructured" and not (target/".specify").is_dir():
        raise RuntimeError("SDD change-request clone lost the original Spec Kit state")
    state=subprocess.run(["git","-C",str(target),"status","--porcelain"],
                         capture_output=True,text=True,timeout=20,check=True)
    if state.stdout.strip():
        raise RuntimeError("Run clone is dirty; do not modify or discard its pending changes")
    return target

def verify_after_run(kit, target, cell):
    manifest=target/"logs/runs"/cell["run_id"]/"manifest.json"
    if not manifest.is_file() or json.loads(manifest.read_text()).get("status")!="completed":
        raise RuntimeError("Runner did not close run as completed; do not archive or advance")
    cmd([sys.executable,str(target/"tools/sddlog/sddlog.py"),
         "--repo",str(target),"verify","--run-id",cell["run_id"]],cwd=target)
    # The frozen run_build.py records the run's closing commit.
    history=subprocess.run(["git","-C",str(target),"log","--format=%s","-n","40"],
                           capture_output=True,text=True,check=True)
    if "run "+cell["run_id"]+" closed" not in history.stdout.splitlines():
        raise RuntimeError("Run closure commit not found; archiving refused")
    dest=kit/"logs"/"runs"/cell["run_id"]
    if dest.exists():
        raise RuntimeError("Archive destination exists; refusing overwrite: "+str(dest))
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(target/"logs"/"runs"/cell["run_id"],dest)
    bundles=kit/"logs"/"bundles"
    bundles.mkdir(parents=True,exist_ok=True)
    bundle=bundles/(cell["build_id"]+".bundle")
    temp=bundles/(cell["build_id"]+".bundle.tmp")
    if temp.exists():
        raise RuntimeError("Existing temporary bundle; inspect before resuming")
    try:
        cmd(["git","-C",str(target),"bundle","create",str(temp),"--all"])
        cmd(["git","-C",str(target),"bundle","verify",str(temp)])
        os.replace(temp,bundle)
    finally:
        if temp.exists():temp.unlink()
    return str(dest),str(bundle)

def run_next(kit,runs_root,base_repo,configs,cell):
    if not sys.stdin.isatty():
        raise RuntimeError("The original operator must be present at a real interactive terminal")
    if (Path(configs)/cell["run_id"]).exists():
        raise RuntimeError("Existing Claude config for run; inspect rather than restart: "+cell["run_id"])
    check_original_environment(kit)
    target=clone_for(cell,runs_root,base_repo)
    print("Running the frozen model/harness. Classify questions only per RUNBOOK and answer sheets.",flush=True)
    argv=[sys.executable,str(kit/"tools"/"study"/"run_build.py"),cell["run_id"],
          "--kit",str(kit),"--clean-env",str(configs)]
    status=subprocess.run(argv,cwd=target).returncode
    if status:
        raise RuntimeError("Frozen runner stopped (exit %s); preserve its logs and resume per RUNBOOK" % status)
    dest,bundle=verify_after_run(kit,target,cell)
    print("Archived verified logs at %s and bundle at %s" % (dest,bundle),flush=True)
    print("REQUIRED: update schedule/run-log.md with actual answers, follow-ups and costs, then commit/push archives.",flush=True)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kit",type=Path,default=KIT)
    p.add_argument("--evidence-root",type=Path,help="Directory with the latest archived logs; defaults to kit")
    p.add_argument("--runs-root",type=Path,default=Path.home()/"sdd-study/runs")
    p.add_argument("--base-repo",type=Path,default=Path.home()/"sdd-study/base")
    p.add_argument("--clean-env",type=Path,default=Path.home()/"sdd-study/claude-configs")
    p.add_argument("--execute",action="store_true",help="Execute next run in original Claude Code workspace")
    p.add_argument("--all",action="store_true",help="Sequentially execute remaining runs with operator supervision")
    p.add_argument("--json-out",type=Path)
    args=p.parse_args(argv)
    kit=args.kit.resolve()
    evidence_root=(args.evidence_root or kit).resolve()
    status=overview(kit/"schedule/schedule.csv",evidence_root)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(json.dumps(status,indent=2)+"\n")
    print(json.dumps(status,indent=2))
    if not args.execute:
        print("Read-only inventory; no experiment was started.")
        return 0
    if evidence_root!=kit:
        print("--execute requires evidence-root equal to kit, so archives update in place",file=sys.stderr)
        return 2
    if args.all and not sys.stdin.isatty():
        print("--all requires continuous interactive operator supervision",file=sys.stderr)
        return 2
    try:
        while status["next"]:
            run_next(kit,args.runs_root.resolve(),args.base_repo.resolve(),
                     args.clean_env.resolve(),status["next"])
            status=overview(kit/"schedule/schedule.csv",kit)
            if not args.all:break
        print("Runs remaining:",status["remaining"],"(the held-out suites remain sealed).")
        return 0
    except (RuntimeError,OSError,subprocess.CalledProcessError,ValueError) as exc:
        print("STOP (no further runs started):",exc,file=sys.stderr)
        return 2
if __name__=="__main__":
    raise SystemExit(main())
