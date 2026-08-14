"""Protect the public documentation and licensing baseline."""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProjectDocumentationTests(unittest.TestCase):
    def test_public_project_documents_exist(self):
        required = (
            "README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md", "SUPPORT.md",
            "Documentation/ARCHITECTURE.md", "Documentation/DEVELOPMENT.md",
            "Documentation/JSForm_Framework.md", "Documentation/VERSIONING.md",
        )
        for relative in required:
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_license_and_readme_identify_lgpl(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("LGPL-3.0-or-later", license_text)
        self.assertIn("LGPL-3.0-or-later", readme)

    def test_top_level_python_modules_have_docstrings(self):
        excluded = {"Log.txt"}
        for path in ROOT.glob("*.py"):
            if path.name in excluded:
                continue
            with self.subTest(module=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                self.assertTrue(ast.get_docstring(tree), f"{path.name} needs a module docstring")


if __name__ == "__main__":
    unittest.main()
