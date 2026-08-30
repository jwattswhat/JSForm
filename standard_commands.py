"""Factories for application, Edit, and current-form standard commands."""

from __future__ import annotations

import wx

try:
    from .menu_commands import ApplicationCommand, CommandState
except ImportError:  # pragma: no cover - repository-level focused tests
    from menu_commands import ApplicationCommand, CommandState


def standard_application_commands(
    application_name, *, application_version="", about_handler=None,
    exit_handler=None,
):
    """Return standard Exit and About commands for an application frame."""
    if not isinstance(application_name, str) or not application_name.strip():
        raise ValueError("application_name must be a nonempty string")

    def close_application(context):
        if exit_handler is not None:
            return exit_handler(context)
        return context.frame.Close()

    def show_about(context):
        if about_handler is not None:
            return about_handler(context)
        message = application_name.strip()
        if application_version:
            message += "\nVersion {}".format(application_version)
        return wx.MessageBox(message, "About {}".format(application_name), wx.OK, context.frame)

    def frame_available(context):
        return CommandState(enabled=context.frame is not None)

    return (
        ApplicationCommand(
            "app.exit", "E&xit", close_application, wx_id=wx.ID_EXIT,
            help_text="Close {}".format(application_name),
            state_provider=frame_available,
        ),
        ApplicationCommand(
            "app.about", "&About", show_about, wx_id=wx.ID_ABOUT,
            help_text="About {}".format(application_name),
            state_provider=frame_available,
        ),
    )


def standard_edit_commands(*, focus_provider=None):
    """Return focus-sensitive Cut, Copy, Paste, and Select All commands."""
    focus_provider = focus_provider or wx.Window.FindFocus

    def focused(_context):
        return focus_provider()

    def supports(method, capability=None):
        def state(context):
            control = focused(context)
            if control is None or not callable(getattr(control, method, None)):
                return CommandState(enabled=False)
            if capability is not None and callable(getattr(control, capability, None)):
                return CommandState(enabled=bool(getattr(control, capability)()))
            return CommandState()
        return state

    def invoke(method, fallback=None):
        def handler(context):
            control = focused(context)
            operation = getattr(control, method, None) if control is not None else None
            if callable(operation):
                return operation()
            if fallback is not None and control is not None:
                fallback_operation = getattr(control, fallback, None)
                if callable(fallback_operation):
                    return fallback_operation(-1, -1)
            return None
        return handler

    def select_all_state(context):
        control = focused(context)
        return CommandState(enabled=(
            control is not None and (
                callable(getattr(control, "SelectAll", None))
                or callable(getattr(control, "SetSelection", None))
            )
        ))

    return (
        ApplicationCommand(
            "edit.cut", "Cu&t", invoke("Cut"), wx_id=wx.ID_CUT,
            help_text="Cut the selection", state_provider=supports("Cut", "CanCut"),
        ),
        ApplicationCommand(
            "edit.copy", "&Copy", invoke("Copy"), wx_id=wx.ID_COPY,
            help_text="Copy the selection", state_provider=supports("Copy", "CanCopy"),
        ),
        ApplicationCommand(
            "edit.paste", "&Paste", invoke("Paste"), wx_id=wx.ID_PASTE,
            help_text="Paste from the clipboard", state_provider=supports("Paste", "CanPaste"),
        ),
        ApplicationCommand(
            "edit.select_all", "Select &All", invoke("SelectAll", "SetSelection"),
            wx_id=wx.ID_SELECTALL, help_text="Select all content",
            state_provider=select_all_state,
        ),
    )


def standard_record_commands():
    """Return commands that target the current JSForm form in their context."""

    def form_method(context, method):
        form = context.current_form
        operation = getattr(form, method, None) if form is not None else None
        if callable(operation):
            return operation()
        return None

    def form_state(operation, method, *, require_record=False, require_table=False):
        def state(context):
            form = context.current_form
            if form is None or not callable(getattr(form, method, None)):
                return CommandState(enabled=False)
            records = getattr(form, "RECORDS", None)
            if require_record and (
                records is None or not callable(getattr(records, "current", None))
                or records.current() is None
            ):
                return CommandState(enabled=False)
            if require_table and "table" not in getattr(form, "FORMDESCRIPTON", {}):
                return CommandState(enabled=False)
            required_operation = operation
            if operation == "save":
                classifier = getattr(records, "pending_save_operation", None)
                if not callable(classifier):
                    return CommandState(enabled=False)
                try:
                    required_operation = classifier()
                except Exception:
                    return CommandState(enabled=False)
            security = getattr(form, "SECURITY", None)
            if security is not None and not security.allows(required_operation):
                return CommandState(enabled=False)
            return CommandState()
        return state

    return (
        ApplicationCommand(
            "record.new", "&New Record",
            lambda context: form_method(context, "new_record"), wx_id=wx.ID_NEW,
            help_text="Create a new record",
            state_provider=form_state("create", "new_record"),
        ),
        ApplicationCommand(
            "record.save", "&Save Record",
            lambda context: form_method(context, "save_record"), wx_id=wx.ID_SAVE,
            help_text="Save the current record",
            state_provider=form_state(
                "save", "save_record", require_record=True
            ),
        ),
        ApplicationCommand(
            "record.delete", "&Delete Record",
            lambda context: form_method(context, "delete_record"), wx_id=wx.ID_DELETE,
            help_text="Delete the current record", destructive=True,
            state_provider=form_state(
                "delete", "delete_record", require_record=True
            ),
        ),
        ApplicationCommand(
            "record.refresh", "&Refresh Records",
            lambda context: form_method(context, "refresh_records"), wx_id=wx.ID_REFRESH,
            help_text="Reload records from the database",
            state_provider=form_state(
                "open", "refresh_records", require_table=True
            ),
        ),
    )
