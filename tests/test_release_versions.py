"""Tests for HACS-safe stable/dev GitHub release discovery."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components" / "hosmart" / "release_versions.py"
)
spec = importlib.util.spec_from_file_location("release_versions", PATH)
release_versions = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(release_versions)

latest = release_versions.latest_tag_for_channel


class ReleaseVersionsTest(unittest.TestCase):
    def setUp(self):
        self.releases = [
            {"tag_name": "v0.2.11-dev.1", "prerelease": True, "draft": True},
            {"tag_name": "v0.2.10-dev.3", "prerelease": True, "draft": False},
            {"tag_name": "v0.2.9", "prerelease": False, "draft": False},
            {"tag_name": "v0.2.8", "prerelease": False, "draft": False},
        ]

    def test_main_selects_only_stable(self):
        self.assertEqual(latest(self.releases, "main"), "v0.2.9")

    def test_dev_selects_only_published_dev_prerelease(self):
        self.assertEqual(latest(self.releases, "dev"), "v0.2.10-dev.3")

    def test_no_dev_release_is_error_not_stable_fallback(self):
        with self.assertRaisesRegex(ValueError, "No published dev"):
            latest([self.releases[2]], "dev")

    def test_other_prerelease_must_not_be_mistaken_for_dev(self):
        with self.assertRaises(ValueError):
            latest([{"tag_name":"v0.2.9-rc.1","prerelease":True}], "dev")

    def test_draft_stable_does_not_install(self):
        with self.assertRaisesRegex(ValueError,"No published stable"):
            latest([{"tag_name":"v0.2.9","draft":True,"prerelease":False}], "main")

    def test_malformed_response_fails_closed(self):
        with self.assertRaises(ValueError):
            latest({"tag_name":"v0.2.9"}, "main")
        with self.assertRaises(ValueError):
            latest(self.releases, "unknown")


if __name__ == "__main__":
    unittest.main()
