"""Reusable interaction behavior for wx.ListCtrl catalog-style grids."""

from __future__ import annotations

from dataclasses import dataclass

import wx


@dataclass
class ListSortState:
    column: int | None = None
    ascending: bool = True

    def select(self, column):
        column = int(column)
        if self.column == column:
            self.ascending = not self.ascending
        else:
            self.column = column
            self.ascending = True
        return self.column, self.ascending


class ListCtrlBehavior:
    """Give a report-style ListCtrl consistent keyboard and mouse behavior."""

    def __init__(
        self, control, *, item_provider, activate=None, delete=None,
        sort=None, action_rules=(), key=None, delete_allowed=None,
    ):
        self.control = control
        self.item_provider = item_provider
        self.activate = activate
        self.delete = delete
        self.delete_allowed = delete_allowed or (lambda _item: True)
        self.sort = sort
        self.action_rules = tuple(action_rules)
        self.key = key or (lambda item: item)
        self.sort_state = ListSortState()
        control.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_selection)
        control.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_selection)
        control.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_activate)
        control.Bind(wx.EVT_LIST_COL_CLICK, self._on_column)
        control.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.update_actions()

    def selected_index(self):
        index = self.control.GetFirstSelected()
        return index if index >= 0 else None

    def selected_item(self):
        index = self.selected_index()
        items = self.item_provider()
        return items[index] if index is not None and index < len(items) else None

    def selected_key(self):
        item = self.selected_item()
        return None if item is None else self.key(item)

    def sorted(self, items, column_keys):
        rows = list(items)
        if self.sort_state.column is None:
            return rows
        key = column_keys[self.sort_state.column]

        def normalized(item):
            value = key(item)
            if value is None:
                return ""
            return value.casefold() if isinstance(value, str) else value

        return sorted(rows, key=normalized, reverse=not self.sort_state.ascending)

    def restore_selection(self, remembered=None, default_first=True):
        items = self.item_provider()
        target = None
        if remembered is not None:
            target = next((index for index, item in enumerate(items) if self.key(item) == remembered), None)
        if target is None and default_first and items:
            target = 0
        if target is not None:
            self.control.Select(target)
            self.control.Focus(target)
            self.control.EnsureVisible(target)
        self.update_actions()

    def update_actions(self):
        item = self.selected_item()
        for control, predicate in self.action_rules:
            control.Enable(item is not None and bool(predicate(item)))

    def _on_selection(self, event):
        self.update_actions()
        event.Skip()

    def _on_activate(self, event):
        if self.activate and self.selected_item() is not None:
            self.activate(event)
        else:
            event.Skip()

    def _on_column(self, event):
        if self.sort:
            column, ascending = self.sort_state.select(event.GetColumn())
            self.sort(column, ascending)
        else:
            event.Skip()

    def _on_key(self, event):
        if event.GetKeyCode() in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            item = self.selected_item()
            if self.delete and item is not None and self.delete_allowed(item):
                self.delete(event)
                return
        event.Skip()
