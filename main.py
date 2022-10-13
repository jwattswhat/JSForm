import wx 
import mysql

import clsDB
import clsForms
from clsConfig import CONFIG
from clsConstants import CONST
from clsFont import FONT, DBconnection
from clsMonitor import PMON, clsMonitor
from clsOption import OPTION
from clsConstants import CONST
from clsFont import FONT

app = wx.App(0)

DB = clsDB.clsDB("localhost")
try:
    DBConnection = mysql.connector.connect(**DB.DB)
except:
    pass
#CONFIG.set_Config_DBConnection(ChurchDBConnection)
#OPTION.set_Option_DBConnection(ChurchDBConnection)
#FONT.set_Font_DBConnection(ChurchDBConnection)
#FONT.Get_Config_Font()

