"""Compact actions, safe confirmations, and application-directed output paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import wx

try:
    from .menu_commands import ApplicationCommand, CommandContext, CommandRegistry
except ImportError:  # pragma: no cover - repository-level focused tests
    from menu_commands import ApplicationCommand, CommandContext, CommandRegistry


@dataclass(frozen=True)
class Action:
    """Describe one command shared by an action bar and optional menu."""

    name: str
    label: str
    handler: object = None
    window_id: int = wx.ID_ANY
    trailing: bool = False
    destructive: bool = False
    help_text: str = ""
    command_name: str = ""

    def __post_init__(self):
        if self.handler is None and not self.command_name:
            raise ValueError("Action requires a handler or registered command name")
        if self.handler is not None and self.command_name:
            raise ValueError("Action cannot define both a handler and command name")
        if self.handler is not None and not callable(self.handler):
            raise TypeError("Action handler must be callable or None")


def action_from_command(command, *, trailing=False):
    """Adapt a registered command for an action-bar or legacy menu surface."""
    if not isinstance(command, ApplicationCommand):
        raise TypeError("command must be an ApplicationCommand")
    return Action(
        name=command.name,
        label=command.label,
        window_id=command.wx_id if command.wx_id is not None else wx.ID_ANY,
        trailing=trailing,
        destructive=command.destructive,
        help_text=command.help_text,
        command_name=command.name,
    )


class StandardActionBar(wx.Panel):
    """One-row action bar whose buttons can share handlers with a menu."""

    def __init__(
        self, parent, actions, *, border=0, registry=None, context_provider=None
    ):
        super().__init__(parent)
        self.actions = tuple(actions)
        self.registry = registry
        self.context_provider = context_provider
        self.buttons = {}
        layout = wx.BoxSizer(wx.HORIZONTAL)
        trailing_started = False
        for action in self.actions:
            if action.trailing and not trailing_started:
                layout.AddStretchSpacer()
                trailing_started = True
            button = wx.Button(self, action.window_id, action.label)
            if action.help_text:
                button.SetToolTip(action.help_text)
            if action.destructive:
                button.SetForegroundColour(wx.Colour(170, 0, 0))
            button.Bind(
                wx.EVT_BUTTON,
                _resolved_handler(
                    action, registry, context_provider, source="action_bar"
                ),
            )
            layout.Add(button, 0, wx.RIGHT, 6)
            self.buttons[action.name] = button
        self.SetSizer(layout)
        if border:
            self.SetWindowStyle(self.GetWindowStyle() | wx.BORDER_SIMPLE)
        if registry is not None:
            self.refresh()

    def enable(self, name, enabled=True):
        self.buttons[name].Enable(bool(enabled))

    def refresh(self):
        """Apply registered command state to command-backed buttons."""
        if self.registry is None:
            return {}
        context = _provided_context(self.context_provider)
        states = {}
        for action in self.actions:
            if not action.command_name:
                continue
            state = self.registry.state(action.command_name, context)
            button = self.buttons[action.name]
            button.Enable(state.enabled)
            button.Show(state.visible)
            states[action.command_name] = state
        if hasattr(self, "Layout"):
            self.Layout()
        return states


def install_action_menu(
    frame, title, actions, menu_bar=None, *, registry=None, context_provider=None
):
    """Expose the same action handlers through a standard menu."""
    menu_bar = menu_bar or frame.GetMenuBar() or wx.MenuBar()
    menu = wx.Menu()
    items = {}
    for action in actions:
        item_id = action.window_id if action.window_id != wx.ID_ANY else wx.NewIdRef()
        item = menu.Append(item_id, action.label, action.help_text)
        frame.Bind(
            wx.EVT_MENU,
            _resolved_handler(action, registry, context_provider, source="menu"),
            id=item.GetId(),
        )
        items[action.name] = item
    menu_bar.Append(menu, title)
    if frame.GetMenuBar() is None:
        frame.SetMenuBar(menu_bar)
    return items


def _provided_context(context_provider):
    context = context_provider() if context_provider is not None else CommandContext()
    if not isinstance(context, CommandContext):
        raise TypeError("context_provider must return CommandContext")
    return context


def _resolved_handler(action, registry, context_provider, *, source):
    if action.command_name:
        if not isinstance(registry, CommandRegistry):
            raise TypeError("A CommandRegistry is required for command-backed actions")

        def dispatch(event):
            return registry.dispatch(
                action.command_name, _provided_context(context_provider),
                event=event, source=source,
            )

        return dispatch
    return action.handler


def destructive_confirmation_message(subject, *, consequence="", dependent_count=0, dependent_label="dependent record"):
    """Build a consistent warning that identifies deletion consequences."""
    message = "Delete {}?".format(subject)
    if dependent_count:
        label = dependent_label if dependent_count == 1 else dependent_label + "s"
        message += "\n\nThis will also affect {} {}.".format(dependent_count, label)
    if consequence:
        message += "\n\n" + consequence
    return message


def confirm_destructive_action(
    parent, subject, *, title="Confirm deletion", consequence="",
    dependent_count=0, dependent_label="dependent record",
):
    """Ask for explicit confirmation and return whether deletion was approved."""
    return wx.MessageBox(
        destructive_confirmation_message(
            subject, consequence=consequence, dependent_count=dependent_count,
            dependent_label=dependent_label,
        ),
        title, wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, parent,
    ) == wx.YES


class OutputLocation:
    """Application-supplied default folder and consistent save-path handling."""

    def __init__(self, default_directory, *, extension="", wildcard="All files (*.*)|*.*"):
        self.default_directory = Path(default_directory).expanduser().resolve()
        self.extension = extension if not extension or extension.startswith(".") else "." + extension
        self.wildcard = wildcard

    def path(self, filename):
        filename = Path(str(filename)).name
        if not filename:
            raise ValueError("Enter an output filename.")
        target = self.default_directory / filename
        if self.extension and target.suffix.casefold() != self.extension.casefold():
            target = target.with_suffix(self.extension)
        return target

    def choose(self, parent, *, title, filename):
        target = self.path(filename)
        with wx.FileDialog(
            parent, title, defaultDir=str(self.default_directory),
            defaultFile=target.name, wildcard=self.wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            selected = Path(dialog.GetPath())
            if self.extension and selected.suffix.casefold() != self.extension.casefold():
                selected = selected.with_suffix(self.extension)
            return selected
