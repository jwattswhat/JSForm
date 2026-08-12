from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from report_definition import ReportDefinitionError, ReportDefinitionLoader, save_report_definition


def valid_definition():
    return {
        "CMMD01REPORT": {
            "REPORT": {
                "schema_version": 1,
                "name": "CMMD01",
                "title": "Member Directory",
                "dataset": "membership.directory",
                "datasetversion": 1,
                "pagesize": "letter",
                "orientation": "portrait",
                "margins": {"top": 36, "right": 36, "bottom": 36, "left": 36},
                "bands": {"Detail": {"type": "detail", "height": 72}}
            },
            "CONTROLS": {
                "FamilyName": {
                    "type": "text", "band": "Detail",
                    "position": [0, 0], "size": [200, 18],
                    "collection": "families", "field": "FamilyName", "format": "text"
                }
            }
        }
    }


class TestReportDefinition(unittest.TestCase):
    def setUp(self):
        self.loader = ReportDefinitionLoader()

    def test_uses_jsform_named_root_report_and_controls_shape(self):
        definition = self.loader.from_dict(valid_definition())
        self.assertEqual(definition.root_name, "CMMD01REPORT")
        self.assertEqual(definition.report_id, "CMMD01")
        self.assertEqual(definition.dataset_name, "membership.directory")
        self.assertIn("FamilyName", definition.controls)
        with self.assertRaises(TypeError):
            definition.controls["FamilyName"]["field"] = "Changed"

    def test_sql_and_credentials_are_not_valid_properties(self):
        for key, value in (("sql", "SELECT * FROM tblPerson"), ("password", "secret"), ("connection", {})):
            data = valid_definition()
            data["CMMD01REPORT"]["REPORT"][key] = value
            with self.subTest(key=key), self.assertRaises(ReportDefinitionError):
                self.loader.from_dict(data)

    def test_binding_cannot_contain_expression_or_sql_syntax(self):
        for field in ("FamilyName; DROP TABLE tblPerson", "person.Name", "${password}"):
            data = valid_definition()
            data["CMMD01REPORT"]["CONTROLS"]["FamilyName"]["field"] = field
            with self.subTest(field=field), self.assertRaises(ReportDefinitionError):
                self.loader.from_dict(data)

    def test_unknown_control_type_fails_closed(self):
        data = valid_definition()
        data["CMMD01REPORT"]["CONTROLS"]["FamilyName"]["type"] = "python_script"
        with self.assertRaises(ReportDefinitionError):
            self.loader.from_dict(data)

    def test_report_name_and_root_must_match(self):
        data = valid_definition()
        data["CMMD01REPORT"]["REPORT"]["name"] = "OTHER"
        with self.assertRaisesRegex(ReportDefinitionError, "does not match"):
            self.loader.from_dict(data)

    def test_control_must_reference_known_band(self):
        data = valid_definition()
        data["CMMD01REPORT"]["CONTROLS"]["FamilyName"]["band"] = "Missing"
        with self.assertRaisesRegex(ReportDefinitionError, "unknown band"):
            self.loader.from_dict(data)

    def test_save_and_reopen_preserves_definition(self):
        definition = self.loader.from_dict(valid_definition())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "member-directory.json"
            save_report_definition(definition, path)
            self.assertEqual(self.loader.load(path).to_dict(), definition.to_dict())
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_save_retains_previous_valid_version(self):
        first = self.loader.from_dict(valid_definition())
        changed_data = valid_definition()
        changed_data["CMMD01REPORT"]["REPORT"]["title"] = "Changed Directory"
        changed = self.loader.from_dict(changed_data)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            save_report_definition(first, path)
            save_report_definition(changed, path)
            backup = path.with_suffix(".json.bak")
            self.assertTrue(backup.is_file())
            self.assertEqual(self.loader.load(backup).title, first.title)


if __name__ == "__main__":
    unittest.main()
