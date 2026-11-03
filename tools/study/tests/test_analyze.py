"""Tests for tools/study/analyze.py: the exact tests, the decision rule, and a full run on made-up scores."""

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze  # noqa: E402


def test_wilcoxon_five_same_sign_pairs_gives_the_registered_floor():
    p, r = analyze.wilcoxon_exact([0.1, 0.2, 0.3, 0.4, 0.5])
    assert p == pytest.approx(0.0625)
    assert r == pytest.approx(1.0)


def test_wilcoxon_drops_zero_differences_and_handles_no_data():
    p, _ = analyze.wilcoxon_exact([0.0, 0.2, -0.2, 0.0, 0.0])
    assert p == pytest.approx(1.0)
    assert analyze.wilcoxon_exact([0, 0, 0]) == (None, None)


def test_friedman_identical_orderings_give_the_registered_floor():
    blocks = [[1, 2, 3, 4]] * 5
    p, _ = analyze.friedman_exact(blocks)
    assert p == pytest.approx(1 / 24 ** 4)


def test_friedman_with_no_differences_is_not_significant():
    p, _ = analyze.friedman_exact([[1, 1, 1, 1]] * 5)
    assert p == pytest.approx(1.0)


def test_spearman_perfect_order_gives_the_registered_floor():
    rho, p = analyze.spearman_exact([1, 2, 3, 4, 5], [10, 20, 30, 40, 50])
    assert rho == pytest.approx(1.0)
    assert p == pytest.approx(2 / 120)


def test_holm_adjusts_in_order_and_keeps_missing():
    assert analyze.holm([0.01, None, 0.04, 0.03]) == pytest.approx([0.03, None, 0.06, 0.06])


@pytest.mark.parametrize("kind, a, b, verdict", [
    ("rate", [0.9, 0.9, 0.9, 0.9, 0.5], [0.6, 0.6, 0.6, 0.6, 0.6], "consistent difference"),
    ("rate", [0.65, 0.65, 0.65, 0.65, 0.65], [0.6, 0.6, 0.6, 0.6, 0.6], "no consistent difference"),
    ("rate", [0.9, 0.9, 0.9, 0.6, 0.6], [0.6, 0.6, 0.6, 0.6, 0.6], "no consistent difference"),
    ("ratio", [700, 700, 700, 700, 100], [100, 100, 100, 100, 100], "consistent difference"),
    ("ratio", [110, 110, 110, 110, 110], [100, 100, 100, 100, 100], "no consistent difference"),
    ("count", [0, 0, 0, 0, 1], [2, 2, 1, 1, 1], "consistent difference"),
    ("count", [None] * 5, [1] * 5, "no data"),
])
def test_decision_rule(kind, a, b, verdict):
    assert analyze.decide(kind, a, b)[0] == verdict


def test_findings_count_one_root_cause_once():
    rows = [{"confirmed": "Y", "cwe": "CWE-89", "location": "app.py:12", "severity": "High"},
            {"confirmed": "Y", "cwe": "CWE-89", "location": "app.py:12", "severity": "High"},
            {"confirmed": "N", "cwe": "CWE-79", "location": "app.py:40", "severity": "Low"},
            {"confirmed": "y", "cwe": "CWE-208", "location": "auth.py:3", "severity": "Low"}]
    assert analyze.findings(rows) == 2
    assert analyze.findings(rows, {"high", "medium"}) == 1


def make_kit(tmp_path):
    kit = tmp_path / "kit"
    (kit / "schedule").mkdir(parents=True)
    rows = [["run_id", "task_id", "condition", "round", "purpose"]]
    run = 4
    for i, task in enumerate(analyze.TASKS):
        for condition in analyze.CONDITIONS:
            rows.append(["R%03d" % run, task, condition, "1", "study"])
            run += 1
    rows.append(["R099", "T-REDACT-01", "sdd", "R", "replication"])
    with open(kit / "schedule" / "schedule.csv", "w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return kit, rows[1:]


def score(stated, intent, security):
    def tier(passed):
        return {"passed": passed, "total": 10}
    return {"tiers": {"stated": tier(stated), "intent": tier(intent), "security": tier(security)}}


def test_full_run_on_made_up_scores(tmp_path):
    kit, rows = make_kit(tmp_path)
    scores = tmp_path / "scores"
    runs = tmp_path / "runs"
    scores.mkdir()
    for run_id, task, condition, _, purpose in rows:
        secure = condition == "sdd_secure"
        (scores / ("%s.json" % run_id)).write_text(json.dumps(score(10, 5, 9 if secure else 5)))
        (scores / ("%sC.json" % run_id)).write_text(json.dumps(score(10, 5, 8)))
        (scores / ("%sC-regression.json" % run_id)).write_text(json.dumps(score(10, 3, 10)))
        (runs / run_id).mkdir(parents=True)
        seconds = 600 if condition == "unstructured" else 4200
        (runs / run_id / "metrics.json").write_text(json.dumps(
            {"totals": {"active_seconds": seconds, "human_prompts": 1 if condition == "unstructured" else 6,
                        "input_tokens_all": seconds * 100, "output_tokens": seconds}}))
    out = tmp_path / "out"
    assert analyze.main(["--kit", str(kit), "--scores", str(scores), "--runs", str(runs),
                         "--out", str(out)]) == 0
    result = json.loads((out / "results.json").read_text())
    pairs = {(p["a"], p["b"]): p for p in result["measures"]["tier_c"]["pairs"]}
    assert pairs[("sdd", "sdd_secure")]["verdict"] == "consistent difference"
    assert pairs[("sdd", "sdd_secure")]["direction"] == "lower"
    assert pairs[("unstructured", "sdd")]["verdict"] == "no consistent difference"
    time_pairs = {(p["a"], p["b"]): p for p in result["measures"]["active_seconds"]["pairs"]}
    assert time_pairs[("unstructured", "sdd")]["median_effect"] == pytest.approx(1 / 7)
    assert time_pairs[("unstructured", "sdd")]["verdict"] == "consistent difference"
    assert result["measures"]["regression"]["table"]["T-TARX-01"]["sdd"] == pytest.approx(1.0)
    assert result["measures"]["findings"]["table"]["T-TARX-01"]["sdd"] is None
    assert result["replication"][0]["differences"]["tier_a"] == pytest.approx(0.0)
    text = (out / "results.md").read_text()
    assert "## Tier C pass rate (P2)" in text and "consistent difference" in text
