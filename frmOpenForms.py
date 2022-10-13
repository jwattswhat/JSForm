import wx
import mysql.connector


from clsConfig import CONFIG
from clsOption import OPTION
from clsFont import FONT
import clsDB
import clsForms

class clsForm(clsForms.clsBASEForm):
    pass

def _buttonclick(event):
    form = frm.CONTROLID["Forms"].GetValueText()
    btn = event.GetEventObject().GetName()
    form = clsForm(None, DBConnection, form, ["Navigation", "Close"])
    form.display_form_data()
    form.show()


#
# 	Main Program
#
app = wx.App(0)
#
# 	Connect to DataBase
#
DB = clsDB.clsDB("localhost", "test", "church", "Church99")
DBConnection = mysql.connector.connect(**DB.DB)
CONFIG.set_Config_DBConnection(DBConnection)
OPTION.set_Option_DBConnection(DBConnection)
FONT.Get_Config_Font()
#
# 	Main form
#
frm = clsForm(None, DBConnection, "frmOpenForms", ["Close"])

#
# bind application events
#

frm.FORM.Bind(wx.EVT_BUTTON, _buttonclick, frm.CONTROLID["btnOpen"])

frm.show()
frm.display_form_data()
app.MainLoop()
