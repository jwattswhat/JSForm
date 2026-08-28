"""Regression tests for applications without JSForm font configuration rows."""

import unittest
from unittest.mock import patch

from clsFont import clsFont


class TestFontDefaults(unittest.TestCase):
    """Verify that optional font configuration has usable defaults."""

    def test_missing_font_configuration_initializes_measurement_defaults(self):
        configured = type(
            "Config", (), {"get_Config_Family": lambda _self, _name: []}
        )()
        with patch("clsFont.JSForm.CONFIG", configured), patch("clsFont.wx.Font"):
            instance = object.__new__(clsFont)
            instance.fontdict = {}
            instance._currentfont = None
            instance.Get_Config_Font()

        self.assertEqual(instance.fontdict["pointSize"], 10)
        self.assertIn("family", instance.fontdict)
        self.assertIn("style", instance.fontdict)
        self.assertIn("weight", instance.fontdict)


if __name__ == "__main__":
    unittest.main()
