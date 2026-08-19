"""Protect the public documentation and licensing baseline."""

import ast
from pathlib import Path
import re
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

    def test_package_metadata_preserves_public_identity(self):
        metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertRegex(metadata, r'(?m)^name = "jsform-desktop"$')
        self.assertIn('package-dir = {JSForm = "."}', metadata)
        self.assertIn('version = {attr = "JSForm.version.__version__"}', metadata)
        self.assertIn('"Forms/*.json"', metadata)
        self.assertIn('"schema/*.json"', metadata)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("distribution name is `jsform-desktop`", readme)
        self.assertIn("`import JSForm`", readme)

    def test_package_version_is_pep440_compatible(self):
        version_source = (ROOT / "version.py").read_text(encoding="utf-8")
        match = re.search(r'__version__\s*=\s*"([^"]+)"', version_source)
        self.assertIsNotNone(match)
        self.assertRegex(match.group(1), r"^\d+\.\d+\.\d+-(?:dev|beta\.\d+)$")

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
