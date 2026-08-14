"""Tests for JSForm's privacy-safe diagnostic error reporting."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from JSForm.error_redaction import REDACTED, redact_text, safe_context
from JSForm.error_reporting import (
    ErrorReporter, ErrorReportingConfig, configure_error_reporting,
    install_error_hooks, report_exception, restore_error_hooks,
)
from JSForm.support_package import create_support_package


class ErrorRedactionTests(unittest.TestCase):
    def test_redacts_credentials_from_text(self):
        value = "mysql://church:secret@localhost/db --password hunter2\nAuthorization: Bearer abc"
        result = redact_text(value)
        self.assertNotIn("secret", result)
        self.assertNotIn("hunter2", result)
        self.assertNotIn("Bearer abc", result)
        self.assertIn(REDACTED, result)

    def test_context_is_allowlisted_bounded_and_safe(self):
        result = safe_context(
            {
                "screen": "frmChurch",
                "password": "do-not-log",
                "not_approved": "private",
                "record_id": 4,
                "object": object(),
            },
            {"screen", "password", "record_id", "object"},
        )
        self.assertEqual(result["screen"], "frmChurch")
        self.assertEqual(result["password"], REDACTED)
        self.assertEqual(result["record_id"], 4)
        self.assertEqual(result["object"], "<object>")
        self.assertNotIn("not_approved", result)


class ErrorReporterTests(unittest.TestCase):
    def tearDown(self):
        restore_error_hooks()

    def test_writes_one_structured_record_with_traceback_and_safe_context(self):
        with tempfile.TemporaryDirectory() as folder:
            reporter = ErrorReporter(ErrorReportingConfig(
                application_name="TestApplication",
                application_version="1.2.3",
                error_id_prefix="TA",
                log_directory=Path(folder),
            ))
            try:
                raise ValueError("fictional failure")
            except ValueError as error:
                display_id = reporter.report(error, context={
                    "operation": "form.save",
                    "screen": "frmExample",
                    "database_name": "JSFormTest",
                    "not_approved": "do not include",
                })

            records = [json.loads(line) for line in reporter.log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertRegex(display_id, r"^TA-[0-9A-F]{4}-[0-9A-F]{4}$")
            self.assertEqual(record["display_error_id"], display_id)
            self.assertEqual(record["operation"], "form.save")
            self.assertEqual(record["screen"], "frmExample")
            self.assertEqual(record["database_name"], "JSFormTest")
            self.assertIn("ValueError: fictional failure", record["traceback"])
            self.assertNotIn("not_approved", record["context"])

    def test_custom_redactor_applies_to_message_traceback_and_context(self):
        with tempfile.TemporaryDirectory() as folder:
            reporter = ErrorReporter(ErrorReportingConfig(
                application_name="TestApplication",
                log_directory=Path(folder),
                redactors=(lambda text: text.replace("Private Person", REDACTED),),
            ))
            try:
                raise RuntimeError("Private Person")
            except RuntimeError as error:
                reporter.report(error, context={"screen": "Private Person"})
            raw = reporter.log_path.read_text(encoding="utf-8")
            self.assertNotIn("Private Person", raw)
            self.assertIn(REDACTED, raw)

    def test_rotates_bounded_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            reporter = ErrorReporter(ErrorReportingConfig(
                application_name="TestApplication",
                log_directory=Path(folder),
                max_bytes=1,
                retained_files=2,
            ))
            reporter.report(RuntimeError("first"))
            reporter.report(RuntimeError("second"))
            reporter.report(RuntimeError("third"))
            self.assertTrue(reporter.log_path.exists())
            self.assertTrue(reporter.log_path.with_suffix(".jsonl.1").exists())
            self.assertTrue(reporter.log_path.with_suffix(".jsonl.2").exists())
            self.assertFalse(reporter.log_path.with_suffix(".jsonl.3").exists())

    def test_public_api_and_hooks_are_idempotent(self):
        original = sys.excepthook
        with tempfile.TemporaryDirectory() as folder:
            configure_error_reporting(application_name="TestApplication", log_directory=folder)
            install_error_hooks()
            installed = sys.excepthook
            install_error_hooks()
            self.assertIs(sys.excepthook, installed)
            self.assertNotEqual(sys.excepthook, original)
            self.assertNotEqual(report_exception(RuntimeError("caught")), "ERR-NOT-CONFIGURED")
        restore_error_hooks()
        self.assertIs(sys.excepthook, original)

    def test_expired_rotated_logs_are_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            reporter = ErrorReporter(ErrorReportingConfig(
                application_name="TestApplication",
                log_directory=Path(folder),
                retention_days=30,
            ))
            reporter.log_directory.mkdir(exist_ok=True)
            expired = reporter.log_path.with_suffix(".jsonl.1")
            expired.write_text("old", encoding="utf-8")
            old = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
            import os
            os.utime(expired, (old, old))
            reporter.cleanup_expired_logs(datetime(2026, 8, 14, tzinfo=timezone.utc))
            self.assertFalse(expired.exists())

    def test_support_package_is_verified_and_contains_only_approved_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reporter = ErrorReporter(ErrorReportingConfig(
                application_name="TestApplication",
                application_version="1.2.3",
                log_directory=root / "logs",
            ))
            reporter.report(RuntimeError("fictional"))
            destination = root / "support.zip"
            result = create_support_package(
                reporter, destination,
                safe_diagnostics={"database_scope": "test"},
            )
            self.assertEqual(result, destination)
            with zipfile.ZipFile(destination) as archive:
                names = set(archive.namelist())
                self.assertEqual(names, {
                    "application-diagnostics.json", "logs/errors.jsonl",
                    "manifest.json", "system-info.json",
                })
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(len(manifest["files"]), 3)
                self.assertIsNone(archive.testzip())

    def test_support_package_does_not_overwrite_existing_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reporter = ErrorReporter(ErrorReportingConfig(
                application_name="TestApplication", log_directory=root / "logs",
            ))
            destination = root / "support.zip"
            destination.write_bytes(b"keep")
            with self.assertRaises(FileExistsError):
                create_support_package(reporter, destination)
            self.assertEqual(destination.read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
