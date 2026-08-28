"""Tests for safe menu starter and customization lifecycle behavior."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from JSForm.catalog_paths import CatalogPathError
from JSForm.menu_catalog import MenuCatalogModel


def data(name="main", label="&File"):
    return {
        "schema_version": 1,
        "name": name,
        "menus": [{"label": label, "items": [{"command": "app.exit"}]}],
    }


class MenuCatalogModelTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        root = Path(self.temporary.name)
        self.starters = root / "starters"
        self.users = root / "users"
        self.starters.mkdir()
        self.starter = self.starters / "main.menu.json"
        self.starter.write_text(json.dumps(data()), encoding="utf-8")
        self.model = MenuCatalogModel(self.users, self.starters)

    def tearDown(self):
        self.temporary.cleanup()

    def test_entries_prefer_customization_and_report_invalid_files(self):
        entry = self.model.entries()[0]
        self.assertTrue(entry["valid"])
        self.assertFalse(entry["customized"])
        custom = self.model.open_customization(entry)
        changed = data(label="&Application")
        custom.write_text(json.dumps(changed), encoding="utf-8")
        entry = self.model.entries()[0]
        self.assertTrue(entry["customized"])
        self.assertEqual(entry["path"], custom.resolve())
        custom.write_text("{broken", encoding="utf-8")
        entry = self.model.entries()[0]
        self.assertFalse(entry["valid"])
        self.assertIn("Cannot read menu definition", entry["error"])

    def test_open_customization_preserves_starter(self):
        before = self.starter.read_bytes()
        custom = self.model.open_customization(self.model.entries()[0])
        self.assertTrue(custom.is_file())
        self.assertEqual(self.starter.read_bytes(), before)

    def test_create_save_previous_restore_and_delete(self):
        custom = self.model.create_from(self.starter, "secondary")
        first = self.model.loader.load(custom)
        changed = data(name="secondary", label="&Changed")
        self.model.save(self.model.loader.from_dict(changed), custom)
        entry = next(item for item in self.model.entries() if item["name"] == "secondary")
        self.assertEqual(self.model.load_previous(entry).to_dict(), first.to_dict())
        self.assertEqual(self.model.delete_customization(entry), "deleted")
        self.assertFalse(custom.exists())

    def test_load_starter_and_delete_customization_returns_to_starter(self):
        custom = self.model.open_customization(self.model.entries()[0])
        entry = self.model.entries()[0]
        self.assertEqual(self.model.load_starter(entry).to_dict(), data())
        self.assertEqual(self.model.delete_customization(entry), "starter")
        self.assertFalse(custom.exists())
        self.assertFalse(self.model.entries()[0]["customized"])

    def test_save_cannot_escape_user_directory(self):
        definition = self.model.loader.load(self.starter)
        with self.assertRaises(CatalogPathError):
            self.model.save(definition, self.starter)
        with self.assertRaises(CatalogPathError):
            self.model.save(definition, self.users.parent / "escape.json")


if __name__ == "__main__":
    unittest.main()
