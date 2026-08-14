"""Structural tests for the standalone JSForm School Bus Sample."""

import ast
import json
import unittest
from pathlib import Path

from JSForm.form_services import FormDefinitionLoader
from JSForm.report_definition import ReportDefinitionLoader


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "JSFormSample"
FORMS = SAMPLE / "Forms"


class SampleApplicationTests(unittest.TestCase):
    def test_sample_is_framework_only_and_has_no_security_ui(self):
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in SAMPLE.glob("*.py")
        )
        self.assertIn("import JSForm", source)
        self.assertNotIn("ChurchManager", source)
        self.assertIn("AllowAllAuthorizationPolicy", source)
        for forbidden in ("Login", "PasswordService", "UserAdministration"):
            self.assertNotIn(forbidden, source)

    def test_launcher_and_setup_compile(self):
        for name in ("app.py", "setup_sample.py", "route_manifest.py", "sample_tools.py"):
            ast.parse((SAMPLE / name).read_text(encoding="utf-8"), filename=name)

    def test_mail_sample_is_preview_only(self):
        source = (SAMPLE / "sample_tools.py").read_text(encoding="utf-8")
        self.assertIn("Fake Mail Preview", source)
        self.assertNotIn("SMTPTransport", source)
        self.assertNotIn(".send(", source)

    def test_route_manifest_is_a_valid_native_report(self):
        definition = ReportDefinitionLoader().load(SAMPLE / "Reports" / "SBRT01.json")
        self.assertEqual(definition.dataset_name, "sample.routemanifest")
        self.assertEqual(definition.report_id, "SBRT01")
        self.assertIn("Stops", definition.controls)

    def test_reset_schema_owns_only_prefixed_tables(self):
        schema = (SAMPLE / "schema.sql").read_text(encoding="utf-8")
        self.assertNotIn("ChurchDB", schema)
        self.assertNotIn("tblUser", schema)
        for table in ("school", "driver", "bus", "route", "route_stop", "student"):
            self.assertIn("sb_{}".format(table), schema)
        for line in schema.splitlines():
            if line.strip().upper().startswith(("DROP TABLE", "CREATE TABLE")):
                self.assertIn("sb_", line)

    def test_every_sample_form_loads_and_root_name_matches_filename(self):
        loader = FormDefinitionLoader(FORMS, FORMS)
        for path in FORMS.glob("*.json"):
            with self.subTest(form=path.stem):
                definition = loader.load(path.stem)
                form, controls = definition
                self.assertEqual(form["name"], path.stem)
                self.assertIsInstance(controls, dict)

    def test_phone_fields_use_framework_phone_format(self):
        definitions = [json.loads(path.read_text(encoding="utf-8")) for path in FORMS.glob("*.json")]
        phone_controls = []
        for definition in definitions:
            root = next(iter(definition.values()))
            phone_controls.extend(
                control for control in root["CONTROLS"].values()
                if "Phone" in control.get("name", "") and control.get("type") == "TextCtrl"
            )
        self.assertTrue(phone_controls)
        self.assertTrue(all(control.get("format") == "phone" for control in phone_controls))


if __name__ == "__main__":
    unittest.main()
