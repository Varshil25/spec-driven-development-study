"""The scoring gate is tested with *missing* input fixtures, never decrypted suites."""
import csv
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from check_unseal_gate import check, EXPECTED, hash_file

class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.kit=Path(self.tmp.name)
        (self.kit/"schedule").mkdir()
        with (self.kit/"schedule/schedule.csv").open("w",newline="") as f:
            w=csv.writer(f)
            w.writerow(("run_id","task_id","condition","round","purpose"))
            w.writerow(("R036","T-REDACT-01","unstructured","4","study"))
    def test_missing_archive_never_ready(self):
        x=check(self.kit,check_verifier=False,check_packages=False)
        self.assertFalse(x["ready_for_scoring"])
        self.assertEqual(x["expected_effective_runs"],2)
        self.assertIn("R036C",x["missing_run_ids"])
    def test_unsealed_suites_must_match_hashes(self):
        x=check(self.kit,check_verifier=False,check_packages=False)
        for suite in ("build","change"):
            self.assertFalse(x["unsealed_hash_checks"][suite]["zip_sha256_matches"])
            self.assertFalse(x["unsealed_hash_checks"][suite]["tree_sha256_matches"])
    def test_frozen_hashes_are_complete(self):
        for suite in EXPECTED.values():
            self.assertEqual(len(suite["sha"]),64)
            self.assertEqual(len(suite["tree"]),64)
    def test_hash_file_known_fixture(self):
        data=self.kit/"fixture"
        data.write_bytes(b"abc")
        self.assertEqual(hash_file(data),"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
if __name__=="__main__":unittest.main()
