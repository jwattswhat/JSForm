"""Reusable catalog for approved, user-editable JSForm screens."""

from pathlib import Path
import re

import wx

from JSForm.screen_definition import (
    ScreenDefinitionLoader, save_screen_definition, screen_definitions_equal,
)
from JSForm.list_behavior import ListCtrlBehavior


SCREEN_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,63}$")


def display_screen_title(form_name, title):
    """Remove a technical form-name prefix from a user-facing catalog title."""
    title = str(title or form_name).strip()
    match = re.match(r"^frm[A-Za-z0-9_]+\s*:\s*(.+)$", title, re.IGNORECASE)
    return match.group(1).strip() if match else title


class ScreenCatalogModel:
    def __init__(self, user_directory, starters, loader=None):
        self.user_directory = Path(user_directory)
        self.starters = Path(starters)
        self.loader = loader or ScreenDefinitionLoader()

    def entries(self):
        self.user_directory.mkdir(parents=True, exist_ok=True)
        names = {path.name for path in self.starters.glob("*.json")}
        names.update(path.name for path in self.user_directory.glob("*.json"))
        result = []
        for filename in sorted(names, key=str.casefold):
            custom = self.user_directory / filename
            starter = self.starters / filename
            selected = custom if custom.is_file() else starter
            try:
                definition = self.loader.load(selected)
            except Exception:
                continue
            customized = custom.is_file() and not starter.is_file()
            if custom.is_file() and starter.is_file():
                try:
                    customized = not screen_definitions_equal(
                        definition, self.loader.load(starter), ignore_theme=True,
                    )
                except Exception:
                    customized = True
            result.append({
                "name": definition.form_name,
                "title": display_screen_title(
                    definition.form_name,
                    definition.form.get("title", definition.form_name),
                ),
                "type": definition.form.get("type", "Panel"),
                "path": selected,
                "starter": starter if starter.is_file() else None,
                "customized": customized,
                "has_custom_file": custom.is_file(),
            })
        return result

    def create_from(self, source, name, title):
        name = name.strip()
        title = title.strip()
        if not SCREEN_NAME.fullmatch(name):
            raise ValueError("Screen name must start with a letter and use only letters, numbers, or underscores.")
        if not title:
            raise ValueError("Enter a screen title.")
        target = self.user_directory / "{}.json".format(name)
        if target.exists() or (self.starters / target.name).exists():
            raise ValueError("A screen named {} already exists.".format(name))
        source_definition = self.loader.load(source)
        data = source_definition.to_dict()
        root = data.pop(source_definition.root_name)
        root["FORM"]["name"] = name
        root["FORM"]["title"] = title
        created = self.loader.from_dict({name + "FORM": root}, name)
        save_screen_definition(created, target)
        return target

    def delete_customization(self, name):
        path = self.user_directory / "{}.json".format(name)
        if not path.is_file():
            raise ValueError("This screen has no user customization to remove.")
        path.unlink()
        backup = path.with_suffix(path.suffix + ".bak")
        if backup.exists():
            backup.unlink()


class ScreenCatalogDialog(wx.Dialog):
    def __init__(self, parent, model, open_handler):
        super().__init__(parent, title="Screen Designer", size=(840, 560))
        self.model = model
        self.open_handler = open_handler
        root = wx.BoxSizer(wx.VERTICAL)
        heading = wx.StaticText(self, label="ChurchManager Screen Layouts")
        heading_font = heading.GetFont(); heading_font.SetPointSize(12); heading_font.SetWeight(wx.FONTWEIGHT_BOLD); heading.SetFont(heading_font)
        root.Add(heading, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        legend = wx.StaticText(self, label="Blue items have a saved customization. Starter screens remain available for recovery.")
        legend.SetForegroundColour(wx.Colour(0, 102, 204))
        root.Add(legend, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 12)
        self.list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        for index, (label, width) in enumerate((("Screen", 160), ("Title", 440), ("Status", 130))):
            self.list.InsertColumn(index, label, width=width)
        root.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        action_buttons = {}
        for label, handler in (("Open Designer", self.on_open), ("New from Selected", self.on_new), ("Delete Custom", self.on_restore)):
            button = wx.Button(self, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.RIGHT, 8)
            action_buttons[label] = button
        buttons.AddStretchSpacer()
        close = wx.Button(self, wx.ID_CLOSE, "Close")
        close.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CLOSE))
        buttons.Add(close)
        root.Add(buttons, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(root)
        self.entries = []
        self.behavior = ListCtrlBehavior(
            self.list, item_provider=lambda: self.entries,
            activate=self.on_open, delete=self.on_restore,
            delete_allowed=lambda entry: entry["customized"],
            sort=lambda _column, _ascending: self.refresh(), key=lambda entry: entry["name"],
            action_rules=(
                (action_buttons["Open Designer"], lambda _entry: True),
                (action_buttons["New from Selected"], lambda _entry: True),
                (action_buttons["Delete Custom"], lambda entry: entry["customized"]),
            ),
        )
        self.refresh()

    def refresh(self, preferred_name=None):
        remembered = preferred_name or self.behavior.selected_key()
        self.entries = self.behavior.sorted(
            self.model.entries(),
            (lambda entry: entry["name"], lambda entry: entry["title"], lambda entry: "Customized" if entry["customized"] else "Starter"),
        )
        self.list.DeleteAllItems()
        for entry in self.entries:
            row = self.list.InsertItem(self.list.GetItemCount(), entry["name"])
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
        if entry: self.open_handler(entry)

    def on_new(self, event):
        entry = self.selected()
        if not entry: return
        name_dialog = wx.TextEntryDialog(self, "Enter the new screen name.", "New Screen")
        try:
            if name_dialog.ShowModal() != wx.ID_OK: return
            name = name_dialog.GetValue()
        finally: name_dialog.Destroy()
        title_dialog = wx.TextEntryDialog(self, "Enter the screen title.", "New Screen")
        try:
            if title_dialog.ShowModal() != wx.ID_OK: return
            title = title_dialog.GetValue()
        finally: title_dialog.Destroy()
        try: self.model.create_from(entry["path"], name, title)
        except ValueError as error: wx.MessageBox(str(error), "Cannot create screen", wx.OK | wx.ICON_ERROR, self); return
        self.refresh(name.strip())

    def on_restore(self, event):
        entry = self.selected()
        if not entry or not entry["customized"]: return
        if wx.MessageBox("Delete this customization and return to the shipped starter?", "Delete Customization", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES: return
        self.model.delete_customization(entry["name"])
        self.refresh()


def open_screen_catalog(user_directory, starters, open_handler, parent=None):
    dialog = ScreenCatalogDialog(parent, ScreenCatalogModel(user_directory, starters), open_handler)
    try: dialog.ShowModal()
    finally: dialog.Destroy()
