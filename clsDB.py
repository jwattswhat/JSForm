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


def database_operation_message(error, operation):
    """Translate common database constraint errors into user-facing guidance."""
    messages = {
        1048: "A required database value is missing.",
        1062: "This record duplicates an existing value.",
        1451: "This record cannot be deleted because other records still use it.",
        1452: "The selected related record no longer exists.",
    }
    return messages.get(
        getattr(error, "errno", None),
        "Unable to {} the database record.".format(operation),
    )
from JSForm.db_connections import DatabaseConnections, DatabaseSettings
from JSForm.record_state import RecordState

class clsDB:
    """
    clsDB - Database Class
    Rev. Jonathan C. Watt
    July 2021

    to manager connections and credentials for sql databases
    
    DB = dictionary description of username, password, host, database
    DBconnection = connection to database

        host - DB Host
        databasename - database name
        username - user id
        password - user password
            if username or password are unspecified a dalog box will open for input
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


    def __init__(self, host=None, databasename=None, username=None, password=None, jsform_database="JSForm"):
        global CONFIG,OPTION,FONT
        if host == None or databasename == None or username == None or password  == None:
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
        application_settings = DatabaseSettings(host, databasename, username, password)
        framework_settings = DatabaseSettings(host, jsform_database, username, password)
        self.CONNECTIONS = DatabaseConnections(
            application_settings, framework_settings, mysql.connector.connect
        )
        # Compatibility attributes retained for existing applications.
        self.DBCredintials = application_settings.connector_arguments()
        self.JSCredintials = framework_settings.connector_arguments()
        self.DBConnection = self.CONNECTIONS.application
        self.JSConnection = self.CONNECTIONS.framework

    def close(self):
        self.CONNECTIONS.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

class clsRecord(RecordState):
    """
        clsRecord -
        Rev. Jonathan C. Watt
        July 2021

        Manages the loading of records from the specified database
        loads all records specified with valid sql select into a dictionary
        setting the first one as current. 
        first,next,prev,last step through the records.
        it allows for updates and deletion of the current record.

        also manages "dirty" records and fields.
            as a new record becomes current the value is saved for comparision
            recordisdirty returns true if the old value doesn't match the current.

    """
    BlankRecord = -1

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
        super().__init__()
        self.DBConnection = connection
        self.TABLENAME = table["name"]
        self.TABLE = table
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
            rows = cursor.fetchall()
        except Exception as error:
            raise RuntimeError("Unable to read records from {}.".format(self.TABLENAME)) from error
        finally:
            cursor.close()
        if len(rows) == 0:
            return []

        records = self.sql.format_sql_records(rows)
        if records != []:
            return records
        return []

    #
    #   internal methods
    #

    def delete_record_from_DB(self):
        """
        delete record from the DB
        """
        cursor = self.DBConnection.cursor()
        sql, values = self.sql.delete_statement(self.current()["ID"])
        try:
            cursor.execute(sql, values)
            self.DBConnection.commit()
        except Exception as error:
            self.DBConnection.rollback()
            raise RuntimeError(database_operation_message(error, "delete")) from error
        finally:
            cursor.close()

        # delete record from the dictionary
        self.delete()

    def update_current_record_in_DB(self):
        """Save the current record, preserving an assigned ID on first insert.

        A record is new when its saved original ID was blank. Applications may
        therefore assign a stable primary key before the first save without
        causing JSForm to mistake the record for an existing database row.
        """
        is_new = self.original.record.get("ID") is None
        if is_new:
            cursor = self.DBConnection.cursor()
            assigned_id = self.current().get("ID")
            sql, values = self.sql.insert_statement(self.current())
            try:
                cursor.execute(sql, values)
                new_id = assigned_id if assigned_id is not None else cursor.lastrowid
                self.DBConnection.commit()
            except Exception as error:
                self.DBConnection.rollback()
                raise RuntimeError(database_operation_message(error, "insert")) from error
            finally:
                cursor.close()
            self.setfieldvalue("ID", new_id)

        # Update existing record only update fields that have changed.
        else:
            cursor = self.DBConnection.cursor()
            sql, values = self.sql.update_statement(self.current())
            try:
                cursor.execute(sql, values)
                self.DBConnection.commit()
            except Exception as error:
                self.DBConnection.rollback()
                raise RuntimeError(database_operation_message(error, "update")) from error
            finally:
                cursor.close()
        self.original.saverecord(self.current())

    def __close__(self):
        if self.DBConnection.isconnected():
            self.DBConnection.close()
