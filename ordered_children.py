"""Reusable ordered child-record model and editor dialog."""

from __future__ import annotations

from dataclasses import dataclass

import wx

from JSForm.list_behavior import ListCtrlBehavior


@dataclass(frozen=True)
class OrderedChildColumn:
    label: str
    field: str
    width: int = 140


class OrderedChildModel:
    """Edit an ordered collection without imposing application persistence rules."""

    def __init__(self, rows=(), *, key="id", sequence="sequence", protected=None):
        self.key = key
        self.sequence = sequence
        self.protected = protected or (lambda _row: False)
        self.rows = [dict(row) for row in rows]
        self.resequence()
        self._original = [dict(row) for row in self.rows]

    @property
    def dirty(self):
        return self.rows != self._original

    def mark_saved(self):
        self._original = [dict(row) for row in self.rows]

    def resequence(self):
        for position, row in enumerate(self.rows, 1):
            row[self.sequence] = position

    def add(self, row, index=None):
        item = dict(row)
        if index is None:
            self.rows.append(item)
            index = len(self.rows) - 1
        else:
            index = max(0, min(int(index), len(self.rows)))
            self.rows.insert(index, item)
        self.resequence()
        return index

    def update(self, index, row):
        current = self.rows[index]
        replacement = dict(row)
        replacement.setdefault(self.key, current.get(self.key))
        self.rows[index] = replacement
        self.resequence()
        return index

    def remove(self, index):
        row = self.rows[index]
        if self.protected(row):
            raise ValueError("This row is protected and cannot be deleted.")
        removed = self.rows.pop(index)
        self.resequence()
        return removed

    def move(self, index, offset):
        target = index + int(offset)
        if index < 0 or index >= len(self.rows) or target < 0 or target >= len(self.rows):
            return index
        self.rows[index], self.rows[target] = self.rows[target], self.rows[index]
        self.resequence()
        return target


class OrderedChildEditorDialog(wx.Dialog):
    """Standard Add/Edit/Delete/Move editor with application-supplied hooks."""

    def __init__(
        self, parent, *, title, rows, columns, create_item, edit_item,
        save_items, key="id", sequence="sequence", protected=None,
        instructions="",
    ):
        super().__init__(
            parent, title=title, size=(820, 560),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.columns = tuple(columns)
        self.create_item = create_item
        self.edit_item = edit_item
        self.save_items = save_items
        self.model = OrderedChildModel(
            rows, key=key, sequence=sequence, protected=protected,
        )
        self._build(instructions)
        self.refresh()
        self.CentreOnParent()

    def _build(self, instructions):
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        if instructions:
            help_text = wx.StaticText(panel, label=instructions)
            help_text.SetForegroundColour(wx.Colour(0, 90, 190))
            outer.Add(help_text, 0, wx.EXPAND | wx.ALL, 10)
        self.list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        for column in self.columns:
            self.list.AppendColumn(column.label, width=column.width)
        outer.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        actions = wx.BoxSizer(wx.HORIZONTAL)
        self.add_button = wx.Button(panel, label="Add...")
        self.edit_button = wx.Button(panel, label="Edit...")
        self.delete_button = wx.Button(panel, label="Delete")
        self.up_button = wx.Button(panel, label="Move Up")
        self.down_button = wx.Button(panel, label="Move Down")
        for button, handler in (
            (self.add_button, self.on_add), (self.edit_button, self.on_edit),
            (self.delete_button, self.on_delete), (self.up_button, lambda event: self.on_move(-1)),
            (self.down_button, lambda event: self.on_move(1)),
        ):
            button.Bind(wx.EVT_BUTTON, handler)
            actions.Add(button, 0, wx.RIGHT, 6)
        actions.AddStretchSpacer()
        save = wx.Button(panel, wx.ID_SAVE, "Save")
        cancel = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        save.Bind(wx.EVT_BUTTON, self.on_save)
        cancel.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CANCEL))
        actions.Add(save, 0, wx.RIGHT, 6)
        actions.Add(cancel)
        outer.Add(actions, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(outer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)
        self.SetMinSize((700, 420))
        self.SetSize((820, 560))
        self.behavior = ListCtrlBehavior(
            self.list, item_provider=lambda: self.model.rows,
            activate=self.on_edit, delete=self.on_delete,
            delete_allowed=lambda row: not self.model.protected(row),
            action_rules=(
                (self.edit_button, lambda _row: True),
                (self.delete_button, lambda row: not self.model.protected(row)),
                (self.up_button, lambda _row: self.list.GetFirstSelected() > 0),
                (self.down_button, lambda _row: 0 <= self.list.GetFirstSelected() < len(self.model.rows) - 1),
            ),
            key=lambda row: row.get(self.model.key),
        )

    def selected_index(self):
        return self.behavior.selected_index()

    def refresh(self, selected=None):
        remembered = self.behavior.selected_key() if selected is None else None
        self.list.DeleteAllItems()
        for row_number, row in enumerate(self.model.rows):
            values = [str(row.get(column.field, "") or "") for column in self.columns]
            item = self.list.InsertItem(row_number, values[0] if values else "")
            for column, value in enumerate(values[1:], 1):
                self.list.SetItem(item, column, value)
        if selected is not None and self.model.rows:
            selected = max(0, min(selected, len(self.model.rows) - 1))
            self.list.Select(selected)
            self.list.Focus(selected)
            self.list.EnsureVisible(selected)
            self.behavior.update_actions()
            return
        self.behavior.restore_selection(remembered)

    def on_add(self, _event):
        row = self.create_item(self)
        if row is not None:
            self.refresh(self.model.add(row))

    def on_edit(self, _event):
        index = self.selected_index()
        if index is None:
            return
        row = self.edit_item(self, dict(self.model.rows[index]))
        if row is not None:
            self.refresh(self.model.update(index, row))

    def on_delete(self, _event):
        index = self.selected_index()
        if index is None:
            return
        try:
            self.model.remove(index)
            self.refresh(min(index, len(self.model.rows) - 1))
        except ValueError as error:
            wx.MessageBox(str(error), "Protected row", wx.OK | wx.ICON_INFORMATION, self)

    def on_move(self, offset):
        index = self.selected_index()
        if index is not None:
            self.refresh(self.model.move(index, offset))

    def on_save(self, _event):
        try:
            self.save_items([dict(row) for row in self.model.rows])
            self.model.mark_saved()
            self.EndModal(wx.ID_SAVE)
        except Exception as error:
            wx.MessageBox(str(error), "Unable to save", wx.OK | wx.ICON_ERROR, self)
