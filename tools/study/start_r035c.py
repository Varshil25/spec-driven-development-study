#!/usr/bin/env python3
"""Guarded hand-off for R035C. Never modifies the frozen study apparatus."""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

def version(command):
    p=shutil.which(command)
    if not p:return None
    try:
        x=subprocess.run([p,"--version"],capture_output=True,text=True,timeout=20)
        return (x.stdout or x.stderr).strip() if x.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):return None

def check(kit,run,configs,check_programs=True):
    problems=[]
    try:
        with (kit/"schedule/schedule.csv").open(newline="",encoding="utf-8") as stream:
            schedule={r["run_id"]:r for r in csv.DictReader(stream)}
        row=schedule.get("R035",{})
        if (row.get("task_id"),row.get("condition"),row.get("purpose"))!=("T-TARX-01","sdd_clarify","study"):
            problems.append("R035 does not match the frozen schedule")
    except OSError:problems.append("Frozen schedule unavailable")
    for relative in ("tools/study/run_build.py","tasks/T-TARX-01-CR/prompt.md",
                     "operator/answer-sheets/T-TARX-01-CR.md",
                     "operator/answer-sheets/T-TARX-01.md"):
        if not (kit/relative).is_file():problems.append("Missing frozen kit input: "+relative)
    if not run.is_dir():problems.append("Original R035 experiment clone unavailable")
    else:
        for p in (".git",".specify","tools/sddlog/sddlog.py","logs/runs/R035/manifest.json"):
            if not (run/p).exists():problems.append("Original clone missing "+p)
        manifest=run/"logs/runs/R035/manifest.json"
        if manifest.is_file():
            try:
                m=json.loads(manifest.read_text())
                if tuple(m.get(k) for k in ("run_id","task_id","condition","status"))!=(
                    "R035","T-TARX-01","sdd_clarify","completed"):
                    problems.append("R035 manifest does not confirm completed build")
            except (OSError,ValueError):problems.append("R035 manifest invalid")
        if (run/"logs/runs/R035C").exists():problems.append("R035C already started; inspect/resume, do not duplicate")
        if (run/"logs/ACTIVE_RUN").exists():problems.append("Clone has an active run")
        if (configs/"R035C").exists():problems.append("Existing R035C Claude configuration; inspect before restarting")
        if (run/".git").exists():
            try:
                status=subprocess.run(["git","-C",str(run),"status","--porcelain"],capture_output=True,text=True,timeout=20)
                history=subprocess.run(["git","-C",str(run),"log","-n","35","--format=%s"],capture_output=True,text=True,timeout=20)
                if status.returncode or status.stdout.strip():problems.append("Original clone has uncommitted changes")
                if history.returncode or "run R035 closed" not in history.stdout.splitlines():
                    problems.append("R035 closure commit missing")
            except (OSError,subprocess.TimeoutExpired):problems.append("Git validation unavailable")
    if sys.version_info[:2]!=(3,13):problems.append("Python 3.13 required")
    versions={}
    if check_programs:
        versions={"claude":version("claude"),"specify":version("specify")}
        if not versions["claude"] or "2.1.317" not in versions["claude"]:
            problems.append("Pinned Claude Code 2.1.317 not available")
        if not versions["specify"] or "1.0.6" not in versions["specify"]:
            problems.append("Pinned Spec Kit 1.0.6 not available")
    cmd=[sys.executable,str(kit/"tools/study/run_build.py"),"R035C","--kit",str(kit),
         "--clean-env",str(configs)]
    return {"status":"ready" if not problems else "blocked","run":"R035C",
            "clone":str(run),"versions":versions,"problems":problems,"command":cmd}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kit",type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument("--run-dir",type=Path,default=Path.home()/"sdd-study/runs/R035")
    p.add_argument("--clean-env",type=Path,default=Path.home()/"sdd-study/claude-configs")
    p.add_argument("--execute",action="store_true")
    a=p.parse_args()
    status=check(a.kit.resolve(),a.run_dir.resolve(),a.clean_env.resolve())
    print(json.dumps(status,indent=2))
    if status["problems"]:return 2
    if not a.execute:
        print("DRY RUN only. Use --execute in original operator terminal after review.")
        return 0
    if not sys.stdin.isatty():
        print("Operator session must have an interactive terminal",file=sys.stderr)
        return 2
    return subprocess.call(status["command"],cwd=str(a.run_dir))
if __name__=="__main__":raise SystemExit(main())
