from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from menu_definition import (
    MenuDefinitionError, MenuDefinitionLoader, save_menu_definition,
)


def valid_definition():
    return {
        "$schema": "https://jsform.local/schema/menu-definition-v1.json",
        "schema_version": 1,
        "name": "main",
        "menus": [
            {
                "label": "&File",
                "items": [
                    {"command": "file.open", "accelerator": "Ctrl+O"},
                    {"separator": True},
                    {"command": "app.exit"},
                ],
            },
            {
                "label": "&View",
                "items": [
                    {"command": "view.status_bar", "kind": "check"},
                    {
                        "label": "&Theme",
                        "items": [
                            {
                                "command": "view.theme.system",
                                "kind": "radio",
                                "radio_group": "theme",
                            },
                            {
                                "command": "view.theme.light",
                                "kind": "radio",
                                "radio_group": "theme",
                            },
                        ],
                    },
                ],
            },
        ],
    }


class TestMenuDefinition(unittest.TestCase):
    def setUp(self):
        self.loader = MenuDefinitionLoader()

    def test_loads_immutable_definition_and_returns_detached_dict(self):
        definition = self.loader.from_dict(valid_definition())
        self.assertEqual(definition.schema_version, 1)
        self.assertEqual(definition.name, "main")
        self.assertEqual(definition.menus[0]["label"], "&File")
        with self.assertRaises(TypeError):
            definition.menus[0]["label"] = "Changed"
        changed = definition.to_dict()
        changed["menus"][0]["label"] = "Changed"
        self.assertEqual(definition.menus[0]["label"], "&File")

    def test_rejects_unknown_version_property_and_executable_fields(self):
        mutations = (
            ("schema_version", 2),
            ("unexpected", True),
        )
        for key, value in mutations:
            data = valid_definition()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(MenuDefinitionError):
                self.loader.from_dict(data)
        for key in ("python", "handler", "sql", "module"):
            data = valid_definition()
            data["menus"][0]["items"][0][key] = "dangerous.value"
            with self.subTest(key=key), self.assertRaises(MenuDefinitionError):
                self.loader.from_dict(data)

    def test_rejects_malformed_commands_accelerators_and_radio_items(self):
        cases = []
        data = valid_definition()
        data["menus"][0]["items"][0]["command"] = "Open"
        cases.append(data)
        data = valid_definition()
        data["menus"][0]["items"][0]["accelerator"] = "Control-O"
        cases.append(data)
        data = valid_definition()
        data["menus"][0]["items"][0]["accelerator"] = "Ctrl+Ctrl+O"
        cases.append(data)
        data = valid_definition()
        radio = data["menus"][1]["items"][1]["items"][0]
        del radio["radio_group"]
        cases.append(data)
        data = valid_definition()
        data["menus"][0]["items"][0]["radio_group"] = "wrong"
        cases.append(data)
        for index, data in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(MenuDefinitionError):
                self.loader.from_dict(data)

    def test_rejects_invalid_separator_positions_and_adjacency(self):
        for items in (
            [{"separator": True}, {"command": "app.exit"}],
            [{"command": "file.open"}, {"separator": True}],
            [
                {"command": "file.open"}, {"separator": True},
                {"separator": True}, {"command": "app.exit"},
            ],
        ):
            data = valid_definition()
            data["menus"][0]["items"] = items
            with self.subTest(items=items), self.assertRaisesRegex(
                MenuDefinitionError, "separator"
            ):
                self.loader.from_dict(data)

    def test_rejects_duplicate_accelerators_and_split_radio_groups(self):
        data = valid_definition()
        data["menus"][1]["items"][0]["accelerator"] = "Ctrl+O"
        with self.assertRaisesRegex(MenuDefinitionError, "assigned to both"):
            self.loader.from_dict(data)
        data = valid_definition()
        theme_items = data["menus"][1]["items"][1]["items"]
        theme_items.insert(1, {"command": "view.zoom"})
        with self.assertRaisesRegex(MenuDefinitionError, "adjacent"):
            self.loader.from_dict(data)

    def test_allows_four_levels_and_rejects_a_fifth(self):
        deepest = {"label": "Level 4", "items": [{"command": "app.about"}]}
        level_three = {"label": "Level 3", "items": [deepest]}
        level_two = {"label": "Level 2", "items": [level_three]}
        data = valid_definition()
        data["menus"] = [{"label": "Level 1", "items": [level_two]}]
        self.loader.from_dict(data)
        too_deep = deepcopy(data)
        too_deep["menus"][0]["items"][0]["items"][0]["items"][0]["items"] = [
            {"label": "Level 5", "items": [{"command": "app.exit"}]}
        ]
        with self.assertRaises(MenuDefinitionError):
            self.loader.from_dict(too_deep)

    def test_load_accepts_utf8_bom_and_preserves_source_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "main.menu.json"
            path.write_text(json.dumps(valid_definition()), encoding="utf-8-sig")
            definition = self.loader.load(path)
            self.assertEqual(definition.path, path)
            self.assertFalse(definition.customized)

    def test_file_validation_error_identifies_source_path(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid.menu.json"
            data = valid_definition()
            data["schema_version"] = 2
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(MenuDefinitionError, "invalid.menu.json"):
                self.loader.load(path)

    def test_save_reopens_and_retains_previous_backup(self):
        first = self.loader.from_dict(valid_definition())
        changed_data = valid_definition()
        changed_data["menus"][0]["label"] = "&Application"
        changed = self.loader.from_dict(changed_data)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "main.menu.json"
            self.assertEqual(save_menu_definition(first, path), path)
            save_menu_definition(changed, path)
            self.assertEqual(self.loader.load(path).to_dict(), changed.to_dict())
            backup = path.with_suffix(".json.bak")
            self.assertEqual(self.loader.load(backup).to_dict(), first.to_dict())
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_application_resolution_prefers_customization(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            starter = root / "starter.json"
            custom = root / "custom.json"
            starter.write_text(json.dumps(valid_definition()), encoding="utf-8")
            changed = valid_definition()
            changed["menus"][0]["label"] = "&Customized"
            custom.write_text(json.dumps(changed), encoding="utf-8")
            loaded = self.loader.load_application(starter, custom)
            self.assertTrue(loaded.customized)
            self.assertEqual(loaded.path, custom)
            self.assertEqual(loaded.menus[0]["label"], "&Customized")

    def test_invalid_customization_fails_unless_fallback_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            starter = root / "starter.json"
            custom = root / "custom.json"
            starter.write_text(json.dumps(valid_definition()), encoding="utf-8")
            custom.write_text("{not json", encoding="utf-8")
            with self.assertRaises(MenuDefinitionError):
                self.loader.load_application(starter, custom)
            loaded = self.loader.load_application(
                starter, custom, fallback_to_starter=True
            )
            self.assertFalse(loaded.customized)
            self.assertEqual(loaded.path, starter)
            self.assertEqual(custom.read_text(encoding="utf-8"), "{not json")


if __name__ == "__main__":
    unittest.main()
