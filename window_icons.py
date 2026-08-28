"""Application-neutral icon selection for JSForm top-level windows."""

from __future__ import annotations

from pathlib import Path

import wx


DEFAULT_ICON_PATH = Path(__file__).with_name("assets") / "jsform.ico"
_application_icon_path: Path | None = None


def configure_application_icon(path=None):
    """Set an application ``.ico`` override, or reset to JSForm's default."""
    global _application_icon_path
    if path is None:
        _application_icon_path = None
        return DEFAULT_ICON_PATH
    selected = Path(path).expanduser().resolve()
    if selected.suffix.casefold() != ".ico":
        raise ValueError("Application icons must use the .ico format.")
    if not selected.is_file():
        raise FileNotFoundError(selected)
    _application_icon_path = selected
    return selected


def application_icon_path():
    """Return the configured application icon or the bundled JSForm icon."""
    return _application_icon_path or DEFAULT_ICON_PATH


def apply_window_icon(window, path=None):
    """Apply an ICO file to a wx top-level *window* and return its path."""
    selected = Path(path).expanduser().resolve() if path else application_icon_path()
    if not selected.is_file():
        raise FileNotFoundError(selected)
    icon = wx.Icon(str(selected), wx.BITMAP_TYPE_ICO)
    if not icon.IsOk():
        raise ValueError("Unable to load application icon: {}".format(selected))
    window.SetIcon(icon)
    return selected
