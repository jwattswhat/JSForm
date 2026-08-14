import tempfile
import unittest
from pathlib import Path

from JSForm.action_ui import OutputLocation, destructive_confirmation_message


class OutputLocationTests(unittest.TestCase):
    def test_default_folder_and_extension_are_application_supplied(self):
        with tempfile.TemporaryDirectory() as folder:
            output = OutputLocation(folder, extension="pdf")
            self.assertEqual(output.path("report"), Path(folder).resolve() / "report.pdf")
            self.assertEqual(output.path("report.PDF").name, "report.PDF")

    def test_filename_cannot_escape_default_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            output = OutputLocation(folder, extension=".json")
            self.assertEqual(output.path("../layout.json").parent, Path(folder).resolve())


class ConfirmationMessageTests(unittest.TestCase):
    def test_dependent_record_warning_is_explicit_and_pluralized(self):
        message = destructive_confirmation_message(
            "the route", consequence="This cannot be undone.",
            dependent_count=2, dependent_label="scheduled stop",
        )
        self.assertIn("Delete the route?", message)
        self.assertIn("2 scheduled stops", message)
        self.assertIn("This cannot be undone.", message)


if __name__ == "__main__":
    unittest.main()
