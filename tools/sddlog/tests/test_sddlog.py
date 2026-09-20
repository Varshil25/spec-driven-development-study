"""Tests for the sddlog capture pipeline.

These tests are the evidence that the logging protocol actually records what
the study claims it records. They drive the tool through synthetic runs --
including synthetic Claude Code hook payloads and a synthetic transcript --
and assert on the resulting event log and derived metrics.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "sddlog.py"
sys.path.insert(0, str(TOOL.parent))

import sddlog  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    """A throwaway git repo with the .specify marker sddlog looks for."""
    root = tmp_path / "repo"
    (root / ".specify" / "memory").mkdir(parents=True)
    (root / ".specify" / "memory" / "constitution.md").write_text("# Constitution\n\nBe simple.\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    (root / "README.md").write_text("seed\n")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed"], check=True)
    return root


def run_cli(repo, *args, stdin=None):
    """Invoke the CLI the way the protocol documents it."""
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--repo", str(repo)] + list(args),
        capture_output=True,
        text=True,
        input=stdin,
    )
    return proc


def start_run(repo, condition="sdd", task="T-TEST-01"):
    proc = run_cli(repo, "run-start", "--task", task, "--condition", condition,
                   "--model", "test-model", "--agent", "claude-code")
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def events_of(repo, run_id):
    return sddlog.Store(repo).read_events(run_id)


# ---------------------------------------------------------------------------
# redaction
# ---------------------------------------------------------------------------


class TestRedaction:
    def test_removes_github_token(self):
        out, fired = sddlog.redact("use ghp_" + "a" * 36 + " to push")
        assert "ghp_" not in out
        assert "github_pat" in fired

    def test_removes_assigned_secret(self):
        out, fired = sddlog.redact('API_KEY = "hunter2hunter2"')
        assert "hunter2hunter2" not in out
        assert "assigned_secret" in fired

    def test_removes_private_key_header(self):
        out, _ = sddlog.redact("-----BEGIN RSA PRIVATE KEY-----\nMII...")
        assert "BEGIN RSA PRIVATE KEY" not in out

    def test_leaves_ordinary_prose_untouched(self):
        text = "Write a CLI that splits an expense among three people."
        out, fired = sddlog.redact(text)
        assert out == text
        assert fired == []

    def test_non_string_passes_through(self):
        assert sddlog.redact(None) == (None, [])
        assert sddlog.redact(17) == (17, [])

    def test_redaction_is_applied_before_disk_write(self, repo):
        """The guarantee that matters: a secret in a prompt never lands in the log."""
        run_id = start_run(repo)
        secret = "ghp_" + "b" * 36
        run_cli(repo, "log-prompt", "--text", "deploy with %s please" % secret)
        raw = (repo / "logs" / "runs" / run_id / "events.jsonl").read_text()
        assert secret not in raw
        assert "REDACTED:github_pat" in raw
        prompt = [e for e in events_of(repo, run_id) if e["type"] == "prompt"][0]
        assert prompt["redactions"] == ["github_pat"]


# ---------------------------------------------------------------------------
# run lifecycle
# ---------------------------------------------------------------------------


class TestRunLifecycle:
    def test_run_start_creates_manifest_and_active_pointer(self, repo):
        run_id = start_run(repo)
        manifest = json.loads((repo / "logs" / "runs" / run_id / "manifest.json").read_text())
        assert manifest["task_id"] == "T-TEST-01"
        assert manifest["condition"] == "sdd"
        assert manifest["status"] == "in_progress"
        assert manifest["start_commit"]
        assert (repo / "logs" / "ACTIVE_RUN").read_text().strip() == run_id

    def test_run_ids_increment(self, repo):
        first = start_run(repo)
        run_cli(repo, "run-end")
        second = start_run(repo, condition="unstructured")
        assert first == "R001"
        assert second == "R002"

    def test_run_end_writes_metrics_and_report(self, repo):
        run_id = start_run(repo)
        run_cli(repo, "run-end", "--status", "completed")
        run_dir = repo / "logs" / "runs" / run_id
        assert (run_dir / "metrics.json").exists()
        assert (run_dir / "report.md").exists()
        assert json.loads((run_dir / "manifest.json").read_text())["status"] == "completed"
        assert not (repo / "logs" / "ACTIVE_RUN").exists()

    def test_commands_refuse_without_an_active_run(self, repo):
        proc = run_cli(repo, "log-prompt", "--text", "hello")
        assert proc.returncode != 0
        assert "no active run" in proc.stderr

    def test_condition_is_constrained(self, repo):
        proc = run_cli(repo, "run-start", "--task", "T", "--condition", "vibes", "--model", "m")
        assert proc.returncode != 0


# ---------------------------------------------------------------------------
# event log invariants
# ---------------------------------------------------------------------------


class TestEventLog:
    def test_sequence_is_dense_and_monotonic(self, repo):
        run_id = start_run(repo)
        for i in range(5):
            run_cli(repo, "note", "--text", "note %d" % i)
        seqs = [e["seq"] for e in events_of(repo, run_id)]
        assert seqs == list(range(1, len(seqs) + 1))

    def test_every_event_carries_study_identifiers(self, repo):
        run_id = start_run(repo, condition="unstructured", task="T-BASE-02")
        run_cli(repo, "log-prompt", "--text", "do the thing")
        for event in events_of(repo, run_id):
            assert event["run_id"] == run_id
            assert event["condition"] == "unstructured"
            assert event["task_id"] == "T-BASE-02"
            assert event["schema_version"] == sddlog.SCHEMA_VERSION
            assert event["ts"].endswith("Z")

    def test_events_inherit_the_open_phase(self, repo):
        run_id = start_run(repo)
        run_cli(repo, "phase", "specify", "--start")
        run_cli(repo, "log-prompt", "--text", "write the spec")
        prompt = [e for e in events_of(repo, run_id) if e["type"] == "prompt"][0]
        assert prompt["phase"] == "specify"

    def test_prompt_payload_records_size_and_hash(self, repo):
        run_id = start_run(repo)
        text = "one two three four five"
        run_cli(repo, "log-prompt", "--text", text)
        payload = [e for e in events_of(repo, run_id) if e["type"] == "prompt"][0]["payload"]
        assert payload["words"] == 5
        assert payload["chars"] == len(text)
        assert payload["sha256"] == sddlog.sha256(text)

    def test_unknown_event_type_is_rejected(self, repo):
        run_id = start_run(repo)
        store = sddlog.Store(repo)
        with pytest.raises(SystemExit):
            store.append(run_id, "telepathy", {})

    def test_log_reads_survive_reopen(self, repo):
        """Append-only: a second process must not truncate the first's log."""
        run_id = start_run(repo)
        run_cli(repo, "note", "--text", "a")
        run_cli(repo, "note", "--text", "b")
        texts = [e["payload"].get("text") for e in events_of(repo, run_id) if e["type"] == "note"]
        assert texts == ["a", "b"]


# ---------------------------------------------------------------------------
# hook capture
# ---------------------------------------------------------------------------


class TestHookCapture:
    def test_user_prompt_submit_is_captured(self, repo):
        run_id = start_run(repo)
        payload = json.dumps({"session_id": "s1", "prompt": "Add a total column"})
        proc = run_cli(repo, "hook", "--event", "UserPromptSubmit", stdin=payload)
        assert proc.returncode == 0
        prompts = [e for e in events_of(repo, run_id) if e["type"] == "prompt"]
        assert prompts[0]["payload"]["text"] == "Add a total column"
        assert prompts[0]["payload"]["source"] == "hook"
        assert prompts[0]["actor"] == "human"

    def test_write_tool_is_captured_as_file_edit(self, repo):
        run_id = start_run(repo)
        payload = json.dumps({
            "session_id": "s1",
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "src" / "app.py"), "content": "a\nb\nc\n"},
            "tool_response": {},
        })
        run_cli(repo, "hook", "--event", "PostToolUse", stdin=payload)
        edit = [e for e in events_of(repo, run_id) if e["type"] == "file_edit"][0]
        assert edit["payload"]["path"] == "src/app.py"  # relativized to the repo
        assert edit["payload"]["lines_added"] == 3
        assert edit["payload"]["tool"] == "Write"

    def test_edit_tool_line_delta_is_computed(self, repo):
        run_id = start_run(repo)
        payload = json.dumps({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(repo / "src" / "app.py"),
                "old_string": "x = 1\ny = 2\n",
                "new_string": "x = 10\ny = 2\nz = 3\n",
            },
            "tool_response": {},
        })
        run_cli(repo, "hook", "--event", "PostToolUse", stdin=payload)
        edit = [e for e in events_of(repo, run_id) if e["type"] == "file_edit"][0]
        assert edit["payload"]["lines_added"] == 2   # x = 10, z = 3
        assert edit["payload"]["lines_removed"] == 1  # x = 1

    def test_non_edit_tool_is_captured_as_tool_call(self, repo):
        run_id = start_run(repo)
        payload = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "pytest -q"},
            "tool_response": {},
        })
        run_cli(repo, "hook", "--event", "PostToolUse", stdin=payload)
        call = [e for e in events_of(repo, run_id) if e["type"] == "tool_call"][0]
        assert call["payload"]["tool"] == "Bash"
        assert call["payload"]["args_summary"] == "pytest -q"

    def test_hook_is_a_noop_with_no_active_run(self, repo):
        proc = run_cli(repo, "hook", "--event", "UserPromptSubmit",
                       stdin=json.dumps({"prompt": "hi"}))
        assert proc.returncode == 0
        assert not (repo / "logs" / "runs").exists() or not list((repo / "logs" / "runs").iterdir())

    def test_hook_never_fails_the_agent_on_bad_input(self, repo):
        """A logging bug must not break the session it is observing."""
        start_run(repo)
        for bad in ["", "not json at all", "{", json.dumps([1, 2, 3])]:
            proc = run_cli(repo, "hook", "--event", "PostToolUse", stdin=bad)
            assert proc.returncode == 0, bad

    def test_hook_secrets_are_redacted(self, repo):
        run_id = start_run(repo)
        secret = "sk-ant-" + "c" * 24
        run_cli(repo, "hook", "--event", "UserPromptSubmit",
                stdin=json.dumps({"prompt": "key is %s" % secret}))
        assert secret not in (repo / "logs" / "runs" / run_id / "events.jsonl").read_text()


# ---------------------------------------------------------------------------
# edit capture via git
# ---------------------------------------------------------------------------


class TestEditCapture:
    def test_captures_added_and_removed_lines(self, repo):
        run_id = start_run(repo)
        run_cli(repo, "capture-edits", "--label", "baseline")
        (repo / "src").mkdir()
        (repo / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
        (repo / "README.md").write_text("seed\nnow with docs\n")
        proc = run_cli(repo, "capture-edits", "--label", "after-implement")
        assert proc.returncode == 0

        edits = {e["payload"]["path"]: e["payload"]
                 for e in events_of(repo, run_id) if e["type"] == "file_edit"}
        assert edits["src/calc.py"]["lines_added"] == 2
        assert edits["README.md"]["lines_added"] == 1
        assert edits["README.md"]["lines_removed"] == 0

    def test_writes_a_unified_diff_to_disk(self, repo):
        run_id = start_run(repo)
        run_cli(repo, "capture-edits", "--label", "baseline")
        (repo / "notes.txt").write_text("hello\n")
        run_cli(repo, "capture-edits", "--label", "step-1")
        diffs = list((repo / "logs" / "runs" / run_id / "diffs").glob("*.diff"))
        assert len(diffs) == 1
        assert "+hello" in diffs[0].read_text()

    def test_diff_files_are_redacted(self, repo):
        run_id = start_run(repo)
        run_cli(repo, "capture-edits", "--label", "baseline")
        secret = "AKIA" + "D" * 16
        (repo / "config.txt").write_text("aws=%s\n" % secret)
        run_cli(repo, "capture-edits", "--label", "leak")
        diff = list((repo / "logs" / "runs" / run_id / "diffs").glob("*.diff"))[0].read_text()
        assert secret not in diff

    def test_capture_is_incremental_not_cumulative(self, repo):
        """Each capture reports only what changed since the previous one, so
        per-phase line counts do not double-count earlier phases."""
        run_id = start_run(repo)
        run_cli(repo, "capture-edits", "--label", "baseline")
        (repo / "a.txt").write_text("1\n")
        run_cli(repo, "capture-edits", "--label", "one")
        (repo / "b.txt").write_text("2\n")
        run_cli(repo, "capture-edits", "--label", "two")
        by_label = {}
        for e in events_of(repo, run_id):
            if e["type"] == "file_edit":
                by_label.setdefault(e["payload"]["capture_label"], []).append(e["payload"]["path"])
        assert by_label["one"] == ["a.txt"]
        assert by_label["two"] == ["b.txt"]


# ---------------------------------------------------------------------------
# artifact snapshots
# ---------------------------------------------------------------------------


class TestSnapshots:
    def test_snapshots_constitution(self, repo):
        run_id = start_run(repo)
        proc = run_cli(repo, "snapshot", "--phase", "constitution")
        assert "constitution" in proc.stdout
        snap = repo / "logs" / "runs" / run_id / "snapshots" / "constitution" / "constitution.md"
        assert snap.exists()
        assert "Be simple" in snap.read_text()

    def test_snapshots_feature_artifacts(self, repo):
        run_id = start_run(repo)
        feature = repo / "specs" / "001-demo"
        feature.mkdir(parents=True)
        (feature / "spec.md").write_text("# Spec\n\nthree words here\n")
        (feature / "plan.md").write_text("# Plan\n")
        (repo / ".specify" / "feature.json").write_text(
            json.dumps({"feature_directory": "specs/001-demo"}))
        run_cli(repo, "snapshot", "--phase", "plan")
        snap_dir = repo / "logs" / "runs" / run_id / "snapshots" / "plan"
        assert (snap_dir / "spec.md").exists()
        assert (snap_dir / "plan.md").exists()

    def test_snapshot_records_hash_for_drift_detection(self, repo):
        """Comparing artifact hashes across phases is how spec drift (RQ4) is
        measured, so the hash must be of the real file contents."""
        run_id = start_run(repo)
        run_cli(repo, "snapshot", "--phase", "constitution")
        event = [e for e in events_of(repo, run_id) if e["type"] == "artifact_snapshot"][0]
        source = (repo / ".specify" / "memory" / "constitution.md").read_text()
        assert event["payload"]["sha256"] == sddlog.sha256(source)
        assert event["payload"]["words"] == len(source.split())


# ---------------------------------------------------------------------------
# phase boundaries and metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_full_sdd_sequence_produces_per_phase_metrics(self, repo):
        run_id = start_run(repo)
        for phase in ("constitution", "specify", "plan", "tasks", "implement"):
            run_cli(repo, "phase", phase, "--start")
            run_cli(repo, "log-prompt", "--text", "run the %s step" % phase)
            run_cli(repo, "phase", phase, "--end")
        run_cli(repo, "run-end")

        metrics = json.loads((repo / "logs" / "runs" / run_id / "metrics.json").read_text())
        assert list(metrics["per_phase"]) == ["constitution", "specify", "plan", "tasks", "implement"]
        assert metrics["totals"]["human_prompts"] == 5
        assert metrics["totals"]["phases_completed"] == 5
        assert metrics["condition"] == "sdd"

    def test_turns_are_counted_per_phase(self, repo):
        run_id = start_run(repo)
        run_cli(repo, "phase", "specify", "--start")
        run_cli(repo, "log-prompt", "--text", "first")
        run_cli(repo, "log-prompt", "--text", "second")
        run_cli(repo, "phase", "specify", "--end")
        run_cli(repo, "phase", "plan", "--start")
        run_cli(repo, "log-prompt", "--text", "third")
        run_cli(repo, "phase", "plan", "--end")
        metrics = sddlog.compute_metrics(sddlog.Store(repo), run_id)
        assert metrics["per_phase"]["specify"]["turns"] == 2
        assert metrics["per_phase"]["plan"]["turns"] == 1

    def test_line_counts_roll_up_into_totals(self, repo):
        run_id = start_run(repo)
        run_cli(repo, "phase", "implement", "--start")
        run_cli(repo, "capture-edits", "--label", "baseline")
        (repo / "impl.py").write_text("one\ntwo\nthree\n")
        run_cli(repo, "capture-edits", "--label", "work")
        run_cli(repo, "phase", "implement", "--end")
        metrics = sddlog.compute_metrics(sddlog.Store(repo), run_id)
        assert metrics["totals"]["lines_added"] == 3
        assert metrics["totals"]["distinct_files_touched"] == 1

    def test_report_renders_markdown_tables(self, repo):
        run_id = start_run(repo)
        run_cli(repo, "phase", "specify", "--start")
        run_cli(repo, "log-prompt", "--text", "spec it")
        run_cli(repo, "phase", "specify", "--end")
        run_cli(repo, "run-end")
        report = (repo / "logs" / "runs" / run_id / "report.md").read_text()
        assert "# Run report: %s" % run_id in report
        assert "| Phase |" in report
        assert "specify" in report


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------


class TestVerify:
    def test_clean_sdd_run_passes(self, repo):
        run_id = start_run(repo)
        run_cli(repo, "capture-edits", "--label", "baseline")
        for phase in ("constitution", "specify", "plan", "tasks", "implement"):
            run_cli(repo, "phase", phase, "--start")
            run_cli(repo, "log-prompt", "--text", "do %s" % phase)
            (repo / ("%s.txt" % phase)).write_text("work\n")
            run_cli(repo, "phase", phase, "--end")
        run_cli(repo, "run-end")
        proc = run_cli(repo, "verify")
        assert proc.returncode == 0, proc.stdout
        assert "OK" in proc.stdout

    def test_incomplete_sdd_run_warns_about_missing_phases(self, repo):
        start_run(repo)
        run_cli(repo, "phase", "specify", "--start")
        run_cli(repo, "phase", "specify", "--end")
        proc = run_cli(repo, "verify")
        assert "missing completed phases" in proc.stdout
        assert "constitution" in proc.stdout

    def test_unclosed_phase_warns(self, repo):
        start_run(repo)
        run_cli(repo, "phase", "plan", "--start")
        proc = run_cli(repo, "verify")
        assert "phases still open: plan" in proc.stdout

    def test_tampered_sequence_fails(self, repo):
        run_id = start_run(repo)
        run_cli(repo, "note", "--text", "a")
        path = repo / "logs" / "runs" / run_id / "events.jsonl"
        lines = path.read_text().splitlines()
        event = json.loads(lines[-1])
        event["seq"] = 99
        lines[-1] = json.dumps(event)
        path.write_text("\n".join(lines) + "\n")
        proc = run_cli(repo, "verify")
        assert proc.returncode == 1
        assert "seq gap" in proc.stdout

    def test_missing_prompts_warns_about_hooks(self, repo):
        start_run(repo)
        proc = run_cli(repo, "verify")
        assert "no prompts captured" in proc.stdout


# ---------------------------------------------------------------------------
# transcript ingestion
# ---------------------------------------------------------------------------


class TestTranscriptIngestion:
    def _transcript(self, path):
        entries = [
            {"type": "user", "timestamp": "2026-09-17T10:00:00.000Z",
             "message": {"content": "Build the splitter"}},
            {"type": "assistant", "timestamp": "2026-09-17T10:00:05.000Z",
             "message": {"model": "claude-opus-5",
                         "content": [{"type": "text", "text": "Here is the plan."}]}},
            {"type": "summary", "timestamp": "2026-09-17T10:00:06.000Z", "summary": "ignored"},
        ]
        path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    def test_ingests_prompts_and_outputs(self, repo, tmp_path):
        run_id = start_run(repo)
        transcript = tmp_path / "session.jsonl"
        self._transcript(transcript)
        proc = run_cli(repo, "ingest-transcript", "--path", str(transcript))
        assert "ingested 2" in proc.stdout
        types = [e["type"] for e in events_of(repo, run_id) if e["type"] in ("prompt", "agent_output")]
        assert types == ["prompt", "agent_output"]

    def test_ingestion_is_idempotent(self, repo, tmp_path):
        """Re-running backfill must not duplicate turns and inflate RQ3 counts."""
        run_id = start_run(repo)
        transcript = tmp_path / "session.jsonl"
        self._transcript(transcript)
        run_cli(repo, "ingest-transcript", "--path", str(transcript))
        proc = run_cli(repo, "ingest-transcript", "--path", str(transcript))
        assert "ingested 0" in proc.stdout
        prompts = [e for e in events_of(repo, run_id) if e["type"] == "prompt"]
        assert len(prompts) == 1

    def test_hook_capture_is_not_duplicated_by_backfill(self, repo, tmp_path):
        run_id = start_run(repo)
        run_cli(repo, "hook", "--event", "UserPromptSubmit",
                stdin=json.dumps({"prompt": "Build the splitter"}))
        transcript = tmp_path / "session.jsonl"
        self._transcript(transcript)
        run_cli(repo, "ingest-transcript", "--path", str(transcript))
        prompts = [e for e in events_of(repo, run_id) if e["type"] == "prompt"]
        assert len(prompts) == 1
        assert prompts[0]["payload"]["source"] == "hook"

    def test_since_filter_excludes_earlier_turns(self, repo, tmp_path):
        run_id = start_run(repo)
        transcript = tmp_path / "session.jsonl"
        self._transcript(transcript)
        run_cli(repo, "ingest-transcript", "--path", str(transcript),
                "--since", "2026-09-17T10:00:03Z")
        kinds = [e["type"] for e in events_of(repo, run_id) if e["type"] in ("prompt", "agent_output")]
        assert kinds == ["agent_output"]

    def test_missing_transcript_is_an_error(self, repo):
        start_run(repo)
        proc = run_cli(repo, "ingest-transcript", "--path", "/nonexistent/x.jsonl")
        assert proc.returncode != 0


# ---------------------------------------------------------------------------
# phase timing reliability
#
# Added after the R001 pilot, where an operator interruption between the end of
# the agent's plan run and the phase_end marker inflated that phase's
# marker-to-marker wall clock by roughly three days.
# ---------------------------------------------------------------------------


class TestPhaseTiming:
    def _write_log(self, repo, run_id, rows):
        """Replace the event log with hand-built timestamps.

        Timing behaviour is not reproducible from real runs inside a test, so
        the log is synthesised directly and read back through the real
        metrics code path.
        """
        store = sddlog.Store(repo)
        events = []
        for seq, (ts, etype, phase, actor) in enumerate(rows, 1):
            events.append({
                "schema_version": sddlog.SCHEMA_VERSION,
                "event_id": "e%d" % seq,
                "run_id": run_id,
                "seq": seq,
                "ts": ts,
                "type": etype,
                "actor": actor,
                "phase": phase,
                "condition": "sdd",
                "task_id": "T-TEST-01",
                "session_id": None,
                "payload": (
                    {"phase": phase} if etype.startswith("phase_")
                    else {"artifact": "spec", "words": 1} if etype == "artifact_snapshot"
                    else {"words": 1}
                ),
            })
        store.events_path(run_id).write_text(
            "\n".join(json.dumps(e) for e in events) + "\n")
        return store

    def test_active_time_ignores_a_late_phase_end_marker(self, repo):
        run_id = start_run(repo)
        store = self._write_log(repo, run_id, [
            ("2026-09-17T20:00:00.000Z", "phase_start", "plan", "system"),
            ("2026-09-17T20:00:10.000Z", "prompt", "plan", "human"),
            ("2026-09-17T20:05:00.000Z", "file_edit", "plan", "agent"),
            # operator walked away; marker issued three days later
            ("2026-09-20T18:00:00.000Z", "phase_end", "plan", "system"),
        ])
        metrics = sddlog.compute_metrics(store, run_id)
        plan = metrics["per_phase"]["plan"]
        assert plan["active_seconds"] == 300.0          # 20:00:00 -> 20:05:00
        assert plan["wall_clock_seconds"] > 200000      # contaminated
        assert plan["timing_reliable"] is False
        assert plan["trailing_idle_seconds"] > 200000

    def test_prompt_phase_end_is_marked_reliable(self, repo):
        run_id = start_run(repo)
        store = self._write_log(repo, run_id, [
            ("2026-09-17T20:00:00.000Z", "phase_start", "specify", "system"),
            ("2026-09-17T20:03:00.000Z", "file_edit", "specify", "agent"),
            ("2026-09-17T20:03:05.000Z", "phase_end", "specify", "system"),
        ])
        metrics = sddlog.compute_metrics(store, run_id)
        specify = metrics["per_phase"]["specify"]
        assert specify["timing_reliable"] is True
        assert specify["active_seconds"] == 180.0
        assert specify["trailing_idle_seconds"] == 5.0
        assert metrics["timing_warnings"] == []

    def test_unreliable_phase_is_excluded_from_reliable_total(self, repo):
        run_id = start_run(repo)
        store = self._write_log(repo, run_id, [
            ("2026-09-17T20:00:00.000Z", "phase_start", "specify", "system"),
            ("2026-09-17T20:01:00.000Z", "file_edit", "specify", "agent"),
            ("2026-09-17T20:01:02.000Z", "phase_end", "specify", "system"),
            ("2026-09-17T20:02:00.000Z", "phase_start", "plan", "system"),
            ("2026-09-17T20:03:00.000Z", "file_edit", "plan", "agent"),
            ("2026-09-20T18:00:00.000Z", "phase_end", "plan", "system"),
        ])
        metrics = sddlog.compute_metrics(store, run_id)
        totals = metrics["totals"]
        assert totals["active_seconds_reliable_phases_only"] == 60.0
        assert totals["active_seconds"] == 120.0
        assert len(metrics["timing_warnings"]) == 1
        assert "plan" in metrics["timing_warnings"][0]

    def test_verify_surfaces_the_timing_warning(self, repo):
        run_id = start_run(repo)
        self._write_log(repo, run_id, [
            ("2026-09-17T20:00:00.000Z", "phase_start", "plan", "system"),
            ("2026-09-17T20:03:00.000Z", "file_edit", "plan", "agent"),
            ("2026-09-20T18:00:00.000Z", "phase_end", "plan", "system"),
        ])
        proc = run_cli(repo, "verify", "--run-id", run_id)
        assert "unreliable" in proc.stdout
        assert "use active_seconds" in proc.stdout

    def test_snapshots_do_not_count_as_activity(self, repo):
        """Snapshots are written by the instrument at phase close, so counting
        them as activity would mask exactly the idle gap we want to detect."""
        run_id = start_run(repo)
        store = self._write_log(repo, run_id, [
            ("2026-09-17T20:00:00.000Z", "phase_start", "plan", "system"),
            ("2026-09-17T20:01:00.000Z", "file_edit", "plan", "agent"),
            ("2026-09-20T17:59:00.000Z", "artifact_snapshot", "plan", "system"),
            ("2026-09-20T18:00:00.000Z", "phase_end", "plan", "system"),
        ])
        metrics = sddlog.compute_metrics(store, run_id)
        assert metrics["per_phase"]["plan"]["active_seconds"] == 60.0
        assert metrics["per_phase"]["plan"]["timing_reliable"] is False
