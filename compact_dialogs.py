"""Reusable compact record editors and read-only linked-record viewers."""

from __future__ import annotations

from dataclasses import dataclass

import wx


@dataclass(frozen=True)
class EditorField:
    label: str
    field: str
    kind: str = "text"
    required: bool = False
    choices: tuple = ()
    read_only: bool = False
    width: int = 280


class CompactEditorModel:
    def __init__(self, fields, values=None, validator=None):
        self.fields = tuple(fields)
        self.values = dict(values or {})
        self.validator = validator

    def validate(self, values):
        cleaned = dict(values)
        for definition in self.fields:
            value = cleaned.get(definition.field)
            if isinstance(value, str):
                value = value.strip()
                cleaned[definition.field] = value
            if definition.required and value in (None, ""):
                raise ValueError("Enter {}.".format(definition.label.rstrip(":")))
        if self.validator:
            result = self.validator(dict(cleaned))
            if result is not None:
                cleaned = dict(result)
        return cleaned


class CompactEditorDialog(wx.Dialog):
    """Standard Save/Cancel editor for a small application-owned record."""

    def __init__(self, parent, *, title, fields, values=None, validator=None, instructions=""):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.model = CompactEditorModel(fields, values, validator)
        self.controls = {}
        self.result = None
        self._build(instructions)
        self.Fit()
        self.SetMinSize((440, self.GetSize().height))
        self.CentreOnParent()

    def _control(self, panel, definition):
        value = self.model.values.get(definition.field)
        if definition.kind == "choice":
            control = wx.Choice(panel, choices=[str(item) for item in definition.choices])
            if value in definition.choices:
                control.SetSelection(definition.choices.index(value))
            elif definition.choices:
                control.SetSelection(0)
        elif definition.kind == "checkbox":
            control = wx.CheckBox(panel)
            control.SetValue(bool(value))
        else:
            style = wx.TE_MULTILINE if definition.kind == "multiline" else 0
            if definition.read_only:
                style |= wx.TE_READONLY
            control = wx.TextCtrl(panel, value="" if value is None else str(value), style=style)
            if definition.kind == "multiline":
                control.SetMinSize((definition.width, 90))
        if definition.width and definition.kind != "checkbox":
            control.SetMinSize((definition.width, control.GetMinSize().height))
        control.Enable(not definition.read_only)
        return control

    def _build(self, instructions):
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        if instructions:
            helper = wx.StaticText(panel, label=instructions)
            helper.SetForegroundColour(wx.Colour(0, 90, 190))
            outer.Add(helper, 0, wx.EXPAND | wx.ALL, 10)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)
        for definition in self.model.fields:
            grid.Add(wx.StaticText(panel, label=definition.label), 0, wx.ALIGN_CENTER_VERTICAL)
            control = self._control(panel, definition)
            grid.Add(control, 1, wx.EXPAND)
            self.controls[definition.field] = control
        outer.Add(grid, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        buttons = wx.StdDialogButtonSizer()
        save = wx.Button(panel, wx.ID_SAVE, "Save")
        cancel = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        buttons.AddButton(save)
        buttons.AddButton(cancel)
        buttons.Realize()
        save.Bind(wx.EVT_BUTTON, self.on_save)
        cancel.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CANCEL))
        outer.Add(buttons, 0, wx.EXPAND | wx.ALL, 12)
        panel.SetSizer(outer)
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)

    def values(self):
        values = dict(self.model.values)
        for definition in self.model.fields:
            control = self.controls[definition.field]
            if definition.kind == "choice":
                values[definition.field] = control.GetStringSelection() or None
            else:
                values[definition.field] = control.GetValue()
        return values

    def on_save(self, _event):
        try:
            self.result = self.model.validate(self.values())
        except ValueError as error:
            wx.MessageBox(str(error), "Check the entry", wx.OK | wx.ICON_INFORMATION, self)
            return
        self.EndModal(wx.ID_SAVE)


@dataclass(frozen=True)
class LinkedRecordField:
    label: str
    field: str


class LinkedRecordViewerDialog(wx.Dialog):
    """Compact, read-only view of an application-supplied related record."""

    def __init__(self, parent, *, title, fields, record, instructions=""):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        if instructions:
            helper = wx.StaticText(panel, label=instructions)
            helper.SetForegroundColour(wx.Colour(0, 90, 190))
            outer.Add(helper, 0, wx.EXPAND | wx.ALL, 10)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)
        for definition in fields:
            grid.Add(wx.StaticText(panel, label=definition.label), 0, wx.ALIGN_TOP)
            value = record.get(definition.field)
            display = wx.TextCtrl(
                panel, value="" if value is None else str(value),
                style=wx.TE_READONLY | (wx.TE_MULTILINE if "\n" in str(value or "") else 0),
            )
            display.SetMinSize((300, 60 if "\n" in str(value or "") else -1))
            grid.Add(display, 1, wx.EXPAND)
        outer.Add(grid, 1, wx.EXPAND | wx.ALL, 12)
        close = wx.Button(panel, wx.ID_CLOSE, "Close")
        close.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CLOSE))
        outer.Add(close, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        panel.SetSizer(outer)
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)
        self.Fit()
        self.SetMinSize((440, self.GetSize().height))
        self.CentreOnParent()


def edit_compact_record(parent, **arguments):
    dialog = CompactEditorDialog(parent, **arguments)
    try:
        return dialog.result if dialog.ShowModal() == wx.ID_SAVE else None
    finally:
        dialog.Destroy()


def view_linked_record(parent, **arguments):
    dialog = LinkedRecordViewerDialog(parent, **arguments)
    try:
        return dialog.ShowModal()
    finally:
        dialog.Destroy()
