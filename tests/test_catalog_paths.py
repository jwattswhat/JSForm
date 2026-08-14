import tempfile
import unittest
from pathlib import Path

from JSForm.catalog_paths import CatalogDirectories, CatalogPathError


class CatalogDirectoriesTests(unittest.TestCase):
    def test_accepts_starter_and_user_json_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            user = root / "user"; starter = root / "starter"
            user.mkdir(); starter.mkdir()
            custom = user / "custom.json"; custom.write_text("{}")
            shipped = starter / "starter.json"; shipped.write_text("{}")
            paths = CatalogDirectories(user, starter)
            self.assertEqual(paths.approved(custom), custom.resolve())
            self.assertEqual(paths.approved(shipped), shipped.resolve())

    def test_rejects_files_outside_approved_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            user = root / "user"; starter = root / "starter"
            user.mkdir(); starter.mkdir()
            outside = root / "outside.json"; outside.write_text("{}")
            with self.assertRaises(CatalogPathError):
                CatalogDirectories(user, starter).approved(outside)

    def test_rejects_traversal_and_non_json_targets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            user = root / "user"; starter = root / "starter"
            user.mkdir(); starter.mkdir()
            paths = CatalogDirectories(user, starter)
            for name in ("../escape.json", "layout.txt"):
                with self.subTest(name=name), self.assertRaises(CatalogPathError):
                    paths.user_target(name)

    def test_starter_cannot_be_changed_as_a_user_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            user = root / "user"; starter = root / "starter"
            user.mkdir(); starter.mkdir()
            shipped = starter / "starter.json"; shipped.write_text("{}")
            with self.assertRaises(CatalogPathError):
                CatalogDirectories(user, starter).user_file(shipped)


if __name__ == "__main__":
    unittest.main()
