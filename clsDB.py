"""
    clsDB.py - Church Database Classes
    Rev. Jonathan C. Watt
    July 1, 2021
"""

#   System Imports

import wx
import mysql
import mysql.connector
from mysql.connector import FieldType
from datetime import datetime, timedelta

#   Framework Imports
import JSForm

class clsDB:
    """
    clsDB -
    Rev. Jonathan C. Watt
    July 2021

    DB = dictionary description of username, password, host, database
    DBconnection = connection to database
    """
    class _getcredentials(wx.Dialog):
        def __init__(self, parent, title):
            super().__init__(None,title=title,size=(400,250))
            panel = wx.Panel(self)
            lblhost =       wx.StaticText(panel,wx.ID_ANY,  pos=(10,20),label="Host:")
            self.host =     wx.TextCtrl(panel,wx.ID_ANY,    pos=(100,20),size=(200,30))
            lbldb =         wx.StaticText(panel,wx.ID_ANY,  pos=(10,50),label="Database:")
            self.database =       wx.TextCtrl(panel,wx.ID_ANY,    pos=(100,50),size=(200,30))
            lblusername =   wx.StaticText(panel,wx.ID_ANY,  pos=(10,80),label="Username:")
            self.username = wx.TextCtrl(panel,wx.ID_ANY,    pos=(100,80),size=(200,30))
            lblpassword =   wx.StaticText(panel,wx.ID_ANY,  pos=(10,110),label="Password:")
            self.password = wx.TextCtrl(panel,wx.ID_ANY,    pos=(100,110),size=(200,30) )
            btnok = wx.Button(panel,wx.ID_OK,label="Connect",pos=(10,150),size=(100,30))


    def __init__(self, host=None, databasename=None, username=None, password=None):
        global CONFIG,OPTION,FONT
        if username == None:
                dlg = self._getcredentials(self, title="Enter DB Login info")
                if host:
                    dlg.host.SetValue(host)
                if databasename:
                    dlg.database.SetValue(databasename)
                if username:
                    dlg.username.SetValue(username)
                if password:
                    dlg.password.SetValue(password)
                result = dlg.ShowModal()
                host = dlg.host.GetValue()
                databasename = dlg.database.GetValue()
                username = dlg.username.GetValue()
                password = dlg.password.GetValue()

                dlg.Destroy()
                if result == JSForm.CONST.FORM_CANCEL:
                    return True
        if password == None:
            pass    
        self.DBCredintials = {
            "user": username,
            "password": password,
            "host": host,
            "database": databasename,
        }
        self.DBConnection = mysql.connector.connect(**self.DBCredintials)

class clsRecord:
    """
    <TODO> Add comments for clsRecord
        clsRecord -
        Rev. Jonathan C. Watt
        July 2021
    """
    BlankRecord = -1

    class clsOriginalRecord:
        def __init__(self):
            self.record = {}

        def saverecord(self, record):
            self.record = record.copy()
            for field in self.record:
                self.savefield(field, self.record[field])

        def savefield(self, field, value):
            if value == "":
                self.record[field] = None
            else:
                self.record[field] = value

        def getsavedfield(self, field):
            return self.record[field]

        def restore(self):
            return self.record

        def comparefield(self, field, value):
            return str(value) == str(self.record[field])

        def comparerecord(self, record):
            errorfields = []
            for field in record:
                if self.original[field] == "":
                    self.original[field] == None
                if record[field] == "":
                    record[field] = None
                # print (self.original[field],record[field],self.original[field]==record[field])
                if str(self.original[field]) != str(record[field]):
                    errorfields.append(field)
            if errorfields != []:
                return errorfields
            return False

    def __init__(self, connection, table=None):
        """
        DBConnection - connection to database
        TABLE - dictionary containing table info
            "table" : {
                "name" : "TableName",
                "fields" : ["fieldname","fieldname"],
                "condition" : "SQLWhere Clause",
                "orderby" : "SQLOrderClause"
            }
        ...
        """
        self.DBConnection = connection
        self.TABLENAME = table["name"]
        self.original = self.clsOriginalRecord()
        self.TABLE = table
        self._record = None
        self._position = 0
        self.sqlaspairs = None
        self.sql = None

    def load_records(self, table=None, parentrecord=None):
        if table == None:
            table = self.TABLE
        self._record = self.read_records(table, parentrecord)
        if not self._record:
            self.add(self.sql.get_blank_record())
            return self.current()
        return self.first()

    def read_records(self, table=None, parentrecord=None):
        self.sql = JSForm.clsSQL(self.DBConnection, table, parentrecord)
        cursor = self.DBConnection.cursor()
        sql = self.sql.select()
        try:
            cursor.execute(sql)
        except:
            return None
        rows = cursor.fetchall()
        if len(rows) == 0:
            return []

        records = self.sql.format_sql_records(rows)
        if records != []:
            return records
        return []

    def add(self, rec):
        if self.isempty():
            self._record = []
        self._record.append(rec)
        return self.last()

    def delete(self):
        if not self.isempty():
            self._record.pop(self._position)
            self.prev()

    def current(self):
        if not self.isempty():
            return self._record[self._position]

    def currentfield(self, field):
        return self._record[self._position][field]

    def currentnum(self):
        return self._position

    def first(self):
        if not self.isempty():
            self._position = 0
            self.original.saverecord(self._record[self._position])
            return self._record[self._position]

    def prev(self,loop=False):
        if self._position > 0:
            self._position -= 1
        else:
            if loop:
                return self.last()
        self.original.saverecord(self._record[self._position])
        return self._record[self._position]

    def next(self,loop=False):
        if self._position < len(self._record) - 1:
            self._position += 1
            self.original.saverecord(self._record[self._position])
            return self._record[self._position]
        if loop:
            return self.first()

    def last(self):
        self._position = len(self._record) - 1
        self.original.saverecord(self._record[self._position])
        return self._record[self._position]

    def setfieldvalue(self, field, value):
        self._record[self._position][field] = value

    def updatecurrentrec(self, rec):
        self._record[self._position] = rec

    def getcurrentID(self):
        if not self.isempty():
            return self._record[self._position]["ID"]

    def getfield(self, name):
        return self._record[self._position][name]

    def setControlID(self, name, ID):
        self._record[self._position][name].update({"ControlID": ID})

    def ControlID(self):
        return self._record[self._position]["ControlID"]

    def get_field_by_name(self, fieldname):
        return self._record[self._position].get(fieldname)

    def isempty(self):
        return self._record == None

    def fieldisdirty(self, field):
        return str(self.original.record[field]) != str(
            self._record[self._position][field]
        )

    def recordisdirty(self):
        dirtyfields = []
        for field in self._record[self._position]:
            if self.fieldisdirty(field):
                dirtyfields.append(field)
        return dirtyfields

    #
    #   internal methods
    #

    def delete_record_from_DB(self):
        """
        delete record from the DB
        """
        cursor = self.DBConnection.cursor()
        sql = self.sql.delete(self._record[self._position]["ID"])
        try:
            cursor.execute(sql)
        except:
            print("sql error {sql}".format(sql=sql))
        self.DBConnection.commit()

        # delete record from the dictionary
        self.delete()

    def update_current_record_in_DB(self):

        # Insert New Record "ID" Field is None
        if self._record[self._position]["ID"] == None:
            cursor = self.DBConnection.cursor()
            sql = self.sql.insert(self._record[self._position])
            try:
                cursor.execute(sql)
            except:
                print("sql error {sql}".format(sql=sql))
            self.DBConnection.commit()

            # Get the ID (autoincrement field) from the last Insert
            sql = "SELECT Last_Insert_ID();"
            try:
                cursor.execute(sql)
            except:
                print("sql error {sql}".format(sql=sql))
            lid = cursor.fetchone()
            cursor.close()
            self.setfieldvalue("ID", lid[0])

        # Update existing record only update fields that have changed.
        else:
            cursor = self.DBConnection.cursor()
            sql = self.sql.update(self._record[self._position])
            try:
                cursor.execute(sql)
            except:
                print("sql error {sql}".format(sql=sql))
            self.DBConnection.commit()
            cursor.close()
        self.original.saverecord(self.current())

    def __close__(self):
        if self.DBConnection.isconnected():
            self.DBConnection.close()
