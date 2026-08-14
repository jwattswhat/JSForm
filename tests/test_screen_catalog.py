from pathlib import Path
import shutil
import tempfile
import unittest

from JSForm.screen_catalog import ScreenCatalogModel, display_screen_title, normalized_screen_name
from JSForm.tests.test_screen_designer import definition
from JSForm.screen_definition import ScreenDefinitionLoader, save_screen_definition


class TestScreenCatalog(unittest.TestCase):
    def test_plain_screen_name_gets_framework_form_prefix(self):
        self.assertEqual(normalized_screen_name("test"), "frmTest")
        self.assertEqual(normalized_screen_name("frmRoute"), "frmRoute")

    def test_catalog_title_omits_technical_form_identifier(self):
        self.assertEqual(
            display_screen_title("frmChurch", "frmChurch: Church Edit Form"),
            "Church Edit Form",
        )
        self.assertEqual(
            display_screen_title("frmPerson", "frmPerson : Person Edit Form"),
            "Person Edit Form",
        )
        self.assertEqual(display_screen_title("frmMain", "Church Manager"), "Church Manager")

    def test_saved_user_copy_is_customized_even_before_contents_change(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            users, starters = root / "users", root / "starters"
            users.mkdir(); starters.mkdir()
            starter = starters / "frmTest.json"
            custom = users / "frmTest.json"
            save_screen_definition(definition(), starter)
            shutil.copyfile(starter, custom)
            model = ScreenCatalogModel(users, starters)
            self.assertTrue(model.entries()[0]["customized"])
            changed = definition().to_dict()
            changed["frmTestFORM"]["FORM"]["title"] = "Changed"
            save_screen_definition(ScreenDefinitionLoader().from_dict(changed), custom)
            self.assertTrue(model.entries()[0]["customized"])

    def test_existing_user_copy_remains_visible_after_starter_theme_upgrade(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            users, starters = root / "users", root / "starters"
            users.mkdir(); starters.mkdir()
            old = definition().to_dict()
            themed = definition().to_dict()
            themed["frmTestFORM"]["FORM"]["theme"] = "churchmanager"
            save_screen_definition(ScreenDefinitionLoader().from_dict(old), users / "frmTest.json")
            save_screen_definition(ScreenDefinitionLoader().from_dict(themed), starters / "frmTest.json")
            self.assertTrue(ScreenCatalogModel(users, starters).entries()[0]["customized"])

    def test_new_screen_from_starter_is_custom_and_has_no_starter_dependency(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            users, starters = root / "users", root / "starters"
            users.mkdir(); starters.mkdir()
            source = starters / "frmTest.json"
            save_screen_definition(definition(), source)
            model = ScreenCatalogModel(users, starters)
            created = model.create_from(source, "frmRoute", "Route Editor")
            entry = next(item for item in model.entries() if item["name"] == "frmRoute")
            self.assertEqual(entry["path"], created)
            self.assertIsNone(entry["starter"])
            self.assertTrue(entry["customized"])
            self.assertTrue(created.is_file())
            self.assertEqual(ScreenDefinitionLoader().load(created).form_name, "frmRoute")

    def test_new_screen_accepts_a_plain_user_facing_name(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            users, starters = root / "users", root / "starters"
            users.mkdir(); starters.mkdir()
            source = starters / "frmTest.json"
            save_screen_definition(definition(), source)
            created = ScreenCatalogModel(users, starters).create_from(
                source, "route", "Route Editor"
            )
            self.assertEqual(created.name, "frmRoute.json")
            self.assertEqual(ScreenDefinitionLoader().load(created).form_name, "frmRoute")


if __name__ == "__main__": unittest.main()
