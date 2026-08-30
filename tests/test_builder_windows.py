"""Tests for shared visual Builder window startup behavior."""

from __future__ import annotations

import unittest

from JSForm.builder_windows import show_builder_window


class FakeBuilderWindow:
    def __init__(self):
        self.calls = []

    def Maximize(self, maximize=True):
        self.calls.append(("Maximize", maximize))

    def Show(self, shown=True):
        self.calls.append(("Show", shown))


class BuilderWindowTests(unittest.TestCase):
    def test_builder_is_maximized_before_it_is_shown(self):
        window = FakeBuilderWindow()

        result = show_builder_window(window)

        self.assertIs(result, window)
        self.assertEqual(window.calls, [("Maximize", True), ("Show", True)])

    def test_all_designer_openers_use_shared_builder_startup(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        for filename in ("screen_designer.py", "report_designer.py", "menu_designer.py"):
            source = (root / filename).read_text(encoding="utf-8")
            self.assertIn("from JSForm.builder_windows import show_builder_window", source)
            self.assertIn("show_builder_window(frame)", source)


if __name__ == "__main__":
    unittest.main()
