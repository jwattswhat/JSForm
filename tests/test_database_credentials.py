"""Tests for bounded and protected JSForm database credentials."""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from JSForm.clsDB import DatabaseCredentialError, clsDB
from JSForm.db_connections import DatabaseConnections, DatabaseSettings


class Connection:
    def close(self):
        pass


class Store:
    def __init__(self, events, value=None, error=None):
        self.events = events
        self.value = value
        self.error = error

    def read(self, target):
        self.events.append(("read", target))
        if self.error:
            raise self.error
        return self.value


class DatabaseCredentialTests(unittest.TestCase):
    def test_password_control_declares_native_masking_style(self):
        source = inspect.getsource(clsDB._getcredentials.__init__)
        self.assertIn("style=wx.TE_PASSWORD", source)

    def test_explicit_positional_password_connects_once_but_is_not_retained(self):
        calls = []

        def connect(**arguments):
            calls.append(dict(arguments))
            return Connection()

        with patch("JSForm.clsDB.mysql.connector.connect", side_effect=connect):
            database = clsDB("localhost", "ExampleDB", "example", "fictional-secret")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["password"], "fictional-secret")
        self.assertIsNone(database.DBCredintials["password"])
        self.assertIsNone(database.CONNECTIONS.application_settings.password)
        self.assertNotIn("fictional-secret", repr(database.CONNECTIONS.application_settings))

    def test_direct_database_connections_scrub_retained_settings_on_success(self):
        seen = []

        def connect(**arguments):
            seen.append(arguments["password"])
            return Connection()

        pair = DatabaseConnections(
            DatabaseSettings("localhost", "ExampleDB", "example", "fictional-secret"),
            connect,
        )
        self.assertEqual(seen, ["fictional-secret"])
        self.assertIsNone(pair.application_settings.password)

    def test_secret_bearing_connector_failure_is_wrapped_and_state_is_nonsecret(self):
        database = clsDB.__new__(clsDB)

        def connect(**arguments):
            raise RuntimeError("connector rejected {!r}".format(arguments))

        with patch("JSForm.clsDB.mysql.connector.connect", side_effect=connect):
            with self.assertRaisesRegex(RuntimeError, "could not be established") as caught:
                clsDB.__init__(
                    database, "localhost", "ExampleDB", "example", "fictional-secret",
                )
        self.assertNotIn("fictional-secret", str(caught.exception))
        self.assertIsNone(database.DBCredintials["password"])
        self.assertIsNone(database.CONNECTIONS)

    def test_target_lookup_is_immediately_before_connector_and_not_retained(self):
        events = []
        store = Store(events, ("stored-user", "fictional-target-secret"))

        def connect(**arguments):
            events.append(("connect", arguments["user"], arguments["password"]))
            return Connection()

        with patch("JSForm.clsDB.mysql.connector.connect", side_effect=connect):
            database = clsDB(
                "localhost", "ExampleDB", None, None,
                credential_target="Example/Database", credential_store=store,
            )
        self.assertEqual(events, [
            ("read", "Example/Database"),
            ("connect", "stored-user", "fictional-target-secret"),
        ])
        self.assertEqual(database.DBCredintials["user"], "stored-user")
        self.assertIsNone(database.DBCredintials["password"])

    def test_unsafe_target_configurations_fail_before_lookup_or_connect(self):
        cases = (
            {"credential_target": "", "credential_store": Store([])},
            {"credential_target": "Example/Database", "password": "fictional"},
            {"credential_target": None, "credential_store": Store([])},
        )
        for values in cases:
            events = []
            store = values.get("credential_store")
            if store is not None:
                store.events = events
            with self.subTest(values=values), patch("JSForm.clsDB.mysql.connector.connect") as connect:
                with self.assertRaises(DatabaseCredentialError):
                    clsDB(
                        "localhost", "ExampleDB", "example", values.get("password"),
                        credential_target=values.get("credential_target"),
                        credential_store=store,
                    )
            self.assertEqual(events, [])
            connect.assert_not_called()

    def test_missing_provider_value_and_username_mismatch_are_safe(self):
        cases = (
            (Store([], error=KeyError("raw target details")), None, "could not be read"),
            (Store([], ("different", "fictional-secret")), "expected", "does not match"),
        )
        for store, username, message in cases:
            with self.subTest(message=message), patch("JSForm.clsDB.mysql.connector.connect") as connect:
                with self.assertRaisesRegex(DatabaseCredentialError, message) as caught:
                    clsDB(
                        "localhost", "ExampleDB", username, None,
                        credential_target="Example/Database", credential_store=store,
                    )
            self.assertNotIn("fictional-secret", str(caught.exception))
            self.assertNotIn("raw target details", str(caught.exception))
            connect.assert_not_called()

    def test_cancel_destroys_dialog_and_does_not_connect(self):
        import JSForm

        class Dialog:
            def __init__(self):
                self.destroyed = False
                self.host = self.database = self.username = self.password = self

            def SetValue(self, _value):
                pass

            def ShowModal(self):
                return JSForm.CONST.FORM_CANCEL

            def GetValue(self):
                raise AssertionError("cancelled controls must not be read")

            def Destroy(self):
                self.destroyed = True

        dialog = Dialog()
        with patch.object(clsDB, "_getcredentials", return_value=dialog), patch(
            "JSForm.clsDB.mysql.connector.connect"
        ) as connect:
            database = clsDB(None, "ExampleDB", "example", "fictional")
        self.assertTrue(database.cancelled)
        self.assertTrue(dialog.destroyed)
        connect.assert_not_called()
        self.assertIsNone(database.DBConnection)
        self.assertIsNone(database.DBCredintials["password"])


if __name__ == "__main__":
    unittest.main()
