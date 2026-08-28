import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestFormCommandContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse((ROOT / "clsForm.py").read_text(encoding="utf-8"))
        cls.form_class = next(
            node for node in cls.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "clsForm"
        )
        cls.methods = {
            node.name: node for node in cls.form_class.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def test_public_record_command_methods_exist_and_have_docstrings(self):
        for name in ("new_record", "save_record", "delete_record", "refresh_records"):
            with self.subTest(name=name):
                self.assertIn(name, self.methods)
                self.assertTrue(ast.get_docstring(self.methods[name]))

    def test_existing_button_handlers_delegate_to_public_methods(self):
        expected = {
            "_on_new_record_click": "new_record",
            "_on_update_record_click": "save_record",
            "_on_delete_record_click": "delete_record",
        }
        for handler_name, public_name in expected.items():
            calls = [
                node for node in ast.walk(self.methods[handler_name])
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
                and node.func.attr == public_name
            ]
            with self.subTest(handler=handler_name):
                self.assertEqual(len(calls), 1)

    def test_public_exports_include_menu_and_standard_command_surfaces(self):
        source = (ROOT / "__init__.py").read_text(encoding="utf-8")
        for name in (
            "ApplicationCommand", "CommandContext", "CommandRegistry", "CommandState",
            "MenuDefinition", "MenuDefinitionLoader", "MenuInstaller",
            "action_from_command", "standard_application_commands",
            "standard_edit_commands", "standard_record_commands",
        ):
            with self.subTest(name=name):
                self.assertIn(name, source)


if __name__ == "__main__":
    unittest.main()
