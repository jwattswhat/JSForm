import os
import wx, mysql 
from JasonSQLForms import CONFIG, OPTION, FONT,clsDB, clsForm
from clsForms import clsBASEForm
class clsForm(clsBASEForm):
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
DB = clsDB.clsDB("localhost", "test")
DBConnection = mysql.connector.connect(**DB.DB)
CONFIG.set_Config_DBConnection(DBConnection)
OPTION.set_Option_DBConnection(DBConnection)
FONT.Get_Config_Font()
#
# 	Main form
#
frm = clsForm(None, DBConnection, "frmOpenForms", ["Close"])
path = CONFIG.get_Config_Value("Location","Form")
list_of_files = []
for root,dirs,files in os.walk(path):
    for file in files:
        fn = os.path.splitext(file)[0]
        if fn != "frmOpenForms":
            list_of_files.append(fn)
frm.CONTROLID["Forms"].Set(list_of_files)
#
# bind application events
#

frm.FORM.Bind(wx.EVT_BUTTON, _buttonclick, frm.CONTROLID["btnOpen"])

frm.show()
frm.display_form_data()
app.MainLoop()
