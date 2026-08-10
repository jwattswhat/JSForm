"""
    jsform 


"""
import argparse
import JSForm

import wx

def _buttonclick(event):
    def _runReports(event):
        reportid = frm.CONTROLID["ReportID"].GetValue()
        JSForm.RunReport(reportid, frm, JSFormDB.DBConnection)
        frm.FORM.Close()

    select = event.GetEventObject().GetName()
    formname = None 
    match select:
        case "lblEnhancements":
            formname = "frmEnhancement"
        case "lblOptions":
            formname = "frmOptions"
        case "lblConfig":
            formname = "frmConfig"
        case "lblReports":
            frm = JSForm.clsForm(cmfrm, JSFormDB.DBConnection, "frmReports", ["Close"])
            frm.CONTROLID["btnRun"].Bind(wx.EVT_LEFT_DOWN, _runReports)
            frm.disable_all_buttons()
            frm.enable_button("ReportID")
            frm.enable_button("btnRun")
            frm.enable_button("btnClose")
            frm.show()
            return

        case _:
            print("form name not found found. {}".format(formname))

    if formname != None:
        form = JSForm.clsForm(cmfrm, JSFormDB.DBConnection, formname)
        form.show()

cmparser = argparse.ArgumentParser(
    prog="JSForm", description="JSForm - Configure v0.1"
)
cmparser.add_argument("-s", "--server", type=str, default="localhost")
cmparser.add_argument("-d", "--database", type=str, default="ChurchDB")
cmparser.add_argument("-u", "--user", type=str)
cmparser.add_argument("-p", "--password", type=str)

args = cmparser.parse_args()
# print(args.server,args.database,args.user,args.password)


host = args.server
database = args.database
user = args.user
password = args.password

app = wx.App(0)

#
# 	Connect to DataBase
#
JSFormDB = JSForm.clsDB(host, database, user, password)
JSForm.CONFIG.set_Config_DBConnection(JSFormDB)
JSForm.OPTION.set_Option_DBConnection(JSFormDB)
JSForm.FONT.set_Font_DBConnection(JSFormDB)
JSForm.FONT.Get_Config_Font()
JSForm.CONST.btnNavigationCONTROLS = JSForm.convertNavButtons(
    JSForm.CONST.btnNavigationCONTROLS
)

#
# 	Main form
#
cmfrm = JSForm.clsForm(None, JSFormDB.DBConnection, "frmJSForm", ["Close"])


cmfrm.CONTROLID["lblEnhancements"].Bind(wx.EVT_LEFT_DOWN, _buttonclick)
cmfrm.CONTROLID["lblOptions"].Bind(wx.EVT_LEFT_DOWN, _buttonclick)
cmfrm.CONTROLID["lblConfig"].Bind(wx.EVT_LEFT_DOWN, _buttonclick)
cmfrm.CONTROLID["lblReports"].Bind(wx.EVT_LEFT_DOWN, _buttonclick)

cmfrm.show()
app.MainLoop()
