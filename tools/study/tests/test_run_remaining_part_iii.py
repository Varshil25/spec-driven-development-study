"""Dry-run-only tests. No Claude Code/model experiment is ever launched."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_remaining_part_iii import archived, clone_for, overview, plan

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.schedule=self.root/"schedule.csv"
        with self.schedule.open("w",newline="") as f:
            w=csv.writer(f)
            w.writerow(("run_id","task_id","condition","round","purpose"))
            w.writerow(("R035","T-TARX-01","sdd_clarify","4","study"))
            w.writerow(("R036","T-REDACT-01","unstructured","4","study"))
            w.writerow(("R011","T-REDACT-01","sdd_clarify","2","study"))
            w.writerow(("R028","T-QNOTES-01","sdd","2","study-java"))
    def put(self,id,task,cond,status="completed"):
        r=self.root/"logs"/"runs"/id
        r.mkdir(parents=True,exist_ok=True)
        (r/"manifest.json").write_text(json.dumps({"run_id":id,"task_id":task,
            "condition":cond,"status":status}))
        (r/"metrics.json").write_text("{}")
        (r/"events.jsonl").write_text("{}\n")
    def test_nominal_and_replacement_ids(self):
        self.assertEqual([x["run_id"] for x in plan(self.schedule)],
            ["R035","R035C","R036","R036C","R011","R019C"])
    def test_finds_first_pending_cell(self):
        self.put("R035","T-TARX-01","sdd_clarify")
        self.put("R035C","T-TARX-01-CR","sdd_clarify")
        self.put("R036","T-REDACT-01","unstructured")
        d=overview(self.schedule,self.root)
        self.assertEqual(d["archived"],3)
        self.assertEqual(d["next"]["run_id"],"R036C")
    def test_incomplete_run_never_counts_as_archived(self):
        self.put("R035","T-TARX-01","sdd_clarify",status="in_progress")
        self.assertFalse(archived(self.root,plan(self.schedule)[0]))
    def test_mismatched_task_never_counts_as_archived(self):
        self.put("R035","T-REDACT-01","sdd_clarify")
        self.assertFalse(archived(self.root,plan(self.schedule)[0]))
    def test_change_cannot_use_missing_clone(self):
        cell=plan(self.schedule)[3]
        with self.assertRaisesRegex(RuntimeError,"must use the completed"):
            clone_for(cell,self.root/"clones",self.root/"base")
    def test_full_frozen_schedule_has_48_cells(self):
        actual=Path(__file__).resolve().parents[3]/"schedule/schedule.csv"
        if actual.is_file():
            entries=plan(actual)
            self.assertEqual(len(entries),48)
            self.assertEqual(entries[-1]["run_id"],"R039C")

if __name__=="__main__":unittest.main()
