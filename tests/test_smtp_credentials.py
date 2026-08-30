"""Tests for explicit SMTP credential migration; all stores are fictional."""

import unittest

from JSForm.smtp_credentials import (
    SMTPCredentialMigrationError, migrate_legacy_smtp_credential,
)


class FakeStore:
    def __init__(self, value=None, fail_delete=False):
        self.value = value
        self.fail_delete = fail_delete
        self.calls = []

    def read(self, target):
        self.calls.append(("read", target))
        if self.value is None:
            raise KeyError(target)
        return self.value

    def write(self, target, username, secret):
        self.calls.append(("write", target, username, secret))
        self.value = (username, secret)

    def delete(self, target):
        self.calls.append(("delete", target))
        if self.fail_delete:
            raise OSError("fictional cleanup failure")
        self.value = None


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = 0
        self.closed = False

    def execute(self, sql, values=()):
        self.connection.calls.append((sql, values))
        if sql.startswith("INSERT") and self.connection.fail_insert:
            raise RuntimeError("fictional SQL failure")
        if sql.startswith("DELETE"):
            self.rowcount = self.connection.delete_count

    def fetchall(self):
        return list(self.connection.rows)

    def close(self):
        self.closed = True
        if self.connection.fail_close:
            raise OSError("Example/Mail fictional-secret")


class Connection:
    def __init__(self, rows, *, delete_count=1, fail_insert=False, fail_close=False):
        self.rows = rows
        self.delete_count = delete_count
        self.fail_insert = fail_insert
        self.fail_close = fail_close
        self.calls = []
        self.commits = self.rollbacks = 0
        self.cursor_value = Cursor(self)

    def cursor(self): return self.cursor_value
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


LEGACY = [
    ("UserName", "sender@example.org"),
    ("Password", "fictional-secret"),
]


class SMTPCredentialMigrationTests(unittest.TestCase):
    def test_migrates_verifies_then_deletes_without_committing(self):
        connection = Connection(LEGACY)
        store = FakeStore()

        result = migrate_legacy_smtp_credential(connection, store, "Example/Mail")

        self.assertTrue(result.migrated)
        self.assertEqual((connection.commits, connection.rollbacks), (0, 0))
        self.assertTrue(connection.cursor_value.closed)
        sql = "\n".join(statement for statement, _values in connection.calls)
        self.assertIn("FOR UPDATE", sql)
        self.assertIn("INSERT INTO tblConfig", sql)
        self.assertIn("DELETE FROM tblConfig", sql)
        self.assertNotIn("fictional-secret", sql)
        delete = next(call for call in connection.calls if call[0].startswith("DELETE"))
        self.assertEqual(delete[1], ("SMTP", "Password"))
        self.assertLess(store.calls.index(("read", "Example/Mail"), 2),
                        next(i for i, call in enumerate(connection.calls)
                             if call[0].startswith("DELETE")) + 10)

    def test_matching_existing_credential_is_not_overwritten(self):
        connection = Connection(LEGACY)
        store = FakeStore(("sender@example.org", "fictional-secret"))
        migrate_legacy_smtp_credential(connection, store, "Example/Mail")
        self.assertFalse(any(call[0] == "write" for call in store.calls))

    def test_conflicting_existing_credential_fails_closed(self):
        connection = Connection(LEGACY)
        store = FakeStore(("other@example.org", "different"))
        with self.assertRaisesRegex(SMTPCredentialMigrationError, "different credentials"):
            migrate_legacy_smtp_credential(connection, store, "Example/Mail")
        self.assertFalse(any(sql.startswith("DELETE") for sql, _ in connection.calls))

    def test_duplicate_or_blank_legacy_rows_fail_closed(self):
        for rows in (
            LEGACY + [("Password", "second")],
            [("UserName", "sender@example.org"), ("Password", "")],
        ):
            with self.subTest(rows=rows):
                connection = Connection(rows)
                with self.assertRaises(SMTPCredentialMigrationError):
                    migrate_legacy_smtp_credential(connection, FakeStore(), "Example/Mail")
                self.assertFalse(any(sql.startswith("DELETE") for sql, _ in connection.calls))

    def test_successful_state_is_idempotent(self):
        connection = Connection([("CredentialTarget", "Example/Mail")])
        result = migrate_legacy_smtp_credential(connection, FakeStore(), "Example/Mail")
        self.assertFalse(result.migrated)
        self.assertEqual(len(connection.calls), 1)

    def test_sql_failure_compensates_and_preserves_original_error(self):
        connection = Connection(LEGACY, fail_insert=True)
        store = FakeStore(fail_delete=True)
        with self.assertRaisesRegex(SMTPCredentialMigrationError, "without changing") as caught:
            migrate_legacy_smtp_credential(connection, store, "Example/Mail")
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)
        self.assertIn(("delete", "Example/Mail"), store.calls)
        self.assertNotIn("fictional-secret", str(caught.exception))

    def test_changed_password_row_count_fails_and_compensates(self):
        connection = Connection(LEGACY, delete_count=0)
        store = FakeStore()
        with self.assertRaisesRegex(SMTPCredentialMigrationError, "changed"):
            migrate_legacy_smtp_credential(connection, store, "Example/Mail")
        self.assertIn(("delete", "Example/Mail"), store.calls)

    def test_cursor_close_failure_is_typed_safe_and_compensated(self):
        connection = Connection(LEGACY, fail_close=True)
        store = FakeStore()
        with self.assertRaisesRegex(SMTPCredentialMigrationError, "finish safely") as caught:
            migrate_legacy_smtp_credential(connection, store, "Example/Mail")
        self.assertIn(("delete", "Example/Mail"), store.calls)
        self.assertNotIn("fictional-secret", str(caught.exception))
        self.assertNotIn("Example/Mail", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
