"""Regression tests for file pickers without configured directories."""

import unittest
from unittest.mock import Mock

from clsField import _set_initial_directory_if_configured


class FilePickerDefaultTests(unittest.TestCase):
    """Keep optional application directory settings optional."""

    def test_none_directory_does_not_call_wx(self):
        picker = Mock()
        _set_initial_directory_if_configured(picker, None)
        picker.SetInitialDirectory.assert_not_called()

    def test_configured_directory_is_passed_as_text(self):
        picker = Mock()
        _set_initial_directory_if_configured(picker, "Documents")
        picker.SetInitialDirectory.assert_called_once_with("Documents")


if __name__ == "__main__":
    unittest.main()
