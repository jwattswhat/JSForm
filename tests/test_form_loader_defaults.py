"""Regression tests for form directories omitted from application config."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from form_services import FormDefinitionLoader


class FormLoaderDefaultTests(unittest.TestCase):
    """Keep built-in forms usable without database configuration records."""

    def test_none_primary_directory_uses_required_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            definition = {
                "frmExampleFORM": {"FORM": {"title": "Example"}, "CONTROLS": {}}
            }
            (root / "frmExample.json").write_text(
                json.dumps(definition), encoding="utf-8"
            )

            form, controls = FormDefinitionLoader(None, root).load("frmExample")

        self.assertEqual(form["title"], "Example")
        self.assertEqual(controls, {})

    def test_missing_fallback_directory_is_rejected_clearly(self):
        with self.assertRaisesRegex(ValueError, "fallback form directory"):
            FormDefinitionLoader(None, None)

    def test_application_forms_override_configured_and_framework_directories(self):
        with (
            tempfile.TemporaryDirectory() as application,
            tempfile.TemporaryDirectory() as configured,
            tempfile.TemporaryDirectory() as fallback,
            patch.dict(os.environ, {"JSFORM_APPLICATION_FORMS": application}),
        ):
            definition = {
                "frmMainFORM": {
                    "FORM": {"title": "Application main form"},
                    "CONTROLS": {},
                }
            }
            Path(application, "frmMain.json").write_text(
                json.dumps(definition), encoding="utf-8"
            )

            form, controls = FormDefinitionLoader(
                configured, fallback,
            ).load("frmMain")

        self.assertEqual(form["title"], "Application main form")
        self.assertEqual(controls, {})


if __name__ == "__main__":
    unittest.main()
