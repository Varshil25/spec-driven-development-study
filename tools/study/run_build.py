#!/usr/bin/env python3
"""Drive one study run with Claude Code in headless mode, the operator in the loop.

Run it from inside the run's clone (RUNBOOK.md, step 1):

    python3 <kit>/tools/study/run_build.py R004            # a build
    python3 <kit>/tools/study/run_build.py R004C           # its change request

It does everything the runbook asks of the operator, except judging the agent's
messages:

  * opens the run in sddlog (run-start, with --stage change for an ID ending
    in C) and records the environment;
  * for each phase of the run's condition, opens the phase, starts a fresh
    `claude -p` session with that phase's fixed prompt, and continues the same
    session (`--resume`) with fixed replies;
  * after every agent turn, shows the agent's final message and asks the
    operator what it is, using the pre-registered rules:
        I2        a question covered by answer-sheet entry I2 (several: I1,I3;
                  an entry of the original task's sheet: orig:I2)
        safety    an uncovered safety question     -> the safety fallback
        nopref    any other uncovered question     -> the no-preference fallback
        permit    a request for permission         -> "Yes, go ahead."
        listed    assumptions listed, nothing asked -> no reply; LISTED note
        done      the agent says it has finished
  * in the implement phase, runs check_examples.py when the agent is done and
    pastes its follow-up verbatim, within the caps (5 follow-ups, 90 minutes);
  * resumes an interrupted session with the one fixed resume message;
  * closes the phase and the run, runs `sddlog verify`, and commits the clone.

Every message it sends comes from prompts/, the task texts, the answer sheets,
or check_examples.py, so the operator never types into the agent. Each
`claude -p` reply is saved under logs/runs/<RUN>/headless/ with Claude Code's
own usage, cost and duration figures, as a cross-check on sddlog's tokens.

Standard library only.
"""

import argparse
import csv
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
MODEL = "claude-opus-5"
ALLOWED_TOOLS = "Bash,Read,Edit,Write,MultiEdit,Glob,Grep,TodoWrite,NotebookEdit,Skill,Task,Agent"
PERMISSION_MODE = "acceptEdits"
MAX_FOLLOW_UPS = 5
IMPLEMENT_CAP_SECONDS = 90 * 60

SAFETY = "On this question: it should be handled safely; the details are up to you."
NOPREF = "No preference on this question. Use your judgement."
PERMIT = "Yes, go ahead."
RESUME = "Please continue from where you stopped."

PHASES = {
    "unstructured": ["implement"],
    "sdd": ["constitution", "specify", "plan", "tasks", "implement"],
    "sdd_clarify": ["constitution", "specify", "clarify", "plan", "tasks", "implement"],
    "sdd_secure": ["constitution", "specify", "plan", "tasks", "implement"],
}

# Environment variables that would tie a child session to a parent Claude Code
# session (for example when this tool is started from inside one).
STRIP_ENV = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION",
             "CLAUDE_CODE_ENTRYPOINT")

# With --clean-env, a child session gets only these variables plus its own
# CLAUDE_CONFIG_DIR, so nothing from the machine's own Claude setup (user
# skills, plugins, hooks, MCP servers, effort settings, a host's extra tools)
# reaches the agent under test, and nothing carries over between runs.
CLEAN_ENV_KEEP = ("PATH", "HOME", "LANG", "LC_ALL", "TERM", "USER", "SHELL", "TMPDIR",
                  "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "NO_PROXY", "no_proxy",
                  "NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE", "GIT_SSL_CAINFO", "REQUESTS_CA_BUNDLE",
                  "PIP_CERT", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY")


class Abort(Exception):
    pass


# ---------------------------------------------------------------------------
# study materials
# ---------------------------------------------------------------------------


def schedule_row(kit, run_id):
    """(task, condition, stage) for a run ID; an ID ending in C is a change request."""
    base = run_id[:-1] if run_id.endswith("C") else run_id
    with open(kit / "schedule" / "schedule.csv", newline="") as handle:
        rows = {row["run_id"]: row for row in csv.DictReader(handle)}
    if base not in rows:
        raise Abort("%s is not in schedule/schedule.csv" % base)
    row = rows[base]
    if run_id.endswith("C"):
        return row["task_id"] + "-CR", row["condition"], "change"
    return row["task_id"], row["condition"], "build"


def phases_for(condition, stage):
    phases = list(PHASES[condition])
    if stage == "change":
        phases = [p for p in phases if p != "constitution"]
    return phases


def phase_range(phases, start_at, stop_after):
    """Indexes of the first and last phase to run in this invocation."""
    for name in (start_at, stop_after):
        if name is not None and name not in phases:
            raise Abort("this run's phases are %s, not %s" % (", ".join(phases), name))
    first = phases.index(start_at) if start_at else 0
    last = phases.index(stop_after) if stop_after else len(phases) - 1
    if first > last:
        raise Abort("--start-at %s comes after --stop-after %s" % (start_at, stop_after))
    return first, last


def read_text(path):
    return Path(path).read_text(encoding="utf-8").strip()


def phase_prompt(kit, task, condition, phase):
    """The fixed message that opens a phase (prompts/README.md)."""
    task_text = read_text(kit / "tasks" / task / "prompt.md")
    if phase == "constitution":
        name = "constitution-secure.txt" if condition == "sdd_secure" else "constitution.txt"
        return read_text(kit / "prompts" / name)
    if phase == "specify":
        return "/speckit-specify " + task_text
    if phase == "clarify":
        return "/speckit-clarify"
    if phase == "plan":
        return read_text(kit / "prompts" / "plan.txt")
    if phase == "tasks":
        return "/speckit-tasks"
    if phase == "implement":
        return task_text if condition == "unstructured" else "/speckit-implement"
    raise Abort("no prompt for phase %s" % phase)


ROW_RE = re.compile(r"^\|\s*(I\d+)\s*\|(.*)\|\s*(.+?)\s*\|\s*$")


def load_answer_sheet(path):
    """{entry: reply} from an answer-sheet table."""
    answers = {}
    if not path.exists():
        return answers
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ROW_RE.match(line)
        if match:
            answers[match.group(1)] = match.group(3)
    return answers


def answer_sheets(kit, task):
    """The task's sheet, plus the original task's sheet (as orig:I1...) for a change request."""
    sheets = kit / "operator" / "answer-sheets"
    answers = load_answer_sheet(sheets / ("%s.md" % task))
    if task.endswith("-CR"):
        for entry, reply in load_answer_sheet(sheets / ("%s.md" % task[:-3])).items():
            answers["orig:" + entry] = reply
    return answers


# ---------------------------------------------------------------------------
# the agent, the instrument and the checker
# ---------------------------------------------------------------------------


def child_env(args):
    """The environment of each `claude -p` call."""
    if args.clean_env:
        env = {k: os.environ[k] for k in CLEAN_ENV_KEEP if k in os.environ}
        env["CLAUDE_CONFIG_DIR"] = str(config_dir(args))
        return env
    return {k: v for k, v in os.environ.items() if k not in STRIP_ENV}


def config_dir(args):
    """A run's own Claude Code configuration folder under --clean-env (build and change request share
    nothing: each run ID gets a new one)."""
    path = Path(args.clean_env).resolve() / args.run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


class Agent:
    """One `claude -p` session per phase, continued with --resume."""

    def __init__(self, args, log_dir):
        self.args = args
        self.log_dir = log_dir
        self.session = None
        self.calls = 0

    def _command(self, message):
        cmd = shlex.split(self.args.claude) + [
            "-p", message, "--model", self.args.model, "--output-format", "json",
            "--permission-mode", self.args.permission_mode,
            "--allowedTools", self.args.allowed_tools]
        if self.session:
            cmd += ["--resume", self.session]
        return cmd

    def send(self, message, phase):
        env = child_env(self.args)
        started = time.time()
        proc = subprocess.run(self._command(message), capture_output=True, text=True, env=env)
        self.calls += 1
        record = {"phase": phase, "call": self.calls, "sent": message, "returncode": proc.returncode,
                  "wall_seconds": round(time.time() - started, 1), "stderr": proc.stderr[-4000:]}
        try:
            reply = json.loads(proc.stdout)
        except ValueError:
            reply = {"is_error": True, "result": proc.stdout[-4000:]}
        record["reply"] = reply
        self.log_dir.mkdir(parents=True, exist_ok=True)
        (self.log_dir / ("%s-%02d.json" % (phase, self.calls))).write_text(json.dumps(record, indent=2))
        if reply.get("session_id"):
            self.session = reply["session_id"]
        failed = proc.returncode != 0 or reply.get("is_error")
        return reply.get("result") or "", failed


def sddlog(*args, check=True):
    proc = subprocess.run([sys.executable, "tools/sddlog/sddlog.py"] + list(args),
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise Abort("sddlog %s failed: %s" % (" ".join(args), proc.stderr.strip() or proc.stdout))
    return proc.stdout.strip()


def note(text):
    sddlog("note", "--text", text)


def check_examples(kit, task):
    proc = subprocess.run([sys.executable, str(kit / "tools" / "study" / "check_examples.py"),
                           task, "--repo", "."], capture_output=True, text=True)
    if proc.returncode == 0:
        return None
    if proc.returncode != 1:
        raise Abort("check_examples.py failed to run:\n%s%s" % (proc.stdout, proc.stderr))
    text = proc.stdout
    start = text.index("-" * 72) + 73
    end = text.index("-" * 72, start)
    return text[start:end].strip()


def shorten(text, limit=120):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 3] + "..."


# ---------------------------------------------------------------------------
# the operator
# ---------------------------------------------------------------------------


class Operator:
    """Reads the operator's classification of each agent turn.

    Interactive by default; --script FILE replays one classification per line
    (used by the tests, and for re-running a mechanics check exactly)."""

    def __init__(self, script=None):
        self.script = list(script) if script is not None else None

    def ask(self, prompt):
        if self.script is not None:
            if not self.script:
                raise Abort("operator script ran out of lines")
            line = self.script.pop(0)
            print(prompt + line)
            return line.strip()
        return input(prompt).strip()


def classify(operator, answers, message, phase):
    """Turn the operator's choice into (kind, reply)."""
    print("\n" + "=" * 72)
    print("[%s] the agent's turn ended with:\n" % phase)
    print(message.strip()[-3000:] or "(no text)")
    print("=" * 72)
    print("What is it?  entry id(s) e.g. I2 or I1,orig:I3 | safety | nopref | permit | listed | done")
    while True:
        choice = operator.ask("> ")
        lowered = choice.lower()
        if lowered in ("done", "listed"):
            return lowered, None
        if lowered == "safety":
            return "SAFETY", SAFETY
        if lowered == "nopref":
            return "NOPREF", NOPREF
        if lowered == "permit":
            return "PERMIT", PERMIT
        entries = [e.strip() for e in choice.split(",") if e.strip()]
        entries = [("orig:" + e[5:].upper()) if e.lower().startswith("orig:") else e.upper()
                   for e in entries]
        if entries and all(e in answers for e in entries):
            # Several questions in one message get one reply, answers in order (rule 6).
            return ",".join(entries), "\n\n".join(answers[e] for e in entries)
        print("not understood; known entries: %s" % ", ".join(sorted(answers)))


# ---------------------------------------------------------------------------
# a run
# ---------------------------------------------------------------------------


def run_phase(args, kit, task, condition, phase, operator, answers, log_dir, resume=None):
    agent = Agent(args, log_dir)
    if resume:
        # The phase is already open: its session was interrupted (RUNBOOK 5). Resume that session
        # with the fixed resume message, as pre-registered in section 6.1.
        agent.session = resume
        note("RESUME: %s session interrupted (operator's workspace restarted); resumed %s" % (phase, resume))
        message = RESUME
    else:
        sddlog("phase", phase, "--start")
        message = phase_prompt(kit, task, condition, phase)
    opened = time.time()
    follow_ups = 0
    while True:
        result, failed = agent.send(message, phase)
        if failed:
            print("\nThe agent session stopped with an error:\n%s" % shorten(result, 500))
            choice = operator.ask("resume the same session with the fixed resume message? [y/n] > ")
            if choice.lower().startswith("y"):
                note("RESUME: %s session stopped with an error: %s" % (phase, shorten(result, 200)))
                message = RESUME
                continue
            raise Abort("phase %s stopped; abort the run and redo it with a spare ID (RUNBOOK 5)" % phase)
        kind, reply = classify(operator, answers, result, phase)
        if kind == "listed":
            note("LISTED: %s" % shorten(result, 200))
            kind = "done"
        if reply is not None:
            note("ANSWER %s: %s" % (kind, shorten(result.strip().splitlines()[-1] if result.strip() else "")))
            message = reply
            continue
        # The agent is done with its turn.
        if phase != "implement":
            break
        follow_up = check_examples(kit, task)
        if follow_up is None:
            print("\nAll examples pass: the stopping rule is met.")
            break
        elapsed = time.time() - opened
        if follow_ups >= args.max_follow_ups or elapsed >= args.cap_seconds:
            which = "follow-up cap" if follow_ups >= args.max_follow_ups else "90-minute cap"
            note("CAP REACHED: %s; examples still failing" % which)
            print("\nCap reached (%s); the run is scored as it stands." % which)
            break
        follow_ups += 1
        print("\nExamples fail; sending follow-up %d of %d." % (follow_ups, args.max_follow_ups))
        message = follow_up
    sddlog("phase", phase, "--end")
    return agent


def environment_note(args):
    def version(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip() or "?"
        except (OSError, subprocess.TimeoutExpired):
            return "not found"
    return "env: claude %s | %s | %s | headless run_build.py, permission mode %s, allowed tools %s%s" % (
        version(shlex.split(args.claude) + ["--version"]),
        version(["specify", "--version"]),
        version([sys.executable, "--version"]),
        args.permission_mode, args.allowed_tools,
        " | clean environment, own config folder" if args.clean_env else "")


def prepare_repository(condition, stage, args):
    """Check the clone is in the state RUNBOOK step 1 requires; add Spec Kit for SDD builds."""
    if not Path("tools/sddlog/sddlog.py").exists():
        raise Abort("run this from inside the run's clone of the base repository")
    has_spec_kit = Path(".specify").exists()
    if condition == "unstructured":
        if has_spec_kit:
            raise Abort("an unstructured run must not have Spec Kit (.specify/ exists)")
        return
    if stage == "change":
        if not has_spec_kit:
            raise Abort("a change request runs in the build's clone, which has Spec Kit")
        return
    if not has_spec_kit:
        if args.no_spec_kit_setup:
            raise Abort("Spec Kit is missing; add it as in RUNBOOK step 1")
        subprocess.run(["specify", "init", "--here", "--force", "--integration", "claude",
                        "--extension", "git", "--non-interactive", "--script", "sh"], check=True)
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-qm", "condition setup: Spec Kit"], check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_id", help="a run ID from schedule/schedule.csv, or that ID plus C")
    parser.add_argument("--kit", default=str(KIT), help="the study repository (default: this tool's)")
    parser.add_argument("--claude", default="claude", help="the Claude Code command")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--permission-mode", default=PERMISSION_MODE)
    parser.add_argument("--allowed-tools", default=ALLOWED_TOOLS)
    parser.add_argument("--max-follow-ups", type=int, default=MAX_FOLLOW_UPS)
    parser.add_argument("--cap-seconds", type=int, default=IMPLEMENT_CAP_SECONDS)
    parser.add_argument("--script", default=None,
                        help="file of operator choices, one per line, instead of asking")
    parser.add_argument("--no-spec-kit-setup", action="store_true",
                        help="fail instead of running `specify init` when Spec Kit is missing")
    parser.add_argument("--no-commit", action="store_true", help="do not commit the clone at the end")
    parser.add_argument("--start-at", metavar="PHASE", default=None,
                        help="continue an open run from PHASE (the run was stopped with --stop-after)")
    parser.add_argument("--stop-after", metavar="PHASE", default=None,
                        help="leave the run open after PHASE; continue later with --start-at")
    parser.add_argument("--resume-session", metavar="ID", default=None,
                        help="with --start-at: resume this interrupted session of that open phase "
                             "with the fixed resume message instead of opening the phase anew")
    parser.add_argument("--clean-env", metavar="DIR", default=None,
                        help="give each claude call only a minimal environment and a fresh config "
                             "folder DIR/<run id> (no user skills, plugins, hooks or host tools)")
    args = parser.parse_args(argv)
    if args.resume_session and not args.start_at:
        parser.error("--resume-session needs --start-at")

    kit = Path(args.kit).resolve()
    script = Path(args.script).read_text().splitlines() if args.script else None
    operator = Operator(script)
    try:
        task, condition, stage = schedule_row(kit, args.run_id)
        phases = phases_for(condition, stage)
        first, last = phase_range(phases, args.start_at, args.stop_after)
        answers = answer_sheets(kit, task)
        log_dir = Path("logs") / "runs" / args.run_id / "headless"
        if first == 0 and not args.resume_session:
            prepare_repository(condition, stage, args)
            sddlog("run-start", "--run-id", args.run_id, "--task", task, "--condition", condition,
                   "--stage", stage, "--model", args.model)
            note(environment_note(args))
        else:
            active = Path("logs") / "ACTIVE_RUN"
            if not active.exists() or active.read_text().strip() != args.run_id:
                raise Abort("--start-at needs %s to be the open run in this clone" % args.run_id)
        print("Run %s: %s, %s, %s stage. Phases: %s" % (
            args.run_id, task, condition, stage, " -> ".join(phases)))
        for phase in phases[first:last + 1]:
            resume = args.resume_session if phase == phases[first] else None
            run_phase(args, kit, task, condition, phase, operator, answers, log_dir, resume)
        if last < len(phases) - 1:
            print("\nRun %s left open after %s. Continue with: run_build.py %s --start-at %s" % (
                args.run_id, phases[last], args.run_id, phases[last + 1]))
            return 0
        sddlog("run-end", "--status", "completed")
    except Abort as exc:
        print("\nrun_build: %s" % exc, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted. The run is still open; see RUNBOOK section 5.", file=sys.stderr)
        return 130

    verify = sddlog("verify", "--run-id", args.run_id, check=False)
    print("\n" + verify)
    summary = usage_summary(log_dir)
    print("Claude Code reported: %(calls)d calls, %(cost).2f USD, %(minutes).1f min of API time, "
          "%(output)d output tokens" % summary)
    if not args.no_commit:
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "-c", "user.name=operator", "-c", "user.email=operator@localhost",
                        "commit", "-qm", "run %s closed" % args.run_id], check=False)
    print("Next: RUNBOOK step 4 (bundle the clone, copy logs/runs/%s into the study repository, "
          "add a run-log line)." % args.run_id)
    return 0


def usage_summary(log_dir):
    total = {"calls": 0, "cost": 0.0, "minutes": 0.0, "output": 0}
    for path in sorted(Path(log_dir).glob("*.json")):
        reply = json.loads(path.read_text()).get("reply", {})
        total["calls"] += 1
        total["cost"] += reply.get("total_cost_usd") or 0.0
        total["minutes"] += (reply.get("duration_api_ms") or 0) / 60000
        total["output"] += (reply.get("usage") or {}).get("output_tokens") or 0
    return total


if __name__ == "__main__":
    sys.exit(main())
