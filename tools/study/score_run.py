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

Java/Quarkus runs (a pom.xml at the repository root) are scored the same way
against the Java suites (`--heldout sealed/heldout-java`), with three
differences:
  * the repository is built once first (`./mvnw -q -B -DskipTests clean
    package`); a failed build scores 0 on every tier;
  * source size counts .java lines (product under src/main, tests under
    src/test);
  * `--sast` runs SpotBugs with the FindSecBugs plugin over the compiled
    classes (`--spotbugs-lib tools/study/java-sast/lib`, fetched by
    tools/study/java-sast/fetch.sh) and keeps the SECURITY category only.

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
import time
import xml.etree.ElementTree as ET
from pathlib import Path

TIERS = [("stated", "test_stated.py"), ("intent", "test_intent.py"), ("security", "test_security.py")]
TIER_TIMEOUT = 900  # seconds per tier; a hung SUT is killed by the per-test timeouts first
# Paths in a run's repository that are not the agent's product code.
SAST_EXCLUDES = ["tests", "test", "logs", "tools", ".specify", ".claude", "specs", ".venv", "venv"]
JAVA_BUILD_TIMEOUT = 1200
JAVA_JAR = Path("target") / "quarkus-app" / "quarkus-run.jar"
JAVA_SAST_CATEGORIES = ["SECURITY"]
JAVA_SKIP_DIRS = {"target", "logs", "tools", "specs", "node_modules"}


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


def java_sloc(path):
    """Non-blank lines that are not wholly comments (// and /* ... */)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    count, in_block = 0, False
    for raw in text.splitlines():
        line = raw.strip()
        while line:
            if in_block:
                end = line.find("*/")
                if end < 0:
                    line = ""
                    break
                line = line[end + 2:].strip()
                in_block = False
                continue
            if line.startswith("//"):
                line = ""
            elif line.startswith("/*"):
                in_block = True
                line = line[2:]
                continue
            break
        if line:
            count += 1
    return count


def java_code_size(repo):
    """Product vs. test Java source size in the run's final repository state."""
    product = tests = 0
    files = {"product": 0, "test": 0}
    for path in repo.rglob("*.java"):
        parts = path.relative_to(repo).parts
        if any(p.startswith(".") or p in JAVA_SKIP_DIRS for p in parts[:-1]):
            continue
        is_test = "test" in parts[:-1] and "src" in parts[:-1] or parts[-1].endswith(("Test.java", "IT.java"))
        if is_test:
            tests += java_sloc(path)
            files["test"] += 1
        else:
            product += java_sloc(path)
            files["product"] += 1
    return {"product_sloc": product, "test_sloc": tests,
            "product_files": files["product"], "test_files": files["test"]}


def is_java(repo):
    return (repo / "pom.xml").is_file()


def java_version(java):
    try:
        out = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = [l for l in (out.stderr + out.stdout).splitlines() if "version" in l]
    return lines[0].strip() if lines else None


def build_java(repo):
    """One clean build per scored run; every tier then tests the same artefact."""
    wrapper = repo / "mvnw"
    command, shown = (["sh", str(wrapper)], "./mvnw") if wrapper.is_file() else (["mvn"], "mvn")
    args = ["-q", "-B", "-DskipTests", "clean", "package"]
    started = time.time()
    try:
        proc = subprocess.run(command + args, cwd=str(repo), capture_output=True, text=True,
                              timeout=JAVA_BUILD_TIMEOUT)
        code, output = proc.returncode, proc.stdout + proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        code, output = None, str(exc)
    ok = code == 0 and (repo / JAVA_JAR).is_file()
    errors = [l.strip() for l in output.splitlines() if l.strip().startswith("[ERROR]")]
    return {"ok": ok, "command": "%s %s" % (shown, " ".join(args)), "exit": code,
            "seconds": round(time.time() - started, 1),
            "error": None if ok else (errors[0] if errors else output.strip()[-500:])}


def collected(heldout, task, filename):
    """Number of test cases in a tier (used when a build failure means none can run)."""
    proc = subprocess.run([sys.executable, "-m", "pytest", str(Path(heldout) / task / filename),
                           "--collect-only", "-q"], cwd=str(heldout), capture_output=True, text=True)
    return sum(1 for line in proc.stdout.splitlines() if "::" in line)


def run_spotbugs(repo, lib_dir, java):
    """SpotBugs + FindSecBugs over the run's compiled product classes (pre-registered Java SAST)."""
    lib = Path(lib_dir) if lib_dir else None
    if not lib or not lib.is_dir():
        return {"error": "no SpotBugs jars at %s (run tools/study/java-sast/fetch.sh)" % lib_dir}
    jars = sorted(lib.glob("*.jar"))
    plugins = [j for j in jars if j.name.startswith("findsecbugs-plugin-")]
    engine = [j for j in jars if j.name.startswith("spotbugs-")]
    if not plugins or not engine:
        return {"error": "SpotBugs or FindSecBugs jar missing from %s" % lib}
    classes = repo / "target" / "classes"
    if not classes.is_dir():
        return {"error": "no compiled classes at %s" % classes}
    aux = sorted((repo / "target" / "quarkus-app" / "lib" / "main").glob("*.jar"))
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "spotbugs.xml"
        cmd = [java, "-cp", os.pathsep.join(str(j) for j in jars if j not in plugins),
               "edu.umd.cs.findbugs.FindBugs2", "-xml:withMessages", "-output", str(out),
               "-effort:max", "-low", "-pluginList", str(plugins[0])]
        if aux:
            cmd += ["-auxclasspath", os.pathsep.join(str(j) for j in aux)]
        cmd.append(str(classes))
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"error": str(exc)}
        if not out.is_file():
            return {"error": (proc.stderr or proc.stdout)[-1000:] or "SpotBugs wrote no report"}
        root = ET.parse(out).getroot()
    severity = {"1": "HIGH", "2": "MEDIUM", "3": "LOW"}
    findings = []
    for bug in root.iter("BugInstance"):
        if bug.get("category") not in JAVA_SAST_CATEGORIES:
            continue
        line = bug.find("SourceLine")
        cwe = bug.get("cweid")
        findings.append({
            "test_id": bug.get("type"),
            "severity": severity.get(bug.get("priority"), bug.get("priority")),
            "confidence": bug.get("rank"),
            "cwe": "CWE-%s" % cwe if cwe and cwe != "0" else None,
            "file": line.get("sourcepath") if line is not None else None,
            "line": line.get("start") if line is not None else None,
            "message": (bug.findtext("ShortMessage") or "").strip(),
        })
    return {"tool": "spotbugs+findsecbugs", "version": root.get("version"),
            "plugin": plugins[0].name, "categories": JAVA_SAST_CATEGORIES, "findings": findings}


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


def run_tier(heldout, task, filename, repo, python, java="java"):
    suite = Path(heldout) / task / filename
    with tempfile.TemporaryDirectory() as tmp:
        xml_path = Path(tmp) / "junit.xml"
        env = dict(os.environ, SUT_REPO=str(repo), SUT_PYTHON=python, SUT_JAVA=java)
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
                        help="also run static analysis (Bandit, or SpotBugs for Java runs) and record its findings")
    parser.add_argument("--java", default="java", help="java launcher for Java runs (default: java)")
    parser.add_argument("--spotbugs-lib", default=str(Path(__file__).resolve().parent / "java-sast" / "lib"),
                        help="directory holding the SpotBugs and FindSecBugs jars (Java runs)")
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
    java = is_java(repo)
    result = {
        "run_id": args.run_id,
        "task_id": args.task,
        "repo": str(repo),
        "scored_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "heldout_tree_sha256": tree_hash(heldout),
        "sut_python": None if java else interpreter_version(args.python),
        "code_size": java_code_size(repo) if java else code_size(repo),
        "tiers": {},
    }
    if java:
        result["sut_java"] = java_version(args.java)
        result["build"] = build_java(repo)
    for tier, filename in TIERS:
        if java and not result["build"]["ok"]:
            total = collected(heldout, args.task, filename)
            result["tiers"][tier] = {"passed": 0, "total": total, "skipped": 0,
                                     "pass_rate": 0.0 if total else None,
                                     "harness_note": "build failed; every test counts as failed",
                                     "tests": []}
            continue
        result["tiers"][tier] = run_tier(heldout, args.task, filename, repo, args.python, args.java)
    if args.sast:
        if java:
            result["sast"] = (run_spotbugs(repo, args.spotbugs_lib, args.java) if result["build"]["ok"]
                              else {"error": "build failed; nothing to analyse"})
        else:
            result["sast"] = run_bandit(repo)

    text = json.dumps(result, indent=2) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
    width = max(len(t) for t, _ in TIERS)
    size = result["code_size"]
    runtime = ("java %s" % result.get("sut_java")) if java else ("python %s" % result["sut_python"])
    print("%s  %s  (%s; %d product / %d test lines)" % (
        args.run_id or "-", args.task, runtime, size["product_sloc"], size["test_sloc"]))
    if java:
        build = result["build"]
        print("  build     %s in %ss%s" % ("ok" if build["ok"] else "FAILED", build["seconds"],
                                          "" if build["ok"] else ": %s" % (build["error"] or "")[:200]))
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
            print("  sast      %d %s finding(s)" % (len(sast["findings"]),
                                            "SpotBugs" if java else "Bandit"))
            for f in sast["findings"]:
                print("      ! %s %s %s %s:%s" % (f["test_id"], f["severity"], f["cwe"], f["file"], f["line"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
