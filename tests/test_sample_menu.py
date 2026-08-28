import ast
from pathlib import Path
import unittest

from menu_definition import MenuDefinitionLoader


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "JSFormSample"
MENU_PATH = SAMPLE / "Menus" / "main.menu.json"


def command_names(items):
    for item in items:
        if "command" in item:
            yield item["command"]
        elif "items" in item:
            yield from command_names(item["items"])


class TestSampleMenu(unittest.TestCase):
    def test_sample_menu_is_valid_and_has_standard_sections(self):
        definition = MenuDefinitionLoader().load(MENU_PATH)
        self.assertEqual(definition.name, "main")
        self.assertEqual(
            [menu["label"] for menu in definition.menus],
            ["&File", "&Records", "&Reports", "&Tools", "&Help"],
        )

    def test_every_menu_command_is_registered_by_sample_source(self):
        definition = MenuDefinitionLoader().load(MENU_PATH)
        source = (SAMPLE / "app.py").read_text(encoding="utf-8")
        for name in command_names(definition.menus):
            with self.subTest(command=name):
                if name in {"app.exit", "app.about"}:
                    self.assertIn("standard_application_commands", source)
                else:
                    self.assertIn('"{}"'.format(name), source)

    def test_sample_uses_registry_for_both_menu_and_buttons(self):
        source = (SAMPLE / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertIn("JSForm.CommandRegistry()", source)
        self.assertIn("JSForm.MenuDefinitionLoader()", source)
        self.assertIn("JSForm.MenuInstaller(", source)
        self.assertIn('source="button"', source)
        self.assertTrue(any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "dispatch"
            for node in ast.walk(tree)
        ))

    def test_menu_json_contains_no_executable_python_or_sql(self):
        text = MENU_PATH.read_text(encoding="utf-8")
        for forbidden in ("handler", "module", "python", "SELECT ", "INSERT ", "password"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
