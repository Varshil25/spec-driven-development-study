#!/usr/bin/env python3
"""sddlog - instrumented logging for the Spec-Driven Development study.

Captures prompts, edits, and outputs during an agent-assisted coding run so
that SDD (Spec Kit) and unstructured-prompting conditions can be compared on
identical evidence.

Design constraints:
  * Python standard library only (no install step, runs under any python3).
  * Append-only JSONL event log; derived metrics are always recomputable.
  * Three independent capture paths, so no single failure loses a run:
      1. Claude Code hooks        -> real-time prompts / tool calls / edits
      2. git phase-boundary tags  -> authoritative file-edit ground truth
      3. transcript ingestion     -> after-the-fact backfill of 1
  * Secret redaction runs before anything touches disk.

Usage: see `sddlog.py --help` or docs/LOGGING-PROTOCOL.md
"""

from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

SCHEMA_VERSION = "1.0.0"

# Canonical Spec Kit phases, in workflow order. Used to validate phase names
# and to order the per-phase metrics table.
PHASES = [
    "constitution",
    "specify",
    "clarify",
    "plan",
    "tasks",
    "analyze",
    "implement",
]

EVENT_TYPES = {
    "run_start",
    "run_end",
    "phase_start",
    "phase_end",
    "prompt",
    "agent_output",
    "file_edit",
    "tool_call",
    "artifact_snapshot",
    "note",
}

CONDITIONS = {"sdd", "unstructured"}

# --------------------------------------------------------------------------
# redaction
# --------------------------------------------------------------------------

# Applied to every free-text field before it is written. Ordered most specific
# first so that a generic rule cannot mask a specific one.
REDACTION_RULES = [
    ("github_pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{16,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    (
        "assigned_secret",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*"
            r"['\"]?([A-Za-z0-9._~+/=-]{8,})['\"]?"
        ),
    ),
]


def redact(text):
    """Replace credential-shaped substrings with a labelled placeholder.

    Returns (redacted_text, [rule_names_that_fired]). Non-string input is
    returned unchanged so callers can pass through structured payloads.
    """
    if not isinstance(text, str) or not text:
        return text, []
    fired = []
    out = text
    for name, pattern in REDACTION_RULES:
        if name == "assigned_secret":
            def _sub(m):
                return "%s=[REDACTED:%s]" % (m.group(1), name)
            new = pattern.sub(_sub, out)
        else:
            new = pattern.sub("[REDACTED:%s]" % name, out)
        if new != out:
            fired.append(name)
            out = new
    return out, fired


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def now_iso():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256(text):
    if text is None:
        return None
    if isinstance(text, str):
        text = text.encode("utf-8", "replace")
    return hashlib.sha256(text).hexdigest()


def word_count(text):
    return len(text.split()) if text else 0


def parse_iso(ts):
    if not ts:
        return None
    try:
        return _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def git(repo, *args, check=False):
    """Run git in `repo`; return (returncode, stdout). Never raises on failure
    unless check=True, because logging must not break the run it observes."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo)] + list(args),
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return 127, ""
    if check and proc.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), proc.stderr.strip()))
    return proc.returncode, proc.stdout.strip()


# --------------------------------------------------------------------------
# store
# --------------------------------------------------------------------------


class Store:
    """Filesystem layout and read/write primitives for run logs."""

    def __init__(self, repo_root):
        self.repo = Path(repo_root).resolve()
        self.logs = self.repo / "logs"
        self.runs = self.logs / "runs"
        self.index_path = self.logs / "index.json"
        self.active_path = self.logs / "ACTIVE_RUN"

    # -- run resolution ---------------------------------------------------

    def run_dir(self, run_id):
        return self.runs / run_id

    def active_run_id(self):
        """The run id recorded by `run-start`, or None.

        SDDLOG_RUN_ID overrides the file so that a second shell (or a hook
        invoked out-of-process) can be pinned to a specific run.
        """
        env = os.environ.get("SDDLOG_RUN_ID")
        if env:
            return env.strip()
        if self.active_path.exists():
            value = self.active_path.read_text().strip()
            if value:
                return value
        return None

    def last_run_id(self):
        """Most recently started run, active or not."""
        entries = []
        if self.runs.exists():
            for child in self.runs.iterdir():
                manifest = child / "manifest.json"
                if child.is_dir() and manifest.exists():
                    try:
                        data = json.loads(manifest.read_text())
                    except json.JSONDecodeError:
                        continue
                    entries.append((data.get("started_at") or "", child.name))
        return max(entries)[1] if entries else None

    def require_run(self, run_id=None, allow_closed=False):
        """Resolve the run to act on.

        Write commands need an *active* run so that stray logging cannot land
        in a finished dataset entry. Read-only commands (verify/metrics/report)
        accept the most recent run, since those are normally invoked after
        `run-end` has already cleared the active pointer.
        """
        rid = run_id or self.active_run_id()
        if not rid and allow_closed:
            rid = self.last_run_id()
        if not rid:
            raise SystemExit("sddlog: no active run. Start one with `sddlog run-start`.")
        if not self.run_dir(rid).exists():
            raise SystemExit("sddlog: run %r not found under %s" % (rid, self.runs))
        return rid

    def next_run_id(self):
        existing = []
        if self.runs.exists():
            for child in self.runs.iterdir():
                m = re.match(r"^R(\d{3,})$", child.name)
                if child.is_dir() and m:
                    existing.append(int(m.group(1)))
        return "R%03d" % ((max(existing) + 1) if existing else 1)

    # -- manifest ---------------------------------------------------------

    def manifest_path(self, run_id):
        return self.run_dir(run_id) / "manifest.json"

    def read_manifest(self, run_id):
        path = self.manifest_path(run_id)
        if not path.exists():
            raise SystemExit("sddlog: manifest missing for run %r" % run_id)
        return json.loads(path.read_text())

    def write_manifest(self, run_id, manifest):
        self.manifest_path(run_id).write_text(json.dumps(manifest, indent=2) + "\n")

    # -- events -----------------------------------------------------------

    def events_path(self, run_id):
        return self.run_dir(run_id) / "events.jsonl"

    def read_events(self, run_id):
        path = self.events_path(run_id)
        if not path.exists():
            return []
        events = []
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(
                    "sddlog: corrupt event at %s:%d (%s)" % (path, line_no, exc)
                )
        return events

    def next_seq(self, run_id):
        path = self.events_path(run_id)
        if not path.exists():
            return 1
        count = 0
        with path.open() as handle:
            for line in handle:
                if line.strip():
                    count += 1
        return count + 1

    def current_phase(self, run_id):
        """Most recent phase_start with no matching phase_end."""
        phase = None
        for event in self.read_events(run_id):
            if event.get("type") == "phase_start":
                phase = event.get("phase")
            elif event.get("type") == "phase_end":
                phase = None
        return phase

    def append(self, run_id, event_type, payload=None, phase=None, actor="system"):
        """Append one event. Redaction and hashing happen here, once, so no
        caller can bypass them."""
        if event_type not in EVENT_TYPES:
            raise SystemExit("sddlog: unknown event type %r" % event_type)
        manifest = self.read_manifest(run_id)
        payload = dict(payload or {})
        redactions = []
        for field in ("text", "diff", "args_summary"):
            if field in payload:
                payload[field], fired = redact(payload[field])
                redactions.extend(fired)

        event = {
            "schema_version": SCHEMA_VERSION,
            "event_id": str(uuid.uuid4()),
            "run_id": run_id,
            "seq": self.next_seq(run_id),
            "ts": now_iso(),
            "type": event_type,
            "actor": actor,
            "phase": phase if phase is not None else self.current_phase(run_id),
            "condition": manifest.get("condition"),
            "task_id": manifest.get("task_id"),
            "session_id": os.environ.get("SDDLOG_SESSION_ID") or manifest.get("session_id"),
            "payload": payload,
        }
        if redactions:
            event["redactions"] = sorted(set(redactions))

        self.run_dir(run_id).mkdir(parents=True, exist_ok=True)
        with self.events_path(run_id).open("a") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    # -- index ------------------------------------------------------------

    def rebuild_index(self):
        entries = []
        if self.runs.exists():
            for child in sorted(self.runs.iterdir()):
                manifest = child / "manifest.json"
                if child.is_dir() and manifest.exists():
                    data = json.loads(manifest.read_text())
                    entries.append(
                        {
                            "run_id": data.get("run_id"),
                            "task_id": data.get("task_id"),
                            "condition": data.get("condition"),
                            "model": data.get("model"),
                            "started_at": data.get("started_at"),
                            "ended_at": data.get("ended_at"),
                            "status": data.get("status"),
                        }
                    )
        self.logs.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps({"runs": entries}, indent=2) + "\n")
        return entries


def find_repo_root(start=None):
    """Walk up for a .specify/ or .git/ marker; fall back to cwd."""
    current = Path(start or os.environ.get("SDDLOG_REPO") or Path.cwd()).resolve()
    for candidate in [current] + list(current.parents):
        if (candidate / ".specify").is_dir() or (candidate / ".git").is_dir():
            return candidate
    return current


# --------------------------------------------------------------------------
# edit capture
# --------------------------------------------------------------------------


# The logger writes into logs/ inside the repo under observation. Those writes
# are instrument output, not agent work, so every measurement excludes them --
# otherwise each capture would report its own previous events file as an edit.
MEASURE_PATHSPEC = ["--", ".", ":(exclude)logs"]


def _numstat_for(repo, *rev_args):
    code, out = git(repo, "diff", "--numstat", *rev_args, *MEASURE_PATHSPEC)
    if code != 0:
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        rows.append(
            {
                "path": path,
                "lines_added": 0 if added == "-" else int(added),
                "lines_removed": 0 if removed == "-" else int(removed),
                "binary": added == "-",
            }
        )
    return rows


def capture_edits(store, run_id, label, phase=None):
    """Record every file changed since the last capture point.

    Uses git as the source of truth: stages nothing, but snapshots the diff
    of the working tree (tracked + untracked) against the last capture commit
    recorded in the manifest, then writes a unified diff to disk and one
    file_edit event per file.
    """
    repo = store.repo
    manifest = store.read_manifest(run_id)
    base = manifest.get("last_capture_commit")

    # Commit the current state so the capture point is reproducible.
    git(repo, "add", "-A")
    code, _ = git(repo, "diff", "--cached", "--quiet")
    committed = None
    if code == 1:  # there are staged changes
        git(repo, "commit", "-m", "sddlog capture: %s (%s)" % (label, run_id), "--no-verify")
        _, committed = git(repo, "rev-parse", "HEAD")
    else:
        _, committed = git(repo, "rev-parse", "HEAD")

    if not base or base == committed:
        rows = []
        diff_text = ""
    else:
        rows = _numstat_for(repo, base, committed)
        _, diff_text = git(repo, "diff", base, committed, *MEASURE_PATHSPEC)

    diff_path = None
    if diff_text:
        diffs_dir = store.run_dir(run_id) / "diffs"
        diffs_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_.-]", "-", label)
        diff_path = diffs_dir / ("%03d-%s.diff" % (store.next_seq(run_id), safe))
        redacted_diff, _ = redact(diff_text)
        diff_path.write_text(redacted_diff)

    for row in rows:
        store.append(
            run_id,
            "file_edit",
            {
                "path": row["path"],
                "lines_added": row["lines_added"],
                "lines_removed": row["lines_removed"],
                "binary": row["binary"],
                "capture_label": label,
                "base_commit": base,
                "head_commit": committed,
                "diff_file": str(diff_path.relative_to(store.repo)) if diff_path else None,
            },
            phase=phase,
            actor="agent",
        )

    manifest["last_capture_commit"] = committed
    store.write_manifest(run_id, manifest)
    return rows, committed


# --------------------------------------------------------------------------
# artifact snapshots
# --------------------------------------------------------------------------

ARTIFACT_CANDIDATES = [
    ("constitution", ".specify/memory/constitution.md"),
    ("spec", "{feature_dir}/spec.md"),
    ("plan", "{feature_dir}/plan.md"),
    ("tasks", "{feature_dir}/tasks.md"),
    ("research", "{feature_dir}/research.md"),
    ("data-model", "{feature_dir}/data-model.md"),
    ("quickstart", "{feature_dir}/quickstart.md"),
]


def feature_dir_for(repo):
    marker = repo / ".specify" / "feature.json"
    if marker.exists():
        try:
            return json.loads(marker.read_text()).get("feature_directory")
        except json.JSONDecodeError:
            return None
    return None


def snapshot_artifacts(store, run_id, phase):
    """Copy the current Spec Kit artifacts into the run's snapshot folder.

    Snapshots are per-phase, so spec drift across phases (a key RQ4 signal)
    stays measurable even after later edits overwrite the live files.
    """
    repo = store.repo
    feature = feature_dir_for(repo) or ""
    target = store.run_dir(run_id) / "snapshots" / phase
    recorded = []
    for name, template in ARTIFACT_CANDIDATES:
        rel = template.format(feature_dir=feature)
        if "{feature_dir}" in template and not feature:
            continue
        source = repo / rel
        if not source.exists() or not source.is_file():
            continue
        text = source.read_text(errors="replace")
        redacted, _ = redact(text)
        target.mkdir(parents=True, exist_ok=True)
        dest = target / ("%s.md" % name)
        dest.write_text(redacted)
        store.append(
            run_id,
            "artifact_snapshot",
            {
                "artifact": name,
                "source_path": rel,
                "snapshot_path": str(dest.relative_to(repo)),
                "sha256": sha256(text),
                "words": word_count(text),
                "lines": len(text.splitlines()),
            },
            phase=phase,
        )
        recorded.append(name)
    return recorded


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------


def compute_metrics(store, run_id):
    """Derive the study's per-run measures from the event log alone."""
    manifest = store.read_manifest(run_id)
    events = store.read_events(run_id)

    started = parse_iso(manifest.get("started_at"))
    ended = parse_iso(manifest.get("ended_at"))
    if not ended:
        last = [parse_iso(e["ts"]) for e in events if parse_iso(e["ts"])]
        ended = max(last) if last else None

    per_phase = {}
    open_phase = {}
    for event in events:
        etype = event.get("type")
        phase = event.get("phase")
        if etype == "phase_start":
            open_phase[event.get("phase")] = parse_iso(event["ts"])
        elif etype == "phase_end":
            name = event.get("phase")
            start_ts = open_phase.pop(name, None)
            end_ts = parse_iso(event["ts"])
            bucket = per_phase.setdefault(name, _empty_phase())
            if start_ts and end_ts:
                bucket["wall_clock_seconds"] += round((end_ts - start_ts).total_seconds(), 1)
        if phase:
            bucket = per_phase.setdefault(phase, _empty_phase())
            if etype == "prompt":
                bucket["human_prompts"] += 1
                bucket["prompt_words"] += event["payload"].get("words", 0)
            elif etype == "agent_output":
                bucket["agent_outputs"] += 1
                bucket["output_words"] += event["payload"].get("words", 0)
            elif etype == "tool_call":
                bucket["tool_calls"] += 1
            elif etype == "file_edit":
                bucket["files_touched"].add(event["payload"].get("path"))
                bucket["lines_added"] += event["payload"].get("lines_added", 0)
                bucket["lines_removed"] += event["payload"].get("lines_removed", 0)

    for bucket in per_phase.values():
        bucket["files_touched"] = len(bucket["files_touched"])
        # One "turn" is a human prompt answered by the agent; the count of
        # prompts is the conversational cost measure used for RQ3.
        bucket["turns"] = bucket["human_prompts"]

    totals = {
        "wall_clock_seconds": round((ended - started).total_seconds(), 1) if (started and ended) else None,
        "phases_completed": sum(1 for p in per_phase.values() if p["wall_clock_seconds"] > 0),
        "human_prompts": sum(p["human_prompts"] for p in per_phase.values()),
        "prompt_words": sum(p["prompt_words"] for p in per_phase.values()),
        "agent_outputs": sum(p["agent_outputs"] for p in per_phase.values()),
        "output_words": sum(p["output_words"] for p in per_phase.values()),
        "tool_calls": sum(p["tool_calls"] for p in per_phase.values()),
        "lines_added": sum(p["lines_added"] for p in per_phase.values()),
        "lines_removed": sum(p["lines_removed"] for p in per_phase.values()),
        "distinct_files_touched": len(
            {
                e["payload"].get("path")
                for e in events
                if e.get("type") == "file_edit" and e["payload"].get("path")
            }
        ),
        "events": len(events),
    }

    artifact_sizes = {}
    for event in events:
        if event.get("type") == "artifact_snapshot":
            payload = event["payload"]
            artifact_sizes.setdefault(payload["artifact"], {})[event.get("phase")] = {
                "words": payload.get("words"),
                "sha256": payload.get("sha256"),
            }

    return {
        "run_id": run_id,
        "task_id": manifest.get("task_id"),
        "condition": manifest.get("condition"),
        "model": manifest.get("model"),
        "agent": manifest.get("agent"),
        "computed_at": now_iso(),
        "totals": totals,
        "per_phase": {k: per_phase[k] for k in PHASES if k in per_phase},
        "artifacts": artifact_sizes,
    }


def _empty_phase():
    return {
        "wall_clock_seconds": 0.0,
        "human_prompts": 0,
        "prompt_words": 0,
        "agent_outputs": 0,
        "output_words": 0,
        "tool_calls": 0,
        "files_touched": set(),
        "lines_added": 0,
        "lines_removed": 0,
    }


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------


def verify_run(store, run_id):
    """Integrity checks that must pass before a run enters the dataset."""
    problems = []
    warnings = []
    events = store.read_events(run_id)
    manifest = store.read_manifest(run_id)

    if not events:
        problems.append("event log is empty")

    for field in ("run_id", "task_id", "condition", "model", "agent", "started_at"):
        if not manifest.get(field):
            problems.append("manifest missing required field: %s" % field)
    if manifest.get("condition") not in CONDITIONS:
        problems.append("condition must be one of %s" % sorted(CONDITIONS))

    # sequence numbers must be dense and monotonic
    for index, event in enumerate(events, 1):
        if event.get("seq") != index:
            problems.append("seq gap at position %d (saw %r)" % (index, event.get("seq")))
            break

    # timestamps must not go backwards
    previous = None
    for event in events:
        ts = parse_iso(event.get("ts"))
        if ts is None:
            problems.append("event %s has unparseable ts" % event.get("event_id"))
            break
        if previous and ts < previous:
            problems.append("timestamp goes backwards at seq %s" % event.get("seq"))
            break
        previous = ts

    # required fields per event
    for event in events:
        for field in ("event_id", "run_id", "type", "ts", "payload"):
            if field not in event:
                problems.append("event seq %s missing %s" % (event.get("seq"), field))
        if event.get("type") not in EVENT_TYPES:
            problems.append("event seq %s has unknown type %r" % (event.get("seq"), event.get("type")))

    # phase pairing
    open_phases = []
    for event in events:
        if event.get("type") == "phase_start":
            open_phases.append(event.get("phase"))
        elif event.get("type") == "phase_end":
            if not open_phases:
                problems.append("phase_end without phase_start (seq %s)" % event.get("seq"))
            elif open_phases[-1] != event.get("phase"):
                problems.append(
                    "phase_end %r does not close %r" % (event.get("phase"), open_phases[-1])
                )
                open_phases.pop()
            else:
                open_phases.pop()
    if open_phases:
        warnings.append("phases still open: %s" % ", ".join(open_phases))

    # condition-specific expectations
    if manifest.get("condition") == "sdd":
        seen = {e.get("phase") for e in events if e.get("type") == "phase_end"}
        required = {"constitution", "specify", "plan", "tasks", "implement"}
        missing = required - seen
        if missing:
            warnings.append("SDD run missing completed phases: %s" % ", ".join(sorted(missing)))

    if not any(e.get("type") == "prompt" for e in events):
        warnings.append("no prompts captured - check hook installation")
    if not any(e.get("type") == "file_edit" for e in events):
        warnings.append("no file edits captured - check capture-edits calls")

    return problems, warnings


# --------------------------------------------------------------------------
# transcript ingestion
# --------------------------------------------------------------------------


def ingest_transcript(store, run_id, transcript_path, since=None):
    """Backfill prompts and agent outputs from a Claude Code transcript.

    The transcript is the most complete record of the conversation, but it is
    written by the agent host rather than by us, so it is treated as a
    secondary source: events carry source="transcript" and are only added for
    entries not already captured by hooks (matched on text hash).
    """
    path = Path(transcript_path)
    if not path.exists():
        raise SystemExit("sddlog: transcript not found: %s" % path)

    existing = set()
    for event in store.read_events(run_id):
        digest = event.get("payload", {}).get("sha256")
        if event.get("type") in ("prompt", "agent_output") and digest:
            existing.add(digest)

    since_dt = parse_iso(since) if since else None
    added = 0
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        role = entry.get("type") or entry.get("role")
        ts = parse_iso(entry.get("timestamp"))
        if since_dt and ts and ts < since_dt:
            continue

        message = entry.get("message") or {}
        text = _extract_text(message.get("content"))
        if not text:
            continue
        digest = sha256(text)
        if digest in existing:
            continue

        if role == "user":
            etype, actor = "prompt", "human"
        elif role == "assistant":
            etype, actor = "agent_output", "agent"
        else:
            continue

        store.append(
            run_id,
            etype,
            {
                "text": text,
                "chars": len(text),
                "words": word_count(text),
                "sha256": digest,
                "source": "transcript",
                "transcript_ts": entry.get("timestamp"),
                "model": message.get("model"),
            },
            actor=actor,
        )
        existing.add(digest)
        added += 1
    return added


def _extract_text(content):
    """Flatten Claude Code's content field (string or content-block list)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(p for p in parts if p).strip()
    return ""


# --------------------------------------------------------------------------
# hook entrypoint
# --------------------------------------------------------------------------


def handle_hook(store, event_name, raw):
    """Translate a Claude Code hook payload into sddlog events.

    Hooks must never block or fail the agent, so every path here exits 0 and
    silently no-ops when there is no active run.
    """
    run_id = store.active_run_id()
    if not run_id or not store.run_dir(run_id).exists():
        return 0
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {}

    session_id = data.get("session_id")
    if session_id:
        os.environ["SDDLOG_SESSION_ID"] = session_id

    if event_name == "SessionStart":
        store.append(
            run_id,
            "note",
            {"text": "agent session started", "session_id": session_id, "source": "hook"},
        )

    elif event_name == "UserPromptSubmit":
        text = data.get("prompt", "") or ""
        if text:
            store.append(
                run_id,
                "prompt",
                {
                    "text": text,
                    "chars": len(text),
                    "words": word_count(text),
                    "sha256": sha256(text),
                    "source": "hook",
                },
                actor="human",
            )

    elif event_name == "PostToolUse":
        tool = data.get("tool_name", "")
        tool_input = data.get("tool_input") or {}
        response = data.get("tool_response") or {}
        if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
            added, removed = _estimate_edit_size(tool, tool_input)
            store.append(
                run_id,
                "file_edit",
                {
                    "path": _relativize(store.repo, path),
                    "tool": tool,
                    "lines_added": added,
                    "lines_removed": removed,
                    "source": "hook",
                    "ok": not bool(response.get("error")),
                },
                actor="agent",
            )
        else:
            store.append(
                run_id,
                "tool_call",
                {
                    "tool": tool,
                    "args_summary": _summarize_args(tool_input),
                    "source": "hook",
                    "ok": not bool(response.get("error")),
                },
                actor="agent",
            )

    elif event_name == "Stop":
        store.append(
            run_id,
            "note",
            {"text": "agent turn ended", "session_id": session_id, "source": "hook"},
        )
    return 0


def _estimate_edit_size(tool, tool_input):
    """Line deltas as reported by the tool call itself.

    This is a fast, per-edit approximation; `capture-edits` supplies the
    authoritative git-derived counts at phase boundaries.
    """
    if tool == "Write":
        content = tool_input.get("content", "") or ""
        return len(content.splitlines()), 0
    edits = tool_input.get("edits")
    if not edits:
        edits = [tool_input]
    added = removed = 0
    for edit in edits:
        if not isinstance(edit, dict):
            continue
        old = (edit.get("old_string") or "").splitlines()
        new = (edit.get("new_string") or "").splitlines()
        for line in difflib.ndiff(old, new):
            if line.startswith("+ "):
                added += 1
            elif line.startswith("- "):
                removed += 1
    return added, removed


def _relativize(repo, path):
    if not path:
        return path
    try:
        return str(Path(path).resolve().relative_to(Path(repo).resolve()))
    except ValueError:
        return path


def _summarize_args(tool_input):
    if not isinstance(tool_input, dict):
        return ""
    for key in ("command", "pattern", "file_path", "query", "description"):
        if key in tool_input and isinstance(tool_input[key], str):
            value = tool_input[key]
            return value if len(value) <= 300 else value[:297] + "..."
    return ""


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------


def render_report(metrics):
    totals = metrics["totals"]
    lines = []
    lines.append("# Run report: %s" % metrics["run_id"])
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    for label, key in (
        ("Task", "task_id"),
        ("Condition", "condition"),
        ("Model", "model"),
        ("Agent", "agent"),
    ):
        lines.append("| %s | %s |" % (label, metrics.get(key)))
    lines.append("| Computed at | %s |" % metrics["computed_at"])
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append("| Measure | Value |")
    lines.append("| --- | --- |")
    for label, key in (
        ("Wall-clock (s)", "wall_clock_seconds"),
        ("Phases completed", "phases_completed"),
        ("Human prompts (turns)", "human_prompts"),
        ("Prompt words", "prompt_words"),
        ("Agent outputs", "agent_outputs"),
        ("Output words", "output_words"),
        ("Tool calls", "tool_calls"),
        ("Lines added", "lines_added"),
        ("Lines removed", "lines_removed"),
        ("Distinct files touched", "distinct_files_touched"),
        ("Events logged", "events"),
    ):
        lines.append("| %s | %s |" % (label, totals.get(key)))
    lines.append("")
    lines.append("## Per phase")
    lines.append("")
    lines.append("| Phase | Wall-clock (s) | Turns | Prompt words | Tool calls | Files | +Lines | -Lines |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for phase, bucket in metrics["per_phase"].items():
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s |"
            % (
                phase,
                bucket["wall_clock_seconds"],
                bucket["turns"],
                bucket["prompt_words"],
                bucket["tool_calls"],
                bucket["files_touched"],
                bucket["lines_added"],
                bucket["lines_removed"],
            )
        )
    if metrics.get("artifacts"):
        lines.append("")
        lines.append("## Artifact growth (words by phase)")
        lines.append("")
        phases_seen = []
        for per_phase in metrics["artifacts"].values():
            for phase in per_phase:
                if phase not in phases_seen:
                    phases_seen.append(phase)
        lines.append("| Artifact | %s |" % " | ".join(phases_seen))
        lines.append("| --- |%s" % ("| --- " * len(phases_seen) + "|"))
        for artifact, per_phase in metrics["artifacts"].items():
            cells = [str(per_phase.get(p, {}).get("words", "-")) for p in phases_seen]
            lines.append("| %s | %s |" % (artifact, " | ".join(cells)))
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _read_text_arg(args):
    if getattr(args, "text", None):
        return args.text
    if getattr(args, "file", None):
        return Path(args.file).read_text(errors="replace")
    if getattr(args, "stdin", False):
        return sys.stdin.read()
    raise SystemExit("sddlog: provide --text, --file, or --stdin")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sddlog", description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=None, help="repository root (default: auto-detect)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run-start", help="begin a new logged run")
    p.add_argument("--task", required=True, help="task identifier, e.g. T-SPLIT-01")
    p.add_argument("--condition", required=True, choices=sorted(CONDITIONS))
    p.add_argument("--model", required=True)
    p.add_argument("--agent", default="claude-code")
    p.add_argument("--operator", default=os.environ.get("USER", "unknown"))
    p.add_argument("--run-id", default=None)
    p.add_argument("--notes", default="")

    p = sub.add_parser("run-end", help="close the active run")
    p.add_argument("--run-id", default=None)
    p.add_argument("--status", default="completed", choices=["completed", "aborted", "failed"])
    p.add_argument("--notes", default="")

    p = sub.add_parser("phase", help="mark a Spec Kit phase boundary")
    p.add_argument("name", choices=PHASES)
    p.add_argument("--start", action="store_true")
    p.add_argument("--end", action="store_true")
    p.add_argument("--run-id", default=None)
    p.add_argument("--no-snapshot", action="store_true", help="skip artifact snapshot on --end")

    p = sub.add_parser("log-prompt", help="record a human prompt")
    p.add_argument("--text"); p.add_argument("--file"); p.add_argument("--stdin", action="store_true")
    p.add_argument("--run-id", default=None)

    p = sub.add_parser("log-output", help="record an agent output")
    p.add_argument("--text"); p.add_argument("--file"); p.add_argument("--stdin", action="store_true")
    p.add_argument("--run-id", default=None)
    p.add_argument("--model", default=None)

    p = sub.add_parser("note", help="record a free-text observation")
    p.add_argument("--text", required=True)
    p.add_argument("--run-id", default=None)

    p = sub.add_parser("capture-edits", help="record file changes since the last capture")
    p.add_argument("--label", required=True)
    p.add_argument("--run-id", default=None)

    p = sub.add_parser("snapshot", help="snapshot Spec Kit artifacts for a phase")
    p.add_argument("--phase", required=True, choices=PHASES)
    p.add_argument("--run-id", default=None)

    p = sub.add_parser("hook", help="Claude Code hook entrypoint (reads JSON on stdin)")
    p.add_argument("--event", required=True)

    p = sub.add_parser("ingest-transcript", help="backfill prompts/outputs from an agent transcript")
    p.add_argument("--path", required=True)
    p.add_argument("--run-id", default=None)
    p.add_argument("--since", default=None)

    p = sub.add_parser("metrics", help="compute and write metrics.json")
    p.add_argument("--run-id", default=None)
    p.add_argument("--print", dest="do_print", action="store_true")

    p = sub.add_parser("report", help="render a Markdown run report")
    p.add_argument("--run-id", default=None)
    p.add_argument("--out", default=None)

    p = sub.add_parser("verify", help="check a run's log integrity")
    p.add_argument("--run-id", default=None)

    p = sub.add_parser("list", help="list all runs")

    args = parser.parse_args(argv)
    store = Store(args.repo or find_repo_root())

    if args.command == "hook":
        # Hooks must never break the observed session.
        try:
            return handle_hook(store, args.event, sys.stdin.read())
        except Exception:
            return 0

    if args.command == "run-start":
        store.runs.mkdir(parents=True, exist_ok=True)
        run_id = args.run_id or store.next_run_id()
        if store.run_dir(run_id).exists():
            raise SystemExit("sddlog: run %r already exists" % run_id)
        store.run_dir(run_id).mkdir(parents=True)
        _, head = git(store.repo, "rev-parse", "HEAD")
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "task_id": args.task,
            "condition": args.condition,
            "model": args.model,
            "agent": args.agent,
            "operator": args.operator,
            "notes": args.notes,
            "started_at": now_iso(),
            "ended_at": None,
            "status": "in_progress",
            "start_commit": head or None,
            "last_capture_commit": head or None,
            "repo": str(store.repo),
        }
        store.write_manifest(run_id, manifest)
        store.active_path.parent.mkdir(parents=True, exist_ok=True)
        store.active_path.write_text(run_id + "\n")
        store.append(run_id, "run_start", {k: manifest[k] for k in
                                           ("task_id", "condition", "model", "agent", "operator")})
        store.rebuild_index()
        print(run_id)
        return 0

    if args.command == "list":
        for entry in store.rebuild_index():
            print("%-6s %-14s %-12s %-10s %s" % (
                entry["run_id"], entry["task_id"], entry["condition"],
                entry["status"], entry["started_at"]))
        return 0

    read_only = args.command in ("verify", "metrics", "report")
    run_id = store.require_run(getattr(args, "run_id", None), allow_closed=read_only)

    if args.command == "run-end":
        manifest = store.read_manifest(run_id)
        manifest["ended_at"] = now_iso()
        manifest["status"] = args.status
        if args.notes:
            manifest["notes"] = (manifest.get("notes", "") + "\n" + args.notes).strip()
        store.write_manifest(run_id, manifest)
        store.append(run_id, "run_end", {"status": args.status})
        metrics = compute_metrics(store, run_id)
        (store.run_dir(run_id) / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
        (store.run_dir(run_id) / "report.md").write_text(render_report(metrics))
        store.rebuild_index()
        if store.active_path.exists() and store.active_path.read_text().strip() == run_id:
            store.active_path.unlink()
        print("closed %s (%s)" % (run_id, args.status))
        return 0

    if args.command == "phase":
        if args.start == args.end:
            raise SystemExit("sddlog: pass exactly one of --start / --end")
        if args.start:
            store.append(run_id, "phase_start", {"phase": args.name}, phase=args.name)
        else:
            if not args.no_snapshot:
                snapshot_artifacts(store, run_id, args.name)
                capture_edits(store, run_id, "phase-%s" % args.name, phase=args.name)
            store.append(run_id, "phase_end", {"phase": args.name}, phase=args.name)
        print("%s %s" % (args.name, "started" if args.start else "ended"))
        return 0

    if args.command == "log-prompt":
        text = _read_text_arg(args)
        store.append(run_id, "prompt", {
            "text": text, "chars": len(text), "words": word_count(text),
            "sha256": sha256(text), "source": "manual"}, actor="human")
        return 0

    if args.command == "log-output":
        text = _read_text_arg(args)
        store.append(run_id, "agent_output", {
            "text": text, "chars": len(text), "words": word_count(text),
            "sha256": sha256(text), "source": "manual",
            "model": args.model or store.read_manifest(run_id).get("model")}, actor="agent")
        return 0

    if args.command == "note":
        store.append(run_id, "note", {"text": args.text, "source": "manual"}, actor="human")
        return 0

    if args.command == "capture-edits":
        rows, head = capture_edits(store, run_id, args.label)
        print("captured %d changed file(s) at %s" % (len(rows), (head or "")[:8]))
        return 0

    if args.command == "snapshot":
        names = snapshot_artifacts(store, run_id, args.phase)
        print("snapshotted: %s" % (", ".join(names) if names else "(none found)"))
        return 0

    if args.command == "ingest-transcript":
        added = ingest_transcript(store, run_id, args.path, args.since)
        print("ingested %d new entries" % added)
        return 0

    if args.command == "metrics":
        metrics = compute_metrics(store, run_id)
        (store.run_dir(run_id) / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
        if args.do_print:
            print(json.dumps(metrics, indent=2))
        else:
            print(str(store.run_dir(run_id) / "metrics.json"))
        return 0

    if args.command == "report":
        metrics = compute_metrics(store, run_id)
        text = render_report(metrics)
        out = Path(args.out) if args.out else (store.run_dir(run_id) / "report.md")
        out.write_text(text)
        print(str(out))
        return 0

    if args.command == "verify":
        problems, warnings = verify_run(store, run_id)
        for warning in warnings:
            print("WARN  %s" % warning)
        for problem in problems:
            print("FAIL  %s" % problem)
        if not problems:
            print("OK    %s passed %d integrity checks" % (run_id, 6))
        return 1 if problems else 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
