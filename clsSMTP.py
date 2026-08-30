"""Preserve the historical SMTP facade through the supported mail service."""

from pathlib import Path

import JSForm


class clsSMTP:
    """
        clsSMTP - Manages SMTP connection and allows sending eMail
            see yagmail Python library
    """
    def __init__(self):
        def setting(name, default=None):
            try:
                value = JSForm.CONFIG.get_Config_Value("SMTP", name)
            except Exception:
                value = None
            return default if value in (None, "") else value

        target = str(setting("CredentialTarget", "") or "").strip()
        if not target:
            raise JSForm.MailConfigurationError(
                "The historical SMTP password must be migrated to protected storage."
            )
        username = str(setting("UserName", "") or "").strip() or None
        sender = str(setting("SenderAddress", username or "") or "").strip()
        settings = JSForm.MailSettings(
            str(setting("Server", "") or ""), int(setting("Port", 587)),
            username, None, sender, str(setting("SenderName", "") or ""),
            str(setting("Security", "starttls") or "starttls").casefold(),
            str(setting("ReplyTo", "") or "").strip() or None,
            target,
        )
        self._service = JSForm.MailService(JSForm.SMTPTransport(settings))

    def sendeMail(self, emailaddress, name, subject, msg, attachment):
        """Deliver through the supported transport while preserving the legacy call."""
        if emailaddress is None:
            return None
        recipients = (emailaddress,) if isinstance(emailaddress, str) else tuple(emailaddress)
        if attachment in (None, ""):
            attachments = ()
        elif isinstance(attachment, (str, Path)):
            attachments = (Path(attachment),)
        else:
            attachments = tuple(Path(value) for value in attachment)
        body = "\n".join(str(value) for value in msg) if isinstance(msg, (list, tuple)) else str(msg)
        results = self._service.send(
            recipients, JSForm.MailMessage(str(subject), body, attachments),
        )
        failed = next((result for result in results if not result.succeeded), None)
        if failed is not None:
            raise JSForm.MailDeliveryError(failed.message or "Email delivery failed.")
        return None
