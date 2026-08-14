"""Provider-neutral, privacy-conscious email delivery for JSForm applications."""

from __future__ import annotations

import mimetypes
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Iterable, Protocol


_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class MailConfigurationError(RuntimeError):
    """Raised when required mail configuration is incomplete or unsafe."""


class MailDeliveryError(RuntimeError):
    """Raised by a transport without exposing credentials."""


@dataclass(frozen=True)
class MailSettings:
    host: str
    port: int
    username: str | None
    password: str | None
    sender_address: str
    sender_name: str = ""
    security: str = "starttls"
    reply_to: str | None = None

    def validate(self):
        if not self.host.strip():
            raise MailConfigurationError("Mail server is required.")
        if not 1 <= int(self.port) <= 65535:
            raise MailConfigurationError("Mail server port must be between 1 and 65535.")
        if not valid_email(self.sender_address):
            raise MailConfigurationError("A valid sender email address is required.")
        if self.reply_to and not valid_email(self.reply_to):
            raise MailConfigurationError("Reply-to must be a valid email address.")
        if self.security.casefold() not in {"ssl", "starttls", "plain"}:
            raise MailConfigurationError("Mail security must be SSL, STARTTLS, or Plain.")
        if bool(self.username) != bool(self.password):
            raise MailConfigurationError("Mail username and password must be supplied together.")


@dataclass(frozen=True)
class MailMessage:
    subject: str
    body: str
    attachments: tuple[Path, ...] = ()


@dataclass(frozen=True)
class DeliveryResult:
    recipient: str
    succeeded: bool
    message: str = ""


class MailTransport(Protocol):
    def deliver(self, recipient: str, message: MailMessage) -> None: ...


def normalized_email(value) -> str:
    return str(value or "").strip().casefold()


def valid_email(value) -> bool:
    return bool(_EMAIL.fullmatch(str(value or "").strip()))


def unique_recipients(recipients: Iterable[str]) -> tuple[str, ...]:
    unique = {}
    for recipient in recipients:
        normalized = normalized_email(recipient)
        if normalized and normalized not in unique:
            unique[normalized] = str(recipient).strip()
    return tuple(unique.values())


class MailService:
    """Deliver separately so recipients never receive one another's addresses."""

    def __init__(self, transport: MailTransport):
        self.transport = transport

    def send(self, recipients: Iterable[str], message: MailMessage) -> tuple[DeliveryResult, ...]:
        results = []
        for recipient in unique_recipients(recipients):
            if not valid_email(recipient):
                results.append(DeliveryResult(recipient, False, "Invalid email address."))
                continue
            try:
                self.transport.deliver(recipient, message)
            except Exception as error:
                safe_message = str(error).strip() or "Delivery failed."
                results.append(DeliveryResult(recipient, False, safe_message))
            else:
                results.append(DeliveryResult(recipient, True, "Sent"))
        return tuple(results)


class SMTPTransport:
    """SMTP implementation that creates a fresh RFC message for every recipient."""

    def __init__(self, settings: MailSettings, timeout=30):
        settings.validate()
        self.settings = settings
        self.timeout = timeout

    def _message(self, recipient: str, message: MailMessage) -> EmailMessage:
        email = EmailMessage()
        email["From"] = formataddr((self.settings.sender_name, self.settings.sender_address))
        email["To"] = recipient
        email["Subject"] = message.subject.strip()
        email["Date"] = formatdate(localtime=True)
        email["Message-ID"] = make_msgid()
        if self.settings.reply_to:
            email["Reply-To"] = self.settings.reply_to
        email.set_content(message.body)
        for attachment in message.attachments:
            path = Path(attachment)
            if not path.is_file():
                raise MailDeliveryError("An email attachment is unavailable: {}".format(path.name))
            content_type, _encoding = mimetypes.guess_type(path.name)
            main_type, sub_type = (content_type or "application/octet-stream").split("/", 1)
            email.add_attachment(
                path.read_bytes(), maintype=main_type, subtype=sub_type, filename=path.name,
            )
        return email

    def deliver(self, recipient: str, message: MailMessage) -> None:
        email = self._message(recipient, message)
        context = ssl.create_default_context()
        try:
            if self.settings.security.casefold() == "ssl":
                connection = smtplib.SMTP_SSL(
                    self.settings.host, self.settings.port, timeout=self.timeout, context=context,
                )
            else:
                connection = smtplib.SMTP(
                    self.settings.host, self.settings.port, timeout=self.timeout,
                )
            with connection:
                if self.settings.security.casefold() == "starttls":
                    connection.starttls(context=context)
                if self.settings.username:
                    connection.login(self.settings.username, self.settings.password)
                connection.send_message(email)
        except (OSError, smtplib.SMTPException) as error:
            raise MailDeliveryError("The mail provider rejected or could not deliver the message.") from error
