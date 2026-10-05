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

  def test_installed_app_offers_a_reload_when_a_new_service_worker_arrives(self):
    app_bundle = (PROJECT_ROOT / "app.js").read_text(encoding="utf-8")

    self.assertIn('id="app-toast-action"', self.index_html)
    self.assertIn('addEventListener("updatefound"', app_bundle)
    self.assertIn('addEventListener("controllerchange"', app_bundle)
    self.assertIn('label: "Reload"', app_bundle)

  def test_phone_navigation_stays_in_one_swipeable_row(self):
    styles = (PROJECT_ROOT / "styles.css").read_text(encoding="utf-8")
    index_html = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
    phone_styles = styles.split("@media (max-width: 760px)", 1)[1]

    self.assertIn(".side-nav {\n    display: flex;", phone_styles)
    self.assertIn("overflow-x: auto;", phone_styles)
    self.assertIn("scroll-snap-type: x proximity;", phone_styles)
    self.assertIn("flex: 0 0 86px;", phone_styles)
    self.assertIn("Swipe sideways on a phone to see more options.", index_html)

  def test_phone_profile_actions_do_not_squeeze_labels(self):
    styles = (PROJECT_ROOT / "styles.css").read_text(encoding="utf-8")
    phone_styles = styles.split("@media (max-width: 760px)", 1)[1]

    self.assertIn(".profile-actions {\n    display: grid;", phone_styles)
    self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", phone_styles)
    self.assertIn(".profile-actions .primary-button,\n  #profile-logout-button { grid-column: 1 / -1; }", phone_styles)

  def test_signed_in_shell_explains_offline_and_reconnect_sync(self):
    app_bundle = (PROJECT_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (PROJECT_ROOT / "styles.css").read_text(encoding="utf-8")

    self.assertIn('id="app-network-status"', self.index_html)
    self.assertIn("function renderAppNetworkStatus", app_bundle)
    self.assertIn("You are offline. You can keep viewing saved guidance", app_bundle)
    self.assertIn("You are back online. Checking and syncing", app_bundle)
    self.assertIn('renderAppNetworkStatus({ reconnected: true })', app_bundle)
    self.assertIn(".app-network-status", styles)


if __name__ == "__main__":
  unittest.main()
