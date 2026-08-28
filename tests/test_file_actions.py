"""Tests for paths used by JSForm's generic open-file action."""

import unittest
from pathlib import Path

from JSForm.file_actions import resolve_picker_file


class Picker:
    def __init__(self, value, remembered=""):
        self.value = value
        self.path = remembered

    def GetPath(self):
        return self.value


class ResolvePickerFileTests(unittest.TestCase):
    def test_preserves_absolute_picker_path_for_any_extension(self):
        expected = Path(r"C:\Church Files\Council Minutes.docx")
        self.assertEqual(resolve_picker_file(Picker(str(expected))), expected)

    def test_uses_directory_remembered_with_stored_filename(self):
        self.assertEqual(
            resolve_picker_file(
                Picker("Council Minutes.docx", r"D:\Congregation\Documents"),
                r"C:\Default",
            ),
            Path(r"D:\Congregation\Documents\Council Minutes.docx"),
        )

    def test_uses_configured_directory_as_fallback(self):
        self.assertEqual(
            resolve_picker_file(Picker("Policy.pdf"), r"C:\ChurchManager\Documents"),
            Path(r"C:\ChurchManager\Documents\Policy.pdf"),
        )

    def test_empty_picker_has_no_file(self):
        self.assertIsNone(resolve_picker_file(Picker(""), r"C:\Documents"))


if __name__ == "__main__":
    unittest.main()
