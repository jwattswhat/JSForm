"""Tests for JSForm's provider-neutral mail service; no real mail is sent."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from JSForm.mail_service import (
    MailConfigurationError, MailDeliveryError, MailMessage, MailService, MailSettings,
    SMTPTransport, unique_recipients, valid_email,
)
from JSForm.credential_store import WindowsCredentialStore


class FakeTransport:
    def __init__(self, failing=()):
        self.failing = set(failing)
        self.calls = []

    def deliver(self, recipient, message):
        self.calls.append((recipient, message))
        if recipient in self.failing:
            raise RuntimeError("fictional provider failure")


class FakeCredentialStore:
    def __init__(self, events, values):
        self.events = events
        self.values = list(values)

    def read(self, _target):
        self.events.append("credential-read")
        return self.values.pop(0)


class FakeSMTPConnection:
    def __init__(self, events, *, starttls_available=True, ehlo_codes=(250, 250),
                 starttls_error=None):
        self.events = events
        self.starttls_available = starttls_available
        self.ehlo_codes = list(ehlo_codes)
        self.starttls_error = starttls_error

    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def ehlo(self):
        self.events.append("ehlo")
        return (self.ehlo_codes.pop(0), b"fictional greeting")
    def has_extn(self, name):
        self.events.append(("has_extn", name))
        return self.starttls_available
    def starttls(self, context=None):
        self.events.append("starttls")
        if self.starttls_error:
            raise self.starttls_error
    def login(self, username, password): self.events.append(("login", username, password))
    def send_message(self, _message): self.events.append("send")


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

    def test_plain_loopback_flag_is_appended_and_defaults_false(self):
        settings = MailSettings(
            "smtp.example.org", 587, "sender@example.org", "fictional-secret",
            "sender@example.org", "Example", "starttls", None, None,
        )
        self.assertFalse(settings.allow_plain_loopback)

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

    def test_credential_target_rejects_blank_names(self):
        store = WindowsCredentialStore()
        with self.assertRaises(ValueError):
            store.read("  ")

    def test_target_credentials_are_resolved_after_tls_and_rotate_per_delivery(self):
        events = []
        store = FakeCredentialStore(events, [
            ("sender@example.org", "first-fictional"),
            ("sender@example.org", "second-fictional"),
        ])
        settings = self.settings(password=None, credential_target="Example/Mail")
        transport = SMTPTransport(settings, credential_store=store)
        self.assertEqual(events, [])
        transport._message("person@example.org", MailMessage("Subject", "Body"))
        self.assertEqual(events, [])

        def connect(*_args, **_kwargs):
            events.append("connect")
            return FakeSMTPConnection(events)

        with patch("smtplib.SMTP", side_effect=connect):
            transport.deliver("person@example.org", MailMessage("One", "Body"))
            transport.deliver("person@example.org", MailMessage("Two", "Body"))

        self.assertEqual(events[:7], [
            "connect", "ehlo", ("has_extn", "starttls"), "starttls", "ehlo",
            "credential-read", ("login", "sender@example.org", "first-fictional"),
        ])
        self.assertIn(("login", "sender@example.org", "second-fictional"), events)
        self.assertNotIn("first-fictional", repr(transport.__dict__))

    def test_target_and_plaintext_password_are_rejected(self):
        with self.assertRaisesRegex(MailConfigurationError, "either"):
            self.settings(credential_target="Example/Mail").validate()

    def test_credential_failures_are_safe_in_delivery_results(self):
        class FailingStore:
            def read(self, _target):
                raise OSError("Example/Mail fictional-secret")

        settings = self.settings(password=None, credential_target="Example/Mail")
        transport = SMTPTransport(settings, credential_store=FailingStore())
        with patch("smtplib.SMTP", return_value=FakeSMTPConnection([])):
            result = MailService(transport).send(
                ("person@example.org",), MailMessage("Subject", "Body"),
            )[0]
        self.assertFalse(result.succeeded)
        self.assertNotIn("fictional-secret", result.message)
        self.assertNotIn("Example/Mail", result.message)

    def test_target_username_must_match_protected_credential(self):
        settings = self.settings(password=None, credential_target="Example/Mail")
        transport = SMTPTransport(
            settings, credential_store=FakeCredentialStore([], [("other@example.org", "safe")]),
        )
        with patch("smtplib.SMTP", return_value=FakeSMTPConnection([])):
            with self.assertRaisesRegex(MailConfigurationError, "does not match"):
                transport.deliver("person@example.org", MailMessage("Subject", "Body"))

    def test_plain_authentication_and_remote_plain_fail_before_network_or_vault(self):
        cases = (
            self.settings(security="plain"),
            self.settings(security="plain", password=None, credential_target="Example/Mail"),
            self.settings(security="plain", username=None, password=None),
        )
        with patch("smtplib.SMTP") as smtp:
            for settings in cases:
                with self.subTest(settings=settings):
                    with self.assertRaises(MailConfigurationError):
                        SMTPTransport(settings)
        smtp.assert_not_called()

    def test_explicit_unauthenticated_plain_is_strictly_loopback(self):
        allowed = ("localhost", " LOCALHOST ", "127.0.0.1", "127.200.4.9", "::1", "[::1]")
        for host in allowed:
            with self.subTest(host=host):
                settings = self.settings(
                    host=host, security="plain", username=None, password=None,
                    allow_plain_loopback=True,
                )
                events = []
                with patch("smtplib.SMTP", return_value=FakeSMTPConnection(events)) as smtp:
                    SMTPTransport(settings).deliver(
                        "person@example.org", MailMessage("Subject", "Body"),
                    )
                self.assertEqual(events, ["send"])
                expected_host = "::1" if host == "[::1]" else host.strip()
                self.assertEqual(smtp.call_args.args[0], expected_host)

    def test_plain_loopback_rejects_alias_encoded_and_nonloopback_hosts(self):
        rejected = (
            "localhost.", "localhost.example.org", "mail.local", "0.0.0.0", "::",
            "10.0.0.1", "192.168.1.1", "169.254.1.1", "224.0.0.1",
            "127.1", "0177.0.0.1", "0x7f000001", "2130706433",
            "::ffff:127.0.0.1", "fe80::1%1", "[::1%1]", "[::ffff:127.0.0.1]",
        )
        for host in rejected:
            with self.subTest(host=host):
                with self.assertRaises(MailConfigurationError):
                    self.settings(
                        host=host, security="plain", username=None, password=None,
                        allow_plain_loopback=True,
                    ).validate()

    def test_plain_loopback_validation_never_uses_dns(self):
        with patch("socket.getaddrinfo", side_effect=AssertionError("DNS used")) as resolver:
            self.settings(
                host="localhost", security="plain", username=None, password=None,
                allow_plain_loopback=True,
            ).validate()
            with self.assertRaises(MailConfigurationError):
                self.settings(
                    host="smtp.example.org", security="plain", username=None, password=None,
                    allow_plain_loopback=True,
                ).validate()
        resolver.assert_not_called()

    def test_plain_loopback_requires_real_boolean_opt_in(self):
        with self.assertRaisesRegex(MailConfigurationError, "true or false"):
            self.settings(
                host="localhost", security="plain", username=None, password=None,
                allow_plain_loopback="false",
            ).validate()

    def test_missing_or_failed_starttls_never_reads_credentials_or_sends(self):
        for connection in (
            FakeSMTPConnection([], starttls_available=False, ehlo_codes=(250,)),
            FakeSMTPConnection([], starttls_error=OSError("raw fictional response")),
            FakeSMTPConnection([], ehlo_codes=(250, 550)),
        ):
            events = connection.events
            store = FakeCredentialStore(events, [("sender@example.org", "fictional-secret")])
            transport = SMTPTransport(
                self.settings(password=None, credential_target="Example/Mail"),
                credential_store=store,
            )
            with self.subTest(connection=connection), \
                 patch("smtplib.SMTP", return_value=connection):
                with self.assertRaises(MailDeliveryError) as caught:
                    transport.deliver("person@example.org", MailMessage("Private subject", "Private body"))
            self.assertNotIn("credential-read", events)
            self.assertNotIn("send", events)
            self.assertNotIn("fictional-secret", str(caught.exception))
            self.assertNotIn("raw fictional", str(caught.exception))

    def test_ssl_authentication_uses_verified_context_without_plain_fallback(self):
        events = []
        connection = FakeSMTPConnection(events)
        context = object()
        store = FakeCredentialStore(events, [("sender@example.org", "fictional-secret")])
        settings = self.settings(
            security="ssl", password=None, credential_target="Example/Mail",
        )
        with patch("ssl.create_default_context", return_value=context), \
             patch("smtplib.SMTP_SSL", return_value=connection) as secure, \
             patch("smtplib.SMTP") as plain:
            SMTPTransport(settings, credential_store=store).deliver(
                "person@example.org", MailMessage("Subject", "Body"),
            )
        self.assertEqual(events, ["credential-read",
                                  ("login", "sender@example.org", "fictional-secret"), "send"])
        self.assertIs(secure.call_args.kwargs["context"], context)
        plain.assert_not_called()

    def test_ssl_failure_is_safe_and_never_falls_back(self):
        settings = self.settings(security="ssl")
        with patch("smtplib.SMTP_SSL", side_effect=OSError("raw server response")), \
             patch("smtplib.SMTP") as plain:
            with self.assertRaises(MailDeliveryError) as caught:
                SMTPTransport(settings).deliver(
                    "person@example.org", MailMessage("Private subject", "Private body"),
                )
        plain.assert_not_called()
        self.assertNotIn("raw server", str(caught.exception))
        self.assertNotIn("Private", str(caught.exception))

    def test_protected_modes_preserve_unauthenticated_delivery(self):
        for security in ("ssl", "starttls"):
            events = []
            connection = FakeSMTPConnection(events)
            settings = self.settings(
                security=security, username=None, password=None,
            )
            patch_target = "smtplib.SMTP_SSL" if security == "ssl" else "smtplib.SMTP"
            with self.subTest(security=security), patch(patch_target, return_value=connection):
                SMTPTransport(settings).deliver(
                    "person@example.org", MailMessage("Subject", "Body"),
                )
            self.assertNotIn("credential-read", events)
            self.assertFalse(any(isinstance(item, tuple) and item[0] == "login" for item in events))
            self.assertEqual(events[-1], "send")

    def test_final_boundary_blocks_artificial_plaintext_auth_before_vault_read(self):
        events = []
        settings = self.settings(password=None, credential_target="Example/Mail")
        transport = SMTPTransport(
            settings, credential_store=FakeCredentialStore(
                events, [("sender@example.org", "fictional-secret")],
            ),
        )
        object.__setattr__(settings, "security", "plain")
        object.__setattr__(settings, "allow_plain_loopback", True)
        object.__setattr__(settings, "host", "localhost")
        with patch("smtplib.SMTP", return_value=FakeSMTPConnection(events)):
            with self.assertRaisesRegex(MailConfigurationError, "cannot use authentication"):
                transport.deliver("person@example.org", MailMessage("Subject", "Body"))
        self.assertNotIn("credential-read", events)
        self.assertNotIn("send", events)

    def test_final_boundary_blocks_mutated_remote_plaintext_before_network(self):
        settings = self.settings(
            host="localhost", security="plain", username=None, password=None,
            allow_plain_loopback=True,
        )
        transport = SMTPTransport(settings)
        object.__setattr__(settings, "host", "smtp.example.org")
        with patch("smtplib.SMTP") as smtp:
            with self.assertRaisesRegex(MailConfigurationError, "loopback"):
                transport.deliver("person@example.org", MailMessage("Subject", "Body"))
        smtp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
