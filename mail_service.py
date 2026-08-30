"""Provider-neutral, privacy-conscious email delivery for JSForm applications."""

from __future__ import annotations

import mimetypes
import ipaddress
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Iterable, Protocol


_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _is_strict_loopback_host(value) -> bool:
    """Return whether ``value`` is one canonical, non-DNS loopback host."""
    host = str(value or "").strip()
    if host.casefold() == "localhost":
        return True
    if host.startswith("[") or host.endswith("]"):
        if not (host.startswith("[") and host.endswith("]")):
            return False
        host = host[1:-1]
        if host != "::1":
            return False
    if "%" in host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv4Address):
        return address in ipaddress.ip_network("127.0.0.0/8")
    return address == ipaddress.IPv6Address("::1")


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
    credential_target: str | None = None
    allow_plain_loopback: bool = False

    def validate(self):
        """Validate addresses, authentication shape, and protected transport policy."""
        if not self.host.strip():
            raise MailConfigurationError("Mail server is required.")
        if not 1 <= int(self.port) <= 65535:
            raise MailConfigurationError("Mail server port must be between 1 and 65535.")
        if not valid_email(self.sender_address):
            raise MailConfigurationError("A valid sender email address is required.")
        if self.reply_to and not valid_email(self.reply_to):
            raise MailConfigurationError("Reply-to must be a valid email address.")
        security = str(self.security or "").casefold()
        if security not in {"ssl", "starttls", "plain"}:
            raise MailConfigurationError("Mail security must be SSL, STARTTLS, or Plain.")
        if not isinstance(self.allow_plain_loopback, bool):
            raise MailConfigurationError("Plain loopback permission must be true or false.")
        target = str(self.credential_target or "").strip()
        username = str(self.username or "").strip()
        password = self.password
        if target and password is not None:
            raise MailConfigurationError(
                "Use either a protected credential target or an in-memory password, not both."
            )
        if not target and bool(username) != bool(password):
            raise MailConfigurationError("Mail username and password must be supplied together.")
        if security == "plain":
            if target or username or password is not None:
                raise MailConfigurationError("Plain SMTP cannot use authentication credentials.")
            if not self.allow_plain_loopback or not _is_strict_loopback_host(self.host):
                raise MailConfigurationError(
                    "Plain SMTP is allowed only for an explicitly approved local loopback relay."
                )


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
    """Send fresh RFC messages through verified TLS or explicit plain loopback."""

    def __init__(self, settings: MailSettings, timeout=30, credential_store=None):
        settings.validate()
        self.settings = settings
        self.timeout = timeout
        self.credential_store = credential_store

    def _authentication(self):
        target = str(self.settings.credential_target or "").strip()
        if not target:
            username = str(self.settings.username or "").strip()
            if username:
                return username, self.settings.password
            return None
        store = self.credential_store
        if store is None:
            from JSForm.credential_store import WindowsCredentialStore
            store = WindowsCredentialStore()
        try:
            value = store.read(target)
        except Exception:
            raise MailConfigurationError(
                "The protected mail credential is unavailable."
            ) from None
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise MailConfigurationError("The protected mail credential is invalid.")
        username, secret = str(value[0] or "").strip(), str(value[1] or "")
        if not username or not secret:
            raise MailConfigurationError("The protected mail credential is incomplete.")
        configured = str(self.settings.username or "").strip()
        if configured and configured.casefold() != username.casefold():
            raise MailConfigurationError(
                "The protected mail credential does not match the configured account."
            )
        return username, secret

    def _require_protected_authentication(self, protected):
        """Fail before credential lookup if authentication lacks established TLS."""
        target = str(self.settings.credential_target or "").strip()
        username = str(self.settings.username or "").strip()
        if (target or username or self.settings.password is not None) and not protected:
            raise MailConfigurationError("Mail authentication requires a protected connection.")

    @staticmethod
    def _require_ehlo(connection, message):
        code, _response = connection.ehlo()
        if not 200 <= int(code) < 300:
            raise MailDeliveryError(message)

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
        try:
            # Reassert the complete configuration contract at the final network
            # boundary.  MailSettings is frozen, but this also fails closed if
            # low-level code has bypassed that protection after construction.
            self.settings.validate()
            security = self.settings.security.casefold()
            context = ssl.create_default_context() if security != "plain" else None
            host = self.settings.host.strip()
            if security == "plain" and host == "[::1]":
                host = "::1"
            if security == "ssl":
                connection = smtplib.SMTP_SSL(
                    host, self.settings.port, timeout=self.timeout, context=context,
                )
            else:
                connection = smtplib.SMTP(
                    host, self.settings.port, timeout=self.timeout,
                )
            with connection:
                protected = security == "ssl"
                if security == "starttls":
                    self._require_ehlo(connection, "The mail server did not accept a secure greeting.")
                    if not connection.has_extn("starttls"):
                        raise MailDeliveryError("The mail server does not offer protected delivery.")
                    connection.starttls(context=context)
                    self._require_ehlo(connection, "The protected mail connection could not be established.")
                    protected = True
                self._require_protected_authentication(protected)
                authentication = self._authentication()
                if authentication:
                    connection.login(*authentication)
                connection.send_message(email)
        except (OSError, smtplib.SMTPException):
            raise MailDeliveryError(
                "The mail provider rejected or could not deliver the message."
            ) from None
