"""Safe maintenance UI for JSForm's shared choice catalogs."""

from __future__ import annotations

import json
import re

import wx

from JSForm.clsChoice import parse_choice_values
from JSForm.list_behavior import ListCtrlBehavior


FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalized_choices(values):
    result = []
    seen = set()
    for raw in values:
        value = str(raw).strip()
        key = value.casefold()
        if value and key not in seen:
            result.append(value)
            seen.add(key)
    if not result:
        raise ValueError("Enter at least one choice.")
    return result


class ChoiceCatalogRepository:
    def __init__(self, connection, protected_fields=()):
        self.connection = connection
        self.protected_fields = frozenset(protected_fields)

    def _cursor(self):
        cursor = self.connection.cursor()
        marker = "%s" if cursor.__class__.__module__.startswith("mysql.connector") else "?"
        return cursor, marker

    def rows(self):
        cursor, _marker = self._cursor()
        try:
            cursor.execute("SELECT ID,Field,Choices,COALESCE(Note,'') FROM tblChoices ORDER BY Field,ID")
            return cursor.fetchall()
        finally:
            cursor.close()

    def save(self, item_id, original_field, field, values, note):
        field = str(field or "").strip()
        if not FIELD_NAME.fullmatch(field):
            raise ValueError("The field name may contain only letters, numbers, and underscores.")
        if item_id is not None and field != original_field:
            raise ValueError("An existing choice field cannot be renamed. Create a new list instead.")
        serialized = json.dumps(normalized_choices(values), ensure_ascii=False, separators=(",", ":"))
        cursor, marker = self._cursor()
        try:
            if item_id is None:
                cursor.execute(
                    f"INSERT INTO tblChoices (Field,Choices,Note) VALUES ({marker},{marker},{marker})",
                    (field, serialized, note or None),
                )
            else:
                cursor.execute(
                    f"UPDATE tblChoices SET Choices={marker},Note={marker} WHERE ID={marker}",
                    (serialized, note or None, item_id),
                )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def delete(self, item_id, field):
        if field in self.protected_fields:
            raise ValueError(f"{field} is used by an active screen and cannot be deleted.")
        cursor, marker = self._cursor()
        try:
            cursor.execute(f"DELETE FROM tblChoices WHERE ID={marker}", (item_id,))
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()


class ChoiceEditDialog(wx.Dialog):
    def __init__(self, parent, row=None):
        super().__init__(parent, title="Choice List", size=(570, 560), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.row = row
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        form = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        form.AddGrowableCol(1, 1)
        self.field = wx.TextCtrl(panel, value=str(row[1]) if row else "")
        self.field.SetEditable(row is None)
        form.Add(wx.StaticText(panel, label="Field:"), 0, wx.ALIGN_CENTER_VERTICAL)
        form.Add(self.field, 1, wx.EXPAND)
        outer.Add(form, 0, wx.EXPAND | wx.ALL, 12)
        outer.Add(wx.StaticText(panel, label="Choices (one per line):"), 0, wx.LEFT | wx.RIGHT, 12)
        self.values = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_DONTWRAP)
        if row:
            self.values.SetValue("\r\n".join(parse_choice_values(row[2])))
        outer.Add(self.values, 1, wx.EXPAND | wx.ALL, 12)
        outer.Add(wx.StaticText(panel, label="Note:"), 0, wx.LEFT | wx.RIGHT, 12)
        self.note = wx.TextCtrl(panel, value=str(row[3] or "") if row else "", style=wx.TE_MULTILINE)
        self.note.SetMinSize((-1, 90))
        outer.Add(self.note, 0, wx.EXPAND | wx.ALL, 12)
        buttons = wx.StdDialogButtonSizer()
        for button_id in (wx.ID_OK, wx.ID_CANCEL):
            buttons.AddButton(wx.Button(panel, button_id))
        buttons.Realize()
        outer.Add(buttons, 0, wx.EXPAND | wx.ALL, 12)
        panel.SetSizer(outer)

    def result(self):
        return self.field.GetValue(), self.values.GetValue().splitlines(), self.note.GetValue().strip()


class ChoiceManagerDialog(wx.Dialog):
    def __init__(self, parent, connection, protected_fields=()):
        super().__init__(parent, title="Choices", size=(820, 590), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.repository = ChoiceCatalogRepository(connection, protected_fields)
        self.rows_data = []
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        message = wx.StaticText(panel, label="Choice lists control dropdowns throughout the program. Double-click a list to edit it.")
        message.SetForegroundColour(wx.Colour(0, 90, 190))
        outer.Add(message, 0, wx.ALL, 10)
        legend = wx.StaticText(panel, label="Blue rows are custom choice lists that are not currently used by a screen.")
        legend.SetForegroundColour(wx.Colour(0, 102, 204))
        outer.Add(legend, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.grid = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.grid.AppendColumn("Field", width=210)
        self.grid.AppendColumn("Choices", width=390)
        self.grid.AppendColumn("Status", width=130)
        outer.Add(self.grid, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        actions = wx.BoxSizer(wx.HORIZONTAL)
        action_buttons = {}
        for label, handler in (("Add...", self.on_add), ("Edit...", self.on_edit), ("Delete", self.on_delete)):
            button = wx.Button(panel, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            actions.Add(button, 0, wx.RIGHT, 8)
            action_buttons[label] = button
        actions.AddStretchSpacer()
        actions.Add(wx.Button(panel, wx.ID_CANCEL, "Close"))
        outer.Add(actions, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(outer)
        self.behavior = ListCtrlBehavior(
            self.grid, item_provider=lambda: self.rows_data,
            activate=self.on_edit, delete=self.on_delete,
            delete_allowed=lambda row: row[1] not in self.repository.protected_fields,
            sort=lambda _column, _ascending: self.refresh(), key=lambda row: row[0],
            action_rules=(
                (action_buttons["Edit..."], lambda _row: True),
                (action_buttons["Delete"], lambda row: row[1] not in self.repository.protected_fields),
            ),
        )
        self.refresh()

    def refresh(self):
        remembered = self.behavior.selected_key()
        self.rows_data = self.behavior.sorted(
            self.repository.rows(),
            (lambda row: row[1], lambda row: ", ".join(parse_choice_values(row[2])), lambda row: row[1] in self.repository.protected_fields),
        )
        self.grid.DeleteAllItems()
        for index, row in enumerate(self.rows_data):
            values = parse_choice_values(row[2])
            item = self.grid.InsertItem(index, str(row[1]))
            self.grid.SetItem(item, 1, ", ".join(values))
            protected = row[1] in self.repository.protected_fields
            self.grid.SetItem(item, 2, "Used by screens" if protected else "Custom choice list")
            if not protected:
                self.grid.SetItemTextColour(item, wx.Colour(0, 102, 204))
        self.behavior.restore_selection(remembered)

    def selected(self):
        index = self.grid.GetFirstSelected()
        return self.rows_data[index] if index >= 0 else None

    def edit(self, row):
        dialog = ChoiceEditDialog(self, row)
        try:
            if dialog.ShowModal() == wx.ID_OK:
                field, values, note = dialog.result()
                self.repository.save(row[0] if row else None, row[1] if row else None, field, values, note)
                self.refresh()
                wx.MessageBox("Choices saved. Reopen affected screens to load the updated list.", "Choices", wx.OK | wx.ICON_INFORMATION, self)
        except Exception as error:
            wx.MessageBox(str(error), "Unable to Save Choices", wx.OK | wx.ICON_ERROR, self)
        finally:
            dialog.Destroy()

    def on_add(self, _event):
        self.edit(None)

    def on_edit(self, _event):
        row = self.selected()
        if row:
            self.edit(row)

    def on_delete(self, _event):
        row = self.selected()
        if not row:
            return
        try:
            if wx.MessageBox(f"Delete the custom choice list {row[1]}?", "Delete Choice List", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self) == wx.YES:
                self.repository.delete(row[0], row[1])
                self.refresh()
        except Exception as error:
            wx.MessageBox(str(error), "Protected Choice List", wx.OK | wx.ICON_INFORMATION, self)


def show_choice_manager(parent, connection, protected_fields=()):
    dialog = ChoiceManagerDialog(parent, connection, protected_fields)
    try:
        return dialog.ShowModal()
    finally:
        dialog.Destroy()
