import csv
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_analysis_view import prepare, sha

class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.schedule=self.root/'schedule.csv'
        with self.schedule.open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['run_id','task_id','condition','round','purpose'])
            w.writerow(['R011','T-REDACT-01','sdd_clarify','2','study'])
        self.runs=self.root/'runs';self.scores=self.root/'scores';self.coding=self.root/'coding'
        self.time=self.root/'time.csv';self.view=self.root/'view'
        rows=[]
        for id in ('R011','R019C'):
            (self.runs/id).mkdir(parents=True)
            (self.runs/id/'metrics.json').write_text(json.dumps({'run_id':id,'totals':{'active_seconds':100}}))
            (self.runs/id/'events.jsonl').write_text('{}\n')
            self.scores.mkdir(exist_ok=True);(self.scores/(id+'.json')).write_text('{}')
            if id=='R019C':(self.scores/(id+'-regression.json')).write_text('{}')
            self.coding.mkdir(exist_ok=True)
            for kind in ['traceability','security','principles']:(self.coding/(id+'-'+kind+'.csv')).write_text('x\n')
            rows.append({'run_id':id,'raw_active_seconds':100,'corrected_active_seconds':80,
             'check':'gap_adjusted','events_sha256':sha(self.runs/id/'events.jsonl'),
             'metrics_sha256':sha(self.runs/id/'metrics.json')})
        with self.time.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    def test_replacement_mapped_without_modifying_original(self):
        self.assertEqual(prepare(self.schedule,self.runs,self.scores,self.coding,self.time,self.view),2)
        self.assertTrue((self.view/'scores'/'R011C-regression.json').exists())
        self.assertEqual(json.loads((self.view/'runs'/'R011C'/'metrics.json').read_text())['totals']['active_seconds'],80)
        self.assertEqual(json.loads((self.runs/'R019C'/'metrics.json').read_text())['totals']['active_seconds'],100)
        prov=json.loads((self.view/'provenance.json').read_text())
        self.assertEqual(prov['records'][1]['source_id'],'R019C')
    def test_stale_time_hash_fails_closed(self):
        (self.runs/'R019C'/'events.jsonl').write_text('{"changed":1}\n')
        with self.assertRaisesRegex(ValueError,'stale'):
            prepare(self.schedule,self.runs,self.scores,self.coding,self.time,self.view)
    def test_missing_regression_fails_closed(self):
        (self.scores/'R019C-regression.json').unlink()
        with self.assertRaisesRegex(ValueError,'missing inputs'):
            prepare(self.schedule,self.runs,self.scores,self.coding,self.time,self.view)

if __name__=='__main__':unittest.main()
