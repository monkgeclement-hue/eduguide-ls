import importlib.util
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMPORT_SCRIPT = PROJECT_ROOT / "scripts" / "import-supplied-college-candidates.py"


def load_import_module():
  spec = importlib.util.spec_from_file_location("supplied_college_candidates", IMPORT_SCRIPT)
  module = importlib.util.module_from_spec(spec)
  assert spec and spec.loader
  spec.loader.exec_module(module)
  return module


class SuppliedProspectusCandidateTests(unittest.TestCase):
  def test_supplied_prospectus_candidates_stay_private_until_reviewed(self):
    module = load_import_module()
    records = json.loads((PROJECT_ROOT / "data" / "real" / "programmes.flat.json").read_text(encoding="utf-8"))
    candidate_ids = {item["id"] for item in module.CANDIDATES}
    captured = [item for item in records if item.get("id") in candidate_ids]

    self.assertEqual(len(captured), len(module.CANDIDATES))
    self.assertTrue(all(item.get("review_status") == "needs_admin_review" for item in captured))
    self.assertTrue(all(item.get("source_path") in {module.SIAC_SOURCE, module.ST_ELIZABETH_SOURCE} for item in captured))

  def test_siac_preserves_its_dated_fee_and_requirement_caveat(self):
    records = json.loads((PROJECT_ROOT / "data" / "real" / "programmes.flat.json").read_text(encoding="utf-8"))
    tourism = next(item for item in records if item.get("id") == "siac-diploma-tourism-travel-management-2025-2026")

    self.assertEqual(tourism["duration"], "3 years")
    self.assertEqual(tourism["application_window"], "February to May")
    self.assertIn("M15,640", tourism["fee_note"])
    self.assertIn("admin-review candidate", tourism["source_note"])

  def test_normalized_seed_includes_unapproved_candidate_institutions(self):
    seed = (PROJECT_ROOT / "supabase" / "seed.normalized.sql").read_text(encoding="utf-8")

    self.assertIn("St Mary''s Integrative Applied College (SIAC)", seed)
    self.assertIn("St Elizabeth College", seed)
    self.assertIn("siac-diploma-tourism-travel-management-2025-2026", seed)
    self.assertIn("st-elizabeth-diploma-business-management-supplied", seed)
    self.assertIn("'needs_admin_review'", seed)

  def test_unapproved_candidates_do_not_enter_the_public_catalogue_bundle(self):
    module = load_import_module()
    bundle = (PROJECT_ROOT / "data" / "admin-catalog.js").read_text(encoding="utf-8")
    payload = json.loads(bundle.split("=", 1)[1].strip().rstrip(";"))
    public_ids = {item.get("id") for item in payload.get("programmes", [])}

    self.assertFalse(public_ids.intersection({item["id"] for item in module.CANDIDATES}))


if __name__ == "__main__":
  unittest.main()
