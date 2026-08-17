"""Tests for application-assigned primary keys on new JSForm records."""

import unittest

from clsDB import clsRecord


class Cursor:
    lastrowid = 99

    def __init__(self, connection): self.connection = connection
    def execute(self, sql, values): self.connection.executed = (sql, values)
    def close(self): pass


class Connection:
    def __init__(self): self.executed = None; self.commits = 0; self.rollbacks = 0
    def cursor(self): return Cursor(self)
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


class SQL:
    def insert_statement(self, record): return "INSERT", tuple(record.values())
    def update_statement(self, record): return "UPDATE", tuple(record.values())


class PreassignedPrimaryKeyTests(unittest.TestCase):
    def record(self, identifier):
        connection = Connection()
        records = clsRecord(connection, {"name": "sample"})
        records.sql = SQL()
        records.add({"ID": None, "Name": ""})
        records.setfieldvalue("ID", identifier)
        records.setfieldvalue("Name", "New record")
        return records, connection

    def test_new_record_with_assigned_id_is_inserted_and_preserved(self):
        records, connection = self.record(5001)
        records.update_current_record_in_DB()
        self.assertEqual(connection.executed[0], "INSERT")
        self.assertEqual(records.current()["ID"], 5001)
        self.assertEqual(connection.commits, 1)

    def test_new_record_without_assigned_id_uses_database_id(self):
        records, connection = self.record(None)
        records.update_current_record_in_DB()
        self.assertEqual(records.current()["ID"], 99)

    def test_loaded_record_is_updated(self):
        records, connection = self.record(7)
        records.original.save(records.current())
        records.setfieldvalue("Name", "Changed")
        records.update_current_record_in_DB()
        self.assertEqual(connection.executed[0], "UPDATE")


if __name__ == "__main__":
    unittest.main()
