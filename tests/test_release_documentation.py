"""Regression coverage for Ho-Smart documentation release synchronization."""

import unittest

from scripts.validate_release_documentation import validate


LATEST = "https://github.com/gigabytegrove/hosmart-home-assistant/releases/latest"
README = f"""# Ho-Smart

**Current integration version: v0.2.5**

See {LATEST} for releases.
"""
CHANGELOG = "# Changelog\n\n## 0.2.5\n\n- Update notes.\n"


class ReleaseDocumentationValidationTests(unittest.TestCase):
    def test_current_version_passes(self):
        self.assertEqual(validate("0.2.5", README, CHANGELOG), [])

    def test_future_manifest_bump_requires_docs_update(self):
        self.assertTrue(validate("0.2.6", README, CHANGELOG))

    def test_stale_readme_baseline_is_rejected(self):
        stale = README + "\n**v0.2.2 is the current stable baseline.**\n"
        result = validate("0.2.5", stale, CHANGELOG)
        self.assertTrue(any("stale" in issue for issue in result))

    def test_changelog_version_must_match(self):
        self.assertTrue(validate("0.2.5", README, "## 0.2.4\n"))

    def test_missing_version_line_is_rejected(self):
        self.assertTrue(validate("0.2.5", README.replace("Current integration version:", "Version:"), CHANGELOG))


if __name__ == "__main__":
    unittest.main()
