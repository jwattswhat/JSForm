"""Privacy-safe normalization for JSForm diagnostic error records."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Callable, Iterable


REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = (
    "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
    "authorization", "cookie", "credential", "connection_string", "hash",
    "salt", "smtp_password", "database_password",
)
_URI_CREDENTIAL = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@", re.I)
_AUTH_HEADER = re.compile(r"(?im)^(authorization\s*:\s*)[^\r\n]+")
_PASSWORD_ARGUMENT = re.compile(r"(?i)(--?(?:password|passwd|pwd)(?:=|\s+))([^\s]+)")
_BOUNDED_TEXT = 2000


def sensitive_key(name: object) -> bool:
    lowered = str(name).casefold()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact_text(
    value: object,
    redactors: Iterable[Callable[[str], str]] = (),
    max_length: int | None = _BOUNDED_TEXT,
) -> str:
    text = str(value)
    text = _URI_CREDENTIAL.sub(lambda match: match.group("scheme") + REDACTED + "@", text)
    text = _AUTH_HEADER.sub(lambda match: match.group(1) + REDACTED, text)
    text = _PASSWORD_ARGUMENT.sub(lambda match: match.group(1) + REDACTED, text)
    for redactor in redactors:
        try:
            text = str(redactor(text))
        except Exception:
            continue
    return text if max_length is None else text[:max_length]


def safe_context(
    values: Mapping[str, Any] | None,
    allowed_keys: set[str],
    redactors: Iterable[Callable[[str], str]] = (),
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in (values or {}).items():
        name = str(key)
        if name not in allowed_keys:
            continue
        if sensitive_key(name):
            result[name] = REDACTED
        elif isinstance(value, bool) or value is None:
            result[name] = value
        elif isinstance(value, (int, float)):
            result[name] = value
        elif isinstance(value, str):
            result[name] = redact_text(value, redactors)
        elif isinstance(value, (list, tuple)):
            result[name] = [
                redact_text(item, redactors) if isinstance(item, str) else item
                for item in value[:25]
                if item is None or isinstance(item, (bool, int, float, str))
            ]
        else:
            result[name] = f"<{type(value).__name__}>"
    return result
