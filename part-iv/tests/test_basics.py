import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from build_index import tokenize
from query import query

class BasicTests(unittest.TestCase):
    def test_tokenizer(self):
        self.assertEqual(tokenize("Spec-driven, SDD!"), ["spec", "driven", "sdd"])
    def test_inventory_schema(self):
        self.assertEqual(json.loads((ROOT / "sources.json").read_text()), [])
    def test_specs_exist(self):
        names = ("overview", "domain_knowledge", "oracle", "collection_techniques", "distillation_techniques", "output_format", "batch_process")
        for name in names:
            self.assertTrue((ROOT / "ai_specs" / (name + ".md")).exists())
    def test_no_index_yields_empty_results(self):
        self.assertIsInstance(query("spec driven development"), list)

if __name__ == "__main__":
    unittest.main()
