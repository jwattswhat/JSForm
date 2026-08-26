"""Helpers for opening files referenced by JSForm controls."""

from __future__ import annotations

from pathlib import Path


def resolve_picker_file(control, configured_directory=None) -> Path | None:
    """Return the best complete path represented by a file-picker control.

    File picker values are historically stored as filenames, while the control
    separately remembers the directory from which a record was loaded.  Prefer
    an absolute picker value, then that remembered directory, and finally the
    configured initial directory.
    """

    raw_value = str(control.GetPath() or "").strip()
    if not raw_value:
        return None
    selected = Path(raw_value).expanduser()
    if selected.is_absolute():
        return selected

    remembered = str(getattr(control, "path", "") or "").strip()
    if remembered:
        return Path(remembered).expanduser() / selected.name

    configured = str(configured_directory or "").strip()
    if configured:
        return Path(configured).expanduser() / selected.name
    return selected
