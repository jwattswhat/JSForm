"""Provide the historical JSForm error namespace and wxPython error handler."""

import wx
import JSForm
class clsErrorNameSpace:
    #    __slots__ = ()

    ERRMSG = "Application Error: #{number}:{msg}"
    ERR = [
        "Cannot Open Database",  # 0 - Error
        "This is also an error",  # 1 - Another Error
    ]
    ERR0 = 0
    ERRANOTHER = 1


er = clsErrorNameSpace()


class _error:
    def __init__(
        self,
        errornumber,
        module=None,
    ):
        errormessage = er.ERRMSG.format(number=er.ERRANOTHER, msg=er.ERR[er.ERRANOTHER])

        panel = wx.Dialog(
            None, id=wx.ID_ANY, title="Application Error", size=[400, 200], pos=[10, 10]
        )
        self.text = wx.StaticText(
            panel,
            wx.ID_ANY,
            label=errormessage,
            pos=(10, 50),
        )
        self.btn = wx.Button(
            panel,
            JSForm.CONST.FORM_CONTINUE,
            label="Continue",
            size=(100, 30),
            pos=(10, 100),
        )
        self.btn = wx.Button(
            panel, JSForm.CONST.FORM_CANCEL, label="Cancel", size=(100, 30), pos=(120, 100)
        )

        result = panel.ShowModal()
        panel.Destroy()


class clsErrorHandler(Exception):
    def __init__(self, number, *args):
        errormessage = _error(number)
