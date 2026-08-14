"""Small diagnostics and no-send mail demonstrations for the JSForm sample."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import wx
import JSForm


def _all(connection, sql):
    cursor = connection.cursor()
    cursor.execute(sql)
    rows = cursor.fetchall()
    cursor.close()
    return rows


class DiagnosticsDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Sample Diagnostics")
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(wx.StaticText(
            panel,
            label="JSForm records unexpected errors locally and can create a safe support package.",
        ), 0, wx.ALL, 10)
        self.status = wx.StaticText(panel, label="No sample error has been recorded in this session.")
        outer.Add(self.status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        record = wx.Button(panel, label="Record Sample Error")
        package = wx.Button(panel, label="Create Support Package")
        logs = wx.Button(panel, label="Open Log Folder")
        close = wx.Button(panel, wx.ID_CLOSE, "Close")
        for button in (record, package, logs):
            buttons.Add(button, 0, wx.RIGHT, 6)
        buttons.AddStretchSpacer()
        buttons.Add(close)
        outer.Add(buttons, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(outer)
        record.Bind(wx.EVT_BUTTON, self.on_record)
        package.Bind(wx.EVT_BUTTON, self.on_package)
        logs.Bind(wx.EVT_BUTTON, self.on_logs)
        close.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CLOSE))
        self.SetSize((680, 180))
        self.CentreOnParent()

    def on_record(self, _event):
        error_id = JSForm.report_exception(
            RuntimeError("Intentional JSForm sample diagnostic"),
            operation="sample.diagnostics", screen="Sample Diagnostics",
        )
        self.status.SetLabel(f"Sample diagnostic recorded as {error_id}.")

    def on_package(self, _event):
        default = "JSFormSample-Support-{}.zip".format(datetime.now().strftime("%Y%m%d-%H%M%S"))
        with wx.FileDialog(
            self, "Save Support Package", wildcard="ZIP files (*.zip)|*.zip",
            defaultFile=default, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as chooser:
            if chooser.ShowModal() != wx.ID_OK:
                return
            try:
                target = JSForm.create_support_package(
                    chooser.GetPath(),
                    safe_diagnostics={"sample_database": "JSFormTest", "real_mail_enabled": False},
                )
            except Exception as error:
                wx.MessageBox(str(error), "Support Package Failed", wx.OK | wx.ICON_ERROR, self)
                return
            self.status.SetLabel(f"Support package created: {Path(target).name}")

    def on_logs(self, _event):
        reporter = JSForm.current_error_reporter()
        if reporter:
            reporter.log_directory.mkdir(parents=True, exist_ok=True)
            os.startfile(reporter.log_directory)


class MailPreviewDialog(wx.Dialog):
    def __init__(self, parent, connection):
        super().__init__(parent, title="Fake Mail Preview - Nothing Will Be Sent")
        recipients = [row[0] for row in _all(
            connection,
            "SELECT Email FROM sb_driver WHERE Active=1 AND Email IS NOT NULL ORDER BY LastName,FirstName",
        ) if JSForm.valid_email(row[0])]
        message = JSForm.MailMessage(
            subject="Pine Valley route reminder",
            body=("This is a fictional JSForm sample message.\n\n"
                  "Please review tomorrow's assigned bus route.\n\n"
                  "This preview cannot send email."),
        )
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        warning = wx.StaticText(panel, label="PREVIEW ONLY - no mail server is configured and no message can be sent.")
        warning.SetForegroundColour(wx.Colour(180, 0, 0))
        outer.Add(warning, 0, wx.ALL, 10)
        grid = wx.FlexGridSizer(3, 2, 6, 8)
        grid.AddGrowableCol(1, 1)
        grid.Add(wx.StaticText(panel, label="Recipients:"), 0, wx.ALIGN_TOP)
        grid.Add(wx.TextCtrl(panel, value="\n".join(JSForm.unique_recipients(recipients)), style=wx.TE_MULTILINE | wx.TE_READONLY), 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Subject:"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.TextCtrl(panel, value=message.subject, style=wx.TE_READONLY), 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Message:"), 0, wx.ALIGN_TOP)
        grid.Add(wx.TextCtrl(panel, value=message.body, style=wx.TE_MULTILINE | wx.TE_READONLY), 1, wx.EXPAND)
        outer.Add(grid, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        close = wx.Button(panel, wx.ID_CLOSE, "Close")
        close.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CLOSE))
        outer.Add(close, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(outer)
        self.SetSize((680, 430))
        self.CentreOnParent()


def show_diagnostics(parent):
    dialog = DiagnosticsDialog(parent)
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()


def show_mail_preview(parent, connection):
    dialog = MailPreviewDialog(parent, connection)
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()
