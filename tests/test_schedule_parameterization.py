"""Regression tests for parameterized legacy schedule SELECT helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import JSForm.fnSchedule as schedule


class Cursor:
    def __init__(self, one=None, many=()):
        self.one = one
        self.many = many
        self.executions = []
        self.closed = False

    def execute(self, sql, parameters):
        self.executions.append((sql, parameters))

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many

    def close(self):
        self.closed = True


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


class ScheduleSelectTests(unittest.TestCase):
    def test_read_one_passes_compiled_parameters_and_closes_cursor(self):
        cursor = Cursor(one=(17,))
        observed = {}

        class Statement:
            def select_statement(self):
                return "SELECT ID FROM tblService WHERE ID=%s", (17,)

        def build(connection, table, parentrecord):
            observed.update(table=table, parentrecord=parentrecord)
            return Statement()

        table = {"name": "tblService", "fields": ["ID"], "condition": "ID={ID}"}
        with patch.object(schedule, "clsSQL", build):
            row = schedule.readonerecord(Connection(cursor), table, {"ID": 17})

        self.assertEqual(row, (17,))
        self.assertEqual(cursor.executions, [
            ("SELECT ID FROM tblService WHERE ID=%s", (17,)),
        ])
        self.assertEqual(observed["parentrecord"], {"ID": 17})
        self.assertTrue(cursor.closed)

    def test_service_role_insert_binds_hostile_role_as_one_value(self):
        cursor = Cursor()
        role = "Reader'); DROP TABLE tblServiceRole; --"

        schedule._insert_service_role(Connection(cursor), 41, 73, role)

        self.assertEqual(cursor.executions, [
            (
                "INSERT INTO tblServiceRole (ServiceID,ParticipantID,Role) "
                "VALUES (%s,%s,%s);",
                (41, 73, role),
            ),
        ])
        self.assertNotIn(role, cursor.executions[0][0])
        self.assertTrue(cursor.closed)

    def test_service_role_insert_closes_cursor_when_execution_fails(self):
        class FailingCursor(Cursor):
            def execute(self, sql, parameters):
                super().execute(sql, parameters)
                raise RuntimeError("fictional connector failure")

        cursor = FailingCursor()
        with self.assertRaisesRegex(RuntimeError, "fictional connector failure"):
            schedule._insert_service_role(Connection(cursor), 41, 73, "Reader")

        self.assertTrue(cursor.closed)

    def test_read_all_closes_cursor_when_execution_fails(self):
        class FailingCursor(Cursor):
            def execute(self, sql, parameters):
                super().execute(sql, parameters)
                raise RuntimeError("fictional connector failure")

        cursor = FailingCursor()

        class Statement:
            def select_statement(self):
                return "SELECT ID FROM tblService WHERE ID=%s", (9,)

        with patch.object(schedule, "clsSQL", lambda *_args: Statement()):
            with self.assertRaisesRegex(RuntimeError, "fictional connector failure"):
                schedule.readallrecords(Connection(cursor), {}, {"ID": 9})

        self.assertTrue(cursor.closed)


if __name__ == "__main__":
    unittest.main()
