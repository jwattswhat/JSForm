"""Editable, application-neutral model for visual JSForm menu design."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import wx

from JSForm.builder_windows import show_builder_window

from JSForm.menu_definition import MenuDefinition, MenuDefinitionError, MenuDefinitionLoader
from JSForm.menu_definition import save_menu_definition
from JSForm.menu_builder import MenuInstaller
from JSForm.menu_commands import ApplicationCommand, CommandContext, CommandRegistry
from JSForm.window_icons import apply_window_icon


@dataclass(frozen=True)
class MenuCommandDescriptor:
    """Safe command metadata exposed to the menu designer."""

    name: str
    label: str
    help_text: str = ""
    category: str = "Other"
    default_accelerator: str = ""
    allowed_kinds: tuple[str, ...] = ("normal",)

    def __post_init__(self):
        if not self.name or not self.label:
            raise ValueError("Command descriptor name and label are required.")
        allowed = tuple(self.allowed_kinds)
        if not allowed or not set(allowed) <= {"normal", "check", "radio"}:
            raise ValueError("allowed_kinds contains an unsupported menu kind.")
        object.__setattr__(self, "allowed_kinds", allowed)


@dataclass(frozen=True)
class MenuValidationIssue:
    """One designer validation result with a stable severity and node path."""

    severity: str
    path: str
    message: str


class MenuDesignerModel:
    """Edit menu JSON through deterministic, undoable model operations."""

    def __init__(self, definition, command_descriptors=(), *, loader=None):
        self.loader = loader or MenuDefinitionLoader()
        if isinstance(definition, MenuDefinition):
            data = definition.to_dict()
        elif isinstance(definition, dict):
            data = deepcopy(definition)
        else:
            raise TypeError("definition must be MenuDefinition or dict")
        descriptors = tuple(command_descriptors)
        self.commands = {item.name: item for item in descriptors}
        if len(self.commands) != len(descriptors):
            raise ValueError("Command descriptor names must be unique.")
        self._data = data
        self._baseline = deepcopy(data)
        self._undo = []
        self._redo = []

    @property
    def name(self):
        return self._data.get("name", "")

    @property
    def dirty(self):
        return self._data != self._baseline

    @property
    def can_undo(self):
        return bool(self._undo)

    @property
    def can_redo(self):
        return bool(self._redo)

    def to_dict(self):
        """Return a detached copy of the current working definition."""
        return deepcopy(self._data)

    def to_definition(self):
        """Return a runtime definition or raise for any designer error."""
        issues = [item for item in self.validate() if item.severity == "error"]
        if issues:
            raise MenuDefinitionError(issues[0].message)
        return self.loader.from_dict(self.to_dict())

    def mark_saved(self):
        """Set the current definition as the clean baseline."""
        self._baseline = deepcopy(self._data)

    def replace_definition(self, definition):
        """Replace the working content as one undoable transaction."""
        data = definition.to_dict() if isinstance(definition, MenuDefinition) else deepcopy(definition)
        self._change(lambda: setattr(self, "_data", data))

    def node(self, path):
        """Return a detached node selected by an index path."""
        return deepcopy(self._node(path))

    def add_menu(self, label="&Menu", index=None):
        """Add a top-level menu and return its path."""
        menus = self._data.setdefault("menus", [])
        index = len(menus) if index is None else index
        self._change(lambda: menus.insert(index, {"label": label, "items": []}))
        return (index,)

    def add_command(self, parent, command, *, index=None, **properties):
        """Add an approved command item beneath a menu or submenu."""
        if self.commands and command not in self.commands:
            raise ValueError("Unknown command: {}".format(command))
        item = {"command": command}
        item.update({key: value for key, value in properties.items() if value not in (None, "")})
        return self._add_child(parent, item, index)

    def add_submenu(self, parent, label="&Submenu", *, index=None):
        """Add a submenu beneath a menu or submenu."""
        if len(tuple(parent)) >= 4:
            raise ValueError("Menus support at most four hierarchy levels.")
        return self._add_child(parent, {"label": label, "items": []}, index)

    def add_separator(self, parent, *, index=None):
        """Add a separator beneath a menu or submenu."""
        return self._add_child(parent, {"separator": True}, index)

    def update_node(self, path, **properties):
        """Update supported properties on one node as one transaction."""
        node = self._node(path)
        forbidden = set(properties) - {
            "label", "help_text", "command", "accelerator", "kind", "radio_group"
        }
        if forbidden:
            raise ValueError("Unsupported menu properties: {}".format(sorted(forbidden)))
        if "command" in properties and self.commands and properties["command"] not in self.commands:
            raise ValueError("Unknown command: {}".format(properties["command"]))

        def mutate():
            for key, value in properties.items():
                if value in (None, ""):
                    node.pop(key, None)
                else:
                    node[key] = value
            if node.get("kind") != "radio":
                node.pop("radio_group", None)

        self._change(mutate)

    def delete(self, path):
        """Delete a selected node and return its detached value."""
        parent, index = self._parent_and_index(path)
        removed = deepcopy(parent[index])
        self._change(lambda: parent.pop(index))
        return removed

    def duplicate(self, path):
        """Duplicate a node immediately after itself and return the new path."""
        parent, index = self._parent_and_index(path)
        self._change(lambda: parent.insert(index + 1, deepcopy(parent[index])))
        return tuple(path[:-1]) + (index + 1,)

    def move_up(self, path):
        """Move a node one position earlier among its siblings."""
        parent, index = self._parent_and_index(path)
        if index == 0:
            return tuple(path)
        self._change(lambda: parent.insert(index - 1, parent.pop(index)))
        return tuple(path[:-1]) + (index - 1,)

    def move_down(self, path):
        """Move a node one position later among its siblings."""
        parent, index = self._parent_and_index(path)
        if index >= len(parent) - 1:
            return tuple(path)
        self._change(lambda: parent.insert(index + 1, parent.pop(index)))
        return tuple(path[:-1]) + (index + 1,)

    def indent(self, path):
        """Move a non-menu node beneath the preceding submenu."""
        parent, index = self._parent_and_index(path)
        if len(path) == 1 or index == 0 or "items" not in parent[index - 1]:
            raise ValueError("Indent requires a preceding menu or submenu.")
        target = parent[index - 1]["items"]
        if len(path) >= 4:
            raise ValueError("Menus support at most four hierarchy levels.")
        self._change(lambda: target.append(parent.pop(index)))
        return tuple(path[:-1]) + (index - 1, len(target) - 1)

    def outdent(self, path):
        """Move a submenu child immediately after its parent submenu."""
        if len(path) < 3:
            raise ValueError("Top-level menu items cannot be outdented.")
        grandparent, parent_index = self._parent_and_index(path[:-1])
        parent_node = grandparent[parent_index]
        child_index = path[-1]

        def mutate():
            child = parent_node["items"].pop(child_index)
            grandparent.insert(parent_index + 1, child)

        self._change(mutate)
        return tuple(path[:-2]) + (parent_index + 1,)

    def undo(self):
        """Restore the state before the most recent successful transaction."""
        if not self._undo:
            return False
        self._redo.append(deepcopy(self._data))
        self._data = self._undo.pop()
        return True

    def redo(self):
        """Reapply the most recently undone transaction."""
        if not self._redo:
            return False
        self._undo.append(deepcopy(self._data))
        self._data = self._redo.pop()
        return True

    def validate(self):
        """Return deterministic schema, command, mnemonic, and usability issues."""
        issues = []
        try:
            self.loader.from_dict(self.to_dict())
        except MenuDefinitionError as error:
            issues.append(MenuValidationIssue("error", self.name or "definition", str(error)))
        accelerators = {}
        for path, node, display_path in self._walk():
            if "command" in node:
                command = node["command"]
                if self.commands and command not in self.commands:
                    issues.append(MenuValidationIssue(
                        "error", display_path, "Unknown command: {}".format(command)
                    ))
                accelerator = node.get("accelerator", "").casefold()
                if accelerator:
                    if accelerator in accelerators:
                        issues.append(MenuValidationIssue(
                            "error", display_path,
                            "Accelerator is also assigned to {}.".format(accelerators[accelerator]),
                        ))
                    accelerators[accelerator] = display_path
        for menu in self._data.get("menus", []):
            if "&" not in menu.get("label", ""):
                issues.append(MenuValidationIssue(
                    "warning", menu.get("label", "Menu"),
                    "Top-level menu has no mnemonic marker (&).",
                ))
        return tuple(issues)

    def _walk(self):
        def visit(items, prefix, labels):
            for index, node in enumerate(items):
                path = prefix + (index,)
                label = node.get("label") or node.get("command") or "Separator"
                display = " > ".join(labels + [label.replace("&", "")])
                yield path, node, display
                if "items" in node:
                    yield from visit(node["items"], path, labels + [label.replace("&", "")])
        yield from visit(self._data.get("menus", []), (), [])

    def _node(self, path):
        path = tuple(path)
        if not path:
            raise ValueError("A node path is required.")
        items = self._data["menus"]
        node = None
        for depth, index in enumerate(path):
            try:
                node = items[index]
            except (IndexError, TypeError):
                raise ValueError("Invalid menu node path: {}".format(path)) from None
            if depth < len(path) - 1:
                if "items" not in node:
                    raise ValueError("Path enters a node that cannot contain items.")
                items = node["items"]
        return node

    def _children(self, path):
        node = self._node(path)
        if "items" not in node:
            raise ValueError("Selected node cannot contain menu items.")
        return node["items"]

    def _parent_and_index(self, path):
        path = tuple(path)
        if not path:
            raise ValueError("A node path is required.")
        parent = self._data["menus"] if len(path) == 1 else self._children(path[:-1])
        if not 0 <= path[-1] < len(parent):
            raise ValueError("Invalid menu node path: {}".format(path))
        return parent, path[-1]

    def _add_child(self, parent_path, item, index):
        children = self._children(parent_path)
        index = len(children) if index is None else index
        self._change(lambda: children.insert(index, item))
        return tuple(parent_path) + (index,)

    def _change(self, mutation):
        before = deepcopy(self._data)
        mutation()
        if self._data != before:
            self._undo.append(before)
            self._redo.clear()


class MenuDesignerFrame(wx.Frame):
    """Visual tree, command-palette, and property editor for one menu file."""

    def __init__(
        self, definition_path, command_descriptors, *, save_path,
        starter_path=None, preview_handler=None, audit_hook=None,
    ):
        self.definition_path = Path(definition_path)
        self.save_path = Path(save_path)
        self.starter_path = Path(starter_path) if starter_path else None
        if self.starter_path and self.save_path.resolve() == self.starter_path.resolve():
            raise ValueError("The menu designer cannot save over a protected starter.")
        self.loader = MenuDefinitionLoader()
        loaded_definition = self._load_with_recovery()
        self.model = MenuDesignerModel(
            loaded_definition, tuple(command_descriptors),
            loader=self.loader,
        )
        self.preview_handler = preview_handler
        self.audit_hook = audit_hook
        self.selected_path = None
        super().__init__(None, title="JSForm Menu Designer - {}".format(self.model.name), size=(1280, 760))
        apply_window_icon(self)
        self._build_menu_bar()
        self._build_interface()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.refresh_all()
        if getattr(self, "recovery_message", ""):
            self.SetStatusText(self.recovery_message)

    def _load_with_recovery(self):
        """Load the requested file, or a valid backup/starter for safe recovery."""
        self.recovery_message = ""
        try:
            return self.loader.load(self.definition_path)
        except (OSError, MenuDefinitionError, ValueError) as original_error:
            candidates = (
                (self.save_path.with_suffix(self.save_path.suffix + ".bak"), "previous version"),
                (self.starter_path, "protected starter"),
            )
            for path, label in candidates:
                if path is None or not path.is_file():
                    continue
                try:
                    definition = self.loader.load(path)
                except (OSError, MenuDefinitionError, ValueError):
                    continue
                self.recovery_message = (
                    "The selected file is invalid. Loaded the {} for recovery; "
                    "the invalid file is unchanged until Save.".format(label)
                )
                return definition
            raise original_error

    def _build_menu_bar(self):
        bar = wx.MenuBar()
        file_menu = wx.Menu()
        for identifier, label, handler in (
            (wx.ID_SAVE, "&Save\tCtrl+S", self.on_save),
            (wx.ID_SAVEAS, "Save &As...", self.on_save_as),
            (wx.ID_PREVIEW, "&Preview", self.on_preview),
            (wx.ID_CLOSE, "&Close", lambda event: self.Close()),
        ):
            file_menu.Append(identifier, label)
            self.Bind(wx.EVT_MENU, handler, id=identifier)
        edit_menu = wx.Menu()
        for identifier, label, handler in (
            (wx.ID_UNDO, "&Undo\tCtrl+Z", self.on_undo),
            (wx.ID_REDO, "&Redo\tCtrl+Y", self.on_redo),
            (wx.ID_DUPLICATE, "&Duplicate", self.on_duplicate),
            (wx.ID_DELETE, "&Delete\tDelete", self.on_delete),
        ):
            edit_menu.Append(identifier, label)
            self.Bind(wx.EVT_MENU, handler, id=identifier)
        edit_menu.AppendSeparator()
        restore_starter_id = wx.NewIdRef()
        restore_previous_id = wx.NewIdRef()
        edit_menu.Append(restore_starter_id, "Restore &Starter")
        edit_menu.Append(restore_previous_id, "Restore &Previous")
        self.Bind(wx.EVT_MENU, self.on_restore_starter, id=restore_starter_id)
        self.Bind(wx.EVT_MENU, self.on_restore_previous, id=restore_previous_id)
        bar.Append(file_menu, "&File")
        bar.Append(edit_menu, "&Edit")
        self.SetMenuBar(bar)

    def _build_interface(self):
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)
        actions = wx.WrapSizer(wx.HORIZONTAL)
        action_specs = (
            ("Save", self.on_save), ("Save As", self.on_save_as),
            ("Undo", self.on_undo), ("Redo", self.on_redo),
            ("Add Menu", self.on_add_menu), ("Add Command", self.on_add_command),
            ("Add Submenu", self.on_add_submenu), ("Add Separator", self.on_add_separator),
            ("Duplicate", self.on_duplicate), ("Delete", self.on_delete),
            ("Up", self.on_move_up), ("Down", self.on_move_down),
            ("Indent", self.on_indent), ("Outdent", self.on_outdent),
            ("Preview", self.on_preview), ("Validate", self.on_validate),
            ("Restore Starter", self.on_restore_starter),
            ("Restore Previous", self.on_restore_previous),
        )
        self.action_buttons = {}
        for label, handler in action_specs:
            button = wx.Button(panel, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            actions.Add(button, 0, wx.RIGHT, 5)
            self.action_buttons[label] = button
        root.Add(actions, 0, wx.EXPAND | wx.ALL, 8)

        body = wx.BoxSizer(wx.HORIZONTAL)
        palette_panel = wx.Panel(panel)
        palette_sizer = wx.BoxSizer(wx.VERTICAL)
        palette_sizer.Add(wx.StaticText(palette_panel, label="Approved Commands"), 0, wx.BOTTOM, 5)
        self.search = wx.SearchCtrl(palette_panel)
        self.search.ShowCancelButton(True)
        self.search.Bind(wx.EVT_TEXT, lambda event: self.refresh_palette())
        palette_sizer.Add(self.search, 0, wx.EXPAND | wx.BOTTOM, 6)
        self.palette = wx.ListCtrl(palette_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.palette.InsertColumn(0, "Command", width=185)
        self.palette.InsertColumn(1, "Label", width=145)
        self.palette.InsertColumn(2, "Category", width=100)
        self.palette.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_add_command)
        palette_sizer.Add(self.palette, 1, wx.EXPAND)
        palette_panel.SetSizer(palette_sizer)
        body.Add(palette_panel, 0, wx.EXPAND | wx.ALL, 8)

        tree_panel = wx.Panel(panel)
        tree_sizer = wx.BoxSizer(wx.VERTICAL)
        tree_sizer.Add(wx.StaticText(tree_panel, label="Menu Structure"), 0, wx.BOTTOM, 5)
        self.tree = wx.TreeCtrl(tree_panel, style=wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT | wx.TR_SINGLE)
        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_selection)
        tree_sizer.Add(self.tree, 1, wx.EXPAND)
        tree_panel.SetSizer(tree_sizer)
        body.Add(tree_panel, 1, wx.EXPAND | wx.ALL, 8)

        properties = wx.Panel(panel)
        property_sizer = wx.BoxSizer(wx.VERTICAL)
        property_sizer.Add(wx.StaticText(properties, label="Properties"), 0, wx.BOTTOM, 5)
        grid = wx.FlexGridSizer(0, 2, 6, 8)
        grid.AddGrowableCol(1, 1)
        self.property_controls = {}
        for name, label in (
            ("label", "Label"), ("command", "Command"), ("help_text", "Help text"),
            ("accelerator", "Accelerator"), ("kind", "Kind"),
            ("radio_group", "Radio group"),
        ):
            grid.Add(wx.StaticText(properties, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            if name == "command":
                control = wx.Choice(properties, choices=sorted(self.model.commands, key=str.casefold))
            elif name == "kind":
                control = wx.Choice(properties, choices=["", "normal", "check", "radio"])
            else:
                control = wx.TextCtrl(properties)
            self.property_controls[name] = control
            grid.Add(control, 1, wx.EXPAND)
        property_sizer.Add(grid, 0, wx.EXPAND)
        apply_button = wx.Button(properties, label="Apply Properties")
        apply_button.Bind(wx.EVT_BUTTON, self.on_apply_properties)
        property_sizer.Add(apply_button, 0, wx.TOP, 8)
        property_sizer.Add(wx.StaticText(properties, label="Validation"), 0, wx.TOP | wx.BOTTOM, 10)
        self.validation = wx.ListBox(properties)
        property_sizer.Add(self.validation, 1, wx.EXPAND)
        properties.SetSizer(property_sizer)
        body.Add(properties, 0, wx.EXPAND | wx.ALL, 8)

        root.Add(body, 1, wx.EXPAND)
        panel.SetSizer(root)
        self.CreateStatusBar()

    def refresh_all(self, selected=None):
        self.refresh_tree(selected)
        self.refresh_palette()
        self.refresh_validation()
        self.SetTitle("JSForm Menu Designer - {}{}".format(
            self.model.name, " *" if self.model.dirty else ""
        ))
        self.action_buttons["Undo"].Enable(self.model.can_undo)
        self.action_buttons["Redo"].Enable(self.model.can_redo)

    def refresh_tree(self, selected=None):
        self.tree.DeleteAllItems()
        root = self.tree.AddRoot(self.model.name or "Menu")

        def append(parent_item, items, prefix):
            for index, node in enumerate(items):
                path = prefix + (index,)
                if "separator" in node:
                    label = "──────── Separator"
                elif "command" in node:
                    label = node.get("label") or self.model.commands.get(
                        node["command"], MenuCommandDescriptor(node["command"], node["command"])
                    ).label
                    label = "{}  [{}]".format(label, node["command"])
                else:
                    label = node.get("label", "Submenu")
                item = self.tree.AppendItem(parent_item, label)
                self.tree.SetItemData(item, path)
                if "items" in node:
                    append(item, node["items"], path)
            self.tree.Expand(parent_item)

        append(root, self.model.to_dict().get("menus", []), ())
        self.tree.ExpandAll()
        self.selected_path = selected
        if selected is not None:
            self._select_tree_path(root, selected)

    def _select_tree_path(self, item, path):
        child, cookie = self.tree.GetFirstChild(item)
        while child.IsOk():
            if self.tree.GetItemData(child) == tuple(path):
                self.tree.SelectItem(child)
                return True
            if self._select_tree_path(child, path):
                return True
            child, cookie = self.tree.GetNextChild(item, cookie)
        return False

    def refresh_palette(self):
        query = self.search.GetValue().strip().casefold()
        self.palette.DeleteAllItems()
        for descriptor in sorted(self.model.commands.values(), key=lambda item: (item.category.casefold(), item.label.casefold())):
            haystack = " ".join((descriptor.name, descriptor.label, descriptor.category, descriptor.help_text)).casefold()
            if query and query not in haystack:
                continue
            row = self.palette.InsertItem(self.palette.GetItemCount(), descriptor.name)
            self.palette.SetItem(row, 1, descriptor.label.replace("&", ""))
            self.palette.SetItem(row, 2, descriptor.category)

    def refresh_validation(self):
        self.validation.Set([
            "{}: {} — {}".format(item.severity.upper(), item.path, item.message)
            for item in self.model.validate()
        ])

    def on_selection(self, event):
        path = self.tree.GetItemData(event.GetItem())
        self.selected_path = tuple(path) if path is not None else None
        node = self.model.node(self.selected_path) if self.selected_path else {}
        for name, control in self.property_controls.items():
            value = str(node.get(name, ""))
            if isinstance(control, wx.Choice):
                control.SetStringSelection(value)
            else:
                control.ChangeValue(value)
        event.Skip()

    def _selected_parent(self):
        if self.selected_path is None:
            raise ValueError("Select a menu or submenu first.")
        node = self.model.node(self.selected_path)
        if "items" in node:
            return self.selected_path
        if len(self.selected_path) == 1:
            raise ValueError("Select a menu or submenu first.")
        return self.selected_path[:-1]

    def _palette_command(self):
        row = self.palette.GetFirstSelected()
        if row == -1:
            raise ValueError("Select an approved command first.")
        return self.palette.GetItemText(row)

    def _run_change(self, operation):
        try:
            selected = operation()
        except (ValueError, MenuDefinitionError) as error:
            wx.MessageBox(str(error), "Cannot change menu", wx.OK | wx.ICON_WARNING, self)
            return
        self.refresh_all(selected)

    def _require_selection(self):
        if self.selected_path is None:
            raise ValueError("Select a menu node first.")
        return self.selected_path

    def on_add_menu(self, _event): self._run_change(lambda: self.model.add_menu())
    def on_add_command(self, _event): self._run_change(lambda: self.model.add_command(self._selected_parent(), self._palette_command()))
    def on_add_submenu(self, _event): self._run_change(lambda: self.model.add_submenu(self._selected_parent()))
    def on_add_separator(self, _event): self._run_change(lambda: self.model.add_separator(self._selected_parent()))
    def on_duplicate(self, _event): self._run_change(lambda: self.model.duplicate(self._require_selection()))
    def on_delete(self, _event): self._run_change(lambda: (self.model.delete(self._require_selection()), None)[1])
    def on_move_up(self, _event): self._run_change(lambda: self.model.move_up(self._require_selection()))
    def on_move_down(self, _event): self._run_change(lambda: self.model.move_down(self._require_selection()))
    def on_indent(self, _event): self._run_change(lambda: self.model.indent(self._require_selection()))
    def on_outdent(self, _event): self._run_change(lambda: self.model.outdent(self._require_selection()))

    def on_apply_properties(self, _event):
        if self.selected_path is None:
            return
        values = {}
        for name, control in self.property_controls.items():
            value = control.GetStringSelection() if isinstance(control, wx.Choice) else control.GetValue()
            values[name] = value.strip()
        node = self.model.node(self.selected_path)
        allowed = {"label", "help_text"}
        if "command" in node:
            allowed.update(("command", "accelerator", "kind", "radio_group"))
        self._run_change(lambda: (self.model.update_node(
            self.selected_path, **{key: value for key, value in values.items() if key in allowed}
        ), self.selected_path)[1])

    def on_undo(self, _event):
        if self.model.undo(): self.refresh_all()

    def on_redo(self, _event):
        if self.model.redo(): self.refresh_all()

    def on_validate(self, _event):
        self.refresh_validation()
        errors = [item for item in self.model.validate() if item.severity == "error"]
        self.SetStatusText("Menu is valid." if not errors else "{} validation error(s).".format(len(errors)))

    def on_save(self, _event):
        try:
            definition = self.model.to_definition()
            save_menu_definition(definition, self.save_path, loader=self.loader)
        except (OSError, MenuDefinitionError, ValueError) as error:
            if self.audit_hook:
                self.audit_hook("menu_validation_failed", {
                    "name": self.model.name,
                    "error_count": len([
                        issue for issue in self.model.validate()
                        if issue.severity == "error"
                    ]),
                })
            wx.MessageBox(str(error), "Cannot save menu", wx.OK | wx.ICON_ERROR, self)
            return
        self.model.mark_saved()
        self.refresh_all(self.selected_path)
        self.SetStatusText("Saved {}".format(self.save_path.name))
        if self.audit_hook:
            self.audit_hook("menu_customization_saved", {"name": self.model.name})

    def on_save_as(self, event):
        """Choose another safe filename in the approved customization directory."""
        with wx.FileDialog(
            self, "Save menu customization as", defaultDir=str(self.save_path.parent),
            defaultFile=self.save_path.name, wildcard="JSON menu files (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            candidate = Path(dialog.GetPath())
        if candidate.suffix.casefold() != ".json" or candidate.resolve().parent != self.save_path.parent.resolve():
            wx.MessageBox(
                "Choose a .json file inside the approved customization directory.",
                "Cannot save menu", wx.OK | wx.ICON_ERROR, self,
            )
            return
        self.save_path = candidate
        self.on_save(event)

    def on_restore_starter(self, _event):
        """Load the protected starter into working memory without saving it."""
        if self.starter_path is None or not self.starter_path.is_file():
            wx.MessageBox("No starter is available.", "Restore Starter", wx.OK | wx.ICON_INFORMATION, self)
            return
        self._restore_from(self.starter_path, "menu_starter_loaded", "Loaded starter; Save to apply it.")

    def on_restore_previous(self, _event):
        """Load the prior valid backup into working memory without saving it."""
        previous = self.save_path.with_suffix(self.save_path.suffix + ".bak")
        if not previous.is_file():
            wx.MessageBox("No previous saved version is available.", "Restore Previous", wx.OK | wx.ICON_INFORMATION, self)
            return
        self._restore_from(previous, "menu_previous_loaded", "Loaded previous version; Save to apply it.")

    def _restore_from(self, path, audit_event, status):
        try:
            definition = self.loader.load(path)
        except (OSError, MenuDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Cannot restore menu", wx.OK | wx.ICON_ERROR, self)
            return
        self.model.replace_definition(definition)
        self.refresh_all()
        self.SetStatusText(status)
        if self.audit_hook:
            self.audit_hook(audit_event, {"name": self.model.name})

    def on_preview(self, _event):
        if self.preview_handler is None:
            self.SetStatusText("Preview is not configured.")
            return
        try:
            self.preview_handler(self.model.to_definition(), tuple(self.model.commands.values()))
        except Exception as error:
            wx.MessageBox(str(error), "Cannot preview menu", wx.OK | wx.ICON_ERROR, self)

    def _on_close(self, event):
        if not self.model.dirty:
            event.Skip(); return
        dialog = wx.MessageDialog(
            self, "Save changes to this menu definition?", "Unsaved menu changes",
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
        )
        result = dialog.ShowModal(); dialog.Destroy()
        if result == wx.ID_CANCEL:
            event.Veto(); return
        if result == wx.ID_YES:
            self.on_save(event)
            if self.model.dirty:
                event.Veto(); return
        event.Skip()


def open_menu_designer(
    definition_path, command_descriptors, *, save_path, starter_path=None,
    preview_handler=None, audit_hook=None,
):
    """Open and return a modeless visual menu designer frame."""
    preview_handler = preview_handler or preview_menu_definition
    frame = MenuDesignerFrame(
        definition_path, command_descriptors, save_path=save_path,
        starter_path=starter_path, preview_handler=preview_handler,
        audit_hook=audit_hook,
    )
    show_builder_window(frame)
    return frame


def preview_menu_definition(definition, command_descriptors):
    """Show an inert native preview that cannot execute application handlers."""
    if not isinstance(definition, MenuDefinition):
        raise TypeError("definition must be a MenuDefinition")
    frame = wx.Frame(None, title="Menu Preview - {}".format(definition.name), size=(720, 420))
    apply_window_icon(frame)
    frame.CreateStatusBar()
    panel = wx.Panel(frame)
    layout = wx.BoxSizer(wx.VERTICAL)
    heading = wx.StaticText(panel, label="Native menu preview")
    font = heading.GetFont(); font.SetPointSize(14); font.SetWeight(wx.FONTWEIGHT_BOLD); heading.SetFont(font)
    layout.Add(heading, 0, wx.ALL, 16)
    layout.Add(wx.StaticText(
        panel,
        label="Preview commands are inert. Select an item to inspect its command name and help text.",
    ), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 16)
    panel.SetSizer(layout)
    registry = CommandRegistry()
    for descriptor in command_descriptors:
        def show_command(context, selected=descriptor):
            context.frame.SetStatusText(
                "{} — {}".format(selected.name, selected.help_text or selected.label.replace("&", ""))
            )
        registry.register(ApplicationCommand(
            descriptor.name, descriptor.label, show_command,
            help_text=descriptor.help_text,
        ))
    installer = MenuInstaller(
        frame, registry, context_provider=lambda: CommandContext(frame=frame, source="preview")
    )
    installer.install(definition)
    frame._jsform_menu_preview_installer = installer

    def dispose(event):
        installer.dispose()
        event.Skip()

    frame.Bind(wx.EVT_CLOSE, dispose)
    frame.Show()
    return frame
