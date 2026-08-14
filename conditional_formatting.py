"""Semantic conditional formatting and compact status summaries."""

from __future__ import annotations

from dataclasses import dataclass

import wx


@dataclass(frozen=True)
class StatusStyle:
    foreground: str | None = None
    background: str | None = None
    bold: bool = False


STATUS_STYLES = {
    "normal": StatusStyle(),
    "complete": StatusStyle("#176B2C", "#EAF7EE", True),
    "incomplete": StatusStyle("#B00020", "#FFF0F0", True),
    "customized": StatusStyle("#0066CC", None, False),
    "omitted": StatusStyle("#6B7280", "#F3F4F6", False),
    "inactive": StatusStyle("#6B7280", "#F3F4F6", False),
    "warning": StatusStyle("#8A4B00", "#FFF4CC", True),
}


def status_style(name):
    key = str(name or "normal").strip().casefold()
    if key not in STATUS_STYLES:
        raise ValueError("Unknown JSForm status style: {}".format(name))
    return STATUS_STYLES[key]


def condition_matches(actual, operator="equals", expected=None):
    operator = str(operator or "equals").casefold()
    if operator in ("equals", "eq"):
        return actual == expected
    if operator in ("not_equals", "ne"):
        return actual != expected
    if operator == "empty":
        return actual is None or actual == ""
    if operator == "not_empty":
        return actual is not None and actual != ""
    if operator == "truthy":
        return bool(actual)
    if operator == "falsy":
        return not bool(actual)
    if operator == "contains":
        return str(expected or "").casefold() in str(actual or "").casefold()
    if operator == "greater_than":
        return actual is not None and actual > expected
    if operator == "less_than":
        return actual is not None and actual < expected
    raise ValueError("Unknown conditional-format operator: {}".format(operator))


class ConditionalFormatter:
    def __init__(self, rules=(), default="normal"):
        self.rules = tuple(dict(rule) for rule in rules)
        self.default = default

    def status(self, record):
        record = record or {}
        for rule in self.rules:
            if condition_matches(
                record.get(rule.get("field")), rule.get("operator", "equals"), rule.get("value"),
            ):
                return rule.get("style", "normal")
        return self.default

    def style(self, record):
        return status_style(self.status(record))


def apply_control_style(control, style_name):
    """Apply a named style while retaining the control's original appearance."""
    if not hasattr(control, "_jsform_base_style"):
        control._jsform_base_style = (
            control.GetForegroundColour(), control.GetBackgroundColour(), control.GetFont(),
        )
    base_foreground, base_background, base_font = control._jsform_base_style
    style = status_style(style_name)
    control.SetForegroundColour(wx.Colour(style.foreground) if style.foreground else base_foreground)
    control.SetBackgroundColour(wx.Colour(style.background) if style.background else base_background)
    font = wx.Font(base_font)
    font.SetWeight(wx.FONTWEIGHT_BOLD if style.bold else base_font.GetWeight())
    control.SetFont(font)
    control.Refresh()


def apply_conditional_controls(controls, descriptions, record):
    for name, control in controls.items():
        rules = descriptions.get(name, {}).get("conditionalformat", ())
        if rules:
            apply_control_style(control, ConditionalFormatter(rules).status(record))


@dataclass(frozen=True)
class StatusSummaryItem:
    label: str
    value: object
    status: str = "normal"


class StatusSummaryCtrl(wx.Panel):
    """Compact, reusable strip of labeled semantic status values."""

    def __init__(self, parent, items=()):
        super().__init__(parent)
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self.sizer)
        self.set_items(items)

    def set_items(self, items):
        self.sizer.Clear(delete_windows=True)
        for item in items:
            label = wx.StaticText(self, label="{}: {}".format(item.label, item.value))
            apply_control_style(label, item.status)
            self.sizer.Add(label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 12)
        self.Layout()
