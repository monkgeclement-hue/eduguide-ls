import importlib.util
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "import-bernarda-candidates.py"


def load_import_module():
    spec = importlib.util.spec_from_file_location("bernarda_candidates", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class BernardaCandidateTests(unittest.TestCase):
    def test_historical_post_remains_private_and_has_no_current_fee(self):
        module = load_import_module()
        records = json.loads((ROOT / "data" / "real" / "programmes.flat.json").read_text(encoding="utf-8"))
        candidates = [item for item in records if item.get("id") in {candidate["id"] for candidate in module.CANDIDATES}]
        self.assertEqual(len(candidates), 2)
        for record in candidates:
            self.assertEqual(record["review_status"], "needs_admin_review")
            self.assertEqual(record["source_url"], module.POST_URL)
            self.assertNotIn("fee_note", record)
            self.assertIn("2024", record["source_note"])

    def test_generated_catalogue_and_seed_keep_candidates_in_review(self):
        module = load_import_module()
        public_bundle = (ROOT / "data" / "admin-catalog.js").read_text(encoding="utf-8")
        public_records = json.loads(public_bundle.split("=", 1)[1].strip().rstrip(";"))["programmes"]
        public_ids = {record["id"] for record in public_records}
        self.assertTrue(all(candidate["id"] not in public_ids for candidate in module.CANDIDATES))

        seed = (ROOT / "supabase" / "seed.normalized.sql").read_text(encoding="utf-8")
        self.assertIn("Bernarda Home Economics School", seed)
        for candidate in module.CANDIDATES:
            self.assertIn(candidate["id"], seed)
        self.assertIn("'needs_admin_review'", seed)

    def test_historical_application_amount_is_not_tuition(self):
        module = load_import_module()
        audit = json.loads((ROOT / "data" / "real" / "source-audit.json").read_text(encoding="utf-8"))
        post = next(item for item in audit if item.get("source_url") == module.POST_URL)
        self.assertIn("M200", " ".join(post["shortage"]))
        self.assertIn("not tuition", " ".join(post["shortage"]))

    def test_original_2024_link_cannot_be_rechecked_into_current_evidence(self):
        import server
        from fastapi import HTTPException

        module = load_import_module()
        candidate_id = module.CANDIDATES[0]["id"]
        self.assertIn(candidate_id, server.get_current_evidence_candidate_ids())
        edit = {
            "sourceUrl": module.POST_URL,
            "sourceCheckedAt": datetime.now(timezone.utc).isoformat(),
            "requirementsSummary": module.CANDIDATES[0]["requirements_summary"],
        }
        self.assertFalse(server.has_current_candidate_evidence(edit, server.CURRENT_EVIDENCE_CANDIDATE_SOURCE_URLS[candidate_id]))
        with self.assertRaises(HTTPException) as error:
            server.validate_current_evidence_catalogue_review_state({
                "programmeStatuses": {candidate_id: "approved"},
                "programmeEdits": {candidate_id: {**edit, "reviewStatus": "approved"}},
            })
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
