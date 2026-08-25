"""Tests for application-neutral wx window icon selection."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import wx

from JSForm.window_icons import (
    DEFAULT_ICON_PATH, application_icon_path, apply_window_icon,
    configure_application_icon,
)


class WindowIconTests(unittest.TestCase):
    def tearDown(self):
        configure_application_icon(None)

    def test_bundled_default_icon_exists(self):
        self.assertEqual(application_icon_path(), DEFAULT_ICON_PATH)
        self.assertTrue(DEFAULT_ICON_PATH.is_file())
        self.assertEqual(DEFAULT_ICON_PATH.suffix, ".ico")

    def test_application_can_override_and_reset_icon(self):
        with TemporaryDirectory() as folder:
            selected = Path(folder) / "application.ico"
            selected.write_bytes(b"icon")
            self.assertEqual(configure_application_icon(selected), selected.resolve())
            self.assertEqual(application_icon_path(), selected.resolve())
        self.assertEqual(configure_application_icon(None), DEFAULT_ICON_PATH)

    def test_rejects_missing_and_non_ico_overrides(self):
        with self.assertRaises(ValueError):
            configure_application_icon("application.png")
        with self.assertRaises(FileNotFoundError):
            configure_application_icon("missing.ico")

    def test_apply_loads_ico_and_sets_window_icon(self):
        window = Mock()
        icon = Mock()
        icon.IsOk.return_value = True
        with patch("JSForm.window_icons.wx.Icon", return_value=icon) as loader:
            selected = apply_window_icon(window)
        loader.assert_called_once_with(str(DEFAULT_ICON_PATH), wx.BITMAP_TYPE_ICO)
        window.SetIcon.assert_called_once_with(icon)
        self.assertEqual(selected, DEFAULT_ICON_PATH)


if __name__ == "__main__":
    unittest.main()
