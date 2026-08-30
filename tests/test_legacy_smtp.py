"""Compatibility tests for the historical SMTP facade."""

import unittest
from unittest.mock import patch

import JSForm
from JSForm.clsSMTP import clsSMTP


class Config:
    values = {
        "Server": "smtp.example.org", "Port": "587",
        "UserName": "sender@example.org", "SenderAddress": "sender@example.org",
        "CredentialTarget": "Example/Mail", "Security": "starttls",
    }

    def __init__(self): self.queries = []

    def get_Config_Value(self, family, key):
        self.queries.append((family, key))
        if key == "Password":
            raise AssertionError("legacy password queried")
        return self.values.get(key)


class Service:
    def __init__(self, _transport): self.calls = []
    def send(self, recipients, message): self.calls.append((recipients, message)); return ()


class FailingService(Service):
    def send(self, recipients, message):
        self.calls.append((recipients, message))
        return (JSForm.DeliveryResult(recipients[0], False, "Safe delivery failure."),)


class LegacySMTPTests(unittest.TestCase):
    def test_facade_never_queries_password_and_preserves_list_delivery(self):
        config = Config()
        with patch.object(JSForm, "CONFIG", config), \
             patch.object(JSForm, "SMTPTransport", return_value=object()), \
             patch.object(JSForm, "MailService", Service):
            facade = clsSMTP()
            result = facade.sendeMail(
                ["one@example.org", "two@example.org"], ["One", "Two"],
                "Subject", ["Body", "Second paragraph"], "planner.pdf",
            )
        self.assertIsNone(result)
        self.assertNotIn(("SMTP", "Password"), config.queries)
        recipients, message = facade._service.calls[0]
        self.assertEqual(recipients, ("one@example.org", "two@example.org"))
        self.assertEqual(message.attachments[0].name, "planner.pdf")
        self.assertEqual(message.body, "Body\nSecond paragraph")
        self.assertNotIn("PASSWORD", repr(facade.__dict__).upper())

    def test_framework_scheduler_constructs_the_exported_compatibility_class(self):
        from pathlib import Path
        source = (Path(__file__).parents[1] / "fnSchedule.py").read_text(encoding="utf-8")
        self.assertIn("SMTP = clsSMTP()", source)
        self.assertNotIn("SMTP = clsSMTP.clsSMTP()", source)

    def test_facade_requires_migrated_target(self):
        config = Config(); config.values = dict(Config.values, CredentialTarget="")
        with patch.object(JSForm, "CONFIG", config):
            with self.assertRaisesRegex(JSForm.MailConfigurationError, "migrated"):
                clsSMTP()

    def test_facade_surfaces_unsuccessful_delivery_result(self):
        with patch.object(JSForm, "CONFIG", Config()), \
             patch.object(JSForm, "SMTPTransport", return_value=object()), \
             patch.object(JSForm, "MailService", FailingService):
            facade = clsSMTP()
            with self.assertRaisesRegex(JSForm.MailDeliveryError, "Safe delivery failure"):
                facade.sendeMail("one@example.org", "One", "Subject", "Body", None)


if __name__ == "__main__":
    unittest.main()
