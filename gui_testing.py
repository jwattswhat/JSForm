"""Reusable wxPython GUI-test lifecycle and visual-evidence helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

import wx
from PIL import Image, ImageChops, ImageGrab


class GUITestError(RuntimeError):
    """Report a deterministic GUI harness or visual-comparison failure."""


_DEFAULT_CONTROL_NAMES = {
    "button", "checkbox", "choice", "combobox", "control", "datectrl",
    "dialog", "frame", "listctrl", "notebook", "panel", "searchctrl",
    "spinCtrl", "staticBitmap", "staticBox", "staticLine", "staticText",
    "text", "window",
}


@dataclass(frozen=True)
class VisualComparison:
    """Describe the result and evidence paths of one screenshot comparison."""

    matched: bool
    changed_pixels: int
    total_pixels: int
    expected: Path
    actual: Path
    difference: Path | None


def application():
    """Return the process wx application, creating it when necessary."""
    return wx.GetApp() or wx.App(False)


def drain_events(timeout=1.0):
    """Process pending GUI events within a bounded wall-clock interval."""
    app = application()
    deadline = time.monotonic() + max(0.01, float(timeout))
    while True:
        app.ProcessPendingEvents()
        wx.YieldIfNeeded()
        if not wx.EventLoopBase.GetActive() or not wx.EventLoopBase.GetActive().Pending():
            return
        if time.monotonic() >= deadline:
            raise GUITestError("The wx event queue did not become idle before timeout.")


def named_controls(window):
    """Return unique, explicitly named descendants keyed by stable identity."""
    found = {}
    pending = [window]
    while pending:
        current = pending.pop()
        name = current.GetName() if hasattr(current, "GetName") else ""
        if name and name not in _DEFAULT_CONTROL_NAMES:
            if name in found:
                raise GUITestError(f"Duplicate control identity: {name}")
            found[name] = current
        pending.extend(current.GetChildren() if hasattr(current, "GetChildren") else ())
    return found


def geometry_issues(window, minimum=(1, 1)):
    """Return named visible descendants outside the window client rectangle."""
    issues = []
    client = window.GetClientRect()
    for name, control in named_controls(window).items():
        if not control.IsShownOnScreen():
            continue
        size = control.GetSize()
        if size.width < minimum[0] or size.height < minimum[1]:
            issues.append(f"{name}: unusable size {size.width}x{size.height}")
            continue
        origin = window.ScreenToClient(control.ClientToScreen((0, 0)))
        rect = wx.Rect(origin, size)
        if not client.Contains(rect.GetTopLeft()) or not client.Contains(rect.GetBottomRight()):
            issues.append(f"{name}: outside client area")
    return issues


def destroy_owned_windows(parent=None):
    """Destroy matching top-level windows child-first and drain cleanup events."""
    windows = list(wx.GetTopLevelWindows())
    if parent is not None:
        windows = [item for item in windows if item is parent or item.IsDescendant(parent)]
    for window in reversed(windows):
        if window:
            window.Destroy()
    drain_events()


def capture_client(window, path):
    """Capture one shown window client area as a PNG without approving a baseline."""
    drain_events()
    size = window.GetClientSize()
    if size.width < 1 or size.height < 1:
        raise GUITestError("Cannot capture an empty client area.")
    origin = window.ClientToScreen((0, 0))
    bitmap = wx.Bitmap(size.width, size.height)
    memory = wx.MemoryDC(bitmap)
    memory.Blit(0, 0, size.width, size.height, wx.ScreenDC(), origin.x, origin.y)
    memory.SelectObject(wx.NullBitmap)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    bitmap.SaveFile(str(target), wx.BITMAP_TYPE_PNG)
    with Image.open(target).convert("RGB") as captured:
        extrema = captured.getextrema()
    if all(low == high == 0 for low, high in extrema):
        bbox = (origin.x, origin.y, origin.x + size.width, origin.y + size.height)
        try:
            fallback = ImageGrab.grab(bbox=bbox, include_layered_windows=True)
        except OSError as error:
            target.unlink(missing_ok=True)
            raise GUITestError(
                "The desktop capture returned a uniform black image and the "
                "Windows fallback capture is unavailable; this session cannot "
                "produce visual evidence."
            ) from error
        fallback.save(target)
        extrema = fallback.convert("RGB").getextrema()
        if all(low == high == 0 for low, high in extrema):
            target.unlink(missing_ok=True)
            raise GUITestError(
                "The desktop capture returned a uniform black image through "
                "both wx and Windows capture; this session cannot produce "
                "visual evidence."
            )
    return target


def compare_png(expected, actual, difference, tolerance=0.001):
    """Compare equal-sized PNGs and write highlighted failure evidence only."""
    expected, actual, difference = Path(expected), Path(actual), Path(difference)
    with Image.open(expected).convert("RGBA") as wanted, Image.open(actual).convert("RGBA") as got:
        if wanted.size != got.size:
            raise GUITestError(f"Visual dimensions differ: {wanted.size} != {got.size}")
        delta = ImageChops.difference(wanted, got)
        pixels = getattr(delta, "get_flattened_data", delta.getdata)()
        changed = sum(1 for pixel in pixels if pixel != (0, 0, 0, 0))
        total = wanted.width * wanted.height
        matched = changed / max(1, total) <= float(tolerance)
        result_path = None
        if not matched:
            difference.parent.mkdir(parents=True, exist_ok=True)
            delta.save(difference)
            result_path = difference
        return VisualComparison(matched, changed, total, expected, actual, result_path)
