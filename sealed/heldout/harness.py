"""Shared harness for the held-out suites.

Every test is black-box: it runs the system under test (SUT) as a subprocess,
`python -m <package>`, exactly as the task description specifies, so the
suites apply unchanged to any implementation from any condition.

Environment:
  SUT_REPO    root of the repository produced by a run (required)
  SUT_PYTHON  interpreter used to run the SUT (default: the one running pytest)

The SUT is run with PYTHONPATH=<repo>/src:<repo>, so a package placed at the
repository root instead of under src/ is still found (layout is not measured).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

DEFAULT_TIMEOUT = 20


def _sut_repo():
    value = os.environ.get("SUT_REPO")
    if not value:
        pytest.exit("SUT_REPO is not set; point it at the run's repository root", returncode=4)
    path = Path(value).resolve()
    if not path.is_dir():
        pytest.exit("SUT_REPO does not exist: %s" % path, returncode=4)
    return path


def sut_env(extra=None):
    repo = _sut_repo()
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(repo / "src"), str(repo)])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("SUT_REPO", None)
    if extra:
        env.update(extra)
    return env


def sut_python():
    return os.environ.get("SUT_PYTHON") or sys.executable


class Runner:
    """Runs `python -m <package> ...` in a scratch working directory."""

    def __init__(self, package, workdir):
        self.package = package
        self.workdir = Path(workdir)

    def __call__(self, *args, input=None, timeout=DEFAULT_TIMEOUT, cwd=None, env=None):
        if isinstance(input, str):
            input = input.encode("utf-8")
        cmd = [sut_python(), "-m", self.package] + [str(a) for a in args]
        try:
            proc = subprocess.run(
                cmd,
                input=input,
                capture_output=True,
                cwd=str(cwd or self.workdir),
                env=sut_env(env),
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            pytest.fail("SUT did not finish within %ss: %s" % (timeout, " ".join(cmd[2:])))
        return Result(proc)


class Result:
    def __init__(self, proc):
        self.returncode = proc.returncode
        self.stdout_bytes = proc.stdout
        self.stderr_bytes = proc.stderr
        self.stdout = proc.stdout.decode("utf-8", "replace")
        self.stderr = proc.stderr.decode("utf-8", "replace")

    def __repr__(self):
        return "Result(rc=%r, stdout=%r, stderr=%r)" % (
            self.returncode, self.stdout[-500:], self.stderr[-500:])
