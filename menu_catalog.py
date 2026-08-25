"""Safe starter and customization catalog for JSForm application menus."""

from __future__ import annotations

from pathlib import Path
import re
import shutil

import wx

from JSForm.catalog_paths import CatalogDirectories
from JSForm.menu_definition import MenuDefinitionLoader, save_menu_definition
from JSForm.window_icons import apply_window_icon


MENU_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class MenuCatalogModel:
    """List and manage protected starters and separate user menu files."""

    def __init__(self, user_directory, starters, loader=None):
        self.user_directory = Path(user_directory)
        self.starters = Path(starters)
        self.loader = loader or MenuDefinitionLoader()
        self.directories = CatalogDirectories(self.user_directory, self.starters)

    def entries(self):
        """Return deterministic valid and invalid menu catalog entries."""
        self.user_directory.mkdir(parents=True, exist_ok=True)
        names = {path.name for path in self.starters.glob("*.json")}
        names.update(path.name for path in self.user_directory.glob("*.json"))
        result = []
        for filename in sorted(names, key=str.casefold):
            custom = self.user_directory / filename
            starter = self.starters / filename
            selected = custom if custom.is_file() else starter
            try:
                selected = self.directories.approved(selected)
                definition = self.loader.load(selected, customized=custom.is_file())
                result.append({
                    "name": definition.name,
                    "filename": filename,
                    "path": selected,
                    "starter": starter if starter.is_file() else None,
                    "customized": custom.is_file(),
                    "valid": True,
                    "error": "",
                    "modified": selected.stat().st_mtime,
                })
            except Exception as error:
                result.append({
                    "name": Path(filename).stem,
                    "filename": filename,
                    "path": selected,
                    "starter": starter if starter.is_file() else None,
                    "customized": custom.is_file(),
                    "valid": False,
                    "error": str(error),
                    "modified": selected.stat().st_mtime if selected.exists() else 0,
                })
        return result

    def open_customization(self, entry):
        """Create and validate a user copy without changing its starter."""
        source = self.directories.approved(entry["path"])
        target = self.directories.user_target(source.name)
        if not target.is_file():
            shutil.copyfile(source, target)
        return target

    def create_from(self, source, name, filename=None):
        """Create a renamed custom definition from an approved source."""
        name = str(name or "").strip()
        if not MENU_NAME.fullmatch(name):
            raise ValueError(
                "Menu name must start with a lowercase letter and use only "
                "lowercase letters, numbers, underscores, or dashes."
            )
        filename = filename or "{}.menu.json".format(name)
        source = self.directories.approved(source)
        target = self.directories.user_target(filename)
        if target.exists() or (self.starters / target.name).exists():
            raise ValueError("A menu definition named {} already exists.".format(target.name))
        data = self.loader.load(source).to_dict()
        data["name"] = name
        save_menu_definition(self.loader.from_dict(data), target, loader=self.loader)
        return target

    def save(self, definition, target):
        """Save a validated definition only inside the user directory."""
        target = self.directories.user_file(target, must_exist=False)
        return save_menu_definition(definition, target, loader=self.loader)

    def load_starter(self, entry):
        """Load the protected starter for an entry without changing disk."""
        starter = entry.get("starter")
        if starter is None:
            raise ValueError("This menu definition has no starter.")
        return self.loader.load(self.directories.approved(starter))

    def load_previous(self, entry):
        """Load the previous valid user definition without changing disk."""
        path = self.directories.user_file(entry["path"])
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.is_file():
            raise ValueError("This menu definition has no previous version.")
        # The backup extension is intentionally outside CatalogDirectories'
        # editable suffix contract; it is read only after its user path is proven.
        return self.loader.load(backup, customized=True)

    def delete_customization(self, entry):
        """Delete one user customization and its retained previous version."""
        path = self.directories.user_file(entry["path"])
        path.unlink()
        backup = path.with_suffix(path.suffix + ".bak")
        if backup.exists():
            backup.unlink()
        return "starter" if entry.get("starter") else "deleted"


class MenuCatalogDialog(wx.Dialog):
    """Catalog window for protected starter and user menu definitions."""

    def __init__(self, parent, model, open_handler):
        super().__init__(parent, title="Menu Designer", size=(860, 560))
        apply_window_icon(self)
        self.model = model
        self.open_handler = open_handler
        self.rows = []
        root = wx.BoxSizer(wx.VERTICAL)
        heading = wx.StaticText(self, label="Application Menus")
        font = heading.GetFont(); font.SetPointSize(12); font.SetWeight(wx.FONTWEIGHT_BOLD); heading.SetFont(font)
        root.Add(heading, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root.Add(wx.StaticText(
            self, label="Custom menus are stored separately; protected starters remain available for recovery."
        ), 0, wx.ALL, 12)
        self.list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        for index, (label, width) in enumerate((
            ("Menu", 180), ("File", 260), ("Source", 110), ("Validation", 220),
        )):
            self.list.InsertColumn(index, label, width=width)
        root.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in (
            ("Open Designer", self.on_open),
            ("New from Selected", self.on_new),
            ("Delete Customization", self.on_delete),
            ("Refresh", lambda event: self.refresh()),
            ("Close", lambda event: self.EndModal(wx.ID_CLOSE)),
        ):
            button = wx.Button(self, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.RIGHT, 8)
        root.Add(buttons, 0, wx.ALL, 10)
        self.SetSizer(root)
        self.refresh()

    def refresh(self):
        self.rows = self.model.entries()
        self.list.DeleteAllItems()
        for entry in self.rows:
            row = self.list.InsertItem(self.list.GetItemCount(), entry["name"])
            self.list.SetItem(row, 1, entry["filename"])
            self.list.SetItem(row, 2, "Custom" if entry["customized"] else "Starter")
            self.list.SetItem(row, 3, "Valid" if entry["valid"] else "Invalid")

    def selected_entry(self):
        row = self.list.GetFirstSelected()
        if row == -1:
            raise ValueError("Select a menu definition first.")
        return self.rows[row]

    def on_open(self, _event):
        try:
            entry = self.selected_entry()
            path = self.model.open_customization(entry)
            starter = entry.get("starter") or entry["path"]
            self.open_handler(path, path, starter)
            self.refresh()
        except Exception as error:
            wx.MessageBox(str(error), "Cannot open menu designer", wx.OK | wx.ICON_ERROR, self)

    def on_new(self, _event):
        try:
            entry = self.selected_entry()
        except ValueError as error:
            wx.MessageBox(str(error), "New menu", wx.OK | wx.ICON_INFORMATION, self); return
        dialog = wx.TextEntryDialog(self, "Enter a lowercase menu name:", "New Menu Definition")
        if dialog.ShowModal() != wx.ID_OK:
            dialog.Destroy(); return
        name = dialog.GetValue().strip(); dialog.Destroy()
        try:
            path = self.model.create_from(entry["path"], name)
            self.open_handler(path, path, None)
            self.refresh()
        except Exception as error:
            wx.MessageBox(str(error), "Cannot create menu", wx.OK | wx.ICON_ERROR, self)

    def on_delete(self, _event):
        try:
            entry = self.selected_entry()
            if not entry["customized"]:
                raise ValueError("The selected menu is already using its protected starter.")
        except ValueError as error:
            wx.MessageBox(str(error), "No customization", wx.OK | wx.ICON_INFORMATION, self); return
        dialog = wx.MessageDialog(
            self, "Delete the selected menu customization and restore its starter?",
            "Delete Menu Customization", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        result = dialog.ShowModal(); dialog.Destroy()
        if result != wx.ID_YES:
            return
        try:
            self.model.delete_customization(entry)
            self.refresh()
        except Exception as error:
            wx.MessageBox(str(error), "Cannot delete customization", wx.OK | wx.ICON_ERROR, self)


def open_menu_catalog(parent, user_directory, starters, open_handler):
    """Open the modal menu catalog and return its result."""
    dialog = MenuCatalogDialog(
        parent, MenuCatalogModel(user_directory, starters), open_handler,
    )
    try:
        return dialog.ShowModal()
    finally:
        dialog.Destroy()
