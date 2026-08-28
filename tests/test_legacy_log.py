"""Regression tests for the legacy-compatible JSForm diagnostic logger."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import JSForm.clsLog as legacy_log


class LegacyLogTests(unittest.TestCase):
    def test_frozen_application_uses_its_local_app_data_log_directory(self):
        with patch.object(legacy_log.sys, "frozen", True, create=True):
            path = legacy_log.default_log_path(
                environment={"LOCALAPPDATA": r"C:\Users\Example\AppData\Local"},
                executable=r"C:\Program Files\ChurchManager\ChurchManager.exe",
            )

        self.assertEqual(
            path,
            Path(r"C:\Users\Example\AppData\Local")
            / "ChurchManager" / "Logs" / "Log.txt",
        )

    def test_disabled_logger_does_not_create_a_file_during_import_style_setup(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "protected-installation" / "Log.txt"
            logger = legacy_log.clsLog(path)

            with patch.object(legacy_log, "cmLOG", False):
                logger.log(secret="must not be written")

            self.assertFalse(path.exists())

    def test_unwritable_log_does_not_raise_during_diagnostics(self):
        logger = legacy_log.clsLog(Path("protected") / "Log.txt")
        with patch.object(legacy_log, "cmLOG", True), patch.object(
            Path, "mkdir", side_effect=PermissionError("protected")
        ):
            logger.log(value="safe")

        self.assertIsNone(logger.lf)


if __name__ == "__main__":
    unittest.main()
