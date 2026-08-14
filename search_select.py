"""Reusable search, filter, sort, and stable-ID selection dialog."""

from __future__ import annotations

from dataclasses import dataclass

import wx

from JSForm.list_behavior import ListCtrlBehavior
from JSForm.conditional_formatting import StatusSummaryCtrl, StatusSummaryItem


@dataclass(frozen=True)
class SearchSelectColumn:
    label: str
    field: str
    width: int = 150


@dataclass(frozen=True)
class SearchSelectFilter:
    label: str
    field: str
    choices: tuple
    all_label: str = "All"


class SearchSelectModel:
    def __init__(self, rows, *, key="id", search_fields=()):
        self.rows = [dict(row) for row in rows]
        self.key = key
        self.search_fields = tuple(search_fields)

    def matching(self, query="", filters=None):
        terms = query.strip().casefold().split()
        filters = filters or {}
        result = []
        for row in self.rows:
            searchable = " ".join(str(row.get(field, "") or "") for field in self.search_fields).casefold()
            if terms and not all(term in searchable for term in terms):
                continue
            if any(value not in (None, "") and row.get(field) != value for field, value in filters.items()):
                continue
            result.append(row)
        return result

    @staticmethod
    def sorted(rows, field, ascending=True):
        def value(row):
            item = row.get(field)
            if item is None:
                return ""
            return item.casefold() if isinstance(item, str) else item
        return sorted(rows, key=value, reverse=not ascending)


class SearchSelectDialog(wx.Dialog):
    def __init__(
        self, parent, *, title, rows, columns, search_fields=(), filters=(),
        key="id", multiple=False, instructions="",
    ):
        super().__init__(
            parent, title=title, size=(820, 560),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.columns = tuple(columns)
        self.filters = tuple(filters)
        self.model = SearchSelectModel(rows, key=key, search_fields=search_fields)
        self.visible_rows = []
        self._selected_ids = []
        self._build(multiple, instructions)
        self.refresh()
        self.CentreOnParent()

    def _build(self, multiple, instructions):
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        if instructions:
            helper = wx.StaticText(panel, label=instructions)
            helper.SetForegroundColour(wx.Colour(0, 90, 190))
            outer.Add(helper, 0, wx.EXPAND | wx.ALL, 10)
        criteria = wx.BoxSizer(wx.HORIZONTAL)
        criteria.Add(wx.StaticText(panel, label="Find:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.search = wx.TextCtrl(panel)
        self.search.Bind(wx.EVT_TEXT, lambda _event: self.refresh())
        criteria.Add(self.search, 1, wx.RIGHT, 12)
        self.filter_controls = {}
        for definition in self.filters:
            criteria.Add(wx.StaticText(panel, label=definition.label + ":"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            choice = wx.Choice(panel, choices=[definition.all_label] + [str(value) for value in definition.choices])
            choice.SetSelection(0)
            choice.Bind(wx.EVT_CHOICE, lambda _event: self.refresh())
            criteria.Add(choice, 0, wx.RIGHT, 12)
            self.filter_controls[definition.field] = (choice, definition)
        outer.Add(criteria, 0, wx.EXPAND | wx.ALL, 10)
        self.summary = StatusSummaryCtrl(panel)
        outer.Add(self.summary, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        style = wx.LC_REPORT
        if not multiple:
            style |= wx.LC_SINGLE_SEL
        self.list = wx.ListCtrl(panel, style=style)
        for column in self.columns:
            self.list.AppendColumn(column.label, width=column.width)
        outer.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.AddStretchSpacer()
        select = wx.Button(panel, wx.ID_OK, "Select")
        cancel = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        select.Bind(wx.EVT_BUTTON, self.on_select)
        cancel.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CANCEL))
        buttons.Add(select, 0, wx.RIGHT, 6)
        buttons.Add(cancel)
        outer.Add(buttons, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(outer)
        frame = wx.BoxSizer(wx.VERTICAL)
        frame.Add(panel, 1, wx.EXPAND)
        self.SetSizer(frame)
        self.SetMinSize((680, 420))
        self.behavior = ListCtrlBehavior(
            self.list, item_provider=lambda: self.visible_rows,
            activate=self.on_select, sort=self.on_sort,
            key=lambda row: row.get(self.model.key),
        )

    def active_filters(self):
        values = {}
        for field, (control, definition) in self.filter_controls.items():
            selection = control.GetSelection()
            values[field] = None if selection <= 0 else definition.choices[selection - 1]
        return values

    def refresh(self, remembered=None):
        if remembered is None:
            remembered = self.behavior.selected_key()
        self.visible_rows = self.model.matching(self.search.GetValue(), self.active_filters())
        state = self.behavior.sort_state
        if state.column is not None and state.column < len(self.columns):
            self.visible_rows = self.model.sorted(
                self.visible_rows, self.columns[state.column].field, state.ascending,
            )
        self.list.DeleteAllItems()
        for row_number, row in enumerate(self.visible_rows):
            values = [str(row.get(column.field, "") or "") for column in self.columns]
            item = self.list.InsertItem(row_number, values[0] if values else "")
            for column, value in enumerate(values[1:], 1):
                self.list.SetItem(item, column, value)
        self.summary.set_items((
            StatusSummaryItem(
                "Results", len(self.visible_rows),
                "normal" if self.visible_rows else "warning",
            ),
        ))
        self.behavior.restore_selection(remembered)

    def on_sort(self, _column, _ascending):
        self.refresh()

    def on_select(self, _event):
        selected = []
        row = -1
        while True:
            row = self.list.GetNextItem(row, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
            if row < 0:
                break
            selected.append(self.visible_rows[row].get(self.model.key))
        if selected:
            self._selected_ids = selected
            self.EndModal(wx.ID_OK)

    def selected_ids(self):
        return list(self._selected_ids)

    def selected_id(self):
        return self._selected_ids[0] if self._selected_ids else None
