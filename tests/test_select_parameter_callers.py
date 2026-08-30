"""Caller-level tests for parameterized clsSQL SELECT execution."""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path
from unittest.mock import patch


HOSTILE = "1' OR 1=1; --"


class Cursor:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.executions = []
        self.closed = False

    def execute(self, sql, parameters):
        self.executions.append((sql, parameters))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def close(self):
        self.closed = True


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, *args, **kwargs):
        return self._cursor


class ParameterizedStatement:
    def __init__(self, *args):
        self.args = args

    def select_statement(self):
        return "SELECT ID FROM tblExample WHERE ParentID=%s", (HOSTILE,)

    def format_sql_records(self, rows):
        return [{"ID": row[0]} for row in rows]


class SelectCallerTests(unittest.TestCase):
    @staticmethod
    def event(name="Open"):
        return type("Event", (), {
            "GetEventObject": lambda self: type(
                "Control", (), {"GetName": lambda self: name}
            )(),
            "GetEventType": lambda self: 0,
        })()

    def test_record_loading_passes_dynamic_parameters(self):
        module = importlib.import_module("JSForm.clsDB")
        cursor = Cursor([(7,)])
        record = object.__new__(module.clsRecord)
        record.DBConnection = Connection(cursor)
        record.TABLENAME = "tblExample"
        table = {"name": "tblExample", "fields": ["ID"]}

        with patch.object(module.JSForm, "clsSQL", ParameterizedStatement):
            rows = record.read_records(table, {"ParentID": HOSTILE})

        self.assertEqual(rows, [{"ID": 7}])
        self.assertEqual(cursor.executions[0][1], (HOSTILE,))
        self.assertNotIn(HOSTILE, cursor.executions[0][0])
        self.assertTrue(cursor.closed)

    def test_lookup_choices_pass_dynamic_parameters(self):
        module = importlib.import_module("JSForm.clsChoice")
        cursor = Cursor([(7, "Example")])
        choice = object.__new__(module.clsChoice)
        choice.dbconnection = Connection(cursor)
        choice.controldescription = {
            "lookupchoices": {"name": "tblExample", "fields": ["ID", "Name"]}
        }
        choice.id = []
        choice.display = []
        choice.fielddata = []
        choice.subfields = []

        with patch.object(module.JSForm, "clsSQL", ParameterizedStatement):
            values = choice._loadchoicesfromtable()

        self.assertEqual(values, ["Example"])
        self.assertEqual(cursor.executions[0][1], (HOSTILE,))
        self.assertNotIn(HOSTILE, cursor.executions[0][0])
        self.assertTrue(cursor.closed)

    def test_linked_file_lookup_passes_dynamic_parameters(self):
        module = importlib.import_module("JSForm.clsForm")
        cursor = Cursor([(r"C:\Documents\example.pdf",)])
        form = object.__new__(module.clsForm)
        form.DBConnection = Connection(cursor)
        form.CONTROLDESCRIPTION = {
            "Open": {"action": ["openfile", "File"]},
            "File": {
                "type": "ComboBox",
                "table": {"name": "tblExample", "fields": ["Path"]},
            },
        }
        form.RECORDS = type("Records", (), {"current": lambda self: {"ID": HOSTILE}})()
        event = self.event()
        built = []

        class TrackingStatement(ParameterizedStatement):
            def __init__(self, *args):
                super().__init__(*args)
                built.append(args)

        with patch.object(module.JSForm, "clsSQL", TrackingStatement), \
                patch.object(module.JSForm.LG, "log"), \
                patch.object(module, "open_approved_file") as open_file:
            form._openfileevent(event)

        self.assertEqual(built[0][2], {"ID": HOSTILE})
        self.assertEqual(cursor.executions[0][1], (HOSTILE,))
        self.assertNotIn(HOSTILE, cursor.executions[0][0])
        self.assertTrue(cursor.closed)
        open_file.assert_called_once_with(r"C:\Documents\example.pdf")

    def test_text_file_source_uses_final_opening_boundary(self):
        module = importlib.import_module("JSForm.clsForm")
        form = object.__new__(module.clsForm)
        form.CONTROLDESCRIPTION = {
            "Open": {"action": ["openfile", "File"]},
            "File": {"type": "TextCtrl"},
        }
        form.CONTROLID = {"File": type("Text", (), {
            "GetValue": lambda self: r"C:\Documents\example.pdf"
        })()}
        with patch.object(module.JSForm.LG, "log"), \
                patch.object(module, "open_approved_file") as open_file:
            self.assertTrue(form._openfileevent(self.event()))
        open_file.assert_called_once_with(r"C:\Documents\example.pdf")

    def test_file_picker_source_uses_final_opening_boundary(self):
        module = importlib.import_module("JSForm.clsForm")
        form = object.__new__(module.clsForm)
        form.CONTROLDESCRIPTION = {
            "Open": {"action": ["openfile", "File"]},
            "File": {"type": "FilePickerCtrl", "directory": ["Location", "Document"]},
        }
        form.CONTROLID = {"File": type("Picker", (), {
            "GetPath": lambda self: "example.pdf", "path": r"C:\Documents"
        })()}
        with patch.object(module.JSForm.LG, "log"), \
                patch.object(module.JSForm.CONFIG, "get_Config_Value", return_value=r"D:\Default"), \
                patch.object(module, "open_approved_file") as open_file:
            self.assertTrue(form._openfileevent(self.event()))
        open_file.assert_called_once_with(Path(r"C:\Documents\example.pdf"))

    def test_denied_file_shows_safe_dialog_and_returns_false(self):
        module = importlib.import_module("JSForm.clsForm")
        form = object.__new__(module.clsForm)
        form.FORM = object()
        form.CONTROLDESCRIPTION = {
            "Open": {"action": ["openfile", "File"]},
            "File": {"type": "TextCtrl"},
        }
        form.CONTROLID = {"File": type("Text", (), {"GetValue": lambda self: "unsafe"})()}
        denial = module.FileOpenDenied("outside_root", "This file cannot be opened.")
        with patch.object(module.JSForm.LG, "log"), \
                patch.object(module, "open_approved_file", side_effect=denial), \
                patch.object(module.wx, "MessageDialog") as dialog:
            self.assertFalse(form._openfileevent(self.event()))
        dialog.assert_called_once_with(
            form.FORM, "This file cannot be opened.", "Unable to open file", module.wx.OK
        )


if __name__ == "__main__":
    unittest.main()
