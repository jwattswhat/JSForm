"""Compact actions, safe confirmations, and application-directed output paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import wx


@dataclass(frozen=True)
class Action:
    name: str
    label: str
    handler: object
    window_id: int = wx.ID_ANY
    trailing: bool = False
    destructive: bool = False
    help_text: str = ""


class StandardActionBar(wx.Panel):
    """One-row action bar whose buttons can share handlers with a menu."""

    def __init__(self, parent, actions, *, border=0):
        super().__init__(parent)
        self.actions = tuple(actions)
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
            button.Bind(wx.EVT_BUTTON, action.handler)
            layout.Add(button, 0, wx.RIGHT, 6)
            self.buttons[action.name] = button
        self.SetSizer(layout)
        if border:
            self.SetWindowStyle(self.GetWindowStyle() | wx.BORDER_SIMPLE)

    def enable(self, name, enabled=True):
        self.buttons[name].Enable(bool(enabled))


def install_action_menu(frame, title, actions, menu_bar=None):
    """Expose the same action handlers through a standard menu."""
    menu_bar = menu_bar or frame.GetMenuBar() or wx.MenuBar()
    menu = wx.Menu()
    items = {}
    for action in actions:
        item_id = action.window_id if action.window_id != wx.ID_ANY else wx.NewIdRef()
        item = menu.Append(item_id, action.label, action.help_text)
        frame.Bind(wx.EVT_MENU, action.handler, id=item.GetId())
        items[action.name] = item
    menu_bar.Append(menu, title)
    if frame.GetMenuBar() is None:
        frame.SetMenuBar(menu_bar)
    return items


def destructive_confirmation_message(subject, *, consequence="", dependent_count=0, dependent_label="dependent record"):
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
