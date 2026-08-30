"""Create verified, local-only JSForm diagnostic support packages."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from JSForm.error_redaction import (
    normalize_diagnostic_value,
    redact_text,
    safe_diagnostics as normalize_diagnostics,
)


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _redact_jsonl(value: bytes, redactors) -> bytes:
    """Redact parsed records and malformed fallback text before archive use."""
    text = value.decode("utf-8", errors="replace")
    raw_lines = text.splitlines()
    parsed: list[Any] = []
    try:
        parsed = [json.loads(line) for line in raw_lines]
    except (TypeError, ValueError, json.JSONDecodeError):
        safe = redact_text(text, redactors, max_length=None)
        return (safe + ("" if not safe or safe.endswith("\n") else "\n")).encode("utf-8")
    lines: list[str] = []
    for record in parsed:
        normalized = normalize_diagnostic_value(record, redactors)
        lines.append(json.dumps(normalized, ensure_ascii=False, separators=(",", ":")))
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def create_support_package(reporter, destination, safe_diagnostics=None) -> Path:
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(f"Support package already exists: {destination.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    reporter.cleanup_expired_logs()

    redactors = reporter.config.redactors
    contents: dict[str, bytes] = {
        "system-info.json": _json_bytes(normalize_diagnostics(reporter.system_info(), redactors)),
    }
    for path in sorted(reporter.log_directory.glob("errors.jsonl*")):
        if path.is_file():
            contents[f"logs/{path.name}"] = _redact_jsonl(path.read_bytes(), redactors)
    if safe_diagnostics is not None:
        diagnostics = safe_diagnostics() if callable(safe_diagnostics) else safe_diagnostics
        if not isinstance(diagnostics, Mapping):
            raise TypeError("Safe diagnostics must be a mapping.")
        contents["application-diagnostics.json"] = _json_bytes(
            normalize_diagnostics(dict(diagnostics), redactors)
        )

    manifest = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "files": [
            {"name": name, "sha256": _sha256(value), "size": len(value)}
            for name, value in sorted(contents.items())
        ],
    }
    contents["manifest.json"] = _json_bytes(manifest)

    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=destination.stem + ".", suffix=".tmp", dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_name = Path(temporary.name)
        with zipfile.ZipFile(temporary_name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, value in sorted(contents.items()):
                archive.writestr(name, value)
        with zipfile.ZipFile(temporary_name, "r") as archive:
            if archive.testzip() is not None:
                raise RuntimeError("The support package did not verify.")
            loaded = json.loads(archive.read("manifest.json"))
            for entry in loaded["files"]:
                value = archive.read(entry["name"])
                if len(value) != entry["size"] or _sha256(value) != entry["sha256"]:
                    raise RuntimeError("The support package manifest did not verify.")
        os.replace(temporary_name, destination)
        temporary_name = None
        return destination
    finally:
        if temporary_name is not None:
            try:
                temporary_name.unlink()
            except OSError:
                pass
