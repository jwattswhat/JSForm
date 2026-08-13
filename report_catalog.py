"""Reusable, folder-backed catalog for user-editable visual reports."""

from copy import deepcopy
from pathlib import Path
import re

import wx

from JSForm.report_definition import ReportDefinitionLoader, save_report_definition


REPORT_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{1,63}$")


class ReportCatalogModel:
    def __init__(self, user_directory, starters, loader=None):
        self.user_directory = Path(user_directory)
        self.starters = Path(starters)
        self.loader = loader or ReportDefinitionLoader()

    def entries(self):
        self.user_directory.mkdir(parents=True, exist_ok=True)
        result = []
        for path in sorted(self.user_directory.glob("*.json")):
            try:
                definition = self.loader.load(path)
            except Exception:
                continue
            starter = self.starters / path.name
            customized = not starter.is_file()
            if starter.is_file():
                try:
                    customized = definition.to_dict() != self.loader.load(starter).to_dict()
                except Exception:
                    customized = True
            result.append({
                "code": definition.report_id, "title": definition.title,
                "path": path, "has_starter": starter.is_file(),
                "customized": customized,
            })
        return result

    def create_from(self, source, code, title):
        code = code.strip()
        title = title.strip()
        if not REPORT_CODE.fullmatch(code):
            raise ValueError("Report code must start with a letter and use only letters, numbers, dots, dashes, or underscores.")
        if not title:
            raise ValueError("Enter a report title.")
        target = self.user_directory / f"{code}.json"
        if target.exists():
            raise ValueError(f"A report named {code} already exists.")
        definition = self.loader.load(source)
        data = definition.to_dict()
        old_root = definition.root_name
        root = data.pop(old_root)
        root["REPORT"]["name"] = code
        root["REPORT"]["title"] = title
        created = self.loader.from_dict({f"{code}REPORT": root})
        save_report_definition(created, target)
        return target

    def delete(self, path):
        path = Path(path)
        if path.parent.resolve() != self.user_directory.resolve():
            raise ValueError("Only user report definitions can be deleted.")
        path.unlink()
        backup = path.with_suffix(path.suffix + ".bak")
        if backup.exists():
            backup.unlink()

    def delete_customization(self, entry):
        path = Path(entry["path"])
        if path.parent.resolve() != self.user_directory.resolve():
            raise ValueError("Only user report definitions can be deleted.")
        starter = self.starters / path.name
        if starter.is_file():
            if not entry.get("customized"):
                raise ValueError("This report is already using its starter definition.")
            definition = self.loader.load(starter)
            save_report_definition(definition, path)
            backup = path.with_suffix(path.suffix + ".bak")
            if backup.exists():
                backup.unlink()
            return "starter"
        self.delete(path)
        return "deleted"


class ReportCatalogDialog(wx.Dialog):
    def __init__(self, parent, model, open_handler):
        super().__init__(parent, title="Report Writer", size=(720, 470))
        self.model = model
        self.open_handler = open_handler
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self, label="Reports"), 0, wx.ALL, 10)
        self.list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list.InsertColumn(0, "Report", width=130)
        self.list.InsertColumn(1, "Title", width=350)
        self.list.InsertColumn(2, "Status", width=120)
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_open)
        layout.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in (
            ("Open Designer", self.on_open), ("New from Selected", self.on_new),
            ("Delete Customization", self.on_delete),
        ):
            button = wx.Button(self, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.RIGHT, 8)
        buttons.AddStretchSpacer()
        close = wx.Button(self, wx.ID_CLOSE, "Close")
        close.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CLOSE))
        buttons.Add(close, 0)
        layout.Add(buttons, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(layout)
        self.refresh()

    def refresh(self):
        self.entries = self.model.entries()
        self.list.DeleteAllItems()
        for entry in self.entries:
            row = self.list.InsertItem(self.list.GetItemCount(), entry["code"])
            self.list.SetItem(row, 1, entry["title"])
            self.list.SetItem(row, 2, "Customized" if entry["customized"] else "Starter")
            if entry["customized"]:
                self.list.SetItemTextColour(row, wx.Colour(0, 102, 204))
        if self.entries:
            self.list.Select(0)

    def selected(self):
        index = self.list.GetFirstSelected()
        return self.entries[index] if index != -1 else None

    def on_open(self, event):
        entry = self.selected()
        if entry:
            self.open_handler(entry["path"])

    def on_new(self, event):
        entry = self.selected()
        if not entry:
            return
        code_dialog = wx.TextEntryDialog(self, "Enter a short report code.", "New Report")
        try:
            if code_dialog.ShowModal() != wx.ID_OK:
                return
            code = code_dialog.GetValue()
        finally:
            code_dialog.Destroy()
        title_dialog = wx.TextEntryDialog(self, "Enter the report title.", "New Report")
        try:
            if title_dialog.ShowModal() != wx.ID_OK:
                return
            title = title_dialog.GetValue()
        finally:
            title_dialog.Destroy()
        try:
            self.model.create_from(entry["path"], code, title)
        except ValueError as error:
            wx.MessageBox(str(error), "Cannot create report", wx.OK | wx.ICON_ERROR, self)
            return
        self.refresh()

    def on_delete(self, event):
        entry = self.selected()
        if not entry:
            return
        if entry["has_starter"] and not entry["customized"]:
            wx.MessageBox("This report is already using its starter definition.", "No customization", wx.OK | wx.ICON_INFORMATION, self)
            return
        message = (
            f"Delete the customization for {entry['title']} and return to its starter?"
            if entry["has_starter"] else f"Permanently delete {entry['title']}?"
        )
        if wx.MessageBox(
            message, "Delete customization",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self,
        ) != wx.YES:
            return
        self.model.delete_customization(entry)
        self.refresh()


def open_report_catalog(user_directory, starters, open_handler, parent=None):
    dialog = ReportCatalogDialog(
        parent, ReportCatalogModel(user_directory, starters), open_handler,
    )
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()
