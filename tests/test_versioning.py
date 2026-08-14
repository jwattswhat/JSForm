"""Checks for JSForm's authoritative semantic version."""

import re
import unittest

import JSForm
from JSForm.error_reporting import configure_error_reporting


class VersioningTests(unittest.TestCase):
    def test_public_version_is_semantic_development_version(self):
        self.assertRegex(JSForm.__version__, r"^\d+\.\d+\.\d+-dev$")

    def test_error_reporting_uses_framework_version_by_default(self):
        reporter = configure_error_reporting(application_name="Version Test")
        self.assertEqual(reporter.config.jsform_version, JSForm.__version__)


if __name__ == "__main__":
    unittest.main()
