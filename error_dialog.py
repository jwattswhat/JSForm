"""Standard wxPython presentation for a recorded JSForm error."""

from __future__ import annotations


def show_error_dialog(parent, error_id: str, *, application_name="Application", fatal=False):
    import wx

    if fatal:
        guidance = "The application must restart before you continue."
        title = "Restart Required"
        style = wx.OK | wx.ICON_ERROR
    else:
        guidance = "The action was not completed. You may close this message and continue."
        title = "Unable to Complete Action"
        style = wx.OK | wx.ICON_ERROR
    message = (
        f"{application_name} could not complete this action.\n\n"
        f"Error ID: {error_id}\n"
        "The technical details were saved in the support log.\n\n"
        f"{guidance}"
    )
    return wx.MessageBox(message, title, style, parent)


def show_error_dialog_threadsafe(parent, error_id: str, **options):
    import wx

    if wx.IsMainThread():
        return show_error_dialog(parent, error_id, **options)
    wx.CallAfter(show_error_dialog, parent, error_id, **options)
    return None
