"""Centralized, local-only diagnostic error reporting for JSForm applications."""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from JSForm.error_redaction import redact_text, safe_context


DEFAULT_CONTEXT_KEYS = {
    "application_mode", "database_name", "database_scope", "screen",
    "operation", "authenticated", "permission_scope", "record_type",
    "record_id", "transaction_state", "external_tool",
}


@dataclass(frozen=True)
class ErrorReportingConfig:
    application_name: str
    application_version: str | None = None
    error_id_prefix: str = "ERR"
    log_directory: Path | None = None
    jsform_version: str | None = None
    max_bytes: int = 2 * 1024 * 1024
    retained_files: int = 5
    context_keys: frozenset[str] = field(default_factory=lambda: frozenset(DEFAULT_CONTEXT_KEYS))
    safe_context_provider: Callable[[], Mapping[str, Any]] | None = None
    redactors: tuple[Callable[[str], str], ...] = ()


class ErrorReporter:
    SCHEMA_VERSION = 1

    def __init__(self, config: ErrorReportingConfig):
        self.config = config
        self.log_directory = config.log_directory or self._default_directory(config.application_name)
        self.log_path = self.log_directory / "errors.jsonl"
        self._lock = threading.RLock()
        self._reporting = threading.local()

    @staticmethod
    def _default_directory(application_name: str) -> Path:
        base = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())
        safe_name = "".join(character for character in application_name if character.isalnum() or character in " -_").strip()
        return base / (safe_name or "JSForm") / "Logs"

    def _error_id(self) -> tuple[str, str]:
        full = uuid.uuid4().hex.upper()
        prefix = "".join(c for c in self.config.error_id_prefix.upper() if c.isalnum())[:6] or "ERR"
        return full, f"{prefix}-{full[:4]}-{full[4:8]}"

    def _context(self, supplied: Mapping[str, Any] | None) -> dict[str, Any]:
        combined: dict[str, Any] = {}
        if self.config.safe_context_provider:
            try:
                combined.update(self.config.safe_context_provider() or {})
            except Exception:
                pass
        combined.update(supplied or {})
        return safe_context(combined, set(self.config.context_keys), self.config.redactors)

    def _record(self, exception: BaseException, *, severity: str, context: Mapping[str, Any] | None) -> tuple[str, dict[str, Any]]:
        full_id, display_id = self._error_id()
        safe = self._context(context)
        rendered = "".join(traceback.TracebackException.from_exception(exception).format())
        record = {
            "schema_version": self.SCHEMA_VERSION,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "error_id": full_id,
            "display_error_id": display_id,
            "severity": severity if severity in {"warning", "error", "fatal"} else "error",
            "exception_type": f"{type(exception).__module__}.{type(exception).__qualname__}",
            "message": redact_text(exception, self.config.redactors),
            "traceback": redact_text(rendered, self.config.redactors, max_length=None),
            "application_name": self.config.application_name,
            "application_version": self.config.application_version,
            "jsform_version": self.config.jsform_version,
            "python_version": platform.python_version(),
            "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
            "process_id": os.getpid(),
            "thread_name": threading.current_thread().name,
            "operation": safe.pop("operation", None),
            "screen": safe.pop("screen", None),
            "database_name": safe.pop("database_name", None),
            "database_scope": safe.pop("database_scope", None),
            "context": safe,
        }
        return display_id, record

    def _rotate(self) -> None:
        if not self.log_path.exists() or self.log_path.stat().st_size < self.config.max_bytes:
            return
        oldest = self.log_path.with_suffix(f".jsonl.{self.config.retained_files}")
        if oldest.exists():
            oldest.unlink()
        for number in range(self.config.retained_files - 1, 0, -1):
            source = self.log_path.with_suffix(f".jsonl.{number}")
            if source.exists():
                source.replace(self.log_path.with_suffix(f".jsonl.{number + 1}"))
        self.log_path.replace(self.log_path.with_suffix(".jsonl.1"))

    def _write(self, record: Mapping[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        try:
            with self._lock:
                self.log_directory.mkdir(parents=True, exist_ok=True)
                self._rotate()
                with self.log_path.open("a", encoding="utf-8", newline="") as stream:
                    stream.write(line)
        except Exception:
            try:
                fallback = Path(tempfile.gettempdir()) / f"{self.config.application_name}-errors-fallback.jsonl"
                with fallback.open("a", encoding="utf-8", newline="") as stream:
                    stream.write(line)
            except Exception:
                try:
                    sys.stderr.write("JSForm could not write its diagnostic error log.\n")
                except Exception:
                    pass

    def report(self, exception: BaseException, *, severity: str = "error", context: Mapping[str, Any] | None = None) -> str:
        if getattr(self._reporting, "active", False):
            return "ERR-LOGGING"
        self._reporting.active = True
        try:
            display_id, record = self._record(exception, severity=severity, context=context)
            self._write(record)
            return display_id
        finally:
            self._reporting.active = False


_REPORTER: ErrorReporter | None = None
_ORIGINAL_SYS_HOOK = None
_ORIGINAL_THREAD_HOOK = None


def configure_error_reporting(**kwargs) -> ErrorReporter:
    global _REPORTER
    normalized = dict(kwargs)
    if normalized.get("log_directory") is not None:
        normalized["log_directory"] = Path(normalized["log_directory"])
    if normalized.get("context_keys") is not None:
        normalized["context_keys"] = frozenset(normalized["context_keys"])
    if normalized.get("redactors") is not None:
        normalized["redactors"] = tuple(normalized["redactors"])
    _REPORTER = ErrorReporter(ErrorReportingConfig(**normalized))
    return _REPORTER


def current_error_reporter() -> ErrorReporter | None:
    return _REPORTER


def report_exception(exception: BaseException, *, severity: str = "error", safe_context: Mapping[str, Any] | None = None, **context) -> str:
    if _REPORTER is None:
        return "ERR-NOT-CONFIGURED"
    combined = dict(safe_context or {})
    combined.update(context)
    return _REPORTER.report(exception, severity=severity, context=combined)


def install_error_hooks() -> None:
    global _ORIGINAL_SYS_HOOK, _ORIGINAL_THREAD_HOOK
    if _ORIGINAL_SYS_HOOK is None:
        _ORIGINAL_SYS_HOOK = sys.excepthook

        def sys_hook(exception_type, exception, tb):
            if exception_type not in {KeyboardInterrupt, SystemExit}:
                report_exception(exception, severity="fatal", operation="python.unhandled")
            _ORIGINAL_SYS_HOOK(exception_type, exception, tb)

        sys.excepthook = sys_hook
    if hasattr(threading, "excepthook") and _ORIGINAL_THREAD_HOOK is None:
        _ORIGINAL_THREAD_HOOK = threading.excepthook

        def thread_hook(arguments):
            if arguments.exc_type not in {KeyboardInterrupt, SystemExit}:
                report_exception(arguments.exc_value, severity="error", operation="thread.unhandled")
            _ORIGINAL_THREAD_HOOK(arguments)

        threading.excepthook = thread_hook


def restore_error_hooks() -> None:
    global _ORIGINAL_SYS_HOOK, _ORIGINAL_THREAD_HOOK
    if _ORIGINAL_SYS_HOOK is not None:
        sys.excepthook = _ORIGINAL_SYS_HOOK
        _ORIGINAL_SYS_HOOK = None
    if _ORIGINAL_THREAD_HOOK is not None:
        threading.excepthook = _ORIGINAL_THREAD_HOOK
        _ORIGINAL_THREAD_HOOK = None
