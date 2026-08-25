"""Tests for the approved visual menu designer's editable model."""

from copy import deepcopy
import unittest

from JSForm.menu_definition import MenuDefinitionError, MenuDefinitionLoader
from JSForm.menu_designer import MenuCommandDescriptor, MenuDesignerModel


def definition():
    return {
        "$schema": "https://jsform.local/schema/menu-definition-v1.json",
        "schema_version": 1,
        "name": "main",
        "menus": [{
            "label": "&File",
            "items": [
                {"command": "file.open", "accelerator": "Ctrl+O"},
                {"separator": True},
                {"command": "app.exit"},
            ],
        }],
    }


COMMANDS = (
    MenuCommandDescriptor("file.open", "&Open", category="File"),
    MenuCommandDescriptor("file.save", "&Save", category="File"),
    MenuCommandDescriptor("app.exit", "E&xit", category="Application"),
    MenuCommandDescriptor(
        "view.mode", "&Mode", category="View", allowed_kinds=("normal", "radio")
    ),
)


class MenuDesignerModelTests(unittest.TestCase):
    def setUp(self):
        self.model = MenuDesignerModel(
            MenuDefinitionLoader().from_dict(definition()), COMMANDS
        )

    def test_add_update_delete_duplicate_and_detached_output(self):
        submenu = self.model.add_submenu((0,), "&Recent")
        command = self.model.add_command(submenu, "file.save")
        self.model.update_node(command, label="Save &Copy", accelerator="Ctrl+S")
        duplicate = self.model.duplicate(command)
        self.assertEqual(self.model.node(duplicate)["command"], "file.save")
        self.model.delete(duplicate)
        output = self.model.to_dict()
        output["menus"][0]["label"] = "Changed"
        self.assertEqual(self.model.node((0,))["label"], "&File")

    def test_each_change_is_undoable_and_redoable(self):
        original = self.model.to_dict()
        self.model.add_command((0,), "file.save")
        changed = self.model.to_dict()
        self.assertTrue(self.model.dirty)
        self.assertTrue(self.model.undo())
        self.assertEqual(self.model.to_dict(), original)
        self.assertTrue(self.model.redo())
        self.assertEqual(self.model.to_dict(), changed)
        self.model.mark_saved()
        self.assertFalse(self.model.dirty)

    def test_move_indent_and_outdent_are_deterministic(self):
        submenu = self.model.add_submenu((0,), "&Recent", index=0)
        command = self.model.add_command((0,), "file.save", index=1)
        indented = self.model.indent(command)
        self.assertEqual(indented, (0, 0, 0))
        outdented = self.model.outdent(indented)
        self.assertEqual(outdented, (0, 1))
        self.assertEqual(self.model.move_down((0, 1)), (0, 2))
        self.assertEqual(self.model.move_up((0, 2)), (0, 1))

    def test_rejected_changes_leave_history_and_data_unchanged(self):
        before = self.model.to_dict()
        with self.assertRaises(ValueError):
            self.model.add_command((0,), "unknown.command")
        with self.assertRaises(ValueError):
            self.model.indent((0, 0))
        self.assertEqual(self.model.to_dict(), before)
        self.assertFalse(self.model.can_undo)

    def test_validation_reports_unknown_commands_and_mnemonic_warning(self):
        changed = deepcopy(definition())
        changed["menus"][0]["label"] = "File"
        changed["menus"][0]["items"][0]["command"] = "missing.command"
        model = MenuDesignerModel(changed, COMMANDS)
        issues = model.validate()
        self.assertTrue(any("Unknown command" in item.message for item in issues))
        self.assertTrue(any(item.severity == "warning" for item in issues))
        with self.assertRaises(MenuDefinitionError):
            model.to_definition()

    def test_runtime_round_trip_is_deterministic(self):
        self.assertEqual(self.model.to_definition().to_dict(), definition())

    def test_descriptor_rejects_invalid_metadata(self):
        with self.assertRaises(ValueError):
            MenuCommandDescriptor("", "Label")
        with self.assertRaises(ValueError):
            MenuCommandDescriptor("file.open", "Open", allowed_kinds=("button",))

    def test_descriptor_generator_is_consumed_once(self):
        model = MenuDesignerModel(definition(), (item for item in COMMANDS))
        self.assertEqual(set(model.commands), {item.name for item in COMMANDS})


if __name__ == "__main__":
    unittest.main()
