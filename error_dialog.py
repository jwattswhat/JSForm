"""Standard wxPython presentation for a recorded JSForm error."""

from __future__ import annotations

from JSForm.error_redaction import redact_text


def show_error_dialog(
    parent, error_id: str, *, application_name="Application", fatal=False,
    user_message=None, redactors=(),
):
    """Show a plain-text error reference without exposing technical details."""
    import wx

    if fatal:
        guidance = "The application must restart before you continue."
        title = "Restart Required"
        style = wx.OK | wx.ICON_ERROR
    else:
        guidance = "The action was not completed. You may close this message and continue."
        title = "Unable to Complete Action"
        style = wx.OK | wx.ICON_ERROR
    safe_application = redact_text(application_name, redactors)
    safe_error_id = redact_text(error_id, redactors)
    message = (
        f"{safe_application} could not complete this action.\n\n"
        f"Error ID: {safe_error_id}\n"
        "The technical details were saved in the support log.\n\n"
        f"{guidance}"
    )
    if user_message:
        message += "\n\n" + redact_text(user_message, redactors)
    return wx.MessageBox(message, title, style, parent)


def show_error_dialog_threadsafe(parent, error_id: str, **options):
    """Show now on the UI thread or schedule the dialog with ``wx.CallAfter``."""
    import wx

    if wx.IsMainThread():
        return show_error_dialog(parent, error_id, **options)
    wx.CallAfter(show_error_dialog, parent, error_id, **options)
    return None
