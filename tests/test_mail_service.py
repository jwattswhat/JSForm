"""Tests for JSForm's provider-neutral mail service; no real mail is sent."""

import tempfile
import unittest
from pathlib import Path

from JSForm.mail_service import (
    MailConfigurationError, MailMessage, MailService, MailSettings,
    SMTPTransport, unique_recipients, valid_email,
)


class FakeTransport:
    def __init__(self, failing=()):
        self.failing = set(failing)
        self.calls = []

    def deliver(self, recipient, message):
        self.calls.append((recipient, message))
        if recipient in self.failing:
            raise RuntimeError("fictional provider failure")


class MailServiceTests(unittest.TestCase):
    def settings(self, **changes):
        values = {
            "host": "smtp.example.org", "port": 587,
            "username": "sender@example.org", "password": "fictional-secret",
            "sender_address": "sender@example.org", "sender_name": "Example Church",
            "security": "starttls",
        }
        values.update(changes)
        return MailSettings(**values)

    def test_addresses_are_validated_and_deduplicated_case_insensitively(self):
        self.assertTrue(valid_email("person@example.org"))
        self.assertFalse(valid_email("not an address"))
        self.assertEqual(
            unique_recipients(["Person@Example.org", " person@example.org ", "two@example.org"]),
            ("Person@Example.org", "two@example.org"),
        )

    def test_each_recipient_is_delivered_separately_with_structured_results(self):
        transport = FakeTransport(failing={"bad@example.org"})
        results = MailService(transport).send(
            ["one@example.org", "bad@example.org", "invalid"],
            MailMessage("Subject", "Body"),
        )
        self.assertEqual([call[0] for call in transport.calls], ["one@example.org", "bad@example.org"])
        self.assertEqual([result.succeeded for result in results], [True, False, False])

    def test_configuration_validation_never_echoes_password(self):
        with self.assertRaises(MailConfigurationError) as caught:
            self.settings(host="").validate()
        self.assertNotIn("fictional-secret", str(caught.exception))

    def test_smtp_message_is_new_conversation_and_has_attachment(self):
        with tempfile.TemporaryDirectory() as folder:
            attachment = Path(folder) / "planner.pdf"
            attachment.write_bytes(b"%PDF-fictional")
            transport = SMTPTransport(self.settings())
            first = transport._message(
                "person@example.org", MailMessage("Unique service subject", "Body", (attachment,)),
            )
            second = transport._message(
                "person@example.org", MailMessage("Unique service subject", "Body", (attachment,)),
            )
        self.assertNotEqual(first["Message-ID"], second["Message-ID"])
        self.assertIsNone(first["In-Reply-To"])
        self.assertIsNone(first["References"])
        self.assertEqual(first["To"], "person@example.org")
        self.assertTrue(first.is_multipart())


if __name__ == "__main__":
    unittest.main()
