#!/usr/bin/env python3
"""Score one run's repository against the sealed held-out suites (Part III).

Runs the three tiers for the run's task as separate pytest sessions and writes
one JSON file with per-test outcomes, so every number in the analysis traces
back to a named test.

  tier A  stated     behaviour written in TASK.md            -> RQ1 correctness
  tier B  intent     answers from the product-owner sheet    -> RQ4 (clarify)
  tier C  security   CWE-mapped probes                       -> RQ1 security

Usage:
  python3 tools/study/score_run.py --task T-REDACT-01 --repo runs/R004 \
      --heldout ../sealed/heldout --out scores/R004.json
  python3 tools/study/score_run.py --hash-only --heldout ../sealed/heldout

Standard library only, apart from pytest itself (needed to run the suites).
"""

import argparse
import ast
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

TIERS = [("stated", "test_stated.py"), ("intent", "test_intent.py"), ("security", "test_security.py")]
TIER_TIMEOUT = 900  # seconds per tier; a hung SUT is killed by the per-test timeouts first
# Paths in a run's repository that are not the agent's product code.
SAST_EXCLUDES = ["tests", "test", "logs", "tools", ".specify", ".claude", "specs", ".venv", "venv"]


def tree_hash(root):
    """SHA-256 over every file's relative path and bytes, in sorted order.

    Independent of zip metadata and timestamps, so the hash recorded in the
    pre-registration can be re-checked against an unpacked copy at any time.
    Bytecode caches are ignored.
    """
    root = Path(root)
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if "__pycache__" in rel.split("/") or rel.endswith(".pyc"):
            continue
        digest.update(rel.encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def sloc(path):
    """Non-blank, non-comment source lines, excluding docstrings."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
        return 0
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(
                    getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
                skip.update(range(body[0].lineno, body[0].end_lineno + 1))
    return sum(1 for number, line in enumerate(source.splitlines(), 1)
               if number not in skip and line.strip() and not line.strip().startswith("#"))


def code_size(repo):
    """Product vs. test Python source size in the run's final repository state."""
    product = tests = 0
    files = {"product": 0, "test": 0}
    for path in repo.rglob("*.py"):
        parts = path.relative_to(repo).parts
        if any(p.startswith(".") for p in parts) or parts[0] in ("logs", "tools", "specs", "venv"):
            continue
        is_test = any(p in ("tests", "test") for p in parts[:-1]) or parts[-1].startswith("test_") \
            or parts[-1] == "conftest.py"
        if is_test:
            tests += sloc(path)
            files["test"] += 1
        else:
            product += sloc(path)
            files["product"] += 1
    return {"product_sloc": product, "test_sloc": tests,
            "product_files": files["product"], "test_files": files["test"]}


def interpreter_version(python):
    out = subprocess.run([python, "-c", "import sys; print(sys.version.split()[0])"],
                         capture_output=True, text=True)
    return out.stdout.strip() or None


def parse_junit(path):
    tests = []
    tree = ET.parse(path)
    for case in tree.iter("testcase"):
        name = case.get("name")
        outcome, message = "passed", ""
        for tag in ("failure", "error", "skipped"):
            node = case.find(tag)
            if node is not None:
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                message = (node.get("message") or node.text or "").strip().splitlines()[:1]
                message = message[0][:300] if message else ""
                break
        tests.append({"test": name, "outcome": outcome, "message": message,
                      "time_s": round(float(case.get("time") or 0), 2)})
    return tests


def run_tier(heldout, task, filename, repo, python):
    suite = Path(heldout) / task / filename
    with tempfile.TemporaryDirectory() as tmp:
        xml_path = Path(tmp) / "junit.xml"
        env = dict(os.environ, SUT_REPO=str(repo), SUT_PYTHON=python)
        cmd = [sys.executable, "-m", "pytest", str(suite), "-q", "-rN",
               "--junitxml", str(xml_path), "-o", "junit_family=xunit2"]
        try:
            proc = subprocess.run(cmd, cwd=str(heldout), env=env, capture_output=True,
                                  text=True, timeout=TIER_TIMEOUT)
            harness_note = None if xml_path.exists() else proc.stdout[-2000:] + proc.stderr[-2000:]
        except subprocess.TimeoutExpired:
            harness_note = "tier exceeded %ss and was killed" % TIER_TIMEOUT
        tests = parse_junit(xml_path) if xml_path.exists() else []
    counted = [t for t in tests if t["outcome"] != "skipped"]
    passed = sum(1 for t in counted if t["outcome"] == "passed")
    return {
        "passed": passed,
        "total": len(counted),
        "skipped": len(tests) - len(counted),
        "pass_rate": round(passed / len(counted), 4) if counted else None,
        "harness_note": harness_note,
        "tests": tests,
    }


def run_bandit(repo):
    """Static analysis with Bandit over the product code only (pre-registered SAST)."""
    excludes = ",".join(str(repo / name) for name in SAST_EXCLUDES)
    cmd = [sys.executable, "-m", "bandit", "-r", str(repo), "-x", excludes, "-f", "json", "-q"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        return {"error": (proc.stderr or proc.stdout)[-1000:] or "bandit produced no JSON (installed?)"}
    version = subprocess.run([sys.executable, "-m", "bandit", "--version"], capture_output=True,
                             text=True).stdout.split()[1:2]
    findings = []
    for item in report.get("results", []):
        cwe = (item.get("issue_cwe") or {}).get("id")
        findings.append({
            "test_id": item.get("test_id"),
            "severity": item.get("issue_severity"),
            "confidence": item.get("issue_confidence"),
            "cwe": "CWE-%s" % cwe if cwe else None,
            "file": os.path.relpath(item.get("filename", ""), str(repo)),
            "line": item.get("line_number"),
            "message": item.get("issue_text"),
        })
    return {"tool": "bandit", "version": version[0] if version else None,
            "excluded": SAST_EXCLUDES, "findings": findings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--heldout", required=True, help="path to the unsealed heldout/ directory")
    parser.add_argument("--task", help="task id, e.g. T-REDACT-01")
    parser.add_argument("--repo", help="root of the run's repository")
    parser.add_argument("--run-id", default=None, help="run id to record in the output")
    parser.add_argument("--out", help="output JSON path")
    parser.add_argument("--python", default=sys.executable,
                        help="interpreter used to run the SUT (pre-registered: 3.13.x)")
    parser.add_argument("--hash-only", action="store_true", help="print the suite's tree hash and exit")
    parser.add_argument("--sast", action="store_true",
                        help="also run Bandit over the product code and record its findings")
    args = parser.parse_args(argv)

    heldout = Path(args.heldout).resolve()
    if args.hash_only:
        print(tree_hash(heldout))
        return 0
    if not (args.task and args.repo):
        parser.error("--task and --repo are required unless --hash-only is given")
    if not (heldout / args.task).is_dir():
        parser.error("no held-out suite for %s under %s" % (args.task, heldout))

    repo = Path(args.repo).resolve()
    result = {
        "run_id": args.run_id,
        "task_id": args.task,
        "repo": str(repo),
        "scored_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "heldout_tree_sha256": tree_hash(heldout),
        "sut_python": interpreter_version(args.python),
        "code_size": code_size(repo),
        "tiers": {},
    }
    for tier, filename in TIERS:
        result["tiers"][tier] = run_tier(heldout, args.task, filename, repo, args.python)
    if args.sast:
        result["sast"] = run_bandit(repo)

    text = json.dumps(result, indent=2) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
    width = max(len(t) for t, _ in TIERS)
    size = result["code_size"]
    print("%s  %s  (python %s; %d product / %d test lines)" % (
        args.run_id or "-", args.task, result["sut_python"], size["product_sloc"], size["test_sloc"]))
    for tier, _ in TIERS:
        data = result["tiers"][tier]
        rate = "-" if data["pass_rate"] is None else "%.0f%%" % (100 * data["pass_rate"])
        print("  %-*s  %3d/%-3d  %5s%s" % (width, tier, data["passed"], data["total"], rate,
                                           "  NOTE: harness problem" if data["harness_note"] else ""))
        for t in data["tests"]:
            if t["outcome"] in ("failed", "error"):
                print("      x %s" % t["test"])
    if args.sast:
        sast = result["sast"]
        if "error" in sast:
            print("  sast      ERROR: %s" % sast["error"][:200])
        else:
            print("  sast      %d Bandit finding(s)" % len(sast["findings"]))
            for f in sast["findings"]:
                print("      ! %s %s %s %s:%s" % (f["test_id"], f["severity"], f["cwe"], f["file"], f["line"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
