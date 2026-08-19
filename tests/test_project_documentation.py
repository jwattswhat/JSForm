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
            "Documentation/PUBLIC_API.md", "Documentation/RELEASING.md",
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

    def test_compatibility_requirements_match_project_dependencies(self):
        metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        requirements = {
            line.strip() for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        dependency_block = metadata.split("dependencies = [", 1)[1].split("]", 1)[0]
        declared = {
            match.group(1) for match in re.finditer(r'^\s*"([^"]+)",?\s*$', dependency_block, re.MULTILINE)
        }
        self.assertEqual(requirements, declared)

    def test_source_manifest_includes_public_project_material(self):
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertIn("recursive-include Documentation *.md", manifest)
        self.assertIn("recursive-include examples", manifest)
        self.assertIn("prune DevelopmentTesting", manifest)
        self.assertIn("global-exclude Log.txt", manifest)

    def test_obsolete_external_report_integration_is_absent(self):
        obsolete_name = "Lime" + "Report"
        checked = [ROOT / "README.md", ROOT / "__init__.py", ROOT / "clsForm.py"]
        checked.extend((ROOT / "Documentation").glob("*.md"))
        checked.extend((ROOT / "Forms").glob("*.json"))
        checked.extend((ROOT / "schema").glob("*.json"))
        for path in checked:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8-sig")
                self.assertNotIn(obsolete_name.lower(), text.lower())
                self.assertNotIn("." + "lrxml", text.lower())
        for removed in (
            "fnReport.py", "report_runtime.py", "report_credentials.py",
            "Forms/frmReports.json",
        ):
            self.assertFalse((ROOT / removed).exists(), removed)

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
