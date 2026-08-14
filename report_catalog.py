"""Reusable, folder-backed catalog for user-editable visual reports."""

from copy import deepcopy
from pathlib import Path
import re
import shutil

import wx

from JSForm.report_definition import ReportDefinitionLoader, save_report_definition
from JSForm.list_behavior import ListCtrlBehavior
from JSForm.catalog_paths import CatalogDirectories


REPORT_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{1,63}$")


class ReportCatalogModel:
    def __init__(self, user_directory, starters, loader=None):
        self.user_directory = Path(user_directory)
        self.starters = Path(starters)
        self.loader = loader or ReportDefinitionLoader()
        self.directories = CatalogDirectories(self.user_directory, self.starters)

    def entries(self):
        self.user_directory.mkdir(parents=True, exist_ok=True)
        result = []
        names = {path.name for path in self.starters.glob("*.json")}
        names.update(path.name for path in self.user_directory.glob("*.json"))
        for filename in sorted(names, key=str.casefold):
            custom = self.user_directory / filename
            starter = self.starters / filename
            path = custom if custom.is_file() else starter
            try:
                path = self.directories.approved(path)
                definition = self.loader.load(path)
            except Exception:
                continue
            marker = custom.with_suffix(custom.suffix + ".custom")
            customized = custom.is_file() and (marker.is_file() or not starter.is_file())
            if custom.is_file() and starter.is_file() and not customized:
                try:
                    customized = definition.to_dict() != self.loader.load(starter).to_dict()
                except Exception:
                    customized = True
            result.append({
                "code": definition.report_id, "title": definition.title,
                "path": path, "has_starter": starter.is_file(),
                "customized": customized, "has_custom_file": custom.is_file(),
            })
        return result

    def open_customization(self, entry):
        source = self.directories.approved(entry["path"])
        target = self.directories.user_target(source.name)
        if not target.is_file():
            shutil.copyfile(source, target)
        self.loader.load(target)
        target.with_suffix(target.suffix + ".custom").write_text("", encoding="utf-8")
        return target

    def create_from(self, source, code, title):
        code = code.strip()
        title = title.strip()
        if not REPORT_CODE.fullmatch(code):
            raise ValueError("Report code must start with a letter and use only letters, numbers, dots, dashes, or underscores.")
        if not title:
            raise ValueError("Enter a report title.")
        source = self.directories.approved(source)
        target = self.directories.user_target(f"{code}.json")
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
        path = self.directories.user_file(path)
        path.unlink()
        backup = path.with_suffix(path.suffix + ".bak")
        if backup.exists():
            backup.unlink()
        marker = path.with_suffix(path.suffix + ".custom")
        if marker.exists():
            marker.unlink()

    def delete_customization(self, entry):
        path = self.directories.user_file(entry["path"])
        starter = self.starters / path.name
        if starter.is_file():
            if not entry.get("customized"):
                raise ValueError("This report is already using its starter definition.")
            self.delete(path)
            return "starter"
        self.delete(path)
        return "deleted"


class ReportCatalogDialog(wx.Dialog):
    def __init__(self, parent, model, open_handler):
        super().__init__(parent, title="Report Writer", size=(820, 540))
        self.model = model
        self.open_handler = open_handler
        layout = wx.BoxSizer(wx.VERTICAL)
        heading = wx.StaticText(self, label="Report Layouts")
        heading_font = heading.GetFont(); heading_font.SetPointSize(12); heading_font.SetWeight(wx.FONTWEIGHT_BOLD); heading.SetFont(heading_font)
        layout.Add(heading, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        legend = wx.StaticText(self, label="Blue items have a saved customization. Starter layouts remain available for recovery.")
        legend.SetForegroundColour(wx.Colour(0, 102, 204))
        layout.Add(legend, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 12)
        self.list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list.InsertColumn(0, "Report", width=130)
        self.list.InsertColumn(1, "Title", width=430)
        self.list.InsertColumn(2, "Status", width=120)
        layout.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        action_buttons = {}
        for label, handler in (
            ("Open Designer", self.on_open), ("New from Selected", self.on_new),
            ("Delete Customization", self.on_delete),
        ):
            button = wx.Button(self, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.RIGHT, 8)
            action_buttons[label] = button
        buttons.AddStretchSpacer()
        close = wx.Button(self, wx.ID_CLOSE, "Close")
        close.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CLOSE))
        buttons.Add(close, 0)
        layout.Add(buttons, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(layout)
        self.entries = []
        self.behavior = ListCtrlBehavior(
            self.list, item_provider=lambda: self.entries,
            activate=self.on_open, delete=self.on_delete,
            delete_allowed=lambda entry: entry["customized"] or not entry["has_starter"],
            sort=lambda _column, _ascending: self.refresh(), key=lambda entry: entry["code"],
            action_rules=(
                (action_buttons["Open Designer"], lambda _entry: True),
                (action_buttons["New from Selected"], lambda _entry: True),
                (action_buttons["Delete Customization"], lambda entry: entry["customized"] or not entry["has_starter"]),
            ),
        )
        self.refresh()

    def refresh(self):
        remembered = self.behavior.selected_key()
        self.entries = self.behavior.sorted(
            self.model.entries(),
            (lambda entry: entry["code"], lambda entry: entry["title"], lambda entry: "Customized" if entry["customized"] else "Starter"),
        )
        self.list.DeleteAllItems()
        for entry in self.entries:
            row = self.list.InsertItem(self.list.GetItemCount(), entry["code"])
            self.list.SetItem(row, 1, entry["title"])
            self.list.SetItem(row, 2, "Customized" if entry["customized"] else "Starter")
            if entry["customized"]:
                self.list.SetItemTextColour(row, wx.Colour(0, 102, 204))
        self.behavior.restore_selection(remembered)

    def selected(self):
        index = self.list.GetFirstSelected()
        return self.entries[index] if index != -1 else None

    def on_open(self, event):
        entry = self.selected()
        if entry:
            try:
                path = self.model.open_customization(entry)
            except Exception as error:
                wx.MessageBox(str(error), "Cannot customize report", wx.OK | wx.ICON_ERROR, self)
                return
            self.refresh()
            self.open_handler(path)

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
