"""Reusable responsive progress dialog for long-running application work."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable

import wx

from JSForm.error_reporting import report_exception


@dataclass(frozen=True)
class OperationResult:
    """User-facing result returned by a background operation."""

    message: str = "The operation completed successfully."
    restart_required: bool = False
    payload: Any = None


class BackgroundOperationController:
    """Run one operation at a time and marshal its result to the UI thread."""

    def __init__(self, *, dispatch=None):
        self.dispatch = dispatch or wx.CallAfter
        self._lock = threading.Lock()
        self._running = False

    @property
    def running(self):
        with self._lock:
            return self._running

    def start(self, operation, *, on_success, on_failure):
        with self._lock:
            if self._running:
                return False
            self._running = True

        def worker():
            try:
                result = operation()
                if result is None:
                    result = OperationResult()
                elif isinstance(result, str):
                    result = OperationResult(result)
                elif not isinstance(result, OperationResult):
                    result = OperationResult(payload=result)
            except BaseException as error:  # operation boundary must restore UI state
                self.dispatch(self._finish_failure, on_failure, error)
            else:
                self.dispatch(self._finish_success, on_success, result)

        threading.Thread(target=worker, name="JSFormBackgroundOperation", daemon=True).start()
        return True

    def _finish_success(self, callback, result):
        with self._lock:
            self._running = False
        callback(result)

    def _finish_failure(self, callback, error):
        with self._lock:
            self._running = False
        callback(error)


class BackgroundOperationDialog(wx.Dialog):
    """Small progress dialog that starts an application-supplied operation."""

    def __init__(
        self, parent, *, title, operation: Callable[[], Any],
        working_message="Working...", success_message="The operation completed successfully.",
        start_immediately=True,
    ):
        super().__init__(
            parent, title=title, size=(500, 240),
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        self.operation = operation
        self.success_message = success_message
        self.controller = BackgroundOperationController()
        self._build(working_message)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.CentreOnParent()
        if start_immediately:
            wx.CallAfter(self.start)

    def _build(self, working_message):
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        self.heading = wx.StaticText(panel, label=working_message)
        font = self.heading.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.heading.SetFont(font)
        outer.Add(self.heading, 0, wx.EXPAND | wx.ALL, 14)
        self.gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        outer.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 14)
        self.detail = wx.StaticText(panel, label="Please wait. You may continue when this window reports completion.")
        self.detail.Wrap(450)
        outer.Add(self.detail, 1, wx.EXPAND | wx.ALL, 14)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.AddStretchSpacer()
        self.start_button = wx.Button(panel, label="Start")
        self.start_button.Bind(wx.EVT_BUTTON, lambda _event: self.start())
        buttons.Add(self.start_button, 0, wx.RIGHT, 8)
        self.close_button = wx.Button(panel, wx.ID_CLOSE, "Close")
        self.close_button.Bind(wx.EVT_BUTTON, self._on_close)
        buttons.Add(self.close_button)
        outer.Add(buttons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)
        panel.SetSizer(outer)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda _event: self.gauge.Pulse(), self.timer)

    def start(self):
        if self.controller.running:
            return False
        self.heading.SetLabel("Working...")
        self.detail.SetLabel("Please wait. This window will remain responsive while the work is completed.")
        self.start_button.Disable()
        self.close_button.Disable()
        self.timer.Start(100)
        started = self.controller.start(
            self.operation, on_success=self._on_success, on_failure=self._on_failure,
        )
        if not started:
            self.timer.Stop()
        return started

    def _finish(self):
        self.timer.Stop()
        self.gauge.SetValue(100)
        self.close_button.Enable()

    def _on_success(self, result):
        self._finish()
        if result.restart_required:
            self.heading.SetLabel("Completed — restart required")
            self.detail.SetLabel(result.message or "Restart the application to continue.")
        else:
            self.heading.SetLabel("Completed")
            self.detail.SetLabel(result.message or self.success_message)

    def _on_failure(self, error):
        self._finish()
        error_id = report_exception(error, operation="background_operation")
        self.heading.SetLabel("Unable to complete")
        self.detail.SetLabel("{}\n\nSupport reference: {}".format(str(error), error_id))
        self.start_button.Enable()

    def _on_close(self, event):
        if self.controller.running:
            if hasattr(event, "Veto"):
                event.Veto()
            return
        self.EndModal(wx.ID_CLOSE)


def run_background_operation(parent, *, title, operation, working_message="Working...", success_message=None):
    """Show the standard modal progress interface for ``operation``."""
    dialog = BackgroundOperationDialog(
        parent, title=title, operation=operation, working_message=working_message,
        success_message=success_message or "The operation completed successfully.",
    )
    try:
        return dialog.ShowModal()
    finally:
        dialog.Destroy()
