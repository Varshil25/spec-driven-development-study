import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recompute_idle_time import correct, read_one

BASE = datetime(2026, 11, 17, tzinfo=timezone.utc)
def ev(seq,seconds,kind,source=None):
    d={"run_id":"R004", "phase":"implement", "type":kind,
       "ts":(BASE+timedelta(seconds=seconds)).isoformat()}
    if source: d["payload"]={"source":source}
    return d

class IdleTests(unittest.TestCase):
    def test_no_idle_matches_raw(self):
        data=[ev(1,0,"phase_start"),ev(2,2,"prompt","hook"),ev(3,14,"tool_call","hook"),ev(4,18,"phase_end")]
        self.assertEqual(correct(data,{"totals":{"active_seconds":14}})["corrected_active_seconds"],14)
        self.assertEqual(correct(data,{"totals":{"active_seconds":14}})["check"],"matches_raw")
    def test_gap_fully_removed(self):
        data=[ev(1,0,"phase_start"),ev(2,3,"prompt","hook"),ev(3,4000,"tool_call","hook"),ev(4,4020,"file_edit","hook")]
        r=correct(data,{"totals":{"active_seconds":4020}})
        self.assertEqual(r["corrected_active_seconds"],23)
        self.assertEqual(r["removed_idle_seconds"],3997)
        self.assertEqual(r["check"],"gap_adjusted")
    def test_operator_note_does_not_extend_hook_activity(self):
        data=[ev(1,0,"phase_start"),ev(2,5,"prompt","hook"),ev(3,7200,"note"),ev(4,7202,"phase_end")]
        self.assertEqual(correct(data,{"totals":{"active_seconds":5}})["corrected_active_seconds"],5)
    def test_duplicate_phase_refused(self):
        data=[ev(1,0,"phase_start"),ev(2,2,"phase_start"),ev(3,5,"prompt","hook")]
        with self.assertRaises(ValueError):correct(data,{"totals":{"active_seconds":5}})
    def test_mismatched_event_run_id_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/"R004";folder.mkdir()
            (folder/"events.jsonl").write_text(json.dumps({**ev(1,0,"phase_start"),"run_id":"oops"})+"\n")
            (folder/"metrics.json").write_text(json.dumps({"run_id":"R004","totals":{"active_seconds":1}}))
            with self.assertRaises(ValueError):read_one(temp,"R004")

if __name__=="__main__":unittest.main()
