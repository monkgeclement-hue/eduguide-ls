import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PwaAssetTests(unittest.TestCase):
  """Keep installed clients aligned with the versioned browser shell."""

  @classmethod
  def setUpClass(cls):
    cls.index_html = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
    cls.service_worker = (PROJECT_ROOT / "sw.js").read_text(encoding="utf-8")

  def test_service_worker_cache_matches_the_versioned_app_bundle(self):
    app_version = re.search(r'src="/app\.js\?v=(\d+)"', self.index_html)
    cache_version = re.search(r'CACHE_NAME = "eduguide-ls-shell-v(\d+)"', self.service_worker)

    self.assertIsNotNone(app_version, "index.html must load a versioned app bundle")
    self.assertIsNotNone(cache_version, "sw.js must use a versioned cache")
    self.assertEqual(app_version.group(1), cache_version.group(1))

  def test_service_worker_precaches_the_exact_versioned_browser_assets(self):
    styles = re.search(r'href="(/styles\.css\?v=\d+)"', self.index_html)
    app = re.search(r'src="(/app\.js\?v=\d+)"', self.index_html)

    self.assertIsNotNone(styles)
    self.assertIsNotNone(app)
    self.assertIn(f'"{styles.group(1)}"', self.service_worker)
    self.assertIn(f'"{app.group(1)}"', self.service_worker)

  def test_service_worker_activates_the_new_shell_without_waiting_for_a_restart(self):
    self.assertIn("self.skipWaiting()", self.service_worker)
    self.assertIn("self.clients.claim()", self.service_worker)


if __name__ == "__main__":
  unittest.main()
