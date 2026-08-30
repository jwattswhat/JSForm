"""Security and compatibility tests for CONFIG and OPTION storage SQL."""

import unittest

from clsConfig import clsConfig
from clsOption import clsOption


class Cursor:
    def __init__(self, connection, rows=None, failure=None, close_failure=None):
        self.connection = connection
        self.rows = rows
        self.failure = failure
        self.close_failure = close_failure
        self.closed = False

    def execute(self, sql, parameters):
        self.connection.executed.append((sql, parameters))
        if self.failure:
            raise self.failure

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True
        if self.close_failure:
            raise self.close_failure


class Connection:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.executed = []
        self.cursors = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        response = self.responses.pop(0) if self.responses else {}
        if isinstance(response, Exception):
            raise response
        cursor = Cursor(
            self, response.get("rows"), response.get("failure"),
            response.get("close_failure"),
        )
        self.cursors.append(cursor)
        return cursor

    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


class DB:
    def __init__(self, application, framework):
        self.DBConnection = application


HOSTILE = "x' OR 1=1; -- \\ % snowman-☃"


class MissingTableError(RuntimeError):
    errno = 1146


class ParameterizationTests(unittest.TestCase):
    def assert_bound(self, connection, expected):
        for sql, parameters in connection.executed:
            self.assertNotIn(HOSTILE, sql)
            self.assertIn("%s", sql)
            self.assertIsInstance(parameters, tuple)
        self.assertEqual(connection.executed, expected)

    def test_config_value_primary_binds_family_and_type(self):
        app = Connection(({"rows": [("value",)]},))
        config = clsConfig(DB(app, Connection()))
        self.assertEqual(config.get_Config_Value(HOSTILE, None), "value")
        self.assert_bound(app, [(
            "SELECT ConfigValue FROM tblConfig WHERE ConfigFamily = %s AND ConfigType = %s;",
            (HOSTILE, None),
        )])
        self.assertTrue(app.cursors[0].closed)

    def test_missing_config_value_does_not_query_framework_database(self):
        app = Connection(({"rows": []},))
        framework = Connection(({"rows": [("fallback",)]},))
        value = clsConfig(DB(app, framework)).get_Config_Value(HOSTILE, HOSTILE)
        self.assertIsNone(value)
        self.assert_bound(app, [(app.executed[0][0], (HOSTILE, HOSTILE))])
        self.assertEqual(framework.executed, [])

    def test_missing_config_family_does_not_query_framework_database(self):
        app = Connection(({"rows": []},))
        framework = Connection(({"rows": [("Type", "Value")]},))
        rows = clsConfig(DB(app, framework)).get_Config_Family(HOSTILE)
        self.assertEqual(rows, [])
        self.assertEqual(app.executed[0][1], (HOSTILE,))
        self.assertEqual(framework.executed, [])

    def test_config_update_binds_all_values_and_preserves_predicate(self):
        app = Connection(({},))
        clsConfig(DB(app, Connection())).set_Config_Value(HOSTILE, HOSTILE, HOSTILE)
        self.assert_bound(app, [(
            "UPDATE tblConfig SET ConfigFamily = %s, ConfigValue = %s WHERE ConfigType = %s;",
            (HOSTILE, HOSTILE, HOSTILE),
        )])
        self.assertEqual((app.commits, app.rollbacks), (0, 0))

    def test_option_primary_binds_group_and_type(self):
        app = Connection(({"rows": [("value",)]},))
        value = clsOption(DB(app, Connection())).get_Option_Value(HOSTILE, HOSTILE)
        self.assertEqual(value, "value")
        self.assert_bound(app, [(app.executed[0][0], (HOSTILE, HOSTILE))])

    def test_missing_option_does_not_query_framework_database(self):
        app = Connection(({"rows": []},))
        framework = Connection(({"rows": [("fallback",)]},))
        value = clsOption(DB(app, framework)).get_Option_Value(HOSTILE, HOSTILE)
        self.assertIsNone(value)
        self.assertEqual(app.executed[0][1], (HOSTILE, HOSTILE))
        self.assertEqual(framework.executed, [])

    def test_option_update_binds_value_group_and_type(self):
        app = Connection(({},))
        clsOption(DB(app, Connection())).set_Option_Value(HOSTILE, HOSTILE, HOSTILE)
        self.assert_bound(app, [(
            "UPDATE tblOptions SET OptionValue = %s WHERE OptionFor = %s AND OptionType = %s;",
            (HOSTILE, HOSTILE, HOSTILE),
        )])
        self.assertEqual((app.commits, app.rollbacks), (0, 0))

    def test_application_read_failure_closes_cursor_without_fallback(self):
        app = Connection(({"failure": RuntimeError("read failed")},))
        framework = Connection(({"rows": [("fallback",)]},))
        value = clsConfig(DB(app, framework)).get_Config_Value("Family", "Type")
        self.assertIsNone(value)
        self.assertTrue(app.cursors[0].closed)
        self.assertEqual(framework.executed, [])

    def test_framework_failure_is_irrelevant_when_option_is_missing(self):
        app = Connection(({"rows": []},))
        framework = Connection(({"failure": RuntimeError("fallback failed")},))
        self.assertIsNone(
            clsOption(DB(app, framework)).get_Option_Value("For", "Type")
        )
        self.assertEqual(framework.cursors, [])

    def test_missing_optional_framework_config_tables_mean_no_default(self):
        app = Connection(({"rows": []}, {"rows": []}))
        framework = Connection((
            {"failure": MissingTableError("jsConfig is absent")},
            {"failure": MissingTableError("jsConfig is absent")},
        ))
        config = clsConfig(DB(app, framework))
        self.assertIsNone(config.get_Config_Value("Family", "Type"))
        self.assertEqual(config.get_Config_Family("Font"), [])

    def test_missing_optional_framework_options_mean_no_default(self):
        app = Connection(({"rows": []},))
        framework = Connection((
            {"failure": MissingTableError("jsOptions is absent")},
        ))
        self.assertIsNone(
            clsOption(DB(app, framework)).get_Option_Value("For", "Type")
        )

    def test_update_failure_closes_cursor_and_does_not_commit(self):
        app = Connection(({"failure": RuntimeError("update failed")},))
        with self.assertRaisesRegex(RuntimeError, "update failed"):
            clsOption(DB(app, Connection())).set_Option_Value("For", "Type", "Value")
        self.assertTrue(app.cursors[0].closed)
        self.assertEqual((app.commits, app.rollbacks), (0, 0))

    def test_config_cursor_creation_failure_does_not_fall_back(self):
        app = Connection((RuntimeError("cursor failed"),))
        framework = Connection(({"rows": [("fallback",)]},))
        with self.assertRaisesRegex(RuntimeError, "cursor failed"):
            clsConfig(DB(app, framework)).get_Config_Value("Family", "Type")
        self.assertEqual(framework.executed, [])

    def test_close_failure_does_not_mask_original_operation_failure(self):
        app = Connection(({
            "failure": RuntimeError("execute failed"),
            "close_failure": RuntimeError("close failed"),
        },))
        with self.assertRaisesRegex(RuntimeError, "execute failed"):
            clsOption(DB(app, Connection())).set_Option_Value("For", "Type", "Value")

    def test_unconfigured_instances_preserve_none_results(self):
        self.assertIsNone(clsConfig().get_Config_Value("Family", "Type"))
        self.assertIsNone(clsOption().set_Option_Value("For", "Type", "Value"))


if __name__ == "__main__":
    unittest.main()
