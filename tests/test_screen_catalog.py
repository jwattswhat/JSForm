from pathlib import Path
import shutil
import tempfile
import unittest

from JSForm.screen_catalog import ScreenCatalogModel
from JSForm.tests.test_screen_designer import definition
from JSForm.screen_definition import ScreenDefinitionLoader, save_screen_definition


class TestScreenCatalog(unittest.TestCase):
    def test_equal_copy_is_starter_and_changed_copy_is_customized(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            users, starters = root / "users", root / "starters"
            users.mkdir(); starters.mkdir()
            starter = starters / "frmTest.json"
            custom = users / "frmTest.json"
            save_screen_definition(definition(), starter)
            shutil.copyfile(starter, custom)
            model = ScreenCatalogModel(users, starters)
            self.assertFalse(model.entries()[0]["customized"])
            changed = definition().to_dict()
            changed["frmTestFORM"]["FORM"]["title"] = "Changed"
            save_screen_definition(ScreenDefinitionLoader().from_dict(changed), custom)
            self.assertTrue(model.entries()[0]["customized"])


if __name__ == "__main__": unittest.main()
