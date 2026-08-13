from pathlib import Path
import tempfile
import unittest

from JSForm.form_services import FormDefinitionError
from JSForm.screen_definition import ScreenDefinitionLoader, save_screen_definition
from JSForm.tests.test_screen_designer import definition


class TestScreenDefinition(unittest.TestCase):
    def test_filename_root_and_form_name_must_match(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "Wrong.json"
            path.write_text(__import__("json").dumps(definition().to_dict()), encoding="utf-8")
            with self.assertRaisesRegex(FormDefinitionError, "filename"):
                ScreenDefinitionLoader().load(path)

    def test_safe_save_retains_previous_version(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "frmTest.json"
            save_screen_definition(definition(), path)
            first = path.read_text(encoding="utf-8")
            changed = definition().to_dict()
            changed["frmTestFORM"]["FORM"]["title"] = "Changed"
            save_screen_definition(ScreenDefinitionLoader().from_dict(changed), path)
            self.assertEqual(path.with_suffix(".json.bak").read_text(encoding="utf-8"), first)

    def test_legacy_internal_form_name_is_preserved(self):
        source = definition().to_dict()
        source["frmTestFORM"]["FORM"]["name"] = "HistoricalInternalName"
        loaded = ScreenDefinitionLoader().from_dict(source, "frmTest")
        self.assertEqual(loaded.form["name"], "HistoricalInternalName")


if __name__ == "__main__":
    unittest.main()
