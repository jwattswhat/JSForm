"""Tests for JSForm's privacy-safe diagnostic error reporting."""

from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import threading
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from JSForm.error_redaction import REDACTED, redact_text, safe_context, safe_diagnostics
from JSForm.error_reporting import (
    ErrorReporter, ErrorReportingConfig, configure_error_reporting,
    error_boundary, install_error_hooks, report_exception, restore_error_hooks,
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

    def test_redacts_common_key_value_mapping_query_header_and_connector_forms(self):
        samples = (
            "password=fictional-one; mode=test",
            "{'api_key': 'fictional-two', 'region': 'local'}",
            '{"access_token": "fictional-three", "status": "failed"}',
            "https://example.invalid/path?token=fictional-four&mode=test",
            "connector(password='fictional-five', timeout=5)",
            "Proxy-Authorization: Basic fictional-six\nserver unavailable",
            "connector failed; Authorization: Bearer fictional-inline",
            "Cookie: session=fictional-seven\nrequest failed",
            "--secret=fictional-eight",
        )
        for value in samples:
            with self.subTest(value=value):
                result = redact_text(value)
                self.assertIn(REDACTED, result)
                self.assertNotIn("fictional-", result)

    def test_redaction_is_idempotent_preserves_benign_detail_and_rechecks_custom_output(self):
        value = "status=failed; password=fictional; retry=3"
        once = redact_text(value)
        self.assertEqual(redact_text(once), once)
        self.assertIn("status=failed", once)
        self.assertIn("retry=3", once)
        self.assertEqual(redact_text("ordinary", (lambda _text: "token=introduced",)), "token=[REDACTED]")
        self.assertEqual(redact_text("ordinary", (lambda _text: 1 / 0,)), "ordinary")

    def test_sensitive_key_avoids_short_fragment_false_positive(self):
        result = safe_diagnostics({"notpwdfield": "keep", "db_pwd": "remove"})
        self.assertEqual(result["notpwdfield"], "keep")
        self.assertEqual(result["db_pwd"], REDACTED)

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

    def test_support_diagnostics_are_redacted_and_objects_are_not_serialized(self):
        result = safe_diagnostics({
            "api_token": "fictional-token",
            "connection": "mysql://user:fictional-password@localhost/test",
            "unsafe": object(),
        })
        serialized = json.dumps(result)
        self.assertNotIn("fictional-token", serialized)
        self.assertNotIn("fictional-password", serialized)
        self.assertEqual(result["api_token"], REDACTED)
        self.assertEqual(result["unsafe"], "<object>")

    def test_nested_cyclic_and_oversized_diagnostics_are_bounded(self):
        cyclic = []
        cyclic.append(cyclic)
        result = safe_diagnostics({
            "nested": {"credentials": {"token": "fictional"}},
            "cycle": cyclic,
            "many": list(range(100)),
        })
        serialized = json.dumps(result)
        self.assertNotIn("fictional", serialized)
        self.assertIn("<cycle>", serialized)
        self.assertEqual(len(result["many"]), 25)


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

    def test_error_boundary_reraises_by_default_and_can_explicitly_suppress(self):
        with tempfile.TemporaryDirectory() as folder:
            reporter = configure_error_reporting(
                application_name="TestApplication", log_directory=folder,
            )
            with self.assertRaisesRegex(RuntimeError, "boundary failure"):
                with error_boundary(operation="report.preview", screen="Preview"):
                    raise RuntimeError("boundary failure")
            with error_boundary(operation="report.preview", suppress=True):
                raise RuntimeError("suppressed failure")
            records = reporter.log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(records), 2)

    def test_wx_hook_records_once_and_classifies_fatal_errors(self):
        class FakeApplication:
            def __init__(self):
                self.original_calls = 0

            def OnExceptionInMainLoop(self):
                self.original_calls += 1
                return False

            def GetTopWindow(self):
                return None

        with tempfile.TemporaryDirectory() as folder:
            reporter = configure_error_reporting(
                application_name="TestApplication", log_directory=folder,
                fatal_error_classifier=lambda error: "fatal" in str(error),
            )
            application = FakeApplication()
            install_error_hooks(application)
            try:
                raise RuntimeError("fatal initialization")
            except RuntimeError:
                should_continue = application.OnExceptionInMainLoop()
            self.assertFalse(should_continue)
            records = [json.loads(line) for line in reporter.log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["operation"], "wx.event.unhandled")
            self.assertEqual(records[0]["severity"], "fatal")

    def test_thread_hook_records_worker_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            reporter = configure_error_reporting(
                application_name="TestApplication", log_directory=folder,
            )
            install_error_hooks()
            original = threading.excepthook
            # Avoid invoking Python's noisy default hook while exercising our wrapper.
            import JSForm.error_reporting as module
            chained = module._ORIGINAL_THREAD_HOOK
            module._ORIGINAL_THREAD_HOOK = lambda _arguments: None
            worker = threading.Thread(
                name="fictional-worker",
                target=lambda: (_ for _ in ()).throw(RuntimeError("worker failed")),
            )
            worker.start()
            worker.join()
            module._ORIGINAL_THREAD_HOOK = chained
            self.assertIs(threading.excepthook, original)
            records = [json.loads(line) for line in reporter.log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["operation"], "thread.unhandled")
            self.assertEqual(records[0]["thread_name"], "fictional-worker")

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
                safe_diagnostics={
                    "database_scope": "test", "password": "do-not-export",
                    "endpoint": "mysql://user:fictional-secret@localhost/test",
                },
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
                raw = b"".join(archive.read(name) for name in names)
                self.assertNotIn(b"do-not-export", raw)
                self.assertNotIn(b"fictional-secret", raw)

    def test_error_dialog_redacts_direct_user_message_at_final_boundary(self):
        import JSForm.error_dialog as dialog

        class FakeWx:
            OK = 1
            ICON_ERROR = 2

            @staticmethod
            def MessageBox(message, title, style, parent):
                return message

        with patch.dict(sys.modules, {"wx": FakeWx}):
            rendered = dialog.show_error_dialog(
                None, "ERR-1234", application_name="TestApplication",
                user_message="Connector failed: password=fictional-display",
            )
        self.assertNotIn("fictional-display", rendered)
        self.assertIn(REDACTED, rendered)

    def test_support_package_reredacts_valid_and_malformed_historical_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reporter = ErrorReporter(ErrorReportingConfig(
                application_name="TestApplication", log_directory=root / "logs",
            ))
            reporter.log_directory.mkdir(parents=True)
            reporter.log_path.write_text(
                json.dumps({"message": "token=fictional-valid", "status": "failed"})
                + "\nmalformed password=fictional-malformed\n"
                + '{"password":\n"fictional-split"}\n',
                encoding="utf-8",
            )
            destination = create_support_package(reporter, root / "support.zip")
            with zipfile.ZipFile(destination) as archive:
                log_bytes = archive.read("logs/errors.jsonl")
                self.assertNotIn(b"fictional-valid", log_bytes)
                self.assertNotIn(b"fictional-malformed", log_bytes)
                self.assertNotIn(b"fictional-split", log_bytes)
                self.assertIn(REDACTED.encode(), log_bytes)
                manifest = json.loads(archive.read("manifest.json"))
                entry = next(item for item in manifest["files"] if item["name"] == "logs/errors.jsonl")
                self.assertEqual(entry["size"], len(log_bytes))
                self.assertEqual(entry["sha256"], hashlib.sha256(log_bytes).hexdigest())

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
