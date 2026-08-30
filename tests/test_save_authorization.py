"""Tests for application-owned create/update authorization at persistence."""

import unittest

from clsDB import RecordOperationError, clsRecord
from security import AuthorizationDenied, FormSecurity


class Cursor:
    lastrowid = 41

    def __init__(self, connection): self.connection = connection
    def execute(self, sql, values): self.connection.executed.append((sql, values))
    def close(self): self.connection.closed += 1


class Connection:
    def __init__(self):
        self.cursor_calls = 0; self.executed = []; self.commits = 0
        self.rollbacks = 0; self.closed = 0
    def cursor(self): self.cursor_calls += 1; return Cursor(self)
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


class SQL:
    def insert_statement(self, record): return "INSERT", (record.get("ID"), record["Name"])
    def update_statement(self, record): return "UPDATE", (record["Name"], record["ID"])


class Policy:
    def __init__(self, allowed=(), error=None):
        self.allowed = set(allowed); self.error = error
    def has_permission(self, permission):
        if self.error is not None: raise self.error
        return permission in self.allowed


FORM = {"security": {"create": "records.create", "update": "records.update"}}


class SaveAuthorizationTests(unittest.TestCase):
    def records(self, original_id, authorizer):
        connection = Connection()
        records = clsRecord(connection, {"name": "records"}, authorizer)
        records.sql = SQL()
        records.add({"ID": original_id, "Name": "Initial"})
        return records, connection

    def assert_no_database_work(self, records, connection, original):
        self.assertEqual(connection.cursor_calls, 0)
        self.assertEqual(connection.executed, [])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 0)
        self.assertEqual(records.original.record, original)

    def test_blank_record_requires_create_and_inserts(self):
        security = FormSecurity("records", FORM, {}, Policy({"records.create"}))
        records, connection = self.records(None, security.require)
        records.update_current_record_in_DB()
        self.assertEqual(connection.executed[0][0], "INSERT")
        self.assertEqual(records.current()["ID"], 41)

    def test_update_only_cannot_insert(self):
        security = FormSecurity("records", FORM, {}, Policy({"records.update"}))
        records, connection = self.records(None, security.require)
        original = dict(records.original.record)
        with self.assertRaises(AuthorizationDenied): records.update_current_record_in_DB()
        self.assert_no_database_work(records, connection, original)

    def test_create_only_cannot_update(self):
        security = FormSecurity("records", FORM, {}, Policy({"records.create"}))
        records, connection = self.records(7, security.require)
        original = dict(records.original.record)
        records.setfieldvalue("Name", "Changed")
        with self.assertRaises(AuthorizationDenied): records.update_current_record_in_DB()
        self.assert_no_database_work(records, connection, original)

    def test_existing_record_requires_update_and_updates(self):
        security = FormSecurity("records", FORM, {}, Policy({"records.update"}))
        records, connection = self.records(7, security.require)
        records.setfieldvalue("Name", "Changed")
        records.update_current_record_in_DB()
        self.assertEqual(connection.executed[0][0], "UPDATE")

    def test_preassigned_id_remains_create(self):
        seen = []
        records, connection = self.records(None, seen.append)
        records.setfieldvalue("ID", 5001)
        records.update_current_record_in_DB()
        self.assertEqual(seen, ["create"])
        self.assertEqual(connection.executed[0][0], "INSERT")
        self.assertEqual(records.current()["ID"], 5001)

    def test_policy_exception_fails_closed_and_preserves_cause(self):
        failure = LookupError("policy unavailable")
        security = FormSecurity("records", FORM, {}, Policy(error=failure))
        records, connection = self.records(None, security.require)
        original = dict(records.original.record)
        with self.assertRaises(AuthorizationDenied) as raised:
            records.update_current_record_in_DB()
        self.assertIs(raised.exception.__cause__, failure)
        self.assert_no_database_work(records, connection, original)

    def test_permission_revocation_at_final_boundary_prevents_sql(self):
        policy = Policy({"records.create"})
        security = FormSecurity("records", FORM, {}, policy)
        records, connection = self.records(None, security.require)
        self.assertTrue(security.allows(records.pending_save_operation()))
        policy.allowed.clear()
        with self.assertRaises(AuthorizationDenied): records.update_current_record_in_DB()
        self.assertEqual(connection.cursor_calls, 0)

    def test_missing_original_snapshot_fails_closed(self):
        records, connection = self.records(None, lambda _operation: None)
        records.original.record = {}
        with self.assertRaises(RecordOperationError): records.update_current_record_in_DB()
        self.assertEqual(connection.cursor_calls, 0)

    def test_undeclared_permissions_preserve_compatibility(self):
        security = FormSecurity("legacy", {}, {}, Policy())
        records, connection = self.records(None, security.require)
        records.update_current_record_in_DB()
        self.assertEqual(connection.executed[0][0], "INSERT")


if __name__ == "__main__":
    unittest.main()
