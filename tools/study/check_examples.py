#!/usr/bin/env python3
"""Stopping-rule check: run a task's examples against a run's repository.

This is the pre-registered definition of "done" for every condition. After
the agent says it has finished (or after each follow-up), the operator runs:

    python3 <kit>/tools/study/check_examples.py T-REDACT-01 --repo .

If every example behaves as the task description shows, the run is done.
Otherwise the script prints a follow-up message in fixed wording, which the
operator pastes to the agent verbatim. Fixed wording keeps the operator's own
phrasing (and any hints) out of the data.

The examples are the ones printed in the task's prompt.md, nothing more, so
the agent can see everything this check tests. The held-out suites are far
larger and stay sealed.

Java/Quarkus tasks (examples.json has "runtime": "quarkus") are built first
with the repository's Maven wrapper (`./mvnw -q -B -DskipTests clean package`, or
`mvn` if the wrapper is missing), then started exactly as the task text says:

    java -Dquarkus.http.host=127.0.0.1 -Dquarkus.http.port=PORT \
         -D<data_property>=DIR -jar target/quarkus-app/quarkus-run.jar

A Quarkus service counts as started once its port accepts connections, since
the task text does not promise any particular log line. A failed build is
reported to the agent in fixed wording, like any failing example.

Standard library only. Exit status: 0 all examples pass, 1 some fail,
2 usage or setup error.
"""

import argparse
import gzip
import http.client
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
TIMEOUT = 30
BUILD_TIMEOUT = 900       # seconds for the Maven build of a Quarkus task
QUARKUS_START_TIMEOUT = 60
QUARKUS_JAR = Path("target") / "quarkus-app" / "quarkus-run.jar"


def sut_env(repo):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(repo / "src"), str(repo)])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def short(text, limit=200):
    text = text if isinstance(text, str) else repr(text)
    text = text.replace("\t", "<TAB>")
    return text if len(text) <= limit else text[:limit] + "..."


def build_fixtures(spec, workdir):
    for name, content in spec.get("files", {}).items():
        (workdir / name).write_text(content)
    for archive in spec.get("archives", []):
        path = workdir / archive["name"]
        with tarfile.open(path, "w:gz" if archive.get("gzip") else "w") as tar:
            for member in archive["members"]:
                data = member["data"].encode("utf-8")
                info = tarfile.TarInfo(member["name"])
                info.size = len(data)
                info.mtime = 1_600_000_000
                tar.addfile(info, io.BytesIO(data))


def check_cli(spec, repo, workdir, python):
    failures = []
    for example in spec["examples"]:
        stdin = example.get("stdin")
        try:
            proc = subprocess.run([python, "-m", spec["package"]] + example["args"],
                                  input=stdin.encode("utf-8") if stdin is not None else b"",
                                  capture_output=True, cwd=str(workdir), env=sut_env(repo),
                                  timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            failures.append((example, "it did not finish within %d seconds" % TIMEOUT))
            continue
        out = proc.stdout.decode("utf-8", "replace")
        err = proc.stderr.decode("utf-8", "replace")
        expect = example["expect"]
        problems = []
        if "exit" in expect and proc.returncode != expect["exit"]:
            problem = "exit status %d instead of %d" % (proc.returncode, expect["exit"])
            if err.strip() and "stderr_contains" not in expect:
                problem += " (its error output was %r)" % short(err.strip().splitlines()[-1])
            problems.append(problem)
        if expect.get("exit_nonzero") and proc.returncode == 0:
            problems.append("exit status 0 instead of a non-zero status")
        if "stdout" in expect and out != expect["stdout"]:
            problems.append("standard output was %r instead of %r"
                            % (short(out), short(expect["stdout"])))
        if "stderr_contains" in expect and expect["stderr_contains"] not in err:
            problems.append("standard error did not contain %r (it was %r)"
                            % (expect["stderr_contains"], short(err)))
        if expect.get("stderr_nonempty") and not err.strip():
            problems.append("nothing was printed to standard error")
        if problems:
            failures.append((example, "; ".join(problems)))
        print("%s  %s" % ("FAIL" if problems else "ok  ", example["show"]))
    return failures


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def maven_command(repo):
    """The repository's Maven wrapper if it has one, else `mvn` from PATH."""
    wrapper = repo / "mvnw"
    if wrapper.is_file():
        return ["sh", str(wrapper)], "./mvnw"
    return ["mvn"], "mvn"


def build_quarkus(repo):
    """Build a Quarkus task's repository. Returns None on success, else a failure."""
    command, shown = maven_command(repo)
    show = "%s package" % shown
    print("build %s -q -B -DskipTests clean package ..." % shown, flush=True)
    try:
        proc = subprocess.run(command + ["-q", "-B", "-DskipTests", "clean", "package"], cwd=str(repo),
                              capture_output=True, timeout=BUILD_TIMEOUT)
    except FileNotFoundError:
        return ({"show": show}, "the build could not run: %s was not found" % shown)
    except subprocess.TimeoutExpired:
        return ({"show": show}, "the build did not finish within %d seconds" % BUILD_TIMEOUT)
    output = (proc.stdout + proc.stderr).decode("utf-8", "replace")
    if proc.returncode != 0:
        errors = [line.strip() for line in output.splitlines() if line.strip().startswith("[ERROR]")]
        detail = errors[0] if errors else (output.strip().splitlines() or ["(no output)"])[-1]
        return ({"show": show}, "the build failed (%s)" % short(detail, 300))
    if not (repo / QUARKUS_JAR).is_file():
        return ({"show": show}, "the build succeeded but %s was not produced" % QUARKUS_JAR.as_posix())
    return None


def start_server(spec, repo, workdir, python, port, out, err, java="java"):
    """Start the system under test.

    Returns (process, command as shown to the agent, readiness test,
    start timeout in seconds, reason to give if it never becomes ready).
    """
    if spec.get("runtime") == "quarkus":
        data = workdir / "data"
        args = ["-Dquarkus.http.host=127.0.0.1", "-Dquarkus.http.port=%d" % port,
                "-D%s=%s" % (spec["data_property"], data), "-jar", str(repo / QUARKUS_JAR)]
        proc = subprocess.Popen([java] + args, cwd=str(workdir), stdout=out, stderr=err)
        shown = "java -Dquarkus.http.host=127.0.0.1 -Dquarkus.http.port=%d -D%s=DIR -jar %s" % (
            port, spec["data_property"], QUARKUS_JAR.as_posix())
        return proc, shown, (lambda: port_open(port)), QUARKUS_START_TIMEOUT, \
            "it did not accept connections on port %d" % port
    args = [a.replace("{port}", str(port)) for a in spec["server_args"]]
    env = sut_env(repo)
    env.update(spec.get("server_env", {}))
    proc = subprocess.Popen([python, "-m", spec["package"]] + args, cwd=str(workdir),
                            env=env, stdout=out, stderr=err)
    ready_line = spec["ready_line"].replace("{port}", str(port))
    out_path = Path(out.name)
    return proc, "python -m %s %s" % (spec["package"], " ".join(args)), \
        (lambda: ready_line in out_path.read_text(errors="replace")), 15, \
        "the line %r never appeared on standard output" % ready_line


def json_subset_problems(expected, actual, where="the JSON response"):
    """Every key in `expected` must be in `actual` with an equal value."""
    if not isinstance(actual, dict):
        return ["%s was not a JSON object" % where]
    problems = []
    for key, value in expected.items():
        if key not in actual:
            problems.append("%s has no %r" % (where, key))
        elif actual[key] != value:
            problems.append("%s has %r = %s instead of %s" % (
                where, key, short(json.dumps(actual[key])), json.dumps(value)))
    return problems


def check_http(spec, repo, workdir, python, java="java"):
    failures = []
    if spec.get("setup"):
        failures += check_cli({"package": spec["package"], "examples": spec["setup"]},
                              repo, workdir, python)
    port = free_port()
    out_path, err_path = workdir / "server.out", workdir / "server.err"
    with open(out_path, "wb") as out, open(err_path, "wb") as err:
        proc, shown, is_ready, start_timeout, not_ready = start_server(
            spec, repo, workdir, python, port, out, err, java)
    try:
        deadline = time.time() + start_timeout
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if is_ready():
                ready = True
                break
            time.sleep(0.1)
        if not ready:
            reason = "the server exited" if proc.poll() is not None else not_ready
            if spec.get("runtime") == "quarkus":
                # The JVM and Quarkus log to standard output, so show the end of both streams.
                log = (err_path.read_text(errors="replace") + out_path.read_text(errors="replace"))[-500:]
                detail = ("; its output ended with %r" % short(log)) if log.strip() else ""
            else:
                log = err_path.read_text(errors="replace")[-500:]
                detail = ("; its error output was %r" % short(log)) if log.strip() else ""
            failures.append(({"show": shown}, "the server did not start: %s%s" % (reason, detail)))
            print("FAIL  server start")
            return failures
        print("ok    server start")
        captured = {}
        for example in spec["examples"]:
            path = example["path"]
            headers = dict(example.get("headers", {}))
            for key, value in captured.items():
                path = path.replace("{%s}" % key, value)
                headers = {h: v.replace("{%s}" % key, value) for h, v in headers.items()}
            body = example.get("body")
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=TIMEOUT)
            problems = []
            try:
                conn.request(example["method"], path,
                             body=body.encode("utf-8") if body is not None else None,
                             headers=headers)
                resp = conn.getresponse()
                status, data = resp.status, resp.read()
                resp_headers = resp.getheaders()
            except (OSError, http.client.HTTPException) as exc:
                failures.append((example, "the request failed: %s" % exc))
                print("FAIL  %s" % example["show"])
                continue
            finally:
                conn.close()
            text = data.decode("utf-8", "replace")
            expect = example["expect"]
            if status != expect["status"]:
                problems.append("status %d instead of %d (body %r)" % (status, expect["status"], short(text)))
            if "body" in expect and text != expect["body"]:
                problems.append("body was %r instead of %r" % (short(text), expect["body"]))
            if "body_contains" in expect and expect["body_contains"] not in text:
                problems.append("the page did not contain %r" % expect["body_contains"])
            if "location" in expect:
                location = dict((k.lower(), v) for k, v in resp_headers).get("location")
                if location != expect["location"]:
                    problems.append("Location header was %r instead of %r" % (location, expect["location"]))
            cookies = {}
            for name, value in resp_headers:
                if name.lower() == "set-cookie" and "=" in value:
                    cname, _, rest = value.partition("=")
                    cookies[cname.strip()] = rest.split(";", 1)[0].strip()
            if expect.get("set_cookie") and not cookies.get(expect["set_cookie"]):
                problems.append("no %r cookie was set" % expect["set_cookie"])
            for name in example.get("capture_cookies", []):
                captured[name] = cookies.get(name, "")
            if "json_keys" in expect:
                try:
                    parsed = json.loads(text)
                    missing = [k for k in expect["json_keys"] if k not in parsed]
                    if missing:
                        problems.append("the JSON response has no %s" % ", ".join(missing))
                    for name, key in example.get("capture", {}).items():
                        captured[name] = str(parsed.get(key, ""))
                except (ValueError, AttributeError):
                    problems.append("the response was not a JSON object: %r" % short(text))
            if "json_subset" in expect:
                try:
                    problems += json_subset_problems(expect["json_subset"], json.loads(text))
                except ValueError:
                    problems.append("the response was not valid JSON: %r" % short(text))
                else:
                    if "json_keys" not in expect:
                        parsed = json.loads(text)
                        for name, key in example.get("capture", {}).items():
                            captured[name] = str(parsed.get(key, "")) if isinstance(parsed, dict) else ""
            if "contains_in_order" in expect:
                position = 0
                for item in expect["contains_in_order"]:
                    found = text.find(item, position)
                    if found < 0:
                        problems.append("the response did not contain %s in that order" % ", ".join(
                            repr(i) for i in expect["contains_in_order"]))
                        break
                    position = found + len(item)
            if problems:
                failures.append((example, "; ".join(problems)))
            print("%s  %s" % ("FAIL" if problems else "ok  ", example["show"]))
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return failures


def follow_up(failures):
    lines = ["I ran the examples from the task description. These did not behave as described:", ""]
    for number, (example, problem) in enumerate(failures, 1):
        lines.append("%d. `%s`: %s." % (number, example["show"], problem))
    lines += ["", "Please fix the implementation."]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("task", help="task id, e.g. T-REDACT-01")
    parser.add_argument("--repo", default=".", help="root of the run's repository (default: .)")
    parser.add_argument("--python", default=sys.executable, help="interpreter to run the code with")
    parser.add_argument("--java", default="java", help="java launcher for Quarkus tasks (default: java)")
    args = parser.parse_args(argv)

    spec_path = KIT / "tasks" / args.task / "examples.json"
    if not spec_path.exists():
        print("no examples defined for %s (%s)" % (args.task, spec_path), file=sys.stderr)
        return 2
    spec = json.loads(spec_path.read_text())
    repo = Path(args.repo).resolve()
    workdir = Path(tempfile.mkdtemp(prefix="examples-"))
    try:
        build_fixtures(spec, workdir)
        failure = build_quarkus(repo) if spec.get("runtime") == "quarkus" else None
        if failure:
            print("FAIL  %s" % failure[0]["show"])
            failures = [failure]
        elif spec["kind"] == "http":
            failures = check_http(spec, repo, workdir, args.python, args.java)
        else:
            failures = check_cli(spec, repo, workdir, args.python)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if not failures:
        print("\nAll examples pass. Stopping rule met: the run is done.")
        return 0
    print("\n%d example(s) failed. Paste this to the agent verbatim as the next prompt:\n" % len(failures))
    print("-" * 72)
    print(follow_up(failures))
    print("-" * 72)
    return 1


if __name__ == "__main__":
    sys.exit(main())
