"""Tests for read-only Part III evidence completeness checking."""
import csv
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preflight_part_iii import build_report, expected_runs, run_artifact


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.schedule = self.root / "schedule.csv"
        with self.schedule.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(("run_id", "task_id", "condition", "round", "purpose"))
            w.writerow(("R004", "T-ACCOUNTS-01", "sdd_secure", "1", "study"))
            w.writerow(("R011", "T-REDACT-01", "sdd_clarify", "2", "study"))
            w.writerow(("R026", "T-QNOTES-01", "sdd", "1", "study-java"))
            w.writerow(("R002", "T-SPLIT-01", "unstructured", "0", "mechanics"))

    def test_expected_python_study_runs_and_replacement(self):
        builds, runs = expected_runs(self.schedule)
        self.assertEqual(len(builds), 2)
        self.assertEqual([r["effective_id"] for r in runs], ["R004", "R004C", "R011", "R019C"])

    def test_detects_missing_without_inventing_scores(self):
        report = build_report(self.schedule, self.root / "runs", self.root / "scores",
                              self.root / "coding", self.root)
        self.assertEqual(report["expected_python_study_runs"], 4)
        self.assertEqual(report["expected_score_files"], 6)
        self.assertEqual(report["expected_coding_sheets"], 12)
        self.assertEqual(report["missing_counts"]["score_file"], 6)
        self.assertEqual(report["status"], "incomplete")

    def test_locates_nested_run_clone_metrics(self):
        path = self.root / "runs" / "R004" / "logs" / "runs" / "R004" / "metrics.json"
        path.parent.mkdir(parents=True)
        path.write_text("{}")
        self.assertEqual(run_artifact(self.root / "runs", "R004", "metrics.json"), str(path))

    def test_duplicate_ids_rejected(self):
        with self.schedule.open("a", newline="") as f:
            csv.writer(f).writerow(("R004", "T-PASTE-01", "sdd", "4", "study"))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            expected_runs(self.schedule)


if __name__ == "__main__":
    unittest.main()
