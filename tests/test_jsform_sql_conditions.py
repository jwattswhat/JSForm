import unittest

from JSForm.clsSQL import clsSQL


class SQLConditionTests(unittest.TestCase):
    def test_missing_parent_value_is_rendered_as_sql_null(self):
        sql = clsSQL.__new__(clsSQL)
        sql.parentrecord = {"PropersID": None}

        self.assertEqual(sql.condition("ID = {PropersID}"), "ID = NULL")

    def test_present_parent_value_is_preserved(self):
        sql = clsSQL.__new__(clsSQL)
        sql.parentrecord = {"PropersID": 17}

        self.assertEqual(sql.condition("ID = {PropersID}"), "ID = 17")


if __name__ == "__main__":
    unittest.main()
