"""Read and write framework configuration values stored by an application."""

import mysql
import mysql.connector
from JSForm import clsDB


def _close_cursor(cursor, operation_failed=False):
    """Close ``cursor`` without masking an active database-operation failure."""
    try:
        cursor.close()
    except Exception:
        if not operation_failed:
            raise


def _missing_optional_framework_table(error):
    """Return whether a framework-default table is intentionally absent."""
    return getattr(error, "errno", None) == 1146


class clsConfig:
    """
    clsConfig.py - Configuration Class for getting and setting system configuration data
    Rev. Jonathan C. Watt
    July 2022

    this class gives the tools to manager system configuration.
    it first looks in the application configuration table.
    if config value is not found it looks in the JSForm configuration table.

    ConfigFamily - Group for the configuration value (all may be read at once)
    ConfigType - Individual configuration key

    CREATE TABLE IF NOT EXISTS `tblconfig` (
        `ID` int(11) NOT NULL AUTO_INCREMENT,
        `ConfigFamily` varchar(255) NOT NULL,
        `ConfigType` varchar(100) NOT NULL,
        `ConfigValue` varchar(255) NOT NULL,
        `Note` longtext DEFAULT NULL,
    PRIMARY KEY (`ID`),
    )

    """

    def __init__(self, DB=None):
        if not DB:
            self.DBConnection = None
            self.JSConnection = None
        else:
            self.DBConnection = DB.DBConnection
            self.JSConnection = DB.JSConnection

    def set_Config_DBConnection(self, DB):
        """Use an application's paired application/framework connections."""
        self.DBConnection = DB.DBConnection
        self.JSConnection = DB.JSConnection

    def get_Config_Value(self, ConfigFamily, ConfigType):
        """Return one value, preferring application config then framework config."""
        if self.DBConnection == None:
            return None
        SQL = "SELECT ConfigValue FROM tblConfig WHERE ConfigFamily = %s AND ConfigType = %s;"
        cursor = self.DBConnection.cursor()
        operation_failed = False
        try:
            cursor.execute(SQL, (ConfigFamily, ConfigType))
            row = cursor.fetchone()
        except:
            operation_failed = True
            row = None
        finally:
            _close_cursor(cursor, operation_failed)
        if not row:
            SQL = "SELECT ConfigValue FROM jsConfig WHERE ConfigFamily = %s AND ConfigType = %s;"
            cursor = self.JSConnection.cursor()
            operation_failed = False
            try:
                cursor.execute(SQL, (ConfigFamily, ConfigType))
                row = cursor.fetchone()
            except Exception as error:
                operation_failed = True
                if _missing_optional_framework_table(error):
                    row = None
                else:
                    raise
            finally:
                _close_cursor(cursor, operation_failed)
        return row[0] if row else None

    def set_Config_Value(self, ConfigFamily, ConfigType, ConfigValue):
        """Update an application value without committing the caller's transaction."""
        if self.DBConnection == None:
            return None
        SQL = "UPDATE tblConfig SET ConfigFamily = %s, ConfigValue = %s WHERE ConfigType = %s;"
        cursor = self.DBConnection.cursor()
        operation_failed = False
        try:
            cursor.execute(SQL, (ConfigFamily, ConfigValue, ConfigType))
        except:
            operation_failed = True
            raise
        finally:
            _close_cursor(cursor, operation_failed)

    def get_Config_Family(self, configfamily):
        """Return family rows, preferring application then framework config."""
        if self.DBConnection == None:
            return None
        SQL = "SELECT ConfigType, ConfigValue FROM tblConfig WHERE ConfigFamily = %s;"
        cursor = self.DBConnection.cursor()
        operation_failed = False
        try:
            cursor.execute(SQL, (configfamily,))
            rows = cursor.fetchall()
        except:
            operation_failed = True
            rows = None
        finally:
            _close_cursor(cursor, operation_failed)
        if not rows:
            SQL = "SELECT ConfigType, ConfigValue FROM jsConfig WHERE ConfigFamily = %s;"
            cursor = self.JSConnection.cursor()
            operation_failed = False
            try:
                cursor.execute(SQL, (configfamily,))
                rows = cursor.fetchall()
            except Exception as error:
                operation_failed = True
                if _missing_optional_framework_table(error):
                    rows = []
                else:
                    raise
            finally:
                _close_cursor(cursor, operation_failed)
        return rows

CONFIG = clsConfig()            #   Application Configuration
