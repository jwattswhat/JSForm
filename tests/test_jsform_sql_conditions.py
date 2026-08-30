import unittest
from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import patch
import importlib

from JSForm.clsSQL import ConditionCompilationError, clsSQL


class SQLConditionTests(unittest.TestCase):
    def sql(self, parentrecord=None, table=None):
        sql = clsSQL.__new__(clsSQL)
        sql.parentrecord = parentrecord
        sql.table = table or {"name": "tblExample", "fields": ["ID"]}
        sql.select_parameters = ()
        return sql

    def test_missing_parent_value_is_bound_as_native_none(self):
        sql = self.sql({"PropersID": None})

        self.assertEqual(sql.condition("ID = {PropersID}"), "ID = %s")
        self.assertEqual(sql.select_parameters, (None,))

    def test_present_parent_value_is_parameterized(self):
        sql = self.sql({"PropersID": 17})

        self.assertEqual(sql.condition("ID = {PropersID}"), "ID = %s")
        self.assertEqual(sql.select_parameters, (17,))

    def test_hostile_parent_text_never_enters_sql(self):
        hostile = "1' OR 1=1; --"
        sql = self.sql({"PersonID": hostile})

        statement, parameters = sql.select_statement({
            "name": "tblPerson", "fields": ["ID"],
            "condition": "PersonID = {PersonID}",
        })

        self.assertEqual(statement, "SELECT ID FROM tblPerson WHERE PersonID = %s ")
        self.assertNotIn(hostile, statement)
        self.assertEqual(parameters, (hostile,))

    def test_option_mapping_is_preserved_and_hostile_value_is_bound(self):
        hostile = "Active\"; DROP TABLE tblPerson; --"

        class Options:
            def get_Option_Value(self, optionfor, optionvalue):
                self.arguments = (optionfor, optionvalue)
                return hostile

        options = Options()
        module = importlib.import_module("JSForm.clsSQL")
        with patch.object(module.JSForm, "OPTION", options):
            compiled, parameters = self.sql().compile_condition(
                "Status = {OPTION:Membership:Current}"
            )

        self.assertEqual(options.arguments, ("Current", "Membership"))
        self.assertEqual(compiled, "Status = %s")
        self.assertNotIn(hostile, compiled)
        self.assertEqual(parameters, (hostile,))

    def test_multiple_repeated_placeholders_keep_occurrence_order(self):
        sql = self.sql({"First": 7, "Second": "two"})
        compiled, parameters = sql.compile_condition(
            "A={First} OR B={Second} OR C={First}"
        )
        self.assertEqual(compiled, "A=%s OR B=%s OR C=%s")
        self.assertEqual(parameters, (7, "two", 7))

    def test_native_values_are_not_stringified(self):
        values = {
            "Boolean": True,
            "Decimal": Decimal("12.50"),
            "Date": date(2026, 8, 28),
            "Time": time(9, 30),
            "DateTime": datetime(2026, 8, 28, 9, 30),
        }
        compiled, parameters = self.sql(values).compile_condition(
            "A={Boolean} AND B={Decimal} AND C={Date} AND D={Time} AND E={DateTime}"
        )
        self.assertEqual(compiled.count("%s"), 5)
        self.assertEqual(parameters, tuple(values.values()))

    def test_static_condition_has_no_parameters(self):
        compiled, parameters = self.sql().compile_condition("Active = 1")
        self.assertEqual(compiled, "Active = 1")
        self.assertEqual(parameters, ())

    def test_missing_parent_field_and_malformed_placeholders_fail_closed(self):
        sql = self.sql({"ID": 1})
        with self.assertRaisesRegex(ConditionCompilationError, "no field named Missing"):
            sql.compile_condition("ID={Missing}")
        for condition in ("ID={", "ID=}", "ID={{ID}}", "ID={UNKNOWN:value}"):
            with self.subTest(condition=condition):
                with self.assertRaises(ConditionCompilationError):
                    sql.compile_condition(condition)


if __name__ == "__main__":
    unittest.main()
