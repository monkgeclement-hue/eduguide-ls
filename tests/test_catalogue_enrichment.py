import importlib.util
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENRICH_SCRIPT = PROJECT_ROOT / "scripts" / "enrich-catalogue.py"


def load_enrichment_module():
  spec = importlib.util.spec_from_file_location("enrich_catalogue", ENRICH_SCRIPT)
  module = importlib.util.module_from_spec(spec)
  assert spec and spec.loader
  spec.loader.exec_module(module)
  return module


class CatalogueEnrichmentTests(unittest.TestCase):
  def test_luct_information_technology_routes_to_technology_careers(self):
    enrichment = load_enrichment_module()
    record = {
      "name": "Diploma in Information Technology",
      "category": "Technology & ICT",
      "faculty": "Faculty of Information & Communication Technology",
    }

    careers = enrichment.infer_careers(record)

    self.assertIn("IT Support Specialist", careers)
    self.assertIn("Network Administrator", careers)
    self.assertNotIn("Journalist", careers)
    self.assertNotIn("Broadcast Producer", careers)

  def test_luct_event_management_uses_event_careers_before_generic_commerce(self):
    enrichment = load_enrichment_module()
    record = {
      "name": "Diploma in Events Management",
      "category": "Business & Commerce",
      "faculty": "Faculty of Creativity in Tourism & Hospitality",
    }

    careers = enrichment.infer_careers(record)

    self.assertIn("Events Coordinator", careers)
    self.assertNotIn("Business Analyst", careers)

  def test_luct_software_engineering_keeps_software_careers(self):
    enrichment = load_enrichment_module()
    record = {
      "name": "BSc in Software Engineering with Multimedia",
      "category": "Technology & ICT",
      "faculty": "Faculty of Information & Communication Technology",
    }

    careers = enrichment.infer_careers(record)

    self.assertIn("Software Engineer", careers)
    self.assertNotIn("Network Administrator", careers)

  def test_generated_luct_it_records_do_not_keep_broadcast_careers(self):
    programmes = json.loads((PROJECT_ROOT / "data" / "real" / "programmes.flat.json").read_text(encoding="utf-8"))
    records = [
      programme for programme in programmes
      if programme.get("id") in {
        "limkokwing-university-lesotho-bsc-in-information-technology",
        "limkokwing-university-lesotho-diploma-in-information-technology",
      }
    ]

    self.assertEqual(len(records), 2)
    for record in records:
      self.assertIn("IT Support Specialist", record.get("career_options") or [])
      self.assertNotIn("Broadcast Producer", record.get("career_options") or [])


if __name__ == "__main__":
  unittest.main()
