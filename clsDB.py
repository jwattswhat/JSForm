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


class RecordOperationError(RuntimeError):
    """Raised when JSForm cannot safely classify a pending record save."""


class DatabaseCredentialError(RuntimeError):
    """Raised when protected database credentials cannot be resolved safely."""


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
            self.password = wx.TextCtrl(
                panel, wx.ID_ANY, pos=(100,110), size=(200,30), style=wx.TE_PASSWORD,
            )
            btnok = wx.Button(panel,wx.ID_OK,label="Connect",pos=(10,150),size=(100,30))


    def __init__(
        self, host=None, databasename=None, username=None, password=None,
        credential_target=None, credential_store=None,
    ):
        global CONFIG,OPTION,FONT
        self.CONNECTIONS = None
        self.DBConnection = None
        self.cancelled = False
        self.DBCredintials = self._nonsecret_arguments(host, databasename, username)

        target_supplied = credential_target is not None
        target = str(credential_target or "").strip()
        if target_supplied and not target:
            raise DatabaseCredentialError("A protected database credential target is required.")
        if target and password is not None:
            raise DatabaseCredentialError(
                "Use either a protected database credential target or an in-memory password, not both."
            )
        if credential_store is not None and not target:
            raise DatabaseCredentialError(
                "A credential provider requires a protected database credential target."
            )

        needs_prompt = (
            host is None or databasename is None
            or (not target and (username is None or password is None))
        )
        if needs_prompt:
            dlg = self._getcredentials(self, title="Enter DB Login info")
            try:
                if host:
                    dlg.host.SetValue(host)
                if databasename:
                    dlg.database.SetValue(databasename)
                if username:
                    dlg.username.SetValue(username)
                if password is not None:
                    dlg.password.SetValue(password)
                result = dlg.ShowModal()
                if result == JSForm.CONST.FORM_CANCEL:
                    self.cancelled = True
                    return
                host = dlg.host.GetValue()
                databasename = dlg.database.GetValue()
                username = dlg.username.GetValue()
                if not target:
                    password = dlg.password.GetValue()
            finally:
                dlg.Destroy()

        host = str(host or "").strip()
        databasename = str(databasename or "").strip()
        username = str(username or "").strip()
        if not host or not databasename:
            raise DatabaseCredentialError("Database host and name are required.")

        if target:
            try:
                if credential_store is None:
                    from JSForm.credential_store import WindowsCredentialStore
                    credential_store = WindowsCredentialStore()
                stored_username, password = credential_store.read(target)
            except Exception:
                raise DatabaseCredentialError(
                    "The protected database credential could not be read."
                ) from None
            stored_username = str(stored_username or "").strip()
            if username and username != stored_username:
                password = None
                raise DatabaseCredentialError(
                    "The database username does not match the protected credential."
                )
            username = stored_username

        if not username or password is None or password == "":
            password = None
            raise DatabaseCredentialError("Database username and password are required.")

        self.DBCredintials = self._nonsecret_arguments(host, databasename, username)
        application_settings = DatabaseSettings(host, databasename, username, password)
        try:
            connections = DatabaseConnections(application_settings, mysql.connector.connect)
        finally:
            password = None
            application_settings = None
        self.CONNECTIONS = connections
        self.DBConnection = connections.application

    @staticmethod
    def _nonsecret_arguments(host, database, username):
        return {
            "host": host,
            "database": database,
            "user": username,
            "password": None,
        }

    def close(self):
        if self.CONNECTIONS is not None:
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

    def __init__(self, connection, table=None, operation_authorizer=None):
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
        self.operation_authorizer = operation_authorizer

    def pending_save_operation(self):
        """Return ``create`` or ``update`` from the saved original identity.

        Classification deliberately ignores an editable, preassigned current
        ID. Indeterminate state fails before an authorization call or cursor.
        """
        if self.current() is None or "ID" not in self.original.record:
            raise RecordOperationError("Unable to determine the pending save operation.")
        return "create" if self.original.record.get("ID") is None else "update"

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
        sql, parameters = self.sql.select_statement()
        try:
            cursor.execute(sql, parameters)
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
        operation = self.pending_save_operation()
        if self.operation_authorizer is not None:
            self.operation_authorizer(operation)
        if operation == "create":
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
