"""Tests for run_build.py, driven by a stand-in for the Claude Code CLI.

No model is called: tests/fake_claude.py answers each `claude -p` call from the
message it is sent. Each test builds a small fake study kit (one task, its
change request, prompts, answer sheets, the real checker) and a fake run
clone (a git repository with the real sddlog), then runs the tool with a
scripted operator.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

STUDY = Path(__file__).resolve().parents[1]
REPO = STUDY.parents[1]
FAKE_CLAUDE = Path(__file__).resolve().parent / "fake_claude.py"
sys.path.insert(0, str(STUDY))

import run_build  # noqa: E402

TASK_TEXT = "Build fakepkg: `python -m fakepkg` prints hello."
CR_TEXT = "CR-FEATURE: with --cr, fakepkg first prints changed."


@pytest.fixture
def kit(tmp_path):
    root = tmp_path / "kit"
    (root / "schedule").mkdir(parents=True)
    (root / "schedule" / "schedule.csv").write_text(
        "run_id,task_id,condition,round,purpose\n"
        "R004,T-FAKE-01,sdd_clarify,1,study\n"
        "R005,T-FAKE-01,unstructured,1,study\n"
        "R006,T-FAKE-01,sdd_secure,1,study\n")
    (root / "prompts").mkdir()
    (root / "prompts" / "constitution.txt").write_text("/speckit-constitution plain principles")
    (root / "prompts" / "constitution-secure.txt").write_text("/speckit-constitution SECURE principles")
    (root / "prompts" / "plan.txt").write_text("/speckit-plan ASK-ME use the standard library")
    for task, text, examples in [
        ("T-FAKE-01", TASK_TEXT, {"task": "T-FAKE-01", "package": "fakepkg", "kind": "cli", "examples": [
            {"show": "python -m fakepkg", "args": [], "expect": {"exit": 0, "stdout": "hello\n"}}]}),
        ("T-FAKE-01-CR", CR_TEXT, {"task": "T-FAKE-01-CR", "package": "fakepkg", "kind": "cli",
                                   "includes": ["T-FAKE-01"], "examples": [
            {"show": "python -m fakepkg --cr", "args": ["--cr"],
             "expect": {"exit": 0, "stdout": "changed\nhello\n"}}]}),
    ]:
        (root / "tasks" / task).mkdir(parents=True)
        (root / "tasks" / task / "prompt.md").write_text(text)
        (root / "tasks" / task / "examples.json").write_text(json.dumps(examples))
    sheets = root / "operator" / "answer-sheets"
    sheets.mkdir(parents=True)
    (sheets / "T-FAKE-01.md").write_text(
        "| Entry | The agent asks about... | Reply (verbatim) |\n| --- | --- | --- |\n"
        "| I1 | case of names | Names are case-sensitive. |\n"
        "| I2 | empty names | Reject them with exit status 2. |\n")
    (sheets / "T-FAKE-01-CR.md").write_text(
        "| Entry | The agent asks about... | Reply (verbatim) |\n| --- | --- | --- |\n"
        "| I1 | --cr with other options | Ignore the other options. |\n")
    (root / "tools" / "study").mkdir(parents=True)
    shutil.copy(STUDY / "check_examples.py", root / "tools" / "study" / "check_examples.py")
    return root


@pytest.fixture
def clone(tmp_path, monkeypatch):
    root = tmp_path / "run"
    (root / "tools" / "sddlog").mkdir(parents=True)
    shutil.copy(REPO / "tools" / "sddlog" / "sddlog.py", root / "tools" / "sddlog" / "sddlog.py")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    (root / ".gitignore").write_text("__pycache__/\n")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)
    monkeypatch.chdir(root)
    monkeypatch.setenv("FAKE_CALLS", str(tmp_path / "calls.jsonl"))
    for name in ("FAKE_BUG", "FAKE_FAIL_ONCE"):
        monkeypatch.delenv(name, raising=False)
    return root


def add_spec_kit(clone):
    (clone / ".specify" / "memory").mkdir(parents=True)
    (clone / ".specify" / "memory" / "constitution.md").write_text("# Constitution\n")
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-qm", "spec kit"], check=True)


def run_tool(kit, tmp_path, run_id, choices, *extra):
    script = tmp_path / ("operator-%s.txt" % run_id)
    script.write_text("\n".join(choices) + "\n")
    return run_build.main([run_id, "--kit", str(kit), "--claude", "%s %s" % (sys.executable, FAKE_CLAUDE),
                           "--script", str(script), "--no-spec-kit-setup"] + list(extra))


def calls(tmp_path):
    path = tmp_path / "calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def events(clone, run_id):
    path = clone / "logs" / "runs" / run_id / "events.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def notes(clone, run_id):
    return [e["payload"]["text"] for e in events(clone, run_id) if e["type"] == "note"]


# ---------------------------------------------------------------------------


def test_unstructured_build_sends_the_task_text_once(kit, clone, tmp_path):
    assert run_tool(kit, tmp_path, "R005", ["done"]) == 0
    sent = calls(tmp_path)
    assert [c["message"] for c in sent] == [TASK_TEXT]
    assert "--resume" not in sent[0]["argv"]
    assert "--model" in sent[0]["argv"] and "claude-opus-5" in sent[0]["argv"]
    phases = [e["phase"] for e in events(clone, "R005") if e["type"] == "phase_end"]
    assert phases == ["implement"]
    manifest = json.loads((clone / "logs" / "runs" / "R005" / "manifest.json").read_text())
    assert manifest["status"] == "completed" and manifest["stage"] == "build"
    assert len(list((clone / "logs" / "runs" / "R005" / "headless").glob("*.json"))) == 1


def test_failing_examples_get_the_checker_follow_up_in_the_same_session(kit, clone, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BUG", "1")
    assert run_tool(kit, tmp_path, "R005", ["done", "done"]) == 0
    sent = calls(tmp_path)
    assert len(sent) == 2
    assert sent[1]["message"].startswith("I ran the examples from the task description.")
    assert sent[1]["argv"][sent[1]["argv"].index("--resume") + 1] == sent[0]["session"]
    assert not any(n.startswith("CAP REACHED") for n in notes(clone, "R005"))


def test_follow_up_cap_ends_the_run_with_a_note(kit, clone, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BUG", "always")
    assert run_tool(kit, tmp_path, "R005", ["done", "done"], "--max-follow-ups", "1") == 0
    assert len(calls(tmp_path)) == 2
    assert any(n.startswith("CAP REACHED: follow-up cap") for n in notes(clone, "R005"))
    manifest = json.loads((clone / "logs" / "runs" / "R005" / "manifest.json").read_text())
    assert manifest["status"] == "completed"


def test_sdd_clarify_build_runs_every_phase_with_the_fixed_prompts(kit, clone, tmp_path):
    add_spec_kit(clone)
    # constitution, specify, clarify, plan (asks a question -> I1), plan again, tasks, implement
    choices = ["done", "done", "done", "I1", "done", "done", "done"]
    assert run_tool(kit, tmp_path, "R004", choices) == 0
    sent = [c["message"] for c in calls(tmp_path)]
    assert sent == [
        "/speckit-constitution plain principles",
        "/speckit-specify " + TASK_TEXT,
        "/speckit-clarify",
        "/speckit-plan ASK-ME use the standard library",
        "Names are case-sensitive.",
        "/speckit-tasks",
        "/speckit-implement",
    ]
    phases = [e["phase"] for e in events(clone, "R004") if e["type"] == "phase_end"]
    assert phases == ["constitution", "specify", "clarify", "plan", "tasks", "implement"]
    assert any(n.startswith("ANSWER I1:") for n in notes(clone, "R004"))


def test_each_phase_starts_a_fresh_session(kit, clone, tmp_path):
    add_spec_kit(clone)
    run_tool(kit, tmp_path, "R004", ["done", "done", "done", "I1", "done", "done", "done"])
    sent = calls(tmp_path)
    fresh = [c for c in sent if "--resume" not in c["argv"]]
    assert len(fresh) == 6
    assert len({c["session"] for c in fresh}) == 6


def test_secure_condition_uses_the_secure_constitution(kit, clone, tmp_path):
    add_spec_kit(clone)
    assert run_tool(kit, tmp_path, "R006", ["done", "done", "I1", "done", "done", "done"]) == 0
    assert calls(tmp_path)[0]["message"] == "/speckit-constitution SECURE principles"


def test_several_entries_get_one_reply_in_order(kit, clone, tmp_path):
    add_spec_kit(clone)
    run_tool(kit, tmp_path, "R004", ["done", "done", "done", "I2,i1", "done", "done", "done"])
    replies = [c["message"] for c in calls(tmp_path) if "--resume" in c["argv"]]
    assert replies == ["Reject them with exit status 2.\n\nNames are case-sensitive."]


def test_fallbacks_permission_and_listed(kit, clone, tmp_path):
    add_spec_kit(clone)
    run_tool(kit, tmp_path, "R004",
             ["permit", "done", "listed", "safety", "nopref", "done", "done", "done", "done"])
    replies = [c["message"] for c in calls(tmp_path) if "--resume" in c["argv"]]
    assert replies == [run_build.PERMIT, run_build.SAFETY, run_build.NOPREF]
    texts = notes(clone, "R004")
    assert any(n.startswith("LISTED:") for n in texts)
    assert any(n.startswith("ANSWER SAFETY:") for n in texts)


def test_change_request_runs_without_constitution_and_checks_both_example_sets(kit, clone, tmp_path,
                                                                               monkeypatch):
    assert run_tool(kit, tmp_path, "R005", ["done"]) == 0
    assert run_tool(kit, tmp_path, "R005C", ["done"]) == 0
    sent = calls(tmp_path)
    assert sent[-1]["message"] == CR_TEXT
    manifest = json.loads((clone / "logs" / "runs" / "R005C" / "manifest.json").read_text())
    assert manifest["task_id"] == "T-FAKE-01-CR" and manifest["stage"] == "change"
    out = subprocess.run([sys.executable, str(kit / "tools" / "study" / "check_examples.py"),
                          "T-FAKE-01-CR", "--repo", "."], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout
    assert "examples of T-FAKE-01" in out.stdout


def test_sdd_change_request_skips_the_constitution(kit, clone, tmp_path):
    add_spec_kit(clone)
    run_tool(kit, tmp_path, "R004", ["done", "done", "done", "I1", "done", "done", "done"])
    before = len(calls(tmp_path))
    run_tool(kit, tmp_path, "R004C", ["done", "done", "done", "done", "done", "done", "done"],
             "--max-follow-ups", "0")
    sent = [c["message"] for c in calls(tmp_path)[before:]]
    assert sent[0] == "/speckit-specify " + CR_TEXT
    assert not any(m.startswith("/speckit-constitution") for m in sent)
    phases = [e["phase"] for e in events(clone, "R004C") if e["type"] == "phase_end"]
    assert phases == ["specify", "clarify", "plan", "tasks", "implement"]


def test_interrupted_session_is_resumed_with_the_fixed_message(kit, clone, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_FAIL_ONCE", str(tmp_path / "failed.flag"))
    assert run_tool(kit, tmp_path, "R005", ["y", "done"]) == 0
    sent = calls(tmp_path)
    assert sent[1]["message"] == run_build.RESUME
    assert "--resume" in sent[1]["argv"]
    assert any(n.startswith("RESUME:") for n in notes(clone, "R005"))


def test_unstructured_run_refuses_a_repository_with_spec_kit(kit, clone, tmp_path):
    add_spec_kit(clone)
    assert run_tool(kit, tmp_path, "R005", ["done"]) == 2
    assert calls(tmp_path) == []


def test_unknown_run_id_is_refused(kit, clone, tmp_path):
    assert run_tool(kit, tmp_path, "R099", ["done"]) == 2


def test_answer_sheets_of_a_change_request_include_the_original_entries(kit):
    answers = run_build.answer_sheets(kit, "T-FAKE-01-CR")
    assert answers["I1"] == "Ignore the other options."
    assert answers["orig:I1"] == "Names are case-sensitive."


def test_real_answer_sheets_parse(tmp_path):
    for sheet in sorted((REPO / "operator" / "answer-sheets").glob("T-*.md")):
        answers = run_build.load_answer_sheet(sheet)
        has_table = "| Entry |" in sheet.read_text()
        assert bool(answers) == has_table, sheet
        assert all(key.startswith("I") and value for key, value in answers.items()), sheet


def test_phase_prompts_for_the_real_tasks():
    for task in ("T-REDACT-01", "T-PASTE-01-CR"):
        assert run_build.phase_prompt(REPO, task, "unstructured", "implement") == \
            (REPO / "tasks" / task / "prompt.md").read_text().strip()
        text = (REPO / "tasks" / task / "prompt.md").read_text().strip()
        assert run_build.phase_prompt(REPO, task, "sdd", "specify") == "/speckit-specify " + text
    assert "Secure by default" in run_build.phase_prompt(REPO, "T-REDACT-01", "sdd_secure", "constitution")
    assert "Secure by default" not in run_build.phase_prompt(REPO, "T-REDACT-01", "sdd", "constitution")


def test_schedule_maps_change_requests():
    assert run_build.schedule_row(REPO, "R004C")[2] == "change"
    task, condition, stage = run_build.schedule_row(REPO, "R004")
    assert stage == "build" and not task.endswith("-CR")
    assert run_build.schedule_row(REPO, "R004C")[0] == task + "-CR"


def test_clean_env_gives_each_run_its_own_config_and_drops_other_variables(kit, clone, tmp_path,
                                                                            monkeypatch):
    monkeypatch.setenv("CLAUDE_EFFORT", "max")
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    monkeypatch.setattr(run_build, "CLEAN_ENV_KEEP", run_build.CLEAN_ENV_KEEP + ("FAKE_CALLS",))
    config = tmp_path / "configs"
    assert run_tool(kit, tmp_path, "R005", ["done"], "--clean-env", str(config)) == 0
    sent = calls(tmp_path)
    assert sent and all(c["env"]["CLAUDE_CONFIG_DIR"] == str((config / "R005").resolve()) for c in sent)
    assert all("CLAUDE_EFFORT" not in c["env"] and "CLAUDE_CODE_REMOTE" not in c["env"] for c in sent)
    assert any("clean environment" in n for n in notes(clone, "R005"))


def test_a_run_can_be_split_into_pieces_by_phase(kit, clone, tmp_path):
    add_spec_kit(clone)
    assert run_tool(kit, tmp_path, "R004", ["done", "done"], "--stop-after", "specify") == 0
    assert (clone / "logs" / "ACTIVE_RUN").read_text().strip() == "R004"
    assert run_tool(kit, tmp_path, "R004", ["done", "I1", "done"], "--start-at", "clarify",
                    "--stop-after", "plan") == 0
    assert run_tool(kit, tmp_path, "R004", ["done", "done"], "--start-at", "tasks") == 0
    sent = [c["message"] for c in calls(tmp_path)]
    assert sent == ["/speckit-constitution plain principles", "/speckit-specify " + TASK_TEXT,
                    "/speckit-clarify", "/speckit-plan ASK-ME use the standard library",
                    "Names are case-sensitive.", "/speckit-tasks", "/speckit-implement"]
    kinds = [e["type"] for e in events(clone, "R004")]
    assert kinds.count("run_start") == 1 and kinds.count("run_end") == 1
    phases = [e["phase"] for e in events(clone, "R004") if e["type"] == "phase_end"]
    assert phases == ["constitution", "specify", "clarify", "plan", "tasks", "implement"]


def test_start_at_needs_the_run_to_be_open(kit, clone, tmp_path):
    add_spec_kit(clone)
    assert run_tool(kit, tmp_path, "R004", ["done"], "--start-at", "plan") == 2

