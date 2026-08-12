from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from report_catalog import ReportCatalogModel
from report_definition import ReportDefinitionLoader, save_report_definition
from test_report_definition import valid_definition


class TestReportCatalog(unittest.TestCase):
    def test_catalog_creates_lists_and_deletes_custom_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            users = root / "users"
            starters = root / "starters"
            starters.mkdir()
            users.mkdir()
            definition = ReportDefinitionLoader().from_dict(valid_definition())
            save_report_definition(definition, starters / "CMMD01.json")
            save_report_definition(definition, users / "CMMD01.json")
            model = ReportCatalogModel(users, starters)
            custom = model.create_from(users / "CMMD01.json", "CMMD02", "Custom Directory")
            entries = model.entries()
            self.assertEqual([item["code"] for item in entries], ["CMMD01", "CMMD02"])
            self.assertTrue(entries[0]["has_starter"])
            self.assertFalse(entries[1]["has_starter"])
            model.delete(custom)
            self.assertEqual([item["code"] for item in model.entries()], ["CMMD01"])

    def test_catalog_rejects_invalid_or_duplicate_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            users = root / "users"
            starters = root / "starters"
            starters.mkdir()
            users.mkdir()
            source = users / "CMMD01.json"
            save_report_definition(ReportDefinitionLoader().from_dict(valid_definition()), source)
            model = ReportCatalogModel(users, starters)
            with self.assertRaises(ValueError):
                model.create_from(source, "1 bad", "Bad")
            with self.assertRaises(ValueError):
                model.create_from(source, "CMMD01", "Duplicate")


if __name__ == "__main__":
    unittest.main()
