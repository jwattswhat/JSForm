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
_SENSITIVE_NAME = (
    r"(?:password|passwd|pwd|secret|token|api[-_ ]?key|apikey|authorization|"
    r"cookie|credential|connection[-_ ]?string|hash|salt|smtp[-_ ]?password|"
    r"database[-_ ]?password)"
)
_HEADER = re.compile(
    r"(?i)(?P<prefix>\b(?:authorization|proxy-authorization|cookie|set-cookie)\s*:\s*)[^\r\n]+"
)
_SECRET_ARGUMENT = re.compile(
    rf"(?i)(?P<prefix>--?{_SENSITIVE_NAME}(?:=|\s+))(?P<value>\[REDACTED\]|\"[^\"]*\"|'[^']*'|[^\s]+)"
)
_KEY_VALUE = re.compile(
    rf"(?i)(?P<prefix>(?P<key_quote>[\"']?)(?:[a-z0-9]+[-_ ])*{_SENSITIVE_NAME}"
    rf"(?P=key_quote)\s*(?:=|:)\s*)(?P<value>\[REDACTED\]|\"(?:\\.|[^\"\\])*\"|"
    rf"'(?:\\.|[^'\\])*'|[^\s,;&}}\]\r\n]+)"
)
_BOUNDED_TEXT = 2000
_MAX_DEPTH = 5
_MAX_ITEMS = 25
_TOO_DEEP = "<maximum-depth>"
_CYCLE = "<cycle>"


def sensitive_key(name: object) -> bool:
    lowered = str(name).casefold()
    tokens = {part for part in re.split(r"[^a-z0-9]+", lowered) if part}
    compact = "".join(character for character in lowered if character.isalnum())
    long_names = tuple(part for part in SENSITIVE_KEY_PARTS if part != "pwd")
    normalized = {"".join(character for character in part if character.isalnum()) for part in long_names}
    return "pwd" in tokens or any(
        marker in tokens or compact == marker or compact.endswith(marker)
        for marker in normalized
    )


def _framework_redact(text: str) -> str:
    text = _URI_CREDENTIAL.sub(lambda match: match.group("scheme") + REDACTED + "@", text)
    text = _HEADER.sub(lambda match: match.group("prefix") + REDACTED, text)
    text = _SECRET_ARGUMENT.sub(lambda match: match.group("prefix") + REDACTED, text)
    return _KEY_VALUE.sub(lambda match: match.group("prefix") + REDACTED, text)


def redact_text(
    value: object,
    redactors: Iterable[Callable[[str], str]] = (),
    max_length: int | None = _BOUNDED_TEXT,
) -> str:
    text = _framework_redact(str(value))
    for redactor in redactors:
        try:
            text = str(redactor(text))
        except Exception:
            continue
    text = _framework_redact(text)
    return text if max_length is None else text[:max_length]


def normalize_diagnostic_value(
    value: Any,
    redactors: Iterable[Callable[[str], str]] = (),
    *,
    _depth: int = 0,
    _seen: set[int] | None = None,
) -> Any:
    """Return a bounded, recursively redacted JSON-safe diagnostic value."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_text(value, redactors)
    if _depth >= _MAX_DEPTH:
        return _TOO_DEEP
    seen = _seen if _seen is not None else set()
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in seen:
            return _CYCLE
        seen.add(identity)
        result: dict[str, Any] = {}
        try:
            for index, (key, item) in enumerate(value.items()):
                if index >= _MAX_ITEMS:
                    break
                name = redact_text(key, redactors, max_length=100)
                result[name] = REDACTED if sensitive_key(name) else normalize_diagnostic_value(
                    item, redactors, _depth=_depth + 1, _seen=seen,
                )
        except Exception:
            result["diagnostics"] = "<unavailable>"
        finally:
            seen.discard(identity)
        return result
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in seen:
            return _CYCLE
        seen.add(identity)
        try:
            return [
                normalize_diagnostic_value(item, redactors, _depth=_depth + 1, _seen=seen)
                for item in value[:_MAX_ITEMS]
            ]
        finally:
            seen.discard(identity)
    return f"<{type(value).__name__}>"


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
        result[name] = REDACTED if sensitive_key(name) else normalize_diagnostic_value(
            value, redactors,
        )
    return result


def safe_diagnostics(values: Mapping[str, Any], redactors=()) -> dict[str, Any]:
    """Return a redacted, scalar-only diagnostics mapping for support export."""
    normalized = normalize_diagnostic_value(values, redactors)
    return normalized if isinstance(normalized, dict) else {}
