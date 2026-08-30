"""Resolve and safely open local files referenced by JSForm controls."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PureWindowsPath
import re
from typing import Iterable


ACTIVE_EXTENSIONS = frozenset({
    ".ahk", ".appinstaller", ".application", ".appref-ms", ".appx", ".appxbundle",
    ".bat", ".chm", ".cmd", ".com", ".cpl", ".diagcab", ".docm", ".dotm",
    ".exe", ".gadget", ".hta", ".htm", ".html", ".inf",
    ".ins", ".isp", ".jar", ".js", ".jse", ".library-ms", ".lnk", ".msc",
    ".mht", ".mhtml", ".msi", ".msix", ".msixbundle", ".msp", ".mst",
    ".pif", ".pl", ".potm", ".ppam", ".ppsm", ".pptm", ".ps1", ".ps1xml",
    ".ps2", ".ps2xml", ".psc1", ".psc2", ".psd1", ".psm1", ".reg",
    ".py", ".pyw", ".rb", ".scf", ".scr", ".sct", ".search-ms",
    ".settingcontent-ms", ".sh", ".shb", ".shs", ".sldm", ".svg", ".theme",
    ".url", ".vb", ".vbe", ".vbs", ".website", ".workflow", ".ws", ".wsc",
    ".wsf", ".wsh", ".xbap", ".xhtml", ".xlam", ".xlsb", ".xll", ".xlsm",
    ".xltm", ".xnk",
})
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_RESERVED_DEVICE = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", re.IGNORECASE)
_policy = None


class FileOpenDenied(RuntimeError):
    """Raised when a candidate fails the configured local-document policy."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FileOpenPolicy:
    """Canonical application-approved roots and passive file extensions."""

    approved_roots: tuple[Path, ...]
    passive_extensions: frozenset[str]


def _deny(code, message="This file cannot be opened from this application."):
    raise FileOpenDenied(code, message)


def _windows_syntax(path_value):
    text = str(path_value or "").strip()
    if not text:
        _deny("empty", "No file has been selected.")
    if "\x00" in text:
        _deny("invalid_path")
    normalized = text.replace("/", "\\")
    if normalized.startswith("\\\\"):
        _deny("remote_or_device")
    scheme = _SCHEME.match(text)
    if scheme:
        if len(scheme.group(0)) == 2 and scheme.group(0)[0].isalpha():
            if len(text) <= 2 or text[2] not in "\\/":
                _deny("relative_path")
        else:
            _deny("url_or_scheme")
    windows = PureWindowsPath(text)
    if not re.fullmatch(r"[A-Za-z]:", windows.drive or "") or windows.root != "\\":
        _deny("relative_path")
    if ":" in text[2:]:
        _deny("alternate_stream")
    for component in windows.parts[1:]:
        if component != component.rstrip(" ."):
            _deny("ambiguous_path")
        device_name = component.rstrip(" .")
        device_base = device_name.split(".", 1)[0].rstrip(" ")
        if _RESERVED_DEVICE.fullmatch(device_base):
            _deny("reserved_device")
    return Path(text)


def _has_reparse_component(path):
    current = Path(path.anchor)
    for component in path.parts[1:]:
        if component in {"", "."}:
            continue
        if component == "..":
            current = current.parent
            continue
        current = current / component
        status = current.lstat()
        attributes = getattr(status, "st_file_attributes", 0)
        reparse_attribute = getattr(stat_constants(), "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if current.is_symlink() or attributes & reparse_attribute:
            return True
    return False


def stat_constants():
    """Return the standard stat module through a testable narrow seam."""
    import stat
    return stat


def _normalize_extensions(values: Iterable[str]):
    if isinstance(values, (str, bytes)):
        raise ValueError("passive_extensions must be a collection of extensions")
    normalized = set()
    for supplied in values:
        extension = str(supplied or "").strip().casefold()
        if extension and not extension.startswith("."):
            extension = "." + extension
        if (
            not extension or extension in {".", ".*"}
            or "*" in extension or "?" in extension
            or "/" in extension or "\\" in extension
            or extension.count(".") != 1
        ):
            raise ValueError("Passive file extensions must be simple explicit suffixes.")
        if extension in ACTIVE_EXTENSIONS:
            raise ValueError("Active file types cannot be approved for shell opening.")
        normalized.add(extension)
    if not normalized:
        raise ValueError("At least one passive file extension is required.")
    return frozenset(normalized)


def configure_file_opening(approved_roots=None, passive_extensions=None):
    """Replace the process-wide application file-opening policy.

    Passing both arguments as ``None`` resets to the secure deny-all default.
    Roots must already exist as local, non-reparse directories.
    """
    global _policy
    if approved_roots is None and passive_extensions is None:
        _policy = None
        return None
    if approved_roots is None or passive_extensions is None:
        raise ValueError("approved_roots and passive_extensions are both required")
    if isinstance(approved_roots, (str, bytes, Path)):
        raise ValueError("approved_roots must be a collection of directories")
    roots = []
    for supplied in approved_roots:
        try:
            selected = _windows_syntax(supplied)
        except FileOpenDenied as error:
            raise ValueError("Approved roots must be absolute local Windows directories.") from error
        try:
            if _has_reparse_component(selected):
                raise ValueError("Approved roots cannot contain reparse points.")
            canonical = selected.resolve(strict=True)
        except FileNotFoundError as error:
            raise ValueError("Approved roots must be existing directories.") from error
        if not canonical.is_dir():
            raise ValueError("Approved roots must be existing directories.")
        roots.append(canonical)
    if not roots:
        raise ValueError("At least one approved local root is required.")
    _policy = FileOpenPolicy(tuple(dict.fromkeys(roots)), _normalize_extensions(passive_extensions))
    return _policy


def current_file_open_policy():
    """Return the configured policy, or ``None`` for the deny-all default."""
    return _policy


def resolve_picker_file(control, configured_directory=None) -> Path | None:
    """Return the best complete path represented by a file-picker control."""
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


def _inside_root(candidate, root):
    try:
        return os.path.commonpath((
            os.path.normcase(str(candidate)), os.path.normcase(str(root)),
        )) == os.path.normcase(str(root))
    except ValueError:
        return False


def approved_file_path(candidate):
    """Validate and return the canonical local passive document path."""
    if _policy is None:
        _deny("policy_missing")
    selected = _windows_syntax(candidate)
    try:
        if _has_reparse_component(selected):
            _deny("reparse_path")
        canonical = selected.resolve(strict=True)
    except FileNotFoundError:
        _deny("missing", "The selected file could not be found.")
    if not canonical.is_file():
        _deny("not_regular_file")
    extension = canonical.suffix.casefold()
    if extension in ACTIVE_EXTENSIONS or extension not in _policy.passive_extensions:
        _deny("disallowed_type", "This type of file cannot be opened from this application.")
    if not any(_inside_root(canonical, root) for root in _policy.approved_roots):
        _deny("outside_root", "This file is outside the application's approved document locations.")
    return canonical


def open_approved_file(candidate):
    """Validate ``candidate``, launch it once through Windows, and return its path."""
    canonical = approved_file_path(candidate)
    if approved_file_path(canonical) != canonical:
        _deny("changed_target")
    os.startfile(str(canonical))
    return canonical
