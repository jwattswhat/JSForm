"""Tests for paths used by JSForm's generic open-file action."""

import unittest
from pathlib import Path
import importlib
import os
from tempfile import TemporaryDirectory
from unittest.mock import patch

from JSForm.file_actions import (
    FileOpenDenied, approved_file_path, configure_file_opening,
    open_approved_file, resolve_picker_file,
)

file_actions = importlib.import_module("JSForm.file_actions")


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


class SafeFileOpeningTests(unittest.TestCase):
    def setUp(self):
        configure_file_opening(None, None)
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.document = self.root / "Council Minutes.PDF"
        self.document.write_text("fictional minutes", encoding="utf-8")

    def tearDown(self):
        configure_file_opening(None, None)
        self.temporary.cleanup()

    def configure(self, extensions=(".pdf",)):
        return configure_file_opening([self.root], extensions)

    def assert_denied(self, candidate, code=None):
        with self.assertRaises(FileOpenDenied) as raised, \
                patch.object(file_actions.os, "startfile") as launcher:
            open_approved_file(candidate)
        if code:
            self.assertEqual(raised.exception.code, code)
        launcher.assert_not_called()

    def test_approved_regular_passive_file_launches_once(self):
        policy = self.configure(("PDF", ".txt"))
        self.assertEqual(policy.passive_extensions, frozenset({".pdf", ".txt"}))
        with patch.object(file_actions.os, "startfile") as launcher:
            opened = open_approved_file(self.document)
        self.assertEqual(opened, self.document.resolve())
        launcher.assert_called_once_with(str(self.document.resolve()))

    def test_no_policy_denies_all_launches(self):
        self.assert_denied(self.document, "policy_missing")

    def test_outside_and_sibling_prefix_paths_are_denied(self):
        self.configure()
        outside = self.root.parent / "outside.pdf"
        sibling = self.root.parent / (self.root.name + "-Old") / "inside.pdf"
        outside.write_text("outside", encoding="utf-8")
        sibling.parent.mkdir()
        sibling.write_text("sibling", encoding="utf-8")
        try:
            self.assert_denied(outside, "outside_root")
            self.assert_denied(sibling, "outside_root")
        finally:
            outside.unlink()
            sibling.unlink()
            sibling.parent.rmdir()

    def test_unsafe_windows_representations_are_denied_before_launch(self):
        self.configure()
        candidates = {
            r"relative.pdf": "relative_path",
            r"C:relative.pdf": "relative_path",
            r"\\server\share\file.pdf": "remote_or_device",
            r"\\?\C:\Documents\file.pdf": "remote_or_device",
            r"\\.\C:\Documents\file.pdf": "remote_or_device",
            r"https://example.invalid/file.pdf": "url_or_scheme",
            r"shell:Downloads": "url_or_scheme",
            r"C:\Documents\file.pdf:payload": "alternate_stream",
            r"C:\Documents\NUL.pdf": "reserved_device",
            r"C:\Documents\NUL .pdf": "reserved_device",
            r"C:\Documents\file.pdf.": "ambiguous_path",
            r"C:\Documents\folder \file.pdf": "ambiguous_path",
            "C:\\Documents\\bad\x00.pdf": "invalid_path",
        }
        for candidate, code in candidates.items():
            with self.subTest(candidate=candidate):
                self.assert_denied(candidate, code)

    def test_missing_file_and_directory_are_denied(self):
        self.configure()
        self.assert_denied(self.root / "missing.pdf", "missing")
        self.assert_denied(self.root, "not_regular_file")

    def test_active_types_and_double_extensions_are_denied(self):
        self.configure((".pdf", ".txt"))
        active = self.root / "report.pdf.exe"
        active.write_text("not executable", encoding="utf-8")
        self.assert_denied(active, "disallowed_type")
        with self.assertRaisesRegex(ValueError, "Active file types"):
            configure_file_opening([self.root], [".pdf", ".lnk"])

    def test_shell_active_redirecting_installer_and_macro_types_cannot_be_approved(self):
        active_types = {
            ".website", ".appinstaller", ".msix", ".msixbundle", ".xlsb",
            ".xltm", ".ppsm", ".appx", ".appxbundle", ".xbap",
        }
        for extension in active_types:
            with self.subTest(extension=extension):
                with self.assertRaisesRegex(ValueError, "Active file types"):
                    configure_file_opening([self.root], [extension])

    def test_policy_rejects_wildcards_relative_and_remote_roots(self):
        with self.assertRaises(ValueError):
            configure_file_opening([self.root], ["*.*"])
        with self.assertRaises(ValueError):
            configure_file_opening(["relative"], [".pdf"])
        with self.assertRaises(ValueError):
            configure_file_opening([r"\\server\share"], [".pdf"])
        with self.assertRaises(ValueError):
            configure_file_opening([self.root / "missing"], [".pdf"])

    def test_reparse_path_is_denied_when_windows_allows_symlink_creation(self):
        self.configure()
        outside = self.root.parent / (self.root.name + "-target")
        outside.mkdir()
        target = outside / "outside.pdf"
        target.write_text("outside", encoding="utf-8")
        link = self.root / "linked"
        try:
            try:
                os.symlink(outside, link, target_is_directory=True)
            except OSError:
                self.skipTest("Windows symlink creation is unavailable")
            self.assert_denied(link / "outside.pdf", "reparse_path")
        finally:
            if link.is_symlink():
                link.unlink()
            target.unlink()
            outside.rmdir()

    def test_injected_reparse_detection_denies_without_launch(self):
        self.configure()
        with patch.object(file_actions, "_has_reparse_component", return_value=True):
            self.assert_denied(self.document, "reparse_path")

    def test_launcher_failure_propagates_without_second_launch(self):
        self.configure()
        with patch.object(file_actions.os, "startfile", side_effect=OSError("no association")) as launcher:
            with self.assertRaisesRegex(OSError, "no association"):
                open_approved_file(self.document)
        self.assertEqual(launcher.call_count, 1)


if __name__ == "__main__":
    unittest.main()
