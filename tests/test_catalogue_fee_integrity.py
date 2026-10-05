import copy
import importlib.util
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build-admin-catalog.py"
FEES_DIR = PROJECT_ROOT / "data" / "real" / "fees"


def load_build_module():
  spec = importlib.util.spec_from_file_location("build_admin_catalog", BUILD_SCRIPT)
  module = importlib.util.module_from_spec(spec)
  assert spec and spec.loader
  spec.loader.exec_module(module)
  return module


class CatalogueFeeIntegrityTests(unittest.TestCase):
  def setUp(self):
    self.catalogue = load_build_module()

  def test_luct_semester_breakdowns_match_their_published_totals(self):
    files = sorted(FEES_DIR.glob("limkokwing-*-fees-undated.json"))
    self.assertEqual(len(files), 3)

    for path in files:
      schedule = json.loads(path.read_text(encoding="utf-8"))
      self.catalogue.validate_fee_schedule(schedule, path)

  def test_mismatched_programme_total_is_rejected_before_public_build(self):
    path = FEES_DIR / "limkokwing-information-technology-fees-undated.json"
    schedule = json.loads(path.read_text(encoding="utf-8"))
    broken = copy.deepcopy(schedule)
    broken["programme_component_fee_items"][-1]["amount"] += 1

    with self.assertRaisesRegex(ValueError, "does not match component total"):
      self.catalogue.validate_fee_schedule(broken, path)


if __name__ == "__main__":
  unittest.main()
