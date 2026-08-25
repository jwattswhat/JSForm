"""Build and manage native wxPython menu bars from validated definitions."""

from __future__ import annotations

from dataclasses import dataclass, field

import wx

try:  # Support installed-package and repository-level focused tests.
    from .menu_commands import CommandContext, CommandRegistry
    from .menu_definition import MenuDefinition
except ImportError:  # pragma: no cover - repository-level fallback
    from menu_commands import CommandContext, CommandRegistry
    from menu_definition import MenuDefinition


class MenuInstallationError(RuntimeError):
    """Report a menu that cannot be safely resolved or installed."""


@dataclass
class _MenuNode:
    kind: str
    parent: object
    item: object
    position: int
    command_name: str | None = None
    item_kind: str = "normal"
    submenu: object | None = None
    children: list = field(default_factory=list)
    present: bool = True


@dataclass
class _TopMenu:
    menu: object
    label: str
    position: int
    children: list
    present: bool = True


class MenuInstaller:
    """Install, refresh, dispatch, replace, and dispose one frame menu bar."""

    def __init__(self, frame, registry, *, context_provider=None):
        if not isinstance(frame, wx.Frame):
            raise TypeError("MenuInstaller requires a top-level wx.Frame")
        if not isinstance(registry, CommandRegistry):
            raise TypeError("registry must be a CommandRegistry")
        if context_provider is not None and not callable(context_provider):
            raise TypeError("context_provider must be callable or None")
        self.frame = frame
        self.registry = registry
        self.context_provider = context_provider
        self._menu_bar = None
        self._previous_menu_bar = None
        self._bindings = []
        self._top_menus = []
        self._command_nodes = {}
        self._current_form = None

    @property
    def menu_bar(self):
        """Return the currently owned menu bar, or None before installation."""
        return self._menu_bar

    def install(self, definition, *, current_form=None):
        """Build and transactionally install a validated menu definition."""
        if not isinstance(definition, MenuDefinition):
            raise TypeError("definition must be a MenuDefinition")
        command_names = tuple(self._definition_commands(definition.menus))
        missing = tuple(name for name in command_names if name not in self.registry)
        if missing:
            source = " in {}".format(definition.path) if definition.path else ""
            raise MenuInstallationError(
                "Unregistered menu command{}{}: {}".format(
                    "s" if len(missing) != 1 else "", source,
                    ", ".join(dict.fromkeys(missing)),
                )
            )

        new_bar = wx.MenuBar()
        new_top = []
        new_command_nodes = {}
        new_bindings = []
        command_ids = {}
        used_ids = set()
        replaced_bar = self.frame.GetMenuBar()
        try:
            for position, menu_data in enumerate(definition.menus):
                menu, children = self._build_menu(
                    menu_data, new_command_nodes, command_ids, used_ids
                )
                new_bar.Append(menu, menu_data["label"])
                new_top.append(_TopMenu(
                    menu=menu, label=menu_data["label"], position=position,
                    children=children,
                ))
            for command_name, item_id in command_ids.items():
                handler = self._menu_handler(command_name)
                self.frame.Bind(wx.EVT_MENU, handler, id=item_id)
                new_bindings.append((wx.EVT_MENU, handler, item_id))
            open_handler = self._on_menu_open
            self.frame.Bind(wx.EVT_MENU_OPEN, open_handler)
            new_bindings.append((wx.EVT_MENU_OPEN, open_handler, None))

            old_current_form = self._current_form
            self._current_form = current_form
            try:
                self._refresh_structure(new_bar, new_top)
                self.frame.SetMenuBar(new_bar)
            except Exception:
                self._current_form = old_current_form
                raise
        except Exception:
            self._unbind(new_bindings)
            self._destroy(new_bar)
            raise

        old_bar = self._menu_bar
        old_bindings = self._bindings
        if old_bar is None:
            self._previous_menu_bar = replaced_bar
        self._menu_bar = new_bar
        self._bindings = new_bindings
        self._top_menus = new_top
        self._command_nodes = new_command_nodes
        self._unbind(old_bindings)
        if old_bar is not None:
            self._destroy(old_bar)
        return new_bar

    def refresh(self):
        """Refresh state and dynamic visibility for all installed commands."""
        if self._menu_bar is None:
            return {}
        return self._refresh_structure(self._menu_bar, self._top_menus)

    def dispose(self):
        """Unbind owned events, restore the prior bar, and destroy owned menus."""
        if self._menu_bar is None:
            return False
        owned = self._menu_bar
        try:
            if self.frame.GetMenuBar() is owned:
                self.frame.SetMenuBar(self._previous_menu_bar)
        except RuntimeError:
            # The owning frame may already have completed native destruction.
            pass
        self._unbind(self._bindings)
        self._destroy(owned)
        self._menu_bar = None
        self._previous_menu_bar = None
        self._bindings = []
        self._top_menus = []
        self._command_nodes = {}
        self._current_form = None
        return True

    def _build_menu(self, menu_data, command_nodes, command_ids, used_ids):
        menu = wx.Menu()
        nodes = []
        for position, item_data in enumerate(menu_data["items"]):
            if "separator" in item_data:
                item = menu.AppendSeparator()
                nodes.append(_MenuNode("separator", menu, item, position))
                continue
            if "items" in item_data:
                submenu, children = self._build_menu(
                    item_data, command_nodes, command_ids, used_ids
                )
                item = menu.AppendSubMenu(
                    submenu, item_data["label"], item_data.get("help_text", "")
                )
                nodes.append(_MenuNode(
                    "submenu", menu, item, position, submenu=submenu,
                    children=children,
                ))
                continue
            command = self.registry.get(item_data["command"])
            item_id = command_ids.get(command.name)
            if item_id is None:
                item_id = command.wx_id
                if item_id is None:
                    item_id = wx.NewIdRef()
                    while int(item_id) in used_ids:
                        item_id = wx.NewIdRef()
                numeric_id = int(item_id)
                if numeric_id in used_ids:
                    raise MenuInstallationError(
                        "Menu item ID collision for command {}: {}".format(
                            command.name, numeric_id
                        )
                    )
                used_ids.add(numeric_id)
                command_ids[command.name] = item_id
            label = item_data.get("label", command.label)
            accelerator = item_data.get("accelerator")
            if accelerator:
                label = "{}\t{}".format(label, accelerator)
            help_text = item_data.get("help_text", command.help_text)
            item_kind = item_data.get("kind", "normal")
            wx_kind = {
                "normal": wx.ITEM_NORMAL,
                "check": wx.ITEM_CHECK,
                "radio": wx.ITEM_RADIO,
            }[item_kind]
            item = menu.Append(item_id, label, help_text, kind=wx_kind)
            node = _MenuNode(
                "command", menu, item, position,
                command_name=command.name, item_kind=item_kind,
            )
            nodes.append(node)
            command_nodes.setdefault(command.name, []).append(node)
        return menu, nodes

    def _refresh_structure(self, menu_bar, top_menus):
        context = self._base_context()
        states = {
            name: self.registry.state(name, context)
            for name in self._command_names(top_menus)
        }
        for top in top_menus:
            self._reconcile_menu(top.menu, top.children, states)
        desired_top = []
        for top in top_menus:
            visible = self._nodes_have_content(top.children, states)
            if visible:
                desired_top.append(top)
            elif top.present:
                index = self._menu_bar_index(menu_bar, top.menu)
                if index != -1:
                    menu_bar.Remove(index)
                top.present = False
        for index, top in enumerate(desired_top):
            current = self._menu_bar_index(menu_bar, top.menu)
            if current == -1:
                menu_bar.Insert(index, top.menu, top.label)
                top.present = True
            elif current != index:
                menu_bar.Remove(current)
                menu_bar.Insert(index, top.menu, top.label)
        for name, nodes in self._command_nodes_for(top_menus).items():
            state = states[name]
            for node in nodes:
                node.item.Enable(state.enabled)
                if node.item_kind in {"check", "radio"}:
                    node.item.Check(state.checked)
        return states

    def _reconcile_menu(self, menu, nodes, states):
        for node in nodes:
            if node.kind == "submenu":
                self._reconcile_menu(node.submenu, node.children, states)
        visible = []
        pending_separator = None
        for node in nodes:
            node_visible = self._node_visible(node, states)
            if node.kind == "separator":
                if visible:
                    pending_separator = node
                continue
            if node_visible:
                if pending_separator is not None:
                    visible.append(pending_separator)
                    pending_separator = None
                visible.append(node)
        visible_ids = {id(node) for node in visible}
        for node in nodes:
            should_show = id(node) in visible_ids
            if node.present and not should_show:
                menu.Remove(node.item)
                node.present = False
        for index, node in enumerate(visible):
            current = self._menu_item_index(menu, node.item)
            if current == -1:
                menu.Insert(index, node.item)
                node.present = True
            elif current != index:
                menu.Remove(node.item)
                menu.Insert(index, node.item)

    def _node_visible(self, node, states):
        if node.kind == "command":
            return states[node.command_name].visible
        if node.kind == "submenu":
            return self._nodes_have_content(node.children, states)
        return False

    def _nodes_have_content(self, nodes, states):
        return any(
            node.kind != "separator" and self._node_visible(node, states)
            for node in nodes
        )

    def _base_context(self):
        if self.context_provider is not None:
            context = self.context_provider()
            if not isinstance(context, CommandContext):
                raise TypeError("context_provider must return CommandContext")
            return context
        current_form = self._current_form() if callable(self._current_form) else self._current_form
        return CommandContext(
            frame=self.frame,
            current_form=current_form,
            authorization_policy=getattr(current_form, "AUTHORIZATION_POLICY", None),
        )

    def _menu_handler(self, command_name):
        def handler(event):
            return self.registry.dispatch(
                command_name, self._base_context(), event=event, source="menu"
            )
        return handler

    def _on_menu_open(self, event):
        self.refresh()
        if hasattr(event, "Skip"):
            event.Skip()

    def _unbind(self, bindings):
        for event_type, handler, item_id in reversed(bindings):
            kwargs = {"handler": handler}
            if item_id is not None:
                kwargs["id"] = item_id
            try:
                self.frame.Unbind(event_type, **kwargs)
            except RuntimeError:
                # Native frame destruction already released the binding.
                continue

    @staticmethod
    def _destroy(menu_bar):
        if menu_bar is not None and hasattr(menu_bar, "Destroy"):
            try:
                menu_bar.Destroy()
            except RuntimeError:
                # wx may have destroyed the bar with its owning frame.
                pass

    @staticmethod
    def _definition_commands(menus):
        for menu in menus:
            for item in menu["items"]:
                if "command" in item:
                    yield item["command"]
                elif "items" in item:
                    yield from MenuInstaller._definition_commands((item,))

    @staticmethod
    def _command_names(top_menus):
        return tuple(dict.fromkeys(MenuInstaller._command_nodes_for(top_menus)))

    @staticmethod
    def _command_nodes_for(top_menus):
        result = {}

        def visit(nodes):
            for node in nodes:
                if node.kind == "command":
                    result.setdefault(node.command_name, []).append(node)
                elif node.kind == "submenu":
                    visit(node.children)

        for top in top_menus:
            visit(top.children)
        return result

    @staticmethod
    def _menu_item_index(menu, item):
        for index, candidate in enumerate(menu.GetMenuItems()):
            if candidate is item:
                return index
        return -1

    @staticmethod
    def _menu_bar_index(menu_bar, menu):
        for index in range(menu_bar.GetMenuCount()):
            if menu_bar.GetMenu(index) is menu:
                return index
        return -1
