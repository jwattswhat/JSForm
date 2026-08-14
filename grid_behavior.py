"""Reusable interaction behavior for wx.Grid data and checkbox tables."""

from __future__ import annotations

import wx
import wx.grid

from JSForm.list_behavior import ListSortState


def grid_checked(value):
    """Return the semantic checked state used by wx.Grid Boolean cells."""
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


class GridBehavior:
    """Give wx.Grid tables the same selection and action contract as lists."""

    def __init__(
        self, control, *, item_provider, checkbox_columns=(), activate=None,
        delete=None, sort=None, changed=None, action_rules=(), key=None,
        delete_allowed=None,
    ):
        self.control = control
        self.item_provider = item_provider
        self.checkbox_columns = frozenset(int(column) for column in checkbox_columns)
        self.activate = activate
        self.delete = delete
        self.sort = sort
        self.changed = changed
        self.action_rules = tuple(action_rules)
        self.key = key or (lambda item: item)
        self.delete_allowed = delete_allowed or (lambda _item: True)
        self.sort_state = ListSortState()
        control.Bind(wx.grid.EVT_GRID_SELECT_CELL, self._on_selection)
        control.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self._on_cell_click)
        control.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self._on_activate)
        control.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self._on_label_click)
        control.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.update_actions()

    def selected_row(self):
        row = self.control.GetGridCursorRow()
        return row if 0 <= row < len(self.item_provider()) else None

    def selected_item(self):
        row = self.selected_row()
        return None if row is None else self.item_provider()[row]

    def selected_key(self):
        item = self.selected_item()
        return None if item is None else self.key(item)

    def remembered_state(self):
        view = self.control.GetViewStart() if hasattr(self.control, "GetViewStart") else (0, 0)
        return self.selected_key(), tuple(view)

    def restore_state(self, state=None, default_first=True):
        remembered, view = state or (None, (0, 0))
        items = self.item_provider()
        row = None
        if remembered is not None:
            row = next((i for i, item in enumerate(items) if self.key(item) == remembered), None)
        if row is None and default_first and items:
            row = 0
        if row is not None:
            column = max(0, self.control.GetGridCursorCol())
            self.control.SetGridCursor(row, column)
            self.control.MakeCellVisible(row, column)
        if hasattr(self.control, "Scroll"):
            self.control.Scroll(*view)
        self.update_actions()

    def toggle(self, row, column):
        checked = not grid_checked(self.control.GetCellValue(row, column))
        self.control.SetCellValue(row, column, "1" if checked else "")
        if self.changed:
            self.changed(row, column, checked)
        return checked

    def update_actions(self):
        item = self.selected_item()
        for control, predicate in self.action_rules:
            control.Enable(item is not None and bool(predicate(item)))

    def _on_selection(self, event):
        self.update_actions()
        event.Skip()

    def _on_cell_click(self, event):
        row, column = event.GetRow(), event.GetCol()
        if row >= 0 and column in self.checkbox_columns:
            self.control.SetGridCursor(row, column)
            self.toggle(row, column)
            self.update_actions()
            return
        event.Skip()

    def _on_activate(self, event):
        if event.GetCol() in self.checkbox_columns:
            event.Skip()
        elif self.activate and self.selected_item() is not None:
            self.activate(event)
        else:
            event.Skip()

    def _on_label_click(self, event):
        column = event.GetCol()
        if column >= 0 and self.sort:
            selected, view = self.remembered_state()
            column, ascending = self.sort_state.select(column)
            self.sort(column, ascending)
            self.restore_state((selected, view))
        else:
            event.Skip()

    def _on_key(self, event):
        if event.GetKeyCode() in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            item = self.selected_item()
            if self.delete and item is not None and self.delete_allowed(item):
                self.delete(event)
                return
        event.Skip()
