"""Opt-in, read-only checks for a disposable JSForm test database."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHURCHMANAGER_ROOT = ROOT.parent / "ChurchManager"
if str(CHURCHMANAGER_ROOT) not in sys.path:
    sys.path.insert(0, str(CHURCHMANAGER_ROOT))

from credential_store import read_credential


REQUIRED_TABLES = {
    "jsChoices", "jsConfig", "jsEnhancemnet", "jsOptions", "jsReports"
}


def database_tests_enabled() -> bool:
    return os.environ.get("JSFORM_RUN_DB_TESTS") == "1"


@unittest.skipUnless(database_tests_enabled(), "Set JSFORM_RUN_DB_TESTS=1 for read-only test-database checks")
class TestJSFormDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database = os.environ.get("JSFORM_TEST_DB_NAME", "")
        if not database:
            raise unittest.SkipTest("JSFORM_TEST_DB_NAME is not set")
        if database.casefold() == "jsform":
            raise RuntimeError("Safety stop: database tests refuse to run against JSForm")
        if "test" not in database.casefold():
            raise RuntimeError("Safety stop: test database name must contain the word 'test'")

        try:
            import mariadb
        except ImportError as error:
            raise unittest.SkipTest("The mariadb Python connector is unavailable") from error

        credential_target = os.environ.get(
            "JSFORM_TEST_CREDENTIAL_TARGET", "ChurchManager/Test"
        )
        stored_user, password = read_credential(credential_target)
        configured_user = os.environ.get("JSFORM_TEST_DB_USER", stored_user)
        if configured_user.casefold() != stored_user.casefold():
            raise RuntimeError(
                "The JSForm test username does not match the stored credential."
            )

        cls.connection = mariadb.connect(
            host=os.environ.get("JSFORM_TEST_DB_HOST", "localhost"),
            port=int(os.environ.get("JSFORM_TEST_DB_PORT", "3306")),
            database=database,
            user=stored_user,
            password=password,
            connect_timeout=5,
        )
        cursor = cls.connection.cursor()
        try:
            cursor.execute(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()"
            )
            cls.available_tables = {row[0].casefold() for row in cursor.fetchall()}
        finally:
            cursor.close()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "connection"):
            cls.connection.close()

    def query(self, sql, values=()):
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, values)
            return cursor.fetchall()
        finally:
            cursor.close()

    def test_required_framework_tables_exist(self):
        required = {table.casefold() for table in REQUIRED_TABLES}
        self.assertEqual(required - self.available_tables, set())

    def test_required_tables_are_readable(self):
        for table in sorted(REQUIRED_TABLES):
            with self.subTest(table=table):
                if table.casefold() not in self.available_tables:
                    continue
                self.query(f"SELECT 1 FROM `{table}` LIMIT 1")

    def test_configuration_keys_are_unique(self):
        if "jsconfig" not in self.available_tables:
            self.skipTest("jsConfig is missing")
        duplicates = self.query(
            "SELECT ConfigFamily, ConfigType, COUNT(*) FROM jsConfig "
            "GROUP BY ConfigFamily, ConfigType HAVING COUNT(*) > 1"
        )
        self.assertEqual(duplicates, [])

    def test_option_keys_are_unique(self):
        if "jsoptions" not in self.available_tables:
            self.skipTest("jsOptions is missing")
        duplicates = self.query(
            "SELECT OptionFor, OptionType, COUNT(*) FROM jsOptions "
            "GROUP BY OptionFor, OptionType HAVING COUNT(*) > 1"
        )
        self.assertEqual(duplicates, [])

    def test_report_codes_are_unique(self):
        if "jsreports" not in self.available_tables:
            self.skipTest("jsReports is missing")
        duplicates = self.query(
            "SELECT Report, COUNT(*) FROM jsReports WHERE Report IS NOT NULL AND Report <> '' "
            "GROUP BY Report HAVING COUNT(*) > 1"
        )
        self.assertEqual(duplicates, [])
