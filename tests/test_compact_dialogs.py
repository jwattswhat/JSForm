import unittest

from JSForm.compact_dialogs import CompactEditorModel, EditorField


class CompactEditorModelTests(unittest.TestCase):
    def test_required_values_are_trimmed_and_validated(self):
        model = CompactEditorModel((EditorField("Stop name:", "name", required=True),))
        self.assertEqual(model.validate({"name": "  Library  "}), {"name": "Library"})
        with self.assertRaisesRegex(ValueError, "Enter Stop name"):
            model.validate({"name": "  "})

    def test_application_validator_can_normalize_values(self):
        model = CompactEditorModel(
            (EditorField("Code:", "code"),),
            validator=lambda values: {**values, "code": values["code"].upper()},
        )
        self.assertEqual(model.validate({"code": " ab "}), {"code": "AB"})

    def test_existing_application_values_are_preserved(self):
        model = CompactEditorModel(
            (EditorField("Name:", "name"),), {"id": 7, "name": "Original"},
        )
        self.assertEqual(model.values["id"], 7)


if __name__ == "__main__":
    unittest.main()
