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
        for name in ("app.py", "setup_sample.py", "route_manifest.py", "route_stop_editor.py", "sample_tools.py", "version.py"):
            ast.parse((SAMPLE / name).read_text(encoding="utf-8"), filename=name)

    def test_route_screen_proves_ordered_child_editor(self):
        launcher = (SAMPLE / "app.py").read_text(encoding="utf-8")
        editor = (SAMPLE / "route_stop_editor.py").read_text(encoding="utf-8")
        self.assertIn("btnOrderedStops", launcher)
        self.assertIn("OrderedChildEditorDialog", editor)
        self.assertIn("connection.commit()", editor)
        self.assertIn("connection.rollback()", editor)

    def test_sample_has_an_independent_semantic_version(self):
        source = (SAMPLE / "version.py").read_text(encoding="utf-8")
        self.assertIn('__version__ = "0.1.0-dev"', source)
        launcher = (SAMPLE / "app.py").read_text(encoding="utf-8")
        self.assertIn("SAMPLE_VERSION", launcher)

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
        allowed_framework_tables = {"jsConfig", "jsOptions"}
        for line in schema.splitlines():
            if line.strip().upper().startswith(("DROP TABLE", "CREATE TABLE")):
                self.assertTrue(
                    "sb_" in line or any(name in line for name in allowed_framework_tables),
                    line,
                )

    def test_sample_uses_an_isolated_database_account(self):
        launcher = (SAMPLE / "app.py").read_text(encoding="utf-8")
        installer = (SAMPLE / "setup_sample.py").read_text(encoding="utf-8")
        self.assertIn('default="JSFormSample"', launcher)
        self.assertIn('default="jsform_sample"', launcher)
        self.assertIn("GRANT ALL PRIVILEGES ON JSFormSample.*", installer)
        self.assertIn('default="localhost"', installer)
        self.assertNotIn('default="church"', launcher)
        self.assertIn("admin = mariadb.connect", installer)

    def test_sample_retries_a_mistyped_database_password(self):
        launcher = (SAMPLE / "app.py").read_text(encoding="utf-8")
        self.assertIn("def connect_database(settings, attempts=3):", launcher)
        self.assertIn("error.errno != 1045", launcher)
        self.assertIn("That password was not accepted", launcher)

    def test_sample_password_can_be_reset_without_resetting_data(self):
        installer = (SAMPLE / "setup_sample.py").read_text(encoding="utf-8")
        self.assertIn('"--password-only"', installer)
        self.assertIn("if args.password_only:", installer)
        self.assertLess(
            installer.index("if args.password_only:"),
            installer.index("schema.sql"),
        )
        self.assertLess(
            installer.index("admin = mariadb.connect"),
            installer.index('Choose a password for jsform_sample'),
        )
        self.assertIn("No sample password or data was changed", installer)
        self.assertIn('"--admin-credential-target"', installer)
        self.assertIn("read_credential(args.admin_credential_target)", installer)
        self.assertIn('"--store-sample-credential"', installer)
        self.assertIn("write_credential(SAMPLE_CREDENTIAL_TARGET", installer)

    def test_sample_can_use_securely_stored_restricted_login(self):
        launcher = (SAMPLE / "app.py").read_text(encoding="utf-8")
        self.assertIn('SAMPLE_CREDENTIAL_TARGET = "JSFormSample/Database"', launcher)
        self.assertIn("read_credential(SAMPLE_CREDENTIAL_TARGET)", launcher)

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
