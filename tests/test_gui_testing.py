"""Tests for the reusable wxPython GUI testing harness."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import wx
from PIL import Image

from JSForm.gui_testing import (
    GUITestError, compare_png, drain_events, geometry_issues, named_controls,
)


class GUITestingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)

    def test_control_discovery_requires_unique_stable_names(self):
        frame = wx.Frame(None, name="fixture_window")
        panel = wx.Panel(frame)
        wx.TextCtrl(panel, name="fixture_value")
        try:
            self.assertIn("fixture_value", named_controls(frame))
            wx.Button(panel, name="fixture_value")
            with self.assertRaisesRegex(GUITestError, "Duplicate"):
                named_controls(frame)
        finally:
            frame.Destroy()
            drain_events()

    def test_geometry_reports_unusable_named_controls(self):
        frame = wx.Frame(None, size=(300, 200), name="fixture_window")
        panel = wx.Panel(frame)
        wx.TextCtrl(panel, pos=(10, 10), size=(0, 0), name="empty_control")
        frame.Show()
        try:
            drain_events()
            self.assertTrue(any("empty_control" in item for item in geometry_issues(frame)))
        finally:
            frame.Destroy()
            drain_events()

    def test_visual_comparison_never_overwrites_the_baseline(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); expected = root / "expected.png"; actual = root / "actual.png"
            difference = root / "difference.png"
            Image.new("RGBA", (4, 4), "white").save(expected)
            Image.new("RGBA", (4, 4), "black").save(actual)
            original = expected.read_bytes()
            result = compare_png(expected, actual, difference, tolerance=0)
            self.assertFalse(result.matched)
            self.assertTrue(difference.is_file())
            self.assertEqual(expected.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
