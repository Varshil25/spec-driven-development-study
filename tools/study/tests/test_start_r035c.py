"""Synthetic-only R035C guardrail tests: never call Claude."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from start_r035c import check

class StartTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name)
        self.kit=base/"kit";self.clone=base/"clone";self.config=base/"configs"
        for path in ("schedule","tools/study","tasks/T-TARX-01-CR","operator/answer-sheets"):
            (self.kit/path).mkdir(parents=True,exist_ok=True)
        for path in (".git",".specify","logs/runs/R035","tools/sddlog"):
            (self.clone/path).mkdir(parents=True,exist_ok=True)
        with (self.kit/"schedule/schedule.csv").open("w",newline="") as f:
            w=csv.writer(f);w.writerow(("run_id","task_id","condition","round","purpose"))
            w.writerow(("R035","T-TARX-01","sdd_clarify","4","study"))
        for f in ("tools/study/run_build.py","tasks/T-TARX-01-CR/prompt.md","operator/answer-sheets/T-TARX-01-CR.md","operator/answer-sheets/T-TARX-01.md"):
            (self.kit/f).write_text("fixture")
        (self.clone/"tools/sddlog/sddlog.py").write_text("fixture")
        (self.clone/"logs/runs/R035/manifest.json").write_text(json.dumps({
            "run_id":"R035","task_id":"T-TARX-01","condition":"sdd_clarify","status":"completed"}))
    def inspect(self):
        with patch("start_r035c.subprocess.run") as run,patch("start_r035c.sys.version_info",(3,13)):
            run.side_effect=[type("R",(),{"stdout":"","returncode":0})(),
                             type("R",(),{"stdout":"run R035 closed\n","returncode":0})()]
            return check(self.kit,self.clone,self.config,check_programs=False)
    def test_ready_frozen_clone(self):
        self.assertEqual(self.inspect()["status"],"ready")
    def test_reject_duplicate_attempt(self):
        (self.clone/"logs/runs/R035C").mkdir()
        self.assertEqual(self.inspect()["status"],"blocked")
    def test_reject_active_run(self):
        (self.clone/"logs/ACTIVE_RUN").write_text("R035C")
        self.assertEqual(self.inspect()["status"],"blocked")
    def test_reject_missing_sheet(self):
        (self.kit/"operator/answer-sheets/T-TARX-01-CR.md").unlink()
        self.assertEqual(self.inspect()["status"],"blocked")
    def test_reject_unverified_clone(self):
        (self.clone/"logs/runs/R035/manifest.json").unlink()
        self.assertEqual(self.inspect()["status"],"blocked")
if __name__=="__main__":unittest.main()
